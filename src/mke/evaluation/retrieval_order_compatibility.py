from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from mke.application import KnowledgeEngine
from mke.evaluation import (
    chinese_artifact as chinese_artifact_module,
)
from mke.evaluation import (
    cjk_lexical_artifact as cjk_lexical_artifact_module,
)
from mke.evaluation import numeric_artifact as numeric_artifact_module
from mke.evaluation import numeric_comparison, retrieval_order_workflow, runner
from mke.evaluation._atomic_json_publication import (
    AtomicPublicationResult,
    publish_json_no_replace,
)
from mke.evaluation.baseline import validate_retrieval_baseline
from mke.evaluation.chinese_artifact import record_chinese_artifact
from mke.evaluation.chinese_protocol import load_chinese_retrieval_protocol
from mke.evaluation.chinese_report import render_chinese_retrieval_json
from mke.evaluation.chinese_runner import run_chinese_retrieval_evaluation
from mke.evaluation.cjk_lexical_artifact import record_cjk_lexical_artifact
from mke.evaluation.cjk_lexical_comparison import (
    render_cjk_lexical_comparison_json,
    run_cjk_lexical_comparison,
)
from mke.evaluation.dense_artifact import validate_dense_comparison_artifact
from mke.evaluation.hybrid_rrf_artifact import validate_hybrid_rrf_artifact
from mke.evaluation.manifest import EvaluationQuery, StableLocator
from mke.evaluation.relevance_gate_artifact import (
    validate_relevance_gate_artifact,
)
from mke.evaluation.report import render_retrieval_json_report
from mke.evaluation.retrieval_order_artifact import (
    file_identity as retrieval_order_file_identity,
)
from mke.evaluation.retrieval_order_artifact import (
    validate_retrieval_order_artifact,
)
from mke.evaluation.retrieval_order_protocol import (
    load_retrieval_order_protocol_metadata,
)
from mke.evaluation.source_identity import (
    build_source_identity,
    validate_recorded_source_identity,
)
from mke.retrieval import compile_fts5_query

_SOURCE_COMMIT = "eea3d51c36c0b3b845b8efb60eff553ddc200b88"
_SOURCE_TREE = "30c0a65e265ce0342462ffc44c2c4fe799f959b5"
_SOURCE_IDENTITY = "c3cec8853547fd09d8fad10865666ce2bb1a507afe19a066a364ab2424064665"
_RUNTIME_PROFILE = {
    "python": "3.13.12",
    "sqlite": "3.51.1",
    "pymupdf": "1.27.2.3",
}
_NUMERIC_ARTIFACT = Path(
    "benchmarks/retrieval/numeric-grouping-v1-comparison.json"
)
_CHINESE_ARTIFACT = Path(
    "benchmarks/retrieval/retrieval-chinese-v1-baseline.json"
)
_E1_MANIFEST = Path("tests/fixtures/retrieval-eval-v1.json")
_NUMERIC_PROTOCOL = Path(
    "tests/fixtures/retrieval-numeric-v1/protocol-lock.json"
)
_HISTORICAL_INPUTS = {
    "e1_baseline": (
        Path("benchmarks/retrieval/retrieval-eval-v1-baseline.json"),
        _E1_MANIFEST,
    ),
    "e2_numeric": (_NUMERIC_ARTIFACT, _NUMERIC_PROTOCOL),
    "e3a_chinese": (
        _CHINESE_ARTIFACT,
        Path("tests/fixtures/retrieval-chinese-v1/protocol.json"),
    ),
    "e3b_cjk_lexical": (
        Path("benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json"),
        Path("tests/fixtures/retrieval-chinese-v1/protocol.json"),
    ),
    "e3c_dense": (
        Path(
            "benchmarks/retrieval/"
            "qwen3-embedding-0.6b-exact-v1-comparison.json"
        ),
        Path("tests/fixtures/retrieval-dense-v1/protocol-lock.json"),
    ),
    "e3d_hybrid_rrf": (
        Path(
            "benchmarks/retrieval/"
            "cjk-active-scan-qwen3-rrf-v1-comparison.json"
        ),
        Path("tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json"),
    ),
    "e3e_relevance_gate": (
        Path(
            "benchmarks/retrieval/"
            "cjk-relevance-gate-reranker-v1-comparison.json"
        ),
        Path(
            "tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json"
        ),
    ),
}
_CANONICAL_ARTIFACT = Path(
    "benchmarks/retrieval/retrieval-order-v2-compatibility.json"
)
_IMMUTABLE_INPUT_SHA256 = {
    "benchmarks/retrieval/retrieval-eval-v1-baseline.json": (
        "c2518b2f95a91eb91f2f83953965e186711e2b3d93725e9d83617d0fde530a88"
    ),
    "benchmarks/retrieval/numeric-grouping-v1-comparison.json": (
        "98fb1f61d824d7b307d3a2745b49ed972fc6d4af292833098a15b13b860ddae9"
    ),
    "benchmarks/retrieval/retrieval-chinese-v1-baseline.json": (
        "7187d999fc98f2ed0f405756f0a4b02ab4dcbb14fdb8d49d8bfd1ad205295828"
    ),
    "benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json": (
        "5cb54cc7baea939b439c617ee917badff64bface2f2fe5a85b128185fdf3ed3c"
    ),
    "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json": (
        "a992059a24b5afbd26c22f71916d7266ada9c3e9ed1fe1354447c7f5f2c40d26"
    ),
    "benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json": (
        "6b77d29fa3b8badd7400e53fa96cd544ecf84d51563170bfc44d56975ff470c3"
    ),
    "benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json": (
        "e22e561618726c339bd955d1c7cfcf573080c251549e6a89c8187251d6011e36"
    ),
    "tests/fixtures/retrieval-eval-v1.json": (
        "a65b33e011c7a39245a2202fa741e57a268b42da9f68d8da0725955834dd4761"
    ),
    "tests/fixtures/retrieval-numeric-v1/protocol-lock.json": (
        "17c424e49237deba600fef70d47da803fb73f72d2ee65995fc155dc96e22da60"
    ),
    "tests/fixtures/retrieval-chinese-v1/protocol.json": (
        "00f72934018a52b5b5f5591fba119050882aee9b782e5dac199702b0cf995944"
    ),
    "tests/fixtures/retrieval-dense-v1/protocol-lock.json": (
        "afca992a7115fdb06e620168d14f8d09055f231c061b59f82c69f0be2a6e4251"
    ),
    "tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json": (
        "2407fb3d9abfe1a1127c5d9a600dea529c32c308a42cbd3622c52211d314a716"
    ),
    "tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json": (
        "6983eb5243493176d6cf97a5e7b5ae888aac9885c25e945583bc291aacf253b1"
    ),
    "benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json": (
        "1a98e4e6c4eabc01663991646aac46e4a73033eef8a7e17a27db2e0fdce71691"
    ),
}
_FAMILY_NAMES = (
    "e1_baseline",
    "e2_numeric",
    "e3a_chinese",
    "e3b_cjk_lexical",
    "e3c_dense",
    "e3d_hybrid_rrf",
    "e3e_relevance_gate",
)
_CANONICAL_LAYER_STATUS_FIELDS = (
    "historical_bytes_frozen",
    "archived_record_self_consistent",
    "current_runtime_replay_compatible",
    "revision_2_differential_valid",
)

RecordedExactScore = Literal[
    "direct",
    "derived_from_recorded_parent",
    "not_recorded",
]
TieGroupAuthority = Literal[
    "deterministic_historical_subprocess_replay",
    "no_ordered_delta_authority",
    "direct_recorded_score",
    "direct_recorded_overlap",
    "derived_from_recorded_parent",
]


class RetrievalOrderCompatibilityError(ValueError):
    """A historical/current retrieval-order differential is not trustworthy."""


@dataclass(frozen=True)
class FamilyCapability:
    family: str
    recorded_order_projection: str
    recorded_exact_score: RecordedExactScore
    historical_runtime_profile: str
    historical_source_tree_resolved: bool
    tie_group_authority: TieGroupAuthority
    allowed_delta: Literal["preidentified_tie_permutation_only"]


@dataclass(frozen=True)
class HistoricalReplayCapability:
    status: Literal[
        "deterministic_historical_subprocess_replay",
        "no_ordered_delta_authority",
    ]
    source_commit: str
    source_tree: str
    source_identity: str
    recorded_blob_count: int
    runtime_profile: dict[str, str]
    bootstrap_sha256: str
    child_argv: tuple[str, ...]
    checkout_external_cwd: bool
    python_no_user_site: bool
    inherited_python_path_cleared: bool
    inherited_python_home_cleared: bool
    module_origins_valid: bool
    input_identities_valid: bool
    first_stdout: str
    second_stdout: str


_HISTORICAL_BOOTSTRAP = r"""
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

import fitz
import mke
from mke.evaluation import numeric_comparison, runner
from mke.evaluation.report import render_retrieval_json_report
from mke.retrieval import compile_fts5_query

request = json.load(sys.stdin)
repository = Path(request["repository"]).resolve()
source_root = (repository / "src").resolve()
cwd = Path.cwd().resolve()

def is_under(path, root):
    return path == root or path.is_relative_to(root)

runtime = {
    "python": ".".join(str(item) for item in sys.version_info[:3]),
    "sqlite": sqlite3.sqlite_version,
    "pymupdf": fitz.VersionBind,
}
if runtime != request["runtime"]:
    raise SystemExit("runtime_mismatch")
if not is_under(Path(mke.__file__).resolve(), source_root):
    raise SystemExit("mke_origin_mismatch")
if not is_under(Path(runner.__file__).resolve(), source_root):
    raise SystemExit("runner_origin_mismatch")
if is_under(Path(fitz.__file__).resolve(), source_root):
    raise SystemExit("pymupdf_origin_mismatch")
if is_under(Path(json.__file__).resolve(), source_root):
    raise SystemExit("stdlib_origin_mismatch")
if is_under(cwd, Path(request["checkout"]).resolve()):
    raise SystemExit("cwd_not_external")
if os.environ.get("PYTHONNOUSERSITE") != "1":
    raise SystemExit("user_site_enabled")
if os.environ.get("PYTHONHOME"):
    raise SystemExit("pythonhome_inherited")

for record in request["inputs"]:
    path = (repository / record["path"]).resolve()
    if not is_under(path, repository):
        raise SystemExit("input_path_escape")
    data = path.read_bytes()
    if len(data) != record["bytes"]:
        raise SystemExit("input_bytes_mismatch")
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise SystemExit("input_digest_mismatch")

def tie_groups(stable_projections, scores):
    grouped = {}
    for projection, score in zip(stable_projections, scores, strict=True):
        grouped.setdefault(score, []).append(projection)
    return [
        {
            "score_hex": score,
            "stable_projections": grouped[score],
        }
        for score in sorted(grouped)
        if len(grouped[score]) > 1
    ]

def replay(manifest_path, policy):
    captured = {}
    original = runner._search_locators

    def capture(engine, query, source_documents):
        results = engine.search(query.text, limit=5)
        compiled = compile_fts5_query(
            query.text,
            policy=engine._store._query_policy,
        )
        score_hex = []
        stable_projections = []
        if compiled:
            all_results = {item.evidence_id: item for item in results}
            profile = engine._store.observe_fts5_rank(compiled)
            for observation in profile.rank_order:
                if observation.evidence_id not in all_results:
                    continue
                item = all_results[observation.evidence_id]
                projection = [
                    source_documents[item.source_id],
                    item.locator_kind,
                    item.locator_start,
                    item.locator_end,
                ]
                stable_projections.append(projection)
                score_hex.append(observation.rank_score.hex())
        key = f"{policy}:{query.query_id}"
        record = {
            "policy": policy,
            "query_id": query.query_id,
            "stable_projections": stable_projections,
            "score_hex": score_hex,
            "tie_groups": tie_groups(stable_projections, score_hex),
        }
        previous = captured.get(key)
        if previous is not None and previous != record:
            raise SystemExit("historical_replay_nondeterministic")
        captured[key] = record
        return tuple(
            runner._stable_locator(item, source_documents)
            for item in results
        )

    runner._search_locators = capture
    try:
        observation = runner._observe_retrieval_evaluation(
            manifest_path,
            query_policy=policy,
        )
    finally:
        runner._search_locators = original
    if observation.report.status != "passed":
        raise SystemExit("historical_evaluation_failed")
    return observation, captured

e1_observation, e1_queries = replay(
    repository / "tests/fixtures/retrieval-eval-v1.json",
    "current",
)
e1_report = json.loads(render_retrieval_json_report(e1_observation.report))
e1_report.pop("duration_ms", None)

captured = {}
original = runner._search_locators

def capture_numeric(engine, query, source_documents):
    results = engine.search(query.text, limit=5)
    policy = engine._store._query_policy
    compiled = compile_fts5_query(query.text, policy=policy)
    score_hex = []
    stable_projections = []
    if compiled:
        all_results = {item.evidence_id: item for item in results}
        profile = engine._store.observe_fts5_rank(compiled)
        for observation in profile.rank_order:
            if observation.evidence_id not in all_results:
                continue
            item = all_results[observation.evidence_id]
            projection = [
                source_documents[item.source_id],
                item.locator_kind,
                item.locator_start,
                item.locator_end,
            ]
            stable_projections.append(projection)
            score_hex.append(observation.rank_score.hex())
    key = f"{policy}:{query.query_id}"
    record = {
        "policy": policy,
        "query_id": query.query_id,
        "stable_projections": stable_projections,
        "score_hex": score_hex,
        "tie_groups": tie_groups(stable_projections, score_hex),
    }
    previous = captured.get(key)
    if previous is not None and previous != record:
        raise SystemExit("historical_numeric_nondeterministic")
    captured[key] = record
    return tuple(
        runner._stable_locator(item, source_documents)
        for item in results
    )

runner._search_locators = capture_numeric
try:
    numeric_report = numeric_comparison.run_numeric_comparison(
        repository / "tests/fixtures/retrieval-numeric-v1/protocol-lock.json"
    )
finally:
    runner._search_locators = original
if numeric_report.integrity_status != "passed":
    raise SystemExit("historical_numeric_failed")
numeric_payload = json.loads(
    numeric_comparison.render_numeric_comparison_json(numeric_report)
)
numeric_payload.pop("duration_ms", None)

def ordered_queries(records):
    return [records[key] for key in sorted(records)]

payload = {
    "families": {
        "e1_baseline": {
            "queries": ordered_queries(e1_queries),
            "semantic_report": e1_report,
        },
        "e2_numeric": {
            "queries": ordered_queries(captured),
            "semantic_report": numeric_payload,
        },
    },
    "origins": {
        "checkout_external_cwd": True,
        "module_origins_valid": True,
    },
    "runtime": runtime,
    "source": {
        "blob_count": request["blob_count"],
        "identity": request["source_identity"],
        "tree": request["source_tree"],
    },
}
print(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
""".strip()


def family_capability_table(
    *,
    historical_capability: HistoricalReplayCapability,
) -> tuple[FamilyCapability, ...]:
    historical_authority: TieGroupAuthority = historical_capability.status
    rows = (
        (
            "e1_baseline",
            "retrieval_result_stable_locators",
            "not_recorded",
            "python_sqlite_pymupdf_exact",
            historical_authority,
        ),
        (
            "e2_numeric",
            "partition_policy_stable_locators",
            "not_recorded",
            "python_sqlite_pymupdf_exact",
            historical_authority,
        ),
        (
            "e3a_chinese",
            "ordered_retrieved_locators",
            "direct",
            "repository_environment_contract",
            "direct_recorded_score",
        ),
        (
            "e3b_cjk_lexical",
            "candidate_result_locators",
            "direct",
            "evaluation_runtime_contract",
            "direct_recorded_overlap",
        ),
        (
            "e3c_dense",
            "dense_result_locators",
            "direct",
            "recorded_model_free_semantics",
            "direct_recorded_score",
        ),
        (
            "e3d_hybrid_rrf",
            "fused_result_locators",
            "derived_from_recorded_parent",
            "recorded_model_free_semantics",
            "derived_from_recorded_parent",
        ),
        (
            "e3e_relevance_gate",
            "allowed_result_locators",
            "derived_from_recorded_parent",
            "recorded_model_free_semantics",
            "derived_from_recorded_parent",
        ),
    )
    return tuple(
        FamilyCapability(
            family=family,
            recorded_order_projection=projection,
            recorded_exact_score=cast(RecordedExactScore, score),
            historical_runtime_profile=runtime,
            historical_source_tree_resolved=(
                historical_capability.status
                == "deterministic_historical_subprocess_replay"
            ),
            tie_group_authority=cast(TieGroupAuthority, authority),
            allowed_delta="preidentified_tie_permutation_only",
        )
        for family, projection, score, runtime, authority in rows
    )


def freeze_historical_capabilities(
    *,
    repository_root: Path,
    workspace: Path,
    numeric_artifact_path: Path | None = None,
) -> HistoricalReplayCapability:
    root = repository_root.resolve()
    scratch = workspace.resolve()
    try:
        if scratch.is_relative_to(root):
            raise ValueError
        numeric_path = (
            root / _NUMERIC_ARTIFACT
            if numeric_artifact_path is None
            else numeric_artifact_path.resolve()
        )
        numeric = _load_object(numeric_path)
        chinese = _load_object(root / _CHINESE_ARTIFACT)
        numeric_source = _source(numeric["source"])
        chinese_source = _source(chinese["source_identity"])
        if numeric_source != chinese_source:
            raise ValueError
        validate_recorded_source_identity(numeric_source)
        if (
            numeric_source["sha256"] != _SOURCE_IDENTITY
            or len(cast(list[object], numeric_source["files"])) != 107
        ):
            raise ValueError
        _validate_all_archived_authority(root)
        historical_root = scratch / "historical-replay" / "repository"
        source_paths, input_paths = _historical_materialization_plan(
            root,
            historical_root,
            numeric_source,
        )
        historical_root.mkdir(parents=True, exist_ok=False)
        _materialize_historical_source(
            root,
            historical_root,
            numeric_source,
            source_paths=source_paths,
        )
        inputs = _materialize_historical_inputs(
            root,
            historical_root,
            relative_paths=input_paths,
        )
        child_cwd = scratch / "historical-replay" / "child-cwd"
        child_cwd.mkdir()
        request: dict[str, object] = {
            "blob_count": 107,
            "checkout": root.as_posix(),
            "inputs": inputs,
            "repository": historical_root.as_posix(),
            "runtime": _RUNTIME_PROFILE,
            "source_identity": _SOURCE_IDENTITY,
            "source_tree": _SOURCE_TREE,
        }
        first = _run_historical_child(
            repository=historical_root,
            child_cwd=child_cwd,
            request=request,
        )
        second = _run_historical_child(
            repository=historical_root,
            child_cwd=child_cwd,
            request=request,
        )
        if first != second:
            raise ValueError
        payload = _load_json_stdout(first)
        if (
            payload.get("runtime") != _RUNTIME_PROFILE
            or _object(payload.get("source")).get("blob_count") != 107
            or set(_object(payload.get("families")))
            != {"e1_baseline", "e2_numeric"}
        ):
            raise ValueError
        _bind_historical_payload(payload, root)
        return _capability(
            status="deterministic_historical_subprocess_replay",
            first=first,
            second=second,
            origins=True,
            inputs=True,
        )
    except RetrievalOrderCompatibilityError:
        raise
    except Exception:
        return _capability(
            status="no_ordered_delta_authority",
            first="",
            second="",
            origins=False,
            inputs=False,
        )


def build_compatibility_artifact(
    *,
    protocol_path: Path,
    repository_root: Path,
    workspace: Path,
) -> dict[str, object]:
    root = repository_root.resolve()
    scratch = workspace.resolve()
    capability = freeze_historical_capabilities(
        repository_root=root,
        workspace=scratch / "capability",
    )
    _validate_all_archived_authority(root)
    protocol = load_retrieval_order_protocol_metadata(
        protocol_path,
        repository_root=root,
    )
    current_source = _current_source_identity(root)
    historical_payload = (
        _bind_historical_payload(
            _load_json_stdout(capability.first_stdout),
            root,
        )
        if capability.status
        == "deterministic_historical_subprocess_replay"
        else None
    )
    e1_current, e2_current = _current_e1_e2(root)
    current_root = scratch / "current-artifacts"
    current_root.mkdir(parents=True, exist_ok=True)
    e3a_current = _current_chinese_artifact(root, current_root)
    e3b_current = _current_cjk_artifact(root, current_root)
    families = [
        _e1_e2_family(
            family="e1_baseline",
            capability=capability,
            historical_payload=historical_payload,
            current_payload=e1_current,
            current_source=current_source,
            root=root,
        ),
        _e1_e2_family(
            family="e2_numeric",
            capability=capability,
            historical_payload=historical_payload,
            current_payload=e2_current,
            current_source=current_source,
            root=root,
        ),
        _e3a_family(
            current=e3a_current,
            current_source=current_source,
            root=root,
        ),
        _e3b_family(
            current=e3b_current,
            current_source=current_source,
            root=root,
        ),
        _e3c_family(current_source=current_source, root=root),
        _e3d_family(current_source=current_source, root=root),
        _e3e_family(current_source=current_source, root=root),
    ]
    if any(item["status"] != "passed" for item in families):
        raise RetrievalOrderCompatibilityError
    return {
        "schema_version": "mke.retrieval_order_compatibility.v1",
        "protocol": {
            "id": protocol.protocol_id,
            "path": protocol_path.resolve().relative_to(root).as_posix(),
            "sha256": _sha256(protocol_path),
        },
        "historical_capability": {
            "status": capability.status,
            "source_commit": capability.source_commit,
            "source_tree": capability.source_tree,
            "source_identity": capability.source_identity,
            "recorded_blob_count": capability.recorded_blob_count,
            "runtime_profile": capability.runtime_profile,
            "bootstrap_sha256": capability.bootstrap_sha256,
            "stdout_sha256": (
                _sha256_bytes(capability.first_stdout.encode())
                if capability.first_stdout
                else None
            ),
        },
        "current_source": current_source,
        "families": families,
        "integrity_status": "passed",
        "compatibility_status": "passed",
        "limitations": [
            "historical_compatibility_only",
            "tie_permutation_only",
            "no_relevance_improvement_claim",
            "no_runtime_promotion",
            "public_holdout_not_observed",
        ],
    }


def render_compatibility_artifact(artifact: dict[str, object]) -> bytes:
    return (
        json.dumps(
            artifact,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def validate_compatibility_artifact(
    artifact: object,
    *,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    root = repository_root.resolve()
    protocol = protocol_path.resolve()
    value = _object(artifact)
    if set(value) != {
        "schema_version",
        "protocol",
        "historical_capability",
        "current_source",
        "families",
        "integrity_status",
        "compatibility_status",
        "limitations",
    }:
        raise RetrievalOrderCompatibilityError
    if (
        value["schema_version"]
        != "mke.retrieval_order_compatibility.v1"
        or value["integrity_status"] != "passed"
        or value["compatibility_status"] != "passed"
    ):
        raise RetrievalOrderCompatibilityError
    protocol_record = _object(value["protocol"])
    if protocol_record != {
        "id": "retrieval-order-v1",
        "path": protocol.relative_to(root).as_posix(),
        "sha256": _sha256(protocol),
    }:
        raise RetrievalOrderCompatibilityError
    capability = _object(value["historical_capability"])
    if (
        set(capability)
        != {
            "status",
            "source_commit",
            "source_tree",
            "source_identity",
            "recorded_blob_count",
            "runtime_profile",
            "bootstrap_sha256",
            "stdout_sha256",
        }
        or capability["status"]
        not in {
            "deterministic_historical_subprocess_replay",
            "no_ordered_delta_authority",
        }
        or capability["source_commit"] != _SOURCE_COMMIT
        or capability["source_tree"] != _SOURCE_TREE
        or capability["source_identity"] != _SOURCE_IDENTITY
        or type(capability["recorded_blob_count"]) is not int
        or capability["recorded_blob_count"] != 107
        or capability["runtime_profile"] != _RUNTIME_PROFILE
        or capability["bootstrap_sha256"]
        != hashlib.sha256(_HISTORICAL_BOOTSTRAP.encode()).hexdigest()
    ):
        raise RetrievalOrderCompatibilityError
    capability_status = cast(str, capability["status"])
    stdout_sha256 = capability["stdout_sha256"]
    if (
        capability_status == "deterministic_historical_subprocess_replay"
        and not _is_sha256(stdout_sha256)
    ) or (
        capability_status == "no_ordered_delta_authority"
        and stdout_sha256 is not None
    ):
        raise RetrievalOrderCompatibilityError
    if value["current_source"] != _current_source_identity(root):
        raise RetrievalOrderCompatibilityError
    raw_families = value["families"]
    if not isinstance(raw_families, list):
        raise RetrievalOrderCompatibilityError
    families = cast(list[object], raw_families)
    if len(families) != 7:
        raise RetrievalOrderCompatibilityError
    expected_names = _FAMILY_NAMES
    family_keys = {
        "family",
        "historical_input",
        "archived_self_consistency_status",
        "current_source_identity",
        "runtime_profile",
        "preidentified_exact_score_tie_groups",
        "before_after_stable_projections",
        "membership_delta",
        "score_hex_delta",
        "non_tied_pair_delta",
        "metric_delta",
        "gate_delta",
        "verdict_delta",
        "status",
    }
    for expected_name, raw_family in zip(
        expected_names,
        families,
        strict=True,
    ):
        family = _object(raw_family)
        if (
            set(family) != family_keys
            or family["family"] != expected_name
            or family["archived_self_consistency_status"] != "passed"
            or family["current_source_identity"]
            != _object(value["current_source"])["sha256"]
            or family["status"] != "passed"
        ):
            raise RetrievalOrderCompatibilityError
        for delta in (
            "membership_delta",
            "score_hex_delta",
            "non_tied_pair_delta",
            "metric_delta",
            "gate_delta",
            "verdict_delta",
        ):
            if type(family[delta]) is not int or family[delta] != 0:
                raise RetrievalOrderCompatibilityError
        if not isinstance(
            family["preidentified_exact_score_tie_groups"], list
        ) or not isinstance(
            family["before_after_stable_projections"], list
        ):
            raise RetrievalOrderCompatibilityError
        _validate_recorded_differential(family)
        historical_input = _object(family["historical_input"])
        artifact_path, family_protocol = _HISTORICAL_INPUTS[expected_name]
        if historical_input != {
            "artifact": _file_identity(root, artifact_path),
            "protocol": _file_identity(root, family_protocol),
        }:
            raise RetrievalOrderCompatibilityError
        if (
            capability_status == "no_ordered_delta_authority"
            and expected_name in {"e1_baseline", "e2_numeric"}
            and (
                family["preidentified_exact_score_tie_groups"]
                or any(
                    _object(item)["before"] != _object(item)["after"]
                    for item in cast(
                        list[object],
                        family["before_after_stable_projections"],
                    )
                )
            )
        ):
            raise RetrievalOrderCompatibilityError
    if value["limitations"] != [
        "historical_compatibility_only",
        "tie_permutation_only",
        "no_relevance_improvement_claim",
        "no_runtime_promotion",
        "public_holdout_not_observed",
    ]:
        raise RetrievalOrderCompatibilityError


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_recorded_differential(
    family: dict[str, object],
) -> None:
    raw_projections = cast(
        list[object],
        family["before_after_stable_projections"],
    )
    if not raw_projections:
        raise RetrievalOrderCompatibilityError
    projections_by_key: dict[
        tuple[str, str],
        tuple[list[tuple[object, ...]], list[tuple[object, ...]]],
    ] = {}
    for raw in raw_projections:
        record = _object(raw)
        if set(record) != {"policy", "query_id", "before", "after"}:
            raise RetrievalOrderCompatibilityError
        key = _query_key(record)
        if key in projections_by_key:
            raise RetrievalOrderCompatibilityError
        before = _projection_sequence(record["before"])
        after = _projection_sequence(record["after"])
        if set(before) != set(after):
            raise RetrievalOrderCompatibilityError
        projections_by_key[key] = (before, after)
    allowed_ties: dict[
        tuple[str, str],
        list[set[tuple[object, ...]]],
    ] = {}
    for raw in cast(
        list[object],
        family["preidentified_exact_score_tie_groups"],
    ):
        tie = _object(raw)
        if set(tie) != {
            "policy",
            "query_id",
            "score_hex",
            "stable_projections",
        }:
            raise RetrievalOrderCompatibilityError
        key = _query_key(tie)
        if (
            not isinstance(tie["score_hex"], str)
            or not tie["score_hex"]
        ):
            raise RetrievalOrderCompatibilityError
        group = set(_projection_sequence(tie["stable_projections"]))
        if len(group) < 2 or key not in projections_by_key:
            raise RetrievalOrderCompatibilityError
        if not group.issubset(set(projections_by_key[key][0])):
            raise RetrievalOrderCompatibilityError
        allowed_ties.setdefault(key, []).append(group)
    for key, (before, after) in projections_by_key.items():
        if before == after:
            continue
        positions = {item: index for index, item in enumerate(after)}
        for index, left in enumerate(before):
            for right in before[index + 1 :]:
                if positions[left] < positions[right]:
                    continue
                if not any(
                    {left, right}.issubset(group)
                    for group in allowed_ties.get(key, [])
                ):
                    raise RetrievalOrderCompatibilityError


def _projection_sequence(value: object) -> list[tuple[object, ...]]:
    if not isinstance(value, list):
        raise RetrievalOrderCompatibilityError
    result: list[tuple[object, ...]] = []
    for item in cast(list[object], value):
        if not isinstance(item, list):
            raise RetrievalOrderCompatibilityError
        projection = cast(list[object], item)
        if (
            len(projection) != 4
            or not isinstance(projection[0], str)
            or not isinstance(projection[1], str)
            or type(projection[2]) is not int
            or type(projection[3]) is not int
        ):
            raise RetrievalOrderCompatibilityError
        result.append(tuple(projection))
    if len(result) != len(set(result)):
        raise RetrievalOrderCompatibilityError
    return result


def _result_payload(
    *,
    command: Literal["record", "validate"],
    status: Literal["passed", "failed"],
    output_state: str,
    publication_outcome: str,
    problem: str,
    cause: str,
    next_step: str,
    canonical: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": (
            "mke.retrieval_order_compatibility_"
            f"{command}_result.v1"
        ),
        "status": status,
        "mode": command,
        "authority_layer": (
            "archive_current_differential"
            if command == "record"
            else "artifact_validation"
        ),
        "canonical": canonical,
        "output_state": output_state,
        "publication_outcome": publication_outcome,
        "problem": problem,
        "cause": cause,
        "next_step": next_step,
        "first_failed_gate": (
            "none" if status == "passed" else "compatibility"
        ),
        "stage_statuses": [
            {
                "name": "compatibility",
                "status": "passed" if status == "passed" else "failed",
            }
        ],
        "historical_revision": 1 if status == "passed" else 0,
        "current_revision": 2 if status == "passed" else 0,
    }


def _failed_result(
    *,
    command: Literal["record", "validate"],
    problem: str,
    output_state: str = "not_applicable",
    publication_outcome: str = "not_attempted",
) -> dict[str, object]:
    return _result_payload(
        command=command,
        status="failed",
        output_state=output_state,
        publication_outcome=publication_outcome,
        problem=problem,
        cause="unapproved_family_delta",
        next_step="inspect_first_failed_family",
    )


def _publication_payload(
    result: AtomicPublicationResult,
) -> dict[str, object]:
    status: Literal["passed", "failed"] = (
        "passed"
        if result.publication_outcome == "published"
        else "failed"
    )
    return _result_payload(
        command="record",
        status=status,
        output_state=result.output_state,
        publication_outcome=result.publication_outcome,
        problem=(
            "none"
            if status == "passed"
            else "retrieval_order_compatibility_incomplete"
        ),
        cause=(
            "none" if status == "passed" else "unapproved_family_delta"
        ),
        next_step=(
            "none"
            if status == "passed"
            else "inspect_first_failed_family"
        ),
    )


def record_temporary_compatibility(
    *,
    protocol_path: Path,
    artifact_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    root = repository_root.resolve()
    destination = artifact_path.resolve()
    if destination == (root / _CANONICAL_ARTIFACT).resolve():
        return _result_payload(
            command="record",
            status="failed",
            output_state="not_applicable",
            publication_outcome="not_attempted",
            problem="retrieval_order_canonical_publication_unauthorized",
            cause="required_success_authority_missing",
            next_step="wait_for_successful_holdout",
        )
    try:
        with tempfile.TemporaryDirectory(
            prefix="mke-retrieval-order-compatibility-"
        ) as workspace:
            artifact = build_compatibility_artifact(
                protocol_path=protocol_path,
                repository_root=root,
                workspace=Path(workspace),
            )
        validate_compatibility_artifact(
            artifact,
            protocol_path=protocol_path,
            repository_root=root,
        )
        content = render_compatibility_artifact(artifact)
        result = publish_json_no_replace(
            destination,
            content,
            validate=lambda candidate: validate_compatibility_artifact(
                candidate,
                protocol_path=protocol_path,
                repository_root=root,
            ),
        )
        return _publication_payload(result)
    except Exception:
        return _failed_result(
            command="record",
            problem="retrieval_order_compatibility_incomplete",
        )


def validate_temporary_compatibility(
    *,
    protocol_path: Path,
    artifact_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    root = repository_root.resolve()
    canonical = (
        artifact_path.resolve() == (root / _CANONICAL_ARTIFACT).resolve()
    )
    try:
        content = artifact_path.read_bytes()
        candidate = _object(json.loads(content))
        if canonical:
            authority = _validate_retained_canonical_authority(
                candidate,
                protocol_path=protocol_path,
                repository_root=root,
            )
            _validate_canonical_artifact(
                candidate,
                protocol_path=protocol_path,
                repository_root=root,
                expected_authority=authority,
            )
        else:
            validate_compatibility_artifact(
                candidate,
                protocol_path=protocol_path,
                repository_root=root,
            )
    except Exception:
        return _result_payload(
            command="validate",
            status="failed",
            output_state="not_applicable",
            publication_outcome="not_attempted",
            problem="retrieval_order_archive_invalid",
            cause="recorded_structure_or_identity_invalid",
            next_step="inspect_immutable_archive",
            canonical=canonical,
        )
    return _result_payload(
        command="validate",
        status="passed",
        output_state="complete_preexisting",
        publication_outcome="not_attempted",
        problem="none",
        cause="none",
        next_step="none",
        canonical=canonical,
    )


_CANONICAL_ATTEMPT = Path(
    "benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json"
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
_CANONICAL_CAPABILITY_ISSUER = object()


@dataclass(init=False)
class _CanonicalPublicationCapability:
    repository_root: Path
    protocol_path: Path
    protocol_sha256: str
    development_freeze_path: Path
    development_freeze_sha256: str
    holdout_receipt_path: Path
    holdout_receipt_sha256: str
    retrieval_artifact_path: Path
    retrieval_artifact_sha256: str
    attempt_path: Path
    attempt_sha256: str
    expected_attempt: dict[str, object]
    candidate_head: str
    runtime_profile: dict[str, object]
    status_records: tuple[tuple[str, str, str | None], ...]
    _consumed: bool

    def __init__(
        self,
        *,
        issuer: object,
        repository_root: Path,
        protocol_path: Path,
        protocol_sha256: str,
        development_freeze_path: Path,
        development_freeze_sha256: str,
        holdout_receipt_path: Path,
        holdout_receipt_sha256: str,
        retrieval_artifact_path: Path,
        retrieval_artifact_sha256: str,
        attempt_path: Path,
        attempt_sha256: str,
        expected_attempt: dict[str, object],
        candidate_head: str,
        runtime_profile: dict[str, object],
        status_records: tuple[tuple[str, str, str | None], ...],
    ) -> None:
        if issuer is not _CANONICAL_CAPABILITY_ISSUER:
            raise RetrievalOrderCompatibilityError
        self.repository_root = repository_root.resolve()
        self.protocol_path = protocol_path
        self.protocol_sha256 = protocol_sha256
        self.development_freeze_path = development_freeze_path
        self.development_freeze_sha256 = development_freeze_sha256
        self.holdout_receipt_path = holdout_receipt_path
        self.holdout_receipt_sha256 = holdout_receipt_sha256
        self.retrieval_artifact_path = retrieval_artifact_path
        self.retrieval_artifact_sha256 = retrieval_artifact_sha256
        self.attempt_path = attempt_path
        self.attempt_sha256 = attempt_sha256
        self.expected_attempt = expected_attempt
        self.candidate_head = candidate_head
        self.runtime_profile = runtime_profile
        self.status_records = status_records
        self._consumed = False

    def consume(self) -> None:
        if self._consumed:
            raise RetrievalOrderCompatibilityError
        self.revalidate()
        self._consumed = True

    def revalidate(self) -> None:
        metadata = load_retrieval_order_protocol_metadata(
            self.protocol_path,
            repository_root=self.repository_root,
        )
        retained = validate_retrieval_order_artifact(
            _load_object(self.retrieval_artifact_path),
            protocol_path=self.protocol_path,
            repository_root=self.repository_root,
        )
        candidate = retrieval_order_workflow._candidate_seal(  # pyright: ignore[reportPrivateUsage]
            self.repository_root,
            expected_status={
                self.development_freeze_path: "??",
                self.holdout_receipt_path: "??",
                self.retrieval_artifact_path: "??",
                self.attempt_path: "??",
            },
        )
        retained_candidate = _object(retained["candidate_seal"])
        expected_candidate = {
            "head": self.candidate_head,
            "runtime_profile": self.runtime_profile,
        }
        if (
            metadata.protocol_sha256 != self.protocol_sha256
            or _sha256(self.development_freeze_path)
            != self.development_freeze_sha256
            or _sha256(self.holdout_receipt_path)
            != self.holdout_receipt_sha256
            or _sha256(self.retrieval_artifact_path)
            != self.retrieval_artifact_sha256
            or _sha256(self.attempt_path) != self.attempt_sha256
            or _load_object(self.attempt_path) != self.expected_attempt
            or retained_candidate != expected_candidate
            or candidate["head"] != self.candidate_head
            or candidate["runtime_profile"] != self.runtime_profile
            or candidate["status_records"] != self.status_records
        ):
            raise RetrievalOrderCompatibilityError


def _canonical_result(
    *,
    status: Literal["passed", "failed"],
    publication: AtomicPublicationResult | None,
    problem: str,
    cause: str,
    next_step: str,
    first_failed_gate: str,
) -> dict[str, object]:
    return {
        "schema_version": (
            "mke.retrieval_order_compatibility_"
            "record_canonical_result.v1"
        ),
        "status": status,
        "mode": "record_canonical",
        "authority_layer": "canonical_publication",
        "canonical": True,
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
        "first_failed_gate": first_failed_gate,
        "stage_statuses": [
            {
                "name": "canonical_publication",
                "status": "passed" if status == "passed" else "failed",
            }
        ],
        "historical_revision": 1 if status == "passed" else 0,
        "current_revision": 2 if status == "passed" else 0,
    }


def _canonical_failure(
    *,
    problem: str,
    cause: str,
    next_step: str,
    first_failed_gate: str,
    publication: AtomicPublicationResult | None = None,
) -> dict[str, object]:
    return _canonical_result(
        status="failed",
        publication=publication,
        problem=problem,
        cause=cause,
        next_step=next_step,
        first_failed_gate=first_failed_gate,
    )


def _postattempt_failure(
    *,
    publication: AtomicPublicationResult,
    problem: str,
    cause: str,
    first_failed_gate: str,
) -> dict[str, object]:
    return _canonical_failure(
        problem=problem,
        cause=cause,
        next_step="retain_attempt_and_stop",
        first_failed_gate=first_failed_gate,
        publication=publication,
    )


def _path_preflight_failure() -> dict[str, object]:
    return _canonical_failure(
        problem="retrieval_order_canonical_publication_unauthorized",
        cause="canonical_path_preflight_failed",
        next_step="correct_canonical_paths_before_first_attempt",
        first_failed_gate="path_preflight",
    )


def _preexisting_regular_digest(path: Path) -> str | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(metadata.st_mode):
        raise RetrievalOrderCompatibilityError
    return _sha256(path)


def _canonical_path(
    supplied: Path | str,
    *,
    repository_root: Path,
    expected: Path,
) -> Path:
    root = repository_root.resolve()
    raw = os.fspath(supplied)
    expected_absolute = root / expected
    if (
        not raw
        or "\\" in raw
        or (
            Path(raw).is_absolute()
            and raw != expected_absolute.as_posix()
        )
        or (
            not Path(raw).is_absolute()
            and raw != expected.as_posix()
        )
    ):
        raise RetrievalOrderCompatibilityError
    lexical = Path(raw) if Path(raw).is_absolute() else root / raw
    _require_lexical_containment(
        lexical,
        root=root,
        require_existing=False,
    )
    if lexical != expected_absolute:
        raise RetrievalOrderCompatibilityError
    return lexical


def _contained_input_path(
    supplied: Path | str,
    *,
    repository_root: Path,
) -> Path:
    root = repository_root.resolve()
    raw = os.fspath(supplied)
    path = Path(raw)
    components = raw.split("/")
    if path.is_absolute():
        components = components[1:]
    if (
        not raw
        or "\\" in raw
        or any(component in {"", ".", ".."} for component in components)
        or raw != PurePosixPath(raw).as_posix()
        or (path.parts and path.parts[0].endswith(":"))
    ):
        raise RetrievalOrderCompatibilityError
    lexical = path if path.is_absolute() else root / path
    _require_lexical_containment(
        lexical,
        root=root,
        require_existing=True,
    )
    return lexical


def _validate_attempt_receipt(
    value: object,
    *,
    expected: dict[str, object],
) -> None:
    if _object(value) != expected:
        raise RetrievalOrderCompatibilityError


def _immutable_input_map(repository_root: Path) -> dict[str, str]:
    root = repository_root.resolve()
    actual = {
        path: _sha256(root / path)
        for path in _IMMUTABLE_INPUT_SHA256
    }
    if actual != _IMMUTABLE_INPUT_SHA256:
        raise RetrievalOrderCompatibilityError
    return actual


def _validate_retained_canonical_authority(
    artifact: dict[str, object],
    *,
    protocol_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    root = repository_root.resolve()
    authority = _object(artifact["canonical_authority"])
    attempt = root / _CANONICAL_ATTEMPT
    development = root / _CANONICAL_DEVELOPMENT_FREEZE
    receipt = root / _CANONICAL_HOLDOUT_RECEIPT
    retrieval = root / _CANONICAL_RETRIEVAL_ARTIFACT
    metadata = load_retrieval_order_protocol_metadata(
        protocol_path,
        repository_root=root,
    )
    retained = validate_retrieval_order_artifact(
        _load_object(retrieval),
        protocol_path=protocol_path,
        repository_root=root,
    )
    expected_attempt: dict[str, object] = {
        "schema_version": (
            "mke.retrieval_order_compatibility_attempt.v1"
        ),
        "command_schema": (
            "mke.retrieval_order_compatibility_record_canonical.v1"
        ),
        "candidate_seal": retained["candidate_seal"],
        "protocol_digest": metadata.protocol_sha256,
        "development_freeze_digest": _sha256(development),
        "holdout_receipt_digest": _sha256(receipt),
        "retrieval_artifact_digest": _sha256(retrieval),
        "compatibility_target": _CANONICAL_ARTIFACT.as_posix(),
    }
    _validate_attempt_receipt(
        _load_object(attempt),
        expected=expected_attempt,
    )
    expected = {
        "attempt_receipt": retrieval_order_file_identity(
            attempt,
            repository_root=root,
        ),
        "candidate_seal": retained["candidate_seal"],
        "development_freeze": retrieval_order_file_identity(
            development,
            repository_root=root,
        ),
        "holdout_receipt": retrieval_order_file_identity(
            receipt,
            repository_root=root,
        ),
        "retrieval_artifact": retrieval_order_file_identity(
            retrieval,
            repository_root=root,
        ),
    }
    if authority != expected:
        raise RetrievalOrderCompatibilityError
    return authority


def _validate_canonical_artifact(
    value: object,
    *,
    protocol_path: Path,
    repository_root: Path,
    expected_authority: dict[str, object],
) -> None:
    artifact = _object(value)
    if set(artifact) != {
        "schema_version",
        "protocol",
        "historical_capability",
        "current_source",
        "families",
        "integrity_status",
        "compatibility_status",
        "limitations",
        "immutable_inputs",
        "canonical_authority",
        *_CANONICAL_LAYER_STATUS_FIELDS,
    }:
        raise RetrievalOrderCompatibilityError
    if artifact["canonical_authority"] != expected_authority:
        raise RetrievalOrderCompatibilityError
    if artifact["immutable_inputs"] != _immutable_input_map(
        repository_root
    ):
        raise RetrievalOrderCompatibilityError
    if any(
        artifact[field] != "passed"
        for field in _CANONICAL_LAYER_STATUS_FIELDS
    ):
        raise RetrievalOrderCompatibilityError
    canonical_limitations = [
        "historical_compatibility_only",
        "tie_permutation_only",
        "no_relevance_improvement_claim",
        "no_runtime_promotion",
        "public_holdout_observed",
    ]
    if artifact["limitations"] != canonical_limitations:
        raise RetrievalOrderCompatibilityError
    base = {
        key: item
        for key, item in artifact.items()
        if key
        not in {
            "canonical_authority",
            "immutable_inputs",
            *_CANONICAL_LAYER_STATUS_FIELDS,
        }
    }
    base["limitations"] = [
        *canonical_limitations[:-1],
        "public_holdout_not_observed",
    ]
    validate_compatibility_artifact(
        base,
        protocol_path=protocol_path,
        repository_root=repository_root,
    )


def record_canonical_compatibility(
    *,
    protocol_path: Path | str,
    development_freeze_path: Path | str,
    holdout_receipt_path: Path | str,
    retrieval_artifact_path: Path | str,
    candidate_head: str,
    attempt_receipt_path: Path | str,
    artifact_path: Path | str,
    repository_root: Path,
) -> dict[str, object]:
    root = repository_root.resolve()
    try:
        protocol = _contained_input_path(
            protocol_path,
            repository_root=root,
        )
        development_freeze = _canonical_path(
            development_freeze_path,
            repository_root=root,
            expected=_CANONICAL_DEVELOPMENT_FREEZE,
        )
        holdout_receipt = _canonical_path(
            holdout_receipt_path,
            repository_root=root,
            expected=_CANONICAL_HOLDOUT_RECEIPT,
        )
        retrieval_artifact = _canonical_path(
            retrieval_artifact_path,
            repository_root=root,
            expected=_CANONICAL_RETRIEVAL_ARTIFACT,
        )
        attempt_receipt = _canonical_path(
            attempt_receipt_path,
            repository_root=root,
            expected=_CANONICAL_ATTEMPT,
        )
        destination = _canonical_path(
            artifact_path,
            repository_root=root,
            expected=_CANONICAL_ARTIFACT,
        )
    except Exception:
        return _path_preflight_failure()
    try:
        attempt_digest = _preexisting_regular_digest(attempt_receipt)
    except (OSError, RetrievalOrderCompatibilityError):
        return _path_preflight_failure()
    if attempt_digest is not None:
        return _canonical_failure(
            problem="retrieval_order_canonical_publication_already_started",
            cause="attempt_receipt_exists",
            next_step="retain_attempt_and_stop",
            first_failed_gate="attempt_preexistence",
            publication=AtomicPublicationResult(
                output_state="complete_preexisting",
                publication_outcome="not_attempted",
                sha256=attempt_digest,
                problem=(
                    "retrieval_order_canonical_publication_already_started"
                ),
            ),
        )
    try:
        destination_digest = _preexisting_regular_digest(destination)
    except (OSError, RetrievalOrderCompatibilityError):
        return _path_preflight_failure()
    if destination_digest is not None:
        return _canonical_failure(
            problem="retrieval_order_canonical_output_exists",
            cause="destination_preexists",
            next_step="validate_retained_bytes",
            first_failed_gate="destination_preexistence",
            publication=AtomicPublicationResult(
                output_state="complete_preexisting",
                publication_outcome="not_attempted",
                sha256=destination_digest,
                problem="retrieval_order_canonical_output_exists",
            ),
        )
    try:
        metadata = load_retrieval_order_protocol_metadata(
            protocol,
            repository_root=root,
        )
        immutable_inputs = _immutable_input_map(root)
        retained = validate_retrieval_order_artifact(
            _load_object(retrieval_artifact),
            protocol_path=protocol,
            repository_root=root,
        )
        candidate_seal = _object(retained["candidate_seal"])
        preattempt_candidate = retrieval_order_workflow._candidate_seal(  # pyright: ignore[reportPrivateUsage]
            root,
            expected_status={
                development_freeze: "??",
                holdout_receipt: "??",
                retrieval_artifact: "??",
            },
        )
        git_head = cast(str, preattempt_candidate["head"])
    except Exception:
        return _canonical_failure(
            problem="retrieval_order_canonical_publication_unauthorized",
            cause="required_success_authority_missing",
            next_step="wait_for_successful_holdout",
            first_failed_gate="success_authority",
        )
    expected_candidate_seal = {
        "head": git_head,
        "runtime_profile": preattempt_candidate["runtime_profile"],
    }
    if (
        candidate_head != git_head
        or candidate_seal != expected_candidate_seal
    ):
        return _canonical_failure(
            problem="retrieval_order_candidate_seal_mismatch",
            cause="candidate_inputs_do_not_match_seal",
            next_step="return_to_authority_review",
            first_failed_gate="candidate_seal",
        )
    try:
        if (
            retained["holdout_status"] != "observed"
            or _object(retained["observation"])["observation_status"]
            != "passed"
        ):
            raise RetrievalOrderCompatibilityError
        expected_attempt: dict[str, object] = {
            "schema_version": (
                "mke.retrieval_order_compatibility_attempt.v1"
            ),
            "command_schema": (
                "mke.retrieval_order_compatibility_record_canonical.v1"
            ),
            "candidate_seal": candidate_seal,
            "protocol_digest": metadata.protocol_sha256,
            "development_freeze_digest": _sha256(development_freeze),
            "holdout_receipt_digest": _sha256(holdout_receipt),
            "retrieval_artifact_digest": _sha256(retrieval_artifact),
            "compatibility_target": _CANONICAL_ARTIFACT.as_posix(),
        }
    except Exception:
        return _canonical_failure(
            problem="retrieval_order_canonical_publication_unauthorized",
            cause="required_success_authority_missing",
            next_step="wait_for_successful_holdout",
            first_failed_gate="success_authority",
        )
    attempt_publication = publish_json_no_replace(
        attempt_receipt,
        render_compatibility_artifact(expected_attempt),
        validate=lambda value: _validate_attempt_receipt(
            value,
            expected=expected_attempt,
        ),
    )
    if attempt_publication.publication_outcome != "published":
        return _canonical_failure(
            problem=(
                "retrieval_order_publication_durability_unconfirmed"
                if attempt_publication.publication_outcome
                == "durability_unconfirmed"
                else "retrieval_order_publication_failed_before_visibility"
            ),
            cause=(
                "directory_fsync_failed_after_visibility"
                if attempt_publication.publication_outcome
                == "durability_unconfirmed"
                else "publication_failed_before_final_path"
            ),
            next_step="retain_attempt_and_stop",
            first_failed_gate="attempt_publication",
            publication=attempt_publication,
        )
    assert attempt_publication.sha256 is not None
    try:
        postattempt_candidate = retrieval_order_workflow._candidate_seal(  # pyright: ignore[reportPrivateUsage]
            root,
            expected_status={
                development_freeze: "??",
                holdout_receipt: "??",
                retrieval_artifact: "??",
                attempt_receipt: "??",
            },
        )
        capability = _CanonicalPublicationCapability(
            issuer=_CANONICAL_CAPABILITY_ISSUER,
            repository_root=root,
            protocol_path=protocol,
            protocol_sha256=metadata.protocol_sha256,
            development_freeze_path=development_freeze,
            development_freeze_sha256=_sha256(development_freeze),
            holdout_receipt_path=holdout_receipt,
            holdout_receipt_sha256=_sha256(holdout_receipt),
            retrieval_artifact_path=retrieval_artifact,
            retrieval_artifact_sha256=_sha256(retrieval_artifact),
            attempt_path=attempt_receipt,
            attempt_sha256=attempt_publication.sha256,
            expected_attempt=expected_attempt,
            candidate_head=candidate_head,
            runtime_profile=cast(
                dict[str, object],
                candidate_seal["runtime_profile"],
            ),
            status_records=cast(
                tuple[tuple[str, str, str | None], ...],
                postattempt_candidate["status_records"],
            ),
        )
        capability.consume()
    except Exception:
        return _postattempt_failure(
            publication=attempt_publication,
            problem="retrieval_order_candidate_seal_mismatch",
            cause="candidate_inputs_do_not_match_seal",
            first_failed_gate="capability_consume",
        )
    try:
        with tempfile.TemporaryDirectory(
            prefix="mke-retrieval-order-canonical-"
        ) as workspace:
            base = build_compatibility_artifact(
                protocol_path=protocol,
                repository_root=root,
                workspace=Path(workspace),
            )
        canonical_authority: dict[str, object] = {
            "attempt_receipt": retrieval_order_file_identity(
                attempt_receipt,
                repository_root=root,
            ),
            "candidate_seal": candidate_seal,
            "development_freeze": retrieval_order_file_identity(
                development_freeze,
                repository_root=root,
            ),
            "holdout_receipt": retrieval_order_file_identity(
                holdout_receipt,
                repository_root=root,
            ),
            "retrieval_artifact": retrieval_order_file_identity(
                retrieval_artifact,
                repository_root=root,
            ),
        }
        candidate: dict[str, object] = {
            **base,
            "limitations": [
                *cast(list[object], base["limitations"])[:-1],
                "public_holdout_observed",
            ],
            "immutable_inputs": immutable_inputs,
            "canonical_authority": canonical_authority,
            **{
                field: "passed"
                for field in _CANONICAL_LAYER_STATUS_FIELDS
            },
        }
        _validate_canonical_artifact(
            candidate,
            protocol_path=protocol,
            repository_root=root,
            expected_authority=canonical_authority,
        )
    except Exception:
        return _postattempt_failure(
            publication=attempt_publication,
            problem="retrieval_order_compatibility_incomplete",
            cause="unapproved_family_delta",
            first_failed_gate="compatibility_build",
        )
    try:
        capability.revalidate()
    except Exception:
        return _postattempt_failure(
            publication=attempt_publication,
            problem="retrieval_order_candidate_seal_mismatch",
            cause="candidate_inputs_do_not_match_seal",
            first_failed_gate="final_authority",
        )
    try:
        publication = publish_json_no_replace(
            destination,
            render_compatibility_artifact(candidate),
            validate=lambda value: _validate_canonical_artifact(
                value,
                protocol_path=protocol,
                repository_root=root,
                expected_authority=canonical_authority,
            ),
        )
    except Exception:
        return _postattempt_failure(
            publication=attempt_publication,
            problem="retrieval_order_compatibility_incomplete",
            cause="unapproved_family_delta",
            first_failed_gate="compatibility_publication",
        )
    if publication.publication_outcome != "published":
        return _postattempt_failure(
            publication=attempt_publication,
            problem=(
                "retrieval_order_publication_durability_unconfirmed"
                if publication.publication_outcome
                == "durability_unconfirmed"
                else "retrieval_order_publication_failed_before_visibility"
            ),
            cause=(
                "directory_fsync_failed_after_visibility"
                if publication.publication_outcome
                == "durability_unconfirmed"
                else "publication_failed_before_final_path"
            ),
            first_failed_gate="compatibility_publication",
        )
    return _canonical_result(
        status="passed",
        publication=publication,
        problem="none",
        cause="none",
        next_step="none",
        first_failed_gate="none",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "archive validation -> historical bytes are "
            "self-consistent only\n"
            "current replay -> current runtime compatibility only\n"
            "differential validation -> revision-2 comparison only\n"
            "temporary output -> never canonical authority"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("record", "validate"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--protocol", type=Path, required=True)
        subparser.add_argument("--artifact", type=Path, required=True)
        subparser.add_argument("--repository", type=Path, required=True)
        subparser.add_argument("--json", action="store_true")
    canonical = subparsers.add_parser(
        "record-canonical",
        description=(
            "preflight rejected -> not attempted; correct the input before "
            "any attempt\nattempt visible -> terminal; retain the attempt "
            "and stop"
        ),
    )
    canonical.add_argument("--protocol", required=True)
    canonical.add_argument("--development-freeze", required=True)
    canonical.add_argument("--holdout-receipt", required=True)
    canonical.add_argument("--retrieval-artifact", required=True)
    canonical.add_argument("--candidate-head", required=True)
    canonical.add_argument("--attempt-receipt", required=True)
    canonical.add_argument("--artifact", required=True)
    canonical.add_argument("--repository", type=Path, required=True)
    canonical.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root = arguments.repository.resolve()
    protocol = arguments.protocol
    artifact = arguments.artifact
    if arguments.command != "record-canonical":
        protocol = (
            protocol.resolve()
            if protocol.is_absolute()
            else (root / protocol).resolve()
        )
        artifact = (
            artifact.resolve()
            if artifact.is_absolute()
            else (root / artifact).resolve()
        )
    if arguments.command == "record":
        result = record_temporary_compatibility(
            protocol_path=protocol,
            artifact_path=artifact,
            repository_root=root,
        )
    elif arguments.command == "validate":
        result = validate_temporary_compatibility(
            protocol_path=protocol,
            artifact_path=artifact,
            repository_root=root,
        )
    else:
        result = record_canonical_compatibility(
            protocol_path=protocol,
            development_freeze_path=arguments.development_freeze,
            holdout_receipt_path=arguments.holdout_receipt,
            retrieval_artifact_path=arguments.retrieval_artifact,
            candidate_head=arguments.candidate_head,
            attempt_receipt_path=arguments.attempt_receipt,
            artifact_path=artifact,
            repository_root=root,
        )
    print(
        json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "passed" else 1


def compare_ordered_queries(
    before: list[dict[str, object]],
    after: list[dict[str, object]],
    *,
    tie_group_authority: Literal[
        "deterministic_historical_subprocess_replay",
        "no_ordered_delta_authority",
        "direct_recorded_score",
        "direct_recorded_overlap",
        "derived_from_recorded_parent",
    ],
) -> dict[str, object]:
    before_by_key = {_query_key(item): item for item in before}
    after_by_key = {_query_key(item): item for item in after}
    if before_by_key.keys() != after_by_key.keys():
        raise RetrievalOrderCompatibilityError
    membership_delta = 0
    score_delta = 0
    non_tied_delta = 0
    projections: list[dict[str, object]] = []
    tie_groups: list[dict[str, object]] = []
    for key in sorted(before_by_key):
        previous = before_by_key[key]
        current = after_by_key[key]
        previous_order = _projection_order(previous)
        current_order = _projection_order(current)
        if tie_group_authority == "no_ordered_delta_authority":
            membership_delta += len(
                set(previous_order).symmetric_difference(current_order)
            )
            if previous_order != current_order:
                raise RetrievalOrderCompatibilityError
            projections.append(
                {
                    "policy": key[0],
                    "query_id": key[1],
                    "before": [list(item) for item in previous_order],
                    "after": [list(item) for item in current_order],
                }
            )
            continue
        previous_scores = _score_map(previous)
        current_scores = _score_map(current)
        membership_delta += len(
            set(previous_order).symmetric_difference(current_order)
        )
        all_projections = set(previous_scores) | set(current_scores)
        score_delta += sum(
            previous_scores.get(item) != current_scores.get(item)
            for item in all_projections
        )
        if set(previous_order) == set(current_order):
            current_positions = {
                projection: index
                for index, projection in enumerate(current_order)
            }
            for index, left in enumerate(previous_order):
                for right in previous_order[index + 1 :]:
                    if previous_scores.get(left) == previous_scores.get(right):
                        continue
                    if current_positions[left] > current_positions[right]:
                        non_tied_delta += 1
        elif previous_order != current_order:
            non_tied_delta += 1
        raw_ties = _query_tie_groups(previous)
        tie_groups.extend(
            {
                "policy": key[0],
                "query_id": key[1],
                **group,
            }
            for group in raw_ties
        )
        projections.append(
            {
                "policy": key[0],
                "query_id": key[1],
                "before": [list(item) for item in previous_order],
                "after": [list(item) for item in current_order],
            }
        )
    if membership_delta or score_delta or non_tied_delta:
        raise RetrievalOrderCompatibilityError
    return {
        "preidentified_exact_score_tie_groups": tie_groups,
        "before_after_stable_projections": projections,
        "membership_delta": membership_delta,
        "score_hex_delta": score_delta,
        "non_tied_pair_delta": non_tied_delta,
    }


def _bind_historical_payload(
    payload: dict[str, object],
    root: Path,
) -> dict[str, object]:
    families = _object(payload["families"])
    bound_families = dict(families)
    for family in ("e1_baseline", "e2_numeric"):
        bound_families[family] = _bind_historical_family(
            family,
            _object(families[family]),
            root,
        )
    return {**payload, "families": bound_families}


def _bind_historical_family(
    family: Literal["e1_baseline", "e2_numeric"],
    child: dict[str, object],
    root: Path,
) -> dict[str, object]:
    bound_queries = _bind_child_score_authority(
        _archived_order_queries(family, root),
        cast(list[dict[str, object]], child["queries"]),
    )
    archived_report = _archived_semantic_report(family, root)
    if child["semantic_report"] != archived_report:
        raise RetrievalOrderCompatibilityError
    return {
        "queries": bound_queries,
        "semantic_report": archived_report,
    }


def _bind_child_score_authority(
    archived: list[dict[str, object]],
    child: list[dict[str, object]],
) -> list[dict[str, object]]:
    archived_by_key = {_query_key(item): item for item in archived}
    child_by_key = {_query_key(item): item for item in child}
    if archived_by_key.keys() != child_by_key.keys():
        raise RetrievalOrderCompatibilityError
    result: list[dict[str, object]] = []
    for key in sorted(archived_by_key):
        immutable = archived_by_key[key]
        replayed = child_by_key[key]
        projections = _projection_order(immutable)
        if projections != _projection_order(replayed):
            raise RetrievalOrderCompatibilityError
        raw_scores = replayed.get("score_hex")
        if not isinstance(raw_scores, list):
            raise RetrievalOrderCompatibilityError
        scores = cast(list[object], raw_scores)
        if not all(isinstance(item, str) for item in scores):
            raise RetrievalOrderCompatibilityError
        score_values = cast(list[str], scores)
        if len(score_values) != len(projections):
            raise RetrievalOrderCompatibilityError
        expected_ties = _tie_groups(
            [list(item) for item in projections],
            score_values,
        )
        if replayed.get("tie_groups") != expected_ties:
            raise RetrievalOrderCompatibilityError
        result.append(
            {
                "policy": key[0],
                "query_id": key[1],
                "stable_projections": [list(item) for item in projections],
                "score_hex": score_values,
                "tie_groups": expected_ties,
            }
        )
    return result


def _archived_semantic_report(
    family: Literal["e1_baseline", "e2_numeric"],
    root: Path,
) -> dict[str, object]:
    artifact = _load_object(root / _HISTORICAL_INPUTS[family][0])
    if family == "e2_numeric":
        return _object(artifact["comparison"])
    results = [
        {
            **item,
            "retrieved_locators": [
                {
                    "document_id": projection[0],
                    "locator_kind": projection[1],
                    "locator_start": projection[2],
                    "locator_end": projection[3],
                }
                for projection in (
                    _parse_stable_locator(cast(str, locator))
                    for locator in cast(
                        list[object],
                        item["retrieved_locators"],
                    )
                )
            ],
        }
        for item in cast(list[dict[str, object]], artifact["results"])
    ]
    return {
        "schema_version": artifact["report_schema_version"],
        "manifest_id": artifact["manifest_id"],
        "evaluation": "retrieval",
        "status": "passed",
        "quality_status": "baseline_recorded",
        "benchmark_scope": artifact["benchmark_scope"],
        "quality_gate": artifact["quality_gate"],
        "documents": artifact["documents"],
        "queries": artifact["queries"],
        "answerable": artifact["answerable"],
        "unanswerable": artifact["unanswerable"],
        "category_counts": artifact["category_counts"],
        "metrics": artifact["metrics"],
        "results": results,
        "integrity_failures": [],
    }


def _validate_all_archived_authority(root: Path) -> None:
    _validate_archived_e1(root)
    _validate_archived_e2(root)
    _validate_archived_e3a(
        _load_object(root / _HISTORICAL_INPUTS["e3a_chinese"][0]),
        root,
    )
    _validate_archived_e3b(
        _load_object(root / _HISTORICAL_INPUTS["e3b_cjk_lexical"][0]),
        root,
    )
    _e3c_family(
        current_source=_current_source_identity(root),
        root=root,
    )
    _e3d_family(
        current_source=_current_source_identity(root),
        root=root,
    )
    _e3e_family(
        current_source=_current_source_identity(root),
        root=root,
    )


def _validate_archived_e1(root: Path) -> None:
    try:
        validate_retrieval_baseline(
            artifact_path=root / _HISTORICAL_INPUTS["e1_baseline"][0],
            manifest_path=root / _HISTORICAL_INPUTS["e1_baseline"][1],
            repository_root=root,
        )
    except Exception as error:
        raise RetrievalOrderCompatibilityError from error


def _validate_archived_e2(root: Path) -> None:
    artifact = _load_object(root / _HISTORICAL_INPUTS["e2_numeric"][0])
    try:
        numeric_artifact_module._validate_artifact_schema(  # pyright: ignore[reportPrivateUsage]
            artifact
        )
        numeric_artifact_module._validate_environment(  # pyright: ignore[reportPrivateUsage]
            artifact["environment"]
        )
        validate_recorded_source_identity(_object(artifact["source"]))
        with tempfile.TemporaryDirectory(
            prefix="mke-archived-numeric-validation-"
        ) as snapshot:
            protocol = numeric_comparison.load_archived_numeric_protocol(
                root / _HISTORICAL_INPUTS["e2_numeric"][1],
                snapshot_root=Path(snapshot),
            )
        comparison = _object(artifact["comparison"])
        numeric_artifact_module._validate_comparison_state(  # pyright: ignore[reportPrivateUsage]
            comparison,
            protocol,
        )
        observed = {**comparison, "duration_ms": 0}
        if comparison != numeric_artifact_module._canonical_comparison(  # pyright: ignore[reportPrivateUsage]
            observed,
            protocol,
        ):
            raise RetrievalOrderCompatibilityError
        expected_protocol = {
            "id": protocol.protocol_id,
            "path": _NUMERIC_PROTOCOL.as_posix(),
            "sha256": _sha256(root / _NUMERIC_PROTOCOL),
        }
        manifest_paths = {
            "development": Path(
                "tests/fixtures/retrieval-numeric-v1/development.json"
            ),
            "holdout": Path(
                "tests/fixtures/retrieval-numeric-v1/holdout.json"
            ),
            "e1": _E1_MANIFEST,
        }
        expected_manifests = {
            partition: {
                "id": protocol.loaded_manifests[partition].manifest_id,
                "path": manifest_paths[partition].as_posix(),
                "sha256": _sha256(root / manifest_paths[partition]),
            }
            for partition in ("development", "holdout", "e1")
        }
        expected_fixtures = [
            {
                "partition": partition,
                "path": manifest.documents[0].primary_file.path.as_posix(),
                "bytes": manifest.documents[0].primary_file.bytes,
                "sha256": manifest.documents[0].primary_file.sha256,
            }
            for partition, manifest in (
                ("development", protocol.loaded_manifests["development"]),
                ("holdout", protocol.loaded_manifests["holdout"]),
            )
        ]
        if (
            artifact["protocol"] != expected_protocol
            or artifact["manifests"] != expected_manifests
            or artifact["fixtures"] != expected_fixtures
            or artifact["candidate"]
            != {
                "id": protocol.candidate_id,
                "revision": protocol.candidate_revision,
            }
        ):
            raise RetrievalOrderCompatibilityError
    except Exception as error:
        if isinstance(error, RetrievalOrderCompatibilityError):
            raise
        raise RetrievalOrderCompatibilityError from error


def _validate_archived_e3a(
    artifact: dict[str, object],
    root: Path,
) -> None:
    try:
        protocol_path = root / _HISTORICAL_INPUTS["e3a_chinese"][1]
        protocol = load_chinese_retrieval_protocol(protocol_path)
        observed: dict[str, object] = {
            "schema_version": artifact["report_schema_version"],
            "protocol_id": artifact["protocol_id"],
            "benchmark_scope": artifact["benchmark_scope"],
            "quality_gate": artifact["quality_gate"],
            "integrity_status": "passed",
            "quality_status": "baseline_recorded",
            "documents": artifact["documents"],
            "queries": artifact["queries"],
            "split_counts": artifact["split_counts"],
            "results": artifact["results"],
            "metrics": {
                **_object(artifact["metrics"]),
                "category_metrics": _object(
                    artifact["query_strata"]
                )["category"],
                "compiled_query_empty_metrics": _object(
                    artifact["query_strata"]
                )["compiled_query_empty"],
                "ascii_token_count_metrics": _object(
                    artifact["query_strata"]
                )["ascii_token_count"],
            },
            "qrel_adjudication": {
                key: _object(artifact["qrel_adjudication"])[key]
                for key in (
                    "sha256",
                    "review_status",
                    "reviewed_query_count",
                    "query_page_judgment_count",
                )
            },
            "e3b_decision": artifact["e3b_decision"],
            "e3b_evidence": artifact["e3b_evidence"],
            "e3b_reason": artifact["e3b_reason"],
            "fts5_rank_profile": artifact["fts5_rank_profile"],
            "fts5_rank_observations": artifact[
                "fts5_rank_observations"
            ],
            "integrity_failures": [],
            "duration_ms": 0,
            "limitations": artifact["limitations"],
        }
        validate_recorded_source_identity(
            _object(artifact["source_identity"])
        )
        expected = chinese_artifact_module._canonical_artifact(  # pyright: ignore[reportPrivateUsage]
            observed,
            protocol=protocol,
            protocol_path=protocol_path,
            repository_root=root,
        )
        expected["source_identity"] = artifact["source_identity"]
        if artifact != expected:
            raise RetrievalOrderCompatibilityError
    except Exception as error:
        if isinstance(error, RetrievalOrderCompatibilityError):
            raise
        raise RetrievalOrderCompatibilityError from error


def _validate_archived_e3b(
    artifact: dict[str, object],
    root: Path,
) -> None:
    try:
        protocol_path = root / _HISTORICAL_INPUTS["e3b_cjk_lexical"][1]
        protocol = load_chinese_retrieval_protocol(protocol_path)
        cjk_lexical_artifact_module._validate_artifact_schema(  # pyright: ignore[reportPrivateUsage]
            artifact
        )
        cjk_lexical_artifact_module._validate_archived_source_identity(  # pyright: ignore[reportPrivateUsage]
            artifact["source"]
        )
        comparison = _object(artifact["comparison"])
        expected = cjk_lexical_artifact_module._canonical_artifact(  # pyright: ignore[reportPrivateUsage]
            comparison,
            protocol=protocol,
            protocol_path=protocol_path,
            repository_root=root,
        )
        expected["source"] = artifact["source"]
        if artifact != expected:
            raise RetrievalOrderCompatibilityError
    except Exception as error:
        if isinstance(error, RetrievalOrderCompatibilityError):
            raise
        raise RetrievalOrderCompatibilityError from error


def _current_e1_e2(
    root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    with _capture_current_queries() as e1_queries:
        observation = runner._observe_retrieval_evaluation(  # pyright: ignore[reportPrivateUsage]
            root / _E1_MANIFEST,
            query_policy="current",
        )
    if observation.report.status != "passed":
        raise RetrievalOrderCompatibilityError
    e1_report = json.loads(render_retrieval_json_report(observation.report))
    e1_report.pop("duration_ms", None)
    with tempfile.TemporaryDirectory(
        prefix="mke-compatibility-numeric-"
    ) as snapshot:
        protocol = numeric_comparison.load_archived_numeric_protocol(
            root / _NUMERIC_PROTOCOL,
            snapshot_root=Path(snapshot),
        )
        with _capture_current_queries() as e2_queries:
            numeric_report = numeric_comparison._evaluate_numeric_protocol(  # pyright: ignore[reportPrivateUsage]
                protocol
            )
    if numeric_report.integrity_status != "passed":
        raise RetrievalOrderCompatibilityError
    numeric_payload = json.loads(
        numeric_comparison.render_numeric_comparison_json(numeric_report)
    )
    numeric_payload.pop("duration_ms", None)
    return (
        {
            "queries": _ordered_query_records(e1_queries),
            "semantic_report": e1_report,
        },
        {
            "queries": _ordered_query_records(e2_queries),
            "semantic_report": numeric_payload,
        },
    )


@contextmanager
def _capture_current_queries() -> Generator[
    dict[tuple[str, str], dict[str, object]], None, None
]:
    captured: dict[tuple[str, str], dict[str, object]] = {}
    original = runner._search_locators  # pyright: ignore[reportPrivateUsage]

    def capture(
        engine: KnowledgeEngine,
        query: EvaluationQuery,
        source_documents: dict[str, str],
    ) -> tuple[StableLocator, ...]:
        query_text = query.text
        query_id = query.query_id
        results = engine.search(query_text, limit=5)
        store = engine._store  # pyright: ignore[reportPrivateUsage]
        policy = store._query_policy  # pyright: ignore[reportPrivateUsage]
        compiled = compile_fts5_query(query_text, policy=policy)
        stable_projections: list[list[object]] = []
        score_hex: list[str] = []
        if compiled:
            all_results = {item.evidence_id: item for item in results}
            profile = store.observe_fts5_rank(compiled)
            for item in profile.rank_order:
                if item.evidence_id not in all_results:
                    continue
                result = all_results[item.evidence_id]
                stable_projections.append(
                    [
                        source_documents[result.source_id],
                        result.locator_kind,
                        result.locator_start,
                        result.locator_end,
                    ]
                )
                score_hex.append(item.rank_score.hex())
        record: dict[str, object] = {
            "policy": policy,
            "query_id": query_id,
            "stable_projections": stable_projections,
            "score_hex": score_hex,
            "tie_groups": _tie_groups(stable_projections, score_hex),
        }
        key = (policy, query_id)
        if key in captured and captured[key] != record:
            raise RetrievalOrderCompatibilityError
        captured[key] = record
        return tuple(
            runner._stable_locator(  # pyright: ignore[reportPrivateUsage]
                item, source_documents
            )
            for item in results
        )

    runner._search_locators = capture  # type: ignore[assignment]  # pyright: ignore[reportPrivateUsage]
    try:
        yield captured
    finally:
        runner._search_locators = original  # pyright: ignore[reportPrivateUsage]


def _e1_e2_family(
    *,
    family: Literal["e1_baseline", "e2_numeric"],
    capability: HistoricalReplayCapability,
    historical_payload: dict[str, object] | None,
    current_payload: dict[str, object],
    current_source: dict[str, object],
    root: Path,
) -> dict[str, object]:
    if family == "e1_baseline":
        _validate_archived_e1(root)
    else:
        _validate_archived_e2(root)
    if historical_payload is None:
        before_queries = _archived_order_queries(family, root)
        authority: TieGroupAuthority = "no_ordered_delta_authority"
        archived = _load_object(root / _HISTORICAL_INPUTS[family][0])
        historical_report = (
            archived
            if family == "e1_baseline"
            else archived["comparison"]
        )
    else:
        child_family_payload = _object(
            _object(historical_payload["families"])[family]
        )
        family_payload = _bind_historical_family(
            family,
            child_family_payload,
            root,
        )
        before_queries = cast(
            list[dict[str, object]], family_payload["queries"]
        )
        authority = "deterministic_historical_subprocess_replay"
        historical_report = family_payload["semantic_report"]
    differential = compare_ordered_queries(
        before_queries,
        cast(list[dict[str, object]], current_payload["queries"]),
        tie_group_authority=authority,
    )
    metric_delta, gate_delta, verdict_delta = _semantic_deltas(
        family,
        _object(historical_report),
        _object(current_payload["semantic_report"]),
    )
    if metric_delta or gate_delta or verdict_delta:
        raise RetrievalOrderCompatibilityError
    return _family_result(
        family=family,
        root=root,
        current_source=current_source,
        runtime_profile=capability.runtime_profile,
        differential=differential,
        metric_delta=metric_delta,
        gate_delta=gate_delta,
        verdict_delta=verdict_delta,
    )


def _archived_order_queries(
    family: Literal["e1_baseline", "e2_numeric"],
    root: Path,
) -> list[dict[str, object]]:
    artifact = _load_object(root / _HISTORICAL_INPUTS[family][0])
    if family == "e1_baseline":
        return _archived_result_records(
            cast(list[dict[str, object]], artifact["results"]),
            policy="current",
            string_locators=True,
        )
    comparison = _object(artifact["comparison"])
    records: list[dict[str, object]] = []
    for partition in ("development", "holdout", "e1"):
        partition_record = _object(comparison[partition])
        for arm, policy in (
            ("current", "current"),
            ("candidate", "numeric-grouping-v1"),
        ):
            report = _object(partition_record[arm])
            records.extend(
                _archived_result_records(
                    cast(
                        list[dict[str, object]],
                        report["results"],
                    ),
                    policy=policy,
                    string_locators=False,
                )
            )
    return sorted(records, key=_query_key)


def _archived_result_records(
    results: list[dict[str, object]],
    *,
    policy: str,
    string_locators: bool,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for result in results:
        raw_locators = cast(list[object], result["retrieved_locators"])
        projections = [
            (
                _parse_stable_locator(cast(str, locator))
                if string_locators
                else _locator_projection(_object(locator))
            )
            for locator in raw_locators
        ]
        records.append(
            {
                "policy": policy,
                "query_id": result["query_id"],
                "stable_projections": projections,
                "tie_groups": [],
            }
        )
    return records


def _parse_stable_locator(locator: str) -> list[object]:
    try:
        document_id, locator_kind, locator_range = locator.rsplit(":", 2)
        start, end = locator_range.split("..", 1)
        return [document_id, locator_kind, int(start), int(end)]
    except (ValueError, TypeError) as error:
        raise RetrievalOrderCompatibilityError from error


def _current_chinese_artifact(
    root: Path, workspace: Path
) -> dict[str, object]:
    protocol = root / _HISTORICAL_INPUTS["e3a_chinese"][1]
    observed = workspace / "chinese-observed.json"
    observed.write_text(
        render_chinese_retrieval_json(
            run_chinese_retrieval_evaluation(protocol)
        ),
        encoding="utf-8",
    )
    artifact = workspace / "chinese-artifact.json"
    record_chinese_artifact(
        observed_path=observed,
        artifact_path=artifact,
        protocol_path=protocol,
        repository_root=root,
    )
    return _load_object(artifact)


def _current_cjk_artifact(
    root: Path, workspace: Path
) -> dict[str, object]:
    protocol = root / _HISTORICAL_INPUTS["e3b_cjk_lexical"][1]
    observed = workspace / "cjk-observed.json"
    observed.write_text(
        render_cjk_lexical_comparison_json(
            run_cjk_lexical_comparison(protocol)
        ),
        encoding="utf-8",
    )
    artifact = workspace / "cjk-artifact.json"
    record_cjk_lexical_artifact(
        observed_path=observed,
        artifact_path=artifact,
        protocol_path=protocol,
        repository_root=root,
    )
    return _load_object(artifact)


def _e3a_family(
    *,
    current: dict[str, object],
    current_source: dict[str, object],
    root: Path,
) -> dict[str, object]:
    historical = _load_object(root / _HISTORICAL_INPUTS["e3a_chinese"][0])
    _validate_archived_e3a(historical, root)
    differential = compare_ordered_queries(
        _chinese_query_records(historical),
        _chinese_query_records(current),
        tie_group_authority="direct_recorded_score",
    )
    metric_delta = int(historical["metrics"] != current["metrics"])
    gate_delta = int(
        historical["e3b_evidence"] != current["e3b_evidence"]
    )
    verdict_delta = int(
        historical["e3b_decision"] != current["e3b_decision"]
    )
    if metric_delta or gate_delta or verdict_delta:
        raise RetrievalOrderCompatibilityError
    return _family_result(
        family="e3a_chinese",
        root=root,
        current_source=current_source,
        runtime_profile=_object(current["environment"]),
        differential=differential,
        metric_delta=metric_delta,
        gate_delta=gate_delta,
        verdict_delta=verdict_delta,
    )


def _e3b_family(
    *,
    current: dict[str, object],
    current_source: dict[str, object],
    root: Path,
) -> dict[str, object]:
    historical = _load_object(
        root / _HISTORICAL_INPUTS["e3b_cjk_lexical"][0]
    )
    _validate_archived_e3b(historical, root)
    historical_comparison = _object(historical["comparison"])
    current_comparison = _object(current["comparison"])
    differential = compare_ordered_queries(
        _cjk_query_records(historical_comparison),
        _cjk_query_records(current_comparison),
        tie_group_authority="direct_recorded_overlap",
    )
    metric_delta = int(
        historical_comparison.get("metrics")
        != current_comparison.get("metrics")
    )
    gate_delta = int(
        historical_comparison.get("gates")
        != current_comparison.get("gates")
    )
    verdict_delta = int(
        historical_comparison.get("candidate_status")
        != current_comparison.get("candidate_status")
    )
    if metric_delta or gate_delta or verdict_delta:
        raise RetrievalOrderCompatibilityError
    return _family_result(
        family="e3b_cjk_lexical",
        root=root,
        current_source=current_source,
        runtime_profile="evaluation_only_revision_1",
        differential=differential,
        metric_delta=metric_delta,
        gate_delta=gate_delta,
        verdict_delta=verdict_delta,
    )


def _e3c_family(
    *,
    current_source: dict[str, object],
    root: Path,
) -> dict[str, object]:
    artifact_path, protocol_path = _HISTORICAL_INPUTS["e3c_dense"]
    artifact = _load_object(root / artifact_path)
    validate_dense_comparison_artifact(
        artifact,
        protocol_path=root / protocol_path,
        repository_root=root,
    )
    queries = _dense_query_records(artifact)
    return _identity_family_result(
        family="e3c_dense",
        root=root,
        current_source=current_source,
        queries=queries,
        runtime_profile=_object(artifact["current_runtime"]),
    )


def _e3d_family(
    *,
    current_source: dict[str, object],
    root: Path,
) -> dict[str, object]:
    artifact_path, protocol_path = _HISTORICAL_INPUTS["e3d_hybrid_rrf"]
    validate_hybrid_rrf_artifact(
        artifact_path=root / artifact_path,
        protocol_path=root / protocol_path,
        dense_artifact_path=root / _HISTORICAL_INPUTS["e3c_dense"][0],
        repository_root=root,
    )
    artifact = _load_object(root / artifact_path)
    return _identity_family_result(
        family="e3d_hybrid_rrf",
        root=root,
        current_source=current_source,
        queries=_rrf_query_records(artifact),
        runtime_profile="model_free_derived_replay",
    )


def _e3e_family(
    *,
    current_source: dict[str, object],
    root: Path,
) -> dict[str, object]:
    artifact_path, protocol_path = _HISTORICAL_INPUTS[
        "e3e_relevance_gate"
    ]
    validate_relevance_gate_artifact(
        artifact_path=root / artifact_path,
        protocol_path=root / protocol_path,
        repository_root=root,
    )
    artifact = _load_object(root / artifact_path)
    return _identity_family_result(
        family="e3e_relevance_gate",
        root=root,
        current_source=current_source,
        queries=_relevance_query_records(artifact),
        runtime_profile="model_free_derived_replay",
    )


def _identity_family_result(
    *,
    family: str,
    root: Path,
    current_source: dict[str, object],
    queries: list[dict[str, object]],
    runtime_profile: object,
) -> dict[str, object]:
    differential = compare_ordered_queries(
        queries,
        queries,
        tie_group_authority="derived_from_recorded_parent",
    )
    return _family_result(
        family=family,
        root=root,
        current_source=current_source,
        runtime_profile=runtime_profile,
        differential=differential,
        metric_delta=0,
        gate_delta=0,
        verdict_delta=0,
    )


def _family_result(
    *,
    family: str,
    root: Path,
    current_source: dict[str, object],
    runtime_profile: object,
    differential: dict[str, object],
    metric_delta: int,
    gate_delta: int,
    verdict_delta: int,
) -> dict[str, object]:
    artifact_path, protocol_path = _HISTORICAL_INPUTS[family]
    return {
        "family": family,
        "historical_input": {
            "artifact": _file_identity(root, artifact_path),
            "protocol": _file_identity(root, protocol_path),
        },
        "archived_self_consistency_status": "passed",
        "current_source_identity": current_source["sha256"],
        "runtime_profile": runtime_profile,
        **differential,
        "metric_delta": metric_delta,
        "gate_delta": gate_delta,
        "verdict_delta": verdict_delta,
        "status": "passed",
    }


def _semantic_deltas(
    family: str,
    historical: dict[str, object],
    current: dict[str, object],
) -> tuple[int, int, int]:
    if family == "e1_baseline":
        metric_delta = int(historical.get("metrics") != current.get("metrics"))
        gate_delta = 0
        verdict_delta = int(
            (
                historical.get("status"),
                historical.get("quality_status"),
            )
            != (current.get("status"), current.get("quality_status"))
        )
        return metric_delta, gate_delta, verdict_delta
    metric_delta = int(
        {
            key: _object(historical[key]).get("candidate")
            for key in ("development", "holdout", "e1")
        }
        != {
            key: _object(current[key]).get("candidate")
            for key in ("development", "holdout", "e1")
        }
    )
    gate_delta = int(historical.get("gates") != current.get("gates"))
    verdict_delta = int(
        (
            historical.get("integrity_status"),
            historical.get("candidate_status"),
        )
        != (
            current.get("integrity_status"),
            current.get("candidate_status"),
        )
    )
    return metric_delta, gate_delta, verdict_delta


def _chinese_query_records(
    artifact: dict[str, object],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    observations = cast(
        list[dict[str, object]], artifact["fts5_rank_observations"]
    )
    for item in observations:
        pairs = cast(list[dict[str, object]], item["score_pairs"])
        projections = [
            _locator_projection(_object(pair["locator"])) for pair in pairs
        ]
        scores = [cast(str, pair["rank_score_hex"]) for pair in pairs]
        result.append(
            {
                "policy": "current",
                "query_id": item["query_id"],
                "stable_projections": projections,
                "score_hex": scores,
                "tie_groups": _tie_groups(projections, scores),
            }
        )
    return result


def _cjk_query_records(
    comparison: dict[str, object],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    observations = cast(
        list[dict[str, object]], comparison["query_observations"]
    )
    for item in observations:
        proofs = cast(
            list[dict[str, object]], item["candidate_result_proofs"]
        )
        projections = [
            _locator_projection(_object(proof["locator"]))
            for proof in proofs
        ]
        scores = [
            (
                f"{proof['overlap_count']}:"
                f"{float(cast(float, proof['overlap_ratio'])).hex()}"
            )
            for proof in proofs
        ]
        result.append(
            {
                "policy": "cjk-trigram-overlap-v1",
                "query_id": item["query_id"],
                "stable_projections": projections,
                "score_hex": scores,
                "tie_groups": _tie_groups(projections, scores),
            }
        )
    return result


def _dense_query_records(
    artifact: dict[str, object],
) -> list[dict[str, object]]:
    observations = cast(
        list[dict[str, object]],
        _object(artifact["development_candidate"])["observations"],
    )
    return [
        _ranked_result_record(
            policy="qwen3-embedding-0.6b-exact-v1",
            query_id=cast(str, observation["query_id"]),
            results=cast(list[dict[str, object]], observation["results"]),
            locator_key="locator",
            score_key="portable_score",
        )
        for observation in observations
    ]


def _rrf_query_records(
    artifact: dict[str, object],
) -> list[dict[str, object]]:
    results = cast(
        list[dict[str, object]], _object(artifact["development"])["results"]
    )
    return [
        _ranked_result_record(
            policy="cjk-active-scan-qwen3-rrf-v1",
            query_id=cast(str, item["query_id"]),
            results=cast(list[dict[str, object]], item["fused_results"]),
            locator_key=None,
            score_key="portable_score",
        )
        for item in results
    ]


def _relevance_query_records(
    artifact: dict[str, object],
) -> list[dict[str, object]]:
    results = cast(
        list[dict[str, object]], _object(artifact["holdout"])["results"]
    )
    return [
        _ranked_result_record(
            policy="cjk-relevance-gate-reranker-v1",
            query_id=cast(str, item["query_id"]),
            results=cast(list[dict[str, object]], item["allowed_results"]),
            locator_key=None,
            score_key="rerank_score",
        )
        for item in results
    ]


def _ranked_result_record(
    *,
    policy: str,
    query_id: str,
    results: list[dict[str, object]],
    locator_key: str | None,
    score_key: str,
) -> dict[str, object]:
    projections = [
        (
            _locator_projection(_object(item[locator_key]))
            if locator_key is not None
            else [
                item["document_id"],
                item["locator_kind"],
                item["locator_start"],
                item["locator_end"],
            ]
        )
        for item in results
    ]
    scores = [str(item.get(score_key, "not_recorded")) for item in results]
    return {
        "policy": policy,
        "query_id": query_id,
        "stable_projections": projections,
        "score_hex": scores,
        "tie_groups": _tie_groups(projections, scores),
    }


def _locator_projection(locator: dict[str, object]) -> list[object]:
    return [
        locator["document_id"],
        locator["locator_kind"],
        locator["locator_start"],
        locator["locator_end"],
    ]


def _query_key(item: dict[str, object]) -> tuple[str, str]:
    policy = item.get("policy")
    query_id = item.get("query_id")
    if not isinstance(policy, str) or not isinstance(query_id, str):
        raise RetrievalOrderCompatibilityError
    return policy, query_id


def _projection_order(
    item: dict[str, object],
) -> list[tuple[object, ...]]:
    value = item.get("stable_projections")
    if not isinstance(value, list):
        raise RetrievalOrderCompatibilityError
    return [
        tuple(cast(list[object], projection))
        for projection in cast(list[object], value)
        if isinstance(projection, list)
    ]


def _score_map(
    item: dict[str, object],
) -> dict[tuple[object, ...], str]:
    order = _projection_order(item)
    raw_scores = item.get("score_hex")
    if not isinstance(raw_scores, list):
        raise RetrievalOrderCompatibilityError
    scores = cast(list[object], raw_scores)
    if len(scores) != len(order) or not all(
        isinstance(score, str) for score in scores
    ):
        raise RetrievalOrderCompatibilityError
    return dict(zip(order, cast(list[str], scores), strict=True))


def _query_tie_groups(
    item: dict[str, object],
) -> list[dict[str, object]]:
    value = item.get("tie_groups")
    if not isinstance(value, list):
        raise RetrievalOrderCompatibilityError
    return cast(list[dict[str, object]], value)


def _tie_groups(
    projections: list[list[object]],
    scores: list[str],
) -> list[dict[str, object]]:
    grouped: dict[str, list[list[object]]] = {}
    for projection, score in zip(projections, scores, strict=True):
        grouped.setdefault(score, []).append(projection)
    return [
        {
            "score_hex": score,
            "stable_projections": grouped[score],
        }
        for score in sorted(grouped)
        if len(grouped[score]) > 1
    ]


def _ordered_query_records(
    records: dict[tuple[str, str], dict[str, object]],
) -> list[dict[str, object]]:
    return [records[key] for key in sorted(records)]


def _current_source_identity(root: Path) -> dict[str, object]:
    paths = tuple(
        path.relative_to(root).as_posix()
        for path in sorted((root / "src/mke").rglob("*.py"))
        if path.is_file()
    )
    return build_source_identity(root, paths)


def _file_identity(root: Path, path: Path) -> dict[str, object]:
    absolute = root / path
    return {
        "path": path.as_posix(),
        "sha256": _sha256(absolute),
    }


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _capability(
    *,
    status: Literal[
        "deterministic_historical_subprocess_replay",
        "no_ordered_delta_authority",
    ],
    first: str,
    second: str,
    origins: bool,
    inputs: bool,
) -> HistoricalReplayCapability:
    return HistoricalReplayCapability(
        status=status,
        source_commit=_SOURCE_COMMIT,
        source_tree=_SOURCE_TREE,
        source_identity=_SOURCE_IDENTITY,
        recorded_blob_count=107,
        runtime_profile=dict(_RUNTIME_PROFILE),
        bootstrap_sha256=hashlib.sha256(
            _HISTORICAL_BOOTSTRAP.encode()
        ).hexdigest(),
        child_argv=("python", "-B", "-P", "-c", "<bootstrap>"),
        checkout_external_cwd=True,
        python_no_user_site=True,
        inherited_python_path_cleared=True,
        inherited_python_home_cleared=True,
        module_origins_valid=origins,
        input_identities_valid=inputs,
        first_stdout=first,
        second_stdout=second,
    )


def _validate_materialization_path(
    relative: str,
    *,
    source_root: Path,
    scratch_root: Path,
) -> Path:
    path = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or relative in {".", ".."}
        or any(component in {"", ".", ".."} for component in relative.split("/"))
        or path.is_absolute()
        or relative != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
        or (path.parts and path.parts[0].endswith(":"))
    ):
        raise RetrievalOrderCompatibilityError
    source = source_root / Path(*path.parts)
    target = scratch_root / Path(*path.parts)
    _require_lexical_containment(
        source,
        root=source_root,
        require_existing=False,
    )
    _require_lexical_containment(
        target,
        root=scratch_root,
        require_existing=False,
    )
    return Path(*path.parts)


def _require_lexical_containment(
    path: Path,
    *,
    root: Path,
    require_existing: bool,
) -> None:
    lexical_root = root.absolute()
    lexical = path.absolute()
    try:
        relative = lexical.relative_to(lexical_root)
    except ValueError as error:
        raise RetrievalOrderCompatibilityError from error
    current = lexical_root
    if current.is_symlink():
        raise RetrievalOrderCompatibilityError
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise RetrievalOrderCompatibilityError
    if require_existing and not lexical.is_file():
        raise RetrievalOrderCompatibilityError


def _manifest_input_paths(
    root: Path,
    destination: Path,
) -> tuple[Path, ...]:
    raw_paths: set[str] = {
        _E1_MANIFEST.as_posix(),
        _NUMERIC_PROTOCOL.as_posix(),
    }
    for manifest_path in (
        root / _E1_MANIFEST,
        root / "tests/fixtures/retrieval-numeric-v1/development.json",
        root / "tests/fixtures/retrieval-numeric-v1/holdout.json",
    ):
        relative_manifest = manifest_path.relative_to(root)
        raw_paths.add(relative_manifest.as_posix())
        manifest = _load_object(manifest_path)
        for raw_document in cast(
            list[dict[str, object]],
            manifest["documents"],
        ):
            primary = _object(raw_document["primary_file"])
            primary_path = cast(str, primary["path"])
            _validate_materialization_path(
                primary_path,
                source_root=root / relative_manifest.parent,
                scratch_root=destination / relative_manifest.parent,
            )
            raw_paths.add(
                (relative_manifest.parent / primary_path).as_posix()
            )
            for raw_support in cast(
                list[dict[str, object]],
                raw_document["supporting_files"],
            ):
                support_path = cast(
                    str,
                    _object(raw_support)["path"],
                )
                _validate_materialization_path(
                    support_path,
                    source_root=root / relative_manifest.parent,
                    scratch_root=destination / relative_manifest.parent,
                )
                raw_paths.add(
                    (relative_manifest.parent / support_path).as_posix()
                )
    protocol = _load_object(root / _NUMERIC_PROTOCOL)
    for record in cast(
        dict[str, dict[str, object]],
        protocol["manifests"],
    ).values():
        manifest_path = cast(str, record["path"])
        _validate_materialization_path(
            manifest_path,
            source_root=root / "tests/fixtures",
            scratch_root=destination / "tests/fixtures",
        )
        raw_paths.add(
            (Path("tests/fixtures") / manifest_path).as_posix()
        )
    raw_paths.update(("pyproject.toml", "uv.lock"))
    return tuple(Path(path) for path in sorted(raw_paths))


def _historical_materialization_plan(
    root: Path,
    destination: Path,
    source: dict[str, object],
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    source_paths: list[Path] = []
    for record in cast(list[dict[str, object]], source["files"]):
        relative = cast(str, record["path"])
        path = _validate_materialization_path(
            relative,
            source_root=root,
            scratch_root=destination,
        )
        if not relative.startswith("src/mke/") or not relative.endswith(".py"):
            raise RetrievalOrderCompatibilityError
        source_paths.append(path)
    if tuple(path.as_posix() for path in source_paths) != tuple(
        cast(str, record["path"])
        for record in cast(list[dict[str, object]], source["files"])
    ):
        raise RetrievalOrderCompatibilityError
    input_paths = _manifest_input_paths(root, destination)
    for relative in input_paths:
        _validate_materialization_path(
            relative.as_posix(),
            source_root=root,
            scratch_root=destination,
        )
        if relative not in {Path("pyproject.toml"), Path("uv.lock")}:
            _require_lexical_containment(
                root / relative,
                root=root,
                require_existing=True,
            )
    return tuple(source_paths), input_paths


def _materialize_historical_source(
    root: Path,
    destination: Path,
    source: dict[str, object],
    *,
    source_paths: tuple[Path, ...],
) -> None:
    tree = _git(root, "rev-parse", f"{_SOURCE_COMMIT}:src/mke").decode().strip()
    if tree != _SOURCE_TREE:
        raise ValueError
    files = cast(list[dict[str, object]], source["files"])
    for record, relative in zip(files, source_paths, strict=True):
        tree_relative = relative.as_posix().removeprefix("src/mke/")
        data = _git(root, "cat-file", "blob", f"{_SOURCE_TREE}:{tree_relative}")
        if (
            len(data) != record["bytes"]
            or hashlib.sha256(data).hexdigest() != record["sha256"]
        ):
            raise ValueError
        target = destination / relative
        _require_lexical_containment(
            target,
            root=destination,
            require_existing=False,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    materialized = sorted(
        path.relative_to(destination).as_posix()
        for path in (destination / "src/mke").rglob("*")
        if path.is_file()
    )
    if materialized != [cast(str, item["path"]) for item in files]:
        raise ValueError


def _materialize_historical_inputs(
    root: Path,
    destination: Path,
    *,
    relative_paths: tuple[Path, ...],
) -> list[dict[str, object]]:
    for path in ("pyproject.toml", "uv.lock"):
        data = _git(root, "cat-file", "blob", f"{_SOURCE_COMMIT}:{path}")
        target = destination / path
        _require_lexical_containment(
            target,
            root=destination,
            require_existing=False,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    identities: list[dict[str, object]] = []
    for relative in relative_paths:
        if relative in {Path("pyproject.toml"), Path("uv.lock")}:
            source = destination / relative
        else:
            source = root / relative
            target = destination / relative
            _require_lexical_containment(
                source,
                root=root,
                require_existing=True,
            )
            _require_lexical_containment(
                target,
                root=destination,
                require_existing=False,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            source = target
        data = source.read_bytes()
        identities.append(
            {
                "path": relative.as_posix(),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return identities


def _run_historical_child(
    *,
    repository: Path,
    child_cwd: Path,
    request: dict[str, object],
) -> str:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONHOME", "PYTHONPATH"}
    }
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONPATH"] = (repository / "src").as_posix()
    result = subprocess.run(
        (
            sys.executable,
            "-B",
            "-P",
            "-c",
            _HISTORICAL_BOOTSTRAP,
        ),
        cwd=child_cwd,
        env=environment,
        input=json.dumps(request, ensure_ascii=True),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or result.stderr != "":
        raise ValueError
    stdout = result.stdout
    if not stdout.endswith("\n") or "\n" in stdout[:-1]:
        raise ValueError
    _load_json_stdout(stdout)
    return stdout


def _git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ("git", *arguments),
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout


def _source(value: object) -> dict[str, object]:
    source = _object(value)
    return {
        "sha256": source["sha256"],
        "files": source["files"],
    }


def _load_object(path: Path) -> dict[str, object]:
    return _object(json.loads(path.read_text(encoding="utf-8")))


def _load_json_stdout(value: str) -> dict[str, object]:
    return _object(json.loads(value))


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError
    return cast(dict[str, object], value)


if __name__ == "__main__":
    raise SystemExit(main())
