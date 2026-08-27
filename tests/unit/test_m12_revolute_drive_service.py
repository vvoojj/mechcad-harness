from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from mechcad_harness.candidates import (
    CandidateCurrentness,
    CandidateCurrentnessService,
    CandidateIntegrityVerifier,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateDesignVariable,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    ComponentPropertyAvailability,
    ComponentPropertyAuthority,
    ComponentPropertySnapshot,
    ComponentSpecificationSnapshot,
    MechanicalDesignCandidate,
    candidate_hash,
)
from mechcad_harness.candidates.models import PolicyEntrySemantics
from mechcad_harness.models import DesignState
from mechcad_harness.revolute_drive import (
    DriveAdmissibility,
    DriveArchitecture,
    EngineeringCheckStatus,
    InputProvenanceKind,
    RevoluteDriveRealizationService,
    RevoluteDriveEngineeringRequirements,
    RevoluteDriveTemplateInput,
    ShaftSupportGeometry,
    SourceBoundScalar,
    StaticOutputShaftDesignLoadCase,
    TrustedCanonicalScalarSourceBinding,
    admissibility_result_hash,
)
from mechcad_harness.models.design import Constraint, Interface, LoadCase, Requirement
from mechcad_harness.state import StateManager, state_hash


_FIXED_TIME = datetime(2026, 8, 27, tzinfo=timezone.utc)

_P_SPEED = "/yagi_payload_carrier_requirements/0"
_P_SPUR_SPEED = "/yagi_payload_carrier_requirements/1"
_P_TORQUE = "/yagi_payload_carrier_requirements/2"
_P_EFFICIENCY = "/yagi_payload_carrier_requirements/3"
_P_PEAK = "/yagi_payload_carrier_requirements/4"
_P_SAFETY = "/yagi_payload_carrier_requirements/5"
_P_YIELD = "/yagi_payload_carrier_requirements/6"
_P_VOLTAGE = "/yagi_payload_carrier_requirements/7"
_P_SUPPORT_A = "/yagi_payload_carrier_requirements/8"
_P_SUPPORT_B = "/yagi_payload_carrier_requirements/9"
_P_LOAD_PLANE = "/yagi_payload_carrier_requirements/10"
_P_FORCE_Y = "/yagi_payload_carrier_requirements/11"
_P_FORCE_Z = "/yagi_payload_carrier_requirements/12"

_ALL_CONSUMED_PATHS = (
    (_P_SPEED, CandidateSourceAuthority.CANONICAL_REQUIREMENT),
    (_P_SPUR_SPEED, CandidateSourceAuthority.CANONICAL_REQUIREMENT),
    (_P_TORQUE, CandidateSourceAuthority.CANONICAL_REQUIREMENT),
    (_P_EFFICIENCY, CandidateSourceAuthority.CANONICAL_REQUIREMENT),
    (_P_PEAK, CandidateSourceAuthority.CANONICAL_REQUIREMENT),
    (_P_SAFETY, CandidateSourceAuthority.CANONICAL_REQUIREMENT),
    (_P_YIELD, CandidateSourceAuthority.CANONICAL_REQUIREMENT),
    (_P_VOLTAGE, CandidateSourceAuthority.CANONICAL_CONSTRAINT),
    (_P_SUPPORT_A, CandidateSourceAuthority.CANONICAL_PARAMETER),
    (_P_SUPPORT_B, CandidateSourceAuthority.CANONICAL_PARAMETER),
    (_P_LOAD_PLANE, CandidateSourceAuthority.CANONICAL_PARAMETER),
    (_P_FORCE_Y, CandidateSourceAuthority.CANONICAL_INTERFACE),
    (_P_FORCE_Z, CandidateSourceAuthority.CANONICAL_INTERFACE),
)


def _state() -> DesignState:
    return DesignState(
        id="DES-M12",
        revision=1,
        created_at=_FIXED_TIME,
        requirements=[
            Requirement(id=f"REQ-M12-3-{index}", name=f"quantity {index}", description="revolute drive authority", created_at=_FIXED_TIME)
            for index in range(6)
        ],
        constraints=[Constraint(id="CON-M12-3-VOLTAGE", name="supply voltage", expression="24 V supply available for the drive", created_at=_FIXED_TIME)],
        interfaces=[
            Interface(id="INT-FORCE-Y", name="transverse force y", component_ids=[], created_at=_FIXED_TIME),
            Interface(id="INT-FORCE-Z", name="transverse force z", component_ids=[], created_at=_FIXED_TIME),
        ],
        load_cases=[
            LoadCase(id="LC-SUPPORT-A", name="support A x coordinate", description="support A axial station", created_at=_FIXED_TIME),
            LoadCase(id="LC-SUPPORT-B", name="support B x coordinate", description="support B axial station", created_at=_FIXED_TIME),
            LoadCase(id="LC-LOAD-PLANE", name="load plane x coordinate", description="load plane axial station", created_at=_FIXED_TIME),
        ],
        yagi_payload_carrier_requirements=[
            {"value": 100.0, "unit": "rpm"},
            {"value": 20.0, "unit": "rpm"},
            {"value": 10.0, "unit": "N*m"},
            {"value": 0.8, "unit": "1"},
            {"value": 30.0, "unit": "N*m"},
            {"value": 2.0, "unit": "1"},
            {"value": 250.0, "unit": "MPa"},
            {"value": 24.0, "unit": "V"},
            {"value": 0.0, "unit": "mm"},
            {"value": 100.0, "unit": "mm"},
            {"value": 50.0, "unit": "mm"},
            {"value": 0.0, "unit": "N"},
            {"value": 0.0, "unit": "N"},
        ],
    )


def _binding(
    paths: tuple[tuple[str, CandidateSourceAuthority], ...] = _ALL_CONSUMED_PATHS,
    source_values: dict[str, tuple[float, str]] | None = None,
) -> object:
    values = {
        _P_SPEED: (100.0, "rpm"),
        _P_TORQUE: (10.0, "N*m"),
        _P_EFFICIENCY: (0.8, "1"),
        _P_PEAK: (30.0, "N*m"),
        _P_SAFETY: (2.0, "1"),
        _P_YIELD: (250.0, "MPa"),
        _P_VOLTAGE: (24.0, "V"),
        _P_SUPPORT_A: (0.0, "mm"),
        _P_SUPPORT_B: (100.0, "mm"),
        _P_LOAD_PLANE: (50.0, "mm"),
        _P_FORCE_Y: (0.0, "N"),
        _P_FORCE_Z: (0.0, "N"),
    }
    values.update(source_values or {})

    def _make(state: DesignState):
        return CandidateSourceBinding(
            project_id="PRJ-M12",
            source_revision=state.revision,
            source_state_hash=state_hash(state),
            consumed_authority=tuple(
                CandidateSourceReference(
                    path=path,
                    value_hash="pending",
                    authority=authority,
                )
                for path, authority in paths
            ),
        ).bound_to(state)

    return _make


def _bound_binding(
    state: DesignState,
    paths=_ALL_CONSUMED_PATHS,
    source_values: dict[str, tuple[float, str]] | None = None,
) -> CandidateSourceBinding:
    return _binding(paths, source_values)(state)


def scalar(value: float, unit: str, path: str | None) -> SourceBoundScalar:
    if path is None:
        return SourceBoundScalar(value=value, unit=unit, provenance=InputProvenanceKind.POLICY_ASSUMPTION)
    return SourceBoundScalar(
        value=value,
        unit=unit,
        provenance=InputProvenanceKind.SOURCE_AUTHORITY,
        source_path=path,
    )


def prop(key: str, value: float, unit: str, source_identity: str = "datasheet:m12@1") -> ComponentPropertySnapshot:
    return ComponentPropertySnapshot(
        key=key,
        availability=ComponentPropertyAvailability.AVAILABLE,
        normalized_value=value,
        canonical_unit=unit,
        source_identity=source_identity,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
    )


def missing_prop(key: str, source_identity: str = "datasheet:m12@1") -> ComponentPropertySnapshot:
    return ComponentPropertySnapshot(
        key=key,
        availability=ComponentPropertyAvailability.MISSING,
        source_identity=source_identity,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
    )


def motor_specification(*, continuous: float | None = 12.0, peak: float = 30.0, speed_min: float = 10.0, speed_max: float = 200.0, voltage: float = 24.0) -> ComponentSpecificationSnapshot:
    properties = [
        prop("motor.speed_min_rpm", speed_min, "rpm"),
        prop("motor.speed_max_rpm", speed_max, "rpm"),
        prop("motor.output_shaft_diameter_mm", 12.0, "mm"),
        prop("motor.rated_voltage_v", voltage, "V"),
    ]
    if peak is not None:
        properties.insert(0, prop("motor.peak_torque_nm", peak, "N*m"))
    if continuous is None:
        properties.insert(0, missing_prop("motor.continuous_torque_nm"))
    else:
        properties.insert(0, prop("motor.continuous_torque_nm", continuous, "N*m"))
    return ComponentSpecificationSnapshot(
        component_type="motor",
        manufacturer="Example Motion",
        part_number="MTR-M12-3",
        source_identity="datasheet:m12:motor@1",
        properties=tuple(properties),
        interfaces=("output-shaft", "mount-face"),
    )


def shaft_specification(diameter: float = 12.0) -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="shaft",
        source_identity="custom:m12:shaft@1",
        properties=(prop("shaft.diameter_mm", diameter, "mm", "drawing:m12:shaft@1"),),
        interfaces=("motor-side", "hub-side", "journal-a", "journal-b"),
    )


def bearing_specification(bore: float = 12.0) -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="bearing",
        source_identity="catalog:m12:bearing@1",
        properties=(prop("bearing.bore_diameter_mm", bore, "mm", "catalog:m12:bearing@1"),),
        interfaces=("housing",),
    )


def hub_specification(bore: float = 12.0) -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="hub",
        source_identity="catalog:m12:hub@1",
        properties=(prop("hub.bore_diameter_mm", bore, "mm", "catalog:m12:hub@1"),),
        interfaces=("shaft", "body"),
    )


def mount_specification() -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="custom:m12:mount@1",
        interfaces=("motor",),
    )


def support_mount_specification() -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="support-mount",
        source_identity="custom:m12:support-mount@1",
        interfaces=("bearing",),
    )


def body_specification() -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="driven-body",
        source_identity="custom:m12:body@1",
        interfaces=("hub", "payload"),
    )


def gear_specification(teeth: int, *, module: float = 2.0, pressure_angle: float = 20.0, bore: float = 12.0, declare_kind: bool = True, interfaces: tuple[str, ...] = ("bore", "mesh")) -> ComponentSpecificationSnapshot:
    declarations: tuple[str, ...] = ()
    if declare_kind:
        declarations = ("external_spur",)
    return ComponentSpecificationSnapshot(
        component_type="gear",
        source_identity=f"catalog:m12:gear-{teeth}@1",
        properties=(
            prop("gear.module_mm", module, "mm", "catalog:m12:gear@1"),
            prop("gear.tooth_count", float(teeth), "1", "catalog:m12:gear@1"),
            prop("gear.pressure_angle_deg", pressure_angle, "deg", "catalog:m12:gear@1"),
            prop("gear.face_width_mm", 10.0, "mm", "catalog:m12:gear@1"),
            prop("gear.bore_diameter_mm", bore, "mm", "catalog:m12:gear@1"),
        ),
        interfaces=interfaces,
        compatibility_declarations=declarations,
    )


def design_variables() -> tuple[CandidateDesignVariable, ...]:
    return (CandidateDesignVariable(name="selected-output-shaft-diameter", value=12.0),)


def template(architecture: DriveArchitecture, **overrides) -> RevoluteDriveTemplateInput:
    values: dict = {
        "architecture": architecture,
        "joint_id": "J-1",
        "axis_frame_reference": "joint:J-1=shaft-axis",
        "motor_instance_id": "drive-motor",
        "motor_specification": motor_specification(),
        "shaft_instance_id": "output-shaft",
        "shaft_specification": shaft_specification(),
        "bearing_a_instance_id": "bearing-a",
        "bearing_a_specification": bearing_specification(),
        "bearing_b_instance_id": "bearing-b",
        "bearing_b_specification": bearing_specification(),
        "hub_instance_id": "output-hub",
        "hub_specification": hub_specification(),
        "mount_instance_id": "motor-mount",
        "mount_specification": mount_specification(),
        "driven_body_instance_id": "payload-body",
        "driven_body_specification": body_specification(),
        "design_variables": design_variables(),
    }
    if architecture is DriveArchitecture.EXTERNAL_SPUR_REDUCTION:
        values.update(
            {
                "driver_gear_instance_id": "driver-gear",
                "driver_gear_specification": gear_specification(20),
                "driven_gear_instance_id": "driven-gear",
                "driven_gear_specification": gear_specification(100),
                "support_mount_instance_ids": ("support-mount-a", "support-mount-b"),
                "support_mount_specifications": (support_mount_specification(), support_mount_specification()),
            }
        )
    values.update(overrides)
    return RevoluteDriveTemplateInput(**values)


def requirements(**overrides) -> RevoluteDriveEngineeringRequirements:
    explicit_trusted_bindings = "trusted_source_scalar_bindings" in overrides
    values: dict = {
        "required_output_speed": scalar(100.0, "rpm", _P_SPEED),
        "design_load_case": StaticOutputShaftDesignLoadCase(
            design_torque=scalar(10.0, "N*m", _P_TORQUE),
            transverse_force_y=scalar(0.0, "N", _P_FORCE_Y),
            transverse_force_z=scalar(0.0, "N", _P_FORCE_Z),
        ),
        "required_voltage": scalar(24.0, "V", _P_VOLTAGE),
        "efficiency": None,
        "required_peak_torque": None,
        "safety_factor": scalar(2.0, "1", _P_SAFETY),
        "shaft_yield_strength": scalar(250.0, "MPa", _P_YIELD),
        "shaft_support_geometry": ShaftSupportGeometry(
            support_a_x=scalar(0.0, "mm", _P_SUPPORT_A),
            support_b_x=scalar(100.0, "mm", _P_SUPPORT_B),
            load_plane_x=scalar(50.0, "mm", _P_LOAD_PLANE),
        ),
        "require_nominal_interface_compatibility": False,
    }
    values.update(overrides)
    bound = _bound_binding(_state())
    reference_hashes = {
        reference.path: reference.value_hash
        for reference in bound.consumed_authority
    }
    scalar_values = (
        values["required_output_speed"],
        values["design_load_case"].design_torque,
        values["design_load_case"].transverse_force_y,
        values["design_load_case"].transverse_force_z,
        values["required_voltage"],
        values["efficiency"],
        values["required_peak_torque"],
        values["safety_factor"],
        values["shaft_yield_strength"],
        None if values["shaft_support_geometry"] is None else values["shaft_support_geometry"].support_a_x,
        None if values["shaft_support_geometry"] is None else values["shaft_support_geometry"].support_b_x,
        None if values["shaft_support_geometry"] is None else values["shaft_support_geometry"].load_plane_x,
    )
    if not explicit_trusted_bindings:
        values["trusted_source_scalar_bindings"] = tuple(
            TrustedCanonicalScalarSourceBinding(
                source_path=scalar_value.source_path,
                source_record_hash=reference_hashes[scalar_value.source_path],
                value=scalar_value.value,
                unit=scalar_value.unit,
                source_identity="fixture:trusted-canonical-scalar@1",
            )
            for scalar_value in scalar_values
            if scalar_value is not None
            and scalar_value.provenance is InputProvenanceKind.SOURCE_AUTHORITY
        )
    return RevoluteDriveEngineeringRequirements(**values)


def spur_requirements(**overrides) -> RevoluteDriveEngineeringRequirements:
    base = dict(
        required_output_speed=scalar(20.0, "rpm", _P_SPUR_SPEED),
        efficiency=scalar(0.8, "1", _P_EFFICIENCY),
        required_peak_torque=scalar(30.0, "N*m", _P_PEAK),
    )
    base.update(overrides)
    return requirements(**base)


def request(
    policy_architecture: DriveArchitecture,
    binding_override=None,
    state=None,
    source_values: dict[str, tuple[float, str]] | None = None,
) -> CandidateSynthesisRequest:
    if binding_override is not None:
        source = binding_override
    else:
        source = _bound_binding(
            _state() if state is None else state,
            source_values={
                **(
                    {_P_SPEED: (20.0, "rpm"), _P_EFFICIENCY: (0.8, "1"), _P_PEAK: (30.0, "N*m")}
                    if policy_architecture is DriveArchitecture.EXTERNAL_SPUR_REDUCTION
                    else {}
                ),
                **(source_values or {}),
            },
        )
    return CandidateSynthesisRequest(
        source_binding=source,
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )


def policy_for(architecture: DriveArchitecture, *, selected_diameter: float = 12.0) -> CandidateSynthesisPolicy:
    return CandidateSynthesisPolicy(
        entries=(
            (f"allow-{architecture.value}", architecture.value, "hard_admissibility"),
            (
                "allow-design-variable:selected-output-shaft-diameter",
                json.dumps({"value": selected_diameter}, sort_keys=True, separators=(",", ":")),
                "hard_admissibility",
            ),
        ),
    )


def statuses(result) -> dict:
    return {check.check_id: check.status for check in result.checks}


_SERVICE = RevoluteDriveRealizationService()


def test_construct_candidate_is_deterministic_and_integrity_valid():
    state = _state()
    direct_template = template(DriveArchitecture.DIRECT_DRIVE)
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=state)
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)

    outcome_one = _SERVICE.construct_candidate(synthesis_request, synthesis_policy, direct_template)
    outcome_two = _SERVICE.construct_candidate(deepcopy(synthesis_request), deepcopy(synthesis_policy), deepcopy(direct_template))

    assert outcome_one.status is DriveAdmissibility.ADMISSIBLE
    assert outcome_one.reason is None
    assert outcome_one.candidate is not None
    assert outcome_two.candidate is not None
    assert outcome_one.candidate.candidate_hash == outcome_two.candidate.candidate_hash
    assert outcome_one.candidate == outcome_two.candidate
    assert outcome_one.candidate.candidate_hash == candidate_hash(outcome_one.candidate)
    verified = CandidateIntegrityVerifier().verify(outcome_one.candidate, synthesis_request, synthesis_policy)
    assert verified.candidate_hash == outcome_one.candidate.candidate_hash


def test_c1_and_c2_selected_shaft_diameter_lineage_has_distinct_identities_without_result_inheritance():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    c2_policy = policy_for(DriveArchitecture.DIRECT_DRIVE, selected_diameter=14.0)
    c1 = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate
    c2 = _SERVICE.construct_candidate(
        synthesis_request,
        c2_policy,
        template(
            DriveArchitecture.DIRECT_DRIVE,
            design_variables=(
                CandidateDesignVariable(
                    name="selected-output-shaft-diameter",
                    value=14.0,
                ),
            ),
        ),
    ).candidate

    c1_result_before = _SERVICE.evaluate(c1, synthesis_request, synthesis_policy, requirements(), source_state=_state())
    c2_result = _SERVICE.evaluate(c2, synthesis_request, c2_policy, requirements(), source_state=_state())
    c1_result_after = _SERVICE.evaluate(c1, synthesis_request, synthesis_policy, requirements(), source_state=_state())

    assert c1.candidate_hash != c2.candidate_hash
    assert c1_result_after == c1_result_before
    assert c1_result_before.candidate_hash == c1.candidate_hash
    assert c2_result.candidate_hash == c2.candidate_hash
    assert c2_result.result_hash != c1_result_before.result_hash
    c1_stress = next(check for check in c1_result_before.checks if check.check_id == "shaft-selected-diameter-stress")
    c2_stress = next(check for check in c2_result.checks if check.check_id == "shaft-selected-diameter-stress")
    assert c1_stress.status is EngineeringCheckStatus.SATISFIED
    assert c2_stress.status is EngineeringCheckStatus.SATISFIED


def test_selected_shaft_diameter_changes_service_stress_admissibility_and_result_identity():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    undersized_policy = policy_for(DriveArchitecture.DIRECT_DRIVE, selected_diameter=2.0)
    adequate = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate
    undersized = _SERVICE.construct_candidate(
        synthesis_request,
        undersized_policy,
        template(
            DriveArchitecture.DIRECT_DRIVE,
            design_variables=(
                CandidateDesignVariable(
                    name="selected-output-shaft-diameter",
                    value=2.0,
                ),
            ),
        ),
    ).candidate

    adequate_result = _SERVICE.evaluate(
        adequate,
        synthesis_request,
        synthesis_policy,
        requirements(),
        source_state=_state(),
    )
    undersized_result = _SERVICE.evaluate(
        undersized,
        synthesis_request,
        undersized_policy,
        requirements(),
        source_state=_state(),
    )

    assert adequate_result.status is DriveAdmissibility.ADMISSIBLE
    assert undersized_result.status is DriveAdmissibility.INADMISSIBLE
    assert undersized_result.result_hash != adequate_result.result_hash


def test_derived_c2_has_explicit_parent_lineage_and_independent_evaluation_identity():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    c2_policy = policy_for(DriveArchitecture.DIRECT_DRIVE, selected_diameter=14.0)
    c1 = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate
    c2_payload = c1.model_dump(mode="json")
    c2_payload["design_variables"][0]["value"] = 14.0
    c2_payload["parent_candidate_hash"] = c1.candidate_hash
    c2_payload["derivation_kind"] = "selected-shaft-diameter-variation"
    c2_payload["synthesis_policy_hash"] = c2_policy.policy_hash
    c2_payload["candidate_hash"] = "pending"
    c2 = MechanicalDesignCandidate.model_validate(c2_payload)

    c1_result = _SERVICE.evaluate(c1, synthesis_request, synthesis_policy, requirements(), source_state=_state())
    c2_result = _SERVICE.evaluate(c2, synthesis_request, c2_policy, requirements(), source_state=_state())

    assert c2.parent_candidate_hash == c1.candidate_hash
    assert c2.derivation_kind == "selected-shaft-diameter-variation"
    assert c2.candidate_hash != c1.candidate_hash
    assert c2_result.candidate_hash == c2.candidate_hash
    assert c2_result.result_hash != c1_result.result_hash


def test_spur_result_preserves_shared_property_bindings_for_both_gear_instances():
    synthesis_request = request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION)
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
    ).candidate

    result = _SERVICE.evaluate(candidate, synthesis_request, synthesis_policy, spur_requirements(), source_state=_state())

    for property_key in ("gear.module_mm", "gear.pressure_angle_deg", "gear.face_width_mm"):
        bindings = [
            binding
            for binding in result.consumed_property_bindings
            if binding.property_key == property_key
        ]
        assert {binding.component_instance_id for binding in bindings} == {
            "driver-gear",
            "driven-gear",
        }
        assert len({binding.specification_hash for binding in bindings}) == 2


def test_service_rejects_requirements_with_stale_caller_hash():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate
    tampered_requirements = requirements().model_copy(
        update={"required_output_speed": scalar(90.0, "rpm", _P_SPEED)}
    )

    with pytest.raises(ValueError, match="requirements hash mismatch"):
        _SERVICE.evaluate(candidate, synthesis_request, synthesis_policy, tampered_requirements, source_state=_state())


def test_service_rejects_request_with_stale_caller_hash():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    tampered_request = synthesis_request.model_copy(
        update={"requested_evaluation_categories": ("torque",)}
    )

    with pytest.raises(ValueError, match="request hash mismatch"):
        _SERVICE.construct_candidate(
            tampered_request,
            policy_for(DriveArchitecture.DIRECT_DRIVE),
            template(DriveArchitecture.DIRECT_DRIVE),
        )


def test_service_rejects_policy_with_stale_caller_hash():
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    tampered_policy = synthesis_policy.model_copy(
        update={
            "entries": (
                ("allow-direct_drive", "direct_drive", PolicyEntrySemantics.HARD_ADMISSIBILITY),
                ("preferred", "direct_drive", PolicyEntrySemantics.PREFERENCE),
            )
        }
    )

    with pytest.raises(ValueError, match="policy hash mismatch"):
        _SERVICE.construct_candidate(
            request(DriveArchitecture.DIRECT_DRIVE, state=_state()),
            tampered_policy,
            template(DriveArchitecture.DIRECT_DRIVE),
        )


def test_incomplete_direct_topology_returns_unresolved_outcome_without_candidate():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    outcome = _SERVICE.construct_candidate(
        synthesis_request,
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        template(DriveArchitecture.DIRECT_DRIVE, hub_specification=None),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert outcome.reason is not None
    assert "hub" in outcome.reason


def test_missing_driver_gear_leaves_spur_topology_unresolved():
    synthesis_request = request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state())
    outcome = _SERVICE.construct_candidate(
        synthesis_request,
        policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        template(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, driver_gear_specification=None),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert "driver gear" in outcome.reason


def test_driven_gear_without_mesh_interface_cannot_form_the_mesh_connection():
    synthesis_request = request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state())
    lone_gear = gear_specification(100, interfaces=("bore",))
    outcome = _SERVICE.construct_candidate(
        synthesis_request,
        policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        template(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, driven_gear_specification=lone_gear),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert "mesh" in outcome.reason


def test_support_mount_without_bearing_interface_is_typed_unresolved_not_valueerror():
    synthesis_request = request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state())
    unmounted_support = ComponentSpecificationSnapshot(
        component_type="support-mount",
        source_identity="custom:m12:support-mount-unmounted@1",
        interfaces=("frame",),
    )
    outcome = _SERVICE.construct_candidate(
        synthesis_request,
        policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        template(
            DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            support_mount_specifications=(support_mount_specification(), unmounted_support),
        ),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert "support mount b" in outcome.reason
    assert "'bearing'" in outcome.reason


def test_wrong_semantic_component_type_is_typed_unresolved_even_when_interfaces_match():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    wrong_motor_payload = motor_specification().model_dump(mode="json")
    wrong_motor_payload["component_type"] = "shaft"
    wrong_motor_payload["specification_hash"] = "pending"
    wrong_motor = type(motor_specification()).model_validate(wrong_motor_payload)

    outcome = _SERVICE.construct_candidate(
        synthesis_request,
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        template(DriveArchitecture.DIRECT_DRIVE, motor_specification=wrong_motor),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert "component type" in (outcome.reason or "")


def test_policy_not_allowing_requested_architecture_stays_unresolved():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    deny_policy = CandidateSynthesisPolicy(entries=(("allow-spur-only", "external_spur_reduction", "hard_admissibility"),))
    outcome = _SERVICE.construct_candidate(
        synthesis_request,
        deny_policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert "policy" in outcome.reason


def test_policy_missing_candidate_design_variable_admission_stays_unresolved():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    architecture_only_policy = CandidateSynthesisPolicy(
        entries=(
            ("allow-direct_drive", "direct_drive", "hard_admissibility"),
        )
    )

    outcome = _SERVICE.construct_candidate(
        synthesis_request,
        architecture_only_policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert "design variable" in (outcome.reason or "")


def test_policy_mismatched_candidate_design_variable_admission_stays_unresolved():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())

    outcome = _SERVICE.construct_candidate(
        synthesis_request,
        policy_for(DriveArchitecture.DIRECT_DRIVE, selected_diameter=13.0),
        template(DriveArchitecture.DIRECT_DRIVE),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert "design variable" in (outcome.reason or "")


def test_request_requiring_multiple_or_different_joints_returns_no_candidate():
    base_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    request_payload = base_request.model_dump(mode="json")
    request_payload["required_joint_ids"] = ["J-1", "J-2"]
    request_payload["requested_joint_ids"] = ["J-1", "J-2"]
    request_payload["request_hash"] = "pending"
    multi_joint_request = CandidateSynthesisRequest.model_validate(request_payload)

    outcome = _SERVICE.construct_candidate(
        multi_joint_request,
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        template(DriveArchitecture.DIRECT_DRIVE),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert "exactly one" in (outcome.reason or "")


def test_missing_axis_frame_reference_returns_no_candidate():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    outcome = _SERVICE.construct_candidate(
        synthesis_request,
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        template(DriveArchitecture.DIRECT_DRIVE, axis_frame_reference=None),
    )

    assert outcome.status is DriveAdmissibility.UNRESOLVED
    assert outcome.candidate is None
    assert "axis/frame" in (outcome.reason or "")


def test_candidate_survives_when_motor_lacks_continuous_torque_and_check_is_unresolved():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    incomplete_motor_template = template(DriveArchitecture.DIRECT_DRIVE, motor_specification=motor_specification(continuous=None))
    outcome = _SERVICE.construct_candidate(synthesis_request, synthesis_policy, incomplete_motor_template)

    assert outcome.status is DriveAdmissibility.ADMISSIBLE
    original_candidate = outcome.candidate
    result = _SERVICE.evaluate(original_candidate, synthesis_request, synthesis_policy, requirements(), source_state=_state())

    assert result.status is DriveAdmissibility.UNRESOLVED
    by_id = statuses(result)
    assert by_id["motor-continuous-torque"] is EngineeringCheckStatus.UNRESOLVED
    assert by_id["motor-speed"] is EngineeringCheckStatus.SATISFIED
    assert by_id["motor-voltage"] is EngineeringCheckStatus.SATISFIED
    assert result.candidate_hash == original_candidate.candidate_hash
    assert result.calculation_id == "m12-3.revolute-drive"


def test_composite_source_path_without_explicit_trusted_scalar_binding_is_unresolved():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate

    result = _SERVICE.evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        requirements(trusted_source_scalar_bindings=()),
        source_state=_state(),
    )

    assert result.status is DriveAdmissibility.UNRESOLVED
    assert result.checks[0].check_id == "source-authority"
    assert "composite canonical source record" in (result.checks[0].reason or "")


def test_direct_evaluation_with_complete_data_is_admissible():
    state = _state()
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=state)
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    complete_requirements = requirements(require_nominal_interface_compatibility=True)
    candidate = _SERVICE.construct_candidate(
        deepcopy(synthesis_request),
        deepcopy(synthesis_policy),
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate

    result = _SERVICE.evaluate(candidate, deepcopy(synthesis_request), deepcopy(synthesis_policy), complete_requirements, source_state=_state())

    assert result.status is DriveAdmissibility.ADMISSIBLE
    assert set(statuses(result).values()) == {EngineeringCheckStatus.SATISFIED}
    assert statuses(result)["nominal-interface-compatibility"] is EngineeringCheckStatus.SATISFIED
    assert result.requirements_hash == complete_requirements.requirements_hash
    assert result.design_variables == candidate.design_variables
    assert candidate.source_binding.source_state_hash == state_hash(state)
    binding_payload_hashes = {
        "state": result.source_binding_hash,
    }
    assert binding_payload_hashes["state"].startswith("sha256:")
    assert result.result_hash == admissibility_result_hash(result)


def test_spur_evaluation_with_explicit_efficiency_transfers_torque():
    candidate = _SERVICE.construct_candidate(
        request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state()),
        policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        template(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
    ).candidate
    evaluated = spur_requirements()

    result = _SERVICE.evaluate(candidate, request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state()), policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION), evaluated, source_state=_state())

    assert result.status is DriveAdmissibility.ADMISSIBLE
    by_id = statuses(result)
    assert by_id["spur-pair-compatibility"] is EngineeringCheckStatus.SATISFIED
    assert by_id["spur-output-speed"] is EngineeringCheckStatus.SATISFIED
    assert by_id["spur-output-torque-transfer"] is EngineeringCheckStatus.SATISFIED
    assert by_id["motor-continuous-torque"] is EngineeringCheckStatus.SATISFIED
    assert by_id["motor-peak-torque"] is EngineeringCheckStatus.SATISFIED
    torque_transfer = next(check for check in result.checks if check.check_id == "spur-output-torque-transfer")
    assert "/requirements/efficiency" in torque_transfer.consumed_requirement_paths
    keys = {binding.property_key for binding in result.consumed_property_bindings}
    assert {"gear.module_mm", "gear.tooth_count", "motor.continuous_torque_nm"} <= keys


def test_spur_evaluation_emits_exactly_one_output_speed_check():
    candidate = _SERVICE.construct_candidate(
        request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state()),
        policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        template(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
    ).candidate

    result = _SERVICE.evaluate(
        candidate,
        request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state()),
        policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        spur_requirements(),
        source_state=_state(),
    )

    assert [check.check_id for check in result.checks if "speed" in check.check_id] == [
        "spur-output-speed"
    ]


def test_spur_nominal_interface_check_requires_and_separately_binds_gear_bores():
    synthesis_request = request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION)
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template(
            DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            driver_gear_specification=gear_specification(20, bore=10.0),
            driven_gear_specification=gear_specification(100, bore=11.0),
        ),
    ).candidate

    result = _SERVICE.evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        spur_requirements(require_nominal_interface_compatibility=True),
        source_state=_state(),
    )
    check = next(check for check in result.checks if check.check_id == "nominal-interface-compatibility")

    assert check.status is EngineeringCheckStatus.VIOLATED
    assert {
        (binding.component_instance_id, binding.property_key)
        for binding in check.consumed_property_bindings
    } >= {
        ("driver-gear", "gear.bore_diameter_mm"),
        ("driven-gear", "gear.bore_diameter_mm"),
        ("drive-motor", "motor.output_shaft_diameter_mm"),
    }


def test_spur_nominal_interface_check_reports_missing_explicit_bore_as_unresolved():
    synthesis_request = request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION)
    driven_payload = gear_specification(100).model_dump(mode="json")
    driven_payload["properties"] = [
        value for value in driven_payload["properties"]
        if value["key"] != "gear.bore_diameter_mm"
    ]
    driven_payload["specification_hash"] = "pending"
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template(
            DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            driven_gear_specification=ComponentSpecificationSnapshot.model_validate(driven_payload),
        ),
    ).candidate

    result = _SERVICE.evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        spur_requirements(require_nominal_interface_compatibility=True),
        source_state=_state(),
    )

    check = next(check for check in result.checks if check.check_id == "nominal-interface-compatibility")
    assert check.status is EngineeringCheckStatus.UNRESOLVED
    assert "driven gear bore" in (check.reason or "")


def test_spur_nominal_interface_check_reports_missing_motor_output_interface_as_unresolved():
    synthesis_request = request(DriveArchitecture.EXTERNAL_SPUR_REDUCTION, state=_state())
    synthesis_policy = policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION)
    motor_payload = motor_specification().model_dump(mode="json")
    motor_payload["properties"] = [
        value for value in motor_payload["properties"]
        if value["key"] != "motor.output_shaft_diameter_mm"
    ]
    motor_payload["specification_hash"] = "pending"
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        synthesis_policy,
        template(
            DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            motor_specification=type(motor_specification()).model_validate(motor_payload),
        ),
    ).candidate

    result = _SERVICE.evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        spur_requirements(require_nominal_interface_compatibility=True),
        source_state=_state(),
    )

    check = next(check for check in result.checks if check.check_id == "nominal-interface-compatibility")
    assert check.status is EngineeringCheckStatus.UNRESOLVED
    assert "motor output interface" in (check.reason or "")


def test_derived_mesh_load_case_without_plane_mapping_stays_unresolved():
    derived_load_case = StaticOutputShaftDesignLoadCase(
        design_torque=scalar(10.0, "N*m", _P_TORQUE),
        derive_transverse_load_from_spur_mesh=True,
    )
    deficient_requirements = requirements(design_load_case=derived_load_case)
    candidate = _SERVICE.construct_candidate(
        request(DriveArchitecture.DIRECT_DRIVE, state=_state()),
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate

    result = _SERVICE.evaluate(
        candidate,
        request(DriveArchitecture.DIRECT_DRIVE, state=_state()),
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        deficient_requirements,
        source_state=_state(),
    )

    assert result.status is DriveAdmissibility.UNRESOLVED
    by_id = statuses(result)
    assert by_id["spur-mesh-load-derivation"] is EngineeringCheckStatus.UNRESOLVED
    assert by_id["shaft-static-equilibrium"] is EngineeringCheckStatus.UNRESOLVED
    assert by_id["shaft-selected-diameter-stress"] is EngineeringCheckStatus.UNRESOLVED
    derivation_check = next(check for check in result.checks if check.check_id == "spur-mesh-load-derivation")
    assert "explicit transverse-plane" in (derivation_check.reason or "")


def test_violated_check_precedes_unresolved_checks_in_the_aggregate():
    deficient_requirements = requirements(shaft_yield_strength=None)
    weak_motor_template = template(DriveArchitecture.DIRECT_DRIVE, motor_specification=motor_specification(continuous=6.0))
    candidate = _SERVICE.construct_candidate(
        request(DriveArchitecture.DIRECT_DRIVE, state=_state()),
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        weak_motor_template,
    ).candidate

    result = _SERVICE.evaluate(candidate, request(DriveArchitecture.DIRECT_DRIVE, state=_state()), policy_for(DriveArchitecture.DIRECT_DRIVE), deficient_requirements, source_state=_state())

    assert result.status is DriveAdmissibility.INADMISSIBLE
    aggregated = set(statuses(result).values())
    assert EngineeringCheckStatus.VIOLATED in aggregated
    assert EngineeringCheckStatus.UNRESOLVED in aggregated
    assert statuses(result)["motor-continuous-torque"] is EngineeringCheckStatus.VIOLATED
    assert statuses(result)["shaft-selected-diameter-stress"] is EngineeringCheckStatus.UNRESOLVED


def test_candidate_is_unchanged_after_evaluation():
    candidate_before = _SERVICE.construct_candidate(
        request(DriveArchitecture.DIRECT_DRIVE, state=_state()),
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate
    identity_before = candidate_before.candidate_hash

    result = _SERVICE.evaluate(candidate_before, request(DriveArchitecture.DIRECT_DRIVE, state=_state()), policy_for(DriveArchitecture.DIRECT_DRIVE), requirements(), source_state=_state())

    assert candidate_before.candidate_hash == identity_before
    assert candidate_before.candidate_hash == result.candidate_hash
    with pytest.raises(Exception):
        candidate_before.generator_identity = "forged-after-evaluation"


def test_evaluation_rejects_requirement_source_paths_absent_from_the_binding():
    state = _state()
    narrow_binding = _bound_binding(
        state,
        ((_P_SPEED, CandidateSourceAuthority.CANONICAL_REQUIREMENT),),
    )
    narrowed_request = CandidateSynthesisRequest(source_binding=narrow_binding, required_joint_ids=("J-1",), requested_joint_ids=("J-1",))
    candidate = _SERVICE.construct_candidate(narrowed_request, policy_for(DriveArchitecture.DIRECT_DRIVE), template(DriveArchitecture.DIRECT_DRIVE)).candidate

    with pytest.raises(ValueError, match="not consumed"):
        _SERVICE.evaluate(candidate, narrowed_request, policy_for(DriveArchitecture.DIRECT_DRIVE), requirements(), source_state=state)


def test_evaluation_returns_unresolved_for_recomputed_scalar_against_old_source_record():
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=_state())
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate
    changed_payload = requirements().model_dump(mode="json")
    changed_payload["required_output_speed"]["value"] = 101.0
    changed_payload["required_output_speed"]["source_value_hash"] = scalar(
        101.0, "rpm", _P_SPEED
    ).source_value_hash
    changed_payload["requirements_hash"] = "pending"
    changed_requirements = RevoluteDriveEngineeringRequirements.model_validate(changed_payload)

    result = _SERVICE.evaluate(
        candidate,
        synthesis_request,
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        changed_requirements,
        source_state=_state(),
    )

    assert result.status is DriveAdmissibility.UNRESOLVED
    assert "source authority" in (result.checks[0].reason or "")


def test_source_authority_requires_an_explicit_scalar_record_not_a_composite_record():
    state = _state()
    composite_reference = CandidateSourceReference(
        path="/requirements/0",
        value_hash="pending",
        authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
    )
    source_binding = CandidateSourceBinding(
        project_id="PRJ-M12",
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(composite_reference,),
    ).bound_to(state)
    synthesis_request = CandidateSynthesisRequest(
        source_binding=source_binding,
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )
    policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    no_source_requirements = requirements(
        required_output_speed=scalar(150.0, "rpm", "/requirements/0"),
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
        trusted_source_scalar_bindings=(
            TrustedCanonicalScalarSourceBinding(
                source_path="/requirements/0",
                source_record_hash=source_binding.consumed_authority[0].value_hash,
                value=150.0,
                unit="rpm",
                source_identity="fixture:trusted-canonical-scalar@1",
            ),
        ),
    )
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate

    result = _SERVICE.evaluate(
        candidate,
        synthesis_request,
        policy,
        no_source_requirements,
        source_state=state,
    )

    assert result.status is DriveAdmissibility.UNRESOLVED
    assert "explicit scalar record" in (result.checks[0].reason or "")


def test_source_authority_accepts_an_exact_canonical_scalar_record():
    state = _state()
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=state)
    policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate

    result = _SERVICE.evaluate(
        candidate,
        synthesis_request,
        policy,
        requirements(),
        source_state=state,
    )

    assert result.status is DriveAdmissibility.ADMISSIBLE


def test_constructed_candidate_passes_currentness_over_real_state(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    synthesis_request = request(DriveArchitecture.DIRECT_DRIVE, state=state)
    candidate = _SERVICE.construct_candidate(
        synthesis_request,
        policy_for(DriveArchitecture.DIRECT_DRIVE),
        template(DriveArchitecture.DIRECT_DRIVE),
    ).candidate

    assert CandidateCurrentnessService(manager).evaluate(candidate, synthesis_request, policy_for(DriveArchitecture.DIRECT_DRIVE)) is CandidateCurrentness.CURRENT


def test_service_has_no_stateful_dependencies():
    service = RevoluteDriveRealizationService()
    assert getattr(service, "__dict__", {}) == {} or not vars(service)
