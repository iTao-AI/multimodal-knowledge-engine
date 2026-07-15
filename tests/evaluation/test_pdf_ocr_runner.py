from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import subprocess
import zipfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import mke.evaluation.pdf_ocr_runner as runner
from mke.evaluation.pdf_ocr_protocol import load_pdf_ocr_evaluation_protocol
from mke.evaluation.pdf_ocr_provider import (
    OcrEvalLine,
    OcrEvalPageResult,
    PdfOcrProviderError,
    ProviderCommand,
)
from mke.evaluation.pdf_ocr_runner import (
    CandidateOutcome,
    CandidateRunConfig,
    ExactRate,
    ExtractorIdentityError,
    Phase0RunnerConfig,
    canonical_extractor_identity_bytes,
    canonical_scorecard_bytes,
    decide,
    edit_rate,
    extractor_fingerprint,
    publish_and_verify,
    run_phase0_scorecard,
    validate_extractor_identity,
    validate_scorecard,
)

PROTOCOL_PATH = Path("tests/fixtures/pdf-ocr-phase0-v1/protocol.json")
SCORECARD_PATH = Path("benchmarks/ocr/phase0-scorecard.json")
SHA = "a" * 64
SCORECARD_SHA256 = "b84720bd33999ad333e3ac5105b7abd996ab910b3c9cd458f6c43e66fa709457"
PACKAGE_RECEIPT = Path("benchmarks/ocr/candidate-environments.json")
MODEL_RECEIPT = Path("benchmarks/ocr/model-artifacts.json")
STARTUP_RECEIPT = Path("benchmarks/ocr/provider-startup.json")
JsonObject = dict[str, object]
JsonMutation = Callable[[JsonObject], object | None]


def _as_object(value: object) -> JsonObject:
    assert isinstance(value, dict)
    return cast(JsonObject, value)


def _as_objects(value: object) -> list[JsonObject]:
    items = _as_list(value)
    assert all(isinstance(item, dict) for item in items)
    return cast(list[JsonObject], items)


def _as_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def _candidate(payload: JsonObject, index: int) -> JsonObject:
    return _as_objects(payload["candidates"])[index]


def _binding(payload: JsonObject, index: int) -> JsonObject:
    return _as_objects(payload["extractor_identities"])[index]


def _nested(mapping: JsonObject, *keys: str) -> JsonObject:
    current = mapping
    for key in keys:
        current = _as_object(current[key])
    return current


def _completed_doctor(
    doctor: JsonObject,
) -> Callable[..., subprocess.CompletedProcess[bytes]]:
    def run(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 0, json.dumps(doctor).encode(), b"")

    return run


def _identity() -> dict[str, object]:
    return {
        "schema": "mke.pdf_ocr_extractor_identity.v1",
        "protocol": {"id": "pdf-ocr-phase0-v1", "sha256": SHA},
        "fixtures": [
            {"document_id": "a", "source_bytes": 1, "source_sha256": SHA},
            {"document_id": "b", "source_bytes": 2, "source_sha256": "b" * 64},
        ],
        "router": {
            "implementation_sha256": SHA,
            "policy": {
                "accepted_text_min_chars": 32,
                "accepted_text_max_replacement_ratio": {"numerator": 1, "denominator": 100},
                "ocr_text_max_chars": 8,
                "ocr_min_image_coverage": {"numerator": 4, "denominator": 5},
                "render_dpi": 200,
                "max_pages": 32,
                "max_page_pixels": 25_000_000,
                "max_total_rendered_pixels": 100_000_000,
                "max_rendered_file_bytes": 32 * 1024 * 1024,
                "max_total_rendered_bytes": 96 * 1024 * 1024,
            },
        },
        "render": {
            "profile": "phase0-200dpi-png-v1",
            "dpi": 200,
            "pages": [
                {
                    "document_id": "a",
                    "page_number": 1,
                    "image_bytes": 10,
                    "image_sha256": SHA,
                },
                {
                    "document_id": "b",
                    "page_number": 2,
                    "image_bytes": 20,
                    "image_sha256": "b" * 64,
                },
            ],
        },
        "provider": {"id": "provider-v1", "profile": "profile-v1"},
        "model": {"receipt_sha256": SHA, "tree_sha256": "b" * 64},
        "package": {
            "receipt_sha256": SHA,
            "installed_packages_sha256": "b" * 64,
            "mke_wheel_sha256": "c" * 64,
        },
        "normalization": {"implementation_sha256": SHA, "profile": "unicode-nfc-lines-v1"},
    }


def _outcome(
    provider: str,
    *,
    cer: ExactRate | None = None,
    peak_rss_bytes: int = 100,
    failures: tuple[str, ...] = (),
) -> CandidateOutcome:
    return CandidateOutcome(
        provider=provider,
        profile="profile-v1",
        status="passed" if not failures else "failed",
        route_accuracy=ExactRate(10, 10),
        query_accuracy=ExactRate(3, 3),
        evidence_ref_accuracy=ExactRate(3, 3),
        character_error_rate=ExactRate(0, 10) if cer is None else cer,
        word_error_rate=ExactRate(0, 3),
        elapsed_ms=100,
        peak_rss_bytes=peak_rss_bytes,
        temporary_bytes=10,
        result_bytes=10,
        model_bytes=20,
        package_bytes=30,
        cold_start=True,
        failure_codes=failures,
    )


def _scorecard() -> dict[str, object]:
    return json.loads(SCORECARD_PATH.read_bytes())


def _controller_config(
    tmp_path: Path, *, unavailable: frozenset[str] = frozenset()
) -> Phase0RunnerConfig:
    candidates = tuple(
        CandidateRunConfig(
            provider=provider,
            command=(
                None
                if provider in unavailable
                else ProviderCommand(
                    argv=("provider", "{input}", "{output}", "{page_number}"),
                    provider=provider,
                    profile="phase0-200dpi-plain-text-v1",
                )
            ),
            unavailable_code=("provider_unavailable" if provider in unavailable else None),
        )
        for provider in (
            "apple-vision-local-v1",
            "paddleocr-vl-1.6-cpu-spike-v1",
            "ppocrv6-medium-cpu-spike-v1",
        )
    )
    return Phase0RunnerConfig(
        protocol=PROTOCOL_PATH,
        package_receipt=PACKAGE_RECEIPT,
        model_receipt=MODEL_RECEIPT,
        startup_receipt=STARTUP_RECEIPT,
        workspace=tmp_path / "owned-workspace",
        output=tmp_path / "phase0-scorecard.json",
        candidates=candidates,
    )


def _fake_provider(
    command: ProviderCommand,
    *,
    image_path: Path,
    page_number: int,
    output_root: Path,
    **_: object,
) -> OcrEvalPageResult:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    document_id = image_path.parent.name
    expected = next(
        page.expected_ocr_text
        for document in protocol.documents
        if document.document_id == document_id
        for page in document.pages
        if page.page_number == page_number
    )
    output_root.mkdir(parents=True)
    (output_root / "result.json").write_text("{}", encoding="utf-8")
    return OcrEvalPageResult(
        schema="mke.pdf_ocr_page_result.v1",
        provider=command.provider,
        profile=command.profile,
        page_number=page_number,
        lines=(OcrEvalLine(text=expected or "", confidence=1.0, box=(0.0, 0.0, 1.0, 1.0)),),
        normalized_text=expected or "",
        duration_ms=1,
    )


def _authority_shaped_config(tmp_path: Path) -> Phase0RunnerConfig:
    runtime_python = tmp_path / "runtime" / "bin" / "python"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_bytes(b"python")
    model_root = tmp_path / "models"
    components = {
        "layout": model_root / "PP-DocLayoutV3-authority",
        "vl": model_root / "PaddleOCR-VL-1.6-authority",
        "detection": model_root / "PP-OCRv6_medium_det-authority",
        "recognition": model_root / "PP-OCRv6_medium_rec-authority",
    }
    for component in components.values():
        component.mkdir(parents=True)
    sandbox = (
        "/usr/bin/sandbox-exec",
        "-p",
        "(version 1)(allow default)(deny network*)",
    )
    common = ("--input", "{input}", "--output", "{output}", "--page-number", "{page_number}")
    return replace(
        _controller_config(tmp_path),
        candidates=(
            CandidateRunConfig(
                provider="apple-vision-local-v1",
                command=ProviderCommand(
                    argv=(
                        *sandbox,
                        runner._APPLE_EXECUTABLE_PLACEHOLDER,  # pyright: ignore[reportPrivateUsage]
                        *common,
                    ),
                    provider="apple-vision-local-v1",
                    profile="phase0-200dpi-plain-text-v1",
                    timeout_seconds=180,
                ),
            ),
            CandidateRunConfig(
                provider="paddleocr-vl-1.6-cpu-spike-v1",
                command=ProviderCommand(
                    argv=(
                        *sandbox,
                        str(runtime_python),
                        "-I",
                        "-B",
                        "-m",
                        "mke.evaluation.pdf_ocr_paddle_vl",
                        *common,
                        "--layout-model-dir",
                        str(components["layout"]),
                        "--vl-model-dir",
                        str(components["vl"]),
                    ),
                    provider="paddleocr-vl-1.6-cpu-spike-v1",
                    profile="phase0-200dpi-plain-text-v1",
                    timeout_seconds=900,
                ),
            ),
            CandidateRunConfig(
                provider="ppocrv6-medium-cpu-spike-v1",
                command=ProviderCommand(
                    argv=(
                        *sandbox,
                        str(runtime_python),
                        "-I",
                        "-B",
                        "-m",
                        "mke.evaluation.pdf_ocr_ppocrv6",
                        *common,
                        "--detection-model-dir",
                        str(components["detection"]),
                        "--recognition-model-dir",
                        str(components["recognition"]),
                    ),
                    provider="ppocrv6-medium-cpu-spike-v1",
                    profile="phase0-200dpi-plain-text-v1",
                    timeout_seconds=600,
                ),
            ),
        ),
    )


def _path_metadata(path: Path) -> tuple[int, int, int, int, int, int]:
    metadata = path.lstat()
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _fail_after_authority_root_creation(
    monkeypatch: pytest.MonkeyPatch, captured_roots: list[Path]
) -> None:
    def accept_canary(_python: Path) -> None:
        return None

    def accept_bytecode(_prefix: Path, _owned_parent: Path) -> None:
        return None

    def accept_runtime(runtime_python: Path, _authority: object, _home: Path) -> Path:
        return runtime_python.parent.parent

    def accept_models(_components: object, _receipt: object) -> None:
        return None

    monkeypatch.setattr(runner, "_run_network_canary", accept_canary)
    monkeypatch.setattr(runner, "_remove_call_owned_mke_bytecode", accept_bytecode)
    monkeypatch.setattr(runner, "_validate_installed_runtime", accept_runtime)
    monkeypatch.setattr(runner, "_validate_model_root", accept_models)

    def fail_compile(
        authority_root: Path,
    ) -> runner._BoundAppleChild:  # pyright: ignore[reportPrivateUsage]
        captured_roots.append(authority_root)
        raise ValueError("controlled post-creation failure")

    monkeypatch.setattr(runner, "_compile_controller_apple_child", fail_compile)


def _prepare_until_controlled_failure(
    config: Phase0RunnerConfig, monkeypatch: pytest.MonkeyPatch
) -> list[Path]:
    captured_roots: list[Path] = []
    _fail_after_authority_root_creation(monkeypatch, captured_roots)
    authority = runner._load_runner_authority(config)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(runner.Phase0RunnerError, match="current_run_authority_invalid"):
        runner._prepare_current_run_authority(  # pyright: ignore[reportPrivateUsage]
            config, authority
        )
    return captured_roots


def test_current_authority_does_not_delete_preexisting_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _authority_shaped_config(tmp_path)
    preexisting = tmp_path / ".pdf-ocr-current-authority"
    preexisting.mkdir(mode=0o750)
    sentinel = preexisting / "operator-owned-sentinel"
    sentinel.write_bytes(b"operator-owned authority\n")
    before_root = _path_metadata(preexisting)
    before_sentinel = (_path_metadata(sentinel), sentinel.read_bytes())

    captured = _prepare_until_controlled_failure(config, monkeypatch)

    assert _path_metadata(preexisting) == before_root
    assert (_path_metadata(sentinel), sentinel.read_bytes()) == before_sentinel
    assert sorted(item.name for item in preexisting.iterdir()) == [sentinel.name]
    assert len(captured) == 1
    assert captured[0] != preexisting


def test_current_authority_does_not_modify_preexisting_regular_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _authority_shaped_config(tmp_path)
    preexisting = tmp_path / ".pdf-ocr-current-authority"
    preexisting.write_bytes(b"operator-owned regular file\n")
    preexisting.chmod(0o640)
    before = (_path_metadata(preexisting), preexisting.read_bytes())

    captured = _prepare_until_controlled_failure(config, monkeypatch)

    assert (_path_metadata(preexisting), preexisting.read_bytes()) == before
    assert len(captured) == 1
    assert captured[0] != preexisting


def test_current_authority_does_not_follow_preexisting_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _authority_shaped_config(tmp_path)
    target = tmp_path / "operator-owned-target"
    target.mkdir(mode=0o750)
    sentinel = target / "operator-owned-sentinel"
    sentinel.write_bytes(b"operator-owned symlink target\n")
    preexisting = tmp_path / ".pdf-ocr-current-authority"
    preexisting.symlink_to(target, target_is_directory=True)
    before_link = (_path_metadata(preexisting), os.readlink(preexisting))
    before_target = (_path_metadata(target), _path_metadata(sentinel), sentinel.read_bytes())

    captured = _prepare_until_controlled_failure(config, monkeypatch)

    assert preexisting.is_symlink()
    assert (_path_metadata(preexisting), os.readlink(preexisting)) == before_link
    assert (
        _path_metadata(target),
        _path_metadata(sentinel),
        sentinel.read_bytes(),
    ) == before_target
    assert len(captured) == 1
    assert captured[0] != preexisting


def test_current_authority_cleans_exclusively_created_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _authority_shaped_config(tmp_path)

    captured = _prepare_until_controlled_failure(config, monkeypatch)

    assert len(captured) == 1
    assert captured[0].name.startswith(".pdf-ocr-current-authority-")
    assert not captured[0].exists()
    assert not captured[0].is_symlink()


def test_current_authority_cleanup_rejects_symlink_replacement_without_following(
    tmp_path: Path,
) -> None:
    owned_path = tmp_path / ".pdf-ocr-current-authority-owned"
    owned_path.mkdir()
    metadata = owned_path.lstat()
    owned = runner._OwnedAuthorityRoot(  # pyright: ignore[reportPrivateUsage]
        owned_path, metadata.st_dev, metadata.st_ino
    )
    original = tmp_path / "displaced-owned-root"
    os.replace(owned_path, original)
    target = tmp_path / "operator-target"
    target.mkdir(mode=0o750)
    sentinel = target / "sentinel"
    sentinel.write_bytes(b"do not follow\n")
    owned_path.symlink_to(target, target_is_directory=True)
    before_link = (_path_metadata(owned_path), os.readlink(owned_path))
    before_target = (_path_metadata(target), _path_metadata(sentinel), sentinel.read_bytes())

    with pytest.raises(runner.Phase0RunnerError, match="cleanup_failed"):
        runner._cleanup_authority_root(owned)  # pyright: ignore[reportPrivateUsage]

    assert original.is_dir()
    assert owned_path.is_symlink()
    assert (_path_metadata(owned_path), os.readlink(owned_path)) == before_link
    assert (
        _path_metadata(target),
        _path_metadata(sentinel),
        sentinel.read_bytes(),
    ) == before_target


def test_current_authority_cleanup_rejects_directory_replacement(
    tmp_path: Path,
) -> None:
    owned_path = tmp_path / ".pdf-ocr-current-authority-owned"
    owned_path.mkdir()
    metadata = owned_path.lstat()
    owned = runner._OwnedAuthorityRoot(  # pyright: ignore[reportPrivateUsage]
        owned_path, metadata.st_dev, metadata.st_ino
    )
    original = tmp_path / "displaced-owned-root"
    os.replace(owned_path, original)
    replacement = owned_path
    replacement.mkdir(mode=0o750)
    sentinel = replacement / "operator-owned-sentinel"
    sentinel.write_bytes(b"replacement authority\n")
    before = (_path_metadata(replacement), _path_metadata(sentinel), sentinel.read_bytes())

    with pytest.raises(runner.Phase0RunnerError, match="cleanup_failed"):
        runner._cleanup_authority_root(owned)  # pyright: ignore[reportPrivateUsage]

    assert original.is_dir()
    assert (_path_metadata(replacement), _path_metadata(sentinel), sentinel.read_bytes()) == before


def test_current_authority_cleanup_revalidates_after_descriptor_content_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned_path = tmp_path / ".pdf-ocr-current-authority-owned"
    owned_path.mkdir()
    (owned_path / "owned-state").write_bytes(b"call-owned\n")
    metadata = owned_path.lstat()
    owned = runner._OwnedAuthorityRoot(  # pyright: ignore[reportPrivateUsage]
        owned_path, metadata.st_dev, metadata.st_ino
    )
    displaced = tmp_path / "displaced-owned-root"
    real_remove_contents = runner._remove_owned_authority_contents  # pyright: ignore[reportPrivateUsage]

    def swap_after_content_removal(descriptor: int) -> None:
        real_remove_contents(descriptor)
        os.replace(owned_path, displaced)
        owned_path.mkdir(mode=0o750)
        (owned_path / "operator-owned-sentinel").write_bytes(b"operator replacement\n")

    monkeypatch.setattr(runner, "_remove_owned_authority_contents", swap_after_content_removal)

    with pytest.raises(runner.Phase0RunnerError, match="cleanup_failed"):
        runner._cleanup_authority_root(owned)  # pyright: ignore[reportPrivateUsage]

    assert displaced.is_dir()
    assert (owned_path / "operator-owned-sentinel").read_bytes() == b"operator replacement\n"


def test_current_authority_final_removal_is_bound_to_owned_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not Path("/.vol").is_dir():
        pytest.skip("inode-addressed directory removal is a macOS authority boundary")
    owned_path = tmp_path / ".pdf-ocr-current-authority-owned"
    owned_path.mkdir()
    (owned_path / "owned-state").write_bytes(b"call-owned\n")
    metadata = owned_path.lstat()
    owned = runner._OwnedAuthorityRoot(  # pyright: ignore[reportPrivateUsage]
        owned_path, metadata.st_dev, metadata.st_ino
    )
    displaced = tmp_path / "displaced-owned-root"
    replacement_metadata: list[tuple[int, int, int, int, int, int]] = []
    real_rmdir = runner.os.rmdir
    swapped = False

    def swap_at_final_removal(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes], *, dir_fd: int | None = None
    ) -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            os.replace(owned_path, displaced)
            owned_path.mkdir(mode=0o750)
            replacement_metadata.append(_path_metadata(owned_path))
        real_rmdir(path, dir_fd=dir_fd)

    monkeypatch.setattr(runner.os, "rmdir", swap_at_final_removal)

    with pytest.raises(runner.Phase0RunnerError, match="cleanup_failed"):
        runner._cleanup_authority_root(owned)  # pyright: ignore[reportPrivateUsage]

    assert swapped
    assert _path_metadata(owned_path) == replacement_metadata[0]
    assert not displaced.exists()


def test_current_authority_cleanup_failure_blocks_scorecard_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _controller_config(tmp_path)
    config.output.write_bytes(b"prior authority\n")
    owned_path = tmp_path / ".pdf-ocr-current-authority-owned"
    owned_path.mkdir()
    metadata = owned_path.lstat()
    owned = runner._OwnedAuthorityRoot(  # pyright: ignore[reportPrivateUsage]
        owned_path, metadata.st_dev, metadata.st_ino
    )
    apple_path = owned_path / "apple-vision-child"
    apple_path.write_bytes(b"compiled child")
    apple_path.chmod(0o500)
    apple = runner._bind_apple_child(apple_path)  # pyright: ignore[reportPrivateUsage]
    def load_inputs(_config: Phase0RunnerConfig) -> tuple[object, object]:
        return object(), object()

    def prepare_authority(
        _config: Phase0RunnerConfig, _authority: object
    ) -> tuple[Phase0RunnerConfig, object, object]:
        return _config, apple, owned

    def evaluate_scorecard(*_args: object, **_kwargs: object) -> JsonObject:
        return _scorecard()

    monkeypatch.setattr(runner, "_load_controller_inputs", load_inputs)
    monkeypatch.setattr(
        runner,
        "_prepare_current_run_authority",
        prepare_authority,
    )
    monkeypatch.setattr(
        runner,
        "_evaluate_phase0_scorecard",
        evaluate_scorecard,
    )
    def fail_authority_cleanup(_descriptor: int) -> None:
        raise OSError("controlled authority cleanup failure")

    monkeypatch.setattr(runner, "_remove_owned_authority_contents", fail_authority_cleanup)

    with pytest.raises(runner.Phase0RunnerError, match="cleanup_failed"):
        run_phase0_scorecard(config)

    assert config.output.read_bytes() == b"prior authority\n"


def test_public_authority_rejects_unsandboxed_commands_before_owned_writes(
    tmp_path: Path,
) -> None:
    config = _controller_config(tmp_path)
    config.output.write_bytes(b"prior authority\n")

    with pytest.raises(runner.Phase0RunnerError, match="current_run_authority_invalid"):
        run_phase0_scorecard(config)

    assert config.output.read_bytes() == b"prior authority\n"
    assert not config.workspace.exists()


def test_public_authority_entrypoint_rejects_fake_provider_and_rss_injection(
    tmp_path: Path,
) -> None:
    config = _controller_config(tmp_path)

    with pytest.raises(TypeError):
        run_phase0_scorecard(
            config,
            provider_runner=_fake_provider,  # pyright: ignore[reportCallIssue]
            peak_rss_reader=lambda: 1024,  # pyright: ignore[reportCallIssue]
        )

    assert not config.output.exists()
    assert not config.workspace.exists()


@pytest.mark.parametrize(
    ("provider", "replacement"),
    [
        ("paddleocr-vl-1.6-cpu-spike-v1", "mke.evaluation.pdf_ocr_ppocrv6"),
        ("ppocrv6-medium-cpu-spike-v1", "mke.evaluation.pdf_ocr_paddle_vl"),
    ],
)
def test_public_authority_rejects_wrong_provider_module_before_owned_writes(
    tmp_path: Path, provider: str, replacement: str
) -> None:
    config = _authority_shaped_config(tmp_path)
    candidates = list(config.candidates)
    index = next(index for index, item in enumerate(candidates) if item.provider == provider)
    command = candidates[index].command
    assert command is not None
    argv = list(command.argv)
    argv[argv.index("-m") + 1] = replacement
    candidates[index] = replace(candidates[index], command=replace(command, argv=tuple(argv)))
    config = replace(config, candidates=tuple(candidates))

    with pytest.raises(runner.Phase0RunnerError, match="current_run_authority_invalid"):
        run_phase0_scorecard(config)

    assert not config.output.exists()
    assert not config.workspace.exists()


def test_public_authority_rejects_wrong_model_root_before_owned_writes(tmp_path: Path) -> None:
    config = _authority_shaped_config(tmp_path)
    candidates = list(config.candidates)
    command = candidates[1].command
    assert command is not None
    argv = list(command.argv)
    argv[-3] = str(tmp_path / "unbound-layout-model")
    candidates[1] = replace(candidates[1], command=replace(command, argv=tuple(argv)))
    config = replace(config, candidates=tuple(candidates))

    with pytest.raises(runner.Phase0RunnerError, match="current_run_authority_invalid"):
        run_phase0_scorecard(config)

    assert not config.output.exists()
    assert not config.workspace.exists()


def test_public_authority_requires_current_sandbox_canary_before_owned_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _authority_shaped_config(tmp_path)
    probes: list[tuple[str, ...]] = []

    def canary_succeeds(argv: tuple[str, ...], **_: object) -> subprocess.CompletedProcess[bytes]:
        probes.append(argv)
        return subprocess.CompletedProcess(argv, 0, b"connected", b"")

    monkeypatch.setattr(runner.subprocess, "run", canary_succeeds)
    with pytest.raises(runner.Phase0RunnerError, match="current_run_network_not_blocked"):
        run_phase0_scorecard(config)

    assert probes
    assert probes[0][:3] == (
        "/usr/bin/sandbox-exec",
        "-p",
        "(version 1)(allow default)(deny network*)",
    )
    assert not config.output.exists()
    assert not config.workspace.exists()


def test_installed_runtime_doctor_timeout_is_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _authority_shaped_config(tmp_path)

    def timeout(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired("runtime-doctor", 120)

    def accept_canary(_python: Path) -> None:
        return None

    monkeypatch.setattr(runner, "_run_network_canary", accept_canary)
    monkeypatch.setattr(runner.subprocess, "run", timeout)

    with pytest.raises(runner.Phase0RunnerError, match="current_run_authority_invalid"):
        run_phase0_scorecard(config)

    assert not config.output.exists()
    assert not config.workspace.exists()


def _runtime_authority_fixture(
    tmp_path: Path,
    *,
    create_wheel: bool,
    installed_drift: str | None = None,
) -> tuple[
    runner._RunnerAuthority,  # pyright: ignore[reportPrivateUsage]
    Path,
    Path,
    Path,
    dict[str, object],
]:
    authority = runner._load_runner_authority(  # pyright: ignore[reportPrivateUsage]
        _controller_config(tmp_path)
    )
    prefix = tmp_path / "provider-env"
    runtime_python = prefix / "bin/python"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_bytes(b"python")
    site_packages = prefix / "lib/python3.13/site-packages"
    module = site_packages / "mke/__init__.py"
    record = site_packages / "multimodal_knowledge_engine-0.1.2.dist-info/RECORD"
    wheel = tmp_path / authority.mke_wheel_filename
    if create_wheel:
        wheel.parent.mkdir(exist_ok=True)
        module_bytes = b'__version__ = "0.1.2"\n'
        extras = {
            "INSTALLER": b"pip\n",
            "REQUESTED": b"",
            "direct_url.json": b"{}\n",
        }
        console_scripts = {
            "../../../bin/mke": b"#!/bin/sh\n",
            "../../../bin/mke-transcribe-faster-whisper": b"#!/bin/sh\n",
        }
        record_lines = [
            f"mke/__init__.py,{runner._record_hash(module_bytes)},{len(module_bytes)}",  # pyright: ignore[reportPrivateUsage]
            "mke/__pycache__/__init__.cpython-313.pyc,,",
            "multimodal_knowledge_engine-0.1.2.dist-info/RECORD,,",
            *[
                "multimodal_knowledge_engine-0.1.2.dist-info/"
                f"{name},{runner._record_hash(value)},{len(value)}"  # pyright: ignore[reportPrivateUsage]
                for name, value in extras.items()
            ],
            *[
                f"{name},{runner._record_hash(value)},{len(value)}"  # pyright: ignore[reportPrivateUsage]
                for name, value in console_scripts.items()
            ],
        ]
        record_bytes = ("\n".join(record_lines) + "\n").encode()
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("mke/__init__.py", module_bytes)
            archive.writestr(
                "multimodal_knowledge_engine-0.1.2.dist-info/RECORD", record_bytes
            )
        module.parent.mkdir(parents=True)
        record.parent.mkdir(parents=True)
        module.write_bytes(
            b"x" * len(module_bytes) if installed_drift == "module" else module_bytes
        )
        record.write_bytes(
            b"x" * len(record_bytes) if installed_drift == "record" else record_bytes
        )
        for name, value in extras.items():
            (record.parent / name).write_bytes(value)
        for name, value in console_scripts.items():
            path = (site_packages / name).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        encoded = wheel.read_bytes()
        authority = replace(
            authority,
            mke_wheel_sha256=hashlib.sha256(encoded).hexdigest(),
            mke_wheel_bytes=len(encoded),
            package_bytes={**authority.package_bytes, "apple-vision-local-v1": len(encoded)},
        )
    doctor: dict[str, object] = {
        "python": "3.13.12",
        "mke_version": "0.1.2",
        "mke_file": str(module),
        "sys_executable": str(runtime_python),
        "sys_prefix": str(prefix),
        "sys_base_prefix": str(tmp_path / "base-python"),
        "isolated": True,
        "dont_write_bytecode": True,
        "pythonpath_present": False,
        "package_versions": authority.package_versions,
        "direct_url": {
            "archive_info": {
                "hash": f"sha256={authority.mke_wheel_sha256}",
                "hashes": {"sha256": authority.mke_wheel_sha256},
            },
            "url": wheel.as_uri(),
        },
    }
    return authority, runtime_python, module, wheel, doctor


def test_apple_authority_rejects_arbitrary_prebuilt_executable(tmp_path: Path) -> None:
    child = tmp_path / "apple-vision-child"
    child.write_bytes(b"#!/bin/sh\nexit 0\n")
    child.chmod(0o500)
    config = _authority_shaped_config(tmp_path)
    commands = {
        item.provider: item.command for item in config.candidates if item.command is not None
    }
    apple = commands["apple-vision-local-v1"]
    commands["apple-vision-local-v1"] = replace(
        apple, argv=(*apple.argv[:3], str(child), *apple.argv[4:])
    )

    with pytest.raises(ValueError, match="Apple Vision child must be controller-compiled"):
        runner._validate_command_shapes(commands)  # pyright: ignore[reportPrivateUsage]


def test_installed_runtime_rejects_nonexistent_module_and_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authority, runtime_python, module, wheel, doctor = _runtime_authority_fixture(
        tmp_path, create_wheel=False
    )
    assert not module.exists()
    assert not wheel.exists()
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _completed_doctor(doctor),
    )
    home = tmp_path / "authority-home"
    home.mkdir()

    with pytest.raises(ValueError, match="installed MKE wheel identity drifted"):
        runner._validate_installed_runtime(  # pyright: ignore[reportPrivateUsage]
            runtime_python, authority, home
        )


def test_installed_runtime_rejects_receipt_claim_over_drifted_wheel_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authority, runtime_python, module, wheel, doctor = _runtime_authority_fixture(
        tmp_path, create_wheel=False
    )
    wheel.write_bytes(b"x" * authority.package_bytes["apple-vision-local-v1"])
    module.parent.mkdir(parents=True)
    module.write_bytes(b'__version__ = "0.1.2"\n')
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _completed_doctor(doctor),
    )
    home = tmp_path / "authority-home"
    home.mkdir()

    with pytest.raises(ValueError, match="installed MKE wheel identity drifted"):
        runner._validate_installed_runtime(  # pyright: ignore[reportPrivateUsage]
            runtime_python, authority, home
        )


@pytest.mark.parametrize("installed_drift", ["module", "record"])
def test_installed_runtime_rejects_installed_wheel_file_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, installed_drift: str
) -> None:
    authority, runtime_python, _module, _wheel, doctor = _runtime_authority_fixture(
        tmp_path, create_wheel=True, installed_drift=installed_drift
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _completed_doctor(doctor),
    )
    home = tmp_path / "authority-home"
    home.mkdir()

    with pytest.raises(ValueError, match="installed MKE files drifted"):
        runner._validate_installed_runtime(  # pyright: ignore[reportPrivateUsage]
            runtime_python, authority, home
        )


def test_installed_runtime_doctor_uses_the_provider_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authority, runtime_python, _module, _wheel, doctor = _runtime_authority_fixture(
        tmp_path, create_wheel=True
    )
    calls: list[tuple[str, ...]] = []

    def doctor_run(argv: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps(doctor).encode(), b"")

    monkeypatch.setattr(runner.subprocess, "run", doctor_run)
    home = tmp_path / "authority-home"
    home.mkdir()

    runner._validate_installed_runtime(  # pyright: ignore[reportPrivateUsage]
        runtime_python, authority, home
    )

    assert calls[0][:3] == runner._SANDBOX_PREFIX  # pyright: ignore[reportPrivateUsage]
    assert calls[0][4:7] == ("-I", "-B", "-c")


def test_call_owned_runtime_removes_installed_mke_bytecode(tmp_path: Path) -> None:
    prefix = tmp_path / "provider-env"
    package = prefix / "lib/python3.13/site-packages/mke"
    bytecode = package / "__pycache__/runtime.cpython-313.pyc"
    bytecode.parent.mkdir(parents=True)
    bytecode.write_bytes(b"caller-asserted bytecode")
    source = package / "runtime.py"
    source.write_bytes(b"tracked wheel source")

    runner._remove_call_owned_mke_bytecode(  # pyright: ignore[reportPrivateUsage]
        prefix, tmp_path
    )

    assert source.read_bytes() == b"tracked wheel source"
    assert not bytecode.exists()
    assert not bytecode.parent.exists()


def test_swift_source_replacement_during_compile_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "tracked.swift"
    source.write_bytes(b"tracked swift source")
    monkeypatch.setattr(runner, "_APPLE_SWIFT_SOURCE", source)
    monkeypatch.setattr(
        runner, "_APPLE_SWIFT_SOURCE_SHA256", hashlib.sha256(source.read_bytes()).hexdigest()
    )

    def replace_source(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        Path(argv[2]).write_bytes(b"replaced swift source")
        Path(argv[4]).write_bytes(b"compiled-child")
        Path(argv[4]).chmod(0o500)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(runner.subprocess, "run", replace_source)
    authority_root = tmp_path / "authority"
    authority_root.mkdir()

    with pytest.raises(ValueError, match="Apple Vision source identity drifted"):
        runner._compile_controller_apple_child(  # pyright: ignore[reportPrivateUsage]
            authority_root
        )


def test_compiled_apple_child_replacement_fails_closed(tmp_path: Path) -> None:
    child = tmp_path / "apple-vision-child"
    child.write_bytes(b"compiled-child")
    child.chmod(0o500)
    binding = runner._bind_apple_child(child)  # pyright: ignore[reportPrivateUsage]
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"replaced-child")
    replacement.chmod(0o500)
    os.replace(replacement, child)

    with pytest.raises(ValueError, match="Apple Vision child identity drifted"):
        runner._revalidate_apple_child(binding)  # pyright: ignore[reportPrivateUsage]


def test_tracked_controller_runs_candidates_serially_with_common_render_and_atomic_output(
    tmp_path: Path,
) -> None:
    config = _controller_config(tmp_path)
    calls: list[tuple[str, str, int]] = []

    def provider(*args: object, **kwargs: object) -> OcrEvalPageResult:
        command = args[0]
        image_path = kwargs["image_path"]
        page_number = kwargs["page_number"]
        assert isinstance(command, ProviderCommand)
        assert isinstance(image_path, Path)
        assert isinstance(page_number, int)
        calls.append((command.provider, image_path.parent.name, page_number))
        return _fake_provider(command, **kwargs)  # type: ignore[arg-type]

    payload = runner._run_phase0_scorecard_for_test(  # pyright: ignore[reportPrivateUsage]
        config,
        provider_runner=provider,
        peak_rss_reader=lambda: 1024,
    )

    assert payload["decision"] == {
        "status": "go",
        "selected_provider": "apple-vision-local-v1",
        "selected_profile": "phase0-200dpi-plain-text-v1",
    }
    assert [item[0] for item in calls] == [
        provider
        for provider in runner._PROVIDERS  # pyright: ignore[reportPrivateUsage]
        for _ in range(4)
    ]
    assert len({(item[1], item[2]) for item in calls}) == 4
    assert not config.output.exists()
    assert not config.workspace.exists()
    assert not list(tmp_path.glob(".phase0-scorecard.json.*.tmp"))


def test_tracked_controller_records_unavailable_and_failure_without_fabricated_measurements(
    tmp_path: Path,
) -> None:
    unavailable = frozenset({"apple-vision-local-v1"})
    config = _controller_config(tmp_path, unavailable=unavailable)

    def provider(command: ProviderCommand, **kwargs: object) -> OcrEvalPageResult:
        if command.provider == "paddleocr-vl-1.6-cpu-spike-v1":
            raise PdfOcrProviderError(
                problem="pdf_ocr_process_failed",
                cause="PDF OCR process failed",
                next_step="inspect_pdf_ocr_run",
                provider=command.provider,
            )
        return _fake_provider(command, **kwargs)  # type: ignore[arg-type]

    payload = runner._run_phase0_scorecard_for_test(  # pyright: ignore[reportPrivateUsage]
        config,
        provider_runner=provider,
        peak_rss_reader=lambda: 1024,
    )

    outcomes: dict[str, JsonObject] = {}
    for item in _as_objects(payload["candidates"]):
        outcome = _as_object(item["outcome"])
        provider_id = outcome["provider"]
        assert isinstance(provider_id, str)
        outcomes[provider_id] = outcome
    unavailable_outcome = outcomes["apple-vision-local-v1"]
    assert unavailable_outcome["status"] == "unavailable"
    assert unavailable_outcome["failure_codes"] == ["provider_unavailable"]
    assert unavailable_outcome["elapsed_ms"] is None
    failed = outcomes["paddleocr-vl-1.6-cpu-spike-v1"]
    assert failed["status"] == "failed"
    assert failed["failure_codes"] == ["pdf_ocr_process_failed"]
    assert _as_object(payload["decision"])["selected_provider"] == (
        "ppocrv6-medium-cpu-spike-v1"
    )


def test_tracked_controller_emits_deterministic_valid_negative_no_go(tmp_path: Path) -> None:
    config = _controller_config(
        tmp_path,
        unavailable=frozenset(runner._PROVIDERS),  # pyright: ignore[reportPrivateUsage]
    )
    payload = runner._run_phase0_scorecard_for_test(  # pyright: ignore[reportPrivateUsage]
        config, provider_runner=_fake_provider, peak_rss_reader=lambda: 1024
    )
    assert payload["decision"] == {
        "status": "no_go",
        "selected_provider": None,
        "selected_profile": None,
    }
    validate_scorecard(payload)


@pytest.mark.parametrize("receipt_name", ["package_receipt", "model_receipt", "startup_receipt"])
def test_tracked_controller_rejects_committed_receipt_drift_before_workspace(
    tmp_path: Path, receipt_name: str
) -> None:
    config = _controller_config(tmp_path)
    source = getattr(config, receipt_name)
    changed = tmp_path / source.name
    changed.write_bytes(source.read_bytes() + b" ")
    config = replace(config, **{receipt_name: changed})
    with pytest.raises(runner.Phase0RunnerError, match="receipt_authority_invalid"):
        run_phase0_scorecard(config)
    assert not config.workspace.exists()


def test_tracked_controller_preserves_prior_output_when_cleanup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _controller_config(tmp_path)
    config.output.write_bytes(b"prior authority\n")
    real_rmtree = runner.shutil.rmtree

    def fail_owned_cleanup(path: Path, *args: object, **kwargs: object) -> None:
        if Path(path) == config.workspace:
            raise OSError("controlled cleanup failure")
        real_rmtree(path)

    monkeypatch.setattr(runner.shutil, "rmtree", fail_owned_cleanup)
    with pytest.raises(runner.Phase0RunnerError, match="cleanup_failed"):
        runner._run_phase0_scorecard_for_test(  # pyright: ignore[reportPrivateUsage]
            config, provider_runner=_fake_provider, peak_rss_reader=lambda: 1024
        )
    assert config.output.read_bytes() == b"prior authority\n"


def test_tracked_controller_preserves_prior_output_when_atomic_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _controller_config(tmp_path)
    config.output.write_bytes(b"prior authority\n")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("controlled replace failure")

    monkeypatch.setattr(runner.os, "replace", fail_replace)
    with pytest.raises(runner.Phase0RunnerError, match="scorecard_publication_failed"):
        runner._publish_scorecard(  # pyright: ignore[reportPrivateUsage]
            config.output, canonical_scorecard_bytes(_scorecard())
        )
    assert config.output.read_bytes() == b"prior authority\n"
    assert not config.workspace.exists()
    assert not list(tmp_path.glob(".phase0-scorecard.json.*.tmp"))


def test_tracked_controller_cleans_owned_state_after_provider_failure(tmp_path: Path) -> None:
    config = _controller_config(tmp_path)

    def fail_provider(command: ProviderCommand, **_: object) -> OcrEvalPageResult:
        raise PdfOcrProviderError(
            problem="pdf_ocr_process_failed",
            cause="PDF OCR process failed",
            next_step="inspect_pdf_ocr_run",
            provider=command.provider,
        )

    payload = runner._run_phase0_scorecard_for_test(  # pyright: ignore[reportPrivateUsage]
        config,
        provider_runner=fail_provider,
        peak_rss_reader=lambda: 1024,
    )
    assert _as_object(payload["decision"])["status"] == "no_go"
    assert not config.workspace.exists()


def test_edit_rates_use_unicode_code_points_and_whitespace_tokens() -> None:
    assert edit_rate("café", "cafe", unit="codepoint") == ExactRate(1, 4)
    assert edit_rate("café", "cafe\u0301", unit="codepoint") == ExactRate(0, 4)
    assert edit_rate("alpha  beta\r\ngamma", "alpha beta\ngamma", unit="codepoint") == ExactRate(
        0, 16
    )
    assert edit_rate("alpha beta", "alpha gamma beta", unit="whitespace_token") == ExactRate(1, 2)
    assert edit_rate("海燕四十二号", "海燕四十号", unit="codepoint") == ExactRate(1, 6)


def test_extractor_identity_is_closed_and_byte_deterministic() -> None:
    payload = _identity()
    validate_extractor_identity(payload)
    expected = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    assert canonical_extractor_identity_bytes(payload) == expected
    assert extractor_fingerprint(payload) == (
        "pdf-ocr-eval-v1:" + hashlib.sha256(expected).hexdigest()
    )


def _identity_add_extra(value: JsonObject) -> None:
    value.update({"extra": True})


def _identity_remove_model(value: JsonObject) -> object:
    return value.pop("model")


def _identity_reverse_fixtures(value: JsonObject) -> None:
    _as_list(value["fixtures"]).reverse()


def _identity_duplicate_fixture(value: JsonObject) -> None:
    fixtures = _as_list(value["fixtures"])
    fixtures.append(copy.deepcopy(fixtures[0]))


def _identity_reverse_render_pages(value: JsonObject) -> None:
    _as_list(_nested(value, "render")["pages"]).reverse()


def _identity_set_boolean_limit(value: JsonObject) -> None:
    _nested(value, "router", "policy").update({"max_pages": True})


def _identity_set_nonfinite_ratio(value: JsonObject) -> None:
    _nested(value, "router", "policy").update(
        {
            "ocr_min_image_coverage": {
                "numerator": math.nan,
                "denominator": 1,
            }
        }
    )


@pytest.mark.parametrize(
    "mutation",
    [
        _identity_add_extra,
        _identity_remove_model,
        _identity_reverse_fixtures,
        _identity_duplicate_fixture,
        _identity_reverse_render_pages,
        _identity_set_boolean_limit,
        _identity_set_nonfinite_ratio,
    ],
)
def test_extractor_identity_rejects_schema_order_and_type_drift(
    mutation: JsonMutation,
) -> None:
    payload = _identity()
    mutation(payload)
    with pytest.raises(ExtractorIdentityError):
        validate_extractor_identity(payload)


def test_every_authority_leaf_changes_fingerprint() -> None:
    original = _identity()
    original_fingerprint = extractor_fingerprint(original)
    for path in _leaf_paths(original):
        changed = copy.deepcopy(original)
        parent = _at_path(changed, path[:-1])
        key = path[-1]
        value = parent[key]
        if isinstance(value, str):
            parent[key] = ("f" * 64) if len(value) == 64 else value + "-changed"
        elif type(value) is int:
            parent[key] = value + 1
        else:
            raise AssertionError(f"unsupported identity leaf at {path}")
        try:
            assert extractor_fingerprint(changed) != original_fingerprint
        except ExtractorIdentityError:
            pass


def test_every_nested_identity_object_rejects_missing_and_extra_keys() -> None:
    original = _identity()
    for path in _mapping_paths(original):
        for operation in ("missing", "extra"):
            changed = copy.deepcopy(original)
            target = _at_path(changed, path)
            if operation == "missing":
                target.pop(next(iter(target)))
            else:
                target["unexpected"] = True
            with pytest.raises(ExtractorIdentityError):
                validate_extractor_identity(changed)


def test_every_identity_integer_rejects_boolean_and_non_finite_values() -> None:
    original = _identity()
    integer_paths = [
        path
        for path in _leaf_paths(original)
        if type(_at_path(original, path[:-1])[path[-1]]) is int
    ]
    for replacement in (True, math.nan):
        for path in integer_paths:
            changed = copy.deepcopy(original)
            _at_path(changed, path[:-1])[path[-1]] = replacement
            with pytest.raises(ExtractorIdentityError):
                validate_extractor_identity(changed)


def test_decision_requires_every_hard_gate_and_uses_deterministic_tiebreaks() -> None:
    failed = _outcome("a-provider", cer=ExactRate(0, 10), failures=("evidence_ref_mismatch",))
    slower = _outcome("z-provider", cer=ExactRate(1, 10), peak_rss_bytes=200)
    winner = _outcome("a-provider", cer=ExactRate(1, 10), peak_rss_bytes=100)

    decision = decide((failed, slower, winner))

    assert decision.status == "go"
    assert decision.selected_provider == "a-provider"
    assert decision.selected_profile == "profile-v1"
    assert decision.outcomes == (failed, slower, winner)
    assert decide((failed,)).status == "no_go"
    assert decide((failed,)).selected_provider is None


def test_disposable_publication_uses_search_ask_and_exact_evidence_refs(tmp_path: Path) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    recognized = {
        (document.document_id, page.page_number): page.expected_ocr_text
        for document in protocol.documents
        for page in document.pages
        if page.expected_ocr_text is not None
    }

    proof = publish_and_verify(
        protocol=protocol,
        recognized_text=recognized,
        extractor_identity=_identity(),
        database=tmp_path / "evaluation.sqlite",
    )

    assert proof.route_accuracy == ExactRate(9, 9)
    assert proof.query_accuracy == ExactRate(3, 3)
    assert proof.evidence_ref_accuracy == ExactRate(3, 3)
    assert proof.publication_evidence_pages == frozenset(
        {
            ("english-scan", 1),
            ("chinese-scan", 1),
            ("mixed-prose", 1),
            ("mixed-prose", 2),
            ("routing-adversarial", 5),
        }
    )
    assert proof.publication_evidence_pages.isdisjoint(
        {("routing-adversarial", page) for page in (1, 2, 3, 4)}
    )
    assert proof.failure_codes == ()


@pytest.mark.parametrize("surface", ["search", "ask"])
@pytest.mark.parametrize(
    ("field", "replacement", "failure_code"),
    [
        ("schema_version", "mke.evidence_ref.v2", "evidence_ref_mismatch"),
        ("evidence_id", "ev_" + "f" * 32, "evidence_ref_mismatch"),
        ("source_id", "src_" + "f" * 32, "evidence_ref_mismatch"),
        ("content_fingerprint", "sha256:" + "f" * 64, "evidence_ref_mismatch"),
        ("publication_id", "pub_" + "f" * 32, "evidence_ref_mismatch"),
        ("publication_revision", 99, "evidence_ref_mismatch"),
        ("run_id", "run_" + "f" * 32, "evidence_ref_mismatch"),
        ("locator_kind", {"kind": "timestamp_ms"}, "evidence_ref_mismatch"),
        ("locator_start", {"start": 2}, "evidence_ref_mismatch"),
        ("locator_end", {"end": 2}, "evidence_ref_mismatch"),
        ("text", "wrong normalized payload", "payload_truth_mismatch"),
    ],
)
def test_product_proof_rejects_every_portable_evidence_leaf_and_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
    field: str,
    replacement: object,
    failure_code: str,
) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    recognized = {
        (document.document_id, page.page_number): page.expected_ocr_text
        for document in protocol.documents
        for page in document.pages
        if page.expected_ocr_text is not None
    }
    function_name = f"{surface}_library_v1"
    real_function = getattr(runner, function_name)
    expected_text_by_query = {
        query.text: next(
            page.expected_ocr_text or page.expected_text_layer_text
            for document in protocol.documents
            if document.document_id == query.expected_document_id
            for page in document.pages
            if page.page_number == query.expected_page
        )
        for query in protocol.queries
    }

    def mutate_response(config: object, query: str) -> object:
        response = real_function(config, query)
        root = response.root
        collection_name = "results" if surface == "search" else "evidence"
        items = list(getattr(root, collection_name))
        target = next(
            index for index, item in enumerate(items) if item.text == expected_text_by_query[query]
        )
        if field.startswith("locator_"):
            changed = items[target].model_copy(
                update={"locator": items[target].locator.model_copy(update=replacement)}
            )
        else:
            changed = items[target].model_copy(update={field: replacement})
        items[target] = changed
        changed_root = root.model_copy(update={collection_name: items})
        return response.model_copy(update={"root": changed_root})

    monkeypatch.setattr(runner, function_name, mutate_response)
    proof = publish_and_verify(
        protocol=protocol,
        recognized_text=recognized,
        extractor_identity=_identity(),
        database=tmp_path / "evaluation.sqlite",
    )

    assert failure_code in proof.failure_codes
    assert proof.evidence_ref_accuracy != ExactRate(3, 3)


def test_missing_ocr_text_fails_closed_before_product_success(tmp_path: Path) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    proof = publish_and_verify(
        protocol=protocol,
        recognized_text={},
        extractor_identity=_identity(),
        database=tmp_path / "evaluation.sqlite",
    )
    assert "provider_output_incomplete" in proof.failure_codes
    assert proof.query_accuracy != ExactRate(3, 3)


def test_route_truth_mismatch_fails_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    recognized = {
        (document.document_id, page.page_number): page.expected_ocr_text
        for document in protocol.documents
        for page in document.pages
        if page.expected_ocr_text is not None
    }
    real_inspect = runner.inspect_pdf

    def inspect_with_mismatch(path: Path, policy: object) -> object:
        inspection = real_inspect(path, policy)  # type: ignore[arg-type]
        if path.name != "english-scan.pdf":
            return inspection
        first = replace(inspection.decisions[0], route="text_layer_accepted")
        return replace(inspection, decisions=(first, *inspection.decisions[1:]))

    monkeypatch.setattr(runner, "inspect_pdf", inspect_with_mismatch)
    proof = publish_and_verify(
        protocol=protocol,
        recognized_text=recognized,
        extractor_identity=_identity(),
        database=tmp_path / "evaluation.sqlite",
    )
    assert proof.route_accuracy == ExactRate(8, 9)
    assert proof.query_accuracy == ExactRate(0, 3)
    assert proof.failure_codes == ("route_truth_mismatch",)
    assert not (tmp_path / "evaluation.sqlite").exists()


def test_scorecard_serialization_is_stable_finite_and_public_neutral() -> None:
    payload = _scorecard()
    encoded = canonical_scorecard_bytes(payload)
    assert encoded.endswith(b"\n")
    assert b"NaN" not in encoded
    assert b"/Users/" not in encoded
    assert canonical_scorecard_bytes(json.loads(encoded)) == encoded


def _scorecard_add_extra(value: JsonObject) -> None:
    value.update({"extra": True})


def _scorecard_drift_receipt(value: JsonObject) -> None:
    _nested(value, "receipts").update({"package_sha256": "bad"})


def _scorecard_duplicate_candidate(value: JsonObject) -> None:
    candidates = _as_list(value["candidates"])
    candidates.append(copy.deepcopy(candidates[0]))


def _scorecard_drift_fingerprint(value: JsonObject) -> None:
    _binding(value, 0).update({"fingerprint": "pdf-ocr-eval-v1:" + "f" * 64})


def _scorecard_set_boolean_measurement(value: JsonObject) -> None:
    _nested(_candidate(value, 0), "outcome").update({"elapsed_ms": True})


def _scorecard_reverse_page_results(value: JsonObject) -> None:
    _as_list(_candidate(value, 0)["page_results"]).reverse()


def _scorecard_force_no_go(value: JsonObject) -> None:
    value.update(
        {
            "decision": {
                "status": "no_go",
                "selected_provider": None,
                "selected_profile": None,
            }
        }
    )


@pytest.mark.parametrize(
    "mutation",
    [
        _scorecard_add_extra,
        _scorecard_drift_receipt,
        _scorecard_duplicate_candidate,
        _scorecard_drift_fingerprint,
        _scorecard_set_boolean_measurement,
        _scorecard_reverse_page_results,
        _scorecard_force_no_go,
    ],
)
def test_scorecard_schema_is_closed_and_cross_bound(mutation: JsonMutation) -> None:
    payload = _scorecard()
    mutation(payload)
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize(
    "measurement",
    [
        "elapsed_ms",
        "peak_rss_bytes",
        "temporary_bytes",
        "result_bytes",
        "model_bytes",
        "package_bytes",
        "cold_start",
    ],
)
def test_passed_candidate_requires_every_complete_measurement(measurement: str) -> None:
    payload = _scorecard()
    selected = _nested(_candidate(payload, 2), "outcome")
    selected[measurement] = None
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize(
    "measurement",
    [
        "elapsed_ms",
        "peak_rss_bytes",
        "temporary_bytes",
        "result_bytes",
        "model_bytes",
        "package_bytes",
    ],
)
def test_passed_candidate_rejects_boolean_numeric_measurements(measurement: str) -> None:
    payload = _scorecard()
    _nested(_candidate(payload, 2), "outcome")[measurement] = True
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize("status", ["failed", "unavailable"])
def test_nonpassing_candidate_may_preserve_unknown_measurements(status: str) -> None:
    payload = _scorecard()
    candidate = _candidate(payload, 0)
    outcome = _nested(candidate, "outcome")
    outcome.update(
        {
            "status": status,
            "elapsed_ms": None,
            "peak_rss_bytes": None,
            "temporary_bytes": None,
            "result_bytes": None,
            "model_bytes": None,
            "package_bytes": None,
            "cold_start": None,
            "failure_codes": [f"provider_{status}"],
        }
    )
    candidate["page_results"] = []
    candidate["publication_evidence_pages"] = []
    validate_scorecard(payload)


def test_scorecard_rejects_top_level_protocol_authority_drift() -> None:
    payload = _scorecard()
    _nested(payload, "protocol")["sha256"] = "f" * 64
    with pytest.raises(ValueError):
        validate_scorecard(payload)


def test_scorecard_rejects_identity_protocol_authority_drift() -> None:
    payload = _scorecard()
    binding = _binding(payload, 1)
    identity = _nested(binding, "payload")
    _nested(identity, "protocol")["sha256"] = "f" * 64
    binding["fingerprint"] = extractor_fingerprint(identity)
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize("authority", ["fixtures", "render"])
def test_scorecard_rejects_cross_provider_comparison_identity_drift(authority: str) -> None:
    payload = _scorecard()
    binding = _binding(payload, 1)
    identity = _nested(binding, "payload")
    if authority == "fixtures":
        fixtures = _as_objects(identity["fixtures"])
        fixtures[0]["source_sha256"] = "f" * 64
    else:
        pages = _as_objects(_nested(identity, "render")["pages"])
        pages[0]["image_sha256"] = "f" * 64
    binding["fingerprint"] = extractor_fingerprint(identity)
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize("mutation", ["blank", "missing", "extra"])
def test_scorecard_rejects_publication_page_inventory_drift(mutation: str) -> None:
    payload = _scorecard()
    for candidate in _as_objects(payload["candidates"]):
        pages = _as_list(candidate["publication_evidence_pages"])
        if mutation == "blank":
            pages[-1] = {"document_id": "routing-adversarial", "page_number": 1}
        elif mutation == "missing":
            pages.pop()
        else:
            pages.append({"document_id": "routing-adversarial", "page_number": 1})
    with pytest.raises(ValueError):
        validate_scorecard(payload)


def test_scorecard_rejects_internal_receipt_leaf_drift() -> None:
    payload = _scorecard()
    binding = _binding(payload, 1)
    identity = _nested(binding, "payload")
    _nested(identity, "package")["receipt_sha256"] = "f" * 64
    binding["fingerprint"] = extractor_fingerprint(identity)
    with pytest.raises(ValueError):
        validate_scorecard(payload)


def test_scorecard_rejects_candidate_page_render_identity_drift() -> None:
    payload = _scorecard()
    pages = _as_objects(_candidate(payload, 1)["page_results"])
    pages[0]["image_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize(
    "unsafe",
    [
        "/private/tmp/operator-cache",
        "/tmp/operator-cache",
        r"C:\\operator\\cache",
        r"\\\\host\\share",
        "file:///tmp/operator-cache",
        "operator-host.local",
        "2026-07-15T12:34:56Z",
    ],
)
def test_scorecard_rejects_non_neutral_profile_values(unsafe: str) -> None:
    payload = _scorecard()
    for binding, candidate in zip(
        _as_objects(payload["extractor_identities"]),
        _as_objects(payload["candidates"]),
        strict=True,
    ):
        _nested(binding, "payload", "provider")["profile"] = unsafe
        _nested(candidate, "outcome")["profile"] = unsafe
    _nested(payload, "decision")["selected_profile"] = unsafe
    with pytest.raises(ValueError):
        canonical_scorecard_bytes(payload)


def test_committed_scorecard_is_canonical_closed_and_frozen() -> None:
    encoded = SCORECARD_PATH.read_bytes()
    payload = cast(JsonObject, json.loads(encoded))
    validate_scorecard(payload)
    assert canonical_scorecard_bytes(payload) == encoded
    assert hashlib.sha256(encoded).hexdigest() == SCORECARD_SHA256
    assert payload["decision"] == {
        "status": "go",
        "selected_provider": "ppocrv6-medium-cpu-spike-v1",
        "selected_profile": "phase0-200dpi-plain-text-v1",
    }
    receipt_paths = {
        "package_sha256": Path("benchmarks/ocr/candidate-environments.json"),
        "model_sha256": Path("benchmarks/ocr/model-artifacts.json"),
        "provider_startup_sha256": Path("benchmarks/ocr/provider-startup.json"),
    }
    assert payload["receipts"] == {
        key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in receipt_paths.items()
    }
    startup = cast(
        JsonObject,
        json.loads(receipt_paths["provider_startup_sha256"].read_bytes()),
    )
    model = cast(JsonObject, json.loads(receipt_paths["model_sha256"].read_bytes()))
    startup_runtime = _nested(startup, "runtime")
    for binding in _as_objects(payload["extractor_identities"]):
        identity = _nested(binding, "payload")
        package = _nested(identity, "package")
        model_identity = _nested(identity, "model")
        assert package["receipt_sha256"] == startup["package_receipt_sha256"]
        assert package["mke_wheel_sha256"] == startup_runtime["mke_wheel_sha256"]
        assert (
            package["installed_packages_sha256"]
            == startup_runtime["installed_packages_sha256"]
        )
        assert model_identity["receipt_sha256"] == startup["model_receipt_sha256"]
        assert model_identity["tree_sha256"] == model["tree_sha256"]


def _leaf_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        return [
            leaf
            for key, item in mapping.items()
            for leaf in _leaf_paths(item, (*path, key))
        ]
    if isinstance(value, list):
        items = cast(list[object], value)
        return [
            leaf
            for index, item in enumerate(items)
            for leaf in _leaf_paths(item, (*path, index))
        ]
    return [path]


def _mapping_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    paths = [path] if isinstance(value, dict) else []
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        for key, item in mapping.items():
            paths.extend(_mapping_paths(item, (*path, key)))
    elif isinstance(value, list):
        items = cast(list[object], value)
        for index, item in enumerate(items):
            paths.extend(_mapping_paths(item, (*path, index)))
    return paths


def _at_path(value: object, path: tuple[object, ...]) -> dict[object, object]:
    current = value
    for part in path:
        if isinstance(current, dict):
            current = cast(dict[object, object], current)[part]
        else:
            assert isinstance(current, list)
            assert isinstance(part, int)
            current = cast(list[object], current)[part]
    assert isinstance(current, dict)
    return cast(dict[object, object], current)
