# Run The Local Knowledge Proof

Use this proof to verify that an Agent can use MKE as a local knowledge tool over real stdio MCP.
The workflow is deterministic, offline, and requires no model, credentials, external service, or
download.

From the repository root with the locked environment available, run:

```bash
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
```

The script starts the current environment's `mke` stdio MCP server against an isolated SQLite
workspace. It uses the repository-authored synthetic fixture pack under
`tests/fixtures/local-knowledge-v1/`, then removes the workspace after the MCP session closes.

## Expected Result

Success prints one JSON object with this aggregate shape:

```json
{
  "ask": {"citations": 1, "status": "evidence_found"},
  "evidence": {"locator": "page", "published": 2},
  "fixtures": 2,
  "proof": "local_knowledge",
  "refusal": {"citations": 0, "status": "insufficient_evidence"},
  "runs": {"published": 2},
  "search": {"results": 1, "status": "evidence_found"},
  "status": "passed"
}
```

The proof returns exit code `0` only after all checks pass. Any fixture, server, transport, tool, or
validation failure returns one redacted failed JSON object and exit code `1`.

## What This Proves

- Two supported local files can be ingested through MCP `ingest_file` calls.
- Each ingest creates an observable Run that reaches `published` with append-only events.
- Published page Evidence is available through active Publication Search.
- MCP `ask_library` returns a cited evidence-only Ask result when Evidence matches.
- MCP `ask_library` returns `insufficient_evidence` with zero citations when Evidence is absent.
- The Agent-facing flow uses the existing MCP tool schemas and the same application contract as
  the CLI.

The proof uses transport responses internally to connect ingest and Run inspection. Public output
contains only counts, locator kind, and stable statuses. It does not render local or temporary
paths, transient identifiers, Evidence text, subprocess details, exception text, or tracebacks.

## Fixture Provenance

The two PDFs are repository-authored synthetic documents about a fictional system. Their README
records the offline generator command, PyMuPDF settings, exact byte counts, and SHA-256 identities.
Fixture tests regenerate the pack and require byte-for-byte equality. No private or external source
material is used.

## What This Does Not Prove

- Dense retrieval, hybrid/RRF execution, or reranker runtime behavior.
- Retrieval quality beyond the fixed synthetic lexical queries.
- Generative answers, model quality, model downloads, or external providers.
- Scanned-PDF OCR, arbitrary media handling, HTTP, UI, or API adapters.
- Installed-wheel portability; the existing consumer-smoke workflow covers package consumption.

This proof does not change Search, Ask, MCP, Publication, ingestion, owner-startup strategy, or the
runtime default.

