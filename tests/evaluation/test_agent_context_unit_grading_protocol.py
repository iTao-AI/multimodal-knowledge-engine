from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from mke.evaluation.agent_context_unit_grading_protocol import (
    load_agent_context_unit_baseline_grading_payload,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/agent-context-unit-v2/protocol.json"


def test_baseline_grading_loader_is_closed_and_development_only() -> None:
    payload = load_agent_context_unit_baseline_grading_payload(PROTOCOL)

    assert len(payload.required_spans) == 12
    assert {item.role for item in payload.required_spans} == {
        "answer",
        "boundary_context",
        "disambiguator",
    }
    assert not hasattr(
        importlib.import_module(
            "mke.evaluation.agent_context_unit_grading_protocol"
        ),
        "load_agent_context_unit_holdout_grading_payload",
    )


def test_grading_loader_rejects_holdout_label_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="development"):
        load_agent_context_unit_baseline_grading_payload(
            ROOT / "tests/fixtures/agent-context-unit-v2/holdout/labels.json"
        )
