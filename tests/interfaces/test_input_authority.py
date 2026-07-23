from __future__ import annotations

import os
import types
from pathlib import Path

import pytest

import mke.interfaces.input_authority
from mke.application import IngestFileAuthorityError
from mke.interfaces.input_authority import bind_allowed_file


def test_bound_input_rejects_same_size_mutation_without_owned_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "voice.mp3"
    owned_root = tmp_path / "owned"
    source.write_bytes(b"original")
    bound = bind_allowed_file(tmp_path, source.name)
    source.write_bytes(b"mutated!")

    def allocate(*, prefix: str) -> str:
        assert prefix == "mke-bound-ingest-"
        owned_root.mkdir(mode=0o700)
        return str(owned_root)

    monkeypatch.setattr(mke.interfaces.input_authority.tempfile, "mkdtemp", allocate)

    try:
        with pytest.raises(IngestFileAuthorityError, match="changed during validation"):
            with bound.materialize():
                pass
        assert not owned_root.exists()
    finally:
        bound.close()


def test_bound_input_close_is_idempotent_and_disables_materialization(
    tmp_path: Path,
) -> None:
    source = tmp_path / "voice.wav"
    source.write_bytes(b"original")
    bound = bind_allowed_file(tmp_path, source.name)

    bound.close()
    bound.close()

    with pytest.raises(IngestFileAuthorityError, match="changed during validation"):
        with bound.materialize():
            pass


def test_bound_input_materializes_companion_and_cleans_owned_root(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clip.mp4"
    companion_path = tmp_path / "clip.mp4.mke-transcript.json"
    source.write_bytes(b"video")
    companion_path.write_bytes(b'{"format":"mke.video_transcript.v1"}')
    bound = bind_allowed_file(tmp_path, source.name)
    companion = bind_allowed_file(tmp_path, companion_path.name)
    bound.add_companion(companion)

    try:
        with bound.materialize() as materialized:
            owned_root = materialized.parent
            assert materialized.read_bytes() == b"video"
            assert (owned_root / companion_path.name).read_bytes() == companion_path.read_bytes()
        assert not owned_root.exists()
    finally:
        bound.close()


def test_bound_input_materialization_canonicalizes_allocator_symlink_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "voice.mp3"
    canonical_parent = tmp_path / "canonical-parent"
    linked_parent = tmp_path / "linked-parent"
    allocated = canonical_parent / "owned"
    source.write_bytes(b"original")
    canonical_parent.mkdir()
    linked_parent.symlink_to(canonical_parent, target_is_directory=True)
    bound = bind_allowed_file(tmp_path, source.name)

    def allocate(*, prefix: str) -> str:
        assert prefix == "mke-bound-ingest-"
        allocated.mkdir(mode=0o700)
        return str(linked_parent / allocated.name)

    monkeypatch.setattr(mke.interfaces.input_authority.tempfile, "mkdtemp", allocate)

    try:
        with bound.materialize() as materialized:
            assert materialized == allocated.resolve() / source.name
            assert materialized.read_bytes() == b"original"
        assert not allocated.exists()
    finally:
        bound.close()


def test_bound_input_linux_cleanup_ignores_regular_sibling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    materialized_parent = tmp_path / "materialized"
    owned_root = materialized_parent / "owned"
    sibling = materialized_parent / "operator.txt"
    source_root.mkdir()
    materialized_parent.mkdir()
    source = source_root / "voice.mp3"
    source.write_bytes(b"original")
    sibling.write_bytes(b"operator state")
    sibling_before = sibling.stat()
    bound = bind_allowed_file(source_root, source.name)

    def allocate(*, prefix: str) -> str:
        assert prefix == "mke-bound-ingest-"
        owned_root.mkdir(mode=0o700)
        return str(owned_root)

    monkeypatch.setattr(mke.interfaces.input_authority.tempfile, "mkdtemp", allocate)
    monkeypatch.setattr(
        mke.interfaces.input_authority,
        "sys",
        types.SimpleNamespace(platform="linux"),
    )

    try:
        with bound.materialize() as materialized:
            assert materialized.read_bytes() == b"original"
        assert not owned_root.exists()
        assert sibling.read_bytes() == b"operator state"
        sibling_after = sibling.stat()
        assert (
            sibling_after.st_dev,
            sibling_after.st_ino,
            sibling_after.st_mode,
            sibling_after.st_size,
            sibling_after.st_mtime_ns,
            sibling_after.st_ctime_ns,
        ) == (
            sibling_before.st_dev,
            sibling_before.st_ino,
            sibling_before.st_mode,
            sibling_before.st_size,
            sibling_before.st_mtime_ns,
            sibling_before.st_ctime_ns,
        )
    finally:
        bound.close()


def test_bound_input_cleanup_preserves_replacement_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "voice.m4a"
    owned_root = tmp_path / "owned"
    displaced_root = tmp_path / "displaced-owned"
    source.write_bytes(b"original")
    bound = bind_allowed_file(tmp_path, source.name)
    original_remove = mke.interfaces.input_authority._remove_owned_root_entry  # pyright: ignore[reportPrivateUsage]

    def allocate(*, prefix: str) -> str:
        assert prefix == "mke-bound-ingest-"
        owned_root.mkdir(mode=0o700)
        return str(owned_root)

    def replace_root(
        root: Path,
        root_identity: tuple[int, int, int],
        root_descriptor: int,
    ) -> bool:
        os.replace(root, displaced_root)
        root.mkdir(mode=0o750)
        return original_remove(root, root_identity, root_descriptor)

    monkeypatch.setattr(mke.interfaces.input_authority.tempfile, "mkdtemp", allocate)
    monkeypatch.setattr(
        mke.interfaces.input_authority,
        "sys",
        types.SimpleNamespace(platform="linux"),
    )
    monkeypatch.setattr(
        mke.interfaces.input_authority,
        "_remove_owned_root_entry",
        replace_root,
    )

    try:
        with pytest.raises(IngestFileAuthorityError, match="changed during validation"):
            with bound.materialize() as materialized:
                assert materialized.read_bytes() == b"original"
        assert owned_root.is_dir()
        assert owned_root.stat().st_mode & 0o777 == 0o750
        assert not displaced_root.exists()
    finally:
        bound.close()
