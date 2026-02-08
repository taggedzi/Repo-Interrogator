# Troubleshooting

## 1) "Path blocked" errors

Symptom:
- `blocked: true`
- `error.code: "PATH_BLOCKED"`

Common causes:
- `..` traversal in `path`
- absolute path outside `repo_root`
- symlink path that escapes `repo_root`
- denylisted file (`.env`, keys, `.git`, `secrets.*`)

What to do:
- use repo-relative paths (for example `src/app.py`)
- avoid denylisted files
- keep reads inside configured repository

## 2) Index appears empty or stale

Symptom:
- `repo.status` shows `index_status: "not_indexed"`
- `repo.search` returns no hits

What to do:
1. run `repo.refresh_index` with `force:false`
2. re-run `repo.status`
3. if schema mismatch, run `repo.refresh_index` with `force:true`

## 3) Permission or file write issues

Symptom:
- warnings about artifact writes
- bundle warnings mention `last_bundle.json` or `last_bundle.md`

What to do:
- check write permission for `data_dir`
- set `--data-dir` to a writable directory

## 4) Windows and WSL path quirks

Use either style:
- `src/main.py`
- `src\\main.py`

Tips:
- prefer repo-relative paths
- avoid mixed absolute path roots
- for search filters, use normalized prefixes like `src/`

## 5) Encoding issues

The server reads text with UTF-8 and `errors="replace"` for file content operations.

If text looks odd:
- confirm file encoding
- use smaller line ranges with `repo.open_file`

## 6) Large file or range blocked

Symptom examples:
- `File exceeds max_file_bytes limit.`
- `Requested line range exceeds max_open_lines limit.`
- `Response exceeds max_total_bytes_per_response limit.`

What to do:
- request fewer lines
- reduce `top_k`
- lower output scope with `file_glob` or `path_prefix`
- adjust limits within allowed caps in config/startup flags

## 7) "Tool not found" or invalid params

Symptom:
- `error.code: "UNKNOWN_TOOL"` or `"INVALID_PARAMS"`

Check tool names exactly:
- `repo.status`
- `repo.list_files`
- `repo.open_file`
- `repo.outline`
- `repo.search`
- `repo.build_context_bundle`
- `repo.refresh_index`
- `repo.audit_log`

## 8) No verbose log flag available

Current implementation does not expose a verbose logging CLI flag.

What you can inspect:
- audit log at `data_dir/audit.jsonl`
- bundle artifacts at `data_dir/last_bundle.json` and `data_dir/last_bundle.md`
- index artifacts at `data_dir/index/*`

## 9) Minimal "is it alive" check

Run one request through STDIO:

```bash
printf '%s\n' '{"id":"t1","method":"repo.status","params":{}}' \
  | repo-mcp --repo-root /absolute/path/to/target/repo
```

If healthy, you will get one JSON response line.

## 10) Minimal request format check

If requests fail parsing, verify:
- each request is valid JSON
- one JSON object per line
- has `method` string
- has `params` object

Example valid line:

```json
{"id":"x1","method":"repo.status","params":{}}
```
