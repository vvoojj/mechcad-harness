from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated, Literal

from pydantic import Field, model_validator

from mechcad_harness.models.common import Model


def analysis_artifact_id(analysis_id: str, plan_hash: str, assembly_artifact_id: str, assembly_artifact_sha256: str, analyzer_version: str) -> str:
    payload = "|".join((analysis_id, plan_hash, assembly_artifact_id, assembly_artifact_sha256, analyzer_version)).encode("utf-8")
    return f"ANALYSIS-{hashlib.sha256(payload).hexdigest()[:24]}"


def _finite_nonnegative(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("value must be finite and non-negative")
    return value


def canonical_instance_pair(instance_a: str, instance_b: str) -> tuple[str, str]:
    if instance_a == instance_b:
        raise ValueError("analysis checks require two distinct instances")
    return tuple(sorted((instance_a, instance_b)))


class _PairCheck(Model):
    check_id: str = Field(min_length=1)
    instance_a: str = Field(min_length=1)
    instance_b: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_pair(self):
        canonical_instance_pair(self.instance_a, self.instance_b)
        return self


class CadInterferenceCheck(_PairCheck):
    kind: Literal["interference"] = "interference"
    max_allowed_interference_volume_mm3: float = 0.0

    @model_validator(mode="after")
    def validate_limit(self):
        self.max_allowed_interference_volume_mm3 = _finite_nonnegative(self.max_allowed_interference_volume_mm3)
        return self


class CadMinimumClearanceCheck(_PairCheck):
    kind: Literal["minimum_clearance"] = "minimum_clearance"
    required_clearance_mm: float = 0.0

    @model_validator(mode="after")
    def validate_requirement(self):
        self.required_clearance_mm = _finite_nonnegative(self.required_clearance_mm)
        return self


CadAnalysisCheck = Annotated[CadInterferenceCheck | CadMinimumClearanceCheck, Field(discriminator="kind")]


class CadAssemblyAnalysisPlan(Model):
    analysis_id: str = Field(min_length=1)
    checks: tuple[CadAnalysisCheck, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_check_ids(self):
        ids = [check.check_id for check in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("analysis check IDs must be unique")
        return self

    @property
    def canonical_checks(self):
        return tuple(sorted(self.checks, key=lambda check: check.check_id))


class CadInterferenceResult(Model):
    check_id: str = Field(min_length=1)
    instance_a: str = Field(min_length=1)
    instance_b: str = Field(min_length=1)
    interference_volume_mm3: float = Field(ge=0)
    allowed_interference_volume_mm3: float = Field(ge=0)
    passed: bool

    @model_validator(mode="after")
    def validate_finite(self):
        if not all(math.isfinite(value) for value in (self.interference_volume_mm3, self.allowed_interference_volume_mm3)):
            raise ValueError("interference values must be finite")
        return self


class CadClearanceResult(Model):
    check_id: str = Field(min_length=1)
    instance_a: str = Field(min_length=1)
    instance_b: str = Field(min_length=1)
    measured_clearance_mm: float = Field(ge=0)
    required_clearance_mm: float = Field(ge=0)
    passed: bool

    @model_validator(mode="after")
    def validate_finite(self):
        if not all(math.isfinite(value) for value in (self.measured_clearance_mm, self.required_clearance_mm)):
            raise ValueError("clearance values must be finite")
        return self


class CadAssemblyAnalysisResult(Model):
    analysis_id: str = Field(min_length=1)
    analysis_plan_hash: str = Field(min_length=1)
    assembly_hash: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    assembly_artifact_id: str = Field(min_length=1)
    assembly_artifact_sha256: str = Field(min_length=1)
    analyzer_version: str = Field(min_length=1)
    freecad_version: str = Field(min_length=1)
    interference: tuple[CadInterferenceResult, ...] = ()
    clearance: tuple[CadClearanceResult, ...] = ()
    passed: bool


class CadClearanceAnalyzer:
    version = "mechcad-freecad-clearance@1.0"
    volume_tolerance_mm3 = 1e-9
    distance_tolerance_mm = 1e-7

    def analyze_shapes(self, plan: CadAssemblyAnalysisPlan, assembly_hash_value: str, shapes: dict[str, object], *, project_id="analysis", run_id="analysis", source_revision=1, source_state_hash="sha256:source", assembly_artifact_id="assembly", assembly_artifact_sha256="sha256:assembly", freecad_version="unknown") -> CadAssemblyAnalysisResult:
        interference = []
        clearance = []
        for check in plan.canonical_checks:
            first, second = canonical_instance_pair(check.instance_a, check.instance_b)
            if first not in shapes or second not in shapes:
                raise ValueError("analysis check references an unknown instance")
            shape_a, shape_b = shapes[first], shapes[second]
            common_volume = float(shape_a.common(shape_b).Volume)
            if not math.isfinite(common_volume) or common_volume < 0:
                raise ValueError("interference volume must be finite and non-negative")
            if isinstance(check, CadInterferenceCheck):
                interference.append(CadInterferenceResult(check_id=check.check_id, instance_a=first, instance_b=second, interference_volume_mm3=common_volume, allowed_interference_volume_mm3=check.max_allowed_interference_volume_mm3, passed=common_volume <= check.max_allowed_interference_volume_mm3 + self.volume_tolerance_mm3))
            else:
                measured = 0.0 if common_volume > self.volume_tolerance_mm3 else float(shape_a.distToShape(shape_b)[0])
                if not math.isfinite(measured) or measured < 0:
                    raise ValueError("clearance must be finite and non-negative")
                clearance.append(CadClearanceResult(check_id=check.check_id, instance_a=first, instance_b=second, measured_clearance_mm=measured, required_clearance_mm=check.required_clearance_mm, passed=common_volume <= self.volume_tolerance_mm3 and measured + self.distance_tolerance_mm >= check.required_clearance_mm))
        return CadAssemblyAnalysisResult(analysis_id=plan.analysis_id, analysis_plan_hash=analysis_plan_hash(plan, assembly_hash_value), assembly_hash=assembly_hash_value, project_id=project_id, run_id=run_id, source_revision=source_revision, source_state_hash=source_state_hash, assembly_artifact_id=assembly_artifact_id, assembly_artifact_sha256=assembly_artifact_sha256, analyzer_version=self.version, freecad_version=freecad_version, interference=tuple(interference), clearance=tuple(clearance), passed=all(item.passed for item in (*interference, *clearance)))

    def result_from_measurements(self, plan, assembly_hash_value, measurements, **provenance):
        interference = []
        clearance = []
        values = {item["check_id"]: item for item in measurements["checks"]}
        for check in plan.canonical_checks:
            item = values[check.check_id]
            common_volume = float(item["interference_volume_mm3"])
            if isinstance(check, CadInterferenceCheck):
                interference.append(CadInterferenceResult(check_id=check.check_id, instance_a=check.instance_a, instance_b=check.instance_b, interference_volume_mm3=common_volume, allowed_interference_volume_mm3=check.max_allowed_interference_volume_mm3, passed=common_volume <= check.max_allowed_interference_volume_mm3 + self.volume_tolerance_mm3))
            else:
                measured = 0.0 if common_volume > self.volume_tolerance_mm3 else float(item["distance_mm"])
                clearance.append(CadClearanceResult(check_id=check.check_id, instance_a=check.instance_a, instance_b=check.instance_b, measured_clearance_mm=measured, required_clearance_mm=check.required_clearance_mm, passed=common_volume <= self.volume_tolerance_mm3 and measured + self.distance_tolerance_mm >= check.required_clearance_mm))
        return CadAssemblyAnalysisResult(analysis_id=plan.analysis_id, analysis_plan_hash=analysis_plan_hash(plan, assembly_hash_value), assembly_hash=assembly_hash_value, analyzer_version=self.version, interference=tuple(interference), clearance=tuple(clearance), passed=all(item.passed for item in (*interference, *clearance)), **provenance)


def analysis_plan_hash(plan: CadAssemblyAnalysisPlan, assembly_hash_value: str) -> str:
    payload = {
        "analysis_id": plan.analysis_id,
        "assembly_hash": assembly_hash_value,
        "checks": [
            {**check.model_dump(mode="json"), "instance_a": canonical_instance_pair(check.instance_a, check.instance_b)[0], "instance_b": canonical_instance_pair(check.instance_a, check.instance_b)[1]}
            for check in plan.canonical_checks
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
