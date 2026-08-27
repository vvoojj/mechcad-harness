from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from mechcad_harness.candidates import (
    CandidateDesignVariable,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    ComponentSpecificationSnapshot,
)
from mechcad_harness.models import DesignState
from mechcad_harness.revolute_drive import (
    DriveArchitecture,
    InputProvenanceKind,
    RevoluteDriveAdmissibilityResult,
    ShaftSupportGeometry,
)
from mechcad_harness.revolute_drive.service import _hash_source_binding
from mechcad_harness.state.hashing import canonical_json

from tests.unit.test_m12_revolute_drive_service import (
    _P_EFFICIENCY,
    _P_LOAD_PLANE,
    _P_SPUR_SPEED,
    _P_SPEED,
    _P_SUPPORT_A,
    _P_SUPPORT_B,
    _P_YIELD,
    _SERVICE,
    _bound_binding,
    _state,
    gear_specification,
    policy_for,
    request,
    requirements,
    scalar,
    spur_requirements,
    template,
    motor_specification,
)


def evaluate(
    architecture: DriveArchitecture,
    *,
    template_input=None,
    engineering=None,
    synthesis_request=None,
    synthesis_policy=None,
    state: DesignState | None = None,
):
    source_state = _state() if state is None else state
    if engineering is None:
        engineering = spur_requirements() if architecture is DriveArchitecture.EXTERNAL_SPUR_REDUCTION else requirements()
    if synthesis_request is None:
        source_values = {
            path: (scalar_value.value, scalar_value.unit)
            for path, scalar_value in (
                (engineering.required_output_speed.source_path, engineering.required_output_speed),
                ("/yagi_payload_carrier_requirements/2", engineering.design_load_case.design_torque),
                ("/yagi_payload_carrier_requirements/3", engineering.efficiency),
                ("/yagi_payload_carrier_requirements/4", engineering.required_peak_torque),
                ("/yagi_payload_carrier_requirements/5", engineering.safety_factor),
                ("/yagi_payload_carrier_requirements/6", engineering.shaft_yield_strength),
                ("/yagi_payload_carrier_requirements/7", engineering.required_voltage),
                ("/yagi_payload_carrier_requirements/8", None if engineering.shaft_support_geometry is None else engineering.shaft_support_geometry.support_a_x),
                ("/yagi_payload_carrier_requirements/9", None if engineering.shaft_support_geometry is None else engineering.shaft_support_geometry.support_b_x),
                ("/yagi_payload_carrier_requirements/10", None if engineering.shaft_support_geometry is None else engineering.shaft_support_geometry.load_plane_x),
                ("/yagi_payload_carrier_requirements/11", engineering.design_load_case.transverse_force_y),
                ("/yagi_payload_carrier_requirements/12", engineering.design_load_case.transverse_force_z),
            )
            if scalar_value is not None and scalar_value.provenance is InputProvenanceKind.SOURCE_AUTHORITY
        }
        synthesis_request = request(
            architecture,
            state=source_state,
            source_values=source_values,
        )
    template_input = template_input or template(architecture)
    selected_diameter = next(
        (
            variable.value
            for variable in template_input.design_variables
            if variable.name == "selected-output-shaft-diameter"
        ),
        12.0,
    )
    synthesis_policy = synthesis_policy or policy_for(
        architecture,
        selected_diameter=selected_diameter,
    )
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template_input,
    ).candidate
    assert candidate is not None
    return _SERVICE.evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        engineering,
        source_state=source_state,
    )


def test_semantically_equal_replays_produce_identical_result_hashes():
    first = evaluate(DriveArchitecture.DIRECT_DRIVE)
    second = evaluate(DriveArchitecture.DIRECT_DRIVE)

    assert second == first
    assert second.result_hash == first.result_hash


def test_result_hash_changes_for_each_consumed_direct_drive_input_change():
    baseline = evaluate(DriveArchitecture.DIRECT_DRIVE)
    variants = {
        "motor continuous torque property value": evaluate(
            DriveArchitecture.DIRECT_DRIVE,
            template_input=template(
                DriveArchitecture.DIRECT_DRIVE,
                motor_specification=motor_specification(continuous=11.0),
            ),
        ),
        "shaft yield strength": evaluate(
            DriveArchitecture.DIRECT_DRIVE,
            engineering=requirements(shaft_yield_strength=scalar(200.0, "MPa", _P_YIELD)),
        ),
        "shaft diameter design variable": evaluate(
            DriveArchitecture.DIRECT_DRIVE,
            template_input=template(
                DriveArchitecture.DIRECT_DRIVE,
                design_variables=(
                    CandidateDesignVariable(
                        name="selected-output-shaft-diameter",
                        value=13.0,
                    ),
                ),
            ),
        ),
        "support geometry coordinate": evaluate(
            DriveArchitecture.DIRECT_DRIVE,
            engineering=requirements(
                shaft_support_geometry=ShaftSupportGeometry(
                    support_a_x=scalar(5.0, "mm", _P_SUPPORT_A),
                    support_b_x=scalar(100.0, "mm", _P_SUPPORT_B),
                    load_plane_x=scalar(50.0, "mm", _P_LOAD_PLANE),
                ),
            ),
        ),
        "requirements value": evaluate(
            DriveArchitecture.DIRECT_DRIVE,
            engineering=requirements(required_output_speed=scalar(90.0, "rpm", _P_SPEED)),
        ),
    }

    for label, changed in variants.items():
        assert changed.result_hash != baseline.result_hash, label


def test_changed_consumed_motor_property_changes_its_binding_identity():
    baseline = evaluate(DriveArchitecture.DIRECT_DRIVE)
    changed = evaluate(
        DriveArchitecture.DIRECT_DRIVE,
        template_input=template(
            DriveArchitecture.DIRECT_DRIVE,
            motor_specification=motor_specification(continuous=11.0),
        ),
    )

    def binding_for(result, property_key):
        return next(binding for binding in result.consumed_property_bindings if binding.property_key == property_key)

    baseline_binding = binding_for(baseline, "motor.continuous_torque_nm")
    changed_binding = binding_for(changed, "motor.continuous_torque_nm")
    assert changed_binding.specification_hash != baseline_binding.specification_hash
    assert changed_binding.property_hash != baseline_binding.property_hash


def test_result_hash_changes_for_gear_efficiency_value_and_efficiency_provenance_changes():
    baseline = evaluate(DriveArchitecture.EXTERNAL_SPUR_REDUCTION)
    changed_gear_payload = gear_specification(20).model_dump(mode="json")
    changed_gear_payload["properties"][1]["normalized_value"] = 21.0
    changed_gear_payload["properties"][1]["property_hash"] = "pending"
    changed_gear_payload["specification_hash"] = "pending"
    changed_gear = ComponentSpecificationSnapshot.model_validate(changed_gear_payload)
    source_efficiency = scalar(0.8, "1", _P_EFFICIENCY)
    policy_efficiency = scalar(0.8, "1", None)
    variants = {
        "gear tooth count": evaluate(
            DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            template_input=template(
                DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
                driver_gear_specification=changed_gear,
            ),
        ),
        "efficiency assumption value": evaluate(
            DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            engineering=spur_requirements(efficiency=scalar(0.7, "1", _P_EFFICIENCY)),
        ),
        "efficiency source-to-policy provenance kind": evaluate(
            DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            engineering=spur_requirements(efficiency=policy_efficiency),
        ),
    }

    assert source_efficiency.provenance.value == "source_authority"
    assert policy_efficiency.provenance.value == "policy_assumption"
    assert baseline.requirements_hash != variants["efficiency source-to-policy provenance kind"].requirements_hash
    for label, changed in variants.items():
        assert changed.result_hash != baseline.result_hash, label


def test_result_identity_binds_source_request_and_policy_hashes():
    baseline_state = _state()
    baseline_request = request(DriveArchitecture.DIRECT_DRIVE, state=baseline_state)
    baseline_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    baseline = evaluate(
        DriveArchitecture.DIRECT_DRIVE,
        synthesis_request=baseline_request,
        synthesis_policy=baseline_policy,
        state=baseline_state,
    )

    changed_state_payload = baseline_state.model_dump(mode="json")
    changed_state_payload["requirements"][0]["description"] = "changed authority value"
    changed_state = DesignState.model_validate(changed_state_payload)
    changed_source = evaluate(DriveArchitecture.DIRECT_DRIVE, state=changed_state)

    changed_request_payload = baseline_request.model_dump(mode="json")
    changed_request_payload["requested_evaluation_categories"] = ["torque"]
    changed_request_payload["request_hash"] = "pending"
    changed_request = CandidateSynthesisRequest.model_validate(changed_request_payload)
    changed_request_result = evaluate(
        DriveArchitecture.DIRECT_DRIVE,
        synthesis_request=changed_request,
        synthesis_policy=baseline_policy,
        state=baseline_state,
    )

    changed_policy = CandidateSynthesisPolicy(
        entries=(
            ("allow-direct_drive", "direct_drive", "hard_admissibility"),
            ("allow-design-variable:selected-output-shaft-diameter", '{"value":12.0}', "hard_admissibility"),
            ("preferred", "direct_drive", "preference"),
        ),
    )
    changed_policy_result = evaluate(
        DriveArchitecture.DIRECT_DRIVE,
        synthesis_request=baseline_request,
        synthesis_policy=changed_policy,
        state=baseline_state,
    )

    assert changed_source.source_binding_hash != baseline.source_binding_hash
    assert changed_source.result_hash != baseline.result_hash
    assert changed_request_result.synthesis_request_hash != baseline.synthesis_request_hash
    assert changed_request_result.result_hash != baseline.result_hash
    assert changed_policy_result.synthesis_policy_hash != baseline.synthesis_policy_hash
    assert changed_policy_result.result_hash != baseline.result_hash


def test_task_4_source_binding_hash_uses_canonical_json_and_tracks_consumed_authority_changes():
    """Pin Task 4's bound source-binding convention and its authority sensitivity."""
    state = _state()
    binding = _bound_binding(state)
    expected = "sha256:" + hashlib.sha256(
        canonical_json(binding.model_dump(mode="json"))
    ).hexdigest()

    changed_payload = state.model_dump(mode="json")
    changed_payload["requirements"][0]["description"] = "changed consumed authority"
    changed_binding = _bound_binding(DesignState.model_validate(changed_payload))

    assert _hash_source_binding(binding) == expected
    assert _hash_source_binding(changed_binding) != _hash_source_binding(binding)


def test_source_authority_classification_is_part_of_binding_request_and_result_identity():
    state = _state()
    binding = _bound_binding(state)
    binding_payload = binding.model_dump(mode="json")
    binding_payload["consumed_authority"][0]["authority"] = CandidateSourceAuthority.CANONICAL_PARAMETER.value
    changed_binding = CandidateSourceBinding.model_validate(binding_payload)
    baseline_request = request(DriveArchitecture.DIRECT_DRIVE, binding_override=binding)
    changed_request = request(DriveArchitecture.DIRECT_DRIVE, binding_override=changed_binding)

    baseline = evaluate(
        DriveArchitecture.DIRECT_DRIVE,
        synthesis_request=baseline_request,
        state=state,
    )
    changed = evaluate(
        DriveArchitecture.DIRECT_DRIVE,
        synthesis_request=changed_request,
        state=state,
    )

    assert _hash_source_binding(changed_binding) != _hash_source_binding(binding)
    assert changed_request.request_hash != baseline_request.request_hash
    assert changed.result_hash != baseline.result_hash


def test_result_calculation_version_is_part_of_result_identity():
    baseline = evaluate(DriveArchitecture.DIRECT_DRIVE)
    payload = baseline.model_dump(mode="json")
    payload["calculation_version"] = "2"
    payload["result_hash"] = "pending"

    changed = RevoluteDriveAdmissibilityResult.model_validate(payload)

    assert changed.result_hash != baseline.result_hash


def _all_keys(value):
    if isinstance(value, dict):
        keys = set(value)
        for nested in value.values():
            keys.update(_all_keys(nested))
        return keys
    if isinstance(value, list):
        keys = set()
        for nested in value:
            keys.update(_all_keys(nested))
        return keys
    return set()


def test_result_and_requirements_json_round_trip_preserves_hashes_and_has_no_volatile_fields():
    engineering = requirements()
    result = evaluate(DriveArchitecture.DIRECT_DRIVE, engineering=engineering)
    volatile_names = {"run_id", "timestamp", "recorded_at", "created_at"}

    result_json = result.model_dump_json()
    result_round_trip = RevoluteDriveAdmissibilityResult.model_validate_json(result_json)
    requirements_json = engineering.model_dump_json()
    requirements_round_trip = type(engineering).model_validate_json(requirements_json)

    assert result_round_trip.result_hash == result.result_hash
    assert result_round_trip.model_dump_json() == result_json
    assert requirements_round_trip.requirements_hash == engineering.requirements_hash
    assert requirements_round_trip.model_dump_json() == requirements_json
    assert volatile_names.isdisjoint(_all_keys(result.model_dump(mode="json")))
    assert volatile_names.isdisjoint(_all_keys(engineering.model_dump(mode="json")))


def test_caller_supplied_tampered_result_hash_is_rejected_after_json_round_trip():
    result = evaluate(DriveArchitecture.DIRECT_DRIVE)
    payload = json.loads(result.model_dump_json())
    payload["result_hash"] = "sha256:" + "0" * 64

    with pytest.raises(ValidationError, match="result hash mismatch"):
        RevoluteDriveAdmissibilityResult.model_validate_json(json.dumps(payload))
