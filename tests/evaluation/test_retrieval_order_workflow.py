from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import mke.adapters.sqlite
from mke.evaluation.retrieval_order_workflow import (
    _controlled_sqlite_ids,  # pyright: ignore[reportPrivateUsage]
    main,
    observe_retrieval_order_partition,
    retrieval_runtime_profile,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-order-v1/protocol.json"


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
    assert profile["strategy_revision"] == 1
    assert profile["query_policy_revision"] == 1


def test_current_partition_observation_reproduces_only_order_failure() -> None:
    observation = observe_retrieval_order_partition(
        protocol_path=PROTOCOL,
        partition="development",
        repository_root=ROOT,
    )

    assert observation["integrity_status"] == "passed"
    assert observation["observation_status"] == "failed"
    stable_order_rate = observation["stable_order_rate"]
    assert isinstance(stable_order_rate, float)
    assert stable_order_rate < 1.0
    assert observation["candidate_membership_delta"] == 0
    assert observation["score_hex_delta"] == 0
    assert observation["non_tied_pair_delta"] == 0
    assert observation["pagination_duplicate_or_gap_count"] == 0
    assert observation["strategy_revision"] == 1
    assert observation["query_policy_revision"] == 1


def test_current_cli_records_redacted_failure(
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
    assert status == 1
    assert captured.err == ""
    assert payload == json.loads(record.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "mke.retrieval_order_observation.v1"
    assert payload["phase"] == "current"
    assert payload["integrity_status"] == "passed"
    assert payload["observation_status"] == "failed"
    assert payload["problem"] == "retrieval_order_nondeterministic"
    assert payload["cause"] == "fresh workspace stable projections differ"
    assert payload["next_step"] == "apply_tie_only_stable_order_maintenance"
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
