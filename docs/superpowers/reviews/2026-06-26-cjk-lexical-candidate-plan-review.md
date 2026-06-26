# CJK Lexical Candidate Plan Review

Status: planning review complete for E3-B handoff. Implementation has not started.

Review date: 2026-06-26

Reviewed inputs:

- `main@bf7929694d91181dad9903eb001f816810871786`
- E3-A design, plan, implementation review, and canonical artifact
- current retrieval query policy and SQLite FTS projection implementation
- SQLite FTS5 tokenizer documentation for the built-in `trigram` tokenizer
- development-only local probes over the E3-A development partition

## Decision

Proceed with one bounded E3-B candidate:

`cjk-trigram-overlap-v1`, revision `1`

The candidate is off-default and comparison-only. It uses the current retrieval path unless the
current compiler returns an empty query. Only compiled-empty queries fall back to the CJK trigram
projection and overlap scorer.

## Findings And Resolutions

### 1. Raw trigram search is too broad for E3-B

Finding: A raw trigram `OR` query can recover Chinese pages, but it is a broad candidate generator,
not a final ranking policy. If used directly, it can over-credit substring overlap and create noisy
matches.

Resolution: Use trigram only to create a candidate pool. The final result must pass a deterministic
overlap filter and ranker over frozen page text.

### 2. Applying the candidate to every query risks scope creep

Finding: Running trigram-overlap for every query turns E3-B into a general replacement ranking
strategy and may change mixed Chinese-English, identifier, and numeric behavior that E2 already
protected.

Resolution: The candidate is a compiled-empty fallback. Non-empty current queries preserve the
current `numeric-grouping-v1` path.

### 3. Embedding, hybrid retrieval, RRF, reranker, and query rewrite are premature

Finding: The E3-A artifact justifies a lexical coverage candidate. It does not prove that semantic
retrieval or fusion is required yet.

Resolution: E3-B remains deterministic, model-free, local, and lexical. Dense/vector/fusion work
remains blocked until E3-B produces a canonical comparison artifact.

### 4. Tokenizer availability must be proven, not assumed

Finding: The local SQLite runtime supports `tokenize='trigram'`, but CI and installed-wheel
environments must prove the same support.

Resolution: The plan requires a Python 3.12/3.13 installed-wheel tokenizer probe. Unsupported
runtimes fail closed with a stable error.

### 5. Candidate evidence must be independently replayable

Finding: E3-A needed multiple hardening rounds around scorer replay and artifact validation. E3-B
has the same risk because it records scores and rankings.

Resolution: The E3-B validator must rebuild active Evidence, rebuild the trigram projection, rerun
the overlap scorer, recompute metrics/gates, and reject coordinated artifact tampering.

## Rejected Alternatives

| Alternative | Reason rejected |
|---|---|
| Query-only CJK expansion against current FTS5 table | Indexed token boundaries remain incompatible; this does not fix Chinese-only lexical coverage. |
| Replace runtime Search with trigram FTS5 | Too broad for E3-B and would alter E1/E2/default behavior before candidate evidence exists. |
| Add `jieba` or another tokenizer dependency | Adds packaging/license/runtime surface without evidence that external segmentation is necessary for the first lexical candidate. |
| Start with embeddings/vector search | E3-A failure evidence first points to empty lexical compilation, not semantic complementarity. |
| Port RAG-OCR retrieval code | High architecture contamination risk; MKE should use legacy experience only as test ideas, not code migration. |

## Review Conclusion

The plan is coherent and bounded. It gives E3-B a defensible market-facing retrieval improvement
path without compromising the project's core Evidence lifecycle and deterministic proof posture.

Next action: hand the plan to the execution window for a TDD implementation branch. The execution
window should stop at a clean local branch and return evidence for planning-window review before
push or PR.
