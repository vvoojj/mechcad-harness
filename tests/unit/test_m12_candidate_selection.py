from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from mechcad_harness.candidates import (
    CandidateComparisonPolicy,
    CandidateComparisonService,
    CandidateEvaluation,
    CandidateEvaluationCurrentnessService,
    CandidateEvaluationOutcome,
    CandidateEvaluationPolicy,
    CandidateSelection,
    CandidateSelectionService,
    CandidateM10StageOutcome,
)
from mechcad_harness.candidates.models import CandidateSynthesisPolicy, CandidateSynthesisRequest
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.continuous_proof import ContinuousSingleAxisProofStatus

from test_m12_candidate_comparison import (
    _CurrentnessVerifier,
    _comparison_result_fixture,
    _policy,
    _request,
    _service as comparison_service,
    _with_metric_value,
)
from test_m12_candidate_evaluation import _evaluation_candidate
from test_m12_candidate_evaluation import _bound_m10_inputs, _m12_result, _evaluation_service
from test_m12_candidate_foundation import _state
from mechcad_harness.revolute_drive import admissibility_result_hash


_selection_state = None


class _SelectionCurrentnessVerifier:
    def __init__(self, manager):
        self._service = CandidateEvaluationCurrentnessService(
            manager, cad_replay_verifier=lambda *args: None
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


class _RecordingSelectionCurrentnessVerifier:
    def __init__(self, stale_candidate_hash=None):
        self.calls = []
        self.stale_candidate_hash = stale_candidate_hash

    def verify_current(self, evaluation, candidate):
        self.calls.append((candidate.candidate_hash, evaluation.evaluation_hash))
        if candidate.candidate_hash == self.stale_candidate_hash:
            raise ValueError("candidate evaluation is stale")
        return True


def _selection_service(state=None):
    state = state or _selection_state
    if state is None:
        raise AssertionError("selection fixture must be created before the service")
    temporary_directory = tempfile.TemporaryDirectory()
    manager = StateManager(Path(temporary_directory.name))
    manager.create_project("PRJ-M12", state)
    verifier = _SelectionCurrentnessVerifier(manager)
    verifier._temporary_directory = temporary_directory
    return CandidateSelectionService(
        project_id="PRJ-M12",
        currentness_verifier=verifier,
    )


def _selection_fixture(state=None):
    global _selection_state
    _selection_state = state or _state()
    comparison, lower, higher = _comparison_result_fixture(_selection_state)
    return comparison, (lower[0], _with_metric_value(lower, 3.0), lower[2]), (higher[0], _with_metric_value(higher, 7.0), higher[2])


def test_selection_binds_exact_feasible_evaluation_and_allows_non_top_ranked_candidate():
    comparison, lower, higher = _selection_fixture()

    selection = _selection_service().select(
        lower[0],
        lower[1],
        selector_identity="human-reviewer",
        rationale="The lower-ranked option fits the packaging constraint.",
        comparison=comparison,
        comparison_entries=((lower[0], lower[1]), (higher[0], higher[1])),
    )

    assert selection.candidate_hash == lower[0].candidate_hash
    assert selection.evaluation_hash == lower[1].evaluation_hash
    assert selection.source_binding_hash == lower[1].source_binding_hash
    assert selection.evaluation_scope_hash == lower[1].evaluation_scope_hash
    assert selection.selector_identity == "human-reviewer"
    assert selection.rationale.startswith("The lower-ranked")
    assert selection.comparison_used is True
    assert selection.comparison_result_hash == comparison.result_hash
    assert selection.selection_hash == CandidateSelectionService.selection_hash(selection)
    assert lower[0].candidate_hash != comparison.ranked_candidate_hashes[0]


def test_selection_without_comparison_records_no_comparison_identity():
    _, lower, _ = _selection_fixture()

    selection = _selection_service().select(
        lower[0],
        lower[1],
        selector_identity="manual",
        rationale="Selected after a review outside the comparator.",
    )

    assert selection.comparison_used is False
    assert selection.comparison_result_hash is None


def test_selection_rejects_infeasible_or_unresolved_evaluation():
    state = _state()
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    proof = m10.pair_proofs[0]
    not_proven_result = proof.result.model_copy(
        update={
            "status": ContinuousSingleAxisProofStatus.NOT_PROVEN,
            "certified_leaf_certificates": (),
            "unresolved_intervals": ((proof.result.start_angle_deg, proof.result.end_angle_deg),),
            "result_hash": "pending",
        }
    )
    payload = not_proven_result.model_dump(mode="json", exclude={"result_hash"})
    not_proven_result = not_proven_result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        }
    )
    not_proven_proof = proof.model_copy(
        update={
            "result": not_proven_result,
            "result_hash": not_proven_result.result_hash,
            "proof_hash": "pending",
        }
    )
    not_proven_m10 = CandidateM10StageOutcome.model_validate(
        m10.model_dump(mode="json")
        | {"pair_proofs": (not_proven_proof,), "outcome_hash": "pending"}
    )
    unresolved = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        not_proven_m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )

    assert unresolved.outcome is CandidateEvaluationOutcome.UNRESOLVED
    with pytest.raises(ValueError, match="FEASIBLE|unresolved"):
        _selection_service(state).select(candidate, unresolved, "manual", "Not selectable.")


def test_selection_rejects_candidate_evaluation_substitution_and_stale_currentness():
    _, lower, higher = _selection_fixture()

    with pytest.raises(ValueError, match="candidate.*identity|binding"):
        _selection_service().select(lower[0], higher[1], "manual", "Wrong evaluation.")

    class _StaleVerifier:
        def verify_current(self, evaluation, candidate):
            raise ValueError("candidate evaluation is stale")

    with pytest.raises(ValueError, match="stale|currentness"):
        CandidateSelectionService(project_id="PRJ-M12", currentness_verifier=_StaleVerifier()).select(
            lower[0], lower[1], "manual", "Stale record."
        )


@pytest.mark.parametrize("field", ["synthesis_request_hash", "synthesis_policy_hash"])
def test_selection_requires_evaluation_synthesis_bindings_to_match_candidate(field):
    _, lower, _ = _selection_fixture()
    forged_result = lower[1].m12_3_result.model_copy(
        update={field: "sha256:" + "f" * 64, "result_hash": "pending"}
    )
    forged_evaluation = CandidateEvaluation.model_validate(
        lower[1].model_dump(mode="json")
        | {
            field: "sha256:" + "f" * 64,
            "m12_3_result": forged_result,
            "m12_3_result_hash": admissibility_result_hash(forged_result),
            "evaluation_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="synthesis|request|policy"):
        CandidateSelectionService(project_id="PRJ-M12", currentness_verifier=_CurrentnessVerifier()).select(
            lower[0], forged_evaluation, "manual", "Mismatched synthesis binding."
        )


def test_selection_rejects_a_rehashed_comparison_metric_not_equal_to_evaluation():
    comparison, lower, higher = _selection_fixture()
    forged_comparison = comparison.model_copy(
        update={
            "ranked_candidate_hashes": (lower[0].candidate_hash, higher[0].candidate_hash),
            "ranked_evaluation_hashes": (lower[1].evaluation_hash, higher[1].evaluation_hash),
            "metric_values": (
                (lower[0].candidate_hash, 8.0),
                (higher[0].candidate_hash, 7.0),
            ),
            "ties": (),
            "result_hash": "pending",
        }
    )
    forged_comparison = type(comparison).model_validate(
        forged_comparison.model_dump(mode="json")
    )

    with pytest.raises(ValueError, match="metric"):
        _selection_service().select(
            lower[0],
            lower[1],
            "manual",
            "Reject a rehashed comparison metric.",
            comparison=forged_comparison,
            comparison_entries=((lower[0], lower[1]), (higher[0], higher[1])),
        )


def test_selection_revalidates_state_backed_currentness_after_source_changes(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    comparison, lower, higher = _selection_fixture(state)
    service = CandidateSelectionService(
        project_id="PRJ-M12",
        currentness_verifier=_SelectionCurrentnessVerifier(manager),
    )

    manager.create_revision("PRJ-M12", state.model_copy(update={"id": "changed"}))

    with pytest.raises(ValueError, match="current|stale|source"):
        service.select(
            lower[0],
            lower[1],
            "manual",
            "Reject a stale comparison member.",
            comparison=comparison,
            comparison_entries=((lower[0], lower[1]), (higher[0], higher[1])),
        )


def test_selection_rejects_foreign_or_forged_comparison_and_missing_membership():
    comparison, lower, higher = _selection_fixture()

    with pytest.raises(ValueError, match="comparison|source"):
        _selection_service().select(
            lower[0],
            lower[1],
            "manual",
            "Foreign comparison.",
            comparison=comparison.model_copy(
                update={"source_binding_hash": "sha256:" + "f" * 64, "result_hash": "pending"}
            ),
            comparison_entries=((lower[0], lower[1]), (higher[0], higher[1])),
        )


def test_selection_revalidates_every_cited_comparison_member_and_exact_pair_binding():
    comparison, lower, higher = _selection_fixture()
    verifier = _RecordingSelectionCurrentnessVerifier(higher[0].candidate_hash)
    service = CandidateSelectionService(project_id="PRJ-M12", currentness_verifier=verifier)
    entries = ((lower[0], lower[1]), (higher[0], higher[1]))

    with pytest.raises(ValueError, match="stale|currentness"):
        service.select(
            lower[0],
            lower[1],
            "manual",
            "Reject a stale non-selected comparison member.",
            comparison=comparison,
            comparison_entries=entries,
        )

    assert verifier.calls == [
        (lower[0].candidate_hash, lower[1].evaluation_hash),
        (higher[0].candidate_hash, higher[1].evaluation_hash),
    ]

    with pytest.raises(ValueError, match="identity|pair|binding|comparison"):
        service.select(
            lower[0],
            lower[1],
            "manual",
            "Reject a substituted comparison member.",
            comparison=comparison,
            comparison_entries=((lower[0], higher[1]), (higher[0], higher[1])),
        )

    with pytest.raises(ValueError, match="contain|member|candidate"):
        _selection_service().select(
            lower[0],
            lower[1],
            "manual",
            "Candidate absent from comparison.",
            comparison=CandidateComparisonService(_policy(), currentness_verifier=_CurrentnessVerifier()).compare(
                _request(_policy(), ((higher[0], higher[1]),)), ((higher[0], higher[1]),)
            ),
            comparison_entries=((higher[0], higher[1]),),
        )


def test_selection_rejects_inconsistent_text_and_comparison_flag():
    _, lower, _ = _selection_fixture()

    with pytest.raises(ValueError, match="selector|rationale"):
        _selection_service().select(lower[0], lower[1], "  ", "Valid rationale.")
    with pytest.raises(ValueError, match="selector|rationale"):
        _selection_service().select(lower[0], lower[1], "manual", "  ")


def test_selection_calls_do_not_change_canonical_state(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    before = manager.load_current_state("PRJ-M12")
    before_hash = state_hash(before)
    _, lower, _ = _selection_fixture(state)
    service = CandidateSelectionService(
        project_id="PRJ-M12",
        currentness_verifier=_SelectionCurrentnessVerifier(manager)
    )

    service.select(lower[0], lower[1], "manual", "No canonical mutation.")

    after = manager.load_current_state("PRJ-M12")
    assert after.revision == before.revision
    assert state_hash(after) == before_hash


def test_selection_requires_an_explicit_project_binding():
    with pytest.raises(TypeError, match="project_id"):
        CandidateSelectionService(currentness_verifier=_CurrentnessVerifier())


def test_selection_rejects_a_candidate_from_a_foreign_project():
    _, lower, _ = _selection_fixture()
    service = CandidateSelectionService(
        project_id="PRJ-OTHER",
        currentness_verifier=_CurrentnessVerifier(),
    )

    with pytest.raises(ValueError, match="project"):
        service.select(lower[0], lower[1], "manual", "Foreign candidate.")
