from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.generate_release_notes import (
    CommitEntry,
    classify_subject,
    normalize_subject,
    render_release_notes,
    update_changelog,
)


def test_classify_subject_by_prefix() -> None:
    assert classify_subject("feat: add references support") == "Features"
    assert classify_subject("fix: handle missing top_k") == "Fixes"
    assert classify_subject("perf: reduce ranking candidates") == "Performance"
    assert classify_subject("docs: add workflow recipe") == "Documentation"
    assert classify_subject("tests: add integration coverage") == "Tests"
    assert classify_subject("ci: add optional perf guardrail job") == "Build/CI"
    assert classify_subject("chore: cleanup") == "Chores"
    assert classify_subject("update deterministic ordering") == "Other"


def test_normalize_subject_strips_known_prefix() -> None:
    assert normalize_subject("feat: add release helper") == "Add release helper"
    assert normalize_subject("docs: improve guide") == "Improve guide"
    assert normalize_subject("raw message") == "Raw message"


def test_render_release_notes_is_deterministic() -> None:
    commits = [
        CommitEntry(sha="aaaaaaaaaaaaaaa", subject="feat: add release helper"),
        CommitEntry(sha="bbbbbbbbbbbbbbb", subject="fix: enforce changelog version check"),
        CommitEntry(sha="ccccccccccccccc", subject="docs: update release process"),
    ]
    rendered = render_release_notes(
        from_ref="v2.5.0",
        to_ref="HEAD",
        commits=commits,
        generated_utc=datetime(2026, 2, 10, 19, 0, tzinfo=UTC),
    )
    assert "range: `v2.5.0..HEAD`" in rendered
    assert "commit_count: `3`" in rendered
    assert "## Features" in rendered
    assert "- Add release helper (`aaaaaaa`)" in rendered
    assert "## Fixes" in rendered
    assert "- Enforce changelog version check (`bbbbbbb`)" in rendered
    assert "## Documentation" in rendered
    assert "- Update release process (`ccccccc`)" in rendered


def test_update_changelog_adds_new_section(tmp_path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n", encoding="utf-8")
    notes = "# Release Notes\n\n## Features\n\n- Add release helper (`aaaaaaa`)\n"
    update_changelog(
        changelog_path=changelog,
        version="v2.6.0",
        notes=notes,
        today=datetime(2026, 2, 10, tzinfo=UTC).date(),
    )
    content = changelog.read_text(encoding="utf-8")
    assert "## [v2.6.0] - 2026-02-10" in content
    assert "- Add release helper (`aaaaaaa`)" in content


def test_update_changelog_rejects_duplicate_version(tmp_path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [v2.6.0] - 2026-02-10\n\n", encoding="utf-8")
    with pytest.raises(ValueError):
        update_changelog(
            changelog_path=changelog,
            version="v2.6.0",
            notes="# Release Notes\n",
            today=datetime(2026, 2, 10, tzinfo=UTC).date(),
        )
