from __future__ import annotations

import errno
import json
import os
import stat
import tempfile
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

import pytest

import mke.adapters.filesystem.library_export as publisher
from mke.adapters.filesystem.library_export import (
    OutputPublicationError,
    publish_compiled_library,
)
from mke.domain import (
    ActivePublicationObservation,
    CompiledEvidenceSnapshot,
    CompiledLibrarySnapshot,
    CompiledSourceSnapshot,
)


class _OwnedEntryLike(Protocol):
    parts: tuple[str, ...]


def _source(digit: str, *, timestamp: bool = False) -> CompiledSourceSnapshot:
    source_id = f"src_{digit * 32}"
    publication_id = f"pub_{digit * 32}"
    run_id = f"run_{digit * 32}"
    fingerprint = f"sha256:{digit * 64}"
    evidence = CompiledEvidenceSnapshot(
        evidence_id=f"ev_{digit * 32}",
        source_id=source_id,
        content_fingerprint=fingerprint,
        publication_id=publication_id,
        publication_revision=1,
        run_id=run_id,
        locator_kind="timestamp_ms" if timestamp else "page",
        locator_start=1000 if timestamp else 1,
        locator_end=2500 if timestamp else 1,
        text=f"evidence {digit}",
    )
    return CompiledSourceSnapshot(
        source_id=source_id,
        display_name=f"source-{digit}.{'mp4' if timestamp else 'pdf'}",
        content_fingerprint=fingerprint,
        media_type="video/mp4" if timestamp else "application/pdf",
        publication_id=publication_id,
        publication_revision=1,
        run_id=run_id,
        extractor_fingerprint=(
            "builtin-video-transcript-v1" if timestamp else "pymupdf-text-v1"
        ),
        required_stages=(
            ("candidate_evidence", "video_transcription")
            if timestamp
            else ("candidate_evidence", "pdf_text_extraction")
        ),
        evidence=(evidence,),
    )


def _snapshot() -> CompiledLibrarySnapshot:
    sources = (_source("a"), _source("b", timestamp=True))
    return CompiledLibrarySnapshot(
        observation=ActivePublicationObservation(
            library_id="local",
            state="active",
            source_count=2,
            active_publication_count=2,
            active_evidence_count=2,
        ),
        sources=sources,
    )


def _identity(path: Path) -> tuple[int, int, int, int, int]:
    value = path.lstat()
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        value.st_mode,
        value.st_mtime_ns,
    )


def _write_same_size_drift(path: Path) -> None:
    original = path.read_bytes()
    assert original
    path.write_bytes(bytes((original[0] ^ 1,)) + original[1:])


def _replace_with_identity_distinct_file(
    path: Path, contents: bytes
) -> tuple[int, int, int, int, int]:
    original_identity = _identity(path)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.replacement-",
            delete=False,
        ) as temporary:
            temporary.write(contents)
            temporary_path = Path(temporary.name)
        replacement_identity = _identity(temporary_path)
        assert replacement_identity[:3] != original_identity[:3]
        os.replace(temporary_path, path)
        temporary_path = None
        assert _identity(path) == replacement_identity
        return replacement_identity
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def test_identity_distinct_replacement_keeps_no_temporary_sibling(
    tmp_path: Path,
) -> None:
    target = tmp_path / "owned.md"
    target.write_bytes(b"call-owned")
    original_identity = _identity(target)

    replacement_identity = _replace_with_identity_distinct_file(
        target, b"operator-owned replacement"
    )

    assert replacement_identity[:3] != original_identity[:3]
    assert _identity(target) == replacement_identity
    assert target.read_bytes() == b"operator-owned replacement"
    assert {entry.name for entry in tmp_path.iterdir()} == {"owned.md"}


def _assert_error(reason: str, call: Callable[[], object]) -> None:
    with pytest.raises(OutputPublicationError) as exc_info:
        call()
    assert exc_info.value.reason == reason


@pytest.mark.parametrize(
    "output_name",
    [
        "",
        ".",
        "..",
        "/absolute",
        "C:\\absolute",
        "C:/absolute",
        "/",
        "\\",
        "nested/child",
        "nested\\child",
        "../traversal",
        "traversal/..",
        "nul\0name",
    ],
)
def test_rejects_non_child_output_names_without_creating_entries(
    tmp_path: Path, output_name: str
) -> None:
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"operator-owned")
    before = _identity(sentinel)

    _assert_error(
        "parent_invalid",
        lambda: publish_compiled_library(
            _snapshot(), output_name=output_name, parent=tmp_path
        ),
    )

    assert sentinel.read_bytes() == b"operator-owned"
    assert _identity(sentinel) == before
    assert {entry.name for entry in tmp_path.iterdir()} == {"sentinel"}


def test_rejects_parent_with_symlink_component(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    before = _identity(linked)

    _assert_error(
        "parent_invalid",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=linked
        ),
    )

    assert _identity(linked) == before
    assert list(real.iterdir()) == []


@pytest.mark.parametrize("kind", ["file", "directory", "symlink"])
def test_collision_preserves_existing_target_identity_and_metadata(
    tmp_path: Path, kind: str
) -> None:
    target = tmp_path / "compiled-library"
    if kind == "file":
        target.write_bytes(b"operator-owned")
    elif kind == "directory":
        target.mkdir()
        (target / "operator.txt").write_bytes(b"operator-owned")
    else:
        referent = tmp_path / "referent"
        referent.write_bytes(b"operator-owned")
        target.symlink_to(referent)
    before = _identity(target)
    before_entries = {entry.name for entry in tmp_path.iterdir()}

    _assert_error(
        "target_exists",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )

    assert _identity(target) == before
    assert {entry.name for entry in tmp_path.iterdir()} == before_entries
    if kind == "file":
        assert target.read_bytes() == b"operator-owned"
    elif kind == "directory":
        assert (target / "operator.txt").read_bytes() == b"operator-owned"
    else:
        assert target.read_bytes() == b"operator-owned"


def test_publishes_exact_tree_and_manifest_is_independently_verifiable(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()

    result = publish_compiled_library(
        snapshot, output_name="compiled-library", parent=tmp_path
    )

    target = tmp_path / "compiled-library"
    expected = {
        "export-manifest.json",
        f"evidence/{'a' * 64}.jsonl",
        f"evidence/{'b' * 64}.jsonl",
        f"sources/{'a' * 64}.md",
        f"sources/{'b' * 64}.md",
    }
    actual = {
        str(path.relative_to(target))
        for path in target.rglob("*")
        if path.is_file()
    }
    assert actual == expected
    assert {path.name for path in target.rglob("*") if path.name.startswith(".")} == set()
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    assert stat.S_IMODE((target / "sources").stat().st_mode) == 0o700
    assert stat.S_IMODE((target / "evidence").stat().st_mode) == 0o700
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o600
        for path in target.rglob("*")
        if path.is_file()
    )

    manifest_bytes = (target / "export-manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    assert result.library_id == "local"
    assert result.source_count == 2
    assert result.evidence_count == 2
    assert result.manifest_sha256 == sha256(manifest_bytes).hexdigest()
    for source in manifest["sources"]:
        for path_key, digest_key in (
            ("evidence_path", "evidence_sha256"),
            ("markdown_path", "markdown_sha256"),
        ):
            content = (target / source[path_key]).read_bytes()
            assert len(content) > 0
            assert sha256(content).hexdigest() == source[digest_key]


def test_manifest_rename_is_last_mutation_before_final_revalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    real_write = publisher._write_content_file  # pyright: ignore[reportPrivateUsage]
    real_inventory = publisher._validate_exact_inventory  # pyright: ignore[reportPrivateUsage]
    real_revalidate_owned = publisher._revalidate_owned_files  # pyright: ignore[reportPrivateUsage]
    real_manifest = publisher._write_manifest_temp  # pyright: ignore[reportPrivateUsage]
    real_publish = publisher._publish_manifest  # pyright: ignore[reportPrivateUsage]

    def write(*args: object, **kwargs: object) -> object:
        result = real_write(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        events.append("content_closed_revalidated")
        return result

    def inventory(*args: object, **kwargs: object) -> object:
        result = real_inventory(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        events.append("exact_inventory")
        return result

    def manifest(*args: object, **kwargs: object) -> object:
        result = real_manifest(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        events.append("manifest_closed_reread")
        return result

    def revalidate_owned(*args: object, **kwargs: object) -> object:
        result = real_revalidate_owned(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        events.append("referenced_files_revalidated")
        return result

    def publish(*args: object, **kwargs: object) -> object:
        result = real_publish(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        events.append("manifest_renamed")
        return result

    monkeypatch.setattr(publisher, "_write_content_file", write)
    monkeypatch.setattr(publisher, "_validate_exact_inventory", inventory)
    monkeypatch.setattr(publisher, "_revalidate_owned_files", revalidate_owned)
    monkeypatch.setattr(publisher, "_write_manifest_temp", manifest)
    monkeypatch.setattr(publisher, "_publish_manifest", publish)

    publish_compiled_library(_snapshot(), output_name="compiled-library", parent=tmp_path)

    assert events == [
        "content_closed_revalidated",
        "content_closed_revalidated",
        "content_closed_revalidated",
        "content_closed_revalidated",
        "exact_inventory",
        "referenced_files_revalidated",
        "manifest_closed_reread",
        "manifest_renamed",
        "exact_inventory",
        "referenced_files_revalidated",
    ]


def test_content_replacement_after_inventory_before_manifest_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_inventory = publisher._validate_exact_inventory  # pyright: ignore[reportPrivateUsage]
    replacement = tmp_path / "compiled-library" / "sources" / f"{'a' * 64}.md"
    replacement_identity: tuple[int, int, int, int, int] | None = None

    def replace_after_inventory(target_fd: int, expected: set[str]) -> None:
        nonlocal replacement_identity
        real_inventory(target_fd, expected)
        replacement_identity = _replace_with_identity_distinct_file(
            replacement, b"operator-owned replacement"
        )

    monkeypatch.setattr(
        publisher, "_validate_exact_inventory", replace_after_inventory
    )

    _assert_error(
        "cleanup_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )

    assert replacement.read_bytes() == b"operator-owned replacement"
    assert _identity(replacement) == replacement_identity
    assert not (tmp_path / "compiled-library/export-manifest.json").exists()
    assert {
        str(path.relative_to(tmp_path / "compiled-library"))
        for path in (tmp_path / "compiled-library").rglob("*")
        if path.is_file()
    } == {f"sources/{'a' * 64}.md"}


@pytest.mark.parametrize("mutation", ["replacement", "digest_drift"])
def test_content_mutation_after_manifest_commit_before_success_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    real_publish = publisher._publish_manifest  # pyright: ignore[reportPrivateUsage]
    content = tmp_path / "compiled-library" / "sources" / f"{'a' * 64}.md"
    replacement_identity: tuple[int, int, int, int, int] | None = None

    def mutate_after_commit(target_fd: int) -> None:
        nonlocal replacement_identity
        real_publish(target_fd)
        if mutation == "replacement":
            replacement_identity = _replace_with_identity_distinct_file(
                content, b"operator-owned replacement"
            )
        else:
            _write_same_size_drift(content)
            replacement_identity = _identity(content)

    monkeypatch.setattr(publisher, "_publish_manifest", mutate_after_commit)

    _assert_error(
        "cleanup_failed" if mutation == "replacement" else "write_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )

    target = tmp_path / "compiled-library"
    if mutation == "replacement":
        assert content.read_bytes() == b"operator-owned replacement"
        assert _identity(content) == replacement_identity
        assert not (target / "export-manifest.json").exists()
    else:
        assert not target.exists()


@pytest.mark.parametrize("mutation", ["replacement", "digest_drift"])
def test_manifest_mutation_after_commit_before_success_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    real_publish = publisher._publish_manifest  # pyright: ignore[reportPrivateUsage]
    manifest = tmp_path / "compiled-library/export-manifest.json"
    replacement_identity: tuple[int, int, int, int, int] | None = None

    def mutate_after_commit(target_fd: int) -> None:
        nonlocal replacement_identity
        real_publish(target_fd)
        if mutation == "replacement":
            replacement_identity = _replace_with_identity_distinct_file(
                manifest, b"operator-owned replacement"
            )
        else:
            _write_same_size_drift(manifest)
            replacement_identity = _identity(manifest)

    monkeypatch.setattr(publisher, "_publish_manifest", mutate_after_commit)

    _assert_error(
        "cleanup_failed" if mutation == "replacement" else "write_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )

    target = tmp_path / "compiled-library"
    if mutation == "replacement":
        assert manifest.read_bytes() == b"operator-owned replacement"
        assert _identity(manifest) == replacement_identity
        assert {
            str(path.relative_to(target))
            for path in target.rglob("*")
            if path.is_file()
        } == {"export-manifest.json"}
    else:
        assert not target.exists()


def test_renders_writes_and_discards_each_source_before_rendering_the_next(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    real_evidence = publisher.render_evidence_jsonl
    real_markdown = publisher.render_compiled_markdown
    real_write = publisher._write_content_file  # pyright: ignore[reportPrivateUsage]

    def render_evidence(source: CompiledSourceSnapshot) -> bytes:
        digit = source.content_fingerprint[-1]
        events.append(f"render-evidence-{digit}")
        return real_evidence(source)

    def render_markdown(source: CompiledSourceSnapshot) -> bytes:
        digit = source.content_fingerprint[-1]
        events.append(f"render-markdown-{digit}")
        return real_markdown(source)

    def write(
        directory_fd: int,
        name: str,
        data: bytes,
        parts: tuple[str, ...],
        owned: Any,
    ) -> None:
        events.append(f"write-{parts[0]}-{name[0]}")
        real_write(directory_fd, name, data, parts, owned)

    monkeypatch.setattr(publisher, "render_evidence_jsonl", render_evidence)
    monkeypatch.setattr(publisher, "render_compiled_markdown", render_markdown)
    monkeypatch.setattr(publisher, "_write_content_file", write)

    publish_compiled_library(_snapshot(), output_name="compiled-library", parent=tmp_path)

    assert events == [
        "render-evidence-a",
        "render-markdown-a",
        "write-evidence-a",
        "write-sources-a",
        "render-evidence-b",
        "render-markdown-b",
        "write-evidence-b",
        "write-sources-b",
    ]


def test_target_replaced_after_temporary_manifest_is_not_published_as_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_manifest = publisher._write_manifest_temp  # pyright: ignore[reportPrivateUsage]

    def replace_after_manifest(*args: object, **kwargs: object) -> None:
        real_manifest(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        target = tmp_path / "compiled-library"
        target.rename(tmp_path / "displaced-owned-tree")
        target.mkdir()
        (target / "operator.txt").write_bytes(b"operator-owned replacement")

    monkeypatch.setattr(publisher, "_write_manifest_temp", replace_after_manifest)

    _assert_error(
        "cleanup_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    assert (tmp_path / "compiled-library/operator.txt").read_bytes() == (
        b"operator-owned replacement"
    )
    assert not (tmp_path / "compiled-library/export-manifest.json").exists()


def test_post_mkdir_lstat_failure_never_reports_untracked_parent_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_lstat = publisher._lstat  # pyright: ignore[reportPrivateUsage]
    target_lookups = 0

    def fail_after_mkdir(name: str, directory_fd: int) -> os.stat_result:
        nonlocal target_lookups
        if name == "compiled-library":
            target_lookups += 1
            if target_lookups == 2:
                raise OSError("post-mkdir lstat failure")
        return real_lstat(name, directory_fd)

    monkeypatch.setattr(publisher, "_lstat", fail_after_mkdir)

    _assert_error(
        "cleanup_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    target = tmp_path / "compiled-library"
    assert not target.exists() or list(target.iterdir()) == []


@pytest.mark.parametrize("error_number", [errno.ENOSPC, errno.EDQUOT, errno.EIO])
def test_initial_target_storage_failure_is_not_misreported_as_invalid_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_number: int
) -> None:
    real_mkdir = publisher.os.mkdir

    def fail_target_mkdir(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> None:
        if path == "compiled-library":
            raise OSError(error_number, "injected storage failure")
        real_mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(publisher.os, "mkdir", fail_target_mkdir)

    _assert_error(
        "write_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    assert not (tmp_path / "compiled-library").exists()


@pytest.mark.parametrize("failure", ["short_write", "write_oserror", "digest"])
def test_content_failure_cleans_the_owned_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    if failure == "short_write":
        def short_write(_fd: int, _data: memoryview) -> int:
            return 0

        monkeypatch.setattr(publisher, "_write_chunk", short_write)
    elif failure == "write_oserror":
        def fail_write(_fd: int, _data: memoryview) -> int:
            raise OSError("disk failure")

        monkeypatch.setattr(publisher, "_write_chunk", fail_write)
    else:
        def fail_revalidation(*_args: object, **_kwargs: object) -> None:
            raise OSError("digest mismatch")

        monkeypatch.setattr(publisher, "_revalidate_file", fail_revalidation)

    _assert_error(
        "write_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )

    assert not (tmp_path / "compiled-library").exists()


def test_close_failure_cleans_the_owned_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_close = publisher._close_fd  # pyright: ignore[reportPrivateUsage]
    failed = False

    def fail_once(fd: int) -> None:
        nonlocal failed
        is_regular = stat.S_ISREG(os.fstat(fd).st_mode)
        real_close(fd)
        if is_regular and not failed:
            failed = True
            raise OSError("close failure")

    monkeypatch.setattr(publisher, "_close_fd", fail_once)

    _assert_error(
        "write_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    assert not (tmp_path / "compiled-library").exists()


@pytest.mark.parametrize("failure", ["temporary_manifest", "final_rename"])
def test_manifest_failure_cleans_the_owned_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    helper = "_write_manifest_temp" if failure == "temporary_manifest" else "_publish_manifest"

    def fail(*_args: object, **_kwargs: object) -> None:
        raise OSError(failure)

    monkeypatch.setattr(publisher, helper, fail)

    _assert_error(
        "write_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    assert not (tmp_path / "compiled-library").exists()


def test_temporary_manifest_revalidation_failure_cleans_the_owned_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_revalidate = publisher._revalidate_file  # pyright: ignore[reportPrivateUsage]

    def fail_manifest(fd: int, expected: bytes, identity: object) -> None:
        if b'"schema_version":"mke.compiled_library_export.v1"' in expected:
            raise OSError("temporary manifest mismatch")
        real_revalidate(fd, expected, identity)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(publisher, "_revalidate_file", fail_manifest)

    _assert_error(
        "write_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    assert not (tmp_path / "compiled-library").exists()


def test_cleanup_visits_only_recorded_inventory_in_reverse_creation_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    visited: list[str] = []
    real_unlink = publisher._unlink_owned  # pyright: ignore[reportPrivateUsage]
    real_rmdir = publisher._rmdir_owned  # pyright: ignore[reportPrivateUsage]

    def unlink(target_fd: int, entry: _OwnedEntryLike) -> None:
        visited.append("/".join(entry.parts))
        real_unlink(target_fd, entry)  # pyright: ignore[reportArgumentType]

    def rmdir(target_fd: int, entry: _OwnedEntryLike) -> None:
        visited.append("/".join(entry.parts))
        real_rmdir(target_fd, entry)  # pyright: ignore[reportArgumentType]

    def fail_publish(_target_fd: int) -> None:
        raise OSError("rename failure")

    monkeypatch.setattr(publisher, "_unlink_owned", unlink)
    monkeypatch.setattr(publisher, "_rmdir_owned", rmdir)
    monkeypatch.setattr(publisher, "_publish_manifest", fail_publish)

    _assert_error(
        "write_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    assert visited == [
        ".export-manifest.json.tmp",
        f"sources/{'b' * 64}.md",
        f"evidence/{'b' * 64}.jsonl",
        f"sources/{'a' * 64}.md",
        f"evidence/{'a' * 64}.jsonl",
        "evidence",
        "sources",
    ]


def test_unexpected_nested_entry_is_not_discovered_or_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_inventory = publisher._validate_exact_inventory  # pyright: ignore[reportPrivateUsage]

    def inject(target_fd: int, expected: set[str]) -> None:
        nested = tmp_path / "compiled-library" / "operator"
        nested.mkdir()
        (nested / "owned.txt").write_bytes(b"operator-owned")
        real_inventory(target_fd, expected)

    monkeypatch.setattr(publisher, "_validate_exact_inventory", inject)

    _assert_error(
        "cleanup_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    assert (tmp_path / "compiled-library/operator/owned.txt").read_bytes() == b"operator-owned"


def test_replaced_child_survives_identity_bound_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def replace_child(_target_fd: int, _expected: set[str]) -> None:
        child = tmp_path / "compiled-library" / "sources" / f"{'a' * 64}.md"
        _replace_with_identity_distinct_file(child, b"operator-owned replacement")
        raise OSError("force cleanup")

    monkeypatch.setattr(publisher, "_validate_exact_inventory", replace_child)

    _assert_error(
        "cleanup_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    child = tmp_path / "compiled-library" / "sources" / f"{'a' * 64}.md"
    assert child.read_bytes() == b"operator-owned replacement"


def test_replaced_target_survives_identity_bound_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def replace_target(_target_fd: int, _expected: set[str]) -> None:
        target = tmp_path / "compiled-library"
        target.rename(tmp_path / "displaced-owned-tree")
        target.mkdir()
        (target / "operator.txt").write_bytes(b"operator-owned replacement")
        raise OSError("force cleanup")

    monkeypatch.setattr(publisher, "_validate_exact_inventory", replace_target)

    _assert_error(
        "cleanup_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    assert (tmp_path / "compiled-library/operator.txt").read_bytes() == (
        b"operator-owned replacement"
    )


@pytest.mark.parametrize("helper", ["_unlink_owned", "_rmdir_owned"])
def test_cleanup_removal_failure_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helper: str
) -> None:
    def force_write_failure(*_args: object, **_kwargs: object) -> None:
        raise OSError("write failure")

    def force_cleanup_failure(*_args: object, **_kwargs: object) -> None:
        raise OSError("cleanup failure")

    monkeypatch.setattr(publisher, "_write_manifest_temp", force_write_failure)
    monkeypatch.setattr(publisher, helper, force_cleanup_failure)

    _assert_error(
        "cleanup_failed",
        lambda: publish_compiled_library(
            _snapshot(), output_name="compiled-library", parent=tmp_path
        ),
    )
    assert (tmp_path / "compiled-library").exists()
