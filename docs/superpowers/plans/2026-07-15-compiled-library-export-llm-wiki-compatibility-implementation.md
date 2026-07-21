# Compiled Library Export LLM Wiki Compatibility Implementation Plan

Status: **ACCEPTED — CLEARED FOR PR HANDOFF**. Final actual-diff review accepted exact candidate
`c8df4bb9dae5c6ca16b5ec392c78fe08bc773c07` as clean with no actionable finding. The cross-run
identity amendment at `e0559816a66957d2964b20d0d08ca1b8ec2f3719` preserved run-local
provenance identifiers and replaced cross-run raw-tree equality with closed raw validation plus
normalized semantic-projection equality. Task 4 local authority is complete. Normal PR CI and all
remote operations remain pending and require separate handoff authorization.

> **For agentic workers:** Use the approved execution controller for the repository-owned
> mechanical, proof, documentation, and verification steps. Run the LLM Wiki workflow only inside
> a call-owned isolated workspace; do not write to an operator's configured wiki hub.

**Goal:** Prove that a fresh Compiled Library Export can be ingested, compiled, queried, and traced
back to exact MKE Evidence in an isolated LLM Wiki workflow, then record the bounded downstream
compatibility claim without changing MKE runtime behavior.

**Architecture:** Build one fresh installed-wheel export from the audited current baseline,
validate and retain only its closed output, ingest the immutable exported Markdown into a new
local `.wiki/`, compile one sourced article, and join two bounded answers back through
`content_fingerprint` to MKE's unchanged manifest and JSONL. MKE remains the provenance authority;
the wiki is a disposable downstream synthesized view.

**Tech Stack:** Python 3.12/3.13, `compiled_library_export_proof.py`, the standalone export
consumer, standard-library hashing and JSON validation, the installed LLM Wiki agent workflow,
Markdown documentation tests, Pytest, Ruff, Pyright, Hatch/uv, and Git.

## Audited Baseline

- Core export lineage: `5d707cfcc98da8ce76d31238c14158cd78b03803`; that historical commit still
  carried package version `0.1.2` and is not the execution checkout.
- Compatibility execution source/amendment commit:
  `c070e0e06e7bb6edd523ef782eb97417f76abf00`, containing the current `v0.1.3` package identity.
- Actual-diff review examined docs candidate
  `de70bc9c1b0fdec7c4f39d5d4c9e5db6e36966dd` and requested this bounded authority repair.
- The public v0.1.3 release history remains frozen. Its generic proof did not establish LLM Wiki
  compatibility; the completed compatibility run is separate post-release acceptance evidence.

## Targeted Authority Re-Review Acceptance

The targeted actual-diff re-review accepted
`0f40cbbd6cdc9463917868415565de899cbdb1d3` as clean with zero actionable findings. It closed all
three prior findings:

1. the plan and review now bind the strict deterministic oracle, exact response and return-path
   contract, and exact 14-field aggregate;
2. Task 4 now treats `README.md` as wheel metadata input and requires a fresh final wheel, retained
   target, oracle, and isolated-wiki proof; and
3. the localized documentation contract now requires the exact Chinese statement, post-release
   v0.1.3 framing, and complete negative claim boundary.

Independent verification at that reviewed HEAD recorded `135 passed` for the focused documentation
and presentation-audit suite, `{"status":"ok","violations":[]}` for the standalone presentation
audit, and successful diff/check, exact seven-path scope, review rename, v0.1.3 release-note SHA,
Markdown, and public-neutral checks. Task 4 had zero checked steps at acceptance.

## Cross-Run Identity Authority Amendment

Source, Publication, Run, and Evidence UUIDs are valid run-local provenance identity, not
cross-run content identity. A diagnostic Task 4 attempt from acceptance commit
`56ac968a7e30f478bb06559c370353895a1a06c5` confirmed that the two raw exports differed only in
those identifiers and in file and manifest digests derived from their bytes. Its wheel SHA-256
`f45c172685744aeee549c41334106bfd40354e62fbfa00b94ebd69c196746e12`, receipt SHA-256
`65e07848d323465cd67cfd647262e0b5ffaee726e1b4411ab398abbb697d2d50`, and raw tree SHA-256
`2b9cedc422ae0a1da46c3d0ecbd0726482c0e03c57c758aee56a983838424822` are diagnostic evidence
only and are not final-candidate authority.

The approved cross-run gate is:

1. Independently validate each raw export with the existing standalone consumer and descriptor
   reads. Require closed canonical manifest, JSONL, and Markdown; exact inventory; every raw byte
   count and SHA-256; valid unique identifiers and referential consistency; and rejection of
   symlinks, special files, and unknown entries.
2. Use `content_fingerprint` as the stable Source key and require the two stable Source key sets to
   be exactly equal.
3. Use `(content_fingerprint, locator.kind, locator.start, locator.end, sha256(exact UTF-8 text))`
   as the stable Evidence key. Require uniqueness inside each export and exact set equality across
   the two exports.
4. In a call-owned standard-library comparator only, derive canonical aliases for comparison:
   Source from `content_fingerprint`, Publication from `content_fingerprint` plus
   `publication_revision`, Run from `content_fingerprint`, and Evidence from the complete stable
   Evidence key. Never write these aliases into a retained export, wiki, or product file.
5. Substitute aliases only in the comparison projection, preserve every exact non-ID field,
   rebuild normalized canonical JSONL and normalized Markdown, recompute their SHA-256 values, and
   rebuild the normalized manifest. Canonical JSON uses `sort_keys=True`, compact separators,
   `ensure_ascii=False`, `allow_nan=False`, and one trailing newline.
6. Compute a normalized semantic tree digest over the same closed inventory with the retained
   evidence validator's live encoding: SHA-256 of concatenated canonical JSON lines, one sorted
   `[relative_path, byte_count, sha256]` row per regular file. Require exact equality between the
   pre-docs and final projections.
7. Record both raw tree digests without requiring cross-run equality. Require the final raw tree
   digest to remain identical before transfer, after transfer, and after the wiki workflow.
   `export_tree_identity="unchanged"` in the 14-field aggregate means this final retained raw-tree
   intra-run immutability only.
8. Require the wiki to consume the final raw export and return the final raw Evidence objects.
   Comparison aliases may not enter the wiki or replace MKE authority.
9. Run controlled negative probes proving that drift in Evidence text, locator, display name,
   media type, extractor fingerprint, required stages, or publication revision changes the
   semantic projection. Continue to reject duplicate or inconsistent raw identifiers during
   closed raw validation.

This amendment changes comparison authority only. It authorizes no producer, schema, proof-script,
product-lifecycle, package, dependency, workflow, or release change and specifically does not
authorize deterministic product UUIDs.

## Entry Gate

- Re-fetch current repository facts and require `main == origin/main`, a clean primary worktree,
  no open Compiled Library Export repair PR, and successful expected checks on current `main`.
- Create a new isolated docs/evidence worktree from current `main`. If current `main` differs from
  the audited baseline, review the intervening diff and stop if it changes export behavior,
  schemas, proof authority, LLM Wiki claim boundaries, or planned file ownership.
- Re-read the merged export spec, implementation plan, implementation review, export how-to,
  proof scripts, release-history boundary, and this amended compatibility plan.
- Do not reuse a pre-release wheel, retained export, receipt, wiki, model response, candidate
  directory, or historical worktree.
- Stop for authority amendment if the live command, schema, retained inventory, proof receipt,
  documentation test contract, or public claim boundary differs from this plan.

## Global Constraints

- This is a docs/evidence PR. Do not modify `src/mke`, dependencies, lockfiles, workflows, product
  scripts, export schemas, fixtures, retrieval artifacts, OCR evidence, package version, release
  notes, tag, or GitHub Release.
- Use only a fresh public-safe synthetic export produced from the exact execution baseline.
- Never write to a configured wiki hub or inspect sibling wiki content. Capture configured-hub
  identity before the proof only to establish the non-impact comparison; all compatibility
  operations run from a call-owned parent containing `.wiki/`. Queries must use the installed
  read-only `wiki-query` local route, whose `.wiki/`-first resolution does not consult the hub or
  sibling indexes.
- Do not add LLM Wiki as a runtime, development, CI, or documentation-build dependency.
- Do not invent `/wiki:*` shell commands. Use the installed agent workflow and its documented
  natural-language operations.
- Do not add a network, hosted API, or external LLM requirement to MKE runtime, CI, export
  generation, or export consumption. The already-configured agent workflow used by the
  compatibility operator remains outside MKE.
- Private source material, local paths, hostnames, credentials, tokens, raw model output,
  timestamps, configured-hub identity, and internal operator details may not enter repository
  files.
- Each retained MKE export is immutable raw input. Any raw inventory, byte, manifest, Markdown,
  JSONL, identifier-integrity, or digest failure rejects that export. Cross-run acceptance
  additionally requires equal normalized semantic projections, while the final raw export must
  remain byte-identical throughout transfer and wiki use.
- A failed compatibility proof does not invalidate the generic Compiled Library Export contract.
  Classify the downstream gap and stop; any product-specific adapter requires a new design.
- This is post-release downstream acceptance. It must not rewrite v0.1.3 history. An accepted
  statement may be presented as post-release evidence and may later be summarized by a v0.1.4
  release, but this PR does not publish a version.

## Data Flow

```text
audited current main
      |
      | build one wheel, Python 3.12 + 3.13 same-wheel proof
      v
retained/compiled-library/ + retained/proof-receipt.json
      |
      | independent inventory, canonical and digest validation
      v
immutable exported Markdown
      |
      | isolated natural-language ingest and compile
      v
call-owned .wiki/
      |
      +--> compiled article --> one bounded page query
      +--> compiled article --> one bounded timestamp query
      |
      | exact sources frontmatter -> raw note -> content_fingerprint
      v
unchanged export-manifest.json + evidence/*.jsonl
      |
      v
exact mke.evidence_ref.v1 return path
```

## Planned Repository Files

- Modify `README.md` and `README_CN.md` only to add the accepted post-release compatibility
  statement in a dedicated downstream-evidence section.
- Modify `docs/how-to/export-compiled-library.md` to explain the isolated workflow, downstream
  synthesis boundary, and Evidence return path.
- Modify `tests/evaluation/test_compiled_library_export_documentation.py` to require the bounded
  English and Chinese statements and reject stronger claims.
- Modify this plan only to record completed steps and accepted evidence.
- Create
  `docs/superpowers/reviews/2026-07-18-compiled-library-export-llm-wiki-compatibility-review.md`
  only after the proof succeeds.
- Keep `docs/releases/v0.1.3.md` byte-identical: its deferred-at-release statement is historical
  fact.
- Keep the generic proof how-to statement that the generic proof does not verify LLM Wiki
  compatibility; the separate workflow remains the only compatibility authority.
- Run but do not modify `scripts/release_presentation_audit.py` unless a live RED proves it cannot
  distinguish the approved sentence from an overclaim. Any audit behavior change is a hard stop
  for separate review.

---

### Task 1: Produce a fresh retained export

**Files:** no tracked changes.

- [x] **Step 1: Verify exact checkout and interpreter authority**

Record the execution commit and exact Python 3.12/3.13 interpreter identities. Require two
distinct real interpreters, a clean source worktree, and successful focused export documentation,
consumer, proof, and CLI tests before retaining evidence.

- [x] **Step 2: Run one fresh same-wheel proof with retained output**

```bash
PROOF_ROOT="$(mktemp -d)"
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --retained-export "$PROOF_ROOT/retained" \
  --json
```

Require one wheel digest across both interpreters and exact proof status `passed`. Require the
retained root to contain exactly:

```text
retained/
├── compiled-library/
└── proof-receipt.json
```

- [x] **Step 3: Independently validate retained authority**

Run the standalone consumer against `retained/compiled-library/` and validate the receipt against
the original proof inputs. Require:

- exact closed receipt schema and canonical receipt bytes, plus an independently computed receipt
  file SHA-256; the v1 receipt does not contain a self-digest;
- exact export inventory and counts;
- canonical manifest and JSONL records;
- every manifest-bound Markdown and JSONL byte count and SHA-256;
- no symlink, special file, unexpected entry, private path, hostname, credential, or timestamp;
- one deterministic tree digest using the retained evidence validator's SHA-256 of concatenated
  canonical JSON lines, one sorted `[relative_path, byte_count, sha256]` row per regular file, with
  descriptor reads supplying each byte count and SHA-256.

Do not transfer the wheel, temporary environments, databases, logs, or original input paths into
the wiki workspace.

- [x] **Step 4: Establish the immutable handoff**

Make only `retained/compiled-library/`, the closed public-safe receipt fields, the validated tree
digest, and the approved natural-language operations available to the isolated compatibility
step. Rehash immediately before and after transfer.

Accepted Task 1 evidence binds source commit
`c070e0e06e7bb6edd523ef782eb97417f76abf00` to pre-docs wheel SHA-256
`50bccd685957c1b21e9b45d066060f0a89dd7f4e71e6f86b3546ce3ea4a2b036`, proof receipt SHA-256
`24b8843b20cf6fa6d64112e4227349e9c870f76d3c85fe12c83dcffefcfdcc28`, and retained export tree
SHA-256 `debd814a900141cf52c08126fb7138aa7bae327e432667f9398d829c54f5335a`. The same-wheel proof,
canonical validation, descriptor reads, exact inventory, and standalone consumer passed.

### Task 2: Run the isolated LLM Wiki compatibility proof

**Files:** no tracked repository changes during this task.

- [x] **Step 1: Establish an isolated local wiki**

Create a new call-owned temporary parent and initialize a local wiki titled
`Compiled Library Export Compatibility`. Require the current local wiki structure, including
`schema.md`, index files, `log.md`, raw source locations, and compiled article locations. Run the
agent from that parent so `<cwd>/.wiki` is the primary wiki. Before querying, explicitly select the
installed read-only `wiki-query` local/query-lite route; do not invoke hub-routed or deep multi-wiki
query behavior. Prove that all writes remain under the call-owned parent and that the configured
hub receives zero writes.

- [x] **Step 2: Ingest immutable raw Markdown**

Ingest every retained `sources/*.md` file as one immutable raw record. The raw wrapper may add the
wiki's required frontmatter, but its source payload must preserve the original MKE Markdown bytes
or a separately delimited exact payload whose SHA-256 equals the manifest `markdown_sha256`.
Require each raw record to preserve its `content_fingerprint` and page or timestamp headings.

- [x] **Step 3: Compile one sourced article**

Compile at least one article whose non-empty `sources:` frontmatter contains exact, existing,
wiki-root-relative paths to the ingested raw records. Run the workflow's index rebuild or stale
check and verify that compilation and indexing operations are represented in the isolated
`log.md`.

- [x] **Step 4: Query one page fact and one timestamp fact**

Before ingest, build a call-owned query oracle from the canonical manifest and JSONL. The retained
v1 proof is frozen at two Sources and three Evidence records. Select the page and timestamp
records deterministically by sorting on
`(locator.kind, content_fingerprint, locator.start, locator.end, evidence_id)` and taking the first
record of each required kind. For each record, choose a public-safe phrase that occurs in exactly
one Evidence text and record the exact `evidence_id`, locator, full JSONL `text` string, its UTF-8
SHA-256, and query prompt. Ambiguous anchors fail before the wiki workflow.

Run exactly two bounded content checks through the installed read-only `wiki-query`
local/query-lite route.
Each prompt requires one closed JSON response with exactly `evidence_text` and `source` keys, where
`source` is the wiki-root-relative compiled article path:

1. ask for the exact source-backed Evidence passage containing the unique page anchor;
2. ask for the exact source-backed Evidence passage containing the unique timestamp anchor.

Parse the response strictly and require the returned `evidence_text` Unicode string to equal the
canonical JSONL `text` string exactly; its UTF-8 SHA-256 must equal the oracle. No whitespace or
Unicode normalization is applied. Require `source` to resolve to the compiled article whose
frontmatter reaches the raw record containing that same locator boundary. A merely plausible
answer, the right Source with the wrong Evidence, extra response fields/prose, or a response filled
from model memory fails. The proof evaluates deterministic source retrieval and linkage, not prose
style or general model quality.

- [x] **Step 5: Prove the exact Evidence return path**

For each query, follow the compiled article `sources:` entry to an ingested raw record. Require the
raw record to preserve the exact `content_fingerprint` and matching `## Page N` or
`## Timestamp START-END ms` boundary. Join that fingerprint to the unchanged export manifest,
select the matching JSONL record, and validate the complete exact `mke.evidence_ref.v1` object.
No wiki-generated identifier may replace Source, Publication, Run, locator, or fingerprint
authority.

- [x] **Step 6: Lint, rehash, record and clean up**

Run wiki lint and require zero Critical issues and zero broken source links. Record unrelated
warnings only in private execution evidence. Rehash the retained export and require the original
tree digest. Verify the isolated `log.md` contains the write-capable initialization, ingest, and
compilation/index-update operations. Because query and non-fixing lint are read-only and forbid
query logging or index rebuilds, bind both queries and the lint result instead to a call-owned
immutable execution record containing prompt digest, strict response digest, selected Evidence
identity, files read, and lint counts; do not append it to the wiki or repository. Remove only the
call-owned wiki, then prove configured-hub impact remains unchanged.

- [x] **Step 7: Produce one closed public-safe aggregate**

```json
{
  "broken_source_link_count": 0,
  "compiled_article_count": 1,
  "configured_hub_impact": "unchanged",
  "evidence_return_count": 2,
  "evidence_schema": "mke.evidence_ref.v1",
  "export_tree_identity": "unchanged",
  "lint_critical_count": 0,
  "page_query_count": 1,
  "query_count": 2,
  "query_scope": "isolated_local_wiki",
  "raw_source_count": 2,
  "schema_version": "mke.compiled_library_export_llm_wiki_proof.v1",
  "status": "passed",
  "timestamp_query_count": 1
}
```

`raw_source_count` is fixed at `2`, matching the live v1 proof receipt and aggregate contract;
`evidence_count` remains fixed at `3` in that upstream authority. Any fixture/count change requires
an authority amendment before execution. Do not persist raw wiki content, query prompts, or model
prose in the repository.

The strict accepted run used two raw Sources and three exact `mke.evidence_ref.v1` records to
compile one sourced article. Its deterministic manifest/JSONL oracle selected exactly one page and
one timestamp query. Each closed response contained exactly `evidence_text` and `source`; exact
Unicode and UTF-8 SHA-256 equality reached the correct raw wrapper, `content_fingerprint`, locator
boundary, manifest leaf, and complete Evidence object. Query and non-fixing lint were read-only and
bound by an immutable call-owned record outside the wiki. The retained tree and configured-hub
identity comparison were unchanged, lint reported zero Critical issues and zero broken source
links, and the call-owned root was removed. The proof compared configured-hub identity without
reading sibling content.

### Task 3: Record the bounded post-release claim

- [x] **Step 1: Write RED documentation contract tests**

Require this exact English sentence in the selected English surfaces:

> The exported Markdown was ingested and compiled in an isolated LLM Wiki workflow, preserving a
> return path to MKE's authoritative content fingerprint and Evidence sidecars for local-Agent use.

Require this exact Chinese sentence in the selected Chinese surfaces:

> 导出的 Markdown 已在隔离的 LLM Wiki 工作流中完成摄取与编译，并保留了回到 MKE 权威
> content fingerprint 和 Evidence sidecar 的路径，供本地 Agent 使用。

Reject claims that LLM Wiki is an MKE dependency, Evidence authority, bundled adapter, automatic
sync, hosted service, production deployment, real-user adoption, general multimodal
understanding, or a capability shipped by the historical v0.1.3 release.

- [x] **Step 2: Run documentation RED**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/scripts/test_release_presentation_audit.py
```

Expected: only the missing bounded compatibility statement and its exact placement fail.

Targeted repair RED observed `3 failed, 132 passed`: the failures were the missing exact Chinese
sentence, historical post-release framing, and full negative claim boundary.

- [x] **Step 3: Update docs and create the review record**

Replace each README's unqualified current statement that compatibility is deferred with a
historically bounded statement: the v0.1.3 generic proof did not verify LLM Wiki compatibility,
while the separate post-release acceptance evidence is recorded below. Add the independent
post-release compatibility-evidence paragraph and update the export how-to. Do not edit the
v0.1.3 release history. Record the execution commit, pre-docs wheel digest, retained export tree
digest, closed aggregate, exact documentation diff, commands, limitations, and cleanup result
without local paths, hostnames, timestamps, query prompts, model prose, or raw wiki content.

- [x] **Step 4: Run docs GREEN and presentation audit**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/scripts/test_release_presentation_audit.py
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
git diff --check
```

Targeted repair GREEN observed `135 passed`; the standalone presentation audit returned
`{"status": "ok", "violations": []}`, and the release-history digest, exact path audit, Markdown
fence balance, public-neutral scan, and `git diff --check` passed.

- [x] **Step 5: Commit the docs/evidence candidate**

Stage only the planned README files, export how-to, documentation test, amended plan, and new
compatibility review. Verify the exact changed-file allowlist and public-neutral scan before the
local commit.

### Task 4: Final committed-candidate verification

- [x] **Step 1: Rebuild and rerun on the committed docs candidate**

`README.md` is package metadata input, so the final docs commit may change wheel bytes. The
authority-amendment commit is the only final-proof source authority. Build a fresh final wheel and
rerun the complete Python 3.12/3.13 proof exactly once with a new retained target. Do not reuse the
diagnostic `56ac968a7e30f478bb06559c370353895a1a06c5` wheel, target, receipt, query oracle, or
aggregate. The pre-docs retained root may be used only as the comparison baseline after it is
freshly descriptor-validated and its raw tree digest is reconfirmed as
`debd814a900141cf52c08126fb7138aa7bae327e432667f9398d829c54f5335a`.

```bash
FINAL_PROOF_ROOT="$(mktemp -d)"
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --retained-export "$FINAL_PROOF_ROOT/retained" \
  --json
```

Independently validate `FINAL_PROOF_ROOT/retained`, record its canonical receipt-file digest,
descriptor-read byte inventory, and final raw tree digest. Run the approved standard-library
semantic comparator and all negative probes against the separately validated pre-docs and final
exports. Only after raw validation and semantic-projection equality pass, build a new query oracle
from the final raw manifest/JSONL and run a fresh isolated wiki workflow from that final raw target.

Require:

- a newly measured final wheel digest, recorded separately from the pre-docs digest;
- the final proof schema, status, interpreter count, export schema, Markdown format, Evidence
  schema, source/evidence counts, and two-query wiki aggregate invariants to match;
- both raw exports to pass closed standalone and descriptor validation;
- exact stable Source and Evidence key-set equality and an equal normalized semantic tree digest;
- separate pre-docs and final raw tree digests, with no cross-run raw-byte equality requirement;
- the final raw tree digest to remain unchanged before transfer, after transfer, and after wiki use;
- two exact Evidence return paths, unchanged configured hub, zero Critical lint issues, zero broken
  source links, and successful cleanup.

The final wheel digest is the candidate authority. Equality with the pre-docs wheel digest is not
required and must not be claimed. The wiki must consume and return final raw Evidence; comparison
aliases are private comparator state and never MKE or wiki authority.

Final Task 4 evidence binds source commit
`e0559816a66957d2964b20d0d08ca1b8ec2f3719` to CPython `3.12.13` and CPython `3.13.12`, fresh
wheel `multimodal_knowledge_engine-0.1.3-py3-none-any.whl` at `309598` bytes with SHA-256
`f45c172685744aeee549c41334106bfd40354e62fbfa00b94ebd69c196746e12`, and canonical receipt
SHA-256 `65e07848d323465cd67cfd647262e0b5ffaee726e1b4411ab398abbb697d2d50`.
The proof returned schema `mke.compiled_library_export_proof.v1`, status `passed`, interpreter
count `2`, and exact same-wheel equality.

Both raw exports passed standalone consumer and independent descriptor validation. The pre-docs
raw tree SHA-256 remained
`debd814a900141cf52c08126fb7138aa7bae327e432667f9398d829c54f5335a`; the final raw tree
SHA-256 is `63495005e7b2fbc466270fe095cf767f0055c8b7325115df3a0daa5717e4a8a0`.
Their two stable Source keys and three stable Evidence keys matched exactly, and both normalized
semantic projections produced SHA-256
`e85a971adaa304e0a4ea3b5249b81e657862d34b831fa1a342501b5ae7a2ef07`. Controlled text,
locator, display-name, media-type, extractor, required-stage, and revision drift probes produced
semantic mismatches; duplicate and inconsistent raw identifier probes failed closed.

The final descriptor inventory is exactly:

```text
evidence/0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd.jsonl  536  fa93f17f917d5f6d8a67f0ca87722fc043c4c57107e2af3ac6e916492e495452
evidence/6c2a57a73ee01976bccfcfe73f3334d8d1675a891ccc5868d68fa2caadf27e3e.jsonl  969  7de643bfee86ae0ddc1e8028060bcb4c1c007c8b058abfc73a87c4aeda98db57
export-manifest.json                                                                    2003  332b17cd4e9795705e82d24e259f39144260f266d0075afe78bdf2a618795450
sources/0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd.md       763  2f39236bdb6c189baac3f5c1a1fd7b46657a577cd455173fe72b90f7c54e95de
sources/6c2a57a73ee01976bccfcfe73f3334d8d1675a891ccc5868d68fa2caadf27e3e.md       858  eb00de8481156ec1e440d0edd4e37e0090a8ee758557d35b56cfc21d5b5a3008
```

The fresh isolated wiki consumed only final raw bytes and compiled one article from two Sources
and three Evidence records. The exact page return path reached Evidence
`ev_042ee266927a42dc88ab101ccaea143b` at page `1`; the exact timestamp return path reached
Evidence `ev_10820df5332549398d706b6243d970ff` at `0-1200` milliseconds. Both returned exact
Unicode text and SHA-256 through the final raw wrapper, `content_fingerprint`, locator boundary,
manifest leaf, and complete `mke.evidence_ref.v1` object. No comparison alias entered the wiki.

Exactly two query-lite processes ran, one per locator kind. A post-query transport encoder was
unavailable after both processes completed, so the processes were not rerun. The immutable wiki
tree and frozen deterministic query program were used to reconstruct the two closed response
bytes, which then passed the independent exact return-path joins. This recovery is retained as a
final-review limitation, not an additional query or a product behavior claim.

The final raw tree retained the same SHA-256 before transfer, after transfer, and after wiki use.
Query and lint made zero wiki writes; lint reported zero Critical issues and zero broken source
links; configured-hub impact was unchanged without sibling-content reads; the call-owned wiki root
was removed. The exact closed aggregate is:

```json
{"broken_source_link_count":0,"compiled_article_count":1,"configured_hub_impact":"unchanged","evidence_return_count":2,"evidence_schema":"mke.evidence_ref.v1","export_tree_identity":"unchanged","lint_critical_count":0,"page_query_count":1,"query_count":2,"query_scope":"isolated_local_wiki","raw_source_count":2,"schema_version":"mke.compiled_library_export_llm_wiki_proof.v1","status":"passed","timestamp_query_count":1}
```

- [x] **Step 2: Run scoped local verification**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/scripts/test_release_presentation_audit.py \
  tests/scripts/test_compiled_library_export_consumer.py \
  tests/scripts/test_compiled_library_export_proof.py \
  tests/interfaces/test_cli_library_export.py
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
git diff --check
git status --short
```

The authoritative same-wheel proof and retained target are the single fresh invocation from Step
1; do not invoke it again against the already populated final target.

This docs/evidence PR does not locally repeat unrelated runtime, retrieval, OCR, Ruff, Pyright, or
build gates. Normal PR CI remains the repository-wide regression authority.

The exact scoped suite passed with `258 passed, 5 warnings`; the standalone presentation audit
returned `{"status":"ok","violations":[]}`. `git diff --check` and the clean pre-closure status
gate passed.

- [x] **Step 3: Authority review and stop**

Review the exact final docs/evidence diff, pre-docs and final wheel identities, both closed raw
validations, stable-key and normalized semantic-projection equality, final raw-tree immutability,
closed wiki aggregate, isolated log evidence, and cleanup proof. Stop with a clean local branch.
Push, PR creation, Ready, merge, version bump, tag, GitHub Release, registry publication,
deployment, direct-audio implementation, and production OCR remain separate authorization gates.

Final actual-diff review accepted exact branch candidate
`c8df4bb9dae5c6ca16b5ec392c78fe08bc773c07` over base
`136e04a8213e126e88d352092da6f886563ad2d0` as clean with no actionable finding. The reviewed
branch changed exactly six approved files with 808 insertions and 168 deletions, and the worktree
was clean.

Independent review reran the call-owned semantic comparator and confirmed both raw validations,
two stable Source keys, three stable Evidence keys, normalized semantic tree SHA-256
`e85a971adaa304e0a4ea3b5249b81e657862d34b831fa1a342501b5ae7a2ef07`, and rejection of every
drift and duplicate or inconsistent-identifier probe. It independently recomputed final raw tree
SHA-256 `63495005e7b2fbc466270fe095cf767f0055c8b7325115df3a0daa5717e4a8a0`
and execution-record SHA-256
`6557af1edb39dcb2a019c13e976216c0fc74b5bd01a4a6050e74430baaf5b6a2`, including the exact
14-field aggregate. The native scoped command returned `258 passed, 5 warnings`; presentation
audit returned status `ok` with zero violations; `git diff --check` passed; and
`docs/releases/v0.1.3.md` remained SHA-256
`85aa1ba71cfc9df18ccd8655d7f3de82434c77cff0b8729a53968471fc5e22e0`.

The disclosed post-query response reconstruction is accepted as a bounded non-blocking execution
limitation. The two query processes were not rerun. The frozen deterministic query program,
unchanged wiki tree, closed canonical response encoding, and exact downstream Evidence joins
uniquely determine the reconstructed response bytes. This acceptance does not strengthen the
claim beyond isolated ingest and compile plus a preserved return path, and it establishes no model
quality, general query capability, product integration, or production behavior.

## Not In Scope

- Product code, schemas, dependencies, workflows, export behavior, or release identity.
- An LLM Wiki adapter, configured-hub sync, watcher, plugin, or bidirectional authority.
- General answer-quality evaluation or model benchmarking.
- Rewriting the v0.1.3 release note or claiming compatibility was shipped by v0.1.3.
- Direct audio, production OCR, Codex integration, or retrieval promotion.

## Completion Boundary

Local plan execution is accepted because the final committed docs/evidence candidate has a fresh
final wheel, a fresh retained export, a passed isolated-wiki aggregate, two exact Evidence return
paths, closed raw validity for both runs, equal stable-key sets and normalized semantic tree digest
across the pre-docs and final runs, an immutable final raw tree throughout transfer and wiki use,
unchanged configured hub, zero Critical lint issues, zero broken source links, scoped local gates,
a clean worktree, and an accepted authority review. Normal PR CI and all remote actions remain PR
handoff gates and are not completed by this local acceptance. Failure at a later gate preserves the
generic export result and withholds only the LLM Wiki compatibility claim.
