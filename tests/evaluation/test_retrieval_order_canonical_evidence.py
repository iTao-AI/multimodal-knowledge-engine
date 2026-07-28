from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import NoReturn, cast

import pytest

import mke.evaluation.retrieval_order_artifact as retrieval_artifact
import mke.evaluation.retrieval_order_compatibility as compatibility
import mke.evaluation.retrieval_order_workflow as workflow
from mke.evaluation import dense_artifact as dense_artifact_module
from mke.evaluation import hybrid_rrf_artifact as hybrid_rrf_artifact_module
from mke.evaluation import (
    relevance_gate_artifact as relevance_gate_artifact_module,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-order-v1/protocol.json"
CANONICAL_SHA256 = {
    "benchmarks/retrieval/retrieval-order-v1-development-freeze.json": (
        "0d8761037e9132461a1d6bbf2eac0a39471dfaa38c65acbdc2400a87ff8bffd8"
    ),
    "benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json": (
        "8f390ada3632c12527eb75747a2ce21721317fffdd30bd9fc177e8f305dc3203"
    ),
    "benchmarks/retrieval/retrieval-order-v1-artifact.json": (
        "104a41a6aa0c719313d508c79d00886a18483bbf3eeeadcdbc8899dd927283c1"
    ),
    "benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json": (
        "df18d9738548fa33af5c7f76dfa26e89a721f1c08a2df0e034a7688c67e81604"
    ),
    "benchmarks/retrieval/retrieval-order-v2-compatibility.json": (
        "f9a5883f3ac47652cbd18ef0bb08b61ceb00065955a3db575df0fd41689240ba"
    ),
}


def test_committed_canonical_retrieval_evidence_validates_purely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = {
        relative: ROOT / relative for relative in CANONICAL_SHA256
    }
    before = {
        relative: path.read_bytes() for relative, path in paths.items()
    }
    assert {
        relative: hashlib.sha256(content).hexdigest()
        for relative, content in before.items()
    } == CANONICAL_SHA256

    protocol_bytes = PROTOCOL.read_bytes()
    protocol = cast(dict[str, object], json.loads(protocol_bytes))
    retrieval = cast(
        dict[str, object],
        json.loads(
            before[
                "benchmarks/retrieval/retrieval-order-v1-artifact.json"
            ]
        ),
    )
    attempt = cast(
        dict[str, object],
        json.loads(
            before[
                "benchmarks/retrieval/"
                "retrieval-order-v2-compatibility-attempt.json"
            ]
        ),
    )
    compatibility_path = paths[
        "benchmarks/retrieval/retrieval-order-v2-compatibility.json"
    ]

    barrier_entries: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        barrier_entries.append("entered")
        raise AssertionError("canonical validation entered a side effect")

    monkeypatch.setattr(
        retrieval_artifact,
        "build_retrieval_order_artifact",
        forbidden,
    )
    monkeypatch.setattr(
        workflow,
        "observe_retrieval_order_partition",
        forbidden,
    )
    monkeypatch.setattr(
        workflow,
        "_run_development",
        forbidden,
    )
    monkeypatch.setattr(
        workflow,
        "_run_holdout",
        forbidden,
    )
    for name in (
        "build_compatibility_artifact",
        "record_temporary_compatibility",
        "record_canonical_compatibility",
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
        "_materialize_historical_inputs",
        "_run_historical_child",
        "publish_json_no_replace",
    ):
        monkeypatch.setattr(compatibility, name, forbidden)
    monkeypatch.setattr(
        compatibility.runner,
        "_observe_retrieval_evaluation",
        forbidden,
    )
    monkeypatch.setattr(
        dense_artifact_module,
        "build_dense_comparison_artifact",
        forbidden,
    )
    monkeypatch.setattr(
        hybrid_rrf_artifact_module,
        "run_hybrid_rrf_development",
        forbidden,
    )
    monkeypatch.setattr(
        relevance_gate_artifact_module,
        "run_relevance_gate_development",
        forbidden,
    )
    monkeypatch.setattr(
        relevance_gate_artifact_module,
        "build_relevance_gate_holdout_report",
        forbidden,
    )

    base_validation_calls = 0
    base_validator = compatibility.validate_compatibility_artifact
    attempt_validation_calls = 0
    attempt_validator = compatibility._validate_attempt_receipt  # pyright: ignore[reportPrivateUsage]

    def validate_base(
        artifact: object,
        *,
        protocol_path: Path,
        repository_root: Path,
    ) -> None:
        nonlocal base_validation_calls
        base_validation_calls += 1
        base_validator(
            artifact,
            protocol_path=protocol_path,
            repository_root=repository_root,
        )

    monkeypatch.setattr(
        compatibility,
        "validate_compatibility_artifact",
        validate_base,
    )

    def validate_attempt(
        value: object,
        *,
        expected: dict[str, object],
    ) -> None:
        nonlocal attempt_validation_calls
        attempt_validation_calls += 1
        attempt_validator(value, expected=expected)

    monkeypatch.setattr(
        compatibility,
        "_validate_attempt_receipt",
        validate_attempt,
    )

    validated_retrieval = (
        retrieval_artifact.validate_retrieval_order_artifact(
            retrieval,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )
    )
    assert validated_retrieval == retrieval
    result = compatibility.validate_temporary_compatibility(
        protocol_path=PROTOCOL,
        artifact_path=compatibility_path,
        repository_root=ROOT,
    )
    assert result == {
        "schema_version": (
            "mke.retrieval_order_compatibility_validate_result.v1"
        ),
        "status": "passed",
        "mode": "validate",
        "authority_layer": "artifact_validation",
        "canonical": True,
        "output_state": "complete_preexisting",
        "publication_outcome": "not_attempted",
        "problem": "none",
        "cause": "none",
        "next_step": "none",
        "first_failed_gate": "none",
        "stage_statuses": [
            {"name": "compatibility", "status": "passed"}
        ],
        "historical_revision": 1,
        "current_revision": 2,
    }
    assert base_validation_calls == 1
    assert attempt_validation_calls == 1

    assert set(attempt) == {
        "schema_version",
        "command_schema",
        "candidate_seal",
        "protocol_digest",
        "development_freeze_digest",
        "holdout_receipt_digest",
        "retrieval_artifact_digest",
        "compatibility_target",
    }
    assert attempt == {
        "schema_version": "mke.retrieval_order_compatibility_attempt.v1",
        "command_schema": (
            "mke.retrieval_order_compatibility_record_canonical.v1"
        ),
        "candidate_seal": retrieval["candidate_seal"],
        "protocol_digest": hashlib.sha256(protocol_bytes).hexdigest(),
        "development_freeze_digest": CANONICAL_SHA256[
            "benchmarks/retrieval/"
            "retrieval-order-v1-development-freeze.json"
        ],
        "holdout_receipt_digest": CANONICAL_SHA256[
            "benchmarks/retrieval/"
            "retrieval-order-v1-holdout-receipt.json"
        ],
        "retrieval_artifact_digest": CANONICAL_SHA256[
            "benchmarks/retrieval/retrieval-order-v1-artifact.json"
        ],
        "compatibility_target": (
            "benchmarks/retrieval/retrieval-order-v2-compatibility.json"
        ),
    }
    assert protocol["schema_version"] == "mke.retrieval_order_protocol.v1"
    assert barrier_entries == []

    after = {
        relative: path.read_bytes() for relative, path in paths.items()
    }
    assert after == before
    assert {
        relative: hashlib.sha256(content).hexdigest()
        for relative, content in after.items()
    } == CANONICAL_SHA256
