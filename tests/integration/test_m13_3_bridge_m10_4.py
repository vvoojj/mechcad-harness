from __future__ import annotations

import os

import pytest

from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.cad_assembly import assembly_hash
from mechcad_harness.multi_joint_continuous_path import (
    MultiJointContinuousPathRequestV2,
    MultiJointPath,
)
from mechcad_harness.multi_joint_kinematics import kinematic_model_hash
from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair

from test_m13_3p_live_grouped_body_freecad import (
    FREECAD_CANDIDATE,
    _application,
    _configuration,
    _fixture,
)


FREECAD_AVAILABLE = discover_freecad().available


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="real FreeCAD is required")
def test_bridge_generated_v2_inputs_reach_continuous_multi_joint_proof(tmp_path):
    application = _application(tmp_path)
    source = application.load_state()
    assembly, model = _fixture()
    path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(_configuration(model, 0.0, 0.0), _configuration(model, 15.0, 90.0)),
    )

    result = application.prove_continuous_multi_joint_path_clearance_v2(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        path=path,
        exact_pair_scope=(
            ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),
        ),
        required_clearance_mm=0.0,
    )

    expected_request = MultiJointContinuousPathRequestV2(
        schema_version="multi-joint-continuous-path-request@2",
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        path=path,
        exact_pair_scope=(
            ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),
        ),
        required_clearance_mm=0.0,
    )
    assert result.request_hash == expected_request.request_hash
    assert result.source_assembly_hash == expected_request.source_assembly_hash
    assert result.model_hash == kinematic_model_hash(model)
    assert expected_request.exact_pair_scope == (
        ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),
    )
