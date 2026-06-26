import subprocess
from pathlib import Path

import pytest


def test_measurement_budgets_use_locked_thresholds() -> None:
    from scripts.chinese_retrieval_measurement import evaluate_budgets

    budgets = evaluate_budgets(
        warm_cache_sync_ms=1_000,
        evaluator_ms=2_000,
        installed_wheel_proof_ms=3_000,
        peak_rss_bytes=128 * 1024 * 1024,
        max_sqlite_bytes=2 * 1024 * 1024,
    )

    assert budgets == {
        "checkout_to_first_report": True,
        "source_tree_evaluation": True,
        "installed_wheel_proof": True,
        "peak_rss": True,
        "temporary_sqlite": True,
    }


def test_checkout_to_first_report_is_exact_sum() -> None:
    from scripts.chinese_retrieval_measurement import build_summary

    summary = build_summary(
        python_version="3.13",
        warm_cache_sync_ms=120,
        evaluator_ms=345,
        installed_wheel_proof_ms=678,
        peak_rss_bytes=100,
        max_sqlite_bytes=200,
    )

    assert summary["checkout_to_first_report_ms"] == 465
    assert summary["telemetry"] is False
    assert summary["network"] is False


def test_measurement_command_failure_and_output_limit_are_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import chinese_retrieval_measurement as measurement

    def oversized(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout="x" * 100_000, stderr=""
        )

    monkeypatch.setattr(measurement.subprocess, "run", oversized)
    with pytest.raises(RuntimeError, match="output limit"):
        measurement.run_timed_command(
            ("true",),
            cwd=tmp_path,
            environment={"UV_OFFLINE": "1"},
        )


def test_measurement_rejects_budget_overrun() -> None:
    from scripts.chinese_retrieval_measurement import evaluate_budgets

    budgets = evaluate_budgets(
        warm_cache_sync_ms=200_000,
        evaluator_ms=181_000,
        installed_wheel_proof_ms=181_000,
        peak_rss_bytes=2 * 1024 * 1024 * 1024,
        max_sqlite_bytes=65 * 1024 * 1024,
    )

    assert not any(budgets.values())


def test_sqlite_sampler_records_peak_before_cleanup(tmp_path: Path) -> None:
    import threading

    from scripts import chinese_retrieval_measurement as measurement

    stop = threading.Event()
    sample = {"max_sqlite_bytes": 0}
    database = tmp_path / "mke.sqlite"
    database.write_bytes(b"x" * 4096)
    stop.set()

    measurement._sample_sqlite_sizes(  # pyright: ignore[reportPrivateUsage]
        tmp_path,
        stop,
        sample,
    )

    database.unlink()
    assert sample["max_sqlite_bytes"] == 4096


def test_measurement_forwards_preinstalled_wheel_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import chinese_retrieval_measurement as measurement

    repository = tmp_path / "repo"
    repository.mkdir()
    protocol = tmp_path / "protocol.json"
    protocol.write_text("{}")
    wheel = tmp_path / "mke.whl"
    wheel.write_bytes(b"wheel")
    installed_environment = tmp_path / "wheel-env"
    installed_environment.mkdir()
    commands: list[tuple[str, ...]] = []

    def fake_timed_command(
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: dict[str, str],
        timeout: float = 180.0,
        resource_sample: dict[str, int] | None = None,
    ) -> tuple[int, subprocess.CompletedProcess[str]]:
        del cwd, timeout
        commands.append(command)
        assert environment["UV_OFFLINE"] == "1"
        assert "PYTHONPATH" not in environment
        assert "PYTHONHOME" not in environment
        assert "VIRTUAL_ENV" not in environment
        if command[:2] == ("uv", "sync"):
            return 10, subprocess.CompletedProcess(command, 0, "", "")
        if command[:3] == ("uv", "run", "mke"):
            return 20, subprocess.CompletedProcess(
                command,
                0,
                "mke eval retrieval-chinese\n",
                "",
            )
        if any(part.endswith("chinese_retrieval_deployment_proof.py") for part in command):
            assert "--installed-environment" in command
            assert str(installed_environment) in command
            return 30, subprocess.CompletedProcess(
                command,
                0,
                '{"status":"passed"}',
                "",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(measurement, "run_timed_command", fake_timed_command)
    monkeypatch.setattr(measurement, "_peak_child_rss_bytes", lambda: 1024)

    summary = measurement.run_measurement(
        repository=repository,
        protocol=protocol,
        wheel=wheel,
        python_version="3.13",
        installed_environment=installed_environment,
    )

    assert summary["installed_wheel_proof_ms"] == 30
    assert commands[-1][-2:] == (
        "--installed-environment",
        str(installed_environment),
    )
