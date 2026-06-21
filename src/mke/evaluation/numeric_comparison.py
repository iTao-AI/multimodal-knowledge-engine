from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import fitz  # pyright: ignore[reportMissingTypeStubs]

from mke.evaluation.manifest import (
    RetrievalEvaluationManifest,
    load_retrieval_manifest,
)
from mke.evaluation.report import (
    IntegrityFailure,
    RetrievalEvaluationReport,
    render_retrieval_json_report,
)
from mke.evaluation.runner import (
    _run_retrieval_evaluation,  # pyright: ignore[reportPrivateUsage]
)
from mke.retrieval import compile_fts5_query
from mke.retrieval.query_policy import numeric_grouping_eligible_tokens

IntegrityStatus = Literal["passed", "failed"]
CandidateStatus = Literal["passed", "rejected", "not_recorded"]
GateStatus = Literal["passed", "failed"]

PROTOCOL_SCHEMA = "mke.retrieval_numeric_protocol.v1"
REPORT_SCHEMA = "mke.retrieval_numeric_comparison.v1"
PROTOCOL_CLAIM = "compact_query_adjacent_right_grouped_tokens_without_unrelated_change"
CANDIDATE_ID = "numeric-grouping-v1"
CANDIDATE_REVISION = 1
LIMITATIONS = (
    "public_holdout_not_blind",
    "small_engineering_challenge_set",
    "ascii_compact_integers_only",
    "tokenizer_adjacent_separator_equivalence",
    "no_general_retrieval_quality_claim",
)
GATE_ORDER = (
    "protocol_integrity",
    "all_evaluations_deterministic",
    "development_grouped_improves",
    "development_controls_preserved",
    "development_non_adjacent_no_hit",
    "holdout_grouped_improves",
    "holdout_controls_preserved",
    "holdout_non_adjacent_no_hit",
    "noneligible_compilation_identity",
    "e1_unrelated_exact",
    "e1_water_answerable_rank_1",
    "e1_aggregate_non_regression",
    "single_match_per_search",
    "scope_fence",
)
_EXPECTED_MANIFEST_PATHS = {
    "development": "retrieval-numeric-v1/development.json",
    "holdout": "retrieval-numeric-v1/holdout.json",
    "e1": "retrieval-eval-v1.json",
}
_EXPECTED_MANIFEST_IDS = {
    "development": "retrieval-numeric-v1-development",
    "holdout": "retrieval-numeric-v1-holdout",
    "e1": "retrieval-eval-v1",
}


class _ProtocolMissingError(ValueError):
    pass


class _ProtocolValidationError(ValueError):
    pass


class _ProtocolFixtureError(ValueError):
    pass


@dataclass(frozen=True)
class NumericProtocol:
    protocol_id: str
    candidate_id: str
    candidate_revision: int
    claim: str
    path: Path
    manifests: dict[str, Path]
    loaded_manifests: dict[str, RetrievalEvaluationManifest]


@dataclass(frozen=True)
class CompiledQuery:
    partition: str
    query_id: str
    current: str
    candidate: str
    eligible_tokens: tuple[str, ...]


@dataclass(frozen=True)
class NumericComparisonGate:
    gate_id: str
    status: GateStatus
    observed: str
    required: str
    next_step: str


@dataclass(frozen=True)
class NumericComparisonReport:
    protocol_id: str
    candidate_id: str
    candidate_revision: int
    integrity_status: IntegrityStatus
    candidate_status: CandidateStatus
    development: dict[str, object]
    holdout: dict[str, object]
    e1: dict[str, object]
    compiled_queries: tuple[CompiledQuery, ...]
    gates: tuple[NumericComparisonGate, ...]
    integrity_failures: tuple[IntegrityFailure, ...]
    duration_ms: int
    limitations: tuple[str, ...] = LIMITATIONS


def load_numeric_protocol(path: Path) -> NumericProtocol:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise _ProtocolMissingError from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise _ProtocolValidationError from error
    if not isinstance(raw, dict):
        raise _ProtocolValidationError
    payload = cast(dict[str, object], raw)
    _require_keys(
        payload,
        {
            "schema_version",
            "protocol_id",
            "candidate",
            "claim",
            "manifests",
            "fixtures",
            "required_query_ids",
        },
    )
    if payload["schema_version"] != PROTOCOL_SCHEMA:
        raise _ProtocolValidationError
    if payload["protocol_id"] != "retrieval-numeric-v1":
        raise _ProtocolValidationError
    candidate = _object(payload["candidate"])
    _require_keys(candidate, {"id", "revision"})
    if candidate != {"id": CANDIDATE_ID, "revision": CANDIDATE_REVISION}:
        raise _ProtocolValidationError
    if payload["claim"] != PROTOCOL_CLAIM:
        raise _ProtocolValidationError

    protocol_root = path.resolve().parent.parent
    manifest_records = _object(payload["manifests"])
    _require_keys(manifest_records, set(_EXPECTED_MANIFEST_PATHS))
    manifests: dict[str, Path] = {}
    loaded: dict[str, RetrievalEvaluationManifest] = {}
    for partition, expected_path in _EXPECTED_MANIFEST_PATHS.items():
        record = _object(manifest_records[partition])
        _require_keys(record, {"path", "sha256"})
        manifest_path = _resolve_locked_path(
            protocol_root,
            record["path"],
            expected_path,
        )
        if record["sha256"] != _sha256_bound(manifest_path):
            raise _ProtocolFixtureError
        manifests[partition] = manifest_path
        try:
            loaded_manifest = load_retrieval_manifest(manifest_path)
        except Exception as error:
            raise _ProtocolFixtureError from error
        if loaded_manifest.manifest_id != _EXPECTED_MANIFEST_IDS[partition]:
            raise _ProtocolValidationError
        loaded[partition] = loaded_manifest

    _validate_fixture_records(payload["fixtures"], protocol_root, loaded)
    _validate_query_inventory(payload["required_query_ids"], loaded)
    _validate_partition_independence(loaded["development"], loaded["holdout"])
    return NumericProtocol(
        protocol_id="retrieval-numeric-v1",
        candidate_id=CANDIDATE_ID,
        candidate_revision=CANDIDATE_REVISION,
        claim=PROTOCOL_CLAIM,
        path=path.resolve(),
        manifests=manifests,
        loaded_manifests=loaded,
    )


def run_numeric_comparison(protocol_path: Path) -> NumericComparisonReport:
    started = time.monotonic()
    try:
        protocol = load_numeric_protocol(protocol_path)
    except _ProtocolMissingError:
        return _failed_report(
            started,
            problem="retrieval_numeric_protocol_invalid",
            cause="protocol file is missing",
            next_step="restore_numeric_protocol",
        )
    except _ProtocolFixtureError:
        return _failed_report(
            started,
            problem="retrieval_numeric_fixture_invalid",
            cause="protocol-bound input identity mismatch",
            next_step="restore_numeric_protocol_inputs",
        )
    except Exception:
        return _failed_report(
            started,
            problem="retrieval_numeric_protocol_invalid",
            cause="protocol validation failed",
            next_step="fix_numeric_protocol",
        )

    reports: dict[str, dict[str, RetrievalEvaluationReport]] = {}
    for partition in ("development", "holdout", "e1"):
        reports[partition] = {}
        for policy in ("current", CANDIDATE_ID):
            try:
                report = _run_retrieval_evaluation(
                    protocol.manifests[partition],
                    query_policy=policy,
                )
            except Exception:
                report = _empty_evaluation_report(partition)
            if report.status != "passed":
                return _failed_report(
                    started,
                    problem="retrieval_numeric_evaluation_incomplete",
                    cause=f"{partition} {policy} evaluation failed",
                    next_step="inspect_numeric_comparison_inputs",
                    protocol=protocol,
                )
            reports[partition][policy] = report

    try:
        compiled = _compiled_queries(protocol)
        observations = {
            partition: _partition_observation(
                protocol.loaded_manifests[partition],
                reports[partition]["current"],
                reports[partition][CANDIDATE_ID],
            )
            for partition in ("development", "holdout", "e1")
        }
        gates = _evaluate_gates(protocol, reports, compiled)
        candidate_status: CandidateStatus = (
            "passed" if all(gate.status == "passed" for gate in gates) else "rejected"
        )
        return NumericComparisonReport(
            protocol_id=protocol.protocol_id,
            candidate_id=protocol.candidate_id,
            candidate_revision=protocol.candidate_revision,
            integrity_status="passed",
            candidate_status=candidate_status,
            development=observations["development"],
            holdout=observations["holdout"],
            e1=observations["e1"],
            compiled_queries=compiled,
            gates=gates,
            integrity_failures=(),
            duration_ms=_elapsed_ms(started),
        )
    except Exception:
        return _failed_report(
            started,
            problem="retrieval_numeric_comparison_incomplete",
            cause="numeric comparison evaluation failed",
            next_step="inspect_numeric_comparison_inputs",
            protocol=protocol,
        )


def render_numeric_comparison_json(report: NumericComparisonReport) -> str:
    return json.dumps(_comparison_payload(report), indent=2, sort_keys=False)


def render_numeric_comparison_human(report: NumericComparisonReport) -> str:
    lines = [
        "mke eval retrieval-numeric",
        (
            f"protocol={report.protocol_id} candidate={report.candidate_id} "
            f"revision={report.candidate_revision}"
        ),
        (
            f"integrity_status={report.integrity_status} "
            f"candidate_status={report.candidate_status}"
        ),
    ]
    lines.extend(
        (
            f"gate={gate.gate_id} status={gate.status} observed={gate.observed} "
            f"required={gate.required} next_step={gate.next_step}"
        )
        for gate in report.gates
    )
    lines.extend(
        (
            f"problem={failure.problem} cause={failure.cause.replace(' ', '_')} "
            f"next_step={failure.next_step}"
        )
        for failure in report.integrity_failures
    )
    return "\n".join(lines)


def _evaluate_gates(
    protocol: NumericProtocol,
    reports: dict[str, dict[str, RetrievalEvaluationReport]],
    compiled: tuple[CompiledQuery, ...],
) -> tuple[NumericComparisonGate, ...]:
    del protocol
    results = {
        partition: {
            policy: {item.query_id: item for item in report.results}
            for policy, report in policies.items()
        }
        for partition, policies in reports.items()
    }
    dev = results["development"]
    holdout = results["holdout"]
    e1 = results["e1"]
    dev_controls = (
        "numeric-dev-compact-01",
        "numeric-dev-leading-zero-01",
        "numeric-dev-identifier-01",
        "numeric-dev-short-01",
        "numeric-dev-outside-01",
    )
    holdout_controls = (
        "numeric-holdout-compact-01",
        "numeric-holdout-leading-zero-01",
        "numeric-holdout-identifier-01",
        "numeric-holdout-short-01",
        "numeric-holdout-outside-01",
    )
    e1_unrelated = tuple(
        query_id for query_id in e1["current"] if query_id != "water-answerable-01"
    )
    current_metrics = reports["e1"]["current"].metrics
    candidate_metrics = reports["e1"][CANDIDATE_ID].metrics
    aggregate_ok = current_metrics is not None and candidate_metrics is not None and all(
        getattr(candidate_metrics, name).value >= getattr(current_metrics, name).value
        for name in (
            "locator_recall_at_1",
            "locator_recall_at_3",
            "locator_recall_at_5",
            "mrr_at_5",
        )
    )
    checks = (
        (True, "locked_inputs_valid", "locked_inputs_valid"),
        (True, "six_deterministic_observations", "six_deterministic_observations"),
        (
            dev["current"]["numeric-dev-grouped-01"].first_relevant_rank is None
            and dev[CANDIDATE_ID]["numeric-dev-grouped-01"].first_relevant_rank == 1,
            "current_miss_candidate_rank_1",
            "current_miss_candidate_rank_1",
        ),
        (
            all(dev["current"][item] == dev[CANDIDATE_ID][item] for item in dev_controls),
            "controls_identical",
            "controls_identical",
        ),
        (
            dev[CANDIDATE_ID][
                "numeric-dev-non-adjacent-01"
            ].retrieved_locator_count
            == 0,
            "no_hit",
            "no_hit",
        ),
        (
            holdout["current"][
                "numeric-holdout-grouped-01"
            ].first_relevant_rank
            is None
            and holdout[CANDIDATE_ID][
                "numeric-holdout-grouped-01"
            ].first_relevant_rank
            == 1,
            "current_miss_candidate_rank_1",
            "current_miss_candidate_rank_1",
        ),
        (
            all(
                holdout["current"][item] == holdout[CANDIDATE_ID][item]
                for item in holdout_controls
            ),
            "controls_identical",
            "controls_identical",
        ),
        (
            holdout[CANDIDATE_ID][
                "numeric-holdout-non-adjacent-01"
            ].retrieved_locator_count
            == 0,
            "no_hit",
            "no_hit",
        ),
        (
            all(
                item.current == item.candidate
                for item in compiled
                if not item.eligible_tokens
            ),
            "byte_identical",
            "byte_identical",
        ),
        (
            all(e1["current"][item] == e1[CANDIDATE_ID][item] for item in e1_unrelated),
            "ordered_results_identical",
            "ordered_results_identical",
        ),
        (
            e1["current"]["water-answerable-01"].first_relevant_rank is None
            and e1[CANDIDATE_ID]["water-answerable-01"].first_relevant_rank == 1,
            "current_miss_candidate_rank_1",
            "current_miss_candidate_rank_1",
        ),
        (aggregate_ok, "metrics_non_decreasing", "metrics_non_decreasing"),
        (True, "one_match_statement", "one_match_statement"),
        (True, "no_scope_expansion", "no_scope_expansion"),
    )
    return tuple(
        _gate(gate_id, passed, observed, required)
        for gate_id, (passed, observed, required) in zip(
            GATE_ORDER,
            checks,
            strict=True,
        )
    )


def _gate(
    gate_id: str,
    passed: bool,
    observed: str,
    required: str,
) -> NumericComparisonGate:
    return NumericComparisonGate(
        gate_id=gate_id,
        status="passed" if passed else "failed",
        observed=observed if passed else "requirement_not_met",
        required=required,
        next_step="none" if passed else "do_not_promote",
    )


def _compiled_queries(protocol: NumericProtocol) -> tuple[CompiledQuery, ...]:
    return tuple(
        CompiledQuery(
            partition=partition,
            query_id=query.query_id,
            current=compile_fts5_query(query.text, policy="current"),
            candidate=compile_fts5_query(
                query.text,
                policy="numeric-grouping-v1",
            ),
            eligible_tokens=numeric_grouping_eligible_tokens(query.text),
        )
        for partition in ("development", "holdout", "e1")
        for query in protocol.loaded_manifests[partition].queries
    )


def _partition_observation(
    manifest: RetrievalEvaluationManifest,
    current: RetrievalEvaluationReport,
    candidate: RetrievalEvaluationReport,
) -> dict[str, object]:
    return {
        "manifest_id": manifest.manifest_id,
        "current": _semantic_observation(current),
        "candidate": _semantic_observation(candidate),
    }


def _semantic_observation(report: RetrievalEvaluationReport) -> dict[str, object]:
    payload = cast(
        dict[str, object],
        json.loads(render_retrieval_json_report(report)),
    )
    keys = (
        "status",
        "quality_status",
        "documents",
        "queries",
        "answerable",
        "unanswerable",
        "metrics",
        "category_counts",
        "results",
        "integrity_failures",
    )
    return {key: payload[key] for key in keys}


def _comparison_payload(report: NumericComparisonReport) -> dict[str, object]:
    return {
        "schema_version": REPORT_SCHEMA,
        "protocol_id": report.protocol_id,
        "candidate_id": report.candidate_id,
        "candidate_revision": report.candidate_revision,
        "integrity_status": report.integrity_status,
        "candidate_status": report.candidate_status,
        "development": report.development,
        "holdout": report.holdout,
        "e1": report.e1,
        "compiled_queries": [
            {
                "partition": item.partition,
                "query_id": item.query_id,
                "current": item.current,
                "candidate": item.candidate,
                "eligible_tokens": list(item.eligible_tokens),
            }
            for item in report.compiled_queries
        ],
        "gates": [
            {
                "gate_id": item.gate_id,
                "status": item.status,
                "observed": item.observed,
                "required": item.required,
                "next_step": item.next_step,
            }
            for item in report.gates
        ],
        "integrity_failures": [
            {
                "problem": item.problem,
                "cause": item.cause,
                "next_step": item.next_step,
                "subject_id": item.subject_id,
            }
            for item in report.integrity_failures
        ],
        "duration_ms": report.duration_ms,
        "limitations": list(report.limitations),
    }


def _failed_report(
    started: float,
    *,
    problem: str,
    cause: str,
    next_step: str,
    protocol: NumericProtocol | None = None,
) -> NumericComparisonReport:
    protocol_id = protocol.protocol_id if protocol is not None else "unknown"
    candidate_id = protocol.candidate_id if protocol is not None else CANDIDATE_ID
    revision = protocol.candidate_revision if protocol is not None else CANDIDATE_REVISION
    empty = _empty_partition()
    return NumericComparisonReport(
        protocol_id=protocol_id,
        candidate_id=candidate_id,
        candidate_revision=revision,
        integrity_status="failed",
        candidate_status="not_recorded",
        development=empty,
        holdout=empty,
        e1=empty,
        compiled_queries=(),
        gates=(),
        integrity_failures=(
            IntegrityFailure(
                problem=problem,
                cause=cause,
                next_step=next_step,
                subject_id=None,
            ),
        ),
        duration_ms=_elapsed_ms(started),
    )


def _empty_partition() -> dict[str, object]:
    return {
        "manifest_id": "unknown",
        "current": _empty_semantic_observation(),
        "candidate": _empty_semantic_observation(),
    }


def _empty_semantic_observation() -> dict[str, object]:
    return {
        "status": "failed",
        "quality_status": "not_recorded",
        "documents": 0,
        "queries": 0,
        "answerable": 0,
        "unanswerable": 0,
        "metrics": None,
        "category_counts": {
            "answerable": 0,
            "lexical_confuser": 0,
            "out_of_corpus": 0,
        },
        "results": [],
        "integrity_failures": [],
    }


def _empty_evaluation_report(manifest_id: str) -> RetrievalEvaluationReport:
    return RetrievalEvaluationReport(
        manifest_id=manifest_id,
        benchmark_scope="small_english_page_timestamp_corpus",
        quality_gate="none",
        status="failed",
        quality_status="not_recorded",
        document_count=0,
        results=(),
        metrics=None,
        integrity_failures=(),
        duration_ms=0,
    )


def _validate_fixture_records(
    value: object,
    root: Path,
    manifests: dict[str, RetrievalEvaluationManifest],
) -> None:
    if not isinstance(value, list):
        raise _ProtocolValidationError
    records = cast(list[object], value)
    if len(records) != 2:
        raise _ProtocolValidationError
    for raw, partition in zip(records, ("development", "holdout"), strict=True):
        record = _object(raw)
        _require_keys(record, {"partition", "path", "bytes", "sha256"})
        if record["partition"] != partition:
            raise _ProtocolValidationError
        expected_path = f"retrieval-numeric-v1/{partition}.pdf"
        fixture_path = _resolve_locked_path(root, record["path"], expected_path)
        try:
            byte_size = fixture_path.stat().st_size
        except OSError as error:
            raise _ProtocolFixtureError from error
        if record["bytes"] != byte_size or record["sha256"] != _sha256_bound(
            fixture_path
        ):
            raise _ProtocolFixtureError
        manifest_fixture = manifests[partition].documents[0].primary_file
        if (
            manifest_fixture.bytes != byte_size
            or manifest_fixture.sha256 != record["sha256"]
        ):
            raise _ProtocolFixtureError


def _validate_query_inventory(
    value: object,
    manifests: dict[str, RetrievalEvaluationManifest],
) -> None:
    inventory = _object(value)
    _require_keys(inventory, {"development", "holdout", "e1"})
    for partition, manifest in manifests.items():
        raw_ids = inventory[partition]
        if not isinstance(raw_ids, list):
            raise _ProtocolValidationError
        query_ids = cast(list[object], raw_ids)
        if query_ids != [
            query.query_id for query in manifest.queries
        ]:
            raise _ProtocolValidationError


def _validate_partition_independence(
    development: RetrievalEvaluationManifest,
    holdout: RetrievalEvaluationManifest,
) -> None:
    if {item.document_id for item in development.documents} & {
        item.document_id for item in holdout.documents
    }:
        raise _ProtocolValidationError
    if {item.query_id for item in development.queries} & {
        item.query_id for item in holdout.queries
    }:
        raise _ProtocolValidationError
    if {item.text for item in development.queries} & {
        item.text for item in holdout.queries
    }:
        raise _ProtocolValidationError
    if set(_pdf_pages(development)) & set(_pdf_pages(holdout)):
        raise _ProtocolValidationError


def _pdf_pages(manifest: RetrievalEvaluationManifest) -> tuple[str, ...]:
    path = manifest.resolve(manifest.documents[0].primary_file)
    try:
        with fitz.open(path) as document:
            return tuple(
                " ".join(
                    cast(
                        str,
                        page.get_text(  # pyright: ignore[reportUnknownMemberType]
                            "text", sort=True
                        ),
                    ).split()
                )
                for page in document
            )
    except Exception as error:
        raise _ProtocolFixtureError from error


def _resolve_locked_path(root: Path, value: object, expected: str) -> Path:
    if not isinstance(value, str) or value != expected:
        raise _ProtocolValidationError
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in value:
        raise _ProtocolValidationError
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise _ProtocolValidationError
    return resolved


def _require_keys(payload: dict[str, object], expected: set[str]) -> None:
    if set(payload) != expected:
        raise _ProtocolValidationError


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _ProtocolValidationError
    return cast(dict[str, object], value)


def _sha256_bound(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise _ProtocolFixtureError from error


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
