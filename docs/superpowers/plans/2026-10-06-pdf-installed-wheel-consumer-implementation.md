# PDF Installed-Wheel Consumer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan in the current delivery context. Steps use checkbox syntax for tracking.

**Goal:** Prove the merged PDF observation route through one installed wheel, fresh stores and independent consumers on available Python 3.12 and 3.13 runtimes.

**Architecture:** Build one wheel from the clean, exact merge commit. A standalone controller verifies its module bytes against that commit, installs only the locked core dependencies into two fresh environments, and copies the public consumers and current fourteen-tool expectation from the same commit. The existing native consumer owns CLI/MCP/export identity and exact UTF-8 verification; a separate stdlib export process supplies an independent success/failure boundary. Missing locked dependency artifacts may be prepared in task-owned isolation before the offline proof; no runtime or dependency version is substituted.

**Tech Stack:** Existing uv, locked PyMuPDF and official MCP SDK; Python stdlib controller and validators. No new dependency.

**Spec:** [PDF observation design](../specs/2026-10-05-pdf-extraction-observation-design.md) and the approved C1 delivery brief below. C1 adds installation evidence, without changing that design's product behavior.

Status: Completed locally on 2026-10-06. After the coordinating owner's explicit second resume,
one complete controller run exited 0 with both fresh Python 3.12.13/3.13.13 native consumers,
independent Export v3 consumers and negative exit boundaries passing. It reused the same wheel,
original lock and prepared cache; no rebuild, runtime download or extra preflight was performed.
The three earlier failed attempts and their diagnostics remain retained. Their partial receipts
are not combined into the successful receipt. C1 remote delivery requires separate authorization.

## Approved Delivery Brief

- Base: merged `main` commit `2426847e53274d7bb14de12428b93107e502e79e` from PR #134, after exact-merge CI succeeds. Its tree equals reviewed candidate `562019ea4d9bf15131fdf320188a88a174f32f6c`.
- Delivery owner: current MKE controller. In-scope implementation details and local acceptance are authorized; remote delivery of this C1 candidate requires separate approval.
- Build from that exact clean merge; install the same wheel in fresh task-owned environments and create fresh synthetic PDF stores. Use independent CLI and stdio MCP server processes, the official SDK, Source v2, complete Evidence reads/citations, Export v3 and the independent stdlib validator.
- Capture wheel SHA-256, actual interpreter and dependency versions, declared/generated fixture identity, Source/Run/Publication/revision and measured response sizes. Assert the current fourteen-tool inventory explicitly.
- Check both declared runtimes if already available. Missing runtimes are an environment limit; do not download or silently substitute a runtime. Necessary original-lock dependency installation in task-owned isolation is authorized, including hash-checked preparation of missing cached artifacts.
- First deliver a reproducible local entry, bounded result, necessary documentation/checks and semantic commits. New version, tag, Release, hosted delivery and M2 are outside this authorization.

## Global Constraints

- Product runtime, required processing stages, SQLite authority, legacy contracts, retrieval defaults and frozen historical fixtures remain unchanged.
- `requires-python = ">=3.12,<3.14"`; use existing installed interpreters only.
- Core dependencies come from unchanged `uv.lock`; offline installation uses hash-checked locked requirements and wheel installation uses `--no-deps`. A cold cache may be prepared with those same hash-checked requirements before the proof; dependency preparation network use must be recorded separately from the offline proof/runtime.
- Never substitute repository source or `PYTHONPATH` for installation. Run isolated Python and clear inherited Python import state; verify the imported package is the selected environment's site-packages and its bytes match the wheel.
- Keep raw commands, paths, PDFs, stores, exports and diagnostics in ignored/task-owned directories. Public receipts contain only declared synthetic identities, versions, digests and bounded aggregates.
- Preserve the primary checkout and the C0/M1 recovery worktree. Reuse unchanged prior tests and installation evidence; run the new installed consumer boundary.
- No OCR, image understanding, autonomous model/content-quality claim, paid provider, dependency/lock change, publication or deployment.

## Review Focus

- Same version with different wheel module bytes must fail before installation; version strings alone do not bind provenance.
- Non-package wheel members are restricted to the canonical metadata inventory; console entry points must match the committed project before installation. Extra modules, startup files and unbound script payloads must fail.
- Host `PYTHONPATH`, an editable/source import, wrong interpreter or wrong dependency versions must never count as installed-wheel evidence.
- A copied historical twelve-tool expectation must fail rather than hide the current fourteen-tool contract.
- A malformed export and a normal native public error must produce bounded failure receipts and nonzero exits.
- A missing interpreter/cache, reused workspace or changed wheel during the proof must fail without overwriting existing evidence or changing authorization.

### Task 1: Reproducible Installed Consumer Controller

**Files:**
- Create: `scripts/pdf_extraction_observation_wheel_proof.py`
- Create: `tests/scripts/test_pdf_extraction_observation_wheel_proof.py`
- Reuse unchanged: `scripts/pdf_extraction_observation_consumer.py`, `scripts/source_discovery_consumer.py`, `scripts/compiled_library_export_consumer_v2.py`, `scripts/compiled_library_export_consumer_v3.py`, `scripts/build_compiled_library_viewer.py`

**Interfaces:**
- Consumes: explicit `--wheel`, full `--source-commit`, two repeatable `--python` paths and fresh `--work-dir`; Git objects from the selected repository, unchanged lock and existing uv cache.
- Produces: `mke.pdf_extraction_observation_wheel_proof.v1` JSON receipt, exit 0 only after both installed consumers and failure boundaries pass; retained private diagnostics and native artifacts.

- [x] **Step 1: Add behavioral RED coverage**

Exercise the actual script CLI and validation functions. Hand-built small wheels and committed local Git fixtures must reject missing/extra/changed package modules despite equal metadata versions. Reused workspaces and invalid inputs must exit nonzero with bounded codes. Identity validation must reject a source-tree import, wrong executable and wrong interpreter minor. A controlled child command must verify inherited Python import variables are absent. Do not mock the consumer's semantic result.

- [x] **Step 2: Run the new tests and inspect RED**

Run the existing locked test interpreter against `tests/scripts/test_pdf_extraction_observation_wheel_proof.py`; expected failures are the missing proof entry/validation behavior, not fixture or import mistakes.

- [x] **Step 3: Implement the smallest controller**

Verify wheel/source bytes and unchanged config/lock; export core locked requirements; create fresh environments with downloads disabled; hash-check offline dependency sync, install the supplied wheel with no dependencies, and check installed identity/versions. Copy the five consumer scripts and current fixture from the selected Git commit into each external case. Execute the existing consumer with `-I -B`, the independent v3 validator, a malformed-export rejection and native unknown-Source rejection. Bind synthetic PDF bytes to the native fingerprint and recheck the wheel digest at the end.

- [x] **Step 4: Run GREEN and focused static checks**

Expected: new tests pass; Ruff passes for the changed script/tests; Pyright passes for affected typed code. Existing product inputs are unchanged; record prior full-suite binding instead of repeating it.

- [x] **Step 5: Commit the intentional controller and tests**

Stage exact paths only. Commit message: `test: prove PDF observations from an installed wheel`.

### Task 2: Exact-Merge Dual-Python Evidence And Documentation

**Files:**
- Modify: `docs/how-to/observe-pdf-extraction-scope.md`
- Modify: this plan's checklist/status
- Create: `docs/superpowers/reviews/2026-10-06-pdf-installed-wheel-consumer-review.md`

**Interfaces:**
- Consumes: Task 1 controller, the wheel built at the clean exact merge, available 3.12/3.13 interpreters, preserved C0/M1 CI/review evidence.
- Produces: two fresh installed consumer results for one wheel, reproducible operator command, truthful local acceptance and a specific candidate for approval.

- [x] **Step 1: Run the actual two-runtime installation proof**

Run the controller once with the same exact-merge wheel and installed 3.12/3.13 paths. Expected: both results use fourteen tools, verify complete UTF-8/citation identity and Export v3, record actual dependencies/interpreters/fixture hashes, and confirm failure exits. If the same costly goal fails twice, return for a route decision.

- [x] **Step 2: Document the verified shortest route and limits**

Add exact build/proof commands, retained artifacts, failure meaning, verification date and completion signal to the existing guide. Keep browser file-origin/clipboard limits and release/publication limits separate from this installed proof. Record wheel/source/test binding without raw private paths or execution logs.

- [x] **Step 3: Review and verify the final local candidate**

Run affected proof/packaging/consumer checks, required docs checks, Ruff, Pyright and `git diff --check`. Obtain one fresh bounded review of the new controller and evidence; fix substantive findings with regression coverage. Do not repeat unchanged provider-free full suites or old installation proofs merely for workflow bookkeeping.

The code review binds the unchanged controller/test HEAD `11d78cab4b4f3abeb83fe444b834201a597a94f0`.
The delivery controller verified the later complete single-run receipt under explicit resume;
see the [bounded review and evidence](../reviews/2026-10-06-pdf-installed-wheel-consumer-review.md).

- [x] **Step 4: Commit documentation and return once for candidate approval**

Report exact local HEAD/base/branch, wheel hash, both actual results, checks, limitations and documentation impact. No C1 push, PR, merge, version or Release without new specific authorization.


## M3: Single-Source Installed-Wheel Follow-up

Approved follow-up, 2026-10-08. Tasks 1 and 2 and their C1 evidence remain completed history;
this follow-up starts at Task 3. M3 status: implementation in progress, native acceptance pending.

**Goal:** Build one commit-bound wheel and prove the single-Source CLI Ask and official SDK
consumer through that wheel in fresh Python 3.12/3.13 environments and Libraries.

**Architecture:** Reuse `consumer_source_pack_proof.py` for the clean commit, immutable tracked
snapshot and incrementally bounded process execution; reuse `consumer_source_pack_client.py`
for MCP schema checks, deadlines and stderr capture. Reuse the C1 wheel/module, installed-origin,
interpreter and dependency validators. A separately named external consumer and synthetic source
pack exercise the new boundary without changing either historical proof output.

**Spec:** [ADR-0017](../../decisions/0017-single-source-evidence-only-cli-ask.md),
[single-Source design](../specs/2026-10-07-source-scoped-ask-design.md), and this approved follow-up.
Base is clean `main` `55e7d42637624c5733f98e7483d32bd5f46b6356`. The delivery controller may decide
in-scope implementation details and local acceptance. Hosted delivery needs separate approval.

### M3 Constraints And Acceptance

- Use one stable clean commit for the tracked build snapshot, unchanged lock, copied scripts,
  current fifteen-tool schemas and newly named fixtures. Reject HEAD/dirty-input changes before
  or after the proof. Build exactly one wheel and use its same SHA-256 in both runtimes.
- Install hash-checked original-lock core dependencies, then the wheel with `--no-deps`, into
  fresh owned environments. Use already available Python 3.12/3.13; do not download runtimes.
  Prefer the provisioned cache, and record any authorized locked cache preparation separately.
- External consumers run with `-I -B`, no inherited Python import state and no repository import
  path. Assert installed site-packages/module bytes, selected interpreter, dependency versions,
  wheel origin and copied consumer asset digests. The build controller may use repository code.
- Discover and explicitly select Source/active Publication, retain revision/Run/fingerprint in
  CLI Ask and all references, and independently verify complete UTF-8 bytes, SHA-256 and excerpt
  windows through `source_evidence_consumer.py`. CLI and SDK must select the same first page.
- Native cases include positive `more_available`, positive `complete`, selected-source empty
  despite an unrelated match, mismatched identity, stale Publication, replacement during reads
  and controlled corruption of a native read payload. Failure processes exit 1 with one bounded
  redacted failure object and no successful prefix/partial references.
- MCP inventory stays fifteen; no MCP Ask or product behavior/authority/lock/fixture rewrite.
  Use the explicit existing `current` retrieval strategy in this installation cell. Existing
  four-strategy checkout evidence is retained rather than rerun as installation evidence.
- Build, installation and consumer subprocess streams are capped while drained (2 MiB per stream), SDK server stderr
  is capped at 64 KiB, tool/startup deadlines are 15 seconds, and each consumer workflow has a
  90-second deadline below the 180-second controller command deadline. Parsed SDK envelopes
  retain the existing 32,768 canonical-byte limit; raw stdout framing remains owned by the SDK.
- Preserve task-owned diagnostics on failure. Successful temporary build/source/env/consumer
  data are removed before emitting a successful proof receipt; retain the wheel, bounded receipt
  and private diagnostic logs. No overwrite or cleanup of prior resources is allowed.
- Freeze and review the candidate before one complete native run. A failure is classified as
  product, harness or environment using retained diagnostics before further costly work; do not
  automatically retry it. Local candidate and semantic commits are authorized, remote delivery,
  Release/tag/deploy, providers, Docker and other frozen goals are outside M3.

### M3 Review Focus

1. Correct version but wrong module bytes, dependency, interpreter or installation origin must fail.
2. A source-tree import, inherited Python path, changed consumer asset or reused Library must fail.
3. Empty selected scope must not admit stronger unrelated Evidence or silently change the pair.
4. A replaced Publication or corruption after a verified read prefix must discard the entire result.
5. Multi-byte text, incomplete first pages, oversized output and cleanup failure must remain explicit.

### Task 3: Installed Single-Source Consumer And Separate Assets

**Files:** Create `scripts/source_evidence_installed_consumer.py`,
`scripts/generate_source_evidence_installed_fixtures.py`,
`tests/fixtures/source-evidence-installed-v1/{manifest.json,selected.pdf,other.pdf}`,
`tests/scripts/test_source_evidence_installed_consumer.py`.
Reuse unchanged `scripts/source_evidence_consumer.py` and `scripts/consumer_source_pack_client.py`.

**Interfaces:** `main(argv=None) -> int` accepts installed `--mke`, fresh `--work-dir`, copied
`--assets` and `--schemas`, and `--case flow|mismatch|stale|read_failure|citation_failure`.
`flow` creates a fresh Library and returns `mke.source_evidence_installed_consumer.v1` with passed
status only after discovery, scoped CLI Ask and complete citation verification. Negative cases
use that owned Library and emit a failed receipt/exit 1 only after the intended real boundary is
exercised. Copies of the example and source-pack client reside beside this external script.

- [x] Add RED tests for fresh Library creation, first-page/complete/empty selection, lineage,
  multi-byte exact reads, wrong/stale pair and failure after a verified prefix. Test real CLI/SDK
  behavior with the development runtime; these are focused checkout checks, not native acceptance.
- [x] Implement `load_assets`, `run_flow`, `run_negative` and bounded SDK sessions using the existing
  consumer validators/deadlines. Independently bind both fixture digests to discovered scopes.
- [x] Run `PYTHONPATH=src UV_NO_SYNC=1 UV_OFFLINE=1 uv run --locked --offline --no-sync python -m pytest -q tests/scripts/test_source_evidence_installed_consumer.py tests/scripts/test_source_evidence_consumer.py`.
  Expected: all pass; no new skip. Commit only the new consumer, its tests and separately named assets.

### Task 4: One-Build Dual-Runtime Controller

**Files:** Create `scripts/source_evidence_wheel_proof.py` and
`tests/scripts/test_source_evidence_wheel_proof.py`; modify this plan's M3 checklists.
Reuse source-pack bounded execution/snapshot and unchanged C1 validation helpers. The bounded
helper's optional private exception fields retain captured prefixes on timeout/overflow; its
historical stdout schemas and failure codes remain unchanged.

**Interfaces:** `run(args) -> dict` and `main(argv=None) -> int` accept `--source-commit`, two
`--python` paths and a fresh external `--work-dir`. Output is independently named
`mke.source_evidence_wheel_proof.v1`; existing strict receipts are untouched. Each runtime gets
one fresh installed environment and Library. The controller runs flow plus all negative processes,
checks exact schemas/exit statuses and cleans successful temporary resources before output.

- [x] Add RED tests for dirty/changed commit, missing/wrong interpreter, existing/repository work
  directory, bad consumer receipts and failure/no partial candidate; exercise bounded subprocess
  failures and diagnostic retention. Reuse existing wheel/import/origin validator tests.
- [x] Implement one tracked snapshot/build and hash-checked installation, validate module/dependency/
  interpreter/origin identity, copy only commit-bound consumer assets, run each boundary with the
  installed Python and CLI, and revalidate source/wheel/lock before successful cleanup and receipt.
- [x] Run focused new controller tests plus `tests/scripts/test_pdf_extraction_observation_wheel_proof.py`
  and `tests/scripts/test_consumer_source_pack_proof.py`; expected all affected cases pass with only
  existing platform skips. Run Ruff/Pyright and diff checks. Commit the intentional controller/tests.

### Task 5: Frozen Candidate, Native Acceptance And Public Route

**Files:** Update `docs/how-to/ask-within-one-source.md`, add
`docs/how-to/run-source-evidence-wheel-proof.md`, update `docs/README.md` and this plan.

- [x] Document the shortest build-once proof command and exact completion/failure signals before
  candidate freeze; link the new installed boundary without erasing historical checkout evidence.
- [x] Complete one fresh bounded whole-branch review, resolve consequential findings with regression
  coverage, run affected/static/docs checks and commit the stable candidate.
- [ ] Run the complete controller once with that exact clean commit and provisioned 3.12/3.13 paths.
  Expected: one wheel, both native flows and all failure exits pass, same installed wheel digest,
  truthful dependency/interpreter identities and successful owned-temp cleanup.
- [ ] Add the actual result/date/binding and limitations to the guide and mark M3 explicitly complete.
  Documentation-only closeout must retain the native input binding. Report local final HEAD, native
  source commit, wheel hash, checks, diagnostics/limits and remaining hosted authorization once.

M3 does not prove a Release, empty-machine/offline cache provisioning, semantic answers, complete
original-media understanding, OS sandboxing or production adoption.
