from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram, ThroughHoleOperation
from mechcad_harness.models.common import Model


M7B1_TEST_FIXTURE_ONLY = "M7B1_TEST_FIXTURE_ONLY"
M7B1B_TEST_FIXTURE_ONLY = "M7B1B_TEST_FIXTURE_ONLY"
AZIMUTH_MOUNT_PLATE_SYNTHESIS_VERSION = "azimuth-mount-plate-synthesis@1.0"


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


class PlateThicknessPolicy(Model):
    allowed_thicknesses_mm: tuple[float, ...] = Field(min_length=1)
    minimum_thickness_mm: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_policy(self):
        if any(not math.isfinite(value) or value <= 0 for value in self.allowed_thicknesses_mm):
            raise ValueError("thickness values must be finite and positive")
        if len(set(self.allowed_thicknesses_mm)) != len(self.allowed_thicknesses_mm):
            raise ValueError("thickness values must be unique")
        if not any(value >= self.minimum_thickness_mm for value in self.allowed_thicknesses_mm):
            raise ValueError("thickness policy has no satisfying stock thickness")
        return self

    @property
    def canonical_allowed_thicknesses_mm(self):
        return tuple(sorted(self.allowed_thicknesses_mm))

    def select(self) -> float:
        return next(value for value in self.canonical_allowed_thicknesses_mm if value >= self.minimum_thickness_mm)


class AzimuthMotorMountPlateDesignRequirements(Model):
    minimum_edge_margin_mm: float = Field(ge=0)
    minimum_hole_ligament_mm: float = Field(ge=0)
    plate_thickness_policy: PlateThicknessPolicy
    mounting_hole_radial_clearance_mm: float | None = Field(default=None, ge=0)
    central_radial_clearance_mm: float | None = Field(default=None, ge=0)
    provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def finite_requirements(self):
        values = (self.minimum_edge_margin_mm, self.minimum_hole_ligament_mm, self.mounting_hole_radial_clearance_mm, self.central_radial_clearance_mm)
        if any(value is not None and not math.isfinite(value) for value in values):
            raise ValueError("design requirements must be finite")
        return self


class SynthesisStatus(StrEnum):
    NOT_READY = "not_ready"
    INFEASIBLE = "infeasible"
    SUCCESS = "success"


class SynthesisInfeasibility(Model):
    code: Literal["minimum_ligament", "central_ligament", "missing_requirement"]
    message: str = Field(min_length=1)
    feature_pair: tuple[str, str] | None = None


class AzimuthMountPlateSynthesisResult(Model):
    status: SynthesisStatus
    hardware_interface_hash: str
    design_requirements_hash: str
    synthesis_version: str = AZIMUTH_MOUNT_PLATE_SYNTHESIS_VERSION
    design_variables: dict[str, float] = {}
    derived_features: dict[str, float] = {}
    edge_margins_mm: dict[str, float] = {}
    minimum_ligament_mm: float | None = None
    minimum_ligament_pair: tuple[str, str] | None = None
    spec: "AzimuthMotorMountPlateSpec | None" = None
    domain_spec_hash: str | None = None
    synthesis_hash: str
    infeasibility: SynthesisInfeasibility | None = None
    proposal: object | None = None


def design_requirements_hash(requirements: AzimuthMotorMountPlateDesignRequirements) -> str:
    return _hash_payload(requirements.model_dump(mode="json"))


def interface_hash(interface: AzimuthDriveMountInterface) -> str:
    payload = interface.model_dump(mode="json")
    payload["mount_points"] = sorted(payload["mount_points"], key=lambda point: point["hole_id"])
    return _hash_payload(payload)


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


def synthesize_azimuth_motor_mount_plate(interface: AzimuthDriveMountInterface, requirements: AzimuthMotorMountPlateDesignRequirements, *, part_id="azimuth_motor_mount_plate") -> AzimuthMountPlateSynthesisResult:
    interface = interface.model_copy(update={"mount_points": tuple(sorted(interface.mount_points, key=lambda point: point.hole_id))})
    hardware_hash = interface_hash(interface)
    requirements_hash = design_requirements_hash(requirements)
    missing = []
    if requirements.mounting_hole_radial_clearance_mm is None and any(point.external_mating_requirement is None for point in interface.mount_points):
        missing.append("mounting_hole_radial_clearance_mm")
    central_external = interface.external_minimum_central_opening_diameter_mm()
    if central_external is None and requirements.central_radial_clearance_mm is None:
        missing.append("central_radial_clearance_mm")
    if missing:
        return _synthesis_result(SynthesisStatus.NOT_READY, hardware_hash, requirements_hash, infeasibility=SynthesisInfeasibility(code="missing_requirement", message="missing authoritative synthesis requirements: " + ", ".join(missing)))
    motor_features = []
    for point in interface.mount_points:
        diameter = point.external_mating_requirement.diameter_mm if point.external_mating_requirement else point.physical_interface.physical_hole_diameter_mm if isinstance(point.physical_interface, ThroughMountHole) else point.physical_interface.nominal_thread_diameter_mm + 2 * requirements.mounting_hole_radial_clearance_mm
        if point.external_mating_requirement is None and isinstance(point.physical_interface, ThreadedMountHole):
            diameter = point.physical_interface.nominal_thread_diameter_mm + 2 * requirements.mounting_hole_radial_clearance_mm
        motor_features.append((point.hole_id, point.x_mm, point.y_mm, diameter))
    central_diameter = max(central_external or 0, (interface.central_keepout_diameter_mm or 0) + 2 * (requirements.central_radial_clearance_mm or 0))
    features = [(name, x, y, diameter) for name, x, y, diameter in motor_features] + [("central_clearance", 0.0, 0.0, central_diameter)]
    for index, first in enumerate(features):
        for second in features[index + 1:]:
            ligament = hole_ligament_mm(XYPoint(x_mm=first[1], y_mm=first[2]), first[3], XYPoint(x_mm=second[1], y_mm=second[2]), second[3])
            if ligament < requirements.minimum_hole_ligament_mm:
                return _synthesis_result(SynthesisStatus.INFEASIBLE, hardware_hash, requirements_hash, infeasibility=SynthesisInfeasibility(code="central_ligament" if "central_clearance" in (first[0], second[0]) else "minimum_ligament", message="minimum hole ligament is infeasible", feature_pair=(first[0], second[0])))
    min_x = min(x - diameter / 2 for _, x, _, diameter in features) - requirements.minimum_edge_margin_mm
    max_x = max(x + diameter / 2 for _, x, _, diameter in features) + requirements.minimum_edge_margin_mm
    min_y = min(y - diameter / 2 for _, _, y, diameter in features) - requirements.minimum_edge_margin_mm
    max_y = max(y + diameter / 2 for _, _, y, diameter in features) + requirements.minimum_edge_margin_mm
    motor_center = XYPoint(x_mm=-min_x, y_mm=-min_y)
    spec = AzimuthMotorMountPlateSpec(part_id=part_id, plate_length_mm=max_x - min_x, plate_width_mm=max_y - min_y, plate_thickness_mm=requirements.plate_thickness_policy.select(), motor_center_x_mm=motor_center.x_mm, motor_center_y_mm=motor_center.y_mm, drive_mount_interface=interface, provenance=requirements.provenance)
    measurements = _synthesis_measurements(spec, interface, motor_features, central_diameter)
    result = _synthesis_result(SynthesisStatus.SUCCESS, hardware_hash, requirements_hash, design_variables={"plate_length_mm": spec.plate_length_mm, "plate_width_mm": spec.plate_width_mm, "plate_thickness_mm": spec.plate_thickness_mm, "motor_center_x_mm": spec.motor_center_x_mm, "motor_center_y_mm": spec.motor_center_y_mm}, derived_features={"central_opening_diameter_mm": central_diameter}, edge_margins_mm=measurements[0], minimum_ligament_mm=measurements[1][0], minimum_ligament_pair=measurements[1][1], spec=spec, domain_spec_hash=mount_plate_spec_hash(spec))
    return result.model_copy(update={"synthesis_hash": _synthesis_hash(result)})


def _synthesis_measurements(spec, interface, motor_features, central_diameter):
    holes = [(point.hole_id, XYPoint(x_mm=spec.motor_center_x_mm + point.x_mm, y_mm=spec.motor_center_y_mm + point.y_mm), diameter) for point, (_, _, _, diameter) in zip(interface.mount_points, motor_features)]
    holes.append(("central_clearance", XYPoint(x_mm=spec.motor_center_x_mm, y_mm=spec.motor_center_y_mm), central_diameter))
    margins = {name: hole_edge_margin_mm(point, diameter, spec.plate_length_mm, spec.plate_width_mm) for name, point, diameter in holes}
    ligaments = [(hole_ligament_mm(first[1], first[2], second[1], second[2]), (first[0], second[0])) for index, first in enumerate(holes) for second in holes[index + 1:]]
    return margins, min(ligaments, key=lambda item: item[0])


def _synthesis_result(status, hardware_hash, requirements_hash, *, design_variables=None, derived_features=None, edge_margins_mm=None, minimum_ligament_mm=None, minimum_ligament_pair=None, spec=None, domain_spec_hash=None, infeasibility=None):
    payload = {"status": status.value, "hardware_interface_hash": hardware_hash, "design_requirements_hash": requirements_hash, "synthesis_version": AZIMUTH_MOUNT_PLATE_SYNTHESIS_VERSION, "design_variables": design_variables or {}, "derived_features": derived_features or {}, "domain_spec_hash": domain_spec_hash, "infeasibility": infeasibility.model_dump(mode="json") if infeasibility else None}
    return AzimuthMountPlateSynthesisResult(status=status, hardware_interface_hash=hardware_hash, design_requirements_hash=requirements_hash, design_variables=design_variables or {}, derived_features=derived_features or {}, edge_margins_mm=edge_margins_mm or {}, minimum_ligament_mm=minimum_ligament_mm, minimum_ligament_pair=minimum_ligament_pair, spec=spec, domain_spec_hash=domain_spec_hash, synthesis_hash=_hash_payload(payload), infeasibility=infeasibility)


def _synthesis_hash(result):
    return _hash_payload({"hardware_interface_hash": result.hardware_interface_hash, "design_requirements_hash": result.design_requirements_hash, "synthesis_version": result.synthesis_version, "design_variables": result.design_variables, "domain_spec_hash": result.domain_spec_hash})


def _hash_payload(value):
    return f"sha256:{hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()}"


def build_azimuth_mount_plate_proposal(result: AzimuthMountPlateSynthesisResult, *, project_id: str, source_revision: int, source_state_hash: str):
    from uuid import NAMESPACE_URL, uuid5
    from mechcad_harness.changes import ChangeOperation, OperationType
    from mechcad_harness.models import ChangeProposal, ProposalStatus

    if result.status is not SynthesisStatus.SUCCESS or result.spec is None:
        raise ValueError("only successful synthesis can produce a proposal")
    path = f"/azimuth_mount_plates/{result.spec.part_id}"
    value = result.spec.model_dump(mode="json")
    operation = ChangeOperation(operation=OperationType.ADD, path=path, value=value)
    identity = _hash_payload({"project_id": project_id, "source_revision": source_revision, "source_state_hash": source_state_hash, "hardware_interface_hash": result.hardware_interface_hash, "design_requirements_hash": result.design_requirements_hash, "synthesis_version": result.synthesis_version, "synthesis_hash": result.synthesis_hash, "domain_spec_hash": result.domain_spec_hash})
    return ChangeProposal(id=f"CP-{uuid5(NAMESPACE_URL, identity)}", title="Synthesize azimuth motor mount plate", status=ProposalStatus.DRAFT, base_revision=source_revision, base_state_hash=source_state_hash, actor="mechcad-azimuth-synthesis", operations=[operation])


class AzimuthMountPlateSynthesisService:
    def synthesize(self, state, *, source_revision: int, source_state_hash: str, project_id: str = "unbound"):
        from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer
        from mechcad_harness.engineering.keys import SupportedConstraintKey

        if state.revision != source_revision:
            return _synthesis_result(SynthesisStatus.NOT_READY, "unbound", "unbound", infeasibility=SynthesisInfeasibility(code="missing_requirement", message="stale source revision"))
        if source_state_hash == "" or state.revision <= 0:
            return _synthesis_result(SynthesisStatus.NOT_READY, "unbound", "unbound", infeasibility=SynthesisInfeasibility(code="missing_requirement", message="invalid source state binding"))
        materializer = ConstraintRequestMaterializer()
        try:
            if not materializer.is_satisfied(SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE, state):
                return _synthesis_result(SynthesisStatus.NOT_READY, "unbound", "unbound", infeasibility=SynthesisInfeasibility(code="missing_requirement", message="azimuth.drive_mount_interface"))
            if not materializer.is_satisfied(SupportedConstraintKey.AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS, state):
                return _synthesis_result(SynthesisStatus.NOT_READY, "unbound", "unbound", infeasibility=SynthesisInfeasibility(code="missing_requirement", message="azimuth.mount_plate_design_requirements"))
        except ValueError as exc:
            return _synthesis_result(SynthesisStatus.NOT_READY, "unbound", "unbound", infeasibility=SynthesisInfeasibility(code="missing_requirement", message=str(exc)))
        drive = next(parameter.value for parameter in state.authoritative_parameters if parameter.key is SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE).to_domain()
        requirements = next(parameter.value for parameter in state.authoritative_parameters if parameter.key is SupportedConstraintKey.AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS)
        result = synthesize_azimuth_motor_mount_plate(drive, requirements.to_domain())
        if result.status is SynthesisStatus.SUCCESS:
            return result.model_copy(update={"proposal": build_azimuth_mount_plate_proposal(result, project_id=project_id, source_revision=source_revision, source_state_hash=source_state_hash)})
        return result


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
