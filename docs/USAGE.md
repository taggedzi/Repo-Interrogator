# Usage

This server uses MCP-style JSON messages over STDIO.

- Input: one JSON object per line
- Output: one JSON object per line

## Start the Server

Using console script:

```bash
repo-mcp --repo-root /absolute/path/to/target/repo
```

Using module form:

```bash
python -m repo_mcp.server --repo-root /absolute/path/to/target/repo
```

Optional startup overrides:

- `--data-dir`
- `--max-file-bytes`
- `--max-open-lines`
- `--max-total-bytes-per-response`
- `--max-search-hits`
- `--max-references`
- `--python-adapter-enabled true|false`

## Default Discovery Filters

By default, index and cross-file references skip common non-project/cache/output folders, including:

- `.git`, `.github`, `.repo_mcp`
- `__pycache__`, `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.nox`
- `node_modules`, `.pnpm-store`, `.yarn`, `.npm`, `.next`, `.nuxt`, `.svelte-kit`
- `.gradle`, `.idea`, `.vscode`
- `dist`, `build`, `target`, `bin`, `obj`, `out`, `coverage`, `tmp`, `temp`

This keeps retrieval focused on repository source/config content rather than language/tooling support artifacts.
If your repository intentionally stores source-of-truth files in excluded paths, override with `index.exclude_globs` in `repo_mcp.toml`.

## Request Shapes

The server accepts either of these request styles.

### Direct method style

```json
{"id":"req-1","method":"repo.status","params":{}}
```

### MCP tools/call style

```json
{
  "id": "req-2",
  "method": "tools/call",
  "params": {
    "name": "repo.search",
    "arguments": {
      "query": "token parser",
      "mode": "bm25",
      "top_k": 5
    }
  }
}
```

## Response Envelope

Success example:

```json
{
  "request_id": "req-1",
  "ok": true,
  "result": {},
  "warnings": [],
  "blocked": false
}
```

Blocked example:

```json
{
  "request_id": "req-3",
  "ok": false,
  "result": {
    "reason": "Path traversal is blocked.",
    "hint": "Remove '..' segments and use a repository-relative path."
  },
  "warnings": [],
  "blocked": true,
  "error": {
    "code": "PATH_BLOCKED",
    "message": "Path traversal is blocked."
  }
}
```

Error example:

```json
{
  "request_id": "req-4",
  "ok": false,
  "result": {},
  "warnings": [],
  "blocked": false,
  "error": {
    "code": "INVALID_PARAMS",
    "message": "repo.search query must be a non-empty string."
  }
}
```

## Core Tools

## `repo.status`
Use this first. It shows index state, active limits, adapters, and effective config.

Request:

```json
{"id":"req-s","method":"repo.status","params":{}}
```

Result fields include:
- `repo_root`
- `index_status` (`not_indexed`, `ready`, or `schema_mismatch`)
- `last_refresh_timestamp`
- `indexed_file_count`
- `enabled_adapters`
- `limits_summary`
- `chunking_summary`
- `effective_config`

## `repo.list_files`
List readable files under `repo_root`.

Params:
- `glob` (optional)
- `max_results` (optional, capped)
- `include_hidden` (optional, default `false`)

Request:

```json
{"id":"req-l","method":"repo.list_files","params":{"glob":"src/*.py","max_results":20}}
```

## `repo.open_file`
Read a line range from a file.

Params:
- `path`
- `start_line` (default `1`)
- `end_line` (optional)

Request:

```json
{"id":"req-o","method":"repo.open_file","params":{"path":"src/repo_mcp/server.py","start_line":1,"end_line":40}}
```

Result fields:
- `path`
- `numbered_lines` (`[{"line": n, "text": "..."}]`)
- `truncated`

## `repo.outline`
Get file structure from adapter output.

Params:
- `path`

Request:

```json
{"id":"req-out","method":"repo.outline","params":{"path":"src/repo_mcp/server.py"}}
```

Result fields:
- `path`
- `language` (adapter name)
- `symbols`:
  - `kind`
  - `name`
  - `signature`
  - `start_line`
  - `end_line`
  - `doc`
  - `parent_symbol` (optional v2 metadata)
  - `scope_kind` (optional v2 metadata: `module` | `class` | `function`)
  - `is_conditional` (optional v2 metadata)
  - `decl_context` (optional v2 metadata)

Current language values:
- `python`
- `ts_js_lexical`
- `java_lexical`
- `go_lexical`
- `rust_lexical`
- `cpp_lexical`
- `csharp_lexical`
- `lexical` (fallback)

TypeScript example:

```json
{"id":"req-out-ts","method":"repo.outline","params":{"path":"src/mod.ts"}}
```

C# example:

```json
{"id":"req-out-cs","method":"repo.outline","params":{"path":"src/Program.cs"}}
```

Notes:
- Python uses AST parsing and includes nested/conditional declarations as syntactic facts.
- Non-Python adapters are lexical and conservative by design.
- `repo.outline` is declaration-based and deterministic; runtime branch truth is not evaluated.
- `repo.outline` can work even when file extensions are not indexed for search.

## `repo.refresh_index`
Build or refresh the index on disk.

Params:
- `force` (optional bool)

Request:

```json
{"id":"req-r","method":"repo.refresh_index","params":{"force":false}}
```

Result fields:
- `added`
- `updated`
- `removed`
- `duration_ms`
- `timestamp`

## `repo.search`
Run deterministic BM25 search over indexed chunks.

Params:
- `query` (required)
- `mode` (must be `"bm25"` in v1)
- `top_k`
- `file_glob` (optional)
- `path_prefix` (optional)

Request:

```json
{
  "id": "req-search",
  "method": "repo.search",
  "params": {
    "query": "token parser",
    "mode": "bm25",
    "top_k": 5,
    "file_glob": "src/*.py"
  }
}
```

Hit fields:
- `path`
- `start_line`
- `end_line`
- `snippet`
- `score`
- `matched_terms`

## `repo.references` (v2.5)
Return deterministic cross-file references for one symbol.

Params:
- `symbol` (required)
- `path` (optional file scope)
- `top_k` (optional, bounded by reference limits)

Request:

```json
{
  "id": "req-ref",
  "method": "repo.references",
  "params": {
    "symbol": "Service.run",
    "top_k": 10
  }
}
```

Result fields:
- `symbol`
- `references`:
  - `symbol`
  - `path`
  - `line`
  - `kind`
  - `evidence`
  - `strategy` (`ast` or `lexical`)
  - `confidence` (`high`, `medium`, `low`)
- `truncated`
- `total_candidates`

Notes:
- Output ordering is deterministic and stable.
- Python references use AST extraction.
- TS/JS/Java/Go/Rust/C++/C# use lexical fallback in v2.5.

## `repo.build_context_bundle`
Build a deterministic context bundle.

Params:
- `prompt` (required)
- `budget` (required object)
  - `max_files`
  - `max_total_lines`
- `strategy` (must be `"hybrid"`)
- `include_tests` (bool)

Request:

```json
{
  "id": "req-bundle",
  "method": "repo.build_context_bundle",
  "params": {
    "prompt": "trace token parser flow",
    "budget": {"max_files": 4, "max_total_lines": 120},
    "strategy": "hybrid",
    "include_tests": false
  }
}
```

Result fields:
- `bundle_id`
- `prompt_fingerprint`
- `strategy`
- `budget`
- `totals`
- `selections`
- `citations`
- `audit`

`selections[*].why_selected` includes:
- `matched_signals`
- `score_components`
- `source_query`
- `matched_terms`
- `symbol_reference`

`audit.ranking_debug` includes:
- `candidate_count`
- `definition_match_count`
- `reference_proximity_count`
- `top_candidates` (bounded deterministic list)

Bundle explainability snippet:

```json
{
  "selections": [
    {
      "path": "src/service.py",
      "why_selected": {
        "matched_signals": ["search_score", "matched_terms", "definition_match", "aligned_symbol"],
        "score_components": {
          "search_score": 2.5,
          "definition_match": true,
          "reference_count_in_range": 0,
          "min_definition_distance": 1000000000,
          "path_name_relevance": 1,
          "range_size_penalty": 4
        }
      }
    }
  ],
  "audit": {
    "ranking_debug": {
      "candidate_count": 3,
      "definition_match_count": 1,
      "reference_proximity_count": 0,
      "top_candidates": [
        {"path": "src/service.py", "rank_position": 1, "selected": true}
      ]
    }
  }
}
```

Artifacts written to `data_dir`:
- `last_bundle.json`
- `last_bundle.md`

Important:
- Bundling uses search hits, so files must be indexed to appear in bundles.
- If you need TS/JS/Java/Go/Rust/C++/C# in bundles, add their extensions to `index.include_extensions` in `repo_mcp.toml`.

## LLM Performance Checklist

Use this checklist to keep retrieval fast and predictable in AI workflows:

- Scope references when possible: prefer `repo.references` with `path` for file-focused analysis.
- Keep index excludes tuned: ensure `index.exclude_globs` removes cache/build/tooling directories.
- Keep index includes focused: include only language extensions needed for your repository tasks.
- Bound response sizes: use `top_k` for search/references and strict budgets for bundles.
- Avoid repeated broad scans in loops: cache or reuse result IDs client-side when possible.
- Verify active config first: call `repo.status` and inspect `effective_config.index` and `limits_summary`.

## `repo.audit_log`
Read sanitized audit events.

Params:
- `since` (optional timestamp string)
- `limit` (optional int)

Request:

```json
{"id":"req-a","method":"repo.audit_log","params":{"limit":20}}
```

Event fields include:
- `timestamp`
- `request_id`
- `tool`
- `ok`
- `blocked`
- `error_code`
- `metadata`

## Realistic Workflow

1. Refresh index.

```json
{"id":"w1","method":"repo.refresh_index","params":{"force":false}}
```

2. Search for a symbol or term.

```json
{"id":"w2","method":"repo.search","params":{"query":"build_context_bundle","mode":"bm25","top_k":5}}
```

3. Open the top hit range.

```json
{"id":"w3","method":"repo.open_file","params":{"path":"src/repo_mcp/server.py","start_line":380,"end_line":470}}
```

4. Outline a key file.

```json
{"id":"w4","method":"repo.outline","params":{"path":"src/repo_mcp/server.py"}}
```

4a. (Optional v2.5) Resolve cross-file references for a symbol.

```json
{"id":"w4-ref","method":"repo.references","params":{"symbol":"Service.run","top_k":10}}
```

Optional multilingual outline checks:

```json
{"id":"w4a","method":"repo.outline","params":{"path":"src/mod.ts"}}
{"id":"w4b","method":"repo.outline","params":{"path":"src/mod.go"}}
{"id":"w4c","method":"repo.outline","params":{"path":"src/mod.rs"}}
```

5. Build a context bundle for your coding task.

```json
{
  "id": "w5",
  "method": "repo.build_context_bundle",
  "params": {
    "prompt": "explain server request handling and bundle flow",
    "budget": {"max_files": 5, "max_total_lines": 150},
    "strategy": "hybrid",
    "include_tests": true
  }
}
```

## Profiling Workflow Performance

Use the built-in workflow validator profiler when diagnosing bottlenecks:

```bash
.venv/bin/python scripts/validate_workflow.py --repo-root . --profile
```

Write a machine-readable profile artifact:

```bash
.venv/bin/python scripts/validate_workflow.py --repo-root . --profile --profile-output /tmp/validate_profile.json
```

Capture Python hotspot stats for deeper software profiling:

```bash
.venv/bin/python scripts/validate_workflow.py --repo-root . --profile --cprofile-output /tmp/validate_profile.pstats
```

Run repeatable benchmark profiling (3 runs per scenario by default; scenarios: `self,medium,large`):

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root .
```

Run only specific scenarios:

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root . --scenarios self,medium
```

Enable targeted `repo.references` profiling in benchmark runs:

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root . --profile-references
```

Enable targeted bundler profiling in benchmark runs:

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root . --profile-bundler
```

Control retention for session artifacts:

```bash
.venv/bin/python scripts/benchmark_workflow.py --repo-root . --retention-sessions 15
```

Notes:
- Profiling is opt-in and disabled by default.
- Profiling output is diagnostic metadata only; tool output contracts are unchanged.
- Benchmark outputs are sessioned under `.repo_mcp/perf/session-*/` with a latest summary at `.repo_mcp/perf/benchmark_summary.json`.
- With `--profile-references`, per-run `repo.references` timing artifacts are written as `references_run_*.jsonl` inside each scenario session directory.
- With `--profile-bundler`, per-run bundler timing artifacts are written as `bundler_run_*.jsonl` inside each scenario session directory.
- For bottleneck diagnosis workflow and interpretation guidance, see `docs/PERFORMANCE_PLAYBOOK.md`.

## Language Adapter Limitations

The current non-Python adapters are lexical. This keeps behavior deterministic and dependency-light, but some syntax is intentionally conservative.

- TypeScript/JavaScript:
  - Best for classes, functions, exports, and common method forms.
  - Dynamic exports and complex metaprogramming may be partial.
- Java:
  - Best for top-level types plus constructors/methods.
  - Nested/anonymous classes and complex generic syntax can be partial.
- Go:
  - Best for package types, funcs, methods, const/var groups.
  - Build tags and uncommon declaration layouts can be partial.
- Rust:
  - Best for `mod/struct/enum/trait/impl/fn/const/type`.
  - Macro-generated items and advanced trait bounds can be partial.
- C++:
  - Best for namespaces, class/struct/enum, common methods/functions.
  - Heavy template/macro/function-pointer forms can be partial.
- C#:
  - Best for namespace/type/method/property/event and constructors.
  - Partial classes and advanced expression-bodied patterns can be partial.
