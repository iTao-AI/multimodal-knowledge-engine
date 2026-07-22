# Run the installed-wheel direct-audio proof

The terminal controller verifies the bounded direct-audio product path from the same fresh MKE
wheel on CPython 3.12 and 3.13. It is offline and has no download option. Run it only after the
retained wheelhouse, constraints, prepared model cache, dependency receipt, fixtures, and two
Darwin arm64 interpreters have been independently authorized.

The value of `DIRECT_AUDIO_FOOTPRINT_BYTES` is an owner-selected proof input. MKE provides no
default, recommendation, production ceiling, or SLA for it. The only accepted direct-audio budget
mode in this release candidate is `baseline_plus`.

Before terminal authorization, add `--authorization-only` to the command below. That mode validates
and freezes the complete input manifest without creating a venv, loading a model, or running ASR.
It returns `mke.direct_audio_terminal_authorization.v1` with `status=ready`; any missing or drifting
input fails closed.

```bash
UV_OFFLINE=1 uv run python scripts/direct_audio_deployment_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --mke-wheel "$MKE_WHEEL" \
  --dependency-receipt benchmarks/audio/dependency-artifacts.json \
  --wheelhouse "$TRANSCRIPTION_WHEELHOUSE" \
  --constraints "$TRANSCRIPTION_CONSTRAINTS" \
  --model-root "$MKE_MODEL_ROOT" \
  --fixture-root tests/fixtures/audio \
  --direct-audio-footprint-bytes "$DIRECT_AUDIO_FOOTPRINT_BYTES" \
  --direct-audio-footprint-budget-mode baseline_plus \
  --receipt "$DIRECT_AUDIO_PROOF_RECEIPT" \
  --json
```

`--model-root` is the Hugging Face cache root. The controller binds the exact
`Systran/faster-whisper-small` snapshot at revision
`536b0662742c02347bc0e980a01041f333bce120`, including its complete file inventory, model card,
license, sizes, per-file SHA-256 values, and aggregate tree digest before any provider is built.

The success receipt uses `mke.direct_audio_deployment_proof.v1`. Its authorization manifest binds
the candidate wheel, accepted dependency receipt, external wheelhouse manifest, constraints,
interpreter identities, installed package sets, model tree, fixtures, standalone Export v2
consumer, call-owned cleanup policy, deny-network method, and the exact owner supervision pair.
The controller then checks Python, CLI, and one official-SDK stdio MCP flow, timestamp Evidence,
Search/Ask, atomic Publication, two equal Export v2 trees, and the independent consumer before and
after a portable copy.

The controller never runs Export v1 and never changes the model cache, retained wheelhouse,
constraints, fixtures, or repository. A failed authority check stops before inference. Raw model
timings and footprint observations are fixed-fixture Darwin arm64 diagnostics only; they do not
establish accuracy, cross-platform behavior, hostile-media containment, a runtime budget default,
or a deployment SLA.
