#!/usr/bin/env python3
"""Prove deterministic retrieval-order inputs with one explicit installed wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

_RECEIPT_FIELDS = {
    "schema_version",
    "repository",
    "source_commit",
    "package_name",
    "package_version",
    "wheel_filename",
    "wheel_bytes",
    "wheel_sha256",
    "requires_python",
    "consumer_proof_schema",
    "consumer_proof_status",
    "proof_input_wheel_sha256",
    "receipt_sha256",
}
_SHA256 = frozenset("0123456789abcdef")
_DIRTY_ENV = frozenset(
    {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
)


class ProofError(RuntimeError):
    def __init__(self, problem: str) -> None:
        super().__init__(problem)
        self.problem = problem


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class ProofInputs:
    interpreters: tuple[Path, Path]
    wheel: Path
    candidate_receipt: Path
    protocol: Path
    development_freeze: Path
    holdout_receipt: Path
    artifact: Path
    compatibility: Path
    timeout_seconds: float


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _SHA256 for character in value)
    )


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProofError("retrieval_order_proof_preflight_invalid")
    return cast(dict[str, object], value)


def _load(path: Path) -> dict[str, object]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ProofError(
                "retrieval_order_proof_preflight_invalid"
            )
        return _object(json.loads(path.read_text(encoding="utf-8")))
    except ProofError:
        raise
    except (OSError, json.JSONDecodeError) as error:
        raise ProofError(
            "retrieval_order_proof_preflight_invalid"
        ) from error


def _canonical_sha256(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_receipt(
    receipt: dict[str, object],
    *,
    wheel: Path,
) -> tuple[str, str]:
    if set(receipt) != _RECEIPT_FIELDS:
        raise ProofError("retrieval_order_shared_wheel_mismatch")
    retained_digest = receipt["receipt_sha256"]
    unsigned = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_sha256"
    }
    wheel_digest = _sha256(wheel)
    sibling_wheels = tuple(wheel.parent.glob("*.whl"))
    if (
        receipt["schema_version"]
        != "mke.candidate_artifact_receipt.v1"
        or receipt["repository"]
        != "iTao-AI/multimodal-knowledge-engine"
        or receipt["package_name"]
        != "multimodal-knowledge-engine"
        or receipt["consumer_proof_schema"]
        != "mke.consumer_source_pack_proof.v1"
        or receipt["consumer_proof_status"] != "passed"
        or not isinstance(receipt["source_commit"], str)
        or len(receipt["source_commit"]) != 40
        or not isinstance(receipt["package_version"], str)
        or receipt["wheel_filename"] != wheel.name
        or receipt["wheel_bytes"] != wheel.stat().st_size
        or receipt["wheel_sha256"] != wheel_digest
        or receipt["proof_input_wheel_sha256"] != wheel_digest
        or not _is_sha256(retained_digest)
        or retained_digest != _canonical_sha256(unsigned)
        or len(sibling_wheels) != 1
        or sibling_wheels[0].resolve() != wheel.resolve()
    ):
        raise ProofError("retrieval_order_shared_wheel_mismatch")
    return receipt["source_commit"], wheel_digest


def _identity_digest(value: object) -> str:
    identity = _object(value)
    digest = identity.get("sha256")
    if not _is_sha256(digest):
        raise ProofError("retrieval_order_proof_preflight_invalid")
    return cast(str, digest)


def _preflight(inputs: ProofInputs) -> tuple[str, str, str]:
    if inputs.wheel.is_symlink():
        raise ProofError("retrieval_order_shared_wheel_mismatch")
    try:
        wheel = inputs.wheel.resolve(strict=True)
    except OSError as error:
        raise ProofError("retrieval_order_shared_wheel_mismatch") from error
    if wheel.is_symlink() or not wheel.is_file():
        raise ProofError("retrieval_order_shared_wheel_mismatch")
    receipt = _load(inputs.candidate_receipt)
    candidate_head, wheel_digest = _validate_receipt(
        receipt,
        wheel=wheel,
    )
    protocol_digest = _sha256(inputs.protocol)
    development = _load(inputs.development_freeze)
    holdout = _load(inputs.holdout_receipt)
    artifact = _load(inputs.artifact)
    compatibility = _load(inputs.compatibility)
    candidate_seal = _object(artifact.get("candidate_seal"))
    authority = _object(compatibility.get("canonical_authority"))
    if (
        development.get("schema_version")
        != "mke.retrieval_order_development_freeze.v1"
        or holdout.get("schema_version")
        != "mke.retrieval_order_holdout_receipt.v1"
        or artifact.get("schema_version")
        != "mke.retrieval_order_artifact.v1"
        or compatibility.get("schema_version")
        != "mke.retrieval_order_compatibility.v1"
        or _identity_digest(development.get("protocol"))
        != protocol_digest
        or _identity_digest(holdout.get("protocol"))
        != protocol_digest
        or _identity_digest(artifact.get("protocol"))
        != protocol_digest
        or development.get("candidate_seal") != candidate_seal
        or holdout.get("candidate_seal") != candidate_seal
        or authority.get("candidate_seal") != candidate_seal
        or candidate_seal.get("head") != candidate_head
        or development.get("development_status") != "passed"
        or holdout.get("attempt_status") != "started"
        or artifact.get("development_status") != "passed"
        or artifact.get("holdout_status") != "observed"
        or artifact.get("integrity_status") != "passed"
        or artifact.get("runtime_promotion_status")
        != "not_evaluated"
        or _object(artifact.get("observation")).get(
            "observation_status"
        )
        != "passed"
        or compatibility.get("integrity_status") != "passed"
        or compatibility.get("compatibility_status") != "passed"
        or any(
            compatibility.get(field) != "passed"
            for field in (
                "historical_bytes_frozen",
                "archived_record_self_consistent",
                "current_runtime_replay_compatible",
                "revision_2_differential_valid",
            )
        )
        or _identity_digest(
            artifact.get("development_freeze")
        )
        != _sha256(inputs.development_freeze)
        or _identity_digest(artifact.get("holdout_receipt"))
        != _sha256(inputs.holdout_receipt)
        or _identity_digest(authority.get("development_freeze"))
        != _sha256(inputs.development_freeze)
        or _identity_digest(authority.get("holdout_receipt"))
        != _sha256(inputs.holdout_receipt)
        or _identity_digest(authority.get("retrieval_artifact"))
        != _sha256(inputs.artifact)
    ):
        raise ProofError("retrieval_order_proof_preflight_invalid")
    interpreters: list[Path] = []
    for supplied in inputs.interpreters:
        try:
            interpreter = supplied.resolve(strict=True)
        except OSError as error:
            raise ProofError(
                "retrieval_order_proof_preflight_invalid"
            ) from error
        if not interpreter.is_file() or supplied.is_symlink():
            raise ProofError(
                "retrieval_order_proof_preflight_invalid"
            )
        interpreters.append(interpreter)
    if interpreters[0] == interpreters[1]:
        raise ProofError("retrieval_order_proof_preflight_invalid")
    return candidate_head, wheel_digest, cast(
        str,
        receipt["package_version"],
    )


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: float,
) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ProofError(
            "retrieval_order_proof_preflight_invalid"
        ) from error
    return CommandResult(
        completed.returncode,
        completed.stdout,
        completed.stderr,
    )


def _installed_probe() -> str:
    return (
        "import importlib.metadata as m,json,mke;"
        "from mke.evaluation.retrieval_order_artifact "
        "import validate_retrieval_order_artifact as a;"
        "from mke.evaluation.retrieval_order_compatibility "
        "import validate_compatibility_artifact as c;"
        "from mke.retrieval.query_policy import QUERY_POLICY_REVISION as q;"
        "from mke.retrieval.strategy import "
        "get_retrieval_strategy_descriptor as g;"
        "print(json.dumps({"
        "'distribution_version':m.version('multimodal-knowledge-engine'),"
        "'module_file':mke.__file__,"
        "'strategy_revision':g('cjk-active-scan-overlap-v1').revision,"
        "'query_policy_revision':q,"
        "'artifact_validator':callable(a),"
        "'compatibility_validator':callable(c)"
        "},sort_keys=True,separators=(',',':')))"
    )


def _prove_interpreter(
    interpreter: Path,
    *,
    index: int,
    root: Path,
    wheel: Path,
    package_version: str,
    timeout_seconds: float,
) -> dict[str, object]:
    environment = root / f"venv-{index}"
    installed_python = environment / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in _DIRTY_ENV
    }
    commands = (
        (
            "uv",
            "venv",
            str(environment),
            "--python",
            str(interpreter),
            "--no-python-downloads",
        ),
        (
            "uv",
            "pip",
            "install",
            "--python",
            str(installed_python),
            str(wheel),
        ),
    )
    for command in commands:
        result = _run(
            command,
            cwd=root,
            env=clean_env,
            timeout_seconds=timeout_seconds,
        )
        if result.returncode != 0:
            raise ProofError(
                "retrieval_order_proof_preflight_invalid"
            )
    probe = _run(
        (
            str(installed_python),
            "-B",
            "-P",
            "-c",
            _installed_probe(),
        ),
        cwd=root,
        env=clean_env,
        timeout_seconds=timeout_seconds,
    )
    try:
        payload = _object(json.loads(probe.stdout))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProofError(
            "retrieval_order_proof_preflight_invalid"
        ) from error
    module_file = payload.get("module_file")
    if (
        probe.returncode != 0
        or probe.stderr
        or payload.get("distribution_version") != package_version
        or not isinstance(module_file, str)
        or not Path(module_file).resolve().is_relative_to(
            environment.resolve()
        )
        or payload.get("strategy_revision") != 2
        or payload.get("query_policy_revision") != 1
        or payload.get("artifact_validator") is not True
        or payload.get("compatibility_validator") is not True
    ):
        raise ProofError("retrieval_order_proof_preflight_invalid")
    return {
        "python": str(interpreter),
        "distribution_version": package_version,
        "strategy_revision": 2,
        "query_policy_revision": 1,
    }


def run_proof(inputs: ProofInputs) -> dict[str, object]:
    candidate_head, wheel_digest, package_version = _preflight(inputs)
    root = Path(tempfile.mkdtemp(prefix="mke-retrieval-order-proof-"))
    try:
        results = [
            _prove_interpreter(
                interpreter,
                index=index,
                root=root,
                wheel=inputs.wheel.resolve(),
                package_version=package_version,
                timeout_seconds=inputs.timeout_seconds,
            )
            for index, interpreter in enumerate(inputs.interpreters)
        ]
    finally:
        shutil.rmtree(root)
    return {
        "schema_version": (
            "mke.retrieval_order_installed_proof_result.v1"
        ),
        "status": "passed",
        "mode": "installed_proof",
        "authority_layer": "same_wheel_external_store",
        "canonical": True,
        "output_state": "not_applicable",
        "publication_outcome": "not_attempted",
        "problem": "none",
        "cause": "none",
        "next_step": "none",
        "first_failed_gate": "none",
        "stage_statuses": [
            {"name": "preflight", "status": "passed"},
            {"name": "installed_proof", "status": "passed"},
        ],
        "historical_revision": 1,
        "current_revision": 2,
        "candidate_seal": candidate_head,
        "wheel_sha256": wheel_digest,
        "interpreters": results,
    }


def _failure(problem: str) -> dict[str, object]:
    cause, next_step = (
        (
            "wheel_or_receipt_digest_mismatch",
            "retain_evidence_and_stop",
        )
        if problem == "retrieval_order_shared_wheel_mismatch"
        else (
            "proof_source_or_input_binding_invalid",
            "inspect_first_failed_gate",
        )
    )
    return {
        "schema_version": (
            "mke.retrieval_order_installed_proof_result.v1"
        ),
        "status": "failed",
        "mode": "installed_proof",
        "authority_layer": "same_wheel_external_store",
        "canonical": True,
        "output_state": "not_applicable",
        "publication_outcome": "not_attempted",
        "problem": problem,
        "cause": cause,
        "next_step": next_step,
        "first_failed_gate": "preflight",
        "stage_statuses": [
            {"name": "preflight", "status": "failed"},
            {"name": "installed_proof", "status": "not_run"},
        ],
        "historical_revision": 0,
        "current_revision": 0,
        "candidate_seal": "none",
        "wheel_sha256": "none",
        "interpreters": [],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Installed deterministic-order proof: explicit prebuilt "
            "wheel only.\n"
            "It never rebuilds or discovers a wheel.\n"
            "It establishes explicit wheel/receipt/input identity "
            "preflight; installed module, distribution, strategy "
            "revision, and query-policy revision; and validator "
            "function availability under Python 3.12 and Python "
            "3.13.\n"
            "This proof checks validator availability only; it does "
            "not execute either validator. Canonical checkout content "
            "is validated separately by "
            "tests/evaluation/"
            "test_retrieval_order_canonical_evidence.py."
        )
    )
    parser.add_argument(
        "--python",
        action="append",
        type=Path,
        required=True,
    )
    parser.add_argument("--mke-wheel", type=Path, required=True)
    parser.add_argument(
        "--candidate-receipt",
        type=Path,
        required=True,
    )
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument(
        "--development-freeze",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--holdout-receipt",
        type=Path,
        required=True,
    )
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument(
        "--compatibility",
        type=Path,
        required=True,
    )
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if len(arguments.python) != 2:
            raise ProofError(
                "retrieval_order_proof_preflight_invalid"
            )
        result = run_proof(
            ProofInputs(
                interpreters=tuple(arguments.python),
                wheel=arguments.mke_wheel,
                candidate_receipt=arguments.candidate_receipt,
                protocol=arguments.protocol,
                development_freeze=arguments.development_freeze,
                holdout_receipt=arguments.holdout_receipt,
                artifact=arguments.artifact,
                compatibility=arguments.compatibility,
                timeout_seconds=arguments.timeout,
            )
        )
    except ProofError as error:
        result = _failure(error.problem)
    except Exception:
        result = _failure(
            "retrieval_order_proof_preflight_invalid"
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


if __name__ == "__main__":
    raise SystemExit(main())
