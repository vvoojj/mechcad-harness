from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from mechcad_harness.cad_program import CadPartProgram, cad_program_hash
from mechcad_harness.models.common import Model
from mechcad_harness.backends.freecad import freecad_object_name


class CadOperationManifestEntry(Model):
    operation_id: str = Field(min_length=1)
    operation_kind: Literal["base_plate", "through_hole", "rectangular_pocket"]
    internal_name: str = Field(min_length=1)


CadOperationManifest = CadOperationManifestEntry


class CadProgramManifest(Model):
    part_id: str = Field(min_length=1)
    program_hash: str = Field(min_length=1)
    operations: tuple[CadOperationManifestEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_entries(self) -> "CadProgramManifest":
        ids = [entry.operation_id for entry in self.operations]
        names = [entry.internal_name for entry in self.operations]
        if len(set(ids)) != len(ids) or len(set(names)) != len(names):
            raise ValueError("manifest operation identities must be unique")
        return self


def build_program_manifest(program: CadPartProgram) -> CadProgramManifest:
    return CadProgramManifest(part_id=program.part_id, program_hash=cad_program_hash(program), operations=tuple(CadOperationManifestEntry(operation_id=operation.operation_id, operation_kind=operation.operation_type, internal_name=freecad_object_name(operation.operation_id)) for operation in program.operations))
