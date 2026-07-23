from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

APPROVED_CLAIM = (
    "Bounded local voice notes and clips or excerpts from meetings, interviews, lectures, and "
    "other downloaded spoken material, when encoded as the supported MP3, WAV/PCM, or M4A/AAC "
    "profiles, can be transcribed through an explicitly prepared, cache-only faster-whisper "
    "runtime into timestamped active Evidence, then consumed through Python, CLI, stdio MCP, "
    "Search/Ask, and a versioned deterministic Compiled Library Export."
)


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _normalized(relative: str) -> str:
    return " ".join(_text(relative).split())


def test_entry_docs_discover_the_release_and_lead_with_model_free_proof() -> None:
    targets = {
        "README.md": "docs/how-to/use-direct-audio.md",
        "README_CN.md": "docs/how-to/use-direct-audio.md",
        "docs/README.md": "how-to/use-direct-audio.md",
        "docs/tutorials/getting-started.md": "../how-to/use-direct-audio.md",
    }
    for relative, link in targets.items():
        text = _text(relative)
        assert link in text
        assert "v0.1.4" in text
        assert "accepted v0.1.4 candidate" not in text

    how_to = _text("docs/how-to/use-direct-audio.md")
    proof = "UV_OFFLINE=1 uv run mke proof direct-audio --json"
    prepare = "mke transcription prepare"
    assert proof in how_to
    assert prepare in how_to
    assert how_to.index(proof) < how_to.index(prepare)
    for checkpoint in (
        "Checkpoint: model-free product wiring passed",
        "Checkpoint: cache-only owner is ready",
        "Checkpoint: the audio Run published",
        "Checkpoint: Export v2 passed its independent consumer",
    ):
        assert checkpoint in how_to


def test_direct_audio_how_to_has_copy_ready_python_cli_and_mcp_paths() -> None:
    text = _normalized("docs/how-to/use-direct-audio.md")
    for term in (
        "RuntimeConfig(",
        "FasterWhisperTranscriptionConfig(",
        "direct_audio_footprint_bytes=OWNER_SELECTED_POSITIVE_BYTES",
        'direct_audio_footprint_budget_mode="baseline_plus"',
        "engine.ingest_file(",
        "engine.search(",
        "engine.ask(",
        "engine.close()",
        '--direct-audio-footprint-bytes "$DIRECT_AUDIO_FOOTPRINT_BYTES"',
        "--direct-audio-footprint-budget-mode baseline_plus",
        "ingest interview-excerpt.m4a",
        "search traceable",
        "ask traceable publication",
        "library export",
        "--output compiled-library-v2 --format-version v2",
        '"name": "ingest_file"',
        '"arguments": {"path": "interview-excerpt.m4a"}',
        "controlled server restart",
    ):
        assert term in text
    assert '"provider"' not in text.split('"arguments": {"path": "interview-excerpt.m4a"}')[1][:120]


def test_docs_freeze_bounded_owner_and_evidence_contract() -> None:
    public = "\n".join(
        _normalized(relative)
        for relative in (
            "docs/decisions/0011-bounded-direct-audio-intake.md",
            "docs/how-to/use-direct-audio.md",
            "docs/explanation/architecture.md",
            "docs/reference/cli.md",
            "docs/reference/contracts.md",
            "docs/reference/mcp-contract.md",
        )
    )
    for term in (
        APPROVED_CLAIM,
        "MP3",
        "WAV/PCM",
        "M4A/AAC",
        "15 minutes",
        "100 MiB",
        "Darwin arm64",
        "cache-only",
        "baseline_plus",
        "no default, recommendation, or SLA",
        "mke.evidence_ref.v1",
        "timestamp_ms",
        "active Publication",
        "immutable snapshot",
        "canonical dispatcher",
        "Source and Run before model work",
    ):
        assert term in public


def test_direct_audio_recovery_table_is_complete_and_bounded() -> None:
    text = _normalized("docs/how-to/use-direct-audio.md")
    triples = (
        (
            "input_path_rejected",
            "input path must exist and be readable",
            "choose_file_under_allowed_root",
        ),
        (
            "input_path_rejected",
            "input path must be a regular file and not a symlink",
            "choose_file_under_allowed_root",
        ),
        (
            "input_path_rejected",
            "input path changed during validation",
            "choose_file_under_allowed_root",
        ),
        (
            "input_path_rejected",
            "input path must not be empty",
            "choose_file_under_allowed_root",
        ),
        (
            "input_path_rejected",
            "input file does not exist",
            "choose_file_under_allowed_root",
        ),
        (
            "input_path_rejected",
            "input path must not be a symlink",
            "choose_file_under_allowed_root",
        ),
        (
            "input_path_rejected",
            "input path must be a file",
            "choose_file_under_allowed_root",
        ),
        (
            "input_path_rejected",
            "input path must be under allowed root",
            "choose_file_under_allowed_root",
        ),
        (
            "input_path_rejected",
            "file path cannot be resolved",
            "choose_file_under_allowed_root",
        ),
        (
            "unsupported_media_type",
            "supported suffixes are .pdf, .mp4, .mp3, .wav, and .m4a",
            "choose_supported_file",
        ),
        ("audio_ingest_failed", "audio input is empty", "choose_supported_file"),
        (
            "transcription_not_ready",
            "direct audio supervision is not configured",
            "configure_direct_audio_supervision",
        ),
        (
            "transcription_not_ready",
            "direct audio runtime is supported only on Darwin arm64",
            "run_on_supported_darwin_arm64",
        ),
        (
            "transcription_not_ready",
            "direct audio requires faster-whisper owner",
            "configure_faster_whisper_owner",
        ),
        (
            "transcription_not_ready",
            "transcription optional dependency is not installed",
            "install_transcription_extra",
        ),
        (
            "transcription_not_ready",
            "configured transcription model is not cached",
            "run_transcription_prepare",
        ),
        (
            "transcription_not_ready",
            "transcription model cache is not readable",
            "check_model_cache_permissions",
        ),
        (
            "transcription_not_ready",
            "configured transcription model revision is unavailable",
            "check_model_and_revision",
        ),
        (
            "transcription_not_ready",
            "transcription model resolution failed",
            "check_model_configuration",
        ),
        (
            "transcription_not_ready",
            "transcription device or compute profile is unsupported",
            "choose_supported_transcription_profile",
        ),
        (
            "transcription_not_ready",
            "configured language is not supported by the model",
            "choose_supported_language",
        ),
        ("transcription_busy", "direct audio owner capacity is busy", "retry_when_owner_ready"),
        (
            "audio_ingest_failed",
            "transcription optional dependency is not installed",
            "install_transcription_extra",
        ),
        (
            "audio_ingest_failed",
            "configured transcription model is not cached",
            "run_transcription_prepare",
        ),
        (
            "audio_ingest_failed",
            "transcription model resolution failed",
            "check_model_configuration",
        ),
        ("audio_ingest_failed", "audio profile is unsupported", "choose_supported_file"),
        ("audio_ingest_failed", "audio input exceeds supported limits", "choose_smaller_file"),
        (
            "audio_ingest_failed",
            "audio source identity changed during intake",
            "retry_with_stable_file",
        ),
        ("audio_ingest_failed", "audio inspection timed out", "retry_with_supported_file"),
        ("audio_ingest_failed", "audio inspection failed", "choose_supported_file"),
        ("audio_ingest_failed", "audio intake cleanup failed", "check_server_logs"),
        (
            "audio_ingest_failed",
            "audio file must contain one audio stream",
            "choose_supported_file",
        ),
        ("audio_ingest_failed", "transcription failed", "check_server_logs"),
        (
            "audio_ingest_failed",
            "audio transcript must contain at least one segment",
            "check_audio",
        ),
        ("audio_ingest_failed", "audio transcript schema validation failed", "check_server_logs"),
        ("audio_ingest_failed", "audio publication failed", "retry_when_owner_ready"),
        (
            "audio_ingest_failed",
            "operation failed; details were redacted",
            "check_server_logs",
        ),
        (
            "audio_ingest_failed",
            "operation failed; details were redacted",
            "fix_input_or_retry",
        ),
    )
    for problem, cause, next_step in triples:
        assert f"`{problem}` | `{cause}` | `{next_step}`" in text

    proof_rows = (
        ("fixture_invalid", "check_fixture_receipt"),
        ("snapshot_failed", "retry_with_stable_file"),
        ("inspection_failed", "choose_supported_file"),
        ("ingest_failed", "check_server_logs"),
        ("publication_incomplete", "retry_when_owner_ready"),
        ("evidence_mismatch", "rerun_direct_audio_proof"),
        ("export_failed", "rerun_export_v2"),
        ("consumer_failed", "check_export_consumer"),
        ("cleanup_failed", "rerun_direct_audio_proof"),
    )
    for code, next_step in proof_rows:
        assert f"proof | `{code}` | `{next_step}`" in text
    assert "Pre-Run failures omit `run_id`" in text
    assert "post-Run failures retain the existing `run_id`" in text
    assert "MKE automatically deletes" not in text
    assert "downloads automatically" not in text


def test_export_docs_freeze_v1_compatibility_and_v2_migration() -> None:
    text = "\n".join(
        _normalized(relative)
        for relative in (
            "docs/how-to/export-compiled-library.md",
            "docs/reference/cli.md",
            "docs/reference/contracts.md",
        )
    )
    for term in (
        "default v1",
        "explicit v1",
        "byte-identical",
        "unsupported_active_media_type",
        "active Library contains media unsupported by export v1",
        "rerun_library_export_with_format_version_v2",
        "--format-version v2",
        "mke.compiled_library_export.v2",
        "mke.compiled_markdown.v2",
        "mke.compiled_library_export_response.v2",
        "mke.compiled_library_export_consumer.v2",
        "v1 and v2 consumers do not cross-consume",
        "omit or remove audio from the active snapshot",
    ):
        assert term in text


def test_contract_reference_freezes_the_complete_v2_authority_matrix() -> None:
    text = _normalized("docs/reference/contracts.md")
    rows = (
        (
            "application/pdf",
            "page",
            "candidate_evidence + pdf_text_extraction",
            "builtin-pdf-text-v1 or pymupdf-text-v1",
        ),
        (
            "application/pdf",
            "page",
            "candidate_evidence + pdf_ocr_extraction",
            "pdf-ocr-eval-v1:<64 lowercase hex>",
        ),
        (
            "video/mp4",
            "timestamp_ms",
            "candidate_evidence + video_transcription",
            (
                "builtin-video-transcript-v1, local-command-video-transcript-v1, or "
                "faster-whisper-v1:<64 lowercase hex>"
            ),
        ),
        (
            "audio/mpeg, audio/wav, audio/mp4",
            "timestamp_ms",
            "audio_transcription + candidate_evidence",
            "faster-whisper-audio-v1:<64 lowercase hex>",
        ),
    )
    for media, locator, stages, fingerprints in rows:
        assert f"`{media}` | `{locator}` | `{stages}` | `{fingerprints}`" in text
    assert "comparison-only PDF OCR" in text


def test_proof_and_dependency_docs_preserve_authority_and_non_claims() -> None:
    proof = _normalized("docs/how-to/run-direct-audio-proof.md")
    evidence = _normalized("docs/reference/direct-audio-dependency-and-license-evidence.md")
    for term in (
        "mke.direct_audio_proof.v1",
        "mke.direct_audio_terminal_authorization.v1",
        "mke.direct_audio_deployment_proof.v1",
        "authorization-only",
        "does not run ASR",
        "configured bytes/mode",
        "baseline",
        "observed peak",
        "effective budget",
        "overshoot",
        "fixed-fixture Darwin arm64 observation",
    ):
        assert term in proof
    for term in (
        "PR C installed-wheel binding",
        "external_binary_redistribution=not_performed",
        "redistribution_authority=not_claimed",
        "future bundling or release redistribution requires separate legal review",
        "dependency-installation input",
        "does not turn the dependency receipt into candidate product or real-ASR evidence",
    ):
        assert term in evidence


def test_adr_records_rollback_and_explicit_non_goals() -> None:
    text = _normalized("docs/decisions/0011-bounded-direct-audio-intake.md")
    for term in (
        "Status: Accepted for v0.1.4",
        "additive audio protocol",
        "command-local errors",
        "Compiled Library Export v2",
        "Rollback",
        "PDF and video remain available",
        "arbitrary codecs",
        "diarization",
        "streaming",
        "implicit model download",
        "hosted deployment",
        "LLM Wiki remains external",
    ):
        assert term in text
