from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from mechcad_harness.cad_program import (
    BasePlateOperation,
    CadPartProgram,
    CadProgramError,
    RectangularPocketOperation,
    ThroughHoleOperation,
    ThroughSlotOperation,
    cad_program_hash,
)
from mechcad_harness.models.common import Model


COMPILER_VERSION = "generic-mounting-plate-compiler@1.0"


class CadCompilationError(CadProgramError):
    pass


class DesignSpecSourceBindingError(CadCompilationError):
    pass


class DesignSpecStaleSourceError(DesignSpecSourceBindingError):
    pass


class DesignSpecHashMismatchError(DesignSpecSourceBindingError):
    pass


class UnresolvedDesignInputError(CadCompilationError):
    pass


class MountingPlateDesignSpec(Model):
    class HoleSpec(Model):
        hole_id: str = Field(min_length=1)
        x_mm: float
        y_mm: float
        diameter_mm: float = Field(gt=0)

        @model_validator(mode="after")
        def validate_finite(self) -> "MountingPlateDesignSpec.HoleSpec":
            values = (self.x_mm, self.y_mm, self.diameter_mm)
            if any(not math.isfinite(v) for v in values):
                raise ValueError("hole coordinates and diameter must be finite")
            return self

    class PocketSpec(Model):
        pocket_id: str = Field(min_length=1)
        x_mm: float
        y_mm: float
        length_mm: float = Field(gt=0)
        width_mm: float = Field(gt=0)
        depth_mm: float = Field(gt=0)

        @model_validator(mode="after")
        def validate_finite(self) -> "MountingPlateDesignSpec.PocketSpec":
            values = (self.x_mm, self.y_mm, self.length_mm, self.width_mm, self.depth_mm)
            if any(not math.isfinite(v) for v in values):
                raise ValueError("pocket values must be finite")
            return self

    class SlotSpec(Model):
        slot_id: str = Field(min_length=1)
        center_x_mm: float
        center_y_mm: float
        length_mm: float = Field(gt=0)
        width_mm: float = Field(gt=0)
        orientation: Literal["x", "y"]

        @model_validator(mode="after")
        def validate_finite(self) -> "MountingPlateDesignSpec.SlotSpec":
            values = (self.center_x_mm, self.center_y_mm, self.length_mm, self.width_mm)
            if any(not math.isfinite(v) for v in values):
                raise ValueError("slot values must be finite")
            if self.length_mm < self.width_mm:
                raise ValueError("slot total length must be at least its width")
            return self

    part_id: str = Field(min_length=1)
    plate_length_mm: float = Field(gt=0)
    plate_width_mm: float = Field(gt=0)
    plate_thickness_mm: float = Field(gt=0)
    mounting_holes: tuple[MountingPlateDesignSpec.HoleSpec, ...] = Field(default_factory=tuple)
    pockets: tuple[MountingPlateDesignSpec.PocketSpec, ...] = Field(default_factory=tuple)
    slots: tuple[MountingPlateDesignSpec.SlotSpec, ...] = Field(default_factory=tuple)

    @field_validator("part_id")
    @classmethod
    def validate_part_id(cls, value: str) -> str:
        if not re.fullmatch(r"^[A-Za-z][A-Za-z0-9_.-]*$", value):
            raise ValueError("part_id must be a safe repository identifier")
        return value

    @model_validator(mode="after")
    def validate_plate_finite(self) -> "MountingPlateDesignSpec":
        if any(not math.isfinite(v) for v in (self.plate_length_mm, self.plate_width_mm, self.plate_thickness_mm)):
            raise ValueError("plate dimensions must be finite")
        return self

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "MountingPlateDesignSpec":
        all_ids = (
            [h.hole_id for h in self.mounting_holes]
            + [p.pocket_id for p in self.pockets]
            + [s.slot_id for s in self.slots]
        )
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("feature IDs must be unique across holes, pockets, and slots")
        return self

    @model_validator(mode="after")
    def validate_holes_inside_plate(self) -> "MountingPlateDesignSpec":
        for hole in self.mounting_holes:
            radius = hole.diameter_mm / 2
            if not (radius <= hole.x_mm <= self.plate_length_mm - radius):
                raise ValueError(f"hole '{hole.hole_id}' x-position places it outside plate")
            if not (radius <= hole.y_mm <= self.plate_width_mm - radius):
                raise ValueError(f"hole '{hole.hole_id}' y-position places it outside plate")
        return self

    @model_validator(mode="after")
    def validate_no_overlapping_holes(self) -> "MountingPlateDesignSpec":
        holes = self.mounting_holes
        for i, first in enumerate(holes):
            for second in holes[i + 1:]:
                dist = math.hypot(first.x_mm - second.x_mm, first.y_mm - second.y_mm)
                min_dist = (first.diameter_mm + second.diameter_mm) / 2
                if dist < min_dist:
                    raise ValueError(f"holes '{first.hole_id}' and '{second.hole_id}' overlap")
        return self

    @model_validator(mode="after")
    def validate_pockets_inside_plate(self) -> "MountingPlateDesignSpec":
        for pocket in self.pockets:
            if pocket.x_mm < 0 or pocket.y_mm < 0:
                raise ValueError(f"pocket '{pocket.pocket_id}' has negative position")
            if pocket.x_mm + pocket.length_mm > self.plate_length_mm:
                raise ValueError(f"pocket '{pocket.pocket_id}' extends beyond plate length")
            if pocket.y_mm + pocket.width_mm > self.plate_width_mm:
                raise ValueError(f"pocket '{pocket.pocket_id}' extends beyond plate width")
            if pocket.depth_mm >= self.plate_thickness_mm:
                raise ValueError(
                    f"pocket '{pocket.pocket_id}' depth must be less than plate thickness"
                )
        return self

    @model_validator(mode="after")
    def validate_slots_inside_plate(self) -> "MountingPlateDesignSpec":
        for slot in self.slots:
            half_major = slot.length_mm / 2
            half_minor = slot.width_mm / 2
            half_x = half_major if slot.orientation == "x" else half_minor
            half_y = half_minor if slot.orientation == "x" else half_major
            if slot.center_x_mm - half_x < 0 or slot.center_x_mm + half_x > self.plate_length_mm:
                raise ValueError(f"slot '{slot.slot_id}' extends beyond plate length")
            if slot.center_y_mm - half_y < 0 or slot.center_y_mm + half_y > self.plate_width_mm:
                raise ValueError(f"slot '{slot.slot_id}' extends beyond plate width")
        return self


def mounting_plate_spec_hash(spec: MountingPlateDesignSpec) -> str:
    payload = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def compile_mounting_plate(spec: MountingPlateDesignSpec) -> CadPartProgram:
    operations: list = []

    operations.append(
        BasePlateOperation(
            operation_id="base",
            length_mm=spec.plate_length_mm,
            width_mm=spec.plate_width_mm,
            thickness_mm=spec.plate_thickness_mm,
        )
    )

    for hole in sorted(spec.mounting_holes, key=lambda h: h.hole_id):
        operations.append(
            ThroughHoleOperation(
                operation_id=hole.hole_id,
                x_mm=hole.x_mm,
                y_mm=hole.y_mm,
                diameter_mm=hole.diameter_mm,
            )
        )

    for pocket in sorted(spec.pockets, key=lambda p: p.pocket_id):
        operations.append(
            RectangularPocketOperation(
                operation_id=pocket.pocket_id,
                x_mm=pocket.x_mm,
                y_mm=pocket.y_mm,
                length_mm=pocket.length_mm,
                width_mm=pocket.width_mm,
                depth_mm=pocket.depth_mm,
            )
        )

    for slot in sorted(spec.slots, key=lambda s: s.slot_id):
        operations.append(
            ThroughSlotOperation(
                operation_id=slot.slot_id,
                center_x_mm=slot.center_x_mm,
                center_y_mm=slot.center_y_mm,
                length_mm=slot.length_mm,
                width_mm=slot.width_mm,
                orientation=slot.orientation,
            )
        )

    return CadPartProgram(part_id=spec.part_id, operations=tuple(operations))


class CadCompilationResult(Model):
    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    spec_hash: str = Field(min_length=1)
    compiler_version: str = Field(min_length=1)
    program: CadPartProgram
    program_hash: str = Field(min_length=1)


class CadCompilationService:
    def __init__(self, state_manager):
        self._state_manager = state_manager

    def compile_mounting_plate(
        self,
        *,
        project_id: str,
        source_revision: int,
        source_state_hash: str,
        spec: MountingPlateDesignSpec,
    ) -> CadCompilationResult:
        self._validate_source_binding(project_id, source_revision, source_state_hash)
        program = compile_mounting_plate(spec)
        program_hash = cad_program_hash(program)
        return CadCompilationResult(
            project_id=project_id,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            spec_hash=mounting_plate_spec_hash(spec),
            compiler_version=COMPILER_VERSION,
            program=program,
            program_hash=program_hash,
        )

    def _validate_source_binding(
        self, project_id: str, revision: int, state_hash: str
    ) -> None:
        from mechcad_harness.state import state_hash as canonical_state_hash
        from mechcad_harness.state.errors import RevisionNotFoundError

        try:
            self._state_manager._read_current(project_id)
        except RevisionNotFoundError:
            raise DesignSpecSourceBindingError(
                f"source project not found: {project_id}"
            )

        try:
            state = self._state_manager.load_revision(project_id, revision)
        except RevisionNotFoundError as exc:
            raise DesignSpecStaleSourceError(
                f"source revision not found: {project_id}:{revision}"
            ) from exc
        actual_hash = canonical_state_hash(state)
        if actual_hash != state_hash:
            raise DesignSpecHashMismatchError(
                f"source state hash mismatch: {project_id}:{revision}"
            )
