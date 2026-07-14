#!/usr/bin/env python3
"""Prepare and replay the PDF OCR Phase 0 package compatibility matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, NoReturn, cast

_SCHEMA = "mke.pdf_ocr_candidate_environments.v1"
_RECEIPT_PROFILE = "phase0-package-only-v1"
_CANDIDATE_PROFILE = "phase0-200dpi-plain-text-v1"
_MKE_WHEEL_FILENAME = "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
_SURFACES = ("base", "embedding", "transcription", "embedding+transcription")
_PYTHON_MINORS = ("3.12", "3.13")
_RESULTS = frozenset({"passed", "resolver_failed", "offline_replay_failed", "validation_failed"})
_FAILURE_CODES = frozenset(
    {
        "resolver_unavailable",
        "offline_install_failed",
        "pip_check_failed",
        "import_doctor_failed",
        "mke_identity_failed",
        "fake_child_failed",
    }
)
_READ_CHUNK_BYTES = 8192
_POLL_SECONDS = 0.02
_TERMINATION_GRACE_SECONDS = 0.5
_DEFAULT_TIMEOUT_SECONDS = 600.0
_DEFAULT_STDOUT_BYTES = 2 * 1024 * 1024
_DEFAULT_STDERR_BYTES = 2 * 1024 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9A-Za-z]+)+(?:[-+._][0-9A-Za-z]+)*\Z")
_SAFE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+()-]{0,255}\Z")
_PRIVATE_RE = re.compile(
    r"(?:/Users/|/private/|[A-Za-z]:\\|https?://|Traceback|API[_-]?KEY|TOKEN=|"
    r"SECRET=|PASSWORD=|BEGIN [A-Z ]*PRIVATE KEY)",
    re.IGNORECASE,
)
_MODEL_SCHEMA = "mke.pdf_ocr_model_artifacts.v1"
_MODEL_PROFILE = "phase0-model-artifacts-v1"
_PROVIDER_STARTUP_SCHEMA = "mke.pdf_ocr_provider_startup.v1"
_MODEL_MAX_TRANSIENT_BYTES = 5 * 1024 * 1024 * 1024
_MODEL_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_MODEL_METADATA_MAX_BYTES = 2 * 1024 * 1024
_MODEL_NETWORK_TIMEOUT_SECONDS = 1800.0
_MODEL_ALLOWED_HOSTS = frozenset(
    {"huggingface.co", "cdn-lfs.huggingface.co", "cas-bridge.xethub.hf.co"}
)
_RESOLVER_MARKERS = (
    b"no matching distribution found",
    b"could not find a version that satisfies the requirement",
    b"resolutionimpossible",
)


class CompatibilityError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Candidate:
    candidate: str
    profile: str
    requirements: tuple[str, str]
    required_symbol: str


@dataclass(frozen=True)
class ModelArtifact:
    candidate: str
    component: str
    repository: str
    revision: str
    license: str
    files: tuple[tuple[str, int, str], ...]

    def __post_init__(self) -> None:
        if (
            self.candidate
            not in {
                "ppocrv6-medium-cpu-spike-v1",
                "paddleocr-vl-1.6-cpu-spike-v1",
            }
            or not _SAFE_RE.fullmatch(self.component)
            or not re.fullmatch(r"PaddlePaddle/[A-Za-z0-9._-]+", self.repository)
            or not re.fullmatch(r"[0-9a-f]{40}", self.revision)
            or self.license != "Apache-2.0"
            or not self.files
        ):
            raise ValueError("model artifact is invalid")
        seen: set[str] = set()
        for path, size, digest in self.files:
            pure = Path(path)
            if (
                not path
                or pure.is_absolute()
                or ".." in pure.parts
                or "\\" in path
                or path in seen
                or size <= 0
                or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", digest)
            ):
                raise ValueError("model artifact is invalid")
            seen.add(path)


# Exact pinned inventories observed from the official metadata endpoint. Git
# blobs use their Git SHA-1 identity; LFS blobs use the declared SHA-256.
MODEL_ARTIFACTS: tuple[ModelArtifact, ...] = (
    ModelArtifact(
        candidate="ppocrv6-medium-cpu-spike-v1",
        component="PP-OCRv6_medium_det",
        repository="PaddlePaddle/PP-OCRv6_medium_det",
        revision="8e0f56fb2ef86b461d99cfc7ac5c137738985f61",
        license="Apache-2.0",
        files=(
            (".gitattributes", 1575, "c48a31d8dce80bfbfe392212dc49792e212a6436"),
            ("README.md", 23247, "715b0f0fcd71d2edc118b1e624ffd954fd9a02db"),
            ("inference.json", 312150, "548f60c00e9303a0323feceeae460256576671a6"),
            (
                "inference.pdiparams",
                61960476,
                "85218d2e3d98f5a21c58b4220627be923a97aee5db3cc71f39536ab31ac53960",
            ),
            ("inference.yml", 886, "1c5c05809877e4c7385f899019fff0ac9017ca80"),
        ),
    ),
    ModelArtifact(
        candidate="ppocrv6-medium-cpu-spike-v1",
        component="PP-OCRv6_medium_rec",
        repository="PaddlePaddle/PP-OCRv6_medium_rec",
        revision="e5a92bcbc5cc1b494628e458d267778f0704fd7c",
        license="Apache-2.0",
        files=(
            (".gitattributes", 1575, "c48a31d8dce80bfbfe392212dc49792e212a6436"),
            ("README.md", 23474, "580e21d8953c774df101f56bf01aa851992e344f"),
            ("inference.json", 221814, "9e0192344de3b69dacdb19dd735efbd06bd852f9"),
            (
                "inference.pdiparams",
                76465087,
                "1b01c79a914587933f615569e75de54f2e638ebb5d3f3b3c1b38c24ede8c7319",
            ),
            ("inference.yml", 150580, "c53a96fcd315a86cb4748d2746f3d90941e1c6d8"),
        ),
    ),
    ModelArtifact(
        candidate="paddleocr-vl-1.6-cpu-spike-v1",
        component="PP-DocLayoutV3",
        repository="PaddlePaddle/PP-DocLayoutV3",
        revision="7b48a7566925fa464281f930c58eee04fe2c862a",
        license="Apache-2.0",
        files=(
            (".gitattributes", 1575, "c48a31d8dce80bfbfe392212dc49792e212a6436"),
            ("README.md", 12077, "0e67905a060d65fffd43d158c078e320b3c5d784"),
            ("inference.json", 1196890, "5fd3ae9d9615dd36cd2134551a3bcc60d222ed21"),
            (
                "inference.pdiparams",
                130806572,
                "70bd316b0582769ec968829fd1feb1a6a58b7c941b938327e551b6b12b45c137",
            ),
            ("inference.yml", 1482, "ed7472400b398e0e0e032893f7986b32692980e7"),
        ),
    ),
    ModelArtifact(
        candidate="paddleocr-vl-1.6-cpu-spike-v1",
        component="PaddleOCR-VL-1.6",
        repository="PaddlePaddle/PaddleOCR-VL-1.6",
        revision="66317acc4c9fc17bd154591ce650735cd2855f3e",
        license="Apache-2.0",
        files=(
            (".gitattributes", 1570, "52373fe24473b1aa44333d318f578ae6bf04b49b"),
            ("LICENSE", 11376, "0491a00e80b424eb709078b57e35d8b83ffee985"),
            ("README.md", 21466, "bf454fab90d7ce2f5529b437ac4f8bb1176c54d0"),
            ("added_tokens.json", 25381, "6a2790e1462ecb007f9b92dfb00f594701462889"),
            ("chat_template.jinja", 1474, "d8b8c271d7a7245d4937098f53aa372cff3dba70"),
            ("config.json", 2059, "c54711466ae75457f8e57b909a49dae570bfa5c5"),
            ("configuration_paddleocr_vl.py", 8104, "a8fd139287293301b287db6dfdaac21d7ad1a236"),
            ("generation_config.json", 133, "ba87d71b9881c1d52f0be4286fb63e381ce3febf"),
            ("image_processing_paddleocr_vl.py", 25032, "f7e28fd3c1971331581f73d573b9c4a2a4ce7a58"),
            ("inference.yml", 43, "93f88dfb31b6dbc3f529094ccfe26ddec98fa8ad"),
            (
                "model.safetensors",
                1917255968,
                "85a479d506a11e724e7285d395c551be69f41dbc16b6342d3cacfb189aed71db",
            ),
            ("modeling_paddleocr_vl.py", 103889, "693782514116586458b12cfd911c88d6565f552c"),
            ("preprocessor_config.json", 641, "d873cd63d04d9e6243999759fc30f7752dab3222"),
            ("processing_paddleocr_vl.py", 12253, "73c3faeff201555fc7b52709848e3c669419dbb1"),
            ("processor_config.json", 137, "033053ac4d8b5de2e47884ce85a6b4939cc58e87"),
            ("special_tokens_map.json", 1151, "dcd70aaa8c9987899d7593995546d9c0cfc6a1f3"),
            (
                "tokenizer.json",
                11189060,
                "c8a215a59183d0d0781adc33bacd3ce6162716f7fd568fb30234a74d69803a7d",
            ),
            (
                "tokenizer.model",
                1614363,
                "34ef7db83df785924fb83d7b887b6e822a031c56e15cff40aaf9b982988180df",
            ),
            ("tokenizer_config.json", 186947, "cd9eb7da01a3209f4fb9b3561e04be022cd87764"),
        ),
    ),
)


CANDIDATES: dict[str, Candidate] = {
    "ppocrv6-medium-cpu-spike-v1": Candidate(
        candidate="ppocrv6-medium-cpu-spike-v1",
        profile=_CANDIDATE_PROFILE,
        requirements=("paddleocr==3.7.0", "paddlepaddle==3.3.1"),
        required_symbol="PaddleOCR",
    ),
    "paddleocr-vl-1.6-cpu-spike-v1": Candidate(
        candidate="paddleocr-vl-1.6-cpu-spike-v1",
        profile=_CANDIDATE_PROFILE,
        requirements=("paddleocr[doc-parser]==3.7.0", "paddlepaddle==3.3.1"),
        required_symbol="PaddleOCRVL",
    ),
}


@dataclass(frozen=True)
class InterpreterIdentity:
    python: Path
    version: str
    minor: str

    def __post_init__(self) -> None:
        if self.minor not in _PYTHON_MINORS or not self.version.startswith(self.minor + "."):
            raise ValueError("interpreter version is invalid")


@dataclass(frozen=True)
class MatrixCell:
    candidate: str
    profile: str
    surface: str
    python: Path
    python_version: str
    python_minor: str
    mke_wheel_sha256: str


@dataclass(frozen=True)
class MatrixPlan:
    cells: tuple[MatrixCell, ...]
    mke_wheel_sha256: str


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class CompatibilityConfig:
    repository: Path
    wheel: Path
    interpreters: tuple[Path, Path]
    staging_root: Path
    cache_root: Path
    output: Path
    allow_package_download: bool
    prepared_wheelhouses: Path | None = None
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    max_stdout_bytes: int = _DEFAULT_STDOUT_BYTES
    max_stderr_bytes: int = _DEFAULT_STDERR_BYTES


@dataclass(frozen=True)
class ModelPreparationConfig:
    staging_root: Path
    final_root: Path
    output: Path
    allow_model_download: bool
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS


@dataclass
class _Capture:
    limit: int
    data: bytearray
    exceeded: threading.Event


def build_matrix_plan(
    wheel: Path,
    interpreters: tuple[InterpreterIdentity, InterpreterIdentity],
) -> MatrixPlan:
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError("MKE wheel is invalid")
    resolved = tuple(item.python.resolve() for item in interpreters)
    if resolved[0] == resolved[1]:
        raise ValueError("interpreter aliasing is forbidden")
    if {item.minor for item in interpreters} != set(_PYTHON_MINORS):
        raise ValueError("interpreters must cover exact Python 3.12 and 3.13")
    digest = _sha256_file(wheel)
    cells = tuple(
        MatrixCell(
            candidate=candidate.candidate,
            profile=candidate.profile,
            surface=surface,
            python=interpreter.python,
            python_version=interpreter.version,
            python_minor=interpreter.minor,
            mke_wheel_sha256=digest,
        )
        for candidate in CANDIDATES.values()
        for interpreter in sorted(interpreters, key=lambda item: item.minor)
        for surface in _SURFACES
    )
    return MatrixPlan(cells=cells, mke_wheel_sha256=digest)


def candidate_download_command(
    *,
    python: Path,
    wheel: Path,
    candidate: Candidate,
    destination: Path,
    cache: Path,
) -> tuple[str, ...]:
    return (
        str(python),
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--only-binary=:all:",
        "--dest",
        str(destination),
        "--cache-dir",
        str(cache),
        f"{wheel}[embedding,transcription]",
        *candidate.requirements,
    )


def offline_install_command(
    *,
    python: Path,
    wheel: Path,
    candidate: Candidate,
    surface: str,
    wheelhouse: Path,
) -> tuple[str, ...]:
    if surface not in _SURFACES:
        raise ValueError("matrix surface is invalid")
    extras = {
        "base": "",
        "embedding": "[embedding]",
        "transcription": "[transcription]",
        "embedding+transcription": "[embedding,transcription]",
    }[surface]
    return (
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-index",
        "--find-links",
        str(wheelhouse),
        f"{wheel}{extras}",
        *candidate.requirements,
    )


def classify_prepare_failure(stderr: bytes) -> str:
    normalized = stderr.lower()
    if any(marker in normalized for marker in _RESOLVER_MARKERS):
        return "resolver_failed"
    return "infrastructure_failed"


def validate_acquisition_mode(
    allow_package_download: bool,
    prepared_wheelhouses: Path | None,
) -> Path | None:
    if allow_package_download and prepared_wheelhouses is not None:
        raise CompatibilityError("acquisition_mode_invalid")
    if allow_package_download:
        return None
    if prepared_wheelhouses is None:
        raise CompatibilityError("package_download_not_authorized")
    resolved = prepared_wheelhouses.resolve()
    if not resolved.is_dir():
        raise CompatibilityError("prepared_wheelhouses_invalid")
    return resolved


def validate_model_metadata(artifact: ModelArtifact, value: object) -> None:
    try:
        root = _mapping(value)
        _exact(root, {"repository", "revision", "license", "files"})
        if (
            root["repository"] != artifact.repository
            or root["revision"] != artifact.revision
            or root["license"] != artifact.license
            or not isinstance(root["files"], list)
        ):
            raise ValueError
        observed: list[tuple[str, int, str]] = []
        for raw in cast(list[object], root["files"]):
            item = _mapping(raw)
            _exact(item, {"path", "bytes", "sha256"})
            identity = item["sha256"]
            if not isinstance(identity, str) or not re.fullmatch(
                r"(?:[0-9a-f]{40}|[0-9a-f]{64})", identity
            ):
                raise ValueError
            observed.append(
                (
                    cast(str, item["path"]),
                    _nonnegative_integer(item["bytes"]),
                    identity,
                )
            )
        if tuple(observed) != artifact.files:
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise CompatibilityError("model_metadata_drift") from error


def canonical_model_receipt_bytes(receipt: object) -> bytes:
    validate_model_receipt(receipt)
    return (
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("utf-8")


def canonical_provider_startup_bytes(receipt: object) -> bytes:
    validate_provider_startup_receipt(receipt)
    return (
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("utf-8")


def validate_provider_startup_authority(repository: Path, value: object) -> None:
    try:
        validate_provider_startup_receipt(value)
        root = _mapping(value)
        package_path = repository / "benchmarks/ocr/candidate-environments.json"
        model_path = repository / "benchmarks/ocr/model-artifacts.json"
        protocol_path = repository / "tests/fixtures/pdf-ocr-phase0-v1/protocol.json"
        observed_path = (
            repository
            / "tests/fixtures/pdf-ocr-provider/paddleocr-vl-1.6-observed.json"
        )
        package_bytes = package_path.read_bytes()
        package_value: object = json.loads(package_bytes.decode("utf-8"))
        if package_bytes != canonical_receipt_bytes(package_value):
            raise ValueError
        model_bytes = model_path.read_bytes()
        model_value: object = json.loads(model_bytes.decode("utf-8"))
        if model_bytes != canonical_model_receipt_bytes(model_value):
            raise ValueError
        if root["package_receipt_sha256"] != hashlib.sha256(package_bytes).hexdigest():
            raise ValueError
        if root["model_receipt_sha256"] != hashlib.sha256(model_bytes).hexdigest():
            raise ValueError
        protocol: object = json.loads(protocol_path.read_text(encoding="utf-8"))
        expected_text = _expected_english_scan_truth(protocol)
        expected_text_sha256 = hashlib.sha256(expected_text.encode("utf-8")).hexdigest()
        provider_inventory = root["providers"]
        if not isinstance(provider_inventory, list):
            raise ValueError
        providers = cast(list[object], provider_inventory)
        if any(_mapping(item)["status"] != "passed" for item in providers):
            raise ValueError
        for raw_provider in providers:
            provider = _mapping(raw_provider)
            if provider["status"] == "passed" and (
                provider["normalized_text_sha256"] != expected_text_sha256
            ):
                raise ValueError
        observed = _mapping(json.loads(observed_path.read_text(encoding="utf-8")))
        _exact(observed, {"source_artifacts", "vendor_json", "markdown"})
        if observed["markdown"] != expected_text:
            raise ValueError
        from mke.evaluation.pdf_ocr_paddle_vl import validate_observed_vendor_evidence

        if (
            validate_observed_vendor_evidence(
                observed["vendor_json"], cast(str, observed["markdown"])
            )
            != expected_text
        ):
            raise ValueError
        paddle = _mapping(providers[1])
        artifacts = _mapping(paddle["vendor_artifacts"])
        if artifacts["files"] != observed["source_artifacts"]:
            raise ValueError
        vendor_json = _mapping(observed["vendor_json"])
        blocks = cast(list[object], vendor_json["parsing_res_list"])
        first_block = _mapping(blocks[0])
        if artifacts["json_top_level_keys"] != sorted(vendor_json):
            raise ValueError
        if artifacts["parsing_block_keys"] != sorted(first_block):
            raise ValueError
    except (KeyError, OSError, TypeError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("provider startup authority is invalid") from error


def write_provider_startup_receipt(repository: Path, value: object, output: Path) -> None:
    validate_provider_startup_authority(repository, value)
    encoded = canonical_provider_startup_bytes(value)
    temporary = output.with_suffix(output.suffix + ".tmp")
    if output.exists() or temporary.exists():
        raise ValueError("provider startup authority is invalid")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, output)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ValueError("provider startup authority is invalid") from error


def _expected_english_scan_truth(value: object) -> str:
    root = _mapping(value)
    if root.get("protocol_id") != "pdf-ocr-phase0-v1":
        raise ValueError
    documents = root.get("documents")
    if not isinstance(documents, list):
        raise ValueError
    matches = [
        _mapping(item)
        for item in cast(list[object], documents)
        if _mapping(item).get("document_id") == "english-scan"
    ]
    if len(matches) != 1:
        raise ValueError
    pages = matches[0].get("pages")
    if not isinstance(pages, list):
        raise ValueError
    page_values = cast(list[object], pages)
    if len(page_values) != 1:
        raise ValueError
    page = _mapping(page_values[0])
    if page.get("page_number") != 1 or page.get("expected_route") != "ocr_required":
        raise ValueError
    text = page.get("expected_ocr_text")
    if not isinstance(text, str) or not text:
        raise ValueError
    from mke.evaluation.pdf_ocr_provider import normalize_ocr_text

    return normalize_ocr_text(text)


def validate_provider_startup_receipt(value: object) -> None:
    try:
        root = _mapping(value)
        _exact(
            root,
            {
                "schema",
                "profile",
                "platform",
                "package_receipt_sha256",
                "model_receipt_sha256",
                "network_isolation",
                "fixture",
                "providers",
            },
        )
        if root["schema"] != _PROVIDER_STARTUP_SCHEMA or root["profile"] != _CANDIDATE_PROFILE:
            raise ValueError
        platform_value = _mapping(root["platform"])
        _exact(platform_value, {"os", "architecture"})
        _safe(platform_value["os"])
        _safe(platform_value["architecture"])
        _digest(root["package_receipt_sha256"])
        _digest(root["model_receipt_sha256"])
        network = _mapping(root["network_isolation"])
        _exact(network, {"mechanism", "canary"})
        if network != {
            "mechanism": "darwin-sandbox-deny-network",
            "canary": "blocked",
        }:
            raise ValueError
        fixture = _mapping(root["fixture"])
        _exact(fixture, {"protocol", "document", "page"})
        if fixture != {
            "protocol": "pdf-ocr-phase0-v1",
            "document": "english-scan",
            "page": 1,
        }:
            raise ValueError
        providers = root["providers"]
        if not isinstance(providers, list):
            raise ValueError
        provider_values = cast(list[object], providers)
        expected_providers = [
            "apple-vision-local-v1",
            "paddleocr-vl-1.6-cpu-spike-v1",
            "ppocrv6-medium-cpu-spike-v1",
        ]
        if len(provider_values) != len(expected_providers):
            raise ValueError
        for raw, expected_provider in zip(provider_values, expected_providers, strict=True):
            provider = _mapping(raw)
            _exact(
                provider,
                {
                    "provider",
                    "status",
                    "failure_code",
                    "duration_ms",
                    "normalized_text_sha256",
                    "vendor_artifacts",
                },
            )
            if provider["provider"] != expected_provider:
                raise ValueError
            status_value = provider["status"]
            if status_value == "passed":
                if (
                    provider["failure_code"] is not None
                    or _nonnegative_integer(provider["duration_ms"]) <= 0
                    or not isinstance(provider["normalized_text_sha256"], str)
                ):
                    raise ValueError
                _digest(provider["normalized_text_sha256"])
                if expected_provider == "paddleocr-vl-1.6-cpu-spike-v1":
                    _validate_vendor_artifacts(provider["vendor_artifacts"], accepted=True)
                elif provider["vendor_artifacts"] is not None:
                    raise ValueError
            elif status_value == "failed" and expected_provider == "paddleocr-vl-1.6-cpu-spike-v1":
                if (
                    provider["failure_code"] != "vendor_artifact_schema_mismatch"
                    or provider["duration_ms"] is not None
                    or provider["normalized_text_sha256"] is not None
                ):
                    raise ValueError
                _validate_vendor_artifacts(provider["vendor_artifacts"], accepted=False)
            else:
                raise ValueError
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if _PRIVATE_RE.search(encoded):
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("provider startup receipt is invalid") from error


def _validate_vendor_artifacts(value: object, *, accepted: bool) -> None:
    artifacts = _mapping(value)
    _exact(
        artifacts,
        {
            "files",
            "json_top_level_keys",
            "parsing_block_keys",
            "markdown_class",
            "adapter_result",
        },
    )
    files = artifacts["files"]
    if not isinstance(files, list):
        raise ValueError
    file_values = cast(list[object], files)
    if len(file_values) != 2:
        raise ValueError
    names: list[str] = []
    for raw in file_values:
        item = _mapping(raw)
        _exact(item, {"name", "bytes", "sha256"})
        name = _safe(item["name"])
        names.append(name)
        if _nonnegative_integer(item["bytes"]) <= 0:
            raise ValueError
        _digest(item["sha256"])
    if names != ["english-scan-page-1.md", "english-scan-page-1_res.json"]:
        raise ValueError
    for field in ("json_top_level_keys", "parsing_block_keys"):
        items = artifacts[field]
        if not isinstance(items, list) or not items:
            raise ValueError
        for item in cast(list[object], items):
            _safe(item)
    if (
        artifacts["markdown_class"] != "prose_only"
        or artifacts["adapter_result"]
        != ("accepted_strict_observed_schema" if accepted else "rejected_fail_closed")
    ):
        raise ValueError


def validate_model_receipt(value: object) -> None:
    try:
        root = _mapping(value)
        _exact(root, {"schema", "profile", "models", "total_bytes", "tree_sha256"})
        if root["schema"] != _MODEL_SCHEMA or root["profile"] != _MODEL_PROFILE:
            raise ValueError
        models = root["models"]
        if not isinstance(models, list):
            raise ValueError
        model_values = cast(list[object], models)
        if len(model_values) != len(MODEL_ARTIFACTS):
            raise ValueError
        total = 0
        components: set[str] = set()
        aggregate_files: list[dict[str, object]] = []
        for raw, expected_artifact in zip(model_values, MODEL_ARTIFACTS, strict=True):
            model = _mapping(raw)
            _exact(
                model,
                {
                    "candidate",
                    "component",
                    "repository",
                    "revision",
                    "license",
                    "files",
                    "total_bytes",
                    "tree_sha256",
                },
            )
            component = _safe(model["component"])
            if component in components:
                raise ValueError
            components.add(component)
            if (
                model["candidate"] != expected_artifact.candidate
                or model["repository"] != expected_artifact.repository
                or model["revision"] != expected_artifact.revision
                or model["license"] != expected_artifact.license
            ):
                raise ValueError
            if not re.fullmatch(r"PaddlePaddle/[A-Za-z0-9._-]+", cast(str, model["repository"])):
                raise ValueError
            if not re.fullmatch(r"[0-9a-f]{40}", cast(str, model["revision"])):
                raise ValueError
            if model["license"] != "Apache-2.0":
                raise ValueError
            files = model["files"]
            if not isinstance(files, list) or not files:
                raise ValueError
            file_total = 0
            expected_paths = [(path, size) for path, size, _ in expected_artifact.files]
            observed_paths: list[tuple[str, int]] = []
            for raw_file in cast(list[object], files):
                file_receipt = _mapping(raw_file)
                _exact(file_receipt, {"path", "bytes", "sha256"})
                path = cast(str, file_receipt["path"])
                if Path(path).is_absolute() or ".." in Path(path).parts or "\\" in path:
                    raise ValueError
                file_bytes = _nonnegative_integer(file_receipt["bytes"])
                observed_paths.append((path, file_bytes))
                file_total += file_bytes
                _digest(file_receipt["sha256"])
            if observed_paths != expected_paths:
                raise ValueError
            if file_total != _nonnegative_integer(model["total_bytes"]):
                raise ValueError
            tree_digest = _digest(model["tree_sha256"])
            if tree_digest != _model_tree_sha256(cast(list[dict[str, object]], files)):
                raise ValueError
            aggregate_files.append({"path": component, "bytes": file_total, "sha256": tree_digest})
            total += file_total
        if total != _nonnegative_integer(root["total_bytes"]):
            raise ValueError
        if _digest(root["tree_sha256"]) != _model_tree_sha256(aggregate_files):
            raise ValueError
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if _PRIVATE_RE.search(encoded):
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("model receipt is invalid") from error


def prepare_model_artifacts(
    config: ModelPreparationConfig,
    *,
    metadata_loader: Callable[[ModelArtifact], object] | None = None,
    downloader: Callable[[ModelArtifact, tuple[str, int, str], Path], None] | None = None,
) -> dict[str, object]:
    if not config.allow_model_download:
        raise CompatibilityError("model_download_not_authorized")
    staging = config.staging_root.resolve()
    final = config.final_root.resolve()
    output = config.output.resolve()
    if staging.exists() or final.exists() or output.exists():
        raise CompatibilityError("model_call_owned_root_exists")
    if staging == final or _within(staging, final) or _within(final, staging):
        raise CompatibilityError("model_root_invalid")
    load = metadata_loader or _fetch_model_metadata
    fetch = downloader or _download_model_file
    metadata_values: list[object] = []
    for artifact in MODEL_ARTIFACTS:
        value = load(artifact)
        validate_model_metadata(artifact, value)
        metadata_values.append(value)
    expected_total = sum(size for item in MODEL_ARTIFACTS for _, size, _ in item.files)
    if expected_total * 2 > _MODEL_MAX_TRANSIENT_BYTES:
        raise CompatibilityError("model_disk_budget_exceeded")
    staging.mkdir(mode=0o700, parents=True)
    payload_root = staging / "snapshot"
    payload_root.mkdir(mode=0o700)
    try:
        models: list[dict[str, object]] = []
        for artifact in MODEL_ARTIFACTS:
            component_root = payload_root / artifact.component
            component_root.mkdir(mode=0o700)
            for file_receipt in artifact.files:
                relative = Path(file_receipt[0])
                if relative.is_absolute() or ".." in relative.parts or "\\" in file_receipt[0]:
                    raise CompatibilityError("model_inventory_invalid")
                destination = component_root / relative
                if destination.exists() or destination.is_symlink():
                    raise CompatibilityError("model_file_collision")
                fetch(artifact, file_receipt, destination)
            files = _validated_model_tree(component_root, artifact.files)
            tree_digest = _model_tree_sha256(files)
            content_addressed = payload_root / f"{artifact.component}-{tree_digest}"
            os.replace(component_root, content_addressed)
            models.append(
                {
                    "candidate": artifact.candidate,
                    "component": artifact.component,
                    "repository": artifact.repository,
                    "revision": artifact.revision,
                    "license": artifact.license,
                    "files": files,
                    "total_bytes": sum(cast(int, item["bytes"]) for item in files),
                    "tree_sha256": tree_digest,
                }
            )
        aggregate_digest = _model_tree_sha256(
            [
                {
                    "path": cast(str, item["component"]),
                    "bytes": cast(int, item["total_bytes"]),
                    "sha256": cast(str, item["tree_sha256"]),
                }
                for item in models
            ]
        )
        receipt: dict[str, object] = {
            "schema": _MODEL_SCHEMA,
            "profile": _MODEL_PROFILE,
            "models": models,
            "total_bytes": sum(cast(int, item["total_bytes"]) for item in models),
            "tree_sha256": aggregate_digest,
        }
        encoded = canonical_model_receipt_bytes(receipt)
        os.replace(payload_root, final)
        temporary = output.with_suffix(output.suffix + ".tmp")
        output.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        temporary.write_bytes(encoded)
        os.replace(temporary, output)
        _make_model_tree_read_only(final)
        return receipt
    except Exception:
        if final.exists():
            shutil.rmtree(final, ignore_errors=True)
        output.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if staging.exists():
            raise CompatibilityError("cleanup_failed")


def _validated_model_tree(
    root: Path,
    expected: tuple[tuple[str, int, str], ...],
) -> list[dict[str, object]]:
    observed: list[dict[str, object]] = []
    expected_by_path = {path: (size, digest) for path, size, digest in expected}
    for path in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        metadata = path.lstat()
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or (
            not stat.S_ISDIR(metadata.st_mode) and not stat.S_ISREG(metadata.st_mode)
        ):
            raise CompatibilityError("model_inventory_invalid")
        if stat.S_ISDIR(metadata.st_mode):
            if relative in expected_by_path:
                raise CompatibilityError("model_inventory_invalid")
            continue
        if relative not in expected_by_path:
            raise CompatibilityError("model_inventory_invalid")
        expected_size, upstream_identity = expected_by_path[relative]
        observed.append(
            _validated_model_file(
                path,
                relative=relative,
                inventory_metadata=metadata,
                expected_size=expected_size,
                upstream_identity=upstream_identity,
            )
        )
    if [cast(str, item["path"]) for item in observed] != [path for path, _, _ in expected]:
        raise CompatibilityError("model_artifact_invalid")
    return observed


def _validated_model_file(
    path: Path,
    *,
    relative: str,
    inventory_metadata: os.stat_result,
    expected_size: int,
    upstream_identity: str,
) -> dict[str, object]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or _file_identity(before) != _file_identity(
            inventory_metadata
        ):
            raise CompatibilityError("model_artifact_invalid")
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_size != expected_size
            or _file_identity(opened) != _file_identity(inventory_metadata)
        ):
            raise CompatibilityError("model_artifact_invalid")
        receipt_digest = hashlib.sha256()
        git_digest = hashlib.sha1(usedforsecurity=False)
        git_digest.update(f"blob {expected_size}\0".encode("ascii"))
        actual_size = 0
        while True:
            chunk = os.read(
                descriptor,
                min(_MODEL_DOWNLOAD_CHUNK_BYTES, expected_size - actual_size + 1),
            )
            if not chunk:
                break
            actual_size += len(chunk)
            if actual_size > expected_size:
                raise CompatibilityError("model_artifact_invalid")
            receipt_digest.update(chunk)
            git_digest.update(chunk)
        receipt_sha256 = receipt_digest.hexdigest()
        observed_upstream = (
            receipt_sha256 if len(upstream_identity) == 64 else git_digest.hexdigest()
        )
        after_descriptor = os.fstat(descriptor)
        after_path = path.lstat()
        if (
            actual_size != expected_size
            or observed_upstream != upstream_identity
            or _file_identity(after_descriptor) != _file_identity(inventory_metadata)
            or _file_identity(after_path) != _file_identity(inventory_metadata)
        ):
            raise CompatibilityError("model_artifact_invalid")
        return {"path": relative, "bytes": actual_size, "sha256": receipt_sha256}
    except OSError as error:
        raise CompatibilityError("model_artifact_invalid") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _file_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _model_tree_sha256(files: list[dict[str, object]]) -> str:
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _make_model_tree_read_only(root: Path) -> None:
    entries = sorted(root.rglob("*"), key=lambda value: len(value.parts), reverse=True)
    for path in entries:
        metadata = path.lstat()
        if path.is_symlink():
            raise CompatibilityError("model_inventory_invalid")
        path.chmod(0o555 if stat.S_ISDIR(metadata.st_mode) else 0o444)
    root.chmod(0o555)


class _PinnedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str
    ):  # type: ignore[no-untyped-def]
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname not in _MODEL_ALLOWED_HOSTS:
            raise CompatibilityError("model_source_rejected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]


def _model_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _PinnedRedirectHandler(),
    )


def _read_network_response(response: object, limit: int) -> bytes:
    stream = cast(BinaryIO, response)
    content = bytearray()
    while True:
        chunk = stream.read(min(_MODEL_DOWNLOAD_CHUNK_BYTES, limit - len(content) + 1))
        if not chunk:
            return bytes(content)
        content.extend(chunk)
        if len(content) > limit:
            raise CompatibilityError("model_network_output_exceeded")


def _fetch_model_metadata(artifact: ModelArtifact) -> object:
    repository = urllib.parse.quote(artifact.repository, safe="/")
    url = f"https://huggingface.co/api/models/{repository}/revision/{artifact.revision}?blobs=true"
    request = urllib.request.Request(url, headers={"User-Agent": "mke-phase0-model-receipt/1"})
    try:
        with _model_opener().open(request, timeout=30.0) as response:
            payload = json.loads(_read_network_response(response, _MODEL_METADATA_MAX_BYTES))
    except CompatibilityError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, urllib.error.URLError) as error:
        raise CompatibilityError("model_metadata_unavailable") from error
    if not isinstance(payload, dict):
        raise CompatibilityError("model_metadata_drift")
    root = cast(dict[str, object], payload)
    siblings = root.get("siblings")
    card = root.get("cardData")
    if not isinstance(siblings, list) or not isinstance(card, dict):
        raise CompatibilityError("model_metadata_drift")
    files: list[dict[str, object]] = []
    for raw in cast(list[object], siblings):
        if not isinstance(raw, dict):
            raise CompatibilityError("model_metadata_drift")
        item = cast(dict[str, object], raw)
        path = item.get("rfilename")
        size = item.get("size")
        lfs = item.get("lfs")
        identity = (
            cast(dict[str, object], lfs).get("sha256")
            if isinstance(lfs, dict)
            else item.get("blobId")
        )
        if not isinstance(path, str) or not isinstance(size, int) or not isinstance(identity, str):
            raise CompatibilityError("model_metadata_drift")
        files.append({"path": path, "bytes": size, "sha256": identity})
    license_value = cast(dict[str, object], card).get("license")
    normalized_license = "Apache-2.0" if license_value == "apache-2.0" else license_value
    return {
        "repository": root.get("id"),
        "revision": root.get("sha"),
        "license": normalized_license,
        "files": files,
    }


def _download_model_file(
    artifact: ModelArtifact,
    file_receipt: tuple[str, int, str],
    destination: Path,
) -> None:
    relative, expected_bytes, _ = file_receipt
    encoded_path = urllib.parse.quote(relative, safe="/")
    repository = urllib.parse.quote(artifact.repository, safe="/")
    url = f"https://huggingface.co/{repository}/resolve/{artifact.revision}/{encoded_path}"
    request = urllib.request.Request(url, headers={"User-Agent": "mke-phase0-model-receipt/1"})
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    created = False
    try:
        with _model_opener().open(request, timeout=_MODEL_NETWORK_TIMEOUT_SECONDS) as response:
            with destination.open("xb") as output:
                created = True
                total = 0
                while True:
                    chunk = response.read(
                        min(_MODEL_DOWNLOAD_CHUNK_BYTES, expected_bytes - total + 1)
                    )
                    if not chunk:
                        break
                    output.write(chunk)
                    total += len(chunk)
                    if total > expected_bytes:
                        raise CompatibilityError("model_artifact_oversized")
                output.flush()
                os.fsync(output.fileno())
        if total != expected_bytes:
            raise CompatibilityError("model_artifact_incomplete")
    except FileExistsError as error:
        raise CompatibilityError("model_file_collision") from error
    except CompatibilityError:
        if created:
            destination.unlink(missing_ok=True)
        raise
    except (OSError, urllib.error.URLError) as error:
        if created:
            destination.unlink(missing_ok=True)
        raise CompatibilityError("model_download_failed") from error


def run_bounded(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> CommandResult:
    if timeout_seconds <= 0 or max_stdout_bytes <= 0 or max_stderr_bytes <= 0:
        raise CompatibilityError("command_contract_invalid")
    try:
        process = subprocess.Popen(
            list(command),
            shell=False,
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == "posix",
        )
    except OSError as error:
        raise CompatibilityError("command_could_not_start") from error
    pgid: int | None = process.pid if os.name == "posix" else None
    if process.stdout is None or process.stderr is None:
        _terminate(process, pgid)
        raise CompatibilityError("command_capture_failed")
    stdout = _Capture(max_stdout_bytes, bytearray(), threading.Event())
    stderr = _Capture(max_stderr_bytes, bytearray(), threading.Event())
    readers = (
        threading.Thread(target=_drain, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr), daemon=True),
    )
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout_seconds
    try:
        while process.poll() is None:
            if stdout.exceeded.is_set() or stderr.exceeded.is_set():
                raise CompatibilityError("command_output_exceeded")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CompatibilityError("command_timed_out")
            try:
                process.wait(timeout=min(_POLL_SECONDS, remaining))
            except subprocess.TimeoutExpired:
                continue
        _terminate(process, pgid)
        for reader in readers:
            reader.join(timeout=1)
        if any(reader.is_alive() for reader in readers):
            raise CompatibilityError("command_capture_failed")
        if stdout.exceeded.is_set() or stderr.exceeded.is_set():
            raise CompatibilityError("command_output_exceeded")
        return CommandResult(process.returncode, bytes(stdout.data), bytes(stderr.data))
    except BaseException:
        _terminate(process, pgid)
        for reader in readers:
            reader.join(timeout=1)
        raise
    finally:
        for stream in (process.stdout, process.stderr):
            try:
                stream.close()
            except OSError:
                pass


def validate_receipt(value: object) -> None:
    receipt = _mapping(value)
    _exact(receipt, {"schema", "profile", "platform", "mke_wheel_sha256", "candidates"})
    if receipt["schema"] != _SCHEMA or receipt["profile"] != _RECEIPT_PROFILE:
        _receipt_error()
    mke_wheel_sha256 = _digest(receipt["mke_wheel_sha256"])
    runtime = _mapping(receipt["platform"])
    _exact(runtime, {"os", "architecture"})
    _safe(runtime["os"])
    _safe(runtime["architecture"])
    raw_candidates = receipt["candidates"]
    if not isinstance(raw_candidates, list):
        _receipt_error()
    candidate_items = cast(list[object], raw_candidates)
    if len(candidate_items) != 2:
        _receipt_error()
    observed_candidates: set[str] = set()
    observed_cells: set[tuple[str, str, str]] = set()
    for raw_candidate in candidate_items:
        candidate = _mapping(raw_candidate)
        _exact(
            candidate,
            {"candidate", "profile", "pins", "distributions", "download_bytes", "cells"},
        )
        candidate_id = _safe(candidate["candidate"])
        expected = CANDIDATES.get(candidate_id)
        if expected is None or candidate["profile"] != expected.profile:
            _receipt_error()
        observed_candidates.add(candidate_id)
        pins = candidate["pins"]
        if not isinstance(pins, list) or pins != list(expected.requirements):
            _receipt_error()
        download_bytes = _nonnegative_integer(candidate["download_bytes"])
        distributions = _validate_distributions(candidate["distributions"])
        if not distributions or download_bytes != sum(
            _nonnegative_integer(item["bytes"]) for item in distributions
        ):
            _receipt_error()
        mke_distributions = [
            item for item in distributions if item["filename"] == _MKE_WHEEL_FILENAME
        ]
        if len(mke_distributions) != 1 or mke_distributions[0]["sha256"] != mke_wheel_sha256:
            _receipt_error()
        cells = candidate["cells"]
        if not isinstance(cells, list):
            _receipt_error()
        cell_items = cast(list[object], cells)
        if len(cell_items) != 8:
            _receipt_error()
        for raw_cell in cell_items:
            cell = _mapping(raw_cell)
            _exact(
                cell,
                {
                    "python",
                    "python_minor",
                    "surface",
                    "result",
                    "failure_code",
                    "package_versions",
                    "install_bytes",
                },
            )
            python = _version(cell["python"])
            minor = cell["python_minor"]
            surface = cell["surface"]
            result = cell["result"]
            if (
                minor not in _PYTHON_MINORS
                or not python.startswith(cast(str, minor) + ".")
                or surface not in _SURFACES
                or result not in _RESULTS
            ):
                _receipt_error()
            key = (candidate_id, cast(str, minor), cast(str, surface))
            if key in observed_cells:
                _receipt_error()
            observed_cells.add(key)
            failure_code = cell["failure_code"]
            versions = _mapping(cell["package_versions"])
            if result == "passed":
                if failure_code is not None or not versions:
                    _receipt_error()
                if (
                    versions.get("multimodal-knowledge-engine") != "0.1.1"
                    or versions.get("paddleocr") != "3.7.0"
                    or versions.get("paddlepaddle") != "3.3.1"
                ):
                    _receipt_error()
            elif failure_code not in _FAILURE_CODES or versions:
                _receipt_error()
            for name, version in versions.items():
                _safe(name)
                _version(version)
            _nonnegative_integer(cell["install_bytes"])
    expected_cells = {
        (candidate, minor, surface)
        for candidate in CANDIDATES
        for minor in _PYTHON_MINORS
        for surface in _SURFACES
    }
    if observed_candidates != set(CANDIDATES) or observed_cells != expected_cells:
        _receipt_error()
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    if _PRIVATE_RE.search(encoded):
        _receipt_error()


def canonical_receipt_bytes(receipt: object) -> bytes:
    validate_receipt(receipt)
    return (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def validate_committed_receipt_bytes(
    encoded: bytes,
    *,
    frozen_sha256: str,
) -> dict[str, object]:
    _digest(frozen_sha256)
    if hashlib.sha256(encoded).hexdigest() != frozen_sha256:
        _receipt_error()
    try:
        receipt = json.loads(encoded.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("candidate compatibility receipt is invalid") from error
    validate_receipt(receipt)
    if canonical_receipt_bytes(receipt) != encoded:
        _receipt_error()
    return _mapping(receipt)


def probe_interpreter(
    python: Path,
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> InterpreterIdentity:
    result = run_bounded(
        (
            str(python),
            "-I",
            "-c",
            (
                "import json,platform,sys;"
                "print(json.dumps({'executable':sys.executable,'version':platform.python_version(),"
                "'minor':f'{sys.version_info.major}.{sys.version_info.minor}'}))"
            ),
        ),
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        max_stdout_bytes=max_stdout_bytes,
        max_stderr_bytes=max_stderr_bytes,
    )
    if result.returncode != 0:
        raise CompatibilityError("interpreter_probe_failed")
    try:
        payload = json.loads(result.stdout)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CompatibilityError("interpreter_probe_failed") from error
    data = _mapping(payload)
    _exact(data, {"executable", "version", "minor"})
    executable = data["executable"]
    version = data["version"]
    minor = data["minor"]
    if (
        not isinstance(executable, str)
        or not isinstance(version, str)
        or not isinstance(minor, str)
    ):
        raise CompatibilityError("interpreter_probe_failed")
    return InterpreterIdentity(Path(executable), version, minor)


def run_package_matrix(config: CompatibilityConfig) -> dict[str, object]:
    repository = config.repository.resolve()
    wheel = config.wheel.resolve()
    staging = config.staging_root.resolve()
    cache = config.cache_root.resolve()
    output = config.output.resolve()
    prepared_wheelhouses = validate_acquisition_mode(
        config.allow_package_download,
        config.prepared_wheelhouses,
    )
    if not repository.is_dir() or not wheel.is_file():
        raise CompatibilityError("input_invalid")
    external_paths = (staging, cache) + (
        (prepared_wheelhouses,) if prepared_wheelhouses is not None else ()
    )
    if any(_within(path, repository) for path in external_paths):
        raise CompatibilityError("external_isolation_failed")
    if output != repository / "benchmarks/ocr/candidate-environments.json":
        raise CompatibilityError("output_invalid")
    if staging.exists() or cache.exists():
        raise CompatibilityError("call_owned_root_exists")
    staging.mkdir(mode=0o700, parents=True)
    cache.mkdir(mode=0o700, parents=True)
    runtime_root = staging / "runtime"
    wheelhouse_root = prepared_wheelhouses or staging / "wheelhouses"
    prepare_root = staging / "prepare"
    directories = [runtime_root]
    if prepared_wheelhouses is None:
        directories.extend((wheelhouse_root, prepare_root))
    for directory in directories:
        directory.mkdir(mode=0o700)
    online_env = _package_environment(staging / "home", cache, offline=False)
    offline_env = _package_environment(staging / "home", cache, offline=True)
    identities = tuple(
        probe_interpreter(
            path,
            cwd=staging,
            env=offline_env,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        for path in config.interpreters
    )
    plan = build_matrix_plan(
        wheel,
        cast(tuple[InterpreterIdentity, InterpreterIdentity], identities),
    )
    candidate_receipts: list[dict[str, object]] = []
    for candidate in CANDIDATES.values():
        wheelhouse = wheelhouse_root / candidate.candidate
        if prepared_wheelhouses is None:
            wheelhouse.mkdir(mode=0o700)
        elif not wheelhouse.is_dir():
            raise CompatibilityError("prepared_wheelhouses_invalid")
        _bind_candidate_mke_wheel(
            wheel,
            wheelhouse,
            seed=prepared_wheelhouses is None,
        )
        preparation_failures: dict[str, str] = {}
        if prepared_wheelhouses is None:
            for identity in sorted(identities, key=lambda item: item.minor):
                destination = prepare_root / f"{candidate.candidate}-{identity.minor}"
                destination.mkdir(mode=0o700)
                result = run_bounded(
                    candidate_download_command(
                        python=identity.python,
                        wheel=wheel,
                        candidate=candidate,
                        destination=destination,
                        cache=cache,
                    ),
                    cwd=staging,
                    env=online_env,
                    timeout_seconds=config.timeout_seconds,
                    max_stdout_bytes=config.max_stdout_bytes,
                    max_stderr_bytes=config.max_stderr_bytes,
                )
                if result.returncode != 0:
                    classification = classify_prepare_failure(result.stderr)
                    shutil.rmtree(destination)
                    if classification != "resolver_failed":
                        raise CompatibilityError("package_prepare_infrastructure_failed")
                    preparation_failures[identity.minor] = "resolver_unavailable"
                    continue
                _merge_wheels(destination, wheelhouse)
                shutil.rmtree(destination)
        distributions = _distribution_receipts(wheelhouse)
        cells: list[dict[str, object]] = []
        for cell in (item for item in plan.cells if item.candidate == candidate.candidate):
            if cell.python_minor in preparation_failures:
                cells.append(
                    _failed_cell(cell, "resolver_failed", preparation_failures[cell.python_minor])
                )
                continue
            cells.append(
                _run_offline_cell(
                    cell,
                    candidate=candidate,
                    wheel=wheel,
                    wheelhouse=wheelhouse,
                    runtime_root=runtime_root,
                    repository=repository,
                    environment=offline_env,
                    config=config,
                )
            )
        candidate_receipts.append(
            {
                "candidate": candidate.candidate,
                "profile": candidate.profile,
                "pins": list(candidate.requirements),
                "distributions": distributions,
                "download_bytes": sum(cast(int, item["bytes"]) for item in distributions),
                "cells": cells,
            }
        )
    receipt: dict[str, object] = {
        "schema": _SCHEMA,
        "profile": _RECEIPT_PROFILE,
        "platform": {"os": platform.system(), "architecture": platform.machine()},
        "mke_wheel_sha256": plan.mke_wheel_sha256,
        "candidates": candidate_receipts,
    }
    encoded = canonical_receipt_bytes(receipt)
    output.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, output)
    if any(runtime_root.iterdir()):
        raise CompatibilityError("cleanup_failed")
    return receipt


def _run_offline_cell(
    cell: MatrixCell,
    *,
    candidate: Candidate,
    wheel: Path,
    wheelhouse: Path,
    runtime_root: Path,
    repository: Path,
    environment: Mapping[str, str],
    config: CompatibilityConfig,
) -> dict[str, object]:
    cell_root = Path(tempfile.mkdtemp(prefix="cell-", dir=runtime_root))
    runtime = cell_root / "venv"
    try:
        create = run_bounded(
            (str(cell.python), "-m", "venv", str(runtime)),
            cwd=cell_root,
            env=environment,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        if create.returncode != 0:
            raise CompatibilityError("environment_create_failed")
        python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        install = run_bounded(
            offline_install_command(
                python=python,
                wheel=wheel,
                candidate=candidate,
                surface=cell.surface,
                wheelhouse=wheelhouse,
            ),
            cwd=cell_root,
            env=environment,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        if install.returncode != 0:
            return _failed_cell(
                cell,
                "offline_replay_failed",
                "offline_install_failed",
                install_bytes=_tree_bytes(runtime),
            )
        checked = run_bounded(
            (str(python), "-m", "pip", "check"),
            cwd=cell_root,
            env=environment,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        if checked.returncode != 0:
            return _failed_cell(
                cell,
                "validation_failed",
                "pip_check_failed",
                install_bytes=_tree_bytes(runtime),
            )
        identity = _run_import_doctor(
            python,
            cell=cell,
            candidate=candidate,
            cwd=cell_root,
            environment=environment,
            config=config,
        )
        if identity is None:
            return _failed_cell(
                cell,
                "validation_failed",
                "import_doctor_failed",
                install_bytes=_tree_bytes(runtime),
            )
        if not _valid_installed_identity(
            identity,
            runtime=runtime,
            repository=repository,
            expected_python=cell.python_version,
        ):
            return _failed_cell(
                cell,
                "validation_failed",
                "mke_identity_failed",
                install_bytes=_tree_bytes(runtime),
            )
        fake = run_bounded(
            (str(python), "-I", "-c", _FAKE_CHILD_PROOF),
            cwd=cell_root,
            env=environment,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        if fake.returncode != 0 or fake.stdout.strip() != b'{"status": "passed"}':
            return _failed_cell(
                cell,
                "validation_failed",
                "fake_child_failed",
                install_bytes=_tree_bytes(runtime),
            )
        versions = identity.get("package_versions")
        if not isinstance(versions, dict):
            raise CompatibilityError("identity_contract_failed")
        return {
            "python": cell.python_version,
            "python_minor": cell.python_minor,
            "surface": cell.surface,
            "result": "passed",
            "failure_code": None,
            "package_versions": dict(sorted(cast(dict[str, str], versions).items())),
            "install_bytes": _tree_bytes(runtime),
        }
    finally:
        shutil.rmtree(cell_root, ignore_errors=True)
        if cell_root.exists():
            raise CompatibilityError("cleanup_failed")


def _run_import_doctor(
    python: Path,
    *,
    cell: MatrixCell,
    candidate: Candidate,
    cwd: Path,
    environment: Mapping[str, str],
    config: CompatibilityConfig,
) -> dict[str, object] | None:
    modules = ["mke", "paddle", "paddleocr"]
    if "embedding" in cell.surface:
        modules.extend(["sentence_transformers", "sqlite_vec", "huggingface_hub"])
    if "transcription" in cell.surface:
        modules.extend(["faster_whisper", "av", "huggingface_hub"])
    program = (
        "import importlib,importlib.metadata as md,json,platform,sys;"
        f"mods={modules!r};"
        "[importlib.import_module(name) for name in mods];"
        "p=importlib.import_module('paddleocr');"
        f"assert hasattr(p,{candidate.required_symbol!r});"
        "versions={};"
        "[(versions.setdefault((d.metadata.get('Name') or '').lower().replace('_','-'),d.version)) "
        "for d in md.distributions() if d.metadata.get('Name')];"
        "import mke;"
        "print(json.dumps({'mke_file':mke.__file__,'sys_executable':sys.executable,"
        "'sys_prefix':sys.prefix,'sys_base_prefix':sys.base_prefix,"
        "'python':platform.python_version(),'package_versions':versions},sort_keys=True))"
    )
    result = run_bounded(
        (str(python), "-I", "-c", program),
        cwd=cwd,
        env=environment,
        timeout_seconds=config.timeout_seconds,
        max_stdout_bytes=config.max_stdout_bytes,
        max_stderr_bytes=config.max_stderr_bytes,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return cast(dict[str, object], payload)


def _valid_installed_identity(
    value: Mapping[str, object],
    *,
    runtime: Path,
    repository: Path,
    expected_python: str,
) -> bool:
    if set(value) != {
        "mke_file",
        "sys_executable",
        "sys_prefix",
        "sys_base_prefix",
        "python",
        "package_versions",
    }:
        return False
    module = value["mke_file"]
    executable = value["sys_executable"]
    prefix = value["sys_prefix"]
    base_prefix = value["sys_base_prefix"]
    version = value["python"]
    versions = value["package_versions"]
    if (
        not isinstance(module, str)
        or not isinstance(executable, str)
        or not isinstance(prefix, str)
        or not isinstance(base_prefix, str)
        or version != expected_python
        or not isinstance(versions, dict)
    ):
        return False
    try:
        module_path = Path(module).resolve()
        prefix_path = Path(prefix).resolve()
        base_prefix_path = Path(base_prefix).resolve()
    except OSError:
        return False
    return (
        _within(module_path, runtime)
        and not _within(module_path, repository)
        and _lexically_within(Path(executable), runtime)
        and _within(prefix_path, runtime)
        and not _within(prefix_path, repository)
        and not _within(base_prefix_path, runtime)
        and "site-packages" in module_path.parts
    )


def _failed_cell(
    cell: MatrixCell,
    result: str,
    failure_code: str,
    *,
    install_bytes: int = 0,
) -> dict[str, object]:
    return {
        "python": cell.python_version,
        "python_minor": cell.python_minor,
        "surface": cell.surface,
        "result": result,
        "failure_code": failure_code,
        "package_versions": {},
        "install_bytes": install_bytes,
    }


def _bind_candidate_mke_wheel(wheel: Path, wheelhouse: Path, *, seed: bool) -> None:
    try:
        source_metadata = wheel.lstat()
    except OSError as error:
        raise CompatibilityError("input_invalid") from error
    if (
        wheel.name != _MKE_WHEEL_FILENAME
        or wheel.is_symlink()
        or not stat.S_ISREG(source_metadata.st_mode)
    ):
        raise CompatibilityError("input_invalid")
    expected_digest = _sha256_file(wheel)
    target = wheelhouse / _MKE_WHEEL_FILENAME
    if not target.exists() and not target.is_symlink():
        if not seed:
            raise CompatibilityError("prepared_wheelhouses_invalid")
        created = False
        try:
            with wheel.open("rb") as source, target.open("xb") as destination:
                created = True
                shutil.copyfileobj(source, destination, length=1024 * 1024)
        except FileExistsError:
            pass
        except OSError as error:
            if created:
                target.unlink(missing_ok=True)
            raise CompatibilityError("package_prepare_failed") from error
    failure_code = "distribution_identity_drift" if seed else "prepared_wheelhouses_invalid"
    try:
        target_metadata = target.lstat()
    except OSError as error:
        raise CompatibilityError(failure_code) from error
    if (
        target.is_symlink()
        or not stat.S_ISREG(target_metadata.st_mode)
        or target_metadata.st_size != source_metadata.st_size
        or _sha256_file(target) != expected_digest
    ):
        raise CompatibilityError(failure_code)


def _merge_wheels(source: Path, destination: Path) -> None:
    entries = tuple(source.iterdir())
    if not entries:
        raise CompatibilityError("package_prepare_failed")
    for entry in entries:
        metadata = entry.lstat()
        if entry.is_symlink() or not stat.S_ISREG(metadata.st_mode) or entry.suffix != ".whl":
            raise CompatibilityError("package_prepare_failed")
        target = destination / entry.name
        if target.exists():
            if _sha256_file(target) != _sha256_file(entry):
                raise CompatibilityError("distribution_identity_drift")
            continue
        shutil.copyfile(entry, target)


def _distribution_receipts(wheelhouse: Path) -> list[dict[str, object]]:
    receipts: list[dict[str, object]] = []
    for path in sorted(wheelhouse.iterdir(), key=lambda item: item.name):
        metadata = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or path.suffix != ".whl":
            raise CompatibilityError("distribution_inventory_invalid")
        receipts.append(
            {"filename": path.name, "sha256": _sha256_file(path), "bytes": metadata.st_size}
        )
    return receipts


def _package_environment(home: Path, cache: Path, *, offline: bool) -> dict[str, str]:
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = home.parent / "tmp"
    temporary.mkdir(mode=0o700, exist_ok=True)
    environment = {
        "HOME": str(home),
        "TMPDIR": str(temporary),
        "TMP": str(temporary),
        "TEMP": str(temporary),
        "PIP_CACHE_DIR": str(cache),
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if offline:
        environment["PIP_NO_INDEX"] = "1"
    if os.name == "nt":
        for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT"):
            value = os.environ.get(key)
            if value is not None:
                environment[key] = value
    return environment


def _drain(stream: BinaryIO, capture: _Capture) -> None:
    try:
        while chunk := stream.read(_READ_CHUNK_BYTES):
            remaining = capture.limit - len(capture.data)
            if remaining > 0:
                capture.data.extend(chunk[:remaining])
            if len(chunk) > remaining:
                capture.exceeded.set()
    except (OSError, ValueError):
        capture.exceeded.set()


def _group_exists(pgid: int) -> bool:
    if os.name != "posix":
        return False
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _terminate(process: subprocess.Popen[bytes], pgid: int | None) -> None:
    if pgid is not None:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        deadline = time.monotonic() + _TERMINATION_GRACE_SECONDS
        while time.monotonic() < deadline:
            if process.poll() is not None and not _group_exists(pgid):
                break
            time.sleep(_POLL_SECONDS)
        if _group_exists(pgid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    elif process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=_TERMINATION_GRACE_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _tree_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        metadata = path.lstat()
        if stat.S_ISREG(metadata.st_mode):
            total += metadata.st_size
    return total


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _lexically_within(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(parent)))
    except ValueError:
        return False
    return True


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        _receipt_error()
    unknown = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in unknown):
        _receipt_error()
    return cast(dict[str, object], value)


def _exact(value: Mapping[str, object], keys: set[str]) -> None:
    if set(value) != keys:
        _receipt_error()


def _safe(value: object) -> str:
    if not isinstance(value, str) or _SAFE_RE.fullmatch(value) is None:
        _receipt_error()
    return value


def _version(value: object) -> str:
    if not isinstance(value, str) or _VERSION_RE.fullmatch(value) is None:
        _receipt_error()
    return value


def _digest(value: object) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _receipt_error()
    return value


def _nonnegative_integer(value: object) -> int:
    if type(value) is not int or value < 0:
        _receipt_error()
    return value


def _validate_distributions(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        _receipt_error()
    distributions: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in cast(list[object], value):
        distribution = _mapping(raw)
        _exact(distribution, {"filename", "sha256", "bytes"})
        filename = _safe(distribution["filename"])
        if filename in seen or Path(filename).name != filename or not filename.endswith(".whl"):
            _receipt_error()
        seen.add(filename)
        _digest(distribution["sha256"])
        _nonnegative_integer(distribution["bytes"])
        distributions.append(distribution)
    return distributions


def _receipt_error() -> NoReturn:
    raise ValueError("candidate compatibility receipt is invalid")


_FAKE_CHILD_PROOF = r"""
import json
import pathlib
import sys
import tempfile
from mke.evaluation.pdf_ocr_provider import ProviderCommand, run_provider
with tempfile.TemporaryDirectory(prefix="mke-ocr-fake-child-") as raw:
    root = pathlib.Path(raw)
    image = root / "page.png"
    image.write_bytes(b"image")
    payload = {
        "schema": "mke.pdf_ocr_eval_result.v1",
        "provider": "ppocrv6-medium-cpu-spike-v1",
        "profile": "phase0-200dpi-plain-text-v1",
        "page_number": 1,
        "lines": [
            {"text": "package proof", "confidence": 0.9, "box": [0, 0, 1, 1]}
        ],
        "normalized_text": "package proof",
        "duration_ms": 1,
    }
    child = (
        "import argparse,json,pathlib;"
        "p=argparse.ArgumentParser();"
        "p.add_argument('--input');p.add_argument('--output');"
        "p.add_argument('--page-number');a=p.parse_args();"
        "pathlib.Path(a.output).write_text(json.dumps(" + repr(payload) + "),"
        "encoding='utf-8')"
    )
    command = ProviderCommand(
        argv=(
            sys.executable,
            "-c",
            child,
            "--input",
            "{input}",
            "--output",
            "{output}",
            "--page-number",
            "{page_number}",
        ),
        provider="ppocrv6-medium-cpu-spike-v1",
        profile="phase0-200dpi-plain-text-v1",
        timeout_seconds=30,
    )
    result = run_provider(command,image_path=image,page_number=1,output_root=root / "output")
    assert result.normalized_text == "package proof"
print(json.dumps({"status":"passed"},sort_keys=True))
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--python", action="append", type=Path)
    parser.add_argument("--staging-root", type=Path)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-package-download", action="store_true")
    parser.add_argument("--prepare-models", action="store_true")
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--model-staging-root", type=Path)
    parser.add_argument("--model-final-root", type=Path)
    parser.add_argument("--model-output", type=Path)
    parser.add_argument("--prepared-wheelhouses", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=_DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.prepare_models:
            if (
                args.model_staging_root is None
                or args.model_final_root is None
                or args.model_output is None
            ):
                raise CompatibilityError("model_input_invalid")
            receipt = prepare_model_artifacts(
                ModelPreparationConfig(
                    staging_root=args.model_staging_root,
                    final_root=args.model_final_root,
                    output=args.model_output,
                    allow_model_download=args.allow_model_download,
                    timeout_seconds=args.timeout_seconds,
                )
            )
            encode = canonical_model_receipt_bytes
        else:
            if (
                args.repository is None
                or args.wheel is None
                or args.python is None
                or len(args.python) != 2
                or args.staging_root is None
                or args.cache_root is None
                or args.output is None
            ):
                raise CompatibilityError("input_invalid")
            receipt = run_package_matrix(
                CompatibilityConfig(
                    repository=args.repository,
                    wheel=args.wheel,
                    interpreters=(args.python[0], args.python[1]),
                    staging_root=args.staging_root,
                    cache_root=args.cache_root,
                    output=args.output,
                    allow_package_download=args.allow_package_download,
                    prepared_wheelhouses=args.prepared_wheelhouses,
                    timeout_seconds=args.timeout_seconds,
                )
            )
            encode = canonical_receipt_bytes
    except (CompatibilityError, ValueError) as error:
        failure = error.code if isinstance(error, CompatibilityError) else "receipt_invalid"
        if args.json:
            print(json.dumps({"status": "failed", "code": failure}, sort_keys=True))
        return 1
    if args.json:
        print(encode(receipt).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
