import pytest
from pydantic import ValidationError

from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.yagi_el_reference import (
    EL_AXIS_HEIGHT_PARAMETRIC,
    YagiELKinematicReference,
    create_yagi_el_reference,
)


def _layout():
    from mechcad_harness.yagi_collision_layout import synthesize_yagi_collision_layout
    from tests.unit.test_m7b2c_collision_layout import _carrier, _requirements

    return synthesize_yagi_collision_layout(
        _requirements(),
        _carrier(),
        ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    ).spec


def test_yagi_el_reference_is_strict_parametric_and_hashes_deterministically():
    layout = _layout()

    reference = create_yagi_el_reference(layout)

    assert reference.el_axis_height_range_mm == (180.0, 300.0)
    assert reference.selected_axis_height_mm is None
    assert reference.reference_status == EL_AXIS_HEIGHT_PARAMETRIC
    assert reference.reference_hash == create_yagi_el_reference(layout).reference_hash
    assert create_yagi_el_reference(layout.model_copy(update={"authority_hash": "sha256:changed"})).reference_hash != reference.reference_hash


def test_yagi_el_reference_rejects_extras_and_selected_height():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        YagiELKinematicReference(source_layout_hash="sha256:layout", motor_position_mm=1)
    with pytest.raises(ValidationError):
        YagiELKinematicReference(source_layout_hash="sha256:layout", selected_axis_height_mm=180)


def test_yagi_el_reference_excludes_mechanical_fields_and_preserves_axis_validation():
    reference = create_yagi_el_reference(_layout())

    for field_name in (
        "motor_position_mm",
        "gearbox",
        "bearing",
        "bracket",
        "riser",
        "load",
        "wind_data",
        "material",
        "manufacturing_dimensions",
        "structural_value",
    ):
        assert not hasattr(reference, field_name)

    with pytest.raises(ValueError, match="non-zero"):
        RevoluteAxis(
            origin_x_mm=0,
            origin_y_mm=0,
            origin_z_mm=0,
            direction_x=0,
            direction_y=0,
            direction_z=0,
            frame_id="yagi_el_reference",
        )
