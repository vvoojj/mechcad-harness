from __future__ import annotations

import json
from pathlib import Path

import pytest

from mechcad_harness.application import ProductionApplication
from mechcad_harness.analysis_provenance import ContinuousProofExecutionProvenance
from mechcad_harness.backends.freecad import FreeCADBackend
from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.models.evidence import Evidence
from mechcad_harness.models import Component, DesignState
from mechcad_harness.multi_joint_continuous_clearance import (
    MultiJointContinuousClearanceProofResult,
    MultiJointContinuousClearanceProofResultV2,
    MultiJointContinuousProofStatus,
    continuous_clearance_result_hash,
    multi_joint_continuous_clearance_proof_result_v2_hash,
)
from mechcad_harness.multi_joint_kinematics import JointConfiguration
from mechcad_harness.transient_freecad_measurement import (
    FreeCADTransientAssemblyMeasurementProvider,
)
from mechcad_harness.state import StateManager


def test_m10_4_symbols_are_separate_from_discrete_result():
    from mechcad_harness.multi_joint_collision_sweep import MultiJointCollisionSweepResult

    assert "continuous_path_verified" in MultiJointCollisionSweepResult.model_fields
    assert MultiJointContinuousProofStatus.VERIFIED_CLEAR.value == "verified_clear"


def test_m10_4_provenance_fields_are_optional_for_legacy_payloads():
    from mechcad_harness.analysis_provenance import ContinuousProofExecutionProvenance

    payload = {
        "request_hash": "sha256:req",
        "result_hash": "sha256:result",
        "source_assembly_hash": "sha256:assembly",
        "proof_algorithm_version": "proof@1.0",
        "provider_name": "provider",
        "provider_version": "provider@1.0",
        "execution_mode": "test",
    }
    provenance = ContinuousProofExecutionProvenance(**payload)
    assert provenance.model_hash is None
    assert provenance.path_hash is None


def test_m10_4_evidence_model_retains_existing_shape():
    assert set(Evidence.model_fields) >= {
        "id", "kind", "revision", "state_hash",
        "continuous_proof_execution_provenance",
    }


def test_m10_4_evidence_can_reload_complete_typed_result_payload():
    assert "continuous_multi_joint_clearance_proof_result_payload" in Evidence.model_fields
    assert MultiJointContinuousClearanceProofResult.model_fields["exact_evaluations"]


def test_m10_4_complete_result_payload_survives_evidence_store_reload(tmp_path):
    from tests.unit.test_multi_joint_continuous_clearance import ASSEMBLY, request, service

    dependency_path = tmp_path / "dependencies.json"
    dependency_path.write_text(json.dumps({
        "rules": [{
            "when": ["/components/*"],
            "invalidates": ["analysis.continuous_multi_joint_clearance_proof"],
        }],
        "edges": [],
    }), encoding="utf-8")
    workspace = tmp_path / "workspace"
    StateManager(workspace).create_project(
        "PRJ-M10-4-PERSIST",
        DesignState(id="DES-M10-4-PERSIST", revision=1, components=[Component(id="fixture", name="Fixture")]),
    )
    store = EvidenceStore(workspace, StateManager(workspace), DependencyGraph.from_yaml(dependency_path))
    result = service(lambda received_request, transformed: tuple(
        (moving, stationary, 0.0, 100.0) for moving, stationary in received_request.pairs
    )).execute(request(max_depth=1), ASSEMBLY)
    provenance = ContinuousProofExecutionProvenance(
        request_hash=result.request_hash,
        result_hash=result.result_hash,
        source_assembly_hash=result.source_assembly_hash,
        model_hash=result.model_hash,
        path_hash="sha256:path",
        proof_algorithm_version=result.proof_algorithm_version,
        reach_bound_algorithm_version=result.reach_bound_algorithm_version,
        provider_name="deterministic-test-provider",
        provider_version="deterministic-test@1.0",
        execution_mode="deterministic-injected",
    )
    evidence = Evidence(
        id="EVD-M10-4-PERSIST",
        kind="analysis.continuous_multi_joint_clearance_proof",
        summary="persisted M10-4 result",
        revision=1,
        state_hash="sha256:state",
        producer_name=provenance.provider_name,
        producer_version=provenance.provider_version,
        producer_result_id=result.result_hash,
        input_hash=result.request_hash,
        output_hash=result.result_hash,
        continuous_proof_execution_provenance=provenance,
        continuous_multi_joint_clearance_proof_result_payload=result.model_dump(mode="json"),
    )
    store.write_evidence("PRJ-M10-4-PERSIST", evidence)
    reloaded = store.load_evidence("PRJ-M10-4-PERSIST", evidence.id)
    restored = MultiJointContinuousClearanceProofResult.model_validate(
        reloaded.continuous_multi_joint_clearance_proof_result_payload
    )
    assert restored.result_hash == result.result_hash
    assert restored.result_hash == continuous_clearance_result_hash(restored)
    assert restored.exact_evaluations == result.exact_evaluations
    assert restored.reach_bounds == result.reach_bounds

    tampered_payload = result.model_dump(mode="json")
    tampered_payload["exact_evaluations"][0]["pair_results"][0]["exact_distance_mm"] = 99.0
    tampered = MultiJointContinuousClearanceProofResult.model_validate(tampered_payload)
    assert continuous_clearance_result_hash(tampered) != result.result_hash


def test_m10_4_evidence_write_failure_leaves_no_record(tmp_path, monkeypatch):
    dependency_path = tmp_path / "dependencies.json"
    dependency_path.write_text(json.dumps({
        "rules": [{
            "when": ["/components/*"],
            "invalidates": ["analysis.continuous_multi_joint_clearance_proof"],
        }],
        "edges": [],
    }), encoding="utf-8")
    workspace = tmp_path / "workspace"
    StateManager(workspace).create_project(
        "PRJ-M10-4-FAIL",
        DesignState(id="DES-M10-4-FAIL", revision=1, components=[Component(id="fixture", name="Fixture")]),
    )
    store = EvidenceStore(workspace, StateManager(workspace), DependencyGraph.from_yaml(dependency_path))
    evidence = Evidence(
        id="EVD-M10-4-FAIL",
        kind="analysis.continuous_multi_joint_clearance_proof",
        summary="failure test",
        revision=1,
        state_hash="sha256:state",
    )

    def fail_write(*args, **kwargs):
        raise RuntimeError("durable evidence write failed")

    monkeypatch.setattr(store, "_write_exclusive", fail_write)
    with pytest.raises(RuntimeError, match="durable evidence write failed"):
        store.write_evidence("PRJ-M10-4-FAIL", evidence)
    evidence_path = workspace / "projects" / "PRJ-M10-4-FAIL" / "evidence" / "EVD-M10-4-FAIL.json"
    assert not evidence_path.exists()


def test_v2_production_proof_persists_and_reloads_v2_result(tmp_path, monkeypatch):
    from tests.integration.test_m10_3_provenance import _application, _measure
    from tests.unit.test_m13_3p_rigid_body_groups import _grouped_fk_fixture
    from mechcad_harness.multi_joint_continuous_path import MultiJointPath

    assembly, model = _grouped_fk_fixture()
    def composed_measure(_provider, request, _assembly, _workspace):
        distance = 1.0 if type(_provider.backend) is FreeCADBackend else 999.0
        return tuple(
            (first, second, 0.0, distance)
            for first, second in request.pairs
        )

    def composed_local_radii(_provider, _assembly, instance_ids):
        radius = 1.0 if type(_provider.backend) is FreeCADBackend else 999.0
        return {instance_id: radius for instance_id in instance_ids}

    monkeypatch.setattr(
        FreeCADTransientAssemblyMeasurementProvider,
        "_execute_in_workspace",
        composed_measure,
    )
    monkeypatch.setattr(
        FreeCADTransientAssemblyMeasurementProvider,
        "_component_local_geometry_radii",
        composed_local_radii,
    )
    monkeypatch.setattr(FreeCADBackend, "provenance", lambda _backend: None)
    application = _application(tmp_path)
    provider = application._kinematic_measurement_provider
    provider.provider_name = "spoof-provider"
    provider.provider_version = "spoof-provider@9.0"
    provider.execution_mode = "spoofed"
    provider.provenance = lambda: None
    provider.backend = object()
    source = application.load_state()
    path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(
            JointConfiguration(
                model_id=model.model_id,
                positions={joint.joint_id: 0.0 for joint in model.joints},
            ),
            JointConfiguration(
                model_id=model.model_id,
                positions={joint.joint_id: 1.0 for joint in model.joints},
            ),
        ),
    )
    result = application.prove_continuous_multi_joint_path_clearance_v2(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        path=path,
        exact_pair_scope=(
            ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),
        ),
        max_depth=0,
    )

    assert isinstance(result, MultiJointContinuousClearanceProofResultV2)
    evidence = application.get_multi_joint_continuous_proof_evidence(result.result_hash)
    assert evidence is not None
    assert evidence.continuous_proof_execution_provenance is not None
    assert evidence.continuous_proof_execution_provenance.request_hash == result.request_hash
    assert evidence.continuous_proof_execution_provenance.result_hash == result.result_hash
    assert evidence.continuous_proof_execution_provenance.reach_bound_plumbing_version == result.reach_bound_algorithm_version
    assert evidence.continuous_proof_execution_provenance.provider_name == "freecad-transient-exact"
    assert evidence.continuous_proof_execution_provenance.provider_version == "mechcad-freecad-transient@1.0"
    assert evidence.continuous_proof_execution_provenance.execution_mode == "freecadcmd-subprocess"
    assert result.reach_bounds.for_instance_joint("A2", "J1").local_geometry_radius_mm == 1.0

    reloaded = application.get_multi_joint_continuous_proof_result(result.result_hash)

    assert isinstance(reloaded, MultiJointContinuousClearanceProofResultV2)
    assert reloaded == result
    assert reloaded.result_hash == multi_joint_continuous_clearance_proof_result_v2_hash(reloaded)


def test_v2_continuous_entrypoint_rejects_v1_model(tmp_path):
    from tests.integration.test_m10_3_provenance import _application, _assembly, _measure, _model
    from mechcad_harness.multi_joint_continuous_path import MultiJointPath

    application = _application(tmp_path, measure=_measure)
    model = _model()
    configuration = JointConfiguration(
        model_id=model.model_id,
        positions={joint.joint_id: 0.0 for joint in model.joints},
    )
    path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(configuration, configuration),
    )
    source = application.load_state()

    with pytest.raises(TypeError, match="v2"):
        application.prove_continuous_multi_joint_path_clearance_v2(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=_assembly(),
            model=model,
            path=path,
            exact_pair_scope=(),
        )


def test_v2_proof_entrypoint_exposes_only_explicit_typed_inputs():
    import inspect

    parameters = inspect.signature(
        ProductionApplication.prove_continuous_multi_joint_path_clearance_v2
    ).parameters
    assert tuple(parameters) == (
        "self",
        "source_revision",
        "source_state_hash",
        "assembly",
        "model",
        "path",
        "exact_pair_scope",
        "required_clearance_mm",
        "proof_guard_mm",
        "max_depth",
        "minimum_path_interval",
        "max_exact_evaluations",
    )
    for forbidden in (
        "moving_instance_ids",
        "stationary_instance_ids",
        "evaluator_version",
        "provider_name",
        "provider_version",
        "backend_provenance",
        "measurement_provider",
        "exact_measure",
        "caller_trust_identity",
        "schema_version",
        "proof_version",
    ):
        assert forbidden not in parameters
