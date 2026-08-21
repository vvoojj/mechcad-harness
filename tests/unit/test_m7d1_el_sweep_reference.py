import pytest

from mechcad_harness.kinematic_sweep import (
    CadKinematicCollisionPairResult,
    CadKinematicSweepResult,
    CadKinematicSweepSample,
    CollisionClassification,
    RevoluteAxis,
)
from mechcad_harness.yagi_el_reference import create_yagi_el_sweep_reference


def _layout():
    from mechcad_harness.yagi_collision_layout import synthesize_yagi_collision_layout
    from tests.unit.test_m7b2c_collision_layout import _carrier, _requirements

    return synthesize_yagi_collision_layout(
        _requirements(),
        _carrier(),
        ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    ).spec


def test_yagi_el_sweep_reference_preserves_layout_axis_angles_and_instance_roles():
    layout = _layout()
    axis = RevoluteAxis(
        origin_x_mm=0,
        origin_y_mm=0,
        origin_z_mm=0,
        direction_x=0,
        direction_y=1,
        direction_z=0,
        frame_id="yagi_el_reference",
    )

    request = create_yagi_el_sweep_reference(
        layout,
        source_assembly_id="assembly",
        source_assembly_hash="sha256:assembly",
        axis=axis,
        sample_angles_deg=(-45, 0, 45, 90, 180, 360),
        moving_instance_ids=("ANTENNA_ENVELOPE_0400",),
        stationary_instance_ids=("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )

    assert request.source_assembly_id == "assembly"
    assert request.source_assembly_hash == "sha256:assembly"
    assert request.axis == axis
    assert request.sample_angles_deg == (-45.0, 0.0, 45.0, 90.0, 180.0, 360.0)
    assert request.moving_instance_ids == ("ANTENNA_ENVELOPE_0400",)
    assert request.stationary_instance_ids == ("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200")


def test_yagi_el_sweep_reference_remains_discrete_only():
    layout = _layout()
    request = create_yagi_el_sweep_reference(
        layout,
        source_assembly_id="assembly",
        source_assembly_hash="sha256:assembly",
        axis=RevoluteAxis(
            origin_x_mm=0,
            origin_y_mm=0,
            origin_z_mm=0,
            direction_x=0,
            direction_y=1,
            direction_z=0,
            frame_id="yagi_el_reference",
        ),
        sample_angles_deg=(0,),
        moving_instance_ids=("ANTENNA_ENVELOPE_0400",),
        stationary_instance_ids=("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )
    sample = CadKinematicSweepSample(
        angle_deg=0,
        transformed_assembly_hash="sha256:sample",
        pair_results=(
            CadKinematicCollisionPairResult(
                moving_instance_id="ANTENNA_ENVELOPE_0400",
                stationary_instance_id="ANTENNA_ENVELOPE_0600",
                interference_volume_mm3=0,
                exact_distance_mm=1,
                classification=CollisionClassification.POSITIVE_CLEARANCE,
            ),
        ),
        maximum_interference_volume_mm3=0,
        minimum_exact_distance_mm=1,
        classification=CollisionClassification.POSITIVE_CLEARANCE,
    )

    assert CadKinematicSweepResult.from_samples(request, (sample,)).continuous_sweep_verified is False


def test_yagi_el_sweep_reference_requires_explicit_assembly_identity():
    with pytest.raises(TypeError):
        create_yagi_el_sweep_reference(
            _layout(),
            axis=RevoluteAxis(
                origin_x_mm=0,
                origin_y_mm=0,
                origin_z_mm=0,
                direction_x=0,
                direction_y=1,
                direction_z=0,
                frame_id="yagi_el_reference",
            ),
            sample_angles_deg=(0,),
            moving_instance_ids=("moving",),
            stationary_instance_ids=("stationary",),
        )
