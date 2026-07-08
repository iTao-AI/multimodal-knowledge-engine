# v0.1.1 Release Closeout Review

## Status

- Review date: 2026-07-08.
- Reviewed commit: `b69ec1a0c1a7d1e40947c8a68fe3bead03d6b55e`.
- Scope: `v0.1.1` release-process documentation and presentation-audit enforcement.
- Result: both authoritative P1 findings were reproduced and remediated with regression tests.
- First targeted re-review: one P1 finding, remediated below.
- Follow-up targeted re-review: pending.
- Full review: not repeated after this focused remediation.

The implementation history is recorded in the
[v0.1.1 Release Closeout Implementation Plan](../plans/2026-07-08-v0-1-1-release-closeout-implementation.md).
Current release instructions are in [Verify The Release](../../how-to/verify-release.md).

## Findings And Resolution

| Severity | Finding | Resolution | Regression evidence |
|---|---|---|---|
| P1 | Stage 2 was described both as part of the final release-candidate branch and as a mandatory separate branch after Stage 1 merged. | Stage 1 and Stage 2 may run on the same final release-candidate branch. After merge, the complete final gate runs again on the resulting `main` commit before separately authorized tag and GitHub Release actions. | The audit rejects the stale sentence requiring Stage 2 to run from a separate branch after Stage 1 merges. |
| P1 | Current release-facing commands used `--wheel dist/*.whl`, but the consumer-smoke CLI accepts one wheel path and stale build outputs can make the wildcard expand to multiple arguments. | README, README_CN, the `v0.1.1` release notes, and the verification guide name `dist/multimodal_knowledge_engine-0.1.1-py3-none-any.whl` exactly. | The audit rejects wildcard consumer-smoke wheel selection in all four current release-facing files and confirms the historical `v0.1.0` record is outside the rule. |
| P1 | The first wildcard regression used a single-line command, while the real release docs split `release_consumer_smoke.py` and `--wheel` across lines; the regex therefore missed multiline regressions. | The audit directly rejects `dist/*.whl` in the same four current command documents, independent of command line wrapping. | A multiline command matching the real docs failed before the fix (`1 failed`) and passed afterward (`1 passed`); all audit tests passed (`51 passed`). |

## Scope Boundary

The remediation changes only release-facing documentation, presentation-audit enforcement, audit
tests, and durable review history. It does not change package identity, MCP, runtime, Search, Ask,
Publication, retrieval evaluation semantics, fixtures, artifacts, or release outputs.

The `v0.1.0` release record remains immutable. No push, PR, tag, GitHub Release, or PyPI
publication is part of this remediation.

## Verification

- RED: `5 failed, 1 passed` for the new focused audit cases.
- GREEN: `6 passed` for the same cases.
- Audit scope guard: a follow-up RED case showed the wildcard rule also matched `CHANGELOG.md`.
  The rule was restricted to the four current command documents; audit tests then passed
  (`50 passed`) and the presentation audit returned `status=ok` with zero violations.
- Targeted release/version/consumer-smoke suite: `80 passed`.
- Full pytest after follow-up remediation: `1328 passed, 5 skipped`. Ruff passed. Pyright reported
  zero errors, warnings, or information messages. The `0.1.1` sdist and wheel built successfully
  in the release-closeout gate.
- Installed-wheel consumer smoke: `status=passed`, `version=0.1.1`; install, identity, product
  proof, demo, CLI, and MCP steps passed.
- Product proof: `8 passed, 0 failed`. Demo and local knowledge proof passed, including cited Ask
  and zero-citation `insufficient_evidence` refusal behavior.
- E1 through E3-E canonical validators passed.
- Relative links, public-boundary and stale-wording scans, and `git diff --check` passed.
- First targeted re-review multiline RED/GREEN: `1 failed` before the fix, then `1 passed`; audit
  tests: `51 passed`.
