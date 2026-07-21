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
article. It ran exactly two content checks: one page locator and one timestamp locator. Each return
path followed the downstream article to its raw record, then used the exact `content_fingerprint`
to recover the unchanged manifest entry and exact `mke.evidence_ref.v1` JSONL record.

The compiled article remains a downstream synthesized view. The MKE manifest and Evidence sidecars
remain authoritative. This fixed synthetic corpus and local isolated workflow do not make LLM Wiki
an MKE dependency, Evidence authority, bundled integration, hosted service, or production
deployment. The proof does not claim hosted integration, real-user adoption, or general multimodal
understanding. OCR Phase 0 remains bounded local viability evidence and is not production OCR. The
export does not claim reconstructed layout or a new release identity.

For exact response and artifact fields, see [CLI Reference](../reference/cli.md) and
[Public Contracts](../reference/contracts.md).
