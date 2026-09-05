from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.candidates import (
    CandidateMultiJointM10EvaluationService,
    CandidateMultiJointM10Replay,
    CandidateMultiJointSelection,
    CandidateMultiJointSelectionService,
    candidate_multi_joint_selection_hash,
)
from mechcad_harness.candidates.services import CandidateCurrentness
from mechcad_harness.multi_joint_collision_sweep import (
    MultiJointCollisionSweepResultV2,
    multi_joint_collision_sweep_result_v2_hash,
)

from test_m13_3_candidate_evaluation import _CurrentnessVerifier, _request, _result, _scope


class _SelectionCurrentnessVerifier:
    def __init__(self, result=CandidateCurrentness.CURRENT):
        self.result = result
        self.calls = []

    def evaluate_source_binding(self, candidate):
        self.calls.append(candidate.candidate_hash)
        return self.result


def _chain(tmp_path, values=(0.0, 10.0)):
    candidate, realization, bridge, request = _request(tmp_path)
    if values != (0.0, 10.0):
        request = CandidateMultiJointM10EvaluationService(
            currentness_verifier=_CurrentnessVerifier()
        ).build_request(
            candidate,
            realization,
            bridge,
            _scope(bridge, values),
            placement_derivations=request.placement_derivations,
        )

    def analyze(**_kwargs):
        reconstructed = CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
            bridge, realization, request.scope
        )
        return _result(reconstructed, realization.assembly)

    evaluation = CandidateMultiJointM10EvaluationService(
        analyze_multi_joint_collision_sweep_v2=analyze,
        currentness_verifier=_CurrentnessVerifier(),
    ).execute(candidate, realization, bridge, request)
    return candidate, realization, bridge, request, evaluation


def _trusted_result_replayer(realization, bridge):
    def replay(candidate, request, _evaluation):
        reconstruction = CandidateMultiJointM10EvaluationService(
            currentness_verifier=_CurrentnessVerifier()
        ).reconstruct_m10_request(candidate, realization, bridge, request)
        return CandidateMultiJointM10Replay(
            reconstruction,
            _result(reconstruction, realization.assembly),
        )

    return replay


def _selection_service(request, realization, bridge, verifier=None, replayer=None):
    return CandidateMultiJointSelectionService(
        project_id=request.project_id,
        currentness_verifier=verifier or _SelectionCurrentnessVerifier(),
        result_replayer=replayer or _trusted_result_replayer(realization, bridge),
    )


def test_selection_has_exact_wire_fields_and_frozen_hash_payload(tmp_path):
    candidate, realization, bridge, request, evaluation = _chain(tmp_path)

    selection = _selection_service(request, realization, bridge).select(
        candidate,
        request,
        evaluation,
        "human-reviewer",
        "Selected after reviewing the exact multi-joint clearance chain.",
    )

    assert set(selection.model_dump(mode="json")) == {
        "schema_version",
        "project_id",
        "source_revision",
        "source_state_hash",
        "source_binding_hash",
        "candidate_hash",
        "evaluation_hash",
        "candidate_request_hash",
        "m10_v2_request_hash",
        "m10_v2_result_hash",
        "physical_to_m10_bridge_hash",
        "m10_model_hash",
        "physical_pair_classification_set_hash",
        "inventory_hash",
        "exact_pair_scope_hash",
        "scope_hash",
        "configuration_set_hash",
        "selector_identity",
        "rationale",
        "selection_hash",
    }
    payload = selection.model_dump(mode="json")
    actual_hash = payload.pop("selection_hash")
    expected_hash = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert actual_hash == expected_hash == candidate_multi_joint_selection_hash(selection)
    assert selection.schema_version == "candidate-multi-joint-selection@1"
    assert selection.configuration_set_hash == request.configuration_set_hash
    assert selection.selector_identity == "human-reviewer"


def test_selection_replays_the_complete_request_and_evaluation_chain(tmp_path):
    candidate, realization, bridge, request, evaluation = _chain(tmp_path)
    verifier = _SelectionCurrentnessVerifier()
    replay_calls = []
    trusted_replayer = _trusted_result_replayer(realization, bridge)

    def replayer(replayed_candidate, replayed_request, replayed_evaluation):
        replay_calls.append((replayed_candidate, replayed_request, replayed_evaluation))
        return trusted_replayer(replayed_candidate, replayed_request, replayed_evaluation)

    selection = _selection_service(request, realization, bridge, verifier, replayer).select(
        candidate, request, evaluation, "manual", "The exact chain is acceptable."
    )

    assert selection.project_id == candidate.source_binding.project_id
    assert selection.source_revision == candidate.source_binding.source_revision
    assert selection.source_state_hash == candidate.source_binding.source_state_hash
    assert selection.source_binding_hash == request.source_binding_hash
    assert selection.candidate_hash == request.candidate_hash == evaluation.candidate_hash
    assert selection.evaluation_hash == evaluation.evaluation_hash
    assert selection.candidate_request_hash == request.request_hash
    assert selection.m10_v2_request_hash == request.m10_v2_request_hash == evaluation.m10_v2_request_hash
    assert selection.m10_v2_result_hash == evaluation.m10_v2_result_hash
    assert selection.physical_to_m10_bridge_hash == request.physical_to_m10_bridge_hash
    assert selection.m10_model_hash == request.m10_model_hash == evaluation.m10_model_hash
    assert selection.physical_pair_classification_set_hash == request.physical_pair_classification_set_hash
    assert selection.inventory_hash == request.inventory_hash == evaluation.inventory_hash
    assert selection.exact_pair_scope_hash == request.exact_pair_scope_hash == evaluation.exact_pair_scope_hash
    assert selection.scope_hash == request.scope_hash == evaluation.scope_hash
    assert selection.configuration_set_hash == request.configuration_set_hash == evaluation.configuration_set_hash
    assert verifier.calls == [candidate.candidate_hash]
    assert replay_calls == [(candidate, request, evaluation)]


@pytest.mark.parametrize("selector_identity,rationale", [("  ", "valid"), ("valid", "  ")])
def test_selection_requires_nonblank_identity_bearing_text(
    tmp_path, selector_identity, rationale
):
    candidate, realization, bridge, request, evaluation = _chain(tmp_path)

    with pytest.raises(ValueError, match="selector|rationale|empty|blank"):
        _selection_service(request, realization, bridge).select(
            candidate, request, evaluation, selector_identity, rationale
        )


def test_selection_rejects_stale_source_before_emitting_selection(tmp_path):
    candidate, realization, bridge, request, evaluation = _chain(tmp_path)

    with pytest.raises(ValueError, match="current|stale"):
        _selection_service(
            request,
            realization,
            bridge,
            _SelectionCurrentnessVerifier(
                CandidateCurrentness.STALE_RELATIVE_TO_CURRENT_STATE
            ),
        ).select(candidate, request, evaluation, "manual", "Stale must be rejected.")


def test_selection_consumer_rejects_evaluation_a_with_request_b_command_chain(tmp_path):
    candidate, realization, bridge, request_a, evaluation_a = _chain(tmp_path, (0.0, 10.0))
    request_b = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessVerifier()
    ).build_request(
        candidate,
        realization,
        bridge,
        _scope(bridge, (0.0, 11.0)),
        placement_derivations=request_a.placement_derivations,
    )

    assert request_a.physical_to_m10_bridge_hash == request_b.physical_to_m10_bridge_hash
    assert request_a.m10_model_hash == request_b.m10_model_hash
    assert request_a.inventory_hash == request_b.inventory_hash
    assert request_a.exact_pair_scope_hash == request_b.exact_pair_scope_hash
    assert request_a.configuration_set_hash != request_b.configuration_set_hash
    assert request_a.m10_v2_request_hash != request_b.m10_v2_request_hash

    with pytest.raises(ValueError, match="request|configuration|chain|binding"):
        _selection_service(request_a, realization, bridge).select(
            candidate,
            request_b,
            evaluation_a,
            "manual",
            "Reject the old evaluation for changed commands.",
        )


def test_selection_consumer_rejects_evaluation_b_with_request_a_chain(tmp_path):
    candidate, realization, bridge, request_a, _ = _chain(tmp_path, (0.0, 10.0))
    request_b = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessVerifier()
    ).build_request(
        candidate,
        realization,
        bridge,
        _scope(bridge, (0.0, 11.0)),
        placement_derivations=request_a.placement_derivations,
    )

    def analyze(**_kwargs):
        reconstructed = CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
            bridge, realization, request_b.scope
        )
        return _result(reconstructed, realization.assembly)

    evaluation_b = CandidateMultiJointM10EvaluationService(
        analyze_multi_joint_collision_sweep_v2=analyze,
        currentness_verifier=_CurrentnessVerifier(),
    ).execute(candidate, realization, bridge, request_b)

    with pytest.raises(ValueError, match="request|configuration|chain|binding"):
        _selection_service(request_a, realization, bridge).select(
            candidate,
            request_a,
            evaluation_b,
            "manual",
            "Reject a substituted evaluation chain.",
        )


def test_selection_rejects_forged_rehashed_evaluation_identity(tmp_path):
    candidate, realization, bridge, request, evaluation = _chain(tmp_path)
    forged = evaluation.model_copy(
        update={
            "configuration_set_hash": "sha256:" + "f" * 64,
            "evaluation_hash": "pending",
        }
    )
    forged = type(evaluation).model_validate(forged.model_dump(mode="json"))

    with pytest.raises(ValueError, match="configuration|binding|request"):
        _selection_service(request, realization, bridge).select(
            candidate, request, forged, "manual", "Reject forged bindings."
        )


def test_selection_rejects_rehashed_candidate_physical_identity_substitution(tmp_path):
    candidate, realization, bridge, request, evaluation = _chain(tmp_path)
    forged_request = request.model_copy(
        update={
            "physical_mechanism_hash": "sha256:" + "f" * 64,
            "request_hash": "pending",
        }
    )
    forged_request = type(request).model_validate(forged_request.model_dump(mode="json"))
    forged_evaluation = evaluation.model_copy(
        update={
            "physical_mechanism_hash": forged_request.physical_mechanism_hash,
            "candidate_request_hash": forged_request.request_hash,
            "evaluation_hash": "pending",
        }
    )
    forged_evaluation = type(evaluation).model_validate(
        forged_evaluation.model_dump(mode="json")
    )

    with pytest.raises(ValueError, match="physical mechanism|candidate|binding"):
        _selection_service(request, realization, bridge).select(
            candidate,
            forged_request,
            forged_evaluation,
            "manual",
            "Reject a rehashed physical substitution.",
        )


def test_selection_is_additive_and_legacy_selection_still_has_comparison_shape():
    from mechcad_harness.candidates import CandidateSelection

    assert "comparison_used" in CandidateSelection.model_fields
    assert "comparison_used" not in CandidateMultiJointSelection.model_fields


def test_selection_requires_a_trusted_result_replayer(tmp_path):
    candidate, _, _, request, _ = _chain(tmp_path)

    with pytest.raises(ValueError, match="result.*replay|replayer"):
        CandidateMultiJointSelectionService(
            project_id=request.project_id,
            currentness_verifier=_SelectionCurrentnessVerifier(),
        )


def test_selection_rejects_a_rehashed_request_with_substituted_cad_realization(
    tmp_path,
):
    candidate, realization, bridge, request, evaluation = _chain(tmp_path)
    forged_request = request.model_copy(
        update={
            "cad_realization_hash": "sha256:" + "f" * 64,
            "request_hash": "pending",
        }
    )
    forged_request = type(request).model_validate(forged_request.model_dump(mode="json"))
    forged_evaluation = evaluation.model_copy(
        update={
            "candidate_request_hash": forged_request.request_hash,
            "evaluation_hash": "pending",
        }
    )
    forged_evaluation = type(evaluation).model_validate(
        forged_evaluation.model_dump(mode="json")
    )

    with pytest.raises(ValueError, match="request|CAD|trusted|replay"):
        _selection_service(request, realization, bridge).select(
            candidate,
            forged_request,
            forged_evaluation,
            "manual",
            "Reject a substituted CAD realization.",
        )


def test_selection_replays_result_instead_of_accepting_rehashed_result_metadata(
    tmp_path,
):
    candidate, realization, bridge, request, evaluation = _chain(tmp_path)
    trusted_result = _result(
        CandidateMultiJointM10EvaluationService._reconstruct_m10_request(
            bridge, realization, request.scope
        ),
        realization.assembly,
    )
    changed_result = trusted_result.model_copy(
        update={"any_touching": True, "result_hash": "pending"}
    )
    changed_result = changed_result.model_copy(
        update={"result_hash": multi_joint_collision_sweep_result_v2_hash(changed_result)}
    )
    assert isinstance(changed_result, MultiJointCollisionSweepResultV2)
    forged_evaluation = evaluation.model_copy(
        update={
            "m10_v2_result_hash": changed_result.result_hash,
            "evaluation_hash": "pending",
        }
    )
    forged_evaluation = type(evaluation).model_validate(
        forged_evaluation.model_dump(mode="json")
    )
    forged_selection = CandidateMultiJointSelection(
        project_id=request.project_id,
        source_revision=request.source_revision,
        source_state_hash=request.source_state_hash,
        source_binding_hash=request.source_binding_hash,
        candidate_hash=request.candidate_hash,
        evaluation_hash=forged_evaluation.evaluation_hash,
        candidate_request_hash=request.request_hash,
        m10_v2_request_hash=request.m10_v2_request_hash,
        m10_v2_result_hash=forged_evaluation.m10_v2_result_hash,
        physical_to_m10_bridge_hash=request.physical_to_m10_bridge_hash,
        m10_model_hash=request.m10_model_hash,
        physical_pair_classification_set_hash=request.physical_pair_classification_set_hash,
        inventory_hash=request.inventory_hash,
        exact_pair_scope_hash=request.exact_pair_scope_hash,
        scope_hash=request.scope_hash,
        configuration_set_hash=request.configuration_set_hash,
        selector_identity="manual",
        rationale="A forged selection must not bypass replay.",
    )
    assert forged_selection.selection_hash == candidate_multi_joint_selection_hash(
        forged_selection
    )

    with pytest.raises(ValueError, match="result|replay|evaluation"):
        _selection_service(request, realization, bridge).select(
            candidate,
            request,
            forged_evaluation,
            "manual",
            "Reject reclassified replay metadata.",
        )


def test_selection_rejects_replayed_result_with_substituted_assembly_hash(
    tmp_path,
):
    candidate, realization, bridge, request, evaluation = _chain(tmp_path)
    trusted_replayer = _trusted_result_replayer(realization, bridge)
    trusted_replay = trusted_replayer(candidate, request, evaluation)
    forged_result = trusted_replay.result.model_copy(
        update={
            "source_assembly_hash": "sha256:" + "f" * 64,
            "result_hash": "pending",
        }
    )
    forged_result = forged_result.model_copy(
        update={"result_hash": multi_joint_collision_sweep_result_v2_hash(forged_result)}
    )
    forged_evaluation = evaluation.model_copy(
        update={
            "m10_v2_result_hash": forged_result.result_hash,
            "evaluation_hash": "pending",
        }
    )
    forged_evaluation = type(evaluation).model_validate(
        forged_evaluation.model_dump(mode="json")
    )

    def forged_replayer(candidate, request, evaluation):
        replay = trusted_replayer(candidate, request, evaluation)
        return CandidateMultiJointM10Replay(replay.request, forged_result)

    with pytest.raises(ValueError, match="assembly|binding|replay"):
        _selection_service(
            request,
            realization,
            bridge,
            replayer=forged_replayer,
        ).select(
            candidate,
            request,
            forged_evaluation,
            "manual",
            "Reject substituted replay assembly.",
        )
