from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    TrustedSourceArtifact,
    normalized_projection,
)
from mechcad_harness.candidates.promotion import CandidatePromotionCompiler
from mechcad_harness.candidates.m11_handoff import (
    CanonicalM11Handoff,
    CanonicalM11HandoffRequest,
    CanonicalM11HandoffService,
    CanonicalM11HandoffStatus,
    build_handoff_request,
)
from mechcad_harness.candidates.promotion_artifacts import (
    CandidatePromotionResultManifest,
    PromotionManifestService,
)
from mechcad_harness.candidates.promotion_models import (
    CandidateCanonicalInstanceMapping,
    CandidatePromotionApplicationResult,
    CandidatePromotionCompilation,
    PrePromotionM10ScopeProjection,
    PostPromotionM11TargetIntent,
    PromotionDecisionInputReference,
    PromotionApplicationStatus,
    PromotionPhysicalPairRequirement,
    PromotionValueClassification,
    promotion_proposal_hash,
)
from mechcad_harness.changes import ChangeOperation
from mechcad_harness.models import (
    CanonicalPhysicalComponent,
    CanonicalPhysicalComponentRole,
    CanonicalPhysicalMechanism,
    CanonicalComponentSpecification,
    CanonicalGeometrySourceReference,
    ChangeProposal,
    DesignState,
    ProposalStatus,
)
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.structural.geometry import GeometryRealization


HASH = "sha256:" + "a" * 64


def _mechanism(instance_id: str = "body-1") -> CanonicalPhysicalMechanism:
    specification = CanonicalComponentSpecification(
        component_type="fixture",
        source_identity="fixture:specification",
        interfaces=("body",),
    )
    return CanonicalPhysicalMechanism(
        id="mechanism-1",
        name="fixture mechanism",
        component_specifications=(specification,),
        components=(
            CanonicalPhysicalComponent(
                instance_id=instance_id,
                specification_hash=specification.specification_hash,
                role=CanonicalPhysicalComponentRole.MOUNT_OR_SUPPORT,
                interfaces=("body",),
            ),
        ),
    )


def _two_component_mechanism() -> CanonicalPhysicalMechanism:
    first = CanonicalComponentSpecification(
        component_type="fixture",
        source_identity="fixture:first",
        interfaces=("body",),
    )
    second = CanonicalComponentSpecification(
        component_type="fixture",
        source_identity="fixture:second",
        interfaces=("body",),
    )
    return CanonicalPhysicalMechanism(
        id="mechanism-1",
        name="two component mechanism",
        component_specifications=(first, second),
        components=(
            CanonicalPhysicalComponent(
                instance_id="body-1",
                specification_hash=first.specification_hash,
                role=CanonicalPhysicalComponentRole.MOUNT_OR_SUPPORT,
                interfaces=("body",),
            ),
            CanonicalPhysicalComponent(
                instance_id="body-2",
                specification_hash=second.specification_hash,
                role=CanonicalPhysicalComponentRole.DRIVEN_BODY,
                interfaces=("body",),
            ),
        ),
    )


def _reconstruction(
    mechanism: CanonicalPhysicalMechanism,
    *,
    revision=2,
    project_id="project-1",
    trusted_source_references=(),
):
    projection = CandidatePromotionCompiler._projection(mechanism)
    return CanonicalMechanismReconstruction(
        project_id=project_id,
        revision=revision,
        state_hash=HASH,
        canonical_mechanism=mechanism,
        trusted_source_references=trusted_source_references,
        normalized_projection_hash=projection.projection_hash,
    )


@dataclass
class _PromotionEnvelope:
    application_result: CandidatePromotionApplicationResult
    result_manifest: CandidatePromotionResultManifest
    manifest_store: ArtifactStore | None = None
    manifest_service: PromotionManifestService | None = None


def _promotion_result(
    mechanism: CanonicalPhysicalMechanism,
    *,
    tmp_path=None,
    revision=2,
    result_state_hash=HASH,
    intent=None,
):
    operation = ChangeOperation(
        operation="add",
        path=f"/physical_mechanisms/{mechanism.id}",
        value=mechanism.model_dump(mode="json"),
    )
    proposal = ChangeProposal(
        id="proposal-1",
        title="promote fixture",
        status=ProposalStatus.DRAFT,
        base_revision=1,
        base_state_hash=HASH,
        actor="candidate-promotion",
        operations=[operation],
    )
    mappings = tuple(
        CandidateCanonicalInstanceMapping(
            candidate_instance_id=(
                "candidate-body"
                if index == 0
                else f"candidate-{component.instance_id}"
            ),
            canonical_instance_id=component.instance_id,
            canonical_path=(
                f"/physical_mechanisms/{mechanism.id}/components/{component.instance_id}"
            ),
            classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            source_identity=(
                "candidate:instance:"
                + ("candidate-body" if index == 0 else component.instance_id)
            ),
        )
        for index, component in enumerate(mechanism.components)
    )
    compilation = CandidatePromotionCompilation(
        canonical_mechanism=mechanism,
        proposal=proposal,
        promotion_proposal_hash=promotion_proposal_hash(1, HASH, (operation,)),
        mapping=mappings,
        projection=CandidatePromotionCompiler._projection(mechanism),
    )
    result_manifest = CandidatePromotionResultManifest(
        decision_artifact_id="decision-1",
        decision_artifact_hash=HASH,
        promotion_proposal_hash=compilation.promotion_proposal_hash,
        proposal_id=proposal.id,
        changeset_id="changeset-1",
        changed_paths=(operation.path,),
        mechanism_path=operation.path,
        resulting_revision=revision,
        resulting_state_hash=result_state_hash,
    )
    if tmp_path is None:
        receipt = CandidatePromotionApplicationResult(
            compilation=compilation,
            result_artifact_id="result-1",
            applied_revision=revision,
            applied_state_hash=result_state_hash,
            status=PromotionApplicationStatus.PROMOTION_APPLIED,
        )
        return _PromotionEnvelope(receipt, result_manifest)

    store = ArtifactStore(tmp_path, project_id="project-1", run_id="promotion-run")
    service = PromotionManifestService()
    projection = CandidatePromotionCompiler._projection(mechanism)
    reference = PromotionDecisionInputReference(
        promotion_request_hash=HASH,
        project_id="project-1",
        base_revision=1,
        base_state_hash=HASH,
        candidate_hash=HASH,
        synthesis_request_hash=HASH,
        synthesis_policy_hash=HASH,
        m12_3_result_hash=HASH,
        evaluation_hash=HASH,
        selection_hash=HASH,
        promotion_policy_hash=HASH,
        canonical_target_mechanism_id=mechanism.id,
        m11_target_intent=intent,
        mapping_identities=tuple(item.mapping_hash for item in compilation.mapping),
    )
    decision_artifact = service.publish_decision(
        store,
        input_reference=reference,
        pre_promotion_scope_projection=PrePromotionM10ScopeProjection(
            joint_semantic_key="fixture-joint",
            angle_interval_deg=(0.0, 1.0),
            required_clearance_mm=0.1,
            physical_pair_requirements=(
                PromotionPhysicalPairRequirement(
                    requirement_key="fixture-pair",
                    first_instance_id="first",
                    first_interface_id="body",
                    second_instance_id="second",
                    second_interface_id="body",
                ),
            ),
        ),
        promotion_policy_hash=HASH,
        base_revision=1,
        base_state_hash=HASH,
        compilation_hash=compilation.compilation_hash,
        promotion_proposal_hash=compilation.promotion_proposal_hash,
        projection_hash=projection.projection_hash,
        projection=projection,
        mapping=compilation.mapping,
    )
    result_artifact = service.publish_result(
        store,
        decision_artifact=decision_artifact,
        compilation=compilation,
        changeset_id="changeset-1",
        changed_paths=(operation.path,),
        resulting_revision=revision,
        resulting_state_hash=result_state_hash,
    )
    result_manifest = service.resolve_result(store, result_artifact.artifact_id)
    receipt = CandidatePromotionApplicationResult(
        compilation=compilation,
        decision_artifact_id=decision_artifact.artifact_id,
        result_artifact_id=result_artifact.artifact_id,
        applied_revision=revision,
        applied_state_hash=result_state_hash,
        status=PromotionApplicationStatus.PROMOTION_APPLIED,
    )
    return _PromotionEnvelope(receipt, result_manifest, store, service)


def _intent(scope="single_component", candidate_instance_id="candidate-body"):
    return PostPromotionM11TargetIntent(
        target_scope=scope,
        candidate_instance_id=candidate_instance_id,
        analysis_category="linear_static",
    )


def _request_with_durable_mapping(envelope, request, mapping):
    mapping = tuple(
        type(item).model_validate(item.model_dump(mode="json")) for item in mapping
    )
    service = envelope.manifest_service
    store = envelope.manifest_store
    decision = service.resolve_decision(
        store, envelope.application_result.decision_artifact_id
    )
    projection = decision.projection.model_copy(
        update={
            "canonical_instance_ids": tuple(
                item.canonical_instance_id for item in mapping
            ),
            "mapping_identities": tuple(item.mapping_hash for item in mapping),
            "projection_hash": "pending",
        }
    )
    projection_payload = projection.model_dump(mode="json")
    projection_payload["projection_hash"] = "pending"
    projection = type(decision.projection).model_validate(projection_payload)
    reference = decision.input_reference.model_copy(
        update={
            "mapping_identities": tuple(item.mapping_hash for item in mapping),
            "reference_hash": "pending",
        }
    )
    reference_payload = reference.model_dump(mode="json")
    reference_payload["reference_hash"] = "pending"
    reference = type(decision.input_reference).model_validate(reference_payload)
    decision_payload = decision.model_dump(mode="json")
    decision_payload.update(
        {
            "input_reference": reference.model_dump(mode="json"),
            "projection": projection.model_dump(mode="json"),
            "projection_hash": projection.projection_hash,
            "mapping": [item.model_dump(mode="json") for item in mapping],
            "decision_hash": "pending",
        }
    )
    forged_decision = type(decision).model_validate(decision_payload)
    decision_artifact = service.publish_decision(store, manifest=forged_decision)
    result = service.resolve_result(
        store, envelope.application_result.result_artifact_id
    ).model_copy(
        update={
            "decision_artifact_id": decision_artifact.artifact_id,
            "decision_artifact_hash": decision_artifact.sha256,
            "result_hash": "pending",
        }
    )
    result_payload = result.model_dump(mode="json")
    result_payload["result_hash"] = "pending"
    result = type(result).model_validate(result_payload)
    result_artifact = service.publish_result(store, manifest=result)
    return CanonicalM11HandoffRequest.model_validate(
        request.model_dump(mode="json")
        | {
            "decision_artifact_id": decision_artifact.artifact_id,
            "decision_artifact_hash": decision_artifact.sha256,
            "promotion_result_artifact_id": result_artifact.artifact_id,
            "promotion_result_hash": result.result_hash,
            "mapping_hashes": tuple(item.mapping_hash for item in mapping),
            "mapping": [item.model_dump(mode="json") for item in mapping],
            "request_hash": "pending",
        }
    )


def _mechanism_with_source(source):
    specification = CanonicalComponentSpecification(
        component_type="fixture",
        source_identity="fixture:specification",
        interfaces=("body",),
        geometry_source=CanonicalGeometrySourceReference(
            artifact_id=source.artifact_id,
            artifact_hash=source.sha256,
            source_identity="fixture:source",
        ),
    )
    return CanonicalPhysicalMechanism(
        id="mechanism-1",
        name="fixture mechanism",
        component_specifications=(specification,),
        components=(
            CanonicalPhysicalComponent(
                instance_id="body-1",
                specification_hash=specification.specification_hash,
                role=CanonicalPhysicalComponentRole.MOUNT_OR_SUPPORT,
                interfaces=("body",),
            ),
        ),
    )


class _GeometryInspector:
    def __init__(self, solid_count=1):
        self.solid_count = solid_count
        self.paths = []

    def realize_geometry(self, step_path):
        self.paths.append(step_path)
        return GeometryRealization(
            shape_valid=True,
            solid_count=self.solid_count,
            faces=[],
        )


def test_no_intent_produces_no_handoff_assessment():
    mechanism = _mechanism()
    assert build_handoff_request(None, _promotion_result(mechanism), _reconstruction(mechanism)) is None


def test_in_memory_manifest_without_verified_services_is_rejected():
    mechanism = _mechanism()

    with pytest.raises(ValueError, match="manifest verification"):
        build_handoff_request(_intent(), _promotion_result(mechanism), _reconstruction(mechanism))


def test_direct_assessment_without_durable_manifests_is_integrity_failure(tmp_path):
    mechanism = _mechanism()
    mapping = _promotion_result(mechanism).application_result.compilation.mapping
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    request = CanonicalM11HandoffRequest(
        project_id="project-1",
        promoted_revision=promoted_snapshot.revision,
        promoted_state_hash=promoted_snapshot.state_hash,
        canonical_mechanism_id=mechanism.id,
        canonical_mechanism_hash=mechanism.mechanism_hash,
        target_scope=intent.target_scope,
        target_instance_id=mechanism.components[0].instance_id,
        analysis_category=intent.analysis_category,
        intent=intent,
        promotion_result_artifact_id="missing-result",
        promotion_result_hash=HASH,
        decision_artifact_id="missing-decision",
        decision_artifact_hash=HASH,
        promotion_proposal_hash=HASH,
        mapping_hashes=tuple(item.mapping_hash for item in mapping),
        mapping=mapping,
    )

    assessment = CanonicalM11HandoffService(manager).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_assessment_rejects_component_not_selected_by_mapping(tmp_path):
    mechanism = _two_component_mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    ).model_copy(
        update={"target_instance_id": "body-2", "request_hash": "pending"}
    )

    assessment = CanonicalM11HandoffService(manager).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_assessment_rejects_incomplete_durable_mapping(tmp_path):
    mechanism = _two_component_mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    )
    forged_request = _request_with_durable_mapping(
        envelope, request, envelope.application_result.compilation.mapping[:1]
    )

    assessment = CanonicalM11HandoffService(manager).assess(forged_request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_assessment_rejects_foreign_durable_mapping(tmp_path):
    mechanism = _two_component_mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    )
    mapping = envelope.application_result.compilation.mapping[0].model_copy(
        update={
            "canonical_instance_id": "foreign-body",
            "canonical_path": "/physical_mechanisms/mechanism-1/components/foreign-body",
            "mapping_hash": "pending",
        }
    )
    forged_request = _request_with_durable_mapping(
        envelope,
        request,
        (mapping, envelope.application_result.compilation.mapping[1]),
    )

    assessment = CanonicalM11HandoffService(manager).assess(forged_request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_assessment_rejects_self_consistent_forged_mapping_path(tmp_path):
    mechanism = _mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    )
    mapping = envelope.application_result.compilation.mapping[0].model_copy(
        update={
            "canonical_path": "/physical_mechanisms/mechanism-1/components/forged",
            "mapping_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="mapping path"):
        _request_with_durable_mapping(envelope, request, (mapping,))


def test_assessment_rejects_self_consistent_alternate_mapped_component(tmp_path):
    mechanism = _two_component_mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    ).model_copy(update={"target_instance_id": "body-2", "request_hash": "pending"})
    original = envelope.application_result.compilation.mapping
    first = original[0].model_copy(
        update={
            "canonical_instance_id": "body-2",
            "canonical_path": "/physical_mechanisms/mechanism-1/components/body-2",
            "mapping_hash": "pending",
        }
    )
    second = original[1].model_copy(
        update={
            "canonical_instance_id": "body-1",
            "canonical_path": "/physical_mechanisms/mechanism-1/components/body-1",
            "mapping_hash": "pending",
        }
    )
    forged_request = _request_with_durable_mapping(envelope, request, (first, second))

    assessment = CanonicalM11HandoffService(manager).assess(forged_request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_whole_mechanism_request_requires_mechanism_target_identity(tmp_path):
    mechanism = _mechanism()
    intent = PostPromotionM11TargetIntent(target_scope="whole_mechanism")
    request = build_handoff_request(
        intent,
        _promotion_result(mechanism, tmp_path=tmp_path, intent=intent),
        _reconstruction(mechanism),
    )

    with pytest.raises(ValueError, match="whole-mechanism"):
        CanonicalM11HandoffRequest.model_validate(
            request.model_dump(mode="json")
            | {"target_instance_id": "arbitrary-target", "request_hash": "pending"}
        )


@pytest.mark.parametrize("mutation", ("assessment_requested", "scope_version"))
def test_assessment_requires_true_intent_and_supported_scope(tmp_path, mutation):
    mechanism = _mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    )
    if mutation == "assessment_requested":
        false_intent = intent.model_copy(
            update={"assessment_requested": False, "intent_hash": "pending"}
        )
        request = request.model_copy(
            update={"intent": false_intent, "request_hash": "pending"}
        )
    else:
        request = request.model_copy(
            update={
                "eligibility_scope_version": "unsupported-scope@1",
                "request_hash": "pending",
            }
        )

    assessment = CanonicalM11HandoffService(manager).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_superseded_promoted_revision_is_integrity_failure(tmp_path):
    mechanism = _mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    )
    manager.create_revision("project-1", state)

    assessment = CanonicalM11HandoffService(manager).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_unsafe_project_id_is_typed_integrity_failure(tmp_path):
    intent = _intent()
    mapping = _promotion_result(_mechanism()).application_result.compilation.mapping
    request = CanonicalM11HandoffRequest(
        project_id="../unsafe",
        promoted_revision=2,
        promoted_state_hash=HASH,
        canonical_mechanism_id="mechanism-1",
        canonical_mechanism_hash=HASH,
        target_scope=intent.target_scope,
        target_instance_id="body-1",
        analysis_category=intent.analysis_category,
        intent=intent,
        promotion_result_artifact_id="result-1",
        promotion_result_hash=HASH,
        decision_artifact_id="decision-1",
        decision_artifact_hash=HASH,
        promotion_proposal_hash=HASH,
        mapping_hashes=tuple(item.mapping_hash for item in mapping),
        mapping=mapping,
    )

    assessment = CanonicalM11HandoffService(StateManager(tmp_path)).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


@pytest.mark.parametrize("artifact_field", ("decision_artifact_id", "result_artifact_id"))
def test_applied_promotion_requires_both_durable_artifact_ids(tmp_path, artifact_field):
    mechanism = _mechanism()
    envelope = _promotion_result(
        mechanism, tmp_path=tmp_path, intent=_intent()
    )
    envelope.application_result = envelope.application_result.model_copy(
        update={artifact_field: None}
    )

    with pytest.raises(ValueError, match="decision and result artifacts"):
        build_handoff_request(_intent(), envelope, _reconstruction(mechanism))


def test_whole_mechanism_is_not_eligible(tmp_path):
    mechanism = _mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = PostPromotionM11TargetIntent(target_scope="whole_mechanism")
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    )

    assessment = CanonicalM11HandoffService(manager).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.NOT_ELIGIBLE
    assert assessment.result.reason == "whole_mechanism_target"


def test_single_solid_without_structural_authority_is_unresolved(tmp_path):
    mechanism = _mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    reconstruction = _reconstruction(mechanism, revision=2).model_copy(
        update={"state_hash": promoted_snapshot.state_hash}
    )
    envelope = _promotion_result(mechanism, tmp_path=tmp_path, result_state_hash=promoted_snapshot.state_hash, intent=_intent())
    envelope.application_result = envelope.application_result.model_copy(
        update={"applied_state_hash": promoted_snapshot.state_hash}
    )
    envelope.result_manifest = envelope.result_manifest.model_copy(
        update={"resulting_state_hash": promoted_snapshot.state_hash, "result_hash": "pending"}
    )
    request = build_handoff_request(
        _intent(),
        envelope,
        reconstruction,
    )

    assessment = CanonicalM11HandoffService(manager).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.UNRESOLVED
    assert "structural definition" in assessment.result.reason
    assert promoted_snapshot.revision == 2


def test_complete_single_solid_without_trusted_source_is_unresolved(tmp_path):
    from test_structural_models import make_definition

    mechanism = _mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(
        id="state-1",
        revision=1,
        physical_mechanisms=[mechanism],
        structural_analysis_definitions=[make_definition()],
    )
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    promoted_state_hash = promoted_snapshot.state_hash
    reconstruction = _reconstruction(mechanism, revision=2)
    reconstruction = reconstruction.model_copy(update={"state_hash": promoted_state_hash})
    envelope = _promotion_result(mechanism, tmp_path=tmp_path, result_state_hash=promoted_state_hash, intent=_intent())
    envelope.application_result = envelope.application_result.model_copy(
        update={"applied_state_hash": promoted_state_hash}
    )
    envelope.result_manifest = envelope.result_manifest.model_copy(
        update={"resulting_state_hash": promoted_state_hash, "result_hash": "pending"}
    )
    request = build_handoff_request(_intent(), envelope, reconstruction)

    class StructuralExecutionSpy:
        def execute(self, request):
            raise AssertionError("M11 execution must not be called")

    assessment = CanonicalM11HandoffService(manager, structural_service=StructuralExecutionSpy()).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.UNRESOLVED
    assert assessment.result.reason == "canonical geometry source is missing"


def test_complete_single_solid_with_trusted_source_is_eligible_without_executing_structural_service(tmp_path):
    import hashlib

    source_hash = "sha256:" + hashlib.sha256(b"trusted-source").hexdigest()
    mechanism = _mechanism_with_source(
        SimpleNamespace(artifact_id="SOURCE-1", sha256=source_hash)
    )
    manager = StateManager(tmp_path)
    from test_structural_models import make_definition

    state = DesignState(
        id="state-1",
        revision=1,
        physical_mechanisms=[mechanism],
        structural_analysis_definitions=[make_definition()],
    )
    manager.create_project("project-1", state)
    source = ArtifactStore(tmp_path, project_id="project-1", run_id="source-run").publish(
        "SOURCE-1",
        ArtifactType.STEP,
        "fixture.step",
        b"trusted-source",
        "freecad",
        "1.1.3",
        1,
        HASH,
    )
    promoted_snapshot = manager.create_revision("project-1", state)
    reconstruction = _reconstruction(
        mechanism,
        trusted_source_references=(TrustedSourceArtifact.from_artifact(source),),
    ).model_copy(update={"state_hash": promoted_snapshot.state_hash})
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=_intent(),
    )
    request = build_handoff_request(_intent(), envelope, reconstruction)

    class StructuralExecutionSpy:
        def execute(self, request):
            raise AssertionError("M11 execution must not be called")

    assessment = CanonicalM11HandoffService(
        manager,
        structural_service=StructuralExecutionSpy(),
        geometry_adapter=_GeometryInspector(),
    ).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.ELIGIBLE


@pytest.mark.parametrize(
    "intent",
    (_intent("single_component", "not-promoted"), _intent("single_component", "foreign")),
)
def test_target_not_promoted_or_foreign_fails_integrity(intent, tmp_path):
    mechanism = _mechanism()

    with pytest.raises(ValueError, match="mapping"):
        build_handoff_request(
            intent,
            _promotion_result(mechanism, tmp_path=tmp_path, intent=intent),
            _reconstruction(mechanism),
        )


def test_ambiguous_target_mapping_fails_integrity(tmp_path):
    mechanism = _mechanism()
    envelope = _promotion_result(
        mechanism, tmp_path=tmp_path, intent=_intent()
    )
    mapping = envelope.application_result.compilation.mapping[0]
    duplicate = mapping.model_copy(update={"mapping_hash": "pending"})
    compilation = envelope.application_result.compilation.model_copy(
        update={"mapping": (mapping, duplicate), "compilation_hash": "pending"}
    )
    envelope.application_result = envelope.application_result.model_copy(update={"compilation": compilation})

    with pytest.raises(ValueError, match="mapping"):
        build_handoff_request(_intent(), envelope, _reconstruction(mechanism))


@pytest.mark.parametrize("field", ("applied_revision", "applied_state_hash"))
def test_stale_promotion_binding_fails_integrity(field, tmp_path):
    mechanism = _mechanism()
    envelope = _promotion_result(
        mechanism, tmp_path=tmp_path, intent=_intent()
    )
    value = 9 if field == "applied_revision" else "sha256:" + "b" * 64
    envelope.application_result = envelope.application_result.model_copy(update={field: value})

    with pytest.raises(ValueError, match="binding"):
        build_handoff_request(_intent(), envelope, _reconstruction(mechanism))


def test_handoff_models_are_strict_frozen_and_content_addressed(tmp_path):
    mechanism = _mechanism()
    request = build_handoff_request(
        _intent(),
        _promotion_result(mechanism, tmp_path=tmp_path, intent=_intent()),
        _reconstruction(mechanism),
    )
    assessment = CanonicalM11HandoffService().assess(request)

    assert CanonicalM11HandoffRequest.model_validate(request.model_dump(mode="json")) == request
    assert CanonicalM11Handoff.model_validate(assessment.model_dump(mode="json")) == assessment
    assert assessment.handoff_hash == CanonicalM11Handoff.model_validate(
        assessment.model_dump(mode="json")
    ).handoff_hash
    with pytest.raises(ValidationError):
        request.analysis_category = "linear_static"
    with pytest.raises(ValidationError):
        CanonicalM11HandoffRequest.model_validate(
            request.model_dump(mode="json") | {"unexpected": True}
        )


def test_result_manifest_is_required_and_tampering_is_integrity_failure():
    mechanism = _mechanism()
    receipt = _promotion_result(mechanism).application_result

    with pytest.raises(ValueError, match="durable promotion manifest verification"):
        build_handoff_request(_intent(), receipt, _reconstruction(mechanism))

    envelope = _promotion_result(mechanism)
    envelope.result_manifest = envelope.result_manifest.model_copy(
        update={"promotion_proposal_hash": HASH, "result_hash": "pending"}
    )
    with pytest.raises(ValueError, match="durable promotion manifest verification"):
        build_handoff_request(_intent(), envelope, _reconstruction(mechanism))


def test_receipt_decision_artifact_must_match_verified_result(tmp_path):
    mechanism = _mechanism()
    envelope = _promotion_result(
        mechanism, tmp_path=tmp_path, intent=_intent()
    )
    envelope.application_result = envelope.application_result.model_copy(
        update={"decision_artifact_id": "PROMOTION-DECISION-forged"}
    )

    with pytest.raises(ValueError, match="decision"):
        build_handoff_request(_intent(), envelope, _reconstruction(mechanism))


def test_cross_project_manifest_binding_fails_integrity(tmp_path):
    mechanism = _mechanism()
    envelope = _promotion_result(
        mechanism, tmp_path=tmp_path, intent=_intent()
    )

    with pytest.raises(ValueError, match="project"):
        build_handoff_request(
            _intent(), envelope, _reconstruction(mechanism, project_id="project-2")
        )


def test_substituted_intent_fails_durable_binding(tmp_path):
    mechanism = _mechanism()
    envelope = _promotion_result(
        mechanism, tmp_path=tmp_path, intent=_intent()
    )
    substituted_intent = PostPromotionM11TargetIntent(target_scope="whole_mechanism")

    with pytest.raises(ValueError, match="intent"):
        build_handoff_request(
            substituted_intent, envelope, _reconstruction(mechanism)
        )


def test_foreign_self_consistent_mapping_path_fails_integrity(tmp_path):
    mechanism = _mechanism()
    envelope = _promotion_result(
        mechanism, tmp_path=tmp_path, intent=_intent()
    )
    mapping = envelope.application_result.compilation.mapping[0].model_copy(
        update={
            "canonical_path": "/physical_mechanisms/other-mechanism/components/body-1",
            "mapping_hash": "pending",
        }
    )
    compilation = envelope.application_result.compilation.model_copy(
        update={"mapping": (mapping,), "compilation_hash": "pending"}
    )
    envelope.application_result = envelope.application_result.model_copy(
        update={"compilation": compilation}
    )

    with pytest.raises(ValueError, match="mapping"):
        build_handoff_request(_intent(), envelope, _reconstruction(mechanism))


def test_stale_whole_mechanism_request_fails_integrity(tmp_path):
    mechanism = _mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = PostPromotionM11TargetIntent(target_scope="whole_mechanism")
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    ).model_copy(update={"promoted_revision": 99, "request_hash": "pending"})

    assessment = CanonicalM11HandoffService(manager).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_tampered_persisted_state_is_integrity_failure(tmp_path):
    import json

    mechanism = _mechanism()
    manager = StateManager(tmp_path)
    state = DesignState(id="state-1", revision=1, physical_mechanisms=[mechanism])
    manager.create_project("project-1", state)
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    request = build_handoff_request(
        intent,
        envelope,
        _reconstruction(mechanism).model_copy(
            update={"state_hash": promoted_snapshot.state_hash}
        ),
    )
    snapshot_path = manager._revision_path("project-1", promoted_snapshot.revision)
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    payload["state"]["id"] = "tampered-state"
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    assessment = CanonicalM11HandoffService(manager).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_multibody_target_is_not_eligible(tmp_path):
    import hashlib

    source_hash = "sha256:" + hashlib.sha256(b"multi-solid-source").hexdigest()
    mechanism = _mechanism_with_source(
        SimpleNamespace(artifact_id="SOURCE-1", sha256=source_hash)
    )
    manager = StateManager(tmp_path)
    from test_structural_models import make_definition

    state = DesignState(
        id="state-1",
        revision=1,
        physical_mechanisms=[mechanism],
        structural_analysis_definitions=[make_definition()],
    )
    manager.create_project("project-1", state)
    source = ArtifactStore(tmp_path, project_id="project-1", run_id="source-run").publish(
        "SOURCE-1",
        ArtifactType.STEP,
        "fixture.step",
        b"multi-solid-source",
        "freecad",
        "1.1.3",
        1,
        HASH,
    )
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    reconstruction = _reconstruction(
        mechanism,
        trusted_source_references=(TrustedSourceArtifact.from_artifact(source),),
    ).model_copy(update={"state_hash": promoted_snapshot.state_hash})
    request = build_handoff_request(intent, envelope, reconstruction)

    assessment = CanonicalM11HandoffService(
        manager,
        geometry_adapter=_GeometryInspector(solid_count=2),
    ).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.NOT_ELIGIBLE
    assert assessment.result.reason == "multibody_target"


def test_declared_but_missing_geometry_artifact_is_integrity_failure(tmp_path):
    import hashlib

    source_hash = "sha256:" + hashlib.sha256(b"missing-source").hexdigest()
    mechanism = _mechanism_with_source(
        SimpleNamespace(artifact_id="SOURCE-1", sha256=source_hash)
    )
    manager = StateManager(tmp_path)
    from test_structural_models import make_definition

    state = DesignState(
        id="state-1",
        revision=1,
        physical_mechanisms=[mechanism],
        structural_analysis_definitions=[make_definition()],
    )
    manager.create_project("project-1", state)
    source = ArtifactStore(tmp_path, project_id="project-1", run_id="source-run").publish(
        "SOURCE-1",
        ArtifactType.STEP,
        "fixture.step",
        b"missing-source",
        "freecad",
        "1.1.3",
        1,
        HASH,
    )
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    reconstruction = _reconstruction(
        mechanism,
        trusted_source_references=(TrustedSourceArtifact.from_artifact(source),),
    ).model_copy(update={"state_hash": promoted_snapshot.state_hash})
    request = build_handoff_request(intent, envelope, reconstruction)
    source_path = tmp_path / source.relative_path
    source_path.unlink()

    assessment = CanonicalM11HandoffService(
        manager, geometry_adapter=_GeometryInspector()
    ).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE


def test_duplicate_authority_gaps_are_deduplicated(tmp_path):
    mechanism = _mechanism()
    envelope = _promotion_result(
        mechanism, tmp_path=tmp_path, intent=_intent()
    )
    request = build_handoff_request(
        _intent(), envelope, _reconstruction(mechanism)
    )

    assessment = CanonicalM11HandoffService._assessment(
        request,
        CanonicalM11HandoffStatus.UNRESOLVED,
        "structural authority is incomplete",
        ("material_authority", "material_authority"),
    )

    assert assessment.result.missing_authority == ("material_authority",)


def test_geometry_source_binding_tamper_is_integrity_failure(tmp_path):
    import hashlib
    import json

    source_hash = "sha256:" + hashlib.sha256(b"bound-source").hexdigest()
    mechanism = _mechanism_with_source(
        SimpleNamespace(artifact_id="SOURCE-1", sha256=source_hash)
    )
    manager = StateManager(tmp_path)
    from test_structural_models import make_definition

    state = DesignState(
        id="state-1",
        revision=1,
        physical_mechanisms=[mechanism],
        structural_analysis_definitions=[make_definition()],
    )
    manager.create_project("project-1", state)
    source = ArtifactStore(tmp_path, project_id="project-1", run_id="source-run").publish(
        "SOURCE-1",
        ArtifactType.STEP,
        "fixture.step",
        b"bound-source",
        "freecad",
        "1.1.3",
        1,
        HASH,
    )
    promoted_snapshot = manager.create_revision("project-1", state)
    intent = _intent()
    envelope = _promotion_result(
        mechanism,
        tmp_path=tmp_path,
        result_state_hash=promoted_snapshot.state_hash,
        intent=intent,
    )
    reconstruction = _reconstruction(
        mechanism,
        trusted_source_references=(TrustedSourceArtifact.from_artifact(source),),
    ).model_copy(update={"state_hash": promoted_snapshot.state_hash})
    request = build_handoff_request(intent, envelope, reconstruction)
    metadata_path = (tmp_path / source.relative_path).parent / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["bound_state_hash"] = "sha256:" + "b" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    assessment = CanonicalM11HandoffService(
        manager, geometry_adapter=_GeometryInspector()
    ).assess(request)

    assert assessment.status is CanonicalM11HandoffStatus.INTEGRITY_FAILURE
