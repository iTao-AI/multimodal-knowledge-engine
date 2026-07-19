# Direct-audio dependency and license evidence

This reference records the bounded PR A feasibility proof for local optional dependencies and the
three repository-distributed synthetic audio fixtures. It does not claim that direct-audio intake
is a product capability, and it does not authorize redistribution of external wheels or native
binaries.

## Canonical receipt

- Schema: `mke.direct_audio_dependency_receipt.v1`
- Receipt: `benchmarks/audio/dependency-artifacts.json`
- Canonical receipt SHA-256:
  `6d8d92a9d6f0be9987cca556c6dc2008ad3703bf220c403e8a4fa9c2dc3c7b0b`
- Locked wheel inventory: 35 unique files and 62 cell-specific resolutions
- Constraints SHA-256:
  `af121bfd1c59381ce9cc960612d2b5e48cfea37572f22fd92a1968dc978959af`
- Full hashed cell requirements SHA-256:
  `33b8f38f3ee89c76e433de76e3e151b3d40876a84db06827ec994f2cc059b4ad`
- Wheelhouse manifest SHA-256:
  `3932575cb68d059f11750ed83649c68f15680e4a5c1d61187645705ee11f4e3f`

The wheel bytes were acquired only from the exact HTTPS artifact URLs and digests recorded in the
locked external-distribution projection. The controller then used ordinary pip in exclusive
call-owned environments with an empty inherited environment, `--no-index`, a validated local
`--find-links`, binary-only selection, `--no-cache-dir`, `--require-hashes`, and the accepted
constraints. Both cells report `pip_install=passed`, `pip_check=passed`, and complete cleanup.

## Validated cells and runtime evidence

| Cell | CPython | Executable SHA-256 | Installed distributions | Required imports | Fixture decodes |
|---|---|---|---:|---:|---:|
| 3.12 | 3.12.13, `cp312`, Darwin arm64 | `e2605291e058fdbe3102e8185d0ac5fe0e063398de617010a6af3a42a78f05e3` | 31 | 3 passed | 3 passed |
| 3.13 | 3.13.13, `cp313`, Darwin arm64 | `3237648c5222017bba78737370570e4c9d5a01e552cdf2fa11f107c8d00fc06e` | 31 | 3 passed | 3 passed |

The required imports were PyAV 17.1.0, faster-whisper 1.2.1, and huggingface-hub 1.21.0. No model
was downloaded or loaded, and no speech recognition was run. Each cell decoded the MP3, WAV, and
M4A fixtures through its installed PyAV runtime.

The runtime reported FFmpeg 8.1.1, `LGPL version 3 or later`, and the exact configuration digest
`4b43d2f7d03dc3e7c2685553ff20594b1fe6e454e916cee4ed037ca9ac6c0cc5`.
The receipt binds 96 cell-qualified PyAV extension identities and these directly observed runtime
components: `libavcodec` 62.28.101, `libavdevice` 62.3.101, `libavfilter` 11.14.101,
`libavformat` 62.12.101, `libavutil` 60.26.101, `libswresample` 6.3.101, and `libswscale`
9.5.101. PyAV's installed license text has SHA-256
`76af0461ffb92e19f1c14449e95557d83a2dfaa1baf202d49e5f1d8746c0da19`.

The receipt binds `pyav-project-17_1_0` to the
[PyAV v17.1.0 source and license](https://github.com/PyAV-Org/PyAV/tree/v17.1.0), and binds
`ffmpeg-project-8_1_1` to the
[FFmpeg n8.1.1 source](https://github.com/FFmpeg/FFmpeg/tree/n8.1.1) and
[FFmpeg legal and license reference](https://ffmpeg.org/legal.html). The component and license
evidence digests plus these closed versioned reference IDs are covered by the canonical receipt
digest. They are evidence, not legal advice.

The installed PyAV wheels also contained 12 observed transitive dylib families whose identities
are recorded in the receipt: `libdav1d`, `libmp3lame`, `libopencore-amrnb`,
`libopencore-amrwb`, `libopus`, `libsharpyuv`, `libsvtav1enc`, `libvpx`, `libwebp`,
`libwebpmux`, `libx264`, and `libx265`. Their binary redistribution clearance remains unresolved.
That does not block this local optional-dependency feasibility proof because no external binary is
distributed by MKE in this change.

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
