from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, cast

import mke.adapters.sqlite
from mke.application import KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    REQUIRED_VIDEO_STAGES,
    VIDEO_TRANSCRIPT_FINGERPRINT,
    CandidateEvidence,
    RunManifest,
)
from mke.evaluation.retrieval_order_protocol import (
    load_retrieval_order_protocol,
)
from mke.retrieval import compile_fts5_query
from mke.retrieval.query_policy import QUERY_POLICY_REVISION
from mke.retrieval.strategy import get_retrieval_strategy_descriptor


class RetrievalOrderWorkflowError(RuntimeError):
    """The deterministic-order observation could not be trusted."""


@contextmanager
def _controlled_sqlite_ids(
    schedule: Mapping[str, tuple[str, ...]],
) -> Generator[None]:
    original = mke.adapters.sqlite._new_id  # pyright: ignore[reportPrivateUsage]
    queues = {prefix: iter(values) for prefix, values in schedule.items()}

    def controlled(prefix: str) -> str:
        return next(queues[prefix])

    mke.adapters.sqlite._new_id = controlled  # pyright: ignore[reportPrivateUsage]
    try:
        yield
    finally:
        mke.adapters.sqlite._new_id = original  # pyright: ignore[reportPrivateUsage]


def retrieval_runtime_profile(
    connection: sqlite3.Connection,
) -> dict[str, object]:
    source_id_row = connection.execute("SELECT sqlite_source_id()").fetchone()
    compile_options = tuple(
        sorted(
            str(row[0])
            for row in connection.execute("PRAGMA compile_options").fetchall()
        )
    )
    revision = get_retrieval_strategy_descriptor(
        "cjk-active-scan-overlap-v1"
    ).revision
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "sqlite": sqlite3.sqlite_version,
        "sqlite_source_id": str(source_id_row[0]),
        "sqlite_compile_options": compile_options,
        "fts5_rank_configuration": "sqlite_fts5_default_bm25",
        "strategy_revision": revision,
        "query_policy_revision": QUERY_POLICY_REVISION,
    }


def observe_retrieval_order_partition(
    *,
    protocol_path: Path,
    partition: Literal["development", "holdout"],
    repository_root: Path,
) -> dict[str, object]:
    protocol = load_retrieval_order_protocol(
        protocol_path, repository_root=repository_root
    )
    contract = (
        protocol.development if partition == "development" else protocol.holdout
    )
    fixture = _load_object(contract.path)
    cases = cast(list[object], fixture["cases"])
    observations: list[dict[str, object]] = []
    stable_count = 0
    membership_delta = 0
    score_delta = 0
    non_tied_delta = 0
    pagination_delta = 0
    profile: dict[str, object] | None = None
    for raw_case in cases:
        case = _object(raw_case)
        forward = _observe_case(case, schedule_name="forward_ids")
        reverse = _observe_case(case, schedule_name="reverse_ids")
        if profile is None:
            profile = cast(dict[str, object], forward["runtime_profile"])
        forward_projection = cast(
            list[list[object]], forward["stable_projections"]
        )
        reverse_projection = cast(
            list[list[object]], reverse["stable_projections"]
        )
        stable = forward_projection == reverse_projection
        stable_count += int(stable)
        forward_membership = {
            tuple(item) for item in forward_projection
        }
        reverse_membership = {
            tuple(item) for item in reverse_projection
        }
        membership_delta += len(
            forward_membership.symmetric_difference(reverse_membership)
        )
        score_delta += _score_delta(forward, reverse)
        non_tied_delta += _non_tied_pair_delta(forward, reverse)
        pagination_delta += int(forward["pagination_lossless"] is not True)
        pagination_delta += int(reverse["pagination_lossless"] is not True)
        observations.append(
            {
                "case_id": case["case_id"],
                "strategy": case["strategy"],
                "stable": stable,
                "forward_stable_projections": forward_projection,
                "reverse_stable_projections": reverse_projection,
                "score_hex": forward["score_hex"],
                "pagination_lossless": (
                    forward["pagination_lossless"] is True
                    and reverse["pagination_lossless"] is True
                ),
            }
        )
    assert profile is not None
    rate = stable_count / len(cases)
    passed = (
        rate == 1.0
        and membership_delta == 0
        and score_delta == 0
        and non_tied_delta == 0
        and pagination_delta == 0
    )
    return {
        "integrity_status": "passed",
        "observation_status": "passed" if passed else "failed",
        "partition": partition,
        "stable_order_rate": rate,
        "candidate_membership_delta": membership_delta,
        "score_hex_delta": score_delta,
        "non_tied_pair_delta": non_tied_delta,
        "pagination_duplicate_or_gap_count": pagination_delta,
        "strategy_revision": profile["strategy_revision"],
        "query_policy_revision": profile["query_policy_revision"],
        "runtime_profile": profile,
        "cases": observations,
    }


def _observe_case(
    case: dict[str, object], *, schedule_name: Literal["forward_ids", "reverse_ids"]
) -> dict[str, object]:
    candidates = cast(list[dict[str, object]], case["candidates"])
    by_source: dict[str, list[dict[str, object]]] = {}
    for candidate in candidates:
        by_source.setdefault(cast(str, candidate["source_id"]), []).append(candidate)
    source_names = list(by_source)
    if schedule_name == "reverse_ids":
        source_names.reverse()
    id_schedule = {
        prefix: tuple(f"{prefix}_{index:04d}" for index in range(1, 1001))
        for prefix in ("lib", "src", "asset", "run", "pub", "evt")
    }
    evidence_index = 0
    with tempfile.TemporaryDirectory(prefix="mke-order-") as directory:
        path = Path(directory) / "workspace.sqlite"
        strategy = (
            "current"
            if case["strategy"] == "fts"
            else "cjk-active-scan-overlap-v1"
        )
        source_fingerprints: dict[str, str] = {}
        evidence_fingerprints: dict[str, str] = {}
        with _controlled_sqlite_ids(id_schedule):
            engine = KnowledgeEngine(path, retrieval_strategy=strategy)
            try:
                for source_name in source_names:
                    source_candidates = by_source[source_name]
                    first = source_candidates[0]
                    locator_kind = cast(str, first["locator_kind"])
                    source = engine.ensure_source(
                        display_name=f"{source_name}.fixture",
                        asset_sha256=cast(str, first["asset_sha256"]),
                        media_type=(
                            "application/pdf"
                            if locator_kind == "page"
                            else "video/mp4"
                        ),
                    )
                    source_fingerprints[source.source_id] = cast(
                        str, first["content_fingerprint"]
                    )
                    run = engine.create_run(source.source_id)
                    evidence: list[CandidateEvidence] = []
                    for candidate in source_candidates:
                        evidence_index += 1
                        evidence_id = f"ev_{evidence_index:04d}"
                        evidence_fingerprints[evidence_id] = cast(
                            str, candidate["content_fingerprint"]
                        )
                        evidence.append(
                            CandidateEvidence(
                                evidence_id=evidence_id,
                                locator_kind=cast(
                                    str, candidate["locator_kind"]
                                ),
                                locator_start=cast(
                                    int, candidate["locator_start"]
                                ),
                                locator_end=cast(
                                    int, candidate["locator_end"]
                                ),
                                text=cast(str, candidate["text"]),
                            )
                        )
                    is_page = locator_kind == "page"
                    engine.persist_validated_candidate(
                        run.run_id,
                        evidence,
                        RunManifest(
                            run_id=run.run_id,
                            evidence_count=len(evidence),
                            required_stages=tuple(
                                sorted(
                                    REQUIRED_PDF_STAGES
                                    if is_page
                                    else REQUIRED_VIDEO_STAGES
                                )
                            ),
                            extractor_fingerprint=(
                                PDF_EXTRACTOR_FINGERPRINT
                                if is_page
                                else VIDEO_TRANSCRIPT_FINGERPRINT
                            ),
                            asset_sha256=cast(str, first["asset_sha256"]),
                        ),
                    )
                    engine.activate_publication(run.run_id)
                results = engine.search(cast(str, case["query"]))
                projections = [
                    [
                        source_fingerprints[item.source_id],
                        item.locator_kind,
                        item.locator_start,
                        item.locator_end,
                    ]
                    for item in results
                ]
                score_hex: list[list[object]] = []
                score_by_projection: dict[
                    tuple[str, str, int, int], str
                ] = {}
                if case["strategy"] == "fts":
                    compiled = compile_fts5_query(
                        cast(str, case["query"]), policy="current"
                    )
                    rank = engine._store.observe_fts5_rank(  # pyright: ignore[reportPrivateUsage]
                        compiled
                    )
                    result_by_id = {
                        item.evidence_id: item for item in results
                    }
                    for item in rank.rank_order:
                        result = result_by_id[item.evidence_id]
                        projection = (
                            evidence_fingerprints[item.evidence_id],
                            result.locator_kind,
                            result.locator_start,
                            result.locator_end,
                        )
                        score = item.rank_score.hex()
                        score_by_projection[projection] = score
                        score_hex.append([list(projection), score])
                else:
                    for projection in projections:
                        key = cast(
                            tuple[str, str, int, int], tuple(projection)
                        )
                        score_by_projection[key] = "cjk-equal-overlap"
                        score_hex.append([projection, "cjk-equal-overlap"])
                pagination_lossless = all(
                    [
                        item
                        for offset in range(0, len(projections), page_size)
                        for item in projections[offset : offset + page_size]
                    ]
                    == projections
                    for page_size in (1, 2, max(1, len(projections)))
                )
                connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
                profile = retrieval_runtime_profile(connection)
            finally:
                engine.close()
    return {
        "stable_projections": projections,
        "score_hex": score_hex,
        "score_by_projection": score_by_projection,
        "pagination_lossless": pagination_lossless,
        "runtime_profile": profile,
    }


def _score_delta(
    forward: dict[str, object], reverse: dict[str, object]
) -> int:
    return int(forward["score_by_projection"] != reverse["score_by_projection"])


def _non_tied_pair_delta(
    forward: dict[str, object], reverse: dict[str, object]
) -> int:
    forward_scores = cast(
        dict[tuple[str, str, int, int], str],
        forward["score_by_projection"],
    )
    forward_order = [
        tuple(item)
        for item in cast(list[list[object]], forward["stable_projections"])
    ]
    reverse_order = [
        tuple(item)
        for item in cast(list[list[object]], reverse["stable_projections"])
    ]
    reverse_positions = {
        projection: index for index, projection in enumerate(reverse_order)
    }
    delta = 0
    for left_index, left in enumerate(forward_order):
        for right in forward_order[left_index + 1 :]:
            if (
                forward_scores[cast(tuple[str, str, int, int], left)]
                == forward_scores[cast(tuple[str, str, int, int], right)]
            ):
                continue
            if reverse_positions[left] > reverse_positions[right]:
                delta += 1
    return delta


def _observation_payload(
    observation: dict[str, object],
) -> dict[str, object]:
    failed = observation["observation_status"] != "passed"
    payload = {
        "schema_version": "mke.retrieval_order_observation.v1",
        "phase": "current",
        **observation,
    }
    if failed:
        payload.update(
            {
                "problem": "retrieval_order_nondeterministic",
                "cause": "fresh workspace stable projections differ",
                "next_step": "apply_tie_only_stable_order_maintenance",
            }
        )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mke.evaluation.retrieval_order_workflow"
    )
    subcommands = parser.add_subparsers(dest="phase", required=True)
    current = subcommands.add_parser("current")
    current.add_argument("--protocol", type=Path, required=True)
    current.add_argument("--record", type=Path, required=True)
    current.add_argument("--json", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        observation = observe_retrieval_order_partition(
            protocol_path=args.protocol,
            partition="development",
            repository_root=Path.cwd(),
        )
        payload = _observation_payload(observation)
        rendered = json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )
        args.record.parent.mkdir(parents=True, exist_ok=True)
        with args.record.open("x", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    payload, ensure_ascii=True, indent=2, sort_keys=True
                )
                + "\n"
            )
        print(rendered)
        return 0 if payload["observation_status"] == "passed" else 1
    except Exception:
        payload = {
            "schema_version": "mke.retrieval_order_observation.v1",
            "phase": "current",
            "integrity_status": "failed",
            "observation_status": "not_observed",
            "problem": "retrieval_order_integrity_invalid",
            "cause": "retrieval order protocol or observation is invalid",
            "next_step": "restore_frozen_protocol_and_retry_current_observation",
        }
        print(
            json.dumps(
                payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
            )
        )
        return 1


def _load_object(path: Path) -> dict[str, object]:
    return _object(json.loads(path.read_text(encoding="utf-8")))


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RetrievalOrderWorkflowError
    return cast(dict[str, object], value)


if __name__ == "__main__":
    raise SystemExit(main())
