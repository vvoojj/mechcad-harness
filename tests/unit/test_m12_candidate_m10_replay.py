from __future__ import annotations

import pytest

from mechcad_harness.candidates import CandidateM10EvaluationService
from mechcad_harness.candidates.m10_evaluation import CandidateM10EvaluationRequest

from test_m12_candidate_m10_service import _continuous_result, _home_result, _request
from test_m12_candidate_m10_binding import _binding, _realization, _scope


def test_candidate_m10_replay_rejects_scope_and_realization_substitution():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)

    def prove(**kwargs):
        return _continuous_result(kwargs)

    service = CandidateM10EvaluationService(prove, lambda **kwargs: _home_result(kwargs), scope=scope)
    baseline = service.evaluate(1, "sha256:" + "a" * 64, realization, binding, request)
    assert baseline.outcome_hash.startswith("sha256:")

    changed_scope = type(scope).model_validate(scope.model_dump(mode="python") | {"required_clearance_mm": 2.0, "scope_hash": "pending"})
    changed_request = _request(realization, binding, changed_scope)
    with pytest.raises(ValueError, match="scope"):
        service.evaluate(1, "sha256:" + "a" * 64, realization, binding, changed_request)

    forged_realization = realization.model_copy(update={"realization_hash": "sha256:" + "f" * 64})
    with pytest.raises(ValueError, match="realization"):
        service.evaluate(1, "sha256:" + "a" * 64, forged_realization, binding, request)


def test_cad_not_reached_does_not_fabricate_m10_identities():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)
    from mechcad_harness.candidates.cad_realization import CandidateCadStageOutcome, CandidateCadStageStatus, CandidateCadStageReason

    prior = CandidateCadStageOutcome(status=CandidateCadStageStatus.NOT_REACHED, reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,))
    outcome = CandidateM10EvaluationService(lambda **kwargs: None, lambda **kwargs: None, scope=scope).evaluate(
        1, "sha256:" + "a" * 64, prior, binding, request
    )

    assert outcome.m10_request_hashes == ()
    assert outcome.m10_result_hashes == ()


def test_cad_not_reached_still_validates_request_against_scope_and_binding():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    changed_scope = type(scope).model_validate(scope.model_dump(mode="python") | {
        "required_clearance_mm": 2.0,
        "scope_hash": "pending",
    })
    changed_request = _request(realization, binding, changed_scope)
    from mechcad_harness.candidates.cad_realization import CandidateCadStageOutcome, CandidateCadStageReason, CandidateCadStageStatus

    prior = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.NOT_REACHED,
        reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,),
    )
    with pytest.raises(ValueError, match="scope"):
        CandidateM10EvaluationService(lambda **kwargs: None, lambda **kwargs: None, scope=scope).evaluate(
            1, "sha256:" + "a" * 64, prior, binding, changed_request
        )


def test_not_reached_short_circuit_rejects_request_hashes_not_bound_to_context():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)
    forged = request.model_copy(update={"binding_hash": "sha256:" + "f" * 64, "request_hash": "pending"})
    from mechcad_harness.candidates.cad_realization import CandidateCadStageOutcome, CandidateCadStageReason, CandidateCadStageStatus

    prior = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.NOT_REACHED,
        reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,),
    )
    with pytest.raises(ValueError, match="binding|request|context"):
        CandidateM10EvaluationService(lambda **kwargs: None, lambda **kwargs: None, scope=scope).evaluate(
            1, "sha256:" + "a" * 64, prior, binding, forged
        )


@pytest.mark.parametrize("field", ("cad_realization_hash", "binding_hash"))
def test_m10_replay_rejects_cad_or_binding_request_substitution(field):
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)
    forged = request.model_dump(mode="python")
    forged_inventory = dict(forged["inventory"])
    replacement = "sha256:" + "f" * 64
    forged[field] = replacement
    forged_inventory[field] = replacement
    forged_inventory["inventory_hash"] = "pending"
    forged["inventory"] = forged_inventory
    forged["request_hash"] = "pending"
    forged_request = CandidateM10EvaluationRequest(**forged)

    service = CandidateM10EvaluationService(
        lambda **kwargs: _continuous_result(kwargs),
        lambda **kwargs: _home_result(kwargs),
        scope=scope,
    )
    with pytest.raises(ValueError, match="CAD|binding|realization"):
        service.evaluate(1, "sha256:" + "a" * 64, realization, binding, forged_request)
