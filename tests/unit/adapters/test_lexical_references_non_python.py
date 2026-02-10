from __future__ import annotations

from repo_mcp.adapters import (
    CppLexicalAdapter,
    CSharpLexicalAdapter,
    GoLexicalAdapter,
    JavaLexicalAdapter,
    RustLexicalAdapter,
    TypeScriptJavaScriptLexicalAdapter,
)


def test_non_python_adapters_return_deterministic_lexical_references() -> None:
    cases = [
        (
            TypeScriptJavaScriptLexicalAdapter(),
            "Service.run",
            [
                (
                    "src/service.ts",
                    """
export class Service {
  run(input: string): string {
    return input;
  }
}
""",
                ),
                (
                    "src/app.ts",
                    """
import { Service } from "./service";

const svc = new Service();
svc.run("ok");
""",
                ),
            ],
            "call",
        ),
        (
            JavaLexicalAdapter(),
            "Service.run",
            [
                (
                    "src/Service.java",
                    """
package com.example;

public class Service {
    public String run(String input) {
        return input;
    }
}
""",
                ),
                (
                    "src/App.java",
                    """
import com.example.Service;

class App {
    String f() {
        return new Service().run("ok");
    }
}
""",
                ),
            ],
            "call",
        ),
        (
            GoLexicalAdapter(),
            "Service.Run",
            [
                (
                    "src/service.go",
                    """
package worker

type Service struct {}

func (s *Service) Run() error {
    return nil
}
""",
                ),
                (
                    "src/app.go",
                    """
package worker

func execute(s *Service) error {
    return s.Run()
}
""",
                ),
            ],
            "call",
        ),
        (
            RustLexicalAdapter(),
            "Service.run",
            [
                (
                    "src/service.rs",
                    """
pub struct Service;

impl Service {
    pub fn run(&self) {}
}
""",
                ),
                (
                    "src/app.rs",
                    """
use crate::service::Service;

fn use_run(service: Service) {
    service.run();
}
""",
                ),
            ],
            "call",
        ),
        (
            CppLexicalAdapter(),
            "Service.run",
            [
                (
                    "src/service.hpp",
                    """
class Service {
public:
    int run(int value) const;
};
""",
                ),
                (
                    "src/app.cpp",
                    """
#include "service.hpp"

int execute() {
    Service svc;
    return svc.run(1);
}
""",
                ),
            ],
            "call",
        ),
        (
            CSharpLexicalAdapter(),
            "Service.RunAsync",
            [
                (
                    "src/Service.cs",
                    """
public class Service
{
    public Task<string> RunAsync(string input)
    {
        return Task.FromResult(input);
    }
}
""",
                ),
                (
                    "src/App.cs",
                    """
using App.Core;

public class App
{
    public async Task<string> Execute()
    {
        var svc = new Service();
        return await svc.RunAsync("ok");
    }
}
""",
                ),
            ],
            "call",
        ),
    ]

    for adapter, symbol, files, expected_kind in cases:
        first = adapter.references_for_symbol(symbol, files)
        second = adapter.references_for_symbol(symbol, files)

        assert first == second
        assert first
        assert all(item.strategy == "lexical" for item in first)
        assert all(item.symbol == symbol for item in first)
        assert expected_kind in {item.kind for item in first}
        assert [(item.path, item.line, item.symbol, item.kind) for item in first] == sorted(
            (item.path, item.line, item.symbol, item.kind) for item in first
        )


def test_non_python_lexical_references_are_stable_with_mixed_path_styles_and_top_k() -> None:
    adapter = TypeScriptJavaScriptLexicalAdapter()
    files = [
        (
            "src\\b.ts",
            """
const svc = new Service();
svc.run("b");
""",
        ),
        (
            "src/a.ts",
            """
const svc = new Service();
svc.run("a");
""",
        ),
    ]

    first = adapter.references_for_symbol("Service.run", files)
    second = adapter.references_for_symbol("Service.run", files)
    limited = adapter.references_for_symbol("Service.run", files, top_k=2)

    assert first == second
    assert first
    assert first[0].path == "src/a.ts"
    assert first[-1].path == "src\\b.ts"
    assert limited == first[:2]
