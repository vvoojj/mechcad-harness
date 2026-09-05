from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.candidates import (
    CandidateMultiJointM10EvaluationRequest,
    CandidateMultiJointM10EvaluationScope,
    CandidateMultiJointM10EvaluationService,
    validate_multi_joint_verification_configurations,
)
from mechcad_harness.candidates.services import CandidateCurrentness
from mechcad_harness.models import MultiJointVerificationConfigurationSet
from mechcad_harness.multi_joint_kinematics import JointConfiguration

from test_m13_3_bridge_compiler import _compiled_candidate_bridge


class _CurrentnessVerifier:
    def __init__(self, result=CandidateCurrentness.CURRENT):
        self.result = result

    def evaluate_source_binding(self, candidate):
        return self.result


def test_scope_and_configuration_set_have_the_exact_replayable_wire_shapes():
    configuration_set = MultiJointVerificationConfigurationSet(
        configurations=(
            JointConfiguration(model_id="model", positions={"joint-a": 0.0}),
            JointConfiguration(model_id="model", positions={"joint-a": 720.0}),
        )
    )
    scope = CandidateMultiJointM10EvaluationScope(
        configuration_set=configuration_set,
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
        scope_identity="candidate-scope:test",
    )

    assert set(configuration_set.model_dump(mode="json")) == {
        "schema_version",
        "configurations",
        "configuration_hashes",
        "configuration_set_hash",
    }
    assert set(scope.model_dump(mode="json")) == {
        "schema_version",
        "configuration_set",
        "volume_tolerance_mm3",
        "distance_tolerance_mm",
        "scope_identity",
        "scope_hash",
    }
    assert [item["positions"]["joint-a"] for item in scope.model_dump(mode="json")["configuration_set"]["configurations"]] == [0.0, 720.0]
    assert "required_clearance_mm" not in scope.model_dump(mode="json")


def test_candidate_request_is_reconstructed_from_the_embedded_scope(tmp_path):
    candidate, cad_request, realization, bridge = _compiled_candidate_bridge(tmp_path)
    scope = CandidateMultiJointM10EvaluationScope(
        configuration_set=MultiJointVerificationConfigurationSet(
            configurations=(
                JointConfiguration(
                    model_id=bridge.model.model_id,
                    positions={bridge.model.joints[0].joint_id: 0.0},
                ),
                JointConfiguration(
                    model_id=bridge.model.model_id,
                    positions={bridge.model.joints[0].joint_id: 10.0},
                ),
            )
        ),
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
        scope_identity="candidate-scope:test",
    )

    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessVerifier()
    )
    request = service.build_request(
        candidate=candidate,
        cad_realization=realization,
        bridge=bridge,
        scope=scope,
        cad_request=cad_request,
    )

    assert isinstance(request, CandidateMultiJointM10EvaluationRequest)
    assert request.scope == scope
    assert request.configuration_hashes == scope.configuration_set.configuration_hashes
    assert request.m10_v2_request_hash.startswith("sha256:")
    assert request.source_revision == candidate.source_binding.source_revision
    assert request.source_state_hash == candidate.source_binding.source_state_hash
    assert set(request.model_dump(mode="json")) == {
        "schema_version",
        "project_id",
        "source_revision",
        "source_state_hash",
        "source_binding_hash",
        "candidate_hash",
        "physical_mechanism_hash",
        "physical_body_binding_hashes",
        "physical_joint_binding_hashes",
        "kinematic_root_binding_hash",
        "physical_pair_classification_set_hash",
        "physical_to_m10_bridge_hash",
        "cad_realization_hash",
        "cad_mapping_hashes",
        "placement_derivations",
        "placement_derivations_hash",
        "m10_model_hash",
        "inventory_hash",
        "exact_pair_scope_hash",
        "scope",
        "scope_hash",
        "configuration_set_hash",
        "configuration_hashes",
        "m10_v2_request_hash",
        "request_hash",
    }
    payload = request.model_dump(mode="json")
    request_hash = payload.pop("request_hash")
    expected = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert request_hash == expected
    assert service.reconstruct_m10_request(
        candidate, realization, bridge, request, cad_request=cad_request
    ).request_hash == request.m10_v2_request_hash


def test_scope_rejects_unknown_fields_and_invalid_tolerances():
    with pytest.raises(ValueError):
        CandidateMultiJointM10EvaluationScope(
            configuration_set=MultiJointVerificationConfigurationSet(
                configurations=(JointConfiguration(model_id="model", positions={"joint-a": 0.0}),)
            ),
            volume_tolerance_mm3=0.0,
            distance_tolerance_mm=0.0,
            scope_identity="scope",
            required_clearance_mm=1.0,
        )


def test_request_builder_requires_a_currentness_authority():
    with pytest.raises(ValueError, match="currentness verifier"):
        CandidateMultiJointM10EvaluationService()


def test_validator_requires_the_exact_emitted_joint_keys_and_inclusive_limits(tmp_path):
    candidate, _, _, bridge = _compiled_candidate_bridge(tmp_path)
    joint_id = bridge.model.joints[0].joint_id
    assert validate_multi_joint_verification_configurations(
        (JointConfiguration(model_id=bridge.model.model_id, positions={joint_id: -90.0}),),
        bridge,
    )
    with pytest.raises(ValueError, match="joint keys"):
        validate_multi_joint_verification_configurations(
            (JointConfiguration(model_id=bridge.model.model_id, positions={}),), bridge
        )
    with pytest.raises(ValueError, match="limit"):
        validate_multi_joint_verification_configurations(
            (JointConfiguration(model_id=bridge.model.model_id, positions={joint_id: 90.001}),), bridge
        )
    with pytest.raises(ValueError, match="model ID"):
        validate_multi_joint_verification_configurations(
            (JointConfiguration(model_id="wrong", positions={joint_id: 0.0}),), bridge
        )


def test_validator_preserves_raw_multi_turn_values_for_unbounded_joints(tmp_path):
    _, _, _, bridge = _compiled_candidate_bridge(tmp_path)
    joint = bridge.model.joints[0].model_copy(update={"min_angle_deg": None, "max_angle_deg": None})
    model = bridge.model.model_copy(update={"joints": (joint,)})
    command = JointConfiguration(
        model_id=model.model_id,
        positions={joint.joint_id: 1080.5},
    )

    validated = validate_multi_joint_verification_configurations((command,), model)

    assert validated[0].positions[joint.joint_id] == 1080.5


def test_replay_rejects_scope_command_substitution_and_caller_m10_authority(tmp_path):
    candidate, cad_request, realization, bridge = _compiled_candidate_bridge(tmp_path)
    scope = CandidateMultiJointM10EvaluationScope(
        configuration_set=MultiJointVerificationConfigurationSet(
            configurations=(
                JointConfiguration(
                    model_id=bridge.model.model_id,
                    positions={bridge.model.joints[0].joint_id: 0.0},
                ),
            )
        ),
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
        scope_identity="candidate-scope:test",
    )
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessVerifier()
    )
    request = service.build_request(
        candidate, realization, bridge, scope, cad_request=cad_request
    )
    changed_scope = scope.model_copy(
        update={
            "configuration_set": MultiJointVerificationConfigurationSet(
                configurations=(
                    JointConfiguration(
                        model_id=bridge.model.model_id,
                        positions={bridge.model.joints[0].joint_id: 10.0},
                    ),
                )
            ),
            "scope_hash": "pending",
        }
    )
    changed_request = request.model_copy(update={"scope": changed_scope})
    with pytest.raises(ValueError, match="scope hash|trusted source inputs"):
        service.reconstruct_m10_request(
            candidate, realization, bridge, changed_request
        )
    with pytest.raises(TypeError):
        service.build_request(
            candidate,
            realization,
            bridge,
            scope,
            cad_request=cad_request,
            m10_request=object(),
        )


def test_stale_candidate_currentness_is_rejected(tmp_path):
    candidate, cad_request, realization, bridge = _compiled_candidate_bridge(tmp_path)
    scope = CandidateMultiJointM10EvaluationScope(
        configuration_set=MultiJointVerificationConfigurationSet(
            configurations=(
                JointConfiguration(
                    model_id=bridge.model.model_id,
                    positions={bridge.model.joints[0].joint_id: 0.0},
                ),
            )
        ),
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
        scope_identity="candidate-scope:test",
    )
    with pytest.raises(ValueError, match="not current"):
        CandidateMultiJointM10EvaluationService(
            currentness_verifier=_CurrentnessVerifier(
                CandidateCurrentness.STALE_RELATIVE_TO_CURRENT_STATE
            )
        ).build_request(
            candidate, realization, bridge, scope, cad_request=cad_request
        )
