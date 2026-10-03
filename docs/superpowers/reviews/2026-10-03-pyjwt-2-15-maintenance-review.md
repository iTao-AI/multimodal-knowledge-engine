# PyJWT 2.15.0 Maintenance Review

Date: 2026-10-03. Focused dependency review: **Approved**, with no blocking findings.
PR: [#130](https://github.com/iTao-AI/multimodal-knowledge-engine/pull/130).
Reviewed dependency candidate: `2b3cd775cf9688d9ee5126521b4d7350525c8a27`.
Comparison base: `3260f892723afb0dba0f46d688539e3f45b46438`.
This record is the only subsequent documentation addition; it does not change runtime inputs.

## Scope And Compatibility

Parsing the complete lock files confirms that only the `pyjwt` package changes,
from 2.13.0 to 2.15.0, including its distribution identities. The dependency path is
MKE -> MCP 1.29.1 -> `pyjwt[crypto]>=2.10.1`; the new version satisfies that requirement.
No application code, public contract, dependency declaration or database schema changes.

The current MKE server uses stdio and constructs FastMCP without HTTP authentication.
Installed MCP JWT calls sign OAuth client assertions in a separate auth extension.
MKE continuation cursors use project-owned HMAC logic and do not call PyJWT.
The installed PyJWT API still supports MCP's explicit-algorithm `jwt.encode` call;
an offline synthetic RS256 assertion round trip also passed.

The [upstream changelog](https://raw.githubusercontent.com/jpadilla/pyjwt/2.15.0/CHANGELOG.rst)
describes stricter key/token validation, JWKS handling and error boundaries. Those changes
matter to JWT/JWKS consumers, but their paths are not initialized by current MKE stdio.
This review does not establish compatibility for future HTTP auth configurations.

## Security Evidence

The repository's pre-update snapshot contains 13 open PyJWT alerts: one critical,
five high and seven medium. Version 2.15.0 is outside all 13 currently published
affected ranges. That version comparison is not evidence that GitHub has closed alerts;
the merge owner must read back their actual states after dependency-graph refresh.

- [GHSA-42vr-xj54-vc7v](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-42vr-xj54-vc7v)
  first receives a released patch in 2.15.0. Deep payload recursion becomes `DecodeError`
  in both direct decode and pre-key-lookup decode; offline probes confirmed both paths.
- [GHSA-gvp8-978c-rx2q](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-gvp8-978c-rx2q)
  still has empty patched-version metadata. Installed source copies `options`; an offline
  reuse probe confirmed the caller's dictionary stays unchanged and an expired token is rejected.
- [GHSA-w6j9-cwv2-h6wq](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-w6j9-cwv2-h6wq)
  has empty current upstream patched-version metadata, whereas the repository snapshot
  names 2.14.0. The changelog links the repair; installed-source inspection and a mixed
  malformed/valid RSA JWK probe confirmed that the invalid key is skipped and the valid key retained.

## Executed Local Verification

The candidate's owned environment was synchronized with
`UV_PYTHON_DOWNLOADS=never uv sync --locked --python 3.13`. Actual versions:
Python 3.13.12, PyJWT 2.15.0, MCP 1.29.1, Pydantic 2.13.5 and cryptography 50.0.0.

- Provider-free MCP schema, stdio, CLI, ownership, cancellation, cursor, exact-read
  and independent consumer selection: **221 passed** in 22.40 seconds.
- `.venv/bin/ruff check .`: passed.
- `.venv/bin/pyright --pythonpath .venv/bin/python`: zero errors and warnings.
- Offline synthetic JWT/JWK probes described above: passed; no real credentials or network.
- `git diff --check`: passed for the dependency candidate.

The focused pytest run retains five existing PyMuPDF/SWIG deprecation warnings.
Python 3.12, full regression, installed-wheel and hosted proof results are recorded in
the PR after fresh hosted checks complete; they are not inferred from this local selection.

## Documentation And Rollback

This review is the documentation impact. CLI/MCP reference snapshots and user guides
remain accurate because no public behavior or workflow changes. No migration is needed.
Reverting the lock update would restore the vulnerable dependency, so a compatibility
failure should be repaired without silently downgrading. No release or tag is part of this PR.
