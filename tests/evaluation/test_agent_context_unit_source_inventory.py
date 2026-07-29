from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests/fixtures/agent-context-unit-v2"
LOCK = FIXTURE_ROOT / "scientific-input-lock.json"
EXPECTED_LOCK_SHA256 = (
    "c9f006e8d8dc32499f81a5f7d847707c3744d00ff1971437084347b8c9188fce"
)


def _protocol_module():
    try:
        return importlib.import_module("mke.evaluation.agent_context_unit_protocol")
    except ModuleNotFoundError:
        pytest.fail("V2_SOURCE_INVENTORY_MISSING")


def test_scientific_projection_is_exact_reviewed_authority() -> None:
    if not LOCK.exists():
        pytest.fail("V2_SCIENTIFIC_PROJECTION_MISSING")
    assert hashlib.sha256(LOCK.read_bytes()).hexdigest() == EXPECTED_LOCK_SHA256
    payload = json.loads(LOCK.read_text(encoding="utf-8"))
    assert len(payload["partitions"]["development"]["sources"]) == 7
    assert len(payload["partitions"]["development"]["observer_cases"]) == 11
    assert len(payload["partitions"]["development"]["required_spans"]) == 12
    assert len(payload["partitions"]["holdout"]["sources"]) == 2
    assert payload["partitions"]["holdout"]["required_spans"] == []


def test_source_inventory_is_sorted_unique_and_phase_closed() -> None:
    module = _protocol_module()
    metadata = module.load_agent_context_unit_protocol_metadata(
        FIXTURE_ROOT / "protocol.json"
    )
    assert metadata.o0_evaluator_paths == tuple(sorted(set(metadata.o0_evaluator_paths)))
    assert metadata.development_evaluator_paths == tuple(
        sorted(set(metadata.development_evaluator_paths))
    )
    assert set(metadata.o0_evaluator_paths) < set(metadata.development_evaluator_paths)


def test_holdout_metadata_does_not_open_holdout_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _protocol_module()
    opened: list[Path] = []
    original = Path.read_bytes

    def guarded(path: Path) -> bytes:
        if "holdout" in path.parts and path.name != "protocol.json":
            opened.append(path)
            pytest.fail("V2_HOLDOUT_METADATA_BARRIER_MISSING")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    metadata = module.load_agent_context_unit_protocol_metadata(
        FIXTURE_ROOT / "protocol.json"
    )
    assert metadata.partitions["holdout"].source_ids == (
        "holdout-usgs-manual",
        "holdout-prc-data-security",
    )
    assert opened == []
