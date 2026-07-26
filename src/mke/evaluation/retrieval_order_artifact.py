from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from mke.evaluation.retrieval_order_protocol import (
    RetrievalOrderProtocolMetadata,
    load_retrieval_order_protocol_metadata,
    load_retrieval_order_protocol_partition,
)
from mke.retrieval import compile_fts5_query
from mke.retrieval.cjk_active_scan import compile_cjk_overlap_terms

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_HEAD_RE = re.compile(r"[0-9a-f]{40}\Z")
_RUNTIME_FIELDS = {
    "python",
    "sqlite",
    "sqlite_source_id",
    "sqlite_compile_options",
    "fts5_rank_configuration",
    "strategy_revision",
    "query_policy_revision",
}
_Projection = tuple[str, str, int, int]
_ExpectedCase = tuple[str, str, tuple[_Projection, ...]]


class RetrievalOrderArtifactError(ValueError):
    """A deterministic retrieval-order proof artifact is invalid."""


def render_json_bytes(value: dict[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def file_identity(
    path: Path,
    *,
    repository_root: Path,
) -> dict[str, object]:
    root = repository_root.resolve()
    absolute = path.resolve()
    if not absolute.is_relative_to(root) or not absolute.is_file():
        raise RetrievalOrderArtifactError
    data = absolute.read_bytes()
    return {
        "path": absolute.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def protocol_identity(
    metadata: RetrievalOrderProtocolMetadata,
    *,
    repository_root: Path,
) -> dict[str, object]:
    root = repository_root.resolve()
    if not metadata.protocol_path.is_relative_to(root):
        raise RetrievalOrderArtifactError
    return {
        "id": metadata.protocol_id,
        "path": metadata.protocol_path.relative_to(root).as_posix(),
        "sha256": metadata.protocol_sha256,
        "development_fixture_sha256": metadata.development.sha256,
        "holdout_fixture_sha256": metadata.holdout.sha256,
    }


def build_development_freeze(
    *,
    metadata: RetrievalOrderProtocolMetadata,
    candidate_seal: dict[str, object],
    observation: dict[str, object],
    repository_root: Path,
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "mke.retrieval_order_development_freeze.v1",
        "protocol": protocol_identity(
            metadata,
            repository_root=repository_root,
        ),
        "candidate_seal": candidate_seal,
        "development_status": "passed",
        "holdout_status": "not_observed",
        "runtime_promotion_status": "not_evaluated",
        "observation": observation,
    }
    validate_development_freeze(
        value,
        metadata=metadata,
        expected_candidate_seal=candidate_seal,
        repository_root=repository_root,
    )
    return value


def validate_development_freeze(
    value: object,
    *,
    metadata: RetrievalOrderProtocolMetadata,
    expected_candidate_seal: dict[str, object] | None,
    repository_root: Path,
) -> dict[str, object]:
    freeze = _object(value)
    if (
        set(freeze)
        != {
            "schema_version",
            "protocol",
            "candidate_seal",
            "development_status",
            "holdout_status",
            "runtime_promotion_status",
            "observation",
        }
        or freeze["schema_version"]
        != "mke.retrieval_order_development_freeze.v1"
        or freeze["protocol"]
        != protocol_identity(metadata, repository_root=repository_root)
        or freeze["development_status"] != "passed"
        or freeze["holdout_status"] != "not_observed"
        or freeze["runtime_promotion_status"] != "not_evaluated"
    ):
        raise RetrievalOrderArtifactError
    candidate = _candidate_seal(freeze["candidate_seal"])
    if (
        expected_candidate_seal is not None
        and candidate != expected_candidate_seal
    ):
        raise RetrievalOrderArtifactError
    observation = _observation(
        freeze["observation"],
        partition="development",
        expected_cases=_evaluate_protocol_partition(
            load_retrieval_order_protocol_partition(
                metadata,
                "development",
            ).fixture,
            partition="development",
        ),
    )
    if observation["runtime_profile"] != candidate["runtime_profile"]:
        raise RetrievalOrderArtifactError
    return freeze


def build_holdout_receipt(
    *,
    metadata: RetrievalOrderProtocolMetadata,
    candidate_seal: dict[str, object],
    development_freeze_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    return {
        "schema_version": "mke.retrieval_order_holdout_receipt.v1",
        "protocol": protocol_identity(
            metadata,
            repository_root=repository_root,
        ),
        "candidate_seal": candidate_seal,
        "development_freeze": file_identity(
            development_freeze_path,
            repository_root=repository_root,
        ),
        "holdout_fixture_sha256": metadata.holdout.sha256,
        "attempt_status": "started",
    }


def validate_holdout_receipt(
    value: object,
    *,
    metadata: RetrievalOrderProtocolMetadata,
    candidate_seal: dict[str, object],
    development_freeze_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    receipt = _object(value)
    if (
        set(receipt)
        != {
            "schema_version",
            "protocol",
            "candidate_seal",
            "development_freeze",
            "holdout_fixture_sha256",
            "attempt_status",
        }
        or receipt["schema_version"]
        != "mke.retrieval_order_holdout_receipt.v1"
        or receipt["protocol"]
        != protocol_identity(metadata, repository_root=repository_root)
        or _candidate_seal(receipt["candidate_seal"]) != candidate_seal
        or receipt["development_freeze"]
        != file_identity(
            development_freeze_path,
            repository_root=repository_root,
        )
        or receipt["holdout_fixture_sha256"] != metadata.holdout.sha256
        or receipt["attempt_status"] != "started"
    ):
        raise RetrievalOrderArtifactError
    return receipt


def build_retrieval_order_artifact(
    *,
    metadata: RetrievalOrderProtocolMetadata,
    candidate_seal: dict[str, object],
    development_freeze_path: Path,
    holdout_receipt_path: Path,
    observation: dict[str, object],
    repository_root: Path,
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "mke.retrieval_order_artifact.v1",
        "protocol": protocol_identity(
            metadata,
            repository_root=repository_root,
        ),
        "candidate_seal": candidate_seal,
        "development_freeze": file_identity(
            development_freeze_path,
            repository_root=repository_root,
        ),
        "holdout_receipt": file_identity(
            holdout_receipt_path,
            repository_root=repository_root,
        ),
        "development_status": "passed",
        "holdout_status": "observed",
        "integrity_status": "passed",
        "runtime_promotion_status": "not_evaluated",
        "observation": observation,
        "limitations": [
            "public_nonblind_mechanism_holdout",
            "not_retrieval_quality_evidence",
            "no_runtime_promotion",
        ],
    }
    _validate_artifact_payload(
        value,
        metadata=metadata,
        candidate_seal=candidate_seal,
        development_freeze_path=development_freeze_path,
        holdout_receipt_path=holdout_receipt_path,
        repository_root=repository_root,
    )
    return value


def validate_retrieval_order_artifact(
    value: object,
    *,
    protocol_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    root = repository_root.resolve()
    metadata = load_retrieval_order_protocol_metadata(
        protocol_path,
        repository_root=root,
    )
    artifact = _object(value)
    candidate = _candidate_seal(artifact.get("candidate_seal"))
    freeze_path = _identity_path(
        artifact.get("development_freeze"),
        repository_root=root,
    )
    receipt_path = _identity_path(
        artifact.get("holdout_receipt"),
        repository_root=root,
    )
    freeze = validate_development_freeze(
        _load_object(freeze_path),
        metadata=metadata,
        expected_candidate_seal=candidate,
        repository_root=root,
    )
    receipt = validate_holdout_receipt(
        _load_object(receipt_path),
        metadata=metadata,
        candidate_seal=candidate,
        development_freeze_path=freeze_path,
        repository_root=root,
    )
    del freeze, receipt
    _validate_artifact_payload(
        artifact,
        metadata=metadata,
        candidate_seal=candidate,
        development_freeze_path=freeze_path,
        holdout_receipt_path=receipt_path,
        repository_root=root,
    )
    return artifact


def _validate_artifact_payload(
    artifact: dict[str, object],
    *,
    metadata: RetrievalOrderProtocolMetadata,
    candidate_seal: dict[str, object],
    development_freeze_path: Path,
    holdout_receipt_path: Path,
    repository_root: Path,
) -> None:
    if (
        set(artifact)
        != {
            "schema_version",
            "protocol",
            "candidate_seal",
            "development_freeze",
            "holdout_receipt",
            "development_status",
            "holdout_status",
            "integrity_status",
            "runtime_promotion_status",
            "observation",
            "limitations",
        }
        or artifact["schema_version"] != "mke.retrieval_order_artifact.v1"
        or artifact["protocol"]
        != protocol_identity(metadata, repository_root=repository_root)
        or _candidate_seal(artifact["candidate_seal"]) != candidate_seal
        or artifact["development_freeze"]
        != file_identity(
            development_freeze_path,
            repository_root=repository_root,
        )
        or artifact["holdout_receipt"]
        != file_identity(
            holdout_receipt_path,
            repository_root=repository_root,
        )
        or artifact["development_status"] != "passed"
        or artifact["holdout_status"] != "observed"
        or artifact["integrity_status"] != "passed"
        or artifact["runtime_promotion_status"] != "not_evaluated"
        or artifact["limitations"]
        != [
            "public_nonblind_mechanism_holdout",
            "not_retrieval_quality_evidence",
            "no_runtime_promotion",
        ]
    ):
        raise RetrievalOrderArtifactError
    observation = _observation(
        artifact["observation"],
        partition="holdout",
        expected_cases=_evaluate_protocol_partition(
            load_retrieval_order_protocol_partition(
                metadata,
                "holdout",
            ).fixture,
            partition="holdout",
        ),
    )
    if observation["runtime_profile"] != candidate_seal["runtime_profile"]:
        raise RetrievalOrderArtifactError


def _candidate_seal(value: object) -> dict[str, object]:
    candidate = _object(value)
    if set(candidate) != {"head", "runtime_profile"}:
        raise RetrievalOrderArtifactError
    head = candidate["head"]
    _runtime_profile(candidate["runtime_profile"])
    if (
        not isinstance(head, str)
        or _HEAD_RE.fullmatch(head) is None
    ):
        raise RetrievalOrderArtifactError
    return candidate


def _runtime_profile(value: object) -> dict[str, object]:
    runtime = _object(value)
    compile_options = runtime.get("sqlite_compile_options")
    if (
        set(runtime) != _RUNTIME_FIELDS
        or any(
            not isinstance(runtime[field], str) or not runtime[field]
            for field in (
                "python",
                "sqlite",
                "sqlite_source_id",
                "fts5_rank_configuration",
            )
        )
        or type(runtime["strategy_revision"]) is not int
        or runtime["strategy_revision"] != 2
        or type(runtime["query_policy_revision"]) is not int
        or runtime["query_policy_revision"] != 1
    ):
        raise RetrievalOrderArtifactError
    if not isinstance(compile_options, list):
        raise RetrievalOrderArtifactError
    options = cast(list[object], compile_options)
    if (
        not all(isinstance(item, str) for item in options)
        or options != sorted(cast(list[str], options))
    ):
        raise RetrievalOrderArtifactError
    return runtime


def _observation(
    value: object,
    *,
    partition: str,
    expected_cases: tuple[_ExpectedCase, ...],
) -> dict[str, object]:
    observation = _object(value)
    required = {
        "integrity_status",
        "observation_status",
        "partition",
        "stable_order_rate",
        "candidate_membership_delta",
        "score_hex_delta",
        "non_tied_pair_delta",
        "pagination_duplicate_or_gap_count",
        "strategy_revision",
        "query_policy_revision",
        "runtime_profile",
        "cases",
    }
    if (
        set(observation) != required
        or observation["integrity_status"] != "passed"
        or observation["observation_status"] != "passed"
        or observation["partition"] != partition
        or type(observation["stable_order_rate"]) is not float
        or observation["stable_order_rate"] != 1.0
        or any(
            type(observation[field]) is not int
            or observation[field] != 0
            for field in (
                "candidate_membership_delta",
                "score_hex_delta",
                "non_tied_pair_delta",
                "pagination_duplicate_or_gap_count",
            )
        )
        or type(observation["strategy_revision"]) is not int
        or observation["strategy_revision"] != 2
        or type(observation["query_policy_revision"]) is not int
        or observation["query_policy_revision"] != 1
        or not isinstance(observation["cases"], list)
    ):
        raise RetrievalOrderArtifactError
    runtime = _runtime_profile(observation["runtime_profile"])
    if (
        observation["strategy_revision"] != runtime["strategy_revision"]
        or observation["query_policy_revision"]
        != runtime["query_policy_revision"]
    ):
        raise RetrievalOrderArtifactError
    cases = cast(list[object], observation["cases"])
    if not cases:
        raise RetrievalOrderArtifactError
    if len(cases) != len(expected_cases):
        raise RetrievalOrderArtifactError
    for raw_case, expected in zip(cases, expected_cases, strict=True):
        _case_observation(raw_case, expected=expected)
    return observation


def _case_observation(
    value: object,
    *,
    expected: _ExpectedCase,
) -> dict[str, object]:
    case = _object(value)
    if set(case) != {
        "case_id",
        "strategy",
        "stable",
        "forward_stable_projections",
        "reverse_stable_projections",
        "score_hex",
        "pagination_lossless",
    }:
        raise RetrievalOrderArtifactError
    case_id = case["case_id"]
    strategy = case["strategy"]
    raw_forward = case["forward_stable_projections"]
    raw_reverse = case["reverse_stable_projections"]
    raw_scores = case["score_hex"]
    expected_case_id, expected_strategy, expected_projections = expected
    if (
        not isinstance(case_id, str)
        or not case_id
        or strategy not in {"fts", "cjk"}
        or case_id != expected_case_id
        or strategy != expected_strategy
        or case["stable"] is not True
        or case["pagination_lossless"] is not True
        or not isinstance(raw_forward, list)
        or not raw_forward
        or not isinstance(raw_reverse, list)
        or raw_forward != raw_reverse
        or not isinstance(raw_scores, list)
    ):
        raise RetrievalOrderArtifactError
    forward = cast(list[object], raw_forward)
    scores = cast(list[object], raw_scores)
    projections = [_projection(item) for item in forward]
    if (
        tuple(projections) != expected_projections
        or len(set(projections)) != len(projections)
        or len(scores) != len(forward)
    ):
        raise RetrievalOrderArtifactError
    score_projections: set[_Projection] = set()
    score_values: list[str] = []
    for raw_score, projection in zip(scores, projections, strict=True):
        if not isinstance(raw_score, list):
            raise RetrievalOrderArtifactError
        score_record = cast(list[object], raw_score)
        if len(score_record) != 2:
            raise RetrievalOrderArtifactError
        score_projection = _projection(score_record[0])
        if (
            score_projection != projection
            or score_projection in score_projections
        ):
            raise RetrievalOrderArtifactError
        score_projections.add(score_projection)
        score = score_record[1]
        if not isinstance(score, str) or not score:
            raise RetrievalOrderArtifactError
        score_values.append(score)
    if len(set(score_values)) != 1:
        raise RetrievalOrderArtifactError
    if strategy == "fts":
        if not _canonical_finite_float_hex(score_values[0]):
            raise RetrievalOrderArtifactError
    elif score_values[0] != "cjk-equal-overlap":
        raise RetrievalOrderArtifactError
    return case


def _canonical_finite_float_hex(value: str) -> bool:
    try:
        parsed = float.fromhex(value)
    except ValueError:
        return False
    return math.isfinite(parsed) and parsed.hex() == value


def _evaluate_protocol_partition(
    fixture: dict[str, object],
    *,
    partition: str,
) -> tuple[_ExpectedCase, ...]:
    if (
        fixture.get("partition") != partition
        or not isinstance(fixture.get("cases"), list)
    ):
        raise RetrievalOrderArtifactError
    result: list[_ExpectedCase] = []
    seen_case_ids: set[str] = set()
    for raw_case in cast(list[object], fixture["cases"]):
        case = _object(raw_case)
        case_id = case.get("case_id")
        strategy = case.get("strategy")
        query = case.get("query")
        raw_candidates = case.get("candidates")
        if (
            not isinstance(case_id, str)
            or not case_id
            or case_id in seen_case_ids
            or strategy not in {"fts", "cjk"}
            or not isinstance(query, str)
            or not query
            or not isinstance(raw_candidates, list)
        ):
            raise RetrievalOrderArtifactError
        candidate_values = cast(list[object], raw_candidates)
        if len(candidate_values) < 2:
            raise RetrievalOrderArtifactError
        seen_case_ids.add(case_id)
        candidates = [
            _oracle_candidate(item)
            for item in candidate_values
        ]
        if strategy == "fts":
            if (
                not compile_fts5_query(query, policy="current")
                or any(candidate["text"] != query for candidate in candidates)
            ):
                raise RetrievalOrderArtifactError
            keyed = [
                (
                    (
                        candidate["locator_start"],
                        candidate["locator_kind"],
                        candidate["locator_end"],
                        candidate["asset_sha256"],
                    ),
                    _candidate_projection(candidate),
                )
                for candidate in candidates
            ]
        else:
            terms = compile_cjk_overlap_terms(
                query,
                require_terms=True,
            ).terms
            tie_values: list[tuple[int, float]] = []
            for candidate in candidates:
                normalized = "".join(
                    character
                    for character in cast(str, candidate["text"]).casefold()
                    if not character.isspace()
                )
                overlap_count = sum(term in normalized for term in terms)
                tie_values.append(
                    (overlap_count, overlap_count / len(terms))
                )
            if (
                not tie_values
                or tie_values[0][0] == 0
                or any(value != tie_values[0] for value in tie_values[1:])
            ):
                raise RetrievalOrderArtifactError
            keyed = [
                (
                    (
                        candidate["content_fingerprint"],
                        candidate["locator_kind"],
                        candidate["locator_start"],
                        candidate["locator_end"],
                    ),
                    _candidate_projection(candidate),
                )
                for candidate in candidates
            ]
        keys = [key for key, _ in keyed]
        if len(keys) != len(set(keys)):
            raise RetrievalOrderArtifactError
        derived = tuple(
            projection for _, projection in sorted(keyed, key=lambda item: item[0])
        )
        raw_expected = case.get("expected_stable_projections")
        if not isinstance(raw_expected, list):
            raise RetrievalOrderArtifactError
        expected = tuple(
            _projection(item)
            for item in cast(list[object], raw_expected)
        )
        if expected != derived:
            raise RetrievalOrderArtifactError
        result.append((case_id, cast(str, strategy), derived))
    if not result:
        raise RetrievalOrderArtifactError
    return tuple(result)


def _oracle_candidate(value: object) -> dict[str, object]:
    candidate = _object(value)
    required = {
        "source_id",
        "content_fingerprint",
        "asset_sha256",
        "locator_kind",
        "locator_start",
        "locator_end",
        "text",
    }
    if set(candidate) != required:
        raise RetrievalOrderArtifactError
    fingerprint, kind, start, end = _projection(
        [
            candidate["content_fingerprint"],
            candidate["locator_kind"],
            candidate["locator_start"],
            candidate["locator_end"],
        ]
    )
    asset = candidate["asset_sha256"]
    text = candidate["text"]
    if (
        not isinstance(asset, str)
        or _SHA256_RE.fullmatch(asset) is None
        or fingerprint != f"sha256:{asset}"
        or not isinstance(text, str)
        or not text
    ):
        raise RetrievalOrderArtifactError
    return candidate | {
        "content_fingerprint": fingerprint,
        "locator_kind": kind,
        "locator_start": start,
        "locator_end": end,
    }


def _candidate_projection(candidate: dict[str, object]) -> _Projection:
    return (
        cast(str, candidate["content_fingerprint"]),
        cast(str, candidate["locator_kind"]),
        cast(int, candidate["locator_start"]),
        cast(int, candidate["locator_end"]),
    )


def _projection(value: object) -> tuple[str, str, int, int]:
    if not isinstance(value, list):
        raise RetrievalOrderArtifactError
    projection = cast(list[object], value)
    if len(projection) != 4:
        raise RetrievalOrderArtifactError
    fingerprint, locator_kind, locator_start, locator_end = projection
    if (
        not isinstance(fingerprint, str)
        or not fingerprint.startswith("sha256:")
        or _SHA256_RE.fullmatch(fingerprint.removeprefix("sha256:"))
        is None
        or not isinstance(locator_kind, str)
        or locator_kind not in {"page", "timestamp_ms"}
        or type(locator_start) is not int
        or type(locator_end) is not int
        or locator_start < 0
        or locator_end < locator_start
    ):
        raise RetrievalOrderArtifactError
    return fingerprint, locator_kind, locator_start, locator_end


def _identity_path(
    value: object,
    *,
    repository_root: Path,
) -> Path:
    identity = _object(value)
    if set(identity) != {"path", "sha256"}:
        raise RetrievalOrderArtifactError
    path_value = identity["path"]
    digest = identity["sha256"]
    if (
        not isinstance(path_value, str)
        or not isinstance(digest, str)
        or _SHA256_RE.fullmatch(digest) is None
    ):
        raise RetrievalOrderArtifactError
    root = repository_root.resolve()
    path = (root / path_value).resolve()
    if not path.is_relative_to(root):
        raise RetrievalOrderArtifactError
    if identity != file_identity(path, repository_root=root):
        raise RetrievalOrderArtifactError
    return path


def _load_object(path: Path) -> dict[str, object]:
    return _object(json.loads(path.read_text(encoding="utf-8")))


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RetrievalOrderArtifactError
    return cast(dict[str, object], value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mke.evaluation.retrieval_order_artifact"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate")
    validate.add_argument("--artifact", type=Path, required=True)
    validate.add_argument("--protocol", type=Path, required=True)
    validate.add_argument("--repository", type=Path, required=True)
    validate.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        artifact = _load_object(arguments.artifact)
        validate_retrieval_order_artifact(
            artifact,
            protocol_path=arguments.protocol,
            repository_root=arguments.repository,
        )
        result = {
            "schema_version": "mke.retrieval_order_artifact_result.v1",
            "status": "passed",
            "mode": "validate",
            "problem": "none",
            "cause": "none",
            "next_step": "none",
        }
    except Exception:
        result = {
            "schema_version": "mke.retrieval_order_artifact_result.v1",
            "status": "failed",
            "mode": "validate",
            "problem": "retrieval_order_artifact_invalid",
            "cause": "recorded_structure_or_identity_invalid",
            "next_step": "inspect_retained_bytes",
        }
    print(
        json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
