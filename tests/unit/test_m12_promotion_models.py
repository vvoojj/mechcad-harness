from __future__ import annotations

import pytest

from mechcad_harness.candidates import (
    CandidatePromotionPolicy,
    CandidatePromotionRequest,
    CandidatePromotionCompilation,
    CandidateCanonicalInstanceMapping,
    CandidatePromotionApplicationResult,
    CandidateComparisonPolicy,
    CandidateComparisonRequest,
    CandidateComparisonResult,
    CandidateEvaluation,
    CandidateEvaluationPolicy,
    CandidateSelection,
    PostPromotionM11TargetIntent,
    PrePromotionM10ScopeProjection,
    PromotionApplicationStatus,
    PromotionDecisionInputReference,
    PromotionPhysicalPairRequirement,
    PromotionValueClassification,
    PromotableMechanismProjection,
    PromotedMechanismVerificationResult,
    PromotedMechanismVerificationStatus,
    promotion_proposal_hash,
)
from mechcad_harness.changes.operations import ChangeOperation
from mechcad_harness.models import (
    CanonicalComponentSpecification,
    CanonicalPhysicalComponent,
    CanonicalPhysicalComponentRole,
    CanonicalPhysicalMechanism,
    ChangeProposal,
    ProposalStatus,
)
from mechcad_harness.revolute_drive import (
    InputProvenanceKind,
    RevoluteDriveAdmissibilityResult,
)
HASH = "sha256:" + "a" * 64
OTHER_HASH = "sha256:" + "b" * 64


def _promotion_inputs():
    from test_m12_candidate_evaluation import (
        _bound_m10_inputs,
        _evaluation_candidate,
        _evaluation_service,
        _m12_result,
    )

    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    m12_result = _m12_result(candidate)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad,
        m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    selection = CandidateSelection(
        candidate_hash=candidate.candidate_hash,
        evaluation_hash=evaluation.evaluation_hash,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        selector_identity="fixture-selector",
        rationale="fixture selection",
    )
    return candidate, synthesis_request, synthesis_policy, m12_result, evaluation, selection


def _promotion_request(*, inputs=None, **updates):
    candidate, synthesis_request, synthesis_policy, m12_result, evaluation, selection = (
        inputs or _promotion_inputs()
    )
    values = {
        "project_id": candidate.source_binding.project_id,
        "source_revision": candidate.source_binding.source_revision,
        "source_state_hash": candidate.source_binding.source_state_hash,
        "candidate": candidate,
        "synthesis_request": synthesis_request,
        "synthesis_policy": synthesis_policy,
        "m12_3_result": m12_result,
        "evaluation": evaluation,
        "selection": selection,
        "promotion_policy": CandidatePromotionPolicy(),
        "canonical_target_mechanism_id": "PM-1",
    }
    values.update(updates)
    return CandidatePromotionRequest(**values)


def _comparison_bundle(candidate, evaluation, *, pair=None):
    policy = CandidateComparisonPolicy()
    pair = pair or ((candidate.candidate_hash, evaluation.evaluation_hash),)
    metric_values = tuple(
        (candidate_hash, evaluation.metrics[0].value)
        for candidate_hash, _ in pair
    )
    request = CandidateComparisonRequest(
        project_id=candidate.source_binding.project_id,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        policy_hash=policy.policy_hash,
        candidate_evaluation_pairs=pair,
    )
    result = CandidateComparisonResult(
        project_id=request.project_id,
        source_binding_hash=request.source_binding_hash,
        evaluation_scope_hash=request.evaluation_scope_hash,
        policy=policy,
        policy_hash=policy.policy_hash,
        request_hash=request.request_hash,
        candidate_evaluation_pairs=pair,
        ranked_candidate_hashes=tuple(candidate_hash for candidate_hash, _ in pair),
        ranked_evaluation_hashes=tuple(evaluation_hash for _, evaluation_hash in pair),
        metric_values=metric_values,
        ties=(tuple(candidate_hash for candidate_hash, _ in pair),) if len(pair) > 1 else (),
        comparator_version=policy.comparator_version,
    )
    selection = CandidateSelection(
        candidate_hash=candidate.candidate_hash,
        evaluation_hash=evaluation.evaluation_hash,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        selector_identity="fixture-selector",
        rationale="fixture selection",
        comparison_used=True,
        comparison_result_hash=result.result_hash,
    )
    return request, result, selection


def test_promotion_policy_is_frozen_strict_and_contains_no_candidate_values():
    policy = CandidatePromotionPolicy(
        allowed_target_family="canonical_physical_mechanism",
        mapping_schema_version="candidate-canonical-mapping@1",
        compiler_version="candidate-promotion@1",
        allowed_classifications=(
            PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
        ),
        publication_mode="decision_and_result_manifests",
    )

    assert CandidatePromotionPolicy.model_validate(policy.model_dump(mode="json")) == policy
    assert policy.policy_hash.startswith("sha256:")
    with pytest.raises(Exception):
        policy.compiler_version = "forged"
    with pytest.raises(ValueError, match="extra"):
        CandidatePromotionPolicy.model_validate(
            policy.model_dump(mode="json") | {"candidate_hash": HASH}
        )


def test_promotion_models_reject_numeric_and_boolean_coercion():
    reference = {
        "promotion_request_hash": HASH,
        "project_id": "PRJ-1",
        "base_revision": "3",
        "base_state_hash": HASH,
        "candidate_hash": HASH,
        "synthesis_request_hash": HASH,
        "synthesis_policy_hash": HASH,
        "m12_3_result_hash": HASH,
        "evaluation_hash": HASH,
        "selection_hash": HASH,
        "promotion_policy_hash": HASH,
        "canonical_target_mechanism_id": "PM-1",
    }
    with pytest.raises(ValueError):
        PromotionDecisionInputReference(**reference)
    with pytest.raises(ValueError):
        PostPromotionM11TargetIntent(assessment_requested=0)


def test_promotion_request_is_candidate_rich_only_at_the_readiness_boundary():
    assert "candidate" in CandidatePromotionRequest.model_fields
    assert "evaluation" in CandidatePromotionRequest.model_fields
    assert "selection" in CandidatePromotionRequest.model_fields
    assert "promotion_policy" in CandidatePromotionRequest.model_fields


@pytest.mark.parametrize("source_value", [0, 0.0, False])
def test_falsy_policy_origin_classification_is_explicit_not_truthiness_based(source_value):
    classification = CandidateCanonicalInstanceMapping(
        candidate_instance_id="shaft",
        canonical_instance_id="PM-1:shaft",
        canonical_path="/physical_mechanisms/PM-1/components/shaft",
        classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
        source_identity="policy:shaft-diameter",
        source_provenance=InputProvenanceKind.POLICY_ASSUMPTION,
        source_value=source_value,
    )
    assert classification.source_value == source_value
    assert classification.source_provenance is InputProvenanceKind.POLICY_ASSUMPTION
    assert classification.classification is PromotionValueClassification.ACCEPTED_DESIGN_CHOICE


def test_decision_reference_is_manifest_only_and_rejects_rich_payloads():
    reference = PromotionDecisionInputReference(
        promotion_request_hash=HASH,
        project_id="PRJ-1",
        base_revision=3,
        base_state_hash=HASH,
        candidate_hash=HASH,
        synthesis_request_hash=HASH,
        synthesis_policy_hash=HASH,
        m12_3_result_hash=HASH,
        evaluation_hash=HASH,
        selection_hash=HASH,
        comparison_used=False,
        promotion_policy_hash=HASH,
        canonical_target_mechanism_id="PM-1",
        mapping_identities=(HASH,),
        classification_identities=(HASH,),
    )
    assert "candidate" not in reference.model_dump(mode="json")
    assert PromotionDecisionInputReference.model_validate(
        reference.model_dump(mode="json")
    ) == reference
    with pytest.raises(ValueError, match="extra"):
        PromotionDecisionInputReference.model_validate(
            reference.model_dump(mode="json") | {"candidate": {"candidate_hash": HASH}}
        )


def test_pre_promotion_scope_projection_excludes_execution_payloads():
    projection = PrePromotionM10ScopeProjection(
        joint_semantic_key="J-1",
        angle_interval_deg=(-30.0, 30.0),
        path_semantics="single_axis_interval",
        required_clearance_mm=1.0,
        physical_pair_requirements=(
            PromotionPhysicalPairRequirement(
                requirement_key="shaft-body",
                first_instance_id="shaft",
                first_interface_id="body-side",
                second_instance_id="body",
                second_interface_id="shaft-side",
            ),
        ),
        fidelity_requirements=(("shaft", "trusted_source_geometry"),),
        required_home_check_semantics=("home_exact",),
        bounded_limitations=("internal_motion_unmodeled",),
    )
    assert projection.projection_hash.startswith("sha256:")
    with pytest.raises(ValueError, match="extra"):
        PrePromotionM10ScopeProjection.model_validate(
            projection.model_dump(mode="json") | {"proof_budget": 10}
        )

    with pytest.raises(ValueError, match="finite"):
        PrePromotionM10ScopeProjection(
            joint_semantic_key="J-1",
            angle_interval_deg=(-30.0, 30.0),
            required_clearance_mm=float("inf"),
            physical_pair_requirements=projection.physical_pair_requirements,
        )


def test_semantic_proposal_hash_ignores_reused_operational_id_but_tracks_base_and_order():
    first = ChangeOperation(operation="add", path="/physical_mechanisms/PM-1", value={"id": "PM-1"})
    second = ChangeOperation(operation="replace", path="/physical_mechanisms/PM-1/name", value="Updated")
    proposal = ChangeProposal(
        id="reused-id",
        title="promotion",
        status=ProposalStatus.DRAFT,
        base_revision=3,
        base_state_hash=HASH,
        actor="promotion",
        operations=[first, second],
    )

    expected = promotion_proposal_hash(3, HASH, (first, second))
    assert expected != promotion_proposal_hash(3, HASH, (second, first))
    assert expected != promotion_proposal_hash(4, HASH, (first, second))
    assert expected != promotion_proposal_hash(3, OTHER_HASH, (first, second))
    assert proposal.id == "reused-id"


def test_durable_result_types_do_not_require_candidate_application_objects():
    specification = CanonicalComponentSpecification(component_type="shaft", source_identity="source:shaft")
    mechanism = CanonicalPhysicalMechanism(
        id="PM-1",
        name="Promoted mechanism",
        component_specifications=(specification,),
        components=(
            CanonicalPhysicalComponent(
                instance_id="PM-1:shaft",
                specification_hash=specification.specification_hash,
                role=CanonicalPhysicalComponentRole.SHAFT,
            ),
        ),
    )
    proposal = ChangeProposal(
        id="proposal-1",
        title="promotion",
        status=ProposalStatus.DRAFT,
        base_revision=3,
        base_state_hash=HASH,
        actor="promotion",
        operations=[],
    )
    projection = PromotableMechanismProjection(
        canonical_target_mechanism_id="PM-1",
        canonical_instance_ids=("PM-1:shaft",),
        mapping_identities=(HASH,),
    )
    compilation = CandidatePromotionCompilation(
        canonical_mechanism=mechanism,
        proposal=proposal,
        promotion_proposal_hash=promotion_proposal_hash(3, HASH, ()),
        mapping=(),
        projection=projection,
    )
    assert compilation.projection.projection_hash == projection.projection_hash
    assert compilation.validated_proposal() == proposal
    compilation.proposal.operations.append(
        ChangeOperation(operation="remove", path="/physical_mechanisms/PM-1")
    )
    with pytest.raises(ValueError, match="proposal semantic hash"):
        compilation.validated_proposal()
    intent = PostPromotionM11TargetIntent(
        assessment_requested=True,
        target_scope="whole_mechanism",
        requested_analysis_category="linear_static",
    )
    assert intent.intent_hash.startswith("sha256:")
    assert PostPromotionM11TargetIntent.model_validate(intent.model_dump(mode="json")) == intent

    application = CandidatePromotionApplicationResult(status=PromotionApplicationStatus.PRE_APPLY_FAILURE)
    assert CandidatePromotionApplicationResult.model_validate(
        application.model_dump(mode="json")
    ) == application
    verification = PromotedMechanismVerificationResult(
        promotion_result_artifact_id="artifact-1",
        promotion_result_hash=HASH,
        promoted_revision=4,
        promoted_state_hash=HASH,
        canonical_target_mechanism_id="PM-1",
        canonical_mechanism_hash=HASH,
        projection_hash=HASH,
        status=PromotedMechanismVerificationStatus.OPERATIONAL_FAILURE,
    )
    assert PromotedMechanismVerificationResult.model_validate(
        verification.model_dump(mode="json")
    ) == verification


def test_promotion_request_requires_exact_m12_result_binding():
    inputs = _promotion_inputs()
    candidate, _, _, m12_result, evaluation, _ = inputs
    alternate = RevoluteDriveAdmissibilityResult.model_validate(
        m12_result.model_dump(mode="json")
        | {"requirements_hash": OTHER_HASH, "result_hash": "pending"}
    )
    with pytest.raises(ValueError, match="M12-3 result identity"):
        _promotion_request(inputs=inputs, m12_3_result=alternate)
    assert evaluation.m12_3_result_hash != alternate.result_hash


@pytest.mark.parametrize("field", ["m12_3_result", "evaluation", "selection"])
def test_promotion_request_rejects_forged_source_binding_context(field):
    inputs = _promotion_inputs()
    candidate, _, _, m12_result, evaluation, selection = inputs
    replacements = {
        "m12_3_result": RevoluteDriveAdmissibilityResult.model_validate(
            m12_result.model_dump(mode="json")
            | {"source_binding_hash": OTHER_HASH, "result_hash": "pending"}
        ),
        "evaluation": evaluation.model_copy(update={"source_binding_hash": OTHER_HASH}),
        "selection": CandidateSelection.model_validate(
            selection.model_dump(mode="json")
            | {"source_binding_hash": OTHER_HASH, "selection_hash": "pending"}
        ),
    }
    with pytest.raises(ValueError, match="source binding|M12-3 result identity"):
        _promotion_request(inputs=inputs, **{field: replacements[field]})


def test_selection_source_and_scope_must_match_selected_candidate_and_evaluation():
    inputs = _promotion_inputs()
    candidate, _, _, _, evaluation, selection = inputs
    with pytest.raises(ValueError, match="selection source binding"):
        _promotion_request(
            inputs=inputs,
            selection=CandidateSelection.model_validate(
                selection.model_dump(mode="json")
                | {"source_binding_hash": OTHER_HASH, "selection_hash": "pending"}
            ),
        )
    with pytest.raises(ValueError, match="selection evaluation scope"):
        _promotion_request(
            inputs=inputs,
            selection=CandidateSelection.model_validate(
                selection.model_dump(mode="json")
                | {"evaluation_scope_hash": OTHER_HASH, "selection_hash": "pending"}
            ),
        )
    assert candidate.source_binding.project_id == "PRJ-M12"
    assert selection.evaluation_scope_hash == evaluation.evaluation_scope_hash


def test_promotion_request_requires_complete_consistent_comparison_entries():
    candidate, synthesis_request, synthesis_policy, m12_result, evaluation, _ = _promotion_inputs()
    comparison_request, comparison, selection = _comparison_bundle(candidate, evaluation)
    base = dict(
        project_id=candidate.source_binding.project_id,
        source_revision=candidate.source_binding.source_revision,
        source_state_hash=candidate.source_binding.source_state_hash,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_3_result=m12_result,
        evaluation=evaluation,
        selection=selection,
        comparison_used=True,
        comparison=comparison,
        comparison_request=comparison_request,
        comparison_entries=((candidate, evaluation),),
        promotion_policy=CandidatePromotionPolicy(),
        canonical_target_mechanism_id="PM-1",
    )
    assert CandidatePromotionRequest(**base).comparison_used is True

    with pytest.raises(ValueError, match="comparison entries"):
        CandidatePromotionRequest(**{**base, "comparison_entries": ()})

    forged_comparison_request = CandidateComparisonRequest(
        project_id=comparison_request.project_id,
        source_binding_hash=comparison_request.source_binding_hash,
        evaluation_scope_hash=comparison_request.evaluation_scope_hash,
        policy_hash=OTHER_HASH,
        candidate_evaluation_pairs=comparison_request.candidate_evaluation_pairs,
    )
    with pytest.raises(ValueError, match="comparison request/result identity"):
        CandidatePromotionRequest(
            **{
                **base,
                "comparison_request": forged_comparison_request,
            }
        )

    mismatched_pair = ((OTHER_HASH, OTHER_HASH),)
    other_request, other_comparison, other_selection = _comparison_bundle(
        candidate, evaluation, pair=mismatched_pair
    )
    with pytest.raises(ValueError, match="comparison (membership|request/result selected pair)"):
        CandidatePromotionRequest(
            **{
                **base,
                "selection": other_selection,
                "comparison": other_comparison,
                "comparison_request": other_request,
            }
        )


def test_comparison_entries_reject_foreign_member_source_and_scope_context():
    candidate, synthesis_request, synthesis_policy, m12_result, evaluation, _ = _promotion_inputs()
    from test_m12_candidate_evaluation import (
        _bound_m10_inputs,
        _evaluation_candidate,
        _evaluation_service,
        _m12_result,
    )
    from test_m12_candidate_foundation import _state

    foreign_candidate, foreign_synthesis_request, foreign_synthesis_policy = _evaluation_candidate(
        _state().model_copy(update={"id": "DES-FOREIGN"})
    )
    foreign_m12_result = _m12_result(foreign_candidate)
    foreign_cad, foreign_m10, foreign_scope, foreign_binding, foreign_m10_request, foreign_cad_request = (
        _bound_m10_inputs(foreign_candidate)
    )
    foreign_evaluation = _evaluation_service().evaluate(
        foreign_candidate,
        foreign_synthesis_request,
        foreign_synthesis_policy,
        foreign_m12_result,
        foreign_cad,
        foreign_m10,
        CandidateEvaluationPolicy(),
        cad_request=foreign_cad_request,
        m10_request=foreign_m10_request,
        m10_scope=foreign_scope,
        m10_binding=foreign_binding,
    )
    pair = (
        (candidate.candidate_hash, evaluation.evaluation_hash),
        (foreign_candidate.candidate_hash, foreign_evaluation.evaluation_hash),
    )
    comparison_request, comparison, selection = _comparison_bundle(
        candidate, evaluation, pair=pair
    )
    values = {
        "project_id": candidate.source_binding.project_id,
        "source_revision": candidate.source_binding.source_revision,
        "source_state_hash": candidate.source_binding.source_state_hash,
        "candidate": candidate,
        "synthesis_request": synthesis_request,
        "synthesis_policy": synthesis_policy,
        "m12_3_result": m12_result,
        "evaluation": evaluation,
        "selection": selection,
        "comparison_used": True,
        "comparison": comparison,
        "comparison_request": comparison_request,
        "comparison_entries": ((candidate, evaluation), (foreign_candidate, foreign_evaluation)),
        "promotion_policy": CandidatePromotionPolicy(),
        "canonical_target_mechanism_id": "PM-1",
    }
    with pytest.raises(ValueError, match="comparison entry source binding"):
        CandidatePromotionRequest(**values)

    scoped_evaluation_values = evaluation.__dict__.copy()
    scoped_evaluation_values["evaluation_scope_hash"] = OTHER_HASH
    scoped_evaluation = CandidateEvaluation.model_construct(**scoped_evaluation_values)
    scoped_pair = ((candidate.candidate_hash, scoped_evaluation.evaluation_hash),)
    scoped_request, scoped_comparison, scoped_selection = _comparison_bundle(
        candidate, evaluation, pair=scoped_pair
    )
    scoped_values = {
        **values,
        "selection": scoped_selection,
        "comparison": scoped_comparison,
        "comparison_request": scoped_request,
        "comparison_entries": ((candidate, scoped_evaluation),),
        "request_hash": "pending",
    }
    with pytest.raises(ValueError, match="comparison entry evaluation scope"):
        CandidatePromotionRequest.model_construct(**scoped_values).validate_request()
