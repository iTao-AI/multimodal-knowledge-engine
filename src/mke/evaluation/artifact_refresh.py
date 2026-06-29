from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType
from typing import Any, cast

from mke.evaluation.baseline import (
    refresh_retrieval_baseline_source,
    validate_retrieval_baseline,
)
from mke.evaluation.chinese_artifact import (
    record_chinese_artifact,
    validate_chinese_artifact,
)
from mke.evaluation.cjk_lexical_artifact import (
    record_cjk_lexical_artifact,
    validate_cjk_lexical_artifact,
)
from mke.evaluation.numeric_artifact import (
    record_numeric_artifact,
    validate_numeric_artifact,
)
from mke.evaluation.numeric_comparison import refresh_numeric_protocol_scope

TRANSACTION_NAME = ".mke-retrieval-artifact-refresh"
JOURNAL_SCHEMA = "mke.retrieval_artifact_refresh_journal.v1"
TARGETS = (
    "benchmarks/retrieval/retrieval-eval-v1-baseline.json",
    "tests/fixtures/retrieval-numeric-v1/protocol-lock.json",
    "benchmarks/retrieval/numeric-grouping-v1-comparison.json",
    "benchmarks/retrieval/retrieval-chinese-v1-baseline.json",
    "benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json",
)


class ArtifactRefreshError(RuntimeError):
    """The retrieval artifact transaction did not complete."""


def refresh_artifact_set(
    *,
    repository_root: Path,
    e1_observed_path: Path,
    e2_observed_path: Path,
    e3_observed_path: Path,
    e3b_observed_path: Path,
) -> dict[str, str]:
    root = repository_root.resolve()
    recover_artifact_refresh(root)
    transaction = root / TRANSACTION_NAME
    transaction.mkdir(parents=False, exist_ok=False)
    (transaction / "backups").mkdir()
    (transaction / "staged").mkdir()
    protocol_stage = (
        root
        / "tests/fixtures/retrieval-numeric-v1/"
        ".protocol-lock.artifact-refresh.json"
    )
    old_handlers = _install_signal_handlers()
    try:
        records = _backup_targets(root, transaction)
        _stage_targets(
            root=root,
            transaction=transaction,
            protocol_stage=protocol_stage,
            e1_observed_path=e1_observed_path,
            e2_observed_path=e2_observed_path,
            e3_observed_path=e3_observed_path,
            e3b_observed_path=e3b_observed_path,
        )
        _validate_staged(
            root=root,
            transaction=transaction,
            protocol_stage=protocol_stage,
            e1_observed_path=e1_observed_path,
            e2_observed_path=e2_observed_path,
            e3_observed_path=e3_observed_path,
            e3b_observed_path=e3b_observed_path,
        )
        _require_semantic_preservation(root, transaction)
        for index, record in enumerate(records):
            staged = transaction / f"staged/{index}"
            record["staged"] = f"staged/{index}"
            record["staged_sha256"] = _sha256(staged)
            record["replaced"] = False
        journal: dict[str, object] = {
            "schema_version": JOURNAL_SCHEMA,
            "targets": records,
        }
        _write_journal(transaction, journal)
        for index, record in enumerate(records):
            target = root / cast(str, record["path"])
            staged = transaction / f"staged/{index}"
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
            _fsync_directory(target.parent)
            record["replaced"] = True
            _write_journal(transaction, journal)
        _validate_checked_in(
            root=root,
            e1_observed_path=e1_observed_path,
            e2_observed_path=e2_observed_path,
            e3_observed_path=e3_observed_path,
            e3b_observed_path=e3b_observed_path,
        )
        manifest = {
            relative: _sha256(root / relative) for relative in TARGETS
        }
        shutil.rmtree(transaction)
        _fsync_directory(root)
        protocol_stage.unlink(missing_ok=True)
        return manifest
    except Exception as error:
        try:
            recover_artifact_refresh(root)
        except Exception as recovery_error:
            raise ArtifactRefreshError(
                "retrieval artifact transaction did not complete"
            ) from recovery_error
        raise ArtifactRefreshError(
            "retrieval artifact transaction did not complete"
        ) from error
    finally:
        protocol_stage.unlink(missing_ok=True)
        _restore_signal_handlers(old_handlers)


def recover_artifact_refresh(repository_root: Path) -> None:
    root = repository_root.resolve()
    transaction = root / TRANSACTION_NAME
    if not transaction.exists():
        return
    journal_path = transaction / "journal.json"
    if not journal_path.exists():
        shutil.rmtree(transaction)
        _fsync_directory(root)
        return
    try:
        journal = _load_object(journal_path)
        if journal.get("schema_version") != JOURNAL_SCHEMA:
            raise ArtifactRefreshError
        records = journal.get("targets")
        if not isinstance(records, list):
            raise ArtifactRefreshError
        for raw in cast(list[object], records):
            if not isinstance(raw, dict):
                raise ArtifactRefreshError
            record = cast(dict[str, object], raw)
            target = root / _safe_relative(record.get("path"))
            existed = record.get("existed")
            if type(existed) is not bool:
                raise ArtifactRefreshError
            if existed:
                backup = transaction / _safe_relative(record.get("backup"))
                expected = record.get("original_sha256")
                if (
                    not isinstance(expected, str)
                    or _sha256(backup) != expected
                ):
                    raise ArtifactRefreshError
                restore = target.with_name(f".{target.name}.restore")
                shutil.copyfile(backup, restore)
                _fsync_file(restore)
                os.replace(restore, target)
                _fsync_directory(target.parent)
                if _sha256(target) != expected:
                    raise ArtifactRefreshError
            else:
                target.unlink(missing_ok=True)
                _fsync_directory(target.parent)
        shutil.rmtree(transaction)
        _fsync_directory(root)
    except ArtifactRefreshError:
        raise
    except Exception as error:
        raise ArtifactRefreshError(
            "retrieval artifact recovery failed"
        ) from error


def _backup_targets(
    root: Path, transaction: Path
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for index, relative in enumerate(TARGETS):
        target = root / relative
        existed = target.exists()
        backup_relative = f"backups/{index}"
        record: dict[str, object] = {
            "path": relative,
            "existed": existed,
            "backup": backup_relative,
            "original_sha256": None,
        }
        if existed:
            backup = transaction / backup_relative
            shutil.copyfile(target, backup)
            _fsync_file(backup)
            record["original_sha256"] = _sha256(backup)
        records.append(record)
    _fsync_directory(transaction / "backups")
    return records


def _stage_targets(
    *,
    root: Path,
    transaction: Path,
    protocol_stage: Path,
    e1_observed_path: Path,
    e2_observed_path: Path,
    e3_observed_path: Path,
    e3b_observed_path: Path,
) -> None:
    del e1_observed_path
    e1_target = root / TARGETS[0]
    e1_stage = transaction / "staged/0"
    shutil.copyfile(e1_target, e1_stage)
    refresh_retrieval_baseline_source(
        artifact_path=e1_stage,
        manifest_path=root / "tests/fixtures/retrieval-eval-v1.json",
        repository_root=root,
        main_ref="main",
    )

    protocol_target = root / TARGETS[1]
    protocol_stage.write_bytes(protocol_target.read_bytes())
    refresh_numeric_protocol_scope(
        protocol_path=protocol_stage,
        repository_root=root,
    )
    shutil.copyfile(protocol_stage, transaction / "staged/1")

    record_numeric_artifact(
        observed_path=e2_observed_path,
        artifact_path=transaction / "staged/2",
        protocol_path=protocol_stage,
        repository_root=root,
    )
    record_chinese_artifact(
        observed_path=e3_observed_path,
        artifact_path=transaction / "staged/3",
        protocol_path=root
        / "tests/fixtures/retrieval-chinese-v1/protocol.json",
        repository_root=root,
    )
    record_cjk_lexical_artifact(
        observed_path=e3b_observed_path,
        artifact_path=transaction / "staged/4",
        protocol_path=root
        / "tests/fixtures/retrieval-chinese-v1/protocol.json",
        repository_root=root,
    )
    for index in range(5):
        _fsync_file(transaction / f"staged/{index}")
    _fsync_directory(transaction / "staged")


def _validate_staged(
    *,
    root: Path,
    transaction: Path,
    protocol_stage: Path,
    e1_observed_path: Path,
    e2_observed_path: Path,
    e3_observed_path: Path,
    e3b_observed_path: Path,
) -> None:
    _validate_e1_observation(
        e1_observed_path, transaction / "staged/0"
    )
    validate_retrieval_baseline(
        artifact_path=transaction / "staged/0",
        manifest_path=root / "tests/fixtures/retrieval-eval-v1.json",
        repository_root=root,
        main_ref="main",
    )
    validate_numeric_artifact(
        artifact_path=transaction / "staged/2",
        observed_path=e2_observed_path,
        protocol_path=protocol_stage,
        repository_root=root,
    )
    numeric_artifact = _load_object(transaction / "staged/2")
    protocol_identity = cast(
        dict[str, object], numeric_artifact["protocol"]
    )
    protocol_identity["path"] = TARGETS[1]
    (transaction / "staged/2").write_text(
        json.dumps(numeric_artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _fsync_file(transaction / "staged/2")
    validate_chinese_artifact(
        artifact_path=transaction / "staged/3",
        observed_path=e3_observed_path,
        protocol_path=root
        / "tests/fixtures/retrieval-chinese-v1/protocol.json",
        repository_root=root,
    )
    validate_cjk_lexical_artifact(
        artifact_path=transaction / "staged/4",
        observed_path=e3b_observed_path,
        protocol_path=root
        / "tests/fixtures/retrieval-chinese-v1/protocol.json",
        repository_root=root,
    )


def _validate_checked_in(
    *,
    root: Path,
    e1_observed_path: Path,
    e2_observed_path: Path,
    e3_observed_path: Path,
    e3b_observed_path: Path,
) -> None:
    _validate_e1_observation(e1_observed_path, root / TARGETS[0])
    validate_retrieval_baseline(
        artifact_path=root / TARGETS[0],
        manifest_path=root / "tests/fixtures/retrieval-eval-v1.json",
        repository_root=root,
        main_ref="main",
    )
    validate_numeric_artifact(
        artifact_path=root / TARGETS[2],
        observed_path=e2_observed_path,
        protocol_path=root / TARGETS[1],
        repository_root=root,
    )
    validate_chinese_artifact(
        artifact_path=root / TARGETS[3],
        observed_path=e3_observed_path,
        protocol_path=root
        / "tests/fixtures/retrieval-chinese-v1/protocol.json",
        repository_root=root,
    )
    validate_cjk_lexical_artifact(
        artifact_path=root / TARGETS[4],
        observed_path=e3b_observed_path,
        protocol_path=root
        / "tests/fixtures/retrieval-chinese-v1/protocol.json",
        repository_root=root,
    )


def _require_semantic_preservation(root: Path, transaction: Path) -> None:
    original_e1 = _load_object(root / TARGETS[0])
    staged_e1 = _load_object(transaction / "staged/0")
    original_code = cast(dict[str, object], original_e1["code"])
    staged_code = cast(dict[str, object], staged_e1["code"])
    original_e1["code"] = {
        **original_code,
        "evaluation_content_sha256": staged_code[
            "evaluation_content_sha256"
        ],
        "evaluation_content_files": staged_code["evaluation_content_files"],
    }
    if original_e1 != staged_e1:
        raise ArtifactRefreshError

    original_protocol = _load_object(root / TARGETS[1])
    staged_protocol = _load_object(transaction / "staged/1")
    original_protocol["scope_fence"] = staged_protocol["scope_fence"]
    if original_protocol != staged_protocol:
        raise ArtifactRefreshError

    original_e2 = _load_object(root / TARGETS[2])
    staged_e2 = _load_object(transaction / "staged/2")
    for key in (
        "schema_version",
        "manifests",
        "fixtures",
        "candidate",
        "environment",
        "comparison",
    ):
        if original_e2.get(key) != staged_e2.get(key):
            raise ArtifactRefreshError

    original_e3 = _load_object(root / TARGETS[3])
    staged_e3 = _load_object(transaction / "staged/3")
    original_e3["source_identity"] = staged_e3["source_identity"]
    if original_e3 != staged_e3:
        raise ArtifactRefreshError

    original_e3b = _load_object(root / TARGETS[4])
    staged_e3b = _load_object(transaction / "staged/4")
    original_e3b["source"] = staged_e3b["source"]
    if original_e3b != staged_e3b:
        raise ArtifactRefreshError


def _validate_e1_observation(observed_path: Path, artifact_path: Path) -> None:
    observed = _load_object(observed_path)
    artifact = _load_object(artifact_path)
    if (
        observed.get("schema_version") != "mke.retrieval_eval_report.v1"
        or observed.get("status") != "passed"
        or observed.get("quality_status") != "baseline_recorded"
        or observed.get("integrity_failures") != []
    ):
        raise ArtifactRefreshError
    for key in (
        "benchmark_scope",
        "quality_gate",
        "documents",
        "queries",
        "answerable",
        "unanswerable",
        "metrics",
        "category_counts",
    ):
        if observed.get(key) != artifact.get(key):
            raise ArtifactRefreshError
    observed_results = cast(list[dict[str, object]], observed.get("results"))
    artifact_results = cast(list[dict[str, object]], artifact.get("results"))
    normalized: list[dict[str, object]] = []
    for result in observed_results:
        item = dict(result)
        item["retrieved_locators"] = [
            (
                f"{locator['document_id']}:{locator['locator_kind']}:"
                f"{locator['locator_start']}..{locator['locator_end']}"
            )
            for locator in cast(
                list[dict[str, object]], result["retrieved_locators"]
            )
        ]
        normalized.append(item)
    if normalized != artifact_results:
        raise ArtifactRefreshError


def _write_journal(
    transaction: Path, journal: dict[str, object]
) -> None:
    temporary = transaction / ".journal.tmp"
    temporary.write_text(
        json.dumps(journal, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _fsync_file(temporary)
    os.replace(temporary, transaction / "journal.json")
    _fsync_directory(transaction)


def _install_signal_handlers() -> dict[int, Any]:
    handlers: dict[int, Any] = {}

    def interrupted(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        raise ArtifactRefreshError(
            "retrieval artifact transaction interrupted"
        )

    for signum in (signal.SIGINT, signal.SIGTERM):
        handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, interrupted)
    return handlers


def _restore_signal_handlers(handlers: dict[int, Any]) -> None:
    for signum, handler in handlers.items():
        signal.signal(signum, handler)


def _safe_relative(value: object) -> Path:
    if not isinstance(value, str):
        raise ArtifactRefreshError
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ArtifactRefreshError
    return path


def _load_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ArtifactRefreshError
    return cast(dict[str, object], payload)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "recover":
        parser = argparse.ArgumentParser(
            description="Recover an interrupted retrieval artifact refresh."
        )
        parser.add_argument("command")
        parser.add_argument("--repository", type=Path, default=Path("."))
        args = parser.parse_args(arguments)
        try:
            recover_artifact_refresh(args.repository)
        except ArtifactRefreshError:
            print(
                "problem=retrieval_artifact_refresh_failed "
                "cause=retrieval artifact transaction did not complete "
                "next_step=recover_checked_in_artifacts"
            )
            return 1
        print("retrieval artifact recovery complete")
        return 0
    parser = argparse.ArgumentParser(
        description="Refresh E1, E2, E3-A, and E3-B artifacts as a recoverable set."
    )
    parser.add_argument("--repository", type=Path, default=Path("."))
    parser.add_argument("--e1-observed", type=Path, required=True)
    parser.add_argument("--e2-observed", type=Path, required=True)
    parser.add_argument("--e3-observed", type=Path, required=True)
    parser.add_argument("--e3b-observed", type=Path, required=True)
    args = parser.parse_args(arguments)
    try:
        manifest = refresh_artifact_set(
            repository_root=args.repository,
            e1_observed_path=args.e1_observed,
            e2_observed_path=args.e2_observed,
            e3_observed_path=args.e3_observed,
            e3b_observed_path=args.e3b_observed,
        )
    except ArtifactRefreshError:
        print(
            "problem=retrieval_artifact_refresh_failed "
            "cause=retrieval artifact transaction did not complete "
            "next_step=recover_checked_in_artifacts"
        )
        return 1
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
