from __future__ import annotations

from pathlib import Path

from repo_mcp.server import create_server


def test_repo_references_calls_python_resolver_once_per_request(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "alpha.py").write_text(
        "def target():\n    return 1\n\n\ndef caller():\n    return target()\n",
        encoding="utf-8",
    )
    (src / "beta.py").write_text(
        "from alpha import target\n\n\ndef another():\n    return target()\n",
        encoding="utf-8",
    )

    server = create_server(repo_root=str(tmp_path))
    refreshed = server.handle_payload(
        {"id": "req-ref-group-refresh", "method": "repo.refresh_index", "params": {}}
    )
    assert refreshed["ok"] is True

    adapter = server._adapters.select("src/alpha.py")
    original_single = adapter.references_for_symbol
    original_many = getattr(adapter, "references_for_symbols", None)
    single_calls = 0
    many_calls = 0

    def wrapped(symbol: str, files: list[tuple[str, str]], *, top_k: int | None = None):
        nonlocal single_calls
        single_calls += 1
        return original_single(symbol, files, top_k=top_k)

    def wrapped_many(symbols: list[str], files: list[tuple[str, str]], *, top_k: int | None = None):
        nonlocal many_calls
        many_calls += 1
        assert callable(original_many)
        return original_many(symbols, files, top_k=top_k)

    adapter.references_for_symbol = wrapped  # type: ignore[method-assign]
    if callable(original_many):
        adapter.references_for_symbols = wrapped_many  # type: ignore[method-assign]
    response = server.handle_payload(
        {
            "id": "req-ref-group-1",
            "method": "repo.references",
            "params": {"symbol": "target", "top_k": 20},
        }
    )

    assert response["ok"] is True
    assert single_calls + many_calls == 1
