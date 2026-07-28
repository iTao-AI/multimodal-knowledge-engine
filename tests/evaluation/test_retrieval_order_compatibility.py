from __future__ import annotations

import errno
import hashlib
import importlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, NoReturn

import fitz  # pyright: ignore[reportMissingTypeStubs]
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
H1_MISSING_ARCHIVED_INPUTS = (
    Path(".github/workflows/ci.yml"),
    Path("scripts/dense_retrieval_measurement.py"),
    Path(
        "benchmarks/retrieval/"
        "cjk-relevance-gate-reranker-v1-development-freeze.json"
    ),
    Path(
        "benchmarks/retrieval/"
        "cjk-relevance-gate-reranker-v1-holdout-receipt.json"
    ),
)
FROZEN_HISTORICAL_REPLAY_PROFILE = {
    "python": "3.13.12",
    "sqlite": "3.51.1",
    "pymupdf": "1.27.2.3",
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


def _live_historical_replay_profile() -> dict[str, str]:
    return {
        "python": ".".join(str(item) for item in sys.version_info[:3]),
        "sqlite": sqlite3.sqlite_version,
        "pymupdf": fitz.VersionBind,
    }


def _has_exact_historical_replay_profile(
    profile: Mapping[str, str],
) -> bool:
    return dict(profile) == FROZEN_HISTORICAL_REPLAY_PROFILE


def _require_exact_historical_replay_profile(
    profile: Mapping[str, str] | None = None,
) -> None:
    candidate = (
        _live_historical_replay_profile()
        if profile is None
        else profile
    )
    if not _has_exact_historical_replay_profile(candidate):
        pytest.skip(
            "exact historical replay not applicable: complete live "
            "Python/SQLite/PyMuPDF profile differs from the frozen profile"
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
    _require_exact_historical_replay_profile()
    return _module().build_compatibility_artifact(
        protocol_path=PROTOCOL,
        repository_root=ROOT,
        workspace=tmp_path_factory.mktemp("compatibility-authority"),
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("python", "0.0.0"),
        ("sqlite", "0.0.0"),
        ("pymupdf", "0.0.0"),
    ),
    ids=("python", "sqlite", "pymupdf"),
)
def test_historical_replay_profile_classifier_requires_complete_match(
    field: str,
    replacement: str,
) -> None:
    profile = dict(FROZEN_HISTORICAL_REPLAY_PROFILE)

    assert _has_exact_historical_replay_profile(profile)
    _require_exact_historical_replay_profile(profile)

    profile[field] = replacement

    assert not _has_exact_historical_replay_profile(profile)
    with pytest.raises(
        pytest.skip.Exception,
        match="complete live Python/SQLite/PyMuPDF profile differs",
    ):
        _require_exact_historical_replay_profile(profile)


def test_live_historical_replay_profile_uses_patch_and_library_versions() -> (
    None
):
    assert _live_historical_replay_profile() == {
        "python": ".".join(str(item) for item in sys.version_info[:3]),
        "sqlite": sqlite3.sqlite_version,
        "pymupdf": fitz.VersionBind,
    }


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
    _require_exact_historical_replay_profile()
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


@pytest.mark.parametrize(
    "field",
    ("python", "sqlite", "pymupdf"),
)
def test_historical_capability_downgrades_complete_runtime_profile_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    module = _module()
    mismatched = dict(FROZEN_HISTORICAL_REPLAY_PROFILE)
    mismatched[field] = "0.0.0"
    monkeypatch.setattr(module, "_RUNTIME_PROFILE", mismatched)

    capability = module.freeze_historical_capabilities(
        repository_root=ROOT,
        workspace=tmp_path / field,
    )

    assert not _has_exact_historical_replay_profile(mismatched)
    assert capability.status == "no_ordered_delta_authority"
    assert capability.first_stdout == ""
    assert capability.second_stdout == ""
    assert capability.module_origins_valid is False
    assert capability.input_identities_valid is False
    table = module.family_capability_table(
        historical_capability=capability
    )
    assert tuple(item.tie_group_authority for item in table[:2]) == (
        "no_ordered_delta_authority",
        "no_ordered_delta_authority",
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


def test_historical_authority_is_complete_before_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    actions: list[str] = []

    def reject_archived(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        actions.append("archived")
        raise module.RetrievalOrderCompatibilityError

    def materialize(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        actions.append("materialize")
        raise AssertionError("materialization must not start")

    monkeypatch.setattr(
        module,
        "_validate_all_archived_authority",
        reject_archived,
    )
    monkeypatch.setattr(module, "_materialize_historical_source", materialize)
    monkeypatch.setattr(module, "_materialize_historical_inputs", materialize)
    monkeypatch.setattr(module, "_run_historical_child", materialize)

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module.freeze_historical_capabilities(
            repository_root=ROOT,
            workspace=tmp_path,
        )

    assert actions == ["archived"]


def test_compatibility_rejects_lexical_repository_root_symlink_before_any_authority_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    alias = tmp_path / "repository-alias"
    alias.symlink_to(root, target_is_directory=True)
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    reads: list[str] = []

    def reject_load(path: Path) -> NoReturn:
        reads.append(f"load:{path.name}")
        raise module.RetrievalOrderCompatibilityError

    def reject_metadata(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        reads.append("metadata")
        raise module.RetrievalOrderCompatibilityError

    monkeypatch.setattr(module, "_load_object", reject_load)
    monkeypatch.setattr(
        module,
        "load_retrieval_order_protocol_metadata",
        reject_metadata,
    )
    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module.freeze_historical_capabilities(
            repository_root=alias,
            workspace=tmp_path / "historical-workspace",
        )
    result = module.record_canonical_compatibility(
        protocol_path=protocol,
        development_freeze_path=freeze,
        holdout_receipt_path=receipt,
        retrieval_artifact_path=retrieval_artifact,
        candidate_head=candidate_head,
        attempt_receipt_path=attempt,
        artifact_path=artifact,
        repository_root=alias,
    )

    assert reads == [], "G2_LEXICAL_ROOT_ALIAS_FALSE_PASS"
    _assert_canonical_path_preflight_failure(result)
    assert not attempt.exists()
    assert not artifact.exists()


def test_compatibility_preflights_complete_immutable_inventory_before_digest(
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
    invalid = root / tuple(module._IMMUTABLE_INPUT_SHA256)[-1]
    invalid.unlink()
    invalid.mkdir()
    _install_g2_candidate_seal(
        monkeypatch,
        root=root,
        retrieval_artifact=retrieval_artifact,
    )
    digests: list[Path] = []
    original_sha256 = module._sha256

    def sha256(path: Path) -> str:
        digests.append(path)
        return original_sha256(path)

    monkeypatch.setattr(module, "_sha256", sha256)

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

    assert digests == [], "G2_IMMUTABLE_BATCH_PREFLIGHT_INCOMPLETE"
    _assert_canonical_path_preflight_failure(result)
    assert not attempt.exists()
    assert not artifact.exists()


def test_compatibility_preflights_current_source_inventory_before_source_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    root = tmp_path / "source-repository"
    source = root / "src/mke"
    outside = tmp_path / "outside-source"
    source.mkdir(parents=True)
    outside.mkdir()
    (source / "valid.py").write_text("VALID = True\n", encoding="utf-8")
    (outside / "aliased.py").write_text("ALIASED = True\n", encoding="utf-8")
    (source / "aliased.py").symlink_to(outside / "aliased.py")
    (source / "aliased-package").symlink_to(
        outside,
        target_is_directory=True,
    )
    build_calls: list[tuple[str, ...]] = []

    def build(
        repository_root: Path,
        paths: tuple[str, ...],
    ) -> dict[str, object]:
        del repository_root
        build_calls.append(paths)
        return {"sha256": "0" * 64, "files": []}

    monkeypatch.setattr(module, "build_source_identity", build)
    rejected = False
    try:
        module._current_source_identity(root)
    except module.RetrievalOrderCompatibilityError:
        rejected = True

    assert rejected and build_calls == [], (
        "G2_CURRENT_SOURCE_PREFLIGHT_INCOMPLETE"
    )


@pytest.mark.parametrize(
    "failure",
    ("missing-root", "empty-root", "nested-scan-error"),
)
def test_current_source_inventory_rejects_incomplete_tree_before_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    module = _module()
    root = tmp_path / "source-repository"
    source = root / "src/mke"
    source.mkdir(parents=True)
    (source / "visible.py").write_text("VISIBLE = True\n", encoding="utf-8")
    blocked = source / "blocked"
    blocked.mkdir()
    (blocked / "hidden.py").write_text("HIDDEN = True\n", encoding="utf-8")
    if failure == "missing-root":
        shutil.rmtree(source)
    elif failure == "empty-root":
        shutil.rmtree(source)
        source.mkdir()
    else:
        original_scandir = module.os.scandir

        def scandir(path: Any) -> Any:
            if Path(path) == blocked:
                raise PermissionError("synthetic nested scan failure")
            return original_scandir(path)

        monkeypatch.setattr(module.os, "scandir", scandir)
    build_calls: list[tuple[str, ...]] = []

    def build(
        repository_root: Path,
        paths: tuple[str, ...],
    ) -> dict[str, object]:
        del repository_root
        build_calls.append(paths)
        return {"sha256": "0" * 64, "files": []}

    monkeypatch.setattr(module, "build_source_identity", build)
    rejected = False
    try:
        module._current_source_identity(root)
    except module.RetrievalOrderCompatibilityError:
        rejected = True

    assert rejected and build_calls == [], (
        "G2_REVIEW_CURRENT_SOURCE_INVENTORY_FALSE_PASS"
    )


def test_current_source_inventory_binds_exact_sorted_recursive_python_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    root = tmp_path / "source-repository"
    source = root / "src/mke"
    (source / "nested").mkdir(parents=True)
    (source / "z.py").write_text("Z = True\n", encoding="utf-8")
    (source / "nested/a.py").write_text("A = True\n", encoding="utf-8")
    (source / "nested/ignored.txt").write_text("ignored\n", encoding="utf-8")
    observed: list[tuple[str, ...]] = []

    def build(
        repository_root: Path,
        paths: tuple[str, ...],
    ) -> dict[str, object]:
        assert repository_root == root
        observed.append(paths)
        return {"sha256": "0" * 64, "files": []}

    monkeypatch.setattr(module, "build_source_identity", build)
    module._current_source_identity(root)

    assert observed == [
        ("src/mke/nested/a.py", "src/mke/z.py")
    ]


def test_current_source_inventory_rejects_existing_empty_tree_before_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    root = tmp_path / "source-repository"
    (root / "src/mke").mkdir(parents=True)
    calls: list[str] = []

    def build(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        calls.append("identity")
        raise AssertionError("identity must not start")

    monkeypatch.setattr(module, "build_source_identity", build)
    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module._current_source_identity(root)
    assert calls == []


@pytest.mark.parametrize(
    "failure",
    ("missing-root", "empty-root", "nested-scan-error"),
)
def test_canonical_current_source_inventory_failure_is_path_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    source = root / "src/mke"
    blocked = source / "blocked"
    blocked.mkdir()
    (blocked / "hidden.py").write_text("HIDDEN = True\n", encoding="utf-8")
    if failure == "missing-root":
        shutil.rmtree(source)
    elif failure == "empty-root":
        shutil.rmtree(source)
        source.mkdir()
    else:
        original_scandir = module.os.scandir

        def scandir(path: Any) -> Any:
            if Path(path) == blocked:
                raise PermissionError("synthetic nested scan failure")
            return original_scandir(path)

        monkeypatch.setattr(module.os, "scandir", scandir)
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    _install_g2_candidate_seal(
        monkeypatch,
        root=root,
        retrieval_artifact=retrieval_artifact,
    )
    consumers: list[str] = []

    def consume(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        consumers.append("called")
        raise AssertionError("content or publication must not start")

    monkeypatch.setattr(
        module,
        "load_retrieval_order_protocol_metadata",
        consume,
    )
    monkeypatch.setattr(module, "build_source_identity", consume)
    monkeypatch.setattr(module, "publish_json_no_replace", consume)
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

    assert consumers == [], (
        "G2_REVIEW_CANONICAL_SOURCE_INVENTORY_FALSE_PASS"
    )
    _assert_canonical_path_preflight_failure(result)
    assert not attempt.exists()
    assert not artifact.exists()


def test_compatibility_preflights_archived_inputs_before_loader_or_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root = authority[0]
    protocol = root / module._NUMERIC_PROTOCOL
    outside = tmp_path / "outside-numeric-protocol.json"
    outside.write_bytes(protocol.read_bytes())
    protocol.unlink()
    protocol.symlink_to(outside)
    consumers: list[str] = []
    original_load = module._load_object
    original_file_identity = module._file_identity
    original_numeric_loader = (
        module.numeric_comparison.load_archived_numeric_protocol
    )

    def load(path: Path) -> dict[str, object]:
        consumers.append("_load_object")
        return original_load(path)

    def file_identity(
        repository_root: Path,
        path: Path,
    ) -> dict[str, object]:
        consumers.append("_file_identity")
        return original_file_identity(repository_root, path)

    def numeric_loader(*args: object, **kwargs: object) -> object:
        consumers.append("load_archived_numeric_protocol")
        return original_numeric_loader(*args, **kwargs)

    def e1_validator(repository_root: Path) -> None:
        del repository_root
        consumers.append("_validate_archived_e1")

    def wrap(
        name: str,
        original: Callable[..., object],
    ) -> Callable[..., object]:
        def wrapped(*args: object, **kwargs: object) -> object:
            consumers.append(name)
            return original(*args, **kwargs)

        return wrapped

    monkeypatch.setattr(module, "_load_object", load)
    monkeypatch.setattr(module, "_file_identity", file_identity)
    monkeypatch.setattr(
        module.numeric_comparison,
        "load_archived_numeric_protocol",
        numeric_loader,
    )
    monkeypatch.setattr(module, "_validate_archived_e1", e1_validator)
    for name in (
        "_validate_archived_e2",
        "_validate_archived_e3a",
        "_validate_archived_e3b",
        "_e3c_family",
        "_e3d_family",
        "_e3e_family",
        "validate_dense_comparison_artifact",
        "validate_hybrid_rrf_artifact",
        "validate_relevance_gate_artifact",
    ):
        monkeypatch.setattr(module, name, wrap(name, getattr(module, name)))
    try:
        module._validate_all_archived_authority(root)
    except module.RetrievalOrderCompatibilityError:
        pass

    assert consumers == [], "G2_ARCHIVED_INPUT_PREFLIGHT_INCOMPLETE"


def test_historical_dynamic_inputs_are_preflighted_before_any_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    root = _synthetic_canonical_authority(tmp_path, monkeypatch)[0]
    manifest = json.loads((root / module._E1_MANIFEST).read_text())
    relative = Path(manifest["documents"][0]["primary_file"]["path"])
    dynamic = root / module._E1_MANIFEST.parent / relative
    dynamic.parent.mkdir(parents=True, exist_ok=True)
    dynamic.unlink()
    dynamic.symlink_to(tmp_path / "outside-dynamic.pdf")
    calls: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        calls.append("consumer")
        raise AssertionError("validator must not start")

    for name in (
        "_validate_archived_e1",
        "_validate_archived_e2",
        "_validate_archived_e3a",
        "_validate_archived_e3b",
        "_e3c_family",
        "_e3d_family",
        "_e3e_family",
    ):
        monkeypatch.setattr(module, name, forbidden)
    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module._validate_all_archived_authority(root)

    assert calls == [], "G4_DYNAMIC_HISTORICAL_PREFLIGHT_FALSE_PASS"


def test_archived_validator_repository_reads_require_prior_batch_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    preflighted: set[Path] = set()
    original_preflight = module._preflight_repository_files
    original_open = Path.open

    def record_preflight(
        repository_root: Path,
        paths: tuple[Path, ...],
    ) -> None:
        original_preflight(repository_root, paths)
        root = repository_root.absolute()
        for path in paths:
            candidate = path if path.is_absolute() else root / path
            if candidate.is_file() and not candidate.is_symlink():
                preflighted.add(candidate.absolute())

    def guarded_open(
        path: Path,
        *args: object,
        **kwargs: object,
    ) -> Any:
        candidate = path.absolute()
        if (
            candidate.is_relative_to(ROOT.absolute())
            and candidate.is_file()
            and candidate not in preflighted
        ):
            pytest.fail("H1_VALIDATOR_READ_BEFORE_PREFLIGHT")
        return original_open(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        module,
        "_preflight_repository_files",
        record_preflight,
    )
    monkeypatch.setattr(Path, "open", guarded_open)

    module._validate_all_archived_authority(ROOT)

    assert set(H1_MISSING_ARCHIVED_INPUTS).issubset(
        {path.relative_to(ROOT) for path in preflighted}
    )


@pytest.mark.parametrize(
    ("relative", "path_kind"),
    (
        pytest.param(
            H1_MISSING_ARCHIVED_INPUTS[0],
            "symlink",
            id="ci-symlink",
        ),
        pytest.param(
            H1_MISSING_ARCHIVED_INPUTS[0],
            "nonregular",
            id="ci-nonregular",
        ),
        pytest.param(
            H1_MISSING_ARCHIVED_INPUTS[1],
            "symlink",
            id="dense-script-symlink",
        ),
        pytest.param(
            H1_MISSING_ARCHIVED_INPUTS[1],
            "nonregular",
            id="dense-script-nonregular",
        ),
        pytest.param(
            H1_MISSING_ARCHIVED_INPUTS[2],
            "symlink",
            id="relevance-freeze-symlink",
        ),
        pytest.param(
            H1_MISSING_ARCHIVED_INPUTS[2],
            "nonregular",
            id="relevance-freeze-nonregular",
        ),
        pytest.param(
            H1_MISSING_ARCHIVED_INPUTS[3],
            "symlink",
            id="relevance-receipt-symlink",
        ),
        pytest.param(
            H1_MISSING_ARCHIVED_INPUTS[3],
            "nonregular",
            id="relevance-receipt-nonregular",
        ),
    ),
)
def test_canonical_archived_validator_input_kind_fails_before_consumer_or_visibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: Path,
    path_kind: str,
) -> None:
    module = _module()

    def mutate_authority(root: Path) -> None:
        selected = root / relative
        retained = selected.with_name(f"{selected.name}.retained")
        if path_kind == "symlink":
            selected.rename(retained)
            selected.symlink_to(retained.name)
        else:
            selected.unlink()
            selected.mkdir()
            subprocess.run(("git", "init", "-q"), cwd=selected, check=True)
            subprocess.run(
                (
                    "git",
                    "config",
                    "user.email",
                    "synthetic@example.invalid",
                ),
                cwd=selected,
                check=True,
            )
            subprocess.run(
                (
                    "git",
                    "config",
                    "user.name",
                    "Synthetic Authority",
                ),
                cwd=selected,
                check=True,
            )
            (selected / "retained.txt").write_text(
                "synthetic nonregular authority\n",
                encoding="utf-8",
            )
            subprocess.run(
                ("git", "add", "retained.txt"),
                cwd=selected,
                check=True,
            )
            subprocess.run(
                ("git", "commit", "-qm", "nested authority"),
                cwd=selected,
                check=True,
            )
            assert (
                subprocess.check_output(
                    ("git", "status", "--porcelain=v1", "-z"),
                    cwd=selected,
                )
                == b""
            )
        subprocess.run(("git", "add", "--all"), cwd=root, check=True)
        subprocess.run(
            ("git", "commit", "-qm", f"replace {relative.as_posix()}"),
            cwd=root,
            check=True,
        )

    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        _synthetic_canonical_authority(
            tmp_path,
            monkeypatch,
            pre_observation_mutation=mutate_authority,
        )
    )
    retained_artifact = json.loads(
        retrieval_artifact.read_text(encoding="utf-8")
    )
    expected_status = {
        freeze: "??",
        receipt: "??",
        retrieval_artifact: "??",
    }
    candidate = retrieval_order_workflow._candidate_seal(  # pyright: ignore[reportPrivateUsage]
        root,
        expected_status=expected_status,
    )
    candidate_authority_passed = (
        candidate["head"]
        == retained_artifact["candidate_seal"]["head"]
        == candidate_head
        and candidate["runtime_profile"]
        == retained_artifact["candidate_seal"]["runtime_profile"]
        and candidate["status_records"]
        == tuple(
            sorted(
                (
                    status,
                    path.relative_to(root).as_posix(),
                    None,
                )
                for path, status in expected_status.items()
            )
        )
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    calls: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        calls.append("consumer")
        raise AssertionError("historical consumer must not start")

    monkeypatch.setattr(
        module,
        "_validate_all_archived_authority",
        forbidden,
    )
    monkeypatch.setattr(module, "_sha256", forbidden)
    monkeypatch.setattr(module, "_materialize_historical_source", forbidden)
    monkeypatch.setattr(module, "_materialize_historical_inputs", forbidden)
    monkeypatch.setattr(module, "_run_historical_child", forbidden)
    monkeypatch.setattr(module, "publish_json_no_replace", forbidden)

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

    assert candidate_authority_passed
    assert calls == [], "H1_HISTORICAL_INPUT_PATH_PREFLIGHT_INCOMPLETE"
    _assert_canonical_path_preflight_failure(result)
    assert not os.path.lexists(attempt)
    assert not os.path.lexists(artifact)


def test_canonical_dynamic_input_alias_is_path_preflight_before_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    root, protocol, freeze, receipt, retrieval_artifact, _ = (
        _synthetic_canonical_authority(tmp_path, monkeypatch)
    )
    manifest = json.loads((root / module._E1_MANIFEST).read_text())
    relative = Path(manifest["documents"][0]["primary_file"]["path"])
    dynamic = root / module._E1_MANIFEST.parent / relative
    retained = dynamic.with_suffix(".retained.pdf")
    dynamic.rename(retained)
    dynamic.symlink_to(retained)
    subprocess.run(("git", "add", "--all"), cwd=root, check=True)
    subprocess.run(
        ("git", "commit", "-qm", "retarget dynamic input"),
        cwd=root,
        check=True,
    )
    candidate_head = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    calls: list[str] = []
    retained_artifact = json.loads(retrieval_artifact.read_text())

    def candidate(
        repository_root: Path,
        *,
        expected_status: dict[Path, str],
    ) -> dict[str, object]:
        del repository_root, expected_status
        return {
            "head": candidate_head,
            "runtime_profile": retained_artifact["candidate_seal"][
                "runtime_profile"
            ],
            "status_records": (),
        }

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        calls.append("consumer")
        raise AssertionError("consumer must not start")

    monkeypatch.setattr(module, "_validate_all_archived_authority", forbidden)
    monkeypatch.setattr(module, "publish_json_no_replace", forbidden)
    monkeypatch.setattr(
        retrieval_order_workflow,
        "_candidate_seal",
        candidate,
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

    _assert_canonical_path_preflight_failure(result)
    assert calls == []
    assert not attempt.exists()
    assert not artifact.exists()


def test_compatibility_preflights_manifest_sources_before_copy_or_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    root = tmp_path / "manifest-repository"
    destination = tmp_path / "historical-repository"
    shutil.copytree(ROOT / "tests/fixtures", root / "tests/fixtures")
    source: dict[str, object] = {"files": []}
    source_paths, input_paths = module._historical_materialization_plan(
        root,
        destination,
        source,
    )
    assert source_paths == ()
    candidates = [
        path
        for path in input_paths
        if path not in {Path("pyproject.toml"), Path("uv.lock")}
        and (root / path).is_file()
    ]
    victim = max(candidates, key=lambda path: path.as_posix())
    victim_path = root / victim
    victim_path.unlink()
    victim_path.mkdir()
    copies: list[Path] = []
    original_copy = module.shutil.copyfile

    def copy(source_path: Path, destination_path: Path) -> Path:
        copies.append(source_path)
        return original_copy(source_path, destination_path)

    def git(*args: object) -> bytes:
        del args
        return b"historical\n"

    monkeypatch.setattr(module.shutil, "copyfile", copy)
    monkeypatch.setattr(module, "_git", git)
    rejected = False
    try:
        module._materialize_historical_inputs(
            root,
            destination,
            relative_paths=input_paths,
        )
    except module.RetrievalOrderCompatibilityError:
        rejected = True

    assert rejected and copies == [], (
        "G2_MANIFEST_SOURCE_PREFLIGHT_INCOMPLETE"
    )


def test_compatibility_rejects_final_parent_and_lstat_failures_before_side_effects(
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
    _install_g2_candidate_seal(
        monkeypatch,
        root=root,
        retrieval_artifact=retrieval_artifact,
    )
    real_parent = root / "protocol-parent-real"
    real_parent.mkdir()
    nested_protocol = real_parent / "protocol.json"
    nested_protocol.write_bytes(protocol.read_bytes())
    alias_parent = root / "protocol-parent"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    parent_result = module.record_canonical_compatibility(
        protocol_path=alias_parent / "protocol.json",
        development_freeze_path=freeze,
        holdout_receipt_path=receipt,
        retrieval_artifact_path=retrieval_artifact,
        candidate_head=candidate_head,
        attempt_receipt_path=attempt,
        artifact_path=artifact,
        repository_root=root,
    )
    _assert_canonical_path_preflight_failure(parent_result)

    metadata_calls = 0

    def metadata(*args: object, **kwargs: object) -> NoReturn:
        nonlocal metadata_calls
        del args, kwargs
        metadata_calls += 1
        raise module.RetrievalOrderCompatibilityError

    original_lstat = Path.lstat

    def lstat(path: Path):
        if path == protocol:
            raise FileNotFoundError(
                errno.ENOENT,
                "synthetic lstat failure",
                str(path),
            )
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(
        module,
        "load_retrieval_order_protocol_metadata",
        metadata,
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

    assert metadata_calls == 0, "G2_PATH_KIND_OR_LSTAT_FALSE_PASS"
    _assert_canonical_path_preflight_failure(result)
    assert not attempt.exists()
    assert not artifact.exists()


def test_canonical_path_preflight_preserves_public_tuple_and_zero_visibility(
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
    invalid = root / tuple(module._IMMUTABLE_INPUT_SHA256)[-2]
    invalid.unlink()
    invalid.mkdir()
    _install_g2_candidate_seal(
        monkeypatch,
        root=root,
        retrieval_artifact=retrieval_artifact,
    )
    side_effects: list[str] = []

    def side_effect(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        side_effects.append("called")
        raise AssertionError("side effect must not start")

    monkeypatch.setattr(module, "build_compatibility_artifact", side_effect)
    monkeypatch.setattr(module, "publish_json_no_replace", side_effect)

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

    assert (
        result["status"] == "failed"
        and result["mode"] == "record_canonical"
        and result["output_state"] == "not_applicable"
        and result["publication_outcome"] == "not_attempted"
        and result["problem"]
        == "retrieval_order_canonical_publication_unauthorized"
        and result["cause"] == "canonical_path_preflight_failed"
        and result["next_step"]
        == "correct_canonical_paths_before_first_attempt"
        and result["first_failed_gate"] == "path_preflight"
        and side_effects == []
        and not attempt.exists()
        and not artifact.exists()
    ), "G2_PUBLIC_TUPLE_OR_VISIBILITY_DRIFT"


@pytest.mark.parametrize(
    "relative",
    (
        "",
        ".",
        "..",
        "/absolute",
        "src//mke/file.py",
        "src/./mke/file.py",
        "src/mke/../file.py",
        r"src\mke\file.py",
        "C:/src/mke/file.py",
    ),
)
def test_historical_materialization_rejects_noncanonical_paths_before_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
) -> None:
    module = _module()
    actions: list[str] = []

    def git_action(*args: object, **kwargs: object) -> None:
        del args, kwargs
        actions.append("git")

    def copy_action(*args: object, **kwargs: object) -> None:
        del args, kwargs
        actions.append("copy")

    monkeypatch.setattr(
        module,
        "_git",
        git_action,
    )
    monkeypatch.setattr(
        module.shutil,
        "copyfile",
        copy_action,
    )

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module._validate_materialization_path(
            relative,
            source_root=tmp_path / "repository",
            scratch_root=tmp_path / "scratch",
        )

    assert actions == []


@pytest.mark.parametrize(
    "location",
    ("source", "source_parent", "scratch_parent"),
)
def test_historical_materialization_rejects_symlinked_paths_before_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    location: str,
) -> None:
    module = _module()
    source_root = tmp_path / "repository"
    scratch_root = tmp_path / "scratch"
    outside = tmp_path / "outside"
    outside.mkdir()
    source_root.mkdir()
    scratch_root.mkdir()
    if location == "source":
        (source_root / "file.json").symlink_to(outside / "file.json")
        relative = "file.json"
    elif location == "source_parent":
        (source_root / "nested").symlink_to(outside)
        relative = "nested/file.json"
    else:
        (scratch_root / "nested").symlink_to(outside)
        relative = "nested/file.json"
    actions: list[str] = []

    def action(*args: object, **kwargs: object) -> None:
        del args, kwargs
        actions.append("action")

    monkeypatch.setattr(module, "_git", action)
    monkeypatch.setattr(module.shutil, "copyfile", action)

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module._validate_materialization_path(
            relative,
            source_root=source_root,
            scratch_root=scratch_root,
        )

    assert actions == []


def test_compatibility_artifact_exposes_complete_family_differentials(
    tmp_path: Path,
) -> None:
    _require_exact_historical_replay_profile()
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
    _require_exact_historical_replay_profile()
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
    _require_exact_historical_replay_profile()
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


def test_strict_live_validator_rejects_future_current_source_mismatch(
    compatibility_artifact: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    calls = 0

    def future_current_source(root: Path) -> dict[str, object]:
        nonlocal calls
        assert root == ROOT
        calls += 1
        return {
            "files": [
                {
                    "path": "src/mke/unrelated_future.py",
                    "bytes": 17,
                    "sha256": "0" * 64,
                }
            ],
            "sha256": "0" * 64,
        }

    monkeypatch.setattr(
        module,
        "_current_source_identity",
        future_current_source,
    )

    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module.validate_compatibility_artifact(
            compatibility_artifact,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )

    assert calls == 1


def test_temporary_record_and_read_only_validate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _require_exact_historical_replay_profile()
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


@pytest.mark.parametrize("initial_state", ("absent", "preexisting"))
def test_record_rejects_canonical_path_before_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    initial_state: str,
) -> None:
    module = _module()
    root = tmp_path / "repository"
    root.mkdir()
    canonical = root / module._CANONICAL_ARTIFACT
    sentinel = b"published canonical compatibility sentinel\n"
    before: tuple[int, int, int, int, int, int] | None = None
    if initial_state == "preexisting":
        canonical.parent.mkdir(parents=True)
        canonical.write_bytes(sentinel)
        canonical.chmod(0o640)
        metadata = canonical.stat()
        before = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )
    else:
        assert not os.path.lexists(canonical)
    _block_all_replay(monkeypatch, module)

    assert module.main(
        [
            "record",
            "--protocol",
            "protocol.json",
            "--artifact",
            module._CANONICAL_ARTIFACT.as_posix(),
            "--repository",
            str(root),
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
    assert str(tmp_path) not in capture.out
    assert all(
        not value.startswith("/")
        for value in output.values()
        if isinstance(value, str)
    )
    if before is None:
        assert not os.path.lexists(canonical)
    else:
        metadata = canonical.stat()
        assert (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        ) == before
        assert canonical.read_bytes() == sentinel


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

    with pytest.raises(SystemExit) as canonical_help:
        module.main(["record-canonical", "--help"])

    assert canonical_help.value.code == 0
    canonical_output = capsys.readouterr().out
    assert (
        "preflight rejected -> not attempted; correct the input before any "
        "attempt"
    ) in canonical_output
    assert (
        "attempt visible -> terminal; retain the attempt and stop"
    ) in canonical_output


def test_record_canonical_cli_preserves_lexical_repository_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()
    (
        root,
        _protocol,
        _freeze,
        _receipt,
        _retrieval_artifact,
        candidate_head,
    ) = _synthetic_canonical_authority(tmp_path, monkeypatch)
    alias = tmp_path / "repository-alias"
    alias.symlink_to(root, target_is_directory=True)
    candidate_calls = 0

    def candidate(*args: object, **kwargs: object) -> NoReturn:
        nonlocal candidate_calls
        del args, kwargs
        candidate_calls += 1
        raise AssertionError("candidate seal must not start")

    monkeypatch.setattr(
        retrieval_order_workflow,
        "_candidate_seal",
        candidate,
    )
    assert module.main(
        [
            "record-canonical",
            "--protocol",
            "protocol.json",
            "--development-freeze",
            module._CANONICAL_DEVELOPMENT_FREEZE.as_posix(),
            "--holdout-receipt",
            module._CANONICAL_HOLDOUT_RECEIPT.as_posix(),
            "--retrieval-artifact",
            module._CANONICAL_RETRIEVAL_ARTIFACT.as_posix(),
            "--candidate-head",
            candidate_head,
            "--attempt-receipt",
            module._CANONICAL_ATTEMPT.as_posix(),
            "--artifact",
            module._CANONICAL_ARTIFACT.as_posix(),
            "--repository",
            str(alias),
            "--json",
        ]
    ) == 1
    output = json.loads(capsys.readouterr().out)

    assert (
        candidate_calls == 0
        and output["cause"] == "canonical_path_preflight_failed"
        and output["next_step"]
        == "correct_canonical_paths_before_first_attempt"
        and output["first_failed_gate"] == "path_preflight"
        and not (root / module._CANONICAL_ATTEMPT).exists()
        and not (root / module._CANONICAL_ARTIFACT).exists()
    ), "G2_REVIEW_CLI_ROOT_ALIAS_FALSE_PASS"


def test_compatibility_rejects_repository_parent_chain_alias_before_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    (
        root,
        protocol,
        freeze,
        receipt,
        retrieval_artifact,
        candidate_head,
    ) = _synthetic_canonical_authority(real_parent, monkeypatch)
    alias_parent = tmp_path / "alias-parent"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    alias = alias_parent / root.name
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    calls: list[str] = []

    def reject(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        calls.append("authority")
        raise AssertionError("authority reads must not start")

    monkeypatch.setattr(module, "_load_object", reject)
    monkeypatch.setattr(
        retrieval_order_workflow,
        "_candidate_seal",
        reject,
    )
    with pytest.raises(module.RetrievalOrderCompatibilityError):
        module.freeze_historical_capabilities(
            repository_root=alias,
            workspace=tmp_path / "historical-workspace",
        )
    result = module.record_canonical_compatibility(
        protocol_path=protocol,
        development_freeze_path=freeze,
        holdout_receipt_path=receipt,
        retrieval_artifact_path=retrieval_artifact,
        candidate_head=candidate_head,
        attempt_receipt_path=attempt,
        artifact_path=artifact,
        repository_root=alias,
    )

    assert calls == [], "G2_REVIEW_PARENT_CHAIN_ALIAS_FALSE_PASS"
    _assert_canonical_path_preflight_failure(result)
    assert not attempt.exists()
    assert not artifact.exists()


def test_record_canonical_cli_rejects_repository_parent_chain_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    root, _, _, _, _, candidate_head = _synthetic_canonical_authority(
        real_parent,
        monkeypatch,
    )
    alias_parent = tmp_path / "alias-parent"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    alias = alias_parent / root.name
    calls: list[str] = []

    def reject(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        calls.append("candidate")
        raise AssertionError("candidate seal must not start")

    monkeypatch.setattr(retrieval_order_workflow, "_candidate_seal", reject)
    assert module.main(
        [
            "record-canonical",
            "--protocol",
            "protocol.json",
            "--development-freeze",
            module._CANONICAL_DEVELOPMENT_FREEZE.as_posix(),
            "--holdout-receipt",
            module._CANONICAL_HOLDOUT_RECEIPT.as_posix(),
            "--retrieval-artifact",
            module._CANONICAL_RETRIEVAL_ARTIFACT.as_posix(),
            "--candidate-head",
            candidate_head,
            "--attempt-receipt",
            module._CANONICAL_ATTEMPT.as_posix(),
            "--artifact",
            module._CANONICAL_ARTIFACT.as_posix(),
            "--repository",
            str(alias),
            "--json",
        ]
    ) == 1
    output = json.loads(capsys.readouterr().out)

    assert (
        calls == []
        and output["cause"] == "canonical_path_preflight_failed"
        and output["first_failed_gate"] == "path_preflight"
        and not (root / module._CANONICAL_ATTEMPT).exists()
        and not (root / module._CANONICAL_ARTIFACT).exists()
    ), "G2_REVIEW_CLI_PARENT_CHAIN_ALIAS_FALSE_PASS"


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
    ("dangling", "symlink_parent"),
    ((False, False), (True, False), (False, True)),
)
def test_record_canonical_rejects_lexical_symlink_before_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dangling: bool,
    symlink_parent: bool,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    outside = tmp_path / "outside.json"
    if not dangling:
        outside.write_text("{}\n", encoding="utf-8")
    if symlink_parent:
        artifact.parent.rename(artifact.parent.with_name("retrieval-real"))
        artifact.parent.symlink_to(artifact.parent.with_name("retrieval-real"))
    else:
        artifact.symlink_to(outside)
    publish_calls = 0

    def publish(*args: object, **kwargs: object) -> NoReturn:
        nonlocal publish_calls
        del args, kwargs
        publish_calls += 1
        raise AssertionError("publication must not start")

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

    assert result == {
        "schema_version": (
            "mke.retrieval_order_compatibility_"
            "record_canonical_result.v1"
        ),
        "status": "failed",
        "mode": "record_canonical",
        "authority_layer": "canonical_publication",
        "canonical": True,
        "output_state": "not_applicable",
        "publication_outcome": "not_attempted",
        "problem": "retrieval_order_canonical_publication_unauthorized",
        "cause": "canonical_path_preflight_failed",
        "next_step": "correct_canonical_paths_before_first_attempt",
        "first_failed_gate": "path_preflight",
        "stage_statuses": [
            {"name": "canonical_publication", "status": "failed"}
        ],
        "historical_revision": 0,
        "current_revision": 0,
    }
    assert publish_calls == 0
    assert not attempt.exists()


def test_record_canonical_rejects_live_runtime_mismatch_before_attempt(
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
    original = retrieval_order_workflow._candidate_seal  # pyright: ignore[reportPrivateUsage]
    replay_calls = 0

    def forged_runtime(*args: object, **kwargs: object) -> dict[str, object]:
        candidate = deepcopy(original(*args, **kwargs))  # type: ignore[arg-type]
        candidate["runtime_profile"] = {
            "python": "forged-post-observation-runtime",
            "sqlite": "forged-post-observation-runtime",
            "pymupdf": "forged-post-observation-runtime",
        }
        return candidate

    def replay(**kwargs: object) -> NoReturn:
        nonlocal replay_calls
        del kwargs
        replay_calls += 1
        raise AssertionError("replay must not start")

    monkeypatch.setattr(
        retrieval_order_workflow,
        "_candidate_seal",
        forged_runtime,
    )
    monkeypatch.setattr(module, "build_compatibility_artifact", replay)

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

    assert result["problem"] == "retrieval_order_candidate_seal_mismatch"
    assert result["cause"] == "candidate_inputs_do_not_match_seal"
    assert result["first_failed_gate"] == "candidate_seal"
    assert result["output_state"] == "not_applicable"
    assert result["publication_outcome"] == "not_attempted"
    assert result["next_step"] == "return_to_authority_review"
    assert replay_calls == 0
    assert not attempt.exists()
    assert not artifact.exists()


def test_record_canonical_rejects_runtime_drift_at_capability_consumption(
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
    original = retrieval_order_workflow._candidate_seal  # pyright: ignore[reportPrivateUsage]
    calls = 0

    def drift_after_attempt(
        *args: object,
        **kwargs: object,
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        candidate = deepcopy(original(*args, **kwargs))  # type: ignore[arg-type]
        if calls > 1:
            candidate["runtime_profile"] = {
                "python": "forged-post-observation-runtime",
                "sqlite": "forged-post-observation-runtime",
                "pymupdf": "forged-post-observation-runtime",
            }
        return candidate

    monkeypatch.setattr(
        retrieval_order_workflow,
        "_candidate_seal",
        drift_after_attempt,
    )
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
    assert result["problem"] == "retrieval_order_candidate_seal_mismatch"
    assert result["first_failed_gate"] == "capability_consume"
    assert result["output_state"] == "complete_visible"
    assert result["publication_outcome"] == "published"
    assert result["next_step"] == "retain_attempt_and_stop"
    assert attempt.exists()
    assert not artifact.exists()


def test_record_canonical_rejects_runtime_drift_before_final_publication(
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
    original = retrieval_order_workflow._candidate_seal  # pyright: ignore[reportPrivateUsage]
    drifted = False

    def runtime_candidate(
        *args: object,
        **kwargs: object,
    ) -> dict[str, object]:
        candidate = deepcopy(original(*args, **kwargs))  # type: ignore[arg-type]
        if drifted:
            candidate["runtime_profile"] = {
                "python": "forged-post-observation-runtime",
                "sqlite": "forged-post-observation-runtime",
                "pymupdf": "forged-post-observation-runtime",
            }
        return candidate

    def build(**kwargs: object) -> dict[str, object]:
        nonlocal drifted
        del kwargs
        drifted = True
        return _complete_compatibility_double()

    monkeypatch.setattr(
        retrieval_order_workflow,
        "_candidate_seal",
        runtime_candidate,
    )
    monkeypatch.setattr(module, "build_compatibility_artifact", build)
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

    assert result["status"] == "failed"
    assert result["problem"] == "retrieval_order_candidate_seal_mismatch"
    assert result["first_failed_gate"] == "final_authority"
    assert result["output_state"] == "complete_visible"
    assert result["publication_outcome"] == "published"
    assert result["next_step"] == "retain_attempt_and_stop"
    assert attempt.exists()
    assert not artifact.exists()


@pytest.mark.parametrize(
    "seam",
    ("capability_consume", "final_authority"),
)
@pytest.mark.parametrize("retarget_kind", ("symlink", "directory"))
def test_record_canonical_repreflights_retargeted_protocol_before_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seam: str,
    retarget_kind: str,
) -> None:
    module = _module()
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        _synthetic_canonical_authority(tmp_path, monkeypatch)
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    original_candidate = retrieval_order_workflow._candidate_seal  # pyright: ignore[reportPrivateUsage]
    original_metadata = module.load_retrieval_order_protocol_metadata
    candidate_calls = 0
    alias_reads: list[str] = []
    replaced = False

    def retarget() -> None:
        nonlocal replaced
        if replaced:
            return
        retained = protocol.with_suffix(".retained.json")
        protocol.rename(retained)
        if retarget_kind == "symlink":
            protocol.symlink_to(retained)
        else:
            protocol.mkdir()
        replaced = True

    def candidate(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal candidate_calls
        candidate_calls += 1
        value = original_candidate(*args, **kwargs)  # type: ignore[arg-type]
        if seam == "capability_consume" and candidate_calls == 2:
            retarget()
        return value

    def metadata(*args: object, **kwargs: object) -> object:
        if protocol.is_symlink() or protocol.is_dir():
            alias_reads.append("metadata")
        return original_metadata(*args, **kwargs)

    def build(**kwargs: object) -> dict[str, object]:
        del kwargs
        if seam == "final_authority":
            retarget()
        return _complete_compatibility_double()

    monkeypatch.setattr(retrieval_order_workflow, "_candidate_seal", candidate)
    monkeypatch.setattr(
        module,
        "load_retrieval_order_protocol_metadata",
        metadata,
    )
    monkeypatch.setattr(module, "build_compatibility_artifact", build)
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

    assert (
        result["first_failed_gate"] == seam
        and result["next_step"] == "retain_attempt_and_stop"
        and alias_reads == []
        and attempt.exists()
        and not artifact.exists()
    ), "G4_CAPABILITY_REPREFLIGHT_FALSE_PASS"


@pytest.mark.parametrize("basename", ("attempt", "destination"))
def test_record_canonical_rejects_directory_basename_as_path_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    basename: str,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    (attempt if basename == "attempt" else artifact).mkdir()
    monkeypatch.setattr(module, "build_compatibility_artifact", _fail_replay)
    monkeypatch.setattr(module, "publish_json_no_replace", _fail_replay)

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

    _assert_canonical_path_preflight_failure(result)


@pytest.mark.parametrize("basename", ("attempt", "destination"))
def test_record_canonical_guards_preexisting_digest_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    basename: str,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    target = attempt if basename == "attempt" else artifact
    target.write_text("{}\n", encoding="utf-8")
    original_sha256 = module._sha256

    def unreadable(path: Path) -> str:
        if path == target:
            raise OSError("synthetic unreadable canonical entry")
        return original_sha256(path)

    monkeypatch.setattr(module, "_sha256", unreadable)
    monkeypatch.setattr(module, "build_compatibility_artifact", _fail_replay)
    monkeypatch.setattr(module, "publish_json_no_replace", _fail_replay)

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

    _assert_canonical_path_preflight_failure(result)


@pytest.mark.parametrize(
    "mutation",
    (
        "unexpected_untracked",
        "staged",
        "partial_index",
        "deleted",
        "renamed",
        "freeze_rewrite",
    ),
)
def test_record_canonical_requires_exact_preattempt_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT
    if mutation == "unexpected_untracked":
        (root / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
    elif mutation == "staged":
        subprocess.run(("git", "add", freeze), cwd=root, check=True)
    elif mutation == "partial_index":
        subprocess.run(
            ("git", "add", "--intent-to-add", receipt),
            cwd=root,
            check=True,
        )
    elif mutation == "deleted":
        receipt.unlink()
    elif mutation == "freeze_rewrite":
        freeze.write_bytes(freeze.read_bytes() + b" ")
    else:
        receipt.rename(receipt.with_name("renamed-receipt.json"))
    monkeypatch.setattr(module, "build_compatibility_artifact", _fail_replay)

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
    assert result["first_failed_gate"] in {
        "success_authority",
        "candidate_seal",
    }
    assert not attempt.exists()
    assert not artifact.exists()


@pytest.mark.parametrize(
    "mutation",
    ("freeze_rewrite", "head_drift", "unexpected_untracked"),
)
def test_postattempt_authority_drift_retains_visible_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    module = _module()
    authority = _synthetic_canonical_authority(tmp_path, monkeypatch)
    root, protocol, freeze, receipt, retrieval_artifact, candidate_head = (
        authority
    )
    attempt = root / module._CANONICAL_ATTEMPT
    artifact = root / module._CANONICAL_ARTIFACT

    def build(**kwargs: object) -> dict[str, object]:
        del kwargs
        assert attempt.exists()
        if mutation == "freeze_rewrite":
            freeze.write_bytes(freeze.read_bytes() + b" ")
        elif mutation == "head_drift":
            tracked = root / "protocol.json"
            tracked.write_bytes(tracked.read_bytes() + b" ")
            subprocess.run(("git", "add", "protocol.json"), cwd=root, check=True)
            subprocess.run(
                ("git", "commit", "-qm", "synthetic head drift"),
                cwd=root,
                check=True,
            )
        else:
            (root / "unexpected.txt").write_text(
                "unexpected\n",
                encoding="utf-8",
            )
        return _complete_compatibility_double()

    monkeypatch.setattr(module, "build_compatibility_artifact", build)
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

    assert result["status"] == "failed"
    assert result["output_state"] == "complete_visible"
    assert result["publication_outcome"] == "published"
    assert result["next_step"] == "retain_attempt_and_stop"
    assert result["first_failed_gate"] in {
        "capability_consume",
        "compatibility_build",
        "final_authority",
    }
    assert attempt.exists()
    assert not artifact.exists()


def test_postattempt_replay_exception_retains_visible_attempt(
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
    assert result["problem"] == "retrieval_order_compatibility_incomplete"
    assert result["cause"] == "unapproved_family_delta"
    assert result["first_failed_gate"] == "compatibility_build"
    assert result["output_state"] == "complete_visible"
    assert result["publication_outcome"] == "published"
    assert result["next_step"] == "retain_attempt_and_stop"
    assert attempt.exists()
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
    monkeypatch.setattr(
        module,
        "_validate_compatibility_artifact",
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
    assert result["output_state"] == "complete_visible"
    assert result["publication_outcome"] == "published"
    assert result["next_step"] == "retain_attempt_and_stop"
    if fault == "directory_fsync":
        assert artifact.exists()
    else:
        assert not artifact.exists()
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


def _install_g2_candidate_seal(
    monkeypatch: pytest.MonkeyPatch,
    *,
    root: Path,
    retrieval_artifact: Path,
) -> None:
    retained = json.loads(retrieval_artifact.read_text(encoding="utf-8"))
    candidate_seal = retained["candidate_seal"]

    def candidate(
        repository_root: Path,
        *,
        expected_status: dict[Path, str],
    ) -> dict[str, object]:
        assert repository_root.resolve() == root.resolve()
        return {
            "head": candidate_seal["head"],
            "runtime_profile": candidate_seal["runtime_profile"],
            "status_records": tuple(
                sorted(
                    (
                        path.relative_to(root).as_posix(),
                        status,
                        None,
                    )
                    for path, status in expected_status.items()
                )
            ),
        }

    monkeypatch.setattr(
        retrieval_order_workflow,
        "_candidate_seal",
        candidate,
    )


def _assert_canonical_path_preflight_failure(
    result: dict[str, object],
) -> None:
    assert result["status"] == "failed"
    assert result["mode"] == "record_canonical"
    assert result["output_state"] == "not_applicable"
    assert result["publication_outcome"] == "not_attempted"
    assert result["problem"] == (
        "retrieval_order_canonical_publication_unauthorized"
    )
    assert result["cause"] == "canonical_path_preflight_failed"
    assert result["next_step"] == (
        "correct_canonical_paths_before_first_attempt"
    )
    assert result["first_failed_gate"] == "path_preflight"


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
    *,
    pre_observation_mutation: Callable[[Path], None] | None = None,
) -> tuple[Path, Path, Path, Path, Path, str]:
    root = tmp_path / "canonical-synthetic-repository"
    for relative in IMMUTABLE_INPUT_SHA256:
        source = ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    module = _module()
    for relative in module._historical_dynamic_inputs(ROOT):
        source = ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    for relative in H1_MISSING_ARCHIVED_INPUTS:
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
    source = root / "src/mke"
    source.mkdir(parents=True, exist_ok=True)
    (source / "synthetic.py").write_text(
        "SYNTHETIC = True\n",
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
            ".github",
            "benchmarks",
            "scripts",
            "src",
            "tests",
            "pyproject.toml",
            "uv.lock",
        ),
        ("git", "commit", "-qm", "synthetic authority"),
    )
    for command in commands:
        subprocess.run(command, cwd=root, check=True)
    if pre_observation_mutation is not None:
        pre_observation_mutation(root)
    assert (
        subprocess.check_output(
            ("git", "status", "--porcelain=v1", "-z"),
            cwd=root,
        )
        == b""
    )
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
