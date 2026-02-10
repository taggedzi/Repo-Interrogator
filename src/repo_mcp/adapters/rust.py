"""Lexical Rust adapter for deterministic symbol outlining."""

from __future__ import annotations

import re

from repo_mcp.adapters.base import OutlineSymbol, SymbolReference, normalize_and_sort_symbols
from repo_mcp.adapters.lexical import (
    mask_comments_and_strings,
    references_for_symbol_lexical,
    scan_brace_blocks,
)

_MOD_RE = re.compile(r"^\s*(?:pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_STRUCT_RE = re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_ENUM_RE = re.compile(r"^\s*(?:pub\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_TRAIT_RE = re.compile(r"^\s*(?:pub\s+)?trait\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_CONST_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_TYPE_ALIAS_RE = re.compile(r"^\s*(?:pub\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_FN_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)"
)
_IMPL_RE = re.compile(r"^\s*impl(?:<[^>]+>)?\s+(.+?)\s*\{")
_IMPL_FN_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)"
)


class RustLexicalAdapter:
    """Deterministic lexical adapter for Rust source files."""

    name = "rust_lexical"

    def supports_path(self, path: str) -> bool:
        """Return True when path is a Rust source file."""
        return path.lower().endswith(".rs")

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Extract top-level Rust items and impl methods deterministically."""
        _ = path
        masked = mask_comments_and_strings(text)
        lines = masked.splitlines()
        depth_before = _line_depths(masked)
        block_ends = _block_end_by_start_line(masked)

        symbols: list[OutlineSymbol] = []
        impl_blocks: list[tuple[int, int, str | None]] = []

        for index, line in enumerate(lines):
            line_number = index + 1
            if depth_before[index] != 0:
                continue

            mod_match = _MOD_RE.match(line)
            if mod_match is not None:
                symbols.append(
                    OutlineSymbol(
                        kind="mod",
                        name=mod_match.group(1),
                        signature=None,
                        start_line=line_number,
                        end_line=max(line_number, block_ends.get(line_number, line_number)),
                        doc=None,
                    )
                )
                continue

            struct_match = _STRUCT_RE.match(line)
            if struct_match is not None:
                symbols.append(
                    OutlineSymbol(
                        kind="struct",
                        name=struct_match.group(1),
                        signature=None,
                        start_line=line_number,
                        end_line=max(line_number, block_ends.get(line_number, line_number)),
                        doc=None,
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

            trait_match = _TRAIT_RE.match(line)
            if trait_match is not None:
                symbols.append(
                    OutlineSymbol(
                        kind="trait",
                        name=trait_match.group(1),
                        signature=None,
                        start_line=line_number,
                        end_line=max(line_number, block_ends.get(line_number, line_number)),
                        doc=None,
                    )
                )
                continue

            impl_match = _IMPL_RE.match(line)
            if impl_match is not None:
                impl_target = _parse_impl_target(impl_match.group(1))
                impl_end = max(line_number, block_ends.get(line_number, line_number))
                symbols.append(
                    OutlineSymbol(
                        kind="impl",
                        name=impl_target or "impl",
                        signature=None,
                        start_line=line_number,
                        end_line=impl_end,
                        doc=None,
                    )
                )
                impl_blocks.append((line_number, impl_end, impl_target))
                continue

            fn_match = _FN_RE.match(line)
            if fn_match is not None:
                fn_name, params = fn_match.groups()
                symbols.append(
                    OutlineSymbol(
                        kind="function",
                        name=fn_name,
                        signature=f"({params.strip()})",
                        start_line=line_number,
                        end_line=max(line_number, block_ends.get(line_number, line_number)),
                        doc=None,
                    )
                )
                continue

            const_match = _CONST_RE.match(line)
            if const_match is not None:
                symbols.append(
                    OutlineSymbol(
                        kind="const",
                        name=const_match.group(1),
                        signature=None,
                        start_line=line_number,
                        end_line=line_number,
                        doc=None,
                    )
                )
                continue

            type_match = _TYPE_ALIAS_RE.match(line)
            if type_match is not None:
                symbols.append(
                    OutlineSymbol(
                        kind="type",
                        name=type_match.group(1),
                        signature=None,
                        start_line=line_number,
                        end_line=line_number,
                        doc=None,
                    )
                )

        for impl_start, impl_end, impl_target in impl_blocks:
            symbols.extend(
                _extract_impl_methods(
                    lines=lines,
                    depth_before=depth_before,
                    block_ends=block_ends,
                    impl_start=impl_start,
                    impl_end=impl_end,
                    impl_target=impl_target,
                )
            )

        return normalize_and_sort_symbols(symbols)

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """Rust adapter does not provide smart chunk ranges in v1."""
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """Rust adapter does not derive symbol hints in v1."""
        _ = prompt
        return ()

    def references_for_symbol(
        self,
        symbol: str,
        files: list[tuple[str, str]],
        *,
        top_k: int | None = None,
    ) -> list[SymbolReference]:
        """Return deterministic lexical references for one symbol in Rust files."""
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


def _block_end_by_start_line(masked_text: str) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for block in scan_brace_blocks(masked_text).blocks:
        existing = mapping.get(block.start_line)
        if existing is None or block.end_line > existing:
            mapping[block.start_line] = block.end_line
    return mapping


def _parse_impl_target(impl_head: str) -> str | None:
    part = impl_head.split(" where ")[0].strip()
    if " for " in part:
        part = part.split(" for ", 1)[1].strip()
    cleaned = re.sub(r"<[^>]*>", "", part).strip()
    cleaned = cleaned.lstrip("&").lstrip("mut").strip()
    if not cleaned:
        return None
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", cleaned)
    if match is None:
        return None
    return match.group(1)


def _extract_impl_methods(
    lines: list[str],
    depth_before: list[int],
    block_ends: dict[int, int],
    impl_start: int,
    impl_end: int,
    impl_target: str | None,
) -> list[OutlineSymbol]:
    symbols: list[OutlineSymbol] = []
    start = max(impl_start + 1, 1)
    end = min(impl_end, len(lines))
    for line_number in range(start, end + 1):
        if depth_before[line_number - 1] != 1:
            continue
        line = lines[line_number - 1]
        matched = _IMPL_FN_RE.match(line)
        if matched is None:
            continue
        method_name, params = matched.groups()
        prefix = f"{impl_target}." if impl_target else "impl."
        symbols.append(
            OutlineSymbol(
                kind="method",
                name=f"{prefix}{method_name}",
                signature=f"({params.strip()})",
                start_line=line_number,
                end_line=max(line_number, block_ends.get(line_number, line_number)),
                doc=None,
            )
        )
    return symbols
