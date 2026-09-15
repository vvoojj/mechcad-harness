from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mechcad_harness.engineering import SupportedConstraintKey
from mechcad_harness.engineering.scalar_projection import (
    AuthoritativeParameterLocator,
    CanonicalScalarProjection,
    authoritative_parameter_hash,
    project_authoritative_scalar,
    projection_hash,
    verify_canonical_scalar_projection,
)
from mechcad_harness.engineering.values import MotorCharacteristicsValue, OutputAngularSpeedValue
from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter, DesignState
from mechcad_harness.state import state_hash


PROJECT_ID = "PRJ-PROJECTION"
_TIME = datetime(2026, 9, 15, tzinfo=timezone.utc)


def parameter(
    *,
    parameter_id: str = "PARAM-SPEED",
    value_rad_s: float = 2.5,
    value=None,
    key: SupportedConstraintKey = SupportedConstraintKey.OUTPUT_ANGULAR_SPEED,
):
    anchor_id = (
        "REQ-TRANSMISSION-MOTOR-CHARACTERISTICS"
        if key is SupportedConstraintKey.MOTOR_CHARACTERISTICS
        else "REQ-TRANSMISSION-OUTPUT-SPEED"
    )
    return AuthoritativeParameter(
        id=parameter_id,
        anchor=AuthoritativeAnchor(kind="requirement", id=anchor_id),
        scope_id="transmission",
        key=key,
        value=value or OutputAngularSpeedValue(
            kind=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED.value,
            value_rad_s=value_rad_s,
        ),
        source_resolution_id="RES-SPEED",
    )


def source_state(*parameters: AuthoritativeParameter) -> DesignState:
    return DesignState(
        id="DES-PROJECTION",
        revision=3,
        created_at=_TIME,
        authoritative_parameters=list(parameters),
    )


def locator(state: DesignState, *, project_id: str = PROJECT_ID, parameter_id: str = "PARAM-SPEED"):
    return AuthoritativeParameterLocator(
        project_id=project_id,
        parameter_id=parameter_id,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
    )


def test_projector_resolves_one_output_speed_by_id_and_hashes_full_parameter():
    state = source_state(parameter())
    result = project_authoritative_scalar(PROJECT_ID, state, locator(state))

    assert result.source.parameter_id == "PARAM-SPEED"
    assert result.authoritative_key is SupportedConstraintKey.OUTPUT_ANGULAR_SPEED
    assert result.authoritative_parameter_hash == authoritative_parameter_hash(state.authoritative_parameters[0])
    assert result.value == 2.5
    assert result.unit == "rad/s"
    assert result.projection_rule_id == "authoritative-output-angular-speed-rad-s@1"
    assert result.projection_hash == projection_hash(result)


@pytest.mark.parametrize(
    ("project_id", "revision", "state_hash_value"),
    [
        ("OTHER", 3, None),
        (PROJECT_ID, 4, None),
        (PROJECT_ID, 3, "sha256:" + "0" * 64),
    ],
)
def test_projector_rejects_locator_identity_mismatches(project_id, revision, state_hash_value):
    state = source_state(parameter())
    current_locator = locator(state, project_id=project_id)
    if revision != state.revision:
        current_locator = current_locator.model_copy(update={"source_revision": revision})
    if state_hash_value is not None:
        current_locator = current_locator.model_copy(update={"source_state_hash": state_hash_value})

    with pytest.raises(ValueError):
        project_authoritative_scalar(PROJECT_ID, state, current_locator)


def test_projector_rejects_missing_and_duplicate_parameter_ids():
    state = source_state(parameter(parameter_id="OTHER"))
    with pytest.raises(ValueError, match="exactly one"):
        project_authoritative_scalar(PROJECT_ID, state, locator(state))

    duplicate = source_state(parameter(), parameter())
    with pytest.raises(ValueError, match="exactly one"):
        project_authoritative_scalar(PROJECT_ID, duplicate, locator(duplicate))


def test_projector_rejects_unsupported_typed_authority():
    unsupported = MotorCharacteristicsValue(
        kind=SupportedConstraintKey.MOTOR_CHARACTERISTICS.value,
        motor_id="MOTOR-1",
        speed_min_rpm=1.0,
        speed_max_rpm=100.0,
        continuous_torque_nm=1.0,
        peak_torque_nm=2.0,
    )
    state = source_state(
        parameter(value=unsupported, key=SupportedConstraintKey.MOTOR_CHARACTERISTICS)
    )

    with pytest.raises(ValueError, match="unsupported"):
        project_authoritative_scalar(PROJECT_ID, state, locator(state))


def test_projection_claim_must_match_fresh_recomputation():
    state = source_state(parameter())
    claim = project_authoritative_scalar(PROJECT_ID, state, locator(state))
    changed = claim.model_dump(mode="json")
    changed["value"] = 9.0
    changed["projection_hash"] = projection_hash(changed)
    tampered = CanonicalScalarProjection.model_validate(changed)

    with pytest.raises(ValueError, match="does not match"):
        verify_canonical_scalar_projection(PROJECT_ID, state, tampered)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authoritative_key", SupportedConstraintKey.MOTOR_CHARACTERISTICS.value),
        ("value", 9.0),
        ("unit", "deg/s"),
        ("projection_rule_id", "other-rule@1"),
        ("authoritative_parameter_hash", "sha256:" + "0" * 64),
    ],
)
def test_rehashed_projection_claims_still_require_fresh_source_recomputation(field, value):
    state = source_state(parameter())
    claim = project_authoritative_scalar(PROJECT_ID, state, locator(state))
    changed = claim.model_dump(mode="json")
    changed[field] = value
    changed["projection_hash"] = projection_hash(changed)
    tampered = CanonicalScalarProjection.model_validate(changed)

    with pytest.raises(ValueError, match="does not match"):
        verify_canonical_scalar_projection(PROJECT_ID, state, tampered)


def test_projection_hash_rejects_tampered_record():
    state = source_state(parameter())
    claim = project_authoritative_scalar(PROJECT_ID, state, locator(state))
    changed = claim.model_dump(mode="json")
    changed["value"] = 9.0

    with pytest.raises(ValidationError, match="projection hash mismatch"):
        CanonicalScalarProjection.model_validate(changed)
