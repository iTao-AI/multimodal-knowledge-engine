# v0.1.0 Release Readiness Plan Review

Status: planning review complete; implementation not started.

Reviewed files:

- [v0.1.0 Release Readiness Design](../specs/2026-07-02-v0-1-0-release-readiness-design.md)
- [v0.1.0 Release Readiness Implementation Plan](../plans/2026-07-02-v0-1-0-release-readiness-implementation.md)

Review base: `main@24691fb0805e4a46bcad41f1699cbef52e65589a`.

Review method: targeted CEO, engineering, DX, and documentation release review. Full
`gstack-autoplan` was not run because the complete pipeline uses independent dual-voice/subagent
steps, while this planning window is operating without delegated agents. The same review concerns
were applied manually and recorded here.

## Verdict

Proceed with Stage 1 release presentation readiness.

Do not add more retrieval features before `v0.1.0`. The release needs clearer packaging, public
entry points, release notes, audit checks, and consumer-smoke evidence. Adding dense/hybrid/reranker
runtime work now would delay release and blur the main product claim.

## CEO / Scope Review

| Finding | Severity | Resolution |
|---|---|---|
| Release could overclaim MKE as a complete RAG platform. | P1 | Design defines the release as a local-first Agent-callable Evidence engine, not a complete RAG platform. |
| E3-C/D/E comparison artifacts are easy to misread as runtime capabilities. | P1 | E3 decision table is mandatory in release-facing docs. Only E3-F is shipped runtime. |
| Continuing to add retrieval candidates before release creates a moving target. | P1 | Release scope excludes new retrieval algorithms and reserves them for `0.1.x` or `0.2.0`. |
| Publishing without consumer smoke would repeat source-checkout-only confidence. | P1 | Stage 2 requires installed-package smoke before tag/release. |

The release wedge is coherent: CLI/MCP Evidence engine with deterministic proof and bounded Chinese
retrieval runtime.

## Engineering Review

| Risk | Severity | Resolution |
|---|---|---|
| Version identity can drift between wheel metadata and runtime import. | P1 | Plan adds a version consistency test for `pyproject.toml` and `mke.__version__`. |
| README and release notes can drift after future docs edits. | P1 | Plan adds `scripts/release_presentation_audit.py` with regression tests. |
| Optional embedding/transcription extras can make core release flaky. | P1 | Optional extras are separated from the core release gate. No model download is required for core release. |
| Consumer smoke could accidentally import from the source tree. | P1 | Stage 2 smoke must verify `mke.__file__` is inside installed site-packages and outside the repository. |
| `gstack-document-release` could propose narrative or scope changes. | P2 | Plan allows factual fixes automatically but requires stopping for narrative, architecture, or version changes. |

The implementation plan has adequate stop conditions. It should produce small commits that are easy
to review.

## DX Review

| Reader | Current issue | Required release outcome |
|---|---|---|
| First-time evaluator | README contains too much stage history before the first working path. | README starts with purpose, install/verify path, current runtime, and non-goals. |
| Agent/tooling integrator | CLI/MCP positioning is spread across docs. | README and release notes point to CLI/MCP contracts and proof commands. |
| Reviewer | E3 artifacts are numerous and hard to interpret. | Release notes include one decision table and links to detailed how-tos. |
| Future maintainer | Release confidence could depend on local source checkout. | Consumer smoke proves installed package identity from outside the repo. |

`docs/how-to/verify-release.md` is justified if Stage 1 documentation audit finds no existing page
that covers post-release verification.

## Documentation Review

`gstack-document-release` is appropriate for the Stage 1 PR because this is a release-facing doc
and version change. `gstack-document-generate` should not be run broadly. It is only appropriate for
clear missing standalone docs such as `docs/how-to/verify-release.md`.

Required release-facing docs:

- `README.md`
- `README_CN.md`
- `CHANGELOG.md`
- `docs/releases/v0.1.0.md`
- `docs/README.md`
- `docs/how-to/verify-release.md` if no equivalent guide exists

Superpowers implementation docs remain history. They should not be the first place a release reader
must go to understand the product.

## Approved Sequence

1. Stage 1 release presentation readiness PR.
2. Planning-window pre-PR review.
3. Push/create PR only after user authorization.
4. Merge after CI and review are clean.
5. Stage 2 consumer smoke PR from latest `main`.
6. Tag and GitHub Release only after both stages are merged and explicitly authorized.

## Explicit Non-Approval

This review does not approve:

- direct tag or release;
- dense runtime promotion;
- RRF runtime promotion;
- reranker runtime;
- HTTP/UI;
- OCR migration;
- API adapters;
- changing Search, Ask, MCP, owner startup, Publication, ingestion, or runtime default.

## Implementation Handoff

Recommended execution prompt:

```text
继续 MKE v0.1.0 release readiness Stage 1。思考深度：high。

先读取并遵守：

1. AGENTS.md
2. docs/superpowers/specs/2026-07-02-v0-1-0-release-readiness-design.md
3. docs/superpowers/plans/2026-07-02-v0-1-0-release-readiness-implementation.md
4. docs/superpowers/reviews/2026-07-02-v0-1-0-release-readiness-review.md

从最新 origin/main 创建 isolated branch/worktree，执行 Stage 1 release presentation readiness：
version identity、release notes、README/README_CN release posture、docs navigation、release
presentation audit、gstack-document-release audit，以及完整验证。

不要实现 Stage 2 consumer smoke，不要 tag/release，不要 push/PR，不要添加新检索功能，不要改变
Search/Ask/MCP/runtime default。完成后保留 clean 本地分支并回报 branch、HEAD、diff、验证结果和风险。
```

## Review Conclusion

The plan is bounded and release-oriented. It follows the successful release discipline used in prior
project release work: presentation cleanup first, then consumer smoke, then tag/release. It is ready
for Stage 1 execution after user authorization.
