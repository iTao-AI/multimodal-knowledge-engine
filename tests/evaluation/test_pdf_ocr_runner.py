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
from mke.evaluation.pdf_ocr_runner import (
    CandidateOutcome,
    ExactRate,
    ExtractorIdentityError,
    canonical_extractor_identity_bytes,
    canonical_scorecard_bytes,
    decide,
    edit_rate,
    extractor_fingerprint,
    publish_and_verify,
    validate_extractor_identity,
    validate_scorecard,
)

PROTOCOL_PATH = Path("tests/fixtures/pdf-ocr-phase0-v1/protocol.json")
SCORECARD_PATH = Path("benchmarks/ocr/phase0-scorecard.json")
SHA = "a" * 64
SCORECARD_SHA256 = "131742b67a10da57355279367a99507365fdcc812e676c48452dd7f7745fe0b2"


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
    providers = (
        "apple-vision-local-v1",
        "paddleocr-vl-1.6-cpu-spike-v1",
        "ppocrv6-medium-cpu-spike-v1",
    )
    identities = []
    candidates = []
    for provider in providers:
        identity = _identity()
        identity["provider"] = {"id": provider, "profile": "profile-v1"}
        outcome = _outcome(provider)
        identities.append(
            {
                "provider": provider,
                "fingerprint": extractor_fingerprint(identity),
                "payload": identity,
            }
        )
        candidates.append(
            {
                "outcome": outcome.to_dict(),
                "page_results": [
                    {
                        "document_id": "a",
                        "page_number": 1,
                        "normalized_text_sha256": SHA,
                        "nonempty": True,
                    },
                    {
                        "document_id": "b",
                        "page_number": 2,
                        "normalized_text_sha256": "b" * 64,
                        "nonempty": True,
                    },
                ],
                "publication_evidence_pages": [
                    {"document_id": "a", "page_number": 1}
                ],
            }
        )
    return {
        "schema": "mke.pdf_ocr_phase0_scorecard.v1",
        "protocol": {
            "id": "pdf-ocr-phase0-v1",
            "sha256": SHA,
            "documents": 4,
            "pages": 9,
            "queries": 3,
        },
        "receipts": {
            "package_sha256": SHA,
            "model_sha256": "b" * 64,
            "provider_startup_sha256": "c" * 64,
        },
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
        "decision": {
            "status": "go",
            "selected_provider": "apple-vision-local-v1",
            "selected_profile": "profile-v1",
        },
    }


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
        key: hashlib.sha256(path.read_bytes()).hexdigest()
        for key, path in receipt_paths.items()
    }
    startup = json.loads(receipt_paths["provider_startup_sha256"].read_bytes())
    model = json.loads(receipt_paths["model_sha256"].read_bytes())
    for binding in payload["extractor_identities"]:
        identity = binding["payload"]
        assert identity["package"]["receipt_sha256"] == startup["package_receipt_sha256"]
        assert identity["package"]["mke_wheel_sha256"] == startup["runtime"][
            "mke_wheel_sha256"
        ]
        assert identity["package"]["installed_packages_sha256"] == startup["runtime"][
            "installed_packages_sha256"
        ]
        assert identity["model"]["receipt_sha256"] == startup["model_receipt_sha256"]
        assert identity["model"]["tree_sha256"] == model["tree_sha256"]


def _leaf_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        return [
            leaf
            for key, item in value.items()
            for leaf in _leaf_paths(item, (*path, key))
        ]
    if isinstance(value, list):
        return [
            leaf
            for index, item in enumerate(value)
            for leaf in _leaf_paths(item, (*path, index))
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
