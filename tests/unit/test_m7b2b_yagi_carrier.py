import pytest

from mechcad_harness.engineering.keys import SupportedConstraintKey
from mechcad_harness.engineering.values import YagiPayloadCarrierRequirementsValue
from mechcad_harness.yagi_carrier import (
    YAGI_CARRIER_LAYOUT_SYNTHESIS_VERSION,
    NominalLayoutStatus,
    YagiCarrierStatus,
    YagiCarrierSynthesisService,
    build_yagi_carrier_proposal,
    carrier_authority_hash,
    envelope_pair_interference,
    synthesize_yagi_carrier_layout,
)


def envelopes():
    values = (
        ("ANTENNA_ENVELOPE_0400", "400-470 MHz", 850, 400, 60, 0.8, 0.08),
        ("ANTENNA_ENVELOPE_0600", "550-700 MHz", 700, 320, 60, 0.7, 0.06),
        ("ANTENNA_ENVELOPE_1200", "1100-1300 MHz", 600, 150, 60, 0.6, 0.04),
        ("ANTENNA_ENVELOPE_3300", "3.3-3.8 GHz", 500, 120, 60, 0.5, 0.03),
        ("ANTENNA_ENVELOPE_5800", "5.7-5.9 GHz", 300, 150, 80, 0.5, 0.03),
    )
    return tuple(
        {
            "semantic_id": identity,
            "frequency_class": frequency,
            "length_mm": length,
            "span_mm": span,
            "depth_mm": depth,
            "placeholder_mass_kg": mass,
            "placeholder_wind_area_m2": area,
        }
        for identity, frequency, length, span, depth, mass, area in values
    )


def requirements(**overrides):
    payload = {
        "kind": "yagi.payload_carrier_requirements",
        "frequency_families_ghz": (0.4, 0.6, 1.2, 3.3, 5.8),
        "minimum_antenna_count": 2,
        "maximum_antenna_count": 3,
        "maximum_rotating_payload_kg": 5.0,
        "envelopes": envelopes(),
        "nominal_spacing_mm": 150,
        "adjustable_spacing_required": True,
        "recommended_lateral_adjustment_mm": 220,
        "preferred_carrier_length_mm": 500,
        "required_fore_aft_travel_mm": 75,
        "preferred_fore_aft_travel_mm": 100,
        "preferred_com_offset_mm": 20,
        "acceptable_com_offset_mm": 30,
        "collision_resolution_strategies": ("orientation", "vertical_staggering", "increased_spacing", "longitudinal_staggering"),
        "maximum_collision_envelope_mm": (850, 400, 80),
        "representative_payload_mass_kg": 2.1,
        "el_collision_sweep_degrees": (0, 15, 30, 45, 60, 75, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360),
        "el_axis_height_search_range_mm": (180, 300),
        "az_continuous_multiturn": True,
        "az_target_revolution_time_s": 12,
        "interchangeable_adjustable_mounts_required": True,
        "boom_compatibility_targets": ("square 15 x 15 mm", "square 20 x 20 mm", "rectangular up to 25 x 20 mm", "round diameter 15 ... 30 mm"),
        "provenance": "USER-SUPPLIED-M7B2A-SPEC",
    }
    payload.update(overrides)
    return YagiPayloadCarrierRequirementsValue(**payload)


def state_with_authority(tmp_path):
    from datetime import datetime, timezone

    from mechcad_harness.agents.constraint_requests import (
        AgentConstraintRequestDraft,
        ConstraintRequestMaterializer,
        ConstraintRequestStore,
    )
    from mechcad_harness.agents.constraint_resolution import (
        ConstraintResolutionAnswer,
        ConstraintResolutionBatchCommand,
        ConstraintResolutionMaterializer,
        ConstraintResolutionStore,
        YagiPayloadCarrierRequirementsAnswer,
    )
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.models import DesignState, Requirement
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    manager.create_project(
        "PRJ-CARRIER",
        DesignState(
            id="DES-CARRIER",
            revision=1,
            requirements=[Requirement(id="REQ-YAGI-PAYLOAD-CARRIER-REQUIREMENTS", name="Yagi payload authority", description="Yagi payload authority")],
        ),
    )
    current = manager._read_current("PRJ-CARRIER")
    request_store = ConstraintRequestStore(tmp_path)
    request = ConstraintRequestMaterializer(request_store).materialize(
        project_id="PRJ-CARRIER",
        run_id="RUN-CARRIER",
        task_id="TASK",
        agent_name="mechcad-yagi-carrier",
        agent_version="m7b2b",
        source_invocation_id="INV",
        source_agent_result_id="RES",
        engineering_scope_id="yagi-carrier",
        bound_revision=1,
        bound_state_hash=current["state_hash"],
        source_created_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        state=manager.load_current_state("PRJ-CARRIER"),
        drafts=(AgentConstraintRequestDraft(key=SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS, description="Resolve payload authority", rationale="M7B-2A spec"),),
    )[0]
    command = ConstraintResolutionBatchCommand(
        command_id="CMD-CARRIER",
        project_id="PRJ-CARRIER",
        engineering_scope_id="yagi-carrier",
        source_revision=1,
        source_state_hash=current["state_hash"],
        answers=(ConstraintResolutionAnswer(request_id=request.request.id, answer=YagiPayloadCarrierRequirementsAnswer(**requirements().model_dump(mode="json"))),),
        resolver_type="user-supplied-project-spec",
        resolver_id="user",
        received_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    materialized = ConstraintResolutionMaterializer(request_store, ConstraintResolutionStore(tmp_path)).materialize_batch(command, run_id="RUN-CARRIER")
    ConstraintResolutionApplicationService(
        manager,
        ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])),
        request_store,
    ).apply_batch(materialized, run_id="RUN-CARRIER")
    return manager


def test_not_ready_without_authority():
    from mechcad_harness.models import DesignState

    result = YagiCarrierSynthesisService().synthesize(DesignState(id="D", revision=1), source_revision=1, source_state_hash="sha256:state")
    assert result.status is YagiCarrierStatus.NOT_READY
    assert result.missing_authority == "yagi.payload_carrier_requirements"
    assert result.spec is None
    assert result.design_variables == {}
    assert result.proposal is None


def test_deterministic_carrier_length_rule_honors_preferred_without_hardcoding():
    result = synthesize_yagi_carrier_layout(requirements())
    assert result.status is YagiCarrierStatus.SUCCESS
    assert result.minimum_required_carrier_length_mm == 440
    assert result.spec.carrier_length_mm == 500
    wider = synthesize_yagi_carrier_layout(requirements(recommended_lateral_adjustment_mm=300))
    assert wider.minimum_required_carrier_length_mm == 600
    assert wider.spec.carrier_length_mm == 600


def test_nominal_two_and_three_antenna_coordinates():
    spec = synthesize_yagi_carrier_layout(requirements()).spec
    assert spec.nominal_two_antenna_y_mm == (-75, 75)
    assert spec.nominal_three_antenna_y_mm == (-150, 0, 150)


def test_lateral_adjustment_region_is_a_range_not_fixed_holes():
    spec = synthesize_yagi_carrier_layout(requirements()).spec
    assert (spec.lateral_adjustment_min_y_mm, spec.lateral_adjustment_max_y_mm) == (-220, 220)
    assert spec.adjustable_mounting == "continuous_lateral_travel_region"


def test_fore_aft_required_and_preferred_travel_are_both_preserved():
    spec = synthesize_yagi_carrier_layout(requirements()).spec
    assert spec.required_fore_aft_travel_mm == 75
    assert spec.preferred_fore_aft_travel_mm == 100
    assert spec.final_antenna_x_positions_selected is False


def test_carrier_frame_and_structural_status():
    spec = synthesize_yagi_carrier_layout(requirements()).spec
    assert spec.carrier_frame == "carrier-center origin; +X boom/fore-aft; +Y lateral spacing; +Z right-handed"
    assert spec.structural_verification == "not_verified"
    assert spec.profile_structural_status == "not_structurally_selected"


def test_synthesis_hash_is_deterministic_and_authority_sensitive():
    first = synthesize_yagi_carrier_layout(requirements())
    second = synthesize_yagi_carrier_layout(requirements())
    assert first.synthesis_hash == second.synthesis_hash
    assert first.synthesis_version == YAGI_CARRIER_LAYOUT_SYNTHESIS_VERSION
    changed = synthesize_yagi_carrier_layout(requirements(preferred_fore_aft_travel_mm=110))
    assert changed.synthesis_hash != first.synthesis_hash
    assert changed.authority_hash != first.authority_hash
    assert carrier_authority_hash(requirements()) == first.authority_hash


def test_nominal_spacing_is_not_assumed_clear_and_identifies_exact_pair():
    result = synthesize_yagi_carrier_layout(requirements())
    assert result.nominal_layout_status is NominalLayoutStatus.COLLIDES
    assert ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600") in result.nominal_colliding_pairs
    assert result.status is YagiCarrierStatus.SUCCESS


def test_actual_envelope_geometry_determines_collision():
    clear = envelope_pair_interference((0.0, -150.0, 0.0), (600, 150, 60), (0.0, 150.0, 0.0), (600, 150, 60))
    overlapping = envelope_pair_interference((0.0, -150.0, 0.0), (850, 400, 60), (0.0, 0.0, 0.0), (700, 320, 60))
    assert clear is False
    assert overlapping is True


def test_collision_does_not_invalidate_adjustable_architecture():
    result = synthesize_yagi_carrier_layout(requirements())
    assert result.lateral_adjustment_available is True
    assert result.two_antenna_lateral_resolution_possible is True
    assert result.collision_resolution_strategies_selected == ()
    assert set(result.collision_resolution_strategies_available) == {"orientation", "vertical_staggering", "increased_spacing", "longitudinal_staggering"}


def test_three_antenna_lateral_only_resolution_is_reported_not_solved():
    result = synthesize_yagi_carrier_layout(requirements())
    assert result.three_antenna_lateral_resolution_possible is False
    assert result.required_three_antenna_lateral_span_mm == pytest.approx(595)


def test_state_backed_synthesis_uses_authority_and_emits_proposal_only(tmp_path):
    manager = state_with_authority(tmp_path)
    pointer = manager._read_current("PRJ-CARRIER")
    state = manager.load_current_state("PRJ-CARRIER")
    result = YagiCarrierSynthesisService().synthesize(state, source_revision=pointer["revision"], source_state_hash=pointer["state_hash"], project_id="PRJ-CARRIER")
    assert result.status is YagiCarrierStatus.SUCCESS
    assert result.authority_hash == carrier_authority_hash(requirements())
    assert result.spec.carrier_length_mm == 500
    proposal = result.proposal
    assert proposal.base_revision == pointer["revision"]
    assert proposal.base_state_hash == pointer["state_hash"]
    assert proposal.actor == "mechcad-yagi-carrier"
    assert [operation.path for operation in proposal.operations] == ["/yagi_carriers/preliminary_yagi_carrier"]
    assert manager.load_current_state("PRJ-CARRIER").yagi_carriers == []
    assert state.yagi_carriers == []


def test_proposal_requires_success():
    from mechcad_harness.models import DesignState

    not_ready = YagiCarrierSynthesisService().synthesize(DesignState(id="D", revision=1), source_revision=1, source_state_hash="sha256:state")
    with pytest.raises(ValueError, match="success"):
        build_yagi_carrier_proposal(not_ready, project_id="PRJ", source_revision=1, source_state_hash="sha256:state")


def test_carrier_path_ownership_is_enforced():
    from mechcad_harness.changes import OwnershipPolicy
    from mechcad_harness.changes.errors import OwnershipViolationError

    policy = OwnershipPolicy.from_file("config/ownership.yaml")
    assert policy.owner_for("/yagi_carriers/preliminary_yagi_carrier") == "mechcad-yagi-carrier"
    with pytest.raises(OwnershipViolationError):
        policy.check("/yagi_carriers/preliminary_yagi_carrier", "mechcad-azimuth-synthesis")


def test_carrier_width_is_not_forced_to_cover_element_span():
    result = synthesize_yagi_carrier_layout(requirements())
    assert result.spec.carrier_length_mm < 850
    assert result.maximum_antenna_element_span_mm == 400


def test_cad_capability_audit_reports_missing_through_slot_operation():
    from mechcad_harness.yagi_carrier import carrier_cad_capability_audit

    audit = carrier_cad_capability_audit()
    assert audit.supported is False
    assert audit.missing_capability == "through_slot"
    assert audit.marker == "M7B2B_CAD_OPERATION_CAPABILITY_REQUIRED"
    assert "rectangular_pocket" in audit.available_operations
    assert "through_slot" not in audit.available_operations


def test_capability_audit_refuses_pocket_substitution_for_slot():
    from mechcad_harness.yagi_carrier import carrier_cad_capability_audit

    audit = carrier_cad_capability_audit()
    assert audit.pocket_substitution_allowed is False
    assert "blind" in audit.rationale


def test_no_carrier_cad_program_is_compiled_without_capability():
    from mechcad_harness.yagi_carrier import compile_preliminary_yagi_carrier

    result = synthesize_yagi_carrier_layout(requirements())
    with pytest.raises(ValueError, match="M7B2B_CAD_OPERATION_CAPABILITY_REQUIRED"):
        compile_preliminary_yagi_carrier(result.spec)
