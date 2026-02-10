"""Deterministic file discovery and incremental change detection."""

from __future__ import annotations

import fnmatch
import hashlib
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from repo_mcp.config import IndexConfig
from repo_mcp.index.models import FileRecord, IndexDelta

_BINARY_SNIFF_BYTES = 4096


@dataclass(slots=True, frozen=True)
class DiscoveryProfile:
    """Deterministic diagnostics for one discovery pass."""

    total_candidates: int
    excluded_by_glob: int
    excluded_by_extension: int
    unchanged_reused: int
    binary_excluded: int
    hashed_files: int
    stat_seconds: float
    binary_sniff_seconds: float
    hash_seconds: float
    total_seconds: float


def discover_files(
    repo_root: Path,
    config: IndexConfig,
    previous_records: dict[str, FileRecord] | None = None,
    profile: dict[str, object] | None = None,
) -> list[FileRecord]:
    """Discover indexable text files with deterministic ordering."""
    started = time.perf_counter()
    root = repo_root.resolve()
    candidates: list[tuple[str, Path]] = []
    total_candidates = 0
    excluded_by_glob = 0
    excluded_by_extension = 0
    stat_seconds = 0.0
    binary_sniff_seconds = 0.0
    hash_seconds = 0.0
    reused = 0
    binary_excluded = 0
    hashed_files = 0

    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        total_candidates += 1
        relative = candidate.relative_to(root).as_posix()
        if should_exclude(relative, config.exclude_globs):
            excluded_by_glob += 1
            continue
        if not has_allowed_extension(relative, config.include_extensions):
            excluded_by_extension += 1
            continue
        candidates.append((relative, candidate))

    candidates.sort(key=lambda item: item[0])
    records: list[FileRecord] = []
    prior = previous_records or {}
    for rel, full_path in candidates:
        stat_started = time.perf_counter()
        stat = full_path.stat()
        stat_seconds += time.perf_counter() - stat_started
        previous = prior.get(rel)
        if (
            previous is not None
            and previous.size == stat.st_size
            and previous.mtime_ns == stat.st_mtime_ns
        ):
            records.append(
                FileRecord(
                    path=rel,
                    size=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                    content_hash=previous.content_hash,
                )
            )
            reused += 1
            continue
        sniff_started = time.perf_counter()
        if is_binary_file(full_path):
            binary_sniff_seconds += time.perf_counter() - sniff_started
            binary_excluded += 1
            continue
        binary_sniff_seconds += time.perf_counter() - sniff_started
        hash_started = time.perf_counter()
        content_hash = sha256_file(full_path)
        hash_seconds += time.perf_counter() - hash_started
        hashed_files += 1
        records.append(
            FileRecord(
                path=rel,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                content_hash=content_hash,
            )
        )

    if profile is not None:
        payload = DiscoveryProfile(
            total_candidates=total_candidates,
            excluded_by_glob=excluded_by_glob,
            excluded_by_extension=excluded_by_extension,
            unchanged_reused=reused,
            binary_excluded=binary_excluded,
            hashed_files=hashed_files,
            stat_seconds=stat_seconds,
            binary_sniff_seconds=binary_sniff_seconds,
            hash_seconds=hash_seconds,
            total_seconds=time.perf_counter() - started,
        )
        profile.update(asdict(payload))
    return records


def detect_index_delta(
    previous: dict[str, FileRecord],
    current_records: list[FileRecord],
) -> IndexDelta:
    """Compute deterministic added/updated/unchanged/removed sets."""
    current = record_map(current_records)
    previous_paths = set(previous.keys())
    current_paths = set(current.keys())

    added = sorted(current_paths - previous_paths)
    removed = sorted(previous_paths - current_paths)

    updated: list[str] = []
    unchanged: list[str] = []
    for path in sorted(previous_paths & current_paths):
        if previous[path] == current[path]:
            unchanged.append(path)
            continue
        updated.append(path)

    return IndexDelta(
        added=tuple(added),
        updated=tuple(updated),
        unchanged=tuple(unchanged),
        removed=tuple(removed),
    )


def record_map(records: list[FileRecord]) -> dict[str, FileRecord]:
    """Map records by relative path."""
    return {record.path: record for record in records}


def should_exclude(relative_path: str, exclude_globs: tuple[str, ...]) -> bool:
    """Return True when a path matches configured ignore globs."""
    anchored = f"/{relative_path}"
    return any(
        fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(anchored, pattern)
        for pattern in exclude_globs
    )


def has_allowed_extension(relative_path: str, include_extensions: tuple[str, ...]) -> bool:
    """Return True when file extension is included."""
    suffix = Path(relative_path).suffix.lower()
    return suffix in include_extensions


def build_file_record(repo_root: Path, full_path: Path) -> FileRecord:
    """Build file metadata + content hash record."""
    relative_path = full_path.relative_to(repo_root.resolve()).as_posix()
    stat = full_path.stat()
    content_hash = sha256_file(full_path)
    return FileRecord(
        path=relative_path,
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        content_hash=content_hash,
    )


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash in deterministic chunked reads."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 128)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def is_binary_file(path: Path) -> bool:
    """Use deterministic content sniffing to exclude binary files."""
    with path.open("rb") as handle:
        sample = handle.read(_BINARY_SNIFF_BYTES)
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False
