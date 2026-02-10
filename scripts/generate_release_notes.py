#!/usr/bin/env python3
"""Generate deterministic release notes and optionally update CHANGELOG.md."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CommitEntry:
    """One git commit entry used for release-note generation."""

    sha: str
    subject: str


SECTION_ORDER = (
    "Features",
    "Fixes",
    "Performance",
    "Refactors",
    "Documentation",
    "Tests",
    "Build/CI",
    "Chores",
    "Other",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to cwd.")
    parser.add_argument(
        "--from-ref",
        default=None,
        help="Start reference (exclusive). Defaults to latest tag when available.",
    )
    parser.add_argument(
        "--to-ref",
        default="HEAD",
        help="End reference (inclusive). Defaults to HEAD.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path for generated release notes markdown.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print generated markdown to stdout.",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Version label for changelog entries (e.g., v2.6.0).",
    )
    parser.add_argument(
        "--update-changelog",
        action="store_true",
        help="Insert generated notes as the newest section in CHANGELOG.md.",
    )
    parser.add_argument(
        "--changelog-path",
        default="CHANGELOG.md",
        help="Changelog path used with --update-changelog. Default: CHANGELOG.md",
    )
    return parser.parse_args()


def _git(repo_root: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def resolve_latest_tag(repo_root: Path) -> str | None:
    """Return latest reachable tag, or None when no tag exists."""
    try:
        value = _git(repo_root, ["describe", "--tags", "--abbrev=0"])
    except RuntimeError:
        return None
    return value or None


def collect_commits(repo_root: Path, *, from_ref: str | None, to_ref: str) -> list[CommitEntry]:
    """Collect commit subjects in deterministic chronological order."""
    range_expr = f"{from_ref}..{to_ref}" if from_ref else to_ref
    output = _git(repo_root, ["log", "--reverse", "--pretty=format:%H%x1f%s", range_expr])
    entries: list[CommitEntry] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        if "\x1f" not in raw_line:
            continue
        sha, subject = raw_line.split("\x1f", 1)
        cleaned = subject.strip()
        if not cleaned:
            continue
        entries.append(CommitEntry(sha=sha.strip(), subject=cleaned))
    return entries


def classify_subject(subject: str) -> str:
    """Classify commit subject to one release-note section."""
    lowered = subject.lower()
    prefix = lowered.split(":", 1)[0].strip()
    if prefix in {"feat", "feature"}:
        return "Features"
    if prefix in {"fix", "bugfix"}:
        return "Fixes"
    if prefix in {"perf", "performance"}:
        return "Performance"
    if prefix in {"refactor"}:
        return "Refactors"
    if prefix in {"docs", "doc"}:
        return "Documentation"
    if prefix in {"test", "tests"}:
        return "Tests"
    if prefix in {"ci", "build"}:
        return "Build/CI"
    if prefix in {"chore"}:
        return "Chores"
    return "Other"


def normalize_subject(subject: str) -> str:
    """Normalize subject for concise bullet formatting."""
    value = subject.strip()
    if ":" in value:
        maybe_prefix, rest = value.split(":", 1)
        if maybe_prefix.strip().lower() in {
            "feat",
            "feature",
            "fix",
            "bugfix",
            "perf",
            "performance",
            "refactor",
            "docs",
            "doc",
            "test",
            "tests",
            "ci",
            "build",
            "chore",
        }:
            value = rest.strip()
    return value[:1].upper() + value[1:] if value else value


def render_release_notes(
    *,
    from_ref: str | None,
    to_ref: str,
    commits: list[CommitEntry],
    generated_utc: datetime,
) -> str:
    """Render deterministic markdown release notes."""
    lines = [
        "# Release Notes",
        "",
        f"- generated_utc: `{generated_utc.isoformat()}`",
        f"- range: `{from_ref or 'root'}..{to_ref}`",
        f"- commit_count: `{len(commits)}`",
        "",
    ]
    if not commits:
        lines.extend(["No commits found for the selected range.", ""])
        return "\n".join(lines).rstrip() + "\n"

    grouped: dict[str, list[CommitEntry]] = {section: [] for section in SECTION_ORDER}
    for entry in commits:
        grouped[classify_subject(entry.subject)].append(entry)

    for section in SECTION_ORDER:
        items = grouped[section]
        if not items:
            continue
        lines.append(f"## {section}")
        lines.append("")
        for item in items:
            short_sha = item.sha[:7]
            lines.append(f"- {normalize_subject(item.subject)} (`{short_sha}`)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_changelog(
    *,
    changelog_path: Path,
    version: str,
    notes: str,
    today: date,
) -> None:
    """Insert a new changelog section at top; fail if version already exists."""
    heading = f"## [{version}] - {today.isoformat()}"
    body_lines = [line for line in notes.splitlines() if line.strip()]
    section_lines = [heading, "", *body_lines, ""]
    section_text = "\n".join(section_lines) + "\n"

    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
    else:
        existing = "# Changelog\n\n"

    if heading in existing:
        raise ValueError(f"Changelog already contains section: {heading}")

    if not existing.startswith("# Changelog"):
        existing = "# Changelog\n\n" + existing.lstrip()

    if existing.endswith("\n"):
        updated = existing + section_text
    else:
        updated = existing + "\n\n" + section_text
    changelog_path.write_text(updated, encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    from_ref = args.from_ref if args.from_ref else resolve_latest_tag(repo_root)
    commits = collect_commits(repo_root, from_ref=from_ref, to_ref=args.to_ref)
    now = datetime.now(UTC)
    notes = render_release_notes(
        from_ref=from_ref,
        to_ref=args.to_ref,
        commits=commits,
        generated_utc=now,
    )

    if args.print or (not args.output and not args.update_changelog):
        print(notes, end="")

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = repo_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(notes, encoding="utf-8")

    if args.update_changelog:
        if not args.version:
            raise SystemExit("--version is required with --update-changelog")
        changelog_path = Path(args.changelog_path)
        if not changelog_path.is_absolute():
            changelog_path = repo_root / changelog_path
        changelog_path.parent.mkdir(parents=True, exist_ok=True)
        update_changelog(
            changelog_path=changelog_path,
            version=args.version,
            notes=notes,
            today=now.date(),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
