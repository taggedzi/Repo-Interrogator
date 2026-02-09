from __future__ import annotations

from repo_mcp.adapters import (
    LexicalRules,
    extract_identifier_tokens,
    mask_comments_and_strings,
    scan_brace_blocks,
)


def test_unterminated_comment_and_string_are_handled_safely() -> None:
    source = 'start /* comment\nnext = "unterminated\nfinal'

    masked = mask_comments_and_strings(source)

    assert masked.count("\n") == source.count("\n")
    tokens = extract_identifier_tokens(masked)
    assert [token.text for token in tokens] == ["start"]


def test_unmatched_braces_report_counts_without_raising() -> None:
    source = "fn x() {\n  if (ok) {\n    }\n}}\n{\n"
    result = scan_brace_blocks(source)

    assert result.unmatched_closing == 1
    assert result.unclosed_opening == 1
    assert [block.depth for block in result.blocks] == [1, 2]


def test_custom_rules_support_sql_style_comments() -> None:
    source = "SELECT value -- hidden\nFROM t;"
    rules = LexicalRules(
        line_comment_prefixes=("--",), block_comment_pairs=(), string_delimiters=("'",)
    )

    masked = mask_comments_and_strings(source, rules=rules)
    tokens = extract_identifier_tokens(masked)

    assert [token.text for token in tokens] == ["SELECT", "value", "FROM", "t"]
