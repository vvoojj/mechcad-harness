from __future__ import annotations

import json
from hashlib import sha256
from math import isfinite
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .models.common import Model
from .models.structural import (
    StructuralAnalysisDefinition,
    StructuralResultField,
    structural_definition_hash,
)


class StructuralSourceBinding(Model):
    model_config = ConfigDict(frozen=True)

    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    definition_id: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    target_body_id: str = Field(min_length=1)
    source_program_hash: str = Field(min_length=1)
    geometry_identity: str = Field(min_length=1)
    geometry_artifact_id: str = Field(min_length=1)
    geometry_artifact_hash: str = Field(min_length=1)


class MeshRefinement(Model):
    model_config = ConfigDict(frozen=True)

    region_id: str = Field(min_length=1)
    target_size_mm: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_target_size(self):
        if not isfinite(self.target_size_mm):
            raise ValueError("refinement target size must be finite")
        return self


class MeshSpecification(Model):
    model_config = ConfigDict(frozen=True)

    element_family: Literal["c3d10"] = "c3d10"
    global_target_size_mm: float = Field(gt=0)
    refinements: tuple[MeshRefinement, ...] = ()
    quality_policy_id: str = Field(min_length=1)
    mesher_settings_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_and_canonicalize(self):
        if not isfinite(self.global_target_size_mm):
            raise ValueError("global target size must be finite")
        region_ids = [refinement.region_id for refinement in self.refinements]
        if len(set(region_ids)) != len(region_ids):
            raise ValueError("mesh refinement region IDs must be unique")
        object.__setattr__(
            self,
            "refinements",
            tuple(sorted(self.refinements, key=lambda item: item.region_id)),
        )
        return self


class StructuralExecutionSettings(Model):
    model_config = ConfigDict(frozen=True)

    max_elements: int = Field(gt=0)
    max_runtime_seconds: float = Field(gt=0)
    max_output_bytes: int = Field(gt=0)
    retain_raw_artifacts: bool

    @model_validator(mode="after")
    def validate_finite_runtime(self):
        if not isfinite(self.max_runtime_seconds):
            raise ValueError("max runtime seconds must be finite")
        return self


class StructuralAnalysisRequest(Model):
    model_config = ConfigDict(frozen=True)

    source_binding: StructuralSourceBinding
    selected_load_case_ids: tuple[str, ...] = Field(min_length=1)
    mesh_specification: MeshSpecification
    requested_result_fields: tuple[StructuralResultField, ...] = Field(min_length=1)
    execution_settings: StructuralExecutionSettings
    analytical_policy_hash: str | None = Field(default=None, min_length=1)
    request_hash: str = "pending"

    @model_validator(mode="after")
    def validate_request(self):
        if any(not case_id for case_id in self.selected_load_case_ids):
            raise ValueError("selected load-case IDs must be non-empty")
        if len(set(self.selected_load_case_ids)) != len(self.selected_load_case_ids):
            raise ValueError("selected load-case IDs must be unique")
        expected_request_hash = structural_request_hash(self)
        if self.request_hash == "pending":
            object.__setattr__(self, "request_hash", expected_request_hash)
        elif self.request_hash != expected_request_hash:
            raise ValueError("request hash does not match canonical request")
        return self

    def validate_against(self, definition: StructuralAnalysisDefinition) -> None:
        if definition.id != self.source_binding.definition_id:
            raise ValueError("request definition ID does not match canonical definition")
        if structural_definition_hash(definition) != self.source_binding.definition_hash:
            raise ValueError("request definition hash does not match canonical definition")
        if definition.target_body_id != self.source_binding.target_body_id:
            raise ValueError("request target body does not match canonical definition")
        defined_cases = {case.id: case for case in definition.load_cases}
        if any(
            case_id not in defined_cases or not defined_cases[case_id].active
            for case_id in self.selected_load_case_ids
        ):
            raise ValueError("request selects an unknown or inactive load case")
        defined_region_ids = {region.region_id for region in definition.regions}
        if any(
            refinement.region_id not in defined_region_ids
            for refinement in self.mesh_specification.refinements
        ):
            raise ValueError("request mesh refinement references an unknown structural region")


def structural_request_hash(request: StructuralAnalysisRequest) -> str:
    payload = {
        "source_binding": request.source_binding.model_dump(mode="json"),
        "selected_load_case_ids": list(request.selected_load_case_ids),
        "mesh_specification": request.mesh_specification.model_dump(mode="json"),
        "requested_result_fields": list(request.requested_result_fields),
        "execution_settings": request.execution_settings.model_dump(mode="json"),
        "analytical_policy_hash": request.analytical_policy_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(canonical).hexdigest()
