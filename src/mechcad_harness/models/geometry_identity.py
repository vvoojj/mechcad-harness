from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import Model


def _require_sha256(value: str) -> str:
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError("must be a sha256 hash")
    if any(c not in "0123456789abcdef" for c in value[7:]):
        raise ValueError("must be a sha256 hash")
    return value


def reference_hash_payload(ref: dict) -> dict:
    payload = dict(ref)
    payload.pop("reference_hash", None)
    if payload.get("coordinate_system_id") is None:
        payload.pop("coordinate_system_id", None)
    return payload


def candidate_geometry_reference_payload(reference, *, m13: bool) -> dict:
    payload = {
        "artifact_id": reference.artifact_id,
        "artifact_hash": reference.artifact_hash,
        "source_identity": reference.source_identity,
        "format": reference.format,
    }
    if m13:
        payload["coordinate_system_id"] = reference.coordinate_system_id
        payload["reference_hash"] = reference.reference_hash
    return payload


def canonical_geometry_reference_payload(reference, *, m13: bool) -> dict:
    payload = {
        "artifact_id": reference.artifact_id,
        "artifact_hash": reference.artifact_hash,
        "source_identity": reference.source_identity,
        "format": reference.format,
        "reference_hash": reference.reference_hash,
    }
    if m13:
        payload["coordinate_system_id"] = reference.coordinate_system_id
    return payload


def geometry_identity_hash(identity: "GeometryArtifactIdentity") -> str:
    from mechcad_harness.state.hashing import canonical_json

    payload = geometry_identity_payload(identity)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def geometry_identity_payload(identity: "GeometryArtifactIdentity") -> dict:
    return {
        "artifact_id": identity.artifact_id,
        "artifact_hash": identity.artifact_hash,
        "source_identity": identity.source_identity,
        "format": identity.format,
        "coordinate_system_id": identity.coordinate_system_id,
    }


def geometry_reference_hash(identity: "GeometryArtifactIdentity") -> str:
    """Return the enclosing geometry-reference hash for an identity projection."""
    from mechcad_harness.state.hashing import canonical_json

    payload = reference_hash_payload(geometry_identity_payload(identity))
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


class GeometryArtifactIdentity(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    artifact_id: str = Field(min_length=1)
    artifact_hash: str
    source_identity: str = Field(min_length=1)
    format: Literal["step"] = "step"
    coordinate_system_id: str | None = None
    geometry_identity_hash: str = "pending"

    @field_validator("artifact_id", "source_identity")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty or whitespace")
        return value

    @field_validator("artifact_hash")
    @classmethod
    def _hash(cls, value: str) -> str:
        return _require_sha256(value)

    @field_validator("coordinate_system_id")
    @classmethod
    def _coordinate(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("coordinate_system_id must not be empty")
        return value

    @model_validator(mode="after")
    def _validate(self) -> "GeometryArtifactIdentity":
        expected = geometry_identity_hash(self)
        if self.geometry_identity_hash == "pending":
            object.__setattr__(self, "geometry_identity_hash", expected)
        elif self.geometry_identity_hash != expected:
            raise ValueError("geometry identity hash mismatch")
        return self

    @classmethod
    def from_fields(
        cls, artifact_id: str, artifact_hash: str, source_identity: str,
        format: str = "step", coordinate_system_id: str | None = None,
    ) -> "GeometryArtifactIdentity":
        return cls(
            artifact_id=artifact_id, artifact_hash=artifact_hash,
            source_identity=source_identity, format=format,
            coordinate_system_id=coordinate_system_id,
        )

    @classmethod
    def from_candidate(cls, ref) -> "GeometryArtifactIdentity":
        return cls.from_fields(
            artifact_id=ref.artifact_id,
            artifact_hash=ref.artifact_hash,
            source_identity=ref.source_identity,
            format=ref.format,
            coordinate_system_id=getattr(ref, "coordinate_system_id", None),
        )

    @classmethod
    def from_canonical(cls, ref) -> "GeometryArtifactIdentity":
        return cls.from_fields(
            artifact_id=ref.artifact_id,
            artifact_hash=ref.artifact_hash,
            source_identity=ref.source_identity,
            format=ref.format,
            coordinate_system_id=getattr(ref, "coordinate_system_id", None),
        )
