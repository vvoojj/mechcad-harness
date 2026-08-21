from __future__ import annotations

import binascii
import hashlib
import json
import math
from typing import Literal

from pydantic import Field, field_validator, model_validator

from mechcad_harness.cad_program import CadPartProgram, cad_program_hash
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.models.common import Model


class CadRigidTransform(Model):
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    rotation_quaternion: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, data):
        data = dict(data)
        quaternion = tuple(float(value) for value in data.get("rotation_quaternion", (1.0, 0.0, 0.0, 0.0)))
        values = (float(data.get("x_mm", 0.0)), float(data.get("y_mm", 0.0)), float(data.get("z_mm", 0.0)), *quaternion)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("rigid transform values must be finite")
        norm = math.sqrt(sum(value * value for value in quaternion))
        if norm <= 1e-12:
            raise ValueError("rotation quaternion must have non-zero norm")
        quaternion = tuple(value / norm for value in quaternion)
        first_nonzero = next((value for value in quaternion if abs(value) > 1e-12), 1.0)
        if first_nonzero < 0:
            quaternion = tuple(-value for value in quaternion)
        data["rotation_quaternion"] = quaternion
        return data


class CadComponentInstance(Model):
    instance_id: str = Field(min_length=1)
    part_id: str = Field(min_length=1)
    placement: CadRigidTransform = Field(default_factory=CadRigidTransform)


class CadAssemblyProgram(Model):
    assembly_id: str = Field(min_length=1)
    parts: tuple[CadPartProgram, ...] = Field(default_factory=tuple)
    imported_components: tuple[ImportedCadComponent, ...] = Field(default_factory=tuple)
    instances: tuple[CadComponentInstance, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_registry(self) -> "CadAssemblyProgram":
        if not self.parts and not self.imported_components:
            raise ValueError("at least one part or imported component is required")

        part_ids = [part.part_id for part in self.parts]
        imported_ids = [comp.component_id for comp in self.imported_components]
        all_component_ids = part_ids + imported_ids

        if len(set(part_ids)) != len(part_ids):
            raise ValueError("part IDs must be unique")
        if len(set(imported_ids)) != len(imported_ids):
            raise ValueError("imported component IDs must be unique")
        if len(set(all_component_ids)) != len(all_component_ids):
            raise ValueError("part and imported component IDs must be unique across each other")

        instance_ids = [instance.instance_id for instance in self.instances]
        if len(set(instance_ids)) != len(instance_ids):
            raise ValueError("instance IDs must be unique")

        registered = set(all_component_ids)
        if any(instance.part_id not in registered for instance in self.instances):
            raise ValueError("instance references an unknown component")
        if set(instance.part_id for instance in self.instances) != registered:
            raise ValueError("unused component definitions are not allowed")
        return self

    @property
    def canonical_parts(self) -> tuple[CadPartProgram, ...]:
        return tuple(sorted(self.parts, key=lambda part: part.part_id))

    @property
    def canonical_imported_components(self) -> tuple[ImportedCadComponent, ...]:
        return tuple(sorted(self.imported_components, key=lambda comp: comp.component_id))

    @property
    def canonical_instances(self) -> tuple[CadComponentInstance, ...]:
        return tuple(sorted(self.instances, key=lambda instance: instance.instance_id))

    @property
    def all_component_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                [part.part_id for part in self.parts] +
                [comp.component_id for comp in self.imported_components]
            )
        )

    @property
    def has_imported_components(self) -> bool:
        return len(self.imported_components) > 0


def instance_object_name(instance_id: str) -> str:
    encoded = binascii.hexlify(instance_id.encode("utf-8")).decode("ascii")
    if len(encoded) > 240:
        raise ValueError("instance_id is too long for deterministic FreeCAD identity")
    return f"inst_{encoded}"


def assembly_hash(program: CadAssemblyProgram) -> str:
    payload = {
        "assembly_id": program.assembly_id,
        "parts": [{"part_id": part.part_id, "program_hash": cad_program_hash(part)} for part in program.canonical_parts],
        "imported_components": [
            {
                "component_id": comp.component_id,
                "artifact_id": comp.artifact_id,
                "artifact_hash": comp.artifact_hash,
                "format": comp.format,
                "source_revision": comp.source_revision,
                "source_state_hash": comp.source_state_hash,
                "component_hash": imported_component_hash(comp),
            }
            for comp in program.canonical_imported_components
        ],
        "instances": [instance.model_dump(mode="json") | {"part_id": instance.part_id} for instance in program.canonical_instances],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"
