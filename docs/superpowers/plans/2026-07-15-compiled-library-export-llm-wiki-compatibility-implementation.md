# Compiled Library Export LLM Wiki Compatibility Implementation Plan

Status: engineering-reviewed follow-up plan; core lineage and post-merge gates are satisfied, and
Task 1 is authorized from a clean current compatibility branch containing the core merge.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute the
> project-owned mechanical and verification steps. The authority window performs the isolated
> LLM Wiki workflow and supplies only its public-safe aggregate back to the project worker.

**Goal:** Prove that a merged Compiled Library Export can be ingested, compiled, queried, and
traced back to exact MKE Evidence in an isolated LLM Wiki workflow, then record the bounded claim
without changing MKE runtime behavior.

**Architecture:** Build one fresh installed-wheel export from the current clean compatibility branch
commit containing the core export merge, transfer only the validated export and closed receipt to a
call-owned compatibility workspace, run the existing agent-driven LLM Wiki workflow against a new
local `.wiki/`, and join the compiled article back to MKE's unchanged manifest and JSONL through
`content_fingerprint`. MKE remains the provenance authority; the wiki is a downstream synthesized
view.

**Tech Stack:** Python 3.12/3.13, the merged `compiled_library_export_proof.py`, standard-library
hashing and JSON validation, the installed LLM Wiki agent workflow, Markdown documentation tests,
Pytest, Ruff, Pyright, Hatch/uv, and Git.

## Entry Gate

- Retain `5d707cfcc98da8ce76d31238c14158cd78b03803` as the core Compiled Library Export
  lineage authority. Require it to remain an ancestor of the current clean compatibility branch.
- Require the core Compiled Library Export PR and its expected CI, CodeQL, and compiled-library
  proof checks to be complete.
- Require `main == origin/main`, a clean primary worktree, and no open core-export repair PR.
- Create a new isolated docs/evidence branch and worktree from the current clean `main`, then build
  and prove the exact compatibility branch commit that contains the core lineage authority.
- Re-read the merged public spec, core plan, implementation review, export how-to, proof how-to,
  and this compatibility plan.
- Do not reuse a pre-merge retained export, wheel, receipt, wiki, or candidate worktree.
- Stop if the merged command, schemas, proof receipt, or public claim boundary differs from this
  plan. Update the plan through authority review before continuing.

### Targeted Authority Amendment

The merged producer, its retained-export tests, and the export how-to already agree on the
`compiled-library/` directory name. This amendment aligns the compatibility evidence procedure with
that established contract and with the current package-bearing branch while retaining the core
merge as lineage authority. It authorizes no runtime, schema, producer, test, dependency, workflow,
or release-identity change.

## Global Constraints

- This is a docs/evidence PR. Do not modify `src/mke`, dependencies, lockfiles, workflows, product
  scripts, export schemas, fixtures, retrieval artifacts, OCR evidence, or release identity.
- Use only a fresh public-safe synthetic export produced from the exact clean compatibility branch
  commit containing the core lineage authority.
- Never write to a configured wiki hub. Create and remove only a call-owned isolated `.wiki/`.
- Do not add LLM Wiki as a runtime, development, CI, or documentation build dependency.
- Do not invent `/wiki:*` shell commands. Use the installed agent workflow and its documented
  natural-language operations.
- Do not add a network, hosted API, or external LLM requirement to MKE runtime, CI, or export
  consumption. The authority window's already-configured agent workflow remains outside MKE.
  Private source material, local paths, hostnames, tokens, raw model output, and timestamps may not
  enter repository files.
- The MKE export tree is immutable input. Any byte drift withholds the compatibility claim.
- A failed compatibility proof does not invalidate the generic export contract. Classify the
  downstream gap and stop; a product-specific adapter needs a new design.
- Version bump, v0.1.3 release notes, tag, GitHub Release, registry publication, and deployment are
  separate operations after this PR.

## Data Flow

```text
current compatibility branch commit containing core merge
      |
      | build one wheel, Python 3.12 + 3.13 generic proof
      v
validated retained export + closed proof receipt
      |
      | immutable raw Markdown ingest
      v
isolated local .wiki/
      |
      +--> compiled article --> bounded page query
      +--> compiled article --> bounded timestamp query
      |
      | sources frontmatter -> raw note -> content_fingerprint
      v
unchanged export-manifest.json + evidence/*.jsonl
      |
      v
exact mke.evidence_ref.v1 return path
```

## Planned Repository Files

- Modify `README.md` and `README_CN.md` only to add the accepted bounded compatibility statement.
- Modify `docs/how-to/export-compiled-library.md` to explain the downstream return path and
  authority boundary.
- Modify `tests/evaluation/test_compiled_library_export_documentation.py` to require the exact
  bounded statement and reject stronger claims.
- Modify this plan's public copy only to check completed steps and record accepted evidence.
- Create
  `docs/superpowers/reviews/2026-07-15-compiled-library-export-llm-wiki-compatibility-review.md`
  after the proof actually succeeds.
- Run but do not modify `scripts/release_presentation_audit.py` and its tests unless live code shows
  the merged core audit cannot distinguish the approved sentence from an authority overclaim. Any
  required behavior change is a hard stop for a separate review, not an assumed docs-only edit.

---

### Task 1: Produce a fresh retained export from the current compatibility branch

**Files:** no tracked changes.

- [ ] **Step 1: Verify the exact merged baseline and interpreter authority**

Record the core lineage SHA, exact compatibility branch source commit, and exact Python 3.12/3.13
interpreter paths. Require distinct real interpreters and a clean source worktree. Run the core
documentation tests and generic proof tests before building retained evidence.

- [ ] **Step 2: Run one fresh same-wheel proof with retained output**

```bash
PROOF_ROOT="$(mktemp -d)"
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --retained-export "$PROOF_ROOT/retained" \
  --json
```

Require one wheel digest across both interpreters and exact proof aggregate status `passed`.
Require the retained root to contain only `compiled-library/` and `proof-receipt.json`.

- [ ] **Step 3: Independently validate retained authority**

Run the standalone consumer against the retained export and original proof inputs. Verify receipt
schema, counts, wheel digest, export tree inventory, canonical manifest/JSONL, and every file
digest. Compute and record one deterministic tree digest over normalized relative path, byte count,
and SHA-256 tuples. Reject symlinks, special files, unknown entries, or local/private receipt data.

- [ ] **Step 4: Hard stop for authority-window compatibility execution**

Transfer only the retained export location, closed receipt values, tree digest, and required
natural-language workflow. Do not ask the project worker to initialize or operate LLM Wiki.

### Task 2: Run isolated LLM Wiki compatibility proof

**Owner:** authority window using the `wiki` skill. No tracked project write during this task.

- [ ] **Step 1: Establish an isolated wiki without configured-hub impact**

Create a new call-owned temporary parent and initialize a local wiki titled
`Compiled Library Export Compatibility`. Record the configured hub identity before and after only
as a private comparison; never copy it into public evidence. Confirm all writes remain under the
call-owned parent.

- [ ] **Step 2: Ingest immutable raw Markdown and compile one sourced article**

Ingest each retained `sources/*.md` as an immutable raw record while preserving Markdown. Compile
at least one article whose non-empty `sources:` frontmatter names the ingested raw records. Rebuild
or stale-check derived indexes according to the installed workflow.

- [ ] **Step 3: Query page and timestamp facts**

Run exactly two bounded content checks: one answer backed by a page locator and one answer backed
by a timestamp locator. The proof checks retrieval of the expected source-backed facts, not prose
style or model quality.

- [ ] **Step 4: Prove the return path to authoritative Evidence**

For each query, follow the compiled article to an ingested raw record. Require the raw body to
retain the exact `content_fingerprint` and its `## Page N` or
`## Timestamp START-END ms` boundary. Join that fingerprint to the unchanged MKE manifest and
JSONL, then recover and validate the exact `mke.evidence_ref.v1` record.

- [ ] **Step 5: Lint, rehash, and clean up**

Run wiki lint and require zero Critical issues and zero broken source links. Report unrelated
warnings without turning them into MKE runtime requirements. Rehash the retained export and require
the original tree digest. Remove only the call-owned wiki and confirm configured-hub impact is
unchanged.

- [ ] **Step 6: Produce the closed public-safe aggregate**

```json
{
  "compiled_article_count": 1,
  "configured_hub_impact": "unchanged",
  "evidence_return_path": "preserved",
  "export_byte_identity": "unchanged",
  "ingested_source_count": 2,
  "lint_critical_count": 0,
  "query_count": 2,
  "schema_version": "mke.compiled_library_export_llm_wiki_proof.v1",
  "status": "passed"
}
```

Counts are runtime-measured and may differ only where explicitly data-dependent. The schema,
field set, two queries, zero Critical lint issues, unchanged hub, unchanged export, and preserved
Evidence return path are fixed. Do not persist raw wiki content or model output.

### Task 3: Record the bounded compatibility claim

- [ ] **Step 1: Write RED documentation contract tests**

Require this exact public sentence in the selected English/Chinese surfaces:

> The exported Markdown was ingested and compiled in an isolated LLM Wiki workflow, preserving a
> return path to MKE's authoritative content fingerprint and Evidence sidecars for local-Agent use.

Reject claims that LLM Wiki is an MKE dependency, Evidence authority, bundled integration, hosted
service, production deployment, real-user adoption, or general multimodal understanding.

- [ ] **Step 2: Run documentation RED**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/scripts/test_release_presentation_audit.py
```

Expected: only the missing accepted compatibility statement fails.

- [ ] **Step 3: Update docs and create the compatibility review**

Document the two-query bounded proof, downstream synthesis boundary, Evidence return path, fixed
synthetic input, local isolated workflow, and non-production limitations. The review records the
core merge SHA, wheel digest, retained tree digest, closed aggregate, exact docs diff, and commands,
without local paths, hostnames, timestamps, or raw content.

- [ ] **Step 4: Run docs GREEN and presentation audit**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/scripts/test_release_presentation_audit.py
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
git diff --check
```

- [ ] **Step 5: Commit the docs/evidence PR candidate**

Stage only the planned documentation, documentation test, compatibility plan, and compatibility
review files. Verify the exact changed-file allowlist before committing.

### Task 4: Final verification and external-action gate

- [ ] **Step 1: Rerun the isolated proof on the committed candidate**

Tracked docs do not change the installed wheel bytes, but the compatibility review must still bind
the final commit. Run one fresh retained-export proof and the complete isolated LLM Wiki workflow
again after the docs/evidence commit. Require the same closed aggregate and byte-identical export.

- [ ] **Step 2: Run repository verification**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/scripts/test_release_presentation_audit.py \
  tests/scripts/test_compiled_library_export_consumer.py \
  tests/scripts/test_compiled_library_export_proof.py
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" --python "$PYTHON313" --json
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
git diff --check
git status --short
```

Because this PR is docs/evidence-only and the retained export plus wiki workflow are rerun on the
final commit, unrelated full runtime, retrieval, OCR, build, Ruff, and Pyright gates are not
repeated locally. The normal PR CI remains authoritative for repository-wide regressions.

- [ ] **Step 3: Authority review and stop**

The planning/review authority reviews the exact docs/evidence diff and proof aggregate. Stop with
a clean local branch.
Do not push, create or ready a PR, merge, bump version, create release notes, tag, publish, deploy,
or begin production OCR without separate authorization.

## NOT in scope

- Product code, schemas, dependencies, workflows, and export behavior: owned by the merged core PR.
- LLM Wiki adapter or direct hub sync: no evidence of need and would create downstream coupling.
- General answer-quality evaluation: this proof tests compatibility and provenance return only.
- v0.1.3 publication: separate release planning and authorization after both PRs merge.

## Completion Boundary

This plan is complete only when the final committed docs/evidence candidate has a fresh retained
export, isolated wiki aggregate `passed`, exact Evidence return path, unchanged export bytes,
unchanged configured hub, zero Critical lint issues, full repository gates, clean worktree, and an
accepted authority review. Failure preserves the generic export result and withholds only the LLM
Wiki compatibility claim.
