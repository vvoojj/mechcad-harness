from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.candidates import (
    CandidateDesignVariable,
    CandidateEvaluationOutcome,
    CandidatePromotionResultManifest,
    CandidatePromotionPolicy,
    CandidatePromotionRequest,
    CandidateSelection,
    PromotionApplicationStatus,
    CandidateSynthesisPolicy,
    result_manifest_hash,
)
from mechcad_harness.candidates.canonical_cad import CanonicalCadIntegrityError
from mechcad_harness.candidates.cad_realization import CandidateCadIntegrityError
from mechcad_harness.changes.operations import ChangeOperation, OperationType
from mechcad_harness.continuous_proof import ContinuousSingleAxisProofStatus
from mechcad_harness.models import ChangeProposal, ProposalStatus
from mechcad_harness.revolute_drive import DriveAdmissibility
from mechcad_harness.runs.models import SourceBinding

from m12_6_acceptance_fixtures import (
    bootstrap_direct_drive_fixture,
    build_direct_requirements,
    build_direct_template,
    build_synthesis_request,
    publish_source_step_inputs,
    direct_drive_state,
    write_project_configuration,
    UninvokedAcceptanceAdapter,
)
from test_m12_candidate_cad_m10_production import (
    FREECAD_CANDIDATE,
    _evaluate_real_candidate,
    _real_candidate,
)
from test_m12_6_end_to_end_direct_drive import (
    _DIRECT_CANDIDATE_POSITIONS,
    _candidate_cad_request,
    _candidate_m10_inputs,
    promotion_classifications,
)
from test_m12_revolute_drive_production import PROJECT_ID, policy_for
from mechcad_harness.application import ProductionApplication
from mechcad_harness.state import StateManager


try:
    _DISCOVERY = discover_freecad()
except Exception:
    _DISCOVERY = None
FREECAD_AVAILABLE = bool((_DISCOVERY is not None and _DISCOVERY.available) or os.path.isfile(FREECAD_CANDIDATE))


def _configure_freecad(monkeypatch):
    discovery = discover_freecad()
    executable = discovery.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE
    monkeypatch.setenv("MECHCAD_FREECADCMD", executable)
    assert discover_freecad().require_available().executable == executable


def _direct_candidate_stage(fixture, positions, *, not_proven=False):
    candidate, synthesis_request, synthesis_policy, m12_result = _real_candidate(
        fixture.app,
        fixture.source_artifacts,
        positions,
    )
    evaluation, cad_request, scope, binding, m10_request = _evaluate_real_candidate(
        fixture.app,
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        not_proven=not_proven,
    )
    return {
        "candidate": candidate,
        "synthesis_request": synthesis_request,
        "synthesis_policy": synthesis_policy,
        "m12_result": m12_result,
        "evaluation": evaluation,
        "cad_request": cad_request,
        "scope": scope,
        "binding": binding,
        "m10_request": m10_request,
    }


def _selection_for(stage, selector="m12-6-failure-selector"):
    candidate = stage["candidate"]
    evaluation = stage["evaluation"]
    return CandidateSelection(
        candidate_hash=candidate.candidate_hash,
        evaluation_hash=evaluation.evaluation_hash,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        selector_identity=selector,
        rationale="isolated failure-boundary selection input",
    )


def _promotion_request(stage, selection, mechanism_id="PM-m12-6-failure"):
    candidate = stage["candidate"]
    return CandidatePromotionRequest(
        project_id=candidate.source_binding.project_id,
        source_revision=candidate.source_binding.source_revision,
        source_state_hash=candidate.source_binding.source_state_hash,
        candidate=candidate,
        synthesis_request=stage["synthesis_request"],
        synthesis_policy=stage["synthesis_policy"],
        m12_3_result=stage["m12_result"],
        evaluation=stage["evaluation"],
        selection=selection,
        promotion_policy=CandidatePromotionPolicy(),
        canonical_target_mechanism_id=mechanism_id,
        classifications=promotion_classifications(candidate),
    )


def _apply_allowed_proposal(
    app,
    source,
    *,
    path,
    value,
    proposal_id="CP-m12-6-failure",
    actor="mechcad-physical-mechanism",
):
    run = app.run_controller.create_run(
        app.project_id,
        expected_source=SourceBinding(
            project_id=app.project_id,
            revision=source.revision,
            state_hash=source.state_hash,
        ),
    )
    proposal = ChangeProposal(
        id=proposal_id,
        title="M12-6 failure boundary source advance",
        status=ProposalStatus.ACCEPTED,
        base_revision=source.revision,
        base_state_hash=source.state_hash,
        actor=actor,
        operations=[
            ChangeOperation(
                operation=OperationType.REPLACE,
                path=path,
                value=value,
            )
        ],
    )
    return app.run_controller.apply_approved_proposal(run.run_id, proposal)


def _fresh_direct_stage(app, source_artifacts):
    source = app.load_state()
    synthesis_request = build_synthesis_request(app, source)
    candidate_template = build_direct_template(source_artifacts)
    variables = list(candidate_template.design_variables)
    variables.extend(
        CandidateDesignVariable(
            name=f"{instance_id}.placement.{axis}",
            value=value,
        )
        for instance_id, position in _DIRECT_CANDIDATE_POSITIONS.items()
        for axis, value in zip(("x_mm", "y_mm", "z_mm"), position, strict=True)
    )
    variables.extend(
        CandidateDesignVariable(name=f"{instance_id}.{axis}", value=value)
        for instance_id, dimensions in {
            "motor-mount": (30.0, 30.0, 5.0),
            "payload-body": (20.0, 20.0, 5.0),
        }.items()
        for axis, value in zip(("length_mm", "width_mm", "thickness_mm"), dimensions, strict=True)
    )
    candidate_template = candidate_template.model_copy(update={"design_variables": tuple(variables)})
    entries = list(policy_for(candidate_template.architecture).entries)
    declared = {entry[0] for entry in entries}
    for variable in variables:
        key = f"allow-design-variable:{variable.name}"
        if key not in declared:
            entries.append(
                (
                    key,
                    json.dumps({"value": variable.value}, sort_keys=True, separators=(",", ":")),
                    "hard_admissibility",
                )
            )
    synthesis_policy = CandidateSynthesisPolicy(entries=tuple(entries))
    m12_outcome = app.realize_and_evaluate_revolute_drive(
        request=synthesis_request,
        policy=synthesis_policy,
        template_input=candidate_template,
        requirements=build_direct_requirements(source, synthesis_request.source_binding),
    )
    assert m12_outcome.construction.candidate is not None
    assert m12_outcome.evaluation is not None
    return _evaluate_promotion_candidate(
        app,
        m12_outcome.construction.candidate,
        synthesis_request,
        synthesis_policy,
        m12_outcome.evaluation,
    )


def _evaluate_promotion_candidate(
    app, candidate, synthesis_request, synthesis_policy, m12_result
):
    cad_request = _candidate_cad_request(candidate)
    cad_stage = app.realize_candidate_cad(
        candidate, synthesis_request, synthesis_policy, cad_request
    )
    scope, binding, m10_request = _candidate_m10_inputs(candidate, cad_stage)
    evaluation = app.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_request,
        m10_request,
        scope,
        binding,
    )
    return {
        "candidate": candidate,
        "synthesis_request": synthesis_request,
        "synthesis_policy": synthesis_policy,
        "m12_result": m12_result,
        "evaluation": evaluation,
        "cad_request": cad_request,
        "scope": scope,
        "binding": binding,
        "m10_request": m10_request,
    }


def _promote_direct_fixture(fixture, mechanism_id="PM-m12-6-failure"):
    candidate, synthesis_request, synthesis_policy, m12_result = _real_candidate(
        fixture.app,
        fixture.source_artifacts,
        dict(_DIRECT_CANDIDATE_POSITIONS),
    )
    stage = _evaluate_promotion_candidate(
        fixture.app,
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
    )
    selection = fixture.app.select_candidate(
        stage["candidate"],
        stage["evaluation"],
        "m12-6-failure-selector",
        "explicitly selected feasible failure-boundary candidate",
    )
    request = _promotion_request(stage, selection, mechanism_id)
    promotion = fixture.app.promote_selected_candidate(request)
    assert promotion.status is PromotionApplicationStatus.PROMOTION_APPLIED, promotion.error
    return stage, selection, request, promotion


def _bootstrap_currentness_fixture(tmp_path):
    workspace, ownership_path, dependency_path = write_project_configuration(tmp_path)
    ownership_path.write_text(
        ownership_path.read_text(encoding="utf-8")
        + "  - path: /yagi_payload_carrier_requirements\n"
        + "    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    StateManager(workspace).create_project(PROJECT_ID, direct_drive_state())
    app = ProductionApplication.create(
        workspace,
        PROJECT_ID,
        UninvokedAcceptanceAdapter(),
        ownership_path=ownership_path,
        dependency_path=dependency_path,
    )
    source = app.load_state()
    source_artifacts = publish_source_step_inputs(app, source)
    return SimpleNamespace(
        app=app,
        source=source,
        source_artifacts=source_artifacts,
        ownership_path=ownership_path,
        dependency_path=dependency_path,
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available")
def test_m12_6_m12_3_insufficient_input_retains_real_inadmissible_outcome(
    tmp_path, monkeypatch
):
    _configure_freecad(monkeypatch)
    fixture = bootstrap_direct_drive_fixture(tmp_path)
    insufficient_motor = fixture.template_input.motor_specification.model_copy(
        update={
            "properties": tuple(
                property_snapshot.model_copy(
                    update={"normalized_value": 6.0, "property_hash": "pending"}
                )
                if property_snapshot.key == "motor.continuous_torque_nm"
                else property_snapshot
                for property_snapshot in fixture.template_input.motor_specification.properties
            ),
            "specification_hash": "pending",
        }
    )

    outcome = fixture.app.realize_and_evaluate_revolute_drive(
        request=fixture.synthesis_request,
        policy=fixture.synthesis_policy,
        template_input=fixture.template_input.model_copy(
            update={"motor_specification": insufficient_motor}
        ),
        requirements=fixture.requirements,
    )

    assert outcome.evaluation is not None
    assert outcome.evaluation.status is DriveAdmissibility.INADMISSIBLE


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available")
def test_m12_6_candidate_collision_is_infeasible_with_collision_witness(
    tmp_path, monkeypatch
):
    _configure_freecad(monkeypatch)
    fixture = bootstrap_direct_drive_fixture(tmp_path)
    positions = dict(_DIRECT_CANDIDATE_POSITIONS)
    positions.update(
        {
            "output-shaft": (0.0, 0.0, 0.0),
            "output-hub": (0.0, 0.0, 0.0),
            "payload-body": (0.0, 0.0, 0.0),
        }
    )

    stage = _direct_candidate_stage(fixture, positions)
    evaluation = stage["evaluation"]

    assert evaluation.outcome is CandidateEvaluationOutcome.INFEASIBLE
    assert (
        evaluation.m10_stage_outcome.pair_proofs[0].result.status
        is ContinuousSingleAxisProofStatus.COLLISION_WITNESS
    )
    with pytest.raises(ValueError, match="FEASIBLE"):
        fixture.app.select_candidate(
            stage["candidate"],
            evaluation,
            "m12-6-collision-selector",
            "must reject collision witness",
        )
    promotion = fixture.app.promote_selected_candidate(
        _promotion_request(stage, _selection_for(stage), "PM-m12-6-collision")
    )
    assert promotion.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert promotion.error and "FEASIBLE" in promotion.error
    assert fixture.app.load_state().revision == fixture.source.revision


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available")
def test_m12_6_candidate_not_proven_is_unresolved_not_infeasible(tmp_path, monkeypatch):
    _configure_freecad(monkeypatch)
    fixture = bootstrap_direct_drive_fixture(tmp_path)

    stage = _direct_candidate_stage(
        fixture,
        dict(_DIRECT_CANDIDATE_POSITIONS),
        not_proven=True,
    )
    evaluation = stage["evaluation"]

    assert evaluation.outcome is CandidateEvaluationOutcome.UNRESOLVED
    assert evaluation.outcome is not CandidateEvaluationOutcome.INFEASIBLE
    assert (
        evaluation.m10_stage_outcome.pair_proofs[0].result.status
        is ContinuousSingleAxisProofStatus.NOT_PROVEN
    )
    with pytest.raises(ValueError, match="FEASIBLE"):
        fixture.app.select_candidate(
            stage["candidate"],
            evaluation,
            "m12-6-not-proven-selector",
            "must reject unresolved proof",
        )
    promotion = fixture.app.promote_selected_candidate(
        _promotion_request(stage, _selection_for(stage), "PM-m12-6-not-proven")
    )
    assert promotion.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert promotion.error and "FEASIBLE" in promotion.error
    assert fixture.app.load_state().revision == fixture.source.revision


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available")
def test_m12_6_source_currentness_rejects_candidate_selection_and_promotion(
    tmp_path, monkeypatch
):
    _configure_freecad(monkeypatch)
    fixture = _bootstrap_currentness_fixture(tmp_path)
    stage = _direct_candidate_stage(fixture, dict(_DIRECT_CANDIDATE_POSITIONS))
    source = fixture.app.load_state()
    changed_requirements = list(source.state.yagi_payload_carrier_requirements)
    changed_requirements[0] = {"value": 101.0, "unit": "rpm"}
    advanced = _apply_allowed_proposal(
        fixture.app,
        source,
        path="/yagi_payload_carrier_requirements",
        value=changed_requirements,
        proposal_id="CP-m12-6-currentness",
        actor="transmission_engineer",
    )
    assert advanced.active_revision == source.revision + 1
    assert advanced.active_state_hash != source.state_hash

    with pytest.raises(CandidateCadIntegrityError, match="not current"):
        fixture.app.realize_candidate_cad(
            stage["candidate"],
            stage["synthesis_request"],
            stage["synthesis_policy"],
            stage["cad_request"],
        )
    with pytest.raises(ValueError, match="current"):
        fixture.app.select_candidate(
            stage["candidate"],
            stage["evaluation"],
            "m12-6-stale-selector",
            "stale candidate must not be selected",
        )

    stale_promotion = fixture.app.promote_selected_candidate(
        _promotion_request(stage, _selection_for(stage), "PM-m12-6-stale")
    )
    assert stale_promotion.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert stale_promotion.error and "stale" in stale_promotion.error.lower()
    assert fixture.app.load_state().revision == source.revision + 1


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available")
def test_m12_6_replay_is_stale_after_later_advance_and_history_remains_verifiable(
    tmp_path, monkeypatch
):
    _configure_freecad(monkeypatch)
    fixture = bootstrap_direct_drive_fixture(tmp_path)
    _stage, _selection, request, promotion = _promote_direct_fixture(fixture)
    immediate_replay = fixture.app.promote_selected_candidate(request)
    assert immediate_replay.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert immediate_replay.error and "stale" in immediate_replay.error.lower()
    assert fixture.app.load_state().revision == promotion.applied_revision
    assert len(fixture.app.load_state().state.physical_mechanisms) == 1
    source_after_promotion = fixture.app.load_state()
    mechanism = source_after_promotion.state.physical_mechanisms[0]
    changed_obligation = mechanism.m10_obligations[0].model_copy(
        update={"required_clearance_mm": 2.0, "obligation_hash": "pending"}
    )
    changed_mechanism = mechanism.model_copy(
        update={
            "m10_obligations": (changed_obligation,),
            "mechanism_hash": "pending",
        }
    )
    later = _apply_allowed_proposal(
        fixture.app,
        source_after_promotion,
        path=f"/physical_mechanisms/{mechanism.id}",
        value=changed_mechanism.model_dump(mode="json"),
        proposal_id="CP-m12-6-later-physical-change",
    )
    assert later.active_revision == source_after_promotion.revision + 1

    result_meta = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id="project-lookup",
    ).existing_in_project(promotion.result_artifact_id)
    assert result_meta is not None
    fresh_app = ProductionApplication.create(
        fixture.app.state_manager.workspace,
        fixture.app.project_id,
        UninvokedAcceptanceAdapter(),
        ownership_path=fixture.ownership_path,
        dependency_path=fixture.dependency_path,
    )
    manifest_store = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id=result_meta.run_id,
    )
    old_result = fresh_app.promotion_manifest_service.resolve_result(
        manifest_store, result_meta.artifact_id
    )
    old_decision = fresh_app.promotion_manifest_service.resolve_decision(
        manifest_store, old_result.decision_artifact_id
    )
    assert old_result.resulting_revision == promotion.applied_revision
    assert old_decision.base_revision == fixture.source.revision
    assert fixture.app.verify_promoted_mechanism(promotion).status.value == "verified"

    replay = fixture.app.promote_selected_candidate(request)
    assert replay.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert replay.error and "stale" in replay.error.lower()
    assert fixture.app.load_state().revision == later.active_revision
    assert len(fixture.app.load_state().state.physical_mechanisms) == 1

    invalidation = fixture.app.evidence_store.load_invalidation(
        fixture.app.project_id, later.active_revision
    )
    assert invalidation.changed_paths == (f"/physical_mechanisms/{mechanism.id}",)
    assert invalidation.directly_invalidated_nodes == (
        "analysis.continuous_clearance_proof",
        "analysis.kinematic_sweep",
    )
    assert invalidation.transitively_invalidated_nodes == (
        "analysis.continuous_clearance_proof",
        "analysis.kinematic_sweep",
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available")
def test_m12_6_valid_fresh_promotion_to_existing_mechanism_is_change_conflict(
    tmp_path, monkeypatch
):
    _configure_freecad(monkeypatch)
    fixture = bootstrap_direct_drive_fixture(tmp_path)
    _stage, _selection, _request, promotion = _promote_direct_fixture(fixture)
    source = fixture.app.load_state()
    mechanism = source.state.physical_mechanisms[0]
    obligation = mechanism.m10_obligations[0].model_copy(
        update={"required_clearance_mm": 2.0, "obligation_hash": "pending"}
    )
    changed_mechanism = mechanism.model_copy(
        update={"m10_obligations": (obligation,), "mechanism_hash": "pending"}
    )
    _apply_allowed_proposal(
        fixture.app,
        source,
        path=f"/physical_mechanisms/{mechanism.id}",
        value=changed_mechanism.model_dump(mode="json"),
        proposal_id="CP-m12-6-target-conflict-advance",
    )
    fresh_source = fixture.app.load_state()
    fresh_artifacts = publish_source_step_inputs(fixture.app, fresh_source)
    stage = _fresh_direct_stage(fixture.app, fresh_artifacts)
    selection = fixture.app.select_candidate(
        stage["candidate"],
        stage["evaluation"],
        "m12-6-target-conflict-selector",
        "fresh candidate remains valid for conflict test",
    )
    conflict = fixture.app.promote_selected_candidate(
        _promotion_request(stage, selection, promotion.request.canonical_target_mechanism_id)
    )
    assert conflict.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert conflict.error and "already exists" in conflict.error
    assert fixture.app.load_state().revision == fresh_source.revision
    assert len(fixture.app.load_state().state.physical_mechanisms) == 1


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available")
def test_m12_6_tampered_selected_source_and_foreign_bytes_fail_closed_without_fallback(
    tmp_path, monkeypatch
):
    _configure_freecad(monkeypatch)
    fixture = bootstrap_direct_drive_fixture(tmp_path)
    _stage, _selection, _request, promotion = _promote_direct_fixture(fixture)
    reconstruction = fixture.app.reconstruct_promoted_mechanism(
        revision=promotion.applied_revision,
        state_hash=promotion.applied_state_hash,
        mechanism_id=promotion.request.canonical_target_mechanism_id,
    )
    selected = fixture.source_artifacts["output-hub"]
    foreign = fixture.source_artifacts["output-shaft"]
    selected_path = fixture.app.state_manager.workspace / selected.relative_path
    foreign_bytes = (
        fixture.app.state_manager.workspace / foreign.relative_path
    ).read_bytes()
    foreign_verified = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id="project-lookup",
    ).read_verified_in_project(
        foreign.artifact_id,
        expected_type=ArtifactType.STEP,
        expected_hash=foreign.sha256,
    )
    assert foreign_verified is not None
    assert foreign_bytes == foreign_verified[1]
    assert selected_path.read_bytes() != foreign_bytes
    selected_path.write_bytes(foreign_bytes)
    assert selected_path.read_bytes() == foreign_bytes

    candidate_calls = []
    monkeypatch.setattr(
        fixture.app.candidate_cad_realization_service,
        "realize",
        lambda *args, **kwargs: candidate_calls.append((args, kwargs)),
    )
    with pytest.raises(CanonicalCadIntegrityError, match="source"):
        fixture.app.canonical_cad_compiler.realize(reconstruction)
    with pytest.raises(ValueError, match="source"):
        fixture.app.reconstruct_promoted_mechanism(
            revision=promotion.applied_revision,
            state_hash=promotion.applied_state_hash,
            mechanism_id=promotion.request.canonical_target_mechanism_id,
        )
    assert candidate_calls == []


@pytest.mark.parametrize("drift", ("joint", "obligation"))
@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available")
def test_m12_6_later_joint_or_obligation_drift_changes_authority_and_request(
    tmp_path, monkeypatch, drift
):
    _configure_freecad(monkeypatch)
    fixture = bootstrap_direct_drive_fixture(tmp_path)
    _stage, _selection, _request, promotion = _promote_direct_fixture(fixture)
    old_reconstruction = fixture.app.reconstruct_promoted_mechanism(
        revision=promotion.applied_revision,
        state_hash=promotion.applied_state_hash,
        mechanism_id=promotion.request.canonical_target_mechanism_id,
    )
    old_cad = fixture.app.canonical_cad_compiler.realize(old_reconstruction)
    old_m10 = fixture.app.canonical_m10_service.execute(old_reconstruction, old_cad)
    mechanism = fixture.app.load_state().state.physical_mechanisms[0]
    if drift == "joint":
        binding = mechanism.joint_bindings[0].model_copy(
            update={
                "axis_frame_reference": "joint:J-1=drifted-axis",
                "binding_hash": "pending",
            }
        )
        changed_mechanism = mechanism.model_copy(
            update={"joint_bindings": (binding,), "mechanism_hash": "pending"}
        )
    else:
        obligation = mechanism.m10_obligations[0].model_copy(
            update={"required_clearance_mm": 2.0, "obligation_hash": "pending"}
        )
        changed_mechanism = mechanism.model_copy(
            update={"m10_obligations": (obligation,), "mechanism_hash": "pending"}
        )
    source = fixture.app.load_state()
    _apply_allowed_proposal(
        fixture.app,
        source,
        path=f"/physical_mechanisms/{mechanism.id}",
        value=changed_mechanism.model_dump(mode="json"),
        proposal_id=f"CP-m12-6-{drift}-drift",
    )
    current = fixture.app.load_state()
    assert current.state_hash != source.state_hash
    assert current.revision == source.revision + 1
    assert (old_m10.request.revision, old_m10.request.state_hash) != (
        current.revision,
        current.state_hash,
    )

    if drift == "joint":
        try:
            fresh_reconstruction = fixture.app.reconstruct_promoted_mechanism(
                revision=current.revision,
                state_hash=current.state_hash,
                mechanism_id=mechanism.id,
            )
            fresh_cad = fixture.app.canonical_cad_compiler.realize(fresh_reconstruction)
            fresh_m10 = fixture.app.canonical_m10_service.execute(fresh_reconstruction, fresh_cad)
        except Exception as exc:
            assert isinstance(exc, (CanonicalCadIntegrityError, ValueError))
            assert "joint" in str(exc).lower() or "binding" in str(exc).lower(), str(exc)
            return
        assert fresh_m10.request.request_hash != old_m10.request.request_hash
        return

    old_obligation = old_reconstruction.mechanism.m10_obligations[0]
    fresh_reconstruction = fixture.app.reconstruct_promoted_mechanism(
        revision=current.revision,
        state_hash=current.state_hash,
        mechanism_id=mechanism.id,
    )
    fresh_cad = fixture.app.canonical_cad_compiler.realize(fresh_reconstruction)
    fresh_m10 = fixture.app.canonical_m10_service.execute(fresh_reconstruction, fresh_cad)
    fresh_obligation = fresh_reconstruction.mechanism.m10_obligations[0]

    assert fresh_obligation.obligation_hash != old_obligation.obligation_hash
    assert fresh_m10.scope.required_clearance_mm != old_m10.scope.required_clearance_mm
    assert fresh_m10.scope.scope_hash != old_m10.scope.scope_hash
    assert fresh_m10.request.scope_hash != old_m10.request.scope_hash
    assert fresh_m10.request.request_hash != old_m10.request.request_hash


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available")
def test_m12_6_manifest_semantics_exclude_operational_run_id_without_duplicate_publication(
    tmp_path, monkeypatch
):
    _configure_freecad(monkeypatch)
    fixture = bootstrap_direct_drive_fixture(tmp_path)
    _stage, _selection, _request, promotion = _promote_direct_fixture(fixture)

    lookup_store = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id="project-lookup",
    )
    result_meta = lookup_store.existing_in_project(promotion.result_artifact_id)
    assert result_meta is not None
    assert result_meta.run_id != "alternate-run"

    result_store = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id=result_meta.run_id,
    )
    verified = result_store.read_verified_strict(
        result_meta.artifact_id,
        expected_type=ArtifactType.JSON,
        expected_hash=result_meta.sha256,
    )
    assert verified is not None
    artifact, content = verified
    manifest = CandidatePromotionResultManifest.model_validate(json.loads(content))

    assert artifact == result_meta
    assert result_manifest_hash(manifest) == manifest.result_hash
    assert result_meta.artifact_id == f"PROMOTION-RESULT-{manifest.result_hash[7:31]}"
    assert "run_id" not in CandidatePromotionResultManifest.model_fields

    alternate_scope = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id="alternate-run",
    )
    reloaded = alternate_scope.read_verified_in_project(
        result_meta.artifact_id,
        expected_type=ArtifactType.JSON,
        expected_hash=result_meta.sha256,
    )
    assert reloaded is not None
    reloaded_artifact, reloaded_content = reloaded
    reloaded_manifest = CandidatePromotionResultManifest.model_validate(
        json.loads(reloaded_content)
    )
    assert reloaded_artifact == artifact
    assert reloaded_content == content
    assert result_manifest_hash(reloaded_manifest) == manifest.result_hash

    published_result_matches = []
    runs_root = (
        fixture.app.state_manager.workspace
        / "projects"
        / fixture.app.project_id
        / "runs"
    )
    for run_dir in sorted(runs_root.iterdir()):
        if run_dir.is_dir():
            run_store = ArtifactStore(
                fixture.app.state_manager.workspace,
                project_id=fixture.app.project_id,
                run_id=run_dir.name,
            )
            found = run_store.existing(promotion.result_artifact_id)
            if found is not None:
                published_result_matches.append(found)
    assert published_result_matches == [result_meta]
