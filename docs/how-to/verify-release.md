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
downstream candidate boundaries, and comparison-only retrieval wording agree on `v0.1.2`.

## Stage 2 Clean Candidate Verification

Stage 2 runs only from a clean committed release candidate. `uv build` remains the ordinary
packaging gate. Its `dist/` wheel may be smoke-tested as packaging evidence, but final artifact
authority comes from the candidate-output wheel and its exact receipt SHA-256 binding.

Run:

```bash
UV_OFFLINE=1 uv build
uv run python scripts/release_consumer_smoke.py \
  --wheel dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl --json

candidate_parent="$(mktemp -d)"
candidate_output="${candidate_parent}/mke-v0.1.2-candidate"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --candidate-output "${candidate_output}" \
  --json
```

The consumer smoke should:

- build the wheel;
- install the wheel into a fresh temporary environment outside the repository;
- clear source-tree import state such as `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`;
- verify `mke.__file__` resolves inside installed site-packages, not `src/mke`;
- verify installed `mke.__version__` and package metadata both equal `0.1.2`;
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
gh release download v0.1.2 --repo iTao-AI/multimodal-knowledge-engine --archive=tar.gz
tar -xzf multimodal-knowledge-engine-0.1.2.tar.gz
cd multimodal-knowledge-engine-0.1.2
uv sync --locked
uv run mke proof run
uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
```

Record the tag object SHA, target commit, publication timestamp, archive filename, archive SHA-256,
and smoke result in a separate durable release closeout after those facts exist.
