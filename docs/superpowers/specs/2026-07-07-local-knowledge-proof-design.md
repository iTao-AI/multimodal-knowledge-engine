# Local Knowledge Proof Design

Status: approved for implementation.

Planning base: `main@6663df059af1a5947abf9ac23214f504967feba3`.

## Goal

Add a deterministic, public-safe proof that MKE can act as an Agent-callable local knowledge tool:

```text
synthetic local PDFs
  -> stdio MCP ingest_file
  -> published Runs and page Evidence
  -> active Publication search_library
  -> evidence-only ask_library answer or insufficient_evidence
```

The proof must use the real stdio MCP server and official Python MCP client. It must not change the
Search, Ask, MCP, Publication, or runtime contracts.

## Fixture Pack

Create `tests/fixtures/local-knowledge-v1/` with two one-page, repository-authored text-layer PDFs.
The documents describe a fictional system and use ASCII text so the proof exercises the shipped
lexical path without claiming broader retrieval quality.

The pack contains:

- `operations-guide.pdf` and `incident-guide.pdf`;
- `manifest.json` with stable fixture names, byte counts, SHA-256 values, and proof queries;
- `README.md` documenting synthetic provenance, the exact offline generation command, PyMuPDF
  version and rendering settings, per-file byte counts, and per-file SHA-256 values;
- a repository script, `scripts/generate_local_knowledge_fixtures.py`, that regenerates the PDFs
  and manifest from repository-owned constants.

The README describes the synthetic subject matter but does not reproduce exact Evidence text.
Tests regenerate the pack in a temporary directory and require byte-for-byte identity with the
committed files.

## Proof Execution

Add `src/mke/proof/local_knowledge.py` and a thin
`scripts/local_knowledge_proof.py` entrypoint. The proof:

1. validates the committed manifest and fixture identities;
2. creates a temporary SQLite workspace;
3. starts the current environment's `mke --db <temporary-db> mcp --allowed-root <fixture-pack>`;
4. validates the existing public MCP tool schemas;
5. calls `ingest_file` for both PDFs;
6. uses returned Run IDs internally to call `get_run` and require published state and events;
7. calls `search_library` and requires page-addressed active Publication Evidence;
8. calls `ask_library` for one evidence-backed question and requires cited page Evidence;
9. calls `ask_library` for one absent subject and requires `insufficient_evidence` with no Evidence;
10. closes the MCP session and removes the temporary workspace.

The implementation may use Run, Publication, Ask, and Evidence IDs internally. The rendered report
must contain only bounded aggregate fields such as published Run count, Evidence count, locator
kind, and answer statuses.

## Public Output And Failure Contract

Success is one JSON object with stable scalar and nested aggregate fields. It does not include:

- absolute or temporary paths;
- Run, Source, Publication, Ask, or Evidence IDs;
- returned Evidence text or fixture page text;
- subprocess argv, environment values, stderr, or traceback content.

Any fixture, server, transport, tool, validation, or cleanup failure returns a single stable failed
JSON object with `reason="local_knowledge_proof_failed"` and exit code `1`. Sensitive exception text
is not rendered.

## Documentation

Add `docs/how-to/run-local-knowledge-proof.md` and link it from README, README_CN, and
`docs/README.md`. The guide explains the offline command, expected redacted report shape, what the
proof establishes, and its non-goals without copying fixture text or transient identifiers.

Adjust both README Mermaid diagrams so the shipped path reads naturally from local files and Agent
or CLI interfaces through the shared application contract, ingest Runs, Evidence, active
Publication, Search, and evidence-only Ask. Dense, RRF, and reranker records remain visibly
separate comparison-only evaluation evidence.

## Non-Goals

- No dense, hybrid/RRF, or reranker runtime.
- No Search, Ask, MCP, CLI, schema, or runtime-default change.
- No HTTP, UI, OCR, API adapter, query rewrite, HyDE, or segmentation work.
- No model or external fixture download and no network access.
- No package version, CHANGELOG, PyPI, tag, GitHub Release, push, or PR action.
- No private documents or private planning material.

## Verification

Required gates:

```bash
UV_OFFLINE=1 uv run pytest -q <targeted-tests>
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
uv run python scripts/release_presentation_audit.py --root .
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check
```

All commands that can resolve packages must run with the existing lock/cache and without network
or model downloads.
