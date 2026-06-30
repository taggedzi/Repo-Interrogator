from __future__ import annotations

from pathlib import Path

from tests.helpers import call_tool, extract_result, is_tool_error

from repo_mcp.server import create_server


def _load_fixture(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_multilanguage_outline_is_stable_across_repeated_and_path_style_calls(
    tmp_path: Path,
) -> None:
    files = {
        "src/sample.py": _load_fixture("tests/fixtures/adapters/python/sample.py"),
        "src/sample.ts": _load_fixture("tests/fixtures/adapters/ts_js/sample.ts"),
        "src/sample.js": _load_fixture("tests/fixtures/adapters/ts_js/sample.js"),
        "src/sample.java": _load_fixture("tests/fixtures/adapters/java/sample.java"),
        "src/sample.go": _load_fixture("tests/fixtures/adapters/go/sample.go"),
        "src/sample.rs": _load_fixture("tests/fixtures/adapters/rust/sample.rs"),
        "src/sample.cpp": _load_fixture("tests/fixtures/adapters/cpp/sample.cpp"),
        "src/sample.cs": _load_fixture("tests/fixtures/adapters/csharp/sample.cs"),
        "docs/sample.md": _load_fixture("tests/fixtures/adapters/lexical/sample.md"),
    }
    expected_language = {
        "src/sample.py": "python",
        "src/sample.ts": "ts_js_lexical",
        "src/sample.js": "ts_js_lexical",
        "src/sample.java": "java_lexical",
        "src/sample.go": "go_lexical",
        "src/sample.rs": "rust_lexical",
        "src/sample.cpp": "cpp_lexical",
        "src/sample.cs": "csharp_lexical",
        "docs/sample.md": "lexical",
    }

    for rel_path, content in files.items():
        _write(tmp_path / rel_path, content)

    server = create_server(repo_root=str(tmp_path))

    for index, rel_path in enumerate(sorted(files.keys()), start=1):
        windows_path = rel_path.replace("/", "\\")

        first = call_tool(server, f"req-multi-det-{index}-a", "repo.outline", {"path": rel_path})
        second = call_tool(server, f"req-multi-det-{index}-b", "repo.outline", {"path": rel_path})
        windows = call_tool(
            server, f"req-multi-det-{index}-c", "repo.outline", {"path": windows_path}
        )

        assert not is_tool_error(first)
        assert not is_tool_error(second)
        assert not is_tool_error(windows)

        assert extract_result(first)["language"] == expected_language[rel_path]
        assert extract_result(second)["language"] == expected_language[rel_path]
        assert extract_result(windows)["language"] == expected_language[rel_path]

        assert extract_result(first) == extract_result(second)
        assert extract_result(first) == extract_result(windows)
