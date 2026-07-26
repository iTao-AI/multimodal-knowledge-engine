from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from mke.application import KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    RunManifest,
)
from mke.evaluation.retrieval_order_workflow import (
    observe_retrieval_order_partition,
)
from mke.retrieval.errors import RetrievalAuthorityError

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-order-v1/protocol.json"


def test_inverse_cjk_id_schedules_return_same_stable_projection() -> None:
    observation = observe_retrieval_order_partition(
        protocol_path=PROTOCOL,
        partition="development",
        repository_root=ROOT,
    )
    cases = observation["cases"]
    assert isinstance(cases, list)
    cjk = [
        cast(dict[str, object], item)
        for item in cast(list[object], cases)
        if isinstance(item, dict)
        and cast(dict[str, object], item).get("strategy") == "cjk"
    ]

    assert cjk
    assert all(item["stable"] is True for item in cjk)
    assert all(item["pagination_lossless"] is True for item in cjk)
    assert observation["candidate_membership_delta"] == 0
    assert observation["score_hex_delta"] == 0
    assert observation["non_tied_pair_delta"] == 0
    assert observation["pagination_duplicate_or_gap_count"] == 0


def test_duplicate_bounded_cjk_candidates_raise_authority_error(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        source = engine.ensure_source("duplicate.pdf", "e" * 64)
        run = engine.create_run(source.source_id)
        engine.persist_validated_candidate(
            run.run_id,
            [
                CandidateEvidence(
                    evidence_id="evidence_original",
                    locator_kind="page",
                    locator_start=1,
                    locator_end=1,
                    text="重复权威验证",
                )
            ],
            RunManifest(
                run_id=run.run_id,
                evidence_count=1,
                required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
                extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
                asset_sha256="e" * 64,
            ),
        )
        engine.activate_publication(run.run_id)
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute(
            """
            INSERT INTO evidence(
              evidence_id, run_id, source_id, locator_kind,
              locator_start, locator_end, text
            )
            SELECT 'evidence_duplicate', run_id, source_id, locator_kind,
                   locator_start, locator_end, text
            FROM evidence WHERE evidence_id = 'evidence_original'
            """
        )

        with pytest.raises(RetrievalAuthorityError):
            engine.search("重复权威验证")
    finally:
        engine.close()
