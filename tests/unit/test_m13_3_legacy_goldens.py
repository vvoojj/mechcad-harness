from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from mechcad_harness.candidates import CandidateEvaluationPolicy, CandidateSelection
from mechcad_harness.models import DesignState
from mechcad_harness.multi_joint_kinematics import JointConfiguration, joint_configuration_hash

from test_m12_candidate_evaluation import (
    _bound_m10_inputs,
    _evaluation_candidate,
    _evaluation_service,
    _m12_result,
)
from test_m12_candidate_foundation import _candidate
from test_m12_canonical_physical_mechanism import _mechanism
from test_m12_promotion_models import _promotion_request


_ROOT = Path(__file__).parents[2]
_PROTECTED_M10_GOLDENS = {
    "src/mechcad_harness/multi_joint_kinematics.py": "sha256:514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f",
    "src/mechcad_harness/multi_joint_pair_scope.py": "sha256:b593e0aa41b50a0dbc84c050f2396e0dba63b621fdd48cf3a7e185120706d344",
    "src/mechcad_harness/multi_joint_collision_sweep.py": "sha256:56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f",
    "src/mechcad_harness/multi_joint_continuous_path.py": "sha256:c063ca8269392b68b911492f72071bdd5f7de30acd4461c98cad045a5574fa9b",
    "src/mechcad_harness/multi_joint_continuous_clearance.py": "sha256:66a62f30a7fe96c40f6cb049bf96906a427931b276ce9847dad42e6f95ad2bc5",
}


def _fixed_state() -> DesignState:
    return DesignState(
        id="DES-M12",
        revision=1,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )


def _json_digest(record) -> str:
    return hashlib.sha256(record.model_dump_json().encode("utf-8")).hexdigest()


def test_protected_m10_sources_match_pre_m13_3_baseline():
    for relative_path, expected in _PROTECTED_M10_GOLDENS.items():
        digest = hashlib.sha256((_ROOT / relative_path).read_bytes()).hexdigest()
        assert f"sha256:{digest}" == expected


def test_joint_configuration_and_canonical_m10_obligation_literals_are_unchanged():
    configuration = JointConfiguration(
        model_id="m13-3p-two-joint-model",
        positions={"joint-1": 0.0, "joint-2": 0.0},
    )
    assert configuration.model_dump_json() == (
        '{"model_id":"m13-3p-two-joint-model","positions":{"joint-1":0.0,"joint-2":0.0}}'
    )
    assert joint_configuration_hash(configuration) == (
        "sha256:5e3e70d8bff9a5352777de2b16545e048313fa9f1e124c60a7e6d72c1c876e9e"
    )

    obligation = _mechanism().m10_obligations[0]
    literal = obligation.model_dump_json()
    assert type(obligation).model_validate_json(literal) == obligation
    assert json.loads(literal)["required_clearance_mm"] == 1.0
    assert obligation.obligation_hash == (
        "sha256:a9f518aa6b47d6723f01edd56661792bd01f7ba2538c99a4d5e84e2d64444289"
    )


def test_m12_candidate_and_canonical_record_hashes_are_immutable():
    state = _fixed_state()
    candidate, synthesis_request, synthesis_policy = _candidate(state)
    assert synthesis_request.request_hash == "sha256:aee76cdc9c5b6c9dd13447c8c5c81538a663e8b751c4655196fb5ffeab82fcba"
    assert synthesis_policy.policy_hash == "sha256:c1c39eab2129bb4885b713596e0644ae8f48e26420266218e35dd2340242b849"
    assert candidate.realization.realization_hash == "sha256:b32be5bb083d31f5eefc6ad76e2866829d7863f7cb668fc5d1f05fd3939b7952"
    assert candidate.candidate_hash == "sha256:9c815e407c3dc1d8ab2af29a36e68ec5824459a21967acb1bece3e4806780ec2"

    evaluation_candidate, evaluation_request, evaluation_policy = _evaluation_candidate(state)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(evaluation_candidate)
    evaluation = _evaluation_service().evaluate(
        evaluation_candidate,
        evaluation_request,
        evaluation_policy,
        _m12_result(evaluation_candidate),
        cad,
        m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    selection = CandidateSelection(
        candidate_hash=evaluation_candidate.candidate_hash,
        evaluation_hash=evaluation.evaluation_hash,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        selector_identity="fixture-selector",
        rationale="fixture selection",
    )
    promotion_request = _promotion_request(
        inputs=(
            evaluation_candidate,
            evaluation_request,
            evaluation_policy,
            _m12_result(evaluation_candidate),
            evaluation,
            selection,
        )
    )

    assert cad.realization.realization_hash == "sha256:228e2940483eca56dc20325489f129e0e292f53f757d3a05636212e259dcf157"
    assert binding.binding_hash == "sha256:16b399eb7cf9cf3e3d7ecbc3d9cdbe14770a3ed5b9076fb1ba091d00dc825a97"
    assert scope.scope_hash == "sha256:6972fbf6c3a7730fabeaff8186b3dbd7edfbf64a8b924db6174daa4c6a4166a2"
    assert m10_request.request_hash == "sha256:e2bf8f52648dec3123729f1a53d20cfd9d5176148a786b3ab14f7a7677e9c422"
    assert m10.outcome_hash == "sha256:b668cea975405d5ef45aa3f8fb963cd4062b322fb873b707fac5d819abfe4852"
    assert evaluation.evaluation_hash == "sha256:95d06e1c713bcd3e4a60c6643e7bc7d3b5912d577e1d5f5897bf70e7ce08acaa"
    assert selection.selection_hash == "sha256:5c8f5bda8a72a82ba130267f152dc97004747813a94546c36580ccc01b4b6e2c"
    assert promotion_request.request_hash == "sha256:4f32742308d998eef387ddddd89920c744e916cbbb26ec5baef3f30cf3b7024c"
    assert _json_digest(_mechanism()) == "4c3eeb1adb6998ddf0d731a452cd3ed49fc1017fa7206474a0f7f64d8de68807"
