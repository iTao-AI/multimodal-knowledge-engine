# v0.1.2 Release Closeout Design

Status: published and verified. The v0.1.2 release closeout is complete.

Planning base: `main@16fae017ced5fe67da3fae4a01f26e9e9f1084aa`.

## Context

At planning time, the latest published MKE release was `v0.1.1`, while the package metadata on the planning base still reported `0.1.1`. Since that release, the following independently reviewed changes had merged:

- the additive versioned Evidence provenance contract;
- strict `mke.evidence_ref.v1` responses from `list_libraries_v1`, `search_library_v1`, and `ask_library_v1`;
- a standalone external consumer source-pack proof using one wheel in fresh Python 3.12 and Python 3.13 environments;
- owner lifecycle, cancellation, subprocess cleanup, and transition hardening;
- a strict local candidate artifact receipt bound to the exact source commit and proven wheel.

A separate downstream consumer has also completed a minimal integration against a candidate built from the planning-base source commit. This is sufficient evidence to close the current contract slice as a small release without waiting for the separate PDF OCR Phase 0 evaluation.

## Goal

Publish `v0.1.2` as a backward-compatible small release that makes the post-`v0.1.1` Evidence contract, external consumer proof, runtime hardening, and candidate artifact handoff visible through one verified package identity and GitHub Release.

The release must remain runtime-neutral apart from the package version identity. It must not introduce a new product contract while closing the release.

## Included Capabilities

The `v0.1.2` release presentation may claim:

- additive versioned read-only MCP tools:
  `list_libraries_v1`, `search_library_v1`, and `ask_library_v1`;
- strict portable `mke.evidence_ref.v1` values containing source-byte fingerprint, Publication revision, producing Run, and page or timestamp locator;
- fail-closed provenance graph validation;
- a standalone consumer that does not import MKE or inspect SQLite directly;
- real stdio MCP validation with the official MCP SDK;
- exact source-pack fingerprint mapping across fresh stores;
- same-wheel validation in fresh Python 3.12 and Python 3.13 environments;
- bounded controller output, deadlines, process cleanup, and redacted stable failures;
- hardened owner lifecycle, cancellation, subprocess cleanup, and atomic transition boundaries;
- local creation of an exact candidate wheel plus
  `mke.candidate_artifact_receipt.v1`.

Existing `v0.1.1` capabilities remain part of the release: observable Runs, active-Publication-only Search and Ask, page or timestamp Evidence, deterministic product proof, local knowledge proof, CLI, and stdio MCP.

## Non-Goals

This release does not include:

- scanned PDF OCR or any PDF OCR Phase 0 evaluation code;
- layout-aware table or formula extraction;
- dense, hybrid, RRF, or reranker runtime promotion;
- query rewrite, HyDE, or segmentation changes;
- HTTP, UI, service adapters, multi-tenancy, RBAC, or hosted deployment;
- PyPI or another package-registry publication;
- a new dependency, database migration, or public schema revision;
- a claim of production adoption, business decision authority, or real-user outcome.

E3-C dense, E3-D RRF, and E3-E relevance-gate/reranker results remain comparison-only evidence.

## Downstream Validation Boundary

The release notes may link the public Night Voyager integration in
[PR #21](https://github.com/iTao-AI/night-voyager/pull/21).

The permitted claim is:

> An independent downstream consumer validated a candidate artifact produced from
> `main@16fae017ced5fe67da3fae4a01f26e9e9f1084aa` using a strict artifact receipt,
> synthetic fixtures, and the real integration boundary.

The release documentation must also state that:

- the downstream evidence is bound to the pre-release candidate source commit, not to the final `v0.1.2` wheel;
- it does not prove production use, real-user adoption, accepted decision authority, or hosted deployment;
- Night Voyager remains an independent consumer and is not an MKE CI dependency;
- a second Night Voyager lock update is not required when the release closeout changes only package identity, release gates, documentation, and identity-only evidence.

If the release branch changes runtime behavior or a consumed contract, this equivalence no longer applies. Implementation must stop and require a new downstream-validation decision.

## Release Architecture

The release has four ordered stages.

### Stage 1: Release Candidate PR

One isolated release branch updates:

- package and module identity to `0.1.2`;
- the mechanical project identity in `uv.lock`;
- version and release audit expectations;
- installed-wheel consumer-smoke expectations;
- `CHANGELOG.md`;
- bilingual README release presentation;
- `docs/releases/v0.1.2.md`;
- release navigation and verification documentation;
- current release-facing exact wheel commands;
- the overly rigid future-version wording in the historical `v0.1.1` release notes.

The branch may refresh frozen source/provenance identities only when the `0.1.2` version-byte change makes that refresh necessary.

### Stage 2: Candidate Verification

After the release candidate is locally committed and the worktree is clean:

- build exactly one `0.1.2` wheel;
- run installed-wheel consumer smoke outside the source checkout;
- run product, demo, local-knowledge, Evidence-provenance, and external source-pack proofs;
- run the source-pack proof with Python 3.12 and Python 3.13 against the same wheel;
- create a local candidate wheel and strict receipt from the clean committed candidate;
- verify all canonical evaluation and provenance identities;
- run the release presentation and public-boundary audits.

The candidate output remains ignored local maintainer evidence. It is not a Release asset, PyPI artifact, or deployment.

### Stage 3: Final Main Gate

After the release PR merges, rerun the complete Stage 1 and Stage 2 verification set on the exact resulting `main` commit.

No tag or GitHub Release may be created when:

- `main` differs from the verified commit;
- any required check fails;
- the working tree is dirty;
- the built wheel reports an identity other than `0.1.2`;
- the candidate receipt is not bound to that exact commit and wheel;
- runtime or contract drift is detected.

### Stage 4: Tag And GitHub Release

Only after separate publication authorization:

- create an annotated `v0.1.2` tag at the verified final `main` commit;
- create the GitHub Release from the checked-in `v0.1.2` release notes;
- record tag object SHA, tag target commit, publication timestamp, archive filename, and archive SHA-256;
- download the public archive into a clean temporary directory;
- run locked installation, product proof, demo, local knowledge proof, Evidence provenance proof, and appropriate release smoke;
- update the durable closeout record through a separate post-release documentation change if required.

PyPI remains unpublished unless separately designed and authorized.

### Completed Stage 3 And Stage 4 Record

PR #69 was squash-merged as
`main@e4be0eee11c671e31c17af8b698bf7921cfc045f`. The complete final-main gate
passed on that exact clean commit, including the receipt-bound candidate wheel, installed-wheel
smoke, same-wheel Python 3.12/3.13 proof, and all seven canonical evaluation validators.

The annotated `v0.1.2` tag object
`3f693502e87367d2c984fb9a04db83e98b68bab6` peels to the exact final-main
commit. The GitHub Release was published at `2026-07-14T09:11:16Z`, and its public
`multimodal-knowledge-engine-0.1.2.tar.gz` archive contains `3334646` bytes with
SHA-256 `19004992527b0d7244bf81756eb0d40302720942473cd3a8fcb1211ef46ef5e0`.
Locked archive installation, product proof, demo, local knowledge proof, and Evidence provenance
proof passed. The Release contains no extra assets. PyPI publication and deployment did not occur.

## Allowed Change Surface

The release implementation may change:

- `pyproject.toml`;
- `src/mke/__init__.py`, limited to the version literal;
- the mechanical root-package identity in `uv.lock`;
- version identity tests;
- release presentation audit and tests;
- release consumer smoke and tests;
- current release documentation and navigation;
- this spec, the approved implementation plan, and durable release review;
- frozen artifact or protocol identity fields transitively affected by the version/source-byte change.

The implementation must not change:

- MCP request or response schemas;
- Search, Ask, Publication, Run, or Evidence behavior;
- database schemas or persistence semantics;
- owner lifecycle behavior;
- retrieval strategies, metrics, thresholds, gates, corpus, queries, qrels, observations, status, or verdict;
- dependencies or dependency versions;
- OCR files or the OCR Phase 0 worktree;
- CI workflow behavior unless an existing version-bound command demonstrably requires a mechanical `0.1.2` update.

Any change outside the allowed surface is an authority hard stop.

## Evaluation Identity Closure

A package-version edit may change a frozen source identity even when retrieval semantics are unchanged. When that occurs, the release branch may refresh the minimum affected provenance chain only if all of the following hold:

- normalized before/after corpus, queries, qrels, observations, metrics, thresholds, gates, diagnostics, status, and verdict are equal;
- no runtime candidate is promoted or rejected differently;
- canonical validators pass;
- the exact reason for the identity refresh is recorded;
- no unrelated artifact is rewritten.

A semantic difference is not a release-closeout repair. It requires a separate scoped task.

## Documentation Contract

`v0.1.2` release-facing documentation must:

- lead with the Evidence provenance and external-consumer result;
- distinguish shipped runtime from comparison-only retrieval evidence;
- link the provenance proof, consumer source-pack proof, release verification guide, CLI reference, and MCP reference;
- name the exact current wheel instead of using `dist/*.whl`;
- preserve `v0.1.0` and `v0.1.1` tag, commit, archive, and publication history;
- avoid stale pre-release, pending, unmerged, or future-tense release claims;
- contain no private paths, credentials, environment values, raw tracebacks, private workflow, or unverified metrics.

The `v0.1.1` release note may revise only its future upgrade guidance. Its historical release identity and completed verification record remain immutable.

The replacement version policy is:

- backward-compatible fixes, documentation, proofs, operational hardening, and bounded capability additions may continue as `0.1.x`;
- `0.2.0` is reserved for a materially larger product or contract evolution;
- no future feature is assigned a version before its real scope and evidence are known.

## Verification Gates

The release candidate and final merged `main` must pass:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
uv run python scripts/release_presentation_audit.py --root .
uv run python scripts/release_consumer_smoke.py \
  --wheel dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl --json
```

The same-wheel source-pack gate must use explicit Python 3.12 and Python 3.13 interpreters:

```bash
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --json
```

On a clean committed candidate, the maintained candidate-output path must also pass:

```bash
candidate_parent="$(mktemp -d)"
candidate_output="${candidate_parent}/mke-v0.1.2-candidate"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --candidate-output "${candidate_output}" \
  --json
```

Implementation planning must enumerate the repository's canonical E1 through E3-E validators and all current documentation, relative-link, public-boundary, marker, and `git diff --check` gates rather than replacing them with a generic assertion.

The final full pytest gate must be green in a neutral clean worktree. The release does not accept a residual failure waiver.

## Failure Handling

- A version or documentation assertion failure is fixed within the release branch using TDD.
- A source-identity failure may use the constrained identity-closure process above.
- A runtime, schema, dependency, metric, fixture, or semantic failure causes an authority hard stop.
- Missing Python 3.12/3.13 interpreters or offline dependencies are reported as environment blockers; implementation must not silently use a different interpreter, enable network fallback, or weaken the gate.
- A dirty tree, stale candidate output, mismatched wheel, changed final `main`, or receipt mismatch invalidates the artifact evidence.
- Tag or Release publication failure must not move or replace an existing tag. Inspect the external state and resume only with explicit authority.

## OCR And Parallel Development

PDF OCR Phase 0 remains on its independent branch and worktree. It is neither a release prerequisite nor a `v0.1.2` claim.

After `v0.1.2` merges, the OCR branch may require a targeted rebase or identity refresh because package version and release documentation changed. That follow-up must preserve the OCR evaluation's own authority gates and must not retroactively add OCR to `v0.1.2`.

A later OCR or other capability release may use `0.1.3` or another appropriate version based on its actual scope. The version is not predetermined.

## Acceptance Criteria

The release closeout is ready for publication authorization only when:

- package, module, lock, audit, smoke, README, changelog, and release notes agree on `0.1.2`;
- the final diff contains no runtime or contract behavior change;
- full tests, lint, type checks, build, all product and provenance proofs, same-wheel source-pack proof, installed-wheel smoke, evaluation validators, and presentation audits pass;
- the final candidate receipt binds the exact clean commit and exact proven `0.1.2` wheel;
- downstream validation is described with the pre-release candidate boundary;
- OCR and all other non-goals remain excluded;
- the authoritative pre-PR review is clean;
- push, PR, merge, tag, GitHub Release, and post-release closeout occur only at their separately authorized gates.

## Risks

| Risk | Mitigation |
|---|---|
| Downstream validation is misread as final release-wheel validation. | State the exact candidate source commit and explicitly deny final-wheel and production-adoption claims. |
| Version-byte changes invalidate frozen evaluation identities. | Permit only minimal provenance refresh with normalized semantic equality and canonical validators. |
| Release work absorbs an unrelated runtime fix. | Limit `src/mke` changes to the version literal and hard-stop on runtime or contract drift. |
| Historical release records are overwritten. | Preserve all prior tag, commit, archive, and publication facts; change only current navigation and future guidance. |
| OCR is accidentally presented as shipped. | Keep the OCR branch independent and prohibit OCR files and claims in `v0.1.2`. |
| Candidate evidence is confused with publication. | Keep candidate output local and ignored; tag and GitHub Release remain separate authorized actions. |

## Approved Next Step

The v0.1.2 release closeout is complete. Continue routine maintenance through separately scoped
work. PDF OCR remains an independent follow-up and is not retroactively part of v0.1.2.
