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
from mke.proof.transcription import (
    ProofEnvironment,
    TranscriptionProofReport,
    render_transcription_proof_human,
    render_transcription_proof_json,
    run_transcription_proof,
    validate_transcription_proof,
)

__all__ = [
    "ObservedField",
    "PRODUCT_PROOF_MANIFEST",
    "ProofCaseResult",
    "ProofFixtures",
    "ProofManifest",
    "ProofReport",
    "ProofEnvironment",
    "TranscriptionProofReport",
    "render_human_report",
    "render_json_report",
    "render_transcription_proof_human",
    "render_transcription_proof_json",
    "run_product_proof",
    "run_transcription_proof",
    "validate_transcription_proof",
]
