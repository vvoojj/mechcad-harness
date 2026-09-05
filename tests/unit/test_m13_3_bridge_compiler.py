from __future__ import annotations

import hashlib
import itertools
import json

import pytest

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.candidates.cad_realization import CandidateCadRealizationService
from mechcad_harness.candidates.canonical_cad import CanonicalCadRealization
from mechcad_harness.candidates.models import (
    ConnectionMeaning,
    MechanicalConnection,
    MechanicalConnectionKind,
    PhysicalAxisOwnerEndpoint,
    PhysicalJointMotionMode,
    PhysicalMechanismRealization,
    PhysicalPairClassificationBinding,
    PhysicalRevoluteJointBinding,
    PhysicalRigidBodyBinding,
    SuppliedRotationalInterfaceAxisSource,
)
from mechcad_harness.candidates import (
    PhysicalToM10V2Bridge,
    PhysicalToM10V2BridgeCompiler,
    compile_candidate,
    compile_canonical,
    physical_to_m10_bridge_hash,
    physical_to_m10_v2_model_id,
    validate_physical_to_m10_v2_bridge,
)
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    MultiJointCollisionPairEntry,
    MultiJointCollisionPairInventory,
)
from mechcad_harness.models import CanonicalPhysicalMechanism, PhysicalPairClassification, physical_kinematic_root_hash
from mechcad_harness.multi_joint_kinematics import kinematic_model_hash
from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair, exact_pair_scope_hash

from test_m13_2_candidate_cad_integration import _mixed_fixture, _mixed_request


def test_bridge_model_id_uses_only_sorted_stable_physical_topology_ids():
    expected_payload = {
        "schema_version": "physical-to-m10-v2-model-id@1",
        "physical_body_ids": ["body-a", "body-b"],
        "physical_joint_ids": ["joint-a", "joint-b"],
    }
    expected = "physical-to-m10-v2-model@1:" + hashlib.sha256(
        json.dumps(expected_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    assert physical_to_m10_v2_model_id(
        ("body-b", "body-a"), ("joint-b", "joint-a")
    ) == expected


@pytest.mark.parametrize(
    "body_ids",
    [(), "body-a", b"body-a", ("",), ("body-a", "body-a"), (1,), None, 42],
)
def test_bridge_model_id_rejects_malformed_body_id_collections(body_ids):
    with pytest.raises(ValueError):
        physical_to_m10_v2_model_id(body_ids, ())


@pytest.mark.parametrize(
    "joint_ids",
    ["joint-a", b"joint-a", ("",), ("joint-a", "joint-a"), (1,), None, 42],
)
def test_bridge_model_id_rejects_malformed_joint_id_collections(joint_ids):
    with pytest.raises(ValueError):
        physical_to_m10_v2_model_id(("body-a",), joint_ids)


def test_bridge_model_id_allows_empty_joint_collection_but_not_empty_body_collection():
    assert physical_to_m10_v2_model_id(("body-a",), ())
    with pytest.raises(ValueError):
        physical_to_m10_v2_model_id((), ())


def test_bridge_compiler_symbols_are_publicly_exported():
    assert PhysicalToM10V2BridgeCompiler is not None
    assert PhysicalToM10V2Bridge is not None
    assert compile_candidate is not None
    assert compile_canonical is not None
    assert physical_to_m10_bridge_hash is not None


def test_compile_canonical_rejects_candidate_cad_type_and_candidate_rejects_canonical_cad_type(tmp_path):
    candidate, _, realization, bridge = _compiled_candidate_bridge(tmp_path)
    with pytest.raises(ValueError, match="canonical bridge CAD input"):
        compile_canonical(
            CanonicalPhysicalMechanism.model_construct(),
            realization,
        )
    with pytest.raises(ValueError, match="candidate bridge CAD input"):
        compile_candidate(candidate, CanonicalCadRealization.model_construct())


def test_candidate_and_canonical_bridge_model_ids_are_equal_for_identical_topology():
    candidate_model_id = physical_to_m10_v2_model_id(("body-b", "body-a"), ("joint-b", "joint-a"))
    canonical_model_id = physical_to_m10_v2_model_id(("body-a", "body-b"), ("joint-a", "joint-b"))
    assert candidate_model_id == canonical_model_id


def _physical_candidate(candidate, specifications):
    motor, shaft, _ = specifications
    shaft_interface = shaft.generated_part.interfaces[0]
    components = candidate.realization.components
    connection = MechanicalConnection(
        connection_id="physical-drive",
        kind=MechanicalConnectionKind.ROTATIONAL_DRIVE,
        from_instance_id="motor-a",
        from_interface_id="output-shaft",
        to_instance_id="shaft-a",
        to_interface_id=shaft_interface.interface_id,
        meanings=(ConnectionMeaning.KINEMATIC_REALIZATION_INTENT,),
    )
    source = SuppliedRotationalInterfaceAxisSource(
        source_physical_instance_id="motor-a",
        interface_id="output-shaft",
        interface_hash=motor.supplied_interface_definitions[0].interface_hash,
        geometry_reference_hash=motor.geometry_source.reference_hash,
        specification_hash=motor.specification_hash,
    )
    joint = PhysicalRevoluteJointBinding(
        physical_joint_id="physical-joint",
        parent_physical_body_id="physical-root",
        child_physical_body_id="physical-link",
        connection_id=connection.connection_id,
        parent_physical_instance_id="motor-a",
        parent_interface_id="output-shaft",
        child_physical_instance_id="shaft-a",
        child_interface_id=shaft_interface.interface_id,
        axis_source=source,
        axis_owner_endpoint=PhysicalAxisOwnerEndpoint.PARENT,
        axis_sign=1,
        motion_mode=PhysicalJointMotionMode.BOUNDED,
        min_angle_deg=-90.0,
        max_angle_deg=90.0,
        zero_reference_semantics="accepted-semantic-home@1",
    )
    bodies = (
        PhysicalRigidBodyBinding(
            physical_body_id="physical-link",
            member_physical_instance_ids=("hub-a", "shaft-a"),
            reference_physical_instance_id="shaft-a",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="physical-root",
            member_physical_instance_ids=("motor-a",),
            reference_physical_instance_id="motor-a",
        ),
    )
    owners = {
        member: body.physical_body_id
        for body in bodies
        for member in body.member_physical_instance_ids
    }
    pairs = tuple(
        PhysicalPairClassificationBinding(
            first_physical_instance_id=first,
            second_physical_instance_id=second,
            classification=(
                PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED
                if owners[first] == owners[second]
                else PhysicalPairClassification.CHECK_CLEARANCE
            ),
            exclusion_reason=("same rigid body" if owners[first] == owners[second] else None),
        )
        for first, second in itertools.combinations(sorted(owners), 2)
    )
    realization = PhysicalMechanismRealization(
        schema_version="physical-mechanism-realization@2",
        components=components,
        connections=(connection,),
        physical_rigid_body_bindings=bodies,
        physical_revolute_joint_bindings=(joint,),
        kinematic_root_physical_body_id="physical-root",
        kinematic_root_binding_hash=physical_kinematic_root_hash("physical-root"),
        physical_pair_classification_bindings=pairs,
    )
    return type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {"realization": realization.model_dump(mode="json"), "candidate_hash": "pending"}
    )


def test_candidate_compiler_finalizes_model_inventory_scope_and_bridge(tmp_path):
    manager, base_candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(tmp_path)
    candidate = _physical_candidate(base_candidate, specifications)
    request = _mixed_request(candidate, specifications, artifact)
    outcome = CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )
    assert outcome.realization is not None

    bridge = compile_candidate(
        candidate, outcome.realization, request.placement_derivations
    )

    assert bridge.model.model_id == physical_to_m10_v2_model_id(
        bridge.ordered_body_ids, bridge.ordered_joint_ids
    )
    assert bridge.m10_model_hash == kinematic_model_hash(bridge.model)
    assert bridge.inventory_hash == bridge.inventory.inventory_hash
    assert bridge.exact_pair_scope_hash.startswith("sha256:")
    assert bridge.physical_to_m10_bridge_hash == physical_to_m10_bridge_hash(bridge)
    assert PhysicalToM10V2Bridge.model_validate(bridge.model_dump(mode="json")) == bridge


def _compiled_candidate_bridge(tmp_path):
    manager, base_candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(tmp_path)
    candidate = _physical_candidate(base_candidate, specifications)
    request = _mixed_request(candidate, specifications, artifact)
    outcome = CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )
    assert outcome.realization is not None
    return candidate, request, outcome.realization, compile_candidate(
        candidate, outcome.realization, request.placement_derivations
    )


def _compiled_candidate_bridge_with_cad_request(tmp_path):
    manager, base_candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(tmp_path)
    candidate = _physical_candidate(base_candidate, specifications)
    request = _mixed_request(candidate, specifications, artifact)
    outcome = CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )
    assert outcome.realization is not None
    return candidate, request, outcome.realization, compile_candidate(
        candidate, outcome.realization, request.placement_derivations
    )


def test_bridge_model_id_is_unchanged_by_fresh_cad_identity_but_bridge_hash_changes(tmp_path):
    candidate, request, realization, original = _compiled_candidate_bridge(tmp_path)
    mapping_payloads = []
    for mapping in realization.mappings:
        mapping_payloads.append(
            mapping.model_dump(mode="json")
            | {"cad_instance_id": f"fresh-{mapping.cad_instance_id}", "mapping_hash": "pending"}
        )
    instances = tuple(
        CadComponentInstance(
            instance_id=f"fresh-{instance.instance_id}",
            part_id=instance.part_id,
            placement=instance.placement,
        )
        for instance in realization.assembly.instances
    )
    assembly = realization.assembly.model_copy(
        update={"assembly_id": "fresh-assembly", "instances": instances}
    )
    fresh = type(realization).model_validate(
        realization.model_dump(mode="json")
        | {
            "mappings": mapping_payloads,
            "assembly": assembly.model_dump(mode="json"),
            "assembly_hash": assembly_hash(assembly),
            "realization_hash": "pending",
        }
    )

    rebuilt = compile_candidate(candidate, fresh, request.placement_derivations)

    assert rebuilt.model.model_id == original.model.model_id
    assert rebuilt.physical_to_m10_bridge_hash != original.physical_to_m10_bridge_hash


def test_bridge_model_id_changes_for_semantic_body_or_joint_id_changes():
    original = physical_to_m10_v2_model_id(("body-a", "body-b"), ("joint-a",))

    assert physical_to_m10_v2_model_id(("body-a", "body-c"), ("joint-a",)) != original
    assert physical_to_m10_v2_model_id(("body-a", "body-b"), ("joint-b",)) != original


def test_bridge_hash_and_nested_revalidation_reject_forged_m10_inputs(tmp_path):
    _, _, _, bridge = _compiled_candidate_bridge(tmp_path)
    forged_hash = bridge.model_copy(update={"m10_model_hash": "sha256:" + "f" * 64})
    with pytest.raises(ValueError, match="model hash"):
        physical_to_m10_bridge_hash(forged_hash)
    with pytest.raises(ValueError, match="model hash"):
        PhysicalToM10V2Bridge.model_validate(forged_hash.model_dump(mode="json"))

    bad_model = bridge.model.model_copy(update={"evaluator_version": "bad"})
    forged_model = bridge.model_copy(update={"model": bad_model})
    with pytest.raises(ValueError):
        PhysicalToM10V2Bridge.model_validate(forged_model.model_dump(mode="json"))

    bad_body = bridge.model.bodies[0]
    object.__setattr__(bad_body, "body_hash", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="body"):
        PhysicalToM10V2Bridge.model_validate(bridge.model_dump(mode="json"))


def test_bridge_rejects_reduced_scope_even_when_scope_and_bridge_hashes_are_recomputed(tmp_path):
    _, _, _, bridge = _compiled_candidate_bridge(tmp_path)
    reduced_scope = bridge.exact_pair_scope[:1]
    forged_scope = bridge.model_copy(
        update={
            "exact_pair_scope": reduced_scope,
            "exact_pair_scope_hash": exact_pair_scope_hash(reduced_scope),
        }
    )
    bridge_payload = forged_scope.model_dump(mode="json")
    bridge_payload.pop("model")
    bridge_payload.pop("inventory")
    bridge_payload.pop("physical_to_m10_bridge_hash")
    forged_scope = forged_scope.model_copy(
        update={
            "physical_to_m10_bridge_hash": "sha256:"
            + hashlib.sha256(
                json.dumps(bridge_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        }
    )

    with pytest.raises(ValueError, match="trusted CHECK_CLEARANCE scope"):
        PhysicalToM10V2Bridge.model_validate(forged_scope.model_dump(mode="json"))


def test_bridge_rejects_rehashed_inventory_with_substituted_grouping_identity(tmp_path):
    _, _, _, bridge = _compiled_candidate_bridge(tmp_path)
    inventory_payload = bridge.inventory.model_dump(mode="json")
    inventory_payload["physical_body_binding_hashes"] = ["sha256:" + "0" * 64]
    inventory_payload.pop("inventory_hash")
    forged_inventory = MultiJointCollisionPairInventory.model_validate(inventory_payload)
    forged_bridge = bridge.model_copy(
        update={
            "inventory": forged_inventory,
            "inventory_hash": forged_inventory.inventory_hash,
        }
    )
    bridge_payload = forged_bridge.model_dump(mode="json")
    bridge_payload.pop("model")
    bridge_payload.pop("inventory")
    bridge_payload.pop("physical_to_m10_bridge_hash")
    forged_bridge = forged_bridge.model_copy(
        update={
            "physical_to_m10_bridge_hash": "sha256:"
            + hashlib.sha256(
                json.dumps(bridge_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        }
    )

    with pytest.raises(ValueError, match="physical body binding"):
        PhysicalToM10V2Bridge.model_validate(forged_bridge.model_dump(mode="json"))


def test_trusted_bridge_validation_rejects_reclassified_inventory_with_recomputed_hashes(tmp_path):
    candidate, _, realization, bridge = _compiled_candidate_bridge(tmp_path)
    reclassified = next(
        entry
        for entry in bridge.inventory.entries
        if entry.classification is PhysicalPairClassification.CHECK_CLEARANCE
    )
    forged_entries = tuple(
        MultiJointCollisionPairEntry.model_validate(
            entry.model_dump(mode="json")
            | (
                {
                    "classification": "other_explicit_out_of_scope",
                    "exclusion_reason": "forged reclassification",
                }
                if entry is reclassified
                else {}
            )
        )
        for entry in bridge.inventory.entries
    )
    inventory_payload = bridge.inventory.model_dump(mode="json") | {
        "entries": [entry.model_dump(mode="json") for entry in forged_entries]
    }
    inventory_payload.pop("inventory_hash")
    forged_inventory = MultiJointCollisionPairInventory.model_validate(inventory_payload)
    forged_scope = tuple(
        ExactConstituentPair(
            first_instance_id=entry.first_instance_id,
            second_instance_id=entry.second_instance_id,
        )
        for entry in forged_inventory.entries
        if entry.classification is PhysicalPairClassification.CHECK_CLEARANCE
    )
    forged_scope = tuple(sorted(forged_scope, key=lambda pair: (pair.first_instance_id, pair.second_instance_id)))
    forged_bridge = bridge.model_copy(
        update={
            "inventory": forged_inventory,
            "inventory_hash": forged_inventory.inventory_hash,
            "exact_pair_scope": forged_scope,
            "exact_pair_scope_hash": exact_pair_scope_hash(forged_scope),
        }
    )
    forged_bridge = forged_bridge.model_copy(
        update={"physical_to_m10_bridge_hash": physical_to_m10_bridge_hash(forged_bridge)}
    )
    assert PhysicalToM10V2Bridge.model_validate(forged_bridge.model_dump(mode="json"))

    with pytest.raises(ValueError, match="trusted physical inputs"):
        validate_physical_to_m10_v2_bridge(
            forged_bridge,
            physical_mechanism_hash=candidate.realization.realization_hash,
            root_physical_body_id=candidate.realization.kinematic_root_physical_body_id,
            model=bridge.model,
            bodies=candidate.realization.physical_rigid_body_bindings,
            joints=candidate.realization.physical_revolute_joint_bindings,
            components=candidate.realization.components,
            connections=candidate.realization.connections,
            mappings=realization.mappings,
            assembly=realization.assembly,
            cad_realization_hash=realization.realization_hash,
            pair_bindings=candidate.realization.physical_pair_classification_bindings,
        )


@pytest.mark.parametrize("field,value", [("schema_version", "kinematic-model@1"),
                                          ("evaluator_version", "wrong-evaluator"),
                                          ("transform_agreement_version", "wrong-agreement")])
def test_bridge_rejects_nested_m13_3p_version_substitutions(tmp_path, field, value):
    _, _, _, bridge = _compiled_candidate_bridge(tmp_path)
    forged_model = bridge.model.model_copy(update={field: value})
    with pytest.raises(ValueError):
        PhysicalToM10V2Bridge.model_validate(
            bridge.model_copy(update={"model": forged_model}).model_dump(mode="json")
        )
