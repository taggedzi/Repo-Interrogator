"""Persistent index storage and refresh orchestration."""

from __future__ import annotations

import fnmatch
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from repo_mcp.config import IndexConfig
from repo_mcp.index.chunking import chunk_text
from repo_mcp.index.discovery import detect_index_delta, discover_files
from repo_mcp.index.models import ChunkRecord, FileRecord
from repo_mcp.index.search import SearchDocument, bm25_search

INDEX_SCHEMA_VERSION = 1


@dataclass(slots=True, frozen=True)
class IndexStatus:
    """Current index status snapshot."""

    index_status: str
    last_refresh_timestamp: str | None
    indexed_file_count: int
    indexed_chunk_count: int


@dataclass(slots=True, frozen=True)
class IndexSchemaUnsupportedError(Exception):
    """Raised when stored index schema does not match supported version."""

    found: int
    expected: int


class IndexManager:
    """Manages deterministic persistent index files."""

    def __init__(self, repo_root: Path, data_dir: Path, index_config: IndexConfig) -> None:
        self._repo_root = repo_root.resolve()
        self._index_config = index_config
        self._data_dir = data_dir.resolve()
        self._index_dir = self._data_dir / "index"
        self._manifest_path = self._index_dir / "manifest.json"
        self._files_path = self._index_dir / "files.jsonl"
        self._chunks_path = self._index_dir / "chunks.jsonl"
        self._data_dir_prefix = self._compute_data_dir_prefix()
        self._search_docs_cache_marker: str | None = None
        self._search_docs_cache: list[SearchDocument] | None = None

    def status(self) -> IndexStatus:
        """Return status derived from manifest, if present."""
        manifest = self._read_manifest()
        if manifest is None:
            return IndexStatus(
                index_status="not_indexed",
                last_refresh_timestamp=None,
                indexed_file_count=0,
                indexed_chunk_count=0,
            )
        schema = manifest.get("schema_version")
        if not isinstance(schema, int) or schema != INDEX_SCHEMA_VERSION:
            return IndexStatus(
                index_status="schema_mismatch",
                last_refresh_timestamp=None,
                indexed_file_count=0,
                indexed_chunk_count=0,
            )
        return IndexStatus(
            index_status="ready",
            last_refresh_timestamp=_as_optional_str(manifest.get("last_refresh_timestamp")),
            indexed_file_count=_as_optional_int(manifest.get("indexed_file_count")) or 0,
            indexed_chunk_count=_as_optional_int(manifest.get("indexed_chunk_count")) or 0,
        )

    def refresh(self, force: bool = False) -> dict[str, object]:
        """Refresh index with incremental behavior by default."""
        start = time.perf_counter()
        discovery_profile: dict[str, object] = {}
        load_previous_started = time.perf_counter()
        previous_records: dict[str, FileRecord] = {}
        if self._manifest_path.exists():
            if force:
                previous_records = self._load_file_records(allow_schema_mismatch=True)
            else:
                previous_records = self._load_file_records(allow_schema_mismatch=False)
        load_previous_seconds = time.perf_counter() - load_previous_started

        discover_started = time.perf_counter()
        current_records = self._filter_internal_records(
            discover_files(
                self._repo_root,
                self._index_config,
                previous_records=previous_records,
                profile=discovery_profile,
            )
        )
        discover_seconds = time.perf_counter() - discover_started

        if force:
            previous_paths = sorted(previous_records.keys())
            current_paths = sorted(record.path for record in current_records)
            previous_set = set(previous_paths)
            current_set = set(current_paths)
            added = tuple(sorted(current_set - previous_set))
            removed = tuple(sorted(previous_set - current_set))
            updated = tuple(sorted(current_set & previous_set))
        else:
            delta = detect_index_delta(previous=previous_records, current_records=current_records)
            added = delta.added
            updated = delta.updated
            removed = delta.removed

        chunk_started = time.perf_counter()
        chunks = self._build_chunks(current_records)
        chunk_seconds = time.perf_counter() - chunk_started
        timestamp = _utc_now_iso()
        manifest = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "last_refresh_timestamp": timestamp,
            "indexed_file_count": len(current_records),
            "indexed_chunk_count": len(chunks),
        }
        write_started = time.perf_counter()
        self._write_all(manifest, current_records, chunks)
        write_seconds = time.perf_counter() - write_started
        duration_ms = int((time.perf_counter() - start) * 1000)
        result: dict[str, object] = {
            "added": len(added),
            "updated": len(updated),
            "removed": len(removed),
            "duration_ms": duration_ms,
            "timestamp": timestamp,
        }
        result["refresh_profile"] = {
            "load_previous_seconds": load_previous_seconds,
            "discover_seconds": discover_seconds,
            "chunk_seconds": chunk_seconds,
            "write_seconds": write_seconds,
            "discovery": discovery_profile,
        }
        return result

    def search(
        self,
        query: str,
        top_k: int,
        file_glob: str | None = None,
        path_prefix: str | None = None,
    ) -> list[dict[str, object]]:
        """Run deterministic BM25 search over indexed chunks."""
        if top_k < 1:
            return []
        docs = self._load_search_documents()
        filtered = self._filter_search_documents(docs, file_glob=file_glob, path_prefix=path_prefix)
        if not filtered:
            return []
        return bm25_search(documents=filtered, query=query, top_k=top_k)

    def _load_search_documents(self) -> list[SearchDocument]:
        marker = self._search_cache_marker()
        if self._search_docs_cache is not None and self._search_docs_cache_marker == marker:
            return self._search_docs_cache

        chunks = self._load_chunks()
        line_cache: dict[str, list[str]] = {}
        docs: list[SearchDocument] = []
        for chunk in chunks:
            lines = line_cache.get(chunk.path)
            if lines is None:
                path = self._repo_root / chunk.path
                if not path.exists() or not path.is_file():
                    continue
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                line_cache[chunk.path] = lines
            start_idx = max(0, chunk.start_line - 1)
            end_idx = min(len(lines), chunk.end_line)
            text = "\n".join(lines[start_idx:end_idx])
            docs.append(
                SearchDocument(
                    path=chunk.path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    text=text,
                )
            )

        self._search_docs_cache = docs
        self._search_docs_cache_marker = marker
        return docs

    def _search_cache_marker(self) -> str:
        manifest = self._read_manifest()
        if manifest is None:
            return "not_indexed"
        schema = manifest.get("schema_version")
        indexed_file_count = manifest.get("indexed_file_count")
        indexed_chunk_count = manifest.get("indexed_chunk_count")
        refresh_timestamp = manifest.get("last_refresh_timestamp")
        return (
            f"{schema}:{indexed_file_count}:{indexed_chunk_count}:"
            f"{refresh_timestamp if isinstance(refresh_timestamp, str) else ''}"
        )

    def _build_chunks(self, records: list[FileRecord]) -> list[ChunkRecord]:
        chunks: list[ChunkRecord] = []
        for record in records:
            path = self._repo_root / record.path
            text = path.read_text(encoding="utf-8", errors="replace")
            chunks.extend(chunk_text(path=record.path, text=text))
        chunks.sort(key=lambda item: (item.path, item.start_line))
        return chunks

    def _load_chunks(self) -> list[ChunkRecord]:
        manifest = self._read_manifest()
        if manifest is None:
            return []
        schema = manifest.get("schema_version")
        if not isinstance(schema, int):
            raise IndexSchemaUnsupportedError(found=-1, expected=INDEX_SCHEMA_VERSION)
        if schema != INDEX_SCHEMA_VERSION:
            raise IndexSchemaUnsupportedError(found=schema, expected=INDEX_SCHEMA_VERSION)
        if not self._chunks_path.exists():
            return []

        chunks: list[ChunkRecord] = []
        for obj in self._read_jsonl(self._chunks_path):
            path = obj.get("path")
            start_line = obj.get("start_line")
            end_line = obj.get("end_line")
            chunk_id = obj.get("chunk_id")
            if not isinstance(path, str):
                continue
            if not isinstance(start_line, int):
                continue
            if not isinstance(end_line, int):
                continue
            if not isinstance(chunk_id, str):
                continue
            chunks.append(
                ChunkRecord(
                    path=path,
                    start_line=start_line,
                    end_line=end_line,
                    chunk_id=chunk_id,
                )
            )
        chunks.sort(key=lambda item: (item.path, item.start_line))
        return chunks

    @staticmethod
    def _filter_chunks(
        chunks: list[ChunkRecord],
        file_glob: str | None,
        path_prefix: str | None,
    ) -> list[ChunkRecord]:
        output: list[ChunkRecord] = []
        normalized_prefix = _normalize_path_prefix(path_prefix)
        for chunk in chunks:
            if file_glob is not None and not fnmatch.fnmatch(chunk.path, file_glob):
                continue
            if normalized_prefix is not None and not chunk.path.startswith(normalized_prefix):
                continue
            output.append(chunk)
        return output

    @staticmethod
    def _filter_search_documents(
        documents: list[SearchDocument],
        file_glob: str | None,
        path_prefix: str | None,
    ) -> list[SearchDocument]:
        output: list[SearchDocument] = []
        normalized_prefix = _normalize_path_prefix(path_prefix)
        for doc in documents:
            if file_glob is not None and not fnmatch.fnmatch(doc.path, file_glob):
                continue
            if normalized_prefix is not None and not doc.path.startswith(normalized_prefix):
                continue
            output.append(doc)
        return output

    def _filter_internal_records(self, records: list[FileRecord]) -> list[FileRecord]:
        if self._data_dir_prefix is None:
            return records
        filtered: list[FileRecord] = []
        for record in records:
            if record.path == self._data_dir_prefix:
                continue
            if record.path.startswith(f"{self._data_dir_prefix}/"):
                continue
            filtered.append(record)
        return filtered

    def _compute_data_dir_prefix(self) -> str | None:
        if not self._data_dir.is_relative_to(self._repo_root):
            return None
        return self._data_dir.relative_to(self._repo_root).as_posix()

    def _load_file_records(self, allow_schema_mismatch: bool) -> dict[str, FileRecord]:
        manifest = self._read_manifest()
        if manifest is None:
            return {}

        schema = manifest.get("schema_version")
        if not isinstance(schema, int):
            raise IndexSchemaUnsupportedError(found=-1, expected=INDEX_SCHEMA_VERSION)
        if schema != INDEX_SCHEMA_VERSION and not allow_schema_mismatch:
            raise IndexSchemaUnsupportedError(found=schema, expected=INDEX_SCHEMA_VERSION)

        if not self._files_path.exists():
            return {}
        output: dict[str, FileRecord] = {}
        for obj in self._read_jsonl(self._files_path):
            path = obj.get("path")
            size = obj.get("size")
            mtime_ns = obj.get("mtime_ns")
            content_hash = obj.get("content_hash")
            if not isinstance(path, str):
                continue
            if not isinstance(size, int):
                continue
            if not isinstance(mtime_ns, int):
                continue
            if not isinstance(content_hash, str):
                continue
            output[path] = FileRecord(
                path=path,
                size=size,
                mtime_ns=mtime_ns,
                content_hash=content_hash,
            )
        return output

    def _write_all(
        self,
        manifest: dict[str, object],
        records: list[FileRecord],
        chunks: list[ChunkRecord],
    ) -> None:
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(self._manifest_path, manifest)
        self._atomic_write_jsonl(self._files_path, [asdict(record) for record in records])
        self._atomic_write_jsonl(self._chunks_path, [asdict(chunk) for chunk in chunks])

    def _read_manifest(self) -> dict[str, object] | None:
        if not self._manifest_path.exists():
            return None
        with self._manifest_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, object]]:
        output: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    output.append(obj)
        return output

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
        tmp.replace(path)

    @staticmethod
    def _atomic_write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True))
                handle.write("\n")
        tmp.replace(path)


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _as_optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _as_optional_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _normalize_path_prefix(path_prefix: str | None) -> str | None:
    if not isinstance(path_prefix, str):
        return None
    normalized = path_prefix.replace("\\", "/").strip()
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized
