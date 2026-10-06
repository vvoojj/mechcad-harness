"""S3 physical-mechanism contract for Rotator V2 Epic 01."""

from __future__ import annotations


def test_s3_freezes_candidate_01_physical_mechanism_without_cad_lowering() -> None:
    from projects.rotator_v2.epic_01.candidate_definition import (
        build_s3_physical_mechanism,
    )

    mechanism = build_s3_physical_mechanism()

    bodies = {
        binding.physical_body_id: binding.member_physical_instance_ids
        for binding in mechanism.physical_realization.physical_rigid_body_bindings
    }
    assert bodies == {
        "base_body": (
            "az_base", "az_carrier", "az_keep_out", "az_motor_mount", "az_pinion",
            "az_support_A", "az_support_B", "motor_AZ",
        ),
        "az_rotating_body": (
            "az_deck", "az_driven_gear", "az_hub", "az_shaft", "el_edge_bridge",
            "el_fork", "el_motor_mount", "el_pinion", "el_support_A", "el_support_B",
            "motor_EL",
        ),
        "el_payload_body": (
            "antenna_envelopes", "carrier_attachment_boss", "el_driven_gear", "el_hub",
            "el_shaft", "rail_and_pad_carrier",
        ),
    }
    assert mechanism.generated_part_specifications["az_shaft"] == {
        "outer_diameter_mm": 60.0,
        "clear_bore_mm": 40.0,
        "length_mm": 220.0,
        "axial_extent": "Z=30..250",
    }
    assert mechanism.generated_part_specifications["el_shaft"] == {
        "outer_diameter_mm": 50.0,
        "length_mm": 300.0,
        "axial_extent": "Y=-150..150",
    }
    assert mechanism.geometry_fidelity["az_keep_out"] == (
        "DECLARED_BOUNDED_COLLISION_REPRESENTATION"
    )

    assert mechanism.frozen_topology == {
        "az_carrier_retained_posts_xy": (
            ("-60..-40", "-60..-40"),
            ("-60..-40", "40..60"),
            ("40..60", "-60..-40"),
        ),
        "az_carrier_posts_z": "20..220",
        "station_a": "X/Y=-60..60,Z=50..70 minus D50",
        "station_b_left_rail": "X=-60..-35,Y=-60..60,Z=170..190",
        "az_corridor_diameter_mm": 40.0,
        "az_support_centers_z_mm": (60.0, 180.0),
        "station_b_support_overlap_mm3": 2616.094617,
        "positive_y_el_arm": "X=-70..40,Y=90..110,Z=220..520",
        "positive_y_arm_support_overlap_mm3": 30630.528373,
    }
    assert mechanism.no_free_placement_dof_audit == "ALL=YES"
    assert mechanism.static_corridor_invariants == {
        "az_base": True,
        "az_carrier": True,
        "az_support_A": True,
        "az_support_B": True,
        "az_motor_mount": True,
        "motor_AZ": True,
        "az_pinion": True,
    }



def test_s3_uses_m13_v2_physical_bindings_with_non_authoritative_intervals() -> None:
    from mechcad_harness.models import PhysicalPairClassification
    from projects.rotator_v2.epic_01.candidate_definition import (
        build_s3_physical_mechanism,
    )

    mechanism = build_s3_physical_mechanism()
    realization = mechanism.physical_realization

    assert realization.schema_version == "physical-mechanism-realization@2"
    assert [binding.physical_body_id for binding in realization.physical_rigid_body_bindings] == [
        "az_rotating_body",
        "base_body",
        "el_payload_body",
    ]
    assert realization.kinematic_root_physical_body_id == "base_body"
    assert {
        binding.physical_joint_id: binding
        for binding in realization.physical_revolute_joint_bindings
    }.keys() == {"joint_az", "joint_el"}

    az_joint = next(
        binding
        for binding in realization.physical_revolute_joint_bindings
        if binding.physical_joint_id == "joint_az"
    )
    assert az_joint.parent_physical_body_id == "base_body"
    assert az_joint.child_physical_body_id == "az_rotating_body"
    assert az_joint.motion_mode.value == "continuous"
    assert az_joint.min_angle_deg is None
    assert az_joint.max_angle_deg is None
    assert az_joint.axis_source.source_physical_instance_id == "az_shaft"
    assert az_joint.axis_sign == 1

    assert mechanism.requested_evaluation_intervals_deg == {
        "joint_az": (0.0, 360.0),
        "joint_el": (0.0, 360.0),
    }
    assert "requested_evaluation_interval_deg" not in az_joint.model_dump(mode="json")
    assert {
        component.instance_id: component.role.value
        for component in realization.components
        if component.instance_id in {"az_motor_mount", "el_motor_mount"}
    } == {
        "az_motor_mount": "mount_or_support",
        "el_motor_mount": "mount_or_support",
    }

    pairs = {
        (binding.first_physical_instance_id, binding.second_physical_instance_id): binding
        for binding in realization.physical_pair_classification_bindings
    }
    assert len(pairs) == 300
    assert pairs[("az_shaft", "az_support_A")].classification is (
        PhysicalPairClassification.INTENDED_CONTACT_EXCLUDED
    )
    assert pairs[("az_base", "az_keep_out")].classification is (
        PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED
    )
    assert pairs[("az_keep_out", "el_shaft")].classification is (
        PhysicalPairClassification.CHECK_CLEARANCE
    )
