from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from mke.adapters.audio import InternalAudioProvider, snapshot_audio_source
from mke.adapters.audio.inspection import AudioInspectionError, AudioInspectionRequest
from mke.adapters.audio.inspection_cli import inspect_audio, main
from mke.adapters.video.process import (
    ActiveProcessController,
    ProcessOperationId,
    SupervisedProcessError,
    SupervisedProcessProfile,
    process_group_absent,
    run_supervised_process,
    terminate_process_group,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "audio"


@pytest.mark.parametrize(
    ("filename", "container", "codec"),
    [
        ("direct-audio.mp3", "mp3", "mp3"),
        ("direct-audio.wav", "wav", "pcm_s16le"),
        ("direct-audio.m4a", "m4a", "aac"),
    ],
)
def test_inspection_child_parses_closed_fixture_profile(
    tmp_path: Path, filename: str, container: str, codec: str
) -> None:
    source = FIXTURES / filename
    snapshot = snapshot_audio_source(source, tmp_path / "owned")
    request = AudioInspectionRequest(
        path=str(snapshot.owned_path),
        expected_suffix=source.suffix,  # type: ignore[typeddict-item]
        expected_sha256=snapshot.owned_identity.sha256,
        expected_bytes=snapshot.owned_identity.bytes,
    )

    result = inspect_audio(request)

    assert result["schema_version"] == "mke.audio_inspection.v1"
    assert result["media"]["container"] == container
    assert result["media"]["audio_codec"] == codec
    assert result["observed_sha256"] == snapshot.owned_identity.sha256
    assert result["observed_bytes"] == snapshot.owned_identity.bytes
    assert set(result) == {
        "schema_version",
        "media",
        "observed_sha256",
        "observed_bytes",
    }


def test_inspection_child_revalidates_path_after_native_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FIXTURES / "direct-audio.wav"
    snapshot = snapshot_audio_source(source, tmp_path / "owned")
    request = AudioInspectionRequest(
        path=str(snapshot.owned_path),
        expected_suffix=".wav",
        expected_sha256=snapshot.owned_identity.sha256,
        expected_bytes=snapshot.owned_identity.bytes,
    )

    def replace_after_open(stream: object) -> object:
        replacement = tmp_path / "replacement"
        replacement.write_bytes(source.read_bytes())
        replacement.chmod(0o400)
        os.replace(replacement, snapshot.owned_path)
        from mke.adapters.audio.inspection_cli import _inspect_container

        return _inspect_container(stream)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "mke.adapters.audio.inspection_cli._inspect_audio_stream",
        replace_after_open,
    )

    with pytest.raises(AudioInspectionError, match="inspection_identity_mismatch"):
        inspect_audio(request)


def test_inspection_cli_emits_one_compact_closed_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    media = {
        "container": "wav",
        "audio_codec": "pcm_s16le",
        "channels": 1,
        "sample_rate_hz": 16_000,
        "duration_ms": 1_000,
    }
    monkeypatch.setattr(
        "mke.adapters.audio.inspection_cli.inspect_audio",
        lambda request: {
            "schema_version": "mke.audio_inspection.v1",
            "media": media,
            "observed_sha256": request["expected_sha256"],
            "observed_bytes": request["expected_bytes"],
        },
    )
    path = tmp_path / "sealed"
    path.write_bytes(b"x")

    exit_code = main(
        [
            "--path",
            str(path),
            "--expected-suffix",
            ".wav",
            "--expected-sha256",
            hashlib.sha256(b"x").hexdigest(),
            "--expected-bytes",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out)["media"] == media


def test_inspection_cli_redacts_native_parser_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = f"SECRET {tmp_path}"
    monkeypatch.setattr(
        "mke.adapters.audio.inspection_cli.inspect_audio",
        lambda request: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    path = tmp_path / "sealed"
    path.write_bytes(b"x")

    exit_code = main(
        [
            "--path",
            str(path),
            "--expected-suffix",
            ".wav",
            "--expected-sha256",
            "a" * 64,
            "--expected-bytes",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 40
    assert captured.out == ""
    assert secret not in captured.err
    assert str(tmp_path) not in captured.err


def test_inspection_child_rejects_corrupt_native_media(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.wav"
    source.write_bytes(b"not a wave file")
    snapshot = snapshot_audio_source(source, tmp_path / "owned")
    request = AudioInspectionRequest(
        path=str(snapshot.owned_path),
        expected_suffix=".wav",
        expected_sha256=snapshot.owned_identity.sha256,
        expected_bytes=snapshot.owned_identity.bytes,
    )

    with pytest.raises(AudioInspectionError, match="audio_profile_unsupported"):
        inspect_audio(request)


def test_inspection_module_uses_isolated_package_child_argv() -> None:
    from mke.adapters.audio import AUDIO_INSPECTION_COMMAND

    assert AUDIO_INSPECTION_COMMAND == (
        sys.executable,
        "-I",
        "-B",
        "-m",
        "mke.adapters.audio.inspection_cli",
    )


def test_real_inspection_provider_uses_darwin_footprint_supervisor(
    tmp_path: Path,
) -> None:
    source = FIXTURES / "direct-audio.wav"
    snapshot = snapshot_audio_source(source, tmp_path / "owned")
    provider = InternalAudioProvider(
        SupervisedProcessProfile(
            wall_seconds=10,
            stdout_bytes=8192,
            stderr_bytes=4096,
            footprint_bytes=256 * 1024 * 1024,
        )
    )

    media = provider.inspect(snapshot, suffix=".wav")

    assert media.container == "wav"
    assert media.audio_codec == "pcm_s16le"


def test_supervisor_uses_shell_false_dedicated_group_and_closed_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    original_popen: Any = subprocess.Popen

    def spy(*args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", spy)
    result = run_supervised_process(
        (sys.executable, "-I", "-B", "-c", "print('ok')"),
        environment={},
        profile=SupervisedProcessProfile(5, 64, 64, footprint_bytes=None),
    )

    assert result.stdout == b"ok\n"
    assert captured["shell"] is False
    assert captured["start_new_session"] is True
    assert captured["close_fds"] is True
    assert result.supervision.hard_kernel_enforced is False
    assert result.supervision.leader_scope == "process_group_leader"
    assert result.supervision.descendants_scope == "ordinary_cooperative_descendants"
    assert not hasattr(result.supervision, "sandbox")
    assert not hasattr(result.supervision, "hostile_media_containment")


@pytest.mark.skipif(
    platform.system() != "Darwin" or platform.machine() != "arm64",
    reason="Darwin arm64 proc_pid_rusage authority",
)
def test_real_controlled_allocator_records_leader_only_footprint() -> None:
    result = run_supervised_process(
        (sys.executable, "-I", "-B", "-c", "value=bytearray(4*1024*1024);print(len(value))"),
        environment={},
        profile=SupervisedProcessProfile(
            5,
            128,
            128,
            footprint_bytes=128 * 1024 * 1024,
        ),
    )

    receipt = result.supervision
    assert result.stdout == b"4194304\n"
    assert receipt.api == "proc_pid_rusage"
    assert receipt.api_version == "RUSAGE_INFO_V4"
    assert receipt.metric == "ri_phys_footprint"
    assert receipt.leader_identity_binding == "pid+ri_proc_start_abstime"
    assert receipt.observed_max_bytes >= receipt.baseline_bytes > 0
    assert receipt.budget_outcome == "within_budget"
    assert receipt.transient_overshoot_possible is True
    assert receipt.cleanup.process_group_absent is True


def test_allocator_transient_footprint_overshoot_terminates_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Sampler:
        identity = "leader"
        calls = 0

        def sample(self) -> int:
            self.calls += 1
            return 0 if self.calls == 1 else 8192

    monkeypatch.setattr(
        "mke.adapters.video.process.DarwinFootprintSampler",
        lambda pid: Sampler(),
    )

    with pytest.raises(SupervisedProcessError, match="footprint_budget_exceeded") as raised:
        run_supervised_process(
            (sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"),
            environment={},
            profile=SupervisedProcessProfile(
                5,
                128,
                128,
                footprint_bytes=4096,
                footprint_budget_mode="absolute",
                termination_grace_seconds=0.05,
            ),
        )

    receipt = raised.value.receipt
    assert receipt is not None
    assert receipt.budget_outcome == "exceeded_terminated"
    assert receipt.observed_max_bytes == 8192
    assert receipt.overshoot_bytes == 4096
    assert receipt.cleanup.sigterm_sent is True
    assert receipt.cleanup.process_group_absent is True


def test_leader_identity_drift_fails_closed_and_cleans_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Sampler:
        identities = iter(("bound", "drift"))

        @property
        def identity(self) -> str:
            return next(self.identities)

        def sample(self) -> int:
            return 1024

    monkeypatch.setattr(
        "mke.adapters.video.process.DarwinFootprintSampler",
        lambda pid: Sampler(),
    )

    with pytest.raises(
        SupervisedProcessError, match="footprint_leader_identity_drift"
    ) as raised:
        run_supervised_process(
            (sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"),
            environment={},
            profile=SupervisedProcessProfile(5, 128, 128, footprint_bytes=4096),
        )

    assert raised.value.receipt is not None
    assert raised.value.receipt.cleanup.process_group_absent is True


def test_timeout_cleans_ordinary_descendant_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "descendant"
    source = (
        "import pathlib,subprocess,sys,time;"
        "child=subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(30)']);"
        f"pathlib.Path({str(marker)!r}).write_text(str(child.pid),encoding='ascii');"
        "time.sleep(30)"
    )
    processes: list[subprocess.Popen[bytes]] = []
    original_popen: Any = subprocess.Popen

    def capture(*args: object, **kwargs: object) -> object:
        process = original_popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", capture)

    with pytest.raises(SupervisedProcessError, match="process_timeout") as raised:
        run_supervised_process(
            (sys.executable, "-I", "-B", "-c", source),
            environment={},
            profile=SupervisedProcessProfile(
                0.2,
                128,
                128,
                footprint_bytes=None,
                termination_grace_seconds=0.05,
            ),
        )

    assert marker.exists()
    assert processes
    assert process_group_absent(processes[0].pid) is True
    assert raised.value.receipt is not None
    assert raised.value.receipt.cleanup.process_group_absent is True


def test_cancellation_latch_terminates_late_registered_group() -> None:
    controller = ActiveProcessController()
    operation_id = controller.begin_operation()
    controller.cancel_operation(operation_id)

    result = run_supervised_process(
        (sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"),
        environment={},
        profile=SupervisedProcessProfile(5, 128, 128, footprint_bytes=None),
        process_controller=controller,
        process_operation_id=operation_id,
    )

    assert result.returncode != 0
    assert result.supervision.cleanup.process_group_absent is True
    assert result.supervision.cleanup.sigterm_sent is True
    controller.end_operation(operation_id)


def test_registration_failure_cleans_group() -> None:
    with pytest.raises(SupervisedProcessError) as raised:
        run_supervised_process(
            (sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"),
            environment={},
            profile=SupervisedProcessProfile(5, 128, 128, footprint_bytes=None),
            process_controller=ActiveProcessController(),
            process_operation_id=ProcessOperationId("missing"),
        )

    assert raised.value.receipt is not None
    assert raised.value.receipt.cleanup.process_group_absent is True


@pytest.mark.parametrize(
    ("stream", "source"),
    [
        ("stdout", "print('x'*1000)"),
        ("stderr", "import sys;sys.stderr.write('x'*1000)"),
    ],
)
def test_supervisor_output_limit_cleans_group(stream: str, source: str) -> None:
    with pytest.raises(SupervisedProcessError, match=f"{stream}_limit_exceeded") as raised:
        run_supervised_process(
            (sys.executable, "-I", "-B", "-c", source),
            environment={},
            profile=SupervisedProcessProfile(5, 16, 16, footprint_bytes=None),
        )
    assert raised.value.receipt is not None
    assert raised.value.receipt.cleanup.process_group_absent is True


def test_native_signal_exit_does_not_terminate_owner() -> None:
    result = run_supervised_process(
        (
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import os,signal;os.kill(os.getpid(),signal.SIGKILL)",
        ),
        environment={},
        profile=SupervisedProcessProfile(5, 64, 64, footprint_bytes=None),
    )

    assert result.returncode == -signal.SIGKILL
    assert result.supervision.cleanup.process_group_absent is True


def test_process_group_signal_failure_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = type(
        "FakeProcess",
        (),
        {"pid": 4242, "poll": lambda self: None, "wait": lambda self, timeout=None: 0},
    )()
    monkeypatch.setattr("mke.adapters.video.process.process_group_absent", lambda pid: False)
    monkeypatch.setattr(
        os,
        "killpg",
        lambda pid, sig: (_ for _ in ()).throw(PermissionError("denied")),
    )

    with pytest.raises(SupervisedProcessError, match="process_group_cleanup_incomplete"):
        terminate_process_group(fake, grace_seconds=0.01)  # type: ignore[arg-type]
