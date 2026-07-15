"""Disposable product-path runner for the PDF OCR Phase 0 scorecard."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from mke.application import KnowledgeEngine
from mke.domain import CandidateEvidence, RunManifest
from mke.evaluation.pdf_ocr_protocol import PdfOcrEvaluationProtocol
from mke.evaluation.pdf_ocr_provider import normalize_ocr_text
from mke.evaluation.pdf_ocr_router import EVALUATION_POLICY, PdfInspectionResult, inspect_pdf
from mke.interfaces.mcp_contract import McpRuntimeConfig, ask_library_v1, search_library_v1
from mke.interfaces.mcp_schemas import AskLibrarySuccessV1, SearchLibrarySuccessV1
from mke.runtime import RuntimeConfig

_SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
_PROVIDERS = (
    "apple-vision-local-v1",
    "paddleocr-vl-1.6-cpu-spike-v1",
    "ppocrv6-medium-cpu-spike-v1",
)
_IDENTITY_KEYS = {
    "schema",
    "protocol",
    "fixtures",
    "router",
    "render",
    "provider",
    "model",
    "package",
    "normalization",
}
_POLICY_KEYS = {
    "accepted_text_min_chars",
    "accepted_text_max_replacement_ratio",
    "ocr_text_max_chars",
    "ocr_min_image_coverage",
    "render_dpi",
    "max_pages",
    "max_page_pixels",
    "max_total_rendered_pixels",
    "max_rendered_file_bytes",
    "max_total_rendered_bytes",
}
_PRIVATE_RE = re.compile(
    r"(?:/Users/|[A-Za-z]:\\|Traceback|API[_-]?KEY|TOKEN=|SECRET=|PASSWORD=|hostname|timestamp)",
    re.IGNORECASE,
)


class ExtractorIdentityError(ValueError):
    """The closed evaluation extractor identity is invalid."""


@dataclass(frozen=True)
class ExactRate:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or self.numerator < 0:
            raise ValueError("rate numerator must be a non-negative integer")
        if type(self.denominator) is not int or self.denominator <= 0:
            raise ValueError("rate denominator must be a positive integer")

    @property
    def value(self) -> float:
        return self.numerator / self.denominator

    def to_dict(self) -> dict[str, int]:
        return {"numerator": self.numerator, "denominator": self.denominator}


@dataclass(frozen=True)
class CandidateOutcome:
    provider: str
    profile: str
    status: Literal["passed", "failed", "unavailable"]
    route_accuracy: ExactRate
    query_accuracy: ExactRate
    evidence_ref_accuracy: ExactRate
    character_error_rate: ExactRate | None
    word_error_rate: ExactRate | None
    elapsed_ms: int | None
    peak_rss_bytes: int | None
    temporary_bytes: int | None
    result_bytes: int | None
    model_bytes: int | None
    package_bytes: int | None
    cold_start: bool | None
    failure_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "profile": self.profile,
            "status": self.status,
            "route_accuracy": self.route_accuracy.to_dict(),
            "query_accuracy": self.query_accuracy.to_dict(),
            "evidence_ref_accuracy": self.evidence_ref_accuracy.to_dict(),
            "character_error_rate": (
                None if self.character_error_rate is None else self.character_error_rate.to_dict()
            ),
            "word_error_rate": (
                None if self.word_error_rate is None else self.word_error_rate.to_dict()
            ),
            "elapsed_ms": self.elapsed_ms,
            "peak_rss_bytes": self.peak_rss_bytes,
            "temporary_bytes": self.temporary_bytes,
            "result_bytes": self.result_bytes,
            "model_bytes": self.model_bytes,
            "package_bytes": self.package_bytes,
            "cold_start": self.cold_start,
            "failure_codes": list(self.failure_codes),
        }


@dataclass(frozen=True)
class Phase0Decision:
    status: Literal["go", "no_go"]
    selected_provider: str | None
    selected_profile: str | None
    outcomes: tuple[CandidateOutcome, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "selected_provider": self.selected_provider,
            "selected_profile": self.selected_profile,
        }


@dataclass(frozen=True)
class ProductProof:
    route_accuracy: ExactRate
    query_accuracy: ExactRate
    evidence_ref_accuracy: ExactRate
    publication_evidence_pages: frozenset[tuple[str, int]]
    failure_codes: tuple[str, ...]


def edit_rate(reference: str, candidate: str, *, unit: str) -> ExactRate:
    reference = normalize_ocr_text(reference)
    candidate = normalize_ocr_text(candidate)
    if unit == "codepoint":
        expected = list(reference)
        observed = list(candidate)
    elif unit == "whitespace_token":
        expected = reference.split()
        observed = candidate.split()
    else:
        raise ValueError("edit rate unit is unsupported")
    if not expected:
        raise ValueError("edit rate reference must not be empty")
    return ExactRate(_edit_distance(expected, observed), len(expected))


def _edit_distance(expected: Sequence[object], observed: Sequence[object]) -> int:
    previous = list(range(len(observed) + 1))
    for row, expected_item in enumerate(expected, start=1):
        current = [row]
        for column, observed_item in enumerate(observed, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected_item != observed_item),
                )
            )
        previous = current
    return previous[-1]


def validate_extractor_identity(value: Mapping[str, object]) -> None:
    payload = _closed(value, _IDENTITY_KEYS, "extractor identity")
    if payload["schema"] != "mke.pdf_ocr_extractor_identity.v1":
        _invalid("extractor identity schema is unsupported")
    protocol = _closed(payload["protocol"], {"id", "sha256"}, "protocol identity")
    _text(protocol["id"], "protocol id")
    _sha(protocol["sha256"], "protocol sha256")
    fixtures = _list(payload["fixtures"], "fixture identities")
    fixture_keys: list[str] = []
    for item in fixtures:
        fixture = _closed(
            item, {"document_id", "source_bytes", "source_sha256"}, "fixture identity"
        )
        fixture_keys.append(_text(fixture["document_id"], "document id"))
        _positive(fixture["source_bytes"], "source bytes")
        _sha(fixture["source_sha256"], "source sha256")
    _sorted_unique(fixture_keys, "fixture identities")
    router = _closed(payload["router"], {"implementation_sha256", "policy"}, "router")
    _sha(router["implementation_sha256"], "router implementation sha256")
    policy = _closed(router["policy"], _POLICY_KEYS, "routing policy")
    for key in _POLICY_KEYS - {
        "accepted_text_max_replacement_ratio",
        "ocr_min_image_coverage",
    }:
        _positive(policy[key], key)
    for key in ("accepted_text_max_replacement_ratio", "ocr_min_image_coverage"):
        ratio = _closed(policy[key], {"numerator", "denominator"}, key)
        _positive(ratio["numerator"], f"{key} numerator")
        _positive(ratio["denominator"], f"{key} denominator")
        if cast(int, ratio["numerator"]) > cast(int, ratio["denominator"]):
            _invalid(f"{key} is outside the unit interval")
    render = _closed(payload["render"], {"profile", "dpi", "pages"}, "render identity")
    _text(render["profile"], "render profile")
    _positive(render["dpi"], "render dpi")
    pages = _list(render["pages"], "render pages")
    page_keys: list[tuple[str, int]] = []
    for item in pages:
        page = _closed(
            item,
            {"document_id", "page_number", "image_bytes", "image_sha256"},
            "render page",
        )
        page_keys.append(
            (
                _text(page["document_id"], "render document id"),
                _positive(page["page_number"], "page number"),
            )
        )
        _positive(page["image_bytes"], "image bytes")
        _sha(page["image_sha256"], "image sha256")
    _sorted_unique(page_keys, "render pages")
    provider = _closed(payload["provider"], {"id", "profile"}, "provider identity")
    _text(provider["id"], "provider id")
    _text(provider["profile"], "provider profile")
    model = _closed(payload["model"], {"receipt_sha256", "tree_sha256"}, "model identity")
    _sha(model["receipt_sha256"], "model receipt sha256")
    _sha(model["tree_sha256"], "model tree sha256")
    package = _closed(
        payload["package"],
        {"receipt_sha256", "installed_packages_sha256", "mke_wheel_sha256"},
        "package identity",
    )
    for key in ("receipt_sha256", "installed_packages_sha256", "mke_wheel_sha256"):
        _sha(package[key], f"package {key}")
    normalization = _closed(
        payload["normalization"], {"implementation_sha256", "profile"}, "normalization"
    )
    _sha(normalization["implementation_sha256"], "normalization implementation sha256")
    _text(normalization["profile"], "normalization profile")
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ExtractorIdentityError("extractor identity is not finite JSON") from error


def canonical_extractor_identity_bytes(value: Mapping[str, object]) -> bytes:
    validate_extractor_identity(value)
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def extractor_fingerprint(value: Mapping[str, object]) -> str:
    return "pdf-ocr-eval-v1:" + hashlib.sha256(
        canonical_extractor_identity_bytes(value)
    ).hexdigest()


def decide(outcomes: Sequence[CandidateOutcome]) -> Phase0Decision:
    passing = [item for item in outcomes if _passes_hard_gates(item)]
    if not passing:
        return Phase0Decision("no_go", None, None, tuple(outcomes))
    winner = min(
        passing,
        key=lambda item: (
            cast(ExactRate, item.character_error_rate).value,
            item.peak_rss_bytes,
            item.provider,
        ),
    )
    return Phase0Decision("go", winner.provider, winner.profile, tuple(outcomes))


def _passes_hard_gates(value: CandidateOutcome) -> bool:
    return (
        value.status == "passed"
        and not value.failure_codes
        and value.route_accuracy.numerator == value.route_accuracy.denominator
        and value.query_accuracy.numerator == value.query_accuracy.denominator
        and value.evidence_ref_accuracy.numerator == value.evidence_ref_accuracy.denominator
        and value.character_error_rate is not None
        and value.word_error_rate is not None
        and type(value.elapsed_ms) is int
        and value.elapsed_ms > 0
        and type(value.peak_rss_bytes) is int
        and value.peak_rss_bytes > 0
    )


def publish_and_verify(
    *,
    protocol: PdfOcrEvaluationProtocol,
    recognized_text: Mapping[tuple[str, int], str | None],
    extractor_identity: Mapping[str, object],
    database: Path,
) -> ProductProof:
    fingerprint = extractor_fingerprint(extractor_identity)
    route_matches = 0
    route_total = 0
    decisions_by_document: dict[str, PdfInspectionResult] = {}
    missing = False
    for document in protocol.documents:
        inspection = inspect_pdf(protocol.resolve(document.fixture), EVALUATION_POLICY)
        decisions_by_document[document.document_id] = inspection
        for decision, expected in zip(inspection, document.pages, strict=True):
            route_total += 1
            route_matches += decision.route == expected.expected_route
            if expected.expected_route == "ocr_required" and not str(
                recognized_text.get((document.document_id, expected.page_number)) or ""
            ).strip():
                missing = True
    if route_matches != route_total:
        return ProductProof(
            ExactRate(route_matches, route_total),
            ExactRate(0, len(protocol.queries)),
            ExactRate(0, len(protocol.queries)),
            frozenset(),
            ("route_truth_mismatch",),
        )
    if missing:
        return ProductProof(
            ExactRate(route_matches, route_total),
            ExactRate(0, len(protocol.queries)),
            ExactRate(0, len(protocol.queries)),
            frozenset(),
            ("provider_output_incomplete",),
        )

    engine = KnowledgeEngine(database)
    sources: dict[str, str] = {}
    published_pages: set[tuple[str, int]] = set()
    try:
        for document in protocol.documents:
            source = engine.ensure_source(
                document.document_id,
                document.fixture.sha256,
                media_type="application/pdf",
            )
            sources[document.document_id] = source.source_id
            run = engine.create_run(source.source_id)
            evidence: list[CandidateEvidence] = []
            inspection = decisions_by_document[document.document_id]
            for decision, expected in zip(inspection, document.pages, strict=True):
                text: str | None = None
                if expected.expected_route == "text_layer_accepted":
                    text = decision.inspection.normalized_text
                elif expected.expected_route == "ocr_required":
                    text = cast(str, recognized_text[(document.document_id, expected.page_number)])
                if text is None:
                    continue
                published_pages.add((document.document_id, expected.page_number))
                evidence.append(
                    CandidateEvidence(
                        evidence_id="ev_"
                        + hashlib.sha256(
                            f"{document.document_id}:{expected.page_number}".encode()
                        ).hexdigest()[:32],
                        locator_kind="page",
                        locator_start=expected.page_number,
                        locator_end=expected.page_number,
                        text=text,
                    )
                )
            manifest = RunManifest(
                run_id=run.run_id,
                evidence_count=len(evidence),
                required_stages=("candidate_evidence", "pdf_ocr_extraction"),
                extractor_fingerprint=fingerprint,
                asset_sha256=document.fixture.sha256,
            )
            if extractor_fingerprint(extractor_identity) != manifest.extractor_fingerprint:
                raise ExtractorIdentityError(
                    "manifest fingerprint does not match extractor identity"
                )
            engine.persist_validated_candidate(run.run_id, evidence, manifest)
            engine.activate_publication(run.run_id)
    finally:
        engine.close()

    config = McpRuntimeConfig(runtime=RuntimeConfig(database), allowed_root=protocol.root)
    query_matches = 0
    locator_matches = 0
    failures: set[str] = set()
    for query in protocol.queries:
        search = search_library_v1(config, query.text).root
        ask = ask_library_v1(config, query.text).root
        expected_source = sources[query.expected_document_id]
        search_refs = search.results if isinstance(search, SearchLibrarySuccessV1) else []
        ask_refs = ask.evidence if isinstance(ask, AskLibrarySuccessV1) else []
        search_match = next(
            (
                item
                for item in search_refs
                if item.source_id == expected_source
                and item.locator.kind == "page"
                and item.locator.start == query.expected_page
                and item.locator.end == query.expected_page
            ),
            None,
        )
        ask_match = next(
            (
                item
                for item in ask_refs
                if item.source_id == expected_source
                and item.locator.kind == "page"
                and item.locator.start == query.expected_page
                and item.locator.end == query.expected_page
            ),
            None,
        )
        if search_match is not None and ask_match is not None:
            query_matches += 1
            if (
                search_match.schema_version == "mke.evidence_ref.v1"
                and ask_match.schema_version == "mke.evidence_ref.v1"
            ):
                locator_matches += 1
        else:
            failures.add("query_answerability_mismatch")
    if locator_matches != len(protocol.queries):
        failures.add("evidence_ref_mismatch")
    return ProductProof(
        ExactRate(route_matches, route_total),
        ExactRate(query_matches, len(protocol.queries)),
        ExactRate(locator_matches, len(protocol.queries)),
        frozenset(published_pages),
        tuple(sorted(failures)),
    )


def validate_scorecard(value: Mapping[str, object]) -> None:
    payload = _closed(
        value,
        {
            "schema",
            "protocol",
            "receipts",
            "measurement_policy",
            "authority_gates",
            "extractor_identities",
            "candidates",
            "decision",
        },
        "scorecard",
    )
    if payload["schema"] != "mke.pdf_ocr_phase0_scorecard.v1":
        raise ValueError("scorecard schema is unsupported")
    protocol = _closed(
        payload["protocol"],
        {"id", "sha256", "documents", "pages", "queries"},
        "scorecard protocol",
    )
    _text(protocol["id"], "scorecard protocol id")
    _sha(protocol["sha256"], "scorecard protocol sha256")
    for key in ("documents", "pages", "queries"):
        _positive(protocol[key], f"scorecard protocol {key}")
    receipts = _closed(
        payload["receipts"],
        {"package_sha256", "model_sha256", "provider_startup_sha256"},
        "scorecard receipts",
    )
    for key in ("package_sha256", "model_sha256", "provider_startup_sha256"):
        _sha(receipts[key], f"scorecard receipt {key}")
    measurement = _closed(
        payload["measurement_policy"], {"quality", "resources"}, "measurement policy"
    )
    if measurement != {
        "quality": "observed_not_approved",
        "resources": "observed_not_approved",
    }:
        raise ValueError("scorecard measurement policy is invalid")
    authority_gates = _closed(
        payload["authority_gates"],
        {"package_matrix", "provider_startup", "model_provenance", "licenses", "network"},
        "authority gates",
    )
    if authority_gates != {
        "package_matrix": "passed_16_of_16",
        "provider_startup": "passed_cache_only",
        "model_provenance": "verified",
        "licenses": "compatible_declared",
        "network": "blocked",
    }:
        raise ValueError("scorecard authority gates are invalid")

    identities = _list(payload["extractor_identities"], "extractor identities")
    identity_providers: list[str] = []
    identity_render_pages: dict[str, list[tuple[str, int]]] = {}
    for raw in identities:
        item = _closed(raw, {"provider", "fingerprint", "payload"}, "extractor binding")
        provider = _text(item["provider"], "extractor provider")
        identity = _closed(item["payload"], _IDENTITY_KEYS, "extractor identity")
        validate_extractor_identity(identity)
        if item["fingerprint"] != extractor_fingerprint(identity):
            raise ValueError("scorecard extractor fingerprint is invalid")
        if _closed(identity["provider"], {"id", "profile"}, "provider identity")["id"] != provider:
            raise ValueError("scorecard extractor provider is inconsistent")
        identity_providers.append(provider)
        render = _closed(identity["render"], {"profile", "dpi", "pages"}, "render identity")
        identity_render_pages[provider] = [
            _render_page_key(page)
            for page in cast(list[object], render["pages"])
        ]
    _sorted_unique(identity_providers, "scorecard extractor providers")

    candidates = _list(payload["candidates"], "scorecard candidates")
    candidate_providers: list[str] = []
    candidate_outcomes: list[CandidateOutcome] = []
    for raw in candidates:
        candidate = _closed(
            raw,
            {"outcome", "page_results", "publication_evidence_pages"},
            "scorecard candidate",
        )
        outcome = _closed(
            candidate["outcome"],
            {
                "provider",
                "profile",
                "status",
                "route_accuracy",
                "query_accuracy",
                "evidence_ref_accuracy",
                "character_error_rate",
                "word_error_rate",
                "elapsed_ms",
                "peak_rss_bytes",
                "temporary_bytes",
                "result_bytes",
                "model_bytes",
                "package_bytes",
                "cold_start",
                "failure_codes",
            },
            "candidate outcome",
        )
        provider = _text(outcome["provider"], "candidate provider")
        candidate_providers.append(provider)
        _text(outcome["profile"], "candidate profile")
        if outcome["status"] not in {"passed", "failed", "unavailable"}:
            raise ValueError("candidate status is invalid")
        accuracy_rates = {
            key: cast(ExactRate, _scorecard_rate(outcome[key], key, allow_none=False))
            for key in ("route_accuracy", "query_accuracy", "evidence_ref_accuracy")
        }
        if any(rate.numerator > rate.denominator for rate in accuracy_rates.values()):
            raise ValueError("candidate accuracy rate is invalid")
        character_error_rate = _scorecard_rate(
            outcome["character_error_rate"], "character_error_rate", allow_none=True
        )
        word_error_rate = _scorecard_rate(
            outcome["word_error_rate"], "word_error_rate", allow_none=True
        )
        for key in (
            "elapsed_ms",
            "peak_rss_bytes",
            "temporary_bytes",
            "result_bytes",
            "package_bytes",
        ):
            if outcome[key] is not None:
                _positive(outcome[key], key)
        if outcome["model_bytes"] is not None:
            _nonnegative(outcome["model_bytes"], "model_bytes")
        if outcome["cold_start"] is not None and type(outcome["cold_start"]) is not bool:
            raise ValueError("candidate cold-start flag is invalid")
        raw_failures = outcome["failure_codes"]
        if not isinstance(raw_failures, list):
            raise ValueError("candidate failure codes are invalid")
        failure_items = cast(list[object], raw_failures)
        if any(
            not isinstance(code, str) or re.fullmatch(r"[a-z0-9_]+", code) is None
            for code in failure_items
        ):
            raise ValueError("candidate failure codes are invalid")
        failures = cast(list[str], raw_failures)
        if failures != sorted(set(failures)):
            raise ValueError("candidate failure codes must be sorted and unique")
        candidate_outcomes.append(
            CandidateOutcome(
                provider=provider,
                profile=cast(str, outcome["profile"]),
                status=cast(Literal["passed", "failed", "unavailable"], outcome["status"]),
                route_accuracy=accuracy_rates["route_accuracy"],
                query_accuracy=accuracy_rates["query_accuracy"],
                evidence_ref_accuracy=accuracy_rates["evidence_ref_accuracy"],
                character_error_rate=character_error_rate,
                word_error_rate=word_error_rate,
                elapsed_ms=cast(int | None, outcome["elapsed_ms"]),
                peak_rss_bytes=cast(int | None, outcome["peak_rss_bytes"]),
                temporary_bytes=cast(int | None, outcome["temporary_bytes"]),
                result_bytes=cast(int | None, outcome["result_bytes"]),
                model_bytes=cast(int | None, outcome["model_bytes"]),
                package_bytes=cast(int | None, outcome["package_bytes"]),
                cold_start=outcome["cold_start"],
                failure_codes=tuple(failures),
            )
        )
        page_keys, all_nonempty = _validate_page_inventory(candidate["page_results"], result=True)
        if page_keys != identity_render_pages[provider]:
            raise ValueError("candidate page results do not match rendered pages")
        if outcome["status"] == "passed" and not all_nonempty:
            raise ValueError("passed candidate has an empty OCR page")
        _validate_page_inventory(candidate["publication_evidence_pages"], result=False)
    _sorted_unique(candidate_providers, "scorecard candidate providers")
    if candidate_providers != identity_providers:
        raise ValueError("scorecard candidate identities are incomplete")
    if tuple(candidate_providers) != _PROVIDERS:
        raise ValueError("scorecard provider inventory is invalid")

    decision = _closed(
        payload["decision"],
        {"status", "selected_provider", "selected_profile"},
        "scorecard decision",
    )
    if decision["status"] == "go":
        selected = _text(decision["selected_provider"], "selected provider")
        _text(decision["selected_profile"], "selected profile")
        if selected not in candidate_providers:
            raise ValueError("selected provider is unknown")
    elif decision["status"] == "no_go":
        if decision["selected_provider"] is not None or decision["selected_profile"] is not None:
            raise ValueError("no-go decision must not select a provider")
    else:
        raise ValueError("scorecard decision is invalid")
    if decision != decide(candidate_outcomes).to_dict():
        raise ValueError("scorecard decision is inconsistent with candidate outcomes")


def canonical_scorecard_bytes(value: Mapping[str, object]) -> bytes:
    validate_scorecard(value)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8") + b"\n"
    except (TypeError, ValueError) as error:
        raise ValueError("scorecard must be finite JSON") from error
    if len(encoded) > 2 * 1024 * 1024 or _PRIVATE_RE.search(encoded.decode("ascii")):
        raise ValueError("scorecard is not public-neutral and bounded")
    return encoded


def _scorecard_rate(value: object, label: str, *, allow_none: bool) -> ExactRate | None:
    if value is None and allow_none:
        return None
    rate = _closed(value, {"numerator", "denominator"}, label)
    numerator = rate["numerator"]
    denominator = rate["denominator"]
    if type(numerator) is not int or numerator < 0:
        raise ValueError(f"{label} numerator is invalid")
    return ExactRate(numerator, _positive(denominator, f"{label} denominator"))


def _validate_page_inventory(
    value: object, *, result: bool
) -> tuple[list[tuple[str, int]], bool]:
    if not isinstance(value, list) or not value:
        raise ValueError("scorecard page inventory is invalid")
    pages = cast(list[object], value)
    keys: list[tuple[str, int]] = []
    all_nonempty = True
    expected = {"document_id", "page_number"}
    if result:
        expected |= {"normalized_text_sha256", "nonempty"}
    for raw in pages:
        page = _closed(raw, expected, "scorecard page")
        keys.append(
            (
                _text(page["document_id"], "scorecard document id"),
                _positive(page["page_number"], "scorecard page number"),
            )
        )
        if result:
            _sha(page["normalized_text_sha256"], "scorecard text sha256")
            if type(page["nonempty"]) is not bool:
                raise ValueError("scorecard nonempty flag is invalid")
            all_nonempty = all_nonempty and page["nonempty"] is True
    _sorted_unique(keys, "scorecard pages")
    return keys, all_nonempty


def _render_page_key(value: object) -> tuple[str, int]:
    page = _closed(
        value,
        {"document_id", "page_number", "image_bytes", "image_sha256"},
        "render page",
    )
    return (
        _text(page["document_id"], "render document id"),
        _positive(page["page_number"], "render page number"),
    )


def _closed(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _invalid(f"{label} keys are invalid")
    payload = cast(dict[str, object], value)
    if set(payload) != keys:
        _invalid(f"{label} keys are invalid")
    return payload


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list) or not value:
        _invalid(f"{label} must be a non-empty list")
    return cast(list[object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        _invalid(f"{label} is invalid")
    return cast(str, value)


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        _invalid(f"{label} must be a positive integer")
    return cast(int, value)


def _nonnegative(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        _invalid(f"{label} must be a non-negative integer")
    return cast(int, value)


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA_RE.fullmatch(value) is None:
        _invalid(f"{label} is invalid")
    return cast(str, value)


def _sorted_unique(values: Sequence[object], label: str) -> None:
    if (
        list(values) != sorted(values)  # pyright: ignore[reportArgumentType]
        or len(values) != len(set(values))
    ):
        _invalid(f"{label} must be sorted and unique")


def _invalid(cause: str) -> None:
    raise ExtractorIdentityError(cause)
