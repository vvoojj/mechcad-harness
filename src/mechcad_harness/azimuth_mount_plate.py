from __future__ import annotations

import hashlib
import json
import math

from pydantic import Field, model_validator

from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram, ThroughHoleOperation
from mechcad_harness.models.common import Model


M7B1_TEST_FIXTURE_ONLY = "M7B1_TEST_FIXTURE_ONLY"


class XYPoint(Model):
    x_mm: float
    y_mm: float

    @model_validator(mode="after")
    def finite(self):
        if not all(math.isfinite(value) for value in (self.x_mm, self.y_mm)):
            raise ValueError("point coordinates must be finite")
        return self


class MountHoleSpec(Model):
    """Compatibility base for physical mount interface records."""


class ThreadedMountHole(MountHoleSpec):
    kind: str = "threaded_mount_interface"
    nominal_thread_diameter_mm: float = Field(gt=0)


class ThroughMountHole(MountHoleSpec):
    kind: str = "through_hole_interface"
    physical_hole_diameter_mm: float = Field(gt=0)


class RequiredMatingHole(MountHoleSpec):
    kind: str = "required_mating_hole"
    diameter_mm: float = Field(gt=0)


MountHoleInterface = ThreadedMountHole | ThroughMountHole


class MountPointSpec(Model):
    hole_id: str = Field(min_length=1)
    x_mm: float
    y_mm: float
    physical_interface: MountHoleInterface | None = None
    external_mating_requirement: RequiredMatingHole | None = None

    @model_validator(mode="after")
    def finite(self):
        if not all(math.isfinite(value) for value in (self.x_mm, self.y_mm)):
            raise ValueError("mount point values must be finite")
        return self


class AzimuthDriveMountInterface(Model):
    component_id: str = Field(min_length=1)
    coordinate_convention: str = "interface-center; mounting plane XY; +Z housing-to-mating-plate; +X source-defined reference; +Y right-handed"
    in_plane_alignment: str = "aligned-with-plate-axes"
    frame_reference_id: str = Field(min_length=1)
    mount_points: tuple[MountPointSpec, ...] = Field(min_length=1)
    central_keepout_diameter_mm: float | None = Field(default=None, gt=0)
    central_required_mating_opening_diameter_mm: float | None = Field(default=None, gt=0)
    manufacturer_required_central_radial_clearance_mm: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_holes(self):
        if len({point.hole_id for point in self.mount_points}) != len(self.mount_points):
            raise ValueError("mount point IDs must be unique")
        if self.central_keepout_diameter_mm is None and self.central_required_mating_opening_diameter_mm is None:
            raise ValueError("central keepout or mating opening requirement is required")
        if self.central_keepout_diameter_mm is not None and self.central_required_mating_opening_diameter_mm is None and self.manufacturer_required_central_radial_clearance_mm is None:
            raise ValueError("central radial clearance or mating opening requirement is required")
        return self

    @property
    def mounting_holes(self):
        return tuple(point.physical_interface or point.external_mating_requirement for point in self.mount_points)

    def external_minimum_central_opening_diameter_mm(self) -> float | None:
        if self.central_required_mating_opening_diameter_mm is not None:
            return self.central_required_mating_opening_diameter_mm
        if self.central_keepout_diameter_mm is not None and self.manufacturer_required_central_radial_clearance_mm is not None:
            return self.central_keepout_diameter_mm + 2 * self.manufacturer_required_central_radial_clearance_mm
        return None


AzimuthDriveMountInterfaceValue = AzimuthDriveMountInterface


class AzimuthMotorMountPlateSpec(Model):
    part_id: str = Field(min_length=1)
    plate_length_mm: float = Field(gt=0)
    plate_width_mm: float = Field(gt=0)
    plate_thickness_mm: float = Field(gt=0)
    motor_center_x_mm: float
    motor_center_y_mm: float
    drive_mount_interface: AzimuthDriveMountInterface | None = None
    motor_mount_hole_diameter_mm: float | None = Field(default=None, gt=0)
    motor_mount_hole_positions: tuple[XYPoint, ...] = ()
    central_clearance_hole_diameter_mm: float | None = Field(default=None, gt=0)
    frame_mount_hole_diameter_mm: float | None = Field(default=None, gt=0)
    frame_mount_hole_positions: tuple[XYPoint, ...] = ()
    material_id: str | None = None
    provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_geometry(self):
        if self.drive_mount_interface is not None:
            if self.motor_mount_hole_diameter_mm is not None or self.motor_mount_hole_positions or self.central_clearance_hole_diameter_mm is not None:
                raise ValueError("hardware interface must not be duplicated as plate-local motor geometry")
            motor_holes = tuple(XYPoint(x_mm=self.motor_center_x_mm + point.x_mm, y_mm=self.motor_center_y_mm + point.y_mm) for point in self.drive_mount_interface.mount_points)
            motor_diameters = tuple(_plate_hole_diameter(point) for point in self.drive_mount_interface.mount_points)
            central_diameter = _central_plate_diameter(self.drive_mount_interface)
        else:
            if self.motor_mount_hole_diameter_mm is None or not self.motor_mount_hole_positions or self.central_clearance_hole_diameter_mm is None:
                raise ValueError("motor geometry or drive interface is required")
            motor_holes = self.motor_mount_hole_positions
            motor_diameters = (self.motor_mount_hole_diameter_mm,) * len(motor_holes)
            central_diameter = self.central_clearance_hole_diameter_mm
        values = (self.plate_length_mm, self.plate_width_mm, self.plate_thickness_mm, self.motor_center_x_mm, self.motor_center_y_mm, central_diameter, *(point.x_mm for point in motor_holes), *(point.y_mm for point in motor_holes), *(point.x_mm for point in self.frame_mount_hole_positions), *(point.y_mm for point in self.frame_mount_hole_positions))
        if any(not math.isfinite(value) for value in values):
            raise ValueError("plate dimensions and coordinates must be finite")
        if self.frame_mount_hole_positions and self.frame_mount_hole_diameter_mm is None:
            raise ValueError("frame hole diameter is required when frame holes are present")
        holes = [(point, diameter, "motor") for point, diameter in zip(motor_holes, motor_diameters)]
        holes += [(point, self.frame_mount_hole_diameter_mm, "frame") for point in self.frame_mount_hole_positions]
        holes.append((XYPoint(x_mm=self.motor_center_x_mm, y_mm=self.motor_center_y_mm), central_diameter, "central"))
        for point, diameter, _ in holes:
            radius = diameter / 2
            if not radius <= point.x_mm <= self.plate_length_mm - radius or not radius <= point.y_mm <= self.plate_width_mm - radius:
                raise ValueError("hole must be fully contained by plate envelope")
        seen = set()
        for point, _, purpose in holes:
            key = (point.x_mm, point.y_mm)
            if key in seen:
                raise ValueError("duplicate hole center")
            seen.add(key)
        for index, (first, first_diameter, first_kind) in enumerate(holes):
            for second, second_diameter, second_kind in holes[index + 1:]:
                if first_kind == second_kind == "central":
                    continue
                if math.hypot(first.x_mm - second.x_mm, first.y_mm - second.y_mm) < (first_diameter + second_diameter) / 2:
                    raise ValueError("duplicate or overlapping incompatible holes")
        return self


def hole_edge_margin_mm(point: XYPoint, diameter_mm: float, plate_length_mm: float, plate_width_mm: float) -> float:
    radius = diameter_mm / 2
    return min(point.x_mm - radius, plate_length_mm - point.x_mm - radius, point.y_mm - radius, plate_width_mm - point.y_mm - radius)


def hole_ligament_mm(first: XYPoint, first_diameter_mm: float, second: XYPoint, second_diameter_mm: float) -> float:
    return math.hypot(first.x_mm - second.x_mm, first.y_mm - second.y_mm) - first_diameter_mm / 2 - second_diameter_mm / 2


def mount_plate_spec_hash(spec: AzimuthMotorMountPlateSpec) -> str:
    encoded = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def compile_azimuth_motor_mount_plate(spec: AzimuthMotorMountPlateSpec) -> CadPartProgram:
    if spec.drive_mount_interface is not None:
        motor_holes = tuple((XYPoint(x_mm=spec.motor_center_x_mm + point.x_mm, y_mm=spec.motor_center_y_mm + point.y_mm), _plate_hole_diameter(point)) for point in spec.drive_mount_interface.mount_points)
        central_diameter = _central_plate_diameter(spec.drive_mount_interface)
    else:
        motor_holes = tuple((point, spec.motor_mount_hole_diameter_mm) for point in spec.motor_mount_hole_positions)
        central_diameter = spec.central_clearance_hole_diameter_mm
    operations = [BasePlateOperation(operation_id="base", length_mm=spec.plate_length_mm, width_mm=spec.plate_width_mm, thickness_mm=spec.plate_thickness_mm), ThroughHoleOperation(operation_id="central_clearance", x_mm=spec.motor_center_x_mm, y_mm=spec.motor_center_y_mm, diameter_mm=central_diameter)]
    operations += [ThroughHoleOperation(operation_id=f"motor_mount_{index}", x_mm=point.x_mm, y_mm=point.y_mm, diameter_mm=diameter) for index, (point, diameter) in enumerate(motor_holes, start=1)]
    if spec.frame_mount_hole_diameter_mm is not None:
        operations += [ThroughHoleOperation(operation_id=f"frame_mount_{index}", x_mm=point.x_mm, y_mm=point.y_mm, diameter_mm=spec.frame_mount_hole_diameter_mm) for index, point in enumerate(spec.frame_mount_hole_positions, start=1)]
    return CadPartProgram(part_id=spec.part_id, operations=tuple(operations))


def azimuth_mount_plate_design_readiness(interface: AzimuthDriveMountInterface, *, design_clearance_diameter_mm: float | None = None) -> bool:
    """Check plate-specific readiness without weakening hardware authority."""
    if design_clearance_diameter_mm is None:
        return False
    return all(point.external_mating_requirement is not None for point in interface.mount_points)


def _plate_hole_diameter(point: MountPointSpec) -> float:
    if point.external_mating_requirement is not None:
        return point.external_mating_requirement.diameter_mm
    raise ValueError("explicit mating-hole requirement is required to derive plate hole")


def _central_plate_diameter(interface: AzimuthDriveMountInterface) -> float:
    if interface.central_required_mating_opening_diameter_mm is not None:
        return interface.central_required_mating_opening_diameter_mm
    if (diameter := interface.external_minimum_central_opening_diameter_mm()) is not None:
        return diameter
    raise ValueError("explicit central mating opening or radial clearance is required")


def mount_plate_measurements(spec: AzimuthMotorMountPlateSpec) -> dict:
    holes = [(f"motor_mount_{index}", point, spec.motor_mount_hole_diameter_mm) for index, point in enumerate(spec.motor_mount_hole_positions, start=1)]
    holes += [(f"frame_mount_{index}", point, spec.frame_mount_hole_diameter_mm) for index, point in enumerate(spec.frame_mount_hole_positions, start=1)]
    holes.append(("central_clearance", XYPoint(x_mm=spec.motor_center_x_mm, y_mm=spec.motor_center_y_mm), spec.central_clearance_hole_diameter_mm))
    ligaments = []
    for index, (name, point, diameter) in enumerate(holes):
        for other_name, other, other_diameter in holes[index + 1:]:
            ligaments.append({"first": name, "second": other_name, "ligament_mm": hole_ligament_mm(point, diameter, other, other_diameter)})
    return {"edge_margins_mm": {name: hole_edge_margin_mm(point, diameter, spec.plate_length_mm, spec.plate_width_mm) for name, point, diameter in holes}, "hole_ligaments_mm": ligaments}


def missing_authoritative_inputs(state) -> tuple[dict, ...]:
    available = {parameter.key.value for parameter in state.authoritative_parameters}
    required = ("plate_length_mm", "plate_width_mm", "plate_thickness_mm", "motor_center_x_mm", "motor_center_y_mm", "motor_mount_hole_diameter_mm", "motor_mount_hole_positions", "central_clearance_hole_diameter_mm", "frame_mount_hole_diameter_mm", "frame_mount_hole_positions")
    return tuple({"field": field, "authoritative_value_found": field in available, "source": next((parameter.source_resolution_id for parameter in state.authoritative_parameters if parameter.key.value == field), None), "blocking": True} for field in required if field not in available)
