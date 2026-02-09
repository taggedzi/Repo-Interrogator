# Security Policy

Thanks for helping keep Repo Interrogator safe.

Project:
- Repository: https://github.com/taggedzi/Repo-Interrogator
- Maintainer: https://github.com/taggedzi

For the detailed security model, see `docs/SECURITY.md`.

## Supported Versions

Security fixes are applied on a best-effort basis to the latest state of the default branch.

There is no formal LTS policy yet.

## Reporting a Vulnerability

Please report vulnerabilities **privately**.

Preferred channel:
- GitHub private vulnerability reporting (Security Advisories) for this repository.

Fallback (if private reporting is unavailable):
- Open a GitHub issue with minimal detail and request a private contact path.
- Do not publish proof-of-concept details publicly until triage is complete.

Include:
- impact summary
- reproduction steps
- affected paths/tools
- version/commit tested
- suggested mitigation (if known)

Please do **not** include secrets, tokens, private keys, or sensitive data in reports.

## Response Expectations

This is a single-maintainer project with limited time and resources.

- Initial acknowledgement may take time.
- Triage/remediation timelines are best-effort, not SLA-backed.
- Complex fixes may be scheduled across multiple releases.

I still take security reports seriously and appreciate clear, reproducible submissions.

## Disclosure Policy

- Please allow reasonable time for triage and patching before public disclosure.
- After a fix is available, coordinated disclosure is welcome.
- Credits can be included in release notes unless you request anonymity.

## Scope and Priorities

High-priority classes include:
- repo sandbox escape (`repo_root` boundary bypass)
- path traversal and symlink escape bypasses
- sensitive file access bypasses
- logging leaks of secrets or file contents
- response limit bypasses that can exfiltrate excess data

Out of scope (unless clearly connected to a concrete security impact in this project):
- generic hardening suggestions without exploit path
- issues requiring non-default, unsafe local modifications

## Security Posture Highlights

- file reads are scoped to `repo_root`
- path traversal and symlink escapes are blocked
- sensitive files are denylisted by default
- blocking is preferred over redaction
- audit logs are structured and sanitized
