import json
import re
from pathlib import Path

from mke.proof.evidence_provenance import run_evidence_provenance_proof


def test_evidence_provenance_proof_runs_real_stdio() -> None:
    root = Path.cwd()
    report = run_evidence_provenance_proof(root, root / ".venv/bin/mke")
    assert report["status"] == "passed"
    assert report["states"] == ["empty", "no_active_publication", "active"]
    assert report["locators"] == ["page", "timestamp_ms"]
    assert report["malformed_payloads_rejected"] is True
    assert report["unexpected_exception_redacted"] is True
    assert report["transport_failure_bounded"] is True
    assert report["timeout_bounded"] is True
    assert report["temporary_store_cleanup"] is True
    rendered = json.dumps(report, sort_keys=True)
    assert re.search(r"(?:run|src|pub|ask|ev)_[0-9a-f]{32}", rendered) is None
    assert str(root) not in rendered
    assert "Traceback" not in rendered and "stderr" not in rendered
