# Bounded Direct-Audio PR B Implementation Review

## Status

**TARGETED AUTHORITY RE-REVIEW PENDING**

This record covers the bounded internal PR B implementation for Tasks 2 through 4. It does not
start PR C, activate direct audio through a public runtime, or mark any Task 5 through Task 10 step
complete.

## Reviewed Candidate And Findings

The authoritative actual-diff review of candidate
`9227995aa56cc44b5537d1f60633b165c4986a83` requested changes for:

1. failed snapshot creation cleanup that could unlink an inode-distinct staging or sealed path
   replacement;
2. final root removal that could remove a replacement directory after the owned-root identity
   check while leaking the displaced call-owned root; and
3. malformed `container` or `audio_codec` values that could leak an untyped `TypeError` before the
   closed parser rejected the payload.

The review also required the Task 3 ordering statement to reflect the current uncomposed boundary:
PR B proves an internal snapshot and cleanup foundation but has no Source/Run owner path. Task 5 /
PR C owns verification that snapshot creation precedes Source/Run creation.

## Repair Candidate

Commit `1c954b89b745a53bf6fc4bfd2e5aaa0e058b7bb5` binds failed-creation file cleanup to the inode
captured when the staging descriptor is opened, keeps the owned-root descriptor open through file
and root cleanup, and removes only the captured root identity. Darwin uses the existing
`/.vol/<dev>/<ino>` authority; the non-Darwin path resolves the exact root identity beneath a
no-follow parent descriptor. Public paths remain drift detectors rather than deletion authority.

The closed parser now requires exact strings before profile membership. Regressions cover list,
object, null, and boolean values for both media identity fields.

Controlled tests against the prior candidate reported `8 failed, 4 passed`. The same targeted set
passed on the repair, and the combined inspection/parser suite reported `81 passed`. Five cleanup
race repetitions and the Tasks 2 through 4 focused and adjacent video suites also passed.

## Pending Gates

- terminal retrieval identity closure for the repaired source identity;
- all seven canonical validators and normalized semantic-equality proof;
- complete repository test, lint, type, build, proof, demo, scope, byte-identity, secret, and residue
  gates; and
- independent targeted authority re-review of the resulting exact HEAD.

This record is execution evidence only. It does not state or imply an accepted review verdict,
released capability, production media containment, redistribution authority, or public runtime
activation.
