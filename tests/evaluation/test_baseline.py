import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.baseline import (
    BaselineValidationError,
    validate_retrieval_baseline,
)

ARTIFACT = Path("benchmarks/retrieval/retrieval-eval-v1-baseline.json")
MANIFEST = Path("tests/fixtures/retrieval-eval-v1.json")
REPOSITORY = Path(".")
EVALUATION_CONTENT_PATHS = (
    "src/mke/adapters/pdf/extractor.py",
    "src/mke/adapters/sqlite/__init__.py",
    "src/mke/adapters/video/transcript.py",
    "src/mke/application/__init__.py",
    "src/mke/cli.py",
    "src/mke/domain/__init__.py",
    "src/mke/evaluation/__init__.py",
    "src/mke/evaluation/manifest.py",
    "src/mke/evaluation/metrics.py",
    "src/mke/evaluation/report.py",
    "src/mke/evaluation/runner.py",
    "src/mke/runtime.py",
)


def _artifact_payload() -> dict[str, object]:
    return cast(dict[str, object], json.loads(ARTIFACT.read_text()))


def _write_artifact(tmp_path: Path, payload: dict[str, object]) -> Path:
    artifact = tmp_path / "baseline.json"
    artifact.write_text(json.dumps(payload))
    return artifact


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _add_durable_content_identity(
    payload: dict[str, object], repository: Path
) -> None:
    files = [
        {
            "path": relative_path,
            "bytes": (repository / relative_path).stat().st_size,
            "sha256": _sha256(repository / relative_path),
        }
        for relative_path in EVALUATION_CONTENT_PATHS
    ]
    encoded_files = json.dumps(
        files, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    code = cast(dict[str, object], payload["code"])
    code["evaluation_content_sha256"] = hashlib.sha256(encoded_files).hexdigest()
    code["evaluation_content_files"] = files


def _git(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def _validate(path: Path) -> None:
    validate_retrieval_baseline(
        artifact_path=path,
        manifest_path=MANIFEST,
        repository_root=REPOSITORY,
    )


def _wrong_manifest_checksum(payload: dict[str, object]) -> None:
    payload["manifest_sha256"] = "0" * 64


def _wrong_fixture_checksum(payload: dict[str, object]) -> None:
    fixtures = cast(list[dict[str, object]], payload["fixtures"])
    fixtures[0]["sha256"] = "0" * 64


def _wrong_evaluation_content_checksum(payload: dict[str, object]) -> None:
    code = cast(dict[str, object], payload["code"])
    code["evaluation_content_sha256"] = "0" * 64


def _wrong_evaluation_content_file_checksum(payload: dict[str, object]) -> None:
    code = cast(dict[str, object], payload["code"])
    files = cast(list[dict[str, object]], code["evaluation_content_files"])
    files[0]["sha256"] = "0" * 64


def _wrong_metric_count(metric: dict[str, object]) -> None:
    metric["count"] = 15


def _wrong_metric_sum(metric: dict[str, object]) -> None:
    metric["sum"] = 13.0


def _wrong_metric_value(metric: dict[str, object]) -> None:
    metric["value"] = 0.5


def _unknown_metric_field(metric: dict[str, object]) -> None:
    metric["unexpected"] = True


def _wrong_query_id(result: dict[str, object]) -> None:
    result["query_id"] = "wrong-query"


def _wrong_category(result: dict[str, object]) -> None:
    result["category"] = "out_of_corpus"


def _wrong_retrieved_count(result: dict[str, object]) -> None:
    result["retrieved_locator_count"] = 99


def _unknown_result_field(result: dict[str, object]) -> None:
    result["unexpected"] = True


def test_checked_in_canonical_baseline_is_self_consistent() -> None:
    _validate(ARTIFACT)


def test_validator_accepts_squash_landed_main_in_fresh_clone(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "--initial-branch=main")
    _git(source, "config", "user.name", "MKE Test")
    _git(source, "config", "user.email", "mke-test@example.invalid")
    (source / "README.md").write_text("base\n")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "base")

    payload = _artifact_payload()
    _add_durable_content_identity(payload, REPOSITORY)
    for relative_path in EVALUATION_CONTENT_PATHS:
        destination = source / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPOSITORY / relative_path, destination)
    fixture_root = source / "tests/fixtures"
    shutil.copytree(REPOSITORY / "tests/fixtures", fixture_root)
    artifact = source / ARTIFACT
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(payload))
    _git(
        source,
        "add",
        *EVALUATION_CONTENT_PATHS,
        "tests/fixtures",
        ARTIFACT.as_posix(),
    )
    _git(source, "commit", "-m", "squash landed retrieval baseline")

    fresh_clone = tmp_path / "fresh-clone"
    subprocess.run(
        [
            "git",
            "clone",
            "--branch",
            "main",
            "--depth",
            "1",
            source.resolve().as_uri(),
            str(fresh_clone),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    code = cast(dict[str, object], payload["code"])
    historical_commit = cast(str, code["evaluation_commit"])
    assert subprocess.run(
        ["git", "cat-file", "-e", f"{historical_commit}^{{commit}}"],
        cwd=fresh_clone,
        capture_output=True,
        text=True,
    ).returncode != 0

    validate_retrieval_baseline(
        artifact_path=fresh_clone / ARTIFACT,
        manifest_path=fresh_clone / MANIFEST,
        repository_root=fresh_clone,
    )


def test_validator_rejects_wrong_main_merge_base(tmp_path: Path) -> None:
    payload = _artifact_payload()
    code = cast(dict[str, object], payload["code"])
    code["main_merge_base"] = code["implementation_start"]

    with pytest.raises(
        BaselineValidationError,
        match="baseline code historical metadata is invalid",
    ):
        _validate(_write_artifact(tmp_path, payload))


def test_validator_rejects_wrong_evaluation_commit_identity(tmp_path: Path) -> None:
    payload = _artifact_payload()
    code = cast(dict[str, object], payload["code"])
    code["evaluation_commit"] = code["main_merge_base"]

    with pytest.raises(
        BaselineValidationError,
        match="baseline code historical metadata is invalid",
    ):
        _validate(_write_artifact(tmp_path, payload))


def test_validator_rejects_malformed_environment(tmp_path: Path) -> None:
    payload = _artifact_payload()
    environment = cast(dict[str, object], payload["environment"])
    environment["python"] = "unknown"

    with pytest.raises(BaselineValidationError, match="baseline environment is invalid"):
        _validate(_write_artifact(tmp_path, payload))


def test_validator_rejects_unknown_top_level_fields(tmp_path: Path) -> None:
    payload = _artifact_payload()
    payload["unexpected"] = True

    with pytest.raises(
        BaselineValidationError, match="baseline artifact fields are invalid"
    ):
        _validate(_write_artifact(tmp_path, payload))


@pytest.mark.parametrize(
    ("mutation", "cause"),
    [
        (_wrong_manifest_checksum, "manifest checksum does not match"),
        (
            _wrong_fixture_checksum,
            "fixture provenance does not match manifest and files",
        ),
    ],
)
def test_validator_derives_manifest_and_fixture_provenance(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    cause: str,
) -> None:
    payload = _artifact_payload()
    mutation(payload)

    with pytest.raises(BaselineValidationError, match=cause):
        _validate(_write_artifact(tmp_path, payload))


@pytest.mark.parametrize(
    "mutation",
    [
        _wrong_evaluation_content_checksum,
        _wrong_evaluation_content_file_checksum,
    ],
)
def test_validator_derives_evaluation_content_identity(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    payload = _artifact_payload()
    mutation(payload)

    with pytest.raises(
        BaselineValidationError,
        match="baseline evaluation content identity is invalid",
    ):
        _validate(_write_artifact(tmp_path, payload))


@pytest.mark.parametrize(
    "mutation",
    [
        _wrong_metric_count,
        _wrong_metric_sum,
        _wrong_metric_value,
        _unknown_metric_field,
    ],
)
def test_validator_rejects_malformed_metrics(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    payload = _artifact_payload()
    metrics = cast(dict[str, dict[str, object]], payload["metrics"])
    mutation(metrics["locator_recall_at_1"])

    with pytest.raises(BaselineValidationError, match="baseline metrics are inconsistent"):
        _validate(_write_artifact(tmp_path, payload))


@pytest.mark.parametrize(
    "mutation",
    [
        _wrong_query_id,
        _wrong_category,
        _wrong_retrieved_count,
        _unknown_result_field,
    ],
)
def test_validator_rejects_malformed_results_or_query_identity(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    payload = _artifact_payload()
    results = cast(list[dict[str, object]], payload["results"])
    mutation(results[0])

    with pytest.raises(
        BaselineValidationError,
        match="baseline results do not match manifest query identity",
    ):
        _validate(_write_artifact(tmp_path, payload))


def test_validator_does_not_compare_current_scores_to_historical_baseline(
    tmp_path: Path,
) -> None:
    payload = _artifact_payload()
    results = cast(list[dict[str, object]], payload["results"])
    result = results[0]
    result.update(
        {
            "retrieved_locator_count": 0,
            "relevant_retrieved_at_1": 0,
            "relevant_retrieved_at_3": 0,
            "relevant_retrieved_at_5": 0,
            "first_relevant_rank": None,
            "ask_status": "insufficient_evidence",
            "retrieved_locators": [],
        }
    )
    metrics = cast(dict[str, dict[str, object]], payload["metrics"])
    metrics["locator_recall_at_1"].update({"value": 0.8125, "sum": 13.0})
    metrics["locator_recall_at_3"].update({"value": 0.875, "sum": 14.0})
    metrics["locator_recall_at_5"].update({"value": 0.875, "sum": 14.0})
    metrics["mrr_at_5"].update({"value": 0.875, "sum": 14.0})
    metrics["answerable_zero_hit_rate"].update({"value": 0.125, "sum": 2.0})
    payload["answerable_misses_at_5"] = [
        "volcano-answerable-01",
        "water-answerable-01",
    ]

    _validate(_write_artifact(tmp_path, payload))


def test_module_cli_redacts_malformed_locator_parse_error(tmp_path: Path) -> None:
    payload = _artifact_payload()
    results = cast(list[dict[str, object]], payload["results"])
    locators = cast(list[str], results[0]["retrieved_locators"])
    document_id, kind, _ = locators[0].split(":")
    locators[0] = f"{document_id}:{kind}:not-an-int..1"
    artifact = _write_artifact(tmp_path, payload)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mke.evaluation.baseline",
            "--artifact",
            str(artifact),
            "--manifest",
            str(MANIFEST),
            "--repository",
            str(REPOSITORY),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert completed.stdout == (
        "retrieval baseline artifact invalid: "
        "baseline results do not match manifest query identity\n"
    )
    assert completed.stderr == ""
