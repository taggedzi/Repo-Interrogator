"""Indexing and search package."""

from .chunking import (
    DEFAULT_CHUNK_LINES,
    DEFAULT_CHUNK_OVERLAP_LINES,
    build_chunk_id,
    chunk_text,
)
from .discovery import detect_index_delta, discover_files, record_map
from .manager import INDEX_SCHEMA_VERSION, IndexManager, IndexSchemaUnsupportedError, IndexStatus
from .models import ChunkRecord, FileRecord, IndexDelta

__all__ = [
    "ChunkRecord",
    "DEFAULT_CHUNK_LINES",
    "DEFAULT_CHUNK_OVERLAP_LINES",
    "FileRecord",
    "INDEX_SCHEMA_VERSION",
    "IndexManager",
    "IndexSchemaUnsupportedError",
    "IndexStatus",
    "IndexDelta",
    "build_chunk_id",
    "chunk_text",
    "detect_index_delta",
    "discover_files",
    "record_map",
]
