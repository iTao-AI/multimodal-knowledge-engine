from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import subprocess
import tempfile
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

import mke.adapters.sqlite
import mke.evaluation._atomic_json_publication as atomic_publication
import mke.evaluation.retrieval_order_workflow as retrieval_order_workflow
from mke.evaluation.retrieval_order_workflow import (
    SyntheticHoldoutCapability,
    _controlled_sqlite_ids,  # pyright: ignore[reportPrivateUsage]
    main,
    observe_retrieval_order_partition,
    retrieval_runtime_profile,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-order-v1/protocol.json"
CANONICAL_HOLDOUT_FIXTURE = (
    ROOT / "tests/fixtures/retrieval-order-v1/holdout/cases.json"
)


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
HISTORICAL_OBSERVATION = (
    ROOT
    / "benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json"
)
HISTORICAL_OBSERVATION_SHA256 = (
    "1a98e4e6c4eabc01663991646aac46e4a73033eef8a7e17a27db2e0fdce71691"
)


def test_development_candidate_is_stable_without_recording(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    benchmark_root = ROOT / "benchmarks/retrieval"
    before = {
        path.name: path.read_bytes()
        for path in benchmark_root.glob("retrieval-order-v1-*.json")
    }
    original_temporary_directory = tempfile.TemporaryDirectory

    def temporary_directory(*, prefix: str):
        return original_temporary_directory(prefix=prefix, dir=tmp_path)

    monkeypatch.setattr(
        retrieval_order_workflow.tempfile,
        "TemporaryDirectory",
        temporary_directory,
    )

    observation = observe_retrieval_order_partition(
        protocol_path=PROTOCOL,
        partition="development",
        repository_root=ROOT,
    )

    assert observation["integrity_status"] == "passed"
    assert observation["observation_status"] == "passed"
    assert observation["stable_order_rate"] == 1.0
    assert observation["candidate_membership_delta"] == 0
    assert observation["score_hex_delta"] == 0
    assert observation["non_tied_pair_delta"] == 0
    assert observation["pagination_duplicate_or_gap_count"] == 0
    assert observation["strategy_revision"] == 2
    assert observation["query_policy_revision"] == 1
    assert list(tmp_path.iterdir()) == []
    assert {
        path.name: path.read_bytes()
        for path in benchmark_root.glob("retrieval-order-v1-*.json")
    } == before


def test_controlled_id_schedule_restores_generator_after_failure() -> None:
    original = mke.adapters.sqlite._new_id  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(RuntimeError, match="probe"):
        with _controlled_sqlite_ids({"lib": ("lib_fixed",)}):
            assert (
                mke.adapters.sqlite._new_id("lib")  # pyright: ignore[reportPrivateUsage]
                == "lib_fixed"
            )
            raise RuntimeError("probe")

    assert mke.adapters.sqlite._new_id is original  # pyright: ignore[reportPrivateUsage]


def test_runtime_profile_contains_only_frozen_fields() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        profile = retrieval_runtime_profile(connection)
    finally:
        connection.close()

    assert tuple(profile) == (
        "python",
        "sqlite",
        "sqlite_source_id",
        "sqlite_compile_options",
        "fts5_rank_configuration",
        "strategy_revision",
        "query_policy_revision",
    )
    assert profile["strategy_revision"] == 2
    assert profile["query_policy_revision"] == 1


def test_premaintenance_failure_record_is_immutable_and_public_safe() -> None:
    content = HISTORICAL_OBSERVATION.read_bytes()
    payload = json.loads(content)

    assert hashlib.sha256(content).hexdigest() == (
        HISTORICAL_OBSERVATION_SHA256
    )
    assert set(payload) == {
        "candidate_membership_delta",
        "cases",
        "cause",
        "integrity_status",
        "next_step",
        "non_tied_pair_delta",
        "observation_status",
        "pagination_duplicate_or_gap_count",
        "partition",
        "phase",
        "problem",
        "query_policy_revision",
        "runtime_profile",
        "schema_version",
        "score_hex_delta",
        "stable_order_rate",
        "strategy_revision",
    }
    assert payload["schema_version"] == "mke.retrieval_order_observation.v1"
    assert payload["phase"] == "current"
    assert payload["partition"] == "development"
    assert payload["integrity_status"] == "passed"
    assert payload["observation_status"] == "failed"
    assert payload["strategy_revision"] == 1
    assert payload["query_policy_revision"] == 1
    assert payload["problem"] == "retrieval_order_nondeterministic"
    assert payload["cause"] == "fresh workspace stable projections differ"
    assert payload["next_step"] == "apply_tie_only_stable_order_maintenance"
    rendered = content.decode("utf-8")
    for forbidden in (
        "amber mechanism probe",
        "青铜机制验证",
        '"evidence_id":',
        '"source_id":',
        "cursor",
        str(ROOT),
    ):
        assert forbidden not in rendered


def test_current_cli_records_live_revision_2_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = tmp_path / "observation.json"

    status = main(
        [
            "current",
            "--protocol",
            str(PROTOCOL),
            "--record",
            str(record),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert status == 0
    assert captured.err == ""
    assert payload == json.loads(record.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "mke.retrieval_order_observation.v1"
    assert payload["phase"] == "current"
    assert payload["integrity_status"] == "passed"
    assert payload["observation_status"] == "passed"
    assert payload["strategy_revision"] == 2
    assert payload["query_policy_revision"] == 1
    assert "problem" not in payload
    assert "cause" not in payload
    assert "next_step" not in payload
    rendered = captured.out
    for forbidden in (
        "amber mechanism probe",
        "青铜机制验证",
        '"evidence_id":',
        '"source_id":',
        "cursor",
        str(ROOT),
    ):
        assert forbidden not in rendered


@pytest.mark.parametrize("entry", ("direct", "helper", "alias", "symlink"))
def test_holdout_requires_typed_capability_before_fixture_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
) -> None:
    root, protocol_path, _, holdout_path = _synthetic_protocol(tmp_path)
    requested = protocol_path
    if entry == "alias":
        requested = protocol_path.parent / "." / protocol_path.name
    elif entry == "symlink":
        requested = tmp_path / "protocol-link.json"
        requested.symlink_to(protocol_path)
    opened: list[Path] = []
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() == holdout_path:
            opened.append(path.resolve())
        return original(path)

    def helper(path: Path) -> dict[str, object]:
        return observe_retrieval_order_partition(
            protocol_path=path,
            partition="holdout",
            repository_root=root,
        )

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    def direct(path: Path) -> dict[str, object]:
        return observe_retrieval_order_partition(
            protocol_path=path,
            partition="holdout",
            repository_root=root,
        )

    invoke: Callable[[Path], dict[str, object]] = (
        helper if entry == "helper" else direct
    )

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="holdout capability",
    ):
        invoke(requested)

    assert opened == []


@pytest.mark.parametrize(
    ("synthetic_partition", "canonical_partition"),
    (
        ("development", "development"),
        ("development", "holdout"),
        ("holdout", "development"),
        ("holdout", "holdout"),
    ),
)
def test_synthetic_capability_rejects_any_canonical_fixture_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_partition: str,
    canonical_partition: str,
) -> None:
    root, protocol_path, development_path, holdout_path = (
        _synthetic_protocol(tmp_path)
    )
    payload = json.loads(protocol_path.read_text(encoding="utf-8"))
    partitions = cast(dict[str, object], payload["partitions"])
    target = cast(dict[str, object], partitions[synthetic_partition])
    canonical_digest = {
        "development": (
            "e37e9519d899fc934c1758860f1b40d3605ed065a11b1921fdac914746f733f5"
        ),
        "holdout": (
            "e95c5253d0284f8127754591b9da9aa71b30a8ceae2670ca4751456cf7d4a080"
        ),
    }[canonical_partition]
    target["sha256"] = canonical_digest
    protocol_path.write_text(json.dumps(payload), encoding="utf-8")
    opened: list[Path] = []
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() in {
            development_path,
            holdout_path,
        }:
            opened.append(path.resolve())
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="synthetic holdout",
    ):
        SyntheticHoldoutCapability.issue(
            protocol_path=protocol_path,
            repository_root=root,
            candidate_head="a" * 40,
            runtime_profile={"strategy_revision": 2},
        )

    assert opened == []


def test_synthetic_holdout_capability_is_bound_and_consumed_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol_path, _, holdout_path = _synthetic_protocol(tmp_path)
    capability = SyntheticHoldoutCapability.issue(
        protocol_path=protocol_path,
        repository_root=root,
        candidate_head="a" * 40,
        runtime_profile={"strategy_revision": 2},
    )

    observation = observe_retrieval_order_partition(
        protocol_path=protocol_path,
        partition="holdout",
        repository_root=root,
        holdout_capability=capability,
    )

    assert observation["observation_status"] == "passed"
    opened: list[Path] = []
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() == holdout_path:
            opened.append(path.resolve())
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="holdout capability",
    ):
        observe_retrieval_order_partition(
            protocol_path=protocol_path,
            partition="holdout",
            repository_root=root,
            holdout_capability=capability,
        )
    assert opened == []


def test_synthetic_capability_cannot_be_constructed_without_issuer(
    tmp_path: Path,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    metadata = retrieval_order_workflow.load_retrieval_order_protocol_metadata(
        protocol_path,
        repository_root=root,
    )

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="issuer",
    ):
        SyntheticHoldoutCapability(
            protocol_path=metadata.protocol_path,
            protocol_sha256=metadata.protocol_sha256,
            holdout_fixture_sha256=metadata.holdout.sha256,
            candidate_head="a" * 40,
            runtime_profile={"strategy_revision": 2},
        )


@pytest.mark.parametrize("copy_mode", ("exact", "reserialized"))
def test_capability_rejects_copied_protocol_before_fixture_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    copy_mode: str,
) -> None:
    root, protocol_path, _, holdout_path = _synthetic_protocol(tmp_path)
    capability = SyntheticHoldoutCapability.issue(
        protocol_path=protocol_path,
        repository_root=root,
        candidate_head="a" * 40,
        runtime_profile={"strategy_revision": 2},
    )
    copied = root / "reserialized.json"
    if copy_mode == "exact":
        copied.write_bytes(protocol_path.read_bytes())
    else:
        copied.write_text(
            json.dumps(
                json.loads(protocol_path.read_text(encoding="utf-8")),
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
    opened: list[Path] = []
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() == holdout_path:
            opened.append(path.resolve())
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="holdout capability",
    ):
        observe_retrieval_order_partition(
            protocol_path=copied,
            partition="holdout",
            repository_root=root,
            holdout_capability=capability,
        )
    assert opened == []


def test_candidate_head_mismatch_rejects_holdout_before_receipt_or_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol_path, _, holdout_path = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    freeze = root / "benchmarks/retrieval/development-freeze.json"
    receipt = root / "benchmarks/retrieval/holdout-receipt.json"
    artifact = root / "benchmarks/retrieval/artifact.json"
    retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol_path,
        freeze_path=freeze,
        repository_root=root,
    )
    subprocess.run(
        ("git", "commit", "--allow-empty", "-qm", "changed candidate"),
        cwd=root,
        check=True,
    )
    opened: list[Path] = []
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() == holdout_path:
            opened.append(path.resolve())
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="development freeze",
    ):
        retrieval_order_workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            development_freeze_path=freeze,
            receipt_path=receipt,
            artifact_path=artifact,
            repository_root=root,
        )
    assert opened == []
    assert not receipt.exists()
    assert not artifact.exists()


def test_preexisting_holdout_artifact_rejects_before_receipt_or_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol_path, _, holdout_path = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    freeze = root / "benchmarks/retrieval/development-freeze.json"
    receipt = root / "benchmarks/retrieval/holdout-receipt.json"
    artifact = root / "benchmarks/retrieval/artifact.json"
    retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol_path,
        freeze_path=freeze,
        repository_root=root,
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{}\n", encoding="utf-8")
    opened: list[Path] = []
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() == holdout_path:
            opened.append(path.resolve())
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="artifact already exists",
    ):
        retrieval_order_workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            development_freeze_path=freeze,
            receipt_path=receipt,
            artifact_path=artifact,
            repository_root=root,
        )

    assert opened == []
    assert not receipt.exists()
    assert artifact.read_text(encoding="utf-8") == "{}\n"


def test_canonical_protocol_rejects_noncanonical_output_paths_before_fixture(
    tmp_path: Path,
) -> None:
    freeze = tmp_path / "development-freeze.json"
    receipt = tmp_path / "holdout-receipt.json"
    artifact = tmp_path / "artifact.json"

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="authority paths",
    ):
        retrieval_order_workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
            protocol_path=PROTOCOL,
            development_freeze_path=freeze,
            receipt_path=receipt,
            artifact_path=artifact,
            repository_root=ROOT,
        )

    assert not receipt.exists()
    assert not artifact.exists()


def test_test_suite_has_no_direct_canonical_holdout_observer_call() -> None:
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
            )
            if name != "observe_retrieval_order_partition":
                continue
            keywords = {item.arg: item.value for item in node.keywords}
            partition = keywords.get("partition")
            protocol = keywords.get("protocol_path")
            if (
                isinstance(partition, ast.Constant)
                and partition.value == "holdout"
                and (
                    isinstance(protocol, ast.Name)
                    and protocol.id == "PROTOCOL"
                    or isinstance(protocol, ast.Constant)
                    and str(protocol.value).endswith(
                        "tests/fixtures/retrieval-order-v1/protocol.json"
                    )
                )
            ):
                raise AssertionError(
                    f"canonical holdout observer call in {path}"
                )


def test_development_and_holdout_publish_receipt_before_synthetic_fixture_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, protocol_path, _, holdout_path = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    output_root = root / "benchmarks/retrieval"
    freeze = output_root / "development-freeze.json"
    receipt = output_root / "holdout-receipt.json"
    artifact = output_root / "artifact.json"
    monkeypatch.chdir(root)
    original_candidate_seal = (
        retrieval_order_workflow._candidate_seal  # pyright: ignore[reportPrivateUsage]
    )
    candidate_seals: list[dict[str, object]] = []

    def candidate_seal(*args: object, **kwargs: object) -> dict[str, object]:
        result = original_candidate_seal(*args, **kwargs)  # type: ignore[arg-type]
        candidate_seals.append(result)
        return result

    monkeypatch.setattr(
        retrieval_order_workflow,
        "_candidate_seal",
        candidate_seal,
    )

    assert main(
        [
            "development",
            "--protocol",
            str(protocol_path),
            "--record-development-freeze",
            str(freeze),
            "--json",
        ]
    ) == 0
    development_result = json.loads(capsys.readouterr().out)
    assert development_result["status"] == "passed"
    assert development_result["mode"] == "development"
    assert development_result["output_state"] == "complete_visible"
    assert development_result["publication_outcome"] == "published"
    opened: list[Path] = []
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() == holdout_path:
            assert receipt.exists()
            retained = json.loads(receipt.read_text(encoding="utf-8"))
            assert retained["schema_version"] == (
                "mke.retrieval_order_holdout_receipt.v1"
            )
            opened.append(path.resolve())
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    original_observer = (
        retrieval_order_workflow.observe_retrieval_order_partition
    )
    holdout_capability_types: list[type[object]] = []

    def observe(**kwargs: object) -> dict[str, object]:
        capability = kwargs.get("holdout_capability")
        if kwargs.get("partition") == "holdout":
            holdout_capability_types.append(type(capability))
        return original_observer(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        retrieval_order_workflow,
        "observe_retrieval_order_partition",
        observe,
    )

    assert main(
        [
            "holdout",
            "--protocol",
            str(protocol_path),
            "--development-freeze",
            str(freeze),
            "--record-holdout-receipt",
            str(receipt),
            "--record",
            str(artifact),
            "--json",
        ]
    ) == 0
    holdout_result = json.loads(capsys.readouterr().out)
    assert holdout_result["status"] == "passed"
    assert holdout_result["mode"] == "holdout"
    assert holdout_result["output_state"] == "complete_visible"
    assert holdout_result["publication_outcome"] == "published"
    assert opened == [holdout_path]
    assert holdout_capability_types == [SyntheticHoldoutCapability]
    retained_artifact = json.loads(artifact.read_text(encoding="utf-8"))
    assert retained_artifact["holdout_status"] == "observed"
    assert retained_artifact["observation"]["observation_status"] == "passed"
    assert len(candidate_seals) == 7
    assert all(
        candidate["head"] == candidate_seals[0]["head"]
        and candidate["runtime_profile"]
        == candidate_seals[0]["runtime_profile"]
        for candidate in candidate_seals
    )

    assert main(
        [
            "holdout",
            "--protocol",
            str(protocol_path),
            "--development-freeze",
            str(freeze),
            "--record-holdout-receipt",
            str(receipt),
            "--record",
            str(artifact),
            "--json",
        ]
    ) == 1
    repeated = json.loads(capsys.readouterr().out)
    assert repeated["problem"] == "retrieval_order_holdout_already_started"
    assert opened == [holdout_path]


@pytest.mark.parametrize(
    "status_kind",
    ("staged", "partial", "modified", "deleted", "rename"),
)
def test_candidate_seal_rejects_non_untracked_allowed_evidence(
    tmp_path: Path,
    status_kind: str,
) -> None:
    root, _, _, _ = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    allowed = root / "allowed.json"
    if status_kind in {"modified", "deleted"}:
        allowed.write_text("{}\n", encoding="utf-8")
        subprocess.run(("git", "add", "allowed.json"), cwd=root, check=True)
        subprocess.run(
            ("git", "commit", "-qm", "track allowed evidence"),
            cwd=root,
            check=True,
        )
        if status_kind == "modified":
            allowed.write_text("{}\n\n", encoding="utf-8")
        else:
            allowed.unlink()
    elif status_kind == "rename":
        source = root / "source.json"
        source.write_text("{}\n", encoding="utf-8")
        subprocess.run(("git", "add", "source.json"), cwd=root, check=True)
        subprocess.run(
            ("git", "commit", "-qm", "track rename source"),
            cwd=root,
            check=True,
        )
        subprocess.run(
            ("git", "mv", "source.json", "allowed.json"),
            cwd=root,
            check=True,
        )
    else:
        allowed.write_text("{}\n", encoding="utf-8")
        subprocess.run(("git", "add", "allowed.json"), cwd=root, check=True)
        if status_kind == "partial":
            allowed.write_text("{}\n\n", encoding="utf-8")

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="candidate seal",
    ):
        retrieval_order_workflow._candidate_seal(  # pyright: ignore[reportPrivateUsage]
            root,
            expected_status={allowed: "??"},
        )


def test_candidate_seal_rejects_head_change_during_status_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _, _ = _synthetic_protocol(tmp_path)
    first = "a" * 40
    second = "b" * 40
    results = iter(
        (
            subprocess.CompletedProcess(("git",), 0, f"{first}\n", ""),
            subprocess.CompletedProcess(("git",), 0, "", ""),
            subprocess.CompletedProcess(("git",), 0, f"{second}\n", ""),
        )
    )

    def run(
        *args: object,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        return next(results)

    monkeypatch.setattr(retrieval_order_workflow.subprocess, "run", run)

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="candidate seal",
    ):
        retrieval_order_workflow._candidate_seal(  # pyright: ignore[reportPrivateUsage]
            root,
            expected_status={},
        )


@pytest.mark.parametrize(
    "mutation_point",
    ("observer_head", "prepublication_status"),
)
def test_development_rechecks_candidate_before_freeze_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation_point: str,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    freeze = root / "benchmarks/retrieval/development-freeze.json"
    original_observer = (
        retrieval_order_workflow.observe_retrieval_order_partition
    )
    original_builder = retrieval_order_workflow.build_development_freeze

    if mutation_point == "observer_head":
        def observe(**kwargs: object) -> dict[str, object]:
            result = original_observer(**kwargs)  # type: ignore[arg-type]
            subprocess.run(
                ("git", "commit", "--allow-empty", "-qm", "mutate head"),
                cwd=root,
                check=True,
            )
            return result

        monkeypatch.setattr(
            retrieval_order_workflow,
            "observe_retrieval_order_partition",
            observe,
        )
    else:
        def build(**kwargs: object) -> dict[str, object]:
            result = original_builder(**kwargs)  # type: ignore[arg-type]
            (root / "unexpected.txt").write_text("dirty", encoding="utf-8")
            return result

        monkeypatch.setattr(
            retrieval_order_workflow,
            "build_development_freeze",
            build,
        )

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="candidate seal",
    ):
        retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            freeze_path=freeze,
            repository_root=root,
        )

    assert not freeze.exists()


@pytest.mark.parametrize(
    "mutation_point",
    (
        "staged_before_receipt",
        "consume_untracked",
        "consume_modified",
        "consume_staged",
        "consume_deleted",
        "consume_renamed",
        "consume_freeze_rewrite",
        "consume_receipt_rewrite",
        "observer_freeze_rewrite",
        "observer_receipt_rewrite",
        "prepublication_status",
    ),
)
def test_holdout_rechecks_exact_post_receipt_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation_point: str,
) -> None:
    root, protocol_path, _, holdout_path = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    freeze = root / "benchmarks/retrieval/development-freeze.json"
    receipt = root / "benchmarks/retrieval/holdout-receipt.json"
    artifact = root / "benchmarks/retrieval/artifact.json"
    tracked_mutation = {
        "consume_modified": "modified.txt",
        "consume_staged": "staged.txt",
        "consume_deleted": "deleted.txt",
        "consume_renamed": "rename-source.txt",
    }.get(mutation_point)
    if tracked_mutation is not None:
        (root / tracked_mutation).write_text("before\n", encoding="utf-8")
        subprocess.run(
            ("git", "add", tracked_mutation),
            cwd=root,
            check=True,
        )
        subprocess.run(
            ("git", "commit", "-qm", "track mutation fixture"),
            cwd=root,
            check=True,
        )
    retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol_path,
        freeze_path=freeze,
        repository_root=root,
    )
    if mutation_point == "staged_before_receipt":
        subprocess.run(
            ("git", "add", freeze.relative_to(root).as_posix()),
            cwd=root,
            check=True,
        )
    original_consume = (
        SyntheticHoldoutCapability._consume  # pyright: ignore[reportPrivateUsage]
    )
    original_observer = (
        retrieval_order_workflow.observe_retrieval_order_partition
    )
    original_builder = retrieval_order_workflow.build_retrieval_order_artifact
    opened = 0
    publication_destinations: list[Path] = []
    receipt_publications: list[atomic_publication.AtomicPublicationResult] = []
    original_read = Path.read_bytes
    original_publish = retrieval_order_workflow.publish_json_no_replace
    original_publish_or_stop = (
        retrieval_order_workflow._publish_or_stop  # pyright: ignore[reportPrivateUsage]
    )

    def read_bytes(path: Path) -> bytes:
        nonlocal opened
        if path.resolve() == holdout_path:
            opened += 1
        return original_read(path)

    def publish(destination: Path, *args: object, **kwargs: object):
        publication_destinations.append(destination.resolve())
        return original_publish(destination, *args, **kwargs)  # type: ignore[arg-type]

    def publish_or_stop(**kwargs: object):
        result = original_publish_or_stop(**kwargs)  # type: ignore[arg-type]
        if cast(Path, kwargs["destination"]).resolve() == receipt.resolve():
            receipt_publications.append(result)
        return result

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(
        retrieval_order_workflow,
        "publish_json_no_replace",
        publish,
    )
    monkeypatch.setattr(
        retrieval_order_workflow,
        "_publish_or_stop",
        publish_or_stop,
    )
    if mutation_point.startswith("consume_"):
        def consume(
            capability: SyntheticHoldoutCapability,
            metadata: object,
        ) -> None:
            original_consume(capability, metadata)  # type: ignore[arg-type]
            if mutation_point == "consume_untracked":
                (root / "consume-dirty.txt").write_text(
                    "dirty",
                    encoding="utf-8",
                )
            elif mutation_point == "consume_modified":
                (root / "modified.txt").write_text(
                    "after\n",
                    encoding="utf-8",
                )
            elif mutation_point == "consume_staged":
                (root / "staged.txt").write_text(
                    "after\n",
                    encoding="utf-8",
                )
                subprocess.run(
                    ("git", "add", "staged.txt"),
                    cwd=root,
                    check=True,
                )
            elif mutation_point == "consume_deleted":
                (root / "deleted.txt").unlink()
            elif mutation_point == "consume_renamed":
                subprocess.run(
                    (
                        "git",
                        "mv",
                        "rename-source.txt",
                        "rename-destination.txt",
                    ),
                    cwd=root,
                    check=True,
                )
            elif mutation_point == "consume_freeze_rewrite":
                freeze.write_bytes(freeze.read_bytes() + b"\n")
            else:
                receipt.write_bytes(receipt.read_bytes() + b"\n")

        monkeypatch.setattr(SyntheticHoldoutCapability, "_consume", consume)
    elif mutation_point.startswith("observer_"):
        def observe(**kwargs: object) -> dict[str, object]:
            result = original_observer(**kwargs)  # type: ignore[arg-type]
            target = (
                freeze
                if mutation_point == "observer_freeze_rewrite"
                else receipt
            )
            target.write_bytes(target.read_bytes() + b"\n")
            return result

        monkeypatch.setattr(
            retrieval_order_workflow,
            "observe_retrieval_order_partition",
            observe,
        )
    elif mutation_point == "prepublication_status":
        def build(**kwargs: object) -> dict[str, object]:
            result = original_builder(**kwargs)  # type: ignore[arg-type]
            (root / "prepublish-dirty.txt").write_text(
                "dirty",
                encoding="utf-8",
            )
            return result

        monkeypatch.setattr(
            retrieval_order_workflow,
            "build_retrieval_order_artifact",
            build,
        )

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError
    ) as raised:
        retrieval_order_workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            development_freeze_path=freeze,
            receipt_path=receipt,
            artifact_path=artifact,
            repository_root=root,
        )

    if mutation_point == "staged_before_receipt":
        assert not receipt.exists()
    else:
        assert receipt.exists()
        assert len(receipt_publications) == 1
        assert raised.value.publication is receipt_publications[0]
        assert raised.value.publication is not None
        assert raised.value.publication.output_state == "complete_visible"
        assert raised.value.publication.publication_outcome == "published"
        assert raised.value.next_step == "retain_receipt_and_stop"
    assert opened == (
        0
        if mutation_point == "staged_before_receipt"
        or mutation_point.startswith("consume_")
        else 1
    )
    assert not artifact.exists()
    assert publication_destinations.count(artifact.resolve()) == 0


def test_production_capability_binds_retained_authority_before_fixture_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    freeze = root / "benchmarks/retrieval/development-freeze.json"
    receipt = root / "benchmarks/retrieval/holdout-receipt.json"
    retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol_path,
        freeze_path=freeze,
        repository_root=root,
    )
    metadata = retrieval_order_workflow.load_retrieval_order_protocol_metadata(
        protocol_path,
        repository_root=root,
    )
    if not hasattr(retrieval_order_workflow, "_bind_holdout_authority"):
        pytest.fail(
            "production capability does not bind retained authority snapshot"
        )
    candidate = retrieval_order_workflow._candidate_seal(  # pyright: ignore[reportPrivateUsage]
        root,
        expected_status={freeze: "??"},
    )
    public_candidate = retrieval_order_workflow._public_candidate_seal(  # pyright: ignore[reportPrivateUsage]
        candidate
    )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_bytes(
        retrieval_order_workflow.render_json_bytes(
            retrieval_order_workflow.build_holdout_receipt(
                metadata=metadata,
                candidate_seal=public_candidate,
                development_freeze_path=freeze,
                repository_root=root,
            )
        )
    )
    authority = retrieval_order_workflow._bind_holdout_authority(  # pyright: ignore[reportPrivateUsage]
        metadata=metadata,
        candidate_seal=public_candidate,
        development_freeze_path=freeze,
        receipt_path=receipt,
        repository_root=root,
    )
    receipt_sha256 = hashlib.sha256(receipt.read_bytes()).hexdigest()

    def is_canonical_metadata(
        *args: object,
        **kwargs: object,
    ) -> bool:
        del args, kwargs
        return True

    monkeypatch.setattr(
        retrieval_order_workflow,
        "_is_canonical_holdout_metadata",
        is_canonical_metadata,
    )

    def issue():
        return retrieval_order_workflow._ProductionHoldoutCapability(  # pyright: ignore[reportPrivateUsage]
            issuer=retrieval_order_workflow._PRODUCTION_CAPABILITY_ISSUER,  # pyright: ignore[reportPrivateUsage]
            metadata=metadata,
            receipt_path=receipt,
            receipt_sha256=receipt_sha256,
            candidate_seal=public_candidate,
            authority=authority,
            repository_root=root,
        )

    capability = issue()
    assert capability.protocol_path == metadata.protocol_path
    assert capability.protocol_sha256 == metadata.protocol_sha256
    assert capability.holdout_fixture_sha256 == metadata.holdout.sha256
    assert capability.receipt_path == receipt.resolve()
    assert capability.receipt_sha256 == receipt_sha256
    assert capability.candidate_head == public_candidate["head"]
    assert capability.runtime_profile == public_candidate["runtime_profile"]
    assert capability.status_records == authority.status_records
    assert capability.development_freeze_sha256 == (
        authority.development_freeze_sha256
    )
    assert capability._authority is authority  # pyright: ignore[reportPrivateUsage]
    assert authority.development_freeze_bytes == freeze.read_bytes()
    assert authority.receipt_bytes == receipt.read_bytes()

    capability._consume(  # pyright: ignore[reportPrivateUsage]
        metadata,
        repository_root=root,
    )
    capability._revalidate_authority(  # pyright: ignore[reportPrivateUsage]
        metadata,
        repository_root=root,
    )
    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="holdout capability",
    ):
        capability._consume(  # pyright: ignore[reportPrivateUsage]
            metadata,
            repository_root=root,
        )

    tampered = issue()
    original_consume = tampered._consume  # pyright: ignore[reportPrivateUsage]
    fixture_open_calls = 0

    def consume(*args: object, **kwargs: object) -> None:
        original_consume(*args, **kwargs)  # type: ignore[arg-type]
        freeze.write_bytes(freeze.read_bytes() + b"\n")

    def load_partition(*args: object, **kwargs: object) -> object:
        nonlocal fixture_open_calls
        del args, kwargs
        fixture_open_calls += 1
        raise AssertionError("fixture must remain unopened")

    monkeypatch.setattr(tampered, "_consume", consume)
    monkeypatch.setattr(
        retrieval_order_workflow,
        "load_retrieval_order_protocol_partition",
        load_partition,
    )
    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError,
        match="candidate seal",
    ):
        retrieval_order_workflow.observe_retrieval_order_partition(
            protocol_path=protocol_path,
            partition="holdout",
            repository_root=root,
            holdout_capability=tampered,
        )
    assert fixture_open_calls == 0


def test_post_receipt_exception_preserves_exact_receipt_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    freeze = root / "benchmarks/retrieval/development-freeze.json"
    receipt = root / "benchmarks/retrieval/holdout-receipt.json"
    artifact = root / "benchmarks/retrieval/artifact.json"
    retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol_path,
        freeze_path=freeze,
        repository_root=root,
    )
    receipt_publication: list[atomic_publication.AtomicPublicationResult] = []
    original_publish = (
        retrieval_order_workflow._publish_or_stop  # pyright: ignore[reportPrivateUsage]
    )

    def publish(**kwargs: object):
        result = original_publish(**kwargs)  # type: ignore[arg-type]
        if Path(cast(Path, kwargs["destination"])).resolve() == receipt.resolve():
            receipt_publication.append(result)
        return result

    def fail_observation(**kwargs: object) -> dict[str, object]:
        del kwargs
        raise retrieval_order_workflow.RetrievalOrderWorkflowError(
            "synthetic post-receipt failure"
        )

    monkeypatch.setattr(retrieval_order_workflow, "_publish_or_stop", publish)
    monkeypatch.setattr(
        retrieval_order_workflow,
        "observe_retrieval_order_partition",
        fail_observation,
    )

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError
    ) as raised:
        retrieval_order_workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            development_freeze_path=freeze,
            receipt_path=receipt,
            artifact_path=artifact,
            repository_root=root,
        )

    assert len(receipt_publication) == 1
    assert raised.value.publication is receipt_publication[0]
    assert raised.value.next_step == "retain_receipt_and_stop"
    assert receipt.exists()
    assert not artifact.exists()


@pytest.mark.parametrize(
    "fault",
    ("write", "file_fsync", "readback", "publish", "directory_fsync"),
)
def test_development_publication_fault_is_absent_or_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    destination = root / "benchmarks/retrieval/development-freeze.json"
    _install_publication_fault(monkeypatch, fault)

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError
    ) as raised:
        retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            freeze_path=destination,
            repository_root=root,
        )

    publication = raised.value.publication
    assert publication is not None
    if fault == "directory_fsync":
        assert publication.output_state == "complete_visible"
        assert publication.publication_outcome == "durability_unconfirmed"
        assert json.loads(destination.read_text(encoding="utf-8"))
    else:
        assert publication.output_state == "absent"
        assert publication.publication_outcome == "failed_before_visibility"
        assert not destination.exists()


@pytest.mark.parametrize(
    "fault",
    ("write", "file_fsync", "readback", "publish", "directory_fsync"),
)
def test_holdout_receipt_fault_never_opens_synthetic_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    root, protocol_path, _, holdout_path = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    freeze = root / "benchmarks/retrieval/development-freeze.json"
    receipt = root / "benchmarks/retrieval/holdout-receipt.json"
    artifact = root / "benchmarks/retrieval/artifact.json"
    retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol_path,
        freeze_path=freeze,
        repository_root=root,
    )
    opened: list[Path] = []
    original_read = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() == holdout_path:
            opened.append(path.resolve())
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    _install_publication_fault(monkeypatch, fault)

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError
    ) as raised:
        retrieval_order_workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            development_freeze_path=freeze,
            receipt_path=receipt,
            artifact_path=artifact,
            repository_root=root,
        )

    publication = raised.value.publication
    assert publication is not None
    assert opened == []
    assert not artifact.exists()
    if fault == "directory_fsync":
        assert publication.output_state == "complete_visible"
        assert receipt.exists()
    else:
        assert publication.output_state == "absent"
        assert not receipt.exists()


@pytest.mark.parametrize(
    "fault",
    ("write", "file_fsync", "readback", "publish", "directory_fsync"),
)
def test_holdout_artifact_fault_retains_exact_receipt_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    root, protocol_path, _, holdout_path = _synthetic_protocol(tmp_path)
    _initialize_repository(root)
    freeze = root / "benchmarks/retrieval/development-freeze.json"
    receipt = root / "benchmarks/retrieval/holdout-receipt.json"
    artifact = root / "benchmarks/retrieval/artifact.json"
    retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol_path,
        freeze_path=freeze,
        repository_root=root,
    )
    original_publish = retrieval_order_workflow.publish_json_no_replace
    calls = 0

    def publish(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        if calls == 2:
            _install_publication_fault(monkeypatch, fault)
        return original_publish(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        retrieval_order_workflow,
        "publish_json_no_replace",
        publish,
    )
    opened: list[Path] = []
    original_read = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() == holdout_path:
            opened.append(path.resolve())
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    with pytest.raises(
        retrieval_order_workflow.RetrievalOrderWorkflowError
    ) as raised:
        retrieval_order_workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            development_freeze_path=freeze,
            receipt_path=receipt,
            artifact_path=artifact,
            repository_root=root,
        )

    assert calls == 2
    assert opened == [holdout_path]
    assert receipt.exists()
    publication = raised.value.publication
    assert publication is not None
    assert publication.output_state == "complete_visible"
    assert publication.publication_outcome == "published"
    assert raised.value.next_step == "retain_receipt_and_stop"
    if fault == "directory_fsync":
        assert artifact.exists()
    else:
        assert not artifact.exists()


def _install_publication_fault(
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    if fault == "readback":
        def invalid_readback(path: Path) -> bytes:
            del path
            return b"{}"

        monkeypatch.setattr(
            atomic_publication,
            "_readback_bytes",
            invalid_readback,
        )
        return

    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise OSError("synthetic publication fault")

    target = {
        "write": "_write_bytes",
        "file_fsync": "_fsync_file",
        "publish": "_publish_no_replace",
        "directory_fsync": "_fsync_directory",
    }[fault]
    monkeypatch.setattr(atomic_publication, target, fail)


def _initialize_repository(root: Path) -> None:
    commands = (
        ("git", "init", "-q"),
        ("git", "config", "user.email", "synthetic@example.invalid"),
        ("git", "config", "user.name", "Synthetic Authority"),
        ("git", "add", "protocol.json", "fixtures"),
        ("git", "commit", "-qm", "synthetic authority"),
    )
    for command in commands:
        subprocess.run(command, cwd=root, check=True)


def _synthetic_protocol(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "synthetic-repository"
    fixture_root = root / "fixtures"
    fixture_root.mkdir(parents=True)
    payload = deepcopy(json.loads(PROTOCOL.read_text(encoding="utf-8")))
    partitions = cast(dict[str, object], payload["partitions"])
    paths: dict[str, Path] = {}
    for name in ("development", "holdout"):
        record = cast(dict[str, object], partitions[name])
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
        paths[name] = destination.resolve()
    protocol_path = root / "protocol.json"
    protocol_path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )
    return (
        root.resolve(),
        protocol_path.resolve(),
        paths["development"],
        paths["holdout"],
    )


def synthetic_fixture_payload(partition: str) -> dict[str, object]:
    cases = [
        _synthetic_case(
            partition=partition,
            label="fts-page",
            strategy="fts",
            locator_kind="page",
        ),
        _synthetic_case(
            partition=partition,
            label="cjk-page",
            strategy="cjk",
            locator_kind="page",
        ),
    ]
    if partition == "development":
        cases.append(
            _synthetic_case(
                partition=partition,
                label="fts-timestamp",
                strategy="fts",
                locator_kind="timestamp_ms",
            )
        )
    return {
        "schema_version": "mke.retrieval_order_cases.v1",
        "partition": partition,
        "workspace_schedules": ["forward_ids", "reverse_ids"],
        "page_sizes": [1, 2, "full"],
        "cases": cases,
    }


def _synthetic_case(
    *,
    partition: str,
    label: str,
    strategy: str,
    locator_kind: str,
) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    projections: list[list[object]] = []
    for index in (1, 2):
        digest = hashlib.sha256(
            f"synthetic-{partition}-{label}-{index}".encode()
        ).hexdigest()
        locator_start = index * 100 if locator_kind == "timestamp_ms" else index
        locator_end = (
            locator_start + 50
            if locator_kind == "timestamp_ms"
            else locator_start
        )
        projection: list[object] = [
            f"sha256:{digest}",
            locator_kind,
            locator_start,
            locator_end,
        ]
        candidates.append(
            {
                "source_id": (
                    f"synthetic-{partition}-{label}-source-{index}"
                ),
                "content_fingerprint": f"sha256:{digest}",
                "asset_sha256": digest,
                "locator_kind": locator_kind,
                "locator_start": locator_start,
                "locator_end": locator_end,
                "text": (
                    "synthetic ordering probe"
                    if strategy == "fts"
                    else "合成排序验证"
                ),
            }
        )
        projections.append(projection)
    return {
        "case_id": f"synthetic-{partition}-{label}",
        "strategy": strategy,
        "query_id": f"synthetic-{partition}-{label}-query",
        "query": (
            "synthetic ordering probe"
            if strategy == "fts"
            else "合成排序验证"
        ),
        "candidates": candidates,
        "expected_stable_projections": projections,
    }


def synthetic_partition_metadata(
    fixture: dict[str, object],
) -> dict[str, object]:
    cases = cast(list[dict[str, object]], fixture["cases"])
    source_ids: set[str] = set()
    coverage: set[str] = set()
    projections: list[list[object]] = []
    for case in cases:
        coverage.add(cast(str, case["strategy"]))
        for candidate in cast(
            list[dict[str, object]],
            case["candidates"],
        ):
            source_ids.add(cast(str, candidate["source_id"]))
            coverage.add(
                "timestamp"
                if candidate["locator_kind"] == "timestamp_ms"
                else "page"
            )
        projections.extend(
            cast(list[list[object]], case["expected_stable_projections"])
        )
    return {
        "case_ids": [case["case_id"] for case in cases],
        "source_ids": sorted(source_ids),
        "query_ids": [case["query_id"] for case in cases],
        "coverage": sorted(coverage),
        "expected_stable_projections": projections,
    }
