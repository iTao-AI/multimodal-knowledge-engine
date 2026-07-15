"""Disposable product-path runner for the PDF OCR Phase 0 scorecard."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from mke.application import KnowledgeEngine
from mke.domain import CandidateEvidence, RunManifest
from mke.evaluation.pdf_ocr_protocol import (
    PdfOcrEvaluationProtocol,
    load_pdf_ocr_evaluation_protocol,
)
from mke.evaluation.pdf_ocr_provider import (
    OcrEvalPageResult,
    PdfOcrProviderError,
    ProviderCommand,
    normalize_ocr_text,
    run_provider,
)
from mke.evaluation.pdf_ocr_router import (
    EVALUATION_POLICY,
    PdfInspectionResult,
    RenderedPage,
    inspect_pdf,
    render_ocr_pages,
)
from mke.interfaces.mcp_contract import McpRuntimeConfig, ask_library_v1, search_library_v1
from mke.interfaces.mcp_schemas import (
    AskLibrarySuccessV1,
    EvidenceRefV1,
    SearchLibrarySuccessV1,
)
from mke.runtime import RuntimeConfig

_SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
_PROVIDERS = (
    "apple-vision-local-v1",
    "paddleocr-vl-1.6-cpu-spike-v1",
    "ppocrv6-medium-cpu-spike-v1",
)
_PROTOCOL_ID = "pdf-ocr-phase0-v1"
_PROTOCOL_SHA256 = "1c1f9310f3c719843e2af49ce44b0d03218c85ab84c7bd9f148afea3d6d1c2ef"
_PROTOCOL_COUNTS = {"documents": 4, "pages": 9, "queries": 3}
_FIXTURE_AUTHORITY = (
    ("chinese-scan", 25147, "face9a62aac30ef2b6e62641dc21fd97dd4e9c554f89230aaa51c28475549414"),
    ("english-scan", 25158, "f7f5813a2d9bbb4012888d711982413f5117b92a6374a5819e80ddcc75b26ad8"),
    ("mixed-prose", 26201, "8f92e133810cf2c3603c23eb5e70e083f3e4a15c707b0cf6275aa3e7d263d090"),
    (
        "routing-adversarial",
        26320,
        "82a96551deb92e4bdbba0e556c532c6ab5a95536ba8a859a9555213f889acb3f",
    ),
)
_PUBLICATION_PAGE_AUTHORITY = (
    ("chinese-scan", 1),
    ("english-scan", 1),
    ("mixed-prose", 1),
    ("mixed-prose", 2),
    ("routing-adversarial", 5),
)
_PROFILE = "phase0-200dpi-plain-text-v1"
_RENDER_PROFILE = "phase0-200dpi-png-v1"
_NORMALIZATION_PROFILE = "unicode-nfc-lines-v1"
_PACKAGE_RECEIPT_SHA256 = "d2232fcbd6775a9f03fa3d2a77b181987b5cfa43c9fdc1efcb48f08f01553d2a"
_MODEL_RECEIPT_SHA256 = "3d1e8c45b7ed0c817acaeda3f51954b463016763690e09ca1f23162042219d6e"
_STARTUP_RECEIPT_SHA256 = "1a159461fd73c7069905b0a085f5b900f4b1577dbf418a86adcf96b9c6354652"
_PACKAGE_CANDIDATES = (
    "ppocrv6-medium-cpu-spike-v1",
    "paddleocr-vl-1.6-cpu-spike-v1",
)
_SANDBOX_PREFIX = (
    "/usr/bin/sandbox-exec",
    "-p",
    "(version 1)(allow default)(deny network*)",
)
_COMMON_PROVIDER_ARGUMENTS = (
    "--input",
    "{input}",
    "--output",
    "{output}",
    "--page-number",
    "{page_number}",
)
_RUNTIME_DOCTOR = r"""
import hashlib
import importlib
import importlib.metadata as metadata
import json
import os
import pathlib
import platform
import sys
import mke
paddle = importlib.import_module("paddle")
paddleocr = importlib.import_module("paddleocr")
assert paddle is not None
assert hasattr(paddleocr, "PaddleOCRVL")
versions = {}
for distribution in metadata.distributions():
    name = distribution.metadata.get("Name")
    if name:
        versions.setdefault(name.lower().replace("_", "-"), distribution.version)
distribution = metadata.distribution("multimodal-knowledge-engine")
direct_url_file = next(
    item for item in (distribution.files or ()) if item.name == "direct_url.json"
)
direct_url_path = pathlib.Path(distribution.locate_file(direct_url_file))
direct_url = json.loads(direct_url_path.read_text(encoding="utf-8"))
print(json.dumps({
    "python": platform.python_version(),
    "mke_version": metadata.version("multimodal-knowledge-engine"),
    "mke_file": mke.__file__,
    "sys_executable": sys.executable,
    "sys_prefix": sys.prefix,
    "sys_base_prefix": sys.base_prefix,
    "isolated": sys.flags.isolated == 1,
    "pythonpath_present": "PYTHONPATH" in os.environ,
    "package_versions": versions,
    "direct_url": direct_url,
}, sort_keys=True))
"""
_NETWORK_CANARY = (
    "import socket;"
    "socket.create_connection(('1.1.1.1',53),timeout=1)"
)
_SAFE_TEXT_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*\Z")
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ][0-9:]+(?:\.\d+)?Z?\Z")
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


class Phase0RunnerError(RuntimeError):
    """A stable failure from the tracked Phase 0 evaluation controller."""

    def __init__(self, problem: str) -> None:
        super().__init__(problem)
        self.problem = problem


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
    route_accuracy: ExactRate | None
    query_accuracy: ExactRate | None
    evidence_ref_accuracy: ExactRate | None
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
            "route_accuracy": _optional_rate_dict(self.route_accuracy),
            "query_accuracy": _optional_rate_dict(self.query_accuracy),
            "evidence_ref_accuracy": _optional_rate_dict(self.evidence_ref_accuracy),
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


@dataclass(frozen=True)
class CandidateRunConfig:
    provider: str
    command: ProviderCommand | None
    unavailable_code: str | None = None


@dataclass(frozen=True)
class Phase0RunnerConfig:
    protocol: Path
    package_receipt: Path
    model_receipt: Path
    startup_receipt: Path
    workspace: Path
    output: Path
    candidates: tuple[CandidateRunConfig, ...]


@dataclass(frozen=True)
class _RunnerAuthority:
    receipts: dict[str, str]
    model_tree_sha256: str
    installed_packages_sha256: str
    mke_wheel_sha256: str
    package_bytes: dict[str, int]
    model_bytes: dict[str, int]
    package_versions: dict[str, str]
    mke_wheel_filename: str
    model_receipt: dict[str, object]


class _ProcessTreeRssMonitor:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self.peak_bytes = 0
        self.samples = 0

    def start(self) -> None:
        self._thread.start()

    def finish(self) -> int:
        self._stop.set()
        self._thread.join(timeout=2.0)
        if self._thread.is_alive() or self.samples == 0 or self.peak_bytes <= 0:
            raise Phase0RunnerError("resource_measurement_failed")
        return self.peak_bytes

    def _sample(self) -> None:
        while not self._stop.is_set():
            try:
                completed = subprocess.run(
                    ("/bin/ps", "-axo", "pid=,ppid=,rss="),
                    check=False,
                    capture_output=True,
                    timeout=1.0,
                    env={"PATH": "/usr/bin:/bin"},
                )
                if completed.returncode == 0:
                    rows = [tuple(map(int, line.split())) for line in completed.stdout.splitlines()]
                    children: dict[int, list[int]] = {}
                    rss: dict[int, int] = {}
                    for pid, parent, kilobytes in rows:
                        children.setdefault(parent, []).append(pid)
                        rss[pid] = kilobytes
                    pending = list(children.get(os.getpid(), ()))
                    descendants: set[int] = set()
                    while pending:
                        pid = pending.pop()
                        if pid in descendants:
                            continue
                        descendants.add(pid)
                        pending.extend(children.get(pid, ()))
                    total = sum(rss.get(pid, 0) for pid in descendants) * 1024
                    self.peak_bytes = max(self.peak_bytes, total)
                    self.samples += 1
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
            self._stop.wait(0.02)


@dataclass(frozen=True)
class _ExpectedEvidenceRef:
    schema_version: str
    evidence_id: str
    source_id: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    page_number: int
    text: str


def _optional_rate_dict(value: ExactRate | None) -> dict[str, int] | None:
    return None if value is None else value.to_dict()


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
    return (
        "pdf-ocr-eval-v1:" + hashlib.sha256(canonical_extractor_identity_bytes(value)).hexdigest()
    )


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
        and value.route_accuracy is not None
        and value.query_accuracy is not None
        and value.evidence_ref_accuracy is not None
        and value.route_accuracy.numerator == value.route_accuracy.denominator
        and value.query_accuracy.numerator == value.query_accuracy.denominator
        and value.evidence_ref_accuracy.numerator == value.evidence_ref_accuracy.denominator
        and value.character_error_rate is not None
        and value.word_error_rate is not None
        and type(value.elapsed_ms) is int
        and value.elapsed_ms > 0
        and type(value.peak_rss_bytes) is int
        and value.peak_rss_bytes > 0
        and type(value.temporary_bytes) is int
        and value.temporary_bytes > 0
        and type(value.result_bytes) is int
        and value.result_bytes > 0
        and type(value.model_bytes) is int
        and value.model_bytes >= 0
        and type(value.package_bytes) is int
        and value.package_bytes > 0
        and type(value.cold_start) is bool
    )


def publish_and_verify(
    *,
    protocol: PdfOcrEvaluationProtocol,
    recognized_text: Mapping[tuple[str, int], str | None],
    extractor_identity: Mapping[str, object],
    database: Path,
    inspections: Mapping[str, PdfInspectionResult] | None = None,
) -> ProductProof:
    fingerprint = extractor_fingerprint(extractor_identity)
    route_matches = 0
    route_total = 0
    decisions_by_document: dict[str, PdfInspectionResult] = {}
    missing = False
    for document in protocol.documents:
        inspection = (
            inspections[document.document_id]
            if inspections is not None
            else inspect_pdf(protocol.resolve(document.fixture), EVALUATION_POLICY)
        )
        decisions_by_document[document.document_id] = inspection
        for decision, expected in zip(inspection, document.pages, strict=True):
            route_total += 1
            route_matches += decision.route == expected.expected_route
            if (
                expected.expected_route == "ocr_required"
                and not str(
                    recognized_text.get((document.document_id, expected.page_number)) or ""
                ).strip()
            ):
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
    expected_refs: dict[tuple[str, int], _ExpectedEvidenceRef] = {}
    published_pages: set[tuple[str, int]] = set()
    try:
        for document in protocol.documents:
            source = engine.ensure_source(
                document.document_id,
                document.fixture.sha256,
                media_type="application/pdf",
            )
            run = engine.create_run(source.source_id)
            evidence: list[CandidateEvidence] = []
            expected_evidence: list[CandidateEvidence] = []
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
                candidate_evidence = CandidateEvidence(
                    evidence_id="ev_"
                    + hashlib.sha256(
                        f"{document.document_id}:{expected.page_number}".encode()
                    ).hexdigest()[:32],
                    locator_kind="page",
                    locator_start=expected.page_number,
                    locator_end=expected.page_number,
                    text=normalize_ocr_text(text),
                )
                evidence.append(candidate_evidence)
                expected_evidence.append(candidate_evidence)
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
            activation = engine.activate_publication(run.run_id)
            if not activation.published or activation.publication_id is None:
                raise ValueError("disposable Publication activation failed")
            for item in expected_evidence:
                expected_refs[(document.document_id, item.locator_start)] = _ExpectedEvidenceRef(
                    schema_version="mke.evidence_ref.v1",
                    evidence_id=item.evidence_id,
                    source_id=source.source_id,
                    content_fingerprint="sha256:" + document.fixture.sha256,
                    publication_id=activation.publication_id,
                    publication_revision=source.active_revision + 1,
                    run_id=run.run_id,
                    page_number=item.locator_start,
                    text=item.text,
                )
    finally:
        engine.close()

    config = McpRuntimeConfig(runtime=RuntimeConfig(database), allowed_root=protocol.root)
    query_matches = 0
    locator_matches = 0
    failures: set[str] = set()
    for query in protocol.queries:
        search = search_library_v1(config, query.text).root
        ask = ask_library_v1(config, query.text).root
        expected_ref = expected_refs[(query.expected_document_id, query.expected_page)]
        search_refs = search.results if isinstance(search, SearchLibrarySuccessV1) else []
        ask_refs = ask.evidence if isinstance(ask, AskLibrarySuccessV1) else []
        search_match = next(
            (item for item in search_refs if _ref_matches(item, expected_ref)), None
        )
        ask_match = next((item for item in ask_refs if _ref_matches(item, expected_ref)), None)
        if search_match is not None and ask_match is not None:
            query_matches += 1
            locator_matches += 1
        else:
            combined = [*search_refs, *ask_refs]
            if any(
                item.locator.kind == "page"
                and item.locator.start == expected_ref.page_number
                and item.locator.end == expected_ref.page_number
                and item.text != expected_ref.text
                for item in combined
            ):
                failures.add("payload_truth_mismatch")
            elif combined:
                failures.add("evidence_ref_mismatch")
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


def _ref_matches(value: EvidenceRefV1, expected: _ExpectedEvidenceRef) -> bool:
    return (
        value.schema_version == expected.schema_version
        and value.evidence_id == expected.evidence_id
        and value.source_id == expected.source_id
        and value.content_fingerprint == expected.content_fingerprint
        and value.publication_id == expected.publication_id
        and value.publication_revision == expected.publication_revision
        and value.run_id == expected.run_id
        and value.locator.kind == "page"
        and value.locator.start == expected.page_number
        and value.locator.end == expected.page_number
        and value.text == expected.text
    )


def run_phase0_scorecard(
    config: Phase0RunnerConfig,
) -> dict[str, object]:
    """Run the closed Phase 0 comparison and atomically publish canonical evidence."""
    protocol, authority = _load_controller_inputs(config)
    _validate_current_run_authority(config, authority)
    payload = _evaluate_phase0_scorecard(
        config,
        protocol,
        authority,
        provider_runner=run_provider,
        peak_rss_reader=None,
    )
    _publish_scorecard(config.output, canonical_scorecard_bytes(payload))
    return payload


def _run_phase0_scorecard_for_test(  # pyright: ignore[reportUnusedFunction]
    config: Phase0RunnerConfig,
    *,
    provider_runner: Callable[..., OcrEvalPageResult],
    peak_rss_reader: Callable[[], int] | None = None,
) -> dict[str, object]:
    """Exercise controller composition without publishing an authority artifact."""
    protocol, authority = _load_controller_inputs(config)
    return _evaluate_phase0_scorecard(
        config,
        protocol,
        authority,
        provider_runner=provider_runner,
        peak_rss_reader=peak_rss_reader,
    )


def _load_controller_inputs(
    config: Phase0RunnerConfig,
) -> tuple[PdfOcrEvaluationProtocol, _RunnerAuthority]:
    _validate_runner_config(config)
    authority = _load_runner_authority(config)
    protocol = load_pdf_ocr_evaluation_protocol(config.protocol)
    if protocol.providers != _PROVIDERS:
        raise Phase0RunnerError("protocol_authority_invalid")
    protocol_bytes = config.protocol.read_bytes()
    if hashlib.sha256(protocol_bytes).hexdigest() != _PROTOCOL_SHA256:
        raise Phase0RunnerError("protocol_authority_invalid")
    return protocol, authority


def _evaluate_phase0_scorecard(
    config: Phase0RunnerConfig,
    protocol: PdfOcrEvaluationProtocol,
    authority: _RunnerAuthority,
    *,
    provider_runner: Callable[..., OcrEvalPageResult],
    peak_rss_reader: Callable[[], int] | None,
) -> dict[str, object]:
    payload: dict[str, object]
    try:
        config.workspace.mkdir(mode=0o700, parents=False, exist_ok=False)
        inspections, renders = _render_common_pages(protocol, config.workspace / "renders")
        identities = [
            _build_extractor_binding(protocol, renders, candidate.provider, authority)
            for candidate in config.candidates
        ]
        candidates = [
            _run_candidate(
                protocol=protocol,
                candidate=candidate,
                identity=cast(dict[str, object], identity["payload"]),
                inspections=inspections,
                renders=renders,
                workspace=config.workspace,
                authority=authority,
                provider_runner=provider_runner,
                peak_rss_reader=peak_rss_reader,
            )
            for candidate, identity in zip(config.candidates, identities, strict=True)
        ]
        outcomes = tuple(_candidate_outcome(item) for item in candidates)
        payload = {
            "schema": "mke.pdf_ocr_phase0_scorecard.v1",
            "protocol": {"id": _PROTOCOL_ID, "sha256": _PROTOCOL_SHA256, **_PROTOCOL_COUNTS},
            "receipts": authority.receipts,
            "measurement_policy": {
                "quality": "observed_not_approved",
                "resources": "observed_not_approved",
            },
            "authority_gates": {
                "package_matrix": "passed_16_of_16",
                "provider_startup": "passed_cache_only",
                "model_provenance": "verified",
                "licenses": "compatible_declared",
                "network": "blocked",
            },
            "extractor_identities": identities,
            "candidates": candidates,
            "decision": decide(outcomes).to_dict(),
        }
        canonical_scorecard_bytes(payload)
    except Phase0RunnerError:
        raise
    except (OSError, ValueError) as error:
        raise Phase0RunnerError("phase0_runner_failed") from error
    finally:
        cleanup_error: OSError | None = None
        if config.workspace.exists():
            try:
                shutil.rmtree(config.workspace)
            except OSError as error:
                cleanup_error = error
        if cleanup_error is not None:
            raise Phase0RunnerError("cleanup_failed") from cleanup_error
    return payload


def _publish_scorecard(output: Path, encoded: bytes) -> None:
    temporary = output.parent / (f".{output.name}.{secrets.token_hex(8)}.tmp")
    try:
        _write_owned_file(temporary, encoded)
        os.replace(temporary, output)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise Phase0RunnerError("scorecard_publication_failed") from error


def _validate_runner_config(config: Phase0RunnerConfig) -> None:
    if tuple(item.provider for item in config.candidates) != _PROVIDERS:
        raise Phase0RunnerError("candidate_inventory_invalid")
    for item in config.candidates:
        if item.command is None:
            if (
                item.unavailable_code is None
                or re.fullmatch(r"[a-z0-9_]+", item.unavailable_code) is None
            ):
                raise Phase0RunnerError("candidate_inventory_invalid")
        elif (
            item.unavailable_code is not None
            or item.command.provider != item.provider
            or item.command.profile != _PROFILE
        ):
            raise Phase0RunnerError("candidate_inventory_invalid")
    if config.workspace.exists() or config.workspace.is_symlink():
        raise Phase0RunnerError("workspace_invalid")
    if not config.workspace.parent.is_dir() or config.workspace.parent.is_symlink():
        raise Phase0RunnerError("workspace_invalid")
    if (
        not config.output.parent.is_dir()
        or config.output.parent.is_symlink()
        or config.output.is_symlink()
    ):
        raise Phase0RunnerError("scorecard_output_invalid")
    if (
        config.workspace.parent.resolve() == config.output.resolve().parent
        and config.output == config.workspace
    ):
        raise Phase0RunnerError("scorecard_output_invalid")


def _validate_current_run_authority(
    config: Phase0RunnerConfig, authority: _RunnerAuthority
) -> None:
    try:
        commands = {
            item.provider: item.command
            for item in config.candidates
            if item.command is not None
        }
        if not commands:
            raise ValueError("no available candidate command")
        runtime_python, apple_executable, components = _validate_command_shapes(commands)
        _run_network_canary(runtime_python)
        authority_home = config.workspace.parent / ".pdf-ocr-current-authority"
        authority_home.mkdir(mode=0o700, exist_ok=False)
        try:
            runtime_prefix = _validate_installed_runtime(
                runtime_python, authority, authority_home
            )
        finally:
            try:
                shutil.rmtree(authority_home)
            except OSError as error:
                raise Phase0RunnerError("cleanup_failed") from error
            if authority_home.exists():
                raise Phase0RunnerError("cleanup_failed")
        _validate_apple_executable(apple_executable, runtime_prefix, config.workspace.parent)
        _validate_model_root(components, authority.model_receipt)
    except Phase0RunnerError:
        raise
    except (
        KeyError,
        OSError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise Phase0RunnerError("current_run_authority_invalid") from error


def _validate_command_shapes(
    commands: Mapping[str, ProviderCommand],
) -> tuple[Path, Path, dict[str, Path]]:
    expected_available = set(_PROVIDERS)
    if set(commands) != expected_available:
        raise ValueError("all reviewed candidates must be available")
    apple = commands["apple-vision-local-v1"]
    vl = commands["paddleocr-vl-1.6-cpu-spike-v1"]
    ppocr = commands["ppocrv6-medium-cpu-spike-v1"]
    _validate_command_limits(apple, timeout=180.0)
    _validate_command_limits(vl, timeout=900.0)
    _validate_command_limits(ppocr, timeout=600.0)
    if apple.argv[:3] != _SANDBOX_PREFIX or apple.argv[4:] != _COMMON_PROVIDER_ARGUMENTS:
        raise ValueError("Apple Vision command is not closed")
    apple_executable = Path(apple.argv[3])
    runtime_python, vl_components = _validate_paddle_command(
        vl,
        module="mke.evaluation.pdf_ocr_paddle_vl",
        model_arguments=("--layout-model-dir", "--vl-model-dir"),
        component_names=("PP-DocLayoutV3", "PaddleOCR-VL-1.6"),
    )
    ppocr_python, ppocr_components = _validate_paddle_command(
        ppocr,
        module="mke.evaluation.pdf_ocr_ppocrv6",
        model_arguments=("--detection-model-dir", "--recognition-model-dir"),
        component_names=("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"),
    )
    if runtime_python != ppocr_python:
        raise ValueError("Paddle candidates do not share one installed runtime")
    return runtime_python, apple_executable, {**vl_components, **ppocr_components}


def _validate_command_limits(command: ProviderCommand, *, timeout: float) -> None:
    if (
        command.profile != _PROFILE
        or command.timeout_seconds != timeout
        or command.max_stdout_bytes != 64 * 1024
        or command.max_stderr_bytes != 256 * 1024
        or command.max_result_bytes != 8 * 1024 * 1024
    ):
        raise ValueError("provider limits are not the reviewed profile")


def _validate_paddle_command(
    command: ProviderCommand,
    *,
    module: str,
    model_arguments: tuple[str, str],
    component_names: tuple[str, str],
) -> tuple[Path, dict[str, Path]]:
    argv = command.argv
    if len(argv) != 17 or argv[:3] != _SANDBOX_PREFIX:
        raise ValueError("Paddle command is not closed")
    if argv[4:7] != ("-I", "-m", module) or argv[7:13] != _COMMON_PROVIDER_ARGUMENTS:
        raise ValueError("Paddle module authority is invalid")
    if argv[13] != model_arguments[0] or argv[15] != model_arguments[1]:
        raise ValueError("Paddle model arguments are invalid")
    components = {
        component_names[0]: Path(argv[14]),
        component_names[1]: Path(argv[16]),
    }
    if any(
        not path.name.startswith(f"{component}-")
        for component, path in components.items()
    ):
        raise ValueError("Paddle model root is invalid")
    return Path(argv[3]), components


def _run_network_canary(runtime_python: Path) -> None:
    try:
        result = subprocess.run(
            (*_SANDBOX_PREFIX, str(runtime_python), "-I", "-c", _NETWORK_CANARY),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=10.0,
            env={"PATH": "/usr/bin:/bin", "HOME": "/var/empty", "TMPDIR": "/tmp"},
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise Phase0RunnerError("current_run_authority_invalid") from error
    if result.returncode == 0:
        raise Phase0RunnerError("current_run_network_not_blocked")
    diagnostic = result.stderr.decode("utf-8", errors="replace")
    if "Operation not permitted" not in diagnostic and "PermissionError" not in diagnostic:
        raise Phase0RunnerError("current_run_network_not_blocked")


def _validate_installed_runtime(
    runtime_python: Path, authority: _RunnerAuthority, authority_home: Path
) -> Path:
    if not runtime_python.exists() or runtime_python.is_dir():
        raise ValueError("installed Python is unavailable")
    result = subprocess.run(
        (str(runtime_python), "-I", "-c", _RUNTIME_DOCTOR),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=120.0,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(authority_home),
            "TMPDIR": str(authority_home),
            "PADDLE_PDX_CACHE_HOME": str(authority_home / "paddlex"),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        },
    )
    if result.returncode != 0 or len(result.stdout) > 8 * 1024 * 1024:
        raise ValueError("installed runtime doctor failed")
    raw: object = json.loads(result.stdout)
    doctor = _closed(
        raw,
        {
            "python",
            "mke_version",
            "mke_file",
            "sys_executable",
            "sys_prefix",
            "sys_base_prefix",
            "isolated",
            "pythonpath_present",
            "package_versions",
            "direct_url",
        },
        "installed runtime doctor",
    )
    package_versions_raw = doctor["package_versions"]
    if not isinstance(package_versions_raw, dict):
        raise ValueError("installed package map is invalid")
    package_versions = cast(dict[object, object], package_versions_raw)
    if (
        doctor["python"] != "3.13.12"
        or doctor["mke_version"] != "0.1.2"
        or doctor["isolated"] is not True
        or doctor["pythonpath_present"] is not False
        or package_versions != authority.package_versions
        or _canonical_sha256(package_versions) != authority.installed_packages_sha256
    ):
        raise ValueError("installed runtime identity drifted")
    prefix = Path(cast(str, doctor["sys_prefix"])).resolve()
    executable = Path(cast(str, doctor["sys_executable"])).resolve()
    module = Path(cast(str, doctor["mke_file"])).resolve()
    base_prefix = Path(cast(str, doctor["sys_base_prefix"])).resolve()
    if (
        executable != runtime_python.resolve()
        or not _within(module, prefix)
        or "site-packages" not in module.parts
        or _within(base_prefix, prefix)
    ):
        raise ValueError("installed runtime origin is invalid")
    direct_url = _closed(doctor["direct_url"], {"archive_info", "url"}, "wheel direct URL")
    archive = _closed(direct_url["archive_info"], {"hash", "hashes"}, "wheel archive")
    hashes = _closed(archive["hashes"], {"sha256"}, "wheel archive hashes")
    url = cast(str, direct_url["url"])
    if (
        archive["hash"] != f"sha256={authority.mke_wheel_sha256}"
        or hashes["sha256"] != authority.mke_wheel_sha256
        or not url.startswith("file://")
        or Path(url.removeprefix("file://")).name != authority.mke_wheel_filename
    ):
        raise ValueError("installed MKE wheel identity drifted")
    return prefix


def _validate_apple_executable(executable: Path, runtime_prefix: Path, owned_parent: Path) -> None:
    metadata = executable.lstat()
    if (
        executable.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_mode & 0o111 == 0
        or executable.name != "apple-vision-child"
        or executable.parent.resolve() != owned_parent.resolve()
        or runtime_prefix.parent.resolve() != owned_parent.resolve()
    ):
        raise ValueError("Apple Vision child identity is invalid")
    _read_bound_regular_file(executable, metadata.st_size, None)


def _validate_model_root(
    components: Mapping[str, Path], model_receipt: Mapping[str, object]
) -> None:
    models_raw = model_receipt.get("models")
    if not isinstance(models_raw, list):
        raise ValueError("model receipt inventory is invalid")
    model_items = cast(list[object], models_raw)
    models = [cast(dict[str, object], item) for item in model_items if isinstance(item, dict)]
    if len(models) != 4 or set(components) != {cast(str, item["component"]) for item in models}:
        raise ValueError("model component inventory is invalid")
    roots = {path.parent.resolve() for path in components.values()}
    if len(roots) != 1:
        raise ValueError("model components do not share one retained root")
    aggregate: list[dict[str, object]] = []
    for model in models:
        component_name = cast(str, model["component"])
        tree_sha256 = _sha(model["tree_sha256"], "model component tree sha256")
        component = components[component_name]
        if component.name != f"{component_name}-{tree_sha256}":
            raise ValueError("model component path is not content-addressed")
        files = _validate_model_component(component, model)
        if _canonical_sha256(files) != tree_sha256:
            raise ValueError("model component tree drifted")
        aggregate.append(
            {
                "path": component_name,
                "bytes": _positive(model["total_bytes"], "model component bytes"),
                "sha256": tree_sha256,
            }
        )
    if _canonical_sha256(aggregate) != model_receipt.get("tree_sha256"):
        raise ValueError("model aggregate tree drifted")


def _validate_model_component(
    component: Path, model: Mapping[str, object]
) -> list[dict[str, object]]:
    metadata = component.lstat()
    if component.is_symlink() or not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode & 0o222:
        raise ValueError("model component is not sealed")
    files_raw = model.get("files")
    if not isinstance(files_raw, list):
        raise ValueError("model file inventory is invalid")
    file_items = cast(list[object], files_raw)
    expected = [cast(dict[str, object], item) for item in file_items if isinstance(item, dict)]
    if len(expected) != len(file_items):
        raise ValueError("model file inventory is invalid")
    observed_paths: list[str] = []
    observed: list[dict[str, object]] = []
    expected_by_path = {cast(str, item["path"]): item for item in expected}
    for path in sorted(component.rglob("*"), key=lambda item: item.as_posix()):
        entry = path.lstat()
        if path.is_symlink() or entry.st_mode & 0o222:
            raise ValueError("model file is not sealed")
        if stat.S_ISDIR(entry.st_mode):
            continue
        relative = path.relative_to(component).as_posix()
        expected_item = expected_by_path.get(relative)
        if not stat.S_ISREG(entry.st_mode) or expected_item is None:
            raise ValueError("model file inventory drifted")
        observed_paths.append(relative)
        observed.append(
            {
                "path": relative,
                "bytes": _positive(expected_item["bytes"], "model file bytes"),
                "sha256": _read_bound_regular_file(
                    path,
                    cast(int, expected_item["bytes"]),
                    _sha(expected_item["sha256"], "model file sha256"),
                ),
            }
        )
    if observed_paths != [cast(str, item["path"]) for item in expected]:
        raise ValueError("model file inventory drifted")
    return observed


def _read_bound_regular_file(path: Path, expected_size: int, expected_sha256: str | None) -> str:
    inventory = path.lstat()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_size != expected_size
            or _file_identity(opened) != _file_identity(inventory)
        ):
            raise ValueError("regular file identity drifted")
        digest = hashlib.sha256()
        actual = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, expected_size - actual + 1))
            if not chunk:
                break
            actual += len(chunk)
            if actual > expected_size:
                raise ValueError("regular file grew")
            digest.update(chunk)
        after_descriptor = os.fstat(descriptor)
        after_path = path.lstat()
        observed = digest.hexdigest()
        if (
            actual != expected_size
            or _file_identity(after_descriptor) != _file_identity(inventory)
            or _file_identity(after_path) != _file_identity(inventory)
            or (expected_sha256 is not None and observed != expected_sha256)
        ):
            raise ValueError("regular file identity drifted")
        return observed
    finally:
        os.close(descriptor)


def _file_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _load_runner_authority(config: Phase0RunnerConfig) -> _RunnerAuthority:
    package, package_sha = _load_receipt(config.package_receipt)
    model, model_sha = _load_receipt(config.model_receipt)
    startup, startup_sha = _load_receipt(config.startup_receipt)
    if (
        package_sha != _PACKAGE_RECEIPT_SHA256
        or model_sha != _MODEL_RECEIPT_SHA256
        or startup_sha != _STARTUP_RECEIPT_SHA256
    ):
        raise Phase0RunnerError("receipt_authority_invalid")
    if (
        startup.get("package_receipt_sha256") != package_sha
        or startup.get("model_receipt_sha256") != model_sha
    ):
        raise Phase0RunnerError("receipt_authority_invalid")
    network_raw = startup.get("network_isolation")
    runtime_raw = startup.get("runtime")
    network = cast(dict[str, object], network_raw) if isinstance(network_raw, dict) else None
    runtime = cast(dict[str, object], runtime_raw) if isinstance(runtime_raw, dict) else None
    if (
        network is None
        or network.get("canary") != "blocked"
        or runtime is None
        or runtime.get("candidate") != "paddleocr-vl-1.6-cpu-spike-v1"
        or runtime.get("surface") != "base"
        or runtime.get("python") != "3.13.12"
        or runtime.get("mke_wheel_sha256") != package.get("mke_wheel_sha256")
    ):
        raise Phase0RunnerError("receipt_authority_invalid")
    startup_providers_raw = startup.get("providers")
    startup_providers = (
        cast(list[object], startup_providers_raw)
        if isinstance(startup_providers_raw, list)
        else None
    )
    if (
        startup_providers is None
        or tuple(
            cast(dict[str, object], item).get("provider")
            for item in startup_providers
            if isinstance(item, dict)
        )
        != _PROVIDERS
        or any(
            not isinstance(item, dict) or cast(dict[str, object], item).get("status") != "passed"
            for item in startup_providers
        )
    ):
        raise Phase0RunnerError("receipt_authority_invalid")
    package_candidates_raw = package.get("candidates")
    if not isinstance(package_candidates_raw, list):
        raise Phase0RunnerError("receipt_authority_invalid")
    package_candidates = cast(list[object], package_candidates_raw)
    if (
        tuple(
            cast(dict[str, object], item).get("candidate")
            for item in package_candidates
            if isinstance(item, dict)
        )
        != _PACKAGE_CANDIDATES
    ):
        raise Phase0RunnerError("receipt_authority_invalid")
    package_bytes: dict[str, int] = {}
    package_versions: dict[str, str] | None = None
    for item in package_candidates:
        if not isinstance(item, dict):
            raise Phase0RunnerError("receipt_authority_invalid")
        candidate_item = cast(dict[str, object], item)
        if candidate_item.get("candidate") not in _PROVIDERS:
            raise Phase0RunnerError("receipt_authority_invalid")
        candidate = cast(str, candidate_item["candidate"])
        package_bytes[candidate] = _positive(candidate_item.get("download_bytes"), "package bytes")
        cells_raw = candidate_item.get("cells")
        cells = cast(list[object], cells_raw) if isinstance(cells_raw, list) else None
        if (
            cells is None
            or len(cells) != 8
            or any(
                not isinstance(cell, dict)
                or cast(dict[str, object], cell).get("result") != "passed"
                for cell in cells
            )
        ):
            raise Phase0RunnerError("receipt_authority_invalid")
        if candidate == "paddleocr-vl-1.6-cpu-spike-v1":
            selected = [
                cast(dict[str, object], cell)
                for cell in cells
                if isinstance(cell, dict)
                and cast(dict[str, object], cell).get("python") == "3.13.12"
                and cast(dict[str, object], cell).get("surface") == "base"
            ]
            if len(selected) != 1 or not isinstance(selected[0].get("package_versions"), dict):
                raise Phase0RunnerError("receipt_authority_invalid")
            raw_versions = cast(dict[object, object], selected[0]["package_versions"])
            if any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in raw_versions.items()
            ):
                raise Phase0RunnerError("receipt_authority_invalid")
            package_versions = cast(dict[str, str], raw_versions)
    wheel_filename, wheel_bytes, wheel_digest = _mke_wheel_authority(package_candidates)
    package_bytes["apple-vision-local-v1"] = wheel_bytes
    models_raw = model.get("models")
    if not isinstance(models_raw, list) or model.get("total_bytes") != 2_201_640_507:
        raise Phase0RunnerError("receipt_authority_invalid")
    models = cast(list[object], models_raw)
    if [
        cast(dict[str, object], item).get("candidate") for item in models if isinstance(item, dict)
    ] != [
        "ppocrv6-medium-cpu-spike-v1",
        "ppocrv6-medium-cpu-spike-v1",
        "paddleocr-vl-1.6-cpu-spike-v1",
        "paddleocr-vl-1.6-cpu-spike-v1",
    ]:
        raise Phase0RunnerError("receipt_authority_invalid")
    model_bytes = {provider: 0 for provider in _PROVIDERS}
    for item in models:
        if not isinstance(item, dict):
            raise Phase0RunnerError("receipt_authority_invalid")
        model_item = cast(dict[str, object], item)
        if model_item.get("candidate") not in _PROVIDERS:
            raise Phase0RunnerError("receipt_authority_invalid")
        if model_item.get("license") != "Apache-2.0":
            raise Phase0RunnerError("receipt_authority_invalid")
        candidate = cast(str, model_item["candidate"])
        model_bytes[candidate] += _positive(model_item.get("total_bytes"), "model bytes")
    assert runtime is not None
    installed_sha = runtime.get("installed_packages_sha256")
    wheel_sha = package.get("mke_wheel_sha256")
    tree_sha = model.get("tree_sha256")
    if (
        package_versions is None
        or installed_sha != _canonical_sha256(package_versions)
        or wheel_sha != wheel_digest
    ):
        raise Phase0RunnerError("receipt_authority_invalid")
    return _RunnerAuthority(
        receipts={
            "package_sha256": package_sha,
            "model_sha256": model_sha,
            "provider_startup_sha256": startup_sha,
        },
        model_tree_sha256=_sha(tree_sha, "model tree sha256"),
        installed_packages_sha256=_sha(installed_sha, "installed packages sha256"),
        mke_wheel_sha256=_sha(wheel_sha, "MKE wheel sha256"),
        package_bytes=package_bytes,
        model_bytes=model_bytes,
        package_versions=package_versions,
        mke_wheel_filename=wheel_filename,
        model_receipt=model,
    )


def _load_receipt(path: Path) -> tuple[dict[str, object], str]:
    try:
        encoded = path.read_bytes()
        if not encoded or len(encoded) > 8 * 1024 * 1024:
            raise ValueError
        raw: object = json.loads(encoded)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise Phase0RunnerError("receipt_authority_invalid") from error
    if not isinstance(raw, dict):
        raise Phase0RunnerError("receipt_authority_invalid")
    return cast(dict[str, object], raw), hashlib.sha256(encoded).hexdigest()


def _mke_wheel_authority(candidates: list[object]) -> tuple[str, int, str]:
    values: set[tuple[str, int, str]] = set()
    for raw in candidates:
        item = cast(dict[str, object], raw)
        distributions_raw = item.get("distributions")
        if not isinstance(distributions_raw, list):
            raise Phase0RunnerError("receipt_authority_invalid")
        distributions = cast(list[object], distributions_raw)
        mke = [
            cast(dict[str, object], value)
            for value in distributions
            if isinstance(value, dict)
            and str(cast(dict[str, object], value).get("filename", "")).startswith(
                "multimodal_knowledge_engine-"
            )
        ]
        if len(mke) != 1:
            raise Phase0RunnerError("receipt_authority_invalid")
        values.add(
            (
                _text(mke[0].get("filename"), "MKE wheel filename"),
                _positive(mke[0].get("bytes"), "MKE wheel bytes"),
                _sha(mke[0].get("sha256"), "MKE wheel sha256"),
            )
        )
    if len(values) != 1:
        raise Phase0RunnerError("receipt_authority_invalid")
    return next(iter(values))


def _render_common_pages(
    protocol: PdfOcrEvaluationProtocol, root: Path
) -> tuple[dict[str, PdfInspectionResult], dict[str, tuple[RenderedPage, ...]]]:
    root.mkdir(mode=0o700)
    inspections: dict[str, PdfInspectionResult] = {}
    renders: dict[str, tuple[RenderedPage, ...]] = {}
    for document in protocol.documents:
        path = protocol.resolve(document.fixture)
        inspection = inspect_pdf(path, EVALUATION_POLICY)
        inspections[document.document_id] = inspection
        renders[document.document_id] = render_ocr_pages(
            path, inspection, root / document.document_id, EVALUATION_POLICY
        )
    return inspections, renders


def _build_extractor_binding(
    protocol: PdfOcrEvaluationProtocol,
    renders: Mapping[str, tuple[RenderedPage, ...]],
    provider: str,
    authority: _RunnerAuthority,
) -> dict[str, object]:
    render_pages = [
        {
            "document_id": document.document_id,
            "page_number": page.page_number,
            "image_bytes": page.bytes,
            "image_sha256": page.sha256,
        }
        for document in protocol.documents
        for page in renders[document.document_id]
    ]
    render_pages.sort(
        key=lambda item: (cast(str, item["document_id"]), cast(int, item["page_number"]))
    )
    payload: dict[str, object] = {
        "schema": "mke.pdf_ocr_extractor_identity.v1",
        "protocol": {"id": _PROTOCOL_ID, "sha256": _PROTOCOL_SHA256},
        "fixtures": [
            {
                "document_id": document.document_id,
                "source_bytes": document.fixture.bytes,
                "source_sha256": document.fixture.sha256,
            }
            for document in sorted(protocol.documents, key=lambda item: item.document_id)
        ],
        "router": {
            "implementation_sha256": hashlib.sha256(
                Path(inspect_pdf.__code__.co_filename).read_bytes()
            ).hexdigest(),
            "policy": {
                "accepted_text_min_chars": EVALUATION_POLICY.accepted_text_min_chars,
                "accepted_text_max_replacement_ratio": {"numerator": 1, "denominator": 100},
                "ocr_text_max_chars": EVALUATION_POLICY.ocr_text_max_chars,
                "ocr_min_image_coverage": {"numerator": 4, "denominator": 5},
                "render_dpi": EVALUATION_POLICY.render_dpi,
                "max_pages": EVALUATION_POLICY.max_pages,
                "max_page_pixels": EVALUATION_POLICY.max_page_pixels,
                "max_total_rendered_pixels": EVALUATION_POLICY.max_total_rendered_pixels,
                "max_rendered_file_bytes": EVALUATION_POLICY.max_rendered_file_bytes,
                "max_total_rendered_bytes": EVALUATION_POLICY.max_total_rendered_bytes,
            },
        },
        "render": {
            "profile": _RENDER_PROFILE,
            "dpi": EVALUATION_POLICY.render_dpi,
            "pages": render_pages,
        },
        "provider": {"id": provider, "profile": _PROFILE},
        "model": {
            "receipt_sha256": authority.receipts["model_sha256"],
            "tree_sha256": authority.model_tree_sha256,
        },
        "package": {
            "receipt_sha256": authority.receipts["package_sha256"],
            "installed_packages_sha256": authority.installed_packages_sha256,
            "mke_wheel_sha256": authority.mke_wheel_sha256,
        },
        "normalization": {
            "implementation_sha256": hashlib.sha256(
                Path(__file__).with_name("pdf_ocr_provider.py").read_bytes()
            ).hexdigest(),
            "profile": _NORMALIZATION_PROFILE,
        },
    }
    return {"provider": provider, "fingerprint": extractor_fingerprint(payload), "payload": payload}


def _run_candidate(
    *,
    protocol: PdfOcrEvaluationProtocol,
    candidate: CandidateRunConfig,
    identity: Mapping[str, object],
    inspections: Mapping[str, PdfInspectionResult],
    renders: Mapping[str, tuple[RenderedPage, ...]],
    workspace: Path,
    authority: _RunnerAuthority,
    provider_runner: Callable[..., OcrEvalPageResult],
    peak_rss_reader: Callable[[], int] | None,
) -> dict[str, object]:
    render_inventory = [
        (document.document_id, page)
        for document in protocol.documents
        for page in renders[document.document_id]
    ]
    if candidate.command is None:
        outcome = CandidateOutcome(
            candidate.provider,
            _PROFILE,
            "unavailable",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (cast(str, candidate.unavailable_code),),
        )
        return {"outcome": outcome.to_dict(), "page_results": [], "publication_evidence_pages": []}
    started = time.monotonic_ns()
    rss_monitor = None if peak_rss_reader is not None else _ProcessTreeRssMonitor()
    if rss_monitor is not None:
        rss_monitor.start()
    recognized: dict[tuple[str, int], str | None] = {}
    page_results: list[dict[str, object]] = []
    try:
        for document_id, page in render_inventory:
            result = provider_runner(
                candidate.command,
                image_path=workspace / "renders" / document_id / page.relative_path.name,
                page_number=page.page_number,
                output_root=workspace
                / "providers"
                / candidate.provider
                / document_id
                / f"page-{page.page_number:04d}",
            )
            text = normalize_ocr_text(result.normalized_text)
            recognized[(document_id, page.page_number)] = text
            page_results.append(
                {
                    "document_id": document_id,
                    "page_number": page.page_number,
                    "image_bytes": page.bytes,
                    "image_sha256": page.sha256,
                    "normalized_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "nonempty": bool(text),
                }
            )
    except PdfOcrProviderError as error:
        peak_rss_bytes = _finish_peak_rss(rss_monitor, peak_rss_reader)
        elapsed = max(1, (time.monotonic_ns() - started) // 1_000_000)
        outcome = CandidateOutcome(
            candidate.provider,
            _PROFILE,
            "failed",
            None,
            None,
            None,
            None,
            None,
            elapsed,
            peak_rss_bytes,
            _candidate_temporary_bytes(workspace, candidate.provider),
            None,
            authority.model_bytes[candidate.provider],
            _candidate_package_bytes(candidate, authority),
            True,
            (error.problem,),
        )
        return {"outcome": outcome.to_dict(), "page_results": [], "publication_evidence_pages": []}
    except BaseException:
        _finish_peak_rss(rss_monitor, peak_rss_reader)
        raise
    peak_rss_bytes = _finish_peak_rss(rss_monitor, peak_rss_reader)
    proof = publish_and_verify(
        protocol=protocol,
        recognized_text=recognized,
        extractor_identity=identity,
        database=_candidate_database(workspace, candidate.provider),
        inspections=inspections,
    )
    references = [
        page.expected_ocr_text
        for document in protocol.documents
        for page in document.pages
        if page.expected_ocr_text is not None
    ]
    observed = [
        cast(str, recognized[(document.document_id, page.page_number)])
        for document in protocol.documents
        for page in document.pages
        if page.expected_ocr_text is not None
    ]
    character_rate = edit_rate("\n".join(references), "\n".join(observed), unit="codepoint")
    word_rate = edit_rate("\n".join(references), "\n".join(observed), unit="whitespace_token")
    elapsed = max(1, (time.monotonic_ns() - started) // 1_000_000)
    result_bytes = sum(len(value.encode()) for value in observed)
    status: Literal["passed", "failed"] = "passed" if not proof.failure_codes else "failed"
    outcome = CandidateOutcome(
        candidate.provider,
        _PROFILE,
        status,
        proof.route_accuracy,
        proof.query_accuracy,
        proof.evidence_ref_accuracy,
        character_rate,
        word_rate,
        elapsed,
        peak_rss_bytes,
        _candidate_temporary_bytes(workspace, candidate.provider),
        result_bytes,
        authority.model_bytes[candidate.provider],
        _candidate_package_bytes(candidate, authority),
        True,
        proof.failure_codes,
    )
    return {
        "outcome": outcome.to_dict(),
        "page_results": sorted(
            page_results,
            key=lambda item: (cast(str, item["document_id"]), cast(int, item["page_number"])),
        ),
        "publication_evidence_pages": [
            {"document_id": document_id, "page_number": page_number}
            for document_id, page_number in sorted(proof.publication_evidence_pages)
        ],
    }


def _candidate_outcome(value: Mapping[str, object]) -> CandidateOutcome:
    outcome = cast(dict[str, object], value["outcome"])
    return CandidateOutcome(
        provider=cast(str, outcome["provider"]),
        profile=cast(str, outcome["profile"]),
        status=cast(Literal["passed", "failed", "unavailable"], outcome["status"]),
        route_accuracy=_scorecard_rate(
            outcome["route_accuracy"], "route accuracy", allow_none=True
        ),
        query_accuracy=_scorecard_rate(
            outcome["query_accuracy"], "query accuracy", allow_none=True
        ),
        evidence_ref_accuracy=_scorecard_rate(
            outcome["evidence_ref_accuracy"], "evidence accuracy", allow_none=True
        ),
        character_error_rate=_scorecard_rate(
            outcome["character_error_rate"], "CER", allow_none=True
        ),
        word_error_rate=_scorecard_rate(outcome["word_error_rate"], "WER", allow_none=True),
        elapsed_ms=cast(int | None, outcome["elapsed_ms"]),
        peak_rss_bytes=cast(int | None, outcome["peak_rss_bytes"]),
        temporary_bytes=cast(int | None, outcome["temporary_bytes"]),
        result_bytes=cast(int | None, outcome["result_bytes"]),
        model_bytes=cast(int | None, outcome["model_bytes"]),
        package_bytes=cast(int | None, outcome["package_bytes"]),
        cold_start=cast(bool | None, outcome["cold_start"]),
        failure_codes=tuple(cast(list[str], outcome["failure_codes"])),
    )


def _finish_peak_rss(
    monitor: _ProcessTreeRssMonitor | None,
    reader: Callable[[], int] | None,
) -> int:
    if monitor is not None:
        return monitor.finish()
    if reader is None:
        raise Phase0RunnerError("resource_measurement_failed")
    return _valid_peak(reader())


def _candidate_database(workspace: Path, provider: str) -> Path:
    root = workspace / "databases"
    root.mkdir(mode=0o700, exist_ok=True)
    return root / f"{provider}.sqlite"


def _candidate_package_bytes(candidate: CandidateRunConfig, authority: _RunnerAuthority) -> int:
    if candidate.provider != "apple-vision-local-v1":
        return authority.package_bytes[candidate.provider]
    if candidate.command is None:
        raise Phase0RunnerError("candidate_inventory_invalid")
    if candidate.command.argv[0] != "/usr/bin/sandbox-exec":
        return authority.package_bytes[candidate.provider]
    if len(candidate.command.argv) < 4:
        raise Phase0RunnerError("candidate_inventory_invalid")
    executable = Path(candidate.command.argv[3])
    if executable.is_symlink() or not executable.is_file():
        raise Phase0RunnerError("candidate_inventory_invalid")
    return _positive(executable.stat().st_size, "Apple Vision executable bytes")


def _valid_peak(value: int) -> int:
    return value if type(value) is int and value > 0 else 1


def _tree_bytes(root: Path) -> int:
    return max(1, sum(path.stat().st_size for path in root.rglob("*") if path.is_file()))


def _candidate_temporary_bytes(workspace: Path, provider: str) -> int:
    database_bytes = sum(
        path.stat().st_size
        for path in (workspace / "databases").glob(f"{provider}.sqlite*")
        if path.is_file()
    )
    return max(
        1,
        _tree_bytes(workspace / "renders")
        + _tree_bytes(workspace / "providers" / provider)
        + database_bytes,
    )


def _write_owned_file(path: Path, value: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


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
    if protocol != {
        "id": _PROTOCOL_ID,
        "sha256": _PROTOCOL_SHA256,
        **_PROTOCOL_COUNTS,
    }:
        raise ValueError("scorecard protocol authority is invalid")
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
    identity_render_authority: dict[str, dict[tuple[str, int], tuple[int, str]]] = {}
    common_render: object | None = None
    common_package: object | None = None
    common_model: object | None = None
    for raw in identities:
        item = _closed(raw, {"provider", "fingerprint", "payload"}, "extractor binding")
        provider = _text(item["provider"], "extractor provider")
        identity = _closed(item["payload"], _IDENTITY_KEYS, "extractor identity")
        validate_extractor_identity(identity)
        if item["fingerprint"] != extractor_fingerprint(identity):
            raise ValueError("scorecard extractor fingerprint is invalid")
        if _closed(identity["provider"], {"id", "profile"}, "provider identity")["id"] != provider:
            raise ValueError("scorecard extractor provider is inconsistent")
        identity_protocol = _closed(identity["protocol"], {"id", "sha256"}, "protocol identity")
        if identity_protocol != {
            "id": protocol["id"],
            "sha256": protocol["sha256"],
        }:
            raise ValueError("scorecard identity protocol authority is inconsistent")
        fixtures = cast(list[object], identity["fixtures"])
        fixture_authority = tuple(
            (
                cast(str, cast(dict[str, object], item)["document_id"]),
                cast(int, cast(dict[str, object], item)["source_bytes"]),
                cast(str, cast(dict[str, object], item)["source_sha256"]),
            )
            for item in fixtures
        )
        if fixture_authority != _FIXTURE_AUTHORITY:
            raise ValueError("scorecard fixture authority is inconsistent")
        identity_providers.append(provider)
        render = _closed(identity["render"], {"profile", "dpi", "pages"}, "render identity")
        if render["profile"] != _RENDER_PROFILE:
            raise ValueError("scorecard render profile is invalid")
        if common_render is None:
            common_render = render
        elif render != common_render:
            raise ValueError("scorecard render comparison identity is inconsistent")
        identity_render_pages[provider] = [
            _render_page_key(page) for page in cast(list[object], render["pages"])
        ]
        identity_render_authority[provider] = {
            _render_page_key(page): (
                cast(int, cast(dict[str, object], page)["image_bytes"]),
                cast(str, cast(dict[str, object], page)["image_sha256"]),
            )
            for page in cast(list[object], render["pages"])
        }
        identity_provider = cast(dict[str, object], identity["provider"])
        if identity_provider["profile"] != _PROFILE:
            raise ValueError("scorecard provider profile is invalid")
        package = identity["package"]
        model = identity["model"]
        if common_package is None:
            common_package = package
            common_model = model
        elif package != common_package or model != common_model:
            raise ValueError("scorecard package or model identity is inconsistent")
        if cast(dict[str, object], package)["receipt_sha256"] != receipts["package_sha256"]:
            raise ValueError("scorecard package receipt binding is inconsistent")
        if cast(dict[str, object], model)["receipt_sha256"] != receipts["model_sha256"]:
            raise ValueError("scorecard model receipt binding is inconsistent")
        normalization = cast(dict[str, object], identity["normalization"])
        if normalization["profile"] != _NORMALIZATION_PROFILE:
            raise ValueError("scorecard normalization profile is invalid")
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
        if outcome["profile"] != _PROFILE:
            raise ValueError("candidate profile is invalid")
        if outcome["status"] not in {"passed", "failed", "unavailable"}:
            raise ValueError("candidate status is invalid")
        status = cast(Literal["passed", "failed", "unavailable"], outcome["status"])
        accuracy_rates = {
            key: _scorecard_rate(outcome[key], key, allow_none=status != "passed")
            for key in ("route_accuracy", "query_accuracy", "evidence_ref_accuracy")
        }
        if any(
            rate is not None and rate.numerator > rate.denominator
            for rate in accuracy_rates.values()
        ):
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
        candidate_outcome = CandidateOutcome(
            provider=provider,
            profile=cast(str, outcome["profile"]),
            status=status,
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
        if status == "passed" and (failures or not _passes_hard_gates(candidate_outcome)):
            raise ValueError("passed candidate does not satisfy complete hard gates")
        if status != "passed" and not failures:
            raise ValueError("nonpassing candidate requires a stable failure code")
        candidate_outcomes.append(candidate_outcome)
        page_keys, all_nonempty = _validate_page_inventory(
            candidate["page_results"],
            result=True,
            allow_empty=status != "passed",
            render_authority=identity_render_authority[provider],
        )
        publication_keys, _ = _validate_page_inventory(
            candidate["publication_evidence_pages"],
            result=False,
            allow_empty=status != "passed",
        )
        if page_keys:
            if page_keys != identity_render_pages[provider]:
                raise ValueError("candidate page results do not match rendered pages")
            if tuple(publication_keys) != _PUBLICATION_PAGE_AUTHORITY:
                raise ValueError("candidate Publication page authority is invalid")
        elif publication_keys:
            raise ValueError("candidate Publication page authority is invalid")
        if status == "passed" and not all_nonempty:
            raise ValueError("passed candidate has an empty OCR page")
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
        if decision["selected_profile"] != _PROFILE:
            raise ValueError("selected profile is invalid")
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
        encoded = (
            json.dumps(
                value,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
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
    value: object,
    *,
    result: bool,
    allow_empty: bool = False,
    render_authority: Mapping[tuple[str, int], tuple[int, str]] | None = None,
) -> tuple[list[tuple[str, int]], bool]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError("scorecard page inventory is invalid")
    pages = cast(list[object], value)
    keys: list[tuple[str, int]] = []
    all_nonempty = True
    expected = {"document_id", "page_number"}
    if result:
        expected |= {
            "image_bytes",
            "image_sha256",
            "normalized_text_sha256",
            "nonempty",
        }
    for raw in pages:
        page = _closed(raw, expected, "scorecard page")
        keys.append(
            (
                _text(page["document_id"], "scorecard document id"),
                _positive(page["page_number"], "scorecard page number"),
            )
        )
        if result:
            image_authority = (
                _positive(page["image_bytes"], "scorecard image bytes"),
                _sha(page["image_sha256"], "scorecard image sha256"),
            )
            if render_authority is None or render_authority.get(keys[-1]) != image_authority:
                raise ValueError("candidate page render authority is inconsistent")
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
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 256
        or _SAFE_TEXT_RE.fullmatch(value) is None
        or value.endswith(".local")
        or _TIMESTAMP_RE.fullmatch(value) is not None
        or "://" in value
        or value.startswith(("/", "\\"))
        or re.match(r"[A-Za-z]:[\\/]", value) is not None
        or any(ord(character) < 32 for character in value)
    ):
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
