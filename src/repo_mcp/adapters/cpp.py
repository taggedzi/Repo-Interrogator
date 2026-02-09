"""Lexical C++ adapter for deterministic symbol outlining."""

from __future__ import annotations

import re
from dataclasses import dataclass

from repo_mcp.adapters.base import OutlineSymbol, normalize_and_sort_symbols
from repo_mcp.adapters.lexical import mask_comments_and_strings, scan_brace_blocks

_NAMESPACE_RE = re.compile(r"^\s*namespace\s+([A-Za-z_][A-Za-z0-9_:]*)\s*\{?")
_CLASS_STRUCT_RE = re.compile(
    r"^\s*(?:template\s*<[^>]+>\s*)?(class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)\b"
)
_ENUM_RE = re.compile(r"^\s*(?:enum(?:\s+class)?)\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_FREE_FUNCTION_RE = re.compile(
    r"^\s*(?:(?:inline|constexpr|static|virtual|friend|extern)\s+)*"
    r"(?:[A-Za-z_~][A-Za-z0-9_:<>\s*&]+)?\s+"
    r"([A-Za-z_~][A-Za-z0-9_:]*)\s*\(([^;{}()]*)\)\s*"
    r"(?:const\s*)?(?:noexcept(?:\([^)]*\))?\s*)?(?:->\s*[^;{]+)?\s*([;{])"
)
_METHOD_RE = re.compile(
    r"^\s*(?:(?:public|protected|private)\s*:\s*)?"
    r"(?:(?:inline|constexpr|virtual|static|friend|explicit)\s+)*"
    r"(?:[A-Za-z_~][A-Za-z0-9_:<>\s*&]+)?\s+"
    r"([A-Za-z_~][A-Za-z0-9_]*)\s*\(([^;{}()]*)\)\s*"
    r"(?:const\s*)?(?:noexcept(?:\([^)]*\))?\s*)?(?:->\s*[^;{]+)?\s*([;{])"
)
_SKIP_NAMES = {"if", "for", "while", "switch", "catch", "return", "sizeof"}


@dataclass(slots=True, frozen=True)
class _TypeBlock:
    name: str
    start_line: int
    end_line: int
    depth: int


class CppLexicalAdapter:
    """Deterministic lexical adapter for C++ source/header files."""

    name = "cpp_lexical"
    _extensions = (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".h")

    def supports_path(self, path: str) -> bool:
        """Return True when path is a C/C++ source or header file."""
        lowered = path.lower()
        return lowered.endswith(self._extensions)

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Extract namespace/type/function/method symbols deterministically."""
        _ = path
        masked = mask_comments_and_strings(text)
        lines = masked.splitlines()
        depth_before = _line_depths(masked)
        block_ends = _block_end_by_start_line(masked)

        symbols: list[OutlineSymbol] = []
        type_blocks: list[_TypeBlock] = []

        for index, line in enumerate(lines):
            line_number = index + 1
            current_depth = depth_before[index]
            if current_depth > 1:
                continue

            namespace_match = _NAMESPACE_RE.match(line)
            if namespace_match is not None:
                name = namespace_match.group(1)
                symbols.append(
                    OutlineSymbol(
                        kind="namespace",
                        name=name,
                        signature=None,
                        start_line=line_number,
                        end_line=max(line_number, block_ends.get(line_number, line_number)),
                        doc=None,
                    )
                )
                continue

            type_match = _CLASS_STRUCT_RE.match(line)
            if type_match is not None:
                kind, name = type_match.groups()
                end_line = max(line_number, block_ends.get(line_number, line_number))
                symbols.append(
                    OutlineSymbol(
                        kind=kind,
                        name=name,
                        signature="()",
                        start_line=line_number,
                        end_line=end_line,
                        doc=None,
                    )
                )
                type_blocks.append(
                    _TypeBlock(
                        name=name,
                        start_line=line_number,
                        end_line=end_line,
                        depth=current_depth + 1,
                    )
                )
                continue

            enum_match = _ENUM_RE.match(line)
            if enum_match is not None:
                symbols.append(
                    OutlineSymbol(
                        kind="enum",
                        name=enum_match.group(1),
                        signature=None,
                        start_line=line_number,
                        end_line=max(line_number, block_ends.get(line_number, line_number)),
                        doc=None,
                    )
                )
                continue

            function_match = _FREE_FUNCTION_RE.match(line)
            if function_match is not None:
                name, params, terminator = function_match.groups()
                if name in _SKIP_NAMES:
                    continue
                end_line = (
                    max(line_number, block_ends.get(line_number, line_number))
                    if terminator == "{"
                    else line_number
                )
                symbols.append(
                    OutlineSymbol(
                        kind="function",
                        name=name,
                        signature=f"({params.strip()})",
                        start_line=line_number,
                        end_line=end_line,
                        doc=None,
                    )
                )

        for type_block in type_blocks:
            symbols.extend(
                _extract_type_methods(
                    lines=lines,
                    depth_before=depth_before,
                    block_ends=block_ends,
                    type_block=type_block,
                )
            )

        return normalize_and_sort_symbols(symbols)

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """C++ adapter does not provide smart chunk ranges in v1."""
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """C++ adapter does not derive symbol hints in v1."""
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


def _extract_type_methods(
    lines: list[str],
    depth_before: list[int],
    block_ends: dict[int, int],
    type_block: _TypeBlock,
) -> list[OutlineSymbol]:
    symbols: list[OutlineSymbol] = []
    start = max(type_block.start_line + 1, 1)
    end = min(type_block.end_line, len(lines))
    for line_number in range(start, end + 1):
        if depth_before[line_number - 1] != type_block.depth:
            continue
        line = lines[line_number - 1]
        matched = _METHOD_RE.match(line)
        if matched is None:
            continue
        name, params, terminator = matched.groups()
        if name in _SKIP_NAMES:
            continue
        symbol_end = (
            max(line_number, block_ends.get(line_number, line_number))
            if terminator == "{"
            else line_number
        )
        symbols.append(
            OutlineSymbol(
                kind="method",
                name=f"{type_block.name}.{name}",
                signature=f"({params.strip()})",
                start_line=line_number,
                end_line=symbol_end,
                doc=None,
            )
        )
    return symbols
