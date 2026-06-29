# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Repo Interrogator** is a local-first, deterministic MCP (Model Context Protocol) server that exposes safe, structured, read-only access to a single code repository over STDIO. It is **not** a CLI app, not a code-modifying agent, and makes no LLM calls. All indexing, search, outlining, and context bundling must be deterministic.

`SPEC.md` is the authoritative source of truth for behavior and intent. When guidance conflicts: `SPEC.md` > `docs/` > code > `AGENTS.md` > `CLAUDE.md`.

## Environment Setup

All Python commands must run inside the `.venv/` virtual environment. Do not create, replace, or modify it — if it is missing, stop and ask.

```bash
# Developer install
python -m venv .venv
source .venv/bin/activate        # or .venv\Scripts\activate on Windows
python -m pip install -e .
python -m pip install ruff mypy pytest build
```

## Commands

```bash
# Format (Ruff replaces Black — do not reintroduce Black)
python -m ruff format .

# Lint
python -m ruff check .

# Type check
python -m mypy src

# Run all tests
python -m pytest -q

# Run a single test file
python -m pytest tests/unit/adapters/test_python_outline_symbols.py -q

# Run tests with coverage
python -m pytest --cov

# Build package artifacts
python -m build
```

## Architecture

```
src/repo_mcp/
├── server.py          # StdioServer — JSON-line MCP request loop, tool dispatch, audit logging
├── config.py          # Config loading: defaults → repo_mcp.toml → CLI overrides
├── tools/
│   ├── registry.py    # ToolRegistry — maps tool names to callables
│   └── builtin.py     # Registers all built-in MCP tools
├── index/
│   ├── manager.py     # IndexManager — persistent BM25 index, incremental refresh
│   ├── search.py      # BM25 search, tokenization, tie-break ordering
│   ├── discovery.py   # File discovery using include_extensions / exclude_globs
│   ├── chunking.py    # Deterministic line-based chunking (200 lines, 30-line overlap)
│   └── models.py      # FileRecord, ChunkRecord dataclasses
├── adapters/
│   ├── base.py        # OutlineSymbol, SymbolReference, AdapterProtocol
│   ├── registry.py    # AdapterRegistry — selects adapter by file extension
│   ├── python.py      # Python adapter: AST-based outline + cross-file references
│   ├── lexical.py     # Lexical fallback adapter (regex-based outline)
│   ├── ts_js.py / java.py / go.py / rust.py / cpp.py / csharp.py  # Language adapters
│   └── fallback.py    # Catch-all for unsupported extensions
├── bundler/
│   ├── engine.py      # Deterministic context bundle assembly (no LLM)
│   └── models.py      # BundleResult, BundleSelection, BundleAudit, etc.
├── security/
│   ├── paths.py       # resolve_repo_path, symlink/traversal blocking
│   └── policy.py      # enforce_file_access_policy, sensitive file denylist
└── logging/
    └── audit.py       # JsonlAuditLogger, AuditEvent, sanitize_arguments
```

### Request Flow

`stdin` → `StdioServer.serve()` → `handle_json_line()` → `ToolRegistry.dispatch()` → tool handler → JSON-line `stdout`.

Security checks (`resolve_repo_path`, `enforce_file_access_policy`) happen inside each tool handler before any file I/O. `PathBlockedError` and `PolicyBlockedError` are caught at the dispatch layer and returned as structured blocked responses. Every request is appended to a JSONL audit log at `.repo_mcp/audit.jsonl`.

### Configuration Merge Order

Defaults (`config.py`) → `repo_mcp.toml` (optional, at repo root) → CLI flags. Hard caps on all limits (e.g. `max_file_bytes ≤ 4 MiB`). Denylist relaxation is not supported in v1 and will raise on load.

### Adapters

Each language adapter implements `supports_path(path)`, `outline(path, text)`, and optionally `references_for_symbol` / `references_for_symbols`. The Python adapter uses `ast`; all others use the lexical fallback. Adapters are selected by `AdapterRegistry.select(path)` and must be pluggable — no Python-specific assumptions belong in core logic.

### Bundler Ranking

`repo.build_context_bundle` uses a fully deterministic lexicographic ranking key: `definition_match` → `reference_proximity` → `path_name_relevance` → `search_score` → `range_size_penalty`, with path/line/symbol tie-breaks. No randomization. The bundle engine also emits `why_selected` per excerpt and `why_not_selected_summary` in the audit payload.

## ADRs

Architectural Decision Records live in `docs/adr/`. Read relevant ADRs before proposing changes. Create or update an ADR when a change affects MCP tool schemas, repo sandboxing, dependencies, determinism guarantees, indexing/chunking/bundling, or adapter extensibility.

## Non-Negotiable Constraints

- **No LLM calls** — all logic must be deterministic.
- **No new dependencies** without prior discussion (license, stdlib alternatives, security review).
- **Sandbox all file access** to `repo_root` — block path traversal (`..`), symlink escapes, and absolute paths outside root. Prefer blocking over redaction; never partially leak content.
- **No network calls in tests** — tests must be self-contained and use temporary directories.
- **Ruff only** — do not reintroduce Black or Black-specific config.
- **Output ordering must be explicit and stable** — never rely on OS enumeration order.

## Profiling (opt-in)

Set env vars to enable profiling artifacts written to `.repo_mcp/perf/`:

- `REPO_MCP_PROFILE_REFERENCES=1` — per-call reference profiling JSONL
- `REPO_MCP_PROFILE_BUNDLER=1` — per-call bundler profiling JSONL
- `REPO_MCP_SERVER_CPROFILE_OUTPUT=<path>` — server-process cProfile dump
