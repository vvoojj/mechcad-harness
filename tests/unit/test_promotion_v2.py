from __future__ import annotations

import pytest

from mechcad_harness.candidates.promotion_models import (
    CandidatePromotionPolicyV2,
    CandidatePromotionRequestV2,
    CandidateMultiJointPromotionRequestV2,
    CandidatePromotionCompilationV2,
    PromotableMechanismProjectionV2,
    PrePromotionM10ScopeProjectionV2,
    PromotionDecisionInputReferenceV2,
    MultiJointPromotionDecisionInputReferenceV2,
    PromotedMechanismVerificationResultV2,
    CandidatePromotionApplicationResultV2,
    CandidateMultiJointPromotionApplicationResultV2,
    PromotionValueClassification,
    PromotionClassification,
    PostPromotionM11TargetIntent,
    CandidateCanonicalInstanceMappingV3,
)
from mechcad_harness.candidates.promotion import (
    PromotionReadinessV2,
    MultiJointPromotionReadinessV2,
    CandidatePromotionCompilerV2,
)
from mechcad_harness.candidates.promotion_artifacts import (
    SelectedCandidateDecisionManifestV2,
    SelectedMultiJointCandidateDecisionManifestV2,
    CandidatePromotionResultManifestV2,
    MultiJointPromotionResultManifestV2,
)
from mechcad_harness.revolute_drive import InputProvenanceKind

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64
HASH_D = "sha256:" + "d" * 64


def _mapping_v3(cid="c1", kid="k1"):
    return CandidateCanonicalInstanceMappingV3(
        candidate_instance_id=cid,
        canonical_instance_id=kid,
        canonical_path=f"/physical_components/{kid}",
        classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
        source_identity=f"src-{cid}-{kid}",
        source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
        source_value="v1",
    )


def _classification(sid="src-1"):
    return PromotionClassification(
        source_identity=sid,
        source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
        classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
        source_value="v1",
    )


def _policy_v2():
    return CandidatePromotionPolicyV2()


def _single_request():
    return CandidatePromotionRequestV2(
        project_id="p1",
        source_revision=1,
        source_state_hash=HASH_A,
        candidate_hash=HASH_A,
        synthesis_request_hash=HASH_B,
        synthesis_policy_hash=HASH_C,
        m12_3_result_hash=HASH_A,
        evaluation_hash=HASH_B,
        selection_hash=HASH_C,
        promotion_policy_hash=HASH_D,
        canonical_target_mechanism_id="mech-1",
        classifications=(_classification(),),
    )


def test_exact_counts():
    assert len(CandidatePromotionRequestV2.model_fields) == 19
    assert len(CandidateMultiJointPromotionRequestV2.model_fields) == 18
    assert len(PromotionReadinessV2.model_fields) == 19
    assert len(MultiJointPromotionReadinessV2.model_fields) == 20
    assert len(CandidatePromotionCompilationV2.model_fields) == 7
    assert len(PromotableMechanismProjectionV2.model_fields) == 20
    assert len(PrePromotionM10ScopeProjectionV2.model_fields) == 10
    assert len(PromotionDecisionInputReferenceV2.model_fields) == 20
    assert len(MultiJointPromotionDecisionInputReferenceV2.model_fields) == 25
    assert len(SelectedCandidateDecisionManifestV2.model_fields) == 12
    assert len(SelectedMultiJointCandidateDecisionManifestV2.model_fields) == 11
    assert len(CandidatePromotionResultManifestV2.model_fields) == 13
    assert len(MultiJointPromotionResultManifestV2.model_fields) == 15
    assert len(PromotedMechanismVerificationResultV2.model_fields) == 20
    assert len(CandidatePromotionApplicationResultV2.model_fields) == 9
    assert len(CandidateMultiJointPromotionApplicationResultV2.model_fields) == 10
    assert len(CandidatePromotionPolicyV2.model_fields) == 8


def test_ordering_and_duplicates():
    m1 = _mapping_v3("c1", "k1")
    m2 = _mapping_v3("c2", "k2")
    # Sorted ok.
    req = CandidatePromotionRequestV2(
        project_id="p1",
        source_revision=1,
        source_state_hash=HASH_A,
        candidate_hash=HASH_A,
        synthesis_request_hash=HASH_B,
        synthesis_policy_hash=HASH_C,
        m12_3_result_hash=HASH_A,
        evaluation_hash=HASH_B,
        selection_hash=HASH_C,
        comparison_used=True,
        comparison_request_hash=HASH_A,
        comparison_result_hash=HASH_B,
        comparison_entry_hashes=((HASH_A, HASH_B), (HASH_A, HASH_C)),
        promotion_policy_hash=HASH_D,
        canonical_target_mechanism_id="mech-1",
    )
    assert req.comparison_entry_hashes == ((HASH_A, HASH_B), (HASH_A, HASH_C))
    # Unsorted entries reject.
    with pytest.raises(ValueError, match="sorted"):
        CandidatePromotionRequestV2(
            project_id="p1",
            source_revision=1,
            source_state_hash=HASH_A,
            candidate_hash=HASH_A,
            synthesis_request_hash=HASH_B,
            synthesis_policy_hash=HASH_C,
            m12_3_result_hash=HASH_A,
            evaluation_hash=HASH_B,
            selection_hash=HASH_C,
            comparison_used=True,
            comparison_request_hash=HASH_A,
            comparison_result_hash=HASH_B,
            comparison_entry_hashes=((HASH_A, HASH_C), (HASH_A, HASH_B)),
            promotion_policy_hash=HASH_D,
            canonical_target_mechanism_id="mech-1",
        )
    # Duplicate mappings reject in readiness.
    with pytest.raises(ValueError, match="unique"):
        PromotionReadinessV2(
            project_id="p1",
            source_revision=1,
            source_state_hash=HASH_A,
            semantic_source_binding_hash=HASH_A,
            request_hash=HASH_B,
            candidate_hash=HASH_A,
            m12_3_result_hash=HASH_A,
            evaluation_hash=HASH_B,
            selection_hash=HASH_C,
            evaluation_scope_hash=HASH_D,
            promotion_policy_hash=HASH_D,
            canonical_target_mechanism_id="mech-1",
            mapping=(m1, m1),
            classification_identities=(HASH_A,),
        )


def test_typed_request_parent_and_at1_rejection(tmp_path):
    from test_candidate_decision_v2 import _decision_evaluation
    from mechcad_harness.candidates.models import CandidateSynthesisRequest

    records = _decision_evaluation(tmp_path)
    candidate = records["candidate"]
    synthesis_request = records["synthesis_request"]
    assert synthesis_request.schema_version == "candidate-synthesis-request@2"

    policy = _policy_v2()
    compiler = CandidatePromotionCompilerV2(project_id=candidate.source_binding.project_id)
    mapping = (_mapping_v3(),)
    req = CandidatePromotionRequestV2(
        project_id=candidate.source_binding.project_id,
        source_revision=synthesis_request.source_binding.source_revision,
        source_state_hash=synthesis_request.source_binding.source_state_hash,
        candidate_hash=candidate.candidate_hash,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=candidate.synthesis_policy_hash,
        m12_3_result_hash=records["admissibility"].result_hash,
        evaluation_hash=records["evaluation"].evaluation_hash,
        selection_hash=HASH_C,  # selection hash placeholder for readiness test
        promotion_policy_hash=policy.policy_hash,
        canonical_target_mechanism_id="mech-1",
    )
    # Positive path with exact typed parent succeeds to readiness (selection hash mismatch
    # is not checked at readiness except via request equality; use request's own selection).
    readiness = compiler.validate_readiness_v2(
        req,
        synthesis_request=synthesis_request,
        candidate=candidate,
        m12_3_result_hash=records["admissibility"].result_hash,
        evaluation_hash=records["evaluation"].evaluation_hash,
        selection_hash=req.selection_hash,
        evaluation_scope_hash=records["evaluation"].evaluation_scope_hash,
        promotion_policy=policy,
        mapping=mapping,
    )
    assert readiness.schema_version == "candidate-promotion-readiness@2"
    assert readiness.candidate_hash == candidate.candidate_hash

    # @1 request rejection.
    legacy = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@1",
        source_binding=synthesis_request.source_binding,
        requested_joint_ids=synthesis_request.requested_joint_ids,
        required_joint_ids=synthesis_request.required_joint_ids,
    )
    with pytest.raises(ValueError, match="@2|@1"):
        compiler.validate_readiness_v2(
            req,
            synthesis_request=legacy,
            candidate=candidate,
            m12_3_result_hash=records["admissibility"].result_hash,
            evaluation_hash=records["evaluation"].evaluation_hash,
            selection_hash=req.selection_hash,
            evaluation_scope_hash=records["evaluation"].evaluation_scope_hash,
            promotion_policy=policy,
            mapping=mapping,
        )

    # Semantic-binding substitution rejection (forged request).
    forged = type(synthesis_request).model_validate(
        synthesis_request.model_dump(mode="json")
        | {"semantic_source_binding_hash": "sha256:" + "f" * 64, "request_hash": "pending"}
    )
    with pytest.raises(ValueError, match="semantic|binding|mismatch"):
        compiler.validate_readiness_v2(
            req,
            synthesis_request=forged,
            candidate=candidate,
            m12_3_result_hash=records["admissibility"].result_hash,
            evaluation_hash=records["evaluation"].evaluation_hash,
            selection_hash=req.selection_hash,
            evaluation_scope_hash=records["evaluation"].evaluation_scope_hash,
            promotion_policy=policy,
            mapping=mapping,
        )


def test_single_joint_promotion_v2_accepts_candidate_realization_v1(tmp_path):
    from mechcad_harness.candidates.promotion_models import (
        CandidateCanonicalInstanceMappingV3,
    )
    from mechcad_harness.revolute_drive.service import RevoluteDriveRealizationService
    from test_candidate_m10_v2 import _policy_requirements
    from test_candidate_trusted_semantic_verification import _at2_setup

    _, _, _, _, synthesis_request, synthesis_policy, candidate = _at2_setup(
        tmp_path
    )
    assert candidate.realization.schema_version == "physical-mechanism-realization@1"
    m12_result = RevoluteDriveRealizationService().evaluate(
        candidate, synthesis_request, synthesis_policy, _policy_requirements()
    )
    promotion_policy = CandidatePromotionPolicyV2()
    mapping = tuple(
        sorted(
            (
                CandidateCanonicalInstanceMappingV3(
                    candidate_instance_id=component.instance_id,
                    canonical_instance_id=f"mech-1:{component.instance_id}",
                    canonical_path=(
                        f"/physical_mechanisms/mech-1/components/mech-1:{component.instance_id}"
                    ),
                    classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                    source_identity=f"candidate:physical-instance:{component.instance_id}",
                    source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
                    source_value=None,
                )
                for component in candidate.realization.components
            ),
            key=lambda item: (
                item.candidate_instance_id,
                item.canonical_instance_id,
            ),
        )
    )
    request = CandidatePromotionRequestV2(
        project_id=candidate.source_binding.project_id,
        source_revision=candidate.source_binding.source_revision,
        source_state_hash=candidate.source_binding.source_state_hash,
        candidate_hash=candidate.candidate_hash,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        m12_3_result_hash=m12_result.result_hash,
        evaluation_hash=HASH_B,
        selection_hash=HASH_C,
        promotion_policy_hash=promotion_policy.policy_hash,
        canonical_target_mechanism_id="mech-1",
    )

    readiness = CandidatePromotionCompilerV2(
        project_id=candidate.source_binding.project_id
    ).validate_readiness_v2(
        request,
        synthesis_request=synthesis_request,
        candidate=candidate,
        m12_3_result_hash=m12_result.result_hash,
        evaluation_hash=request.evaluation_hash,
        selection_hash=request.selection_hash,
        evaluation_scope_hash=HASH_D,
        promotion_policy=promotion_policy,
        mapping=mapping,
    )

    assert readiness.schema_version == "candidate-promotion-readiness@2"
    assert readiness.candidate_hash == candidate.candidate_hash


def test_receipts_exact_type():
    req = _single_request()
    with pytest.raises(ValueError, match="exact"):
        CandidatePromotionApplicationResultV2(
            request={"not": "typed"},
            status="promotion_applied",
        )
    # MJ receipt requires exact readiness type.
    with pytest.raises(ValueError, match="exact"):
        CandidateMultiJointPromotionApplicationResultV2(
            readiness={"not": "typed"},
            status="pre_apply_failure",
            error="x",
        )


def test_single_vs_mj_result_and_projection():
    # 12-vs-13 distinction: @1 single has no decision_hash, @2 single has it.
    from mechcad_harness.candidates.promotion_artifacts import CandidatePromotionResultManifest

    assert "decision_hash" not in CandidatePromotionResultManifest.model_fields
    assert "decision_hash" in CandidatePromotionResultManifestV2.model_fields
    assert len(CandidatePromotionResultManifestV2.model_fields) == 13
    assert len(MultiJointPromotionResultManifestV2.model_fields) == 15
    # Projection expansion: @2 includes canonical_mechanism_hash.
    assert "canonical_mechanism_hash" in PromotableMechanismProjectionV2.model_fields
    assert len(PromotableMechanismProjectionV2.model_fields) == 20


def test_decision_hash_linkage_and_raw_invariance():
    base = dict(
        decision_artifact_id="dec-1",
        decision_artifact_hash=HASH_A,
        decision_hash=HASH_B,
        promotion_proposal_hash=HASH_C,
        changed_paths=("/physical_mechanisms/m1",),
        mechanism_path="/physical_mechanisms/m1",
        resulting_revision=2,
        resulting_state_hash=HASH_D,
    )
    r1 = CandidatePromotionResultManifestV2(**base)
    # Raw-only variation (artifact hash) leaves semantic result hash invariant.
    r2 = CandidatePromotionResultManifestV2(**{**base, "decision_artifact_hash": HASH_C})
    assert r1.result_hash == r2.result_hash
    # Decision-hash variation changes semantic result hash.
    r3 = CandidatePromotionResultManifestV2(**{**base, "decision_hash": HASH_C})
    assert r3.result_hash != r1.result_hash


def test_policy_admission_vs_wire_read():
    # Wire-read allows @1/@2/@3.
    for v in ("candidate-canonical-mapping@1", "candidate-canonical-mapping@2", "candidate-canonical-mapping@3"):
        p = CandidatePromotionPolicyV2(mapping_schema_version=v)
        assert p.mapping_schema_version == v
    # New production admits @3 only.
    CandidatePromotionPolicyV2(mapping_schema_version="candidate-canonical-mapping@3").admit_new_production()
    with pytest.raises(ValueError, match="@3"):
        CandidatePromotionPolicyV2(mapping_schema_version="candidate-canonical-mapping@1").admit_new_production()
    with pytest.raises(ValueError, match="@3"):
        CandidatePromotionPolicyV2(mapping_schema_version="candidate-canonical-mapping@2").admit_new_production()


def _promotion_family(tmp_path, base, candidate_transform=None):
    """Build the real applicable promotion@2 family from one candidate chain.

    Covered §17 members that are reachable without a canonical mechanism@4:
    `candidate-promotion-policy@2`, `candidate-promotion-request@2`,
    `candidate-promotion-readiness@2`, and
    `promotion-decision-input-reference@2`. The compilation/projection/decision/
    result/verification members require a compiled `canonical-physical-mechanism@4`
    and a decision-application run, which this candidate fixture cannot produce
    (the canonical @4 promotion/compilation path is not wired into the fixture
    chain); they are therefore out of scope for this focused suite.
    """
    from test_candidate_decision_v2 import _decision_evaluation, _compare_and_select

    records = _decision_evaluation(
        tmp_path, base=base, candidate_transform=candidate_transform
    )
    candidate = records["candidate"]
    synthesis_request = records["synthesis_request"]
    comparison_request, comparison, selection = _compare_and_select(records)
    policy = CandidatePromotionPolicyV2()
    mapping = tuple(
        sorted(
            (
                CandidateCanonicalInstanceMappingV3(
                    candidate_instance_id=component.instance_id,
                    canonical_instance_id=f"mech-1:{component.instance_id}",
                    canonical_path=(
                        "/physical_mechanisms/mech-1/components/"
                        f"mech-1:{component.instance_id}"
                    ),
                    classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
                    source_identity=(
                        f"candidate:physical-instance:{component.instance_id}"
                    ),
                    source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
                    source_value="v1",
                )
                for component in candidate.realization.components
            ),
            key=lambda item: (item.candidate_instance_id, item.canonical_instance_id),
        )
    )
    request = CandidatePromotionRequestV2(
        project_id=candidate.source_binding.project_id,
        source_revision=synthesis_request.source_binding.source_revision,
        source_state_hash=synthesis_request.source_binding.source_state_hash,
        candidate_hash=candidate.candidate_hash,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=candidate.synthesis_policy_hash,
        m12_3_result_hash=records["admissibility"].result_hash,
        evaluation_hash=records["evaluation"].evaluation_hash,
        selection_hash=selection.selection_hash,
        comparison_used=True,
        comparison_request_hash=comparison_request.request_hash,
        comparison_result_hash=comparison.result_hash,
        comparison_entry_hashes=(
            (candidate.candidate_hash, records["evaluation"].evaluation_hash),
        ),
        promotion_policy_hash=policy.policy_hash,
        canonical_target_mechanism_id="mech-1",
    )
    compiler = CandidatePromotionCompilerV2(
        project_id=candidate.source_binding.project_id
    )
    readiness = compiler.validate_readiness_v2(
        request,
        synthesis_request=synthesis_request,
        candidate=candidate,
        m12_3_result_hash=records["admissibility"].result_hash,
        evaluation_hash=records["evaluation"].evaluation_hash,
        selection_hash=selection.selection_hash,
        evaluation_scope_hash=records["evaluation"].evaluation_scope_hash,
        promotion_policy=policy,
        mapping=mapping,
    )
    reference = PromotionDecisionInputReferenceV2(
        promotion_request_hash=request.request_hash,
        project_id=candidate.source_binding.project_id,
        base_revision=synthesis_request.source_binding.source_revision,
        base_state_hash=synthesis_request.source_binding.source_state_hash,
        candidate_hash=candidate.candidate_hash,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=candidate.synthesis_policy_hash,
        m12_3_result_hash=records["admissibility"].result_hash,
        evaluation_hash=records["evaluation"].evaluation_hash,
        selection_hash=selection.selection_hash,
        comparison_used=True,
        comparison_result_hash=comparison.result_hash,
        comparison_request_hash=comparison_request.request_hash,
        promotion_policy_hash=policy.policy_hash,
        canonical_target_mechanism_id="mech-1",
        mapping_identities=tuple(sorted(item.mapping_hash for item in mapping)),
    )
    return {
        "candidate": candidate,
        "evaluation": records["evaluation"],
        "request": request,
        "readiness": readiness,
        "reference": reference,
        "policy": policy,
    }


def test_case_89_90_92_93_promotion_suffixes(tmp_path):
    """Cases 89/92/93 SET_SEMANTIC reorder preserves the applicable promotion@2 family.

    Case 90's engineering-order distinction (support A/B swap) MUST change it.
    """
    from test_candidate_decision_v2 import (
        _candidate_with_m13_multi_joint_authority,
        _set_semantic_reordered_candidate,
        _realization_order_candidate,
        _candidate_level_order_candidate,
        _support_order_candidate,
    )

    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    baseline = _promotion_family(tmp_path, base)
    for transform in (
        _set_semantic_reordered_candidate,
        _realization_order_candidate,
        _candidate_level_order_candidate,
    ):
        reordered = _promotion_family(tmp_path, base, candidate_transform=transform)
        assert (
            reordered["candidate"].candidate_hash
            == baseline["candidate"].candidate_hash
        )
        assert reordered["request"].request_hash == baseline["request"].request_hash
        assert (
            reordered["readiness"].readiness_hash
            == baseline["readiness"].readiness_hash
        )
        assert (
            reordered["reference"].reference_hash
            == baseline["reference"].reference_hash
        )
        assert reordered["policy"].policy_hash == baseline["policy"].policy_hash

    changed = _promotion_family(
        tmp_path, base, candidate_transform=_support_order_candidate
    )
    assert (
        changed["candidate"].candidate_hash != baseline["candidate"].candidate_hash
    )
    assert changed["request"].request_hash != baseline["request"].request_hash
    assert changed["readiness"].readiness_hash != baseline["readiness"].readiness_hash
    assert changed["reference"].reference_hash != baseline["reference"].reference_hash
    assert changed["evaluation"].evaluation_hash != baseline["evaluation"].evaluation_hash


def test_case_93_non_empty_unresolved_is_rejected_by_existing_promotion_gate(tmp_path):
    """Case 93: the existing promotion gate rejects non-empty `unresolved_items`.

    The accepted Spec (§6C candidate ordering closure / §23 case 93) states that
    any non-empty `unresolved_items` blocks promotion admission in both
    orderings and that no promotion-result identity is claimed for the ineligible
    candidate. This exercises the real existing `CandidatePromotionCompiler`
    admission gate (the pre-existing `_verify_candidate` unresolved check) for
    both unresolved-item permutations and asserts no readiness identity is
    invented.

    Note: the new-family `CandidatePromotionCompilerV2.validate_readiness_v2`
    path does not yet enforce this rule (T-P7.2 remains STOPPED), so this test
    deliberately binds the legacy candidate gate that the Spec's "existing
    promotion admission remains" clause refers to.
    """
    from test_m12_candidate_foundation import _state
    from test_m12_candidate_evaluation import (
        _evaluation_candidate,
        _evaluation_service,
        _m12_result,
        _bound_m10_inputs,
    )
    from test_m12_promotion_compiler import _classifications, _compiler
    from mechcad_harness.candidates import (
        CandidateEvaluationPolicy,
        CandidatePromotionPolicy,
        CandidatePromotionRequest,
        CandidateSelection,
    )
    from mechcad_harness.candidates.models import (
        MechanicalDesignCandidate,
        UnresolvedCandidateItem,
        UnresolvedCandidateReason,
    )

    def _items():
        return (
            UnresolvedCandidateItem(
                subject_path="/components/z",
                required_information="z-information",
                reason=UnresolvedCandidateReason.PROPERTY_UNAVAILABLE,
                source_context="ctx-z",
            ),
            UnresolvedCandidateItem(
                subject_path="/components/a",
                required_information="a-information",
                reason=UnresolvedCandidateReason.REQUIRED_AUTHORITY_MISSING,
                source_context=None,
            ),
        )

    def _request_for(candidate, synthesis_request, synthesis_policy):
        m12 = _m12_result(candidate)
        cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(
            candidate
        )
        evaluation = _evaluation_service().evaluate(
            candidate,
            synthesis_request,
            synthesis_policy,
            m12,
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
        request = CandidatePromotionRequest(
            project_id=candidate.source_binding.project_id,
            source_revision=candidate.source_binding.source_revision,
            source_state_hash=candidate.source_binding.source_state_hash,
            candidate=candidate,
            synthesis_request=synthesis_request,
            synthesis_policy=synthesis_policy,
            m12_3_result=m12,
            evaluation=evaluation,
            selection=selection,
            promotion_policy=CandidatePromotionPolicy(),
            canonical_target_mechanism_id="PM-1",
        )
        return CandidatePromotionRequest.model_validate(
            request.model_copy(
                update={
                    "classifications": _classifications(request),
                    "request_hash": "pending",
                }
            ).model_dump(mode="json")
        )

    state = _state()
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    for index, items in enumerate((_items(), tuple(reversed(_items())))):
        ineligible = candidate.model_copy(
            update={"unresolved_items": items, "candidate_hash": "pending"}
        )
        ineligible = MechanicalDesignCandidate.model_validate(
            ineligible.model_dump(mode="json")
        )
        request = _request_for(ineligible, synthesis_request, synthesis_policy)
        _, compiler = _compiler(tmp_path / f"unresolved-perm-{index}", state)
        with pytest.raises(ValueError, match="unresolved items"):
            compiler.validate_readiness(request)


def test_case_93_v2_readiness_rejects_non_empty_unresolved_items(tmp_path):
    """Case 93 on the new family: @2 readiness gates reject unresolved items.

    The accepted Spec (§6C candidate ordering closure / §23 case 93) states that
    any non-empty `unresolved_items` blocks readiness in both orderings and that
    no promotion-result identity is claimed for the ineligible candidate. This
    exercises the real `CandidatePromotionCompilerV2.validate_readiness_v2` and
    `validate_multi_joint_readiness_v2` gates with a real candidate@2 carrying
    non-empty unresolved items, for both unresolved-item permutations, and
    asserts no readiness identity is produced.
    """
    from test_candidate_decision_v2 import (
        _candidate_with_m13_multi_joint_authority,
        _candidate_with_unresolved_items,
        _compare_and_select,
        _decision_evaluation,
        _unresolved_items,
    )

    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    records = _decision_evaluation(tmp_path, base=base)
    candidate = records["candidate"]
    synthesis_request = records["synthesis_request"]
    comparison_request, comparison, selection = _compare_and_select(records)
    policy = CandidatePromotionPolicyV2()
    mapping = tuple(
        sorted(
            (
                CandidateCanonicalInstanceMappingV3(
                    candidate_instance_id=component.instance_id,
                    canonical_instance_id=f"mech-1:{component.instance_id}",
                    canonical_path=(
                        "/physical_mechanisms/mech-1/components/"
                        f"mech-1:{component.instance_id}"
                    ),
                    classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
                    source_identity=(
                        f"candidate:physical-instance:{component.instance_id}"
                    ),
                    source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
                    source_value="v1",
                )
                for component in candidate.realization.components
            ),
            key=lambda item: (item.candidate_instance_id, item.canonical_instance_id),
        )
    )
    compiler = CandidatePromotionCompilerV2(
        project_id=candidate.source_binding.project_id
    )

    def _request_for(target):
        return CandidatePromotionRequestV2(
            project_id=target.source_binding.project_id,
            source_revision=synthesis_request.source_binding.source_revision,
            source_state_hash=synthesis_request.source_binding.source_state_hash,
            candidate_hash=target.candidate_hash,
            synthesis_request_hash=synthesis_request.request_hash,
            synthesis_policy_hash=target.synthesis_policy_hash,
            m12_3_result_hash=records["admissibility"].result_hash,
            evaluation_hash=records["evaluation"].evaluation_hash,
            selection_hash=selection.selection_hash,
            comparison_used=True,
            comparison_request_hash=comparison_request.request_hash,
            comparison_result_hash=comparison.result_hash,
            comparison_entry_hashes=(
                (target.candidate_hash, records["evaluation"].evaluation_hash),
            ),
            promotion_policy_hash=policy.policy_hash,
            canonical_target_mechanism_id="mech-1",
        )

    def _mj_request_for(target):
        return CandidateMultiJointPromotionRequestV2(
            project_id=target.source_binding.project_id,
            source_revision=synthesis_request.source_binding.source_revision,
            source_state_hash=synthesis_request.source_binding.source_state_hash,
            candidate_hash=target.candidate_hash,
            synthesis_request_hash=synthesis_request.request_hash,
            synthesis_policy_hash=target.synthesis_policy_hash,
            m12_3_result_hash=records["admissibility"].result_hash,
            multi_joint_request_hash=HASH_A,
            multi_joint_evaluation_hash=HASH_B,
            multi_joint_selection_hash=HASH_C,
            promotion_policy_hash=policy.policy_hash,
            canonical_target_mechanism_id="mech-1",
        )

    def _single_readiness(target):
        return compiler.validate_readiness_v2(
            _request_for(target),
            synthesis_request=synthesis_request,
            candidate=target,
            m12_3_result_hash=records["admissibility"].result_hash,
            evaluation_hash=records["evaluation"].evaluation_hash,
            selection_hash=selection.selection_hash,
            evaluation_scope_hash=records["evaluation"].evaluation_scope_hash,
            promotion_policy=policy,
            mapping=mapping,
        )

    # Positive control: the same typed request/readiness path admits the eligible
    # candidate, proving the fixture is causally valid and the rejection below is
    # specifically caused by `unresolved_items`.
    assert candidate.unresolved_items == ()
    eligible_readiness = _single_readiness(candidate)
    assert eligible_readiness.schema_version == "candidate-promotion-readiness@2"

    for index, items in enumerate((_unresolved_items(), tuple(reversed(_unresolved_items())))):
        ineligible = _candidate_with_unresolved_items(candidate, items)
        assert ineligible.unresolved_items
        assert ineligible.candidate_hash != candidate.candidate_hash
        assert ineligible.schema_version == "mechanical-design-candidate@2"

        with pytest.raises(ValueError, match="unresolved items"):
            _single_readiness(ineligible)

        with pytest.raises(ValueError, match="unresolved items"):
            compiler.validate_multi_joint_readiness_v2(
                _mj_request_for(ineligible),
                synthesis_request=synthesis_request,
                candidate=ineligible,
                scope_hash=HASH_A,
                configuration_set_hash=HASH_B,
                promotion_policy=policy,
                mapping=mapping,
            )


def test_multi_joint_compile_v2_emits_semantic_mechanism_and_exact_obligation(tmp_path):
    from mechcad_harness.artifacts import ArtifactStore
    from mechcad_harness.candidates.promotion import CandidatePromotionCompiler
    from mechcad_harness.candidates.promotion_models import (
        CandidateMultiJointPromotionRequestV2,
    )
    from mechcad_harness.revolute_drive import InputProvenanceKind, RevoluteDriveRealizationService
    from mechcad_harness.state import state_hash
    from test_candidate_m10_v2 import _policy_requirements
    from test_candidate_multi_joint_m10_provenance_v1 import _mj_chain

    chain = _mj_chain(tmp_path)
    candidate = chain["candidate"]
    synthesis_request = chain["synthesis_request"]
    synthesis_policy = chain["synthesis_policy"]
    state = chain["state"]
    m12_result = RevoluteDriveRealizationService().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _policy_requirements(),
        source_state=state,
    )
    policy = CandidatePromotionPolicyV2()
    classifications = tuple(
        sorted(
            (
                *(
                    PromotionClassification(
                        source_identity=f"candidate:physical-instance:{item.instance_id}",
                        source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
                        classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                    )
                    for item in candidate.realization.components
                ),
                *(
                    PromotionClassification(
                        source_identity=f"candidate:design-variable:{item.name}",
                        source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
                        classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
                        source_value=item.value,
                    )
                    for item in candidate.design_variables
                ),
            ),
            key=lambda item: item.source_identity,
        )
    )
    request = CandidateMultiJointPromotionRequestV2(
        project_id=candidate.source_binding.project_id,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        candidate_hash=candidate.candidate_hash,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        m12_3_result_hash=m12_result.result_hash,
        multi_joint_request_hash=chain["request"].request_hash,
        multi_joint_evaluation_hash=chain["evaluation"].evaluation_hash,
        multi_joint_selection_hash=chain["selection"].selection_hash,
        generated_placement_derivations=chain["request"].placement_derivations,
        semantic_placement_derivations_hash=(
            chain["request"].semantic_placement_derivations_hash
        ),
        promotion_policy_hash=policy.policy_hash,
        canonical_target_mechanism_id="PM-MJ-V2",
        classifications=classifications,
    )
    mechanism_compiler = CandidatePromotionCompiler(
        chain["manager"],
        ArtifactStore(
            tmp_path,
            project_id=request.project_id,
            run_id="promotion-v2-compile-test",
        ),
        cad_replay_verifier=lambda *args: None,
    )
    compiler = CandidatePromotionCompilerV2(
        project_id=request.project_id,
        mechanism_compiler=mechanism_compiler,
    )
    mapping = compiler.map_instances_v2(request, candidate)
    readiness = compiler.validate_multi_joint_readiness_v2(
        request,
        synthesis_request=synthesis_request,
        candidate=candidate,
        scope_hash=chain["request"].scope_hash,
        configuration_set_hash=chain["request"].configuration_set_hash,
        promotion_policy=policy,
        mapping=mapping,
    )

    compilation = compiler.compile_multi_joint_v2(
        state,
        request,
        readiness=readiness,
        candidate=candidate,
        synthesis_request=synthesis_request,
        multi_joint_request=chain["request"],
        multi_joint_evaluation=chain["evaluation"],
        multi_joint_selection=chain["selection"],
        promotion_policy=policy,
    )

    assert compilation.canonical_mechanism.schema_version == "canonical-physical-mechanism@4"
    assert len(compilation.canonical_mechanism.multi_joint_verification_obligations) == 1
    obligation = compilation.canonical_mechanism.multi_joint_verification_obligations[0]
    assert obligation.configuration_set == chain["request"].scope.configuration_set
    assert compilation.projection.canonical_mechanism_hash == (
        compilation.canonical_mechanism.mechanism_hash
    )
