"""Deterministic product proof harness."""

from mke.proof.manifest import PRODUCT_PROOF_MANIFEST, ProofFixtures, ProofManifest
from mke.proof.report import (
    ObservedField,
    ProofCaseResult,
    ProofReport,
    render_human_report,
    render_json_report,
)
from mke.proof.runner import run_product_proof

__all__ = [
    "ObservedField",
    "PRODUCT_PROOF_MANIFEST",
    "ProofCaseResult",
    "ProofFixtures",
    "ProofManifest",
    "ProofReport",
    "render_human_report",
    "render_json_report",
    "run_product_proof",
]
