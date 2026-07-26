from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import NoReturn, cast

import pytest

import mke.evaluation.retrieval_order_workflow as workflow
from mke.evaluation.retrieval_order_artifact import (
    RetrievalOrderArtifactError,
    main,
    validate_retrieval_order_artifact,
)
from tests.evaluation.test_retrieval_order_workflow import (
    synthetic_fixture_payload,
    synthetic_partition_metadata,
)

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PROTOCOL = (
    ROOT / "tests/fixtures/retrieval-order-v1/protocol.json"
)
CANONICAL_HOLDOUT_FIXTURE = (
    ROOT / "tests/fixtures/retrieval-order-v1/holdout/cases.json"
)


@pytest.fixture(autouse=True)
def forbid_canonical_holdout_fixture_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_bytes

    def guarded(path: Path) -> bytes:
        if path.resolve() == CANONICAL_HOLDOUT_FIXTURE.resolve():
            raise AssertionError("canonical holdout fixture must stay unopened")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)


@pytest.fixture
def recorded_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, Path]:
    root, protocol = _synthetic_repository(tmp_path)
    output = root / "benchmarks/retrieval"
    freeze = output / "development-freeze.json"
    receipt = output / "holdout-receipt.json"
    artifact = output / "artifact.json"
    monkeypatch.chdir(root)
    workflow._run_development(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol,
        freeze_path=freeze,
        repository_root=root,
    )
    workflow._run_holdout(  # pyright: ignore[reportPrivateUsage]
        protocol_path=protocol,
        development_freeze_path=freeze,
        receipt_path=receipt,
        artifact_path=artifact,
        repository_root=root,
    )
    return root, protocol, artifact


def test_artifact_validate_is_pure_and_byte_preserving(
    recorded_artifact: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, protocol, artifact = recorded_artifact
    original = artifact.read_bytes()

    def observer(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("post-holdout validation must not observe")

    monkeypatch.setattr(
        workflow,
        "observe_retrieval_order_partition",
        observer,
    )

    assert main(
        [
            "validate",
            "--artifact",
            str(artifact),
            "--protocol",
            str(protocol),
            "--repository",
            str(root),
            "--json",
        ]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    assert artifact.read_bytes() == original


@pytest.mark.parametrize(
    "tamper",
    (
        "candidate_head",
        "receipt_digest",
        "holdout_delta",
        "runtime_profile",
        "case_projection",
    ),
)
def test_artifact_validate_rejects_cross_binding_tamper_without_observation(
    recorded_artifact: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    root, protocol, artifact_path = recorded_artifact
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if tamper == "candidate_head":
        artifact["candidate_seal"]["head"] = "0" * 40
    elif tamper == "receipt_digest":
        artifact["holdout_receipt"]["sha256"] = "0" * 64
    elif tamper == "holdout_delta":
        artifact["observation"]["candidate_membership_delta"] = 1
    elif tamper == "runtime_profile":
        artifact["observation"]["runtime_profile"]["sqlite"] = "0.0.0"
    else:
        artifact["observation"]["cases"][0][
            "reverse_stable_projections"
        ].reverse()

    def observer(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("post-holdout validation must not observe")

    monkeypatch.setattr(
        workflow,
        "observe_retrieval_order_partition",
        observer,
    )

    with pytest.raises(RetrievalOrderArtifactError):
        validate_retrieval_order_artifact(
            artifact,
            protocol_path=protocol,
            repository_root=root,
        )


def _synthetic_repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "synthetic-repository"
    fixture_root = root / "fixtures"
    fixture_root.mkdir(parents=True)
    payload = deepcopy(
        json.loads(CANONICAL_PROTOCOL.read_text(encoding="utf-8"))
    )
    partitions = cast(dict[str, object], payload["partitions"])
    for name in ("development", "holdout"):
        record = cast(dict[str, object], partitions[name])
        fixture = synthetic_fixture_payload(name)
        data = (
            json.dumps(
                fixture,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        destination = fixture_root / f"{name}.json"
        destination.write_bytes(data)
        record["path"] = destination.relative_to(root).as_posix()
        record["bytes"] = len(data)
        record["sha256"] = hashlib.sha256(data).hexdigest()
        record["cases"] = synthetic_partition_metadata(fixture)
    protocol = root / "protocol.json"
    protocol.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )
    commands = (
        ("git", "init", "-q"),
        ("git", "config", "user.email", "synthetic@example.invalid"),
        ("git", "config", "user.name", "Synthetic Authority"),
        ("git", "add", "protocol.json", "fixtures"),
        ("git", "commit", "-qm", "synthetic authority"),
    )
    for command in commands:
        subprocess.run(command, cwd=root, check=True)
    return root.resolve(), protocol.resolve()
