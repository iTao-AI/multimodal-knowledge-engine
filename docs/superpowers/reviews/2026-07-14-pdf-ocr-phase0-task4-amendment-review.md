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
- The provider-startup authority path derives package and model receipt identities from their
  canonical committed bytes and derives passed-provider text identity from the normalized
  `english-scan` page-1 protocol truth. Provider order, profile, fixture, network isolation, and
  PaddleOCR-VL artifact inventory and digests are verified in the same path.
- The PaddleOCR-VL adapter no longer accepts the unobserved nested result envelope. It accepts only
  the observed pinned direct-top-level schema represented by a public-safe sanitized fixture,
  validates exact keys and bounded values, admits supported prose labels only, and requires the
  normalized Markdown to equal normalized validated block content. Vendor-only paths and settings
  do not enter the project-owned OCR result.

## Fresh Implementation Evidence

With external egress denied by the operating system and the canary blocked, cache-only startup from
the retained package and model evidence returned the exact fixture truth for Apple Vision,
PaddleOCR-VL, and PP-OCRv6 medium. The observed durations were 212 ms, 12,766 ms, and 8,759 ms
respectively. These are bounded single-page startup observations, not OCR quality or production
claims.

The retained PaddleOCR-VL evidence remains exactly two regular files: a 51-byte Markdown artifact
and a 2,458-byte JSON artifact. Their SHA-256 values, direct top-level keys, and parsing-block keys
are recorded in the canonical provider-startup receipt. The amended adapter passed the same strict
prose-only envelope during the fresh real-provider run.

## Remaining Gate

Targeted authority re-review must accept this amendment before Task 5 begins. No scorecard,
provider selection, production OCR surface, dependency change, or external publication is included.
