from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


POLICY_ID = "rectangular-cantilever-linear-static-validation@1"
TIP_METRIC_ID = "free_end_cps6_quadratic_surface_integral_transverse_over_area@1"


class _StructuralEvidenceModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _finite_tuple(value: tuple[float, ...], name: str) -> tuple[float, ...]:
    if not all(math.isfinite(component) for component in value):
        raise ValueError(f"{name} must contain only finite values")
    return value


class RectangularCantileverValidationPolicy(_StructuralEvidenceModel):
    """Frozen analytical declarations made before a structural execution."""

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


class CantileverGeometryObservation(_StructuralEvidenceModel):
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


class CantileverMaterialObservation(_StructuralEvidenceModel):
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


class AnalyticalValidationCheck(_StructuralEvidenceModel):
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

    @field_validator("expected_value", "observed_value", mode="before")
    @classmethod
    def normalize_vector_values(cls, value):
        return tuple(value) if isinstance(value, list) else value

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


class StructuralAnalyticalValidationResult(_StructuralEvidenceModel):
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
