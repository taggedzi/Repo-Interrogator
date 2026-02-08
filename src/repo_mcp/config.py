"""Configuration loading and deterministic merge order."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from repo_mcp.security import SecurityLimits

DEFAULT_INCLUDE_EXTENSIONS = (
    ".py",
    ".md",
    ".rst",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
)
DEFAULT_EXCLUDE_GLOBS = ("**/.git/**", "**/__pycache__/**", "**/.venv/**")


@dataclass(slots=True, frozen=True)
class IndexConfig:
    """Deterministic indexing settings."""

    include_extensions: tuple[str, ...]
    exclude_globs: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class AdaptersConfig:
    """Adapter feature toggles."""

    python_enabled: bool


@dataclass(slots=True, frozen=True)
class ServerConfig:
    """Fully merged server configuration."""

    repo_root: Path
    data_dir: Path
    limits: SecurityLimits
    index: IndexConfig
    adapters: AdaptersConfig

    def to_public_dict(self) -> dict[str, object]:
        """Return serializable config snapshot for tool responses."""
        return {
            "repo_root": str(self.repo_root),
            "data_dir": str(self.data_dir),
            "limits": {
                "max_file_bytes": self.limits.max_file_bytes,
                "max_open_lines": self.limits.max_open_lines,
                "max_total_bytes_per_response": self.limits.max_total_bytes_per_response,
                "max_search_hits": self.limits.max_search_hits,
            },
            "index": {
                "include_extensions": list(self.index.include_extensions),
                "exclude_globs": list(self.index.exclude_globs),
            },
            "adapters": {
                "python_enabled": self.adapters.python_enabled,
            },
        }


@dataclass(slots=True, frozen=True)
class CliOverrides:
    """Optional startup overrides applied at highest precedence."""

    data_dir: Path | None = None
    max_file_bytes: int | None = None
    max_open_lines: int | None = None
    max_total_bytes_per_response: int | None = None
    max_search_hits: int | None = None
    python_enabled: bool | None = None


def default_config(repo_root: Path) -> ServerConfig:
    """Build default config for a given repository root."""
    resolved_root = repo_root.resolve()
    return ServerConfig(
        repo_root=resolved_root,
        data_dir=resolved_root / ".repo_mcp",
        limits=SecurityLimits(),
        index=IndexConfig(
            include_extensions=DEFAULT_INCLUDE_EXTENSIONS,
            exclude_globs=DEFAULT_EXCLUDE_GLOBS,
        ),
        adapters=AdaptersConfig(python_enabled=True),
    )


def load_repo_config_file(repo_root: Path) -> dict[str, object]:
    """Load optional repo_mcp.toml from repo root."""
    config_path = repo_root / "repo_mcp.toml"
    if not config_path.exists():
        return {}
    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("repo_mcp.toml must contain a top-level table.")
    return payload


def _get_table(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Config section '{key}' must be a table.")
    return value


def _tuple_of_strings(value: object, section: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"Config field '{section}.{field}' must be a list of strings.")
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"Config field '{section}.{field}' must contain only strings.")
        output.append(item)
    return tuple(output)


def merge_config(
    base: ServerConfig, repo_payload: dict[str, object], overrides: CliOverrides
) -> ServerConfig:
    """Merge defaults, repo config, then CLI/startup overrides."""
    limits_payload = _get_table(repo_payload, "limits")
    index_payload = _get_table(repo_payload, "index")
    adapters_payload = _get_table(repo_payload, "adapters")

    max_file_bytes = _optional_positive_int(
        limits_payload.get("max_file_bytes"),
        "limits.max_file_bytes",
        base.limits.max_file_bytes,
    )
    max_open_lines = _optional_positive_int(
        limits_payload.get("max_open_lines"),
        "limits.max_open_lines",
        base.limits.max_open_lines,
    )
    max_total_bytes_per_response = _optional_positive_int(
        limits_payload.get("max_total_bytes_per_response"),
        "limits.max_total_bytes_per_response",
        base.limits.max_total_bytes_per_response,
    )
    max_search_hits = _optional_positive_int(
        limits_payload.get("max_search_hits"),
        "limits.max_search_hits",
        base.limits.max_search_hits,
    )

    include_extensions = base.index.include_extensions
    if "include_extensions" in index_payload:
        include_extensions = _tuple_of_strings(
            index_payload["include_extensions"], "index", "include_extensions"
        )
    exclude_globs = base.index.exclude_globs
    if "exclude_globs" in index_payload:
        exclude_globs = _tuple_of_strings(index_payload["exclude_globs"], "index", "exclude_globs")

    python_enabled = base.adapters.python_enabled
    if "python_enabled" in adapters_payload:
        raw_python_enabled = adapters_payload["python_enabled"]
        if not isinstance(raw_python_enabled, bool):
            raise ValueError("Config field 'adapters.python_enabled' must be a boolean.")
        python_enabled = raw_python_enabled

    merged = ServerConfig(
        repo_root=base.repo_root,
        data_dir=base.data_dir,
        limits=SecurityLimits(
            max_file_bytes=max_file_bytes,
            max_open_lines=max_open_lines,
            max_total_bytes_per_response=max_total_bytes_per_response,
            max_search_hits=max_search_hits,
        ),
        index=IndexConfig(
            include_extensions=include_extensions,
            exclude_globs=exclude_globs,
        ),
        adapters=AdaptersConfig(python_enabled=python_enabled),
    )
    return apply_cli_overrides(merged, overrides)


def apply_cli_overrides(config: ServerConfig, overrides: CliOverrides) -> ServerConfig:
    """Apply startup overrides at highest precedence."""
    limits = SecurityLimits(
        max_file_bytes=overrides.max_file_bytes or config.limits.max_file_bytes,
        max_open_lines=overrides.max_open_lines or config.limits.max_open_lines,
        max_total_bytes_per_response=(
            overrides.max_total_bytes_per_response or config.limits.max_total_bytes_per_response
        ),
        max_search_hits=overrides.max_search_hits or config.limits.max_search_hits,
    )
    adapters = AdaptersConfig(
        python_enabled=(
            overrides.python_enabled
            if overrides.python_enabled is not None
            else config.adapters.python_enabled
        )
    )
    data_dir = overrides.data_dir or config.data_dir
    return ServerConfig(
        repo_root=config.repo_root,
        data_dir=data_dir.resolve(),
        limits=limits,
        index=config.index,
        adapters=adapters,
    )


def load_effective_config(repo_root: Path, overrides: CliOverrides | None = None) -> ServerConfig:
    """Load effective config using merge order defaults -> repo config -> overrides."""
    resolved_root = repo_root.resolve()
    base = default_config(resolved_root)
    payload = load_repo_config_file(resolved_root)
    return merge_config(base, payload, overrides or CliOverrides())


def _optional_positive_int(value: object, name: str, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"Config field '{name}' must be a positive integer.")
    return value
