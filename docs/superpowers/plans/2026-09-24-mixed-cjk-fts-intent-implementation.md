# Mixed CJK/ASCII Intent Retrieval Implementation

Status: completed locally on `codex/retrieval-mixed-cjk-intent` from
`main@d3d801bb776480516f3062673a43a592ea99b581`.

Design: [Bounded Mixed CJK/ASCII Intent Retrieval](../specs/2026-09-24-mixed-cjk-fts-intent-design.md).

## Checklist

- [x] Freeze public-neutral synthetic failure cases and expected locators. Run the new tests RED
  against the unchanged baseline; record old-strategy observations separately.
- [x] Add `mixed-cjk-fts-intent-v1` revision `1` as an owner-selected strategy. Preserve all
  existing strategy IDs, revisions, default, compiler behavior, and public request schemas.
- [x] Add one shared mixed selector for Search, Ask, provenance, and MCP pages. Gate candidates
  through the complete active FTS `MATCH`, then enforce CJK normalization, overlap, stable order,
  and row, byte, term, pool, and selected-result bounds.
- [x] Preserve original Evidence identity and byte-exact excerpts; bind cursors to strategy and
  active authority, distinguish pagination from capping, and retain exact-read recovery.
- [x] Verify numeric, identifier, active-only, duplicate-projection, provenance, compatibility,
  response-byte, and bounded-performance controls. Check baseline strategy and default outputs.
- [x] Record actual old/candidate observations without changing frozen benchmark artifacts.
  Verify the local built artifact through CLI and stdio MCP with cached tooling.
- [x] Update the targeted ADR, usage and contract reference, and review the complete diff.
  Run applicable repository verification, then create a task-owned local commit.

Completion requires a clean isolated worktree at an exact reviewable commit, actual verification
results, candidate and baseline observations, explicit limitations, and remaining gates. This
stage excludes dependency installation, external providers, user-library mutation, push, PR,
merge, release, and default promotion.
