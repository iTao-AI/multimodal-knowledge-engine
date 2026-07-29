from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/agent-context-unit-v2/protocol.json"
LOCK = ROOT / "tests/fixtures/agent-context-unit-v2/scientific-input-lock.json"


def _protocol_module():
    try:
        return importlib.import_module("mke.evaluation.agent_context_unit_protocol")
    except ModuleNotFoundError:
        pytest.fail("V2_PROTOCOL_MISSING")


def _copy_fixture_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    (repository / "src/mke").mkdir(parents=True)
    (repository / "pyproject.toml").write_text("[project]\nname='test'\n")
    target = repository / "tests/fixtures/agent-context-unit-v2"
    shutil.copytree(PROTOCOL.parent, target)
    return repository, target / "protocol.json"


def test_protocol_metadata_is_closed_and_matches_scientific_lock() -> None:
    module = _protocol_module()
    metadata = module.load_agent_context_unit_protocol_metadata(PROTOCOL)
    lock = json.loads(LOCK.read_text(encoding="utf-8"))

    assert metadata.schema_version == "mke.agent_context_unit_protocol.v2"
    assert metadata.candidate_profile == lock["candidate_profile"]
    assert metadata.projection_bounds == lock["projection_bounds"]
    assert metadata.runtime_profile_fields == tuple(lock["runtime_profile_fields"])
    assert metadata.mechanism_verdict_revision == lock["mechanism_verdict_revision"]
    assert metadata.stage_verdict_revision == lock["stage_verdict_revision"]
    assert len(metadata.partitions["development"].source_ids) == 7
    assert len(metadata.partitions["development"].query_ids) == 11
    assert len(metadata.partitions["holdout"].source_ids) == 2
    assert len(metadata.partitions["holdout"].query_ids) == 2


def test_protocol_rejects_scientific_lock_whitespace_identity_drift(
    tmp_path: Path,
) -> None:
    _repository, protocol = _copy_fixture_repository(tmp_path)
    lock = protocol.parent / "scientific-input-lock.json"
    lock.write_bytes(lock.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="scientific input lock identity"):
        _protocol_module().load_agent_context_unit_protocol_metadata(protocol)


def test_common_protocol_exposes_no_payload_or_label_loader() -> None:
    module = _protocol_module()
    names = set(dir(module))
    assert not any(
        token in name.lower()
        for name in names
        for token in ("label", "required_span", "observer_case", "holdout_payload")
    )
