# AI Integration (MCP over STDIO)

This guide explains how to connect AI tooling to Repo Interrogator.

## MCP in Plain Language

MCP is a way for an AI client to call local tools.

In this project, the MCP server runs as a local process. The AI client sends JSON requests to stdin and reads JSON responses from stdout.

## What "STDIO transport" means

- The AI client starts `repo-mcp` as a subprocess.
- The client writes one JSON object per line to stdin.
- The server writes one JSON object per line to stdout.
- There is no HTTP server, port, or remote service.

## Launch Command

Use one of these:

```bash
repo-mcp --repo-root /absolute/path/to/target/repo
```

or

```bash
python -m repo_mcp.server --repo-root /absolute/path/to/target/repo
```

Optional flags:
- `--data-dir`
- `--max-file-bytes`
- `--max-open-lines`
- `--max-total-bytes-per-response`
- `--max-search-hits`
- `--max-references`
- `--python-adapter-enabled true|false`

Default discovery excludes common non-source/cache/output directories (for example `.git`, `.github`, `.repo_mcp`, `__pycache__`, `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `node_modules`, `dist`, `build`, `target`).
This reduces noise and improves retrieval latency for index/search/references.
If your repo stores important content in excluded paths, adjust `index.exclude_globs` in `repo_mcp.toml`.

Environment variables:
- none required by this server

## Important Compatibility Note

Current implementation supports:
- direct method calls (for example `{"method":"repo.status"...}`)
- `tools/call` requests (`params.name` + `params.arguments`)

Current implementation does not expose a dedicated tools discovery endpoint.

So, tool names and argument shapes should be preconfigured in the client using this fixed tool set:
- `repo.status`
- `repo.list_files`
- `repo.open_file`
- `repo.outline`
- `repo.search`
- `repo.references`
- `repo.build_context_bundle`
- `repo.refresh_index`
- `repo.audit_log`

## Client Setup Examples

These are practical templates. Client-specific field names may vary.

## A) Claude Desktop style config (template)

Use this as a starting point only, then adjust to your client's exact schema.

```json
{
  "mcpServers": {
    "repo-interrogator": {
      "command": "repo-mcp",
      "args": [
        "--repo-root",
        "/absolute/path/to/target/repo"
      ]
    }
  }
}
```

If `repo-mcp` is not on PATH, use:
- full executable path, or
- `python` + `-m repo_mcp.server` in command/args form.

## B) Cursor or Windsurf external tool style (generic)

Use a local command tool entry that launches:

```bash
repo-mcp --repo-root /absolute/path/to/target/repo
```

Set transport to STDIO if your client asks.

Because exact config keys vary by version, map these concepts:
- executable command
- argument array
- working directory (optional)
- stdio transport mode

## C) Any MCP client (generic checklist)

1. Configure subprocess command and args.
2. Point `--repo-root` at one target repository.
3. Send newline-delimited JSON requests.
4. Parse response envelope fields:
   - `ok`
   - `blocked`
   - `result`
   - `warnings`
   - `error` (if present)

## How AI should choose tools

A practical order:

1. `repo.status` to check limits/index state.
2. `repo.refresh_index` if index is stale or not built.
3. `repo.search` to locate relevant files/ranges.
4. `repo.open_file` for exact lines.
5. `repo.outline` for declaration structure (Python AST + lexical adapters).
6. `repo.references` for cross-file usage links (`symbol` + optional `path` scope).
7. `repo.build_context_bundle` when you need compact cited context.
8. `repo.audit_log` for diagnostics and verification.

When using `repo.outline`, each symbol includes:
- `kind`, `name`, `signature`, `start_line`, `end_line`, `doc`
- optional v2 metadata: `parent_symbol`, `scope_kind`, `is_conditional`, `decl_context`

Interpretation notes:
- Outline output is declaration-based and deterministic.
- Python includes nested and conditional declarations as syntactic facts.
- Runtime branch truth is not evaluated.

`repo.references` notes:
- Returns deterministic declaration-linked references with `strategy` + `confidence`.
- Python uses `ast`; non-Python uses lexical fallback in v2.5.
- Use `top_k` to bound payload size and `path` to scope to one file.
- When `path` is omitted, candidate files are selected using the same discovery filters as indexing (`include_extensions` + `exclude_globs` + binary exclusion).

`repo.build_context_bundle` v2.5 explainability notes:
- Each selection includes `why_selected` with signal and score component details.
- `audit.ranking_debug` includes bounded ranking candidate diagnostics.

## How to interpret and use results safely

- Treat `blocked: true` as final for that request. Do not guess hidden content.
- Use citations from bundle output and search ranges.
- Quote file references as `path:start_line-end_line`.
- Keep excerpts small and tied to exact ranges.

Example citation style:
- `src/repo_mcp/server.py:120-168`
- `src/repo_mcp/tools/builtin.py:140-190`

## Prompt snippet for AI clients

Paste this into your AI tool's system or task prompt:

```text
Use Repo Interrogator tools before making assumptions.
Start with repo.status.
If needed, run repo.refresh_index.
Use repo.search to find relevant code, then repo.open_file and repo.outline for exact evidence.
For larger tasks, call repo.build_context_bundle with a strict budget and cite file paths with line ranges.
If a tool response is blocked, do not infer blocked content.
```

## Minimal request example

```json
{"id":"ai-1","method":"repo.status","params":{}}
```

Example `tools/call` request:

```json
{
  "id": "ai-2",
  "method": "tools/call",
  "params": {
    "name": "repo.search",
    "arguments": {
      "query": "build_context_bundle",
      "mode": "bm25",
      "top_k": 5
    }
  }
}
```

Reference lookup example:

```json
{
  "id": "ai-3",
  "method": "tools/call",
  "params": {
    "name": "repo.references",
    "arguments": {
      "symbol": "Service.run",
      "top_k": 10
    }
  }
}
```

Bundle explainability example (result snippet):

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
          "reference_count_in_range": 0
        }
      }
    }
  ],
  "audit": {
    "ranking_debug": {
      "candidate_count": 3,
      "definition_match_count": 1,
      "reference_proximity_count": 0
    }
  }
}
```
