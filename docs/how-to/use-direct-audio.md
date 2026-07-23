# Use bounded direct audio

Direct audio is a bounded v0.1.4 capability for local voice notes and clips or excerpts encoded as
MP3, WAV/PCM, or M4A/AAC, with a 15 minutes and 100 MiB maximum. The prepared runtime is cache-only
and currently proved only on Darwin arm64.

The exact profiles are MP3/MPEG Layer III, RIFF-WAVE signed 16-bit little-endian PCM, and M4A
AAC-LC. Each file contains exactly one decodable audio stream and no other stream, uses one or two
channels at 8–48 kHz, has `0 < bytes <= 100 MiB` and `0 < duration <= 15 minutes`, and produces no
more than 10,000 ordered, finite, non-overlapping integer-millisecond segments. Suffix routing is
only a profile selector; byte inspection is authoritative. MKE does not transcode the input.

Bounded local voice notes and clips or excerpts from meetings, interviews, lectures, and other
downloaded spoken material, when encoded as the supported MP3, WAV/PCM, or M4A/AAC profiles, can
be transcribed through an explicitly prepared, cache-only faster-whisper runtime into timestamped
active Evidence, then consumed through Python, CLI, stdio MCP, Search/Ask, and a versioned
deterministic Compiled Library Export.

## 1. Prove product wiring without a model

```bash
UV_OFFLINE=1 uv run mke proof direct-audio --json
```

Checkpoint: model-free product wiring passed. This deterministic proof exercises inspection,
Publication, Search/Ask, timestamp EvidenceRef, Export v2, and the independent consumer with a
fake application-port provider. Its closed output records `proof_mode=model_free` and
`asr_execution=not_performed`; it does not establish real-ASR readiness.

## 2. Prepare and check the owner

Install the locked transcription extra. Model acquisition is a separate operator-authorized step:

```bash
uv sync --locked --extra transcription
uv run mke transcription prepare --allow-model-download \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --model-cache "$MKE_MODEL_CACHE" --json
HF_HUB_OFFLINE=1 uv run mke transcription doctor \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --model-cache "$MKE_MODEL_CACHE" --json
```

`mke transcription prepare` is the only download-capable command. Normal ingest, doctor, MCP, and
proof paths never download or repair a model.

Checkpoint: cache-only owner is ready.

Choose a strictly positive owner supervision value through the owner's independent startup policy.
The terminal proof observes and records the configured value; it does not select or recommend it.
MKE gives `DIRECT_AUDIO_FOOTPRINT_BYTES` no default, recommendation, or SLA. The mode is exactly
`baseline_plus`; `absolute` is not accepted at the direct-audio composition boundary.

## 3. Python golden path

```python
import os
from pathlib import Path

from mke.runtime import FasterWhisperTranscriptionConfig, RuntimeConfig, build_engine

OWNER_SELECTED_POSITIVE_BYTES = int(os.environ["DIRECT_AUDIO_FOOTPRINT_BYTES"])
runtime = RuntimeConfig(
    db_path=Path("library.sqlite3"),
    transcription=FasterWhisperTranscriptionConfig(
        model="small",
        model_revision="536b0662742c02347bc0e980a01041f333bce120",
        cache_dir=Path(os.environ["MKE_MODEL_CACHE"]),
    ),
    direct_audio_footprint_bytes=OWNER_SELECTED_POSITIVE_BYTES,
    direct_audio_footprint_budget_mode="baseline_plus",
)
engine = build_engine(runtime)
try:
    result = engine.ingest_file(Path("interview-excerpt.m4a"))
    evidence = engine.search("traceable", limit=5)
    answer = engine.ask("traceable publication", limit=5)
finally:
    engine.close()
```

The successful Run publishes timestamp Evidence with `timestamp_ms` locators. Strict MCP and Export
projections serialize it as `mke.evidence_ref.v1`. The immutable snapshot and complete manifest
must validate before the active Publication changes.

## 4. CLI golden path

```bash
export DIRECT_AUDIO_FOOTPRINT_BYTES=<owner-selected-positive-int>
uv run mke --db library.sqlite3 ingest interview-excerpt.m4a \
  --transcript-provider faster-whisper \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --model-cache "$MKE_MODEL_CACHE" \
  --direct-audio-footprint-bytes "$DIRECT_AUDIO_FOOTPRINT_BYTES" \
  --direct-audio-footprint-budget-mode baseline_plus --json
uv run mke --db library.sqlite3 search traceable
uv run mke --db library.sqlite3 ask traceable publication
uv run mke --db library.sqlite3 library export \
  --output compiled-library-v2 --format-version v2 --json
uv run python scripts/compiled_library_export_consumer_v2.py \
  --export compiled-library-v2 --json
```

Checkpoint: the audio Run published. Checkpoint: Export v2 passed its independent consumer.

## 5. stdio MCP golden path

Start or restart the owner with the same startup controls:

```bash
uv run mke --db library.sqlite3 mcp --allowed-root . \
  --transcript-provider faster-whisper \
  --model-cache "$MKE_MODEL_CACHE" \
  --direct-audio-footprint-bytes "$DIRECT_AUDIO_FOOTPRINT_BYTES" \
  --direct-audio-footprint-budget-mode baseline_plus
```

Then invoke the unchanged path-only tool request:

```json
{"name": "ingest_file", "arguments": {"path": "interview-excerpt.m4a"}}
```

These controls belong to owner startup, never the MCP request schema. Changing them requires a
controlled server restart. Search with `search_library_v1` and Ask with `ask_library_v1` return the
same portable timestamp Evidence projection.

## Recovery table

Every action is bounded; none authorizes automatic cache deletion or implicit download.
All failures keep `active_publication_impact=unchanged`. Pre-Run failures omit `run_id`; post-Run
failures retain the existing `run_id`.

| Problem/code | Exact cause | `next_step` | Bounded action |
|---|---|---|---|
| `input_path_rejected` | `input path must exist and be readable` | `choose_file_under_allowed_root` | Select a stable regular file under the configured root. |
| `input_path_rejected` | `input path must be a regular file and not a symlink` | `choose_file_under_allowed_root` | Replace a link/special file with a stable regular file. |
| `input_path_rejected` | `input path changed during validation` | `choose_file_under_allowed_root` | Stop writers and select the stable path again. |
| `input_path_rejected` | `input path must not be empty` | `choose_file_under_allowed_root` | Supply one path-only MCP input. |
| `input_path_rejected` | `input file does not exist` | `choose_file_under_allowed_root` | Select an existing file under the configured root. |
| `input_path_rejected` | `input path must not be a symlink` | `choose_file_under_allowed_root` | Select a regular non-symlink file. |
| `input_path_rejected` | `input path must be a file` | `choose_file_under_allowed_root` | Replace the directory/special entry with a regular file. |
| `input_path_rejected` | `input path must be under allowed root` | `choose_file_under_allowed_root` | Select a file under the owner-configured root. |
| `input_path_rejected` | `file path cannot be resolved` | `choose_file_under_allowed_root` | Correct the bounded path, then retry once. |
| `unsupported_media_type` | `supported suffixes are .pdf, .mp4, .mp3, .wav, and .m4a` | `choose_supported_file` | Choose one listed suffix; bytes are still inspected. |
| `audio_ingest_failed` | `audio input is empty` | `choose_supported_file` | Choose a non-empty supported file. |
| `transcription_not_ready` | `direct audio supervision is not configured` | `configure_direct_audio_supervision` | Restart the owner with both supervision flags. |
| `transcription_not_ready` | `direct audio runtime is supported only on Darwin arm64` | `run_on_supported_darwin_arm64` | Move the same inputs to an authorized Darwin arm64 owner. |
| `transcription_not_ready` | `direct audio requires faster-whisper owner` | `configure_faster_whisper_owner` | Restart with `--transcript-provider faster-whisper`. |
| `transcription_not_ready` | `transcription optional dependency is not installed` | `install_transcription_extra` | Install the locked `transcription` extra, then rerun doctor. |
| `transcription_not_ready` | `configured transcription model is not cached` | `run_transcription_prepare` | Run the explicit authorized `mke transcription prepare --allow-model-download ...` command. |
| `transcription_not_ready` | `transcription model cache is not readable` | `check_model_cache_permissions` | Correct only the configured cache permissions, then rerun doctor. |
| `transcription_not_ready` | `configured transcription model revision is unavailable` | `check_model_and_revision` | Recheck the documented model and immutable revision. |
| `transcription_not_ready` | `transcription model resolution failed` | `check_model_configuration` | Rerun cache-only doctor with the same owner fields. |
| `transcription_not_ready` | `transcription device or compute profile is unsupported` | `choose_supported_transcription_profile` | Choose a locally supported device/compute pair. |
| `transcription_not_ready` | `configured language is not supported by the model` | `choose_supported_language` | Choose `auto` or a language supported by the prepared model. |
| `transcription_busy` | `direct audio owner capacity is busy` | `retry_when_owner_ready` | Wait for the current owner child to finish, then retry once. |
| `audio_ingest_failed` | `transcription optional dependency is not installed` | `install_transcription_extra` | Install the locked extra; this post-Run row retains its Run. |
| `audio_ingest_failed` | `configured transcription model is not cached` | `run_transcription_prepare` | Run the separately authorized prepare command before retrying the Run. |
| `audio_ingest_failed` | `transcription model resolution failed` | `check_model_configuration` | Check the fixed model/revision and rerun cache-only doctor. |
| `audio_ingest_failed` | `audio profile is unsupported` | `choose_supported_file` | Use a bounded MP3, WAV/PCM, or M4A/AAC file. |
| `audio_ingest_failed` | `audio input exceeds supported limits` | `choose_smaller_file` | Choose a file at or below 15 minutes and 100 MiB. |
| `audio_ingest_failed` | `audio source identity changed during intake` | `retry_with_stable_file` | Stop writers and retry the stable file. |
| `audio_ingest_failed` | `audio inspection timed out` | `retry_with_supported_file` | Recheck the bounded profile, then retry once. |
| `audio_ingest_failed` | `audio inspection failed` | `choose_supported_file` | Inspect the container/stream and choose a supported file. |
| `audio_ingest_failed` | `audio intake cleanup failed` | `check_server_logs` | Run `mke --db library.sqlite3 run get <run_id> --json`; do not delete shared caches. |
| `audio_ingest_failed` | `audio file must contain one audio stream` | `choose_supported_file` | Choose a file with exactly one audio stream. |
| `audio_ingest_failed` | `transcription failed` | `check_server_logs` | Inspect the returned Run with `run get`; retain only closed output. |
| `audio_ingest_failed` | `audio transcript must contain at least one segment` | `check_audio` | Confirm the clip contains audible speech. |
| `audio_ingest_failed` | `audio transcript schema validation failed` | `check_server_logs` | Inspect `run get`, then retry only after owner correction. |
| `audio_ingest_failed` | `audio publication failed` | `retry_when_owner_ready` | Inspect `run get`; retry after owner/storage readiness returns. |
| `audio_ingest_failed` | `operation failed; details were redacted` | `check_server_logs` | Unknown child status: retain the closed response and inspect the bounded Run. |
| `audio_ingest_failed` | `operation failed; details were redacted` | `fix_input_or_retry` | Unknown application failure: correct the bounded input or retry once. |
| proof | `fixture_invalid` | `check_fixture_receipt` | Revalidate the committed fixture receipt. |
| proof | `snapshot_failed` | `retry_with_stable_file` | Recreate only the call-owned proof workspace. |
| proof | `inspection_failed` | `choose_supported_file` | Revalidate the bounded synthetic fixture. |
| proof | `ingest_failed` | `check_server_logs` | Rerun `mke proof direct-audio --json` and retain its closed result. |
| proof | `publication_incomplete` | `retry_when_owner_ready` | Rerun after owner readiness. |
| proof | `evidence_mismatch` | `rerun_direct_audio_proof` | Rerun the model-free proof from a clean call-owned workspace. |
| proof | `export_failed` | `rerun_export_v2` | Rerun the complete export with `--format-version v2`. |
| proof | `consumer_failed` | `check_export_consumer` | Run the v2 standalone consumer against the same export. |
| proof | `cleanup_failed` | `rerun_direct_audio_proof` | Rerun the proof; call-owned cleanup remains controller-owned. |

## Boundaries

This bounded release does not support arbitrary codecs or full-length meetings, interviews, or lectures.
Long audio, chunking, resume, streaming, diarization, microphone capture, cloud fallback, implicit
download, transcript-accuracy guarantees, all-platform coverage, hosted deployment, production
SLA, automatic LLM Wiki sync, and official OpenAI integration are excluded.
