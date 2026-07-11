#!/usr/bin/env python3
"""Run the public-safe Evidence provenance proof over real stdio MCP."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mke.proof.evidence_provenance import run_evidence_provenance_proof


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        report = run_evidence_provenance_proof(root, Path(sys.executable).parent / "mke")
    except Exception:
        report = {
            "proof": "evidence_provenance",
            "status": "failed",
            "reason": "evidence_provenance_proof_failed",
        }
        print(json.dumps(report, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
