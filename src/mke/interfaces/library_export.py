"""Closed CLI response boundary for compiled local Library export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from mke.adapters.filesystem import OutputPublicationError, publish_compiled_library
from mke.application import KnowledgeEngine
from mke.domain import LibraryExportDataError
from mke.interfaces.public_errors import PublicError

_SCHEMA_VERSION = "mke.compiled_library_export_response.v1"
_REDACTED_CAUSE = "operation failed; details were redacted"
_NON_REDACTED_CAUSES = frozenset(
    {
        "local Library has no active Publications",
        "active Publication provenance graph is invalid",
        "local Library database is unavailable or incompatible",
        "output directory must not already exist",
        "output parent is invalid",
        "active Library exceeds v1 export limits",
    }
)
_EXPORT_CAUSES = _NON_REDACTED_CAUSES | {_REDACTED_CAUSE}
_MachineToken = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,127}$")]
_Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class LibraryExportSuccessV1(_StrictModel):
    schema_version: Literal["mke.compiled_library_export_response.v1"] = _SCHEMA_VERSION
    ok: Literal[True] = True
    library_id: Literal["local"] = "local"
    source_count: int = Field(ge=1)
    evidence_count: int = Field(ge=1)
    manifest_sha256: _Sha256


class LibraryExportErrorV1(_StrictModel):
    schema_version: Literal["mke.compiled_library_export_response.v1"] = _SCHEMA_VERSION
    ok: Literal[False]
    problem: _MachineToken
    cause: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    active_publication_impact: Literal["unchanged"] = "unchanged"
    next_step: _MachineToken

    @model_validator(mode="after")
    def validate_export_cause(self) -> LibraryExportErrorV1:
        if self.cause not in _EXPORT_CAUSES:
            raise ValueError("error cause is not approved for the Library export boundary")
        return self


def library_export_error_payload(error: PublicError) -> dict[str, object]:
    return {"schema_version": _SCHEMA_VERSION, **error.payload()}


def _error_model(error: PublicError) -> LibraryExportErrorV1:
    return LibraryExportErrorV1.model_validate(library_export_error_payload(error))


def _render_response(
    payload: LibraryExportSuccessV1 | LibraryExportErrorV1, *, json_output: bool
) -> str:
    if json_output:
        return json.dumps(
            payload.model_dump(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
    if isinstance(payload, LibraryExportSuccessV1):
        return (
            "library_export=passed "
            f"library_id={payload.library_id} "
            f"source_count={payload.source_count} "
            f"evidence_count={payload.evidence_count} "
            f"manifest_sha256={payload.manifest_sha256}"
        )
    return " ".join(
        f"{key}={value}"
        for key, value in payload.model_dump().items()
        if key not in {"schema_version", "ok"}
    )


def _snapshot_error(error: LibraryExportDataError) -> PublicError:
    if error.reason == "empty":
        return PublicError(
            "library_export_invalid",
            "local Library has no active Publications",
            "ingest_and_publish_source",
        )
    if error.reason == "provenance":
        return PublicError(
            "library_export_invalid",
            "active Publication provenance graph is invalid",
            "repair_local_library",
        )
    return PublicError(
        "library_export_too_large",
        "active Library exceeds v1 export limits",
        "reduce_active_library_or_use_later_export_version",
    )


def _publication_error(error: OutputPublicationError) -> PublicError:
    if error.reason == "target_exists":
        return PublicError(
            "output_path_invalid",
            "output directory must not already exist",
            "choose_new_output_directory",
        )
    if error.reason == "parent_invalid":
        return PublicError(
            "output_path_invalid",
            "output parent is invalid",
            "choose_valid_output_parent",
        )
    if error.reason == "cleanup_failed":
        return PublicError("cleanup_failed", _REDACTED_CAUSE, "inspect_output_parent")
    return PublicError("library_export_failed", _REDACTED_CAUSE, "retry_library_export")


def _redacted_failure() -> LibraryExportErrorV1:
    return _error_model(
        PublicError("library_export_failed", _REDACTED_CAUSE, "retry_library_export")
    )


def run_library_export(
    db_path: Path,
    output_name: str,
    *,
    json_output: bool,
    parent: Path = Path("."),
) -> int:
    """Read one immutable active-state snapshot and publish it under ``parent``."""

    try:
        engine = KnowledgeEngine.open_read_only_export(db_path)
    except Exception:
        response = _error_model(
            PublicError(
                "library_export_invalid",
                "local Library database is unavailable or incompatible",
                "open_current_library_database",
            )
        )
        print(_render_response(response, json_output=json_output))
        return 1

    close_error: Exception | None = None
    try:
        try:
            snapshot = engine.compiled_library_snapshot()
        except LibraryExportDataError as error:
            response: LibraryExportSuccessV1 | LibraryExportErrorV1 = _error_model(
                _snapshot_error(error)
            )
            exit_code = 1
        except Exception:
            response = _redacted_failure()
            exit_code = 1
        else:
            try:
                result = publish_compiled_library(
                    snapshot,
                    output_name=output_name,
                    parent=parent,
                )
                response = LibraryExportSuccessV1.model_validate(
                    {
                        "library_id": result.library_id,
                        "source_count": result.source_count,
                        "evidence_count": result.evidence_count,
                        "manifest_sha256": result.manifest_sha256,
                    }
                )
                exit_code = 0
            except OutputPublicationError as error:
                response = _error_model(_publication_error(error))
                exit_code = 1
            except Exception:
                response = _redacted_failure()
                exit_code = 1
    except Exception:
        response = _redacted_failure()
        exit_code = 1
    finally:
        try:
            engine.close()
        except Exception as error:
            close_error = error

    if close_error is not None:
        response = _redacted_failure()
        exit_code = 1

    print(_render_response(response, json_output=json_output))
    return exit_code
