#!/usr/bin/env python3
"""Prove the bounded direct-audio path from two fresh wheel installations."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import platform
import re
import shutil
import socket
import stat
import tempfile
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

from mke.runtime import DEFAULT_MODEL_REVISION

if TYPE_CHECKING or __package__:
    from scripts import direct_audio_dependency_receipt as dependency_authority
else:
    import direct_audio_dependency_receipt as dependency_authority

_MODEL_IDENTIFIER = "Systran/faster-whisper-small"
_MODEL_DIRECTORY = "models--Systran--faster-whisper-small"
_FIXTURES = ("direct-audio.m4a", "direct-audio.mp3", "direct-audio.wav")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!_+()-]{0,255}\Z")
_EVIDENCE_ID_RE = re.compile(r"ev_[0-9a-f]{32}\Z")
_SOURCE_ID_RE = re.compile(r"src_[0-9a-f]{32}\Z")
_PUBLICATION_ID_RE = re.compile(r"pub_[0-9a-f]{32}\Z")
_RUN_ID_RE = re.compile(r"run_[0-9a-f]{32}\Z")
_COMMAND_TIMEOUT_SECONDS = 300.0
_PROVIDER_TIMEOUT_SECONDS = 900.0
_MAX_STDOUT_BYTES = 2 * 1024 * 1024
_MAX_STDERR_BYTES = 512 * 1024
_DENY_NETWORK_PROFILE = "(version 1)(allow default)(deny network*)"
_PRODUCT_HELPER_SOURCE = r'''
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
from pathlib import Path

from mke.application import KnowledgeEngine
from mke.runtime import (
    FasterWhisperTranscriptionConfig,
    RuntimeConfig,
    build_engine,
)


def evidence_ref(item):
    result = item.result
    return {
        "schema_version": "mke.evidence_ref.v1",
        "evidence_id": result.evidence_id,
        "source_id": result.source_id,
        "content_fingerprint": item.content_fingerprint,
        "publication_id": result.publication_id,
        "publication_revision": item.publication_revision,
        "run_id": item.run_id,
        "locator": {
            "kind": result.locator_kind,
            "start": result.locator_start,
            "end": result.locator_end,
        },
        "text": result.text,
    }


parser = argparse.ArgumentParser()
parser.add_argument("--lane", choices=("python", "cli"), required=True)
parser.add_argument("--mke-command", required=True)
parser.add_argument("--fixture", type=Path, required=True)
parser.add_argument("--db", type=Path, required=True)
parser.add_argument("--model", required=True)
parser.add_argument("--model-revision", required=True)
parser.add_argument("--device", required=True)
parser.add_argument("--compute-type", required=True)
parser.add_argument("--language", required=True)
parser.add_argument("--model-cache", type=Path, required=True)
parser.add_argument("--transcription-timeout-seconds", required=True)
parser.add_argument("--direct-audio-footprint-bytes", type=int, required=True)
parser.add_argument("--direct-audio-footprint-budget-mode", required=True)
args = parser.parse_args()
runtime = RuntimeConfig(
    db_path=args.db,
    transcription=FasterWhisperTranscriptionConfig(
        model=args.model,
        model_revision=args.model_revision,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        cache_dir=args.model_cache,
    ),
    direct_audio_footprint_bytes=args.direct_audio_footprint_bytes,
    direct_audio_footprint_budget_mode=args.direct_audio_footprint_budget_mode,
)
if args.lane == "python":
    engine = build_engine(runtime)
    try:
        ingest = engine.ingest_file(args.fixture)
        report = dataclasses.asdict(ingest.transcript_intake_report)
        run_state = ingest.run_state.value
        ingest_run_id = ingest.run_id
    finally:
        engine.close()
else:
    runtime_args = [
        "--transcript-provider", "faster-whisper",
        "--model", args.model,
        "--model-revision", args.model_revision,
        "--device", args.device,
        "--compute-type", args.compute_type,
        "--language", args.language,
        "--model-cache", str(args.model_cache),
        "--transcription-timeout-seconds", args.transcription_timeout_seconds,
        "--direct-audio-footprint-bytes", str(args.direct_audio_footprint_bytes),
        "--direct-audio-footprint-budget-mode", args.direct_audio_footprint_budget_mode,
    ]
    completed = subprocess.run(
        [args.mke_command, "--db", str(args.db), "ingest", str(args.fixture),
         *runtime_args, "--json"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=float(args.transcription_timeout_seconds),
    )
    if completed.stderr or len(completed.stdout) > 1024 * 1024:
        raise SystemExit("cli ingest output invalid")
    ingest_payload = json.loads(completed.stdout.decode("utf-8"))
    report = ingest_payload["transcript_intake_report"]
    run_state = ingest_payload["run_state"]
    ingest_run_id = ingest_payload["run_id"]
    for command, words in (("search", ["traceable"]), ("ask", ["traceable", "publication"])):
        checked = subprocess.run(
            [args.mke_command, "--db", str(args.db), command, *words],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
            timeout=60,
        )
        if checked.stderr or b"traceable" not in checked.stdout.lower():
            raise SystemExit("cli retrieval output invalid")

engine = KnowledgeEngine(args.db)
try:
    search = engine.search_provenance_snapshot("traceable", limit=5)
    ask = engine.ask_provenance_snapshot("traceable publication", limit=5)
finally:
    engine.close()
if not search.results or not ask.evidence:
    raise SystemExit("retrieval returned no Evidence")
source_sha256 = hashlib.sha256(args.fixture.read_bytes()).hexdigest()
fingerprint = "sha256:" + source_sha256
search_matches = [item for item in search.results if item.content_fingerprint == fingerprint]
ask_matches = [item for item in ask.evidence if item.content_fingerprint == fingerprint]
if len(search_matches) != 1 or len(ask_matches) != 1:
    raise SystemExit("fixture Evidence identity mismatch")
if evidence_ref(search_matches[0]) != evidence_ref(ask_matches[0]):
    raise SystemExit("Search and Ask EvidenceRef mismatch")
if search_matches[0].run_id != ingest_run_id:
    raise SystemExit("ingest Run and EvidenceRef mismatch")
print(json.dumps({
    "status": "passed",
    "lane": args.lane,
    "fixture": args.fixture.suffix.removeprefix("."),
    "source_sha256": source_sha256,
    "run_id": ingest_run_id,
    "run_state": run_state,
    "search_keyword_matched": True,
    "ask_status": "evidence_found",
    "evidence_ref": evidence_ref(search_matches[0]),
    "transcript_intake_report": report,
}, sort_keys=True))
'''.strip()
_INSTALLED_IDENTITY_SOURCE = r'''
import importlib.metadata
import json
import mke
import re
import sys

rows = []
for distribution in importlib.metadata.distributions():
    name = distribution.metadata.get("Name")
    if not name:
        continue
    normalized = re.sub(r"[-_.]+", "-", name).lower()
    if normalized != "pip":
        rows.append([normalized, distribution.version])
print(json.dumps({
    "distribution": "multimodal-knowledge-engine",
    "mke_file": mke.__file__,
    "python": sys.executable,
    "repository_import": False,
    "distributions": sorted(rows),
}, sort_keys=True))
'''.strip()


class DirectAudioDeploymentProofError(RuntimeError):
    """Closed deployment-proof failure with a stable public code."""


@dataclass(frozen=True)
class DirectAudioProofConfig:
    interpreters: tuple[Path, ...]
    mke_wheel: Path
    dependency_receipt: Path
    wheelhouse: Path
    constraints: Path
    model_root: Path
    fixture_root: Path
    direct_audio_footprint_bytes: int
    direct_audio_footprint_budget_mode: Literal["baseline_plus"]
    provider_timeout_seconds: float = _PROVIDER_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if len(self.interpreters) != 2:
            raise ValueError("exactly two interpreters are required")
        if self.interpreters[0] == self.interpreters[1]:
            raise ValueError("interpreters must be distinct")
        if type(self.direct_audio_footprint_bytes) is not int:
            raise TypeError("direct audio footprint bytes must be a positive integer")
        if self.direct_audio_footprint_bytes <= 0:
            raise ValueError("direct audio footprint bytes must be a positive integer")
        if self.direct_audio_footprint_budget_mode != "baseline_plus":
            raise ValueError("direct audio footprint budget mode must be baseline_plus")
        if self.provider_timeout_seconds <= 0:
            raise ValueError("provider timeout must be positive")


@dataclass(frozen=True)
class AuthorizationManifest:
    mke_wheel_sha256: str
    mke_wheel_bytes: int
    dependency_receipt_sha256: str
    dependency_receipt_payload_sha256: str
    wheelhouse_manifest_sha256: str
    constraints_sha256: str
    interpreters: tuple[tuple[str, str, str], ...]
    package_sets: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    model_identifier: str
    model_revision: str
    model_tree_sha256: str
    model_files: tuple[tuple[str, int, str], ...]
    consumer_sha256: str
    fixtures: tuple[tuple[str, int, str], ...]
    retained_inputs_sha256: str
    estimated_temporary_disk_bytes: int
    temporary_disk_estimate_method: str
    deny_network_method: str
    cleanup_owner: str
    direct_audio_footprint_bytes: int
    direct_audio_footprint_budget_mode: Literal["baseline_plus"]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "mke.direct_audio_terminal_authorization.v1",
            "status": "ready",
            "mke_wheel_sha256": self.mke_wheel_sha256,
            "mke_wheel_bytes": self.mke_wheel_bytes,
            "dependency_receipt_sha256": self.dependency_receipt_sha256,
            "dependency_receipt_payload_sha256": self.dependency_receipt_payload_sha256,
            "wheelhouse_manifest_sha256": self.wheelhouse_manifest_sha256,
            "constraints_sha256": self.constraints_sha256,
            "interpreters": [
                {
                    "cell": cell,
                    "python_version": version,
                    "executable_sha256": digest,
                }
                for cell, version, digest in self.interpreters
            ],
            "package_sets": [
                {
                    "cell": cell,
                    "distributions": [
                        {"name": name, "version": version}
                        for name, version in distributions
                    ],
                }
                for cell, distributions in self.package_sets
            ],
            "model": {
                "identifier": self.model_identifier,
                "revision": self.model_revision,
                "tree_sha256": self.model_tree_sha256,
                "files": [
                    {"path": path, "bytes": size, "sha256": digest}
                    for path, size, digest in self.model_files
                ],
            },
            "fixtures": [
                {"filename": name, "bytes": size, "sha256": digest}
                for name, size, digest in self.fixtures
            ],
            "consumer_sha256": self.consumer_sha256,
            "retained_inputs_sha256": self.retained_inputs_sha256,
            "estimated_temporary_disk_bytes": self.estimated_temporary_disk_bytes,
            "temporary_disk_estimate_method": self.temporary_disk_estimate_method,
            "deny_network_method": self.deny_network_method,
            "cleanup_owner": self.cleanup_owner,
            "direct_audio_footprint_bytes": self.direct_audio_footprint_bytes,
            "direct_audio_footprint_budget_mode": self.direct_audio_footprint_budget_mode,
        }


@dataclass(frozen=True)
class CommandCall:
    step: str
    argv: tuple[str, ...]
    env: Mapping[str, str]
    cwd: Path
    timeout_seconds: float = _COMMAND_TIMEOUT_SECONDS
    footprint_observation: bool = False


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    supervision: Mapping[str, object] | None = None


class CommandRunner(Protocol):
    def run(self, call: CommandCall) -> CommandResult: ...


class _RealRunner:
    def __init__(self, config: DirectAudioProofConfig) -> None:
        self._config = config
        self.observations: list[dict[str, object]] = []

    def run(self, call: CommandCall) -> CommandResult:
        footprint = (
            self._config.direct_audio_footprint_bytes
            if call.footprint_observation
            else None
        )
        profile = dependency_authority.BoundedProfile(
            wall_seconds=call.timeout_seconds,
            stdout_bytes=_MAX_STDOUT_BYTES,
            stderr_bytes=_MAX_STDERR_BYTES,
            footprint_bytes=footprint,
            footprint_budget_mode=(
                self._config.direct_audio_footprint_budget_mode
                if footprint is not None
                else "absolute"
            ),
            output_bytes=_MAX_STDOUT_BYTES,
        )
        try:
            result = dependency_authority._run_bounded(  # pyright: ignore[reportPrivateUsage]
                list(call.argv),
                env=dict(call.env),
                cwd=call.cwd,
                profile=profile,
            )
        except dependency_authority.ReceiptError as error:
            raise DirectAudioDeploymentProofError("bounded_execution_failed") from error
        if result.supervision is not None:
            self.observations.append({"step": call.step, **dict(result.supervision)})
        return CommandResult(
            result.returncode,
            result.stdout,
            result.stderr,
            result.supervision,
        )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _wheel_unpacked_bytes(value: bytes) -> int:
    try:
        with zipfile.ZipFile(io.BytesIO(value)) as archive:
            total = sum(item.file_size for item in archive.infolist())
    except zipfile.BadZipFile as error:
        raise DirectAudioDeploymentProofError("candidate_artifact_invalid") from error
    if total <= 0:
        raise DirectAudioDeploymentProofError("candidate_artifact_invalid")
    return total


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def _read_regular(path: Path) -> bytes:
    try:
        return dependency_authority._read_regular(path)  # pyright: ignore[reportPrivateUsage]
    except dependency_authority.ReceiptError as error:
        raise DirectAudioDeploymentProofError("input_authority_invalid") from error


def _wheel_metadata(value: bytes) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(io.BytesIO(value)) as archive:
            metadata_names = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise DirectAudioDeploymentProofError("candidate_artifact_invalid")
            metadata = archive.read(metadata_names[0]).decode("utf-8", errors="strict")
    except (OSError, UnicodeError, zipfile.BadZipFile, KeyError) as error:
        raise DirectAudioDeploymentProofError("candidate_artifact_invalid") from error
    fields: dict[str, str] = {}
    for line in metadata.splitlines():
        if ": " in line:
            key, item = line.split(": ", 1)
            if key in {"Name", "Version"}:
                fields[key] = item
    if fields.get("Name") != "multimodal-knowledge-engine" or not fields.get("Version"):
        raise DirectAudioDeploymentProofError("candidate_artifact_invalid")
    return fields["Name"], fields["Version"]


def _receipt_payload(path: Path) -> tuple[dict[str, object], bytes]:
    value = _read_regular(path)
    try:
        decoded = json.loads(value.decode("ascii", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DirectAudioDeploymentProofError("dependency_authority_invalid") from error
    if not isinstance(decoded, dict):
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    payload = cast(dict[str, object], decoded)
    validation = dependency_authority.validate_committed_receipt(payload)
    if validation.get("status") != "passed":
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    receipt_digest = payload.get("receipt_sha256")
    if not isinstance(receipt_digest, str) or _DIGEST_RE.fullmatch(receipt_digest) is None:
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    return payload, value


def _expected_wheel_manifest(payload: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    raw = payload.get("wheel_inventory")
    if not isinstance(raw, list):
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    result: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        row = dict(cast(dict[str, object], item))
        row.pop("artifact_scope", None)
        result.append(row)
    return tuple(result)


def _observed_wheel_manifest(path: Path) -> tuple[dict[str, object], ...]:
    try:
        observed = dependency_authority.build_wheelhouse_manifest(path)
    except dependency_authority.ReceiptError as error:
        raise DirectAudioDeploymentProofError("dependency_authority_invalid") from error
    return tuple(
        {
            "filename": item.filename,
            "distribution": item.distribution,
            "version": item.version,
            "build": item.build,
            "python_tags": list(item.python_tags),
            "abi_tags": list(item.abi_tags),
            "platform_tags": list(item.platform_tags),
            "bytes": item.bytes,
            "sha256": item.sha256,
        }
        for item in observed
    )


def _receipt_cell_digest(payload: Mapping[str, object], field: str) -> str:
    raw_cells = payload.get("cells")
    if not isinstance(raw_cells, list) or len(raw_cells) != 2:
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    values: set[str] = set()
    names: set[str] = set()
    for raw in raw_cells:
        if not isinstance(raw, dict):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        cell = cast(dict[str, object], raw)
        name = cell.get("cell")
        pip = cell.get("pip")
        if not isinstance(name, str) or not isinstance(pip, dict):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        staging = cast(dict[str, object], pip).get("staging")
        if not isinstance(staging, dict):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        value = cast(dict[str, object], staging).get(field)
        if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        names.add(name)
        values.add(value)
    if names != {"3.12", "3.13"} or len(values) != 1:
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    return next(iter(values))


def _model_snapshot_root(model_root: Path) -> Path:
    return model_root / _MODEL_DIRECTORY / "snapshots" / DEFAULT_MODEL_REVISION


def _tree_manifest(root: Path, *, authority_root: Path) -> tuple[tuple[str, int, str], ...]:
    try:
        authority = authority_root.resolve(strict=True)
        snapshot = root.resolve(strict=True)
        snapshot.relative_to(authority)
    except (OSError, ValueError) as error:
        raise DirectAudioDeploymentProofError("model_authority_invalid") from error
    files: list[tuple[str, int, str]] = []
    try:
        paths = sorted(root.rglob("*"), key=lambda item: item.as_posix())
    except OSError as error:
        raise DirectAudioDeploymentProofError("model_authority_invalid") from error
    for logical in paths:
        if logical.is_dir():
            continue
        try:
            before = logical.lstat()
            resolved = logical.resolve(strict=True)
            resolved.relative_to(authority)
            value = _read_regular(resolved)
            after = logical.lstat()
        except (OSError, ValueError, DirectAudioDeploymentProofError) as error:
            raise DirectAudioDeploymentProofError("model_authority_invalid") from error
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity:
            raise DirectAudioDeploymentProofError("model_authority_invalid")
        files.append((logical.relative_to(root).as_posix(), len(value), _sha256(value)))
    names = {name for name, _, _ in files}
    required = {"README.md", "config.json", "model.bin", "tokenizer.json"}
    if not required <= names or not any(name.startswith("vocabulary.") for name in names):
        raise DirectAudioDeploymentProofError("model_authority_invalid")
    try:
        model_card = _read_regular((root / "README.md").resolve(strict=True)).decode(
            "utf-8", errors="strict"
        )
    except (OSError, UnicodeDecodeError) as error:
        raise DirectAudioDeploymentProofError("model_authority_invalid") from error
    if "\nlicense: mit\n" not in model_card:
        raise DirectAudioDeploymentProofError("model_authority_invalid")
    return tuple(files)


def _fixture_manifest(
    root: Path, payload: Mapping[str, object]
) -> tuple[tuple[str, int, str], ...]:
    raw = payload.get("fixtures")
    if not isinstance(raw, list):
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    expected = {
        cast(str, item.get("filename")): (item.get("bytes"), item.get("sha256"))
        for item in raw
        if isinstance(item, dict)
    }
    result: list[tuple[str, int, str]] = []
    for name in _FIXTURES:
        value = _read_regular(root / name)
        identity = (len(value), _sha256(value))
        if expected.get(name) != identity:
            raise DirectAudioDeploymentProofError("input_authority_invalid")
        result.append((name, *identity))
    return tuple(result)


def _interpreter_manifest(
    config: DirectAudioProofConfig,
    payload: Mapping[str, object],
) -> tuple[tuple[str, str, str], ...]:
    raw_cells = payload.get("cells")
    if not isinstance(raw_cells, list):
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    expected: dict[str, tuple[str, str]] = {}
    for raw in raw_cells:
        if not isinstance(raw, dict):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        cell = cast(dict[str, object], raw)
        name = cell.get("cell")
        interpreter = cell.get("interpreter")
        if not isinstance(name, str) or not isinstance(interpreter, dict):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        identity = cast(dict[str, object], interpreter)
        version = identity.get("python_version")
        digest = identity.get("executable_sha256")
        if (
            not isinstance(version, str)
            or not isinstance(digest, str)
            or _DIGEST_RE.fullmatch(digest) is None
        ):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        expected[name] = (version, digest)
    if set(expected) != {"3.12", "3.13"}:
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    result: list[tuple[str, str, str]] = []
    supported = dependency_authority._supported_cells()  # pyright: ignore[reportPrivateUsage]
    for cell, path in zip(supported, config.interpreters, strict=True):
        try:
            observed, _, _ = dependency_authority._probe_target_interpreter(  # pyright: ignore[reportPrivateUsage]
                path, cell
            )
        except dependency_authority.ReceiptError as error:
            raise DirectAudioDeploymentProofError("input_authority_invalid") from error
        version, expected_digest = expected[cell.version]
        raw_cells = cast(list[object], payload["cells"])
        expected_identity = next(
            cast(dict[str, object], item)["interpreter"]
            for item in raw_cells
            if cast(dict[str, object], item).get("cell") == cell.version
        )
        if observed != expected_identity or observed["executable_sha256"] != expected_digest:
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        result.append((cell.version, version, expected_digest))
    return tuple(result)


def _package_sets(
    payload: Mapping[str, object], candidate_version: str
) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    raw_cells = payload.get("cells")
    if not isinstance(raw_cells, list):
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    result: list[tuple[str, tuple[tuple[str, str], ...]]] = []
    for raw in raw_cells:
        if not isinstance(raw, dict):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        cell = cast(dict[str, object], raw)
        name = cell.get("cell")
        raw_distributions = cell.get("installed_distributions")
        if not isinstance(name, str) or not isinstance(raw_distributions, list):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        distributions: list[tuple[str, str]] = []
        for item in raw_distributions:
            if not isinstance(item, dict):
                raise DirectAudioDeploymentProofError("dependency_authority_invalid")
            distribution = item.get("distribution")
            version = item.get("version")
            if not isinstance(distribution, str) or not isinstance(version, str):
                raise DirectAudioDeploymentProofError("dependency_authority_invalid")
            distributions.append((distribution, version))
        distributions.append(("multimodal-knowledge-engine", candidate_version))
        ordered = tuple(sorted(distributions))
        if len(set(ordered)) != len(ordered):
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        result.append((name, ordered))
    ordered_cells = tuple(sorted(result))
    if {name for name, _ in ordered_cells} != {"3.12", "3.13"}:
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    return ordered_cells


def _validate_wheel_compatibility(
    constraints: bytes,
    observed_wheels: tuple[dict[str, object], ...],
    payload: Mapping[str, object],
) -> None:
    try:
        _, _, requirements_by_cell = dependency_authority._parse_constraints(  # pyright: ignore[reportPrivateUsage]
            constraints
        )
        entries = tuple(
            dependency_authority.WheelEntry(
                cast(str, item["filename"]),
                cast(str, item["distribution"]),
                cast(str, item["version"]),
                cast(str | None, item["build"]),
                tuple(cast(list[str], item["python_tags"])),
                tuple(cast(list[str], item["abi_tags"])),
                tuple(cast(list[str], item["platform_tags"])),
                cast(int, item["bytes"]),
                cast(str, item["sha256"]),
            )
            for item in observed_wheels
        )
        raw_cells = cast(list[object], payload["cells"])
        if len(raw_cells) != 2:
            raise DirectAudioDeploymentProofError("dependency_authority_invalid")
        cells = dependency_authority._supported_cells()  # pyright: ignore[reportPrivateUsage]
        dependency_authority.resolve_wheels_by_cell(
            entries,
            requirements_by_cell,
            cells,
        )
    except (KeyError, TypeError, dependency_authority.ReceiptError) as error:
        raise DirectAudioDeploymentProofError("dependency_authority_invalid") from error


def _validate_inputs(config: DirectAudioProofConfig) -> AuthorizationManifest:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise DirectAudioDeploymentProofError("unsupported_platform")
    sandbox = Path("/usr/bin/sandbox-exec")
    try:
        sandbox_stat = sandbox.stat()
    except OSError as error:
        raise DirectAudioDeploymentProofError("network_boundary_failed") from error
    if not stat.S_ISREG(sandbox_stat.st_mode) or not os.access(sandbox, os.X_OK):
        raise DirectAudioDeploymentProofError("network_boundary_failed")
    wheel = _read_regular(config.mke_wheel)
    _, candidate_version = _wheel_metadata(wheel)
    payload, receipt_bytes = _receipt_payload(config.dependency_receipt)
    constraints = _read_regular(config.constraints)
    constraints_sha = _sha256(constraints)
    if constraints_sha != _receipt_cell_digest(payload, "constraints_sha256"):
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    expected_wheels = _expected_wheel_manifest(payload)
    observed_wheels = _observed_wheel_manifest(config.wheelhouse)
    if observed_wheels != expected_wheels:
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    _validate_wheel_compatibility(constraints, observed_wheels, payload)
    wheelhouse_sha = _sha256(_canonical(list(observed_wheels)))
    if wheelhouse_sha != _receipt_cell_digest(payload, "wheelhouse_manifest_sha256"):
        raise DirectAudioDeploymentProofError("dependency_authority_invalid")
    model_files = _tree_manifest(
        _model_snapshot_root(config.model_root),
        authority_root=config.model_root,
    )
    fixtures = _fixture_manifest(config.fixture_root, payload)
    interpreters = _interpreter_manifest(config, payload)
    package_sets = _package_sets(payload, candidate_version)
    consumer_path = Path(__file__).resolve().parent / "compiled_library_export_consumer_v2.py"
    consumer_sha = _sha256(_read_regular(consumer_path))
    retained = {
        "mke_wheel": _sha256(wheel),
        "dependency_receipt": _sha256(receipt_bytes),
        "constraints": constraints_sha,
        "wheelhouse": wheelhouse_sha,
        "model_tree": _sha256(_canonical(model_files)),
        "fixtures": fixtures,
        "interpreters": interpreters,
        "package_sets": package_sets,
        "consumer": consumer_sha,
    }
    receipt_payload_sha = cast(str, payload["receipt_sha256"])
    wheelhouse_bytes = sum(cast(int, item["bytes"]) for item in observed_wheels)
    wheelhouse_unpacked = sum(
        _wheel_unpacked_bytes(_read_regular(config.wheelhouse / cast(str, item["filename"])))
        for item in observed_wheels
    )
    fixture_bytes = sum(size for _, size, _ in fixtures)
    database_allowance = 3 * 128 * 1024 * 1024
    export_allowance = 4 * 64 * 1024 * 1024
    bounded_output_allowance = 8 * _MAX_STDOUT_BYTES
    per_cell_temp = (
        wheelhouse_bytes
        + len(wheel)
        + wheelhouse_unpacked
        + _wheel_unpacked_bytes(wheel)
        + fixture_bytes
        + database_allowance
        + export_allowance
        + bounded_output_allowance
    )
    estimated_temp = 2 * per_cell_temp
    return AuthorizationManifest(
        mke_wheel_sha256=_sha256(wheel),
        mke_wheel_bytes=len(wheel),
        dependency_receipt_sha256=_sha256(receipt_bytes),
        dependency_receipt_payload_sha256=receipt_payload_sha,
        wheelhouse_manifest_sha256=wheelhouse_sha,
        constraints_sha256=constraints_sha,
        interpreters=interpreters,
        package_sets=package_sets,
        model_identifier=_MODEL_IDENTIFIER,
        model_revision=DEFAULT_MODEL_REVISION,
        model_tree_sha256=retained["model_tree"],
        model_files=model_files,
        consumer_sha256=consumer_sha,
        fixtures=fixtures,
        retained_inputs_sha256=_sha256(_canonical(retained)),
        estimated_temporary_disk_bytes=estimated_temp,
        temporary_disk_estimate_method=(
            "two_cells_staged_and_unpacked_wheels_plus_fixed_fixture_copies_"
            "plus_three_database_and_four_export_limit_allowances_plus_bounded_outputs"
        ),
        deny_network_method="darwin-sandbox-deny-network",
        cleanup_owner="call_owned_recursive_removal",
        direct_audio_footprint_bytes=config.direct_audio_footprint_bytes,
        direct_audio_footprint_budget_mode=config.direct_audio_footprint_budget_mode,
    )


def _clean_environment(root: Path) -> dict[str, str]:
    return {
        "HOME": str(root / "home"),
        "TMPDIR": str(root / "tmp"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "PIP_CONFIG_FILE": os.devnull,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }


def _pip_environment(root: Path) -> dict[str, str]:
    return {
        "HOME": str(root / "home"),
        "PIP_CONFIG_FILE": os.devnull,
        "TMPDIR": str(root / "tmp"),
    }


def _json_result(result: CommandResult, code: str) -> dict[str, object]:
    if result.returncode != 0 or result.stderr:
        raise DirectAudioDeploymentProofError(code)
    try:
        payload = json.loads(result.stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DirectAudioDeploymentProofError(code) from error
    if not isinstance(payload, dict):
        raise DirectAudioDeploymentProofError(code)
    return cast(dict[str, object], payload)


def _run_ok(runner: CommandRunner, call: CommandCall, code: str) -> None:
    result = runner.run(call)
    if result.returncode != 0:
        raise DirectAudioDeploymentProofError(code)


def _validate_installed_candidate(
    *,
    venv: Path,
    identity: Mapping[str, object],
    wheel_value: bytes,
    expected_packages: tuple[tuple[str, str], ...],
) -> None:
    raw_mke = identity.get("mke_file")
    raw_python = identity.get("python")
    raw_distributions = identity.get("distributions")
    if (
        not isinstance(raw_mke, str)
        or not isinstance(raw_python, str)
        or not isinstance(raw_distributions, list)
    ):
        raise DirectAudioDeploymentProofError("installed_identity_failed")
    try:
        resolved_venv = venv.resolve(strict=True)
        mke_file = Path(raw_mke).resolve(strict=True)
        python = Path(raw_python).resolve(strict=True)
        mke_file.relative_to(resolved_venv)
        python.relative_to(resolved_venv)
    except (OSError, ValueError) as error:
        raise DirectAudioDeploymentProofError("installed_identity_failed") from error
    distributions: list[tuple[str, str]] = []
    for raw in raw_distributions:
        if (
            not isinstance(raw, list)
            or len(raw) != 2
            or not all(isinstance(item, str) for item in raw)
        ):
            raise DirectAudioDeploymentProofError("installed_identity_failed")
        distributions.append((cast(str, raw[0]), cast(str, raw[1])))
    if tuple(distributions) != expected_packages:
        raise DirectAudioDeploymentProofError("installed_identity_failed")
    site_packages = mke_file.parent.parent
    try:
        with zipfile.ZipFile(io.BytesIO(wheel_value)) as archive:
            records = [name for name in archive.namelist() if name.endswith(".dist-info/RECORD")]
            if len(records) != 1:
                raise DirectAudioDeploymentProofError("installed_identity_failed")
            record_rows = {
                row[0]: (row[1], row[2])
                for row in csv.reader(
                    io.StringIO(archive.read(records[0]).decode("utf-8", errors="strict"))
                )
                if len(row) == 3
            }
            dist_info_prefix = records[0].rsplit("/", 1)[0] + "/"
            installed_record = _read_regular(site_packages / records[0]).decode(
                "utf-8", errors="strict"
            )
            installed_rows = {
                row[0]: (row[1], row[2])
                for row in csv.reader(io.StringIO(installed_record))
                if len(row) == 3
            }
            installed_files = [
                name
                for name in archive.namelist()
                if (
                    name.startswith("mke/") or name.startswith(dist_info_prefix)
                )
                and name != records[0]
                and not name.endswith("/")
            ]
            if not installed_files:
                raise DirectAudioDeploymentProofError("installed_identity_failed")
            for name in installed_files:
                expected = archive.read(name)
                observed = _read_regular(site_packages / name)
                raw_digest = hashlib.sha256(expected).digest()
                digest = base64.urlsafe_b64encode(raw_digest).decode().rstrip("=")
                if (
                    observed != expected
                    or record_rows.get(name) != (f"sha256={digest}", str(len(expected)))
                    or installed_rows.get(name)
                    != (f"sha256={digest}", str(len(expected)))
                ):
                    raise DirectAudioDeploymentProofError("installed_identity_failed")
    except (OSError, UnicodeError, zipfile.BadZipFile, KeyError) as error:
        raise DirectAudioDeploymentProofError("installed_identity_failed") from error


def _sandbox(argv: Sequence[str]) -> tuple[str, ...]:
    return ("/usr/bin/sandbox-exec", "-p", _DENY_NETWORK_PROFILE, *argv)


def _run_json(runner: CommandRunner, call: CommandCall, code: str) -> dict[str, object]:
    return _json_result(runner.run(call), code)


def _report_is_valid(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    report = cast(dict[str, object], value)
    required_strings = {
        "provider": "faster-whisper",
        "model": "small",
        "model_revision": DEFAULT_MODEL_REVISION,
        "model_source": "cache",
    }
    if any(report.get(key) != expected for key, expected in required_strings.items()):
        return False
    for field in (
        "library_version",
        "device",
        "compute_type",
        "language",
        "detected_language",
    ):
        item = report.get(field)
        if not isinstance(item, str) or _SAFE_TOKEN_RE.fullmatch(item) is None:
            return False
    return (
        type(report.get("media_duration_ms")) is int
        and cast(int, report["media_duration_ms"]) > 0
        and type(report.get("transcription_duration_ms")) is int
        and cast(int, report["transcription_duration_ms"]) >= 0
        and type(report.get("segment_count")) is int
        and cast(int, report["segment_count"]) > 0
    )


def validate_product_result(payload: Mapping[str, object], *, fixture: str) -> None:
    if (
        payload.get("status") != "passed"
        or payload.get("run_state") != "published"
        or payload.get("search_keyword_matched") is not True
        or payload.get("ask_status") != "evidence_found"
        or not _report_is_valid(payload.get("transcript_intake_report"))
    ):
        raise DirectAudioDeploymentProofError("product_path_failed")
    digest = payload.get("source_sha256")
    if not isinstance(digest, str) or _DIGEST_RE.fullmatch(digest) is None:
        raise DirectAudioDeploymentProofError("product_path_failed")
    raw = payload.get("evidence_ref")
    if not isinstance(raw, dict):
        raise DirectAudioDeploymentProofError("product_path_failed")
    evidence = cast(dict[str, object], raw)
    run_id = payload.get("run_id")
    locator = evidence.get("locator")
    report = cast(dict[str, object], payload["transcript_intake_report"])
    if not isinstance(locator, dict):
        raise DirectAudioDeploymentProofError("product_path_failed")
    location = cast(dict[str, object], locator)
    valid = (
        evidence.get("schema_version") == "mke.evidence_ref.v1"
        and isinstance(evidence.get("evidence_id"), str)
        and _EVIDENCE_ID_RE.fullmatch(cast(str, evidence["evidence_id"])) is not None
        and isinstance(evidence.get("source_id"), str)
        and _SOURCE_ID_RE.fullmatch(cast(str, evidence["source_id"])) is not None
        and isinstance(evidence.get("publication_id"), str)
        and _PUBLICATION_ID_RE.fullmatch(cast(str, evidence["publication_id"])) is not None
        and isinstance(evidence.get("run_id"), str)
        and _RUN_ID_RE.fullmatch(cast(str, evidence["run_id"])) is not None
        and evidence.get("run_id") == run_id
        and isinstance(evidence.get("content_fingerprint"), str)
        and evidence.get("content_fingerprint") == f"sha256:{digest}"
        and type(evidence.get("publication_revision")) is int
        and cast(int, evidence["publication_revision"]) > 0
        and location.get("kind") == "timestamp_ms"
        and type(location.get("start")) is int
        and type(location.get("end")) is int
        and 0 <= cast(int, location["start"]) < cast(int, location["end"])
        <= cast(int, report["media_duration_ms"])
        and isinstance(evidence.get("text"), str)
        and "traceable" in cast(str, evidence["text"]).casefold()
    )
    if not valid or payload.get("fixture") not in {fixture, f"direct-audio.{fixture}"}:
        raise DirectAudioDeploymentProofError("product_path_failed")


def _probe_call(path: Path, version: str, root: Path, env: Mapping[str, str]) -> CommandCall:
    source = (
        "import json,sys; "
        "print(json.dumps({'python_version':"
        "f'{sys.version_info.major}.{sys.version_info.minor}'}))"
    )
    return CommandCall(
        f"probe-python-{version}",
        (str(path), "-I", "-B", "-c", source),
        env,
        root,
    )


def _runtime_args(config: DirectAudioProofConfig) -> tuple[str, ...]:
    return (
        "--model",
        "small",
        "--model-revision",
        DEFAULT_MODEL_REVISION,
        "--device",
        "cpu",
        "--compute-type",
        "int8",
        "--language",
        "auto",
        "--model-cache",
        str(config.model_root),
        "--transcription-timeout-seconds",
        str(config.provider_timeout_seconds),
        "--direct-audio-footprint-bytes",
        str(config.direct_audio_footprint_bytes),
        "--direct-audio-footprint-budget-mode",
        config.direct_audio_footprint_budget_mode,
    )


def _product_call(
    *,
    lane: str,
    suffix: str,
    python: Path,
    mke: Path,
    fixture: Path,
    db: Path,
    root: Path,
    env: Mapping[str, str],
    config: DirectAudioProofConfig,
) -> CommandCall:
    if lane == "mcp":
        fixture_fingerprint = "sha256:" + _sha256(_read_regular(fixture))
        argv = (
            str(python),
            "-I",
            "-B",
            "-m",
            "mke.proof.mcp_deployment_client",
            "--mke-command",
            str(mke),
            "--fixture-name",
            fixture.name,
            "--db",
            str(db),
            "--allowed-root",
            str(fixture.parent),
            "--model-revision",
            DEFAULT_MODEL_REVISION,
            "--model-cache",
            str(config.model_root),
            "--transcription-timeout-seconds",
            str(config.provider_timeout_seconds),
            "--direct-audio-footprint-bytes",
            str(config.direct_audio_footprint_bytes),
            "--direct-audio-footprint-budget-mode",
            config.direct_audio_footprint_budget_mode,
            "--search-query",
            "traceable",
            "--ask-question",
            "traceable publication",
            "--expected-keyword",
            "traceable",
            "--expected-content-fingerprint",
            fixture_fingerprint,
            "--portable-evidence",
        )
    else:
        helper = root / f"{lane}-product-path.py"
        argv = (
            str(python),
            "-I",
            "-B",
            str(helper),
            "--lane",
            lane,
            "--mke-command",
            str(mke),
            "--fixture",
            str(fixture),
            "--db",
            str(db),
            *_runtime_args(config),
        )
    return CommandCall(
        f"{lane}-{suffix}",
        _sandbox(argv),
        env,
        root,
        timeout_seconds=config.provider_timeout_seconds,
        footprint_observation=True,
    )


def _stage_cell_impl(
    config: DirectAudioProofConfig,
    authorization: AuthorizationManifest,
    root: Path,
    version: str,
) -> tuple[Path, Path, Path]:
    cell = root / f"python-{version}"
    stage = cell / "stage"
    stage_wheels = stage / "wheelhouse"
    allowed = cell / "allowed"
    for directory in (stage_wheels, allowed, cell / "home", cell / "tmp", cell / "cache"):
        directory.mkdir(parents=True, mode=0o700)
    source_manifest = _observed_wheel_manifest(config.wheelhouse)
    if _sha256(_canonical(list(source_manifest))) != authorization.wheelhouse_manifest_sha256:
        raise DirectAudioDeploymentProofError("input_identity_drift")
    for path in sorted(config.wheelhouse.iterdir(), key=lambda item: item.name):
        (stage_wheels / path.name).write_bytes(_read_regular(path))
    if _observed_wheel_manifest(stage_wheels) != source_manifest:
        raise DirectAudioDeploymentProofError("input_identity_drift")
    wheel_value = _read_regular(config.mke_wheel)
    if _sha256(wheel_value) != authorization.mke_wheel_sha256:
        raise DirectAudioDeploymentProofError("input_identity_drift")
    (stage_wheels / config.mke_wheel.name).write_bytes(wheel_value)
    constraints_value = _read_regular(config.constraints)
    if _sha256(constraints_value) != authorization.constraints_sha256:
        raise DirectAudioDeploymentProofError("input_identity_drift")
    (stage / "constraints.txt").write_bytes(constraints_value)
    (stage / "root-requirements.txt").write_text(
        "multimodal-knowledge-engine[transcription] @ "
        f"{(stage_wheels / config.mke_wheel.name).as_uri()} "
        f"--hash=sha256:{_sha256(wheel_value)}\n",
        encoding="ascii",
    )
    for name in _FIXTURES:
        value = _read_regular(config.fixture_root / name)
        expected = {filename: digest for filename, _, digest in authorization.fixtures}
        if _sha256(value) != expected[name]:
            raise DirectAudioDeploymentProofError("input_identity_drift")
        (allowed / name).write_bytes(value)
    for lane in ("python", "cli"):
        (cell / f"{lane}-product-path.py").write_text(
            _PRODUCT_HELPER_SOURCE + "\n",
            encoding="utf-8",
        )
    consumer = Path(__file__).resolve().parent / "compiled_library_export_consumer_v2.py"
    consumer_value = _read_regular(consumer)
    if _sha256(consumer_value) != authorization.consumer_sha256:
        raise DirectAudioDeploymentProofError("input_identity_drift")
    (cell / "compiled-library-consumer-v2.py").write_bytes(consumer_value)
    return cell, stage, allowed


def _stage_cell(
    config: DirectAudioProofConfig,
    authorization: AuthorizationManifest,
    root: Path,
    version: str,
) -> tuple[Path, Path, Path]:
    try:
        return _stage_cell_impl(config, authorization, root, version)
    except OSError as error:
        raise DirectAudioDeploymentProofError("runtime_path_invalid") from error


@contextmanager
def _owned_temporary_directory() -> Iterator[str]:
    temporary = tempfile.TemporaryDirectory(prefix="mke-direct-audio-deployment-")
    try:
        raw_root = temporary.__enter__()
    except OSError as error:
        raise DirectAudioDeploymentProofError("runtime_path_invalid") from error
    try:
        yield raw_root
    finally:
        try:
            temporary.__exit__(None, None, None)
        except OSError as error:
            raise DirectAudioDeploymentProofError("cleanup_failed") from error


def _bound_interpreter_snapshots(
    config: DirectAudioProofConfig,
    authorization: AuthorizationManifest,
) -> tuple[dependency_authority.ExecutableSnapshot, ...]:
    expected = {cell: digest for cell, _, digest in authorization.interpreters}
    result: list[dependency_authority.ExecutableSnapshot] = []
    for cell, path in zip(("3.12", "3.13"), config.interpreters, strict=True):
        try:
            snapshot = dependency_authority._snapshot_executable(  # pyright: ignore[reportPrivateUsage]
                path
            )
        except dependency_authority.ReceiptError as error:
            raise DirectAudioDeploymentProofError("interpreter_identity_drift") from error
        if snapshot.sha256 != expected[cell]:
            raise DirectAudioDeploymentProofError("interpreter_identity_drift")
        result.append(snapshot)
    return tuple(result)


def _require_interpreter_snapshot(
    path: Path,
    expected: dependency_authority.ExecutableSnapshot,
) -> None:
    try:
        observed = dependency_authority._snapshot_executable(  # pyright: ignore[reportPrivateUsage]
            path
        )
    except dependency_authority.ReceiptError as error:
        raise DirectAudioDeploymentProofError("interpreter_identity_drift") from error
    if observed != expected:
        raise DirectAudioDeploymentProofError("interpreter_identity_drift")


def _network_canary(
    runner: CommandRunner,
    *,
    python: Path,
    env: Mapping[str, str],
    cell: Path,
) -> dict[str, object]:
    listener: socket.socket | None = None
    port = 9
    if isinstance(runner, _RealRunner):
        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = cast(int, listener.getsockname()[1])
        except OSError as error:
            if listener is not None:
                listener.close()
            raise DirectAudioDeploymentProofError("network_boundary_failed") from error
    source = (
        "import json,socket\n"
        f"try: socket.create_connection(('127.0.0.1',{port}),.5)\n"
        "except OSError: print(json.dumps({'status':'blocked'}))\n"
        "else: print(json.dumps({'status':'unexpected_success'}))"
    )
    try:
        return _run_json(
            runner,
            CommandCall(
                "network-canary",
                _sandbox((str(python), "-I", "-B", "-c", source)),
                env,
                cell,
            ),
            "network_boundary_failed",
        )
    finally:
        if listener is not None:
            listener.close()


def _export_tree_digest(root: Path) -> str:
    rows: list[tuple[str, int, str]] = []
    try:
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_dir():
                continue
            value = _read_regular(path)
            rows.append((path.relative_to(root).as_posix(), len(value), _sha256(value)))
    except OSError as error:
        raise DirectAudioDeploymentProofError("export_failed") from error
    if not rows:
        raise DirectAudioDeploymentProofError("export_failed")
    return _sha256(_canonical(rows))


def _validate_staged_inputs(
    *,
    config: DirectAudioProofConfig,
    authorization: AuthorizationManifest,
    stage: Path,
) -> None:
    observed = list(_observed_wheel_manifest(stage / "wheelhouse"))
    candidate = [item for item in observed if item["filename"] == config.mke_wheel.name]
    if (
        len(candidate) != 1
        or candidate[0]["sha256"] != authorization.mke_wheel_sha256
    ):
        raise DirectAudioDeploymentProofError("pip_input_identity_drift")
    external = [item for item in observed if item["filename"] != config.mke_wheel.name]
    if _sha256(_canonical(external)) != authorization.wheelhouse_manifest_sha256:
        raise DirectAudioDeploymentProofError("pip_input_identity_drift")
    constraints = _read_regular(stage / "constraints.txt")
    requirements = _read_regular(stage / "root-requirements.txt")
    if (
        _sha256(constraints) != authorization.constraints_sha256
        or authorization.mke_wheel_sha256.encode("ascii") not in requirements
    ):
        raise DirectAudioDeploymentProofError("pip_input_identity_drift")


def _run_direct_audio_deployment_proof_impl(
    config: DirectAudioProofConfig,
    authorization: AuthorizationManifest,
    runner: CommandRunner,
    interpreter_snapshots: tuple[dependency_authority.ExecutableSnapshot, ...] | None = None,
) -> dict[str, object]:
    cells: list[dict[str, object]] = []
    with _owned_temporary_directory() as raw_root:
        runtime_root = Path(raw_root).resolve()
        if isinstance(runner, _RealRunner):
            try:
                free_disk = shutil.disk_usage(runtime_root).free
            except OSError as error:
                raise DirectAudioDeploymentProofError("runtime_path_invalid") from error
            if free_disk < authorization.estimated_temporary_disk_bytes:
                raise DirectAudioDeploymentProofError("insufficient_temporary_disk")
        for index, (version, interpreter) in enumerate(
            zip(("3.12", "3.13"), config.interpreters, strict=True)
        ):
            supervision_start = (
                len(runner.observations) if isinstance(runner, _RealRunner) else 0
            )
            snapshot = interpreter_snapshots[index] if interpreter_snapshots is not None else None
            execution_target = snapshot.resolved if snapshot is not None else interpreter
            if snapshot is not None:
                _require_interpreter_snapshot(interpreter, snapshot)
            cell, stage, allowed = _stage_cell(config, authorization, runtime_root, version)
            env = _clean_environment(cell)
            pip_env = _pip_environment(cell)
            probe = _run_json(
                runner,
                _probe_call(execution_target, version, cell, env),
                "interpreter_probe_failed",
            )
            if probe.get("python_version") != version:
                raise DirectAudioDeploymentProofError("interpreter_probe_failed")
            if snapshot is not None:
                _require_interpreter_snapshot(interpreter, snapshot)
            venv = cell / "venv"
            _run_ok(
                runner,
                CommandCall(
                    f"create-venv-{version}",
                    (
                        str(execution_target),
                        "-I",
                        "-B",
                        "-m",
                        "venv",
                        "--without-pip",
                        "--copies",
                        str(venv),
                    ),
                    pip_env,
                    cell,
                ),
                "environment_create_failed",
            )
            if snapshot is not None:
                _require_interpreter_snapshot(interpreter, snapshot)
            dependency_cell = dependency_authority._supported_cells()[index]  # pyright: ignore[reportPrivateUsage]
            if isinstance(runner, _RealRunner):
                try:
                    dependency_authority._prepare_darwin_copied_runtime(  # pyright: ignore[reportPrivateUsage]
                        base_executable=execution_target,
                        venv=venv,
                        cell=dependency_cell,
                    )
                except dependency_authority.ReceiptError as error:
                    raise DirectAudioDeploymentProofError(
                        "environment_create_failed"
                    ) from error
            python = venv / "bin" / f"python{version}"
            mke = venv / "bin" / "mke"
            venv_initial: dependency_authority.VenvAuthority | None = None
            venv_authority: dependency_authority.VenvAuthority | None = None
            if isinstance(runner, _RealRunner):
                try:
                    venv_initial = dependency_authority._snapshot_venv_authority(  # pyright: ignore[reportPrivateUsage]
                        venv=venv,
                        executable=python,
                        call_root=cell,
                        cell=dependency_cell,
                    )
                    if (
                        snapshot is not None
                        and venv_initial.executable.target_file_identity
                        == snapshot.target_file_identity
                    ):
                        raise DirectAudioDeploymentProofError("installed_identity_failed")
                    venv_probe, _, venv_target = dependency_authority._probe_target_interpreter(  # pyright: ignore[reportPrivateUsage]
                        python,
                        dependency_cell,
                    )
                except dependency_authority.ReceiptError as error:
                    raise DirectAudioDeploymentProofError(
                        "installed_identity_failed"
                    ) from error
                expected_interpreters = {
                    cell_name: (python_version, digest)
                    for cell_name, python_version, digest in authorization.interpreters
                }
                expected_version, expected_digest = expected_interpreters[version]
                if (
                    venv_target != venv_initial.executable.resolved
                    or venv_probe.get("python_version") != expected_version
                    or venv_probe.get("executable_sha256") != expected_digest
                ):
                    raise DirectAudioDeploymentProofError("installed_identity_failed")
            _run_ok(
                runner,
                CommandCall(
                    f"ensurepip-{version}",
                    (
                        str(python),
                        "-I",
                        "-B",
                        "-m",
                        "ensurepip",
                        "--upgrade",
                        "--default-pip",
                    ),
                    pip_env,
                    cell,
                ),
                "environment_create_failed",
            )
            if venv_initial is not None:
                try:
                    observed_before_install = dependency_authority._snapshot_venv_authority(  # pyright: ignore[reportPrivateUsage]
                        venv=venv,
                        executable=python,
                        call_root=cell,
                        cell=dependency_cell,
                    )
                except dependency_authority.ReceiptError as error:
                    raise DirectAudioDeploymentProofError(
                        "installed_identity_failed"
                    ) from error
                if (
                    observed_before_install.executable != venv_initial.executable
                    or observed_before_install.configuration != venv_initial.configuration
                    or [name for name, _ in observed_before_install.directories]
                    != [name for name, _ in venv_initial.directories]
                ):
                    raise DirectAudioDeploymentProofError("installed_identity_failed")
                venv_authority = observed_before_install
            pip_argv = (
                str(python),
                "-I",
                "-m",
                "pip",
                "--isolated",
                "--disable-pip-version-check",
                "--no-input",
                "install",
                "--no-index",
                "--find-links",
                (stage / "wheelhouse").as_uri(),
                "--only-binary=:all:",
                "--no-cache-dir",
                "--require-hashes",
                "--constraint",
                str(stage / "constraints.txt"),
                "--requirement",
                str(stage / "root-requirements.txt"),
            )
            _run_ok(
                runner,
                CommandCall(f"pip-install-{version}", pip_argv, pip_env, cell),
                "install_failed",
            )
            _validate_staged_inputs(
                config=config,
                authorization=authorization,
                stage=stage,
            )
            if venv_authority is not None:
                try:
                    dependency_authority._validate_venv_authority(  # pyright: ignore[reportPrivateUsage]
                        venv_authority,
                        venv=venv,
                        executable=python,
                        call_root=cell,
                        cell=dependency_cell,
                    )
                except dependency_authority.ReceiptError as error:
                    raise DirectAudioDeploymentProofError(
                        "installed_identity_failed"
                    ) from error
            _run_ok(
                runner,
                CommandCall(
                    f"pip-check-{version}",
                    (str(python), "-I", "-m", "pip", "check"),
                    pip_env,
                    cell,
                ),
                "install_failed",
            )
            if isinstance(runner, _RealRunner):
                try:
                    for bytecode in venv.rglob("*.pyc"):
                        bytecode.unlink()
                except OSError as error:
                    raise DirectAudioDeploymentProofError(
                        "installed_identity_failed"
                    ) from error
            identity = _run_json(
                runner,
                CommandCall(
                    "installed-identity",
                    (
                        str(python),
                        "-I",
                        "-B",
                        "-c",
                        _INSTALLED_IDENTITY_SOURCE,
                    ),
                    env,
                    cell,
                ),
                "installed_identity_failed",
            )
            if identity.get("repository_import") is not False:
                raise DirectAudioDeploymentProofError("installed_identity_failed")
            if isinstance(runner, _RealRunner):
                package_map = dict(authorization.package_sets)
                _validate_installed_candidate(
                    venv=venv,
                    identity=identity,
                    wheel_value=_read_regular(config.mke_wheel),
                    expected_packages=package_map[version],
                )
            canary = _network_canary(
                runner,
                python=python,
                env=env,
                cell=cell,
            )
            if canary.get("status") != "blocked":
                raise DirectAudioDeploymentProofError("network_boundary_failed")
            doctor = _run_json(
                runner,
                CommandCall(
                    "doctor",
                    _sandbox(
                        (
                            str(mke),
                            "transcription",
                            "doctor",
                            *_runtime_args(config)[:-4],
                            "--json",
                        )
                    ),
                    env,
                    cell,
                ),
                "model_authority_invalid",
            )
            if doctor.get("status") != "ready":
                raise DirectAudioDeploymentProofError("model_authority_invalid")
            products: list[dict[str, object]] = []
            fixture_digests = {name: digest for name, _, digest in authorization.fixtures}
            for lane in ("python", "cli"):
                for suffix in ("mp3", "wav", "m4a"):
                    payload = _run_json(
                        runner,
                        _product_call(
                            lane=lane,
                            suffix=suffix,
                            python=python,
                            mke=mke,
                            fixture=allowed / f"direct-audio.{suffix}",
                            db=cell / f"{lane}.sqlite",
                            root=cell,
                            env=env,
                            config=config,
                        ),
                        "product_path_failed",
                    )
                    validate_product_result(payload, fixture=suffix)
                    if payload.get("source_sha256") != fixture_digests[f"direct-audio.{suffix}"]:
                        raise DirectAudioDeploymentProofError("product_path_failed")
                    products.append(payload)
            semantic_groups: dict[str, set[bytes]] = {
                suffix: set() for suffix in ("mp3", "wav", "m4a")
            }
            for payload in products:
                evidence = cast(dict[str, object], payload["evidence_ref"])
                semantic_groups[cast(str, payload["fixture"])].add(
                    _canonical(
                        {
                            "source_sha256": payload["source_sha256"],
                            "content_fingerprint": evidence["content_fingerprint"],
                            "locator": evidence["locator"],
                            "text": evidence["text"],
                        }
                    )
                )
            if any(len(values) != 1 for values in semantic_groups.values()):
                raise DirectAudioDeploymentProofError("product_path_failed")
            mcp = _run_json(
                runner,
                _product_call(
                    lane="mcp",
                    suffix="m4a",
                    python=python,
                    mke=mke,
                    fixture=allowed / "direct-audio.m4a",
                    db=cell / "mcp.sqlite",
                    root=cell,
                    env=env,
                    config=config,
                ),
                "mcp_failed",
            )
            try:
                validate_product_result(mcp, fixture="m4a")
            except DirectAudioDeploymentProofError as error:
                raise DirectAudioDeploymentProofError("mcp_failed") from error
            if mcp.get("source_sha256") != fixture_digests["direct-audio.m4a"]:
                raise DirectAudioDeploymentProofError("mcp_failed")
            export_root = cell / "export"
            export_results: list[dict[str, object]] = []
            for name in ("first", "second"):
                export = _run_json(
                    runner,
                    CommandCall(
                        f"export-{name}",
                        (
                            str(mke),
                            "--db",
                            str(cell / "cli.sqlite"),
                            "library",
                            "export",
                            "--output",
                            str(export_root / name),
                            "--format-version",
                            "v2",
                            "--json",
                        ),
                        env,
                        cell,
                    ),
                    "export_failed",
                )
                if (
                    export.get("schema_version")
                    != "mke.compiled_library_export_response.v2"
                    or export.get("ok") is not True
                ):
                    raise DirectAudioDeploymentProofError("export_failed")
                export_results.append(export)
            if (
                export_results[0].get("manifest_sha256")
                != export_results[1].get("manifest_sha256")
            ):
                raise DirectAudioDeploymentProofError("export_failed")
            export_tree_sha256: str | None = None
            if isinstance(runner, _RealRunner):
                first = export_root / "first"
                second = export_root / "second"
                first_tree = _export_tree_digest(first)
                if first_tree != _export_tree_digest(second):
                    raise DirectAudioDeploymentProofError("export_failed")
                export_tree_sha256 = first_tree
                try:
                    shutil.copytree(first, export_root / "copy")
                except OSError as error:
                    raise DirectAudioDeploymentProofError("export_failed") from error
                if _export_tree_digest(export_root / "copy") != first_tree:
                    raise DirectAudioDeploymentProofError("export_failed")
            consumer_results: list[dict[str, object]] = []
            for name in ("original", "copy"):
                consumer = _run_json(
                    runner,
                    CommandCall(
                        f"consumer-{name}",
                        (
                            str(python),
                            "-I",
                            "-B",
                            str(cell / "compiled-library-consumer-v2.py"),
                            "--export",
                            str(export_root / ("first" if name == "original" else "copy")),
                            "--json",
                        ),
                        env,
                        cell,
                    ),
                    "consumer_failed",
                )
                if (
                    consumer.get("schema_version")
                    != "mke.compiled_library_export_consumer.v2"
                    or consumer.get("status") != "passed"
                ):
                    raise DirectAudioDeploymentProofError("consumer_failed")
                consumer_results.append(consumer)
            _validate_staged_inputs(
                config=config,
                authorization=authorization,
                stage=stage,
            )
            if venv_authority is not None:
                try:
                    dependency_authority._validate_venv_authority(  # pyright: ignore[reportPrivateUsage]
                        venv_authority,
                        venv=venv,
                        executable=python,
                        call_root=cell,
                        cell=dependency_cell,
                    )
                except dependency_authority.ReceiptError as error:
                    raise DirectAudioDeploymentProofError(
                        "installed_identity_failed"
                    ) from error
            cells.append(
                {
                    "python_version": version,
                    "proof_input_wheel_sha256": authorization.mke_wheel_sha256,
                    "product_path_count": len(products) + 1,
                    "network": "blocked",
                    "doctor": "ready",
                    "export": "passed",
                    "consumer": "passed",
                    "product_results": [*products, mcp],
                    "export_result": export_results[0],
                    "export_tree_sha256": export_tree_sha256,
                    "consumer_result": consumer_results[0],
                    "consumer_sha256": authorization.consumer_sha256,
                    "supervision_observations": (
                        runner.observations[supervision_start:]
                        if isinstance(runner, _RealRunner)
                        else []
                    ),
                }
            )
    return {
        "schema_version": "mke.direct_audio_deployment_test_observation.v1",
        "canonical": False,
        "status": "passed",
        "interpreter_count": len(cells),
        "authorization_manifest": authorization.as_dict(),
        "cells": cells,
    }


def _run_direct_audio_deployment_proof(
    config: DirectAudioProofConfig,
    authorization: AuthorizationManifest,
    runner: CommandRunner,
    interpreter_snapshots: tuple[dependency_authority.ExecutableSnapshot, ...] | None = None,
) -> dict[str, object]:
    return _run_direct_audio_deployment_proof_impl(
        config,
        authorization,
        runner,
        interpreter_snapshots,
    )


def run_direct_audio_deployment_proof(
    config: DirectAudioProofConfig,
) -> dict[str, object]:
    """Run the canonical terminal proof with no injectable authority seams."""
    authorization = _validate_inputs(config)
    interpreter_snapshots = _bound_interpreter_snapshots(config, authorization)
    runner = _RealRunner(config)
    observation = _run_direct_audio_deployment_proof(
        config,
        authorization,
        runner,
        interpreter_snapshots,
    )
    if _validate_inputs(config) != authorization:
        raise DirectAudioDeploymentProofError("input_identity_drift")
    return {
        **observation,
        "schema_version": "mke.direct_audio_deployment_proof.v1",
        "canonical": True,
        "supervision_observations": runner.observations,
    }


def build_direct_audio_authorization_manifest(
    config: DirectAudioProofConfig,
) -> dict[str, object]:
    """Validate and freeze exact terminal inputs without starting inference."""
    return _validate_inputs(config).as_dict()


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="direct_audio_deployment_proof.py")
    parser.add_argument("--python", action="append", type=Path, required=True)
    parser.add_argument("--mke-wheel", type=Path, required=True)
    parser.add_argument("--dependency-receipt", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--constraints", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--direct-audio-footprint-bytes", type=_positive_int, required=True)
    parser.add_argument(
        "--direct-audio-footprint-budget-mode",
        choices=("baseline_plus",),
        required=True,
    )
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--authorization-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def _atomic_write(path: Path, payload: Mapping[str, object]) -> None:
    temporary: Path | None = None
    try:
        parent = path.parent.resolve(strict=True)
        if path.parent.resolve() != parent:
            raise DirectAudioDeploymentProofError("receipt_write_failed")
        temporary = parent / f".{path.name}.tmp-{os.getpid()}"
        value = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
            + b"\n"
        )
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            os.write(descriptor, value)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
    except DirectAudioDeploymentProofError:
        raise
    except OSError as error:
        try:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise DirectAudioDeploymentProofError("receipt_write_failed") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if len(args.python) != 2:
        parser.error("--python must be provided exactly twice")
    try:
        config = DirectAudioProofConfig(
            interpreters=tuple(args.python),
            mke_wheel=args.mke_wheel,
            dependency_receipt=args.dependency_receipt,
            wheelhouse=args.wheelhouse,
            constraints=args.constraints,
            model_root=args.model_root,
            fixture_root=args.fixture_root,
            direct_audio_footprint_bytes=args.direct_audio_footprint_bytes,
            direct_audio_footprint_budget_mode=args.direct_audio_footprint_budget_mode,
        )
        report = (
            build_direct_audio_authorization_manifest(config)
            if args.authorization_only
            else run_direct_audio_deployment_proof(config)
        )
        if args.receipt is not None:
            _atomic_write(args.receipt, report)
    except (TypeError, ValueError):
        report = {
            "schema_version": "mke.direct_audio_deployment_proof.v1",
            "canonical": False,
            "status": "failed",
            "failure": "cli_arguments_invalid",
        }
        if args.json:
            print(json.dumps(report, sort_keys=True))
        return 1
    except DirectAudioDeploymentProofError as error:
        report = {
            "schema_version": "mke.direct_audio_deployment_proof.v1",
            "canonical": False,
            "status": "failed",
            "failure": str(error),
        }
        if args.json:
            print(json.dumps(report, sort_keys=True))
        return 1
    if args.json:
        print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
