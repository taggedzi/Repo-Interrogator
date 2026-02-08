# Repo Interrogator

Repo Interrogator is a local-first, deterministic MCP server for safe interrogation of a single repository.

## Scope

- Integration-first MCP server for AI clients.
- STDIO transport only in v1.
- Deterministic indexing, search, outlining, and context bundling.
- Strong repository sandboxing with deny-by-default file access.

## Limits Policy (v1)

Default limits:

- `max_file_bytes = 1_048_576`
- `max_open_lines = 500`
- `max_total_bytes_per_response = 262_144`
- `max_search_hits = 50`

Repo config and startup overrides may lower these values or raise them only up to hard caps:

- `max_file_bytes <= 4_194_304`
- `max_open_lines <= 2_000`
- `max_total_bytes_per_response <= 1_048_576`
- `max_search_hits <= 200`

Values above caps fail fast with explicit configuration errors.

## Status

This repository is under active implementation. See `SPEC.md` for product requirements and `TODO.md` for the implementation sequence.
