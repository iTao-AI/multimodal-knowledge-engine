"""Frozen E3-E relevance gate comparison protocol lock."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import cast

SCHEMA_VERSION = "mke.relevance_gate_protocol.v1"
CANDIDATE_ID = "cjk-relevance-gate-reranker-v1"
CANDIDATE_REVISION = 1

_PROFILE_IDS = ("lexical-floor", "balanced-constraint", "strict-constraint")
_INPUTS = {
    "chinese_protocol": "tests/fixtures/retrieval-chinese-v1/protocol.json",
    "qrel_adjudication": "tests/fixtures/retrieval-chinese-v1/qrel-adjudication.json",
    "dense_artifact": "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json",
    "rrf_artifact": "benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json",
    "protocol_source": "src/mke/evaluation/relevance_gate_protocol.py",
    "metrics_source": "src/mke/evaluation/graded_metrics.py",
    "cli_source": "src/mke/cli.py",
}
_EVAL_ONLY_MODULES = [
    "src/mke/evaluation/relevance_gate_features.py",
    "src/mke/evaluation/relevance_gate_candidate.py",
    "src/mke/evaluation/relevance_gate_workflow.py",
    "src/mke/evaluation/relevance_gate_artifact.py",
    "src/mke/evaluation/relevance_gate_protocol.py",
]
_FORBIDDEN_SCORING_INPUTS = [
    "qrel_grades",
    "expected_locators",
    "query_category_labels",
    "split_labels",
    "ask_outcome_labels",
    "artifact_metric_values",
    "manual_query_allowlists",
]
_ALLOWED_SCORING_INPUTS = [
    "query_text",
    "evidence_text",
    "stable_locator_id",
    "source_text_digest",
    "document_id",
    "locator_identity",
    "arm_provenance",
    "rank_provenance",
]


class RelevanceGateProtocolError(ValueError):
    """Stable public protocol validation error."""

    def __init__(self, problem: str, cause: str, next_step: str) -> None:
        super().__init__(f"{problem}: {cause}")
        self.problem = problem
        self.cause = cause
        self.next_step = next_step

    def __str__(self) -> str:
        return f"{self.problem}: {self.cause}"


def build_relevance_gate_protocol_lock(*, repository_root: Path) -> dict[str, object]:
    root = repository_root.resolve()
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            "candidate_revision": CANDIDATE_REVISION,
        },
        "comparison_scope": {
            "runtime_promotion_status": "not_evaluated",
            "search_ask_mcp_runtime_changed": False,
            "candidate_type": "deterministic_relevance_gate_reranker",
        },
        "inputs": {
            name: _file_identity(root, relative_path)
            for name, relative_path in _INPUTS.items()
        },
        "source_inventory": {
            "eval_only_modules": list(_EVAL_ONLY_MODULES),
            "runtime_modules_changed": [],
        },
        "profiles": [
            {"profile_id": profile_id, "profile_revision": 1}
            for profile_id in _PROFILE_IDS
        ],
        "scoring_inputs": {
            "allowed": list(_ALLOWED_SCORING_INPUTS),
            "forbidden": list(_FORBIDDEN_SCORING_INPUTS),
        },
        "selection_objective": [
            "pass_refusal_and_hard_negative_gates",
            "maximize_recall_at_5",
            "maximize_ndcg_at_10",
            "preserve_dense_or_union_only_recovery_when_possible",
            "tie_break_stricter_profile",
        ],
        "development_gates": {
            "unanswerable_no_hit_minimum": 0.5,
            "hard_negative_failure_maximum": 0.2,
            "recall_at_5_minimum": 0.681818,
            "ndcg_at_10_minimum": 0.643390,
            "mrr_at_5_minimum": 0.636364,
        },
        "state": {
            "development_freeze_required_before_holdout": True,
            "development_freeze_mode": "exclusive_create",
            "holdout_receipt_mode": "exclusive_create",
            "candidate_status_initial": "not_evaluated",
            "runtime_promotion_status": "not_evaluated",
        },
    }


def render_relevance_gate_protocol_lock_json(protocol: dict[str, object]) -> str:
    return json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_relevance_gate_protocol_lock(
    path: Path,
    *,
    repository_root: Path,
) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise _error(
            "protocol lock is invalid",
            "protocol JSON could not be loaded",
            "Regenerate the E3-E protocol lock from the repository root.",
        ) from error
    if not isinstance(payload, dict):
        raise _error(
            "protocol lock is invalid",
            "protocol JSON root must be an object",
            "Regenerate the E3-E protocol lock from the repository root.",
        )
    protocol = cast(dict[str, object], payload)
    validate_relevance_gate_protocol_lock(protocol, repository_root=repository_root)
    return protocol


def validate_relevance_gate_protocol_lock(
    protocol: dict[str, object],
    *,
    repository_root: Path,
) -> None:
    expected = build_relevance_gate_protocol_lock(repository_root=repository_root)
    if protocol.get("schema_version") != SCHEMA_VERSION:
        raise _error(
            "schema is invalid",
            "schema_version is not E3-E v1",
            "Use the checked-in E3-E protocol lock.",
        )
    _validate_candidate(protocol.get("candidate"))
    _validate_scope(protocol.get("comparison_scope"))
    _validate_inputs(protocol.get("inputs"), repository_root=repository_root)
    _validate_source_inventory(protocol.get("source_inventory"))
    _validate_profiles(protocol.get("profiles"))
    _validate_scoring_inputs(protocol.get("scoring_inputs"))
    _validate_selection_objective(protocol.get("selection_objective"))
    _validate_development_gates(protocol.get("development_gates"))
    _validate_state(protocol.get("state"))
    if protocol != expected:
        raise _error(
            "protocol identity drift",
            "recorded protocol content does not match repository inputs",
            "Regenerate the protocol only after confirming the drift is identity-only.",
        )


def _validate_candidate(value: object) -> None:
    data = _object(value, "candidate")
    if (
        data.get("candidate_id") != CANDIDATE_ID
        or data.get("candidate_revision") != CANDIDATE_REVISION
        or type(data.get("candidate_revision")) is not int
    ):
        raise _error(
            "candidate identity is invalid",
            "candidate_id or integer candidate_revision does not match E3-E",
            "Use candidate_id cjk-relevance-gate-reranker-v1 and revision 1.",
        )


def _validate_scope(value: object) -> None:
    if value != {
        "runtime_promotion_status": "not_evaluated",
        "search_ask_mcp_runtime_changed": False,
        "candidate_type": "deterministic_relevance_gate_reranker",
    }:
        raise _error(
            "comparison scope is invalid",
            "protocol must remain comparison-only and runtime-neutral",
            "Restore the E3-E comparison scope fields.",
        )


def _validate_inputs(value: object, *, repository_root: Path) -> None:
    data = _object(value, "input identities")
    if set(data) != set(_INPUTS):
        raise _error(
            "input identities are invalid",
            "bound input inventory does not match E3-E protocol",
            "Restore the protocol input inventory.",
        )
    root = repository_root.resolve()
    for name, expected_path in _INPUTS.items():
        record = _object(data.get(name), f"{name} identity")
        recorded_path = record.get("path")
        if type(recorded_path) is not str:
            raise _error(
                "repository path is invalid",
                f"{name} path must be repository-relative",
                "Regenerate the protocol with repository-relative paths.",
            )
        _repository_path(root, recorded_path)
        if record != _file_identity(root, expected_path):
            raise _error(
                "input identity drift",
                f"{name} bytes or sha256 does not match the repository file",
                "Confirm semantic equality before refreshing protocol identity.",
            )


def _validate_source_inventory(value: object) -> None:
    if value != {
        "eval_only_modules": list(_EVAL_ONLY_MODULES),
        "runtime_modules_changed": [],
    }:
        raise _error(
            "source inventory is invalid",
            "source inventory must list eval-only E3-E modules and no runtime modules",
            "Restore the E3-E source inventory.",
        )


def _validate_profiles(value: object) -> None:
    if not isinstance(value, list):
        raise _error(
            "profile catalog is invalid",
            "profiles must be a list",
            "Restore the frozen profile catalog.",
        )
    profiles = cast(list[object], value)
    expected = [
        {"profile_id": profile_id, "profile_revision": 1}
        for profile_id in _PROFILE_IDS
    ]
    if profiles != expected:
        raise _error(
            "profile catalog is invalid",
            "profile IDs and revisions must exactly match the frozen catalog",
            "Use lexical-floor, balanced-constraint, and strict-constraint revision 1.",
        )
    for profile in profiles:
        data = _object(profile, "profile")
        if type(data.get("profile_revision")) is not int:
            raise _error(
                "profile catalog is invalid",
                "profile_revision must be an integer",
                "Use integer profile revisions.",
            )


def _validate_scoring_inputs(value: object) -> None:
    if value != {
        "allowed": list(_ALLOWED_SCORING_INPUTS),
        "forbidden": list(_FORBIDDEN_SCORING_INPUTS),
    }:
        raise _error(
            "scoring input contract is invalid",
            "allowed or forbidden scoring inputs drifted",
            "Restore the E3-E scoring input contract.",
        )


def _validate_selection_objective(value: object) -> None:
    if value != [
        "pass_refusal_and_hard_negative_gates",
        "maximize_recall_at_5",
        "maximize_ndcg_at_10",
        "preserve_dense_or_union_only_recovery_when_possible",
        "tie_break_stricter_profile",
    ]:
        raise _error(
            "selection objective is invalid",
            "profile selection objective drifted",
            "Restore the frozen development selection objective.",
        )


def _validate_development_gates(value: object) -> None:
    if value != {
        "unanswerable_no_hit_minimum": 0.5,
        "hard_negative_failure_maximum": 0.2,
        "recall_at_5_minimum": 0.681818,
        "ndcg_at_10_minimum": 0.643390,
        "mrr_at_5_minimum": 0.636364,
    }:
        raise _error(
            "development gates are invalid",
            "development gate thresholds drifted",
            "Restore the frozen E3-E development gates.",
        )


def _validate_state(value: object) -> None:
    if value != {
        "development_freeze_required_before_holdout": True,
        "development_freeze_mode": "exclusive_create",
        "holdout_receipt_mode": "exclusive_create",
        "candidate_status_initial": "not_evaluated",
        "runtime_promotion_status": "not_evaluated",
    }:
        raise _error(
            "holdout state is invalid",
            "development freeze and holdout receipt state must be exclusive-create",
            "Restore E3-E development and holdout state.",
        )


def _file_identity(root: Path, relative_path: str) -> dict[str, object]:
    path = _repository_path(root, relative_path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise _error(
            "input identity drift",
            f"{relative_path} is missing or unreadable",
            "Restore the bound input before validating the protocol.",
        ) from error
    return {
        "path": relative_path,
        "bytes": len(data),
        "sha256": sha256(data).hexdigest(),
    }


def _repository_path(root: Path, relative_path: str) -> Path:
    posix_path = PurePosixPath(relative_path)
    if posix_path.is_absolute() or ".." in posix_path.parts:
        raise _error(
            "repository path is invalid",
            "bound paths must be relative to the repository root",
            "Use repository-relative paths without parent traversal.",
        )
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise _error(
            "repository path is invalid",
            "bound path escapes the repository root",
            "Use repository-relative paths inside this repository.",
        )
    return path


def _object(value: object, subject: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _error(
            f"{subject} is invalid",
            f"{subject} must be an object",
            "Regenerate the E3-E protocol lock.",
        )
    return cast(dict[str, object], value)


def _error(problem: str, cause: str, next_step: str) -> RelevanceGateProtocolError:
    return RelevanceGateProtocolError(
        problem=problem,
        cause=cause,
        next_step=next_step,
    )
