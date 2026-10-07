"""One bounded CLI Ask packet from the existing scoped Search snapshot."""

from __future__ import annotations

from mke.application.evidence_access import MAX_CANONICAL_MODEL_BYTES, canonical_json_bytes
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.source_ask_schemas import ASK_LIMITATIONS, SourceAskResponseV1
from mke.interfaces.source_search import search_source_evidence_v1
from mke.interfaces.source_search_schemas import (
    SearchSourceEvidenceResponseV1,
    SearchSourceEvidenceSuccessV1,
    SearchSourceEvidenceV1Request,
)


def ask_source_evidence(
    config: McpRuntimeConfig,
    source_id: str,
    publication_id: str,
    question: str,
    limit: int = 5,
) -> SourceAskResponseV1:
    try:
        response = search_source_evidence_v1(
            config,
            SearchSourceEvidenceV1Request(
                root={
                    "source_id": source_id,
                    "publication_id": publication_id,
                    "query": question,
                    "limit": limit,
                }
            ),
        )
        # Revalidate every citation before any envelope-driven omission.
        validated = SearchSourceEvidenceResponseV1.model_validate(response.model_dump(mode="json"))
        snapshot = validated.root
        if not isinstance(snapshot, SearchSourceEvidenceSuccessV1):
            payload = validated.model_dump(mode="json")
            payload["schema_version"] = "mke.source_ask_response.v1"
            return SourceAskResponseV1.model_validate(payload)
        return _assemble(snapshot, question.strip())
    except Exception:
        return SourceAskResponseV1.model_validate(
            {
                "schema_version": "mke.source_ask_response.v1",
                "ok": False,
                "problem": "internal_error",
                "cause": "operation failed; details were redacted",
                "active_publication_impact": "unchanged",
                "next_step": "check_server_logs",
            }
        )


def _assemble(snapshot: SearchSourceEvidenceSuccessV1, question: str) -> SourceAskResponseV1:
    for count in range(len(snapshot.matches), -1, -1):
        if count == 0 and snapshot.matches:
            break
        selected = snapshot.matches[:count]
        more = snapshot.selection.status == "more_available" or count < len(snapshot.matches)
        next_step = (
            "run_scoped_search_for_all_matches"
            if more
            else "read_selected_evidence"
            if selected
            else "refine_question_in_selected_source"
        )
        payload = {
            "schema_version": "mke.source_ask_response.v1",
            "ok": True,
            "question": question,
            "answer_status": "evidence_found" if selected else "insufficient_evidence",
            "scope": snapshot.scope.model_dump(mode="json"),
            "authority_snapshot": snapshot.authority_snapshot.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in selected],
            "selection": {
                "mode": "bounded_first_page",
                "status": "more_available" if more else "complete",
                "returned": count,
                "next_step": next_step,
            },
            "output": {
                **snapshot.output.model_dump(mode="json"),
                "incomplete_excerpt_count": sum(not item.excerpt.complete for item in selected),
            },
            "limitations": ASK_LIMITATIONS,
        }
        if len(canonical_json_bytes(payload)) <= MAX_CANONICAL_MODEL_BYTES:
            return SourceAskResponseV1.model_validate(payload)
    return SourceAskResponseV1.model_validate(
        {
            "schema_version": "mke.source_ask_response.v1",
            "ok": False,
            "problem": "response_too_large",
            "cause": "mandatory response metadata exceeds the response limit",
            "active_publication_impact": "unchanged",
            "next_step": "reduce_query_scope_or_report_contract_limit",
        }
    )
