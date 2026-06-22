# Evaluate The Numeric Retrieval Candidate

Use the frozen E2 protocol to compare the off-default `numeric-grouping-v1` query policy with the
current policy:

```bash
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json
```

PR 1 is comparison-only. It does not change normal Search or Ask behavior; the runtime default
remains `current`.

JSON output:

```bash
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json | python -m json.tool
```

The protocol binds the development and holdout manifests/PDFs, the complete E1 manifest,
candidate ID `numeric-grouping-v1`, semantic candidate revision `1`, dependency identities,
retrieval execution source identities, and the expected SQLite schema identity. One immutable
protocol snapshot feeds all six observations, compiled queries, and gates. The evaluator runs
development, holdout, and E1 under both policies in fresh temporary workspaces.

## Candidate Boundary

The candidate expands only standalone ASCII digit tokens that:

- contain at least five digits;
- do not start with `0`;
- are not alphanumeric identifiers, decimals, signed values, dates, or scientific notation.

For example:

```text
410000 million gallons
  -> ("410000" OR "410 000") AND "million" AND "gallons"
```

The grouped alternative is an FTS5 adjacent-token phrase. It matches tokenizer-equivalent comma,
space, hyphen, and slash separators. It does not match `410` and `000` separated by another token.
Queries without an eligible token compile byte-for-byte identically under both policies.

## Interpret The Result

- `integrity_status=failed`, `candidate_status=not_recorded`: the protocol, input identity,
  evaluation, determinism, gate calculation, or rendering failed.
- `integrity_status=passed`, `candidate_status=rejected`: the comparison is trustworthy, but at
  least one promotion gate failed.
- `integrity_status=passed`, `candidate_status=passed`: all 14 bounded promotion gates passed.

Exit `0` means a trustworthy passing candidate. Exit `1` means either a trustworthy rejection or
an integrity failure. Exit `2` means invalid CLI usage. `--db` and candidate overrides are
rejected because the protocol owns temporary workspaces and candidate identity.

The checked-in comparison records `integrity_status=passed`, `candidate_status=passed`, and 14/14
passing gates. E1 Recall@1 changes from `0.875000` to `0.937500`; the only E1 result delta is
`water-answerable-01`, which changes from no hit to rank 1.

The last two gates are evidence-backed. `single_match_per_search` counts the actual FTS5 `MATCH`
statements traced for every Search call. `scope_fence` checks the protocol-bound dependency and
execution identities plus the observed SQLite schema and local PDF/sidecar provider identities.

## Validate The Reviewed Artifact

```bash
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/numeric-comparison.json

uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/numeric-comparison.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
```

The artifact binds the protocol, manifests, fixture identities, complete `src/mke/**/*.py`
content identity, environment, compiled queries, ordered per-query observations, metrics, gates,
and verdict. Validation independently checks every nested field, type, order, locator/result
relationship, recomputed metric, gate, and verdict before comparing with the fresh observation.
Duration is excluded from semantic equality.

The holdout is independently authored and locked, but public rather than blind. The result is a
small engineering challenge-set observation, not a general retrieval-quality claim.

Promotion is a separate decision. Only a valid passing artifact permits an ADR-backed PR 2 that
changes the runtime default and proves the `current` rollback selector. A rejected artifact
completes E2 without promotion.
