# Contributing to Repo Interrogator

Thanks for contributing.

This project is a **local-first, deterministic MCP server** for repository interrogation. Contributions should preserve safety, auditability, and deterministic behavior.

## Ground Rules

- Follow `SPEC.md` as the source of truth for product behavior.
- Keep the server passive and interrogative (no code-modifying behavior).
- Preserve determinism: no hidden heuristics, no nondeterministic ordering.
- Keep all file access scoped to `repo_root` and maintain sandbox protections.
- Do not add dependencies without prior discussion and approval.

## Before You Start

1. Read:
- `SPEC.md`
- `README.md`
- `AGENTS.md` (workflow guardrails)
- Relevant ADRs in `docs/adr/`

2. If your change affects architecture or contracts, create/update an ADR.

## Development Setup

Python 3.11+ is required (3.12+ recommended for development).

```bash
python -m pip install -e .
python -m pip install -e .[dev]
```

If you use a virtual environment, activate it first.

## Required Quality Gates

Run all checks before opening a PR:

```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest
```

## Testing Expectations

- Tests must be deterministic and self-contained.
- No network calls in tests.
- Filesystem tests should use temporary directories.
- Add/adjust tests for all behavior changes.
- Update golden fixtures/snapshots when behavior intentionally changes.

## API and Tool Contract Changes

`repo.*` tool schemas and response shapes are API contracts.

If your change modifies tool behavior or schema:
- update `SPEC.md`
- update relevant docs in `docs/`
- add/update ADR(s)
- include migration notes in your PR description

## Pull Request Guidelines

Please include:

- What changed
- Why it changed
- How it was tested
- Determinism/safety impact
- Any follow-up work

Keep PRs focused and avoid unrelated refactors.

## Dependency Changes

Dependency additions/replacements require explicit justification in the PR:

- license
- why stdlib/current deps are insufficient
- security and maintenance considerations

## Documentation

Update docs when behavior, defaults, limits, or tool responses change.

Common docs to touch:
- `README.md`
- `docs/USAGE.md`
- `docs/CONFIG.md`
- `docs/AI_INTEGRATION.md`
- `docs/adr/`

## Security and Sensitive Data

- Do not log secrets or environment variable values.
- Never leak blocked file content.
- Prefer explicit blocking with clear reasons.

## Code of Conduct

By participating, you agree to follow `CODE_OF_CONDUCT.md`.
