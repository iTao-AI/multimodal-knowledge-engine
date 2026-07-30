from __future__ import annotations

import dataclasses
import hashlib
import importlib
import inspect
import json
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from mke.evaluation.agent_context_unit_diagnostics import (
    AgentContextStageError,
)

ROOT = Path(__file__).resolve().parents[2]


def _assembly() -> ModuleType:
    return importlib.import_module("mke.evaluation.agent_context_unit_assembly")


def _sha(character: str) -> str:
    return "sha256:" + character * 64


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _selected(
    module: ModuleType,
    text: bytes = b"authoritative unit",
    *,
    stable_id: str | None = None,
    fingerprint: str | None = None,
    publication: str | None = None,
    evidence: str | None = None,
    page: int = 2,
    start: int = 100,
    active: bool = True,
    rank_profile_id: str = "deterministic-unit-rank-v1",
    runtime_handle: str = "opaque-workspace-a",
) -> Any:
    source_fingerprint = fingerprint or _sha("2")
    text_sha256 = _digest(text)
    stable_payload = {
        "content_fingerprint": source_fingerprint,
        "end_utf8_byte": start + len(text),
        "locator_end": page,
        "locator_kind": "page",
        "locator_start": page,
        "rank_profile_id": rank_profile_id,
        "start_utf8_byte": start,
        "text_sha256": text_sha256,
    }
    computed_stable_id = "sha256:" + hashlib.sha256(
        json.dumps(
            stable_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return module.FrozenDeliveryInput(
        stable_context_unit_id=stable_id or computed_stable_id,
        source_content_fingerprint=source_fingerprint,
        publication_identity=publication or _sha("3"),
        origin_evidence_ref=evidence or _sha("4"),
        parent_locator=("page", page, page),
        origin_start_utf8_byte=start,
        origin_end_utf8_byte=start + len(text),
        text_bytes=text,
        text_sha256=text_sha256,
        rank_profile_id=rank_profile_id,
        active=active,
        runtime_evidence_handle=runtime_handle,
    )


def _selection(module: ModuleType, *stable_ids: str) -> Any:
    return module.seal_selected_identities(tuple(stable_ids))


def _component(
    module: ModuleType,
    selected: Any,
    *,
    kind: str,
    text: bytes = b"context",
    status: str = "available",
    page: int | None = None,
    start: int | None = None,
    fingerprint: str | None = None,
    publication: str | None = None,
    evidence: str | None = None,
) -> Any:
    locator_page = selected.parent_locator[1] if page is None else page
    payload = text if status == "available" else b""
    if start is None:
        if kind == "previous_unit":
            start = selected.origin_start_utf8_byte - len(payload)
        elif kind == "next_unit":
            start = selected.origin_end_utf8_byte
        else:
            start = 0
    assert start is not None
    return module.ContextComponentInput(
        selected_stable_context_unit_id=selected.stable_context_unit_id,
        kind=kind,
        status=status,
        source_content_fingerprint=fingerprint
        or selected.source_content_fingerprint,
        publication_identity=publication or selected.publication_identity,
        origin_evidence_ref=evidence or selected.origin_evidence_ref,
        parent_locator=("page", locator_page, locator_page),
        origin_start_utf8_byte=start,
        origin_end_utf8_byte=start + len(payload),
        text_bytes=payload,
        text_sha256=_digest(payload),
    )


def _o4_contexts(module: ModuleType, selected: Any, *components: Any) -> tuple[Any, ...]:
    by_kind = {component.kind: component for component in components}
    return tuple(
        by_kind.get(kind)
        or _component(module, selected, kind=kind, status="missing")
        for kind in ("heading", "previous_unit", "next_unit")
    )


def _o5_contexts(module: ModuleType, selected: Any, *components: Any) -> tuple[Any, ...]:
    by_kind = {component.kind: component for component in components}
    return tuple(
        by_kind.get(kind)
        or _component(
            module,
            selected,
            kind=kind,
            status="missing",
            page=(
                max(1, selected.parent_locator[1] - 1)
                if kind == "previous_page_tail"
                else selected.parent_locator[1] + 1
            ),
        )
        for kind in ("previous_page_tail", "next_page_head")
    )


def test_default_bounds_match_frozen_scientific_lock() -> None:
    module = _assembly()
    lock = json.loads(
        (
            ROOT
            / "tests/fixtures/agent-context-unit-v2/scientific-input-lock.json"
        ).read_bytes()
    )

    assert module.DEFAULT_ASSEMBLY_BOUNDS == module.AssemblyBounds(
        max_primary_results=5,
        max_item_utf8_bytes=2_048,
        max_content_utf8_bytes=16_384,
        max_envelope_utf8_bytes=32_768,
        max_source_context_utf8_bytes=512,
        max_adjacent_utf8_bytes_each=256,
    )
    assert lock["projection_bounds"]["max_primary_results"] == 5
    assert lock["mechanism_profile"]["o2"]["max_item_utf8_bytes"] == 2_048
    assert (
        lock["mechanism_profile"]["o4"]["max_source_context_utf8_bytes"]
        == 512
    )
    assert lock["mechanism_profile"]["o5"]["max_adjacent_utf8_bytes_each"] == 256


def test_mechanism_ids_and_context_orders_match_frozen_scientific_lock() -> None:
    module = _assembly()
    lock = json.loads(
        (
            ROOT
            / "tests/fixtures/agent-context-unit-v2/scientific-input-lock.json"
        ).read_bytes()
    )["mechanism_profile"]
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)

    o2 = module.assemble_o2_delivery(selection, (selected,))
    o4 = module.assemble_o4_delivery(
        selection, (selected,), _o4_contexts(module, selected)
    )
    o5 = module.assemble_o5_delivery(
        selection, (selected,), _o5_contexts(module, selected)
    )

    assert {
        "o2": o2.mechanism_id,
        "o4": o4.mechanism_id,
        "o5": o5.mechanism_id,
    } == {
        name: lock["mechanism_ids"][name] for name in ("o2", "o4", "o5")
    }
    assert [record.kind for record in o4.items[0].components] == lock["o4"][
        "context_order"
    ]
    assert [record.kind for record in o5.items[0].components] == lock["o5"][
        "context_order"
    ]


@pytest.mark.parametrize("legacy_kind", ("previous_page", "next_page"))
def test_o5_rejects_legacy_component_aliases(legacy_kind: str) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    legacy_previous = replace(
        _component(
            module,
            selected,
            kind="previous_page_tail",
            status="missing",
            page=1,
        ),
        kind="previous_page",
    )
    legacy_next = replace(
        _component(
            module,
            selected,
            kind="next_page_head",
            status="missing",
            page=3,
        ),
        kind="next_page",
    )
    legacy = legacy_previous if legacy_kind == "previous_page" else legacy_next
    other = legacy_next if legacy_kind == "previous_page" else legacy_previous

    with pytest.raises(ValueError, match="context authority is invalid"):
        module.assemble_o5_delivery(
            selection,
            (selected,),
            (legacy, other),
        )


@pytest.mark.parametrize(
    "rank_profile_id",
    ("current-runtime-baseline-v1", "deterministic-unit-rank-v1"),
)
def test_o5_accepts_each_frozen_selection_profile(
    rank_profile_id: str,
) -> None:
    module = _assembly()
    selected = _selected(module, rank_profile_id=rank_profile_id)
    selection = _selection(module, selected.stable_context_unit_id)

    item = module.assemble_o5_delivery(
        selection, (selected,), _o5_contexts(module, selected)
    ).items[0]

    assert item.rank_profile_id == rank_profile_id
    assert item.stable_context_unit_id == selected.stable_context_unit_id


def test_o5_rejects_unfrozen_selection_profile() -> None:
    module = _assembly()
    selected = _selected(module, rank_profile_id="unfrozen-rank-profile")
    selection = _selection(module, selected.stable_context_unit_id)

    with pytest.raises(ValueError, match="delivery input authority is invalid"):
        module.assemble_o5_delivery(
            selection, (selected,), _o5_contexts(module, selected)
        )


@pytest.mark.parametrize("mechanism", ("o2", "o4"))
def test_o2_o4_reject_current_runtime_selection_profile(
    mechanism: str,
) -> None:
    module = _assembly()
    selected = _selected(
        module, rank_profile_id="current-runtime-baseline-v1"
    )
    selection = _selection(module, selected.stable_context_unit_id)

    with pytest.raises(ValueError, match="delivery input authority is invalid"):
        if mechanism == "o2":
            module.assemble_o2_delivery(selection, (selected,))
        else:
            module.assemble_o4_delivery(
                selection, (selected,), _o4_contexts(module, selected)
            )


@pytest.mark.parametrize(
    ("mechanism", "expected_substage"),
    (
        ("o2", "fixed_rank_delivery"),
        ("o4", "source_context_delivery"),
        ("o5", "adjacent_page_assembly"),
    ),
)
@pytest.mark.parametrize("malformed", (None, {}, object()))
def test_malformed_bounds_fail_through_typed_stage_boundary(
    mechanism: str,
    expected_substage: str,
    malformed: object,
) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    bounds: Any = malformed

    with pytest.raises(AgentContextStageError) as captured:
        if mechanism == "o2":
            module.assemble_o2_delivery(
                selection, (selected,), bounds=bounds
            )
        elif mechanism == "o4":
            module.assemble_o4_delivery(
                selection,
                (selected,),
                _o4_contexts(module, selected),
                bounds=bounds,
            )
        else:
            module.assemble_o5_delivery(
                selection,
                (selected,),
                _o5_contexts(module, selected),
                bounds=bounds,
            )

    error = captured.value
    assert error.substage.value == expected_substage
    assert error.error_code == "assembly_bounds_invalid"
    assert error.error_family == "integrity"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("max_primary_results", 6),
        ("max_item_utf8_bytes", 2_049),
        ("max_content_utf8_bytes", 16_385),
        ("max_envelope_utf8_bytes", 32_769),
        ("max_source_context_utf8_bytes", 513),
        ("max_adjacent_utf8_bytes_each", 257),
    ),
)
def test_bounds_cannot_exceed_frozen_scientific_ceiling(
    field: str, value: int
) -> None:
    module = _assembly()

    with pytest.raises(ValueError, match="assembly bounds are invalid"):
        module.AssemblyBounds(**{field: value})


@pytest.mark.parametrize("mechanism", ("o4", "o5"))
def test_context_inventory_requires_explicit_record_for_every_component(
    mechanism: str,
) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    assembler = (
        module.assemble_o4_delivery
        if mechanism == "o4"
        else module.assemble_o5_delivery
    )

    with pytest.raises(ValueError, match="context authority is incomplete"):
        assembler(selection, (selected,), ())


@pytest.mark.parametrize(
    ("mechanism", "expected_substage"),
    (
        ("o2", "fixed_rank_delivery"),
        ("o4", "source_context_delivery"),
        ("o5", "adjacent_page_assembly"),
    ),
)
def test_public_assemblers_raise_typed_stage_integrity_errors(
    mechanism: str, expected_substage: str
) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = replace(
        _selection(module, selected.stable_context_unit_id),
        selection_digest=_sha("9"),
    )
    def invoke() -> None:
        if mechanism == "o2":
            module.assemble_o2_delivery(selection, (selected,))
        elif mechanism == "o4":
            module.assemble_o4_delivery(
                selection, (selected,), _o4_contexts(module, selected)
            )
        else:
            module.assemble_o5_delivery(
                selection, (selected,), _o5_contexts(module, selected)
            )

    with pytest.raises(AgentContextStageError) as captured:
        invoke()

    error = captured.value
    assert error.substage.value == expected_substage
    assert error.error_code == "selection_authority_invalid"
    assert error.error_family == "integrity"


def test_public_assembler_raises_typed_stage_capacity_error() -> None:
    module = _assembly()
    selected = _selected(module, b"x" * 2_049)
    selection = _selection(module, selected.stable_context_unit_id)

    with pytest.raises(AgentContextStageError) as captured:
        module.assemble_o2_delivery(selection, (selected,))

    error = captured.value
    assert error.substage.value == "fixed_rank_delivery"
    assert error.error_code == "item_capacity_exceeded"
    assert error.error_family == "capacity"


@pytest.mark.parametrize(
    ("mechanism", "expected_substage"),
    (
        ("o4", "source_context_delivery"),
        ("o5", "adjacent_page_assembly"),
    ),
)
def test_context_inventory_shape_fails_through_typed_stage_boundary(
    mechanism: str, expected_substage: str
) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    malformed: Any = None

    with pytest.raises(AgentContextStageError) as captured:
        if mechanism == "o4":
            module.assemble_o4_delivery(selection, (selected,), malformed)
        else:
            module.assemble_o5_delivery(selection, (selected,), malformed)

    error = captured.value
    assert error.substage.value == expected_substage
    assert error.error_code == "context_authority_invalid"
    assert error.error_family == "integrity"


def test_o2_preserves_selection_order_digest_provenance_and_full_unit_bytes() -> None:
    module = _assembly()
    first = _selected(module, b"first")
    second = _selected(module, b"second")
    selection = _selection(
        module, first.stable_context_unit_id, second.stable_context_unit_id
    )

    result = module.assemble_o2_delivery(selection, (second, first))

    assert result.mechanism_id == "fixed-rank-delivery-v1"
    assert result.selection_digest == selection.selection_digest
    assert result.selected_stable_context_unit_ids == selection.stable_context_unit_ids
    assert [item.stable_context_unit_id for item in result.items] == [
        first.stable_context_unit_id,
        second.stable_context_unit_id,
    ]
    assert [item.delivered_text_bytes for item in result.items] == [
        b"first",
        b"second",
    ]
    assert result.items[0].origin_evidence_ref == first.origin_evidence_ref
    assert result.items[0].requested_utf8_bytes == 5
    assert result.items[0].returned_utf8_bytes == 5
    assert result.items[0].omitted_utf8_bytes == 0
    assert result.items[0].truncated_utf8_bytes == 0


@pytest.mark.parametrize("fault", ("duplicate", "missing", "digest", "order"))
def test_fixed_selection_rejects_identity_and_digest_tamper(fault: str) -> None:
    module = _assembly()
    first = _selected(module)
    second = _selected(module, fingerprint=_sha("5"))
    selection = _selection(
        module, first.stable_context_unit_id, second.stable_context_unit_id
    )
    inventory = (first, second)
    if fault == "duplicate":
        inventory = (first, first)
    elif fault == "missing":
        inventory = (first,)
    elif fault == "digest":
        selection = replace(selection, selection_digest=_sha("9"))
    else:
        selection = replace(
            selection,
            stable_context_unit_ids=tuple(
                reversed(selection.stable_context_unit_ids)
            ),
        )

    with pytest.raises(ValueError, match="selection authority is invalid"):
        module.assemble_o2_delivery(selection, inventory)


def test_delivery_input_rejects_stable_identity_not_bound_to_exact_unit() -> None:
    module = _assembly()
    selected = _selected(module)
    forged = replace(selected, stable_context_unit_id=_sha("9"))
    selection = _selection(module, forged.stable_context_unit_id)

    with pytest.raises(ValueError, match="delivery input authority is invalid"):
        module.assemble_o2_delivery(selection, (forged,))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("stable_context_unit_id", 7),
        ("source_content_fingerprint", None),
        ("publication_identity", "bad"),
        ("origin_evidence_ref", None),
        ("parent_locator", []),
        ("parent_locator", ()),
        ("parent_locator", ("page", 2)),
        ("parent_locator", ("page", 2, True)),
        ("active", 1),
        ("text_bytes", "text"),
        ("text_sha256", None),
    ),
)
def test_malformed_delivery_input_fails_closed_before_field_work(
    field: str,
    value: object,
) -> None:
    module = _assembly()
    selected = _selected(module)
    forged = replace(selected, **{field: value})
    selection = _selection(module, selected.stable_context_unit_id)

    with pytest.raises(
        ValueError, match="delivery input authority is invalid$"
    ):
        module.assemble_o2_delivery(selection, (forged,))


def test_o2_item_exact_boundary_passes_and_one_over_precedes_decode() -> None:
    module = _assembly()
    exact = _selected(module, b"x" * 2_048)
    exact_selection = _selection(module, exact.stable_context_unit_id)
    assert (
        module.assemble_o2_delivery(exact_selection, (exact,))
        .items[0]
        .returned_utf8_bytes
        == 2_048
    )

    over = _selected(module, b"x" * 2_048 + b"\xff")
    over_selection = _selection(module, over.stable_context_unit_id)
    with pytest.raises(ValueError, match="item capacity exceeded"):
        module.assemble_o2_delivery(over_selection, (over,))


def test_o2_global_content_one_over_fails_before_render() -> None:
    module = _assembly()
    first = _selected(module, b"1234")
    second = _selected(module, b"5678")
    selection = _selection(
        module, first.stable_context_unit_id, second.stable_context_unit_id
    )
    bounds = module.AssemblyBounds(max_content_utf8_bytes=7)

    with pytest.raises(ValueError, match="content capacity exceeded"):
        module.assemble_o2_delivery(selection, (first, second), bounds=bounds)


def test_o4_allocates_heading_previous_tail_next_head_in_frozen_order() -> None:
    module = _assembly()
    selected = _selected(module, b"unit", page=2)
    selection = _selection(module, selected.stable_context_unit_id)
    heading = _component(
        module, selected, kind="heading", text=b"HEADING", start=0
    )
    previous = _component(
        module,
        selected,
        kind="previous_unit",
        text=b"0123456789",
        start=90,
    )
    following = _component(
        module,
        selected,
        kind="next_unit",
        text=b"abcdefghij",
        start=104,
    )
    bounds = module.AssemblyBounds(
        max_item_utf8_bytes=48,
        max_source_context_utf8_bytes=44,
    )

    result = module.assemble_o4_delivery(
        selection,
        (selected,),
        _o4_contexts(module, selected, following, previous, heading),
        bounds=bounds,
    )
    item = result.items[0]

    assert [record.kind for record in item.components] == [
        "heading",
        "previous_unit",
        "next_unit",
    ]
    assert item.components[0].returned_text_bytes == b"HEADING"
    assert item.components[1].returned_text_bytes.endswith(b"789")
    assert item.components[2].returned_text_bytes.startswith(b"a")
    assert item.delivered_text_bytes.startswith(b"unit")
    assert sum(record.rendered_utf8_bytes for record in item.components) <= 44
    assert item.returned_utf8_bytes <= 48


def test_o4_unicode_cuts_are_safe_and_directional() -> None:
    module = _assembly()
    selected = _selected(module, "单元".encode(), page=2)
    selection = _selection(module, selected.stable_context_unit_id)
    previous = _component(
        module,
        selected,
        kind="previous_unit",
        text="甲乙丙丁".encode(),
        start=88,
    )
    following = _component(
        module,
        selected,
        kind="next_unit",
        text="戊己庚辛".encode(),
        start=106,
    )
    bounds = module.AssemblyBounds(
        max_item_utf8_bytes=47,
        max_source_context_utf8_bytes=41,
    )

    item = module.assemble_o4_delivery(
        selection,
        (selected,),
        _o4_contexts(module, selected, previous, following),
        bounds=bounds,
    ).items[0]

    records = {record.kind: record for record in item.components}
    previous_record = records["previous_unit"]
    next_record = records["next_unit"]
    previous_record.returned_text_bytes.decode("utf-8")
    next_record.returned_text_bytes.decode("utf-8")
    assert previous_record.returned_text_bytes.endswith("丁".encode())
    assert next_record.returned_text_bytes.startswith("戊".encode())
    assert previous_record.returned_origin_end_utf8_byte == 100
    assert next_record.returned_origin_start_utf8_byte == 106


def test_o4_separator_and_label_bytes_count_against_context_and_item_caps() -> None:
    module = _assembly()
    selected = _selected(module, b"u")
    selection = _selection(module, selected.stable_context_unit_id)
    heading = _component(module, selected, kind="heading", text=b"x")
    label_and_separator = len(b"\n[heading]\n")
    bounds = module.AssemblyBounds(
        max_item_utf8_bytes=1 + label_and_separator,
        max_source_context_utf8_bytes=label_and_separator,
    )

    record = module.assemble_o4_delivery(
        selection,
        (selected,),
        _o4_contexts(module, selected, heading),
        bounds=bounds,
    ).items[0].components[0]

    assert record.requested_utf8_bytes == 1
    assert record.returned_utf8_bytes == 0
    assert record.omitted_utf8_bytes == 1
    assert record.truncated_utf8_bytes == 1
    assert record.rendered_utf8_bytes == 0


def test_o4_item_accounting_includes_component_label_and_separator() -> None:
    module = _assembly()
    selected = _selected(module, b"u")
    selection = _selection(module, selected.stable_context_unit_id)
    heading = _component(module, selected, kind="heading", text=b"x")

    item = module.assemble_o4_delivery(
        selection,
        (selected,),
        _o4_contexts(module, selected, heading),
    ).items[0]

    assert item.requested_utf8_bytes == item.returned_utf8_bytes
    assert item.omitted_utf8_bytes == 0
    assert item.requested_utf8_bytes == len(b"u\n[heading]\nx")


def test_o4_context_input_capacity_precedes_component_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _assembly()
    selected = _selected(module, start=20_000)
    selection = _selection(module, selected.stable_context_unit_id)
    exact = _component(
        module,
        selected,
        kind="previous_unit",
        text=b"x" * 16_384,
        start=3_616,
    )
    module.assemble_o4_delivery(
        selection, (selected,), _o4_contexts(module, selected, exact)
    )
    over = replace(
        exact,
        origin_start_utf8_byte=3_615,
        text_bytes=b"x" * 16_385,
        text_sha256=_digest(b"x" * 16_385),
    )
    called = False
    original = module._validate_context_component

    def spy(
        component: Any, allowed_kinds: Any, allowed_statuses: Any
    ) -> None:
        nonlocal called
        called = True
        original(component, allowed_kinds, allowed_statuses)

    monkeypatch.setattr(module, "_validate_context_component", spy)
    with pytest.raises(ValueError, match="context input capacity exceeded"):
        module.assemble_o4_delivery(
            selection, (selected,), _o4_contexts(module, selected, over)
        )
    assert called is False


@pytest.mark.parametrize("status", ("missing", "ambiguous", "inactive"))
def test_o4_unavailable_context_is_explicit(status: str) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    component = _component(
        module, selected, kind="heading", status=status, text=b"ignored"
    )

    record = module.assemble_o4_delivery(
        selection, (selected,), _o4_contexts(module, selected, component)
    ).items[0].components[0]

    assert record.status == status
    assert record.returned_utf8_bytes == 0
    assert record.rendered_utf8_bytes == 0


@pytest.mark.parametrize("mechanism", ("o4", "o5"))
def test_nonempty_inactive_context_fails_before_allocation(
    mechanism: str,
) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    if mechanism == "o4":
        available = _component(
            module, selected, kind="heading", text=b"inactive payload"
        )
        inactive = replace(available, status="inactive")
        contexts = _o4_contexts(module, selected, inactive)
    else:
        available = _component(
            module,
            selected,
            kind="previous_page_tail",
            text=b"inactive payload",
            page=1,
        )
        inactive = replace(available, status="inactive")
        contexts = _o5_contexts(module, selected, inactive)

    with pytest.raises(ValueError, match="context authority is invalid"):
        if mechanism == "o4":
            module.assemble_o4_delivery(selection, (selected,), contexts)
        else:
            module.assemble_o5_delivery(selection, (selected,), contexts)


@pytest.mark.parametrize(
    ("kind", "allowed_kinds", "allowed_statuses"),
    (
        (
            "heading",
            ("heading", "previous_unit", "next_unit"),
            ("available", "missing", "ambiguous", "inactive"),
        ),
        (
            "previous_page_tail",
            ("previous_page_tail", "next_page_head"),
            (
                "available",
                "missing",
                "ambiguous",
                "inactive",
                "nonadjacent",
            ),
        ),
    ),
)
def test_context_validator_rejects_nonempty_inactive_payload(
    kind: str,
    allowed_kinds: tuple[str, ...],
    allowed_statuses: tuple[str, ...],
) -> None:
    module = _assembly()
    selected = _selected(module)
    available = _component(
        module,
        selected,
        kind=kind,
        text=b"inactive payload",
        page=1 if kind == "previous_page_tail" else None,
    )
    inactive = replace(available, status="inactive")

    with pytest.raises(ValueError, match="context authority is invalid"):
        module._validate_context_component(
            inactive, allowed_kinds, allowed_statuses
        )


@pytest.mark.parametrize("mechanism", ("o4", "o5"))
def test_explicit_inactive_context_has_zero_payload_and_accounting(
    mechanism: str,
) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    if mechanism == "o4":
        kind = "heading"
        inactive = _component(
            module, selected, kind=kind, status="inactive"
        )
        result = module.assemble_o4_delivery(
            selection,
            (selected,),
            _o4_contexts(module, selected, inactive),
        )
    else:
        kind = "previous_page_tail"
        inactive = _component(
            module,
            selected,
            kind=kind,
            status="inactive",
            page=1,
        )
        result = module.assemble_o5_delivery(
            selection,
            (selected,),
            _o5_contexts(module, selected, inactive),
        )
    record = next(
        record for record in result.items[0].components if record.kind == kind
    )

    assert record.status == "inactive"
    assert record.origin_start_utf8_byte == record.origin_end_utf8_byte
    assert (
        record.requested_utf8_bytes,
        record.returned_utf8_bytes,
        record.omitted_utf8_bytes,
        record.truncated_utf8_bytes,
        record.rendered_utf8_bytes,
    ) == (0, 0, 0, 0, 0)


def test_o4_rejects_o5_only_nonadjacent_status() -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    component = _component(
        module, selected, kind="heading", status="nonadjacent"
    )

    with pytest.raises(ValueError, match="context authority is invalid"):
        module.assemble_o4_delivery(
            selection,
            (selected,),
            _o4_contexts(module, selected, component),
        )


def test_o5_retains_explicit_nonadjacent_status() -> None:
    module = _assembly()
    selected = _selected(module, page=2)
    selection = _selection(module, selected.stable_context_unit_id)
    component = _component(
        module,
        selected,
        kind="next_page_head",
        status="nonadjacent",
        page=4,
    )

    item = module.assemble_o5_delivery(
        selection,
        (selected,),
        _o5_contexts(module, selected, component),
    ).items[0]
    record = next(
        record
        for record in item.components
        if record.kind == "next_page_head"
    )
    assert record.status == "nonadjacent"


@pytest.mark.parametrize("drift", ("source", "publication", "selected"))
def test_o4_rejects_context_authority_alias_drift_before_allocation(
    drift: str,
) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    component = _component(
        module,
        selected,
        kind="heading",
        fingerprint=_sha("8") if drift == "source" else None,
        publication=_sha("8") if drift == "publication" else None,
    )
    if drift == "selected":
        component = replace(
            component, selected_stable_context_unit_id=_sha("8")
        )

    with pytest.raises(ValueError, match="context provenance is invalid"):
        module.assemble_o4_delivery(
            selection,
            (selected,),
            _o4_contexts(module, selected, component),
        )


@pytest.mark.parametrize("kind", ("heading", "previous_unit", "next_unit"))
def test_o4_rejects_nonlocal_or_gapped_component_ranges(kind: str) -> None:
    module = _assembly()
    selected = _selected(module, b"unit")
    selection = _selection(module, selected.stable_context_unit_id)
    component = _component(
        module,
        selected,
        kind=kind,
        text=b"context",
        start=500,
    )

    with pytest.raises(ValueError, match="context provenance is invalid"):
        module.assemble_o4_delivery(
            selection,
            (selected,),
            _o4_contexts(module, selected, component),
        )


@pytest.mark.parametrize("duplicate", ("range", "bytes"))
def test_o4_rejects_duplicate_context_ranges_or_bytes(duplicate: str) -> None:
    module = _assembly()
    selected = _selected(module)
    selection = _selection(module, selected.stable_context_unit_id)
    first = _component(
        module, selected, kind="heading", text=b"same", start=0
    )
    second = _component(
        module,
        selected,
        kind="previous_unit",
        text=b"diff" if duplicate == "range" else b"same",
        start=0 if duplicate == "range" else 20,
    )

    with pytest.raises(ValueError, match="context duplication is invalid"):
        module.assemble_o4_delivery(
            selection,
            (selected,),
            _o4_contexts(module, selected, first, second),
        )


def test_o4_rejects_overlapping_context_origin_ranges() -> None:
    module = _assembly()
    selected = _selected(module, start=100)
    selection = _selection(module, selected.stable_context_unit_id)
    heading = _component(
        module, selected, kind="heading", text=b"h" * 60, start=40
    )
    previous = _component(
        module, selected, kind="previous_unit", text=b"p" * 50, start=50
    )

    with pytest.raises(ValueError, match="context duplication is invalid"):
        module.assemble_o4_delivery(
            selection,
            (selected,),
            _o4_contexts(module, selected, heading, previous),
        )


def test_o4_overlap_coordinates_are_local_to_origin_evidence() -> None:
    module = _assembly()
    selected = _selected(module, start=100)
    selection = _selection(module, selected.stable_context_unit_id)
    heading = _component(
        module,
        selected,
        kind="heading",
        text=b"h" * 60,
        start=40,
        evidence=_sha("8"),
    )
    previous = _component(
        module,
        selected,
        kind="previous_unit",
        text=b"p" * 50,
        start=50,
        evidence=_sha("9"),
    )

    result = module.assemble_o4_delivery(
        selection,
        (selected,),
        _o4_contexts(module, selected, heading, previous),
    )

    assert [record.origin_evidence_ref for record in result.items[0].components] == [
        _sha("8"),
        _sha("9"),
        selected.origin_evidence_ref,
    ]


def test_o4_preserves_unit_bytes_and_context_origin_ranges() -> None:
    module = _assembly()
    selected = _selected(module, b"unit")
    selection = _selection(module, selected.stable_context_unit_id)
    context = _component(
        module,
        selected,
        kind="next_unit",
        text=b"context-only-token",
        start=104,
        evidence=_sha("8"),
    )

    item = module.assemble_o4_delivery(
        selection, (selected,), _o4_contexts(module, selected, context)
    ).items[0]

    assert item.unit_text_bytes == b"unit"
    next_record = next(
        record for record in item.components if record.kind == "next_unit"
    )
    assert next_record.origin_evidence_ref == _sha("8")
    assert next_record.origin_start_utf8_byte == 104
    assert next_record.origin_end_utf8_byte == 122
    assert next_record.returned_text_bytes == b"context-only-token"


def test_o5_preserves_excerpt_then_allocates_previous_tail_before_next_head() -> None:
    module = _assembly()
    selected = _selected(module, b"excerpt", page=2)
    selection = _selection(module, selected.stable_context_unit_id)
    previous = _component(
        module,
        selected,
        kind="previous_page_tail",
        text=b"0123456789",
        page=1,
        start=0,
    )
    following = _component(
        module,
        selected,
        kind="next_page_head",
        text=b"abcdefghij",
        page=3,
        start=0,
    )
    bounds = module.AssemblyBounds(max_item_utf8_bytes=43)

    item = module.assemble_o5_delivery(
        selection,
        (selected,),
        _o5_contexts(module, selected, following, previous),
        bounds=bounds,
    ).items[0]

    assert item.excerpt_text_bytes == b"excerpt"
    assert [record.kind for record in item.components] == [
        "previous_page_tail",
        "next_page_head",
    ]
    assert item.components[0].returned_text_bytes.endswith(b"789")
    assert item.components[1].returned_text_bytes.startswith(b"a")
    assert item.returned_utf8_bytes <= 43


def test_o5_reduces_overlong_excerpt_with_utf8_safe_prefix() -> None:
    module = _assembly()
    selected = _selected(module, "甲乙丙".encode())
    selection = _selection(module, selected.stable_context_unit_id)
    bounds = module.AssemblyBounds(max_item_utf8_bytes=7)

    item = module.assemble_o5_delivery(
        selection,
        (selected,),
        _o5_contexts(module, selected),
        bounds=bounds,
    ).items[0]

    assert item.excerpt_text_bytes == "甲乙".encode()
    assert item.requested_utf8_bytes == 9
    assert item.returned_utf8_bytes == 6
    assert item.omitted_utf8_bytes == 3
    assert item.truncated_utf8_bytes == 3


def test_o5_selected_input_capacity_precedes_delivery_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _assembly()
    exact = _selected(module, b"x" * 16_384)
    exact_selection = _selection(module, exact.stable_context_unit_id)
    module.assemble_o5_delivery(
        exact_selection, (exact,), _o5_contexts(module, exact)
    )
    over = _selected(module, b"x" * 16_385)
    over_selection = _selection(module, over.stable_context_unit_id)
    called = False
    original = module._validate_delivery_input

    def spy(
        item: Any,
        *,
        allowed_rank_profile_ids: tuple[str, ...],
        require_active: bool = True,
    ) -> None:
        nonlocal called
        called = True
        original(
            item,
            allowed_rank_profile_ids=allowed_rank_profile_ids,
            require_active=require_active,
        )

    monkeypatch.setattr(module, "_validate_delivery_input", spy)
    with pytest.raises(ValueError, match="item input capacity exceeded"):
        module.assemble_o5_delivery(
            over_selection, (over,), _o5_contexts(module, over)
        )
    assert called is False


def test_o5_item_accounting_includes_component_label_and_separator() -> None:
    module = _assembly()
    selected = _selected(module, b"e", page=2)
    selection = _selection(module, selected.stable_context_unit_id)
    previous = _component(
        module, selected, kind="previous_page_tail", text=b"p", page=1
    )

    item = module.assemble_o5_delivery(
        selection,
        (selected,),
        _o5_contexts(module, selected, previous),
    ).items[0]

    assert item.requested_utf8_bytes == item.returned_utf8_bytes
    assert item.omitted_utf8_bytes == 0
    assert item.requested_utf8_bytes == len(b"e\n[p]\np")


def test_o5_each_adjacent_payload_is_capped_at_256_utf8_bytes() -> None:
    module = _assembly()
    selected = _selected(module, b"x", page=2)
    selection = _selection(module, selected.stable_context_unit_id)
    previous = _component(
        module,
        selected,
        kind="previous_page_tail",
        text=b"p" * 300,
        page=1,
    )
    following = _component(
        module,
        selected,
        kind="next_page_head",
        text=b"n" * 300,
        page=3,
    )

    records = module.assemble_o5_delivery(
        selection,
        (selected,),
        _o5_contexts(module, selected, previous, following),
    ).items[0].components

    assert records[0].returned_utf8_bytes == 256
    assert records[0].returned_text_bytes == b"p" * 256
    assert records[1].returned_utf8_bytes == 256
    assert records[1].returned_text_bytes == b"n" * 256


@pytest.mark.parametrize(
    ("kind", "status", "page"),
    (
        ("previous_page_tail", "missing", 1),
        ("previous_page_tail", "inactive", 1),
        ("next_page_head", "ambiguous", 3),
        ("next_page_head", "nonadjacent", 4),
    ),
)
def test_o5_unavailable_or_nonadjacent_context_is_explicit(
    kind: str,
    status: str,
    page: int,
) -> None:
    module = _assembly()
    selected = _selected(module, page=2)
    selection = _selection(module, selected.stable_context_unit_id)
    context = _component(
        module,
        selected,
        kind=kind,
        status=status,
        page=page,
    )

    records = module.assemble_o5_delivery(
        selection, (selected,), _o5_contexts(module, selected, context)
    ).items[0].components
    record = next(record for record in records if record.kind == kind)

    assert record.status == status
    assert record.returned_utf8_bytes == 0


@pytest.mark.parametrize("drift", ("source", "publication", "wrong_page"))
def test_o5_rejects_cross_authority_or_nonadjacent_available_page(
    drift: str,
) -> None:
    module = _assembly()
    selected = _selected(module, page=2)
    selection = _selection(module, selected.stable_context_unit_id)
    context = _component(
        module,
        selected,
        kind="previous_page_tail",
        page=4 if drift == "wrong_page" else 1,
        fingerprint=_sha("8") if drift == "source" else None,
        publication=_sha("8") if drift == "publication" else None,
    )

    with pytest.raises(ValueError, match="context provenance is invalid"):
        module.assemble_o5_delivery(
            selection,
            (selected,),
            _o5_contexts(module, selected, context),
        )


def test_o5_no_context_record_is_bound_to_attempted_adjacent_page() -> None:
    module = _assembly()
    selected = _selected(module, page=2)
    selection = _selection(module, selected.stable_context_unit_id)
    forged = _component(
        module,
        selected,
        kind="next_page_head",
        status="missing",
        page=999,
    )

    with pytest.raises(ValueError, match="context provenance is invalid"):
        module.assemble_o5_delivery(
            selection,
            (selected,),
            _o5_contexts(module, selected, forged),
        )


def test_portable_bytes_are_canonical_and_ignore_runtime_handles() -> None:
    module = _assembly()
    workspace_a = _selected(module, runtime_handle="evidence-workspace-a")
    workspace_b = _selected(module, runtime_handle="evidence-workspace-b")
    selection = _selection(module, workspace_a.stable_context_unit_id)

    first = module.assemble_o2_delivery(selection, (workspace_a,))
    second = module.assemble_o2_delivery(selection, (workspace_b,))

    assert first.portable_bytes() == second.portable_bytes()
    assert first.portable_bytes().endswith(b"\n")
    assert json.dumps(
        json.loads(first.portable_bytes()),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode() + b"\n" == first.portable_bytes()
    assert b"workspace-a" not in first.portable_bytes()
    assert b"workspace-b" not in first.portable_bytes()


def test_envelope_capacity_rejects_canonical_bytes_one_over() -> None:
    module = _assembly()
    selected = _selected(module, b"x")
    selection = _selection(module, selected.stable_context_unit_id)
    exact = module.AssemblyBounds(max_envelope_utf8_bytes=1_097)
    one_under = module.AssemblyBounds(max_envelope_utf8_bytes=1_096)

    assert (
        len(
            module.assemble_o2_delivery(
                selection, (selected,), bounds=exact
            ).portable_bytes()
        )
        == 1_097
    )
    with pytest.raises(ValueError, match="envelope capacity exceeded"):
        module.assemble_o2_delivery(
            selection, (selected,), bounds=one_under
        )


def test_assembly_contract_has_no_label_filename_ranking_or_runtime_imports() -> None:
    module = _assembly()
    source = inspect.getsource(module)
    forbidden_tokens = {
        "qrel",
        "filename",
        "display_name",
        "agent_context_unit_grading",
        "agent_context_unit_workflow",
        "mke.application",
        "mke.adapters",
        "mke.retrieval",
    }

    assert all(token not in source for token in forbidden_tokens)
    public_fields = {
        field.name for field in dataclasses.fields(module.DeliveryAssemblyResult)
    }
    assert public_fields.isdisjoint(
        {"label", "qrel", "filename", "display_name", "verdict"}
    )
