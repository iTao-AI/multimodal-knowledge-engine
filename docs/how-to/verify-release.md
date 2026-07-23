# Verify The Release

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

## Stage 1 Release Candidate Readiness

Run these commands from the release presentation branch:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
uv run python scripts/release_presentation_audit.py --root .
git diff --check origin/main...HEAD
```

The presentation audit checks that package version identity, README posture, release notes,
Compiled Library Export, OCR Phase 0 boundaries, and comparison-only retrieval wording agree on
`v0.1.3`.

The accepted v0.1.4 direct-audio candidate adds a model-free pre-authorization gate:

```bash
UV_OFFLINE=1 uv run mke proof direct-audio --json
```

This does not run real ASR. The terminal installed-wheel proof, final candidate wheel, exact owner
footprint value, and fixed-fixture Darwin arm64 observations remain separately authorized later
gates. They are not completed by the v0.1.3 release procedure on this page.

## Stage 2 Clean Candidate Verification

Stage 2 runs only from a clean committed release candidate. `uv build` remains the ordinary
packaging gate. Its `dist/` wheel may be smoke-tested as packaging evidence, but final artifact
authority comes from the candidate-output wheel and its exact receipt SHA-256 binding.

Run:

```bash
UV_OFFLINE=1 uv build
uv run python scripts/release_consumer_smoke.py \
  --wheel dist/multimodal_knowledge_engine-0.1.3-py3-none-any.whl --json

candidate_parent="$(mktemp -d)"
candidate_output="${candidate_parent}/mke-v0.1.3-candidate"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
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
expected_wheel_name = "multimodal_knowledge_engine-0.1.3-py3-none-any.whl"
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
assert receipt["package_version"] == project["version"] == "0.1.3"
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
  --wheel "${candidate_wheel}" --json

UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
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
- verify installed `mke.__version__` and package metadata both equal `0.1.3`;
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
gh release download v0.1.3 --repo iTao-AI/multimodal-knowledge-engine --archive=tar.gz
tar -xzf multimodal-knowledge-engine-0.1.3.tar.gz
cd multimodal-knowledge-engine-0.1.3
uv sync --locked
uv run mke proof run
uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
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
uv run --project "${archive_root}" mke --db library.sqlite ingest operations-guide.pdf --json
uv run --project "${archive_root}" mke --db library.sqlite ingest spoken-evidence.mp4 --json
uv run --project "${archive_root}" mke --db library.sqlite library export \
  --output compiled-library --json
uv run --project "${archive_root}" python \
  "${archive_root}/scripts/compiled_library_export_consumer.py" \
  --export compiled-library \
  --source "operations-guide=${runtime}/operations-guide.pdf" \
  --source "spoken-evidence=${runtime}/spoken-evidence.mp4" \
  --json
```

Require `status="passed"`, exact portable schemas, two sources, and three Evidence records. Remove
only the call-owned archive and runtime directories after recording their identities.

The completed `v0.1.3` record above is the durable result of this procedure. Future releases must
record their own tag object SHA, target commit, publication timestamp, archive filename, archive
SHA-256, and smoke result after those facts exist.
