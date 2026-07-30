from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class AgentContextSubstage(StrEnum):
    AUTHORITY_PREFLIGHT = "authority_preflight"
    RUNTIME_BASELINE = "runtime_baseline"
    SOURCE_SNAPSHOT = "source_snapshot"
    UNIT_PROJECTION = "unit_projection"
    UNIT_RANK = "unit_rank"
    FIXED_RANK_DELIVERY = "fixed_rank_delivery"
    RESIDUAL_GATE = "residual_gate"
    ADJACENT_PAGE_ASSEMBLY = "adjacent_page_assembly"
    SOURCE_CONTEXT_INDEX = "source_context_index"
    SOURCE_CONTEXT_DELIVERY = "source_context_delivery"
    COMPLETE_OBSERVATION_SEAL = "complete_observation_seal"
    GRADING = "grading"
    ARTIFACT_VALIDATION = "artifact_validation"
    PUBLICATION = "publication"


@dataclass(frozen=True)
class AgentContextStageSuccess:
    substage: AgentContextSubstage
    portable_sha256: str


class AgentContextStageError(ValueError):
    def __init__(
        self,
        substage: AgentContextSubstage,
        error_code: str,
        error_family: str,
        *,
        completed: tuple[AgentContextStageSuccess, ...] = (),
    ) -> None:
        super().__init__(f"{substage.value}:{error_code}:{error_family}")
        self.substage = substage
        self.error_code = error_code
        self.error_family = error_family
        self.completed = completed

    @property
    def first_failed_gate(self) -> str:
        return self.substage.value


def run_diagnostic_stage(
    substage: AgentContextSubstage,
    operation: Callable[[], object],
) -> AgentContextStageSuccess:
    value = operation()
    if not isinstance(value, bytes):
        raise AgentContextStageError(
            substage, "stage_output_invalid", "integrity"
        )
    return AgentContextStageSuccess(
        substage=substage,
        portable_sha256=hashlib.sha256(value).hexdigest(),
    )


def execute_diagnostic_stages(
    stages: Sequence[tuple[AgentContextSubstage, Callable[[], object]]],
) -> tuple[AgentContextStageSuccess, ...]:
    completed: list[AgentContextStageSuccess] = []
    for substage, operation in stages:
        try:
            completed.append(run_diagnostic_stage(substage, operation))
        except AgentContextStageError as error:
            raise AgentContextStageError(
                error.substage,
                error.error_code,
                error.error_family,
                completed=tuple(completed),
            ) from None
        except Exception:
            raise AgentContextStageError(
                substage,
                "unexpected_stage_failure",
                "unexpected",
                completed=tuple(completed),
            ) from None
    return tuple(completed)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def build_agent_context_diagnostic_receipt(
    *,
    protocol_sha256: str,
    profile_sha256: str,
    evaluator_source_sha256: str,
    observation_sha256: str | None,
    phase: str,
    attempt_kind: str,
    observation_started: bool,
    completed: tuple[AgentContextStageSuccess, ...],
    error: AgentContextStageError,
    output_state: str,
    publication_outcome: str,
    stderr_bytes: int,
    stderr_sha256: str,
) -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": "mke.agent_context_unit_diagnostic_receipt.v1",
        "protocol_sha256": protocol_sha256,
        "profile_sha256": profile_sha256,
        "evaluator_source_sha256": evaluator_source_sha256,
        "observation_sha256": observation_sha256,
        "phase": phase,
        "attempt_kind": attempt_kind,
        "observation_started": observation_started,
        "completed_substages": [
            {
                "substage": item.substage.value,
                "portable_sha256": item.portable_sha256,
            }
            for item in completed
        ],
        "last_completed_substage": (
            completed[-1].substage.value if completed else "none"
        ),
        "failed_substage": error.substage.value,
        "error_code": error.error_code,
        "error_family": error.error_family,
        "output_state": output_state,
        "publication_outcome": publication_outcome,
        "stderr_bytes": stderr_bytes,
        "stderr_sha256": stderr_sha256,
    }
    record["content_digest"] = hashlib.sha256(_canonical(record)).hexdigest()
    return record


def render_agent_context_diagnostic_receipt(
    receipt: dict[str, object],
) -> bytes:
    validate_agent_context_diagnostic_receipt(receipt)
    return _canonical(receipt) + b"\n"


def validate_agent_context_diagnostic_receipt(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("diagnostic receipt fields are invalid")
    receipt = cast(dict[str, object], value)
    expected = {
        "attempt_kind",
        "completed_substages",
        "content_digest",
        "error_code",
        "error_family",
        "evaluator_source_sha256",
        "failed_substage",
        "last_completed_substage",
        "observation_sha256",
        "observation_started",
        "output_state",
        "phase",
        "profile_sha256",
        "protocol_sha256",
        "publication_outcome",
        "schema_version",
        "stderr_bytes",
        "stderr_sha256",
    }
    if set(receipt) != expected:
        raise ValueError("diagnostic receipt fields are invalid")
    if receipt["schema_version"] != "mke.agent_context_unit_diagnostic_receipt.v1":
        raise ValueError("diagnostic receipt schema is invalid")
    for field in (
        "protocol_sha256",
        "profile_sha256",
        "evaluator_source_sha256",
        "stderr_sha256",
        "content_digest",
    ):
        item = receipt[field]
        if not isinstance(item, str) or _SHA256.fullmatch(item) is None:
            raise ValueError("diagnostic receipt digest is invalid")
    observation = receipt["observation_sha256"]
    if observation is not None and (
        not isinstance(observation, str)
        or _SHA256.fullmatch(observation) is None
    ):
        raise ValueError("diagnostic receipt digest is invalid")
    completed_value = receipt["completed_substages"]
    if not isinstance(completed_value, list):
        raise ValueError("diagnostic receipt stages are invalid")
    completed = cast(list[object], completed_value)
    stage_order = list(AgentContextSubstage)
    seen: list[AgentContextSubstage] = []
    for item in completed:
        if not isinstance(item, dict):
            raise ValueError("diagnostic receipt stages are invalid")
        item_mapping = cast(dict[object, object], item)
        if set(item_mapping) != {
            "portable_sha256",
            "substage",
        }:
            raise ValueError("diagnostic receipt stages are invalid")
        stage_record = cast(dict[str, object], item)
        try:
            stage = AgentContextSubstage(stage_record["substage"])
        except (ValueError, TypeError):
            raise ValueError("diagnostic receipt stages are invalid") from None
        digest = stage_record["portable_sha256"]
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ValueError("diagnostic receipt stages are invalid")
        seen.append(stage)
    if seen != stage_order[: len(seen)] or len(seen) != len(set(seen)):
        raise ValueError("diagnostic receipt stages are invalid")
    try:
        failed = AgentContextSubstage(receipt["failed_substage"])
    except (ValueError, TypeError):
        raise ValueError("diagnostic receipt stages are invalid") from None
    if failed is not stage_order[len(seen)]:
        raise ValueError("diagnostic receipt stages are invalid")
    last = seen[-1].value if seen else "none"
    if receipt["last_completed_substage"] != last:
        raise ValueError("diagnostic receipt stages are invalid")
    stderr_bytes = receipt["stderr_bytes"]
    if type(stderr_bytes) is not int or stderr_bytes < 0:
        raise ValueError("diagnostic receipt stderr is invalid")
    claimed = cast(str, receipt["content_digest"])
    without_digest = dict(receipt)
    del without_digest["content_digest"]
    if hashlib.sha256(_canonical(without_digest)).hexdigest() != claimed:
        raise ValueError("diagnostic receipt digest is invalid")
