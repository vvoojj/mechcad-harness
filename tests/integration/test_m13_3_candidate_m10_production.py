from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.candidates import (
    CandidateMultiJointM10EvaluationScope,
    CandidateMultiJointM10EvaluationService,
)
from mechcad_harness.models import DesignState
from mechcad_harness.multi_joint_collision_sweep import MultiJointCollisionSweepResultV2
from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair
from mechcad_harness.state import StateManager
from mechcad_harness.models import MultiJointVerificationConfigurationSet
from mechcad_harness.multi_joint_kinematics import JointConfiguration

from test_m13_3p_live_grouped_body_freecad import _configuration, _fixture


PROJECT_ID = "PRJ-M13-3-T11"


def _application(
    tmp_path,
    calls,
    *,
    project_id=PROJECT_ID,
    create_state=True,
    measurement=(0.0, 1.0),
):
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: m13-3-task-11\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/components/*"],
                        "invalidates": ["analysis.multi_joint_collision_sweep"],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    if create_state:
        StateManager(tmp_path).create_project(
            project_id,
            DesignState(id="DES-M13-3-T11", revision=1),
        )

    def recording_measure(request, assembly):
        calls.append((request, assembly))
        return tuple(
            (pair[0], pair[1], measurement[0], measurement[1])
            for pair in request.pairs
        )

    identity = AgentIdentity(
        agent_name="m13-3-task-11-test-agent",
        agent_version="1.0",
        role="m13-3-task-11-test",
        protocol_version="1.0",
    )
    return ProductionApplication.create(
        tmp_path,
        project_id,
        FakeAgentAdapter(identity, scripted_responses=()),
        ownership_path=ownership,
        dependency_path=dependencies,
        kinematic_measure=recording_measure,
    )


def test_production_composes_candidate_multi_joint_m10_service(tmp_path):
    application = _application(tmp_path, [])

    assert isinstance(
        application.candidate_multi_joint_m10_evaluation_service,
        CandidateMultiJointM10EvaluationService,
    )


def test_recording_v2_production_reaches_exact_a2_b1_scope(tmp_path):
    calls = []
    application = _application(tmp_path, calls)
    source = application.load_state()
    assembly, model = _fixture()
    configurations = (
        _configuration(model, 0.0, 0.0),
        _configuration(model, 15.0, 90.0),
    )

    result = application.analyze_multi_joint_collision_sweep_v2(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        configurations=configurations,
        exact_pair_scope=(ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),),
    )

    assert isinstance(result, MultiJointCollisionSweepResultV2)
    assert len(calls) == len(configurations)
    assert all(
        tuple((pair[0], pair[1]) for pair in request.pairs) == (("A2", "B1"),)
        for request, _ in calls
    )
    assert all(
        tuple(
            (pair.first_instance_id, pair.second_instance_id)
            for pair in configuration.pair_results
        ) == (("A2", "B1"),)
        for configuration in result.configuration_results
    )


def test_candidate_evaluation_uses_production_composition_and_binds_recording_result(tmp_path):
    unit_path = str(Path(__file__).parents[1] / "unit")
    if unit_path not in sys.path:
        sys.path.insert(0, unit_path)
    from test_m13_3_bridge_compiler import _compiled_candidate_bridge_with_cad_request

    candidate, cad_request, cad_realization, bridge = _compiled_candidate_bridge_with_cad_request(tmp_path)
    calls = []
    application = _application(
        tmp_path,
        calls,
        project_id=candidate.source_binding.project_id,
        create_state=False,
        measurement=(0.01, 0.0),
    )
    source = application.load_state()
    assert candidate.source_binding.source_revision == source.revision
    assert candidate.source_binding.source_state_hash == source.state_hash
    joint_id = bridge.model.joints[0].joint_id
    scope = CandidateMultiJointM10EvaluationScope(
        configuration_set=MultiJointVerificationConfigurationSet(
            configurations=(
                JointConfiguration(
                    model_id=bridge.model.model_id,
                    positions={joint_id: 0.0},
                ),
                JointConfiguration(
                    model_id=bridge.model.model_id,
                    positions={joint_id: 10.0},
                ),
            )
        ),
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
        scope_identity="candidate-scope:production-composition",
    )
    request = application.candidate_multi_joint_m10_evaluation_service.build_request(
        candidate, cad_realization, bridge, scope, cad_request=cad_request
    )

    evaluation = application.evaluate_candidate_multi_joint_m10(
        candidate, cad_realization, bridge, request
    )
    reconstructed = application.candidate_multi_joint_m10_evaluation_service.reconstruct_m10_request(
        candidate, cad_realization, bridge, request
    )

    assert evaluation.source_revision == source.revision
    assert evaluation.source_state_hash == source.state_hash
    assert evaluation.candidate_request_hash == request.request_hash
    assert evaluation.m10_v2_request_hash == reconstructed.request_hash
    assert len(calls) == 2
    assert all(
        exact_request.pairs
        == tuple(
            (pair.first_instance_id, pair.second_instance_id)
            for pair in bridge.exact_pair_scope
        )
        for exact_request, _ in calls
    )
    assert all(
        exact_request.sweep_request_hash == reconstructed.request_hash
        for exact_request, _ in calls
    )
    assert application.get_multi_joint_collision_sweep_evidence(
        evaluation.m10_v2_result_hash
    ) is not None


def test_candidate_production_entrypoint_proves_scoped_tolerances_and_result_bindings(
    tmp_path, monkeypatch
):
    unit_path = str(Path(__file__).parents[1] / "unit")
    if unit_path not in sys.path:
        sys.path.insert(0, unit_path)
    from test_m13_3_bridge_compiler import _compiled_candidate_bridge_with_cad_request

    candidate, cad_request, cad_realization, bridge = _compiled_candidate_bridge_with_cad_request(tmp_path)
    public_results = []
    application = _application(
        tmp_path,
        [],
        project_id=candidate.source_binding.project_id,
        create_state=False,
        measurement=(0.01, 0.01),
    )
    source = application.load_state()
    public_method = application.analyze_multi_joint_collision_sweep_v2

    def public_spy(self, **kwargs):
        result = public_method(**kwargs)
        public_results.append(result)
        return result

    monkeypatch.setattr(
        ProductionApplication,
        "analyze_multi_joint_collision_sweep_v2",
        public_spy,
    )
    joint_id = bridge.model.joints[0].joint_id
    configuration_set = MultiJointVerificationConfigurationSet(
        configurations=(
            JointConfiguration(
                model_id=bridge.model.model_id,
                positions={joint_id: 0.0},
            ),
        )
    )

    def scope(volume_tolerance, distance_tolerance, identity):
        return CandidateMultiJointM10EvaluationScope(
            configuration_set=configuration_set,
            volume_tolerance_mm3=volume_tolerance,
            distance_tolerance_mm=distance_tolerance,
            scope_identity=identity,
        )

    scopes = (
        scope(0.001, 0.002, "candidate-scope:interference"),
        scope(0.02, 0.002, "candidate-scope:positive-clearance"),
        scope(0.02, 0.02, "candidate-scope:touching"),
    )
    evaluations = []
    requests = []
    for candidate_scope in scopes:
        request = application.candidate_multi_joint_m10_evaluation_service.build_request(
            candidate, cad_realization, bridge, candidate_scope, cad_request=cad_request
        )
        evaluations.append(
            application.evaluate_candidate_multi_joint_m10(
                candidate, cad_realization, bridge, request
            )
        )
        requests.append(request)

    assert len(public_results) == 3
    assert [
        result.configuration_results[0].pair_results[0].classification.value
        for result in public_results
    ] == ["interference", "positive_clearance", "touching"]
    assert all(
        result.request_hash
        == application.candidate_multi_joint_m10_evaluation_service.reconstruct_m10_request(
            candidate, cad_realization, bridge, request
        ).request_hash
        for result, request in zip(public_results, requests, strict=True)
    )
    assert all(
        evaluation.m10_v2_result_hash == result.result_hash
        and evaluation.m10_v2_request_hash == result.request_hash
        and evaluation.source_revision == source.revision
        and evaluation.source_state_hash == source.state_hash
        for evaluation, result in zip(evaluations, public_results, strict=True)
    )
    for evaluation, request, result in zip(
        evaluations, requests, public_results, strict=True
    ):
        evidence = application.get_multi_joint_collision_sweep_evidence(
            evaluation.m10_v2_result_hash
        )
        assert evidence is not None
        assert evidence.input_hash == request.m10_v2_request_hash
        assert evidence.output_hash == result.result_hash
        assert evidence.producer_result_id == result.result_hash
        assert evidence.analysis_execution_provenance is not None
        assert evidence.analysis_execution_provenance.request_hash == request.m10_v2_request_hash
        assert evidence.analysis_execution_provenance.result_hash == result.result_hash


def test_candidate_production_entrypoint_rejects_stale_source_candidate(tmp_path):
    unit_path = str(Path(__file__).parents[1] / "unit")
    if unit_path not in sys.path:
        sys.path.insert(0, unit_path)
    from test_m13_3_bridge_compiler import _compiled_candidate_bridge_with_cad_request

    candidate, cad_request, cad_realization, bridge = _compiled_candidate_bridge_with_cad_request(tmp_path)
    application = _application(
        tmp_path,
        [],
        project_id=candidate.source_binding.project_id,
        create_state=False,
    )
    joint_id = bridge.model.joints[0].joint_id
    request = application.candidate_multi_joint_m10_evaluation_service.build_request(
        candidate,
        cad_realization,
        bridge,
        CandidateMultiJointM10EvaluationScope(
            configuration_set=MultiJointVerificationConfigurationSet(
                configurations=(
                    JointConfiguration(
                        model_id=bridge.model.model_id,
                        positions={joint_id: 0.0},
                    ),
                )
            ),
            volume_tolerance_mm3=0.001,
            distance_tolerance_mm=0.002,
            scope_identity="candidate-scope:stale-source",
        ),
        cad_request=cad_request,
    )
    stale_binding = candidate.source_binding.model_copy(
        update={
            "source_revision": candidate.source_binding.source_revision + 1,
            "source_state_hash": "sha256:" + "f" * 64,
            "consumed_authority": (
                candidate.source_binding.consumed_authority[0].model_copy(
                    update={"value_hash": "sha256:" + "f" * 64}
                ),
                *candidate.source_binding.consumed_authority[1:],
            ),
        }
    )
    stale_candidate = type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "source_binding": stale_binding.model_dump(mode="json"),
            "candidate_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="not current|currentness"):
        application.evaluate_candidate_multi_joint_m10(
            stale_candidate, cad_realization, bridge, request
        )
