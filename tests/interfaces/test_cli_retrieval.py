import json
import sqlite3
from pathlib import Path

import pytest
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
            {"name": "active_fts_projection", "status": "ready"},
            {"name": "additional_cjk_projection", "status": "not_required"},
        ],
    }
    assert str(tmp_path) not in json.dumps(payload)


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--extractor-fingerprint", "pdf-ocr-eval-v1:" + ("a" * 64)),
        ("--run-manifest", "{}"),
    ],
)
def test_cli_ingest_has_no_manifest_authority_input(
    option: str,
    value: str,
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["ingest", "fixture.pdf", option, value])

    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert "unrecognized arguments" in error
    assert option in error


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
        "name": "additional_cjk_projection",
        "status": "not_required",
    }


def test_retrieval_doctor_rejects_missing_active_fts_projection(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _publish_text(db_path, "发布证据检索确认。")
    with sqlite3.connect(db_path) as connection:
        connection.execute("DROP TABLE active_evidence_fts")

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
    assert payload["status"] == "not_ready"
    assert payload["problem"] == "retrieval_projection_not_ready"
    assert payload["cause"] == "Active FTS5 projection is missing or inconsistent"
    assert payload["next_step"] == "republish_active_sources"
    assert {check["name"]: check["status"] for check in payload["checks"]} == {
        "sqlite_domain_truth": "ready",
        "active_publication": "ready",
        "active_fts_projection": "not_ready",
        "additional_cjk_projection": "not_required",
    }


def test_retrieval_doctor_rejects_inconsistent_active_fts_projection(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _publish_text(db_path, "发布证据检索确认。")
    with sqlite3.connect(db_path) as connection:
        connection.execute("DELETE FROM active_evidence_fts")

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
    assert payload["problem"] == "retrieval_projection_not_ready"
    assert payload["checks"][2] == {
        "name": "active_fts_projection",
        "status": "not_ready",
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
        "scope": "additional_cjk_projection",
        "problem": None,
        "cause": None,
        "next_step": None,
    }


@pytest.mark.parametrize("strategy", ["current", "numeric-grouping-v1"])
def test_retrieval_rebuild_rejects_base_projection_strategies(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    strategy: str,
) -> None:
    assert (
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "retrieval",
                "rebuild",
                "--strategy",
                strategy,
                "--json",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "not_supported",
        "strategy": strategy,
        "action": "none",
        "projection": "active_evidence_fts",
        "scope": "base_projection",
        "problem": "retrieval_rebuild_not_supported",
        "cause": "Base active FTS5 projection rebuild is not supported",
        "next_step": "republish_active_sources",
    }


@pytest.mark.parametrize("strategy", ["unsupported", "secret=ghp_not-a-strategy"])
@pytest.mark.parametrize("json_output", [False, True])
def test_retrieval_rebuild_rejects_unvalidated_strategy_before_output(
    capsys: CaptureFixture[str],
    strategy: str,
    json_output: bool,
) -> None:
    with pytest.raises(ValueError, match="retrieval strategy is unsupported"):
        vars(mke.cli)["_retrieval_rebuild"](strategy, json_output=json_output)

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("strategy", "expected_exit_code"),
    [
        ("current", 1),
        ("numeric-grouping-v1", 1),
        ("cjk-active-scan-overlap-v1", 0),
    ],
)
def test_retrieval_rebuild_human_output_uses_canonical_strategy_id(
    capsys: CaptureFixture[str],
    strategy: str,
    expected_exit_code: int,
) -> None:
    assert (
        vars(mke.cli)["_retrieval_rebuild"](strategy, json_output=False)
        == expected_exit_code
    )

    output = capsys.readouterr().out
    assert f"strategy={strategy}" in output
    assert output.count("strategy=") == 1


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
