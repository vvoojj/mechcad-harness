from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.candidates import MultiJointPromotionDecisionInputReference
from mechcad_harness.candidates.multi_joint_m10_evaluation import (
    CandidateMultiJointM10EvaluationService,
)
from mechcad_harness.candidates.promotion_artifacts import (
    PromotionManifestService,
    SelectedMultiJointCandidateDecisionManifest,
    _build_multi_joint_decision_input_reference,
    multi_joint_decision_manifest_hash,
    resolve_multi_joint_decision,
    verify_multi_joint_promotion_decision,
)
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates import CandidatePromotionCompilation
from mechcad_harness.candidates.promotion_models import PromotionValueClassification
from mechcad_harness.models import MultiJointVerificationConfigurationSet
from mechcad_harness.models.generated_placement import placement_derivations_hash
from mechcad_harness.models.physical_pair_policy import (
    PhysicalPairClassification,
    physical_pair_classification_set_hash,
)
from mechcad_harness.multi_joint_collision_sweep import (
    multi_joint_collision_sweep_result_v2_hash,
)
from mechcad_harness.multi_joint_kinematics import JointConfiguration
from mechcad_harness.runs import Run, RunStatus

from test_m13_3_promotion import _promotion_chain
from test_m13_3_candidate_evaluation import _result


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64


def _reference(**updates):
    values = {
        "promotion_request_hash": HASH_A,
        "readiness_hash": HASH_B,
        "project_id": "PRJ-1",
        "source_revision": 3,
        "source_state_hash": HASH_A,
        "source_binding_hash": HASH_A,
        "candidate_hash": HASH_A,
        "synthesis_request_hash": HASH_A,
        "synthesis_policy_hash": HASH_A,
        "m12_3_result_hash": HASH_A,
        "multi_joint_evaluation_request_hash": HASH_A,
        "multi_joint_evaluation_hash": HASH_A,
        "multi_joint_selection_hash": HASH_A,
        "scope_hash": HASH_A,
        "configuration_set_hash": HASH_A,
        "placement_derivations_hash": None,
        "physical_pair_classification_set_hash": HASH_A,
        "m10_v2_request_hash": HASH_A,
        "m10_v2_result_hash": HASH_A,
        "promotion_policy_hash": HASH_A,
        "canonical_target_mechanism_id": "PM-1",
        "mapping_identities": (HASH_A, HASH_B),
        "classification_identities": (HASH_A, HASH_B),
    }
    values.update(updates)
    return MultiJointPromotionDecisionInputReference(**values)


def test_multi_joint_decision_input_reference_has_the_accepted_schema_literal():
    assert MultiJointPromotionDecisionInputReference.model_fields["schema_version"].default == (
        "multi-joint-promotion-decision-input-reference@1"
    )


def test_reference_has_exact_fields_and_hash_payload():
    reference = _reference()
    assert set(reference.model_dump(mode="json")) == {
        "schema_version",
        "promotion_request_hash",
        "readiness_hash",
        "project_id",
        "source_revision",
        "source_state_hash",
        "source_binding_hash",
        "candidate_hash",
        "synthesis_request_hash",
        "synthesis_policy_hash",
        "m12_3_result_hash",
        "multi_joint_evaluation_request_hash",
        "multi_joint_evaluation_hash",
        "multi_joint_selection_hash",
        "scope_hash",
        "configuration_set_hash",
        "placement_derivations_hash",
        "physical_pair_classification_set_hash",
        "m10_v2_request_hash",
        "m10_v2_result_hash",
        "promotion_policy_hash",
        "canonical_target_mechanism_id",
        "mapping_identities",
        "classification_identities",
        "reference_hash",
    }
    payload = reference.model_dump(mode="json")
    actual = payload.pop("reference_hash")
    expected = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert actual == expected
    assert reference.placement_derivations_hash is None
    assert reference.model_dump(mode="json")["placement_derivations_hash"] is None


@pytest.mark.parametrize(
    "updates",
    [
        {"source_revision": 0},
        {"project_id": " "},
        {"canonical_target_mechanism_id": " "},
        {"mapping_identities": ()},
        {"classification_identities": ()},
        {"mapping_identities": (HASH_A, HASH_A)},
        {"classification_identities": (HASH_A, HASH_A)},
        {"classification_identities": (HASH_B, HASH_A)},
        {"m10_v2_result_hash": "not-a-hash"},
    ],
)
def test_reference_rejects_invalid_identity_fields(updates):
    with pytest.raises(ValueError):
        _reference(**updates)


def test_reference_builder_derives_each_identity_from_typed_request_and_readiness(tmp_path):
    _, _, _, _, _, request, _, compiler = _promotion_chain(tmp_path)
    readiness = compiler.validate_multi_joint_readiness(request)

    reference = _build_multi_joint_decision_input_reference(request, readiness)

    assert reference.promotion_request_hash == request.request_hash
    assert reference.readiness_hash == readiness.readiness_hash
    assert reference.project_id == request.project_id == readiness.project_id
    assert reference.source_revision == request.source_revision == readiness.source_revision
    assert reference.source_state_hash == request.source_state_hash == readiness.source_state_hash
    assert reference.source_binding_hash == readiness.source_binding_hash
    assert reference.candidate_hash == request.candidate.candidate_hash == readiness.candidate_hash
    assert reference.synthesis_request_hash == request.synthesis_request.request_hash
    assert reference.synthesis_policy_hash == request.synthesis_policy.policy_hash
    assert reference.m12_3_result_hash == request.m12_3_result.result_hash
    assert reference.multi_joint_evaluation_request_hash == request.multi_joint_request.request_hash
    assert reference.multi_joint_evaluation_hash == request.multi_joint_evaluation.evaluation_hash
    assert reference.multi_joint_selection_hash == request.multi_joint_selection.selection_hash
    assert reference.scope_hash == request.multi_joint_request.scope_hash
    assert reference.configuration_set_hash == request.multi_joint_request.configuration_set_hash
    assert reference.placement_derivations_hash == request.placement_derivations_hash
    assert reference.physical_pair_classification_set_hash == (
        request.multi_joint_request.physical_pair_classification_set_hash
    )
    assert reference.m10_v2_request_hash == request.multi_joint_request.m10_v2_request_hash
    assert reference.m10_v2_result_hash == request.multi_joint_evaluation.m10_v2_result_hash
    assert reference.promotion_policy_hash == request.promotion_policy.policy_hash
    assert reference.canonical_target_mechanism_id == request.canonical_target_mechanism_id
    assert reference.mapping_identities == tuple(item.mapping_hash for item in readiness.mapping)
    assert reference.classification_identities == readiness.classification_identities


def test_reference_builder_rejects_a_readiness_from_a_different_typed_chain(tmp_path):
    _, _, _, _, _, request_a, _, compiler_a = _promotion_chain(tmp_path / "a")
    chain_b = _promotion_chain(tmp_path / "b", values=(0.0, 11.0))
    request_b, compiler_b = chain_b[5], chain_b[7]
    readiness_a = compiler_a.validate_multi_joint_readiness(request_a)
    readiness_b = compiler_b.validate_multi_joint_readiness(request_b)

    with pytest.raises(ValueError, match="binding|mismatch|identity"):
        _build_multi_joint_decision_input_reference(request_a, readiness_b)
    assert readiness_a.configuration_set_hash != request_b.multi_joint_request.configuration_set_hash


def test_reference_builder_requires_the_exact_concrete_request_and_readiness_types(tmp_path):
    _, _, _, _, _, request, _, compiler = _promotion_chain(tmp_path)
    readiness = compiler.validate_multi_joint_readiness(request)

    with pytest.raises(ValueError, match="typed"):
        _build_multi_joint_decision_input_reference(request.model_copy(), object())


def test_selected_manifest_has_exact_fields_and_hash_payload(tmp_path):
    _, _, _, _, _, request, manager, compiler = _promotion_chain(tmp_path)
    readiness = compiler.validate_multi_joint_readiness(request)
    compilation = compiler.compile_multi_joint(
        manager.load_current_state(request.project_id), request
    )
    reference = _build_multi_joint_decision_input_reference(request, readiness)
    manifest = SelectedMultiJointCandidateDecisionManifest(
        input_reference=reference,
        promotion_policy_hash=request.promotion_policy.policy_hash,
        base_revision=compilation.proposal.base_revision,
        base_state_hash=compilation.proposal.base_state_hash,
        compilation_hash=compilation.compilation_hash,
        promotion_proposal_hash=compilation.promotion_proposal_hash,
        projection_hash=compilation.projection.projection_hash,
        projection=compilation.projection,
        mapping=compilation.mapping,
    )

    assert set(manifest.model_dump(mode="json")) == {
        "schema_version",
        "input_reference",
        "promotion_policy_hash",
        "base_revision",
        "base_state_hash",
        "compilation_hash",
        "promotion_proposal_hash",
        "projection_hash",
        "projection",
        "mapping",
        "decision_hash",
    }
    assert "pre_promotion_scope_projection" not in manifest.model_dump(mode="json")
    payload = manifest.model_dump(mode="json")
    actual = payload.pop("decision_hash")
    expected = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert actual == expected == multi_joint_decision_manifest_hash(manifest)
    assert manifest.mapping == readiness.mapping
    assert set(manifest.projection.canonical_instance_ids) == {
        item.canonical_instance_id for item in manifest.mapping
    }


def test_legacy_family_is_separate_from_multi_joint_manifest(tmp_path):
    from mechcad_harness.candidates.promotion_artifacts import SelectedCandidateDecisionManifest

    _, _, _, _, _, request, manager, compiler = _promotion_chain(tmp_path)
    readiness = compiler.validate_multi_joint_readiness(request)
    compilation = compiler.compile_multi_joint(
        manager.load_current_state(request.project_id), request
    )
    reference = _build_multi_joint_decision_input_reference(request, readiness)
    manifest = SelectedMultiJointCandidateDecisionManifest(
        input_reference=reference,
        promotion_policy_hash=request.promotion_policy.policy_hash,
        base_revision=compilation.proposal.base_revision,
        base_state_hash=compilation.proposal.base_state_hash,
        compilation_hash=compilation.compilation_hash,
        promotion_proposal_hash=compilation.promotion_proposal_hash,
        projection_hash=compilation.projection.projection_hash,
        projection=compilation.projection,
        mapping=compilation.mapping,
    )

    with pytest.raises(ValueError):
        SelectedCandidateDecisionManifest.model_validate(manifest.model_dump(mode="json"))
    with pytest.raises(ValueError):
        SelectedMultiJointCandidateDecisionManifest.model_validate(
            {"schema_version": "selected-candidate-decision-manifest@1"}
        )


def _decision_inputs(tmp_path):
    candidate, realization, bridge, _, _, request, manager, compiler = _promotion_chain(tmp_path)
    readiness = compiler.validate_multi_joint_readiness(request)
    compilation = compiler.compile_multi_joint(
        manager.load_current_state(request.project_id), request
    )
    run = Run(
        run_id="RUN-M13-4E",
        project_id=request.project_id,
        initial_revision=request.source_revision,
        initial_state_hash=request.source_state_hash,
        active_revision=request.source_revision,
        active_state_hash=request.source_state_hash,
        status=RunStatus.CREATED,
    )
    store = ArtifactStore(tmp_path, project_id=request.project_id, run_id=run.run_id)
    return store, run, request, readiness, compilation


def _verification_inputs_with_chain(tmp_path):
    candidate, realization, bridge, _, _, request, manager, compiler = _promotion_chain(tmp_path)
    readiness = compiler.validate_multi_joint_readiness(request)
    compilation = compiler.compile_multi_joint(
        manager.load_current_state(request.project_id), request
    )
    return request, readiness, compilation, candidate, realization, bridge


_MIRRORED_MULTI_JOINT_FIELDS = (
    "project_id",
    "source_revision",
    "source_state_hash",
    "source_binding_hash",
    "candidate_hash",
    "m10_v2_request_hash",
    "physical_to_m10_bridge_hash",
    "m10_model_hash",
    "physical_pair_classification_set_hash",
    "inventory_hash",
    "exact_pair_scope_hash",
    "scope_hash",
    "configuration_set_hash",
)


def _json_value(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def _rehash_record(record, identity_field, **updates):
    payload = record.model_dump(mode="json")
    payload.update({name: _json_value(value) for name, value in updates.items()})
    payload[identity_field] = "pending"
    return type(record).model_validate(payload)


def _rehashed_multi_joint_chain(
    request,
    readiness,
    *,
    multi_request_updates=None,
    evaluation_updates=None,
    selection_updates=None,
    request_updates=None,
    readiness_updates=None,
):
    multi_request = _rehash_record(
        request.multi_joint_request,
        "request_hash",
        **(multi_request_updates or {}),
    )

    mirrored = {name: getattr(multi_request, name) for name in _MIRRORED_MULTI_JOINT_FIELDS}
    rebuilt_evaluation_updates = dict(mirrored)
    rebuilt_evaluation_updates.update(
        {
            "candidate_request_hash": multi_request.request_hash,
            **(evaluation_updates or {}),
        }
    )
    evaluation = _rehash_record(
        request.multi_joint_evaluation,
        "evaluation_hash",
        **rebuilt_evaluation_updates,
    )

    rebuilt_selection_updates = dict(mirrored)
    rebuilt_selection_updates.update(
        {
            "evaluation_hash": evaluation.evaluation_hash,
            "candidate_request_hash": multi_request.request_hash,
            "m10_v2_result_hash": evaluation.m10_v2_result_hash,
            **(selection_updates or {}),
        }
    )
    selection = _rehash_record(
        request.multi_joint_selection,
        "selection_hash",
        **rebuilt_selection_updates,
    )

    rebuilt_request_updates = {
        "multi_joint_request": multi_request,
        "multi_joint_evaluation": evaluation,
        "multi_joint_selection": selection,
        **(request_updates or {}),
    }
    forged_request = _rehash_record(request, "request_hash", **rebuilt_request_updates)

    rebuilt_readiness_updates = {
        "request_hash": forged_request.request_hash,
        "multi_joint_evaluation_hash": evaluation.evaluation_hash,
        "multi_joint_selection_hash": selection.selection_hash,
        "scope_hash": multi_request.scope_hash,
        "configuration_set_hash": multi_request.configuration_set_hash,
        "classification_identities": tuple(
            sorted(item.classification_hash for item in forged_request.classifications)
        ),
        **(readiness_updates or {}),
    }
    forged_readiness = _rehash_record(
        readiness,
        "readiness_hash",
        **rebuilt_readiness_updates,
    )
    return (
        forged_request,
        forged_readiness,
        request.multi_joint_request,
        multi_request,
        evaluation,
        selection,
    )


def _assert_records_are_self_consistent(*records):
    for record in records:
        assert type(record).model_validate(record.model_dump(mode="json")) == record


def _forged_m10_result(candidate, realization, bridge, request):
    m10_request = CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
        bridge, realization, request.multi_joint_request.scope
    )
    baseline = _result(m10_request, realization.assembly)
    forged = type(baseline).model_validate(
        baseline.model_dump(mode="json")
        | {
            "any_touching": True,
            "all_positive_clearance": False,
            "minimum_exact_distance_mm": 0.0,
            "result_hash": "pending",
        }
    )
    return type(forged).model_validate(
        forged.model_dump(mode="json")
        | {"result_hash": multi_joint_collision_sweep_result_v2_hash(forged)}
    )


R6_SUBSTITUTION_IDS = (
    "readiness",
    "evaluation_request_substitution",
    "evaluation_substitution",
    "selection_substitution",
    "configuration_set_substitution",
    "placement_derivation_substitution",
    "pair_policy_substitution",
    "m10_request_substitution",
    "m10_result_substitution",
    "mapping_substitution",
    "classification_substitution",
)


def _build_r6_substitution(
    substitution_id,
    *,
    request,
    readiness,
    compilation,
    candidate,
    realization,
    bridge,
):
    records = []
    expected_binding_label = {
        "readiness": "readiness",
        "evaluation_request_substitution": "multi-joint evaluation request",
        "evaluation_substitution": "multi-joint evaluation",
        "selection_substitution": "multi-joint selection",
        "configuration_set_substitution": "configuration set",
        "placement_derivation_substitution": "placement derivation",
        "pair_policy_substitution": "physical pair classification set",
        "m10_request_substitution": "M10 v2 request",
        "m10_result_substitution": "M10 v2 result",
        "mapping_substitution": "multi-joint decision mapping does not match the original compilation",
        "classification_substitution": "classification identities",
    }[substitution_id]

    if substitution_id == "readiness":
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            readiness_updates={
                "trusted_geometry_artifact_ids": tuple(
                    sorted((*readiness.trusted_geometry_artifact_ids, "R6-FORGED-GEOMETRY"))
                )
            },
        )
        records.extend(chain_records)
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    if substitution_id == "evaluation_request_substitution":
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            multi_request_updates={"physical_to_m10_bridge_hash": HASH_C},
        )
        records.extend(chain_records)
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    if substitution_id == "evaluation_substitution":
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            evaluation_updates={"m10_v2_result_hash": HASH_C},
        )
        records.extend(chain_records)
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    if substitution_id == "selection_substitution":
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            selection_updates={"selector_identity": "R6-forged-selector"},
        )
        records.extend(chain_records)
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    if substitution_id == "configuration_set_substitution":
        configuration_set = request.multi_joint_request.scope.configuration_set
        last_configuration = configuration_set.configurations[-1]
        joint_id, value = next(iter(last_configuration.positions.items()))
        forged_configuration = last_configuration.model_copy(
            update={"positions": {**last_configuration.positions, joint_id: value + 1.0}}
        )
        forged_configuration_set = MultiJointVerificationConfigurationSet(
            configurations=configuration_set.configurations[:-1] + (forged_configuration,)
        )
        forged_scope = _rehash_record(
            request.multi_joint_request.scope,
            "scope_hash",
            configuration_set=forged_configuration_set,
        )
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            multi_request_updates={
                "scope": forged_scope,
                "scope_hash": forged_scope.scope_hash,
                "configuration_set_hash": forged_configuration_set.configuration_set_hash,
                "configuration_hashes": forged_configuration_set.configuration_hashes,
            },
        )
        records.extend((forged_configuration_set, forged_scope, *chain_records))
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    if substitution_id == "placement_derivation_substitution":
        derivation = request.generated_placement_derivations[0]
        forged_interface = derivation.source_interface_ref.model_copy(
            update={"interface_hash": HASH_C}
        )
        forged_derivation = _rehash_record(
            derivation,
            "derivation_hash",
            source_interface_ref=forged_interface,
        )
        forged_derivations = tuple(
            sorted(
                (forged_derivation, *request.generated_placement_derivations[1:]),
                key=lambda item: item.derivation_id,
            )
        )
        forged_derivations_hash = placement_derivations_hash(forged_derivations)
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            multi_request_updates={
                "placement_derivations": forged_derivations,
                "placement_derivations_hash": forged_derivations_hash,
            },
            request_updates={
                "generated_placement_derivations": forged_derivations,
                "placement_derivations_hash": forged_derivations_hash,
            },
        )
        records.extend((forged_derivation, *chain_records))
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    if substitution_id == "pair_policy_substitution":
        pair = candidate.realization.physical_pair_classification_bindings[0]
        forged_pair = _rehash_record(
            pair,
            "binding_hash",
            classification=PhysicalPairClassification.INTENDED_CONTACT_EXCLUDED,
            exclusion_reason="R6 substituted pair policy",
        )
        forged_pairs = tuple(
            forged_pair if item is pair else item
            for item in candidate.realization.physical_pair_classification_bindings
        )
        forged_pair_policy_hash = physical_pair_classification_set_hash(forged_pairs)
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            multi_request_updates={
                "physical_pair_classification_set_hash": forged_pair_policy_hash
            },
        )
        records.extend((forged_pair, *chain_records))
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    if substitution_id == "m10_request_substitution":
        m10_request = CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
            bridge, realization, request.multi_joint_request.scope
        )
        forged_m10_request = _rehash_record(
            m10_request,
            "request_hash",
            distance_tolerance_mm=m10_request.distance_tolerance_mm + 0.5,
        )
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            multi_request_updates={"m10_v2_request_hash": forged_m10_request.request_hash},
        )
        records.extend((forged_m10_request, *chain_records))
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    if substitution_id == "m10_result_substitution":
        forged_m10_result = _forged_m10_result(candidate, realization, bridge, request)
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            evaluation_updates={"m10_v2_result_hash": forged_m10_result.result_hash},
        )
        records.extend((forged_m10_result, *chain_records))
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    if substitution_id == "mapping_substitution":
        first, second, *remaining = compilation.mapping
        target = request.canonical_target_mechanism_id
        swapped_first = _rehash_record(
            first,
            "mapping_hash",
            canonical_instance_id=second.canonical_instance_id,
            canonical_path=(
                f"/physical_mechanisms/{target}/components/{second.canonical_instance_id}"
            ),
        )
        swapped_second = _rehash_record(
            second,
            "mapping_hash",
            canonical_instance_id=first.canonical_instance_id,
            canonical_path=(
                f"/physical_mechanisms/{target}/components/{first.canonical_instance_id}"
            ),
        )
        swapped_mapping = (swapped_first, swapped_second, *remaining)
        assert tuple(item.candidate_instance_id for item in swapped_mapping) == tuple(
            item.candidate_instance_id for item in compilation.mapping
        )
        assert {item.canonical_instance_id for item in swapped_mapping} == {
            item.canonical_instance_id for item in compilation.mapping
        }
        assert tuple(item.mapping_hash for item in swapped_mapping) != tuple(
            item.mapping_hash for item in compilation.mapping
        )
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            readiness_updates={"mapping": swapped_mapping},
        )
        forged_compilation = _rehash_record(
            compilation,
            "compilation_hash",
            mapping=swapped_mapping,
        )
        records.extend((*swapped_mapping, *chain_records, forged_compilation))
        return forged_request, forged_readiness, forged_compilation, records, expected_binding_label

    if substitution_id == "classification_substitution":
        original = next(
            item
            for item in request.classifications
            if item.source_identity == "candidate:connection:physical-drive"
        )
        forged_classification = _rehash_record(
            original,
            "classification_hash",
            classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
        )
        forged_classifications = tuple(
            forged_classification if item is original else item
            for item in request.classifications
        )
        assert tuple(item.source_identity for item in forged_classifications) == tuple(
            item.source_identity for item in request.classifications
        )
        assert tuple(item.source_identity for item in forged_classifications) == tuple(
            sorted(item.source_identity for item in forged_classifications)
        )
        forged_request, forged_readiness, _, *chain_records = _rehashed_multi_joint_chain(
            request,
            readiness,
            request_updates={"classifications": forged_classifications},
        )
        records.extend((forged_classification, *chain_records))
        return forged_request, forged_readiness, compilation, records, expected_binding_label

    raise AssertionError(f"unknown R6 substitution: {substitution_id}")


def test_decision_publication_uses_exact_namespace_metadata_and_fresh_resolution(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    service = PromotionManifestService()

    artifact = service.publish_multi_joint_decision(
        store, run=run, request=request, readiness=readiness, compilation=compilation
    )
    manifest = service.resolve_multi_joint_decision(store, artifact.artifact_id)

    assert artifact.artifact_id == f"MULTI-JOINT-PROMOTION-DECISION-{manifest.decision_hash[7:31]}"
    assert artifact.artifact_type is ArtifactType.JSON
    assert artifact.relative_path.endswith("/multi_joint_decision.json")
    assert artifact.producer_tool_name == "mechcad-promotion-manifest"
    assert artifact.producer_tool_version == "1"
    assert artifact.bound_revision == request.source_revision
    assert artifact.bound_state_hash == request.source_state_hash
    assert artifact.input_hash == manifest.decision_hash
    assert artifact.run_id == run.run_id == store.run_id
    content = (tmp_path / artifact.relative_path).read_bytes()
    assert content.endswith(b"\n")
    assert not content.endswith(b"\n\n")
    assert artifact.sha256 == "sha256:" + hashlib.sha256(content).hexdigest()


def test_decision_publication_rejects_mismatched_created_run_and_store_scope(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    service = PromotionManifestService()

    for forged_run in (
        run.model_copy(update={"status": RunStatus.FAILED}),
        run.model_copy(update={"active_revision": run.active_revision + 1}),
        run.model_copy(update={"active_state_hash": HASH_B}),
        run.model_copy(update={"project_id": "OTHER"}),
    ):
        with pytest.raises(ValueError, match="run|binding|scope|project"):
            service.publish_multi_joint_decision(
                store,
                run=forged_run,
                request=request,
                readiness=readiness,
                compilation=compilation,
            )

    wrong_store = ArtifactStore(tmp_path, project_id=request.project_id, run_id="OTHER-RUN")
    with pytest.raises(ValueError, match="scope|run"):
        service.publish_multi_joint_decision(
            wrong_store,
            run=run,
            request=request,
            readiness=readiness,
            compilation=compilation,
        )


def test_decision_resolver_is_artifact_local_and_reloads_typed_manifest(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    service = PromotionManifestService()
    artifact = service.publish_multi_joint_decision(
        store, run=run, request=request, readiness=readiness, compilation=compilation
    )

    resolved = resolve_multi_joint_decision(store, artifact.artifact_id)

    assert resolved.decision_hash
    assert resolved.project_id == store.project_id
    assert resolved.base_revision == request.source_revision
    assert resolved.base_state_hash == request.source_state_hash


def test_decision_resolver_rejects_tampered_manifest_bytes(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    service = PromotionManifestService()
    artifact = service.publish_multi_joint_decision(
        store, run=run, request=request, readiness=readiness, compilation=compilation
    )
    path = tmp_path / artifact.relative_path
    path.write_bytes(path.read_bytes().replace(b"PM-M13-3", b"PM-TAMPERED", 1))

    with pytest.raises(ValueError, match="byte|artifact|manifest"):
        service.resolve_multi_joint_decision(store, artifact.artifact_id)


def test_full_decision_verifier_rebuilds_reference_and_compilation_binding(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    service = PromotionManifestService()
    artifact = service.publish_multi_joint_decision(
        store, run=run, request=request, readiness=readiness, compilation=compilation
    )
    manifest = service.resolve_multi_joint_decision(store, artifact.artifact_id)

    assert verify_multi_joint_promotion_decision(
        manifest, request=request, readiness=readiness, compilation=compilation
    ) is None


def test_original_compilation_projection_identity_and_projection_mapping_accepts_independent_orders(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    assert compilation.projection.canonical_instance_ids != tuple(
        item.canonical_instance_id for item in compilation.mapping
    )

    artifact = PromotionManifestService().publish_multi_joint_decision(
        store, run=run, request=request, readiness=readiness, compilation=compilation
    )
    manifest = resolve_multi_joint_decision(store, artifact.artifact_id)

    assert manifest.projection == compilation.projection
    assert manifest.projection.mapping_identities == compilation.projection.mapping_identities
    assert manifest.mapping == compilation.mapping
    assert verify_multi_joint_promotion_decision(
        manifest, request=request, readiness=readiness, compilation=compilation
    ) is None


@pytest.mark.parametrize(
    "field",
    ["mapping_identities", "classification_identities"],
)
@pytest.mark.parametrize("value", ["abc", "sha256:", "sha256:" + "a" * 63, "sha256:" + "g" * 64])
def test_identity_member_hash_rejects_non_sha256_members(field, value):
    values = (
        (value, HASH_B)
        if field == "mapping_identities"
        else tuple(sorted((HASH_A, value)))
    )
    with pytest.raises(ValueError, match="sha256"):
        _reference(**{field: values})


def test_identity_member_hash_accepts_valid_sha256_members():
    assert _reference().mapping_identities == (HASH_A, HASH_B)


def test_swapped_pairing_full_verifier_rejects_self_consistent_mapping(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    swapped_mapping = tuple(
        type(item).model_validate(
            item.model_dump(mode="json")
            | {
                "canonical_instance_id": other.canonical_instance_id,
                "mapping_hash": "pending",
            }
        )
        for item, other in zip(compilation.mapping, reversed(compilation.mapping), strict=True)
    )
    forged_readiness = type(readiness).model_validate(
        readiness.model_dump(mode="json")
        | {"mapping": swapped_mapping, "readiness_hash": "pending"}
    )
    forged_compilation = CandidatePromotionCompilation.model_validate(
        compilation.model_dump(mode="json")
        | {"mapping": swapped_mapping, "compilation_hash": "pending"}
    )
    reference = _build_multi_joint_decision_input_reference(request, forged_readiness)
    forged_manifest = SelectedMultiJointCandidateDecisionManifest(
        input_reference=reference,
        promotion_policy_hash=request.promotion_policy.policy_hash,
        base_revision=forged_compilation.proposal.base_revision,
        base_state_hash=forged_compilation.proposal.base_state_hash,
        compilation_hash=forged_compilation.compilation_hash,
        promotion_proposal_hash=forged_compilation.promotion_proposal_hash,
        projection_hash=forged_compilation.projection.projection_hash,
        projection=forged_compilation.projection,
        mapping=forged_compilation.mapping,
    )

    with pytest.raises(ValueError, match="match|mapping|binding"):
        verify_multi_joint_promotion_decision(
            forged_manifest,
            request=request,
            readiness=forged_readiness,
            compilation=compilation,
        )


def test_full_decision_verifier_rejects_request_readiness_and_compilation_substitution(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    service = PromotionManifestService()
    artifact = service.publish_multi_joint_decision(
        store, run=run, request=request, readiness=readiness, compilation=compilation
    )
    manifest = service.resolve_multi_joint_decision(store, artifact.artifact_id)

    _, _, _, _, _, request_b, manager_b, compiler_b = _promotion_chain(
        tmp_path / "substitution", values=(0.0, 11.0)
    )
    readiness_b = compiler_b.validate_multi_joint_readiness(request_b)
    compilation_b = compiler_b.compile_multi_joint(
        manager_b.load_current_state(request_b.project_id), request_b
    )

    for supplied_request, supplied_readiness, supplied_compilation in (
        (request_b, readiness, compilation),
        (request, readiness_b, compilation),
        (request, readiness, compilation_b),
    ):
        with pytest.raises(ValueError, match="binding|mismatch|integrity|identity"):
            verify_multi_joint_promotion_decision(
                manifest,
                request=supplied_request,
                readiness=supplied_readiness,
                compilation=supplied_compilation,
            )


@pytest.mark.parametrize(
    "substitution_id",
    R6_SUBSTITUTION_IDS,
    ids=R6_SUBSTITUTION_IDS,
)
def test_full_verifier_rejects_self_consistent_rehash_substitution(
    tmp_path, substitution_id
):
    (
        request,
        readiness,
        compilation,
        candidate,
        realization,
        bridge,
    ) = _verification_inputs_with_chain(tmp_path)
    manifest = SelectedMultiJointCandidateDecisionManifest(
        input_reference=_build_multi_joint_decision_input_reference(request, readiness),
        promotion_policy_hash=request.promotion_policy.policy_hash,
        base_revision=compilation.proposal.base_revision,
        base_state_hash=compilation.proposal.base_state_hash,
        compilation_hash=compilation.compilation_hash,
        promotion_proposal_hash=compilation.promotion_proposal_hash,
        projection_hash=compilation.projection.projection_hash,
        projection=compilation.projection,
        mapping=compilation.mapping,
    )

    forged_request, forged_readiness, forged_compilation, records, expected_binding_label = (
        _build_r6_substitution(
            substitution_id,
            request=request,
            readiness=readiness,
            compilation=compilation,
            candidate=candidate,
            realization=realization,
            bridge=bridge,
        )
    )
    _assert_records_are_self_consistent(
        forged_request, forged_readiness, forged_compilation, *records
    )

    with pytest.raises(ValueError, match=expected_binding_label):
        verify_multi_joint_promotion_decision(
            manifest,
            request=forged_request,
            readiness=forged_readiness,
            compilation=forged_compilation,
        )
