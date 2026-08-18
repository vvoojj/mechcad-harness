import importlib.util
import math

import pytest

from mechcad_harness.sections import CircleSectionInput, HollowCircleSectionInput, RectangleSectionInput

SECTION_PROPERTIES_AVAILABLE = importlib.util.find_spec("sectionproperties") is not None


def test_warping_result_model_is_mechcad_owned():
    from mechcad_harness.sections import SectionWarpingResult

    result = SectionWarpingResult(
        section_type="circle",
        torsion_constant_j_mm4=100.0,
        shear_center_x_mm=0.0,
        shear_center_y_mm=0.0,
        shear_area_x_mm2=10.0,
        shear_area_y_mm2=10.0,
        warping_constant_mm6=0.0,
        solver_type="direct",
        mesh_metadata={"mesh_size_mm2": 2.0},
        convergence_metadata={"converged": True},
        backend_provenance=None,
    )
    assert result.solver_type == "direct"
    assert "convergence_metadata" in result.model_dump(mode="json")


def test_warping_result_rejects_nonfinite_values():
    from mechcad_harness.sections import SectionWarpingResult

    with pytest.raises(Exception):
        SectionWarpingResult(
            section_type="circle",
            torsion_constant_j_mm4=math.nan,
            shear_center_x_mm=0,
            shear_center_y_mm=0,
            shear_area_x_mm2=1,
            shear_area_y_mm2=1,
            warping_constant_mm6=0,
            solver_type="direct",
            mesh_metadata={},
            convergence_metadata={},
        )


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_adapter_version_and_warping_capability():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    assert SectionPropertiesAdapter.identity.adapter_version == "0.2.0"
    assert SectionPropertiesAdapter.identity.capabilities == (
        "structural.cross_section.geometry",
        "structural.cross_section.warping",
    )


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_rectangle_warping_is_positive_converged_and_symmetric():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    result = SectionPropertiesAdapter().rectangle_warping(
        RectangleSectionInput(width_mm=50, height_mm=100, mesh_size_mm2=20)
    )
    assert result.torsion_constant_j_mm4 > 0
    assert result.convergence_metadata["converged"] is True
    assert result.convergence_metadata["solver_type"] == "direct"
    assert result.shear_center_x_mm == pytest.approx(25, abs=1e-6)
    assert result.shear_center_y_mm == pytest.approx(50, abs=1e-6)
    assert result.shear_area_x_mm2 > 0
    assert result.shear_area_y_mm2 > 0
    assert math.isfinite(result.warping_constant_mm6)


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_circle_warping_matches_independent_torsion_oracle():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    diameter = 50
    result = SectionPropertiesAdapter().circle_warping(
        CircleSectionInput(diameter_mm=diameter, discretization_points=128, mesh_size_mm2=20)
    )
    expected_j = math.pi * diameter**4 / 32
    assert result.torsion_constant_j_mm4 == pytest.approx(expected_j, rel=3e-3)
    assert result.shear_center_x_mm == pytest.approx(0, abs=1e-6)
    assert result.shear_center_y_mm == pytest.approx(0, abs=1e-6)


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_hollow_circle_warping_matches_independent_torsion_oracle():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    outer = 50
    inner = 40
    result = SectionPropertiesAdapter().hollow_circle_warping(
        HollowCircleSectionInput(outer_diameter_mm=outer, wall_thickness_mm=5, discretization_points=128, mesh_size_mm2=20)
    )
    expected_j = math.pi * (outer**4 - inner**4) / 32
    assert result.torsion_constant_j_mm4 == pytest.approx(expected_j, rel=3e-3)
    assert result.shear_center_x_mm == pytest.approx(0, abs=1e-6)
    assert result.shear_center_y_mm == pytest.approx(0, abs=1e-6)


def test_direct_solver_is_the_only_supported_solver():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    with pytest.raises(ValueError):
        SectionPropertiesAdapter()._validate_solver_type("cgs")


def test_existing_c2a_inputs_remain_available():
    assert RectangleSectionInput(width_mm=50, height_mm=100, mesh_size_mm2=20).width_mm == 50
    assert CircleSectionInput(diameter_mm=50, discretization_points=128, mesh_size_mm2=20).diameter_mm == 50


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_warping_records_two_level_convergence_metadata_and_backend_provenance():
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    result = SectionPropertiesAdapter().circle_warping(
        CircleSectionInput(diameter_mm=50, discretization_points=128, mesh_size_mm2=20)
    )
    metadata = result.convergence_metadata
    assert metadata["coarse_mesh_size_mm2"] == 20
    assert metadata["fine_mesh_size_mm2"] == 5
    assert metadata["solver_type"] == "direct"
    assert metadata["converged"] is True
    assert metadata["j_relative_difference"] <= metadata["j_relative_tolerance"]
    assert result.backend_provenance.backend_adapter_version == "0.2.0"


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_nonconvergence_fails_closed(monkeypatch):
    from mechcad_harness.backends.section_properties import SectionPropertiesAdapter

    adapter = SectionPropertiesAdapter()
    monkeypatch.setattr(adapter, "_calculate_warping_level", lambda *args, **kwargs: {"j": 1.0, "sc_x": 0.0, "sc_y": 0.0, "as_x": 1.0, "as_y": 1.0, "gamma": 1.0, "nodes": 1, "elements": 1})
    monkeypatch.setattr(adapter, "_warping_tolerances", lambda: {"j_relative": 1e-3, "gamma_relative": 1e-3, "gamma_absolute": 1e-6, "shear_area_relative": 1e-3, "shear_center_absolute_mm": 1e-6})
    values = iter((1.0, 2.0))
    monkeypatch.setattr(adapter, "_calculate_warping_level", lambda *args, **kwargs: {"j": next(values), "sc_x": 0.0, "sc_y": 0.0, "as_x": 1.0, "as_y": 1.0, "gamma": 1.0, "nodes": 1, "elements": 1})
    with pytest.raises(Exception, match="convergence"):
        adapter.rectangle_warping(RectangleSectionInput(width_mm=50, height_mm=100, mesh_size_mm2=20))
