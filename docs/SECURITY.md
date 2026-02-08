# Security Model

Repo Interrogator is designed to reduce accidental data exposure while allowing AI-assisted repository interrogation.

## Threat Model Summary

Primary risks addressed:
- reading files outside the target repository
- path traversal and symlink escape
- accidental exposure of sensitive files
- oversized responses that leak too much context
- hidden logging of sensitive values

Out of scope in v1:
- remote network service hardening (server is STDIO only)
- secret scanning of repository content

## Sandboxing Rules

All file access is scoped to one configured `repo_root`.

Blocked by design:
- absolute paths outside `repo_root`
- `..` traversal segments
- symlink-resolved paths outside `repo_root`

See:
- `SPEC.md` section 7
- `docs/adr/ADR-0006-repo-sandboxing.md`

## Deny-by-default File Policy

Default denylist includes:
- `.env`
- `*.pem`, `*.key`, `*.pfx`, `*.p12`
- `id_rsa*`
- files named like `secrets.*`
- `.git` internals

Current v1 policy:
- denylist cannot be relaxed through repo config
- blocked reads return explicit reason/hint
- blocking is preferred over redaction

## Limits and Guardrails

Runtime guardrails include:
- max file bytes
- max open lines
- max total response bytes
- max search hits

Overrides are bounded by hard caps in config logic.

## Audit Logging

Audit log path:
- `data_dir/audit.jsonl`

Audit entries include:
- timestamp
- request_id
- tool name
- success/blocked state
- error code
- sanitized metadata

What is not recorded:
- raw prompt text
- raw query text
- full file contents
- credentials, environment variable values, or token values

## Safe Usage Guidance for Untrusted Repos

- use dedicated local clones for untrusted code
- keep strict limits for file and response sizes
- review `blocked` responses instead of trying to bypass them
- do not run with overly permissive filesystem assumptions

## Security Reporting

Use the project vulnerability reporting process in root `SECURITY.md`.
