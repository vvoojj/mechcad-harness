from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .common import Model
from mechcad_harness.multi_joint_kinematics import JointConfiguration, joint_configuration_hash


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _require_hash_or_pending(value: str) -> str:
    if value == "pending":
        return value
    if len(value) != 71 or not value.startswith("sha256:") or any(
        character not in "0123456789abcdef" for character in value[7:]
    ):
        raise ValueError("must be a sha256 hash")
    return value


class MultiJointVerificationConfigurationSet(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["multi-joint-verification-configuration-set@1"] = (
        "multi-joint-verification-configuration-set@1"
    )
    configurations: tuple[JointConfiguration, ...] = Field(min_length=1)
    configuration_hashes: tuple[str, ...] = Field(min_length=1)
    configuration_set_hash: str = "pending"

    _validate_hash = field_validator("configuration_set_hash")(_require_hash_or_pending)

    @model_validator(mode="before")
    @classmethod
    def default_configuration_hashes(cls, data):
        values = dict(data)
        if "configuration_hashes" not in values and "configurations" in values:
            configurations = tuple(
                item
                if isinstance(item, JointConfiguration)
                else JointConfiguration.model_validate(item)
                for item in values["configurations"]
            )
            values["configuration_hashes"] = tuple(
                joint_configuration_hash(configuration) for configuration in configurations
            )
        return values

    @model_validator(mode="after")
    def validate_configuration_set(self) -> "MultiJointVerificationConfigurationSet":
        if self.schema_version != "multi-joint-verification-configuration-set@1":
            raise ValueError("unsupported multi-joint verification configuration-set schema")
        expected_hashes = tuple(
            joint_configuration_hash(configuration) for configuration in self.configurations
        )
        if self.configuration_hashes != expected_hashes:
            raise ValueError("configuration hashes do not match configurations")
        expected_set_hash = configuration_set_hash(self)
        if self.configuration_set_hash == "pending":
            object.__setattr__(self, "configuration_set_hash", expected_set_hash)
        elif self.configuration_set_hash != expected_set_hash:
            raise ValueError("configuration set hash mismatch")
        return self


def configuration_set_hash(value: MultiJointVerificationConfigurationSet) -> str:
    if not isinstance(value, MultiJointVerificationConfigurationSet):
        raise TypeError("configuration set hash requires a configuration set")
    if value.schema_version != "multi-joint-verification-configuration-set@1":
        raise ValueError("unsupported multi-joint verification configuration-set schema")
    configurations = tuple(
        JointConfiguration.model_validate(item.model_dump(mode="json"))
        for item in value.configurations
    )
    if configurations != value.configurations:
        raise ValueError("configuration set contains invalid configuration records")
    expected_hashes = tuple(joint_configuration_hash(item) for item in configurations)
    if value.configuration_hashes != expected_hashes:
        raise ValueError("configuration hashes do not match configurations")
    return _hash_payload(
        {
            "schema_version": "multi-joint-verification-configuration-set@1",
            "configurations": [
                configuration.model_dump(mode="json") for configuration in configurations
            ],
        }
    )


__all__ = ["MultiJointVerificationConfigurationSet", "configuration_set_hash"]
