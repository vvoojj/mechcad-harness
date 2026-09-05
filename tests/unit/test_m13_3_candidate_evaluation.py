from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.candidates import (
    CandidateMultiJointM10Evaluation,
    CandidateMultiJointM10EvaluationRequest,
    CandidateMultiJointM10EvaluationScope,
    CandidateMultiJointM10EvaluationService,
    CandidateCurrentness,
)
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.multi_joint_collision_sweep import (
    ExactConstituentPairResultV2,
    MultiJointCollisionConfigurationResultV2,
    MultiJointCollisionSweepResultV2,
    multi_joint_collision_sweep_result_v2_hash,
)
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    MultiJointKinematicsService,
    joint_configuration_hash,
)
from mechcad_harness.models import MultiJointVerificationConfigurationSet

from test_m13_3_bridge_compiler import _compiled_candidate_bridge_with_cad_request


class _CurrentnessVerifier:
    def evaluate_source_binding(self, candidate):
        return CandidateCurrentness.CURRENT


def _scope(bridge, values=(0.0, 10.0)):
    joint_id = bridge.model.joints[0].joint_id
    return CandidateMultiJointM10EvaluationScope(
        configuration_set=MultiJointVerificationConfigurationSet(
            configurations=tuple(
                JointConfiguration(
                    model_id=bridge.model.model_id,
                    positions={joint_id: value},
                )
                for value in values
            )
        ),
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
        scope_identity="candidate-scope:m13-3-task-11",
    )


def _result(request, assembly, *, request_hash=None):
    fk_service = MultiJointKinematicsService()
    configuration_results = []
    for index, configuration in enumerate(request.configurations):
        fk = fk_service.evaluate(assembly, request.model, configuration)
        pairs = tuple(
            ExactConstituentPairResultV2(
                schema_version="exact-constituent-pair-result@2",
                first_instance_id=pair.first_instance_id,
                second_instance_id=pair.second_instance_id,
                interference_volume_mm3=0.0,
                exact_distance_mm=1.0,
                classification=CollisionClassification.POSITIVE_CLEARANCE,
            )
            for pair in request.exact_pair_scope
        )
        configuration_results.append(
            MultiJointCollisionConfigurationResultV2(
                schema_version="multi-joint-collision-configuration-result@2",
                configuration_index=index,
                configuration_hash=joint_configuration_hash(configuration),
                transformed_assembly_hash=fk.transformed_assembly_hash,
                ordered_joint_states=fk.ordered_joint_states,
                instance_world_transforms=fk.instance_world_transforms,
                pair_results=pairs,
                classification=CollisionClassification.POSITIVE_CLEARANCE,
                any_interference=False,
                any_touching=False,
                all_positive_clearance=True,
                minimum_exact_distance_mm=1.0,
            )
        )
    result = MultiJointCollisionSweepResultV2(
        schema_version="multi-joint-collision-sweep-result@2",
        evaluator_version="multi-joint-exact-collision-sweep@2.0",
        source_assembly_hash=request.source_assembly_hash,
        model_hash=request.model_hash,
        request_hash=request_hash or request.request_hash,
        configuration_results=tuple(configuration_results),
        any_interference=False,
        any_touching=False,
        all_positive_clearance=True,
        collision_configuration_indices=(),
        minimum_exact_distance_mm=1.0,
        minimum_distance_configuration_index=0,
    )
    return result.model_copy(
        update={"result_hash": multi_joint_collision_sweep_result_v2_hash(result)}
    )


def _request(tmp_path):
    candidate, cad_request, realization, bridge = _compiled_candidate_bridge_with_cad_request(
        tmp_path
    )
    request_service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessVerifier()
    )
    request = request_service.build_request(
        candidate, realization, bridge, _scope(bridge), cad_request=cad_request
    )
    return candidate, realization, bridge, request


def test_evaluation_has_exact_wire_fields_and_hash_payload(tmp_path):
    candidate, _, _, request = _request(tmp_path)
    evaluation = CandidateMultiJointM10Evaluation(
        project_id=request.project_id,
        source_revision=request.source_revision,
        source_state_hash=request.source_state_hash,
        source_binding_hash=request.source_binding_hash,
        candidate_hash=request.candidate_hash,
        candidate_request_hash=request.request_hash,
        m10_v2_request_hash=request.m10_v2_request_hash,
        m10_v2_result_hash="sha256:" + "a" * 64,
        physical_to_m10_bridge_hash=request.physical_to_m10_bridge_hash,
        m10_model_hash=request.m10_model_hash,
        physical_pair_classification_set_hash=request.physical_pair_classification_set_hash,
        inventory_hash=request.inventory_hash,
        exact_pair_scope_hash=request.exact_pair_scope_hash,
        scope_hash=request.scope_hash,
        configuration_set_hash=request.configuration_set_hash,
    )

    assert candidate.candidate_hash == evaluation.candidate_hash
    assert set(evaluation.model_dump(mode="json")) == {
        "schema_version",
        "project_id",
        "source_revision",
        "source_state_hash",
        "source_binding_hash",
        "candidate_hash",
        "candidate_request_hash",
        "m10_v2_request_hash",
        "m10_v2_result_hash",
        "physical_to_m10_bridge_hash",
        "m10_model_hash",
        "physical_pair_classification_set_hash",
        "inventory_hash",
        "exact_pair_scope_hash",
        "scope_hash",
        "configuration_set_hash",
        "evaluation_hash",
    }
    payload = evaluation.model_dump(mode="json")
    evaluation_hash = payload.pop("evaluation_hash")
    expected = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert evaluation_hash == expected


def test_execute_reconstructs_request_and_reaches_exact_scope(tmp_path):
    candidate, realization, bridge, request = _request(tmp_path)
    calls = []

    def analyze(**kwargs):
        calls.append(kwargs)
        reconstructed = CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
            bridge, realization, request.scope
        )
        return _result(reconstructed, realization.assembly)

    evaluation = CandidateMultiJointM10EvaluationService(
        analyze_multi_joint_collision_sweep_v2=analyze,
        currentness_verifier=_CurrentnessVerifier()
    ).execute(candidate, realization, bridge, request)

    assert isinstance(evaluation, CandidateMultiJointM10Evaluation)
    assert calls[0]["configurations"] == request.scope.configuration_set.configurations
    assert calls[0]["exact_pair_scope"] == bridge.exact_pair_scope
    assert calls[0]["assembly"] == realization.assembly
    assert evaluation.m10_v2_request_hash == request.m10_v2_request_hash
    assert evaluation.m10_v2_result_hash.startswith("sha256:")


def test_execute_rejects_result_bound_to_another_request(tmp_path):
    candidate, realization, bridge, request = _request(tmp_path)
    other_request = CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
        bridge,
        realization,
        _scope(bridge, (0.0, 11.0)),
    )

    def analyze(**kwargs):
        return _result(other_request, realization.assembly)

    with pytest.raises(ValueError, match="result.*request|request.*result"):
        CandidateMultiJointM10EvaluationService(
            analyze_multi_joint_collision_sweep_v2=analyze,
            currentness_verifier=_CurrentnessVerifier()
        ).execute(candidate, realization, bridge, request)


def test_execute_rejects_evaluation_configuration_set_substitution(tmp_path):
    candidate, realization, bridge, request = _request(tmp_path)
    other_scope = _scope(bridge, (0.0, 11.0))

    def analyze(**kwargs):
        reconstructed = CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
            bridge, realization, request.scope
        )
        return _result(reconstructed, realization.assembly)

    with pytest.raises(ValueError, match="configuration-set"):
        CandidateMultiJointM10EvaluationService(
            analyze_multi_joint_collision_sweep_v2=analyze,
            currentness_verifier=_CurrentnessVerifier(),
        ).execute(
            candidate,
            realization,
            bridge,
            request,
            evaluation_configuration_set_hash=other_scope.configuration_set.configuration_set_hash,
        )


def test_execute_does_not_accept_a_caller_authored_m10_request(tmp_path):
    candidate, realization, bridge, request = _request(tmp_path)
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessVerifier(),
        analyze_multi_joint_collision_sweep_v2=lambda **kwargs: pytest.fail(
            "provider must not be reached"
        ),
    )
    with pytest.raises(TypeError):
        service.execute(candidate, realization, bridge, request, m10_request=object())
