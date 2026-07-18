## Summary

Describe the final result and core changes.

## Completion

- Summarize completed acceptance facts with ordinary bullets.
- Add checkbox items only for real pending gates that affect merge readiness.
- During final reconciliation, change every satisfied `[ ]` gate to `[x]`. After merge and before
  closeout, synchronize actual checks, authorization, merge identity, mergeability, review
  blockers, necessary links, cleanup, remaining risk, and explicit non-claims. Attempt the
  write-back, then read back the persisted PR body. If the write-back or persisted-body readback
  fails, or the body still drifts from actual state, record the exact blocker or pending trigger
  and you must not claim complete closeout.

## Verification

- `command` — actual result

## Documentation Impact

Describe updated docs or state `No documentation impact`.

## Risk / Migration

Remove this section when not applicable.
