"""Development-label authority opened only after the O0 observation seal."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, cast

from mke.evaluation.agent_context_unit_protocol import (
    AgentContextProtocolAuthority,
    load_agent_context_unit_protocol_authority,
    validate_agent_context_unit_file_read,
)
from mke.evaluation.source_identity import read_no_follow_regular_file

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SPAN_FIELDS = {
    "byte_range",
    "control",
    "hypothesis",
    "locator",
    "query_id",
    "role",
    "source_content_fingerprint",
    "span_id",
    "text_sha256",
}
_RESIDUAL_GATE_FIELDS = {
    "control_only",
    "controls_must_pass",
    "o3_enabled_when",
    "o4_enabled_when",
    "o5_enabled_when",
}
_MECHANISM_VERDICT_FIELDS = {"delivery", "rank", "status_inventory"}
_MECHANISM_IDS = {"o0", "o1", "o2", "o3", "o4", "o5"}
_RESIDUAL_GATE_RULES_SHA256 = (
    "fb5e857daf667f7ca6905e1577f4e7241f759af0130997fb50733d02b2b35b07"
)
_MECHANISM_VERDICT_RULES_SHA256 = (
    "b88d88a38351eff93fe6720cb7277b262f23d04eb72ff531123bf89837d328ab"
)
_CONTROL_QUERY_KINDS = {
    "q-current-success": "current_success",
    "q-exact-read-control": "exact_read",
    "q-hard-negative": "hard_negative",
    "q-misleading-name": "misleading_source_name",
    "q-tokenization-control": "tokenization_query_policy",
}
_PORTABLE_GRADING_AUTHORITY_FIELDS = {
    "control_query_kinds",
    "expected_routes_by_query",
    "mechanism_ids",
    "mechanism_verdict_revision",
    "mechanism_verdict_rules",
    "observation_ids_by_query",
    "query_ids",
    "query_terms_by_query",
    "query_text_by_query",
    "rank_profiles_by_mechanism",
    "required_spans",
    "residual_gate_rules",
    "schema_version",
    "scientific_nonclaims",
    "stage_verdict_revision",
}


@dataclass(frozen=True)
class AgentContextRequiredSpan:
    span_id: str
    query_id: str
    source_content_fingerprint: str
    locator_kind: str
    locator_start: int
    locator_end: int
    start_utf8_byte: int
    end_utf8_byte: int
    text_sha256: str
    role: str
    hypothesis: str
    control: str

    def __post_init__(self) -> None:
        if (
            not all(
                (
                    self.span_id,
                    self.query_id,
                    self.role,
                    self.hypothesis,
                    self.control,
                )
            )
            or not self.source_content_fingerprint.startswith("sha256:")
            or _SHA256.fullmatch(self.source_content_fingerprint.removeprefix("sha256:")) is None
            or _SHA256.fullmatch(self.text_sha256) is None
            or self.start_utf8_byte < 0
            or self.end_utf8_byte <= self.start_utf8_byte
        ):
            raise ValueError("required span is invalid")


@dataclass(frozen=True)
class AgentContextBaselineGradingPayload:
    required_spans: tuple[AgentContextRequiredSpan, ...]

    def __post_init__(self) -> None:
        identities = tuple(item.span_id for item in self.required_spans)
        if not identities or len(set(identities)) != len(identities):
            raise ValueError("grading span inventory is invalid")


@dataclass(frozen=True)
class AgentContextDevelopmentGradingPayload:
    required_spans: tuple[AgentContextRequiredSpan, ...]
    query_ids: tuple[str, ...]
    observation_ids_by_query: Mapping[str, tuple[str, ...]]
    expected_routes_by_query: Mapping[str, str]
    query_text_by_query: Mapping[str, str]
    query_terms_by_query: Mapping[str, tuple[str, ...]]
    control_query_kinds: Mapping[str, str]
    mechanism_ids: Mapping[str, str]
    rank_profiles_by_mechanism: Mapping[str, tuple[str, ...]]
    residual_gate_rules: Mapping[str, Any]
    mechanism_verdict_rules: Mapping[str, Any]
    mechanism_verdict_revision: str
    stage_verdict_revision: str
    scientific_nonclaims: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_ids_by_query",
            MappingProxyType(dict(self.observation_ids_by_query)),
        )
        object.__setattr__(
            self,
            "expected_routes_by_query",
            MappingProxyType(dict(self.expected_routes_by_query)),
        )
        object.__setattr__(
            self,
            "query_text_by_query",
            MappingProxyType(dict(self.query_text_by_query)),
        )
        object.__setattr__(
            self,
            "query_terms_by_query",
            MappingProxyType(dict(self.query_terms_by_query)),
        )
        object.__setattr__(
            self,
            "control_query_kinds",
            MappingProxyType(dict(self.control_query_kinds)),
        )
        object.__setattr__(self, "mechanism_ids", MappingProxyType(dict(self.mechanism_ids)))
        object.__setattr__(
            self,
            "rank_profiles_by_mechanism",
            MappingProxyType(dict(self.rank_profiles_by_mechanism)),
        )
        object.__setattr__(
            self,
            "residual_gate_rules",
            _deep_freeze(dict(self.residual_gate_rules)),
        )
        object.__setattr__(
            self,
            "mechanism_verdict_rules",
            _deep_freeze(dict(self.mechanism_verdict_rules)),
        )
        span_queries = {span.query_id for span in self.required_spans}
        if (
            not self.required_spans
            or not self.query_ids
            or not span_queries <= set(self.query_ids)
            or set(self.observation_ids_by_query) != set(self.query_ids)
            or set(self.expected_routes_by_query) != set(self.query_ids)
            or set(self.query_text_by_query) != set(self.query_ids)
            or set(self.query_terms_by_query) != set(self.query_ids)
            or any(
                not text
                or self.query_terms_by_query[query_id]
                != tuple(text.casefold().split())
                for query_id, text in self.query_text_by_query.items()
            )
            or not set(self.control_query_kinds) <= set(self.query_ids)
            or not set(self.control_query_kinds.values()) <= set(_CONTROL_QUERY_KINDS.values())
            or set(self.mechanism_ids) != _MECHANISM_IDS
            or set(self.rank_profiles_by_mechanism) != set(self.mechanism_ids.values())
            or any(not profiles for profiles in self.rank_profiles_by_mechanism.values())
            or set(self.residual_gate_rules) != _RESIDUAL_GATE_FIELDS
            or set(self.mechanism_verdict_rules) != _MECHANISM_VERDICT_FIELDS
            or _canonical_sha256(_deep_thaw(self.residual_gate_rules))
            != _RESIDUAL_GATE_RULES_SHA256
            or _canonical_sha256(_deep_thaw(self.mechanism_verdict_rules))
            != _MECHANISM_VERDICT_RULES_SHA256
            or _prefixed_sha256(self.mechanism_verdict_revision) is None
            or _prefixed_sha256(self.stage_verdict_revision) is None
            or not self.scientific_nonclaims
        ):
            raise ValueError("development grading rules are invalid")


def load_agent_context_unit_baseline_grading_payload(
    protocol_authority: Path | AgentContextProtocolAuthority,
) -> AgentContextBaselineGradingPayload:
    if isinstance(protocol_authority, Path) and protocol_authority.name != "protocol.json":
        raise ValueError("baseline grading authority must be development protocol")
    authority = (
        protocol_authority
        if isinstance(protocol_authority, AgentContextProtocolAuthority)
        else load_agent_context_unit_protocol_authority(protocol_authority)
    )
    if PurePosixPath(cast(str, authority.protocol_read.identity["path"])).name != "protocol.json":
        raise ValueError("baseline grading authority must be development protocol")
    labels = authority.metadata.partitions["development"].labels
    relative = labels.path
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or "development" not in pure.parts
        or "holdout" in pure.parts
    ):
        raise ValueError("development grading authority is invalid")
    labels_read = read_no_follow_regular_file(authority.repository_root, relative)
    validate_agent_context_unit_file_read(
        labels,
        labels_read,
        name="development grading",
    )
    payload_value: object = json.loads(labels_read.content)
    if not isinstance(payload_value, dict):
        raise ValueError("development grading payload is invalid")
    payload = cast(dict[str, object], payload_value)
    if set(payload) != {"required_spans", "schema_version"}:
        raise ValueError("development grading payload is invalid")
    if payload["schema_version"] != "mke.agent_context_unit_labels.v2" or not isinstance(
        payload["required_spans"], list
    ):
        raise ValueError("development grading payload is invalid")
    required_spans = cast(list[object], payload["required_spans"])
    if _canonical_sha256(required_spans) != authority.development_span_projection_sha256:
        raise ValueError("development grading scientific projection is invalid")
    spans: list[AgentContextRequiredSpan] = []
    for value in required_spans:
        if not isinstance(value, dict):
            raise ValueError("development grading payload is invalid")
        item = cast(dict[str, object], value)
        if set(item) != _SPAN_FIELDS:
            raise ValueError("development grading payload is invalid")
        locator = item["locator"]
        byte_range = item["byte_range"]
        if not isinstance(locator, dict) or not isinstance(byte_range, dict):
            raise ValueError("development grading payload is invalid")
        locator = cast(dict[str, object], locator)
        byte_range = cast(dict[str, object], byte_range)
        if set(locator) != {"end", "kind", "start"} or set(byte_range) != {
            "end",
            "start",
        }:
            raise ValueError("development grading payload is invalid")
        spans.append(
            AgentContextRequiredSpan(
                span_id=_string(item["span_id"]),
                query_id=_string(item["query_id"]),
                source_content_fingerprint=_string(item["source_content_fingerprint"]),
                locator_kind=_string(locator["kind"]),
                locator_start=_integer(locator["start"]),
                locator_end=_integer(locator["end"]),
                start_utf8_byte=_integer(byte_range["start"]),
                end_utf8_byte=_integer(byte_range["end"]),
                text_sha256=_string(item["text_sha256"]),
                role=_string(item["role"]),
                hypothesis=_string(item["hypothesis"]),
                control=_string(item["control"]),
            )
        )
    return AgentContextBaselineGradingPayload(tuple(spans))


def load_agent_context_unit_development_grading_payload(
    protocol_authority: Path | AgentContextProtocolAuthority,
) -> AgentContextDevelopmentGradingPayload:
    authority = (
        protocol_authority
        if isinstance(protocol_authority, AgentContextProtocolAuthority)
        else load_agent_context_unit_protocol_authority(protocol_authority)
    )
    baseline = load_agent_context_unit_baseline_grading_payload(authority)
    value: object = json.loads(authority.scientific_lock_read.content)
    if not isinstance(value, dict):
        raise ValueError("development grading rules are invalid")
    lock = cast(dict[str, object], value)
    required = {
        "mechanism_profile",
        "mechanism_verdict_revision",
        "mechanism_verdict_rules",
        "partitions",
        "residual_gate_rules",
        "scientific_nonclaims",
        "stage_verdict_revision",
    }
    if not required <= set(lock):
        raise ValueError("development grading rules are invalid")
    mechanism_profile = lock["mechanism_profile"]
    partitions = lock["partitions"]
    residual_gate_rules = lock["residual_gate_rules"]
    verdict_rules = lock["mechanism_verdict_rules"]
    nonclaims = lock["scientific_nonclaims"]
    residual_mapping = (
        cast(dict[object, object], residual_gate_rules)
        if isinstance(residual_gate_rules, dict)
        else {}
    )
    verdict_mapping = (
        cast(dict[object, object], verdict_rules) if isinstance(verdict_rules, dict) else {}
    )
    if (
        not isinstance(mechanism_profile, dict)
        or not isinstance(partitions, dict)
        or not isinstance(residual_gate_rules, dict)
        or set(residual_mapping) != _RESIDUAL_GATE_FIELDS
        or not isinstance(verdict_rules, dict)
        or set(verdict_mapping) != _MECHANISM_VERDICT_FIELDS
        or not isinstance(nonclaims, list)
    ):
        raise ValueError("development grading rules are invalid")
    profile = cast(dict[str, object], mechanism_profile)
    mechanism_ids = profile.get("mechanism_ids")
    development = cast(dict[str, object], partitions).get("development")
    mechanism_mapping = (
        cast(dict[object, object], mechanism_ids) if isinstance(mechanism_ids, dict) else {}
    )
    if (
        not isinstance(mechanism_ids, dict)
        or set(mechanism_mapping) != _MECHANISM_IDS
        or not isinstance(development, dict)
    ):
        raise ValueError("development grading rules are invalid")
    development_record = cast(dict[str, object], development)
    query_ids = development_record.get("query_ids")
    cases = development_record.get("observer_cases")
    if not isinstance(query_ids, list) or not isinstance(cases, list):
        raise ValueError("development grading rules are invalid")
    query_items = cast(list[object], query_ids)
    case_items = cast(list[object], cases)
    observation_ids_by_query: dict[str, tuple[str, ...]] = {}
    expected_routes_by_query: dict[str, str] = {}
    query_text_by_query: dict[str, str] = {}
    query_terms_by_query: dict[str, tuple[str, ...]] = {}
    for case in case_items:
        if not isinstance(case, dict):
            raise ValueError("development grading rules are invalid")
        record = cast(dict[str, object], case)
        query_id = record.get("query_id")
        observation_ids = record.get("observation_ids")
        expected_route = record.get("runtime_route_profile")
        query_text = record.get("query_text")
        observation_items = (
            cast(list[object], observation_ids) if isinstance(observation_ids, list) else []
        )
        if (
            not isinstance(query_id, str)
            or not query_id
            or not isinstance(observation_ids, list)
            or not observation_ids
            or not isinstance(expected_route, str)
            or expected_route not in {"fts5", "cjk-active-scan-overlap-v1"}
            or not isinstance(query_text, str)
            or not query_text
            or any(not isinstance(item, str) or not item for item in observation_items)
            or query_id in observation_ids_by_query
        ):
            raise ValueError("development grading rules are invalid")
        observation_ids_by_query[query_id] = tuple(cast(str, item) for item in observation_items)
        expected_routes_by_query[query_id] = expected_route
        query_text_by_query[query_id] = query_text
        query_terms_by_query[query_id] = tuple(query_text.casefold().split())
    mechanism_values = {
        _string(key): _string(item) for key, item in mechanism_mapping.items()
    }
    o3_profile = cast(dict[str, object], profile.get("o3"))
    variants = cast(list[object], o3_profile.get("variants"))
    pattern = _string(o3_profile.get("rank_profile_id_pattern"))
    o1_profile = cast(dict[str, object], profile.get("o1"))
    o1_rank_profile = _string(o1_profile.get("rank_profile_id"))
    rank_profiles_by_mechanism = {
        mechanism_values["o0"]: (mechanism_values["o0"],),
        mechanism_values["o1"]: (o1_rank_profile,),
        mechanism_values["o2"]: (o1_rank_profile,),
        mechanism_values["o3"]: tuple(
            pattern.format(variant=_string(variant)) for variant in variants
        ),
        mechanism_values["o4"]: (o1_rank_profile,),
        mechanism_values["o5"]: (mechanism_values["o0"], o1_rank_profile),
    }
    return AgentContextDevelopmentGradingPayload(
        required_spans=baseline.required_spans,
        query_ids=tuple(_string(item) for item in query_items),
        observation_ids_by_query=observation_ids_by_query,
        expected_routes_by_query=expected_routes_by_query,
        query_text_by_query=query_text_by_query,
        query_terms_by_query=query_terms_by_query,
        control_query_kinds={
            query_id: kind
            for query_id, kind in _CONTROL_QUERY_KINDS.items()
            if query_id in observation_ids_by_query
        },
        mechanism_ids=mechanism_values,
        rank_profiles_by_mechanism=rank_profiles_by_mechanism,
        residual_gate_rules=cast(dict[str, Any], residual_gate_rules.copy()),
        mechanism_verdict_rules=cast(dict[str, Any], verdict_rules.copy()),
        mechanism_verdict_revision=_string(lock["mechanism_verdict_revision"]),
        stage_verdict_revision=_string(lock["stage_verdict_revision"]),
        scientific_nonclaims=tuple(_string(item) for item in cast(list[object], nonclaims)),
    )


def portable_agent_context_unit_development_grading_payload(
    payload: AgentContextDevelopmentGradingPayload,
) -> dict[str, object]:
    if type(payload) is not AgentContextDevelopmentGradingPayload:
        raise ValueError("development grading rules are invalid")
    return {
        "control_query_kinds": dict(payload.control_query_kinds),
        "expected_routes_by_query": dict(payload.expected_routes_by_query),
        "mechanism_ids": dict(payload.mechanism_ids),
        "mechanism_verdict_revision": payload.mechanism_verdict_revision,
        "mechanism_verdict_rules": _deep_thaw(payload.mechanism_verdict_rules),
        "observation_ids_by_query": {
            key: list(value) for key, value in payload.observation_ids_by_query.items()
        },
        "query_ids": list(payload.query_ids),
        "query_terms_by_query": {
            key: list(value) for key, value in payload.query_terms_by_query.items()
        },
        "query_text_by_query": dict(payload.query_text_by_query),
        "rank_profiles_by_mechanism": {
            key: list(value) for key, value in payload.rank_profiles_by_mechanism.items()
        },
        "required_spans": [asdict(item) for item in payload.required_spans],
        "residual_gate_rules": _deep_thaw(payload.residual_gate_rules),
        "schema_version": "mke.agent_context_unit_grading_authority.v1",
        "scientific_nonclaims": list(payload.scientific_nonclaims),
        "stage_verdict_revision": payload.stage_verdict_revision,
    }


def parse_agent_context_unit_development_grading_payload(
    value: object,
) -> AgentContextDevelopmentGradingPayload:
    if not isinstance(value, dict):
        raise ValueError("development grading rules are invalid")
    record = cast(dict[object, object], value)
    if (
        set(record) != _PORTABLE_GRADING_AUTHORITY_FIELDS
        or record["schema_version"] != "mke.agent_context_unit_grading_authority.v1"
    ):
        raise ValueError("development grading rules are invalid")
    try:
        spans_value = _object_list(record["required_spans"])
        spans = tuple(_parse_portable_required_span(item) for item in spans_value)
        return AgentContextDevelopmentGradingPayload(
            required_spans=spans,
            query_ids=tuple(_string(item) for item in _object_list(record["query_ids"])),
            observation_ids_by_query=_string_tuple_mapping(
                record["observation_ids_by_query"]
            ),
            expected_routes_by_query=_string_mapping(
                record["expected_routes_by_query"]
            ),
            query_text_by_query=_string_mapping(record["query_text_by_query"]),
            query_terms_by_query=_string_tuple_mapping(record["query_terms_by_query"]),
            control_query_kinds=_string_mapping(record["control_query_kinds"]),
            mechanism_ids=_string_mapping(record["mechanism_ids"]),
            rank_profiles_by_mechanism=_string_tuple_mapping(
                record["rank_profiles_by_mechanism"]
            ),
            residual_gate_rules=_string_object_mapping(record["residual_gate_rules"]),
            mechanism_verdict_rules=_string_object_mapping(
                record["mechanism_verdict_rules"]
            ),
            mechanism_verdict_revision=_string(record["mechanism_verdict_revision"]),
            stage_verdict_revision=_string(record["stage_verdict_revision"]),
            scientific_nonclaims=tuple(
                _string(item) for item in _object_list(record["scientific_nonclaims"])
            ),
        )
    except (TypeError, ValueError) as error:
        raise ValueError("development grading rules are invalid") from error


def _parse_portable_required_span(value: object) -> AgentContextRequiredSpan:
    record = _string_object_mapping(value)
    expected = {
        "control",
        "end_utf8_byte",
        "hypothesis",
        "locator_end",
        "locator_kind",
        "locator_start",
        "query_id",
        "role",
        "source_content_fingerprint",
        "span_id",
        "start_utf8_byte",
        "text_sha256",
    }
    if set(record) != expected:
        raise ValueError("development grading rules are invalid")
    return AgentContextRequiredSpan(
        span_id=_string(record["span_id"]),
        query_id=_string(record["query_id"]),
        source_content_fingerprint=_string(record["source_content_fingerprint"]),
        locator_kind=_string(record["locator_kind"]),
        locator_start=_integer(record["locator_start"]),
        locator_end=_integer(record["locator_end"]),
        start_utf8_byte=_integer(record["start_utf8_byte"]),
        end_utf8_byte=_integer(record["end_utf8_byte"]),
        text_sha256=_string(record["text_sha256"]),
        role=_string(record["role"]),
        hypothesis=_string(record["hypothesis"]),
        control=_string(record["control"]),
    )


def _object_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("development grading rules are invalid")
    return cast(list[object], value)


def _string_object_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("development grading rules are invalid")
    return {
        _string(key): item for key, item in cast(dict[object, object], value).items()
    }


def _string_mapping(value: object) -> dict[str, str]:
    return {
        key: _string(item) for key, item in _string_object_mapping(value).items()
    }


def _string_tuple_mapping(value: object) -> dict[str, tuple[str, ...]]:
    return {
        key: tuple(_string(item) for item in _object_list(items))
        for key, items in _string_object_mapping(value).items()
    }


def _string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("development grading payload is invalid")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("development grading payload is invalid")
    return value


def _canonical_sha256(value: object) -> str:
    from hashlib import sha256

    return sha256(
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _deep_freeze(value: object) -> object:
    if isinstance(value, dict):
        items = cast(dict[object, object], value)
        return MappingProxyType(
            {
                _string(key): _deep_freeze(item)
                for key, item in items.items()
            }
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in cast(list[object] | tuple[object, ...], value))
    return value


def _deep_thaw(value: object) -> object:
    if isinstance(value, Mapping):
        items = cast(Mapping[object, object], value)
        return {_string(key): _deep_thaw(item) for key, item in items.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in cast(tuple[object, ...], value)]
    return value


def _prefixed_sha256(value: object) -> str | None:
    if (
        isinstance(value, str)
        and value.startswith("sha256:")
        and _SHA256.fullmatch(value.removeprefix("sha256:")) is not None
    ):
        return value
    return None
