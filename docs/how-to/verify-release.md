# Verify The Release

This guide separates three checks:

1. Stage 1 repository readiness on the release presentation branch.
2. Stage 2 installed-package consumer smoke before any tag is created.
3. Post-tag archive smoke after a GitHub Release exists.

Do not tag or publish `v0.1.0` until Stage 1 and Stage 2 have both merged.

## Stage 1 Repository Readiness

Run these commands from the release presentation branch:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
uv run python scripts/release_presentation_audit.py --root .
git diff --check origin/main...HEAD
```

The presentation audit checks that package version identity, README posture, release notes, and
comparison-only retrieval wording agree on `v0.1.0`.

## Stage 2 Consumer Smoke

Stage 2 must run from a separate branch after Stage 1 merges. It proves the built package works
outside the source checkout before the release tag is created.

Run:

```bash
uv build
uv run python scripts/release_consumer_smoke.py --wheel dist/*.whl --json
```

The consumer smoke should:

- build the wheel;
- install the wheel into a fresh temporary environment outside the repository;
- clear source-tree import state such as `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`;
- verify `mke.__file__` resolves inside installed site-packages, not `src/mke`;
- run `mke proof run`;
- run `mke demo --verify`;
- run a lightweight CLI Search/Ask path;
- run a minimal MCP contract or owner-startup smoke.

The script copies only the public proof/demo fixtures into the external temporary workspace and
prints stable JSON, for example `{"status": "passed", ...}` on success or
`{"status": "failed", "code": "..."}` on failure.

Core consumer smoke must not require `[embedding]`, `[transcription]`, package index access beyond
normal wheel installation, or model downloads. Optional extras can have separate reported checks.

## Post-Tag Archive Smoke

After Stage 1 and Stage 2 merge, create the annotated tag and GitHub Release only with explicit
authorization. Then verify the public archive from a clean temporary directory:

```bash
archive_dir="$(mktemp -d)"
cd "$archive_dir"
gh release download v0.1.0 --repo iTao-AI/multimodal-knowledge-engine --archive=tar.gz
tar -xzf multimodal-knowledge-engine-v0.1.0.tar.gz
cd multimodal-knowledge-engine-0.1.0
uv sync --locked
uv run mke proof run
uv run mke demo --verify
```

Record the tag, commit, archive checksum, and smoke result in the release closeout.
