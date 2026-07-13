from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.relevance_gate_protocol import (
    RelevanceGateProtocolError,
    build_relevance_gate_protocol_lock,
    load_relevance_gate_protocol_lock,
    render_relevance_gate_protocol_lock_json,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_LOCK = ROOT / "tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json"


def test_protocol_lock_is_byte_stable_and_checked_in() -> None:
    protocol = build_relevance_gate_protocol_lock(repository_root=ROOT)
    rendered = render_relevance_gate_protocol_lock_json(protocol)

    assert rendered.endswith("\n")
    assert json.loads(rendered) == protocol
    assert load_relevance_gate_protocol_lock(PROTOCOL_LOCK, repository_root=ROOT) == protocol


def test_protocol_freezes_candidate_inputs_and_profile_catalog() -> None:
    protocol = build_relevance_gate_protocol_lock(repository_root=ROOT)
    candidate = cast(dict[str, object], protocol["candidate"])
    inputs = cast(dict[str, dict[str, object]], protocol["inputs"])
    profiles = cast(list[dict[str, object]], protocol["profiles"])
    source_inventory = cast(dict[str, object], protocol["source_inventory"])

    assert protocol["schema_version"] == "mke.relevance_gate_protocol.v1"
    assert candidate == {
        "candidate_id": "cjk-relevance-gate-reranker-v1",
        "candidate_revision": 1,
    }
    assert inputs["dense_artifact"] == {
        "path": "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json",
        "bytes": 403821,
            "sha256": "ba8787b763b4454de740fe09416de65966c3109d8f65588b5331bdae342e98e5",
    }
    assert inputs["rrf_artifact"] == {
        "path": "benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json",
        "bytes": 117521,
            "sha256": "2dc96e732cab4cd46f4a6d586572379e5631a164af80da6cdf1d1cbf8fd638bf",
    }
    assert inputs["chinese_protocol"]["sha256"] == (
        "00f72934018a52b5b5f5591fba119050882aee9b782e5dac199702b0cf995944"
    )
    assert inputs["qrel_adjudication"]["sha256"] == (
        "b638a7729725d495e809bb52a93b071e65a51b0f0ebcb218d3ee3298a04bd0c4"
    )
    assert [profile["profile_id"] for profile in profiles] == [
        "lexical-floor",
        "balanced-constraint",
        "strict-constraint",
    ]
    assert all(profile["profile_revision"] == 1 for profile in profiles)
    assert set(inputs) == {
        "chinese_protocol",
        "qrel_adjudication",
        "dense_artifact",
        "rrf_artifact",
        "protocol_source",
        "metrics_source",
        "cli_source",
    }
    assert source_inventory == {
        "eval_only_modules": [
            "src/mke/evaluation/relevance_gate_features.py",
            "src/mke/evaluation/relevance_gate_candidate.py",
            "src/mke/evaluation/relevance_gate_workflow.py",
            "src/mke/evaluation/relevance_gate_artifact.py",
            "src/mke/evaluation/relevance_gate_protocol.py",
        ],
        "runtime_modules_changed": [],
    }


def test_protocol_rejects_bool_revision_unknown_profiles_and_missing_inventory(
    tmp_path: Path,
) -> None:
    protocol = build_relevance_gate_protocol_lock(repository_root=ROOT)

    mutations: tuple[tuple[Callable[[dict[str, object]], None], str], ...] = (
        (_mutate_revision_bool, "candidate"),
        (_mutate_unknown_profile, "profile"),
        (_mutate_extra_profile, "profile"),
        (_mutate_missing_source_inventory, "source inventory"),
    )
    for mutation, match in mutations:
        changed = _copy(protocol)
        mutation(changed)
        path = tmp_path / f"{match.replace(' ', '-')}.json"
        path.write_text(json.dumps(changed), encoding="utf-8")

        with pytest.raises(RelevanceGateProtocolError, match=match) as raised:
            load_relevance_gate_protocol_lock(path, repository_root=ROOT)

        assert raised.value.problem
        assert raised.value.cause
        assert raised.value.next_step


def test_protocol_rejects_absolute_paths_and_identity_drift(tmp_path: Path) -> None:
    protocol = build_relevance_gate_protocol_lock(repository_root=ROOT)

    changed = _copy(protocol)
    inputs = cast(dict[str, dict[str, object]], changed["inputs"])
    inputs["dense_artifact"]["path"] = str(
        ROOT / "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json"
    )
    path = tmp_path / "absolute.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(RelevanceGateProtocolError, match="repository path"):
        load_relevance_gate_protocol_lock(path, repository_root=ROOT)

    changed = _copy(protocol)
    inputs = cast(dict[str, dict[str, object]], changed["inputs"])
    inputs["rrf_artifact"]["sha256"] = "0" * 64
    path = tmp_path / "drift.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(RelevanceGateProtocolError, match="identity"):
        load_relevance_gate_protocol_lock(path, repository_root=ROOT)


def _copy(payload: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(payload)))


def _mutate_revision_bool(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["candidate"])["candidate_revision"] = True


def _mutate_unknown_profile(payload: dict[str, object]) -> None:
    profiles = cast(list[dict[str, object]], payload["profiles"])
    profiles[0]["profile_id"] = "query-aware-shortcut"


def _mutate_extra_profile(payload: dict[str, object]) -> None:
    profiles = cast(list[dict[str, object]], payload["profiles"])
    profiles.append({"profile_id": "extra", "profile_revision": 1})


def _mutate_missing_source_inventory(payload: dict[str, object]) -> None:
    del payload["source_inventory"]
