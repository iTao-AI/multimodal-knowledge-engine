# Real Video Intake Provider Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Completion Note

- Status: implemented locally on `codex/real-video-intake-plan`.
- PR: not created per instruction.
- Final verification on 2026-06-17:
  - `uv run pytest -q`: `199 passed, 5 warnings`
  - `uv run ruff check .`: `All checks passed!`
  - `uv run pyright`: `0 errors, 0 warnings, 0 informations`
  - `uv build`: sdist and wheel built successfully
  - `uv run mke proof run`: `proof=product status=passed cases=8 passed=8 failed=0`
  - `uv run mke demo --verify`: `result=passed duration_ms=9`
  - `git diff --check`: no output

**Goal:** Add a transcript provider port and proof-only local-command MP4 transcription smoke path while preserving deterministic sidecar proof behavior.

**Architecture:** Refactor video transcription into a `TranscriptProvider` boundary. Keep `SidecarTranscriptProvider` as the default provider, add a shared transcript schema parser, then add `LocalCommandTranscriptProvider` behind explicit injection and proof-only smoke wiring.

**Tech Stack:** Python 3.12/3.13, pytest, Ruff, Pyright strict mode, SQLite, stdlib `subprocess`, existing MKE application and MCP contract APIs.

---

## Review Findings Covered

This plan incorporates:

- `docs/superpowers/specs/2026-06-17-real-video-intake-provider-port-design.md`
- `docs/decisions/0005-optional-local-command-transcription-provider.md`
- Eng Review decisions from 2026-06-17:
  - reduce scope to Provider Port + MP4 LocalCommand Smoke,
  - use explicit `transcript_provider` dependency injection,
  - keep sidecar deterministic proof as default,
  - use shared MKE transcript JSON validation,
  - accept argv-only local command configuration,
  - avoid command override through normal CLI ingest and MCP,
  - keep real-provider smoke separate from `mke proof run` and `mke demo --verify`.

## File Structure

- Modify `src/mke/domain/__init__.py`: add `VideoTranscriptSegment`, `TranscriptExtractionResult`, and local-command fingerprint constant.
- Create `src/mke/adapters/video/errors.py`: shared `VideoExtractionError`.
- Create `src/mke/adapters/video/schema.py`: public parser and validator for `mke.video_transcript.v1`.
- Create `src/mke/adapters/video/providers.py`: `SidecarTranscriptProvider`, `LocalCommandTranscriptProvider`, and `LocalCommandTranscriptConfig`.
- Modify `src/mke/adapters/video/transcript.py`: keep backward-compatible wrapper around `SidecarTranscriptProvider`.
- Modify `src/mke/adapters/video/__init__.py`: export provider, config, result, segment, and error names.
- Modify `src/mke/application/__init__.py`: add `TranscriptProvider` protocol and inject it into `KnowledgeEngine`.
- Modify `src/mke/cli.py`: add `mke proof transcript-smoke` as a proof-only local-command smoke command.
- Modify `src/mke/proof/runner.py`: keep deterministic proof explicitly sidecar-backed.
- Add tests under `tests/adapters/`, `tests/application/`, `tests/interfaces/`, and `tests/proof/`.
- Update public docs listed in the design spec after behavior is implemented.

## Task 1: Shared Transcript Domain DTOs And Schema Parser

**Files:**
- Modify: `src/mke/domain/__init__.py`
- Create: `src/mke/adapters/video/errors.py`
- Create: `src/mke/adapters/video/schema.py`
- Modify: `src/mke/adapters/video/transcript.py`
- Modify: `src/mke/adapters/video/__init__.py`
- Modify: `tests/adapters/test_video_transcript.py`

- [x] **Step 1: Write parser tests against public functions**

Update `tests/adapters/test_video_transcript.py` so segment validation no longer imports private
`_segment_from_payload`. Add public parser tests:

```python
from mke.adapters.video.schema import parse_transcript_payload


def test_parse_transcript_payload_returns_timestamp_segments() -> None:
    segments = parse_transcript_payload(
        {
            "format": "mke.video_transcript.v1",
            "media": {
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "has_audio": True,
                "duration_ms": 2200,
            },
            "segments": [
                {"start_ms": 0, "end_ms": 1200, "text": "first"},
                {"start_ms": 1200, "end_ms": 2200, "text": "second"},
            ],
        }
    )

    assert [(segment.start_ms, segment.end_ms, segment.text) for segment in segments] == [
        (0, 1200, "first"),
        (1200, 2200, "second"),
    ]
```

- [x] **Step 2: Run the focused adapter tests and verify failure**

Run:

```bash
uv run pytest tests/adapters/test_video_transcript.py -q
```

Expected: fail because `mke.adapters.video.schema` does not exist.

- [x] **Step 3: Add domain DTOs**

In `src/mke/domain/__init__.py`, add:

```python
@dataclass(frozen=True)
class VideoTranscriptSegment:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class TranscriptExtractionResult:
    segments: tuple[VideoTranscriptSegment, ...]
    extractor_fingerprint: str
```

Also add:

```python
LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT = "local-command-video-transcript-v1"
```

- [x] **Step 4: Create the shared video error module**

Create `src/mke/adapters/video/errors.py`:

```python
class VideoExtractionError(ValueError):
    """Raised when a local video cannot produce trustworthy timestamp Evidence."""
```

Update `src/mke/adapters/video/transcript.py`, `src/mke/adapters/video/__init__.py`, and existing
tests to import `VideoExtractionError` from `mke.adapters.video.errors` or the package export.

- [x] **Step 5: Create the shared parser**

Create `src/mke/adapters/video/schema.py` with public functions:

```python
import json
from typing import Any, cast

from mke.adapters.video.errors import VideoExtractionError
from mke.domain import VideoTranscriptSegment


def parse_transcript_payload(payload: object) -> tuple[VideoTranscriptSegment, ...]:
    if not isinstance(payload, dict):
        raise VideoExtractionError("video transcript sidecar must be a JSON object")
    transcript = cast(dict[str, object], payload)
    if transcript.get("format") != "mke.video_transcript.v1":
        raise VideoExtractionError("video transcript sidecar format is unsupported")
    if transcript.get("transcription_error"):
        raise VideoExtractionError("transcription failed")
    media = _require_object(transcript, "media")
    _validate_media(media)
    raw_segments = transcript.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise VideoExtractionError("video transcript must contain at least one segment")
    return _parse_segments(raw_segments)


def load_transcript_json(text: str) -> tuple[VideoTranscriptSegment, ...]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise VideoExtractionError("video transcript sidecar is not valid JSON") from error
    return parse_transcript_payload(payload)
```

Implement `_require_object`, `_validate_media`, `_parse_segments`, and `_segment_from_payload` in
the same module. These helpers are private implementation details; tests should call
`parse_transcript_payload()` or `load_transcript_json()`.

The parser must enforce the same validation messages currently covered by video adapter tests:

- `video transcript sidecar must be a JSON object`
- `video transcript sidecar format is unsupported`
- `transcription failed`
- `video must contain an audio track`
- `unsupported codec for local video proof`
- `video transcript must contain at least one segment`
- `video transcript segment must be an object`
- `timestamp locators must be integer milliseconds`
- `stable timestamp locator generation requires increasing ranges`
- `stable timestamp locator generation requires sorted ranges`
- `video transcript text must not be empty`

- [x] **Step 6: Preserve the old wrapper**

Keep `extract_transcript_segments(path)` as a compatibility wrapper in
`src/mke/adapters/video/transcript.py`. It should read the sidecar JSON and call the shared parser.

- [x] **Step 7: Run the adapter tests**

Run:

```bash
uv run pytest tests/adapters/test_video_transcript.py -q
```

Expected: pass.

## Task 2: Sidecar Provider And Application Injection

**Files:**
- Create: `src/mke/adapters/video/providers.py`
- Modify: `src/mke/application/__init__.py`
- Modify: `src/mke/adapters/video/__init__.py`
- Create or modify: `tests/application/test_video_provider_injection.py`
- Modify: `tests/application/test_video_publication.py`

- [x] **Step 1: Write failing application injection tests**

Create `tests/application/test_video_provider_injection.py`:

```python
from pathlib import Path

from mke.application import KnowledgeEngine
from mke.domain import (
    LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
    RunState,
    TranscriptExtractionResult,
    VideoTranscriptSegment,
)


class FakeTranscriptProvider:
    def extract(self, path: Path) -> TranscriptExtractionResult:
        return TranscriptExtractionResult(
            segments=(VideoTranscriptSegment(0, 1000, "fake command transcript"),),
            extractor_fingerprint=LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
        )


def test_knowledge_engine_accepts_injected_transcript_provider(tmp_path: Path) -> None:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    engine = KnowledgeEngine(tmp_path / "mke.sqlite", transcript_provider=FakeTranscriptProvider())

    result = engine.ingest_video(video)

    assert result.run_state == RunState.PUBLISHED
    assert result.evidence_count == 1
    assert [match.text for match in engine.search("fake command")] == [
        "fake command transcript"
    ]
```

- [x] **Step 2: Run the new test and verify failure**

Run:

```bash
uv run pytest tests/application/test_video_provider_injection.py -q
```

Expected: fail because `KnowledgeEngine` does not accept `transcript_provider`.

- [x] **Step 3: Add provider classes**

Create `src/mke/adapters/video/providers.py`:

```python
@dataclass(frozen=True)
class SidecarTranscriptProvider:
    def extract(self, path: Path) -> TranscriptExtractionResult:
        segments = extract_transcript_segments(path)
        return TranscriptExtractionResult(
            segments=tuple(segments),
            extractor_fingerprint=VIDEO_TRANSCRIPT_FINGERPRINT,
        )
```

- [x] **Step 4: Add `TranscriptProvider` protocol and injection**

In `src/mke/application/__init__.py`, add:

```python
class TranscriptProvider(Protocol):
    def extract(self, path: Path) -> TranscriptExtractionResult:
        raise NotImplementedError
```

Update `KnowledgeEngine.__init__`:

```python
def __init__(
    self,
    db_path: Path,
    pdf_extractor: PdfExtractor | None = None,
    transcript_provider: TranscriptProvider | None = None,
) -> None:
    self._store = SQLiteStore(db_path)
    self._pdf_extractor = pdf_extractor or PyMuPDFPdfExtractor()
    self._transcript_provider = transcript_provider or SidecarTranscriptProvider()
```

Update `_process_video()` to call:

```python
transcript = self._transcript_provider.extract(path)
segments = transcript.segments
evidence = [
    CandidateEvidence(
        evidence_id=f"ev_{uuid4().hex}",
        locator_kind="timestamp_ms",
        locator_start=segment.start_ms,
        locator_end=segment.end_ms,
        text=segment.text,
    )
    for segment in segments
]
manifest = RunManifest(
    run_id=run.run_id,
    evidence_count=len(evidence),
    required_stages=tuple(sorted(REQUIRED_VIDEO_STAGES)),
    extractor_fingerprint=transcript.extractor_fingerprint,
    asset_sha256=asset_sha256,
)
```

- [x] **Step 5: Run video application tests**

Run:

```bash
uv run pytest tests/application/test_video_provider_injection.py tests/application/test_video_publication.py -q
```

Expected: pass.

## Task 3: Local Command Transcript Provider

**Files:**
- Modify: `src/mke/adapters/video/providers.py`
- Create: `tests/adapters/test_local_command_transcript_provider.py`

- [x] **Step 1: Write success and failure tests with fake commands**

Create `tests/adapters/test_local_command_transcript_provider.py`. Use temporary Python scripts as
fake commands. The success test should emit a valid `mke.video_transcript.v1` object to stdout:

```python
import sys
from pathlib import Path

import pytest

from mke.adapters.video import VideoExtractionError
from mke.adapters.video.providers import (
    LocalCommandTranscriptConfig,
    LocalCommandTranscriptProvider,
)


def test_local_command_provider_parses_stdout_json(tmp_path: Path) -> None:
    script = tmp_path / "emit_transcript.py"
    script.write_text(
        "import json, sys\n"
        "print(json.dumps({"
        "'format':'mke.video_transcript.v1',"
        "'media':{'container':'mp4','video_codec':'h264','audio_codec':'aac','has_audio':True,'duration_ms':1000},"
        "'segments':[{'start_ms':0,'end_ms':1000,'text':'local command transcript'}]"
        "}))\n"
    )
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(argv=(sys.executable, str(script), "{input}"))
    )

    result = provider.extract(video)

    assert result.segments[0].text == "local command transcript"
```

Also cover:

- config accepts list `argv` and normalizes it to a tuple,
- config rejects string `argv`,
- config rejects missing `{input}`,
- config rejects duplicate `{input}`,
- missing executable raises `VideoExtractionError`,
- non-zero exit raises `VideoExtractionError`,
- timeout raises `VideoExtractionError`,
- invalid JSON raises `VideoExtractionError`,
- oversized stdout raises `VideoExtractionError`,
- oversized stderr raises `VideoExtractionError`,
- invalid transcript ranges are rejected by the shared schema parser.

- [x] **Step 2: Run the tests and verify failure**

Run:

```bash
uv run pytest tests/adapters/test_local_command_transcript_provider.py -q
```

Expected: fail because `LocalCommandTranscriptProvider` does not exist.

- [x] **Step 3: Implement config validation**

In `src/mke/adapters/video/providers.py`, add:

```python
from collections.abc import Sequence
from dataclasses import dataclass

from mke.domain import LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT


@dataclass(frozen=True)
class LocalCommandTranscriptConfig:
    argv: Sequence[str]
    timeout_seconds: float = 60.0
    max_stdout_bytes: int = 1024 * 1024
    max_stderr_bytes: int = 64 * 1024
    extractor_fingerprint: str = LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT

    def __post_init__(self) -> None:
        if isinstance(self.argv, str) or not isinstance(self.argv, Sequence):
            raise TypeError("argv must be a non-empty sequence of strings")
        normalized = tuple(self.argv)
        if not normalized:
            raise TypeError("argv must be a non-empty sequence of strings")
        if any(not isinstance(part, str) or not part for part in normalized):
            raise TypeError("argv must contain non-empty strings")
        if normalized.count("{input}") != 1:
            raise ValueError("argv must contain exactly one {input} placeholder")
        object.__setattr__(self, "argv", normalized)
```

- [x] **Step 4: Implement local command extraction**

Implement `LocalCommandTranscriptProvider.extract(path)`:

- check the input file exists,
- replace `{input}` with `str(path)`,
- call `subprocess.run(command, shell=False, capture_output=True, timeout=config.timeout_seconds)`,
- reject stdout/stderr above configured limits before JSON parsing or diagnostic handling,
- reject non-zero exit without exposing argv or raw stderr,
- decode stdout as UTF-8,
- parse with shared `load_transcript_json`,
- return `TranscriptExtractionResult`.

Stable public errors should include:

- `input video is missing`
- `transcript command executable is missing`
- `transcript command timed out`
- `transcript command failed`
- `transcript command produced too much stdout`
- `transcript command produced too much stderr`
- `transcript command stdout is not valid UTF-8`
- parser validation errors from the shared schema.

- [x] **Step 5: Run adapter tests**

Run:

```bash
uv run pytest tests/adapters/test_video_transcript.py tests/adapters/test_local_command_transcript_provider.py -q
```

Expected: pass.

## Task 4: Fail-Closed Publication Lifecycle With Local Provider

**Files:**
- Modify: `tests/application/test_video_provider_injection.py`
- Modify: `src/mke/application/__init__.py`

- [x] **Step 1: Write a regression test for failed provider isolation**

Add:

```python
class FailingTranscriptProvider:
    def extract(self, path: Path) -> TranscriptExtractionResult:
        raise VideoExtractionError("transcript command failed")


def test_failed_transcript_provider_leaves_active_search_unchanged(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")
    before = [match.text for match in engine.search("timestamp proof")]
    failed_video = tmp_path / "failed.mp4"
    failed_video.write_bytes(b"fake mp4 bytes")
    failing = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        transcript_provider=FailingTranscriptProvider(),
    )

    with pytest.raises(VideoIngestError, match="transcript command failed"):
        failing.ingest_video(failed_video)

    assert [match.text for match in engine.search("timestamp proof")] == before
```

- [x] **Step 2: Run the regression test**

Run:

```bash
uv run pytest tests/application/test_video_provider_injection.py -q
```

Expected: pass once Task 2 is implemented. If it fails, fix `_process_video()` so provider errors
are caught in the existing `VideoIngestError` fail-closed branch.

## Task 5: Proof-Only Local Command Smoke

**Files:**
- Modify: `src/mke/cli.py`
- Create: `tests/interfaces/test_cli_transcript_smoke.py`

- [x] **Step 1: Write CLI smoke tests**

Add a test that writes a temporary fake transcriber script under `tmp_path` and invokes:

```bash
mke proof transcript-smoke --fixture <tmp-video> -- <python> <fake-script> {input}
```

Assertions:

- exit code `0`,
- stdout includes `proof=transcript_smoke status=passed`,
- stdout includes `provider=local_command`,
- stdout includes `evidence_count=1`,
- no absolute temp path appears in stdout.

Add failure tests for:

- missing `--` command,
- command without `{input}`,
- command emitting invalid JSON.

- [x] **Step 2: Run the smoke tests and verify failure**

Run:

```bash
uv run pytest tests/interfaces/test_cli_transcript_smoke.py -q
```

Expected: fail because the CLI command does not exist.

- [x] **Step 3: Add CLI parser branch**

In `src/mke/cli.py`, extend `mke proof`:

```python
proof_smoke = proof_subcommands.add_parser("transcript-smoke")
proof_smoke.add_argument("--fixture", type=Path, required=True)
proof_smoke.add_argument("command", nargs=argparse.REMAINDER)
```

Normalize a leading `--` separator in `args.command`. Build
`LocalCommandTranscriptProvider(LocalCommandTranscriptConfig(argv=tuple(command)))`.

Use a temporary SQLite database and `KnowledgeEngine(db_path, transcript_provider=provider)` to
ingest the fixture. Print stable output:

```text
mke proof transcript-smoke
proof=transcript_smoke status=passed provider=local_command evidence_count=<n>
```

On failure, reuse the CLI error contract with `problem=video_ingest_failed`.

- [x] **Step 4: Run CLI smoke tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_transcript_smoke.py -q
```

Expected: pass.

## Task 6: Guard Deterministic Proof And MCP Boundaries

**Files:**
- Modify: `tests/proof/test_runner.py`
- Modify: `tests/interfaces/test_cli_demo.py` or `tests/interfaces/test_cli_video.py`
- Modify: `tests/interfaces/test_mcp_contract.py`
- Modify: `src/mke/proof/runner.py`

- [x] **Step 1: Add proof determinism tests**

Add tests proving:

- `run_product_proof()` still passes with sidecar fixtures,
- `mke demo --verify` still passes and prints existing phase lines,
- neither proof path requires a local command provider.

If implementation introduces any process-level provider configuration later, these tests must
explicitly force `SidecarTranscriptProvider`.

- [x] **Step 2: Add MCP boundary tests**

Add tests proving:

- MCP `ingest_file(config, path)` accepts only `config` and `path`,
- MCP `.mp4` ingest still uses the default sidecar provider,
- MCP cannot receive command argv in the request payload,
- MCP video failures return `video_ingest_failed` without argv, stderr, stack traces, or absolute
  local paths.

- [x] **Step 3: Run proof and MCP tests**

Run:

```bash
uv run pytest tests/proof tests/interfaces/test_cli_demo.py tests/interfaces/test_cli_video.py tests/interfaces/test_mcp_contract.py -q
uv run mke proof run
uv run mke demo --verify
```

Expected:

- pytest passes,
- `mke proof run` prints `proof=product status=passed`,
- `mke demo --verify` prints `result=passed`.

## Task 7: Documentation Updates

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/reference/contracts.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/how-to/run-local-product-proof.md`
- Modify: `docs/superpowers/plans/2026-06-17-real-video-intake-provider-port-implementation.md`

- [x] **Step 1: Update public docs**

Document:

- sidecar remains the default deterministic provider,
- `LocalCommandTranscriptProvider` is optional and local-only,
- MCP does not accept command overrides,
- `mke proof transcript-smoke` is proof-only,
- real speech-model runtimes are still not bundled.

- [x] **Step 2: Mark this plan as completed**

At the top of this plan, add a completion note with the PR number and final verification results.
Keep checklist items accurate.

- [x] **Step 3: Scan for stale non-goals**

Run:

```bash
rg -n "real speech-model transcription|real transcription|LocalCommand|transcript-smoke|sidecar" README.md README_CN.md docs src tests
```

Expected: docs should distinguish "not bundled" from "optional local command provider exists".

## Task 8: Final Verification And PR Preparation

**Files:**
- No new files expected.

- [x] **Step 1: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check
```

Expected:

- all tests pass,
- Ruff passes,
- Pyright reports zero errors,
- build succeeds,
- product proof passes,
- compatibility demo passes,
- `git diff --check` prints no output.

- [x] **Step 2: Review the diff**

Run:

```bash
git status --short
git diff --stat
git diff -- docs src tests pyproject.toml
```

Check:

- no private paths,
- no provider credentials,
- no raw stderr or argv in public errors,
- no unrelated formatting churn,
- no changes to deterministic proof output except intentional docs.

- [x] **Step 3: Commit**

Use a focused commit message:

```bash
git add <intentional-files>
git commit -m "feat(video): add transcript provider port"
```

- [x] **Step 4: Prepare a Simplified Chinese PR body**

Use the repository PR format. The PR body should contain these concrete facts after Step 1 records
the exact verification outputs:

- Summary: transcript provider port, shared schema validation, local-command provider, proof-only
  smoke command, and deterministic proof preservation.
- Completion: provider injection completed, local command smoke completed, MCP command override not
  exposed, proof and demo still pass.
- Verification: copy exact results from `uv run pytest -q`, `uv run ruff check .`, `uv run pyright`,
  `uv build`, `uv run mke proof run`, `uv run mke demo --verify`, and `git diff --check`.
- Scope: MP4 local-command smoke only; no audio-only ingest, no bundled ASR runtime, no cloud
  provider, no diarization, no HTTP, no workspace UI.
- Risk / Impact: deterministic proof remains sidecar-backed; rollback removes the provider classes,
  smoke command, and related docs while preserving existing sidecar ingest.
