"""Deterministic lexical scanning helpers for non-AST adapters."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from repo_mcp.adapters.base import SymbolReference, normalize_and_sort_references

_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_SYMBOL_BOUNDARY_TEMPLATE = r"(?<![A-Za-z0-9_$]){token}(?![A-Za-z0-9_$])"
_IMPORT_HINT_RE = re.compile(r"\b(import|from|using|use|require|include)\b")
_INHERITANCE_HINT_RE = re.compile(r"\b(extends|implements|inherits|:\s*public|:\s*private)\b")
_DECLARATION_HINT_RE = re.compile(
    r"\b(class|struct|interface|enum|record|trait|type|namespace|package|module|impl|func|fn|def)\b"
)


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


def references_for_symbol_lexical(
    symbol: str,
    files: list[tuple[str, str]],
    *,
    supports_path: Callable[[str], bool],
    top_k: int | None = None,
) -> list[SymbolReference]:
    """Extract deterministic lexical references for one symbol over supported files."""
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        return []

    symbol_parts = [part for part in re.split(r"[.:]+", normalized_symbol) if part]
    if not symbol_parts:
        return []
    short_symbol = symbol_parts[-1]
    short_pattern = re.compile(_SYMBOL_BOUNDARY_TEMPLATE.format(token=re.escape(short_symbol)))
    sequence_pattern = _build_symbol_sequence_pattern(symbol_parts)
    references: list[SymbolReference] = []

    for path, text in files:
        if not supports_path(path):
            continue
        masked = mask_comments_and_strings(text)
        original_lines = text.splitlines()
        masked_lines = masked.splitlines()
        for line_no, (masked_line, original_line) in enumerate(
            zip(masked_lines, original_lines, strict=True),
            start=1,
        ):
            if not _line_mentions_symbol(
                masked_line=masked_line,
                short_pattern=short_pattern,
                sequence_pattern=sequence_pattern,
                short_symbol=short_symbol,
            ):
                continue
            if _is_probable_symbol_declaration(masked_line, short_symbol):
                continue
            kind, confidence = _classify_reference(masked_line, short_symbol)
            evidence = _evidence_from_line(original_line)
            if not evidence:
                continue
            references.append(
                SymbolReference(
                    symbol=normalized_symbol,
                    path=path,
                    line=line_no,
                    kind=kind,
                    evidence=evidence,
                    strategy="lexical",
                    confidence=confidence,
                )
            )

    sorted_references = normalize_and_sort_references(references)
    if top_k is None or top_k < 1:
        return sorted_references
    return sorted_references[:top_k]


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


def _build_symbol_sequence_pattern(parts: list[str]) -> re.Pattern[str] | None:
    if len(parts) < 2:
        return None
    sep = r"\s*(?:\.|::)\s*"
    sequence = sep.join(re.escape(part) for part in parts)
    return re.compile(_SYMBOL_BOUNDARY_TEMPLATE.format(token=sequence))


def _line_mentions_symbol(
    *,
    masked_line: str,
    short_pattern: re.Pattern[str],
    sequence_pattern: re.Pattern[str] | None,
    short_symbol: str,
) -> bool:
    if sequence_pattern is not None and sequence_pattern.search(masked_line):
        return True
    if not short_pattern.search(masked_line):
        return False
    short_call = re.search(rf"{re.escape(short_symbol)}\s*\(", masked_line) is not None
    short_new = re.search(rf"\bnew\s+{re.escape(short_symbol)}\b", masked_line) is not None
    short_import = _IMPORT_HINT_RE.search(masked_line) is not None
    short_inheritance = _INHERITANCE_HINT_RE.search(masked_line) is not None
    return short_call or short_new or short_import or short_inheritance


def _is_probable_symbol_declaration(masked_line: str, short_symbol: str) -> bool:
    if _DECLARATION_HINT_RE.search(masked_line) is None:
        return False
    pattern = _SYMBOL_BOUNDARY_TEMPLATE.format(token=re.escape(short_symbol))
    return re.search(pattern, masked_line) is not None


def _classify_reference(masked_line: str, short_symbol: str) -> tuple[str, str]:
    if _IMPORT_HINT_RE.search(masked_line) is not None:
        return ("import", "high")
    if _INHERITANCE_HINT_RE.search(masked_line) is not None:
        return ("inheritance", "high")
    if re.search(rf"\bnew\s+{re.escape(short_symbol)}\b", masked_line) is not None:
        return ("instantiation", "high")
    if re.search(rf"{re.escape(short_symbol)}\s*\(", masked_line) is not None:
        return ("call", "medium")
    return ("read", "low")


def _evidence_from_line(line: str) -> str:
    compact = " ".join(line.strip().split())
    if not compact:
        return ""
    return compact[:160]
