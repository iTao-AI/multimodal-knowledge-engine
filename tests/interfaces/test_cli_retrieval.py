import json
from pathlib import Path

from pytest import CaptureFixture, MonkeyPatch

import mke.cli
from mke.application import KnowledgeEngine
from mke.cli import main
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    RunManifest,
)
from mke.retrieval.cjk_active_scan import CjkActiveScanError
from mke.runtime import RuntimeConfig


def test_retrieval_doctor_reports_not_ready_without_active_publication(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(db_path)
    engine.close()

    assert (
        main(
            [
                "--db",
                str(db_path),
                "retrieval",
                "doctor",
                "--strategy",
                "cjk-active-scan-overlap-v1",
                "--json",
            ]
        )
        == 1
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "not_ready",
        "strategy": "cjk-active-scan-overlap-v1",
        "problem": "no_active_publication",
        "cause": "No active Publication is available to scan",
        "next_step": "ingest_and_publish_source",
        "checks": [
            {"name": "sqlite_domain_truth", "status": "ready"},
            {"name": "active_publication", "status": "not_ready"},
            {"name": "persistent_cjk_projection", "status": "not_required"},
        ],
    }
    assert str(tmp_path) not in json.dumps(payload)


def test_retrieval_doctor_does_not_create_missing_database(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "missing.sqlite"

    assert (
        main(
            [
                "--db",
                str(db_path),
                "retrieval",
                "doctor",
                "--strategy",
                "cjk-active-scan-overlap-v1",
                "--json",
            ]
        )
        == 1
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["problem"] == "sqlite_unreadable"
    assert payload["cause"] == "SQLite domain truth could not be inspected"
    assert payload["next_step"] == "check_database_file"
    assert not db_path.exists()


def test_retrieval_doctor_reports_ready_for_active_scan_without_projection(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _publish_text(db_path, "发布证据检索确认。")

    assert (
        main(
            [
                "--db",
                str(db_path),
                "retrieval",
                "doctor",
                "--strategy",
                "cjk-active-scan-overlap-v1",
                "--json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ready"
    assert payload["strategy"] == "cjk-active-scan-overlap-v1"
    assert payload["problem"] is None
    assert payload["cause"] is None
    assert payload["next_step"] is None
    assert payload["checks"][-1] == {
        "name": "persistent_cjk_projection",
        "status": "not_required",
    }


def test_retrieval_rebuild_active_scan_is_no_projection_noop(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert (
        main(
            [
                "--db",
                str(db_path),
                "retrieval",
                "rebuild",
                "--strategy",
                "cjk-active-scan-overlap-v1",
                "--json",
            ]
        )
        == 0
    )

    assert json.loads(capsys.readouterr().out) == {
        "status": "succeeded",
        "strategy": "cjk-active-scan-overlap-v1",
        "action": "noop",
        "projection": "none",
        "problem": None,
        "cause": None,
        "next_step": None,
    }


def test_cli_search_renders_stable_active_scan_budget_error(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    class BudgetEngine:
        def search(self, query: str, limit: int | None = None) -> object:
            raise CjkActiveScanError(
                "cjk_scan_budget_exceeded",
                "CJK active Evidence scan would exceed configured local budget",
                "narrow_query_or_use_projection_strategy",
            )

        def close(self) -> None:
            return None

    def build_budget_engine(_config: RuntimeConfig) -> BudgetEngine:
        return BudgetEngine()

    monkeypatch.setattr(mke.cli, "build_engine", build_budget_engine)

    assert (
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "--retrieval-strategy",
                "cjk-active-scan-overlap-v1",
                "search",
                "发布证据检索",
            ]
        )
        == 1
    )

    output = capsys.readouterr().out
    assert "problem=cjk_scan_budget_exceeded" in output
    assert "cause=CJK active Evidence scan would exceed configured local budget" in output
    assert "next_step=narrow_query_or_use_projection_strategy" in output
    assert str(tmp_path) not in output


def _publish_text(db_path: Path, text: str) -> None:
    engine = KnowledgeEngine(db_path)
    try:
        source = engine.ensure_source("fixture", "f" * 64, media_type="text/plain")
        run = engine.create_run(source.source_id)
        engine.persist_validated_candidate(
            run.run_id,
            [
                CandidateEvidence(
                    evidence_id="evidence_1",
                    locator_kind="page",
                    locator_start=1,
                    locator_end=1,
                    text=text,
                )
            ],
            RunManifest(
                run_id=run.run_id,
                evidence_count=1,
                required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
                extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
                asset_sha256="f" * 64,
            ),
        )
        engine.activate_publication(run.run_id)
    finally:
        engine.close()
