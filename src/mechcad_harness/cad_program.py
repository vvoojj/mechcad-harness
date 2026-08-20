from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from mechcad_harness.models.common import Model


SAFE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


class CadProgramError(ValueError):
    pass


class CadOperation(Model):
    operation_id: str = Field(min_length=1)

    @field_validator("operation_id")
    @classmethod
    def safe_operation_id(cls, value: str) -> str:
        if not SAFE_ID.fullmatch(value):
            raise ValueError("operation_id must be a safe repository identifier")
        return value


class BasePlateOperation(CadOperation):
    operation_type: Literal["base_plate"] = "base_plate"
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    thickness_mm: float = Field(gt=0)

    @model_validator(mode="after")
    def finite(self) -> "BasePlateOperation":
        if any(not math.isfinite(value) for value in (self.length_mm, self.width_mm, self.thickness_mm)):
            raise ValueError("base dimensions must be finite")
        return self


class ThroughHoleOperation(CadOperation):
    operation_type: Literal["through_hole"] = "through_hole"
    x_mm: float
    y_mm: float
    diameter_mm: float = Field(gt=0)

    @model_validator(mode="after")
    def finite(self) -> "ThroughHoleOperation":
        if any(not math.isfinite(value) for value in (self.x_mm, self.y_mm, self.diameter_mm)):
            raise ValueError("hole values must be finite")
        return self


class RectangularPocketOperation(CadOperation):
    operation_type: Literal["rectangular_pocket"] = "rectangular_pocket"
    x_mm: float
    y_mm: float
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    depth_mm: float = Field(gt=0)

    @model_validator(mode="after")
    def finite(self) -> "RectangularPocketOperation":
        if any(not math.isfinite(value) for value in (self.x_mm, self.y_mm, self.length_mm, self.width_mm, self.depth_mm)):
            raise ValueError("pocket values must be finite")
        return self


class ThroughSlotOperation(CadOperation):
    operation_type: Literal["through_slot"] = "through_slot"
    center_x_mm: float
    center_y_mm: float
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    orientation: Literal["x", "y"]

    @model_validator(mode="after")
    def finite(self) -> "ThroughSlotOperation":
        if any(not math.isfinite(value) for value in (self.center_x_mm, self.center_y_mm, self.length_mm, self.width_mm)):
            raise ValueError("slot values must be finite")
        if self.length_mm < self.width_mm:
            raise ValueError("slot total length must be at least its width")
        return self


CadOperationValue = Annotated[BasePlateOperation | ThroughHoleOperation | RectangularPocketOperation | ThroughSlotOperation, Field(discriminator="operation_type")]


class CadPartProgram(Model):
    part_id: str = Field(min_length=1)
    operations: tuple[CadOperationValue, ...] = Field(min_length=1)
    coordinate_system: Literal["lower-left-bottom; +X length, +Y width, +Z thickness"] = "lower-left-bottom; +X length, +Y width, +Z thickness"

    @field_validator("part_id")
    @classmethod
    def safe_part_id(cls, value: str) -> str:
        if not SAFE_ID.fullmatch(value):
            raise ValueError("part_id must be a safe repository identifier")
        return value

    @model_validator(mode="after")
    def validate_operations(self) -> "CadPartProgram":
        ids = [operation.operation_id for operation in self.operations]
        if len(set(ids)) != len(ids):
            raise ValueError("operation IDs must be unique")
        bases = [index for index, operation in enumerate(self.operations) if isinstance(operation, BasePlateOperation)]
        if bases != [0]:
            raise ValueError("program must contain exactly one base operation first")
        base = self.operations[0]
        assert isinstance(base, BasePlateOperation)
        for operation in self.operations[1:]:
            if isinstance(operation, ThroughHoleOperation):
                radius = operation.diameter_mm / 2
                if not radius <= operation.x_mm <= base.length_mm - radius or not radius <= operation.y_mm <= base.width_mm - radius:
                    raise ValueError("through hole must lie inside base plate")
            elif isinstance(operation, RectangularPocketOperation):
                if operation.x_mm < 0 or operation.y_mm < 0 or operation.x_mm + operation.length_mm > base.length_mm or operation.y_mm + operation.width_mm > base.width_mm:
                    raise ValueError("pocket footprint must lie inside base plate")
                if operation.depth_mm >= base.thickness_mm:
                    raise ValueError("pocket depth must be less than base thickness")
            elif isinstance(operation, ThroughSlotOperation):
                half_major = operation.length_mm / 2
                half_minor = operation.width_mm / 2
                half_x = half_major if operation.orientation == "x" else half_minor
                half_y = half_minor if operation.orientation == "x" else half_major
                if operation.center_x_mm - half_x < 0 or operation.center_x_mm + half_x > base.length_mm or operation.center_y_mm - half_y < 0 or operation.center_y_mm + half_y > base.width_mm:
                    raise ValueError("through slot must lie inside base plate")
            else:
                raise ValueError("unsupported CAD operation")
        return self


def acceptance_program() -> CadPartProgram:
    return CadPartProgram(part_id="M7A2ABracket", operations=(
        BasePlateOperation(operation_id="base", length_mm=80, width_mm=60, thickness_mm=8),
        ThroughHoleOperation(operation_id="hole1", x_mm=10, y_mm=10, diameter_mm=6),
        ThroughHoleOperation(operation_id="hole2", x_mm=70, y_mm=50, diameter_mm=6),
        RectangularPocketOperation(operation_id="pocket", x_mm=25, y_mm=20, length_mm=30, width_mm=20, depth_mm=3),
    ))


def cad_program_hash(program: CadPartProgram) -> str:
    payload = json.dumps(program.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
