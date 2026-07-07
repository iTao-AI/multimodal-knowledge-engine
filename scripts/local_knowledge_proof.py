#!/usr/bin/env python3
"""Run the public-safe synthetic local knowledge proof over stdio MCP."""

from __future__ import annotations

import sys
from pathlib import Path

from mke.proof.local_knowledge import (
    render_local_knowledge_report,
    run_local_knowledge_proof,
)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    mke_executable = Path(sys.executable).parent / "mke"
    try:
        report = run_local_knowledge_proof(
            repo_root=repo_root,
            mke_executable=mke_executable,
        )
    except Exception:
        failure_report: dict[str, object] = {
            "proof": "local_knowledge",
            "reason": "local_knowledge_proof_failed",
            "status": "failed",
        }
        print(render_local_knowledge_report(failure_report))
        return 1
    print(render_local_knowledge_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
