from __future__ import annotations

import json
import math
from collections.abc import Mapping
from enum import StrEnum
from hashlib import sha256
from typing import Any, Literal

from pydantic import AliasChoices, ConfigDict, Field, field_validator, model_validator
from typing_extensions import TypeAliasType

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.models.common import Model
from mechcad_harness.structural.models import (
    StructuralAnalysisResult,
    StructuralCriterionStatus,
    StructuralExecutionManifest,
    StructuralResultParserProvenance,
    StructuralVerificationResult,
    execution_manifest_hash,
)
from mechcad_harness.structural.evidence_models import (
    CantileverGeometryObservation,
    CantileverMaterialObservation,
    StructuralAnalyticalValidationResult,
)
from mechcad_harness.structural_request import (
    MeshSpecification,
    StructuralAnalysisRequest,
    structural_request_hash,
)


STRUCTURAL_EVIDENCE_SCHEMA_VERSION = "structural-evidence@1"
STRUCTURAL_REPEATABILITY_SCHEMA_VERSION = "structural-repeatability@1"
STRUCTURAL_MESH_CONVERGENCE_SCHEMA_VERSION = "structural-mesh-convergence@1"
FREE_END_TRANSVERSE_DISPLACEMENT = "free_end_cps6_quadratic_surface_integral_transverse_over_area@1"


StructuralSummaryValue = TypeAliasType(
    "StructuralSummaryValue",
    None
    | bool
    | int
    | float
    | str
    | tuple["StructuralSummaryValue", ...]
    | tuple[tuple[str, "StructuralSummaryValue"], ...],
)


class EvidenceSubject(StrEnum):
    STRUCTURAL_ANALYSIS = "analysis.structural"
    STRUCTURAL_CONVERGENCE_STUDY = "analysis.structural.convergence"


class StructuralEvidenceCurrentness(StrEnum):
    CURRENT = "current"
    STALE_RELATIVE_TO_CURRENT_STATE = "stale_relative_to_current_state"
    CURRENTNESS_UNAVAILABLE = "currentness_unavailable"


class StructuralRepeatabilityStatus(StrEnum):
    REPEATABLE = "repeatable"
    NOT_REPEATABLE = "not_repeatable"
    INTEGRITY_FAILURE = "integrity_failure"


class StructuralMeshConvergenceStatus(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    CONVERGED = "converged"
    NOT_CONVERGED = "not_converged"
    NOT_EVALUABLE = "not_evaluable"
    INTEGRITY_FAILURE = "integrity_failure"


def _finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, (tuple, list, set, frozenset)):
        return all(_finite(item) for item in value)
    if isinstance(value, Model):
        return _finite(value.model_dump(mode="python"))
    return True


def _freeze_summary_value(value: Any) -> StructuralSummaryValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("summary object keys must be strings")
        return tuple(
            (key, _freeze_summary_value(child))
            for key, child in sorted(value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_summary_value(child) for child in value)
    raise ValueError("summary values must be JSON-compatible")


class _EvidenceModel(Model):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def validate_finite_values(self):
        if not _finite(self.model_dump(mode="python")):
            raise ValueError("structural evidence numeric values must be finite")
        return self


def _canonical(value: Any, *, identity_field: str | None = None) -> Any:
    if isinstance(value, Model):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        volatile = {
            "created_at",
            "correlation_id",
            "path",
            "pid",
            "process_id",
            "run_directory",
            "run_id",
            "storage_path",
            "temp_directory",
            "timestamp",
            "updated_at",
            "whitespace",
        }
        return {
            key: _canonical(child, identity_field=identity_field)
            for key, child in value.items()
            if key not in volatile and key != identity_field
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(child, identity_field=identity_field) for child in value]
    return value


def _hash(value: Any, *, identity_field: str | None = None) -> str:
    encoded = json.dumps(
        _canonical(value, identity_field=identity_field),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


class StructuralPipelineProvenance(_EvidenceModel):
    """Aggregate provenance for the complete structural evidence pipeline."""

    pipeline_identity: str = Field(min_length=1)
    pipeline_version: str = Field(default="1", min_length=1)
    geometry_provenance: BackendProvenance = Field(
        validation_alias=AliasChoices("geometry_provenance", "geometry_provider_provenance")
    )
    mesh_provenance: BackendProvenance = Field(
        validation_alias=AliasChoices("mesh_provenance", "gmsh_provenance", "meshing_provenance")
    )
    solver_provenance: BackendProvenance = Field(
        validation_alias=AliasChoices("solver_provenance", "calculix_provenance")
    )
    parser_provenance: StructuralResultParserProvenance

    @property
    def geometry_provider_provenance(self) -> BackendProvenance:
        return self.geometry_provenance

    @property
    def gmsh_provenance(self) -> BackendProvenance:
        return self.mesh_provenance

    @property
    def calculix_provenance(self) -> BackendProvenance:
        return self.solver_provenance


class StructuralEvidencePayload(_EvidenceModel):
    schema_version: Literal[STRUCTURAL_EVIDENCE_SCHEMA_VERSION] = STRUCTURAL_EVIDENCE_SCHEMA_VERSION
    request: StructuralAnalysisRequest | None = None
    execution_manifest_artifact_id: str | None = Field(default=None, min_length=1)
    execution_manifest_artifact_hash: str | None = Field(default=None, min_length=1)
    execution_manifest: StructuralExecutionManifest | None = None
    result: StructuralAnalysisResult | None = None
    verification: StructuralVerificationResult | None = None
    analytical_validation: StructuralAnalyticalValidationResult | None = None
    analytical_geometry_observation: CantileverGeometryObservation | None = None
    analytical_material_observation: CantileverMaterialObservation | None = None
    aggregate_provenance: StructuralPipelineProvenance | None = None
    mesh_convergence_status: StructuralMeshConvergenceStatus = StructuralMeshConvergenceStatus.NOT_EVALUATED
    repeatability: StructuralRepeatabilityResult | None = None
    convergence: StructuralMeshConvergenceResult | None = None
    subject: EvidenceSubject = EvidenceSubject.STRUCTURAL_ANALYSIS
    semantic_hash: str = "pending"

    @model_validator(mode="after")
    def validate_bindings_and_hash(self):
        if self.subject is EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY:
            if self.convergence is None:
                raise ValueError("convergence-study evidence requires a convergence payload")
            if any(
                value is not None
                for value in (
                    self.request,
                    self.execution_manifest_artifact_id,
                    self.execution_manifest_artifact_hash,
                    self.execution_manifest,
                    self.result,
                    self.verification,
                    self.analytical_validation,
                    self.analytical_geometry_observation,
                    self.analytical_material_observation,
                    self.aggregate_provenance,
                    self.repeatability,
                )
            ):
                raise ValueError("convergence-study evidence cannot carry physical analysis fields")
            if self.mesh_convergence_status is not self.convergence.status:
                raise ValueError("convergence-study mesh convergence status does not match result")
            expected = structural_evidence_hash(self)
            if self.semantic_hash == "pending":
                object.__setattr__(self, "semantic_hash", expected)
            elif self.semantic_hash != expected:
                raise ValueError("structural evidence semantic hash does not match canonical payload")
            return self

        if self.mesh_convergence_status is not StructuralMeshConvergenceStatus.NOT_EVALUATED:
            raise ValueError("ordinary structural evidence must have NOT_EVALUATED mesh convergence status")
        if self.convergence is not None:
            raise ValueError("ordinary structural evidence cannot carry a convergence payload")
        if any(
            value is None
            for value in (
                self.request,
                self.execution_manifest_artifact_id,
                self.execution_manifest_artifact_hash,
                self.execution_manifest,
                self.result,
                self.verification,
                self.aggregate_provenance,
            )
        ):
            raise ValueError("ordinary structural evidence requires complete physical analysis fields")
        request = self.request
        source = request.source_binding
        manifest = self.execution_manifest
        if request.request_hash != structural_request_hash(request):
            raise ValueError("structural evidence request hash does not match canonical request")
        if (
            manifest.project_id,
            manifest.revision,
            manifest.state_hash,
            manifest.definition_id,
            manifest.definition_hash,
            manifest.request_hash,
        ) != (
            source.project_id,
            source.source_revision,
            source.source_state_hash,
            source.definition_id,
            source.definition_hash,
            request.request_hash,
        ):
            raise ValueError("structural evidence execution manifest binding mismatch")
        if self.result.source_binding != source:
            raise ValueError("structural evidence result source binding mismatch")
        if (
            self.result.request_hash != request.request_hash
            or self.result.execution_manifest_hash != execution_manifest_hash(manifest)
        ):
            raise ValueError("structural evidence result binding mismatch")
        if (
            self.verification.project_id != source.project_id
            or self.verification.source_revision != source.source_revision
            or self.verification.source_state_hash != source.source_state_hash
            or self.verification.definition_id != source.definition_id
            or self.verification.definition_hash != source.definition_hash
            or self.verification.request_hash != request.request_hash
            or self.verification.execution_manifest_hash != execution_manifest_hash(manifest)
            or self.verification.result_hash != self.result.result_hash
            or self.verification.mesh_hash != self.result.mesh_hash
        ):
            raise ValueError("structural evidence verification binding mismatch")
        expected = structural_evidence_hash(self)
        if self.semantic_hash == "pending":
            object.__setattr__(self, "semantic_hash", expected)
        elif self.semantic_hash != expected:
            raise ValueError("structural evidence semantic hash does not match canonical payload")
        return self


class StructuralEvidenceVerification(_EvidenceModel):
    evidence_id: str = Field(min_length=1)
    payload: StructuralEvidencePayload
    valid: bool
    engineering_status: StructuralCriterionStatus | None = None
    request_hash: str = ""
    result_hash: str = ""
    verification_hash: str = ""
    integrity_reason: str = ""

    @model_validator(mode="after")
    def populate_bindings(self):
        if self.payload.subject is EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY:
            return self
        if not self.request_hash:
            object.__setattr__(self, "request_hash", self.payload.request.request_hash)
        if not self.result_hash:
            object.__setattr__(self, "result_hash", self.payload.result.result_hash)
        if not self.verification_hash:
            object.__setattr__(self, "verification_hash", self.payload.verification.verification_hash)
        if self.valid and self.engineering_status is not self.payload.verification.overall_status:
            raise ValueError("structural evidence verification status does not match payload")
        return self


_DEFAULT_SUMMARIES = (
    "free_end_transverse_displacement_mm",
    "maximum_displacement_mm",
    "maximum_von_mises_stress_mpa",
    "total_reaction_force_n",
    "total_reaction_moment_n_mm",
    "criterion_results",
    "analytical_validation",
)


def _validate_named_tolerances(fields: tuple[str, ...], values: tuple[tuple[str, float], ...]) -> None:
    names = [name for name, _ in values]
    if len(set(names)) != len(names):
        raise ValueError("tolerance field IDs must be unique")
    unknown = set(names) - set(fields)
    if unknown:
        raise ValueError("tolerance field IDs must name semantic summaries")
    if any(not name.strip() or not math.isfinite(value) or value < 0 for name, value in values):
        raise ValueError("tolerances must contain finite nonnegative values")


def _is_mesh_correspondence_field(field_id: str) -> bool:
    normalized = field_id.strip().lower().replace("-", "_").replace(" ", "_")
    forbidden = {
        "mesh_node_ids",
        "mesh_element_ids",
        "node_ids",
        "element_ids",
        "node_correspondence_ids",
        "element_correspondence_ids",
        "mesh_correspondence_ids",
    }
    return normalized in forbidden or (
        "id" in normalized
        and (
            "correspondence" in normalized
            or "node_id" in normalized
            or "element_id" in normalized
            or "mesh_node" in normalized
            or "mesh_element" in normalized
        )
    )


class StructuralRepeatabilityPolicy(_EvidenceModel):
    schema_version: Literal[STRUCTURAL_REPEATABILITY_SCHEMA_VERSION] = STRUCTURAL_REPEATABILITY_SCHEMA_VERSION
    policy_id: str = Field(min_length=1)
    source_project_id: str = Field(min_length=1)
    source_definition_id: str = Field(min_length=1)
    source_definition_hash: str = Field(min_length=1)
    source_request_hash: str = Field(min_length=1)
    required_provider_identities: tuple[str, ...] = Field(min_length=1)
    required_runtime_identities: tuple[str, ...] = Field(min_length=1)
    semantic_summary_fields: tuple[str, ...] = Field(default=_DEFAULT_SUMMARIES, min_length=1)
    absolute_tolerances: tuple[tuple[str, float], ...] = ()
    relative_tolerances: tuple[tuple[str, float], ...] = ()
    raw_artifact_bytes_comparison: Literal["ignored"] = "ignored"
    mesh_numbering_comparison: Literal["ignored"] = "ignored"
    policy_hash: str = "pending"

    @model_validator(mode="after")
    def validate_policy(self):
        for field_name, values in (
            ("provider", self.required_provider_identities),
            ("runtime", self.required_runtime_identities),
            ("summary", self.semantic_summary_fields),
        ):
            if any(not value.strip() for value in values) or len(set(values)) != len(values):
                raise ValueError(f"{field_name} identities/fields must be nonempty and unique")
        if any(_is_mesh_correspondence_field(field_id) for field_id in self.semantic_summary_fields):
            raise ValueError("mesh node/element correspondence is not a semantic summary")
        _validate_named_tolerances(self.semantic_summary_fields, self.absolute_tolerances)
        _validate_named_tolerances(self.semantic_summary_fields, self.relative_tolerances)
        expected = structural_repeatability_policy_hash(self)
        if self.policy_hash == "pending":
            object.__setattr__(self, "policy_hash", expected)
        elif self.policy_hash != expected:
            raise ValueError("repeatability policy hash does not match canonical policy")
        return self

    @property
    def summary_fields(self) -> tuple[str, ...]:
        return self.semantic_summary_fields


class StructuralRepeatabilityComparison(_EvidenceModel):
    field_id: str = Field(min_length=1)
    first_value: StructuralSummaryValue
    second_value: StructuralSummaryValue
    absolute_difference: float | None = None
    relative_difference: float | None = None
    absolute_tolerance: float = Field(ge=0)
    relative_tolerance: float = Field(ge=0)
    within_tolerance: bool

    @field_validator("first_value", "second_value", mode="before")
    @classmethod
    def freeze_summary_values(cls, value: Any) -> StructuralSummaryValue:
        return _freeze_summary_value(value)

    @model_validator(mode="after")
    def reject_mesh_correspondence(self):
        if _is_mesh_correspondence_field(self.field_id):
            raise ValueError("mesh node/element correspondence is not a semantic comparison field")
        return self


class StructuralRepeatabilityResult(_EvidenceModel):
    policy: StructuralRepeatabilityPolicy
    first_evidence_id: str = Field(min_length=1)
    second_evidence_id: str = Field(min_length=1)
    status: StructuralRepeatabilityStatus
    comparisons: tuple[StructuralRepeatabilityComparison, ...]
    reason: str = ""
    policy_hash: str = ""
    result_hash: str = "pending"

    @model_validator(mode="after")
    def validate_result(self):
        if self.first_evidence_id == self.second_evidence_id and self.status is not StructuralRepeatabilityStatus.INTEGRITY_FAILURE:
            raise ValueError("repeatability comparison requires two distinct evidence IDs")
        if (
            self.status is not StructuralRepeatabilityStatus.INTEGRITY_FAILURE
            and tuple(comparison.field_id for comparison in self.comparisons)
            != self.policy.semantic_summary_fields
        ):
            raise ValueError("repeatability result comparisons do not match policy summaries")
        if not self.policy_hash:
            object.__setattr__(self, "policy_hash", self.policy.policy_hash)
        elif self.policy_hash != self.policy.policy_hash:
            raise ValueError("repeatability result policy hash does not match policy")
        expected = structural_repeatability_result_hash(self)
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected)
        elif self.result_hash != expected:
            raise ValueError("repeatability result hash does not match canonical result")
        return self

    @property
    def compared_fields(self) -> tuple[str, ...]:
        return tuple(comparison.field_id for comparison in self.comparisons)


def structural_mesh_specification_hash(specification: MeshSpecification) -> str:
    return _hash(specification)


class StructuralMeshConvergenceStudy(_EvidenceModel):
    schema_version: Literal[STRUCTURAL_MESH_CONVERGENCE_SCHEMA_VERSION] = STRUCTURAL_MESH_CONVERGENCE_SCHEMA_VERSION
    policy_id: str = Field(min_length=1)
    mesh_specifications: tuple[MeshSpecification, ...] = Field(min_length=3)
    minimum_mesh_levels: int = Field(default=3, ge=3, le=64)
    load_case_id: str = Field(min_length=1)
    response_metric: Literal[FREE_END_TRANSVERSE_DISPLACEMENT] = FREE_END_TRANSVERSE_DISPLACEMENT
    response_domain: Literal["free-end"] = "free-end"
    response_semantics: Literal["magnitude"] = Field(
        default="magnitude",
        description="All recorded response and analytical-reference values are nonnegative magnitudes.",
    )
    relative_change_threshold: float = Field(gt=0)
    epsilon: float = Field(gt=0)
    max_levels: int = Field(ge=3, le=64)
    required_runtime_identities: tuple[str, ...] = Field(min_length=1)
    study_hash: str = "pending"

    @model_validator(mode="after")
    def validate_study(self):
        if len(self.mesh_specifications) < self.minimum_mesh_levels:
            raise ValueError("mesh convergence study requires at least three mesh levels")
        if len(self.mesh_specifications) > self.max_levels:
            raise ValueError("mesh convergence study exceeds max_levels")
        hashes = tuple(structural_mesh_specification_hash(spec) for spec in self.mesh_specifications)
        if len(set(hashes)) != len(hashes):
            raise ValueError("mesh specifications must be unique")
        if any(not identity.strip() for identity in self.required_runtime_identities) or len(
            set(self.required_runtime_identities)
        ) != len(self.required_runtime_identities):
            raise ValueError("runtime identities must be nonempty and unique")
        expected = structural_mesh_convergence_study_hash(self)
        if self.study_hash == "pending":
            object.__setattr__(self, "study_hash", expected)
        elif self.study_hash != expected:
            raise ValueError("mesh convergence study hash does not match canonical study")
        return self

    @property
    def mesh_specification_hashes(self) -> tuple[str, ...]:
        return tuple(structural_mesh_specification_hash(spec) for spec in self.mesh_specifications)


class StructuralMeshConvergenceLevel(_EvidenceModel):
    level_index: int = Field(gt=0)
    evidence_id: str = Field(min_length=1)
    evidence_hash: str = Field(min_length=1)
    mesh_specification_hash: str = Field(min_length=1)
    node_count: int = Field(gt=0)
    volume_element_count: int = Field(gt=0)
    response_value: float | None = Field(
        default=None,
        description="Nonnegative magnitude of the declared response metric."
    )
    status: StructuralMeshConvergenceStatus = StructuralMeshConvergenceStatus.CONVERGED
    reason: str = ""
    analytical_reference: float | None = Field(
        default=None,
        description="Nonnegative magnitude of the analytical reference response, when available.",
    )
    analytical_error: float | None = Field(
        default=None,
        description="Relative error of the response against the analytical reference, when available.",
    )
    previous_relative_change: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_magnitude_values(self):
        if self.response_value is None:
            if self.status is not StructuralMeshConvergenceStatus.NOT_EVALUABLE:
                raise ValueError("missing response_value requires NOT_EVALUABLE status")
            if not self.reason.strip():
                raise ValueError("NOT_EVALUABLE convergence level requires a reason")
            if self.previous_relative_change is not None:
                raise ValueError("NOT_EVALUABLE convergence level cannot have a relative change")
        elif self.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE:
            raise ValueError("NOT_EVALUABLE convergence level requires response_value=None")
        elif self.response_value < 0:
            raise ValueError("response_value must be a nonnegative magnitude")
        if self.analytical_reference is not None and self.analytical_reference < 0:
            raise ValueError("analytical_reference must be a nonnegative magnitude")
        if self.analytical_error is not None and self.analytical_error < 0:
            raise ValueError("analytical_error must be nonnegative")
        return self


class StructuralMeshConvergenceResult(_EvidenceModel):
    study: StructuralMeshConvergenceStudy
    status: StructuralMeshConvergenceStatus
    levels: tuple[StructuralMeshConvergenceLevel, ...] = ()
    reason: str = ""
    study_hash: str = ""
    result_hash: str = "pending"

    @model_validator(mode="after")
    def validate_result(self):
        if self.status is StructuralMeshConvergenceStatus.NOT_EVALUATED:
            raise ValueError("convergence result status cannot be NOT_EVALUATED")
        if not self.study_hash:
            object.__setattr__(self, "study_hash", self.study.study_hash)
        elif self.study_hash != self.study.study_hash:
            raise ValueError("mesh convergence result study hash does not match study")
        if len(self.levels) > self.study.max_levels:
            raise ValueError("mesh convergence result exceeds study max_levels")
        if self.status in {
            StructuralMeshConvergenceStatus.CONVERGED,
            StructuralMeshConvergenceStatus.NOT_CONVERGED,
        } and len(self.levels) != len(self.study.mesh_specifications):
            raise ValueError("convergence result requires all declared mesh levels")
        if (
            self.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE
            and len(self.levels) != len(self.study.mesh_specifications)
        ):
            raise ValueError("convergence result requires all declared mesh levels")
        if self.status in {
            StructuralMeshConvergenceStatus.CONVERGED,
            StructuralMeshConvergenceStatus.NOT_CONVERGED,
        } and any(level.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE for level in self.levels):
            raise ValueError("successful convergence result cannot contain NOT_EVALUABLE levels")
        indices = tuple(level.level_index for level in self.levels)
        evidence_ids = tuple(level.evidence_id for level in self.levels)
        mesh_hashes = tuple(level.mesh_specification_hash for level in self.levels)
        if indices != tuple(range(1, len(indices) + 1)):
            raise ValueError("convergence levels must be ordered")
        if len(set(evidence_ids)) != len(evidence_ids) or len(set(mesh_hashes)) != len(mesh_hashes):
            raise ValueError("convergence level evidence bindings must be unique")
        if mesh_hashes != self.study.mesh_specification_hashes[: len(mesh_hashes)]:
            raise ValueError("convergence level mesh specification hashes must match study order")
        if self.status in {
            StructuralMeshConvergenceStatus.NOT_EVALUABLE,
            StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
        } and not self.reason:
            raise ValueError("convergence result reason is required for non-success status")
        expected = structural_mesh_convergence_result_hash(self)
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected)
        elif self.result_hash != expected:
            raise ValueError("mesh convergence result hash does not match canonical result")
        return self


def structural_evidence_hash(payload: StructuralEvidencePayload) -> str:
    core = payload.model_dump(mode="json")
    return _hash(core, identity_field="semantic_hash")


def structural_repeatability_policy_hash(policy: StructuralRepeatabilityPolicy) -> str:
    return _hash(policy, identity_field="policy_hash")


def structural_repeatability_result_hash(result: StructuralRepeatabilityResult) -> str:
    return _hash(result, identity_field="result_hash")


def structural_mesh_convergence_study_hash(study: StructuralMeshConvergenceStudy) -> str:
    return _hash(study, identity_field="study_hash")


def structural_mesh_convergence_result_hash(result: StructuralMeshConvergenceResult) -> str:
    return _hash(result, identity_field="result_hash")


StructuralEvidencePayload.model_rebuild()
StructuralEvidenceVerification.model_rebuild()
