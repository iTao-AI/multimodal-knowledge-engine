# Evidence-Only Ask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic evidence-only Ask through `KnowledgeEngine.ask()`, MCP `ask_library`, and CLI `mke ask`.

**Architecture:** Define an `AskResult` DTO in the project-owned domain boundary and implement `KnowledgeEngine.ask()` as a thin active-only Search composition service. The MCP contract layer maps `AskResult` to stable JSON payloads using a shared `SearchResult` evidence mapper that is reused by both `search_library` and `ask_library`.

**Tech Stack:** Python 3.12/3.13, SQLite FTS5, pytest, Ruff, Pyright strict mode, MCP Python SDK.

---

## Review Findings Covered

This plan incorporates the pre-implementation review in
`docs/superpowers/reviews/2026-06-16-evidence-only-ask-autoplan-review.md`.

| Finding | Handling |
|---|---|
| `AskResult` DTO undefined | Task 1 defines `AskResult` in `src/mke/domain/__init__.py`. |
| Evidence dict mapping duplication | Task 2 extracts `_evidence_from_search_result()` in `mcp_contract.py`. |
| Summary wording overclaims semantic relevance | Task 1 uses `matched the search terms`. |
| CJK-only questions silently become empty FTS queries | Task 1 rejects no-searchable-token questions with `invalid_question`. |
| Missing max question length | Task 1 enforces 1000 characters after trimming. |
| `insufficient_evidence` root causes merged | Task 1 documents and tests the intentional C2 behavior. |
| Missing MCP insufficient Evidence test | Task 2 adds MCP contract coverage. |
| Missing Ask correlation id | Task 1 adds `ask_id` to `AskResult`; Task 2 exposes it. |
| Summary contradiction | Task 1 keeps the summary deterministic and count-only. |

## File Structure

- Modify `src/mke/domain/__init__.py`: add `AskResult`.
- Modify `src/mke/application/__init__.py`: add `AskValidationError`, Ask constants, and `KnowledgeEngine.ask()`.
- Create `tests/application/test_ask.py`: application tests for PDF, video, no-match, empty, overlong, no-token, and limit validation.
- Modify `src/mke/interfaces/mcp_contract.py`: add `ask_library()` and `_evidence_from_search_result()`, then reuse the mapper in `search_library()`.
- Modify `tests/interfaces/test_mcp_contract.py`: add Ask contract tests and mapper consistency checks.
- Modify `src/mke/interfaces/mcp_server.py`: expose `ask_library` as a FastMCP tool.
- Modify `src/mke/cli.py`: add `mke ask <question>` and reusable error printing for Ask validation failures.
- Create `tests/interfaces/test_cli_ask.py`: deterministic CLI Ask tests.
- Modify `docs/reference/contracts.md`: mark MCP `ask_library` and CLI `mke ask` implemented in C2 and document payload shape.
- Modify `docs/reference/cli.md`: document `mke ask`.
- Modify `docs/how-to/use-mke-mcp.md`: add `ask_library` usage.
- Modify `README.md` and `README_CN.md`: describe evidence-only Ask and keep non-generative boundary explicit.
- Modify `docs/README.md`: link this plan and the C2 review.

## Task 1: Add Ask DTO And Application Service

**Files:**
- Modify: `src/mke/domain/__init__.py`
- Modify: `src/mke/application/__init__.py`
- Create: `tests/application/test_ask.py`

- [x] **Step 1: Write failing application tests**

Create `tests/application/test_ask.py`:

```python
from pathlib import Path

import pytest

from mke.application import AskValidationError, KnowledgeEngine
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def test_ask_returns_pdf_page_evidence_packet(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    result = engine.ask("publication active")

    assert result.ask_id.startswith("ask_")
    assert result.question == "publication active"
    assert result.answer_status == "evidence_found"
    assert result.summary == "1 active Evidence item matched the search terms."
    assert result.limitations == [
        "No model-generated answer is produced in this slice.",
        "The summary is deterministic and only reports matched Evidence count.",
    ]
    assert len(result.evidence) == 1
    match = result.evidence[0]
    assert match.locator_kind == "page"
    assert match.locator_start == 2
    assert match.locator_end == 2
    assert "Publication search returns only active page two." in match.text


def test_ask_returns_video_timestamp_evidence_packet(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    result = engine.ask("timestamp proof")

    assert result.answer_status == "evidence_found"
    assert result.summary == "1 active Evidence item matched the search terms."
    match = result.evidence[0]
    assert match.locator_kind == "timestamp_ms"
    assert match.locator_start == 1200
    assert match.locator_end == 2200
    assert "Active publication search finds spoken timestamp proof." in match.text


def test_ask_returns_insufficient_evidence_for_no_match(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    result = engine.ask("audio diarization")

    assert result.ask_id.startswith("ask_")
    assert result.question == "audio diarization"
    assert result.answer_status == "insufficient_evidence"
    assert result.summary == "No active Evidence matched the search terms."
    assert result.evidence == []
    assert result.limitations == [
        "No answer is produced because no active Evidence matched the search terms.",
        "No model-generated answer is produced in this slice.",
    ]


def test_ask_rejects_empty_question(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AskValidationError) as error:
        engine.ask("   ")

    assert error.value.problem == "invalid_question"
    assert error.value.cause == "question must not be empty"
    assert error.value.next_step == "provide_non_empty_question"


def test_ask_rejects_overlong_question(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AskValidationError) as error:
        engine.ask("x" * 1001)

    assert error.value.problem == "invalid_question"
    assert error.value.cause == "question must be 1000 characters or fewer"
    assert error.value.next_step == "shorten_question"


@pytest.mark.parametrize("question", ["发布时间？", "？！？", "... ---"])
def test_ask_rejects_question_without_searchable_ascii_token(
    tmp_path: Path, question: str
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AskValidationError) as error:
        engine.ask(question)

    assert error.value.problem == "invalid_question"
    assert error.value.cause == "question must contain at least one searchable ASCII token"
    assert error.value.next_step == "provide_searchable_question"


@pytest.mark.parametrize("limit", [0, 21])
def test_ask_rejects_invalid_limit(tmp_path: Path, limit: int) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AskValidationError) as error:
        engine.ask("publication", limit=limit)

    assert error.value.problem == "invalid_query"
    assert error.value.cause == "limit must be between 1 and 20"
    assert error.value.next_step == "choose_limit_between_1_and_20"
```

- [x] **Step 2: Run failing application tests**

Run:

```bash
uv run pytest tests/application/test_ask.py -q
```

Expected: FAIL because `AskValidationError`, `AskResult`, and `KnowledgeEngine.ask()` do not exist.

- [x] **Step 3: Add the `AskResult` DTO**

Modify `src/mke/domain/__init__.py` after `SearchResult`:

```python
@dataclass(frozen=True)
class AskResult:
    ask_id: str
    question: str
    answer_status: str
    summary: str
    evidence: list[SearchResult]
    limitations: list[str]
```

- [x] **Step 4: Add Ask validation and service code**

Modify imports in `src/mke/application/__init__.py`:

```python
import re
from uuid import uuid4
```

Extend the domain import list:

```python
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    REQUIRED_VIDEO_STAGES,
    VIDEO_TRANSCRIPT_FINGERPRINT,
    ActivationResult,
    AskResult,
    CandidateEvidence,
    FailurePoint,
    IngestResult,
    ManifestValidationError,
    RunEvent,
    RunManifest,
    RunRecord,
    RunState,
    SearchResult,
    SourceRecord,
)
```

Add constants near `_SHA256_CHUNK_BYTES`:

```python
_SHA256_CHUNK_BYTES = 1024 * 1024
_DEFAULT_ASK_LIMIT = 5
_MIN_ASK_LIMIT = 1
_MAX_ASK_LIMIT = 20
_MAX_ASK_QUESTION_CHARS = 1000
_SEARCHABLE_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_MODEL_FREE_LIMITATION = "No model-generated answer is produced in this slice."
_COUNT_ONLY_LIMITATION = (
    "The summary is deterministic and only reports matched Evidence count."
)
```

Add `AskValidationError` after `VideoIngestError`:

```python
class AskValidationError(ValueError):
    """Raised when an Ask request cannot be evaluated safely."""

    def __init__(self, problem: str, cause: str, next_step: str) -> None:
        super().__init__(cause)
        self.problem = problem
        self.cause = cause
        self.next_step = next_step
```

Add `KnowledgeEngine.ask()` after `search()`:

```python
    def ask(self, question: str, limit: int = _DEFAULT_ASK_LIMIT) -> AskResult:
        normalized_question = _normalize_ask_question(question)
        if limit < _MIN_ASK_LIMIT or limit > _MAX_ASK_LIMIT:
            raise AskValidationError(
                "invalid_query",
                f"limit must be between {_MIN_ASK_LIMIT} and {_MAX_ASK_LIMIT}",
                "choose_limit_between_1_and_20",
            )
        evidence = self.search(normalized_question, limit=limit)
        if evidence:
            return AskResult(
                ask_id=f"ask_{uuid4().hex}",
                question=normalized_question,
                answer_status="evidence_found",
                summary=_matched_summary(len(evidence)),
                evidence=evidence,
                limitations=[_MODEL_FREE_LIMITATION, _COUNT_ONLY_LIMITATION],
            )
        return AskResult(
            ask_id=f"ask_{uuid4().hex}",
            question=normalized_question,
            answer_status="insufficient_evidence",
            summary="No active Evidence matched the search terms.",
            evidence=[],
            limitations=[
                "No answer is produced because no active Evidence matched the search terms.",
                _MODEL_FREE_LIMITATION,
            ],
        )
```

Add module helpers before `_sha256_file()`:

```python
def _normalize_ask_question(question: str) -> str:
    normalized_question = question.strip()
    if not normalized_question:
        raise AskValidationError(
            "invalid_question",
            "question must not be empty",
            "provide_non_empty_question",
        )
    if len(normalized_question) > _MAX_ASK_QUESTION_CHARS:
        raise AskValidationError(
            "invalid_question",
            f"question must be {_MAX_ASK_QUESTION_CHARS} characters or fewer",
            "shorten_question",
        )
    if _SEARCHABLE_TOKEN_RE.search(normalized_question) is None:
        raise AskValidationError(
            "invalid_question",
            "question must contain at least one searchable ASCII token",
            "provide_searchable_question",
        )
    return normalized_question


def _matched_summary(evidence_count: int) -> str:
    noun = "item" if evidence_count == 1 else "items"
    verb = "matched" if evidence_count != 1 else "matched"
    return f"{evidence_count} active Evidence {noun} {verb} the search terms."
```

- [x] **Step 5: Run application tests**

Run:

```bash
uv run pytest tests/application/test_ask.py -q
```

Expected: PASS.

- [x] **Step 6: Commit application Ask service**

Run:

```bash
git add src/mke/domain/__init__.py src/mke/application/__init__.py tests/application/test_ask.py
git commit -m "feat(ask): add evidence-only ask service"
```

## Task 2: Add MCP Contract `ask_library`

**Files:**
- Modify: `src/mke/interfaces/mcp_contract.py`
- Modify: `tests/interfaces/test_mcp_contract.py`

- [ ] **Step 1: Write failing MCP contract tests**

Modify imports in `tests/interfaces/test_mcp_contract.py`:

```python
from mke.interfaces.mcp_contract import (
    McpRuntimeConfig,
    ask_library,
    get_run,
    ingest_file,
    list_libraries,
    search_library,
)
```

Append these tests:

```python
def test_ask_library_returns_pdf_evidence_packet(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest_file(config, "text-layer.pdf")

    result = ask_library(config, "publication active")

    assert result["ok"] is True
    assert str(result["ask_id"]).startswith("ask_")
    assert result["question"] == "publication active"
    assert result["answer_status"] == "evidence_found"
    assert result["summary"] == "1 active Evidence item matched the search terms."
    assert result["limitations"] == [
        "No model-generated answer is produced in this slice.",
        "The summary is deterministic and only reports matched Evidence count.",
    ]
    evidence = result["evidence"][0]
    assert evidence["locator"] == {"kind": "page", "start": 2, "end": 2}
    assert "Publication search returns only active page two." in evidence["text"]


def test_ask_library_returns_video_evidence_packet(tmp_path: Path) -> None:
    config = _config(tmp_path, VIDEO_FIXTURES)
    ingest_file(config, "short-audio.mp4")

    result = ask_library(config, "timestamp proof")

    assert result["ok"] is True
    assert result["answer_status"] == "evidence_found"
    evidence = result["evidence"][0]
    assert evidence["locator"] == {"kind": "timestamp_ms", "start": 1200, "end": 2200}
    assert "Active publication search finds spoken timestamp proof." in evidence["text"]


def test_ask_library_returns_insufficient_evidence(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest_file(config, "text-layer.pdf")

    result = ask_library(config, "audio diarization")

    assert result == {
        "ok": True,
        "ask_id": result["ask_id"],
        "question": "audio diarization",
        "answer_status": "insufficient_evidence",
        "summary": "No active Evidence matched the search terms.",
        "evidence": [],
        "limitations": [
            "No answer is produced because no active Evidence matched the search terms.",
            "No model-generated answer is produced in this slice.",
        ],
    }
    assert str(result["ask_id"]).startswith("ask_")


def test_ask_library_rejects_empty_question(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ask_library(config, "   ")

    assert result == {
        "ok": False,
        "problem": "invalid_question",
        "cause": "question must not be empty",
        "active_publication_impact": "unchanged",
        "next_step": "provide_non_empty_question",
    }


def test_ask_library_rejects_no_searchable_token_question(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ask_library(config, "发布时间？")

    assert result == {
        "ok": False,
        "problem": "invalid_question",
        "cause": "question must contain at least one searchable ASCII token",
        "active_publication_impact": "unchanged",
        "next_step": "provide_searchable_question",
    }


def test_ask_library_rejects_overlong_question(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ask_library(config, "x" * 1001)

    assert result == {
        "ok": False,
        "problem": "invalid_question",
        "cause": "question must be 1000 characters or fewer",
        "active_publication_impact": "unchanged",
        "next_step": "shorten_question",
    }


def test_ask_library_rejects_invalid_limit(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ask_library(config, "publication", limit=21)

    assert result == {
        "ok": False,
        "problem": "invalid_query",
        "cause": "limit must be between 1 and 20",
        "active_publication_impact": "unchanged",
        "next_step": "choose_limit_between_1_and_20",
    }


def test_search_and_ask_share_evidence_payload_shape(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest_file(config, "text-layer.pdf")

    search = search_library(config, "publication active")
    ask = ask_library(config, "publication active")

    assert ask["evidence"][0] == search["results"][0]
```

- [ ] **Step 2: Run failing MCP contract tests**

Run:

```bash
uv run pytest tests/interfaces/test_mcp_contract.py -q
```

Expected: FAIL because `ask_library` does not exist.

- [ ] **Step 3: Implement shared Evidence mapper and `ask_library`**

Modify imports in `src/mke/interfaces/mcp_contract.py`:

```python
from mke.application import AskValidationError, KnowledgeEngine, PdfIngestError, VideoIngestError
from mke.domain import SearchResult
```

Replace the Evidence mapping loop in `search_library()` with:

```python
        results = [
            _evidence_from_search_result(match)
            for match in engine.search(normalized_query, limit=limit)
        ]
```

Add `ask_library()` after `search_library()`:

```python
def ask_library(
    config: McpRuntimeConfig, question: str, limit: int = _DEFAULT_SEARCH_LIMIT
) -> dict[str, Any]:
    engine: KnowledgeEngine | None = None
    try:
        engine = KnowledgeEngine(config.db_path)
        try:
            result = engine.ask(question, limit=limit)
        except AskValidationError as error:
            return _failure(error.problem, error.cause, error.next_step)
        return {
            "ok": True,
            "ask_id": result.ask_id,
            "question": result.question,
            "answer_status": result.answer_status,
            "summary": result.summary,
            "evidence": [
                _evidence_from_search_result(match) for match in result.evidence
            ],
            "limitations": result.limitations,
        }
    finally:
        if engine is not None:
            engine.close()
```

Add the shared mapper before `_resolve_allowed_file()`:

```python
def _evidence_from_search_result(match: SearchResult) -> dict[str, Any]:
    return {
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
```

- [ ] **Step 4: Run MCP contract tests**

Run:

```bash
uv run pytest tests/interfaces/test_mcp_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit MCP contract Ask**

Run:

```bash
git add src/mke/interfaces/mcp_contract.py tests/interfaces/test_mcp_contract.py
git commit -m "feat(mcp): add evidence-only ask contract"
```

## Task 3: Expose Ask Through MCP Server And CLI

**Files:**
- Modify: `src/mke/interfaces/mcp_server.py`
- Modify: `src/mke/cli.py`
- Create: `tests/interfaces/test_cli_ask.py`

- [ ] **Step 1: Add CLI Ask tests**

Create `tests/interfaces/test_cli_ask.py`:

```python
from pathlib import Path

from pytest import CaptureFixture

from mke.cli import main
from tests.conftest import PDF_FIXTURES


def test_cli_ask_returns_evidence_packet(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer.pdf")]) == 0
    capsys.readouterr()

    assert main(["--db", str(db_path), "ask", "publication active"]) == 0

    output = capsys.readouterr().out
    assert "answer_status=evidence_found" in output
    assert "evidence_count=1" in output
    assert 'summary="1 active Evidence item matched the search terms."' in output
    assert "page=2" in output
    assert "Publication search returns only active page two." in output


def test_cli_ask_returns_insufficient_evidence(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer.pdf")]) == 0
    capsys.readouterr()

    assert main(["--db", str(db_path), "ask", "audio diarization"]) == 0

    output = capsys.readouterr().out
    assert "answer_status=insufficient_evidence" in output
    assert "evidence_count=0" in output
    assert 'summary="No active Evidence matched the search terms."' in output


def test_cli_ask_invalid_question_returns_error_contract(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ask", "发布时间？"]) == 1

    output = capsys.readouterr().out
    assert "problem=invalid_question" in output
    assert "cause=question must contain at least one searchable ASCII token" in output
    assert "active_publication_impact=unchanged" in output
    assert "next_step=provide_searchable_question" in output
```

- [ ] **Step 2: Run failing CLI Ask tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_ask.py -q
```

Expected: FAIL because `mke ask` does not exist.

- [ ] **Step 3: Add MCP server tool wrapper**

Modify `src/mke/interfaces/mcp_server.py` after `search_library()`:

```python
    @mcp.tool()
    @_safe_tool
    def ask_library(  # pyright: ignore[reportUnusedFunction]
        question: str, limit: int = 5
    ) -> dict[str, Any]:
        """Return deterministic cited Evidence or insufficient-Evidence state."""
        return mcp_contract.ask_library(config, question, limit)
```

- [ ] **Step 4: Add CLI `ask` parser and dispatch**

Modify `src/mke/cli.py` imports:

```python
from mke.application import AskValidationError, KnowledgeEngine, PdfIngestError, VideoIngestError
```

Add parser setup after `search`:

```python
    ask = subcommands.add_parser("ask")
    ask.add_argument("question", nargs="+")
```

Add dispatch before `_run_get` fallback:

```python
        if args.command == "ask":
            return _ask(engine, " ".join(args.question))
```

Add `_ask()` after `_search()`:

```python
def _ask(engine: KnowledgeEngine, question: str) -> int:
    try:
        result = engine.ask(question)
    except AskValidationError as error:
        _print_error_contract(error.cause, problem=error.problem, next_step=error.next_step)
        return 1
    print(
        f"answer_status={result.answer_status} evidence_count={len(result.evidence)} "
        f"summary=\"{result.summary}\""
    )
    for match in result.evidence:
        if match.locator_kind == "page":
            locator = f"page={match.page_number}"
        else:
            locator = f"{match.locator_kind}={match.locator_start}..{match.locator_end}"
        print(f"{locator} evidence_id={match.evidence_id} text={match.text}")
    return 0
```

Update `_print_error_contract()` signature and body:

```python
def _print_error_contract(
    cause: str,
    problem: str = "pdf_ingest_failed",
    next_step: str = "fix_input_or_retry",
) -> None:
    print(
        f"problem={problem} "
        f"cause={cause} "
        "active_publication_impact=unchanged "
        f"next_step={next_step}"
    )
```

- [ ] **Step 5: Run CLI and MCP server tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_ask.py tests/interfaces/test_mcp_server.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit MCP server and CLI Ask**

Run:

```bash
git add src/mke/interfaces/mcp_server.py src/mke/cli.py tests/interfaces/test_cli_ask.py
git commit -m "feat(cli): expose evidence-only ask"
```

## Task 4: Update Public Contracts And User Docs

**Files:**
- Modify: `docs/reference/contracts.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/how-to/use-mke-mcp.md`
- Modify: `docs/tutorials/getting-started.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Update contracts**

In `docs/reference/contracts.md`:

- Change `mke ask` status from planned to implemented in C2.
- Move `ask_library` from planned MCP tools to implemented MCP tools.
- Add the evidence-only Ask payload fields:
  - `ok`
  - `ask_id`
  - `question`
  - `answer_status`
  - `summary`
  - `evidence`
  - `limitations`
- State that `answer_status` supports `evidence_found` and `insufficient_evidence` in C2.
- State that no-Evidence is `ok=true`, not an error.
- State that CJK-only and punctuation-only Ask inputs return `invalid_question` because C2 uses the current ASCII-token FTS path.

- [ ] **Step 2: Update CLI reference**

In `docs/reference/cli.md`, add:

```bash
mke --db <path> ask <question>
```

Document successful output:

```text
answer_status=evidence_found evidence_count=1 summary="1 active Evidence item matched the search terms."
page=2 evidence_id=ev_... text=Publication search returns only active page two.
```

Document insufficient Evidence output:

```text
answer_status=insufficient_evidence evidence_count=0 summary="No active Evidence matched the search terms."
```

Document Ask validation errors:

```text
problem=invalid_question cause=question must contain at least one searchable ASCII token active_publication_impact=unchanged next_step=provide_searchable_question
```

- [ ] **Step 3: Update MCP how-to**

In `docs/how-to/use-mke-mcp.md`, add `ask_library` after `search_library`:

```json
{
  "question": "What does the document say about Publication failures?",
  "limit": 5
}
```

Explain that the tool returns cited Evidence packets and never model-generated answers.

- [ ] **Step 4: Update tutorials and README files**

In `README.md` and `README_CN.md`, state:

- C2 Ask is evidence-only.
- It returns cited page or timestamp Evidence.
- It refuses with `insufficient_evidence` when Search finds no active Evidence.
- It does not call an LLM.

In `docs/tutorials/getting-started.md`, add a short `mke ask` example after ingest/search if it fits the existing tutorial flow.

In `docs/README.md`, add links to:

- `docs/superpowers/plans/2026-06-16-evidence-only-ask-implementation.md`
- `docs/superpowers/reviews/2026-06-16-evidence-only-ask-autoplan-review.md`

- [ ] **Step 5: Run docs-sensitive tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_ask.py tests/interfaces/test_mcp_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit documentation updates**

Run:

```bash
git add docs/reference/contracts.md docs/reference/cli.md docs/how-to/use-mke-mcp.md docs/tutorials/getting-started.md README.md README_CN.md docs/README.md
git commit -m "docs(ask): document evidence-only ask"
```

## Task 5: Full Verification And PR Preparation

**Files:**
- Modify: `docs/superpowers/plans/2026-06-16-evidence-only-ask-implementation.md`
- Optional create: `docs/superpowers/reviews/2026-06-16-evidence-only-ask-review.md` after pre-landing review

- [ ] **Step 1: Mark completed checklist items**

As each implementation task is completed, update this plan from `- [ ]` to `- [x]` for completed steps. Do not mark future tasks complete early.

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/application/test_ask.py tests/interfaces/test_mcp_contract.py tests/interfaces/test_cli_ask.py tests/interfaces/test_mcp_server.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full local verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke demo --verify
git diff --check
```

Expected:

- `pytest` passes with no failures.
- `ruff` reports all checks passed.
- `pyright` reports 0 errors.
- `uv build` creates both sdist and wheel.
- `mke demo --verify` prints `result=passed`.
- `git diff --check` exits 0.

- [ ] **Step 4: Run pre-landing review**

Run `gstack-review` or the currently approved project review workflow against the full branch diff. Persist durable public-neutral findings to:

```text
docs/superpowers/reviews/2026-06-16-evidence-only-ask-review.md
```

If the review produces actionable findings in scope, fix them in the same branch and rerun the relevant tests.

- [ ] **Step 5: Prepare Chinese PR body**

Use this structure:

```markdown
## Summary

MKE 现在提供 evidence-only Ask：Agent 可以通过 MCP `ask_library` 或 CLI `mke ask` 获取 cited Evidence packet，而不会触发模型生成。

- 新增 `KnowledgeEngine.ask()` 和 `AskResult`。
- 新增 MCP `ask_library`，返回 `evidence_found` 或 `insufficient_evidence`。
- 新增 `mke ask <question>` 作为本地 smoke/debug 入口。
- Ask 复用 active-only Search，并明确拒绝空问题、超长问题、无 searchable ASCII token 的问题和非法 limit。
- 更新 contracts、CLI、MCP how-to、README 和教程文档。

## Completion

- [x] `ask_library` 返回 cited page/timestamp Evidence packet。
- [x] no-match Ask 返回 `ok=true` + `answer_status=insufficient_evidence`。
- [x] C2 不调用 LLM，不生成自然语言答案，不引入 provider 配置。
- [x] `search_library` 与 `ask_library` 共享 Evidence payload mapper。
- [x] `mke ask` 复用同一个 application service。

## Verification

| Check | Result |
|---|---|
| `uv run pytest -q` | Record the exact pass summary from Task 5 Step 3. |
| `uv run ruff check .` | Record the exact result from Task 5 Step 3. |
| `uv run pyright` | Record the exact result from Task 5 Step 3. |
| `uv build` | Record the exact build summary from Task 5 Step 3. |
| `uv run mke demo --verify` | Record the exact `result=passed` line from Task 5 Step 3. |
| `git diff --check` | passed |

## Scope

本 PR 只实现 evidence-only Ask。不包含模型生成、HTTP、workspace UI、embedding/reranking、OCR、任意视频处理、真实转录、认证或托管运行时。

## Risk / Impact

- User impact: Agent 和本地 CLI 可以获得结构化 Ask Evidence packet。
- System impact: 不新增外部服务或 provider 依赖。
- Compatibility impact: 现有 ingest、search、run、demo、MCP 工具保持兼容。
- Rollback plan: revert 本 PR 即可移除 Ask service、MCP tool、CLI command 和文档更新。

## Documentation impact

更新 public contracts、CLI reference、MCP how-to、README、getting-started tutorial、C2 implementation plan 和 review report。
```

- [ ] **Step 6: Stop before push or PR**

Report the branch, commits, verification results, documentation impact, and remaining risks. Do not push, create a PR, or merge without explicit user authorization.
