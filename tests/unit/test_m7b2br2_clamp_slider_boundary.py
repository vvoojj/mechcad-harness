import pytest

from mechcad_harness.yagi_clamp_slider import (
    ClampSliderBoundaryStatus,
    ClampSliderInterfaceSource,
    PreliminaryClampSliderPolicy,
    classify_clamp_slider_boundary,
)


def test_unselected_clamp_makes_slider_diameter_a_design_variable_and_slot_width_derived():
    result = classify_clamp_slider_boundary(
        lateral_adjustment_min_y_mm=-220,
        lateral_adjustment_max_y_mm=220,
        carrier_length_mm=500,
    )
    assert result.status is ClampSliderBoundaryStatus.PRELIMINARY_POLICY_REQUIRED
    assert result.interface_source is ClampSliderInterfaceSource.DESIGN_DERIVED
    assert result.external_hardware_facts_required == ()
    assert result.design_variables == ("selected_preliminary_slider_diameter_mm",)
    assert result.derived_cad_values == ("slot_width_mm", "slot_total_length_mm", "slot_center_y_mm", "end_material_mm")
    assert result.missing_design_requirements == ("allowed_preliminary_slider_diameters_mm", "slot_radial_clearance_mm")
    assert result.selected_slider_diameter_mm is None
    assert result.slot_width_mm is None


def test_external_fixed_slider_is_classified_as_hardware_fact():
    result = classify_clamp_slider_boundary(
        lateral_adjustment_min_y_mm=-220,
        lateral_adjustment_max_y_mm=220,
        carrier_length_mm=500,
        external_slider_diameter_mm=8,
    )
    assert result.interface_source is ClampSliderInterfaceSource.EXTERNAL_HARDWARE
    assert result.external_hardware_facts_required == ("slot_radial_clearance_mm",)
    assert result.design_variables == ()


def test_clearance_is_a_requirement_not_silently_equal_to_slider_diameter():
    result = classify_clamp_slider_boundary(
        lateral_adjustment_min_y_mm=-220,
        lateral_adjustment_max_y_mm=220,
        carrier_length_mm=500,
        external_slider_diameter_mm=8,
    )
    assert result.slot_width_mm is None
    assert "slot_radial_clearance_mm" in result.external_hardware_facts_required


def test_policy_selects_diameter_and_derives_slot_geometry_without_structural_claim():
    result = classify_clamp_slider_boundary(
        lateral_adjustment_min_y_mm=-220,
        lateral_adjustment_max_y_mm=220,
        carrier_length_mm=500,
        policy=PreliminaryClampSliderPolicy(allowed_preliminary_slider_diameters_mm=(8, 6), slot_radial_clearance_mm=0.5, provenance="PRELIMINARY-POLICY"),
    )
    assert result.status is ClampSliderBoundaryStatus.READY
    assert result.selected_slider_diameter_mm == 6
    assert result.slot_width_mm == 7
    assert result.slot_total_length_mm == 447
    assert result.slot_center_y_mm == 0
    assert result.end_material_mm == pytest.approx(26.5)
    assert result.structural_verification == "not_verified"
    assert result.carrier_structural_status == "not_verified"


def test_slot_total_length_uses_center_travel_plus_slot_width():
    result = classify_clamp_slider_boundary(
        lateral_adjustment_min_y_mm=-220,
        lateral_adjustment_max_y_mm=220,
        carrier_length_mm=500,
        policy=PreliminaryClampSliderPolicy(allowed_preliminary_slider_diameters_mm=(10,), slot_radial_clearance_mm=1, provenance="POLICY"),
    )
    assert result.required_center_travel_mm == 440
    assert result.slot_width_mm == 12
    assert result.slot_total_length_mm == 452
    assert result.end_material_mm == 24


def test_geometrically_incompatible_policy_is_not_clipped():
    result = classify_clamp_slider_boundary(
        lateral_adjustment_min_y_mm=-220,
        lateral_adjustment_max_y_mm=220,
        carrier_length_mm=500,
        policy=PreliminaryClampSliderPolicy(allowed_preliminary_slider_diameters_mm=(500,), slot_radial_clearance_mm=1, provenance="POLICY"),
    )
    assert result.status is ClampSliderBoundaryStatus.INFEASIBLE
    assert result.slot_total_length_mm == 942
    assert result.end_material_mm == -221


def test_no_direct_state_mutation_or_carrier_cad_is_performed():
    result = classify_clamp_slider_boundary(
        lateral_adjustment_min_y_mm=-220,
        lateral_adjustment_max_y_mm=220,
        carrier_length_mm=500,
    )
    assert result.proposal is None
    assert result.carrier_cad_generation_authorized is False
    assert result.fore_aft_adjustment_owner == "interchangeable_clamp"
