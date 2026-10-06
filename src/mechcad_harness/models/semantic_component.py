"""Context-bound semantic projections for component specifications.

The persisted component records retain their raw geometry and M13 records for
replay.  The ``@4`` identity is computed separately from verifier-local
geometry bindings so raw artifact identifiers and hashes never enter the new
semantic chain.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.semantic_m13 import (
    VerifiedSemanticGeometryBindings,
    semantic_geometry_artifact_identity_projection,
    semantic_m13_collections_projection,
)


_SHA256_PREFIX = "sha256:"
_STEP_CONTENT_IDENTITY = "step-content-identity@1"
_COMPONENT_FIELDS = {
    "schema_version",
    "component_type",
    "manufacturer",
    "part_number",
    "source_identity",
    "properties",
    "geometry_source",
    "generated_part",
    "interfaces",
    "compatibility_declarations",
    "supplied_reference_frames",
    "supplied_interface_definitions",
    "geometry_derivation_transforms",
    "specification_hash",
}


def semantic_component_specification_projection(
    specification: object,
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    _allow_pending: bool = False,
) -> dict[str, object]:
    """Project one candidate or canonical component specification at ``@4``."""

    data = _component_data(specification)
    schema_version = data["schema_version"]
    if schema_version not in {
        "component-specification@4",
        "canonical-component-specification@4",
    }:
        raise ValueError("semantic component specification projection requires @4")

    geometry_source = data["geometry_source"]
    generated_part = data["generated_part"]
    frames = tuple(data["supplied_reference_frames"])
    definitions = tuple(data["supplied_interface_definitions"])
    transforms = tuple(data["geometry_derivation_transforms"])
    has_m13 = bool(frames or definitions or transforms)
    if generated_part is not None:
        if geometry_source is not None or has_m13:
            raise ValueError("generated component specification is exclusive")
    elif geometry_source is None:
        raise ValueError("supplied component specification requires geometry_source")
    elif has_m13 and getattr(geometry_source, "coordinate_system_id", None) is None:
        raise ValueError("M13 component specification requires a coordinate system")

    m13 = semantic_m13_collections_projection(
        frames,
        definitions,
        transforms,
        verified_semantic_geometry_bindings,
    )
    payload: dict[str, object] = {
        "schema_version": schema_version,
        "component_type": data["component_type"],
        "manufacturer": data["manufacturer"],
        "part_number": data["part_number"],
        "source_identity": data["source_identity"],
        "properties": [
            property_value.model_dump(mode="json")
            for property_value in data["properties"]
        ],
        "geometry_source": (
            None
            if geometry_source is None
            else _semantic_geometry_source_projection(
                geometry_source,
                verified_semantic_geometry_bindings,
                allow_pending=_allow_pending,
            )
        ),
        "interfaces": list(data["interfaces"]),
        "compatibility_declarations": list(data["compatibility_declarations"]),
        "supplied_reference_frames": m13["supplied_reference_frames"],
        "supplied_interface_definitions": m13["supplied_interface_definitions"],
        "geometry_derivation_transforms": m13["geometry_derivation_transforms"],
    }
    if generated_part is not None:
        payload["generated_part"] = generated_part.model_dump(mode="json")
    return payload


def semantic_component_specification_hash(
    specification: object,
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> str:
    return _hash_payload(
        semantic_component_specification_projection(
            specification, verified_semantic_geometry_bindings
        )
    )


def bind_component_specification_semantic_identity(
    specification: object,
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> Any:
    """Return an ``@4`` specification with its context-bound hash filled."""

    projection = semantic_component_specification_projection(
        specification,
        verified_semantic_geometry_bindings,
        _allow_pending=True,
    )
    expected = _hash_payload(projection)
    current = getattr(specification, "specification_hash", None)
    if current not in (None, "pending", expected):
        raise ValueError("component specification semantic hash mismatch")
    geometry_source = getattr(specification, "geometry_source", None)
    if geometry_source is None:
        return specification.model_copy(update={"specification_hash": expected})
    geometry_projection = _semantic_geometry_source_projection(
        geometry_source,
        verified_semantic_geometry_bindings,
        allow_pending=True,
    )
    bound_reference = geometry_source.model_copy(
        update={
            "content_identity": geometry_projection["content_identity"],
            "content_identity_algorithm": geometry_projection[
                "content_identity_algorithm"
            ],
            "semantic_reference_hash": _hash_payload(geometry_projection),
        }
    )
    bound = specification.model_copy(
        update={"geometry_source": bound_reference, "specification_hash": "pending"}
    )
    bound_hash = semantic_component_specification_hash(
        bound, verified_semantic_geometry_bindings
    )
    return bound.model_copy(update={"specification_hash": bound_hash})


def _component_data(specification: object) -> dict[str, object]:
    model_fields = getattr(type(specification), "model_fields", None)
    if not isinstance(model_fields, dict) or not hasattr(specification, "model_dump"):
        raise TypeError("component specification must be a production model")
    fields = set(model_fields)
    if fields != _COMPONENT_FIELDS:
        raise ValueError("component specification has unknown or missing fields")
    data = {
        field: getattr(specification, field)
        for field in _COMPONENT_FIELDS
        if hasattr(specification, field)
    }
    if set(data) != _COMPONENT_FIELDS:
        raise ValueError("component specification has unknown or missing fields")
    return data


def _semantic_geometry_source_projection(
    reference: object,
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    allow_pending: bool = False,
) -> dict[str, object]:
    identity = GeometryArtifactIdentity.from_fields(
        reference.artifact_id,
        reference.artifact_hash,
        reference.source_identity,
        reference.format,
        reference.coordinate_system_id,
    )
    projection = semantic_geometry_artifact_identity_projection(
        identity, verified_semantic_geometry_bindings
    )
    persisted_content_identity = reference.content_identity
    if not allow_pending and persisted_content_identity != projection["content_identity"]:
        raise ValueError("persisted semantic geometry content identity mismatch")
    if reference.content_identity_algorithm != _STEP_CONTENT_IDENTITY and not allow_pending:
        raise ValueError("unsupported semantic geometry identity algorithm")
    if not allow_pending and reference.semantic_reference_hash in (None, "pending"):
        raise ValueError("semantic geometry reference trio is incomplete")
    if reference.semantic_reference_hash not in (None, "pending"):
        expected = _hash_payload(projection)
        if reference.semantic_reference_hash != expected:
            raise ValueError("persisted semantic geometry reference hash mismatch")
    return projection


def _hash_payload(payload: Mapping[str, object]) -> str:
    return _SHA256_PREFIX + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


__all__ = [
    "bind_component_specification_semantic_identity",
    "semantic_component_specification_hash",
    "semantic_component_specification_projection",
]
