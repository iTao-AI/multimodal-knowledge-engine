from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from mke.application.evidence_access import canonical_json_bytes
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.source_search import search_source_evidence_v1
from mke.interfaces.source_search_schemas import (
    SearchSourceEvidenceResponseV1,
    SearchSourceEvidenceSuccessV1,
    SearchSourceEvidenceV1Request,
)
from mke.runtime import RuntimeConfig
from tests.source_discovery_support import publish_pages


def search_snapshot(
    root: Path,
    texts: tuple[str, ...],
) -> tuple[McpRuntimeConfig, str, str, SearchSourceEvidenceResponseV1]:
    database = root / "mke.sqlite"
    source, publication = publish_pages(database, texts)
    config = McpRuntimeConfig(RuntimeConfig(db_path=database), root)
    response = search_source_evidence_v1(
        config,
        SearchSourceEvidenceV1Request(
            root={
                "source_id": source,
                "publication_id": publication,
                "query": "needle",
                "limit": 20,
            }
        ),
    )
    assert response.root.ok
    return config, source, publication, response


def ask_shape(search: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "mke.source_ask_response.v1",
        "ok": True,
        "question": "needle",
        "answer_status": "evidence_found",
        "scope": search["scope"],
        "authority_snapshot": search["authority_snapshot"],
        "evidence": search["matches"],
        "selection": {
            "mode": "bounded_first_page",
            "status": "complete",
            "returned": 1,
            "next_step": "read_selected_evidence",
        },
        "output": search["output"],
        "limitations": (
            "Evidence selection only; matches do not verify an answer or complete understanding "
            "of original media."
        ),
    }


def test_cli_ask_schema_matches_its_separate_frozen_snapshot() -> None:
    from mke.interfaces.source_ask_schemas import SourceAskResponseV1

    snapshot = Path("tests/fixtures/source-ask-v1/cli-response-schema.json")
    assert SourceAskResponseV1.model_json_schema() == json.loads(snapshot.read_text())


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "publication",
        "revision",
        "run",
        "fingerprint",
        "read",
        "count",
        "answer",
        "cursor",
        "excerpt_bytes",
    ],
)
def test_ask_dto_rejects_incoherent_citation_or_selection(tmp_path: Path, mutation: str) -> None:
    from mke.interfaces.source_ask_schemas import SourceAskResponseV1

    config, _, _, response = search_snapshot(tmp_path, ("needle",))
    try:
        payload = ask_shape(response.model_dump(mode="json"))
        if mutation in {"source", "publication", "revision", "run", "fingerprint"}:
            key = {
                "source": "source_id",
                "publication": "publication_id",
                "revision": "publication_revision",
                "run": "run_id",
                "fingerprint": "content_fingerprint",
            }[mutation]
            payload["evidence"][0]["evidence"][key] = (
                2
                if mutation == "revision"
                else ("sha256:" + "0" * 64 if mutation == "fingerprint" else "wrong_identity")
            )
        elif mutation == "read":
            payload["evidence"][0]["read"]["evidence_id"] = "ev_wrong"
        elif mutation == "count":
            payload["selection"]["returned"] = 0
        elif mutation == "answer":
            payload["answer_status"] = "insufficient_evidence"
        elif mutation == "cursor":
            payload["selection"]["next_cursor"] = "not_reusable"
        else:
            payload["evidence"][0]["excerpt"]["returned_utf8_bytes"] = 1
        with pytest.raises(ValidationError):
            SourceAskResponseV1.model_validate(payload)
    finally:
        config.runtime.process_controller.shutdown()


def test_added_ask_envelope_shrinks_complete_search_without_false_completeness(
    tmp_path: Path,
) -> None:
    from mke.interfaces.source_ask import ask_source_evidence

    config, source, publication, search = search_snapshot(tmp_path, ("needle " + '"' * 1175,) * 10)
    try:
        snapshot = search.root
        assert isinstance(snapshot, SearchSourceEvidenceSuccessV1)
        assert snapshot.selection.status == "complete"
        assert (
            len(snapshot.matches) == 10
            and len(canonical_json_bytes(search.model_dump(mode="json"))) > 32600
        )
        response = ask_source_evidence(config, source, publication, "needle", limit=20).model_dump(
            mode="json"
        )
        assert response["ok"] and 0 < len(response["evidence"]) < 10
        assert len(canonical_json_bytes(response)) <= 32768
        assert response["selection"]["status"] == "more_available"
        assert response["selection"]["next_step"] == "run_scoped_search_for_all_matches"
        assert response["selection"]["returned"] == len(response["evidence"])
    finally:
        config.runtime.process_controller.shutdown()


def test_invalid_last_citation_cannot_be_hidden_by_envelope_shrink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mke.interfaces.source_ask as operation

    config, source, publication, search = search_snapshot(tmp_path, ("needle " + '"' * 1175,) * 10)
    try:
        snapshot = search.root
        assert isinstance(snapshot, SearchSourceEvidenceSuccessV1)
        last = snapshot.matches[-1]
        invalid = last.model_copy(
            update={"evidence": last.evidence.model_copy(update={"source_id": "src_wrong"})}
        )
        corrupt = search.model_copy(
            update={
                "root": snapshot.model_copy(
                    update={
                        "matches": [*snapshot.matches[:-1], invalid],
                    }
                )
            }
        )

        def corrupted_search(
            _config: McpRuntimeConfig,
            _request: SearchSourceEvidenceV1Request,
        ) -> SearchSourceEvidenceResponseV1:
            return corrupt

        monkeypatch.setattr(operation, "search_source_evidence_v1", corrupted_search)
        response = operation.ask_source_evidence(
            config, source, publication, "needle", limit=20
        ).model_dump(mode="json")
        assert response["ok"] is False and response["problem"] == "internal_error"
        assert "src_wrong" not in json.dumps(response)
    finally:
        config.runtime.process_controller.shutdown()
