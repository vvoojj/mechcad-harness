from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, field_validator

from mechcad_harness.artifacts.storage import ArtifactStore
from mechcad_harness.models.common import Model


class ImportedComponentError(Exception):
    pass


class ImportedArtifactNotFoundError(ImportedComponentError):
    pass


class ImportedArtifactIntegrityError(ImportedComponentError):
    pass


class UnsupportedImportedFormatError(ImportedComponentError):
    pass


class ImportedCadComponent(Model):
    component_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    artifact_hash: str = Field(min_length=1)
    format: Literal["step"] = "step"
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)

    @field_validator("artifact_hash")
    @classmethod
    def validate_artifact_hash(cls, value: str) -> str:
        if not value.startswith("sha256:"):
            raise ValueError("artifact_hash must be a sha256 hash")
        hex_part = value[7:]
        if len(hex_part) != 64 or not all(c in "0123456789abcdef" for c in hex_part):
            raise ValueError("artifact_hash must be a valid sha256 hex digest")
        return value

    @field_validator("source_state_hash")
    @classmethod
    def validate_source_state_hash(cls, value: str) -> str:
        if not value.startswith("sha256:"):
            raise ValueError("source_state_hash must be a sha256 hash")
        hex_part = value[7:]
        if len(hex_part) != 64 or not all(c in "0123456789abcdef" for c in hex_part):
            raise ValueError("source_state_hash must be a valid sha256 hex digest")
        return value


def imported_component_hash(component: ImportedCadComponent) -> str:
    payload = {
        "component_id": component.component_id,
        "artifact_id": component.artifact_id,
        "artifact_hash": component.artifact_hash,
        "format": component.format,
        "source_revision": component.source_revision,
        "source_state_hash": component.source_state_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def resolve_imported_component(
    artifact_id: str,
    artifact_hash: str,
    store: ArtifactStore,
    *,
    component_id: str,
    expected_format: str = "step",
) -> ImportedCadComponent:
    artifact = store.existing(artifact_id)
    if artifact is None:
        raise ImportedArtifactNotFoundError(
            f"artifact not found: {artifact_id}"
        )

    if artifact.artifact_type.value != expected_format:
        raise UnsupportedImportedFormatError(
            f"unsupported format: {artifact.artifact_type.value}, expected: {expected_format}"
        )

    if artifact.sha256 != artifact_hash:
        raise ImportedArtifactIntegrityError(
            f"artifact hash mismatch: expected {artifact_hash}, got {artifact.sha256}"
        )

    return ImportedCadComponent(
        component_id=component_id,
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        format=expected_format,
        source_revision=artifact.bound_revision,
        source_state_hash=artifact.bound_state_hash,
    )
