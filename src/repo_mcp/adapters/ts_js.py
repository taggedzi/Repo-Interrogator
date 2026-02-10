"""Lexical TypeScript/JavaScript adapter with deterministic outline extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from repo_mcp.adapters.base import OutlineSymbol, SymbolReference, normalize_and_sort_symbols
from repo_mcp.adapters.lexical import (
    mask_comments_and_strings,
    references_for_symbol_lexical,
)

_CLASS_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)\b")
_INTERFACE_RE = re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][A-Za-z0-9_$]*)\b")
_ENUM_RE = re.compile(r"^\s*(?:export\s+)?enum\s+([A-Za-z_$][A-Za-z0-9_$]*)\b")
_TYPE_ALIAS_RE = re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][A-Za-z0-9_$]*)\b")
_FUNCTION_RE = re.compile(
    r"^\s*(?:export\s+)?(?:(async)\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(([^)]*)\)"
)
_EXPORT_BINDING_RE = re.compile(r"^\s*export\s+(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\b")
_COMMONJS_EXPORT_RE = re.compile(r"^\s*(?:module\.)?exports\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=")
_METHOD_RE = re.compile(
    r"^\s*(?:public|private|protected|static|readonly|override|abstract|get|set|async|\s)*"
    r"([A-Za-z_$][A-Za-z0-9_$]*)\s*\(([^)]*)\)\s*\{?"
)
_SKIP_METHOD_NAMES = {"if", "for", "while", "switch", "catch", "function"}
_BLOCK_SYMBOL_KINDS = {"class", "interface", "enum", "function", "async_function"}


@dataclass(slots=True, frozen=True)
class _Block:
    start_line: int
    end_line: int
    depth: int


class TypeScriptJavaScriptLexicalAdapter:
    """Deterministic lexical adapter for TypeScript and JavaScript source files."""

    name = "ts_js_lexical"
    _extensions = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")

    def supports_path(self, path: str) -> bool:
        """Return True when path is a TypeScript or JavaScript source file."""
        lowered = path.lower()
        return lowered.endswith(self._extensions)

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Extract deterministic top-level and class-method symbols."""
        _ = path
        masked = mask_comments_and_strings(text)
        lines = masked.splitlines()
        depth_before = _line_depths(masked)
        blocks = _line_blocks(masked)

        symbols: list[OutlineSymbol] = []
        class_blocks: list[tuple[str, _Block]] = []

        for index, line in enumerate(lines):
            line_number = index + 1
            if depth_before[index] != 0:
                continue

            class_match = _CLASS_RE.match(line)
            if class_match is not None:
                name = class_match.group(1)
                symbol = OutlineSymbol(
                    kind="class",
                    name=name,
                    signature="()",
                    start_line=line_number,
                    end_line=_find_block_end(line_number, blocks),
                    doc=None,
                )
                symbols.append(symbol)
                class_blocks.append(
                    (
                        name,
                        _Block(
                            start_line=symbol.start_line,
                            end_line=symbol.end_line,
                            depth=1,
                        ),
                    )
                )
                continue

            interface_match = _INTERFACE_RE.match(line)
            if interface_match is not None:
                name = interface_match.group(1)
                symbols.append(
                    OutlineSymbol(
                        kind="interface",
                        name=name,
                        signature="()",
                        start_line=line_number,
                        end_line=_find_block_end(line_number, blocks),
                        doc=None,
                    )
                )
                continue

            enum_match = _ENUM_RE.match(line)
            if enum_match is not None:
                name = enum_match.group(1)
                symbols.append(
                    OutlineSymbol(
                        kind="enum",
                        name=name,
                        signature="()",
                        start_line=line_number,
                        end_line=_find_block_end(line_number, blocks),
                        doc=None,
                    )
                )
                continue

            type_alias_match = _TYPE_ALIAS_RE.match(line)
            if type_alias_match is not None:
                symbols.append(
                    OutlineSymbol(
                        kind="type_alias",
                        name=type_alias_match.group(1),
                        signature=None,
                        start_line=line_number,
                        end_line=line_number,
                        doc=None,
                    )
                )
                continue

            function_match = _FUNCTION_RE.match(line)
            if function_match is not None:
                is_async = function_match.group(1) is not None
                signature = f"({function_match.group(3).strip()})"
                kind = "async_function" if is_async else "function"
                end_line = _find_block_end(line_number, blocks)
                symbols.append(
                    OutlineSymbol(
                        kind=kind,
                        name=function_match.group(2),
                        signature=signature,
                        start_line=line_number,
                        end_line=end_line,
                        doc=None,
                    )
                )
                continue

            export_match = _EXPORT_BINDING_RE.match(line)
            if export_match is not None:
                symbols.append(
                    OutlineSymbol(
                        kind="exported_variable",
                        name=export_match.group(1),
                        signature=None,
                        start_line=line_number,
                        end_line=line_number,
                        doc=None,
                    )
                )
                continue

            commonjs_match = _COMMONJS_EXPORT_RE.match(line)
            if commonjs_match is not None:
                symbols.append(
                    OutlineSymbol(
                        kind="exported_variable",
                        name=commonjs_match.group(1),
                        signature=None,
                        start_line=line_number,
                        end_line=line_number,
                        doc=None,
                    )
                )

        for class_name, class_block in class_blocks:
            symbols.extend(
                _extract_class_methods(
                    class_name=class_name,
                    lines=lines,
                    depth_before=depth_before,
                    class_block=class_block,
                    blocks=blocks,
                )
            )

        filtered = [symbol for symbol in symbols if symbol.kind or symbol.name]
        return normalize_and_sort_symbols(filtered)

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """TS/JS adapter does not provide smart chunk ranges in v1."""
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """TS/JS adapter does not derive prompt symbol hints in v1."""
        _ = prompt
        return ()

    def references_for_symbol(
        self,
        symbol: str,
        files: list[tuple[str, str]],
        *,
        top_k: int | None = None,
    ) -> list[SymbolReference]:
        """Return deterministic lexical references for one symbol in TS/JS files."""
        return references_for_symbol_lexical(
            symbol=symbol,
            files=files,
            supports_path=self.supports_path,
            top_k=top_k,
        )


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


def _line_blocks(masked_text: str) -> list[_Block]:
    stack: list[tuple[int, int]] = []
    blocks: list[_Block] = []
    line = 1
    col = 1
    for char in masked_text:
        if char == "{":
            stack.append((line, col))
        elif char == "}":
            if stack:
                start_line, _ = stack.pop()
                depth = len(stack) + 1
                blocks.append(_Block(start_line=start_line, end_line=line, depth=depth))
        if char == "\n":
            line += 1
            col = 1
        else:
            col += 1
    blocks.sort(key=lambda item: (item.start_line, item.end_line, item.depth))
    return blocks


def _find_block_end(start_line: int, blocks: list[_Block]) -> int:
    for block in blocks:
        if block.start_line >= start_line:
            return block.end_line
    return start_line


def _extract_class_methods(
    class_name: str,
    lines: list[str],
    depth_before: list[int],
    class_block: _Block,
    blocks: list[_Block],
) -> list[OutlineSymbol]:
    symbols: list[OutlineSymbol] = []
    start_index = max(class_block.start_line, 1)
    end_index = min(class_block.end_line, len(lines))
    for line_number in range(start_index + 1, end_index + 1):
        line = lines[line_number - 1]
        if depth_before[line_number - 1] != class_block.depth:
            continue
        match = _METHOD_RE.match(line)
        if match is None:
            continue
        method_name = match.group(1)
        if method_name in _SKIP_METHOD_NAMES:
            continue
        signature = f"({match.group(2).strip()})"
        kind = "async_method" if "async " in line else "method"
        end_line = _find_block_end(
            line_number,
            [block for block in blocks if block.depth >= class_block.depth + 1],
        )
        if kind not in _BLOCK_SYMBOL_KINDS:
            symbols.append(
                OutlineSymbol(
                    kind=kind,
                    name=f"{class_name}.{method_name}",
                    signature=signature,
                    start_line=line_number,
                    end_line=max(line_number, end_line),
                    doc=None,
                )
            )
    return symbols
