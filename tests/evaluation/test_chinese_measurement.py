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
