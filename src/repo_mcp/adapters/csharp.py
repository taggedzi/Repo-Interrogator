"""Lexical C# adapter for deterministic symbol outlining."""

from __future__ import annotations

import re
from dataclasses import dataclass

from repo_mcp.adapters.base import OutlineSymbol, normalize_and_sort_symbols
from repo_mcp.adapters.lexical import mask_comments_and_strings, scan_brace_blocks

_NAMESPACE_RE = re.compile(r"^\s*namespace\s+([A-Za-z_][A-Za-z0-9_.]*)\b")
_TYPE_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|abstract|sealed|static|partial)\s+)*"
    r"(class|struct|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)\b"
)
_METHOD_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract|async|sealed|new)\s+)*"
    r"(?:[A-Za-z_][A-Za-z0-9_<>\[\],?.\s]*\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*((?:=>|[;{]))?"
)
_PROPERTY_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract)\s+)*"
    r"[A-Za-z_][A-Za-z0-9_<>\[\],?.\s]*\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\{\s*(?:get|set|init)\b"
)
_EVENT_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static)\s+)*event\s+"
    r"[A-Za-z_][A-Za-z0-9_<>\[\],?.\s]*\s+([A-Za-z_][A-Za-z0-9_]*)\s*;"
)
_METHOD_SKIP = {"if", "for", "while", "switch", "catch", "return", "new"}


@dataclass(slots=True, frozen=True)
class _TypeBlock:
    name: str
    start_line: int
    end_line: int
    member_depth: int


class CSharpLexicalAdapter:
    """Deterministic lexical adapter for C# source files."""

    name = "csharp_lexical"

    def supports_path(self, path: str) -> bool:
        """Return True when path is a C# source file."""
        return path.lower().endswith(".cs")

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Extract namespace, type, method, property, and event symbols."""
        _ = path
        masked = mask_comments_and_strings(text)
        lines = masked.splitlines()
        depth_before = _line_depths(masked)
        block_ends = _block_end_by_start_line(masked)

        symbols: list[OutlineSymbol] = []
        type_blocks: list[_TypeBlock] = []
        current_namespace_depth: int | None = None
        current_namespace: str | None = None

        for index, line in enumerate(lines):
            line_number = index + 1
            if depth_before[index] != 0:
                continue

            namespace_match = _NAMESPACE_RE.match(line)
            if namespace_match is not None:
                current_namespace = namespace_match.group(1)
                current_namespace_depth = depth_before[index] + (1 if "{" in line else 0)
                symbols.append(
                    OutlineSymbol(
                        kind="namespace",
                        name=current_namespace,
                        signature=None,
                        start_line=line_number,
                        end_line=_declaration_end(line_number, line, block_ends),
                        doc=None,
                    )
                )
                continue

            type_match = _TYPE_RE.match(line)
            if type_match is not None:
                kind, type_name = type_match.groups()
                qualified = _qualify(current_namespace, type_name)
                type_end = _declaration_end(line_number, line, block_ends)
                namespace_depth = current_namespace_depth or 0
                symbols.append(
                    OutlineSymbol(
                        kind=kind,
                        name=qualified,
                        signature="()",
                        start_line=line_number,
                        end_line=type_end,
                        doc=None,
                    )
                )
                type_blocks.append(
                    _TypeBlock(
                        name=qualified,
                        start_line=line_number,
                        end_line=type_end,
                        member_depth=namespace_depth + 1,
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
        """C# adapter does not provide smart chunk ranges in v1."""
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """C# adapter does not derive symbol hints in v1."""
        _ = prompt
        return ()


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
    type_block: _TypeBlock,
) -> list[OutlineSymbol]:
    symbols: list[OutlineSymbol] = []
    start = max(type_block.start_line + 1, 1)
    end = min(type_block.end_line, len(lines))
    simple_type_name = type_block.name.split(".")[-1]
    for line_number in range(start, end + 1):
        if depth_before[line_number - 1] != type_block.member_depth:
            continue
        line = lines[line_number - 1]

        event_match = _EVENT_RE.match(line)
        if event_match is not None:
            event_name = event_match.group(1)
            symbols.append(
                OutlineSymbol(
                    kind="event",
                    name=f"{type_block.name}.{event_name}",
                    signature=None,
                    start_line=line_number,
                    end_line=line_number,
                    doc=None,
                )
            )
            continue

        property_match = _PROPERTY_RE.match(line)
        if property_match is not None:
            property_name = property_match.group(1)
            symbols.append(
                OutlineSymbol(
                    kind="property",
                    name=f"{type_block.name}.{property_name}",
                    signature=None,
                    start_line=line_number,
                    end_line=max(line_number, block_ends.get(line_number, line_number)),
                    doc=None,
                )
            )
            continue

        method_match = _METHOD_RE.match(line)
        if method_match is None:
            continue
        member_name, params, terminator = method_match.groups()
        if member_name in _METHOD_SKIP:
            continue
        kind = "constructor" if member_name == simple_type_name else "method"
        if terminator in (";", "=>"):
            end_line = line_number
        else:
            end_line = _declaration_end(line_number, line, block_ends, lookahead=2)
        symbols.append(
            OutlineSymbol(
                kind=kind,
                name=f"{type_block.name}.{member_name}",
                signature=f"({params.strip()})",
                start_line=line_number,
                end_line=end_line,
                doc=None,
            )
        )
    return symbols


def _qualify(namespace: str | None, type_name: str) -> str:
    if namespace is None:
        return type_name
    return f"{namespace}.{type_name}"


def _declaration_end(
    line_number: int,
    line_text: str,
    block_ends: dict[int, int],
    lookahead: int = 3,
) -> int:
    if line_text.strip().endswith(";"):
        return line_number
    direct = block_ends.get(line_number)
    if direct is not None:
        return max(line_number, direct)
    for candidate in range(line_number + 1, line_number + lookahead + 1):
        end_line = block_ends.get(candidate)
        if end_line is not None:
            return max(line_number, end_line)
    return line_number
