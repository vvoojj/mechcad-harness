from __future__ import annotations

from types import MappingProxyType

import pytest

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.candidates.cad_realization import (
    CandidateCadInstanceMapping,
    CandidateGeometryFidelity,
    CandidatePlacementOrigin,
)
from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadMapping
from mechcad_harness.candidates.models import PhysicalRigidBodyBinding
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    validate_complete_physical_pair_policy,
    validate_physical_body_pair_consistency,
    validate_physical_cad_universe,
)
from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.models import (
    CanonicalGeometryFidelity,
    CanonicalPhysicalPairClassificationBinding,
    CanonicalPhysicalRigidBodyBinding,
    PhysicalPairClassification,
    PhysicalPairClassificationBinding,
)


_HASH = "sha256:" + "a" * 64


def _mapping(physical_id: str, cad_id: str) -> CandidateCadInstanceMapping:
    transform = CadRigidTransform(x_mm=float(len(physical_id)))
    return CandidateCadInstanceMapping(
        candidate_hash=_HASH,
        physical_instance_id=physical_id,
        cad_instance_id=cad_id,
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
                placement=CadRigidTransform(x_mm=float(len(physical_id))),
            )
            for physical_id in physical_ids
        ),
    )

def _canonical_mapping(physical_id: str, cad_id: str) -> CanonicalPhysicalCadMapping:
    return CanonicalPhysicalCadMapping(
        mechanism_hash=_HASH,
        physical_instance_id=physical_id,
        cad_instance_id=cad_id,
        component_hash=_HASH,
        specification_hash=_HASH,
        fidelity=CanonicalGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
        representation_identity=_HASH,
        geometry_definition_identities=(f"geometry-{physical_id}",),
        placement=CadRigidTransform(x_mm=float(len(physical_id))),
        placement_input_identities=(f"placement-{physical_id}",),
        placement_relation="test placement",
    )


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


def _pairs(
    physical_ids: tuple[str, ...] = ("a1", "a2", "b1", "b2", "c1", "c2"),
) -> tuple[PhysicalPairClassificationBinding, ...]:
    body_by_member = {member: body for body in _bodies() for member in body.member_physical_instance_ids}
    return tuple(
        PhysicalPairClassificationBinding(
            first_physical_instance_id=first,
            second_physical_instance_id=second,
            classification=(
                PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED
                if body_by_member[first] is body_by_member[second]
                else PhysicalPairClassification.CHECK_CLEARANCE
            ),
            exclusion_reason=(
                "same physical body"
                if body_by_member[first] is body_by_member[second]
                else None
            ),
        )
        for index, first in enumerate(physical_ids)
        for second in physical_ids[index + 1 :]
    )


def test_physical_cad_universe_returns_sorted_immutable_mapping_and_rejects_unmapped_members():
    ids = ("b2", "a1", "c1", "a2", "c2", "b1")
    mappings = tuple(_mapping(physical_id, f"cad-{physical_id}") for physical_id in ids)

    normalized = validate_physical_cad_universe(mappings, _assembly(ids), _bodies())

    assert isinstance(normalized, MappingProxyType)
    assert tuple(normalized) == tuple(sorted(ids))
    assert tuple(mapping.physical_instance_id for mapping in normalized.values()) == tuple(sorted(ids))
    with pytest.raises(TypeError):
        normalized["a1"] = mappings[0]

    with pytest.raises(ValueError, match="body member universe"):
        validate_physical_cad_universe(
            mappings,
            _assembly(ids),
            _bodies()[:-1],
        )


def test_physical_cad_universe_rejects_duplicate_or_omitted_cad_constituents():
    ids = ("a1", "b1")
    mappings = tuple(_mapping(physical_id, f"cad-{physical_id}") for physical_id in ids)
    bodies = tuple(
        PhysicalRigidBodyBinding(
            physical_body_id=f"body-{physical_id}",
            member_physical_instance_ids=(physical_id,),
            reference_physical_instance_id=physical_id,
        )
        for physical_id in ids
    )

    with pytest.raises(ValueError, match="duplicate CAD instance"):
        validate_physical_cad_universe(
            mappings + (_mapping("c1", "cad-a1"),), _assembly(ids), bodies
        )
    with pytest.raises(ValueError, match="assembly membership"):
        validate_physical_cad_universe(mappings[:-1], _assembly(ids), bodies)
    with pytest.raises(ValueError, match="assembly membership"):
        validate_physical_cad_universe(mappings, _assembly(ids + ("extra",)), bodies)


def test_physical_cad_universe_rejects_duplicate_physical_body_membership():
    ids = ("a1", "b1")
    mappings = tuple(_mapping(physical_id, f"cad-{physical_id}") for physical_id in ids)
    duplicate_bodies = (
        PhysicalRigidBodyBinding(
            physical_body_id="body-a",
            member_physical_instance_ids=("a1",),
            reference_physical_instance_id="a1",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="body-b",
            member_physical_instance_ids=("a1", "b1"),
            reference_physical_instance_id="a1",
        ),
    )

    with pytest.raises(ValueError, match="multiple bodies"):
        validate_physical_cad_universe(mappings, _assembly(ids), duplicate_bodies)


def test_physical_cad_universe_rejects_mapping_assembly_placement_mismatch():
    ids = ("a1", "b1")
    mappings = (_mapping("a1", "cad-a1"), _mapping("b1", "cad-b1"))
    mismatched_assembly = _assembly(ids).model_copy(
        update={
            "instances": (
                CadComponentInstance(
                    instance_id="cad-a1",
                    part_id="part-a1",
                    placement=CadRigidTransform(x_mm=100.0),
                ),
                CadComponentInstance(instance_id="cad-b1", part_id="part-b1"),
            )
        }
    )
    bodies = tuple(
        PhysicalRigidBodyBinding(
            physical_body_id=f"body-{physical_id}",
            member_physical_instance_ids=(physical_id,),
            reference_physical_instance_id=physical_id,
        )
        for physical_id in ids
    )

    with pytest.raises(ValueError, match="placement"):
        validate_physical_cad_universe(mappings, mismatched_assembly, bodies)


def test_physical_cad_universe_accepts_canonical_mapping_layer_without_mixing_layers():
    ids = ("a1", "b1")
    mappings = tuple(_canonical_mapping(physical_id, f"cad-{physical_id}") for physical_id in ids)
    bodies = tuple(
        CanonicalPhysicalRigidBodyBinding(
            physical_body_id=f"body-{physical_id}",
            member_physical_instance_ids=(physical_id,),
            reference_physical_instance_id=physical_id,
        )
        for physical_id in ids
    )

    normalized = validate_physical_cad_universe(mappings, _assembly(ids), bodies)

    assert tuple(normalized) == ids
    assert all(isinstance(value, CanonicalPhysicalCadMapping) for value in normalized.values())
    with pytest.raises(ValueError, match="must not mix"):
        validate_physical_cad_universe(
            mappings[:1] + (_mapping("b1", "cad-b1"),), _assembly(ids), bodies
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda pairs: pairs[:-1],
        lambda pairs: pairs + (pairs[0],),
        lambda pairs: pairs[:-1] + (pairs[0],),
    ],
)
def test_complete_physical_pair_policy_requires_exactly_one_entry_per_pair(mutate):
    pairs = mutate(_pairs())

    with pytest.raises(ValueError):
        validate_complete_physical_pair_policy(pairs, tuple("a1 a2 b1 b2 c1 c2".split()))


@pytest.mark.parametrize(
    "bad_pair",
    [
        ("a1", "a1"),
        ("a1", "unknown"),
        ("z1", "z2"),
    ],
)
def test_complete_physical_pair_policy_rejects_self_unknown_and_extra_pairs(bad_pair):
    pairs = list(_pairs())
    pairs.append(
        PhysicalPairClassificationBinding.model_construct(
            first_physical_instance_id=bad_pair[0],
            second_physical_instance_id=bad_pair[1],
            classification=PhysicalPairClassification.CHECK_CLEARANCE,
            exclusion_reason=None,
        )
    )

    with pytest.raises(ValueError):
        validate_complete_physical_pair_policy(tuple(pairs), ("a1", "a2", "b1", "b2", "c1", "c2"))


def test_complete_physical_pair_policy_returns_canonical_15_pair_map_and_preserves_binding_identity():
    pairs = _pairs()
    normalized = validate_complete_physical_pair_policy(tuple(reversed(pairs)), ("c2", "a2", "b1", "c1", "a1", "b2"))

    assert isinstance(normalized, MappingProxyType)
    assert len(normalized) == 15
    assert tuple(normalized) == tuple(sorted(normalized))
    assert normalized[("a1", "a2")].binding_hash == next(
        pair.binding_hash for pair in pairs if pair.first_physical_instance_id == "a1" and pair.second_physical_instance_id == "a2"
    )


def test_complete_physical_pair_policy_rejects_mixed_candidate_and_canonical_bindings():
    pairs = list(_pairs())
    pairs[0] = CanonicalPhysicalPairClassificationBinding(
        first_physical_instance_id="a1",
        second_physical_instance_id="a2",
        classification=PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED,
        exclusion_reason="same physical body",
    )

    with pytest.raises(ValueError, match="must not mix"):
        validate_complete_physical_pair_policy(
            tuple(pairs), ("a1", "a2", "b1", "b2", "c1", "c2")
        )


def test_body_pair_consistency_requires_same_body_exclusion_and_cross_body_not_same_body():
    pairs = list(_pairs())
    same_body = pairs[0]
    pairs[0] = PhysicalPairClassificationBinding(
        first_physical_instance_id=same_body.first_physical_instance_id,
        second_physical_instance_id=same_body.second_physical_instance_id,
        classification=PhysicalPairClassification.CHECK_CLEARANCE,
        exclusion_reason=None,
    )
    normalized_pairs = validate_complete_physical_pair_policy(tuple(pairs), ("a1", "a2", "b1", "b2", "c1", "c2"))

    with pytest.raises(ValueError, match="same physical body"):
        validate_physical_body_pair_consistency(_bodies(), normalized_pairs)

    valid_pairs = validate_complete_physical_pair_policy(
        _pairs(), ("a1", "a2", "b1", "b2", "c1", "c2")
    )
    cross_body = ("a1", "b1")
    bad_cross = dict(valid_pairs)
    bad_cross[cross_body] = PhysicalPairClassificationBinding(
        first_physical_instance_id=cross_body[0],
        second_physical_instance_id=cross_body[1],
        classification=PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED,
        exclusion_reason="wrong",
    )
    with pytest.raises(ValueError, match="cross-body"):
        validate_physical_body_pair_consistency(_bodies(), bad_cross)


def test_body_pair_consistency_returns_immutable_member_owner_map():
    normalized_pairs = validate_complete_physical_pair_policy(_pairs(), ("a1", "a2", "b1", "b2", "c1", "c2"))

    owners = validate_physical_body_pair_consistency(_bodies(), normalized_pairs)

    assert isinstance(owners, MappingProxyType)
    assert owners == {
        "a1": "body-a",
        "a2": "body-a",
        "b1": "body-b",
        "b2": "body-b",
        "c1": "body-c",
        "c2": "body-c",
    }
