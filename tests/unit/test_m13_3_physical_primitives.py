from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from mechcad_harness.candidates import (
    PhysicalRigidBodyBinding as ExportedPhysicalRigidBodyBinding,
    physical_kinematic_root_hash as exported_physical_kinematic_root_hash,
)
from mechcad_harness.candidates.m10_evaluation import CandidateM10PairClassification
from mechcad_harness.candidates.models import (
    PhysicalRigidBodyBinding,
    physical_kinematic_root_hash,
)
from mechcad_harness.models import (
    PhysicalPairClassification,
    PhysicalPairClassificationBinding,
    physical_pair_classification_set_hash,
)


def _hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def test_physical_primitives_are_publicly_exported_and_usable():
    assert ExportedPhysicalRigidBodyBinding is PhysicalRigidBodyBinding
    assert exported_physical_kinematic_root_hash("body-r") == physical_kinematic_root_hash("body-r")


def test_candidate_pair_enum_is_the_neutral_enum_with_legacy_wire_values():
    assert CandidateM10PairClassification is PhysicalPairClassification
    assert [member.value for member in PhysicalPairClassification] == [
        "check_clearance",
        "intended_contact_excluded",
        "same_rigid_group_excluded",
        "unmodeled_motion_out_of_scope",
        "other_explicit_out_of_scope",
    ]


def test_physical_rigid_body_binding_canonicalizes_members_and_hashes_exact_semantics():
    binding = PhysicalRigidBodyBinding(
        physical_body_id="body-a",
        member_physical_instance_ids=("instance-z", "instance-a"),
        reference_physical_instance_id="instance-a",
    )

    assert binding.member_physical_instance_ids == ("instance-a", "instance-z")
    assert binding.binding_hash == _hash(
        {
            "schema_version": "physical-rigid-body-binding@1",
            "physical_body_id": "body-a",
            "member_physical_instance_ids": ["instance-a", "instance-z"],
            "reference_physical_instance_id": "instance-a",
        }
    )
    assert binding.model_dump(mode="json").keys() == {
        "schema_version",
        "physical_body_id",
        "member_physical_instance_ids",
        "reference_physical_instance_id",
        "binding_hash",
    }
    assert PhysicalRigidBodyBinding(
        physical_body_id="body-a",
        member_physical_instance_ids=("instance-a", "instance-z"),
        reference_physical_instance_id="instance-a",
    ) == binding

    changed_body = PhysicalRigidBodyBinding(
        physical_body_id="body-b",
        member_physical_instance_ids=("instance-a", "instance-z"),
        reference_physical_instance_id="instance-a",
    )
    changed_reference = PhysicalRigidBodyBinding(
        physical_body_id="body-a",
        member_physical_instance_ids=("instance-a", "instance-z"),
        reference_physical_instance_id="instance-z",
    )
    assert changed_body.binding_hash != binding.binding_hash
    assert changed_reference.binding_hash != binding.binding_hash


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "physical_body_id": " ",
            "member_physical_instance_ids": ("instance-a",),
            "reference_physical_instance_id": "instance-a",
        },
        {
            "physical_body_id": "body-a",
            "member_physical_instance_ids": (),
            "reference_physical_instance_id": "instance-a",
        },
        {
            "physical_body_id": "body-a",
            "member_physical_instance_ids": ("instance-a", "instance-a"),
            "reference_physical_instance_id": "instance-a",
        },
        {
            "physical_body_id": "body-a",
            "member_physical_instance_ids": ("instance-a",),
            "reference_physical_instance_id": "instance-z",
        },
    ],
)
def test_physical_rigid_body_binding_rejects_malformed_membership(kwargs):
    with pytest.raises((ValueError, ValidationError)):
        PhysicalRigidBodyBinding(**kwargs)


def test_physical_kinematic_root_hash_uses_only_the_root_fact():
    assert physical_kinematic_root_hash("body-r") == _hash(
        {
            "schema_version": "physical-kinematic-root@1",
            "kinematic_root_physical_body_id": "body-r",
        }
    )
    assert physical_kinematic_root_hash("body-r") == physical_kinematic_root_hash("body-r")
    assert physical_kinematic_root_hash("body-r") != physical_kinematic_root_hash("body-x")
    with pytest.raises(ValueError):
        physical_kinematic_root_hash(" ")


def test_physical_pair_binding_canonicalizes_identity_and_enforces_reason_contract():
    first = PhysicalPairClassificationBinding(
        first_physical_instance_id="instance-z",
        second_physical_instance_id="instance-a",
        classification=PhysicalPairClassification.CHECK_CLEARANCE,
        exclusion_reason=None,
    )
    second = PhysicalPairClassificationBinding(
        first_physical_instance_id="instance-a",
        second_physical_instance_id="instance-z",
        classification=PhysicalPairClassification.CHECK_CLEARANCE,
        exclusion_reason=None,
    )

    assert first.first_physical_instance_id == "instance-a"
    assert first.second_physical_instance_id == "instance-z"
    assert first.binding_hash == second.binding_hash
    assert first.binding_hash == _hash(
        {
            "schema_version": "physical-pair-classification-binding@1",
            "first_physical_instance_id": "instance-a",
            "second_physical_instance_id": "instance-z",
            "classification": "check_clearance",
            "exclusion_reason": None,
        }
    )

    excluded = PhysicalPairClassificationBinding(
        first_physical_instance_id="instance-a",
        second_physical_instance_id="instance-z",
        classification=PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED,
        exclusion_reason="same body",
    )
    assert excluded.binding_hash != first.binding_hash

    with pytest.raises((ValueError, ValidationError)):
        PhysicalPairClassificationBinding(
            first_physical_instance_id="instance-a",
            second_physical_instance_id="instance-z",
            classification=PhysicalPairClassification.CHECK_CLEARANCE,
            exclusion_reason="not allowed",
        )
    with pytest.raises((ValueError, ValidationError)):
        PhysicalPairClassificationBinding(
            first_physical_instance_id="instance-a",
            second_physical_instance_id="instance-z",
            classification=PhysicalPairClassification.OTHER_EXPLICIT_OUT_OF_SCOPE,
            exclusion_reason=" ",
        )
    with pytest.raises((ValueError, ValidationError)):
        PhysicalPairClassificationBinding(
            first_physical_instance_id="instance-a",
            second_physical_instance_id="instance-a",
            classification=PhysicalPairClassification.CHECK_CLEARANCE,
            exclusion_reason=None,
        )


def test_physical_pair_set_hash_sorts_semantic_binding_hashes_and_rejects_duplicates():
    clear = PhysicalPairClassificationBinding(
        first_physical_instance_id="instance-a",
        second_physical_instance_id="instance-b",
        classification=PhysicalPairClassification.CHECK_CLEARANCE,
        exclusion_reason=None,
    )
    excluded = PhysicalPairClassificationBinding(
        first_physical_instance_id="instance-a",
        second_physical_instance_id="instance-c",
        classification=PhysicalPairClassification.OTHER_EXPLICIT_OUT_OF_SCOPE,
        exclusion_reason="outside requested scope",
    )

    expected = _hash(
        {
            "schema_version": "physical-pair-classification-set@1",
            "binding_hashes": sorted([clear.binding_hash, excluded.binding_hash]),
        }
    )
    assert physical_pair_classification_set_hash((excluded, clear)) == expected
    assert physical_pair_classification_set_hash((clear, excluded)) == expected
    with pytest.raises((ValueError, ValidationError)):
        physical_pair_classification_set_hash((clear, clear))
