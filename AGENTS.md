# AGENTS.md

This file is the operational guide for AI coding agents (Codex, Codex CLI, Cursor agents, etc.) working in this repository.

This project implements a **local-first, deterministic MCP server** that allows AI clients to **interrogate a single code repository** in a safe, auditable, and structured way.
The server exposes tools for indexing, searching, outlining, and context bundling — **not** for modifying code.

If anything in this file conflicts with `SPEC.md`, **`SPEC.md` is the source of truth**.

---

## Python environment

This project uses a Python virtual environment located at `.venv/`.

Rules:

* The `.venv/` directory is created and managed by the user.
* Agents **must not** create, modify, delete, or replace virtual environments.
* All Python commands (tests, linting, formatting, execution) **must** be run using the `.venv/` environment.
* If the environment is not active or unavailable, agents must **stop and ask for guidance** rather than guessing.

---

## 0) Decision hierarchy (important)

When guidance conflicts, follow this order:

1. `SPEC.md` (authoritative behavior and intent)
2. User-facing docs (`README.md`, `docs/`)
3. Code + tests (actual behavior)
4. `AGENTS.md` (workflow and guardrails)

`AGENTS.md` exists to help agents succeed — **not** to override product intent.

---

## 0.5) Architectural Decision Records (ADRs)

This project uses **Architectural Decision Records (ADRs)** to document important design and architectural decisions.

ADRs capture **why** a decision was made — not how the code works.

### ADR rules

* ADRs live in `docs/adr/`
* ADRs are short, focused, and written in plain language
* Not every change needs an ADR

### When an ADR is required

Create or update an ADR when a change:

* affects MCP tool behavior or schemas
* impacts repo sandboxing or security boundaries
* introduces, removes, or replaces a dependency
* changes determinism guarantees
* alters indexing, chunking, or bundling strategies
* affects extensibility (adapters, plugins, future LLM hooks)

### How agents should use ADRs

* Read relevant ADRs **before** proposing changes
* Do not silently violate an accepted ADR
* If an ADR no longer fits, propose a **new ADR** rather than bypassing it

---

## 1) Project overview

* **Name:** Repo Interrogator
* **Primary language:** Python
* **Minimum runtime:** Python 3.11+
* **Developer environment:** Python 3.12+ (Windows + WSL friendly)
* **Packaging:** pip / editable installs
* **Transport:** MCP over STDIO only (v1)
* **Primary consumers:** AI agents (Codex VS Code, Codex CLI, other MCP-capable agents)

This repository is **not** a CLI application and **not** a code-modifying agent.

---

## 2) Agent mission

Agents should:

* Implement features **exactly** as specified in `SPEC.md`.
* Preserve determinism, auditability, and safety at all times.
* Favor clarity and correctness over cleverness.
* Keep the server **passive and interrogative**, never agentic.

Agents must:

* Ask for clarification when ambiguity is **high-impact**.
* Keep changes tightly scoped to the task at hand.
* Avoid “helpful” expansions (LLM calls, heuristics, automation) unless explicitly requested.

---

## 3) Non-negotiable constraints

### Determinism

* The server **must not call LLMs** in v1.
* All indexing, searching, outlining, and bundling logic must be deterministic.
* Outputs must be stable across runs given the same repo state and inputs.

### Dependencies

* **Do not add new dependencies** without prior discussion and approval.
* Any proposed dependency must include:

  * license
  * why the standard library is insufficient
  * security and maintenance considerations
* Prefer the standard library wherever reasonable.

### Tests

* **No network calls in tests** (direct or indirect).
* Tests must be deterministic and self-contained.
* Filesystem tests must use temporary directories.

### Security & logging

* Logging must be structured and configurable.
* Logs are intended to be **human-inspectable diagnostics**.
* Never log:

  * environment variable values
  * credentials, tokens, keys
  * full file contents
* File paths and line ranges are acceptable.

---

## 4) Repo sandboxing (must not drift)

* All file access must be scoped to `repo_root`.
* Path traversal (`..`), symlink escape, and absolute-path access outside the repo **must be blocked**.
* Sensitive files must be blocked according to `SPEC.md`.

If a read is blocked:

* Return an explicit reason.
* Never partially leak content.
* Prefer blocking over redaction.

---

## 5) Determinism & ordering

* Output ordering must be **explicit and stable**.
* File and symbol ordering must not rely on OS enumeration order.
* Platform differences (Windows vs POSIX paths) must be handled intentionally.
* Any nondeterminism must be:

  * documented, and
  * guarded behind an explicit opt-in (not present in v1).

---

## 6) Language adapters & extensibility

* Language-specific behavior lives in **adapters**.
* Python adapter is first-class in v1.
* Other languages default to lexical search + file reading.
* Adapter interfaces must be clean, minimal, and documented.

Agents must **not** bake Python assumptions into core logic outside the adapter layer.

---

## 7) Definition of done

A task is considered complete when:

* The objective is implemented and functional.
* Behavior matches `SPEC.md`.
* Tests are written for core logic.
* All formatting, linting, and tests pass.
* No safety or determinism guarantees are weakened.

---

## 8) Tooling (authoritative)

### Formatting (replace Black)

**Use Ruff for formatting.**

```bash
python -m ruff format .
```

Rationale:

* More consistent in agent environments
* Faster
* Fewer hangs than Black
* Single tool for lint + format

### Linting

```bash
python -m ruff check .
```

### Type checking

```bash
python -m mypy src
```

### Tests

```bash
python -m pytest
```

Coverage (when enabled):

```bash
python -m pytest --cov
```

Agents must **not** reintroduce Black or Black-specific configuration.

---

## 9) Expected repository structure

Unless explicitly approved otherwise, default to:

```
repo_mcp/
├─ server.py            # MCP server entrypoint (STDIO)
├─ tools/               # MCP tool implementations
├─ index/               # indexing + search
├─ adapters/            # language adapters (python, future)
├─ bundler/             # deterministic context bundler
├─ security/            # sandbox, path checks, denylist
├─ logging/             # audit + structured logging
tests/
docs/
  └─ adr/
pyproject.toml
SPEC.md
AGENTS.md
```

Structural deviations require discussion.

---

## 10) MCP-specific rules

* Tool schemas are **part of the API contract**.
* Do not rename tools, inputs, or outputs without approval.
* Tool responses must be:

  * structured
  * self-describing
  * auditable
* Errors must be explicit and actionable.

---

## 11) Documentation standards

* Public functions, adapters, and tools require docstrings.
* Type hints are expected throughout core logic.
* Update documentation when:

  * behavior changes
  * tool schemas change
  * limits or defaults change

---

## 12) Performance posture

* Correctness and safety > performance.
* Avoid premature optimization.
* Incremental indexing is preferred over full rebuilds.
* Never read more file content than necessary.

---

## 13) Agent communication expectations

For each task or PR, include:

* what changed
* why it changed
* how to test it
* any safety or determinism considerations
* known limitations or follow-ups

---

## 14) When to ask the human

Ask for clarification when:

* behavior impacts security or sandboxing
* determinism could be weakened
* adding dependencies
* expanding scope beyond `SPEC.md`
* introducing heuristics that may affect output stability

If ambiguity is **low-impact**, choose the simplest reasonable behavior and **document it**.

---

## 15) References

* `SPEC.md` — authoritative specification
* `docs/adr/` — architectural rationale
