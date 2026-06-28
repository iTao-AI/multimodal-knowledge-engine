"""Exact, cache-only lifecycle for the frozen local embedding model."""

from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Literal, Protocol, cast

from mke.embeddings.contracts import MODEL_ID, MODEL_REVISION

MODEL_CLI_ID = "qwen3-embedding-0.6b"
MAX_SNAPSHOT_BYTES = 1_610_612_736  # 1.5 GiB
_REQUIRED_SNAPSHOT_FILES = frozenset(
    {"modules.json", "tokenizer_config.json", "config.json", "model.safetensors"}
)
_HASH_CHUNK_BYTES = 1024 * 1024


class _SnapshotDownload(Protocol):
    def __call__(
        self,
        *,
        repo_id: str,
        revision: str,
        cache_dir: str,
        local_files_only: bool,
    ) -> str: ...


class EmbeddingModelError(RuntimeError):
    """Stable local-model failure that never includes SDK text or local paths."""

    def __init__(self, cause: str, next_step: str) -> None:
        super().__init__(cause)
        self.cause = cause
        self.next_step = next_step


@dataclass(frozen=True)
class EmbeddingSnapshotFile:
    relative_path: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class EmbeddingSnapshotManifest:
    snapshot_fingerprint: str
    total_bytes: int
    files: tuple[EmbeddingSnapshotFile, ...]


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: Literal["passed", "failed"]
    message: str


@dataclass(frozen=True)
class EmbeddingReadiness:
    status: Literal["ready", "not_ready"]
    model_id: str
    model_revision: str
    snapshot_fingerprint: str | None
    checks: tuple[ReadinessCheck, ...]
    cause: str | None
    next_step: str | None


@dataclass(frozen=True)
class EmbeddingPreparationResult:
    status: Literal["already_cached", "downloaded"]
    model_id: str
    model_revision: str
    snapshot_fingerprint: str


def require_embedding_model_identity(model: object, revision: object) -> tuple[str, str]:
    if type(model) is not str or model != MODEL_ID:
        raise EmbeddingModelError(
            "configured embedding model revision is unavailable",
            "use_allowlisted_embedding_model",
        )
    if type(revision) is not str or revision != MODEL_REVISION:
        raise EmbeddingModelError(
            "configured embedding model revision is unavailable",
            "use_allowlisted_embedding_model_revision",
        )
    return MODEL_ID, MODEL_REVISION


def resolve_embedding_cache(
    cache_dir: Path | None,
    *,
    repository_root: Path | None = None,
) -> Path:
    candidate = cache_dir
    if candidate is None:
        configured = os.environ.get("MKE_EMBEDDING_CACHE")
        if configured:
            candidate = Path(configured)
        elif sys.platform == "darwin":
            candidate = Path.home() / "Library" / "Caches" / "mke" / "embedding"
        else:
            cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            candidate = cache_home / "mke" / "embedding"
    resolved = candidate.expanduser().resolve(strict=False)
    if repository_root is not None:
        repository = repository_root.resolve(strict=False)
        if resolved == repository or resolved.is_relative_to(repository):
            raise EmbeddingModelError(
                "embedding model cache must be outside the repository",
                "choose_external_embedding_cache",
            )
    return resolved


def validate_embedding_snapshot(
    snapshot: Path,
    *,
    cache_dir: Path,
) -> EmbeddingSnapshotManifest:
    cache = cache_dir.resolve(strict=False)
    try:
        snapshot_root = snapshot.resolve(strict=True)
    except OSError as error:
        raise _snapshot_error("configured embedding model snapshot is incomplete") from error
    if not snapshot_root.is_dir() or not snapshot_root.is_relative_to(cache):
        raise _snapshot_error("configured embedding model snapshot is incomplete")
    if snapshot_root.name != MODEL_REVISION:
        raise EmbeddingModelError(
            "configured embedding model revision is unavailable",
            "restore_exact_embedding_model_revision",
        )

    logical_paths = tuple(sorted(path for path in snapshot_root.rglob("*") if not path.is_dir()))
    relative_paths = {path.relative_to(snapshot_root).as_posix() for path in logical_paths}
    if not _REQUIRED_SNAPSHOT_FILES.issubset(relative_paths):
        raise _snapshot_error("configured embedding model snapshot is incomplete")
    if not logical_paths:
        raise _snapshot_error("configured embedding model snapshot is incomplete")

    files: list[EmbeddingSnapshotFile] = []
    total_bytes = 0
    for logical_path in logical_paths:
        source = _resolve_snapshot_file(logical_path, snapshot_root=snapshot_root)
        try:
            file_stat = source.stat()
            if not stat.S_ISREG(file_stat.st_mode):
                raise OSError("not a regular file")
            digest = _hash_file(source)
        except OSError as error:
            raise _snapshot_error("configured embedding model snapshot is incomplete") from error
        total_bytes += file_stat.st_size
        if total_bytes > MAX_SNAPSHOT_BYTES:
            raise _snapshot_error("configured embedding model snapshot exceeds size limit")
        files.append(
            EmbeddingSnapshotFile(
                relative_path=logical_path.relative_to(snapshot_root).as_posix(),
                byte_size=file_stat.st_size,
                sha256=digest,
            )
        )

    identity = [
        {
            "relative_path": item.relative_path,
            "byte_size": item.byte_size,
            "sha256": item.sha256,
        }
        for item in files
    ]
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return EmbeddingSnapshotManifest(
        snapshot_fingerprint="sha256:" + sha256(canonical.encode("utf-8")).hexdigest(),
        total_bytes=total_bytes,
        files=tuple(files),
    )


def prepare_embedding(
    *,
    cache_dir: Path,
    model: object,
    revision: object,
    allow_model_download: bool,
) -> EmbeddingPreparationResult:
    model_id, model_revision = require_embedding_model_identity(model, revision)
    cache = resolve_embedding_cache(cache_dir)
    try:
        snapshot = _resolve_snapshot(cache, local_files_only=True)
        manifest = validate_embedding_snapshot(snapshot, cache_dir=cache)
    except EmbeddingModelError as error:
        downloadable = error.cause in {
            "configured embedding model is not cached",
            "configured embedding model snapshot is incomplete",
        }
        if not allow_model_download or not downloadable:
            raise
        snapshot = _resolve_snapshot(cache, local_files_only=False)
        manifest = validate_embedding_snapshot(snapshot, cache_dir=cache)
        status: Literal["already_cached", "downloaded"] = "downloaded"
    else:
        status = "already_cached"
    return EmbeddingPreparationResult(
        status=status,
        model_id=model_id,
        model_revision=model_revision,
        snapshot_fingerprint=manifest.snapshot_fingerprint,
    )


def doctor_embedding(
    *,
    cache_dir: Path,
    model: object,
    revision: object,
) -> EmbeddingReadiness:
    try:
        model_id, model_revision = require_embedding_model_identity(model, revision)
    except EmbeddingModelError as error:
        return _not_ready(error, checks=())
    checks = [ReadinessCheck("dependencies", "passed", "optional dependency available")]
    try:
        snapshot = _resolve_snapshot(cache_dir, local_files_only=True)
        manifest = validate_embedding_snapshot(snapshot, cache_dir=cache_dir)
    except EmbeddingModelError as error:
        checks.append(ReadinessCheck("model", "failed", "model snapshot unavailable"))
        return _not_ready(error, checks=tuple(checks))
    checks.extend(
        (
            ReadinessCheck("model", "passed", "exact model revision cached"),
            ReadinessCheck("snapshot", "passed", "snapshot manifest complete"),
        )
    )
    return EmbeddingReadiness(
        status="ready",
        model_id=model_id,
        model_revision=model_revision,
        snapshot_fingerprint=manifest.snapshot_fingerprint,
        checks=tuple(checks),
        cause=None,
        next_step=None,
    )


def _resolve_snapshot(cache_dir: Path, *, local_files_only: bool) -> Path:
    try:
        hub = import_module("huggingface_hub")
        snapshot_download = cast(_SnapshotDownload, hub.snapshot_download)
    except (ImportError, AttributeError) as error:
        raise EmbeddingModelError(
            "embedding optional dependency is not installed",
            "install_embedding_extra",
        ) from error
    try:
        resolved = snapshot_download(
            repo_id=MODEL_ID,
            revision=MODEL_REVISION,
            cache_dir=str(cache_dir),
            local_files_only=local_files_only,
        )
    except Exception as error:
        raise _classify_resolution_error(error, local_files_only=local_files_only) from error
    return Path(resolved)


def _classify_resolution_error(
    error: Exception,
    *,
    local_files_only: bool,
) -> EmbeddingModelError:
    error_name = type(error).__name__
    if isinstance(error, PermissionError):
        return EmbeddingModelError(
            "embedding model cache is not readable",
            "check_embedding_cache_permissions",
        )
    if error_name in {"RevisionNotFoundError", "RepositoryNotFoundError"}:
        return EmbeddingModelError(
            "configured embedding model revision is unavailable",
            "restore_exact_embedding_model_revision",
        )
    if local_files_only and (
        isinstance(error, FileNotFoundError)
        or error_name in {"LocalEntryNotFoundError", "CacheNotFound"}
    ):
        return EmbeddingModelError(
            "configured embedding model is not cached",
            "run_embedding_prepare",
        )
    if not local_files_only:
        return EmbeddingModelError(
            "embedding model download failed",
            "check_network_before_authorized_retry",
        )
    return EmbeddingModelError(
        "configured embedding model snapshot is incomplete",
        "restore_exact_embedding_model_snapshot",
    )


def _resolve_snapshot_file(logical_path: Path, *, snapshot_root: Path) -> Path:
    if not logical_path.is_symlink():
        return logical_path
    try:
        direct_target = logical_path.parent / os.readlink(logical_path)
        if direct_target.is_symlink():
            raise OSError("chained symlink")
        target = direct_target.resolve(strict=True)
    except OSError as error:
        raise _snapshot_error("configured embedding model snapshot is incomplete") from error
    blobs = (snapshot_root.parent.parent / "blobs").resolve(strict=False)
    if not target.is_relative_to(blobs):
        raise _snapshot_error("configured embedding model snapshot is incomplete")
    return target


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_error(cause: str) -> EmbeddingModelError:
    return EmbeddingModelError(cause, "restore_exact_embedding_model_snapshot")


def _not_ready(
    error: EmbeddingModelError,
    *,
    checks: tuple[ReadinessCheck, ...],
) -> EmbeddingReadiness:
    return EmbeddingReadiness(
        status="not_ready",
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        snapshot_fingerprint=None,
        checks=checks,
        cause=error.cause,
        next_step=error.next_step,
    )
