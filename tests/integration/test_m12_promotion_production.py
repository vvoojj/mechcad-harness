from __future__ import annotations

import json
import hashlib
import os
import weakref
from types import SimpleNamespace

import pytest

from mechcad_harness.application import ProductionApplication, _PromotionVerificationContext
from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.candidates import (
    CandidatePromotionApplicationService,
    CandidateDesignVariable,
    CandidatePromotionPolicy,
    CandidatePromotionRequest,
    PostPromotionM11TargetIntent,
    PromotionClassification,
    PromotionValueClassification,
    PromotedMechanismVerificationStatus,
)
from mechcad_harness.candidates.canonical_m10 import (
    CanonicalM10ScopeEquivalenceService,
    CanonicalM10VerificationStatus,
)
from mechcad_harness.candidates.canonical_mechanism import normalized_projection
from mechcad_harness.candidates.m11_handoff import (
    CanonicalM11HandoffStatus,
    build_handoff_request,
)
from mechcad_harness.agents.models import AgentAdapterIdentity
from mechcad_harness.models import Component, DesignState
from mechcad_harness.models import CanonicalMechanicalConnectionKind
from mechcad_harness.revolute_drive import DriveArchitecture
from mechcad_harness.state import StateManager, canonical_json, state_hash

from test_m12_candidate_cad_m10_production import (
    FREECAD_CANDIDATE,
    _evaluate_real_candidate,
    _publish_gear_step,
    _publish_source_step,
    _real_candidate,
)
import test_m12_candidate_cad_m10_production as m12_4
_M12_4_M10_INPUTS = m12_4._m10_inputs
GEAR_AVAILABLE = m12_4.GEAR_AVAILABLE
from test_m12_revolute_drive_production import (
    PROJECT_ID,
    UninvokedAgentAdapter,
    production_state,
)


try:
    _FREECAD_DISCOVERY = discover_freecad()
except Exception:
    _FREECAD_DISCOVERY = None
FREECAD_AVAILABLE = bool(
    (_FREECAD_DISCOVERY is not None and _FREECAD_DISCOVERY.available)
    or os.path.isfile(FREECAD_CANDIDATE)
)


class _CompositionAdapter:
    identity = AgentAdapterIdentity(adapter_name="integration", adapter_version="1")

    def invoke(self, _request):
        raise AssertionError("composition test must not invoke the adapter")


def _semantic_identity(value):
    payload = json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_application(tmp_path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    StateManager(workspace).create_project(
        "PRJ-production",
        DesignState(
            id="DES-production",
            revision=1,
            components=[Component(id="PRT-bracket", name="Bracket")],
        ),
    )

    from mechcad_harness.application import ProductionApplication

    return ProductionApplication.create(
        workspace,
        "PRJ-production",
        _CompositionAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def test_production_promotion_entrypoint_uses_composed_orchestrator(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    request = SimpleNamespace(project_id=application.project_id)
    events = []
    expected = object()

    monkeypatch.setattr(
        application.promotion_application_service,
        "promote_selected_candidate",
        lambda supplied: events.append(("promotion", supplied)) or expected,
    )
    monkeypatch.setattr(
        application.change_engine,
        "apply_proposal",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("ProductionApplication must not apply proposals directly")
        ),
    )

    assert application.promote_selected_candidate(request) is expected
    assert events == [("promotion", request)]
    assert isinstance(application.promotion_application_service, CandidatePromotionApplicationService)


def _build_promotion_live_application(tmp_path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n"
        "  - path: /requirements/*\n"
        "    owner: transmission_engineer\n"
        "  - path: /physical_mechanisms/*\n"
        "    owner: mechcad-physical-mechanism\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/physical_mechanisms/*"],
                        "invalidates": [
                            "analysis.continuous_clearance_proof",
                            "analysis.kinematic_sweep",
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    StateManager(workspace).create_project(PROJECT_ID, production_state())
    return ProductionApplication.create(
        workspace,
        PROJECT_ID,
        UninvokedAgentAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def _build_external_promotion_application(tmp_path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n"
        "  - path: /requirements/*\n"
        "    owner: transmission_engineer\n"
        "  - path: /physical_mechanisms/*\n"
        "    owner: mechcad-physical-mechanism\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/requirements/*"],
                        "invalidates": [
                            "analysis.continuous_clearance_proof",
                            "analysis.kinematic_sweep",
                        ],
                    },
                    {
                        "when": ["/physical_mechanisms/*"],
                        "invalidates": [
                            "analysis.continuous_clearance_proof",
                            "analysis.kinematic_sweep",
                        ],
                    },
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    StateManager(workspace).create_project(PROJECT_ID, production_state())
    return ProductionApplication.create(
        workspace,
        PROJECT_ID,
        UninvokedAgentAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
        additional_tool_registrations=m12_4.GearworksTools.registrations(),
    )


def _promotion_classifications(candidate):
    values = []

    def add(value):
        if value.source_identity not in {item.source_identity for item in values}:
            values.append(value)

    for specification in candidate.component_specifications:
        for prop in specification.properties:
            add(
                PromotionClassification(
                    source_identity=f"candidate:property:{specification.source_identity}:{prop.key}",
                    classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                    source_value=(
                        prop.normalized_value
                        if prop.normalized_value is not None
                        else tuple(prop.normalized_range)
                        if prop.normalized_range is not None
                        else None
                    ),
                )
            )
        if specification.geometry_source is not None:
            add(
                PromotionClassification(
                    source_identity=(
                        f"candidate:geometry-source:{specification.geometry_source.artifact_id}"
                    ),
                    classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                    source_value=specification.geometry_source.artifact_hash,
                )
            )
    for variable in candidate.design_variables:
        add(
            PromotionClassification(
                source_identity=f"candidate:design-variable:{variable.name}",
                classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
                source_value=variable.value,
            )
        )
    for component in candidate.realization.components:
        add(
            PromotionClassification(
                source_identity=f"candidate:physical-instance:{component.instance_id}",
                classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            )
        )
    for connection in candidate.realization.connections:
        add(
            PromotionClassification(
                source_identity=f"candidate:connection:{connection.connection_id}",
                classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            )
        )
    for binding in candidate.realization.joint_bindings:
        add(
            PromotionClassification(
                source_identity=f"candidate:joint-binding:{binding.joint_id}",
                classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            )
        )
    return tuple(values)


class _NoStructuralExecution:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def unexpected(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            raise AssertionError(f"M11 structural execution must not run: {name}")

        return unexpected


def _task17_m10_inputs(candidate, cad_stage, *, external_spur=False, home=False):
    """Use the existing live helper with promotion-resolvable pair semantics."""
    original_scope, original_binding, original_request = _M12_4_M10_INPUTS(
        candidate, cad_stage, external_spur=external_spur, home=home
    )
    joint_id = candidate.realization.joint_bindings[0].joint_id
    model = original_binding.model.model_copy(
        update={
            "joints": (
                original_binding.model.joints[0].model_copy(update={"joint_id": joint_id}),
            )
        }
    )
    dispositions = tuple(
        item.model_copy(
            update={
                "output_transform_group": (
                    joint_id
                    if item.disposition is m12_4.CandidateM10BodyDisposition.OUTPUT_RIGID
                    else None
                ),
                "disposition_hash": "pending",
            }
        )
        for item in original_binding.constituent_dispositions
    )
    binding = type(original_binding).model_validate(
        original_binding.model_dump(mode="json")
        | {
            "model": model.model_dump(mode="json"),
            "model_hash": "pending",
            "output_joint_id": joint_id,
            "output_axis": original_binding.output_axis.model_dump(mode="json")
            | {"frame_id": f"joint:{joint_id}"},
            "constituent_dispositions": [item.model_dump(mode="json") for item in dispositions],
            "binding_hash": "pending",
        }
    )
    first_constituent_key = "output-shaft"
    second_constituent_key = "bearing-a" if external_spur else "drive-motor"
    fidelity_keys = (
        ("output-shaft", "trusted_source_geometry"),
        ("bearing-a", "trusted_source_geometry"),
    ) if external_spur else (
        ("output-shaft", "trusted_source_geometry"),
        ("drive-motor", "trusted_source_geometry"),
    )
    scope = type(original_scope).model_validate(
        {
            **original_scope.model_dump(mode="json"),
            "pair_scope_requirements": [
                {
                    "requirement_key": "shaft-motor-clearance",
                    "first_constituent_key": first_constituent_key,
                    "second_constituent_key": second_constituent_key,
                    "required_classification": "check_clearance",
                }
            ],
            "fidelity_requirements": [list(item) for item in fidelity_keys],
            "scope_hash": "pending",
        }
    )
    inventory = m12_4.CandidateCollisionPairInventory.complete_for(
        cad_stage.realization, binding, scope
    )
    request = type(original_request).model_validate(
        original_request.model_dump(mode="json")
        | {
            "binding_hash": binding.binding_hash,
            "scope_hash": scope.scope_hash,
            "model_hash": binding.model_hash,
            "inventory": inventory.model_dump(mode="json"),
            "request_hash": "pending",
        }
    )
    return scope, binding, request


@pytest.mark.skipif(
    not FREECAD_AVAILABLE,
    reason="FreeCAD is not available through deterministic discovery",
)
@pytest.mark.parametrize(
    ("m11_intent", "expected_m11_status"),
    (
        (PostPromotionM11TargetIntent(target_scope="whole_mechanism"), CanonicalM11HandoffStatus.NOT_ELIGIBLE),
        (
            PostPromotionM11TargetIntent(
                target_scope="single_component",
                candidate_instance_id="motor-mount",
            ),
            CanonicalM11HandoffStatus.UNRESOLVED,
        ),
    ),
)
def test_live_direct_drive_promotion_rebinds_canonical_cad_m10_and_non_gating_m11(
    tmp_path,
    monkeypatch,
    m11_intent,
    expected_m11_status,
):
    discovery = discover_freecad()
    executable = discovery.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE
    monkeypatch.setenv("MECHCAD_FREECADCMD", executable)
    runtime = discover_freecad().require_available()
    print(
        "M12_5_RUNTIME="
        + json.dumps(
            {
                "available": runtime.available,
                "executable": runtime.executable,
                "version": runtime.version,
                "importable": runtime.importable,
                "execution_boundary": runtime.execution_boundary,
            },
            sort_keys=True,
        )
    )


    application = _build_promotion_live_application(tmp_path)
    monkeypatch.setattr(m12_4, "_m10_inputs", _task17_m10_inputs)
    source_before = application.load_state()
    original_revision_path = application.state_manager._revision_path(
        application.project_id, source_before.revision
    )
    original_revision_bytes = original_revision_path.read_bytes()
    original_state = source_before.state.model_copy(deep=True)
    original_state_identity = state_hash(original_state)
    source_artifacts = {
        instance_id: _publish_source_step(
            application,
            part_id=f"promotion-task-17-{instance_id}",
            size=(20.0 + index, 20.0, 5.0),
        )
        for index, instance_id in enumerate(
            ("drive-motor", "output-shaft", "bearing-a", "bearing-b", "output-hub")
        )
    }
    source_bytes = {
        artifact_id: (
            application.state_manager.workspace / artifact.relative_path
        ).read_bytes()
        for artifact_id, artifact in source_artifacts.items()
    }

    positions = {
        "drive-motor": (100.0, 100.0, 0.0),
        "output-shaft": (80.0, 0.0, 0.0),
        "bearing-a": (90.0, 30.0, 0.0),
        "bearing-b": (90.0, -30.0, 0.0),
        "output-hub": (80.0, 0.0, 0.0),
        "motor-mount": (0.0, 0.0, 0.0),
        "payload-body": (80.0, 0.0, 0.0),
    }
    candidate, synthesis_request, synthesis_policy, m12_result = _real_candidate(
        application, source_artifacts, positions
    )
    evaluation, candidate_cad_request, _candidate_scope, _candidate_binding, candidate_m10_request = (
        _evaluate_real_candidate(
            application,
            candidate,
            synthesis_request,
            synthesis_policy,
            m12_result,
        )
    )
    assert m12_result.status.value == "admissible"
    assert evaluation.outcome.value == "feasible"
    assert evaluation.m10_stage_outcome.pair_proofs[0].result.status.value == "verified_clear"
    assert evaluation.cad_stage_outcome.realization is not None
    assert evaluation.cad_stage_outcome.realization.verified_source_content_identities
    assert evaluation.cad_stage_outcome.realization.assembly.imported_components
    selection = application.select_candidate(
        candidate,
        evaluation,
        "task-17-selector",
        "explicitly selected accepted direct-drive feasible candidate",
    )
    request = CandidatePromotionRequest(
        project_id=application.project_id,
        source_revision=source_before.revision,
        source_state_hash=source_before.state_hash,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_3_result=m12_result,
        evaluation=evaluation,
        selection=selection,
        promotion_policy=CandidatePromotionPolicy(),
        canonical_target_mechanism_id="PM-task17-direct-drive",
        classifications=_promotion_classifications(candidate),
        m11_target_intent=m11_intent,
    )

    application_result = application.promote_selected_candidate(request)
    assert application_result.status.value == "promotion_applied", application_result.error
    assert application_result.applied_revision == source_before.revision + 1
    assert application_result.applied_state_hash != source_before.state_hash
    assert application_result.compilation is not None
    assert len(application_result.compilation.proposal.operations) == 1
    assert application_result.compilation.proposal.operations[0].path == (
        "/physical_mechanisms/PM-task17-direct-drive"
    )

    decision_artifact = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id="project-lookup",
    ).existing_in_project(application_result.decision_artifact_id)
    result_artifact = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id="project-lookup",
    ).existing_in_project(application_result.result_artifact_id)
    assert decision_artifact is not None
    assert result_artifact is not None
    assert decision_artifact.run_id == result_artifact.run_id
    manifest_store = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id=decision_artifact.run_id,
    )
    decision = application.promotion_manifest_service.resolve_decision(
        manifest_store, decision_artifact.artifact_id
    )
    result_manifest = application.promotion_manifest_service.resolve_result(
        manifest_store, result_artifact.artifact_id
    )
    assert decision.base_revision == source_before.revision
    assert decision.base_state_hash == source_before.state_hash
    assert result_manifest.resulting_revision == source_before.revision + 1
    assert result_manifest.resulting_state_hash == application_result.applied_state_hash
    assert all(
        "run_id" not in json.dumps(value.model_dump(mode="json"), sort_keys=True)
        for value in (request, application_result.compilation, decision, result_manifest)
    )

    run = application.run_controller.get_run(decision_artifact.run_id, application.project_id)
    assert (
        run.initial_revision,
        run.initial_state_hash,
        run.active_revision,
        run.active_state_hash,
    ) == (
        source_before.revision,
        source_before.state_hash,
        source_before.revision + 1,
        application_result.applied_state_hash,
    )
    invalidation = application.evidence_store.load_invalidation(
        application.project_id, application_result.applied_revision
    )
    assert invalidation.parent_revision == source_before.revision
    assert invalidation.revision == source_before.revision + 1
    assert tuple(invalidation.changed_paths) == (
        "/physical_mechanisms/PM-task17-direct-drive",
    )
    assert invalidation.changeset_id
    assert result_manifest.changeset_id == invalidation.changeset_id
    assert result_manifest.proposal_id == application_result.compilation.proposal.id
    assert result_manifest.changed_paths == tuple(invalidation.changed_paths)

    source_after = application.load_state()
    assert source_after.revision == source_before.revision + 1
    assert len(
        tuple(
            (
                application.state_manager.workspace
                / "projects"
                / application.project_id
                / "revisions"
            ).glob("REV-*.json")
        )
    ) == source_before.revision + 1

    candidate_cad_realization_hash = evaluation.cad_realization_hash
    candidate_m10_request_hash = candidate_m10_request.request_hash
    candidate_cad_request_hash = candidate_cad_request.request_hash
    del candidate, synthesis_request, synthesis_policy, m12_result, evaluation, selection

    reconstruction = application.reconstruct_promoted_mechanism(
        revision=application_result.applied_revision,
        state_hash=application_result.applied_state_hash,
        mechanism_id="PM-task17-direct-drive",
    )
    reconstructed_projection = normalized_projection(reconstruction)
    assert reconstructed_projection == application_result.compilation.projection
    assert reconstructed_projection.projection_hash == decision.projection_hash

    canonical_cad = application.canonical_cad_compiler.realize(reconstruction)
    assert canonical_cad.revision == source_before.revision + 1
    assert canonical_cad.state_hash == application_result.applied_state_hash
    assert canonical_cad.selected_source_content_identities
    assert canonical_cad.realization_hash != candidate_cad_realization_hash
    assert canonical_cad.request_hash != candidate_cad_request_hash
    canonical_semantic_payload = json.dumps(
        reconstruction.mechanism.model_dump(mode="json"), sort_keys=True
    )
    assert candidate_cad_request_hash not in canonical_semantic_payload
    assert candidate_cad_realization_hash not in canonical_semantic_payload
    assert candidate_m10_request_hash not in canonical_semantic_payload

    canonical_m10 = application.canonical_m10_service.execute(reconstruction, canonical_cad)
    assert canonical_m10.status is CanonicalM10VerificationStatus.VERIFIED_CLEAR
    assert canonical_m10.request.request_hash != candidate_m10_request_hash
    scope_equivalence = CanonicalM10ScopeEquivalenceService().compare(
        decision.pre_promotion_scope_projection,
        canonical_m10.scope,
    )
    assert scope_equivalence.equivalent is True, scope_equivalence.differences
    assert scope_equivalence.differences == ()

    no_structural_execution = _NoStructuralExecution()
    application.m11_handoff_service.structural_service = no_structural_execution
    context = _PromotionVerificationContext(application, application_result, manifest_store)
    handoff_request = build_handoff_request(m11_intent, context, reconstruction)
    assert handoff_request is not None
    handoff = application.m11_handoff_service.assess(handoff_request)
    assert handoff.status is expected_m11_status
    assert no_structural_execution.calls == []

    verification = application.verify_promoted_mechanism(application_result)
    assert verification.status is PromotedMechanismVerificationStatus.VERIFIED
    assert verification.promoted_revision == source_before.revision + 1
    assert verification.promoted_state_hash == application_result.applied_state_hash
    assert verification.scope_equivalence_hash == scope_equivalence.result_hash

    equivalent_store = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id=f"{decision_artifact.run_id}-equivalent",
    )
    equivalent_decision_artifact = application.promotion_manifest_service.publish_decision(
        equivalent_store, manifest=decision
    )
    equivalent_result_artifact = application.promotion_manifest_service.publish_result(
        equivalent_store,
        manifest=result_manifest,
        decision_artifact=equivalent_decision_artifact,
    )
    equivalent_decision = application.promotion_manifest_service.resolve_decision(
        equivalent_store, equivalent_decision_artifact.artifact_id
    )
    equivalent_result_manifest = application.promotion_manifest_service.resolve_result(
        equivalent_store, equivalent_result_artifact.artifact_id
    )
    assert equivalent_decision_artifact.run_id != decision_artifact.run_id
    assert equivalent_result_artifact.run_id != result_artifact.run_id
    assert equivalent_decision_artifact.sha256 == decision_artifact.sha256
    assert equivalent_result_artifact.sha256 == result_artifact.sha256
    assert (
        _semantic_identity(decision),
        _semantic_identity(result_manifest),
    ) == (
        _semantic_identity(equivalent_decision),
        _semantic_identity(equivalent_result_manifest),
    )

    fresh_manager = StateManager(application.state_manager.workspace)
    original_revision = fresh_manager.load_revision(
        application.project_id, source_before.revision
    )
    assert original_revision_path.read_bytes() == original_revision_bytes
    assert original_revision == original_state
    assert original_revision.model_dump(mode="json") == original_state.model_dump(mode="json")
    assert state_hash(original_revision) == original_state_identity == source_before.state_hash
    fresh_state = fresh_manager.load_revision(
        application.project_id, application_result.applied_revision
    )
    assert fresh_state.revision == application_result.applied_revision
    assert fresh_state.physical_mechanisms[0].id == "PM-task17-direct-drive"
    for artifact_id, expected_bytes in source_bytes.items():
        artifact = source_artifacts[artifact_id]
        assert (
            application.state_manager.workspace / artifact.relative_path
        ).read_bytes() == expected_bytes

    print(
        "M12_5_TASK17_RESULTS="
        + json.dumps(
            {
                "m11_status": handoff.status.value,
                "candidate_hash": request.candidate.candidate_hash,
                "candidate_cad_request_hash": candidate_cad_request_hash,
                "candidate_cad_realization_hash": candidate_cad_realization_hash,
                "candidate_m10_request_hash": candidate_m10_request_hash,
                "decision_artifact_id": decision_artifact.artifact_id,
                "decision_hash": decision.decision_hash,
                "result_artifact_id": result_artifact.artifact_id,
                "result_hash": result_manifest.result_hash,
                "promotion_proposal_hash": application_result.compilation.promotion_proposal_hash,
                "promoted_revision": application_result.applied_revision,
                "promoted_state_hash": application_result.applied_state_hash,
                "canonical_projection_hash": reconstructed_projection.projection_hash,
                "canonical_cad_request_hash": canonical_cad.request_hash,
                "canonical_cad_realization_hash": canonical_cad.realization_hash,
                "canonical_m10_request_hash": canonical_m10.request.request_hash,
                "canonical_m10_result_hashes": [
                    proof.result.result_hash for proof in canonical_m10.pair_proofs
                ],
                "original_revision_state_hash": original_state_identity,
                "original_revision_bytes_sha256": "sha256:" + hashlib.sha256(original_revision_bytes).hexdigest(),
                "scope_equivalence_hash": scope_equivalence.result_hash,
                "run_id": decision_artifact.run_id,
            },
            sort_keys=True,
        )
    )


def _run_live_external_spur_promotion(tmp_path, monkeypatch, *, comparison_used=True):
    discovery = discover_freecad()
    monkeypatch.setenv(
        "MECHCAD_FREECADCMD",
        discovery.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE,
    )
    application = _build_external_promotion_application(tmp_path)
    monkeypatch.setattr(m12_4, "_m10_inputs", _task17_m10_inputs)
    source_before = application.load_state()
    source_revision_path = (
        application.state_manager._revision_path(PROJECT_ID, source_before.revision)
    )
    source_revision_bytes = source_revision_path.read_bytes()
    original_state = source_before.state.model_copy(deep=True)
    original_state_identity = state_hash(original_state)
    source_artifacts = {
        instance_id: _publish_source_step(
            application,
            part_id=f"promotion-task-18-{instance_id}",
            size=(20.0 + index, 20.0, 5.0),
        )
        for index, instance_id in enumerate(
            (
                "drive-motor", "output-shaft", "bearing-a", "bearing-b", "output-hub",
                "support-mount-a", "support-mount-b",
            )
        )
    }
    gear_artifacts = {
        "driver-gear": _publish_gear_step(application, teeth=20),
        "driven-gear": _publish_gear_step(application, teeth=100),
    }
    source_bytes = {
        artifact.artifact_id: (
            application.state_manager.workspace / artifact.relative_path
        ).read_bytes()
        for artifact in (*source_artifacts.values(), *gear_artifacts.values())
    }
    positions = {
        "drive-motor": (150.0, 150.0, 0.0), "driver-gear": (40.0, 0.0, 0.0),
        "driven-gear": (80.0, 0.0, 0.0), "output-shaft": (80.0, 0.0, 0.0),
        "bearing-a": (100.0, 30.0, 0.0), "bearing-b": (100.0, -30.0, 0.0),
        "output-hub": (80.0, 0.0, 0.0), "motor-mount": (0.0, 0.0, 0.0),
        "support-mount-a": (120.0, 30.0, 0.0), "support-mount-b": (120.0, -30.0, 0.0),
        "payload-body": (80.0, 0.0, 0.0),
    }
    candidate, synthesis_request, synthesis_policy, m12_result = _real_candidate(
        application, source_artifacts, positions,
        architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
        gear_artifact=gear_artifacts,
    )
    evaluation, candidate_cad_request, scope, binding, candidate_m10_request = _evaluate_real_candidate(
        application, candidate, synthesis_request, synthesis_policy, m12_result,
        external_spur=True,
    )
    assert m12_result.status.value == "admissible"
    assert evaluation.outcome.value == "feasible"
    assert binding.driver_gear_constituent_key == "driver-gear"
    assert candidate_m10_request.request_hash

    candidate_b = None
    synthesis_request_b = None
    synthesis_policy_b = None
    m12_result_b = None
    evaluation_b = None
    cad_request_b = None
    scope_b = None
    binding_b = None
    m10_request_b = None
    ranking_request = None
    ranking = None
    selected_top = None
    selected_without_comparison = None
    selected_non_top = None
    comparison_calls = None
    if comparison_used:
        positions_b = dict(positions)
        positions_b.update({
            "output-shaft": (60.0, 0.0, 0.0),
            "output-hub": (60.0, 0.0, 0.0),
            "payload-body": (60.0, 0.0, 0.0),
        })
        candidate_b, synthesis_request_b, synthesis_policy_b, m12_result_b = _real_candidate(
            application, source_artifacts, positions_b,
            architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            gear_artifact=gear_artifacts,
            extra_design_variables=(CandidateDesignVariable(name="comparison-tag", value="b"),),
        )
        evaluation_b, cad_request_b, scope_b, binding_b, m10_request_b = _evaluate_real_candidate(
            application, candidate_b, synthesis_request_b, synthesis_policy_b, m12_result_b,
            external_spur=True,
        )
        assert evaluation_b.outcome.value == "feasible"
        assert evaluation_b.metrics[0].value > evaluation.metrics[0].value
        assert any(
            variable.name == "comparison-tag" and variable.value == "b"
            for variable in candidate_b.design_variables
        )
        assert scope_b.scope_hash == scope.scope_hash
        assert binding_b.driver_gear_constituent_key == "driver-gear"
        assert cad_request_b.request_hash != candidate_cad_request.request_hash
        assert m10_request_b.request_hash != candidate_m10_request.request_hash

        comparison_policy = application.candidate_comparison_service.policy
        ranking_request = m12_4.CandidateComparisonRequest(
            project_id=application.project_id,
            source_binding_hash=application._candidate_source_binding_hash(candidate),
            evaluation_scope_hash=scope.scope_hash,
            policy_hash=comparison_policy.policy_hash,
            candidate_evaluation_pairs=(
                (candidate.candidate_hash, evaluation.evaluation_hash),
                (candidate_b.candidate_hash, evaluation_b.evaluation_hash),
            ),
        )
        ranking = application.compare_candidates(
            ranking_request, ((candidate, evaluation), (candidate_b, evaluation_b))
        )
        selected_top = application.select_candidate(
            candidate_b, evaluation_b, "task-18-selector", "selected top-ranked candidate",
            comparison=ranking,
            comparison_entries=((candidate, evaluation), (candidate_b, evaluation_b)),
        )
        selected_without_comparison = application.select_candidate(
            candidate, evaluation, "task-18-selector", "selected without comparison"
        )
        selected_non_top = application.select_candidate(
            candidate, evaluation, "task-18-selector", "selected explicit non-top candidate",
            comparison=ranking,
            comparison_entries=((candidate, evaluation), (candidate_b, evaluation_b)),
        )
        assert ranking.ranked_candidate_hashes[0] == candidate_b.candidate_hash
        assert selected_top.candidate_hash == candidate_b.candidate_hash
        assert selected_without_comparison.comparison_used is False
        assert selected_non_top.candidate_hash == candidate.candidate_hash
        assert selected_non_top.candidate_hash != ranking.ranked_candidate_hashes[0]
        selected = selected_non_top
    else:
        comparison_calls = []

        def forbidden_comparison(*args, **kwargs):
            comparison_calls.append((args, kwargs))
            raise AssertionError("comparison service must not be invoked")

        monkeypatch.setattr(
            application.candidate_comparison_service,
            "compare",
            forbidden_comparison,
        )
        selected = application.select_candidate(
            candidate,
            evaluation,
            "task-18-no-comparison-selector",
            "selected feasible external spur candidate without comparison",
        )
        assert selected.comparison_used is False
    promotion_request = CandidatePromotionRequest(
        project_id=application.project_id,
        source_revision=source_before.revision,
        source_state_hash=source_before.state_hash,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_3_result=m12_result,
        evaluation=evaluation,
        selection=selected,
        comparison_used=comparison_used,
        comparison=ranking if comparison_used else None,
        comparison_request=ranking_request if comparison_used else None,
        comparison_entries=(
            ((candidate, evaluation), (candidate_b, evaluation_b))
            if comparison_used
            else None
        ),
        promotion_policy=CandidatePromotionPolicy(),
        canonical_target_mechanism_id=(
            "PM-task18-external-spur"
            if comparison_used
            else "PM-task18-external-spur-no-comparison"
        ),
        classifications=_promotion_classifications(candidate),
    )
    application_result = application.promote_selected_candidate(promotion_request)
    assert application_result.status.value == "promotion_applied", application_result.error
    assert application_result.applied_revision == source_before.revision + 1
    assert application_result.request.comparison_used is comparison_used
    if not comparison_used:
        assert application_result.request.comparison is None
        assert application_result.request.comparison_request is None
        assert application_result.request.comparison_entries is None

    mechanism = application.load_state().state.physical_mechanisms[0]
    assert mechanism.id == promotion_request.canonical_target_mechanism_id
    assert mechanism.components
    assert mechanism.connections
    assert mechanism.joint_bindings
    assert len(application.load_state().state.physical_mechanisms) == 1
    assert application_result.compilation is not None
    assert mechanism == application_result.compilation.canonical_mechanism
    mapping = {item.candidate_instance_id: item.canonical_instance_id
               for item in application_result.compilation.mapping}
    assert set(mapping) == {item.instance_id for item in candidate.realization.components}
    assert {item.instance_id for item in mechanism.components} == set(mapping.values())
    canonical_connections = {item.connection_id: item for item in mechanism.connections}
    for source_connection in candidate.realization.connections:
        connection = canonical_connections[source_connection.connection_id]
        assert connection.kind.value == source_connection.kind.value
        assert connection.from_instance_id == mapping[source_connection.from_instance_id]
        assert connection.from_interface_id == source_connection.from_interface_id
        assert connection.to_instance_id == mapping[source_connection.to_instance_id]
        assert connection.to_interface_id == source_connection.to_interface_id
        assert tuple(item.value for item in connection.meanings) == tuple(
            item.value for item in source_connection.meanings
        )
    gear_mesh = next(
        item for item in mechanism.connections
        if item.kind is CanonicalMechanicalConnectionKind.GEAR_MESH
    )
    source_gear_mesh = next(
        item
        for item in candidate.realization.connections
        if item.connection_id == "gear-mesh"
    )
    assert (
        source_gear_mesh.from_interface_id,
        source_gear_mesh.to_interface_id,
        tuple(item.value for item in source_gear_mesh.meanings),
    ) == ("mesh", "mesh", ("kinematic_realization_intent",))
    assert gear_mesh.from_instance_id == mapping["driver-gear"]
    assert gear_mesh.to_instance_id == mapping["driven-gear"]
    assert gear_mesh.from_interface_id == "mesh"
    assert gear_mesh.to_interface_id == "mesh"
    assert tuple(item.value for item in gear_mesh.meanings) == (
        "kinematic_realization_intent",
    )
    assert not any(
        item.kind.value == "coupling"
        and "gear" in {item.from_instance_id, item.to_instance_id}
        for item in mechanism.connections
    )
    canonical_binding = mechanism.joint_bindings[0]
    physical_binding = candidate.realization.joint_bindings[0]
    source_joint = binding.model.joints[0]
    assert canonical_binding.joint_id == scope.output_joint_semantic_key
    assert physical_binding.joint_id == binding.model.joints[0].joint_id
    assert source_joint.parent_instance_id == "cad-motor-mount"
    assert source_joint.child_instance_id == "cad-output-shaft"
    assert canonical_binding.expected_parent_instance_id == mapping["motor-mount"]
    assert canonical_binding.expected_child_instance_id == mapping[physical_binding.driven_instance_id]
    assert canonical_binding.axis_frame_reference == physical_binding.axis_frame_reference
    assert (
        canonical_binding.axis_origin_x_mm,
        canonical_binding.axis_origin_y_mm,
        canonical_binding.axis_origin_z_mm,
        canonical_binding.axis_direction_x,
        canonical_binding.axis_direction_y,
        canonical_binding.axis_direction_z,
    ) == (
        source_joint.axis_origin_x_mm,
        source_joint.axis_origin_y_mm,
        source_joint.axis_origin_z_mm,
        source_joint.axis_direction_x,
        source_joint.axis_direction_y,
        source_joint.axis_direction_z,
    )
    expected_semantic_hash = "sha256:" + hashlib.sha256(
        canonical_json(
            {
                "joint_id": canonical_binding.joint_id,
                "joint_kind": source_joint.joint_kind.value,
                "parent_instance_id": canonical_binding.expected_parent_instance_id,
                "child_instance_id": canonical_binding.expected_child_instance_id,
                "axis_origin": [
                    source_joint.axis_origin_x_mm,
                    source_joint.axis_origin_y_mm,
                    source_joint.axis_origin_z_mm,
                ],
                "axis_direction": [
                    source_joint.axis_direction_x,
                    source_joint.axis_direction_y,
                    source_joint.axis_direction_z,
                ],
                "semantic_version": binding.model.evaluator_version,
            }
        )
    ).hexdigest()
    assert canonical_binding.semantic_hash == expected_semantic_hash
    def payload_keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(payload_keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(payload_keys(item) for item in value))
        return set()

    assert not {
        "gear_ratio", "ratio", "phase", "backlash", "gear_coupling"
    } & payload_keys(mechanism.model_dump(mode="json"))

    candidate_specs = {
        item.source_identity: item for item in candidate.component_specifications
    }
    canonical_specs = {
        item.source_identity: item for item in mechanism.component_specifications
    }
    assert set(canonical_specs) == set(candidate_specs)
    for source_identity, candidate_specification in candidate_specs.items():
        canonical_specification = canonical_specs[source_identity]
        assert canonical_specification.source_identity == candidate_specification.source_identity
        if candidate_specification.geometry_source is None:
            assert canonical_specification.geometry_source is None
        else:
            assert canonical_specification.geometry_source is not None
            assert (
                canonical_specification.geometry_source.artifact_id,
                canonical_specification.geometry_source.artifact_hash,
                canonical_specification.geometry_source.source_identity,
            ) == (
                candidate_specification.geometry_source.artifact_id,
                candidate_specification.geometry_source.artifact_hash,
                candidate_specification.geometry_source.source_identity,
            )
    canonical_components = {item.instance_id: item for item in mechanism.components}
    for candidate_component in candidate.realization.components:
        canonical_component = canonical_components[mapping[candidate_component.instance_id]]
        assert canonical_component.role.value == candidate_component.role.value
        assert canonical_component.interfaces == candidate_component.interfaces

    reconstruction = application.reconstruct_promoted_mechanism(
        revision=application_result.applied_revision,
        state_hash=application_result.applied_state_hash,
        mechanism_id=mechanism.id,
    )
    assert reconstruction.revision == source_before.revision + 1
    assert reconstruction.state_hash == application_result.applied_state_hash
    assert reconstruction.mechanism.id == promotion_request.canonical_target_mechanism_id
    canonical_cad = application.canonical_cad_compiler.realize(reconstruction)
    assert canonical_cad.revision == source_before.revision + 1
    assert canonical_cad.state_hash == application_result.applied_state_hash
    assert canonical_cad.mechanism_id == mechanism.id
    canonical_m10 = application.canonical_m10_service.execute(reconstruction, canonical_cad)
    assert canonical_m10.revision == source_before.revision + 1
    assert canonical_m10.state_hash == application_result.applied_state_hash
    assert canonical_m10.mechanism_id == mechanism.id
    assert canonical_m10.status is CanonicalM10VerificationStatus.VERIFIED_CLEAR
    canonical_choice_keys = {
        choice.key for choice in reconstruction.mechanism.accepted_design_choices
    }
    assert "comparison-tag" not in canonical_choice_keys
    assert all(choice.value != "b" for choice in reconstruction.mechanism.accepted_design_choices)
    assert "comparison-tag" not in json.dumps(canonical_cad.model_dump(mode="json"), sort_keys=True)
    output_mapping = next(
        item for item in canonical_cad.mappings
        if item.physical_instance_id == mapping["output-shaft"]
    )
    assert output_mapping.placement.x_mm == positions["output-shaft"][0]
    assert output_mapping.source_geometry_identity == source_artifacts["output-shaft"].sha256
    by_physical = {
        item.physical_instance_id: item.cad_instance_id
        for item in canonical_m10.inventory.constituent_dispositions
    }
    driver_cad_id = by_physical[mapping["driver-gear"]]
    driven_cad_id = by_physical[mapping["driven-gear"]]
    driver = next(
        item for item in canonical_m10.inventory.constituent_dispositions
        if item.cad_instance_id == driver_cad_id
    )
    assert driver.disposition.value == "internal_motion_unmodeled"
    gear_pair = next(
        item for item in canonical_m10.inventory.classifications
        if set(item.pair) == {driver_cad_id, driven_cad_id}
    )
    assert gear_pair.classification.value == "intended_contact_excluded"
    assert "gear mesh interface is outside M10 scope" in gear_pair.reason
    assert all(driver_cad_id not in item.pair for item in canonical_m10.pair_proofs)
    assert all(driver_cad_id not in item.pair for item in canonical_m10.home_exact_checks)
    assert application.verify_promoted_mechanism(application_result).status is PromotedMechanismVerificationStatus.VERIFIED

    promoted_revision = application_result.applied_revision
    promoted_state_hash = application_result.applied_state_hash
    replay = application.promote_selected_candidate(promotion_request)
    assert replay.status.value == "pre_apply_failure"
    assert replay.error and "stale" in replay.error.lower()
    assert application.load_state().revision == promoted_revision
    assert len(application.load_state().state.physical_mechanisms) == 1

    canonical_target_mechanism_id = promotion_request.canonical_target_mechanism_id
    canonical_cad_request_hash = canonical_cad.request_hash
    canonical_cad_realization_hash = canonical_cad.realization_hash
    canonical_m10_request_hash = canonical_m10.request.request_hash
    candidate_ref = weakref.ref(candidate)
    candidate_b_ref = None if candidate_b is None else weakref.ref(candidate_b)
    del (
        candidate, candidate_b, synthesis_request, synthesis_request_b,
        synthesis_policy, synthesis_policy_b, m12_result, m12_result_b,
        evaluation, evaluation_b, selected, selected_top, selected_without_comparison,
            selected_non_top, ranking, ranking_request, promotion_request,
            application_result, reconstruction, canonical_cad, canonical_m10,
            candidate_cad_request, candidate_m10_request, scope, binding,
            cad_request_b, m10_request_b, scope_b, binding_b, replay,
        )
    import gc
    gc.collect()
    assert candidate_ref() is None
    if candidate_b_ref is not None:
        assert candidate_b_ref() is None
    if not comparison_used:
        assert comparison_calls == []
    assert source_revision_path.read_bytes() == source_revision_bytes
    original_revision = application.state_manager.load_revision(PROJECT_ID, source_before.revision)
    assert original_revision == original_state
    assert state_hash(original_revision) == original_state_identity == source_before.state_hash

    fresh_application = ProductionApplication.create(
        application.state_manager.workspace,
        PROJECT_ID,
        UninvokedAgentAdapter(),
        ownership_path=application.state_manager.workspace.parent / "ownership.yaml",
        dependency_path=application.state_manager.workspace.parent / "dependencies.yaml",
        additional_tool_registrations=m12_4.GearworksTools.registrations(),
    )
    fresh_state = fresh_application.load_state()
    assert (fresh_state.revision, fresh_state.state_hash) == (
        promoted_revision,
        promoted_state_hash,
    )
    fresh_reconstruction = fresh_application.reconstruct_promoted_mechanism(
        revision=promoted_revision,
        state_hash=promoted_state_hash,
        mechanism_id=canonical_target_mechanism_id,
    )
    assert fresh_reconstruction.mechanism.id == canonical_target_mechanism_id
    fresh_cad = fresh_application.canonical_cad_compiler.realize(fresh_reconstruction)
    assert (fresh_cad.revision, fresh_cad.state_hash, fresh_cad.mechanism_id) == (
        promoted_revision,
        promoted_state_hash,
        canonical_target_mechanism_id,
    )
    fresh_m10 = fresh_application.canonical_m10_service.execute(fresh_reconstruction, fresh_cad)
    assert (fresh_m10.revision, fresh_m10.state_hash, fresh_m10.mechanism_id) == (
        promoted_revision,
        promoted_state_hash,
        canonical_target_mechanism_id,
    )
    assert fresh_m10.status is CanonicalM10VerificationStatus.VERIFIED_CLEAR
    assert fresh_cad.request_hash == canonical_cad_request_hash
    assert fresh_cad.realization_hash == canonical_cad_realization_hash
    assert fresh_m10.request.request_hash == canonical_m10_request_hash
    assert set(fresh_cad.selected_source_artifact_ids) == set(source_bytes)
    assert dict(
        zip(
            fresh_cad.selected_source_artifact_ids,
            fresh_cad.selected_source_content_identities,
            strict=True,
        )
    ) == {
        artifact.artifact_id: artifact.sha256
        for _name, artifact in (
            *source_artifacts.items(),
            *gear_artifacts.items(),
        )
    }
    assert all(
        (
            application.state_manager.workspace / artifact.relative_path
        ).read_bytes() == source_bytes[artifact.artifact_id]
        for artifact in (*source_artifacts.values(), *gear_artifacts.values())
    )
    print(
        "M12_5_TASK18_EXTERNAL_SPUR_"
        + ("COMPARISON=" if comparison_used else "NO_COMPARISON=")
        + json.dumps(
            {
                "promoted_revision": promoted_revision,
                "promoted_state_hash": promoted_state_hash,
                "canonical_mechanism_hash": fresh_reconstruction.mechanism.mechanism_hash,
                "canonical_cad_request_hash": fresh_cad.request_hash,
                "canonical_cad_realization_hash": fresh_cad.realization_hash,
                "canonical_m10_request_hash": fresh_m10.request.request_hash,
                "canonical_m10_result_hashes": [item.result.result_hash for item in fresh_m10.pair_proofs],
                "selected_source_artifact_ids": list(fresh_cad.selected_source_artifact_ids),
            },
            sort_keys=True,
        )
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available through deterministic discovery")
@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras are not installed")
def test_live_external_spur_promotion_preserves_selection_topology_and_replays_from_canonical_state(
    tmp_path, monkeypatch
):
    _run_live_external_spur_promotion(tmp_path, monkeypatch, comparison_used=True)


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available through deterministic discovery")
@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras are not installed")
def test_live_external_spur_promotion_without_comparison_applies_selected_candidate(
    tmp_path, monkeypatch
):
    _run_live_external_spur_promotion(tmp_path, monkeypatch, comparison_used=False)
