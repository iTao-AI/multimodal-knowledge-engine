import json

from pytest import CaptureFixture

from scripts import evidence_provenance_proof


def test_script_prints_public_report(capsys: CaptureFixture[str]) -> None:
    assert evidence_provenance_proof.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["proof"] == "evidence_provenance"
    assert report["status"] == "passed"
