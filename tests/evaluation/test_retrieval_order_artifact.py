from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import NoReturn, cast

import pytest

import mke.evaluation.retrieval_order_artifact as artifact_module
import mke.evaluation.retrieval_order_workflow as workflow
from mke.evaluation.retrieval_order_artifact import (
    RetrievalOrderArtifactError,
    main,
    validate_retrieval_order_artifact,
)
from mke.evaluation.retrieval_order_protocol import (
    load_retrieval_order_protocol,
)
from tests.evaluation.test_retrieval_order_workflow import (
    synthetic_fixture_payload,
    synthetic_partition_metadata,
)

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PROTOCOL = (
    ROOT / "tests/fixtures/retrieval-order-v1/protocol.json"
)
CANONICAL_HOLDOUT_FIXTURE = (
    ROOT / "tests/fixtures/retrieval-order-v1/holdout/cases.json"
)


@pytest.fixture(autouse=True)
def forbid_canonical_holdout_fixture_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_bytes

    def guarded(path: Path) -> bytes:
        if path.resolve() == CANONICAL_HOLDOUT_FIXTURE.resolve():
            raise AssertionError("canonical holdout fixture must stay unopened")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)


@pytest.fixture
def recorded_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, Path]:
    root, protocol = _synthetic_repository(tmp_path)
    output = root / "benchmarks/retrieval"
    freeze = output / "development-freeze.json"
    receipt = output / "holdout-receipt.json"
    artifact = output / "artifact.json"
    monkeypatch.chdir(root)
    workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol,
        freeze_path=freeze,
        repository_root=root,
    )
    workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol,
        development_freeze_path=freeze,
        receipt_path=receipt,
        artifact_path=artifact,
        repository_root=root,
    )
    return root, protocol, artifact


def test_artifact_validate_is_pure_and_byte_preserving(
    recorded_artifact: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, protocol, artifact = recorded_artifact
    original = artifact.read_bytes()

    def observer(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("post-holdout validation must not observe")

    monkeypatch.setattr(
        workflow,
        "observe_retrieval_order_partition",
        observer,
    )

    assert main(
        [
            "validate",
            "--artifact",
            str(artifact),
            "--protocol",
            str(protocol),
            "--repository",
            str(root),
            "--json",
        ]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    assert artifact.read_bytes() == original


@pytest.mark.parametrize(
    "tamper",
    (
        "candidate_head",
        "receipt_digest",
        "holdout_delta",
        "runtime_profile",
        "case_projection",
    ),
)
def test_artifact_validate_rejects_cross_binding_tamper_without_observation(
    recorded_artifact: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    root, protocol, artifact_path = recorded_artifact
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if tamper == "candidate_head":
        artifact["candidate_seal"]["head"] = "0" * 40
    elif tamper == "receipt_digest":
        artifact["holdout_receipt"]["sha256"] = "0" * 64
    elif tamper == "holdout_delta":
        artifact["observation"]["candidate_membership_delta"] = 1
    elif tamper == "runtime_profile":
        artifact["observation"]["runtime_profile"]["sqlite"] = "0.0.0"
    else:
        artifact["observation"]["cases"][0][
            "reverse_stable_projections"
        ].reverse()

    def observer(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("post-holdout validation must not observe")

    monkeypatch.setattr(
        workflow,
        "observe_retrieval_order_partition",
        observer,
    )

    with pytest.raises(RetrievalOrderArtifactError):
        validate_retrieval_order_artifact(
            artifact,
            protocol_path=protocol,
            repository_root=root,
        )


def test_protocol_oracle_is_independent_of_candidate_array_order(
    tmp_path: Path,
) -> None:
    root, protocol_path = _synthetic_repository(tmp_path)
    protocol = load_retrieval_order_protocol(
        protocol_path,
        repository_root=root,
    )
    fixture = deepcopy(protocol.development.fixture)
    cases = cast(list[dict[str, object]], fixture["cases"])
    for case in cases:
        cast(list[object], case["candidates"]).reverse()

    original = artifact_module._evaluate_protocol_partition(  # pyright: ignore[reportPrivateUsage]
        protocol.development.fixture,
        partition="development",
    )
    reversed_candidates = artifact_module._evaluate_protocol_partition(  # pyright: ignore[reportPrivateUsage]
        fixture,
        partition="development",
    )

    assert reversed_candidates == original


@pytest.mark.parametrize(
    "tamper",
    (
        "contradict_expected",
        "fts_text_shape",
        "cjk_overlap_shape",
        "duplicate_total_key",
    ),
)
def test_protocol_oracle_rejects_invalid_frozen_tie_contract(
    tmp_path: Path,
    tamper: str,
) -> None:
    root, protocol_path = _synthetic_repository(tmp_path)
    protocol = load_retrieval_order_protocol(
        protocol_path,
        repository_root=root,
    )
    fixture = deepcopy(protocol.development.fixture)
    cases = cast(list[dict[str, object]], fixture["cases"])
    fts = next(case for case in cases if case["strategy"] == "fts")
    cjk = next(case for case in cases if case["strategy"] == "cjk")
    if tamper == "contradict_expected":
        cast(list[object], fts["expected_stable_projections"]).reverse()
    elif tamper == "fts_text_shape":
        cast(list[dict[str, object]], fts["candidates"])[0]["text"] = (
            "synthetic ordering probe synthetic"
        )
    elif tamper == "cjk_overlap_shape":
        cast(list[dict[str, object]], cjk["candidates"])[0]["text"] = (
            "合成排序"
        )
    else:
        candidates = cast(list[dict[str, object]], fts["candidates"])
        for field in (
            "locator_start",
            "locator_kind",
            "locator_end",
            "asset_sha256",
            "content_fingerprint",
        ):
            candidates[1][field] = candidates[0][field]

    with pytest.raises(RetrievalOrderArtifactError):
        artifact_module._evaluate_protocol_partition(  # pyright: ignore[reportPrivateUsage]
            fixture,
            partition="development",
        )


@pytest.mark.parametrize(
    "tamper",
    (
        "identical_forged_projection",
        "missing_case",
        "extra_case",
        "reordered_case",
        "substituted_case",
        "wrong_strategy",
        "missing_score",
        "extra_score",
        "duplicate_score_projection",
        "mismatched_score_projection",
        "bool_strategy_revision",
        "bool_query_policy_revision",
        "bool_counter",
        "bool_rate",
    ),
)
def test_retained_artifact_is_bound_to_exact_protocol_inventory(
    recorded_artifact: tuple[Path, Path, Path],
    tamper: str,
) -> None:
    root, protocol, artifact_path = recorded_artifact
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    observation = cast(dict[str, object], artifact["observation"])
    cases = cast(list[dict[str, object]], observation["cases"])
    if tamper == "identical_forged_projection":
        forged = deepcopy(cases[0]["forward_stable_projections"])
        cast(list[object], forged).reverse()
        cases[0]["forward_stable_projections"] = forged
        cases[0]["reverse_stable_projections"] = deepcopy(forged)
        scores = cast(list[list[object]], cases[0]["score_hex"])
        scores.reverse()
    elif tamper == "missing_case":
        cases.pop()
    elif tamper == "extra_case":
        extra = deepcopy(cases[-1])
        extra["case_id"] = "synthetic-extra-case"
        cases.append(extra)
    elif tamper == "reordered_case":
        cases.reverse()
    elif tamper == "substituted_case":
        cases[0]["case_id"] = "synthetic-substitute"
    elif tamper == "wrong_strategy":
        cases[0]["strategy"] = "cjk"
    elif tamper == "missing_score":
        cast(list[object], cases[0]["score_hex"]).pop()
    elif tamper == "extra_score":
        cast(list[object], cases[0]["score_hex"]).append(
            deepcopy(cast(list[object], cases[0]["score_hex"])[0])
        )
    elif tamper == "duplicate_score_projection":
        scores = cast(list[list[object]], cases[0]["score_hex"])
        projections = cast(
            list[list[object]],
            cases[0]["forward_stable_projections"],
        )
        projections[1] = deepcopy(projections[0])
        cast(list[list[object]], cases[0]["reverse_stable_projections"])[
            1
        ] = deepcopy(projections[0])
        scores[1][0] = deepcopy(scores[0][0])
    elif tamper == "mismatched_score_projection":
        cast(list[list[object]], cases[0]["score_hex"])[0][0] = deepcopy(
            cast(list[list[object]], cases[0]["score_hex"])[1][0]
        )
    elif tamper == "bool_strategy_revision":
        observation["strategy_revision"] = True
        cast(dict[str, object], observation["runtime_profile"])[
            "strategy_revision"
        ] = True
        candidate = cast(dict[str, object], artifact["candidate_seal"])
        cast(dict[str, object], candidate["runtime_profile"])[
            "strategy_revision"
        ] = True
    elif tamper == "bool_query_policy_revision":
        observation["query_policy_revision"] = True
        cast(dict[str, object], observation["runtime_profile"])[
            "query_policy_revision"
        ] = True
        candidate = cast(dict[str, object], artifact["candidate_seal"])
        cast(dict[str, object], candidate["runtime_profile"])[
            "query_policy_revision"
        ] = True
    elif tamper == "bool_counter":
        observation["candidate_membership_delta"] = False
    else:
        observation["stable_order_rate"] = True

    with pytest.raises(RetrievalOrderArtifactError):
        validate_retrieval_order_artifact(
            artifact,
            protocol_path=protocol,
            repository_root=root,
        )


def test_retained_freeze_is_bound_to_protocol_oracle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol = _synthetic_repository(tmp_path)
    freeze = root / "development-freeze.json"
    monkeypatch.chdir(root)
    workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol,
        freeze_path=freeze,
        repository_root=root,
    )
    payload = json.loads(freeze.read_text(encoding="utf-8"))
    cases = cast(
        list[dict[str, object]],
        cast(dict[str, object], payload["observation"])["cases"],
    )
    cases.reverse()
    metadata = workflow.load_retrieval_order_protocol_metadata(
        protocol,
        repository_root=root,
    )

    with pytest.raises(RetrievalOrderArtifactError):
        artifact_module.validate_development_freeze(
            payload,
            metadata=metadata,
            expected_candidate_seal=cast(
                dict[str, object], payload["candidate_seal"]
            ),
            repository_root=root,
        )


def test_retained_validation_is_pure_protocol_reconstruction(
    recorded_artifact: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol, artifact_path = recorded_artifact
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    before = {
        path: path.read_bytes()
        for path in (
            protocol,
            artifact_path,
            root / artifact["development_freeze"]["path"],
            root / artifact["holdout_receipt"]["path"],
        )
    }

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("pure validation crossed the observer boundary")

    monkeypatch.setattr(workflow, "observe_retrieval_order_partition", forbidden)
    monkeypatch.setattr(workflow.tempfile, "TemporaryDirectory", forbidden)

    validate_retrieval_order_artifact(
        artifact,
        protocol_path=protocol,
        repository_root=root,
    )

    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("retained_shape", ("development", "holdout"))
@pytest.mark.parametrize(
    "score_tamper",
    (
        "fts_distinct_canonical_hex",
        "fts_noncanonical_token",
        "cjk_wrong_marker",
    ),
)
def test_retained_validation_rejects_forged_primary_tie_scores(
    recorded_artifact: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    retained_shape: str,
    score_tamper: str,
) -> None:
    root, protocol, artifact_path = recorded_artifact
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    freeze_identity = cast(
        dict[str, object],
        artifact["development_freeze"],
    )
    freeze_relative = freeze_identity["path"]
    assert isinstance(freeze_relative, str)
    freeze_path = root / freeze_relative
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    retained = freeze if retained_shape == "development" else artifact
    observation = cast(dict[str, object], retained["observation"])
    cases = cast(list[dict[str, object]], observation["cases"])
    strategy = "cjk" if score_tamper == "cjk_wrong_marker" else "fts"
    case = next(item for item in cases if item["strategy"] == strategy)
    scores = cast(list[list[object]], case["score_hex"])
    assert len({cast(str, item[1]) for item in scores}) == 1
    if score_tamper == "fts_distinct_canonical_hex":
        scores[0][1] = (1.0).hex()
    elif score_tamper == "fts_noncanonical_token":
        for item in scores:
            item[1] = "forged-non-tied-primary-score"
    else:
        for item in scores:
            item[1] = "cjk-forged-overlap"
    before = {
        path: path.read_bytes()
        for path in (protocol, freeze_path, artifact_path)
    }

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("retained validation must stay pure")

    monkeypatch.setattr(workflow, "observe_retrieval_order_partition", forbidden)
    monkeypatch.setattr(workflow.tempfile, "TemporaryDirectory", forbidden)

    with pytest.raises(RetrievalOrderArtifactError):
        if retained_shape == "development":
            metadata = workflow.load_retrieval_order_protocol_metadata(
                protocol,
                repository_root=root,
            )
            artifact_module.validate_development_freeze(
                freeze,
                metadata=metadata,
                expected_candidate_seal=cast(
                    dict[str, object],
                    freeze["candidate_seal"],
                ),
                repository_root=root,
            )
        else:
            validate_retrieval_order_artifact(
                artifact,
                protocol_path=protocol,
                repository_root=root,
            )

    assert {path: path.read_bytes() for path in before} == before


def _synthetic_repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "synthetic-repository"
    fixture_root = root / "fixtures"
    fixture_root.mkdir(parents=True)
    payload = deepcopy(
        json.loads(CANONICAL_PROTOCOL.read_text(encoding="utf-8"))
    )
    partitions = cast(dict[str, object], payload["partitions"])
    for name in ("development", "holdout"):
        record = cast(dict[str, object], partitions[name])
        fixture = synthetic_fixture_payload(name)
        data = (
            json.dumps(
                fixture,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        destination = fixture_root / f"{name}.json"
        destination.write_bytes(data)
        record["path"] = destination.relative_to(root).as_posix()
        record["bytes"] = len(data)
        record["sha256"] = hashlib.sha256(data).hexdigest()
        record["cases"] = synthetic_partition_metadata(fixture)
    protocol = root / "protocol.json"
    protocol.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )
    commands = (
        ("git", "init", "-q"),
        ("git", "config", "user.email", "synthetic@example.invalid"),
        ("git", "config", "user.name", "Synthetic Authority"),
        ("git", "add", "protocol.json", "fixtures"),
        ("git", "commit", "-qm", "synthetic authority"),
    )
    for command in commands:
        subprocess.run(command, cwd=root, check=True)
    return root.resolve(), protocol.resolve()
