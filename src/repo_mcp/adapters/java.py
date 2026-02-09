"""Lexical Java adapter for deterministic symbol outlining."""

from __future__ import annotations

import re
from dataclasses import dataclass

from repo_mcp.adapters.base import OutlineSymbol, normalize_and_sort_symbols
from repo_mcp.adapters.lexical import mask_comments_and_strings, scan_brace_blocks

_PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*;")
_TYPE_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|abstract|final|static|sealed|non-sealed|strictfp)\s+)*"
    r"(class|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)\b"
)
_METHOD_RE = re.compile(
    r"^\s*(?:@[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*)*"
    r"(?:(?:public|protected|private|abstract|final|static|synchronized|native|strictfp|default)\s+)*"
    r"(?:(?:<[^>]+>\s*)?([A-Za-z_][A-Za-z0-9_<>\[\], ?.]*?)\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*"
    r"(?:throws\s+[A-Za-z0-9_.,\s]+)?\s*([;{])"
)
_METHOD_SKIP = {"if", "for", "while", "switch", "catch", "return", "new"}


@dataclass(slots=True, frozen=True)
class _JavaTypeBlock:
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    depth: int


class JavaLexicalAdapter:
    """Deterministic lexical adapter for Java source files."""

    name = "java_lexical"

    def supports_path(self, path: str) -> bool:
        """Return True when path is a Java source file."""
        return path.lower().endswith(".java")

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Extract package-aware top-level types and class members."""
        _ = path
        masked = mask_comments_and_strings(text)
        lines = masked.splitlines()
        depth_before = _line_depths(masked)
        block_ends = _block_end_by_start_line(masked)
        package_name = _find_package(lines)

        symbols: list[OutlineSymbol] = []
        type_blocks: list[_JavaTypeBlock] = []

        for index, line in enumerate(lines):
            line_number = index + 1
            if depth_before[index] != 0:
                continue
            type_match = _TYPE_RE.match(line)
            if type_match is None:
                continue

            kind, type_name = type_match.group(1), type_match.group(2)
            qualified_name = (
                f"{package_name}.{type_name}" if package_name is not None else type_name
            )
            end_line = block_ends.get(line_number, line_number)
            symbol_kind = "type" if kind == "record" else kind
            symbols.append(
                OutlineSymbol(
                    kind=symbol_kind,
                    name=qualified_name,
                    signature="()",
                    start_line=line_number,
                    end_line=end_line,
                    doc=None,
                )
            )
            type_blocks.append(
                _JavaTypeBlock(
                    name=type_name,
                    qualified_name=qualified_name,
                    start_line=line_number,
                    end_line=end_line,
                    depth=1,
                )
            )

        for type_block in type_blocks:
            symbols.extend(
                _extract_type_members(
                    lines=lines,
                    depth_before=depth_before,
                    block_ends=block_ends,
                    type_block=type_block,
                )
            )

        return normalize_and_sort_symbols(symbols)

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """Java adapter does not provide smart chunk ranges in v1."""
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """Java adapter does not derive symbol hints in v1."""
        _ = prompt
        return ()


def _find_package(lines: list[str]) -> str | None:
    for line in lines:
        matched = _PACKAGE_RE.match(line)
        if matched is not None:
            return matched.group(1)
    return None


def _line_depths(masked_text: str) -> list[int]:
    depths: list[int] = []
    depth = 0
    for line in masked_text.splitlines():
        depths.append(depth)
        for char in line:
            if char == "{":
                depth += 1
            elif char == "}":
                depth = max(0, depth - 1)
    return depths


def _block_end_by_start_line(masked_text: str) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for block in scan_brace_blocks(masked_text).blocks:
        existing = mapping.get(block.start_line)
        if existing is None or block.end_line > existing:
            mapping[block.start_line] = block.end_line
    return mapping


def _extract_type_members(
    lines: list[str],
    depth_before: list[int],
    block_ends: dict[int, int],
    type_block: _JavaTypeBlock,
) -> list[OutlineSymbol]:
    symbols: list[OutlineSymbol] = []
    start = max(1, type_block.start_line + 1)
    end = min(type_block.end_line, len(lines))
    for line_number in range(start, end + 1):
        line = lines[line_number - 1]
        if depth_before[line_number - 1] != type_block.depth:
            continue
        matched = _METHOD_RE.match(line)
        if matched is None:
            continue

        return_type, member_name, params, terminator = (
            matched.group(1),
            matched.group(2),
            matched.group(3).strip(),
            matched.group(4),
        )
        if member_name in _METHOD_SKIP:
            continue

        if member_name == type_block.name:
            kind = "constructor"
        elif return_type is None:
            continue
        else:
            kind = "method"

        symbol_end = line_number if terminator == ";" else block_ends.get(line_number, line_number)
        symbols.append(
            OutlineSymbol(
                kind=kind,
                name=f"{type_block.qualified_name}.{member_name}",
                signature=f"({params})",
                start_line=line_number,
                end_line=max(line_number, symbol_end),
                doc=None,
            )
        )
    return symbols
