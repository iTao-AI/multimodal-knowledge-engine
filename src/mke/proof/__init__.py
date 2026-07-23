"""Deterministic product proof harness."""

from mke.proof.direct_audio import (
    DIRECT_AUDIO_PROOF_FAILURE_NEXT_STEPS,
    DeterministicAudioProvider,
    DirectAudioProofError,
    DirectAudioProofReport,
    direct_audio_report_payload,
    run_direct_audio_proof,
)
from mke.proof.local_knowledge import (
    render_local_knowledge_report,
    run_local_knowledge_proof,
)
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
    "DIRECT_AUDIO_PROOF_FAILURE_NEXT_STEPS",
    "DeterministicAudioProvider",
    "DirectAudioProofError",
    "DirectAudioProofReport",
    "ObservedField",
    "PRODUCT_PROOF_MANIFEST",
    "ProofCaseResult",
    "ProofFixtures",
    "ProofManifest",
    "ProofReport",
    "ProofEnvironment",
    "TranscriptionProofReport",
    "render_human_report",
    "direct_audio_report_payload",
    "render_json_report",
    "render_local_knowledge_report",
    "render_transcription_proof_human",
    "render_transcription_proof_json",
    "run_local_knowledge_proof",
    "run_direct_audio_proof",
    "run_product_proof",
    "run_transcription_proof",
    "validate_transcription_proof",
]
