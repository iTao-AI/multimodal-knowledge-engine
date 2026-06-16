# MCP Agent Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a local stdio MCP server that lets Agents ingest supported files, inspect Runs, and
search active Evidence through the existing `KnowledgeEngine`.

**Architecture:** Keep the MCP SDK at the interface boundary. Add a pure `mcp_contract` module
that wraps `KnowledgeEngine` and is easy to unit test, then add a thin `FastMCP` server module and
wire `mke mcp --allowed-root <path>` through the existing CLI. The server uses one configured
SQLite database and one allowed input root; it does not implement Ask, HTTP, workspace UI, model
calls, or broad file access.

**Tech Stack:** Python 3.12/3.13, `mcp>=1.12.4,<2`, pytest, pyright strict mode, Ruff, SQLite.

---

## File Structure

- Modify `pyproject.toml`: add the official MCP Python SDK as a runtime dependency.
- Create `src/mke/interfaces/__init__.py`: package marker for interface adapters.
- Create `src/mke/interfaces/mcp_contract.py`: pure tool-contract functions and path-safety
  helpers. This module owns stable MCP payload shapes and opens/closes `KnowledgeEngine` per call.
- Create `src/mke/interfaces/mcp_server.py`: thin `FastMCP` adapter that exposes the contract
  functions via `@mcp.tool()`.
- Modify `src/mke/cli.py`: add `mke mcp --allowed-root <path>` and delegate to `run_mcp_server`.
- Create `tests/interfaces/test_mcp_contract.py`: unit tests for MCP payloads, Evidence search,
  path safety, and error contracts.
- Create `tests/interfaces/test_cli_mcp.py`: CLI parser test that monkeypatches the server runner
  and avoids starting stdio in tests.
- Modify `docs/reference/contracts.md`: mark MCP partially implemented and keep `ask_library`
  planned.
- Modify `docs/reference/cli.md`: document `mke mcp`.
- Create `docs/how-to/use-mke-mcp.md`: show local stdio server usage and tool boundaries.
- Modify `docs/README.md`: link the MCP how-to and this plan.
- Modify `README.md` and `README_CN.md`: mention MCP as the first Agent-facing interface only
  after tests pass.

## Task 1: Add MCP Dependency And Interface Package

**Files:**
- Modify: `pyproject.toml`
- Create: `src/mke/interfaces/__init__.py`

- [x] **Step 1: Add the MCP SDK runtime dependency**

Modify `[project]` dependencies in `pyproject.toml` to:

```toml
dependencies = [
  "mcp>=1.12.4,<2",
]
```

- [x] **Step 2: Create the interface package marker**

Create `src/mke/interfaces/__init__.py`:

```python
"""Interface adapters for CLI-adjacent public contracts."""
```

- [x] **Step 3: Sync dependencies**

Run:

```bash
uv sync --locked
```

Expected: `uv.lock` updates and the environment installs the `mcp` package.

- [x] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/mke/interfaces/__init__.py
git commit -m "chore: add mcp interface dependency"
```

## Task 2: Implement Pure MCP Contract Functions

**Files:**
- Create: `src/mke/interfaces/mcp_contract.py`
- Test: `tests/interfaces/test_mcp_contract.py`

- [x] **Step 1: Write failing MCP contract tests**

Create `tests/interfaces/test_mcp_contract.py`:

```python
from pathlib import Path

from mke.interfaces.mcp_contract import (
    McpRuntimeConfig,
    get_run,
    ingest_file,
    list_libraries,
    search_library,
)
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def _config(tmp_path: Path, allowed_root: Path) -> McpRuntimeConfig:
    return McpRuntimeConfig(db_path=tmp_path / "mke.sqlite", allowed_root=allowed_root)


def test_list_libraries_returns_implicit_local_library() -> None:
    result = list_libraries()

    assert result == {
        "libraries": [
            {
                "library_id": "local",
                "name": "Local Library",
                "status": "implicit",
                "active_publication_scope": "source",
            }
        ]
    }


def test_ingest_file_publishes_pdf_and_search_returns_page_evidence(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    ingest = ingest_file(config, "text-layer.pdf")
    assert ingest["ok"] is True
    assert ingest["run_state"] == "published"
    assert ingest["evidence_count"] == 2
    assert ingest["media_type"] == "application/pdf"
    assert ingest["active_publication_impact"] == "changed"

    search = search_library(config, "publication active")
    assert search["ok"] is True
    assert search["query"] == "publication active"
    result = search["results"][0]
    assert result["locator"] == {"kind": "page", "start": 2, "end": 2}
    assert "Publication search returns only active page two." in result["text"]


def test_ingest_file_publishes_video_and_search_returns_timestamp_evidence(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, VIDEO_FIXTURES)

    ingest = ingest_file(config, "short-audio.mp4")
    assert ingest["ok"] is True
    assert ingest["run_state"] == "published"
    assert ingest["evidence_count"] == 2
    assert ingest["media_type"] == "video/mp4"

    search = search_library(config, "timestamp proof", limit=2)
    assert search["ok"] is True
    result = search["results"][0]
    assert result["locator"] == {"kind": "timestamp_ms", "start": 1200, "end": 2200}
    assert "Active publication search finds spoken timestamp proof." in result["text"]


def test_ingest_file_rejects_paths_outside_allowed_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside.pdf"
    outside.write_bytes((PDF_FIXTURES / "text-layer.pdf").read_bytes())
    config = _config(tmp_path, PDF_FIXTURES)

    result = ingest_file(config, str(outside))

    assert result == {
        "ok": False,
        "problem": "input_path_rejected",
        "cause": "input path must be under allowed root",
        "active_publication_impact": "unchanged",
        "next_step": "choose_file_under_allowed_root",
    }


def test_ingest_file_rejects_unsupported_media_type(tmp_path: Path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("not supported")
    config = _config(tmp_path, tmp_path)

    result = ingest_file(config, "note.txt")

    assert result == {
        "ok": False,
        "problem": "unsupported_media_type",
        "cause": "supported suffixes are .pdf and .mp4",
        "active_publication_impact": "unchanged",
        "next_step": "choose_supported_file",
    }


def test_get_run_returns_state_and_events(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest = ingest_file(config, "text-layer.pdf")

    result = get_run(config, str(ingest["run_id"]))

    assert result["ok"] is True
    assert result["run"]["run_id"] == ingest["run_id"]
    assert result["run"]["state"] == "published"
    assert result["run"]["retry_of_run_id"] is None
    assert [event["event"] for event in result["events"]] == [
        "run_created",
        "run_started",
        "candidate_validated",
        "publication_activated",
    ]


def test_get_run_unknown_id_returns_stable_error(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = get_run(config, "run_missing")

    assert result == {
        "ok": False,
        "problem": "run_not_found",
        "cause": "unknown run: run_missing",
        "active_publication_impact": "unchanged",
        "next_step": "check_run_id",
    }


def test_search_library_rejects_empty_query(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = search_library(config, "   ")

    assert result == {
        "ok": False,
        "problem": "invalid_query",
        "cause": "query must not be empty",
        "active_publication_impact": "unchanged",
        "next_step": "provide_non_empty_query",
    }


def test_search_library_rejects_invalid_limit(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = search_library(config, "publication", limit=0)

    assert result == {
        "ok": False,
        "problem": "invalid_query",
        "cause": "limit must be between 1 and 20",
        "active_publication_impact": "unchanged",
        "next_step": "choose_limit_between_1_and_20",
    }
```

- [x] **Step 2: Run the failing tests**

Run:

```bash
uv run pytest tests/interfaces/test_mcp_contract.py -q
```

Expected: FAIL because `mke.interfaces.mcp_contract` does not exist.

- [x] **Step 3: Implement the MCP contract module**

Create `src/mke/interfaces/mcp_contract.py`:

```python
"""Pure MCP tool contracts backed by the project-owned KnowledgeEngine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mke.application import KnowledgeEngine, PdfIngestError, VideoIngestError

_SUPPORTED_SUFFIX_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
}


@dataclass(frozen=True)
class McpRuntimeConfig:
    db_path: Path
    allowed_root: Path


def list_libraries() -> dict[str, Any]:
    return {
        "libraries": [
            {
                "library_id": "local",
                "name": "Local Library",
                "status": "implicit",
                "active_publication_scope": "source",
            }
        ]
    }


def ingest_file(config: McpRuntimeConfig, path: str) -> dict[str, Any]:
    try:
        input_path = _resolve_allowed_file(config, path)
    except ValueError as error:
        return _failure(
            "input_path_rejected",
            str(error),
            "choose_file_under_allowed_root",
        )
    suffix = input_path.suffix.lower()
    media_type = _SUPPORTED_SUFFIX_MEDIA_TYPES.get(suffix)
    if media_type is None:
        return _failure(
            "unsupported_media_type",
            "supported suffixes are .pdf and .mp4",
            "choose_supported_file",
        )

    engine = KnowledgeEngine(config.db_path)
    try:
        try:
            if suffix == ".mp4":
                result = engine.ingest_video(input_path)
            else:
                result = engine.ingest_pdf(input_path)
        except PdfIngestError as error:
            return _failure("pdf_ingest_failed", str(error), "fix_input_or_retry")
        except VideoIngestError as error:
            return _failure("video_ingest_failed", str(error), "fix_input_or_retry")
        return {
            "ok": True,
            "run_id": result.run_id,
            "run_state": result.run_state.value,
            "evidence_count": result.evidence_count,
            "media_type": media_type,
            "active_publication_impact": "changed"
            if result.run_state.value == "published"
            else "unchanged",
        }
    finally:
        engine.close()


def get_run(config: McpRuntimeConfig, run_id: str) -> dict[str, Any]:
    engine = KnowledgeEngine(config.db_path)
    try:
        try:
            run = engine.get_run(run_id)
        except KeyError:
            return _failure("run_not_found", f"unknown run: {run_id}", "check_run_id")
        events = [
            {"event_index": event.event_index, "event": event.event_type}
            for event in engine.get_run_events(run_id)
        ]
        return {
            "ok": True,
            "run": {
                "run_id": run.run_id,
                "state": run.state.value,
                "source_generation": run.source_generation,
                "retry_of_run_id": run.retry_of_run_id,
            },
            "events": events,
        }
    finally:
        engine.close()


def search_library(config: McpRuntimeConfig, query: str, limit: int = 5) -> dict[str, Any]:
    normalized_query = query.strip()
    if not normalized_query:
        return _failure("invalid_query", "query must not be empty", "provide_non_empty_query")
    if limit < 1 or limit > 20:
        return _failure(
            "invalid_query",
            "limit must be between 1 and 20",
            "choose_limit_between_1_and_20",
        )

    engine = KnowledgeEngine(config.db_path)
    try:
        results = []
        for match in engine.search(normalized_query)[:limit]:
            results.append(
                {
                    "evidence_id": match.evidence_id,
                    "publication_id": match.publication_id,
                    "source_id": match.source_id,
                    "locator": {
                        "kind": match.locator_kind,
                        "start": match.locator_start,
                        "end": match.locator_end,
                    },
                    "text": match.text,
                }
            )
        return {"ok": True, "query": normalized_query, "results": results}
    finally:
        engine.close()


def _resolve_allowed_file(config: McpRuntimeConfig, path: str) -> Path:
    allowed_root = config.allowed_root.resolve()
    requested = Path(path)
    candidate = requested if requested.is_absolute() else allowed_root / requested
    resolved = candidate.resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as error:
        raise ValueError("input path must be under allowed root") from error
    if not resolved.exists():
        raise ValueError("input file does not exist")
    if not resolved.is_file():
        raise ValueError("input path must be a file")
    return resolved


def _failure(problem: str, cause: str, next_step: str) -> dict[str, Any]:
    return {
        "ok": False,
        "problem": problem,
        "cause": cause,
        "active_publication_impact": "unchanged",
        "next_step": next_step,
    }
```

- [x] **Step 4: Run contract tests**

Run:

```bash
uv run pytest tests/interfaces/test_mcp_contract.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/mke/interfaces/mcp_contract.py tests/interfaces/test_mcp_contract.py
git commit -m "feat(mcp): add evidence tool contract layer"
```

## Task 3: Add FastMCP Server Adapter

**Files:**
- Create: `src/mke/interfaces/mcp_server.py`
- Test: `tests/interfaces/test_mcp_server.py`

- [x] **Step 1: Write a server construction test**

Create `tests/interfaces/test_mcp_server.py`:

```python
from pathlib import Path

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server


def test_build_mcp_server_returns_named_server(tmp_path: Path) -> None:
    server = build_mcp_server(
        McpRuntimeConfig(db_path=tmp_path / "mke.sqlite", allowed_root=tmp_path)
    )

    assert server.name == "Multimodal Knowledge Engine"
```

- [x] **Step 2: Run the failing server test**

Run:

```bash
uv run pytest tests/interfaces/test_mcp_server.py -q
```

Expected: FAIL because `mke.interfaces.mcp_server` does not exist.

- [x] **Step 3: Implement the FastMCP adapter**

Create `src/mke/interfaces/mcp_server.py`:

```python
"""MCP stdio server for local Agent access to MKE Evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from mke.interfaces import mcp_contract
from mke.interfaces.mcp_contract import McpRuntimeConfig


def build_mcp_server(config: McpRuntimeConfig) -> FastMCP:
    mcp = FastMCP("Multimodal Knowledge Engine", json_response=True)

    @mcp.tool()
    def list_libraries() -> dict[str, Any]:
        """List available MKE Libraries."""
        return mcp_contract.list_libraries()

    @mcp.tool()
    def ingest_file(path: str) -> dict[str, Any]:
        """Ingest a PDF or short MP4 under the configured allowed root."""
        return mcp_contract.ingest_file(config, path)

    @mcp.tool()
    def get_run(run_id: str) -> dict[str, Any]:
        """Inspect a Run and its append-only events."""
        return mcp_contract.get_run(config, run_id)

    @mcp.tool()
    def search_library(query: str, limit: int = 5) -> dict[str, Any]:
        """Search active Publication Evidence."""
        return mcp_contract.search_library(config, query, limit)

    return mcp


def run_mcp_server(*, db_path: Path, allowed_root: Path) -> int:
    config = McpRuntimeConfig(db_path=db_path, allowed_root=allowed_root)
    build_mcp_server(config).run()
    return 0
```

- [x] **Step 4: Run server tests**

Run:

```bash
uv run pytest tests/interfaces/test_mcp_server.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/mke/interfaces/mcp_server.py tests/interfaces/test_mcp_server.py
git commit -m "feat(mcp): add stdio server adapter"
```

## Task 4: Wire `mke mcp` Into CLI

**Files:**
- Modify: `src/mke/cli.py`
- Test: `tests/interfaces/test_cli_mcp.py`

- [x] **Step 1: Write CLI parser tests**

Create `tests/interfaces/test_cli_mcp.py`:

```python
from pathlib import Path

import mke.cli
from mke.cli import main


def test_cli_mcp_passes_db_and_allowed_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[tuple[Path, Path]] = []
    db_path = tmp_path / "mke.sqlite"
    allowed_root = tmp_path / "materials"
    allowed_root.mkdir()

    def fake_run_mcp_server(*, db_path: Path, allowed_root: Path) -> int:
        calls.append((db_path, allowed_root))
        return 0

    monkeypatch.setattr(mke.cli, "run_mcp_server", fake_run_mcp_server)

    assert main(["--db", str(db_path), "mcp", "--allowed-root", str(allowed_root)]) == 0

    assert calls == [(db_path, allowed_root)]


def test_cli_mcp_allowed_root_defaults_to_current_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[tuple[Path, Path]] = []
    db_path = tmp_path / "mke.sqlite"

    def fake_run_mcp_server(*, db_path: Path, allowed_root: Path) -> int:
        calls.append((db_path, allowed_root))
        return 0

    monkeypatch.setattr(mke.cli, "run_mcp_server", fake_run_mcp_server)
    monkeypatch.chdir(tmp_path)

    assert main(["--db", str(db_path), "mcp"]) == 0

    assert calls == [(db_path, Path.cwd())]
```

- [x] **Step 2: Run the failing CLI tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_mcp.py -q
```

Expected: FAIL because `mke.cli` does not expose `run_mcp_server` or parse `mcp`.

- [x] **Step 3: Modify `src/mke/cli.py` imports**

Add near the existing imports:

```python
from mke.interfaces.mcp_server import run_mcp_server
```

- [x] **Step 4: Add the `mcp` subcommand**

In `main`, after the `demo` parser setup, add:

```python
    mcp = subcommands.add_parser("mcp")
    mcp.add_argument("--allowed-root", type=Path, default=Path.cwd())
```

- [x] **Step 5: Dispatch the `mcp` command before opening `KnowledgeEngine`**

After the existing `if args.command == "demo":` block, add:

```python
    if args.command == "mcp":
        return run_mcp_server(db_path=args.db, allowed_root=args.allowed_root)
```

- [x] **Step 6: Run CLI MCP tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_mcp.py -q
```

Expected: PASS.

- [x] **Step 7: Run existing CLI tests**

Run:

```bash
uv run pytest tests/interfaces -q
```

Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add src/mke/cli.py tests/interfaces/test_cli_mcp.py
git commit -m "feat(cli): expose mcp stdio server command"
```

## Task 5: Update Public Contracts And User Docs

**Files:**
- Modify: `docs/reference/contracts.md`
- Modify: `docs/reference/cli.md`
- Create: `docs/how-to/use-mke-mcp.md`
- Modify: `docs/README.md`
- Modify: `README.md`
- Modify: `README_CN.md`

- [x] **Step 1: Update `docs/reference/contracts.md`**

Change MCP status to:

```markdown
## MCP

Status: partially implemented.

Implemented tools:

```text
list_libraries
ingest_file
get_run
search_library
```

Planned tools:

```text
ask_library
```

The MCP server runs over stdio through `mke mcp --allowed-root <path>`. It reuses the same
`KnowledgeEngine` application service as CLI ingest, Run inspection, and Search. `ingest_file`
only accepts files under the configured allowed root and currently supports `.pdf` and `.mp4`.
`search_library` reads active Publication Evidence only.
```

- [x] **Step 2: Update `docs/reference/cli.md` planned and implemented command sections**

Add under implemented commands:

```markdown
## MCP Server Command

```bash
mke --db <path> mcp --allowed-root <path>
```

- Runs a local stdio MCP server.
- `--allowed-root` defaults to the current working directory.
- `ingest_file` rejects paths outside `--allowed-root`.
- Implemented MCP tools are `list_libraries`, `ingest_file`, `get_run`, and `search_library`.
- `ask_library`, HTTP, and workspace UI remain planned.
```

Remove `mke mcp` from the planned command sentence.

- [x] **Step 3: Add the MCP how-to**

Create `docs/how-to/use-mke-mcp.md`:

```markdown
# Use MKE As A Local MCP Server

Use this guide when an Agent needs local tool access to MKE Evidence.

## Start The Server

```bash
uv sync --locked
uv run mke --db .tmp/mke.sqlite mcp --allowed-root .
```

The server uses stdio. Configure the Agent client to run the command above from the repository
root.

## Available Tools

- `list_libraries`: returns the implicit local library.
- `ingest_file`: ingests a supported `.pdf` or `.mp4` under `--allowed-root`.
- `get_run`: returns Run state and append-only Run events.
- `search_library`: searches active Publication Evidence.

## Example Agent Flow

1. Call `list_libraries`.
2. Call `ingest_file` with `tests/fixtures/pdf/text-layer.pdf`.
3. Call `search_library` with `publication active`.
4. Cite returned Evidence locators.

## Boundaries

- `ask_library` is not implemented yet.
- HTTP and workspace UI are not implemented yet.
- Scanned-PDF OCR, arbitrary videos, real speech-model transcription, and external providers are
  outside this MCP slice.
- The server rejects paths outside `--allowed-root`.
```

- [x] **Step 4: Update `docs/README.md`**

Add a bullet under the current product proof and plan section:

```markdown
- [Use MKE As A Local MCP Server](./how-to/use-mke-mcp.md) explains the first Agent-facing
  stdio interface.
```

- [x] **Step 5: Update README files**

In `README.md`, add one sentence to `Current Status`:

```markdown
The first Agent-facing interface is a local stdio MCP server for ingest, Run inspection, and
active Evidence Search.
```

In `README_CN.md`, add the equivalent:

```markdown
首个 Agent-facing interface 是本地 stdio MCP server，支持 ingest、Run 检查和 active Evidence Search。
```

- [x] **Step 6: Run documentation checks**

Run:

```bash
rg -n "run-local-pdf-proof" README.md README_CN.md docs/reference docs/how-to docs/tutorials docs/README.md || true
rg -n "## MCP|Status:" docs/reference/contracts.md
rg -n "MCP.*not implemented|MCP.*尚未实现" README.md README_CN.md docs/reference docs/how-to docs/tutorials docs/README.md || true
git diff --check
```

Expected:

- `run-local-pdf-proof` has no matches.
- MCP status in `docs/reference/contracts.md` is `partially implemented`.
- Any `MCP.*not implemented` or `MCP.*尚未实现` match is reviewed as a real conflict, not just a nearby non-scope sentence.
- `git diff --check` exits 0.

- [x] **Step 7: Commit**

```bash
git add AGENTS.md README.md README_CN.md docs/README.md docs/how-to/run-local-product-proof.md docs/how-to/use-mke-mcp.md docs/reference/contracts.md docs/reference/cli.md docs/superpowers/plans/2026-06-16-mcp-agent-interface-implementation.md docs/superpowers/reviews/2026-06-16-mcp-agent-interface-autoplan-review.md docs/tutorials/getting-started.md
git commit -m "docs(mcp): document local agent interface"
```

## Task 6: Full Verification And PR Preparation

**Files:**
- No new files expected unless previous verification finds a docs-only correction.

- [x] **Step 1: Run focused tests**

```bash
uv run pytest tests/interfaces/test_mcp_contract.py tests/interfaces/test_mcp_server.py tests/interfaces/test_cli_mcp.py -q
```

Expected: PASS.

- [x] **Step 2: Run full tests**

```bash
uv run pytest -q
```

Expected: PASS.

- [x] **Step 3: Run lint and type checks**

```bash
uv run ruff check .
uv run pyright
```

Expected:

- Ruff reports `All checks passed!`.
- Pyright reports `0 errors, 0 warnings, 0 informations`.

- [x] **Step 4: Build and run the existing product proof**

```bash
uv build
uv run mke demo --verify
```

Expected:

- sdist and wheel build successfully.
- `uv run mke demo --verify` prints `result=passed`.

- [x] **Step 5: Inspect final diff**

```bash
git status --short
git diff --stat main...HEAD
git diff --check main...HEAD
```

Expected:

- Only intentional MCP interface, tests, dependency, and docs files changed.
- No whitespace errors.

- [x] **Step 6: Prepare PR body**

Use this PR body shape:

```markdown
## Summary

MKE now has its first Agent-facing local interface: a stdio MCP server that exposes the existing
Evidence lifecycle without adding Ask, HTTP, workspace UI, model calls, or broad file access.

- Adds `mke --db <path> mcp --allowed-root <path>`.
- Exposes `list_libraries`, `ingest_file`, `get_run`, and `search_library`.
- Enforces allowed-root path safety for file ingestion.
- Updates MCP, CLI, and how-to documentation.

## Completion

- [x] MCP stdio server starts through `mke mcp`.
- [x] MCP tools reuse `KnowledgeEngine` instead of subprocess CLI calls.
- [x] PDF and short-video ingest are available through `ingest_file`.
- [x] Run events and active Publication Search are available to Agents.
- [x] `ask_library`, HTTP, workspace UI, OCR, arbitrary video processing, and real transcription remain out of scope.

## Verification

| Check | Result |
|---|---|
| `uv run pytest -q` | Record the exact pass summary from Task 6 Step 2. |
| `uv run ruff check .` | Record the exact pass summary from Task 6 Step 3. |
| `uv run pyright` | Record the exact pass summary from Task 6 Step 3. |
| `uv build` | Record the exact build summary from Task 6 Step 4. |
| `uv run mke demo --verify` | Record the exact `result=passed` line from Task 6 Step 4. |

## Scope

This PR adds the first MCP interface. It does not add Ask, HTTP, workspace UI, hosted coordination,
external providers, OCR, arbitrary video support, real speech-model transcription, or embedding
retrieval.

## Risk / Impact

- User impact: local Agents can call MKE as a tool server.
- System impact: adds the official MCP Python SDK as a runtime dependency.
- Compatibility impact: existing CLI commands remain unchanged.
- Rollback plan: revert this PR to remove the MCP command and dependency.

## Documentation impact

Updates public contracts, CLI reference, MCP how-to, docs index, and README files.
```

Do not open the PR until every Verification row has the actual command result from this branch.

Completed verification:

| Check | Result |
|---|---|
| `uv run pytest tests/interfaces/test_mcp_contract.py tests/interfaces/test_mcp_server.py tests/interfaces/test_cli_mcp.py -q` | `18 passed in 0.19s` |
| `uv run pytest -q` | `91 passed in 0.31s` |
| `uv run ruff check .` | `All checks passed!` |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `uv build` | Built `dist/multimodal_knowledge_engine-0.0.0.tar.gz` and `dist/multimodal_knowledge_engine-0.0.0-py3-none-any.whl` |
| `uv run mke demo --verify` | `result=passed duration_ms=5` |
