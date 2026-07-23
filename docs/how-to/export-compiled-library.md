# Export A Compiled Library

Use the read-only export command to create a portable snapshot of every active Publication in the
local Library:

```bash
mkdir -p .tmp/exports
cd .tmp/exports
uv run mke --db ../../.tmp/mke.sqlite library export --output compiled-library --json
```

`--output` is one new direct child of the current working directory. It must not exist, and the
command never overwrites it. On success, `compiled-library/` contains:

```text
export-manifest.json
sources/<content-sha256>.md
evidence/<content-sha256>.jsonl
```

Treat `export-manifest.json` as the commit marker. The exporter writes and validates all content
first, then atomically publishes the manifest as the final artifact operation. A directory without
a valid manifest is incomplete and must not be consumed. Re-running against the same active
database snapshot and contract in a different new output directory produces the same bytes.

## V1 To V2 Migration

| Library state | Command | Result |
|---|---|---|
| PDF/video only | omit `--format-version` or use explicit v1 | Default v1 and explicit v1 are byte-identical for the same snapshot. |
| Active audio Source | default or explicit v1 | Fails closed without omitting a Source. |
| Active audio Source | `--format-version v2` | Exports the complete mixed Library. |

The stable v1 failure is
`problem=unsupported_active_media_type`,
`cause=active Library contains media unsupported by export v1`,
`active_publication_impact=unchanged`, and
`next_step=rerun_library_export_with_format_version_v2`. Rerun the complete export:

```bash
uv run mke --db "$MKE_DB" library export \
  --output compiled-library-v2 --format-version v2 --json
uv run python scripts/compiled_library_export_consumer_v2.py \
  --export compiled-library-v2 --json
```

V2 uses `mke.compiled_library_export.v2`, `mke.compiled_markdown.v2`, and
`mke.compiled_library_export_response.v2`; Evidence stays `mke.evidence_ref.v1`. The standalone
success schema is `mke.compiled_library_export_consumer.v2`. The v1 and v2 consumers do not
cross-consume. Rollback preserves v1: omit or remove audio from the active snapshot, never widen
the v1 validator.

## Authority And Safety Boundaries

The command opens SQLite read-only, performs no migration or unfinished-Run recovery, and does not
change active Publication state. It captures and validates one coherent active Publication
snapshot before creating the output directory. The export does not read or include original Source
files; it contains the active Publication text and provenance already bound in SQLite.

Markdown is a readable derivative. JSONL EvidenceRef records remain the machine authority for the
Source, Run, Publication, revision, content fingerprint, page or timestamp locator, and exact
Evidence text. Display names and Evidence text are untrusted data, including when passed to a
downstream Agent.

V1 accepts at most:

- 4,096 active Publications;
- 65,536 active Evidence records;
- 128 MiB of aggregate Evidence text as strict UTF-8; and
- 64 MiB for any one rendered Markdown or Evidence JSONL file.

Values equal to a limit are accepted; values above it fail closed with
`library_export_too_large`. These are local artifact-safety budgets, not product-scale or latency
claims. A catchable failure removes only call-owned entries whose identity can be proven; an
ambiguous replacement is left for operator inspection and returns `cleanup_failed`.

## Downstream LLM Wiki Compatibility

> The exported Markdown was ingested and compiled in an isolated LLM Wiki workflow, preserving a
> return path to MKE's authoritative content fingerprint and Evidence sidecars for local-Agent use.

The bounded proof ingested two immutable synthetic Markdown records and synthesized one sourced
article from two Sources and three exact `mke.evidence_ref.v1` records. Before ingest, a
deterministic oracle derived from the canonical manifest and JSONL selected exactly one page record
and one timestamp record. The proof then ran exactly two content checks through the installed
read-only `wiki-query` local/query-lite route.

Each closed response contained exactly `evidence_text` and `source`. The returned Unicode text and
its UTF-8 SHA-256 matched the oracle without normalization. The `source` path reached the correct
compiled article and immutable raw wrapper, then the exact `content_fingerprint`, locator boundary,
manifest leaf, and complete Evidence object. Query and non-fixing lint made no wiki writes; their
execution evidence was retained in an immutable call-owned record outside the wiki.

The compiled article remains a downstream synthesized view. The MKE manifest and Evidence sidecars
remain authoritative.

This evidence does not make LLM Wiki an MKE dependency or Evidence authority, and it does not
provide a bundled adapter, automatic sync, hosted service, production deployment, real-user
adoption, or general multimodal understanding. LLM Wiki compatibility was not shipped by v0.1.3.

This fixed synthetic corpus is post-release acceptance evidence from a call-owned isolated local
workflow. It does not claim reconstructed layout or a new release identity. OCR Phase 0 remains
bounded local viability evidence and is not production OCR.

For exact response and artifact fields, see [CLI Reference](../reference/cli.md) and
[Public Contracts](../reference/contracts.md).
