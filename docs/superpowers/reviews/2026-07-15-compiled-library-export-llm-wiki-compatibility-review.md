# Compiled Library Export LLM Wiki Compatibility Review

Status: Task 2 evidence is accepted and Task 3 is a locally verified docs/evidence candidate. Task
4 has not started and remains subject to an independent actual-diff review.

## Authority Binding

- Core lineage: `5d707cfcc98da8ce76d31238c14158cd78b03803`
- Compatibility source/amendment commit: `c070e0e06e7bb6edd523ef782eb97417f76abf00`
- Wheel SHA-256: `50bccd685957c1b21e9b45d066060f0a89dd7f4e71e6f86b3546ce3ea4a2b036`
- Retained export tree SHA-256:
  `debd814a900141cf52c08126fb7138aa7bae327e432667f9398d829c54f5335a`
- Proof receipt SHA-256: `24b8843b20cf6fa6d64112e4227349e9c870f76d3c85fe12c83dcffefcfdcc28`

## Closed Aggregate

```json
{"compiled_article_count":1,"configured_hub_impact":"unchanged","evidence_return_path":"preserved","export_byte_identity":"unchanged","ingested_source_count":2,"lint_critical_count":0,"query_count":2,"schema_version":"mke.compiled_library_export_llm_wiki_proof.v1","status":"passed"}
```

Two immutable raw Markdown records were ingested and synthesized into one sourced article. Exactly
two bounded queries were run: one page locator and one timestamp locator. Both return paths used the
exact `content_fingerprint` to reach unchanged manifest/JSONL bytes and exact
`mke.evidence_ref.v1` records. The retained export final rehash matched its original tree digest.

Lint reported zero Critical issues and zero broken source links. One single-article/no-peer
suggestion was non-blocking. Configured hub, configuration, and credentials were not resolved or
touched; all writes stayed in the call-owned local wiki root, which was removed after the proof.

## Documentation Contract

The accepted public statement is:

> The exported Markdown was ingested and compiled in an isolated LLM Wiki workflow, preserving a
> return path to MKE's authoritative content fingerprint and Evidence sidecars for local-Agent use.

This is a fixed synthetic-input, local isolated compatibility result. LLM Wiki remains a downstream
synthesized view. The result does not make it an MKE dependency, Evidence authority, bundled
integration, hosted service, or production deployment, and it does not establish real-user
adoption or general multimodal understanding.

## Exact Docs Diff

- `README.md`
- `README_CN.md`
- `docs/how-to/export-compiled-library.md`
- `tests/evaluation/test_compiled_library_export_documentation.py`
- `docs/superpowers/plans/2026-07-15-compiled-library-export-llm-wiki-compatibility-implementation.md`
- `docs/superpowers/reviews/2026-07-15-compiled-library-export-llm-wiki-compatibility-review.md`

No product code, producer contract, schema, dependency, workflow, fixture, lockfile, release
identity, or presentation-audit implementation is changed.

## Verification

RED contract:

```text
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_compiled_library_export_documentation.py tests/scripts/test_release_presentation_audit.py
1 failed, 131 passed
```

The only RED failure was the new exact-sentence contract.

GREEN and presentation audit:

```text
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_compiled_library_export_documentation.py tests/scripts/test_release_presentation_audit.py
132 passed
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
{"status": "ok", "violations": []}
git diff --check
passed
```
