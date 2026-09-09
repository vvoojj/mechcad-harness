from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.multi_joint_collision_sweep import (
    multi_joint_collision_sweep_result_v2_hash,
)
from mechcad_harness.candidates import (
    CandidateIntegrityError,
    CandidateMultiJointPromotionRequest,
    PromotionApplicationStatus,
)
from mechcad_harness.state import state_hash

unit_path = str(Path(__file__).parents[1] / "unit")
if unit_path not in sys.path:
    sys.path.insert(0, unit_path)

from test_m13_3_promotion import _promotion_chain


def _application(tmp_path, request, calls):
    ownership = tmp_path / "m13-4p-ownership.yaml"
    dependencies = tmp_path / "m13-4p-dependencies.json"
    ownership.write_text(
        "ownership:\n  - path: /physical_mechanisms/*\n    owner: mechcad-physical-mechanism\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/physical_mechanisms/*"],
                        "invalidates": ["analysis.multi_joint_collision_sweep"],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )

    def measure(exact_request, _assembly):
        calls.append(exact_request)
        return tuple((first, second, 0.0, 1.0) for first, second in exact_request.pairs)

    identity = AgentIdentity(
        agent_name="m13-4p-test-agent",
        agent_version="1.0",
        role="test",
        protocol_version="1.0",
    )
    return ProductionApplication.create(
        tmp_path,
        request.project_id,
        FakeAgentAdapter(identity, scripted_responses=()),
        ownership_path=ownership,
        dependency_path=dependencies,
        kinematic_measure=measure,
    )


def test_production_root_exposes_typed_multi_joint_composition_methods():
    assert hasattr(ProductionApplication, "select_candidate_multi_joint")
    assert hasattr(ProductionApplication, "promote_selected_multi_joint_candidate")
    assert hasattr(ProductionApplication, "verify_multi_joint_promotion_application")


def test_production_root_composes_multi_joint_selection_promotion_and_verification(
    tmp_path, monkeypatch
):
    candidate, cad_realization, bridge, evaluation_request, evaluation, request, _, _ = (
        _promotion_chain(tmp_path)
    )
    calls = []
    app = _application(tmp_path, request, calls)
    source = app.load_state()
    evaluation = app.evaluate_candidate_multi_joint_m10(
        candidate, cad_realization, bridge, evaluation_request
    )
    compiled = []
    original_compile = app.candidate_promotion_compiler.compile_multi_joint

    def observe_compile(state, promotion_request):
        result = original_compile(state, promotion_request)
        compiled.append(result)
        return result

    monkeypatch.setattr(
        app.candidate_promotion_compiler, "compile_multi_joint", observe_compile
    )
    promoted_requests = []
    original_route = app.promotion_application_service._promote_multi_joint_route

    def observe_route(promotion_request):
        promoted_requests.append(promotion_request)
        return original_route(promotion_request)

    monkeypatch.setattr(
        app.promotion_application_service,
        "_promote_multi_joint_route",
        observe_route,
    )
    composition_state = dict(app.__dict__)

    selection = app.select_candidate_multi_joint(
        candidate,
        cad_realization,
        bridge,
        evaluation_request,
        evaluation,
        "m13-4p-selector",
        "independent production replay",
    )
    promotion_request = CandidateMultiJointPromotionRequest.model_validate(
        request.model_copy(
            update={
                "multi_joint_evaluation": evaluation,
                "multi_joint_selection": selection,
                "request_hash": "pending",
            }
        ).model_dump(mode="json")
    )
    receipt = app.promote_selected_multi_joint_candidate(promotion_request)

    assert promoted_requests == [promotion_request]
    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED
    assert receipt.request == promotion_request
    assert receipt.compilation is not None
    assert len(compiled) == 1
    assert receipt.compilation == compiled[0]
    assert receipt.compilation.compilation_hash == compiled[0].compilation_hash
    assert receipt.compilation.projection == compiled[0].projection
    assert (
        receipt.compilation.projection.projection_hash
        == compiled[0].projection.projection_hash
    )
    assert receipt.compilation.mapping == compiled[0].mapping
    assert receipt.decision_artifact_id is not None
    assert receipt.result_artifact_id is not None
    assert receipt.applied_revision == source.revision + 1
    assert receipt.applied_state_hash == state_hash(
        app.state_manager.load_revision(app.project_id, receipt.applied_revision)
    )
    assert len(calls) == 2 * len(evaluation_request.scope.configuration_set.configurations)
    assert app.__dict__ == composition_state
    assert not any(
        hasattr(app, name)
        for name in (
            "latest_run",
            "last_candidate",
            "candidate_result_store",
            "cad_realization",
            "bridge",
        )
    )

    app.verify_multi_joint_promotion_application(receipt)


def test_root_selection_rejects_foreign_candidate_before_replay(tmp_path):
    candidate, cad_realization, bridge, evaluation_request, evaluation, request, _, _ = (
        _promotion_chain(tmp_path)
    )
    calls = []
    app = _application(tmp_path, request, calls)
    evaluation = app.evaluate_candidate_multi_joint_m10(
        candidate, cad_realization, bridge, evaluation_request
    )
    before = len(calls)
    foreign = candidate.model_copy(
        update={
            "source_binding": candidate.source_binding.model_copy(
                update={"project_id": "PRJ-foreign"}
            )
        }
    )

    with pytest.raises(CandidateIntegrityError, match="project"):
        app.select_candidate_multi_joint(
            foreign,
            cad_realization,
            bridge,
            evaluation_request,
            evaluation,
            "selector",
            "replay",
        )

    assert len(calls) == before


def test_root_selection_rejects_replay_result_not_bound_to_evaluation(tmp_path, monkeypatch):
    candidate, cad_realization, bridge, evaluation_request, _, request, _, _ = (
        _promotion_chain(tmp_path)
    )
    app = _application(tmp_path, request, [])
    evaluation = app.evaluate_candidate_multi_joint_m10(
        candidate, cad_realization, bridge, evaluation_request
    )
    original_sweep = app._execute_candidate_v2_sweep

    def different_valid_result(*args, **kwargs):
        result = original_sweep(*args, **kwargs)
        changed = result.model_copy(
            update={
                "minimum_exact_distance_mm": result.minimum_exact_distance_mm + 1.0,
                "result_hash": "pending",
            }
        )
        return changed.model_copy(
            update={"result_hash": multi_joint_collision_sweep_result_v2_hash(changed)}
        )

    monkeypatch.setattr(app, "_execute_candidate_v2_sweep", different_valid_result)

    with pytest.raises(ValueError, match="replay result identity"):
        app.select_candidate_multi_joint(
            candidate,
            cad_realization,
            bridge,
            evaluation_request,
            evaluation,
            "selector",
            "replay result mismatch",
        )


def _completed_receipt(tmp_path):
    candidate, cad_realization, bridge, evaluation_request, _, request, _, _ = (
        _promotion_chain(tmp_path)
    )
    calls = []
    app = _application(tmp_path, request, calls)
    evaluation = app.evaluate_candidate_multi_joint_m10(
        candidate, cad_realization, bridge, evaluation_request
    )
    selection = app.select_candidate_multi_joint(
        candidate,
        cad_realization,
        bridge,
        evaluation_request,
        evaluation,
        "m13-4p-selector",
        "verifier scope test",
    )
    promotion_request = CandidateMultiJointPromotionRequest.model_validate(
        request.model_copy(
            update={
                "multi_joint_evaluation": evaluation,
                "multi_joint_selection": selection,
                "request_hash": "pending",
            }
        ).model_dump(mode="json")
    )
    return app, app.promote_selected_multi_joint_candidate(promotion_request)


def _copy_strict_valid_decision_artifact_to_another_run(tmp_path, receipt):
    locator = ArtifactStore(tmp_path, project_id=receipt.request.project_id, run_id="locator")
    verified = locator.read_verified_in_project(
        receipt.decision_artifact_id, expected_type=ArtifactType.JSON
    )
    assert verified is not None
    artifact, content = verified
    duplicate_store = ArtifactStore(
        tmp_path, project_id=artifact.project_id, run_id="M13-4P-DUPLICATE-RUN"
    )
    duplicate_store.publish(
        artifact.artifact_id,
        artifact.artifact_type,
        artifact.relative_path.rsplit("/", 1)[-1],
        content,
        artifact.producer_tool_name,
        artifact.producer_tool_version,
        artifact.bound_revision,
        artifact.bound_state_hash,
        backend_provenance=artifact.backend_provenance,
        build123d_provenance=artifact.build123d_provenance,
        input_hash=artifact.input_hash,
    )


def _rewrite_decision_artifact_run_id(tmp_path, receipt, run_id):
    locator = ArtifactStore(tmp_path, project_id=receipt.request.project_id, run_id="locator")
    verified = locator.read_verified_in_project(
        receipt.decision_artifact_id, expected_type=ArtifactType.JSON
    )
    assert verified is not None
    artifact, _ = verified
    metadata_path = (tmp_path / artifact.relative_path).parent / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["run_id"] = run_id
    metadata_path.write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def test_root_verifier_locates_decision_scope_from_exact_artifact_id(tmp_path):
    app, receipt = _completed_receipt(tmp_path)

    app.verify_multi_joint_promotion_application(receipt)


def test_root_verifier_rejects_ambiguous_decision_artifact_id(tmp_path):
    app, receipt = _completed_receipt(tmp_path)
    _copy_strict_valid_decision_artifact_to_another_run(tmp_path, receipt)

    with pytest.raises(CandidateIntegrityError, match="missing or ambiguous"):
        app.verify_multi_joint_promotion_application(receipt)


def test_root_verifier_rejects_forged_decision_metadata_run_id(tmp_path):
    app, receipt = _completed_receipt(tmp_path)
    _rewrite_decision_artifact_run_id(tmp_path, receipt, "RUN-forged")

    with pytest.raises(CandidateIntegrityError, match="missing or ambiguous"):
        app.verify_multi_joint_promotion_application(receipt)


def test_legacy_promotion_entry_rejects_multi_joint_request_at_legacy_schema(tmp_path):
    *_, request, __, ___ = _promotion_chain(tmp_path)
    app = _application(tmp_path, request, [])

    with pytest.raises(ValidationError, match="CandidatePromotionRequest"):
        app.promote_selected_candidate(request)
