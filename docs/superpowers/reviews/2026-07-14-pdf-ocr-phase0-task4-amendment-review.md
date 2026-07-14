# PDF OCR Phase 0 Task 4 Amendment Review

Date: 2026-07-14

Status: implementation complete; targeted authority re-review pending. Task 5 has not started.

## Scope

This amendment covers model-file provenance validation, repository authority for the committed
provider-startup receipt, and the pinned PaddleOCR-VL 1.6 direct-top-level vendor envelope. It does
not select a provider, define a scorecard, change production PDF intake, or promote OCR into a
runtime contract.

## Resolution

- Each model file is opened without following links where supported, read once through one bounded
  descriptor-owned stream, and bound to inventory metadata, descriptor metadata, exact size,
  upstream Git blob or LFS identity, receipt SHA-256, and post-read path identity.
- The content-addressed model tree is sealed while still in private staging, then every file,
  component digest, and aggregate digest is recomputed from descriptor-bound reads before atomic
  final publication. The canonical receipt is published only after the sealed final identity is
  confirmed.
- The provider-startup authority path derives package and model receipt identities from their
  canonical committed bytes and derives passed-provider text identity from the normalized
  `english-scan` page-1 protocol truth. Provider order, profile, fixture, network isolation, and
  PaddleOCR-VL artifact inventory and digests are verified in the same path.
- Provider startup now runs from a fresh offline environment installed from the exact MKE wheel
  bound by the package receipt. The controller rejects repository or `PYTHONPATH` source shadows
  and records the exact Python version, distribution version, wheel digest, installed module
  origin, isolated-mode result, and packaged vendor-fixture digest.
- The PaddleOCR-VL adapter no longer accepts the unobserved nested result envelope. It accepts only
  the observed pinned direct-top-level schema represented by a public-safe sanitized fixture,
  validates exact keys and bounded values, admits supported prose labels only, and requires the
  normalized Markdown to equal normalized validated block content. Vendor-only paths and settings
  do not enter the project-owned OCR result.

## Fresh Implementation Evidence

One current MKE wheel was built at SHA-256
`529a49b33ffce5af8243f9b50f5050d5b0e3a28ada9c13dabb8cd723549e6f47`. Call-owned copies of the
retained third-party wheelhouses replaced only their MKE distribution, and the complete offline
matrix passed all 16 cells on exact Python 3.12.13 and 3.13.12. The resulting canonical package
receipt SHA-256 is `3b8014d0988b3b657fb2ada23ae78ac7d48e4f63eafd4a7074e4c6976d0896ff`.

With external egress denied by the operating system and the canary blocked, cache-only startup from
that exact installed wheel and the retained model evidence returned the exact fixture truth for
Apple Vision, PaddleOCR-VL, and PP-OCRv6 medium. The observed durations were 291 ms, 18,951 ms, and
8,688 ms respectively. The canonical provider-startup receipt SHA-256 is
`e271df496688e4960cf9f117f63fca8f7afc85d995d15614317d1d291b5f3838`. These are bounded single-page
startup observations, not OCR quality or production claims.

The retained PaddleOCR-VL evidence remains exactly two regular files: a 51-byte Markdown artifact
and a 2,458-byte JSON artifact. Their SHA-256 values, direct top-level keys, and parsing-block keys
are recorded in the canonical provider-startup receipt. The amended adapter passed the same strict
prose-only envelope during the fresh real-provider run.

The retained model receipt remains SHA-256
`3d1e8c45b7ed0c817acaeda3f51954b463016763690e09ca1f23162042219d6e`; the controller rehashed the
sealed 34-file, 2,201,640,507-byte snapshot before startup. No package or model was downloaded during
this targeted repair.

## Remaining Gate

Targeted authority re-review must accept this amendment before Task 5 begins. No scorecard,
provider selection, production OCR surface, dependency change, or external publication is included.
