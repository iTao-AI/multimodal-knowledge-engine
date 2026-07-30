from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.agent_context_unit_grading_protocol import (
    load_agent_context_unit_baseline_grading_payload,
    load_agent_context_unit_development_grading_payload,
    parse_agent_context_unit_development_grading_payload,
    portable_agent_context_unit_development_grading_payload,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/agent-context-unit-v2/protocol.json"


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {key: _plain(item) for key, item in mapping.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in cast(tuple[object, ...], value)]
    return value


def _copy_fixture_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    (repository / "src/mke").mkdir(parents=True)
    (repository / "pyproject.toml").write_text("[project]\nname='test'\n")
    target = repository / "tests/fixtures/agent-context-unit-v2"
    shutil.copytree(PROTOCOL.parent, target)
    return repository, target / "protocol.json"


def test_baseline_grading_loader_is_closed_and_development_only() -> None:
    payload = load_agent_context_unit_baseline_grading_payload(PROTOCOL)

    assert len(payload.required_spans) == 12
    assert {item.role for item in payload.required_spans} == {
        "answer",
        "boundary_context",
        "disambiguator",
    }
    assert not hasattr(
        importlib.import_module("mke.evaluation.agent_context_unit_grading_protocol"),
        "load_agent_context_unit_holdout_grading_payload",
    )


def test_grading_loader_rejects_holdout_label_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="development"):
        load_agent_context_unit_baseline_grading_payload(
            ROOT / "tests/fixtures/agent-context-unit-v2/holdout/labels.json"
        )


def test_grading_loader_rejects_symlinked_development_labels(
    tmp_path: Path,
) -> None:
    _repository, protocol = _copy_fixture_repository(tmp_path)
    labels = protocol.parent / "development/labels.json"
    retained = protocol.parent / "development/retained-labels.json"
    labels.rename(retained)
    labels.symlink_to(retained.name)

    with pytest.raises(ValueError, match="source identity path"):
        load_agent_context_unit_baseline_grading_payload(protocol)


def test_grading_loader_rejects_scientific_projection_drift(
    tmp_path: Path,
) -> None:
    _repository, protocol = _copy_fixture_repository(tmp_path)
    protocol_value = json.loads(protocol.read_bytes())
    reference = protocol_value["partitions"]["development"]["labels"]
    labels = protocol.parent.parent.parent.parent / reference["path"]
    value = json.loads(labels.read_bytes())
    value["required_spans"][0]["role"] = "drift"
    content = (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    labels.write_bytes(content)
    reference["bytes"] = len(content)
    reference["sha256"] = hashlib.sha256(content).hexdigest()
    protocol.write_text(
        json.dumps(
            protocol_value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )

    with pytest.raises(ValueError, match="scientific projection"):
        load_agent_context_unit_baseline_grading_payload(protocol)


def test_development_grading_payload_binds_frozen_rules_and_inventory() -> None:
    payload = load_agent_context_unit_development_grading_payload(PROTOCOL)
    lock = json.loads(
        (ROOT / "tests/fixtures/agent-context-unit-v2/scientific-input-lock.json").read_bytes()
    )

    assert payload.required_spans == (
        load_agent_context_unit_baseline_grading_payload(PROTOCOL).required_spans
    )
    assert payload.query_ids == tuple(lock["partitions"]["development"]["query_ids"])
    assert dict(payload.observation_ids_by_query) == {
        item["query_id"]: tuple(item["observation_ids"])
        for item in lock["partitions"]["development"]["observer_cases"]
    }
    assert payload.expected_routes_by_query["q-volcano-hazards"] == "fts5"
    assert payload.query_text_by_query["q-volcano-hazards"] == "volcano geologic hazards"
    assert payload.query_terms_by_query["q-volcano-hazards"] == (
        "volcano",
        "geologic",
        "hazards",
    )
    assert payload.rank_profiles_by_mechanism["fixed-rank-delivery-v1"] == (
        "deterministic-unit-rank-v1",
    )
    assert payload.control_query_kinds == {
        "q-current-success": "current_success",
        "q-exact-read-control": "exact_read",
        "q-hard-negative": "hard_negative",
        "q-misleading-name": "misleading_source_name",
        "q-tokenization-control": "tokenization_query_policy",
    }
    assert dict(payload.mechanism_ids) == lock["mechanism_profile"]["mechanism_ids"]
    assert _plain(payload.residual_gate_rules) == lock["residual_gate_rules"]
    assert _plain(payload.mechanism_verdict_rules) == lock["mechanism_verdict_rules"]
    assert payload.mechanism_verdict_revision == lock["mechanism_verdict_revision"]
    assert payload.stage_verdict_revision == lock["stage_verdict_revision"]
    assert payload.scientific_nonclaims == tuple(lock["scientific_nonclaims"])
    assert not hasattr(payload, "holdout")
    assert not hasattr(payload, "holdout_cases")


def test_development_grading_payload_uses_retained_protocol_authority(
    tmp_path: Path,
) -> None:
    _repository, protocol = _copy_fixture_repository(tmp_path)
    from mke.evaluation.agent_context_unit_protocol import (
        load_agent_context_unit_protocol_authority,
    )

    authority = load_agent_context_unit_protocol_authority(protocol)
    retained = load_agent_context_unit_development_grading_payload(authority)
    protocol.unlink()
    protocol.write_text("{}\n")

    assert load_agent_context_unit_development_grading_payload(authority) == retained


def test_development_grading_payload_rejects_unknown_verdict_rule(
    tmp_path: Path,
) -> None:
    _repository, protocol = _copy_fixture_repository(tmp_path)
    protocol_value = json.loads(protocol.read_bytes())
    lock_reference = protocol_value["scientific_input_lock"]
    lock_path = protocol.parent.parent.parent.parent / lock_reference["path"]
    lock = json.loads(lock_path.read_bytes())
    lock["residual_gate_rules"]["unexpected"] = True
    content = (
        json.dumps(lock, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    lock_path.write_bytes(content)
    lock_reference["bytes"] = len(content)
    lock_reference["sha256"] = hashlib.sha256(content).hexdigest()
    protocol.write_text(
        json.dumps(
            protocol_value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )

    with pytest.raises(ValueError, match="development grading rules"):
        load_agent_context_unit_development_grading_payload(protocol)


def test_development_grading_payload_deep_freezes_and_rejects_nested_rule_drift() -> None:
    payload = load_agent_context_unit_development_grading_payload(PROTOCOL)

    with pytest.raises(TypeError):
        payload.residual_gate_rules["o3_enabled_when"]["predicate"] = "forged"
    with pytest.raises(TypeError):
        payload.mechanism_verdict_rules["rank"]["strict_repair"] = "forged"

    forged_residual = _plain(payload.residual_gate_rules)
    assert isinstance(forged_residual, dict)
    cast(dict[str, object], forged_residual["o3_enabled_when"])["predicate"] = "forged"
    with pytest.raises(ValueError, match="development grading rules"):
        replace(payload, residual_gate_rules=forged_residual)

    forged_verdict = _plain(payload.mechanism_verdict_rules)
    assert isinstance(forged_verdict, dict)
    cast(dict[str, object], forged_verdict["rank"])["strict_repair"] = "forged"
    with pytest.raises(ValueError, match="development grading rules"):
        replace(payload, mechanism_verdict_rules=forged_verdict)


def test_development_grading_payload_portable_round_trip_is_exact() -> None:
    payload = load_agent_context_unit_development_grading_payload(PROTOCOL)
    portable = portable_agent_context_unit_development_grading_payload(payload)

    assert parse_agent_context_unit_development_grading_payload(portable) == payload
    cast(dict[str, object], portable["query_terms_by_query"])[
        "q-volcano-hazards"
    ] = ["forged"]
    with pytest.raises(ValueError, match="development grading rules"):
        parse_agent_context_unit_development_grading_payload(portable)
