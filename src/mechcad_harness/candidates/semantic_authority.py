"""Pure semantic projections for candidate source authority bindings.

The raw source binding remains the authority for exact revision and artifact
replay.  This module computes the separate semantic commitment without
looking up state, files, or artifacts; trusted callers must provide the
verifier-local dual-binding context.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, TypeAlias

from mechcad_harness.core.canonical import canonical_json_bytes


RawGeometryBindingKey: TypeAlias = tuple[str, str, str, str, str | None]
VerifiedSemanticGeometryBindings: TypeAlias = Mapping[
    RawGeometryBindingKey, object
]

_SHA256_PREFIX = "sha256:"
_STEP_CONTENT_IDENTITY = "step-content-identity@1"
_RAW_GEOMETRY_FIELDS = frozenset({"artifact_id", "artifact_hash"})
_RAW_GEOMETRY_HASH_FIELDS = frozenset(
    {"reference_hash", "geometry_reference_hash", "geometry_identity_hash"}
)
_GEOMETRY_FIELDS = frozenset(
    {
        "artifact_id",
        "artifact_hash",
        "source_identity",
        "format",
        "coordinate_system_id",
        "reference_hash",
        "geometry_identity_hash",
        "content_identity",
        "content_identity_algorithm",
        "semantic_reference_hash",
    }
)
_SEMANTIC_GEOMETRY_FIELDS = frozenset(
    {"content_identity", "content_identity_algorithm", "semantic_reference_hash"}
)


def semantic_authority_value_hash(
    path: str,
    resolved_value: object,
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> str:
    """Hash one resolved authority value under the §5 semantic projection.

    ``verified_semantic_geometry_bindings`` is intentionally verifier-local.
    A raw geometry value is accepted only when its complete raw binding tuple
    selects a trusted ``step-content-identity@1`` record in that map.
    """

    _require_path(path)
    _require_context(verified_semantic_geometry_bindings)
    payload = {
        "path": path,
        "value": _semantic_projection(
            _json_value(resolved_value), verified_semantic_geometry_bindings
        ),
    }
    return _hash_payload(payload)


def semantic_source_binding_hash(
    source_binding: object,
    resolved_authority_values: Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> str:
    """Hash a source binding using only its §5 semantic commitments.

    Revision/state coordinates and each legacy ``value_hash`` are retained by
    the caller for raw replay validation, but are deliberately absent here.
    The resolved values are supplied explicitly so this function remains pure.
    """

    _require_context(verified_semantic_geometry_bindings)
    if not isinstance(resolved_authority_values, Mapping):
        raise TypeError("resolved_authority_values must be a mapping")

    binding = _json_value(source_binding)
    if not isinstance(binding, Mapping):
        raise TypeError("source_binding must be a mapping or model")
    project_id = binding.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("source_binding project_id must not be empty")

    references = binding.get("consumed_authority")
    if not isinstance(references, Sequence) or isinstance(references, (str, bytes)):
        raise TypeError("source_binding consumed_authority must be a sequence")
    if not references:
        raise ValueError("source_binding consumed_authority must not be empty")

    semantic_references: list[dict[str, str]] = []
    paths: set[str] = set()
    for reference in references:
        reference_payload = _json_value(reference)
        if not isinstance(reference_payload, Mapping):
            raise TypeError("consumed authority references must be mappings or models")
        path = reference_payload.get("path")
        authority = reference_payload.get("authority")
        _require_path(path)
        if not isinstance(authority, str) or not authority.strip():
            raise ValueError("consumed authority authority must not be empty")
        if path in paths:
            raise ValueError("consumed authority paths must be unique")
        paths.add(path)
        if path not in resolved_authority_values:
            raise ValueError(f"resolved authority value is missing: {path}")
        semantic_references.append(
            {
                "path": path,
                "authority": authority,
                "semantic_authority_value_hash": semantic_authority_value_hash(
                    path,
                    resolved_authority_values[path],
                    verified_semantic_geometry_bindings,
                ),
            }
        )

    return _hash_payload(
        {
            "project_id": project_id,
            "consumed_authority": semantic_references,
        }
    )


def _semantic_projection(
    value: object,
    context: VerifiedSemanticGeometryBindings,
) -> object:
    value = _json_value(value)
    if isinstance(value, Mapping):
        keys = set(value)
        if not all(isinstance(key, str) for key in keys):
            raise TypeError("semantic authority mappings require string keys")
        if keys & _RAW_GEOMETRY_FIELDS:
            return _semantic_geometry_projection(value, context)
        if keys & _RAW_GEOMETRY_HASH_FIELDS:
            raise ValueError("legacy geometry hash requires an explicit semantic projection")
        if keys & _SEMANTIC_GEOMETRY_FIELDS:
            return _semantic_geometry_projection_from_semantic(value)
        if _contains_geometry_fields(value.values()):
            raise ValueError(
                "nested raw-bearing values require an explicit semantic projection"
            )
        return {
            key: _semantic_projection(item, context) for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_semantic_projection(item, context) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported semantic authority value type: {type(value).__name__}")


def _contains_geometry_fields(values: Any) -> bool:
    for value in values:
        value = _json_value(value)
        if isinstance(value, Mapping):
            keys = set(value)
            if keys & (_RAW_GEOMETRY_FIELDS | _RAW_GEOMETRY_HASH_FIELDS | _SEMANTIC_GEOMETRY_FIELDS):
                return True
            if _contains_geometry_fields(value.values()):
                return True
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            if _contains_geometry_fields(value):
                return True
    return False


def _semantic_geometry_projection(
    value: Mapping[str, object],
    context: VerifiedSemanticGeometryBindings,
) -> dict[str, object]:
    required = {"artifact_id", "artifact_hash", "source_identity", "format"}
    if not required.issubset(value):
        raise ValueError("unknown raw-bearing geometry shape")
    if not set(value).issubset(_GEOMETRY_FIELDS):
        raise ValueError("unknown raw-bearing geometry shape")

    artifact_id = value["artifact_id"]
    artifact_hash = value["artifact_hash"]
    source_identity = value["source_identity"]
    geometry_format = value["format"]
    coordinate_system_id = value.get("coordinate_system_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        raise ValueError("geometry artifact_id must not be empty")
    _require_sha256(artifact_hash, "geometry artifact_hash")
    if not isinstance(source_identity, str) or not source_identity.strip():
        raise ValueError("geometry source_identity must not be empty")
    if geometry_format != "step":
        raise ValueError("unsupported raw geometry format")
    if coordinate_system_id is not None and (
        not isinstance(coordinate_system_id, str) or not coordinate_system_id.strip()
    ):
        raise ValueError("geometry coordinate_system_id must not be empty")

    key: RawGeometryBindingKey = (
        artifact_id,
        artifact_hash,
        source_identity,
        geometry_format,
        coordinate_system_id,
    )
    if key not in context:
        raise ValueError("verified semantic geometry binding is missing or mismatched")
    content_identity, algorithm = _semantic_identity(context[key])
    persisted_content_identity = value.get("content_identity")
    persisted_algorithm = value.get("content_identity_algorithm")
    if persisted_content_identity is not None and persisted_content_identity != content_identity:
        raise ValueError("persisted semantic geometry content identity mismatch")
    if persisted_algorithm is not None and persisted_algorithm != algorithm:
        raise ValueError("persisted semantic geometry algorithm mismatch")
    persisted_reference_hash = value.get("semantic_reference_hash")
    if persisted_reference_hash is not None:
        expected_reference_hash = _hash_payload(
            {
                "source_identity": source_identity,
                "format": geometry_format,
                **(
                    {"coordinate_system_id": coordinate_system_id}
                    if coordinate_system_id is not None
                    else {}
                ),
                "content_identity": content_identity,
                "content_identity_algorithm": algorithm,
            }
        )
        if persisted_reference_hash != expected_reference_hash:
            raise ValueError("persisted semantic geometry reference hash mismatch")

    projected = {
        "source_identity": source_identity,
        "format": geometry_format,
        "content_identity": content_identity,
        "content_identity_algorithm": algorithm,
    }
    if coordinate_system_id is not None:
        projected["coordinate_system_id"] = coordinate_system_id
    return projected


def _semantic_geometry_projection_from_semantic(
    value: Mapping[str, object],
) -> dict[str, object]:
    allowed = {
        "source_identity",
        "format",
        "coordinate_system_id",
        "content_identity",
        "content_identity_algorithm",
        "semantic_reference_hash",
    }
    required = {
        "source_identity",
        "format",
        "content_identity",
        "content_identity_algorithm",
    }
    if set(value) - allowed or not required.issubset(value):
        raise ValueError("unknown semantic geometry shape")
    source_identity = value["source_identity"]
    geometry_format = value["format"]
    coordinate_system_id = value.get("coordinate_system_id")
    content_identity = value["content_identity"]
    algorithm = value["content_identity_algorithm"]
    if not isinstance(source_identity, str) or not source_identity.strip():
        raise ValueError("semantic geometry source_identity must not be empty")
    if geometry_format != "step":
        raise ValueError("unsupported semantic geometry format")
    if coordinate_system_id is not None and (
        not isinstance(coordinate_system_id, str) or not coordinate_system_id.strip()
    ):
        raise ValueError("semantic geometry coordinate_system_id must not be empty")
    if algorithm != _STEP_CONTENT_IDENTITY:
        raise ValueError("unsupported semantic geometry identity algorithm")
    _require_sha256(content_identity, "semantic geometry content identity")
    projected = {
        "source_identity": source_identity,
        "format": geometry_format,
        "content_identity": content_identity,
        "content_identity_algorithm": algorithm,
    }
    if coordinate_system_id is not None:
        projected["coordinate_system_id"] = coordinate_system_id
    persisted_reference_hash = value.get("semantic_reference_hash")
    if persisted_reference_hash is not None and persisted_reference_hash != _hash_payload(projected):
        raise ValueError("persisted semantic geometry reference hash mismatch")
    return projected


def _semantic_identity(value: object) -> tuple[str, str]:
    payload = _json_value(value)
    if not isinstance(payload, Mapping):
        raise ValueError("verified semantic geometry binding is not a typed identity")
    algorithm = payload.get("algorithm", payload.get("content_identity_algorithm"))
    content_identity = payload.get("content_hash", payload.get("content_identity"))
    if algorithm != _STEP_CONTENT_IDENTITY:
        raise ValueError("unsupported verified semantic geometry identity algorithm")
    _require_sha256(content_identity, "verified semantic geometry content identity")
    return content_identity, algorithm


def _json_value(value: object) -> object:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return value


def _require_context(value: object) -> None:
    if not isinstance(value, Mapping):
        raise TypeError("verified_semantic_geometry_bindings must be a mapping")


def _require_path(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("/") or value == "/":
        raise ValueError("semantic authority path must be a canonical non-root path")
    if "//" in value or "~" in value:
        raise ValueError("semantic authority path must be a canonical non-root path")
    return value


def _require_sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(_SHA256_PREFIX)
        or len(value) != len(_SHA256_PREFIX) + 64
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{label} must be a sha256 hash")
    return value


def _hash_payload(payload: Mapping[str, object]) -> str:
    return _SHA256_PREFIX + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


__all__ = [
    "RawGeometryBindingKey",
    "VerifiedSemanticGeometryBindings",
    "semantic_authority_value_hash",
    "semantic_source_binding_hash",
]
