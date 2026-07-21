"""Immutable direct-audio snapshot and closed inspection contracts."""

from __future__ import annotations

import hashlib
import math
import os
import re
import secrets
import stat
import sys
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, TypedDict, cast

from mke.adapters.audio.contracts import AudioTranscriptionLimits
from mke.domain import AudioMediaInfo

_BUFFER_BYTES = 1024 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST_FIELDS = frozenset({"path", "expected_suffix", "expected_sha256", "expected_bytes"})
_RESULT_FIELDS = frozenset({"schema_version", "media", "observed_sha256", "observed_bytes"})
_MEDIA_FIELDS = frozenset({"container", "audio_codec", "channels", "sample_rate_hz", "duration_ms"})
_OBSERVATION_FIELDS = frozenset(
    {
        "format_tokens",
        "audio_stream_count",
        "video_stream_count",
        "subtitle_stream_count",
        "data_stream_count",
        "attachment_stream_count",
        "audio_codec",
        "audio_profile",
        "channels",
        "sample_rate_hz",
        "duration_seconds",
    }
)
_DEFAULT_LIMITS = AudioTranscriptionLimits()


class AudioSnapshotError(ValueError):
    """Raised when immutable snapshot authority cannot be established or cleaned."""


class AudioInspectionError(ValueError):
    """Raised when the closed inspection protocol or profile is invalid."""


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    bytes: int
    modified_ns: int
    changed_ns: int
    sha256: str


@dataclass
class AudioSourceSnapshot:
    original_path: Path
    owned_root: Path
    owned_path: Path
    source_identity: FileIdentity
    owned_identity: FileIdentity
    _owned_root_identity: tuple[int, int, int] = field(repr=False, compare=False)

    def verify_source_path(self) -> None:
        verify_source_path(self)

    def verify_owned_path(self) -> None:
        verify_owned_path(self)


class AudioInspectionObservation(TypedDict):
    format_tokens: tuple[str, ...]
    audio_stream_count: int
    video_stream_count: int
    subtitle_stream_count: int
    data_stream_count: int
    attachment_stream_count: int
    audio_codec: str
    audio_profile: str | None
    channels: int
    sample_rate_hz: int
    duration_seconds: float


class AudioMediaInfoPayload(TypedDict):
    container: Literal["mp3", "wav", "m4a"]
    audio_codec: Literal["mp3", "pcm_s16le", "aac"]
    channels: int
    sample_rate_hz: int
    duration_ms: int


class AudioInspectionRequest(TypedDict):
    path: str
    expected_suffix: Literal[".mp3", ".wav", ".m4a"]
    expected_sha256: str
    expected_bytes: int


class AudioInspectionResult(TypedDict):
    schema_version: Literal["mke.audio_inspection.v1"]
    media: AudioMediaInfoPayload
    observed_sha256: str
    observed_bytes: int


def snapshot_audio_source(
    source: Path,
    owned_root: Path,
    *,
    limits: AudioTranscriptionLimits = _DEFAULT_LIMITS,
) -> AudioSourceSnapshot:
    original_path = _absolute_path(source)
    private_root = _absolute_path(owned_root)
    if private_root == original_path.parent or private_root in original_path.parents:
        raise AudioSnapshotError("owned_root_overlap")
    _reject_symlink_components(original_path.parent, "source_parent_symlink")
    try:
        initial_stat = original_path.lstat()
    except OSError as error:
        raise AudioSnapshotError("source_not_regular") from error
    if stat.S_ISLNK(initial_stat.st_mode) or not stat.S_ISREG(initial_stat.st_mode):
        raise AudioSnapshotError("source_not_regular")
    if initial_stat.st_size <= 0:
        raise AudioSnapshotError("source_empty")
    if initial_stat.st_size > limits.max_input_bytes:
        raise AudioSnapshotError("source_limit_exceeded")

    _reject_symlink_components(private_root.parent, "owned_root_invalid")
    if os.path.lexists(private_root):
        raise AudioSnapshotError("owned_root_exists")

    root_identity: tuple[int, int, int] | None = None
    source_fd: int | None = None
    target_fd: int | None = None
    target_identity: tuple[int, int, int] | None = None
    staging_path: Path | None = None
    sealed_path: Path | None = None
    try:
        os.mkdir(private_root, 0o700)
        root_stat = private_root.lstat()
        root_identity = _directory_identity(root_stat)
        if not stat.S_ISDIR(root_stat.st_mode) or stat.S_IMODE(root_stat.st_mode) != 0o700:
            raise AudioSnapshotError("owned_root_invalid")

        source_fd = os.open(original_path, _read_flags())
        opened_stat = os.fstat(source_fd)
        if _stat_tuple(opened_stat) != _stat_tuple(initial_stat):
            raise AudioSnapshotError("source_identity_mismatch")
        if _stat_tuple(original_path.lstat()) != _stat_tuple(initial_stat):
            raise AudioSnapshotError("source_identity_mismatch")

        staging_path = private_root / f".staging-{secrets.token_hex(16)}"
        target_fd = os.open(
            staging_path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        target_identity = _node_identity(os.fstat(target_fd))
        copied_bytes, copied_sha256 = _copy_descriptor(source_fd, target_fd, limits.max_input_bytes)
        os.fsync(target_fd)
        second_bytes, second_sha256 = _hash_descriptor(source_fd, limits.max_input_bytes)
        final_stat = os.fstat(source_fd)
        final_path_stat = original_path.lstat()
        if (
            copied_bytes != initial_stat.st_size
            or second_bytes != initial_stat.st_size
            or copied_sha256 != second_sha256
            or _stat_tuple(final_stat) != _stat_tuple(initial_stat)
            or _stat_tuple(final_path_stat) != _stat_tuple(initial_stat)
        ):
            raise AudioSnapshotError("source_identity_mismatch")

        os.fchmod(target_fd, 0o400)
        os.fsync(target_fd)
        sealed_path = private_root / f"snapshot-{secrets.token_hex(16)}"
        os.replace(staging_path, sealed_path)
        staging_path = None
        os.close(target_fd)
        target_fd = None

        source_identity = _identity(initial_stat, second_sha256)
        owned_identity = _read_path_identity(
            sealed_path,
            code="owned_identity_mismatch",
            max_bytes=limits.max_input_bytes,
        )
        if (
            owned_identity.bytes != source_identity.bytes
            or owned_identity.sha256 != source_identity.sha256
            or stat.S_IMODE(owned_identity.mode) != 0o400
        ):
            raise AudioSnapshotError("owned_identity_mismatch")
        snapshot = AudioSourceSnapshot(
            original_path=original_path,
            owned_root=private_root,
            owned_path=sealed_path,
            source_identity=source_identity,
            owned_identity=owned_identity,
            _owned_root_identity=root_identity,
        )
        verify_source_path(snapshot)
        verify_owned_path(snapshot)
        return snapshot
    except AudioSnapshotError:
        _cleanup_failed_snapshot(
            private_root,
            root_identity=root_identity,
            target_identity=target_identity,
            staging_path=staging_path,
            sealed_path=sealed_path,
        )
        raise
    except OSError as error:
        _cleanup_failed_snapshot(
            private_root,
            root_identity=root_identity,
            target_identity=target_identity,
            staging_path=staging_path,
            sealed_path=sealed_path,
        )
        raise AudioSnapshotError("snapshot_creation_failed") from error
    finally:
        if target_fd is not None:
            os.close(target_fd)
        if source_fd is not None:
            os.close(source_fd)


def verify_source_path(snapshot: AudioSourceSnapshot) -> None:
    observed = _read_path_identity(
        snapshot.original_path,
        code="source_identity_mismatch",
        max_bytes=snapshot.source_identity.bytes,
    )
    require_matching_identity(
        snapshot.source_identity,
        observed,
        code="source_identity_mismatch",
    )


def verify_owned_path(snapshot: AudioSourceSnapshot) -> None:
    _require_owned_root(snapshot)
    observed = _read_path_identity(
        snapshot.owned_path,
        code="owned_identity_mismatch",
        max_bytes=snapshot.owned_identity.bytes,
    )
    require_matching_identity(
        snapshot.owned_identity,
        observed,
        code="owned_identity_mismatch",
    )


def require_matching_identity(
    expected: FileIdentity,
    observed: FileIdentity,
    *,
    code: str = "file_identity_mismatch",
) -> None:
    if expected != observed:
        raise AudioSnapshotError(code)


def cleanup_audio_snapshot(snapshot: AudioSourceSnapshot) -> None:
    root_fd: int | None = None
    try:
        try:
            verify_owned_path(snapshot)
        except AudioSnapshotError as error:
            raise AudioSnapshotError("snapshot_cleanup_failed") from error
        if snapshot.owned_path.parent != snapshot.owned_root:
            raise AudioSnapshotError("snapshot_cleanup_failed")
        root_identity = snapshot._owned_root_identity  # pyright: ignore[reportPrivateUsage]
        root_fd = os.open(snapshot.owned_root, _directory_flags())
        if _directory_identity(os.fstat(root_fd)) != root_identity:
            raise AudioSnapshotError("snapshot_cleanup_failed")
        observed = os.stat(
            snapshot.owned_path.name,
            dir_fd=root_fd,
            follow_symlinks=False,
        )
        if _stat_tuple(observed) != _file_identity_tuple(snapshot.owned_identity):
            raise AudioSnapshotError("snapshot_cleanup_failed")
        os.unlink(snapshot.owned_path.name, dir_fd=root_fd)
        _require_owned_root(snapshot)
        root_path_unchanged = _remove_owned_root_entry(
            snapshot.owned_root,
            root_identity,
            root_fd,
        )
        if not root_path_unchanged or os.path.lexists(snapshot.owned_root):
            raise AudioSnapshotError("snapshot_cleanup_failed")
    except AudioSnapshotError as error:
        if str(error) == "snapshot_cleanup_failed":
            raise
        raise AudioSnapshotError("snapshot_cleanup_failed") from error
    except OSError as error:
        raise AudioSnapshotError("snapshot_cleanup_failed") from error
    finally:
        if root_fd is not None:
            os.close(root_fd)


def validate_audio_inspection_request(payload: object) -> AudioInspectionRequest:
    if not isinstance(payload, dict):
        raise AudioInspectionError("inspection_request_invalid")
    value = cast(dict[str, object], payload)
    if frozenset(value) != _REQUEST_FIELDS:
        raise AudioInspectionError("inspection_request_invalid")
    path = value["path"]
    suffix = value["expected_suffix"]
    digest = value["expected_sha256"]
    byte_count = value["expected_bytes"]
    if (
        type(path) is not str
        or not path
        or not Path(path).is_absolute()
        or suffix not in {".mp3", ".wav", ".m4a"}
        or type(digest) is not str
        or _SHA256_RE.fullmatch(digest) is None
        or type(byte_count) is not int
        or not 0 < byte_count <= _DEFAULT_LIMITS.max_input_bytes
    ):
        raise AudioInspectionError("inspection_request_invalid")
    return AudioInspectionRequest(
        path=path,
        expected_suffix=cast(Literal[".mp3", ".wav", ".m4a"], suffix),
        expected_sha256=digest,
        expected_bytes=byte_count,
    )


def parse_audio_inspection_result(
    payload: object,
    *,
    request: AudioInspectionRequest,
) -> AudioInspectionResult:
    if not isinstance(payload, dict):
        raise AudioInspectionError("inspection_result_invalid")
    value = cast(dict[str, object], payload)
    if frozenset(value) != _RESULT_FIELDS:
        raise AudioInspectionError("inspection_result_invalid")
    digest = value["observed_sha256"]
    byte_count = value["observed_bytes"]
    if (
        value["schema_version"] != "mke.audio_inspection.v1"
        or type(digest) is not str
        or _SHA256_RE.fullmatch(digest) is None
        or type(byte_count) is not int
    ):
        raise AudioInspectionError("inspection_result_invalid")
    if digest != request["expected_sha256"] or byte_count != request["expected_bytes"]:
        raise AudioInspectionError("inspection_identity_mismatch")
    media = _parse_media_payload(value["media"])
    expected = {
        ".mp3": ("mp3", "mp3"),
        ".wav": ("wav", "pcm_s16le"),
        ".m4a": ("m4a", "aac"),
    }[request["expected_suffix"]]
    if (media["container"], media["audio_codec"]) != expected:
        raise AudioInspectionError("inspection_result_invalid")
    return AudioInspectionResult(
        schema_version="mke.audio_inspection.v1",
        media=media,
        observed_sha256=digest,
        observed_bytes=byte_count,
    )


def _normalize_audio_profile(  # pyright: ignore[reportUnusedFunction]
    observation: AudioInspectionObservation,
    *,
    expected_suffix: str,
) -> AudioMediaInfo:
    value = cast(dict[str, object], observation)
    try:
        if frozenset(value) != _OBSERVATION_FIELDS:
            raise ValueError
        counts = tuple(
            value[field]
            for field in (
                "audio_stream_count",
                "video_stream_count",
                "subtitle_stream_count",
                "data_stream_count",
                "attachment_stream_count",
            )
        )
        if any(type(count) is not int for count in counts) or counts != (1, 0, 0, 0, 0):
            raise ValueError
        raw_tokens = value["format_tokens"]
        if not isinstance(raw_tokens, tuple) or not raw_tokens:
            raise ValueError
        untyped_tokens = cast(tuple[object, ...], raw_tokens)
        if any(type(token) is not str or not token for token in untyped_tokens):
            raise ValueError
        typed_tokens = cast(tuple[str, ...], untyped_tokens)
        tokens = frozenset(typed_tokens)
        if len(tokens) != len(typed_tokens):
            raise ValueError
        codec = value["audio_codec"]
        profile = value["audio_profile"]
        if expected_suffix == ".mp3":
            if (
                tokens != frozenset({"mp3"})
                or codec not in {"mp3", "mp3float"}
                or profile is not None
            ):
                raise ValueError
            container, normalized_codec = "mp3", "mp3"
        elif expected_suffix == ".wav":
            if tokens != frozenset({"wav"}) or codec != "pcm_s16le" or profile is not None:
                raise ValueError
            container, normalized_codec = "wav", "pcm_s16le"
        elif expected_suffix == ".m4a":
            if (
                tokens != frozenset({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"})
                or codec != "aac"
                or profile != "LC"
            ):
                raise ValueError
            container, normalized_codec = "m4a", "aac"
        else:
            raise ValueError
        channels = value["channels"]
        sample_rate = value["sample_rate_hz"]
        duration = value["duration_seconds"]
        if (
            type(channels) is not int
            or channels not in {1, 2}
            or type(sample_rate) is not int
            or not 8_000 <= sample_rate <= 48_000
            or type(duration) not in {int, float}
            or not math.isfinite(cast(float, duration))
        ):
            raise ValueError
        duration_ms = int(
            (Decimal(str(duration)) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        if not 0 < duration_ms <= _DEFAULT_LIMITS.max_media_duration_ms:
            raise ValueError
        return AudioMediaInfo(
            container=container,
            audio_codec=normalized_codec,
            channels=channels,
            sample_rate_hz=sample_rate,
            duration_ms=duration_ms,
        )
    except (InvalidOperation, TypeError, ValueError) as error:
        raise AudioInspectionError("audio_profile_unsupported") from error


def _parse_media_payload(value: object) -> AudioMediaInfoPayload:
    if not isinstance(value, dict):
        raise AudioInspectionError("inspection_result_invalid")
    payload = cast(dict[str, object], value)
    if frozenset(payload) != _MEDIA_FIELDS:
        raise AudioInspectionError("inspection_result_invalid")
    try:
        media = AudioMediaInfo(
            container=cast(Literal["mp3", "wav", "m4a"], payload["container"]),
            audio_codec=cast(Literal["mp3", "pcm_s16le", "aac"], payload["audio_codec"]),
            channels=cast(int, payload["channels"]),
            sample_rate_hz=cast(int, payload["sample_rate_hz"]),
            duration_ms=cast(int, payload["duration_ms"]),
        )
    except (TypeError, ValueError) as error:
        raise AudioInspectionError("inspection_result_invalid") from error
    return AudioMediaInfoPayload(
        container=media.container,
        audio_codec=media.audio_codec,
        channels=media.channels,
        sample_rate_hz=media.sample_rate_hz,
        duration_ms=media.duration_ms,
    )


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_components(path: Path, code: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            observed = current.lstat()
        except OSError as error:
            raise AudioSnapshotError(code) from error
        if stat.S_ISLNK(observed.st_mode):
            raise AudioSnapshotError(code)


def _read_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


def _directory_flags() -> int:
    return _read_flags() | getattr(os, "O_DIRECTORY", 0)


def _stat_tuple(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _directory_identity(value: os.stat_result) -> tuple[int, int, int]:
    return (value.st_dev, value.st_ino, value.st_mode)


def _node_identity(value: os.stat_result) -> tuple[int, int, int]:
    return (value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode))


def _file_identity_tuple(value: FileIdentity) -> tuple[int, ...]:
    return (
        value.device,
        value.inode,
        value.mode,
        value.bytes,
        value.modified_ns,
        value.changed_ns,
    )


def _identity(value: os.stat_result, digest: str) -> FileIdentity:
    return FileIdentity(
        device=value.st_dev,
        inode=value.st_ino,
        mode=value.st_mode,
        bytes=value.st_size,
        modified_ns=value.st_mtime_ns,
        changed_ns=value.st_ctime_ns,
        sha256=digest,
    )


def _copy_descriptor(source_fd: int, target_fd: int, max_bytes: int) -> tuple[int, str]:
    os.lseek(source_fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while True:
        block = os.read(source_fd, _BUFFER_BYTES)
        if not block:
            break
        total += len(block)
        if total > max_bytes:
            raise AudioSnapshotError("source_limit_exceeded")
        digest.update(block)
        offset = 0
        while offset < len(block):
            offset += os.write(target_fd, block[offset:])
    return total, digest.hexdigest()


def _hash_descriptor(descriptor: int, max_bytes: int) -> tuple[int, str]:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while True:
        block = os.read(descriptor, _BUFFER_BYTES)
        if not block:
            break
        total += len(block)
        if total > max_bytes:
            raise AudioSnapshotError("source_limit_exceeded")
        digest.update(block)
    return total, digest.hexdigest()


def _read_path_identity(path: Path, *, code: str, max_bytes: int) -> FileIdentity:
    try:
        _reject_symlink_components(path.parent, code)
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise AudioSnapshotError(code)
        descriptor = os.open(path, _read_flags())
        try:
            opened = os.fstat(descriptor)
            if _stat_tuple(opened) != _stat_tuple(before):
                raise AudioSnapshotError(code)
            byte_count, digest = _hash_descriptor(descriptor, max_bytes)
            after = os.fstat(descriptor)
            path_after = path.lstat()
            if (
                byte_count != before.st_size
                or _stat_tuple(after) != _stat_tuple(before)
                or _stat_tuple(path_after) != _stat_tuple(before)
            ):
                raise AudioSnapshotError(code)
            return _identity(before, digest)
        finally:
            os.close(descriptor)
    except AudioSnapshotError as error:
        if str(error) == code:
            raise
        raise AudioSnapshotError(code) from error
    except OSError as error:
        raise AudioSnapshotError(code) from error


def _require_owned_root(snapshot: AudioSourceSnapshot) -> None:
    try:
        observed = snapshot.owned_root.lstat()
    except OSError as error:
        raise AudioSnapshotError("owned_identity_mismatch") from error
    if (
        not stat.S_ISDIR(observed.st_mode)
        or _directory_identity(observed) != snapshot._owned_root_identity  # pyright: ignore[reportPrivateUsage]
    ):
        raise AudioSnapshotError("owned_identity_mismatch")


def _cleanup_failed_snapshot(
    root: Path,
    *,
    root_identity: tuple[int, int, int] | None,
    target_identity: tuple[int, int, int] | None,
    staging_path: Path | None,
    sealed_path: Path | None,
) -> None:
    if root_identity is None:
        return
    root_fd: int | None = None
    try:
        if _directory_identity(root.lstat()) != root_identity:
            raise AudioSnapshotError("snapshot_cleanup_failed")
        root_fd = os.open(root, _directory_flags())
        if _directory_identity(os.fstat(root_fd)) != root_identity:
            raise AudioSnapshotError("snapshot_cleanup_failed")
        if target_identity is not None:
            for name in tuple(os.listdir(root_fd)):
                observed = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                if _node_identity(observed) == target_identity:
                    os.unlink(name, dir_fd=root_fd)
        if os.listdir(root_fd):
            raise AudioSnapshotError("snapshot_cleanup_failed")
        for path in (staging_path, sealed_path):
            if path is not None and path.parent != root:
                raise AudioSnapshotError("snapshot_cleanup_failed")
        root_path_unchanged = _remove_owned_root_entry(root, root_identity, root_fd)
        if not root_path_unchanged or os.path.lexists(root):
            raise AudioSnapshotError("snapshot_cleanup_failed")
    except AudioSnapshotError:
        raise
    except OSError as error:
        raise AudioSnapshotError("snapshot_cleanup_failed") from error
    finally:
        if root_fd is not None:
            os.close(root_fd)


def _remove_owned_root_entry(
    root: Path,
    root_identity: tuple[int, int, int],
    root_fd: int,
) -> bool:
    if _directory_identity(os.fstat(root_fd)) != root_identity or os.listdir(root_fd):
        raise AudioSnapshotError("snapshot_cleanup_failed")
    if sys.platform == "darwin":
        identity_path = Path("/.vol") / str(root_identity[0]) / str(root_identity[1])
        if _directory_identity(identity_path.lstat()) != root_identity:
            raise AudioSnapshotError("snapshot_cleanup_failed")
        try:
            root_path_unchanged = _directory_identity(root.lstat()) == root_identity
        except OSError:
            root_path_unchanged = False
        os.rmdir(identity_path)
        return root_path_unchanged
    parent_fd = os.open(root.parent, _directory_flags())
    try:
        owned_name: str | None = None
        for name in os.listdir(parent_fd):
            observed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if _directory_identity(observed) == root_identity:
                if owned_name is not None:
                    raise AudioSnapshotError("snapshot_cleanup_failed")
                owned_name = name
        if owned_name is None:
            raise AudioSnapshotError("snapshot_cleanup_failed")
        os.rmdir(owned_name, dir_fd=parent_fd)
        return owned_name == root.name
    finally:
        os.close(parent_fd)
