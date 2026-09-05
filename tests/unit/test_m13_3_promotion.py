from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.candidates import (
    CandidateMultiJointM10EvaluationRequest,
    CandidateMultiJointM10EvaluationScope,
    CandidateMultiJointPromotionRequest,
    CandidateMultiJointSelection,
    CandidatePromotionCompiler,
    CandidatePromotionPolicy,
    MultiJointPromotionReadiness,
    PromotionClassification,
    PromotionValueClassification,
)
from mechcad_harness.candidates.multi_joint_m10_evaluation import (
    CandidateMultiJointM10EvaluationService,
)
from mechcad_harness.candidates.models import (
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
)
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.models import ChangeProposal, ChangeSet
from mechcad_harness.models import MultiJointVerificationConfigurationSet
from mechcad_harness.multi_joint_kinematics import JointConfiguration
from mechcad_harness.state import StateManager

from test_m12_candidate_evaluation import _m12_result
from test_m13_3_multi_joint_selection import _selection_service
from test_m13_3_bridge_compiler import _compiled_candidate_bridge_with_cad_request
from test_m13_3_candidate_evaluation import _result, _scope
from test_m13_3_candidate_evaluation import _CurrentnessVerifier


def _promotion_chain(tmp_path, *, values=(0.0, 10.0), tolerances=(0.001, 0.002)):
    candidate, cad_request, realization, bridge = _compiled_candidate_bridge_with_cad_request(
        tmp_path
    )
    multi_request = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessVerifier()
    ).build_request(
        candidate,
        realization,
        bridge,
        _scope(bridge, values),
        cad_request=cad_request,
    )
    reconstructed = CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
        bridge, realization, multi_request.scope
    )
    multi_evaluation = CandidateMultiJointM10EvaluationService(
        analyze_multi_joint_collision_sweep_v2=lambda **_: _result(
            reconstructed, realization.assembly
        ),
        currentness_verifier=_CurrentnessVerifier(),
    ).execute(candidate, realization, bridge, multi_request)
    if tolerances != (0.001, 0.002):
        scope = CandidateMultiJointM10EvaluationScope(
            configuration_set=MultiJointVerificationConfigurationSet(
                configurations=tuple(
                    JointConfiguration(
                        model_id=bridge.model.model_id,
                        positions={bridge.model.joints[0].joint_id: value},
                    )
                    for value in values
                )
            ),
            volume_tolerance_mm3=tolerances[0],
            distance_tolerance_mm=tolerances[1],
            scope_identity="candidate-scope:m13-3-task-13",
        )
        multi_request = CandidateMultiJointM10EvaluationService(
            currentness_verifier=_CurrentnessVerifier()
        ).build_request(
            candidate,
            realization,
            bridge,
            scope,
            placement_derivations=multi_request.placement_derivations,
        )
        reconstructed = CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
            bridge, realization, multi_request.scope
        )
        multi_evaluation = CandidateMultiJointM10EvaluationService(
            analyze_multi_joint_collision_sweep_v2=lambda **_: _result(
                reconstructed, realization.assembly
            ),
            currentness_verifier=_CurrentnessVerifier(),
        ).execute(candidate, realization, bridge, multi_request)
    multi_selection = _selection_service(multi_request, realization, bridge).select(
        candidate,
        multi_request,
        multi_evaluation,
        "task-13-selector",
        "Selected exact multi-joint candidate chain.",
    )
    synthesis_request = CandidateSynthesisRequest(source_binding=candidate.source_binding)
    synthesis_policy = CandidateSynthesisPolicy()
    request = CandidateMultiJointPromotionRequest(
        project_id=candidate.source_binding.project_id,
        source_revision=candidate.source_binding.source_revision,
        source_state_hash=candidate.source_binding.source_state_hash,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_3_result=type(_m12_result(candidate)).model_validate(
            _m12_result(candidate)
            .model_copy(update={"design_variables": candidate.design_variables, "result_hash": "pending"})
            .model_dump(mode="json")
        ),
        multi_joint_request=multi_request,
        multi_joint_evaluation=multi_evaluation,
        multi_joint_selection=multi_selection,
        generated_placement_derivations=multi_request.placement_derivations,
        placement_derivations_hash=multi_request.placement_derivations_hash,
        promotion_policy=CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
        canonical_target_mechanism_id="PM-M13-3",
        classifications=(),
    )
    expected = CandidatePromotionCompiler._expected_multi_joint_classifications(request)
    classifications = []
    for identity, item in expected.items():
        classifications.append(
            PromotionClassification(
                source_identity=identity,
                classification=(
                    item.required_classification
                    or (
                        PromotionValueClassification.ACCEPTED_DESIGN_CHOICE
                        if identity.startswith("candidate:design-variable:")
                        else PromotionValueClassification.ACCEPTED_PHYSICAL_FACT
                    )
                ),
                source_value=item.source_value if item.has_source_value else None,
            )
        )
    request = CandidateMultiJointPromotionRequest.model_validate(
        request.model_copy(
            update={
                "classifications": tuple(
                    sorted(classifications, key=lambda item: item.source_identity)
                ),
                "request_hash": "pending",
            }
        ).model_dump(mode="json")
    )
    manager = StateManager(tmp_path)
    compiler = CandidatePromotionCompiler(
        manager,
        lambda project_id: ArtifactStore(
            tmp_path, project_id=project_id, run_id="promotion-lookup"
        ),
        cad_replay_verifier=lambda *args: None,
    )
    return (
        candidate,
        realization,
        bridge,
        multi_request,
        multi_evaluation,
        request,
        manager,
        compiler,
    )


def test_multi_joint_promotion_request_and_readiness_have_exact_frozen_fields(tmp_path):
    _, _, _, _, _, request, _, compiler = _promotion_chain(tmp_path)

    assert set(request.model_dump(mode="json")) == {
        "schema_version",
        "project_id",
        "source_revision",
        "source_state_hash",
        "candidate",
        "synthesis_request",
        "synthesis_policy",
        "m12_3_result",
        "generated_placement_derivations",
        "placement_derivations_hash",
        "multi_joint_request",
        "multi_joint_evaluation",
        "multi_joint_selection",
        "promotion_policy",
        "canonical_target_mechanism_id",
        "classifications",
        "m11_target_intent",
        "request_hash",
    }
    payload = request.model_dump(mode="json")
    actual_hash = payload.pop("request_hash")
    expected_hash = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert actual_hash == expected_hash

    readiness = compiler.validate_multi_joint_readiness(request)
    assert isinstance(readiness, MultiJointPromotionReadiness)
    assert set(readiness.model_dump(mode="json")) == {
        "schema_version",
        "project_id",
        "source_revision",
        "source_state_hash",
        "source_binding_hash",
        "request_hash",
        "candidate_hash",
        "synthesis_request_hash",
        "synthesis_policy_hash",
        "m12_3_result_hash",
        "multi_joint_evaluation_hash",
        "multi_joint_selection_hash",
        "scope_hash",
        "configuration_set_hash",
        "promotion_policy_hash",
        "canonical_target_mechanism_id",
        "mapping",
        "classification_identities",
        "trusted_geometry_artifact_ids",
        "readiness_hash",
    }


def test_multi_joint_promotion_projects_complete_physical_pairs_and_obligation_only(tmp_path):
    candidate, _, _, multi_request, _, request, manager, compiler = _promotion_chain(tmp_path)

    compilation = compiler.compile_multi_joint(
        manager.load_current_state(request.project_id), request
    )
    mechanism = compilation.canonical_mechanism
    assert mechanism.schema_version == "canonical-physical-mechanism@3"
    assert mechanism.physical_rigid_body_bindings
    assert mechanism.physical_revolute_joint_bindings
    assert len(mechanism.physical_pair_classification_bindings) == len(
        candidate.realization.physical_pair_classification_bindings
    )
    assert mechanism.multi_joint_verification_obligations[0].configuration_set == (
        multi_request.scope.configuration_set
    )
    assert mechanism.multi_joint_verification_obligations[0].volume_tolerance_mm3 == 0.001
    assert "bridge" not in json.dumps(mechanism.model_dump(mode="json"))
    assert "inventory" not in json.dumps(mechanism.model_dump(mode="json"))
    assert isinstance(compilation.proposal, ChangeProposal)


def test_multi_joint_promotion_preserves_pair_classification_and_reason(tmp_path):
    candidate, _, _, _, _, request, manager, compiler = _promotion_chain(tmp_path)
    compilation = compiler.compile_multi_joint(
        manager.load_current_state(request.project_id), request
    )
    candidate_pairs = {
        (item.first_physical_instance_id, item.second_physical_instance_id): item
        for item in candidate.realization.physical_pair_classification_bindings
    }
    canonical_pairs = {
        (item.first_physical_instance_id, item.second_physical_instance_id): item
        for item in compilation.canonical_mechanism.physical_pair_classification_bindings
    }
    mapping = {item.candidate_instance_id: item.canonical_instance_id for item in compilation.mapping}
    for (first, second), pair in candidate_pairs.items():
        projected = canonical_pairs[(mapping[first], mapping[second])]
        assert projected.classification == pair.classification
        assert projected.exclusion_reason == pair.exclusion_reason

    obligation_identity = (
        f"candidate:multi-joint-verification-obligation:{request.multi_joint_request.scope_hash}"
    )
    obligation = next(
        item for item in request.classifications if item.source_identity == obligation_identity
    )
    assert obligation.classification is PromotionValueClassification.CANONICAL_REDERIVATION_INPUT
    assert obligation.source_value == request.multi_joint_request.scope_hash


def test_multi_joint_promotion_rejects_evaluated_set_a_with_set_b_request(tmp_path):
    values = _promotion_chain(tmp_path, values=(0.0, 10.0))
    candidate, _, _, _, evaluation_a, request_a, _, compiler = values
    _, _, _, request_b, _, _, _, _ = _promotion_chain(tmp_path / "b", values=(0.0, 11.0))
    forged = request_a.model_copy(
        update={"multi_joint_request": request_b, "request_hash": "pending"}
    )
    with pytest.raises(ValueError, match="configuration|request|evaluation|selection|binding"):
        compiler.validate_multi_joint_readiness(
            CandidateMultiJointPromotionRequest.model_validate(forged.model_dump(mode="json"))
        )
    assert evaluation_a.configuration_set_hash != request_b.configuration_set_hash


def test_multi_joint_promotion_rejects_rehashed_selection_with_forged_m10_result(tmp_path):
    _, _, _, _, evaluation, request, _, compiler = _promotion_chain(tmp_path)
    forged_selection = CandidateMultiJointSelection.model_validate(
        request.multi_joint_selection.model_copy(
            update={
                "m10_v2_result_hash": "sha256:" + "0" * 64,
                "selection_hash": "pending",
            }
        ).model_dump(mode="json")
    )
    forged_request = CandidateMultiJointPromotionRequest.model_validate(
        request.model_copy(
            update={"multi_joint_selection": forged_selection, "request_hash": "pending"}
        ).model_dump(mode="json")
    )

    assert forged_selection.selection_hash != request.multi_joint_selection.selection_hash
    assert forged_selection.m10_v2_result_hash != evaluation.m10_v2_result_hash
    with pytest.raises(ValueError, match="result|binding"):
        compiler.validate_multi_joint_readiness(forged_request)


def test_multi_joint_readiness_direct_model_rejects_duplicate_geometry_artifact_ids(tmp_path):
    _, _, _, _, _, request, _, compiler = _promotion_chain(tmp_path)
    readiness = compiler.validate_multi_joint_readiness(request)
    payload = readiness.model_dump(mode="json")
    payload.update(
        {
            "trusted_geometry_artifact_ids": ("artifact-a", "artifact-a"),
            "readiness_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="unique"):
        MultiJointPromotionReadiness.model_validate(payload)


def test_multi_joint_readiness_direct_model_rejects_unsorted_geometry_artifact_ids(tmp_path):
    _, _, _, _, _, request, _, compiler = _promotion_chain(tmp_path)
    readiness = compiler.validate_multi_joint_readiness(request)
    payload = readiness.model_dump(mode="json")
    payload.update(
        {
            "trusted_geometry_artifact_ids": ("artifact-z", "artifact-a"),
            "readiness_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="lexically sorted"):
        MultiJointPromotionReadiness.model_validate(payload)


def test_multi_joint_promotion_tolerance_change_changes_scope_obligation_and_rejects_old_chain(tmp_path):
    _, _, _, multi_request_a, _, promotion_a, _, compiler = _promotion_chain(tmp_path)
    _, _, _, multi_request_b, _, promotion_b, _, _ = _promotion_chain(
        tmp_path / "b", tolerances=(0.003, 0.002)
    )
    assert multi_request_a.scope.scope_hash != multi_request_b.scope.scope_hash
    assert (
        f"candidate:multi-joint-verification-obligation:{multi_request_a.scope.scope_hash}"
        != f"candidate:multi-joint-verification-obligation:{multi_request_b.scope.scope_hash}"
    )
    forged = promotion_a.model_copy(
        update={"multi_joint_request": multi_request_b, "request_hash": "pending"}
    )
    with pytest.raises(ValueError, match="scope|configuration|request|selection|binding"):
        compiler.validate_multi_joint_readiness(
            CandidateMultiJointPromotionRequest.model_validate(forged.model_dump(mode="json"))
        )
    assert promotion_b.request_hash != promotion_a.request_hash


def test_multi_joint_compilation_uses_the_normal_changeproposal_changeset_route(tmp_path):
    _, _, _, _, _, request, manager, compiler = _promotion_chain(tmp_path)
    compilation = compiler.compile_multi_joint(
        manager.load_current_state(request.project_id), request
    )
    engine = ChangeEngine(
        manager,
        OwnershipPolicy(
            [{"path": "/physical_mechanisms", "owner": "mechcad-physical-mechanism"}]
        ),
    )
    _, _, changeset = engine.prepare_proposal(request.project_id, compilation.proposal)
    assert isinstance(changeset, ChangeSet)
    assert changeset.proposal_id == compilation.proposal.id
