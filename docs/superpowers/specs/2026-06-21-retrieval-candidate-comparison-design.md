# Numeric Retrieval Candidate Comparison Design

## Status

- Stage: PR 1 implemented locally; candidate passed comparison gates.
- Slice: E2.
- Design date: 2026-06-21.
- Baseline: `main@e3a3f3656be8889e8e54e06a1de09ebd6412384f`.
- Depends on: the completed E1 retrieval evaluation baseline.

## PR 1 Result

- Integrity status: `passed`.
- Candidate status: `passed`.
- Promotion gates: 14/14 passed.
- E1 Recall@1: `0.875000` current, `0.937500` candidate.
- Only E1 result delta: `water-answerable-01`, from no hit to rank 1.
- Reviewed artifact:
  `benchmarks/retrieval/numeric-grouping-v1-comparison.json`.
- Runtime default: unchanged at `current`.

This result permits a separately reviewed PR 2. It does not itself approve ADR-0007 or a default
policy change.

## Goal

Determine whether one bounded query-normalization candidate can fix the observed
compact-query/grouped-document numeric mismatch without changing any unrelated retrieval result.

The candidate is `numeric-grouping-v1`. It may be promoted only after it proves:

1. a compact numeric query can retrieve equivalent comma-grouped document text;
2. compact numeric document text keeps its existing match;
3. non-adjacent numeric tokens do not become a false phrase match;
4. leading-zero values and alphanumeric identifiers remain unchanged;
5. queries without an eligible compact integer compile and retrieve identically;
6. the complete E1 result has no per-query rank or false-positive regression;
7. each Search still executes one FTS5 `MATCH` query with no new dependency, index, model, or
   network access.

E2 does not choose among broad retrieval families. E1 already isolated the first concrete failure
class.

## Evidence From E1

E1 recorded:

- Recall@1: `0.875000`.
- Recall@3/5 and MRR@5: `0.937500`.
- One answerable miss: `water-answerable-01`.
- No unanswerable false positives.

The missed query is:

```text
410000 million gallons withdrawals
```

The relevant page contains:

```text
Total withdrawals were 410,000 million gallons per day
```

The current compiler produces one token for `410000`. SQLite FTS5 `unicode61` tokenizes the comma
as a separator, so the document contains adjacent `410` and `000` tokens. Repository reproduction
confirmed:

| Query | Result |
|---|---|
| `410000 million gallons withdrawals` | no hit |
| `410,000 million gallons withdrawals` | page 1 |
| `410 000 million gallons withdrawals` | page 1 |
| `million gallons withdrawals` | pages 1 and 2 |

This supports a numeric token-equivalence candidate. It does not support CJK tokenization,
embeddings, fusion, reranking, or a vector index.

## Chosen Approach

Use two PRs:

1. **Comparison PR:** freeze independent development and public holdout documents before candidate
   code; add paired adversarial controls; implement the off-default candidate; record a reviewed
   comparison artifact. The runtime default remains `current`.
2. **Promotion PR:** only if every gate passes, add an ADR and change the default policy while
   retaining `current` for rollback.

Protocol-first integrity is enforced by execution and commit order inside PR 1:

```text
fixture + manifests + protocol acceptance tests
  -> current-policy observation
  -> candidate TDD and code
  -> comparison artifact
```

The public holdout is locked and independently authored, but not secret or statistically blind.
It protects against editing the target after candidate implementation; it is not a generalization
claim.

## Rejected Alternatives

| Alternative | Decision | Reason |
|---|---|---|
| Patch `_to_fts_query()` before freezing cases | Rejected | It would tune implementation and evaluation target together. |
| Replace compact tokens with grouped phrases | Rejected | It would break documents that contain the original compact token. |
| Add CJK or semantic slices | Deferred | They do not test this candidate and would add unrelated fixtures and schema. |
| Build a generic retrieval-candidate platform | Rejected | One observed failure does not justify a broad plugin system. |
| Treat the existing USGS page as both development and holdout | Rejected | Different numbers from the same page are not an independent holdout. |
| Add embeddings, RRF, reranking, or `sqlite-vec` | Deferred | E1 contains no evidence that they are the next required change. |
| Promote in the comparison PR | Rejected | Evidence collection and changing the product default require separate review decisions. |

## Scope

### In Scope

- Two small repository-generated text-layer PDF fixtures:
  - one development document;
  - one independently authored public holdout document.
- Strict manifests with page qrels, checksums, byte sizes, and a protocol lock.
- Positive controls for grouped and compact document numbers.
- Positive controls for comma-, space-, and hyphen-separated adjacent grouped tokens.
- A negative control for non-adjacent numeric tokens, plus preservation controls for leading zeros,
  alphanumeric identifiers, short numbers, and unrelated queries.
- An allowlisted off-default `numeric-grouping-v1` policy.
- Current-versus-candidate comparison on development, holdout, and full E1.
- A reviewed machine-readable comparison artifact.
- A later conditional ADR-backed promotion.

### Not In Scope

- CJK, semantic-paraphrase, OCR, or ASR evaluation.
- Video, audio, model, voice, font, or downloaded fixtures.
- Passage/chunk segmentation changes.
- New FTS schema, tokenizer configuration, index, retrieval dependency, or network access.
- Arbitrary query-rewriter imports, SQL, regex, commands, or tokenizer expressions.
- Publication, Evidence, Search result, Ask result, CLI/MCP error, or transcription contract
  changes.
- A secret holdout or statistical generalization claim.
- Changing the runtime default in the comparison PR.
- Distinguishing comma-grouped text from other punctuation that the configured FTS5 tokenizer
  treats as the same adjacent token sequence.

## Frozen Protocol

### Layout

```text
tests/fixtures/retrieval-numeric-v1/
  development.pdf
  holdout.pdf
  development.json
  holdout.json
  protocol-lock.json
  README.md
```

The PDFs are generated outside the repository with the already-pinned PyMuPDF dependency, then
copied in only after text extraction, page count, byte size, and SHA-256 verification. Required CI
does not regenerate them.

The README records:

- exact generation script/command;
- PyMuPDF version;
- exact page text;
- byte size, page count, and SHA-256;
- statement that both documents were created for this repository;
- statement that the public holdout is locked but visible;
- narrow numeric-equivalence claim boundary.

### Manifest Contract

Both manifests use `mke.retrieval_eval.v1` so the existing E1 parser, snapshot validation,
ingestion, qrel validation, metrics, and report DTOs remain reusable.

The protocol lock uses `mke.retrieval_numeric_protocol.v1` and records:

- development and holdout manifest paths and SHA-256 values;
- every fixture path, byte size, and SHA-256;
- required query IDs and counts;
- candidate ID and semantic candidate revision `1`;
- full E1 manifest identity;
- protocol claim:
  `compact_query_adjacent_right_grouped_tokens_without_unrelated_change`.

The protocol root is `protocol_path.parent.parent`, which is the `tests/fixtures/` directory for
the approved layout. The lock accepts only these exact repository-relative locations:

- `retrieval-numeric-v1/development.json`;
- `retrieval-numeric-v1/holdout.json`;
- `retrieval-eval-v1.json`.

Every resolved path must remain below the protocol root. Absolute paths, `..`, symlink escape, and
alternate layouts fail validation before engine construction.

The comparison runner rejects:

- a changed or missing manifest/fixture;
- path escape;
- duplicate query/document identity;
- a query or exact page text shared across development and holdout;
- unknown fields;
- a candidate ID outside the allowlist;
- a protocol or artifact version mismatch.

### Development Document

`development.pdf` contains four pages:

1. `Grouped daily withdrawal total: 410,000 million gallons.`
2. `Compact inventory total: 730000 storage units.`
3. `Non-adjacent ledger values: 410 units were accepted; after review, 000 units were rejected.`
4. `Identifiers: postal district 02139; equipment model ZX410000; reporting year 2005.`

Development queries:

| ID | Category | Query | Expected |
|---|---|---|---|
| `numeric-dev-grouped-01` | answerable | `410000 grouped daily withdrawal` | page 1 at rank 1 |
| `numeric-dev-compact-01` | answerable | `730000 compact inventory` | page 2 at rank 1 |
| `numeric-dev-non-adjacent-01` | lexical_confuser | `410000 non-adjacent ledger` | no hit |
| `numeric-dev-leading-zero-01` | answerable | `02139 postal district` | page 4 at rank 1 |
| `numeric-dev-identifier-01` | answerable | `ZX410000 equipment model` | page 4 at rank 1 |
| `numeric-dev-short-01` | answerable | `2005 reporting year` | page 4 at rank 1 |
| `numeric-dev-outside-01` | out_of_corpus | `quantum entanglement photon experiment` | no hit |

### Holdout Document

`holdout.pdf` is independently authored and contains different numbers, units, vocabulary, and
page organization:

1. `Grouped reserve capacity: 57,600 cubic meters.`
2. `Compact shipment count: 880000 sealed packages.`
3. `Non-adjacent audit values: 57 samples passed; later, 600 samples failed.`
4. `Identifiers: postal district 00701; sensor model AB57600; reporting year 1997.`

Holdout queries:

| ID | Category | Query | Expected |
|---|---|---|---|
| `numeric-holdout-grouped-01` | answerable | `57600 grouped reserve capacity` | page 1 at rank 1 |
| `numeric-holdout-compact-01` | answerable | `880000 compact shipment count` | page 2 at rank 1 |
| `numeric-holdout-non-adjacent-01` | lexical_confuser | `57600 non-adjacent audit values` | no hit |
| `numeric-holdout-leading-zero-01` | answerable | `00701 postal district` | page 4 at rank 1 |
| `numeric-holdout-identifier-01` | answerable | `AB57600 sensor model` | page 4 at rank 1 |
| `numeric-holdout-short-01` | answerable | `1997 reporting year` | page 4 at rank 1 |
| `numeric-holdout-outside-01` | out_of_corpus | `Roman empire tax policy` | no hit |

No query ID, exact query text, exact page text, primary number, unit, or positive-control context is
shared across development and holdout.

## Query Policies

Candidate IDs are bounded lowercase ASCII literals:

```text
current
numeric-grouping-v1
```

`current` preserves the existing compiler exactly.

`numeric-grouping-v1` applies only to ASCII digit-only tokens that:

- have at least five digits;
- do not start with `0`;
- are not part of an alphanumeric token.

For each eligible token, it emits an FTS5 disjunction containing:

1. the original compact token;
2. the right-grouped adjacent phrase.

Other terms remain conjunctive:

```text
410000 million gallons
  -> ("410000" OR "410 000") AND "million" AND "gallons"

25600 public supply
  -> ("25600" OR "25 600") AND "public" AND "supply"

02139 postal district
  -> "02139" "postal" "district"

ZX410000 equipment model
  -> "zx410000" "equipment" "model"

2005 reporting year
  -> "2005" "reporting" "year"
```

If no token is eligible, the candidate returns the current compiler output byte-for-byte. It only
uses explicit `AND` when at least one numeric disjunction is present.

With the configured FTS5 tokenizer, the grouped phrase means adjacent tokens, not a specific
separator. The phrase `"410 000"` therefore matches `410,000`, `410 000`, `410-000`, and
`410/000`; it does not match `410` and `000` separated by another token. That is the explicit
candidate boundary.

The candidate changes query compilation only. It does not alter indexed text, the FTS table,
tokenizer, ranking order, Publication activation, result DTOs, or Search limit behavior.

## Architecture

```text
protocol lock
  + development manifest/PDF
  + holdout manifest/PDF
  + E1 manifest
            |
            v
 strict validation + immutable snapshots
            |
    +-------+-------------------+
    |                           |
    v                           v
 current policy            numeric-grouping-v1
 fresh workspaces          fresh workspaces
    |                           |
 normal ingest -> active Publication projection
    |                           |
 one normal FTS5 MATCH Search + evidence-only Ask
    +-------------+-------------+
                  |
 ordered stable-locator comparison
 + transformation invariants
 + E1 per-query regression gates
                  |
 reviewed comparison artifact
```

The public `run_retrieval_evaluation(manifest_path)` function, E1 CLI, and report schema remain
unchanged. The public function delegates to a private evaluator entry point fixed to `current`.
A narrow comparator invokes that private entry point for:

- development with `current` and candidate;
- holdout with `current` and candidate;
- full E1 with `current` and candidate.

Each evaluator call retains its own two-fresh-workspace determinism check.

## Metrics And Gates

E1 locator Recall@k and MRR definitions remain unchanged. Numeric challenge promotion uses
query-level gates because every positive query has exactly one relevant page.

`numeric-grouping-v1` is promotable only when:

1. every evaluator run passes integrity and determinism checks;
2. every development and holdout positive has `first_relevant_rank == 1`;
3. every development and holdout lexical-confuser/out-of-corpus query has no hit;
4. grouped-document positives improve from current miss to candidate rank 1;
5. compact-document, leading-zero, alphanumeric-identifier, and short-number controls have
   identical ordered results under current and candidate;
6. non-adjacent-token controls remain no-hit, while comma-, space-, and hyphen-adjacent controls
   match as the documented tokenizer-equivalent phrase;
7. every query without an eligible compact integer compiles byte-for-byte identically under both
   policies;
8. every full-E1 query with identical compiled text retains identical ordered locator tuples, Ask
   status, and per-query fields;
9. `water-answerable-01` is the only allowlisted E1 delta and must improve from no hit to rank 1;
10. E1 aggregate Recall@1/3/5 and MRR@5 do not decrease;
11. one Search call still executes exactly one FTS5 `MATCH` statement;
12. no dependency, index, model, network access, migration, or additional Search query is added;
13. human and JSON semantic fields are deterministic and public-safe; runtime duration is
    informational and excluded from semantic equality;
14. integrity failure, trustworthy candidate rejection, and passing candidate are distinct states.

The comparison report is a total result with:

- `integrity_status=failed`, `candidate_status=not_recorded` for invalid input or execution;
- `integrity_status=passed`, `candidate_status=rejected` when trustworthy runs fail a gate;
- `integrity_status=passed`, `candidate_status=passed` when all gates pass.

Errors are converted to fixed, redacted causes without absolute paths or tracebacks.

## CLI

Add:

```text
mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json
```

`--json` emits one object. `--db` remains invalid because the evaluator owns temporary workspaces.
The candidate ID and semantic revision come only from the validated protocol lock. The command
accepts no candidate override, output path, provider, URL, model, SQL, regex, import path,
tokenizer expression, or executable command.

The JSON schema is `mke.retrieval_numeric_comparison.v1`. Required top-level fields are:

- `schema_version`, `protocol_id`, `candidate_id`, and `candidate_revision`;
- `integrity_status` and `candidate_status`;
- `development`, `holdout`, and `e1` current/candidate semantic observations;
- `compiled_queries`, `gates`, `integrity_failures`, and `duration_ms`;
- `limitations`.

Each of `development`, `holdout`, and `e1` has:

```json
{
  "manifest_id": "string",
  "current": {"...": "semantic E1 observation"},
  "candidate": {"...": "semantic E1 observation"}
}
```

A semantic E1 observation contains exactly:

- `status`, `quality_status`, `documents`, `queries`, `answerable`, and `unanswerable`;
- `metrics`, using the E1 metric object `{value, sum, count}`;
- `category_counts`;
- ordered `results`, using the complete E1 per-query result shape and stable locator shape;
- `integrity_failures`, which must be empty for a trustworthy comparison.

It excludes `duration_ms` and temporary paths.

`compiled_queries` is ordered by partition, then manifest query order. Each entry is exactly:

```json
{
  "partition": "development|holdout|e1",
  "query_id": "string",
  "current": "compiled FTS5 text",
  "candidate": "compiled FTS5 text",
  "eligible_tokens": ["string"]
}
```

`gates` uses this fixed order:

1. `protocol_integrity`;
2. `all_evaluations_deterministic`;
3. `development_grouped_improves`;
4. `development_controls_preserved`;
5. `development_non_adjacent_no_hit`;
6. `holdout_grouped_improves`;
7. `holdout_controls_preserved`;
8. `holdout_non_adjacent_no_hit`;
9. `noneligible_compilation_identity`;
10. `e1_unrelated_exact`;
11. `e1_water_answerable_rank_1`;
12. `e1_aggregate_non_regression`;
13. `single_match_per_search`;
14. `scope_fence`.

Every gate is exactly `{gate_id, status, observed, required, next_step}`. `status` is `passed` or
`failed`; the other values are bounded public strings.

Every integrity failure is exactly `{problem, cause, next_step, subject_id}`. Problems and fixed
redacted mappings are:

| Situation | `problem` | `cause` | `next_step` |
|---|---|---|---|
| supplied protocol file missing | `retrieval_numeric_protocol_invalid` | `protocol file is missing` | `restore_numeric_protocol` |
| invalid protocol, version, path, or candidate | `retrieval_numeric_protocol_invalid` | `protocol validation failed` | `fix_numeric_protocol` |
| bound manifest or fixture identity mismatch | `retrieval_numeric_fixture_invalid` | `protocol-bound input identity mismatch` | `restore_numeric_protocol_inputs` |
| one partition/policy E1 evaluation fails | `retrieval_numeric_evaluation_incomplete` | `<partition> <policy> evaluation failed` | `inspect_numeric_comparison_inputs` |
| repeated observation differs | `retrieval_numeric_nondeterministic` | `numeric comparison results were not deterministic` | `inspect_numeric_comparison_runtime` |
| gate computation or unexpected execution fails | `retrieval_numeric_comparison_incomplete` | `numeric comparison evaluation failed` | `inspect_numeric_comparison_inputs` |
| report rendering fails | `retrieval_numeric_comparison_incomplete` | `numeric comparison report could not be rendered` | `inspect_numeric_comparison_inputs` |

`<partition>` and `<policy>` are allowlisted identifiers. `subject_id` is either an allowlisted
protocol/query/document identifier or `null`.

`limitations` is the fixed ordered list:

```text
public_holdout_not_blind
small_engineering_challenge_set
ascii_compact_integers_only
tokenizer_adjacent_separator_equivalence
no_general_retrieval_quality_claim
```

Human output starts with `mke eval retrieval-numeric`, then prints protocol/candidate identity and
the two statuses before gate or failure details.

Exit codes:

- `0`: trustworthy comparison and all promotion gates passed;
- `1`: trustworthy rejected candidate, integrity failure, or renderer failure;
- `2`: invalid CLI usage.

Missing required `--protocol` is usage exit `2`. A supplied path whose file is missing or invalid is
an evaluation result with `failed/not_recorded`, exit `1`, empty stderr, and no traceback or path
leakage. A trustworthy rejection is `passed/rejected`, exit `1`.

`--help` states that the command is comparison-only, PR 1 leaves the runtime default unchanged, the
holdout is public rather than blind, and promotion is conditional.

## Comparison Artifact

The reviewed artifact contains:

- protocol, manifest, fixture, candidate, environment, and complete source identities;
- semantic candidate revision `1`, independent of Git commit ancestry;
- current and candidate ordered per-query results for development, holdout, and E1;
- compiled-query pairs for every development, holdout, and E1 query;
- all gate observations and verdicts;
- explicit public-holdout and narrow-claim limitations.

The checked-in artifact excludes duration. Validation recomputes identities and aggregate
consistency, then compares its canonical semantic payload with a fresh observed comparison.
Compiled queries, ordered results, metrics, gates, and final status must match. It does not accept
raw score equality as a substitute for semantic gate validation.

Source identity is a sorted content identity for the complete `src/mke/**/*.py` set and does not
require pre-squash commits to remain reachable. Validation must pass in a depth-1 fresh clone after
a squash landing.

## Promotion And Rollback

The conditional promotion PR must:

- reference a valid passing comparison artifact;
- add an ADR describing the evidence and bounded behavior;
- change the default policy identifier to `numeric-grouping-v1`;
- add an allowlisted `RuntimeConfig.retrieval_query_policy`;
- expose the same owner-controlled global CLI/MCP startup option:
  `--retrieval-query-policy {current,numeric-grouping-v1}`;
- retain `current` as the tested rollback value during the Pilot;
- require no database migration or index rebuild;
- rerun full tests, E1, numeric comparison, product proof, demo, lint, type checking, build, and
  installed-wheel CLI/MCP Search checks.

Rollback starts CLI/MCP with `--retrieval-query-policy current`; an emergency code rollback may
also restore the `current` default identifier. Invalid policy values are usage errors and never
reach engine construction.

Examples place the global option before the subcommand:

```text
mke --retrieval-query-policy current --db PATH search QUERY
mke --retrieval-query-policy current --db PATH mcp --allowed-root ROOT
```

## Remaining Limits

- The holdout is independent and locked but public, not blind.
- Five answerable controls per partition remain a small engineering challenge set, not statistical
  evidence of general retrieval quality.
- The candidate only handles ASCII compact integers with conventional three-digit grouping and
  treats tokenizer-adjacent punctuation variants as equivalent.
- Locale-specific separators, decimals, signs, scientific notation, dates, account numbers, and
  arbitrary identifier semantics remain outside the claim.
- E1 and E2 page qrels require a new protocol if Evidence segmentation changes.
