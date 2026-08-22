from __future__ import annotations

import json
from pathlib import Path

import pytest

from mechcad_harness.application import ProductionApplication
from mechcad_harness.analysis_provenance import ContinuousProofExecutionProvenance
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.models.evidence import Evidence
from mechcad_harness.models import Component, DesignState
from mechcad_harness.multi_joint_continuous_clearance import (
    MultiJointContinuousClearanceProofResult,
    MultiJointContinuousProofStatus,
    continuous_clearance_result_hash,
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
