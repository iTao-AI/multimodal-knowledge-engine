from __future__ import annotations

import importlib
import json
import os
import shutil
from pathlib import Path

import pytest

from mke.evaluation import source_identity

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


def test_protocol_rejects_final_and_component_symlink_authority(
    tmp_path: Path,
) -> None:
    repository, protocol = _copy_fixture_repository(tmp_path)
    retained = protocol.with_name("retained-protocol.json")
    protocol.rename(retained)
    protocol.symlink_to(retained.name)

    with pytest.raises(ValueError, match="source identity path"):
        _protocol_module().load_agent_context_unit_protocol_metadata(protocol)

    protocol.unlink()
    retained.rename(protocol)
    alias = repository / "fixture-alias"
    alias.symlink_to(protocol.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="source identity path"):
        _protocol_module().load_agent_context_unit_protocol_metadata(alias / "protocol.json")


def test_protocol_rejects_replacement_during_descriptor_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _repository, protocol = _copy_fixture_repository(tmp_path)
    original_read = source_identity.os.read
    replaced = False

    def replace_after_first_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        content = original_read(descriptor, size)
        if content and not replaced:
            retained = protocol.with_name("retained-protocol.json")
            protocol.rename(retained)
            protocol.write_bytes(content)
            replaced = True
        return content

    monkeypatch.setattr(source_identity.os, "read", replace_after_first_read)

    with pytest.raises(ValueError, match="changed during read"):
        _protocol_module().load_agent_context_unit_protocol_authority(protocol)

    assert replaced is True


@pytest.mark.parametrize(
    "target",
    (
        "candidate_profile",
        "projection_bounds",
        "runtime_profile_fields",
        "mechanism_verdict_revision",
        "stage_verdict_revision",
        "development_source_ids",
        "development_query_ids",
        "holdout_source_ids",
        "holdout_query_ids",
    ),
)
def test_protocol_rejects_scientific_projection_drift(
    tmp_path: Path,
    target: str,
) -> None:
    _repository, protocol = _copy_fixture_repository(tmp_path)
    value = json.loads(protocol.read_bytes())
    if target == "candidate_profile":
        value["candidate_profile"]["hard_page_boundary"] = False
    elif target == "projection_bounds":
        value["projection_bounds"]["max_pages"] += 1
    elif target == "runtime_profile_fields":
        value["runtime_profile_fields"] = list(
            reversed(value["runtime_profile_fields"])
        )
    elif target in {"mechanism_verdict_revision", "stage_verdict_revision"}:
        value[target] = f"sha256:{'0' * 64}"
    else:
        partition, field = target.split("_", 1)
        value["partitions"][partition][field].append("drift")
    protocol.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    )

    with pytest.raises(ValueError, match="scientific projection"):
        _protocol_module().load_agent_context_unit_protocol_metadata(protocol)


def test_retained_authority_reads_protocol_once_and_survives_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _repository, protocol = _copy_fixture_repository(tmp_path)
    module = _protocol_module()
    direct_read = module.read_no_follow_regular_file
    protocol_reads = 0

    def record_read(root: Path, relative: str):
        nonlocal protocol_reads
        if relative.endswith("/protocol.json"):
            protocol_reads += 1
        return direct_read(root, relative)

    monkeypatch.setattr(module, "read_no_follow_regular_file", record_read)
    authority = module.load_agent_context_unit_protocol_authority(protocol)
    original_sha256 = authority.protocol_read.identity["sha256"]
    replacement = protocol.with_name("replacement.json")
    replacement_value = json.loads(authority.protocol_read.content)
    replacement_value["candidate_profile"]["hard_page_boundary"] = False
    replacement.write_text(
        json.dumps(
            replacement_value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    os.replace(replacement, protocol)
    original_path_read = Path.read_bytes

    def reject_protocol_path_reopen(path: Path) -> bytes:
        if path == protocol:
            pytest.fail("PROTOCOL_PATH_REOPENED_AFTER_AUTHORITY_SNAPSHOT")
        return original_path_read(path)

    monkeypatch.setattr(Path, "read_bytes", reject_protocol_path_reopen)

    observer = importlib.import_module(
        "mke.evaluation.agent_context_unit_observer_protocol"
    ).load_agent_context_unit_observer_contract(authority)
    grading = importlib.import_module(
        "mke.evaluation.agent_context_unit_grading_protocol"
    ).load_agent_context_unit_baseline_grading_payload(authority)

    assert protocol_reads == 1
    assert authority.protocol_read.identity["sha256"] == original_sha256
    assert len(observer.sources) == 7
    assert len(grading.required_spans) == 12


def test_common_protocol_exposes_no_payload_or_label_loader() -> None:
    module = _protocol_module()
    names = set(dir(module))
    assert not any(
        token in name.lower()
        for name in names
        for token in ("label", "required_span", "observer_case", "holdout_payload")
    )
