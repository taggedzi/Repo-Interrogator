"""Lexical Go adapter for deterministic symbol outlining."""

from __future__ import annotations

import re

from repo_mcp.adapters.base import OutlineSymbol, SymbolReference, normalize_and_sort_symbols
from repo_mcp.adapters.lexical import (
    mask_comments_and_strings,
    references_for_symbol_lexical,
    scan_brace_blocks,
)

_PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_TYPE_RE = re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_FUNC_RE = re.compile(r"^\s*func\s*(?:\(([^)]*)\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)")
_CONST_VAR_SINGLE_RE = re.compile(r"^\s*(const|var)\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_CONST_VAR_GROUP_START_RE = re.compile(r"^\s*(const|var)\s*\(")
_GROUP_ENTRY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\b")


class GoLexicalAdapter:
    """Deterministic lexical adapter for Go source files."""

    name = "go_lexical"

    def supports_path(self, path: str) -> bool:
        """Return True when path is a Go source file."""
        return path.lower().endswith(".go")

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Extract package-level types, funcs, methods, consts, and vars."""
        _ = path
        masked = mask_comments_and_strings(text)
        lines = masked.splitlines()
        depth_before = _line_depths(masked)
        block_ends = _block_end_by_start_line(masked)
        package_name = _find_package(lines)

        symbols: list[OutlineSymbol] = []
        index = 0
        while index < len(lines):
            line_number = index + 1
            line = lines[index]
            if depth_before[index] != 0:
                index += 1
                continue

            type_match = _TYPE_RE.match(line)
            if type_match is not None:
                type_name = type_match.group(1)
                symbols.append(
                    OutlineSymbol(
                        kind="type",
                        name=_qualify(package_name, type_name),
                        signature=None,
                        start_line=line_number,
                        end_line=max(line_number, block_ends.get(line_number, line_number)),
                        doc=None,
                    )
                )
                index += 1
                continue

            func_match = _FUNC_RE.match(line)
            if func_match is not None:
                receiver, name, params = func_match.groups()
                end_line = max(line_number, block_ends.get(line_number, line_number))
                signature = f"({params.strip()})"
                if receiver is None:
                    kind = "function"
                    symbol_name = _qualify(package_name, name)
                else:
                    kind = "method"
                    receiver_type = _parse_receiver_type(receiver)
                    method_base = f"{receiver_type}.{name}" if receiver_type else name
                    symbol_name = _qualify(package_name, method_base)
                symbols.append(
                    OutlineSymbol(
                        kind=kind,
                        name=symbol_name,
                        signature=signature,
                        start_line=line_number,
                        end_line=end_line,
                        doc=None,
                    )
                )
                index += 1
                continue

            single_match = _CONST_VAR_SINGLE_RE.match(line)
            if single_match is not None:
                decl_kind, name = single_match.groups()
                symbols.append(
                    OutlineSymbol(
                        kind=decl_kind,
                        name=_qualify(package_name, name),
                        signature=None,
                        start_line=line_number,
                        end_line=line_number,
                        doc=None,
                    )
                )
                index += 1
                continue

            group_start = _CONST_VAR_GROUP_START_RE.match(line)
            if group_start is not None:
                decl_kind = group_start.group(1)
                group_end = _find_group_end(lines, start_index=index)
                for group_line_idx in range(index + 1, group_end):
                    if depth_before[group_line_idx] != 0:
                        continue
                    entry = _GROUP_ENTRY_RE.match(lines[group_line_idx])
                    if entry is None:
                        continue
                    name = entry.group(1)
                    symbols.append(
                        OutlineSymbol(
                            kind=decl_kind,
                            name=_qualify(package_name, name),
                            signature=None,
                            start_line=group_line_idx + 1,
                            end_line=group_line_idx + 1,
                            doc=None,
                        )
                    )
                index = group_end + 1
                continue

            index += 1

        return normalize_and_sort_symbols(symbols)

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """Go adapter does not provide smart chunk ranges in v1."""
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """Go adapter does not derive symbol hints in v1."""
        _ = prompt
        return ()

    def references_for_symbol(
        self,
        symbol: str,
        files: list[tuple[str, str]],
        *,
        top_k: int | None = None,
    ) -> list[SymbolReference]:
        """Return deterministic lexical references for one symbol in Go files."""
        return references_for_symbol_lexical(
            symbol=symbol,
            files=files,
            supports_path=self.supports_path,
            top_k=top_k,
        )


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


def _parse_receiver_type(receiver: str) -> str | None:
    stripped = receiver.strip()
    if not stripped:
        return None
    parts = stripped.split()
    type_part = parts[-1] if parts else stripped
    type_part = type_part.lstrip("*")
    return type_part if type_part else None


def _find_group_end(lines: list[str], start_index: int) -> int:
    depth = 0
    for idx in range(start_index, len(lines)):
        for char in lines[idx]:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return idx
    return len(lines) - 1


def _qualify(package_name: str | None, name: str) -> str:
    if package_name is None:
        return name
    return f"{package_name}.{name}"
