from enum import StrEnum

from pydantic import Field, model_validator

from mechcad_harness.models.common import Model


class ClampSliderBoundaryStatus(StrEnum):
    PRELIMINARY_POLICY_REQUIRED = "preliminary_policy_required"
    EXTERNAL_INTERFACE_REQUIRED = "external_interface_required"
    INFEASIBLE = "infeasible"
    READY = "ready"


class ClampSliderInterfaceSource(StrEnum):
    DESIGN_DERIVED = "design_derived"
    EXTERNAL_HARDWARE = "external_hardware"


class PreliminaryClampSliderPolicy(Model):
    allowed_preliminary_slider_diameters_mm: tuple[float, ...] = Field(min_length=1)
    slot_radial_clearance_mm: float = Field(ge=0)
    provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_policy(self):
        if any(value <= 0 for value in self.allowed_preliminary_slider_diameters_mm):
            raise ValueError("preliminary slider diameters must be positive")
        if len(set(self.allowed_preliminary_slider_diameters_mm)) != len(self.allowed_preliminary_slider_diameters_mm):
            raise ValueError("preliminary slider diameters must be unique")
        return self

    def select(self) -> float:
        return min(self.allowed_preliminary_slider_diameters_mm)


class ClampSliderBoundaryResult(Model):
    status: ClampSliderBoundaryStatus
    interface_source: ClampSliderInterfaceSource
    external_hardware_facts_required: tuple[str, ...] = ()
    missing_design_requirements: tuple[str, ...] = ()
    design_variables: tuple[str, ...] = ()
    derived_cad_values: tuple[str, ...] = ("slot_width_mm", "slot_total_length_mm", "slot_center_y_mm", "end_material_mm")
    required_center_travel_mm: float
    selected_slider_diameter_mm: float | None = None
    slot_radial_clearance_mm: float | None = None
    slot_width_mm: float | None = None
    slot_total_length_mm: float | None = None
    slot_center_y_mm: float = 0.0
    end_material_mm: float | None = None
    structural_verification: str = "not_verified"
    carrier_structural_status: str = "not_verified"
    fore_aft_adjustment_owner: str = "interchangeable_clamp"
    carrier_cad_generation_authorized: bool = False
    proposal: object | None = None


def classify_clamp_slider_boundary(*, lateral_adjustment_min_y_mm: float, lateral_adjustment_max_y_mm: float, carrier_length_mm: float, external_slider_diameter_mm: float | None = None, policy: PreliminaryClampSliderPolicy | None = None) -> ClampSliderBoundaryResult:
    center_travel = lateral_adjustment_max_y_mm - lateral_adjustment_min_y_mm
    if center_travel <= 0 or carrier_length_mm <= 0:
        raise ValueError("carrier travel and length must be positive")
    if external_slider_diameter_mm is not None:
        if external_slider_diameter_mm <= 0:
            raise ValueError("external slider diameter must be positive")
        if policy is None:
            return ClampSliderBoundaryResult(
                status=ClampSliderBoundaryStatus.EXTERNAL_INTERFACE_REQUIRED,
                interface_source=ClampSliderInterfaceSource.EXTERNAL_HARDWARE,
                external_hardware_facts_required=("slot_radial_clearance_mm",),
                required_center_travel_mm=center_travel,
            )
        selected = external_slider_diameter_mm
        source = ClampSliderInterfaceSource.EXTERNAL_HARDWARE
        design_variables = ()
    else:
        source = ClampSliderInterfaceSource.DESIGN_DERIVED
        design_variables = ("selected_preliminary_slider_diameter_mm",)
        if policy is None:
            return ClampSliderBoundaryResult(
                status=ClampSliderBoundaryStatus.PRELIMINARY_POLICY_REQUIRED,
                interface_source=source,
                missing_design_requirements=("allowed_preliminary_slider_diameters_mm", "slot_radial_clearance_mm"),
                design_variables=design_variables,
                required_center_travel_mm=center_travel,
            )
        selected = policy.select()
    slot_width = selected + 2 * policy.slot_radial_clearance_mm
    slot_length = center_travel + slot_width
    end_material = (carrier_length_mm - slot_length) / 2
    return ClampSliderBoundaryResult(
        status=ClampSliderBoundaryStatus.READY if end_material > 0 else ClampSliderBoundaryStatus.INFEASIBLE,
        interface_source=source,
        design_variables=design_variables,
        required_center_travel_mm=center_travel,
        selected_slider_diameter_mm=selected,
        slot_radial_clearance_mm=policy.slot_radial_clearance_mm,
        slot_width_mm=slot_width,
        slot_total_length_mm=slot_length,
        slot_center_y_mm=(lateral_adjustment_min_y_mm + lateral_adjustment_max_y_mm) / 2,
        end_material_mm=end_material,
    )
