"""JSON Schema definitions for all built-in MCP tools."""

from __future__ import annotations

TOOL_SCHEMAS: dict[str, dict[str, object]] = {
    "repo.status": {
        "name": "repo.status",
        "description": (
            "Return index state, active limits, enabled adapters, and effective config. "
            "Call this first to verify the server is connected and the index is ready."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "repo.list_files": {
        "name": "repo.list_files",
        "description": (
            "List readable source files under the repository root. "
            "Supports glob filtering. Use to discover what files exist before searching or opening."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "glob": {
                    "type": "string",
                    "description": "Glob pattern to filter results (e.g. 'src/**/*.py').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of files to return.",
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files and directories (default false).",
                },
            },
        },
    },
    "repo.open_file": {
        "name": "repo.open_file",
        "description": (
            "Read a line range from a source file. Returns numbered lines. "
            "Specify start_line and end_line to read a focused range rather than the entire file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative file path (e.g. 'src/server.py').",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read, 1-indexed (default 1).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to read, inclusive.",
                },
            },
            "required": ["path"],
        },
    },
    "repo.outline": {
        "name": "repo.outline",
        "description": (
            "Return the declaration structure of a file using AST (Python) or lexical analysis. "
            "Shows classes, functions, and other symbols with line ranges and parent context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative file path.",
                },
            },
            "required": ["path"],
        },
    },
    "repo.search": {
        "name": "repo.search",
        "description": (
            "Run BM25 full-text search over indexed repository chunks. "
            "Returns ranked hits with file path, line range, snippet, and matched terms. "
            "Run repo.refresh_index first if the index is not yet built."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms (BM25 keyword matching).",
                },
                "mode": {
                    "type": "string",
                    "enum": ["bm25"],
                    "description": "Search mode — only 'bm25' is supported in v1.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                },
                "file_glob": {
                    "type": "string",
                    "description": (
                        "Glob pattern to restrict search to matching files "
                        "(e.g. 'src/**/*.py')."
                    ),
                },
                "path_prefix": {
                    "type": "string",
                    "description": "Path prefix to restrict search scope (e.g. 'src/repo_mcp/').",
                },
            },
            "required": ["query"],
        },
    },
    "repo.build_context_bundle": {
        "name": "repo.build_context_bundle",
        "description": (
            "Build a compact, ranked, cited context bundle for a coding task. "
            "Combines search, outline, and cross-file references into a "
            "budget-bounded excerpt set. Each selection includes why_selected "
            "explaining which signals drove it. Requires the index to be built "
            "first (repo.refresh_index)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Natural language description of your coding task.",
                },
                "budget": {
                    "type": "object",
                    "description": "Size constraints for the bundle.",
                    "properties": {
                        "max_files": {
                            "type": "integer",
                            "description": "Maximum number of files to include.",
                        },
                        "max_total_lines": {
                            "type": "integer",
                            "description": "Maximum total lines across all selected excerpts.",
                        },
                    },
                    "required": ["max_files", "max_total_lines"],
                },
                "strategy": {
                    "type": "string",
                    "enum": ["hybrid"],
                    "description": "Bundle strategy — only 'hybrid' is supported in v1.",
                },
                "include_tests": {
                    "type": "boolean",
                    "description": "Whether to include test files in the bundle.",
                },
            },
            "required": ["prompt", "budget"],
        },
    },
    "repo.references": {
        "name": "repo.references",
        "description": (
            "Find all cross-file references to a named symbol using AST "
            "(Python) or lexical analysis. Returns file paths, line numbers, "
            "strategy, and confidence level per reference."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to find references for (e.g. 'MyClass.my_method').",
                },
                "path": {
                    "type": "string",
                    "description": "Optional file path to scope the reference search to one file.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of references to return.",
                },
            },
            "required": ["symbol"],
        },
    },
    "repo.refresh_index": {
        "name": "repo.refresh_index",
        "description": (
            "Build or incrementally refresh the BM25 search index. "
            "Run this before searching or bundling if the index is stale or not yet built. "
            "Use force=true to rebuild from scratch."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Force a full rebuild even if the index appears current.",
                },
            },
        },
    },
    "repo.audit_log": {
        "name": "repo.audit_log",
        "description": (
            "Read sanitized audit log entries for all tool calls made in this session. "
            "Useful for diagnostics and verifying what was called and whether it succeeded."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "since": {
                    "type": "string",
                    "description": "ISO timestamp — return only events after this time.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entries to return.",
                },
            },
        },
    },
}
