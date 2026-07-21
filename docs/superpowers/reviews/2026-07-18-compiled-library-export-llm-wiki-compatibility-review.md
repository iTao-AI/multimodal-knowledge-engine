# Compiled Library Export LLM Wiki Compatibility Review

Verdict: **CLEARED FOR SEMANTIC-PROJECTION TASK 4**. Targeted authority re-review accepted the
exact repaired docs/test candidate at `0f40cbbd6cdc9463917868415565de899cbdb1d3` as clean with zero
actionable findings. A subsequent authority amendment preserves run-local provenance UUIDs and
replaces cross-run raw-tree equality with closed raw validity plus normalized semantic-projection
equality. Task 4 has not started under the amended gate.

## Initial Actual-Diff Findings

The first docs candidate recorded a weaker nine-field aggregate and did not preserve the approved
deterministic query-oracle and exact-response contract. It also required the English compatibility
sentence in both README files and omitted the complete negative and historical release boundaries.

The first Task 4 wording incorrectly stated that tracked docs could not change wheel bytes.
`README.md` is package metadata input. Diagnostic builds measured the pre-docs wheel at 309326
bytes with SHA-256
`50bccd685957c1b21e9b45d066060f0a89dd7f4e71e6f86b3546ce3ea4a2b036` and the reviewed docs
candidate wheel at 309422 bytes with SHA-256
`3167b0d2edc07bc62e15c0e36540fcb5e8dc8d39b391e18664c91353661bcf23`. These diagnostic values
explain the repaired gate; neither is final-candidate wheel authority.

## Targeted Re-Review Acceptance

The accepted repair closed all three findings:

1. the weak aggregate and manual evidence were replaced by the strict deterministic oracle, exact
   response and return-path contract, and exact 14-field aggregate;
2. Task 4 was corrected to rebuild and validate a fresh final wheel, retained target, oracle, and
   isolated-wiki proof because `README.md` contributes package metadata; and
3. the documentation contract now requires the exact localized statements, historical v0.1.3
   framing, and full negative claim boundary.

Independent verification at the reviewed HEAD recorded:

- focused documentation and presentation-audit suite: `135 passed`;
- standalone presentation audit: `{"status":"ok","violations":[]}`;
- diff/check, exact seven-path scope, review rename, v0.1.3 release-note SHA, Markdown, and
  public-neutral checks: passed; and
- Task 4 checked steps: `0`.

## Cross-Run Identity Authority Amendment

A diagnostic Task 4 attempt from acceptance commit
`56ac968a7e30f478bb06559c370353895a1a06c5` produced a valid fresh same-wheel export, but its raw
tree was not byte-identical to the independent pre-docs run. Read-only comparison confirmed that
paths, `content_fingerprint`, display name, media type, extractor fingerprint, required stages,
locator, exact Evidence text, counts, and observation were unchanged. Differences were limited to
run-local Source, Publication, Run, and Evidence UUIDs and the Evidence, Markdown, and manifest
SHA-256 values derived from those bytes.

The diagnostic wheel SHA-256
`f45c172685744aeee549c41334106bfd40354e62fbfa00b94ebd69c196746e12`, receipt SHA-256
`65e07848d323465cd67cfd647262e0b5ffaee726e1b4411ab398abbb697d2d50`, and raw tree SHA-256
`2b9cedc422ae0a1da46c3d0ecbd0726482c0e03c57c758aee56a983838424822` are blocker/diagnostic
evidence only. The authority amendment that records this finding changes the execution HEAD, so
none is final-candidate authority.

The repaired gate independently validates both raw exports as closed canonical artifacts with
valid unique identifiers and referential consistency. Cross-run Source identity uses
`content_fingerprint`; Evidence identity uses
`(content_fingerprint, locator.kind, locator.start, locator.end, sha256(exact UTF-8 text))`.
A call-owned standard-library comparator derives comparison-only aliases for Source, Publication,
Run, and Evidence, preserves all exact non-ID fields, rebuilds normalized canonical JSONL,
Markdown, manifest, and a normalized semantic tree digest, and requires exact equality. The tree
digest reuses the retained evidence validator's live encoding: SHA-256 of concatenated canonical
JSON lines, one sorted `[relative_path, byte_count, sha256]` row per regular file.

The comparator must prove rejection of drift in Evidence text, locator, display name, media type,
extractor fingerprint, required stages, or publication revision. Closed raw validation continues
to reject duplicate or inconsistent identifiers, symlinks, special files, and unknown entries.
Aliases are never written into retained output or the wiki and never replace MKE authority. The
wiki consumes final raw bytes and returns final raw `mke.evidence_ref.v1` objects.

Raw tree digest equality is not required across independent runs. Both raw digests are recorded,
and the final raw digest must remain identical before transfer, after transfer, and after the wiki
workflow. Consequently, `export_tree_identity="unchanged"` in the frozen 14-field aggregate means
final retained raw-tree intra-run immutability, not pre-docs/final raw-byte equality. This repair
does not authorize deterministic product UUIDs or any producer, schema, proof-script,
product-lifecycle, package, dependency, workflow, or release change.

## Authority Binding

- Core export lineage: `5d707cfcc98da8ce76d31238c14158cd78b03803`
- Compatibility execution source/amendment commit:
  `c070e0e06e7bb6edd523ef782eb97417f76abf00`
- Actual-diff reviewed docs commit: `de70bc9c1b0fdec7c4f39d5d4c9e5db6e36966dd`
- Pre-docs wheel SHA-256:
  `50bccd685957c1b21e9b45d066060f0a89dd7f4e71e6f86b3546ce3ea4a2b036`
- Retained export tree SHA-256:
  `debd814a900141cf52c08126fb7138aa7bae327e432667f9398d829c54f5335a`
- Proof receipt SHA-256:
  `24b8843b20cf6fa6d64112e4227349e9c870f76d3c85fe12c83dcffefcfdcc28`

The final-candidate wheel identity is intentionally pending Task 4. It must be freshly measured
after this docs repair is committed.

## Strict Closed Aggregate

```json
{"broken_source_link_count":0,"compiled_article_count":1,"configured_hub_impact":"unchanged","evidence_return_count":2,"evidence_schema":"mke.evidence_ref.v1","export_tree_identity":"unchanged","lint_critical_count":0,"page_query_count":1,"query_count":2,"query_scope":"isolated_local_wiki","raw_source_count":2,"schema_version":"mke.compiled_library_export_llm_wiki_proof.v1","status":"passed","timestamp_query_count":1}
```

The strict run used two raw Sources and three exact `mke.evidence_ref.v1` records to compile one
sourced article. A deterministic oracle derived from the canonical manifest and JSONL selected
exactly one page and one timestamp record. Exactly two queries ran through the installed read-only
`wiki-query` local/query-lite route.

Each closed response contained exactly `evidence_text` and `source`. Its Unicode text and UTF-8
SHA-256 exactly matched the oracle, and its source reached the correct raw wrapper,
`content_fingerprint`, locator boundary, manifest leaf, and complete Evidence object. Query and
non-fixing lint made no wiki writes; immutable execution evidence remained outside the wiki.

The retained tree remained unchanged within that run, and the configured-hub identity comparison
was unchanged. Lint reported zero Critical issues and zero broken source links. The call-owned
root was removed. The configured-hub comparison did not read sibling content.

## Documentation Contract And Limitations

The exact English statement is:

> The exported Markdown was ingested and compiled in an isolated LLM Wiki workflow, preserving a
> return path to MKE's authoritative content fingerprint and Evidence sidecars for local-Agent use.

The exact Chinese statement is:

> 导出的 Markdown 已在隔离的 LLM Wiki 工作流中完成摄取与编译，并保留了回到 MKE 权威
> content fingerprint 和 Evidence sidecar 的路径，供本地 Agent 使用。

This is fixed synthetic-input, isolated local, post-release acceptance evidence. LLM Wiki remains a
disposable downstream synthesized view. The result does not establish an MKE dependency, Evidence
authority, bundled adapter, automatic sync, hosted service, production deployment, real-user
adoption, or general multimodal understanding. Compatibility was not shipped by v0.1.3, whose
release history remains unchanged.

## Repair Scope

- `README.md`
- `README_CN.md`
- `docs/how-to/export-compiled-library.md`
- `tests/evaluation/test_compiled_library_export_documentation.py`
- `docs/superpowers/plans/2026-07-15-compiled-library-export-llm-wiki-compatibility-implementation.md`
- rename the superseded 2026-07-15 compatibility review to this 2026-07-18 review

No product code, audit implementation, release history, dependency, lockfile, workflow, producer
contract, schema, fixture, package version, or release identity changes in this repair.

## Verification

Focused RED:

```text
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_compiled_library_export_documentation.py tests/scripts/test_release_presentation_audit.py
3 failed, 132 passed
```

The failures were limited to the missing exact Chinese statement, historical post-release framing,
and complete negative claim boundary.

Focused GREEN and presentation audit:

```text
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_compiled_library_export_documentation.py tests/scripts/test_release_presentation_audit.py
135 passed
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
{"status": "ok", "violations": []}
git diff --check
passed
```

The exact path audit, review rename, Markdown fence balance, public-neutral scan, and byte identity
of `docs/releases/v0.1.3.md` are verified before the local repair commit. Task 4 remains pending
under the raw-valid plus semantic-projection-equal plus final-raw-immutable gate.
