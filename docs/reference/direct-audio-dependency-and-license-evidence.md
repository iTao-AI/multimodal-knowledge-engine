# Direct-audio dependency and license evidence

This reference records the bounded PR A feasibility proof for local optional dependencies and the
three repository-distributed synthetic audio fixtures. The refreshed receipt binds the PR C
candidate wheel only as a dependency-installation input; it does not prove candidate product
behavior, and it does not authorize redistribution of external wheels or native binaries.

## Canonical receipt

- Schema: `mke.direct_audio_dependency_receipt.v1`
- Receipt: `benchmarks/audio/dependency-artifacts.json`
- Canonical payload SHA-256 (`receipt_sha256`):
  `fd369d35cb97754839f62ed6ee72dbb69f4cedc85eae40f3c0891d314e0dc61e`
- Committed file SHA-256:
  `befc901781c597b8e80f380cf5e29a183c672132c31590efff7d9ff1dad373b7`
- Wheel inventory: 60 locked external files plus one candidate MKE wheel, with 108 cell-specific
  resolutions
- Constraints SHA-256:
  `4379a58870a10077587ba55b4d01669fca580301223d19a2f31307eefd395b08`
- Full hashed cell requirements SHA-256:
  `e653870bfb252d22309bbe6b66bf7790bd89d167e41094dd5a358a20f876aebf`
- Wheelhouse manifest SHA-256:
  `de0361b881ba936bb61c473df99f2a2b1f44fb02baefd56f027414587790c4a4`

The wheel bytes were acquired only from the exact HTTPS artifact URLs and digests recorded in the
locked external-distribution projection. The candidate wheel was the separately bound local PR C
input. The controller then used ordinary pip in exclusive call-owned environments with an empty
inherited environment, `--no-index`, a validated local `--find-links`, binary-only selection,
`--no-cache-dir`, `--require-hashes`, and the accepted constraints. Both cells report
`pip_install=passed`, `pip_check=passed`, and complete cleanup.

The controller was executed through the fixed
`mke.fixed_stdlib_descriptor_bootstrap.v1` bootstrap. The bootstrap descriptor-read, hashed,
compiled, and executed the same controller bytes, then bound controller SHA-256
`932c9e17733e343f15fa558f1e54d21248da8f3f13ce4e52acc344b8f7ca2257` into the receipt.
The read-only `--validate-receipt` lane validates canonical JSON, schema, self-digest, controller
identity, and all static cross-bindings without replaying retained wheels or installed runtimes.
Its result therefore states `retained_runtime_replay=not_performed`; the separate generation run
is the retained-input and runtime replay authority.

## Validated cells and runtime evidence

| Cell | CPython | Executable SHA-256 | Installed distributions | Required imports | Fixture decodes |
|---|---|---|---:|---:|---:|
| 3.12 | 3.12.13, `cp312`, Darwin arm64 | `e2605291e058fdbe3102e8185d0ac5fe0e063398de617010a6af3a42a78f05e3` | 54 | 3 passed | 3 passed |
| 3.13 | 3.13.13, `cp313`, Darwin arm64 | `3237648c5222017bba78737370570e4c9d5a01e552cdf2fa11f107c8d00fc06e` | 54 | 3 passed | 3 passed |

The required imports were PyAV 17.1.0, faster-whisper 1.2.1, and huggingface-hub 1.21.0. No model
was downloaded or loaded, and no speech recognition was run. Each cell decoded the MP3, WAV, and
M4A fixtures through its installed PyAV runtime.

The runtime reported FFmpeg 8.1.1 and `LGPL version 3 or later`. The public configuration field is
a canonical path-free flag projection; SHA-256
`4b43d2f7d03dc3e7c2685553ff20594b1fe6e454e916cee4ed037ca9ac6c0cc5` binds the exact raw runtime
configuration bytes rather than the projected text.
The receipt binds 96 cell-qualified PyAV extension identities and these directly observed runtime
components: `libavcodec` 62.28.101, `libavdevice` 62.3.101, `libavfilter` 11.14.101,
`libavformat` 62.12.101, `libavutil` 60.26.101, `libswresample` 6.3.101, and `libswscale`
9.5.101. PyAV's installed license text has SHA-256
`76af0461ffb92e19f1c14449e95557d83a2dfaa1baf202d49e5f1d8746c0da19`.

The receipt binds `pyav-project-17_1_0` to the
[PyAV v17.1.0 source and license](https://github.com/PyAV-Org/PyAV/tree/v17.1.0). It binds FFmpeg tag
`n8.1.1` (tag object `150ba6ddfabb5c433bb2fb3ee546d2a96e59066d`) to immutable source commit
[`239f2c733de417201d7ad3b3b8b0d9b63285b2b1`](https://github.com/FFmpeg/FFmpeg/tree/239f2c733de417201d7ad3b3b8b0d9b63285b2b1).
At that commit, [`LICENSE.md`](https://github.com/FFmpeg/FFmpeg/blob/239f2c733de417201d7ad3b3b8b0d9b63285b2b1/LICENSE.md)
is 4,346 bytes with SHA-256
`2e1d16c72fd74e12063776371da757322f8b77589386532f4fd8634bde7de1af`, and
[`COPYING.LGPLv3`](https://github.com/FFmpeg/FFmpeg/blob/239f2c733de417201d7ad3b3b8b0d9b63285b2b1/COPYING.LGPLv3)
is 7,651 bytes with SHA-256
`da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768`.
These immutable source and license identities are covered by the canonical payload digest. They
are evidence, not legal advice or a binary redistribution claim.

The installed PyAV wheels also contained 12 observed transitive dylib families whose identities
are recorded in the receipt: `libdav1d`, `libmp3lame`, `libopencore-amrnb`,
`libopencore-amrwb`, `libopus`, `libsharpyuv`, `libsvtav1enc`, `libvpx`, `libwebp`,
`libwebpmux`, `libx264`, and `libx265`. Their filename suffixes are recorded as observations, not
asserted upstream versions; upstream version authority, local-use restrictions, and binary source
provenance remain unestablished or not assessed. Their binary redistribution clearance remains
unresolved. That does not block this local optional-dependency feasibility proof because no
external binary is distributed by MKE in this change.

## Darwin supervisory proof

The controlled allocator proof used public `proc_pid_rusage` `RUSAGE_INFO_V4` process inspection
and sampled the leader's `ri_phys_footprint` every 0.01 seconds. The final canonical run recorded a
24 MiB baseline-plus budget, detected an over-budget sample, sent process-group `SIGTERM`, waited,
and proved the process group absent. The receipt explicitly records `hard_kernel_enforced=false`
and the observed transient overshoot. This is a supervisory physical-footprint budget for ordinary
cooperative descendants, not a production sandbox, hostile-media boundary, or aggregate hard RSS
ceiling.

## Repository-distributed fixture authority

All three fixtures derive from the same repository-authored synthetic source. The exact source,
Flite and FFmpeg identities, commands, profiles, notice, and redistribution basis are recorded in
`tests/fixtures/audio/README.md`.

| Fixture | Bytes | SHA-256 |
|---|---:|---|
| `direct-audio.m4a` | 24,880 | `cd7307b22b74de4fef8bda87582be791528c65d6546e4abdf42128070980e260` |
| `direct-audio.mp3` | 22,509 | `cc10ce7b07ae0ea8434b690383bb7ef0a43f7af66aec474d410e5a9612158631` |
| `direct-audio.wav` | 116,238 | `ec82eefefc5a6ccbbfc757864fc94bffd250bf185b03fc0404568063c8f993ac` |

## Distribution boundary

`external_binary_redistribution=not_performed` and
`redistribution_authority=not_claimed`. The prepared wheelhouse, installed environments, PyAV and
FFmpeg binaries, models, and caches are not committed to Git, included in an MKE sdist or wheel, or
published as release assets. Package metadata alone is not treated as bundled-binary
redistribution authority. Any future wheelhouse, container, native-binary, or additional release
asset distribution requires a separate complete binary redistribution and legal review.

## PR C installed-wheel binding

PR C validates this refreshed receipt before its authorization-only and terminal installed-wheel
controller paths. The refresh closes and installs the candidate wheel's complete active locked
dependency graph for the two declared cells; it does not turn the dependency receipt into candidate
product or real-ASR evidence. The deployment controller independently rebinds the candidate MKE
wheel, external wheelhouse manifest, accepted constraints, exact prepared model tree, two
interpreter identities, fixtures, Export v2 consumer, and the owner-selected `baseline_plus`
supervision pair.

The PR A literals remain `external_binary_redistribution=not_performed` and
`redistribution_authority=not_claimed`. Package metadata is not redistribution authority. Any
future bundling or release redistribution requires separate legal review.
