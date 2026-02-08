from __future__ import annotations

from repo_mcp.index import chunk_text


def test_chunk_ids_are_stable_for_same_input() -> None:
    text = "\n".join([f"line-{i}" for i in range(1, 260)])

    first = chunk_text(path="src/app.py", text=text)
    second = chunk_text(path="src/app.py", text=text)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]


def test_chunk_ids_change_when_content_changes() -> None:
    baseline = chunk_text(path="src/app.py", text="a\nb\nc\nd")
    changed = chunk_text(path="src/app.py", text="a\nb\nx\nd")

    assert baseline[0].chunk_id != changed[0].chunk_id
