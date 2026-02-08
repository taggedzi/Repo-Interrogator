# Configuration

Repo Interrogator loads configuration in this exact order:

1. built-in defaults
2. optional `repo_mcp.toml` at `repo_root`
3. CLI/startup overrides

## Defaults

Current defaults:

- `max_file_bytes = 1_048_576`
- `max_open_lines = 500`
- `max_total_bytes_per_response = 262_144`
- `max_search_hits = 50`
- `index.include_extensions = [.py, .md, .rst, .toml, .yaml, .yml, .json, .ini, .cfg]`
- `index.exclude_globs = ["**/.git/**", "**/__pycache__/**", "**/.venv/**"]`
- `adapters.python_enabled = true`
- `data_dir = <repo_root>/.repo_mcp`

## Hard Caps

Overrides may lower limits freely, or raise only up to these caps:

- `max_file_bytes <= 4_194_304`
- `max_open_lines <= 2_000`
- `max_total_bytes_per_response <= 1_048_576`
- `max_search_hits <= 200`

Values above caps fail fast with explicit errors.

## Repo Config File

Path:

- `<repo_root>/repo_mcp.toml`

Example:

```toml
[limits]
max_file_bytes = 1048576
max_open_lines = 500
max_total_bytes_per_response = 262144
max_search_hits = 50

[index]
include_extensions = [".py", ".md", ".rst", ".toml", ".yaml", ".yml", ".json", ".ini", ".cfg"]
exclude_globs = ["**/.git/**", "**/__pycache__/**", "**/.venv/**"]

[adapters]
python_enabled = true
```

## CLI Overrides

Available startup flags:

```bash
repo-mcp \
  --repo-root /path/to/repo \
  --data-dir /path/to/data_dir \
  --max-file-bytes 1048576 \
  --max-open-lines 500 \
  --max-total-bytes-per-response 262144 \
  --max-search-hits 50 \
  --python-adapter-enabled true
```

## Denylist Policy

Denylist relaxation is not supported in v1.

These `repo_mcp.toml` keys are rejected:
- `security.denylist_override`
- `security.denylist_allowlist`
- `security.denylist_relax`

## Data Directory Contents

The server writes deterministic local artifacts under `data_dir`:

- `audit.jsonl`
- `index/manifest.json`
- `index/files.jsonl`
- `index/chunks.jsonl`
- `last_bundle.json`
- `last_bundle.md`

## Notes on Determinism

- Sorting is explicit for file/chunk ordering.
- Search ranking uses deterministic tie-breaks.
- Context bundle generation is deterministic for fixed repo state and inputs.
