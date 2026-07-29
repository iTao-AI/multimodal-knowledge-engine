from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from pathlib import Path

import pytest

from mke.evaluation.agent_context_unit_grading_protocol import (
    load_agent_context_unit_baseline_grading_payload,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/agent-context-unit-v2/protocol.json"


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
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
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
