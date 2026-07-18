# Direct Audio Fixtures

The three files in this directory are repository-authored synthetic spoken fixtures for bounded
direct-audio profile and provenance tests. They are three encodings of the same synthetic source
WAV, not three independently synthesized recordings.

## Source and redistribution authority

- Spoken text: `Direct audio remains traceable after publication.`
- Source: repository-authored English text synthesized once with Mimic 1.3.0.1. No personal recording
  was used. No private source audio, downloaded voice, downloaded model, or cloud service was used.
- Shared source identity: the uncommitted intermediate `source.wav` was 116,204 bytes with SHA-256
  `2e62303fbc08223d326b6faa3699bbbfdf0e0fca335101bdb7265b4988d11cb4`. All three committed files
  were generated from those exact source bytes.
- Voice: Mimic's built-in `slt` / `cmu_us_slt` voice. The installed Homebrew bottle links
  `libttsmimic_lang_cmu_us_slt.0.dylib`; Mimic's corresponding upstream artifact is
  `voices/cmu_us_slt.flitevox`.
- Voice copyright: Copyright 1999-2014 Language Technologies Institute, Carnegie Mellon
  University.
- Redistribution basis: Mimic 1.3.0.1 assigns `voices/cmu_us_slt.flitevox` to the permissive Flite
  license. That license permits use, copying, modification, publication, distribution,
  sublicensing, and sale subject to retaining its copyright notice, conditions, attribution, and
  disclaimer. These fixtures redistribute the generated synthetic speech on that basis. The
  repository-authored sentence and fixture packaging use this repository's license; the repository
  does not relicense Mimic, Flite, or the built-in voice.
- Primary evidence:
  [Mimic 1.3.0.1 `COPYING`](https://github.com/MycroftAI/mimic1/blob/adf655da0399530ac1b586590257847eb61be232/COPYING),
  [`voices/cmu_us_slt.flitevox`](https://github.com/MycroftAI/mimic1/blob/adf655da0399530ac1b586590257847eb61be232/voices/cmu_us_slt.flitevox),
  and the [Flite download and license page](https://www.festvox.org/flite/download.html).
- Local license evidence: the installed `/opt/homebrew/opt/mimic/COPYING` had SHA-256
  `996e1812de0adcf8a58e0a0977d04dbf03d9f04097562eb8a57b7487fafbb943`. Its file inventory lists
  `voices/cmu_us_slt.flitevox`, followed by the CMU copyright above and `License: flite`.
- Installed source identity: Homebrew formula `mimic` 1.3.0.1 uses the upstream tag archive
  `https://github.com/MycroftAI/mimic1/archive/refs/tags/1.3.0.1.tar.gz`, whose formula source
  checksum is `9041f5c7d3720899c90c890ada179c92c3b542b90bb655c247e4a4835df79249`.
  The installed Mimic binary had SHA-256
  `1688519d7e403129c3e984188fca1c0416409b53952088e986d811463827f036`; the built-in `slt` dylib had
  SHA-256 `32baf028277764bd1d9aff05b36b106b7149f6bcefcce698b842b863fd81cc6d`.

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

## Generation tool authority and verbatim recipe

Generation used the installed Homebrew `ffmpeg` 8.1.1 bottle. `ffmpeg -version` identified FFmpeg
8.1.1, `libavcodec` 62.28.101, `libavformat` 62.12.101, `--enable-gpl`, and
`--enable-libmp3lame`. The Homebrew formula identifies this build as `GPL-3.0-or-later` and its
upstream source as `https://ffmpeg.org/releases/ffmpeg-8.1.1.tar.xz`. The installed binary had
SHA-256 `00d01197255300c02122c783dd0126a9e7f47d6c6a19faafae2e6610efd071d3`; the installed formula
records source SHA-256 `b6863adde98898f42602017462871b5f6333e65aec803fdd7a6308639c52edf3`.
FFmpeg and its libraries are generation tools and are not copied into these fixtures.

The following is the full command recipe used. `tmp_dir` is outside the repository, and only the
three final encoded outputs are copied into the repository. The intermediate `source.wav` is not a
repository fixture.

```bash
tmp_dir="$(mktemp -d)"
mimic -t "Direct audio remains traceable after publication." \
  -voice slt \
  -o "$tmp_dir/source.wav"
ffmpeg -nostdin -y -i "$tmp_dir/source.wav" -map 0:a:0 -vn -sn -dn \
  -c:a libmp3lame -ar 16000 -ac 1 -b:a 48k "$tmp_dir/direct-audio.mp3"
ffmpeg -nostdin -y -i "$tmp_dir/source.wav" -map 0:a:0 -vn -sn -dn \
  -c:a pcm_s16le -ar 16000 -ac 1 "$tmp_dir/direct-audio.wav"
ffmpeg -nostdin -y -i "$tmp_dir/source.wav" -map 0:a:0 -vn -sn -dn \
  -c:a aac -profile:a aac_low -ar 16000 -ac 1 -b:a 48k \
  "$tmp_dir/direct-audio.m4a"
mkdir -p tests/fixtures/audio
cp "$tmp_dir/direct-audio.mp3" tests/fixtures/audio/direct-audio.mp3
cp "$tmp_dir/direct-audio.wav" tests/fixtures/audio/direct-audio.wav
cp "$tmp_dir/direct-audio.m4a" tests/fixtures/audio/direct-audio.m4a
rm -rf -- "$tmp_dir"
```

## Frozen fixture identities and profiles

All files contain exactly one decodable mono audio stream at 16,000 Hz, last 3.630000 seconds, and
contain zero video, subtitle, data, or attachment streams. No transcript sidecar or source WAV is
committed.

| Fixture | Media type | Container tokens | Codec/profile | Bytes | SHA-256 |
|---|---|---|---|---:|---|
| `direct-audio.mp3` | `audio/mpeg` | `mp3` | PyAV `mp3float` / normalized MPEG Layer III | 22,509 bytes | `cc10ce7b07ae0ea8434b690383bb7ef0a43f7af66aec474d410e5a9612158631` |
| `direct-audio.wav` | `audio/wav` | `wav` | `pcm_s16le` | 116,238 bytes | `ec82eefefc5a6ccbbfc757864fc94bffd250bf185b03fc0404568063c8f993ac` |
| `direct-audio.m4a` | `audio/mp4` | `mov,mp4,m4a,3gp,3g2,mj2` | `aac` / AAC Low Complexity (`LC`) | 24,880 bytes | `cd7307b22b74de4fef8bda87582be791528c65d6546e4abdf42128070980e260` |

For `direct-audio.m4a`, PyAV 17.1.0 exposed AAC profile `LC`, major brand `M4A `, and compatible
brands `M4A isomiso2`; the fixture tests require those exact values.

These short fixtures establish deterministic format, provenance, redistribution, and product-path
inputs. They are not a transcription-quality benchmark and make no speech-recognition accuracy,
language-quality, platform-performance, or production-readiness claim.
