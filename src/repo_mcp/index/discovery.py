"""Deterministic file discovery and incremental change detection."""

from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path

from repo_mcp.config import IndexConfig
from repo_mcp.index.models import FileRecord, IndexDelta

_BINARY_SNIFF_BYTES = 4096


def discover_files(repo_root: Path, config: IndexConfig) -> list[FileRecord]:
    """Discover indexable text files with deterministic ordering."""
    root = repo_root.resolve()
    relative_paths: list[str] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(root).as_posix()
        if should_exclude(relative, config.exclude_globs):
            continue
        if not has_allowed_extension(relative, config.include_extensions):
            continue
        relative_paths.append(relative)

    relative_paths.sort()
    records: list[FileRecord] = []
    for rel in relative_paths:
        full_path = root / rel
        if is_binary_file(full_path):
            continue
        records.append(build_file_record(root, full_path))
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
