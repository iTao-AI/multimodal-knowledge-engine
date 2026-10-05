# Observe PDF Extraction Scope

Use this provider-free current-checkout proof to verify a PDF's local text/displayed-raster
observations across actual CLI, stdio MCP, Export v3 and the offline Viewer. Use an existing locked
environment containing MKE, PyMuPDF and the official MCP SDK. The script installs nothing and
downloads no model or dependency. From the repository root:

```bash
UV_OFFLINE=1 .venv/bin/python -I -B scripts/pdf_extraction_observation_consumer.py \
  --mke-bin /ABSOLUTE/PATH/TO/EXISTING/mke \
  --work-dir /ABSOLUTE/PATH/TO/NEW/pdf-observation-example \
  --expectation tests/fixtures/pdf-extraction-observation-v1/mcp-tool-schemas.json
```

The new `--work-dir` is retained for inspection: generated public synthetic PDF, SQLite Library,
`compiled-v3/` and `viewer.html`. Use a fresh directory for another run. No original private
material, credentials or provider service is used. The script imports no MKE implementation,
test helper or storage module; native public results are its identity/content authority.

## Declared Input And Checks

The six pages deliberately contain:

| Page | Input | Expected local signal |
|---|---|---|
| 1 | Ordinary PDF text | Text only |
| 2 | Sixty accented text lines plus a raster figure with `RASTER ONLY: value = 37` | Mixed text/raster |
| 3 | Text plus a tiny decorative raster | Mixed text/raster |
| 4 | The raster figure without a PDF text layer | Raster only |
| 5 | No text or drawing | Neither signal |
| 6 | A vector rectangle without text or raster | Neither signal; vectors are not assessed |

The resulting partition is 6 total / 1 text-only / 2 mixed / 1 raster-only / 2 neither.
The old suspected-scan count stays 1 because it only considers empty-text pages. Stored Evidence
exists for pages 1–3. The image-only value is absent from their text; the proof runs no OCR or
image understanding and assigns no semantic completeness score.

The consumer performs real CLI ingest, opt-in CLI list/browse, and official MCP SDK initialize,
`tools/list`, `list_sources_v2`, `browse_source_evidence_v2` with page-size-1 continuation, and
`read_evidence_v1`. It checks the exact fourteen-tool fixture. It compares legacy v1 entries with
v2 entries, verifies complete known UTF-8 text through multiple 97-byte exact-read chunks and
checks every Source/Publication/revision/Run/fingerprint/locator descriptor and final digest.
It also exercises the actual CLI exact-read route.

Actual `library export --format-version v3` is then validated by the independent stdlib consumer.
Export Source/Run identity, observation object, Evidence IDs/locators/text bytes match the native
results. The actual Viewer builder validates the export and publishes HTML; its embedded payload
is checked against that same validated snapshot. This payload check is separate from interactive
browser/clipboard verification. Every MCP result also checks structured/compatibility-text equality,
canonical response ≤32,768 bytes and full SDK result <96 KiB.

Stdout is one public-safe `mke.pdf_extraction_observation_consumer.v1` receipt. It includes synthetic
identity, observations, counts and measured maximum response sizes, with no paths, cursors or raw
Evidence text. `status="passed"` means this bounded native synthetic route passed. Failure is
a bounded code and nonzero exit. It does not prove production adoption, retrieval quality,
original-media completeness, OCR quality or a new installed-wheel/dual-Python release result.

## Installed-Wheel Follow-Up

`scripts/pdf_extraction_observation_wheel_proof.py` adds an explicit installation boundary to the
same synthetic route. Supply one wheel built from a clean exact merge snapshot, its full Git SHA,
two already installed Python 3.12/3.13 interpreters, and a new external work directory. For example,
prepare the source snapshot and wheel without moving the current checkout:

```bash
mkdir -p artifacts
git archive --format=tar --output artifacts/pdf-wheel-source.tar <FULL_MERGE_SHA>
mkdir artifacts/pdf-wheel-source
tar -xf artifacts/pdf-wheel-source.tar -C artifacts/pdf-wheel-source
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv --directory artifacts/pdf-wheel-source \
  build --wheel --out-dir ../pdf-wheel-build
```

The archive/build paths must be new task-owned locations. Then use an existing compatible
controller Python; it needs only stdlib:

```bash
python -I -B scripts/pdf_extraction_observation_wheel_proof.py \
  --wheel artifacts/pdf-wheel-build/multimodal_knowledge_engine-0.1.7-py3-none-any.whl \
  --source-commit <FULL_MERGE_SHA> \
  --python /ABSOLUTE/PATH/TO/EXISTING/python3.12 \
  --python /ABSOLUTE/PATH/TO/EXISTING/python3.13 \
  --work-dir /ABSOLUTE/EXTERNAL/PATH/TO/NEW/pdf-wheel-proof
```

The controller runs on a POSIX host with existing uv/Git and runtime paths. It verifies all package
files against the selected Git commit, restricts other wheel members to canonical distribution
metadata and binds console entry points to the committed `pyproject.toml`. Extra modules, startup
`.pth` files and `.data` script payloads fail before installation. It requires unchanged
`pyproject.toml`/`uv.lock`, exports only
locked core requirements, and hash-checks their offline installation into two fresh environments.
It installs the supplied wheel with `--no-deps`, removes inherited Python import state and probes
isolated site-packages/interpreter/versions/package bytes. Copied standalone consumers and the exact
current fourteen-tool fixture come from the same Git commit; product source is not copied into
the environments or added to `PYTHONPATH`.

A cold cache can fail before ingestion. When necessary dependency setup is authorized, prepare
missing artifacts with the same exported/hash-checked core requirements in a task-owned environment.
Record that preparation's network use separately; start the complete offline proof with a new
environment/store. Do not install a new runtime or change the lock to make the check pass.
For each existing interpreter whose cache is incomplete, the preparation route is:

```bash
uv export --locked --no-dev --no-emit-project --no-header \
  > /ABSOLUTE/PATH/TO/NEW/TASK/locked-core-requirements.txt
UV_PYTHON_DOWNLOADS=never uv venv --python /ABSOLUTE/PATH/TO/EXISTING/python3.12 \
  /ABSOLUTE/PATH/TO/NEW/TASK/cache-preparation
UV_PYTHON_DOWNLOADS=never uv pip sync --require-hashes \
  --python /ABSOLUTE/PATH/TO/NEW/TASK/cache-preparation/bin/python \
  /ABSOLUTE/PATH/TO/NEW/TASK/locked-core-requirements.txt
uv pip check --python /ABSOLUTE/PATH/TO/NEW/TASK/cache-preparation/bin/python
```

The task directory must already exist. Dependency preparation may use network; the complete proof
uses new environments and requires offline installation. This temporary preparation environment
never counts as native consumer acceptance.

Installer `direct_url.json` binds the selected local wheel. Its archive hashes are optional under
the [PyPA direct URL specification](https://packaging.python.org/en/latest/specifications/direct-url-data-structure/#archive-urls).
Present SHA-256 values must match; an absent recorded hash stays null. The supplied wheel hash,
commit/package byte equality, selected origin and final input hash recheck remain mandatory. A
version string or successful build alone does not establish an installed consumer result.

The actual route runs separate installed CLI and official-SDK stdio MCP processes, the independent
stdlib Export v3 validator and Viewer builder. Malformed export and unknown-Source CLI calls must
return bounded failure and exit 1. Stdout is `mke.pdf_extraction_observation_wheel_proof.v1`; exit 0
and `status="passed"` require both runtime cases, fourteen tools, exact UTF-8/citation identity and
failure exits. The receipt captures source/wheel/lock/fixture/tool-schema digests, actual Python and
dependency versions, native Source/Run/Publication identity and measured response sizes. Private
per-command diagnostics and all synthetic artifacts remain in the new external directory. Reused
work directories fail without overwriting evidence; a timed-out command terminates its own POSIX
process group.

On 2026-10-06 fresh installation preflights passed on Python 3.12.13 and 3.13.13. The resumed
complete run passed the 3.12 native and independent Export v3 consumers, then failed in the
controller's negative-fixture setup before the 3.13 case. The setup now uses the public
`export-manifest.json` filename; its regression and actual targeted malformed-export/unknown-Source
exit checks pass. The controller has 39 passing regression tests, but no complete dual-runtime
success receipt is claimed. The full run awaits a coordinating route decision; all three failed
attempts are retained. See the [bounded review](../superpowers/reviews/2026-10-06-pdf-installed-wheel-consumer-review.md)
for source/wheel binding, actual evidence and remaining acceptance.
This entry does not claim a stable release, original-media completeness, OCR/model quality, or
interactive file-origin/clipboard verification.

## Manual Use And Limits

For an existing Library, choose a Source/Publication from:

```bash
mke --db <library.sqlite> sources list --contract-version v2 --json
mke --db <library.sqlite> source browse <source_id> --publication-id <publication_id> \
  --contract-version v2 --page-start 2 --page-end 4 --json
```

Catalog returns whole-document aggregates without per-page details. Browse returns at most 256
contiguous observations starting at the requested page or page 1. Returned/omitted ranges disclose
all unreturned page details; Evidence pagination remains a separate boundary. Export v3 uses
pages 1–256. Missing older observations are `not_observed` with null counts and empty arrays.
Decorative images count as present; vectors, image meaning and importance are not assessed.

Open the generated HTML with the [offline Viewer workflow](./view-compiled-library.md). A returned
mixed page tells the reader that only the text layer was extracted and image questions require
checking the original page. The original PDF is not bundled. Unknown and omitted observations
have separate notices. For contract fields and rollback, see
[MCP Reference](../reference/mcp-contract.md), [Export Guide](./export-compiled-library.md) and
[ADR-0015](../decisions/0015-pdf-extraction-observations.md).
