from __future__ import annotations

import pytest

from mechcad_harness.candidates.models import (
    GeneratedRotationalInterfaceAxisSource,
    GeneratedReferenceFrameAxisSource,
    MechanicalConnection,
    MechanicalConnectionKind,
    PhysicalAxisOwnerEndpoint,
    PhysicalJointMotionMode,
    PhysicalRevoluteJointBinding,
    PhysicalRigidBodyBinding,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    SuppliedRotationalInterfaceAxisSource,
    SuppliedReferenceFrameAxisSource,
    ConnectionMeaning,
)
from mechcad_harness.models import GeneratedPlacementDerivation
from mechcad_harness.models import (
    CanonicalAcceptedDesignChoice,
    CanonicalPhysicalComponent,
    CanonicalPhysicalComponentRole,
    CanonicalPlacement,
    CanonicalPlacementOrigin,
    CanonicalDesignChoiceOrigin,
)
from mechcad_harness.models.physical_mechanism import (
    CanonicalConnectionMeaning,
    CanonicalMechanicalConnection,
    CanonicalMechanicalConnectionKind,
    CanonicalGeneratedRotationalInterfaceAxisSource,
    CanonicalSuppliedRotationalInterfaceAxisSource,
    CanonicalPhysicalMechanism,
)
from mechcad_harness.candidates.promotion import CandidatePromotionCompiler
from mechcad_harness.candidates import multi_joint_m10_bridge as bridge

from test_m13_2_candidate_cad_integration import (
    _candidate,
    _direct,
    _mixed_fixture,
    _selection_input,
    _shaft_spec,
    _state,
)
from test_m13_geometry_materialization import _frame_for_source
from mechcad_harness.candidates.models import ComponentSpecificationSnapshot
from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.models.supplied_component_interface import SuppliedInterfaceEvidenceOrigin
from mechcad_harness.models import RectangularFrameMemberSpecification


HASH = "sha256:" + "a" * 64


def _joint(**overrides):
    values = {
        "physical_joint_id": "joint-a",
        "parent_physical_body_id": "body-root",
        "child_physical_body_id": "body-a",
        "connection_id": "connection-a",
        "parent_physical_instance_id": "root-instance",
        "parent_interface_id": "root-interface",
        "child_physical_instance_id": "child-instance",
        "child_interface_id": "child-interface",
        "axis_source": SuppliedRotationalInterfaceAxisSource(
            source_physical_instance_id="root-instance",
            interface_id="root-interface",
            interface_hash=HASH,
            geometry_reference_hash=HASH,
            specification_hash=HASH,
        ),
        "axis_owner_endpoint": PhysicalAxisOwnerEndpoint.PARENT,
        "axis_sign": 1,
        "motion_mode": PhysicalJointMotionMode.BOUNDED,
        "min_angle_deg": 0.0,
        "max_angle_deg": 360.0,
        "zero_reference_semantics": "accepted-semantic-home@1",
    }
    return PhysicalRevoluteJointBinding(**(values | overrides))


def _components():
    return (
        PhysicalComponentInstance(
            instance_id="root-instance",
            specification_hash=HASH,
            role=PhysicalComponentRole.ACTUATOR,
            interfaces=("root-interface",),
        ),
        PhysicalComponentInstance(
            instance_id="child-instance",
            specification_hash=HASH,
            role=PhysicalComponentRole.DRIVEN_BODY,
            interfaces=("child-interface",),
        ),
    )


def _connection(**overrides):
    values = {
        "connection_id": "connection-a",
        "kind": MechanicalConnectionKind.ROTATIONAL_DRIVE,
        "from_instance_id": "root-instance",
        "from_interface_id": "root-interface",
        "to_instance_id": "child-instance",
        "to_interface_id": "child-interface",
        "meanings": (ConnectionMeaning.KINEMATIC_REALIZATION_INTENT,),
    }
    return MechanicalConnection(**(values | overrides))


def test_candidate_resolvers_consume_supplied_and_generated_authority_and_replay_placement(
    tmp_path,
):
    _, candidate, _, _, specifications, _ = _mixed_fixture(tmp_path)
    motor, shaft, _ = specifications
    supplied = SuppliedRotationalInterfaceAxisSource(
        source_physical_instance_id="motor-a",
        interface_id="output-shaft",
        interface_hash=motor.supplied_interface_definitions[0].interface_hash,
        geometry_reference_hash=motor.geometry_source.reference_hash,
        specification_hash=motor.specification_hash,
    )
    generated_interface = shaft.generated_part.interfaces[0]
    generated = GeneratedRotationalInterfaceAxisSource(
        source_physical_instance_id="shaft-a",
        interface_id=generated_interface.interface_id,
        interface_hash=generated_interface.interface_hash,
        generated_specification_hash=shaft.specification_hash,
    )
    generated_frame = GeneratedReferenceFrameAxisSource(
        source_physical_instance_id="shaft-a",
        frame_id=shaft.generated_part.reference_frames[0].frame_id,
        frame_hash=shaft.generated_part.reference_frames[0].frame_hash,
        generated_specification_hash=shaft.specification_hash,
    )

    assert bridge.resolve_candidate_axis_source(candidate, supplied).interface_id == "output-shaft"
    assert bridge.resolve_candidate_axis_source(candidate, generated).interface_id == generated.interface_id
    assert bridge.resolve_candidate_axis_source(candidate, generated_frame).frame_id == generated_frame.frame_id

    derivation = GeneratedPlacementDerivation(
        derivation_id="place-shaft",
        rule_id="coaxial-generated-placement@1",
        source_physical_instance_id="motor-a",
        source_interface_ref={
            "interface_id": "output-shaft",
            "interface_hash": supplied.interface_hash,
        },
        source_placement_ref={"kind": "design_variable_placement"},
        target_physical_instance_id="shaft-a",
        target_generated_interface_ref={
            "interface_id": generated_interface.interface_id,
            "interface_hash": generated_interface.interface_hash,
        },
        inputs=(),
    )
    placement = bridge.resolve_candidate_placement(candidate, "shaft-a", (derivation,))
    assert (placement.x_mm, placement.y_mm, placement.z_mm) == (11.0, 22.0, 33.0)


def test_candidate_supplied_source_rejects_stale_specification_geometry_and_inferred_authority(
    tmp_path,
):
    _, candidate, _, _, specifications, _ = _mixed_fixture(tmp_path)
    motor = specifications[0]
    source = SuppliedRotationalInterfaceAxisSource(
        source_physical_instance_id="motor-a",
        interface_id="output-shaft",
        interface_hash=motor.supplied_interface_definitions[0].interface_hash,
        geometry_reference_hash=motor.geometry_source.reference_hash,
        specification_hash=motor.specification_hash,
    )
    with pytest.raises(ValueError, match="specification"):
        bridge.resolve_candidate_axis_source(
            candidate,
            SuppliedRotationalInterfaceAxisSource(
                source_physical_instance_id=source.source_physical_instance_id,
                interface_id=source.interface_id,
                interface_hash=source.interface_hash,
                geometry_reference_hash=source.geometry_reference_hash,
                specification_hash=HASH,
            ),
        )
    with pytest.raises(ValueError, match="geometry"):
        bridge.resolve_candidate_axis_source(
            candidate,
            SuppliedRotationalInterfaceAxisSource(
                source_physical_instance_id=source.source_physical_instance_id,
                interface_id=source.interface_id,
                interface_hash=source.interface_hash,
                geometry_reference_hash=HASH,
                specification_hash=source.specification_hash,
            ),
        )


def test_canonical_resolvers_use_projected_authority_and_canonical_placement_replay(tmp_path):
    _, candidate, _, _, specifications, _ = _mixed_fixture(tmp_path)
    canonical_specifications = tuple(
        CandidatePromotionCompiler._canonical_specification(specification)
        for specification in specifications
    )
    canonical_components = tuple(
        CanonicalPhysicalComponent(
            instance_id=component.instance_id,
            specification_hash=next(
                specification.specification_hash
                for specification in canonical_specifications
                if specification.source_identity
                == next(
                    source.source_identity
                    for source in specifications
                    if source.specification_hash == component.specification_hash
                )
            ),
            role=CanonicalPhysicalComponentRole(component.role.value),
            interfaces=component.interfaces,
        )
        for component in candidate.realization.components
    )
    choices = tuple(
        CanonicalAcceptedDesignChoice(
            key=f"motor-a.placement.{axis}",
            value=value,
            origin=CanonicalDesignChoiceOrigin.CANDIDATE_LOCAL_CHOICE,
            provenance="test-choice",
            source_identities=(f"choice:{axis}",),
        )
        for axis, value in (("x_mm", 10.0), ("y_mm", 20.0), ("z_mm", 30.0))
    )
    placement = CanonicalPlacement(
        placement_id="motor-a:placement",
        instance_id="motor-a",
        origin=CanonicalPlacementOrigin.ACCEPTED_DESIGN_CHOICE,
        input_identities=tuple(
            identity for choice in choices for identity in choice.source_identities
        ),
        relation="accepted-design-variable-placement@1",
        x_mm=10.0,
        y_mm=20.0,
        z_mm=30.0,
    )
    mechanism = CanonicalPhysicalMechanism(
        schema_version="canonical-physical-mechanism@2",
        id="canonical-mechanism",
        name="Canonical mechanism",
        component_specifications=canonical_specifications,
        components=canonical_components,
        accepted_design_choices=choices,
        placements=(placement,),
    )
    motor, shaft, _ = specifications
    canonical_motor = next(
        component for component in canonical_components if component.instance_id == "motor-a"
    )
    canonical_shaft = next(
        component for component in canonical_components if component.instance_id == "shaft-a"
    )
    supplied = CanonicalSuppliedRotationalInterfaceAxisSource(
        source_physical_instance_id="motor-a",
        interface_id="output-shaft",
        interface_hash=motor.supplied_interface_definitions[0].interface_hash,
        geometry_reference_hash=motor.geometry_source.reference_hash,
        specification_hash=canonical_motor.specification_hash,
    )
    generated_interface = shaft.generated_part.interfaces[0]
    generated = CanonicalGeneratedRotationalInterfaceAxisSource(
        source_physical_instance_id="shaft-a",
        interface_id=generated_interface.interface_id,
        interface_hash=generated_interface.interface_hash,
        generated_specification_hash=canonical_shaft.specification_hash,
    )

    assert bridge.resolve_canonical_axis_source(mechanism, supplied).interface_id == "output-shaft"
    assert bridge.resolve_canonical_axis_source(mechanism, generated).interface_id == generated.interface_id
    resolved = bridge.resolve_canonical_placement(mechanism, "motor-a")
    assert (resolved.x_mm, resolved.y_mm, resolved.z_mm) == (10.0, 20.0, 30.0)


def test_candidate_supplied_frame_source_is_resolved_from_exact_active_geometry_authority(tmp_path):
    _, _, _, _, specifications, _ = _mixed_fixture(tmp_path)
    motor = specifications[0]
    definition = motor.supplied_interface_definitions[0]
    frame = _frame_for_source(definition.geometry)
    shaft_payload = definition.shaft.model_dump(mode="json")
    shaft_payload.update(reference_frame_id=frame.frame_id, interface_hash="pending")
    definition_payload = definition.model_dump(mode="json")
    definition_payload.update(
        shaft=shaft_payload,
        interface_hash="pending",
    )
    definition = type(definition).model_validate(definition_payload)
    geometry = motor.geometry_source
    assert geometry is not None
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="shaft",
        source_identity="supplied:shaft",
        geometry_source=geometry,
        interfaces=(definition.interface_id,),
        supplied_reference_frames=(frame,),
        supplied_interface_definitions=(definition,),
    )
    candidate, _, _ = _candidate(_state(), specification, ("shaft-a",))
    source = SuppliedReferenceFrameAxisSource(
        source_physical_instance_id="shaft-a",
        frame_id=frame.frame_id,
        frame_hash=frame.frame_hash,
        geometry_reference_hash=geometry.reference_hash,
        specification_hash=specification.specification_hash,
    )

    assert bridge.resolve_candidate_axis_source(candidate, source).frame_id == frame.frame_id


def test_candidate_supplied_frame_source_requires_m13_authoritative_consumption(tmp_path):
    _, _, _, _, specifications, _ = _mixed_fixture(tmp_path)
    motor = specifications[0]
    original = motor.supplied_interface_definitions[0]
    frame = _frame_for_source(original.geometry)
    shaft_payload = original.shaft.model_dump(mode="json")
    shaft_payload.update(reference_frame_id=frame.frame_id, interface_hash="pending")
    fact = shaft_payload["axis_direction"]
    fact["evidence"][0]["evidence_origin"] = SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED
    fact["evidence"][0]["geometry_reference_hash"] = original.geometry_reference_hash
    fact["evidence"][0]["evidence_hash"] = "pending"
    fact["accepted_evidence_id"] = None
    fact["fact_hash"] = "pending"
    shaft_payload["axis_direction"] = fact
    definition_payload = original.model_dump(mode="json")
    definition_payload.update(shaft=shaft_payload, interface_hash="pending")
    inferred = type(original).model_validate(definition_payload)
    geometry = motor.geometry_source
    assert geometry is not None
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="supplied:frame-gate",
        geometry_source=geometry,
        interfaces=(inferred.interface_id,),
        supplied_reference_frames=(frame,),
        supplied_interface_definitions=(inferred,),
    )
    candidate, _, _ = _candidate(_state(), specification, ("motor-a",))
    source = SuppliedReferenceFrameAxisSource(
        source_physical_instance_id="motor-a",
        frame_id=frame.frame_id,
        frame_hash=frame.frame_hash,
        geometry_reference_hash=geometry.reference_hash,
        specification_hash=specification.specification_hash,
    )

    with pytest.raises(ValueError, match="accepted evidence"):
        bridge.resolve_candidate_axis_source(candidate, source)


def test_candidate_supplied_axis_rejects_inferred_accepted_evidence(tmp_path):
    _, _, _, _, specifications, _ = _mixed_fixture(tmp_path)
    motor = specifications[0]
    definition = motor.supplied_interface_definitions[0]
    payload = definition.model_dump(mode="json")
    fact = payload["shaft"]["axis_direction"]
    fact["evidence"][0]["evidence_origin"] = SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED
    fact["evidence"][0]["geometry_reference_hash"] = definition.geometry_reference_hash
    fact["evidence"][0]["evidence_hash"] = "pending"
    fact["accepted_evidence_id"] = None
    fact["fact_hash"] = "pending"
    payload["shaft"]["axis_direction"] = fact
    payload["shaft"]["interface_hash"] = "pending"
    payload["interface_hash"] = "pending"
    inferred = type(definition).model_validate(payload)
    geometry = motor.geometry_source
    assert geometry is not None
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="supplied:inferred-motor",
        geometry_source=geometry,
        interfaces=(inferred.interface_id,),
        supplied_interface_definitions=(inferred,),
    )
    candidate, _, _ = _candidate(_state(), specification, ("motor-a",))
    source = SuppliedRotationalInterfaceAxisSource(
        source_physical_instance_id="motor-a",
        interface_id=inferred.interface_id,
        interface_hash=inferred.interface_hash,
        geometry_reference_hash=geometry.reference_hash,
        specification_hash=specification.specification_hash,
    )

    with pytest.raises(ValueError, match="accepted evidence"):
        bridge.resolve_candidate_axis_source(candidate, source)


def test_revolute_connection_requires_exact_directed_kind_meaning_and_endpoints():
    joint = _joint()
    components = _components()
    assert bridge.validate_physical_revolute_connections((joint,), (_connection(),), components)["joint-a"]

    for connection in (
        _connection(from_instance_id="child-instance", to_instance_id="root-instance"),
        _connection(kind=MechanicalConnectionKind.COAXIAL_CONNECTION),
        _connection(meanings=()),
        _connection(to_interface_id="other-interface"),
    ):
        with pytest.raises(ValueError):
            bridge.validate_physical_revolute_connections((joint,), (connection,), components)


def test_revolute_connection_rejects_mixed_candidate_and_canonical_layers():
    canonical_connection = CanonicalMechanicalConnection(
        connection_id="connection-a",
        kind=CanonicalMechanicalConnectionKind.ROTATIONAL_DRIVE,
        from_instance_id="root-instance",
        from_interface_id="root-interface",
        to_instance_id="child-instance",
        to_interface_id="child-interface",
        meanings=(CanonicalConnectionMeaning.KINEMATIC_REALIZATION_INTENT,),
    )

    with pytest.raises(ValueError, match="must not mix"):
        bridge.validate_physical_revolute_connections(
            (_joint(),), (canonical_connection,), _components()
        )


def test_kinematic_tree_rejects_cycles_disconnected_components_and_multiple_parents():
    bodies = (
        PhysicalRigidBodyBinding(
            physical_body_id="body-root",
            member_physical_instance_ids=("root-instance",),
            reference_physical_instance_id="root-instance",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="body-a",
            member_physical_instance_ids=("child-instance",),
            reference_physical_instance_id="child-instance",
        ),
    )
    assert bridge.validate_physical_kinematic_tree(bodies, (_joint(),), "body-root") == {
        "body-a": "body-root"
    }

    with pytest.raises(ValueError, match="cycle"):
        bridge.validate_physical_kinematic_tree(
            bodies,
            (
                _joint(),
                    _joint(
                        physical_joint_id="joint-back",
                        parent_physical_body_id="body-a",
                        child_physical_body_id="body-root",
                        parent_physical_instance_id="child-instance",
                        child_physical_instance_id="root-instance",
                    ),
            ),
            "body-root",
        )
    with pytest.raises(ValueError, match="disconnected"):
        bridge.validate_physical_kinematic_tree(
            bodies + (
                PhysicalRigidBodyBinding(
                    physical_body_id="body-disconnected",
                    member_physical_instance_ids=("other-instance",),
                    reference_physical_instance_id="other-instance",
                ),
            ),
            (_joint(),),
            "body-root",
        )
    with pytest.raises(ValueError, match="parent"):
        bridge.validate_physical_kinematic_tree(
            bodies,
            (
                _joint(),
                _joint(
                    physical_joint_id="joint-second",
                    connection_id="connection-second",
                    parent_physical_body_id="body-root",
                    child_physical_body_id="body-a",
                ),
            ),
            "body-root",
        )


def test_kinematic_tree_rejects_joint_endpoint_without_matching_body_owner():
    bodies = (
        PhysicalRigidBodyBinding(
            physical_body_id="body-root",
            member_physical_instance_ids=("root-instance",),
            reference_physical_instance_id="root-instance",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="body-a",
            member_physical_instance_ids=("other-instance",),
            reference_physical_instance_id="other-instance",
        ),
    )

    with pytest.raises(ValueError, match="endpoint.*owner"):
        bridge.validate_physical_kinematic_tree(bodies, (_joint(),), "body-root")


def test_kinematic_tree_accepts_a_single_root_without_joints():
    body = PhysicalRigidBodyBinding(
        physical_body_id="body-root",
        member_physical_instance_ids=("root-instance",),
        reference_physical_instance_id="root-instance",
    )

    assert bridge.validate_physical_kinematic_tree((body,), (), "body-root") == {}


def test_generated_rotational_source_rejects_generated_attachment_face(tmp_path):
    frame = RectangularFrameMemberSpecification(
        generated_part_id="frame-definition",
        length_mm=60.0,
        width_mm=20.0,
        height_mm=10.0,
        inputs=(
            _selection_input("length", 60.0),
            _selection_input("width", 20.0),
            _selection_input("height", 10.0),
        ),
        field_bindings=(
            _direct("frame.length_mm", "length", 60.0),
            _direct("frame.width_mm", "width", 20.0),
            _direct("frame.height_mm", "height", 10.0),
        ),
    )
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@3",
        component_type="frame",
        source_identity="generated:frame-definition",
        generated_part=frame,
        interfaces=frame.active_interface_ids,
    )
    candidate, _, _ = _candidate(_state(), specification, ("frame-a",))
    interface = frame.interfaces[0]
    source = GeneratedRotationalInterfaceAxisSource(
        source_physical_instance_id="frame-a",
        interface_id=interface.interface_id,
        interface_hash=interface.interface_hash,
        generated_specification_hash=specification.specification_hash,
    )

    with pytest.raises(ValueError, match="rotational"):
        bridge.resolve_candidate_axis_source(candidate, source)


def test_generated_candidate_placement_requires_derivation_instead_of_raw_variables():
    generated = _shaft_spec()
    candidate, _, _ = _candidate(_state(), generated, ("shaft-a",))
    payload = candidate.model_dump(mode="json")
    payload["design_variables"] += [
        {"name": "shaft-a.placement.x_mm", "value": 1.0},
        {"name": "shaft-a.placement.y_mm", "value": 2.0},
        {"name": "shaft-a.placement.z_mm", "value": 3.0},
    ]
    payload["candidate_hash"] = "pending"
    candidate = type(candidate).model_validate(payload)

    with pytest.raises(ValueError, match="derivation"):
        bridge.resolve_candidate_placement(candidate, "shaft-a")


@pytest.mark.parametrize(
    ("mode", "minimum", "maximum"),
    [
        (PhysicalJointMotionMode.BOUNDED, 0.0, 360.0),
        (PhysicalJointMotionMode.BOUNDED, 0.0, 1080.0),
        (PhysicalJointMotionMode.CONTINUOUS, None, None),
    ],
)
def test_joint_limits_preserve_bounded_single_and_multi_turn_and_continuous_semantics(
    mode, minimum, maximum
):
    joint = _joint(motion_mode=mode, min_angle_deg=minimum, max_angle_deg=maximum)
    assert (joint.motion_mode, joint.min_angle_deg, joint.max_angle_deg) == (
        mode,
        minimum,
        maximum,
    )
