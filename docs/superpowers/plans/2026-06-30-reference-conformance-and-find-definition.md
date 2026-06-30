# Reference Conformance & repo.find_definition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the demonstrated `repo.references` blind spot (bare-name usages like `key=_rank_sort_key` are invisible) by emitting `read`/`write` reference kinds from the Python adapter, and add a new `repo.find_definition` tool so an AI can find where a symbol is declared without scanning per-file outlines.

**Architecture:** Two additive changes to the existing Python-first adapter architecture, no new modules, no new dependencies, no persisted index state. `_PythonReferenceCollector` gains a `visit_Name` pass with explicit dedup against already-classified Call/ClassDef-base nodes. `repo.find_definition` reuses the exact same file-discovery-and-caching path `repo.references` already uses (`StdioServer._reference_source_files`), running each file's existing `adapter.outline()` and filtering by name match — same AST-for-Python/lexical-for-others split the rest of the project uses.

**Tech Stack:** Python 3.11+, stdlib `ast` only, existing project test stack (pytest).

## Global Constraints

- No new runtime dependencies (`pyproject.toml` `dependencies = []` stays empty).
- No LLM calls; all logic deterministic.
- Output ordering must be explicit and stable — no reliance on OS/dict iteration order beyond what's already sorted.
- Ruff only for formatting/linting (`python -m ruff format .`, `python -m ruff check .`); `python -m mypy src` must pass (strict mode).
- Schema/contract changes require `SPEC.md` updated as part of this plan, not deferred.
- Tests must be self-contained, no network calls.

---

### Task 1: Emit `read`/`write` reference kinds from the Python adapter, with dedup

**Files:**
- Modify: `src/repo_mcp/adapters/python.py:289-329` (`_PythonReferenceCollector`)
- Test: `tests/unit/adapters/test_python_references.py`

**Interfaces:**
- Consumes: nothing new — operates on `ast.Name` nodes already reachable via existing `generic_visit` traversal.
- Produces: `_PythonReferenceCollector.candidates` (existing `list[tuple[int, str, str, str, str]]` of `(line, candidate, kind, evidence, confidence)`) now also contains `kind="read"` and `kind="write"` entries with `confidence="low"`. No change to the tuple shape, so every downstream consumer (`PythonAstAdapter.references_for_symbols`, the caching layer keyed by content hash) is unaffected.

- [ ] **Step 1: Write the failing regression test for the demonstrated bug**

Add to `tests/unit/adapters/test_python_references.py`:

```python
def test_python_references_captures_bare_name_passed_as_keyword_argument() -> None:
    files = [
        (
            "src/engine.py",
            """
def _rank_sort_key(hit):
    return hit


def build():
    return sorted([], key=_rank_sort_key)
""",
        ),
    ]

    adapter = PythonAstAdapter()
    references = adapter.references_for_symbol("_rank_sort_key", files)

    assert [(item.path, item.line, item.kind, item.confidence) for item in references] == [
        ("src/engine.py", 7, "read", "low"),
    ]


def test_python_references_captures_write_reference_on_rebind() -> None:
    files = [
        (
            "src/handlers.py",
            """
def real_func():
    pass


real_func = decorate(real_func)
""",
        ),
    ]

    adapter = PythonAstAdapter()
    references = adapter.references_for_symbol("real_func", files)

    assert [(item.path, item.line, item.kind, item.confidence) for item in references] == [
        ("src/handlers.py", 6, "read", "low"),
        ("src/handlers.py", 6, "write", "low"),
    ]


def test_python_references_does_not_duplicate_call_target_as_read() -> None:
    files = [
        (
            "src/service.py",
            """
class Service:
    pass


Service()
""",
        ),
    ]

    adapter = PythonAstAdapter()
    references = adapter.references_for_symbol("Service", files)

    assert [(item.path, item.line, item.kind) for item in references] == [
        ("src/service.py", 6, "instantiation"),
    ]


def test_python_references_does_not_duplicate_inheritance_base_as_read() -> None:
    files = [
        (
            "src/models.py",
            """
class Base:
    pass


class Sub(Base):
    pass
""",
        ),
    ]

    adapter = PythonAstAdapter()
    references = adapter.references_for_symbol("Base", files)

    assert [(item.path, item.line, item.kind) for item in references] == [
        ("src/models.py", 6, "inheritance"),
    ]


def test_python_references_captures_bare_decorator_application() -> None:
    files = [
        (
            "src/decorators.py",
            """
def my_decorator(fn):
    return fn


@my_decorator
def handler():
    pass
""",
        ),
    ]

    adapter = PythonAstAdapter()
    references = adapter.references_for_symbol("my_decorator", files)

    assert [(item.path, item.line, item.kind, item.confidence) for item in references] == [
        ("src/decorators.py", 6, "read", "low"),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/adapters/test_python_references.py -v`
Expected: the five new tests FAIL or are vacuously passing for the wrong reason — `test_python_references_captures_bare_name_passed_as_keyword_argument`, `test_python_references_captures_write_reference_on_rebind`, and `test_python_references_captures_bare_decorator_application` fail with empty/wrong reference lists (the bug being fixed); the two dedup tests (`test_python_references_does_not_duplicate_call_target_as_read`, `test_python_references_does_not_duplicate_inheritance_base_as_read`) currently PASS already (no `read` visitor exists yet to cause duplication) — that's expected, they exist to catch a regression in Step 3, not to currently fail.

- [ ] **Step 3: Implement `visit_Name` with dedup in `_PythonReferenceCollector`**

Replace the `_PythonReferenceCollector` class in `src/repo_mcp/adapters/python.py:289-329` with:

```python
class _PythonReferenceCollector(ast.NodeVisitor):
    """Collect Python usage candidates that can map to symbol references."""

    def __init__(self) -> None:
        self.candidates: list[tuple[int, str, str, str, str]] = []
        self._suppressed_name_ids: set[int] = set()

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            symbol = alias.name
            evidence = f"import {symbol}"
            self.candidates.append((node.lineno, symbol, "import", evidence, "high"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        module = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                continue
            joined = f"{module}.{alias.name}".strip(".")
            evidence = f"from {module or '.'} import {alias.name}"
            self.candidates.append((node.lineno, joined, "import", evidence, "high"))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        for base in node.bases:
            dotted = _dotted_name(base)
            if dotted is None:
                continue
            evidence = f"class {node.name}({dotted})"
            self.candidates.append((node.lineno, dotted, "inheritance", evidence, "high"))
            if isinstance(base, ast.Name):
                self._suppressed_name_ids.add(id(base))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        dotted = _dotted_name(node.func)
        if dotted is not None:
            last = dotted.rsplit(".", 1)[-1]
            kind = "instantiation" if last[:1].isupper() else "call"
            confidence = "high" if "." in dotted else "medium"
            evidence = f"{dotted}()"
            self.candidates.append((node.lineno, dotted, kind, evidence, confidence))
            if isinstance(node.func, ast.Name):
                self._suppressed_name_ids.add(id(node.func))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if id(node) in self._suppressed_name_ids:
            return
        if isinstance(node.ctx, ast.Load):
            evidence = node.id
            self.candidates.append((node.lineno, node.id, "read", evidence, "low"))
        elif isinstance(node.ctx, ast.Store):
            evidence = f"{node.id} = ..."
            self.candidates.append((node.lineno, node.id, "write", evidence, "low"))
```

Note: each `_PythonReferenceCollector` instance is short-lived (constructed fresh per file in `PythonAstAdapter._reference_candidates`), so `_suppressed_name_ids` never grows across files and needs no cleanup.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/adapters/test_python_references.py -v`
Expected: all tests PASS, including the pre-existing ones (`test_python_references_for_symbol_links_cross_file_usages`, `test_python_references_for_symbol_are_deterministic_and_sorted`, `test_python_references_for_symbol_top_k_is_applied_after_sorting`, `test_python_references_for_symbol_skips_non_python_and_parse_failures`, `test_python_references_reuses_cached_candidates_between_symbols`).

- [ ] **Step 5: Verify the existing golden snapshot test still passes unchanged**

Run: `python -m pytest tests/unit/adapters/test_python_reference_golden_snapshot.py -v`
Expected: PASS with no changes to `tests/fixtures/adapters/golden/python_references.json`. The fixture only contains `Service`/`svc.run()` usage where `Service` and `run` are always the `func` of a `Call` (suppressed) — if this test fails, the dedup suppression in Step 3 has a gap; do not edit the golden fixture to paper over it, fix the suppression logic instead.

- [ ] **Step 6: Run the full test suite to check for unrelated regressions**

Run: `python -m pytest -q`
Expected: PASS. The new `read`/`write` candidates only surface in results when a caller explicitly queries a symbol whose short name matches a bare variable/parameter name somewhere — if any existing test starts failing because of new unrelated `read`/`write` entries appearing in a `repo.references` result list, inspect that test's fixture for a bare-name collision and adjust the fixture's symbol choice rather than special-casing the collector.

- [ ] **Step 7: Commit**

```bash
git add src/repo_mcp/adapters/python.py tests/unit/adapters/test_python_references.py
git commit -m "$(cat <<'EOF'
fix: emit read/write reference kinds for bare-name Python usages

repo.references previously missed any usage that wasn't an import, call,
or inheritance base - e.g. a function passed by name (sorted(..., key=fn))
was invisible. Adds a dedup-safe visit_Name pass so SPEC.md's documented
read/write kinds are actually produced.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add a shared cross-adapter symbol-name matcher

**Files:**
- Modify: `src/repo_mcp/adapters/base.py`
- Test: `tests/unit/adapters/test_outline_symbol_matching.py` (new)

**Interfaces:**
- Consumes: nothing.
- Produces: `outline_symbol_matches(candidate_name: str, requested_symbol: str) -> bool` in `repo_mcp.adapters.base`, used by Task 3's `repo.find_definition` implementation to match `OutlineSymbol.name` values against a requested symbol string, mirroring the matching semantics `python.py`'s existing `_candidate_matches_symbol` already uses for references (exact match, short-name match, or qualified-suffix match).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/adapters/test_outline_symbol_matching.py`:

```python
from __future__ import annotations

from repo_mcp.adapters.base import outline_symbol_matches


def test_outline_symbol_matches_exact_name() -> None:
    assert outline_symbol_matches("Service.run", "Service.run") is True


def test_outline_symbol_matches_short_name_request() -> None:
    assert outline_symbol_matches("Service.run", "run") is True


def test_outline_symbol_matches_qualified_suffix() -> None:
    assert outline_symbol_matches("Service.run", "run") is True
    assert outline_symbol_matches("run", "Service.run") is True


def test_outline_symbol_matches_rejects_unrelated_name() -> None:
    assert outline_symbol_matches("Service.run", "Service.stop") is False
    assert outline_symbol_matches("Service.run", "OtherService.run") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/adapters/test_outline_symbol_matching.py -v`
Expected: FAIL with `ImportError: cannot import name 'outline_symbol_matches'`.

- [ ] **Step 3: Implement `outline_symbol_matches`**

Add to `src/repo_mcp/adapters/base.py`, after `reference_sort_key` (around line 88):

```python
def outline_symbol_matches(candidate_name: str, requested_symbol: str) -> bool:
    """Return True when an outline symbol's qualified name matches a requested symbol.

    Mirrors the matching semantics used for cross-file reference lookups: an
    exact match, a bare short-name match, or a qualified-suffix match (e.g.
    requesting "run" matches "Service.run", and requesting "Service.run"
    matches a bare "run" declaration).
    """
    if candidate_name == requested_symbol:
        return True
    short_requested = requested_symbol.rsplit(".", 1)[-1]
    short_candidate = candidate_name.rsplit(".", 1)[-1]
    if candidate_name == short_requested:
        return True
    if short_candidate == short_requested:
        return candidate_name.endswith(f".{short_requested}") or requested_symbol.endswith(
            f".{short_candidate}"
        )
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/adapters/test_outline_symbol_matching.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/repo_mcp/adapters/base.py tests/unit/adapters/test_outline_symbol_matching.py
git commit -m "$(cat <<'EOF'
feat: add shared outline_symbol_matches helper

Cross-adapter symbol-name matcher for the upcoming repo.find_definition
tool, mirroring the existing reference-matching semantics.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Implement the `repo.find_definition` tool end-to-end

**Files:**
- Modify: `src/repo_mcp/tools/schemas.py`
- Modify: `src/repo_mcp/tools/builtin.py`
- Modify: `src/repo_mcp/server.py`
- Test: `tests/integration/test_repo_find_definition_tool.py` (new)

**Interfaces:**
- Consumes: `outline_symbol_matches` (Task 2), `self._reference_source_files` (existing, `server.py:555`), `self._adapters.select(path)` (existing `AdapterRegistry.select`), `normalize_and_sort_symbols` (existing, already imported in `server.py`).
- Produces: tool `repo.find_definition` registered in `ToolRegistry`, callable via `tools/call`. Response shape: `{"symbol": str, "definitions": [{"path": str, "start_line": int, "end_line": int, "kind": str, "signature": str | None, "scope_kind": str | None}], "truncated": bool, "total_candidates": int}`.

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_repo_find_definition_tool.py`:

```python
from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.server import create_server


def test_repo_find_definition_returns_declaration_site(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        "class Service:\n    def run(self) -> str:\n        return 'ok'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text(
        "from service import Service\n\nsvc = Service()\nsvc.run()\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    response = call_tool(
        server, "req-def-1", "repo.find_definition", {"symbol": "Service.run", "top_k": 10}
    )
    assert not is_tool_error(response)
    result = extract_result(response)

    assert result["symbol"] == "Service.run"
    assert result["definitions"] == [
        {
            "path": "src/service.py",
            "start_line": 2,
            "end_line": 3,
            "kind": "method",
            "signature": "(self)",
            "scope_kind": "class",
        }
    ]
    assert result["truncated"] is False
    assert result["total_candidates"] == 1


def test_repo_find_definition_unknown_symbol_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        "class Service:\n    def run(self) -> str:\n        return 'ok'\n",
        encoding="utf-8",
    )
    server = create_server(repo_root=str(tmp_path))

    response = call_tool(
        server, "req-def-2", "repo.find_definition", {"symbol": "NoSuchSymbol", "top_k": 10}
    )
    assert not is_tool_error(response)
    result = extract_result(response)

    assert result["definitions"] == []
    assert result["total_candidates"] == 0
    assert result["truncated"] is False


def test_repo_find_definition_path_scope_and_truncation(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def handler():\n    pass\n", encoding="utf-8")
    server = create_server(repo_root=str(tmp_path))

    scoped = extract_result(
        call_tool(
            server,
            "req-def-scope-1",
            "repo.find_definition",
            {"symbol": "handler", "path": "src/a.py", "top_k": 10},
        )
    )
    assert [item["path"] for item in scoped["definitions"]] == ["src/a.py"]

    truncated = extract_result(
        call_tool(
            server, "req-def-scope-2", "repo.find_definition", {"symbol": "handler", "top_k": 1}
        )
    )
    assert truncated["truncated"] is True
    assert truncated["total_candidates"] == 2
    assert len(truncated["definitions"]) == 1


def test_repo_find_definition_requires_non_empty_symbol(tmp_path: Path) -> None:
    server = create_server(repo_root=str(tmp_path))

    response = call_tool(server, "req-def-3", "repo.find_definition", {"symbol": "  "})
    assert is_tool_error(response)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_repo_find_definition_tool.py -v`
Expected: FAIL — `repo.find_definition` is not a registered tool yet (`UNKNOWN_TOOL` dispatch error surfaced as `isError: true`).

- [ ] **Step 3: Add the tool schema**

In `src/repo_mcp/tools/schemas.py`, add a new entry immediately after the `"repo.references"` entry (after the closing `},` that follows line 189):

```python
    "repo.find_definition": {
        "name": "repo.find_definition",
        "description": (
            "Find where a named symbol is declared using AST (Python) or lexical "
            "outline analysis. Returns file path, line range, kind, and signature "
            "for each matching declaration. Use this before repo.references when "
            "you don't yet know which file defines a symbol."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": (
                        "Symbol name to find the declaration for (e.g. 'MyClass.my_method')."
                    ),
                },
                "path": {
                    "type": "string",
                    "description": "Optional file path to scope the definition search to one file.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of definitions to return.",
                },
            },
            "required": ["symbol"],
        },
    },
```

- [ ] **Step 4: Add the handler and registration in `tools/builtin.py`**

In `src/repo_mcp/tools/builtin.py`, update the `register_builtin_tools` signature (currently starting at line 34) to add a new parameter. Replace:

```python
def register_builtin_tools(
    registry: ToolRegistry,
    repo_root: Path,
    limits: SecurityLimits,
    read_audit_entries: Callable[[str | None, int], list[dict[str, object]]],
    list_files: Callable[[dict[str, object]], dict[str, object]],
    refresh_index: Callable[[bool], dict[str, object]],
    read_index_status: Callable[[], IndexStatus],
    search_index: Callable[[str, int, str | None, str | None], list[dict[str, object]]],
    outline_path: Callable[[str], dict[str, object]],
    build_context_bundle: Callable[[dict[str, object]], dict[str, object]],
    resolve_references: Callable[[dict[str, object]], dict[str, object]],
    config: ServerConfig,
) -> None:
```

with:

```python
def register_builtin_tools(
    registry: ToolRegistry,
    repo_root: Path,
    limits: SecurityLimits,
    read_audit_entries: Callable[[str | None, int], list[dict[str, object]]],
    list_files: Callable[[dict[str, object]], dict[str, object]],
    refresh_index: Callable[[bool], dict[str, object]],
    read_index_status: Callable[[], IndexStatus],
    search_index: Callable[[str, int, str | None, str | None], list[dict[str, object]]],
    outline_path: Callable[[str], dict[str, object]],
    build_context_bundle: Callable[[dict[str, object]], dict[str, object]],
    resolve_references: Callable[[dict[str, object]], dict[str, object]],
    find_definition: Callable[[dict[str, object]], dict[str, object]],
    config: ServerConfig,
) -> None:
```

Then, in the same function body, add a registration call immediately after the existing `"repo.references"` registration block (after the `)` that closes it, currently ending at line 83):

```python
    registry.register(
        "repo.find_definition",
        _find_definition_handler(limits, find_definition),
        _meta("repo.find_definition"),
    )
```

Finally, add the handler factory function. Insert it immediately after `_references_handler` (after the function ending at line 353):

```python
def _find_definition_handler(
    limits: SecurityLimits,
    find_definition: Callable[[dict[str, object]], dict[str, object]],
) -> ToolHandler:
    def handler(arguments: dict[str, object]) -> dict[str, object]:
        symbol = arguments.get("symbol")
        path = arguments.get("path")
        top_k = arguments.get("top_k", limits.max_references)

        if not isinstance(symbol, str) or not symbol.strip():
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.find_definition symbol must be a non-empty string.",
            )
        if path is not None and not isinstance(path, str):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.find_definition path must be a string when provided.",
            )
        if isinstance(path, str) and not path.strip():
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.find_definition path must be a non-empty string when provided.",
            )
        if isinstance(top_k, int) and top_k > limits.max_references:
            raise PolicyBlockedError(
                reason="Requested top_k exceeds max_references limit.",
                hint="Reduce top_k or adjust the configured references limit.",
            )
        if not isinstance(top_k, int) or top_k < 1:
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.find_definition top_k must be an integer >= 1.",
            )

        payload: dict[str, object] = {"symbol": symbol, "top_k": top_k}
        if isinstance(path, str):
            payload["path"] = path.strip()
        return find_definition(payload)

    return handler
```

- [ ] **Step 5: Implement `StdioServer._find_definition` and wire it up**

In `src/repo_mcp/server.py`, update the import block (lines 20-24) to add `outline_symbol_matches`:

```python
from repo_mcp.adapters.base import (
    SymbolReference,
    normalize_and_sort_references,
    normalize_and_sort_symbols,
    outline_symbol_matches,
)
```

Update the `register_builtin_tools(...)` call (lines 89-102) to pass the new callable:

```python
        register_builtin_tools(
            self._registry,
            repo_root=self._repo_root,
            limits=self._limits,
            read_audit_entries=self._audit_logger.read,
            list_files=self._list_files,
            refresh_index=self._index_manager.refresh,
            read_index_status=self._index_manager.status,
            search_index=self._index_manager.search,
            outline_path=self._outline_path,
            build_context_bundle=self._build_context_bundle,
            resolve_references=self._resolve_references,
            find_definition=self._find_definition,
            config=self._config,
        )
```

Add the `_find_definition` method immediately after `_resolve_references` (after the method body ending at `server.py:553`, i.e. right before `def _reference_source_files`):

```python
    def _find_definition(self, arguments: dict[str, object]) -> dict[str, object]:
        symbol_value = arguments.get("symbol")
        if not isinstance(symbol_value, str):
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.find_definition symbol must be a string.",
            )
        symbol = symbol_value.strip()
        if not symbol:
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.find_definition symbol must be a non-empty string.",
            )

        path_value = arguments.get("path")
        path_scope = path_value.strip() if isinstance(path_value, str) else None

        top_k_value = arguments.get("top_k", self._limits.max_references)
        if isinstance(top_k_value, int) and top_k_value > self._limits.max_references:
            raise PolicyBlockedError(
                reason="Requested top_k exceeds max_references limit.",
                hint="Reduce top_k or adjust the configured references limit.",
            )
        if not isinstance(top_k_value, int):
            top_k_value = self._limits.max_references
        if top_k_value < 1:
            raise ToolDispatchError(
                code="INVALID_PARAMS",
                message="repo.find_definition top_k must be >= 1.",
            )

        files = self._reference_source_files(path_scope)
        matches: list[dict[str, object]] = []
        for path, text in files:
            try:
                adapter = self._adapters.select(path)
                outline_symbols = normalize_and_sort_symbols(adapter.outline(path, text))
            except Exception:
                continue
            for outline_symbol in outline_symbols:
                if not outline_symbol_matches(outline_symbol.name, symbol):
                    continue
                matches.append(
                    {
                        "path": path,
                        "start_line": outline_symbol.start_line,
                        "end_line": outline_symbol.end_line,
                        "kind": outline_symbol.kind,
                        "signature": outline_symbol.signature,
                        "scope_kind": outline_symbol.scope_kind,
                    }
                )

        matches.sort(key=lambda item: (item["path"], item["start_line"]))
        total_candidates = len(matches)
        limited = matches[:top_k_value]
        return {
            "symbol": symbol,
            "definitions": limited,
            "truncated": len(limited) < total_candidates,
            "total_candidates": total_candidates,
        }

```

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `python -m pytest tests/integration/test_repo_find_definition_tool.py -v`
Expected: PASS.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest -q`
Expected: PASS for all pre-existing tests except the two tool-count assertions fixed in Task 4 (`tests/integration/test_mcp_protocol.py` and any tool-count check) — confirm those are the *only* failures before proceeding to Task 4.

- [ ] **Step 8: Commit**

```bash
git add src/repo_mcp/tools/schemas.py src/repo_mcp/tools/builtin.py src/repo_mcp/server.py tests/integration/test_repo_find_definition_tool.py
git commit -m "$(cat <<'EOF'
feat: add repo.find_definition tool

Lets an AI client find where a symbol is declared (AST for Python,
lexical outline scan for other languages) without scanning per-file
outlines one at a time. Reuses the existing repo.references file
discovery/caching path.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Fix tool-count assertions and add contract-matrix coverage

**Files:**
- Modify: `tests/integration/test_mcp_protocol.py:133`
- Modify: `tests/integration/test_tool_contract_matrix.py`

**Interfaces:**
- Consumes: the now-registered `repo.find_definition` tool from Task 3.
- Produces: nothing new — these are assertion updates only.

- [ ] **Step 1: Update the tools/list count assertion**

In `tests/integration/test_mcp_protocol.py`, change line 133 from:

```python
    assert len(list_resp["result"]["tools"]) == 9
```

to:

```python
    assert len(list_resp["result"]["tools"]) == 10
```

- [ ] **Step 2: Add `repo.find_definition` to the contract matrix test**

In `tests/integration/test_tool_contract_matrix.py`, add a new entry to the `tool_calls` list (after the `"repo.references"` tuple, currently ending at line 30):

```python
        ("repo.find_definition", {"symbol": "Main.run", "top_k": 5}),
```

Then add a corresponding shape assertion inside the `for idx, (tool_name, arguments) in enumerate(tool_calls):` loop, after the existing `if tool_name == "repo.references":` block (after line 98):

```python
        if tool_name == "repo.find_definition":
            assert set(result.keys()) == {
                "symbol",
                "definitions",
                "truncated",
                "total_candidates",
            }
```

- [ ] **Step 3: Run both tests to verify they pass**

Run: `python -m pytest tests/integration/test_mcp_protocol.py tests/integration/test_tool_contract_matrix.py -v`
Expected: PASS.

- [ ] **Step 4: Run full test suite to confirm no other count assertions were missed**

Run: `python -m pytest -q`
Expected: PASS. If any other test still asserts a tool count of 9 or enumerates exactly 9 tool names, fix it the same way before proceeding.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_mcp_protocol.py tests/integration/test_tool_contract_matrix.py
git commit -m "$(cat <<'EOF'
test: update tool-count assertions for repo.find_definition

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Update documentation and SPEC

**Files:**
- Modify: `SPEC.md`
- Modify: `README.md`
- Modify: `docs/AI_INTEGRATION.md`
- Modify: `docs/USAGE.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update `SPEC.md` §10.4 to confirm read/write kinds are emitted**

In `SPEC.md`, after the existing reference-kind bullet at line 324:

```
* `kind`: reference kind (for example `import`, `call`, `read`, `write`, `inheritance`, `instantiation`)
```

add a new sentence directly below the "Required behavior" list (after line 327, before the "Reference record fields:" heading at line 319 — insert after line 317's closing of the "Required behavior" bullet list, i.e. immediately before `Reference record fields:`):

```markdown
Python adapter v2.6+ emits `read` and `write` kinds for bare-name usages that
are not an import, call, or inheritance base (for example, a function passed
by name as `key=my_sort_key`, a bare `@decorator` application, or a rebind of
an existing name). These carry `confidence: low`, since unscoped name
matching has higher false-positive risk than qualified or call-site matches.
```

- [ ] **Step 2: Add `SPEC.md` §11.10 for `repo.find_definition`**

After the `### 11.9 \`repo.references\` (v2.5)` section (ends at line 649, right before the `## 12. Observability` heading at line 651), insert:

```markdown
### 11.10 `repo.find_definition` (v2.6)

Inputs:

* `symbol`
* `path?` (optional path scope)
* `top_k?` (bounded max definitions)

Returns:

* `symbol`
* `definitions` list:

  * `path`
  * `start_line`
  * `end_line`
  * `kind`
  * `signature`
  * `scope_kind`
* `truncated` (bool)
* `total_candidates` (int)

Notes:

* output is deterministic, declaration-based, and uses the same AST
  (Python) / lexical (other languages) split as `repo.outline`
* no disambiguation beyond syntax: if a name is declared in multiple
  places, all matching declarations are returned, sorted `path` ascending
  then `start_line` ascending
* when `path` is omitted, candidate files are selected using the same
  deterministic discovery filters as `repo.references`

---

```

- [ ] **Step 3: Update `README.md` tool list**

In `README.md`, in the `## Tool Surface (Current)` list (lines 86-94), add a new bullet after `- \`repo.references\``:

```markdown
- `repo.find_definition`
```

- [ ] **Step 4: Update `docs/AI_INTEGRATION.md`**

In `docs/AI_INTEGRATION.md`, change line 37 from:

```markdown
4. Client → `tools/list` — server returns all 9 tool definitions with JSON Schema
```

to:

```markdown
4. Client → `tools/list` — server returns all 10 tool definitions with JSON Schema
```

Change line 92 from:

```markdown
All 9 tools are discovered automatically by the client. Descriptions and JSON Schema are served via `tools/list`.
```

to:

```markdown
All 10 tools are discovered automatically by the client. Descriptions and JSON Schema are served via `tools/list`.
```

In the tool table (lines 94-104), add a new row after the `repo.references` row:

```markdown
| `repo.find_definition` | Find where a symbol is declared |
```

- [ ] **Step 5: Add a `repo.find_definition` section to `docs/USAGE.md`**

In `docs/USAGE.md`, after the existing `## \`repo.references\` (v2.5)` section (ends at line 300, right before `## \`repo.build_context_bundle\`` at line 302), insert:

```markdown
## `repo.find_definition` (v2.6)
Return deterministic declaration sites for one symbol.

Params:
- `symbol` (required)
- `path` (optional file scope)
- `top_k` (optional, bounded by reference limits)

Request:

```json
{
  "id": "req-def",
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "repo.find_definition",
    "arguments": {
      "symbol": "Service.run",
      "top_k": 10
    }
  }
}
```

Result fields:
- `symbol`
- `definitions`:
  - `path`
  - `start_line`
  - `end_line`
  - `kind`
  - `signature`
  - `scope_kind`
- `truncated`
- `total_candidates`

Notes:
- Use this before `repo.references` when you don't yet know which file declares a symbol.
- Uses the same AST (Python) / lexical (other languages) split as `repo.outline`.

```

- [ ] **Step 6: Commit**

```bash
git add SPEC.md README.md docs/AI_INTEGRATION.md docs/USAGE.md
git commit -m "$(cat <<'EOF'
docs: document repo.find_definition and read/write reference kinds

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Final verification and TODO.md update

**Files:**
- Modify: `TODO.md`

**Interfaces:** none.

- [ ] **Step 1: Run formatting, linting, and type checks**

Run:
```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
```
Expected: `ruff format` reports no changes needed (or auto-fixes are re-staged before the final commit); `ruff check` and `mypy src` both report no errors.

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest -q`
Expected: all tests PASS.

- [ ] **Step 3: Update `TODO.md`**

In `TODO.md`, the `## Now` section currently reads:

```markdown
## Now

_None open._
```

Leave it as `_None open._` if Task 1-5 commits already landed everything (this plan is the complete unit of work). If this plan is being executed across multiple sessions and isn't fully done yet, instead use this section to track remaining tasks from this plan using the same short, execution-scoped style as the rest of the file.

- [ ] **Step 4: Final commit (only if Step 1 produced formatting changes or Step 3 changed TODO.md)**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: final formatting pass for reference conformance work

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
