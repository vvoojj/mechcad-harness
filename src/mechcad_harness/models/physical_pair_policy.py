from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Iterable, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .common import Model


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _hash_payload(payload: dict[str, object]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def _require_hash_or_pending(value: str) -> str:
    if value == "pending":
        return value
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError("must be a sha256 hash")
    return value


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _require_optional_nonblank(value: str | None) -> str | None:
    return None if value is None else _require_nonblank(value)


class PhysicalPairClassification(StrEnum):
    CHECK_CLEARANCE = "check_clearance"
    INTENDED_CONTACT_EXCLUDED = "intended_contact_excluded"
    SAME_RIGID_GROUP_EXCLUDED = "same_rigid_group_excluded"
    UNMODELED_MOTION_OUT_OF_SCOPE = "unmodeled_motion_out_of_scope"
    OTHER_EXPLICIT_OUT_OF_SCOPE = "other_explicit_out_of_scope"


class PhysicalPairClassificationBinding(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["physical-pair-classification-binding@1"] = (
        "physical-pair-classification-binding@1"
    )
    first_physical_instance_id: str = Field(min_length=1)
    second_physical_instance_id: str = Field(min_length=1)
    classification: PhysicalPairClassification
    exclusion_reason: str | None
    binding_hash: str = "pending"

    _validate_ids = field_validator(
        "first_physical_instance_id", "second_physical_instance_id", "exclusion_reason"
    )(_require_optional_nonblank)
    _validate_hash = field_validator("binding_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_pair_and_hash(self) -> "PhysicalPairClassificationBinding":
        first, second = self.first_physical_instance_id, self.second_physical_instance_id
        if first == second:
            raise ValueError("physical pair must contain two distinct instances")
        if first > second:
            object.__setattr__(self, "first_physical_instance_id", second)
            object.__setattr__(self, "second_physical_instance_id", first)
        if self.classification is PhysicalPairClassification.CHECK_CLEARANCE:
            if self.exclusion_reason is not None:
                raise ValueError("checked physical pairs cannot carry an exclusion reason")
        elif self.exclusion_reason is None:
            raise ValueError("excluded physical pairs require an explicit reason")

        expected = _hash_payload(
            {
                "schema_version": self.schema_version,
                "first_physical_instance_id": self.first_physical_instance_id,
                "second_physical_instance_id": self.second_physical_instance_id,
                "classification": self.classification.value,
                "exclusion_reason": self.exclusion_reason,
            }
        )
        if self.binding_hash == "pending":
            object.__setattr__(self, "binding_hash", expected)
        elif self.binding_hash != expected:
            raise ValueError("physical pair classification binding hash mismatch")
        return self


def canonical_physical_pair_classification_bindings(
    bindings: Iterable[PhysicalPairClassificationBinding],
) -> tuple[PhysicalPairClassificationBinding, ...]:
    canonical = tuple(
        sorted(
            bindings,
            key=lambda binding: (
                binding.first_physical_instance_id,
                binding.second_physical_instance_id,
            ),
        )
    )
    pairs = tuple(
        (binding.first_physical_instance_id, binding.second_physical_instance_id)
        for binding in canonical
    )
    if len(set(pairs)) != len(pairs):
        raise ValueError("physical pair classification bindings must contain unique pairs")
    return canonical


def physical_pair_classification_set_hash(
    bindings: Iterable[PhysicalPairClassificationBinding],
) -> str:
    canonical = canonical_physical_pair_classification_bindings(bindings)
    return _hash_payload(
        {
            "schema_version": "physical-pair-classification-set@1",
            "binding_hashes": sorted(binding.binding_hash for binding in canonical),
        }
    )


__all__ = [
    "PhysicalPairClassification",
    "PhysicalPairClassificationBinding",
    "canonical_physical_pair_classification_bindings",
    "physical_pair_classification_set_hash",
]
