# Installation

This guide covers both end users and contributors.

## Requirements

- Python `>=3.11`
- A local filesystem path for your target repository
- No network service is required at runtime

## OS Notes

Repo Interrogator is local and cross-platform by design.

- Linux: supported
- WSL: supported
- Windows: supported with path normalization (for example `src\\file.py` and `src/file.py` both work)
- macOS: expected to work with Python 3.11+

## End-User Install

### Option A: install from source checkout (most direct)

```bash
git clone <your-fork-or-repo-url>
cd repomap
python -m pip install .
```

Then run:

```bash
repo-mcp --repo-root /absolute/path/to/target/repo
```

### Option B: isolated app install with pipx

If you already have this repository locally:

```bash
pipx install /absolute/path/to/repomap
```

Then run:

```bash
repo-mcp --repo-root /absolute/path/to/target/repo
```

## Developer Install

```bash
git clone <your-fork-or-repo-url>
cd repomap
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install ruff mypy pytest build
```

Notes:
- This project currently has no declared runtime dependencies in `pyproject.toml`.
- Dev tools (`ruff`, `mypy`, `pytest`, `build`) are installed separately.

## Required Project Checks

```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest -q
```

## Build Package Artifacts

```bash
python -m pip install build
python -m build
```

Artifacts are created in `dist/` (`.whl` and `.tar.gz`).

## Install Smoke Test from Artifacts

```bash
python -m pip install dist/*.whl
python -c "import repo_mcp, repo_mcp.server; print('wheel import ok')"

python -m pip uninstall -y repo-interrogator
python -m pip install dist/*.tar.gz
python -c "import repo_mcp, repo_mcp.server; print('sdist import ok')"
```
