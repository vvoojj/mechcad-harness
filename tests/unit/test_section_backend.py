import importlib.util
import math

import pytest

from mechcad_harness.backends import BackendHealthStatus
from mechcad_harness.sections import CircleSectionInput, HollowCircleSectionInput, RectangleSectionInput

SECTION_PROPERTIES_AVAILABLE = importlib.util.find_spec("sectionproperties") is not None


def test_section_backend_identity_preserves_geometry_and_adds_warping():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    identity = SectionPropertiesAdapter.identity
    assert identity.name == "section-properties"
    assert identity.adapter_version == "0.2.0"
    assert identity.library_version == "3.10.2"
    assert identity.capabilities == ("structural.cross_section.geometry", "structural.cross_section.warping")


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_section_backend_is_available_in_validated_profile():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    health = SectionPropertiesAdapter().healthcheck()
    assert health.status is BackendHealthStatus.AVAILABLE
    assert health.detected_version == "3.10.2"


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_rectangle_golden_case_matches_independent_oracle_and_upstream_centroid():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    result = SectionPropertiesAdapter().rectangle(
        RectangleSectionInput(width_mm=50, height_mm=100, mesh_size_mm2=5)
    )
    assert result.area_mm2 == pytest.approx(5000, rel=1e-8)
    assert result.ixx_centroid_mm4 == pytest.approx(50 * 100**3 / 12, rel=1e-8)
    assert result.iyy_centroid_mm4 == pytest.approx(100 * 50**3 / 12, rel=1e-8)
    assert result.ixy_centroid_mm4 == pytest.approx(0, abs=1e-7)
    assert result.centroid_x_mm == pytest.approx(25, abs=1e-8)
    assert result.centroid_y_mm == pytest.approx(50, abs=1e-8)


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_circle_matches_independent_oracle_and_upstream_origin():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    diameter = 50
    result = SectionPropertiesAdapter().circle(
        CircleSectionInput(diameter_mm=diameter, discretization_points=256, mesh_size_mm2=2)
    )
    assert result.area_mm2 == pytest.approx(math.pi * diameter**2 / 4, rel=2e-4)
    expected_i = math.pi * diameter**4 / 64
    assert result.ixx_centroid_mm4 == pytest.approx(expected_i, rel=3e-4)
    assert result.iyy_centroid_mm4 == pytest.approx(expected_i, rel=3e-4)
    assert result.ixy_centroid_mm4 == pytest.approx(0, abs=1e-7)
    assert result.centroid_x_mm == pytest.approx(0, abs=1e-8)
    assert result.centroid_y_mm == pytest.approx(0, abs=1e-8)


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_hollow_circle_matches_independent_oracle_and_upstream_origin():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    outer = 50
    thickness = 5
    inner = outer - 2 * thickness
    result = SectionPropertiesAdapter().hollow_circle(
        HollowCircleSectionInput(
            outer_diameter_mm=outer,
            wall_thickness_mm=thickness,
            discretization_points=256,
            mesh_size_mm2=2,
        )
    )
    assert result.area_mm2 == pytest.approx(math.pi * (outer**2 - inner**2) / 4, rel=2e-4)
    expected_i = math.pi * (outer**4 - inner**4) / 64
    assert result.ixx_centroid_mm4 == pytest.approx(expected_i, rel=3e-4)
    assert result.iyy_centroid_mm4 == pytest.approx(expected_i, rel=3e-4)
    assert result.ixy_centroid_mm4 == pytest.approx(0, abs=1e-7)
    assert result.centroid_x_mm == pytest.approx(0, abs=1e-8)
    assert result.centroid_y_mm == pytest.approx(0, abs=1e-8)


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_rectangle_mesh_sizes_are_mesh_independent_for_geometric_properties():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    adapter = SectionPropertiesAdapter()
    coarse = adapter.rectangle(RectangleSectionInput(width_mm=50, height_mm=100, mesh_size_mm2=20))
    fine = adapter.rectangle(RectangleSectionInput(width_mm=50, height_mm=100, mesh_size_mm2=2))
    assert coarse.mesh_metadata["mesh_size_mm2"] == 20
    assert fine.mesh_metadata["mesh_size_mm2"] == 2
    assert coarse.area_mm2 == pytest.approx(fine.area_mm2, rel=1e-8)
    assert coarse.ixx_centroid_mm4 == pytest.approx(fine.ixx_centroid_mm4, rel=1e-8)
    assert coarse.iyy_centroid_mm4 == pytest.approx(fine.iyy_centroid_mm4, rel=1e-8)


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_circle_discretization_accuracy_improves_or_is_preserved():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    adapter = SectionPropertiesAdapter()
    expected = math.pi * 50**2 / 4
    coarse = adapter.circle(CircleSectionInput(diameter_mm=50, discretization_points=16, mesh_size_mm2=2))
    fine = adapter.circle(CircleSectionInput(diameter_mm=50, discretization_points=128, mesh_size_mm2=2))
    assert fine.mesh_metadata["discretization_points"] == 128
    assert abs(fine.area_mm2 - expected) <= abs(coarse.area_mm2 - expected)


def test_invalid_wall_thickness_is_rejected():
    with pytest.raises(Exception):
        HollowCircleSectionInput(outer_diameter_mm=10, wall_thickness_mm=5, discretization_points=32, mesh_size_mm2=2)
