from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from mechcad_harness.application import ProductionApplication
from mechcad_harness.candidates import (
    CandidateCurrentness,
    CandidateIntegrityError,
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
)
from mechcad_harness.models import DesignState
from mechcad_harness.models.design import Constraint, Interface, LoadCase, Requirement
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
)
from mechcad_harness.state import StateManager, state_hash


PROJECT_ID = "PRJ-M12"

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


class UninvokedAgentAdapter:
    def __init__(self):
        self.invocation_count = 0

    @property
    def identity(self):
        return "m12-revolute-drive-uninvoked"

    def invoke(self, request):
        self.invocation_count += 1
        raise AssertionError("agent adapter must never be invoked by the M12-3 flow")


def production_state() -> DesignState:
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


def build_application(tmp_path: Path) -> ProductionApplication:
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /requirements/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    StateManager(workspace).create_project(PROJECT_ID, production_state())
    return ProductionApplication.create(
        workspace,
        PROJECT_ID,
        UninvokedAgentAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def make_request(
    application: ProductionApplication,
    architecture: DriveArchitecture = DriveArchitecture.DIRECT_DRIVE,
    source_value_overrides: dict[str, tuple[float, str]] | None = None,
) -> CandidateSynthesisRequest:
    state = application.state_manager.load_current_state(application.project_id)
    source_values = {
        _P_SPEED: (20.0, "rpm"),
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
    if architecture is DriveArchitecture.DIRECT_DRIVE:
        source_values[_P_SPEED] = (100.0, "rpm")
    source_values.update(source_value_overrides or {})
    binding = CandidateSourceBinding(
        project_id=application.project_id,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=tuple(
                CandidateSourceReference(
                    path=path,
                    value_hash="pending",
                    authority=authority,
                )
            for path, authority in _ALL_CONSUMED_PATHS
        ),
    ).bound_to(state)
    return CandidateSynthesisRequest(
        source_binding=binding,
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )


def scalar(value: float, unit: str, path: str | None) -> SourceBoundScalar:
    if path is None:
        return SourceBoundScalar(value=value, unit=unit, provenance=InputProvenanceKind.POLICY_ASSUMPTION)
    return SourceBoundScalar(value=value, unit=unit, provenance=InputProvenanceKind.SOURCE_AUTHORITY, source_path=path)


def prop(key: str, value: float, unit: str, source_identity: str = "datasheet:m12@1") -> ComponentPropertySnapshot:
    return ComponentPropertySnapshot(
        key=key,
        availability=ComponentPropertyAvailability.AVAILABLE,
        normalized_value=value,
        canonical_unit=unit,
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
        properties.insert(0, ComponentPropertySnapshot(
            key="motor.continuous_torque_nm",
            availability=ComponentPropertyAvailability.MISSING,
            source_identity="datasheet:m12@1",
            authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        ))
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


def gear_specification(teeth: int, *, module: float = 2.0, pressure_angle: float = 20.0) -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="gear",
        source_identity=f"catalog:m12:gear-{teeth}@1",
        properties=(
            prop("gear.module_mm", module, "mm", "catalog:m12:gear@1"),
            prop("gear.tooth_count", float(teeth), "1", "catalog:m12:gear@1"),
            prop("gear.pressure_angle_deg", pressure_angle, "deg", "catalog:m12:gear@1"),
            prop("gear.face_width_mm", 10.0, "mm", "catalog:m12:gear@1"),
            prop("gear.bore_diameter_mm", 12.0, "mm", "catalog:m12:gear@1"),
        ),
        interfaces=("bore", "mesh"),
        compatibility_declarations=("external_spur",),
    )


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
        "design_variables": (CandidateDesignVariable(name="selected-output-shaft-diameter", value=12.0),),
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
    source_binding = CandidateSourceBinding(
        project_id=PROJECT_ID,
        source_revision=production_state().revision,
        source_state_hash=state_hash(production_state()),
        consumed_authority=tuple(
            CandidateSourceReference(path=path, value_hash="pending", authority=authority)
            for path, authority in _ALL_CONSUMED_PATHS
        ),
    ).bound_to(production_state())
    reference_hashes = {
        reference.path: reference.value_hash
        for reference in source_binding.consumed_authority
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


def test_source_scalar_with_recomputed_hash_against_old_record_fails_closed(tmp_path):
    application = build_application(tmp_path)
    old_requirements = requirements()
    changed = old_requirements.model_dump(mode="json")
    changed["required_output_speed"]["value"] = 999.0
    changed["required_output_speed"]["source_value_hash"] = SourceBoundScalar(
        value=999.0,
        unit="rpm",
        provenance=InputProvenanceKind.SOURCE_AUTHORITY,
        source_path=_P_SPEED,
    ).source_value_hash
    changed["requirements_hash"] = "pending"
    forged = RevoluteDriveEngineeringRequirements.model_validate(changed)

    outcome = application.realize_and_evaluate_revolute_drive(
        request=make_request(application),
        policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
        template_input=template(DriveArchitecture.DIRECT_DRIVE),
        requirements=forged,
    )

    assert outcome.evaluation is not None
    assert outcome.evaluation.status is DriveAdmissibility.UNRESOLVED
    assert "source authority" in " ".join(check.reason or "" for check in outcome.evaluation.checks)


def test_source_scalar_retaining_old_hash_is_rejected_before_production_evaluation():
    old_requirements = requirements()
    changed = old_requirements.model_dump(mode="json")
    changed["required_output_speed"]["value"] = 999.0
    changed["requirements_hash"] = "pending"

    with pytest.raises(ValueError, match="source scalar value hash mismatch"):
        RevoluteDriveEngineeringRequirements.model_validate(changed)


def test_recomputed_scalar_against_old_composite_source_record_fails_closed(tmp_path):
    application = build_application(tmp_path)
    state = production_state()
    source_binding = CandidateSourceBinding(
        project_id=PROJECT_ID,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path="/requirements/0",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
        ),
    ).bound_to(state)
    old_composite_hash = source_binding.consumed_authority[0].value_hash
    old_composite_request = CandidateSynthesisRequest(
        source_binding=source_binding,
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )
    forged_requirements = requirements(
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
                source_record_hash=old_composite_hash,
                value=150.0,
                unit="rpm",
                source_identity="fixture:trusted-canonical-scalar@1",
            ),
        ),
    )

    outcome = application.realize_and_evaluate_revolute_drive(
        request=old_composite_request,
        policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
        template_input=template(DriveArchitecture.DIRECT_DRIVE),
        requirements=forged_requirements,
    )

    assert outcome.evaluation is not None
    assert outcome.evaluation.status is DriveAdmissibility.UNRESOLVED
    assert "explicit scalar record" in " ".join(
        check.reason or "" for check in outcome.evaluation.checks
    )


def spur_requirements(**overrides) -> RevoluteDriveEngineeringRequirements:
    base = dict(
        required_output_speed=scalar(20.0, "rpm", _P_SPUR_SPEED),
        efficiency=scalar(0.8, "1", _P_EFFICIENCY),
        required_peak_torque=scalar(30.0, "N*m", _P_PEAK),
    )
    base.update(overrides)
    return requirements(**base)


def policy_for(architecture: DriveArchitecture) -> CandidateSynthesisPolicy:
    return CandidateSynthesisPolicy(
        entries=(
            (f"allow-{architecture.value}", architecture.value, "hard_admissibility"),
            (
                "allow-design-variable:selected-output-shaft-diameter",
                json.dumps({"value": 12.0}, sort_keys=True, separators=(",", ":")),
                "hard_admissibility",
            ),
        ),
    )


def statuses(result) -> dict:
    return {check.check_id: check.status for check in result.checks}


def run_direct(application: ProductionApplication):
    return application.realize_and_evaluate_revolute_drive(
        request=make_request(application),
        policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
        template_input=template(DriveArchitecture.DIRECT_DRIVE),
        requirements=requirements(require_nominal_interface_compatibility=True),
    )


def run_spur(application: ProductionApplication):
    return application.realize_and_evaluate_revolute_drive(
        request=make_request(application, DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        policy=policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        template_input=template(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        requirements=spur_requirements(require_nominal_interface_compatibility=True),
    )


def run_incomplete(application: ProductionApplication):
    return application.realize_and_evaluate_revolute_drive(
        request=make_request(application),
        policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
        template_input=template(DriveArchitecture.DIRECT_DRIVE, hub_specification=None),
        requirements=requirements(),
    )


def workspace_snapshot(root: Path) -> dict:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def spy_on_trust_gates(monkeypatch, application) -> dict:
    gates = {"integrity": [], "currentness": []}
    original_verify = application.candidate_integrity_verifier.verify
    original_currentness = application.candidate_currentness_service.evaluate

    def verify_spy(*args, **kwargs):
        gates["integrity"].append(args[0].candidate_hash)
        return original_verify(*args, **kwargs)

    def currentness_spy(*args, **kwargs):
        gates["currentness"].append(args[0].candidate_hash)
        return original_currentness(*args, **kwargs)

    monkeypatch.setattr(application.candidate_integrity_verifier, "verify", verify_spy)
    monkeypatch.setattr(application.candidate_currentness_service, "evaluate", currentness_spy)
    return gates


def test_realize_and_evaluate_is_deterministic_across_two_calls(tmp_path):
    application = build_application(tmp_path)
    request = make_request(application)
    policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    template_input = template(DriveArchitecture.DIRECT_DRIVE)
    engineering = requirements(require_nominal_interface_compatibility=True)

    first = application.realize_and_evaluate_revolute_drive(
        request=deepcopy(request),
        policy=deepcopy(policy),
        template_input=deepcopy(template_input),
        requirements=deepcopy(engineering),
    )
    second = application.realize_and_evaluate_revolute_drive(
        request=deepcopy(request),
        policy=deepcopy(policy),
        template_input=deepcopy(template_input),
        requirements=deepcopy(engineering),
    )

    assert first.construction.status is DriveAdmissibility.ADMISSIBLE
    assert first.construction.candidate is not None
    assert first.evaluation is not None
    assert second.construction == first.construction
    assert second.evaluation == first.evaluation
    assert (
        first.construction.candidate.candidate_hash
        == second.construction.candidate.candidate_hash
    )
    assert first.evaluation.result_hash == second.evaluation.result_hash
    assert first.evaluation.candidate_hash == first.construction.candidate.candidate_hash


def test_direct_drive_end_to_end_consults_integrity_and_currentness_gates_once(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    gates = spy_on_trust_gates(monkeypatch, application)

    outcome = run_direct(application)

    assert outcome.construction.status is DriveAdmissibility.ADMISSIBLE
    assert outcome.construction.reason is None
    assert outcome.evaluation.status is DriveAdmissibility.ADMISSIBLE
    assert set(statuses(outcome.evaluation).values()) == {EngineeringCheckStatus.SATISFIED}
    assert len(gates["integrity"]) == 1
    assert len(gates["currentness"]) == 1
    assert gates["integrity"][0] == outcome.construction.candidate.candidate_hash
    assert_adapter_was_not_invoked(application)


def assert_adapter_was_not_invoked(application) -> None:
    registered = application.agent_registry.get("mechcad-transmission", "1.0")
    assert registered.invocation_count == 0


def test_spur_drive_end_to_end_returns_satisfied_spur_checks(tmp_path):
    application = build_application(tmp_path)

    outcome = run_spur(application)

    assert outcome.construction.status is DriveAdmissibility.ADMISSIBLE
    assert outcome.construction.candidate is not None
    by_id = statuses(outcome.evaluation)
    assert by_id["spur-pair-compatibility"] is EngineeringCheckStatus.SATISFIED
    assert by_id["spur-output-speed"] is EngineeringCheckStatus.SATISFIED
    assert by_id["spur-output-torque-transfer"] is EngineeringCheckStatus.SATISFIED
    assert outcome.evaluation.status is DriveAdmissibility.ADMISSIBLE


def test_spur_drive_end_to_end_rejects_insufficient_efficiency_bound_output_torque(tmp_path):
    application = build_application(tmp_path)
    insufficient_torque = StaticOutputShaftDesignLoadCase(
        design_torque=scalar(60.0, "N*m", None),
        transverse_force_y=scalar(0.0, "N", _P_FORCE_Y),
        transverse_force_z=scalar(0.0, "N", _P_FORCE_Z),
    )

    outcome = application.realize_and_evaluate_revolute_drive(
        request=make_request(
            application,
            DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
            source_value_overrides={_P_TORQUE: (60.0, "N*m")},
        ),
        policy=policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        template_input=template(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        requirements=spur_requirements(design_load_case=insufficient_torque),
    )

    assert outcome.evaluation.status is DriveAdmissibility.INADMISSIBLE
    assert statuses(outcome.evaluation)["spur-output-torque-transfer"] is EngineeringCheckStatus.VIOLATED


def test_production_precedence_is_inadmissible_with_violation_and_unresolved_check(tmp_path):
    application = build_application(tmp_path)

    outcome = application.realize_and_evaluate_revolute_drive(
        request=make_request(application),
        policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
        template_input=template(
            DriveArchitecture.DIRECT_DRIVE,
            motor_specification=motor_specification(continuous=6.0),
        ),
        requirements=requirements(shaft_yield_strength=None),
    )

    assert outcome.evaluation.status is DriveAdmissibility.INADMISSIBLE
    by_id = statuses(outcome.evaluation)
    assert by_id["motor-continuous-torque"] is EngineeringCheckStatus.VIOLATED
    assert by_id["shaft-selected-diameter-stress"] is EngineeringCheckStatus.UNRESOLVED


def test_spur_drive_end_to_end_keeps_ratio_and_speed_satisfied_when_efficiency_is_unresolved(tmp_path):
    application = build_application(tmp_path)

    outcome = application.realize_and_evaluate_revolute_drive(
        request=make_request(application, DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        policy=policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        template_input=template(DriveArchitecture.EXTERNAL_SPUR_REDUCTION),
        requirements=spur_requirements(efficiency=None, required_peak_torque=None),
    )

    assert outcome.evaluation.status is DriveAdmissibility.UNRESOLVED
    by_id = statuses(outcome.evaluation)
    assert by_id["spur-pair-compatibility"] is EngineeringCheckStatus.SATISFIED
    assert by_id["spur-output-speed"] is EngineeringCheckStatus.SATISFIED
    assert by_id["spur-output-torque-transfer"] is EngineeringCheckStatus.UNRESOLVED
    assert "motor-speed" not in by_id


def test_application_rejects_stale_nested_template_snapshot_before_construction(tmp_path):
    application = build_application(tmp_path)
    stale_motor = motor_specification().model_copy(
        update={"specification_hash": "sha256:" + "0" * 64}
    )

    with pytest.raises(ValueError, match="component specification hash mismatch"):
        application.realize_and_evaluate_revolute_drive(
            request=make_request(application),
            policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
            template_input=template(DriveArchitecture.DIRECT_DRIVE, motor_specification=stale_motor),
            requirements=requirements(),
        )


def test_production_rejects_stale_requirements_hash_before_evaluation(tmp_path):
    application = build_application(tmp_path)
    tampered_requirements = requirements().model_copy(
        update={"required_output_speed": scalar(90.0, "rpm", _P_SPEED)}
    )

    with pytest.raises(ValueError, match="requirements hash mismatch"):
        application.realize_and_evaluate_revolute_drive(
            request=make_request(application),
            policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
            template_input=template(DriveArchitecture.DIRECT_DRIVE),
            requirements=tampered_requirements,
        )


def test_structural_incompleteness_returns_no_candidate_without_consulting_trust_gates(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    gates = spy_on_trust_gates(monkeypatch, application)

    outcome = run_incomplete(application)

    assert outcome.construction.status is DriveAdmissibility.UNRESOLVED
    assert outcome.construction.candidate is None
    assert "hub" in outcome.construction.reason
    assert outcome.evaluation is None
    assert gates["integrity"] == []
    assert gates["currentness"] == []


def test_forged_candidate_fails_closed_before_currentness_or_evaluation(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    request = make_request(application)
    other_policy = CandidateSynthesisPolicy(entries=(
        ("allow-direct_drive", "direct_drive", "hard_admissibility"),
        ("allow-design-variable:selected-output-shaft-diameter", '{"value":12.0}', "hard_admissibility"),
        ("extra-preference", "unused", "preference"),
    ))
    constructed_under_other_policy = application.revolute_drive_service.construct_candidate(
        request,
        other_policy,
        template(DriveArchitecture.DIRECT_DRIVE),
    )
    assert constructed_under_other_policy.candidate is not None

    def substitute_construction(*args, **kwargs):
        return constructed_under_other_policy

    def refuse_currentness(*args, **kwargs):
        raise AssertionError("currentness must not be consulted for a forged candidate")

    def refuse_evaluation(*args, **kwargs):
        raise AssertionError("pure evaluation must not run for a forged candidate")

    monkeypatch.setattr(application.revolute_drive_service, "construct_candidate", substitute_construction)
    monkeypatch.setattr(application.candidate_currentness_service, "evaluate", refuse_currentness)
    monkeypatch.setattr(application.revolute_drive_service, "evaluate", refuse_evaluation)

    with pytest.raises(CandidateIntegrityError, match="policy hash mismatch"):
        application.realize_and_evaluate_revolute_drive(
            request=request,
            policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
            template_input=template(DriveArchitecture.DIRECT_DRIVE),
            requirements=requirements(),
        )


@pytest.mark.parametrize(
    "non_current",
    [CandidateCurrentness.STALE_RELATIVE_TO_CURRENT_STATE, CandidateCurrentness.CURRENTNESS_UNAVAILABLE],
)
def test_non_current_candidate_fails_closed_operationally_before_evaluation(tmp_path, monkeypatch, non_current):
    application = build_application(tmp_path)

    def substitute_currentness(*args, **kwargs):
        return non_current

    def refuse_evaluation(*args, **kwargs):
        raise AssertionError("pure evaluation must not run for a non-current candidate")

    monkeypatch.setattr(application.candidate_currentness_service, "evaluate", substitute_currentness)
    monkeypatch.setattr(application.revolute_drive_service, "evaluate", refuse_evaluation)

    with pytest.raises(CandidateIntegrityError, match="currentness"):
        application.realize_and_evaluate_revolute_drive(
            request=make_request(application),
            policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
            template_input=template(DriveArchitecture.DIRECT_DRIVE),
            requirements=requirements(),
        )


def test_stale_source_binding_fails_closed_before_any_construction(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    stale_request = make_request(application)
    advanced = production_state().model_copy(update={"revision": 2})
    application.state_manager.create_revision(application.project_id, advanced)

    def refuse_construction(*args, **kwargs):
        raise AssertionError("pure construction must not run against a stale source binding")

    monkeypatch.setattr(application.revolute_drive_service, "construct_candidate", refuse_construction)

    with pytest.raises(ValueError, match="mismatch"):
        application.realize_and_evaluate_revolute_drive(
            request=stale_request,
            policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
            template_input=template(DriveArchitecture.DIRECT_DRIVE),
            requirements=requirements(),
        )

    assert application.state_manager.load_current_state(application.project_id).revision == 2


def test_change_engine_and_publication_are_never_invoked_by_revolute_drive_operations(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    invoked: list[str] = []

    def refuse(name):
        def _spy(*args, **kwargs):
            invoked.append(name)
            raise AssertionError(f"{name} must not be invoked")

        return _spy

    monkeypatch.setattr(application.change_engine, "prepare_proposal", refuse("prepare_proposal"))
    monkeypatch.setattr(application.change_engine, "apply_proposal", refuse("apply_proposal"))
    monkeypatch.setattr(application.evidence_store, "write_evidence", refuse("write_evidence"))
    monkeypatch.setattr(application.candidate_publication_service, "publish", refuse("publish"))

    direct = run_direct(application)
    spur = run_spur(application)
    unresolved = run_incomplete(application)

    assert direct.evaluation is not None
    assert spur.evaluation is not None
    assert unresolved.evaluation is None
    assert invoked == []


def test_all_operations_create_nothing_on_disk_and_zero_new_revisions(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    before = workspace_snapshot(application.state_manager.workspace)

    run_direct(application)
    run_spur(application)
    run_incomplete(application)

    def substitute_currentness(*args, **kwargs):
        return CandidateCurrentness.STALE_RELATIVE_TO_CURRENT_STATE

    monkeypatch.setattr(application.candidate_currentness_service, "evaluate", substitute_currentness)
    with pytest.raises(CandidateIntegrityError):
        application.realize_and_evaluate_revolute_drive(
            request=make_request(application),
            policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
            template_input=template(DriveArchitecture.DIRECT_DRIVE),
            requirements=requirements(),
        )

    after = workspace_snapshot(application.state_manager.workspace)
    assert after == before
    assert application.state_manager.load_current_state(application.project_id).revision == 1


def test_revolute_drive_service_composition_is_read_only_and_pure(tmp_path):
    application = build_application(tmp_path)

    assert isinstance(application.revolute_drive_service, RevoluteDriveRealizationService)
    assert vars(application.revolute_drive_service) == {}
    assert "revolute_drive_service" in ProductionApplication._READ_ONLY_DEPENDENCIES
    with pytest.raises(AttributeError):
        application.revolute_drive_service = RevoluteDriveRealizationService()
