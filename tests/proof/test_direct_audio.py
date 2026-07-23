from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path
from typing import cast

import pytest

from mke.application import AudioIngestError, KnowledgeEngine
from mke.proof.direct_audio import (
    DIRECT_AUDIO_PROOF_FAILURE_NEXT_STEPS,
    DeterministicAudioProvider,
    DirectAudioProofError,
    DirectAudioProofFailureCode,
    DirectAudioProofReport,
    direct_audio_report_payload,
    run_direct_audio_proof,
)

ROOT = Path(__file__).resolve().parents[2]
AUDIO_FIXTURE_ROOT = ROOT / "tests/fixtures/audio"
RECEIPT = ROOT / "benchmarks/audio/dependency-artifacts.json"
CONSUMER = ROOT / "scripts/compiled_library_export_consumer_v2.py"
MAX_AUDIO_BYTES = 100 * 1024 * 1024


@pytest.fixture(scope="session")
def audio_boundary_files(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, Path]:
    root = tmp_path_factory.mktemp("direct-audio-boundaries")
    exact = root / "exact.mp3"
    over = root / "over.mp3"
    duration = root / "duration.wav"
    exact.write_bytes(b"\0")
    over.write_bytes(b"\0")
    with exact.open("r+b") as stream:
        stream.truncate(MAX_AUDIO_BYTES)
    with over.open("r+b") as stream:
        stream.truncate(MAX_AUDIO_BYTES + 1)
    duration_data_bytes = 16_000 * 2 * 900
    duration.write_bytes(
        b"RIFF"
        + struct.pack("<I", 36 + duration_data_bytes)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, 16_000, 32_000, 2, 16)
        + b"data"
        + struct.pack("<I", duration_data_bytes)
    )
    with duration.open("r+b") as stream:
        stream.truncate(44 + duration_data_bytes)
    return exact, over, duration


def test_direct_audio_proof_covers_all_formats_and_product_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mke.proof import direct_audio

    workspace = tmp_path / "proof"
    provider = DeterministicAudioProvider()
    inspected: list[tuple[str, str, int]] = []
    original_inspect = direct_audio.inspect_audio

    def deny_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("network access is forbidden in the model-free proof")

    monkeypatch.setattr("socket.create_connection", deny_network)

    def inspect_with_real_boundary(
        request: object, **kwargs: object
    ) -> object:
        parsed = cast(dict[str, object], request)
        inspected.append(
            (
                cast(str, parsed["expected_suffix"]),
                cast(str, parsed["expected_sha256"]),
                cast(int, parsed["expected_bytes"]),
            )
        )
        return original_inspect(request, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(direct_audio, "inspect_audio", inspect_with_real_boundary)

    report = run_direct_audio_proof(
        fixture_root=AUDIO_FIXTURE_ROOT,
        receipt_path=RECEIPT,
        consumer_path=CONSUMER,
        workspace=workspace,
        provider=provider,
    )

    assert report.status == "passed"
    assert report.media_types == ("audio/mpeg", "audio/wav", "audio/mp4")
    assert report.published_run_count == 3
    assert report.evidence_count == 3
    assert report.timestamp_evidence is True
    assert report.search_ask_projection_equal is True
    assert report.evidence_schema == "mke.evidence_ref.v1"
    assert report.export_schema == "mke.compiled_library_export.v2"
    assert report.markdown_format == "mke.compiled_markdown.v2"
    assert report.consumer_status == "passed"
    assert report.network_access == "not_used"
    assert report.proof_mode == "model_free"
    assert report.asr_execution == "not_performed"
    assert report.cleanup is True
    assert provider.inspect_count == 3
    assert provider.transcribe_count == 3
    assert {suffix for suffix, _, _ in inspected} == {".mp3", ".wav", ".m4a"}
    assert len({(digest, byte_count) for _, digest, byte_count in inspected}) == 3
    assert not workspace.exists()
    payload = direct_audio_report_payload(report)
    assert set(payload) == {
        "schema_version",
        "status",
        "media_types",
        "published_run_count",
        "evidence_count",
        "timestamp_evidence",
        "search_ask_projection_equal",
        "evidence_schema",
        "export_schema",
        "markdown_format",
        "consumer_status",
        "network_access",
        "proof_mode",
        "asr_execution",
        "cleanup",
    }
    assert "failure_code" not in payload and "next_step" not in payload


def test_receipt_identity_remains_bound_through_snapshot_and_before_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mke.proof import direct_audio

    fixture_root = tmp_path / "audio"
    shutil.copytree(AUDIO_FIXTURE_ROOT, fixture_root)
    original_verify = direct_audio._verify_stable_inputs  # pyright: ignore[reportPrivateUsage]

    def mutate_after_validation(root: Path) -> None:
        original_verify(root)
        target = root / "direct-audio.mp3"
        value = bytearray(target.read_bytes())
        value[0] ^= 0xFF
        target.write_bytes(value)

    monkeypatch.setattr(direct_audio, "_verify_stable_inputs", mutate_after_validation)
    report = run_direct_audio_proof(
        fixture_root=fixture_root,
        receipt_path=RECEIPT,
        consumer_path=CONSUMER,
        workspace=tmp_path / "proof",
        provider=DeterministicAudioProvider(),
    )

    assert report.failure_code == "snapshot_failed"
    assert report.next_step == "retry_with_stable_file"
    assert not (tmp_path / "proof").exists()


def test_report_rejects_unknown_status_and_non_boolean_contract_fields() -> None:
    values = {
        "schema_version": "mke.direct_audio_proof.v1",
        "status": "failed",
        "media_types": (),
        "published_run_count": 0,
        "evidence_count": 0,
        "timestamp_evidence": False,
        "search_ask_projection_equal": False,
        "evidence_schema": "mke.evidence_ref.v1",
        "export_schema": "mke.compiled_library_export.v2",
        "markdown_format": "mke.compiled_markdown.v2",
        "consumer_status": "failed",
        "network_access": "not_used",
        "proof_mode": "model_free",
        "asr_execution": "not_performed",
        "cleanup": True,
        "failure_code": "consumer_failed",
        "next_step": "check_export_consumer",
    }
    with pytest.raises(ValueError):
        DirectAudioProofReport(**{**values, "status": "bogus"})  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        DirectAudioProofReport(
            **{**values, "timestamp_evidence": 0}  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        DirectAudioProofReport(
            **{**values, "proof_mode": "real_asr"}  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        DirectAudioProofReport(
            **{**values, "asr_execution": "performed"}  # type: ignore[arg-type]
        )


def test_workspace_replacement_is_not_deleted_and_reports_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mke.proof import direct_audio

    workspace = tmp_path / "proof"
    displaced = tmp_path / "displaced"

    def displace_workspace(*_args: object, **kwargs: object) -> object:
        active = cast(Path, kwargs["workspace"])
        active.rename(displaced)
        active.mkdir()
        raise DirectAudioProofError("ingest_failed")

    monkeypatch.setattr(
        direct_audio, "_execute_direct_audio_proof", displace_workspace
    )
    report = run_direct_audio_proof(
        fixture_root=AUDIO_FIXTURE_ROOT,
        receipt_path=RECEIPT,
        consumer_path=CONSUMER,
        workspace=workspace,
        provider=DeterministicAudioProvider(),
    )

    assert report.failure_code == "cleanup_failed"
    assert report.cleanup is False
    assert workspace.is_dir()
    assert displaced.is_dir()
    workspace.rmdir()
    displaced.rmdir()


def test_child_boundary_denies_network_and_does_not_inherit_proxy_or_token_state() -> None:
    from mke.proof import direct_audio

    direct_audio._verify_network_denial()  # pyright: ignore[reportPrivateUsage]
    assert direct_audio._PROOF_CHILD_ENVIRONMENT == {  # pyright: ignore[reportPrivateUsage]
        "HF_HUB_OFFLINE": "1",
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "UV_OFFLINE": "1",
    }
    with pytest.raises(DirectAudioProofError, match="consumer_failed"):
        direct_audio._require_network_closed_consumer_source(  # pyright: ignore[reportPrivateUsage]
            "import socket\nsocket.create_connection(('example.invalid', 443))\n"
        )


@pytest.mark.parametrize("failure_code", sorted(DIRECT_AUDIO_PROOF_FAILURE_NEXT_STEPS))
def test_direct_audio_proof_failure_codes_have_exact_next_steps_and_closed_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_code: DirectAudioProofFailureCode,
) -> None:
    from mke.proof import direct_audio

    def fail(*_args: object, **_kwargs: object) -> object:
        raise DirectAudioProofError(failure_code)

    monkeypatch.setattr(direct_audio, "_execute_direct_audio_proof", fail)
    report = run_direct_audio_proof(
        fixture_root=AUDIO_FIXTURE_ROOT,
        receipt_path=RECEIPT,
        consumer_path=CONSUMER,
        workspace=tmp_path / "proof",
        provider=DeterministicAudioProvider(),
    )
    payload = direct_audio_report_payload(report)
    assert payload["status"] == "failed"
    assert payload["failure_code"] == failure_code
    assert payload["next_step"] == DIRECT_AUDIO_PROOF_FAILURE_NEXT_STEPS[failure_code]
    assert set(payload) == {
        "schema_version",
        "status",
        "media_types",
        "published_run_count",
        "evidence_count",
        "timestamp_evidence",
        "search_ask_projection_equal",
        "evidence_schema",
        "export_schema",
        "markdown_format",
        "consumer_status",
        "network_access",
        "proof_mode",
        "asr_execution",
        "cleanup",
        "failure_code",
        "next_step",
    }
    assert str(tmp_path) not in json.dumps(payload)


def test_direct_audio_proof_unknown_exception_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mke.proof import direct_audio

    def fail(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(f"SECRET Traceback {tmp_path}")

    monkeypatch.setattr(direct_audio, "_execute_direct_audio_proof", fail)
    report = run_direct_audio_proof(
        fixture_root=AUDIO_FIXTURE_ROOT,
        receipt_path=RECEIPT,
        consumer_path=CONSUMER,
        workspace=tmp_path / "proof",
        provider=DeterministicAudioProvider(),
    )
    rendered = json.dumps(direct_audio_report_payload(report))
    assert report.failure_code == "ingest_failed"
    assert "SECRET" not in rendered and "Traceback" not in rendered
    assert str(tmp_path) not in rendered


def test_exact_byte_and_duration_boundaries_accept_and_overages_fail_before_transcribe(
    tmp_path: Path, audio_boundary_files: tuple[Path, Path, Path]
) -> None:
    exact, over, duration = audio_boundary_files
    exact_provider = DeterministicAudioProvider()
    engine = KnowledgeEngine(
        tmp_path / "exact.sqlite",
        audio_provider=exact_provider,
        audio_transcription_config=object(),
        audio_preflight=lambda: None,
    )
    try:
        result = engine.ingest_file(exact)
        assert result.evidence_count == 1
    finally:
        engine.close()
    assert exact_provider.transcribe_count == 1

    duration_provider = DeterministicAudioProvider(duration_ms=900_000)
    engine = KnowledgeEngine(
        tmp_path / "duration.sqlite",
        audio_provider=duration_provider,
        audio_transcription_config=object(),
        audio_preflight=lambda: None,
    )
    try:
        result = engine.ingest_file(duration)
        assert result.evidence_count == 1
    finally:
        engine.close()
    assert duration_provider.transcribe_count == 1

    over_provider = DeterministicAudioProvider()
    engine = KnowledgeEngine(
        tmp_path / "over.sqlite",
        audio_provider=over_provider,
        audio_transcription_config=object(),
        audio_preflight=lambda: None,
    )
    try:
        with pytest.raises(AudioIngestError):
            engine.ingest_file(over)
        assert engine.observe_active_publications().active_publication_count == 0
    finally:
        engine.close()
    assert over_provider.inspect_count == 0
    assert over_provider.transcribe_count == 0

    duration_over_provider = DeterministicAudioProvider(duration_ms=900_001)
    engine = KnowledgeEngine(
        tmp_path / "duration-over.sqlite",
        audio_provider=duration_over_provider,
        audio_transcription_config=object(),
        audio_preflight=lambda: None,
    )
    try:
        with pytest.raises(AudioIngestError):
            engine.ingest_file(duration)
        assert engine.observe_active_publications().active_publication_count == 0
    finally:
        engine.close()
    assert duration_over_provider.inspect_count == 1
    assert duration_over_provider.transcribe_count == 0
