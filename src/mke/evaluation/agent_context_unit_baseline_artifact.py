"""Pure O0 grading and retained baseline artifact validation."""

from __future__ import annotations

import hashlib
import json
import re
from typing import cast

from mke.evaluation.agent_context_unit_grading_protocol import (
    AgentContextBaselineGradingPayload,
    AgentContextRequiredSpan,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MECHANISM_STATUSES = {
    "adjacent-page-assembly-v1": "not_evaluated",
    "deterministic-unit-rank-v1": "not_evaluated",
    "fixed-rank-delivery-v1": "not_evaluated",
    "source-context-delivery-v1": "not_evaluated",
    "source-context-index-v1": "not_evaluated",
}
_FIELDS = {
    "candidate_target_query_ids",
    "content_digest",
    "coverage",
    "evaluator_source_sha256",
    "fixture_sha256",
    "holdout_status",
    "integrity_status",
    "limitations",
    "mechanism_statuses",
    "observation",
    "observation_sha256",
    "phase",
    "protocol_sha256",
    "runtime_profile",
    "runtime_profile_sha256",
    "runtime_promotion_status",
    "role_coverage",
    "schema_version",
    "stage_outcome",
    "status",
    "targeted_failure_observed",
}
_OBSERVATION_FIELDS = {
    "candidate_count",
    "delivered_utf8_bytes",
    "expected_route",
    "items",
    "profile_identity",
    "query_id",
    "query_text",
    "selected_count",
    "statuses",
}
_OBSERVATION_ITEM_FIELDS = {
    "content_fingerprint",
    "exact_read_sha256",
    "exact_read_utf8_bytes",
    "excerpt",
    "excerpt_utf8_bytes",
    "hints",
    "locator_end",
    "locator_kind",
    "locator_start",
    "original_utf8_bytes",
    "rank",
    "route",
    "score",
    "text_sha256",
}
_EXCERPT_FIELDS = {
    "complete",
    "content_trust",
    "end_utf8_byte",
    "kind",
    "prefix_omitted",
    "returned_utf8_bytes",
    "start_utf8_byte",
    "suffix_omitted",
    "text",
}
_SCORE_FIELDS = {"kind", "primary", "secondary"}


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def build_agent_context_unit_baseline_artifact(
    *,
    sealed_observation_bytes: bytes,
    grading_payload: AgentContextBaselineGradingPayload,
    candidate_target_query_ids: tuple[str, ...],
    protocol_sha256: str,
    evaluator_source_sha256: str,
    runtime_profile: dict[str, object],
    fixture_sha256: str,
) -> dict[str, object]:
    for value in (protocol_sha256, evaluator_source_sha256, fixture_sha256):
        if _SHA256.fullmatch(value) is None:
            raise ValueError("baseline authority digest is invalid")
    if (
        not candidate_target_query_ids
        or len(set(candidate_target_query_ids)) != len(candidate_target_query_ids)
    ):
        raise ValueError("candidate target inventory is invalid")
    observation = json.loads(sealed_observation_bytes)
    if sealed_observation_bytes != _observation_bytes(observation):
        raise ValueError("sealed observation bytes are not canonical")
    observations = _observation_rows(observation)
    _require_complete_observations(observations)
    coverage = tuple(
        _span_coverage(span, observations) for span in grading_payload.required_spans
    )
    role_coverage = _role_coverage(coverage)
    targets = set(candidate_target_query_ids)
    targeted_failure = any(
        not cast(bool, item["covered"]) and cast(str, item["query_id"]) in targets
        for item in coverage
    )
    record: dict[str, object] = {
        "schema_version": "mke.agent_context_unit_baseline.v2",
        "status": "passed",
        "phase": "baseline",
        "integrity_status": "passed",
        "stage_outcome": (
            "baseline_red_observed"
            if targeted_failure
            else "docs_regression_only"
        ),
        "targeted_failure_observed": targeted_failure,
        "mechanism_statuses": dict(_MECHANISM_STATUSES),
        "holdout_status": "not_evaluated",
        "runtime_promotion_status": "not_evaluated",
        "protocol_sha256": protocol_sha256,
        "evaluator_source_sha256": evaluator_source_sha256,
        "fixture_sha256": fixture_sha256,
        "runtime_profile": runtime_profile,
        "runtime_profile_sha256": hashlib.sha256(
            _canonical(runtime_profile)
        ).hexdigest(),
        "observation": observation,
        "observation_sha256": hashlib.sha256(sealed_observation_bytes).hexdigest(),
        "candidate_target_query_ids": list(candidate_target_query_ids),
        "coverage": list(coverage),
        "role_coverage": list(role_coverage),
        "limitations": [
            "comparison_only",
            "development_only_until_separate_holdout_authority",
            "no_performance_claim",
            "no_retrieval_quality_claim",
            "no_runtime_promotion",
        ],
    }
    record["content_digest"] = hashlib.sha256(_canonical(record)).hexdigest()
    return record


def render_agent_context_unit_baseline_artifact(
    artifact: dict[str, object],
) -> bytes:
    _validate_closed_digest(artifact)
    return _canonical(artifact) + b"\n"


def validate_agent_context_unit_baseline_artifact(
    value: object,
    grading_payload: AgentContextBaselineGradingPayload,
) -> None:
    artifact = _artifact(value)
    observation = artifact["observation"]
    sealed = _observation_bytes(observation)
    targets_value = artifact["candidate_target_query_ids"]
    if not isinstance(targets_value, list):
        raise ValueError("baseline artifact inventory is invalid")
    targets = cast(list[object], targets_value)
    if not all(isinstance(item, str) for item in targets):
        raise ValueError("baseline artifact inventory is invalid")
    expected = build_agent_context_unit_baseline_artifact(
        sealed_observation_bytes=sealed,
        grading_payload=grading_payload,
        candidate_target_query_ids=tuple(cast(list[str], targets)),
        protocol_sha256=_digest_field(artifact, "protocol_sha256"),
        evaluator_source_sha256=_digest_field(
            artifact, "evaluator_source_sha256"
        ),
        runtime_profile=_mapping_field(artifact, "runtime_profile"),
        fixture_sha256=_digest_field(artifact, "fixture_sha256"),
    )
    if artifact != expected:
        raise ValueError("baseline artifact does not recompute")


def validate_agent_context_unit_baseline_artifact_live(
    value: object,
    grading_payload: AgentContextBaselineGradingPayload,
    *,
    protocol_sha256: str,
    evaluator_source_sha256: str,
    fixture_sha256: str,
) -> None:
    validate_agent_context_unit_baseline_artifact(value, grading_payload)
    artifact = _artifact(value)
    actual = (
        artifact["protocol_sha256"],
        artifact["evaluator_source_sha256"],
        artifact["fixture_sha256"],
    )
    if actual != (protocol_sha256, evaluator_source_sha256, fixture_sha256):
        raise ValueError("baseline live authority differs")


def _artifact(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("baseline artifact fields are invalid")
    artifact = cast(dict[str, object], value)
    if set(artifact) != _FIELDS:
        raise ValueError("baseline artifact fields are invalid")
    _validate_closed_digest(artifact)
    if (
        artifact["schema_version"] != "mke.agent_context_unit_baseline.v2"
        or artifact["status"] != "passed"
        or artifact["phase"] != "baseline"
        or artifact["integrity_status"] != "passed"
        or artifact["stage_outcome"]
        not in {"baseline_red_observed", "docs_regression_only"}
        or artifact["mechanism_statuses"] != _MECHANISM_STATUSES
        or artifact["holdout_status"] != "not_evaluated"
        or artifact["runtime_promotion_status"] != "not_evaluated"
    ):
        raise ValueError("baseline artifact status is invalid")
    return artifact


def _validate_closed_digest(artifact: dict[str, object]) -> None:
    if set(artifact) != _FIELDS:
        raise ValueError("baseline artifact fields are invalid")
    claimed = artifact.get("content_digest")
    if not isinstance(claimed, str) or _SHA256.fullmatch(claimed) is None:
        raise ValueError("baseline artifact digest is invalid")
    body = dict(artifact)
    del body["content_digest"]
    if hashlib.sha256(_canonical(body)).hexdigest() != claimed:
        raise ValueError("baseline artifact digest is invalid")


def _observation_rows(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, dict):
        raise ValueError("sealed observation is invalid")
    observation = cast(dict[str, object], value)
    if (
        set(observation) != {"observations", "schema_version"}
        or observation["schema_version"]
        != "mke.agent_context_unit_observation.v2"
        or not isinstance(observation["observations"], list)
    ):
        raise ValueError("sealed observation is invalid")
    raw_rows = cast(list[object], observation["observations"])
    if not raw_rows or not all(isinstance(row, dict) for row in raw_rows):
        raise ValueError("sealed observation is invalid")
    rows = tuple(cast(dict[str, object], row) for row in raw_rows)
    for row in rows:
        if set(row) != _OBSERVATION_FIELDS:
            raise ValueError("sealed observation is invalid")
        statuses = row["statuses"]
        items = row["items"]
        if (
            not isinstance(statuses, list)
            or not all(isinstance(item, str) for item in cast(list[object], statuses))
            or not isinstance(items, list)
        ):
            raise ValueError("sealed observation is invalid")
        for raw_item in cast(list[object], items):
            if not isinstance(raw_item, dict):
                raise ValueError("sealed observation is invalid")
            item = cast(dict[str, object], raw_item)
            excerpt = item.get("excerpt")
            score = item.get("score")
            if (
                set(item) != _OBSERVATION_ITEM_FIELDS
                or not isinstance(excerpt, dict)
                or set(cast(dict[str, object], excerpt)) != _EXCERPT_FIELDS
                or not isinstance(score, dict)
                or set(cast(dict[str, object], score)) != _SCORE_FIELDS
            ):
                raise ValueError("sealed observation is invalid")
    return rows


def _observation_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        + "\n"
    ).encode("utf-8")


def _require_complete_observations(
    observations: tuple[dict[str, object], ...],
) -> None:
    required = {
        "output_complete",
        "exact_read_complete",
        "provenance_complete",
    }
    for observation in observations:
        statuses = observation.get("statuses")
        status_items = cast(list[object], statuses) if isinstance(statuses, list) else []
        if (
            not isinstance(statuses, list)
            or not all(isinstance(item, str) for item in status_items)
            or not required <= set(cast(list[str], status_items))
            or not isinstance(observation.get("items"), list)
        ):
            raise ValueError("baseline observation integrity is incomplete")


def _span_coverage(
    span: AgentContextRequiredSpan,
    observations: tuple[dict[str, object], ...],
) -> dict[str, object]:
    covered = False
    for observation in observations:
        if observation.get("query_id") != span.query_id:
            continue
        for raw_item in cast(list[object], observation["items"]):
            if not isinstance(raw_item, dict):
                raise ValueError("sealed observation is invalid")
            item = cast(dict[str, object], raw_item)
            excerpt = item.get("excerpt")
            if not isinstance(excerpt, dict):
                raise ValueError("sealed observation is invalid")
            excerpt = cast(dict[str, object], excerpt)
            if (
                item.get("content_fingerprint")
                == span.source_content_fingerprint
                and item.get("locator_kind") == span.locator_kind
                and item.get("locator_start") == span.locator_start
                and item.get("locator_end") == span.locator_end
                and item.get("text_sha256") == f"sha256:{span.text_sha256}"
                and type(excerpt.get("start_utf8_byte")) is int
                and type(excerpt.get("end_utf8_byte")) is int
                and cast(int, excerpt["start_utf8_byte"]) <= span.start_utf8_byte
                and cast(int, excerpt["end_utf8_byte"]) >= span.end_utf8_byte
            ):
                covered = True
    return {
        "control": span.control,
        "covered": covered,
        "hypothesis": span.hypothesis,
        "query_id": span.query_id,
        "role": span.role,
        "span_id": span.span_id,
    }


def _role_coverage(
    coverage: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], ...]:
    identities = sorted(
        {
            (cast(str, item["query_id"]), cast(str, item["role"]))
            for item in coverage
        }
    )
    return tuple(
        {
            "complete": all(
                cast(bool, item["covered"])
                for item in coverage
                if (item["query_id"], item["role"]) == (query_id, role)
            ),
            "covered": sum(
                cast(bool, item["covered"])
                for item in coverage
                if (item["query_id"], item["role"]) == (query_id, role)
            ),
            "query_id": query_id,
            "required": sum(
                1
                for item in coverage
                if (item["query_id"], item["role"]) == (query_id, role)
            ),
            "role": role,
        }
        for query_id, role in identities
    )


def _digest_field(artifact: dict[str, object], field: str) -> str:
    value = artifact[field]
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("baseline artifact digest is invalid")
    return value


def _mapping_field(
    artifact: dict[str, object], field: str
) -> dict[str, object]:
    value = artifact[field]
    if not isinstance(value, dict):
        raise ValueError("baseline artifact profile is invalid")
    return cast(dict[str, object], value)
