import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.numeric_artifact import (
    NumericArtifactValidationError,
    record_numeric_artifact,
    validate_numeric_artifact,
)
from mke.evaluation.numeric_comparison import (
    render_numeric_comparison_json,
    run_numeric_comparison,
)

PROTOCOL = Path("tests/fixtures/retrieval-numeric-v1/protocol-lock.json")
REPOSITORY = Path(".")


def _observed(tmp_path: Path) -> Path:
    path = tmp_path / "observed.json"
    path.write_text(
        render_numeric_comparison_json(run_numeric_comparison(PROTOCOL)),
        encoding="utf-8",
    )
    return path


def _record(tmp_path: Path) -> tuple[Path, Path]:
    observed = _observed(tmp_path)
    artifact = tmp_path / "artifact.json"
    record_numeric_artifact(
        observed_path=observed,
        artifact_path=artifact,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )
    return artifact, observed


def _mutate_candidate(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["candidate"])["revision"] = 2


def _mutate_protocol(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["protocol"])["sha256"] = "0" * 64


def _mutate_manifest(payload: dict[str, object]) -> None:
    manifests = cast(dict[str, dict[str, object]], payload["manifests"])
    manifests["development"]["sha256"] = "0" * 64


def _mutate_fixture(payload: dict[str, object]) -> None:
    fixtures = cast(list[dict[str, object]], payload["fixtures"])
    fixtures[0]["bytes"] = 1


def _mutate_source(payload: dict[str, object]) -> None:
    source = cast(dict[str, object], payload["source"])
    files = cast(list[dict[str, object]], source["files"])
    files[0]["sha256"] = "0" * 64


def _mutate_compiled_query(payload: dict[str, object]) -> None:
    comparison = cast(dict[str, object], payload["comparison"])
    queries = cast(list[dict[str, object]], comparison["compiled_queries"])
    queries[0]["candidate"] = '"mutated"'


def _mutate_gate(payload: dict[str, object]) -> None:
    comparison = cast(dict[str, object], payload["comparison"])
    gates = cast(list[dict[str, object]], comparison["gates"])
    gates[0]["status"] = "failed"


def _mutate_verdict(payload: dict[str, object]) -> None:
    comparison = cast(dict[str, object], payload["comparison"])
    comparison["candidate_status"] = "rejected"


def test_recorded_artifact_validates_against_fresh_observation(
    tmp_path: Path,
) -> None:
    artifact, observed = _record(tmp_path)

    validate_numeric_artifact(
        artifact_path=artifact,
        observed_path=observed,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )

    payload = json.loads(artifact.read_text())
    assert payload["schema_version"] == (
        "mke.retrieval_numeric_comparison_artifact.v1"
    )
    assert payload["candidate"] == {
        "id": "numeric-grouping-v1",
        "revision": 1,
    }
    assert payload["comparison"]["integrity_status"] == "passed"
    assert payload["comparison"]["candidate_status"] == "passed"
    assert "duration_ms" not in payload["comparison"]
    assert payload["source"]["files"]
    assert payload["source"]["sha256"]


@pytest.mark.parametrize(
    "mutation",
    [
        _mutate_candidate,
        _mutate_protocol,
        _mutate_manifest,
        _mutate_fixture,
        _mutate_source,
        _mutate_compiled_query,
        _mutate_gate,
        _mutate_verdict,
    ],
)
def test_validator_rejects_mutated_bound_fields(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    artifact, observed = _record(tmp_path)
    payload = json.loads(artifact.read_text())
    mutation(payload)
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        NumericArtifactValidationError,
        match="numeric comparison artifact is invalid",
    ):
        validate_numeric_artifact(
            artifact_path=artifact,
            observed_path=observed,
            protocol_path=PROTOCOL,
            repository_root=REPOSITORY,
        )


def test_validator_rejects_source_content_change(tmp_path: Path) -> None:
    artifact, observed = _record(tmp_path)
    repository = tmp_path / "repository"
    shutil.copytree("src", repository / "src")
    copied_protocol = repository / PROTOCOL
    copied_protocol.parent.mkdir(parents=True)
    shutil.copy2(PROTOCOL, copied_protocol)
    fixtures_root = PROTOCOL.parent.parent
    for relative in (
        "retrieval-numeric-v1/development.json",
        "retrieval-numeric-v1/holdout.json",
        "retrieval-numeric-v1/development.pdf",
        "retrieval-numeric-v1/holdout.pdf",
        "retrieval-eval-v1.json",
        "eval/retrieval/usgs-volcano-hazards.pdf",
        "eval/retrieval/usgs-water-use-2005.pdf",
        "video/short-audio.mp4",
        "video/short-audio.mp4.mke-transcript.json",
    ):
        target = repository / fixtures_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixtures_root / relative, target)
    source = repository / "src/mke/retrieval/query_policy.py"
    source.write_text(source.read_text() + "\n# mutation\n")

    with pytest.raises(
        NumericArtifactValidationError,
        match="numeric comparison artifact is invalid",
    ):
        validate_numeric_artifact(
            artifact_path=artifact,
            observed_path=observed,
            protocol_path=copied_protocol,
            repository_root=repository,
        )


def test_self_consistent_rejected_candidate_artifact_is_valid(
    tmp_path: Path,
) -> None:
    observed = _observed(tmp_path)
    payload = json.loads(observed.read_text())
    payload["candidate_status"] = "rejected"
    payload["gates"][2].update(
        {
            "status": "failed",
            "observed": "requirement_not_met",
            "next_step": "do_not_promote",
        }
    )
    observed.write_text(json.dumps(payload), encoding="utf-8")
    artifact = tmp_path / "rejected.json"

    record_numeric_artifact(
        observed_path=observed,
        artifact_path=artifact,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )
    validate_numeric_artifact(
        artifact_path=artifact,
        observed_path=observed,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )


def test_validation_accepts_recorded_environment_from_another_ci_runtime(
    tmp_path: Path,
) -> None:
    artifact, observed = _record(tmp_path)
    payload = json.loads(artifact.read_text())
    payload["environment"]["python"] = "3.12.0"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    validate_numeric_artifact(
        artifact_path=artifact,
        observed_path=observed,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )


def test_validation_rejects_malformed_recorded_environment(
    tmp_path: Path,
) -> None:
    artifact, observed = _record(tmp_path)
    payload = json.loads(artifact.read_text())
    payload["environment"]["python"] = "unknown"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        NumericArtifactValidationError,
        match="numeric comparison artifact is invalid",
    ):
        validate_numeric_artifact(
            artifact_path=artifact,
            observed_path=observed,
            protocol_path=PROTOCOL,
            repository_root=REPOSITORY,
        )


def test_validation_does_not_require_feature_commit_ancestry(
    tmp_path: Path,
) -> None:
    artifact, observed = _record(tmp_path)
    repository = tmp_path / "source-repository"
    repository.mkdir()
    for relative in ("src", "tests/fixtures"):
        shutil.copytree(relative, repository / relative)
    (repository / "benchmarks/retrieval").mkdir(parents=True)
    shutil.copy2(artifact, repository / "benchmarks/retrieval/artifact.json")
    shutil.copy2(observed, repository / "observed.json")
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "add", "src", "tests", "benchmarks", "observed.json"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-qm", "squash landed"],
        cwd=repository,
        check=True,
    )
    clone = tmp_path / "depth-one"
    subprocess.run(
        ["git", "clone", "-q", "--depth=1", f"file://{repository}", str(clone)],
        check=True,
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mke.evaluation.numeric_artifact",
            "validate",
            "--artifact",
            "benchmarks/retrieval/artifact.json",
            "--observed",
            "observed.json",
            "--protocol",
            str(PROTOCOL),
            "--repository",
            ".",
        ],
        cwd=clone,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(clone / "src"), "PATH": str(Path(sys.executable).parent)},
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout == "numeric comparison artifact valid\n"
