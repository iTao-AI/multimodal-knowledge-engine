# v0.1.2 Release Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before claiming a gate passed. Steps use checkbox (`- [ ]`) syntax for tracking.

Status: implementation accepted by authoritative review; final reviewed local-candidate verification pending. Publication remains unauthorized.

Planning base: `main@16fae017ced5fe67da3fae4a01f26e9e9f1084aa`.

Approved design: [v0.1.2 Release Closeout Design](../specs/2026-07-14-v0-1-2-release-closeout-design.md).

**Goal:** Prepare a locally verified `v0.1.2` release candidate whose package identity, Evidence-provenance presentation, external-consumer proof, downstream candidate boundary, evaluation identities, and installed-wheel evidence agree without publishing it.

**Architecture:** Keep runtime and public contracts unchanged. Treat the release as an ordered identity-and-evidence closure: define the `0.1.2` contract in tests, update only package/release identity, make current release documentation describe the already-merged Evidence and source-pack capabilities, refresh frozen evaluation identities only when canonical validators prove a source-byte dependency, generate pre-review candidate evidence from one clean committed neutral worktree, stop for authoritative review, commit the accepted review closure, then re-prove the exact new commit from scratch. `UV_OFFLINE=1 uv build` remains a packaging gate, but only the exact candidate-output wheel bound by its receipt SHA-256 is final artifact authority. Tagging and GitHub Release publication remain later, separately authorized stages.

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
neutral detached-worktree pre-review full gate
          |
          v
once-only candidate-output same-wheel proof
          |
          v
candidate-output wheel installed smoke + receipt coherence
          |
          v
authoritative review checkpoint (stop)
          |
          v
accepted review-closure commit invalidates prior evidence
          |
          v
fresh neutral worktree + complete gate rerun
          |
          v
final reviewed candidate-output wheel + receipt
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

- [x] **Step 1: Write the RED version assertions**

Change only current-release expectations in the three test files from `0.1.1` to `0.1.2`. Rename test functions that embed `v0_1_1`. Keep failure-path fixture versions unchanged when they are intentionally synthetic.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/test_version_identity.py \
  tests/test_bootstrap.py \
  tests/scripts/test_release_consumer_smoke.py
```

Expected RED: failures identify the still-current `0.1.1` source and smoke implementation. Any unrelated failure is investigated before implementation.

- [x] **Step 2: Apply the minimal package identity change**

Set:

- `project.version = "0.1.2"` in `pyproject.toml`;
- `__version__ = "0.1.2"` in `src/mke/__init__.py`;
- `EXPECTED_VERSION = "0.1.2"` and the module description in `scripts/release_consumer_smoke.py`.

Refresh the lock offline:

```bash
uv lock --offline
```

Inspect `uv.lock` and require that the root `multimodal-knowledge-engine` package version is the only dependency-graph identity delta. If any dependency name, version, source, marker, extra, wheel, or checksum changes, restore nothing automatically: stop and report the lock drift.

- [x] **Step 3: Run the identity tests GREEN**

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

- [x] **Step 4: Audit and commit the exact Task 1 files**

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

- [x] **Step 1: Add RED audit tests for current release identity**

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

- [x] **Step 2: Add RED downstream-boundary mutation tests**

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

- [x] **Step 3: Implement the minimal audit update**

Update `scripts/release_presentation_audit.py` so the current file tuples, headings, terms, release-note checks, command checks, and parser description target `v0.1.2`. Keep historical release documents outside current-release mutation rules. Add one focused downstream boundary audit; do not embed private workflow or local paths.

- [x] **Step 4: Run audit tests GREEN and commit**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_release_presentation_audit.py
set +e
audit_stderr="$(mktemp)"
audit_json="$(uv run python scripts/release_presentation_audit.py --root . 2>"${audit_stderr}")"
audit_exit=$?
set -e
test "${audit_exit}" -eq 1
test ! -s "${audit_stderr}"
AUDIT_JSON="${audit_json}" uv run python - <<'PY'
import json
import os

payload = json.loads(os.environ["AUDIT_JSON"])
assert payload["status"] == "failed"
assert payload["violations"]
print(json.dumps(payload, sort_keys=True))
PY
git diff --check
git add scripts/release_presentation_audit.py \
  tests/scripts/test_release_presentation_audit.py
git diff --cached --check
git commit -m "test(release): define v0.1.2 presentation contract"
```

The expected-negative probe must exit `1` with valid JSON, `status == "failed"`, and non-empty `violations`. Review every violation and require it to come only from Task 3's not-yet-updated current `v0.1.2` documentation or presentation. Exit `0`, non-JSON output, raw traceback, an unknown rule, or any non-documentation/presentation violation is a hard stop. Remove the call-owned stderr file after inspection; never use blanket failure suppression.

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

- [x] **Step 1: Write RED source-pack documentation assertions**

Change the source-pack documentation contract so it requires both truths:

1. the source-built proof command is a `v0.1.2` release-candidate verification gate;
2. its locally built wheel/candidate output is not the final tagged `v0.1.2` Release wheel, a PyPI artifact, a deployment, or production adoption proof.

Remove the old blanket rule that any “release gate” or `v0.1.1` mention is forbidden. Replace it with exact positive and negative boundaries. Preserve all existing closed-output, manifest, fingerprint, MCP SDK, fresh-environment, failure, cleanup, and candidate-receipt assertions.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_consumer_source_pack_documentation.py
```

Expected RED: the current how-to still says the proof is not a release gate and references the old tag.

- [x] **Step 2: Add `CHANGELOG` and candidate release notes**

Add a `0.1.2` entry dated `2026-07-14` and create `docs/releases/v0.1.2.md`. Lead with:

- the additive Evidence provenance v1 tools and strict `mke.evidence_ref.v1`;
- the independent source-pack consumer proof using the official MCP SDK and same wheel on Python 3.12/3.13;
- bounded cleanup/failure behavior and owner lifecycle/runtime hardening;
- exact local candidate artifact receipt;
- the downstream candidate boundary from Task 2.

Include exact verification commands and links. State comparison-only retrieval and OCR exclusion. Omit tag object SHA, Release URL, publication timestamp, archive filename/SHA, and post-release archive smoke until those facts exist. Do not use incomplete markers or fake placeholders inside the current release note.

- [x] **Step 3: Update bilingual entry points and docs navigation**

Update `README.md`, `README_CN.md`, and `docs/README.md` to make `v0.1.2` current. Preserve the existing architecture diagram and runtime default. Expand the verified-capability table and engineering-depth section with the Evidence/source-pack capabilities while keeping dense, RRF, and reranker comparison-only and OCR out of the release.

- [x] **Step 4: Update release verification and exact wheel commands**

In `docs/how-to/verify-release.md`:

- preserve completed `v0.1.0` and `v0.1.1` records byte-for-byte except navigation context;
- make Stage 1/2 candidate commands target `0.1.2`;
- make Stage 3 explicitly rerun the full gate on final merged `main`;
- keep Stage 4 tag/Release/archive steps as future authorized instructions, not completed facts.

Replace current exact wheel examples with `dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl` in the listed current docs/tests. Do not change historical release commands and do not mass-replace synthetic `0.1.1` fixture values.

- [x] **Step 5: Apply the approved flexible version policy**

In `docs/releases/v0.1.1.md`, change only the future guidance that rigidly assigns contract expansion to `0.2.0`. State that backward-compatible fixes, proofs, operational hardening, and bounded capability additions may remain `0.1.x`; reserve `0.2.0` for materially larger product or contract evolution; do not preassign a future feature version.

- [x] **Step 6: Run focused documentation gates GREEN**

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

- [x] **Step 7: Run link, stale-wording, and public-boundary checks**

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

- [x] **Step 8: Commit the documentation slice**

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
  - `docs/how-to/evaluate-dense-retrieval.md`
  - `docs/how-to/evaluate-hybrid-rrf-retrieval.md`
  - `docs/how-to/evaluate-relevance-gate-reranker.md`
  - `tests/evaluation/test_relevance_gate_protocol.py`
  - `tests/evaluation/test_relevance_gate_workflow.py`

The maximum expected conditional changed set is the 21-file identity chain previously used by the repository. A smaller validator-proven subset is preferred. Any different or larger set is an authority hard stop.

**Interfaces:**

- Consumes: clean committed release identity and fresh E1/E2/E3-A/E3-B observations.
- Produces: validator-accepted provenance identities with normalized semantics unchanged.
- Failure contract: semantic drift stops the release task; it is not repaired here.

- [x] **Step 1: Capture pre-refresh semantic reference and fresh observations**

Before writing any artifact, freeze the exact pre-refresh commit and run fresh observations into a call-owned temporary directory. Later semantic comparison must read pre-refresh artifacts with `git show "${task4_start}:<path>"`; it must not compare against a mutable worktree copy.

The E2 observation must bind the refreshed scope identity before the comparison runs. The call-owned hidden protocol must remain in the canonical numeric fixture directory because `load_numeric_protocol` derives `protocol_root` from the protocol path. Never overwrite a pre-existing hidden protocol.

```bash
evidence_dir="$(mktemp -d)"
task4_start="$(git rev-parse HEAD)"
e2_protocol="tests/fixtures/retrieval-numeric-v1/.protocol-lock.v0.1.2-observation.json"
test ! -e "${e2_protocol}"
cleanup_e2_protocol() {
  rm -f -- "${e2_protocol}"
}
trap cleanup_e2_protocol EXIT INT TERM

cp tests/fixtures/retrieval-numeric-v1/protocol-lock.json "${e2_protocol}"
uv run python -m mke.evaluation.numeric_comparison refresh-scope \
  --protocol "${e2_protocol}" \
  --repository .
uv run mke eval retrieval-numeric \
  --protocol "${e2_protocol}" \
  --json > "${evidence_dir}/e2.json"
jq -e '
  .schema_version == "mke.retrieval_numeric_comparison.v1" and
  .protocol_id == "retrieval-numeric-v1" and
  .integrity_status == "passed" and
  .candidate_status == "passed" and
  .integrity_failures == []
' "${evidence_dir}/e2.json"

rm -f -- "${e2_protocol}"
trap - EXIT INT TERM
test ! -e "${e2_protocol}"

uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > "${evidence_dir}/e1.json"
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > "${evidence_dir}/e3a.json"
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > "${evidence_dir}/e3b.json"
```

Expected: all four observation commands exit `0`, and the exact E2 integrity assertion passes. Preserve the temporary observations until Task 4 completes. An E2 observation generated from the pre-refresh checked-in protocol is diagnostic only; it must never be passed to `artifact_refresh`.

Before any artifact write, run only the helper regression that proves its internal refreshed-protocol observation order without requiring the still-stale checked-in canonical protocol to pass:

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_artifact_refresh.py
```

- [x] **Step 2: Run all seven canonical validators before writing**

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

This is a diagnostic against the checked-in canonical graph before any write. Record the exact pass/fail chain. If all pass, skip directly to Step 6 with no artifact write. Continue only when failures are exclusively source/scope/dependency identity mismatches caused by the version-byte change. Step 3 consumes the corrected, refreshed-scope `${evidence_dir}/e2.json`; it does not change helper semantics.

- [x] **Step 3: Perform the supported atomic E1 through E3-B refresh**

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

- [x] **Step 4: Rebind downstream E3-C, E3-D, and E3-E identities in dependency order**

Freeze `task4_start` before any write. Read every before byte with `git show "${task4_start}:<path>"`; never compare against a mutable worktree copy. Enter this step only after all seven validators have proven that every failure is identity-only.

Create a call-owned, untracked Python rebinder under `${evidence_dir}`. Do not add the rebinder or another mutator to the repository. The rebinder may call or mirror only these existing deterministic builder/renderer contracts:

- `build_dense_protocol_lock` / `render_dense_protocol_lock_json`;
- `build_dense_comparison_artifact` / `render_dense_comparison_artifact_json`;
- `build_hybrid_rrf_protocol_lock` / `render_hybrid_rrf_protocol_lock_json`;
- `build_hybrid_rrf_development_freeze`;
- `build_hybrid_rrf_comparison_artifact` / `render_hybrid_rrf_artifact_json`;
- `build_relevance_gate_protocol_lock` / `render_relevance_gate_protocol_lock_json`;
- `build_relevance_gate_development_freeze`;
- `build_relevance_gate_holdout_report`;
- `build_relevance_gate_comparison_artifact`.

Dense development-freeze and holdout-receipt have no public identity-only builder. Do not rerun a model or re-observe the holdout. Rebind only their protocol, dependency, source, and state-receipt identity fields using the changed-field pattern verified by commit `6c2559b3fec80b3b98608214594f9069e4b5fd2e`; this commit is a changed-field reference, never a source for copied digests. Require the dense comparison builder, dense validator, and normalized semantic projection equality to prove the result.

Generate all E3-C/D/E candidate bytes first under `${evidence_dir}/staged`. After the E1-E3-B helper succeeds, create a call-owned detached validation mirror rooted at `task4_start`. Overlay into canonical repository-relative paths in that mirror both:

```bash
validation_parent="$(mktemp -d)"
validation_mirror="${validation_parent}/mke-identity-validation"
git worktree add --detach "${validation_mirror}" "${task4_start}"
```

1. the exact successful E1-E3-B refreshed candidate bytes read from the feature worktree; and
2. every staged E3-C/D/E candidate byte.

The validation mirror must contain the complete proposed dependency graph. Passing only staged top-level `--artifact` or `--protocol` paths while leaving `--repository .` is prohibited because builders and validators resolve repository-relative sources, development freezes, holdout receipts, and dependency identities through `repository_root`.

Before feature-worktree publication, the rebinder and validation mirror must:

1. enforce the exact 21-path maximum allowlist;
2. require the mirror changed set relative to `task4_start` to equal the complete candidate changed set and remain within that allowlist;
3. require every changed mirror byte to equal its corresponding refreshed/staged candidate byte;
4. compare before/mirror normalized semantic projections for every E1 through E3-E layer;
5. permit changes only to path, bytes, SHA-256, source inventory, dependency identity, state-receipt digest, and equivalent identity metadata;
6. reject changes to observations, results, metrics, thresholds, gates, diagnostics, selected profile/candidate, status, verdict, corpus, queries, qrels, or fixtures;
7. run applicable builders and layer validators using paths inside the mirror and `repository_root`/`--repository "${validation_mirror}"`;
8. run all seven canonical validators against the mirror, with every artifact, protocol, and dense-artifact path resolved inside the mirror;
9. preserve the exact validated downstream bytes for feature-worktree application only after the complete mirror is green.

Any failure before feature-worktree application discards only the call-owned E3-C/D/E staging and validation mirror. If E1-E3-B atomic refresh requires recovery, use only the existing `artifact_refresh recover` command. Never partially publish staged downstream files, hand-edit a validator, or weaken validation because a builder cannot express the identity-only change. Inability to express the change is an authority hard stop.

- [x] **Step 5: Enforce the exact changed-file and semantic allowlists**

Compare the staged set, validation-mirror changed set, and proposed feature-worktree changed set against the conditional list above and the previous repository identity chain. Require all corpus PDFs/text, manifests, qrels, query definitions, and evaluation implementation files to remain byte-identical to the Task 4 starting commit.

The following must remain equal for every layer: observations, ordered results after approved volatile-field normalization, metrics, thresholds, gates, diagnostics, selected profile/candidate, holdout status, release/promotion status, and verdict.

Before applying downstream bytes, capture path descriptors and exact bytes/digests for every pre-apply conditional downstream path in a call-owned backup. Apply only the exact mirror-validated E3-C/D/E bytes to the feature worktree, using per-file atomic replacement in dependency order. This is a recoverable ordered multi-file operation, not filesystem-wide multi-file atomicity.

If any apply step or post-apply validator fails, restore every touched downstream path from the call-owned backup and verify exact descriptor/byte restoration. If restoration is not exact, hard stop and report the precise dirty paths. Never stage or commit a partial downstream set.

- [x] **Step 6: Run artifact regression suites and all validators GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_artifact_refresh.py \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_numeric_comparison.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_protocol.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_protocol.py \
  tests/evaluation/test_hybrid_rrf_workflow.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py \
  tests/evaluation/test_relevance_gate_protocol.py \
  tests/evaluation/test_relevance_gate_workflow.py
```

After the exact validated downstream bytes are applied to the feature worktree, rerun all seven commands from Step 2 with `--repository .` before any staging or commit. Every validator must pass against the real worktree. A post-apply validator failure triggers the Step 5 restoration contract. Optional cache-ready dense replay is not required and must not trigger a model download.

- [x] **Step 7: Commit only if validator-proven files changed**

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

The Task 4 handoff must report the call-owned rebinder SHA-256, exact changed paths, and before/after semantic projection equality for each E1 through E3-E layer. Do not commit the rebinder.

## Task 5: Finalize Durable Status Before Candidate Evidence

**Files:**

- Modify: `docs/superpowers/specs/2026-07-14-v0-1-2-release-closeout-design.md`
- Modify: `docs/superpowers/plans/2026-07-14-v0-1-2-release-closeout-implementation.md`
- Create: `docs/superpowers/reviews/2026-07-14-v0-1-2-release-implementation-review.md`

**Interfaces:**

- Consumes: completed Tasks 1-4 and their exact commits/results.
- Produces: accurate repository-visible implementation status before the commit-bound candidate proof.
- Failure contract: no claim of review acceptance, PR, merge, tag, Release, or publication before it occurs.

- [x] **Step 1: Add the implementation review skeleton**

Record:

- scope and non-scope;
- release implementation commits;
- package/release/doc identity result;
- whether identity refresh was required and the exact changed set;
- semantic equality and seven-validator evidence;
- verification matrix still to run in Task 6;
- status `release changes complete; clean-candidate verification and authoritative review pending`.

- [x] **Step 2: Update plan checkboxes and spec status accurately**

Mark Tasks 1-4 complete only when their commands passed. Leave Tasks 6 and 7 unchecked. Set the spec to release changes complete but pending pre-review candidate verification and authoritative review. Do not use ambiguous `complete` wording.

- [x] **Step 3: Run docs/status checks and commit all remaining repository writes**

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
git commit -m "docs(release): prepare v0.1.2 candidate review"
```

After this commit, make no repository write before the Task 6 pre-review candidate receipt. Any later review finding or review-closure commit invalidates Task 6 evidence and requires the complete Task 7 rerun on the new reviewed commit.

## Task 6: Produce Pre-Review Candidate Evidence And Stop For Review

**Files:**

- Do not modify tracked repository files.
- Create only call-owned temporary worktrees, observations, build outputs, venvs, and candidate-output directories.

**Interfaces:**

- Consumes: exact clean Task 5 commit.
- Produces: pre-review full-gate evidence, one authoritative candidate-output wheel, its installed-wheel smoke, a same-wheel dual-interpreter proof, and a strict receipt for external authoritative review.
- Failure contract: any failure leaves Task 6 incomplete; there is no residual waiver. Task 6 evidence is invalidated by every later tracked change, including the required review-closure commit.

- [x] **Step 1: Freeze the pre-review commit and create a neutral detached worktree**

```bash
git status --short
candidate_commit="$(git rev-parse HEAD)"
neutral_parent="$(mktemp -d)"
neutral_worktree="${neutral_parent}/mke-candidate"
git worktree add --detach "${neutral_worktree}" "${candidate_commit}"
```

Require the source worktree clean before creation. The temporary worktree name must not contain `proof`, `demo`, `release_consumer_smoke`, or other test command markers that can affect path-sensitive synthetic tests.

- [x] **Step 2: Run full suite, static, packaging, and core proof gates**

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

Require full pytest green with no residual waiver. `UV_OFFLINE=1 uv build` proves ordinary packaging succeeds, but its `dist/` wheel is not final artifact authority and must not be used for installed-wheel smoke. Existing warnings may be reported but not reclassified as failures or silently hidden.

- [x] **Step 3: Run documentation, presentation, and seven-validator gates**

```bash
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_*documentation.py \
  tests/scripts/test_release_presentation_audit.py
```

Generate fresh E1/E2/E3-A/E3-B observations by reusing the corrected Task 4 Step 1 sequence in full, including the call-owned hidden numeric protocol, `refresh-scope` before `eval retrieval-numeric`, the exact `jq` integrity assertion, trap cleanup, and proof that the hidden protocol no longer exists. A stale checked-in-protocol E2 observation is prohibited. Then run all seven canonical validator commands from Task 4 Step 2 and require every validator green.

- [x] **Step 4: Run the once-only candidate-output same-wheel proof**

Verify the exact interpreters without substitution, then invoke the source-pack proof exactly once:

```bash
python312="$(command -v python3.12)"
python313="$(command -v python3.13)"
"${python312}" --version
"${python313}" --version
candidate_parent="$(mktemp -d)"
candidate_output="${candidate_parent}/mke-v0.1.2-candidate"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "${python312}" \
  --python "${python313}" \
  --candidate-output "${candidate_output}" \
  --json
```

The invocation must internally build one wheel, prove that exact wheel in both interpreter cells, and atomically publish exactly one wheel plus one receipt. Missing Python 3.12/3.13 interpreters or offline dependencies are environment hard stops; do not substitute, download, or enable network fallback.

- [x] **Step 5: Run installed-wheel smoke against the candidate-output wheel**

Parse the strict receipt and locate the exact candidate-output wheel. Do not infer equivalence from filename or version, and do not substitute the `dist/` wheel. Require the wheel bytes and SHA-256 to match the receipt, then run:

```bash
UV_OFFLINE=1 uv run python scripts/release_consumer_smoke.py \
  --wheel "${candidate_wheel}" --json
```

Require `status=passed`, installed package/module metadata `0.1.2`, an external working directory, and all proof/demo/CLI/MCP substeps passed against the receipt-bound candidate-output wheel.

- [x] **Step 6: Verify receipt coherence and final scope**

Require:

- exactly one `multimodal_knowledge_engine-0.1.2-py3-none-any.whl` and one receipt in candidate output;
- receipt schema `mke.candidate_artifact_receipt.v1`;
- `source_commit == candidate_commit`;
- package version `0.1.2`;
- wheel filename, bytes, SHA-256, proof input SHA-256, dual-interpreter result, installed-smoke input SHA-256, and canonical receipt SHA agree;
- candidate path is outside the repository and no candidate file is tracked;
- the `dist/` wheel is treated only as packaging evidence and never as equivalent authority by filename/version alone.

Run:

```bash
git -C "${neutral_worktree}" diff --check \
  16fae017ced5fe67da3fae4a01f26e9e9f1084aa.."${candidate_commit}"
git -C "${neutral_worktree}" status --short
git diff --name-status \
  16fae017ced5fe67da3fae4a01f26e9e9f1084aa.."${candidate_commit}"
```

Require no out-of-scope runtime/schema/dependency/OCR/CI change, `src/mke/__init__.py` as the only `src/mke` diff, a clean neutral worktree, preserved historical release identities, and no private path, credential, traceback, private workflow, unsupported production claim, stale current command, or incomplete marker in changed public text.

- [x] **Step 7: Report pre-review evidence and stop**

Report the branch, exact pre-review commit, commit series, changed-file set, diff stat, RED/GREEN evidence, full gates, validator results, interpreter versions, identity-refresh evidence, candidate-output wheel filename/bytes/SHA-256, receipt SHA-256 and `source_commit`, installed-smoke result, remaining risks, and clean status. Final artifact claims must reference only the candidate-output wheel and receipt.

Preserve review-relevant evidence, remove only call-owned temporary resources when safe, and stop for external authoritative review. Do not push, create a PR, merge, tag, create a GitHub Release, or mark the candidate final. Task 6 is only a pre-review evidence checkpoint.

## Task 7: Finalize After Authoritative Review And Re-Prove The Exact Commit

**Files:**

- Modify after a clean/accepted authority verdict:
  - `docs/superpowers/specs/2026-07-14-v0-1-2-release-closeout-design.md`
  - `docs/superpowers/plans/2026-07-14-v0-1-2-release-closeout-implementation.md`
  - `docs/superpowers/reviews/2026-07-14-v0-1-2-release-implementation-review.md`
- Do not modify tracked files after the review-closure commit.

**Interfaces:**

- Consumes: Task 6 pre-review evidence and an external authoritative review verdict.
- Produces: an accepted-but-unpublished review-closure commit and fresh final reviewed candidate evidence bound to that exact commit.
- Failure contract: findings, tracked changes, or reused evidence prevent final local-candidate status.

- [x] **Step 1: Resolve authoritative review findings before closure**

Stop after Task 6 and wait for external authoritative review. If review has findings, fix only within the approved release scope using TDD, run targeted verification, and obtain targeted re-review. Do not enter closure while any finding remains unresolved.

- [x] **Step 2: Record the clean/accepted authority verdict**

After a clean/accepted verdict, update plan checkboxes/status, spec status, and `docs/superpowers/reviews/2026-07-14-v0-1-2-release-implementation-review.md` to an accurate accepted-but-unpublished state. Record the reviewed implementation commit, findings and their resolution, and Task 6 pre-review evidence. Do not claim push, PR, merge, tag, Release, publication, or final-main verification.

- [x] **Step 3: Commit the review closure**

Stage only the three durable status files after exact diff review, then commit:

```bash
git diff --check
git add docs/superpowers/specs/2026-07-14-v0-1-2-release-closeout-design.md \
  docs/superpowers/plans/2026-07-14-v0-1-2-release-closeout-implementation.md \
  docs/superpowers/reviews/2026-07-14-v0-1-2-release-implementation-review.md
git diff --cached --check
git commit -m "docs(release): accept v0.1.2 candidate review"
```

The docs-only commit creates a new final commit and immediately invalidates every Task 6 wheel, receipt, observation, build output, and candidate result.

- [ ] **Step 4: Create a fresh neutral worktree and rerun Task 6 in full**

Freeze the review-closure commit, create a new neutral detached worktree, and rerun every Task 6 step in order. Do not reuse the old wheel, receipt, observed JSON, build output, venv, candidate directory, or temporary worktree. The new candidate-output receipt must have `source_commit` equal to the review-closure commit.

- [ ] **Step 5: Re-prove the final candidate-output wheel**

Run the once-only Python 3.12/3.13 candidate-output proof on the review-closure commit, parse the new exact wheel from its receipt, and run installed-wheel consumer smoke against that wheel. Require the new receipt SHA-256, exact wheel SHA-256, source commit, dual-interpreter proof, and installed smoke to agree. The `dist/` wheel remains packaging-only evidence.

- [ ] **Step 6: Freeze the final reviewed local candidate and stop**

After the complete rerun, make no tracked repository write. Any later tracked change invalidates the evidence and requires another full rerun. Report only the new review-closure commit, new candidate-output wheel filename/bytes/SHA-256, new receipt SHA-256/source commit, and fresh gate results as final reviewed local-candidate evidence.

Task 7 completion makes the local candidate eligible for a separate push/PR authorization. It does not authorize push, PR, merge, tag, GitHub Release, registry publication, or deployment.

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
| Validators have not passed against a complete validation mirror containing every proposed dependency byte | Stop before feature-worktree application; staged top-level paths with the old repository root are not valid evidence. |
| Validation-mirror changed paths or bytes differ from the exact staged candidate set | Stop, discard call-owned mirror/staging, and report the mismatch; do not apply downstream bytes. |
| Downstream apply or post-apply validation fails | Restore every touched downstream path from call-owned backup and verify exact restoration before stopping. |
| Downstream restoration is not exact | Hard stop, report exact dirty paths, and do not stage or commit any conditional identity file. |
| Conditional artifact changed set exceeds the expected chain | Stop and report the exact extra paths. |
| Python 3.12/3.13 or offline dependencies are unavailable | Report environment blocker; do not substitute, download, or use the network. |
| Full pytest has any failure in the neutral worktree | Task 6 remains incomplete; no residual waiver. |
| Candidate receipt commit/wheel identity differs | Delete only call-owned invalid output, fix the cause, recommit if needed, and rerun the complete final gate. |
| `dist/` wheel is used as final artifact authority or installed-smoke input | Stop; use only the exact candidate-output wheel bound by the receipt SHA-256. |
| Source-pack proof is invoked more than once in one candidate gate | Invalidate the gate and rerun from a fresh neutral worktree with one candidate-output invocation. |
| Authoritative review has unresolved findings | Stop before review closure; fix within scope, verify, and obtain targeted re-review. |
| Review closure or any later tracked change changes the candidate commit | Invalidate all prior wheel, receipt, observation, build, and temporary-worktree evidence; rerun Task 6 in full under Task 7. |
| Task 7 reuses any Task 6 output | Invalidate the final rerun and restart it from a fresh neutral worktree and call-owned directories. |
| Tag/Release action is requested during implementation | Stop; publication requires a separate explicit authorization after merge and final-main verification. |

## Completion Boundary

Task 6 completes only a pre-review evidence checkpoint and must stop for external authoritative review. Task 7 alone can produce the final reviewed local candidate: it records the accepted-but-unpublished review closure, invalidates all pre-review artifact evidence, and reruns the complete gate on the exact new commit. `UV_OFFLINE=1 uv build` remains packaging evidence; final acceptance and reporting use only the candidate-output wheel filename, bytes, SHA-256, receipt SHA-256, and receipt-bound source commit. The final rerun must perform candidate-output same-wheel proof once, then installed smoke against that exact receipt-bound wheel. No tracked write may follow the rerun.

This plan does not complete release publication.

Later stages remain separately authorized:

1. push and create the release PR;
2. merge after hosted checks pass;
3. rerun the entire final gate on the exact resulting `main` commit;
4. create annotated tag `v0.1.2` and GitHub Release only after explicit publication authorization;
5. run downloaded public-archive smoke and land a separate durable post-release closeout if needed.

The OCR branch remains independent throughout.
