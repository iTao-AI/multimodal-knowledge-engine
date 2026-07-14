# PDF OCR Phase 0 Task 4 Amendment Review

Date: 2026-07-14

Status: targeted authority re-review accepted at implementation HEAD
`040cb6cea2439f5f9d46b09862b17fa1fee59e39`; CLEARED FOR TASK 5. The independent review
recorded `158 passed, 5 warnings`, with Ruff, Pyright, diff check, and all three canonical receipt
SHA-256 identities passing. Task 5 had not started at this acceptance boundary.

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
  `english-scan` page-1 protocol truth. Before creating a venv, it verifies every supplied
  wheelhouse filename, byte count, and SHA-256 through bounded descriptor reads against the exact
  PaddleOCR-VL candidate inventory. It then binds the exact passed Python 3.13/base cell and
  requires the fresh installed distribution map to match that cell after the same provider import
  boundary and a successful `pip check`.
- Provider startup now runs from a fresh offline environment installed from the exact MKE wheel
  bound by the package receipt. The controller rejects repository or `PYTHONPATH` source shadows
  and records the exact Python version, distribution version, wheel digest, installed module
  origin, isolated-mode result, candidate, surface, wheelhouse identity, and installed package-set
  identity.
- Historical vendor evidence and fresh startup evidence are separate. The top-level
  `observed_vendor_fixture` records the retained authorized two-file observation and its schema;
  fresh provider entries contain only facts produced by the installed-wheel run and do not claim
  historical artifact bytes or digests as current-run output.
- Provider startup owns cleanup from the first staging-directory creation. Environment setup and
  receipt write failures return stable errors and remove only call-owned temporary state. A new
  receipt is first fsynced to a call-owned temporary file, all staging cleanup is then completed
  and verified, and only then may an atomic replace update the canonical receipt. Cleanup or
  temporary-file removal failure returns a stable cleanup error without overwriting prior
  canonical evidence; cleanup attempts are not skipped by a temporary-file error.
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
receipt SHA-256 is `91c782fb147fbb1f59f2c2f447f79d8c8c82188860b2b6afeb4455c92630fcbb`.

With external egress denied by the operating system and the canary blocked, cache-only startup from
that exact installed wheel and the retained model evidence returned the exact fixture truth for
Apple Vision, PaddleOCR-VL, and PP-OCRv6 medium. The observed durations were 328 ms, 15,118 ms, and
9,536 ms respectively. The canonical provider-startup receipt SHA-256 is
`b51dccfc532d8866e49f8325ccb5684b755a63c0356198d793c63b7cad4a7d5f`. These are bounded single-page
startup observations, not OCR quality or production claims.

The retained PaddleOCR-VL observation remains exactly two regular files: a 51-byte Markdown
artifact and a 2,458-byte JSON artifact. Its SHA-256 values, direct top-level keys, and
parsing-block keys are recorded separately as `observed_vendor_fixture`. The fresh installed-wheel
run proves that the adapter accepted new provider output under the same strict prose-only schema
and returned the normalized fixture truth; it does not claim that the fresh temporary artifacts
had the retained observation's exact byte identities.

The retained model receipt remains SHA-256
`3d1e8c45b7ed0c817acaeda3f51954b463016763690e09ca1f23162042219d6e`; the controller rehashed the
sealed 34-file, 2,201,640,507-byte snapshot before startup. No package or model was downloaded during
this targeted repair.

## Accepted Boundary

Targeted authority re-review accepted this bounded amendment and cleared Task 5 to generate the
evaluation scorecard through current Publication, Search, Ask, and EvidenceRef contracts. This
acceptance does not select a provider, approve numeric thresholds, authorize production OCR,
change dependencies, or authorize external publication.
