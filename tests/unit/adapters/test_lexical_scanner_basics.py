from __future__ import annotations

from repo_mcp.adapters import (
    extract_identifier_tokens,
    mask_comments_and_strings,
    scan_brace_blocks,
)


def test_mask_comments_and_strings_preserves_lines_and_masks_text() -> None:
    source = 'const value = "inside"; // comment token\nfunction run() { return value; }\n'

    masked = mask_comments_and_strings(source)

    assert masked.count("\n") == source.count("\n")
    assert "inside" not in masked
    assert "comment" not in masked
    assert "function run()" in masked


def test_extract_identifier_tokens_skips_masked_regions() -> None:
    source = "const value = `template`; // hidden_token\nlet next_value = value;\n"

    masked = mask_comments_and_strings(source)
    tokens = extract_identifier_tokens(masked)

    token_texts = [token.text for token in tokens]
    assert token_texts == ["const", "value", "let", "next_value", "value"]


def test_scan_brace_blocks_returns_stable_nested_ranges() -> None:
    source = "function a() {\n  if (ok) {\n    run();\n  }\n}\n"

    masked = mask_comments_and_strings(source)
    result = scan_brace_blocks(masked)

    assert result.unmatched_closing == 0
    assert result.unclosed_opening == 0
    assert len(result.blocks) == 2
    assert [block.depth for block in result.blocks] == [1, 2]
    assert result.blocks[0].start_line == 1
    assert result.blocks[0].end_line == 5
    assert result.blocks[1].start_line == 2
    assert result.blocks[1].end_line == 4
