import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.cjk_lexical_artifact import (
    CjkLexicalArtifactValidationError,
    record_cjk_lexical_artifact,
    validate_cjk_lexical_artifact,
)
from mke.evaluation.cjk_lexical_artifact import (
    main as cjk_lexical_artifact_main,
)
from mke.evaluation.cjk_lexical_comparison import (
    render_cjk_lexical_comparison_json,
    run_cjk_lexical_comparison,
)

PROTOCOL = Path("tests/fixtures/retrieval-chinese-v1/protocol.json")
REPOSITORY = Path(".")


def _record(tmp_path: Path) -> tuple[Path, Path]:
    observed = tmp_path / "observed.json"
    observed.write_text(
        render_cjk_lexical_comparison_json(
            run_cjk_lexical_comparison(PROTOCOL)
        ),
        encoding="utf-8",
    )
    artifact = tmp_path / "artifact.json"
    record_cjk_lexical_artifact(
        observed_path=observed,
        artifact_path=artifact,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )
    return artifact, observed


def test_recorded_cjk_lexical_artifact_validates_by_recomputing_candidate(
    tmp_path: Path,
) -> None:
    artifact, observed = _record(tmp_path)

    validate_cjk_lexical_artifact(
        artifact_path=artifact,
        observed_path=observed,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "mke.cjk_lexical_comparison_artifact.v1"
    assert payload["candidate"] == {
        "id": "cjk-trigram-overlap-v1",
        "revision": 1,
        "minimum_overlap_count": 2,
        "minimum_overlap_ratio": 0.3,
        "max_results": 10,
    }
    assert payload["comparison"]["candidate_status"] == "passed"
    assert "duration_ms" not in payload["comparison"]
    assert "commit" not in payload["source"]


def _add_unknown_key(payload: dict[str, object]) -> None:
    payload["unexpected"] = True


def _make_revision_bool(payload: dict[str, object]) -> None:
    candidate = cast(dict[str, object], payload["candidate"])
    candidate["revision"] = True


def _reverse_observations(payload: dict[str, object]) -> None:
    comparison = cast(dict[str, object], payload["comparison"])
    observations = cast(list[object], comparison["query_observations"])
    comparison["query_observations"] = list(reversed(observations))


def _tamper_source_identity(payload: dict[str, object]) -> None:
    source = cast(dict[str, object], payload["source"])
    files = cast(list[dict[str, object]], source["files"])
    files[0]["sha256"] = "0" * 64


def _tamper_locator_and_score(payload: dict[str, object]) -> None:
    comparison = cast(dict[str, object], payload["comparison"])
    observations = cast(list[dict[str, object]], comparison["query_observations"])
    target = next(
        item
        for item in observations
        if cast(list[object], item["candidate_result_proofs"])
    )
    proof = cast(list[dict[str, object]], target["candidate_result_proofs"])[0]
    locator = cast(dict[str, object], proof["locator"])
    locator["locator_start"] = cast(int, locator["locator_start"]) + 1
    proof["overlap_count"] = cast(int, proof["overlap_count"]) + 1


@pytest.mark.parametrize(
    "mutation",
    [
        _add_unknown_key,
        _make_revision_bool,
        _reverse_observations,
        _tamper_source_identity,
        _tamper_locator_and_score,
    ],
)
def test_cjk_lexical_artifact_rejects_schema_identity_or_score_tampering(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    artifact, observed = _record(tmp_path)
    payload = cast(
        dict[str, object],
        json.loads(artifact.read_text(encoding="utf-8")),
    )
    mutation(payload)
    artifact.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(CjkLexicalArtifactValidationError):
        validate_cjk_lexical_artifact(
            artifact_path=artifact,
            observed_path=observed,
            protocol_path=PROTOCOL,
            repository_root=REPOSITORY,
        )


def test_validation_rejects_observed_report_replay_without_recompute(
    tmp_path: Path,
) -> None:
    artifact, observed = _record(tmp_path)
    payload = json.loads(observed.read_text(encoding="utf-8"))
    payload["candidate_status"] = "failed"
    observed.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(CjkLexicalArtifactValidationError):
        validate_cjk_lexical_artifact(
            artifact_path=artifact,
            observed_path=observed,
            protocol_path=PROTOCOL,
            repository_root=REPOSITORY,
        )


def test_cjk_lexical_artifact_cli_error_is_stable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact, observed = _record(tmp_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["candidate"]["revision"] = True
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = cjk_lexical_artifact_main(
        [
            "validate",
            "--artifact",
            str(artifact),
            "--observed",
            str(observed),
            "--protocol",
            str(PROTOCOL),
            "--repository",
            str(REPOSITORY),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "CJK lexical comparison artifact is invalid" in captured.err
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err
