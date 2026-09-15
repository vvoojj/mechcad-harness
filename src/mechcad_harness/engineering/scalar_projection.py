from __future__ import annotations

import hashlib
import math
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.models.common import Model

from .keys import SupportedConstraintKey
from .values import OutputAngularSpeedValue


_HASH_PREFIX = "sha256:"
_OUTPUT_SPEED_RULE = "authoritative-output-angular-speed-rad-s@1"


def _hash_payload(payload: dict[str, Any]) -> str:
    from mechcad_harness.state.hashing import canonical_json

    return _HASH_PREFIX + hashlib.sha256(canonical_json(payload)).hexdigest()


def _require_hash(value: str) -> str:
    if len(value) != 71 or not value.startswith(_HASH_PREFIX):
        raise ValueError("must be a sha256 hash")
    if any(character not in "0123456789abcdef" for character in value[7:]):
        raise ValueError("must be a sha256 hash")
    return value


class AuthoritativeParameterLocator(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str = Field(min_length=1)
    parameter_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str

    _validate_hash = field_validator("source_state_hash")(_require_hash)


class CanonicalScalarProjection(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: AuthoritativeParameterLocator
    authoritative_key: SupportedConstraintKey
    authoritative_parameter_hash: str
    value: float
    unit: str = Field(min_length=1)
    projection_rule_id: str = Field(min_length=1)
    projection_hash: str

    _validate_parameter_hash = field_validator("authoritative_parameter_hash")(_require_hash)
    _validate_projection_hash = field_validator("projection_hash")(_require_hash)

    @field_validator("value", mode="before")
    @classmethod
    def validate_finite(cls, value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("projection value must be numeric")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("projection value must be finite")
        return value

    @model_validator(mode="after")
    def validate_hash(self) -> CanonicalScalarProjection:
        if self.projection_hash != projection_hash(self):
            raise ValueError("projection hash mismatch")
        return self


def authoritative_parameter_hash(parameter: Any) -> str:
    payload = parameter.model_dump(mode="json")
    return _hash_payload(payload)


def projection_hash(projection: CanonicalScalarProjection | dict[str, Any]) -> str:
    payload = (
        projection.model_dump(mode="json")
        if isinstance(projection, CanonicalScalarProjection)
        else dict(projection)
    )
    if hasattr(payload.get("source"), "model_dump"):
        payload["source"] = payload["source"].model_dump(mode="json")
    payload.pop("projection_hash", None)
    return _hash_payload(payload)


def project_authoritative_scalar(
    expected_project_id: str,
    source_state,
    locator: AuthoritativeParameterLocator,
) -> CanonicalScalarProjection:
    if not isinstance(expected_project_id, str) or not expected_project_id.strip():
        raise ValueError("expected project identity is required")
    if locator.project_id != expected_project_id:
        raise ValueError("authoritative parameter locator project mismatch")
    if source_state.revision != locator.source_revision:
        raise ValueError("authoritative parameter locator revision mismatch")

    from mechcad_harness.models.design import AuthoritativeParameter
    from mechcad_harness.state.hashing import state_hash

    actual_state_hash = state_hash(source_state)
    if actual_state_hash != locator.source_state_hash:
        raise ValueError("authoritative parameter locator state hash mismatch")

    matches = [
        parameter
        for parameter in source_state.authoritative_parameters
        if parameter.id == locator.parameter_id
    ]
    if len(matches) != 1:
        raise ValueError("authoritative parameter ID must resolve to exactly one parameter")

    try:
        parameter = AuthoritativeParameter.model_validate(matches[0].model_dump(mode="json"))
    except Exception as exc:
        raise ValueError("authoritative parameter validation failed") from exc

    if (
        parameter.key is not SupportedConstraintKey.OUTPUT_ANGULAR_SPEED
        or not isinstance(parameter.value, OutputAngularSpeedValue)
    ):
        raise ValueError("unsupported authoritative scalar projection")

    fields: dict[str, Any] = {
        "source": locator,
        "authoritative_key": parameter.key,
        "authoritative_parameter_hash": authoritative_parameter_hash(parameter),
        "value": parameter.value.value_rad_s,
        "unit": "rad/s",
        "projection_rule_id": _OUTPUT_SPEED_RULE,
    }
    fields["projection_hash"] = projection_hash(fields)
    return CanonicalScalarProjection.model_validate(fields)


def verify_canonical_scalar_projection(
    expected_project_id: str,
    source_state,
    projection: CanonicalScalarProjection,
) -> CanonicalScalarProjection:
    claim = CanonicalScalarProjection.model_validate(projection.model_dump(mode="json"))
    expected = project_authoritative_scalar(expected_project_id, source_state, claim.source)
    if claim != expected:
        raise ValueError("canonical scalar projection does not match recomputation")
    return expected


__all__ = [
    "AuthoritativeParameterLocator",
    "CanonicalScalarProjection",
    "authoritative_parameter_hash",
    "project_authoritative_scalar",
    "projection_hash",
    "verify_canonical_scalar_projection",
]
