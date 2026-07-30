"""Pure fixed-selection delivery and bounded context assembly for evaluation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, fields
from functools import wraps
from typing import Literal, ParamSpec, TypeVar

from mke.evaluation.agent_context_unit_diagnostics import (
    AgentContextStageError,
    AgentContextSubstage,
)

_PREFIXED_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_BARE_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_P = ParamSpec("_P")
_R = TypeVar("_R")

_KNOWN_ERRORS: dict[str, tuple[str, str]] = {
    "assembly bounds are invalid": ("assembly_bounds_invalid", "integrity"),
}
_KNOWN_ERRORS.update(
    {
        message: (
            message.replace(" is invalid", " invalid").replace(" ", "_"),
            "capacity" if "capacity exceeded" in message else "integrity",
        )
        for message in (
            "content capacity exceeded",
            "context authority is incomplete",
            "context authority is invalid",
            "context duplication is invalid",
            "context input capacity exceeded",
            "context inventory capacity exceeded",
            "context provenance is invalid",
            "delivery input authority is invalid",
            "envelope authority is invalid",
            "envelope capacity exceeded",
            "item capacity exceeded",
            "item input capacity exceeded",
            "selection authority is invalid",
        )
    }
)

ContextKind = Literal[
    "heading",
    "previous_unit",
    "next_unit",
    "previous_page_tail",
    "next_page_head",
]
ContextStatus = Literal[
    "available",
    "missing",
    "ambiguous",
    "inactive",
    "nonadjacent",
]

_O4_KINDS: tuple[ContextKind, ...] = (
    "heading",
    "previous_unit",
    "next_unit",
)
_O5_KINDS: tuple[ContextKind, ...] = (
    "previous_page_tail",
    "next_page_head",
)
_O4_STATUSES: tuple[ContextStatus, ...] = (
    "available",
    "missing",
    "ambiguous",
    "inactive",
)
_O5_STATUSES: tuple[ContextStatus, ...] = (
    "available",
    "missing",
    "ambiguous",
    "inactive",
    "nonadjacent",
)
_O1_SELECTION_PROFILES = ("deterministic-unit-rank-v1",)
_O5_SELECTION_PROFILES = (
    "current-runtime-baseline-v1",
    "deterministic-unit-rank-v1",
)
_O4_LABELS: dict[ContextKind, bytes] = {
    "heading": b"\n[heading]\n",
    "previous_unit": b"\n[p]\n",
    "next_unit": b"\n[n]\n",
    "previous_page_tail": b"",
    "next_page_head": b"",
}
_O5_LABELS: dict[ContextKind, bytes] = {
    "heading": b"",
    "previous_unit": b"",
    "next_unit": b"",
    "previous_page_tail": b"\n[p]\n",
    "next_page_head": b"\n[n]\n",
}


@dataclass(frozen=True)
class AssemblyBounds:
    max_primary_results: int = 5
    max_item_utf8_bytes: int = 2_048
    max_content_utf8_bytes: int = 16_384
    max_envelope_utf8_bytes: int = 32_768
    max_source_context_utf8_bytes: int = 512
    max_adjacent_utf8_bytes_each: int = 256

    def __post_init__(self) -> None:
        values = tuple(getattr(self, field.name) for field in fields(self))
        if any(type(value) is not int or value < 1 for value in values):
            raise ValueError("assembly bounds are invalid")
        if (
            self.max_primary_results > 5
            or self.max_item_utf8_bytes > 2_048
            or self.max_content_utf8_bytes > 16_384
            or self.max_envelope_utf8_bytes > 32_768
            or self.max_source_context_utf8_bytes > 512
            or self.max_adjacent_utf8_bytes_each > 256
        ):
            raise ValueError("assembly bounds are invalid")


DEFAULT_ASSEMBLY_BOUNDS = AssemblyBounds()


class AgentContextAssemblyStageError(AgentContextStageError):
    def __init__(
        self,
        substage: AgentContextSubstage,
        error_code: str,
        error_family: str,
        message: str,
    ) -> None:
        super().__init__(substage, error_code, error_family)
        self.args = (
            f"{substage.value}:{error_code}:{error_family}: {message}",
        )


def _typed_stage_errors(
    substage: AgentContextSubstage,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    def decorate(operation: Callable[_P, _R]) -> Callable[_P, _R]:
        @wraps(operation)
        def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            try:
                return operation(*args, **kwargs)
            except AgentContextStageError:
                raise
            except ValueError as error:
                authority = _KNOWN_ERRORS.get(str(error))
                if authority is None:
                    raise
                error_code, error_family = authority
                raise AgentContextAssemblyStageError(
                    substage,
                    error_code,
                    error_family,
                    str(error),
                ) from None

        return wrapped

    return decorate


@dataclass(frozen=True)
class SealedSelection:
    stable_context_unit_ids: tuple[str, ...]
    selection_digest: str


@dataclass(frozen=True)
class FrozenDeliveryInput:
    stable_context_unit_id: str
    source_content_fingerprint: str
    publication_identity: str
    origin_evidence_ref: str
    parent_locator: tuple[Literal["page"], int, int]
    origin_start_utf8_byte: int
    origin_end_utf8_byte: int
    text_bytes: bytes
    text_sha256: str
    rank_profile_id: str
    active: bool
    runtime_evidence_handle: str


@dataclass(frozen=True)
class ContextComponentInput:
    selected_stable_context_unit_id: str
    kind: ContextKind
    status: ContextStatus
    source_content_fingerprint: str
    publication_identity: str
    origin_evidence_ref: str
    parent_locator: tuple[Literal["page"], int, int]
    origin_start_utf8_byte: int
    origin_end_utf8_byte: int
    text_bytes: bytes
    text_sha256: str


@dataclass(frozen=True)
class ContextComponentRecord:
    kind: ContextKind
    status: ContextStatus
    source_content_fingerprint: str
    publication_identity: str
    origin_evidence_ref: str
    parent_locator: tuple[Literal["page"], int, int]
    origin_start_utf8_byte: int
    origin_end_utf8_byte: int
    returned_origin_start_utf8_byte: int
    returned_origin_end_utf8_byte: int
    requested_utf8_bytes: int
    returned_utf8_bytes: int
    omitted_utf8_bytes: int
    truncated_utf8_bytes: int
    rendered_utf8_bytes: int
    returned_text_bytes: bytes


@dataclass(frozen=True)
class DeliveredAssemblyItem:
    stable_context_unit_id: str
    source_content_fingerprint: str
    publication_identity: str
    origin_evidence_ref: str
    parent_locator: tuple[Literal["page"], int, int]
    origin_start_utf8_byte: int
    origin_end_utf8_byte: int
    rank_profile_id: str
    selection_digest: str
    unit_text_bytes: bytes
    excerpt_text_bytes: bytes
    delivered_text_bytes: bytes
    requested_utf8_bytes: int
    returned_utf8_bytes: int
    omitted_utf8_bytes: int
    truncated_utf8_bytes: int
    components: tuple[ContextComponentRecord, ...]


@dataclass(frozen=True)
class DeliveryAssemblyResult:
    mechanism_id: str
    selection_digest: str
    selected_stable_context_unit_ids: tuple[str, ...]
    items: tuple[DeliveredAssemblyItem, ...]
    content_utf8_bytes: int
    envelope_utf8_bytes: int

    def portable_bytes(self) -> bytes:
        return _canonical_json_bytes(_portable_result(self))


def seal_selected_identities(
    stable_context_unit_ids: tuple[str, ...],
) -> SealedSelection:
    if (
        type(stable_context_unit_ids) is not tuple
        or not stable_context_unit_ids
        or len(stable_context_unit_ids) > 5
        or any(
            type(stable_id) is not str
            or _PREFIXED_SHA256.fullmatch(stable_id) is None
            for stable_id in stable_context_unit_ids
        )
        or len(set(stable_context_unit_ids)) != len(stable_context_unit_ids)
    ):
        raise ValueError("selection authority is invalid")
    return SealedSelection(
        stable_context_unit_ids=stable_context_unit_ids,
        selection_digest=_selection_digest(stable_context_unit_ids),
    )


@_typed_stage_errors(AgentContextSubstage.FIXED_RANK_DELIVERY)
def assemble_o2_delivery(
    selection: SealedSelection,
    inventory: tuple[FrozenDeliveryInput, ...],
    *,
    bounds: AssemblyBounds = DEFAULT_ASSEMBLY_BOUNDS,
) -> DeliveryAssemblyResult:
    _validate_bounds(bounds)
    ordered = _ordered_delivery_inputs(selection, inventory, bounds)
    lengths = tuple(len(item.text_bytes) for item in ordered)
    if any(length > bounds.max_item_utf8_bytes for length in lengths):
        raise ValueError("item capacity exceeded")
    if sum(lengths) > bounds.max_content_utf8_bytes:
        raise ValueError("content capacity exceeded")
    for item in ordered:
        _validate_delivery_input(
            item, allowed_rank_profile_ids=_O1_SELECTION_PROFILES
        )

    items = tuple(
        DeliveredAssemblyItem(
            stable_context_unit_id=item.stable_context_unit_id,
            source_content_fingerprint=item.source_content_fingerprint,
            publication_identity=item.publication_identity,
            origin_evidence_ref=item.origin_evidence_ref,
            parent_locator=item.parent_locator,
            origin_start_utf8_byte=item.origin_start_utf8_byte,
            origin_end_utf8_byte=item.origin_end_utf8_byte,
            rank_profile_id=item.rank_profile_id,
            selection_digest=selection.selection_digest,
            unit_text_bytes=item.text_bytes,
            excerpt_text_bytes=b"",
            delivered_text_bytes=item.text_bytes,
            requested_utf8_bytes=len(item.text_bytes),
            returned_utf8_bytes=len(item.text_bytes),
            omitted_utf8_bytes=0,
            truncated_utf8_bytes=0,
            components=(),
        )
        for item in ordered
    )
    return _finalize_result(
        mechanism_id="fixed-rank-delivery-v1",
        selection=selection,
        items=items,
        bounds=bounds,
    )


@_typed_stage_errors(AgentContextSubstage.SOURCE_CONTEXT_DELIVERY)
def assemble_o4_delivery(
    selection: SealedSelection,
    inventory: tuple[FrozenDeliveryInput, ...],
    context_inventory: tuple[ContextComponentInput, ...],
    *,
    bounds: AssemblyBounds = DEFAULT_ASSEMBLY_BOUNDS,
) -> DeliveryAssemblyResult:
    _validate_bounds(bounds)
    ordered = _ordered_delivery_inputs(selection, inventory, bounds)
    _validate_context_inventory_container(context_inventory)
    if len(context_inventory) > len(ordered) * len(_O4_KINDS):
        raise ValueError("context inventory capacity exceeded")
    _preflight_context_input_capacity(context_inventory, bounds)
    if any(len(item.text_bytes) > bounds.max_item_utf8_bytes for item in ordered):
        raise ValueError("item capacity exceeded")
    for item in ordered:
        _validate_delivery_input(
            item, allowed_rank_profile_ids=_O1_SELECTION_PROFILES
        )
    grouped = _validated_context_inventory(
        ordered,
        context_inventory,
        allowed_kinds=_O4_KINDS,
        allowed_statuses=_O4_STATUSES,
        adjacent=False,
    )

    items: list[DeliveredAssemblyItem] = []
    for selected in ordered:
        remaining = min(
            bounds.max_source_context_utf8_bytes,
            bounds.max_item_utf8_bytes - len(selected.text_bytes),
        )
        records: list[ContextComponentRecord] = []
        rendered_parts: list[bytes] = [selected.text_bytes]
        for kind in _O4_KINDS:
            component = grouped.get(selected.stable_context_unit_id, {}).get(kind)
            if component is None:
                continue
            record, rendered = _allocate_component(
                component,
                label=_O4_LABELS[kind],
                remaining=remaining,
                payload_ceiling=remaining,
                take_tail=kind == "previous_unit",
            )
            records.append(record)
            if rendered:
                rendered_parts.append(rendered)
                remaining -= len(rendered)
        delivered = b"".join(rendered_parts)
        requested = len(selected.text_bytes) + sum(
            _requested_rendered_bytes(component, _O4_LABELS[component.kind])
            for component in grouped[selected.stable_context_unit_id].values()
        )
        returned = len(delivered)
        omitted = requested - returned
        items.append(
            DeliveredAssemblyItem(
                stable_context_unit_id=selected.stable_context_unit_id,
                source_content_fingerprint=selected.source_content_fingerprint,
                publication_identity=selected.publication_identity,
                origin_evidence_ref=selected.origin_evidence_ref,
                parent_locator=selected.parent_locator,
                origin_start_utf8_byte=selected.origin_start_utf8_byte,
                origin_end_utf8_byte=selected.origin_end_utf8_byte,
                rank_profile_id=selected.rank_profile_id,
                selection_digest=selection.selection_digest,
                unit_text_bytes=selected.text_bytes,
                excerpt_text_bytes=b"",
                delivered_text_bytes=delivered,
                requested_utf8_bytes=requested,
                returned_utf8_bytes=returned,
                omitted_utf8_bytes=omitted,
                truncated_utf8_bytes=omitted,
                components=tuple(records),
            )
        )
    return _finalize_result(
        mechanism_id="source-context-delivery-v1",
        selection=selection,
        items=tuple(items),
        bounds=bounds,
    )


@_typed_stage_errors(AgentContextSubstage.ADJACENT_PAGE_ASSEMBLY)
def assemble_o5_delivery(
    selection: SealedSelection,
    inventory: tuple[FrozenDeliveryInput, ...],
    context_inventory: tuple[ContextComponentInput, ...],
    *,
    bounds: AssemblyBounds = DEFAULT_ASSEMBLY_BOUNDS,
) -> DeliveryAssemblyResult:
    _validate_bounds(bounds)
    ordered = _ordered_delivery_inputs(selection, inventory, bounds)
    _validate_context_inventory_container(context_inventory)
    if len(context_inventory) > len(ordered) * len(_O5_KINDS):
        raise ValueError("context inventory capacity exceeded")
    if any(len(item.text_bytes) > bounds.max_content_utf8_bytes for item in ordered):
        raise ValueError("item input capacity exceeded")
    _preflight_context_input_capacity(context_inventory, bounds)
    for item in ordered:
        _validate_delivery_input(
            item,
            allowed_rank_profile_ids=_O5_SELECTION_PROFILES,
            require_active=True,
        )
    grouped = _validated_context_inventory(
        ordered,
        context_inventory,
        allowed_kinds=_O5_KINDS,
        allowed_statuses=_O5_STATUSES,
        adjacent=True,
    )

    items: list[DeliveredAssemblyItem] = []
    for selected in ordered:
        excerpt = _utf8_prefix(selected.text_bytes, bounds.max_item_utf8_bytes)
        remaining = bounds.max_item_utf8_bytes - len(excerpt)
        records: list[ContextComponentRecord] = []
        rendered_parts: list[bytes] = [excerpt]
        for kind in _O5_KINDS:
            component = grouped.get(selected.stable_context_unit_id, {}).get(kind)
            if component is None:
                continue
            record, rendered = _allocate_component(
                component,
                label=_O5_LABELS[kind],
                remaining=remaining,
                payload_ceiling=bounds.max_adjacent_utf8_bytes_each,
                take_tail=kind == "previous_page_tail",
            )
            records.append(record)
            if rendered:
                rendered_parts.append(rendered)
                remaining -= len(rendered)
        delivered = b"".join(rendered_parts)
        requested = len(selected.text_bytes) + sum(
            _requested_rendered_bytes(component, _O5_LABELS[component.kind])
            for component in grouped[selected.stable_context_unit_id].values()
        )
        returned = len(delivered)
        omitted = requested - returned
        items.append(
            DeliveredAssemblyItem(
                stable_context_unit_id=selected.stable_context_unit_id,
                source_content_fingerprint=selected.source_content_fingerprint,
                publication_identity=selected.publication_identity,
                origin_evidence_ref=selected.origin_evidence_ref,
                parent_locator=selected.parent_locator,
                origin_start_utf8_byte=selected.origin_start_utf8_byte,
                origin_end_utf8_byte=selected.origin_end_utf8_byte,
                rank_profile_id=selected.rank_profile_id,
                selection_digest=selection.selection_digest,
                unit_text_bytes=b"",
                excerpt_text_bytes=excerpt,
                delivered_text_bytes=delivered,
                requested_utf8_bytes=requested,
                returned_utf8_bytes=returned,
                omitted_utf8_bytes=omitted,
                truncated_utf8_bytes=omitted,
                components=tuple(records),
            )
        )
    return _finalize_result(
        mechanism_id="adjacent-page-assembly-v1",
        selection=selection,
        items=tuple(items),
        bounds=bounds,
    )


def _ordered_delivery_inputs(
    selection: SealedSelection,
    inventory: tuple[FrozenDeliveryInput, ...],
    bounds: AssemblyBounds,
) -> tuple[FrozenDeliveryInput, ...]:
    _validate_selection(selection, bounds)
    if (
        type(inventory) is not tuple
        or len(inventory) != len(selection.stable_context_unit_ids)
        or len(inventory) > bounds.max_primary_results
        or any(type(item) is not FrozenDeliveryInput for item in inventory)
    ):
        raise ValueError("selection authority is invalid")
    for item in inventory:
        _validate_delivery_input_shape(item)
    identities = tuple(item.stable_context_unit_id for item in inventory)
    if (
        any(type(identity) is not str for identity in identities)
        or len(set(identities)) != len(identities)
        or set(identities) != set(selection.stable_context_unit_ids)
    ):
        raise ValueError("selection authority is invalid")
    by_identity = {item.stable_context_unit_id: item for item in inventory}
    return tuple(
        by_identity[stable_id] for stable_id in selection.stable_context_unit_ids
    )


def _preflight_context_input_capacity(
    context_inventory: tuple[ContextComponentInput, ...],
    bounds: AssemblyBounds,
) -> None:
    if (
        type(context_inventory) is not tuple
        or any(
            type(component) is not ContextComponentInput
            or type(component.text_bytes) is not bytes
            for component in context_inventory
        )
    ):
        raise ValueError("context authority is invalid")
    if any(
        len(component.text_bytes) > bounds.max_content_utf8_bytes
        for component in context_inventory
    ):
        raise ValueError("context input capacity exceeded")


def _validate_bounds(bounds: object) -> None:
    if type(bounds) is not AssemblyBounds:
        raise ValueError("assembly bounds are invalid")


def _validate_context_inventory_container(context_inventory: object) -> None:
    if type(context_inventory) is not tuple:
        raise ValueError("context authority is invalid")


def _validate_selection(
    selection: SealedSelection, bounds: AssemblyBounds
) -> None:
    if (
        type(selection) is not SealedSelection
        or type(selection.stable_context_unit_ids) is not tuple
        or not selection.stable_context_unit_ids
        or len(selection.stable_context_unit_ids) > bounds.max_primary_results
        or any(
            type(stable_id) is not str
            or _PREFIXED_SHA256.fullmatch(stable_id) is None
            for stable_id in selection.stable_context_unit_ids
        )
        or len(set(selection.stable_context_unit_ids))
        != len(selection.stable_context_unit_ids)
        or type(selection.selection_digest) is not str
        or selection.selection_digest
        != _selection_digest(selection.stable_context_unit_ids)
    ):
        raise ValueError("selection authority is invalid")


def _validate_delivery_input(
    item: FrozenDeliveryInput,
    *,
    allowed_rank_profile_ids: tuple[str, ...],
    require_active: bool = True,
) -> None:
    _validate_delivery_input_shape(item)
    if (
        _PREFIXED_SHA256.fullmatch(item.stable_context_unit_id) is None
        or _PREFIXED_SHA256.fullmatch(item.source_content_fingerprint) is None
        or _PREFIXED_SHA256.fullmatch(item.publication_identity) is None
        or _PREFIXED_SHA256.fullmatch(item.origin_evidence_ref) is None
        or item.parent_locator[0] != "page"
        or item.parent_locator[1] < 1
        or item.parent_locator[2] != item.parent_locator[1]
        or item.origin_start_utf8_byte < 0
        or item.origin_end_utf8_byte
        != item.origin_start_utf8_byte + len(item.text_bytes)
        or _BARE_SHA256.fullmatch(item.text_sha256) is None
        or item.text_sha256 != hashlib.sha256(item.text_bytes).hexdigest()
        or item.rank_profile_id not in allowed_rank_profile_ids
        or item.stable_context_unit_id != _stable_unit_id(item)
        or (require_active and not item.active)
    ):
        raise ValueError("delivery input authority is invalid")
    try:
        item.text_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("delivery input authority is invalid") from error


def _validate_delivery_input_shape(item: FrozenDeliveryInput) -> None:
    if (
        type(item) is not FrozenDeliveryInput
        or type(item.stable_context_unit_id) is not str
        or type(item.source_content_fingerprint) is not str
        or type(item.publication_identity) is not str
        or type(item.origin_evidence_ref) is not str
        or type(item.parent_locator) is not tuple
        or len(item.parent_locator) != 3
        or type(item.parent_locator[0]) is not str
        or type(item.parent_locator[1]) is not int
        or type(item.parent_locator[2]) is not int
        or type(item.origin_start_utf8_byte) is not int
        or type(item.origin_end_utf8_byte) is not int
        or type(item.text_bytes) is not bytes
        or type(item.text_sha256) is not str
        or type(item.rank_profile_id) is not str
        or type(item.active) is not bool
        or type(item.runtime_evidence_handle) is not str
    ):
        raise ValueError("delivery input authority is invalid")


def _validated_context_inventory(
    selected_items: tuple[FrozenDeliveryInput, ...],
    context_inventory: tuple[ContextComponentInput, ...],
    *,
    allowed_kinds: tuple[ContextKind, ...],
    allowed_statuses: tuple[ContextStatus, ...],
    adjacent: bool,
) -> dict[str, dict[ContextKind, ContextComponentInput]]:
    if (
        type(context_inventory) is not tuple
        or any(
            type(component) is not ContextComponentInput
            for component in context_inventory
        )
    ):
        raise ValueError("context authority is invalid")
    selected_by_id = {
        item.stable_context_unit_id: item for item in selected_items
    }
    grouped: dict[str, dict[ContextKind, ContextComponentInput]] = {}
    seen_ranges: dict[
        tuple[str, str, str, tuple[Literal["page"], int, int]],
        list[tuple[int, int]],
    ] = {}
    seen_payloads: set[bytes] = set()
    for component in context_inventory:
        _validate_context_component(
            component, allowed_kinds, allowed_statuses
        )
        selected = selected_by_id.get(
            component.selected_stable_context_unit_id
        )
        if selected is None:
            raise ValueError("context provenance is invalid")
        if (
            component.source_content_fingerprint
            != selected.source_content_fingerprint
            or component.publication_identity != selected.publication_identity
        ):
            raise ValueError("context provenance is invalid")
        if adjacent:
            expected_page = selected.parent_locator[1] + (
                -1 if component.kind == "previous_page_tail" else 1
            )
            expected_locator = ("page", expected_page, expected_page)
            if expected_page < 1:
                valid_locator = (
                    component.status == "missing"
                    and component.parent_locator == selected.parent_locator
                )
            elif component.status == "nonadjacent":
                valid_locator = component.parent_locator != expected_locator
            else:
                valid_locator = component.parent_locator == expected_locator
            if not valid_locator:
                raise ValueError("context provenance is invalid")
        elif component.parent_locator != selected.parent_locator:
            raise ValueError("context provenance is invalid")
        per_selected = grouped.setdefault(
            component.selected_stable_context_unit_id, {}
        )
        if component.kind in per_selected:
            raise ValueError("context duplication is invalid")
        if component.status == "available" and component.text_bytes:
            range_authority = (
                component.source_content_fingerprint,
                component.publication_identity,
                component.origin_evidence_ref,
                component.parent_locator,
            )
            component_range = (
                component.origin_start_utf8_byte,
                component.origin_end_utf8_byte,
            )
            overlaps = any(
                component_range[0] < end and start < component_range[1]
                for start, end in seen_ranges.get(range_authority, ())
            )
            if overlaps or component.text_bytes in seen_payloads:
                raise ValueError("context duplication is invalid")
            seen_ranges.setdefault(range_authority, []).append(component_range)
            seen_payloads.add(component.text_bytes)
        if not adjacent and component.status == "available":
            if (
                component.kind == "heading"
                and component.origin_end_utf8_byte
                > selected.origin_start_utf8_byte
            ) or (
                component.kind == "previous_unit"
                and component.origin_end_utf8_byte
                != selected.origin_start_utf8_byte
            ) or (
                component.kind == "next_unit"
                and component.origin_start_utf8_byte
                != selected.origin_end_utf8_byte
            ):
                raise ValueError("context provenance is invalid")
        per_selected[component.kind] = component
    if any(
        set(grouped.get(item.stable_context_unit_id, ())) != set(allowed_kinds)
        for item in selected_items
    ):
        raise ValueError("context authority is incomplete")
    return grouped


def _validate_context_component(
    component: ContextComponentInput,
    allowed_kinds: tuple[ContextKind, ...],
    allowed_statuses: tuple[ContextStatus, ...],
) -> None:
    if (
        type(component) is not ContextComponentInput
        or type(component.selected_stable_context_unit_id) is not str
        or type(component.kind) is not str
        or type(component.status) is not str
        or type(component.source_content_fingerprint) is not str
        or type(component.publication_identity) is not str
        or type(component.origin_evidence_ref) is not str
        or type(component.parent_locator) is not tuple
        or len(component.parent_locator) != 3
        or type(component.parent_locator[0]) is not str
        or type(component.parent_locator[1]) is not int
        or type(component.parent_locator[2]) is not int
        or type(component.origin_start_utf8_byte) is not int
        or type(component.origin_end_utf8_byte) is not int
        or type(component.text_bytes) is not bytes
        or type(component.text_sha256) is not str
    ):
        raise ValueError("context authority is invalid")
    if (
        component.kind not in allowed_kinds
        or component.status not in allowed_statuses
        or _PREFIXED_SHA256.fullmatch(
            component.selected_stable_context_unit_id
        )
        is None
        or _PREFIXED_SHA256.fullmatch(
            component.source_content_fingerprint
        )
        is None
        or _PREFIXED_SHA256.fullmatch(component.publication_identity) is None
        or _PREFIXED_SHA256.fullmatch(component.origin_evidence_ref) is None
        or component.parent_locator[0] != "page"
        or component.parent_locator[1] < 1
        or component.parent_locator[2] != component.parent_locator[1]
        or component.origin_start_utf8_byte < 0
        or component.origin_end_utf8_byte
        != component.origin_start_utf8_byte + len(component.text_bytes)
        or _BARE_SHA256.fullmatch(component.text_sha256) is None
        or component.text_sha256
        != hashlib.sha256(component.text_bytes).hexdigest()
        or (
            component.status == "available"
            and not component.text_bytes
        )
        or (
            component.status != "available"
            and component.text_bytes
        )
    ):
        raise ValueError("context authority is invalid")
    try:
        component.text_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("context authority is invalid") from error


def _allocate_component(
    component: ContextComponentInput,
    *,
    label: bytes,
    remaining: int,
    payload_ceiling: int,
    take_tail: bool,
) -> tuple[ContextComponentRecord, bytes]:
    if component.status != "available":
        return (
            _component_record(
                component,
                returned=b"",
                returned_start=component.origin_start_utf8_byte,
                rendered_utf8_bytes=0,
            ),
            b"",
        )
    payload_budget = min(payload_ceiling, max(0, remaining - len(label)))
    returned = (
        _utf8_suffix(component.text_bytes, payload_budget)
        if take_tail
        else _utf8_prefix(component.text_bytes, payload_budget)
    )
    if not returned:
        rendered = b""
        returned_start = component.origin_start_utf8_byte
    else:
        rendered = label + returned
        returned_start = (
            component.origin_end_utf8_byte - len(returned)
            if take_tail
            else component.origin_start_utf8_byte
        )
    return (
        _component_record(
            component,
            returned=returned,
            returned_start=returned_start,
            rendered_utf8_bytes=len(rendered),
        ),
        rendered,
    )


def _requested_rendered_bytes(
    component: ContextComponentInput, label: bytes
) -> int:
    if component.status != "available":
        return 0
    return len(label) + len(component.text_bytes)


def _component_record(
    component: ContextComponentInput,
    *,
    returned: bytes,
    returned_start: int,
    rendered_utf8_bytes: int,
) -> ContextComponentRecord:
    requested = len(component.text_bytes)
    returned_count = len(returned)
    omitted = requested - returned_count
    return ContextComponentRecord(
        kind=component.kind,
        status=component.status,
        source_content_fingerprint=component.source_content_fingerprint,
        publication_identity=component.publication_identity,
        origin_evidence_ref=component.origin_evidence_ref,
        parent_locator=component.parent_locator,
        origin_start_utf8_byte=component.origin_start_utf8_byte,
        origin_end_utf8_byte=component.origin_end_utf8_byte,
        returned_origin_start_utf8_byte=returned_start,
        returned_origin_end_utf8_byte=returned_start + returned_count,
        requested_utf8_bytes=requested,
        returned_utf8_bytes=returned_count,
        omitted_utf8_bytes=omitted,
        truncated_utf8_bytes=omitted,
        rendered_utf8_bytes=rendered_utf8_bytes,
        returned_text_bytes=returned,
    )


def _finalize_result(
    *,
    mechanism_id: str,
    selection: SealedSelection,
    items: tuple[DeliveredAssemblyItem, ...],
    bounds: AssemblyBounds,
) -> DeliveryAssemblyResult:
    content_count = sum(len(item.delivered_text_bytes) for item in items)
    if content_count > bounds.max_content_utf8_bytes:
        raise ValueError("content capacity exceeded")
    envelope_count = 0
    result = DeliveryAssemblyResult(
        mechanism_id=mechanism_id,
        selection_digest=selection.selection_digest,
        selected_stable_context_unit_ids=selection.stable_context_unit_ids,
        items=items,
        content_utf8_bytes=content_count,
        envelope_utf8_bytes=envelope_count,
    )
    for _ in range(4):
        envelope_count = len(result.portable_bytes())
        result = DeliveryAssemblyResult(
            mechanism_id=result.mechanism_id,
            selection_digest=result.selection_digest,
            selected_stable_context_unit_ids=result.selected_stable_context_unit_ids,
            items=result.items,
            content_utf8_bytes=result.content_utf8_bytes,
            envelope_utf8_bytes=envelope_count,
        )
    if len(result.portable_bytes()) != envelope_count:
        raise ValueError("envelope authority is invalid")
    if envelope_count > bounds.max_envelope_utf8_bytes:
        raise ValueError("envelope capacity exceeded")
    return result


def _selection_digest(stable_ids: tuple[str, ...]) -> str:
    return "sha256:" + hashlib.sha256(
        _canonical_json_bytes({"stable_context_unit_ids": list(stable_ids)})
    ).hexdigest()


def _stable_unit_id(item: FrozenDeliveryInput) -> str:
    payload = {
        "content_fingerprint": item.source_content_fingerprint,
        "end_utf8_byte": item.origin_end_utf8_byte,
        "locator_end": item.parent_locator[2],
        "locator_kind": item.parent_locator[0],
        "locator_start": item.parent_locator[1],
        "rank_profile_id": item.rank_profile_id,
        "start_utf8_byte": item.origin_start_utf8_byte,
        "text_sha256": item.text_sha256,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _utf8_prefix(data: bytes, limit: int) -> bytes:
    end = min(len(data), max(0, limit))
    while end > 0:
        try:
            data[:end].decode("utf-8")
        except UnicodeDecodeError:
            end -= 1
        else:
            return data[:end]
    return b""


def _utf8_suffix(data: bytes, limit: int) -> bytes:
    start = max(0, len(data) - max(0, limit))
    while start < len(data):
        try:
            data[start:].decode("utf-8")
        except UnicodeDecodeError:
            start += 1
        else:
            return data[start:]
    return b""


def _portable_result(result: DeliveryAssemblyResult) -> dict[str, object]:
    return {
        "content_utf8_bytes": result.content_utf8_bytes,
        "envelope_utf8_bytes": result.envelope_utf8_bytes,
        "items": [_portable_item(item) for item in result.items],
        "mechanism_id": result.mechanism_id,
        "selected_stable_context_unit_ids": list(
            result.selected_stable_context_unit_ids
        ),
        "selection_digest": result.selection_digest,
    }


def _portable_item(item: DeliveredAssemblyItem) -> dict[str, object]:
    return {
        "components": [
            _portable_component(component) for component in item.components
        ],
        "delivered_text": item.delivered_text_bytes.decode("utf-8"),
        "excerpt_text": item.excerpt_text_bytes.decode("utf-8"),
        "omitted_utf8_bytes": item.omitted_utf8_bytes,
        "origin_end_utf8_byte": item.origin_end_utf8_byte,
        "origin_evidence_ref": item.origin_evidence_ref,
        "origin_start_utf8_byte": item.origin_start_utf8_byte,
        "parent_locator": list(item.parent_locator),
        "publication_identity": item.publication_identity,
        "requested_utf8_bytes": item.requested_utf8_bytes,
        "returned_utf8_bytes": item.returned_utf8_bytes,
        "rank_profile_id": item.rank_profile_id,
        "selection_digest": item.selection_digest,
        "source_content_fingerprint": item.source_content_fingerprint,
        "stable_context_unit_id": item.stable_context_unit_id,
        "truncated_utf8_bytes": item.truncated_utf8_bytes,
        "unit_text": item.unit_text_bytes.decode("utf-8"),
    }


def _portable_component(
    component: ContextComponentRecord,
) -> dict[str, object]:
    return {
        "kind": component.kind,
        "omitted_utf8_bytes": component.omitted_utf8_bytes,
        "origin_end_utf8_byte": component.origin_end_utf8_byte,
        "origin_evidence_ref": component.origin_evidence_ref,
        "origin_start_utf8_byte": component.origin_start_utf8_byte,
        "parent_locator": list(component.parent_locator),
        "publication_identity": component.publication_identity,
        "rendered_utf8_bytes": component.rendered_utf8_bytes,
        "requested_utf8_bytes": component.requested_utf8_bytes,
        "returned_origin_end_utf8_byte": (
            component.returned_origin_end_utf8_byte
        ),
        "returned_origin_start_utf8_byte": (
            component.returned_origin_start_utf8_byte
        ),
        "returned_text": component.returned_text_bytes.decode("utf-8"),
        "returned_utf8_bytes": component.returned_utf8_bytes,
        "source_content_fingerprint": component.source_content_fingerprint,
        "status": component.status,
        "truncated_utf8_bytes": component.truncated_utf8_bytes,
    }


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
