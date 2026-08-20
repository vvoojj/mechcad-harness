from mechcad_harness.yagi_sliding_interface import (
    SlidingArchitecture,
    SlidingInterfaceStatus,
    select_yagi_carrier_sliding_interface,
)


def test_both_native_extrusion_and_custom_slot_options_are_represented():
    result = select_yagi_carrier_sliding_interface()
    assert result.candidates == (SlidingArchitecture.NATIVE_EXTRUSION_T_SLOT, SlidingArchitecture.CUSTOM_THROUGH_SLOT)


def test_native_extrusion_is_selected_from_preferred_carrier_direction_and_adjustment_requirement():
    result = select_yagi_carrier_sliding_interface()
    assert result.status is SlidingInterfaceStatus.SUCCESS
    assert result.architecture is SlidingArchitecture.NATIVE_EXTRUSION_T_SLOT
    assert result.custom_through_slot_required is False
    assert result.continuous_lateral_travel_required is True
    assert result.compatible_clamp_attachment == "t_nut_or_equivalent"


def test_selection_is_independent_of_through_slot_implementation_existence():
    assert select_yagi_carrier_sliding_interface().architecture is SlidingArchitecture.NATIVE_EXTRUSION_T_SLOT


def test_profile_guidance_influences_selection_without_selecting_2040_or_4040():
    result = select_yagi_carrier_sliding_interface()
    assert result.preliminary_profile_guidance == ("2040",)
    assert result.preferred_profile_guidance == "4040"
    assert result.exact_extrusion_profile == "unresolved"
    assert result.final_profile_selected is False


def test_native_interface_leaves_vendor_geometry_unresolved_and_packaging_cad_ready():
    result = select_yagi_carrier_sliding_interface()
    assert result.unresolved_interface_inputs == ("exact_extrusion_profile_or_series", "native_t_slot_opening_geometry", "compatible_t_nut_interface")
    assert result.preliminary_packaging_cad_ready is True
    assert result.manufacturing_accurate_cad_ready is False
    assert result.antenna_collision_analysis_ready is True


def test_custom_through_slot_branch_preserves_r2_derivation_semantics():
    result = select_yagi_carrier_sliding_interface()
    custom = result.option(SlidingArchitecture.CUSTOM_THROUGH_SLOT)
    assert custom.slider_diameter_ownership == "design_variable_unless_externally_fixed"
    assert custom.slot_width_rule == "slider_diameter_mm + 2 * slot_radial_clearance_mm"
    assert custom.slot_total_length_rule == "440 mm + slot_width_mm"
    assert custom.slot_center_y_mm == 0


def test_structural_and_manufacturing_status_remain_preliminary():
    result = select_yagi_carrier_sliding_interface()
    assert result.structural_verification == "not_verified"
    assert result.manufacturing_status == "preliminary_packaging_geometry_only"
    assert result.proposal is None
    assert result.selected_collision_strategy is None


def test_selection_hash_is_deterministic():
    assert select_yagi_carrier_sliding_interface().selection_hash == select_yagi_carrier_sliding_interface().selection_hash
