# Real Local Transcription Deployment Proof And Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the D3-B runtime with one redistribution-safe spoken MP4, a cache-only real transcription proof, and an isolated wheel-installed CLI plus stdio MCP deployment proof, then publish only verified platform evidence.

**Architecture:** Keep required tests model-free by injecting fake resolver/model boundaries. Run real ASR only through explicit opt-in commands against an already prepared exact model revision, and run the deployment proof in a temporary environment outside the repository with lock-derived constraints and a real MCP SDK client.

**Tech Stack:** Python 3.12/3.13, faster-whisper, PyAV, MCP Python SDK, uv, pytest, ffmpeg for fixture generation only, GStack document-release and review.

---

## Prerequisites And PR Boundary

- Start only after the runtime/interfaces PR is merged.
- Sync latest `main`, create an isolated worktree, and use branch `codex/transcription-deployment-proof`.
- Read the approved D3-B design, Autoplan review, and both completed implementation plans.
- Real model acquisition is a large network side effect. Stop before the first
  `mke transcription prepare --allow-model-download` run, report the model/revision/cache policy,
  and obtain explicit user authorization.
- Do not add HTTP, remote ASR, AutoDL, vendor APIs, queue workers, long-video support, audio-only
  ingest, diarization, GPU scheduling, or quality benchmarking.
- Do not turn one observed transcript or duration into a quality or performance claim.

## File Structure

### Create

- `tests/fixtures/video/spoken-evidence.mp4`: short synthetic spoken MP4 without a sidecar.
- `src/mke/proof/transcription.py`: cache-only real transcription proof runner and report.
- `src/mke/proof/mcp_deployment_client.py`: installed-package stdio MCP SDK client.
- `scripts/transcription_deployment_proof.py`: isolated wheel build/install/CLI/MCP orchestrator.
- `tests/proof/test_transcription_proof.py`: model-free proof behavior and redaction.
- `tests/proof/test_mcp_deployment_client.py`: SDK call sequence and report comparison.
- `tests/scripts/test_transcription_deployment_proof.py`: subprocess plan, constraints, temp
  isolation, and failure handling.

### Modify

- `tests/fixtures/video/README.md`: text, synthetic voice source, regeneration, license, checksum.
- `src/mke/proof/__init__.py`: proof exports.
- `src/mke/cli.py`: `proof transcription-run`.
- `tests/interfaces/test_cli_proof.py`: real-proof CLI JSON/human/error contract.
- `tests/proof/test_runner.py`: deterministic product proof remains independent.
- `README.md` and `README_CN.md`: verified real-transcription and deployment proof.
- `docs/README.md`: new guide and milestone navigation.
- `docs/explanation/architecture.md`: verified first-party runtime flow.
- `docs/reference/cli.md`: real-proof command and exit behavior.
- `docs/reference/contracts.md`: proof report fields and platform evidence boundary.
- `docs/how-to/run-local-product-proof.md`: deterministic versus opt-in real proof.
- `docs/how-to/use-mke-mcp.md`: wheel-installed stdio MCP proof.
- `docs/how-to/use-local-transcription.md`: fixture, preparation, proof, and recovery.
- `docs/tutorials/getting-started.md`: optional path after deterministic proof.
- `docs/decisions/0006-first-party-local-transcription-runtime.md`: implementation status and
  verified environment, without changing the decision.
- `.github/workflows/ci.yml`: fixture/package checks only; no model execution.

## Task 1: Add A Redistribution-Safe Spoken Fixture

**Files:**
- Create: `tests/fixtures/video/spoken-evidence.mp4`
- Modify: `tests/fixtures/video/README.md`
- Modify: `tests/conftest.py`
- Create: `tests/adapters/test_spoken_video_fixture.py`

- [ ] **Step 1: Define the repository-authored spoken text**

Use this short sentence so the proof has one stable keyword without asserting an exact full
transcript:

```text
Evidence remains traceable after publication.
```

The voice must be synthetic, not a personal recording or private source. Before generating or
committing the fixture, record a primary-source license or terms link that explicitly permits
redistribution of the generated audio. A synthesizer's software license alone is not evidence that
its bundled voice output can be redistributed.

- [ ] **Step 2: Generate the fixture outside the repository and then copy only the MP4**

The following macOS command is only a local prototype. Do not use its output as the committed
fixture unless Apple voice-output redistribution terms are found and recorded:

```bash
tmp_dir="$(mktemp -d)"
say -v Samantha -o "$tmp_dir/spoken-evidence.aiff" "Evidence remains traceable after publication."
ffmpeg -y -f lavfi -i color=c=black:s=160x90:d=4.0 \
  -i "$tmp_dir/spoken-evidence.aiff" \
  -c:v libx264 -pix_fmt yuv420p -preset ultrafast -tune stillimage \
  -c:a aac -b:a 64k -shortest -movflags +faststart \
  tests/fixtures/video/spoken-evidence.mp4
```

Do not commit the temporary AIFF. If the selected synthetic voice changes, regenerate and rerun the
real proof before accepting the fixture.

- [ ] **Step 3: Record provenance and checksum**

Add to the fixture README:

- repository-authored text;
- synthesizer and voice identifier;
- primary-source generated-output or source-recording license URL;
- the exact redistribution basis for the committed audio;
- no personal/private source audio;
- MP4/H.264/AAC profile;
- exact generation command;
- `shasum -a 256 tests/fixtures/video/spoken-evidence.mp4` result;
- fixture byte size and duration;
- no transcript sidecar;
- no exact cross-runtime transcript assertion;
- repository fixture policy, without relicensing third-party source audio.

- [ ] **Step 4: Write and run model-free fixture tests**

Use the optional PyAV package in the extra-enabled test environment to assert container, codecs,
audio presence, positive duration, short-video limits, checksum, and absence of
`spoken-evidence.mp4.mke-transcript.json`.

The test module must not import `av` at module import time. Inside the media-profile test, check
`importlib.util.find_spec("av")`: skip only when the extra is absent and
`MKE_REQUIRE_TRANSCRIPTION_EXTRA` is unset; fail when that environment variable is `1` but PyAV is
missing. Add a dedicated extra-enabled CI step with
`MKE_REQUIRE_TRANSCRIPTION_EXTRA=1` so the media-profile assertion cannot silently skip.

```bash
uv sync --locked --extra transcription
uv run pytest tests/adapters/test_spoken_video_fixture.py -q
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/video/spoken-evidence.mp4 tests/fixtures/video/README.md tests/conftest.py tests/adapters/test_spoken_video_fixture.py
git commit -m "test(video): add spoken transcription fixture"
```

## Task 2: Add The Cache-Only Real Transcription Proof

**Files:**
- Create: `src/mke/proof/transcription.py`
- Modify: `src/mke/proof/__init__.py`
- Modify: `src/mke/cli.py`
- Create: `tests/proof/test_transcription_proof.py`
- Modify: `tests/interfaces/test_cli_proof.py`
- Modify: `tests/proof/test_runner.py`

- [ ] **Step 1: Write failing proof tests with fake real-provider output**

Cover:

- temporary SQLite workspace;
- faster-whisper runtime selected explicitly;
- proof never enables model download;
- published Run and successful transcript report;
- non-empty ordered timestamp Evidence;
- Search for `evidence`;
- evidence-only Ask result;
- one-object JSON and sanitized human output;
- actual non-sensitive runtime profile and library versions;
- no database or cache copy left in the repository;
- cache miss is a stable failed proof, not a traceback;
- `mke proof run` and `mke demo --verify` never invoke this proof.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/proof/test_transcription_proof.py tests/interfaces/test_cli_proof.py tests/proof/test_runner.py -q
```

- [ ] **Step 3: Define a dedicated proof report**

```python
@dataclass(frozen=True)
class TranscriptionProofReport:
    status: Literal["passed", "failed"]
    run_state: str
    evidence_count: int
    timestamp_evidence: bool
    search_keyword_matched: bool
    ask_status: str
    transcript_intake_report: TranscriptIntakeReport | None
    environment: ProofEnvironment | None
    duration_ms: int
    reason: str | None = None
```

The environment contains only Python, OS, architecture, faster-whisper, CTranslate2, and PyAV
versions. It contains no paths, hostnames, usernames, cache locations, argv, endpoints, or secrets.

- [ ] **Step 4: Implement the cache-only runner**

```python
def run_transcription_proof(
    fixture: Path,
    transcription: FasterWhisperTranscriptionConfig,
) -> TranscriptionProofReport:
    with tempfile.TemporaryDirectory(prefix="mke-transcription-proof-") as temp_dir:
        runtime = RuntimeConfig(
            db_path=Path(temp_dir) / "proof.sqlite",
            transcription=transcription,
        )
        engine = build_engine(runtime)
        try:
            result = engine.ingest_video(fixture)
            matches = engine.search("evidence")
            answer = engine.ask("evidence publication")
            return validate_transcription_proof(result, matches, answer)
        finally:
            engine.close()
```

Do not call `prepare_model()`. Validate only invariants, stable keyword presence, and report
consistency; do not assert the exact complete transcript.

- [ ] **Step 5: Add the CLI command**

```text
mke proof transcription-run
  --fixture tests/fixtures/video/spoken-evidence.mp4
  [trusted faster-whisper runtime flags]
  [--json]
```

JSON writes one object to stdout. Human output must remain sanitized. Exit 0 on passed proof, 1 on
failed proof, 2 on usage.

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/proof/test_transcription_proof.py tests/interfaces/test_cli_proof.py tests/proof/test_runner.py -q
uv run ruff check src/mke/proof src/mke/cli.py tests/proof tests/interfaces/test_cli_proof.py
uv run pyright
```

```bash
git add src/mke/proof/transcription.py src/mke/proof/__init__.py src/mke/cli.py tests/proof/test_transcription_proof.py tests/interfaces/test_cli_proof.py tests/proof/test_runner.py
git commit -m "feat(proof): add real transcription proof"
```

## Task 3: Add An Isolated Wheel-Installed CLI And MCP Proof

**Files:**
- Create: `src/mke/proof/mcp_deployment_client.py`
- Create: `scripts/transcription_deployment_proof.py`
- Create: `tests/proof/test_mcp_deployment_client.py`
- Create: `tests/scripts/test_transcription_deployment_proof.py`

- [ ] **Step 1: Write failing orchestration tests**

Mock subprocesses and assert this exact order:

1. `uv build`;
2. lock-derived constraints export;
3. temporary environment outside the repository;
4. install built `wheel[transcription]` under constraints;
5. installed `mke transcription doctor --json`;
6. optional explicit preparation only when the script received `--allow-model-download`;
7. installed CLI ingest, run get, search, and ask;
8. installed Python invokes the MCP SDK client;
9. client calls `ingest_file`, `get_run`, `search_library`, and `ask_library`;
10. compare CLI and MCP report identity fields;
11. clean temporary DB/environment and emit one redacted JSON result.

Also assert every subprocess has a timeout and bounded captured output.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/proof/test_mcp_deployment_client.py tests/scripts/test_transcription_deployment_proof.py -q
```

- [ ] **Step 3: Implement the installed-package MCP SDK client**

Use the SDK, not hand-written JSON-RPC:

```python
async def run_mcp_flow(
    server: StdioServerParameters,
    fixture_name: str,
) -> dict[str, object]:
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert_public_tool_schemas(tools)
            ingest = await session.call_tool("ingest_file", {"path": fixture_name})
            run_id = extract_run_id(ingest)
            inspected = await session.call_tool("get_run", {"run_id": run_id})
            searched = await session.call_tool(
                "search_library", {"query": "evidence", "limit": 5}
            )
            asked = await session.call_tool(
                "ask_library", {"question": "evidence publication", "limit": 5}
            )
            return validate_mcp_flow(ingest, inspected, searched, asked)
```

The client timeout must be at least the configured provider timeout. Tool schemas must not expose
provider/model/revision/cache/argv/download controls.

- [ ] **Step 4: Implement the deployment orchestrator**

The script accepts trusted operator inputs:

```text
--fixture
--model-cache
--python 3.12|3.13
--allow-model-download
--json
```

It must:

- resolve the repository root only for build input;
- create all runtime state under a temporary directory outside the repository;
- export requirements from `uv.lock` with `--locked --extra transcription --no-dev --no-emit-project`;
- install the built wheel with the transcription extra under those constraints;
- copy the spoken fixture into the temporary MCP allowed root;
- pass the exact same model profile to CLI and MCP owner startup;
- use `subprocess.Popen` or `subprocess.run` with `shell=False`, timeouts, and bounded output;
- redact all local paths from the final report;
- fail closed on any command or contract mismatch;
- never download unless `--allow-model-download` was supplied.

- [ ] **Step 5: Run model-free tests and commit**

```bash
uv run pytest tests/proof/test_mcp_deployment_client.py tests/scripts/test_transcription_deployment_proof.py -q
uv run ruff check src/mke/proof scripts tests/proof tests/scripts
uv run pyright
```

```bash
git add src/mke/proof/mcp_deployment_client.py scripts/transcription_deployment_proof.py tests/proof/test_mcp_deployment_client.py tests/scripts/test_transcription_deployment_proof.py
git commit -m "feat(proof): add wheel deployment proof"
```

## Task 4: Run The Authorized Real Proofs

**Files:**
- Modify: `docs/how-to/use-local-transcription.md`
- Modify: `docs/how-to/use-mke-mcp.md`
- Modify: `docs/how-to/run-local-product-proof.md`

- [ ] **Step 1: Stop for explicit model-download authorization**

Report:

- model: `Systran/faster-whisper-small`;
- revision: `536b0662742c02347bc0e980a01041f333bce120`;
- network download is opt-in;
- cache is outside the repository;
- normal ingest, proof, doctor, and MCP remain cache-only.

Do not run preparation until the user approves this side effect.

- [ ] **Step 2: Prepare and verify readiness**

After approval:

```bash
uv sync --locked --extra transcription
uv run mke transcription prepare --allow-model-download --json
uv run mke transcription doctor --json
```

Capture actual safe JSON, exit codes, Python version, OS, architecture, faster-whisper, CTranslate2,
and PyAV versions. Do not copy cache paths into docs.

- [ ] **Step 3: Run the cache-only real proof**

```bash
uv run mke proof transcription-run \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --json
```

Verify status passed, published Run, non-empty timestamp Evidence, keyword Search, evidence-only Ask,
and complete `transcript_intake_report`.

- [ ] **Step 4: Run the isolated wheel deployment proof**

Run the script first on the current verified Python version without download if the cache is
already prepared:

```bash
uv run python scripts/transcription_deployment_proof.py \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --python 3.12 \
  --json
```

If the cache is intentionally isolated and empty, rerun with `--allow-model-download` only under
the authorization from Step 1. The proof must pass real CLI and stdio MCP flows.

- [ ] **Step 5: Record only verified evidence**

Update docs with:

- exact tested OS, architecture, and Python;
- library versions;
- proof command and passed capabilities;
- observed duration labeled as one observation, not a performance guarantee;
- untested platforms explicitly unverified;
- no full generated transcript if it contains unstable variation.

- [ ] **Step 6: Commit evidence documentation**

```bash
git add docs/how-to/use-local-transcription.md docs/how-to/use-mke-mcp.md docs/how-to/run-local-product-proof.md
git commit -m "docs(proof): record verified transcription deployment"
```

## Task 5: Complete Required CI And Regression Coverage

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/proof/test_transcription_proof.py`
- Modify: `tests/scripts/test_transcription_deployment_proof.py`
- Modify: `tests/proof/test_runner.py`
- Modify: `tests/interfaces/test_cli_demo.py`

- [ ] **Step 1: Add model-free CI coverage**

CI may:

- verify the fixture checksum and media profile;
- install the wheel transcription extra on Python 3.12 and 3.13;
- run mocked proof/orchestrator tests;
- assert doctor cache-miss behavior.

CI must not:

- call preparation with download enabled;
- contact model hosting;
- execute real ASR;
- require a persisted model cache.

Run the fixture profile test explicitly after installing the transcription extra, and configure
the step with `MKE_REQUIRE_TRANSCRIPTION_EXTRA=1` so a missing PyAV dependency fails instead of
skipping. The earlier core-only `uv run pytest -q` must still collect the module successfully
without importing PyAV.

- [ ] **Step 2: Add the hostile cleanup regression**

Simulate an oversized malformed MP4, excessive stderr, cancellation, and a newer concurrent ingest.
Assert:

- bounded output;
- child termination;
- failed or superseded Run;
- previous active Search unchanged;
- no successful report;
- no path or stderr leak.

- [ ] **Step 3: Run complete model-free verification**

```bash
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check
```

Then repeat the wheel-extra import/doctor checks for local Python 3.12 and 3.13 where both interpreters
are available. Required GitHub CI remains the authoritative two-version result.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml tests/proof/test_transcription_proof.py tests/scripts/test_transcription_deployment_proof.py tests/proof/test_runner.py tests/interfaces/test_cli_demo.py
git commit -m "test(video): harden transcription deployment proof"
```

## Task 6: Finish Public Documentation

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/reference/contracts.md`
- Modify: `docs/how-to/run-local-product-proof.md`
- Modify: `docs/how-to/use-mke-mcp.md`
- Modify: `docs/how-to/use-local-transcription.md`
- Modify: `docs/tutorials/getting-started.md`
- Modify: `docs/decisions/0006-first-party-local-transcription-runtime.md`
- Modify: this plan

- [ ] **Step 1: Update capability and boundary statements**

State that MKE can ingest a short spoken MP4 through an opt-in local faster-whisper runtime and
expose timestamp Evidence through CLI and owner-configured stdio MCP. Keep these boundaries visible:

- core and deterministic proof remain model-free;
- real runtime requires the optional extra and prepared model;
- normal execution is cache-only;
- verified platform list is narrow and evidence-backed;
- HTTP, cloud, long-video, audio-only, quality benchmark, and UI remain deferred.

- [ ] **Step 2: Run document-release audit**

Run `gstack-document-release` because D3-B changes installation, CLI, MCP, architecture, proof,
dependencies, and operator workflows. Apply only findings supported by the final diff and actual
proof results.

- [ ] **Step 3: Check navigation and stale claims**

```bash
rg -n "fixture-only|sidecar-only|planned|not implemented|faster-whisper|transcription-run" README.md README_CN.md docs
rg -n "(/U[s]ers/|/p[r]ivate/|C[a]reer|求[职]|面[试])" README.md README_CN.md docs
```

Manually verify every relative link and command in the changed documents.

- [ ] **Step 4: Commit**

```bash
git add README.md README_CN.md docs/README.md docs/explanation/architecture.md docs/reference/cli.md docs/reference/contracts.md docs/how-to/run-local-product-proof.md docs/how-to/use-mke-mcp.md docs/how-to/use-local-transcription.md docs/tutorials/getting-started.md docs/decisions/0006-first-party-local-transcription-runtime.md docs/superpowers/plans/2026-06-18-real-local-transcription-deployment-proof-docs-implementation.md
git commit -m "docs(video): publish transcription proof workflow"
```

## Task 7: Final Review And PR Preparation

**Files:**
- Create: `docs/superpowers/reviews/2026-06-18-real-local-transcription-deployment-proof-review.md`
- Modify: this plan

- [ ] **Step 1: Run final verification from a clean worktree**

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
uv run mke proof transcription-run \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --json
uv run python scripts/transcription_deployment_proof.py \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --python 3.12 \
  --json
git diff --check
```

The two real-proof commands require the already authorized and prepared cache. Record actual
results; never substitute mocked results.

- [ ] **Step 2: Run a heavy pre-landing review**

Use `gstack-review` with emphasis on:

- proof authenticity;
- wheel isolation;
- MCP SDK use rather than direct contract calls;
- model download boundaries;
- subprocess limits and cancellation;
- public redaction;
- fixture provenance/license;
- CI model independence;
- unsupported platform claims.

Persist the public-neutral review, fix blockers, and rerun all affected checks.

- [ ] **Step 3: Mark the D3-B plans and design complete**

After all three PRs are merged and real proof evidence exists:

- mark all plan checklists complete;
- change the design stage to completed;
- retain all three plans as implementation history;
- do not rewrite the earlier Autoplan review.

- [ ] **Step 4: Prepare the Chinese PR body**

```markdown
## Summary

为短 spoken MP4 增加可重复的真实本地转录与 wheel-installed CLI/MCP 部署证明，并公开实际验证的平台边界。

## Completion

- [x] Redistribution-safe spoken fixture
- [x] Cache-only real transcription proof
- [x] Isolated wheel-installed CLI proof
- [x] Real stdio MCP SDK ingest/get/search/ask proof
- [x] Verified environment and public documentation

## Verification

List actual model-free and real-proof results separately.

## Scope

明确未包含 HTTP、remote ASR、AutoDL、vendor API、queue worker、long-video、audio-only、diarization、GPU scheduling 或 quality benchmark。

## Risk / Impact

- Real proof depends on a prepared exact model revision.
- Required CI remains model-free.
- Rollback is owner configuration back to sidecar.

## Documentation impact

Updated README, ADR status, architecture, CLI/contracts, tutorials, MCP guide, local transcription guide, fixture provenance, and proof guide.
```

- [ ] **Step 5: Commit final review metadata**

```bash
git add docs/superpowers/reviews/2026-06-18-real-local-transcription-deployment-proof-review.md docs/superpowers/plans/2026-06-18-real-local-transcription-deployment-proof-docs-implementation.md docs/superpowers/specs/2026-06-18-real-local-transcription-deployment-proof-design.md
git commit -m "docs(review): record transcription deployment review"
```

Do not push or create the PR until explicitly authorized.
