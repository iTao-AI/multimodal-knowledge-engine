from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
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
from mke.evaluation._atomic_json_publication import (
    AtomicPublicationResult,
    publish_json_no_replace,
)
from mke.evaluation.retrieval_order_artifact import (
    build_development_freeze,
    build_holdout_receipt,
    build_retrieval_order_artifact,
    render_json_bytes,
    validate_development_freeze,
    validate_holdout_receipt,
    validate_retrieval_order_artifact,
)
from mke.evaluation.retrieval_order_protocol import (
    RetrievalOrderProtocolMetadata,
    load_retrieval_order_protocol_metadata,
    load_retrieval_order_protocol_partition,
)
from mke.retrieval import compile_fts5_query
from mke.retrieval.query_policy import QUERY_POLICY_REVISION
from mke.retrieval.strategy import get_retrieval_strategy_descriptor


class RetrievalOrderWorkflowError(RuntimeError):
    """The deterministic-order observation could not be trusted."""

    def __init__(
        self,
        message: str = "retrieval order workflow is invalid",
        *,
        problem: str = "retrieval_order_holdout_unauthorized",
        cause: str = "typed_capability_missing_or_mismatched",
        next_step: str = "restore_approved_transition",
        publication: AtomicPublicationResult | None = None,
    ) -> None:
        super().__init__(message)
        self.problem = problem
        self.cause = cause
        self.next_step = next_step
        self.publication = publication


_StatusRecord = tuple[str, str, str | None]


_CANONICAL_FIXTURE_DIGESTS = frozenset(
    {
        "e37e9519d899fc934c1758860f1b40d3605ed065a11b1921fdac914746f733f5",
        "e95c5253d0284f8127754591b9da9aa71b30a8ceae2670ca4751456cf7d4a080"
    }
)
_CANONICAL_PROTOCOL = Path(
    "tests/fixtures/retrieval-order-v1/protocol.json"
)
_CANONICAL_DEVELOPMENT_FREEZE = Path(
    "benchmarks/retrieval/retrieval-order-v1-development-freeze.json"
)
_CANONICAL_HOLDOUT_RECEIPT = Path(
    "benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json"
)
_CANONICAL_RETRIEVAL_ARTIFACT = Path(
    "benchmarks/retrieval/retrieval-order-v1-artifact.json"
)
_CANONICAL_PROTOCOL_SHA256 = (
    "cd90fd4158438bd57c3fb1325961f9a7098811c5a4be8cd24eec9e766374bc60"
)
_CANONICAL_HOLDOUT_SHA256 = (
    "e95c5253d0284f8127754591b9da9aa71b30a8ceae2670ca4751456cf7d4a080"
)


_SYNTHETIC_CAPABILITY_ISSUER = object()


@dataclass(init=False)
class SyntheticHoldoutCapability:
    protocol_path: Path
    protocol_sha256: str
    holdout_fixture_sha256: str
    candidate_head: str
    runtime_profile: dict[str, object]
    _authority: _HoldoutAuthority | None
    _consumed: bool = field(default=False, init=False, repr=False)

    def __init__(
        self,
        *,
        protocol_path: Path,
        protocol_sha256: str,
        holdout_fixture_sha256: str,
        candidate_head: str,
        runtime_profile: dict[str, object],
        authority: _HoldoutAuthority | None = None,
        issuer: object | None = None,
    ) -> None:
        if issuer is not _SYNTHETIC_CAPABILITY_ISSUER:
            raise RetrievalOrderWorkflowError(
                "synthetic holdout capability issuer is invalid"
            )
        self.protocol_path = protocol_path
        self.protocol_sha256 = protocol_sha256
        self.holdout_fixture_sha256 = holdout_fixture_sha256
        self.candidate_head = candidate_head
        self.runtime_profile = dict(runtime_profile)
        self._authority = authority
        self._consumed = False

    @classmethod
    def issue(
        cls,
        *,
        protocol_path: Path,
        repository_root: Path,
        candidate_head: str,
        runtime_profile: dict[str, object],
        authority: _HoldoutAuthority | None = None,
    ) -> SyntheticHoldoutCapability:
        metadata = load_retrieval_order_protocol_metadata(
            protocol_path,
            repository_root=repository_root,
        )
        fixture_digests = {
            metadata.development.sha256,
            metadata.holdout.sha256,
        }
        if (
            fixture_digests & _CANONICAL_FIXTURE_DIGESTS
            or len(candidate_head) != 40
            or any(
                character not in "0123456789abcdef"
                for character in candidate_head
            )
            or (
                authority is not None
                and (
                    authority.candidate_seal["head"] != candidate_head
                    or authority.candidate_seal["runtime_profile"]
                    != runtime_profile
                )
            )
        ):
            raise RetrievalOrderWorkflowError(
                "synthetic holdout capability is invalid"
            )
        return cls(
            issuer=_SYNTHETIC_CAPABILITY_ISSUER,
            protocol_path=metadata.protocol_path,
            protocol_sha256=metadata.protocol_sha256,
            holdout_fixture_sha256=metadata.holdout.sha256,
            candidate_head=candidate_head,
            runtime_profile=dict(runtime_profile),
            authority=authority,
        )

    def _consume(
        self,
        metadata: RetrievalOrderProtocolMetadata,
    ) -> None:
        if (
            self._consumed
            or metadata.protocol_path != self.protocol_path
            or metadata.protocol_sha256 != self.protocol_sha256
            or metadata.holdout.sha256 != self.holdout_fixture_sha256
        ):
            raise RetrievalOrderWorkflowError(
                "holdout capability is missing or mismatched"
            )
        self._consumed = True

    def _revalidate_authority(
        self,
        metadata: RetrievalOrderProtocolMetadata,
        *,
        repository_root: Path,
    ) -> None:
        if self._authority is not None:
            self._authority.validate(
                metadata,
                repository_root=repository_root,
            )


_PRODUCTION_CAPABILITY_ISSUER = object()


def _is_canonical_holdout_metadata(
    metadata: RetrievalOrderProtocolMetadata,
    *,
    repository_root: Path,
) -> bool:
    root = repository_root.resolve()
    return (
        metadata.protocol_path == (root / _CANONICAL_PROTOCOL).resolve()
        and metadata.protocol_sha256 == _CANONICAL_PROTOCOL_SHA256
        and metadata.holdout.sha256 == _CANONICAL_HOLDOUT_SHA256
    )


def _has_canonical_protocol_authority(repository_root: Path) -> bool:
    protocol = repository_root.resolve() / _CANONICAL_PROTOCOL
    try:
        return (
            hashlib.sha256(protocol.read_bytes()).hexdigest()
            == _CANONICAL_PROTOCOL_SHA256
        )
    except OSError:
        return False


@dataclass(frozen=True)
class _HoldoutAuthority:
    candidate_seal: dict[str, object]
    status_records: tuple[_StatusRecord, ...]
    development_freeze_path: Path
    development_freeze_bytes: bytes
    development_freeze_sha256: str
    receipt_path: Path
    receipt_bytes: bytes
    receipt_sha256: str

    def validate(
        self,
        metadata: RetrievalOrderProtocolMetadata,
        *,
        repository_root: Path,
    ) -> None:
        root = repository_root.resolve()
        expected_status = {
            self.development_freeze_path: "??",
            self.receipt_path: "??",
        }
        try:
            candidate = _candidate_seal(
                root,
                expected_status=expected_status,
            )
            freeze_bytes = self.development_freeze_path.read_bytes()
            receipt_bytes = self.receipt_path.read_bytes()
            if (
                _public_candidate_seal(candidate) != self.candidate_seal
                or _status_records(candidate) != self.status_records
                or freeze_bytes != self.development_freeze_bytes
                or receipt_bytes != self.receipt_bytes
                or hashlib.sha256(freeze_bytes).hexdigest()
                != self.development_freeze_sha256
                or hashlib.sha256(receipt_bytes).hexdigest()
                != self.receipt_sha256
            ):
                raise ValueError("retained authority changed")
            validate_development_freeze(
                _object_from_bytes(freeze_bytes),
                metadata=metadata,
                expected_candidate_seal=self.candidate_seal,
                repository_root=root,
            )
            validate_holdout_receipt(
                _object_from_bytes(receipt_bytes),
                metadata=metadata,
                candidate_seal=self.candidate_seal,
                development_freeze_path=self.development_freeze_path,
                repository_root=root,
            )
        except Exception as error:
            raise RetrievalOrderWorkflowError(
                "candidate seal is invalid",
                problem="retrieval_order_candidate_seal_mismatch",
                cause="candidate_inputs_do_not_match_seal",
                next_step="retain_receipt_and_stop",
            ) from error


@dataclass(init=False)
class _ProductionHoldoutCapability:
    protocol_path: Path
    protocol_sha256: str
    holdout_fixture_sha256: str
    receipt_path: Path
    receipt_sha256: str
    candidate_head: str
    runtime_profile: dict[str, object]
    status_records: tuple[_StatusRecord, ...]
    development_freeze_sha256: str
    _authority: _HoldoutAuthority
    _consumed: bool

    def __init__(
        self,
        *,
        issuer: object,
        metadata: RetrievalOrderProtocolMetadata,
        receipt_path: Path,
        receipt_sha256: str,
        candidate_seal: dict[str, object],
        authority: _HoldoutAuthority,
        repository_root: Path,
    ) -> None:
        if (
            issuer is not _PRODUCTION_CAPABILITY_ISSUER
            or not _is_canonical_holdout_metadata(
                metadata,
                repository_root=repository_root,
            )
            or authority.candidate_seal != candidate_seal
            or authority.receipt_path != receipt_path.resolve()
            or authority.receipt_sha256 != receipt_sha256
        ):
            raise RetrievalOrderWorkflowError(
                "holdout capability issuer is invalid"
            )
        self.protocol_path = metadata.protocol_path
        self.protocol_sha256 = metadata.protocol_sha256
        self.holdout_fixture_sha256 = metadata.holdout.sha256
        self.receipt_path = receipt_path.resolve()
        self.receipt_sha256 = receipt_sha256
        self.candidate_head = cast(str, candidate_seal["head"])
        self.runtime_profile = dict(
            cast(dict[str, object], candidate_seal["runtime_profile"])
        )
        self.status_records = authority.status_records
        self.development_freeze_sha256 = (
            authority.development_freeze_sha256
        )
        self._authority = authority
        self._consumed = False

    def _consume(
        self,
        metadata: RetrievalOrderProtocolMetadata,
        *,
        repository_root: Path,
    ) -> None:
        if (
            self._consumed
            or metadata.protocol_path != self.protocol_path
            or metadata.protocol_sha256 != self.protocol_sha256
            or metadata.holdout.sha256 != self.holdout_fixture_sha256
        ):
            raise RetrievalOrderWorkflowError(
                "holdout capability is missing or mismatched"
            )
        self._consumed = True

    def _revalidate_authority(
        self,
        metadata: RetrievalOrderProtocolMetadata,
        *,
        repository_root: Path,
    ) -> None:
        self._authority.validate(
            metadata,
            repository_root=repository_root,
        )


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
    compile_options = sorted(
        str(row[0])
        for row in connection.execute("PRAGMA compile_options").fetchall()
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
    holdout_capability: (
        SyntheticHoldoutCapability | _ProductionHoldoutCapability | None
    ) = None,
) -> dict[str, object]:
    metadata = load_retrieval_order_protocol_metadata(
        protocol_path,
        repository_root=repository_root,
    )
    if partition == "holdout":
        if type(holdout_capability) not in {
            SyntheticHoldoutCapability,
            _ProductionHoldoutCapability,
        }:
            raise RetrievalOrderWorkflowError(
                "holdout capability is missing or mismatched"
            )
        if type(holdout_capability) is SyntheticHoldoutCapability:
            holdout_capability._consume(  # pyright: ignore[reportPrivateUsage]
                metadata
            )
        else:
            assert type(holdout_capability) is _ProductionHoldoutCapability
            holdout_capability._consume(  # pyright: ignore[reportPrivateUsage]
                metadata,
                repository_root=repository_root,
            )
        holdout_capability._revalidate_authority(  # pyright: ignore[reportPrivateUsage]
            metadata,
            repository_root=repository_root,
        )
    contract = load_retrieval_order_protocol_partition(
        metadata,
        partition,
    )
    fixture = contract.fixture
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


def _candidate_seal(
    repository_root: Path,
    *,
    expected_status: Mapping[Path, str],
) -> dict[str, object]:
    root = repository_root.resolve()
    try:
        first_head = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status_output = subprocess.run(
            (
                "git",
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
            ),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        final_head = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise _candidate_seal_error() from error
    try:
        records = _parse_status_records(status_output)
        expected_records = _expected_status_records(
            root,
            expected_status,
        )
    except (TypeError, ValueError) as error:
        raise _candidate_seal_error() from error
    if (
        not _valid_head(first_head)
        or not _valid_head(final_head)
        or first_head != final_head
        or records != expected_records
    ):
        raise _candidate_seal_error()
    connection = sqlite3.connect(":memory:")
    try:
        profile = retrieval_runtime_profile(connection)
    finally:
        connection.close()
    return {
        "head": first_head,
        "runtime_profile": profile,
        "status_records": records,
    }


def _candidate_seal_error() -> RetrievalOrderWorkflowError:
    return RetrievalOrderWorkflowError(
        "candidate seal is invalid",
        problem="retrieval_order_candidate_seal_mismatch",
        cause="candidate_inputs_do_not_match_seal",
        next_step="return_to_authority_review",
    )


def _valid_head(value: str) -> bool:
    return (
        len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _parse_status_records(output: str) -> tuple[_StatusRecord, ...]:
    fields = output.split("\0")
    if fields[-1:] == [""]:
        fields.pop()
    records: list[_StatusRecord] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        if len(field) < 4 or field[2] != " ":
            raise ValueError("invalid porcelain status")
        status = field[:2]
        path = _status_path(field[3:])
        rename_source: str | None = None
        if "R" in status or "C" in status:
            index += 1
            if index >= len(fields):
                raise ValueError("missing rename source")
            rename_source = _status_path(fields[index])
        records.append((status, path, rename_source))
        index += 1
    return tuple(sorted(records))


def _status_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or value != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("status path escapes repository")
    return value


def _expected_status_records(
    root: Path,
    expected_status: Mapping[Path, str],
) -> tuple[_StatusRecord, ...]:
    records: list[_StatusRecord] = []
    seen: set[str] = set()
    for path, status in expected_status.items():
        absolute = path if path.is_absolute() else root / path
        try:
            relative = absolute.relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError("expected path escapes repository") from error
        relative = _status_path(relative)
        if (
            status != "??"
            or relative in seen
        ):
            raise ValueError("invalid expected status")
        seen.add(relative)
        records.append((status, relative, None))
    return tuple(sorted(records))


def _public_candidate_seal(
    candidate: Mapping[str, object],
) -> dict[str, object]:
    return {
        "head": candidate["head"],
        "runtime_profile": candidate["runtime_profile"],
    }


def _status_records(
    candidate: Mapping[str, object],
) -> tuple[_StatusRecord, ...]:
    return cast(tuple[_StatusRecord, ...], candidate["status_records"])


def _publish_or_stop(
    *,
    destination: Path,
    value: dict[str, object],
    validate: Callable[[object], None],
) -> AtomicPublicationResult:
    result = publish_json_no_replace(
        destination,
        render_json_bytes(value),
        validate=validate,
    )
    if result.publication_outcome != "published":
        problem = (
            "retrieval_order_publication_durability_unconfirmed"
            if result.publication_outcome == "durability_unconfirmed"
            else "retrieval_order_publication_failed_before_visibility"
        )
        cause = (
            "directory_fsync_failed_after_visibility"
            if result.publication_outcome == "durability_unconfirmed"
            else "publication_failed_before_final_path"
        )
        next_step = (
            "retain_visible_bytes_and_stop"
            if result.publication_outcome == "durability_unconfirmed"
            else "retain_attempt_and_stop"
        )
        raise RetrievalOrderWorkflowError(
            "retrieval order publication failed",
            problem=problem,
            cause=cause,
            next_step=next_step,
            publication=result,
        )
    return result


def _run_development(
    *,
    protocol_path: Path,
    freeze_path: Path,
    repository_root: Path,
) -> AtomicPublicationResult:
    root = repository_root.resolve()
    metadata = load_retrieval_order_protocol_metadata(
        protocol_path,
        repository_root=root,
    )
    canonical_metadata = _is_canonical_holdout_metadata(
        metadata,
        repository_root=root,
    )
    canonical_destination = freeze_path.resolve() == (
        root / _CANONICAL_DEVELOPMENT_FREEZE
    ).resolve()
    if (
        canonical_metadata and not canonical_destination
    ) or (
        _has_canonical_protocol_authority(root)
        and canonical_destination
        and not canonical_metadata
    ):
        raise RetrievalOrderWorkflowError(
            "development authority paths are mismatched",
            problem="retrieval_order_holdout_unauthorized",
            cause="typed_capability_missing_or_mismatched",
            next_step="restore_approved_transition",
        )
    candidate = _candidate_seal(
        root,
        expected_status={},
    )
    public_candidate = _public_candidate_seal(candidate)
    observation = observe_retrieval_order_partition(
        protocol_path=protocol_path,
        partition="development",
        repository_root=root,
    )
    if _candidate_seal(root, expected_status={}) != candidate:
        raise _candidate_seal_error()
    if (
        observation["observation_status"] != "passed"
        or observation["runtime_profile"] != candidate["runtime_profile"]
    ):
        raise RetrievalOrderWorkflowError(
            "development observation failed",
            problem="retrieval_order_compatibility_incomplete",
            cause="unapproved_family_delta",
            next_step="inspect_first_failed_family",
        )
    freeze = build_development_freeze(
        metadata=metadata,
        candidate_seal=public_candidate,
        observation=observation,
        repository_root=root,
    )

    def validate_candidate(value: object) -> None:
        validate_development_freeze(
            value,
            metadata=metadata,
            expected_candidate_seal=public_candidate,
            repository_root=root,
        )

    if _candidate_seal(root, expected_status={}) != candidate:
        raise _candidate_seal_error()
    return _publish_or_stop(
        destination=freeze_path,
        value=freeze,
        validate=validate_candidate,
    )


def _run_holdout(
    *,
    protocol_path: Path,
    development_freeze_path: Path,
    receipt_path: Path,
    artifact_path: Path,
    repository_root: Path,
) -> AtomicPublicationResult:
    root = repository_root.resolve()
    metadata = load_retrieval_order_protocol_metadata(
        protocol_path,
        repository_root=root,
    )
    canonical_metadata = _is_canonical_holdout_metadata(
        metadata,
        repository_root=root,
    )
    canonical_outputs = (
        development_freeze_path.resolve()
        == (root / _CANONICAL_DEVELOPMENT_FREEZE).resolve()
        and receipt_path.resolve()
        == (root / _CANONICAL_HOLDOUT_RECEIPT).resolve()
        and artifact_path.resolve()
        == (root / _CANONICAL_RETRIEVAL_ARTIFACT).resolve()
    )
    if (
        canonical_metadata and not canonical_outputs
    ) or (
        _has_canonical_protocol_authority(root)
        and canonical_outputs
        and not canonical_metadata
    ):
        raise RetrievalOrderWorkflowError(
            "holdout authority paths are mismatched",
            problem="retrieval_order_holdout_unauthorized",
            cause="typed_capability_missing_or_mismatched",
            next_step="restore_approved_transition",
        )
    if receipt_path.exists():
        raise RetrievalOrderWorkflowError(
            "holdout receipt already exists",
            problem="retrieval_order_holdout_already_started",
            cause="holdout_receipt_exists",
            next_step="retain_receipt_and_stop",
            publication=AtomicPublicationResult(
                output_state="complete_preexisting",
                publication_outcome="not_attempted",
                sha256=None,
                problem="retrieval_order_holdout_already_started",
            ),
        )
    if artifact_path.exists():
        raise RetrievalOrderWorkflowError(
            "holdout artifact already exists",
            problem="retrieval_order_holdout_unauthorized",
            cause="typed_capability_missing_or_mismatched",
            next_step="restore_approved_transition",
            publication=AtomicPublicationResult(
                output_state="complete_preexisting",
                publication_outcome="not_attempted",
                sha256=hashlib.sha256(
                    artifact_path.read_bytes()
                ).hexdigest(),
                problem="retrieval_order_holdout_unauthorized",
            ),
        )
    candidate = _candidate_seal(
        root,
        expected_status={development_freeze_path: "??"},
    )
    public_candidate = _public_candidate_seal(candidate)
    try:
        validate_development_freeze(
            _load_object(development_freeze_path),
            metadata=metadata,
            expected_candidate_seal=public_candidate,
            repository_root=root,
        )
    except Exception as error:
        raise RetrievalOrderWorkflowError(
            "development freeze is invalid",
            problem="retrieval_order_candidate_seal_mismatch",
            cause="candidate_inputs_do_not_match_seal",
            next_step="return_to_authority_review",
        ) from error
    receipt = build_holdout_receipt(
        metadata=metadata,
        candidate_seal=public_candidate,
        development_freeze_path=development_freeze_path,
        repository_root=root,
    )

    def validate_receipt_candidate(value: object) -> None:
        validate_holdout_receipt(
            value,
            metadata=metadata,
            candidate_seal=public_candidate,
            development_freeze_path=development_freeze_path,
            repository_root=root,
        )

    publication = _publish_or_stop(
        destination=receipt_path,
        value=receipt,
        validate=validate_receipt_candidate,
    )
    assert publication.sha256 is not None
    try:
        authority = _bind_holdout_authority(
            metadata=metadata,
            candidate_seal=public_candidate,
            development_freeze_path=development_freeze_path,
            receipt_path=receipt_path,
            repository_root=root,
        )
    except Exception as error:
        raise RetrievalOrderWorkflowError(
            str(error),
            problem="retrieval_order_candidate_seal_mismatch",
            cause="candidate_inputs_do_not_match_seal",
            next_step="retain_receipt_and_stop",
            publication=publication,
        ) from error
    if authority.receipt_sha256 != publication.sha256:
        raise RetrievalOrderWorkflowError(
            "visible receipt identity is invalid",
            publication=publication,
            next_step="retain_receipt_and_stop",
        )
    try:
        if canonical_metadata:
            capability: (
                SyntheticHoldoutCapability | _ProductionHoldoutCapability
            ) = _ProductionHoldoutCapability(
                issuer=_PRODUCTION_CAPABILITY_ISSUER,
                metadata=metadata,
                receipt_path=receipt_path,
                receipt_sha256=publication.sha256,
                candidate_seal=public_candidate,
                authority=authority,
                repository_root=root,
            )
        else:
            capability = SyntheticHoldoutCapability.issue(
                protocol_path=protocol_path,
                repository_root=root,
                candidate_head=cast(str, candidate["head"]),
                runtime_profile=cast(
                    dict[str, object],
                    candidate["runtime_profile"],
                ),
                authority=authority,
            )
        observation = observe_retrieval_order_partition(
            protocol_path=protocol_path,
            partition="holdout",
            repository_root=root,
            holdout_capability=capability,
        )
        authority.validate(metadata, repository_root=root)
        if observation["observation_status"] != "passed":
            raise RetrievalOrderWorkflowError(
                "holdout observation failed",
                problem="retrieval_order_compatibility_incomplete",
                cause="unapproved_family_delta",
                next_step="retain_receipt_and_stop",
            )
        artifact = build_retrieval_order_artifact(
            metadata=metadata,
            candidate_seal=public_candidate,
            development_freeze_path=development_freeze_path,
            holdout_receipt_path=receipt_path,
            observation=observation,
            repository_root=root,
        )
        authority.validate(metadata, repository_root=root)

        def validate_artifact_candidate(value: object) -> None:
            validate_retrieval_order_artifact(
                value,
                protocol_path=protocol_path,
                repository_root=root,
            )

        return _publish_or_stop(
            destination=artifact_path,
            value=artifact,
            validate=validate_artifact_candidate,
        )
    except Exception as error:
        if isinstance(error, RetrievalOrderWorkflowError):
            problem = error.problem
            cause = error.cause
        else:
            problem = "retrieval_order_candidate_seal_mismatch"
            cause = "candidate_inputs_do_not_match_seal"
        raise RetrievalOrderWorkflowError(
            str(error),
            problem=problem,
            cause=cause,
            next_step="retain_receipt_and_stop",
            publication=publication,
        ) from error


def _bind_holdout_authority(
    *,
    metadata: RetrievalOrderProtocolMetadata,
    candidate_seal: dict[str, object],
    development_freeze_path: Path,
    receipt_path: Path,
    repository_root: Path,
) -> _HoldoutAuthority:
    root = repository_root.resolve()
    freeze = development_freeze_path.resolve()
    receipt = receipt_path.resolve()
    freeze_bytes = freeze.read_bytes()
    receipt_bytes = receipt.read_bytes()
    validate_development_freeze(
        _object_from_bytes(freeze_bytes),
        metadata=metadata,
        expected_candidate_seal=candidate_seal,
        repository_root=root,
    )
    validate_holdout_receipt(
        _object_from_bytes(receipt_bytes),
        metadata=metadata,
        candidate_seal=candidate_seal,
        development_freeze_path=freeze,
        repository_root=root,
    )
    return _HoldoutAuthority(
        candidate_seal=candidate_seal,
        status_records=_expected_status_records(
            root,
            {
                freeze: "??",
                receipt: "??",
            },
        ),
        development_freeze_path=freeze,
        development_freeze_bytes=freeze_bytes,
        development_freeze_sha256=hashlib.sha256(freeze_bytes).hexdigest(),
        receipt_path=receipt,
        receipt_bytes=receipt_bytes,
        receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
    )


def _workflow_result(
    *,
    mode: str,
    status: str,
    publication: AtomicPublicationResult | None,
    problem: str,
    cause: str,
    next_step: str,
    canonical: bool,
) -> dict[str, object]:
    return {
        "schema_version": "mke.retrieval_order_workflow_result.v1",
        "status": status,
        "mode": mode,
        "authority_layer": "candidate_observation",
        "canonical": canonical,
        "output_state": (
            publication.output_state
            if publication is not None
            else "not_applicable"
        ),
        "publication_outcome": (
            publication.publication_outcome
            if publication is not None
            else "not_attempted"
        ),
        "problem": problem,
        "cause": cause,
        "next_step": next_step,
        "first_failed_gate": (
            "none" if status == "passed" else "workflow"
        ),
        "stage_statuses": [
            {
                "name": "workflow",
                "status": "passed" if status == "passed" else "failed",
            }
        ],
        "historical_revision": 1,
        "current_revision": 2,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mke.evaluation.retrieval_order_workflow"
    )
    subcommands = parser.add_subparsers(dest="phase", required=True)
    current = subcommands.add_parser("current")
    current.add_argument("--protocol", type=Path, required=True)
    current.add_argument("--record", type=Path, required=True)
    current.add_argument("--json", action="store_true", required=True)
    development = subcommands.add_parser("development")
    development.add_argument("--protocol", type=Path, required=True)
    development.add_argument(
        "--record-development-freeze",
        type=Path,
        required=True,
    )
    development.add_argument("--json", action="store_true", required=True)
    holdout = subcommands.add_parser("holdout")
    holdout.add_argument("--protocol", type=Path, required=True)
    holdout.add_argument("--development-freeze", type=Path, required=True)
    holdout.add_argument(
        "--record-holdout-receipt",
        type=Path,
        required=True,
    )
    holdout.add_argument("--record", type=Path, required=True)
    holdout.add_argument("--json", action="store_true", required=True)
    args = parser.parse_args(argv)
    if args.phase != "current":
        root = Path.cwd().resolve()
        mode = cast(str, args.phase)
        canonical = (
            (
                args.record_development_freeze.resolve()
                == (
                    root
                    / "benchmarks/retrieval/"
                    "retrieval-order-v1-development-freeze.json"
                ).resolve()
            )
            if mode == "development"
            else (
                args.record_holdout_receipt.resolve()
                == (
                    root
                    / "benchmarks/retrieval/"
                    "retrieval-order-v1-holdout-receipt.json"
                ).resolve()
                and args.record.resolve()
                == (
                    root
                    / "benchmarks/retrieval/"
                    "retrieval-order-v1-artifact.json"
                ).resolve()
            )
        )
        try:
            if mode == "development":
                publication = _run_development(
                    protocol_path=args.protocol,
                    freeze_path=args.record_development_freeze,
                    repository_root=root,
                )
            else:
                publication = _run_holdout(
                    protocol_path=args.protocol,
                    development_freeze_path=args.development_freeze,
                    receipt_path=args.record_holdout_receipt,
                    artifact_path=args.record,
                    repository_root=root,
                )
            payload = _workflow_result(
                mode=mode,
                status="passed",
                publication=publication,
                problem="none",
                cause="none",
                next_step="none",
                canonical=canonical,
            )
        except RetrievalOrderWorkflowError as error:
            payload = _workflow_result(
                mode=mode,
                status="failed",
                publication=error.publication,
                problem=error.problem,
                cause=error.cause,
                next_step=error.next_step,
                canonical=canonical,
            )
        except Exception:
            payload = _workflow_result(
                mode=mode,
                status="failed",
                publication=None,
                problem="retrieval_order_holdout_unauthorized",
                cause="typed_capability_missing_or_mismatched",
                next_step="restore_approved_transition",
                canonical=canonical,
            )
        print(
            json.dumps(
                payload,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 0 if payload["status"] == "passed" else 1
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


def _object_from_bytes(value: bytes) -> dict[str, object]:
    return _object(json.loads(value))


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RetrievalOrderWorkflowError
    return cast(dict[str, object], value)


if __name__ == "__main__":
    raise SystemExit(main())
