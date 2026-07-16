# Compiled Library Export v1 Design

Status: approved and engineering-reviewed for two-PR implementation planning on 2026-07-15;
amended after live code-authority preflight on 2026-07-16.

Engineering self-review: completed; no unresolved architecture decisions.

Date: 2026-07-15.

## Summary

MKE already owns a trustworthy local lifecycle from Source bytes through Run, Publication,
Search/Ask, and portable `mke.evidence_ref.v1` provenance. The next product gap is not another OCR
model or another retrieval candidate. It is a deterministic way for an external knowledge-base or
Agent consumer to use the complete active Library without querying MKE one result window at a
time.

This design adds a read-only Compiled Library Export use case:

```text
active Publications in the implicit local Library
        |
        | one validated SQLite read snapshot
        v
mke library export --output <new-directory>
        |
        +--> export-manifest.json
        +--> sources/<content-sha256>.md
        +--> evidence/<content-sha256>.jsonl
        v
portable Markdown plus exact mke.evidence_ref.v1 records
```

The export is a deterministic projection of already-active Publications. It does not ingest new
material, choose an OCR provider, alter retrieval, copy raw assets, or create a second Evidence
identity system.

## Problem

The current public read paths are intentionally query-oriented:

- Search and Ask return at most twenty Evidence items;
- active-Publication observation returns state and counts rather than content;
- the existing consumer source-pack proof begins with consumer-owned input material; and
- the existing installed-wheel proofs validate CLI and MCP consumption but do not produce a
  portable compiled Library artifact.

These boundaries are correct for interactive retrieval, but they do not support a consumer that
wants to index, diff, inspect, or import the complete active Library as files. Reconstructing that
artifact through repeated Search calls would be query-dependent, incomplete, and unable to prove
that every active Publication was represented exactly once.

The missing product contract is therefore:

> Export one coherent snapshot of every active Publication into deterministic Markdown and exact
> portable Evidence records, without changing MKE's lifecycle authority.

## Existing Foundations

The implementation reuses rather than rebuilds these current boundaries:

- `ActivePublicationObservation` and `SQLiteStore._observe_active_publications()` already validate
  the active Source -> Publication -> published Run -> RunManifest -> Evidence graph;
- `search_provenance_snapshot()` already proves that observation and enriched Evidence can be read
  coherently inside one PEP 249 transaction;
- `mke.evidence_ref.v1` already defines the portable Source fingerprint, Publication revision,
  producing Run, locator, and Evidence text contract;
- the CLI and shared public-error serializer already own stable local command presentation;
- installed-wheel source-pack, Evidence-provenance, local-knowledge, product, and release proofs
  already provide orchestration patterns; and
- OCR Phase 0 remains evaluation evidence and does not need promotion for export to work.

The new work is the complete bounded snapshot read model, deterministic renderer, safe output
publication, CLI entry point, and independent consumer evidence. It does not add a second
Publication validator, Evidence identity system, retrieval path, or knowledge-base runtime.

## Goals

1. Export every active Publication in the implicit `local` Library from one coherent database
   snapshot.
2. Produce deterministic, diffable Markdown for human and Agent-oriented knowledge-base
   consumers.
3. Preserve the exact existing `mke.evidence_ref.v1` contract in a machine-readable sidecar.
4. Bind every exported file to Source, Publication, Run, extractor, locator, and byte identity.
5. Fail closed on an invalid active provenance graph, output collision, artifact drift, partial
   publication, or cleanup failure.
6. Prove the contract through a standalone installed-wheel consumer that does not import MKE
   implementation modules.
7. Demonstrate, through one bounded and isolated compatibility proof, that an LLM Wiki workflow
   can ingest the exported Markdown, compile it, and answer from the resulting local wiki without
   weakening MKE provenance authority.
8. Deliver the runtime contract and deterministic consumer proof in one independently reviewable
   core PR, then record LLM Wiki compatibility and its bounded public claim in a second docs/evidence
   PR after the core PR is merged and reverified.

## Non-Goals

This design does not:

- add production OCR or promote the Phase 0 OCR evaluation runtime;
- integrate PP-OCRv6 or PaddleOCR-VL into the normal ingest path;
- claim table, formula, chart, layout, picture, or caption reconstruction;
- introduce `document.json`, a rich block intermediate representation, or an asset graph;
- copy original PDFs, videos, images, or model artifacts into the export;
- add a quality report or reinterpret existing intake/evaluation reports;
- change Search, Ask, retrieval ranking, FTS, embedding, RRF, or reranker behavior;
- add or change MCP tools, Resources, Prompts, or transport adapters;
- add an HTTP service, watcher, plugin, bidirectional sync, or hosted integration;
- depend on a particular downstream knowledge-base product;
- add an LLM Wiki adapter, write into an operator's configured wiki hub, or make LLM Wiki a
  runtime or CI dependency;
- make MKE runtime, CLI, proof CI, or artifact consumption require an LLM, hosted API, network
  access, or new runtime dependency; or
- make release, production-readiness, or real-user adoption claims by itself.

## Approaches Considered

### A. Rich multimodal document IR now

Define page, heading, paragraph, list, table, formula, figure, caption, reading-order, and asset
types before exposing any compiled output.

Rejected for this stage. Mature document systems and OCR providers already expose rich document
structures. MKE does not yet have representative production evidence showing which of those
structures it must own. Freezing a parallel IR now would expand the architecture before the
consumer boundary is proven and would couple this PR to production OCR.

### B. Markdown-only dump

Write one Markdown file per Source without a versioned manifest or Evidence sidecar.

Rejected. It is easy to demo but cannot prove snapshot completeness, active Publication identity,
portable locators, file integrity, or deterministic failure. It would reduce MKE to another text
conversion wrapper.

### C. Versioned manifest plus Markdown plus existing EvidenceRef

Export one canonical manifest, one readable Markdown file per active Source, and one JSONL file of
exact `mke.evidence_ref.v1` objects per active Source.

Selected. It exposes a useful compiled artifact while preserving MKE's strongest existing
contracts. It is compatible with plain file consumers today and leaves room for richer structure
only after real evidence justifies it.

### D. Wait for production OCR

Defer any compiled output until scanned-PDF runtime integration is complete.

Rejected. The export is valuable for the existing PDF and video Publication lifecycle, and its
contract should remain independent of extractor selection. Production OCR can later feed the same
Publication and export boundary.

## Public CLI Contract

The new command is:

```bash
mke --db <database> library export --output <new-directory>
mke --db <database> library export --output <new-directory> --json
```

`--db` retains the existing global CLI semantics. The command explicitly rejects the global
`--retrieval-query-policy` and `--retrieval-strategy` options, including `--option=value` forms;
they are retrieval runtime controls and are not part of this closed export surface. `--output`
is required and accepts exactly one normalized child-directory name under the process working
directory. Absolute paths, separators, empty names, `.`, `..`, symbolic-link parents, and
traversal are rejected. An operator exports to a different parent by changing the working
directory before invoking MKE. The target must not exist as a file, directory, or symbolic link.
The command never merges into or replaces an existing directory. This keeps the public contract
inside an operator-selected root instead of adding an arbitrary filesystem-output capability.

The command operates only on the implicit local Library. v1 does not accept a library ID,
Publication ID, query, Source selector, output format selector, or extractor option.

On success, `--json` emits this closed response:

```json
{
  "schema_version": "mke.compiled_library_export_response.v1",
  "ok": true,
  "library_id": "local",
  "source_count": 2,
  "evidence_count": 5,
  "manifest_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

The response contains no database path, output path, hostname, timestamp, temporary path, or raw
diagnostic. `source_count` is the number of exported active Publications, not the total number of
Source rows; it equals `len(manifest.sources)`. `evidence_count` equals the manifest observation's
active Evidence count. The non-JSON form renders the same bounded fields as one stable status
line.

On failure, the command exits nonzero and emits the existing public error shape extended only by
the literal response schema version:

```json
{
  "schema_version": "mke.compiled_library_export_response.v1",
  "ok": false,
  "problem": "library_export_invalid",
  "cause": "local Library has no active Publications",
  "active_publication_impact": "unchanged",
  "next_step": "ingest_and_publish_source"
}
```

The command is read-only with respect to MKE domain state. Every success and failure leaves the
active Publication graph unchanged.

The export composition opens an existing database through SQLite read-only mode with
`PRAGMA query_only=ON`. It does not create a missing database, run migrations, probe or rebuild
retrieval projections, recover unfinished Runs, or invoke the default owner-startup recovery
path. A missing, incompatible, or migration-stale database fails closed with a stable public
error. This is a command-specific composition choice; existing CLI and MCP owner startup behavior
does not change.

The command-specific serializer may add `schema_version` around the existing public error fields.
Its six non-redacted export causes are a closed command-local set owned by
`mke.interfaces.library_export`; they must not be added to the shared `_ALLOWLISTED_CAUSES`, MCP
schemas, or the frozen consumer source-pack fixture. Known export failures may reuse the
`PublicError` value shape, but command-local validation accepts only those six causes plus the
existing exact redacted literal. It must not change the shared `PublicError.payload()` shape or any
existing CLI or MCP error contract.

## Export Tree

A successful target has this exact inventory:

```text
<output>/
├── export-manifest.json
├── evidence/
│   ├── <content-sha256>.jsonl
│   └── ...
└── sources/
    ├── <content-sha256>.md
    └── ...
```

`<content-sha256>` is the 64-character lowercase digest from the Source content fingerprint with
the `sha256:` prefix removed. Each active Source contributes exactly one Markdown file and one
Evidence JSONL file. Duplicate content fingerprints, unexpected files, nested content paths, or
name collisions fail closed.

The export contains no raw Source bytes. The content fingerprint is the portable join back to
consumer-owned Source material.

## Manifest Contract

`export-manifest.json` is UTF-8 canonical JSON with sorted object keys, compact separators, and one
trailing LF. Canonical JSON means
`json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"` encoded as
strict UTF-8. Its schema is `mke.compiled_library_export.v1`. The top-level object is closed and
has these exact fields:

```json
{
  "evidence_schema": "mke.evidence_ref.v1",
  "markdown_format": "mke.compiled_markdown.v1",
  "observation": {
    "active_evidence_count": 5,
    "active_publication_count": 2,
    "library_id": "local",
    "schema_version": "mke.active_publication_observation.v1",
    "source_count": 2,
    "state": "active"
  },
  "schema_version": "mke.compiled_library_export.v1",
  "sources": [
    {
      "content_fingerprint": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "display_name": "example.pdf",
      "evidence_count": 3,
      "evidence_path": "evidence/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.jsonl",
      "evidence_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "extractor_fingerprint": "pymupdf-text-v1",
      "markdown_path": "sources/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.md",
      "markdown_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "media_type": "application/pdf",
      "publication_id": "pub_0123456789abcdef0123456789abcdef",
      "publication_revision": 1,
      "required_stages": [
        "candidate_evidence",
        "pdf_text_extraction"
      ],
      "run_id": "run_0123456789abcdef0123456789abcdef",
      "source_id": "src_0123456789abcdef0123456789abcdef"
    }
  ]
}
```

The example values are illustrative shape values, not frozen fixture identities.

Manifest invariants:

- `observation` is the exact `mke.active_publication_observation.v1` shape already exposed by the
  strict read contract;
- `observation.state` must be `active`;
- `len(sources)` equals `observation.active_publication_count`;
- the sum of source `evidence_count` equals `observation.active_evidence_count`;
- `observation.source_count` may be greater than the exported source count when inactive Sources
  exist;
- each source entry is closed and contains one valid active Source -> Publication -> published Run
  -> RunManifest graph;
- `content_fingerprint` equals `sha256:` plus the active Source asset digest and the RunManifest
  asset digest;
- `publication_revision` equals the Source active revision and Publication revision;
- `evidence_count` equals both the RunManifest count and the number of JSONL records;
- `required_stages` is sorted and satisfies the existing extractor-fingerprint contract;
- all IDs and fingerprints satisfy the existing strict public patterns;
- `display_name` is a valid UTF-8 scalar string from 1 through 1,024 characters and contains no
  control, line-separator, or paragraph-separator code point;
- `media_type` is one of the currently ingestible `application/pdf` or `video/mp4` values;
- Evidence text satisfies the existing `mke.evidence_ref.v1` 1,000,000-character maximum;
- all paths are normalized relative POSIX paths with no absolute form, parent traversal, empty
  segment, backslash, or symbolic-link target;
- file SHA-256 values bind the exact emitted bytes; and
- `sources` is sorted by `(content_fingerprint, source_id)`.

The manifest deliberately contains no export ID or creation time. For the same active database
snapshot and exporter contract, the emitted bytes are identical. Re-ingesting the same source into
a new database may create new Source, Run, Publication, and Evidence IDs, so cross-database byte
identity is not promised; the content fingerprint remains the portable Source identity.

## Evidence JSONL Contract

Each `evidence/<content-sha256>.jsonl` contains the complete active Evidence for one Source. Every
non-empty line is one canonical JSON object conforming exactly to `mke.evidence_ref.v1`:

```json
{"content_fingerprint":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","evidence_id":"ev_0123456789abcdef0123456789abcdef","locator":{"end":1,"kind":"page","start":1},"publication_id":"pub_0123456789abcdef0123456789abcdef","publication_revision":1,"run_id":"run_0123456789abcdef0123456789abcdef","schema_version":"mke.evidence_ref.v1","source_id":"src_0123456789abcdef0123456789abcdef","text":"Example Evidence."}
```

Each line uses the same `ensure_ascii=False`, sorted-key, compact-separator encoding. The file ends
with one LF. Records are sorted by `(locator.kind, locator.start, locator.end, evidence_id)`.

The JSONL object is not an export-specific copy with similar fields. It is the same closed
EvidenceRef contract used by strict Search and Ask, including:

- Evidence, Source, Publication, and Run identities;
- Source content fingerprint;
- active Publication revision;
- page or timestamp locator; and
- exact Evidence text.

For every record, Source, Publication, revision, Run, and fingerprint must equal the containing
manifest source entry. Page locators require equal positive start/end values. Timestamp locators
require non-negative increasing millisecond values.

## Markdown Contract

Each `sources/<content-sha256>.md` is UTF-8 and follows
`mke.compiled_markdown.v1`. It is a readable derivative; the JSONL EvidenceRef records remain the
machine authority for provenance.

The file begins with YAML-compatible front matter in this fixed key order. String values use JSON
string escaping, preventing embedded line breaks or control characters from creating additional
metadata keys:

```markdown
---
mke_format: "mke.compiled_markdown.v1"
source_id: "src_0123456789abcdef0123456789abcdef"
display_name: "example.pdf"
content_fingerprint: "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
media_type: "application/pdf"
publication_id: "pub_0123456789abcdef0123456789abcdef"
publication_revision: 1
run_id: "run_0123456789abcdef0123456789abcdef"
extractor_fingerprint: "pymupdf-text-v1"
evidence_schema: "mke.evidence_ref.v1"
evidence_count: 1
---

# Compiled source `sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef`

<a id="mke-evidence-ev_0123456789abcdef0123456789abcdef"></a>
## Page 1

Example Evidence.
```

For timestamp Evidence, the generated heading is:

```markdown
## Timestamp 1000-2500 ms
```

Evidence sections use the same ordering as the JSONL file. The generated heading and anchor are
renderer-owned. Evidence text follows after the heading and is emitted from the exact EvidenceRef
text; it is not summarized, translated, interpreted, or sent to a model.

Source display names and Evidence text are untrusted content. The exporter serializes them as data
and never interprets them as commands. Downstream Agents must preserve the same trust boundary.
Consumers that require authoritative provenance must read the JSONL record rather than infer
identity from arbitrary Markdown contained in Evidence text.

## Snapshot And Authority Boundary

The export must not use Search, FTS, repeated public queries, or direct reads performed by the
standalone consumer. A new read-only `KnowledgeEngine` use case delegates to one project-owned
SQLiteStore method and returns frozen project DTOs. v1 does not introduce a speculative storage
port or a second persistence abstraction solely for this command.

The SQLite adapter obtains the snapshot in one PEP 249 transaction on its existing connection; it
does not issue a nested `BEGIN`. Within that transaction it reads and validates:

- the single implicit default Library;
- total Source count;
- every Source with a non-null active Publication pointer;
- Source asset digest and media type;
- active Publication identity and revision;
- published Run identity and Source ownership;
- RunManifest asset digest, Evidence count, required stages, and extractor fingerprint; and
- every active Evidence identity, Source/Run ownership, locator, and text.

The adapter must apply at least the same provenance-graph checks as
`observe_active_publications()`. It performs bounded aggregate preflight before constructing the
complete read model, then uses a bounded number of set-oriented queries rather than one query per
Source or Evidence. It returns immutable project snapshot values and must not expose a SQLite
connection, row object, query cursor, or database path to the application renderer.

The transaction commits after the complete immutable snapshot has been constructed and validated;
any failure rolls it back. Rendering uses only that snapshot, so a concurrent Publication change
after snapshot acquisition cannot mix revisions inside one export.

The read-only connection validates the exact required schema before reading domain rows. It does
not reuse the normal constructor path that calls `migrate()` or unfinished-Run recovery. The
implementation may add a bounded read-only construction option to the existing SQLite adapter;
it must not introduce a second database schema or duplicate Publication authority.

## V1 Export Budgets

The complete read model is intentionally bounded for a local CLI process. v1 accepts at most:

- 4,096 active Publications;
- 65,536 active Evidence records;
- 128 MiB of aggregate Evidence text measured as strict UTF-8 bytes; and
- 64 MiB for any one rendered Markdown or Evidence JSONL file.

Counts and aggregate database text bytes are checked inside the same read transaction before all
Evidence text is materialized. Per-file rendered-byte limits are checked before file publication.
The renderer processes one Source at a time and does not construct the complete export tree as one
additional in-memory byte buffer.
Values equal to a limit are accepted; values above it fail closed with no committed export. These
are artifact safety limits for v1, not product-scale, latency, or production SLA claims. Raising
them requires explicit benchmark evidence and a versioned contract decision rather than an
unreviewed constant change.

The following conditions fail closed before artifact publication:

- no active Publication exists;
- more than one Library or invalid implicit Library ownership exists;
- an active pointer, Source, Publication, Run, or manifest identity disagrees;
- the Run is not `published`;
- the Source active revision and Publication revision disagree;
- the Source asset, manifest asset, or content fingerprint disagrees;
- Evidence count or ownership disagrees;
- an Evidence locator is invalid;
- an ID, fingerprint, media type, required-stage set, or extractor identity violates the existing
  domain contract; or
- a duplicate fingerprint or output path would be produced.

The export does not read original Source files. The checked-in database authority is the active
Publication graph plus its bound Source digest.

## Output Publication And Cleanup

The output is a transactional artifact with `export-manifest.json` as its commit marker.

1. Preflight opens and binds the process working directory, validates the single child name, and
   verifies that the target does not exist.
2. The complete read-only database snapshot is acquired and validated before any output path is
   created.
3. The implementation creates the target directory exclusively relative to the bound working
   directory.
4. `sources/` and `evidence/` are created under that call-owned target without following symbolic
   links.
5. Every content file is created exclusively, written with bounded operations, closed, re-read,
   and checked against its planned byte count and SHA-256.
6. The exact inventory is checked before publication.
7. The canonical manifest is written to a call-owned temporary file inside the target, verified,
   and atomically renamed to `export-manifest.json` as the final artifact operation.
8. Success is reported only after the committed manifest and every referenced file revalidate.

A consumer must treat a directory without a valid `export-manifest.json` as incomplete. An
uncatchable process termination may leave such an uncommitted directory; it is never a valid v1
export and a later invocation will not overwrite it.

On a catchable failure before manifest publication, cleanup removes only entries proven to belong
to the current invocation. The implementation binds call-owned directory/file identities and
refuses to remove a path that was replaced. A pre-existing target or operator-owned replacement is
never deleted. If complete cleanup cannot be proven, the command returns `cleanup_failed` and
leaves the ambiguous path for operator inspection.

No operation mutates the database or active Publication state.

## Stable Failure Contract

The public response uses closed machine tokens and allowlisted causes. At minimum, the design
requires these outcomes:

| Problem | Public cause | Next step |
|---|---|---|
| `library_export_invalid` | `local Library has no active Publications` | `ingest_and_publish_source` |
| `library_export_invalid` | `active Publication provenance graph is invalid` | `repair_local_library` |
| `library_export_invalid` | `local Library database is unavailable or incompatible` | `open_current_library_database` |
| `output_path_invalid` | `output directory must not already exist` | `choose_new_output_directory` |
| `output_path_invalid` | `output parent is invalid` | `choose_valid_output_parent` |
| `library_export_too_large` | `active Library exceeds v1 export limits` | `reduce_active_library_or_use_later_export_version` |
| `library_export_failed` | approved redacted cause | `retry_library_export` |
| `cleanup_failed` | approved redacted cause | `inspect_output_parent` |

All failures include `active_publication_impact="unchanged"`. Raw SQLite errors, absolute paths,
temporary names, host details, source text, and stack traces must not cross the public CLI
boundary.

The six non-redacted table causes are allowlisted only for
`mke.compiled_library_export_response.v1`. They are intentionally absent from the shared MCP/CLI
cause allowlist; the two redacted rows reuse the exact existing redacted literal by value.

## Failure Modes

| Failure | Required behavior | Verification |
|---|---|---|
| Missing or migration-stale database | Fail before target creation; do not create or migrate the database | Read-only adapter and CLI tests |
| Invalid active provenance edge | Roll back the read transaction and create no target | SQLite graph-mutation tests |
| Concurrent Publication switch | Export either the complete before-snapshot or after-snapshot state, never a mixture | Two-connection snapshot test |
| Export exceeds a v1 count or byte budget | Return `library_export_too_large` and create no committed export | Exact-limit and over-limit tests |
| Another process creates the target | Exclusive creation fails without merging, replacing, or deleting operator state | Filesystem race regression |
| Disk-full, short write, digest mismatch, or final rename failure | Return a stable failure and remove only proven call-owned entries | Injected filesystem failures |
| Catchable cleanup failure | Return `cleanup_failed`; leave the ambiguous uncommitted directory for inspection | Cleanup ownership tests |
| Uncatchable process termination | A directory without a valid final manifest remains visibly incomplete | Manifest-last consumer rejection |
| Downstream LLM Wiki rejects or rewrites required identity | Do not change MKE output; withhold the LLM Wiki compatibility claim | Isolated compatibility proof |

## Determinism And Compatibility

Determinism means that the same immutable snapshot rendered by the same v1 contract produces the
same bytes in a different new output directory. It does not mean that independently ingested
databases share random lifecycle IDs.

The following are byte-authority requirements:

- canonical JSON object encoding;
- fixed source and Evidence ordering;
- fixed Markdown metadata order and locator headings;
- UTF-8 encoding;
- LF-owned generated lines and one final LF per generated file;
- no timestamp, hostname, absolute path, random export ID, temporary name, or process identity in
  committed output; and
- SHA-256 over exact file bytes.

Readers must reject unknown manifest, Markdown-format, active-observation, or Evidence schema
versions. Additive fields require a new schema version because all v1 objects are closed.

Future exporters may add a richer optional structure file only under a new versioned contract.
They must not silently change v1 Markdown or reinterpret `mke.evidence_ref.v1`.

## Security And Trust Boundaries

- Original Source content, display names, extracted Evidence text, and downstream Markdown are
  untrusted data.
- The exporter performs no prompt execution, template evaluation, shell interpolation, network
  access, or model call.
- Output paths are derived only from validated lowercase SHA-256 values, never display names or
  Evidence text.
- All filesystem operations are relative to a bound output root and reject symbolic-link or
  identity drift.
- The manifest and JSONL are closed schemas with bounded scalar validation.
- Public failures are redacted and never include Source content or local path data.
- The standalone consumer validates the export independently and must not trust producer-owned
  Python models at runtime.

## Installed-Wheel External Consumer Proof

Completion requires a repository-owned public-safe proof, separate from unit tests. The proof:

1. builds one wheel from the exact committed source candidate;
2. installs that wheel in a fresh external environment and working directory;
3. clears hostile Python environment variables and proves the imported distribution and `mke`
   executable come from that environment;
4. ingests frozen repository-authored synthetic material that produces at least one page locator
   and one timestamp locator using existing supported runtime paths;
5. runs the installed `mke library export` command against the resulting external database;
6. invokes a standalone standard-library consumer that does not import `mke` or read SQLite;
7. validates the closed response, exact export inventory, manifest, file digests, Markdown
   anchors, and every EvidenceRef independently;
8. maps each content fingerprint to a consumer-owned source key;
9. copies the committed export to a second directory and revalidates it without path rewriting;
10. proves repeated export of the unchanged active snapshot to another new directory is
    byte-identical;
11. proves an existing target, provenance drift, digest drift, unexpected file, and partial output
    fail closed without changing active Publications; cleanup failure injection remains owned by
    the filesystem adapter tests rather than the installed public-interface proof; and
12. emits only a bounded public-safe aggregate result.

The proof may reuse existing repository-authored fixtures and orchestration helpers, but its
consumer-owned schema fixture and validator must remain independent of MKE implementation models.
It does not need a new MCP tool. Existing strict Search/Ask consumer proofs continue to own the MCP
contract boundary.

The proof must run from an installed wheel and must not describe a source-built candidate wheel as
a published Release artifact.

## LLM Wiki Compatibility Proof

The installed-wheel standalone consumer remains the public, deterministic correctness gate. After
the core export PR is merged and its post-merge checks pass, a separate docs/evidence PR performs
one bounded downstream compatibility proof using the current LLM Wiki workflow. The later release
decision may include the resulting claim, but neither PR itself changes release identity. This
proof demonstrates a real local-Agent consumption path without making MKE depend on that product.

The compatibility proof:

1. uses only the public-safe synthetic export produced by the installed-wheel proof;
2. creates a call-owned isolated local wiki rather than using an operator's configured hub;
3. ingests the exported Markdown through LLM Wiki's file-ingestion workflow, which preserves
   Markdown formatting inside an immutable raw source record;
4. compiles at least one article, rebuilds the derived index, and runs a bounded content query;
5. verifies that the compiled article cites the ingested raw source and that the raw record
   preserves the MKE content fingerprint plus page or timestamp boundaries needed to return to the
   authoritative export;
6. runs the applicable wiki lint checks;
7. confirms that the MKE export tree is byte-identical before and after consumption; and
8. removes only the call-owned isolated wiki after recording a bounded public-safe aggregate
   result.

LLM Wiki articles are synthesized downstream views. They do not replace
`mke.evidence_ref.v1`, and the proof must not claim that a compiled article itself is an MKE
Evidence record. Exact Source, Publication, Run, locator, and text authority remains in the export
manifest and JSONL sidecars.

Because the LLM Wiki workflow is Agent-driven rather than a repository runtime dependency, this
proof is an operator-local acceptance check and is not added to GitHub Actions. If it cannot be
completed, the generic export contract may still be technically correct, but v0.1.3 must not claim
verified LLM Wiki compatibility. Any incompatibility should first be assessed as a generic export
contract gap; a product-specific MKE adapter requires separate evidence and design approval.

## Test Strategy

Implementation follows TDD and includes at least:

### Domain and schema tests

- valid page and timestamp snapshot records;
- closed export response, manifest, source-entry, and EvidenceRef shapes;
- ID, fingerprint, revision, count, stage, media-type, and locator rejection;
- deterministic ordering and canonical bytes; and
- unknown version and extra-field rejection.

### SQLite adapter tests

- missing database is not created, incompatible schema is not migrated, and unfinished Runs are
  not recovered or changed;
- empty Library and Sources-without-active-Publication states;
- multiple active Sources with page and timestamp Evidence;
- inactive Sources excluded while observation counts remain accurate;
- malformed active pointer, revision, Run state, RunManifest, digest, count, and Evidence ownership;
- duplicate or invalid output identity;
- exact-limit acceptance and over-limit rejection for Publications, Evidence, aggregate UTF-8
  bytes, and per-file rendered bytes;
- a bounded set-oriented query count that does not grow once per Source or Evidence;
- one-transaction snapshot consistency under a second connection; and
- rollback and unchanged active state after every failure.

### Renderer and filesystem tests

- exact tree, JSON, JSONL, Markdown, ordering, and digests;
- adversarial display names and Evidence text remain serialized data;
- existing file, directory, and symbolic-link target rejection;
- descriptor-bound writes plus replacement-safe cleanup for the owned target tree;
- unexpected, nested, missing, truncated, or modified output rejection;
- manifest-last publication;
- short write, rename, pre-commit revalidation, and cleanup failures;
- no removal of pre-existing or replacement operator state; and
- repeated byte-identical exports to distinct new directories.

The filesystem threat model is bounded to real local-operation failures and preservation of
operator state. It does not treat exhaustive same-account malicious inode replacement at every
micro-step as a release blocker. Every fallible close, inventory check, digest check, and temporary
manifest validation occurs before the final manifest rename; that rename is the final production
operation.

### CLI tests

- exact parser surface and `--json` behavior;
- one child-directory output name accepted while absolute, nested, traversal, empty, dot, and
  symbolic-link-parent targets are rejected;
- success summary matches committed manifest bytes;
- stable public failures and nonzero exit codes;
- no path, hostname, timestamp, Source text, or raw diagnostic leakage; and
- no change to existing CLI, MCP, Search, Ask, or ingest contracts.

### Product proof and regression gates

- installed-wheel standalone consumer proof;
- in the follow-up PR only, bounded isolated LLM Wiki ingest, compile, query, provenance-link,
  lint, and cleanup proof;
- existing consumer source-pack and Evidence provenance proofs;
- existing product proof, demo, local-knowledge proof, and release presentation audit;
- focused and full pytest;
- Ruff, Pyright, build, and diff checks; and
- documentation contract tests.

## Documentation Impact

The core implementation PR updates:

- README capability and boundary tables;
- architecture documentation for the new read-only export use case;
- CLI reference;
- a how-to for exporting and validating a compiled Library;
- an explanation of Markdown versus EvidenceRef authority;
- proof documentation and release presentation audit; and
- this design, the core implementation plan, and core review records.

The follow-up compatibility PR updates only the bounded LLM Wiki compatibility statement,
documentation contract tests, the compatibility plan, and its public-neutral review record. It
does not change product code, dependency files, workflows, schemas, or the export artifact.

Documentation must state that the export contains active Publication text and provenance, not
original Source bytes or reconstructed layout.

## Release Claim Boundary

After implementation, independent review, installed-wheel proof, merge, and a separate release
decision, the strongest supported concise claim is:

> MKE can deterministically export active Publications as portable Markdown with exact page or
> timestamp Evidence provenance, validated through an installed-wheel external consumer proof.

After the separate LLM Wiki compatibility proof succeeds, a second bounded claim may be added:

> The exported Markdown was ingested and compiled in an isolated LLM Wiki workflow, preserving a
> return path to MKE's authoritative content fingerprint and Evidence sidecars for local-Agent
> use.

If released together with the existing OCR Phase 0 evidence, the claim may add:

> OCR Phase 0 records bounded local viability evidence on a fixed synthetic corpus.

It must not claim production OCR, general document understanding, layout recovery, structured
table/formula/chart extraction, hosted deployment, real-user adoption, or business impact.

## Future Phases

These are explicit follow-ups, not hidden requirements for v1:

1. Selective production plain-text OCR may publish through the same Run/Publication/export path
   after representative installed-wheel evidence and fail-closed quality gates exist.
2. Complex-page OCR may be evaluated separately for tables, formulas, charts, layout, and image
   regions.
3. Actual provider outputs should be compared with mature document models before MKE owns a rich
   block or asset schema.
4. A future export version may add optional structured blocks or assets while preserving v1.
5. If direct Agent discovery of exports becomes a real integration need, a later design may expose
   them through standard MCP Resources without duplicating application authority.

None of these follow-ups may broaden the core PR beyond one Compiled Library Export contract and
its deterministic consumer proof, or broaden the later compatibility PR beyond downstream
evidence and documentation.

## Acceptance Criteria

The design is complete when an implementation can prove all of the following without expanding
scope:

- one coherent snapshot includes every active Publication exactly once;
- the existing provenance graph is revalidated rather than bypassed;
- the output tree and all three versioned formats are closed and deterministic;
- exact `mke.evidence_ref.v1` objects remain the machine provenance authority;
- no existing target or active Publication state is mutated;
- export startup does not create, migrate, recover, or otherwise write the Library database;
- partial and failed exports are never accepted as committed exports;
- a standalone installed-wheel consumer validates portability without importing MKE internals;
- after the core PR is merged, an isolated LLM Wiki proof validates ingest, compilation, query,
  provenance return, lint, and cleanup without introducing a runtime or CI dependency;
- every successful export stays within the closed v1 count and byte budgets, while an oversized
  active Library produces no committed export;
- current CLI/MCP/retrieval/ingest behavior remains compatible;
- full repository quality gates pass; and
- documentation and release claims remain within the stated boundary.
