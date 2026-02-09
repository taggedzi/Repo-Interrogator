from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_repo_outline_selects_expected_adapter_by_extension(tmp_path: Path) -> None:
    _write_file(tmp_path / "src" / "mod.py", "def f(x: int) -> int:\n    return x\n")
    _write_file(
        tmp_path / "src" / "mod.ts", "export function build(name: string) { return name; }\n"
    )
    _write_file(tmp_path / "src" / "mod.js", "function run(v) { return v; }\n")
    _write_file(
        tmp_path / "src" / "Mod.java", "public class Mod { public int run(int v) { return v; } }\n"
    )
    _write_file(tmp_path / "src" / "mod.go", "package mod\nfunc Build() int { return 1 }\n")
    _write_file(tmp_path / "src" / "mod.rs", "pub fn run(v: i32) -> i32 { v }\n")
    _write_file(
        tmp_path / "src" / "mod.cpp",
        "class Mod { public: int run(int v); };\nint parse(int v) { return v; }\n",
    )
    _write_file(
        tmp_path / "src" / "Mod.cs",
        "namespace Acme;\npublic class Mod { public int Run(int v) { return v; } }\n",
    )
    _write_file(tmp_path / "docs" / "notes.md", "# Notes\n")

    server = create_server(repo_root=str(tmp_path))

    expected = {
        "src/mod.py": "python",
        "src/mod.ts": "ts_js_lexical",
        "src/mod.js": "ts_js_lexical",
        "src/Mod.java": "java_lexical",
        "src/mod.go": "go_lexical",
        "src/mod.rs": "rust_lexical",
        "src/mod.cpp": "cpp_lexical",
        "src/Mod.cs": "csharp_lexical",
        "docs/notes.md": "lexical",
    }

    for index, (path, language) in enumerate(expected.items(), start=1):
        response = server.handle_payload(
            {
                "id": f"req-outline-multi-{index}",
                "method": "repo.outline",
                "params": {"path": path},
            }
        )
        assert response["ok"] is True
        result = response["result"]
        assert result["path"] == path
        assert result["language"] == language

        if language == "lexical":
            assert result["symbols"] == []
        else:
            assert isinstance(result["symbols"], list)
            assert len(result["symbols"]) >= 1
            for symbol in result["symbols"]:
                if language != "python":
                    assert symbol["scope_kind"] in {"module", "class"}
                    if symbol["scope_kind"] == "class":
                        assert symbol["parent_symbol"] is not None
