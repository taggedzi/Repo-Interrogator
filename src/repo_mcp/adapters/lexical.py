"""Deterministic lexical scanning helpers for non-AST adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass

_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


@dataclass(slots=True, frozen=True)
class LexicalRules:
    """Configurable lexical markers used while masking non-code text."""

    line_comment_prefixes: tuple[str, ...] = ("//", "#")
    block_comment_pairs: tuple[tuple[str, str], ...] = (("/*", "*/"),)
    string_delimiters: tuple[str, ...] = ("'''", '"""', "'", '"', "`")
    escape_char: str = "\\"


@dataclass(slots=True, frozen=True)
class LexicalToken:
    """Identifier token with 1-based line/column metadata."""

    text: str
    line: int
    start_col: int
    end_col: int


@dataclass(slots=True, frozen=True)
class BraceBlock:
    """Matched brace block range with nesting depth."""

    start_line: int
    start_col: int
    end_line: int
    end_col: int
    depth: int


@dataclass(slots=True, frozen=True)
class BraceScanResult:
    """Result of deterministic brace scanning."""

    blocks: tuple[BraceBlock, ...]
    unmatched_closing: int
    unclosed_opening: int


def mask_comments_and_strings(text: str, rules: LexicalRules | None = None) -> str:
    """Mask comments and strings while preserving original line count and character offsets."""
    active_rules = rules or LexicalRules()
    line_prefixes = tuple(
        sorted(
            (prefix for prefix in active_rules.line_comment_prefixes if prefix),
            key=len,
            reverse=True,
        )
    )
    block_pairs = tuple(
        sorted(
            ((start, end) for start, end in active_rules.block_comment_pairs if start and end),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )
    )
    string_delimiters = tuple(
        sorted(
            (marker for marker in active_rules.string_delimiters if marker),
            key=len,
            reverse=True,
        )
    )

    chars = list(text)
    length = len(text)
    index = 0
    state: tuple[str, str] | None = None

    while index < length:
        if state is None:
            line_marker = _match_any(text, index, line_prefixes)
            if line_marker is not None:
                for offset in range(len(line_marker)):
                    chars[index + offset] = " "
                state = ("line_comment", line_marker)
                index += len(line_marker)
                continue

            block_marker = _match_block_start(text, index, block_pairs)
            if block_marker is not None:
                start_marker, end_marker = block_marker
                for offset in range(len(start_marker)):
                    chars[index + offset] = " "
                state = ("block_comment", end_marker)
                index += len(start_marker)
                continue

            string_marker = _match_any(text, index, string_delimiters)
            if string_marker is not None:
                for offset in range(len(string_marker)):
                    chars[index + offset] = " "
                state = ("string", string_marker)
                index += len(string_marker)
                continue

            index += 1
            continue

        mode, marker = state
        if mode == "line_comment":
            if text[index] == "\n":
                state = None
                index += 1
            else:
                chars[index] = " "
                index += 1
            continue

        if mode == "block_comment":
            if text.startswith(marker, index):
                for offset in range(len(marker)):
                    chars[index + offset] = " "
                state = None
                index += len(marker)
            else:
                if text[index] != "\n":
                    chars[index] = " "
                index += 1
            continue

        if mode == "string":
            if text.startswith(marker, index) and not _is_escaped(
                text, index, marker, active_rules.escape_char
            ):
                for offset in range(len(marker)):
                    chars[index + offset] = " "
                state = None
                index += len(marker)
            else:
                if text[index] != "\n":
                    chars[index] = " "
                index += 1
            continue

    return "".join(chars)


def extract_identifier_tokens(masked_text: str) -> list[LexicalToken]:
    """Extract deterministic identifier tokens from already-masked source text."""
    tokens: list[LexicalToken] = []
    for line_number, raw_line in enumerate(masked_text.splitlines(), start=1):
        for match in _IDENTIFIER_PATTERN.finditer(raw_line):
            start = match.start() + 1
            end = match.end()
            tokens.append(
                LexicalToken(
                    text=match.group(0),
                    line=line_number,
                    start_col=start,
                    end_col=end,
                )
            )
    return tokens


def scan_brace_blocks(
    masked_text: str,
    open_char: str = "{",
    close_char: str = "}",
) -> BraceScanResult:
    """Scan brace block ranges with deterministic line and column accounting."""
    if len(open_char) != 1 or len(close_char) != 1:
        raise ValueError("open_char and close_char must be single characters.")

    stack: list[tuple[int, int, int]] = []
    blocks: list[BraceBlock] = []
    line = 1
    col = 1
    unmatched_closing = 0

    for char in masked_text:
        if char == open_char:
            depth = len(stack) + 1
            stack.append((line, col, depth))
        elif char == close_char:
            if not stack:
                unmatched_closing += 1
            else:
                start_line, start_col, depth = stack.pop()
                blocks.append(
                    BraceBlock(
                        start_line=start_line,
                        start_col=start_col,
                        end_line=line,
                        end_col=col,
                        depth=depth,
                    )
                )

        if char == "\n":
            line += 1
            col = 1
        else:
            col += 1

    ordered = tuple(
        sorted(
            blocks,
            key=lambda item: (
                item.start_line,
                item.start_col,
                item.end_line,
                item.end_col,
                item.depth,
            ),
        )
    )
    return BraceScanResult(
        blocks=ordered,
        unmatched_closing=unmatched_closing,
        unclosed_opening=len(stack),
    )


def _match_any(text: str, index: int, markers: tuple[str, ...]) -> str | None:
    for marker in markers:
        if text.startswith(marker, index):
            return marker
    return None


def _match_block_start(
    text: str,
    index: int,
    pairs: tuple[tuple[str, str], ...],
) -> tuple[str, str] | None:
    for start, end in pairs:
        if text.startswith(start, index):
            return start, end
    return None


def _is_escaped(text: str, index: int, marker: str, escape_char: str) -> bool:
    if len(marker) > 1:
        return False
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == escape_char:
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1
