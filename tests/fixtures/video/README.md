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
