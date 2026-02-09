from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from repo_mcp.adapters import (
    CppLexicalAdapter,
    CSharpLexicalAdapter,
    GoLexicalAdapter,
    JavaLexicalAdapter,
    LexicalFallbackAdapter,
    PythonAstAdapter,
    RustLexicalAdapter,
    TypeScriptJavaScriptLexicalAdapter,
)


def _load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _load_golden(name: str) -> dict[str, object]:
    golden_path = Path("tests/fixtures/adapters/golden") / f"{name}.json"
    return json.loads(golden_path.read_text(encoding="utf-8"))


def _actual_payload(adapter: object, outline_path: str, source_text: str) -> dict[str, object]:
    symbols = [asdict(item) for item in adapter.outline(outline_path, source_text)]
    return {
        "language": adapter.name,
        "symbols": symbols,
    }


def test_multilanguage_adapter_outputs_match_golden_snapshots() -> None:
    cases = [
        (
            "python",
            PythonAstAdapter(),
            "src/sample.py",
            _load_text("tests/fixtures/adapters/python/sample.py"),
        ),
        (
            "ts",
            TypeScriptJavaScriptLexicalAdapter(),
            "src/sample.ts",
            _load_text("tests/fixtures/adapters/ts_js/sample.ts"),
        ),
        (
            "js",
            TypeScriptJavaScriptLexicalAdapter(),
            "src/sample.js",
            _load_text("tests/fixtures/adapters/ts_js/sample.js"),
        ),
        (
            "java",
            JavaLexicalAdapter(),
            "src/sample.java",
            _load_text("tests/fixtures/adapters/java/sample.java"),
        ),
        (
            "go",
            GoLexicalAdapter(),
            "src/sample.go",
            _load_text("tests/fixtures/adapters/go/sample.go"),
        ),
        (
            "rust",
            RustLexicalAdapter(),
            "src/sample.rs",
            _load_text("tests/fixtures/adapters/rust/sample.rs"),
        ),
        (
            "cpp",
            CppLexicalAdapter(),
            "src/sample.cpp",
            _load_text("tests/fixtures/adapters/cpp/sample.cpp"),
        ),
        (
            "csharp",
            CSharpLexicalAdapter(),
            "src/sample.cs",
            _load_text("tests/fixtures/adapters/csharp/sample.cs"),
        ),
        (
            "lexical",
            LexicalFallbackAdapter(),
            "docs/sample.md",
            _load_text("tests/fixtures/adapters/lexical/sample.md"),
        ),
    ]

    for golden_name, adapter, outline_path, source_text in cases:
        expected = _load_golden(golden_name)
        first = _actual_payload(adapter, outline_path, source_text)
        second = _actual_payload(adapter, outline_path, source_text)

        assert first == expected
        assert second == expected
        assert first == second
