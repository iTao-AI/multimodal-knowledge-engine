# Real Local Transcription Protocol And Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the provider-neutral transcript, provenance, report, error, fingerprint, resource, and atomic Publication contracts required by D3-B without installing or invoking a real ASR runtime.

**Architecture:** Extend the existing D3-A transcript protocol additively. The shared schema parser returns project-owned media, segment, and optional provenance DTOs; providers return a typed extraction result; the application passes a validated successful report into SQLite activation, where Publication, FTS, Run state, and report become visible in one transaction.

**Tech Stack:** Python 3.12/3.13, dataclasses, SQLite, pytest, Ruff, Pyright, uv.

---

## Prerequisites And PR Boundary

- Start from the latest `main` that contains this approved design and plan set.
- Use an isolated worktree and branch `codex/transcription-protocol-lifecycle`.
- Read:
  - `AGENTS.md`
  - `docs/decisions/0002-source-publication-and-active-search-projection.md`
  - `docs/decisions/0005-optional-local-command-transcription-provider.md`
  - `docs/superpowers/specs/2026-06-18-real-local-transcription-deployment-proof-design.md`
  - `docs/superpowers/reviews/2026-06-18-real-local-transcription-deployment-proof-autoplan-review.md`
- Do not add `faster-whisper`, PyAV, model resolution, new CLI commands, or MCP startup flags in this PR.
- Preserve sidecar payloads without `transcription` provenance and preserve the deterministic proof.

## File Structure

### Create

- `src/mke/adapters/video/contracts.py`: resource limits, adapter exit codes, canonical identity, and report construction.
- `src/mke/interfaces/public_errors.py`: one typed, redacted public error contract shared by CLI and MCP.
- `tests/domain/test_transcript_contracts.py`: DTO, report, limit, identity, and Manifest validation.
- `tests/adapters/test_sqlite_transcript_intake_report.py`: migration and atomic report visibility.
- `tests/interfaces/test_public_errors.py`: serializer allowlist and redaction contract.

### Modify

- `src/mke/domain/__init__.py`: parsed transcript, provenance, report, extraction result, and `IngestResult`.
- `src/mke/adapters/video/schema.py`: provider-neutral payload parser with optional provenance.
- `src/mke/adapters/video/transcript.py`: sidecar-only file lookup, shared parser delegation.
- `src/mke/adapters/video/providers.py`: adapt sidecar and command providers to the typed parsed result.
- `src/mke/adapters/video/__init__.py`: public adapter exports.
- `src/mke/adapters/sqlite/__init__.py`: report table, getter, and atomic activation insert.
- `src/mke/application/__init__.py`: input preflight, report propagation, and failure cleanup.
- `src/mke/cli.py`: shared error serializer plus human transcript report output.
- `src/mke/interfaces/mcp_contract.py`: shared error serializer and transcript report payload.
- `tests/adapters/test_video_transcript.py`: schema compatibility, bounds, and provenance tests.
- `tests/adapters/test_local_command_transcript_provider.py`: parsed-result compatibility.
- `tests/application/test_video_provider_injection.py`: report propagation.
- `tests/application/test_video_publication.py`: fail-closed and active Search regression coverage.
- `tests/interfaces/test_cli_error_contract.py`: shared serializer output.
- `tests/interfaces/test_cli_video.py`: successful report output.
- `tests/interfaces/test_mcp_contract.py`: ingest/get report output and unchanged MCP schemas.
- `docs/explanation/architecture.md`: candidate report and atomic activation flow.
- `docs/reference/contracts.md`: additive transcript provenance, report, fingerprint, and errors.

## Task 1: Define Typed Transcript And Fingerprint Contracts

**Files:**
- Create: `src/mke/adapters/video/contracts.py`
- Create: `tests/domain/test_transcript_contracts.py`
- Modify: `src/mke/domain/__init__.py`
- Modify: `tests/domain/test_manifest.py`

- [ ] **Step 1: Write failing DTO and Manifest tests**

Add tests that instantiate a complete parsed transcript, assert a frozen report contains no path or argv fields, and verify the exact fingerprint grammar:

```python
def test_faster_whisper_fingerprint_requires_version_and_lowercase_sha256() -> None:
    valid = "faster-whisper-v1:" + ("a" * 64)
    assert is_recognized_video_fingerprint(valid)
    assert not is_recognized_video_fingerprint("faster-whisper-v1:abc")
    assert not is_recognized_video_fingerprint("faster-whisper-v1:" + ("A" * 64))
    assert not is_recognized_video_fingerprint("faster-whisper-v2:" + ("a" * 64))
```

Add a Manifest test using the valid dynamic fingerprint and another asserting a prefix-only value raises `ManifestValidationError`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run pytest tests/domain/test_transcript_contracts.py tests/domain/test_manifest.py -q
```

Expected: collection or import failure because the new types and helper do not exist.

- [ ] **Step 3: Add project-owned frozen DTOs**

Add these domain shapes without provider SDK types:

```python
@dataclass(frozen=True)
class VideoMediaInfo:
    container: str
    video_codec: str
    audio_codec: str
    has_audio: bool
    duration_ms: int


@dataclass(frozen=True)
class TranscriptionProvenance:
    provider: str
    model: str
    model_revision: str
    library_version: str
    device: str
    compute_type: str
    detected_language: str
    model_source: str
    transcription_duration_ms: int


@dataclass(frozen=True)
class ParsedVideoTranscript:
    media: VideoMediaInfo
    segments: tuple[VideoTranscriptSegment, ...]
    transcription_provenance: TranscriptionProvenance | None = None


@dataclass(frozen=True)
class TranscriptIntakeReport:
    provider: str
    model: str
    model_revision: str
    library_version: str
    device: str
    compute_type: str
    detected_language: str
    media_duration_ms: int
    transcription_duration_ms: int
    segment_count: int
    model_source: str


@dataclass(frozen=True)
class TranscriptExtractionResult:
    parsed_transcript: ParsedVideoTranscript
    extractor_fingerprint: str
    transcript_intake_report: TranscriptIntakeReport | None = None

    @property
    def segments(self) -> tuple[VideoTranscriptSegment, ...]:
        return self.parsed_transcript.segments
```

Extend `IngestResult` with:

```python
transcript_intake_report: TranscriptIntakeReport | None = None
```

Keep `intake_report` as the PDF-only field.

- [ ] **Step 4: Add exact fingerprint recognition**

Use a full-match regex and keep legacy D3-A fingerprints:

```python
_FASTER_WHISPER_FINGERPRINT_RE = re.compile(
    r"faster-whisper-v1:[0-9a-f]{64}\Z"
)


def is_recognized_video_fingerprint(value: str) -> bool:
    return value in {
        VIDEO_TRANSCRIPT_FINGERPRINT,
        LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
    } or _FASTER_WHISPER_FINGERPRINT_RE.fullmatch(value) is not None
```

Route `validate_manifest()` through this helper. Do not accept arbitrary provider strings or a broad prefix.

- [ ] **Step 5: Add canonical identity and resource contracts**

In `contracts.py`, add:

```python
@dataclass(frozen=True)
class VideoTranscriptionLimits:
    max_input_bytes: int = 100 * 1024 * 1024
    max_media_duration_ms: int = 900_000
    max_segment_count: int = 10_000
    timeout_seconds: float = 900.0
    max_stdout_bytes: int = 2 * 1024 * 1024
    max_stderr_bytes: int = 512 * 1024


class AdapterExitCode(IntEnum):
    DEPENDENCY_MISSING = 20
    MODEL_UNAVAILABLE = 21
    MODEL_RESOLUTION_FAILED = 22
    MEDIA_UNSUPPORTED = 30
    MEDIA_NO_AUDIO = 31
    MEDIA_LIMIT_EXCEEDED = 32
    TRANSCRIPTION_FAILED = 40
    EMPTY_TRANSCRIPT = 41
    SCHEMA_INVALID = 50


def faster_whisper_fingerprint(provenance: TranscriptionProvenance) -> str:
    identity = {
        "compute_type": provenance.compute_type,
        "device": provenance.device,
        "library_version": provenance.library_version,
        "model": provenance.model,
        "model_revision": provenance.model_revision,
        "provider": provenance.provider,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "faster-whisper-v1:" + sha256(canonical.encode("utf-8")).hexdigest()
```

Validate positive limits in `VideoTranscriptionLimits.__post_init__`.

- [ ] **Step 6: Run focused tests and commit**

Run:

```bash
uv run pytest tests/domain/test_transcript_contracts.py tests/domain/test_manifest.py -q
uv run ruff check src/mke/domain src/mke/adapters/video/contracts.py tests/domain
uv run pyright
```

Commit:

```bash
git add src/mke/domain/__init__.py src/mke/adapters/video/contracts.py tests/domain/test_transcript_contracts.py tests/domain/test_manifest.py
git commit -m "feat(video): define transcription contracts"
```

## Task 2: Upgrade The Shared Transcript Schema Additively

**Files:**
- Modify: `src/mke/adapters/video/schema.py`
- Modify: `src/mke/adapters/video/transcript.py`
- Modify: `src/mke/adapters/video/providers.py`
- Modify: `src/mke/adapters/video/__init__.py`
- Modify: `tests/adapters/test_video_transcript.py`
- Modify: `tests/adapters/test_local_command_transcript_provider.py`

- [ ] **Step 1: Write failing parser tests**

Cover:

- old sidecar without provenance remains valid;
- first-party parse with `require_provenance=True` rejects missing or partial provenance;
- unknown provenance fields are ignored;
- `media.duration_ms > 0`;
- segment end does not exceed media duration;
- segment count is at most 10,000;
- bounded provider/model/version/language strings;
- parser errors use provider-neutral wording, while missing sidecar remains sidecar-specific.

Use assertions against `ParsedVideoTranscript`, not raw dictionaries.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/adapters/test_video_transcript.py tests/adapters/test_local_command_transcript_provider.py -q
```

Expected: failures because `parse_transcript_payload()` still returns only segments.

- [ ] **Step 3: Return a parsed transcript from the shared parser**

Implement these signatures:

```python
def parse_transcript_payload(
    payload: object,
    *,
    require_provenance: bool = False,
    limits: VideoTranscriptionLimits = VideoTranscriptionLimits(),
) -> ParsedVideoTranscript:
    ...


def load_transcript_json(
    text: str,
    *,
    require_provenance: bool = False,
    limits: VideoTranscriptionLimits = VideoTranscriptionLimits(),
) -> ParsedVideoTranscript:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise VideoExtractionError("video transcript is not valid JSON") from error
    return parse_transcript_payload(
        payload,
        require_provenance=require_provenance,
        limits=limits,
    )
```

Keep file-not-found handling in `transcript.py` as `video transcript sidecar is missing`.

- [ ] **Step 4: Validate media, provenance, and segments before returning**

Build `VideoMediaInfo` first, parse segments in source order, enforce media and count limits, then parse the fixed provenance allowlist. For first-party output require:

```python
required = {
    "provider",
    "model",
    "model_revision",
    "library_version",
    "device",
    "compute_type",
    "detected_language",
    "model_source",
    "transcription_duration_ms",
}
```

Require `provider == "faster-whisper"`, `model_source == "cache"`, a full 40-character lowercase commit SHA, non-negative integer duration, and bounded strings. Reject segment end values greater than `media.duration_ms`.

- [ ] **Step 5: Adapt both D3-A providers**

`SidecarTranscriptProvider` calls the parser with `require_provenance=False` and returns no successful intake report. `LocalCommandTranscriptProvider` keeps the generic D3-A behavior and also allows missing provenance. Its result is:

```python
parsed = load_transcript_json(text)
return TranscriptExtractionResult(
    parsed_transcript=parsed,
    extractor_fingerprint=self.config.extractor_fingerprint,
)
```

The first-party runtime in PR 2 will call the same parser with `require_provenance=True`.

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/adapters/test_video_transcript.py tests/adapters/test_local_command_transcript_provider.py -q
uv run ruff check src/mke/adapters/video tests/adapters
uv run pyright
```

```bash
git add src/mke/adapters/video src/mke/domain/__init__.py tests/adapters/test_video_transcript.py tests/adapters/test_local_command_transcript_provider.py
git commit -m "feat(video): validate transcript provenance"
```

## Task 3: Add One Typed Public Error Serializer

**Files:**
- Create: `src/mke/interfaces/public_errors.py`
- Create: `tests/interfaces/test_public_errors.py`
- Modify: `src/mke/cli.py`
- Modify: `src/mke/interfaces/mcp_contract.py`
- Modify: `src/mke/interfaces/mcp_server.py`
- Modify: `tests/interfaces/test_cli_error_contract.py`
- Modify: `tests/interfaces/test_mcp_server.py`

- [ ] **Step 1: Write failing serializer and redaction tests**

Assert CLI and MCP payloads come from the same DTO and that an unknown exception containing a home path, cache path, argv, stderr, endpoint, secret, and traceback serializes only:

```python
{
    "ok": False,
    "problem": "internal_error",
    "cause": "operation failed; details were redacted",
    "active_publication_impact": "unchanged",
    "next_step": "check_server_logs",
}
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/interfaces/test_public_errors.py tests/interfaces/test_cli_error_contract.py tests/interfaces/test_mcp_server.py -q
```

- [ ] **Step 3: Implement the typed contract**

```python
@dataclass(frozen=True)
class PublicError:
    problem: str
    cause: str
    next_step: str
    run_id: str | None = None
    active_publication_impact: str = "unchanged"

    def payload(self) -> dict[str, object]:
        result: dict[str, object] = {
            "ok": False,
            "problem": self.problem,
            "cause": self.cause,
            "active_publication_impact": self.active_publication_impact,
            "next_step": self.next_step,
        }
        if self.run_id is not None:
            result["run_id"] = self.run_id
        return result
```

Add an exact allowlist mapping for stable causes and a generic fallback. Never include `str(error)` unless it exactly matches an allowlisted cause.

- [ ] **Step 4: Route CLI and MCP through the serializer**

Replace `_PUBLIC_ERROR_CAUSES`, `_public_error_cause()`, `_failure()`, and the duplicated MCP fallback payload with `PublicError.payload()` plus a single human renderer:

```python
def render_public_error_line(error: PublicError) -> str:
    payload = error.payload()
    return " ".join(
        f"{key}={value}"
        for key, value in payload.items()
        if key != "ok"
    )
```

Preserve current public output values for existing PDF, Ask, sidecar, and local-command failures.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/interfaces/test_public_errors.py tests/interfaces/test_cli_error_contract.py tests/interfaces/test_mcp_server.py -q
uv run ruff check src/mke/interfaces src/mke/cli.py tests/interfaces
uv run pyright
```

```bash
git add src/mke/interfaces/public_errors.py src/mke/interfaces/mcp_contract.py src/mke/interfaces/mcp_server.py src/mke/cli.py tests/interfaces
git commit -m "refactor(interfaces): share public error contract"
```

## Task 4: Persist Successful Transcript Reports Atomically

**Files:**
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Create: `tests/adapters/test_sqlite_transcript_intake_report.py`
- Modify: `tests/adapters/test_sqlite_migration.py`

- [ ] **Step 1: Write failing migration and transaction tests**

Cover:

- migration creates `transcript_intake_reports`;
- a normal faster-whisper activation exposes Publication and report together;
- failure after Publication insert, during FTS replacement, after pointer switch, or during report insert rolls back both;
- superseded activation exposes no report;
- a faster-whisper Manifest cannot publish without a report;
- legacy sidecar and PDF activation still allow `None`.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/adapters/test_sqlite_migration.py tests/adapters/test_sqlite_transcript_intake_report.py -q
```

- [ ] **Step 3: Add the additive table**

Add an idempotent table with bounded CHECK constraints:

```sql
CREATE TABLE IF NOT EXISTS transcript_intake_reports (
  run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  model_revision TEXT NOT NULL,
  library_version TEXT NOT NULL,
  device TEXT NOT NULL,
  compute_type TEXT NOT NULL,
  detected_language TEXT NOT NULL,
  media_duration_ms INTEGER NOT NULL CHECK(media_duration_ms > 0),
  transcription_duration_ms INTEGER NOT NULL CHECK(transcription_duration_ms >= 0),
  segment_count INTEGER NOT NULL CHECK(segment_count > 0),
  model_source TEXT NOT NULL CHECK(model_source = 'cache')
);
```

- [ ] **Step 4: Insert the report inside activation**

Change the signature to:

```python
def activate_publication(
    self,
    run_id: str,
    failure_point: FailurePoint | None = None,
    *,
    transcript_intake_report: TranscriptIntakeReport | None = None,
) -> ActivationResult:
```

Inside the existing `with self._connection:` block:

1. read the Manifest fingerprint;
2. reject a recognized faster-whisper fingerprint without a report;
3. perform Publication, FTS, and active pointer writes;
4. insert the report;
5. mark the Run published and append the event.

Do not commit in the report helper. Let the enclosing transaction own commit/rollback.

- [ ] **Step 5: Add the report getter**

Implement `get_transcript_intake_report(run_id) -> TranscriptIntakeReport | None` with explicit field conversion. Do not return arbitrary row dictionaries.

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/adapters/test_sqlite_migration.py tests/adapters/test_sqlite_transcript_intake_report.py -q
uv run ruff check src/mke/adapters/sqlite tests/adapters
uv run pyright
```

```bash
git add src/mke/adapters/sqlite/__init__.py tests/adapters/test_sqlite_migration.py tests/adapters/test_sqlite_transcript_intake_report.py
git commit -m "feat(storage): activate transcript reports atomically"
```

## Task 5: Wire Reports And Fail-Closed Resource Checks Through The Application

**Files:**
- Modify: `src/mke/application/__init__.py`
- Modify: `tests/application/test_video_provider_injection.py`
- Modify: `tests/application/test_video_publication.py`

- [ ] **Step 1: Write failing application lifecycle tests**

Use a fake provider that returns a valid faster-whisper fingerprint and report. Assert:

- successful ingest returns and persists `transcript_intake_report`;
- input over 100 MiB is rejected before hashing, provider execution, or Run creation;
- missing, empty, and non-MP4 input is rejected before Run creation;
- provider, schema, candidate, activation, and report-insert failures mark an existing Run failed;
- every failure keeps the previous active Search unchanged and exposes no successful report;
- latest-request-wins superseded result exposes no report.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/application/test_video_provider_injection.py tests/application/test_video_publication.py -q
```

- [ ] **Step 3: Add application preflight and report access**

Add:

```python
def get_transcript_intake_report(self, run_id: str) -> TranscriptIntakeReport | None:
    return self._store.get_transcript_intake_report(run_id)


def _validate_video_input(path: Path, limits: VideoTranscriptionLimits) -> None:
    if not path.exists():
        raise VideoIngestError("input video is missing")
    if not path.is_file() or path.suffix.lower() != ".mp4":
        raise VideoIngestError("input video must be an MP4 file")
    size = path.stat().st_size
    if size == 0:
        raise VideoIngestError("input video is empty")
    if size > limits.max_input_bytes:
        raise VideoIngestError("video input exceeds 100 MiB limit")
```

Call this before `_sha256_file()`.

- [ ] **Step 4: Pass the validated report into activation**

```python
activation = self._store.activate_publication(
    run.run_id,
    transcript_intake_report=transcript.transcript_intake_report,
)
return IngestResult(
    run_id=run.run_id,
    run_state=activation.run_state,
    evidence_count=len(evidence) if activation.published else 0,
    transcript_intake_report=(
        transcript.transcript_intake_report if activation.published else None
    ),
)
```

Catch ordinary `Exception` after Run creation, attempt `mark_run_failed()` in a separate recovery transaction, and raise `VideoIngestError` from the original error. Do not catch `KeyboardInterrupt` or `SystemExit`.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/application/test_video_provider_injection.py tests/application/test_video_publication.py -q
uv run ruff check src/mke/application tests/application
uv run pyright
```

```bash
git add src/mke/application/__init__.py tests/application/test_video_provider_injection.py tests/application/test_video_publication.py
git commit -m "feat(video): publish transcript reports safely"
```

## Task 6: Expose The Report Through Existing CLI And MCP Contracts

**Files:**
- Modify: `src/mke/cli.py`
- Modify: `src/mke/interfaces/mcp_contract.py`
- Modify: `tests/interfaces/test_cli_video.py`
- Modify: `tests/interfaces/test_mcp_contract.py`

- [ ] **Step 1: Write failing output tests**

Assert successful video ingest and `run get` render only non-sensitive report fields. Assert MCP `ingest_file` and `get_run` use the exact key `transcript_intake_report`. Assert the MCP tool input schemas still contain no provider, model, cache, argv, endpoint, credential, or download fields.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/interfaces/test_cli_video.py tests/interfaces/test_mcp_contract.py -q
```

- [ ] **Step 3: Add one report payload helper**

```python
def transcript_intake_report_payload(
    report: TranscriptIntakeReport,
) -> dict[str, object]:
    return {
        "provider": report.provider,
        "model": report.model,
        "model_revision": report.model_revision,
        "library_version": report.library_version,
        "device": report.device,
        "compute_type": report.compute_type,
        "detected_language": report.detected_language,
        "media_duration_ms": report.media_duration_ms,
        "transcription_duration_ms": report.transcription_duration_ms,
        "segment_count": report.segment_count,
        "model_source": report.model_source,
    }
```

Use the same field set for CLI human formatting and MCP payloads. Do not include paths, argv, stderr, or cache data.

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/interfaces/test_cli_video.py tests/interfaces/test_mcp_contract.py -q
uv run ruff check src/mke/cli.py src/mke/interfaces tests/interfaces
uv run pyright
```

```bash
git add src/mke/cli.py src/mke/interfaces/mcp_contract.py tests/interfaces/test_cli_video.py tests/interfaces/test_mcp_contract.py
git commit -m "feat(interfaces): expose transcript intake report"
```

## Task 7: Update Protocol Documentation And Close PR 1

**Files:**
- Create: `docs/superpowers/reviews/2026-06-18-real-local-transcription-protocol-lifecycle-review.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/reference/contracts.md`
- Modify: this plan

- [ ] **Step 1: Update public-neutral contract documentation**

Document:

- optional additive `transcription` provenance;
- `ParsedVideoTranscript` and successful `TranscriptIntakeReport`;
- exact `faster-whisper-v1:<64 lowercase hex>` grammar;
- 100 MiB, 15-minute, and 10,000-segment limits;
- atomic report/Publication visibility;
- shared public error fields;
- sidecar backward compatibility;
- real ASR runtime and new commands remain for PR 2.

- [ ] **Step 2: Run complete verification**

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check
```

Expected baseline before implementation is 205 tests; the final count must be higher and recorded from actual output.

- [ ] **Step 3: Run pre-landing review and self-review**

Run `gstack-review` because this PR changes Manifest recognition, public error behavior, SQLite
transactions, and Run/Publication visibility. Persist durable public-neutral findings under:

```text
docs/superpowers/reviews/2026-06-18-real-local-transcription-protocol-lifecycle-review.md
```

Fix blockers, rerun affected tests, and then verify:

- no optional ASR dependency was introduced;
- no model download path exists;
- deterministic proof and demo still use sidecars;
- no public payload contains local paths or raw exception text;
- every faster-whisper Publication requires a successful report;
- report visibility is transactionally coupled to Publication visibility;
- the next plan can build the runtime without changing these contracts.

- [ ] **Step 4: Mark this plan complete and commit**

Change every completed checkbox to `[x]` and add a completion note with the PR number and actual verification results.

```bash
git add docs/explanation/architecture.md docs/reference/contracts.md docs/superpowers/plans/2026-06-18-real-local-transcription-protocol-lifecycle-implementation.md docs/superpowers/reviews/2026-06-18-real-local-transcription-protocol-lifecycle-review.md
git commit -m "docs(video): record transcription protocol lifecycle"
```

- [ ] **Step 5: Prepare the Chinese PR body**

Use the repository result-first format:

```markdown
## Summary

为真实本地转录建立 provider-neutral 协议、成功报告和原子 Publication 生命周期，但不安装或运行 ASR 模型。

## Completion

- [x] Transcript provenance and report contracts
- [x] Exact faster-whisper fingerprint validation
- [x] Atomic Publication and report visibility
- [x] Shared redacted CLI/MCP error contract
- [x] Sidecar and deterministic proof compatibility

## Verification

Record the actual result of every Task 7 verification command before creating the PR.

## Scope

本 PR 不包含 faster-whisper 依赖、模型下载、真实转录命令或 MCP provider 启动配置；这些属于后续顺序 PR。

## Documentation impact

Updated architecture and public contract references.
```

Do not push or create the PR until explicitly authorized.
