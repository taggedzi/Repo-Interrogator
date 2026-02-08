# Security Policy

## Supported Versions

Security support applies to the latest development branch until the first stable release policy is published.

## Reporting a Vulnerability

Please report vulnerabilities privately to the maintainers with:

- impact summary,
- reproduction steps,
- affected paths/tools,
- suggested mitigation if known.

Do not include secrets in reports.

## Security Posture Highlights

- All file reads are scoped to `repo_root`.
- Path traversal and symlink escapes are blocked.
- Sensitive files are denylisted by default.
- Blocking is preferred over redaction.
- Audit logs are structured and must never include secrets or full file contents.

