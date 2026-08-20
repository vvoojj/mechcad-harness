import pytest

from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer
from mechcad_harness.agents.constraint_resolution import (
    YagiPayloadCarrierRequirementsAnswer,
    canonical_value_for_answer,
)
from mechcad_harness.engineering.keys import SupportedConstraintKey
from mechcad_harness.engineering.values import YagiPayloadCarrierRequirementsValue


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


def test_exact_key_and_anchor():
    key = SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS
    assert key.value == "yagi.payload_carrier_requirements"
    assert ConstraintRequestMaterializer.anchor_for(key) == ("requirement", "REQ-YAGI-PAYLOAD-CARRIER-REQUIREMENTS")


def test_hard_payload_and_count_semantics():
    value = requirements()
    assert (value.minimum_antenna_count, value.maximum_antenna_count) == (2, 3)
    assert value.maximum_rotating_payload_kg == 5.0
    with pytest.raises(ValueError):
        requirements(maximum_rotating_payload_kg=4.9)


def test_all_envelopes_preserve_collision_and_placeholder_semantics():
    value = requirements()
    assert [envelope.semantic_id for envelope in value.envelopes] == [
        "ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200", "ANTENNA_ENVELOPE_3300", "ANTENNA_ENVELOPE_5800"
    ]
    assert all(envelope.envelope_semantics == "collision_envelope" for envelope in value.envelopes)
    assert all(envelope.mass_semantics == "engineering_placeholder" for envelope in value.envelopes)
    assert all(envelope.wind_area_semantics == "engineering_placeholder" for envelope in value.envelopes)


def test_spacing_adjustment_and_nominal_positions_are_explicit():
    value = requirements()
    assert value.nominal_spacing_mm == 150
    assert value.adjustable_spacing_required is True
    assert value.recommended_lateral_adjustment_mm == 220
    assert (-(value.nominal_spacing_mm / 2), value.nominal_spacing_mm / 2) == (-75, 75)
    assert (-value.nominal_spacing_mm, 0, value.nominal_spacing_mm) == (-150, 0, 150)


def test_balance_load_and_carrier_semantics_remain_distinct():
    value = requirements()
    assert value.required_fore_aft_travel_mm == 75
    assert value.preferred_fore_aft_travel_mm == 100
    assert value.preferred_com_offset_mm == 20
    assert value.acceptable_com_offset_mm == 30
    assert value.representative_payload_mass_kg == 2.1
    assert value.maximum_rotating_payload_kg == 5.0
    assert value.final_carrier_cross_section_status == "not_structurally_accepted"
    assert value.preliminary_profile_guidance == ("2040",)
    assert value.preferred_profile_guidance == "4040"


def test_parametric_and_unresolved_values_are_not_frozen():
    value = requirements()
    assert value.el_axis_height_semantics == "parametric"
    assert value.el_axis_height_search_range_mm == (180, 300)
    assert value.wind_speed_status == "not_frozen"
    assert value.exact_yagi_products_status == "not_frozen"
    assert value.exact_boom_sections_status == "not_frozen"
    assert value.polarization_status == "not_frozen"
    assert value.cable_routing_status == "not_frozen"


def test_resolution_answer_round_trip_preserves_semantics_and_hash_inputs():
    key = SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS
    answer = YagiPayloadCarrierRequirementsAnswer(**requirements().model_dump(mode="json"))
    canonical = canonical_value_for_answer(key, answer)
    assert canonical == requirements()
    changed = requirements(preferred_fore_aft_travel_mm=110)
    assert canonical.model_dump(mode="json") != changed.model_dump(mode="json")


def test_wrong_type_is_rejected():
    from mechcad_harness.agents.constraint_resolution import PackagingEnvelopeAnswer

    with pytest.raises(ValueError, match="answer type"):
        canonical_value_for_answer(SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS, PackagingEnvelopeAnswer(max_length_mm=1, max_width_mm=1, max_height_mm=1, mounting_description="x"))


def test_collision_strategy_is_allowed_future_semantics_not_a_selected_strategy():
    assert set(requirements().collision_resolution_strategies) == {"orientation", "vertical_staggering", "increased_spacing", "longitudinal_staggering"}


def test_yagi_authority_uses_m6b_resolution_application_and_persisted_reload(tmp_path):
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
    )
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.models import Constraint, DesignState, Requirement
    from mechcad_harness.state import StateManager

    key = SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS
    manager = StateManager(tmp_path)
    manager.create_project(
        "PRJ-YAGI",
        DesignState(
            id="DES-YAGI",
            revision=1,
            requirements=[Requirement(id="REQ-YAGI-PAYLOAD-CARRIER-REQUIREMENTS", name="Yagi payload and carrier authority", description="Yagi payload and carrier authority")],
            constraints=[Constraint(id="CON-AZIMUTH-DRIVE-MOUNT-INTERFACE", name="unrelated", expression="unrelated")],
        ),
    )
    current = manager._read_current("PRJ-YAGI")
    request_store = ConstraintRequestStore(tmp_path)
    request = ConstraintRequestMaterializer(request_store).materialize(
        project_id="PRJ-YAGI",
        run_id="RUN-YAGI",
        task_id="TASK-YAGI",
        agent_name="mechcad-yagi-carrier",
        agent_version="m7b2a",
        source_invocation_id="INV-YAGI",
        source_agent_result_id="RESULT-YAGI",
        engineering_scope_id="yagi-carrier",
        bound_revision=1,
        bound_state_hash=current["state_hash"],
        source_created_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        state=manager.load_current_state("PRJ-YAGI"),
        drafts=(AgentConstraintRequestDraft(key=key, description="Resolve Yagi payload/carrier requirements", rationale="User-supplied M7B-2A specification"),),
    )[0]
    answer = ConstraintResolutionAnswer(
        request_id=request.request.id,
        answer=YagiPayloadCarrierRequirementsAnswer(**requirements().model_dump(mode="json")),
    )
    command = ConstraintResolutionBatchCommand(
        command_id="CMD-YAGI",
        project_id="PRJ-YAGI",
        engineering_scope_id="yagi-carrier",
        source_revision=1,
        source_state_hash=current["state_hash"],
        answers=(answer,),
        resolver_type="user-supplied-project-spec",
        resolver_id="user",
        received_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    materialized = ConstraintResolutionMaterializer(request_store, ConstraintResolutionStore(tmp_path)).materialize_batch(command, run_id="RUN-YAGI")
    application = ConstraintResolutionApplicationService(
        manager,
        ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])),
        request_store,
    )
    applied = application.apply_batch(materialized, run_id="RUN-YAGI")
    assert applied.new_revision == 2
    reloaded = manager.load_current_state("PRJ-YAGI")
    assert reloaded.revision == 2
    assert len(reloaded.authoritative_parameters) == 1
    parameter = reloaded.authoritative_parameters[0]
    assert parameter.key is key
    assert parameter.anchor.model_dump() == {"kind": "requirement", "id": "REQ-YAGI-PAYLOAD-CARRIER-REQUIREMENTS"}
    assert parameter.value.provenance == "USER-SUPPLIED-M7B2A-SPEC"
    assert ConstraintRequestMaterializer().is_satisfied(key, reloaded, engineering_scope_id="yagi-carrier")
