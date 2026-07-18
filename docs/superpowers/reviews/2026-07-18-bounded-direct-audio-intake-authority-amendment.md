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
