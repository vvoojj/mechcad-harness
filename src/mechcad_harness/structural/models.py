from __future__ import annotations

import json
import math
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from pydantic import Field, model_validator

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.models.common import Model
from mechcad_harness.models.structural import StructuralResultField
from mechcad_harness.structural_request import StructuralSourceBinding


# ---------------------------------------------------------------------------
# Provider identity / version constants (composition-owned, never caller-supplied)
# ---------------------------------------------------------------------------
REGION_RESOLVER_IDENTITY = "mechcad-structural-region-resolver@1"
GMSH_PROVIDER_IDENTITY = "mechcad-structural-gmsh@1"
DECK_BUILDER_IDENTITY = "mechcad-structural-deck-builder@1"
CALCULIX_PROVIDER_IDENTITY = "mechcad-structural-calculix@1"
UNIT_POLICY_ID = "structural-units@1"
FRD_RESULT_PARSER_IDENTITY = "mechcad-calculix-frd-result-parser@1"
DAT_RESULT_PARSER_IDENTITY = "mechcad-calculix-dat-result-parser@1"
INTERPRETER_IDENTITY = "mechcad-structural-result-interpreter@1"


class StructuralExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    GEOMETRY_REJECTED = "geometry_rejected"
    REGION_RESOLUTION_FAILED = "region_resolution_failed"
    MESH_FAILED = "mesh_failed"
    DECK_INVALID = "deck_invalid"
    SOLVER_UNDERCONSTRAINED = "solver_underconstrained"
    SOLVER_UNAVAILABLE = "solver_unavailable"
    SOLVER_FAILED = "solver_failed"


class StructuralResultMaturity(StrEnum):
    FEA_EXECUTED = "FEA_EXECUTED"


# Naming used by some structural callers before the result terminology settled.
StructuralExecutionMaturity = StructuralResultMaturity


class SemanticGeometryKind(StrEnum):
    PLANAR_FACE = "planar_face"


class StructuralCriterionStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUABLE = "not_evaluable"


class StressFieldRepresentation(StrEnum):
    CALCULIX_EXTRAPOLATED_NODAL_STRESS = "calculix_extrapolated_nodal_stress"


class _ImmutableFiniteModel(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    @model_validator(mode="after")
    def validate_finite_scalars(self):
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            values = value if isinstance(value, tuple) else (value,)
            if any(isinstance(item, float) and not math.isfinite(item) for item in values):
                raise ValueError(f"{field_name} must contain only finite scalars")
        return self


class StructuralResultUnits(_ImmutableFiniteModel):
    displacement: Literal["mm"] = "mm"
    stress: Literal["MPa"] = "MPa"
    force: Literal["N"] = "N"
    moment: Literal["N*mm"] = "N*mm"


class StructuralResultParserProvenance(_ImmutableFiniteModel):
    frd_parser_identity: Literal[FRD_RESULT_PARSER_IDENTITY] = FRD_RESULT_PARSER_IDENTITY
    dat_parser_identity: Literal[DAT_RESULT_PARSER_IDENTITY] = DAT_RESULT_PARSER_IDENTITY
    interpreter_identity: Literal[INTERPRETER_IDENTITY] = INTERPRETER_IDENTITY


class StructuralStressTensor(_ImmutableFiniteModel):
    sxx: float
    syy: float
    szz: float
    sxy: float
    syz: float
    szx: float


CauchyStressTensor = StructuralStressTensor


class StructuralStressSampleIdentity(_ImmutableFiniteModel):
    mesh_hash: str = Field(min_length=1)
    node_id: int = Field(gt=0)
    element_id: int | None = Field(default=None, gt=0)
    location_id: str | None = None

    @model_validator(mode="after")
    def validate_location_identity(self):
        if self.location_id is not None and not self.location_id:
            raise ValueError("stress sample location identity must be nonempty")
        return self


class StructuralDisplacementSample(_ImmutableFiniteModel):
    field: Literal[StructuralResultField.DISPLACEMENT] = StructuralResultField.DISPLACEMENT
    mesh_hash: str = Field(min_length=1)
    node_id: int = Field(gt=0)
    vector_mm: tuple[float, float, float]
    units: StructuralResultUnits


class StructuralReactionSample(_ImmutableFiniteModel):
    field: Literal[StructuralResultField.REACTIONS] = StructuralResultField.REACTIONS
    mesh_hash: str = Field(min_length=1)
    node_id: int = Field(gt=0)
    support_set_name: str = Field(min_length=1, pattern=r"[A-Z][A-Z0-9_]*")
    vector_n: tuple[float, float, float]
    units: StructuralResultUnits


class StructuralStressSample(_ImmutableFiniteModel):
    field: Literal[StructuralResultField.VON_MISES_STRESS] = StructuralResultField.VON_MISES_STRESS
    identity: StructuralStressSampleIdentity
    mesh_hash: str = Field(min_length=1)
    representation: StressFieldRepresentation
    tensor_mpa: StructuralStressTensor
    units: StructuralResultUnits

    @model_validator(mode="after")
    def validate_mesh_binding(self):
        if self.identity.mesh_hash != self.mesh_hash:
            raise ValueError("stress sample mesh hash does not match identity mesh hash")
        return self


# ---------------------------------------------------------------------------
# Resolved semantic region realization (no raw FaceN/EdgeN authority)
# ---------------------------------------------------------------------------
class ResolvedStructuralRegion(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    region_id: str = Field(min_length=1)
    source_geometry_hash: str = Field(min_length=1)
    resolver_identity: str = Field(min_length=1)
    resolver_version: str = Field(min_length=1)
    geometry_kind: SemanticGeometryKind
    exact_brep_area_mm2: float
    exact_brep_centroid_mm: tuple[float, float, float]
    plane_normal: tuple[float, float, float]
    bounding_box_mm: tuple[float, float, float, float, float, float]  # xmin,ymin,zmin,xmax,ymax,zmax
    expected_cardinality: int = Field(gt=0)
    actual_cardinality: int = Field(gt=0)
    semantic_descriptor: str = Field(min_length=1)
    region_realization_hash: str = Field(min_length=1)


class ResolvedRegionMap(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    source_geometry_hash: str = Field(min_length=1)
    resolver_identity: str = Field(min_length=1)
    resolver_version: str = Field(min_length=1)
    match_policy_id: str = Field(min_length=1)
    regions: tuple[ResolvedStructuralRegion, ...]
    region_map_hash: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Mesh execution / manifest
# ---------------------------------------------------------------------------
class PhysicalGroupBinding(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    semantic_region_id: str | None = None  # None for the volume group
    physical_group_name: str = Field(min_length=1)
    gmsh_entity_dim: int
    gmsh_entity_id: int  # runtime topology; audit only


class StructuralMeshManifest(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    mesh_specification_hash: str = Field(min_length=1)
    gmsh_identity: str = Field(min_length=1)
    gmsh_version: str = Field(min_length=1)
    element_family: str = Field(min_length=1)
    node_count: int = Field(gt=0)
    volume_element_count: int = Field(gt=0)
    boundary_element_count: int = Field(gt=0)
    volume_entity_id: int
    physical_groups: tuple[PhysicalGroupBinding, ...]
    mesh_hash: str = Field(min_length=1)
    region_map_hash: str = ""


class StructuralSolverManifest(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    calculix_identity: str = Field(min_length=1)
    calculix_version: str = Field(min_length=1)
    backend_provenance: BackendProvenance | None = None
    exit_code: int | None = None
    job_finished: bool = False
    produced_frd: bool = False
    produced_dat: bool = False
    produced_log: bool = False
    solver_message: str = ""


# ---------------------------------------------------------------------------
# Load lowering provenance (ResultantForce consistent nodal lowering)
# ---------------------------------------------------------------------------
class LoweredLoadProvenance(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    canonical_load_id: str = Field(min_length=1)
    canonical_load_semantic_hash: str = Field(min_length=1)
    semantic_region_id: str = Field(min_length=1)
    resolved_region_map_hash: str = Field(min_length=1)
    exact_semantic_face_area_mm2: float
    source_force_vector_n: tuple[float, float, float]
    source_application_point_mm: tuple[float, float, float]
    normalized_solver_traction_vector_n_per_mm2: tuple[float, float, float]
    lowering_algorithm_id: str = Field(min_length=1)
    c3d10_surface_integration_rule_version: str = Field(min_length=1)
    produced_nodal_load_semantic_hash: str = Field(min_length=1)
    mesh_hash: str = Field(min_length=1)
    force_conservation_error_n: float
    moment_conservation_error_n_mm: float


# ---------------------------------------------------------------------------
# Execution manifest binding the complete pipeline
# ---------------------------------------------------------------------------
class StructuralArtifactRef(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    artifact_type: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    sha256: str = Field(min_length=1)
    producer_identity: str = Field(min_length=1)
    producer_version: str = Field(min_length=1)


class StructuralCaseExecutionManifest(_ImmutableFiniteModel):
    load_case_id: str = Field(min_length=1)
    mesh_artifact_id: str = Field(min_length=1)
    mesh_artifact_hash: str = Field(min_length=1)
    deck_artifact_id: str | None = Field(default=None, min_length=1)
    deck_artifact_hash: str | None = Field(default=None, min_length=1)
    deck_semantic_hash: str | None = Field(default=None, min_length=1)
    deck_builder_identity: str | None = Field(default=None, min_length=1)
    deck_builder_version: str | None = Field(default=None, min_length=1)
    frd_artifact_id: str | None = Field(default=None, min_length=1)
    frd_artifact_hash: str | None = Field(default=None, min_length=1)
    dat_artifact_id: str | None = Field(default=None, min_length=1)
    dat_artifact_hash: str | None = Field(default=None, min_length=1)
    log_artifact_id: str | None = Field(default=None, min_length=1)
    log_artifact_hash: str | None = Field(default=None, min_length=1)
    execution_status: StructuralExecutionStatus
    failure_stage: str = ""
    error_detail: str = ""
    solver_manifest: StructuralSolverManifest | None = None
    lowered_loads: tuple[LoweredLoadProvenance, ...] = ()
    run_id: str | None = None
    case_manifest_hash: str = "pending"

    @model_validator(mode="after")
    def validate_artifact_pairs_and_hash(self):
        for artifact_id, artifact_hash in (
            (self.deck_artifact_id, self.deck_artifact_hash),
            (self.frd_artifact_id, self.frd_artifact_hash),
            (self.dat_artifact_id, self.dat_artifact_hash),
            (self.log_artifact_id, self.log_artifact_hash),
        ):
            if (artifact_id is None) != (artifact_hash is None):
                raise ValueError("artifact IDs and hashes must be supplied together")
        expected_hash = structural_case_manifest_hash(self)
        if self.case_manifest_hash == "pending":
            object.__setattr__(self, "case_manifest_hash", expected_hash)
        elif self.case_manifest_hash != expected_hash:
            raise ValueError("case manifest hash does not match canonical manifest")
        return self


def _validate_request_case_history(
    selected_load_case_ids: tuple[str, ...],
    case_manifests: tuple[StructuralCaseExecutionManifest, ...],
    execution_status: StructuralExecutionStatus,
) -> None:
    manifest_ids = tuple(manifest.load_case_id for manifest in case_manifests)
    if execution_status is StructuralExecutionStatus.SUCCEEDED:
        if manifest_ids != selected_load_case_ids or any(
            case.execution_status is not StructuralExecutionStatus.SUCCEEDED
            for case in case_manifests
        ):
            raise ValueError("successful request manifests must include all selected successful cases")
        return

    if not case_manifests or case_manifests[-1].execution_status is StructuralExecutionStatus.SUCCEEDED:
        raise ValueError("failed request manifests must end with a failed case")
    if any(
        case.execution_status is not StructuralExecutionStatus.SUCCEEDED
        for case in case_manifests[:-1]
    ):
        raise ValueError("failed request manifests cannot contain a case after the first failure")


class StructuralRequestExecutionManifest(_ImmutableFiniteModel):
    selected_load_case_ids: tuple[str, ...]
    case_manifests: tuple[StructuralCaseExecutionManifest, ...]
    mesh_artifact_id: str | None = Field(default=None, min_length=1)
    mesh_artifact_hash: str | None = Field(default=None, min_length=1)
    analytical_policy_hash: str | None = Field(default=None, min_length=1)
    execution_status: StructuralExecutionStatus = StructuralExecutionStatus.SUCCEEDED
    request_manifest_hash: str = "pending"

    @model_validator(mode="after")
    def validate_ordered_case_ids(self):
        if (self.mesh_artifact_id is None) != (self.mesh_artifact_hash is None):
            raise ValueError("shared mesh artifact ID and hash must be supplied together")
        if not self.selected_load_case_ids:
            raise ValueError("load-case IDs must be nonempty and ordered")
        if any(not case_id for case_id in self.selected_load_case_ids):
            raise ValueError("load-case IDs must be nonempty and ordered")
        if len(set(self.selected_load_case_ids)) != len(self.selected_load_case_ids):
            raise ValueError("load-case IDs must be unique and ordered")
        if not self.case_manifests:
            raise ValueError("case manifests must be nonempty")
        if self.mesh_artifact_id is None:
            raise ValueError("shared mesh artifact ID and hash are required")
        manifest_ids = tuple(manifest.load_case_id for manifest in self.case_manifests)
        if (
            len(manifest_ids) > len(self.selected_load_case_ids)
            or manifest_ids != self.selected_load_case_ids[:len(manifest_ids)]
        ):
            raise ValueError("case manifests must preserve selected load-case order and prefix")
        _validate_request_case_history(
            self.selected_load_case_ids,
            self.case_manifests,
            self.execution_status,
        )
        if any(
            case.mesh_artifact_id != self.mesh_artifact_id
            or case.mesh_artifact_hash != self.mesh_artifact_hash
            for case in self.case_manifests
        ):
            raise ValueError("case manifests must reference the shared mesh artifact")
        expected_hash = structural_request_manifest_hash(self)
        if self.request_manifest_hash == "pending":
            object.__setattr__(self, "request_manifest_hash", expected_hash)
        elif self.request_manifest_hash != expected_hash:
            raise ValueError("request manifest hash does not match ordered case manifests")
        return self


class StructuralCriterionResult(_ImmutableFiniteModel):
    criterion_id: str = Field(min_length=1)
    status: StructuralCriterionStatus
    reason: str = ""
    consumed_result_field: str | None = None
    observed_value: float | None = None
    allowable_value: float | None = None
    safety_factor: float | None = None
    units: str | None = None

    @model_validator(mode="after")
    def validate_reason(self):
        if self.status is not StructuralCriterionStatus.PASS and not self.reason:
            raise ValueError("criterion reason is required when status is not pass")
        return self


class StructuralLoadCaseResult(_ImmutableFiniteModel):
    run_id: str | None = None
    load_case_id: str = Field(min_length=1)
    mesh_hash: str = Field(min_length=1)
    deck_artifact_hash: str | None = Field(default=None, min_length=1)
    frd_artifact_hash: str | None = Field(default=None, min_length=1)
    dat_artifact_hash: str | None = Field(default=None, min_length=1)
    log_artifact_hash: str | None = Field(default=None, min_length=1)
    displacements: tuple[StructuralDisplacementSample, ...] = ()
    stress_samples: tuple[StructuralStressSample, ...] = ()
    reactions: tuple[StructuralReactionSample, ...] = ()
    requested_result_fields: tuple[StructuralResultField, ...] = ()
    region_node_ids: tuple[tuple[str, tuple[int, ...]], ...] = ()
    maximum_displacement_mm: float | None = None
    maximum_displacement_node_id: int | None = Field(default=None, gt=0)
    maximum_displacement_location_mm: tuple[float, float, float] | None = None
    maximum_von_mises_stress_mpa: float | None = None
    maximum_von_mises_stress_node_id: int | None = Field(default=None, gt=0)
    total_reaction_force_n: tuple[float, float, float] | None = None
    reaction_reference_point_mm: tuple[float, float, float] | None = None
    total_reaction_moment_n_mm: tuple[float, float, float] | None = None
    applied_force_n: tuple[float, float, float] | None = None
    applied_moment_n_mm: tuple[float, float, float] | None = None
    force_equilibrium_residual_n: float | None = None
    moment_equilibrium_residual_n_mm: float | None = None
    equilibrium_policy_id: str | None = None
    equilibrium_status: str | None = None
    equilibrium_diagnostic: str | None = None
    units: StructuralResultUnits = Field(default_factory=StructuralResultUnits)
    parser_provenance: StructuralResultParserProvenance = Field(
        default_factory=StructuralResultParserProvenance
    )
    maturity: StructuralResultMaturity = StructuralResultMaturity.FEA_EXECUTED
    result_hash: str = "pending"

    @model_validator(mode="after")
    def validate_result_integrity(self):
        for sample in (*self.displacements, *self.reactions):
            if sample.mesh_hash != self.mesh_hash:
                raise ValueError("local result mesh hash does not match case mesh hash")
        for sample in self.stress_samples:
            if sample.mesh_hash != self.mesh_hash or sample.identity.mesh_hash != self.mesh_hash:
                raise ValueError("local result mesh hash does not match case mesh hash")
        identities = [sample.identity.model_dump(mode="json", exclude_none=False) for sample in self.stress_samples]
        if len({json.dumps(identity, sort_keys=True, separators=(",", ":")) for identity in identities}) != len(identities):
            raise ValueError("duplicate stress sample identity")
        displacement_identities = [(sample.mesh_hash, sample.node_id) for sample in self.displacements]
        if len(set(displacement_identities)) != len(displacement_identities):
            raise ValueError("duplicate displacement sample identity")
        reaction_identities = [(sample.mesh_hash, sample.node_id) for sample in self.reactions]
        if len(set(reaction_identities)) != len(reaction_identities):
            raise ValueError("duplicate reaction sample identity")
        if (self.displacements or self.stress_samples) and self.frd_artifact_hash is None:
            raise ValueError("FRD artifact hash is required for FRD result fields")
        if self.reactions and self.dat_artifact_hash is None:
            raise ValueError("DAT artifact hash is required for reaction result fields")
        expected_hash = structural_result_hash(self)
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected_hash)
        elif self.result_hash != expected_hash:
            raise ValueError("structural result hash does not match canonical result")
        return self


class StructuralAnalysisResult(_ImmutableFiniteModel):
    run_id: str | None = None
    source_binding: StructuralSourceBinding
    definition_id: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    request_hash: str = Field(min_length=1)
    execution_manifest_hash: str = Field(min_length=1)
    mesh_hash: str = Field(min_length=1)
    load_case_results: tuple[StructuralLoadCaseResult, ...] = Field(min_length=1)
    maturity: StructuralResultMaturity = StructuralResultMaturity.FEA_EXECUTED
    parser_provenance: StructuralResultParserProvenance = Field(
        default_factory=StructuralResultParserProvenance
    )
    result_hash: str = "pending"

    @model_validator(mode="after")
    def validate_case_order_and_mesh(self):
        if self.definition_id != self.source_binding.definition_id:
            raise ValueError("result definition ID does not match source binding")
        if self.definition_hash != self.source_binding.definition_hash:
            raise ValueError("result definition hash does not match source binding")
        case_ids = tuple(case.load_case_id for case in self.load_case_results)
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("load-case IDs must be unique and ordered")
        if any(case.mesh_hash != self.mesh_hash for case in self.load_case_results):
            raise ValueError("case result mesh hash does not match analysis mesh hash")
        expected_hash = structural_result_hash(self)
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected_hash)
        elif self.result_hash != expected_hash:
            raise ValueError("structural result hash does not match canonical result")
        return self


class StructuralVerificationResult(_ImmutableFiniteModel):
    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    definition_id: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    request_hash: str = Field(min_length=1)
    execution_manifest_hash: str = Field(min_length=1)
    result_hash: str = Field(min_length=1)
    mesh_hash: str = Field(min_length=1)
    raw_artifact_hashes: tuple[str, ...] = Field(min_length=1)
    parser_provenance: StructuralResultParserProvenance
    overall_status: StructuralCriterionStatus
    criterion_results: tuple[StructuralCriterionResult, ...]
    verification_hash: str = "pending"

    @model_validator(mode="after")
    def validate_overall_status_and_hash(self):
        statuses = {result.status for result in self.criterion_results}
        expected_status = (
            StructuralCriterionStatus.FAIL
            if StructuralCriterionStatus.FAIL in statuses
            else StructuralCriterionStatus.NOT_EVALUABLE
            if not self.criterion_results or StructuralCriterionStatus.NOT_EVALUABLE in statuses
            else StructuralCriterionStatus.PASS
        )
        if self.overall_status is not expected_status:
            raise ValueError("overall criterion status does not match criterion results")
        if any(not artifact_hash for artifact_hash in self.raw_artifact_hashes):
            raise ValueError("raw artifact hashes must be nonempty")
        criterion_ids = [result.criterion_id for result in self.criterion_results]
        if len(set(criterion_ids)) != len(criterion_ids):
            raise ValueError("criterion IDs must be unique")
        expected_hash = structural_verification_hash(self)
        if self.verification_hash == "pending":
            object.__setattr__(self, "verification_hash", expected_hash)
        elif self.verification_hash != expected_hash:
            raise ValueError("verification hash does not match canonical verification")
        return self


class StructuralExecutionResult(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    run_id: str | None = None
    execution_status: StructuralExecutionStatus
    failure_stage: str = ""
    error_detail: str = ""
    manifest: StructuralExecutionManifest | None = None
    produced_artifact_ids: tuple[str, ...] = ()


class StructuralExecutionManifest(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    project_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    state_hash: str = Field(min_length=1)
    definition_id: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    request_hash: str = Field(min_length=1)
    analytical_policy_hash: str | None = Field(default=None, min_length=1)
    run_id: str = Field(min_length=1)

    geometry_artifact_id: str = Field(min_length=1)
    geometry_artifact_hash: str = Field(min_length=1)
    geometry_provider_provenance: BackendProvenance | None = None

    region_map_hash: str = Field(min_length=1)
    resolver_identity: str = Field(min_length=1)
    resolver_version: str = Field(min_length=1)

    gmsh_identity: str = Field(min_length=1)
    gmsh_version: str = Field(min_length=1)
    mesh_specification_hash: str = Field(min_length=1)
    mesh_artifact_id: str = Field(min_length=1)
    mesh_artifact_hash: str = Field(min_length=1)
    mesh_manifest: StructuralMeshManifest | None = None
    mesh_manifest_hash: str | None = Field(default=None, min_length=1)

    deck_builder_identity: str = Field(min_length=1)
    deck_builder_version: str = Field(min_length=1)
    deck_semantic_hash: str | None = Field(default=None, min_length=1)
    deck_artifact_id: str | None = Field(default=None, min_length=1)
    deck_artifact_hash: str | None = Field(default=None, min_length=1)

    calculix_identity: str = Field(min_length=1)
    calculix_version: str = Field(min_length=1)
    execution_status: StructuralExecutionStatus

    solver_manifest: StructuralSolverManifest | None = None
    log_artifact_id: str | None = Field(default=None, min_length=1)
    log_artifact_hash: str | None = Field(default=None, min_length=1)
    frd_artifact_id: str | None = Field(default=None, min_length=1)
    frd_artifact_hash: str | None = Field(default=None, min_length=1)
    dat_artifact_id: str | None = Field(default=None, min_length=1)
    dat_artifact_hash: str | None = Field(default=None, min_length=1)

    artifacts: tuple[StructuralArtifactRef, ...] = ()
    lowered_loads: tuple[LoweredLoadProvenance, ...] = ()
    selected_load_case_ids: tuple[str, ...] | None = None
    case_manifests: tuple[StructuralCaseExecutionManifest, ...] = ()
    maturity: StructuralResultMaturity | None = None
    request_manifest_hash: str | None = None

    @model_validator(mode="after")
    def validate_artifact_pairs(self):
        for artifact_id, artifact_hash in (
            (self.deck_artifact_id, self.deck_artifact_hash),
            (self.log_artifact_id, self.log_artifact_hash),
            (self.frd_artifact_id, self.frd_artifact_hash),
            (self.dat_artifact_id, self.dat_artifact_hash),
        ):
            if (artifact_id is None) != (artifact_hash is None):
                raise ValueError("artifact IDs and hashes must be supplied together")
        return self

    @model_validator(mode="after")
    def validate_multi_case_legacy_fields(self):
        if self.selected_load_case_ids is not None and len(self.selected_load_case_ids) > 1:
            if any(
                value is not None
                for value in (
                    self.deck_semantic_hash,
                    self.deck_artifact_id,
                    self.deck_artifact_hash,
                    self.solver_manifest,
                    self.log_artifact_id,
                    self.log_artifact_hash,
                    self.frd_artifact_id,
                    self.frd_artifact_hash,
                    self.dat_artifact_id,
                    self.dat_artifact_hash,
                )
            ):
                raise ValueError("legacy top-level artifact and solver fields are unavailable for multi-case manifests")
        return self

    @model_validator(mode="after")
    def validate_case_manifest_order(self):
        if self.selected_load_case_ids is None:
            if self.case_manifests:
                raise ValueError("case manifests require selected load-case IDs")
            return self
        if not self.selected_load_case_ids or any(not case_id for case_id in self.selected_load_case_ids):
            raise ValueError("load-case IDs must be nonempty and ordered")
        if len(set(self.selected_load_case_ids)) != len(self.selected_load_case_ids):
            raise ValueError("load-case IDs must be unique and ordered")
        expected_hash = structural_request_manifest_hash(
            StructuralRequestExecutionManifest(
                selected_load_case_ids=self.selected_load_case_ids,
                case_manifests=self.case_manifests,
                mesh_artifact_id=self.mesh_artifact_id,
                mesh_artifact_hash=self.mesh_artifact_hash,
                analytical_policy_hash=self.analytical_policy_hash,
                execution_status=self.execution_status,
            )
        )
        if self.request_manifest_hash is None:
            object.__setattr__(self, "request_manifest_hash", expected_hash)
        elif self.request_manifest_hash != expected_hash:
            raise ValueError("request manifest hash does not match ordered case manifests")
        return self


# ---------------------------------------------------------------------------
# Deterministic semantic hashing helpers (engineering identity, no volatile data)
# ---------------------------------------------------------------------------
def _stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def resolved_region_hash(region: ResolvedStructuralRegion) -> str:
    payload = {
        "region_id": region.region_id,
        "source_geometry_hash": region.source_geometry_hash,
        "resolver_identity": region.resolver_identity,
        "resolver_version": region.resolver_version,
        "geometry_kind": region.geometry_kind.value,
        "area": region.exact_brep_area_mm2,
        "centroid": region.exact_brep_centroid_mm,
        "normal": region.plane_normal,
        "bbox": region.bounding_box_mm,
        "expected_cardinality": region.expected_cardinality,
        "actual_cardinality": region.actual_cardinality,
        "semantic_descriptor": region.semantic_descriptor,
    }
    return "sha256:" + sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def region_map_hash(regions: tuple[ResolvedStructuralRegion, ...], *, source_geometry_hash: str,
                    match_policy_id: str) -> str:
    payload = {
        "source_geometry_hash": source_geometry_hash,
        "match_policy_id": match_policy_id,
        "regions": sorted(r.region_realization_hash for r in regions),
    }
    return "sha256:" + sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def mesh_manifest_hash(manifest: StructuralMeshManifest) -> str:
    payload = manifest.model_dump(mode="json")
    payload.pop("mesh_hash", None)
    return "sha256:" + sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def lowered_load_semantic_hash(nodal_loads: dict[int, tuple[float, float, float]]) -> str:
    ordered = {str(node): [round(v, 12) for v in vec] for node, vec in sorted(nodal_loads.items())}
    return "sha256:" + sha256(_stable_json(ordered).encode("utf-8")).hexdigest()


def canonical_load_semantic_hash(load) -> str:
    return _hash_payload(load.model_dump(mode="json"))


def mesh_input_hash(*, source_geometry_hash: str, mesh_specification_hash: str,
                    region_map_hash: str, gmsh_identity: str, gmsh_version: str) -> str:
    return _hash_payload({
        "source_geometry_hash": source_geometry_hash,
        "mesh_specification_hash": mesh_specification_hash,
        "region_map_hash": region_map_hash,
        "gmsh_identity": gmsh_identity,
        "gmsh_version": gmsh_version,
    })


def deck_semantic_hash(deck_text: str) -> str:
    return "sha256:" + sha256(deck_text.encode("utf-8")).hexdigest()


def _engineering_payload(value, *, identity_field: str | None = None):
    payload = value.model_dump(mode="json") if isinstance(value, Model) else value

    def remove_run_ids(item):
        if isinstance(item, dict):
            return {
                key: remove_run_ids(child)
                for key, child in item.items()
                if key != "run_id"
            }
        if isinstance(item, list):
            return [remove_run_ids(child) for child in item]
        return item

    payload = remove_run_ids(payload)
    if identity_field is not None:
        payload.pop(identity_field, None)
    return payload


def _hash_payload(payload) -> str:
    return "sha256:" + sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def structural_case_manifest_hash(manifest: StructuralCaseExecutionManifest) -> str:
    return _hash_payload(_engineering_payload(manifest, identity_field="case_manifest_hash"))


def structural_request_manifest_hash(manifest: StructuralRequestExecutionManifest) -> str:
    payload = {
        "selected_load_case_ids": list(manifest.selected_load_case_ids),
        "mesh_artifact_id": manifest.mesh_artifact_id,
        "mesh_artifact_hash": manifest.mesh_artifact_hash,
        "analytical_policy_hash": manifest.analytical_policy_hash,
        "case_manifests": [
            {
                "load_case_id": case_manifest.load_case_id,
                "case_manifest_hash": case_manifest.case_manifest_hash,
            }
            for case_manifest in manifest.case_manifests
        ],
    }
    return _hash_payload(payload)


def structural_result_hash(result: StructuralLoadCaseResult | StructuralAnalysisResult) -> str:
    return _hash_payload(_engineering_payload(result, identity_field="result_hash"))


def structural_verification_hash(result: StructuralVerificationResult) -> str:
    return _hash_payload(_engineering_payload(result, identity_field="verification_hash"))


def execution_manifest_hash(manifest: StructuralExecutionManifest) -> str:
    return _hash_payload(_engineering_payload(manifest))


def geometry_sha256(content: bytes) -> str:
    return "sha256:" + sha256(content).hexdigest()


def finite_vector(value) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2]))
