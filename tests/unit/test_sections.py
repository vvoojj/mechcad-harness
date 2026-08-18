import pytest

from mechcad_harness.sections import (
    CircleSectionInput,
    HollowCircleSectionInput,
    RectangleSectionInput,
    SectionGeometryResult,
)


def test_section_inputs_reject_nonpositive_or_nonfinite_values():
    with pytest.raises(Exception):
        RectangleSectionInput(width_mm=0, height_mm=10, mesh_size_mm2=5)
    with pytest.raises(Exception):
        CircleSectionInput(diameter_mm=float("nan"), discretization_points=32, mesh_size_mm2=5)
    with pytest.raises(Exception):
        CircleSectionInput(diameter_mm=10, discretization_points=3, mesh_size_mm2=5)
    with pytest.raises(Exception):
        HollowCircleSectionInput(outer_diameter_mm=10, wall_thickness_mm=5, discretization_points=32, mesh_size_mm2=5)


def test_section_result_is_json_safe_and_has_no_external_object_fields():
    result = SectionGeometryResult(
        section_type="rectangle",
        area_mm2=5000,
        centroid_x_mm=25,
        centroid_y_mm=50,
        ixx_centroid_mm4=4166666.666666667,
        iyy_centroid_mm4=1041666.666666667,
        ixy_centroid_mm4=0,
        perimeter_mm=300,
        radius_of_gyration_x_mm=28.8675,
        radius_of_gyration_y_mm=14.4338,
        mesh_metadata={"mesh_size_mm2": 5.0},
        backend_provenance=None,
    )
    assert "mesh_metadata" in result.model_dump(mode="json")
