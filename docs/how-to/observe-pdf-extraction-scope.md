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
