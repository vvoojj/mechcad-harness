from pydantic import Field, model_validator

from .common import StateBinding
from mechcad_harness.analysis_provenance import (
    AnalysisExecutionProvenance,
    ContinuousProofExecutionProvenance,
)
from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.structural.evidence import EvidenceSubject, StructuralEvidencePayload


class Evidence(StateBinding):
    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    producer_type: str | None = None
    producer_name: str | None = None
    producer_version: str | None = None
    producer_result_id: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    backend_provenance: BackendProvenance | None = None
    analysis_execution_provenance: AnalysisExecutionProvenance | None = None
    continuous_proof_execution_provenance: ContinuousProofExecutionProvenance | None = None
    continuous_multi_joint_clearance_proof_result_payload: dict[str, object] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    subject: EvidenceSubject | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    structural_evidence_payload: StructuralEvidencePayload | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @model_validator(mode="after")
    def validate_structural_discriminator(self):
        payload = self.structural_evidence_payload
        if self.kind == EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY.value and payload is None:
            raise ValueError("convergence Evidence requires a typed convergence payload")
        if payload is not None:
            if self.subject is None or self.subject is not payload.subject or self.kind != self.subject.value:
                raise ValueError("structural evidence discriminator does not match kind and payload")
        elif self.subject is not None and self.kind != self.subject.value:
            raise ValueError("structural evidence discriminator does not match kind")
        return self
