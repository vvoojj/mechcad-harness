from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from types import SimpleNamespace

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateCadRealizationRequest,
    CandidateCadStageStatus,
    CandidateDesignVariable,
    CandidateGeometryFidelity,
    CandidateEvaluationOutcome,
    CandidateEvaluationPolicy,
    CandidateM10StageStatus,
    CandidateM10PairScopeRequirement,
    CandidateM10PairClassification,
    CandidatePlacementOrigin,
    CandidatePromotionPolicy,
    CandidatePromotionRequest,
    CandidateSynthesisPolicy,
    PromotionApplicationStatus,
    PromotionClassification,
    PromotionValueClassification,
    PromotedMechanismVerificationStatus,
    CanonicalM10ScopeEquivalenceService,
    CanonicalM10VerificationStatus,
    CanonicalM11HandoffStatus,
    PostPromotionM11TargetIntent,
    build_handoff_request,
)
from mechcad_harness.application import ProductionApplication
from mechcad_harness.candidates.canonical_mechanism import normalized_projection
from mechcad_harness.continuous_proof import ContinuousSingleAxisProofStatus
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.cad_compilation import MountingPlateDesignSpec, compile_mounting_plate
from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash

from m12_6_acceptance_fixtures import (
    bootstrap_direct_drive_fixture,
    build_direct_requirements,
    build_synthesis_request,
    UninvokedAcceptanceAdapter,
)
from mechcad_harness.revolute_drive import DriveAdmissibility

from test_m12_candidate_cad_m10_production import _m10_inputs


_DIRECT_CANDIDATE_POSITIONS = {
    "drive-motor": (100.0, 100.0, 0.0),
    "output-shaft": (80.0, 0.0, 0.0),
    "bearing-a": (90.0, 30.0, 0.0),
    "bearing-b": (90.0, -30.0, 0.0),
    "output-hub": (80.0, 0.0, 0.0),
    "motor-mount": (0.0, 0.0, 0.0),
    "payload-body": (80.0, 0.0, 0.0),
}
_FREECADCMD = r"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"


class _NoStructuralExecution:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def unexpected(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            raise AssertionError(f"M11 structural execution must not run: {name}")

        return unexpected


@dataclass(frozen=True)
class DirectDriveIdentityRecord:
    """Scalar locators retained for the later restart/M11 acceptance tasks."""

    workspace: str
    ownership_path: str
    dependency_path: str
    project_id: str
    source_revision: int
    source_state_hash: str
    source_revision_bytes_sha256: str
    source_artifact_run_id: str
    source_artifacts: tuple[str, ...]
    promoted_revision: int
    promoted_state_hash: str
    canonical_mechanism_id: str
    candidate_hash: str
    synthesis_request_hash: str
    synthesis_policy_hash: str
    m12_3_result_hash: str
    candidate_evaluation_hash: str
    selection_hash: str
    promotion_request_hash: str
    promotion_compilation_hash: str
    promotion_proposal_hash: str
    promotion_result_hash: str
    promoted_verification_hash: str
    candidate_cad_request_hash: str
    candidate_cad_realization_hash: str
    candidate_m10_request_hash: str
    candidate_m10_result_hashes: tuple[str, ...]
    candidate_m10_scope_hash: str
    promotion_policy_hash: str
    promotion_projection_hash: str
    promotion_scope_projection_hash: str
    promotion_run_id: str
    changeset_id: str
    proposal_id: str
    decision_artifact_id: str
    decision_artifact_hash: str
    result_artifact_id: str
    result_artifact_hash: str
    result_manifest_hash: str
    canonical_mechanism_hash: str
    canonical_cad_request_hash: str
    canonical_cad_realization_hash: str
    canonical_m10_request_hash: str
    canonical_m10_result_hashes: tuple[str, ...]
    canonical_m10_inventory_hash: str
    canonical_m10_scope_hash: str
    scope_equivalence_hash: str
    canonical_reconstruction_projection_hash: str
    m11_handoff_request_hashes: tuple[str, ...]
    m11_handoff_hashes: tuple[str, ...]


def promotion_classifications(candidate) -> tuple[PromotionClassification, ...]:
    values: list[PromotionClassification] = []

    def add(value: PromotionClassification) -> None:
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


def _candidate_cad_request(candidate) -> CandidateCadRealizationRequest:
    specifications = {
        specification.specification_hash: specification
        for specification in candidate.component_specifications
    }
    source_artifacts = {
        specification.geometry_source.artifact_id: specification.geometry_source
        for specification in candidate.component_specifications
        if specification.geometry_source is not None
    }
    bounded_dimensions = {
        "motor-mount": (30.0, 30.0, 5.0),
        "payload-body": (20.0, 20.0, 5.0),
    }
    mappings = []
    design_variable_identities = set()
    for component in candidate.realization.components:
        instance_id = component.instance_id
        x_mm, y_mm, z_mm = _DIRECT_CANDIDATE_POSITIONS[instance_id]
        placement = CadRigidTransform(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
        placement_inputs = tuple(
            f"candidate:design-variable:{instance_id}.placement.{axis}"
            for axis in ("x_mm", "y_mm", "z_mm")
        )
        placement_origin = CandidatePlacementOrigin(
            authority="candidate_design_variable",
            input_identities=placement_inputs,
            derivation="m12-6-direct-placement@1",
            transform=placement,
        )
        design_variable_identities.update(placement_inputs)
        specification = specifications[component.specification_hash]
        cad_instance_id = f"cad-{instance_id}"
        if specification.geometry_source is not None:
            source = source_artifacts[specification.geometry_source.artifact_id]
            imported = ImportedCadComponent(
                component_id=cad_instance_id,
                artifact_id=source.artifact_id,
                artifact_hash=source.artifact_hash,
                source_revision=candidate.source_binding.source_revision,
                source_state_hash=candidate.source_binding.source_state_hash,
            )
            mappings.append(
                CandidateCadInstanceMapping(
                    candidate_hash=candidate.candidate_hash,
                    physical_instance_id=instance_id,
                    cad_instance_id=cad_instance_id,
                    fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
                    representation_identity=imported_component_hash(imported),
                    source_geometry_identity=source.artifact_hash,
                    geometry_definition_identities=(source.artifact_id,),
                    placement=placement,
                    placement_origin=placement_origin,
                )
            )
            continue

        dimensions = bounded_dimensions[instance_id]
        program = compile_mounting_plate(
            MountingPlateDesignSpec(
                part_id=cad_instance_id,
                plate_length_mm=dimensions[0],
                plate_width_mm=dimensions[1],
                plate_thickness_mm=dimensions[2],
            )
        )
        geometry_inputs = tuple(
            f"candidate:design-variable:{instance_id}.{axis}"
            for axis in ("length_mm", "width_mm", "thickness_mm")
        )
        design_variable_identities.update(geometry_inputs)
        mappings.append(
            CandidateCadInstanceMapping(
                candidate_hash=candidate.candidate_hash,
                physical_instance_id=instance_id,
                cad_instance_id=cad_instance_id,
                fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
                representation_identity=cad_program_hash(program),
                geometry_definition_identities=geometry_inputs,
                placement=placement,
                placement_origin=placement_origin,
            )
        )
    return CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="m12-6-direct-candidate-cad@1",
        compiler_identity="m12-6-direct-candidate-cad-fixture",
        compiler_version="1",
        candidate_instance_ids=tuple(
            component.instance_id for component in candidate.realization.components
        ),
        mappings=tuple(mappings),
        design_variable_identities=tuple(sorted(design_variable_identities)),
    )


def _candidate_synthesis_inputs(fixture):
    variables = [
        CandidateDesignVariable(
            name=f"{instance_id}.placement.{axis}",
            value=value,
        )
        for instance_id, position in _DIRECT_CANDIDATE_POSITIONS.items()
        for axis, value in zip(("x_mm", "y_mm", "z_mm"), position, strict=True)
    ]
    variables.extend(
        CandidateDesignVariable(name=f"{instance_id}.{axis}", value=value)
        for instance_id, dimensions in {
            "motor-mount": (30.0, 30.0, 5.0),
            "payload-body": (20.0, 20.0, 5.0),
        }.items()
        for axis, value in zip(
            ("length_mm", "width_mm", "thickness_mm"), dimensions, strict=True
        )
    )
    template_input = fixture.template_input.model_copy(
        update={
            "design_variables": (*fixture.template_input.design_variables, *variables)
        }
    )
    entries = list(fixture.synthesis_policy.entries)
    declared_keys = {entry[0] for entry in entries}
    for variable in variables:
        key = f"allow-design-variable:{variable.name}"
        if key not in declared_keys:
            entries.append(
                (
                    key,
                    json.dumps(
                        {"value": variable.value},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "hard_admissibility",
                )
            )
    return (
        fixture.synthesis_request,
        CandidateSynthesisPolicy(entries=tuple(entries)),
        template_input,
    )


def _candidate_m10_inputs(candidate, candidate_cad_stage):
    scope, binding, request = _m10_inputs(candidate, candidate_cad_stage)
    scope = type(scope).model_validate(
        scope.model_dump(mode="json")
        | {
            "pair_scope_requirements": [
                CandidateM10PairScopeRequirement(
                    requirement_key="shaft-motor-clearance",
                    first_constituent_key="output-shaft",
                    second_constituent_key="drive-motor",
                    required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
                ).model_dump(mode="json")
            ],
            "fidelity_requirements": [
                ["output-shaft", CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY],
                ["drive-motor", CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY],
            ],
            "scope_hash": "pending",
        }
    )
    joint_id = candidate.realization.joint_bindings[0].joint_id
    model = binding.model.model_copy(
        update={
            "joints": (
                binding.model.joints[0].model_copy(update={"joint_id": joint_id}),
            )
        }
    )
    dispositions = tuple(
        item.model_copy(
            update={
                "output_transform_group": (
                    joint_id
                    if item.disposition.value == "output_rigid"
                    else None
                ),
                "disposition_hash": "pending",
            }
        )
        for item in binding.constituent_dispositions
    )
    binding = type(binding).model_validate(
        binding.model_dump(mode="json")
        | {
            "model": model.model_dump(mode="json"),
            "model_hash": "pending",
            "output_joint_id": joint_id,
            "output_axis": binding.output_axis.model_dump(mode="json")
            | {"frame_id": f"joint:{joint_id}"},
            "constituent_dispositions": [
                item.model_dump(mode="json") for item in dispositions
            ],
            "binding_hash": "pending",
        }
    )
    inventory = type(request.inventory).complete_for(
        candidate_cad_stage.realization, binding, scope
    )
    request = type(request).model_validate(
        request.model_dump(mode="json")
        | {
            "binding_hash": binding.binding_hash,
            "model_hash": binding.model_hash,
            "scope_hash": scope.scope_hash,
            "inventory": inventory.model_dump(mode="json"),
            "request_hash": "pending",
        }
    )
    return scope, binding, request


def _promote_direct_drive_and_return_locators(
    tmp_path, monkeypatch, *, m11_intent=None, expected_m11_status=None
):
    monkeypatch.setenv("MECHCAD_FREECADCMD", _FREECADCMD)
    runtime = discover_freecad().require_available()
    backend_provenance = FreeCADBackend().provenance()
    print(
        "M12_6_DIRECT_RUNTIME="
        + json.dumps(
            {
                "available": runtime.available,
                "executable": runtime.executable,
                "version": runtime.version,
                "runtime_reported_version": backend_provenance.library_version,
                "importable": runtime.importable,
                "execution_boundary": runtime.execution_boundary,
            },
            sort_keys=True,
        )
    )
    assert runtime.executable == _FREECADCMD
    assert backend_provenance.library_name == "FreeCAD"
    assert backend_provenance.library_version == "1.1.3"

    fixture = bootstrap_direct_drive_fixture(tmp_path)
    app = fixture.app
    source = fixture.source
    source_revision_path = app.state_manager._revision_path(
        app.project_id, source.revision
    )
    source_revision_bytes = source_revision_path.read_bytes()
    source_revision_bytes_sha256 = "sha256:" + hashlib.sha256(source_revision_bytes).hexdigest()
    source_artifact_bytes = {
        artifact.artifact_id: (app.state_manager.workspace / artifact.relative_path).read_bytes()
        for artifact in fixture.source_artifacts.values()
    }

    synthesis_request, synthesis_policy, template_input = _candidate_synthesis_inputs(fixture)
    outcome = app.realize_and_evaluate_revolute_drive(
        request=synthesis_request,
        policy=synthesis_policy,
        template_input=template_input,
        requirements=fixture.requirements,
    )
    candidate = outcome.construction.candidate
    m12_result = outcome.evaluation
    assert outcome.construction.status is DriveAdmissibility.ADMISSIBLE
    assert candidate is not None
    assert m12_result is not None
    assert m12_result.status is DriveAdmissibility.ADMISSIBLE
    assert m12_result.candidate_hash == candidate.candidate_hash
    assert m12_result.result_hash

    candidate_cad_request = _candidate_cad_request(candidate)
    candidate_cad_stage = app.realize_candidate_cad(
        candidate,
        synthesis_request,
        synthesis_policy,
        candidate_cad_request,
    )
    assert candidate_cad_stage.status is CandidateCadStageStatus.SUCCESS
    assert candidate_cad_stage.realization is not None
    assert candidate_cad_stage.realization.candidate_hash == candidate.candidate_hash
    assert candidate_cad_stage.realization.verified_source_content_identities == tuple(
        fixture.source_artifacts[component.instance_id].sha256
        for component in candidate.realization.components
        if component.instance_id in fixture.source_artifacts
    )
    assert candidate_cad_stage.realization.assembly.imported_components

    candidate_m10_scope, candidate_m10_binding, candidate_m10_request = _candidate_m10_inputs(
        candidate, candidate_cad_stage
    )
    evaluation = app.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        candidate_cad_request,
        candidate_m10_request,
        candidate_m10_scope,
        candidate_m10_binding,
        evaluation_policy=CandidateEvaluationPolicy(),
    )
    assert evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
    assert evaluation.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS
    assert evaluation.m10_stage_outcome.status is CandidateM10StageStatus.SUCCESS
    assert evaluation.cad_request == candidate_cad_request
    assert evaluation.m10_request == candidate_m10_request
    assert evaluation.m10_scope == candidate_m10_scope
    assert evaluation.m10_binding == candidate_m10_binding
    assert evaluation.m12_3_result_hash == m12_result.result_hash
    assert evaluation.evaluation_hash

    pair_proof = evaluation.m10_stage_outcome.pair_proofs[0]
    proof = pair_proof.result
    assert pair_proof.pair == ("cad-drive-motor", "cad-output-shaft")
    assert proof.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR
    assert (proof.start_angle_deg, proof.end_angle_deg) == (
        candidate_m10_scope.angle_interval_deg
    )
    assert proof.required_clearance_mm == candidate_m10_scope.required_clearance_mm == 1.0
    assert proof.collision_witness is None
    assert proof.exact_evaluations_count == 1
    assert len(proof.certified_leaf_certificates) == 1
    certificate = proof.certified_leaf_certificates[0]
    assert (certificate.interval_start_deg, certificate.interval_end_deg) == (
        -10.0,
        10.0,
    )
    assert certificate.minimum_certified_lower_clearance_mm > 1.0
    assert certificate.pair_certificates[0].certified_lower_clearance_mm > 1.0
    assert evaluation.metrics[0].key.value == "verified_clearance_lower_bound_mm"
    assert evaluation.metrics[0].value == certificate.minimum_certified_lower_clearance_mm
    assert evaluation.metrics[0].value > candidate_m10_scope.required_clearance_mm

    proof_evidence = app.get_continuous_proof_evidence(proof.result_hash)
    assert proof_evidence is not None
    proof_provenance = proof_evidence.continuous_proof_execution_provenance
    assert proof_provenance is not None
    assert proof_provenance.provider_name == "freecad-transient-exact"
    assert proof_provenance.provider_version
    assert proof_provenance.execution_mode == "freecadcmd-subprocess"
    assert proof_provenance.backend_provenance is not None
    assert proof_provenance.backend_provenance.backend_name == "freecad"
    assert proof_provenance.backend_provenance.library_name == "FreeCAD"
    assert proof_provenance.backend_provenance.library_version
    print(
        "M12_6_DIRECT_PROOF_PROVENANCE="
        + json.dumps(
            {
                "provider_name": proof_provenance.provider_name,
                "provider_version": proof_provenance.provider_version,
                "execution_mode": proof_provenance.execution_mode,
                "backend": proof_provenance.backend_provenance.model_dump(mode="json"),
            },
            sort_keys=True,
        )
    )

    selection = app.select_candidate(
        candidate,
        evaluation,
        "m12-6-direct-selector",
        "explicit direct-drive acceptance selection",
    )
    assert selection.candidate_hash == candidate.candidate_hash
    assert selection.evaluation_hash == evaluation.evaluation_hash
    assert selection.comparison_used is False
    assert selection.selection_hash

    promotion_request = CandidatePromotionRequest(
        project_id=app.project_id,
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_3_result=m12_result,
        evaluation=evaluation,
        selection=selection,
        promotion_policy=CandidatePromotionPolicy(),
        canonical_target_mechanism_id="PM-m12-6-direct",
        classifications=promotion_classifications(candidate),
        m11_target_intent=m11_intent,
    )
    classification_prefixes = {
        item.source_identity.split(":", 2)[1]
        for item in promotion_request.classifications
    }
    assert {
        "property",
        "geometry-source",
        "design-variable",
        "physical-instance",
        "connection",
        "joint-binding",
    } <= classification_prefixes
    assert any(
        item.classification is PromotionValueClassification.ACCEPTED_DESIGN_CHOICE
        and item.source_identity.startswith("candidate:design-variable:")
        for item in promotion_request.classifications
    )

    promotion = app.promote_selected_candidate(promotion_request)
    assert promotion.status is PromotionApplicationStatus.PROMOTION_APPLIED, promotion.error
    assert promotion.request is not None
    assert promotion.compilation is not None
    assert promotion.request.request_hash == promotion_request.request_hash
    assert promotion.compilation.compilation_hash
    assert promotion.compilation.promotion_proposal_hash
    assert promotion.applied_revision == source.revision + 1
    assert promotion.applied_state_hash != source.state_hash
    assert len(promotion.compilation.proposal.operations) == 1
    assert promotion.compilation.proposal.operations[0].operation.value == "add"
    assert promotion.compilation.proposal.operations[0].path == (
        "/physical_mechanisms/PM-m12-6-direct"
    )
    assert promotion.decision_artifact_id
    assert promotion.result_artifact_id
    promoted_state = app.load_state()
    assert promoted_state.revision == promotion.applied_revision
    assert state_hash(promoted_state.state) == promotion.applied_state_hash
    assert len(promoted_state.state.physical_mechanisms) == 1
    assert promoted_state.state.physical_mechanisms[0].id == "PM-m12-6-direct"

    promotion_run_dirs = {
        path.name
        for path in (
            app.state_manager.workspace / "projects" / app.project_id / "runs"
        ).iterdir()
        if path.is_dir()
    }
    promotion_lookup = ArtifactStore(
        app.state_manager.workspace,
        project_id=app.project_id,
        run_id="project-lookup",
    )
    decision_artifact = promotion_lookup.existing_in_project(promotion.decision_artifact_id)
    result_artifact = promotion_lookup.existing_in_project(promotion.result_artifact_id)
    assert decision_artifact is not None
    assert result_artifact is not None
    assert decision_artifact.artifact_type is ArtifactType.JSON
    assert result_artifact.artifact_type is ArtifactType.JSON
    assert decision_artifact.run_id == result_artifact.run_id
    assert decision_artifact.run_id != fixture.source_artifact_run_id
    assert promotion_run_dirs == {
        fixture.source_artifact_run_id,
        decision_artifact.run_id,
    }

    manifest_store = ArtifactStore(
        app.state_manager.workspace,
        project_id=app.project_id,
        run_id=decision_artifact.run_id,
    )
    result_manifest = app.promotion_manifest_service.resolve_result(
        manifest_store, result_artifact.artifact_id
    )
    decision = app.promotion_manifest_service.resolve_decision(
        manifest_store, result_manifest.decision_artifact_id
    )
    assert result_manifest.decision_artifact_id == decision_artifact.artifact_id
    assert result_manifest.decision_artifact_hash == decision_artifact.sha256
    assert result_artifact.input_hash == decision_artifact.sha256
    assert decision.base_revision == source.revision
    assert decision.base_state_hash == source.state_hash
    assert result_manifest.resulting_revision == promotion.applied_revision
    assert result_manifest.resulting_state_hash == promotion.applied_state_hash
    assert result_manifest.result_hash
    assert result_manifest.proposal_id == promotion.compilation.proposal.id
    assert result_manifest.changeset_id
    assert result_manifest.changed_paths == (
        "/physical_mechanisms/PM-m12-6-direct",
    )
    assert decision_artifact.created_at <= result_artifact.created_at

    run = app.run_controller.get_run(decision_artifact.run_id, app.project_id)
    assert (
        run.initial_revision,
        run.initial_state_hash,
        run.active_revision,
        run.active_state_hash,
    ) == (
        source.revision,
        source.state_hash,
        promotion.applied_revision,
        promotion.applied_state_hash,
    )
    invalidation = app.evidence_store.load_invalidation(
        app.project_id, promotion.applied_revision
    )
    assert invalidation.project_id == app.project_id
    assert invalidation.parent_revision == source.revision
    assert invalidation.revision == source.revision + 1
    assert invalidation.changeset_id == result_manifest.changeset_id
    assert invalidation.changed_paths == (
        "/physical_mechanisms/PM-m12-6-direct",
    )
    assert invalidation.directly_invalidated_nodes == (
        "analysis.continuous_clearance_proof",
        "analysis.kinematic_sweep",
    )
    assert invalidation.transitively_invalidated_nodes == (
        "analysis.continuous_clearance_proof",
        "analysis.kinematic_sweep",
    )

    verification = app.verify_promoted_mechanism(promotion)
    assert verification.status is PromotedMechanismVerificationStatus.VERIFIED
    assert verification.promotion_result_hash == result_manifest.result_hash
    assert verification.verification_hash
    assert verification.promoted_revision == promotion.applied_revision
    assert verification.promoted_state_hash == promotion.applied_state_hash
    assert verification.canonical_target_mechanism_id == "PM-m12-6-direct"
    assert verification.canonical_mechanism_hash == (
        promotion.compilation.canonical_mechanism.mechanism_hash
    )
    assert verification.projection_hash == promotion.compilation.projection.projection_hash
    assert verification.canonical_cad_request_hash
    assert verification.canonical_cad_realization_hash
    assert verification.canonical_m10_inventory_hash
    assert verification.canonical_m10_outcome_hash
    assert verification.canonical_m10_request_hashes
    assert verification.canonical_m10_result_hashes
    assert verification.scope_equivalence_hash
    assert verification.canonical_cad_request_hash != candidate_cad_request.request_hash
    assert verification.canonical_cad_realization_hash != candidate_cad_stage.realization.realization_hash
    assert candidate_m10_request.request_hash not in verification.canonical_m10_request_hashes

    identity_reconstruction = app.reconstruct_promoted_mechanism(
        revision=promotion.applied_revision,
        state_hash=promotion.applied_state_hash,
        mechanism_id=promotion_request.canonical_target_mechanism_id,
    )
    identity_cad = app.canonical_cad_compiler.realize(identity_reconstruction)
    identity_m10 = app.canonical_m10_service.execute(identity_reconstruction, identity_cad)

    canonical_reconstruction_projection_hash = promotion.compilation.projection.projection_hash
    m11_handoff_request_hashes = ()
    m11_handoff_hashes = ()
    if m11_intent is not None:
        assert expected_m11_status is not None
        reconstruction = app.reconstruct_promoted_mechanism(
            revision=promotion.applied_revision,
            state_hash=promotion.applied_state_hash,
            mechanism_id=promotion_request.canonical_target_mechanism_id,
        )
        no_structural_execution = _NoStructuralExecution()
        app.m11_handoff_service.structural_service = no_structural_execution
        context = SimpleNamespace(
            application_result=promotion,
            manifest_store=manifest_store,
            manifest_service=app.promotion_manifest_service,
        )
        handoff_request = build_handoff_request(m11_intent, context, reconstruction)
        assert handoff_request is not None
        handoff = app.m11_handoff_service.assess(handoff_request)
        assert handoff.status is expected_m11_status
        assert no_structural_execution.calls == []
        canonical_reconstruction_projection_hash = reconstruction.normalized_projection_hash
        m11_handoff_request_hashes = (handoff.request.request_hash,)
        m11_handoff_hashes = (handoff.handoff_hash,)

    fresh_manager = StateManager(app.state_manager.workspace)
    original_revision = fresh_manager.load_revision(app.project_id, source.revision)
    assert source_revision_path.read_bytes() == source_revision_bytes
    assert "sha256:" + hashlib.sha256(source_revision_path.read_bytes()).hexdigest() == source_revision_bytes_sha256
    assert state_hash(original_revision) == source.state_hash
    assert original_revision.model_dump(mode="json") == source.state.model_dump(mode="json")
    assert {
        artifact.artifact_id: (
            app.state_manager.workspace / artifact.relative_path
        ).read_bytes()
        for artifact in fixture.source_artifacts.values()
    } == source_artifact_bytes

    identity_record = DirectDriveIdentityRecord(
        workspace=str(app.state_manager.workspace),
        ownership_path=str(fixture.ownership_path),
        dependency_path=str(fixture.dependency_path),
        project_id=app.project_id,
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        source_revision_bytes_sha256=source_revision_bytes_sha256,
        source_artifact_run_id=fixture.source_artifact_run_id,
        source_artifacts=tuple(
            f"{artifact.artifact_id}:{artifact.sha256}"
            for artifact in fixture.source_artifacts.values()
        ),
        promoted_revision=promotion.applied_revision,
        promoted_state_hash=promotion.applied_state_hash,
        canonical_mechanism_id=promotion_request.canonical_target_mechanism_id,
        candidate_hash=candidate.candidate_hash,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        m12_3_result_hash=m12_result.result_hash,
        candidate_evaluation_hash=evaluation.evaluation_hash,
        selection_hash=selection.selection_hash,
        promotion_request_hash=promotion.request.request_hash,
        promotion_compilation_hash=promotion.compilation.compilation_hash,
        promotion_proposal_hash=promotion.compilation.promotion_proposal_hash,
        promotion_result_hash=result_manifest.result_hash,
        promoted_verification_hash=verification.verification_hash,
        candidate_cad_request_hash=candidate_cad_request.request_hash,
        candidate_cad_realization_hash=candidate_cad_stage.realization.realization_hash,
        candidate_m10_request_hash=candidate_m10_request.request_hash,
        candidate_m10_result_hashes=evaluation.m10_result_hashes,
        candidate_m10_scope_hash=candidate_m10_scope.scope_hash,
        promotion_policy_hash=promotion_request.promotion_policy.policy_hash,
        promotion_projection_hash=decision.projection_hash,
        promotion_scope_projection_hash=decision.pre_promotion_scope_projection.projection_hash,
        promotion_run_id=decision_artifact.run_id,
        changeset_id=result_manifest.changeset_id,
        proposal_id=promotion.compilation.proposal.id,
        decision_artifact_id=decision_artifact.artifact_id,
        decision_artifact_hash=decision_artifact.sha256,
        result_artifact_id=result_artifact.artifact_id,
        result_artifact_hash=result_artifact.sha256,
        result_manifest_hash=result_manifest.result_hash,
        canonical_mechanism_hash=promotion.compilation.canonical_mechanism.mechanism_hash,
        canonical_cad_request_hash=verification.canonical_cad_request_hash,
        canonical_cad_realization_hash=verification.canonical_cad_realization_hash,
        canonical_m10_request_hash=verification.canonical_m10_request_hashes[0],
        canonical_m10_result_hashes=verification.canonical_m10_result_hashes,
        canonical_m10_inventory_hash=verification.canonical_m10_inventory_hash,
        canonical_m10_scope_hash=identity_m10.scope.scope_hash,
        scope_equivalence_hash=verification.scope_equivalence_hash,
        canonical_reconstruction_projection_hash=canonical_reconstruction_projection_hash,
        m11_handoff_request_hashes=m11_handoff_request_hashes,
        m11_handoff_hashes=m11_handoff_hashes,
    )
    assert identity_record.source_revision + 1 == identity_record.promoted_revision
    print("M12_6_DIRECT_IDENTITY=" + json.dumps(asdict(identity_record), sort_keys=True))
    assert fixture.acceptance_adapter.call_count == 0
    return identity_record


def test_live_direct_drive_m12_6_end_to_end(tmp_path, monkeypatch):
    locators = _promote_direct_drive_and_return_locators(tmp_path, monkeypatch)
    assert locators.canonical_mechanism_id == "PM-m12-6-direct"


def test_direct_drive_durable_provenance_survives_restart(tmp_path, monkeypatch):
    locators = _promote_direct_drive_and_return_locators(tmp_path, monkeypatch)
    fresh_adapter = UninvokedAcceptanceAdapter()
    fresh_app = ProductionApplication.create(
        locators.workspace,
        locators.project_id,
        fresh_adapter,
        ownership_path=locators.ownership_path,
        dependency_path=locators.dependency_path,
    )

    result_meta = ArtifactStore(
        locators.workspace,
        project_id=locators.project_id,
        run_id="project-lookup",
    ).existing_in_project(locators.result_artifact_id)
    assert result_meta is not None
    assert result_meta.artifact_type is ArtifactType.JSON
    assert result_meta.sha256 == locators.result_artifact_hash

    store = ArtifactStore(
        locators.workspace,
        project_id=locators.project_id,
        run_id=result_meta.run_id,
    )
    fresh_result = fresh_app.promotion_manifest_service.resolve_result(
        store, result_meta.artifact_id
    )
    fresh_decision = fresh_app.promotion_manifest_service.resolve_decision(
        store, fresh_result.decision_artifact_id
    )
    decision_meta, _decision_bytes = store.read_verified_strict(
        fresh_result.decision_artifact_id,
        expected_type=ArtifactType.JSON,
        expected_hash=fresh_result.decision_artifact_hash,
    )
    assert decision_meta.sha256 == locators.decision_artifact_hash
    assert fresh_result.decision_artifact_id == decision_meta.artifact_id
    assert fresh_result.decision_artifact_hash == decision_meta.sha256
    assert result_meta.input_hash == decision_meta.sha256
    assert fresh_result.result_hash == locators.result_manifest_hash
    assert fresh_result.resulting_revision == locators.promoted_revision
    assert fresh_result.resulting_state_hash == locators.promoted_state_hash
    assert fresh_decision.base_revision == locators.source_revision
    assert fresh_decision.base_state_hash == locators.source_state_hash
    assert fresh_adapter.call_count == 0


def test_direct_drive_canonical_restart_round_trip_and_scope_isolation(tmp_path, monkeypatch):
    locators = _promote_direct_drive_and_return_locators(tmp_path, monkeypatch)
    fresh_adapter = UninvokedAcceptanceAdapter()
    fresh_app = ProductionApplication.create(
        locators.workspace,
        locators.project_id,
        fresh_adapter,
        ownership_path=locators.ownership_path,
        dependency_path=locators.dependency_path,
    )
    result_meta = ArtifactStore(
        locators.workspace,
        project_id=locators.project_id,
        run_id="project-lookup",
    ).existing_in_project(locators.result_artifact_id)
    assert result_meta is not None
    store = ArtifactStore(
        locators.workspace,
        project_id=locators.project_id,
        run_id=result_meta.run_id,
    )
    fresh_result = fresh_app.promotion_manifest_service.resolve_result(
        store, result_meta.artifact_id
    )
    fresh_decision = fresh_app.promotion_manifest_service.resolve_decision(
        store, fresh_result.decision_artifact_id
    )

    promoted_state = fresh_app.state_manager.load_revision(
        locators.project_id, locators.promoted_revision
    )
    assert promoted_state.revision == locators.promoted_revision
    assert state_hash(promoted_state) == locators.promoted_state_hash
    reconstruction = fresh_app.reconstruct_promoted_mechanism(
        revision=locators.promoted_revision,
        state_hash=locators.promoted_state_hash,
        mechanism_id=locators.canonical_mechanism_id,
    )
    assert reconstruction.mechanism.mechanism_hash == locators.canonical_mechanism_hash
    canonical_cad = fresh_app.canonical_cad_compiler.realize(reconstruction)
    canonical_m10 = fresh_app.canonical_m10_service.execute(reconstruction, canonical_cad)
    assert canonical_m10.status is CanonicalM10VerificationStatus.VERIFIED_CLEAR
    assert canonical_cad.request_hash == locators.canonical_cad_request_hash
    assert canonical_cad.realization_hash == locators.canonical_cad_realization_hash
    assert canonical_m10.request.request_hash == locators.canonical_m10_request_hash

    scope_equivalence = CanonicalM10ScopeEquivalenceService().compare(
        fresh_decision.pre_promotion_scope_projection,
        canonical_m10.scope,
    )
    assert scope_equivalence.equivalent is True
    assert scope_equivalence.differences == ()

    normalized = normalized_projection(reconstruction)
    assert normalized == fresh_decision.projection
    assert normalized.projection_hash == fresh_decision.projection_hash

    projected_specs = {
        item.source_identity: item for item in fresh_decision.projection.component_specifications
    }
    canonical_specs = {
        item.source_identity: item
        for item in normalized.component_specifications
    }
    source_identity = sorted(projected_specs)[0]
    projected_property = projected_specs[source_identity].properties[0]
    canonical_property = canonical_specs[source_identity].properties[0]
    assert (
        canonical_property.key,
        canonical_property.normalized_value,
        canonical_property.normalized_range,
        canonical_property.canonical_unit,
        canonical_property.authority,
        canonical_property.source_identity,
        canonical_property.property_hash,
        canonical_property.availability,
    ) == (
        projected_property.key,
        projected_property.normalized_value,
        projected_property.normalized_range,
        projected_property.canonical_unit,
        projected_property.authority,
        projected_property.source_identity,
        projected_property.property_hash,
        projected_property.availability,
    )
    source = projected_specs[source_identity].geometry_source
    assert source is not None
    canonical_source = canonical_specs[source_identity].geometry_source
    assert canonical_source is not None
    assert (
        canonical_source.artifact_id,
        canonical_source.artifact_hash,
        canonical_source.source_identity,
        canonical_source.format,
    ) == (source.artifact_id, source.artifact_hash, source.source_identity, source.format)

    choice = fresh_decision.projection.accepted_design_choices[0]
    canonical_choice = normalized.accepted_design_choices[0]
    assert (
        canonical_choice.key,
        canonical_choice.value,
        canonical_choice.origin,
        canonical_choice.provenance,
        canonical_choice.source_identities,
        canonical_choice.choice_hash,
    ) == (
        choice.key,
        choice.value,
        choice.origin,
        choice.provenance,
        choice.source_identities,
        choice.choice_hash,
    )
    assert canonical_choice.origin.value == "candidate_local_choice"

    assert normalized.components == fresh_decision.projection.components
    assert normalized.placements == fresh_decision.projection.placements
    assert normalized.connections == fresh_decision.projection.connections
    assert normalized.joint_bindings == fresh_decision.projection.joint_bindings
    assert normalized.m10_obligations == fresh_decision.projection.m10_obligations
    obligation = normalized.m10_obligations[0]
    assert obligation.joint_semantic_key == canonical_m10.scope.joint_semantic_key
    assert obligation.angle_interval_deg == canonical_m10.scope.angle_interval_deg
    assert obligation.required_clearance_mm == canonical_m10.scope.required_clearance_mm
    assert obligation.physical_pair_requirements
    assert tuple(obligation.fidelity_requirements) == tuple(
        canonical_m10.scope.fidelity_requirements
    )
    assert obligation.required_home_check_semantics == canonical_m10.scope.required_home_check_semantics

    changed_audit_scope = type(
        fresh_decision.pre_promotion_scope_projection
    ).model_validate(
        fresh_decision.pre_promotion_scope_projection.model_dump(mode="json")
        | {"required_clearance_mm": 99.0, "projection_hash": "pending"}
    )
    changed_comparison = CanonicalM10ScopeEquivalenceService().compare(
        changed_audit_scope, canonical_m10.scope
    )
    assert changed_comparison.equivalent is False
    assert changed_comparison.differences == ("required_clearance_mm",)

    canonical_m10_again = fresh_app.canonical_m10_service.execute(
        reconstruction, canonical_cad
    )
    assert canonical_m10_again.request == canonical_m10.request
    assert canonical_m10_again.inventory == canonical_m10.inventory
    assert canonical_m10_again.scope.angle_interval_deg == canonical_m10.scope.angle_interval_deg
    assert canonical_m10_again.scope.required_clearance_mm == canonical_m10.scope.required_clearance_mm
    assert canonical_m10_again.scope.fidelity_requirements == canonical_m10.scope.fidelity_requirements
    assert canonical_m10_again.scope.required_home_check_semantics == canonical_m10.scope.required_home_check_semantics
    assert canonical_m10_again.pair_proofs == canonical_m10.pair_proofs
    assert canonical_m10_again.home_exact_checks == canonical_m10.home_exact_checks
    assert fresh_adapter.call_count == 0


@pytest.mark.parametrize(
    ("m11_intent", "expected_status"),
    (
        (
            PostPromotionM11TargetIntent(target_scope="whole_mechanism"),
            CanonicalM11HandoffStatus.NOT_ELIGIBLE,
        ),
        (
            PostPromotionM11TargetIntent(
                target_scope="single_component",
                candidate_instance_id="motor-mount",
            ),
            CanonicalM11HandoffStatus.UNRESOLVED,
        ),
    ),
)
def test_direct_drive_m11_handoff_is_non_gating(
    tmp_path, monkeypatch, m11_intent, expected_status
):
    locators = _promote_direct_drive_and_return_locators(
        tmp_path,
        monkeypatch,
        m11_intent=m11_intent,
        expected_m11_status=expected_status,
    )
    assert locators.promoted_revision == locators.source_revision + 1


def test_direct_drive_fixture_stays_at_source_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", _FREECADCMD)
    fixture = bootstrap_direct_drive_fixture(tmp_path)

    assert fixture.source.revision == 1
    assert fixture.source_label == "M12-6 ACCEPTANCE FIXTURE SOURCE AUTHORITY"
    assert fixture.source_artifacts["output-hub"].artifact_type is ArtifactType.STEP
    assert fixture.source_artifact_run_id
    assert fixture.acceptance_adapter.call_count == 0
    assert fixture.synthesis_request.source_binding.source_revision == fixture.source.revision
    assert fixture.synthesis_request.source_binding.source_state_hash == fixture.source.state_hash
    assert all(
        getattr(fixture.template_input, field).geometry_source is not None
        for field in (
            "motor_specification",
            "shaft_specification",
            "bearing_a_specification",
            "bearing_b_specification",
            "hub_specification",
        )
    )
    assert {
        artifact.run_id for artifact in fixture.source_artifacts.values()
    } == {fixture.source_artifact_run_id}
    assert all(
        artifact.project_id == fixture.app.project_id
        and artifact.bound_revision == fixture.source.revision
        and artifact.bound_state_hash == fixture.source.state_hash
        for artifact in fixture.source_artifacts.values()
    )
    runs_root = (
        fixture.app.state_manager.workspace
        / "projects"
        / fixture.app.project_id
        / "runs"
    )
    assert {path.name for path in runs_root.iterdir() if path.is_dir()} == {
        fixture.source_artifact_run_id
    }

    outcome = fixture.app.realize_and_evaluate_revolute_drive(
        request=fixture.synthesis_request,
        policy=fixture.synthesis_policy,
        template_input=fixture.template_input,
        requirements=fixture.requirements,
    )

    assert outcome.evaluation is not None
    assert outcome.evaluation.status is DriveAdmissibility.ADMISSIBLE
    assert fixture.acceptance_adapter.call_count == 0


def test_fixture_inputs_remain_bound_to_captured_source_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", _FREECADCMD)
    fixture = bootstrap_direct_drive_fixture(tmp_path)
    source = fixture.source

    request = build_synthesis_request(fixture.app, source)
    engineering = build_direct_requirements(source, request.source_binding)

    assert (
        request.source_binding.project_id,
        request.source_binding.source_revision,
        request.source_binding.source_state_hash,
    ) == (source.project_id, source.revision, source.state_hash)
    request.source_binding.validate_against(source.project_id, source.state)
    assert all(
        binding.source_record_hash
        == next(
            reference.value_hash
            for reference in request.source_binding.consumed_authority
            if reference.path == binding.source_path
        )
        for binding in engineering.trusted_source_scalar_bindings
    )
    source_values = source.state.yagi_payload_carrier_requirements
    assert all(
        binding.value == source_values[int(binding.source_path.rsplit("/", 1)[1])]["value"]
        for binding in engineering.trusted_source_scalar_bindings
    )
