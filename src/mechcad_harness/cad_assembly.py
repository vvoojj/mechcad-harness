from __future__ import annotations

import binascii
import hashlib
import json
import math
from typing import Literal

from pydantic import Field, field_validator, model_validator

from mechcad_harness.cad_program import CadPartProgram, cad_program_hash
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
    parts: tuple[CadPartProgram, ...] = Field(min_length=1)
    instances: tuple[CadComponentInstance, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_registry(self) -> "CadAssemblyProgram":
        part_ids = [part.part_id for part in self.parts]
        instance_ids = [instance.instance_id for instance in self.instances]
        if len(set(part_ids)) != len(part_ids):
            raise ValueError("part IDs must be unique")
        if len(set(instance_ids)) != len(instance_ids):
            raise ValueError("instance IDs must be unique")
        registered = set(part_ids)
        if any(instance.part_id not in registered for instance in self.instances):
            raise ValueError("instance references an unknown part")
        if set(instance.part_id for instance in self.instances) != registered:
            raise ValueError("unused part definitions are not allowed")
        return self

    @property
    def canonical_parts(self) -> tuple[CadPartProgram, ...]:
        return tuple(sorted(self.parts, key=lambda part: part.part_id))

    @property
    def canonical_instances(self) -> tuple[CadComponentInstance, ...]:
        return tuple(sorted(self.instances, key=lambda instance: instance.instance_id))


def instance_object_name(instance_id: str) -> str:
    encoded = binascii.hexlify(instance_id.encode("utf-8")).decode("ascii")
    if len(encoded) > 240:
        raise ValueError("instance_id is too long for deterministic FreeCAD identity")
    return f"inst_{encoded}"


def assembly_hash(program: CadAssemblyProgram) -> str:
    payload = {
        "assembly_id": program.assembly_id,
        "parts": [{"part_id": part.part_id, "program_hash": cad_program_hash(part)} for part in program.canonical_parts],
        "instances": [instance.model_dump(mode="json") | {"part_id": instance.part_id} for instance in program.canonical_instances],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"
