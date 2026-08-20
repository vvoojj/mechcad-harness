from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadRigidTransform, assembly_hash, instance_object_name
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.models.common import Model


class CadAssemblyPartManifest(Model):
    part_id: str = Field(min_length=1)
    part_program_hash: str = Field(min_length=1)
    source_fcstd_artifact_id: str = Field(min_length=1)
    source_fcstd_sha256: str = Field(min_length=1)


class CadAssemblyInstanceManifest(Model):
    instance_id: str = Field(min_length=1)
    part_id: str = Field(min_length=1)
    internal_name: str = Field(min_length=1)
    placement: CadRigidTransform


class CadAssemblyManifest(Model):
    assembly_id: str = Field(min_length=1)
    assembly_hash: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    parts: tuple[CadAssemblyPartManifest, ...] = Field(min_length=1)
    instances: tuple[CadAssemblyInstanceManifest, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique(self) -> "CadAssemblyManifest":
        if len({part.part_id for part in self.parts}) != len(self.parts):
            raise ValueError("assembly manifest part IDs must be unique")
        if len({instance.instance_id for instance in self.instances}) != len(self.instances):
            raise ValueError("assembly manifest instance IDs must be unique")
        return self


def build_assembly_manifest(program: CadAssemblyProgram, part_artifacts, revision: int, state_hash: str) -> CadAssemblyManifest:
    parts = tuple(CadAssemblyPartManifest(part_id=part.part_id, part_program_hash=cad_program_hash(part), source_fcstd_artifact_id=part_artifacts[part.part_id].artifact_id, source_fcstd_sha256=part_artifacts[part.part_id].sha256) for part in program.canonical_parts)
    instances = tuple(CadAssemblyInstanceManifest(instance_id=instance.instance_id, part_id=instance.part_id, internal_name=instance_object_name(instance.instance_id), placement=instance.placement) for instance in program.canonical_instances)
    return CadAssemblyManifest(assembly_id=program.assembly_id, assembly_hash=assembly_hash(program), bound_revision=revision, bound_state_hash=state_hash, parts=parts, instances=instances)
