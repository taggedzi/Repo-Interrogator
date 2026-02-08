"""Python AST adapter for deterministic symbol outlining."""

from __future__ import annotations

import ast

from repo_mcp.adapters.base import OutlineSymbol


class PythonAstAdapter:
    """Python-first adapter with AST-based structural outlines."""

    name = "python"

    def supports_path(self, path: str) -> bool:
        """Return True when path is a Python source file."""
        return path.lower().endswith(".py")

    def outline(self, path: str, text: str) -> list[OutlineSymbol]:
        """Extract classes, methods, and functions with line ranges/signatures."""
        _ = path
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []

        symbols: list[OutlineSymbol] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.append(self._class_symbol(node))
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append(self._method_symbol(child, class_name=node.name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._function_symbol(node))

        symbols.sort(key=lambda item: (item.start_line, item.name, item.kind))
        return symbols

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """Python v1 does not provide smart chunk ranges yet."""
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """Python v1 does not derive symbol hints from prompt."""
        _ = prompt
        return ()

    def _class_symbol(self, node: ast.ClassDef) -> OutlineSymbol:
        bases = ", ".join(ast.unparse(base) for base in node.bases) if node.bases else ""
        signature = f"({bases})" if bases else "()"
        return OutlineSymbol(
            kind="class",
            name=node.name,
            signature=signature,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            doc=_doc_first_line(node),
        )

    def _function_symbol(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> OutlineSymbol:
        kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
        signature = f"({ast.unparse(node.args)})"
        return OutlineSymbol(
            kind=kind,
            name=node.name,
            signature=signature,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            doc=_doc_first_line(node),
        )

    def _method_symbol(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_name: str,
    ) -> OutlineSymbol:
        kind = "async_method" if isinstance(node, ast.AsyncFunctionDef) else "method"
        signature = f"({ast.unparse(node.args)})"
        return OutlineSymbol(
            kind=kind,
            name=f"{class_name}.{node.name}",
            signature=signature,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            doc=_doc_first_line(node),
        )


def _doc_first_line(
    node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
) -> str | None:
    doc = ast.get_docstring(node, clean=False)
    if not doc:
        return None
    first = doc.strip().splitlines()
    if not first:
        return None
    return first[0].strip() or None
