import json
from dataclasses import replace
from pathlib import Path

import pytest
from pytest import CaptureFixture

from mke.cli import main

MANIFEST = Path("tests/fixtures/retrieval-eval-v1.json")
NUMERIC_PROTOCOL = Path(
    "tests/fixtures/retrieval-numeric-v1/protocol-lock.json"
)
CHINESE_PROTOCOL = Path("tests/fixtures/retrieval-chinese-v1/protocol.json")
DENSE_PROTOCOL = Path("tests/fixtures/retrieval-dense-v1/protocol-lock.json")


def test_cli_eval_retrieval_outputs_human_baseline(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["eval", "retrieval", "--manifest", str(MANIFEST)]) == 0

    output = capsys.readouterr()
    assert output.err == ""
    assert "mke eval retrieval" in output.out
    assert "scope=small_english_page_timestamp_corpus quality_gate=none" in output.out
    assert "status=passed quality_status=baseline_recorded" in output.out
    assert "documents=3 queries=24 answerable=16 unanswerable=8" in output.out
    assert "query_id=volcano-answerable-01 category=answerable" in output.out
    assert "/Users/" not in output.out
    assert "eruption clouds aviation" not in output.out


def test_cli_eval_retrieval_outputs_one_json_object(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["eval", "retrieval", "--manifest", str(MANIFEST), "--json"]) == 0

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["evaluation"] == "retrieval"
    assert payload["benchmark_scope"] == "small_english_page_timestamp_corpus"
    assert payload["quality_gate"] == "none"
    assert payload["status"] == "passed"
    assert payload["quality_status"] == "baseline_recorded"
    assert payload["queries"] == 24
    assert payload["integrity_failures"] == []


def test_cli_eval_integrity_failure_is_exit_one_and_redacted(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    missing = tmp_path / "private" / "missing.json"

    assert main(["eval", "retrieval", "--manifest", str(missing), "--json"]) == 1

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["status"] == "failed"
    assert payload["integrity_failures"][0]["problem"] == (
        "retrieval_eval_manifest_invalid"
    )
    assert payload["integrity_failures"][0]["cause"] == "manifest file is missing"
    assert str(tmp_path) not in output.out
    assert "Traceback" not in output.out


def test_cli_eval_requires_manifest_as_usage_error(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval"])

    assert error.value.code == 2
    assert "required" in capsys.readouterr().err


def test_cli_eval_retrieval_help_documents_required_manifest(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval", "--help"])

    assert error.value.code == 0
    output = capsys.readouterr()
    normalized = " ".join(output.out.split())
    assert "--manifest" in output.out
    assert "--json" in output.out
    assert "small English" in normalized
    assert "no retrieval-quality threshold" in normalized


def test_cli_eval_rejects_explicit_global_db(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--db",
                str(tmp_path / "ignored.sqlite"),
                "eval",
                "retrieval",
                "--manifest",
                str(MANIFEST),
            ]
        )

    assert error.value.code == 2
    assert "--db is not supported" in capsys.readouterr().err


def test_cli_eval_does_not_create_current_directory_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    manifest = MANIFEST.resolve()
    monkeypatch.chdir(tmp_path)

    assert main(["eval", "retrieval", "--manifest", str(manifest)]) == 0

    assert not (tmp_path / "mke.sqlite").exists()
    capsys.readouterr()


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_eval_renderer_failure_is_redacted_exit_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
    json_output: bool,
) -> None:
    def fail_renderer(*args: object, **kwargs: object) -> str:
        raise RuntimeError("Traceback SECRET /Users/mac/private")

    name = (
        "render_retrieval_json_report"
        if json_output
        else "render_retrieval_human_report"
    )
    monkeypatch.setattr(f"mke.cli.{name}", fail_renderer)
    argv = ["eval", "retrieval", "--manifest", str(MANIFEST)]
    if json_output:
        argv.append("--json")

    assert main(argv) == 1

    output = capsys.readouterr()
    assert output.err == ""
    assert "retrieval evaluation report could not be rendered" in output.out
    assert "Traceback" not in output.out
    assert "SECRET" not in output.out
    assert "/Users/" not in output.out
    if json_output:
        payload = json.loads(output.out)
        assert payload["status"] == "failed"


def test_cli_eval_distinguishes_invalid_json_from_missing_manifest(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{")

    assert main(["eval", "retrieval", "--manifest", str(invalid), "--json"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["integrity_failures"][0]["cause"] == "manifest is not valid JSON"


def test_cli_eval_numeric_outputs_passing_json(
    capsys: CaptureFixture[str],
) -> None:
    assert main(
        [
            "eval",
            "retrieval-numeric",
            "--protocol",
            str(NUMERIC_PROTOCOL),
            "--json",
        ]
    ) == 0

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["schema_version"] == "mke.retrieval_numeric_comparison.v1"
    assert payload["integrity_status"] == "passed"
    assert payload["candidate_status"] == "passed"
    assert len(payload["gates"]) == 14
    assert "/Users/" not in output.out
    assert "Traceback" not in output.out


def test_cli_eval_numeric_outputs_human_status_first(
    capsys: CaptureFixture[str],
) -> None:
    assert main(
        [
            "eval",
            "retrieval-numeric",
            "--protocol",
            str(NUMERIC_PROTOCOL),
        ]
    ) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "mke eval retrieval-numeric"
    assert "protocol=retrieval-numeric-v1" in lines[1]
    assert "candidate=numeric-grouping-v1 revision=1" in lines[1]
    assert lines[2] == "integrity_status=passed candidate_status=passed"


def test_cli_eval_numeric_missing_protocol_path_is_exit_one_and_redacted(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    missing = tmp_path / "private" / "protocol.json"

    assert main(
        [
            "eval",
            "retrieval-numeric",
            "--protocol",
            str(missing),
            "--json",
        ]
    ) == 1

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["integrity_status"] == "failed"
    assert payload["candidate_status"] == "not_recorded"
    assert str(tmp_path) not in output.out


def test_cli_eval_numeric_requires_protocol_as_usage_error(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval-numeric"])

    assert error.value.code == 2
    assert "--protocol" in capsys.readouterr().err


def test_cli_eval_numeric_rejects_db_and_candidate_override(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--db",
                str(tmp_path / "ignored.sqlite"),
                "eval",
                "retrieval-numeric",
                "--protocol",
                str(NUMERIC_PROTOCOL),
            ]
        )
    assert error.value.code == 2
    assert "--db is not supported" in capsys.readouterr().err

    with pytest.raises(SystemExit) as error:
        main(
            [
                "eval",
                "retrieval-numeric",
                "--protocol",
                str(NUMERIC_PROTOCOL),
                "--candidate",
                "current",
            ]
        )
    assert error.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_cli_eval_numeric_help_documents_comparison_boundary(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval-numeric", "--help"])

    assert error.value.code == 0
    normalized = " ".join(capsys.readouterr().out.split())
    assert "--protocol" in normalized
    assert "--json" in normalized
    assert "historical comparison-only" in normalized
    assert "public rather than blind" in normalized
    assert "policy is protocol-owned" in normalized
    assert "does not select the runtime strategy" in normalized
    assert "runtime default" not in normalized


def test_cli_eval_cjk_help_documents_historical_comparison_boundary(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval-cjk-lexical", "--help"])

    assert error.value.code == 0
    normalized = " ".join(capsys.readouterr().out.split())
    assert "historical E3-B comparison-only" in normalized
    assert "candidate and policy are protocol-owned" in normalized
    assert "does not select the runtime strategy" in normalized
    assert "runtime default" not in normalized


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_eval_numeric_renderer_failure_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
    json_output: bool,
) -> None:
    def fail_renderer(*args: object, **kwargs: object) -> str:
        raise RuntimeError("Traceback SECRET /Users/mac/private")

    name = (
        "render_numeric_comparison_json"
        if json_output
        else "render_numeric_comparison_human"
    )
    monkeypatch.setattr(f"mke.cli.{name}", fail_renderer)
    argv = [
        "eval",
        "retrieval-numeric",
        "--protocol",
        str(NUMERIC_PROTOCOL),
    ]
    if json_output:
        argv.append("--json")

    assert main(argv) == 1

    output = capsys.readouterr()
    assert output.err == ""
    assert "numeric comparison report could not be rendered" in output.out
    assert "Traceback" not in output.out
    assert "SECRET" not in output.out
    assert "/Users/" not in output.out


def test_cli_eval_chinese_outputs_human_report_and_progress(
    capsys: CaptureFixture[str],
) -> None:
    assert main(
        ["eval", "retrieval-chinese", "--protocol", str(CHINESE_PROTOCOL)]
    ) == 0

    output = capsys.readouterr()
    lines = output.out.splitlines()
    assert lines[0] == "mke eval retrieval-chinese"
    assert "quality_status=baseline_recorded quality_gate=none" in lines[1]
    assert any(line.startswith("category=") for line in lines)
    assert any(line.startswith("compiled_query_empty=") for line in lines)
    assert any(line.startswith("ascii_token_count=") for line in lines)
    assert output.err.splitlines() == [
        "protocol_validated",
        "development_ingested",
        "holdout_ingested",
        "determinism_verified",
    ]


def test_cli_eval_chinese_outputs_one_json_object_without_progress(
    capsys: CaptureFixture[str],
) -> None:
    assert main(
        [
            "eval",
            "retrieval-chinese",
            "--protocol",
            str(CHINESE_PROTOCOL),
            "--json",
        ]
    ) == 0

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["schema_version"] == "mke.retrieval_chinese_report.v1"
    assert payload["integrity_status"] == "passed"
    assert payload["quality_status"] == "baseline_recorded"
    assert payload["documents"] == 5
    assert payload["queries"] == 48
    assert payload["split_counts"] == {"development": 24, "holdout": 24}
    assert payload["fts5_rank_profile"] == "sqlite_fts5_default_bm25"


def test_cli_eval_chinese_help_documents_baseline_boundary(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval-chinese", "--help"])

    assert error.value.code == 0
    normalized = " ".join(capsys.readouterr().out.split()).lower()
    assert "--protocol" in normalized
    assert "--json" in normalized
    assert "fts5 lexical baseline" in normalized
    assert "public chinese" in normalized
    assert "no retrieval-quality threshold" in normalized
    assert "no dense, hybrid, or reranker claim" in normalized


@pytest.mark.parametrize("option", ["--db", "--retrieval-query-policy"])
def test_cli_eval_chinese_rejects_global_runtime_overrides(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    option: str,
) -> None:
    value = str(tmp_path / "ignored.sqlite") if option == "--db" else "current"
    with pytest.raises(SystemExit) as error:
        main(
            [
                option,
                value,
                "eval",
                "retrieval-chinese",
                "--protocol",
                str(CHINESE_PROTOCOL),
            ]
        )

    assert error.value.code == 2
    assert "not supported" in capsys.readouterr().err


def test_cli_eval_chinese_missing_protocol_is_safe_exit_one(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    missing = tmp_path / "private" / "protocol.json"

    assert main(
        [
            "eval",
            "retrieval-chinese",
            "--protocol",
            str(missing),
            "--json",
        ]
    ) == 1

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["integrity_status"] == "failed"
    assert payload["quality_status"] == "not_recorded"
    assert payload["integrity_failures"] == [
        {
            "problem": "retrieval_chinese_protocol_invalid",
            "cause": "Chinese retrieval protocol is invalid",
            "next_step": "restore_checked_in_protocol",
        }
    ]
    assert str(tmp_path) not in output.out
    assert "Traceback" not in output.out


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_eval_chinese_renderer_failure_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
    json_output: bool,
) -> None:
    def fail_renderer(*args: object, **kwargs: object) -> str:
        raise RuntimeError("Traceback SECRET /Users/mac/private")

    name = (
        "render_chinese_retrieval_json"
        if json_output
        else "render_chinese_retrieval_human"
    )
    monkeypatch.setattr(f"mke.cli.{name}", fail_renderer)
    argv = ["eval", "retrieval-chinese", "--protocol", str(CHINESE_PROTOCOL)]
    if json_output:
        argv.append("--json")

    assert main(argv) == 1

    output = capsys.readouterr()
    assert "retrieval Chinese report could not be rendered" in output.out
    assert "Traceback" not in output.out
    assert "SECRET" not in output.out
    assert "/Users/" not in output.out
    if json_output:
        payload = json.loads(output.out)
        assert payload["schema_version"] == "mke.retrieval_chinese_report.v1"
        assert payload["integrity_status"] == "failed"
        assert output.err == ""


def test_cli_eval_chinese_low_quality_still_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    from mke.evaluation.chinese_report import ChineseRetrievalReport
    from mke.evaluation.chinese_runner import run_chinese_retrieval_evaluation

    report = run_chinese_retrieval_evaluation(CHINESE_PROTOCOL)
    low_quality = replace(
        report,
        e3b_decision="not_justified",
        e3b_reason="no_development_compiled_query_empty_miss",
    )

    def return_low_quality(
        *args: object, **kwargs: object
    ) -> ChineseRetrievalReport:
        del args, kwargs
        return low_quality

    monkeypatch.setattr(
        "mke.cli.run_chinese_retrieval_evaluation",
        return_low_quality,
    )

    assert main(
        [
            "eval",
            "retrieval-chinese",
            "--protocol",
            str(CHINESE_PROTOCOL),
            "--json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["e3b_decision"] == "not_justified"


def test_cli_eval_cjk_lexical_outputs_passing_json(
    capsys: CaptureFixture[str],
) -> None:
    assert main(
        [
            "eval",
            "retrieval-cjk-lexical",
            "--protocol",
            str(CHINESE_PROTOCOL),
            "--candidate",
            "cjk-trigram-overlap-v1",
            "--json",
        ]
    ) == 0

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["schema_version"] == "mke.cjk_lexical_comparison.v1"
    assert payload["integrity_status"] == "passed"
    assert payload["candidate_status"] == "passed"
    assert payload["candidate_id"] == "cjk-trigram-overlap-v1"
    assert payload["projection"]["tokenizer"] == "trigram"
    assert payload["projection"]["row_count"] == 70
    assert "/Users/" not in output.out
    assert "Traceback" not in output.out


def test_cli_eval_cjk_lexical_outputs_human_status_first(
    capsys: CaptureFixture[str],
) -> None:
    assert main(
        [
            "eval",
            "retrieval-cjk-lexical",
            "--protocol",
            str(CHINESE_PROTOCOL),
            "--candidate",
            "cjk-trigram-overlap-v1",
        ]
    ) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "mke eval retrieval-cjk-lexical"
    assert "protocol=retrieval-chinese-v1" in lines[1]
    assert "candidate=cjk-trigram-overlap-v1 revision=1" in lines[1]
    assert lines[2] == "integrity_status=passed candidate_status=passed"
    assert any(line.startswith("development_gate=") for line in lines)
    assert any(line.startswith("holdout_gate=") for line in lines)


def test_cli_eval_cjk_lexical_record_writes_valid_artifact(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    artifact = tmp_path / "cjk-artifact.json"

    assert main(
        [
            "eval",
            "retrieval-cjk-lexical",
            "--protocol",
            str(CHINESE_PROTOCOL),
            "--candidate",
            "cjk-trigram-overlap-v1",
            "--record",
            str(artifact),
            "--json",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    recorded = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["candidate_status"] == "passed"
    assert recorded["schema_version"] == "mke.cjk_lexical_comparison_artifact.v1"
    assert recorded["comparison"]["candidate_status"] == "passed"


def test_cli_eval_cjk_lexical_rejects_unsupported_candidate(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "eval",
                "retrieval-cjk-lexical",
                "--protocol",
                str(CHINESE_PROTOCOL),
                "--candidate",
                "raw-trigram",
            ]
        )

    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("option", ["--db", "--retrieval-query-policy"])
def test_cli_eval_cjk_lexical_rejects_global_runtime_overrides(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    option: str,
) -> None:
    value = str(tmp_path / "ignored.sqlite") if option == "--db" else "current"
    with pytest.raises(SystemExit) as error:
        main(
            [
                option,
                value,
                "eval",
                "retrieval-cjk-lexical",
                "--protocol",
                str(CHINESE_PROTOCOL),
                "--candidate",
                "cjk-trigram-overlap-v1",
            ]
        )

    assert error.value.code == 2
    assert "not supported" in capsys.readouterr().err


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_eval_cjk_lexical_renderer_failure_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
    json_output: bool,
) -> None:
    def fail_renderer(*args: object, **kwargs: object) -> str:
        raise RuntimeError("Traceback SECRET /Users/mac/private")

    name = (
        "render_cjk_lexical_comparison_json"
        if json_output
        else "render_cjk_lexical_comparison_human"
    )
    monkeypatch.setattr(f"mke.cli.{name}", fail_renderer)
    argv = [
        "eval",
        "retrieval-cjk-lexical",
        "--protocol",
        str(CHINESE_PROTOCOL),
        "--candidate",
        "cjk-trigram-overlap-v1",
    ]
    if json_output:
        argv.append("--json")

    assert main(argv) == 1

    output = capsys.readouterr()
    assert "CJK lexical comparison report could not be rendered" in output.out
    assert "Traceback" not in output.out
    assert "SECRET" not in output.out
    assert "/Users/" not in output.out
    if json_output:
        payload = json.loads(output.out)
        assert payload["schema_version"] == "mke.cjk_lexical_comparison.v1"
        assert payload["integrity_status"] == "failed"
        assert output.err == ""


def test_cli_eval_dense_development_invokes_cache_only_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def run_phase(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "phase": "development",
            "development_status": "passed",
            "selected_threshold": 0.42,
            "candidate_status": "not_evaluated",
            "e3d_status": "not_evaluated",
            "runtime_promotion_status": "not_evaluated",
        }

    monkeypatch.setattr("mke.cli.run_dense_evaluation_phase", run_phase)
    freeze = tmp_path / "development-freeze.json"

    assert main(
        [
            "eval",
            "retrieval-dense",
            "--protocol",
            str(DENSE_PROTOCOL),
            "--candidate",
            "qwen3-embedding-0.6b-exact-v1",
            "--model-cache",
            str(tmp_path / "model-cache"),
            "--development-only",
            "--record-development-freeze",
            str(freeze),
            "--json",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["selected_threshold"] == 0.42
    assert captured["phase"] == "development"
    assert captured["record_development_freeze"] == freeze


def test_cli_eval_dense_holdout_valid_negative_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def run_negative(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "phase": "holdout",
            "holdout_status": "observed",
            "candidate_status": "completed",
            "e3d_status": "not_eligible",
            "runtime_promotion_status": "not_evaluated",
        }

    monkeypatch.setattr(
        "mke.cli.run_dense_evaluation_phase",
        run_negative,
    )

    assert main(
        [
            "eval",
            "retrieval-dense",
            "--protocol",
            str(DENSE_PROTOCOL),
            "--candidate",
            "qwen3-embedding-0.6b-exact-v1",
            "--model-cache",
            str(tmp_path / "model-cache"),
            "--development-freeze",
            str(tmp_path / "freeze.json"),
            "--record",
            str(tmp_path / "artifact.json"),
            "--record-holdout-receipt",
            str(tmp_path / "receipt.json"),
            "--json",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["candidate_status"] == "completed"
    assert payload["e3d_status"] == "not_eligible"


def test_cli_eval_dense_known_workflow_failure_returns_stable_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    from mke.evaluation.dense_workflow import DenseWorkflowError

    def fail_phase(**kwargs: object) -> dict[str, object]:
        del kwargs
        raise DenseWorkflowError("development threshold inputs are invalid")

    monkeypatch.setattr("mke.cli.run_dense_evaluation_phase", fail_phase)

    assert main(
        [
            "eval",
            "retrieval-dense",
            "--protocol",
            str(DENSE_PROTOCOL),
            "--candidate",
            "qwen3-embedding-0.6b-exact-v1",
            "--model-cache",
            str(tmp_path / "model-cache"),
            "--development-only",
            "--record-development-freeze",
            str(tmp_path / "freeze.json"),
            "--json",
        ]
    ) == 1

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["failure"]["cause"] == "development threshold inputs are invalid"
    assert "Traceback" not in output.out
    assert "/Users/" not in output.out


@pytest.mark.parametrize(
    "argv",
    (
        ["--development-only"],
        ["--record-development-freeze", "freeze.json"],
        ["--development-freeze", "freeze.json", "--record", "artifact.json"],
        ["--allow-model-download"],
    ),
)
def test_cli_eval_dense_rejects_incomplete_or_download_phase_flags(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    argv: list[str],
) -> None:
    base = [
        "eval",
        "retrieval-dense",
        "--protocol",
        str(DENSE_PROTOCOL),
        "--candidate",
        "qwen3-embedding-0.6b-exact-v1",
        "--model-cache",
        str(tmp_path / "model-cache"),
    ]
    with pytest.raises(SystemExit) as error:
        main([*base, *argv])

    assert error.value.code == 2
    assert "Traceback" not in capsys.readouterr().err


def test_cli_eval_dense_help_is_comparison_only(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval-dense", "--help"])

    assert error.value.code == 0
    normalized = " ".join(capsys.readouterr().out.split())
    assert "comparison-only" in normalized
    assert "--development-only" in normalized
    assert "--record-holdout-receipt" in normalized
    assert "does not change Search, Ask, MCP, or runtime defaults" in normalized
