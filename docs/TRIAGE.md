# Issue Triage Guide (Single Maintainer)

This guide defines a lightweight, repeatable triage workflow for one-maintainer operation.

Goals:
- keep issue intake deterministic and auditable
- prioritize high-impact defects first
- avoid stale backlog growth from ambiguous requests

## Label Set

Use these labels consistently:

- Type:
  - `bug`
  - `enhancement`
  - `documentation`
- Priority:
  - `priority:p0` (release-blocking / security-sensitive)
  - `priority:p1` (high user impact, should schedule soon)
  - `priority:p2` (normal backlog)
  - `priority:p3` (nice-to-have / speculative)
- Status:
  - `status:needs-triage`
  - `status:needs-info`
  - `status:ready`
  - `status:in-progress`
  - `status:blocked`
  - `status:wontfix`
- Area:
  - `area:adapters`
  - `area:index`
  - `area:search`
  - `area:references`
  - `area:bundler`
  - `area:security`
  - `area:docs`
  - `area:ci-release`
  - `area:performance`

## Triage Protocol

Apply this sequence to each new issue:

1. Confirm issue template quality.
2. Assign one `Type` label.
3. Assign one `Priority` label.
4. Assign one or more `Area` labels.
5. Set one `Status` label (`status:ready` or `status:needs-info`).
6. Link related issue/PR/ADR/SPEC sections.

## Priority Rules

- `priority:p0`:
  - security boundary regressions
  - deterministic contract breakages
  - CI/release pipeline failures that block shipping
- `priority:p1`:
  - major functionality regression in core tools (`repo.search`, `repo.references`, `repo.build_context_bundle`)
  - high-confidence correctness bug with clear reproduction
- `priority:p2`:
  - normal improvements, non-blocking bugs, docs gaps
- `priority:p3`:
  - exploratory ideas, optional enhancements, deferred polish

## Response SLO (Best Effort)

- new issue acknowledgement: within 3 business days
- first triage label set: within 7 business days
- `status:needs-info` timeout: close after 14 days without reporter response

## Close Rules

Close as `status:wontfix` when:
- proposal conflicts with `SPEC.md`/accepted ADR direction
- maintenance cost is disproportionate to user impact
- issue is duplicate/superseded by tracked work

When closing:
- add a concise rationale
- link related issue/ADR/SPEC section
- suggest next viable path if available

## Weekly Maintainer Sweep

Recommended weekly pass:

1. Re-check all `status:needs-triage`.
2. Re-check `status:needs-info` older than 14 days.
3. Promote at most 1-3 `status:ready` items into active TODO.
4. Ensure TODO mirrors only currently active work.
