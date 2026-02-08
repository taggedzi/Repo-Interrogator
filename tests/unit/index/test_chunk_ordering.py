from __future__ import annotations

from repo_mcp.index import chunk_text


def test_chunk_ordering_is_by_ascending_start_line() -> None:
    text = "\n".join([f"line-{i}" for i in range(1, 650)])
    chunks = chunk_text(path="docs/readme.md", text=text)

    starts = [chunk.start_line for chunk in chunks]
    assert starts == sorted(starts)

    paths = {chunk.path for chunk in chunks}
    assert paths == {"docs/readme.md"}
