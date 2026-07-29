from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/agent-context-unit-v2/protocol.json"


def _observer_module():
    try:
        return importlib.import_module(
            "mke.evaluation.agent_context_unit_observer_protocol"
        )
    except ModuleNotFoundError:
        pytest.fail("V2_OBSERVER_PROTOCOL_MISSING")


def test_development_observer_contract_is_label_blind() -> None:
    module = _observer_module()
    contract = module.load_agent_context_unit_observer_contract(PROTOCOL)

    assert len(contract.sources) == 7
    assert len(contract.cases) == 11
    assert {case.runtime_route_profile for case in contract.cases} == {"fts5"}
    serialized = repr(contract).lower()
    for forbidden in (
        "required_span",
        "expected_locator",
        "qrel",
        "hypothesis",
        "verdict",
        "labels",
    ):
        assert forbidden not in serialized


def test_observer_module_cannot_import_grading_protocol() -> None:
    module = _observer_module()
    assert "agent_context_unit_grading_protocol" not in {
        value.__name__
        for value in vars(module).values()
        if isinstance(value, type(importlib))
    }
