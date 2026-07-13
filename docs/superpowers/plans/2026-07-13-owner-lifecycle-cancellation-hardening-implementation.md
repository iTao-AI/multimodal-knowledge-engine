# Owner Lifecycle and Cancellation Hardening Implementation Plan

**Status:** Completed on 2026-07-13; awaiting authoritative branch-diff review.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Run recovery, state transitions, subprocess cancellation, and future long-running-work admission owner-scoped and concurrency-safe without adding OCR behavior.

**Architecture:** `SQLiteStore` becomes a side-effect-free connection adapter, while `KnowledgeEngine` and shared `OwnerRuntimeState` own startup recovery. Run transitions become transactional compare-and-set operations. `ActiveProcessController` assigns children to opaque operation IDs so request cancellation is isolated and owner shutdown remains the only broadcast path.

**Tech Stack:** Python 3.12/3.13, frozen dataclasses, SQLite transactions, `threading`, `asyncio`, stdio MCP, pytest, Ruff, Pyright.

## Global Constraints

- Add no OCR behavior, provider dependency, model download, CLI flag, MCP tool, migration, or public request field.
- Preserve the current one-owner-process and SQLite domain-truth architecture.
- Direct `KnowledgeEngine(db_path)` construction remains an owner boundary and performs startup recovery once for that instance.
- Engines built repeatedly from one shared `RuntimeConfig` recover unfinished Runs once per owner, not once per request.
- Every Run state change and matching Run event commit in one SQLite transaction.
- An interrupted, cancelled, failed, superseded, published, or stale Run never returns to `running` or `validated`.
- Individual cancellation terminates only children registered to that operation; `shutdown()` is the only broadcast cancellation API.
- Existing CLI and MCP request/response schemas remain byte-for-byte compatible.
- Use TDD, exact-file staging, focused checks after each task, and the full repository gate before completion.

---

## File Map

| File | Responsibility |
|---|---|
| `src/mke/runtime_owner.py` | Once-per-owner startup state and bounded admission primitive. |
| `src/mke/adapters/video/process.py` | Operation-scoped child tracking and cancellation. |
| `src/mke/adapters/video/providers.py` | Forward the operation ID to bounded child execution. |
| `src/mke/domain/__init__.py` | Project-owned `RunTransitionError`. |
| `src/mke/adapters/sqlite/__init__.py` | Side-effect-free construction and transactional Run CAS. |
| `src/mke/application/__init__.py` | Explicit recovery and fail-closed transition races. |
| `src/mke/runtime.py` | Compose owner state, admission, and operation ID. |
| `src/mke/interfaces/mcp_server.py` | Per-ingest operation and shutdown-only broadcast. |
| `tests/adapters/test_sqlite_run_transitions.py` | CAS, event atomicity, rollback, and no resurrection. |
| `tests/adapters/test_process_controller.py` | Targeted cancellation and shutdown. |
| `tests/runtime/test_owner_runtime.py` | Once-per-owner recovery and admission. |
| `tests/interfaces/test_mcp_owner_concurrency.py` | Real owner concurrency and restart behavior. |
| `tests/interfaces/test_mcp_transcription_runtime.py` | MCP cancellation isolation. |
| `docs/decisions/0002-source-publication-and-active-search-projection.md` | Durable CAS/recovery decision. |
| `docs/decisions/0006-first-party-local-transcription-runtime.md` | Durable cancellation decision. |
| `docs/explanation/architecture.md` | Current owner lifecycle. |

## Interfaces Frozen by This Plan

```python
ProcessOperationId = NewType("ProcessOperationId", str)

class ActiveProcessController:
    def begin_operation(self) -> ProcessOperationId: ...
    def end_operation(self, operation_id: ProcessOperationId) -> None: ...
    def register(
        self,
        process: Popen[bytes],
        *,
        operation_id: ProcessOperationId | None = None,
    ) -> None: ...
    def unregister(
        self,
        process: Popen[bytes],
        *,
        operation_id: ProcessOperationId | None = None,
    ) -> None: ...
    def cancel_operation(self, operation_id: ProcessOperationId) -> None: ...
    def shutdown(self) -> None: ...

class OwnerRuntimeState:
    def recover_unfinished_runs_once(
        self,
        db_path: Path,
        recovery: Callable[[], None],
    ) -> None: ...

@dataclass(frozen=True)
class AdmissionSnapshot:
    capacity: int
    active: int
    waiting: int
    state: Literal["available", "busy", "overloaded"]

class AdmissionOverloadedError(RuntimeError):
    """Raised when bounded owner capacity cannot admit an operation."""

class AdmissionLease:
    def release(self) -> None: ...
    def __enter__(self) -> AdmissionLease: ...
    def __exit__(self, *exc_info: object) -> None: ...

class BoundedAdmissionController:
    def __init__(self, *, capacity: int, max_waiters: int) -> None: ...
    def acquire(self, *, timeout_seconds: float = 0.0) -> AdmissionLease: ...
    def snapshot(self) -> AdmissionSnapshot: ...
```

`RuntimeConfig` adds internal, non-comparing fields `owner_state`, `admission_controller`, and `process_operation_id`. `McpRuntimeConfig` and MCP tool inputs remain unchanged.

---

### Task 1: Move unfinished-Run recovery to the owner boundary

**Files:**
- Create: `src/mke/runtime_owner.py`
- Create: `tests/runtime/test_owner_runtime.py`
- Modify: `src/mke/adapters/sqlite/__init__.py:73-104,446-460`
- Modify: `src/mke/application/__init__.py:108-145`
- Modify: `src/mke/runtime.py:126-162,223-230`
- Modify: `tests/application/test_reliability_demo.py:104-118`
- Modify: `tests/runtime/test_runtime_composition.py`

**Interfaces:**
- Consumes: `SQLiteStore.interrupt_unfinished_runs()` and `RuntimeConfig.db_path`.
- Produces: `OwnerRuntimeState.recover_unfinished_runs_once()` and `KnowledgeEngine.recover_unfinished_runs()`.

- [x] **Step 1: Write failing recovery ownership tests**

Create `tests/runtime/test_owner_runtime.py`:

```python
from pathlib import Path

from mke.adapters.sqlite import SQLiteStore
from mke.application import KnowledgeEngine
from mke.domain import RunState
from mke.runtime import RuntimeConfig, build_engine
from tests.conftest import PDF_FIXTURES


def _leave_running(db_path: Path) -> str:
    engine = KnowledgeEngine(db_path)
    try:
        return engine.prepare_pdf_candidate(
            PDF_FIXTURES / "text-layer.pdf",
            leave_running_for_test=True,
        ).run_id
    finally:
        engine.close()


def test_sqlite_store_construction_does_not_recover_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    run_id = _leave_running(db_path)
    store = SQLiteStore(db_path)
    try:
        assert store.get_run(run_id).state is RunState.RUNNING
    finally:
        store.close()


def test_shared_runtime_recovers_only_on_first_engine_build(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    old_run_id = _leave_running(db_path)
    runtime = RuntimeConfig(db_path)
    first = build_engine(runtime)
    assert first.get_run(old_run_id).state is RunState.INTERRUPTED
    live_run_id = first.prepare_pdf_candidate(
        PDF_FIXTURES / "text-layer.pdf",
        leave_running_for_test=True,
    ).run_id
    first.close()
    second = build_engine(runtime)
    try:
        assert second.get_run(live_run_id).state is RunState.RUNNING
    finally:
        second.close()
```

Keep `test_startup_marks_unfinished_runs_interrupted` as the direct `KnowledgeEngine` regression.

- [x] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/runtime/test_owner_runtime.py \
  tests/application/test_reliability_demo.py::test_startup_marks_unfinished_runs_interrupted
```

Expected: the raw Store interrupts the Run and the second shared-runtime engine interrupts live work.

- [x] **Step 3: Implement explicit recovery ownership**

Create `src/mke/runtime_owner.py`:

```python
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path


class OwnerRuntimeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recovered_databases: set[Path] = set()

    def recover_unfinished_runs_once(
        self,
        db_path: Path,
        recovery: Callable[[], None],
    ) -> None:
        identity = db_path.resolve()
        with self._lock:
            if identity in self._recovered_databases:
                return
            recovery()
            self._recovered_databases.add(identity)
```

Then make these exact composition changes:

- remove `self.interrupt_unfinished_runs()` from `SQLiteStore.__init__`;
- add keyword-only `recover_unfinished_runs: bool = True` to `KnowledgeEngine.__init__`;
- call `self.recover_unfinished_runs()` after Store construction only when true;
- expose `KnowledgeEngine.recover_unfinished_runs()` as a thin Store call;
- add `owner_state: OwnerRuntimeState = field(default_factory=OwnerRuntimeState, compare=False)` to `RuntimeConfig` and validate the exact type;
- make `build_engine()` construct `KnowledgeEngine(..., recover_unfinished_runs=False)`, invoke `owner_state.recover_unfinished_runs_once()`, close on recovery failure, then return the engine.

- [x] **Step 4: Run GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/runtime/test_owner_runtime.py \
  tests/runtime/test_runtime_composition.py \
  tests/application/test_reliability_demo.py
```

- [x] **Step 5: Commit Task 1**

```bash
git add \
  src/mke/runtime_owner.py \
  src/mke/adapters/sqlite/__init__.py \
  src/mke/application/__init__.py \
  src/mke/runtime.py \
  tests/runtime/test_owner_runtime.py \
  tests/runtime/test_runtime_composition.py \
  tests/application/test_reliability_demo.py
git diff --cached --check
git commit -m "fix(runtime): recover unfinished runs once per owner"
```

---

### Task 2: Enforce transactional compare-and-set Run transitions

**Files:**
- Create: `tests/adapters/test_sqlite_run_transitions.py`
- Modify: `src/mke/domain/__init__.py:10-47`
- Modify: `src/mke/adapters/sqlite/__init__.py:432-620,699-718`
- Modify: `src/mke/application/__init__.py:18-50,255-430`
- Modify: `tests/application/test_pdf_publication.py`
- Modify: `tests/application/test_video_publication.py`

**Interfaces:**
- Consumes: Task 1 side-effect-free Store construction.
- Produces: `RunTransitionError` and one transaction-local `_transition_run()` primitive.

- [x] **Step 1: Write failing stale-transition and rollback tests**

Create `tests/adapters/test_sqlite_run_transitions.py`:

```python
from pathlib import Path

import pytest

from mke.adapters.sqlite import SQLiteStore
from mke.domain import CandidateEvidence, RunManifest, RunState, RunTransitionError


def _running_run(store: SQLiteStore) -> str:
    source = store.ensure_source("fixture.pdf", "a" * 64)
    run = store.create_run(source.source_id)
    store.mark_run_running(run.run_id)
    return run.run_id


def test_interrupted_run_cannot_be_validated_or_append_event(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    run_id = _running_run(store)
    store.interrupt_unfinished_runs()
    before = store.get_run_events(run_id)

    with pytest.raises(RunTransitionError) as error:
        store.persist_validated_candidate(
            run_id,
            [CandidateEvidence("ev_1", "page", 1, 1, "trusted text")],
            RunManifest(run_id, 1, ("pdf_text_extraction",), "test-v1", "a" * 64),
        )

    assert error.value.actual is RunState.INTERRUPTED
    assert store.get_run(run_id).state is RunState.INTERRUPTED
    assert store.get_run_events(run_id) == before
    row = store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        "SELECT COUNT(*) AS count FROM evidence WHERE run_id = ?", (run_id,)
    ).fetchone()
    assert row is not None
    assert int(row["count"]) == 0


def test_second_running_transition_has_no_duplicate_event(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    run_id = _running_run(store)
    before = store.get_run_events(run_id)
    with pytest.raises(RunTransitionError):
        store.mark_run_running(run_id)
    assert store.get_run_events(run_id) == before
```

Keep this as a private adapter-test query; do not add a production read API only for the assertion.

- [x] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/adapters/test_sqlite_run_transitions.py
```

Expected: `RunTransitionError` is absent and unconditional writes resurrect the interrupted Run.

- [x] **Step 3: Add `RunTransitionError` and CAS helper**

Add to `src/mke/domain/__init__.py`:

```python
class RunTransitionError(RuntimeError):
    def __init__(
        self,
        run_id: str,
        *,
        expected: tuple[RunState, ...],
        actual: RunState,
        target: RunState,
    ) -> None:
        super().__init__("Run state changed during processing")
        self.run_id = run_id
        self.expected = expected
        self.actual = actual
        self.target = target
```

Add inside `SQLiteStore`:

```python
def _transition_run(
    self,
    run_id: str,
    *,
    expected: tuple[RunState, ...],
    target: RunState,
    event_type: str,
) -> None:
    slots = ",".join("?" for _ in expected)
    cursor = self._connection.execute(
        f"UPDATE runs SET state = ? WHERE run_id = ? AND state IN ({slots})",
        (target.value, run_id, *(state.value for state in expected)),
    )
    if cursor.rowcount != 1:
        row = self._connection.execute(
            "SELECT state FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown run: {run_id}")
        raise RunTransitionError(
            run_id,
            expected=expected,
            actual=RunState(str(row["state"])),
            target=target,
        )
    self._append_event(run_id, event_type)
```

Use it in existing transactions for:

- `QUEUED -> RUNNING` with `RUN_STARTED`;
- `QUEUED|RUNNING -> FAILED` with `RUN_FAILED`;
- `QUEUED|RUNNING -> INTERRUPTED` with `RUN_INTERRUPTED` only after a successful row update;
- `RUNNING -> VALIDATED` after Evidence and manifest writes;
- `VALIDATED -> SUPERSEDED` after the generation/revision conflict check;
- `VALIDATED -> PUBLISHED` as the last activation write.

The final activation CAS must roll back Publication, FTS, pointer, reports, and event if it fails.

- [x] **Step 4: Make application races fail closed**

Import `RunTransitionError` in the application layer. Add dedicated handlers before branches that call `mark_run_failed()`:

```python
except RunTransitionError as error:
    raise PdfIngestError(str(error), run.run_id) from error
```

The video path returns `VideoIngestError` with `problem="video_ingest_failed"` and `next_step="retry_when_owner_ready"`. Never rewrite the authoritative state after a CAS error.

Add application tests that interrupt immediately before validation and immediately before the final activation CAS. Both preserve the old active Search/Ask result and append no validation/publication event.

- [x] **Step 5: Run transition and Publication suites**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_sqlite_run_transitions.py \
  tests/adapters/test_sqlite_transcript_intake_report.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py \
  tests/application/test_reliability_demo.py
```

- [x] **Step 6: Commit Task 2**

```bash
git add \
  src/mke/domain/__init__.py \
  src/mke/adapters/sqlite/__init__.py \
  src/mke/application/__init__.py \
  tests/adapters/test_sqlite_run_transitions.py \
  tests/adapters/test_sqlite_transcript_intake_report.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py \
  tests/application/test_reliability_demo.py
git diff --cached --check
git commit -m "fix(storage): enforce atomic run transitions"
```

---

### Task 3: Isolate subprocess cancellation by operation

**Files:**
- Create: `tests/adapters/test_process_controller.py`
- Modify: `src/mke/adapters/video/process.py`
- Modify: `src/mke/adapters/video/providers.py:55-66,94-104,144-186`
- Modify: `src/mke/runtime.py:126-230`
- Modify: `src/mke/interfaces/mcp_server.py:35-45,155-175`
- Modify: `tests/adapters/test_local_command_transcript_provider.py`
- Modify: `tests/interfaces/test_mcp_transcription_runtime.py`
- Modify: `tests/runtime/test_runtime_composition.py`

**Interfaces:**
- Consumes: Task 1 shared runtime and Task 2 no-resurrection transitions.
- Produces: `ProcessOperationId`, targeted `cancel_operation()`, and owner-only `shutdown()`.

- [x] **Step 1: Write failing controller tests**

Create a bounded `FakeProcess` in `tests/adapters/test_process_controller.py` whose `poll()` returns `None` until `kill()`, and whose `wait()` records the call. Cover:

```python
def test_cancel_operation_kills_only_its_children() -> None:
    controller = ActiveProcessController()
    first = controller.begin_operation()
    second = controller.begin_operation()
    first_process = FakeProcess()
    second_process = FakeProcess()
    controller.register(first_process, operation_id=first)  # type: ignore[arg-type]
    controller.register(second_process, operation_id=second)  # type: ignore[arg-type]
    controller.cancel_operation(first)
    assert first_process.killed is True
    assert second_process.killed is False


def test_late_registration_after_targeted_cancel_is_killed() -> None:
    controller = ActiveProcessController()
    operation_id = controller.begin_operation()
    controller.cancel_operation(operation_id)
    process = FakeProcess()
    controller.register(process, operation_id=operation_id)  # type: ignore[arg-type]
    assert process.killed is True


def test_shutdown_kills_scoped_and_unscoped_children() -> None:
    controller = ActiveProcessController()
    operation_id = controller.begin_operation()
    scoped = FakeProcess()
    unscoped = FakeProcess()
    controller.register(scoped, operation_id=operation_id)  # type: ignore[arg-type]
    controller.register(unscoped)  # type: ignore[arg-type]
    controller.shutdown()
    assert scoped.killed is True
    assert unscoped.killed is True
```

- [x] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_process_controller.py \
  tests/interfaces/test_mcp_transcription_runtime.py
```

Expected: the operation ID and targeted cancellation APIs do not exist.

- [x] **Step 3: Replace global cancellation with operation-scoped state**

Use this state shape in `src/mke/adapters/video/process.py`:

```python
from typing import NewType
from uuid import uuid4

ProcessOperationId = NewType("ProcessOperationId", str)

class ActiveProcessController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[
            ProcessOperationId | None, set[subprocess.Popen[bytes]]
        ] = {}
        self._cancelled_operations: set[ProcessOperationId] = set()
        self._shutdown_requested = False

    def begin_operation(self) -> ProcessOperationId:
        operation_id = ProcessOperationId(f"op_{uuid4().hex}")
        with self._lock:
            if self._shutdown_requested:
                raise RuntimeError("process controller is shutting down")
            self._processes[operation_id] = set()
        return operation_id
```

Complete the frozen methods as follows:

- `register()` adds to the selected set unless shutdown or that operation's cancel latch is set; a late child is terminated immediately;
- `unregister()` removes only from the matching set;
- `cancel_operation()` latches and copies one set, then terminates outside the lock;
- `end_operation()` rejects unknown IDs, requires no registered child, then removes the set and latch;
- `shutdown()` latches permanently, copies all sets, and terminates every child;
- `_terminate()` kills only a live process and always waits for the parent.

Delete `cancel_active()` and the global `_cancel_requested`/`_active_operations` behavior.

- [x] **Step 4: Thread the operation ID through provider and runtime composition**

Add to `LocalCommandTranscriptConfig` and `_run_bounded_command()`:

```python
process_operation_id: ProcessOperationId | None = None
```

Use the same ID for controller `register()` and `unregister()`.

Add to `RuntimeConfig`:

```python
process_operation_id: ProcessOperationId | None = field(default=None, compare=False)
```

Reject a non-`None` value that is not a string beginning with `op_`. `build_transcript_provider()` forwards it unchanged.

Change `_ingest_with_cancellation()`:

```python
from dataclasses import replace

operation_id = controller.begin_operation()
scoped = replace(
    config,
    runtime=replace(config.runtime, process_operation_id=operation_id),
)
worker = asyncio.create_task(
    asyncio.to_thread(mcp_contract.ingest_file, scoped, path)
)
```

On cancellation, call `cancel_operation(operation_id)`, await shielded worker cleanup, then re-raise. In `finally`, call `end_operation(operation_id)`. MCP lifespan calls `shutdown()`.

- [x] **Step 5: Add a two-ingest MCP regression**

Extend `tests/interfaces/test_mcp_transcription_runtime.py` with two worker events and two fake children. Cancel only the first async ingest and assert:

- the first child is killed and its worker exits;
- the second child stays live until explicitly released;
- the second task returns normally;
- a late child using the first operation ID is killed;
- `shutdown()` remains broadcast.

- [x] **Step 6: Run provider/runtime/MCP GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_process_controller.py \
  tests/adapters/test_local_command_transcript_provider.py \
  tests/runtime/test_runtime_composition.py \
  tests/interfaces/test_mcp_transcription_runtime.py \
  tests/interfaces/test_mcp_server.py
```

- [x] **Step 7: Commit Task 3**

```bash
git add \
  src/mke/adapters/video/process.py \
  src/mke/adapters/video/providers.py \
  src/mke/runtime.py \
  src/mke/interfaces/mcp_server.py \
  tests/adapters/test_process_controller.py \
  tests/adapters/test_local_command_transcript_provider.py \
  tests/runtime/test_runtime_composition.py \
  tests/interfaces/test_mcp_transcription_runtime.py \
  tests/interfaces/test_mcp_server.py
git diff --cached --check
git commit -m "fix(runtime): isolate subprocess cancellation"
```

---

### Task 4: Add bounded owner admission and concurrency proof

**Files:**
- Modify: `src/mke/runtime_owner.py`
- Modify: `src/mke/runtime.py`
- Modify: `tests/runtime/test_owner_runtime.py`
- Create: `tests/interfaces/test_mcp_owner_concurrency.py`

**Interfaces:**
- Consumes: Tasks 1-3 owner state, CAS transitions, and operation IDs.
- Produces: `BoundedAdmissionController`, `AdmissionLease`, and `AdmissionSnapshot` for a later approved OCR runtime.

- [x] **Step 1: Write failing admission tests**

Add tests for exact `capacity=1`, `max_waiters=1` behavior. Use a held first lease, one waiting thread, and eight additional callers. Assert one waiter is admitted after release, eight callers receive `AdmissionOverloadedError`, counters return to zero, a lease cannot be released twice, and non-finite/negative timeouts are rejected.

Also assert the snapshot shape exactly:

```python
assert controller.snapshot() == AdmissionSnapshot(
    capacity=1,
    active=1,
    waiting=0,
    state="busy",
)
```

- [x] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/runtime/test_owner_runtime.py
```

Expected: the admission types are absent.

- [x] **Step 3: Implement the condition-based admission contract**

Use one `threading.Condition`, private counters, and an `AdmissionLease` that calls one private release callback. The contract is exact:

- immediate acquire when `active < capacity`;
- reject when full and `max_waiters == 0`;
- reject when the waiter bound is already full;
- otherwise wait no longer than a finite non-negative timeout;
- a timed-out waiter decrements `waiting` before raising;
- release decrements `active` once and notifies one waiter;
- lease context-manager exit calls `release()`, while a second explicit or implicit release raises
  `RuntimeError` without changing counters;
- snapshot exposes only `capacity`, `active`, `waiting`, and `state`: `available` when capacity is
  immediately free, `overloaded` when capacity is full and no additional waiter may enter, and
  `busy` otherwise.

Use frozen dataclasses for `AdmissionSnapshot` and an internal `_AdmissionState`. Validate
`capacity >= 1`, `max_waiters >= 0`, and finite `timeout_seconds >= 0`. `AdmissionOverloadedError`
contains the stable message `owner capacity is busy` and no wait duration or process details.

Add to `RuntimeConfig`:

```python
admission_controller: BoundedAdmissionController = field(
    default_factory=lambda: BoundedAdmissionController(capacity=1, max_waiters=1),
    compare=False,
)
```

Validate the exact type. Current PDF/video ingest does not acquire a lease, so this task changes no current throughput.

- [x] **Step 4: Add owner concurrency and restart tests**

Create `tests/interfaces/test_mcp_owner_concurrency.py` using one `McpRuntimeConfig` and real SQLite. Cover:

- two first-use engine builds recover one old running Run once;
- `get_run`, Search, and Ask do not interrupt a Run created after owner recovery;
- cancelling one scoped worker adds no event to a sibling Run;
- another request engine after cancellation does not recover again;
- a fresh `RuntimeConfig` representing owner restart interrupts the remaining unfinished Run once.

- [x] **Step 5: Run the concurrency slice five times**

```bash
for attempt in 1 2 3 4 5; do
  UV_OFFLINE=1 uv run pytest -q \
    tests/runtime/test_owner_runtime.py \
    tests/interfaces/test_mcp_owner_concurrency.py \
    tests/interfaces/test_mcp_transcription_runtime.py || exit 1
done
```

- [x] **Step 6: Commit Task 4**

```bash
git add \
  src/mke/runtime_owner.py \
  src/mke/runtime.py \
  tests/runtime/test_owner_runtime.py \
  tests/interfaces/test_mcp_owner_concurrency.py
git diff --cached --check
git commit -m "feat(runtime): add bounded owner admission"
```

---

### Task 5: Document the lifecycle contract and close verification

**Files:**
- Modify: `docs/decisions/0002-source-publication-and-active-search-projection.md`
- Modify: `docs/decisions/0006-first-party-local-transcription-runtime.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/superpowers/plans/2026-07-13-owner-lifecycle-cancellation-hardening-implementation.md`
- Test: `tests/evaluation/test_evidence_provenance_documentation.py`
- Test: `tests/scripts/test_release_presentation_audit.py`

**Interfaces:**
- Consumes: completed Tasks 1-4 and their command evidence.
- Produces: durable public architecture documentation and a reviewable local branch.

- [x] **Step 1: Update durable documentation**

Record these exact facts:

- Store connection construction performs no recovery;
- direct `KnowledgeEngine` construction is one owner boundary;
- shared `RuntimeConfig.owner_state` recovers once across request engines;
- each Run transition and event is one CAS transaction;
- request cancellation targets one operation ID;
- owner shutdown is the only broadcast child cancellation;
- bounded admission exists but current PDF/video paths do not consume it;
- no public request/response contract or throughput behavior changed.

Do not mention OCR providers in the ADR updates.

- [x] **Step 2: Run focused quality checks**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_sqlite_run_transitions.py \
  tests/adapters/test_process_controller.py \
  tests/runtime/test_owner_runtime.py \
  tests/interfaces/test_mcp_owner_concurrency.py \
  tests/interfaces/test_mcp_transcription_runtime.py \
  tests/application/test_reliability_demo.py
UV_OFFLINE=1 uv run ruff check src/mke tests
UV_OFFLINE=1 uv run pyright
git diff --check
```

- [x] **Step 3: Run the complete repository gate**

```bash
UV_OFFLINE=1 uv run pytest -q
UV_OFFLINE=1 uv run ruff check .
UV_OFFLINE=1 uv run pyright
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run pytest -q tests/proof/test_local_knowledge.py
UV_OFFLINE=1 uv run pytest -q tests/proof/test_evidence_provenance_stdio.py
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_consumer_source_pack_proof.py
uv run python scripts/release_presentation_audit.py --root .
```

If the full suite exposes an unchanged baseline failure, isolate it against the planning parent and report it. Do not modify retrieval, evaluation, release, or OCR surfaces outside this plan.

- [x] **Step 4: Mark status accurately and commit documentation**

Only after Step 3 passes or an authority-approved baseline blocker is recorded, update completed checkboxes and append exact command evidence.

Execution evidence from the final committed candidate:

- focused lifecycle slice: `34 passed`; Ruff passed; Pyright reported `0 errors, 0 warnings, 0 informations`;
- complete suite: `1616 passed, 5 skipped`; only SWIG deprecation warnings were emitted;
- `uv build`: source distribution and wheel built successfully;
- `mke proof run`: `proof=product status=passed cases=8 passed=8 failed=0`;
- `mke demo --verify`: `result=passed`;
- proof suites: `11 passed`, `1 passed`, and `81 passed`;
- release presentation audit: `{"status": "ok", "violations": []}`;
- E1 through E3-E canonical validators passed after an identity-only provenance refresh; normalized
  protocol, observation, metric, gate, profile, candidate, status, and verdict payloads were equal.

```bash
git add \
  docs/decisions/0002-source-publication-and-active-search-projection.md \
  docs/decisions/0006-first-party-local-transcription-runtime.md \
  docs/explanation/architecture.md \
  docs/superpowers/plans/2026-07-13-owner-lifecycle-cancellation-hardening-implementation.md
git diff --cached --check
git commit -m "docs(runtime): record owner lifecycle hardening"
```

- [x] **Step 5: Stop for authoritative review**

Do not push or open a PR. Report branch, commit series, exact diff, verification evidence, remaining risks, and any unchanged baseline blocker. The planning/review window reviews the actual branch diff before publication.
