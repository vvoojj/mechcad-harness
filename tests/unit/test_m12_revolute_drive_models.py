from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from mechcad_harness.candidates import (
    CandidateDesignVariable,
    ComponentSpecificationSnapshot,
)
from tests.unit.test_m12_candidate_foundation import _candidate
from mechcad_harness.revolute_drive import (
    ConsumedPropertyBinding,
    DriveAdmissibility,
    DriveArchitecture,
    EngineeringCheck,
    EngineeringCheckStatus,
    InputProvenanceKind,
    RevoluteDriveAdmissibilityResult,
    RevoluteDriveConstructionOutcome,
    RevoluteDriveEngineeringRequirements,
    RevoluteDriveTemplateInput,
    ShaftSupportGeometry,
    SourceBoundScalar,
    TrustedCanonicalScalarSourceBinding,
    StaticOutputShaftDesignLoadCase,
)


def scalar(value: float, unit: str = "N*m", *, provenance=InputProvenanceKind.SOURCE_AUTHORITY, source_path="/requirements/design_torque"):
    return SourceBoundScalar(value=value, unit=unit, provenance=provenance, source_path=source_path)


def test_models_are_frozen_and_forbid_extra_fields():
    value = scalar(2.0)
    with pytest.raises((ValidationError, TypeError)):
        value.value = 3.0
    with pytest.raises(ValidationError):
        SourceBoundScalar(value=2.0, unit="N*m", provenance=InputProvenanceKind.SOURCE_AUTHORITY, source_path="/x", extra="nope")


def test_source_and_policy_scalar_provenance_are_explicit():
    source = scalar(24.0, "V")
    policy = scalar(
        0.95,
        "1",
        provenance=InputProvenanceKind.POLICY_ASSUMPTION,
        source_path=None,
    )
    assert source.provenance is InputProvenanceKind.SOURCE_AUTHORITY
    assert source.source_path == "/requirements/design_torque"
    assert policy.provenance is InputProvenanceKind.POLICY_ASSUMPTION
    assert policy.source_path is None


def test_source_scalar_value_hash_is_self_consistent_and_rejects_stale_values():
    source = scalar(24.0, "V")
    assert source.source_value_hash is not None

    changed = source.model_dump(mode="json")
    changed["value"] = 48.0
    with pytest.raises(ValidationError, match="source scalar value hash mismatch"):
        SourceBoundScalar.model_validate(changed)

    policy = scalar(
        0.95,
        "1",
        provenance=InputProvenanceKind.POLICY_ASSUMPTION,
        source_path=None,
    )
    assert policy.source_value_hash is None


def test_trusted_scalar_binding_is_explicitly_anchored_to_a_composite_source_record():
    binding = TrustedCanonicalScalarSourceBinding(
        source_path="/requirements/0",
        source_record_hash="sha256:" + "1" * 64,
        value=24.0,
        unit="V",
        source_identity="fixture:trusted-scalar@1",
    )
    assert binding.source_value_hash is not None
    assert binding.binding_hash.startswith("sha256:")


def test_trusted_scalar_binding_rejects_a_stale_scalar_hash():
    binding = TrustedCanonicalScalarSourceBinding(
        source_path="/requirements/0",
        source_record_hash="sha256:" + "1" * 64,
        value=24.0,
        unit="V",
        source_identity="fixture:trusted-scalar@1",
    )
    payload = binding.model_dump(mode="json")
    payload["value"] = 999.0
    with pytest.raises(ValidationError, match="source scalar value hash mismatch"):
        TrustedCanonicalScalarSourceBinding.model_validate(payload)


def test_source_paths_use_literal_canonical_path_rules():
    for path in ("/a//b", "/a~b", "/"):
        with pytest.raises(ValidationError):
            scalar(1.0, source_path=path)
    with pytest.raises(ValidationError):
        EngineeringCheck(
            check_id="path",
            status=EngineeringCheckStatus.SATISFIED,
            consumed_requirement_paths=("/requirements//speed",),
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_scalar_rejects_nonfinite_values(value):
    with pytest.raises(ValidationError):
        scalar(value)


@pytest.mark.parametrize("field", ["required_voltage", "required_peak_torque", "efficiency", "safety_factor"])
def test_positive_requirement_scalars_reject_nonpositive_values(field):
    value = scalar(0.0, "V" if field == "required_voltage" else "1" if field in {"efficiency", "safety_factor"} else "N*m", provenance=InputProvenanceKind.POLICY_ASSUMPTION, source_path=None)
    with pytest.raises(ValidationError):
        RevoluteDriveEngineeringRequirements(
            required_output_speed=scalar(10.0, "rpm"),
            design_load_case=StaticOutputShaftDesignLoadCase(design_torque=scalar(4.0)),
            trusted_source_scalar_bindings=(),
            **{field: value},
        )


def test_speed_scalar_contract_requires_rpm_and_allows_zero_only_for_speed():
    requirements = RevoluteDriveEngineeringRequirements(
        required_output_speed=scalar(0.0, "rpm"),
        design_load_case=StaticOutputShaftDesignLoadCase(
            design_torque=scalar(4.0),
            transverse_force_y=scalar(0.0, "N"),
            transverse_force_z=scalar(0.0, "N"),
        ),
        trusted_source_scalar_bindings=(),
    )
    assert requirements.required_output_speed.value == 0.0
    with pytest.raises(ValidationError):
        RevoluteDriveEngineeringRequirements(
            required_output_speed=scalar(1.0, "rad/s"),
            design_load_case=requirements.design_load_case,
            trusted_source_scalar_bindings=(),
        )


@pytest.mark.parametrize("efficiency", [0.0, -0.1, 1.1, math.nan, math.inf])
def test_efficiency_must_be_finite_in_open_closed_unit_interval(efficiency):
    with pytest.raises(ValidationError):
        RevoluteDriveEngineeringRequirements(
            required_output_speed=scalar(10.0, "rpm"),
            design_load_case=StaticOutputShaftDesignLoadCase(design_torque=scalar(4.0)),
            efficiency=scalar(efficiency, "1", provenance=InputProvenanceKind.POLICY_ASSUMPTION, source_path=None),
            trusted_source_scalar_bindings=(),
        )


@pytest.mark.parametrize("factor", [0.0, -1.0, math.nan, math.inf])
def test_safety_factor_must_be_finite_and_positive(factor):
    with pytest.raises(ValidationError):
        RevoluteDriveEngineeringRequirements(
            required_output_speed=scalar(10.0, "rpm"),
            design_load_case=StaticOutputShaftDesignLoadCase(design_torque=scalar(4.0)),
            safety_factor=scalar(factor, "1", provenance=InputProvenanceKind.POLICY_ASSUMPTION, source_path=None),
            trusted_source_scalar_bindings=(),
        )


def test_load_case_requires_one_explicit_vector_or_spur_derivation():
    base = dict(design_torque=scalar(4.0))
    explicit = StaticOutputShaftDesignLoadCase(
        **base,
        transverse_force_y=scalar(12.0, "N"),
        transverse_force_z=scalar(-3.0, "N"),
    )
    derived = StaticOutputShaftDesignLoadCase(**base, derive_transverse_load_from_spur_mesh=True)
    assert explicit.transverse_force_y.value == 12.0
    assert derived.derive_transverse_load_from_spur_mesh is True
    with pytest.raises(ValidationError):
        StaticOutputShaftDesignLoadCase(**base)
    with pytest.raises(ValidationError):
        StaticOutputShaftDesignLoadCase(
            **base,
            transverse_force_y=scalar(1.0, "N"),
            transverse_force_z=scalar(1.0, "N"),
            derive_transverse_load_from_spur_mesh=True,
        )


def test_support_geometry_is_ordered_and_load_plane_is_between_supports():
    geometry = ShaftSupportGeometry(
        support_a_x=scalar(10.0, "mm", source_path="/geometry/support_a_x"),
        support_b_x=scalar(110.0, "mm", source_path="/geometry/support_b_x"),
        load_plane_x=scalar(60.0, "mm", source_path="/geometry/load_plane_x"),
    )
    assert geometry.support_a_x.value < geometry.load_plane_x.value < geometry.support_b_x.value
    with pytest.raises(ValidationError):
        ShaftSupportGeometry(
            support_a_x=scalar(110.0, "mm", source_path="/geometry/support_a_x"),
            support_b_x=scalar(10.0, "mm", source_path="/geometry/support_b_x"),
            load_plane_x=scalar(60.0, "mm", source_path="/geometry/load_plane_x"),
        )
    with pytest.raises(ValidationError):
        ShaftSupportGeometry(
            support_a_x=scalar(10.0, "mm", source_path="/geometry/support_a_x"),
            support_b_x=scalar(110.0, "mm", source_path="/geometry/support_b_x"),
            load_plane_x=scalar(120.0, "mm", source_path="/geometry/load_plane_x"),
        )
    with pytest.raises(ValidationError):
        ShaftSupportGeometry(support_a_x=10.0, support_b_x=110.0, load_plane_x=60.0)


def test_load_case_has_no_duplicate_load_plane_coordinate():
    with pytest.raises(ValidationError):
        StaticOutputShaftDesignLoadCase(
            design_torque=scalar(4.0),
            load_plane_x=scalar(10.0, "mm"),
            derive_transverse_load_from_spur_mesh=True,
        )


def test_template_input_keeps_supplied_specifications_and_explicit_ids():
    specification = ComponentSpecificationSnapshot(component_type="motor", source_identity="fixture:motor")
    template = RevoluteDriveTemplateInput(
        architecture=DriveArchitecture.DIRECT_DRIVE,
        joint_id="J-1",
        motor_instance_id="motor",
        motor_specification=specification,
        shaft_instance_id="shaft",
        bearing_a_instance_id="bearing-a",
        bearing_b_instance_id="bearing-b",
        hub_instance_id="hub",
        mount_instance_id="mount",
        driven_body_instance_id="body",
        axis_frame_reference="joint:J-1=shaft-axis",
    )
    assert template.motor_specification.specification_hash == specification.specification_hash
    with pytest.raises(ValidationError):
        RevoluteDriveTemplateInput.model_validate({**template.model_dump(mode="json"), "unexpected": "forbidden"})


@pytest.mark.parametrize(
    "field",
    [
        "joint_id",
        "axis_frame_reference",
        "motor_instance_id",
        "shaft_instance_id",
        "bearing_a_instance_id",
        "bearing_b_instance_id",
        "hub_instance_id",
        "mount_instance_id",
        "driven_body_instance_id",
        "driver_gear_instance_id",
        "driven_gear_instance_id",
    ],
)
def test_template_rejects_whitespace_in_every_supplied_identifier(field):
    specification = ComponentSpecificationSnapshot(component_type="motor", source_identity="fixture:motor")
    values = dict(
        architecture=DriveArchitecture.DIRECT_DRIVE,
        joint_id="J-1",
        motor_instance_id="motor",
        motor_specification=specification,
        shaft_instance_id="shaft",
        bearing_a_instance_id="bearing-a",
        bearing_b_instance_id="bearing-b",
        hub_instance_id="hub",
        mount_instance_id="mount",
        driven_body_instance_id="body",
        axis_frame_reference="joint:J-1=shaft-axis",
    )
    values[field] = "bad value"
    with pytest.raises(ValidationError):
        RevoluteDriveTemplateInput(**values)


def test_template_rejects_whitespace_in_support_mount_identifiers():
    with pytest.raises(ValidationError):
        RevoluteDriveTemplateInput(
            architecture=DriveArchitecture.DIRECT_DRIVE,
            joint_id="J-1",
            support_mount_instance_ids=("support mount",),
        )


def test_unresolved_construction_is_valid_without_candidate():
    outcome = RevoluteDriveConstructionOutcome(status=DriveAdmissibility.UNRESOLVED, reason="missing shaft")
    assert outcome.candidate is None


def test_construction_outcome_status_and_candidate_are_consistent_in_both_directions():
    candidate = _candidate()[0]
    with pytest.raises(ValidationError):
        RevoluteDriveConstructionOutcome(status=DriveAdmissibility.ADMISSIBLE)
    with pytest.raises(ValidationError):
        RevoluteDriveConstructionOutcome(
            candidate=candidate,
            status=DriveAdmissibility.UNRESOLVED,
            reason="missing shaft",
        )


def test_result_hash_is_deterministic_and_excludes_its_own_hash():
    check = EngineeringCheck(
        check_id="motor-continuous-torque",
        status=EngineeringCheckStatus.SATISFIED,
        reason=None,
        consumed_property_bindings=(
            ConsumedPropertyBinding(
                component_instance_id="motor",
                specification_hash="sha256:" + "1" * 64,
                property_key="motor.continuous_torque_nm",
                property_hash="sha256:" + "2" * 64,
                source_identity="datasheet:fixture",
                authority="manufacturer_datasheet",
            ),
        ),
    )
    payload = dict(
        candidate_hash="sha256:" + "3" * 64,
        source_binding_hash="sha256:" + "4" * 64,
        synthesis_request_hash="sha256:" + "5" * 64,
        synthesis_policy_hash="sha256:" + "6" * 64,
        requirements_hash="sha256:" + "7" * 64,
        design_variables=(CandidateDesignVariable(name="shaft-diameter", value=12.0),),
        calculation_id="m12-3.revolute-drive",
        calculation_version="1",
        checks=(check,),
    )
    first = RevoluteDriveAdmissibilityResult(**payload)
    second = RevoluteDriveAdmissibilityResult(**{**payload, "result_hash": first.result_hash})
    assert first.result_hash == second.result_hash
    assert first.status is DriveAdmissibility.ADMISSIBLE
    with pytest.raises(ValidationError):
        RevoluteDriveAdmissibilityResult(**{**payload, "result_hash": "sha256:" + "0" * 64})


def test_requirements_hash_is_deterministic_and_excludes_its_own_hash():
    load_case = StaticOutputShaftDesignLoadCase(design_torque=scalar(4.0), derive_transverse_load_from_spur_mesh=True)
    geometry = ShaftSupportGeometry(
        support_a_x=scalar(10.0, "mm", source_path="/geometry/support_a_x"),
        support_b_x=scalar(110.0, "mm", source_path="/geometry/support_b_x"),
        load_plane_x=scalar(60.0, "mm", source_path="/geometry/load_plane_x"),
    )
    first = RevoluteDriveEngineeringRequirements(
        required_output_speed=scalar(10.0, "rpm"),
        design_load_case=load_case,
        shaft_support_geometry=geometry,
        trusted_source_scalar_bindings=(),
    )
    second = RevoluteDriveEngineeringRequirements.model_validate(first.model_dump(mode="json"))
    assert first.requirements_hash == second.requirements_hash
    changed = first.model_dump(mode="json")
    changed["requirements_hash"] = "pending"
    changed["required_output_speed"]["value"] = 20.0
    changed["required_output_speed"]["source_value_hash"] = None
    assert RevoluteDriveEngineeringRequirements.model_validate(changed).requirements_hash != first.requirements_hash
    forged = first.model_dump(mode="json")
    forged["requirements_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError):
        RevoluteDriveEngineeringRequirements.model_validate(forged)
