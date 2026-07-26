from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, NoReturn

import pytest

import mke.evaluation._atomic_json_publication as atomic_publication
import mke.evaluation.retrieval_order_workflow as retrieval_order_workflow
from mke.evaluation import dense_artifact as dense_artifact_module
from mke.evaluation import hybrid_rrf_artifact as hybrid_rrf_artifact_module
from mke.evaluation import (
    relevance_gate_artifact as relevance_gate_artifact_module,
)
from tests.evaluation.test_retrieval_order_workflow import (
    synthetic_fixture_payload,
    synthetic_partition_metadata,
)

ROOT = Path(__file__).resolve().parents[2]
NUMERIC_ARTIFACT = (
    ROOT / "benchmarks/retrieval/numeric-grouping-v1-comparison.json"
)
PROTOCOL = ROOT / "tests/fixtures/retrieval-order-v1/protocol.json"
CANONICAL = (
    ROOT / "benchmarks/retrieval/retrieval-order-v2-compatibility.json"
)
CANONICAL_HOLDOUT_FIXTURE = (
    ROOT / "tests/fixtures/retrieval-order-v1/holdout/cases.json"
)
IMMUTABLE_INPUT_SHA256 = {
    "benchmarks/retrieval/retrieval-eval-v1-baseline.json": (
        "c2518b2f95a91eb91f2f83953965e186711e2b3d93725e9d83617d0fde530a88"
    ),
    "benchmarks/retrieval/numeric-grouping-v1-comparison.json": (
        "98fb1f61d824d7b307d3a2745b49ed972fc6d4af292833098a15b13b860ddae9"
    ),
    "benchmarks/retrieval/retrieval-chinese-v1-baseline.json": (
        "7187d999fc98f2ed0f405756f0a4b02ab4dcbb14fdb8d49d8bfd1ad205295828"
    ),
    "benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json": (
        "5cb54cc7baea939b439c617ee917badff64bface2f2fe5a85b128185fdf3ed3c"
    ),
    "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json": (
        "a992059a24b5afbd26c22f71916d7266ada9c3e9ed1fe1354447c7f5f2c40d26"
    ),
    "benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json": (
        "6b77d29fa3b8badd7400e53fa96cd544ecf84d51563170bfc44d56975ff470c3"
    ),
    "benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json": (
        "e22e561618726c339bd955d1c7cfcf573080c251549e6a89c8187251d6011e36"
    ),
    "tests/fixtures/retrieval-eval-v1.json": (
        "a65b33e011c7a39245a2202fa741e57a268b42da9f68d8da0725955834dd4761"
    ),
    "tests/fixtures/retrieval-numeric-v1/protocol-lock.json": (
        "17c424e49237deba600fef70d47da803fb73f72d2ee65995fc155dc96e22da60"
    ),
    "tests/fixtures/retrieval-chinese-v1/protocol.json": (
        "00f72934018a52b5b5f5591fba119050882aee9b782e5dac199702b0cf995944"
    ),
    "tests/fixtures/retrieval-dense-v1/protocol-lock.json": (
        "afca992a7115fdb06e620168d14f8d09055f231c061b59f82c69f0be2a6e4251"
    ),
    "tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json": (
        "2407fb3d9abfe1a1127c5d9a600dea529c32c308a42cbd3622c52211d314a716"
    ),
    "tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json": (
        "6983eb5243493176d6cf97a5e7b5ae888aac9885c25e945583bc291aacf253b1"
    ),
    "benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json": (
        "1a98e4e6c4eabc01663991646aac46e4a73033eef8a7e17a27db2e0fdce71691"
    ),
}


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


def _module() -> Any:
    return importlib.import_module(
        "mke.evaluation.retrieval_order_compatibility"
    )


def _fail_replay(*args: object, **kwargs: object) -> NoReturn:
    del args
    del kwargs
    raise AssertionError("replay must not start")


def _accept_validation(*args: object, **kwargs: object) -> None:
    del args, kwargs


def _invalid_readback(path: Path) -> bytes:
    del path
    return b"{}"


def _block_all_replay(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
) -> None:
    for name in (
        "build_compatibility_artifact",
        "freeze_historical_capabilities",
        "_current_e1_e2",
        "_current_chinese_artifact",
        "_current_cjk_artifact",
        "validate_dense_comparison_artifact",
        "validate_hybrid_rrf_artifact",
        "validate_relevance_gate_artifact",
        "run_chinese_retrieval_evaluation",
        "run_cjk_lexical_comparison",
        "record_chinese_artifact",
        "record_cjk_lexical_artifact",
    ):
        monkeypatch.setattr(module, name, _fail_replay)
    monkeypatch.setattr(
        module.runner,
        "_observe_retrieval_evaluation",
        _fail_replay,
    )
    monkeypatch.setattr(
        dense_artifact_module,
        "build_dense_comparison_artifact",
        _fail_replay,
    )
    monkeypatch.setattr(
        hybrid_rrf_artifact_module,
        "run_hybrid_rrf_development",
        _fail_replay,
    )
    monkeypatch.setattr(
        relevance_gate_artifact_module,
        "run_relevance_gate_development",
        _fail_replay,
    )
    monkeypatch.setattr(
        relevance_gate_artifact_module,
        "build_relevance_gate_holdout_report",
        _fail_replay,
    )


@pytest.fixture(scope="module")
def compatibility_artifact(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, object]:
    return _module().build_compatibility_artifact(
        protocol_path=PROTOCOL,
        repository_root=ROOT,
        workspace=tmp_path_factory.mktemp("compatibility-authority"),
    )


def test_family_table_freezes_all_historical_authority_before_replay() -> None:
    module = _module()
    capability = module._capability(
        status="deterministic_historical_subprocess_replay",
        first="",
        second="",
        origins=True,
        inputs=True,
    )

    table = module.family_capability_table(
        historical_capability=capability
    )

    assert tuple(item.family for item in table) == (
        "e1_baseline",
        "e2_numeric",
        "e3a_chinese",
        "e3b_cjk_lexical",
        "e3c_dense",
        "e3d_hybrid_rrf",
        "e3e_relevance_gate",
    )
    assert all(item.recorded_order_projection for item in table)
    assert tuple(item.recorded_exact_score for item in table) == (
        "not_recorded",
        "not_recorded",
        "direct",
        "direct",
        "direct",
        "derived_from_recorded_parent",
        "derived_from_recorded_parent",
    )
    assert all(item.historical_runtime_profile for item in table)
    assert all(item.allowed_delta == "preidentified_tie_permutation_only" for item in table)
    assert tuple(item.tie_group_authority for item in table[:2]) == (
        "deterministic_historical_subprocess_replay",
        "deterministic_historical_subprocess_replay",
    )


def test_family_table_requires_explicit_frozen_capability() -> None:
    module = _module()

    with pytest.raises(TypeError):
        module.family_capability_table()


def test_historical_capability_uses_exact_tree_runtime_and_two_replays(
    tmp_path: Path,
) -> None:
    module = _module()

    capability = module.freeze_historical_capabilities(
        repository_root=ROOT,
        workspace=tmp_path,
    )

    assert capability.status == "deterministic_historical_subprocess_replay"
    assert capability.source_commit == (
        "eea3d51c36c0b3b845b8efb60eff553ddc200b88"
    )
    assert capability.source_tree == (
        "30c0a65e265ce0342462ffc44c2c4fe799f959b5"
    )
    assert capability.source_identity == (
        "c3cec8853547fd09d8fad10865666ce2bb1a507afe19a066a364ab2424064665"
    )
    assert capability.recorded_blob_count == 107
    assert capability.runtime_profile == {
        "python": "3.13.12",
        "sqlite": "3.51.1",
        "pymupdf": "1.27.2.3",
    }
    assert capability.child_argv == ("python", "-B", "-P", "-c", "<bootstrap>")
    assert capability.checkout_external_cwd is True
    assert capability.python_no_user_site is True
    assert capability.inherited_python_path_cleared is True
    assert capability.inherited_python_home_cleared is True
    assert capability.module_origins_valid is True
    assert capability.input_identities_valid is True
    assert capability.bootstrap_sha256 == (
        "0890233aa38141a17fce5fb445a9660cf7ca1d38e70259db2266fc4eda2b6abf"
    )
    assert capability.first_stdout == capability.second_stdout
    payload = json.loads(capability.first_stdout)
    assert set(payload["families"]) == {"e1_baseline", "e2_numeric"}
    assert payload["runtime"] == capability.runtime_profile
    assert payload["source"]["blob_count"] == 107
    assert payload["families"]["e1_baseline"]["queries"]
    assert payload["families"]["e2_numeric"]["queries"]
    assert all(
        {
            "score_hex",
            "stable_projections",
            "tie_groups",
        }.issubset(query)
        for family in payload["families"].values()
        for query in family["queries"]
    )


def test_historical_capability_downgrades_both_families_before_current_replay(
    tmp_path: Path,
) -> None:
    module = _module()
    artifact = tmp_path / "numeric.json"
    payload = json.loads(NUMERIC_ARTIFACT.read_text(encoding="utf-8"))
    payload["source"]["files"][0]["sha256"] = "0" * 64
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    capability = module.freeze_historical_capabilities(
        repository_root=ROOT,
        workspace=tmp_path / "workspace",
        numeric_artifact_path=artifact,
    )

    assert capability.status == "no_ordered_delta_authority"
    assert capability.first_stdout == ""
    assert capability.second_stdout == ""
    assert capability.module_origins_valid is False
    table = module.family_capability_table(historical_capability=capability)
    assert tuple(item.tie_group_authority for item in table[:2]) == (
        "no_ordered_delta_authority",
        "no_ordered_delta_authority",
    )


def test_compatibility_artifact_exposes_complete_family_differentials(
    tmp_path: Path,
) -> None:
    module = _module()

    artifact = module.build_compatibility_artifact(
        protocol_path=PROTOCOL,
        repository_root=ROOT,
        workspace=tmp_path,
    )

    assert artifact["schema_version"] == (
        "mke.retrieval_order_compatibility.v1"
    )
    assert artifact["integrity_status"] == "passed"
    assert artifact["compatibility_status"] == "passed"
    assert artifact["protocol"]["id"] == "retrieval-order-v1"
    assert artifact["historical_capability"]["status"] == (
        "deterministic_historical_subprocess_replay"
    )
    assert artifact["current_source"]["files"]
    families = artifact["families"]
    assert tuple(item["family"] for item in families) == (
        "e1_baseline",
        "e2_numeric",
        "e3a_chinese",
        "e3b_cjk_lexical",
        "e3c_dense",
        "e3d_hybrid_rrf",
        "e3e_relevance_gate",
    )
    required = {
        "family",
        "historical_input",
        "archived_self_consistency_status",
        "current_source_identity",
        "runtime_profile",
        "preidentified_exact_score_tie_groups",
        "before_after_stable_projections",
        "membership_delta",
        "score_hex_delta",
        "non_tied_pair_delta",
        "metric_delta",
        "gate_delta",
        "verdict_delta",
        "status",
    }
    assert all(set(item) == required for item in families)
    assert all(item["archived_self_consistency_status"] == "passed" for item in families)
    assert all(item["membership_delta"] == 0 for item in families)
    assert all(item["score_hex_delta"] == 0 for item in families)
    assert all(item["non_tied_pair_delta"] == 0 for item in families)
    assert all(item["metric_delta"] == 0 for item in families)
    assert all(item["gate_delta"] == 0 for item in families)
    assert all(item["verdict_delta"] == 0 for item in families)
    assert all(item["status"] == "passed" for item in families)
    assert isinstance(
        families[0]["preidentified_exact_score_tie_groups"], list
    )
    assert isinstance(
        families[1]["preidentified_exact_score_tie_groups"], list
    )


def test_no_ordered_delta_authority_rejects_any_order_change() -> None:
    module = _module()
    before = {
        "policy": "current",
        "query_id": "query",
        "stable_projections": [
            ["doc-a", "page", 1, 1],
            ["doc-b", "page", 1, 1],
        ],
        "score_hex": ["-0x1.0p-2", "-0x1.0p-2"],
        "tie_groups": [
            {
                "score_hex": "-0x1.0p-2",
                "stable_projections": [
                    ["doc-a", "page", 1, 1],
                    ["doc-b", "page", 1, 1],
                ],
            }
        ],
    }
    after = {
        **before,
        "stable_projections": list(
            reversed(before["stable_projections"])
        ),
    }

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module.compare_ordered_queries(
            [before],
            [after],
            tie_group_authority="no_ordered_delta_authority",
        )


def test_downgraded_family_uses_immutable_recorded_order() -> None:
    module = _module()
    capability = module._capability(
        status="no_ordered_delta_authority",
        first="",
        second="",
        origins=False,
        inputs=False,
    )
    queries = module._archived_order_queries("e1_baseline", ROOT)
    current_queries = deepcopy(queries)
    changed = next(
        query
        for query in current_queries
        if len(query["stable_projections"]) > 1
    )
    changed["stable_projections"].reverse()
    historical = json.loads(
        (
            ROOT
            / "benchmarks/retrieval/retrieval-eval-v1-baseline.json"
        ).read_text(encoding="utf-8")
    )

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module._e1_e2_family(
            family="e1_baseline",
            capability=capability,
            historical_payload=None,
            current_payload={
                "queries": current_queries,
                "semantic_report": historical,
            },
            current_source=module._current_source_identity(ROOT),
            root=ROOT,
        )


def test_historical_child_cannot_replace_immutable_e1_authority() -> None:
    module = _module()
    capability = module._capability(
        status="deterministic_historical_subprocess_replay",
        first="forged",
        second="forged",
        origins=True,
        inputs=True,
    )
    archived_queries = module._archived_order_queries("e1_baseline", ROOT)
    forged_queries = deepcopy(archived_queries)
    forged = next(
        query
        for query in forged_queries
        if query["stable_projections"]
    )
    forged["stable_projections"] = [["forged", "page", 1, 1]]
    for query in forged_queries:
        query["score_hex"] = [
            "0x0.0p+0"
            for _ in query["stable_projections"]
        ]
        query["tie_groups"] = []
    archived = json.loads(
        (
            ROOT
            / "benchmarks/retrieval/retrieval-eval-v1-baseline.json"
        ).read_text(encoding="utf-8")
    )
    historical_payload = {
        "families": {
            "e1_baseline": {
                "queries": forged_queries,
                "semantic_report": {
                    "metrics": archived["metrics"],
                    "status": "passed",
                    "quality_status": "baseline_recorded",
                },
            }
        }
    }

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module._e1_e2_family(
            family="e1_baseline",
            capability=capability,
            historical_payload=historical_payload,
            current_payload={
                "queries": deepcopy(forged_queries),
                "semantic_report": deepcopy(
                    historical_payload["families"]["e1_baseline"][
                        "semantic_report"
                    ]
                ),
            },
            current_source=module._current_source_identity(ROOT),
            root=ROOT,
        )


def test_historical_child_artifact_mismatch_is_terminal_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    capability = module.freeze_historical_capabilities(
        repository_root=ROOT,
        workspace=tmp_path / "authority",
    )
    payload = json.loads(capability.first_stdout)
    payload["families"]["e1_baseline"]["queries"][0][
        "stable_projections"
    ] = [["forged", "page", 1, 1]]
    forged = (
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )

    def forged_child(**kwargs: object) -> str:
        del kwargs
        return forged

    monkeypatch.setattr(module, "_run_historical_child", forged_child)

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module.freeze_historical_capabilities(
            repository_root=ROOT,
            workspace=tmp_path / "forged",
        )


def test_e3a_adapter_rejects_tampered_unselected_archived_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    artifact_path = ROOT / (
        "benchmarks/retrieval/retrieval-chinese-v1-baseline.json"
    )
    historical = json.loads(artifact_path.read_text(encoding="utf-8"))
    tampered = deepcopy(historical)
    tampered["source_identity"]["sha256"] = "0" * 64
    original_load = module._load_object

    def load(path: Path) -> dict[str, object]:
        if path.resolve() == artifact_path.resolve():
            return deepcopy(tampered)
        return original_load(path)

    monkeypatch.setattr(module, "_load_object", load)

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module._e3a_family(
            current=historical,
            current_source=module._current_source_identity(ROOT),
            root=ROOT,
        )


def test_repeated_builds_are_byte_identical(tmp_path: Path) -> None:
    module = _module()
    first = module.build_compatibility_artifact(
        protocol_path=PROTOCOL,
        repository_root=ROOT,
        workspace=tmp_path / "first",
    )
    second = module.build_compatibility_artifact(
        protocol_path=PROTOCOL,
        repository_root=ROOT,
        workspace=tmp_path / "second",
    )

    assert module.render_compatibility_artifact(first) == (
        module.render_compatibility_artifact(second)
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        (("current_source", "sha256"), "0" * 64),
        (
            (
                "families",
                0,
                "preidentified_exact_score_tie_groups",
            ),
            [{"query_id": "forged"}],
        ),
        (("families", 0, "membership_delta"), 1),
        (("families", 0, "score_hex_delta"), 1),
        (
            (
                "families",
                0,
                "before_after_stable_projections",
            ),
            [],
        ),
        (("families", 0, "metric_delta"), 1),
        (("families", 0, "gate_delta"), 1),
        (("families", 0, "verdict_delta"), 1),
        (
            ("historical_capability", "runtime_profile", "python"),
            "0.0.0",
        ),
        (
            (
                "families",
                0,
                "historical_input",
                "artifact",
                "sha256",
            ),
            "0" * 64,
        ),
    ],
)
def test_validator_rejects_authority_tampering(
    compatibility_artifact: dict[str, object],
    field: tuple[object, ...],
    replacement: object,
) -> None:
    module = _module()
    expected = compatibility_artifact
    candidate = deepcopy(expected)
    target: object = candidate
    for key in field[:-1]:
        target = target[key]  # type: ignore[index]
    target[field[-1]] = replacement  # type: ignore[index]

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module.validate_compatibility_artifact(
            candidate,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )


def test_temporary_record_and_read_only_validate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()
    artifact = tmp_path / "compatibility.json"

    assert module.main(
        [
            "record",
            "--protocol",
            str(PROTOCOL),
            "--artifact",
            str(artifact),
            "--repository",
            str(ROOT),
            "--json",
        ]
    ) == 0
    record_output = json.loads(capsys.readouterr().out)
    original = artifact.read_bytes()
    assert record_output["status"] == "passed"
    assert record_output["output_state"] == "complete_visible"
    assert record_output["publication_outcome"] == "published"

    assert module.main(
        [
            "validate",
            "--protocol",
            str(PROTOCOL),
            "--artifact",
            str(artifact),
            "--repository",
            str(ROOT),
            "--json",
        ]
    ) == 0
    validate_capture = capsys.readouterr()
    validate_output = json.loads(validate_capture.out)
    assert validate_capture.err == ""
    assert validate_output["status"] == "passed"
    assert validate_output["output_state"] == "complete_preexisting"
    assert validate_output["publication_outcome"] == "not_attempted"
    assert artifact.read_bytes() == original


def test_validate_is_pure_and_never_replays(
    compatibility_artifact: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()
    artifact = tmp_path / "compatibility.json"
    artifact.write_bytes(
        module.render_compatibility_artifact(compatibility_artifact)
    )

    _block_all_replay(monkeypatch, module)

    assert module.main(
        [
            "validate",
            "--protocol",
            str(PROTOCOL),
            "--artifact",
            str(artifact),
            "--repository",
            str(ROOT),
            "--json",
        ]
    ) == 0
    capture = capsys.readouterr()
    assert capture.err == ""
    assert json.loads(capture.out)["status"] == "passed"


@pytest.mark.parametrize("tamper", ("historical_digest", "differential"))
def test_pure_validate_rejects_tampering_without_replay(
    compatibility_artifact: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    module = _module()
    candidate = deepcopy(compatibility_artifact)
    family = candidate["families"][0]  # type: ignore[index]
    if tamper == "historical_digest":
        family["historical_input"]["protocol"]["sha256"] = "0" * 64  # type: ignore[index]
    else:
        family["before_after_stable_projections"] = []  # type: ignore[index]
    _block_all_replay(monkeypatch, module)

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module.validate_compatibility_artifact(
            candidate,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )


def test_record_rejects_canonical_path_before_replay(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()
    assert not CANONICAL.exists()
    monkeypatch.setattr(
        module,
        "build_compatibility_artifact",
        _fail_replay,
    )

    assert module.main(
        [
            "record",
            "--protocol",
            str(PROTOCOL),
            "--artifact",
            str(CANONICAL),
            "--repository",
            str(ROOT),
            "--json",
        ]
    ) == 1

    capture = capsys.readouterr()
    output = json.loads(capture.out)
    assert capture.err == ""
    assert output["status"] == "failed"
    assert output["output_state"] == "not_applicable"
    assert output["publication_outcome"] == "not_attempted"
    assert output["problem"] == (
        "retrieval_order_canonical_publication_unauthorized"
    )
    assert output["cause"] == "required_success_authority_missing"
    assert output["next_step"] == "wait_for_successful_holdout"
    assert str(ROOT) not in capture.out
    assert not CANONICAL.exists()


def test_help_freezes_authority_boundaries(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()

    with pytest.raises(SystemExit) as raised:
        module.main(["--help"])

    assert raised.value.code == 0
    output = capsys.readouterr().out
    for boundary in (
        (
            "archive validation -> historical bytes are "
            "self-consistent only"
        ),
        "current replay -> current runtime compatibility only",
        (
            "differential validation -> revision-2 "
            "comparison only"
        ),
        "temporary output -> never canonical authority",
    ):
        assert boundary in output


def test_record_canonical_publishes_attempt_before_replay_and_closes_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()
    (
        root,
        protocol,
        freeze,
        receipt,
        retrieval_artifact,
        candidate_head,
    ) = _synthetic_canonical_authority(tmp_path, monkeypatch)
    attempt = (
        root
        / "benchmarks/retrieval/"
        "retrieval-order-v2-compatibility-attempt.json"
    )
    artifact = (
        root
        / "benchmarks/retrieval/"
        "retrieval-order-v2-compatibility.json"
    )
    build_calls = 0

    def build(**kwargs: object) -> dict[str, object]:
        nonlocal build_calls
        del kwargs
        build_calls += 1
        assert attempt.exists()
        return {
            "schema_version": "mke.retrieval_order_compatibility.v1",
            "protocol": {},
            "historical_capability": {},
            "current_source": {},
            "families": [],
            "integrity_status": "passed",
            "compatibility_status": "passed",
            "limitations": [
                "historical_compatibility_only",
                "tie_permutation_only",
                "no_relevance_improvement_claim",
                "no_runtime_promotion",
                "public_holdout_not_observed",
            ],
        }

    monkeypatch.setattr(module, "build_compatibility_artifact", build)
    monkeypatch.setattr(
        module,
        "validate_compatibility_artifact",
        _accept_validation,
    )

    arguments = [
        "record-canonical",
        "--protocol",
        str(protocol),
        "--development-freeze",
        str(freeze),
        "--holdout-receipt",
        str(receipt),
        "--retrieval-artifact",
        str(retrieval_artifact),
        "--candidate-head",
        candidate_head,
        "--attempt-receipt",
        str(attempt),
        "--artifact",
        str(artifact),
        "--repository",
        str(root),
        "--json",
    ]
    assert module.main(arguments) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    assert result["mode"] == "record_canonical"
    assert result["canonical"] is True
    assert build_calls == 1
    attempt_bytes = attempt.read_bytes()
    assert artifact.exists()

    assert module.main(arguments) == 1
    repeated = json.loads(capsys.readouterr().out)
    assert repeated["problem"] == (
        "retrieval_order_canonical_publication_already_started"
    )
    assert attempt.read_bytes() == attempt_bytes
    assert build_calls == 1


def test_record_canonical_rejects_missing_success_authority_before_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()
    (
        root,
        protocol,
        freeze,
        receipt,
        retrieval_artifact,
        candidate_head,
    ) = _synthetic_canonical_authority(tmp_path, monkeypatch)
    receipt.unlink()
    attempt = (
        root
        / "benchmarks/retrieval/"
        "retrieval-order-v2-compatibility-attempt.json"
    )
    artifact = (
        root
        / "benchmarks/retrieval/"
        "retrieval-order-v2-compatibility.json"
    )
    monkeypatch.setattr(
        module,
        "build_compatibility_artifact",
        _fail_replay,
    )

    assert module.main(
        [
            "record-canonical",
            "--protocol",
            str(protocol),
            "--development-freeze",
            str(freeze),
            "--holdout-receipt",
            str(receipt),
            "--retrieval-artifact",
            str(retrieval_artifact),
            "--candidate-head",
            candidate_head,
            "--attempt-receipt",
            str(attempt),
            "--artifact",
            str(artifact),
            "--repository",
            str(root),
            "--json",
        ]
    ) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["problem"] == (
        "retrieval_order_canonical_publication_unauthorized"
    )
    assert not attempt.exists()
    assert not artifact.exists()


@pytest.mark.parametrize(
    ("tamper", "expected_problem"),
    (
        ("candidate_seal", "retrieval_order_candidate_seal_mismatch"),
        (
            "failed_holdout",
            "retrieval_order_canonical_publication_unauthorized",
        ),
    ),
)
def test_record_canonical_rejects_seal_or_holdout_tamper_before_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
    expected_problem: str,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    if tamper == "candidate_seal":
        candidate_head = "0" * 40
    else:
        payload = json.loads(
            retrieval_artifact.read_text(encoding="utf-8")
        )
        payload["holdout_status"] = "failed"
        retrieval_artifact.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    monkeypatch.setattr(
        module,
        "build_compatibility_artifact",
        _fail_replay,
    )

    result = module.record_canonical_compatibility(
        protocol_path=protocol,
        development_freeze_path=freeze,
        holdout_receipt_path=receipt,
        retrieval_artifact_path=retrieval_artifact,
        candidate_head=candidate_head,
        attempt_receipt_path=attempt,
        artifact_path=artifact,
        repository_root=root,
    )

    assert result["status"] == "failed"
    assert result["problem"] == expected_problem
    assert not attempt.exists()
    assert not artifact.exists()


def test_canonical_validate_is_pure_and_preserves_existing_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    monkeypatch.setattr(
        module,
        "build_compatibility_artifact",
        _complete_compatibility_double,
    )
    monkeypatch.setattr(
        module,
        "validate_compatibility_artifact",
        _accept_validation,
    )
    recorded = module.record_canonical_compatibility(
        protocol_path=protocol,
        development_freeze_path=freeze,
        holdout_receipt_path=receipt,
        retrieval_artifact_path=retrieval_artifact,
        candidate_head=candidate_head,
        attempt_receipt_path=attempt,
        artifact_path=artifact,
        repository_root=root,
    )
    assert recorded["status"] == "passed"
    retained = artifact.read_bytes()
    monkeypatch.setattr(
        module,
        "build_compatibility_artifact",
        _fail_replay,
    )
    monkeypatch.setattr(
        retrieval_order_workflow,
        "observe_retrieval_order_partition",
        _fail_replay,
    )

    assert module.main(
        [
            "validate",
            "--protocol",
            str(protocol),
            "--artifact",
            str(artifact),
            "--repository",
            str(root),
            "--json",
        ]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    assert result["canonical"] is True
    assert artifact.read_bytes() == retained


def test_canonical_artifact_binds_exact_immutable_inputs_and_rejects_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    monkeypatch.setattr(
        module,
        "build_compatibility_artifact",
        _complete_compatibility_double,
    )
    monkeypatch.setattr(
        module,
        "validate_compatibility_artifact",
        _accept_validation,
    )

    result = module.record_canonical_compatibility(
        protocol_path=protocol,
        development_freeze_path=freeze,
        holdout_receipt_path=receipt,
        retrieval_artifact_path=retrieval_artifact,
        candidate_head=candidate_head,
        attempt_receipt_path=attempt,
        artifact_path=artifact,
        repository_root=root,
    )

    assert result["status"] == "passed"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["immutable_inputs"] == IMMUTABLE_INPUT_SHA256
    assert {
        name: payload[name]
        for name in (
            "historical_bytes_frozen",
            "archived_record_self_consistent",
            "current_runtime_replay_compatible",
            "revision_2_differential_valid",
        )
    } == {
        "historical_bytes_frozen": "passed",
        "archived_record_self_consistent": "passed",
        "current_runtime_replay_compatible": "passed",
        "revision_2_differential_valid": "passed",
    }
    assert payload["limitations"][-1] == "public_holdout_observed"
    assert "public_holdout_not_observed" not in payload["limitations"]
    payload["immutable_inputs"][
        "benchmarks/retrieval/retrieval-eval-v1-baseline.json"
    ] = "0" * 64
    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module._validate_canonical_artifact(
            payload,
            protocol_path=protocol,
            repository_root=root,
            expected_authority=payload["canonical_authority"],
        )


@pytest.mark.parametrize(
    "fault",
    ("write", "file_fsync", "readback", "publish", "directory_fsync"),
)
def test_record_canonical_attempt_fault_never_starts_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    monkeypatch.setattr(
        module,
        "build_compatibility_artifact",
        _fail_replay,
    )
    _install_atomic_fault(monkeypatch, fault)

    result = module.record_canonical_compatibility(
        protocol_path=protocol,
        development_freeze_path=freeze,
        holdout_receipt_path=receipt,
        retrieval_artifact_path=retrieval_artifact,
        candidate_head=candidate_head,
        attempt_receipt_path=attempt,
        artifact_path=artifact,
        repository_root=root,
    )

    assert result["status"] == "failed"
    assert result["first_failed_gate"] == "attempt_publication"
    assert not artifact.exists()
    if fault == "directory_fsync":
        assert attempt.exists()
        assert result["output_state"] == "complete_visible"
        assert result["publication_outcome"] == "durability_unconfirmed"
    else:
        assert not attempt.exists()
        assert result["output_state"] == "absent"
        assert result["publication_outcome"] == "failed_before_visibility"


@pytest.mark.parametrize(
    "fault",
    ("write", "file_fsync", "readback", "publish", "directory_fsync"),
)
def test_record_canonical_output_fault_retains_attempt_and_closes_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    monkeypatch.setattr(
        module,
        "build_compatibility_artifact",
        _complete_compatibility_double,
    )
    monkeypatch.setattr(
        module,
        "validate_compatibility_artifact",
        _accept_validation,
    )
    original_publish = module.publish_json_no_replace
    calls = 0

    def publish(*args: object, **kwargs: object) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            _install_atomic_fault(monkeypatch, fault)
        return original_publish(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(module, "publish_json_no_replace", publish)

    result = module.record_canonical_compatibility(
        protocol_path=protocol,
        development_freeze_path=freeze,
        holdout_receipt_path=receipt,
        retrieval_artifact_path=retrieval_artifact,
        candidate_head=candidate_head,
        attempt_receipt_path=attempt,
        artifact_path=artifact,
        repository_root=root,
    )

    assert calls == 2
    assert attempt.exists()
    assert result["status"] == "failed"
    assert result["first_failed_gate"] == "compatibility_publication"
    if fault == "directory_fsync":
        assert artifact.exists()
        assert result["output_state"] == "complete_visible"
    else:
        assert not artifact.exists()
        assert result["output_state"] == "absent"
    second = module.record_canonical_compatibility(
        protocol_path=protocol,
        development_freeze_path=freeze,
        holdout_receipt_path=receipt,
        retrieval_artifact_path=retrieval_artifact,
        candidate_head=candidate_head,
        attempt_receipt_path=attempt,
        artifact_path=artifact,
        repository_root=root,
    )
    assert second["problem"] == (
        "retrieval_order_canonical_publication_already_started"
    )
    assert calls == 2


def _complete_compatibility_double(
    **kwargs: object,
) -> dict[str, object]:
    del kwargs
    return {
        "schema_version": "mke.retrieval_order_compatibility.v1",
        "protocol": {},
        "historical_capability": {},
        "current_source": {},
        "families": [],
        "integrity_status": "passed",
        "compatibility_status": "passed",
        "limitations": [
            "historical_compatibility_only",
            "tie_permutation_only",
            "no_relevance_improvement_claim",
            "no_runtime_promotion",
            "public_holdout_not_observed",
        ],
    }


def _install_atomic_fault(
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    if fault == "readback":
        monkeypatch.setattr(
            atomic_publication,
            "_readback_bytes",
            _invalid_readback,
        )
        return

    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise OSError("synthetic publication fault")

    monkeypatch.setattr(
        atomic_publication,
        {
            "write": "_write_bytes",
            "file_fsync": "_fsync_file",
            "publish": "_publish_no_replace",
            "directory_fsync": "_fsync_directory",
        }[fault],
        fail,
    )


def _synthetic_canonical_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, Path, Path, Path, str]:
    root = tmp_path / "canonical-synthetic-repository"
    for relative in IMMUTABLE_INPUT_SHA256:
        source = ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    fixture_root = root / "fixtures"
    fixture_root.mkdir(parents=True)
    payload = deepcopy(json.loads(PROTOCOL.read_text(encoding="utf-8")))
    partitions = payload["partitions"]
    for name in ("development", "holdout"):
        record = partitions[name]
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
        (
            "git",
            "add",
            "protocol.json",
            "fixtures",
            "benchmarks",
            "tests",
        ),
        ("git", "commit", "-qm", "synthetic authority"),
    )
    for command in commands:
        subprocess.run(command, cwd=root, check=True)
    output = root / "benchmarks/retrieval"
    freeze = output / "retrieval-order-v1-development-freeze.json"
    receipt = output / "retrieval-order-v1-holdout-receipt.json"
    retrieval_artifact = output / "retrieval-order-v1-artifact.json"
    monkeypatch.chdir(root)
    retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol,
        freeze_path=freeze,
        repository_root=root,
    )
    retrieval_order_workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol,
        development_freeze_path=freeze,
        receipt_path=receipt,
        artifact_path=retrieval_artifact,
        repository_root=root,
    )
    artifact_payload = json.loads(
        retrieval_artifact.read_text(encoding="utf-8")
    )
    return (
        root.resolve(),
        protocol.resolve(),
        freeze.resolve(),
        receipt.resolve(),
        retrieval_artifact.resolve(),
        artifact_payload["candidate_seal"]["head"],
    )
