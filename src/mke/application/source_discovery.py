"""Shared, loss-aware response assembly for MCP and CLI Source discovery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import overload

from mke.application.evidence_access import (
    MAX_CANONICAL_MODEL_BYTES,
    MAX_EXCERPT_CONTENT_BYTES,
    ResponseTooLargeError,
    canonical_json_bytes,
)
from mke.domain.source_discovery import SourceBrowsePage, SourceCatalogPage


@dataclass(frozen=True)
class SourcePageAssembly[Page: SourceCatalogPage | SourceBrowsePage]:
    page: Page
    next_cursor: str | None


@overload
def assemble_source_page(
    page: SourceCatalogPage,
    *,
    cursor_factory: Callable[[int], str],
    serialize_response: Callable[[SourceCatalogPage, str | None], object],
) -> SourcePageAssembly[SourceCatalogPage]: ...


@overload
def assemble_source_page(
    page: SourceBrowsePage,
    *,
    cursor_factory: Callable[[int], str],
    serialize_response: Callable[[SourceBrowsePage, str | None], object],
) -> SourcePageAssembly[SourceBrowsePage]: ...


def assemble_source_page[Page: SourceCatalogPage | SourceBrowsePage](
    page: Page,
    *,
    cursor_factory: Callable[[int], str],
    serialize_response: Callable[[Page, str | None], object],
) -> SourcePageAssembly[Page]:
    """Measure the caller's exact canonical envelope, including the next cursor.

    Callers serialize strict public response models to JSON-compatible objects.
    A size-limited success advances by the count actually returned, never by the
    requested page size. Mandatory metadata that cannot fit raises a bounded error.
    """
    count = len(page.sources) if isinstance(page, SourceCatalogPage) else len(page.entries)
    for returned in range(count, -1, -1):
        more = page.more_available or returned < count
        if more and returned == 0:
            break
        if isinstance(page, SourceCatalogPage):
            selected = replace(page, sources=page.sources[:returned], more_available=more)
            content_bytes = 0
        else:
            selected = replace(page, entries=page.entries[:returned], more_available=more)
            content_bytes = sum(entry.preview.returned_utf8_bytes for entry in selected.entries)
        cursor = cursor_factory(page.position + returned) if more else None
        if (
            content_bytes <= MAX_EXCERPT_CONTENT_BYTES
            and len(canonical_json_bytes(serialize_response(selected, cursor)))
            <= MAX_CANONICAL_MODEL_BYTES
        ):
            return SourcePageAssembly(selected, cursor)
    raise ResponseTooLargeError("Source response metadata exceeds the bounded envelope")
