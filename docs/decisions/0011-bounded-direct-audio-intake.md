# ADR-0011: Bounded direct-audio intake

Status: Accepted candidate

## Context

MKE already publishes page Evidence from text-layer PDFs and timestamp Evidence from the bounded
video path. The accepted v0.1.4 candidate adds downloaded spoken audio without changing SQLite,
Run, Publication, or Evidence authority. It supersedes only the historical deferral of direct
audio; ADR-0003, ADR-0005, and ADR-0006 remain in force.

## Decision

Bounded local voice notes and clips or excerpts from meetings, interviews, lectures, and other
downloaded spoken material, when encoded as the supported MP3, WAV/PCM, or M4A/AAC profiles, can
be transcribed through an explicitly prepared, cache-only faster-whisper runtime into timestamped
active Evidence, then consumed through Python, CLI, stdio MCP, Search/Ask, and a versioned
deterministic Compiled Library Export.

The profile is limited to 15 minutes and 100 MiB. Direct audio is enabled only on Darwin arm64
when the owner supplies one positive `direct_audio_footprint_bytes` value and
`direct_audio_footprint_budget_mode="baseline_plus"`. The value has no default, recommendation,
or SLA. One pair supervises audio inspection and transcription. Missing policy or an unsupported
platform fails before Source and Run before model work; PDF and video remain available.

The canonical dispatcher routes `.mp3`, `.wav`, and `.m4a` through the existing lifecycle. The
input is an immutable snapshot, the additive audio protocol remains separate from the video
protocol, and a complete Run switches the active Publication atomically. CLI and stdio MCP expose
command-local errors; shared `PublicError` authority is unchanged.

The closed v1 compiled export stays byte-compatible. An active audio Source makes v1 fail closed;
explicit Compiled Library Export v2 represents the complete mixed Library and keeps
`mke.evidence_ref.v1` as Evidence authority. LLM Wiki remains external to MKE runtime and Evidence
authority.

## Proof and dependency gates

The ordinary proof is deterministic and model-free. The separately authorized terminal proof
uses the accepted external dependency receipt, exact model snapshot, two fresh installed-wheel
cells, deny-network execution, and an owner-selected supervision pair. Package metadata alone does
not establish external binary redistribution authority.

## Rollback

Rollback disables direct audio by omitting the owner supervision pair or using an owner without
the direct-audio adapter. Existing PDF and video remain available. Export rollback preserves v1
by omitting or removing audio from the active snapshot; it never widens the v1 validator.

## Non-goals

This decision does not authorize arbitrary codecs, full-length meetings/interviews/lectures,
long-audio workers, diarization, chunking, resume, streaming, microphone capture, implicit model
download, cloud fallback, hosted deployment, transcript-accuracy claims, a production SLA, or
external binary redistribution.
