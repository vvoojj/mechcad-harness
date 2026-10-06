from __future__ import annotations

import pytest

from mechcad_harness.candidates import CandidateCurrentnessService, CandidateIntegrityError
from mechcad_harness.candidates.cad_realization import (
    CandidateCadStageOutcomeV2,
    CandidateCadStageStatus,
    CandidateCadRealizationV2,
    CandidateCadRealizationRequestV3,
    candidate_realization_hash_v2,
)
from mechcad_harness.candidates.comparison import (
    CandidateComparisonDirection,
    CandidateComparisonPolicy,
)
import mechcad_harness.candidates.comparison as comparison_models
import mechcad_harness.candidates.evaluation as evaluation_models
import mechcad_harness.candidates.selection as selection_models
from mechcad_harness.candidates.evaluation import CandidateEvaluationOutcome
from mechcad_harness.candidates.evaluation import CandidateMetricKey
from mechcad_harness.candidates.models import (
    CandidateSynthesisRequest,
    MechanicalDesignCandidate,
)
from mechcad_harness.candidates.evaluation import (
    CandidateEvaluationCurrentnessService,
    CandidateEvaluationPolicy,
    CandidateEvaluationService,
)
from mechcad_harness.candidates.m10_evaluation import CandidateM10EvaluationService
from mechcad_harness.revolute_drive import RevoluteDriveRealizationService
from mechcad_harness.candidates.m10_result_validation import m10_result_hash
from mechcad_harness.candidates.models import (
    UnresolvedCandidateItem,
    UnresolvedCandidateReason,
    candidate_hash_v2,
    semantic_candidate_mechanism_hash,
)
from mechcad_harness.application import ProductionApplication

from task6_provenance_fixtures import make_proof_result
from test_candidate_m10_v2 import _new_m10_records, _policy_requirements
from test_candidate_multijoint_m10_v2 import (
    _candidate_cad_v2,
    _candidate_with_m13_multi_joint_authority,
)
from test_candidate_trusted_semantic_verification import _feasible_at1_evaluation


def _verify_candidate_cad_v2(candidate, request, realization):
    request = CandidateCadRealizationRequestV3.model_validate(
        request.model_dump(mode="json")
    )
    realization = CandidateCadRealizationV2.model_validate(
        realization.model_dump(mode="json")
    )
    assert request.candidate_hash == candidate.candidate_hash
    assert request.source_binding == candidate.source_binding
    assert request.semantic_source_binding_hash == candidate.semantic_source_binding_hash
    assert realization.request_hash == request.request_hash
    assert realization.realization_hash == candidate_realization_hash_v2(realization)


def _decision_evaluation(
    tmp_path,
    *,
    base=None,
    candidate_transform=None,
    proof_result_factory=make_proof_result,
):
    base = base or _candidate_with_m13_multi_joint_authority(tmp_path)
    state, manager, store, synthesis_request, synthesis_policy, candidate = base
    if candidate_transform is not None:
        candidate = candidate_transform(candidate)
    admissibility = RevoluteDriveRealizationService().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _policy_requirements(),
        source_state=state,
    )
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    binding, scope, m10_request = _new_m10_records(
        candidate, synthesis_request, cad_realization
    )

    def prove(**kwargs):
        return proof_result_factory(kwargs)

    m10_stage = CandidateM10EvaluationService(
        prove,
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("no home exact check is declared in this scope")
        ),
        scope=scope,
    ).evaluate(
        synthesis_request.source_binding.source_revision,
        synthesis_request.source_binding.source_state_hash,
        cad_realization,
        binding,
        m10_request,
        scope=scope,
        physical_realization=candidate.realization,
    )
    cad_stage = CandidateCadStageOutcomeV2(
        status=CandidateCadStageStatus.SUCCESS,
        realization=cad_realization,
    )
    evaluation = CandidateEvaluationService(
        currentness_verifier=CandidateCurrentnessService(manager),
        cad_replay_verifier=_verify_candidate_cad_v2,
    ).evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        admissibility,
        cad_stage,
        m10_stage,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    currentness = CandidateEvaluationCurrentnessService(
        manager,
        cad_replay_verifier=_verify_candidate_cad_v2,
    )
    return _decision_records(
        state, manager, store, synthesis_request, synthesis_policy, candidate,
        admissibility, cad_request, cad_realization, cad_stage, binding, scope,
        m10_request, m10_stage, evaluation, currentness,
    )


def _proof_result_with_clearance(clearance_mm):
    def prove(kwargs):
        result = make_proof_result(kwargs)
        certificates = []
        for certificate in result.certified_leaf_certificates:
            pair_certificates = tuple(
                item.model_copy(update={"certified_lower_clearance_mm": clearance_mm})
                for item in certificate.pair_certificates
            )
            certificates.append(
                certificate.model_copy(
                    update={
                        "pair_certificates": pair_certificates,
                        "minimum_certified_lower_clearance_mm": clearance_mm,
                    }
                )
            )
        result = result.model_copy(
            update={"certified_leaf_certificates": tuple(certificates), "result_hash": "pending"}
        )
        return result.model_copy(
            update={"result_hash": m10_result_hash(result)}
        )

    return prove


def _decision_records(
    state, manager, store, synthesis_request, synthesis_policy, candidate,
    admissibility, cad_request, cad_realization, cad_stage, binding, scope,
    m10_request, m10_stage, evaluation, currentness,
):
    return {
        "state": state,
        "manager": manager,
        "store": store,
        "synthesis_request": synthesis_request,
        "synthesis_policy": synthesis_policy,
        "candidate": candidate,
        "admissibility": admissibility,
        "cad_request": cad_request,
        "cad_realization": cad_realization,
        "cad_stage": cad_stage,
        "binding": binding,
        "scope": scope,
        "m10_request": m10_request,
        "m10_stage": m10_stage,
        "evaluation": evaluation,
        "currentness": currentness,
    }


def _comparison_request(records, policy):
    records = tuple(records) if isinstance(records, (tuple, list)) else (records,)
    candidate = records[0]["candidate"]
    evaluation = records[0]["evaluation"]
    return comparison_models.CandidateComparisonRequestV2(
        project_id=candidate.source_binding.project_id,
        source_binding_hash=candidate.semantic_source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        policy_hash=policy.policy_hash,
        candidate_evaluation_pairs=tuple(
            (item["candidate"].candidate_hash, item["evaluation"].evaluation_hash)
            for item in records
        ),
    )


def _compare_and_select(records, *, policy=None, application=None, selected_index=0):
    policy = policy or CandidateComparisonPolicy()
    records = tuple(records) if isinstance(records, (tuple, list)) else (records,)
    entries = tuple((item["candidate"], item["evaluation"]) for item in records)
    requests = {
        item["candidate"].candidate_hash: item["synthesis_request"]
        for item in records
    }
    request = _comparison_request(records, policy)
    selected = records[selected_index]
    candidate = selected["candidate"]
    evaluation = selected["evaluation"]
    synthesis_request = selected["synthesis_request"]
    currentness = records[0]["currentness"]
    comparison_service = comparison_models.CandidateComparisonService(
        policy,
        project_id=candidate.source_binding.project_id,
        currentness_verifier=currentness,
    )
    selection_service = selection_models.CandidateSelectionService(
        project_id=candidate.source_binding.project_id,
        currentness_verifier=selected["currentness"],
    )
    if application is None:
        comparison = comparison_service.compare(
            request, entries, synthesis_requests_by_candidate_hash=requests
        )
        selection = selection_service.select(
            candidate,
            evaluation,
            "p7.1-test-selector@1",
            "explicit typed request@2 context",
            comparison=comparison,
            comparison_entries=entries,
            synthesis_request=synthesis_request,
            synthesis_requests_by_candidate_hash=requests,
        )
    else:
        application.project_id = candidate.source_binding.project_id
        application.candidate_comparison_service = comparison_service
        application.candidate_selection_service = selection_service
        comparison = application.compare_candidates(
            request, entries, synthesis_requests_by_candidate_hash=requests
        )
        selection = application.select_candidate(
            candidate,
            evaluation,
            "p7.1-test-selector@1",
            "explicit typed request@2 context",
            comparison=comparison,
            comparison_entries=entries,
            synthesis_request=synthesis_request,
            synthesis_requests_by_candidate_hash=requests,
        )
    return request, comparison, selection


def _set_semantic_reordered_candidate(candidate):
    realization = candidate.realization
    components = [item.model_dump(mode="json") for item in realization.components]
    for item in components:
        item["interfaces"] = list(reversed(item["interfaces"]))
    connections = [item.model_dump(mode="json") for item in realization.connections]
    for item in connections:
        item["meanings"] = list(reversed(item["meanings"]))
    joints = [item.model_dump(mode="json") for item in realization.joint_bindings]
    for item in joints:
        for field in (
            "realization_component_ids",
            "actuator_path_connection_ids",
            "transmission_path_connection_ids",
            "mount_or_support_instance_ids",
        ):
            item[field] = list(reversed(item[field]))
    reordered_realization = type(realization).model_validate(
        realization.model_dump(mode="json")
        | {
            "components": list(reversed(components)),
            "connections": list(reversed(connections)),
            "joint_bindings": list(reversed(joints)),
            "realization_hash": "pending",
        }
    )
    return type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "component_specifications": list(
                reversed(candidate.component_specifications)
            ),
            "realization": reordered_realization.model_dump(mode="json"),
            "design_variables": list(reversed(candidate.design_variables)),
            "unresolved_items": list(reversed(candidate.unresolved_items)),
            "candidate_hash": "pending",
        }
    )


def _support_order_candidate(candidate):
    payload = candidate.realization.model_dump(mode="json")
    joint = payload["joint_bindings"][0]
    joint["support_instance_ids"] = list(reversed(joint["support_instance_ids"]))
    payload["realization_hash"] = "pending"
    realization = type(candidate.realization).model_validate(payload)
    return type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "realization": realization.model_dump(mode="json"),
            "candidate_hash": "pending",
        }
    )


def _realization_order_candidate(candidate):
    realization = candidate.realization
    components = [item.model_dump(mode="json") for item in realization.components]
    for item in components:
        item["interfaces"] = list(reversed(item["interfaces"]))
    connections = [item.model_dump(mode="json") for item in realization.connections]
    for item in connections:
        item["meanings"] = list(reversed(item["meanings"]))
    joints = [item.model_dump(mode="json") for item in realization.joint_bindings]
    for item in joints:
        for field in (
            "realization_component_ids",
            "actuator_path_connection_ids",
            "transmission_path_connection_ids",
            "mount_or_support_instance_ids",
        ):
            item[field] = list(reversed(item[field]))
    realization = type(realization).model_validate(
        realization.model_dump(mode="json")
        | {
            "components": list(reversed(components)),
            "connections": list(reversed(connections)),
            "joint_bindings": list(reversed(joints)),
            "realization_hash": "pending",
        }
    )
    return type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {"realization": realization.model_dump(mode="json"), "candidate_hash": "pending"}
    )


def _candidate_level_order_candidate(candidate):
    return type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "component_specifications": list(reversed(candidate.component_specifications)),
            "design_variables": list(reversed(candidate.design_variables)),
            "unresolved_items": list(reversed(candidate.unresolved_items)),
            "candidate_hash": "pending",
        }
    )


def _different_generator(candidate):
    return type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "generator_identity": "p7.1-comparator-second-generator@1",
            "candidate_hash": "pending",
        }
    )


def _connection_direction_reversal_candidate(candidate, connection_id="motor-mount"):
    """Reverse one connection's real from/to endpoint direction (Case 90)."""
    payload = candidate.realization.model_dump(mode="json")
    found = False
    for connection in payload["connections"]:
        if connection["connection_id"] != connection_id:
            continue
        found = True
        connection["from_instance_id"], connection["to_instance_id"] = (
            connection["to_instance_id"],
            connection["from_instance_id"],
        )
        connection["from_interface_id"], connection["to_interface_id"] = (
            connection["to_interface_id"],
            connection["from_interface_id"],
        )
    if not found:
        raise AssertionError(f"connection {connection_id!r} is not in the realization")
    payload["realization_hash"] = "pending"
    realization = type(candidate.realization).model_validate(payload)
    return type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "realization": realization.model_dump(mode="json"),
            "candidate_hash": "pending",
        }
    )


def _joint_parent_child_reversal_candidate(candidate):
    """Reverse a physical revolute joint's real parent/child endpoint direction."""
    payload = candidate.realization.model_dump(mode="json")
    if not payload["physical_revolute_joint_bindings"]:
        raise AssertionError("realization has no physical revolute joint binding")
    joint = payload["physical_revolute_joint_bindings"][0]
    for parent, child in (
        ("parent_physical_body_id", "child_physical_body_id"),
        ("parent_physical_instance_id", "child_physical_instance_id"),
        ("parent_interface_id", "child_interface_id"),
    ):
        joint[parent], joint[child] = joint[child], joint[parent]
    joint["axis_owner_endpoint"] = (
        "child" if joint["axis_owner_endpoint"] == "parent" else "parent"
    )
    joint["binding_hash"] = "pending"
    payload["realization_hash"] = "pending"
    realization = type(candidate.realization).model_validate(payload)
    return type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "realization": realization.model_dump(mode="json"),
            "candidate_hash": "pending",
        }
    )


def _unresolved_items():
    """Two unresolved items whose canonical sort keys are unambiguous."""
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


def _candidate_with_unresolved_items(candidate, items):
    return type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {"unresolved_items": list(items), "candidate_hash": "pending"}
    )


def test_decision_v2_records_are_the_accepted_versioned_siblings():
    evaluation_v2 = getattr(evaluation_models, "CandidateEvaluationV2", None)
    request_v2 = getattr(comparison_models, "CandidateComparisonRequestV2", None)
    result_v2 = getattr(comparison_models, "CandidateComparisonResultV2", None)
    selection_v2 = getattr(selection_models, "CandidateSelectionV2", None)
    assert evaluation_v2 is not None, "candidate-evaluation@2 is not implemented"
    assert request_v2 is not None, "candidate-comparison-request@2 is not implemented"
    assert result_v2 is not None, "candidate-comparison-result@2 is not implemented"
    assert selection_v2 is not None, "candidate-selection@2 is not implemented"

    assert set(evaluation_v2.model_fields) == set(
        evaluation_models.CandidateEvaluation.model_fields
    )
    assert evaluation_models.CandidateEvaluation.model_fields[
        "schema_version"
    ].default == "candidate-evaluation@1"
    assert set(request_v2.model_fields) == set(
        comparison_models.CandidateComparisonRequest.model_fields
    )
    assert set(result_v2.model_fields) == set(
        comparison_models.CandidateComparisonResult.model_fields
    )
    assert set(selection_v2.model_fields) == set(
        selection_models.CandidateSelection.model_fields
    )
    assert selection_models.CandidateSelection.model_fields[
        "schema_version"
    ].default == "candidate-selection@1"


def test_candidate_evaluation_v2_carries_semantic_p5_references_and_typed_request(tmp_path):
    records = _decision_evaluation(tmp_path)
    candidate = records["candidate"]
    request = records["synthesis_request"]
    evaluation = records["evaluation"]

    assert evaluation.schema_version == "candidate-evaluation@2"
    assert evaluation.candidate_hash == candidate.candidate_hash
    assert evaluation.source_binding_hash == candidate.semantic_source_binding_hash
    assert evaluation.synthesis_request_hash == request.request_hash
    assert evaluation.m12_3_result.schema_version == "revolute-drive-admissibility@2"
    assert evaluation.m12_3_result_hash == records["admissibility"].result_hash
    assert evaluation.cad_stage_outcome.schema_version == "candidate-cad-stage-outcome@2"
    assert evaluation.m10_stage_outcome.schema_version == "candidate-m10-stage-outcome@2"
    assert evaluation.cad_stage_outcome_hash == records["cad_stage"].outcome_hash
    assert evaluation.m10_stage_outcome_hash == records["m10_stage"].outcome_hash
    assert evaluation.evaluation_scope_hash == records["m10_stage"].scope_hash
    assert evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
    assert evaluation.metrics[0].source_result_hashes == tuple(
        proof.proof_hash for proof in records["m10_stage"].pair_proofs
    )
    evaluator_only = type(evaluation).model_validate(
        evaluation.model_dump(mode="json")
        | {
            "evaluator_identity": "different-runtime-adapter",
            "evaluator_version": "different-runtime-version",
            "evaluation_hash": "pending",
        }
    )
    assert evaluator_only.evaluation_hash == evaluation.evaluation_hash

    assert records["currentness"].verify_current(
        evaluation, candidate, synthesis_request=request
    ) is True
    with pytest.raises(CandidateIntegrityError, match="request@2"):
        records["currentness"].verify_current(evaluation, candidate)
    with pytest.raises((CandidateIntegrityError, AttributeError)):
        records["currentness"].verify_current(
            evaluation,
            candidate,
            synthesis_request=candidate.synthesis_request_hash,
        )

    legacy_request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@1",
        source_binding=request.source_binding,
        requested_joint_ids=request.requested_joint_ids,
        required_joint_ids=request.required_joint_ids,
    )
    with pytest.raises(CandidateIntegrityError, match="request@2"):
        records["currentness"].verify_current(
            evaluation, candidate, synthesis_request=legacy_request
        )

    mismatched_request = CandidateSynthesisRequest.model_validate(
        request.model_dump(mode="json")
        | {
            "semantic_source_binding_hash": "sha256:" + "f" * 64,
            "request_hash": "pending",
        }
    )
    with pytest.raises(CandidateIntegrityError, match="semantic|request"):
        records["currentness"].verify_current(
            evaluation, candidate, synthesis_request=mismatched_request
        )

    mismatched_scope_request = CandidateSynthesisRequest.model_validate(
        request.model_dump(mode="json")
        | {
            "requested_evaluation_categories": ("another-scope-category",),
            "request_hash": "pending",
        }
    )
    with pytest.raises(CandidateIntegrityError, match="request"):
        records["currentness"].verify_current(
            evaluation, candidate, synthesis_request=mismatched_scope_request
        )


def test_evaluation_v2_rejects_request_v1_for_candidate_v2(tmp_path):
    records = _decision_evaluation(tmp_path)
    request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@1",
        source_binding=records["synthesis_request"].source_binding,
        requested_joint_ids=records["synthesis_request"].requested_joint_ids,
        required_joint_ids=records["synthesis_request"].required_joint_ids,
    )

    with pytest.raises(CandidateIntegrityError, match="candidate@2.*request@2"):
        CandidateEvaluationService(
            currentness_verifier=records["currentness"],
            cad_replay_verifier=_verify_candidate_cad_v2,
        ).evaluate(
            records["candidate"],
            request,
            records["synthesis_policy"],
            records["admissibility"],
            records["cad_stage"],
            records["m10_stage"],
            CandidateEvaluationPolicy(),
            cad_request=records["cad_request"],
            m10_request=records["m10_request"],
            m10_scope=records["scope"],
            m10_binding=records["binding"],
        )


def test_decision_services_reject_mixed_candidate_evaluation_and_comparison_families(
    tmp_path,
):
    records = _decision_evaluation(tmp_path)
    candidate_v2 = records["candidate"]
    evaluation_v2 = records["evaluation"]
    currentness = records["currentness"]
    selection_service = selection_models.CandidateSelectionService(
        project_id=candidate_v2.source_binding.project_id,
        currentness_verifier=currentness,
    )
    candidate_v1, evaluation_v1 = _feasible_at1_evaluation(None)

    with pytest.raises(ValueError, match="evaluation@2|candidate@2"):
        selection_service.select(
            candidate_v2,
            evaluation_v1,
            "mixed-family-selector@1",
            "candidate@2 with evaluation@1",
            synthesis_request=records["synthesis_request"],
        )
    with pytest.raises(ValueError, match="candidate-selection@2|candidate@2"):
        selection_service.select(
            candidate_v1,
            evaluation_v2,
            "mixed-family-selector@1",
            "candidate@1 with evaluation@2",
            synthesis_request=records["synthesis_request"],
        )

    policy = CandidateComparisonPolicy()
    legacy_request = comparison_models.CandidateComparisonRequest(
        project_id=candidate_v2.source_binding.project_id,
        source_binding_hash=candidate_v2.semantic_source_binding_hash,
        evaluation_scope_hash=evaluation_v2.evaluation_scope_hash,
        policy_hash=policy.policy_hash,
        candidate_evaluation_pairs=((candidate_v2.candidate_hash, evaluation_v2.evaluation_hash),),
    )
    comparison_service = comparison_models.CandidateComparisonService(
        policy,
        project_id=candidate_v2.source_binding.project_id,
        currentness_verifier=currentness,
    )
    with pytest.raises(ValueError, match="candidate@2 comparison requires request@2"):
        comparison_service.compare(
            legacy_request,
            ((candidate_v2, evaluation_v2),),
        )

    request_v2 = _comparison_request((records,), policy)
    result_v2 = comparison_models.CandidateComparisonService(
        policy,
        project_id=candidate_v2.source_binding.project_id,
        currentness_verifier=currentness,
    ).compare(
        request_v2,
        ((candidate_v2, evaluation_v2),),
        synthesis_requests_by_candidate_hash={
            candidate_v2.candidate_hash: records["synthesis_request"]
        },
    )
    with pytest.raises(ValueError, match="CandidateComparisonResult|candidate-selection@2"):
        selection_service.select(
            candidate_v1,
            evaluation_v1,
            "mixed-family-selector@1",
            "legacy selection with comparison@2",
            comparison=result_v2,
            comparison_entries=((candidate_v1, evaluation_v1),),
        )


def test_comparison_v2_requires_exact_request_map_and_excludes_comparator_version(
    tmp_path,
):
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    first = _decision_evaluation(
        tmp_path, base=base, proof_result_factory=_proof_result_with_clearance(3.0)
    )
    second = _decision_evaluation(
        tmp_path,
        base=base,
        candidate_transform=_different_generator,
        proof_result_factory=_proof_result_with_clearance(7.0),
    )
    records = (first, second)
    policy = CandidateComparisonPolicy()
    request = _comparison_request(records, policy)
    entries = tuple((item["candidate"], item["evaluation"]) for item in records)
    requests = {item["candidate"].candidate_hash: item["synthesis_request"] for item in records}
    service = comparison_models.CandidateComparisonService(
        policy,
        project_id=first["candidate"].source_binding.project_id,
        currentness_verifier=first["currentness"],
    )

    with pytest.raises(ValueError, match="request@2 mapping"):
        service.compare(request, entries)
    with pytest.raises((ValueError, AttributeError)):
        service.compare(
            request,
            entries,
            synthesis_requests_by_candidate_hash={
                candidate.candidate_hash: candidate.synthesis_request_hash
                for candidate, _ in entries
            },
        )
    with pytest.raises(ValueError, match="request@2 mapping"):
        service.compare(
            request,
            entries,
            synthesis_requests_by_candidate_hash={
                first["candidate"].candidate_hash: first["synthesis_request"]
            },
        )
    with pytest.raises(ValueError, match="request@2 mapping"):
        service.compare(
            request,
            entries,
            synthesis_requests_by_candidate_hash=(
                requests | {first["candidate"].candidate_hash: CandidateSynthesisRequest(
                    schema_version="candidate-synthesis-request@1",
                    source_binding=first["synthesis_request"].source_binding,
                )}
            ),
        )
    with pytest.raises(ValueError, match="exactly|mapping"):
        service.compare(
            request,
            entries,
            synthesis_requests_by_candidate_hash=(
                requests | {"sha256:" + "f" * 64: first["synthesis_request"]}
            ),
        )
    wrong_request = CandidateSynthesisRequest.model_validate(
        first["synthesis_request"].model_dump(mode="json")
        | {
            "semantic_source_binding_hash": "sha256:" + "e" * 64,
            "request_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="currentness|semantic|request"):
        service.compare(
            request,
            entries,
            synthesis_requests_by_candidate_hash=(
                requests | {first["candidate"].candidate_hash: wrong_request}
            ),
        )
    result = service.compare(
        request, entries, synthesis_requests_by_candidate_hash=requests
    )
    assert result.schema_version == "candidate-comparison-result@2"
    assert result.ranked_candidate_hashes == (
        second["candidate"].candidate_hash,
        first["candidate"].candidate_hash,
    )
    assert result.ties == ()

    changed_policy = CandidateComparisonPolicy(
        comparator_version="candidate-comparison-execution-change@1"
    )
    changed_request = _comparison_request(records, changed_policy)
    changed_service = comparison_models.CandidateComparisonService(
        changed_policy,
        project_id=first["candidate"].source_binding.project_id,
        currentness_verifier=first["currentness"],
    )
    changed_result = changed_service.compare(
        changed_request, entries, synthesis_requests_by_candidate_hash=requests
    )
    assert changed_request.request_hash != request.request_hash
    assert changed_result.result_hash == result.result_hash


def test_comparison_v2_preserves_equal_metric_tie_semantics(tmp_path):
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    first = _decision_evaluation(
        tmp_path, base=base, proof_result_factory=_proof_result_with_clearance(5.0)
    )
    second = _decision_evaluation(
        tmp_path,
        base=base,
        candidate_transform=_different_generator,
        proof_result_factory=_proof_result_with_clearance(5.0),
    )
    policy = CandidateComparisonPolicy()
    request = _comparison_request((first, second), policy)
    result = comparison_models.CandidateComparisonService(
        policy,
        project_id=first["candidate"].source_binding.project_id,
        currentness_verifier=first["currentness"],
    ).compare(
        request,
        tuple((item["candidate"], item["evaluation"]) for item in (first, second)),
        synthesis_requests_by_candidate_hash={
            item["candidate"].candidate_hash: item["synthesis_request"]
            for item in (first, second)
        },
    )
    assert result.ranked_candidate_hashes == tuple(
        item["candidate"].candidate_hash for item in (first, second)
    )
    assert result.ties == (result.ranked_candidate_hashes,)


def test_application_compare_and_select_routes_exact_request_context(tmp_path):
    from test_candidate_comparison_selection_provenance_v2 import (
        _published_v2_parents,
    )

    records, provenance, _, _ = _published_v2_parents(tmp_path)
    application = object.__new__(ProductionApplication)
    application.state_manager = records["manager"]
    application.candidate_provenance_artifact_service = provenance

    request, comparison, selection = _compare_and_select(
        records, application=application
    )

    assert request.schema_version == "candidate-comparison-request@2"
    assert comparison.schema_version == "candidate-comparison-result@2"
    assert selection.schema_version == "candidate-selection@2"
    assert selection.source_binding_hash == records["candidate"].semantic_source_binding_hash
    assert selection.evaluation_hash == records["evaluation"].evaluation_hash

    with pytest.raises(ValueError, match="request@2"):
        application.candidate_selection_service.select(
            records["candidate"],
            records["evaluation"],
            "p7.1-test-selector@1",
            "no typed request",
        )


@pytest.mark.parametrize(
    ("case", "candidate_transform"),
    (
        ("89", _set_semantic_reordered_candidate),
        ("92", _realization_order_candidate),
        ("93", _candidate_level_order_candidate),
    ),
)
def test_case_89_92_93_evaluation_comparison_selection_suffixes_are_invariant(
    tmp_path, case, candidate_transform
):
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    baseline = _decision_evaluation(tmp_path, base=base)
    reordered = _decision_evaluation(
        tmp_path, base=base, candidate_transform=candidate_transform
    )

    assert reordered["candidate"].candidate_hash == baseline["candidate"].candidate_hash
    assert reordered["evaluation"].evaluation_hash == baseline["evaluation"].evaluation_hash
    _, baseline_comparison, baseline_selection = _compare_and_select(baseline)
    _, reordered_comparison, reordered_selection = _compare_and_select(reordered)
    assert reordered_comparison.result_hash == baseline_comparison.result_hash
    assert reordered_selection.selection_hash == baseline_selection.selection_hash


def test_case_90_support_order_difference_propagates_to_evaluation_comparison_selection(
    tmp_path,
):
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    baseline = _decision_evaluation(tmp_path, base=base)
    support_changed = _decision_evaluation(
        tmp_path, base=base, candidate_transform=_support_order_candidate
    )

    assert support_changed["candidate"].candidate_hash != baseline["candidate"].candidate_hash
    assert semantic_candidate_mechanism_hash(
        support_changed["candidate"].realization
    ) != semantic_candidate_mechanism_hash(baseline["candidate"].realization)
    assert support_changed["evaluation"].evaluation_hash != baseline["evaluation"].evaluation_hash
    _, baseline_comparison, baseline_selection = _compare_and_select(baseline)
    _, changed_comparison, changed_selection = _compare_and_select(support_changed)
    assert changed_comparison.result_hash != baseline_comparison.result_hash
    assert changed_selection.selection_hash != baseline_selection.selection_hash


def test_raw_step_rotation_preserves_decision_v2_hashes(tmp_path):
    state_a, manager, store, synthesis_a, policy_a, candidate_a = (
        _candidate_with_m13_multi_joint_authority(tmp_path, variant="A")
    )
    state_b, _, _, synthesis_b, policy_b, candidate_b = (
        _candidate_with_m13_multi_joint_authority(
            tmp_path, variant="B", manager=manager, store=store
        )
    )
    first = _decision_evaluation(
        tmp_path,
        base=(state_a, manager, store, synthesis_a, policy_a, candidate_a),
    )
    second = _decision_evaluation(
        tmp_path,
        base=(state_b, manager, store, synthesis_b, policy_b, candidate_b),
    )

    assert candidate_a.realization.realization_hash != candidate_b.realization.realization_hash
    assert first["evaluation"].evaluation_hash == second["evaluation"].evaluation_hash
    _, first_comparison, first_selection = _compare_and_select(first)
    _, second_comparison, second_selection = _compare_and_select(second)
    assert first_comparison.result_hash == second_comparison.result_hash
    assert first_selection.selection_hash == second_selection.selection_hash


def test_selection_v2_hash_includes_selector_identity_and_rationale(tmp_path):
    records = _decision_evaluation(tmp_path)
    service = selection_models.CandidateSelectionService(
        project_id=records["candidate"].source_binding.project_id,
        currentness_verifier=records["currentness"],
    )

    baseline = service.select(
        records["candidate"],
        records["evaluation"],
        "selector-a@1",
        "explicit rationale A",
        synthesis_request=records["synthesis_request"],
    )
    selector_changed = service.select(
        records["candidate"],
        records["evaluation"],
        "selector-b@1",
        "explicit rationale A",
        synthesis_request=records["synthesis_request"],
    )
    rationale_changed = service.select(
        records["candidate"],
        records["evaluation"],
        "selector-a@1",
        "explicit rationale B",
        synthesis_request=records["synthesis_request"],
    )

    assert selector_changed.selection_hash != baseline.selection_hash
    assert rationale_changed.selection_hash != baseline.selection_hash


def test_case_93_unresolved_items_multiset_and_field_sensitivity(tmp_path):
    """Case 93: unresolved-items multiset ordering/multiplicity and field semantics."""
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    candidate = _decision_evaluation(tmp_path, base=base)["candidate"]
    items = _unresolved_items()
    permuted = _candidate_with_unresolved_items(candidate, tuple(reversed(items)))
    baseline = _candidate_with_unresolved_items(candidate, items)

    # Reordering the unresolved-items tuple is a SET/multiset permutation.
    assert baseline.candidate_hash == permuted.candidate_hash
    # Multiplicity is preserved: dropping one item is a real change.
    assert (
        _candidate_with_unresolved_items(candidate, items[:-1]).candidate_hash
        != baseline.candidate_hash
    )
    # Each of the four semantic fields independently changes the hash.
    for field, value in (
        ("subject_path", "/components/zzz"),
        ("required_information", "changed-information"),
        ("reason", UnresolvedCandidateReason.GEOMETRY_UNAVAILABLE),
        ("source_context", "changed-context"),
    ):
        changed = (items[0].model_copy(update={field: value}), items[1])
        assert (
            _candidate_with_unresolved_items(candidate, changed).candidate_hash
            != baseline.candidate_hash
        )


def test_case_93_combined_permutation_preserves_candidate_hash(tmp_path):
    """Case 93: the combined non-realization permutation preserves candidate_hash@2."""
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    candidate = _decision_evaluation(tmp_path, base=base)["candidate"]
    with_items = _candidate_with_unresolved_items(candidate, _unresolved_items())
    combined = _candidate_level_order_candidate(with_items)
    assert combined.candidate_hash == with_items.candidate_hash


def test_case_93_component_spec_and_variable_changes_are_sensitive(tmp_path):
    """Case 93: specification membership and variable name/value changes MUST change."""
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    candidate = _decision_evaluation(tmp_path, base=base)["candidate"]
    expected = candidate_hash_v2(candidate)

    changed_specification = candidate.component_specifications[0].model_copy(
        update={"specification_hash": "sha256:" + "e" * 64}
    )
    membership_changed = candidate.model_copy(
        update={
            "component_specifications": (
                changed_specification,
                *candidate.component_specifications[1:],
            ),
            "candidate_hash": "pending",
        }
    )
    assert candidate_hash_v2(membership_changed) != expected

    variable = candidate.design_variables[0]
    name_changed = candidate.model_copy(
        update={
            "design_variables": (
                variable.model_copy(update={"name": variable.name + "-changed"}),
                *candidate.design_variables[1:],
            ),
            "candidate_hash": "pending",
        }
    )
    value_changed = candidate.model_copy(
        update={
            "design_variables": (
                variable.model_copy(update={"value": "changed-value"}),
                *candidate.design_variables[1:],
            ),
            "candidate_hash": "pending",
        }
    )
    assert candidate_hash_v2(name_changed) != expected
    assert candidate_hash_v2(value_changed) != expected


def test_case_90_connection_direction_reversal_propagates(tmp_path):
    """Case 90: reversing a connection's from/to endpoints is an engineering change."""
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    baseline = _decision_evaluation(tmp_path, base=base)
    reversed_records = _decision_evaluation(
        tmp_path, base=base, candidate_transform=_connection_direction_reversal_candidate
    )

    assert (
        reversed_records["candidate"].candidate_hash
        != baseline["candidate"].candidate_hash
    )
    assert semantic_candidate_mechanism_hash(
        reversed_records["candidate"].realization
    ) != semantic_candidate_mechanism_hash(baseline["candidate"].realization)
    assert (
        reversed_records["evaluation"].evaluation_hash
        != baseline["evaluation"].evaluation_hash
    )
    _, baseline_comparison, baseline_selection = _compare_and_select(baseline)
    _, reversed_comparison, reversed_selection = _compare_and_select(reversed_records)
    assert reversed_comparison.result_hash != baseline_comparison.result_hash
    assert reversed_selection.selection_hash != baseline_selection.selection_hash


def test_case_90_joint_parent_child_reversal_propagates(tmp_path):
    """Case 90: reversing a revolute joint's parent/child direction is engineering-significant."""
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    baseline = _decision_evaluation(tmp_path, base=base)
    reversed_records = _decision_evaluation(
        tmp_path, base=base, candidate_transform=_joint_parent_child_reversal_candidate
    )

    assert (
        reversed_records["candidate"].candidate_hash
        != baseline["candidate"].candidate_hash
    )
    assert semantic_candidate_mechanism_hash(
        reversed_records["candidate"].realization
    ) != semantic_candidate_mechanism_hash(baseline["candidate"].realization)
    assert (
        reversed_records["evaluation"].evaluation_hash
        != baseline["evaluation"].evaluation_hash
    )
    _, baseline_comparison, baseline_selection = _compare_and_select(baseline)
    _, reversed_comparison, reversed_selection = _compare_and_select(reversed_records)
    assert reversed_comparison.result_hash != baseline_comparison.result_hash
    assert reversed_selection.selection_hash != baseline_selection.selection_hash
