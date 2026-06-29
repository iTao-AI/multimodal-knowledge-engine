from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from mke.embeddings.contracts import MODEL_ID, MODEL_REVISION
from mke.embeddings.readiness import (
    EmbeddingModelError,
    doctor_embedding,
    prepare_embedding,
    require_embedding_model_identity,
    resolve_embedding_cache,
    validate_embedding_snapshot,
)


def _complete_snapshot(cache: Path, *, revision: str = MODEL_REVISION) -> Path:
    snapshot = cache / "models--Qwen--Qwen3-Embedding-0.6B" / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (snapshot / "modules.json").write_text("{}", encoding="utf-8")
    (snapshot / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    (snapshot / "model.safetensors").write_bytes(b"weights")
    return snapshot


def _install_fake_hub(
    monkeypatch: pytest.MonkeyPatch,
    snapshot_download: object,
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(snapshot_download=snapshot_download),
    )


@pytest.mark.parametrize(
    ("model", "revision"),
    [
        ("main", MODEL_REVISION),
        ("Qwen3-Embedding-0.6B", MODEL_REVISION),
        (MODEL_ID, "main"),
        (MODEL_ID, ""),
        (MODEL_ID, True),
        (MODEL_ID, 1.0),
    ],
)
def test_model_identity_rejects_aliases_arbitrary_values_and_weak_types(
    model: object, revision: object
) -> None:
    with pytest.raises(EmbeddingModelError):
        require_embedding_model_identity(model, revision)


def test_embedding_cache_uses_owner_override_and_rejects_repository_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    external = tmp_path / "external-cache"
    monkeypatch.setenv("MKE_EMBEDDING_CACHE", str(external))

    assert resolve_embedding_cache(None, repository_root=repository) == external.resolve()
    assert resolve_embedding_cache(external, repository_root=repository) == external.resolve()

    with pytest.raises(EmbeddingModelError, match="outside the repository"):
        resolve_embedding_cache(repository / "cache", repository_root=repository)


def test_prepare_reuses_complete_exact_cache_without_sdk_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    snapshot = _complete_snapshot(cache)
    calls: list[dict[str, object]] = []

    def snapshot_download(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return str(snapshot)

    _install_fake_hub(monkeypatch, snapshot_download)

    result = prepare_embedding(
        cache_dir=cache,
        model=MODEL_ID,
        revision=MODEL_REVISION,
        allow_model_download=True,
    )

    assert result.status == "already_cached"
    assert result.model_id == MODEL_ID
    assert result.model_revision == MODEL_REVISION
    assert result.snapshot_fingerprint.startswith("sha256:")
    assert calls == []


def test_prepare_downloads_only_after_cache_miss_and_explicit_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    calls: list[dict[str, object]] = []

    def snapshot_download(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return str(_complete_snapshot(cache))

    _install_fake_hub(monkeypatch, snapshot_download)

    result = prepare_embedding(
        cache_dir=cache,
        model=MODEL_ID,
        revision=MODEL_REVISION,
        allow_model_download=True,
    )

    assert result.status == "downloaded"
    assert calls == [
        {
            "repo_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "cache_dir": str(cache.resolve()),
            "local_files_only": False,
            "max_workers": 1,
        }
    ]


def test_prepare_without_permission_never_attempts_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def snapshot_download(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        raise AssertionError("snapshot_download must not be called")

    _install_fake_hub(monkeypatch, snapshot_download)

    with pytest.raises(EmbeddingModelError) as exc_info:
        prepare_embedding(
            cache_dir=tmp_path / "cache",
            model=MODEL_ID,
            revision=MODEL_REVISION,
            allow_model_download=False,
        )

    assert exc_info.value.cause == "configured embedding model is not cached"
    assert calls == []


def test_prepare_network_failure_is_stable_and_never_reinvokes_snapshot_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "secret-cache"
    calls: list[dict[str, object]] = []

    def snapshot_download(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        raise RuntimeError(f"peer closed {cache}?token=secret Traceback")

    _install_fake_hub(monkeypatch, snapshot_download)

    with pytest.raises(EmbeddingModelError) as exc_info:
        prepare_embedding(
            cache_dir=cache,
            model=MODEL_ID,
            revision=MODEL_REVISION,
            allow_model_download=True,
        )

    assert exc_info.value.cause == "embedding model download failed"
    assert exc_info.value.next_step == "check_network_before_authorized_retry"
    assert calls == [
        {
            "repo_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "cache_dir": str(cache.resolve()),
            "local_files_only": False,
            "max_workers": 1,
        }
    ]
    assert str(cache) not in repr(exc_info.value)
    assert "secret" not in repr(exc_info.value)
    assert "Traceback" not in repr(exc_info.value)


def test_doctor_is_cache_only_and_reports_redacted_manifest_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "secret-cache"
    snapshot = _complete_snapshot(cache)
    calls: list[dict[str, object]] = []

    def snapshot_download(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return str(snapshot)

    _install_fake_hub(monkeypatch, snapshot_download)

    readiness = doctor_embedding(
        cache_dir=cache,
        model=MODEL_ID,
        revision=MODEL_REVISION,
    )

    assert readiness.status == "ready"
    assert readiness.model_id == MODEL_ID
    assert readiness.model_revision == MODEL_REVISION
    assert readiness.snapshot_fingerprint is not None
    assert calls == [
        {
            "repo_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "cache_dir": str(cache),
            "local_files_only": True,
            "max_workers": 1,
        }
    ]
    assert str(cache) not in repr(readiness)


def test_doctor_maps_missing_cache_without_sdk_text_or_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "secret-cache"

    def snapshot_download(**kwargs: object) -> str:
        raise FileNotFoundError(f"missing {cache}?token=secret Traceback")

    _install_fake_hub(monkeypatch, snapshot_download)

    readiness = doctor_embedding(
        cache_dir=cache,
        model=MODEL_ID,
        revision=MODEL_REVISION,
    )

    assert readiness.status == "not_ready"
    assert readiness.cause == "configured embedding model is not cached"
    assert readiness.next_step == "run_embedding_prepare"
    assert str(cache) not in repr(readiness)
    assert "secret" not in repr(readiness)
    assert "Traceback" not in repr(readiness)


def test_snapshot_manifest_hashes_every_logical_file_and_is_deterministic(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    snapshot = _complete_snapshot(cache)
    (snapshot / "subdirectory").mkdir()
    (snapshot / "subdirectory" / "extra.json").write_text('{"value":1}', encoding="utf-8")

    first = validate_embedding_snapshot(snapshot, cache_dir=cache)
    second = validate_embedding_snapshot(snapshot, cache_dir=cache)

    assert first == second
    assert tuple(item.relative_path for item in first.files) == (
        "config.json",
        "model.safetensors",
        "modules.json",
        "subdirectory/extra.json",
        "tokenizer_config.json",
    )
    assert first.snapshot_fingerprint.startswith("sha256:")
    assert first.total_bytes == sum(item.byte_size for item in first.files)

    (snapshot / "config.json").write_text('{"mutated":true}', encoding="utf-8")
    mutated = validate_embedding_snapshot(snapshot, cache_dir=cache)
    assert mutated.snapshot_fingerprint != first.snapshot_fingerprint


def test_snapshot_accepts_one_direct_same_model_blob_symlink(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    snapshot = _complete_snapshot(cache)
    weight = snapshot / "model.safetensors"
    weight.unlink()
    blobs = snapshot.parent.parent / "blobs"
    blobs.mkdir()
    blob = blobs / "weight-blob"
    blob.write_bytes(b"weights")
    weight.symlink_to(os.path.relpath(blob, weight.parent))

    manifest = validate_embedding_snapshot(snapshot, cache_dir=cache)

    recorded = next(item for item in manifest.files if item.relative_path == "model.safetensors")
    assert recorded.byte_size == len(b"weights")


@pytest.mark.parametrize("unsafe_kind", ["cross_cache", "chained", "dangling", "directory"])
def test_snapshot_rejects_unsafe_symlink_targets(tmp_path: Path, unsafe_kind: str) -> None:
    cache = tmp_path / "cache"
    snapshot = _complete_snapshot(cache)
    weight = snapshot / "model.safetensors"
    weight.unlink()
    blobs = snapshot.parent.parent / "blobs"
    blobs.mkdir()
    if unsafe_kind == "cross_cache":
        target = tmp_path / "other-cache" / "blob"
        target.parent.mkdir()
        target.write_bytes(b"weights")
    elif unsafe_kind == "chained":
        final = blobs / "final"
        final.write_bytes(b"weights")
        target = blobs / "chain"
        target.symlink_to(final.name)
    elif unsafe_kind == "dangling":
        target = blobs / "missing"
    else:
        target = blobs / "directory"
        target.mkdir()
    weight.symlink_to(os.path.relpath(target, weight.parent))

    with pytest.raises(EmbeddingModelError, match="snapshot"):
        validate_embedding_snapshot(snapshot, cache_dir=cache)


def test_snapshot_rejects_wrong_revision_incomplete_and_oversized_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    wrong_revision = _complete_snapshot(cache, revision="wrong")
    with pytest.raises(EmbeddingModelError, match="revision"):
        validate_embedding_snapshot(wrong_revision, cache_dir=cache)

    snapshot = _complete_snapshot(tmp_path / "incomplete")
    (snapshot / "modules.json").unlink()
    with pytest.raises(EmbeddingModelError) as incomplete:
        validate_embedding_snapshot(snapshot, cache_dir=tmp_path / "incomplete")
    assert incomplete.value.cause == "configured embedding model snapshot is incomplete"

    oversized_cache = tmp_path / "oversized"
    oversized = _complete_snapshot(oversized_cache)
    monkeypatch.setattr("mke.embeddings.readiness.MAX_SNAPSHOT_BYTES", 10)
    with pytest.raises(EmbeddingModelError, match="snapshot"):
        validate_embedding_snapshot(oversized, cache_dir=oversized_cache)
