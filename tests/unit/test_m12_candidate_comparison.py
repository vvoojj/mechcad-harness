from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.candidates import (
    CandidateComparisonDirection,
    CandidateComparisonPolicy,
    CandidateComparisonRequest,
    CandidateComparisonResult,
    CandidateComparisonService,
    CandidateEvaluation,
    CandidateEvaluationCurrentnessService,
    CandidateEvaluationPolicy,
    CandidateMetricKey,
)
from mechcad_harness.candidates.m10_evaluation import CandidateM10StageOutcome
from mechcad_harness.candidates.evaluation import _stage_outcome_hash
from test_m12_candidate_evaluation import (
    _bound_m10_inputs,
    _evaluation_candidate,
    _evaluation_service,
    _m12_result,
)
from test_m12_candidate_foundation import _state
from mechcad_harness.candidates.models import CandidateSynthesisPolicy, CandidateSynthesisRequest
from mechcad_harness.state import StateManager


def _evaluated_candidate(suffix: str = "", state=None):
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    if suffix:
        candidate = type(candidate).model_validate(
            candidate.model_dump(mode="json")
            | {"generator_identity": f"fixture-generator-{suffix}", "candidate_hash": "pending"}
        )
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    return candidate, evaluation, scope


def _policy() -> CandidateComparisonPolicy:
    return CandidateComparisonPolicy(
        metric_keys=(CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM,),
        directions=(CandidateComparisonDirection.MAXIMIZE,),
        expected_units=("mm",),
    )


def _request(policy, entries, *, project_id="PRJ-M12", source_binding_hash=None, scope_hash=None):
    first = entries[0]
    if len(first) == 3:
        candidate, evaluation, scope = first
    else:
        candidate, evaluation = first
        scope = None
    return CandidateComparisonRequest(
        project_id=project_id,
        source_binding_hash=source_binding_hash or evaluation.source_binding_hash,
        evaluation_scope_hash=scope_hash or (scope.scope_hash if scope is not None else evaluation.evaluation_scope_hash),
        policy_hash=policy.policy_hash,
        candidate_evaluation_pairs=tuple(
            (item[0].candidate_hash, item[1].evaluation_hash) for item in entries
        ),
    )


def _pair(entry):
    return entry[0], entry[1]


class _CurrentnessVerifier:
    def verify_current(self, evaluation, candidate):
        return True


class _StaleCurrentnessVerifier:
    def verify_current(self, evaluation, candidate):
        raise ValueError("candidate evaluation is stale")


class _StateBackedCurrentnessVerifier:
    def __init__(self, state_manager):
        self._service = CandidateEvaluationCurrentnessService(
            state_manager, cad_replay_verifier=lambda *args: None
        )

    def verify_current(self, evaluation, candidate):
        return self._service.verify_current(
            evaluation,
            candidate,
            CandidateSynthesisRequest(source_binding=candidate.source_binding),
            CandidateSynthesisPolicy(
                entries=(
                    ("allow-direct-drive", "direct_drive", "hard_admissibility"),
                    ("preferred-voltage", "24 V", "preference"),
                )
            ),
        )


def _service(policy, *, currentness_verifier=None, project_id="PRJ-M12"):
    return CandidateComparisonService(
        policy,
        project_id=project_id,
        currentness_verifier=currentness_verifier or _CurrentnessVerifier(),
    )


def _with_metric_value(entry, value):
    candidate, evaluation, _ = entry
    proof = evaluation.m10_stage_outcome.pair_proofs[0]
    certificate = proof.result.certified_leaf_certificates[0]
    pair_certificate = certificate.pair_certificates[0].model_copy(
        update={"certified_lower_clearance_mm": value}
    )
    certificate = certificate.model_copy(
        update={
            "pair_certificates": (pair_certificate,),
            "minimum_certified_lower_clearance_mm": value,
        }
    )
    result = proof.result.model_copy(
        update={"certified_leaf_certificates": (certificate,), "result_hash": "pending"}
    )
    result_payload = result.model_dump(mode="json", exclude={"result_hash"})
    result_hash = "sha256:" + hashlib.sha256(
        json.dumps(result_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    proof = proof.model_copy(
        update={
            "result": result.model_copy(update={"result_hash": result_hash}),
            "result_hash": result_hash,
            "proof_hash": "pending",
        }
    )
    stage = CandidateM10StageOutcome.model_validate(
        evaluation.m10_stage_outcome.model_dump(mode="json")
        | {"pair_proofs": (proof,), "outcome_hash": "pending"}
    )
    metric = evaluation.metrics[0].model_copy(
        update={
            "value": value,
            "source_result_hashes": (result_hash,),
            "metric_hash": "pending",
        }
    )
    return CandidateEvaluation.model_validate(
        evaluation.model_dump(mode="json")
        | {
            "m10_stage_outcome": stage,
            "m10_stage_outcome_hash": _stage_outcome_hash(stage),
            "metrics": (metric,),
            "evaluation_hash": "pending",
        }
    )


def test_policy_hash_is_independent_of_candidate_set_and_request_binds_substitutions():
    state = _state()
    first = _evaluated_candidate("a", state)
    second = _evaluated_candidate("b", state)
    policy = _policy()

    request_one = _request(policy, (first,))
    request_two = _request(policy, (first, second))
    substituted = _request(policy, (second,))

    assert policy.policy_hash == _policy().policy_hash
    assert request_one.request_hash != request_two.request_hash
    assert request_one.request_hash != substituted.request_hash


def test_compare_maximizes_verified_clearance_and_binds_exact_result():
    state = _state()
    lower = _evaluated_candidate("lower", state)
    higher = _evaluated_candidate("higher", state)
    lower_evaluation = _with_metric_value(lower, 3.0)
    higher_evaluation = _with_metric_value(higher, 7.0)
    entries = ((lower[0], lower_evaluation), (higher[0], higher_evaluation))
    request = _request(_policy(), entries)

    result = _service(_policy()).compare(
        request, entries
    )

    assert result.ranked_candidate_hashes == (higher[0].candidate_hash, lower[0].candidate_hash)
    assert result.request_hash == request.request_hash
    assert result.policy_hash == request.policy_hash
    assert result.result_hash == CandidateComparisonService.result_hash(result)


def test_compare_rejects_candidate_evaluation_hash_substitution():
    state = _state()
    candidate_a, _, _ = _evaluated_candidate("candidate-a", state)
    candidate_b, evaluation_b, _ = _evaluated_candidate("candidate-b", state)
    policy = _policy()
    request = _request(policy, ((candidate_b, evaluation_b),))

    with pytest.raises(ValueError, match="candidate.*identity|candidate.*hash"):
        _service(policy).compare(request, ((candidate_a, evaluation_b),))


def test_equal_metric_values_are_a_true_tie_without_hash_preference():
    state = _state()
    first = _evaluated_candidate("first", state)
    second = _evaluated_candidate("second", state)
    entries = (_pair(second), _pair(first))
    request = _request(_policy(), entries)

    result = _service(_policy()).compare(
        request, entries
    )

    assert result.ranked_candidate_hashes == (second[0].candidate_hash, first[0].candidate_hash)
    assert result.ties == ((second[0].candidate_hash, first[0].candidate_hash),)


def test_missing_metric_is_rejected_instead_of_receiving_an_implicit_value():
    candidate, evaluation, scope = _evaluated_candidate("missing")
    forged = evaluation.model_copy(update={"metrics": (), "evaluation_hash": "pending"})
    policy = _policy()
    request = _request(policy, ((candidate, evaluation),))

    with pytest.raises(ValueError, match="metric|integrity"):
        _service(policy).compare(request, ((candidate, forged),))


@pytest.mark.parametrize("field", ["source_result_hashes", "unit"])
def test_metric_source_or_unit_substitution_is_rejected(field):
    candidate, evaluation, scope = _evaluated_candidate(f"substitute-{field}")
    metric = evaluation.metrics[0]
    update = {"metric_hash": "pending"}
    update[field] = ("sha256:" + "f" * 64,) if field == "source_result_hashes" else "cm"
    forged = evaluation.model_copy(
        update={"metrics": (metric.model_copy(update=update),), "evaluation_hash": "pending"}
    )
    policy = _policy()
    request = _request(policy, ((candidate, evaluation),))

    with pytest.raises(ValueError, match="metric|unit|source"):
        _service(policy).compare(request, ((candidate, forged),))


def test_foreign_project_source_and_scope_are_rejected():
    entry = _evaluated_candidate("binding")
    policy = _policy()
    service = _service(policy)

    with pytest.raises(ValueError, match="project"):
        service.compare(_request(policy, (entry,), project_id="OTHER"), (_pair(entry),))
    with pytest.raises(ValueError, match="source"):
        service.compare(_request(policy, (entry,), source_binding_hash="sha256:" + "a" * 64), (_pair(entry),))
    with pytest.raises(ValueError, match="scope"):
        service.compare(_request(policy, (entry,), scope_hash="sha256:" + "b" * 64), (_pair(entry),))


@pytest.mark.parametrize("scope_update", [
    {"required_clearance_mm": 2.0},
    {"angle_interval_deg": (1.0, 91.0)},
    {"pair_scope_requirements": ()},
    {"fidelity_requirements": ()},
])
def test_different_m10_clearance_path_or_fidelity_scope_is_not_compatible(scope_update):
    entry = _evaluated_candidate("scope")
    policy = _policy()
    if "pair_scope_requirements" in scope_update:
        requirement = entry[2].pair_scope_requirements[0].model_copy(
            update={"requirement_key": "different-pair-scope"}
        )
        scope_update = {"pair_scope_requirements": (requirement,)}
    changed_scope = type(entry[2]).model_validate(
        entry[2].model_dump(mode="json") | (scope_update | {"scope_hash": "pending"})
    )
    request = _request(policy, (entry,), scope_hash=changed_scope.scope_hash)

    with pytest.raises(ValueError, match="scope"):
        _service(policy).compare(
            request, (_pair(entry),)
        )


def test_comparison_requires_a_currentness_verifier():
    with pytest.raises(ValueError, match="currentness"):
        CandidateComparisonService(_policy(), project_id="PRJ-M12")


def test_compare_rejects_stale_evaluation_at_comparison_time():
    entry = _evaluated_candidate("stale")
    policy = _policy()
    request = _request(policy, (entry,))

    with pytest.raises(ValueError, match="stale|currentness"):
        _service(policy, currentness_verifier=_StaleCurrentnessVerifier()).compare(
            request, (_pair(entry),)
        )


def test_compare_uses_state_backed_currentness_at_comparison_time(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    entry = _evaluated_candidate("state-backed", state)
    policy = _policy()
    request = _request(policy, (entry,))

    manager.create_revision("PRJ-M12", state.model_copy(update={"id": "changed"}))

    with pytest.raises(ValueError, match="stale|currentness"):
        _service(
            policy,
            currentness_verifier=_StateBackedCurrentnessVerifier(manager),
        ).compare(request, (_pair(entry),))


def _comparison_result_fixture(state=None):
    state = state or _state()
    lower = _evaluated_candidate("result-lower", state)
    higher = _evaluated_candidate("result-higher", state)
    lower_evaluation = _with_metric_value(lower, 3.0)
    higher_evaluation = _with_metric_value(higher, 7.0)
    entries = ((lower[0], lower_evaluation), (higher[0], higher_evaluation))
    policy = _policy()
    request = _request(policy, entries)
    result = _service(policy).compare(request, entries)
    return result, lower, higher


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ranked_candidate_hashes", lambda result, lower, higher: (lower[0].candidate_hash, lower[0].candidate_hash)),
        ("ranked_evaluation_hashes", lambda result, lower, higher: (result.ranked_evaluation_hashes[0], result.ranked_evaluation_hashes[0])),
        ("metric_values", lambda result, lower, higher: ((lower[0].candidate_hash, 3.0),)),
        ("ties", lambda result, lower, higher: ((lower[0].candidate_hash, higher[0].candidate_hash),)),
    ],
)
def test_result_rejects_incomplete_or_inconsistent_semantics(field, value):
    result, lower, higher = _comparison_result_fixture()
    forged = result.model_copy(
        update={field: value(result, lower, higher), "result_hash": "pending"}
    )

    with pytest.raises(ValueError, match="comparison|rank|metric|tie|pair|candidate"):
        CandidateComparisonResult.model_validate(forged.model_dump(mode="json"))


def test_result_rejects_ranked_candidate_evaluation_pair_substitution():
    result, lower, higher = _comparison_result_fixture()
    forged = result.model_copy(
        update={
            "ranked_candidate_hashes": (higher[0].candidate_hash, lower[0].candidate_hash),
            "ranked_evaluation_hashes": (
                result.ranked_evaluation_hashes[1],
                result.ranked_evaluation_hashes[1],
            ),
            "result_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="pair|ranking|evaluation"):
        CandidateComparisonResult.model_validate(forged.model_dump(mode="json"))


@pytest.mark.parametrize(
    "direction",
    [CandidateComparisonDirection.MAXIMIZE, CandidateComparisonDirection.MINIMIZE],
)
def test_result_rejects_ranking_order_not_matching_policy_direction(direction):
    state = _state()
    lower = _evaluated_candidate(f"order-lower-{direction.value}", state)
    higher = _evaluated_candidate(f"order-higher-{direction.value}", state)
    lower_evaluation = _with_metric_value(lower, 3.0)
    higher_evaluation = _with_metric_value(higher, 7.0)
    entries = ((lower[0], lower_evaluation), (higher[0], higher_evaluation))
    policy = CandidateComparisonPolicy(
        metric_keys=(CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM,),
        directions=(direction,),
        expected_units=("mm",),
    )
    request = _request(policy, entries)
    result = _service(policy).compare(request, entries)
    forged = result.model_copy(
        update={
            "ranked_candidate_hashes": tuple(reversed(result.ranked_candidate_hashes)),
            "ranked_evaluation_hashes": tuple(reversed(result.ranked_evaluation_hashes)),
            "metric_values": tuple(reversed(result.metric_values)),
            "ties": (),
            "result_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="ranking|order|metric"):
        CandidateComparisonResult.model_validate(forged.model_dump(mode="json"))


def test_result_rejects_whitespace_only_comparator_version():
    result, _, _ = _comparison_result_fixture()
    forged = result.model_copy(update={"comparator_version": "   ", "result_hash": "pending"})

    with pytest.raises(ValueError, match="comparator version"):
        CandidateComparisonResult.model_validate(forged.model_dump(mode="json"))


def test_result_hash_is_recomputed_after_valid_result_reconstruction():
    result, _, _ = _comparison_result_fixture()
    reconstructed = CandidateComparisonResult.model_validate(
        result.model_dump(mode="json") | {"result_hash": "pending"}
    )

    assert reconstructed.result_hash == CandidateComparisonService.result_hash(reconstructed)


def test_result_rejects_forged_request_hash_when_reconstructing_request_identity():
    result, _, _ = _comparison_result_fixture()
    forged = result.model_copy(
        update={"request_hash": "sha256:" + "f" * 64, "result_hash": "pending"}
    )

    with pytest.raises(ValueError, match="request.*identity|request hash"):
        CandidateComparisonResult.model_validate(forged.model_dump(mode="json"))


def test_result_rejects_reordered_request_pairs():
    result, _, _ = _comparison_result_fixture()
    forged = result.model_copy(
        update={
            "candidate_evaluation_pairs": tuple(reversed(result.candidate_evaluation_pairs)),
            "result_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="request.*identity|request hash"):
        CandidateComparisonResult.model_validate(forged.model_dump(mode="json"))
