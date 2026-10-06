"""S2 source-authority contract for Rotator V2 Epic 01."""

from __future__ import annotations

def test_s2_binds_two_motor_instances_to_one_source_bound_trusted_artifact(tmp_path) -> None:
    from projects.rotator_v2.epic_01.candidate_definition import (
        build_s2_candidate_fixture,
    )

    fixture = build_s2_candidate_fixture(tmp_path)
    artifact = fixture.artifact

    assert artifact.artifact_type.value == "step"
    assert (tmp_path / artifact.relative_path).is_file()
    assert artifact.bound_revision == fixture.source_binding.source_revision
    assert artifact.bound_state_hash == fixture.source_binding.source_state_hash

    assert fixture.candidate.source_binding == fixture.source_binding
    assert len(fixture.candidate.component_specifications) == 1
    motor = fixture.candidate.component_specifications[0]
    assert motor.schema_version == "component-specification@2"
    assert motor.geometry_source is not None
    assert motor.geometry_source.artifact_id == artifact.artifact_id
    assert motor.geometry_source.artifact_hash == artifact.sha256
    assert motor.geometry_source.coordinate_system_id == "5840-31ZY-normalized-mm"
    assert len(motor.supplied_reference_frames) == 1
    output_frame = motor.supplied_reference_frames[0]
    assert output_frame.frame_id == "output-frame"
    assert output_frame.origin.accepted_evidence_id == "output-frame-origin-confirmed"
    assert output_frame.orientation.accepted_evidence_id == "output-frame-orientation-confirmed"
    assert {component.instance_id for component in fixture.candidate.realization.components} == {
        "motor_AZ",
        "motor_EL",
    }

    assert set(fixture.motor_target_transforms) == {
        "motor_AZ",
        "motor_EL",
    }
    assert fixture.motor_target_transforms["motor_AZ"].model_dump() == {
        "x_mm": 66.0,
        "y_mm": 0.0,
        "z_mm": 220.0,
        "rotation_quaternion": (1.0, 0.0, 0.0, 0.0),
    }
    assert fixture.motor_target_transforms["motor_EL"].model_dump() == {
        "x_mm": 66.0,
        "y_mm": 135.0,
        "z_mm": 520.0,
        "rotation_quaternion": (0.7071067811865476, -0.7071067811865475, 0.0, 0.0),
    }

    assert fixture.source_facts == {
        "rated_voltage_V": 24.0,
        "internal_reduction_ratio": 1000.0,
        "rated_load_torque_Nm": 9.80665,
    }
    assert fixture.operating_limits == {
        "rated_load_torque_Nm": 9.80665,
        "peak_short_term_allowable_torque_Nm": None,
        "stall_torque_Nm": 39.2266,
        "stall_torque_allowed_for_normal_sizing": False,
    }
