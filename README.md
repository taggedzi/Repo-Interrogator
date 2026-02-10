# Repo Interrogator

Repo Interrogator is a local-first, deterministic MCP server that helps AI tools inspect one code repository safely.

It is for repository interrogation, not code modification.

What it does:
- indexes files inside one `repo_root`
- runs deterministic BM25 search
- outlines code structure via pluggable language adapters
- builds context bundles with citations
- writes sanitized audit logs

What it does not do:
- no LLM calls in v1
- no code writes or patching
- no multi-repo routing
- no HTTP/SSE transport in v1

## Supported Environments

- Python: `>=3.11`
- Tested in this project: Linux and WSL paths, with explicit Windows path normalization tests
- Expected to run on: Linux, macOS, Windows (with Python 3.11+)

## Quick Start

1. Clone this repository and enter it:

```bash
git clone https://github.com/taggedzi/Repo-Interrogator
cd repomap
```

2. Install (end-user style):

```bash
python -m pip install .
```

This installs the console command `repo-mcp`.

3. Run against a local repository:

```bash
repo-mcp --repo-root /absolute/path/to/target/repo
```

The server uses STDIO. It waits for newline-delimited JSON requests and writes newline-delimited JSON responses.

4. Verify it responds:

```bash
printf '%s\n' '{"id":"req-1","method":"repo.status","params":{}}' \
  | repo-mcp --repo-root /absolute/path/to/target/repo
```

You should get a JSON envelope with keys like:
- `request_id`
- `ok`
- `result`
- `warnings`
- `blocked`

## Developer Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install ruff mypy pytest build
```

Run checks:

```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

## Tool Surface (Current)

- `repo.status`
- `repo.list_files`
- `repo.open_file`
- `repo.outline`
- `repo.search`
- `repo.references`
- `repo.build_context_bundle`
- `repo.refresh_index`
- `repo.audit_log`

## Language Adapter Support

`repo.outline` currently supports these adapters:

- Python: `python` (AST-based)
- TypeScript/JavaScript: `ts_js_lexical` (lexical)
- Java: `java_lexical` (lexical)
- Go: `go_lexical` (lexical)
- Rust: `rust_lexical` (lexical)
- C++: `cpp_lexical` (lexical)
- C#: `csharp_lexical` (lexical)
- Fallback: `lexical` (empty structural outline for unsupported files)

Important limits:
- Non-Python adapters are lexical. They are deterministic and fast, but conservative.
- Macro/generated code and advanced language features can be partially represented.
- Search, references, and context bundle coverage depend on indexed extensions/excludes.
- Start from `examples/repo_mcp.toml` for stack-aware include/exclude defaults and override guidance.

## Documentation

- Installation: `docs/INSTALL.md`
- Usage and request/response examples: `docs/USAGE.md`
- Configuration and limits: `docs/CONFIG.md`
- AI client integration (MCP over STDIO): `docs/AI_INTEGRATION.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- Issue labels and triage workflow: `docs/TRIAGE.md`
- Security policy and vulnerability reporting: `SECURITY.md`
- Security model and blocked behavior: `docs/SECURITY.md`
- Release process: `docs/release.md`

## Docs Verification Checklist

Run these commands to validate docs examples against the current codebase:

```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q

# quick server smoke
printf '%s\n' '{"id":"req-docs-1","method":"repo.status","params":{}}' \
  | python -m repo_mcp.server --repo-root .
```
