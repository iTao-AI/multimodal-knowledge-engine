# Verify The Release

For v0.1.5 evaluators, use the source archive or checkout in a prepared cache-warmed environment:
build one exact wheel, run `release_consumer_smoke.py`, then follow the completeness-aware stdio MCP
flow. GitHub Release has zero assets and PyPI is absent.

## Stable proof code recovery

These stable proof-controller codes identify the failed operation and its bounded recovery. This
table is documentation; proof JSON remains exactly `{"status","code"}` on failure and is not
relabeled as the product CLI/MCP `problem/cause/next_step` schema.

| code | problem | likely cause | bounded next action |
|---|---|---|---|
| `candidate_artifact_invalid` | Candidate authority is invalid. | Output identity, receipt, or source seal is unsafe. | Stop; use a fresh absent candidate output under the owning gate. |
| `cleanup_failed` | Call-owned cleanup did not finish. | A retained process or filesystem condition blocked removal. | Retain the exact path and inspect it; do not broaden cleanup. |
| `cli_ask_failed` | Installed CLI Ask failed. | The installed wheel, fixture, or active Publication did not satisfy Ask. | Inspect the bounded command result, restore the fixture, and rerun the owning smoke. |
| `cli_ingest_failed` | Installed CLI ingest failed. | The public fixture or isolated runtime was not ingestible. | Restore the documented fixture and rerun the owning smoke. |
| `cli_search_failed` | Installed CLI Search failed. | The isolated Library did not expose expected active Evidence. | Inspect Publication state, restore the fixture, and rerun the owning smoke. |
| `command_could_not_start` | A required subprocess did not start. | The executable or prepared environment is unavailable. | Verify the declared executable and cache-warmed environment, then rerun once. |
| `command_failed` | A required subprocess exited nonzero. | The command reported a bounded proof failure. | Inspect its retained stdout/stderr and fix only the named prerequisite. |
| `command_output_exceeded` | Subprocess output crossed its safety bound. | A command emitted unexpectedly large output. | Stop; inspect the retained bounded prefix before changing the output limit. |
| `command_timed_out` | A required subprocess exceeded its time bound. | The process stalled or the prepared environment is unhealthy. | Stop the owning gate and inspect the retained timeout evidence. |
| `consumer_failed` | Installed consumer execution failed. | A consumer step did not complete under the exact wheel. | Inspect the consumer receipt and rerun only after correcting its prerequisite. |
| `consumer_payload_invalid` | Consumer JSON is invalid. | Output was missing, malformed, or outside the closed schema. | Inspect the retained payload and restore the expected controller version. |
| `consumer_proof_failed` | Consumer proof reported failure. | One exact-wheel consumer lane did not pass. | Keep the wheel and receipt; inspect the failed lane before any fresh invocation. |
| `consumer_schema_invalid` | Consumer result schema is invalid. | Required keys or value types drifted. | Restore the documented schema producer; do not reinterpret the payload. |
| `consumer_smoke_failed` | Release consumer smoke failed unexpectedly. | The controller raised outside its stable step failures. | Inspect retained stderr and fix the first bounded cause before rerunning. |
| `demo_failed` | Installed demo verification failed. | The wheel or copied demo fixture did not satisfy the demo contract. | Restore the public demo fixture and rerun the owning smoke. |
| `environment_create_failed` | Isolated environment creation failed. | The selected interpreter or cache could not create the environment. | Verify the prepared interpreter/cache and recreate only the isolated environment. |
| `external_isolation_failed` | Consumer isolation is invalid. | Runtime or import state still resolves into the source checkout. | Remove the leaked environment variable or path and recreate the isolated lane. |
| `fixture_setup_failed` | Public fixture setup failed. | A documented proof fixture is missing or could not be copied. | Restore the documented fixture and rerun the owning controller. |
| `fixture_unavailable` | A required public fixture is unavailable. | The source checkout or archive lacks the declared fixture. | Use the complete source archive or checkout; do not synthesize the fixture. |
| `install_failed` | Exact-wheel installation failed. | The wheel, interpreter, constraints, or warm cache is unsuitable. | Verify those four inputs and recreate only the failed install environment. |
| `installed_identity_failed` | Installed package identity is wrong. | Module, metadata, executable, or site-packages authority drifted. | Stop; inspect the exact wheel and isolated interpreter identity. |
| `locked_constraints_mismatch` | Constraints do not match `uv.lock`. | The supplied constraints were generated from different lock bytes. | Re-export twice from the exact source seal and require byte equality. |
| `locked_constraints_unavailable` | Exact constraints are unavailable. | The constraints file is missing or unreadable. | Provide the verified lock-derived constraints before running the proof. |
| `manifest_locator_mismatch` | Manifest locator identity is inconsistent. | A locator no longer matches its declared Source/Evidence mapping. | Stop; restore the exact manifest and source inputs without normalization. |
| `manifest_mapping_ambiguous` | Manifest mapping is ambiguous. | More than one entry can satisfy the requested mapping. | Stop; correct the manifest to one exact mapping before retrying. |
| `manifest_mapping_missing` | Manifest mapping is missing. | No entry binds the requested Source/Evidence identity. | Restore the required manifest entry and rerun the owning controller. |
| `mcp_contract_failed` | MCP contract verification failed. | Tool inventory, schema, or response behavior drifted. | Inspect the first contract mismatch; do not weaken the canonical fixture. |
| `mcp_startup_timeout` | stdio MCP did not become ready. | The installed server stalled during bounded startup. | Stop the lane and inspect retained startup stderr and process state. |
| `mcp_tool_timeout` | An MCP tool call exceeded its bound. | The server or tool stalled after startup. | Stop the lane and inspect the retained request/tool evidence. |
| `mcp_transport_failed` | stdio MCP transport failed. | Framing, process exit, or SDK transport broke. | Inspect the retained transport error and restore the exact installed command. |
| `observation_state_mismatch` | Persisted observation state is inconsistent. | The observed receipt does not match the sealed source or lifecycle state. | Stop; retain evidence and obtain the owning observation decision. |
| `producer_failed` | Candidate producer failed. | The source-pack producer could not complete its exact-wheel workflow. | Inspect the first producer failure; do not reuse partial output. |
| `proof_failed` | A proof controller failed unexpectedly. | An unclassified internal proof step raised or returned failure. | Inspect retained stderr and fix the first bounded prerequisite. |
| `python_interpreter_unavailable` | A required Python minor is unavailable. | The supplied Python 3.12 or 3.13 executable is missing or wrong. | Provide the prepared exact interpreter; do not download one in an offline gate. |
| `retrieval_order_publication_durability_unconfirmed` | Historical publication durability was not confirmed. | The maintenance attempt lacks durable publication evidence. | Historical maintenance only: retain evidence and stop without a release claim. |
| `retrieval_order_publication_failed_before_visibility` | Historical publication failed before visibility. | The maintenance publication never became authoritative. | Historical maintenance only: retain evidence and stop without retrying publication. |
| `retrieval_order_source_pack_already_started` | Historical source-pack attempt was already started. | The one-shot attempt-claim state is no longer fresh. | Historical maintenance only: keep the attempt terminal and do not reuse it. |
| `retrieval_order_source_pack_attempt_terminal` | Historical source-pack attempt is terminal. | A prior attempt already completed or failed closed. | Historical maintenance only: retain the terminal receipt; do not retry it. |
| `retrieval_order_source_pack_claim_invalid` | Historical attempt claim is invalid. | Attempt identity or ownership does not match the sealed source. | Historical maintenance only: retain evidence and stop without normalizing it. |
| `runtime_root_inside_repository` | External runtime is inside the repository. | The chosen isolation path violates source/runtime separation. | Select a fresh physical runtime root outside the repository. |
| `server_exit_nonzero` | MCP server exited nonzero. | The installed server terminated during the proof. | Inspect retained stderr and fix the first server failure before rerunning. |
| `source_pack_identity_mismatch` | Source-pack identity does not match the seal. | Commit, package, wheel, or receipt identity drifted. | Stop; use the exact sealed source and a fresh absent output. |
| `source_pack_manifest_invalid` | Source-pack manifest is invalid. | The manifest bytes or closed schema are malformed. | Restore the exact manifest producer; do not repair the receipt by hand. |
| `venv_failed` | Isolated virtual environment failed. | Environment creation or its interpreter binding failed. | Recreate the isolated environment with the prepared interpreter and warm cache. |
| `wheel_build_failed` | Wheel build failed. | The sealed source or prepared build cache cannot produce the wheel. | Inspect the retained build output and fix only the declared build prerequisite. |
| `wheel_invalid` | Built or supplied wheel is invalid. | Filename, metadata, contents, or digest failed validation. | Stop; retain the wheel and inspect the exact failed identity check. |
| `wheel_unavailable` | Required wheel is unavailable. | No exact visible wheel was produced or supplied. | Build or supply one exact wheel under the owning controller gate. |

This guide separates four ordered stages:

1. Stage 1 repository readiness on the release-candidate branch.
2. Stage 2 clean-commit candidate verification and exact artifact receipt.
3. Stage 3 complete final gate on the exact merged `main` commit.
4. Stage 4 separately authorized tag, GitHub Release, and public-archive smoke.

`v0.1.0` and `v0.1.1` completed the earlier three-check workflow: repository readiness,
installed-package smoke, and post-tag archive smoke. The records below preserve their release
identity and archive-smoke evidence. The current four-stage workflow adds an exact candidate
receipt and a separate final-main gate; those newer requirements are not retroactively attributed
to the earlier releases.

## Stage 1 Release Candidate Readiness

Run these commands from the release presentation branch:

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
git diff --check origin/main...HEAD
```

The presentation audit checks that package version identity, README posture, release notes,
Compiled Library Export, OCR Phase 0 boundaries, and comparison-only retrieval wording agree on
`v0.1.5`.

Bounded direct audio adds a model-free pre-authorization gate:

```bash
UV_OFFLINE=1 uv run mke proof direct-audio --json
```

This does not run real ASR. The terminal installed-wheel proof, final candidate wheel, exact owner
footprint value, and fixed-fixture Darwin arm64 observations remain separately authorized later
gates. They are not completed by the repository-readiness procedure on this page.

## Stage 2 Clean Candidate Verification

Stage 2 runs only from a clean committed release candidate. `uv build` remains the ordinary
packaging gate. Its `dist/` wheel may be smoke-tested as packaging evidence, but final artifact
authority comes from the candidate-output wheel and its exact receipt SHA-256 binding.

Run:

```bash
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run python scripts/release_consumer_smoke.py \
  --wheel dist/multimodal_knowledge_engine-0.1.5-py3-none-any.whl --json

candidate_parent="$(mktemp -d)"
candidate_output="${candidate_parent}/mke-v0.1.5-candidate"
PYTHON312="$(command -v python3.12)"
PYTHON313="$(command -v python3.13)"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "${PYTHON312}" \
  --python "${PYTHON313}" \
  --candidate-output "${candidate_output}" \
  --json

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
expected_wheel_name = "multimodal_knowledge_engine-0.1.5-py3-none-any.whl"
assert {entry.name for entry in entries} == {receipt_name, expected_wheel_name}
receipt_bytes = (root / receipt_name).read_bytes()
receipt = json.loads(receipt_bytes)
assert isinstance(receipt, dict)
expected_keys = {
    "schema_version", "repository", "source_commit", "package_name", "package_version",
    "wheel_filename", "wheel_bytes", "wheel_sha256", "requires_python",
    "consumer_proof_schema", "consumer_proof_status", "proof_input_wheel_sha256",
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
assert receipt["schema_version"] == "mke.candidate_artifact_receipt.v1"
assert receipt["repository"] == "iTao-AI/multimodal-knowledge-engine"
assert receipt["source_commit"] == head
assert receipt["package_name"] == project["name"] == "multimodal-knowledge-engine"
assert receipt["package_version"] == project["version"] == "0.1.5"
assert receipt["requires_python"] == project["requires-python"]
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
    after.st_dev, after.st_ino, after.st_size
)
wheel_sha256 = hashlib.sha256(wheel_bytes).hexdigest()
assert isinstance(receipt["wheel_bytes"], int) and not isinstance(receipt["wheel_bytes"], bool)
assert receipt["wheel_bytes"] == len(wheel_bytes) == after.st_size
assert re.fullmatch(r"[0-9a-f]{64}", receipt["wheel_sha256"])
assert receipt["wheel_sha256"] == receipt["proof_input_wheel_sha256"] == wheel_sha256

without_digest = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
canonical_without_digest = json.dumps(
    without_digest, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
).encode("utf-8")
assert receipt["receipt_sha256"] == hashlib.sha256(canonical_without_digest).hexdigest()
output.write_text(
    json.dumps(
        {"candidate_wheel": str(wheel_path), "wheel_sha256": wheel_sha256},
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n",
    encoding="utf-8",
)
PY

candidate_wheel="$(python3 - "${candidate_validation}" <<'PY'
import json, pathlib, sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["candidate_wheel"])
PY
)"
UV_OFFLINE=1 uv run python scripts/release_consumer_smoke.py \
  --wheel "${candidate_wheel}" \
  --python "${PYTHON312}" \
  --json
UV_OFFLINE=1 uv run python scripts/release_consumer_smoke.py \
  --wheel "${candidate_wheel}" \
  --python "${PYTHON313}" \
  --json

UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "${PYTHON312}" \
  --python "${PYTHON313}" \
  --mke-wheel "${candidate_wheel}" \
  --json > "${candidate_parent}/compiled-export-proof.json"

UV_OFFLINE=1 uv run python - \
  "${candidate_validation}" "${candidate_parent}/compiled-export-proof.json" <<'PY'
import json
import pathlib
import sys

validated = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
proof = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
assert proof["schema_version"] == "mke.compiled_library_export_proof.v1"
assert proof["status"] == "passed"
assert proof["interpreter_count"] == 2
assert proof["proof_input_wheel_sha256"] == validated["wheel_sha256"]
print("compiled_export_candidate_digest=matched")
PY
```

The consumer smoke should:

- build the wheel;
- install the wheel into a fresh temporary environment outside the repository;
- clear source-tree import state such as `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`;
- verify `mke.__file__` resolves inside installed site-packages, not `src/mke`;
- verify installed `mke.__version__` and package metadata both equal `0.1.5`;
- run `mke proof run`;
- run `mke demo --verify`;
- run a lightweight CLI Search/Ask path;
- run a minimal MCP contract or owner-startup smoke.

The script copies only the public proof/demo fixtures into the external temporary workspace and
prints stable JSON, for example `{"status": "passed", ...}` on success or
`{"status": "failed", "code": "..."}` on failure.

Core consumer smoke must not require `[embedding]`, `[transcription]`, package index access beyond
normal wheel installation, or model downloads. Optional extras can have separate reported checks.

The source-pack proof internally builds and proves one wheel in both interpreter cells, then
publishes exactly that wheel plus `candidate-artifact-receipt.json`. Locate the wheel inside
`candidate_output` and run `scripts/release_consumer_smoke.py --wheel ... --json` against that
receipt-bound wheel. Filename or version equality with the `dist/` wheel is insufficient; the
receipt's exact wheel SHA-256 is authoritative.

The independent candidate validator above binds the canonical receipt, committed source identity,
package metadata, descriptor-read wheel bytes, size, and SHA-256 before either installed smoke or
Compiled Library Export proof is accepted. The compiled proof must pass on Python 3.12 and 3.13,
and its `proof_input_wheel_sha256` must exactly equal the independently validated candidate wheel
SHA-256.

## Stage 3 Final Main Gate

After the final release-candidate PR merges, check out the resulting `main` commit and rerun every
Stage 1 and Stage 2 command above. Create no tag or GitHub Release unless this final `main` gate
passes and separate release authorization is given. Recreate candidate output on that exact clean
commit; do not reuse a branch wheel, receipt, observed JSON, build output, or temporary worktree.

## Stage 4 Tag, GitHub Release, And Archive Smoke

After the final `main` gate passes, create the annotated tag and GitHub Release only with explicit
authorization. Then verify the public archive from a clean temporary directory:

```bash
archive_dir="$(mktemp -d)"
cd "$archive_dir"
gh release download v0.1.5 --repo iTao-AI/multimodal-knowledge-engine --archive=tar.gz
tar -xzf multimodal-knowledge-engine-v0.1.5.tar.gz
cd multimodal-knowledge-engine-0.1.5
UV_OFFLINE=1 uv sync --locked
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
UV_OFFLINE=1 uv run mke proof direct-audio --json
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root . --json
```

Run a real Compiled Library Export and the standalone standard-library consumer against the public
proof fixtures:

```bash
archive_root="${PWD}"
runtime="$(mktemp -d)"
cp tests/fixtures/local-knowledge-v1/operations-guide.pdf "${runtime}/operations-guide.pdf"
cp tests/fixtures/video/spoken-evidence.mp4 "${runtime}/spoken-evidence.mp4"
cp tests/fixtures/video/short-audio.mp4.mke-transcript.json \
  "${runtime}/spoken-evidence.mp4.mke-transcript.json"
cd "${runtime}"
UV_OFFLINE=1 uv run --project "${archive_root}" mke --db library.sqlite ingest operations-guide.pdf --json
UV_OFFLINE=1 uv run --project "${archive_root}" mke --db library.sqlite ingest spoken-evidence.mp4 --json
UV_OFFLINE=1 uv run --project "${archive_root}" mke --db library.sqlite library export \
  --output compiled-library --json
UV_OFFLINE=1 uv run --project "${archive_root}" python \
  "${archive_root}/scripts/compiled_library_export_consumer.py" \
  --export compiled-library \
  --source "operations-guide=${runtime}/operations-guide.pdf" \
  --source "spoken-evidence=${runtime}/spoken-evidence.mp4" \
  --json
```

Require `status="passed"`, exact portable schemas, two sources, and three Evidence records. Remove
only the call-owned archive and runtime directories after recording their identities.

Do not substitute `scripts/compiled_library_export_proof.py` for this native lane in a GitHub
source archive. That controller binds a clean Git snapshot before it handles a supplied wheel, so
`--mke-wheel` does not replace source authority. Do not synthesize `.git` metadata for archive
smoke.

The completed release records below are durable results of this procedure. Future releases must
record their own tag object SHA, target commit, publication timestamp, archive filename, archive
SHA-256, and smoke result after those facts exist.


## Completed v0.1.5 Release Record

- Tag: `v0.1.5`
- Annotated tag object SHA: `1ca0a0b348638369e8407270ca5f363b0e551a9e`
- Tag target commit: `d258c10dc40bd9eccd67c858b56f4e4cf5fe4610`
- Merge commit: `d258c10dc40bd9eccd67c858b56f4e4cf5fe4610`
- Merge tree: `22756fdfa8ef131d3e28fc2a44acc3f2b6fa32f0`
- GitHub Release URL: https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.5
- Published timestamp: `2026-07-29T01:31:18Z`
- Release state: public, non-draft, non-prerelease.
- Assets: zero
- Post-merge hosted checks: `8/8 SUCCESS` on the merge commit: python 3.12/3.13,
  embedding extra 3.12/3.13, compiled Library export proof, consumer source-pack proof, and
  Analyze actions/python.
- Exact-main proof: full suite `3745 passed, 4 skipped`; Ruff clean; Pyright 0; build, product,
  demo, local-knowledge, Evidence-provenance, model-free direct-audio, presentation, canonical,
  query-plan, numeric, and temporary compatibility gates passed.
- Canonical development freeze SHA-256:
  `0d8761037e9132461a1d6bbf2eac0a39471dfaa38c65acbdc2400a87ff8bffd8`.
- Canonical holdout receipt SHA-256:
  `8f390ada3632c12527eb75747a2ce21721317fffdd30bd9fc177e8f305dc3203`.
- Canonical retrieval artifact SHA-256:
  `104a41a6aa0c719313d508c79d00886a18483bbf3eeeadcdbc8899dd927283c1`.
- Canonical compatibility attempt receipt SHA-256:
  `df18d9738548fa33af5c7f76dfa26e89a721f1c08a2df0e034a7688c67e81604`.
- Canonical compatibility artifact SHA-256:
  `f9a5883f3ac47652cbd18ef0bb08b61ceb00065955a3db575df0fd41689240ba`.
- Fixed query-plan fixture SHA-256:
  `1f6a70a69edb9a3b182e21a9b125a37d81ed4dca869c16d1f5d5b807554ffdc1`.
- Temporary compatibility: seven families; membership, score_hex, non-tied-pair, metric, gate,
  and verdict were all six delta classes zero.
- Release archive: `multimodal-knowledge-engine-v0.1.5.tar.gz`
- Release archive bytes: `4609206`
- Release archive SHA-256: `baccc11f339b1241a454458b80f4faecf0a72297f0fc84184d004942c564dac4`
- Archive manifest SHA-256: `d3c682e085592034c02596a8278cadd309b3464ba3d5249e85c7b2b4e45474ec`
- Normalized archive manifest SHA-256:
  `2214f7478a692b0ddd67baa98dc509e050abc97fa2a0c86d4a33990dacdf6d98`.
- Tagged tree manifest SHA-256:
  `96f9bd404f15d279555e5c2f073b9f5e894d660114e3e6f059fb287b6cc2501d`.
- Public archive source inventory: 602 files, byte-identical before and after proof.
- Archive wheel: `multimodal_knowledge_engine-0.1.5-py3-none-any.whl`
- Archive wheel identity: `421538 bytes`, SHA-256
  `4c2da1a84871e1865b05a720c6ef7b7d2122ed570ec8eb0035627493ba96d281`;
  module and package metadata both report `0.1.5`.
- Git-less allowlist: passed with product proof `8/8`, demo, local-knowledge,
  Evidence-provenance, model-free direct-audio, presentation audit, dual-Python MCP completeness
  on python 3.12/3.13 with 10 tools, native PDF/video ingest, Library export plus standalone
  consumer, and the approved tests `11 passed, 5 warnings`.
- Publication did not change runtime behavior, schema, dependencies, or canonical Evidence.
- Limitations and non-claims: no real ASR or model download; no network during archive sync, build, or proofs; no PyPI, deployment, or runtime promotion; no quality/performance, cold-cache, empty-machine, air-gapped, or cache-portability claim; no comparison or observation conclusion.

## Completed v0.1.4 Release Record

- Release-candidate PR: <https://github.com/iTao-AI/multimodal-knowledge-engine/pull/88>
- Reviewed head: `0a60ff6b63ed497cc570456ad0e1b13a99b56e6d`
- Squash merge commit: `84fb533072a965b2ad833d12723e6ac0fff19d55`
- Reviewed feature tree and merge tree:
  `b1d5a0c767e04dd4d402163f16f3ebdce8b1a787`
- Exact-main hosted checks: 9 completed successfully on the merge commit
- Tag: `v0.1.4`
- Annotated tag object SHA: `5453f2d787185a318794d47f084c0f952939946e`
- Tag target commit: `84fb533072a965b2ad833d12723e6ac0fff19d55`
- GitHub Release:
  <https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.4>
- Published: `2026-07-23T19:07:19Z` by `iTao-AI`
- Release state: latest at publication, non-draft, non-prerelease, with zero extra assets
- Release archive: `multimodal-knowledge-engine-v0.1.4.tar.gz`
- Release archive bytes: `4214296`
- Release archive SHA-256:
  `e9492e5115110c5fa421c565c51226ba0e25d16a62230f92760f13b1ec1a76ce`
- Exact-main candidate wheel: `multimodal_knowledge_engine-0.1.4-py3-none-any.whl`, `353324`
  bytes, SHA-256 `3b3c19fd87d015762a6d446e0e47f8719c87218734faa141915a17cca1fa72e3`.
- Exact-main candidate receipt canonical digest:
  `5b20bbbc829eeb4fa4d066fa83bd1d97f8544ba7865f2db563f1405a0b628b4f`; receipt file
  SHA-256: `f7ceae28989bae12d568a611513a3fac6f848967a3eac923398bb5110de934c2`.
- Reviewed terminal receipt SHA-256:
  `91f3bfcb5e8ef1d1b12d4a31724e0f92f3507ea25c7afaa940e5c430777339fc`.
- Public archive smoke: locked sync, product proof `8/8`, demo `result=passed`, local-knowledge
  proof `status=passed`, Evidence-provenance proof `status=passed`, model-free direct-audio
  `status=passed` with `asr_execution=not_performed`, native Compiled Library Export plus
  standalone consumption with two Sources and three Evidence records, and presentation audit
  `status=ok` with zero violations.
- PyPI and other package registries: not published.
- Deployment: not performed.

The native Export and standalone consumer are the archive-safe Compiled Library authority.
`scripts/compiled_library_export_proof.py` requires clean Git source authority even when
`--mke-wheel` is supplied, so it must not be used as a passing gate from a GitHub source archive
without `.git`. Two such invocations failed closed with `candidate_artifact_invalid`; they remain
failure evidence and were not retried as the successful native lane.

## Completed v0.1.3 Release Record

- Release-candidate PR: <https://github.com/iTao-AI/multimodal-knowledge-engine/pull/73>
- Squash merge commit: `86b8a2d85631f5e94afa49186909ac62ffd54a15`
- Reviewed feature tree and merge tree: `88862bf57464e4eb630eb938a573d5188e3feed6`
- Tag: `v0.1.3`
- Annotated tag object SHA: `447ebdf7416b6c6e25c8f6d2017d1ef48b465c0f`
- Tag target commit: `86b8a2d85631f5e94afa49186909ac62ffd54a15`
- GitHub Release: <https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.3>
- Published: `2026-07-17T02:10:45Z` by `iTao-AI`
- Release state: latest at publication, non-draft, non-prerelease, with zero extra assets
- Release archive: `multimodal-knowledge-engine-0.1.3.tar.gz`
- Release archive bytes: `3691525`
- Release archive SHA-256:
  `a8f0a595f6f039628feb2a9d3e13237b37b000aa311e1b7b7b013e0e8303496e`
- Exact-main candidate wheel: `multimodal_knowledge_engine-0.1.3-py3-none-any.whl`, `309326`
  bytes, SHA-256 `50bccd685957c1b21e9b45d066060f0a89dd7f4e71e6f86b3546ce3ea4a2b036`.
- Exact-main candidate receipt canonical digest:
  `b6527b462c1f76907c46477c30fff1202dfc44ba3c8cea17cb633072c9a1accc`; receipt file
  SHA-256: `fac2dc1b1166712944268e389beef1cd27e740ce32b4f4fa6ffad1808434e4f6`.
- Post-release archive smoke: locked sync, product proof `8/8`, demo `result=passed`, local
  knowledge proof `status=passed`, Evidence provenance proof `status=passed`, and a real Compiled
  Library Export accepted by the standalone consumer with two sources and three Evidence records.
- PyPI and other package registries: not published.
- Deployment: not performed.

## Completed v0.1.2 Release Record

- Tag: `v0.1.2`
- Annotated tag object SHA: `3f693502e87367d2c984fb9a04db83e98b68bab6`
- Tag target commit: `e4be0eee11c671e31c17af8b698bf7921cfc045f`
- GitHub Release: <https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.2>
- Published: `2026-07-14T09:11:16Z` by `iTao-AI`
- Release state: latest at publication, non-draft, non-prerelease, with zero extra assets
- Release archive: `multimodal-knowledge-engine-0.1.2.tar.gz`
- Release archive bytes: `3334646`
- Release archive SHA-256:
  `19004992527b0d7244bf81756eb0d40302720942473cd3a8fcb1211ef46ef5e0`
- Post-release archive smoke: `uv sync --locked`, product proof `8/8`, demo
  `result=passed`, local knowledge proof `status=passed`, and Evidence provenance proof
  `status=passed`.
- PyPI and other package registries: not published.
- Deployment: not performed.

## Completed v0.1.1 Release Record

- Tag: `v0.1.1`
- Tag object SHA: `8e84b9a8638691b4dcb1eff6b8c7d56d8cb8c073`
- Tag target commit: `91abbaeff7aac0a1879e409c38b24c1d4e143d91`
- GitHub Release: <https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.1>
- Published: `2026-07-08T09:09:41Z`
- Release archive: `multimodal-knowledge-engine-0.1.1.tar.gz`
- Release archive SHA-256:
  `caa4f695e87eb4e8569a1c0b5caaed339dccfb53c8b6e074d4020c8743bc8f87`
- Post-release archive smoke: `UV_OFFLINE=1 uv sync --locked`, product proof `8/8`, demo
  `result=passed`, and local knowledge proof `status=passed`.
- PyPI: not published.

## Completed v0.1.0 Release Record

- Tag: `v0.1.0`
- Tag object SHA: `1f6f77bfa9d06b8f4348c864b9704bc338799c70`
- Tag target commit: `7f46fe6b775139d396e3849c9484f454880cb7e8`
- GitHub Release: <https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.0>
- Published: `2026-07-02T12:47:19Z`
- Release archive: `multimodal-knowledge-engine-0.1.0.tar.gz`
- Release archive SHA-256:
  `0ea6fefa1d5c51f7f221841999ce8009756f47f5ce7b88468ae1ef38be45f129`
- Post-release archive smoke: `uv sync --locked`, `uv run mke proof run`, and
  `uv run mke demo --verify` passed from the GitHub Release archive.
- PyPI: not published; the PyPI JSON endpoint returned `404`.
