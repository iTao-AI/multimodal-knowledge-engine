# v0.1.3 Release Closeout Implementation Plan

> **For implementers:** Use `superpowers:executing-plans` as the primary controller,
> `superpowers:test-driven-development` for behavior and contract changes,
> `superpowers:systematic-debugging` for failures, and
> `superpowers:verification-before-completion` before every completion claim.

Status: approved plan pending mechanical landing and implementation dispatch.

**Goal:** Publish `v0.1.3` with Compiled Library Export as the primary capability and PDF OCR
Phase 0 as accurately bounded evaluation evidence, while preserving runtime semantics and proving
the exact release wheel through the existing installed-consumer boundaries.

**Architecture:** Reuse the established four-stage release chain: release-candidate PR, clean
committed candidate evidence, exact merged-main re-verification, then annotated tag/GitHub Release
and public-archive smoke. One release-candidate wheel is authoritative through
`mke.candidate_artifact_receipt.v1`; the independent compiled-export proof must report the same
wheel SHA-256. Version and documentation byte changes may trigger the established retrieval
identity-only closure, but no evaluation semantics may change. Historical OCR evidence remains
bound to its recorded `0.1.2` wheel and is not rewritten.

**Tech Stack:** Python 3.12 and 3.13, uv, Hatchling, pytest, Ruff, Pyright, SQLite, Markdown,
Git, GitHub Actions, and GitHub Releases.

## Provenance And Starting State

- Approved repository baseline: `5d707cfcc98da8ce76d31238c14158cd78b03803`.
- Approved design commit: `990292a23b17eeca6c876f52b79b43cc0a11627f`.
- Design: `docs/superpowers/specs/2026-07-17-v0-1-3-release-closeout-design.md`.
- Branch: `codex/v0-1-3-release-closeout-design`.
- Existing package identity: `0.1.2`.
- Target package and tag identity: `0.1.3` / `v0.1.3`.
- Previous published tag: `v0.1.2`.
- Current release delta is already merged through PR #71 and PR #72; this plan changes release
  identity and presentation, not those implementations.

Before implementation, require the branch to contain only the approved design and this plan on top
of the approved baseline. Re-read `AGENTS.md`, inventory all linked worktrees, and stop if the branch
or worktree has unexplained changes.

## Global Constraints

- Keep runtime Search, Ask, Publication, MCP, retrieval strategy, SQLite schema, and dependencies
  unchanged.
- Do not add production OCR, an OCR public flag, provider configuration, model download, or runtime
  promotion.
- Do not claim verified LLM Wiki compatibility.
- Do not update historical `v0.1.2` release records as if they were current evidence.
- Keep `benchmarks/ocr/candidate-environments.json`, `model-artifacts.json`,
  `provider-startup.json`, and `phase0-scorecard.json` byte-identical.
- Treat hard-coded `0.1.2` values in historical fixtures or compatibility tests as historical until
  a failing current-identity test proves otherwise; do not global-replace version strings.
- `uv.lock` may change only in the root-project version identity. No dependency drift is allowed.
- Use explicit offline-capable Python 3.12 and Python 3.13 executables. Verify their major/minor
  versions before expensive proof work.
- Local candidate output is evidence, not a release asset. Never add it to Git.
- No tracked write may occur after a candidate evidence run that is claimed as final authority.
- The already granted publication authorization is exercised only after the authoritative actual-
  diff review and every gate in this plan passes. Stop on any mismatch.

## File And Responsibility Map

### Current version and smoke identity

- `pyproject.toml`
- `src/mke/__init__.py`
- `uv.lock`
- `tests/test_version_identity.py`
- `tests/test_bootstrap.py`
- `scripts/release_consumer_smoke.py`
- `tests/scripts/test_release_consumer_smoke.py`

### Release presentation contract

- `scripts/release_presentation_audit.py`
- `tests/scripts/test_release_presentation_audit.py`
- `tests/evaluation/test_consumer_source_pack_documentation.py`
- `tests/evaluation/test_compiled_library_export_documentation.py`
- `tests/evaluation/test_dense_documentation.py`

### Current release documentation

- `README.md`
- `README_CN.md`
- `docs/README.md`
- `CHANGELOG.md`
- new `docs/releases/v0.1.3.md`
- `docs/how-to/verify-release.md`
- `docs/how-to/run-consumer-source-pack-proof.md`
- `docs/how-to/run-compiled-library-export-proof.md`
- `docs/how-to/enable-cjk-retrieval.md`
- `docs/how-to/evaluate-dense-retrieval.md`
- `docs/how-to/evaluate-numeric-retrieval.md`
- `docs/how-to/prepare-local-embeddings.md`
- `docs/how-to/run-chinese-retrieval-evaluation.md`
- `docs/reference/cli.md`

Additional release-facing files may be modified only when a failing test or exact version scan
proves they describe the current release rather than historical evidence. Report every such file.

### Conditional retrieval identity closure

At most the established 21-path closure from
`docs/superpowers/plans/2026-07-14-v0-1-2-release-closeout-implementation.md`, Task 4. A smaller
validator-proven dependency-closed subset is preferred. Any larger or different artifact set is a
hard stop.

### Durable review and closeout

- this plan;
- new `docs/superpowers/reviews/2026-07-17-v0-1-3-release-implementation-review.md`;
- new `docs/superpowers/reviews/2026-07-17-v0-1-3-post-release-closeout.md` after publication;
- approved design and `docs/how-to/verify-release.md` in the post-release docs-only closure.

## Task 1: Lock The `0.1.3` Package And Installed-Smoke Identity

**Files:** current version and smoke identity group above.

- [ ] **Step 1: Write current-version RED tests**

Update only current-identity assertions to expect `0.1.3`:

- package metadata and `mke.__version__` agree;
- bootstrap exports `0.1.3`;
- release consumer smoke accepts only installed module and metadata version `0.1.3`;
- the exact wheel name is `multimodal_knowledge_engine-0.1.3-py3-none-any.whl`.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/test_version_identity.py \
  tests/test_bootstrap.py \
  tests/scripts/test_release_consumer_smoke.py
```

Expected RED: failures are version-identity mismatches against `0.1.2`, not unrelated behavior.

- [ ] **Step 2: Bump package and smoke identity minimally**

Set `0.1.3` in `pyproject.toml`, `src/mke/__init__.py`, and
`scripts/release_consumer_smoke.py`. Refresh the lock offline:

```bash
UV_OFFLINE=1 uv lock --offline
```

Inspect `uv.lock` structurally. Only the root `multimodal-knowledge-engine` version may change;
dependency names, versions, sources, markers, hashes, and extras must remain equal.

- [ ] **Step 3: Run Task 1 GREEN and build identity checks**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/test_version_identity.py \
  tests/test_bootstrap.py \
  tests/scripts/test_release_consumer_smoke.py
UV_OFFLINE=1 uv build
python3 - <<'PY'
import pathlib, tomllib, zipfile
wheel = next(pathlib.Path("dist").glob("multimodal_knowledge_engine-0.1.3-*.whl"))
with zipfile.ZipFile(wheel) as archive:
    metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
    metadata = archive.read(metadata_name).decode("utf-8")
assert "Version: 0.1.3\n" in metadata
assert tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"] == "0.1.3"
PY
```

- [ ] **Step 4: Commit Task 1**

Stage only the seven Task 1 files and commit:

```bash
git commit -m "chore(release): set v0.1.3 identity"
```

Do not include generated `dist/` artifacts.

## Task 2: Define The `v0.1.3` Presentation Contract

**Files:** release presentation contract group above.

- [ ] **Step 1: Add RED tests for the current release surfaces**

Update the presentation-audit fixtures to model `0.1.3` and add exact negative cases proving the
audit rejects:

- package/module/docs version disagreement;
- no `docs/releases/v0.1.3.md` current release note;
- Compiled Library Export described only as a future candidate;
- claims of verified LLM Wiki compatibility;
- claims of production OCR, public OCR runtime, provider promotion, general quality, production
  resource limits, or layout reconstruction;
- claims of hosted integration, production adoption, business impact, PyPI, deployment, or extra
  GitHub Release assets;
- promotion of dense/RRF/reranker into the runtime; and
- mutation of the completed `v0.1.2` release record.

Update source-pack documentation tests from the current `v0.1.2` candidate gate to `v0.1.3`.
Replace the compiled-proof phrase `does not release v0.1.3` with a version-neutral requirement such
as `running the proof does not publish a release`.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/evaluation/test_dense_documentation.py
```

Expected RED: current docs still describe `v0.1.2` and the compiled export as unreleased.

- [ ] **Step 2: Update the audit implementation**

Set the current expected version to `0.1.3`. Separate current release files from historical release
records. `docs/releases/v0.1.3.md` is current; `docs/releases/v0.1.2.md` remains a historical record.

Add closed positive requirements for:

- the exact Compiled Library Export headline;
- `mke.compiled_library_export.v1`, `mke.compiled_markdown.v1`, and
  `mke.evidence_ref.v1` boundaries;
- OCR Phase 0 wording, selected planning baseline, and non-production boundary;
- the no-LLM-Wiki-compatibility boundary; and
- the unchanged `cjk-active-scan-overlap-v1` runtime default.

Do not make audit success depend on private paths, timestamps, external consumers, or model caches.

- [ ] **Step 3: Run focused audit tests GREEN and expected-negative audit**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/evaluation/test_dense_documentation.py
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
```

The live audit is expected to fail at this point only on Task 3 documentation gaps and must emit
valid stable JSON. Record its exact violations.

- [ ] **Step 4: Commit Task 2**

```bash
git commit -m "test(release): define v0.1.3 presentation contract"
```

## Task 3: Write The Current Release Documentation

**Files:** current release documentation group above.

- [ ] **Step 1: Classify every `0.1.2` occurrence before editing**

```bash
rg -n "0\\.1\\.2|v0\\.1\\.2|later release decision|current main candidate|does not release v0\\.1\\.3" \
  README.md README_CN.md CHANGELOG.md docs scripts tests pyproject.toml src/mke/__init__.py
```

Classify each occurrence as one of:

1. current release identity that must become `0.1.3`;
2. completed `v0.1.2` historical record that must remain unchanged;
3. frozen OCR/package compatibility evidence that must remain unchanged; or
4. generic test fixture whose version is not current authority and should remain unchanged.

No global replacement is allowed.

- [ ] **Step 2: Create `docs/releases/v0.1.3.md`**

Use these sections:

- `Compiled Library Export`;
- `PDF OCR Phase 0 Evidence`;
- `Verification`;
- `Boundaries`; and
- `References`.

Lead with the approved export headline. Document the exact CLI and portable schemas. State that
PP-OCRv6 medium is only the selected production-planning baseline, PaddleOCR-VL 1.6 is a validated
comparison candidate, numeric measurements are closed-protocol observations, and no production OCR
or LLM Wiki compatibility is released.

- [ ] **Step 3: Update README, docs index, changelog, and how-to guides**

Required presentation:

- `README.md` / `README_CN.md`: `v0.1.3` is current; Compiled Library Export is the lead feature;
  prior Evidence/source-pack capabilities remain; OCR Phase 0 gets a clearly separated evidence
  row and non-production boundary.
- `docs/README.md`: link `v0.1.3` first and update current release/proof wording.
- `CHANGELOG.md`: add `0.1.3` with Added, Verified, and Not included sections.
- `docs/how-to/verify-release.md`: keep completed release records, make `0.1.3` the active four-
  stage commands, and add compiled-proof digest co-binding.
- source-pack how-to: current checkout is a `v0.1.3` candidate; local candidate output remains not
  the final tagged wheel or release asset.
- compiled-export proof how-to: running the proof does not itself publish a release; remove the
  stale statement that the capability is awaiting `v0.1.3`.
- embedding guide: use the current `0.1.3` wheel in the current installation example without
  changing the historical dense evidence decision.
- current deployment-proof command examples in the CJK, numeric, Chinese, dense, and CLI guides:
  use the `0.1.3` wheel while leaving their recorded observations and decisions unchanged.

- [ ] **Step 4: Run documentation and presentation gates GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/evaluation/test_dense_documentation.py
UV_OFFLINE=1 uv run pytest -q tests/evaluation -k "documentation or release"
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
```

Expected audit result: exactly `{"status":"ok","violations":[]}` modulo canonical JSON spacing.

- [ ] **Step 5: Run public-neutral and unsupported-claim scans**

Scan the complete branch diff for private paths, credentials, timestamps presented as future facts,
candidate output directories, source text, raw diagnostics, production OCR claims, verified LLM
Wiki claims, PyPI claims, and deployment claims. Allow only explicit negations and historical facts.

Prove the completed prior release note has not changed:

```bash
git diff --exit-code 5d707cfcc98da8ce76d31238c14158cd78b03803..HEAD -- \
  docs/releases/v0.1.2.md
```

- [ ] **Step 6: Commit Task 3**

```bash
git commit -m "docs(release): prepare v0.1.3 candidate"
```

## Task 4: Close Conditional Retrieval Identities Without Semantic Drift

**Files:** only the established 21-path maximum conditional closure.

- [ ] **Step 1: Freeze the starting commit and observations**

Use the exact Task 4 transaction and observation order from the completed `v0.1.2` plan, replacing
only the hidden protocol filename with `.protocol-lock.v0.1.3-observation.json`. In particular,
refresh the call-owned E2 protocol scope before generating the E2 observation.

Generate fresh E1, E2, E3-A, and E3-B observations in a call-owned temporary directory and require
their integrity assertions before any artifact write.

- [ ] **Step 2: Run all seven canonical validators before writing**

Run the exact E1, E2, E3-A, E3-B, E3-C, E3-D, and E3-E validator commands recorded in the completed
`v0.1.2` plan against the real worktree. If all pass, record `identity_refresh=not_required` and skip
to Step 6. Continue only for source/scope/dependency identity mismatch caused by this branch.

- [ ] **Step 3: Refresh E1 through E3-B atomically when required**

Use only:

```bash
uv run python -m mke.evaluation.artifact_refresh \
  --repository . \
  --e1-observed "${evidence_dir}/e1.json" \
  --e2-observed "${evidence_dir}/e2.json" \
  --e3-observed "${evidence_dir}/e3a.json" \
  --e3b-observed "${evidence_dir}/e3b.json"
```

On failure, run only
`UV_OFFLINE=1 uv run python -m mke.evaluation.artifact_refresh recover --repository .`, then stop.

- [ ] **Step 4: Rebind downstream identities in a detached validation mirror**

Use a call-owned untracked rebinder and the same deterministic builders, 21-path maximum allowlist,
descriptor/backup contract, and full-graph detached validation mirror defined in the completed
`v0.1.2` plan. Require every staged/mirror/worktree byte to agree before applying downstream files.

Before/after normalized semantic projections must be equal for every layer. Reject any change to
observations, ordered results, metrics, thresholds, gates, diagnostics, profile, candidate, status,
verdict, corpus, query, qrels, or fixture content.

- [ ] **Step 5: Prove OCR evidence bytes are unchanged**

Record before and after SHA-256 for:

```text
benchmarks/ocr/candidate-environments.json
benchmarks/ocr/model-artifacts.json
benchmarks/ocr/provider-startup.json
benchmarks/ocr/phase0-scorecard.json
```

All four must remain byte-identical.

Also require exact equality to the approved baseline:

```bash
git diff --exit-code 5d707cfcc98da8ce76d31238c14158cd78b03803..HEAD -- \
  benchmarks/ocr/candidate-environments.json \
  benchmarks/ocr/model-artifacts.json \
  benchmarks/ocr/provider-startup.json \
  benchmarks/ocr/phase0-scorecard.json
```

- [ ] **Step 6: Run artifact regression and all validators GREEN**

Run the exact artifact regression suite and seven validator commands from the completed `v0.1.2`
plan. Optional model replay is not required and must not trigger a package or model download.

- [ ] **Step 7: Commit only the validator-proven subset**

If no files changed, do not create an empty commit. Otherwise stage only exact proven paths:

```bash
git commit -m "test(eval): refresh v0.1.3 release identities"
```

Report the rebinder SHA-256, exact changed set, and per-layer semantic equality.

## Task 5: Finalize Durable Candidate State And Stop For Authority Review

- [ ] **Step 1: Create the implementation review record in pending state**

Create `docs/superpowers/reviews/2026-07-17-v0-1-3-release-implementation-review.md` with:

- scope and exact commit sequence;
- package/lock identity;
- documentation claim matrix;
- conditional evaluation closure paths and semantic-equality result;
- OCR byte-identity result;
- verification evidence;
- status `PENDING AUTHORITATIVE REVIEW`.

Update this plan only for Tasks 1 through 4 facts. Do not pre-complete proof, PR, merge, tag, or
publication steps.

- [ ] **Step 2: Commit the durable pre-review state**

```bash
git commit -m "docs(release): record v0.1.3 candidate state"
```

- [ ] **Step 3: Run complete repository gates from the clean commit**

```bash
UV_OFFLINE=1 uv run pytest -q
UV_OFFLINE=1 uv run ruff check .
UV_OFFLINE=1 uv run pyright
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
git diff --check
```

- [ ] **Step 4: Generate exactly one pre-review candidate evidence set**

Validate explicit interpreters first:

```bash
"${PYTHON312}" -c 'import platform,sys; assert sys.version_info[:2] == (3,12); print(platform.machine())'
"${PYTHON313}" -c 'import platform,sys; assert sys.version_info[:2] == (3,13); print(platform.machine())'
```

Then:

```bash
candidate_parent="$(mktemp -d)"
candidate_output="${candidate_parent}/mke-v0.1.3-candidate"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "${PYTHON312}" \
  --python "${PYTHON313}" \
  --candidate-output "${candidate_output}" \
  --json
```

Require exactly one wheel and one receipt. Independently validate the candidate directory and
receipt before using either as authority; do not use a glob-selected `dist/` wheel or an
unvalidated receipt field.

Use a call-owned validator and write its result outside the repository:

```bash
candidate_validation="${candidate_parent}/validated-candidate.json"
UV_OFFLINE=1 uv run python - "${candidate_output}" "${candidate_validation}" <<'PY'
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tomllib

root = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2])
assert root.is_dir() and not root.is_symlink()
entries = list(os.scandir(root))
assert len(entries) == 2
assert all(not entry.is_symlink() and entry.is_file(follow_symlinks=False) for entry in entries)

receipt_name = "candidate-artifact-receipt.json"
assert receipt_name in {entry.name for entry in entries}
receipt_path = root / receipt_name
receipt_bytes = receipt_path.read_bytes()
receipt = json.loads(receipt_bytes)
assert isinstance(receipt, dict)
expected_keys = {
    "schema_version",
    "repository",
    "source_commit",
    "package_name",
    "package_version",
    "wheel_filename",
    "wheel_bytes",
    "wheel_sha256",
    "requires_python",
    "consumer_proof_schema",
    "consumer_proof_status",
    "proof_input_wheel_sha256",
    "receipt_sha256",
}
assert set(receipt) == expected_keys
canonical_receipt = json.dumps(
    receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
).encode("utf-8") + b"\n"
assert receipt_bytes == canonical_receipt

project = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
head = subprocess.run(
    ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
).stdout.strip()
expected_wheel_name = "multimodal_knowledge_engine-0.1.3-py3-none-any.whl"
assert {entry.name for entry in entries} == {receipt_name, expected_wheel_name}
assert receipt["schema_version"] == "mke.candidate_artifact_receipt.v1"
assert receipt["repository"] == "iTao-AI/multimodal-knowledge-engine"
assert receipt["source_commit"] == head
assert receipt["package_name"] == "multimodal-knowledge-engine"
assert receipt["package_version"] == "0.1.3"
assert receipt["requires_python"] == project["requires-python"]
assert project["name"] == "multimodal-knowledge-engine"
assert project["version"] == "0.1.3"
assert receipt["wheel_filename"] == expected_wheel_name
assert receipt["consumer_proof_schema"] == "mke.consumer_source_pack_proof.v1"
assert receipt["consumer_proof_status"] == "passed"

wheel_path = root / expected_wheel_name
flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
descriptor = os.open(wheel_path, flags)
try:
    before = os.fstat(descriptor)
    assert stat.S_ISREG(before.st_mode)
    wheel_bytes = bytearray()
    while chunk := os.read(descriptor, 1024 * 1024):
        wheel_bytes.extend(chunk)
finally:
    os.close(descriptor)
after = os.stat(wheel_path, follow_symlinks=False)
assert stat.S_ISREG(after.st_mode)
assert (before.st_dev, before.st_ino, before.st_size) == (
    after.st_dev,
    after.st_ino,
    after.st_size,
)
wheel_sha256 = hashlib.sha256(wheel_bytes).hexdigest()
assert isinstance(receipt["wheel_bytes"], int) and not isinstance(receipt["wheel_bytes"], bool)
assert receipt["wheel_bytes"] == len(wheel_bytes) == after.st_size
assert re.fullmatch(r"[0-9a-f]{64}", receipt["wheel_sha256"])
assert receipt["wheel_sha256"] == wheel_sha256
assert receipt["proof_input_wheel_sha256"] == wheel_sha256

without_digest = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
canonical_without_digest = json.dumps(
    without_digest, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
).encode("utf-8")
assert receipt["receipt_sha256"] == hashlib.sha256(canonical_without_digest).hexdigest()

validated = {"candidate_wheel": str(wheel_path), "wheel_sha256": wheel_sha256}
output.write_text(
    json.dumps(validated, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY
```

This validation must reject symlinks, non-regular files, extra/trailing directory entries,
non-canonical receipt bytes, unknown or missing receipt keys, and any source/package/wheel/digest
drift.

- [ ] **Step 5: Smoke the exact receipt-bound wheel**

```bash
candidate_wheel="$(python3 - "${candidate_validation}" <<'PY'
import json, pathlib, sys
validated = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(validated["candidate_wheel"])
PY
)"
candidate_wheel_sha256="$(python3 - "${candidate_validation}" <<'PY'
import json, pathlib, sys
validated = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(validated["wheel_sha256"])
PY
)"
UV_OFFLINE=1 uv run python scripts/release_consumer_smoke.py \
  --wheel "${candidate_wheel}" --json
```

- [ ] **Step 6: Run compiled-export proof and co-bind the digest**

```bash
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "${PYTHON312}" \
  --python "${PYTHON313}" \
  --json > "${candidate_parent}/compiled-export-proof.json"
```

Require:

- schema `mke.compiled_library_export_proof.v1`;
- `status="passed"`;
- interpreter count `2`; and
- `proof_input_wheel_sha256` exactly equals `candidate_wheel_sha256` from the independent
  candidate validator. The validator has already proved both receipt digest fields equal that
  descriptor-read wheel digest.

- [ ] **Step 7: Hard stop for authoritative actual-diff review**

Report final HEAD, commit series, exact diff, full gates, receipt/wheel/source commit/digests,
compiled proof digest equality, OCR frozen hashes, and remaining boundaries. Do not push or create a
PR. Preserve call-owned candidate evidence for review.

## Task 6: Resolve Findings And Produce The Final Committed Candidate

This task starts only after findings return from the authoritative actual-diff review.

- [ ] **Step 1: Verify each finding before editing**

Use `superpowers:receiving-code-review`. Reproduce the finding on the real authority path. If a
finding is not reproducible or no longer release-blocking, document why rather than expanding scope.

- [ ] **Step 2: Repair with targeted TDD and rerun affected gates**

Keep each fix bounded. Any change to version, docs, audit, workflow, or source identity may require
another evaluation identity closure. Do not weaken tests, validators, or claim boundaries.

- [ ] **Step 3: Update the implementation review to accepted state**

Record exact reviewed HEAD, findings and resolutions, targeted re-review, and verdict
`ACCEPTED / CLEARED FOR RELEASE-CANDIDATE PR`. Complete only facts that already exist.

- [ ] **Step 4: Commit the review closure**

```bash
git commit -m "docs(release): accept v0.1.3 candidate review"
```

This tracked commit invalidates Task 5 candidate evidence.

- [ ] **Step 5: Re-run the entire Task 5 gate from scratch**

From the clean closure commit, rerun full pytest, Ruff, Pyright, build, product proof, demo, local
knowledge proof, Evidence provenance proof, presentation audit, all required retrieval validators,
source-pack candidate output, exact receipt-bound installed smoke, compiled-export proof, and digest
co-binding. Reuse no branch artifact, receipt, log, or temporary worktree.

- [ ] **Step 6: Stop with a clean final local branch**

Do not write checkboxes after the final proof. Report the final evidence externally; post-release
closeout will durably record it.

## Task 7: PR, Exact-Main Gate, Publication, And Closeout

Task 7 is executed by explicit follow-up after the authoritative review owner binds the review to
the final HEAD. It is sequential and uses a low-complexity mechanical Git/GitHub pass.

- [ ] **Step 1: Push and open a Draft release-candidate PR**

PR body sections must include the repository-required `Summary`, `Completion`, `Verification`,
`Risk / Impact`, and `Documentation impact`. Optional sections `Scope`, `Claim boundaries`, and
`Publication plan` may follow. Bind the body to exact final HEAD, wheel/receipt/compiled proof
digests, full test count, and frozen OCR hashes. Do not upload candidate artifacts. After creating
or updating the PR, read the body back and require it to be non-empty and to contain every mandatory
section exactly once.

- [ ] **Step 2: Require exact-head CI and platform gates**

Require the PR head to equal the last reviewed HEAD. Require CI Python 3.12/3.13, embedding extras,
consumer source-pack proof, compiled Library export proof, configured CodeQL, mergeability, and
platform review state to be successful. Any new commit requires targeted re-review.

- [ ] **Step 3: Ready and squash merge**

Verify base `main`, then mark Ready and squash merge. Record PR, merge SHA, parents, merged feature
tree, and reviewed-head tree equality.

- [ ] **Step 4: Run the exact merged-main gate**

Fast-forward the primary worktree safely. Require:

```text
HEAD == main == origin/main == exact merge SHA
```

Rerun every Task 6 Step 5 gate from scratch and generate a new candidate receipt bound to the exact
merge SHA. Verify post-merge GitHub workflows for that SHA. Do not tag until all pass.

- [ ] **Step 5: Create and publish `v0.1.3`**

Check that no conflicting tag or Release exists. Then:

```bash
git tag -a v0.1.3 -m "v0.1.3"
git push origin v0.1.3
gh release create v0.1.3 \
  --repo iTao-AI/multimodal-knowledge-engine \
  --title "v0.1.3" \
  --notes-file docs/releases/v0.1.3.md \
  --latest
```

Verify annotated tag object, peeled target, non-draft/non-prerelease/latest state, publication time,
and zero extra assets.

- [ ] **Step 6: Verify the public source archive**

In a clean call-owned directory:

```bash
gh release download v0.1.3 \
  --repo iTao-AI/multimodal-knowledge-engine \
  --archive=tar.gz
shasum -a 256 multimodal-knowledge-engine-0.1.3.tar.gz
tar -xzf multimodal-knowledge-engine-0.1.3.tar.gz
cd multimodal-knowledge-engine-0.1.3
uv sync --locked
uv run mke proof run
uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
```

Check package/module version `0.1.3` and scan archive paths/text for candidate receipts, private
paths, credentials, and private workflow material.

Run a real archive export smoke with the public proof fixtures:

```bash
runtime="$(mktemp -d)"
cp tests/fixtures/local-knowledge-v1/operations-guide.pdf "${runtime}/operations-guide.pdf"
cp tests/fixtures/video/spoken-evidence.mp4 "${runtime}/spoken-evidence.mp4"
cp tests/fixtures/video/short-audio.mp4.mke-transcript.json \
  "${runtime}/spoken-evidence.mp4.mke-transcript.json"
cd "${runtime}"
uv run --project "${OLDPWD}" mke --db library.sqlite ingest operations-guide.pdf --json
uv run --project "${OLDPWD}" mke --db library.sqlite ingest spoken-evidence.mp4 --json
uv run --project "${OLDPWD}" mke --db library.sqlite library export \
  --output compiled-library --json
uv run --project "${OLDPWD}" python \
  "${OLDPWD}/scripts/compiled_library_export_consumer.py" \
  --export compiled-library \
  --source "operations-guide=${runtime}/operations-guide.pdf" \
  --source "spoken-evidence=${runtime}/spoken-evidence.mp4" \
  --json
```

Require `status="passed"`, exact portable schemas, two sources, and three Evidence records. Remove
only call-owned archive/runtime directories after recording identities.

- [ ] **Step 7: Land docs-only post-release closeout**

Create a separate docs-only branch from current `main`. Update only:

- `docs/how-to/verify-release.md` with completed `v0.1.3` facts;
- the `v0.1.3` design status;
- this plan's final historical status/checkboxes;
- the implementation review with merge/final-main/publication evidence; and
- new `docs/superpowers/reviews/2026-07-17-v0-1-3-post-release-closeout.md`.

Run documentation tests, presentation audit, public-neutral scan, and exact changed-file audit.
Create a docs-only PR, require its checks, squash merge, and verify that the published tag target is
unchanged.

- [ ] **Step 8: Perform safe task-owned cleanup**

Only after all required checks and retained-authority proofs pass, remove task-owned clean release
and closeout worktrees/local branches, observe remote branch state, prune stale worktree metadata,
and leave unrelated worktrees and external package/model evidence untouched.

## Completion Boundary

The task is complete only after the public `v0.1.3` GitHub Release and source archive smoke are
verified, the docs-only post-release closeout is merged, `main == origin/main` is clean, and all
task-owned safe cleanup is complete.

The task does not publish PyPI, another registry, a deployed service, model files, production OCR,
or verified LLM Wiki compatibility.
