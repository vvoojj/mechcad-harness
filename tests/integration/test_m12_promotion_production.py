from __future__ import annotations

import json
import hashlib
import gc
import os
import shutil
import sys
import weakref
from pathlib import Path
from types import SimpleNamespace

import pytest

from mechcad_harness.application import ProductionApplication, _PromotionVerificationContext
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.cad_assembly import assembly_hash
from mechcad_harness.continuous_proof import (
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
    ContinuousIntervalCertificate,
    ContinuousPairCertificate,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisProofStatus,
)
from mechcad_harness.candidates import (
    CandidateComparisonDirection,
    CandidateComparisonPolicy,
    CandidateComparisonRequest,
    CandidateEvaluationCurrentnessService,
    CandidateEvaluationPolicy,
    CandidateCollisionPairInventory,
    CandidateM10Binding,
    CandidateM10EvaluationRequest,
    CandidateM10EvaluationService,
    CandidateGeometryFidelity,
    MechanicalConnection,
    MechanicalConnectionKind,
    CandidateMetricKey,
    CandidatePromotionApplicationService,
    CandidateDesignVariable,
    CandidatePromotionPolicy,
    CandidatePromotionRequest,
    CandidateProvenanceIntegrityError,
    CandidateSelectionService,
    PostPromotionM11TargetIntent,
    PromotionClassification,
    PromotionValueClassification,
    PromotedMechanismVerificationStatus,
)
from mechcad_harness.candidates.models import (
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    GeometrySourceReference,
)
from mechcad_harness.candidates.canonical_m10 import (
    CanonicalM10ScopeEquivalenceService,
    CanonicalM10VerificationService,
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
from mechcad_harness.models.evidence import Evidence
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.revolute_drive import DriveArchitecture
from mechcad_harness.state import StateManager, canonical_json, state_hash

from test_m12_candidate_cad_m10_production import (
    FREECAD_CANDIDATE,
    evaluate_real_candidate,
    publish_gear_step,
    publish_source_step,
    real_candidate,
    cad_m10_inputs,
)

unit_path = str(Path(__file__).parents[1] / "unit")
if unit_path not in sys.path:
    sys.path.insert(0, unit_path)
import test_m12_candidate_cad_m10_production as m12_4
GEAR_AVAILABLE = m12_4.GEAR_AVAILABLE
_BASE_M10_INPUTS = m12_4._m10_inputs
from test_m12_revolute_drive_production import (
    PROJECT_ID,
    UninvokedAgentAdapter,
    _geometry_identities,
    make_request,
    policy_for,
    production_state,
    requirements,
    template,
    _publish_source_artifacts,
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


class _IntegrationCurrentnessVerifier:
    def __init__(self, state_manager, *, synthesis_request=None, synthesis_policy=None):
        self._service = CandidateEvaluationCurrentnessService(
            state_manager, cad_replay_verifier=lambda *args: None
        )
        self._synthesis_request = synthesis_request
        self._synthesis_policy = synthesis_policy

    def verify_current(self, evaluation, candidate):
        return self._service.verify_current(
            evaluation,
            candidate,
            self._synthesis_request
            or CandidateSynthesisRequest(source_binding=candidate.source_binding),
            self._synthesis_policy
            or CandidateSynthesisPolicy(
                entries=(
                    ("allow-direct-drive", "direct_drive", "hard_admissibility"),
                    ("preferred-voltage", "24 V", "preference"),
                )
            ),
        )


def _integration_comparison_policy():
    return CandidateComparisonPolicy(
        metric_keys=(CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM,),
        directions=(CandidateComparisonDirection.MAXIMIZE,),
        expected_units=("mm",),
    )


def _integration_comparison_request(policy, entries):
    evaluation = entries[0][1]
    return CandidateComparisonRequest(
        project_id="PRJ-M12",
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        policy_hash=policy.policy_hash,
        candidate_evaluation_pairs=tuple(
            (candidate.candidate_hash, item.evaluation_hash)
            for candidate, item in entries
        ),
    )


def _write_integration_evidence(workspace, candidate, evidence):
    path = workspace / "projects" / candidate.source_binding.project_id / "evidence" / f"{evidence.id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(evidence.model_dump_json(), encoding="utf-8")


def _nonlive_canonical_proof_result(kwargs):
    request = ContinuousSingleAxisProofRequest(
        source_assembly_id=kwargs["assembly"].assembly_id,
        source_assembly_hash=assembly_hash(kwargs["assembly"]),
        axis=kwargs["axis"],
        start_angle_deg=kwargs["start_angle_deg"],
        end_angle_deg=kwargs["end_angle_deg"],
        moving_instance_ids=kwargs["moving_instance_ids"],
        stationary_instance_ids=kwargs["stationary_instance_ids"],
        required_clearance_mm=kwargs["required_clearance_mm"],
        proof_guard_mm=kwargs["proof_guard_mm"],
        max_depth=kwargs["max_depth"],
        minimum_interval_deg=kwargs["minimum_interval_deg"],
        max_exact_evaluations=kwargs["max_exact_evaluations"],
    )
    certificate = ContinuousIntervalCertificate(
        interval_start_deg=request.start_angle_deg,
        interval_end_deg=request.end_angle_deg,
        reference_angle_deg=request.start_angle_deg,
        pair_certificates=(
            ContinuousPairCertificate(
                moving_instance_id=request.moving_instance_ids[0],
                stationary_instance_id=request.stationary_instance_ids[0],
                exact_distance_mm=10.0,
                radial_bound_mm=1.0,
                angular_motion_bound_mm=0.1,
                certified_lower_clearance_mm=9.9,
            ),
        ),
        minimum_certified_lower_clearance_mm=9.9,
    )
    result = ContinuousSingleAxisProofResult(
        request_hash=request.request_hash,
        source_assembly_hash=request.source_assembly_hash,
        proof_algorithm_version=CONTINUOUS_PROOF_ALGORITHM_VERSION,
        axis=request.axis,
        start_angle_deg=request.start_angle_deg,
        end_angle_deg=request.end_angle_deg,
        moving_instance_ids=request.moving_instance_ids,
        stationary_instance_ids=request.stationary_instance_ids,
        required_clearance_mm=request.required_clearance_mm,
        proof_guard_mm=request.proof_guard_mm,
        status=ContinuousSingleAxisProofStatus.VERIFIED_CLEAR,
        certified_leaf_certificates=(certificate,),
        exact_evaluations_count=1,
        maximum_depth_reached=0,
    )
    return result.model_copy(
        update={
            "result_hash": "sha256:"
            + hashlib.sha256(
                json.dumps(
                    result.model_dump(mode="json", exclude={"result_hash"}),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        }
    )


class _NonLiveCanonicalM10Application:
    def prove_continuous_single_axis_clearance(self, **kwargs):
        return _nonlive_canonical_proof_result(kwargs)


def _evaluate_publish_and_select(
    application,
    tmp_path,
    *,
    candidate,
    synthesis_request,
    synthesis_policy,
    m12_result,
    source,
    source_step_artifacts,
    selector="promotion-fixture-selector",
    rationale="promotion fixture selection",
    scope_pair=None,
):
    """Deterministic no-live evaluate/publish/select pipeline for promotion fixtures."""
    cad_stage, m10_stage, scope, binding, m10_request, cad_request = (
        cad_m10_inputs(
            candidate,
            application=application,
            synthesis_request=synthesis_request,
            synthesis_policy=synthesis_policy,
            scope_pair=scope_pair,
        )
    )
    if candidate.schema_version == "mechanical-design-candidate@2":
        return _evaluate_publish_and_select_v2(
            application,
            tmp_path,
            candidate=candidate,
            synthesis_request=synthesis_request,
            synthesis_policy=synthesis_policy,
            m12_result=m12_result,
            cad_stage=cad_stage,
            m10_stage=m10_stage,
            scope=scope,
            binding=binding,
            m10_request=m10_request,
            cad_request=cad_request,
            selector=selector,
            rationale=rationale,
        )
    specifications = {
        specification.specification_hash: specification
        for specification in candidate.component_specifications
    }
    components = {
        component.instance_id: component
        for component in candidate.realization.components
    }
    trusted_mappings = []
    imported_components = []
    trusted_part_ids = set()
    for mapping in cad_stage.realization.mappings:
        component = components[mapping.physical_instance_id]
        specification = specifications[component.specification_hash]
        source_reference = specification.geometry_source
        assert source_reference is not None
        instance = next(
            item
            for item in cad_stage.realization.assembly.instances
            if item.instance_id == mapping.cad_instance_id
        )
        imported = ImportedCadComponent(
            component_id=instance.part_id,
            artifact_id=source_reference.artifact_id,
            artifact_hash=source_reference.artifact_hash,
            source_revision=source.revision,
            source_state_hash=source.state_hash,
        )
        imported_components.append(imported)
        trusted_part_ids.add(instance.part_id)
        trusted_mappings.append(
            type(mapping).model_validate(
                mapping.model_dump(mode="json")
                | {
                    "fidelity": CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
                    "representation_identity": imported_component_hash(imported),
                    "source_geometry_identity": source_reference.artifact_hash,
                    "geometry_definition_identities": (source_reference.artifact_id,),
                    "mapping_hash": "pending",
                }
            )
        )
    assembly = type(cad_stage.realization.assembly).model_validate(
        cad_stage.realization.assembly.model_dump(mode="json")
        | {
            "parts": tuple(
                part
                for part in cad_stage.realization.assembly.parts
                if part.part_id not in trusted_part_ids
            ),
            "imported_components": tuple(
                imported.model_dump(mode="json") for imported in imported_components
            ),
        }
    )
    realization = type(cad_stage.realization).model_validate(
        cad_stage.realization.model_dump(mode="json")
        | {
            "mappings": tuple(mapping.model_dump(mode="json") for mapping in trusted_mappings),
            "assembly": assembly.model_dump(mode="json"),
            "assembly_hash": assembly_hash(assembly),
            "representation_identities": (),
            "verified_source_content_identities": tuple(
                dict.fromkeys(
                    mapping.source_geometry_identity
                    for mapping in trusted_mappings
                    if mapping.source_geometry_identity is not None
                )
            ),
            "realization_hash": "pending",
        }
    )
    cad_request = type(cad_request).model_validate(
        cad_request.model_dump(mode="json")
        | {
            "candidate_hash": candidate.candidate_hash,
            "mappings": tuple(mapping.model_dump(mode="json") for mapping in trusted_mappings),
            "request_hash": "pending",
        }
    )
    realization = type(realization).model_validate(
        realization.model_dump(mode="json")
        | {"request_hash": cad_request.request_hash, "realization_hash": "pending"}
    )
    cad_stage = type(cad_stage).model_validate(
        cad_stage.model_dump(mode="json")
        | {
            "realization": realization.model_dump(mode="json"),
            "realization_hash": realization.realization_hash,
            "outcome_hash": "pending",
        }
    )
    scope = type(scope).model_validate(
        scope.model_dump(mode="json")
        | {
            "fidelity_requirements": tuple(
                (key, CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY)
                for key, _ in scope.fidelity_requirements
            ),
            "scope_hash": "pending",
        }
    )
    physical_joint_id = candidate.realization.joint_bindings[0].joint_id
    m10_model = binding.model.model_copy(
        update={
            "joints": (
                binding.model.joints[0].model_copy(update={"joint_id": physical_joint_id}),
            )
        }
    )
    binding = CandidateM10Binding.model_validate(
        binding.model_dump(mode="json")
        | {
            "model": m10_model.model_dump(mode="json"),
            "cad_realization_hash": cad_stage.realization.realization_hash,
            "output_joint_id": physical_joint_id,
            "output_axis": binding.output_axis.model_copy(
                update={"frame_id": f"joint:{physical_joint_id}"}
            ).model_dump(mode="json"),
            "constituent_dispositions": tuple(
                disposition.model_copy(
                    update={
                        "output_transform_group": (
                            physical_joint_id
                            if disposition.output_transform_group == "output-joint"
                            else disposition.output_transform_group
                        ),
                        "disposition_hash": "pending",
                    }
                ).model_dump(mode="json")
                for disposition in binding.constituent_dispositions
            ),
            "model_hash": "pending",
            "binding_hash": "pending",
        }
    )
    inventory = CandidateCollisionPairInventory.complete_for(
        cad_stage.realization, binding, scope
    )
    m10_request = CandidateM10EvaluationRequest(
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=cad_stage.realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding.model_hash,
        mapping_hashes=tuple(
            sorted(mapping.mapping_hash for mapping in cad_stage.realization.mappings)
        ),
        inventory=inventory,
    )
    rebound_pair_proofs = []
    for proof in m10_stage.pair_proofs:
        pair_assembly = CandidateM10EvaluationService._induced_pair_assembly(
            cad_stage.realization.assembly,
            proof.moving_instance_id,
            proof.stationary_instance_id,
        )
        proof_request = type(proof.request).model_validate(
            proof.request.model_dump(mode="json")
            | {
                "axis": binding.output_axis.model_dump(mode="json"),
                "source_assembly_id": pair_assembly.assembly_id,
                "source_assembly_hash": assembly_hash(pair_assembly),
                "request_hash": "pending",
            }
        )
        proof_result_pending = type(proof.result).model_validate(
            proof.result.model_dump(mode="json")
            | {
                "axis": binding.output_axis.model_dump(mode="json"),
                "source_assembly_hash": proof_request.source_assembly_hash,
                "request_hash": proof_request.request_hash,
                "result_hash": "pending",
            }
        )
        proof_result = type(proof.result).model_validate(
            proof_result_pending.model_dump(mode="json")
            | {
                "result_hash": "sha256:"
                + hashlib.sha256(
                    json.dumps(
                        proof_result_pending.model_dump(
                            mode="json", exclude={"result_hash"}
                        ),
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
            }
        )
        rebound_pair_proofs.append(
            type(proof).model_validate(
                proof.model_dump(mode="json")
                | {
                    "request": proof_request.model_dump(mode="json"),
                    "result": proof_result.model_dump(mode="json"),
                    "request_hash": proof_request.request_hash,
                    "result_hash": proof_result.result_hash,
                    "proof_hash": "pending",
                }
            )
        )
    m10_stage = type(m10_stage).model_validate(
        m10_stage.model_dump(mode="json")
            | {
                "pair_proofs": tuple(
                proof.model_dump(mode="json") for proof in rebound_pair_proofs
            ),
                "cad_realization_hash": cad_stage.realization.realization_hash,
                "binding_hash": binding.binding_hash,
                "scope_hash": scope.scope_hash,
            "evaluation_request_hash": m10_request.request_hash,
            "outcome_hash": "pending",
        }
    )
    application.candidate_evaluation_service.cad_replay_verifier = lambda *args: None
    application.candidate_evaluation_currentness_service.cad_replay_verifier = (
        lambda *args: None
    )
    application.candidate_provenance_artifact_service.cad_replay_verifier = (
        lambda *args: None
    )
    evaluation = application.candidate_evaluation_service.evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    for kind, prefix, records in (
        (
            "analysis.continuous_clearance_proof",
            "EVD-CPROOF-",
            evaluation.m10_stage_outcome.pair_proofs,
        ),
        (
            "analysis.kinematic_sweep",
            "EVD-KSWEEP-",
            evaluation.m10_stage_outcome.home_exact_checks,
        ),
    ):
        for record in records:
            evidence_id = prefix + hashlib.sha256(
                (record.request_hash + record.result_hash).encode()
            ).hexdigest()[:24]
            _write_integration_evidence(
                tmp_path,
                candidate,
                Evidence(
                    id=evidence_id,
                    kind=kind,
                    summary="deterministic production integration fixture",
                    revision=candidate.source_binding.source_revision,
                    state_hash=candidate.source_binding.source_state_hash,
                    producer_result_id=record.result_hash,
                    input_hash=record.request_hash,
                    output_hash=record.result_hash,
                ),
            )

    provenance = application.candidate_provenance_artifact_service
    candidate_cad_publication = provenance.publish_candidate_cad(
        candidate,
        synthesis_request,
        synthesis_policy,
        cad_request,
        cad_stage.realization,
        source_step_artifacts=tuple(source_step_artifacts),
    )
    candidate_evaluation_publication = provenance.publish_candidate_evaluation(
        candidate_cad_publication.artifact, evaluation
    )
    selection = CandidateSelectionService(
        project_id=PROJECT_ID,
        currentness_verifier=_IntegrationCurrentnessVerifier(
            application.state_manager,
            synthesis_request=synthesis_request,
            synthesis_policy=synthesis_policy,
        ),
    ).select(
        candidate,
        candidate_evaluation_publication.payload.evaluation,
        selector,
        rationale,
    )
    selection_publication = provenance.publish_candidate_selection(
        selection,
        candidate_cad_publication.artifact,
        candidate_evaluation_publication.artifact,
    )
    return SimpleNamespace(
        evaluation=evaluation,
        cad_request=cad_request,
        cad_stage=cad_stage,
        m10_stage=m10_stage,
        scope=scope,
        binding=binding,
        m10_request=m10_request,
        candidate_cad_publication=candidate_cad_publication,
        candidate_evaluation_publication=candidate_evaluation_publication,
        selection=selection,
        selection_publication=selection_publication,
    )


def _evaluate_publish_and_select_v2(
    application,
    tmp_path,
    *,
    candidate,
    synthesis_request,
    synthesis_policy,
    m12_result,
    cad_stage,
    m10_stage,
    scope,
    binding,
    m10_request,
    cad_request,
    selector,
    rationale,
):
    """Use the production CAD/evaluation/selection @2 path with non-live M10 evidence."""
    evaluation = application.candidate_evaluation_service.evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    for kind, prefix, records in (
        (
            "analysis.continuous_clearance_proof",
            "EVD-CPROOF-",
            evaluation.m10_stage_outcome.pair_proofs,
        ),
        (
            "analysis.kinematic_sweep",
            "EVD-KSWEEP-",
            evaluation.m10_stage_outcome.home_exact_checks,
        ),
    ):
        for record in records:
            evidence_id = prefix + hashlib.sha256(
                (record.request_hash + record.result_hash).encode()
            ).hexdigest()[:24]
            _write_integration_evidence(
                tmp_path,
                candidate,
                Evidence(
                    id=evidence_id,
                    kind=kind,
                    summary="deterministic promotion fixture proof",
                    revision=candidate.source_binding.source_revision,
                    state_hash=candidate.source_binding.source_state_hash,
                    producer_result_id=record.result_hash,
                    input_hash=record.request_hash,
                    output_hash=record.result_hash,
                ),
            )

    provenance = application.candidate_provenance_artifact_service
    candidate_cad_publication = provenance.resolve_candidate_cad(
        application._candidate_provenance_artifact_id(
            "CANDIDATE-CAD-", cad_stage.realization.realization_hash
        )
    )
    candidate_evaluation_publication = provenance.publish_candidate_evaluation(
        candidate_cad_publication, evaluation
    )
    selection = application.select_candidate(
        candidate,
        candidate_evaluation_publication.payload.evaluation,
        selector,
        rationale,
        synthesis_request=synthesis_request,
    )
    selection_publication = provenance.resolve_candidate_selection(
        application._candidate_provenance_artifact_id(
            "CANDIDATE-SELECTION-", selection.selection_hash
        )
    )
    return SimpleNamespace(
        evaluation=evaluation,
        cad_request=cad_request,
        cad_stage=cad_stage,
        m10_stage=m10_stage,
        scope=scope,
        binding=binding,
        m10_request=m10_request,
        candidate_cad_publication=candidate_cad_publication,
        candidate_evaluation_publication=candidate_evaluation_publication,
        selection=selection,
        selection_publication=selection_publication,
    )


def _build_nonlive_promotion_context(tmp_path, *, promote=True):
    """Build the canonical no-live chain from production integration types."""
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /physical_mechanisms/*\n    owner: mechcad-physical-mechanism\n",
        encoding="utf-8",
    )
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    state = production_state()
    state = state.model_copy(
        update={
            "yagi_payload_carrier_requirements": list(
                state.yagi_payload_carrier_requirements
            )
            + _geometry_identities(state)
        }
    )
    StateManager(tmp_path).create_project(PROJECT_ID, state)
    application = ProductionApplication.create(
        tmp_path,
        PROJECT_ID,
        _CompositionAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )
    _publish_source_artifacts(application, state)

    from mechcad_harness.revolute_drive.service import RevoluteDriveRealizationService
    from test_candidate_m10_v2 import _policy_requirements
    from test_candidate_multijoint_m10_v2 import (
        _candidate_with_m13_multi_joint_authority,
    )

    (
        source_snapshot,
        _,
        _,
        synthesis_request,
        synthesis_policy,
        candidate,
    ) = _candidate_with_m13_multi_joint_authority(
        tmp_path,
        manager=application.state_manager,
        store=application.candidate_publication_service.store,
    )
    source = application.load_state()
    m12_result = RevoluteDriveRealizationService().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _policy_requirements(),
        source_state=source_snapshot,
    )
    source_store = ArtifactStore(tmp_path, project_id=PROJECT_ID, run_id="SOURCE")
    source_step_artifacts = []
    from mechcad_harness.step_content_identity import step_content_identity_v1

    seen_source_artifact_ids = set()
    for specification in candidate.component_specifications:
        source_reference = specification.geometry_source
        if source_reference is None:
            continue
        verified = source_store.read_verified_in_project(
            source_reference.artifact_id,
            expected_type=ArtifactType.STEP,
            expected_hash=source_reference.artifact_hash,
        )
        if verified is None:
            raise AssertionError(
                "promotion fixture source artifact is absent from its accepted builder"
            )
        source_artifact, source_bytes = verified
        if (
            source_reference.content_identity_algorithm != "step-content-identity@1"
            or step_content_identity_v1(source_bytes).content_hash
            != source_reference.content_identity
        ):
            raise AssertionError(
                "promotion fixture semantic source identity does not match source bytes"
            )
        if source_artifact.artifact_id not in seen_source_artifact_ids:
            source_step_artifacts.append(source_artifact)
            seen_source_artifact_ids.add(source_artifact.artifact_id)
    published = _evaluate_publish_and_select(
        application,
        tmp_path,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_result=m12_result,
        source=source,
        source_step_artifacts=source_step_artifacts,
        scope_pair=("bearing-shaft-clearance", "bearing-a", "output-shaft"),
    )
    evaluation = published.evaluation
    candidate_cad_publication = published.candidate_cad_publication
    candidate_evaluation_publication = published.candidate_evaluation_publication
    selection = published.selection
    selection_publication = published.selection_publication
    if candidate.schema_version == "mechanical-design-candidate@2":
        from mechcad_harness.candidates.promotion import CandidatePromotionCompilerV2
        from mechcad_harness.candidates.promotion_models import (
            CandidateCanonicalInstanceMappingV3,
            CandidatePromotionPolicyV2,
            CandidatePromotionRequestV2,
        )

        promotion_policy_v2 = CandidatePromotionPolicyV2()
        classifications_v2 = tuple(
            sorted(
                (
                    item
                    for item in _promotion_classifications(candidate)
                    if not item.source_identity.startswith(
                        "candidate:geometry-source:"
                    )
                ),
                key=lambda item: item.source_identity,
            )
        )
        classifications_by_identity = {
            item.source_identity: item for item in classifications_v2
        }
        mapping_v3 = tuple(
            sorted(
                (
                    CandidateCanonicalInstanceMappingV3(
                        candidate_instance_id=component.instance_id,
                        canonical_instance_id=(
                            f"PM-M12-NONLIVE:{component.instance_id}"
                        ),
                        canonical_path=(
                            "/physical_mechanisms/PM-M12-NONLIVE/components/"
                            f"PM-M12-NONLIVE:{component.instance_id}"
                        ),
                        classification=classifications_by_identity[
                            f"candidate:physical-instance:{component.instance_id}"
                        ].classification,
                        source_identity=(
                            f"candidate:physical-instance:{component.instance_id}"
                        ),
                        source_provenance=classifications_by_identity[
                            f"candidate:physical-instance:{component.instance_id}"
                        ].source_provenance,
                        source_value=classifications_by_identity[
                            f"candidate:physical-instance:{component.instance_id}"
                        ].source_value,
                    )
                    for component in candidate.realization.components
                ),
                key=lambda item: (
                    item.candidate_instance_id,
                    item.canonical_instance_id,
                ),
            )
        )
        promotion_request_v2 = CandidatePromotionRequestV2(
            project_id=PROJECT_ID,
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            candidate_hash=candidate.candidate_hash,
            synthesis_request_hash=synthesis_request.request_hash,
            synthesis_policy_hash=synthesis_policy.policy_hash,
            m12_3_result_hash=m12_result.result_hash,
            evaluation_hash=evaluation.evaluation_hash,
            selection_hash=selection.selection_hash,
            comparison_used=selection.comparison_used,
            comparison_request_hash=None,
            comparison_result_hash=selection.comparison_result_hash,
            comparison_entry_hashes=(),
            promotion_policy_hash=promotion_policy_v2.policy_hash,
            canonical_target_mechanism_id="PM-M12-NONLIVE",
            classifications=classifications_v2,
        )
        readiness_v2 = CandidatePromotionCompilerV2(
            project_id=PROJECT_ID
        ).validate_readiness_v2(
            promotion_request_v2,
            synthesis_request=synthesis_request,
            candidate=candidate,
            m12_3_result_hash=m12_result.result_hash,
            evaluation_hash=evaluation.evaluation_hash,
            selection_hash=selection.selection_hash,
            evaluation_scope_hash=evaluation.evaluation_scope_hash,
            promotion_policy=promotion_policy_v2,
            mapping=mapping_v3,
        )
        context = SimpleNamespace(
            application=application,
            application_result=SimpleNamespace(
                request=promotion_request_v2,
                readiness=readiness_v2,
                compilation=None,
                applied_revision=None,
                applied_state_hash=None,
            ),
            selection=selection,
            selection_publication=selection_publication,
            candidate_cad_publication=candidate_cad_publication,
            candidate_evaluation_publication=candidate_evaluation_publication,
            canonical_mechanism_compiler=application.canonical_mechanism_compiler,
            pre_promotion_scope_projection=None,
        )
        if not promote:
            return context, candidate, evaluation, None, None, None
        application_result = application.promote_selected_candidate(
            promotion_request_v2
        )
        assert application_result.status.value == "promotion_applied", (
            f"promotion@2 application status={application_result.status.value}: "
            f"{application_result.error}"
        )
        canonical_reconstruction = application.reconstruct_promoted_mechanism(
            revision=application_result.applied_revision,
            state_hash=application_result.applied_state_hash,
            mechanism_id=promotion_request_v2.canonical_target_mechanism_id,
        )
        canonical_cad = application.canonical_cad_compiler.realize(
            canonical_reconstruction
        )
        canonical_m10 = CanonicalM10VerificationService(
            _NonLiveCanonicalM10Application()
        ).execute(canonical_reconstruction, canonical_cad)
        decision_artifact = ArtifactStore(
            tmp_path,
            project_id=PROJECT_ID,
            run_id="promotion-v2-lookup",
        ).existing_in_project(application_result.decision_artifact_id)
        assert decision_artifact is not None
        manifest_store = ArtifactStore(
            tmp_path,
            project_id=PROJECT_ID,
            run_id=decision_artifact.run_id,
            task_id=decision_artifact.task_id,
        )
        decision = application.promotion_manifest_service.resolve_decision_v2(
            manifest_store,
            decision_artifact.artifact_id,
            provenance_service=application.candidate_provenance_artifact_service,
            promotion_request=promotion_request_v2,
        )
        context = SimpleNamespace(
            application=application,
            application_result=application_result,
            manifest_store=manifest_store,
            manifest_service=application.promotion_manifest_service,
            canonical_mechanism_compiler=application.canonical_mechanism_compiler,
            request=promotion_request_v2,
            pre_promotion_scope_projection=decision.pre_promotion_scope_projection,
            candidate_cad_publication=candidate_cad_publication,
            candidate_evaluation_publication=candidate_evaluation_publication,
            selection=selection,
            selection_publication=selection_publication,
        )
        return (
            context,
            candidate,
            evaluation,
            canonical_reconstruction,
            canonical_cad,
            canonical_m10,
        )

    promotion_request = CandidatePromotionRequest(
        project_id=PROJECT_ID,
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_3_result=m12_result,
        evaluation=evaluation,
        selection=selection,
        promotion_policy=CandidatePromotionPolicy(),
        canonical_target_mechanism_id="PM-M12-NONLIVE",
        classifications=_promotion_classifications(candidate),
    )
    if not promote:
        compilation = application.candidate_promotion_compiler.compile(
            source.state, promotion_request
        )
        context = SimpleNamespace(
            application=application,
            application_result=SimpleNamespace(
                request=promotion_request,
                compilation=compilation,
            ),
            selection=selection,
            selection_publication=selection_publication,
            candidate_cad_publication=candidate_cad_publication,
            candidate_evaluation_publication=candidate_evaluation_publication,
            canonical_mechanism_compiler=application.canonical_mechanism_compiler,
        )
        return context, candidate, evaluation, None, None, None
    application_result = application.promote_selected_candidate(promotion_request)
    assert application_result.status.value == "promotion_applied", application_result.error
    assert application_result.compilation is not None

    canonical_reconstruction = application.reconstruct_promoted_mechanism(
        revision=application_result.applied_revision,
        state_hash=application_result.applied_state_hash,
        mechanism_id=promotion_request.canonical_target_mechanism_id,
    )
    canonical_cad = application.canonical_cad_compiler.realize(canonical_reconstruction)
    canonical_m10 = CanonicalM10VerificationService(
        _NonLiveCanonicalM10Application()
    ).execute(
        canonical_reconstruction, canonical_cad
    )
    decision_artifact = ArtifactStore(
        tmp_path,
        project_id=PROJECT_ID,
        run_id="promotion-fixture-lookup",
    ).existing_in_project(application_result.decision_artifact_id)
    assert decision_artifact is not None
    pre_promotion_scope_projection = application.promotion_manifest_service.resolve_decision(
        ArtifactStore(
            tmp_path, project_id=PROJECT_ID, run_id=decision_artifact.run_id
        ),
        decision_artifact.artifact_id,
    ).pre_promotion_scope_projection
    for artifact_id in (
        application_result.decision_artifact_id,
        application_result.result_artifact_id,
    ):
        artifact = ArtifactStore(
            tmp_path, project_id=PROJECT_ID, run_id="promotion-fixture-lookup"
        ).existing_in_project(artifact_id)
        if artifact is not None:
            shutil.rmtree((tmp_path / artifact.relative_path).parent)
    context = SimpleNamespace(
        application=application,
        application_result=application_result,
        manifest_store=ArtifactStore(
            tmp_path, project_id=PROJECT_ID, run_id=decision_artifact.run_id
        ),
        manifest_service=application.promotion_manifest_service,
        canonical_mechanism_compiler=application.canonical_mechanism_compiler,
        request=promotion_request,
        pre_promotion_scope_projection=pre_promotion_scope_projection,
        candidate_cad_publication=candidate_cad_publication,
        candidate_evaluation_publication=candidate_evaluation_publication,
        selection=selection,
        selection_publication=selection_publication,
    )
    return context, candidate, evaluation, canonical_reconstruction, canonical_cad, canonical_m10


def _nonlive_promotion_chain_fixture(
    tmp_path, *, with_canonical=False, promote=True
):
    """Build a production-verifiable durable selection chain without live CAD."""

    from mechcad_harness.candidates import CandidateComparisonService, CandidateSelectionService
    from mechcad_harness.candidates.promotion_artifacts import (
        SelectedCandidateDecisionManifest,
    )
    from mechcad_harness.candidates.promotion_models import PromotionDecisionInputReference

    (
        context,
        candidate,
        evaluation,
        canonical_reconstruction,
        canonical_cad,
        canonical_m10,
    ) = _build_nonlive_promotion_context(tmp_path, promote=promote)
    if (
        not promote
        and context.application_result.request.schema_version
        == "candidate-promotion-request@2"
    ):
        return (
            context.application,
            context.application_result.request,
            context.selection_publication,
        )
    if context.application_result.request.schema_version == "candidate-promotion-request@2":
        application = context.application
        request = context.application_result.request
        lookup = ArtifactStore(tmp_path, project_id=request.project_id, run_id="LOOKUP")
        decision_artifact = lookup.existing_in_project(
            context.application_result.decision_artifact_id
        )
        result_artifact = lookup.existing_in_project(
            context.application_result.result_artifact_id
        )
        assert decision_artifact is not None and result_artifact is not None
        canonical_publication = None
        if with_canonical:
            for kind, prefix, records in (
                (
                    "analysis.continuous_clearance_proof",
                    "EVD-CPROOF-",
                    canonical_m10.pair_proofs,
                ),
                (
                    "analysis.kinematic_sweep",
                    "EVD-KSWEEP-",
                    canonical_m10.home_exact_checks,
                ),
            ):
                for record in records:
                    evidence_id = prefix + hashlib.sha256(
                        (record.request_hash + record.result_hash).encode()
                    ).hexdigest()[:24]
                    _write_integration_evidence(
                        tmp_path,
                        candidate,
                        Evidence(
                            id=evidence_id,
                            kind=kind,
                            summary="canonical @2 fixture evidence",
                            revision=canonical_m10.revision,
                            state_hash=canonical_m10.state_hash,
                            producer_result_id=record.result_hash,
                            input_hash=record.request_hash,
                            output_hash=record.result_hash,
                        ),
                    )
            service = application.candidate_provenance_artifact_service
            canonical_cad_publication = service.publish_canonical_cad(
                canonical_reconstruction, canonical_cad
            )
            canonical_publication = service.publish_canonical_m10(
                canonical_cad_publication, canonical_m10
            )
        if with_canonical:
            return (
                application,
                context.application_result,
                context.selection_publication,
                decision_artifact,
                result_artifact.artifact_id,
                canonical_publication,
            )
        return (
            application,
            context.application_result,
            context.selection_publication,
            decision_artifact,
            result_artifact.artifact_id,
        )
    compilation = context.application_result.compilation
    manager = context.canonical_mechanism_compiler.state_manager
    state = manager.load_revision("PRJ-M12", 1)
    request_template = context.application_result.request
    candidate = request_template.candidate
    evaluation = request_template.evaluation
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceArtifactService

    service = CandidateProvenanceArtifactService(
        tmp_path,
        request_template.project_id,
        manager,
        cad_replay_verifier=lambda *args: None,
    )
    canonical_publication = None
    if with_canonical:
        for kind, prefix, records in (
            (
                "analysis.continuous_clearance_proof",
                "EVD-CPROOF-",
                canonical_m10.pair_proofs,
            ),
            (
                "analysis.kinematic_sweep",
                "EVD-KSWEEP-",
                canonical_m10.home_exact_checks,
            ),
        ):
            for record in records:
                evidence_id = prefix + hashlib.sha256(
                    (record.request_hash + record.result_hash).encode()
                ).hexdigest()[:24]
                _write_integration_evidence(
                    tmp_path,
                    candidate,
                    Evidence(
                        id=evidence_id,
                        kind=kind,
                        summary="canonical fixture evidence",
                        revision=canonical_m10.revision,
                        state_hash=canonical_m10.state_hash,
                        producer_result_id=record.result_hash,
                        input_hash=record.request_hash,
                        output_hash=record.result_hash,
                    ),
                )
        canonical_cad_publication = service.publish_canonical_cad(
            canonical_reconstruction, canonical_cad
        )
        canonical_publication = service.publish_canonical_m10(
            canonical_cad_publication, canonical_m10
        )
    first_cad = context.candidate_cad_publication
    first = context.candidate_evaluation_publication
    first_candidate = candidate
    assert request_template.project_id == "PRJ-M12"
    assert first_candidate.candidate_hash == request_template.candidate.candidate_hash
    assert first.payload.evaluation == request_template.evaluation
    selection = context.selection
    selection_publication = context.selection_publication

    base_revision = selection_publication.artifact.bound_revision
    base_state_hash = selection_publication.artifact.bound_state_hash
    from mechcad_harness.candidates.promotion_models import CandidatePromotionRequest

    request = CandidatePromotionRequest.model_validate(
        request_template.model_dump(mode="json")
        | {
            "selection": selection.model_dump(mode="json"),
            "comparison_used": False,
            "comparison": None,
            "comparison_request": None,
            "comparison_entries": None,
            "request_hash": "pending",
        }
    )
    if not promote:
        return context.application, request, selection_publication
    reference = PromotionDecisionInputReference(
        promotion_request_hash=request.request_hash,
        project_id=request.project_id,
        base_revision=base_revision,
        base_state_hash=base_state_hash,
        candidate_hash=first_candidate.candidate_hash,
        synthesis_request_hash=first_candidate.synthesis_request_hash,
        synthesis_policy_hash=first_candidate.synthesis_policy_hash,
        m12_3_result_hash=request.m12_3_result.result_hash,
        evaluation_hash=first.payload.evaluation.evaluation_hash,
        selection_hash=selection.selection_hash,
        comparison_used=False,
        comparison_result_hash=None,
        comparison_request_hash=None,
        promotion_policy_hash=request.promotion_policy.policy_hash,
        canonical_target_mechanism_id=compilation.projection.canonical_target_mechanism_id,
        mapping_identities=tuple(item.mapping_hash for item in compilation.mapping),
        classification_identities=tuple(
            item.classification_hash for item in request.classifications
        ),
    )
    decision = SelectedCandidateDecisionManifest(
        input_reference=reference,
        pre_promotion_scope_projection=context.pre_promotion_scope_projection,
        promotion_policy_hash=reference.promotion_policy_hash,
        base_revision=base_revision,
        base_state_hash=base_state_hash,
        compilation_hash=compilation.compilation_hash,
        promotion_proposal_hash=compilation.promotion_proposal_hash,
        projection_hash=compilation.projection.projection_hash,
        projection=compilation.projection,
        mapping=compilation.mapping,
    )
    from mechcad_harness.candidates import PromotionManifestService

    manifest_store = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="SYNTHETIC-PROMOTION-MANIFESTS"
    )
    manifest_service = PromotionManifestService()
    decision_artifact = manifest_service.publish_decision(
        manifest_store, manifest=decision
    )
    result_artifact = manifest_service.publish_result(
        manifest_store,
        decision_artifact=decision_artifact,
        compilation=compilation,
        proposal=compilation.proposal,
        changeset_id="SYNTHETIC-CHANGESET",
        changed_paths=tuple(operation.path for operation in compilation.proposal.operations),
        resulting_revision=context.application_result.applied_revision,
        resulting_state_hash=context.application_result.applied_state_hash,
    )
    result_artifact_id = result_artifact.artifact_id
    result = manifest_service.resolve_result(manifest_store, result_artifact_id)
    from mechcad_harness.candidates.promotion_models import CandidatePromotionApplicationResult

    application_result = CandidatePromotionApplicationResult.model_validate(
        context.application_result.model_dump(mode="json")
        | {
            "request": request.model_dump(mode="json"),
            "decision_artifact_id": decision_artifact.artifact_id,
            "result_artifact_id": result_artifact_id,
        }
    )
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /physical_mechanisms/*\n    owner: mechcad-physical-mechanism\n",
        encoding="utf-8",
    )
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    application = ProductionApplication.create(
        tmp_path,
        request.project_id,
        _CompositionAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )
    if with_canonical:
        return (
            application,
            application_result,
            selection_publication,
            decision_artifact,
            result_artifact_id,
            canonical_publication,
        )
    return application, application_result, selection_publication, decision_artifact, result_artifact_id


def test_production_verification_uses_exact_candidate_source_snapshot_with_duplicate_scope(
    tmp_path, monkeypatch
):
    (
        application,
        application_result,
        selection_publication,
        _,
        _,
        _,
    ) = _nonlive_promotion_chain_fixture(tmp_path, with_canonical=True)
    application.candidate_provenance_artifact_service.cad_replay_verifier = (
        lambda *args: None
    )
    application.candidate_evaluation_currentness_service.cad_replay_verifier = (
        lambda *args: None
    )
    monkeypatch.setattr(
        application.canonical_m10_service,
        "application",
        _NonLiveCanonicalM10Application(),
    )
    candidate_cad = application.candidate_provenance_artifact_service.resolve_candidate_cad(
        selection_publication.payload.candidate_cad.artifact
    )
    source = candidate_cad.payload.source_step_artifacts[0]
    source_path = tmp_path / source.relative_path
    duplicate = ArtifactStore(
        tmp_path,
        project_id=source.project_id,
        run_id="DUPLICATE-SOURCE",
        task_id="DUPLICATE-TASK",
    ).publish(
        source.artifact_id,
        ArtifactType.STEP,
        "duplicate.step",
        source_path.read_bytes(),
        source.producer_tool_name,
        source.producer_tool_version,
        source.bound_revision,
        source.bound_state_hash,
        input_hash=source.input_hash,
    )
    assert duplicate.sha256 == source.sha256

    verification = application.verify_promoted_mechanism(application_result)

    assert verification.status is PromotedMechanismVerificationStatus.VERIFIED


@pytest.mark.parametrize("mutation", ("missing", "wrong-scope"))
def test_production_verification_rejects_missing_or_wrong_scope_source_before_m10(
    tmp_path, mutation, monkeypatch
):
    (
        application,
        application_result,
        selection_publication,
        _,
        _,
    ) = _nonlive_promotion_chain_fixture(tmp_path)
    application.candidate_provenance_artifact_service.cad_replay_verifier = (
        lambda *args: None
    )
    application.candidate_evaluation_currentness_service.cad_replay_verifier = (
        lambda *args: None
    )
    candidate_cad = application.candidate_provenance_artifact_service.resolve_candidate_cad(
        selection_publication.payload.candidate_cad.artifact
    )
    source = candidate_cad.payload.source_step_artifacts[0]
    source_path = tmp_path / source.relative_path
    if mutation == "missing":
        shutil.rmtree(source_path.parent)
    else:
        metadata_path = source_path.parent / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["run_id"] = "WRONG-SCOPE"
        metadata_path.write_text(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    m10_calls = []
    monkeypatch.setattr(
        application.canonical_m10_service,
        "execute",
        lambda *args: m10_calls.append(args),
    )
    if application_result.schema_version == "candidate-promotion-application-result@2":
        from mechcad_harness.candidates.promotion import (
            PromotedMechanismVerificationIntegrityError,
        )

        with pytest.raises(PromotedMechanismVerificationIntegrityError):
            application.verify_promoted_mechanism(application_result)
    else:
        verification = application.verify_promoted_mechanism(application_result)
        assert verification.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE
    assert m10_calls == []


def test_nonlive_promotion_v2_scope_compiles_mechanism_at4_and_keeps_legacy_at2(
    tmp_path,
):
    from types import SimpleNamespace

    from mechcad_harness.candidates.promotion import (
        CandidatePromotionCompiler,
        CandidatePromotionCompilerV2,
    )
    from mechcad_harness.candidates.promotion_models import CandidatePromotionPolicyV2
    from mechcad_harness.models.physical_mechanism import CanonicalPhysicalMechanism
    from test_m13_2_promotion_canonical_roundtrip import (
        _generated_promotion_fixture,
    )

    context, candidate, evaluation, *_ = _build_nonlive_promotion_context(
        tmp_path, promote=False
    )
    application = context.application
    request = context.application_result.request
    readiness = context.application_result.readiness
    resolved_candidate, synthesis_request, synthesis_policy = (
        application.candidate_provenance_artifact_service._candidate_from_cad(
            context.candidate_cad_publication
        )
    )

    scope_pair = evaluation.m10_scope.pair_scope_requirements[0]
    assert (
        scope_pair.first_constituent_key,
        scope_pair.second_constituent_key,
    ) == ("bearing-a", "output-shaft")
    support = next(
        connection
        for connection in resolved_candidate.realization.connections
        if connection.connection_id == "support-a"
    )
    assert (support.from_instance_id, support.to_instance_id) == (
        "bearing-a",
        "output-shaft",
    )
    assert CandidatePromotionCompiler._interface_for(
        SimpleNamespace(candidate=resolved_candidate),
        "bearing-a",
        "output-shaft",
        "bearing-a",
    ) == "housing"
    assert CandidatePromotionCompiler._interface_for(
        SimpleNamespace(candidate=resolved_candidate),
        "output-shaft",
        "bearing-a",
        "output-shaft",
    ) == "journal-a"

    compiler_v2 = CandidatePromotionCompilerV2(
        project_id=request.project_id,
        mechanism_compiler=application.candidate_promotion_compiler,
    )
    compilation = compiler_v2.compile_v2(
        application.load_state().state,
        request,
        readiness=readiness,
        candidate=resolved_candidate,
        evaluation=evaluation,
        selection=context.selection,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        promotion_policy=CandidatePromotionPolicyV2(),
    )
    mechanism = CanonicalPhysicalMechanism.model_validate(
        compilation.canonical_mechanism.model_dump(mode="json")
    )
    assert mechanism.schema_version == "canonical-physical-mechanism@4"
    assert {
        item.schema_version for item in mechanism.component_specifications
    } == {"canonical-component-specification@4"}
    pair = mechanism.m10_obligations[0].physical_pair_requirements[0]
    assert (pair.first_interface_id, pair.second_interface_id) == (
        "housing",
        "journal-a",
    )

    legacy_manager, legacy_compiler, legacy_request, _ = _generated_promotion_fixture(
        tmp_path / "legacy"
    )
    legacy_compilation = legacy_compiler.compile(
        legacy_manager.load_current_state(legacy_request.project_id), legacy_request
    )
    assert legacy_compilation.canonical_mechanism.schema_version == (
        "canonical-physical-mechanism@2"
    )


def test_promotion_manifest_v2_decision_publishes_and_resolves_typed_records(
    tmp_path,
):
    from mechcad_harness.artifacts import ArtifactStore
    from mechcad_harness.candidates.promotion import CandidatePromotionCompilerV2
    from mechcad_harness.candidates.promotion_models import CandidatePromotionPolicyV2
    from mechcad_harness.runs import SourceBinding

    context, candidate, evaluation, *_ = _build_nonlive_promotion_context(
        tmp_path, promote=False
    )
    application = context.application
    request = context.application_result.request
    readiness = context.application_result.readiness
    resolved_candidate, synthesis_request, synthesis_policy = (
        application.candidate_provenance_artifact_service._candidate_from_cad(
            context.candidate_cad_publication
        )
    )
    compiler = CandidatePromotionCompilerV2(
        project_id=request.project_id,
        mechanism_compiler=application.candidate_promotion_compiler,
    )
    compilation = compiler.compile_v2(
        application.load_state().state,
        request,
        readiness=readiness,
        candidate=resolved_candidate,
        evaluation=evaluation,
        selection=context.selection,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        promotion_policy=CandidatePromotionPolicyV2(),
    )
    scope_projection = compiler.scope_projection_v2(
        request, resolved_candidate, evaluation
    )
    run = application.run_controller.create_run(
        request.project_id,
        expected_source=SourceBinding(
            project_id=request.project_id,
            revision=request.source_revision,
            state_hash=request.source_state_hash,
        ),
    )
    store = ArtifactStore(
        tmp_path,
        project_id=request.project_id,
        run_id=run.run_id,
    )

    artifact = application.promotion_manifest_service.publish_decision_v2(
        store,
        run=run,
        request=request,
        readiness=readiness,
        compilation=compilation,
        pre_promotion_scope_projection=scope_projection,
        provenance_service=application.candidate_provenance_artifact_service,
    )
    resolved = application.promotion_manifest_service.resolve_decision_v2(
        store,
        artifact.artifact_id,
        provenance_service=application.candidate_provenance_artifact_service,
        promotion_request=request,
    )

    assert resolved.decision_hash == artifact.input_hash
    assert resolved.input_reference.promotion_request_hash == request.request_hash
    assert resolved.compilation_hash == compilation.compilation_hash
    assert resolved.projection.schema_version == "promotable-mechanism-projection@2"

    applied_run = application.run_controller.apply_approved_proposal(
        run.run_id, compilation.proposal
    )
    final_run = application.run_controller.get_run(run.run_id)
    invalidation = application.run_controller.evidence.load_invalidation(
        request.project_id, applied_run.active_revision
    )
    result_artifact = application.promotion_manifest_service.publish_result_v2(
        store,
        decision_artifact=artifact,
        compilation=compilation,
        proposal=compilation.proposal,
        invalidation=invalidation,
        final_run=final_run,
        changeset_id=invalidation.changeset_id,
        changed_paths=tuple(invalidation.changed_paths),
        resulting_revision=applied_run.active_revision,
        resulting_state_hash=applied_run.active_state_hash,
        promotion_request=request,
        provenance_service=application.candidate_provenance_artifact_service,
    )
    result = application.promotion_manifest_service.resolve_result_v2(
        store,
        result_artifact.artifact_id,
        promotion_request=request,
        provenance_service=application.candidate_provenance_artifact_service,
    )
    assert result.decision_hash == resolved.decision_hash
    assert result.resulting_revision == request.source_revision + 1
    assert result_artifact.input_hash == artifact.sha256


def test_production_promotion_v2_applies_only_through_runcontroller(tmp_path):
    context, _candidate, _evaluation, *_ = _build_nonlive_promotion_context(
        tmp_path, promote=False
    )
    application = context.application
    request = context.application_result.request

    result = application.promote_selected_candidate(request)

    assert result.status.value == "promotion_applied", result.error
    assert result.compilation.canonical_mechanism.schema_version == (
        "canonical-physical-mechanism@4"
    )
    assert result.applied_revision == request.source_revision + 1
    assert result.decision_artifact_id is not None
    assert result.result_artifact_id is not None
    promoted = application.load_state().state.physical_mechanisms
    assert len(promoted) == 1
    assert promoted[0].mechanism_hash == result.compilation.canonical_mechanism.mechanism_hash


def test_production_verification_v2_reconstructs_canonical_chain(tmp_path):
    context, _candidate, _evaluation, _reconstruction, _cad, _m10 = (
        _build_nonlive_promotion_context(tmp_path, promote=True)
    )
    application = context.application
    application.canonical_m10_service.application = _NonLiveCanonicalM10Application()

    verification = application.verify_promoted_mechanism(
        context.application_result
    )

    assert verification.schema_version == "promoted-mechanism-verification-result@2"
    assert verification.status is PromotedMechanismVerificationStatus.VERIFIED, verification.error
    assert verification.canonical_mechanism_hash == (
        context.application_result.compilation.canonical_mechanism.mechanism_hash
    )


def _build_nonlive_multi_joint_promotion_v2_fixture(
    tmp_path, monkeypatch
):
    from test_candidate_multijoint_m10_v2 import (
        _multi_joint_scope,
        _raw_m10_result,
    )
    from mechcad_harness.candidates.multi_joint_m10_bridge import (
        PhysicalToM10V2BridgeCompiler,
    )
    from mechcad_harness.candidates.promotion import CandidatePromotionCompilerV2
    from mechcad_harness.candidates.promotion_models import (
        CandidateMultiJointPromotionRequestV2,
        CandidatePromotionPolicyV2,
    )

    context, candidate, _single_evaluation, *_ = _build_nonlive_promotion_context(
        tmp_path, promote=False
    )
    application = context.application
    source_request = context.application_result.request
    cad_publication = context.candidate_cad_publication
    cad_realization = cad_publication.payload.realization
    cad_request = cad_publication.payload.request
    resolved_candidate, synthesis_request, synthesis_policy = (
        application.candidate_provenance_artifact_service._candidate_from_cad(
            cad_publication
        )
    )
    assert resolved_candidate == candidate
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    scope = _multi_joint_scope(bridge.model.model_id)
    monkeypatch.setattr(
        application.candidate_multi_joint_m10_evaluation_service,
        "analyze_multi_joint_collision_sweep_v2",
        _raw_m10_result,
    )
    monkeypatch.setattr(application, "_execute_candidate_v2_sweep", _raw_m10_result)
    service = application.candidate_multi_joint_m10_evaluation_service
    multi_request = service.build_request(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        scope,
        cad_request=cad_request,
    )
    multi_evaluation = application.evaluate_candidate_multi_joint_m10(
        candidate, synthesis_request, cad_realization, bridge, multi_request
    )
    multi_selection = application.select_candidate_multi_joint(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        multi_request,
        multi_evaluation,
        "nonlive-mj-selector@1",
        "promote the explicitly selected M13 candidate chain",
    )
    low_request = service.reconstruct_m10_request(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        multi_request,
    )
    from mechcad_harness.revolute_drive import InputProvenanceKind

    p6_result = _raw_m10_result(
        source_revision=multi_request.source_revision,
        source_state_hash=multi_request.source_state_hash,
        assembly=cad_realization.assembly,
        model=low_request.model,
        configurations=low_request.configurations,
        exact_pair_scope=low_request.exact_pair_scope,
        volume_tolerance_mm3=low_request.volume_tolerance_mm3,
        distance_tolerance_mm=low_request.distance_tolerance_mm,
    )
    mj_provenance = application.candidate_provenance_artifact_service.publish_candidate_multi_joint_m10(
        request=multi_request,
        evaluation=multi_evaluation,
        selection=multi_selection,
        m10_v2_result=p6_result,
        candidate_cad=cad_publication,
    )
    assert mj_provenance.payload.selection.selection_hash == multi_selection.selection_hash

    policy = CandidatePromotionPolicyV2()
    classifications = list(
        item
        for item in _promotion_classifications(candidate)
        if not item.source_identity.startswith("candidate:geometry-source:")
    )
    classifications.extend(
        PromotionClassification(
            source_identity=f"candidate:physical-rigid-body:{body.physical_body_id}",
            source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
            classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
        )
        for body in candidate.realization.physical_rigid_body_bindings
    )
    classifications.extend(
        PromotionClassification(
            source_identity=f"candidate:physical-revolute-joint:{joint.physical_joint_id}",
            source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
            classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
        )
        for joint in candidate.realization.physical_revolute_joint_bindings
    )
    classifications.append(
        PromotionClassification(
            source_identity=(
                "candidate:physical-kinematic-root:"
                f"{candidate.realization.kinematic_root_physical_body_id}"
            ),
            source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
            classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            source_value=candidate.realization.kinematic_root_physical_body_id,
        )
    )
    classifications.extend(
        PromotionClassification(
            source_identity=(
                "candidate:physical-pair-classification:"
                f"{pair.first_physical_instance_id}:{pair.second_physical_instance_id}"
            ),
            source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
            classification=PromotionValueClassification.CANONICAL_REDERIVATION_INPUT,
            source_value=f"{pair.classification.value}:{pair.exclusion_reason or ''}",
        )
        for pair in candidate.realization.physical_pair_classification_bindings
    )
    classifications.append(
        PromotionClassification(
            source_identity=(
                "candidate:multi-joint-verification-obligation:"
                f"{multi_request.scope_hash}"
            ),
            source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
            classification=PromotionValueClassification.CANONICAL_REDERIVATION_INPUT,
            source_value=multi_request.scope_hash,
        )
    )
    classifications = tuple(sorted(classifications, key=lambda item: item.source_identity))
    promotion_request = CandidateMultiJointPromotionRequestV2(
        project_id=candidate.source_binding.project_id,
        source_revision=candidate.source_binding.source_revision,
        source_state_hash=candidate.source_binding.source_state_hash,
        candidate_hash=candidate.candidate_hash,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        m12_3_result_hash=source_request.m12_3_result_hash,
        multi_joint_request_hash=multi_request.request_hash,
        multi_joint_evaluation_hash=multi_evaluation.evaluation_hash,
        multi_joint_selection_hash=multi_selection.selection_hash,
        generated_placement_derivations=multi_request.placement_derivations,
        semantic_placement_derivations_hash=(
            multi_request.semantic_placement_derivations_hash
        ),
        promotion_policy_hash=policy.policy_hash,
        canonical_target_mechanism_id="PM-M12-NONLIVE-MJ",
        classifications=classifications,
    )

    result = application.promote_selected_multi_joint_candidate(promotion_request)

    assert result.status.value == "promotion_applied", result.error
    assert result.compilation.canonical_mechanism.schema_version == (
        "canonical-physical-mechanism@4"
    )
    mechanism = result.compilation.canonical_mechanism
    assert len(mechanism.multi_joint_verification_obligations) == 1
    assert (
        mechanism.multi_joint_verification_obligations[0].configuration_set
        == multi_request.scope.configuration_set
    )
    assert result.decision_artifact_id and result.result_artifact_id

    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
        candidate_multi_joint_m10_provenance_artifact_id,
        resolve_mj_provenance_expected_tuple_from_decision_manifest,
        resolve_mj_provenance_expected_tuple_from_result_manifest,
    )

    locator = ArtifactStore(
        tmp_path, project_id=promotion_request.project_id, run_id="LOOKUP"
    )
    decision_artifact = locator.existing_in_project(result.decision_artifact_id)
    result_artifact = locator.existing_in_project(result.result_artifact_id)
    assert decision_artifact is not None and result_artifact is not None
    manifest_store = ArtifactStore(
        tmp_path,
        project_id=promotion_request.project_id,
        run_id=decision_artifact.run_id,
        task_id=decision_artifact.task_id,
    )
    decision_manifest = application.promotion_manifest_service.resolve_multi_joint_decision_v2(
        manifest_store,
        decision_artifact.artifact_id,
        promotion_request=promotion_request,
        multi_joint_provenance_service=(
            application.candidate_provenance_artifact_service
        ),
    )
    expected_tuple_b = resolve_mj_provenance_expected_tuple_from_decision_manifest(
        decision_manifest
    )
    assert expected_tuple_b == (
        multi_request.request_hash,
        multi_evaluation.evaluation_hash,
        multi_selection.selection_hash,
    )
    fresh_provenance = CandidateProvenanceArtifactService(
        tmp_path,
        promotion_request.project_id,
        application.state_manager,
        cad_replay_verifier=application.candidate_cad_realization_service.validate_realization,
    )
    restarted_b = fresh_provenance.resolve_candidate_multi_joint_m10(
        candidate_multi_joint_m10_provenance_artifact_id(expected_tuple_b[2]),
        expected_selection_hash=expected_tuple_b[2],
    )
    result_manifest = application.promotion_manifest_service.resolve_multi_joint_result_v2(
        manifest_store,
        result_artifact.artifact_id,
        promotion_request=promotion_request,
        multi_joint_provenance_service=application.candidate_provenance_artifact_service,
    )
    decision_bytes = (tmp_path / decision_artifact.relative_path).read_bytes()
    expected_tuple_c = resolve_mj_provenance_expected_tuple_from_result_manifest(
        result_manifest,
        decision_artifact_bytes=decision_bytes,
        decision_artifact_hash=decision_artifact.sha256,
    )
    assert expected_tuple_c == expected_tuple_b
    restarted_c = fresh_provenance.resolve_candidate_multi_joint_m10(
        candidate_multi_joint_m10_provenance_artifact_id(expected_tuple_c[2]),
        expected_selection_hash=expected_tuple_c[2],
    )
    assert restarted_b.payload == restarted_c.payload
    return SimpleNamespace(
        application=application,
        promotion_request=promotion_request,
        application_result=result,
        candidate=candidate,
        synthesis_request=synthesis_request,
        multi_joint_request=multi_request,
        multi_joint_evaluation=multi_evaluation,
        multi_joint_selection=multi_selection,
        p6_result=p6_result,
        multi_joint_provenance=mj_provenance,
        decision_artifact=decision_artifact,
        result_artifact=result_artifact,
    )


def test_nonlive_multi_joint_promotion_v2_uses_section18b_and_emits_mechanism_at4(
    tmp_path, monkeypatch
):
    fixture = _build_nonlive_multi_joint_promotion_v2_fixture(tmp_path, monkeypatch)
    assert fixture.application_result.status.value == "promotion_applied"
    assert fixture.application_result.compilation.canonical_mechanism.schema_version == (
        "canonical-physical-mechanism@4"
    )
    assert fixture.multi_joint_provenance.payload.selection == fixture.multi_joint_selection


def test_canonical_bridge_v2_consumes_promoted_mechanism_at4_and_cad_at2(
    tmp_path, monkeypatch
):
    from mechcad_harness.candidates.multi_joint_m10_bridge import (
        PhysicalToM10V2BridgeCompiler,
        MultiJointCollisionPairInventoryV2,
        PhysicalToM10V2BridgeV2,
        validate_canonical_physical_to_m10_v2_bridge_v2,
    )
    from mechcad_harness.candidates.canonical_cad import CanonicalCadRealizationV2
    from mechcad_harness.candidates.models import semantic_candidate_mechanism_hash

    fixture = _build_nonlive_multi_joint_promotion_v2_fixture(tmp_path, monkeypatch)
    application = fixture.application
    reconstruction = application.reconstruct_promoted_mechanism(
        revision=fixture.application_result.applied_revision,
        state_hash=fixture.application_result.applied_state_hash,
        mechanism_id=fixture.promotion_request.canonical_target_mechanism_id,
    )
    cad = application.canonical_cad_compiler.realize(reconstruction)

    bridge = PhysicalToM10V2BridgeCompiler().compile_canonical(reconstruction, cad)

    assert bridge.schema_version == "physical-to-m10-v2-bridge@2"
    assert reconstruction.mechanism.schema_version == "canonical-physical-mechanism@4"
    assert cad.schema_version == "canonical-cad-realization@2"
    assert bridge.physical_mechanism_hash == reconstruction.mechanism.mechanism_hash
    assert bridge.inventory.schema_version == "multi-joint-collision-pair-inventory@2"
    assert bridge.inventory.physical_mechanism_hash == reconstruction.mechanism.mechanism_hash
    assert bridge.inventory.cad_realization_hash == cad.realization_hash
    assert bridge.cad_mapping_hashes == tuple(
        sorted(mapping.mapping_hash for mapping in cad.mappings)
    )
    assert validate_canonical_physical_to_m10_v2_bridge_v2(
        bridge, reconstruction=reconstruction, cad_realization=cad
    ) == bridge
    canonical_verification = application.canonical_multi_joint_m10_verification_service.execute(
        reconstruction, cad
    )
    assert canonical_verification.mechanism_hash == reconstruction.mechanism.mechanism_hash
    assert canonical_verification.canonical_cad_realization_hash == cad.realization_hash
    assert canonical_verification.request.model == bridge.model
    assert canonical_verification.result.continuous_path_verified is False

    # Rotation of the operational assembly name affects raw replay identity,
    # while all accepted canonical semantic bridge inputs remain the same.
    renamed_assembly = cad.assembly.model_copy(update={"assembly_id": "canonical-renamed"})
    renamed_cad = CanonicalCadRealizationV2.model_validate(
        cad.model_dump(mode="json") | {
            "assembly": renamed_assembly.model_dump(mode="json"),
            "assembly_hash": assembly_hash(renamed_assembly),
            "realization_hash": "pending",
        }
    )
    assert renamed_cad.realization_hash == cad.realization_hash
    assert PhysicalToM10V2BridgeCompiler().compile_canonical(
        reconstruction, renamed_cad
    ) == bridge

    for field, value in (("revision", cad.revision + 1), ("state_hash", "sha256:" + "f" * 64)):
        foreign_cad = cad.model_copy(update={field: value})
        with pytest.raises(ValueError):
            PhysicalToM10V2BridgeCompiler().compile_canonical(reconstruction, foreign_cad)

    forged_mapping = cad.mappings[0].model_copy(update={"mapping_hash": "sha256:" + "f" * 64})
    forged_cad = cad.model_copy(update={"mappings": (forged_mapping, *cad.mappings[1:])})
    with pytest.raises(ValueError):
        PhysicalToM10V2BridgeCompiler().compile_canonical(reconstruction, forged_cad)

    candidate_identity = semantic_candidate_mechanism_hash(fixture.candidate.realization)
    assert candidate_identity != bridge.physical_mechanism_hash
    inventory_payload = bridge.inventory.model_dump(mode="json")
    inventory_payload["physical_mechanism_hash"] = candidate_identity
    inventory_payload.pop("inventory_hash")
    foreign_inventory = MultiJointCollisionPairInventoryV2.model_validate(inventory_payload)
    foreign_bridge = PhysicalToM10V2BridgeV2.model_validate(
        bridge.model_dump(mode="json") | {
            "physical_mechanism_hash": candidate_identity,
            "inventory": foreign_inventory.model_dump(mode="json"),
            "inventory_hash": foreign_inventory.inventory_hash,
            "physical_to_m10_bridge_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="trusted canonical/CAD/M13"):
        validate_canonical_physical_to_m10_v2_bridge_v2(
            foreign_bridge, reconstruction=reconstruction, cad_realization=cad
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "selection-missing",
        "selection-wrong-scope",
        "candidate-cad-missing",
        "source-step-missing",
        "evidence-missing",
    ),
)
def test_production_promotion_rejects_invalid_selection_before_canonical_mutation(
    tmp_path, mutation
):
    (
        application,
        promotion_request,
        selection_publication,
    ) = _nonlive_promotion_chain_fixture(tmp_path, promote=False)
    application.candidate_provenance_artifact_service.cad_replay_verifier = (
        lambda *args: None
    )
    selection_path = tmp_path / selection_publication.artifact.relative_path
    provenance = application.candidate_provenance_artifact_service
    if mutation == "selection-missing":
        shutil.rmtree(selection_path.parent)
    elif mutation == "selection-wrong-scope":
        metadata_path = selection_path.parent / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["run_id"] = "FOREIGN-SELECTION-RUN"
        metadata_path.write_text(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
    else:
        candidate_cad = provenance.resolve_candidate_cad(
            selection_publication.payload.candidate_cad.artifact
        )
        if mutation == "candidate-cad-missing":
            shutil.rmtree((tmp_path / candidate_cad.artifact.relative_path).parent)
        elif mutation == "source-step-missing":
            source = candidate_cad.payload.source_step_artifacts[0]
            shutil.rmtree((tmp_path / source.relative_path).parent)
        else:
            evaluation = provenance.resolve_candidate_evaluation(
                selection_publication.payload.evaluation.artifact
            )
            evidence = (
                evaluation.payload.proof_evidence[0]
                if evaluation.payload.proof_evidence
                else evaluation.payload.home_evidence[0]
            )
            (tmp_path / "projects" / application.project_id / "evidence" / f"{evidence.id}.json").unlink()
    before_pointer = application.state_manager.load_current_pointer(application.project_id)

    result = application.promote_selected_candidate(promotion_request)

    assert result.status.value == "pre_apply_failure"
    assert result.error
    assert result.decision_artifact_id is None
    assert application.state_manager.load_current_pointer(application.project_id) == before_pointer
    assert application.load_state().state.physical_mechanisms == []


def _create_restart_chain_fixture(tmp_path):
    (
        application,
        application_result,
        selection_publication,
        decision_artifact,
        result_artifact_id,
        canonical_m10_publication,
    ) = _nonlive_promotion_chain_fixture(tmp_path, with_canonical=True)
    result_artifact = ArtifactStore(
        tmp_path,
        project_id=application.project_id,
        run_id=decision_artifact.run_id,
        task_id=decision_artifact.task_id,
    ).existing_in_project(result_artifact_id)
    assert result_artifact is not None
    provenance = application.candidate_provenance_artifact_service
    provenance.cad_replay_verifier = lambda *args: None
    evaluation = provenance.resolve_candidate_evaluation(
        selection_publication.payload.evaluation.artifact
    )
    candidate_cad = provenance.resolve_candidate_cad(
        selection_publication.payload.candidate_cad.artifact
    )
    candidate_publication = provenance.candidate_publication_service.resolve(
        candidate_cad.payload.candidate_artifact.artifact.artifact_id,
        exact_source_artifacts=candidate_cad.payload.source_step_artifacts,
    )
    canonical_cad = provenance.resolve_canonical_cad(
        canonical_m10_publication.payload.canonical_cad.artifact
    )
    evaluation_bytes = (tmp_path / evaluation.artifact.relative_path).read_bytes()
    ArtifactStore(
        tmp_path,
        project_id=evaluation.artifact.project_id,
        run_id="DISTINCT-EVALUATION-REPLAY",
        task_id="DISTINCT-EVALUATION-TASK",
    ).publish(
        evaluation.artifact.artifact_id,
        evaluation.artifact.artifact_type,
        evaluation.artifact.relative_path.rsplit("/", 1)[-1],
        evaluation_bytes,
        evaluation.artifact.producer_tool_name,
        evaluation.artifact.producer_tool_version,
        evaluation.artifact.bound_revision,
        evaluation.artifact.bound_state_hash,
        input_hash=evaluation.artifact.input_hash,
    )
    request = application_result.request
    manifest_store = ArtifactStore(
        tmp_path,
        project_id=application.project_id,
        run_id=decision_artifact.run_id,
        task_id=decision_artifact.task_id,
    )
    decision_manifest = application.promotion_manifest_service.resolve_decision_v2(
        manifest_store,
        decision_artifact.artifact_id,
        promotion_request=request,
        provenance_service=provenance,
    )
    result_manifest = application.promotion_manifest_service.resolve_result_v2(
        manifest_store,
        result_artifact_id,
        promotion_request=request,
        provenance_service=provenance,
    )
    locators = {
        "project_id": application.project_id,
        "request": request,
        "decision_artifact_id": decision_artifact.artifact_id,
        "decision_artifact_hash": decision_artifact.sha256,
        "decision_run_id": decision_artifact.run_id,
        "decision_task_id": decision_artifact.task_id,
        "decision_hash": decision_manifest.decision_hash,
        "result_artifact_id": result_artifact_id,
        "result_artifact_hash": result_artifact.sha256,
        "result_run_id": result_artifact.run_id,
        "result_task_id": result_artifact.task_id,
        "result_hash": result_manifest.result_hash,
        "selection_artifact_id": selection_publication.artifact.artifact_id,
        "selection_artifact_hash": selection_publication.artifact.sha256,
        "selection_run_id": selection_publication.artifact.run_id,
        "selection_task_id": selection_publication.artifact.task_id,
        "selection_hash": selection_publication.payload.selection.selection_hash,
        "comparison_artifact_id": None,
        "comparison_artifact_hash": None,
        "comparison_result_hash": None,
        "evaluation_artifact_id": evaluation.artifact.artifact_id,
        "evaluation_artifact_hash": evaluation.artifact.sha256,
        "evaluation_run_id": evaluation.artifact.run_id,
        "evaluation_task_id": evaluation.artifact.task_id,
        "evaluation_hash": evaluation.payload.evaluation.evaluation_hash,
        "candidate_cad_artifact_id": candidate_cad.artifact.artifact_id,
        "candidate_cad_artifact_hash": candidate_cad.artifact.sha256,
        "candidate_cad_realization_hash": candidate_cad.payload.realization.realization_hash,
        "candidate_artifact_id": candidate_publication.artifact.artifact_id,
        "candidate_artifact_hash": candidate_publication.artifact.sha256,
        "canonical_m10_artifact_id": canonical_m10_publication.artifact.artifact_id,
        "canonical_m10_artifact_hash": canonical_m10_publication.artifact.sha256,
        "canonical_m10_outcome_hash": canonical_m10_publication.payload.outcome.outcome_hash,
        "canonical_cad_artifact_id": canonical_cad.artifact.artifact_id,
        "canonical_cad_artifact_hash": canonical_cad.artifact.sha256,
        "canonical_cad_realization_hash": canonical_cad.payload.realization.realization_hash,
    }
    return application, locators


def _build_application_from_same_workspace(tmp_path, project_id):
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    application = ProductionApplication.create(
        tmp_path,
        project_id,
        _CompositionAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )
    # The persisted fixture deliberately uses deterministic typed CAD records;
    # no live CAD replay is permitted in this restart-only test.
    application.candidate_provenance_artifact_service.cad_replay_verifier = (
        lambda *args: None
    )
    return application


def test_restart_reconstructs_full_candidate_and_canonical_chain_from_artifacts_only(tmp_path):
    application, locators = _create_restart_chain_fixture(tmp_path)
    del application
    gc.collect()

    restarted = _build_application_from_same_workspace(tmp_path, locators["project_id"])
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceIntegrityError,
    )

    with pytest.raises(CandidateProvenanceIntegrityError, match="missing or ambiguous"):
        restarted.candidate_provenance_artifact_service.resolve_candidate_evaluation(
            locators["evaluation_artifact_id"]
        )
    persisted_selection = (
        restarted.candidate_provenance_artifact_service.resolve_candidate_selection(
            locators["selection_artifact_id"]
        )
    )
    assert persisted_selection.payload.evaluation.artifact.artifact_id == locators[
        "evaluation_artifact_id"
    ]
    assert persisted_selection.payload.evaluation.artifact.sha256 == locators[
        "evaluation_artifact_hash"
    ]
    assert persisted_selection.payload.evaluation.artifact.run_id == locators[
        "evaluation_run_id"
    ]
    assert persisted_selection.payload.evaluation.artifact.task_id == locators[
        "evaluation_task_id"
    ]
    service = restarted.candidate_provenance_artifact_service
    selection = persisted_selection
    evaluation = service.resolve_candidate_evaluation(
        selection.payload.evaluation.artifact
    )
    candidate_cad = service.resolve_candidate_cad(
        selection.payload.candidate_cad.artifact
    )
    candidate_publication = service.candidate_publication_service.resolve(
        candidate_cad.payload.candidate_artifact.artifact.artifact_id,
        exact_source_artifacts=candidate_cad.payload.source_step_artifacts,
    )
    canonical_m10 = service.resolve_canonical_m10(
        locators["canonical_m10_artifact_id"]
    )
    canonical_cad = service.resolve_canonical_cad(
        canonical_m10.payload.canonical_cad.artifact
    )
    manifest_store = ArtifactStore(
        tmp_path,
        project_id=locators["project_id"],
        run_id=locators["decision_run_id"],
        task_id=locators["decision_task_id"],
    )
    decision = restarted.promotion_manifest_service.resolve_decision_v2(
        manifest_store,
        locators["decision_artifact_id"],
        promotion_request=locators["request"],
        provenance_service=service,
    )
    result = restarted.promotion_manifest_service.resolve_result_v2(
        manifest_store,
        locators["result_artifact_id"],
        promotion_request=locators["request"],
        provenance_service=service,
    )

    assert decision.decision_hash == locators["decision_hash"]
    assert decision.input_reference.selection_hash == locators["selection_hash"]
    assert selection.artifact.artifact_id == locators["selection_artifact_id"]
    assert selection.artifact.sha256 == locators["selection_artifact_hash"]
    assert selection.payload.selection.selection_hash == locators["selection_hash"]
    assert evaluation.artifact.artifact_id == locators["evaluation_artifact_id"]
    assert evaluation.payload.evaluation.evaluation_hash == locators["evaluation_hash"]
    assert candidate_cad.artifact.artifact_id == locators["candidate_cad_artifact_id"]
    assert candidate_cad.payload.realization.realization_hash == locators["candidate_cad_realization_hash"]
    assert candidate_publication.artifact.artifact_id == locators["candidate_artifact_id"]
    assert canonical_cad.artifact.artifact_id == locators["canonical_cad_artifact_id"]
    assert canonical_m10.artifact.artifact_id == locators["canonical_m10_artifact_id"]
    assert canonical_m10.payload.outcome.outcome_hash == locators["canonical_m10_outcome_hash"]
    assert canonical_m10.payload.canonical_cad.artifact == canonical_cad.artifact
    assert result.decision_hash == decision.decision_hash
    assert result.result_hash == locators["result_hash"]


def test_promotion_v2_verifies_after_fresh_composition_with_typed_receipt(
    tmp_path, monkeypatch
):
    (
        application,
        application_result,
        _selection_publication,
        _decision_artifact,
        _result_artifact_id,
        _canonical_m10_publication,
    ) = _nonlive_promotion_chain_fixture(tmp_path, with_canonical=True)
    application.candidate_provenance_artifact_service.cad_replay_verifier = (
        lambda *args: None
    )
    application.candidate_evaluation_currentness_service.cad_replay_verifier = (
        lambda *args: None
    )
    monkeypatch.setattr(
        application.canonical_m10_service,
        "application",
        _NonLiveCanonicalM10Application(),
    )
    project_id = application.project_id
    del application
    gc.collect()

    restarted = _build_application_from_same_workspace(tmp_path, project_id)
    restarted.candidate_provenance_artifact_service.cad_replay_verifier = (
        lambda *args: None
    )
    restarted.candidate_evaluation_currentness_service.cad_replay_verifier = (
        lambda *args: None
    )
    monkeypatch.setattr(
        restarted.canonical_m10_service,
        "application",
        _NonLiveCanonicalM10Application(),
    )
    verification = restarted.verify_promoted_mechanism(application_result)
    assert verification.schema_version == "promoted-mechanism-verification-result@2"
    assert verification.status is PromotedMechanismVerificationStatus.VERIFIED


def _comparison_bearing_production_chain(tmp_path, monkeypatch):
    """Production comparison -> selection -> promotion -> verification, no live CAD."""
    context, candidate_a, evaluation_a, *_ = _build_nonlive_promotion_context(
        tmp_path, promote=False
    )
    application = context.application
    request_a = context.application_result.request
    candidate_cad = context.candidate_cad_publication
    candidate_a, synthesis_request, synthesis_policy = (
        application.candidate_provenance_artifact_service._candidate_from_cad(
            candidate_cad
        )
    )
    m12_a = evaluation_a.m12_3_result
    source = application.load_state()
    source_state = application.state_manager.load_revision(
        candidate_a.source_binding.project_id,
        candidate_a.source_binding.source_revision,
    )
    from test_candidate_decision_v2 import _different_generator
    from test_candidate_m10_v2 import _policy_requirements
    from mechcad_harness.candidates.comparison import CandidateComparisonRequestV2
    from mechcad_harness.candidates.promotion_models import (
        CandidatePromotionPolicyV2,
        CandidatePromotionRequestV2,
    )
    from mechcad_harness.revolute_drive import RevoluteDriveRealizationService

    candidate_b = _different_generator(candidate_a)
    assert candidate_b.candidate_hash != candidate_a.candidate_hash
    m12_b = RevoluteDriveRealizationService().evaluate(
        candidate_b,
        synthesis_request,
        synthesis_policy,
        _policy_requirements(),
        source_state=source_state,
    )
    published_b = _evaluate_publish_and_select(
        application,
        tmp_path,
        candidate=candidate_b,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_result=m12_b,
        source=source,
        source_step_artifacts=candidate_cad.payload.source_step_artifacts,
        selector="promotion-fixture-selector-b",
        rationale="promotion fixture second candidate",
        scope_pair=("bearing-shaft-clearance", "bearing-a", "output-shaft"),
    )
    evaluation_b = published_b.evaluation
    assert evaluation_b.evaluation_hash != evaluation_a.evaluation_hash
    assert evaluation_b.evaluation_scope_hash == evaluation_a.evaluation_scope_hash
    policy = application.candidate_comparison_service.policy
    entries = ((candidate_a, evaluation_a), (candidate_b, evaluation_b))
    synthesis_requests = {
        candidate_a.candidate_hash: synthesis_request,
        candidate_b.candidate_hash: synthesis_request,
    }
    ranking_request = CandidateComparisonRequestV2(
        project_id=application.project_id,
        source_binding_hash=candidate_a.semantic_source_binding_hash,
        evaluation_scope_hash=evaluation_a.evaluation_scope_hash,
        policy_hash=policy.policy_hash,
        candidate_evaluation_pairs=(
            (candidate_a.candidate_hash, evaluation_a.evaluation_hash),
            (candidate_b.candidate_hash, evaluation_b.evaluation_hash),
        ),
    )
    ranking = application.compare_candidates(
        ranking_request,
        entries,
        synthesis_requests_by_candidate_hash=synthesis_requests,
    )
    selected = application.select_candidate(
        candidate_a,
        evaluation_a,
        "comparison-fixture-selector",
        "explicitly selected candidate with comparison",
        comparison=ranking,
        comparison_entries=entries,
        synthesis_request=synthesis_request,
        synthesis_requests_by_candidate_hash=synthesis_requests,
    )
    assert selected.comparison_used is True
    assert selected.comparison_result_hash == ranking.result_hash
    promotion_policy = CandidatePromotionPolicyV2()
    classifications = tuple(
        sorted(
            (
                item
                for item in _promotion_classifications(candidate_a)
                if not item.source_identity.startswith("candidate:geometry-source:")
            ),
            key=lambda item: item.source_identity,
        )
    )
    promotion_request = CandidatePromotionRequestV2(
        project_id=application.project_id,
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        candidate_hash=candidate_a.candidate_hash,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        m12_3_result_hash=m12_a.result_hash,
        evaluation_hash=evaluation_a.evaluation_hash,
        selection_hash=selected.selection_hash,
        comparison_used=True,
        comparison_request_hash=ranking_request.request_hash,
        comparison_result_hash=ranking.result_hash,
        comparison_entry_hashes=tuple(
            sorted(
                (entry_candidate.candidate_hash, entry_evaluation.evaluation_hash)
                for entry_candidate, entry_evaluation in entries
            )
        ),
        promotion_policy_hash=promotion_policy.policy_hash,
        canonical_target_mechanism_id="PM-M12-NONLIVE-COMPARISON",
        classifications=classifications,
    )
    application_result = application.promote_selected_candidate(promotion_request)
    assert application_result.status.value == "promotion_applied", application_result.error
    canonical_reconstruction = application.reconstruct_promoted_mechanism(
        revision=application_result.applied_revision,
        state_hash=application_result.applied_state_hash,
        mechanism_id=promotion_request.canonical_target_mechanism_id,
    )
    canonical_cad = application.canonical_cad_compiler.realize(canonical_reconstruction)
    canonical_m10 = CanonicalM10VerificationService(
        _NonLiveCanonicalM10Application()
    ).execute(
        canonical_reconstruction, canonical_cad
    )
    for kind, prefix, records in (
        (
            "analysis.continuous_clearance_proof",
            "EVD-CPROOF-",
            canonical_m10.pair_proofs,
        ),
        (
            "analysis.kinematic_sweep",
            "EVD-KSWEEP-",
            canonical_m10.home_exact_checks,
        ),
    ):
        for record in records:
            evidence_id = prefix + hashlib.sha256(
                (record.request_hash + record.result_hash).encode()
            ).hexdigest()[:24]
            _write_integration_evidence(
                tmp_path,
                candidate_a,
                Evidence(
                    id=evidence_id,
                    kind=kind,
                    summary="canonical fixture evidence",
                    revision=canonical_m10.revision,
                    state_hash=canonical_m10.state_hash,
                    producer_result_id=record.result_hash,
                    input_hash=record.request_hash,
                    output_hash=record.result_hash,
                ),
            )
    application.candidate_provenance_artifact_service.cad_replay_verifier = (
        lambda *args: None
    )
    application.candidate_evaluation_currentness_service.cad_replay_verifier = (
        lambda *args: None
    )
    monkeypatch.setattr(
        application.canonical_m10_service,
        "application",
        _NonLiveCanonicalM10Application(),
    )
    verification = application.verify_promoted_mechanism(application_result)
    assert verification.status is PromotedMechanismVerificationStatus.VERIFIED, verification.error
    located = ArtifactStore(
        tmp_path, project_id=application.project_id, run_id="LOOKUP"
    )
    decision_artifact = located.existing_in_project(
        application_result.decision_artifact_id
    )
    result_artifact = located.existing_in_project(
        application_result.result_artifact_id
    )
    assert decision_artifact is not None and result_artifact is not None
    provenance = application.candidate_provenance_artifact_service
    selection_publication = provenance.resolve_candidate_selection(
        application._candidate_provenance_artifact_id(
            "CANDIDATE-SELECTION-", selected.selection_hash
        )
    )
    comparison_publication = provenance.resolve_candidate_comparison(
        application._candidate_provenance_artifact_id(
            "CANDIDATE-COMPARISON-", ranking.result_hash
        )
    )
    oracles = SimpleNamespace(
        selection_hash=selected.selection_hash,
        comparison_result_hash=ranking.result_hash,
        ranked_candidate_hashes=tuple(ranking.ranked_candidate_hashes),
        candidate_evaluation_pairs=tuple(ranking_request.candidate_evaluation_pairs),
        evaluation_hash=evaluation_a.evaluation_hash,
        candidate_cad_realization_hash=evaluation_a.cad_realization_hash,
        canonical_m10_outcome_hash=verification.canonical_m10_outcome_hash,
    )
    return SimpleNamespace(
        project_id=application.project_id,
        request=promotion_request,
        application_result=application_result,
        decision_artifact=decision_artifact,
        result_artifact=result_artifact,
        selection_artifact=selection_publication.artifact,
        comparison_artifact=comparison_publication.artifact,
        oracles=oracles,
    )


def test_promotion_v2_typed_restart_rejects_missing_comparison_parent(tmp_path, monkeypatch):
    produced = _comparison_bearing_production_chain(tmp_path, monkeypatch)
    request = produced.request
    project_id = produced.project_id
    comparison_path = tmp_path / produced.comparison_artifact.relative_path
    original_bytes = comparison_path.read_bytes()
    metadata_path = comparison_path.parent / "metadata.json"
    original_metadata = metadata_path.read_bytes()
    decision_artifact = produced.decision_artifact
    decision_path = tmp_path / decision_artifact.relative_path
    decision_bytes = decision_path.read_bytes()
    del produced
    gc.collect()

    restarted = _build_application_from_same_workspace(tmp_path, project_id)
    restarted.candidate_provenance_artifact_service.cad_replay_verifier = lambda *args: None
    decision_store = ArtifactStore(
        tmp_path,
        project_id=project_id,
        run_id=decision_artifact.run_id,
        task_id=decision_artifact.task_id,
    )

    comparison_path.unlink()
    metadata_path.unlink()
    from mechcad_harness.candidates.promotion_artifacts import (
        PromotionManifestIntegrityError,
    )

    with pytest.raises(PromotionManifestIntegrityError):
        restarted.promotion_manifest_service.resolve_decision_v2(
            decision_store,
            decision_artifact.artifact_id,
            promotion_request=request,
            provenance_service=restarted.candidate_provenance_artifact_service,
        )
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_path.write_bytes(original_bytes)
    metadata_path.write_bytes(original_metadata)
    assert decision_path.read_bytes() == decision_bytes


def test_comparison_bearing_promotion_resolves_full_chain_from_production_root_after_restart(
    tmp_path, monkeypatch
):
    produced = _comparison_bearing_production_chain(tmp_path, monkeypatch)
    project_id = produced.project_id
    request = produced.request
    decision_artifact = produced.decision_artifact
    result_artifact = produced.result_artifact
    selection_artifact = produced.selection_artifact
    comparison_artifact = produced.comparison_artifact
    oracles = produced.oracles
    del produced
    gc.collect()

    for _ in range(2):
        fresh = _build_application_from_same_workspace(tmp_path, project_id)
        service = fresh.candidate_provenance_artifact_service
        selection = service.resolve_candidate_selection(selection_artifact.artifact_id)
        comparison = service.resolve_candidate_comparison(comparison_artifact.artifact_id)
        evaluation = service.resolve_candidate_evaluation(
            selection.payload.evaluation.artifact
        )
        candidate_cad = service.resolve_candidate_cad(
            selection.payload.candidate_cad.artifact
        )
        decision_store = ArtifactStore(
            tmp_path,
            project_id=project_id,
            run_id=decision_artifact.run_id,
            task_id=decision_artifact.task_id,
        )
        decision = fresh.promotion_manifest_service.resolve_decision_v2(
            decision_store,
            decision_artifact.artifact_id,
            promotion_request=request,
            provenance_service=service,
        )
        result_store = ArtifactStore(
            tmp_path,
            project_id=project_id,
            run_id=result_artifact.run_id,
            task_id=result_artifact.task_id,
        )
        result = fresh.promotion_manifest_service.resolve_result_v2(
            result_store,
            result_artifact.artifact_id,
            promotion_request=request,
            provenance_service=service,
        )
        assert selection.payload.selection.selection_hash == oracles.selection_hash
        assert comparison.payload.result.result_hash == oracles.comparison_result_hash
        assert tuple(comparison.payload.result.ranked_candidate_hashes) == oracles.ranked_candidate_hashes
        assert tuple(comparison.payload.request.candidate_evaluation_pairs) == oracles.candidate_evaluation_pairs
        assert evaluation.payload.evaluation.evaluation_hash == oracles.evaluation_hash
        assert candidate_cad.payload.realization.realization_hash == oracles.candidate_cad_realization_hash
        assert decision.input_reference.comparison_used is True
        assert result.decision_hash == decision.decision_hash
        assert result.decision_artifact_id == decision_artifact.artifact_id
        del fresh, service, selection, comparison, evaluation, candidate_cad, decision, result
        gc.collect()


def test_promotion_negative_provenance_cases_preserve_manifests(tmp_path, monkeypatch):
    application, application_result, selection_publication, decision_artifact, result_artifact_id = (
        _nonlive_promotion_chain_fixture(tmp_path)
    )
    manifest_store = ArtifactStore(
        tmp_path, project_id=application.project_id, run_id=decision_artifact.run_id
    )
    v2 = application_result.schema_version == "candidate-promotion-application-result@2"
    if v2:
        request = application_result.request
        decision = application.promotion_manifest_service.resolve_decision_v2(
            manifest_store,
            decision_artifact.artifact_id,
            promotion_request=request,
            provenance_service=application.candidate_provenance_artifact_service,
        )
    else:
        decision = application.promotion_manifest_service.resolve_decision(
            manifest_store, decision_artifact.artifact_id
        )
    result_artifact = manifest_store.existing(result_artifact_id)
    assert result_artifact is not None
    if v2:
        result = application.promotion_manifest_service.resolve_result_v2(
            manifest_store,
            result_artifact_id,
            promotion_request=request,
            provenance_service=application.candidate_provenance_artifact_service,
        )
    else:
        result = application.promotion_manifest_service.resolve_result(
            manifest_store, result_artifact_id
        )
    decision_path = tmp_path / decision_artifact.relative_path
    result_path = tmp_path / result_artifact.relative_path
    decision_bytes = decision_path.read_bytes()
    result_bytes = result_path.read_bytes()
    decision_semantic_hash = _semantic_identity(decision)
    result_semantic_hash = _semantic_identity(result)
    selection_path = tmp_path / selection_publication.artifact.relative_path
    selection_metadata_path = selection_path.parent / "metadata.json"
    selection_bytes = selection_path.read_bytes()
    selection_metadata = selection_metadata_path.read_bytes()

    canonical_calls = []
    for method_name in (
        "publish_canonical_cad",
        "publish_canonical_m10",
        "resolve_canonical_m10",
    ):
        monkeypatch.setattr(
            application.candidate_provenance_artifact_service,
            method_name,
            lambda *args, _method_name=method_name, **kwargs: canonical_calls.append(
                _method_name
            ),
        )

    def assert_rejected():
        if v2:
            from mechcad_harness.candidates.promotion import (
                PromotedMechanismVerificationIntegrityError,
            )

            with pytest.raises(PromotedMechanismVerificationIntegrityError):
                application.verify_promoted_mechanism(application_result)
        else:
            verification = application.verify_promoted_mechanism(application_result)
            assert verification.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE
        assert canonical_calls == []
        assert decision_path.read_bytes() == decision_bytes
        assert result_path.read_bytes() == result_bytes
        if v2:
            from mechcad_harness.candidates.promotion_artifacts import (
                CandidatePromotionResultManifestV2,
                SelectedCandidateDecisionManifestV2,
            )

            current_decision = SelectedCandidateDecisionManifestV2.model_validate_json(
                decision_path.read_bytes()
            )
            current_result = CandidatePromotionResultManifestV2.model_validate_json(
                result_path.read_bytes()
            )
        else:
            current_decision = application.promotion_manifest_service.resolve_decision(
                manifest_store, decision_artifact.artifact_id
            )
            current_result = application.promotion_manifest_service.resolve_result(
                manifest_store, result_artifact.artifact_id
            )
        assert _semantic_identity(current_decision) == decision_semantic_hash
        assert _semantic_identity(current_result) == result_semantic_hash

    selection_path.unlink()
    assert_rejected()
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_bytes(selection_bytes)
    selection_metadata_path.write_bytes(selection_metadata)

    selection_path.unlink()
    selection_metadata_path.unlink()
    ArtifactStore(
        tmp_path, project_id="PRJ-foreign", run_id=selection_publication.artifact.run_id
    ).publish(
        selection_publication.artifact.artifact_id,
        ArtifactType.JSON,
        "candidate_selection_provenance.json",
        selection_bytes,
        selection_publication.artifact.producer_tool_name,
        selection_publication.artifact.producer_tool_version,
        selection_publication.artifact.bound_revision,
        selection_publication.artifact.bound_state_hash,
        input_hash=selection_publication.artifact.input_hash,
    )
    assert_rejected()
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_bytes(selection_bytes)
    selection_metadata_path.write_bytes(selection_metadata)

    selection_path.unlink()
    selection_metadata_path.unlink()
    ArtifactStore(
        tmp_path,
        project_id="PRJ-M12",
        run_id="WRONG-RUN",
        task_id="WRONG-TASK",
    ).publish(
        selection_publication.artifact.artifact_id,
        ArtifactType.JSON,
        "candidate_selection_provenance.json",
        selection_bytes,
        selection_publication.artifact.producer_tool_name,
        selection_publication.artifact.producer_tool_version,
        selection_publication.artifact.bound_revision,
        selection_publication.artifact.bound_state_hash,
        input_hash=selection_publication.artifact.input_hash,
    )
    assert_rejected()
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_bytes(selection_bytes)
    selection_metadata_path.write_bytes(selection_metadata)

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
    assert application.promotion_application_service.provenance_service is (
        application.candidate_provenance_artifact_service
    )


def test_production_promotion_verification_context_exposes_provenance_service(
    tmp_path, monkeypatch
):
    import mechcad_harness.application as application_module

    application = build_application(tmp_path)
    supplied = SimpleNamespace(project_id=application.project_id)
    captured = []
    expected = object()

    def verify(context):
        captured.append(context)
        return expected

    monkeypatch.setattr(application_module, "verify_promoted_mechanism", verify)

    assert application.verify_promoted_mechanism(supplied) is expected
    assert captured[0].candidate_provenance_artifact_service is (
        application.candidate_provenance_artifact_service
    )


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
    state = production_state()
    state = state.model_copy(
        update={
            "yagi_payload_carrier_requirements": list(
                state.yagi_payload_carrier_requirements
            )
            + _geometry_identities(state)
        }
    )
    StateManager(workspace).create_project(PROJECT_ID, state)
    application = ProductionApplication.create(
        workspace,
        PROJECT_ID,
        UninvokedAgentAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )
    _publish_source_artifacts(application, state)
    return application


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
    state = production_state()
    state = state.model_copy(
        update={
            "yagi_payload_carrier_requirements": list(
                state.yagi_payload_carrier_requirements
            )
            + _geometry_identities(state)
        }
    )
    StateManager(workspace).create_project(PROJECT_ID, state)
    application = ProductionApplication.create(
        workspace,
        PROJECT_ID,
        UninvokedAgentAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
        additional_tool_registrations=m12_4.GearworksTools.registrations(),
    )
    _publish_source_artifacts(application, state)
    return application


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
    original_scope, original_binding, original_request = _BASE_M10_INPUTS(
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
    inventory = CandidateCollisionPairInventory.complete_for(
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
            instance_id: publish_source_step(
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
    candidate, synthesis_request, synthesis_policy, m12_result = m12_4._bounded_legacy_candidate(
        application, source_artifacts, positions
    )
    assert candidate.schema_version == "mechanical-design-candidate@1"
    assert synthesis_request.schema_version == "candidate-synthesis-request@1"
    evaluation, candidate_cad_request, _candidate_scope, _candidate_binding, candidate_m10_request = (
        evaluate_real_candidate(
            application,
            candidate,
            synthesis_request,
            synthesis_policy,
            m12_result,
            scope_pair=(
                "shaft-motor-clearance",
                "output-shaft",
                "drive-motor",
            ),
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
    assert verification.status is PromotedMechanismVerificationStatus.VERIFIED, verification.error
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
        instance_id: publish_source_step(
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
        "driver-gear": publish_gear_step(application, teeth=20),
        "driven-gear": publish_gear_step(application, teeth=100),
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
    candidate, synthesis_request, synthesis_policy, m12_result = m12_4._bounded_legacy_candidate(
        application, source_artifacts, positions,
        architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
        gear_artifact=gear_artifacts,
    )
    assert candidate.schema_version == "mechanical-design-candidate@1"
    assert synthesis_request.schema_version == "candidate-synthesis-request@1"
    evaluation, candidate_cad_request, scope, binding, candidate_m10_request = evaluate_real_candidate(
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
        candidate_b, synthesis_request_b, synthesis_policy_b, m12_result_b = m12_4._bounded_legacy_candidate(
            application, source_artifacts, positions_b,
            architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            gear_artifact=gear_artifacts,
            extra_design_variables=(CandidateDesignVariable(name="comparison-tag", value="b"),),
        )
        assert candidate_b.schema_version == "mechanical-design-candidate@1"
        assert synthesis_request_b.schema_version == "candidate-synthesis-request@1"
        evaluation_b, cad_request_b, scope_b, binding_b, m10_request_b = evaluate_real_candidate(
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
            candidate,
            evaluation,
            "task-18-selector",
            "selected without comparison",
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
