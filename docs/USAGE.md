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
- `--python-adapter-enabled true|false`

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
- `language` (`python` or `lexical`)
- `symbols` (kind, name, signature, start_line, end_line, doc)

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

Artifacts written to `data_dir`:
- `last_bundle.json`
- `last_bundle.md`

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
