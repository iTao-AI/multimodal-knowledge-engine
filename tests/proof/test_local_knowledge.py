from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from mke.proof.local_knowledge import run_local_knowledge_proof


def test_local_knowledge_proof_runs_real_stdio_mcp_flow() -> None:
    repo_root = Path.cwd()

    report = run_local_knowledge_proof(
        repo_root=repo_root,
        mke_executable=repo_root / ".venv/bin/mke",
    )

    assert report == {
        "proof": "local_knowledge",
        "status": "passed",
        "fixtures": 2,
        "runs": {"published": 2},
        "evidence": {"published": 2, "locator": "page"},
        "search": {"status": "evidence_found", "results": 1},
        "ask": {"status": "evidence_found", "citations": 1},
        "refusal": {"status": "insufficient_evidence", "citations": 0},
    }


def test_local_knowledge_proof_report_contains_only_public_aggregates() -> None:
    repo_root = Path.cwd()
    report = run_local_knowledge_proof(
        repo_root=repo_root,
        mke_executable=repo_root / ".venv/bin/mke",
    )

    rendered = json.dumps(report, sort_keys=True)
    assert str(Path.home()) not in rendered
    assert tempfile.gettempdir() not in rendered
    assert str(repo_root) not in rendered
    assert re.search(r"(?:run|src|pub|ask|ev)_[0-9a-f]{32}", rendered) is None
    assert "14:00 UTC" not in rendered
    assert "telemetry turns amber" not in rendered
    assert "Traceback" not in rendered
    assert "argv" not in rendered
    assert "stderr" not in rendered

