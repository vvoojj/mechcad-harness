from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Literal

from pydantic import Field, model_validator

from mechcad_harness.models.common import Model
from mechcad_harness.models.structural import (
    StructuralAnalysisDefinition,
    StructuralMaterialPropertyName,
    structural_definition_hash,
)
from mechcad_harness.structural.geometry import GeometryRealization
from mechcad_harness.structural.mesh import FrozenParsedMesh, ParsedMesh, freeze_parsed_mesh
from mechcad_harness.structural.models import (
    StructuralAnalysisResult,
    StructuralExecutionManifest,
    StructuralLoadCaseResult,
    execution_manifest_hash,
    structural_result_hash,
)
from mechcad_harness.structural_request import StructuralAnalysisRequest, structural_request_hash


POLICY_ID = "rectangular-cantilever-linear-static-validation@1"
TIP_METRIC_ID = "free_end_cps6_quadratic_surface_integral_transverse_over_area@1"


def _finite_tuple(value: tuple[float, ...], name: str) -> tuple[float, ...]:
    if not all(math.isfinite(component) for component in value):
        raise ValueError(f"{name} must contain only finite values")
    return value


class RectangularCantileverValidationPolicy(Model):
    """Frozen analytical declarations made before a structural execution."""

    model_config = {"frozen": True, "extra": "forbid"}

    policy_id: Literal[POLICY_ID] = POLICY_ID
    request_hash: str | None = Field(default=None, min_length=1)
    geometry_artifact_hash: str | None = Field(default=None, min_length=1)
    material_identity: str = Field(min_length=1)
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    elastic_modulus_mpa: float = Field(gt=0)
    poisson_ratio: float
    resultant_force_n: tuple[float, float, float]
    mesh_specification_hash: str = Field(min_length=1)
    mesh_hash: str | None = Field(default=None, min_length=1)
    region_map_hash: str | None = Field(default=None, min_length=1)
    free_end_region_id: str = Field(min_length=1)
    fixed_end_region_id: str = Field(min_length=1)
    free_end_area_mm2: float = Field(gt=0)
    displacement_relative_tolerance: float = Field(gt=0)
    reaction_relative_tolerance: float = Field(gt=0)
    load_case_id: str = Field(default="LC-1", min_length=1)
    transverse_axis: Literal[0, 1, 2] = 1
    transverse_sign_convention: Literal["signed_applied_force_direction"] = "signed_applied_force_direction"
    tip_displacement_metric: Literal[TIP_METRIC_ID] = TIP_METRIC_ID
    second_moment_equation: Literal["I=width_mm*height_mm^3/12"] = "I=width_mm*height_mm^3/12"
    tip_displacement_equation: Literal["delta=F*length_mm^3/(3*E*I)"] = (
        "delta=F*length_mm^3/(3*E*I)"
    )
    reference_point_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @model_validator(mode="after")
    def validate_declarations(self):
        scalar_values = (
            self.length_mm,
            self.width_mm,
            self.height_mm,
            self.elastic_modulus_mpa,
            self.poisson_ratio,
            self.free_end_area_mm2,
            self.displacement_relative_tolerance,
            self.reaction_relative_tolerance,
        )
        if not all(math.isfinite(value) for value in scalar_values):
            raise ValueError("cantilever policy scalars must be finite")
        if not -1 < self.poisson_ratio < 0.5:
            raise ValueError("poisson_ratio must be finite, greater than -1, and less than 0.5")
        _finite_tuple(self.resultant_force_n, "resultant_force_n")
        _finite_tuple(self.reference_point_mm, "reference_point_mm")
        if all(component == 0.0 for component in self.resultant_force_n):
            raise ValueError("resultant_force_n must be nonzero")
        return self


class CantileverGeometryObservation(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    definition_id: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    geometry_artifact_id: str = Field(min_length=1)
    geometry_artifact_hash: str = Field(min_length=1)
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    free_end_area_mm2: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_finite(self):
        if not all(math.isfinite(value) for value in (self.length_mm, self.width_mm, self.height_mm)):
            raise ValueError("geometry observation must be finite")
        return self


class CantileverMaterialObservation(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    definition_id: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    geometry_artifact_id: str = Field(min_length=1)
    geometry_artifact_hash: str = Field(min_length=1)
    material_identity: str = Field(min_length=1)
    elastic_modulus_mpa: float = Field(gt=0)
    poisson_ratio: float
    material_assignment_id: str | None = Field(default=None, min_length=1)
    elastic_modulus_source_identity: str | None = Field(default=None, min_length=1)
    poisson_ratio_source_identity: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_finite(self):
        if not all(math.isfinite(value) for value in (self.elastic_modulus_mpa, self.poisson_ratio)):
            raise ValueError("material observation must be finite")
        if not -1 < self.poisson_ratio < 0.5:
            raise ValueError("material observation Poisson ratio is outside the admissible range")
        return self


def cantilever_geometry_observation(
    request: StructuralAnalysisRequest,
    definition: StructuralAnalysisDefinition,
    realization: GeometryRealization,
    region_map,
) -> CantileverGeometryObservation:
    """Build geometry facts from the trusted realized BREP and semantic map."""
    if structural_definition_hash(definition) != request.source_binding.definition_hash:
        raise ValueError("geometry observation definition hash does not match source binding")
    if realization.bounding_box is None:
        raise ValueError("trusted geometry realization has no bounding box")
    xmin, ymin, zmin, xmax, ymax, zmax = realization.bounding_box
    region = next(
        (item for item in region_map.regions if item.region_id == "free"),
        None,
    )
    if region is None:
        raise ValueError("trusted region map has no free cantilever region")
    return CantileverGeometryObservation(
        project_id=request.source_binding.project_id,
        source_revision=request.source_binding.source_revision,
        source_state_hash=request.source_binding.source_state_hash,
        definition_id=definition.id,
        definition_hash=request.source_binding.definition_hash,
        geometry_artifact_id=request.source_binding.geometry_artifact_id,
        geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
        length_mm=xmax - xmin,
        width_mm=ymax - ymin,
        height_mm=zmax - zmin,
        free_end_area_mm2=region.exact_brep_area_mm2,
    )


def cantilever_material_observation(
    request: StructuralAnalysisRequest,
    definition: StructuralAnalysisDefinition,
) -> CantileverMaterialObservation:
    """Build material facts from the canonical property snapshots."""
    if structural_definition_hash(definition) != request.source_binding.definition_hash:
        raise ValueError("material observation definition hash does not match source binding")
    assignment = definition.material_assignment
    snapshots = {snapshot.property_name: snapshot for snapshot in assignment.property_snapshot}
    elastic = snapshots.get(StructuralMaterialPropertyName.ELASTIC_MODULUS)
    poisson = snapshots.get(StructuralMaterialPropertyName.POISSON_RATIO)
    if elastic is None or poisson is None:
        raise ValueError("canonical material assignment lacks elastic or Poisson snapshot")
    return CantileverMaterialObservation(
        project_id=request.source_binding.project_id,
        source_revision=request.source_binding.source_revision,
        source_state_hash=request.source_binding.source_state_hash,
        definition_id=definition.id,
        definition_hash=request.source_binding.definition_hash,
        geometry_artifact_id=request.source_binding.geometry_artifact_id,
        geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
        material_identity=assignment.material_identity,
        elastic_modulus_mpa=elastic.value,
        poisson_ratio=poisson.value,
        material_assignment_id=assignment.assignment_id,
        elastic_modulus_source_identity=elastic.source_identity,
        poisson_ratio_source_identity=poisson.source_identity,
    )


class AnalyticalValidationCheck(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    check_id: Literal[
        "geometry", "material", "load", "tip_displacement", "reaction_force", "reaction_moment"
    ]
    expected_value: Any
    observed_value: Any
    absolute_error: float | None = None
    relative_error: float | None = None
    tolerance: float
    status: Literal["pass", "fail", "not_evaluable"]
    reason: str = ""

    @model_validator(mode="after")
    def validate_finite_errors(self):
        for value in (self.absolute_error, self.relative_error, self.tolerance):
            if value is not None and not math.isfinite(value):
                raise ValueError("analytical validation errors must be finite")
        if self.tolerance < 0:
            raise ValueError("analytical validation tolerance must be nonnegative")
        expected_absolute, expected_relative = _error(self.expected_value, self.observed_value)
        if self.expected_value is None or self.observed_value is None:
            if self.absolute_error is not None or self.relative_error is not None:
                raise ValueError("analytical check status and errors are inconsistent")
        elif self.absolute_error != expected_absolute or self.relative_error != expected_relative:
            raise ValueError("analytical check status and errors are inconsistent")
        if self.status == "pass":
            if self.absolute_error is None or self.relative_error is None or self.reason:
                raise ValueError("analytical check status and errors are inconsistent")
            if self.relative_error > self.tolerance:
                raise ValueError("analytical check status and errors are inconsistent")
        elif self.status == "not_evaluable":
            if self.absolute_error is not None or self.relative_error is not None or not self.reason:
                raise ValueError("analytical check status and errors are inconsistent")
        elif not self.reason:
            raise ValueError("analytical check status and errors are inconsistent")
        return self


class StructuralAnalyticalValidationResult(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    policy: RectangularCantileverValidationPolicy
    policy_hash: str = Field(min_length=1)
    source_result_hash: str = Field(min_length=1)
    source_request_hash: str = Field(min_length=1)
    source_execution_manifest_hash: str = Field(min_length=1)
    status: Literal["pass", "fail", "not_evaluable"]
    checks: tuple[AnalyticalValidationCheck, ...] = Field(min_length=1)
    validation_hash: str = "pending"

    @model_validator(mode="after")
    def validate_status_and_hash(self):
        if self.policy_hash != cantilever_validation_policy_hash(self.policy):
            raise ValueError("analytical policy hash does not match canonical policy")
        if self.policy.request_hash is not None and self.source_request_hash != self.policy.request_hash:
            raise ValueError("analytical policy is not bound to the source request")
        expected_status = (
            "fail" if any(check.status == "fail" for check in self.checks)
            else "not_evaluable" if any(check.status == "not_evaluable" for check in self.checks)
            else "pass"
        )
        if self.status != expected_status:
            raise ValueError("analytical validation status does not match checks")
        check_ids = [check.check_id for check in self.checks]
        if len(set(check_ids)) != len(check_ids):
            raise ValueError("analytical validation check IDs must be unique")
        if set(check_ids) != {
            "geometry", "material", "load", "tip_displacement", "reaction_force", "reaction_moment",
        }:
            raise ValueError("analytical validation requires exactly six checks")
        expected_hash = structural_analytical_validation_hash(self)
        if self.validation_hash == "pending":
            object.__setattr__(self, "validation_hash", expected_hash)
        elif self.validation_hash != expected_hash:
            raise ValueError("analytical validation hash does not match canonical validation")
        return self


AnalyticalValidationResult = StructuralAnalyticalValidationResult


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def cantilever_validation_policy_hash(policy: RectangularCantileverValidationPolicy) -> str:
    payload = policy.model_dump(mode="json")
    # The source request binds this policy hash; excluding the request hash
    # avoids a circular request-hash/policy-hash construction.
    payload.pop("request_hash", None)
    return _stable_hash(payload)


def structural_analytical_validation_hash(result: StructuralAnalyticalValidationResult) -> str:
    payload = result.model_dump(mode="json")
    payload.pop("validation_hash", None)
    return _stable_hash(payload)


def _vector_norm(value: tuple[float, float, float]) -> float:
    return math.sqrt(sum(component * component for component in value))


def _vector_subtract(left: tuple[float, float, float], right: tuple[float, float, float]):
    return tuple(left[index] - right[index] for index in range(3))


def _cross(left: tuple[float, float, float], right: tuple[float, float, float]):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _mesh_hash(mesh: ParsedMesh) -> str:
    return "sha256:" + hashlib.sha256(mesh.mesh_bytes).hexdigest()


def _case(result: StructuralLoadCaseResult | StructuralAnalysisResult, policy):
    if isinstance(result, StructuralLoadCaseResult):
        return result
    matches = tuple(case for case in result.load_case_results if case.load_case_id == policy.load_case_id)
    return matches[0] if len(matches) == 1 else None


def _error(expected: Any, observed: Any) -> tuple[float | None, float | None]:
    if expected is None or observed is None:
        return None, None
    if isinstance(expected, (tuple, list)) and isinstance(observed, (tuple, list)):
        if len(expected) != len(observed):
            return None, None
        difference = tuple(observed[index] - expected[index] for index in range(len(expected)))
        absolute = math.sqrt(sum(component * component for component in difference))
        denominator = math.sqrt(sum(component * component for component in expected))
    else:
        absolute = abs(float(observed) - float(expected))
        denominator = abs(float(expected))
    return absolute, absolute / denominator if denominator else (0.0 if absolute == 0 else None)


def _check(check_id, expected, observed, tolerance, *, reason="", forced_reason="", not_evaluable=False):
    absolute, relative = _error(expected, observed)
    status = (
        "not_evaluable" if not_evaluable
        else "pass" if not forced_reason and absolute is not None and relative is not None and relative <= tolerance
        else "fail"
    )
    failure_reason = "" if status == "pass" else forced_reason or reason or "outside_tolerance"
    if status == "not_evaluable":
        absolute = relative = None
    return AnalyticalValidationCheck(
        check_id=check_id,
        expected_value=expected,
        observed_value=observed,
        absolute_error=absolute,
        relative_error=relative,
        tolerance=tolerance,
        status=status,
        reason=failure_reason,
    )


class StructuralAnalyticalValidator:
    """Compare trusted solver fields with one immutable cantilever policy."""

    def validate(
        self,
        result: StructuralLoadCaseResult | StructuralAnalysisResult,
        policy: RectangularCantileverValidationPolicy,
        *,
        request: StructuralAnalysisRequest,
        execution_manifest: StructuralExecutionManifest,
        mesh: ParsedMesh,
        mesh_artifact_bytes: bytes,
        geometry_observation: CantileverGeometryObservation | None,
        material_observation: CantileverMaterialObservation | None,
        definition: StructuralAnalysisDefinition | None = None,
    ) -> StructuralAnalyticalValidationResult:
        if not isinstance(request, StructuralAnalysisRequest):
            raise TypeError("analytical validation requires a typed structural request")
        if not isinstance(execution_manifest, StructuralExecutionManifest):
            raise TypeError("analytical validation requires a typed execution manifest")
        if not isinstance(mesh, (ParsedMesh, FrozenParsedMesh)):
            raise TypeError("analytical validation requires a trusted ParsedMesh")
        if not isinstance(mesh_artifact_bytes, bytes) or not mesh_artifact_bytes:
            raise TypeError("analytical validation requires authoritative MSH artifact bytes")
        from mechcad_harness.structural.results import parse_trusted_msh_bytes

        try:
            mesh = freeze_parsed_mesh(parse_trusted_msh_bytes(mesh_artifact_bytes))
        except Exception as exc:
            raise ValueError("authoritative MSH artifact bytes are not a valid trusted mesh") from exc
        if geometry_observation is not None and not isinstance(geometry_observation, CantileverGeometryObservation):
            raise TypeError("analytical validation requires a typed geometry observation")
        if material_observation is not None and not isinstance(material_observation, CantileverMaterialObservation):
            raise TypeError("analytical validation requires a typed material observation")

        case = _case(result, policy)
        manifest_cases = tuple(
            case_manifest
            for case_manifest in execution_manifest.case_manifests
            if case_manifest.load_case_id == policy.load_case_id
        )
        dynamic_fields = tuple(
            field_name
            for value in ((result,) if case is None else (result, case))
            for field_name in vars(value)
            if field_name.startswith("analytical_")
        )
        if dynamic_fields:
            raise ValueError("dynamic analytical observation fields are not trusted")

        actual_result_hash = structural_result_hash(result)
        if result.result_hash != actual_result_hash:
            raise ValueError("source structural_result_hash does not match the actual result")

        source_request_hash = result.request_hash if isinstance(result, StructuralAnalysisResult) else request.request_hash
        source_execution_hash = (
            result.execution_manifest_hash
            if isinstance(result, StructuralAnalysisResult)
            else execution_manifest_hash(execution_manifest)
        )
        request_mesh_hash = _mesh_specification_hash(request)
        computed_mesh_hash = _mesh_hash(mesh)
        manifest_mesh = execution_manifest.mesh_manifest
        manifest_groups = tuple(manifest_mesh.physical_groups) if manifest_mesh is not None else ()
        actual_groups = tuple(mesh.physical_groups)
        mesh_binding_reason = ""
        if request.request_hash != structural_request_hash(request):
            mesh_binding_reason = "request hash does not match canonical request"
        elif policy.request_hash is not None and policy.request_hash != request.request_hash:
            mesh_binding_reason = "policy/result request hash mismatch"
        elif source_request_hash != request.request_hash:
            mesh_binding_reason = "policy/result request hash mismatch"
        elif not request.analytical_policy_hash:
            mesh_binding_reason = "analytical policy hash is absent from the source request"
        elif request.analytical_policy_hash != cantilever_validation_policy_hash(policy):
            mesh_binding_reason = "source request analytical policy hash mismatch"
        elif execution_manifest.analytical_policy_hash != request.analytical_policy_hash:
            mesh_binding_reason = "execution manifest analytical policy hash mismatch"
        elif (
            policy.geometry_artifact_hash is not None
            and policy.geometry_artifact_hash != request.source_binding.geometry_artifact_hash
        ):
            mesh_binding_reason = "policy geometry artifact binding mismatch"
        elif execution_manifest.project_id != request.source_binding.project_id or execution_manifest.revision != request.source_binding.source_revision or execution_manifest.state_hash != request.source_binding.source_state_hash:
            mesh_binding_reason = "execution manifest source binding mismatch"
        elif execution_manifest.definition_id != request.source_binding.definition_id or execution_manifest.definition_hash != request.source_binding.definition_hash:
            mesh_binding_reason = "execution manifest definition binding mismatch"
        elif execution_manifest.geometry_artifact_id != request.source_binding.geometry_artifact_id or execution_manifest.geometry_artifact_hash != request.source_binding.geometry_artifact_hash:
            mesh_binding_reason = "execution manifest geometry artifact binding mismatch"
        elif execution_manifest.selected_load_case_ids != request.selected_load_case_ids:
            mesh_binding_reason = "execution manifest load-case selection mismatch"
        elif len(manifest_cases) != 1 or case is None or manifest_cases[0].load_case_id != case.load_case_id:
            mesh_binding_reason = "result load-case provenance mismatch"
        elif isinstance(result, StructuralAnalysisResult) and (
            result.source_binding != request.source_binding
            or result.definition_id != request.source_binding.definition_id
            or result.definition_hash != request.source_binding.definition_hash
        ):
            mesh_binding_reason = "result source binding mismatch"
        elif manifest_cases and (
            manifest_cases[0].frd_artifact_hash != case.frd_artifact_hash
            or manifest_cases[0].dat_artifact_hash != case.dat_artifact_hash
            or manifest_cases[0].log_artifact_hash != case.log_artifact_hash
            or manifest_cases[0].deck_artifact_hash != case.deck_artifact_hash
        ):
            mesh_binding_reason = "result artifact provenance mismatch"
        elif isinstance(result, StructuralAnalysisResult) and source_execution_hash != execution_manifest_hash(execution_manifest):
            mesh_binding_reason = "result execution-manifest hash mismatch"
        elif execution_manifest.execution_status.value != "succeeded":
            mesh_binding_reason = "execution manifest is not successful"
        elif execution_manifest.request_hash != request.request_hash:
            mesh_binding_reason = "execution manifest request hash mismatch"
        elif execution_manifest.mesh_specification_hash != request_mesh_hash:
            mesh_binding_reason = "execution manifest mesh specification hash mismatch"
        elif manifest_mesh is None or manifest_mesh.mesh_specification_hash != request_mesh_hash:
            mesh_binding_reason = "mesh manifest mesh specification hash mismatch"
        elif (
            policy.mesh_specification_hash is not None
            and policy.mesh_specification_hash != request_mesh_hash
        ):
            mesh_binding_reason = "policy mesh specification hash mismatch"
        elif (
            (policy.mesh_hash is not None and policy.mesh_hash != computed_mesh_hash)
            or execution_manifest.mesh_artifact_hash != computed_mesh_hash
            or manifest_mesh is None
            or manifest_mesh.mesh_hash != computed_mesh_hash
            or case is None
            or case.mesh_hash != computed_mesh_hash
            or any(
                case_manifest.mesh_artifact_hash != computed_mesh_hash
                for case_manifest in execution_manifest.case_manifests
            )
            or any(
                case_manifest.mesh_artifact_id != execution_manifest.mesh_artifact_id
                for case_manifest in execution_manifest.case_manifests
            )
        ):
            mesh_binding_reason = "exact mesh byte hash mismatch"
        elif (
            (
                policy.region_map_hash is not None
                and manifest_mesh.region_map_hash != policy.region_map_hash
            )
            or execution_manifest.region_map_hash != manifest_mesh.region_map_hash
        ):
            mesh_binding_reason = "region-map hash mismatch"
        elif tuple(sorted(actual_groups, key=lambda group: (group.gmsh_entity_dim, group.physical_group_name, group.gmsh_entity_id))) != tuple(
            sorted(manifest_groups, key=lambda group: (group.gmsh_entity_dim, group.physical_group_name, group.gmsh_entity_id))
        ):
            mesh_binding_reason = "trusted mesh region mapping mismatch"

        expected_geometry = (policy.length_mm, policy.width_mm, policy.height_mm)
        observed_geometry = (
            (geometry_observation.length_mm, geometry_observation.width_mm, geometry_observation.height_mm)
            if geometry_observation is not None else None
        )
        geometry_reason = self._observation_binding_reason(geometry_observation, request, execution_manifest)
        geometry_check = _check(
            "geometry", expected_geometry, observed_geometry, 0.0,
            forced_reason=geometry_reason, not_evaluable=geometry_observation is None,
        )

        canonical_material = None
        if definition is not None:
            snapshots = {
                snapshot.property_name: snapshot
                for snapshot in definition.material_assignment.property_snapshot
            }
            elastic = snapshots.get(StructuralMaterialPropertyName.ELASTIC_MODULUS)
            poisson = snapshots.get(StructuralMaterialPropertyName.POISSON_RATIO)
            if elastic is None or poisson is None:
                canonical_material = None
            else:
                canonical_material = (elastic, poisson)
        expected_material = (
            (canonical_material[0].value, canonical_material[1].value)
            if canonical_material is not None
            else (policy.elastic_modulus_mpa, policy.poisson_ratio)
        )
        observed_material = (
            (material_observation.elastic_modulus_mpa, material_observation.poisson_ratio)
            if material_observation is not None else None
        )
        material_reason = self._observation_binding_reason(material_observation, request, execution_manifest)
        if not material_reason and definition is not None and canonical_material is None:
            material_reason = "canonical material snapshots are unavailable"
        if not material_reason and definition is not None and (
            material_observation.material_assignment_id != definition.material_assignment.assignment_id
            or material_observation.material_identity != definition.material_assignment.material_identity
            or material_observation.elastic_modulus_source_identity != canonical_material[0].source_identity
            or material_observation.poisson_ratio_source_identity != canonical_material[1].source_identity
            or material_observation.elastic_modulus_mpa != canonical_material[0].value
            or material_observation.poisson_ratio != canonical_material[1].value
        ):
            material_reason = "material observation is not bound to canonical snapshots"
        if not material_reason and material_observation.material_identity != policy.material_identity:
            material_reason = "material observation identity mismatch"
        material_check = _check(
            "material", expected_material, observed_material, 0.0,
            forced_reason=material_reason, not_evaluable=material_observation is None,
        )

        expected_force = tuple(-component for component in policy.resultant_force_n)
        observed_load = case.applied_force_n if case is not None else None
        transverse_force = policy.resultant_force_n[policy.transverse_axis]
        axial_components = tuple(
            component for index, component in enumerate(policy.resultant_force_n) if index != policy.transverse_axis
        )
        axis_reason = "axial force is outside the declared transverse direction" if any(axial_components) else ""
        load_check = _check(
            "load", policy.resultant_force_n, observed_load, 0.0,
            reason="trusted applied load is unavailable", forced_reason=axis_reason or mesh_binding_reason,
            not_evaluable=observed_load is None and not axis_reason and not mesh_binding_reason,
        )

        expected_tip = self._expected_tip_displacement(policy) if not axis_reason else None
        observed_free_end_area = (
            geometry_observation.free_end_area_mm2
            if geometry_observation is not None
            else None
        )
        free_end_area_reason = (
            "independent observed free-end area is unavailable"
            if observed_free_end_area is None
            or not math.isfinite(observed_free_end_area)
            or observed_free_end_area <= 0
            else ""
        )
        observed_tip = (
            self._tip_displacement(
                case,
                policy,
                mesh,
                free_end_area_mm2=observed_free_end_area,
            )
            if not mesh_binding_reason and not geometry_reason and not free_end_area_reason
            else None
        )
        tip_reason = axis_reason or mesh_binding_reason or geometry_reason or free_end_area_reason
        if observed_tip is None and not tip_reason:
            tip_reason = "complete free-end CPS6 displacement coverage is unavailable"
        tip_not_evaluable = bool(
            (geometry_reason or free_end_area_reason)
            and not axis_reason
            and not mesh_binding_reason
        ) or bool(
            observed_tip is None
            and (case is None or not case.displacements)
            and not axis_reason
            and not mesh_binding_reason
            and not geometry_reason
        )
        tip_check = _check(
            "tip_displacement", expected_tip, observed_tip,
            policy.displacement_relative_tolerance, forced_reason=tip_reason,
            not_evaluable=tip_not_evaluable,
        )

        fixed_reason = self._fixed_region_reason(case, policy, mesh, execution_manifest)
        observed_reaction_force, observed_moment = self._reaction_totals(
            case, mesh, policy.reference_point_mm,
        )
        reaction_force_check = _check(
            "reaction_force", expected_force, observed_reaction_force,
            policy.reaction_relative_tolerance,
            reason="trusted reaction force is unavailable", forced_reason=fixed_reason or mesh_binding_reason,
            not_evaluable=(
                observed_reaction_force is None
                and (case is None or not case.reactions)
                and not mesh_binding_reason
            ),
        )

        free_centroid = self._surface_centroid(mesh, policy.free_end_region_id)
        expected_moment = (
            tuple(
                -component
                for component in _cross(
                    _vector_subtract(free_centroid, policy.reference_point_mm), policy.resultant_force_n
                )
            )
            if free_centroid is not None
            else None
        )
        reference_reason = (
            "reaction reference point does not equal the policy reference point"
            if case is None or case.reaction_reference_point_mm != policy.reference_point_mm
            else ""
        )
        reaction_moment_check = _check(
            "reaction_moment", expected_moment, observed_moment,
            policy.reaction_relative_tolerance,
            reason="trusted reaction moment is unavailable",
            forced_reason=reference_reason or fixed_reason or mesh_binding_reason,
            not_evaluable=(
                observed_moment is None
                and (case is None or not case.reactions)
                and not mesh_binding_reason
            ),
        )

        checks = (geometry_check, material_check, load_check, tip_check, reaction_force_check, reaction_moment_check)
        return StructuralAnalyticalValidationResult(
            policy=policy,
            policy_hash=cantilever_validation_policy_hash(policy),
            source_result_hash=actual_result_hash,
            source_request_hash=source_request_hash,
            source_execution_manifest_hash=source_execution_hash,
            status=(
                "fail" if any(check.status == "fail" for check in checks)
                else "not_evaluable" if any(check.status == "not_evaluable" for check in checks)
                else "pass"
            ),
            checks=checks,
        )

    @staticmethod
    def _observation_binding_reason(observation, request, execution_manifest):
        if observation is None:
            return "independent observation is unavailable"
        expected = (
            request.source_binding.project_id,
            request.source_binding.source_revision,
            request.source_binding.source_state_hash,
            request.source_binding.definition_id,
            request.source_binding.definition_hash,
            request.source_binding.geometry_artifact_id,
            request.source_binding.geometry_artifact_hash,
        )
        observed = (
            observation.project_id,
            observation.source_revision,
            observation.source_state_hash,
            observation.definition_id,
            observation.definition_hash,
            observation.geometry_artifact_id,
            observation.geometry_artifact_hash,
        )
        if observed != expected:
            return "independent observation source binding mismatch"
        if (
            execution_manifest.project_id != observation.project_id
            or execution_manifest.revision != observation.source_revision
            or execution_manifest.state_hash != observation.source_state_hash
            or execution_manifest.definition_id != observation.definition_id
            or execution_manifest.definition_hash != observation.definition_hash
            or execution_manifest.geometry_artifact_id != observation.geometry_artifact_id
            or execution_manifest.geometry_artifact_hash != observation.geometry_artifact_hash
        ):
            return "independent observation execution binding mismatch"
        return ""

    @staticmethod
    def _expected_tip_displacement(policy):
        force = policy.resultant_force_n[policy.transverse_axis]
        second_moment = policy.width_mm * policy.height_mm**3 / 12.0
        return force * policy.length_mm**3 / (3.0 * policy.elastic_modulus_mpa * second_moment)

    @staticmethod
    def _surface_elements(mesh: ParsedMesh, region_id: str):
        elements = tuple(mesh.surface_elements.get(region_id, ()))
        if not elements or any(len(nodes) != 6 for _element_id, nodes in elements):
            return None
        if len({element_id for element_id, _nodes in elements}) != len(elements):
            return None
        return elements

    @classmethod
    def _surface_centroid(cls, mesh: ParsedMesh, region_id: str):
        elements = cls._surface_elements(mesh, region_id)
        if elements is None:
            return None
        total_area = 0.0
        centroid = [0.0, 0.0, 0.0]
        for _element_id, nodes in elements:
            if any(node_id not in mesh.nodes for node_id in nodes):
                return None
            a, b, c = (mesh.nodes[node_id] for node_id in nodes[:3])
            area = 0.5 * _vector_norm(_cross(_vector_subtract(b, a), _vector_subtract(c, a)))
            if area <= 0:
                return None
            point = tuple((a[index] + b[index] + c[index]) / 3.0 for index in range(3))
            total_area += area
            for index in range(3):
                centroid[index] += point[index] * area
        return tuple(value / total_area for value in centroid) if total_area else None

    @staticmethod
    def _reaction_totals(case, mesh: ParsedMesh, reference_point_mm):
        if case is None or not case.reactions:
            return None, None
        total_force = [0.0, 0.0, 0.0]
        total_moment = [0.0, 0.0, 0.0]
        for sample in case.reactions:
            coordinates = mesh.nodes.get(sample.node_id)
            if coordinates is None:
                return None, None
            for index in range(3):
                total_force[index] += sample.vector_n[index]
            moment = _cross(
                tuple(coordinates[index] - reference_point_mm[index] for index in range(3)),
                sample.vector_n,
            )
            for index in range(3):
                total_moment[index] += moment[index]
        return tuple(total_force), tuple(total_moment)

    @classmethod
    def _tip_displacement(cls, case, policy, mesh, *, free_end_area_mm2=None):
        if case is None or free_end_area_mm2 is None:
            return None
        elements = cls._surface_elements(mesh, policy.free_end_region_id)
        if elements is None:
            return None
        coordinates = mesh.nodes
        displacement_samples = {
            sample.node_id: sample.vector_mm[policy.transverse_axis]
            for sample in case.displacements
            if sample.mesh_hash == _mesh_hash(mesh)
        }
        region_nodes = dict(case.region_node_ids).get(policy.free_end_region_id)
        surface_node_ids = {
            node_id for _element_id, nodes in elements for node_id in nodes
        }
        if region_nodes is None or set(region_nodes) != surface_node_ids:
            return None
        if not surface_node_ids.issubset(displacement_samples):
            return None
        total_area = 0.0
        displacement_integral = 0.0
        for _element_id, nodes in elements:
            if any(node_id not in coordinates or node_id not in displacement_samples for node_id in nodes):
                return None
            a, b, c = (coordinates[node_id] for node_id in nodes[:3])
            area = 0.5 * _vector_norm(_cross(_vector_subtract(b, a), _vector_subtract(c, a)))
            if area <= 0:
                return None
            weighted = sum(displacement_samples[node_id] for node_id in nodes[3:]) / 3.0
            displacement_integral += area * weighted
            total_area += area
        area = free_end_area_mm2
        if not math.isclose(total_area, area, rel_tol=1e-9, abs_tol=1e-9):
            return None
        return displacement_integral / area

    @classmethod
    def _fixed_region_reason(cls, case, policy, mesh, execution_manifest):
        if case is None:
            return "fixed-end case is unavailable"
        fixed_elements = cls._surface_elements(mesh, policy.fixed_end_region_id)
        if fixed_elements is None:
            return "trusted fixed-end region mapping is unavailable"
        groups = {group.semantic_region_id for group in mesh.physical_groups}
        if policy.fixed_end_region_id not in groups or policy.free_end_region_id not in groups:
            return "fixed/free region mapping is incomplete"
        if policy.region_map_hash is not None and execution_manifest.region_map_hash != policy.region_map_hash:
            return "fixed-end region map hash mismatch"
        fixed_surface_nodes = {
            node_id for _element_id, nodes in fixed_elements for node_id in nodes
        }
        result_region_nodes = dict(case.region_node_ids).get(policy.fixed_end_region_id)
        if result_region_nodes is None or set(result_region_nodes) != fixed_surface_nodes:
            return "trusted fixed-end region node mapping mismatch"
        expected_support_set = policy.fixed_end_region_id.upper() + "_NODES"
        if not case.reactions or any(sample.support_set_name != expected_support_set for sample in case.reactions):
            return "reactions are not bound to the declared fixed-end region"
        reaction_node_ids = {sample.node_id for sample in case.reactions}
        if reaction_node_ids != fixed_surface_nodes:
            return "reaction node IDs do not exactly match the trusted fixed-end region"
        return ""


def _mesh_specification_hash(request: StructuralAnalysisRequest) -> str:
    payload = request.mesh_specification.model_dump(mode="json")
    return _stable_hash(payload)
