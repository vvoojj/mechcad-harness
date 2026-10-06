from __future__ import annotations

import hashlib

import pytest

import mechcad_harness.candidates.canonical_m10 as canonical_m10
from mechcad_harness.candidates.canonical_m10 import (
    CanonicalM10BodyDisposition,
    CanonicalM10ConstituentDisposition,
    CanonicalM10PairClassification,
    CanonicalM10PairClassificationRecord,
    DerivedCanonicalM10Scope,
)
from mechcad_harness.models import CanonicalPhysicalPairRequirement
from mechcad_harness.state.hashing import canonical_json


def _scope(requirements=None):
    return DerivedCanonicalM10Scope(
        project_id="PRJ-SCOPE-V2",
        revision=4,
        state_hash="sha256:" + "a" * 64,
        mechanism_id="mechanism-scope-v2",
        mechanism_hash="sha256:" + "b" * 64,
        joint_semantic_key="joint-output",
        angle_interval_deg=(-15.0, 35.0),
        path_semantics="single_axis_interval",
        required_clearance_mm=2.5,
        physical_pair_requirements=(
            CanonicalPhysicalPairRequirement(
                requirement_key="pair-fixed-output",
                first_instance_id="fixed",
                first_interface_id="fixed-interface",
                second_instance_id="output",
                second_interface_id="output-interface",
                requires_home_exact_check=True,
            ),
        ) if requirements is None else tuple(requirements),
        fidelity_requirements=(
            ("fixed", "trusted_source_geometry"),
            ("output", "exact_generated_geometry"),
        ),
        required_home_check_semantics=("check-home-contact",),
        bounded_limitations=("single-solid-linear-static-excluded",),
    )


def test_semantic_canonical_scope_identity_has_an_explicit_owner():
    project = getattr(canonical_m10, "semantic_canonical_m10_scope_hash", None)

    assert callable(project), "canonical M10 N2-S scope identity is not implemented"
    assert project(_scope()).startswith("sha256:")


def test_semantic_scope_ignores_legacy_requirement_hash_and_sorts_requirement_set():
    project = getattr(canonical_m10, "semantic_canonical_m10_scope_hash", None)
    assert callable(project), "canonical M10 N2-S scope identity is not implemented"
    first = _scope()
    requirement = first.physical_pair_requirements[0]
    replay_only_change = requirement.model_copy(
        update={"requirement_hash": "sha256:" + "c" * 64}
    )
    changed_replay = first.model_copy(
        update={"physical_pair_requirements": (replay_only_change,)}
    )
    assert project(first) == project(changed_replay)

    second_requirement = CanonicalPhysicalPairRequirement(
        requirement_key="pair-output-motor",
        first_instance_id="output",
        first_interface_id="output-mount",
        second_instance_id="motor",
        second_interface_id="motor-mount",
    )
    reverse_order = _scope(
        requirements=(requirement, second_requirement)
    )
    forward_order = _scope(
        requirements=(second_requirement, requirement)
    )
    assert project(reverse_order) == project(forward_order)

    changed_engineering = requirement.model_copy(
        update={"second_interface_id": "changed-interface"}
    )
    changed_scope = first.model_copy(
        update={"physical_pair_requirements": (changed_engineering,)}
    )
    assert project(changed_scope) != project(first)

    duplicate_requirement = CanonicalPhysicalPairRequirement(
        requirement_key=requirement.requirement_key,
        first_instance_id="another-fixed",
        first_interface_id="another-fixed-interface",
        second_instance_id="another-output",
        second_interface_id="another-output-interface",
    )
    duplicate_scope = _scope(requirements=(requirement, duplicate_requirement))
    with pytest.raises(ValueError, match="duplicate|unique"):
        project(duplicate_scope)


def test_n2a_disposition_and_classification_v2_have_exact_fields_and_pinned_payloads():
    disposition_type = getattr(
        canonical_m10, "CanonicalM10ConstituentDispositionV2", None
    )
    classification_type = getattr(
        canonical_m10, "CanonicalM10PairClassificationRecordV2", None
    )
    assert disposition_type is not None, "canonical disposition@2 is not implemented"
    assert classification_type is not None, "canonical pair classification@2 is not implemented"

    disposition_fields = {
        "schema_version", "physical_instance_id", "cad_instance_id",
        "disposition", "output_transform_group", "disposition_hash",
    }
    classification_fields = {
        "schema_version", "pair", "classification", "reason",
        "requires_home_exact_check", "classification_hash",
    }
    assert set(disposition_type.model_fields) == disposition_fields
    assert set(classification_type.model_fields) == classification_fields
    assert set(CanonicalM10ConstituentDisposition.model_fields) == disposition_fields
    assert set(CanonicalM10PairClassificationRecord.model_fields) == classification_fields

    disposition = disposition_type(
        physical_instance_id="instance-a",
        cad_instance_id="cad-a",
        disposition=CanonicalM10BodyDisposition.FIXED,
    )
    disposition_payload = {
        "schema_version": "canonical-m10-constituent-disposition@2",
        "physical_instance_id": "instance-a",
        "cad_instance_id": "cad-a",
        "disposition": "fixed",
        "output_transform_group": None,
        "semantic_projection_version": "m10-execution-semantics@1",
    }
    expected_disposition_hash = "sha256:" + hashlib.sha256(
        canonical_json(disposition_payload)
    ).hexdigest()
    assert disposition.disposition_hash == expected_disposition_hash
    assert disposition.disposition_hash == (
        "sha256:6185d9ad1d47fe8ccb5377ecc039dacc76ac0a0e7f1c9fa0d8cd245bffea3318"
    )
    assert disposition.disposition_hash == canonical_m10.canonical_m10_constituent_disposition_hash_v2(
        disposition
    )

    classification = classification_type(
        pair=("cad-a", "cad-b"),
        classification=CanonicalM10PairClassification.CHECK_CLEARANCE,
        requires_home_exact_check=True,
    )
    classification_payload = {
        "schema_version": "canonical-m10-pair-classification@2",
        "pair": ["cad-a", "cad-b"],
        "classification": "check_clearance",
        "reason": None,
        "requires_home_exact_check": True,
        "semantic_projection_version": "m10-execution-semantics@1",
    }
    expected_classification_hash = "sha256:" + hashlib.sha256(
        canonical_json(classification_payload)
    ).hexdigest()
    assert classification.classification_hash == expected_classification_hash
    assert classification.classification_hash == (
        "sha256:4237ad52360fdc4e6787283dff3b684ed46f837635888374af9f48da802277a2"
    )
    assert classification.classification_hash == canonical_m10.canonical_m10_pair_classification_hash_v2(
        classification
    )


def test_semantic_scope_hash_is_pinned_and_excludes_legacy_scope_and_requirement_hashes():
    project = getattr(canonical_m10, "semantic_canonical_m10_scope_hash", None)
    payload_builder = getattr(canonical_m10, "_semantic_canonical_m10_scope_payload", None)
    assert callable(project), "canonical M10 N2-S scope identity is not implemented"
    assert callable(payload_builder), "canonical M10 N2-S payload is not inspectable by its owner"
    scope = _scope()
    payload = payload_builder(scope)

    assert payload == {
        "scope_contract": "derived-canonical-m10-scope@1",
        "semantic_projection_version": "m10-execution-semantics@1",
        "joint_semantic_key": "joint-output",
        "angle_interval_deg": [-15.0, 35.0],
        "path_semantics": "single_axis_interval",
        "required_clearance_mm": 2.5,
        "physical_pair_requirements": [{
            "requirement_key": "pair-fixed-output",
            "first_instance_id": "fixed",
            "first_interface_id": "fixed-interface",
            "second_instance_id": "output",
            "second_interface_id": "output-interface",
            "requires_home_exact_check": True,
        }],
        "fidelity_requirements": [
            ["fixed", "trusted_source_geometry"],
            ["output", "exact_generated_geometry"],
        ],
        "required_home_check_semantics": ["check-home-contact"],
        "bounded_limitations": ["single-solid-linear-static-excluded"],
    }
    assert "scope_hash" not in payload
    assert "requirement_hash" not in repr(payload)
    assert "binding_semantic_hash" not in payload
    assert project(scope) == (
        "sha256:9a13bb8bdf16c0afc02c703cdbbd164f5fe1cbc75325ce66f703e0a3307e3a5a"
    )


def test_semantic_scope_is_carried_by_inventory_and_request_and_mismatches_reject():
    scope = _scope()
    scope_identity = canonical_m10.semantic_canonical_m10_scope_hash(scope)
    dispositions = (
        canonical_m10.CanonicalM10ConstituentDispositionV2(
            physical_instance_id="fixed",
            cad_instance_id="cad-fixed",
            disposition=canonical_m10.CanonicalM10BodyDisposition.FIXED,
        ),
        canonical_m10.CanonicalM10ConstituentDispositionV2(
            physical_instance_id="output",
            cad_instance_id="cad-output",
            disposition=canonical_m10.CanonicalM10BodyDisposition.OUTPUT_RIGID,
            output_transform_group="joint-output",
        ),
    )
    classifications = (
        canonical_m10.CanonicalM10PairClassificationRecordV2(
            pair=("cad-fixed", "cad-output"),
            classification=canonical_m10.CanonicalM10PairClassification.CHECK_CLEARANCE,
            requires_home_exact_check=True,
        ),
    )
    inventory = canonical_m10.CanonicalM10PairInventoryV2(
        project_id=scope.project_id,
        revision=scope.revision,
        state_hash=scope.state_hash,
        mechanism_id=scope.mechanism_id,
        mechanism_hash=scope.mechanism_hash,
        cad_realization_hash="sha256:" + "d" * 64,
        semantic_scope_hash=scope_identity,
        constituent_dispositions=dispositions,
        expected_pair_universe=(("cad-fixed", "cad-output"),),
        classifications=classifications,
        checked_pairs=(("cad-fixed", "cad-output"),),
    )
    request = canonical_m10.CanonicalM10EvaluationRequestV2(
        project_id=scope.project_id,
        revision=scope.revision,
        state_hash=scope.state_hash,
        mechanism_id=scope.mechanism_id,
        mechanism_hash=scope.mechanism_hash,
        cad_realization_hash=inventory.cad_realization_hash,
        semantic_single_joint_kinematic_model_hash="sha256:" + "e" * 64,
        mapping_hashes=("sha256:" + "a" * 64, "sha256:" + "b" * 64),
        semantic_scope_hash=scope_identity,
        inventory=inventory,
    )
    assert inventory.semantic_scope_hash == request.semantic_scope_hash == scope_identity

    with pytest.raises(ValueError, match="semantic scope"):
        canonical_m10.CanonicalM10EvaluationRequestV2.model_validate(
            request.model_dump(mode="json")
            | {
                "semantic_scope_hash": "sha256:" + "f" * 64,
                "request_hash": "pending",
            }
        )
