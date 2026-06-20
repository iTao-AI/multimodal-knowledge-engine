# Real Local Transcription Runtime And Interfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the optional cache-only `faster-whisper` runtime, explicit model preparation and read-only diagnostics, and one owner-configured runtime path shared by CLI and stdio MCP.

**Architecture:** Resolve the exact model revision through a typed owner configuration, execute ASR in the package-owned adapter subprocess, parse its bounded stdout through the PR 1 protocol, and build `KnowledgeEngine` through one composition root. CLI and MCP select only trusted startup policy; MCP tool schemas remain unchanged.

**Tech Stack:** Python 3.12/3.13, faster-whisper, CTranslate2, PyAV, huggingface_hub, MCP Python SDK, asyncio, subprocess, pytest, uv.

## Completion Record

- Status: completed and merged through PR #17 as `7a8c82b` after authoritative review
  remediation; post-merge CI passed.
- Scope: PR 2 only. No model, spoken fixture, real ASR proof, or PR 3 deployment proof was added.
- Review: the authoritative gstack review identified eight findings. All eight were independently
  reproduced, fixed with regression coverage, and recorded in
  `docs/superpowers/reviews/2026-06-18-real-local-transcription-runtime-interfaces-review.md`.
- Verification: `364 passed, 5 warnings`; Ruff passed; Pyright reported zero errors; build,
  eight-case product proof, demo verification, `git diff --check`, and the Python 3.13 model-free
  `wheel[transcription]` install/import/empty-cache doctor gate passed.

---

## Prerequisites And PR Boundary

- Start only after the protocol/lifecycle PR is merged.
- Sync latest `main`, create an isolated worktree, and use branch `codex/transcription-runtime-interfaces`.
- Read the approved D3-B design, Autoplan review, and completed protocol/lifecycle plan.
- Before coding against third-party APIs, verify the locked versions' signatures in official docs or installed source:
  - `huggingface_hub.snapshot_download(..., revision=..., local_files_only=...)`;
  - `faster_whisper.WhisperModel(...)`;
  - `WhisperModel.transcribe(...)`;
  - PyAV container/stream metadata;
  - FastMCP lifespan and async tool behavior.
- Do not add the real spoken fixture, real-model proof, wheel deployment proof, HTTP, remote ASR, queues, or vendor APIs in this PR.
- Required tests must not download model weights or require a model cache.

## File Structure

### Create

- `src/mke/runtime.py`: typed runtime configuration, process controller, provider factory, engine factory, and readiness preflight.
- `src/mke/adapters/video/faster_whisper.py`: model identity validation, exact-revision resolution, preparation, doctor, media probe, timestamp normalization, and ASR execution.
- `src/mke/adapters/video/faster_whisper_cli.py`: thin package-owned adapter process entrypoint and stable exit codes.
- `src/mke/adapters/video/process.py`: thread-safe active child registry and termination.
- `tests/runtime/test_runtime_composition.py`: one composition path for CLI and MCP.
- `tests/adapters/test_faster_whisper.py`: resolver, probe, normalization, ASR materialization, and redaction.
- `tests/adapters/test_faster_whisper_cli.py`: adapter stdout/exit-code protocol.
- `tests/interfaces/test_cli_transcription.py`: prepare, doctor, provider-selected ingest, JSON, and no-Run contracts.
- `tests/interfaces/test_mcp_transcription_runtime.py`: owner configuration, preflight, schema, cancellation, and shutdown.

### Modify

- `pyproject.toml`: optional transcription extra and adapter script.
- `uv.lock`: resolved optional dependency graph.
- `src/mke/adapters/video/providers.py`: first-party exit map, provenance requirement, process controller, and cancellation cleanup.
- `src/mke/adapters/video/__init__.py`: runtime exports.
- `src/mke/application/__init__.py`: engine/provider close behavior where required.
- `src/mke/cli.py`: typed startup flags, prepare, doctor, JSON ingest/run inspection, and shared factory.
- `src/mke/interfaces/mcp_contract.py`: build engines through runtime config.
- `src/mke/interfaces/mcp_server.py`: owner preflight, async cancellation, and lifespan cleanup.
- `tests/adapters/test_local_command_transcript_provider.py`: stable exit mapping and BaseException cleanup.
- `tests/interfaces/test_cli_mcp.py`: startup flags and safe preflight.
- `tests/interfaces/test_mcp_contract.py`: shared factory and unchanged request fields.
- `.github/workflows/ci.yml`: model-free wheel-extra install on Python 3.12 and 3.13.
- `docs/decisions/0006-first-party-local-transcription-runtime.md`: dependency, subprocess, model, revision, and download policy.
- `docs/explanation/architecture.md`: runtime composition and adapter process.
- `docs/reference/cli.md`: exact commands, flags, exit codes, and JSON shapes.
- `docs/reference/contracts.md`: owner configuration and error semantics.
- `docs/how-to/use-mke-mcp.md`: owner-configured faster-whisper MCP startup.
- `docs/how-to/use-local-transcription.md`: install, prepare, doctor, ingest, and recovery.

## Task 1: Add Optional Dependencies And Typed Runtime Configuration

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/mke/runtime.py`
- Create: `tests/runtime/test_runtime_composition.py`

- [x] **Step 1: Write failing configuration tests**

Cover:

- sidecar is the default;
- faster-whisper defaults are `small`, approved revision, CPU, `int8`, language auto;
- model identifiers reject absolute paths, relative paths, `..`, empty values, and malformed repository IDs;
- revision must be exactly 40 lowercase hex characters;
- language syntax is normalized to `auto` or `[a-z]{2,3}`, doctor verifies the explicit code is
  supported by the resolved model before a Run starts, and the value is propagated into
  first-party provenance;
- timeout/capture/resource limits must be positive and bounded;
- download permission exists only on `ModelPreparationConfig`;
- runtime config has one shared `ActiveProcessController`.

- [x] **Step 2: Verify RED**

```bash
uv run pytest tests/runtime/test_runtime_composition.py -q
```

- [x] **Step 3: Declare optional dependencies and scripts**

Add:

```toml
[project.optional-dependencies]
transcription = [
  "faster-whisper>=1.2.1,<2",
  "av>=11,<18",
  "huggingface-hub>=0.33,<2",
]

[project.scripts]
mke = "mke.cli:console_main"
mke-transcribe-faster-whisper = "mke.adapters.video.faster_whisper_cli:console_main"
```

Then run:

```bash
uv lock
uv sync --locked
```

The ordinary sync must keep working without the extra. Do not download a model.

- [x] **Step 4: Implement typed configuration**

Use a discriminated union:

```python
@dataclass(frozen=True)
class SidecarTranscriptionConfig:
    provider: Literal["sidecar"] = "sidecar"


@dataclass(frozen=True)
class FasterWhisperTranscriptionConfig:
    provider: Literal["faster-whisper"] = "faster-whisper"
    model: str = "small"
    model_revision: str = DEFAULT_MODEL_REVISION
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "auto"
    cache_dir: Path | None = None
    limits: VideoTranscriptionLimits = VideoTranscriptionLimits()


@dataclass(frozen=True)
class ModelPreparationConfig:
    transcription: FasterWhisperTranscriptionConfig
    allow_model_download: bool = False


TranscriptionConfig = SidecarTranscriptionConfig | FasterWhisperTranscriptionConfig


@dataclass(frozen=True)
class RuntimeConfig:
    db_path: Path
    transcription: TranscriptionConfig = SidecarTranscriptionConfig()
    process_controller: ActiveProcessController = field(
        default_factory=ActiveProcessController,
        compare=False,
    )
```

Import `ActiveProcessController` from `mke.adapters.video.process`; do not define it in
`runtime.py`, because both the runtime factory and provider need it and a runtime/provider import
cycle is not acceptable. Validate values in `__post_init__`; do not accept arbitrary dictionaries.

- [x] **Step 5: Run tests and commit**

```bash
uv run pytest tests/runtime/test_runtime_composition.py -q
uv run ruff check pyproject.toml src/mke/runtime.py tests/runtime
uv run pyright
```

```bash
git add pyproject.toml uv.lock src/mke/runtime.py tests/runtime/test_runtime_composition.py
git commit -m "feat(video): add transcription runtime config"
```

## Task 2: Implement Exact-Revision Resolution, Prepare, And Doctor

**Files:**
- Create: `src/mke/adapters/video/faster_whisper.py`
- Create: `tests/adapters/test_faster_whisper.py`

- [x] **Step 1: Write failing resolver and readiness tests**

Mock every network/model boundary. Cover:

- `small` maps to `Systran/faster-whisper-small`;
- exact revision and optional cache directory are passed to `snapshot_download`;
- normal resolution and doctor always set `local_files_only=True`;
- prepare retries with `local_files_only=False` only when `allow_model_download=True`;
- prepare reports `already_cached` or `downloaded`;
- missing dependency, cache miss, bad revision, permission error, and unsupported device/compute profile return stable typed results;
- no result contains the resolved snapshot path or cache path;
- prepare and doctor never open SQLite or create a Run.

- [x] **Step 2: Verify RED**

```bash
uv run pytest tests/adapters/test_faster_whisper.py -q
```

- [x] **Step 3: Implement strict model identity resolution**

Use lazy imports so core installation remains usable:

```python
def resolve_model_snapshot(
    config: FasterWhisperTranscriptionConfig,
    *,
    allow_download: bool,
) -> Path:
    from huggingface_hub import snapshot_download

    repo_id = normalize_model_identifier(config.model)
    try:
        resolved = snapshot_download(
            repo_id=repo_id,
            revision=config.model_revision,
            cache_dir=str(config.cache_dir) if config.cache_dir is not None else None,
            local_files_only=not allow_download,
        )
    except Exception as error:
        raise classify_model_resolution_error(error, allow_download=allow_download) from error
    return Path(resolved)
```

`classify_model_resolution_error()` must return project-owned stable failures and log internal details separately. Never use raw exception text as a public cause.

- [x] **Step 4: Implement preparation and read-only doctor DTOs**

```python
@dataclass(frozen=True)
class ModelPreparationResult:
    status: Literal["already_cached", "downloaded"]
    provider: str
    model: str
    model_revision: str


@dataclass(frozen=True)
class TranscriptionReadiness:
    status: Literal["ready", "not_ready"]
    checks: tuple[ReadinessCheck, ...]
    cause: str | None
    next_step: str | None
```

`prepare_model()` must first attempt local-only resolution and only call network-enabled resolution after explicit opt-in. `doctor_transcription()` checks imports, config/profile, and cache-only resolution; it never transcribes or mutates cache.

- [x] **Step 5: Run tests and commit**

```bash
uv run pytest tests/adapters/test_faster_whisper.py -q
uv run ruff check src/mke/adapters/video/faster_whisper.py tests/adapters/test_faster_whisper.py
uv run pyright
```

```bash
git add src/mke/adapters/video/faster_whisper.py tests/adapters/test_faster_whisper.py
git commit -m "feat(video): add model preparation and doctor"
```

## Task 3: Implement Media Probe, Timestamp Normalization, And Adapter Protocol

**Files:**
- Modify: `src/mke/adapters/video/faster_whisper.py`
- Create: `src/mke/adapters/video/faster_whisper_cli.py`
- Create: `tests/adapters/test_faster_whisper_cli.py`
- Modify: `tests/adapters/test_faster_whisper.py`

- [x] **Step 1: Write failing probe and normalization tests**

Use fake PyAV containers and fake `WhisperModel` objects. Cover:

- MP4/H.264/AAC with at least one audio stream succeeds;
- wrong container/codec, missing audio, zero duration, and duration over 900000 ms fail before model construction;
- 100 MiB exactly succeeds and one byte over fails before opening PyAV;
- `floor(seconds * 1000 + 0.5)`;
- non-finite/negative values fail;
- at most 1 ms overlap clamps to prior end;
- larger overlap and zero-length normalized segments fail;
- text trims and empty text fails;
- provider order is preserved;
- generator is fully consumed before any JSON is emitted;
- more than 10,000 normalized segments fails.

- [x] **Step 2: Verify RED**

```bash
uv run pytest tests/adapters/test_faster_whisper.py tests/adapters/test_faster_whisper_cli.py -q
```

- [x] **Step 3: Implement media probe and timestamp normalization**

Use PyAV only inside the optional adapter:

```python
def normalize_timestamp_ms(seconds: float) -> int:
    if not math.isfinite(seconds) or seconds < 0:
        raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
    return math.floor(seconds * 1000 + 0.5)
```

`probe_media()` opens the file with PyAV, derives actual codec names and positive duration, closes the container in `finally`, and returns `VideoMediaInfo`. Do not invoke `ffmpeg` or `ffprobe`.

- [x] **Step 4: Implement cache-only ASR execution**

```python
def transcribe_media(
    path: Path,
    config: FasterWhisperTranscriptionConfig,
) -> ParsedVideoTranscript:
    media = probe_media(path, config.limits)
    snapshot = resolve_model_snapshot(config, allow_download=False)
    from faster_whisper import WhisperModel

    model = WhisperModel(
        str(snapshot),
        device=config.device,
        compute_type=config.compute_type,
        local_files_only=True,
    )
    raw_segments, info = model.transcribe(
        str(path),
        language=None if config.language == "auto" else config.language,
    )
    materialized = tuple(raw_segments)
    segments = normalize_segments(materialized, media, config.limits)
    return build_first_party_transcript(
        media,
        segments,
        info,
        config,
        requested_language=config.language,
    )
```

If the locked constructor does not accept `local_files_only` when given a snapshot path, remove only that redundant keyword after verifying installed source; cache-only behavior remains enforced by prior exact snapshot resolution.

- [x] **Step 5: Implement a thin stable adapter CLI**

`faster_whisper_cli.main(argv)` must:

1. parse package-owned internal arguments;
2. validate config and input;
3. call `transcribe_media()`;
4. write exactly one compact `mke.video_transcript.v1` object to stdout on success;
5. write diagnostics only to stderr;
6. return the versioned `AdapterExitCode` on known failure;
7. return a generic transcription exit code on unexpected `Exception`;
8. never catch `KeyboardInterrupt` or `SystemExit`;
9. never serialize raw exception text.

- [x] **Step 6: Run tests and commit**

```bash
uv run pytest tests/adapters/test_faster_whisper.py tests/adapters/test_faster_whisper_cli.py -q
uv run ruff check src/mke/adapters/video tests/adapters
uv run pyright
```

```bash
git add src/mke/adapters/video/faster_whisper.py src/mke/adapters/video/faster_whisper_cli.py tests/adapters/test_faster_whisper.py tests/adapters/test_faster_whisper_cli.py
git commit -m "feat(video): add faster whisper adapter"
```

## Task 4: Bind The First-Party Adapter Through The Existing Process Boundary

**Files:**
- Create: `src/mke/adapters/video/process.py`
- Modify: `src/mke/adapters/video/providers.py`
- Modify: `src/mke/application/__init__.py`
- Modify: `src/mke/runtime.py`
- Modify: `tests/adapters/test_local_command_transcript_provider.py`
- Modify: `tests/runtime/test_runtime_composition.py`

- [x] **Step 1: Write failing provider and cancellation tests**

Assert:

- factory argv begins with `sys.executable, "-m", "mke.adapters.video.faster_whisper_cli"`;
- it contains exactly one `{input}`;
- no PATH lookup or shell is used;
- known adapter exit codes map to stable causes and next steps;
- unknown return codes map to a generic safe failure;
- first-party output requires complete provenance;
- `KeyboardInterrupt`, task cancellation signal, and owner shutdown kill and wait for the active child;
- stderr, argv, cache path, input path, and exception text never enter the public failure.

- [x] **Step 2: Verify RED**

```bash
uv run pytest tests/adapters/test_local_command_transcript_provider.py tests/runtime/test_runtime_composition.py -q
```

- [x] **Step 3: Add a thread-safe active process controller**

```python
class ActiveProcessController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: set[subprocess.Popen[bytes]] = set()

    def register(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes.add(process)

    def unregister(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes.discard(process)

    def cancel_active(self) -> None:
        with self._lock:
            processes = tuple(self._processes)
        for process in processes:
            _kill_process(process)
```

Register immediately after spawn and unregister in `finally`. In `_run_bounded_command()`, catch `BaseException` only to kill/wait, then re-raise unchanged. This cleanup must not convert `KeyboardInterrupt` or `SystemExit` into a product error.

- [x] **Step 4: Extend local-command configuration for first-party protocol**

Add immutable fields:

```python
require_provenance: bool = False
exit_code_errors: Mapping[int, AdapterFailureSpec] = field(default_factory=dict)
process_controller: ActiveProcessController | None = None
```

Keep `AdapterFailureSpec(problem, cause, next_step)` in the video adapter contracts so the adapter
does not depend on the interface layer. The generic D3-A provider keeps its old fallback. The
faster-whisper factory supplies the stable exit map and `require_provenance=True`.

When `require_provenance=True`, derive all successful identity from the validated actual output:

```python
provenance = parsed.transcription_provenance
if provenance is None:
    raise VideoExtractionError("transcript provenance is required")
report = transcript_intake_report_from(parsed)
fingerprint = faster_whisper_fingerprint(provenance)
return TranscriptExtractionResult(
    parsed_transcript=parsed,
    extractor_fingerprint=fingerprint,
    transcript_intake_report=report,
)
```

Do not use merely requested config values for the report or dynamic fingerprint.
The adapter writes the normalized requested language into the validated provenance before this
step; the report and fingerprint therefore distinguish `auto` from an explicit language override.

- [x] **Step 5: Implement the provider and engine factories**

```python
def build_transcript_provider(config: RuntimeConfig) -> TranscriptProvider:
    if isinstance(config.transcription, SidecarTranscriptionConfig):
        return SidecarTranscriptProvider()
    command = first_party_adapter_argv(config.transcription)
    return LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(
            argv=command,
            timeout_seconds=config.transcription.limits.timeout_seconds,
            max_stdout_bytes=config.transcription.limits.max_stdout_bytes,
            max_stderr_bytes=config.transcription.limits.max_stderr_bytes,
            require_provenance=True,
            exit_code_errors=FIRST_PARTY_EXIT_ERRORS,
            process_controller=config.process_controller,
        )
    )


def build_engine(config: RuntimeConfig) -> KnowledgeEngine:
    return KnowledgeEngine(
        config.db_path,
        transcript_provider=build_transcript_provider(config),
    )
```

- [x] **Step 6: Run tests and commit**

```bash
uv run pytest tests/adapters/test_local_command_transcript_provider.py tests/runtime/test_runtime_composition.py -q
uv run ruff check src/mke/runtime.py src/mke/adapters/video/providers.py tests
uv run pyright
```

```bash
git add src/mke/runtime.py src/mke/adapters/video/process.py src/mke/adapters/video/providers.py src/mke/application/__init__.py tests/adapters/test_local_command_transcript_provider.py tests/runtime/test_runtime_composition.py
git commit -m "feat(video): compose first party transcript provider"
```

## Task 5: Add Prepare, Doctor, And JSON CLI Contracts

**Files:**
- Modify: `src/mke/cli.py`
- Create: `tests/interfaces/test_cli_transcription.py`
- Modify: `tests/interfaces/test_cli_video.py`
- Modify: `tests/interfaces/test_cli_error_contract.py`

- [x] **Step 1: Write failing CLI tests**

Cover:

- `mke transcription prepare` without `--allow-model-download` is a usage error;
- prepare is the only CLI path that calls network-enabled resolution;
- prepare never opens the DB and creates no Run;
- doctor is read-only and exits 0 ready, 1 not-ready, 2 usage;
- prepare and doctor `--json` each write exactly one JSON object to stdout;
- `mke ingest ... --transcript-provider faster-whisper --json` uses the shared runtime factory;
- default ingest remains sidecar-backed;
- ingest and `run get --json` include `transcript_intake_report`;
- JSON stdout has no logs or paths;
- stable failures are identical to the shared public serializer.

- [x] **Step 2: Verify RED**

```bash
uv run pytest tests/interfaces/test_cli_transcription.py tests/interfaces/test_cli_video.py tests/interfaces/test_cli_error_contract.py -q
```

- [x] **Step 3: Add reusable owner configuration arguments**

Add `add_transcription_runtime_arguments(parser)` with:

```text
--transcript-provider sidecar|faster-whisper
--model
--model-revision
--device
--compute-type
--language
--model-cache
--transcription-timeout-seconds
```

These are local operator/startup controls. Never add command argv, endpoint, or credentials.

- [x] **Step 4: Add prepare and doctor subcommands**

The CLI tree is:

```text
mke transcription prepare --allow-model-download [runtime flags] [--json]
mke transcription doctor [runtime flags] [--json]
```

Prepare does not accept `--db` behaviorally even though the global parser has a default; its handler must not build an engine. Doctor uses `doctor_transcription()` directly.

- [x] **Step 5: Add one-object JSON serializers**

Use explicit payload builders rather than `dataclasses.asdict()`. Include only stable documented fields. Human output may be multi-line; JSON output must call `print(json.dumps(payload))` exactly once and route logs to stderr.

- [x] **Step 6: Route normal commands through the composition root**

Replace direct `KnowledgeEngine(args.db)` construction with:

```python
runtime = runtime_config_from_args(args)
engine = build_engine(runtime)
```

Keep `mke proof run` and `mke demo --verify` on their existing deterministic sidecar construction path.

- [x] **Step 7: Run tests and commit**

```bash
uv run pytest tests/interfaces/test_cli_transcription.py tests/interfaces/test_cli_video.py tests/interfaces/test_cli_error_contract.py -q
uv run ruff check src/mke/cli.py tests/interfaces
uv run pyright
```

```bash
git add src/mke/cli.py tests/interfaces/test_cli_transcription.py tests/interfaces/test_cli_video.py tests/interfaces/test_cli_error_contract.py
git commit -m "feat(cli): add transcription setup and ingest"
```

## Task 6: Route Owner-Configured MCP Through The Same Runtime

**Files:**
- Modify: `src/mke/interfaces/mcp_contract.py`
- Modify: `src/mke/interfaces/mcp_server.py`
- Modify: `src/mke/cli.py`
- Create: `tests/interfaces/test_mcp_transcription_runtime.py`
- Modify: `tests/interfaces/test_mcp_contract.py`
- Modify: `tests/interfaces/test_mcp_server.py`
- Modify: `tests/interfaces/test_cli_mcp.py`

- [x] **Step 1: Write failing owner-policy and schema tests**

Assert:

- MCP startup accepts the same trusted flags as CLI;
- cache miss or unsupported profile exits before stdio protocol startup;
- startup never enables download;
- every contract function calls `build_engine(config.runtime)`;
- tool input schemas remain exactly `path`, `run_id`, `query/limit`, and `question/limit`;
- no tool accepts provider, model, revision, cache, argv, endpoint, credential, or download policy;
- CLI and MCP provider factories receive equal typed config;
- MCP output includes the transcript report without local paths.

- [x] **Step 2: Verify RED**

```bash
uv run pytest tests/interfaces/test_mcp_transcription_runtime.py tests/interfaces/test_mcp_contract.py tests/interfaces/test_mcp_server.py tests/interfaces/test_cli_mcp.py -q
```

- [x] **Step 3: Make MCP runtime configuration explicit**

```python
@dataclass(frozen=True)
class McpRuntimeConfig:
    runtime: RuntimeConfig
    allowed_root: Path

    @property
    def db_path(self) -> Path:
        return self.runtime.db_path
```

Provide a compatibility constructor/helper only if existing tests or internal callers require it; do not maintain a second provider-building path.

- [x] **Step 4: Add preflight before stdio startup**

`run_mcp_server()` must call the same read-only readiness function when the owner selected faster-whisper. On failure, render one safe message to stderr, return 1, and never call `FastMCP.run()`.

- [x] **Step 5: Add cancellation-safe async ingest**

Use the shared controller and an async tool wrapper:

```python
async def ingest_file(path: str) -> dict[str, Any]:
    worker = asyncio.create_task(
        asyncio.to_thread(mcp_contract.ingest_file, config, path)
    )
    try:
        # Shield keeps request cancellation from cancelling the wrapper task while
        # the underlying worker thread is still performing lifecycle cleanup.
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        config.runtime.process_controller.cancel_active()
        with suppress(Exception):
            await asyncio.shield(worker)
        raise
```

Configure a FastMCP lifespan whose `finally` calls `cancel_active()`. The application thread must finish its failure cleanup so a created Run becomes failed and no candidate becomes searchable. Add a bounded test timeout to prevent hanging CI.
The cancellation test must prove the worker task was not marked cancelled by the request, the
subprocess was killed, and the worker completed the failed-Run recovery before the tool returned
`CancelledError`. Keep the timeout in the test harness, not around production cleanup: swallowing a
cleanup timeout would let the tool return while a worker could still mutate Run state.

- [x] **Step 6: Preserve safe async error handling**

Extend the safe tool decorator or add a dedicated async equivalent that:

- re-raises `CancelledError`;
- logs unexpected internal exceptions;
- returns the shared generic public error for ordinary `Exception`;
- never catches `BaseException`.

- [x] **Step 7: Run tests and commit**

```bash
uv run pytest tests/interfaces/test_mcp_transcription_runtime.py tests/interfaces/test_mcp_contract.py tests/interfaces/test_mcp_server.py tests/interfaces/test_cli_mcp.py -q
uv run ruff check src/mke/interfaces src/mke/cli.py tests/interfaces
uv run pyright
```

```bash
git add src/mke/interfaces/mcp_contract.py src/mke/interfaces/mcp_server.py src/mke/cli.py tests/interfaces
git commit -m "feat(mcp): add owner configured transcription"
```

## Task 7: Add Model-Free Packaging Gates

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_bootstrap.py`
- Modify: `tests/proof/test_runner.py`
- Modify: `tests/interfaces/test_cli_demo.py`

- [x] **Step 1: Write deterministic guard tests**

Patch real provider construction to fail and assert:

- `mke proof run` remains sidecar-backed;
- `mke demo --verify` remains sidecar-backed;
- core imports and `mke` bootstrap work when optional imports are unavailable;
- doctor reports dependency missing instead of crashing.

- [x] **Step 2: Verify RED or regression coverage**

```bash
uv run pytest tests/test_bootstrap.py tests/proof/test_runner.py tests/interfaces/test_cli_demo.py -q
```

- [x] **Step 3: Extend both Python matrix jobs without model download**

After building the wheel:

1. create an isolated environment;
2. install the core wheel and run bootstrap/demo as today;
3. recreate the environment;
4. install `wheel[transcription]` from the built artifact;
5. import `faster_whisper` and `av`;
6. run doctor in cache-only mode and assert its documented not-ready exit is 1 when the model is absent;
7. verify no model directory is created in the repository.

Use `uv export --locked --extra transcription --no-dev --no-emit-project` to create lock-derived constraints when supported by the pinned uv action. If the installed uv syntax differs, verify `uv export --help` and use its equivalent locked requirements output; do not drop the lock-derived constraint requirement.

- [x] **Step 4: Run local packaging checks**

```bash
uv sync --locked
uv run pytest -q
uv build
uv sync --locked --extra transcription
uv run python -c "import av, faster_whisper"
```

Do not invoke model preparation or real transcription.

- [x] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml tests/test_bootstrap.py tests/proof/test_runner.py tests/interfaces/test_cli_demo.py
git commit -m "ci: verify transcription wheel extra"
```

## Task 8: Update Runtime Documentation And Close PR 2

**Files:**
- Create: `docs/decisions/0006-first-party-local-transcription-runtime.md`
- Create: `docs/how-to/use-local-transcription.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/reference/contracts.md`
- Modify: `docs/how-to/use-mke-mcp.md`
- Modify: this plan

- [x] **Step 1: Record ADR-0006**

Document:

- first-party faster-whisper adapter subprocess;
- optional dependencies and licenses;
- default model/revision/CPU/int8 profile;
- explicit prepare versus cache-only doctor/ingest/MCP;
- current-interpreter module invocation;
- owner-only provider policy;
- model-free required CI;
- rollback to sidecar;
- HTTP/remote/vendor/queue work deferred.

- [x] **Step 2: Update Diataxis documentation**

Add exact install, prepare, doctor, CLI ingest, MCP startup, JSON, recovery, and non-goal examples. Clearly state that real proof evidence is added in PR 3; do not claim an unexecuted platform result.

- [x] **Step 3: Run complete verification**

```bash
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check
```

Also run the model-free extra installation commands from Task 7. Record actual output only.

- [x] **Step 4: Run a pre-landing review**

Use `gstack-review` because this PR changes subprocess handling, optional native dependencies, CLI/MCP contracts, and cancellation behavior. Persist durable findings under:

```text
docs/superpowers/reviews/2026-06-18-real-local-transcription-runtime-interfaces-review.md
```

Fix blockers, rerun focused tests, then rerun the full verification set.

- [x] **Step 5: Mark this plan complete and commit**

```bash
git add docs/decisions/0006-first-party-local-transcription-runtime.md docs/how-to/use-local-transcription.md docs/explanation/architecture.md docs/reference/cli.md docs/reference/contracts.md docs/how-to/use-mke-mcp.md docs/superpowers/plans/2026-06-18-real-local-transcription-runtime-interfaces-implementation.md docs/superpowers/reviews/2026-06-18-real-local-transcription-runtime-interfaces-review.md
git commit -m "docs(video): document local transcription runtime"
```

- [x] **Step 6: Prepare the Chinese PR body**

```markdown
## Summary

新增可选的 faster-whisper 本地转录运行时，并通过同一 composition root 向 CLI 和 owner-configured stdio MCP 提供 cache-only ingest。

## Completion

- [x] Explicit model preparation and read-only doctor
- [x] Cache-only first-party adapter subprocess
- [x] Shared CLI/MCP runtime construction
- [x] MCP cancellation and shutdown cleanup
- [x] Model-free Python 3.12/3.13 wheel-extra gates

## Verification

Use actual command results from this branch.

## Scope

本 PR 不包含真实 spoken fixture、真实模型里程碑 proof、HTTP、remote ASR 或 queue worker。

## Risk / Impact

- Core install remains independent of transcription dependencies.
- Faster-whisper is opt-in and can be rolled back to sidecar configuration.

## Documentation impact

Added ADR-0006 and local transcription/MCP operator documentation.
```

Do not push or create the PR until explicitly authorized.
