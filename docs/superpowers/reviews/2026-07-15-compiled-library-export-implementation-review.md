# Compiled Library Export v1 Implementation Review

Status: accepted by authoritative targeted re-review at reviewed final HEAD
`a8d4bfd5d31d34b04b7d64993bcf8e0cd4096e19`. This verdict clears only Task 8 Step 8 final
committed-candidate verification after the documentation closure commit.

Review base and merge-base: `a03c2308106ef499c6bd64b0efb1c123d5059f47`.

Reviewed final HEAD: `a8d4bfd5d31d34b04b7d64993bcf8e0cd4096e19`.

Reviewed range:
`a03c2308106ef499c6bd64b0efb1c123d5059f47...a8d4bfd5d31d34b04b7d64993bcf8e0cd4096e19`.

## Scope

The reviewed implementation adds the read-only `mke library export` contract, bounded active
Publication snapshot, canonical Markdown and `mke.evidence_ref.v1` output, descriptor-bound local
publisher, closed CLI response, independent installed-wheel consumer proof, CI workflow, and user
documentation. SQLite remains authority for active Publication facts, EvidenceRef JSONL remains
portable provenance authority, and Markdown remains a readable derivative.

The installed-wheel proof validates the generic portable export contract against Python 3.12 and
3.13 without making LLM Wiki a runtime, CI, or package dependency.

## Authoritative Finding And Resolution

The authoritative review at candidate `2d58a91c53527148d08d7164a9a600abc993e034`
identified one P1 finding: the manifest rename committed the output after pre-commit checks, but the
publisher did not revalidate the committed tree before returning success. A local replacement or
same-inode content mutation in that interval could therefore escape the earlier validation.

Resolution commit `b0a703e3af4aab8c812f35a1dad0eb27ed1be41f` closes that interval while
preserving the manifest as the commit marker:

- every owned regular file is reopened descriptor-relative with `O_NOFOLLOW` where available;
- path and descriptor identity, regular-file type, expected size, and SHA-256 are checked before
  and after the bounded read;
- the temporary manifest ownership record is rebound from `.export-manifest.json.tmp` to
  `export-manifest.json` immediately after rename;
- the rename is the last artifact mutation and commit-marker mutation, followed by a final exact
  inventory, committed-manifest and referenced-content revalidation, and target identity
  revalidation before success; and
- path-identity replacement preserves operator-owned state and returns stable `cleanup_failed`,
  while same-inode, same-size digest drift returns `write_failed` and removes the call-owned tree.

Five real race regressions cover the closed interval:

1. content replacement after the pre-commit inventory and before manifest commit;
2. content replacement after manifest commit and before success;
3. same-inode, same-size content digest drift after manifest commit and before success;
4. committed-manifest replacement after commit and before success; and
5. same-inode, same-size committed-manifest digest drift after commit and before success.

Targeted authoritative re-review accepted the resolution with no remaining implementation
finding in the approved local threat model.

## Evaluation Identity Closure

The final identity closure at `a8d4bfd5d31d34b04b7d64993bcf8e0cd4096e19` changed exactly
these 16 paths, a validator-proven subset of the maximum 21-path allowlist:

- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json`
- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json`
- `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
- `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`
- `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
- `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
- `docs/how-to/evaluate-dense-retrieval.md`
- `docs/how-to/evaluate-hybrid-rrf-retrieval.md`
- `docs/how-to/evaluate-relevance-gate-reranker.md`
- `tests/evaluation/test_relevance_gate_protocol.py`
- `tests/evaluation/test_relevance_gate_workflow.py`
- `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json`
- `tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json`

Across E1 through E3-E, observations, ordered results, metrics, thresholds, gates, diagnostics,
selected profile and candidate, status, and verdict are unchanged. The normalized semantic
projections are equal before and after the identity refresh. No evaluation implementation changed.

## Reviewed-HEAD Verification Evidence

Fresh verification on reviewed HEAD `a8d4bfd5d31d34b04b7d64993bcf8e0cd4096e19` recorded:

| Command | Result |
|---|---|
| `UV_OFFLINE=1 uv run pytest -q` | `2305 passed, 5 skipped, 5 warnings` |
| `UV_OFFLINE=1 uv run ruff check .` | clean |
| `UV_OFFLINE=1 uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `UV_OFFLINE=1 uv build` | passed |
| `UV_OFFLINE=1 uv run mke proof run` | `proof=product status=passed cases=8 passed=8 failed=0` |
| `UV_OFFLINE=1 uv run mke demo --verify` | `result=passed` |
| `UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py` | JSON reported `proof=local_knowledge`, `status=passed` |
| `UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py` | JSON reported `proof=evidence_provenance`, `status=passed` |
| `UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py --python "$PYTHON312" --python "$PYTHON313" --json` | JSON reported `proof=consumer_source_pack`, `status=passed`; explicit Python 3.12 and 3.13 commands were provided |
| `UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .` | `status=ok` |
| `UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py --python "$PYTHON312" --python "$PYTHON313" --json` | Python 3.12 and 3.13 passed against the same wheel |
| `git diff --check a03c230..a8d4bfd` | passed |

The reviewed-range changed-file audit recorded
`60 files changed, 11403 insertions(+), 105 deletions(-)`. The reviewed worktree and index were
clean, and the public-neutral and scope audit passed.

The generic proof aggregate was:

```json
{
  "evidence_schema": "mke.evidence_ref.v1",
  "export_schema": "mke.compiled_library_export.v1",
  "interpreter_count": 2,
  "markdown_format": "mke.compiled_markdown.v1",
  "proof_input_wheel_sha256": "eadd5065b4008b5505bc2806706418e4997483f76b027bdc101b19e9028f6570",
  "schema_version": "mke.compiled_library_export_proof.v1",
  "status": "passed"
}
```

Every command and audit above, including the wheel SHA-256, is evidence only for reviewed HEAD
`a8d4bfd5d31d34b04b7d64993bcf8e0cd4096e19`. The documentation closure commit changes the
candidate identity, so Task 8 Step 8 must freshly rerun the committed-candidate gates, rebuild, and
rerun the generic proof on that new committed HEAD. This digest and the reviewed-head results are
not final committed-candidate authority and must not be reused as such.

## Claim Boundaries

- Package and module version remain `0.1.2`; no `v0.1.3` identity or release was created.
- No OCR promotion, production OCR claim, layout reconstruction claim, MCP change, HTTP surface,
  dependency change, or retrieval-semantic change is included.
- No release, push, pull request, merge, tag, registry publication, artifact upload, or deployment
  occurred.
- LLM Wiki compatibility has not started and is not claimed by this review.

## Verdict

`ACCEPTED` — the reviewed implementation and P1 resolution are cleared only to proceed to Task 8
Step 8 final committed-candidate verification after this documentation closure commit. Task 8
Step 8 is not complete, Task 8 Step 9 remains pending, and this review does not claim authority
closure beyond this gate.
