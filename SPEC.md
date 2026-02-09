# SPEC.md

## Repo Interrogator (STDIO · Deterministic · Python-First)

---

## 1. Purpose

This project implements a **local-first Model Context Protocol (MCP) server** that exposes safe, structured, deterministic access to a single code repository.

Its role is to allow AI clients (Codex in VS Code, Codex CLI, agents) to **interrogate a codebase**—searching, outlining, and selectively reading files—in order to build high-quality task-specific context *before* executing coding tasks.

The server does **not** write code, apply patches, or run tests. It provides the tooling that makes AI-assisted coding scalable, auditable, and manageable for humans in large projects.

---

## 2. Design goals

### Primary goals

* Enable AI-driven **repo exploration**, not static context dumps
* Provide **deterministic, inspectable context selection**
* Enforce strong **sandboxing and safety**
* Produce **human-auditable artifacts**
* Deliver **high-quality Python support**
* Support **future expansion** without architectural rewrite

### Secondary goals

* Fast incremental indexing
* Minimal dependencies
* Cross-platform (Windows + Linux / WSL)

---

## 3. Non-goals

* No code generation or patch application
* No test execution
* No Git operations
* No multi-repo management
* No HTTP/SSE transport in v1
* No LLM calls in v1

---

## 4. Scope model

* **Single repository per server instance**
* Server launched with a fixed `repo_root`
* All operations strictly scoped to that repository

---

## 5. Transport

* **STDIO only (v1)**
* MCP-compliant request/response protocol
* Designed for IDE-embedded clients (Codex VS Code)

---

## 6. High-level architecture

```
AI Client (Codex / Agent)
        |
        |  MCP (STDIO)
        v
+---------------------------+
|  Repo Interrogation MCP   |
|                           |
|  - Tool Router            |
|  - Safety / Sandbox       |
|  - Audit Logger           |
|                           |
|  - Index Manager          |
|  - Search Engine (BM25)   |
|                           |
|  - Language Adapters      |
|    - Python (v1)          |
|    - Others (lexical)     |
|                           |
|  - Context Bundler        |
|    (Deterministic v1)     |
+---------------------------+
```

---

## 7. Security and sandboxing (mandatory)

### 7.1 Repo root enforcement

* All file paths are resolved relative to `repo_root`
* Reject:

  * absolute paths outside repo_root
  * `..` traversal
  * symlinks escaping repo_root

### 7.2 Sensitive file denylist (default)

Blocked by default:

* `.env`
* `*.pem`, `*.key`, `*.pfx`, `*.p12`
* `id_rsa*`
* `**/secrets.*`
* `**/.git/**`
* Files exceeding `MAX_FILE_BYTES`

Blocked reads must return:

* `blocked: true`
* explicit reason
* safe remediation hint

### 7.3 Limits (configurable)

* max file bytes
* max lines per open
* max total bytes per response
* max search hits
* max files per context bundle

### 7.4 Redaction policy

* Prefer **blocking over redaction**
* Redaction only if deterministic and safe
* Never guess or partially redact secrets

---

## 8. Configuration

### 8.1 Server startup config

* `repo_root` (required)
* `data_dir` (default: `<repo_root>/.repo_mcp`)
* limits:

  * `max_file_bytes`
  * `max_open_lines`
  * `max_total_bytes_per_response`
  * `max_search_hits`
* indexing:

  * included extensions
  * excluded globs
* embeddings (reserved for future):

  * `enabled = false`

### 8.2 Repo config (optional)

File: `repo_mcp.toml` at repo root

Used for:

* ignore globs
* extension overrides
* language adapter configuration
* future hybrid search parameters

Priority:

1. defaults
2. `repo_mcp.toml`
3. CLI flags

---

## 9. Indexing

### 9.1 Indexed files

Text-like files only:

* Python: `.py`
* Docs/config: `.md`, `.rst`, `.toml`, `.yaml`, `.yml`, `.json`, `.ini`, `.cfg`
* Optional web: `.js`, `.ts`, `.html`, `.css`

Binary files excluded by MIME/extension checks.

### 9.2 Chunking

* Deterministic line-based chunking
* Default:

  * 200 lines per chunk
  * 30-line overlap
* Chunks store:

  * path
  * start_line / end_line
  * stable chunk_id

Python adapter may propose smarter chunk boundaries.

### 9.3 Incremental refresh

* Track file hash + mtime
* Reindex only changed files
* Remove deleted files from index

---

## 10. Language adapters (plugin system)

### 10.1 Adapter design

Language behavior is implemented via adapters.

Each adapter may provide:

* `supports_path(path)`
* `outline(path, text)`
* optional:

  * `smart_chunks(path, text)`
  * `symbol_hints(prompt)`

### 10.2 Python adapter (required v1)

* Use `ast`
* Extract:

  * functions
  * classes
  * methods
  * signatures (best effort)
  * line ranges
  * first docstring line (optional)

Python v2 outline behavior (when enabled by spec/version):

* include declarations in nested scopes
* include declarations inside conditional blocks (`if`, `try`, `match`, etc.)
* do not evaluate runtime branch truth
* represent declarations as syntactic facts only

Other languages:

* lexical search + open_file only

Adapters must be pluggable without core changes.

### 10.3 Outline contract (v2, cross-adapter)

`outline(path, text)` is declaration-based and deterministic.

Required behavior:

* include syntactically declared symbols, including nested and conditional declarations
* never execute code and never evaluate runtime branch truth
* preserve deterministic ordering with explicit stable sort rules
* keep adapters pluggable; language-specific extraction remains in adapter layer

Required symbol fields (existing):

* `kind`
* `name`
* `signature`
* `start_line`
* `end_line`
* `doc` (optional)

New optional symbol fields (v2):

* `parent_symbol` (nullable): fully-qualified parent declaration name
* `scope_kind` (nullable): one of `module`, `class`, `function`
* `is_conditional` (nullable bool): true when declaration appears under control-flow
* `decl_context` (nullable string): compact deterministic declaration context label

Signature guidance:

* best effort only
* for Python classes, include bases and class keywords when representable from AST

Error handling:

* parse failures must not leak partial content
* adapters return an empty symbol list for unreadable/unparseable files

---

## 11. MCP tools (v1)

### Common response envelope

```json
{
  "request_id": "uuid",
  "ok": true,
  "result": {},
  "warnings": [],
  "blocked": false
}
```

---

### 11.1 `repo.status`

Returns:

* repo_root
* index status
* last refresh timestamp
* indexed file count
* enabled adapters
* limits summary

---

### 11.2 `repo.list_files`

Inputs:

* `glob?`
* `max_results?`
* `include_hidden?`

Returns:

* `{path, size, mtime}`

---

### 11.3 `repo.open_file`

Inputs:

* `path`
* `start_line`
* `end_line`

Returns:

* numbered lines
* truncation indicator

---

### 11.4 `repo.outline`

Inputs:

* `path`

Returns:

* language
* symbol list:

  * kind
  * name
  * signature
  * start_line
  * end_line
  * doc (optional)
  * parent_symbol (optional, v2)
  * scope_kind (optional, v2)
  * is_conditional (optional, v2)
  * decl_context (optional, v2)

Notes:

* symbol list is deterministic and declaration-based
* symbols represent syntactic declarations; runtime branch truth is not inferred

---

### 11.5 `repo.search`

Inputs:

* `query`
* `mode = "bm25"`
* `top_k`
* `file_glob?`

Returns:

* ranked hits:

  * path
  * line range
  * snippet
  * score
  * matched terms

---

### 11.6 `repo.refresh_index`

Inputs:

* `force?`

Returns:

* added / updated / removed counts
* duration
* new timestamp

---

### 11.7 `repo.build_context_bundle` (deterministic-only)

**Purpose:** Assemble a task-specific context bundle with citations.

Inputs:

* `prompt`
* `budget`:

  * `max_files`
  * `max_total_lines`
* `strategy = "hybrid"`
* `include_tests`

Outputs:

* `bundle_id`
* `prompt_fingerprint`
* selected files + ranges + rationale
* excerpts
* citations
* audit details

#### Deterministic bundling algorithm

1. Extract keywords from prompt
2. Run multiple searches (prompt + keywords)
3. Rank and dedupe hits
4. For Python files:

   * prefer symbol-aligned ranges
5. Open minimal necessary ranges
6. Enforce budgets strictly
7. Emit per-excerpt rationale

**Important:**
No LLM calls.
Architecture must allow future replacement with an LLM-assisted bundler without changing schemas.

---

### 11.8 `repo.audit_log`

Inputs:

* `since?`
* `limit?`

Returns:

* recent sanitized tool calls

---

## 12. Observability

* Structured JSONL audit log
* Each request has a stable `request_id`
* Optionally write:

  * `last_bundle.json`
  * `last_bundle.md`
    to `data_dir` for human inspection

---

## 13. Packaging

* Python 3.11+
* `pyproject.toml`
* Entry point: `repo_mcp.server:main`
* Directory layout:

  * `repo_mcp/`
  * `repo_mcp/adapters/`
  * `repo_mcp/index/`
  * `repo_mcp/bundler/`
  * `tests/`
* Include:

  * `README.md`
  * `AGENTS.md` (rules + safety constraints)
  * `examples/` configs

---

## 14. Testing requirements

### Unit tests

* path traversal blocking
* denylist enforcement
* limit enforcement
* incremental index correctness
* search stability
* Python outline accuracy
* nested declaration extraction (module/class/function scopes)
* conditional declaration extraction (without runtime evaluation)
* outline ordering stability across repeated runs
* symbol parent/scope metadata correctness (v2 fields)

### Integration tests

* start server
* call tools in sequence
* verify audit log correctness

### Cross-platform tests

* Windows vs Linux path normalization
* WSL compatibility

---

## 15. Milestones

**M0** – MCP server + sandbox + logging
**M1** – Index + BM25 search
**M2** – Python adapter + outline
**M3** – Deterministic context bundler
**M4** – Plugin + future-ready hooks
**M5** – v2 declaration-based outline semantics (nested/conditional + metadata)
