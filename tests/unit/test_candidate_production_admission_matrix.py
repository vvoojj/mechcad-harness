"""Literal T-P2.6 ``ProductionApplication`` candidate-admission route matrix.

Transcribed verbatim from the accepted controlling Plan
``docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md``
§T-P2.6, "``ProductionApplication`` candidate-admission table" (lines 304-316).

Each row names one production entrypoint and its exact request@2 route.  Every
test below builds the real request@2/candidate@2 fixtures from the existing unit
infrastructure and then **calls the real production route** (a composed
``ProductionApplication`` instance, or the real service the application
delegates to when the composed provider needs live CAD), asserting the exact
behavior observed on the current tree.

The Plan's table describes the *final implemented state* ("new-family rows are
mandatory; legacy remains explicit replay-only") and states that P2 itself
activates only reject-only boundaries.  Each row becomes a positive new-family
admission route in its stated P3/P5/P7 owner task; the deterministic default
itself changes only at T-P8.4a.  On the current tree the activated new-family
routes are rows 1-7 (revolute realization, candidate CAD, evaluation, multi-joint
M10/selection, and the decision comparison/selection chain); rows 8-9
(promotion compile/apply) remain reject-only because their owner task T-P7.2 is
not yet complete.  Row 1 dispatches on the request schema family: an inbound
typed ``candidate-synthesis-request@2`` is trusted-bound and constructed as
candidate@2, while an inbound ``@1`` request keeps the legacy family (the
integration production paths construct ``@1`` requests).  Row 9's promotion@2
application route is admitted (no legacy ``@1`` downgrade) but fails closed
before canonical mutation.  The assertions below pin that observed split; see
the module ``_ROUTE_OBSERVATIONS`` notes and the task report for the discrepancy
record.
"""

from __future__ import annotations

import json

import pytest

from mechcad_harness.agents.models import (
    AgentAdapterExecutionOutcome,
    AgentAdapterIdentity,
    AgentAdapterProvenance,
    AgentAuthoredResponsePayload,
)
from mechcad_harness.application import ProductionApplication
from mechcad_harness.candidates import (
    CandidateIntegrityError,
    PromotionApplicationStatus,
)
from mechcad_harness.candidates.cad_realization import (
    CandidateCadIntegrityError,
    CandidateCadStageStatus,
)
from mechcad_harness.candidates.comparison import CandidateComparisonPolicy
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    PhysicalToM10V2BridgeCompiler,
)
from mechcad_harness.candidates.multi_joint_m10_evaluation import (
    CandidateMultiJointM10EvaluationRequestV2,
)
from mechcad_harness.candidates.promotion_models import (
    CandidateMultiJointPromotionRequestV2,
)
from pydantic import ValidationError

from test_candidate_decision_v2 import (
    _comparison_request,
    _decision_evaluation,
)
from test_candidate_multijoint_m10_v2 import (
    _candidate_cad_v2,
    _candidate_with_m13_multi_joint_authority,
    _multi_joint_scope,
    _raw_m10_result,
)
from test_candidate_trusted_semantic_verification import _at2_setup
from test_m12_revolute_drive_service import (
    DriveArchitecture,
    ShaftSupportGeometry,
    StaticOutputShaftDesignLoadCase,
    requirements,
    scalar,
    template,
)
from test_promotion_v2 import _promotion_family


# ---------------------------------------------------------------------------
# Literal transcription of the accepted Plan's T-P2.6 admission table.
# ---------------------------------------------------------------------------
T_P2_6_ROUTE_MATRIX = (
    {
        "route": "realize_and_evaluate_revolute_drive",
        "entrypoint": (
            "ProductionApplication.realize_and_evaluate_revolute_drive(request, policy, ...)"
        ),
        "request_context": "DIRECT_TYPED",
        "expected_current_behavior": (
            "positive new-family route: an inbound typed request@2 is trusted-bound, "
            "constructs candidate@2, contextually verifies request/candidate, passes "
            "typed-request currentness, then evaluates to revolute-drive-admissibility@2; "
            "an inbound request@1 keeps the legacy family"
        ),
        "actual_invocation": (
            "app.realize_and_evaluate_revolute_drive(request=request@2, policy=..., "
            "template_input=..., requirements=...)"
        ),
    },
    {
        "route": "realize_candidate_cad",
        "entrypoint": (
            "ProductionApplication.realize_candidate_cad(candidate, synthesis_request, "
            "synthesis_policy, cad_request)"
        ),
        "request_context": "DIRECT_TYPED",
        "expected_current_behavior": (
            "positive new-family route (T-P3): CandidateCadRealizationService "
            "dispatches candidate@2/request@3 through the shared lowering and "
            "returns a realization@2 stage outcome"
        ),
        "actual_invocation": (
            "app.realize_candidate_cad(candidate@2, synthesis_request@2, policy, "
            "cad_request@3)"
        ),
    },
    {
        "route": "evaluate_candidate",
        "entrypoint": (
            "ProductionApplication.evaluate_candidate(candidate, synthesis_request, "
            "synthesis_policy, ...)"
        ),
        "request_context": "DIRECT_TYPED",
        "expected_current_behavior": (
            "positive new-family route (T-P7.1): entry validation admits the "
            "candidate@2 chain, the CAD/evaluation services verify the typed "
            "request@2, and the route returns candidate-evaluation@2"
        ),
        "actual_invocation": (
            "app.evaluate_candidate(candidate@2, synthesis_request@2, policy, "
            "m12_3_result@2, cad_request@3, m10_request, scope, binding)"
        ),
    },
    {
        "route": "evaluate_candidate_multi_joint_m10",
        "entrypoint": (
            "ProductionApplication.evaluate_candidate_multi_joint_m10(candidate, "
            "synthesis_request, cad_realization, bridge, request)"
        ),
        "request_context": "DIRECT_TYPED",
        "expected_current_behavior": (
            "positive new-family route; candidate@2 requires the exact typed "
            "synthesis request@2 before build/execute"
        ),
        "actual_invocation": (
            "app.evaluate_candidate_multi_joint_m10(candidate@2, synthesis_request@2, "
            "cad_realization, bridge, m10_request)"
        ),
    },
    {
        "route": "select_candidate_multi_joint",
        "entrypoint": (
            "ProductionApplication.select_candidate_multi_joint(candidate, "
            "synthesis_request, cad_realization, bridge, request, evaluation, ...)"
        ),
        "request_context": "DIRECT_TYPED",
        "expected_current_behavior": (
            "positive new-family route; selection and replay revalidate "
            "candidate/request before typed-request currentness"
        ),
        "actual_invocation": (
            "app.select_candidate_multi_joint(candidate@2, synthesis_request@2, "
            "cad_realization, bridge, m10_request, m10_evaluation, selector, rationale)"
        ),
    },
    {
        "route": "compare_candidates",
        "entrypoint": (
            "ProductionApplication.compare_candidates(request, evaluations, *, "
            "synthesis_requests_by_candidate_hash)"
        ),
        "request_context": "RESOLVED_TYPED_PARENT",
        "expected_current_behavior": (
            "positive new-family route; a one-to-one typed request@2 mapping is "
            "required for every candidate@2 entry, otherwise reject"
        ),
        "actual_invocation": (
            "app.compare_candidates(comparison_request@2, entries, "
            "synthesis_requests_by_candidate_hash={candidate_hash: request@2})"
        ),
    },
    {
        "route": "select_candidate",
        "entrypoint": (
            "ProductionApplication.select_candidate(candidate, evaluation, ..., "
            "synthesis_request, comparison_entries, synthesis_requests_by_candidate_hash)"
        ),
        "request_context": "DIRECT_TYPED",
        "expected_current_behavior": (
            "positive new-family route; the selected candidate requires the exact "
            "typed synthesis request@2 (no bare evaluation/request hash admission)"
        ),
        "actual_invocation": (
            "app.select_candidate(candidate@2, evaluation@2, selector, rationale, "
            "comparison=..., comparison_entries=..., synthesis_request=request@2, "
            "synthesis_requests_by_candidate_hash=...)"
        ),
    },
    {
        "route": "compile_candidate_promotion",
        "entrypoint": "ProductionApplication.compile_candidate_promotion(request)",
        "request_context": "RESOLVED_TYPED_PARENT",
        "expected_current_behavior": (
            "reject-before-readiness: the composed promotion compiler is the legacy "
            "@1 compiler and rejects a CandidatePromotionRequest@2 parent"
        ),
        "actual_invocation": (
            "app.compile_candidate_promotion(CandidatePromotionRequest@2)"
        ),
    },
    {
        "route": "promote_selected_candidate",
        "entrypoint": (
            "ProductionApplication.promote_selected_candidate(request) / "
            "promote_selected_multi_joint_candidate(request)"
        ),
        "request_context": "RESOLVED_TYPED_PARENT",
        "expected_current_behavior": (
            "reject-before-promote: promotion application rejects a typed @2 parent "
            "without exact request@2/candidate@2 equality before promote"
        ),
        "actual_invocation": (
            "app.promote_selected_candidate(CandidatePromotionRequest@2) / "
            "app.promote_selected_multi_joint_candidate(CandidateMultiJointPromotionRequest@2)"
        ),
    },
)


# Observed on the current worktree.  Rows marked ACTIVATED call the real
# new-family route positively; rows marked REJECT_ONLY stop before legacy
# construction/execution as the Plan reserves for their owner phases.
_ROUTE_OBSERVATIONS = {
    "realize_and_evaluate_revolute_drive": "ACTIVATED",
    "realize_candidate_cad": "ACTIVATED",
    "evaluate_candidate": "ACTIVATED",
    "evaluate_candidate_multi_joint_m10": "ACTIVATED",
    "select_candidate_multi_joint": "ACTIVATED",
    "compare_candidates": "ACTIVATED",
    "select_candidate": "ACTIVATED",
    "compile_candidate_promotion": "REJECT_ONLY",
    "promote_selected_candidate": "REJECT_ONLY",
}


class _UninvokedAdapter:
    def __init__(self):
        self.identity = AgentAdapterIdentity(
            adapter_name="b3-route-matrix", adapter_version="1"
        )

    def invoke(self, request):  # pragma: no cover - never executed
        return AgentAdapterExecutionOutcome(
            authored_response=AgentAuthoredResponsePayload(
                status="succeeded",
                summary="unused",
                findings=(),
                issues=(),
                constraint_requests=(),
                change_proposals=(),
            ),
            provenance=AgentAdapterProvenance(
                adapter_name="b3-route-matrix",
                adapter_version="1",
                provider="test",
                transport="test",
            ),
        )


def _real_application(tmp_path, project_id: str) -> ProductionApplication:
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /requirements/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(json.dumps({"rules": [], "edges": []}), encoding="utf-8")
    return ProductionApplication.create(
        tmp_path,
        project_id,
        _UninvokedAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def _template_from_candidate(candidate):
    by_slot = {}
    for specification in candidate.component_specifications:
        slot = specification.source_identity.rsplit(":", 1)[-1].split("@", 1)[0]
        by_slot[slot] = specification
    return template(
        DriveArchitecture.DIRECT_DRIVE,
        motor_specification=by_slot["motor"],
        shaft_specification=by_slot["shaft"],
        bearing_a_specification=by_slot["bearing"],
        bearing_b_specification=by_slot["bearing"],
        hub_specification=by_slot["hub"],
        mount_specification=by_slot["mount"],
        driven_body_specification=by_slot["body"],
    )


def _policy_assumption_requirements():
    """Requirements whose scalars are policy assumptions.

    The semantic ``@2`` fixtures carry geometry identities in the canonical
    ``yagi_payload_carrier_requirements`` carrier rather than the M12-3 scalar
    records, so source-authority scalars cannot be asserted here.  Policy
    assumptions exercise the same production construction/verification/evaluation
    route without fabricating canonical scalar records.
    """
    return requirements(
        required_output_speed=scalar(100.0, "rpm", None),
        design_load_case=StaticOutputShaftDesignLoadCase(
            design_torque=scalar(10.0, "N*m", None),
            transverse_force_y=scalar(0.0, "N", None),
            transverse_force_z=scalar(0.0, "N", None),
        ),
        required_voltage=scalar(24.0, "V", None),
        safety_factor=scalar(2.0, "1", None),
        shaft_yield_strength=scalar(250.0, "MPa", None),
        shaft_support_geometry=ShaftSupportGeometry(
            support_a_x=scalar(0.0, "mm", None),
            support_b_x=scalar(100.0, "mm", None),
            load_plane_x=scalar(50.0, "mm", None),
        ),
    )


def _multi_joint_chain(tmp_path):
    state, manager, _, synthesis_request, policy, candidate = (
        _candidate_with_m13_multi_joint_authority(tmp_path)
    )
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    scope = _multi_joint_scope(bridge.model.model_id)
    return (
        state,
        manager,
        synthesis_request,
        policy,
        candidate,
        cad_request,
        cad_realization,
        bridge,
        scope,
    )


def test_t_p2_6_matrix_literally_covers_the_nine_entrypoints():
    assert len(T_P2_6_ROUTE_MATRIX) == 9
    routes = tuple(row["route"] for row in T_P2_6_ROUTE_MATRIX)
    assert routes == (
        "realize_and_evaluate_revolute_drive",
        "realize_candidate_cad",
        "evaluate_candidate",
        "evaluate_candidate_multi_joint_m10",
        "select_candidate_multi_joint",
        "compare_candidates",
        "select_candidate",
        "compile_candidate_promotion",
        "promote_selected_candidate",
    )
    for row in T_P2_6_ROUTE_MATRIX:
        assert row["request_context"] in {"DIRECT_TYPED", "RESOLVED_TYPED_PARENT"}
        assert row["entrypoint"]
        assert row["expected_current_behavior"]
        assert row["actual_invocation"]
    assert set(_ROUTE_OBSERVATIONS) == set(routes)


def test_t_p2_6_row_1_realize_and_evaluate_revolute_drive_admits_request_at2(tmp_path):
    _, _, _, _, bound_request, policy, candidate = _at2_setup(tmp_path)
    application = _real_application(tmp_path, "PRJ-M12")

    outcome = application.realize_and_evaluate_revolute_drive(
        request=bound_request,
        policy=policy,
        template_input=_template_from_candidate(candidate),
        requirements=_policy_assumption_requirements(),
    )

    assert outcome.construction.candidate is not None
    assert (
        outcome.construction.candidate.schema_version
        == "mechanical-design-candidate@2"
    )
    assert outcome.evaluation is not None
    assert outcome.evaluation.schema_version == "revolute-drive-admissibility@2"
    assert outcome.evaluation.candidate_hash == outcome.construction.candidate.candidate_hash


def test_t_p2_6_row_2_realize_candidate_cad_admits_candidate_at2(tmp_path):
    from test_candidate_cad_request_v3 import (
        _INSTANCE_SLOTS,
        _mapping_at2,
        _request_at3,
    )

    _, _manager, _, _, synthesis_request, policy, candidate = _at2_setup(tmp_path)
    mappings = tuple(
        _mapping_at2(candidate.candidate_hash, instance_id, slot)
        for instance_id, slot in _INSTANCE_SLOTS
    )
    cad_request = _request_at3(
        candidate,
        synthesis_request.semantic_source_binding_hash,
        mappings=mappings,
    )
    application = _real_application(tmp_path, candidate.source_binding.project_id)

    # Owner task T-P3 activates the positive candidate@2 route: the CAD service
    # dispatches request@3 through the shared lowering and produces a
    # realization@2 instead of rejecting at the legacy request-family boundary.
    stage = application.realize_candidate_cad(
        candidate, synthesis_request, policy, cad_request
    )
    assert stage.schema_version == "candidate-cad-stage-outcome@2"
    assert stage.status is CandidateCadStageStatus.SUCCESS
    assert stage.realization.schema_version == "candidate-cad-realization@2"


def test_t_p2_6_row_3_evaluate_candidate_admits_candidate_at2(tmp_path):
    from test_candidate_comparison_selection_provenance_v2 import (
        _published_v2_parents,
    )

    # Owner task T-P7.1 activates the positive evaluation@2 route.  Reuse the
    # published-parent fixture so the candidate CAD/evaluation evidence the
    # evaluation-provenance publication needs is present.
    records, _service, _, _ = _published_v2_parents(tmp_path)
    application = _real_application(
        tmp_path, records["candidate"].source_binding.project_id
    )

    evaluation = application.evaluate_candidate(
        records["candidate"],
        records["synthesis_request"],
        records["synthesis_policy"],
        records["admissibility"],
        records["cad_request"],
        records["m10_request"],
        records["scope"],
        records["binding"],
    )
    assert evaluation.schema_version == "candidate-evaluation@2"
    assert evaluation.candidate_hash == records["candidate"].candidate_hash


def test_t_p2_6_row_4_evaluate_candidate_multi_joint_m10_admits_typed_request_at2(
    tmp_path, monkeypatch
):
    (
        _state,
        _manager,
        synthesis_request,
        _policy,
        candidate,
        cad_request,
        cad_realization,
        bridge,
        scope,
    ) = _multi_joint_chain(tmp_path)
    application = _real_application(tmp_path, candidate.source_binding.project_id)
    monkeypatch.setattr(
        application.candidate_multi_joint_m10_evaluation_service,
        "analyze_multi_joint_collision_sweep_v2",
        _raw_m10_result,
    )
    request = application.candidate_multi_joint_m10_evaluation_service.build_request(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        scope,
        cad_request=cad_request,
    )

    evaluation = application.evaluate_candidate_multi_joint_m10(
        candidate, synthesis_request, cad_realization, bridge, request
    )
    assert evaluation.schema_version == "candidate-multi-joint-m10-evaluation@2"
    assert evaluation.candidate_hash == candidate.candidate_hash

    with pytest.raises(CandidateIntegrityError, match="synthesis request@2"):
        application.evaluate_candidate_multi_joint_m10(
            candidate, None, cad_realization, bridge, request
        )


def test_t_p2_6_row_5_select_candidate_multi_joint_admits_typed_request_at2(
    tmp_path, monkeypatch
):
    (
        _state,
        _manager,
        synthesis_request,
        _policy,
        candidate,
        cad_request,
        cad_realization,
        bridge,
        scope,
    ) = _multi_joint_chain(tmp_path)
    application = _real_application(tmp_path, candidate.source_binding.project_id)
    monkeypatch.setattr(
        application.candidate_multi_joint_m10_evaluation_service,
        "analyze_multi_joint_collision_sweep_v2",
        _raw_m10_result,
    )
    # The selection replay re-executes the sweep through the application's
    # composed entrypoint; swap the live FreeCAD provider for the same
    # deterministic provider used by the direct evaluation.
    monkeypatch.setattr(
        application, "_execute_candidate_v2_sweep", _raw_m10_result
    )
    request = application.candidate_multi_joint_m10_evaluation_service.build_request(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        scope,
        cad_request=cad_request,
    )
    evaluation = application.evaluate_candidate_multi_joint_m10(
        candidate, synthesis_request, cad_realization, bridge, request
    )

    selection = application.select_candidate_multi_joint(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        request,
        evaluation,
        "b3-route-matrix-selector@1",
        "typed request@2 multi-joint selection",
    )
    assert selection.schema_version == "candidate-multi-joint-selection@2"
    assert selection.candidate_hash == candidate.candidate_hash

    with pytest.raises(
        (CandidateIntegrityError, ValueError, TypeError),
        match="synthesis request@2",
    ):
        application.select_candidate_multi_joint(
            candidate,
            None,
            cad_realization,
            bridge,
            request,
            evaluation,
            "b3-route-matrix-selector@1",
            "missing typed request@2",
        )


def test_t_p2_6_row_6_compare_candidates_resolves_typed_request_at2_mapping(tmp_path):
    from test_candidate_comparison_selection_provenance_v2 import (
        _published_v2_parents,
    )

    records, _service, _, _ = _published_v2_parents(tmp_path)
    candidate = records["candidate"]
    application = _real_application(
        tmp_path, candidate.source_binding.project_id
    )
    policy = CandidateComparisonPolicy()
    request = _comparison_request((records,), policy)
    entries = ((candidate, records["evaluation"]),)
    mapping = {candidate.candidate_hash: records["synthesis_request"]}

    comparison = application.compare_candidates(
        request, entries, synthesis_requests_by_candidate_hash=mapping
    )
    assert comparison.schema_version == "candidate-comparison-result@2"

    with pytest.raises(ValueError, match="request@2 mapping"):
        application.compare_candidates(request, entries)


def test_t_p2_6_row_7_select_candidate_requires_typed_request_at2(tmp_path):
    from test_candidate_comparison_selection_provenance_v2 import (
        _published_v2_parents,
    )

    records, _service, _, _ = _published_v2_parents(tmp_path)
    candidate = records["candidate"]
    application = _real_application(
        tmp_path, candidate.source_binding.project_id
    )
    policy = CandidateComparisonPolicy()
    request = _comparison_request((records,), policy)
    entries = ((candidate, records["evaluation"]),)
    mapping = {candidate.candidate_hash: records["synthesis_request"]}
    comparison = application.compare_candidates(
        request, entries, synthesis_requests_by_candidate_hash=mapping
    )

    selection = application.select_candidate(
        candidate,
        records["evaluation"],
        "b3-route-matrix-selector@1",
        "typed request@2 selection",
        comparison=comparison,
        comparison_entries=entries,
        synthesis_request=records["synthesis_request"],
        synthesis_requests_by_candidate_hash=mapping,
    )
    assert selection.schema_version == "candidate-selection@2"
    assert selection.candidate_hash == candidate.candidate_hash

    with pytest.raises((CandidateIntegrityError, ValueError)):
        application.select_candidate(
            candidate,
            records["evaluation"],
            "b3-route-matrix-selector@1",
            "missing typed request@2",
        )


def test_t_p2_6_row_8_compile_candidate_promotion_rejects_promotion_request_at2(
    tmp_path,
):
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    family = _promotion_family(tmp_path, base)
    request = family["request"]
    assert request.schema_version == "candidate-promotion-request@2"
    application = _real_application(tmp_path, request.project_id)

    with pytest.raises(ValueError, match="promotion request integrity failure"):
        application.compile_candidate_promotion(request)


def test_t_p2_6_row_9_promote_routes_reject_typed_at2_parent_before_promote(
    tmp_path,
):
    base = _candidate_with_m13_multi_joint_authority(tmp_path)
    family = _promotion_family(tmp_path, base)
    request = family["request"]
    application = _real_application(tmp_path, request.project_id)

    # Promotion@2 is admitted without a legacy @1 downgrade; an unresolved
    # parent fails closed before canonical mutation via the typed receipt.
    result = application.promote_selected_candidate(request)
    assert result.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert result.error
    assert result.decision_artifact_id is None
    assert application.load_state().state.physical_mechanisms == []

    mj_request = CandidateMultiJointPromotionRequestV2.model_construct(
        project_id=request.project_id
    )
    mj_result = application.promote_selected_multi_joint_candidate(mj_request)
    assert mj_result.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert mj_result.error
    assert mj_result.decision_artifact_id is None
    assert application.load_state().state.physical_mechanisms == []


def test_t_p2_6_multi_joint_m10_request_type_is_exact_v2(tmp_path):
    """Row 4/5 parent is a real ``CandidateMultiJointM10EvaluationRequestV2``."""
    (
        _state,
        _manager,
        synthesis_request,
        _policy,
        candidate,
        cad_request,
        cad_realization,
        bridge,
        scope,
    ) = _multi_joint_chain(tmp_path)
    application = _real_application(tmp_path, candidate.source_binding.project_id)
    request = application.candidate_multi_joint_m10_evaluation_service.build_request(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        scope,
        cad_request=cad_request,
    )
    assert type(request) is CandidateMultiJointM10EvaluationRequestV2
    assert request.schema_version == "candidate-multi-joint-m10-evaluation-request@2"
