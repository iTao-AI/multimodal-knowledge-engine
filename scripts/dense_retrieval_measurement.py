#!/usr/bin/env python3
"""Validate dense comparison evidence model-free or by cache-only replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from mke.adapters.embedding import create_sentence_transformers_embedding
from mke.evaluation.dense_artifact import validate_dense_comparison_artifact
from mke.evaluation.dense_candidate import (
    DensePartition,
    run_dense_candidate_partition,
)
from mke.evaluation.dense_protocol import load_dense_protocol_lock
from mke.evaluation.dense_replay import validate_dense_cache_replay


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dense_retrieval_measurement.py")
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--model-free", action="store_true")
    mode.add_argument("--cache-ready", action="store_true")
    parser.add_argument("--model-cache", type=Path)
    args = parser.parse_args(argv)
    if args.model_free and args.model_cache is not None:
        parser.error("--model-cache is not accepted in model-free mode")
    if args.cache_ready and args.model_cache is None:
        parser.error("--model-cache is required in cache-ready mode")
    try:
        payload = json.loads(args.artifact.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("artifact is invalid")
        artifact = cast(dict[str, Any], payload)
        validate_dense_comparison_artifact(
            artifact,
            protocol_path=args.protocol,
            repository_root=args.repository,
        )
        if args.cache_ready:
            _validate_cache_ready(
                artifact,
                protocol_path=args.protocol,
                repository_root=args.repository,
                model_cache=cast(Path, args.model_cache),
            )
        print(
            json.dumps(
                {
                    "mode": "cache-ready" if args.cache_ready else "model-free",
                    "status": "passed",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 0
    except Exception:
        print(
            json.dumps(
                {
                    "mode": "cache-ready" if args.cache_ready else "model-free",
                    "status": "failed",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1


def _validate_cache_ready(
    artifact: dict[str, Any],
    *,
    protocol_path: Path,
    repository_root: Path,
    model_cache: Path,
) -> None:
    root = repository_root.resolve()
    cache = model_cache.resolve()
    if cache == root or cache.is_relative_to(root):
        raise ValueError("model cache must be outside the repository")
    protocol = load_dense_protocol_lock(protocol_path, repository_root=root)
    provider = create_sentence_transformers_embedding(cache_dir=cache)

    def run_partition(partition: str) -> dict[str, Any]:
        if partition not in {"development", "holdout"}:
            raise ValueError("partition is invalid")
        return cast(
            dict[str, Any],
            run_dense_candidate_partition(
                protocol,
                repository_root=root,
                partition=cast(DensePartition, partition),
                provider=provider,
                threshold=0.0,
            ),
        )

    validate_dense_cache_replay(artifact, partition_runner=run_partition)


if __name__ == "__main__":
    raise SystemExit(main())
