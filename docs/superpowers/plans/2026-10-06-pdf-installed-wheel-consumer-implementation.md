# PDF Installed-Wheel Consumer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan in the current delivery context. Steps use checkbox syntax for tracking.

**Goal:** Prove the merged PDF observation route through one installed wheel, fresh stores and independent consumers on available Python 3.12 and 3.13 runtimes.

**Architecture:** Build one wheel from the clean, exact merge commit. A standalone controller verifies its module bytes against that commit, installs only the locked core dependencies into two fresh environments, and copies the public consumers and current fourteen-tool expectation from the same commit. The existing native consumer owns CLI/MCP/export identity and exact UTF-8 verification; a separate stdlib export process supplies an independent success/failure boundary. Missing locked dependency artifacts may be prepared in task-owned isolation before the offline proof; no runtime or dependency version is substituted.

**Tech Stack:** Existing uv, locked PyMuPDF and official MCP SDK; Python stdlib controller and validators. No new dependency.

**Spec:** [PDF observation design](../specs/2026-10-05-pdf-extraction-observation-design.md) and the approved C1 delivery brief below. C1 adds installation evidence, without changing that design's product behavior.

Status: Controller and targeted provenance/isolation/negative-fixture repairs verified locally on
2026-10-06; full C1 remains incomplete. Two initial attempts stopped before native ingestion (cold
locked cache, then an invalid optional-metadata assumption). After explicit resume, both installation
preflights passed; the complete run passed the 3.12 native and independent export consumers, then
failed because its negative-fixture setup used the wrong manifest filename. The corrected setup
passes its regression and actual targeted failure-exit checks. The 3.13 native case and a complete
successful receipt remain pending a new route decision. All failed runs/diagnostics are retained.

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

- [ ] **Step 1: Run the actual two-runtime installation proof**

Run the controller once with the same exact-merge wheel and installed 3.12/3.13 paths. Expected: both results use fourteen tools, verify complete UTF-8/citation identity and Export v3, record actual dependencies/interpreters/fixture hashes, and confirm failure exits. If the same costly goal fails twice, return for a route decision.

- [ ] **Step 2: Document the verified shortest route and limits**

Add exact build/proof commands, retained artifacts, failure meaning, verification date and completion signal to the existing guide. Keep browser file-origin/clipboard limits and release/publication limits separate from this installed proof. Record wheel/source/test binding without raw private paths or execution logs.

- [ ] **Step 3: Review and verify the final local candidate**

Run affected proof/packaging/consumer checks, required docs checks, Ruff, Pyright and `git diff --check`. Obtain one fresh bounded review of the new controller and evidence; fix substantive findings with regression coverage. Do not repeat unchanged provider-free full suites or old installation proofs merely for workflow bookkeeping.

- [ ] **Step 4: Commit documentation and return once for candidate approval**

Report exact local HEAD/base/branch, wheel hash, both actual results, checks, limitations and documentation impact. No C1 push, PR, merge, version or Release without new specific authorization.
