from typing import Annotated, Literal, Union

from pydantic import Field, model_validator

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AngularSpeedQuantity(Model):
    source_value: float
    source_unit: Literal["deg/s", "rad/s"]
    canonical_value_rad_s: float = Field(gt=0)


class OutputAngularSpeedValue(Model):
    kind: Literal["transmission.output_angular_speed"]
    value_rad_s: float = Field(gt=0)


class MotorCharacteristicsValue(Model):
    kind: Literal["transmission.motor_characteristics"]
    motor_id: str = Field(min_length=1)
    speed_min_rpm: float = Field(ge=0)
    speed_max_rpm: float = Field(gt=0)
    continuous_torque_nm: float = Field(gt=0)
    peak_torque_nm: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.speed_min_rpm > self.speed_max_rpm or self.peak_torque_nm < self.continuous_torque_nm:
            raise ValueError("motor characteristics ranges are invalid")
        return self


class OutputInterfaceValue(Model):
    kind: Literal["transmission.output_interface"]
    interface_type: str = Field(min_length=1)
    shaft_diameter_mm: float | None = Field(default=None, gt=0)
    torque_transfer_description: str = Field(min_length=1)


class PackagingEnvelopeValue(Model):
    kind: Literal["transmission.packaging_envelope"]
    max_length_mm: float = Field(gt=0)
    max_width_mm: float = Field(gt=0)
    max_height_mm: float = Field(gt=0)
    mounting_description: str = Field(min_length=1)


class AzimuthDriveMountInterfaceValue(Model):
    kind: Literal["azimuth.drive_mount_interface"]
    component_id: str = Field(min_length=1)
    coordinate_convention: Literal["interface-center; mounting plane XY; +Z housing-to-mating-plate; +X source-defined reference; +Y right-handed"] = "interface-center; mounting plane XY; +Z housing-to-mating-plate; +X source-defined reference; +Y right-handed"
    in_plane_alignment: Literal["aligned-with-plate-axes"] = "aligned-with-plate-axes"
    frame_reference_id: str = Field(min_length=1)
    mount_points: tuple[dict, ...] = Field(min_length=1)
    central_keepout_diameter_mm: float | None = Field(default=None, gt=0)
    central_required_mating_opening_diameter_mm: float | None = Field(default=None, gt=0)
    manufacturer_required_central_radial_clearance_mm: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_mount_points(self):
        ids = [point.get("hole_id") for point in self.mount_points]
        if any(not isinstance(item, str) or not item.strip() for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("mount point IDs must be unique")
        return self

    def to_domain(self):
        from mechcad_harness.azimuth_mount_plate import AzimuthDriveMountInterface
        return AzimuthDriveMountInterface.model_validate(self.model_dump(exclude={"kind"}))


class PlateThicknessPolicyValue(Model):
    allowed_thicknesses_mm: tuple[float, ...]
    minimum_thickness_mm: float


class AzimuthMotorMountPlateDesignRequirementsValue(Model):
    kind: Literal["azimuth.mount_plate_design_requirements"]
    minimum_edge_margin_mm: float
    minimum_hole_ligament_mm: float
    plate_thickness_policy: PlateThicknessPolicyValue
    mounting_hole_radial_clearance_mm: float | None = None
    central_radial_clearance_mm: float | None = None
    provenance: str = "M7B1B_TEST_FIXTURE_ONLY"

    @classmethod
    def from_domain(cls, requirements):
        return cls(kind="azimuth.mount_plate_design_requirements", **requirements.model_dump(mode="json"))

    def to_domain(self):
        from mechcad_harness.azimuth_mount_plate import AzimuthMotorMountPlateDesignRequirements, PlateThicknessPolicy
        payload = self.model_dump(exclude={"kind"})
        payload["plate_thickness_policy"] = PlateThicknessPolicy.model_validate(payload["plate_thickness_policy"])
        return AzimuthMotorMountPlateDesignRequirements(**payload)


class YagiEnvelopeValue(Model):
    semantic_id: str = Field(min_length=1)
    frequency_class: str = Field(min_length=1)
    length_mm: float = Field(gt=0)
    span_mm: float = Field(gt=0)
    depth_mm: float = Field(gt=0)
    placeholder_mass_kg: float = Field(gt=0)
    placeholder_wind_area_m2: float = Field(gt=0)
    mass_semantics: Literal["engineering_placeholder"] = "engineering_placeholder"
    wind_area_semantics: Literal["engineering_placeholder"] = "engineering_placeholder"
    envelope_semantics: Literal["collision_envelope"] = "collision_envelope"


class YagiPayloadCarrierRequirementsValue(Model):
    kind: Literal["yagi.payload_carrier_requirements"]
    frequency_families_ghz: tuple[float, ...] = Field(min_length=1)
    minimum_antenna_count: int = Field(ge=2)
    maximum_antenna_count: int = Field(le=3)
    maximum_rotating_payload_kg: float = Field(gt=0)
    envelopes: tuple[YagiEnvelopeValue, ...] = Field(min_length=5)
    nominal_spacing_mm: float = Field(gt=0)
    adjustable_spacing_required: bool
    recommended_lateral_adjustment_mm: float = Field(gt=0)
    preferred_carrier_length_mm: float = Field(gt=0)
    required_fore_aft_travel_mm: float = Field(gt=0)
    preferred_fore_aft_travel_mm: float = Field(gt=0)
    preferred_com_offset_mm: float = Field(gt=0)
    acceptable_com_offset_mm: float = Field(gt=0)
    collision_resolution_strategies: tuple[Literal["orientation", "vertical_staggering", "increased_spacing", "longitudinal_staggering"], ...] = Field(min_length=1)
    maximum_collision_envelope_mm: tuple[float, float, float]
    representative_payload_mass_kg: float = Field(gt=0)
    el_rotation_semantics: Literal["up_to_360_where_mechanically_possible"] = "up_to_360_where_mechanically_possible"
    el_collision_sweep_degrees: tuple[float, ...] = Field(min_length=1)
    el_axis_height_semantics: Literal["parametric"] = "parametric"
    el_axis_height_search_range_mm: tuple[float, float]
    az_continuous_multiturn: bool
    az_target_revolution_time_s: float = Field(gt=0)
    carrier_material_guidance: Literal["aluminum_extrusion"] = "aluminum_extrusion"
    preliminary_profile_guidance: tuple[str, ...] = ("2040",)
    preferred_profile_guidance: str = "4040"
    interchangeable_adjustable_mounts_required: bool
    boom_compatibility_targets: tuple[str, ...] = Field(min_length=1)
    wind_speed_status: Literal["not_frozen"] = "not_frozen"
    final_carrier_cross_section_status: Literal["not_structurally_accepted"] = "not_structurally_accepted"
    exact_yagi_products_status: Literal["not_frozen"] = "not_frozen"
    exact_boom_sections_status: Literal["not_frozen"] = "not_frozen"
    polarization_status: Literal["not_frozen"] = "not_frozen"
    cable_routing_status: Literal["not_frozen"] = "not_frozen"
    provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_semantics(self):
        if self.minimum_antenna_count > self.maximum_antenna_count:
            raise ValueError("antenna count range is invalid")
        if self.maximum_rotating_payload_kg != 5.0:
            raise ValueError("maximum rotating payload must preserve the hard 5 kg limit")
        if self.required_fore_aft_travel_mm > self.preferred_fore_aft_travel_mm:
            raise ValueError("preferred fore/aft travel must meet required travel")
        if self.preferred_com_offset_mm > self.acceptable_com_offset_mm:
            raise ValueError("preferred COM target must be stricter than acceptable target")
        if self.representative_payload_mass_kg >= self.maximum_rotating_payload_kg:
            raise ValueError("representative payload must remain distinct from hard payload limit")
        if self.maximum_collision_envelope_mm != (850.0, 400.0, 80.0):
            raise ValueError("maximum collision envelope must preserve the authoritative envelope")
        if self.el_axis_height_search_range_mm != (180.0, 300.0):
            raise ValueError("EL axis search range must preserve the authoritative range")
        return self


AuthoritativeValue = Annotated[Union[OutputAngularSpeedValue, MotorCharacteristicsValue, OutputInterfaceValue, PackagingEnvelopeValue, AzimuthDriveMountInterfaceValue, AzimuthMotorMountPlateDesignRequirementsValue, YagiPayloadCarrierRequirementsValue], Field(discriminator="kind")]
