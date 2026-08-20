import hashlib
import json
from enum import StrEnum

from pydantic import Field

from mechcad_harness.models.common import Model


YAGI_CARRIER_SLIDING_INTERFACE_SELECTION_VERSION = "yagi-carrier-sliding-interface-selection@1.0"


class SlidingInterfaceStatus(StrEnum):
    NOT_READY = "not_ready"
    SUCCESS = "success"


class SlidingArchitecture(StrEnum):
    NATIVE_EXTRUSION_T_SLOT = "native_extrusion_t_slot"
    CUSTOM_THROUGH_SLOT = "custom_through_slot"


class SlidingArchitectureOption(Model):
    architecture: SlidingArchitecture
    satisfies_continuous_lateral_travel: bool
    requires_custom_machining: bool
    removes_carrier_material: bool
    unresolved_inputs: tuple[str, ...] = ()
    slider_diameter_ownership: str | None = None
    slot_width_rule: str | None = None
    slot_total_length_rule: str | None = None
    slot_center_y_mm: float | None = None


class YagiCarrierSlidingInterfaceDesign(Model):
    status: SlidingInterfaceStatus
    architecture: SlidingArchitecture
    candidates: tuple[SlidingArchitecture, ...]
    selection_version: str = YAGI_CARRIER_SLIDING_INTERFACE_SELECTION_VERSION
    selection_rule: str = Field(min_length=1)
    selection_reasons: tuple[str, ...] = Field(min_length=1)
    continuous_lateral_travel_required: bool = True
    compatible_clamp_attachment: str = Field(min_length=1)
    custom_through_slot_required: bool
    preliminary_profile_guidance: tuple[str, ...]
    preferred_profile_guidance: str
    exact_extrusion_profile: str = "unresolved"
    final_profile_selected: bool = False
    unresolved_interface_inputs: tuple[str, ...] = ()
    preliminary_packaging_cad_ready: bool
    manufacturing_accurate_cad_ready: bool
    antenna_collision_analysis_ready: bool
    structural_verification: str = "not_verified"
    manufacturing_status: str = "preliminary_packaging_geometry_only"
    selected_collision_strategy: None = None
    selection_hash: str
    proposal: object | None = None
    options: tuple[SlidingArchitectureOption, ...]

    def option(self, architecture: SlidingArchitecture) -> SlidingArchitectureOption:
        return next(option for option in self.options if option.architecture is architecture)


def _hash_payload(value) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()}"


def select_yagi_carrier_sliding_interface() -> YagiCarrierSlidingInterfaceDesign:
    native = SlidingArchitectureOption(
        architecture=SlidingArchitecture.NATIVE_EXTRUSION_T_SLOT,
        satisfies_continuous_lateral_travel=True,
        requires_custom_machining=False,
        removes_carrier_material=False,
        unresolved_inputs=("exact_extrusion_profile_or_series", "native_t_slot_opening_geometry", "compatible_t_nut_interface"),
    )
    custom = SlidingArchitectureOption(
        architecture=SlidingArchitecture.CUSTOM_THROUGH_SLOT,
        satisfies_continuous_lateral_travel=True,
        requires_custom_machining=True,
        removes_carrier_material=True,
        unresolved_inputs=("selected_preliminary_slider_diameter_mm", "slot_radial_clearance_mm"),
        slider_diameter_ownership="design_variable_unless_externally_fixed",
        slot_width_rule="slider_diameter_mm + 2 * slot_radial_clearance_mm",
        slot_total_length_rule="440 mm + slot_width_mm",
        slot_center_y_mm=0,
    )
    payload = {
        "architecture": SlidingArchitecture.NATIVE_EXTRUSION_T_SLOT.value,
        "selection_version": YAGI_CARRIER_SLIDING_INTERFACE_SELECTION_VERSION,
        "preliminary_profile_guidance": ("2040",),
        "preferred_profile_guidance": "4040",
        "options": [native.model_dump(mode="json"), custom.model_dump(mode="json")],
    }
    return YagiCarrierSlidingInterfaceDesign(
        status=SlidingInterfaceStatus.SUCCESS,
        architecture=SlidingArchitecture.NATIVE_EXTRUSION_T_SLOT,
        candidates=(SlidingArchitecture.NATIVE_EXTRUSION_T_SLOT, SlidingArchitecture.CUSTOM_THROUGH_SLOT),
        selection_rule="Reject options that fail continuous adjustment; then prefer the existing extrusion carrier direction, native standard sliding interfaces, fewer custom manufacturing features, and fewer unresolved CAD-driving dimensions.",
        selection_reasons=(
            "aluminum extrusion is the accepted carrier direction",
            "native T-slot interfaces provide continuous clamp travel without custom through-slot machining",
            "custom through-slot geometry requires unresolved slider diameter and clearance policy",
            "no requirement demands removal of carrier material for a custom slot",
        ),
        compatible_clamp_attachment="t_nut_or_equivalent",
        custom_through_slot_required=False,
        preliminary_profile_guidance=("2040",),
        preferred_profile_guidance="4040",
        unresolved_interface_inputs=native.unresolved_inputs,
        preliminary_packaging_cad_ready=True,
        manufacturing_accurate_cad_ready=False,
        antenna_collision_analysis_ready=True,
        selection_hash=_hash_payload(payload),
        options=(native, custom),
    )
