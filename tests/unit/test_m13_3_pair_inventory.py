from __future__ import annotations

import hashlib
import itertools
import json

import pytest

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.candidates.cad_realization import (
    CandidateCadInstanceMapping,
    CandidateGeometryFidelity,
    CandidatePlacementOrigin,
)
from mechcad_harness.candidates.models import PhysicalRigidBodyBinding
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    MultiJointCollisionPairEntry,
    MultiJointCollisionPairInventory,
    derive_multi_joint_collision_pair_inventory,
    exact_scope_from_inventory,
)
from mechcad_harness.models.physical_pair_policy import (
    PhysicalPairClassification,
    PhysicalPairClassificationBinding,
)
from mechcad_harness.multi_joint_kinematics import (
    KinematicModelV2,
    KinematicRigidBody,
    KinematicRigidBodyMember,
    kinematic_model_hash,
)
from mechcad_harness.multi_joint_pair_scope import exact_pair_scope_hash


_HASH = "sha256:" + "a" * 64


def _bodies() -> tuple[PhysicalRigidBodyBinding, ...]:
    return (
        PhysicalRigidBodyBinding(
            physical_body_id="body-a",
            member_physical_instance_ids=("a1", "a2"),
            reference_physical_instance_id="a1",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="body-b",
            member_physical_instance_ids=("b1", "b2"),
            reference_physical_instance_id="b1",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="body-c",
            member_physical_instance_ids=("c1", "c2"),
            reference_physical_instance_id="c1",
        ),
    )


def _mapping(physical_id: str) -> CandidateCadInstanceMapping:
    transform = CadRigidTransform()
    return CandidateCadInstanceMapping(
        candidate_hash=_HASH,
        physical_instance_id=physical_id,
        cad_instance_id=f"cad-{physical_id}",
        fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
        representation_identity=_HASH,
        geometry_definition_identities=(f"geometry-{physical_id}",),
        placement=transform,
        placement_origin=CandidatePlacementOrigin(
            authority="candidate_design_variable",
            input_identities=(f"placement-{physical_id}",),
            derivation="test placement",
            transform=transform,
        ),
    )


def _assembly(physical_ids: tuple[str, ...]) -> CadAssemblyProgram:
    parts = tuple(
        CadPartProgram(
            part_id=f"part-{physical_id}",
            operations=(
                BasePlateOperation(
                    operation_id=f"operation-{physical_id}",
                    length_mm=10.0,
                    width_mm=10.0,
                    thickness_mm=1.0,
                ),
            ),
        )
        for physical_id in physical_ids
    )
    return CadAssemblyProgram(
        assembly_id="assembly",
        parts=parts,
        instances=tuple(
            CadComponentInstance(
                instance_id=f"cad-{physical_id}",
                part_id=f"part-{physical_id}",
            )
            for physical_id in physical_ids
        ),
    )


def _model() -> KinematicModelV2:
    bodies = tuple(
        KinematicRigidBody(
            body_id=body.physical_body_id,
            reference_member_instance_id=f"cad-{body.reference_physical_instance_id}",
            members=tuple(
                KinematicRigidBodyMember(
                    member_instance_id=f"cad-{member_id}",
                    reference_to_member_home=CadRigidTransform(),
                )
                for member_id in body.member_physical_instance_ids
            ),
        )
        for body in _bodies()
    )
    return KinematicModelV2(model_id="physical-to-m10-v2-model", bodies=bodies, joints=())


def _pairs() -> tuple[PhysicalPairClassificationBinding, ...]:
    owners = {
        member_id: body.physical_body_id
        for body in _bodies()
        for member_id in body.member_physical_instance_ids
    }
    physical_ids = tuple(sorted(owners))
    return tuple(
        PhysicalPairClassificationBinding(
            first_physical_instance_id=first,
            second_physical_instance_id=second,
            classification=(
                PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED
                if owners[first] == owners[second]
                else PhysicalPairClassification.CHECK_CLEARANCE
            ),
            exclusion_reason=(
                "same physical body" if owners[first] == owners[second] else None
            ),
        )
        for first, second in itertools.combinations(physical_ids, 2)
    )


def _derive(*, mappings=None, pairs=None, model=None):
    physical_ids = tuple(sorted(member for body in _bodies() for member in body.member_physical_instance_ids))
    return derive_multi_joint_collision_pair_inventory(
        physical_mechanism_hash=_HASH,
        cad_realization_hash=_HASH,
        model=_model() if model is None else model,
        mappings=tuple(_mapping(item) for item in physical_ids) if mappings is None else mappings,
        assembly=_assembly(physical_ids),
        physical_body_bindings=_bodies(),
        pair_bindings=_pairs() if pairs is None else pairs,
    )


def _scope(inventory):
    physical_ids = tuple(
        sorted(member for body in _bodies() for member in body.member_physical_instance_ids)
    )
    return exact_scope_from_inventory(
        inventory,
        model=_model(),
        mappings=tuple(_mapping(item) for item in physical_ids),
        assembly=_assembly(physical_ids),
        physical_body_bindings=_bodies(),
        pair_bindings=_pairs(),
    )


def test_derived_inventory_has_complete_15_pairs_and_exact_cross_body_scope():
    inventory = _derive()

    assert isinstance(inventory, MultiJointCollisionPairInventory)
    assert len(inventory.entries) == 15
    assert inventory.complete_concrete_instance_ids == tuple(
        f"cad-{item}" for item in ("a1", "a2", "b1", "b2", "c1", "c2")
    )
    assert inventory.expected_pair_universe == tuple(
        itertools.combinations(inventory.complete_concrete_instance_ids, 2)
    )
    same_body = next(item for item in inventory.entries if item.first_instance_id == "cad-a1" and item.second_instance_id == "cad-a2")
    assert same_body.classification is PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED
    assert same_body.exclusion_reason == "same physical body"

    scope = _scope(inventory)
    assert ("cad-a2", "cad-b1") in {
        (item.first_instance_id, item.second_instance_id) for item in scope
    }
    assert len(scope) == 12
    assert all(
        inventory_entry.classification is PhysicalPairClassification.CHECK_CLEARANCE
        for inventory_entry in inventory.entries
        if (inventory_entry.first_instance_id, inventory_entry.second_instance_id)
        in {(item.first_instance_id, item.second_instance_id) for item in scope}
    )
    assert exact_pair_scope_hash(scope).startswith("sha256:")


def test_inventory_and_scope_are_canonical_under_caller_reordering():
    inventory = _derive()
    reordered = _derive(
        mappings=tuple(reversed(tuple(_mapping(item) for item in ("a1", "a2", "b1", "b2", "c1", "c2")))),
        pairs=tuple(reversed(_pairs())),
    )

    assert reordered.model_dump(mode="json") == inventory.model_dump(mode="json")
    assert _scope(reordered) == _scope(inventory)


def test_exclusion_reason_is_part_of_inventory_identity():
    pairs = list(_pairs())
    pairs[0] = PhysicalPairClassificationBinding(
        first_physical_instance_id="a1",
        second_physical_instance_id="a2",
        classification=PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED,
        exclusion_reason="different explicit reason",
    )

    changed = _derive(pairs=tuple(pairs))

    assert changed.inventory_hash != _derive().inventory_hash


def test_inventory_rejects_legacy_home_check_flag_and_pair_substitution():
    with pytest.raises(ValueError):
        MultiJointCollisionPairEntry(
            first_instance_id="cad-a1",
            second_instance_id="cad-b1",
            classification=PhysicalPairClassification.CHECK_CLEARANCE,
            exclusion_reason=None,
            requires_home_exact_check=False,
        )

    with pytest.raises(ValueError):
        _derive(pairs=_pairs()[:-1])

    model = _model().model_copy(
        update={
            "bodies": _model().bodies[:-1],
        }
    )
    with pytest.raises(ValueError):
        _derive(model=model)


def test_inventory_hash_rejects_entry_tampering():
    inventory = _derive()
    payload = inventory.model_dump(mode="json")
    payload["entries"][0]["exclusion_reason"] = "tampered reason"

    with pytest.raises(ValueError):
        MultiJointCollisionPairInventory.model_validate(payload)


def test_inventory_binds_the_v2_model_hash():
    inventory = _derive()

    assert inventory.m10_model_hash == kinematic_model_hash(_model())


def test_inventory_derivation_rejects_v2_model_with_regrouped_physical_members():
    substituted_model = KinematicModelV2(
        model_id="physical-to-m10-v2-model",
        bodies=(
            KinematicRigidBody(
                body_id="body-a",
                reference_member_instance_id="cad-a1",
                members=(
                    KinematicRigidBodyMember(
                        member_instance_id="cad-a1",
                        reference_to_member_home=CadRigidTransform(),
                    ),
                ),
            ),
            KinematicRigidBody(
                body_id="body-b",
                reference_member_instance_id="cad-b1",
                members=tuple(
                    KinematicRigidBodyMember(
                        member_instance_id=f"cad-{member_id}",
                        reference_to_member_home=CadRigidTransform(),
                    )
                    for member_id in ("a2", "b1", "b2")
                ),
            ),
            KinematicRigidBody(
                body_id="body-c",
                reference_member_instance_id="cad-c1",
                members=tuple(
                    KinematicRigidBodyMember(
                        member_instance_id=f"cad-{member_id}",
                        reference_to_member_home=CadRigidTransform(),
                    )
                    for member_id in ("c1", "c2")
                ),
            ),
        ),
        joints=(),
    )

    with pytest.raises(ValueError, match="physical body ownership"):
        _derive(model=substituted_model)


def test_exact_scope_rejects_pending_rehash_of_tampered_same_body_check():
    inventory = _derive()
    tampered_entries = tuple(
        MultiJointCollisionPairEntry(
            first_instance_id=entry.first_instance_id,
            second_instance_id=entry.second_instance_id,
            classification=(
                PhysicalPairClassification.CHECK_CLEARANCE
                if (entry.first_instance_id, entry.second_instance_id)
                == ("cad-a1", "cad-a2")
                else entry.classification
            ),
            exclusion_reason=(
                None
                if (entry.first_instance_id, entry.second_instance_id)
                == ("cad-a1", "cad-a2")
                else entry.exclusion_reason
            ),
        )
        for entry in inventory.entries
    )
    tampered_inventory = inventory.model_copy(
        update={"entries": tampered_entries, "inventory_hash": "pending"}
    )

    with pytest.raises(ValueError, match="finalized"):
        MultiJointCollisionPairInventory.model_validate(
            tampered_inventory.model_dump(mode="json")
        )
    with pytest.raises(ValueError, match="finalized"):
        _scope(tampered_inventory)


def test_exact_scope_rejects_recomputed_hash_same_body_check_forgery():
    inventory = _derive()
    tampered_entries = tuple(
        MultiJointCollisionPairEntry(
            first_instance_id=entry.first_instance_id,
            second_instance_id=entry.second_instance_id,
            classification=(
                PhysicalPairClassification.CHECK_CLEARANCE
                if (entry.first_instance_id, entry.second_instance_id)
                == ("cad-a1", "cad-a2")
                else entry.classification
            ),
            exclusion_reason=(
                None
                if (entry.first_instance_id, entry.second_instance_id)
                == ("cad-a1", "cad-a2")
                else entry.exclusion_reason
            ),
        )
        for entry in inventory.entries
    )
    payload = inventory.model_dump(mode="json")
    payload["entries"] = [entry.model_dump(mode="json") for entry in tampered_entries]
    payload.pop("inventory_hash")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["inventory_hash"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    forged_inventory = MultiJointCollisionPairInventory.model_validate(payload)

    with pytest.raises(ValueError, match="does not match trusted physical inputs"):
        _scope(forged_inventory)
