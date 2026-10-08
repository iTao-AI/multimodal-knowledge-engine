# Run The Installed Single-Source Evidence Proof

Use this provider-free proof to test single-Source CLI Ask and the official MCP SDK consumer
from one installed wheel on Python 3.12 and 3.13. It builds the selected clean commit once,
installs that wheel into two fresh environments and creates a fresh synthetic Library in each.
It uses the explicit existing `current` retrieval strategy and fifteen MCP tools.

## Run Once From A Clean Checkout

Prepare the existing locked development runtime, Git, uv and already installed Python 3.12/3.13.
Core dependency artifacts and the build backend must be present in the uv cache. The controller
does not download a runtime or dependency, change the lock, or install into a shared environment.

From the repository root, use its full clean `HEAD` and a new external directory whose parent
already exists:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --locked --offline --no-sync \
  python -m scripts.source_evidence_wheel_proof \
  --source-commit <FULL_CLEAN_HEAD_SHA> \
  --python /ABSOLUTE/PATH/TO/EXISTING/python3.12 \
  --python /ABSOLUTE/PATH/TO/EXISTING/python3.13 \
  --work-dir /ABSOLUTE/EXTERNAL/PATH/TO/NEW/source-evidence-wheel-proof
```

The controller requires a POSIX host. It rejects a dirty or different `HEAD`, reused directories,
repository directories and repository aliases before creating an environment. Dependencies are
exported from the unchanged lock and installed offline with `--require-hashes`; the wheel is
installed with `--no-deps`. A missing cached artifact is an environment failure. If separate
dependency preparation is authorized, use the existing
[hash-checked cache preparation route](./observe-pdf-extraction-scope.md#installed-wheel-follow-up)
with the original lock and an owned environment. Record its network use separately.

## What The Consumers Verify

The separately named `tests/fixtures/source-evidence-installed-v1/` pack contains three selected
PDF text pages (`needle café selected page N`) and five unrelated pages (`needle outsideonly
page N`). Its manifest binds exact PDF bytes and SHA-256. The generator is
`scripts/generate_source_evidence_installed_fixtures.py`; it writes only a new output directory.
Historical fixtures and source-pack/C1 receipt schemas are unchanged.

Each external consumer runs with isolated Python (`-I -B`), cleared inherited Python import state
and copied scripts/assets from the same Git commit. The controller checks every installed MKE
module byte, console entry point, interpreter, dependency version and local-wheel origin, then
rechecks installation identity and copied bytes after the cases. CLI and SDK use the installed
console script; repository source is never their import path.

The official SDK discovers the active pair explicitly. CLI Ask must equal the complete native SDK
first-page matches, including excerpts and read descriptors. SDK reads verify each Source, Publication, revision,
Run, fingerprint and locator. Complete stored UTF-8 reads use four-byte chunk budgets and
independent byte counts, SHA-256 and excerpt windows. The controller also checks the three
complete references against the declared page text's independently computed lengths and digests.

| Case | Required result |
|---|---|
| Selected query, limit 1 | One verified reference and `more_available`; no Ask cursor. |
| Selected query, limit 3 | All three selected references and `complete`. |
| Selected `outsideonly` query | `insufficient_evidence`, empty/complete selection, despite real unrelated matches. |
| Other Source's Publication | SDK and CLI reject the mismatched pair. |
| Republished selected Source | SDK and CLI reject the stale Publication; no automatic reselection. |
| Replacement during reads | After one complete verified reference, a native read fails; the consumer discards the whole result. |
| Controlled read corruption | After one verified reference, the harness changes a native payload's text; exact verification rejects it without partial success. |

The last case deliberately injects corruption in the consumer boundary. It does not claim the
native server ordinarily emits corrupted text. Negative cases run in separate processes and
must exit 1 with exactly one redacted failure object. A successful verified prefix is never
printed as a successful receipt.

## Completion, Diagnostics And Cleanup

Stdout is one `mke.source_evidence_wheel_proof.v1` JSON object, at most 32,768 canonical bytes.
Exit 0 and `status="passed"` require both runtime cases and all negative boundaries. The receipt
records the exact source commit, same wheel SHA-256, lock/requirements hashes, actual Python and
dependency versions, copied asset hashes, full positive lineage and verified reference lengths.

The new external directory retains `wheel/`, `proof.json` and private `commands.jsonl` diagnostics.
Successful temporary source/build/environment/consumer data are removed before the success
receipt is published. Cleanup failure cannot count as success. A failed attempt retains its
owned temporary state and bounded diagnostics for classification; `proof.json` is published
only after acceptance and cleanup. Do not combine partial results from different attempts.
The controller does not retry automatically.

Failed consumers retain `data/diagnostics/cli.jsonl`, bounded `sdk-*.stderr.log` files and
`failure.json` with the workflow phase and bounded exception traceback. Command timeout/overflow
also retains its already captured stream prefixes. These are private diagnostics, never public
stdout or a partial successful receipt. The shared bounded helper's optional exception fields
carry those prefixes without changing historical source-pack output schemas or failure codes.

Build, install and consumer command streams are drained with 2 MiB caps per stream and a
180-second deadline. Consumers have a 90-second workflow deadline, CLI/tool/startup calls have
15-second deadlines, and SDK server stderr has a 64 KiB cap. Parsed SDK packets retain the
existing canonical/SDK envelope checks; raw stdout framing remains the official SDK's boundary.
Timeout/overflow ends the owned command process group; ordinary SDK exit closes its server.
These are process and protocol bounds, not an OS sandbox.

The controller composes the existing source-pack snapshot/process helpers and C1 installation
validators. Focused checks are `tests/scripts/test_source_evidence_installed_consumer.py`,
`tests/scripts/test_source_evidence_wheel_proof.py` and their existing helper regressions.
The ordinary checkout evidence remains documented in [Ask Within One Active Source](./ask-within-one-source.md).

Native installed acceptance is pending for this follow-up. A successful build or checkout test
alone does not establish it. This route proves bounded synthetic Evidence consumption; it does
not establish a Release, cold-machine cache provisioning, semantic answers, original-media
completeness, OCR/ASR quality or production adoption.
