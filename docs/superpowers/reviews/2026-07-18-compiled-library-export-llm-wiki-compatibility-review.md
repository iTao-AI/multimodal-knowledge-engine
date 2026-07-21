# Compiled Library Export LLM Wiki Compatibility Review

Verdict: **TASK 4 LOCAL EVIDENCE COMPLETE; PENDING FINAL ACTUAL-DIFF REVIEW**. Targeted authority
re-review accepted the repaired docs/test candidate at
`0f40cbbd6cdc9463917868415565de899cbdb1d3` as clean with zero actionable findings. The subsequent
authority amendment at `e0559816a66957d2964b20d0d08ca1b8ec2f3719` preserves run-local
provenance UUIDs and replaces cross-run raw-tree equality with closed raw validity plus normalized
semantic-projection equality. The amended final proof and scoped local gates passed; this closure
now awaits final actual-diff review.

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

## Final Task 4 Evidence

The amendment commit `e0559816a66957d2964b20d0d08ca1b8ec2f3719` is the sole final-proof
source authority. The fresh final wheel is
`multimodal_knowledge_engine-0.1.3-py3-none-any.whl`, `309598` bytes, SHA-256
`f45c172685744aeee549c41334106bfd40354e62fbfa00b94ebd69c196746e12`. Independent descriptor
reads confirmed package name `multimodal-knowledge-engine`, version `0.1.3`, and source binding.
The Python identities were CPython `3.12.13` and CPython `3.13.12`.

The single fresh same-wheel proof returned schema `mke.compiled_library_export_proof.v1`, status
`passed`, interpreter count `2`, and the same final wheel SHA-256. Its canonical retained receipt
SHA-256 is `65e07848d323465cd67cfd647262e0b5ffaee726e1b4411ab398abbb697d2d50`.
Both standalone consumer runs and independent closed raw validation passed.

The pre-docs raw tree SHA-256 remained
`debd814a900141cf52c08126fb7138aa7bae327e432667f9398d829c54f5335a`; the final raw tree
SHA-256 is `63495005e7b2fbc466270fe095cf767f0055c8b7325115df3a0daa5717e4a8a0`.
The two stable Source keys and three stable Evidence keys matched. Both normalized semantic
projections produced SHA-256
`e85a971adaa304e0a4ea3b5249b81e657862d34b831fa1a342501b5ae7a2ef07`.
All seven semantic-drift probes changed that projection, and duplicate or inconsistent raw
identifier probes failed closed.

The final closed descriptor inventory is:

```text
evidence/0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd.jsonl  536  fa93f17f917d5f6d8a67f0ca87722fc043c4c57107e2af3ac6e916492e495452
evidence/6c2a57a73ee01976bccfcfe73f3334d8d1675a891ccc5868d68fa2caadf27e3e.jsonl  969  7de643bfee86ae0ddc1e8028060bcb4c1c007c8b058abfc73a87c4aeda98db57
export-manifest.json                                                                    2003  332b17cd4e9795705e82d24e259f39144260f266d0075afe78bdf2a618795450
sources/0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd.md       763  2f39236bdb6c189baac3f5c1a1fd7b46657a577cd455173fe72b90f7c54e95de
sources/6c2a57a73ee01976bccfcfe73f3334d8d1675a891ccc5868d68fa2caadf27e3e.md       858  eb00de8481156ec1e440d0edd4e37e0090a8ee758557d35b56cfc21d5b5a3008
```

The final raw tree retained the same digest before transfer, after transfer, and after wiki use.
The fresh isolated local wiki compiled one sourced article from two raw Sources and three exact
Evidence records. The page return path reached final raw Evidence
`ev_042ee266927a42dc88ab101ccaea143b` at page `1`; the timestamp return path reached final raw
Evidence `ev_10820df5332549398d706b6243d970ff` at `0-1200` milliseconds. Both exact Unicode and
SHA-256 joins reached the raw wrapper, `content_fingerprint`, locator boundary, manifest leaf, and
complete `mke.evidence_ref.v1` object. Comparison aliases never entered the wiki.

Exactly two query-lite processes ran, one per locator kind. A post-query transport encoder was
unavailable after both processes completed, so the queries were not rerun. The immutable wiki tree
and frozen deterministic query program reconstructed the two closed response bytes for independent
return-path validation. This is a bounded final-review limitation; it does not alter the query
count or establish a product behavior claim.

Query and non-fixing lint made zero wiki writes. Lint reported zero Critical issues and zero broken
source links. Configured-hub impact remained unchanged without sibling-content reads, the
call-owned wiki root was removed, and the final retained evidence was preserved.

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
