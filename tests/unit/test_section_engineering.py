import pytest

from mechcad_harness.materials import (
    MaterialDataAuthority,
    MaterialPropertyName,
    MaterialPropertyStatus,
    MaterialPropertyValue,
    TypicalMaterialPropertiesResult,
)
from mechcad_harness.sections import SectionGeometryResult, SectionWarpingResult


def _material(*, density=True, modulus=True, shear=False, density_unit="kg/m^3", modulus_unit="GPa"):
    properties = {}
    if modulus:
        properties["elastic_modulus"] = MaterialPropertyValue(
            property=MaterialPropertyName.ELASTIC_MODULUS,
            unit=modulus_unit,
            status=MaterialPropertyStatus.AVAILABLE,
            min_value=68,
            max_value=72,
            authority=MaterialDataAuthority.TYPICAL_REFERENCE,
            source="test",
        )
    else:
        properties["elastic_modulus"] = MaterialPropertyValue(
            property=MaterialPropertyName.ELASTIC_MODULUS,
            unit=modulus_unit,
            status=MaterialPropertyStatus.MISSING,
            authority=MaterialDataAuthority.TYPICAL_REFERENCE,
            source="test",
        )
    if shear:
        properties["shear_modulus"] = MaterialPropertyValue(
            property=MaterialPropertyName.SHEAR_MODULUS,
            unit="GPa",
            status=MaterialPropertyStatus.AVAILABLE,
            min_value=25,
            max_value=27,
            authority=MaterialDataAuthority.TYPICAL_REFERENCE,
            source="test",
        )
    if density:
        density_value = MaterialPropertyValue(
            property=MaterialPropertyName.DENSITY,
            unit=density_unit,
            status=MaterialPropertyStatus.AVAILABLE,
            min_value=2810,
            max_value=2810,
            representative_value=2810,
            authority=MaterialDataAuthority.TYPICAL_REFERENCE,
            source="test",
            value_semantics="representative",
        )
    else:
        density_value = MaterialPropertyValue(
            property=MaterialPropertyName.DENSITY,
            unit=density_unit,
            status=MaterialPropertyStatus.MISSING,
            authority=MaterialDataAuthority.TYPICAL_REFERENCE,
            source="test",
        )
    return TypicalMaterialPropertiesResult(
        canonical_name="Alu_G7075_T6",
        category="metal",
        family="aluminum",
        authority=MaterialDataAuthority.TYPICAL_REFERENCE,
        density=density_value,
        properties=properties,
        backend_provenance={
            "backend_name": "test",
            "backend_adapter_version": "0.0.0",
        },
    )


def _geometry():
    return SectionGeometryResult(
        section_type="rectangle",
        area_mm2=5000,
        centroid_x_mm=25,
        centroid_y_mm=50,
        ixx_centroid_mm4=50 * 100**3 / 12,
        iyy_centroid_mm4=100 * 50**3 / 12,
        ixy_centroid_mm4=0,
        perimeter_mm=300,
        radius_of_gyration_x_mm=28.8675,
        radius_of_gyration_y_mm=14.4338,
        mesh_metadata={"mesh_size_mm2": 5},
    )


def _input(material=None, warping=None):
    from mechcad_harness.section_engineering import PreliminarySectionEngineeringCalculatorInput

    return PreliminarySectionEngineeringCalculatorInput(material=material or _material(), section_geometry=_geometry(), section_warping=warping)


def test_aluminum_rectangle_preserves_ranges_and_representative_mass():
    from mechcad_harness.section_engineering import DerivedPropertyStatus, calculate_preliminary_section_engineering

    result = calculate_preliminary_section_engineering(_input())
    assert result.mass_per_length.status is DerivedPropertyStatus.AVAILABLE
    assert result.mass_per_length.representative_value == pytest.approx(14.05)
    assert result.axial_rigidity_ea.min_value == pytest.approx(340_000_000)
    assert result.axial_rigidity_ea.max_value == pytest.approx(360_000_000)
    assert result.axial_rigidity_ea.representative_value is None
    assert result.material_authority is MaterialDataAuthority.TYPICAL_REFERENCE


def test_missing_modulus_returns_partial_result_without_fabricated_values():
    from mechcad_harness.section_engineering import DerivedPropertyStatus, calculate_preliminary_section_engineering

    result = calculate_preliminary_section_engineering(_input(_material(modulus=False)))
    assert result.mass_per_length.status is DerivedPropertyStatus.AVAILABLE
    assert result.axial_rigidity_ea.status is DerivedPropertyStatus.UNAVAILABLE
    assert result.bending_rigidity_eix.status is DerivedPropertyStatus.UNAVAILABLE
    assert result.bending_rigidity_eiy.status is DerivedPropertyStatus.UNAVAILABLE
    assert result.axial_rigidity_ea.min_value is None


def test_missing_density_keeps_stiffness_and_marks_mass_unavailable():
    from mechcad_harness.section_engineering import DerivedPropertyStatus, calculate_preliminary_section_engineering

    result = calculate_preliminary_section_engineering(_input(_material(density=False)))
    assert result.mass_per_length.status is DerivedPropertyStatus.UNAVAILABLE
    assert result.axial_rigidity_ea.status is DerivedPropertyStatus.AVAILABLE
    assert result.bending_rigidity_eix.status is DerivedPropertyStatus.AVAILABLE


def test_missing_shear_modulus_is_explicitly_unavailable():
    from mechcad_harness.section_engineering import DerivedPropertyStatus, calculate_preliminary_section_engineering

    result = calculate_preliminary_section_engineering(_input())
    assert result.torsional_rigidity_gj.status is DerivedPropertyStatus.UNAVAILABLE
    assert result.torsional_rigidity_gj.reason == "SHEAR_MODULUS_UNAVAILABLE"


def test_explicit_shear_modulus_and_warping_produce_gj():
    from mechcad_harness.section_engineering import DerivedPropertyStatus, calculate_preliminary_section_engineering

    warping = SectionWarpingResult(
        section_type="rectangle",
        torsion_constant_j_mm4=2_000_000,
        shear_center_x_mm=25,
        shear_center_y_mm=50,
        shear_area_x_mm2=4000,
        shear_area_y_mm2=4000,
        warping_constant_mm6=100,
        solver_type="direct",
        mesh_metadata={"mesh_size_mm2": 1},
        convergence_metadata={"converged": True},
    )
    result = calculate_preliminary_section_engineering(_input(_material(shear=True), warping))
    assert result.torsional_rigidity_gj.status is DerivedPropertyStatus.AVAILABLE
    assert result.torsional_rigidity_gj.min_value == pytest.approx(50_000_000_000)
    assert result.torsional_rigidity_gj.max_value == pytest.approx(54_000_000_000)


def test_unsupported_units_fail_closed():
    from mechcad_harness.section_engineering import calculate_preliminary_section_engineering

    with pytest.raises(ValueError, match="unsupported unit"):
        calculate_preliminary_section_engineering(_input(_material(modulus_unit="MPa")))


def test_no_midpoint_is_fabricated_and_assumptions_are_explicit():
    from mechcad_harness.section_engineering import calculate_preliminary_section_engineering

    result = calculate_preliminary_section_engineering(_input())
    assert result.bending_rigidity_eix.representative_value is None
    assert "HOMOGENEOUS_SECTION" in result.assumptions
    assert "ISOTROPIC_LINEAR_ELASTIC_PRELIMINARY" in result.assumptions
