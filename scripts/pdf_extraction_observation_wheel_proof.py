#!/usr/bin/env python3
"""Prove one commit-bound installed wheel through fresh PDF CLI/MCP/export consumers.

Only locked cached dependencies and already installed Python 3.12/3.13 are used.
The external work directory is retained; stdout never contains its private paths.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path
from typing import Any, cast

SCHEMA = "mke.pdf_extraction_observation_wheel_proof.v1"
DISTRIBUTION = "multimodal-knowledge-engine"
CONSUMERS = (
    "pdf_extraction_observation_consumer.py",
    "source_discovery_consumer.py",
    "compiled_library_export_consumer_v2.py",
    "compiled_library_export_consumer_v3.py",
    "build_compiled_library_viewer.py",
)
EXPECTATION = "tests/fixtures/pdf-extraction-observation-v1/mcp-tool-schemas.json"
DIRTY_ENV = frozenset({"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"})


class ProofFailure(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProofFailure(code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def command(
    argv: list[str], *, cwd: Path, log: Path | None = None, timeout: float = 180
) -> subprocess.CompletedProcess[bytes]:
    environment = {key: value for key, value in os.environ.items() if key not in DIRTY_ENV}
    environment.update(
        UV_OFFLINE="1", UV_PYTHON_DOWNLOADS="never", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1"
    )
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=environment,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    except (OSError, subprocess.SubprocessError) as error:
        raise ProofFailure("command_failed") from error
    require(
        len(result.stdout) <= 2 * 1024 * 1024 and len(result.stderr) <= 2 * 1024 * 1024,
        "command_output_exceeded",
    )
    if log is not None:
        with log.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "argv": argv,
                        "returncode": result.returncode,
                        "stdout": result.stdout.decode("utf-8", errors="replace"),
                        "stderr": result.stderr.decode("utf-8", errors="replace"),
                    }
                )
                + "\n"
            )
    require(not timed_out, "command_failed")
    return result


def blob(repository: Path, commit: str, path: str) -> bytes:
    result = command(["git", "show", f"{commit}:{path}"], cwd=repository)
    require(result.returncode == 0, "source_commit_invalid")
    return result.stdout


def verify_wheel(repository: Path, commit: str, wheel: Path) -> dict[str, Any]:
    listing = command(
        ["git", "ls-tree", "-r", "--name-only", commit, "--", "src/mke"], cwd=repository
    )
    require(listing.returncode == 0, "source_commit_invalid")
    files = listing.stdout.decode().splitlines()
    require(bool(files), "wheel_source_mismatch")
    expected = {path.removeprefix("src/"): digest(blob(repository, commit, path)) for path in files}
    project = tomllib.loads(blob(repository, commit, "pyproject.toml").decode())["project"]
    dist_info = f"{project['name'].replace('-', '_')}-{project['version']}.dist-info"
    metadata_name = f"{dist_info}/METADATA"
    entry_points_name = f"{dist_info}/entry_points.txt"
    metadata_files = {
        metadata_name,
        entry_points_name,
        f"{dist_info}/WHEEL",
        f"{dist_info}/RECORD",
        f"{dist_info}/licenses/LICENSE",
    }
    console_scripts = project.get("scripts", {})
    expected_entry_points = {"console_scripts": console_scripts} if console_scripts else {}
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        require(
            len(names) == len(set(names))
            and set(names) <= expected.keys() | metadata_files
            and metadata_name in names,
            "wheel_source_mismatch",
        )
        observed = {
            name: digest(archive.read(name))
            for name in names
            if name.startswith("mke/") and not name.endswith("/")
        }
        require(observed == expected, "wheel_source_mismatch")
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        require(
            metadata["Name"] == project["name"] == DISTRIBUTION
            and metadata["Version"] == project["version"]
            and set(str(metadata["Requires-Python"]).split(","))
            == set(project["requires-python"].split(",")),
            "wheel_source_mismatch",
        )
        observed_entry_points: dict[str, dict[str, str]] = {}
        if entry_points_name in names:
            parser = configparser.ConfigParser(interpolation=None)
            parser.optionxform = lambda optionstr: optionstr
            try:
                parser.read_string(archive.read(entry_points_name).decode("utf-8"))
            except (configparser.Error, UnicodeError) as error:
                raise ProofFailure("wheel_source_mismatch") from error
            require(not parser.defaults(), "wheel_source_mismatch")
            observed_entry_points = {
                section: dict(parser.items(section)) for section in parser.sections()
            }
        require(observed_entry_points == expected_entry_points, "wheel_source_mismatch")
    return {
        "wheel_sha256": digest(wheel.read_bytes()),
        "version": project["version"],
        "module_sha256": expected,
        "wheel_members_matched": len(names),
        "console_scripts": console_scripts,
    }


def verify_locked_inputs(repository: Path, commit: str) -> None:
    for path in ("pyproject.toml", "uv.lock"):
        require(
            (repository / path).read_bytes() == blob(repository, commit, path),
            "locked_inputs_changed",
        )


def validate_installed_identity(
    payload: dict[str, Any],
    environment: Path,
    repository: Path,
    minor: str,
    expected_modules: dict[str, str],
) -> None:
    module = Path(payload["module"])
    executable = Path(payload["executable"])
    require(
        module.is_absolute()
        and executable.is_absolute()
        and environment.resolve() in module.resolve().parents
        and repository.resolve() not in module.resolve().parents
        and module.parent.name == "mke"
        and module.parent.parent.name == "site-packages"
        and executable.name == "python"
        and executable.parent.resolve() == (environment / "bin").resolve()
        and Path(payload["prefix"]).resolve() == environment.resolve()
        and payload["python_version"].rsplit(".", 1)[0] == minor
        and payload["module_sha256"] == expected_modules,
        "installed_identity_failed",
    )


def validate_dependencies(
    actual: dict[str, str],
    locked: dict[str, set[str]],
    version: str,
) -> None:
    require(
        {"mcp", "pydantic", "pymupdf", DISTRIBUTION} <= actual.keys(),
        "installed_dependencies_failed",
    )
    for name, observed in actual.items():
        require(
            observed == version if name == DISTRIBUTION else observed in locked.get(name, set()),
            "installed_dependencies_failed",
        )


def validate_install_origin(payload: dict[str, Any], wheel: Path, wheel_sha256: str) -> str | None:
    """PyPA permits empty archive_info; present SHA-256 values must still match."""
    raw_direct: object = payload.get("direct_url")
    require(isinstance(raw_direct, dict), "installed_origin_invalid")
    direct = cast(dict[str, Any], raw_direct)
    require(
        direct.get("url") == wheel.resolve().as_uri()
        and "archive_info" in direct
        and "dir_info" not in direct
        and "vcs_info" not in direct,
        "installed_origin_invalid",
    )
    raw_archive: object = direct["archive_info"]
    require(isinstance(raw_archive, dict), "installed_origin_invalid")
    archive = cast(dict[str, Any], raw_archive)
    raw_hashes: object = archive.get("hashes", {})
    require(isinstance(raw_hashes, dict), "installed_origin_invalid")
    hashes = cast(dict[str, Any], raw_hashes)
    recorded = hashes.get("sha256")
    if recorded is not None:
        require(recorded == wheel_sha256, "installed_origin_invalid")
    legacy = archive.get("hash")
    if legacy is not None:
        require(legacy == "sha256=" + wheel_sha256, "installed_origin_invalid")
        recorded = wheel_sha256
    return cast(str | None, recorded)


_IDENTITY_PROBE = """
import hashlib,importlib.metadata,json,sys
from pathlib import Path
import mke
package=Path(mke.__file__).resolve().parent
distribution=importlib.metadata.distribution('multimodal-knowledge-engine')
direct=json.loads(distribution.read_text('direct_url.json'))
print(json.dumps({
 'module':mke.__file__,'executable':sys.executable,'prefix':sys.prefix,
 'python_version':'.'.join(map(str,sys.version_info[:3])),
 'module_sha256':{'mke/'+str(path.relative_to(package)):hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in package.rglob('*')
                  if path.is_file() and '__pycache__' not in path.parts},
 'dependencies':{item.metadata['Name'].lower().replace('_','-'):item.version
                 for item in importlib.metadata.distributions()},
 'direct_url':direct,
}))
"""


def receipt(result: subprocess.CompletedProcess[bytes], code: str) -> dict[str, Any]:
    require(result.returncode == 0, code)
    payload = json.loads(result.stdout)
    require(isinstance(payload, dict), code)
    value = cast(dict[str, Any], payload)
    require(value.get("status") == "passed", code)
    return value


def create_malformed_export(export: Path, destination: Path) -> None:
    shutil.copytree(export, destination)
    manifest = destination / "export-manifest.json"
    payload = json.loads(manifest.read_bytes())
    payload["schema_version"] = "mke.compiled_library_export.invalid"
    manifest.write_text(json.dumps(payload), encoding="utf-8")


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
) -> dict[str, Any]:
    root.mkdir()
    log = root / "commands.jsonl"

    def checked(
        argv: list[str], code: str, *, cwd: Path = root
    ) -> subprocess.CompletedProcess[bytes]:
        result = command(argv, cwd=cwd, log=log)
        require(result.returncode == 0, code)
        return result

    environment = root / "environment"
    checked(
        ["uv", "venv", "--python", str(interpreter), "--no-python-downloads", str(environment)],
        "environment_create_failed",
    )
    python = environment / "bin/python"
    checked(
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
    checked(
        ["uv", "pip", "install", "--offline", "--no-deps", "--python", str(python), str(wheel)],
        "wheel_install_failed",
    )
    checked(["uv", "pip", "check", "--python", str(python)], "installed_dependencies_failed")
    identity = json.loads(
        checked(
            [str(python), "-I", "-B", "-c", _IDENTITY_PROBE], "installed_identity_failed"
        ).stdout
    )
    validate_installed_identity(identity, environment, repository, minor, binding["module_sha256"])
    validate_dependencies(identity["dependencies"], locked, binding["version"])
    recorded_hash = validate_install_origin(identity, wheel, binding["wheel_sha256"])

    client = root / "consumer"
    client.mkdir()
    for name in CONSUMERS:
        (client / name).write_bytes(blob(repository, commit, "scripts/" + name))
    expectation = client / "mcp-tool-schemas.json"
    expectation.write_bytes(blob(repository, commit, EXPECTATION))
    require(len(json.loads(expectation.read_bytes())["tools"]) == 14, "tool_inventory_mismatch")
    data = root / "data"
    native = receipt(
        checked(
            [
                str(python),
                "-I",
                "-B",
                str(client / CONSUMERS[0]),
                "--mke-bin",
                str(environment / "bin/mke"),
                "--work-dir",
                str(data),
                "--expectation",
                str(expectation),
            ],
            "native_consumer_failed",
        ),
        "native_consumer_failed",
    )
    require(native.get("tool_count") == 14, "tool_inventory_mismatch")
    fixture_sha256 = digest((data / "declared-mixed.pdf").read_bytes())
    require(
        native["identity"]["content_fingerprint"] == "sha256:" + fixture_sha256,
        "fixture_identity_mismatch",
    )
    validator = [str(python), "-I", "-B", str(client / "compiled_library_export_consumer_v3.py")]
    independent = receipt(
        checked(
            validator + ["--export", str(data / "compiled-v3"), "--json"],
            "independent_consumer_failed",
        ),
        "independent_consumer_failed",
    )
    broken = root / "malformed-export"
    create_malformed_export(data / "compiled-v3", broken)
    rejected = command(validator + ["--export", str(broken), "--json"], cwd=root, log=log)
    require(
        rejected.returncode == 1
        and json.loads(rejected.stdout) == {"code": "export_invalid", "status": "failed"},
        "failure_exit_contract_failed",
    )
    unknown = command(
        [
            str(environment / "bin/mke"),
            "--db",
            str(data / "library.sqlite"),
            "source",
            "browse",
            "src_unknown",
            "--publication-id",
            "pub_unknown",
            "--contract-version",
            "v2",
            "--json",
        ],
        cwd=root,
        log=log,
    )
    unknown_payload = json.loads(unknown.stdout)
    require(
        unknown.returncode == 1
        and unknown_payload.get("ok") is False
        and unknown_payload.get("problem") == "evidence_not_found",
        "failure_exit_contract_failed",
    )
    return {
        "python_version": identity["python_version"],
        "dependencies": identity["dependencies"],
        "installed_identity": "environment_site_packages_bytes_match_wheel",
        "installed_wheel_origin": "bound_local_wheel",
        "recorded_archive_sha256": recorded_hash,
        "fixture_sha256": fixture_sha256,
        "tool_schema_sha256": digest(expectation.read_bytes()),
        "native_consumer": native,
        "independent_export_consumer": independent,
        "failure_exits": {"malformed_export": 1, "unknown_source": 1},
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    require(re.fullmatch(r"[0-9a-f]{40}", args.source_commit) is not None, "source_commit_invalid")
    repository = args.repository.resolve()
    root = args.work_dir.resolve()
    require(not root.exists(), "work_directory_exists")
    require(
        repository != root and repository not in root.parents, "external_work_directory_required"
    )
    require(os.name == "posix", "posix_host_required")
    require(len(args.python) == 2, "python_interpreter_unavailable")
    wheel = args.wheel.resolve()
    verify_locked_inputs(repository, args.source_commit)
    binding = verify_wheel(repository, args.source_commit, wheel)
    versions: list[tuple[Path, str]] = []
    for path in args.python:
        interpreter = path.absolute()
        result = command(
            [
                str(interpreter),
                "-I",
                "-c",
                "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            cwd=repository,
        )
        require(result.returncode == 0, "python_interpreter_unavailable")
        versions.append((interpreter, result.stdout.decode().strip()))
    require(
        sorted(minor for _, minor in versions) == ["3.12", "3.13"], "python_interpreter_unavailable"
    )
    root.mkdir(parents=True)
    exported = command(
        ["uv", "export", "--locked", "--no-dev", "--no-emit-project", "--no-header"],
        cwd=repository,
        log=root / "commands.jsonl",
    )
    require(exported.returncode == 0, "locked_constraints_unavailable")
    constraints = root / "locked-core-requirements.txt"
    constraints.write_bytes(exported.stdout)
    lock = tomllib.loads(blob(repository, args.source_commit, "uv.lock").decode())
    locked: dict[str, set[str]] = {}
    for package in lock["package"]:
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
            root / f"python-{minor}",
        )
        for interpreter, minor in versions
    ]
    require(digest(wheel.read_bytes()) == binding["wheel_sha256"], "wheel_changed")
    verify_locked_inputs(repository, args.source_commit)
    return {
        "schema_version": SCHEMA,
        "status": "passed",
        "source_commit": args.source_commit,
        "wheel_sha256": binding["wheel_sha256"],
        "package_version": binding["version"],
        "package_files_matched": len(binding["module_sha256"]),
        "wheel_members_matched": binding["wheel_members_matched"],
        "console_scripts": binding["console_scripts"],
        "uv_lock_sha256": digest(blob(repository, args.source_commit, "uv.lock")),
        "constraints_sha256": digest(exported.stdout),
        "python_versions": sorted(minor for _, minor in versions),
        "tool_count": 14,
        "source_import": "installed_wheel",
        "network_access": "not_used",
        "dependency_constraints": "uv_lock_hash_checked",
        "results": results,
        "scope": "synthetic_native_consumer",
        "ocr_execution": "not_performed",
        "release_publication": "not_performed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--python", type=Path, action="append", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args)
    except ProofFailure as error:
        result = {"status": "failed", "code": str(error)}
    except Exception:
        result = {"status": "failed", "code": "proof_failed"}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
