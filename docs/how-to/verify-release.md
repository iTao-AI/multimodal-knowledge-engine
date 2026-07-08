# Verify The Release

This guide separates three checks:

1. Stage 1 repository readiness on the release presentation branch.
2. Stage 2 installed-package consumer smoke before any tag is created.
3. Post-tag archive smoke after a GitHub Release exists.

`v0.1.0` and `v0.1.1` have completed all three checks. The records below preserve their release
identity and archive-smoke evidence. For the same workflow, Stage 1 and Stage 2 may run together
on a final release-candidate branch, followed by a complete final gate on `main` before separately
authorized tag and GitHub Release creation.

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

## Stage 1 Repository Readiness

Run these commands from the release presentation branch:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
uv run python scripts/release_presentation_audit.py --root .
git diff --check origin/main...HEAD
```

The presentation audit checks that package version identity, README posture, release notes, and
comparison-only retrieval wording agree on `v0.1.1`.

## Stage 2 Consumer Smoke

Stage 2 may run on the same final release-candidate branch as Stage 1. It proves the built package
works outside the source checkout before the release tag is created.

Run:

```bash
uv build
uv run python scripts/release_consumer_smoke.py \
  --wheel dist/multimodal_knowledge_engine-0.1.1-py3-none-any.whl --json
```

The consumer smoke should:

- build the wheel;
- install the wheel into a fresh temporary environment outside the repository;
- clear source-tree import state such as `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`;
- verify `mke.__file__` resolves inside installed site-packages, not `src/mke`;
- verify installed `mke.__version__` and package metadata both equal `0.1.1`;
- run `mke proof run`;
- run `mke demo --verify`;
- run a lightweight CLI Search/Ask path;
- run a minimal MCP contract or owner-startup smoke.

The script copies only the public proof/demo fixtures into the external temporary workspace and
prints stable JSON, for example `{"status": "passed", ...}` on success or
`{"status": "failed", "code": "..."}` on failure.

Core consumer smoke must not require `[embedding]`, `[transcription]`, package index access beyond
normal wheel installation, or model downloads. Optional extras can have separate reported checks.

## Final Pre-Tag Gate On main

After the final release-candidate PR merges, check out the resulting `main` commit and rerun every
Stage 1 and Stage 2 command above. Create no tag or GitHub Release unless this final `main` gate
passes and separate release authorization is given.

## Post-Tag Archive Smoke

After the final `main` gate passes, create the annotated tag and GitHub Release only with explicit
authorization. Then verify the public archive from a clean temporary directory:

```bash
archive_dir="$(mktemp -d)"
cd "$archive_dir"
gh release download v0.1.1 --repo iTao-AI/multimodal-knowledge-engine --archive=tar.gz
tar -xzf multimodal-knowledge-engine-0.1.1.tar.gz
cd multimodal-knowledge-engine-0.1.1
uv sync --locked
uv run mke proof run
uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
```

Record the tag, commit, archive checksum, and smoke result in the release closeout.
