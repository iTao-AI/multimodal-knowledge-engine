# Bounded Direct Audio Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Status: CLEARED FOR STAGED IMPLEMENTATION; PR A REQUIRES SEPARATE DISPATCH

This document does not itself authorize PR A, implementation, acquisition, or external side
effects.

The superseding feasibility-authority amendments are recorded in
`docs/superpowers/reviews/2026-07-18-bounded-direct-audio-intake-authority-amendment.md`.

**Goal:** Add bounded local MP3, WAV, and M4A intake for voice notes and clips or excerpts from meetings, interviews, lectures, and downloaded spoken material; publish timestamp Evidence through the existing Run/Publication authority; and export complete mixed Libraries through an explicit Compiled Library Export v2 contract.

**Architecture:** Introduce a project-owned audio protocol and immutable media snapshot without reinterpreting the historical video contract. Reuse the owner-configured cache-only faster-whisper runtime behind a separate audio child protocol, route Python/CLI/MCP through one `KnowledgeEngine.ingest_file()` dispatcher, and add an explicit export v2 while preserving v1 bytes and consumers. Required CI stays model-free; package, binary, license, installed-wheel, and real cache-only provider evidence remain explicit later gates.

**Tech Stack:** Python 3.12/3.13, SQLite, PyAV from the existing `[transcription]` extra, faster-whisper, CTranslate2, MCP Python SDK, uv, pytest, Ruff, Pyright, GitHub Actions.

## Global Constraints

- Planning baseline is `6dfc1882a78f23023e26018df7ec1d60adcd8e3e`; execution must first reconcile the approved spec and plan onto current `main` without silently carrying stale assumptions.
- Delivery uses ordered PR A, PR B, and PR C gates. PR A may run in parallel with the independent
  LLM Wiki compatibility docs/evidence PR. PR B waits for accepted/merged PR A but need not wait for
  LLM Wiki. PR C waits for accepted/merged PR A, PR B, and LLM Wiki compatibility evidence.
- Dependabot PR #76 and other dependency maintenance remain independent; do not merge their lockfile or workflow changes into this feature.
- This source is approved for mechanical landing and full-plan review only. It does not authorize implementation, dependency or model acquisition, push, PR, merge, tag, release, registry publication, deployment, or operator-data ingestion.
- Supported inputs are `.mp3` as `audio/mpeg` with MPEG Layer III, `.wav` as `audio/wav` with signed 16-bit little-endian PCM, and `.m4a` as `audio/mp4` with AAC-LC.
- Each accepted file has exactly one decodable audio stream; zero video, subtitle, data, or attachment streams; one or two channels; sample rate from 8,000 through 48,000 Hz inclusive; `0 < input_bytes <= 100 * 1024 * 1024`; and `0 < media_duration_ms <= 900_000`.
- An accepted transcript has at most 10,000 non-empty, ordered, finite, non-overlapping integer-millisecond segments inside media duration.
- Source SHA-256, media inspection, and transcription must bind the same immutable regular-file bytes. Symlinks, replacement, truncation, growth, and same-size digest drift fail closed before candidate persistence or Publication.
- A digest already stored under a different media type fails closed; SQLite must not silently reuse an Asset with mismatched `media_type`.
- Reuse the locked `[transcription]` dependency set. Do not add a Python dependency, cloud API, hosted fallback, AutoDL path, or normal-run network/download behavior.
- `mke.audio_transcript.v1`, `AudioMediaInfo`, `ParsedAudioTranscript`, `AudioTranscriptExtractionResult`, and `AudioIngestError` are additive. Do not rename or reinterpret `mke.video_transcript.v1` or its DTOs.
- The audio manifest uses `REQUIRED_AUDIO_STAGES = frozenset({"audio_transcription", "candidate_evidence"})` and the exact grammar `faster-whisper-audio-v1:[0-9a-f]{64}`.
- The default sidecar owner does not accept direct audio. It fails before Source or Run creation with the stable next step `configure_faster_whisper_owner`.
- `KnowledgeEngine.ingest_file(path: Path) -> IngestResult` is the canonical suffix dispatcher. Python, CLI, and stdio MCP must converge on it.
- MCP `ingest_file` remains path-only. Do not add request-time provider, model, revision, cache, device, language, download, command, URL, endpoint, token, or credential fields.
- Do not expand the shared `_ALLOWLISTED_CAUSES` or the frozen read-tool/source-pack fixture. Direct-audio failure serialization is operation-local.
- Existing PDF and MP4 behavior, read-only MCP schemas, EvidenceRef v1, Search/Ask DTOs, retrieval runtime, and transcript reports remain compatible.
- `mke.compiled_library_export.v1`, `mke.compiled_markdown.v1`, `mke.compiled_library_export_response.v1`, their exact default behavior, and the existing standalone consumer remain unchanged.
- Add only explicit `v2` export contracts. `library export` without `--format-version` remains v1;
  v1 fails closed when an active audio Source makes the Library incomplete; `--format-version v2`
  exports the complete active PDF, comparison-only PDF OCR, video, and audio Library. The exact v2
  closed shape is not frozen until PR C reads the accepted LLM Wiki v1 compatibility evidence and
  completes the bounded schema reconciliation checkpoint.
- Required CI is offline and model-free. Real ASR runs only against an already prepared exact local model revision and must prove network denial.
- Synthetic fixtures must be redistribution-safe, committed with generation recipe, license/provenance, byte size, SHA-256, and exact media profile. No private recording or operator material enters Git.
- PR A must audit the exact locked external dependency set and constraints, canonical wheelhouse
  manifest, installed PyAV wheel, linked or bundled FFmpeg component inventory/direct evidence,
  fixture identities and redistribution authority, the closed external-binary redistribution
  literals, validation platform, fixed target-executable identity probe, and Darwin arm64
  supervisory allocator/process-group authority. Missing fixture redistribution authority, local
  dependency feasibility, target identity, or supervisor proof is a no-go hard stop before PR B;
  transitive external-binary redistribution clearance is not a stop while no such binaries are
  distributed or claimed.
- The PR A receipt does not bind MKE source or an MKE wheel. Refresh it only when an external
  dependency or constraints, prepared wheelhouse, PyAV wheel, platform, supervisory mechanism,
  target-probe contract, external-binary non-redistribution boundary, or fixture authority changes.
  PR C separately binds its fresh final MKE wheel to the accepted PR A receipt digest, installed
  package set, and prepared model tree.
- Numeric ceilings observed on the fixed proof corpus are evidence, not a production SLA or cross-platform performance claim.
- Direct audio is composed only on Darwin arm64 when the owner explicitly configures both
  `RuntimeConfig.direct_audio_footprint_bytes` and
  `RuntimeConfig.direct_audio_footprint_budget_mode="baseline_plus"`. The bytes value is a positive
  non-boolean integer with no default or recommended value. The pair is absent by default, applies
  identically to the supervised inspection and transcription children, and never appears in the
  path-only `ingest_file` request.
- PR A's `24 MiB baseline_plus` controlled-allocator value proves only the supervisory mechanism;
  it is not a PyAV/faster-whisper runtime budget. `1 GiB absolute` has no authority. PR C does not
  change the PR A/PR B mechanism or refresh the PR A receipt. The direct-audio composition boundary
  accepts only `baseline_plus` without narrowing the generic `SupervisedProcessProfile` contract.
- Missing direct-audio supervision fails before Source, Run, snapshot, child, or model work with
  `direct audio supervision is not configured / configure_direct_audio_supervision`. A non-Darwin
  arm64 runtime fails at the same boundary with
  `direct audio runtime is supported only on Darwin arm64 / run_on_supported_darwin_arm64`. Both
  conditions disable only direct audio; PDF, video, and the historical faster-whisper video owner
  remain compatible.
- PR A owns Task 1, PR B owns Tasks 2-4, and PR C owns Tasks 5-10. A v0.1.4
  version/tag/Release/archive-smoke closeout is a separate post-merge PR and separate authorization.
- Full-length meetings, interviews, lectures, long-audio workers, chunking, resume, and streaming
  remain non-goals. Do not raise the 15-minute or 100-MiB limits.

---

## Plan Authority And Review Gate

1. Mechanically land the approved design as
   `docs/superpowers/specs/2026-07-18-bounded-direct-audio-intake-design.md` and this plan as
   `docs/superpowers/plans/2026-07-18-bounded-direct-audio-intake-implementation.md` in one clean,
   isolated project worktree.
2. Verify source/worktree/index/commit bytes and public-neutral content, then create a docs-only local
   commit.
3. Run one full `autoplan` against that exact committed plan revision. Do not stack a second full
   manual plan-review chain on the same revision.
4. Persist only durable, public-neutral accepted amendments in the plan and, if useful, one review
   record under `docs/superpowers/reviews/`; do not commit raw GStack artifacts.
5. Stop for a separate PR A dispatch after the reviewed plan is marked
   `CLEARED FOR STAGED IMPLEMENTATION; PR A REQUIRES SEPARATE DISPATCH`.

## Planned File Structure

### Create

- `src/mke/adapters/audio/__init__.py`: exports the project-owned audio adapter surface.
- `src/mke/adapters/audio/contracts.py`: canonical audio extractor identity and fingerprint.
- `src/mke/adapters/audio/schema.py`: strict `mke.audio_transcript.v1` parser and serializer.
- `src/mke/adapters/audio/inspection.py`: immutable descriptor-bound snapshot, pure profile normalization, and closed inspection DTOs.
- `src/mke/adapters/audio/inspection_cli.py`: bounded package-owned PyAV audio-v1 inspection child.
- `src/mke/adapters/audio/faster_whisper_cli.py`: first-party cache-only audio child protocol.
- `tests/fixtures/audio/README.md`: fixture provenance, generation, checksums, and profiles.
- `tests/fixtures/audio/direct-audio.mp3`: redistribution-safe synthetic MP3 fixture.
- `tests/fixtures/audio/direct-audio.wav`: redistribution-safe synthetic PCM fixture.
- `tests/fixtures/audio/direct-audio.m4a`: redistribution-safe synthetic AAC-LC fixture.
- `tests/adapters/test_audio_fixtures.py`: exact fixture identity, profile, and provenance tests.
- `tests/domain/test_audio_contracts.py`: audio DTO, fingerprint, manifest, and wire tests.
- `tests/adapters/test_audio_inspection.py`: descriptor identity, profile, bounds, and cleanup tests.
- `tests/adapters/test_audio_inspection_cli.py`: bounded native inspection child and Darwin arm64
  supervisory tests.
- `tests/adapters/test_faster_whisper_audio_cli.py`: first-party child protocol tests.
- `tests/application/test_audio_publication.py`: audio lifecycle, rollback, concurrency, and dispatcher tests.
- `tests/interfaces/test_cli_audio.py`: CLI routing, readiness, success, and public errors.
- `tests/scripts/test_compiled_library_export_consumer_v2.py`: independent v2 consumer tests.
- `scripts/compiled_library_export_consumer_v2.py`: standard-library-only v2 consumer.
- `src/mke/proof/direct_audio.py`: model-free direct-audio product proof report.
- `scripts/direct_audio_dependency_receipt.py`: installed package/binary inventory, direct evidence,
  fixture, target-executable probe, non-redistribution, and supervisory receipt controller.
- `tests/scripts/test_direct_audio_dependency_receipt.py`: receipt controller and canonical validator tests.
- `benchmarks/audio/dependency-artifacts.json`: canonical public-safe dependency and binary evidence.
- `scripts/direct_audio_deployment_proof.py`: installed-wheel Python 3.12/3.13 and real cache-only orchestration.
- `tests/proof/test_direct_audio.py`: proof invariant and redaction tests.
- `tests/scripts/test_direct_audio_deployment_proof.py`: installed-wheel controller tests.
- `docs/decisions/0011-bounded-direct-audio-intake.md`: accepted architecture and compatibility decision.
- `docs/how-to/use-direct-audio.md`: operator preparation, doctor, ingest, consume, export, and recovery.
- `docs/how-to/run-direct-audio-proof.md`: model-free and real proof boundaries.
- `docs/reference/direct-audio-dependency-and-license-evidence.md`: exact external dependency,
  PyAV/FFmpeg inventory/direct evidence, external-binary non-redistribution literals, Darwin arm64
  supervisory authority, target-executable probe, constraints, wheelhouse, and fixture evidence
  boundary.
- `tests/evaluation/test_direct_audio_documentation.py`: documentation contract and claim-boundary tests.
- `docs/superpowers/reviews/2026-07-18-bounded-direct-audio-intake-implementation-review.md`: final actual-diff review record.

### Modify

- `src/mke/domain/__init__.py`: additive audio DTOs, required stages, fingerprint recognition, and manifest validation.
- `src/mke/application/__init__.py`: `AudioIngestError`, `ingest_audio`, canonical `ingest_file`, and audio lifecycle.
- `src/mke/adapters/sqlite/__init__.py`: digest/media-type authority, audio report activation, and export snapshot support.
- `src/mke/adapters/video/faster_whisper.py`: extract only genuinely shared private model/transcription helpers; preserve video behavior.
- `src/mke/adapters/video/providers.py`: preserve video provider; share only typed private runtime composition when required.
- `src/mke/adapters/video/process.py`: add the receipt-backed Darwin arm64 polling supervisor and
  process-group cleanup without weakening existing cancellation.
- `src/mke/runtime.py`: owner-selected audio provider composition and operation-local audio exit mapping.
- `src/mke/cli.py`: canonical ingest routing, direct-audio presentation, proof command, and export format selector.
- `src/mke/interfaces/mcp_contract.py`: path validation before resolution, canonical dispatcher, and operation-local error mapping.
- `src/mke/interfaces/mcp_server.py`: preserve the exact path-only tool schema while calling the amended contract.
- `src/mke/domain/library_export.py`: versioned v1/v2 snapshot and manifest types without weakening v1.
- `src/mke/application/library_export.py`: version-selected deterministic renderers.
- `src/mke/adapters/filesystem/library_export.py`: version-selected atomic output and post-commit verification.
- `src/mke/interfaces/library_export.py`: closed v1/v2 response envelopes.
- `scripts/compiled_library_export_proof.py`: version-aware same-wheel proof while retaining v1 assertions.
- `tests/domain/test_manifest.py`: audio manifest acceptance and mismatch rejection.
- `tests/adapters/test_sqlite_transcript_intake_report.py`: audio fingerprint/report activation and rollback.
- `tests/adapters/test_sqlite_library_export.py`: mixed-source v2 snapshot and v1 incompleteness tests.
- `tests/application/test_library_export.py`: v1 byte compatibility and v2 rendering tests.
- `tests/adapters/test_library_export_filesystem.py`: v2 atomicity, tamper, and cleanup tests.
- `tests/domain/test_library_export.py`: closed v1/v2 models and cross-field authority.
- `tests/interfaces/test_cli_library_export.py`: `--format-version v1|v2` parser and result tests.
- `tests/interfaces/test_mcp_contract.py`: audio route and unchanged schema/error fixture tests.
- `tests/interfaces/test_mcp_server.py`: exact path-only schema snapshot.
- `tests/runtime/test_runtime_composition.py`: sidecar rejection and faster-whisper audio composition.
- `tests/runtime/test_owner_runtime.py`: admission ordering and release behavior.
- `tests/adapters/test_process_controller.py`: process-group, resource-limit, cancellation, and video compatibility regressions.
- `tests/scripts/test_compiled_library_export_consumer.py`: legacy v1 consumer freeze only.
- `tests/scripts/test_compiled_library_export_proof.py`: v1 regression and explicit v2 aggregate.
- `src/mke/proof/__init__.py`: direct-audio proof export.
- `tests/interfaces/test_cli_proof.py`: proof CLI contract.
- `.github/workflows/ci.yml`: model-free audio fixture/contract coverage only when ordinary matrix coverage is insufficient.
- `README.md`, `README_CN.md`, `docs/README.md`: bounded capability and navigation.
- `docs/explanation/architecture.md`: audio branch inside the existing lifecycle.
- `docs/reference/cli.md`, `docs/reference/contracts.md`: exact commands and versioned contracts.
- `docs/reference/mcp-contract.md`: unchanged path-only schema and bounded audio result/error behavior.
- `docs/how-to/use-local-transcription.md`: shared model preparation and video/audio owner boundary.
- `docs/how-to/use-mke-mcp.md`: owner-configured direct-audio tool flow and request-time non-controls.
- `docs/how-to/export-compiled-library.md`: default v1 and explicit v2 behavior.
- `docs/how-to/verify-release.md`: future v0.1.4 proof and archive gates without claiming publication.
- `docs/tutorials/getting-started.md`: optional bounded direct-audio path after deterministic setup.
- `scripts/release_presentation_audit.py`, `tests/scripts/test_release_presentation_audit.py`: reject direct-audio overclaims.
- Relevant retrieval identity artifacts only if canonical validators prove source-identity drift; use the existing transaction and preserve normalized semantics.

## Execution Topology

The implementation is staged through three independently reviewed PRs. A later stage cannot use a
draft or unmerged predecessor as authority:

```text
PR A: Task 1 feasibility + dependency/fixture/supervisor receipt
  | accepted and merged
  v
PR B: Task 2 -> Task 3 -> Task 4 internal foundation
  | accepted and merged
  +-----------------------------+
                                | PR A and LLM Wiki compatibility may overlap
LLM Wiki compatibility --------+ accepted and merged
                                v
PR C: schema reconciliation -> Task 5 -> Task 6 -> Task 7 -> Task 8 -> Task 9 -> Task 10
  | accepted and merged
  v
separately authorized release-closeout PR
```

- PR A must not modify `src/mke`, dependencies, lockfiles, workflows, README, export schemas, export
  documentation, runtime, CLI/MCP, or product claims. It may overlap only with the independent LLM
  Wiki docs/evidence PR because their tracked file sets are disjoint.
- PR B may modify internal domain, adapter, storage, and model-free test surfaces. It must not add
  the canonical dispatcher, runtime composition that exposes audio, CLI/MCP routing, Export v2,
  public capability docs, real-provider proof, or release proof.
- PR C has one integration owner for application activation, runtime composition, CLI/MCP, Export
  v2, shared docs, proof, workflow, and conditional evaluation identities. Shared contracts and
  terminal verification remain serialized.
- Each Task ends with task-scoped review, focused verification, and an intentional local commit.
  Each PR ends with the stage-specific verification below; no task reruns a release-grade terminal
  proof merely because a smaller tracked change landed.

## Verification Layers

- **PR A:** fixture identity and redistribution authority, linked-or-bundled component
  inventory/direct evidence, external-binary non-redistribution literals, target-executable probe,
  Darwin arm64 controlled-allocator supervisory proof, receipt validation, focused tests, necessary
  static checks, and normal CI. No real model proof.
- **PR B:** focused TDD, adjacent video compatibility, full Pytest, Ruff, Pyright, build, and one
  terminal mechanical evaluation-identity closure only when that PR's actual source identity
  triggers it. No release-grade candidate receipt or real model proof.
- **PR C:** fresh installed wheel, real cache-only ASR, Python/CLI/MCP/Search/Ask/EvidenceRef,
  reconciled Export v2 consumer, network denial, all canonical validators, whole-branch review, and
  terminal proof on the reviewed HEAD.
- Do not repeat the PR A license receipt or full retrieval gates after every task. Preserve final
  authenticity while avoiding circular proof refreshes. If the same finding remains open after two
  or three evidence-backed repairs, first reassess whether it is still a blocker or should become a
  documented limitation or follow-up.

---

### Task 1 (PR A): Prove Direct-Audio Feasibility, Fixtures, And License Authority

**Files:**
- Create: `tests/fixtures/audio/README.md`
- Create: `tests/fixtures/audio/direct-audio.mp3`
- Create: `tests/fixtures/audio/direct-audio.wav`
- Create: `tests/fixtures/audio/direct-audio.m4a`
- Create: `tests/adapters/test_audio_fixtures.py`
- Create: `scripts/direct_audio_dependency_receipt.py`
- Create: `tests/scripts/test_direct_audio_dependency_receipt.py`
- Create: `benchmarks/audio/dependency-artifacts.json`
- Create: `docs/reference/direct-audio-dependency-and-license-evidence.md`

**Interfaces:**
- Consumes: the exact locked external dependency set, prepared offline wheel inputs, supported
  Python/platform cells, a canonical wheelhouse manifest, lock-derived external constraints, and
  redistribution-safe synthetic fixture source.
- Produces: three immutable fixture identities plus one canonical external dependency, binary
  inventory/direct-evidence, non-redistribution, fixture, executable-probe, and supported-platform
  supervisor receipt used as the hard PR B entry gate.

- [x] **Step 1: Write fixture-absence RED tests before generating media**

```python
@pytest.mark.parametrize(
    ("name", "expected_media_type"),
    [
        ("direct-audio.mp3", "audio/mpeg"),
        ("direct-audio.wav", "audio/wav"),
        ("direct-audio.m4a", "audio/mp4"),
    ],
)
def test_direct_audio_fixture_inventory(name: str, expected_media_type: str) -> None:
    path = AUDIO_FIXTURE_ROOT / name
    assert path.is_file()
    assert not path.is_symlink()
    receipt = FIXTURE_RECEIPTS[name]
    assert receipt.media_type == expected_media_type
    assert path.stat().st_size == receipt.bytes
    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt.sha256
```

PR A does not amend legacy product, MCP, or export contract tests; those remain read-only baseline
authority for later stages.

- [x] **Step 2: Run RED tests**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_audio_fixtures.py \
  tests/scripts/test_direct_audio_dependency_receipt.py
```

Expected: fixture and dependency-receipt cases fail because the files, controller, and canonical
receipt do not exist.

- [x] **Step 3: Generate the three fixtures outside the repository**

Use one repository-authored sentence, a redistribution-safe synthetic speech source with an
explicit redistribution basis, and a pinned local `ffmpeg` binary only as a fixture-generation tool.
The accepted media commands must be recorded verbatim in the fixture README. A representative
closed profile is:

```bash
ffmpeg -nostdin -y -i source.wav -map 0:a:0 -vn -sn -dn \
  -c:a libmp3lame -ar 16000 -ac 1 -b:a 48k direct-audio.mp3
ffmpeg -nostdin -y -i source.wav -map 0:a:0 -vn -sn -dn \
  -c:a pcm_s16le -ar 16000 -ac 1 direct-audio.wav
ffmpeg -nostdin -y -i source.wav -map 0:a:0 -vn -sn -dn \
  -c:a aac -profile:a aac_low -ar 16000 -ac 1 -b:a 48k direct-audio.m4a
```

Before using the generation command, verify the already installed synthesizer and `ffmpeg` binary,
version, source, and license. If either tool or a redistribution-safe speech source is absent, stop
and request separate installation/acquisition authorization. Do not install a tool, download a
voice, or add a runtime dependency inside this Task.

The README must contain the source text or signal recipe, synthesizer/source license, output
redistribution basis, exact command, tool version, byte size, SHA-256, duration, stream count,
channel count, sample rate, container, codec, and AAC profile. Do not commit the intermediate source.

- [x] **Step 4: Make fixture and compatibility tests GREEN**

Inspect the committed bytes with PyAV inside the test body. Skip only when the transcription extra
is absent and `MKE_REQUIRE_TRANSCRIPTION_EXTRA` is not `1`; fail when that variable is `1` and PyAV
is unavailable. Assert exact normalized profile observations and the absence of sidecars, metadata
paths, personal voice sources, video, subtitle, data, and attachment streams.

Run:

```bash
UV_OFFLINE=1 MKE_REQUIRE_TRANSCRIPTION_EXTRA=1 uv run pytest -q \
  tests/adapters/test_audio_fixtures.py
```

Expected: PASS with exactly three fixture identities.

> **Pre-acquisition checkpoint (2026-07-18):** Commit
> `a19743992f73d8c03e543344227abadd4c3cb6fb` retains the fixture RED/GREEN work,
> the redistribution-safe generation record, and the three immutable fixture identities. A fresh
> required-extra fixture run passed `8` tests. The acquisition-independent Step 5 controller and
> validator remain partial; targeted authority repair commit
> `f49fbb231bb24b7ec180a54ef9f3dc9246402b68` established the closed controller schema. Follow-up
> commit `55d3c3a3365ea36bf0be39ed5e6c9d50d70346ac` bound the complete call-owned venv target tree;
> final authority repair commit `7425334e2320df3a112f03bf765decca3bab3e35` froze canonical
> inventory ordering and the receipt schema identity, added whole-input preflight revalidation,
> introduced Darwin inode-bound cleanup, and rejected venv hardlink aliases before pip. Follow-up
> cleanup authority repair commit `2802d6687d6e583bc9f5b023a6770da1f43ca5b5` closes the remaining
> pre-open replacement window by opening the captured Darwin inode through `/.vol`, cleaning the
> original `venv` and staging tree, preserving a same-name replacement, and returning terminal
> `pip_cleanup_failed` after observed path drift. The resulting receipt-controller suite passed all
> `208` tests, and its combined fixture run passed all `216` tests. No package acquisition,
> call-owned package environment, or canonical dependency receipt was generated. Step 5 remains
> unchecked, and Steps 6-7 remain pending their explicit gates.

> **Authorized acquisition closure (2026-07-19):** Commit
> `6547b05704c798cc1ea6b929f27bd4c0b8513cf1` established the first real controller path,
> dependency receipt, and durable evidence reference. The retained wheelhouse contains 35 exact
> lock-derived wheels (81,319,275 bytes); both CPython cells passed offline ordinary-pip install,
> `pip check`, required imports, and all three fixture decodes. Its initial receipt identity and
> verification record are historical because a subsequent actual-diff review requested bounded
> controller, decode, cleanup, immutable-license-source, and committed-validator repair.

> **Targeted actual-diff repair acceptance (2026-07-19):** The fixed descriptor bootstrap now binds
> the exact bytes compiled and executed by the controller; fixture decode uses the bytes bound to
> each fixture digest; terminal process-group cleanup failure overrides the triggering error;
> FFmpeg evidence binds immutable `n8.1.1` source and official license bytes; and
> `--validate-receipt` independently checks the canonical committed artifact without claiming a
> retained-runtime replay. Offline regeneration passed for both cells. The current canonical
> payload SHA-256 is `af6664c35b50a84ec9ba8d7cf08fd6c2c60ff8cbb1f4682253d6c1b6db2329ec`;
> the committed file SHA-256 is
> `9ec24aa34ce5ad9f1f8160d26694180a76a8b2c31d3b53322105941551b33fe6`.
> Final candidate verification passed 239 focused receipt/fixture tests with the transcription
> extra required, 115 adjacent model-free transcription/package tests, and 2,594 full-suite tests
> with 4 skips. Full Ruff, Pyright with the existing interpreter bound explicitly, offline build,
> product proof (8/8), demo verification, canonical static readback, retained-input identity, and
> no-residue checks passed; a bounded findings-only near-field review returned no findings.
> Independent targeted authority re-review of commit
> `3638619efd07916055caa2e80d9592a525a0248e` returned `CLEAN`: all five critical findings and both
> informational findings are closed, the independent targeted slice passed 17 tests with 214
> deselected, `git diff --check` passed, the branch remained within its exact 13-path scope, and the
> reviewed worktree was clean. Task 1 is accepted, PR A implementation is complete, and the result
> is **CLEARED FOR PR A PR HANDOFF**. This clears only PR A's local acceptance gate; it does not
> authorize PR B, PR C, release, or external publication.

- [x] **Step 5: Implement the external dependency/license receipt and validator**

The controller accepts explicit Python 3.12 and 3.13 interpreters, a prepared-offline wheelhouse
directory, lock-derived external constraints, the fixture root, and an output path. It
does not build, accept, identify, or install an MKE wheel. Each supported cell uses ordinary pip
semantics under those exact constraints and wheel inputs, runs `pip check`, imports the installed
external modules in isolation, decodes all three fixtures through installed PyAV, inventories the
actual linked or bundled FFmpeg components with available platform binary tooling, and proves the
Darwin arm64 supervisory mechanism before native parsing is considered supported.

The controller derives the canonical wheelhouse manifest itself and identifies every wheel by its
full canonical filename, parsed distribution/version/build and compatibility tags, byte count, and
SHA-256. Do not globally deduplicate by normalized distribution/version: wheels for the same locked
version may coexist when their interpreter/platform tags are disjoint, and one universal wheel may
serve multiple cells while appearing only once in the inventory.

For each supported Python/platform cell, project the lock-derived required distributions/versions
and require each one to resolve to exactly one compatible manifest entry. Missing,
ambiguous/overlapping compatible candidates, wrong version or tag, unsupported or surplus input,
duplicate canonical filename, invalid wheel filename, symlink, subdirectory, non-regular or
unrelated file, and identity drift all fail closed. Freeze deterministic sorted derivation and
per-cell resolution in tests so PR C can recompute the same manifest from a different absolute
root. Tests include legal cp312/cp313 wheels for one distribution/version, a universal wheel reused
by both cells, ambiguous compatible pairs, missing wheel, wrong tag/version, surplus input,
duplicate filename, and before/after identity drift.

The controller's ordinary-pip subprocess is the offline installation authority; an outer
`UV_OFFLINE=1` is not. Freeze the real argv and environment path in tests. The exact install argv
includes `--isolated`, `--disable-pip-version-check`, `--no-input`, `--no-index`, one
descriptor-validated local `--find-links`, `--only-binary=:all:`, `--require-hashes`, the canonical
lock-derived root requirements, and the accepted constraints. Run it only inside a call-owned
environment/home/cache/temp root with a platform null pip-config authority and an explicit
environment allowlist. Remove index URL, extra-index, proxy, credential, user-site, interactive,
and inherited pip configuration inputs. Missing wheels or resolution drift fail with a stable
closed result; pip cannot reach an index, use a user/global config, consume an undeclared cache, or
fall back to a source build. Controller tests must intercept the actual subprocess argv/environment
and prove index/config/build isolation rather than treating `UV_OFFLINE` as nested-pip authority.

Freeze the subprocess shape before implementation:

```python
pip_argv = [
    cell_python,
    "-I",
    "-m",
    "pip",
    "--isolated",
    "--disable-pip-version-check",
    "--no-input",
    "install",
    "--no-index",
    "--find-links",
    validated_wheelhouse_uri,
    "--only-binary=:all:",
    "--no-cache-dir",
    "--require-hashes",
    "--constraint",
    validated_constraints_path,
    "--requirement",
    validated_root_requirements_path,
]
```

The subprocess environment is built from an empty mapping. Add only the supported-cell minimum
needed to execute the approved interpreter plus call-owned `HOME` and `TMPDIR`; bind
`PIP_CONFIG_FILE` to the platform null device. Do not copy `PIP_*`, `HTTP_PROXY`, `HTTPS_PROXY`,
`ALL_PROXY`, `NO_PROXY`, credential, user-site, or index variables from the controller. The
wheelhouse URI, constraints, and root-requirement files are descriptor-validated, canonical local
inputs whose bytes/digests are already bound before this argv is constructed.

The closed public-safe receipt records only external distribution filenames/versions/digests,
Python/platform labels, PyAV wheel/runtime identity, binary components and direct license/notice
evidence, the external `local_runtime_only` classification, fixture profiles and their
`repository_distributed` classification, target-executable probe identities, and Darwin arm64
supervisory proof.
It rejects paths, hostnames, timestamps, environment dumps, tokens, unknown fields, incomplete
inventory, or inferred redistribution permission. It also requires the exact literals
`external_binary_redistribution=not_performed` and
`redistribution_authority=not_claimed`. Unknown transitive redistribution clearance is recorded but
does not fail PR A while those literals remain true; fixture redistribution ambiguity or missing
fixture authority remains `license_evidence_incomplete` and fails the gate. Any future bundling or
release redistribution of external binaries requires separate legal review.

Freeze this acquisition-independent authority matrix in RED tests before collecting real evidence:

| Authority | Required evidence | Classification |
|---|---|---|
| external constraints | canonical bytes, SHA-256, source `uv.lock` external-distribution projection, supported marker cells | missing distribution/hash or marker drift is `failed` |
| wheelhouse manifest | one sorted full-filename/parsed-tags/bytes/SHA-256 inventory; disjoint tagged wheels may share distribution/version and a universal wheel is recorded once | invalid/duplicate filename, symlink/nested/non-regular/unrelated input, identity drift, or surplus input is `failed` |
| external wheel per cell | exactly one compatible wheel for every lock-derived distribution/version in each supported Python/platform cell | missing, ambiguous/overlapping, wrong-version, or wrong-tag resolution is `failed` |
| nested pip | exact isolated `--no-index`/validated-local-`--find-links`/binary-only/hashed argv plus sanitized config-free environment | index/proxy/config/cache inheritance, source build, network attempt, or resolution drift is `failed` |
| PyAV runtime | installed distribution identity plus extension and linked/bundled component inventory from the platform tool recorded in the receipt | `unknown` or unobservable runtime identity/inventory is `failed` |
| component direct evidence | observed component identity, available license identifier/source/text digest, and available notice owner/source/digest | unresolved transitive redistribution clearance is recorded, not inferred or promoted to a local-use failure |
| external binary redistribution | classification `local_runtime_only`; exact closed literals `external_binary_redistribution=not_performed` and `redistribution_authority=not_claimed` | any distribution/claim or omitted literal is `failed` and requires separate legal review |
| target executable | descriptor-bound regular executable identity before/after one fixed bounded stdlib probe under a sanitized environment | missing/substituted/drifting identity, malformed/oversized/timed-out probe, or pip/uv/install/cache access is `failed` |
| Darwin arm64 supervisor | controlled allocator in one supervisory leader and dedicated process group; stable leader identity; leader-only non-aggregate `ri_phys_footprint` polling; ordinary-cooperative-descendant scope only through process-group identity/signaling/wait/cleanup; transient overshoot observation; `SIGTERM` -> fixed grace -> `SIGKILL` -> wait/reap; `hard_kernel_enforced=false` | unavailable/bypassed leader sampling, child/leader identity drift, or process-group signaling, wait, or cleanup failure is `failed`; no sandbox or hostile-media claim is permitted |
| fixture | classification `repository_distributed`; source/recipe, redistribution basis, profile, bytes, SHA-256 | missing permission or identity is `license_evidence_incomplete` |

Each supported platform cell freezes the exact inventory command/tool identity and its allowed
evidence sources. Unsupported tooling is a failed cell, not a reason to omit the component.

- [x] **Step 6: Stop for acquisition authority, then generate the PR A receipt**

Before any real package or fixture-generation input is acquired, report the exact missing inputs,
source, expected disk impact, and cleanup ownership and obtain separate authorization. Input
preflight uses an already existing and explicitly approved CPython controller executable. Resolve
the controller and each declared target Python to regular executables and descriptor-bind device,
inode, mode, byte count, `mtime_ns`, `ctime_ns`, and SHA-256 before use.

For every target Python, run one fixed bounded stdlib-only identity probe under the sanitized empty
environment. The probe accepts no caller code/import path and reports only
`sys.implementation.name`, exact version, platform identity, and executable digest. Reopen and
descriptor-revalidate the target identity and digest after the probe. Missing/substituted identity,
nonzero exit, timeout, oversized/malformed output, or before/after drift fails closed. The probe and
input preflight must not invoke pip, `uv`, install or synchronize an environment, read/write a
package cache, create bytecode, or execute caller-supplied code. Public-safe JSON records identities,
not local executable paths.

Freeze the target subprocess as `(target_python, "-I", "-B", "-c", FIXED_IDENTITY_PROBE)` with
`shell=False`, a constant audited probe body/digest, bounded stdout/stderr/time, and an environment
built from an empty mapping with only a separately proved platform minimum. Tests intercept the
actual argv/environment, reject any caller-controlled probe text or import path, and prove the
before/after descriptor identity transaction around the real bounded subprocess. Invoke the
controller itself through the reviewed `_CONTROLLER_BOOTSTRAP_SOURCE`; direct script execution is
rejected because it cannot bind the exact bytes that were compiled and executed. In the commands
below, `FIXED_DESCRIPTOR_BOOTSTRAP_SOURCE` is that reviewed literal.

```bash
/usr/bin/env -i PATH=/usr/bin:/bin \
  "$RECEIPT_CONTROLLER_PYTHON" -I -B -c "$FIXED_DESCRIPTOR_BOOTSTRAP_SOURCE" -- \
  scripts/direct_audio_dependency_receipt.py \
  --check-inputs \
  --lock uv.lock \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --wheelhouse "$TRANSCRIPTION_WHEELHOUSE" \
  --constraints "$TRANSCRIPTION_CONSTRAINTS" \
  --fixture-root tests/fixtures/audio \
  --json
```

This read-only preflight reports a closed sorted list of missing, extra, substituted, or invalid
inputs. Its preflight import path is stdlib-only and descriptor-binds declared interpreters,
constraints, wheelhouse entries, fixture paths, and the controller script. Target execution is
limited to the fixed identity probe above. It performs no install,
fixture generation, output or temporary write, bytecode creation, environment/venv synchronization,
or cache access/mutation. It must not invoke `uv run`, pip, or any network-capable resolver. Tests
snapshot the worktree plus declared environment/cache roots before and after the real preflight path and
require byte identity, no `.venv`, lock/cache mutation, or temporary residue. Use this output to
prepare the separate acquisition dispatch without trial and error.

Only after that independent acquisition authorization may the receipt controller create call-owned
environments and invoke the frozen nested-pip boundary from Step 5:

```bash
/usr/bin/env -i PATH=/usr/bin:/bin \
  "$RECEIPT_CONTROLLER_PYTHON" -I -B -c "$FIXED_DESCRIPTOR_BOOTSTRAP_SOURCE" -- \
  scripts/direct_audio_dependency_receipt.py \
  --lock uv.lock \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --wheelhouse "$TRANSCRIPTION_WHEELHOUSE" \
  --constraints "$TRANSCRIPTION_CONSTRAINTS" \
  --fixture-root tests/fixtures/audio \
  --output benchmarks/audio/dependency-artifacts.json \
  --json

/usr/bin/env -i PATH=/usr/bin:/bin \
  "$RECEIPT_CONTROLLER_PYTHON" -I -B -c "$FIXED_DESCRIPTOR_BOOTSTRAP_SOURCE" -- \
  scripts/direct_audio_dependency_receipt.py \
  --validate-receipt benchmarks/audio/dependency-artifacts.json \
  --json
```

Require `status=passed`, two exact interpreter/platform cells, canonical constraints and wheelhouse
manifest digests, exactly one compatible wheel per required distribution/version/cell,
`pip_check=passed`, the frozen nested-pip argv/environment evidence, three fixture decodes per cell,
passed target-executable probes, proved Darwin arm64 supervisor evidence, complete linked/bundled
component inventory/direct evidence, complete fixture redistribution authority, and exact
non-redistribution/non-claim literals.
The receipt digest must be independently reproducible from canonical bytes. It is refreshed only
when the external dependency set or constraints, prepared wheelhouse, PyAV wheel, validation
platform, supervisory authority, target-probe contract, non-redistribution boundary, or fixture
authority changes.

- [x] **Step 7: Write the durable evidence reference and close PR A**

`docs/reference/direct-audio-dependency-and-license-evidence.md` records the receipt schema,
validated external boundary, component inventory/direct evidence, fixture redistribution
basis, canonical external constraints and wheelhouse-manifest digests, proof platforms,
Darwin arm64 supervisory authority, target-executable probe, the external-binary
non-redistribution/non-claim literals, and explicit non-claim that package metadata proves binary
redistribution authority. It states that future bundling/release redistribution requires separate
legal review. It contains no product capability claim, local path, or MKE wheel identity.

```bash
git diff --check
UV_OFFLINE=1 MKE_REQUIRE_TRANSCRIPTION_EXTRA=1 uv run pytest -q \
  tests/adapters/test_audio_fixtures.py \
  tests/scripts/test_direct_audio_dependency_receipt.py
UV_OFFLINE=1 uv run ruff check scripts/direct_audio_dependency_receipt.py \
  tests/adapters/test_audio_fixtures.py tests/scripts/test_direct_audio_dependency_receipt.py
git add tests/fixtures/audio tests/adapters/test_audio_fixtures.py \
  scripts/direct_audio_dependency_receipt.py \
  tests/scripts/test_direct_audio_dependency_receipt.py \
  benchmarks/audio/dependency-artifacts.json \
  docs/reference/direct-audio-dependency-and-license-evidence.md
git commit -m "proof(audio): establish feasibility and license evidence"
```

PR A review must verify exact scope and reject any `src/mke`, dependency, lockfile, workflow,
README/export surface, public runtime, CLI/MCP, Export schema, product claim, personal recording,
missing fixture redistribution basis, profile ambiguity, missing local-use inventory/direct
evidence, omitted non-redistribution literals, target-probe failure, or supervisor failure.
PR B cannot begin until this PR is accepted and merged.

---

### Task 2 (PR B): Add Project-Owned Audio Domain And Wire Contracts

**Files:**
- Create: `src/mke/adapters/audio/__init__.py`
- Create: `src/mke/adapters/audio/contracts.py`
- Create: `src/mke/adapters/audio/schema.py`
- Create: `tests/domain/test_audio_contracts.py`
- Modify: `src/mke/domain/__init__.py`
- Modify: `tests/domain/test_manifest.py`
- Modify: `tests/domain/test_transcript_contracts.py`

**Interfaces:**
- Consumes: existing timestamp normalization semantics, `TranscriptionProvenance`, RunManifest validation, and fixed audio-v1 limits.
- Produces: `AudioTranscriptSegment`, `AudioMediaInfo`, `ParsedAudioTranscript`, `AudioTranscriptExtractionResult`, `REQUIRED_AUDIO_STAGES`, `audio_extractor_fingerprint()`, `parse_audio_transcript_payload()`.

- [x] **Step 1: Write failing closed-contract tests**

Cover exact schema keys, unknown/missing fields, bool-as-int rejection, Unicode normalization,
segment ordering, finite/in-range timestamps, segment count, media limits, container/codec/profile,
fingerprint grammar, required-stage mismatch, and video compatibility.

```python
def test_audio_manifest_requires_audio_stages_and_fingerprint() -> None:
    manifest = RunManifest(
        run_id="run_audio",
        asset_sha256="a" * 64,
        evidence_count=1,
        extractor_fingerprint="faster-whisper-audio-v1:" + ("b" * 64),
        required_stages=tuple(sorted(REQUIRED_AUDIO_STAGES)),
    )
    validate_run_manifest(manifest, evidence_count=1, locator_kinds={"timestamp_ms"})


@pytest.mark.parametrize(
    "fingerprint",
    [
        "faster-whisper-audio-v1:abc",
        "faster-whisper-audio-v1:" + ("A" * 64),
        "faster-whisper-v1:" + ("a" * 64),
    ],
)
def test_audio_manifest_rejects_wrong_fingerprint(fingerprint: str) -> None:
    with pytest.raises(ManifestValidationError):
        validate_audio_manifest(_audio_manifest(fingerprint))
```

- [x] **Step 2: Run RED tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_audio_contracts.py \
  tests/domain/test_manifest.py \
  tests/domain/test_transcript_contracts.py
```

Expected: collection or import failures for the new audio symbols; existing video tests remain green.

- [x] **Step 3: Add immutable audio values and closed parser**

Use these exact public shapes:

```python
@dataclass(frozen=True)
class AudioTranscriptSegment:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class AudioMediaInfo:
    container: Literal["mp3", "wav", "m4a"]
    audio_codec: Literal["mp3", "pcm_s16le", "aac"]
    channels: int
    sample_rate_hz: int
    duration_ms: int


@dataclass(frozen=True)
class ParsedAudioTranscript:
    media: AudioMediaInfo
    segments: tuple[AudioTranscriptSegment, ...]
    transcription_provenance: TranscriptionProvenance | None = None


@dataclass(frozen=True)
class AudioTranscriptExtractionResult:
    parsed_transcript: ParsedAudioTranscript
    extractor_fingerprint: str
    transcript_intake_report: TranscriptIntakeReport | None = None


REQUIRED_AUDIO_STAGES = frozenset({"audio_transcription", "candidate_evidence"})
_AUDIO_FINGERPRINT_RE = re.compile(r"faster-whisper-audio-v1:[0-9a-f]{64}\Z")
```

`parse_audio_transcript_payload(payload: object) -> ParsedAudioTranscript` accepts only
`format == "mke.audio_transcript.v1"`, the exact top-level fields frozen in the approved
spec, and closed nested media/segment/provenance fields. Reuse normalization helpers only when their
semantics are identical; do not return video DTOs.

- [x] **Step 4: Add canonical extractor identity**

```python
def audio_extractor_fingerprint(provenance: TranscriptionProvenance) -> str:
    identity = {
        "compute_type": provenance.compute_type,
        "device": provenance.device,
        "language": provenance.language,
        "library_version": provenance.library_version,
        "model": provenance.model,
        "model_revision": provenance.model_revision,
        "provider": provenance.provider,
    }
    canonical = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "faster-whisper-audio-v1:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

Manifest validation accepts the exact audio grammar only with audio stages and timestamp locators.
It must still accept every existing PDF, OCR-evaluation, sidecar-video, and faster-whisper-video
manifest unchanged.

- [x] **Step 5: Run GREEN and adjacent tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_audio_contracts.py \
  tests/domain/test_manifest.py \
  tests/domain/test_transcript_contracts.py \
  tests/application/test_video_publication.py \
  tests/adapters/test_sqlite_transcript_intake_report.py
UV_OFFLINE=1 uv run ruff check src/mke/domain src/mke/adapters/audio tests/domain
UV_OFFLINE=1 uv run pyright
```

Expected: all pass; no existing manifest or video output changes.

- [x] **Step 6: Review and commit Task 2**

```bash
git diff --check
git add src/mke/domain/__init__.py src/mke/adapters/audio \
  tests/domain/test_audio_contracts.py tests/domain/test_manifest.py \
  tests/domain/test_transcript_contracts.py
git commit -m "feat(audio): define direct audio contracts"
```

---

### Task 3 (PR B): Bind Immutable Input, Inspection Protocol, And Asset Media Authority

**Files:**
- Create: `src/mke/adapters/audio/inspection.py`
- Create: `tests/adapters/test_audio_inspection.py`
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `tests/adapters/test_sqlite_migration.py`
- Modify: `tests/adapters/test_sqlite_transcript_intake_report.py`
- Modify: `tests/application/test_video_publication.py`

**Interfaces:**
- Consumes: Task 1 fixtures and Task 2 `AudioMediaInfo`.
- Produces: `AudioSourceSnapshot`, `snapshot_audio_source()`, `verify_source_path()`,
  `verify_owned_path()`, `require_matching_identity()`, a closed inspection request/result
  protocol, pure `_normalize_audio_profile()`, and digest/media-type conflict rejection used by
  Tasks 4-7. Task 3 does not run PyAV or expose an executable inspection provider; Task 4 owns all
  native parsing. PR B never parses untrusted media in the owner process.

- [x] **Step 1: Write descriptor and SQLite authority RED tests**

```python
def test_audio_snapshot_rejects_same_size_replacement(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(WAV_BYTES)
    snapshot = snapshot_audio_source(source, tmp_path / "owned")
    replacement = tmp_path / "replacement.wav"
    replacement.write_bytes(_same_size_mutation(WAV_BYTES))
    os.replace(replacement, source)
    with pytest.raises(AudioSnapshotError, match="source_identity_mismatch"):
        snapshot.verify_source_path()


def test_asset_digest_cannot_change_media_type(store: SQLiteStore) -> None:
    store.ensure_source("first.pdf", "a" * 64, media_type="application/pdf")
    with pytest.raises(AssetMediaTypeMismatchError, match="asset_media_type_mismatch"):
        store.ensure_source("same.mp3", "a" * 64, media_type="audio/mpeg")
```

Also cover symlink file, symlink parent, non-regular file, empty input, growth, truncation,
same-inode same-size writes during copy, descriptor/path inode replacement before and after
inspection, cleanup failure, output root overlap, and all invalid stream/profile/limit cases.

- [x] **Step 2: Run RED tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_audio_inspection.py \
  tests/adapters/test_sqlite_migration.py \
  tests/adapters/test_sqlite_transcript_intake_report.py
```

Expected: new snapshot/inspection imports fail and SQLite media-type conflict is not rejected.

- [x] **Step 3: Implement a call-owned immutable snapshot**

```python
@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    bytes: int
    modified_ns: int
    changed_ns: int
    sha256: str


@dataclass
class AudioSourceSnapshot:
    original_path: Path
    owned_root: Path
    owned_path: Path
    source_identity: FileIdentity
    owned_identity: FileIdentity
```

Provide concrete `verify_source_path(snapshot) -> None`, `verify_owned_path(snapshot) -> None`, and
`cleanup_audio_snapshot(snapshot) -> None` functions. Each function performs the identity checks
listed below and raises a typed stable snapshot error on the first mismatch; none silently repairs
or follows a replacement.

`snapshot_audio_source(source: Path, owned_root: Path) -> AudioSourceSnapshot` must:

1. reject a symlink or non-regular source with `lstat` before creating `owned_root`;
2. open with `O_RDONLY | O_CLOEXEC` and `O_NOFOLLOW` where available;
3. bind initial `lstat`, descriptor `fstat`, and post-open path identity;
4. stream-copy with a bounded buffer from the same descriptor into an exclusive call-owned file;
5. compute the copied snapshot SHA-256 during the bounded stream copy, rewind the still-open source
   descriptor, perform one bounded second full SHA-256 read, and require exact digest equality;
6. require initial/final descriptor size, mode, inode, device, `mtime_ns`, and `ctime_ns` equality so
   same-inode writes cannot hide behind an unchanged byte count;
7. fsync, chmod read-only, atomically rename staging to a random sealed name inside a 0700 private
   root, and revalidate both descriptor identities and the original path;
8. expose the sealed file to Task 4 only through a no-follow descriptor-bound request while the controller owns its
   lifecycle; and
9. remove only call-owned inodes using no-follow identity checks, returning a stable cleanup error
   without deleting a replacement.

- [x] **Step 4: Define pure profile normalization and a closed inspection protocol**

```python
class AudioInspectionRequest(TypedDict):
    path: str
    expected_suffix: Literal[".mp3", ".wav", ".m4a"]
    expected_sha256: str
    expected_bytes: int


class AudioInspectionResult(TypedDict):
    schema_version: Literal["mke.audio_inspection.v1"]
    media: AudioMediaInfoPayload
    observed_sha256: str
    observed_bytes: int
```

The normalizer is a pure function over bounded observations and is closed over the approved
token/profile table. Convert duration to integer milliseconds with an explicitly tested rounding
rule; reject unknown duration, non-finite values, extra streams, aliases outside the frozen
inventory, wrong AAC profile, unsupported channel/sample rate, and extension/profile mismatch.
Task 4 owns the package child that performs `av.open()` and revalidates the sealed snapshot before
and after parsing; the owner validates only the closed result.

- [x] **Step 5: Make digest/media-type reuse fail closed**

Add `AssetMediaTypeMismatchError(ValueError)` in the SQLite adapter. In `_ensure_asset`, select the
existing row by digest and compare exact SQLite storage class and
media type before returning its ID. Do not migrate or rewrite an existing Asset:

```python
row = self._connection.execute(
    "SELECT asset_id, media_type FROM assets WHERE sha256 = ?",
    (asset_sha256,),
).fetchone()
if row is not None:
    stored_media_type = self._require_sqlite_text(row["media_type"], "asset media type is invalid")
    if stored_media_type != media_type:
        raise AssetMediaTypeMismatchError("asset_media_type_mismatch")
    return self._require_sqlite_text(row["asset_id"], "asset id is invalid")
```

Add a migration/read regression proving old PDF/video Assets remain valid and no schema change is
required.

- [x] **Step 6: Run GREEN, race repetitions, and adjacent suites**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_audio_inspection.py \
  tests/adapters/test_sqlite_migration.py \
  tests/adapters/test_sqlite_transcript_intake_report.py \
  tests/application/test_video_publication.py
for run in 1 2 3 4 5; do
  UV_OFFLINE=1 uv run pytest -q tests/adapters/test_audio_inspection.py \
    -k 'replacement or same_inode or cleanup or identity'
done
UV_OFFLINE=1 uv run ruff check src/mke/adapters/audio src/mke/adapters/sqlite tests/adapters
UV_OFFLINE=1 uv run pyright
```

Expected: every run passes; no partial output, operator-owned deletion, or legacy Asset drift.

- [x] **Step 7: Review and commit Task 3**

```bash
git diff --check
git add src/mke/adapters/audio/inspection.py src/mke/adapters/sqlite/__init__.py \
  tests/adapters/test_audio_inspection.py tests/adapters/test_sqlite_migration.py \
  tests/adapters/test_sqlite_transcript_intake_report.py tests/application/test_video_publication.py
git commit -m "fix(audio): bind direct audio source identity"
```

The review must explicitly verify that PR B remains an uncomposed internal foundation with no
Source/Run creation path, and that cleanup owns only the copied inode. Task 5 / PR C must verify
snapshot creation before Source/Run creation when it composes the owner lifecycle.

---

### Task 4 (PR B): Add The Internal Cache-Only Audio Child And Provider

**Files:**
- Create: `src/mke/adapters/audio/inspection_cli.py`
- Create: `src/mke/adapters/audio/faster_whisper_cli.py`
- Create: `tests/adapters/test_audio_inspection_cli.py`
- Create: `tests/adapters/test_faster_whisper_audio_cli.py`
- Modify: `src/mke/adapters/audio/__init__.py`
- Modify: `src/mke/adapters/video/faster_whisper.py`
- Modify: `src/mke/adapters/video/providers.py`
- Modify: `src/mke/adapters/video/process.py`
- Modify: `tests/adapters/test_local_command_transcript_provider.py`
- Modify: `tests/adapters/test_process_controller.py`

**Interfaces:**
- Consumes: Task 2 audio schema/fingerprint, Task 3 `AudioSourceSnapshot` and inspected `AudioMediaInfo`, existing `FasterWhisperTranscriptionConfig` and `ActiveProcessController`.
- Produces: internal package-owned bounded inspection and transcription children, a lightweight
  non-model-constructing audio preflight, and uncomposed provider adapters. No owner/runtime
  composition exposes this behavior in PR B.

- [x] **Step 1: Write child/provider RED tests**

Cover both package children: exact argv, isolated interpreter flags, `shell=False`, owner config,
cache-only environment,
normalization, output cap, stderr cap, timeout, cancellation latch, process-group cleanup, model
generator failure, empty transcript, media/profile mismatch, schema rejection, unknown exit, and
video regression. The inspection child additionally covers corrupt/native-parser exit, parse
timeout, the accepted Darwin arm64 controlled allocator, stable supervisory-leader identity,
leader-only non-aggregate `ri_phys_footprint` polling, ordinary-descendant process-group identity
for cleanup, transient overshoot, `SIGTERM`/grace/`SIGKILL`/wait, leader-sampling and descendant
signaling/cleanup failure, signal/native crash, owner survival, before/after descriptor
identity and digest checks, and closed results. Freeze `hard_kernel_enforced=false` and reject any
sandbox or hostile-media claim. Prove that
lightweight audio preflight checks typed config, optional dependency presence, and exact prepared
model-tree completeness without importing or constructing `WhisperModel`.

```python
def test_audio_child_uses_closed_protocol_and_offline_environment(
    fake_model: FakeWhisperModel,
    audio_fixture: Path,
) -> None:
    result = run_audio_child(audio_fixture, fake_model=fake_model)
    payload = json.loads(result.stdout)
    assert payload["format"] == "mke.audio_transcript.v1"
    assert result.environment["HF_HUB_OFFLINE"] == "1"
    assert "PYTHONPATH" not in result.environment
    assert result.network_calls == []
```

The tests must prove the child validates the Task 3 inspected identity supplied by the parent and
does not independently accept a different path or download policy.

- [x] **Step 2: Run RED tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_audio_inspection_cli.py \
  tests/adapters/test_faster_whisper_audio_cli.py \
  tests/adapters/test_local_command_transcript_provider.py
```

Expected: missing internal inspection/transcription child and provider symbols; existing video cases pass.

- [x] **Step 3: Extract only identical private faster-whisper helpers**

Keep `FasterWhisperTranscriptionConfig`, exact revision, explicit prepare, doctor, model resolution,
runtime profile resolution, and cache-only loading as the single owner policy. Private helpers may
move only when video tests prove byte/semantic compatibility. The shared inference helper has a
media-neutral signature:

```python
@dataclass(frozen=True)
class NormalizedTranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
```

The shared private inference helper has the exact signature
`transcribe_cached_media(media: str | BinaryIO, *, config: FasterWhisperTranscriptionConfig, model_factory: WhisperModelFactory) -> tuple[tuple[NormalizedTranscriptSegment, ...], TranscriptionProvenance]`.
It constructs the model through the supplied factory, materializes the generator once, normalizes
every segment into the private value above, records the actual runtime profile, and returns no
media-specific public DTO. Video continues to supply its existing path string. The audio child
opens the sealed snapshot with no-follow, verifies descriptor identity and SHA-256, supplies a
binary stream from that descriptor, then revalidates descriptor/path identity and digest after
generator materialization. Audio and video adapters convert the private result into their own
project-owned public values.

Do not change the public `mke.video_transcript.v1` serializer, video fingerprint, MP4 probe, video
exit mapping, or video provider result type.

- [x] **Step 4: Implement the two closed audio children**

The inspection child accepts only the sealed snapshot path, expected identity/digest/bytes, suffix,
and fixed inspection limits. It opens no-follow, binds the descriptor, runs PyAV/FFmpeg parsing in
the bounded child process, revalidates descriptor/path identity and digest after parsing, and emits
one closed `mke.audio_inspection.v1` result. A crash, signal, timeout, oversized output, malformed
result, or identity drift fails before Source/Run creation and cannot terminate the owner process.

Before importing PyAV, each child enters the exact Darwin arm64 supervisory boundary proved in PR A.
The package-owned supervisor starts one leader in a dedicated process group, establishes the stable
leader identity, and polls only that leader's `ri_phys_footprint` against the configured budget.
This is a non-aggregate, leader-process scope: ordinary-descendant footprints are neither sampled
for the budget nor added to it. Polling may observe a transient overshoot and is not a kernel ceiling.
On budget exceedance, timeout, cancellation, output overflow, registration failure, or shutdown,
the supervisor sends `SIGTERM` to the dedicated process group, waits one fixed grace interval,
sends `SIGKILL` to survivors in that group, and waits/reaps the group. Child/leader identity drift,
unavailable or failed leader sampling, process-group signaling failure, or incomplete wait/cleanup
is a closed provider failure.
The runtime and receipt expose `hard_kernel_enforced=false`; ordinary descendants are in scope only
for process-group identity, signaling, wait/reap, and cleanup. This boundary is not a sandbox and
does not claim hostile-media, escaped/reparented-process, `setsid`/`setpgid` escape,
privileged-helper, or kernel compromise containment. Preserve existing video process behavior and
prove its cancellation/cleanup tests unchanged.

The transcription child accepts only trusted owner argv: immutable snapshot path,
expected SHA-256, expected bytes, inspected media fields, and existing transcription owner fields.
It writes one JSON object on stdout and no success text on stderr.

```python
AUDIO_EXIT_ERRORS: dict[int, tuple[str, str]] = {
    20: ("transcription optional dependency is not installed", "install_transcription_extra"),
    21: ("configured transcription model is not cached", "run_transcription_prepare"),
    22: ("transcription model resolution failed", "check_model_configuration"),
    30: ("audio profile is unsupported", "choose_supported_file"),
    31: ("audio file must contain one audio stream", "choose_supported_file"),
    32: ("audio input exceeds supported limits", "choose_smaller_file"),
    40: ("transcription failed", "check_server_logs"),
    41: ("audio transcript must contain at least one segment", "check_audio"),
    50: ("audio transcript schema validation failed", "check_server_logs"),
}
```

Unknown nonzero exits map to redacted `audio_ingest_failed`; raw stderr, argv, cache paths, model
paths, exception text, and tracebacks never enter public payloads.

- [x] **Step 5: Keep the package-owned provider internal**

The internal adapter commands use the current interpreter and modules, not PATH discovery:

```python
audio_command = (
    sys.executable,
    "-I",
    "-B",
    "-m",
    "mke.adapters.audio.faster_whisper_cli",
)
inspection_command = (
    sys.executable,
    "-I",
    "-B",
    "-m",
    "mke.adapters.audio.inspection_cli",
)
```

PR B does not edit `runtime.py` or install this adapter into an owner-visible composition root. It
proves that a future PR C composition can bind the existing `FasterWhisperTranscriptionConfig`,
operation controller, timeout, bounded capture, receipt-backed Darwin arm64 supervisor, and lightweight
preflight without changing video behavior. The module invocation above is the sole internal child
entry point; do not add a console script.
`pyproject.toml`, dependencies, and `uv.lock` remain unchanged.

- [x] **Step 6: Run GREEN and process cleanup repetitions**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_audio_inspection_cli.py \
  tests/adapters/test_faster_whisper_audio_cli.py \
  tests/adapters/test_local_command_transcript_provider.py \
  tests/adapters/test_faster_whisper_cli.py \
  tests/adapters/test_process_controller.py
for run in 1 2 3 4 5; do
  UV_OFFLINE=1 uv run pytest -q \
    tests/adapters/test_audio_inspection_cli.py \
    tests/adapters/test_faster_whisper_audio_cli.py \
    -k 'footprint or allocator or signal or timeout or cancellation or descendant or registration'
done
UV_OFFLINE=1 uv run ruff check src/mke/adapters/audio src/mke/adapters/video tests/adapters
UV_OFFLINE=1 uv run pyright
```

Expected: all pass with no descendant, reader thread, temp file, or operation registration leak.

- [x] **Step 7: Review and commit Task 4**

```bash
git diff --check
git add src/mke/adapters/audio src/mke/adapters/video/faster_whisper.py \
  src/mke/adapters/video/providers.py src/mke/adapters/video/process.py \
  tests/adapters/test_audio_inspection_cli.py \
  tests/adapters/test_faster_whisper_audio_cli.py \
  tests/adapters/test_local_command_transcript_provider.py \
  tests/adapters/test_process_controller.py
git commit -m "feat(audio): add internal cache-only audio provider"
```

Task review must prove the internal child/provider boundary and video compatibility. Public owner
composition remains intentionally absent and is verified in PR C.

### PR B Local Acceptance Closure

Tasks 2 through 4 are locally accepted at reviewed repair HEAD
`1fb1cd88a393207684d0cbf3072a116e4b1f6dfc` and are **CLEARED FOR PR B PR HANDOFF**. The final
targeted authority re-review closed the Linux-host portability issue in the cleanup regression by
gating the real Darwin `/.vol/<dev>/<ino>` contract on the host's actual `sys.platform` and keeping
an independent regression that explicitly selects the generic non-Darwin path. The accepted repair
changes tests only; production, contracts, evaluation identities, dependencies, workflows, and
public surfaces remain unchanged.

This closure records local acceptance only. PR B remains an uncomposed internal foundation: it does
not activate direct audio through runtime, CLI, or MCP; run real ASR or acquire a model; claim a
sandbox or hostile-media containment; claim external-binary redistribution authority; or authorize
release or deployment. It does not mark PR B merged, satisfy the PR C entry gate, start PR C, or
complete any Task 5 through Task 10 checkbox.

---

## PR C Entry Gate: Reconcile Export v2 Before Public Activation

Before Task 5, require accepted/merged PR A, accepted/merged PR B, and the accepted/merged LLM Wiki
compatibility docs/evidence PR. Read the exact compatibility plan/review and the live v1
manifest/Markdown/consumer implementation. Record in the PR C implementation review:

- which v1 fields and Markdown boundaries the real downstream workflow consumed;
- the exact v1 bytes and consumer behavior that remain frozen;
- the smallest additive v2 media/stage/field delta required for complete audio representation;
- the full version-selected authority path from CLI parser through interface, application, SQLite
  snapshot DTO, renderer/publisher, response, proof, and independent consumer; and
- the stable v1 mixed-Library failure plus actionable `--format-version v2` next step.

LLM Wiki remains an external downstream view, not an MKE dependency, runtime component, schema
owner, or Evidence authority. Only after this checkpoint may PR C freeze exact v2 tests. A
non-additive authority change, product-specific adapter, new dependency direction, or broader
consumer contract is a design hard stop.

---

### Task 5 (PR C): Activate Direct Audio Through The Existing Lifecycle And Canonical Dispatcher

**Files:**
- Create: `tests/application/test_audio_publication.py`
- Modify: `src/mke/application/__init__.py`
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `src/mke/runtime.py`
- Modify: `tests/adapters/test_sqlite_transcript_intake_report.py`
- Modify: `tests/application/test_pdf_publication.py`
- Modify: `tests/application/test_video_publication.py`
- Modify: `tests/application/test_video_provider_injection.py`
- Modify: `tests/runtime/test_runtime_composition.py`
- Modify: `tests/runtime/test_owner_runtime.py`

**Interfaces:**
- Consumes: accepted/merged PR B immutable snapshot/media authority and internal audio provider.
- Produces: `AudioIngestError`, `IngestDispatchError`, `KnowledgeEngine.ingest_audio()`, canonical `KnowledgeEngine.ingest_file()`, audio Run/Publication lifecycle, and active timestamp Evidence.

- [x] **Step 1: Write lifecycle and dispatcher RED tests**

Cover suffix dispatch, uppercase suffixes, unsupported suffix, sidecar-owner rejection before Source
and Run, exact snapshot hash, Run states, candidate/manifest/report atomicity, Search/Ask,
superseded race, failure/cancellation/cleanup rollback, prior Publication preservation, Source
revision, report insertion failure, admission busy/overloaded behavior and lease release after every
success/failure/cancellation path, zero model-factory calls when admission rejects, and PDF/video
behavior.

```python
@pytest.mark.parametrize(
    ("name", "method"),
    [
        ("document.pdf", "ingest_pdf"),
        ("clip.mp4", "ingest_video"),
        ("voice.mp3", "ingest_audio"),
        ("voice.wav", "ingest_audio"),
        ("voice.m4a", "ingest_audio"),
    ],
)
def test_ingest_file_uses_one_closed_suffix_dispatcher(
    engine: KnowledgeEngine,
    name: str,
    method: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Path]] = []
    monkeypatch.setattr(engine, method, lambda path: calls.append((method, path)) or INGEST_RESULT)
    assert engine.ingest_file(Path(name)) == INGEST_RESULT
    assert calls == [(method, Path(name))]
```

- [x] **Step 2: Run RED tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/application/test_audio_publication.py \
  tests/adapters/test_sqlite_transcript_intake_report.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py
```

Expected: missing audio ingest/dispatcher and audio activation behavior.

- [x] **Step 3: Add the canonical application surface**

First compose the accepted internal inspection/transcription providers at the owner boundary only for the existing
faster-whisper owner on Darwin arm64 when the owner explicitly supplies the paired
`direct_audio_footprint_bytes` and `direct_audio_footprint_budget_mode="baseline_plus"` startup
policy. The default sidecar owner and an unconfigured or unsupported-platform faster-whisper owner
continue to reject direct audio before Source or Run creation. Bind the current interpreter,
existing owner configuration, operation controller, timeout, bounded capture, the explicit owner
pair through the accepted PR A/PR B Darwin arm64 supervisory mechanism, lightweight
non-model-constructing audio
preflight, and existing `RuntimeConfig.admission_controller`; add no request-time controls or public
child command. Existing explicit `transcription doctor` and owner-startup diagnostics retain their
meaning, but a direct-audio request must not invoke the full model-constructing doctor before
admission.

```python
class AudioIngestError(ValueError):
    def __init__(
        self,
        cause: str,
        run_id: str | None = None,
        *,
        problem: str = "audio_ingest_failed",
        next_step: str = "fix_input_or_retry",
    ) -> None:
        super().__init__(cause)
        self.cause = cause
        self.problem = problem
        self.next_step = next_step
        self.run_id = run_id


class IngestDispatchError(ValueError):
    def __init__(self, cause: str, next_step: str = "choose_supported_file") -> None:
        super().__init__(cause)
        self.problem = "unsupported_media_type"
        self.cause = cause
        self.next_step = next_step


_INGEST_SUFFIXES = {
    ".pdf": "pdf",
    ".mp4": "video",
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
}


def ingest_file(self, path: Path) -> IngestResult:
    route = _INGEST_SUFFIXES.get(path.suffix.lower())
    if route == "pdf":
        return self.ingest_pdf(path)
    if route == "video":
        return self.ingest_video(path)
    if route == "audio":
        return self.ingest_audio(path)
    raise IngestDispatchError("supported suffixes are .pdf, .mp4, .mp3, .wav, and .m4a")
```

The dispatcher does not resolve the path and does not accept MIME hints from callers.

- [x] **Step 4: Implement fail-closed audio lifecycle**

`ingest_audio()` must order authority as follows:

```text
lstat/no-follow validation
  -> lightweight owner/provider preflight with no model construction
  -> acquire existing bounded admission lease
  -> immutable call-owned snapshot
  -> bounded inspection child over sealed bytes
  -> exact-byte SHA and audio-v1 result validation
  -> digest/media-type check and Source/Run creation
  -> cache-only child transcription of owned bytes
  -> strict audio payload + extractor identity validation
  -> revalidate sealed snapshot identity, byte count, and SHA-256
  -> ordered timestamp Evidence
  -> validate RunManifest + TranscriptIntakeReport in memory
  -> owned snapshot cleanup
  -> persist candidate + validated Run
  -> one atomic Publication/FTS/report/published transaction
  -> return success
```

The preflight may validate only typed owner configuration, optional dependency availability,
static profile grammar, and prepared cache-tree completeness. Acquire admission before snapshot
creation, child start, or any CTranslate2/`WhisperModel` construction. Full device/compute/model
initialization occurs only inside the admitted transcription child. Release the lease on every
return, exception, timeout, cancellation, and cleanup path. Capacity exhaustion is an
operation-local pre-Run `transcription_busy` failure with no `run_id`, zero model-factory calls, and
no snapshot; it does not alter PDF/video admission behavior or expose queue internals.

If cleanup cannot prove removal of the call-owned snapshot, return a stable failure and do not
publish. If a failure occurs after Run creation, mark only that Run failed or superseded and keep
the prior active Publication. Do not fabricate a transcript report for failed or unavailable runs.

- [x] **Step 5: Extend atomic report activation for audio fingerprints**

SQLite recognizes either historical `faster-whisper-v1:[0-9a-f]{64}` with video stages or new
`faster-whisper-audio-v1:[0-9a-f]{64}` with audio stages as report-requiring. Validate report media
duration/segment counts/provenance against the audio manifest and candidate Evidence in the same
transaction. No new table or migration is required unless a real schema mismatch is proven.

- [x] **Step 6: Run GREEN, lifecycle races, and regressions**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/application/test_audio_publication.py \
  tests/adapters/test_sqlite_transcript_intake_report.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py \
  tests/application/test_video_provider_injection.py \
  tests/runtime/test_runtime_composition.py tests/runtime/test_owner_runtime.py
for run in 1 2 3 4 5; do
  UV_OFFLINE=1 uv run pytest -q tests/application/test_audio_publication.py \
    -k 'superseded or cancellation or cleanup or rollback or concurrent'
done
UV_OFFLINE=1 uv run ruff check src/mke/application src/mke/adapters/sqlite tests/application tests/adapters
UV_OFFLINE=1 uv run pyright
```

Expected: all pass; active Publication changes only on complete success.

- [x] **Step 7: Review and commit Task 5**

```bash
git diff --check
git add src/mke/application/__init__.py src/mke/adapters/sqlite/__init__.py src/mke/runtime.py \
  tests/application/test_audio_publication.py \
  tests/adapters/test_sqlite_transcript_intake_report.py \
  tests/application/test_pdf_publication.py tests/application/test_video_publication.py \
  tests/application/test_video_provider_injection.py tests/runtime/test_runtime_composition.py \
  tests/runtime/test_owner_runtime.py
git commit -m "feat(audio): publish direct audio evidence"
```

---

### Task 6 (PR C): Route CLI And stdio MCP Through The Canonical Dispatcher

**Files:**
- Create: `tests/interfaces/test_cli_audio.py`
- Modify: `src/mke/cli.py`
- Modify: `src/mke/interfaces/mcp_contract.py`
- Modify: `src/mke/interfaces/mcp_server.py`
- Modify: `tests/interfaces/test_cli_error_contract.py`
- Modify: `tests/interfaces/test_cli_transcription.py`
- Modify: `tests/interfaces/test_mcp_contract.py`
- Modify: `tests/interfaces/test_mcp_server.py`
- Modify: `tests/interfaces/test_mcp_transcription_runtime.py`

**Interfaces:**
- Consumes: Task 5 `KnowledgeEngine.ingest_file()` and `AudioIngestError`.
- Produces: CLI and MCP direct-audio flows with stable operation-local public errors and unchanged request schemas.

- [x] **Step 1: Write parser/schema/error RED tests**

```python
def test_mcp_ingest_file_schema_remains_path_only(server: FastMCP) -> None:
    schema = _tool_schema(server, "ingest_file")
    assert set(schema["properties"]) == {"path"}
    assert schema["required"] == ["path"]


@pytest.mark.parametrize("suffix", [".mp3", ".wav", ".m4a", ".MP3", ".WAV", ".M4A"])
def test_cli_ingest_routes_audio_to_application_dispatcher(suffix: str, cli: CliHarness) -> None:
    result, calls = cli.run_with_engine_spy("ingest", "fixture" + suffix, "--json")
    assert result.exit_code == 0
    assert set(result.json) == {"ok", "run_id", "run_state", "evidence_count", "transcript_intake_report"}
    assert calls == [("ingest_file", Path("fixture" + suffix))]
```

Do not add `media_type` or another unversioned success field to the existing CLI envelope merely to
test routing. Assert dispatch through the application spy/provider plus the existing success keys
and transcript report.

Add negatives for a symlink file, symlink parent escape, nonexistent path, directory, unsupported
suffix, parent-symlink retarget after containment, sidecar owner, dependency/cache/config readiness, admission overload, pre-Run profile
rejection, source identity drift, inspection crash/timeout, snapshot cleanup failure, audio child
exits 20-50, unknown exit, unexpected exception, cancellation, and all forbidden request-time
controls. Run the retarget regression through audio, PDF, and video dispatch so the canonical
dispatcher cannot weaken existing containment. Assert every pre-Run row omits `run_id`.

- [x] **Step 2: Run RED tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/interfaces/test_cli_audio.py \
  tests/interfaces/test_cli_error_contract.py \
  tests/interfaces/test_cli_transcription.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_server.py \
  tests/interfaces/test_mcp_transcription_runtime.py
```

Expected: audio routes unsupported or bypass the canonical dispatcher; legacy schema assertions pass.

- [x] **Step 3: Validate MCP path identity before resolution**

`mcp_contract.ingest_file()` must preserve the exact path-only schema but reject a symlinked final
component before calling `resolve(strict=True)`. Keep the unresolved spelling only for this
`lstat` check and public presentation. Resolve the allowed root and candidate, prove containment,
bind the resolved target identity, and pass the containment-validated resolved `Path` (or an
equivalent descriptor-backed authority) into the canonical application dispatcher. Never reopen
the unresolved parent path after containment. Task 3 then binds that resolved target again while
opening the snapshot descriptor. A parent-symlink retarget between containment and application
open must fail without reading outside the allowed root.

```python
candidate = Path(path)
stat_result = candidate.lstat()
if stat.S_ISLNK(stat_result.st_mode):
    return _ingest_failure("input_path_rejected", "input path must not be a symlink", "choose_file_under_allowed_root")
resolved = candidate.resolve(strict=True)
resolved_stat = resolved.stat()
if not stat.S_ISREG(resolved_stat.st_mode):
    return _ingest_failure("input_path_rejected", "input path must be a regular file", "choose_file_under_allowed_root")
# After the resolved allowed-root containment check, dispatch `resolved` plus its bound identity.
```

- [x] **Step 4: Use command-local error mappings**

CLI and MCP route success through `engine.ingest_file(candidate)`. Direct-audio failures serialize
only these problems: `input_path_rejected`, `unsupported_media_type`, `transcription_not_ready`,
`transcription_busy`, and `audio_ingest_failed`, with the closed pre-Run/post-Run safe causes,
next steps, and `run_id` presence frozen in the design. Unknown errors use the existing redacted
generic cause. Do not add the audio causes to shared
`_ALLOWLISTED_CAUSES` or the read-tool consumer fixture.

- [x] **Step 5: Preserve owner-only transcription controls**

The existing global trusted-owner transcription configuration remains the only model/cache/device/
language input. The owner-startup CLI/MCP composition adds only:

```text
--direct-audio-footprint-bytes <positive-int>
--direct-audio-footprint-budget-mode baseline_plus
```

The pair must be supplied together and does not enter an ingest request. `ingest` accepts a file
plus existing presentation flags; stdio MCP tool input stays `{"path": string}`. The default
sidecar owner returns:

```json
{
  "problem": "transcription_not_ready",
  "cause": "direct audio requires faster-whisper owner",
  "active_publication_impact": "unchanged",
  "next_step": "configure_faster_whisper_owner"
}
```

No Source or Run may exist after this rejection.

An unconfigured faster-whisper owner returns
`direct audio supervision is not configured / configure_direct_audio_supervision`; a non-Darwin
arm64 owner returns
`direct audio runtime is supported only on Darwin arm64 / run_on_supported_darwin_arm64`. These are
operation-local closed errors and do not expand the shared `PublicError` allowlist.

- [x] **Step 6: Run GREEN and contract regressions**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/interfaces/test_cli_audio.py \
  tests/interfaces/test_cli_error_contract.py \
  tests/interfaces/test_cli_transcription.py \
  tests/interfaces/test_cli_video.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_server.py \
  tests/interfaces/test_mcp_transcription_runtime.py \
  tests/interfaces/test_cli_retrieval.py \
  tests/scripts/test_consumer_source_pack_client.py
UV_OFFLINE=1 uv run ruff check src/mke/cli.py src/mke/interfaces tests/interfaces
UV_OFFLINE=1 uv run pyright
```

Expected: all pass; frozen MCP/read-tool/source-pack schemas remain exact.

- [x] **Step 7: Review and commit Task 6**

```bash
git diff --check
git add src/mke/cli.py src/mke/interfaces/mcp_contract.py src/mke/interfaces/mcp_server.py \
  tests/interfaces/test_cli_audio.py tests/interfaces/test_cli_error_contract.py \
  tests/interfaces/test_cli_transcription.py tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_server.py tests/interfaces/test_mcp_transcription_runtime.py
git commit -m "feat(audio): route direct audio interfaces"
```

---

### Task 7 (PR C): Reconcile And Add Explicit Compiled Library Export v2

**Files:**
- Create: `scripts/compiled_library_export_consumer_v2.py`
- Create: `tests/scripts/test_compiled_library_export_consumer_v2.py`
- Modify: `src/mke/domain/library_export.py`
- Modify: `src/mke/application/library_export.py`
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `src/mke/adapters/filesystem/library_export.py`
- Modify: `src/mke/interfaces/library_export.py`
- Modify: `src/mke/cli.py`
- Modify: `scripts/compiled_library_export_proof.py`
- Modify: `tests/domain/test_library_export.py`
- Modify: `tests/adapters/test_sqlite_library_export.py`
- Modify: `tests/application/test_library_export.py`
- Modify: `tests/adapters/test_library_export_filesystem.py`
- Modify: `tests/interfaces/test_cli_library_export.py`
- Modify: `tests/scripts/test_compiled_library_export_consumer.py`
- Modify: `tests/scripts/test_compiled_library_export_proof.py`

**Interfaces:**
- Consumes: the completed PR C entry-gate reconciliation and active PDF/OCR/video/audio snapshot
  from accepted PR B plus Tasks 5-6.
- Produces: explicit v2 manifest/Markdown/response, default v1 compatibility, v2 standalone consumer, and same-wheel v2 proof.

- [x] **Step 1: Freeze v1 bytes and write reconciled v2 RED tests**

Build committed in-memory/golden snapshots for a v1-compatible PDF/video Library and a v2 mixed
Library containing PDF text, current comparison-only PDF OCR, video, MP3, WAV, and M4A Sources.
The exact v2 expected keys and Markdown fields come from the PR C entry gate, not from pre-evidence
examples in this planning document.

```python
def test_default_export_remains_exact_v1(tmp_path: Path, v1_store: SQLiteStore) -> None:
    default_output = export_library(v1_store, tmp_path / "default")
    explicit_output = export_library(v1_store, tmp_path / "explicit", format_version="v1")
    assert _tree_bytes(default_output) == _tree_bytes(explicit_output) == V1_GOLDEN_TREE


def test_v1_rejects_incomplete_audio_library(tmp_path: Path, mixed_store: SQLiteStore) -> None:
    with pytest.raises(LibraryExportError, match="unsupported_active_media_type"):
        export_library(mixed_store, tmp_path / "v1", format_version="v1")
```

The v2 tests must reject missing/extra Sources, unsupported media, wrong locator, stage/fingerprint
mismatch, stale Publication, evidence graph mismatch, tampered Markdown/JSONL/manifest, symlinks,
unknown schema, and v1/v2 cross-consumption.

- [x] **Step 2: Run RED tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_library_export.py \
  tests/adapters/test_sqlite_library_export.py \
  tests/application/test_library_export.py \
  tests/adapters/test_library_export_filesystem.py \
  tests/interfaces/test_cli_library_export.py \
  tests/scripts/test_compiled_library_export_consumer_v2.py
```

Expected: v2 symbols/flag/consumer are missing; v1 golden passes until the explicit audio snapshot case.

- [x] **Step 3: Add the reconciled closed version-selected domain models**

Preserve the current v1 `CompiledSourceSnapshot` and `CompiledLibrarySnapshot` accepted literals
and validation byte-for-byte. Add separate closed v2 snapshot/source types, or an equivalently
explicit version-discriminated type that cannot widen the v1 constructor. Use a typed selector:

```python
ExportFormatVersion = Literal["v1", "v2"]
V1_MEDIA_TYPES = frozenset({"application/pdf", "video/mp4"})
V2_MEDIA_TYPES = frozenset({"application/pdf", "video/mp4", "audio/mpeg", "audio/wav", "audio/mp4"})


def validate_compiled_source(source: CompiledSourceSnapshot, *, format_version: ExportFormatVersion) -> None:
    allowed = V1_MEDIA_TYPES if format_version == "v1" else V2_MEDIA_TYPES
    if source.media_type not in allowed:
        raise CompiledLibraryValidationError("unsupported_active_media_type")
    _validate_locator_stages_and_fingerprint(source, format_version=format_version)
```

Do not expand the existing v1 parser/consumer accepted schema. New v2 domain validation accepts
the exact reconciled source matrix, including current comparison-only
`pdf-ocr-eval-v1:[0-9a-f]{64}` rows when the live v1 contract still accepts them.

Carry `format_version` through the complete authority path:

```text
CLI --format-version
  -> interfaces.library_export.run_library_export(format_version=...)
  -> KnowledgeEngine.compiled_library_snapshot(format_version=...)
  -> SQLiteStore.compiled_library_snapshot(format_version=...)
  -> closed v1 or v2 snapshot DTO
  -> version-selected renderer and descriptor-bound publisher
  -> closed version-matched response and consumer
```

SQLite must detect a v1-incompatible active audio Source before constructing a v1 DTO and raise a
typed `unsupported_active_media_type` result. The public v1 failure directs the operator to rerun
the complete export with `--format-version v2`; it never reports generic provenance drift or omits
the Source.

- [x] **Step 4: Implement explicit deterministic reconciled v2 rendering and response**

`export_library(store, output, format_version=format_version)` chooses constants from this closed map:

```python
_EXPORT_SCHEMAS = {"v1": "mke.compiled_library_export.v1", "v2": "mke.compiled_library_export.v2"}
_MARKDOWN_FORMATS = {"v1": "mke.compiled_markdown.v1", "v2": "mke.compiled_markdown.v2"}
_RESPONSE_SCHEMAS = {"v1": "mke.compiled_library_export_response.v1", "v2": "mke.compiled_library_export_response.v2"}
```

The closed v2 success and failure values contain exactly the fields frozen by the PR C entry-gate
reconciliation and Step 1 RED tests.
They preserve the v1 safety and determinism properties, identify the exact v2 manifest and Markdown
versions, and never include an output/database path, Source content, hostname, timestamp, temporary
path, or raw diagnostic.

Every layer above rejects an unknown version and proves that response, manifest, Markdown, and
consumer versions match. No renderer-only switch is accepted: Task review must trace a mixed
Library through the real CLI/interface/application/SQLite path.

V2 preserves deterministic order, normalized POSIX relative paths, canonical JSON separators,
content fingerprints, exact active Publication/revision/Run/manifest ownership, EvidenceRef v1, and
post-commit tree revalidation. Add `--format-version {v1,v2}` with default `v1`; reject the option
outside `library export` and preserve existing retrieval-option guards.

- [x] **Step 5: Add a standard-library-only v2 consumer**

`compiled_library_export_consumer_v2.py` must independently parse and validate only v2. It accepts
one export root, checks exact inventory, manifest self-digest, JSONL/source/Markdown digests,
Source/Publication/Run/Evidence ownership, locator/media/stage/fingerprint matrix, no private path,
and portable EvidenceRef fields. It must not import `mke`, Pydantic, MCP, or repository code.

Stable success output:

```json
{
  "schema_version": "mke.compiled_library_export_consumer.v2",
  "status": "passed",
  "export_schema": "mke.compiled_library_export.v2",
  "markdown_format": "mke.compiled_markdown.v2",
  "evidence_schema": "mke.evidence_ref.v1"
}
```

- [x] **Step 6: Extend same-wheel proof without weakening v1 proof**

The proof accepts either a call-owned wheel it builds for task verification or an explicit
descriptor-verified `--mke-wheel` supplied by terminal verification. It installs the same wheel
under explicit Python 3.12 and 3.13 interpreters, creates a
mixed active Library through installed MKE, exports v2 twice, compares exact trees, invokes the
standalone v2 consumer, and reports the same wheel digest. Existing v1 proof cases remain unchanged.

- [x] **Step 7: Run GREEN and full export regressions**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_library_export.py \
  tests/adapters/test_sqlite_library_export.py \
  tests/application/test_library_export.py \
  tests/adapters/test_library_export_filesystem.py \
  tests/interfaces/test_cli_library_export.py \
  tests/scripts/test_compiled_library_export_consumer.py \
  tests/scripts/test_compiled_library_export_consumer_v2.py \
  tests/scripts/test_compiled_library_export_proof.py
UV_OFFLINE=1 uv run ruff check src/mke/domain/library_export.py src/mke/application/library_export.py \
  src/mke/adapters/filesystem/library_export.py src/mke/interfaces/library_export.py \
  scripts/compiled_library_export_consumer_v2.py scripts/compiled_library_export_proof.py
UV_OFFLINE=1 uv run pyright
```

Expected: all pass; legacy v1 tree and consumer remain exact; v2 exports every active Source once.

- [x] **Step 8: Review and commit Task 7**

```bash
git diff --check
git add src/mke/domain/library_export.py src/mke/application/library_export.py \
  src/mke/adapters/sqlite/__init__.py src/mke/adapters/filesystem/library_export.py \
  src/mke/interfaces/library_export.py src/mke/cli.py \
  scripts/compiled_library_export_consumer_v2.py scripts/compiled_library_export_proof.py \
  tests/domain/test_library_export.py tests/adapters/test_sqlite_library_export.py \
  tests/application/test_library_export.py tests/adapters/test_library_export_filesystem.py \
  tests/interfaces/test_cli_library_export.py tests/scripts/test_compiled_library_export_consumer.py \
  tests/scripts/test_compiled_library_export_consumer_v2.py \
  tests/scripts/test_compiled_library_export_proof.py
git commit -m "feat(export): add mixed library v2"
```

Task review must separately approve v1 byte compatibility and v2 completeness.

---

### Task 8 (PR C): Add Model-Free Product Proof And Required CI Coverage

**Files:**
- Create: `src/mke/proof/direct_audio.py`
- Create: `tests/proof/test_direct_audio.py`
- Modify: `src/mke/proof/__init__.py`
- Modify: `src/mke/cli.py`
- Modify: `tests/interfaces/test_cli_proof.py`
- Modify: `.github/workflows/ci.yml` only if the existing transcription-extra matrix does not execute the required model-free slice.

**Interfaces:**
- Consumes: accepted PR A fixtures/receipt plus Tasks 5-7 canonical ingest,
  Publication/Search/Ask, reconciled export v2, and independent v2 consumer.
- Produces: deterministic model-free direct-audio product proof and bounded required CI coverage.

- [x] **Step 1: Write model-free product-proof RED tests**

The proof injects a project-owned fake audio provider at the application port but exercises the
real snapshot, inspection, Run/Publication, Search/Ask, EvidenceRef, export v2, consumer, and
cleanup paths. It must not construct a real model or call a network-capable resolver.

Cover every closed proof failure code, exact code/next-step pairing, unknown-exception redaction,
success-field absence, and stable JSON keys in RED tests before implementing the report.

Generate one call-owned deterministic synthetic audio case at the exact 15-minute duration boundary
and one exact 100-MiB byte-boundary mutation for model-free inspection/admission tests; neither is
committed or passed through real ASR. Prove equality acceptance, over-bound rejection before model
construction, bounded cleanup, and no active-Publication change. Generate these exact-boundary
artifacts once per test session and reuse their immutable identities across focused cases; do not
recreate 100-MiB inputs in each test or retry loop. The single terminal real-ASR proof continues to
use the three small redistribution-safe fixtures; no performance SLA or second real provider run is
added.

```python
def test_direct_audio_proof_covers_all_formats_and_product_path(tmp_path: Path) -> None:
    report = run_direct_audio_proof(
        fixture_root=AUDIO_FIXTURE_ROOT,
        workspace=tmp_path / "proof",
        provider=DeterministicAudioProvider(),
    )
    assert report.status == "passed"
    assert report.media_types == ("audio/mpeg", "audio/wav", "audio/mp4")
    assert report.published_run_count == 3
    assert report.timestamp_evidence is True
    assert report.search_ask_projection_equal is True
    assert report.export_schema == "mke.compiled_library_export.v2"
    assert report.consumer_status == "passed"
    assert report.cleanup is True
```

- [x] **Step 2: Run RED tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/proof/test_direct_audio.py \
  tests/interfaces/test_cli_proof.py
```

Expected: missing product-proof module and CLI contract.

- [x] **Step 3: Implement the deterministic proof report**

```python
DirectAudioProofFailureCode = Literal[
    "fixture_invalid",
    "snapshot_failed",
    "inspection_failed",
    "ingest_failed",
    "publication_incomplete",
    "evidence_mismatch",
    "export_failed",
    "consumer_failed",
    "cleanup_failed",
]

DirectAudioProofNextStep = Literal[
    "check_fixture_receipt",
    "retry_with_stable_file",
    "choose_supported_file",
    "check_server_logs",
    "retry_when_owner_ready",
    "rerun_direct_audio_proof",
    "rerun_export_v2",
    "check_export_consumer",
]


@dataclass(frozen=True)
class DirectAudioProofReport:
    schema_version: Literal["mke.direct_audio_proof.v1"]
    status: Literal["passed", "failed"]
    media_types: tuple[str, ...]
    published_run_count: int
    evidence_count: int
    timestamp_evidence: bool
    search_ask_projection_equal: bool
    evidence_schema: Literal["mke.evidence_ref.v1"]
    export_schema: Literal["mke.compiled_library_export.v2"]
    markdown_format: Literal["mke.compiled_markdown.v2"]
    consumer_status: Literal["passed", "failed"]
    network_access: Literal["not_used"]
    cleanup: bool
    failure_code: DirectAudioProofFailureCode | None = None
    next_step: DirectAudioProofNextStep | None = None
```

`mke proof direct-audio --json` emits exactly one closed object, returns 0 only for `passed`, and
uses a temporary database/export root outside the repository. It must not alter `mke proof run`,
`mke demo --verify`, local-knowledge proof, Evidence-provenance proof, or consumer source-pack proof.
Freeze the exact failure-code-to-next-step map and require both fields to be absent on success and
present/matched on failure. Unknown exceptions map to a closed redacted failure; no path, exception,
stderr, or arbitrary string crosses the proof boundary.

- [x] **Step 4: Run model-free GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/proof/test_direct_audio.py \
  tests/interfaces/test_cli_proof.py \
  tests/adapters/test_audio_fixtures.py \
  tests/scripts/test_compiled_library_export_consumer_v2.py
UV_OFFLINE=1 uv run ruff check src/mke/proof tests/proof tests/interfaces/test_cli_proof.py
UV_OFFLINE=1 uv run pyright
```

Expected: all model-free tests pass.

- [x] **Step 5: Bind required CI without model downloads**

Prefer the existing Python 3.12/3.13 transcription-extra jobs. Add exact tests for fixture decode,
fake-model audio child, model-free proof, accepted PR A receipt validator, `pip check`, empty-cache
doctor, and network denial. Modify `.github/workflows/ci.yml` only if these commands are not already
executed.
Do not add a model download, hosted cache mutation, system FFmpeg requirement, or arbitrary short
job timeout.

- [x] **Step 6: Review and commit Task 8**

```bash
git diff --check
git add src/mke/proof/direct_audio.py src/mke/proof/__init__.py src/mke/cli.py \
  tests/proof/test_direct_audio.py tests/interfaces/test_cli_proof.py \
  .github/workflows/ci.yml
git commit -m "proof(audio): add model-free direct audio proof"
```

Omit `.github/workflows/ci.yml` from staging when unchanged. This Task validates the accepted PR A
receipt but does not regenerate or reinterpret its license evidence.

---

### Task 9 (PR C): Build The Fresh-Wheel Terminal Proof Controller

**Files:**
- Create: `scripts/direct_audio_deployment_proof.py`
- Create: `tests/scripts/test_direct_audio_deployment_proof.py`
- Modify: `src/mke/proof/mcp_deployment_client.py`
- Modify: `tests/proof/test_mcp_deployment_client.py`
- Modify: `docs/how-to/run-direct-audio-proof.md` only after the proof schema is fixed in tests.

**Interfaces:**
- Consumes: one fresh MKE wheel, accepted PR A dependency/license receipt digest, exact prepared
  model tree, three fixtures, installed CLI/MCP, and the reconciled export v2 consumer.
- Produces: `mke.direct_audio_deployment_proof.v1` aggregate bound to wheel, package set, model tree, fixtures, Publications, Evidence, export, consumer, network denial, and cleanup.

- [x] **Step 1: Write controller RED tests with fake subprocess boundaries**

Cover exact two interpreters, same wheel, receipt binding, isolated venvs, the accepted PR A
nested-pip argv/environment contract, descriptor-verified per-cell wheel compatibility and
lock-derived constraints binding, installed-module
identity, no `PYTHONPATH`, no repository import, model tree descriptor validation,
network canary, three-format Python/CLI calls, one real stdio MCP call plan, Search/Ask,
Publication/EvidenceRef, v2 export/consumer/copy, output limits, child timeout/process cleanup,
atomic receipt write, failure codes, and call-owned cleanup.

Add explicit negatives for swapped constraints, marker drift, a missing or extra wheel, a
same-name/different-digest wheel, an ambiguous compatible pair, wrong tags, inherited pip
config/index/proxy/build inputs, and any mismatch between Task 9 inputs and the accepted PR A
constraints/wheelhouse-manifest cells.

```python
def test_controller_requires_same_wheel_for_both_interpreters(fake_runner: FakeRunner) -> None:
    report = run_direct_audio_deployment_proof(_valid_config(), command_runner=fake_runner)
    assert report.interpreter_count == 2
    assert {cell.proof_input_wheel_sha256 for cell in report.cells} == {MKE_WHEEL_SHA256}
    assert report.status == "passed"
```

Public `run_direct_audio_deployment_proof()` must not accept fake provider, sandbox, network, model,
or footprint seams. Test-only orchestration lives behind a private controller function and cannot publish
canonical evidence.

- [x] **Step 2: Run RED tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_direct_audio_deployment_proof.py \
  tests/proof/test_mcp_deployment_client.py
```

Expected: missing controller/schema and MCP audio orchestration.

- [x] **Step 3: Implement bounded installed-wheel orchestration**

The public CLI is:

```text
python scripts/direct_audio_deployment_proof.py
  --python "$PYTHON312"
  --python "$PYTHON313"
  --mke-wheel "$MKE_WHEEL"
  --dependency-receipt benchmarks/audio/dependency-artifacts.json
  --wheelhouse "$TRANSCRIPTION_WHEELHOUSE"
  --constraints "$TRANSCRIPTION_CONSTRAINTS"
  --model-root "$MKE_MODEL_ROOT"
  --fixture-root tests/fixtures/audio
  --json
```

There is no download flag. Resolve each interpreter strictly to a regular executable target so
GitHub-style interpreter symlinks are valid while missing, dangling, directory, or non-executable
targets fail closed. Every external command uses bounded stdout/stderr, a process group, timeout,
parent wait, descendant cleanup, and a call-owned environment/home/cache/temp root.

- [x] **Step 4: Bind installed package and model authority before inference**

For each environment:

1. verify the dependency receipt, fresh MKE wheel, and lock-derived constraints through descriptor
   reads; independently derive the wheelhouse's sorted full-filename/parsed-tags/bytes/SHA-256
   manifest, resolve exactly one compatible wheel per required distribution/version/cell, and
   require exact equality with the accepted PR A cells;
2. create a fresh venv and install `wheel[transcription]` only through the accepted PR A nested-pip
   argv/environment authority: isolated and config-free, `--no-index`, one validated local
   `--find-links`, binary-only hashed roots/constraints, and no proxy/index/cache/build fallback;
3. run `pip check` and compare the complete installed distribution map;
4. prove imported `mke` comes from that venv and installed files match wheel bytes/RECORD;
5. verify the exact model inventory, revision, file sizes, SHA-256 values, aggregate tree digest,
   model card, and license before constructing a provider;
6. run the network canary under the same deny-network boundary as doctor and provider commands; and
7. delete call-owned bytecode before installed-module identity checks and execution.

- [x] **Step 5: Execute the real product path**

Using installed code only:

- doctor returns ready without writing the model root;
- Python and CLI ingest all three fixtures through `KnowledgeEngine.ingest_file()`;
- official MCP SDK invokes path-only `ingest_file` for at least one format;
- every successful Run is published with a complete report and exact Source SHA;
- Search and Ask return the stable fixture keyword and equivalent portable EvidenceRefs;
- timestamp locators are ordered and inside inspected duration;
- v2 exports the complete active Library twice with equal bytes;
- independent v2 consumer passes before and after copying the export to another root; and
- no v1 export, legacy MCP schema, model tree, retained wheelhouse, or repository state changes.

Do not require exact full transcript equality across runtimes. Bind a stable expected keyword,
non-empty normalized transcript, exact publication graph, locator integrity, and Source identity.

- [x] **Step 6: Run controller GREEN tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_direct_audio_deployment_proof.py \
  tests/proof/test_mcp_deployment_client.py \
  tests/scripts/test_transcription_deployment_proof.py \
  tests/proof/test_transcription_proof.py
UV_OFFLINE=1 uv run ruff check scripts/direct_audio_deployment_proof.py \
  tests/scripts/test_direct_audio_deployment_proof.py src/mke/proof/mcp_deployment_client.py
UV_OFFLINE=1 uv run pyright
```

Expected: all model-free controller tests pass and the historical video deployment proof remains valid.

- [x] **Step 7: Freeze the terminal proof authorization manifest without running real ASR**

The controller tests freeze the exact inputs that Task 10 must report before authorization: final
MKE wheel SHA-256, PR A receipt digest, canonical wheelhouse-manifest and constraints digests,
prepared model identifier,
revision and tree digest, interpreter versions, retained inputs, estimated temporary disk use,
deny-network method, cleanup ownership, and the exact owner-configured
`direct_audio_footprint_bytes` plus `baseline_plus` mode. If any input is absent, Task 10 stops;
nothing downloads or repairs it. The later real proof records configured bytes/mode, baseline,
observed peak, effective budget, and overshoot as fixed-fixture Darwin arm64 observations only. Do
not run a non-terminal real ASR checkpoint in this Task or promote those observations to a default,
recommendation, product ceiling, SLA, or cross-platform fact.

- [x] **Step 8: Review and commit Task 9**

The controller, tests, and proof-schema documentation are committed; raw proof output remains
external evidence and volatile timings are not frozen as thresholds. Then:

```bash
git diff --check
git add scripts/direct_audio_deployment_proof.py tests/scripts/test_direct_audio_deployment_proof.py \
  src/mke/proof/mcp_deployment_client.py tests/proof/test_mcp_deployment_client.py \
  docs/how-to/run-direct-audio-proof.md
git commit -m "proof(audio): verify installed direct audio path"
```

Do not commit model weights, caches, venvs, wheelhouses, candidate wheels, databases, or raw logs.

---

### Task 10 (PR C): Document The Contract, Close Conditional Identity, And Run Final Gates

**Files:**
- Create: `docs/decisions/0011-bounded-direct-audio-intake.md`
- Create: `docs/how-to/use-direct-audio.md`
- Create: `docs/how-to/run-direct-audio-proof.md` if not created in Task 9
- Modify: `docs/reference/direct-audio-dependency-and-license-evidence.md`
- Create: `tests/evaluation/test_direct_audio_documentation.py`
- Create: `docs/superpowers/reviews/2026-07-18-bounded-direct-audio-intake-implementation-review.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/reference/contracts.md`
- Modify: `docs/reference/mcp-contract.md`
- Modify: `docs/how-to/use-local-transcription.md`
- Modify: `docs/how-to/use-mke-mcp.md`
- Modify: `docs/how-to/export-compiled-library.md`
- Modify: `docs/how-to/verify-release.md`
- Modify: `docs/tutorials/getting-started.md`
- Modify: `scripts/release_presentation_audit.py`
- Modify: `tests/scripts/test_release_presentation_audit.py`
- Modify: approved retrieval identity artifacts only when canonical validators prove identity drift.

**Interfaces:**
- Consumes: reviewed actual behavior and proof identities from Tasks 1-9.
- Produces: accepted ADR/docs/claims, canonical evaluation provenance, clean reviewed feature branch, and final evidence for independent authority review.

- [x] **Step 1: Write documentation and overclaim RED tests**

The contract test requires bounded MP3/WAV-PCM/M4A-AAC, 15 minutes, 100 MiB, voice notes and clips
or excerpts rather than full-length meeting/interview/lecture support, owner-configured cache-only
faster-whisper, explicit preparation, timestamp EvidenceRef, atomic Publication, Python/CLI/MCP,
default v1/explicit reconciled v2, independent consumer, and real proof boundaries.

Documentation tests require one copy-ready golden path for each supported entry surface:

- Python: typed owner/runtime construction, `KnowledgeEngine.ingest_file()`, Search/Ask, and close;
- CLI: prepare, doctor, ingest `interview-excerpt.m4a`, Search, Ask, and explicit v2 export; and
- stdio MCP: owner startup flags plus the unchanged `{"path": "interview-excerpt.m4a"}` tool call.

Freeze existing success keys, timestamp EvidenceRef v1, and explicit export version in examples;
examples must not invent `media_type` or request-time model controls. Lead the onboarding path with
the one-command offline model-free proof, then present one sequential source-checkout route through
the first real Evidence before alternatives. State prerequisites and which separately authorized
step may download, distinguish deterministic product-wiring proof from real ASR readiness, and give
a checkpoint after proof, doctor, ingest, and export.

Also require a complete public recovery table mapping every direct-audio problem/cause/`next_step`
token and every model-free proof failure code to one copy-paste command or bounded operator action.
MCP owner configuration changes explicitly require a controlled server restart; destructive cache
repair, implicit download, and generic “check logs” without a bounded diagnostic command are not
presented as automatic recovery.

The export migration table must prove:

- existing PDF/video automation and explicit v1 remain byte-identical;
- an active audio Source makes default or explicit v1 fail with the exact command to rerun the
  complete export as `--format-version v2`;
- v1 and v2 consumers are intentionally distinct and never cross-consume; and
- rollback preserves v1 by omitting/removing audio from the active snapshot, never by widening or
  weakening the v1 validator.

Presentation tests reject affirmative claims for arbitrary codecs, full-length meetings,
interviews or lectures, long audio, chunking, resume, streaming, diarization, microphone capture,
implicit download, cloud/hosted fallback, automatic LLM Wiki sync,
cross-platform coverage, transcript accuracy, SLA, deployment, adoption, business impact, PyPI, or
official OpenAI integration. Wrapped Markdown paragraphs and legitimate negated boundary statements
must be tested.

Also freeze the complete approved positive sentence from the design Claim Boundary as a passing
fixture, plus unqualified `meetings`, `interviews`, and `lectures` claims as failing fixtures. The
audit must distinguish bounded clips/excerpts from full-length support rather than banning the
approved nouns mechanically.

- [x] **Step 2: Run documentation RED tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_direct_audio_documentation.py \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/scripts/test_release_presentation_audit.py
```

Expected: direct-audio docs and overclaim rules are missing.

- [x] **Step 3: Add ADR-0011 and public documentation**

ADR-0011 records the accepted bounded-audio decision, immutable snapshot, additive audio protocol,
cache-only owner policy, canonical dispatcher, command-local errors, export v2, proof and license
gates, rollback, and non-goals. It supersedes only the historical deferral of direct audio; it does
not rewrite ADR-0003/0005/0006.

Public docs describe only behavior proved on the feature branch. Before v0.1.4 publication they
must say the feature is an accepted candidate or development capability, not a released version.
LLM Wiki may be named only as an independently verified downstream compatibility target after that
proof merges; it remains outside MKE runtime and Evidence authority.

`docs/how-to/use-direct-audio.md` leads with the tested golden path and troubleshooting table;
reference pages hold the full option/schema matrices. Record observed ready-owner-to-first-Evidence
time and step count from the terminal proof as diagnostics only, excluding separately authorized
model acquisition and making no SLA or cross-platform claim.

Update the PR A `docs/reference/direct-audio-dependency-and-license-evidence.md` only with PR C's
distinct model and final installed-proof bindings. Preserve its exact external receipt schema,
constraints and wheelhouse-manifest digests, PyAV wheel/runtime boundary, linked or bundled FFmpeg
component inventory/direct evidence, fixture redistribution basis, supported proof platforms,
Darwin arm64 supervisory authority, target-executable probe, and the exact
`external_binary_redistribution=not_performed` /
`redistribution_authority=not_claimed` literals. Preserve the hard stop for fixture redistribution,
local-use feasibility, executable identity, and supervisor evidence; do not convert unresolved
transitive redistribution clearance into a failure while external binaries remain undistributed.
Document that future bundling or release redistribution requires separate legal review.
Do not rewrite or refresh PR A license evidence merely because MKE source/docs changed. It must not
copy local paths, environment dumps, or infer redistribution permission from package metadata
alone.

- [x] **Step 4: Make docs and audit GREEN**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_direct_audio_documentation.py \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/evaluation/test_repository_governance_documentation.py \
  tests/scripts/test_release_presentation_audit.py
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --json
```

Expected: all tests pass and audit returns `{"status":"ok","violations":[]}`.

- [ ] **Step 5: Run canonical evaluation validators before writing artifacts**

Run the repository's exact E1, E2, E3-A, E3-B, E3-C, E3-D, and E3-E validators from the current CI
workflow. If all pass, do not create an identity commit. If only source/scope/dependency identities
fail because of this branch, use the existing approved mechanical transaction from one committed
candidate and preserve normalized semantic projections.

Before refresh, capture exact allowed paths and semantic projections. After refresh, require:

- exact staged/mirror byte equality;
- all seven canonical validators pass;
- observations, ordered results, metrics, thresholds, gates, diagnostics, profile, candidate,
  status, and verdict are unchanged; and
- no OCR scorecard/receipt, corpus, qrels, queries, runtime selector, or dependency change outside
  the proved identity closure.

If the transaction fails, run only its documented recovery command, verify no partial diff, and
stop for authority review. Do not hand-edit generated evaluation artifacts.

- [ ] **Step 6: Run the final actual-diff review and bounded fix loop**

Commit the implementation/docs candidate before whole-branch review, without yet creating the
durable implementation-review record or claiming a final review verdict:

```bash
git diff --check
git add README.md README_CN.md docs/README.md \
  docs/decisions/0011-bounded-direct-audio-intake.md \
  docs/explanation/architecture.md docs/reference/cli.md docs/reference/contracts.md \
  docs/reference/mcp-contract.md \
  docs/reference/direct-audio-dependency-and-license-evidence.md \
  docs/tutorials/getting-started.md \
  docs/how-to/use-direct-audio.md docs/how-to/run-direct-audio-proof.md \
  docs/how-to/use-local-transcription.md docs/how-to/use-mke-mcp.md \
  docs/how-to/export-compiled-library.md docs/how-to/verify-release.md \
  docs/superpowers/plans/2026-07-18-bounded-direct-audio-intake-implementation.md \
  scripts/release_presentation_audit.py tests/evaluation/test_direct_audio_documentation.py \
  tests/scripts/test_release_presentation_audit.py
git commit -m "docs(audio): document bounded direct audio intake"
```

If and only if the validator-proven identity transaction produced a non-empty approved diff,
write its already audited exact path list to `$evidence_root/identity-paths.txt`, one repository
relative path per line, stage only that list, and commit it before review:

```bash
git add --pathspec-from-file="$evidence_root/identity-paths.txt"
git commit -m "test(eval): refresh direct audio identities"
```

The execution report lists every identity path before staging and proves it belongs to the approved
validator-generated closure. The implementation controller performs internal task reviews and
integrates all lanes. An independent authority reviewer then runs one pre-PR whole-branch
findings-only review of that exact committed candidate against the approved spec and plan,
including the accepted PR A receipt and durable license document. Findings return to the
implementation controller for
`superpowers:receiving-code-review`, targeted repair, focused verification, full verification, and
targeted authority re-review. Do not run repeated full review without a material diff.

After two or three evidence-backed repairs of the same finding, first decide whether it remains a
real release blocker or should become a known limitation/follow-up. Do not continue an assurance
spiral solely because a theoretical race or unsupported platform can be imagined.

Every substantive fix is committed and moves the candidate HEAD before targeted re-review. The
reviewer returns an exact reviewed HEAD, verdict, findings, and verification identity outside the
repository. Step 7 persists only that returned durable result. A substantive discrepancy in the
record or status restarts this review step; a mechanical public-neutral transcription receives one
targeted read-back, not another full whole-branch review.

- [ ] **Step 7: Persist and commit the returned durable review result**

After a clean verdict, write the exact reviewed HEAD, verdict, verification identity, durable
public-neutral findings, and final plan status to the implementation review record and plan. Then
stage only those two files:

```bash
git diff --check
git add \
  docs/superpowers/plans/2026-07-18-bounded-direct-audio-intake-implementation.md \
  docs/superpowers/reviews/2026-07-18-bounded-direct-audio-intake-implementation-review.md
git commit -m "docs(audio): record implementation review"
```

Read back both committed files and compare them with the returned review result. This mechanical
targeted read-back does not rerun the whole review. Any substantive mismatch or new implementation
change returns to Step 6. This review/status commit is the final planned tracked write before the
terminal MKE wheel is built.

- [ ] **Step 8: Build the final MKE wheel and bind the terminal proof inputs**

After PR C implementation, documentation, plan/review status, and any conditional identity closure
are committed, require the accepted PR A dependency/license receipt and recompute its canonical
digest without changing its bytes. Build one fresh final MKE wheel from the exact candidate HEAD.
The terminal proof input record binds this wheel digest, the accepted PR A receipt digest, the
accepted constraints and wheelhouse-manifest digests, actual installed package-set digest, the
prepared model-tree digest, and fixture identities.

```bash
evidence_root="$(mktemp -d)"
mkdir -p "$evidence_root/dist"
UV_OFFLINE=1 uv build --out-dir "$evidence_root/dist"
MKE_WHEEL="$(find "$evidence_root/dist" -maxdepth 1 -type f \
  -name 'multimodal_knowledge_engine-*.whl' -print)"
test -f "$MKE_WHEEL"
MKE_WHEEL_SHA256="$(shasum -a 256 "$MKE_WHEEL" | awk '{print $1}')"
PR_A_RECEIPT_SHA256="$(shasum -a 256 benchmarks/audio/dependency-artifacts.json | awk '{print $1}')"
```

Do not regenerate the PR A receipt unless an external dependency or constraints, prepared
wheelhouse, PyAV wheel, validation platform, supervisory mechanism, or fixture authority changed.
Such a change invalidates the staged premise and returns to PR A; it is not repaired inside PR C.
Later tracked PR C changes require a fresh MKE wheel and terminal proof, but not a circular rerun of
the complete external inventory/direct-evidence analysis.

- [ ] **Step 9: Run final repository and real-provider gates on the reviewed terminal HEAD**

Generate fresh terminal observations after the final MKE wheel build and any review repair. The
numeric observation must use an exclusive call-owned protocol copy whose scope is refreshed before
the observation runs; an observation generated directly from the checked-in numeric protocol is
not terminal authority.

Before the single real-ASR execution, report the exact final MKE wheel SHA-256, PR A receipt digest,
wheelhouse and lock-derived constraints digests, prepared model identifier/revision/tree digest,
interpreter versions, retained inputs, estimated temporary disk use, deny-network method, and
cleanup ownership, then stop for the separately required real-model-proof authorization. If the
exact prepared inputs are absent, stop without download or repair.

```bash
terminal_eval_dir="$(mktemp -d)"
terminal_e2_protocol="tests/fixtures/retrieval-numeric-v1/.protocol-lock.direct-audio-terminal.json"
test ! -e "$terminal_e2_protocol"
cleanup_terminal_eval() {
  rm -f -- "$terminal_e2_protocol"
  if test -n "$terminal_eval_dir" && test -d "$terminal_eval_dir"; then
    rm -rf -- "$terminal_eval_dir"
  fi
}
trap cleanup_terminal_eval EXIT INT TERM

cp tests/fixtures/retrieval-numeric-v1/protocol-lock.json "$terminal_e2_protocol"
UV_OFFLINE=1 uv run python -m mke.evaluation.numeric_comparison refresh-scope \
  --protocol "$terminal_e2_protocol" \
  --repository .
UV_OFFLINE=1 uv run mke eval retrieval-numeric \
  --protocol "$terminal_e2_protocol" \
  --json > "$terminal_eval_dir/e2.json"
jq -e '
  .schema_version == "mke.retrieval_numeric_comparison.v1" and
  .protocol_id == "retrieval-numeric-v1" and
  .integrity_status == "passed" and
  .candidate_status == "passed" and
  .integrity_failures == []
' "$terminal_eval_dir/e2.json"
rm -f -- "$terminal_e2_protocol"
test ! -e "$terminal_e2_protocol"

UV_OFFLINE=1 uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > "$terminal_eval_dir/e1.json"
UV_OFFLINE=1 uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > "$terminal_eval_dir/e3a.json"
UV_OFFLINE=1 uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > "$terminal_eval_dir/e3b.json"

UV_OFFLINE=1 uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository .
UV_OFFLINE=1 uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed "$terminal_eval_dir/e2.json" \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
UV_OFFLINE=1 uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed "$terminal_eval_dir/e3a.json" \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
UV_OFFLINE=1 uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed "$terminal_eval_dir/e3b.json" \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
UV_OFFLINE=1 uv run python -m mke.evaluation.dense_artifact validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --repository .
UV_OFFLINE=1 uv run python -m mke.evaluation.hybrid_rrf_artifact validate \
  --artifact benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --repository .
UV_OFFLINE=1 uv run python -m mke.evaluation.relevance_gate_artifact validate \
  --artifact benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --repository .
cleanup_terminal_eval
trap - EXIT INT TERM
test ! -e "$terminal_eval_dir"
```

Expected: the four observations and all seven canonical validators pass on the exact reviewed
terminal HEAD. Any failure after the receipt commit is a terminal blocker; do not cite the earlier
Step 5 validator run as substitute evidence.

```bash
UV_OFFLINE=1 uv run pytest -q
UV_OFFLINE=1 uv run ruff check .
UV_OFFLINE=1 uv run pyright
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py --json
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py --json
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py --json
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --mke-wheel "$MKE_WHEEL" \
  --json
UV_OFFLINE=1 uv run mke proof direct-audio --json
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --json
HF_HUB_OFFLINE=1 UV_OFFLINE=1 uv run python scripts/direct_audio_deployment_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --mke-wheel "$MKE_WHEEL" \
  --dependency-receipt benchmarks/audio/dependency-artifacts.json \
  --wheelhouse "$TRANSCRIPTION_WHEELHOUSE" \
  --constraints "$TRANSCRIPTION_CONSTRAINTS" \
  --model-root "$MKE_MODEL_ROOT" \
  --fixture-root tests/fixtures/audio \
  --json
git diff --check
git status --short
```

Expected: tests, Ruff, Pyright, build, existing proofs, v1/v2 compiled proof, direct-audio proof,
presentation audit, all canonical validators, and the real cache-only deployment proof pass; source
worktree is clean. The final HEAD, fresh wheel SHA, committed receipt digest, installed package-set
digest, model tree digest, fixture digests, export digest, consumer result, and proof aggregate must
be mutually consistent. The exact test count and wheel digest must be reported from this run, not
predicted here.

- [ ] **Step 10: Stop without a post-proof tracked write**

All implementation-plan/review status text must already be committed before Step 8. Do not update a
checkbox or review file after the final MKE wheel/terminal-proof sequence. A later tracked change
invalidates the MKE wheel and terminal proof and requires Steps 8-9 again; it does not invalidate
the PR A receipt unless one of that receipt's external authority inputs changed.

Stop with a clean local branch/worktree, exact commit series, changed-file inventory, diff stat,
test/build/proof identities, license evidence, residual boundaries, and next authorization. Do not
push or create a PR until the user explicitly authorizes it.

After the final report has preserved the required digests and aggregates, remove every call-owned
temporary directory created by this task, including `$evidence_root`, and verify it no longer
exists. Retained operator-owned wheelhouses and model caches are read-only inputs and are not part
of this cleanup.

---

## Final Acceptance Matrix

| Requirement | Task authority | Blocking evidence |
|---|---|---|
| MP3/WAV/M4A closed profiles | 1, 2, 3 | Exact fixture/probe matrix and invalid-profile negatives |
| Immutable inspected/transcribed bytes | 3, 5 | Descriptor identity, SHA, replacement and cleanup regressions |
| Cache-only faster-whisper | 4, 8, 9 | Owner composition, empty-cache negative, real network-denied proof |
| Run/Publication/report atomicity | 5 | Failure, supersession, rollback, Search/Ask tests |
| Python/CLI/MCP canonical routing | 5, 6, 9 | One dispatcher and exact path-only MCP contract |
| Legacy video/PDF/read-tool compatibility | 1-7 | Existing suites and frozen fixtures unchanged |
| Export v1 compatibility | 7 | Default/explicit v1 golden bytes and legacy consumer |
| Complete Export v2 | 7, 9 | LLM Wiki evidence reconciliation, mixed Library, repeated tree equality, v2 consumer and copy proof |
| Python 3.12/3.13 package authority | 1, 9 | PR A external cells plus final same-wheel ordinary-pip installed identity |
| Local binary evidence and redistribution boundary | 1 | Exact PyAV-linked inventory/direct evidence, fixed non-redistribution literals, fixture authority, executable probe, and Darwin arm64 supervisor proof before PR B |
| Real local product proof | 9 | Three formats, MCP, EvidenceRef, export v2, network denial, cleanup |
| Honest public claims | 10 | ADR/docs contracts and presentation audit |
| Retrieval evaluation non-regression | 10 | Seven validators and semantic equality when identity refresh is needed |

## Release Boundary

Completion of this plan produces a feature candidate, not v0.1.4 publication. After merge and
exact-main hosted verification, write a separate release-closeout spec/plan bound to the actual
merged scope. Version bump, candidate receipt, tag, GitHub Release, archive smoke, PyPI/registry,
deployment, and post-release docs remain separately authorized actions. If that closeout would
bundle, vendor, attach, or otherwise redistribute external dependency binaries, it must first stop
for the separate legal review required by the amended PR A authority.

---

## GSTACK REVIEW REPORT

### Review Identity And Verdict

- Reviewed committed revision: `c150c3c3c49990265cb756ef45a3669cd683714c`.
- Review mode: one fresh full plan review of the amended revision; no competing whole-plan review
  chain was layered onto it.
- Targeted repair: a later actual-diff authority review of
  `bf4fc6107ca3afeb7f84da773a2ca0f2ef72d062` identified three P1 executability gaps on the single
  PR A offline-input surface. They were repaired and targeted-re-reviewed without rerunning CEO,
  Engineering, Developer Experience, or the full Autoplan chain.
- CEO review: clean after nine accepted product-boundary and proof amendments; dual-voice consensus
  confirmed all nine.
- Design review: skipped because this plan adds no graphical or browser UI.
- Engineering review: clean after six accepted correctness and operability amendments; dual-voice
  consensus confirmed all six.
- Developer-experience review: initial `3.8/5`, clean after six accepted onboarding, schema, and
  sequencing amendments; dual-voice consensus confirmed all six.
- Authority amendment: the original resource-enforcement, target-executable preflight, and
  external-binary redistribution-clearance surfaces are superseded by
  `docs/superpowers/reviews/2026-07-18-bounded-direct-audio-intake-authority-amendment.md`; unrelated
  review findings and staging remain unchanged.
- Final verdict: `CLEARED FOR STAGED IMPLEMENTATION; PR A REQUIRES SEPARATE DISPATCH`.

### Plan Summary

The plan delivers a closed direct-audio capability in three ordered implementation PRs. PR A proves
external dependency/local-binary feasibility, fixture redistribution, wheelhouse authority, fixed
target-executable identity, and Darwin arm64 supervisory behavior without changing runtime code or
redistributing external binaries. PR B builds only project-owned internal contracts, immutable
intake, integrates the accepted supervisor into bounded children, storage authority, and model-free
compatibility. PR C begins only after PR A,
PR B, and the independent LLM Wiki compatibility evidence are accepted and merged; it activates the
public application/CLI/MCP path, reconciles and freezes Export v2, proves the installed wheel and
real cache-only provider, updates public docs, and runs terminal verification. Release publication
remains a separate post-merge closeout.

### Cross-Phase Themes

1. Native media parsing is an explicit receipt-backed Darwin arm64 supervised-child boundary with
   leader-only non-aggregate `ri_phys_footprint` polling and fail-closed ordinary-descendant
   process-group cleanup, not an owner-process, timeout-only, hard-kernel, sandbox, escaped-hostile-
   descendant, or hostile-media assumption.
2. Immutable Source authority includes allowed-root containment, descriptor identity, a second
   full digest, timestamp metadata, and cleanup before candidate persistence.
3. Resource admission precedes snapshot, child, and model work; busy requests perform zero model
   construction.
4. Export v1 remains byte-compatible while v2 is reconciled with real downstream evidence before
   its closed shape is frozen.
5. External binaries are classified `local_runtime_only`; local inventory/direct evidence and the
   explicit external-binary non-redistribution boundary are stable across ordinary MKE commits.
   Committed fixtures are classified `repository_distributed`; terminal installed proof binds one
   fresh MKE wheel to the accepted external receipt digest. Future bundling or redistribution
   requires separate legal review.
6. Operator paths lead with a one-command model-free proof and closed, actionable recovery tokens.

### Architecture And Data Flow

```text
PR A: locked external inputs -> canonical constraints/wheelhouse manifest
     -> fixed target-executable identity probe
     -> PyAV/FFmpeg component inventory/direct evidence
     -> fixture redistribution + non-redistribution literals
     -> Darwin arm64 controlled allocator/supervisor -> accept or hard stop

PR B: unresolved operator path -> allowed-root/descriptor authority
     -> immutable snapshot + second digest -> bounded inspection child
     -> integrate ri_phys_footprint polling + TERM/grace/KILL/wait
     -> project-owned audio contracts + cache-only internal child
     -> storage/model-free compatibility (no public activation)

PR C: accepted LLM Wiki v1 evidence -> bounded Export v2 reconciliation
     -> KnowledgeEngine.ingest_file -> CLI/MCP application lifecycle
     -> Run -> validated Evidence -> atomic Publication -> Search/Ask
     -> Export v2 -> independent consumer
     -> fresh wheel + accepted PR A receipt + prepared model tree
     -> one network-denied real-ASR terminal proof
```

### Test Plan Artifact

| Layer | Primary evidence | Required negatives |
|---|---|---|
| PR A fixture and receipt | exact fixture identities/redistribution; lock-derived constraints; canonical wheelhouse; installed PyAV/FFmpeg inventory/direct evidence; non-redistribution literals; target-executable probe; controlled allocator/supervisor proof | missing/extra/substituted wheel; fixture ambiguity; omitted literals; target identity drift; failed footprint sampling, signaling, wait, or cleanup |
| PR B domain and adapters | closed DTO/wire schemas; descriptor-bound snapshot; pure profile normalization; supervised inspection/transcription children; SQLite media authority | symlink and parent retarget; same-inode mutation; size/duration/profile limits; child crash/footprint budget/timeout; sampling or cleanup failure; video regression |
| PR C application and interfaces | canonical dispatcher; Run/Publication atomicity; CLI/MCP schemas; Search/Ask/EvidenceRef; v1 compatibility; reconciled v2 consumer | busy-before-model; sidecar owner rejection; malformed child output; v1 mixed-Library omission; request-time controls; error leakage |
| Required CI | model-free proof; fake provider; full pytest/Ruff/Pyright/build; canonical validators when identity actually changes | network resolver use; cache mutation; overclaiming docs; evaluation semantic drift |
| Terminal proof | same fresh wheel on Python 3.12/3.13; accepted receipt digest; installed packages; prepared model tree; three formats; CLI/MCP/Search/Ask/export consumer; network denial | empty cache; wrong receipt/wheel/model/fixture digest; partial Publication; cleanup failure; any post-proof tracked write |

Exact 15-minute and 100-MiB artifacts are generated once per model-free test session and reused.
The only real-provider execution is the final authorized terminal proof.

### Failure-Mode Registry

| Failure mode | Closed authority |
|---|---|
| Missing fixture redistribution, local wheel/runtime inventory, target identity, or Darwin arm64 supervisor proof | PR A no-go; PR B cannot begin |
| Transitive external-binary redistribution clearance is unresolved while binaries are not distributed | Record `external_binary_redistribution=not_performed` and `redistribution_authority=not_claimed`; do not block local-use feasibility; require separate legal review before future bundling/distribution |
| Parent symlink retarget or final-component symlink | containment-validated resolved target plus descriptor identity; cross-media regressions |
| Same-inode, same-size mutation | second descriptor digest plus device/inode/mode/size/mtime/ctime equality |
| Native parser footprint/crash/ordinary-descendant leak | stable leader identity and leader-only non-aggregate `ri_phys_footprint` polling; transient overshoot observation; ordinary-cooperative-descendant process-group signaling/`SIGTERM`/grace/`SIGKILL`/wait and cleanup; fail-closed child/leader identity, leader sampling, and process-group signaling/wait/cleanup; bounded output/time and owner-survival tests; `hard_kernel_enforced=false`; no `setsid`/`setpgid` escape claim |
| Busy owner still constructs model | lightweight no-model preflight, admission first, zero model-factory calls |
| Partial or invalid transcript becomes searchable | validate before persistence; atomic Publication switch; failed Run isolation |
| Mixed Library silently loses audio under v1 | default/explicit v1 fail closed; explicit reconciled v2 is complete |
| Downstream assumptions freeze v2 prematurely | accepted LLM Wiki evidence and bounded reconciliation before PR C implementation |
| Proof failure is unactionable or leaks internals | closed failure-code/next-step mapping and unknown-exception redaction |
| Review record does not match reviewed candidate | candidate committed before review; mechanical read-back; substantive mismatch restarts review |
| Repeated assurance loop | reassess blocker status after two or three evidence-backed repair attempts |

### Developer Journey Map

1. Run `UV_OFFLINE=1 uv run mke proof direct-audio --json` to verify deterministic product wiring
   without a model or download.
2. If real ASR is required and separately authorized, prepare the exact model revision once.
3. Run read-only doctor and require the owner to report ready.
4. Ingest a bounded excerpt such as `interview-excerpt.m4a` through Python, CLI, or unchanged
   path-only stdio MCP.
5. Search and Ask against timestamp `mke.evidence_ref.v1`.
6. Export the complete mixed Library explicitly as v2 and run the distinct v2 consumer.
7. Use the closed recovery table for any failure; restart MCP only when owner startup configuration
   changes.

### Developer Empathy And Time-To-Hello-World

The first-success path separates deterministic product wiring from model readiness, so a developer
can diagnose contracts before handling a large local model. The planning target is one offline
command for the deterministic proof and no more than ten minutes after dependencies are already
present; the real ready-owner-to-first-Evidence target is no more than fifteen minutes after the
exact model is prepared. These are onboarding targets, not measured SLA claims. PR C records the
actual command count and elapsed time as diagnostics only.

| DX dimension | Review result |
|---|---:|
| Getting started | 4.8/5 |
| API clarity | 4.8/5 |
| Error actionability | 4.8/5 |
| Documentation completeness | 4.8/5 |
| Test discoverability | 4.8/5 |
| Operational safety | 5.0/5 |
| Compatibility/migration clarity | 4.8/5 |
| Review and release sequencing | 4.8/5 |

DX implementation checklist:

- [ ] Lead public onboarding with the model-free proof, then the real-input sequence.
- [ ] Keep tested Python, CLI, and stdio MCP examples copy-ready and contract-accurate.
- [ ] Freeze every public problem and proof failure to one bounded recovery action.
- [ ] Publish the explicit v1-to-v2 migration and rollback table.
- [ ] Record first-Evidence diagnostics only from terminal proof; make no SLA claim.
- [ ] Commit the reviewed candidate before whole-branch review and persist only the returned result.

### Decision Audit Trail

| # | Accepted decision | Rationale | Plan location |
|---:|---|---|---|
| 1 | Use voice notes and bounded clips/excerpts in claims | Prevent full-length use-case overstatement | Goal, docs tests, claim boundary |
| 2 | Split delivery into PR A, PR B, PR C, then release closeout | Make license, internal foundation, public activation, and release independently gated | Global Constraints, Delivery Order |
| 3 | Make PR A a hard fixture/local-use/supervisor gate while external binaries remain undistributed | Native feasibility and fixture rights must precede runtime work without claiming transitive redistribution clearance | Task 1 |
| 4 | Bind PR A to external inputs rather than MKE commits | Avoid circular receipt refresh after normal source/docs changes | Task 1, Task 9 |
| 5 | Reconcile Export v2 only after downstream v1 evidence | Preserve v1 compatibility and prevent speculative v2 freeze | Task 7 entry gate |
| 6 | Put PyAV parsing under the Darwin arm64 polling supervisor | Bound observed supervisory-leader footprint/time/output and clean ordinary cooperative descendants without claiming hard-kernel, escaped-descendant, or sandbox enforcement | Tasks 3-4 |
| 7 | Add exact constraints and canonical wheelhouse lineage | Make ordinary-pip and receipt reproduction deterministic | Task 1 |
| 8 | Add no-write input preflight to PR A tooling | Expose missing/substituted inputs before acquisition authority | Task 1 |
| 9 | Perform lightweight preflight and admission before model work | Busy or invalid requests must have zero model cost | Tasks 4-5 |
| 10 | Preserve unresolved path spelling through symlink rejection | Keep public path semantics while proving resolved containment | Tasks 3, 6 |
| 11 | Rehash the still-open descriptor and compare file timestamps | Close same-inode, same-size mutation gaps | Task 3 |
| 12 | Reuse existing validation/admission authorities | Avoid competing runtime gates and duplicated behavior | Tasks 3-5 |
| 13 | Freeze closed pre-Run and proof error maps | Keep CLI/MCP failures actionable and non-leaking | Tasks 6, 8, 10 |
| 14 | Generate exact-bound test media once per session | Preserve limit proof without an expensive repeated-fixture loop | Task 8 |
| 15 | Lead onboarding with model-free proof | Shorten contract diagnosis before model readiness | User Journey, Tasks 8, 10 |
| 16 | Add tested Python/CLI/MCP examples and migration table | Make all entry surfaces and v1/v2 operator choices explicit | Task 10 |
| 17 | Run one real-ASR proof only at terminal candidate identity | Preserve truth while avoiding repeated release-grade gates | Task 9, Task 10 |
| 18 | Commit candidate before review and result after review | Bind findings to an exact HEAD without post-proof writes | Task 10 Steps 6-10 |
| 19 | Resolve wheelhouse authority per Python/platform cell | Permit disjoint tagged wheels and universal reuse without ambiguous compatibility | Task 1 Steps 5-6 |
| 20 | Make nested pip self-contained and offline | Outer `UV_OFFLINE` cannot constrain ordinary pip subprocesses | Task 1 Step 5, Task 9 Steps 1-4 |
| 21 | Invoke acquisition preflight with a direct stdlib-only controller and fixed bounded target probe | Prevent `uv run`, pip, install, environment, or cache activity while binding target executable identity before/after execution | Task 1 Step 6 |
| 22 | Freeze external-binary non-redistribution literals | Separate local optional-dependency feasibility from any future binary bundling/legal review | Task 1 Steps 5-7 |
| 23 | Prove Darwin arm64 polling supervision in PR A and integrate it in PR B | Make polling/overshoot/termination semantics explicit and fail closed without a sandbox claim | Task 1 and Task 4 |

### Implementation Tasks Aggregated From Review

No additional review tasks remain. All accepted durable amendments are integrated into the staged
task checklists above.

### Remaining Prerequisites And Boundaries

- PR A requires a separate dispatch and any package, wheel, fixture-generation, or model acquisition
  requires separate authority.
- PR B cannot begin until PR A is accepted and merged.
- PR C cannot begin until PR A, PR B, and the independent LLM Wiki compatibility docs/evidence PR
  are accepted and merged. No expected downstream compatibility result is recorded as fact.
- The exact Export v2 shape remains intentionally unfrozen until the PR C reconciliation checkpoint.
- No implementation, push, PR, merge, release, model proof, or external side effect is authorized by
  this review.

NO UNRESOLVED DECISIONS
