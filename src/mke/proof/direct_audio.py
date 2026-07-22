"""Deterministic model-free proof for the direct-audio product path."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Iterable
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO, Literal, Protocol, cast

from mke.adapters.audio import (
    AudioInspectionError,
    AudioProviderError,
    AudioSourceSnapshot,
    validate_audio_inspection_request,
)
from mke.adapters.audio.contracts import audio_extractor_fingerprint
from mke.adapters.audio.inspection import AudioInspectionObservation
from mke.adapters.audio.inspection_cli import inspect_audio
from mke.application import AudioIngestError, KnowledgeEngine
from mke.domain import (
    AudioMediaInfo,
    AudioTranscriptExtractionResult,
    AudioTranscriptSegment,
    IngestResult,
    ParsedAudioTranscript,
    RunState,
    SearchResultProvenance,
    TranscriptIntakeReport,
    TranscriptionProvenance,
)
from mke.interfaces.library_export import run_library_export

DirectAudioProofFailureCode = Literal[
    "fixture_invalid",
    "snapshot_failed",
    "inspection_failed",
    "ingest_failed",
    "publication_incomplete",
    "evidence_mismatch",
    "export_failed",
    "consumer_failed",
    "cleanup_failed",
]
DirectAudioProofNextStep = Literal[
    "check_fixture_receipt",
    "retry_with_stable_file",
    "choose_supported_file",
    "check_server_logs",
    "retry_when_owner_ready",
    "rerun_direct_audio_proof",
    "rerun_export_v2",
    "check_export_consumer",
]

DIRECT_AUDIO_PROOF_FAILURE_NEXT_STEPS: dict[
    DirectAudioProofFailureCode, DirectAudioProofNextStep
] = {
    "fixture_invalid": "check_fixture_receipt",
    "snapshot_failed": "retry_with_stable_file",
    "inspection_failed": "choose_supported_file",
    "ingest_failed": "check_server_logs",
    "publication_incomplete": "retry_when_owner_ready",
    "evidence_mismatch": "rerun_direct_audio_proof",
    "export_failed": "rerun_export_v2",
    "consumer_failed": "check_export_consumer",
    "cleanup_failed": "rerun_direct_audio_proof",
}

_FIXTURE_MEDIA = {
    "direct-audio.mp3": "audio/mpeg",
    "direct-audio.wav": "audio/wav",
    "direct-audio.m4a": "audio/mp4",
}
_CONSUMER_SUCCESS = {
    "schema_version": "mke.compiled_library_export_consumer.v2",
    "status": "passed",
    "export_schema": "mke.compiled_library_export.v2",
    "markdown_format": "mke.compiled_markdown.v2",
    "evidence_schema": "mke.evidence_ref.v1",
}
_RECEIPT_VALIDATION_SUCCESS = {
    "authority": "canonical_static_artifact",
    "binary_source_provenance": "not_claimed",
    "external_binary_redistribution": "not_performed",
    "redistribution_authority": "not_claimed",
    "retained_runtime_replay": "not_performed",
    "status": "passed",
}
_PROOF_CHILD_ENVIRONMENT = {
    "HF_HUB_OFFLINE": "1",
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONNOUSERSITE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "UV_OFFLINE": "1",
}
_NETWORK_DENIED_EXEC_SOURCE = r"""
import socket
import sys

def denied(*args, **kwargs):
    del args, kwargs
    raise RuntimeError("network_access_denied")

class DeniedSocket(socket.socket):
    def connect(self, *args, **kwargs):
        return denied(*args, **kwargs)
    def connect_ex(self, *args, **kwargs):
        return denied(*args, **kwargs)
    def sendto(self, *args, **kwargs):
        return denied(*args, **kwargs)
    def sendmsg(self, *args, **kwargs):
        return denied(*args, **kwargs)

socket.socket = DeniedSocket
socket.create_connection = denied
socket.getaddrinfo = denied
socket.gethostbyname = denied
socket.gethostbyname_ex = denied
source = sys.argv[1]
label = sys.argv[2]
arguments = sys.argv[3:]
sys.argv = [label, *arguments]
namespace = {
    "__cached__": None,
    "__file__": label,
    "__name__": "__main__",
    "__package__": None,
    "__spec__": None,
}
exec(compile(source, label, "exec", dont_inherit=True), namespace)
""".strip()
_NETWORK_DENIAL_CANARY = r"""
import json
import socket

try:
    socket.create_connection(("network-canary.invalid", 443))
except RuntimeError as error:
    if str(error) != "network_access_denied":
        raise
else:
    raise RuntimeError("network denial was not enforced")
print(json.dumps({"network_access":"denied","status":"passed"},sort_keys=True,separators=(",",":")))
""".strip()


class DirectAudioProvider(Protocol):
    def inspect(self, snapshot: AudioSourceSnapshot, *, suffix: str) -> AudioMediaInfo: ...

    def transcribe(
        self, snapshot: AudioSourceSnapshot, media: AudioMediaInfo, config: object
    ) -> AudioTranscriptExtractionResult: ...


class DirectAudioProofError(RuntimeError):
    def __init__(self, code: DirectAudioProofFailureCode) -> None:
        self.code: DirectAudioProofFailureCode = code
        super().__init__(code)


@dataclass(frozen=True)
class DirectAudioProofReport:
    schema_version: Literal["mke.direct_audio_proof.v1"]
    status: Literal["passed", "failed"]
    media_types: tuple[str, ...]
    published_run_count: int
    evidence_count: int
    timestamp_evidence: bool
    search_ask_projection_equal: bool
    evidence_schema: Literal["mke.evidence_ref.v1"]
    export_schema: Literal["mke.compiled_library_export.v2"]
    markdown_format: Literal["mke.compiled_markdown.v2"]
    consumer_status: Literal["passed", "failed"]
    network_access: Literal["not_used"]
    cleanup: bool
    failure_code: DirectAudioProofFailureCode | None = None
    next_step: DirectAudioProofNextStep | None = None

    def __post_init__(self) -> None:
        closed_fields = (
            self.schema_version == "mke.direct_audio_proof.v1"
            and self.status in ("passed", "failed")
            and self.evidence_schema == "mke.evidence_ref.v1"
            and self.export_schema == "mke.compiled_library_export.v2"
            and self.markdown_format == "mke.compiled_markdown.v2"
            and self.network_access == "not_used"
            and type(self.published_run_count) is int
            and self.published_run_count >= 0
            and type(self.evidence_count) is int
            and self.evidence_count >= 0
            and type(self.timestamp_evidence) is bool
            and type(self.search_ask_projection_equal) is bool
            and self.consumer_status in ("passed", "failed")
            and type(self.cleanup) is bool
        )
        if self.status == "passed":
            valid = (
                closed_fields
                and self.failure_code is None
                and self.next_step is None
                and self.media_types == ("audio/mpeg", "audio/wav", "audio/mp4")
                and self.published_run_count == 3
                and self.evidence_count == 3
                and self.timestamp_evidence
                and self.search_ask_projection_equal
                and self.consumer_status == "passed"
                and self.cleanup
            )
        else:
            valid = (
                closed_fields
                and self.media_types == ()
                and self.published_run_count == 0
                and self.evidence_count == 0
                and not self.timestamp_evidence
                and not self.search_ask_projection_equal
                and self.failure_code in DIRECT_AUDIO_PROOF_FAILURE_NEXT_STEPS
                and self.next_step
                == DIRECT_AUDIO_PROOF_FAILURE_NEXT_STEPS.get(self.failure_code)
                and self.consumer_status == "failed"
                and self.cleanup == (self.failure_code != "cleanup_failed")
            )
        if not valid:
            raise ValueError("direct-audio proof report is inconsistent")


class DeterministicAudioProvider:
    """Project-owned model-free provider used only by the deterministic proof."""

    def __init__(self, *, duration_ms: int = 3_630) -> None:
        self.duration_ms = duration_ms
        self.inspect_count = 0
        self.transcribe_count = 0

    def inspect(self, snapshot: AudioSourceSnapshot, *, suffix: str) -> AudioMediaInfo:
        snapshot.verify_owned_path()
        self.inspect_count += 1
        try:
            request = validate_audio_inspection_request(
                {
                    "path": str(snapshot.owned_path),
                    "expected_suffix": suffix,
                    "expected_sha256": snapshot.owned_identity.sha256,
                    "expected_bytes": snapshot.owned_identity.bytes,
                }
            )
            result = inspect_audio(
                request,
                _stream_inspector=lambda stream: self._inspect_stream(stream, suffix),
            )
            media = result["media"]
            snapshot.verify_owned_path()
            return AudioMediaInfo(
                container=media["container"],
                audio_codec=media["audio_codec"],
                channels=media["channels"],
                sample_rate_hz=media["sample_rate_hz"],
                duration_ms=media["duration_ms"],
            )
        except AudioInspectionError as error:
            raise AudioProviderError(
                "audio inspection failed", next_step="choose_supported_file"
            ) from error

    def _inspect_stream(
        self, stream: BinaryIO, suffix: str
    ) -> AudioInspectionObservation:
        del stream
        format_tokens, codec, profile = {
            ".mp3": (("mp3",), "mp3float", None),
            ".wav": (("wav",), "pcm_s16le", None),
            ".m4a": (("3g2", "3gp", "m4a", "mj2", "mov", "mp4"), "aac", "LC"),
        }[suffix]
        return AudioInspectionObservation(
            format_tokens=format_tokens,
            audio_stream_count=1,
            video_stream_count=0,
            subtitle_stream_count=0,
            data_stream_count=0,
            attachment_stream_count=0,
            audio_codec=codec,
            audio_profile=profile,
            channels=1,
            sample_rate_hz=16_000,
            duration_seconds=self.duration_ms / 1_000,
        )

    def transcribe(
        self, snapshot: AudioSourceSnapshot, media: AudioMediaInfo, config: object
    ) -> AudioTranscriptExtractionResult:
        del config
        snapshot.verify_owned_path()
        self.transcribe_count += 1
        provenance = TranscriptionProvenance(
            "faster-whisper",
            "small",
            "a" * 40,
            "1.2.3",
            "cpu",
            "int8",
            "auto",
            "en",
            "cache",
            0,
        )
        segment_end = min(1_000, media.duration_ms)
        report = TranscriptIntakeReport(
            "faster-whisper",
            "small",
            "a" * 40,
            "1.2.3",
            "cpu",
            "int8",
            "auto",
            "en",
            media.duration_ms,
            0,
            1,
            "cache",
        )
        return AudioTranscriptExtractionResult(
            ParsedAudioTranscript(
                media,
                (
                    AudioTranscriptSegment(
                        0, segment_end, "bounded synthetic speech remains traceable"
                    ),
                ),
                provenance,
            ),
            audio_extractor_fingerprint(provenance),
            report,
        )


def direct_audio_report_payload(report: DirectAudioProofReport) -> dict[str, object]:
    payload = asdict(report)
    payload["media_types"] = list(report.media_types)
    if report.failure_code is None:
        payload.pop("failure_code")
        payload.pop("next_step")
    return payload


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def _run_network_denied_source(
    source: str, label: str, arguments: tuple[str, ...], *, timeout: int = 30
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            _NETWORK_DENIED_EXEC_SOURCE,
            source,
            label,
            *arguments,
        ],
        capture_output=True,
        check=False,
        env=dict(_PROOF_CHILD_ENVIRONMENT),
        timeout=timeout,
    )


def _verify_network_denial() -> None:
    try:
        result = _run_network_denied_source(
            _NETWORK_DENIAL_CANARY, "<mke-network-denial-canary>", ()
        )
        expected = _canonical({"network_access": "denied", "status": "passed"})
    except (OSError, subprocess.SubprocessError) as error:
        raise DirectAudioProofError("ingest_failed") from error
    if result.returncode != 0 or result.stderr or result.stdout != expected:
        raise DirectAudioProofError("ingest_failed")


def _read_stable_script(
    path: Path, *, failure_code: DirectAudioProofFailureCode = "consumer_failed"
) -> str:
    descriptor: int | None = None
    try:
        before = path.lstat()
        if (
            stat.S_ISLNK(before.st_mode)
            or not stat.S_ISREG(before.st_mode)
            or not 0 < before.st_size <= 2 * 1024 * 1024
        ):
            raise DirectAudioProofError(failure_code)
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        if _stat_identity(opened) != _stat_identity(before):
            raise DirectAudioProofError(failure_code)
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                raise DirectAudioProofError(failure_code)
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise DirectAudioProofError(failure_code)
        after = os.fstat(descriptor)
        path_after = path.lstat()
        if (
            _stat_identity(after) != _stat_identity(opened)
            or _stat_identity(path_after) != _stat_identity(opened)
        ):
            raise DirectAudioProofError(failure_code)
        return b"".join(chunks).decode("utf-8")
    except DirectAudioProofError:
        raise
    except (OSError, UnicodeDecodeError) as error:
        raise DirectAudioProofError(failure_code) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _require_network_closed_consumer_source(source: str) -> None:
    forbidden_modules = {
        "_socket",
        "aiohttp",
        "http",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "urllib.request",
    }
    forbidden_os_calls = {"popen", "posix_spawn", "posix_spawnp", "system"}
    try:
        tree = ast.parse(source, filename="<compiled-library-consumer>")
    except SyntaxError as error:
        raise DirectAudioProofError("consumer_failed") from error
    for node in ast.walk(tree):
        imported: tuple[str, ...] = ()
        if isinstance(node, ast.Import):
            imported = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported = (node.module,)
        if any(
            name in forbidden_modules
            or any(name.startswith(f"{prefix}.") for prefix in forbidden_modules)
            for name in imported
        ):
            raise DirectAudioProofError("consumer_failed")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
            and node.func.attr in forbidden_os_calls
        ):
            raise DirectAudioProofError("consumer_failed")


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _run_canonical_receipt_validator(receipt_path: Path) -> dict[str, object]:
    script = receipt_path.parents[2] / "scripts" / "direct_audio_dependency_receipt.py"
    try:
        script_source = _read_stable_script(script, failure_code="fixture_invalid")
        tree = ast.parse(script_source, filename=str(script))
        bootstrap_assignment = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "_CONTROLLER_BOOTSTRAP_SOURCE"
                    for target in node.targets
                )
            ),
            None,
        )
        if bootstrap_assignment is None:
            raise DirectAudioProofError("fixture_invalid")
        string_literals = [
            node.value
            for node in ast.walk(bootstrap_assignment.value)
            if isinstance(node, ast.Constant) and type(node.value) is str
        ]
        if not string_literals:
            raise DirectAudioProofError("fixture_invalid")
        raw_bootstrap = max(string_literals, key=len)
        receipt_value: object = json.loads(receipt_path.read_bytes().decode("ascii"))
        if type(receipt_value) is not dict:
            raise DirectAudioProofError("fixture_invalid")
        controller = cast(dict[str, object], receipt_value).get("controller_execution")
        if type(controller) is not dict:
            raise DirectAudioProofError("fixture_invalid")
        contract_sha256 = cast(dict[str, object], controller).get(
            "bootstrap_contract_sha256"
        )
        if (
            type(contract_sha256) is not str
            or len(contract_sha256) != 64
            or any(character not in "0123456789abcdef" for character in contract_sha256)
        ):
            raise DirectAudioProofError("fixture_invalid")
        bootstrap = raw_bootstrap.strip().replace(
            "__CONTRACT_SHA256__", contract_sha256
        )
        result = _run_network_denied_source(
            bootstrap,
            "<mke-direct-audio-receipt-bootstrap>",
            (
                "--",
                str(script),
                "--validate-receipt",
                str(receipt_path),
                "--json",
            ),
        )
        parsed: object = json.loads(result.stdout.decode("ascii"))
        if (
            result.returncode != 0
            or result.stderr
            or type(parsed) is not dict
        ):
            raise DirectAudioProofError("fixture_invalid")
        payload = cast(dict[str, object], parsed)
        if result.stdout != _canonical(payload):
            raise DirectAudioProofError("fixture_invalid")
        return payload
    except DirectAudioProofError:
        raise
    except (
        OSError,
        RuntimeError,
        SyntaxError,
        subprocess.SubprocessError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise DirectAudioProofError("fixture_invalid") from error


def _validate_fixture_authority(
    fixture_root: Path, receipt_path: Path
) -> dict[Path, tuple[int, str]]:
    try:
        validator_payload = _run_canonical_receipt_validator(receipt_path)
        receipt_bytes = receipt_path.read_bytes()
        parsed: object = json.loads(receipt_bytes.decode("ascii"))
        if type(parsed) is not dict:
            raise DirectAudioProofError("fixture_invalid")
        normalized = cast(dict[str, object], parsed)
        if receipt_bytes != _canonical(normalized):
            raise DirectAudioProofError("fixture_invalid")
        receipt_digest = normalized.get("receipt_sha256")
        digest_payload = {
            key: value for key, value in normalized.items() if key != "receipt_sha256"
        }
        if (
            normalized.get("schema_version") != "mke.direct_audio_dependency_receipt.v1"
            or type(receipt_digest) is not str
            or hashlib.sha256(_canonical(digest_payload)[:-1]).hexdigest()
            != receipt_digest
        ):
            raise DirectAudioProofError("fixture_invalid")
        if validator_payload != {
            **_RECEIPT_VALIDATION_SUCCESS,
            "canonical_payload_sha256": receipt_digest,
            "committed_file_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        }:
            raise DirectAudioProofError("fixture_invalid")
        rows = normalized.get("fixtures")
        if type(rows) is not list:
            raise DirectAudioProofError("fixture_invalid")
        by_name: dict[str, dict[str, object]] = {}
        for raw_row in cast(list[object], rows):
            if type(raw_row) is not dict:
                continue
            row = cast(dict[str, object], raw_row)
            filename = row.get("filename")
            if type(filename) is str:
                by_name[filename] = row
        if set(by_name) != set(_FIXTURE_MEDIA):
            raise DirectAudioProofError("fixture_invalid")
        authority: dict[Path, tuple[int, str]] = {}
        for name in _FIXTURE_MEDIA:
            path = fixture_root / name
            before = path.lstat()
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
                raise DirectAudioProofError("fixture_invalid")
            data = path.read_bytes()
            after = path.lstat()
            row = by_name[name]
            if (
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or row.get("bytes") != len(data)
                or row.get("sha256") != hashlib.sha256(data).hexdigest()
                or row.get("artifact_scope") != "repository_distributed"
                or row.get("redistribution") != "permitted"
            ):
                raise DirectAudioProofError("fixture_invalid")
            authority[path.resolve()] = (len(data), hashlib.sha256(data).hexdigest())
        return authority
    except DirectAudioProofError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise DirectAudioProofError("fixture_invalid") from exc


def _verify_stable_inputs(fixture_root: Path) -> None:
    try:
        for name in _FIXTURE_MEDIA:
            path = fixture_root / name
            before = path.lstat()
            with path.open("rb") as stream:
                while stream.read(64 * 1024):
                    pass
            after = path.lstat()
            if (
                not stat.S_ISREG(before.st_mode)
                or stat.S_ISLNK(before.st_mode)
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            ):
                raise DirectAudioProofError("snapshot_failed")
    except DirectAudioProofError:
        raise
    except OSError as exc:
        raise DirectAudioProofError("snapshot_failed") from exc


def _evidence_projection(
    values: Iterable[SearchResultProvenance],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.result.evidence_id,
            item.result.source_id,
            item.content_fingerprint,
            item.result.publication_id,
            item.publication_revision,
            item.run_id,
            item.result.locator_kind,
            item.result.locator_start,
            item.result.locator_end,
            item.result.text,
        )
        for item in values
    )


@dataclass(frozen=True)
class _ReceiptBoundAudioProvider:
    delegate: DirectAudioProvider
    authority: dict[Path, tuple[int, str]]

    def inspect(self, snapshot: AudioSourceSnapshot, *, suffix: str) -> AudioMediaInfo:
        expected = self.authority.get(snapshot.original_path)
        observed = (snapshot.source_identity.bytes, snapshot.source_identity.sha256)
        owned = (snapshot.owned_identity.bytes, snapshot.owned_identity.sha256)
        if expected is None or observed != expected or owned != expected:
            raise AudioProviderError(
                "audio source identity changed during intake",
                next_step="retry_with_stable_file",
            )
        return self.delegate.inspect(snapshot, suffix=suffix)

    def transcribe(
        self, snapshot: AudioSourceSnapshot, media: AudioMediaInfo, config: object
    ) -> AudioTranscriptExtractionResult:
        return self.delegate.transcribe(snapshot, media, config)


@dataclass(frozen=True)
class _WorkspaceAuthority:
    parent_descriptor: int
    workspace_descriptor: int
    identity: tuple[int, int, int]


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _directory_identity(value: os.stat_result) -> tuple[int, int, int]:
    return (value.st_dev, value.st_ino, value.st_mode)


def _create_workspace(workspace: Path) -> _WorkspaceAuthority:
    parent_descriptor: int | None = None
    workspace_descriptor: int | None = None
    created = False
    try:
        if workspace.name in {"", ".", ".."}:
            raise OSError("invalid workspace name")
        parent_descriptor = os.open(workspace.parent, _directory_flags())
        try:
            os.stat(workspace.name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise OSError("workspace already exists")
        os.mkdir(workspace.name, mode=0o700, dir_fd=parent_descriptor)
        created = True
        observed = os.stat(
            workspace.name, dir_fd=parent_descriptor, follow_symlinks=False
        )
        identity = _directory_identity(observed)
        if not stat.S_ISDIR(observed.st_mode):
            raise OSError("workspace is not a directory")
        workspace_descriptor = os.open(
            workspace.name, _directory_flags(), dir_fd=parent_descriptor
        )
        if _directory_identity(os.fstat(workspace_descriptor)) != identity:
            raise OSError("workspace identity changed")
        return _WorkspaceAuthority(parent_descriptor, workspace_descriptor, identity)
    except OSError as error:
        if workspace_descriptor is not None:
            os.close(workspace_descriptor)
        if created and parent_descriptor is not None:
            try:
                os.rmdir(workspace.name, dir_fd=parent_descriptor)
            except OSError:
                pass
        if parent_descriptor is not None:
            os.close(parent_descriptor)
        raise DirectAudioProofError("snapshot_failed") from error


def _cleanup_workspace(workspace: Path, authority: _WorkspaceAuthority) -> None:
    try:
        if _directory_identity(os.fstat(authority.workspace_descriptor)) != authority.identity:
            raise OSError("workspace descriptor identity changed")
        for name in os.listdir(authority.workspace_descriptor):
            observed = os.stat(
                name,
                dir_fd=authority.workspace_descriptor,
                follow_symlinks=False,
            )
            if stat.S_ISDIR(observed.st_mode):
                shutil.rmtree(name, dir_fd=authority.workspace_descriptor)
            else:
                os.unlink(name, dir_fd=authority.workspace_descriptor)
        if os.listdir(authority.workspace_descriptor):
            raise OSError("workspace cleanup was incomplete")
        current = os.stat(
            workspace.name,
            dir_fd=authority.parent_descriptor,
            follow_symlinks=False,
        )
        if _directory_identity(current) != authority.identity:
            raise OSError("workspace path identity changed")
        os.rmdir(workspace.name, dir_fd=authority.parent_descriptor)
    except OSError as error:
        raise DirectAudioProofError("cleanup_failed") from error
    finally:
        os.close(authority.workspace_descriptor)
        os.close(authority.parent_descriptor)


def _run_consumer(consumer_path: Path, export: Path) -> None:
    try:
        source = _read_stable_script(consumer_path)
        _require_network_closed_consumer_source(source)
        result = _run_network_denied_source(
            source,
            str(consumer_path),
            ("--export", str(export), "--json"),
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise DirectAudioProofError("consumer_failed") from exc
    if result.returncode != 0 or result.stderr or payload != _CONSUMER_SUCCESS:
        raise DirectAudioProofError("consumer_failed")


def _execute_direct_audio_proof(
    *,
    fixture_root: Path,
    receipt_path: Path,
    consumer_path: Path,
    workspace: Path,
    provider: DirectAudioProvider,
) -> DirectAudioProofReport:
    _verify_network_denial()
    fixture_authority = _validate_fixture_authority(fixture_root, receipt_path)
    _verify_stable_inputs(fixture_root)
    bound_provider = _ReceiptBoundAudioProvider(provider, fixture_authority)
    engine = KnowledgeEngine(
        workspace / "library.sqlite",
        audio_provider=bound_provider,
        audio_transcription_config=object(),
        audio_preflight=lambda: None,
    )
    results: list[IngestResult] = []
    try:
        for name in _FIXTURE_MEDIA:
            try:
                results.append(engine.ingest_file(fixture_root / name))
            except AudioIngestError as exc:
                code: DirectAudioProofFailureCode
                if exc.next_step == "retry_with_stable_file":
                    code = "snapshot_failed"
                elif exc.next_step in {"choose_supported_file", "choose_smaller_file"}:
                    code = "inspection_failed"
                else:
                    code = "ingest_failed"
                raise DirectAudioProofError(code) from exc
        if any(
            result.run_state is not RunState.PUBLISHED or result.evidence_count != 1
            for result in results
        ):
            raise DirectAudioProofError("publication_incomplete")
        observation = engine.observe_active_publications()
        if (
            observation.active_publication_count != 3
            or observation.active_evidence_count != 3
        ):
            raise DirectAudioProofError("publication_incomplete")
        search = engine.search_provenance_snapshot("bounded synthetic speech")
        ask = engine.ask_provenance_snapshot("bounded synthetic speech")
        search_projection = _evidence_projection(search.results)
        ask_projection = _evidence_projection(ask.evidence)
        if (
            len(search_projection) != 3
            or ask.result.answer_status != "evidence_found"
            or search_projection != ask_projection
            or search.observation != observation
            or ask.observation != observation
            or any(
                item.result.locator_kind != "timestamp_ms" for item in search.results
            )
        ):
            raise DirectAudioProofError("evidence_mismatch")
    finally:
        try:
            engine.close()
        except Exception as exc:
            raise DirectAudioProofError("ingest_failed") from exc

    export = workspace / "compiled-library"
    try:
        rendered = io.StringIO()
        with redirect_stdout(rendered):
            exit_code = run_library_export(
                workspace / "library.sqlite",
                export.name,
                json_output=True,
                format_version="v2",
                parent=workspace,
            )
        parsed_response: object = json.loads(rendered.getvalue())
        response = (
            cast(dict[str, object], parsed_response)
            if type(parsed_response) is dict
            else None
        )
        if (
            exit_code != 0
            or response is None
            or response.get("schema_version")
            != "mke.compiled_library_export_response.v2"
            or response.get("ok") is not True
            or response.get("source_count") != 3
            or response.get("evidence_count") != 3
        ):
            raise DirectAudioProofError("export_failed")
        parsed_manifest: object = json.loads(
            (export / "export-manifest.json").read_bytes()
        )
        if type(parsed_manifest) is not dict:
            raise DirectAudioProofError("export_failed")
        manifest = cast(dict[str, object], parsed_manifest)
    except DirectAudioProofError:
        raise
    except Exception as exc:
        raise DirectAudioProofError("export_failed") from exc
    raw_sources = manifest.get("sources")
    if type(raw_sources) is not list:
        raise DirectAudioProofError("export_failed")
    media_types: set[object] = set()
    for raw_source in cast(list[object], raw_sources):
        if type(raw_source) is not dict:
            raise DirectAudioProofError("export_failed")
        media_types.add(cast(dict[str, object], raw_source).get("media_type"))
    if (
        manifest.get("schema_version") != "mke.compiled_library_export.v2"
        or manifest.get("markdown_format") != "mke.compiled_markdown.v2"
        or manifest.get("evidence_schema") != "mke.evidence_ref.v1"
        or media_types != set(_FIXTURE_MEDIA.values())
    ):
        raise DirectAudioProofError("export_failed")
    _run_consumer(consumer_path, export)
    return DirectAudioProofReport(
        "mke.direct_audio_proof.v1",
        "passed",
        tuple(_FIXTURE_MEDIA.values()),
        3,
        3,
        True,
        True,
        "mke.evidence_ref.v1",
        "mke.compiled_library_export.v2",
        "mke.compiled_markdown.v2",
        "passed",
        "not_used",
        True,
    )


def _failed_report(
    code: DirectAudioProofFailureCode, *, cleanup: bool
) -> DirectAudioProofReport:
    return DirectAudioProofReport(
        "mke.direct_audio_proof.v1",
        "failed",
        (),
        0,
        0,
        False,
        False,
        "mke.evidence_ref.v1",
        "mke.compiled_library_export.v2",
        "mke.compiled_markdown.v2",
        "failed",
        "not_used",
        cleanup,
        code,
        DIRECT_AUDIO_PROOF_FAILURE_NEXT_STEPS[code],
    )


def run_direct_audio_proof(
    *,
    fixture_root: Path,
    workspace: Path,
    provider: DirectAudioProvider,
    receipt_path: Path | None = None,
    consumer_path: Path | None = None,
) -> DirectAudioProofReport:
    """Run one offline model-free product proof and remove all call-owned state."""

    error: DirectAudioProofFailureCode | None = None
    report: DirectAudioProofReport | None = None
    workspace_authority: _WorkspaceAuthority | None = None
    try:
        repository_root = fixture_root.parents[2]
        if receipt_path is None:
            receipt_path = repository_root / "benchmarks/audio/dependency-artifacts.json"
        if consumer_path is None:
            consumer_path = (
                repository_root / "scripts/compiled_library_export_consumer_v2.py"
            )
        workspace_authority = _create_workspace(workspace)
        report = _execute_direct_audio_proof(
            fixture_root=fixture_root,
            receipt_path=receipt_path,
            consumer_path=consumer_path,
            workspace=workspace,
            provider=provider,
        )
    except DirectAudioProofError as exc:
        error = exc.code
    except Exception:
        error = "ingest_failed"
    finally:
        if workspace_authority is not None:
            try:
                _cleanup_workspace(workspace, workspace_authority)
            except DirectAudioProofError:
                error = "cleanup_failed"
    if error is not None:
        return _failed_report(error, cleanup=error != "cleanup_failed")
    assert report is not None
    return report
