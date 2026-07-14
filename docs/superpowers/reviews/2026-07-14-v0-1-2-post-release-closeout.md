# v0.1.2 Post-Release Closeout

Status: published and verified.

## Scope

This record closes the verified `v0.1.2` publication after the release candidate, authoritative
review, final-main verification, annotated tag, GitHub Release, and public-archive smoke completed.
It records facts only and does not alter the published release.

## Non-Scope

- No package-registry publication or deployment occurred.
- No candidate wheel or additional GitHub Release asset was uploaded.
- No OCR, HTTP, UI, hosted service, retrieval runtime promotion, dependency, database, runtime,
  or public-contract change is included.
- The checked-in `docs/releases/v0.1.2.md` remains the immutable source of the published
  GitHub Release body.

## Git And GitHub Provenance

- Release PR: [#69](https://github.com/iTao-AI/multimodal-knowledge-engine/pull/69)
- Squash-merge commit: `e4be0eee11c671e31c17af8b698bf7921cfc045f`
- Annotated tag: `v0.1.2`
- Tag object SHA: `3f693502e87367d2c984fb9a04db83e98b68bab6`
- Peeled tag target: `e4be0eee11c671e31c17af8b698bf7921cfc045f`
- GitHub Release:
  <https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.2>
- Published: `2026-07-14T09:11:16Z` by `iTao-AI`
- Release state: latest at publication, non-draft, non-prerelease, with zero extra assets

## Final-Main Gate

The complete release gate passed on the exact clean merge commit. It included full pytest, Ruff,
Pyright, build, product proof, demo, local knowledge proof, Evidence provenance proof, release
presentation audit, the corrected E2 observation, all seven canonical evaluation validators, the
same-wheel Python 3.12/3.13 proof, and installed-wheel smoke.

The final-main candidate receipt:

- used schema `mke.candidate_artifact_receipt.v1`;
- bound `source_commit` to
  `e4be0eee11c671e31c17af8b698bf7921cfc045f`;
- bound wheel SHA-256
  `ca4c978ec6fc8ffab3e04375ab2500b39584e2b5fcfa333bb0cb0cbd76b223dd`;
- had canonical receipt SHA-256
  `8412d0b1b879a31c94f7c09e805dc6d54dd869ebe08342246073e5eff28a35da`.

## Public Archive Verification

- Archive: `multimodal-knowledge-engine-0.1.2.tar.gz`
- Bytes: `3334646`
- SHA-256:
  `19004992527b0d7244bf81756eb0d40302720942473cd3a8fcb1211ef46ef5e0`
- Locked sync: passed
- Product proof: `8/8` passed
- Demo: passed
- Local knowledge proof: passed
- Evidence provenance proof: passed

The public archive contained package identity `0.1.2` and no private or candidate artifact.

## Downstream Evidence Boundary

The independent downstream integration remains bound to the pre-release candidate documented in
the release notes. It did not validate the final `v0.1.2` wheel and does not prove production
adoption, hosted deployment, real-user outcomes, or an MKE CI dependency.

## Remaining Boundaries

PyPI and other registries remain unpublished. No deployment occurred. PDF OCR remains independent
follow-up work and is not a `v0.1.2` capability.

## Verdict

`v0.1.2` is published and verified. The release closeout is complete.
