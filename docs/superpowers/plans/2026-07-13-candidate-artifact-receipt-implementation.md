# MKE Candidate Artifact Receipt Prerequisite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Do not use
> subagents unless the user separately requests them.

**Goal:** Extend MKE's existing same-wheel consumer source-pack proof so a clean reviewed
commit can produce an exact candidate wheel and a strict
`mke.candidate_artifact_receipt.v1` for downstream Night Voyager verification.

**Architecture:** Keep the existing controller as the single wheel builder and proof owner.
It continues to install the same wheel in fresh Python 3.12 and 3.13 environments, then
optionally publishes that already-proven wheel and a canonical receipt through an atomic,
operator-selected maintainer output. The output is not a Release, PyPI artifact, or product
runtime surface.

**Tech Stack:** Python 3.12/3.13, `uv`, existing stdio MCP proof, pytest, Ruff, Pyright,
GitHub Actions.

## Global Constraints

- Implementation base is the latest clean MKE `main` after the current OCR phase is either
  merged or explicitly excluded. At plan time `main`/`origin/main` is
  `6333612732d0fd832f572f55868b9c2a1d01fc92`; OCR branch
  `91fc807830a01e2cf4f71f40f0bdbeea2d4a1bcf` does not modify consumed v1 MCP or existing
  consumer-proof files.
- Re-query the selected base before implementation. If OCR or another branch changes
  `pyproject.toml`, `uv.lock`, v1 MCP schemas/runtime, or consumer proof files, stop for
  targeted review.
- Preserve package version `0.1.1` unless a separate release decision changes it. This task
  creates a candidate artifact, not a tag, GitHub Release, or PyPI upload.
- Build exactly one wheel and prove those exact bytes in both supported Python minors before
  publishing any output.
- Existing proof stdout success and failure contracts remain backward compatible.
- Candidate output contains only the wheel and
  `candidate-artifact-receipt.json`; it contains no repository path, environment value,
  Evidence text, MKE opaque ID, traceback, stderr, credential, hostname, or username.
- Source commit is derived from a clean Git tree. Dirty trees and non-Git snapshots may run
  the existing proof but cannot publish a candidate artifact.
- The output directory is maintainer input, must not already exist, and is published
  atomically only after functional proof and owned-temp cleanup both succeed.
- Do not alter OCR, retrieval semantics, v1 response schemas, CLI/MCP product behavior,
  database formats, dependencies, version, Release files, or evaluation artifacts.
- Before implementation, mechanically land this approved plan at
  `docs/superpowers/plans/2026-07-13-candidate-artifact-receipt-implementation.md`, review
  that docs-only diff, and merge it through its own PR. Do not combine MKE and Night
  Voyager changes in one execution task, branch, or PR.

---

## File and responsibility map

- `scripts/consumer_source_pack_proof.py`: canonical receipt construction, clean-source
  identity, optional atomic artifact publication, and unchanged controller output.
- `tests/scripts/test_consumer_source_pack_proof.py`: receipt closure, same-wheel binding,
  dirty-tree rejection, atomic publication, cleanup precedence, CLI, and redaction tests.
- `.github/workflows/consumer-source-pack-proof.yml`: exercise candidate-output generation
  in the existing hosted same-wheel job without making an upload or release claim.
- `docs/how-to/run-consumer-source-pack-proof.md`: maintainer candidate-output command,
  receipt reference, limitations, and downstream handoff boundary.
- `tests/evaluation/test_consumer_source_pack_documentation.py`: public wording and command
  regression.

## Frozen receipt contract

The strict receipt has exactly these fields:

```python
class CandidateArtifactReceipt(TypedDict):
    schema_version: Literal["mke.candidate_artifact_receipt.v1"]
    repository: Literal["iTao-AI/multimodal-knowledge-engine"]
    source_commit: str
    package_name: Literal["multimodal-knowledge-engine"]
    package_version: str
    wheel_filename: str
    wheel_bytes: int
    wheel_sha256: str
    requires_python: str
    consumer_proof_schema: Literal["mke.consumer_source_pack_proof.v1"]
    consumer_proof_status: Literal["passed"]
    proof_input_wheel_sha256: str
    receipt_sha256: str
```

`source_commit` is the exact Git commit ID and is 40 lowercase hexadecimal characters because
this repository uses the `sha1` object format. Candidate receipt creation fails closed for any
other object format; an object-format migration requires an explicit schema and downstream
contract review. `wheel_sha256`, `proof_input_wheel_sha256`, and `receipt_sha256` are 64 lowercase
hexadecimal SHA-256 digests. `wheel_sha256 == proof_input_wheel_sha256` is mandatory. Receipt
hashing uses UTF-8 JSON, ASCII escaping, sorted keys, compact separators, no NaN, and omits
`receipt_sha256` from its own input.

### Task 1: Freeze candidate receipt construction

**Files:**

- Modify: `scripts/consumer_source_pack_proof.py`
- Modify: `tests/scripts/test_consumer_source_pack_proof.py`

**Interfaces:**

- Consumes: the exact wheel path built by `run_proof`, validated installed package version,
  current proof result, and a clean Git repository.
- Produces:
  `build_candidate_receipt(repository: Path, wheel: Path, package_version: str,
  proof_result: Mapping[str, object]) -> dict[str, object]` and
  `canonical_sha256(value: Mapping[str, object]) -> str`.

- [ ] **Step 1: Write RED receipt contract tests**

Add tests that build a temporary Git repository with one clean commit and assert:

```python
receipt = proof.build_candidate_receipt(repository, wheel, "0.1.1", success)
assert set(receipt) == {
    "schema_version", "repository", "source_commit", "package_name",
    "package_version", "wheel_filename", "wheel_bytes", "wheel_sha256",
    "requires_python", "consumer_proof_schema", "consumer_proof_status",
    "proof_input_wheel_sha256", "receipt_sha256",
}
assert receipt["schema_version"] == "mke.candidate_artifact_receipt.v1"
assert receipt["wheel_sha256"] == receipt["proof_input_wheel_sha256"]
assert receipt["receipt_sha256"] == proof.canonical_sha256(
    {key: value for key, value in receipt.items() if key != "receipt_sha256"}
)
```

Also assert dirty Git status, missing Git metadata, wrong package version, failed proof,
zero-byte wheel, invalid wheel filename, and a result not bound to the current wheel all
raise `ControllerError("candidate_artifact_invalid")`.

- [ ] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_consumer_source_pack_proof.py \
  -k 'candidate_receipt or clean_source_commit'
```

Expected: FAIL because the receipt functions and `candidate_artifact_invalid` code do not
exist.

- [ ] **Step 3: Add the strict pure helpers**

Add `hashlib`, `tomllib`, and these exact constants/signatures:

```python
_CANDIDATE_RECEIPT_SCHEMA = "mke.candidate_artifact_receipt.v1"
_CONSUMER_PROOF_SCHEMA = "mke.consumer_source_pack_proof.v1"
_REPOSITORY = "iTao-AI/multimodal-knowledge-engine"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

def canonical_sha256(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

`build_candidate_receipt` must call `git status --porcelain=v1 --untracked-files=all` and
`git rev-parse HEAD`, parse `project.name`, `project.version`, and `project.requires-python`
from `pyproject.toml`, hash the already-built wheel bytes, require
`proof_result["status"] == "passed"`, set the same digest as the proof-input digest, and
then compute the receipt digest.

Add `candidate_artifact_invalid` to the controller's closed stable failure-code set. Do not
add receipt fields to the existing public proof result.

- [ ] **Step 4: Run GREEN and static checks**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_consumer_source_pack_proof.py \
  -k 'candidate_receipt or clean_source_commit'
UV_OFFLINE=1 uv run ruff check scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
UV_OFFLINE=1 uv run pyright scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
```

Expected: focused tests pass; Ruff and Pyright report no errors.

- [ ] **Step 5: Commit**

```bash
git add scripts/consumer_source_pack_proof.py tests/scripts/test_consumer_source_pack_proof.py
git commit -m "feat(proof): define candidate artifact receipt"
```

### Task 2: Publish only the already-proven wheel atomically

**Files:**

- Modify: `scripts/consumer_source_pack_proof.py`
- Modify: `tests/scripts/test_consumer_source_pack_proof.py`

**Interfaces:**

- Consumes: Task 1 receipt builder and the single `wheel` path created inside `run_proof`.
- Produces: optional `ProofConfig.candidate_output: Path | None`; when set, the final
  directory contains exactly the proven wheel and `candidate-artifact-receipt.json`.

- [ ] **Step 1: Write RED atomic-output tests**

Cover:

```python
files = sorted(path.name for path in output.iterdir())
assert files == ["candidate-artifact-receipt.json", "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"]
assert (output / files[1]).read_bytes() == built_wheel_bytes
assert json.loads((output / files[0]).read_text())["wheel_sha256"] == hashlib.sha256(
    built_wheel_bytes
).hexdigest()
```

Require no output for functional failure, client failure, dirty tree, root cleanup failure,
copy/write failure, any pre-existing output path, or receipt mismatch. Verify no staging
directory remains after any path. Verify `cleanup_failed` still overrides an earlier
candidate publication error when owned temp cleanup cannot be proven.

- [ ] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_consumer_source_pack_proof.py \
  -k 'candidate_output or atomic_publication'
```

Expected: FAIL because `ProofConfig` has no candidate output and no files are published.

- [ ] **Step 3: Implement staging and final publication**

Extend the config without changing existing callers:

```python
@dataclass(frozen=True)
class ProofConfig:
    repository: Path
    python_interpreters: tuple[Path, Path]
    command_timeout_seconds: float
    max_stdout_bytes: int
    max_stderr_bytes: int
    candidate_output: Path | None = None
```

Implementation order is fixed:

1. Build exactly one wheel in the existing owned root.
2. Run both interpreter proofs using that exact path.
3. Build the candidate receipt from the successful aggregate result.
4. Copy wheel and canonical receipt into a hidden staging directory adjacent to the final
   output; `fsync` both files and directory.
5. Remove and verify all existing owned proof state.
6. Atomically rename staging to the requested final directory.
7. If any step fails, remove only staging/owned paths and emit the closed stable code.

Do not accept symlink output parents or an existing non-empty final directory. Resolve the
parent once and keep every staging/final path under that parent.

- [ ] **Step 4: Add the CLI flag without changing stdout**

```python
parser.add_argument("--candidate-output", type=Path)
```

Pass it into `ProofConfig`. Success stdout remains the existing
`{"proof":"consumer_source_pack",...}` object. Failure remains exactly
`{"status":"failed","code":"<stable_code>"}`.

- [ ] **Step 5: Run GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_consumer_source_pack_proof.py
UV_OFFLINE=1 uv run ruff check scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
UV_OFFLINE=1 uv run pyright scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
```

- [ ] **Step 6: Commit**

```bash
git add scripts/consumer_source_pack_proof.py tests/scripts/test_consumer_source_pack_proof.py
git commit -m "feat(proof): publish exact candidate wheel atomically"
```

### Task 3: Exercise and document the candidate lane

**Files:**

- Modify: `.github/workflows/consumer-source-pack-proof.yml`
- Modify: `docs/how-to/run-consumer-source-pack-proof.md`
- Modify: `tests/evaluation/test_consumer_source_pack_documentation.py`
- Modify: `tests/scripts/test_consumer_source_pack_proof.py`

**Interfaces:**

- Consumes: `--candidate-output` from Task 2.
- Produces: hosted execution of the publication path plus a maintainer-only local command.

- [ ] **Step 1: Write RED workflow/documentation tests**

Require the hosted command to contain exactly one proof invocation and:

```text
--candidate-output "$RUNNER_TEMP/mke-candidate"
```

Require the how-to to show:

```bash
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --candidate-output artifacts/m4b-candidate \
  --json
```

Require wording that the output is operator-supplied, local, not uploaded by the workflow,
not a Release/PyPI artifact, and must be regenerated from the exact merged clean commit.

- [ ] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_consumer_source_pack_proof.py -k workflow \
  tests/evaluation/test_consumer_source_pack_documentation.py
```

- [ ] **Step 3: Update workflow and docs**

Add `--candidate-output "$RUNNER_TEMP/mke-candidate"` only to the existing offline proof
step. Do not add `upload-artifact`, Release permissions, secrets, a new job, or a required
downstream callback. Update the how-to's output contract with all receipt fields and its
canonical hash rule.

- [ ] **Step 4: Run GREEN and full MKE gates**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_consumer_source_pack_proof.py \
  tests/evaluation/test_consumer_source_pack_documentation.py
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/consumer-source-pack-proof.yml \
  docs/how-to/run-consumer-source-pack-proof.md \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  tests/scripts/test_consumer_source_pack_proof.py
git commit -m "docs(proof): document candidate artifact handoff"
```

### Task 4: Local branch closeout and post-merge artifact gate

**Files:** No new code unless verification exposes a focused defect.

**Interfaces:** Produces a clean MKE branch for authority review. Artifact generation from
the merged commit is a later authorized operation, not part of the implementation branch.

- [ ] **Step 1: Run the exact local candidate path on the feature branch**

```bash
OUTPUT="artifacts/m4b-candidate-$(git rev-parse --short=12 HEAD)"
test ! -e "$OUTPUT"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --candidate-output "$OUTPUT" \
  --json
```

Expected: existing success stdout; output directory contains exactly one wheel and one
receipt; receipt `source_commit` equals feature HEAD and both wheel digests match.

- [ ] **Step 2: Prove cleanup and public hygiene**

```bash
git status --short
git diff --check
OUTPUT="artifacts/m4b-candidate-$(git rev-parse --short=12 HEAD)"
find "$OUTPUT" -maxdepth 1 -type f -print
```

`artifacts/` remains ignored and must not be staged. The Git worktree must be clean.

- [ ] **Step 3: Stop for authority review**

Report branch/worktree/base/HEAD, commits, full diff, RED/GREEN evidence, actual gates,
documentation impact, and remaining risk. Do not push or create a PR.

- [ ] **Step 4: Post-merge operational gate**

Only after separate push/PR/merge authorization and successful hosted checks:

1. fast-forward a clean local MKE `main` to the merge commit;
2. rerun the candidate-output command on that exact clean merge commit;
3. record wheel and receipt paths outside Git;
4. independently verify receipt SHA, wheel SHA, `source_commit`, hosted proof run, and
   absence of uncommitted files;
5. hand only those two artifact paths and public commit/run evidence to the Night Voyager
   authority window.

Do not tag, publish, upload, create a GitHub Release, or change credentials.

## Self-review checklist

- Spec coverage: same-wheel identity, clean source commit, canonical receipt, atomic
  operator handoff, hosted path exercise, redaction, cleanup, and non-Release claims are
  assigned to Tasks 1-4.
- Placeholder scan: concrete artifact identity values are generated only from the eventual
  merged clean commit; no checked-in placeholder is permitted.
- Type consistency: `ProofConfig.candidate_output`, `build_candidate_receipt`, stable code,
  filenames, receipt fields, and CLI flag are identical across tasks.
- Scope: no OCR, product MCP, retrieval, dependency, version, release, or downstream repo
  change is included.
