from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import cast

from mke.evaluation.chinese_protocol import (
    ChineseRetrievalProtocol,
    load_chinese_retrieval_protocol,
)
from mke.evaluation.cjk_lexical_candidate import (
    CJK_LEXICAL_CANDIDATE,
)
from mke.evaluation.cjk_lexical_comparison import (
    COMPARISON_SCHEMA,
    cjk_lexical_comparison_payload,
    run_cjk_lexical_comparison,
)

ARTIFACT_SCHEMA = "mke.cjk_lexical_comparison_artifact.v1"
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "protocol",
    "fixtures",
    "qrel_adjudication",
    "candidate",
    "source",
    "comparison",
}
_SOURCE_PATHS = (
    "pyproject.toml",
    "uv.lock",
    "src/mke/adapters/sqlite/__init__.py",
    "src/mke/evaluation/chinese_protocol.py",
    "src/mke/evaluation/chinese_runner.py",
    "src/mke/evaluation/cjk_lexical_artifact.py",
    "src/mke/evaluation/cjk_lexical_candidate.py",
    "src/mke/evaluation/cjk_lexical_comparison.py",
    "src/mke/evaluation/graded_metrics.py",
    "src/mke/retrieval/query_policy.py",
)


class CjkLexicalArtifactValidationError(ValueError):
    """The CJK lexical comparison artifact or bound report is invalid."""

    def __init__(self) -> None:
        super().__init__("CJK lexical comparison artifact is invalid")


def record_cjk_lexical_artifact(
    *,
    observed_path: Path,
    artifact_path: Path,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    observed = _load_object(observed_path)
    protocol = load_chinese_retrieval_protocol(protocol_path)
    fresh = _fresh_comparison(protocol_path)
    _require_observed_matches_fresh(observed, fresh)
    artifact = _canonical_artifact(
        fresh,
        protocol=protocol,
        protocol_path=protocol_path,
        repository_root=repository_root.resolve(),
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = artifact_path.with_name(f".{artifact_path.name}.tmp")
    temporary.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(artifact_path)


def validate_cjk_lexical_artifact(
    *,
    artifact_path: Path,
    observed_path: Path,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    try:
        artifact = _load_object(artifact_path)
        _validate_artifact_schema(artifact)
        observed = _load_object(observed_path)
        protocol = load_chinese_retrieval_protocol(protocol_path)
        fresh = _fresh_comparison(protocol_path)
        _require_observed_matches_fresh(observed, fresh)
        expected = _canonical_artifact(
            fresh,
            protocol=protocol,
            protocol_path=protocol_path,
            repository_root=repository_root.resolve(),
        )
        if artifact != expected:
            raise CjkLexicalArtifactValidationError
    except CjkLexicalArtifactValidationError:
        raise
    except Exception as error:
        raise CjkLexicalArtifactValidationError from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mke.evaluation.cjk_lexical_artifact")
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate")
    validate.add_argument("--artifact", type=Path, required=True)
    validate.add_argument("--observed", type=Path, required=True)
    validate.add_argument("--protocol", type=Path, required=True)
    validate.add_argument("--repository", type=Path, required=True)
    record = subcommands.add_parser("record")
    record.add_argument("--artifact", type=Path, required=True)
    record.add_argument("--observed", type=Path, required=True)
    record.add_argument("--protocol", type=Path, required=True)
    record.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            validate_cjk_lexical_artifact(
                artifact_path=args.artifact,
                observed_path=args.observed,
                protocol_path=args.protocol,
                repository_root=args.repository,
            )
        else:
            record_cjk_lexical_artifact(
                artifact_path=args.artifact,
                observed_path=args.observed,
                protocol_path=args.protocol,
                repository_root=args.repository,
            )
    except CjkLexicalArtifactValidationError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


def _fresh_comparison(protocol_path: Path) -> dict[str, object]:
    report = run_cjk_lexical_comparison(protocol_path)
    if report.integrity_status != "passed":
        raise CjkLexicalArtifactValidationError
    return _json_normalized(
        cjk_lexical_comparison_payload(report, include_duration=False)
    )


def _require_observed_matches_fresh(
    observed: dict[str, object],
    fresh: dict[str, object],
) -> None:
    observed_canonical = dict(observed)
    observed_canonical.pop("duration_ms", None)
    observed_canonical = _json_normalized(observed_canonical)
    if observed_canonical != fresh:
        raise CjkLexicalArtifactValidationError


def _canonical_artifact(
    comparison: dict[str, object],
    *,
    protocol: ChineseRetrievalProtocol,
    protocol_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    return {
        "schema_version": ARTIFACT_SCHEMA,
        "protocol": {
            "id": protocol.protocol_id,
            "path": protocol_path.resolve().relative_to(repository_root).as_posix(),
            "sha256": _sha256(protocol_path),
        },
        "fixtures": [
            {
                "document_id": item.document_id,
                "split": item.split,
                "path": item.primary_file.path.as_posix(),
                "bytes": item.primary_file.bytes,
                "sha256": item.primary_file.sha256,
            }
            for item in protocol.documents
        ],
        "qrel_adjudication": {
            "path": protocol.qrel_adjudication.path.relative_to(
                protocol.root
            ).as_posix(),
            "sha256": protocol.qrel_adjudication.sha256,
            "review_status": protocol.qrel_adjudication.review_status,
            "reviewed_query_count": protocol.qrel_adjudication.reviewed_query_count,
            "query_page_judgment_count": (
                protocol.qrel_adjudication.query_page_judgment_count
            ),
        },
        "candidate": {
            "id": CJK_LEXICAL_CANDIDATE.candidate_id,
            "revision": CJK_LEXICAL_CANDIDATE.revision,
            "minimum_overlap_count": CJK_LEXICAL_CANDIDATE.minimum_overlap_count,
            "minimum_overlap_ratio": CJK_LEXICAL_CANDIDATE.minimum_overlap_ratio,
            "max_results": CJK_LEXICAL_CANDIDATE.max_results,
        },
        "source": _source_identity(repository_root),
        "comparison": comparison,
    }


def _validate_artifact_schema(artifact: dict[str, object]) -> None:
    if set(artifact) != _TOP_LEVEL_FIELDS:
        raise CjkLexicalArtifactValidationError
    if artifact["schema_version"] != ARTIFACT_SCHEMA:
        raise CjkLexicalArtifactValidationError
    candidate = _object(artifact["candidate"])
    revision = candidate.get("revision")
    if (
        candidate
        != {
            "id": CJK_LEXICAL_CANDIDATE.candidate_id,
            "revision": CJK_LEXICAL_CANDIDATE.revision,
            "minimum_overlap_count": CJK_LEXICAL_CANDIDATE.minimum_overlap_count,
            "minimum_overlap_ratio": CJK_LEXICAL_CANDIDATE.minimum_overlap_ratio,
            "max_results": CJK_LEXICAL_CANDIDATE.max_results,
        }
        or isinstance(revision, bool)
    ):
        raise CjkLexicalArtifactValidationError
    comparison = _object(artifact["comparison"])
    if comparison.get("schema_version") != COMPARISON_SCHEMA:
        raise CjkLexicalArtifactValidationError
    if "duration_ms" in comparison:
        raise CjkLexicalArtifactValidationError


def _source_identity(repository_root: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    for raw_path in _SOURCE_PATHS:
        path = repository_root / raw_path
        data = path.read_bytes()
        files.append(
            {
                "path": raw_path,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return {
        "sha256": _digest(files),
        "files": files,
    }


def _load_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise CjkLexicalArtifactValidationError from error
    if not isinstance(payload, dict):
        raise CjkLexicalArtifactValidationError
    return cast(dict[str, object], payload)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CjkLexicalArtifactValidationError
    return cast(dict[str, object], value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _json_normalized(value: object) -> dict[str, object]:
    normalized = json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    if not isinstance(normalized, dict):
        raise CjkLexicalArtifactValidationError
    return cast(dict[str, object], normalized)


if __name__ == "__main__":
    raise SystemExit(main())
