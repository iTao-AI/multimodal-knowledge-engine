from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import cast

import pytest

import mke.adapters.audio.inspection as inspection
from mke.adapters.audio.inspection import (
    AudioInspectionError,
    AudioSnapshotError,
    cleanup_audio_snapshot,
    parse_audio_inspection_result,
    snapshot_audio_source,
    validate_audio_inspection_request,
)


def _source(tmp_path: Path, value: bytes = b"bounded audio bytes") -> Path:
    source = tmp_path / "source.wav"
    source.write_bytes(value)
    return source


def _observation(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "format_tokens": ("wav",),
        "audio_stream_count": 1,
        "video_stream_count": 0,
        "subtitle_stream_count": 0,
        "data_stream_count": 0,
        "attachment_stream_count": 0,
        "audio_codec": "pcm_s16le",
        "audio_profile": None,
        "channels": 1,
        "sample_rate_hz": 16_000,
        "duration_seconds": 1.2345,
    }
    values.update(overrides)
    return values


def test_audio_snapshot_is_descriptor_bound_read_only_and_cleanable(tmp_path: Path) -> None:
    source = _source(tmp_path)
    snapshot = snapshot_audio_source(source, tmp_path / "owned")

    assert snapshot.source_identity.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert snapshot.source_identity.sha256 == snapshot.owned_identity.sha256
    assert snapshot.owned_path.read_bytes() == source.read_bytes()
    assert stat.S_IMODE(snapshot.owned_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(snapshot.owned_path.stat().st_mode) == 0o400
    snapshot.verify_source_path()
    snapshot.verify_owned_path()

    cleanup_audio_snapshot(snapshot)
    assert not snapshot.owned_path.exists()
    assert not snapshot.owned_root.exists()


def test_audio_snapshot_rejects_same_size_replacement(tmp_path: Path) -> None:
    source = _source(tmp_path, b"original")
    snapshot = snapshot_audio_source(source, tmp_path / "owned")
    replacement = tmp_path / "replacement.wav"
    replacement.write_bytes(b"replaced")
    os.replace(replacement, source)

    with pytest.raises(AudioSnapshotError, match="source_identity_mismatch"):
        snapshot.verify_source_path()
    cleanup_audio_snapshot(snapshot)


@pytest.mark.parametrize("mutation", ["same_size", "growth", "truncation"])
def test_audio_snapshot_rejects_same_inode_mutation_during_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    source = _source(tmp_path, b"abcdefgh")
    original_copy = inspection._copy_descriptor  # pyright: ignore[reportPrivateUsage]

    def mutate_after_copy(source_fd: int, target_fd: int, max_bytes: int) -> tuple[int, str]:
        result = original_copy(source_fd, target_fd, max_bytes)
        with source.open("r+b") as stream:
            if mutation == "same_size":
                stream.write(b"ABCDEFGH")
            elif mutation == "growth":
                stream.seek(0, os.SEEK_END)
                stream.write(b"x")
            else:
                stream.truncate(4)
            stream.flush()
            os.fsync(stream.fileno())
        return result

    monkeypatch.setattr(inspection, "_copy_descriptor", mutate_after_copy)

    with pytest.raises(AudioSnapshotError, match="source_identity_mismatch"):
        snapshot_audio_source(source, tmp_path / "owned")
    assert not (tmp_path / "owned").exists()


def test_audio_snapshot_rejects_symlink_file_and_parent(tmp_path: Path) -> None:
    target = _source(tmp_path)
    linked_file = tmp_path / "linked.wav"
    linked_file.symlink_to(target)
    with pytest.raises(AudioSnapshotError, match="source_not_regular"):
        snapshot_audio_source(linked_file, tmp_path / "owned-file")

    real_parent = tmp_path / "real"
    real_parent.mkdir()
    nested = real_parent / "nested.wav"
    nested.write_bytes(b"audio")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(AudioSnapshotError, match="source_parent_symlink"):
        snapshot_audio_source(linked_parent / nested.name, tmp_path / "owned-parent")


def test_audio_snapshot_rejects_non_regular_empty_and_overlapping_root(tmp_path: Path) -> None:
    fifo = tmp_path / "source.wav"
    os.mkfifo(fifo)
    with pytest.raises(AudioSnapshotError, match="source_not_regular"):
        snapshot_audio_source(fifo, tmp_path / "fifo-owned")
    fifo.unlink()

    empty = tmp_path / "empty.wav"
    empty.touch()
    with pytest.raises(AudioSnapshotError, match="source_empty"):
        snapshot_audio_source(empty, tmp_path / "empty-owned")

    source = _source(tmp_path, b"nonempty")
    with pytest.raises(AudioSnapshotError, match="owned_root_overlap"):
        snapshot_audio_source(source, tmp_path)


def test_audio_snapshot_cleanup_preserves_replacement(tmp_path: Path) -> None:
    snapshot = snapshot_audio_source(_source(tmp_path), tmp_path / "owned")
    snapshot.owned_path.unlink()
    snapshot.owned_path.write_bytes(b"operator replacement")

    with pytest.raises(AudioSnapshotError, match="snapshot_cleanup_failed"):
        cleanup_audio_snapshot(snapshot)
    assert snapshot.owned_path.read_bytes() == b"operator replacement"


def test_audio_snapshot_owned_identity_rejects_path_replacement(tmp_path: Path) -> None:
    snapshot = snapshot_audio_source(_source(tmp_path), tmp_path / "owned")
    replacement = tmp_path / "replacement"
    replacement.write_bytes(snapshot.owned_path.read_bytes())
    replacement.chmod(0o400)
    os.replace(replacement, snapshot.owned_path)

    with pytest.raises(AudioSnapshotError, match="owned_identity_mismatch"):
        snapshot.verify_owned_path()


def test_audio_snapshot_creation_reports_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, b"abcdefgh")
    original_copy = inspection._copy_descriptor  # pyright: ignore[reportPrivateUsage]

    def mutate_after_copy(source_fd: int, target_fd: int, max_bytes: int) -> tuple[int, str]:
        result = original_copy(source_fd, target_fd, max_bytes)
        source.write_bytes(b"ABCDEFGH")
        return result

    def fail_cleanup(path: os.PathLike[str] | str, *args: object, **kwargs: object) -> None:
        raise OSError("injected cleanup failure")

    monkeypatch.setattr(inspection, "_copy_descriptor", mutate_after_copy)
    monkeypatch.setattr(inspection.os, "unlink", fail_cleanup)

    with pytest.raises(AudioSnapshotError, match="snapshot_cleanup_failed"):
        snapshot_audio_source(source, tmp_path / "owned")


@pytest.mark.parametrize(
    ("suffix", "observation", "expected"),
    [
        (
            ".mp3",
            _observation(format_tokens=("mp3",), audio_codec="mp3float", audio_profile=None),
            ("mp3", "mp3"),
        ),
        (".wav", _observation(), ("wav", "pcm_s16le")),
        (
            ".m4a",
            _observation(
                format_tokens=("mov", "mp4", "m4a", "3gp", "3g2", "mj2"),
                audio_codec="aac",
                audio_profile="LC",
            ),
            ("m4a", "aac"),
        ),
    ],
)
def test_audio_profile_normalization_is_closed_and_rounds_half_up(
    suffix: str, observation: dict[str, object], expected: tuple[str, str]
) -> None:
    media = inspection._normalize_audio_profile(  # pyright: ignore[reportPrivateUsage]
        cast(inspection.AudioInspectionObservation, observation),
        expected_suffix=suffix,
    )
    assert (media.container, media.audio_codec) == expected
    assert media.duration_ms == 1_235


@pytest.mark.parametrize(
    ("overrides", "suffix"),
    [
        ({"audio_stream_count": 0}, ".wav"),
        ({"audio_stream_count": 2}, ".wav"),
        ({"video_stream_count": 1}, ".wav"),
        ({"subtitle_stream_count": 1}, ".wav"),
        ({"data_stream_count": 1}, ".wav"),
        ({"attachment_stream_count": 1}, ".wav"),
        ({"format_tokens": ("mp3",)}, ".wav"),
        ({"audio_codec": "pcm_s24le"}, ".wav"),
        ({"channels": 3}, ".wav"),
        ({"sample_rate_hz": 7_999}, ".wav"),
        ({"duration_seconds": None}, ".wav"),
        ({"duration_seconds": float("nan")}, ".wav"),
        ({"duration_seconds": 900.001}, ".wav"),
        ({"audio_profile": "HE-AAC"}, ".m4a"),
    ],
)
def test_audio_profile_normalization_rejects_invalid_observations(
    overrides: dict[str, object], suffix: str
) -> None:
    observation = _observation(**overrides)
    if suffix == ".m4a":
        observation.update(
            format_tokens=("mov", "mp4", "m4a", "3gp", "3g2", "mj2"),
            audio_codec="aac",
        )
    with pytest.raises(AudioInspectionError, match="audio_profile_unsupported"):
        inspection._normalize_audio_profile(  # pyright: ignore[reportPrivateUsage]
            cast(inspection.AudioInspectionObservation, observation),
            expected_suffix=suffix,
        )


def test_audio_inspection_request_and_result_are_closed() -> None:
    request = validate_audio_inspection_request(
        {
            "path": "/private/call-owned/snapshot.wav",
            "expected_suffix": ".wav",
            "expected_sha256": "a" * 64,
            "expected_bytes": 123,
        }
    )
    assert request["expected_suffix"] == ".wav"
    result = parse_audio_inspection_result(
        {
            "schema_version": "mke.audio_inspection.v1",
            "media": {
                "container": "wav",
                "audio_codec": "pcm_s16le",
                "channels": 1,
                "sample_rate_hz": 16_000,
                "duration_ms": 1_235,
            },
            "observed_sha256": "a" * 64,
            "observed_bytes": 123,
        },
        request=request,
    )
    assert result["media"]["container"] == "wav"


@pytest.mark.parametrize(
    "payload",
    [
        {"path": "x", "expected_suffix": ".wav", "expected_sha256": "a" * 64},
        {
            "path": "x",
            "expected_suffix": ".flac",
            "expected_sha256": "a" * 64,
            "expected_bytes": 1,
        },
        {
            "path": "x",
            "expected_suffix": ".wav",
            "expected_sha256": "A" * 64,
            "expected_bytes": 1,
        },
        {
            "path": "x",
            "expected_suffix": ".wav",
            "expected_sha256": "a" * 64,
            "expected_bytes": True,
        },
        {
            "path": "x",
            "expected_suffix": ".wav",
            "expected_sha256": "a" * 64,
            "expected_bytes": 1,
            "extra": True,
        },
    ],
)
def test_audio_inspection_request_rejects_malformed_payload(
    payload: dict[str, object],
) -> None:
    with pytest.raises(AudioInspectionError, match="inspection_request_invalid"):
        validate_audio_inspection_request(payload)


def test_audio_inspection_result_rejects_identity_drift_and_unknown_fields() -> None:
    request = validate_audio_inspection_request(
        {
            "path": "/private/call-owned/snapshot.wav",
            "expected_suffix": ".wav",
            "expected_sha256": "a" * 64,
            "expected_bytes": 123,
        }
    )
    base: dict[str, object] = {
        "schema_version": "mke.audio_inspection.v1",
        "media": {
            "container": "wav",
            "audio_codec": "pcm_s16le",
            "channels": 1,
            "sample_rate_hz": 16_000,
            "duration_ms": 1_235,
        },
        "observed_sha256": "b" * 64,
        "observed_bytes": 123,
    }
    with pytest.raises(AudioInspectionError, match="inspection_identity_mismatch"):
        parse_audio_inspection_result(base, request=request)
    base["observed_sha256"] = "a" * 64
    base["extra"] = True
    with pytest.raises(AudioInspectionError, match="inspection_result_invalid"):
        parse_audio_inspection_result(base, request=request)
