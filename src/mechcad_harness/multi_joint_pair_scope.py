from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import ConfigDict, field_validator, model_validator

from mechcad_harness.models.common import Model


EXACT_CONSTITUENT_PAIR_SCOPE_VERSION = "exact-constituent-pair-scope@1.0"


class ExactConstituentPair(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["exact-constituent-pair@1"] = "exact-constituent-pair@1"
    first_instance_id: str
    second_instance_id: str

    @model_validator(mode="before")
    @classmethod
    def _normalize_operands(cls, data):
        data = dict(data)
        first = data.get("first_instance_id")
        second = data.get("second_instance_id")
        if isinstance(first, str) and isinstance(second, str):
            data["first_instance_id"], data["second_instance_id"] = sorted(
                (first, second)
            )
        return data

    @field_validator("first_instance_id", "second_instance_id")
    @classmethod
    def _require_nonblank_instance_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("instance IDs must not be blank")
        return value

    @model_validator(mode="after")
    def _require_strict_pair_order(self) -> "ExactConstituentPair":
        if self.first_instance_id >= self.second_instance_id:
            raise ValueError(
                "exact constituent pair IDs must be strictly ordered"
            )
        return self


def canonical_exact_pair_scope(
    pairs: tuple[ExactConstituentPair, ...],
) -> tuple[ExactConstituentPair, ...]:
    if not pairs:
        raise ValueError("exact constituent pair scope must not be empty")

    # model_copy(update=...) does not validate Pydantic models; rebuild each
    # record so canonicalization never trusts a forged or mutated instance.
    validated_pairs = tuple(
        ExactConstituentPair.model_validate(pair.model_dump()) for pair in pairs
    )
    pair_keys = [
        (pair.first_instance_id, pair.second_instance_id)
        for pair in validated_pairs
    ]
    seen: set[tuple[str, str]] = set()
    for pair_key in pair_keys:
        if pair_key in seen:
            raise ValueError(f"duplicate exact constituent pair: {pair_key!r}")
        seen.add(pair_key)

    return tuple(
        sorted(
            validated_pairs,
            key=lambda pair: (pair.first_instance_id, pair.second_instance_id),
        )
    )


def exact_pair_scope_hash(pairs: tuple[ExactConstituentPair, ...]) -> str:
    canonical_pairs = canonical_exact_pair_scope(pairs)
    payload = {
        "exact_pair_scope_version": EXACT_CONSTITUENT_PAIR_SCOPE_VERSION,
        "pairs": [pair.model_dump(mode="json") for pair in canonical_pairs],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


__all__ = [
    "EXACT_CONSTITUENT_PAIR_SCOPE_VERSION",
    "ExactConstituentPair",
    "canonical_exact_pair_scope",
    "exact_pair_scope_hash",
]
