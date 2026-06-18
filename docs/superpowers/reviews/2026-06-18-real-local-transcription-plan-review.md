# Real Local Transcription Implementation Plan Review

## Status

- Review target: D3-B design, Autoplan review, and three implementation plans.
- Review type: pre-landing plan-diff review.
- Result: all findings resolved in the reviewed branch.
- Scope: documentation only; no runtime implementation was reviewed.

## Scope Check

- Intent: define an implementation-ready real local transcription milestone.
- Delivered: one approved design, one Autoplan review, and three sequential PR plans.
- Scope result: clean.
- Implementation checklist state: intentionally pending because the plans describe future PRs.

## Findings Resolved

### 1. Language Was Missing From Extractor Identity

The design allows an operator to choose automatic or explicit language handling, but the original
provenance, report, and fingerprint input omitted that requested mode. Two behaviorally different
transcription configurations could therefore share one extractor fingerprint.

Resolution:

- add normalized requested language to provenance and `TranscriptIntakeReport`;
- include it in canonical fingerprint input and persistence/public payload plans;
- retain detected language as a separate observed value;
- require tests proving a language change changes the fingerprint.

### 2. MCP Cancellation Could Cancel The Wrapper Before Cleanup Completed

The original example directly awaited the `asyncio.to_thread` task. Request cancellation could
mark that wrapper task cancelled while the underlying thread continued, preventing the server from
reliably waiting for failed-Run cleanup.

Resolution:

- shield the worker task from request cancellation;
- terminate registered adapter processes;
- wait for the worker under a bounded cleanup timeout;
- require tests proving subprocess termination and failed-Run recovery complete before cancellation
  is returned.

### 3. Model Preparation Was Incorrectly Described As Side-Effect-Free

Preparation may download an exact model revision and write the configured cache.

Resolution:

- describe preparation as explicit and Run-free, not side-effect-free;
- keep doctor, ingest, proof execution, and MCP cache-only.

### 4. Spoken Fixture Redistribution Evidence Was Incomplete

The original plan named a macOS system voice but did not establish that generated audio from that
voice can be redistributed in a public repository.

Resolution:

- require a primary-source generated-output or source-recording license;
- treat the macOS command as a prototype unless its redistribution terms are documented;
- record synthesizer/voice identity, license URL, redistribution basis, and checksum;
- do not relicense third-party source audio as repository-owned content.

### 5. Optional PyAV Fixture Test Could Break Or Silently Skip Core CI

The fixture test belongs to the transcription extra, while the required core suite intentionally
does not install that extra.

Resolution:

- avoid module-import-time PyAV imports;
- keep the core suite collectable without the extra;
- run the media-profile test explicitly in an extra-enabled CI step;
- fail that step if the test is unexpectedly skipped.

### 6. Architecture Diagram And File Plan Disagreed

The design placed `runtime.py` under `adapters/video`, while the implementation plan correctly
created the shared CLI/MCP composition root at `src/mke/runtime.py`.

Resolution:

- move `runtime.py` to the package root in the design diagram;
- name `faster_whisper.py` and `process.py` as video adapter modules;
- make the responsibility table use the exact package-root path.

### 7. Cancellation Cleanup Timeout Was Silently Suppressed

The corrected cancellation example initially wrapped worker cleanup in a suppressed
`asyncio.wait_for`. A timeout could therefore return `CancelledError` to the MCP caller while the
worker thread continued mutating Run state.

Resolution:

- shield the worker before request cancellation can cancel its wrapper task;
- terminate the registered subprocess;
- await worker lifecycle cleanup before propagating cancellation;
- keep timeout enforcement in the test harness rather than silently abandoning production cleanup.

## Verification

- The pinned `Systran/faster-whisper-small` revision resolves to
  `536b0662742c02347bc0e980a01041f333bce120`.
- faster-whisper v1.2.1 source accepts `model_size_or_path`, `device`, `compute_type`,
  `download_root`, `local_files_only`, and `revision`, and returns lazy segments plus
  `TranscriptionInfo`.
- Current `uv export` supports the planned `--locked`, `--extra`, `--no-dev`, and
  `--no-emit-project` flags.

## Verdict

The corrected plans are ready for a documentation PR. Runtime correctness still depends on each
implementation PR following its TDD, review, and verification gates.
