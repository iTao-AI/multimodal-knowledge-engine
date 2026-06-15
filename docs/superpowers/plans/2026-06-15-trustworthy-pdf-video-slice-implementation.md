# Trustworthy PDF And Video Slice Implementation Plan

> For agentic workers: keep this plan current as work completes. Do not copy private planning
> notes into this repository. Public source of truth is ADR-0001, ADR-0002, this plan, tests, and
> actual command output.

Status: Approved for implementation.

## Scope

Implement the first useful MKE product proof in three PRs:

1. PR 2: text-layer PDF happy path with minimal Publication correctness.
2. PR 3: failure isolation, reprocess/retry proof, and `mke demo --verify`.
3. PR 4: short video timestamp Evidence using the same lifecycle.

## PR 2: PDF Happy Path With Minimal Publication Correctness

Files expected to change:

- `src/mke/domain/`
- `src/mke/application/`
- `src/mke/ports/`
- `src/mke/adapters/sqlite/`
- `src/mke/adapters/pdf/`
- `src/mke/interfaces/`
- `tests/`
- `docs/explanation/architecture.md`
- `docs/reference/contracts.md`

- [x] Add domain states and identifiers for `Library`, `Source`, `Asset`, `Run`, `Evidence`,
  `RunManifest`, and `Publication`.
- [x] Add SQLite migrations for Source active Publication, active revision, requested generation,
  Runs, Run manifests, Evidence, Publications, and active FTS5 projection.
- [x] Ensure SQLite enables `foreign_keys`, uses WAL, sets `busy_timeout`, and probes FTS5.
- [x] Add Run creation that increments `Source.requested_generation` and captures
  `Run.source_generation` plus `Run.based_on_active_revision` in one transaction.
- [x] Add text-layer PDF extraction for a public-safe fixture PDF.
- [x] Persist candidate Evidence and Run manifest in relational tables.
- [x] Validate counts, locators, extractor fingerprint, and required stages before activation.
- [x] Activate Publication in one transaction: generation/revision check, Publication insert,
  active FTS5 replacement, active pointer switch, active revision increment, Run `published`
  state, and Run event.
- [x] Mark stale Runs `superseded` without changing active Search visibility.
- [x] Add narrow CLI commands for local PDF ingest and Search.
- [x] Add tests for Run states, manifest validation, active-only Search, stale Run rejection,
  invalid PDFs, no-text PDFs, and FTS query escaping.
- [x] Update docs for implemented PDF commands and known non-goals.

## PR 3: Reliability Proof And Golden Demo

Files expected to change:

- `src/mke/application/`
- `src/mke/adapters/sqlite/`
- `src/mke/interfaces/`
- `tests/fixtures/pdf/`
- `tests/`
- `.github/workflows/ci.yml`
- `README.md`
- `README_CN.md`
- `docs/tutorials/getting-started.md`
- `docs/reference/cli.md`
- `docs/reference/contracts.md`
- `docs/how-to/`

- [ ] Add reprocess and retry lineage.
- [ ] Add append-only Run event query support.
- [ ] Add interrupted Run handling at startup without claiming automatic checkpoint resume.
- [ ] Add failure injection before validation, during candidate writes, during active FTS5
  replacement, after Publication insert, after active pointer switch, and during activation
  conflict.
- [ ] Prove every failed path leaves previous active Search results unchanged.
- [ ] Add `mke demo --verify` as a deterministic offline product proof using a temporary SQLite
  workspace and repository fixture PDF.
- [ ] Define demo phases, stdout shape, exit codes, cleanup behavior, and expected duration.
- [ ] Add CLI error contracts covering problem, cause, active Publication impact, and next step.
- [ ] Add `docs/reference/cli.md` with implemented versus planned command status.
- [ ] Update README and getting-started tutorial so the first proof path is
  `uv sync --locked && uv run mke demo --verify`.
- [ ] Update CI to run the wheel-installed `mke demo --verify`.
- [ ] Document default DB path, `--db`, demo DB isolation, migration, reset, and local cleanup.

## PR 4: Short Video Timestamp Evidence

Files expected to change:

- `docs/decisions/`
- `docs/superpowers/specs/`
- `src/mke/adapters/video/`
- `src/mke/application/`
- `tests/fixtures/video/`
- `tests/`
- `docs/reference/cli.md`

- [ ] Add or update ADR for video dependency and transcription strategy.
- [ ] Decide and document `ffmpeg` handling, supported codecs, transcription adapter,
  model/cache behavior, offline behavior, fixture license, fixture size, and CI strategy.
- [ ] Persist timestamp Evidence using integer millisecond time ranges.
- [ ] Reuse the PR 2/3 Source Publication lifecycle without weakening PDF semantics.
- [ ] Add failure tests for missing audio, unsupported codec, transcription failure, and unstable
  timestamp locator generation.
- [ ] Extend `mke demo --verify` to prove one PDF and one short video.

## Verification

Run commands that exist in the repository at the time of each PR:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
```

After PR 3:

```bash
uv run mke demo --verify
```

CI must also run the wheel-installed version of `mke demo --verify`.

## Documentation Gate

Each PR must update documentation in the same branch as behavior. If a command is planned but
not implemented, the docs must say so explicitly.
