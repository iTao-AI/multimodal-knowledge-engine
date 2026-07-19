# Bounded Direct Audio Intake Authority Amendment

## Status And Scope

This record supersedes three feasibility-authority surfaces in the approved bounded direct-audio
design, implementation plan, and historical Autoplan review:

1. Darwin arm64 native-child resource supervision;
2. target Python executable identity probing during acquisition preflight; and
3. the boundary between local optional-dependency use and external-binary redistribution.

All other product limits, formats, lifecycle semantics, PR staging, Export v1/v2 compatibility,
proof sequencing, authorization gates, release boundaries, and non-goals remain unchanged. This
record does not authorize implementation, acquisition, push, pull request, merge, release,
deployment, or publication.

## A. Darwin arm64 Supervisory Authority

The supported feasibility cell uses a package-owned supervisory leader and a dedicated process
group. It is a polling supervisor, not a hard kernel-enforced memory limit.

The closed authority is:

- resolve and bind the stable process identity for the supervisory leader;
- poll Darwin `ri_phys_footprint` only for that leader and compare the non-aggregate observation
  with the configured budget. Ordinary-descendant footprints are neither sampled for the budget
  nor added to it;
- bind the dedicated process-group identity used for ordinary cooperative descendant signaling,
  wait/reap, and cleanup;
- permit and record the possibility of transient overshoot between polls;
- on budget exceedance, timeout, cancellation, output overflow, registration failure, or shutdown,
  send `SIGTERM` to the dedicated process group, wait one fixed grace interval, send `SIGKILL` to
  survivors in that group, and wait/reap the group; and
- fail closed on child/leader identity drift, unavailable or failed leader sampling, process-group
  signaling failure, incomplete wait/reap, or cleanup failure.

The receipt and runtime evidence must contain `hard_kernel_enforced=false` and record the footprint
budget as leader-process scope. Ordinary cooperative descendants are covered only by process-group
termination, wait/reap, and cleanup. This is not a sandbox and does not claim hostile-media safety,
containment of escaped or reparented processes, `setsid`/`setpgid` escape, privileged helpers,
kernel compromise, or decoder compromise.

PR A proves the mechanism with a controlled allocator running in the supervisory leader and freezes
leader identity, leader-only non-aggregate budget sampling, polling overshoot, ordinary-descendant
process-group termination/grace/kill/wait ordering, and fail-closed identity, sampling, signaling,
wait, and cleanup negatives. PR B integrates the accepted mechanism into the internal PyAV
inspection and faster-whisper transcription children. PR C consumes that integrated boundary; it
does not redefine it.

## B. Fixed Target-Executable Identity Probe

The no-write acquisition preflight uses an already approved stdlib-only controller interpreter.
For each declared target Python executable, the controller must:

1. resolve it to a regular executable target and bind descriptor device, inode, mode, byte count,
   `mtime_ns`, `ctime_ns`, and SHA-256 before use;
2. execute one fixed, bounded stdlib-only identity probe under a sanitized environment and
   isolated/no-bytecode flags;
3. accept only the closed implementation, exact version, platform, and executable-digest result;
4. reopen and revalidate descriptor identity plus SHA-256 after the probe; and
5. fail closed on substitution, drift, nonzero exit, timeout, oversized output, malformed output,
   unexpected fields, or identity mismatch.

The probe accepts no caller code or import path. Neither the probe nor the input-preflight path may
invoke pip, `uv`, install or synchronize an environment, access or mutate a package cache, create
bytecode, or use a network-capable resolver. It does not publish local executable paths.

This fixed probe is the only target-executable execution permitted by the no-write preflight. The
later, separately authorized receipt-generation path retains its isolated ordinary-pip boundary.

## C. Local Use Versus External-Binary Redistribution

PR A proves local optional-dependency feasibility. External optional-dependency binaries are
classified `local_runtime_only`; the receipt retains exact wheel identities, installed runtime
identity, linked/bundled component inventory, and available direct license/notice evidence. Package
metadata alone is not promoted to transitive redistribution authority.

PR A, the MKE sdist/wheel, Git history, and MKE Release assets do not redistribute the external
PyAV/FFmpeg dependency binaries. The public-safe receipt therefore requires the exact closed
literals:

```text
external_binary_redistribution=not_performed
redistribution_authority=not_claimed
```

While both literals remain true, unresolved transitive external-binary redistribution clearance is
recorded as a non-claim and is not a feasibility hard stop. It must not be inferred, silently
upgraded, or represented as clearance.

Fixture redistribution is different: the committed synthetic audio bytes are classified
`repository_distributed` and redistributed by the repository, so fixture source/voice permission,
retained notice, exact identity, and profile remain a hard PR A gate. Missing local wheel
resolution/import/decode, runtime/component inventory, target-executable identity, or supported-cell
supervisor evidence also remains a hard feasibility failure.

Any future proposal to bundle, vendor, attach, or otherwise redistribute external dependency
binaries requires a separate legal review before release. This amendment grants no such authority.

## Stage And Review Effect

| Stage | Amended authority |
|---|---|
| PR A | Prove `repository_distributed` fixtures, `local_runtime_only` dependency cells, direct component inventory/evidence, closed non-redistribution literals, fixed executable probe, and Darwin arm64 leader-allocator/process-group-cleanup supervision. |
| PR B | Integrate the accepted polling supervisor into internal inspection/transcription children and freeze fail-closed identity/sampling/termination/wait/cleanup behavior. |
| PR C | Bind the accepted PR A receipt and integrated PR B runtime without claiming sandboxing, hostile-media safety, hard kernel enforcement, or external-binary redistribution authority. |
| Release closeout | If external binaries would be bundled or redistributed, stop for a separate legal review; ordinary local dependency installation does not make that claim. |

The historical Autoplan review remains authoritative outside these three surfaces. Its conflicting
resource-ceiling, generic interpreter-preflight, and transitive-redistribution hard-stop wording is
superseded only as described here.

## Amendment Verdict

The staged plan remains `CLEARED FOR STAGED IMPLEMENTATION; PR A REQUIRES SEPARATE DISPATCH` under
this amended authority. No unrelated plan checkbox is completed, and no implementation or external
side effect is authorized by this record.

## Targeted PR A Authority Repair Checkpoint

An executable-path review of candidate `c9a3e39bbda3bfa8a7a1f39098d282b952e004d8`
requested bounded repair before acquisition. Commit
`f49fbb231bb24b7ec180a54ef9f3dc9246402b68` now provides the local model-free repair evidence:

- the generation validator binds canonical receipt bytes, the live controller-script digest,
  production-parsed wheel filenames and tags, exact supported-cell interpreter semantics, per-cell
  installed/import/decode evidence, frozen nested-pip authority, and the controlled-allocator
  supervisor cleanup record;
- the nested-pip boundary uses the approved interpreter only for identity and call-owned venv
  creation, copies all inputs into exclusive call-owned staging, validates source and stage
  identities before and after execution, and treats venv drift or cleanup failure as terminal;
- the lock projection retains URL basename, digest, size, and compatibility-tag authority, while
  fixture preflight binds the exact `README.md` plus three-binary inventory and rejects root or file
  identity drift; and
- marker evaluation, spawn failures, malformed lock structures, CLI argument failures, and
  unexpected controller failures terminate at closed public-safe error codes.

The repair preserved real RED evidence for forged generation authority, nested-pip ownership and
TOCTOU drift, lock/fixture provenance, and public error leakage. A bounded near-field review then
identified one remaining venv-target alias boundary. Follow-up commit
`55d3c3a3365ea36bf0be39ed5e6c9d50d70346ac` binds the venv root, executable, configuration,
`bin`, `lib`, interpreter-library, and `site-packages` identities before install and after both
install and `pip check`; its regressions reject pre-install aliasing and post-install retargeting
without changing the operator-owned target. The resulting focused controller suite passed `182`
tests, and the required-extra fixture suite passed `8` tests. This checkpoint is not Task 1
acceptance: Step 5 remains partial, no real package environment or canonical dependency receipt
exists, Steps 6-7 remain open, and acquisition still requires separate authorization and a targeted
authority re-review.

## Final Bounded Authority Repair Checkpoint

A targeted review of the candidate through
`7063266247565ad3f6460cfe7bab4dcf6b9145d6` found five remaining model-free authority gaps.
Commit `7425334e2320df3a112f03bf765decca3bab3e35` closes that bounded range:

- all preflight and generation inventories must use their one frozen ordering before their
  canonical digest can validate, and the exact
  `schema_version=mke.direct_audio_dependency_receipt.v1` literal is digest-bound;
- `--check-inputs` retains and revalidates the complete lock, constraints, wheelhouse, and
  `README.md` plus three-fixture authority after all initial reads;
- Darwin call-root cleanup holds a no-follow descriptor, removes the bound call-owned inode, keeps
  a raced same-name replacement, and reports incomplete ownership cleanup as terminal;
- a `--copies` venv executable that shares the approved interpreter's device and inode is rejected
  before any pip command; and
- the new regressions preserved the independent RED cases before the receipt-controller suite
  passed `207` tests and the combined controller/fixture run passed `215` tests.

A final targeted cleanup review found that the public path could be replaced between its identity
precheck and descriptor open, preserving the replacement but leaking the displaced call-owned
tree. Commit `2802d6687d6e583bc9f5b023a6770da1f43ca5b5` closes only that Darwin boundary: it opens the
captured `(device, inode)` through `/.vol`, performs descriptor-bound cleanup of the original
`venv` and staging tree, preserves any same-name replacement, and returns terminal
`pip_cleanup_failed` after observed public-path drift. The independent pre-open race regression and
the existing final-`rmdir` race regression both pass. The receipt-controller suite now passes `208`
tests, and the combined controller/fixture run passes `216` tests.

This remains a pre-acquisition checkpoint rather than Task 1 acceptance. No package acquisition,
real package environment, canonical receipt, dependency artifact, or durable license evidence
reference was produced. Step 5 remains partial and unchecked; Steps 6-7 remain open.

## Authorized acquisition execution (2026-07-19)

Independent acquisition authority subsequently approved the exact lock-derived Darwin arm64
binary wheels for the existing CPython 3.12 and 3.13 targets. The controller acquired 35 unique
wheel files from their locked HTTPS artifact sources, validated 81,319,275 retained wheel bytes,
and stayed within the approved 2.5 GiB combined retained and call-owned estimate. It used no source
build, sdist, interpreter, model, voice, hosted API, index fallback, or cache fallback.

The final model-free receipt-controller and fixture suite passed 221 tests before canonical
generation. Both isolated ordinary-pip cells then passed install, `pip check`, the three required
imports, and all three fixture decodes; every call-owned environment and staging tree was removed.
The Darwin controlled allocator probe exceeded its supervisory footprint budget, terminated the
process group, waited, and proved cleanup. The canonical receipt digest is
`6d8d92a9d6f0be9987cca556c6dc2008ad3703bf220c403e8a4fa9c2dc3c7b0b`.

The durable reference records PyAV 17.1.0, runtime-reported FFmpeg 8.1.1 and its license and
configuration evidence, exact directly observed FFmpeg library versions, PyAV extension and
bundled-library identities, and 12 unresolved transitive dylib families. The distribution boundary
remains `external_binary_redistribution=not_performed` and
`redistribution_authority=not_claimed`; no full transitive binary redistribution clearance is
claimed. This execution completes the planned local Task 1 implementation gates but remains
subject to actual-diff authority review; it does not approve PR B or PR C.

Local execution commit `6547b05704c798cc1ea6b929f27bd4c0b8513cf1` binds the final controller,
regressions, canonical receipt, durable reference, and this acquisition record. A bounded
findings-only review identified one source-reference substitution gap; the repair added an exact
RED regression and closed versioned reference IDs for PyAV 17.1.0 and FFmpeg 8.1.1. Targeted
re-review then returned no findings. Final verification passed 294 focused and adjacent tests,
2,576 full-suite tests with 4 skips, Ruff, Pyright, offline build, product proof, demo verification,
canonical readback, no-write preflight identity, public-neutral scans, and no-residue cleanup.
