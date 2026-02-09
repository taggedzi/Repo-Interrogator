"""Python AST adapter for deterministic symbol outlining."""

from __future__ import annotations

import ast

from repo_mcp.adapters.base import OutlineSymbol, normalize_and_sort_symbols, normalize_signature


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
        except (SyntaxError, ValueError):
            return []

        collector = _PythonOutlineCollector()
        collector.visit(tree)
        return normalize_and_sort_symbols(collector.symbols)

    def smart_chunks(self, path: str, text: str) -> list[tuple[int, int]] | None:
        """Python v1 does not provide smart chunk ranges yet."""
        _ = path
        _ = text
        return None

    def symbol_hints(self, prompt: str) -> tuple[str, ...]:
        """Python v1 does not derive symbol hints from prompt."""
        _ = prompt
        return ()


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


class _PythonOutlineCollector(ast.NodeVisitor):
    """Collect Python declaration symbols from all nested and conditional scopes."""

    def __init__(self) -> None:
        self.symbols: list[OutlineSymbol] = []
        self._scope_stack: list[tuple[str, str]] = []
        self._control_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        parent_symbol = self._parent_symbol()
        self.symbols.append(
            OutlineSymbol(
                kind="class",
                name=self._qualified_name(node.name),
                signature=_class_signature(node),
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                doc=_doc_first_line(node),
                parent_symbol=parent_symbol,
                scope_kind=self._scope_kind(),
                is_conditional=self._is_conditional(),
                decl_context=self._decl_context(),
            )
        )
        self._scope_stack.append(("class", node.name))
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._add_function_like_symbol(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._add_function_like_symbol(node)

    def _add_function_like_symbol(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        parent_kind = self._scope_stack[-1][0] if self._scope_stack else None
        if parent_kind == "class":
            kind = "async_method" if isinstance(node, ast.AsyncFunctionDef) else "method"
        else:
            kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"

        parent_symbol = self._parent_symbol()
        self.symbols.append(
            OutlineSymbol(
                kind=kind,
                name=self._qualified_name(node.name),
                signature=normalize_signature(f"({ast.unparse(node.args)})"),
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                doc=_doc_first_line(node),
                parent_symbol=parent_symbol,
                scope_kind=self._scope_kind(),
                is_conditional=self._is_conditional(),
                decl_context=self._decl_context(),
            )
        )
        self._scope_stack.append(("function", node.name))
        self.generic_visit(node)
        self._scope_stack.pop()

    def _qualified_name(self, local_name: str) -> str:
        if not self._scope_stack:
            return local_name
        return ".".join([*(name for _, name in self._scope_stack), local_name])

    def _parent_symbol(self) -> str | None:
        if not self._scope_stack:
            return None
        return ".".join(name for _, name in self._scope_stack)

    def _scope_kind(self) -> str:
        if not self._scope_stack:
            return "module"
        return self._scope_stack[-1][0]

    def _is_conditional(self) -> bool:
        return bool(self._control_stack)

    def _decl_context(self) -> str | None:
        if not self._control_stack:
            return None
        return ">".join(self._control_stack)

    def _visit_control_node(self, label: str, node: ast.AST) -> None:
        self._control_stack.append(label)
        self.generic_visit(node)
        self._control_stack.pop()

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        self._visit_control_node("if", node)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        self._visit_control_node("for", node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802
        self._visit_control_node("async_for", node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self._visit_control_node("while", node)

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        self._visit_control_node("try", node)

    def visit_TryStar(self, node: ast.TryStar) -> None:  # noqa: N802
        self._visit_control_node("try_star", node)

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        self._visit_control_node("with", node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:  # noqa: N802
        self._visit_control_node("async_with", node)

    def visit_Match(self, node: ast.Match) -> None:  # noqa: N802
        self._visit_control_node("match", node)


def _class_signature(node: ast.ClassDef) -> str | None:
    parts = [ast.unparse(base) for base in node.bases]
    for keyword in node.keywords:
        if keyword.arg is None:
            parts.append(f"**{ast.unparse(keyword.value)}")
        else:
            parts.append(f"{keyword.arg}={ast.unparse(keyword.value)}")
    if not parts:
        return "()"
    return normalize_signature(f"({', '.join(parts)})")
