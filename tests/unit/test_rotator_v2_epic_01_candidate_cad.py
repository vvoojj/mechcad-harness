"""S4 CAD mapping contract for Rotator V2 Epic 01."""

from __future__ import annotations


def test_s4_candidate_inventory_equals_frozen_s3_physical_inventory(tmp_path) -> None:
    from projects.rotator_v2.epic_01.candidate_definition import (
        build_s2_candidate_fixture,
        build_s3_physical_mechanism,
    )

    fixture = build_s2_candidate_fixture(tmp_path)
    mechanism = build_s3_physical_mechanism()

    expected_ids = {
        member_id
        for body in mechanism.physical_realization.physical_rigid_body_bindings
        for member_id in body.member_physical_instance_ids
    }
    assert {
        component.instance_id for component in fixture.candidate.realization.components
    } == expected_ids
