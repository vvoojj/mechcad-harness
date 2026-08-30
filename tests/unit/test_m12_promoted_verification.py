from __future__ import annotations

from dataclasses import dataclass
import json
from types import ModuleType, SimpleNamespace

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackendError
from mechcad_harness.candidates import (
    CandidateCanonicalInstanceMapping,
    CandidatePromotionApplicationResult,
    CandidatePromotionApplicationService,
    CandidatePromotionCompilation,
    CandidatePromotionCompiler,
    CandidatePromotionRequest,
    MechanicalConnection,
    MechanicalConnectionKind,
    PromotableMechanismProjection,
    PromotionManifestService,
    PromotionValueClassification,
    ProjectArtifactResolver,
)
from mechcad_harness.candidates.canonical_cad import (
    CanonicalCadIntegrityError,
    CanonicalPhysicalCadCompiler,
)
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    CanonicalPhysicalMechanismCompiler,
)
from mechcad_harness.candidates.canonical_m10 import (
    CanonicalM10ScopeEquivalenceResult,
    CanonicalM10VerificationOutcome,
    CanonicalM10VerificationService,
    CanonicalM10VerificationStatus,
)
from mechcad_harness.candidates.promotion import verify_promoted_mechanism
from mechcad_harness.candidates.promotion_models import (
    PromotionApplicationStatus,
    PromotedMechanismVerificationResult,
    PromotedMechanismVerificationStatus,
)
from mechcad_harness.changes import ChangeEngine, ChangeOperation, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceFreshness, EvidenceStore
from mechcad_harness.models import (
    CanonicalAcceptedDesignChoice,
    ChangeProposal,
    DesignState,
    Evidence,
    ProposalStatus,
)
from mechcad_harness.state import StateManager, state_hash

from test_m12_canonical_m10 import _joint_semantic_hash, _proof_result
from test_m12_canonical_physical_mechanism import _mechanism
from test_m12_canonical_reconstruction import _mechanism_with_source
from test_m12_promotion_apply import _request_and_manager
from test_m12_promotion_compiler import _classifications


@dataclass
class _VerificationContext:
    application_result: object
    manifest_store: ArtifactStore
    manifest_service: PromotionManifestService
    canonical_mechanism_compiler: object
    canonical_cad_compiler: object
    canonical_m10_service: object
    scope_equivalence_service: object
    request_scope_projection: object | None = None
    normalized_projection: object | None = None
    m11_handoff: object | None = None


class _CanonicalM10Application:
    def __init__(self, status):
        self.status = status

    def prove_continuous_single_axis_clearance(self, **kwargs):
        return _proof_result(kwargs, self.status)


class _CanonicalCadFailure:
    def realize(self, reconstruction):
        raise RuntimeError("FreeCAD backend failed")


class _WrappedCanonicalCadFailure:
    def realize(self, reconstruction):
        try:
            raise FreeCADBackendError("backend process unavailable")
        except FreeCADBackendError as exc:
            raise CanonicalCadIntegrityError("CAD realization failed") from exc


class _TypedCadResult:
    def __init__(self, realization):
        self.realization = realization

    def realize(self, reconstruction):
        return self.realization


class _TypedM10Result:
    def __init__(self, outcome):
        self.outcome = outcome

    def execute(self, reconstruction, cad):
        return self.outcome


def _context(tmp_path, *, m10_status=CanonicalM10VerificationStatus.VERIFIED_CLEAR):
    import test_m12_candidate_evaluation as evaluation_fixtures

    original_evaluation_candidate = evaluation_fixtures._evaluation_candidate

    def _candidate_with_declared_scope_connection(state=None):
        candidate, synthesis_request, synthesis_policy = original_evaluation_candidate(state)
        realization = candidate.realization.model_copy(
            update={
                "connections": (
                    MechanicalConnection(
                        connection_id="hub-mount-clearance",
                        kind=MechanicalConnectionKind.FIXED_ATTACHMENT,
                        from_instance_id="hub",
                        from_interface_id="body",
                        to_instance_id="mount",
                        to_interface_id="frame",
                    ),
                ),
                "realization_hash": "pending",
            }
        )
        candidate = type(candidate).model_validate(
            candidate.model_dump(mode="json")
            | {"realization": realization.model_dump(mode="json"), "candidate_hash": "pending"}
        )
        return candidate, synthesis_request, synthesis_policy

    evaluation_fixtures._evaluation_candidate = _candidate_with_declared_scope_connection
    try:
        request, base_state, manager = _request_and_manager(tmp_path)
    finally:
        evaluation_fixtures._evaluation_candidate = original_evaluation_candidate
    source = ArtifactStore(tmp_path, project_id=request.project_id, run_id="SOURCE").publish(
        "ART-shaft",
        ArtifactType.STEP,
        "shaft.step",
        b"trusted-canonical-source",
        "freecad",
        "1.1.3",
        request.source_revision,
        request.source_state_hash,
    )
    mechanism = _mechanism_with_source(source.sha256)
    binding = mechanism.joint_bindings[0].model_copy(
        update={
            "semantic_hash": _joint_semantic_hash(mechanism.joint_bindings[0]),
            "binding_hash": "pending",
        }
    )
    mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "joint_bindings": (binding,),
            "accepted_design_choices": mechanism.accepted_design_choices
            + tuple(
                CanonicalAcceptedDesignChoice(
                    key=f"mount-1.geometry.{key}",
                    value=value,
                    origin="explicit_policy_assumption",
                    provenance="test:task-14-review",
                )
                for key, value in (
                    ("length_mm", 40.0),
                    ("width_mm", 30.0),
                    ("thickness_mm", 5.0),
                )
            ),
            "mechanism_hash": "pending",
        }
    )
    promoted_state = base_state.model_copy(update={"physical_mechanisms": [mechanism]})
    applied_snapshot = manager.create_revision(request.project_id, promoted_state)
    resolver = ProjectArtifactResolver(
        ArtifactStore(tmp_path, project_id=request.project_id, run_id="lookup")
    )
    reconstruction_compiler = CanonicalPhysicalMechanismCompiler(
        manager, lambda project_id: resolver
    )
    reconstruction = reconstruction_compiler.reconstruct(
        request.project_id,
        applied_snapshot.revision,
        applied_snapshot.state_hash,
        mechanism.id,
    )
    cad = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)
    m10 = CanonicalM10VerificationService(
        _CanonicalM10Application(m10_status)
    ).execute(reconstruction, cad)

    projection = CandidatePromotionCompiler._projection(mechanism)
    mappings = tuple(
        CandidateCanonicalInstanceMapping(
            candidate_instance_id=candidate_id,
            canonical_instance_id=component_id,
            canonical_path=f"/physical_mechanisms/PM-1/components/{component_id}",
            classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            source_identity=f"candidate:physical-instance:{candidate_id}",
        )
        for candidate_id, component_id in (("shaft", "shaft-1"), ("mount", "mount-1"))
    )
    operation = ChangeOperation(
        operation="add",
        path="/physical_mechanisms/PM-1",
        value=mechanism.model_dump(mode="json"),
    )
    proposal = ChangeProposal(
        id="promotion:PM-1",
        title="Promote PM-1",
        status=ProposalStatus.DRAFT,
        base_revision=request.source_revision,
        base_state_hash=request.source_state_hash,
        actor="candidate-promotion",
        operations=[operation],
    )
    from mechcad_harness.candidates.promotion_models import promotion_proposal_hash

    compilation = CandidatePromotionCompilation(
        canonical_mechanism=mechanism,
        proposal=proposal,
        promotion_proposal_hash=promotion_proposal_hash(
            request.source_revision, request.source_state_hash, (operation,)
        ),
        mapping=mappings,
        projection=projection,
    )
    scope = m10.scope
    frozen_scope = CandidatePromotionApplicationService._scope_projection(request)
    from mechcad_harness.candidates.promotion_artifacts import (
        SelectedCandidateDecisionManifest,
    )
    from mechcad_harness.candidates.promotion_models import PromotionDecisionInputReference

    reference = PromotionDecisionInputReference(
        promotion_request_hash=request.request_hash,
        project_id=request.project_id,
        base_revision=request.source_revision,
        base_state_hash=request.source_state_hash,
        candidate_hash=request.candidate.candidate_hash,
        synthesis_request_hash=request.synthesis_request.request_hash,
        synthesis_policy_hash=request.synthesis_policy.policy_hash,
        m12_3_result_hash=request.m12_3_result.result_hash,
        evaluation_hash=request.evaluation.evaluation_hash,
        selection_hash=request.selection.selection_hash,
        promotion_policy_hash=request.promotion_policy.policy_hash,
        canonical_target_mechanism_id="PM-1",
        mapping_identities=tuple(item.mapping_hash for item in mappings),
        classification_identities=tuple(
            item.classification_hash for item in request.classifications
        ),
    )
    decision = SelectedCandidateDecisionManifest(
        input_reference=reference,
        pre_promotion_scope_projection=frozen_scope,
        promotion_policy_hash=request.promotion_policy.policy_hash,
        base_revision=request.source_revision,
        base_state_hash=request.source_state_hash,
        compilation_hash=compilation.compilation_hash,
        promotion_proposal_hash=compilation.promotion_proposal_hash,
        projection_hash=projection.projection_hash,
        projection=projection,
        mapping=mappings,
    )
    store = ArtifactStore(tmp_path, project_id=request.project_id, run_id="RUN-1")
    manifest_service = PromotionManifestService()
    decision_artifact = manifest_service.publish_decision(store, manifest=decision)
    result_artifact = manifest_service.publish_result(
        store,
        decision_artifact=decision_artifact,
        compilation=compilation,
        proposal=proposal,
        changeset_id="CS-1",
        changed_paths=(operation.path,),
        resulting_revision=applied_snapshot.revision,
        resulting_state_hash=applied_snapshot.state_hash,
    )
    application_result = CandidatePromotionApplicationResult(
        request=request,
        compilation=compilation,
        decision_artifact_id=decision_artifact.artifact_id,
        result_artifact_id=result_artifact.artifact_id,
        applied_revision=applied_snapshot.revision,
        applied_state_hash=applied_snapshot.state_hash,
        status=PromotionApplicationStatus.PROMOTION_APPLIED,
    )
    return _VerificationContext(
        application_result=application_result,
        manifest_store=store,
        manifest_service=manifest_service,
        canonical_mechanism_compiler=reconstruction_compiler,
        canonical_cad_compiler=CanonicalPhysicalCadCompiler(resolver),
        canonical_m10_service=CanonicalM10VerificationService(
            _CanonicalM10Application(m10_status)
        ),
        scope_equivalence_service=SimpleNamespace(
            compare=lambda frozen, derived: CanonicalM10ScopeEquivalenceResult(
                project_id=derived.project_id,
                revision=derived.revision,
                state_hash=derived.state_hash,
                frozen_projection_hash=frozen.projection_hash,
                derived_scope_hash=derived.scope_hash,
                equivalent=True,
            )
        ),
        request_scope_projection=frozen_scope,
    ), source, reconstruction, cad, m10


def test_verified_path_uses_only_typed_records_and_fresh_canonical_execution(tmp_path):
    context, _, _, _, _ = _context(tmp_path)

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.VERIFIED
    assert (result.promoted_revision, result.promoted_state_hash) == (
        context.application_result.applied_revision,
        context.application_result.applied_state_hash,
    )
    assert result.canonical_cad_request_hash
    assert result.canonical_cad_realization_hash
    assert result.canonical_m10_request_hashes
    assert result.canonical_m10_result_hashes


def test_canonical_cad_m10_records_reverify_at_n_plus_one_and_old_nodes_are_stale_after_mechanism_change(
    tmp_path,
):
    context, _, reconstruction, canonical_cad, canonical_m10 = _context(tmp_path)
    manager = context.canonical_mechanism_compiler.state_manager
    evidence_store = EvidenceStore(
        tmp_path, manager, DependencyGraph.from_yaml("config/dependencies.yaml")
    )
    old_cad = type(canonical_cad).model_validate(
        canonical_cad.model_dump(mode="json")
    )
    old_m10 = CanonicalM10VerificationOutcome.model_validate(
        canonical_m10.model_dump(mode="json")
    )
    canonical_store = ArtifactStore(
        tmp_path, project_id=reconstruction.project_id, run_id="CANONICAL-TASK19"
    )
    cad_artifact = canonical_store.publish(
        "CANONICAL-CAD-TASK19",
        ArtifactType.JSON,
        "canonical-cad.json",
        json.dumps(
            {"record": old_cad.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        "canonical-physical-cad-test",
        "1",
        old_cad.revision,
        old_cad.state_hash,
        input_hash=old_cad.request_hash,
    )
    m10_artifact = canonical_store.publish(
        "CANONICAL-M10-TASK19",
        ArtifactType.JSON,
        "canonical-m10.json",
        json.dumps(
            {"record": old_m10.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        "canonical-m10-test",
        "1",
        old_m10.revision,
        old_m10.state_hash,
        input_hash=old_m10.request.request_hash,
    )
    _, persisted_cad_bytes = canonical_store.read_verified_strict(
        cad_artifact.artifact_id, expected_type=ArtifactType.JSON
    )
    _, persisted_m10_bytes = canonical_store.read_verified_strict(
        m10_artifact.artifact_id, expected_type=ArtifactType.JSON
    )
    persisted_cad = type(old_cad).model_validate(
        json.loads(persisted_cad_bytes)["record"]
    )
    persisted_m10 = CanonicalM10VerificationOutcome.model_validate(
        json.loads(persisted_m10_bytes)["record"]
    )
    assert persisted_cad == old_cad
    assert persisted_m10 == old_m10
    proof = old_m10.pair_proofs[0]
    evidence = Evidence(
        id="EVD-CANONICAL-M10-TASK19",
        kind="analysis.continuous_clearance_proof",
        summary="Persisted typed canonical M10 request/result binding for Task 19",
        revision=old_m10.revision,
        state_hash=old_m10.state_hash,
        producer_type="canonical_m10",
        producer_name="canonical-m10-test",
        producer_version="1",
        producer_result_id=proof.result.result_hash,
        input_hash=proof.request.request_hash,
        output_hash=old_m10.outcome_hash,
        continuous_multi_joint_clearance_proof_result_payload={
            "canonical_cad_request_hash": old_cad.request_hash,
            "canonical_cad_realization_hash": old_cad.realization_hash,
            "canonical_m10_request_hash": old_m10.request.request_hash,
            "canonical_m10_outcome_hash": old_m10.outcome_hash,
        },
    )
    evidence_store.write_evidence(reconstruction.project_id, evidence)
    assert (
        evidence_store.get_evidence_freshness(
            reconstruction.project_id, evidence.id
        )
        is EvidenceFreshness.CURRENT
    )

    mechanism = reconstruction.mechanism
    changed_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="json")
        | {
            "name": "changed after canonical M10 result",
            "mechanism_hash": "pending",
        }
    )
    proposal = ChangeProposal(
        id="CP-TASK19-MECHANISM-CHANGE",
        title="Change canonical physical mechanism",
        status=ProposalStatus.DRAFT,
        base_revision=reconstruction.revision,
        base_state_hash=reconstruction.state_hash,
        actor="mechcad-physical-mechanism",
        operations=[
            ChangeOperation(
                operation="replace",
                path=f"/physical_mechanisms/{mechanism.id}",
                value=changed_mechanism.model_dump(mode="json"),
            )
        ],
    )
    applied = ChangeEngine(
        manager, OwnershipPolicy.from_file("config/ownership.yaml")
    ).apply_proposal(reconstruction.project_id, proposal)
    invalidation = evidence_store.build_invalidation(
        reconstruction.project_id,
        applied.snapshot.revision,
        applied.snapshot.parent_revision,
        applied.changed_paths,
        applied.changeset_id,
    )
    evidence_store.record_invalidation(invalidation)

    fresh_manager = StateManager(tmp_path)
    fresh_store = EvidenceStore(
        tmp_path, fresh_manager, DependencyGraph.from_yaml("config/dependencies.yaml")
    )
    assert fresh_manager.load_current_pointer(reconstruction.project_id)["revision"] == 3
    assert (
        fresh_store.get_evidence_freshness(
            reconstruction.project_id, evidence.id
        )
        is EvidenceFreshness.STALE
    )
    assert not fresh_store.is_evidence_fresh(reconstruction.project_id, evidence.id)
    assert fresh_store.get_invalidated_nodes(
        reconstruction.project_id, applied.snapshot.revision
    ) == (
        "analysis.continuous_clearance_proof",
        "analysis.kinematic_sweep",
    )
    assert old_cad.revision == old_m10.revision < applied.snapshot.revision

    fresh_state = fresh_manager.load_revision(
        reconstruction.project_id, applied.snapshot.revision
    )
    assert fresh_state.revision == applied.snapshot.revision
    assert state_hash(fresh_state) == applied.snapshot.state_hash
    fresh_compiler = CanonicalPhysicalMechanismCompiler(
        fresh_manager,
        lambda project_id: ProjectArtifactResolver(
            ArtifactStore(tmp_path, project_id=project_id, run_id="lookup-fresh")
        ),
    )
    fresh_reconstruction = fresh_compiler.reconstruct(
        reconstruction.project_id,
        applied.snapshot.revision,
        applied.snapshot.state_hash,
        reconstruction.mechanism.id,
    )
    with pytest.raises(ValueError, match="does not match canonical reconstruction"):
        context.canonical_m10_service.execute(fresh_reconstruction, persisted_cad)
    fresh_cad = CanonicalPhysicalCadCompiler(
        ProjectArtifactResolver(
            ArtifactStore(
                tmp_path,
                project_id=reconstruction.project_id,
                run_id="lookup-fresh-cad",
            )
        )
    ).realize(fresh_reconstruction)
    fresh_m10 = context.canonical_m10_service.execute(
        fresh_reconstruction, fresh_cad
    )
    assert (fresh_cad.revision, fresh_cad.state_hash) == (
        applied.snapshot.revision,
        applied.snapshot.state_hash,
    )
    assert (fresh_m10.revision, fresh_m10.state_hash) == (
        applied.snapshot.revision,
        applied.snapshot.state_hash,
    )
    assert fresh_cad.request_hash != old_cad.request_hash
    assert fresh_cad.realization_hash != old_cad.realization_hash
    assert fresh_m10.request.request_hash != old_m10.request.request_hash
    assert fresh_m10.outcome_hash != old_m10.outcome_hash
    assert persisted_m10.request.request_hash == old_m10.request.request_hash

    historical = verify_promoted_mechanism(context)
    assert historical.status is PromotedMechanismVerificationStatus.VERIFIED
    assert (historical.promoted_revision, historical.promoted_state_hash) == (
        old_m10.revision,
        old_m10.state_hash,
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (
            CanonicalM10VerificationStatus.COLLISION_WITNESS,
            PromotedMechanismVerificationStatus.ENGINEERING_VIOLATION,
        ),
        (
            CanonicalM10VerificationStatus.NOT_PROVEN,
            PromotedMechanismVerificationStatus.UNRESOLVED,
        ),
    ),
)
def test_canonical_m10_status_mapping_preserves_applied_identity(tmp_path, status, expected):
    context, _, _, _, _ = _context(tmp_path, m10_status=status)

    result = verify_promoted_mechanism(context)

    assert result.status is expected
    assert (result.promoted_revision, result.promoted_state_hash) == (
        context.application_result.applied_revision,
        context.application_result.applied_state_hash,
    )


def test_scope_mismatch_is_typed_unresolved_without_changing_m10_inputs(tmp_path):
    context, _, _, cad, m10 = _context(tmp_path)
    mismatch = context.scope_equivalence_service.compare(
        context.manifest_service.resolve_decision(
            context.manifest_store, context.application_result.decision_artifact_id
        ).pre_promotion_scope_projection,
        m10.scope,
    ).model_copy(update={"equivalent": False, "differences": ("clearance",), "result_hash": "pending"})
    context.scope_equivalence_service = SimpleNamespace(
        compare=lambda frozen, derived: CanonicalM10ScopeEquivalenceResult.model_validate(
            mismatch.model_dump(mode="json")
        )
    )

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.UNRESOLVED
    assert context.application_result.applied_revision == 2
    assert cad.realization_hash == context.canonical_cad_compiler.realize(
        context.canonical_mechanism_compiler.reconstruct(
            context.application_result.request.project_id,
            context.application_result.applied_revision,
            context.application_result.applied_state_hash,
            "PM-1",
        )
    ).realization_hash


def test_cad_backend_exception_is_operational_and_preserves_n_plus_one(tmp_path):
    context, _, _, _, _ = _context(tmp_path)
    context.canonical_cad_compiler = _CanonicalCadFailure()

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.OPERATIONAL_FAILURE
    assert (result.promoted_revision, result.promoted_state_hash) == (
        context.application_result.applied_revision,
        context.application_result.applied_state_hash,
    )


def test_wrapped_cad_backend_exception_remains_operational(tmp_path):
    context, _, _, _, _ = _context(tmp_path)
    context.canonical_cad_compiler = _WrappedCanonicalCadFailure()

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.OPERATIONAL_FAILURE
    assert result.promoted_revision == 2


def test_request_scope_mismatch_cannot_be_hidden_by_self_consistent_manifest(tmp_path):
    context, _, _, _, m10 = _context(tmp_path)
    original_service = context.manifest_service
    decision = original_service.resolve_decision(
        context.manifest_store, context.application_result.decision_artifact_id
    )
    mismatched_scope = type(decision.pre_promotion_scope_projection).model_validate(
        decision.pre_promotion_scope_projection.model_dump(mode="json")
        | {"required_clearance_mm": 99.0, "projection_hash": "pending"}
    )
    mismatched_decision = decision.model_copy(
        update={
            "pre_promotion_scope_projection": mismatched_scope,
            "decision_hash": "pending",
        }
    )
    scope_result = CanonicalM10ScopeEquivalenceResult(
        project_id=m10.project_id,
        revision=m10.revision,
        state_hash=m10.state_hash,
        frozen_projection_hash=mismatched_scope.projection_hash,
        derived_scope_hash=m10.scope.scope_hash,
        equivalent=True,
    )
    context.manifest_service = SimpleNamespace(
        resolve_decision=lambda store, artifact_id: mismatched_decision,
        resolve_result=lambda store, artifact_id: original_service.resolve_result(store, artifact_id),
    )
    context.scope_equivalence_service = SimpleNamespace(
        compare=lambda frozen, derived: scope_result
    )

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_forged_context_scope_projection_is_ignored(tmp_path, monkeypatch):
    context, _, _, _, _ = _context(tmp_path)
    decision = context.manifest_service.resolve_decision(
        context.manifest_store, context.application_result.decision_artifact_id
    )
    recomputed_scope = decision.pre_promotion_scope_projection.model_copy(
        update={"required_clearance_mm": 99.0, "projection_hash": "pending"}
    )
    context.request_scope_projection = decision.pre_promotion_scope_projection
    monkeypatch.setattr(
        CandidatePromotionApplicationService,
        "_scope_projection",
        staticmethod(lambda request: recomputed_scope),
    )

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_malformed_raw_receipt_returns_integrity_failure_without_raising():
    malformed = SimpleNamespace(
        applied_revision="not-a-revision",
        applied_state_hash=object(),
        result_artifact_id=object(),
    )

    result = verify_promoted_mechanism(malformed)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_m10_scope_mechanism_hash_must_match_canonical_mechanism(tmp_path):
    context, _, _, _, m10 = _context(tmp_path)
    tampered_scope = m10.scope.model_copy(
        update={"mechanism_hash": "sha256:" + "9" * 64, "scope_hash": "pending"}
    )
    tampered = m10.model_copy(update={"scope": tampered_scope, "outcome_hash": "pending"})
    context.canonical_m10_service = _TypedM10Result(tampered)

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_tampered_canonical_source_is_integrity_failure(tmp_path):
    context, source, _, _, _ = _context(tmp_path)
    (tmp_path / source.relative_path).write_bytes(b"tampered-source")

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE
    assert result.promoted_revision == context.application_result.applied_revision
    assert result.promoted_state_hash == context.application_result.applied_state_hash


@pytest.mark.parametrize(
    "replacement",
    (
        SimpleNamespace(),
        SimpleNamespace(application_result=SimpleNamespace()),
    ),
)
def test_forged_application_result_is_rejected_before_verified(replacement):
    result = verify_promoted_mechanism(replacement)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


@pytest.mark.parametrize(
    "attribute",
    ("canonical_mechanism_compiler", "canonical_cad_compiler", "canonical_m10_service"),
)
def test_forged_nested_canonical_record_is_rejected(tmp_path, attribute):
    context, _, reconstruction, _, _ = _context(tmp_path)
    if attribute == "canonical_mechanism_compiler":
        context.canonical_mechanism_compiler = SimpleNamespace(
            reconstruct=lambda *args: SimpleNamespace(
                project_id=reconstruction.project_id,
                revision=reconstruction.revision,
                state_hash=reconstruction.state_hash,
                mechanism=reconstruction.mechanism,
            )
        )
    elif attribute == "canonical_cad_compiler":
        context.canonical_cad_compiler = SimpleNamespace(
            realize=lambda *args: SimpleNamespace()
        )
    else:
        context.canonical_m10_service = SimpleNamespace(execute=lambda *args: SimpleNamespace())

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE
    assert result.promoted_revision == context.application_result.applied_revision


def test_m10_cad_realization_hash_cross_binding_is_integrity_failure(tmp_path):
    context, _, _, _, m10 = _context(tmp_path)
    tampered = m10.model_copy(
        update={"cad_realization_hash": "sha256:" + "9" * 64, "outcome_hash": "pending"}
    )
    context.canonical_m10_service = _TypedM10Result(tampered)

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_canonical_cad_selected_source_content_binding_is_integrity_failure(tmp_path):
    context, _, _, cad, _ = _context(tmp_path)
    tampered = cad.model_copy(
        update={
            "selected_source_content_identities": ("sha256:" + "9" * 64,),
            "realization_hash": "pending",
        }
    )
    context.canonical_cad_compiler = _TypedCadResult(tampered)

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_canonical_cad_selected_source_id_binding_is_integrity_failure(tmp_path):
    context, _, _, cad, _ = _context(tmp_path)
    tampered = cad.model_copy(
        update={
            "selected_source_artifact_ids": ("ART-foreign",),
            "realization_hash": "pending",
        }
    )
    context.canonical_cad_compiler = _TypedCadResult(tampered)

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_canonical_cad_source_provenance_binding_is_integrity_failure(tmp_path):
    context, _, _, cad, _ = _context(tmp_path)
    source = cad.selected_source_provenance[0].model_copy(
        update={"bound_revision": cad.revision, "bound_state_hash": cad.state_hash}
    )
    tampered = cad.model_copy(
        update={"selected_source_provenance": (source,), "realization_hash": "pending"}
    )
    context.canonical_cad_compiler = _TypedCadResult(tampered)

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_request_source_binding_must_match_promotion_base(tmp_path):
    context, _, _, _, _ = _context(tmp_path)
    forged_request = context.application_result.request.model_copy(
        update={"source_revision": 9, "request_hash": "pending"}
    )
    context.application_result = context.application_result.model_copy(
        update={"request": forged_request}
    )

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_decision_source_binding_must_match_promotion_request(tmp_path):
    context, _, _, _, _ = _context(tmp_path)
    decision = context.manifest_service.resolve_decision(
        context.manifest_store, context.application_result.decision_artifact_id
    )
    forged_decision = decision.model_copy(
        update={"base_revision": 9, "decision_hash": "pending"}
    )
    context.manifest_service = SimpleNamespace(
        resolve_decision=lambda store, artifact_id: forged_decision,
        resolve_result=lambda store, artifact_id: context.manifest_service.result
        if hasattr(context.manifest_service, "result")
        else PromotionManifestService().resolve_result(store, artifact_id),
    )

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_optional_forged_m11_assessment_is_not_accepted(tmp_path):
    context, _, _, _, _ = _context(tmp_path)
    context.m11_handoff = SimpleNamespace(
        project_id=context.application_result.request.project_id,
        revision=context.application_result.applied_revision,
    )

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_model_shaped_duck_typed_m11_assessment_is_not_accepted(tmp_path, monkeypatch):
    context, _, _, _, _ = _context(tmp_path)
    from mechcad_harness.candidates.promotion_models import PostPromotionM11TargetIntent

    intent = PostPromotionM11TargetIntent()
    request = CandidatePromotionRequest.model_validate(
        context.application_result.request.model_dump(mode="json")
        | {"m11_target_intent": intent.model_dump(mode="json"), "request_hash": "pending"}
    )
    context.application_result = context.application_result.model_copy(update={"request": request})
    decision = context.manifest_service.resolve_decision(
        context.manifest_store, context.application_result.decision_artifact_id
    )
    reference = decision.input_reference.model_copy(
        update={
            "promotion_request_hash": request.request_hash,
            "m11_target_intent": intent,
        }
    )
    decision = decision.model_copy(update={"input_reference": reference, "decision_hash": "pending"})
    manifest_service = context.manifest_service
    context.manifest_service = SimpleNamespace(
        resolve_decision=lambda store, artifact_id: decision,
        resolve_result=lambda store, artifact_id: manifest_service.resolve_result(store, artifact_id),
    )

    class DuckTypedM11:
        @classmethod
        def model_validate(cls, payload):
            return cls()

        def model_dump(self, mode="python"):
            return {
                "project_id": request.project_id,
                "revision": request.source_revision + 1,
                "state_hash": context.application_result.applied_state_hash,
                "mechanism_id": "PM-1",
                "mechanism_hash": "sha256:" + "a" * 64,
                "target_scope": "whole_mechanism",
                "target_instance_id": None,
                "analysis_category": "linear_static",
                "intent_hash": intent.intent_hash,
                "result_hash": "sha256:" + "b" * 64,
                "request": {
                    "project_id": request.project_id,
                    "revision": request.source_revision + 1,
                    "state_hash": context.application_result.applied_state_hash,
                    "mechanism_id": "PM-1",
                    "mechanism_hash": "sha256:" + "a" * 64,
                    "target_scope": "whole_mechanism",
                    "target_instance_id": None,
                    "analysis_category": "linear_static",
                    "intent_hash": intent.intent_hash,
                    "intent": intent.model_dump(mode="json"),
                },
                "result": {
                    "result_hash": "sha256:" + "b" * 64,
                    "status": "unresolved",
                },
            }

    monkeypatch.setitem(
        __import__("sys").modules,
        "mechcad_harness.candidates.m11_handoff",
        ModuleType("mechcad_harness.candidates.m11_handoff"),
    )
    __import__("sys").modules[
        "mechcad_harness.candidates.m11_handoff"
    ].CanonicalM11Handoff = DuckTypedM11
    context.m11_handoff = DuckTypedM11()

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.INTEGRITY_FAILURE


def test_post_application_failure_preserves_applied_identity(tmp_path):
    context, _, _, _, _ = _context(tmp_path)
    context.application_result = context.application_result.model_copy(
        update={
            "status": PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED,
            "error": "result artifact unavailable",
        }
    )

    result = verify_promoted_mechanism(context)

    assert result.status is PromotedMechanismVerificationStatus.OPERATIONAL_FAILURE
    assert result.error == "result artifact unavailable"
    assert result.promoted_revision == 2


def test_verified_result_requires_complete_provenance():
    with pytest.raises(ValueError, match="incomplete"):
        PromotedMechanismVerificationResult(
            status=PromotedMechanismVerificationStatus.VERIFIED,
            promoted_revision=2,
            promoted_state_hash="sha256:" + "a" * 64,
        )
