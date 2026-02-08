"""STDIO MCP server entrypoint."""

from __future__ import annotations

import argparse


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for server startup configuration."""
    parser = argparse.ArgumentParser(prog="repo-mcp")
    parser.add_argument("--repo-root", required=False, default=".")
    parser.add_argument("--data-dir", required=False, default=None)
    return parser


def main() -> int:
    """Entrypoint for the repo interrogator server process."""
    parser = build_arg_parser()
    parser.parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
