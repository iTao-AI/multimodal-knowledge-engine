#!/usr/bin/env python3
"""Build once and prove installed single-Source CLI/SDK consumption on Python 3.12/3.13.

Run as ``python -m scripts.source_evidence_wheel_proof`` from the checkout.
All installation inputs are locked, offline and commit-bound; raw diagnostics stay external.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from mke.interfaces.mcp_schemas import (
    ActiveAuthoritySnapshotV1,
    EvidenceDescriptorV1,
    EvidenceReadAffordanceV1,
)
from mke.interfaces.source_search_schemas import SourceSearchScopeV1
from scripts import consumer_source_pack_proof as processes
from scripts import pdf_extraction_observation_wheel_proof as installation
from scripts import source_evidence_installed_consumer as consumer

SCHEMA = "mke.source_evidence_wheel_proof.v1"
CASE_CODES = consumer.CASE_CODES
ASSET_PATHS = (
    "scripts/source_evidence_installed_consumer.py",
    "scripts/source_evidence_consumer.py",
    "scripts/consumer_source_pack_client.py",
    "scripts/consumer_source_pack_proof.py",
    "tests/fixtures/source-search-v1/mcp-tool-schemas.json",
    "tests/fixtures/source-evidence-installed-v1/manifest.json",
    "tests/fixtures/source-evidence-installed-v1/selected.pdf",
    "tests/fixtures/source-evidence-installed-v1/other.pdf",
)
EXPECTED_CASES = {
    "first_page": "more_available",
    "complete": "complete",
    "selected_empty": "insufficient_evidence",
    "unrelated_match": True,
    "cli_sdk_equal": True,
    "utf8_digest_and_excerpt_verified": True,
}
FAILURE_CODES = frozenset(
    {
        "source_commit_invalid",
        "source_commit_changed",
        "work_directory_exists",
        "external_work_directory_required",
        "python_interpreter_unavailable",
        "posix_host_required",
        "wheel_build_failed",
        "wheel_source_mismatch",
        "locked_inputs_changed",
        "locked_constraints_unavailable",
        "wheel_install_failed",
        "locked_install_failed",
        "environment_create_failed",
        "installed_dependencies_failed",
        "installed_identity_failed",
        "installed_origin_invalid",
        "asset_identity_invalid",
        "consumer_payload_invalid",
        "native_consumer_failed",
        "negative_boundary_failed",
        "wheel_changed",
        "cleanup_failed",
        "command_output_exceeded",
        "command_timed_out",
        "command_could_not_start",
        "proof_failed",
        "receipt_publication_failed",
    }
)


class ProofFailure(RuntimeError):
    pass


def require(value: bool, code: str) -> None:
    if not value:
        raise ProofFailure(code)


def encoded(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def safe_code(error: Exception) -> str:
    code = (
        str(error)
        if isinstance(error, (ProofFailure, installation.ProofFailure))
        else "proof_failed"
    )
    return code if code in FAILURE_CODES else "proof_failed"


class Runner:
    def __init__(self, cwd: Path, log: Path | None = None) -> None:
        self.cwd, self.log = cwd, log
        self.environment = processes.isolated_environment(os.environ)
        self.environment.update(
            UV_OFFLINE="1",
            UV_PYTHON_DOWNLOADS="never",
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            PWD=str(cwd),
        )

    def record(self, value: dict[str, Any]) -> None:
        if self.log is not None:
            with self.log.open("a", encoding="utf-8") as stream:
                stream.write(encoded(value).decode() + "\n")

    def call(
        self, argv: list[str], code: str = "command", *, cwd: Path | None = None
    ) -> processes.CommandResult:
        try:
            result = processes.run_bounded(
                argv,
                cwd=cwd or self.cwd,
                env=self.environment,
                timeout_seconds=180,
                max_stdout_bytes=2 * 1024 * 1024,
                max_stderr_bytes=2 * 1024 * 1024,
            )
        except processes.ControllerError as error:
            terminal = error.code if error.code in FAILURE_CODES else "proof_failed"
            self.record(
                {
                    "argv": argv,
                    "code": terminal,
                    "stdout": error.stdout.decode(errors="replace"),
                    "stderr": error.stderr.decode(errors="replace"),
                }
            )
            raise ProofFailure(terminal) from error
        self.record(
            {
                "argv": argv,
                "code": code,
                "returncode": result.returncode,
                "stdout": result.stdout.decode(errors="replace"),
                "stderr": result.stderr.decode(errors="replace"),
            }
        )
        return result

    def checked(
        self, argv: list[str], code: str, *, cwd: Path | None = None
    ) -> processes.CommandResult:
        result = self.call(argv, code, cwd=cwd)
        require(result.returncode == 0, code)
        return result


def check_source(repository: Path, commit: str, code: str) -> None:
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, code)
    try:
        actual = processes._clean_sha1_source_commit(repository)  # pyright: ignore[reportPrivateUsage]
    except processes.ControllerError as error:
        raise ProofFailure(code) from error
    require(actual == commit, code)


def external_root(repository: Path, requested: Path) -> Path:
    require(not requested.exists() and not requested.is_symlink(), "work_directory_exists")
    try:
        parent = requested.absolute().parent.resolve(strict=True)
        inside = processes._repository_identity_in_ancestry(parent, repository=repository)  # pyright: ignore[reportPrivateUsage]
    except (OSError, RuntimeError, processes.ControllerError) as error:
        raise ProofFailure("external_work_directory_required") from error
    require(not inside, "external_work_directory_required")
    return parent / requested.name


def interpreters(paths: list[Path], repository: Path) -> list[tuple[Path, str]]:
    require(len(paths) == 2, "python_interpreter_unavailable")
    versions: list[tuple[Path, str]] = []
    runner = Runner(repository)
    for path in paths:
        try:
            result = runner.checked(
                [
                    str(path.absolute()),
                    "-I",
                    "-B",
                    "-c",
                    "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')",
                ],
                "python_interpreter_unavailable",
            )
        except ProofFailure as error:
            raise ProofFailure("python_interpreter_unavailable") from error
        versions.append((path.absolute(), result.stdout.decode().strip()))
    require(
        sorted(minor for _, minor in versions) == ["3.12", "3.13"], "python_interpreter_unavailable"
    )
    return sorted(versions, key=lambda value: value[1])


def asset_target(root: Path, relative: str) -> Path:
    name = Path(relative).name
    return (
        root / name
        if relative.startswith("scripts/") or name == "mcp-tool-schemas.json"
        else root / "assets" / name
    )


def copy_assets(repository: Path, commit: str, destination: Path) -> dict[str, str]:
    destination.mkdir()
    (destination / "assets").mkdir()
    expected: dict[str, str] = {}
    for relative in ASSET_PATHS:
        content = installation.blob(repository, commit, relative)
        asset_target(destination, relative).write_bytes(content)
        expected[relative] = hashlib.sha256(content).hexdigest()
    verify_assets(destination, expected)
    return expected


def verify_assets(root: Path, expected: dict[str, str]) -> None:
    try:
        require(set(expected) == set(ASSET_PATHS), "asset_identity_invalid")
        for relative, digest in expected.items():
            path = asset_target(root, relative)
            require(
                not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                "asset_identity_invalid",
            )
    except (OSError, ValueError) as error:
        raise ProofFailure("asset_identity_invalid") from error


def validate_consumer(
    result: processes.CommandResult, case: str, assets: dict[str, str]
) -> dict[str, Any]:
    code = "consumer_payload_invalid" if case == "flow" else "negative_boundary_failed"
    try:
        require(len(result.stdout) <= 32768, code)
        payload = json.loads(result.stdout)
        require(isinstance(payload, dict), code)
        if case != "flow":
            require(
                result.returncode == 1
                and payload
                == {
                    "schema_version": consumer.SCHEMA,
                    "status": "failed",
                    "code": CASE_CODES[case],
                },
                code,
            )
            return cast(dict[str, Any], payload)
        require(
            result.returncode == 0
            and set(payload)
            == {
                "schema_version",
                "status",
                "tool_count",
                "source_count",
                "scope",
                "authority_snapshot",
                "references",
                "asset_sha256",
                "cases",
            },
            code,
        )
        require(
            payload["schema_version"] == consumer.SCHEMA
            and payload["status"] == "passed"
            and type(payload["tool_count"]) is int
            and payload["tool_count"] == 15
            and type(payload["source_count"]) is int
            and payload["source_count"] == 2
            and payload["asset_sha256"] == assets
            and payload["cases"] == EXPECTED_CASES,
            code,
        )
        require(
            all(
                payload["cases"][key] is True
                for key in ("unrelated_match", "cli_sdk_equal", "utf8_digest_and_excerpt_verified")
            ),
            code,
        )
        scope = SourceSearchScopeV1.model_validate(payload["scope"])
        require(
            scope.publication_revision == 1
            and scope.content_fingerprint == "sha256:" + assets["selected"],
            code,
        )
        authority = ActiveAuthoritySnapshotV1.model_validate(payload["authority_snapshot"])
        observation = authority.observation
        require(
            observation.state == "active"
            and observation.source_count == 2
            and observation.active_publication_count == 2
            and observation.active_evidence_count == 8,
            code,
        )
        raw_references: object = payload["references"]
        require(isinstance(raw_references, list), code)
        references = cast(list[dict[str, Any]], raw_references)
        require(len(references) == 3, code)
        evidence_ids: set[str] = set()
        pages: set[int] = set()
        for reference in references:
            require(
                set(reference)
                == {
                    "evidence",
                    "read",
                    "verified_utf8_bytes",
                    "exact_text_sha256_verified",
                    "excerpt_window_verified",
                },
                code,
            )
            evidence = EvidenceDescriptorV1.model_validate(reference["evidence"])
            read = EvidenceReadAffordanceV1.model_validate(reference["read"])
            require(
                all(getattr(evidence, key) == getattr(scope, key) for key in consumer.SCOPE_KEYS)
                and read.evidence_id == evidence.evidence_id
                and evidence.evidence_id not in evidence_ids,
                code,
            )
            page = evidence.locator.start
            require(
                evidence.locator.kind == "page"
                and evidence.locator.end == page
                and page in {1, 2, 3},
                code,
            )
            text = f"needle café selected page {page}".encode()
            require(
                type(reference["verified_utf8_bytes"]) is int
                and reference["verified_utf8_bytes"] == evidence.original_utf8_bytes == len(text)
                and evidence.evidence_text_sha256 == "sha256:" + hashlib.sha256(text).hexdigest()
                and reference["exact_text_sha256_verified"] is True
                and reference["excerpt_window_verified"] is True,
                code,
            )
            evidence_ids.add(evidence.evidence_id)
            pages.add(page)
        require(pages == {1, 2, 3}, code)
        return cast(dict[str, Any], payload)
    except ProofFailure:
        raise
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ProofFailure(code) from error


def cleanup_temporary(path: Path) -> None:
    try:
        processes._remove_candidate_staging(path)  # pyright: ignore[reportPrivateUsage]
    except processes.ControllerError as error:
        raise ProofFailure("cleanup_failed") from error


def installed_case(
    repository: Path,
    commit: str,
    interpreter: Path,
    minor: str,
    wheel: Path,
    binding: dict[str, Any],
    constraints: Path,
    locked: dict[str, set[str]],
    root: Path,
    runner: Runner,
) -> dict[str, Any]:
    root.mkdir()
    environment = root / "environment"
    runner.checked(
        ["uv", "venv", "--python", str(interpreter), "--no-python-downloads", str(environment)],
        "environment_create_failed",
    )
    python = environment / "bin/python"
    mke = environment / "bin/mke"
    runner.checked(
        [
            "uv",
            "pip",
            "sync",
            "--offline",
            "--require-hashes",
            "--python",
            str(python),
            str(constraints),
        ],
        "locked_install_failed",
    )
    runner.checked(
        ["uv", "pip", "install", "--offline", "--no-deps", "--python", str(python), str(wheel)],
        "wheel_install_failed",
    )
    runner.checked(["uv", "pip", "check", "--python", str(python)], "installed_dependencies_failed")

    def identity() -> dict[str, Any]:
        probe = installation._IDENTITY_PROBE  # pyright: ignore[reportPrivateUsage]
        payload = json.loads(
            runner.checked(
                [str(python), "-I", "-B", "-c", probe],
                "installed_identity_failed",
            ).stdout
        )
        installation.validate_installed_identity(
            payload, environment, repository, minor, binding["module_sha256"]
        )
        installation.validate_dependencies(payload["dependencies"], locked, binding["version"])
        installation.validate_install_origin(payload, wheel, binding["wheel_sha256"])
        return cast(dict[str, Any], payload)

    before = identity()
    client = root / "consumer"
    asset_sha256 = copy_assets(repository, commit, client)
    declared = consumer.load_assets(client / "assets")
    fixtures = {role: entry["sha256"] for role, entry in declared.items()}
    data = root / "data"
    command = [
        str(python),
        "-I",
        "-B",
        str(client / "source_evidence_installed_consumer.py"),
        "--mke",
        str(mke),
        "--work-dir",
        str(data),
        "--assets",
        str(client / "assets"),
        "--schemas",
        str(client / "mcp-tool-schemas.json"),
    ]
    native = validate_consumer(
        runner.call(command, "native_consumer_failed", cwd=client), "flow", fixtures
    )
    boundaries: dict[str, str] = {}
    for case in CASE_CODES:
        result = runner.call([*command, "--case", case], "negative_boundary_failed", cwd=client)
        boundary = validate_consumer(result, case, fixtures)
        if case in {"read_failure", "citation_failure"}:
            observed = json.loads((data / f"{case}-boundary.json").read_bytes())
            require(
                observed
                == {
                    "first_reference_complete": True,
                    "native_boundary_exercised": True,
                    "successful_receipt_emitted": False,
                },
                "negative_boundary_failed",
            )
        boundaries[case] = boundary["code"]
    verify_assets(client, asset_sha256)
    after = identity()
    require(before == after, "installed_identity_failed")
    return {
        "python_version": before["python_version"],
        "dependencies": before["dependencies"],
        "wheel_sha256": binding["wheel_sha256"],
        "source_import": "installed_site_packages",
        "installed_origin": "local_wheel",
        "consumer_asset_sha256": asset_sha256,
        "native": native,
        "negative_boundaries": boundaries,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    repository = args.repository.resolve()
    check_source(repository, args.source_commit, "source_commit_invalid")
    root = external_root(repository, args.work_dir)
    require(os.name == "posix", "posix_host_required")
    versions = interpreters(args.python, repository)
    installation.verify_locked_inputs(repository, args.source_commit)
    try:
        root.mkdir()
    except FileExistsError as error:
        raise ProofFailure("work_directory_exists") from error
    temporary = root / "temporary"
    temporary.mkdir()
    runner = Runner(temporary, root / "commands.jsonl")
    try:
        snapshotter = processes._candidate_source_snapshot  # pyright: ignore[reportPrivateUsage]
        snapshot = snapshotter(repository, args.source_commit, temporary, 180)
        build = temporary / "build"
        build.mkdir()
        runner.checked(
            [
                "uv",
                "build",
                "--offline",
                "--wheel",
                "--python",
                str(versions[0][0]),
                "--out-dir",
                str(build),
                str(snapshot),
            ],
            "wheel_build_failed",
        )
        wheels = list(build.glob("*.whl"))
        require(len(wheels) == 1, "wheel_build_failed")
        binding = installation.verify_wheel(repository, args.source_commit, wheels[0])
        retained = root / "wheel"
        retained.mkdir()
        wheel = retained / wheels[0].name
        shutil.move(wheels[0], wheel)
        exported = runner.checked(
            [
                "uv",
                "export",
                "--project",
                str(snapshot),
                "--locked",
                "--no-dev",
                "--no-emit-project",
                "--no-header",
            ],
            "locked_constraints_unavailable",
        )
        constraints = temporary / "locked-core-requirements.txt"
        constraints.write_bytes(exported.stdout)
        lock_content = installation.blob(repository, args.source_commit, "uv.lock")
        locked: dict[str, set[str]] = {}
        for package in tomllib.loads(lock_content.decode())["package"]:
            locked.setdefault(package["name"], set()).add(package["version"])
        results = [
            installed_case(
                repository,
                args.source_commit,
                interpreter,
                minor,
                wheel,
                binding,
                constraints,
                locked,
                temporary / f"python-{minor}",
                runner,
            )
            for interpreter, minor in versions
        ]
        require(
            results[0]["consumer_asset_sha256"] == results[1]["consumer_asset_sha256"],
            "asset_identity_invalid",
        )
        result = {
            "schema_version": SCHEMA,
            "status": "passed",
            "source_commit": args.source_commit,
            "wheel_sha256": binding["wheel_sha256"],
            "wheel_filename": wheel.name,
            "package_version": binding["version"],
            "package_files_matched": len(binding["module_sha256"]),
            "wheel_members_matched": binding["wheel_members_matched"],
            "wheel_build_count": 1,
            "uv_lock_sha256": hashlib.sha256(lock_content).hexdigest(),
            "constraints_sha256": hashlib.sha256(exported.stdout).hexdigest(),
            "python_versions": [minor for _, minor in versions],
            "tool_count": 15,
            "network_access": "not_used",
            "dependency_constraints": "uv_lock_hash_checked",
            "cleanup": True,
            "results": results,
        }
        require(len(encoded(result)) <= 32768, "consumer_payload_invalid")
        require(
            hashlib.sha256(wheel.read_bytes()).hexdigest() == binding["wheel_sha256"],
            "wheel_changed",
        )
        installation.verify_locked_inputs(repository, args.source_commit)
        check_source(repository, args.source_commit, "source_commit_changed")
        cleanup_temporary(temporary)
        check_source(repository, args.source_commit, "source_commit_changed")

        def validate(value: object) -> None:
            if value != result:
                raise ValueError("receipt changed")

        publication = processes.publish_json_no_replace(
            root / "proof.json", encoded(result) + b"\n", validate=validate
        )
        require(publication.publication_outcome == "published", "receipt_publication_failed")
        return result
    except Exception as error:
        runner.record({"event": "controller_failure", "code": safe_code(error)})
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--python", type=Path, action="append", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except Exception as error:
        result = {"schema_version": SCHEMA, "status": "failed", "code": safe_code(error)}
    print(encoded(result).decode())
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
