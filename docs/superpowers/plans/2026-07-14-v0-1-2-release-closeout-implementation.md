# v0.1.2 Release Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before claiming a gate passed. Steps use checkbox (`- [ ]`) syntax for tracking.

Status: pending authoritative engineering review. Implementation must not start until this committed plan is cleared and explicitly dispatched.

Planning base: `main@16fae017ced5fe67da3fae4a01f26e9e9f1084aa`.

Approved design: [v0.1.2 Release Closeout Design](../specs/2026-07-14-v0-1-2-release-closeout-design.md).

**Goal:** Prepare a locally verified `v0.1.2` release candidate whose package identity, Evidence-provenance presentation, external-consumer proof, downstream candidate boundary, evaluation identities, and installed-wheel evidence agree without publishing it.

**Architecture:** Keep runtime and public contracts unchanged. Treat the release as an ordered identity-and-evidence closure: define the `0.1.2` contract in tests, update only package/release identity, make current release documentation describe the already-merged Evidence and source-pack capabilities, refresh frozen evaluation identities only when canonical validators prove a source-byte dependency, then generate final candidate evidence from one clean committed neutral worktree. Tagging and GitHub Release publication remain later, separately authorized stages.

**Tech Stack:** Python 3.12 and 3.13, Hatchling, uv, pytest, Ruff, Pyright, Markdown, Git.

## What Already Exists

- `main@16fae017ced5fe67da3fae4a01f26e9e9f1084aa` contains the reviewed Evidence provenance contract, source-pack consumer proof, owner lifecycle hardening, and candidate artifact receipt.
- `scripts/release_consumer_smoke.py` already proves a built wheel outside the source checkout and fails closed on installed identity drift.
- `scripts/release_presentation_audit.py` already validates version alignment, README boundaries, exact wheel commands, release-note links, comparison-only retrieval wording, and public-neutral output.
- `scripts/consumer_source_pack_proof.py` already supports one-wheel Python 3.12/3.13 validation and `--candidate-output` receipt creation.
- `src/mke/evaluation/artifact_refresh.py` already performs recoverable atomic E1 through E3-B identity refresh with semantic-preservation checks.
- Canonical E1 through E3-E validators already exist. This release may rebind their source/dependency identities; it may not change evaluation semantics.
- The public downstream proof is Night Voyager PR #21. It is evidence for the pre-release candidate built from `main@16fae017...`, not proof of the final tagged wheel or production adoption.

## Global Constraints

- Work only in the isolated release-closeout branch/worktree that contains the approved spec and this plan.
- Compare all implementation changes against `main@16fae017ced5fe67da3fae4a01f26e9e9f1084aa`.
- Execute tasks sequentially. Package version, release presentation, evaluation identities, and candidate receipt share one commit-sensitive dependency chain and must not be implemented in parallel.
- Do not modify MCP schemas, Search, Ask, Publication, Run, Evidence behavior, owner lifecycle behavior, database schemas, retrieval behavior, CI behavior, dependencies, or dependency versions.
- `src/mke/__init__.py` may change only the `__version__` literal.
- Do not touch OCR implementation/evaluation files, OCR worktrees, model caches, or retained OCR package/model evidence.
- Do not add OCR, tables, formulas, dense/RRF/reranker runtime promotion, HTTP/UI/service adapters, multi-tenancy, RBAC, hosted deployment, or PyPI publication.
- Do not rewrite historical `v0.1.0` or `v0.1.1` tag, commit, archive, publication, or verification facts. The only permitted historical edit is the approved future-version guidance in `docs/releases/v0.1.1.md`.
- Do not change generic `0.1.1` synthetic fixtures in `tests/scripts/test_consumer_source_pack_proof.py` merely because the repository version changes. Change only assertions that intentionally bind the current package/release identity.
- Do not enable network fallback, interpreter substitution, or dependency/model download to make an offline gate pass.
- Do not push, create a PR, merge, tag, create a GitHub Release, upload an asset, deploy, or publish to a package registry.
- A runtime, schema, dependency, fixture, qrel, query, observation, metric, threshold, gate, diagnostic, profile, candidate, status, or verdict change is an authority hard stop.

## Ordered Data Flow

```text
RED release contract tests
          |
          v
0.1.2 package/module/lock identity
          |
          v
release audit + current public docs
          |
          v
canonical validator failure inventory
          |
          v
identity-only E1 -> E2 -> E3-A -> E3-B -> E3-C -> E3-D -> E3-E closure
          |
          v
all repository writes committed; worktree clean
          |
          v
neutral detached-worktree full gate
          |
          v
one exact 0.1.2 wheel + source-pack candidate receipt
          |
          v
authoritative pre-PR review (no publication side effect)
```

## File And Responsibility Map

| File or set | Responsibility | Allowed change |
|---|---|---|
| `tests/test_version_identity.py` | Package and module version contract | Current expected version only |
| `tests/test_bootstrap.py` | Imported package version contract | Current expected version only |
| `pyproject.toml` | Distribution version | `0.1.1` to `0.1.2` only |
| `src/mke/__init__.py` | Module version | Version literal only |
| `uv.lock` | Root distribution identity | Mechanical root-package version only; no dependency delta |
| `scripts/release_consumer_smoke.py` and tests | Installed-wheel identity and release smoke | Current release version only |
| `scripts/release_presentation_audit.py` and tests | Current release presentation, exact commands, downstream boundary | Extend existing fail-closed rules without weakening historical checks |
| `README.md`, `README_CN.md`, `docs/README.md` | Current release entry points | Present shipped Evidence/source-pack capability and comparison-only boundary |
| `CHANGELOG.md`, `docs/releases/v0.1.2.md` | Current release record | Candidate facts only; no fabricated tag/Release metadata |
| `docs/releases/v0.1.1.md` | Historical release record | Future-version policy sentence only |
| `docs/how-to/verify-release.md` | Four-stage release procedure | Current candidate `0.1.2`; preserve completed prior records |
| `docs/how-to/run-consumer-source-pack-proof.md` and its test | Source-pack proof/release-gate boundary | Source-built proof is a release gate but is not the final tagged wheel |
| Current wheel-command docs/tests | Exact `0.1.2` wheel examples | Current command literals only |
| Canonical E1-E3-E artifacts/protocol locks/tests/docs | Frozen source/dependency identities | Conditional identity-only refresh after semantic equality proof |
| This plan, approved spec, implementation review | Durable status and evidence | Accurate status only; no premature completion claim |

## Task 1: Lock And Implement The `0.1.2` Package Identity

**Files:**

- Modify: `tests/test_version_identity.py`
- Modify: `tests/test_bootstrap.py`
- Modify: `tests/scripts/test_release_consumer_smoke.py`
- Modify: `pyproject.toml`
- Modify: `src/mke/__init__.py`
- Modify: `uv.lock`
- Modify: `scripts/release_consumer_smoke.py`

**Interfaces:**

- Consumes: current package metadata, imported `mke.__version__`, built-wheel metadata, installed module identity.
- Produces: one exact `0.1.2` identity across source, lock, build, and consumer smoke.
- Failure contract: any metadata disagreement is a stable smoke failure; dependency or runtime drift is a hard stop.

- [ ] **Step 1: Write the RED version assertions**

Change only current-release expectations in the three test files from `0.1.1` to `0.1.2`. Rename test functions that embed `v0_1_1`. Keep failure-path fixture versions unchanged when they are intentionally synthetic.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/test_version_identity.py \
  tests/test_bootstrap.py \
  tests/scripts/test_release_consumer_smoke.py
```

Expected RED: failures identify the still-current `0.1.1` source and smoke implementation. Any unrelated failure is investigated before implementation.

- [ ] **Step 2: Apply the minimal package identity change**

Set:

- `project.version = "0.1.2"` in `pyproject.toml`;
- `__version__ = "0.1.2"` in `src/mke/__init__.py`;
- `EXPECTED_VERSION = "0.1.2"` and the module description in `scripts/release_consumer_smoke.py`.

Refresh the lock offline:

```bash
uv lock --offline
```

Inspect `uv.lock` and require that the root `multimodal-knowledge-engine` package version is the only dependency-graph identity delta. If any dependency name, version, source, marker, extra, wheel, or checksum changes, restore nothing automatically: stop and report the lock drift.

- [ ] **Step 3: Run the identity tests GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/test_version_identity.py \
  tests/test_bootstrap.py \
  tests/scripts/test_release_consumer_smoke.py
uv run python - <<'PY'
import tomllib
from pathlib import Path
import mke

project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
assert project["project"]["version"] == "0.1.2"
assert mke.__version__ == "0.1.2"
print("version_identity=0.1.2")
PY
git diff --check
```

- [ ] **Step 4: Audit and commit the exact Task 1 files**

```bash
git diff -- pyproject.toml src/mke/__init__.py uv.lock \
  scripts/release_consumer_smoke.py tests/test_version_identity.py \
  tests/test_bootstrap.py tests/scripts/test_release_consumer_smoke.py
git add pyproject.toml src/mke/__init__.py uv.lock \
  scripts/release_consumer_smoke.py tests/test_version_identity.py \
  tests/test_bootstrap.py tests/scripts/test_release_consumer_smoke.py
git diff --cached --check
git commit -m "chore(release): set v0.1.2 identity"
```

## Task 2: Define The `v0.1.2` Presentation And Downstream Boundary

**Files:**

- Modify: `tests/scripts/test_release_presentation_audit.py`
- Modify: `scripts/release_presentation_audit.py`

**Interfaces:**

- Consumes: current package identity, release-facing files, public downstream PR URL and source commit.
- Produces: deterministic violations for stale release identity, wildcard wheel commands, missing Evidence/source-pack presentation, comparison-only drift, and overclaimed downstream evidence.
- Failure contract: a missing or overstated boundary is a release audit failure, never a warning.

- [ ] **Step 1: Add RED audit tests for current release identity**

Update the synthetic release tree and assertions to require:

- `EXPECTED_VERSION == "0.1.2"`;
- `docs/releases/v0.1.2.md` as the current release note;
- `docs/releases/v0.1.0.md` and `docs/releases/v0.1.1.md` excluded from current-release mutation rules;
- `## Verified in v0.1.2` and `## v0.1.2 已验证能力` current headings;
- exact wheel `dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl` in current release command surfaces;
- Evidence provenance, `mke.evidence_ref.v1`, external source-pack proof, same-wheel Python 3.12/3.13, and owner/runtime hardening terms;
- E3-C/E3-D/E3-E remain comparison-only and OCR remains excluded.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_release_presentation_audit.py
```

Expected RED: the audit implementation still targets `v0.1.1` and lacks the new current-release terms.

- [ ] **Step 2: Add RED downstream-boundary mutation tests**

Require the current release notes to contain:

- `https://github.com/iTao-AI/night-voyager/pull/21`;
- exact candidate source commit `16fae017ced5fe67da3fae4a01f26e9e9f1084aa`;
- explicit pre-release candidate, not-final-`v0.1.2`-wheel, independent-consumer, and CI-independent boundaries;
- synthetic fixture and strict receipt language.

Add mutations that must be rejected:

- replacing the source commit;
- deleting the PR link;
- claiming the final `v0.1.2` wheel was validated;
- claiming production adoption, hosted deployment, real-user outcomes, or MKE CI dependency;
- implying that the downstream lock must be updated for an identity-only release.

Run the focused new cases and confirm RED for the missing audit behavior.

- [ ] **Step 3: Implement the minimal audit update**

Update `scripts/release_presentation_audit.py` so the current file tuples, headings, terms, release-note checks, command checks, and parser description target `v0.1.2`. Keep historical release documents outside current-release mutation rules. Add one focused downstream boundary audit; do not embed private workflow or local paths.

- [ ] **Step 4: Run audit tests GREEN and commit**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_release_presentation_audit.py
uv run python scripts/release_presentation_audit.py --root . || true
git diff --check
git add scripts/release_presentation_audit.py \
  tests/scripts/test_release_presentation_audit.py
git diff --cached --check
git commit -m "test(release): define v0.1.2 presentation contract"
```

The direct audit may remain non-zero here because Task 3 has not yet updated the real documents. Its violations must be limited to expected missing/stale `v0.1.2` presentation; implementation or schema violations are a hard stop.

## Task 3: Update Current Release Documentation

**Files:**

- Modify: `CHANGELOG.md`
- Create: `docs/releases/v0.1.2.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/how-to/verify-release.md`
- Modify: `docs/how-to/run-consumer-source-pack-proof.md`
- Modify: `docs/releases/v0.1.1.md`, future-version guidance only
- Modify current wheel examples in:
  - `docs/reference/cli.md`
  - `docs/how-to/enable-cjk-retrieval.md`
  - `docs/how-to/evaluate-dense-retrieval.md`
  - `docs/how-to/prepare-local-embeddings.md`
  - `docs/how-to/evaluate-numeric-retrieval.md`
- Modify version-bound documentation tests:
  - `tests/evaluation/test_consumer_source_pack_documentation.py`
  - `tests/evaluation/test_dense_documentation.py`
  - `tests/scripts/test_transcription_deployment_proof.py`
- Modify other current documentation tests only when a focused RED proves they bind `0.1.1` as the current release.

**Interfaces:**

- Consumes: merged public capabilities and the Task 2 audit contract.
- Produces: public-neutral current release notes and reproducible commands without inventing tag, Release, archive, publication, or PyPI facts.
- Failure contract: stale current-release language, private material, wildcard wheel commands, or unsupported claims fail tests/audit.

- [ ] **Step 1: Write RED source-pack documentation assertions**

Change the source-pack documentation contract so it requires both truths:

1. the source-built proof command is a `v0.1.2` release-candidate verification gate;
2. its locally built wheel/candidate output is not the final tagged `v0.1.2` Release wheel, a PyPI artifact, a deployment, or production adoption proof.

Remove the old blanket rule that any “release gate” or `v0.1.1` mention is forbidden. Replace it with exact positive and negative boundaries. Preserve all existing closed-output, manifest, fingerprint, MCP SDK, fresh-environment, failure, cleanup, and candidate-receipt assertions.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_consumer_source_pack_documentation.py
```

Expected RED: the current how-to still says the proof is not a release gate and references the old tag.

- [ ] **Step 2: Add `CHANGELOG` and candidate release notes**

Add a `0.1.2` entry dated `2026-07-14` and create `docs/releases/v0.1.2.md`. Lead with:

- the additive Evidence provenance v1 tools and strict `mke.evidence_ref.v1`;
- the independent source-pack consumer proof using the official MCP SDK and same wheel on Python 3.12/3.13;
- bounded cleanup/failure behavior and owner lifecycle/runtime hardening;
- exact local candidate artifact receipt;
- the downstream candidate boundary from Task 2.

Include exact verification commands and links. State comparison-only retrieval and OCR exclusion. Omit tag object SHA, Release URL, publication timestamp, archive filename/SHA, and post-release archive smoke until those facts exist. Do not use incomplete markers or fake placeholders inside the current release note.

- [ ] **Step 3: Update bilingual entry points and docs navigation**

Update `README.md`, `README_CN.md`, and `docs/README.md` to make `v0.1.2` current. Preserve the existing architecture diagram and runtime default. Expand the verified-capability table and engineering-depth section with the Evidence/source-pack capabilities while keeping dense, RRF, and reranker comparison-only and OCR out of the release.

- [ ] **Step 4: Update release verification and exact wheel commands**

In `docs/how-to/verify-release.md`:

- preserve completed `v0.1.0` and `v0.1.1` records byte-for-byte except navigation context;
- make Stage 1/2 candidate commands target `0.1.2`;
- make Stage 3 explicitly rerun the full gate on final merged `main`;
- keep Stage 4 tag/Release/archive steps as future authorized instructions, not completed facts.

Replace current exact wheel examples with `dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl` in the listed current docs/tests. Do not change historical release commands and do not mass-replace synthetic `0.1.1` fixture values.

- [ ] **Step 5: Apply the approved flexible version policy**

In `docs/releases/v0.1.1.md`, change only the future guidance that rigidly assigns contract expansion to `0.2.0`. State that backward-compatible fixes, proofs, operational hardening, and bounded capability additions may remain `0.1.x`; reserve `0.2.0` for materially larger product or contract evolution; do not preassign a future feature version.

- [ ] **Step 6: Run focused documentation gates GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  tests/evaluation/test_dense_documentation.py \
  tests/scripts/test_transcription_deployment_proof.py \
  tests/evaluation/test_evidence_provenance_documentation.py
uv run python scripts/release_presentation_audit.py --root .
```

Expected: tests pass; audit emits `{"status":"ok","violations":[]}`.

- [ ] **Step 7: Run link, stale-wording, and public-boundary checks**

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_*documentation.py
rg -n 'dist/\*\.whl|multimodal_knowledge_engine-0\.1\.1-py3-none-any\.whl' \
  README.md README_CN.md docs/README.md docs/how-to docs/reference docs/releases/v0.1.2.md
rg -n 'T[B]D|T[O]DO|PLACEH[O]LDER|implementation has not start[e]d|targeted .* pendi[n]g' \
  README.md README_CN.md CHANGELOG.md docs/releases/v0.1.2.md \
  docs/how-to/verify-release.md docs/how-to/run-consumer-source-pack-proof.md
rg -n '/U[s]ers/|\.gsta[c]k|tok[e]n=|api[_-]?k[e]y|Tracebac[k] \(most recent call last\)' \
  README.md README_CN.md CHANGELOG.md docs/releases/v0.1.2.md docs/how-to docs/reference
git diff --check
```

Expected: no current wildcard/old-wheel, incomplete marker, private path/workflow, credential, or traceback hit. Review any broad-scan hit in unchanged historical or fail-closed test text; do not weaken tests to silence an intentional sentinel.

- [ ] **Step 8: Commit the documentation slice**

Stage only the documented Task 3 paths after reviewing the exact diff.

```bash
git diff --name-only
git diff --check
git add CHANGELOG.md README.md README_CN.md \
  docs/README.md docs/releases/v0.1.1.md docs/releases/v0.1.2.md \
  docs/how-to/verify-release.md docs/how-to/run-consumer-source-pack-proof.md \
  docs/reference/cli.md docs/how-to/enable-cjk-retrieval.md \
  docs/how-to/evaluate-dense-retrieval.md \
  docs/how-to/prepare-local-embeddings.md \
  docs/how-to/evaluate-numeric-retrieval.md \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  tests/evaluation/test_dense_documentation.py \
  tests/scripts/test_transcription_deployment_proof.py
git diff --cached --check
git commit -m "docs(release): prepare v0.1.2 candidate"
```

## Task 4: Close The Conditional E1 Through E3-E Identity Chain

**Files:**

- Modify only when a canonical validator proves the dependency invalid:
  - `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
  - `tests/fixtures/retrieval-numeric-v1/protocol-lock.json`
  - `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
  - `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
  - `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`
  - `tests/fixtures/retrieval-dense-v1/protocol-lock.json`
  - `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-development-freeze.json`
  - `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-holdout-receipt.json`
  - `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`
  - `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json`
  - `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json`
  - `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json`
  - `tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json`
  - `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json`
  - `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json`
  - `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json`
  - identity-reference docs/tests proven stale by the same chain.

The maximum expected conditional changed set is the 21-file identity chain previously used by the repository. A smaller validator-proven subset is preferred. Any different or larger set is an authority hard stop.

**Interfaces:**

- Consumes: clean committed release identity and fresh E1/E2/E3-A/E3-B observations.
- Produces: validator-accepted provenance identities with normalized semantics unchanged.
- Failure contract: semantic drift stops the release task; it is not repaired here.

- [ ] **Step 1: Capture pre-refresh semantic reference and fresh observations**

Before writing any artifact, freeze the exact pre-refresh commit and run fresh observations into a call-owned temporary directory. Later semantic comparison must read pre-refresh artifacts with `git show "${task4_start}:<path>"`; it must not compare against a mutable worktree copy.

```bash
evidence_dir="$(mktemp -d)"
task4_start="$(git rev-parse HEAD)"
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > "${evidence_dir}/e1.json"
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > "${evidence_dir}/e2.json"
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > "${evidence_dir}/e3a.json"
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > "${evidence_dir}/e3b.json"
```

Expected: all four commands exit `0`. Preserve the temporary observations until Task 4 completes.

- [ ] **Step 2: Run all seven canonical validators before writing**

```bash
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository .
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed "${evidence_dir}/e2.json" \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed "${evidence_dir}/e3a.json" \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed "${evidence_dir}/e3b.json" \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.dense_artifact validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.hybrid_rrf_artifact validate \
  --artifact benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --repository .
uv run python -m mke.evaluation.relevance_gate_artifact validate \
  --artifact benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --repository .
```

Record the exact pass/fail chain. If all pass, skip directly to Step 6 with no artifact write. Continue only when failures are exclusively source/scope/dependency identity mismatches caused by the version-byte change.

- [ ] **Step 3: Perform the supported atomic E1 through E3-B refresh**

Use the repository helper; do not hand-edit its five targets:

```bash
uv run python -m mke.evaluation.artifact_refresh \
  --repository . \
  --e1-observed "${evidence_dir}/e1.json" \
  --e2-observed "${evidence_dir}/e2.json" \
  --e3-observed "${evidence_dir}/e3a.json" \
  --e3b-observed "${evidence_dir}/e3b.json"
```

If the helper fails, run only its supported recovery command:

```bash
uv run python -m mke.evaluation.artifact_refresh recover --repository .
```

Then stop and inspect. Do not continue after an incomplete transaction or manually copy staged files.

- [ ] **Step 4: Rebind downstream E3-C, E3-D, and E3-E identities in dependency order**

Use existing deterministic artifact builders/validators and the prior repository identity-closure pattern. Rebind only hashes, byte sizes, source inventories, dependency identities, and exact identity-reference literals. Do not rerun model scoring, retune a threshold, reopen a holdout, or rewrite semantic observations.

After each layer:

1. compare normalized semantic payload with the pre-change artifact;
2. require metrics, gates, selected profile/candidate, status, verdict, and diagnostics to be equal;
3. run that layer's model-free validator before proceeding.

If a deterministic existing builder cannot express an identity-only update, stop. Do not add release-specific artifact mutation code.

- [ ] **Step 5: Enforce the exact changed-file and semantic allowlists**

Compare the changed set against the conditional list above and against the previous repository identity chain. Require all corpus PDFs/text, manifests, qrels, query definitions, and evaluation implementation files to remain byte-identical to the Task 4 starting commit.

The following must remain equal for every layer: observations, ordered results after approved volatile-field normalization, metrics, thresholds, gates, diagnostics, selected profile/candidate, holdout status, release/promotion status, and verdict.

- [ ] **Step 6: Run artifact regression suites and all validators GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_artifact_refresh.py \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py \
  tests/evaluation/test_relevance_gate_protocol.py \
  tests/evaluation/test_relevance_gate_workflow.py
```

Then rerun all seven commands from Step 2. Every validator must pass. Optional cache-ready dense replay is not required and must not trigger a model download.

- [ ] **Step 7: Commit only if validator-proven files changed**

```bash
git diff --check
git diff --name-only -- benchmarks/retrieval tests/fixtures tests/evaluation docs/how-to
```

If no identity file changed, record `identity_refresh=not_required` and do not create an empty commit. Otherwise stage only the exact validator-proven allowlist, then commit:

```bash
git add -- <space-separated exact validator-proven paths>
git diff --cached --check
git commit -m "test(eval): refresh v0.1.2 release identities"
```

## Task 5: Finalize Durable Status Before Candidate Evidence

**Files:**

- Modify: `docs/superpowers/specs/2026-07-14-v0-1-2-release-closeout-design.md`
- Modify: `docs/superpowers/plans/2026-07-14-v0-1-2-release-closeout-implementation.md`
- Create: `docs/superpowers/reviews/2026-07-14-v0-1-2-release-implementation-review.md`

**Interfaces:**

- Consumes: completed Tasks 1-4 and their exact commits/results.
- Produces: accurate repository-visible implementation status before the commit-bound candidate proof.
- Failure contract: no claim of review acceptance, PR, merge, tag, Release, or publication before it occurs.

- [ ] **Step 1: Add the implementation review skeleton**

Record:

- scope and non-scope;
- release implementation commits;
- package/release/doc identity result;
- whether identity refresh was required and the exact changed set;
- semantic equality and seven-validator evidence;
- verification matrix still to run in Task 6;
- status `implementation complete; final clean-candidate verification and authoritative review pending`.

- [ ] **Step 2: Update plan checkboxes and spec status accurately**

Mark Tasks 1-4 complete only when their commands passed. Leave Task 6 unchecked. Set the spec to implemented locally but pending final candidate verification and authoritative pre-PR review. Do not use ambiguous `complete` wording.

- [ ] **Step 3: Run docs/status checks and commit all remaining repository writes**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_*documentation.py
uv run python scripts/release_presentation_audit.py --root .
rg -n 'T[B]D|T[O]DO|PLACEH[O]LDER|implementation has not start[e]d|CLEARED FOR IMPLEMENTATI[O]N' \
  docs/superpowers/specs/2026-07-14-v0-1-2-release-closeout-design.md \
  docs/superpowers/plans/2026-07-14-v0-1-2-release-closeout-implementation.md \
  docs/superpowers/reviews/2026-07-14-v0-1-2-release-implementation-review.md
git diff --check
git add docs/superpowers/specs/2026-07-14-v0-1-2-release-closeout-design.md \
  docs/superpowers/plans/2026-07-14-v0-1-2-release-closeout-implementation.md \
  docs/superpowers/reviews/2026-07-14-v0-1-2-release-implementation-review.md
git diff --cached --check
git commit -m "docs(release): record v0.1.2 candidate evidence"
```

After this commit, make no repository write before the Task 6 candidate receipt. A later review fix invalidates Task 6 evidence and requires a complete rerun on the new reviewed commit.

## Task 6: Verify One Clean Committed Candidate And Stop For Review

**Files:**

- Do not modify tracked repository files.
- Create only call-owned temporary worktrees, build outputs, venvs, and candidate-output directories.

**Interfaces:**

- Consumes: exact clean Task 5 commit.
- Produces: full repository gate, one exact `0.1.2` wheel, installed-wheel evidence, same-wheel dual-interpreter source-pack proof, strict candidate receipt, and review handoff.
- Failure contract: any failure leaves Task 6 incomplete; there is no residual waiver.

- [ ] **Step 1: Freeze the candidate commit and create a neutral detached worktree**

```bash
git status --short
candidate_commit="$(git rev-parse HEAD)"
neutral_parent="$(mktemp -d)"
neutral_worktree="${neutral_parent}/mke-release-candidate"
git worktree add --detach "${neutral_worktree}" "${candidate_commit}"
```

Require the source worktree clean before creation. The temporary worktree name must not contain `proof`, `demo`, `release_consumer_smoke`, or other test command markers that can affect path-sensitive synthetic tests.

- [ ] **Step 2: Run static, full-suite, build, and core proof gates in the neutral worktree**

From `neutral_worktree`:

```bash
UV_OFFLINE=1 uv run pytest -q
UV_OFFLINE=1 uv run ruff check .
UV_OFFLINE=1 uv run pyright
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
```

Require full pytest green with no residual waiver. Existing warnings may be reported but not reclassified as failures or silently hidden.

- [ ] **Step 3: Verify the exact built wheel outside the source checkout**

```bash
wheel="dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl"
test -f "${wheel}"
UV_OFFLINE=1 uv run python scripts/release_consumer_smoke.py \
  --wheel "${wheel}" --json
```

Require `status=passed`, installed package/module metadata `0.1.2`, external working directory, and all proof/demo/CLI/MCP substeps passed.

- [ ] **Step 4: Run release presentation, documentation, and seven-validator gates**

```bash
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_*documentation.py \
  tests/scripts/test_release_presentation_audit.py
```

Generate fresh E1/E2/E3-A/E3-B observations in a call-owned temporary directory and run all seven canonical validator commands from Task 4 Step 2. Require every validator green.

- [ ] **Step 5: Run the same-wheel Python 3.12/3.13 source-pack gate**

First verify the exact interpreters without substituting another version:

```bash
python312="$(command -v python3.12)"
python313="$(command -v python3.13)"
"${python312}" --version
"${python313}" --version
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "${python312}" \
  --python "${python313}" \
  --json
```

Require both interpreter cells to install and prove the same input wheel digest. Missing interpreters or offline packages are environment blockers; do not enable network access.

- [ ] **Step 6: Generate the strict local candidate output last**

The maintained candidate path builds from clean `HEAD`, so run it only after every tracked write is committed and the neutral gate is green:

```bash
candidate_parent="$(mktemp -d)"
candidate_output="${candidate_parent}/mke-v0.1.2-candidate"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "${python312}" \
  --python "${python313}" \
  --candidate-output "${candidate_output}" \
  --json
```

Verify:

- exactly one `multimodal_knowledge_engine-0.1.2-py3-none-any.whl` and one receipt;
- receipt schema `mke.candidate_artifact_receipt.v1`;
- `source_commit == candidate_commit`;
- package version `0.1.2`;
- wheel filename, bytes, SHA-256, proof input SHA-256, dual-interpreter result, and canonical receipt SHA agree;
- candidate path is outside the repository and no candidate file is tracked.

- [ ] **Step 7: Run final diff, scope, marker, and public-neutral audits**

```bash
git -C "${neutral_worktree}" diff --check \
  16fae017ced5fe67da3fae4a01f26e9e9f1084aa.."${candidate_commit}"
git -C "${neutral_worktree}" status --short
git diff --name-status \
  16fae017ced5fe67da3fae4a01f26e9e9f1084aa.."${candidate_commit}"
```

Require:

- no runtime/schema/dependency/OCR/CI workflow file outside the approved surface;
- `src/mke/__init__.py` version literal as the only `src/mke` diff;
- clean neutral worktree;
- no private paths, credentials, raw tracebacks, private workflow, unsupported production claims, stale `0.1.1` current commands, or incomplete markers in changed public text;
- historical release identities preserved.

- [ ] **Step 8: Remove only call-owned temporary resources and report**

Remove only the neutral worktree and temporary directories created by this task after preserving the exact command results, commit SHA, wheel SHA-256, receipt SHA-256, and candidate path needed for review. Do not remove or modify any pre-existing branch/worktree or OCR evidence.

Report:

- branch and exact candidate commit;
- commit series;
- exact changed-file set and diff stat;
- RED/GREEN evidence;
- full test/lint/type/build/proof/audit/validator results;
- Python 3.12/3.13 versions;
- wheel filename/bytes/SHA-256;
- receipt SHA-256 and `source_commit`;
- identity refresh result and semantic-equality evidence;
- remaining risks;
- clean worktree status.

Stop for authoritative pre-PR review. Do not push, create a PR, merge, tag, create a GitHub Release, or mark publication complete.

## Failure Modes And Required Response

| Failure | Required response |
|---|---|
| `uv lock --offline` changes dependencies | Stop; report exact lock drift. Do not accept it as release work. |
| Runtime, schema, CLI/MCP behavior, or dependency test fails | Stop; do not repair outside this release scope. |
| Source-pack docs cannot express both release-gate and non-final-wheel boundaries | Fix the audit/test contract before prose; do not weaken either boundary. |
| Downstream prose implies final-wheel validation or production adoption | Fail presentation audit and correct the claim. |
| Evaluation validator fails on semantics rather than identity | Stop before artifact writes and return to authority review. |
| Atomic artifact refresh is interrupted | Run supported recovery, inspect, and stop; do not hand-copy transaction files. |
| E3-C/D/E identity cannot be rebuilt with existing deterministic tooling | Stop; do not add a release-specific mutator. |
| Conditional artifact changed set exceeds the expected chain | Stop and report the exact extra paths. |
| Python 3.12/3.13 or offline dependencies are unavailable | Report environment blocker; do not substitute, download, or use the network. |
| Full pytest has any failure in the neutral worktree | Task 6 remains incomplete; no residual waiver. |
| Candidate receipt commit/wheel identity differs | Delete only call-owned invalid output, fix the cause, recommit if needed, and rerun the complete final gate. |
| Authoritative review changes the candidate commit | Invalidate prior Task 6 evidence and rerun it in full on the reviewed commit. |
| Tag/Release action is requested during implementation | Stop; publication requires a separate explicit authorization after merge and final-main verification. |

## Completion Boundary

This plan completes only the locally verified release candidate and authoritative pre-PR handoff. It does not complete the release publication.

Later stages remain separately authorized:

1. push and create the release PR;
2. merge after hosted checks pass;
3. rerun the entire final gate on the exact resulting `main` commit;
4. create annotated tag `v0.1.2` and GitHub Release only after explicit publication authorization;
5. run downloaded public-archive smoke and land a separate durable post-release closeout if needed.

The OCR branch remains independent throughout.
