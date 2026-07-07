from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pytest import CaptureFixture

from scripts import local_knowledge_proof as proof_script

_PASSED_REPORT: dict[str, object] = {
    "proof": "local_knowledge",
    "status": "passed",
    "fixtures": 2,
    "runs": {"published": 2},
    "evidence": {"published": 2, "locator": "page"},
    "search": {"status": "evidence_found", "results": 1},
    "ask": {"status": "evidence_found", "citations": 1},
    "refusal": {"status": "insufficient_evidence", "citations": 0},
}


def test_local_knowledge_proof_script_runs_from_virtual_environment() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/local_knowledge_proof.py"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == _PASSED_REPORT


def test_local_knowledge_proof_script_prints_one_compact_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def succeed(**_: object) -> dict[str, object]:
        return _PASSED_REPORT

    monkeypatch.setattr(proof_script, "run_local_knowledge_proof", succeed)

    assert proof_script.main() == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == _PASSED_REPORT
    assert captured.out == json.dumps(_PASSED_REPORT, sort_keys=True) + "\n"


def test_local_knowledge_proof_script_redacts_all_failure_details(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def fail(**_: object) -> dict[str, object]:
        raise RuntimeError(
            "Traceback /private/tmp/mke.sqlite run_0123456789abcdef0123456789abcdef "
            "ev_0123456789abcdef0123456789abcdef telemetry turns amber"
        )

    monkeypatch.setattr(proof_script, "run_local_knowledge_proof", fail)

    assert proof_script.main() == 1

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == (
        '{"proof": "local_knowledge", "reason": "local_knowledge_proof_failed", '
        '"status": "failed"}\n'
    )
    assert "Traceback" not in captured.out
    assert "/private/" not in captured.out
    assert "run_" not in captured.out
    assert "ev_" not in captured.out
    assert "telemetry turns amber" not in captured.out


def test_local_knowledge_proof_is_documented_without_sensitive_details() -> None:
    entry_points = [Path("README.md"), Path("README_CN.md"), Path("docs/README.md")]
    how_to = Path("docs/how-to/run-local-knowledge-proof.md")

    assert how_to.is_file()
    for path in entry_points:
        assert "run-local-knowledge-proof.md" in path.read_text(encoding="utf-8")

    guide = how_to.read_text(encoding="utf-8")
    required_terms = (
        "UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py",
        "real stdio MCP",
        "offline",
        "no model",
        "active Publication Search",
        "evidence-only Ask",
        "insufficient_evidence",
    )
    assert all(term in guide for term in required_terms)
    combined = "\n".join(path.read_text(encoding="utf-8") for path in [*entry_points, how_to])
    forbidden = (
        "/Users/",
        "/private/var/",
        "/tmp/",
        "Traceback",
        "14:00 UTC",
        "telemetry turns amber",
    )
    assert all(term not in combined for term in forbidden)
