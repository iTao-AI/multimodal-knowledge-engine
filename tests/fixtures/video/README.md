# Video Fixtures

`short-audio.mp4` is generated test media for the PR 4 timestamp Evidence proof.

- License: MIT-compatible generated fixture for this repository.
- Size target: small source-controlled fixture suitable for CI.
- Runtime behavior: tests and `mke demo --verify` read the MP4 path plus
  `short-audio.mp4.mke-transcript.json`; they do not run `ffmpeg`, download models, call external
  services, or create a model cache.
- Fixture profile: MP4 container, H.264 video, AAC audio.

Regeneration command used by maintainers:

```bash
ffmpeg -y \
  -f lavfi -i color=c=black:s=160x90:d=2.2 \
  -f lavfi -i sine=frequency=440:duration=2.2 \
  -c:v libx264 -pix_fmt yuv420p -preset ultrafast -tune stillimage \
  -c:a aac -b:a 32k -shortest -movflags +faststart \
  tests/fixtures/video/short-audio.mp4
```

## `spoken-evidence.mp4`

`spoken-evidence.mp4` is a repository-authored synthetic spoken fixture for the real local
transcription proof.

- Spoken text: `Evidence remains traceable after publication.`
- Source: repository-authored text synthesized with Mimic 1.3.0.1; no personal recording, private
  source audio, downloaded voice, or downloaded model was used.
- Voice: Mimic's built-in `slt` / `cmu_us_slt` voice. The installed voice library was
  `libttsmimic_lang_cmu_us_slt.0.dylib`; the corresponding upstream artifact is
  `voices/cmu_us_slt.flitevox`.
- Voice copyright: Copyright 1999-2014 Language Technologies Institute, Carnegie Mellon
  University.
- Redistribution basis: Mimic 1.3.0.1 identifies `voices/cmu_us_slt.flitevox` under the permissive
  Flite license, which permits use, copy, modification, publication, distribution, sublicensing,
  and sale subject to retaining its copyright notice, conditions, author attribution, and
  disclaimer. The generated audio is redistributed on that basis.
- Primary sources:
  [Mimic 1.3.0.1 `COPYING`](https://github.com/MycroftAI/mimic1/blob/adf655da0399530ac1b586590257847eb61be232/COPYING),
  [`voices/cmu_us_slt.flitevox`](https://github.com/MycroftAI/mimic1/blob/adf655da0399530ac1b586590257847eb61be232/voices/cmu_us_slt.flitevox),
  and the [Flite download and license page](https://www.festvox.org/flite/download.html).
- Installed license evidence: `/opt/homebrew/opt/mimic/COPYING` had SHA-256
  `996e1812de0adcf8a58e0a0977d04dbf03d9f04097562eb8a57b7487fafbb943`, matching
  Mimic tag 1.3.0.1 commit `adf655da0399530ac1b586590257847eb61be232`.
- Fixture profile: MP4 container, H.264 video, AAC audio, black 160x90 frame, 3.330000 seconds.
- Fixture identity: 33,171 bytes; SHA-256
  `6c2a57a73ee01976bccfcfe73f3334d8d1675a891ccc5868d68fa2caadf27e3e`.
- Sidecars: none. In particular, `spoken-evidence.mp4.mke-transcript.json` must not exist.
- Transcript policy: tests may require non-empty timestamp Evidence and stable keywords, but do not
  assert an exact full transcript across speech-recognition runtimes.

Generation commands used by maintainers:

```bash
tmp_dir="$(mktemp -d)"
mimic -t "Evidence remains traceable after publication." \
  -voice slt \
  -o "$tmp_dir/spoken-evidence.wav"
ffmpeg -y \
  -f lavfi -i color=c=black:s=160x90:d=10 \
  -i "$tmp_dir/spoken-evidence.wav" \
  -c:v libx264 -pix_fmt yuv420p -preset ultrafast -tune stillimage \
  -c:a aac -b:a 64k -shortest -movflags +faststart \
  "$tmp_dir/spoken-evidence.mp4"
cp "$tmp_dir/spoken-evidence.mp4" tests/fixtures/video/spoken-evidence.mp4
rm -rf "$tmp_dir"
```

Flite notice retained for the built-in voice source:

> Copyright 1999-2014 Language Technologies Institute, Carnegie Mellon University. All Rights
> Reserved.
>
> Permission is hereby granted, free of charge, to use and distribute this software and its
> documentation without restriction, including without limitation the rights to use, copy, modify,
> merge, publish, distribute, sublicense, and/or sell copies of this work, and to permit persons to
> whom this work is furnished to do so, subject to the following conditions:
>
> 1. The code must retain the above copyright notice, this list of conditions and the following
>    disclaimer.
> 2. Any modifications must be clearly marked as such.
> 3. Original authors' names are not deleted.
> 4. The authors' names are not used to endorse or promote products derived from this software
>    without specific prior written permission.
>
> CARNEGIE MELLON UNIVERSITY AND THE CONTRIBUTORS TO THIS WORK DISCLAIM ALL WARRANTIES WITH REGARD
> TO THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN NO EVENT
> SHALL CARNEGIE MELLON UNIVERSITY NOR THE CONTRIBUTORS BE LIABLE FOR ANY SPECIAL, INDIRECT OR
> CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
> WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
> CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

Repository fixture policy: repository-authored fixture text and packaging may use the repository's
license, but this repository does not relicense the third-party voice or source audio as MIT.
