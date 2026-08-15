# Native Evidence Showcase Implementation Plan

Status: Complete

## Goal

Add a deterministic, read-only documentation projection of the existing MKE Evidence lifecycle.
The projection consists of static HTML/CSS, three canonical 1600x1000 PNG frames, a SHA-256-bound
manifest, and provider-free standard-library guards. It does not add a Web product, server,
runtime behavior, dependency, schema, or domain contract.

## Fixed contract boundary

- Use the existing synthetic local-knowledge, short-video, and compiled-library-export proof
  fixtures and the canonical `Source`, `Run`, `Publication`, `Evidence`, and consumer vocabulary.
- Show only current contract fields: active-publication observation counts, `mke.evidence_ref.v1`
  provenance, page or `timestamp_ms` locators, Search v2 `selection.status`, CLI/stdio MCP/
  Compiled Library Export consumers, and the existing failed-ingest and
  `insufficient_evidence` fields.
- Keep all identifiers and frame state explicitly synthetic/demo; do not claim runtime adoption,
  external providers, or production data.
- Keep the protected retrieval-coverage worktree and unrelated maintenance untouched. Do not push,
  create a PR, merge, release, deploy, or clean remote/local resources.

## Implementation

1. Add `scripts/generate_evidence_workspace.py` with deterministic frame data, static HTML/CSS
   generation, PNG rendering through the existing browser CLI, manifest generation, and strict
   standard-library verification of dimensions, hashes, inventory, source tree, and disclosure.
2. Add focused tests before implementation (RED/GREEN) for the three-frame inventory, exact
   viewport, manifest/hash binding, current contract vocabulary, and private-marker hygiene.
3. Generate exactly `evidence-workspace-overview.png`, `evidence-publication-search.png`, and
   `evidence-insufficient-recovery.png` under `docs/evidence-workspace/`; keep HTML/CSS static and narrow
   layout accessible with visible focus, readable contrast, and no document overflow.
4. Reorder `README.md` and `README_CN.md` around value, lifecycle relation, normal/failure frames,
   engineering judgments, quick verification, and detailed proof/contracts without changing
   release history or existing proof claims.

## Verification gates

- Focused showcase tests: RED observed before implementation, then GREEN.
- Static browser QA at 1600x1000 and a narrow viewport: text/overflow/focus/contrast/console.
- Existing public/docs/hygiene validators, Ruff, Pyright, build, product proof, demo verification,
  and the environment-independent full suite as warranted by the changed generator/README surface.
- `git diff --check`, exact-path diff review, private-marker scan, clean worktree, and one semantic
  atomic local commit.

## Bounded repair

- Align the publication-search frame to one visible timestamp Evidence result, with
  `selection.returned=1`, `active_evidence_count=4`, and matching provenance.
- Embed the three canonical PNGs in both README first layers, add per-asset route/state and
  uniform asset metadata to the manifest, and naturalize only the Chinese first layer.
- Keep the repair docs-only and provider-free; do not change runtime, domain, schema, dependency,
  protected worktrees, or remote state.
