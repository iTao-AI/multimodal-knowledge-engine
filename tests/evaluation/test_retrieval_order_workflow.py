from __future__ import annotations

import ast
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
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
from mke.retrieval.cjk_active_scan import (
    CjkActiveScanParameters,
    CjkActiveScanSelection,
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


def test_observation_uses_real_application_pagination_for_every_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del tmp_path
    calls: list[tuple[str, str, int, int]] = []
    original = retrieval_order_workflow.KnowledgeEngine.search_evidence_page

    def spy(
        engine: retrieval_order_workflow.KnowledgeEngine,
        query: str,
        *,
        position: int,
        page_size: int,
        authority_validator: Callable[[object], None],
    ):
        calls.append(
            (
                engine._store._retrieval_strategy,  # pyright: ignore[reportPrivateUsage]
                query,
                position,
                page_size,
            )
        )
        return original(
            engine,
            query,
            position=position,
            page_size=page_size,
            authority_validator=authority_validator,
        )

    monkeypatch.setattr(
        retrieval_order_workflow.KnowledgeEngine,
        "search_evidence_page",
        spy,
    )

    observation = observe_retrieval_order_partition(
        protocol_path=PROTOCOL,
        partition="development",
        repository_root=ROOT,
    )

    assert observation["observation_status"] == "passed"
    assert {
        (strategy, page_size)
        for strategy, _, _, page_size in calls
    } == {
        ("current", 1),
        ("current", 2),
        ("current", 3),
        ("cjk-active-scan-overlap-v1", 1),
        ("cjk-active-scan-overlap-v1", 2),
    }
    assert any(
        position == 0 and page_size > 2
        for _, _, position, page_size in calls
    )
    assert any(position > 0 for _, _, position, _ in calls)


@pytest.mark.parametrize(
    "drift",
    (
        "duplicate",
        "gap",
        "reorder",
        "wrong_position",
        "authority",
        "premature_termination",
        "late_termination",
    ),
)
def test_observation_counts_real_pagination_protocol_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    original = retrieval_order_workflow.KnowledgeEngine.search_evidence_page
    injected = False

    def drifted(
        engine: retrieval_order_workflow.KnowledgeEngine,
        query: str,
        *,
        position: int,
        page_size: int,
        authority_validator: Callable[[object], None],
    ):
        nonlocal injected
        page = original(
            engine,
            query,
            position=position,
            page_size=page_size,
            authority_validator=authority_validator,
        )
        target = (
            page_size == 2 and position == 0
            if drift == "reorder"
            else page_size == 1 and position > 0
            if drift in {"authority", "late_termination"}
            else page_size == 1 and position == 0
        )
        if injected or not target:
            return page
        injected = True
        if drift == "duplicate":
            return replace(page, results=(page.results[0], page.results[0]))
        if drift == "gap":
            return replace(page, results=())
        if drift == "reorder":
            return replace(page, results=tuple(reversed(page.results)))
        if drift == "wrong_position":
            return replace(page, position=1)
        if drift == "authority":
            return replace(
                page,
                authority=replace(
                    page.authority,
                    active_set_fingerprint=f"sha256:{'0' * 64}",
                ),
            )
        if drift == "premature_termination":
            return replace(page, more_in_selected_pool=False)
        return replace(page, more_in_selected_pool=True)

    monkeypatch.setattr(
        retrieval_order_workflow.KnowledgeEngine,
        "search_evidence_page",
        drifted,
    )

    observation = observe_retrieval_order_partition(
        protocol_path=protocol_path,
        partition="development",
        repository_root=root,
    )

    assert injected is True
    assert observation["observation_status"] == "failed"
    assert (
        cast(int, observation["pagination_duplicate_or_gap_count"])
        > 0
    )


def test_observation_rejects_matching_extra_primary_score_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    original = retrieval_order_workflow._observe_case  # pyright: ignore[reportPrivateUsage]

    def forged(*args: object, **kwargs: object) -> dict[str, object]:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        scores = cast(
            dict[tuple[str, str, int, int], str],
            result["score_by_projection"],
        )
        scores[(f"sha256:{'f' * 64}", "page", 99, 99)] = next(
            iter(scores.values())
        )
        return result

    monkeypatch.setattr(
        retrieval_order_workflow,
        "_observe_case",
        forged,
    )

    observation = observe_retrieval_order_partition(
        protocol_path=protocol_path,
        partition="development",
        repository_root=root,
    )

    assert observation["observation_status"] == "failed"
    assert cast(int, observation["score_hex_delta"]) > 0


def test_cjk_primary_witness_reads_production_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, calls = _observe_g1_case(monkeypatch)

    assert list(calls.values()) == [2], (
        "G1_SELECTOR_WITNESS_NOT_OBSERVED"
    )
    assert result["score_hex"]


@pytest.mark.parametrize("drift", ("count", "ratio"), ids=("count", "ratio"))
def test_cjk_primary_witness_rejects_order_preserving_tuple_drift(
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    result, _ = _observe_g1_case(monkeypatch, mutation=drift)

    assert result["score_hex"] == [], (
        "G1_ORDER_PRESERVING_TUPLE_DRIFT_FALSE_PASS"
    )
    assert result["score_by_projection"] == {}


@pytest.mark.parametrize(
    "drift",
    ("missing", "extra", "duplicate", "reordered", "projection-mismatch"),
    ids=("missing", "extra", "duplicate", "reordered", "projection-mismatch"),
)
def test_cjk_primary_witness_rejects_inventory_drift(
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    result, _ = _observe_g1_case(monkeypatch, mutation=drift)

    assert result["score_hex"] == [], (
        "G1_SELECTOR_INVENTORY_DRIFT_FALSE_PASS"
    )
    assert result["score_by_projection"] == {}


@pytest.mark.parametrize(
    "drift",
    ("empty", "nonfinite", "boolean-count", "noninteger-count", "nonfloat-ratio"),
    ids=("empty", "nonfinite", "boolean-count", "noninteger-count", "nonfloat-ratio"),
)
def test_cjk_primary_witness_rejects_invalid_numeric_shape(
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    result, _ = _observe_g1_case(monkeypatch, mutation=drift)

    assert result["score_hex"] == [], (
        "G1_INVALID_NUMERIC_SHAPE_FALSE_PASS"
    )
    assert result["score_by_projection"] == {}


@pytest.mark.parametrize(
    "drift",
    (
        "negative-count",
        "zero-count",
        "count-above-term-count",
        "ratio-above-one",
        "below-count-threshold",
        "below-ratio-threshold",
        "count-ratio-inconsistent",
        "matched-terms-inconsistent",
        "matched-terms-list",
        "matched-terms-unknown",
        "matched-terms-reversed",
    ),
    ids=(
        "negative-count",
        "zero-count",
        "count-above-term-count",
        "ratio-above-one",
        "below-count-threshold",
        "below-ratio-threshold",
        "count-ratio-inconsistent",
        "matched-terms-inconsistent",
        "matched-terms-list",
        "matched-terms-unknown",
        "matched-terms-reversed",
    ),
)
def test_cjk_primary_witness_rejects_impossible_tuple(
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    result, _ = _observe_g1_case(monkeypatch, mutation=drift)

    assert result["score_hex"] == [], "G1_IMPOSSIBLE_TUPLE_FALSE_PASS"
    assert result["score_by_projection"] == {}


def test_cjk_primary_witness_returns_structured_failure_without_pair_comparison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    original_selector = mke.adapters.sqlite.SQLiteStore._select_cjk_active_scan  # pyright: ignore[reportPrivateUsage]
    calls: dict[mke.adapters.sqlite.SQLiteStore, int] = {}

    def selector(
        store: mke.adapters.sqlite.SQLiteStore,
        terms: tuple[str, ...],
        *,
        parameters: CjkActiveScanParameters,
    ) -> CjkActiveScanSelection:
        selection = original_selector(
            store,
            terms,
            parameters=parameters,
        )
        calls[store] = calls.get(store, 0) + 1
        if calls[store] == 2:
            return _mutate_g1_selection(selection, terms, "nonfinite")
        return selection

    monkeypatch.setattr(
        mke.adapters.sqlite.SQLiteStore,
        "_select_cjk_active_scan",
        selector,
    )
    monkeypatch.setattr(
        retrieval_order_workflow,
        "_pagination_lossless",
        _g1_pagination_lossless,
    )
    original_pair_delta = (
        retrieval_order_workflow._non_tied_pair_delta  # pyright: ignore[reportPrivateUsage]
    )

    def guarded_pair_delta(
        forward: dict[str, object],
        reverse: dict[str, object],
    ) -> int:
        if (
            forward["score_by_projection"] == {}
            or reverse["score_by_projection"] == {}
        ):
            raise AssertionError("G1_INVALID_WITNESS_RAISED_KEY_ERROR")
        return original_pair_delta(forward, reverse)

    monkeypatch.setattr(
        retrieval_order_workflow,
        "_non_tied_pair_delta",
        guarded_pair_delta,
    )

    observation = observe_retrieval_order_partition(
        protocol_path=protocol_path,
        partition="development",
        repository_root=root,
    )

    assert observation["observation_status"] == "failed", (
        "G1_INVALID_WITNESS_RAISED_KEY_ERROR"
    )
    assert cast(int, observation["score_hex_delta"]) > 0


def test_cjk_primary_witness_accepts_valid_frozen_tie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, calls = _observe_g1_case(monkeypatch)

    assert list(calls.values()) == [2], (
        "G1_VALID_TIE_NOT_BOUND_TO_SELECTOR"
    )
    assert {
        cast(str, record[1])
        for record in cast(list[list[object]], result["score_hex"])
    } == {"cjk-equal-overlap"}


def test_fts_observation_does_not_call_cjk_primary_witness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _synthetic_case(
        partition="development",
        label="fts-primary-control",
        strategy="fts",
        locator_kind="page",
    )
    expected = tuple(
        tuple(cast(list[object], item))
        for item in cast(
            list[object],
            case["expected_stable_projections"],
        )
    )

    def forbidden(*args: object, **kwargs: object) -> CjkActiveScanSelection:
        del args, kwargs
        raise AssertionError("FTS must not call the CJK primary witness")

    monkeypatch.setattr(
        mke.adapters.sqlite.SQLiteStore,
        "_select_cjk_active_scan",
        forbidden,
    )
    monkeypatch.setattr(
        retrieval_order_workflow,
        "_pagination_lossless",
        _g1_pagination_lossless,
    )

    result = retrieval_order_workflow._observe_case(  # pyright: ignore[reportPrivateUsage]
        case,
        schedule_name="forward_ids",
        expected_projections=cast(
            tuple[tuple[str, str, int, int], ...],
            expected,
        ),
    )

    assert result["score_hex"]
    assert result["score_by_projection"]


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


@pytest.mark.parametrize(
    "destination_kind",
    ("regular", "dangling", "directory"),
    ids=("regular", "dangling", "directory"),
)
def test_development_preflight_rejects_visible_destination_before_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    destination_kind: str,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    destination = root / "benchmarks/retrieval/development-freeze.json"
    destination.parent.mkdir(parents=True)
    if destination_kind == "regular":
        destination.write_bytes(b"retained development authority")
    elif destination_kind == "dangling":
        destination.symlink_to("missing-development-freeze.json")
    else:
        destination.mkdir()
    before = destination.lstat()
    retained_bytes = (
        destination.read_bytes() if destination_kind == "regular" else None
    )
    retained_link = (
        destination.readlink() if destination_kind == "dangling" else None
    )
    calls = _install_l3_authority_barriers(monkeypatch)

    error: Exception | None = None
    try:
        retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            freeze_path=destination,
            repository_root=root,
        )
    except Exception as caught:
        error = caught

    assert calls == [], "L3_DEVELOPMENT_DESTINATION_PREFLIGHT_LATE"
    assert isinstance(
        error,
        retrieval_order_workflow.RetrievalOrderWorkflowError,
    )
    after = destination.lstat()
    assert (after.st_dev, after.st_ino, after.st_mode) == (
        before.st_dev,
        before.st_ino,
        before.st_mode,
    )
    if retained_bytes is not None:
        assert destination.read_bytes() == retained_bytes
    if retained_link is not None:
        assert destination.readlink() == retained_link


@pytest.mark.parametrize(
    "alias_kind",
    ("protocol-final", "protocol-parent", "output-parent"),
    ids=("protocol-final", "protocol-parent", "output-parent"),
)
def test_development_preflight_rejects_protocol_and_output_aliases_before_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    alias_kind: str,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    requested_protocol = protocol_path
    destination = root / "benchmarks/retrieval/development-freeze.json"
    if alias_kind == "protocol-final":
        requested_protocol = root / "protocol-alias.json"
        requested_protocol.symlink_to(protocol_path.name)
    elif alias_kind == "protocol-parent":
        alias_root = tmp_path / "repository-alias"
        alias_root.symlink_to(root, target_is_directory=True)
        requested_protocol = alias_root / protocol_path.name
    else:
        retained_parent = root / "retained-output-parent"
        retained_parent.mkdir()
        alias_parent = root / "benchmarks"
        alias_parent.symlink_to(retained_parent, target_is_directory=True)
        destination = alias_parent / "development-freeze.json"
    calls = _install_l3_authority_barriers(monkeypatch)

    error: Exception | None = None
    try:
        retrieval_order_workflow._run_development(  # pyright: ignore[reportPrivateUsage]
            protocol_path=requested_protocol,
            freeze_path=destination,
            repository_root=root,
        )
    except Exception as caught:
        error = caught

    assert calls == [], "L3_DEVELOPMENT_ALIAS_PREFLIGHT_LATE"
    assert isinstance(
        error,
        retrieval_order_workflow.RetrievalOrderWorkflowError,
    )
    assert not destination.exists()


@pytest.mark.parametrize(
    "output_case",
    (
        "receipt-regular",
        "receipt-dangling",
        "receipt-final-alias",
        "receipt-parent-alias",
        "artifact-regular",
        "artifact-dangling",
        "artifact-final-alias",
        "artifact-parent-alias",
    ),
    ids=(
        "receipt-regular",
        "receipt-dangling",
        "receipt-final-alias",
        "receipt-parent-alias",
        "artifact-regular",
        "artifact-dangling",
        "artifact-final-alias",
        "artifact-parent-alias",
    ),
)
def test_holdout_preflight_rejects_visible_or_aliased_outputs_before_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_case: str,
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    output_parent = root / "benchmarks/retrieval"
    kind = output_case.split("-", 1)[1]
    if kind == "parent-alias":
        retained_parent = root / "retained-retrieval"
        retained_parent.mkdir()
        output_parent.parent.mkdir()
        output_parent.symlink_to(retained_parent, target_is_directory=True)
    else:
        output_parent.mkdir(parents=True)
    freeze = output_parent / "development-freeze.json"
    freeze.write_bytes(b"synthetic retained freeze")
    receipt = output_parent / "holdout-receipt.json"
    artifact = output_parent / "artifact.json"
    selected = receipt if output_case.startswith("receipt") else artifact
    if kind == "regular":
        selected.write_bytes(b"retained output authority")
    elif kind == "dangling":
        selected.symlink_to(f"missing-{selected.name}")
    elif kind == "final-alias":
        retained = selected.with_name(f"retained-{selected.name}")
        retained.write_bytes(b"retained output authority")
        selected.symlink_to(retained.name)
    calls = _install_l3_authority_barriers(monkeypatch)

    error: Exception | None = None
    try:
        retrieval_order_workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
            protocol_path=protocol_path,
            development_freeze_path=freeze,
            receipt_path=receipt,
            artifact_path=artifact,
            repository_root=root,
        )
    except Exception as caught:
        error = caught

    assert calls == [], "L3_HOLDOUT_OUTPUT_PREFLIGHT_LATE"
    assert isinstance(
        error,
        retrieval_order_workflow.RetrievalOrderWorkflowError,
    )
    if kind in {"regular", "final-alias"}:
        assert os.path.lexists(selected)


def test_case_alias_is_not_canonical_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
    cased_root = root.with_name("SyntheticRepository")
    root.rename(cased_root)
    alias_root = cased_root.with_name("syntheticrepository")
    try:
        same_directory = alias_root.samefile(cased_root)
    except FileNotFoundError:
        same_directory = False
    if not same_directory:
        pytest.skip("filesystem does not provide a lexical case alias")
    canonical_protocol = (
        cased_root / "tests/fixtures/retrieval-order-v1/protocol.json"
    )
    canonical_protocol.parent.mkdir(parents=True)
    (alias_root / protocol_path.name).rename(canonical_protocol)
    requested_protocol = (
        alias_root / "tests/fixtures/retrieval-order-v1/protocol.json"
    )
    requested_output = (
        alias_root
        / "benchmarks/retrieval/retrieval-order-v1-development-freeze.json"
    )
    calls = _install_l3_authority_barriers(monkeypatch)
    monkeypatch.chdir(cased_root)

    status = main(
        [
            "development",
            "--protocol",
            str(requested_protocol),
            "--record-development-freeze",
            str(requested_output),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert calls == [], "L3_CASE_ALIAS_FALSE_CANONICAL"
    assert status == 1
    assert payload["canonical"] is False


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
    assert opened
    assert set(opened) == {holdout_path}
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

    opened_before_repeat = list(opened)
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
    assert opened == opened_before_repeat


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
    if (
        mutation_point == "staged_before_receipt"
        or mutation_point.startswith("consume_")
    ):
        assert opened == 0
    else:
        assert opened >= 1
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
    assert opened
    assert set(opened) == {holdout_path}
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


def _install_l3_authority_barriers(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    calls: list[str] = []

    def barrier(name: str):
        def fail(*args: object, **kwargs: object) -> object:
            del args, kwargs
            calls.append(name)
            raise RuntimeError(f"L3 barrier entered: {name}")

        return fail

    for name in (
        "load_retrieval_order_protocol_metadata",
        "_candidate_seal",
        "observe_retrieval_order_partition",
        "build_development_freeze",
        "build_holdout_receipt",
        "build_retrieval_order_artifact",
        "_publish_or_stop",
    ):
        monkeypatch.setattr(
            retrieval_order_workflow,
            name,
            barrier(name),
        )
    return calls


def _observe_g1_case(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mutation: str | None = None,
) -> tuple[
    dict[str, object],
    dict[mke.adapters.sqlite.SQLiteStore, int],
]:
    case = _synthetic_case(
        partition="development",
        label="cjk-primary-witness",
        strategy="cjk",
        locator_kind="page",
    )
    expected = cast(
        tuple[tuple[str, str, int, int], ...],
        tuple(
            tuple(cast(list[object], item))
            for item in cast(
                list[object],
                case["expected_stable_projections"],
            )
        ),
    )
    original = mke.adapters.sqlite.SQLiteStore._select_cjk_active_scan  # pyright: ignore[reportPrivateUsage]
    calls: dict[mke.adapters.sqlite.SQLiteStore, int] = {}

    def selector(
        store: mke.adapters.sqlite.SQLiteStore,
        terms: tuple[str, ...],
        *,
        parameters: CjkActiveScanParameters,
    ) -> CjkActiveScanSelection:
        selection = original(store, terms, parameters=parameters)
        calls[store] = calls.get(store, 0) + 1
        if calls[store] == 2 and mutation is not None:
            return _mutate_g1_selection(selection, terms, mutation)
        return selection

    monkeypatch.setattr(
        mke.adapters.sqlite.SQLiteStore,
        "_select_cjk_active_scan",
        selector,
    )
    monkeypatch.setattr(
        retrieval_order_workflow,
        "_pagination_lossless",
        _g1_pagination_lossless,
    )

    result = retrieval_order_workflow._observe_case(  # pyright: ignore[reportPrivateUsage]
        case,
        schedule_name="forward_ids",
        expected_projections=expected,
    )
    return result, calls


def _mutate_g1_selection(
    selection: CjkActiveScanSelection,
    terms: tuple[str, ...],
    mutation: str,
) -> CjkActiveScanSelection:
    results = list(selection.results)
    if mutation == "empty":
        return replace(selection, results=())
    first = results[0]
    if mutation == "missing":
        results.pop()
    elif mutation == "extra":
        results.append(
            replace(first, document_id=f"sha256:{'f' * 64}")
        )
    elif mutation == "duplicate":
        results.insert(1, first)
    elif mutation == "reordered":
        results.reverse()
    elif mutation == "projection-mismatch":
        results[0] = replace(
            first,
            document_id=f"sha256:{'e' * 64}",
        )
    elif mutation == "count":
        count = first.overlap_count - 1
        results[0] = replace(
            first,
            overlap_count=count,
            overlap_ratio=count / len(terms),
            matched_terms=first.matched_terms[:-1],
        )
    elif mutation == "ratio":
        results[0] = replace(first, overlap_ratio=0.75)
    elif mutation == "nonfinite":
        results[0] = replace(first, overlap_ratio=float("nan"))
    elif mutation == "boolean-count":
        results[0] = replace(first, overlap_count=True)
    elif mutation == "noninteger-count":
        results[0] = replace(first, overlap_count=1.5)
    elif mutation == "nonfloat-ratio":
        results[0] = replace(first, overlap_ratio=1)
    elif mutation == "negative-count":
        results[0] = replace(first, overlap_count=-1)
    elif mutation == "zero-count":
        results[0] = replace(first, overlap_count=0)
    elif mutation == "count-above-term-count":
        results[0] = replace(first, overlap_count=len(terms) + 1)
    elif mutation == "ratio-above-one":
        results[0] = replace(first, overlap_ratio=1.25)
    elif mutation == "below-count-threshold":
        results[0] = replace(
            first,
            overlap_count=1,
            overlap_ratio=1 / len(terms),
            matched_terms=first.matched_terms[:1],
        )
    elif mutation == "below-ratio-threshold":
        results[0] = replace(
            first,
            overlap_count=2,
            overlap_ratio=0.25,
            matched_terms=first.matched_terms[:2],
        )
    elif mutation == "count-ratio-inconsistent":
        results[0] = replace(first, overlap_ratio=0.5)
    elif mutation == "matched-terms-inconsistent":
        results[0] = replace(
            first,
            matched_terms=(terms[0],) * first.overlap_count,
        )
    elif mutation == "matched-terms-list":
        results[0] = replace(
            first,
            matched_terms=cast(
                tuple[str, ...],
                list(first.matched_terms),
            ),
        )
    elif mutation == "matched-terms-unknown":
        results[0] = replace(
            first,
            matched_terms=(
                *first.matched_terms[:-1],
                "unknown-compiled-term",
            ),
        )
    elif mutation == "matched-terms-reversed":
        results[0] = replace(
            first,
            matched_terms=tuple(reversed(first.matched_terms)),
        )
    else:
        raise AssertionError(f"unsupported G1 mutation: {mutation}")
    return replace(selection, results=tuple(results))


def _g1_pagination_lossless(
    *args: object,
    **kwargs: object,
) -> bool:
    del args, kwargs
    return True


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
    ordered = list(zip(candidates, projections, strict=True))
    if strategy == "fts":
        ordered.sort(
            key=lambda item: (
                item[0]["locator_start"],
                item[0]["locator_kind"],
                item[0]["locator_end"],
                item[0]["asset_sha256"],
            )
        )
    else:
        ordered.sort(
            key=lambda item: (
                item[0]["content_fingerprint"],
                item[0]["locator_kind"],
                item[0]["locator_start"],
                item[0]["locator_end"],
            )
        )
    return {
        "case_id": f"synthetic-{partition}-{label}",
        "strategy": strategy,
        "query_id": f"synthetic-{partition}-{label}-query",
        "query": (
            "synthetic ordering probe"
            if strategy == "fts"
            else "合成排序验证"
        ),
        "candidates": [item[0] for item in ordered],
        "expected_stable_projections": [item[1] for item in ordered],
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
