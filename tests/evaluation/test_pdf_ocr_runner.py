from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

import mke.evaluation.pdf_ocr_runner as runner
from mke.evaluation.pdf_ocr_protocol import load_pdf_ocr_evaluation_protocol
from mke.evaluation.pdf_ocr_provider import (
    OcrEvalLine,
    OcrEvalPageResult,
    PdfOcrProviderError,
    ProviderCommand,
)
from mke.evaluation.pdf_ocr_runner import (
    CandidateOutcome,
    CandidateRunConfig,
    ExactRate,
    ExtractorIdentityError,
    Phase0RunnerConfig,
    canonical_extractor_identity_bytes,
    canonical_scorecard_bytes,
    decide,
    edit_rate,
    extractor_fingerprint,
    publish_and_verify,
    run_phase0_scorecard,
    validate_extractor_identity,
    validate_scorecard,
)

PROTOCOL_PATH = Path("tests/fixtures/pdf-ocr-phase0-v1/protocol.json")
SCORECARD_PATH = Path("benchmarks/ocr/phase0-scorecard.json")
SHA = "a" * 64
SCORECARD_SHA256 = "9f646a6e48f2d2d17c266036b4e331cecba5240c009257d65d4131e25f29881c"
PACKAGE_RECEIPT = Path("benchmarks/ocr/candidate-environments.json")
MODEL_RECEIPT = Path("benchmarks/ocr/model-artifacts.json")
STARTUP_RECEIPT = Path("benchmarks/ocr/provider-startup.json")


def _identity() -> dict[str, object]:
    return {
        "schema": "mke.pdf_ocr_extractor_identity.v1",
        "protocol": {"id": "pdf-ocr-phase0-v1", "sha256": SHA},
        "fixtures": [
            {"document_id": "a", "source_bytes": 1, "source_sha256": SHA},
            {"document_id": "b", "source_bytes": 2, "source_sha256": "b" * 64},
        ],
        "router": {
            "implementation_sha256": SHA,
            "policy": {
                "accepted_text_min_chars": 32,
                "accepted_text_max_replacement_ratio": {"numerator": 1, "denominator": 100},
                "ocr_text_max_chars": 8,
                "ocr_min_image_coverage": {"numerator": 4, "denominator": 5},
                "render_dpi": 200,
                "max_pages": 32,
                "max_page_pixels": 25_000_000,
                "max_total_rendered_pixels": 100_000_000,
                "max_rendered_file_bytes": 32 * 1024 * 1024,
                "max_total_rendered_bytes": 96 * 1024 * 1024,
            },
        },
        "render": {
            "profile": "phase0-200dpi-png-v1",
            "dpi": 200,
            "pages": [
                {
                    "document_id": "a",
                    "page_number": 1,
                    "image_bytes": 10,
                    "image_sha256": SHA,
                },
                {
                    "document_id": "b",
                    "page_number": 2,
                    "image_bytes": 20,
                    "image_sha256": "b" * 64,
                },
            ],
        },
        "provider": {"id": "provider-v1", "profile": "profile-v1"},
        "model": {"receipt_sha256": SHA, "tree_sha256": "b" * 64},
        "package": {
            "receipt_sha256": SHA,
            "installed_packages_sha256": "b" * 64,
            "mke_wheel_sha256": "c" * 64,
        },
        "normalization": {"implementation_sha256": SHA, "profile": "unicode-nfc-lines-v1"},
    }


def _outcome(
    provider: str,
    *,
    cer: ExactRate | None = None,
    peak_rss_bytes: int = 100,
    failures: tuple[str, ...] = (),
) -> CandidateOutcome:
    return CandidateOutcome(
        provider=provider,
        profile="profile-v1",
        status="passed" if not failures else "failed",
        route_accuracy=ExactRate(10, 10),
        query_accuracy=ExactRate(3, 3),
        evidence_ref_accuracy=ExactRate(3, 3),
        character_error_rate=ExactRate(0, 10) if cer is None else cer,
        word_error_rate=ExactRate(0, 3),
        elapsed_ms=100,
        peak_rss_bytes=peak_rss_bytes,
        temporary_bytes=10,
        result_bytes=10,
        model_bytes=20,
        package_bytes=30,
        cold_start=True,
        failure_codes=failures,
    )


def _scorecard() -> dict[str, object]:
    return json.loads(SCORECARD_PATH.read_bytes())


def _controller_config(
    tmp_path: Path, *, unavailable: frozenset[str] = frozenset()
) -> Phase0RunnerConfig:
    candidates = tuple(
        CandidateRunConfig(
            provider=provider,
            command=(
                None
                if provider in unavailable
                else ProviderCommand(
                    argv=("provider", "{input}", "{output}", "{page_number}"),
                    provider=provider,
                    profile="phase0-200dpi-plain-text-v1",
                )
            ),
            unavailable_code=("provider_unavailable" if provider in unavailable else None),
        )
        for provider in (
            "apple-vision-local-v1",
            "paddleocr-vl-1.6-cpu-spike-v1",
            "ppocrv6-medium-cpu-spike-v1",
        )
    )
    return Phase0RunnerConfig(
        protocol=PROTOCOL_PATH,
        package_receipt=PACKAGE_RECEIPT,
        model_receipt=MODEL_RECEIPT,
        startup_receipt=STARTUP_RECEIPT,
        workspace=tmp_path / "owned-workspace",
        output=tmp_path / "phase0-scorecard.json",
        candidates=candidates,
    )


def _fake_provider(
    command: ProviderCommand,
    *,
    image_path: Path,
    page_number: int,
    output_root: Path,
    **_: object,
) -> OcrEvalPageResult:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    document_id = image_path.parent.name
    expected = next(
        page.expected_ocr_text
        for document in protocol.documents
        if document.document_id == document_id
        for page in document.pages
        if page.page_number == page_number
    )
    output_root.mkdir(parents=True)
    (output_root / "result.json").write_text("{}", encoding="utf-8")
    return OcrEvalPageResult(
        schema="mke.pdf_ocr_page_result.v1",
        provider=command.provider,
        profile=command.profile,
        page_number=page_number,
        lines=(OcrEvalLine(text=expected or "", confidence=1.0, box=(0.0, 0.0, 1.0, 1.0)),),
        normalized_text=expected or "",
        duration_ms=1,
    )


def test_tracked_controller_runs_candidates_serially_with_common_render_and_atomic_output(
    tmp_path: Path,
) -> None:
    config = _controller_config(tmp_path)
    calls: list[tuple[str, str, int]] = []

    def provider(*args: object, **kwargs: object) -> OcrEvalPageResult:
        command = args[0]
        image_path = kwargs["image_path"]
        page_number = kwargs["page_number"]
        assert isinstance(command, ProviderCommand)
        assert isinstance(image_path, Path)
        assert isinstance(page_number, int)
        calls.append((command.provider, image_path.parent.name, page_number))
        return _fake_provider(command, **kwargs)  # type: ignore[arg-type]

    payload = run_phase0_scorecard(
        config,
        provider_runner=provider,
        peak_rss_reader=lambda: 1024,
    )

    assert payload["decision"] == {
        "status": "go",
        "selected_provider": "apple-vision-local-v1",
        "selected_profile": "phase0-200dpi-plain-text-v1",
    }
    assert [item[0] for item in calls] == [
        provider for provider in runner._PROVIDERS for _ in range(4)
    ]
    assert len({(item[1], item[2]) for item in calls}) == 4
    assert config.output.read_bytes() == canonical_scorecard_bytes(payload)
    assert not config.workspace.exists()
    assert not list(tmp_path.glob(".phase0-scorecard.json.*.tmp"))


def test_tracked_controller_records_unavailable_and_failure_without_fabricated_measurements(
    tmp_path: Path,
) -> None:
    unavailable = frozenset({"apple-vision-local-v1"})
    config = _controller_config(tmp_path, unavailable=unavailable)

    def provider(command: ProviderCommand, **kwargs: object) -> OcrEvalPageResult:
        if command.provider == "paddleocr-vl-1.6-cpu-spike-v1":
            raise PdfOcrProviderError(
                problem="pdf_ocr_process_failed",
                cause="PDF OCR process failed",
                next_step="inspect_pdf_ocr_run",
                provider=command.provider,
            )
        return _fake_provider(command, **kwargs)  # type: ignore[arg-type]

    payload = run_phase0_scorecard(
        config,
        provider_runner=provider,
        peak_rss_reader=lambda: 1024,
    )

    outcomes = {item["outcome"]["provider"]: item["outcome"] for item in payload["candidates"]}
    unavailable_outcome = outcomes["apple-vision-local-v1"]
    assert unavailable_outcome["status"] == "unavailable"
    assert unavailable_outcome["failure_codes"] == ["provider_unavailable"]
    assert unavailable_outcome["elapsed_ms"] is None
    failed = outcomes["paddleocr-vl-1.6-cpu-spike-v1"]
    assert failed["status"] == "failed"
    assert failed["failure_codes"] == ["pdf_ocr_process_failed"]
    assert payload["decision"]["selected_provider"] == "ppocrv6-medium-cpu-spike-v1"


def test_tracked_controller_emits_deterministic_valid_negative_no_go(tmp_path: Path) -> None:
    config = _controller_config(tmp_path, unavailable=frozenset(runner._PROVIDERS))
    payload = run_phase0_scorecard(config, provider_runner=_fake_provider)
    assert payload["decision"] == {
        "status": "no_go",
        "selected_provider": None,
        "selected_profile": None,
    }
    validate_scorecard(payload)


@pytest.mark.parametrize("receipt_name", ["package_receipt", "model_receipt", "startup_receipt"])
def test_tracked_controller_rejects_committed_receipt_drift_before_workspace(
    tmp_path: Path, receipt_name: str
) -> None:
    config = _controller_config(tmp_path)
    source = getattr(config, receipt_name)
    changed = tmp_path / source.name
    changed.write_bytes(source.read_bytes() + b" ")
    config = replace(config, **{receipt_name: changed})
    with pytest.raises(runner.Phase0RunnerError, match="receipt_authority_invalid"):
        run_phase0_scorecard(config, provider_runner=_fake_provider)
    assert not config.workspace.exists()


def test_tracked_controller_preserves_prior_output_when_cleanup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _controller_config(tmp_path)
    config.output.write_bytes(b"prior authority\n")
    real_rmtree = runner.shutil.rmtree

    def fail_owned_cleanup(path: Path, *args: object, **kwargs: object) -> None:
        if Path(path) == config.workspace:
            raise OSError("controlled cleanup failure")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(runner.shutil, "rmtree", fail_owned_cleanup)
    with pytest.raises(runner.Phase0RunnerError, match="cleanup_failed"):
        run_phase0_scorecard(config, provider_runner=_fake_provider, peak_rss_reader=lambda: 1024)
    assert config.output.read_bytes() == b"prior authority\n"


def test_tracked_controller_preserves_prior_output_when_atomic_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _controller_config(tmp_path)
    config.output.write_bytes(b"prior authority\n")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("controlled replace failure")

    monkeypatch.setattr(runner.os, "replace", fail_replace)
    with pytest.raises(runner.Phase0RunnerError, match="scorecard_publication_failed"):
        run_phase0_scorecard(
            config,
            provider_runner=_fake_provider,
            peak_rss_reader=lambda: 1024,
        )
    assert config.output.read_bytes() == b"prior authority\n"
    assert not config.workspace.exists()
    assert not list(tmp_path.glob(".phase0-scorecard.json.*.tmp"))


def test_tracked_controller_cleans_owned_state_after_provider_failure(tmp_path: Path) -> None:
    config = _controller_config(tmp_path)

    def fail_provider(command: ProviderCommand, **_: object) -> OcrEvalPageResult:
        raise PdfOcrProviderError(
            problem="pdf_ocr_process_failed",
            cause="PDF OCR process failed",
            next_step="inspect_pdf_ocr_run",
            provider=command.provider,
        )

    payload = run_phase0_scorecard(
        config,
        provider_runner=fail_provider,
        peak_rss_reader=lambda: 1024,
    )
    assert payload["decision"]["status"] == "no_go"
    assert not config.workspace.exists()


def test_edit_rates_use_unicode_code_points_and_whitespace_tokens() -> None:
    assert edit_rate("café", "cafe", unit="codepoint") == ExactRate(1, 4)
    assert edit_rate("café", "cafe\u0301", unit="codepoint") == ExactRate(0, 4)
    assert edit_rate("alpha  beta\r\ngamma", "alpha beta\ngamma", unit="codepoint") == ExactRate(
        0, 16
    )
    assert edit_rate("alpha beta", "alpha gamma beta", unit="whitespace_token") == ExactRate(1, 2)
    assert edit_rate("海燕四十二号", "海燕四十号", unit="codepoint") == ExactRate(1, 6)


def test_extractor_identity_is_closed_and_byte_deterministic() -> None:
    payload = _identity()
    validate_extractor_identity(payload)
    expected = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    assert canonical_extractor_identity_bytes(payload) == expected
    assert extractor_fingerprint(payload) == (
        "pdf-ocr-eval-v1:" + hashlib.sha256(expected).hexdigest()
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update({"extra": True}),
        lambda value: value.pop("model"),
        lambda value: value["fixtures"].reverse(),  # type: ignore[union-attr]
        lambda value: value["fixtures"].append(copy.deepcopy(value["fixtures"][0])),  # type: ignore[index,union-attr]
        lambda value: value["render"]["pages"].reverse(),  # type: ignore[index,union-attr]
        lambda value: value["router"]["policy"].update(  # type: ignore[index,union-attr]
            {"max_pages": True}
        ),
        lambda value: value["router"]["policy"].update(  # type: ignore[index,union-attr]
            {
                "ocr_min_image_coverage": {
                    "numerator": math.nan,
                    "denominator": 1,
                }
            }
        ),
    ],
)
def test_extractor_identity_rejects_schema_order_and_type_drift(mutation: object) -> None:
    payload = _identity()
    mutation(payload)  # type: ignore[operator]
    with pytest.raises(ExtractorIdentityError):
        validate_extractor_identity(payload)


def test_every_authority_leaf_changes_fingerprint() -> None:
    original = _identity()
    original_fingerprint = extractor_fingerprint(original)
    for path in _leaf_paths(original):
        changed = copy.deepcopy(original)
        parent = _at_path(changed, path[:-1])
        key = path[-1]
        value = parent[key]
        if isinstance(value, str):
            parent[key] = ("f" * 64) if len(value) == 64 else value + "-changed"
        elif type(value) is int:
            parent[key] = value + 1
        else:
            raise AssertionError(f"unsupported identity leaf at {path}")
        try:
            assert extractor_fingerprint(changed) != original_fingerprint
        except ExtractorIdentityError:
            pass


def test_every_nested_identity_object_rejects_missing_and_extra_keys() -> None:
    original = _identity()
    for path in _mapping_paths(original):
        for operation in ("missing", "extra"):
            changed = copy.deepcopy(original)
            target = _at_path(changed, path)
            if operation == "missing":
                target.pop(next(iter(target)))
            else:
                target["unexpected"] = True
            with pytest.raises(ExtractorIdentityError):
                validate_extractor_identity(changed)


def test_every_identity_integer_rejects_boolean_and_non_finite_values() -> None:
    original = _identity()
    integer_paths = [
        path
        for path in _leaf_paths(original)
        if type(_at_path(original, path[:-1])[path[-1]]) is int
    ]
    for replacement in (True, math.nan):
        for path in integer_paths:
            changed = copy.deepcopy(original)
            _at_path(changed, path[:-1])[path[-1]] = replacement
            with pytest.raises(ExtractorIdentityError):
                validate_extractor_identity(changed)


def test_decision_requires_every_hard_gate_and_uses_deterministic_tiebreaks() -> None:
    failed = _outcome("a-provider", cer=ExactRate(0, 10), failures=("evidence_ref_mismatch",))
    slower = _outcome("z-provider", cer=ExactRate(1, 10), peak_rss_bytes=200)
    winner = _outcome("a-provider", cer=ExactRate(1, 10), peak_rss_bytes=100)

    decision = decide((failed, slower, winner))

    assert decision.status == "go"
    assert decision.selected_provider == "a-provider"
    assert decision.selected_profile == "profile-v1"
    assert decision.outcomes == (failed, slower, winner)
    assert decide((failed,)).status == "no_go"
    assert decide((failed,)).selected_provider is None


def test_disposable_publication_uses_search_ask_and_exact_evidence_refs(tmp_path: Path) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    recognized = {
        (document.document_id, page.page_number): page.expected_ocr_text
        for document in protocol.documents
        for page in document.pages
        if page.expected_ocr_text is not None
    }

    proof = publish_and_verify(
        protocol=protocol,
        recognized_text=recognized,
        extractor_identity=_identity(),
        database=tmp_path / "evaluation.sqlite",
    )

    assert proof.route_accuracy == ExactRate(9, 9)
    assert proof.query_accuracy == ExactRate(3, 3)
    assert proof.evidence_ref_accuracy == ExactRate(3, 3)
    assert proof.publication_evidence_pages == frozenset(
        {
            ("english-scan", 1),
            ("chinese-scan", 1),
            ("mixed-prose", 1),
            ("mixed-prose", 2),
            ("routing-adversarial", 5),
        }
    )
    assert proof.publication_evidence_pages.isdisjoint(
        {("routing-adversarial", page) for page in (1, 2, 3, 4)}
    )
    assert proof.failure_codes == ()


@pytest.mark.parametrize("surface", ["search", "ask"])
@pytest.mark.parametrize(
    ("field", "replacement", "failure_code"),
    [
        ("schema_version", "mke.evidence_ref.v2", "evidence_ref_mismatch"),
        ("evidence_id", "ev_" + "f" * 32, "evidence_ref_mismatch"),
        ("source_id", "src_" + "f" * 32, "evidence_ref_mismatch"),
        ("content_fingerprint", "sha256:" + "f" * 64, "evidence_ref_mismatch"),
        ("publication_id", "pub_" + "f" * 32, "evidence_ref_mismatch"),
        ("publication_revision", 99, "evidence_ref_mismatch"),
        ("run_id", "run_" + "f" * 32, "evidence_ref_mismatch"),
        ("locator_kind", {"kind": "timestamp_ms"}, "evidence_ref_mismatch"),
        ("locator_start", {"start": 2}, "evidence_ref_mismatch"),
        ("locator_end", {"end": 2}, "evidence_ref_mismatch"),
        ("text", "wrong normalized payload", "payload_truth_mismatch"),
    ],
)
def test_product_proof_rejects_every_portable_evidence_leaf_and_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
    field: str,
    replacement: object,
    failure_code: str,
) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    recognized = {
        (document.document_id, page.page_number): page.expected_ocr_text
        for document in protocol.documents
        for page in document.pages
        if page.expected_ocr_text is not None
    }
    function_name = f"{surface}_library_v1"
    real_function = getattr(runner, function_name)
    expected_text_by_query = {
        query.text: next(
            page.expected_ocr_text or page.expected_text_layer_text
            for document in protocol.documents
            if document.document_id == query.expected_document_id
            for page in document.pages
            if page.page_number == query.expected_page
        )
        for query in protocol.queries
    }

    def mutate_response(config: object, query: str) -> object:
        response = real_function(config, query)
        root = response.root
        collection_name = "results" if surface == "search" else "evidence"
        items = list(getattr(root, collection_name))
        target = next(
            index for index, item in enumerate(items) if item.text == expected_text_by_query[query]
        )
        if field.startswith("locator_"):
            changed = items[target].model_copy(
                update={"locator": items[target].locator.model_copy(update=replacement)}
            )
        else:
            changed = items[target].model_copy(update={field: replacement})
        items[target] = changed
        changed_root = root.model_copy(update={collection_name: items})
        return response.model_copy(update={"root": changed_root})

    monkeypatch.setattr(runner, function_name, mutate_response)
    proof = publish_and_verify(
        protocol=protocol,
        recognized_text=recognized,
        extractor_identity=_identity(),
        database=tmp_path / "evaluation.sqlite",
    )

    assert failure_code in proof.failure_codes
    assert proof.evidence_ref_accuracy != ExactRate(3, 3)


def test_missing_ocr_text_fails_closed_before_product_success(tmp_path: Path) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    proof = publish_and_verify(
        protocol=protocol,
        recognized_text={},
        extractor_identity=_identity(),
        database=tmp_path / "evaluation.sqlite",
    )
    assert "provider_output_incomplete" in proof.failure_codes
    assert proof.query_accuracy != ExactRate(3, 3)


def test_route_truth_mismatch_fails_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    recognized = {
        (document.document_id, page.page_number): page.expected_ocr_text
        for document in protocol.documents
        for page in document.pages
        if page.expected_ocr_text is not None
    }
    real_inspect = runner.inspect_pdf

    def inspect_with_mismatch(path: Path, policy: object) -> object:
        inspection = real_inspect(path, policy)  # type: ignore[arg-type]
        if path.name != "english-scan.pdf":
            return inspection
        first = replace(inspection.decisions[0], route="text_layer_accepted")
        return replace(inspection, decisions=(first, *inspection.decisions[1:]))

    monkeypatch.setattr(runner, "inspect_pdf", inspect_with_mismatch)
    proof = publish_and_verify(
        protocol=protocol,
        recognized_text=recognized,
        extractor_identity=_identity(),
        database=tmp_path / "evaluation.sqlite",
    )
    assert proof.route_accuracy == ExactRate(8, 9)
    assert proof.query_accuracy == ExactRate(0, 3)
    assert proof.failure_codes == ("route_truth_mismatch",)
    assert not (tmp_path / "evaluation.sqlite").exists()


def test_scorecard_serialization_is_stable_finite_and_public_neutral() -> None:
    payload = _scorecard()
    encoded = canonical_scorecard_bytes(payload)
    assert encoded.endswith(b"\n")
    assert b"NaN" not in encoded
    assert b"/Users/" not in encoded
    assert canonical_scorecard_bytes(json.loads(encoded)) == encoded


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update({"extra": True}),
        lambda value: value["receipts"].update({"package_sha256": "bad"}),  # type: ignore[union-attr]
        lambda value: value["candidates"].append(copy.deepcopy(value["candidates"][0])),  # type: ignore[index,union-attr]
        lambda value: value["extractor_identities"][0].update(  # type: ignore[index,union-attr]
            {"fingerprint": "pdf-ocr-eval-v1:" + "f" * 64}
        ),
        lambda value: value["candidates"][0]["outcome"].update(  # type: ignore[index,union-attr]
            {"elapsed_ms": True}
        ),
        lambda value: value["candidates"][0]["page_results"].reverse(),  # type: ignore[index,union-attr]
        lambda value: value.update(
            {
                "decision": {
                    "status": "no_go",
                    "selected_provider": None,
                    "selected_profile": None,
                }
            }
        ),
    ],
)
def test_scorecard_schema_is_closed_and_cross_bound(mutation: object) -> None:
    payload = _scorecard()
    mutation(payload)  # type: ignore[operator]
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize(
    "measurement",
    [
        "elapsed_ms",
        "peak_rss_bytes",
        "temporary_bytes",
        "result_bytes",
        "model_bytes",
        "package_bytes",
        "cold_start",
    ],
)
def test_passed_candidate_requires_every_complete_measurement(measurement: str) -> None:
    payload = _scorecard()
    selected = payload["candidates"][2]["outcome"]  # type: ignore[index]
    selected[measurement] = None
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize(
    "measurement",
    [
        "elapsed_ms",
        "peak_rss_bytes",
        "temporary_bytes",
        "result_bytes",
        "model_bytes",
        "package_bytes",
    ],
)
def test_passed_candidate_rejects_boolean_numeric_measurements(measurement: str) -> None:
    payload = _scorecard()
    payload["candidates"][2]["outcome"][measurement] = True  # type: ignore[index]
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize("status", ["failed", "unavailable"])
def test_nonpassing_candidate_may_preserve_unknown_measurements(status: str) -> None:
    payload = _scorecard()
    outcome = payload["candidates"][0]["outcome"]  # type: ignore[index]
    outcome.update(
        {
            "status": status,
            "elapsed_ms": None,
            "peak_rss_bytes": None,
            "temporary_bytes": None,
            "result_bytes": None,
            "model_bytes": None,
            "package_bytes": None,
            "cold_start": None,
            "failure_codes": [f"provider_{status}"],
        }
    )
    payload["candidates"][0]["page_results"] = []  # type: ignore[index]
    payload["candidates"][0]["publication_evidence_pages"] = []  # type: ignore[index]
    validate_scorecard(payload)


def test_scorecard_rejects_top_level_protocol_authority_drift() -> None:
    payload = _scorecard()
    payload["protocol"]["sha256"] = "f" * 64  # type: ignore[index]
    with pytest.raises(ValueError):
        validate_scorecard(payload)


def test_scorecard_rejects_identity_protocol_authority_drift() -> None:
    payload = _scorecard()
    binding = payload["extractor_identities"][1]  # type: ignore[index]
    binding["payload"]["protocol"]["sha256"] = "f" * 64
    binding["fingerprint"] = extractor_fingerprint(binding["payload"])
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize("authority", ["fixtures", "render"])
def test_scorecard_rejects_cross_provider_comparison_identity_drift(authority: str) -> None:
    payload = _scorecard()
    binding = payload["extractor_identities"][1]  # type: ignore[index]
    if authority == "fixtures":
        binding["payload"]["fixtures"][0]["source_sha256"] = "f" * 64
    else:
        binding["payload"]["render"]["pages"][0]["image_sha256"] = "f" * 64
    binding["fingerprint"] = extractor_fingerprint(binding["payload"])
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize("mutation", ["blank", "missing", "extra"])
def test_scorecard_rejects_publication_page_inventory_drift(mutation: str) -> None:
    payload = _scorecard()
    for candidate in payload["candidates"]:  # type: ignore[union-attr]
        pages = candidate["publication_evidence_pages"]
        if mutation == "blank":
            pages[-1] = {"document_id": "routing-adversarial", "page_number": 1}
        elif mutation == "missing":
            pages.pop()
        else:
            pages.append({"document_id": "routing-adversarial", "page_number": 1})
    with pytest.raises(ValueError):
        validate_scorecard(payload)


def test_scorecard_rejects_internal_receipt_leaf_drift() -> None:
    payload = _scorecard()
    binding = payload["extractor_identities"][1]  # type: ignore[index]
    binding["payload"]["package"]["receipt_sha256"] = "f" * 64
    binding["fingerprint"] = extractor_fingerprint(binding["payload"])
    with pytest.raises(ValueError):
        validate_scorecard(payload)


def test_scorecard_rejects_candidate_page_render_identity_drift() -> None:
    payload = _scorecard()
    payload["candidates"][1]["page_results"][0]["image_sha256"] = "f" * 64  # type: ignore[index]
    with pytest.raises(ValueError):
        validate_scorecard(payload)


@pytest.mark.parametrize(
    "unsafe",
    [
        "/private/tmp/operator-cache",
        "/tmp/operator-cache",
        r"C:\\operator\\cache",
        r"\\\\host\\share",
        "file:///tmp/operator-cache",
        "operator-host.local",
        "2026-07-15T12:34:56Z",
    ],
)
def test_scorecard_rejects_non_neutral_profile_values(unsafe: str) -> None:
    payload = _scorecard()
    for binding, candidate in zip(
        payload["extractor_identities"],
        payload["candidates"],
        strict=True,  # type: ignore[arg-type]
    ):
        binding["payload"]["provider"]["profile"] = unsafe
        candidate["outcome"]["profile"] = unsafe
    payload["decision"]["selected_profile"] = unsafe  # type: ignore[index]
    with pytest.raises(ValueError):
        canonical_scorecard_bytes(payload)


def test_committed_scorecard_is_canonical_closed_and_frozen() -> None:
    encoded = SCORECARD_PATH.read_bytes()
    payload = json.loads(encoded)
    validate_scorecard(payload)
    assert canonical_scorecard_bytes(payload) == encoded
    assert hashlib.sha256(encoded).hexdigest() == SCORECARD_SHA256
    assert payload["decision"] == {
        "status": "go",
        "selected_provider": "ppocrv6-medium-cpu-spike-v1",
        "selected_profile": "phase0-200dpi-plain-text-v1",
    }
    receipt_paths = {
        "package_sha256": Path("benchmarks/ocr/candidate-environments.json"),
        "model_sha256": Path("benchmarks/ocr/model-artifacts.json"),
        "provider_startup_sha256": Path("benchmarks/ocr/provider-startup.json"),
    }
    assert payload["receipts"] == {
        key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in receipt_paths.items()
    }
    startup = json.loads(receipt_paths["provider_startup_sha256"].read_bytes())
    model = json.loads(receipt_paths["model_sha256"].read_bytes())
    for binding in payload["extractor_identities"]:
        identity = binding["payload"]
        assert identity["package"]["receipt_sha256"] == startup["package_receipt_sha256"]
        assert identity["package"]["mke_wheel_sha256"] == startup["runtime"]["mke_wheel_sha256"]
        assert (
            identity["package"]["installed_packages_sha256"]
            == startup["runtime"]["installed_packages_sha256"]
        )
        assert identity["model"]["receipt_sha256"] == startup["model_receipt_sha256"]
        assert identity["model"]["tree_sha256"] == model["tree_sha256"]


def _leaf_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        return [leaf for key, item in value.items() for leaf in _leaf_paths(item, (*path, key))]
    if isinstance(value, list):
        return [
            leaf for index, item in enumerate(value) for leaf in _leaf_paths(item, (*path, index))
        ]
    return [path]


def _mapping_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    paths = [path] if isinstance(value, dict) else []
    if isinstance(value, dict):
        for key, item in value.items():
            paths.extend(_mapping_paths(item, (*path, key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_mapping_paths(item, (*path, index)))
    return paths


def _at_path(value: object, path: tuple[object, ...]) -> dict[object, object]:
    current = value
    for part in path:
        current = current[part]  # type: ignore[index]
    assert isinstance(current, dict)
    return current
