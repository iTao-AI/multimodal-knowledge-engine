"""Internal direct-audio contracts and uncomposed provider adapters."""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from typing import cast

from mke.adapters.audio.contracts import AudioTranscriptionLimits, audio_extractor_fingerprint
from mke.adapters.audio.inspection import (
    AudioInspectionError,
    AudioSnapshotError,
    AudioSourceSnapshot,
    cleanup_audio_snapshot,
    parse_audio_inspection_result,
    snapshot_audio_source,
    validate_audio_inspection_request,
    verify_owned_path,
    verify_source_path,
)
from mke.adapters.audio.schema import (
    AudioTranscriptValidationError,
    parse_audio_transcript_payload,
)
from mke.adapters.video.process import (
    ActiveProcessController,
    ProcessOperationId,
    SupervisedProcessError,
    SupervisedProcessProfile,
    run_supervised_process,
)
from mke.domain import (
    AudioMediaInfo,
    AudioTranscriptExtractionResult,
    TranscriptIntakeReport,
)
from mke.runtime import FasterWhisperTranscriptionConfig

AUDIO_INSPECTION_COMMAND = (
    sys.executable,
    "-I",
    "-B",
    "-m",
    "mke.adapters.audio.inspection_cli",
)
AUDIO_TRANSCRIPTION_COMMAND = (
    sys.executable,
    "-I",
    "-B",
    "-m",
    "mke.adapters.audio.faster_whisper_cli",
)

AUDIO_EXIT_ERRORS: dict[int, tuple[str, str]] = {
    20: ("transcription optional dependency is not installed", "install_transcription_extra"),
    21: ("configured transcription model is not cached", "run_transcription_prepare"),
    22: ("transcription model resolution failed", "check_model_configuration"),
    30: ("audio profile is unsupported", "choose_supported_file"),
    31: ("audio file must contain one audio stream", "choose_supported_file"),
    32: ("audio input exceeds supported limits", "choose_smaller_file"),
    40: ("transcription failed", "check_server_logs"),
    41: ("audio transcript must contain at least one segment", "check_audio"),
    50: ("audio transcript schema validation failed", "check_server_logs"),
}

_OFFLINE_CHILD_ENVIRONMENT = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
    "PYTHONNOUSERSITE": "1",
}


class AudioProviderError(RuntimeError):
    """Redacted internal provider failure for future owner composition."""

    def __init__(self, cause: str, *, next_step: str) -> None:
        super().__init__(cause)
        self.problem = "audio_ingest_failed"
        self.next_step = next_step


@dataclass(frozen=True)
class InternalAudioProvider:
    """Uncomposed package-owned provider for the two closed audio children."""

    profile: SupervisedProcessProfile
    process_controller: ActiveProcessController | None = None
    process_operation_id: ProcessOperationId | None = None

    def __post_init__(self) -> None:
        if (
            platform.system() == "Darwin"
            and platform.machine() == "arm64"
            and self.profile.footprint_bytes is None
        ):
            raise ValueError("footprint supervision is required on Darwin arm64")

    def inspect(self, snapshot: AudioSourceSnapshot, *, suffix: str) -> AudioMediaInfo:
        try:
            snapshot.verify_owned_path()
            request = validate_audio_inspection_request(
                {
                    "path": str(snapshot.owned_path),
                    "expected_suffix": suffix,
                    "expected_sha256": snapshot.owned_identity.sha256,
                    "expected_bytes": snapshot.owned_identity.bytes,
                }
            )
        except (AudioInspectionError, AudioSnapshotError, TypeError, ValueError) as error:
            raise AudioProviderError(
                "audio transcript schema validation failed",
                next_step="check_server_logs",
            ) from error
        command = AUDIO_INSPECTION_COMMAND + (
            "--path",
            request["path"],
            "--expected-suffix",
            request["expected_suffix"],
            "--expected-sha256",
            request["expected_sha256"],
            "--expected-bytes",
            str(request["expected_bytes"]),
        )
        payload = self._run_child(command)
        try:
            result = parse_audio_inspection_result(payload, request=request)
            media = result["media"]
            parsed = AudioMediaInfo(
                media["container"],
                media["audio_codec"],
                media["channels"],
                media["sample_rate_hz"],
                media["duration_ms"],
            )
            snapshot.verify_owned_path()
            return parsed
        except (AudioInspectionError, AudioSnapshotError, TypeError, ValueError) as error:
            raise AudioProviderError(
                "audio transcript schema validation failed",
                next_step="check_server_logs",
            ) from error

    def transcribe(
        self,
        snapshot: AudioSourceSnapshot,
        media: AudioMediaInfo,
        config: FasterWhisperTranscriptionConfig,
    ) -> AudioTranscriptExtractionResult:
        try:
            snapshot.verify_owned_path()
        except AudioSnapshotError as error:
            raise AudioProviderError(
                "audio transcript schema validation failed",
                next_step="check_server_logs",
            ) from error
        command = AUDIO_TRANSCRIPTION_COMMAND + (
            "--path",
            str(snapshot.owned_path),
            "--expected-sha256",
            snapshot.owned_identity.sha256,
            "--expected-bytes",
            str(snapshot.owned_identity.bytes),
            "--container",
            media.container,
            "--audio-codec",
            media.audio_codec,
            "--channels",
            str(media.channels),
            "--sample-rate-hz",
            str(media.sample_rate_hz),
            "--duration-ms",
            str(media.duration_ms),
            "--model",
            config.model,
            "--model-revision",
            config.model_revision,
            "--device",
            config.device,
            "--compute-type",
            config.compute_type,
            "--language",
            config.language,
        )
        if config.cache_dir is not None:
            command += ("--cache-dir", str(config.cache_dir))
        payload = self._run_child(command)
        try:
            parsed = parse_audio_transcript_payload(payload)
            if parsed.media != media or parsed.transcription_provenance is None:
                raise AudioTranscriptValidationError("audio child media identity mismatch")
            snapshot.verify_owned_path()
        except (AudioSnapshotError, AudioTranscriptValidationError, TypeError, ValueError) as error:
            raise AudioProviderError(
                "audio transcript schema validation failed",
                next_step="check_server_logs",
            ) from error
        provenance = parsed.transcription_provenance
        return AudioTranscriptExtractionResult(
            parsed_transcript=parsed,
            extractor_fingerprint=audio_extractor_fingerprint(provenance),
            transcript_intake_report=TranscriptIntakeReport(
                provider=provenance.provider,
                model=provenance.model,
                model_revision=provenance.model_revision,
                library_version=provenance.library_version,
                device=provenance.device,
                compute_type=provenance.compute_type,
                language=provenance.language,
                detected_language=provenance.detected_language,
                media_duration_ms=parsed.media.duration_ms,
                transcription_duration_ms=provenance.transcription_duration_ms,
                segment_count=len(parsed.segments),
                model_source=provenance.model_source,
            ),
        )

    def _run_child(self, command: tuple[str, ...]) -> object:
        try:
            completed = run_supervised_process(
                command,
                environment=dict(_OFFLINE_CHILD_ENVIRONMENT),
                profile=self.profile,
                process_controller=self.process_controller,
                process_operation_id=self.process_operation_id,
            )
        except SupervisedProcessError as error:
            raise AudioProviderError(
                "audio ingest failed", next_step="check_server_logs"
            ) from error
        if completed.supervision.hard_kernel_enforced is not False:
            raise AudioProviderError("audio ingest failed", next_step="check_server_logs")
        if completed.returncode != 0:
            cause, next_step = AUDIO_EXIT_ERRORS.get(
                completed.returncode,
                ("audio ingest failed", "check_server_logs"),
            )
            raise AudioProviderError(cause, next_step=next_step)
        try:
            text = completed.stdout.decode("utf-8")
            if not text.endswith("\n") or text.count("\n") != 1:
                raise ValueError
            return cast(object, json.loads(text))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise AudioProviderError(
                "audio transcript schema validation failed",
                next_step="check_server_logs",
            ) from error

__all__ = [
    "AudioInspectionError",
    "AudioProviderError",
    "AudioSnapshotError",
    "AudioSourceSnapshot",
    "AudioTranscriptValidationError",
    "AudioTranscriptionLimits",
    "AUDIO_EXIT_ERRORS",
    "AUDIO_INSPECTION_COMMAND",
    "AUDIO_TRANSCRIPTION_COMMAND",
    "InternalAudioProvider",
    "audio_extractor_fingerprint",
    "cleanup_audio_snapshot",
    "parse_audio_inspection_result",
    "parse_audio_transcript_payload",
    "snapshot_audio_source",
    "validate_audio_inspection_request",
    "verify_owned_path",
    "verify_source_path",
]
