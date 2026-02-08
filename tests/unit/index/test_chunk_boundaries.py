from __future__ import annotations

from repo_mcp.index import chunk_text


def test_chunk_boundaries_follow_default_overlap_policy() -> None:
    lines = [f"line-{i}" for i in range(1, 501)]
    text = "\n".join(lines)

    chunks = chunk_text(path="src/main.py", text=text)

    assert len(chunks) == 3
    assert [(c.start_line, c.end_line) for c in chunks] == [
        (1, 200),
        (171, 370),
        (341, 500),
    ]
