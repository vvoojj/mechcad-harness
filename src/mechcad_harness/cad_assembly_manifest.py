from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadRigidTransform, assembly_hash, instance_object_name
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.imported_component import imported_component_hash
from mechcad_harness.models.common import Model


class CadAssemblyPartManifest(Model):
    part_id: str = Field(min_length=1)
    part_program_hash: str = Field(min_length=1)
    source_fcstd_artifact_id: str = Field(min_length=1)
    source_fcstd_sha256: str = Field(min_length=1)


class CadAssemblyImportedComponentManifest(Model):
    component_id: str = Field(min_length=1)
    imported_component_hash: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    artifact_sha256: str = Field(min_length=1)
    format: Literal["step"] = "step"
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)


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
    parts: tuple[CadAssemblyPartManifest, ...] = ()
    imported_components: tuple[CadAssemblyImportedComponentManifest, ...] = ()
    instances: tuple[CadAssemblyInstanceManifest, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique(self) -> "CadAssemblyManifest":
        if len({part.part_id for part in self.parts}) != len(self.parts):
            raise ValueError("assembly manifest part IDs must be unique")
        imported_ids = [component.component_id for component in self.imported_components]
        if len(set(imported_ids)) != len(imported_ids):
            raise ValueError("assembly manifest imported component IDs must be unique")
        component_ids = [part.part_id for part in self.parts] + imported_ids
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("assembly manifest component IDs must be unique")
        if len({instance.instance_id for instance in self.instances}) != len(self.instances):
            raise ValueError("assembly manifest instance IDs must be unique")
        if not component_ids:
            raise ValueError("assembly manifest requires at least one component")
        instance_component_ids = [instance.part_id for instance in self.instances]
        if set(instance_component_ids) != set(component_ids):
            raise ValueError("assembly manifest instances must resolve exactly to declared components")
        return self


def build_assembly_manifest(program: CadAssemblyProgram, component_artifacts, revision: int, state_hash: str) -> CadAssemblyManifest:
    parts = tuple(CadAssemblyPartManifest(part_id=part.part_id, part_program_hash=cad_program_hash(part), source_fcstd_artifact_id=component_artifacts[part.part_id].artifact_id, source_fcstd_sha256=component_artifacts[part.part_id].sha256) for part in program.canonical_parts)
    imported_components = []
    for component in program.canonical_imported_components:
        artifact = component_artifacts[component.component_id]
        if artifact.artifact_id != component.artifact_id or artifact.sha256 != component.artifact_hash:
            raise ValueError(f"imported artifact binding mismatch: {component.component_id}")
        if artifact.artifact_type.value != component.format:
            raise ValueError(f"imported artifact format mismatch: {component.component_id}")
        if artifact.bound_revision != component.source_revision or artifact.bound_state_hash != component.source_state_hash:
            raise ValueError(f"imported artifact source binding mismatch: {component.component_id}")
        imported_components.append(CadAssemblyImportedComponentManifest(
            component_id=component.component_id,
            imported_component_hash=imported_component_hash(component),
            artifact_id=artifact.artifact_id,
            artifact_sha256=artifact.sha256,
            format=component.format,
            source_revision=component.source_revision,
            source_state_hash=component.source_state_hash,
        ))
    instances = tuple(CadAssemblyInstanceManifest(instance_id=instance.instance_id, part_id=instance.part_id, internal_name=instance_object_name(instance.instance_id), placement=instance.placement) for instance in program.canonical_instances)
    return CadAssemblyManifest(assembly_id=program.assembly_id, assembly_hash=assembly_hash(program), bound_revision=revision, bound_state_hash=state_hash, parts=parts, imported_components=tuple(imported_components), instances=instances)
