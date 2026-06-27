# ADR-0007: Numeric Grouping Query Policy

## Status

Accepted for E2 promotion. Default selection superseded by ADR-0008.

## Evidence

The E1 baseline recorded one answerable compact-query/grouped-document miss:
`water-answerable-01` queried `410000`, while the relevant page contained `410,000`. E2 froze
separate development and public-holdout PDFs plus the complete E1 manifest in protocol
`mke.retrieval_numeric_protocol.v1`.

The reviewed `numeric-grouping-v1` comparison artifact had SHA-256
`019ad6aae0d1a46b3784eee64ea7f220488b530daef5ee40f0d7a7d78802d361`, protocol-lock SHA-256
`5ab8505c41a8be561654392f756d78853a52d55a684004ee481c275a6e26f4d9`, and complete source-content
SHA-256 `ba17dad428445548888bd8ebd6f0dc64b3b43594250c401f6a63d34dcca44f8b`.
Artifact integrity passed, the candidate passed, and all 14 promotion gates passed. E1 Recall@1
changed from `0.875000` to `0.937500`; the only ordered E1 result delta was the intended
`water-answerable-01` improvement from no hit to rank 1.

The frozen controls prove compact/grouped matching, compact-document preservation, non-adjacent
rejection, preservation of leading-zero and identifier inputs, one FTS5 `MATCH` per Search, and no
unrelated development, public-holdout, or E1 regression.

The public holdout is independently authored and locked, but not blind. These results are bounded
engineering evidence, not a general retrieval-quality claim.

## Decision

`numeric-grouping-v1` became the default retrieval query policy for normal `KnowledgeEngine`, CLI,
and owner-started MCP composition at the E2 stage. ADR-0008 later superseded only that default
selection; this policy remains the E3-F base compiler and explicit primary rollback.

The policy expands only standalone ASCII digit tokens that contain at least five digits, do not
start with `0`, and are not part of an alphanumeric token, decimal, signed value, date, or
scientific notation. It preserves the compact token and adds its conventional right-grouped
adjacent-token phrase:

```text
410000 million gallons
  -> ("410000" OR "410 000") AND "million" AND "gallons"
```

With the configured tokenizer, the phrase proves token adjacency rather than a comma-specific
separator. It therefore matches tokenizer-equivalent comma, space, hyphen, and slash separators.
Queries without an eligible token compile byte-for-byte identically to `current`.

The allowlisted owner startup selector is:

```text
--retrieval-query-policy {current,numeric-grouping-v1}
```

`current` remains the operational rollback identifier. The selector is stored in typed
`RuntimeConfig` and applied before engine construction. It is available to normal CLI and
owner-started MCP composition, but is not exposed through MCP tool inputs or request-time DTOs.
`mke eval ...` rejects the selector because evaluation policy is protocol-owned.

Switching policies changes query compilation only. It requires no database migration, Publication
change, index rebuild, or Evidence rewrite.

## Rejected Alternatives

- Replacing compact tokens with grouped phrases would regress compact document text.
- A second Search, fusion, reranking, embeddings, or a vector index is not supported by E1
  evidence.
- Request-time policy overrides would move owner policy into untrusted request input.
- CJK, semantic, OCR, ASR, and segmentation changes are outside the E2 evidence boundary.
- Database schema or tokenizer changes are unnecessary.

## Limitations

The policy does not claim locale-specific grouping, decimals, signs, scientific notation, dates,
identifier interpretation, semantic equivalence, or punctuation-specific matching. A future
policy requires a new frozen protocol, artifact, and ADR-backed promotion.
