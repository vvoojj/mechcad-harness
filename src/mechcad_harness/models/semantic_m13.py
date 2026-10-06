"""Pure, type-directed semantic projections for the persisted M13 records.

The projections in this module are deliberately separate from the persisted
models.  They retain engineering values, replace raw geometry references with
verified semantic identities, and omit replay-only self hashes and provenance
coordinates.  No projection uses a recursive model dump as its semantic
payload.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from typing import TypeAlias

from .geometry_identity import GeometryArtifactIdentity, geometry_reference_hash
from .supplied_component_interface import (
    GeometryDerivationAuthorityFact,
    GeometryDerivationTransform,
    GeometryDerivationUnitConversion,
    InterfaceDerivationProvenance,
    InterfaceFactDerivationBinding,
    MountingFaceInterface,
    MountingHole,
    RotationalShaftInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedComponentReferenceFrame,
    SuppliedInterfaceEvidence,
    SuppliedInterfaceEvidenceOrigin,
    SuppliedInterfaceFact,
    SuppliedPilotBossReference,
    SuppliedShaftDFlatProfile,
)


RawGeometryBindingKey: TypeAlias = tuple[str, str, str, str, str | None]
VerifiedSemanticGeometryBindings: TypeAlias = Mapping[
    RawGeometryBindingKey, object
]

_SHA256_PREFIX = "sha256:"
_STEP_CONTENT_IDENTITY = "step-content-identity@1"
_MATERIALIZATION_ALGORITHM = "supplied-interface-materialization@1"
_MODEL_TYPES = {
    "GeometryArtifactIdentity": GeometryArtifactIdentity,
    "SuppliedComponentReferenceFrame": SuppliedComponentReferenceFrame,
    "RotationalShaftInterface": RotationalShaftInterface,
    "MountingFaceInterface": MountingFaceInterface,
    "SuppliedComponentInterfaceDefinition": SuppliedComponentInterfaceDefinition,
    "SuppliedShaftDFlatProfile": SuppliedShaftDFlatProfile,
    "MountingHole": MountingHole,
    "SuppliedPilotBossReference": SuppliedPilotBossReference,
    "SuppliedInterfaceFact": SuppliedInterfaceFact,
    "SuppliedInterfaceEvidence": SuppliedInterfaceEvidence,
    "GeometryDerivationAuthorityFact": GeometryDerivationAuthorityFact,
    "GeometryDerivationUnitConversion": GeometryDerivationUnitConversion,
    "GeometryDerivationTransform": GeometryDerivationTransform,
    "InterfaceFactDerivationBinding": InterfaceFactDerivationBinding,
    "InterfaceDerivationProvenance": InterfaceDerivationProvenance,
}


def semantic_geometry_artifact_identity_projection(
    identity: GeometryArtifactIdentity | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> dict[str, object]:
    data = _as_mapping(
        identity,
        {
            "artifact_id",
            "artifact_hash",
            "source_identity",
            "format",
            "coordinate_system_id",
            "geometry_identity_hash",
        },
        "GeometryArtifactIdentity",
    )
    return _semantic_geometry_data(data, verified_semantic_geometry_bindings)


def semantic_reference_frame_projection(
    frame: SuppliedComponentReferenceFrame | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        frame,
        {"frame_id", "geometry_reference_hash", "origin", "orientation", "frame_hash"},
        "SuppliedComponentReferenceFrame",
    )
    _require_geometry_reference_in_scope(
        data["geometry_reference_hash"], enclosing_geometry_reference_hashes
    )
    return {
        "frame_id": _nonblank(data["frame_id"], "frame_id"),
        "geometry_reference_hash": _semantic_reference_for_hash(
            data["geometry_reference_hash"], verified_semantic_geometry_bindings
        ),
        "origin": semantic_interface_fact_projection(
            data["origin"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
        ),
        "orientation": semantic_interface_fact_projection(
            data["orientation"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
        ),
    }


def semantic_rotational_shaft_interface_projection(
    interface: RotationalShaftInterface | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        interface,
        {
            "interface_id",
            "geometry_reference_hash",
            "geometry",
            "reference_frame_id",
            "axis_point",
            "axis_direction",
            "nominal_shaft_diameter",
            "usable_axial_engagement_length",
            "shoulder_reference_plane",
            "shaft_profile",
            "d_flat_profile",
            "thread_designation",
            "interface_hash",
        },
        "RotationalShaftInterface",
    )
    _require_geometry_reference_in_scope(
        data["geometry_reference_hash"], enclosing_geometry_reference_hashes
    )
    shoulder = data["shoulder_reference_plane"]
    if shoulder is not None:
        shoulder_values = _sequence(shoulder, "shoulder_reference_plane")
        if len(shoulder_values) != 2:
            raise ValueError("shoulder_reference_plane must contain two facts")
        shoulder_projection: object = [
            semantic_interface_fact_projection(
                shoulder_values[0],
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
            ),
            semantic_interface_fact_projection(
                shoulder_values[1],
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
            ),
        ]
    else:
        shoulder_projection = None
    geometry_reference = _semantic_reference_for_geometry(
        data["geometry_reference_hash"], data["geometry"], verified_semantic_geometry_bindings
    )
    return {
        "interface_id": _nonblank(data["interface_id"], "interface_id"),
        "geometry_reference_hash": geometry_reference,
        "geometry": semantic_geometry_artifact_identity_projection(
            data["geometry"], verified_semantic_geometry_bindings
        ),
        "reference_frame_id": _optional_nonblank(
            data["reference_frame_id"], "reference_frame_id"
        ),
        "axis_point": semantic_interface_fact_projection(
            data["axis_point"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
        ),
        "axis_direction": semantic_interface_fact_projection(
            data["axis_direction"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
        ),
        "nominal_shaft_diameter": semantic_interface_fact_projection(
            data["nominal_shaft_diameter"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
        ),
        "usable_axial_engagement_length": semantic_interface_fact_projection(
            data["usable_axial_engagement_length"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
        ),
        "shoulder_reference_plane": shoulder_projection,
        "shaft_profile": _enum_value(data["shaft_profile"]),
        "d_flat_profile": (
            None
            if data["d_flat_profile"] is None
            else semantic_shaft_d_flat_profile_projection(
                data["d_flat_profile"],
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
            )
        ),
        "thread_designation": (
            None
            if data["thread_designation"] is None
            else semantic_interface_fact_projection(
                data["thread_designation"],
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
            )
        ),
    }


def semantic_mounting_face_interface_projection(
    interface: MountingFaceInterface | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        interface,
        {
            "interface_id",
            "geometry_reference_hash",
            "geometry",
            "face_reference_id",
            "reference_frame_id",
            "plane_point",
            "outward_normal",
            "holes",
            "pilot_boss",
            "interface_hash",
        },
        "MountingFaceInterface",
    )
    _require_geometry_reference_in_scope(
        data["geometry_reference_hash"], enclosing_geometry_reference_hashes
    )
    holes = _sorted_unique(
        data["holes"], "hole_id", "mounting face holes"
    )
    geometry_reference = _semantic_reference_for_geometry(
        data["geometry_reference_hash"], data["geometry"], verified_semantic_geometry_bindings
    )
    return {
        "interface_id": _nonblank(data["interface_id"], "interface_id"),
        "geometry_reference_hash": geometry_reference,
        "geometry": semantic_geometry_artifact_identity_projection(
            data["geometry"], verified_semantic_geometry_bindings
        ),
        "face_reference_id": _nonblank(data["face_reference_id"], "face_reference_id"),
        "reference_frame_id": _nonblank(data["reference_frame_id"], "reference_frame_id"),
        "plane_point": semantic_interface_fact_projection(
            data["plane_point"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
        ),
        "outward_normal": semantic_interface_fact_projection(
            data["outward_normal"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
        ),
        "holes": [
            semantic_mounting_hole_projection(
                hole,
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
            )
            for hole in holes
        ],
        "pilot_boss": (
            None
            if data["pilot_boss"] is None
            else semantic_pilot_boss_projection(
                data["pilot_boss"],
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
            )
        ),
    }


def semantic_interface_definition_projection(
    definition: SuppliedComponentInterfaceDefinition | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        definition,
        {
            "kind",
            "interface_id",
            "geometry_reference_hash",
            "geometry",
            "shaft",
            "mounting_face",
            "derivation",
            "interface_hash",
        },
        "SuppliedComponentInterfaceDefinition",
    )
    _require_geometry_reference_in_scope(
        data["geometry_reference_hash"], enclosing_geometry_reference_hashes
    )
    kind = _enum_value(data["kind"])
    if kind not in {"direct", "materialized"}:
        raise ValueError("interface definition kind is invalid")
    shaft = data["shaft"]
    mounting_face = data["mounting_face"]
    if (shaft is None) == (mounting_face is None):
        raise ValueError("exactly one interface variant is required")
    derivation = data["derivation"]
    if kind == "direct" and derivation is not None:
        raise ValueError("direct interface must not have derivation provenance")
    if kind == "materialized" and derivation is None:
        raise ValueError("materialized interface requires derivation provenance")
    geometry_reference = _semantic_reference_for_geometry(
        data["geometry_reference_hash"], data["geometry"], verified_semantic_geometry_bindings
    )
    return {
        "kind": kind,
        "interface_id": _nonblank(data["interface_id"], "interface_id"),
        "geometry_reference_hash": geometry_reference,
        "geometry": semantic_geometry_artifact_identity_projection(
            data["geometry"], verified_semantic_geometry_bindings
        ),
        "shaft": (
            None
            if shaft is None
            else semantic_rotational_shaft_interface_projection(
                shaft,
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
            )
        ),
        "mounting_face": (
            None
            if mounting_face is None
            else semantic_mounting_face_interface_projection(
                mounting_face,
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=(data["geometry_reference_hash"],),
            )
        ),
        "derivation": (
            None
            if derivation is None
            else semantic_interface_derivation_provenance_projection(
                derivation, verified_semantic_geometry_bindings
            )
        ),
    }


def semantic_supplied_reference_frames_projection(
    frames: Sequence[SuppliedComponentReferenceFrame | Mapping[str, object]],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> list[dict[str, object]]:
    return [
        semantic_reference_frame_projection(item, verified_semantic_geometry_bindings)
        for item in _sorted_unique(frames, "frame_id", "reference frames")
    ]


def semantic_supplied_interface_definitions_projection(
    definitions: Sequence[
        SuppliedComponentInterfaceDefinition | Mapping[str, object]
    ],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> list[dict[str, object]]:
    return [
        semantic_interface_definition_projection(
            item, verified_semantic_geometry_bindings
        )
        for item in _sorted_unique(definitions, "interface_id", "interface definitions")
    ]


def semantic_geometry_derivation_transforms_projection(
    transforms: Sequence[GeometryDerivationTransform | Mapping[str, object]],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> list[dict[str, object]]:
    return [
        semantic_geometry_derivation_transform_projection(
            item, verified_semantic_geometry_bindings
        )
        for item in _sorted_unique(transforms, "transform_id", "geometry derivation transforms")
    ]


def semantic_m13_collections_projection(
    supplied_reference_frames: Sequence[
        SuppliedComponentReferenceFrame | Mapping[str, object]
    ],
    supplied_interface_definitions: Sequence[
        SuppliedComponentInterfaceDefinition | Mapping[str, object]
    ],
    geometry_derivation_transforms: Sequence[
        GeometryDerivationTransform | Mapping[str, object]
    ],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> dict[str, list[dict[str, object]]]:
    return {
        "supplied_reference_frames": semantic_supplied_reference_frames_projection(
            supplied_reference_frames, verified_semantic_geometry_bindings
        ),
        "supplied_interface_definitions": semantic_supplied_interface_definitions_projection(
            supplied_interface_definitions, verified_semantic_geometry_bindings
        ),
        "geometry_derivation_transforms": semantic_geometry_derivation_transforms_projection(
            geometry_derivation_transforms, verified_semantic_geometry_bindings
        ),
    }


def semantic_shaft_d_flat_profile_projection(
    profile: SuppliedShaftDFlatProfile | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        profile,
        {
            "flat_normal_direction",
            "flat_across_dimension",
            "start_from_shoulder",
            "effective_length",
        },
        "SuppliedShaftDFlatProfile",
    )
    return {
        field: semantic_interface_fact_projection(
            data[field],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=enclosing_geometry_reference_hashes,
        )
        for field in (
            "flat_normal_direction",
            "flat_across_dimension",
            "start_from_shoulder",
            "effective_length",
        )
    }


def semantic_mounting_hole_projection(
    hole: MountingHole | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        hole,
        {"hole_id", "center", "axis", "nominal_diameter", "thread_designation"},
        "MountingHole",
    )
    return {
        "hole_id": _nonblank(data["hole_id"], "hole_id"),
        "center": semantic_interface_fact_projection(
            data["center"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=enclosing_geometry_reference_hashes,
        ),
        "axis": semantic_interface_fact_projection(
            data["axis"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=enclosing_geometry_reference_hashes,
        ),
        "nominal_diameter": semantic_interface_fact_projection(
            data["nominal_diameter"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=enclosing_geometry_reference_hashes,
        ),
        "thread_designation": (
            None
            if data["thread_designation"] is None
            else semantic_interface_fact_projection(
                data["thread_designation"],
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=enclosing_geometry_reference_hashes,
            )
        ),
    }


def semantic_pilot_boss_projection(
    pilot: SuppliedPilotBossReference | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        pilot,
        {"point", "axis", "diameter"},
        "SuppliedPilotBossReference",
    )
    return {
        field: semantic_interface_fact_projection(
            data[field],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=enclosing_geometry_reference_hashes,
        )
        for field in ("point", "axis", "diameter")
    }


def semantic_interface_fact_projection(
    fact: SuppliedInterfaceFact | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        fact,
        {
            "fact_id",
            "expected_shape",
            "expected_unit",
            "transform_role",
            "evidence",
            "accepted_evidence_id",
            "fact_hash",
        },
        "SuppliedInterfaceFact",
    )
    evidence = _sorted_unique(data["evidence"], "evidence_id", "fact evidence")
    return {
        "fact_id": _nonblank(data["fact_id"], "fact_id"),
        "expected_shape": _enum_value(data["expected_shape"]),
        "expected_unit": _optional_nonblank(data["expected_unit"], "expected_unit"),
        "transform_role": _enum_value(data["transform_role"]),
        "evidence": [
            semantic_interface_evidence_projection(
                item,
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=enclosing_geometry_reference_hashes,
            )
            for item in evidence
        ],
        "accepted_evidence_id": _optional_nonblank(
            data["accepted_evidence_id"], "accepted_evidence_id"
        ),
    }


def semantic_interface_evidence_projection(
    evidence: SuppliedInterfaceEvidence | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        evidence,
        {
            "evidence_id",
            "shape",
            "value",
            "canonical_unit",
            "availability",
            "authority",
            "source_identity",
            "applicability_context",
            "conversion_provenance",
            "evidence_origin",
            "source_document_identity",
            "geometry_reference_hash",
            "basis_evidence_ids",
            "evidence_hash",
        },
        "SuppliedInterfaceEvidence",
    )
    _require_geometry_reference_in_scope(
        data["geometry_reference_hash"], enclosing_geometry_reference_hashes
    )
    semantic_geometry_reference = (
        None
        if data["geometry_reference_hash"] is None
        else _semantic_reference_for_hash(
            data["geometry_reference_hash"], verified_semantic_geometry_bindings
        )
    )
    source_identity = _semantic_evidence_source_identity(
        data["source_identity"],
        data["source_document_identity"],
        data["geometry_reference_hash"],
        verified_semantic_geometry_bindings,
    )
    origin = _enum_value(data["evidence_origin"])
    if (
        origin == SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION.value
        and not data["basis_evidence_ids"]
    ):
        raise ValueError("human-confirmed interpretation evidence requires basis evidence")
    if (
        origin == SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED.value
        and data["geometry_reference_hash"] is None
    ):
        raise ValueError("geometry-inferred evidence requires a geometry reference hash")
    output = {
        "evidence_id": _nonblank(data["evidence_id"], "evidence_id"),
        "shape": _enum_value(data["shape"]),
        "value": _json_engineering_value(data["value"]),
        "canonical_unit": _optional_nonblank(data["canonical_unit"], "canonical_unit"),
        "availability": _enum_value(data["availability"]),
        "authority": _enum_value(data["authority"]),
        "source_identity": source_identity,
        "applicability_context": _optional_nonblank(
            data["applicability_context"], "applicability_context"
        ),
        "evidence_origin": origin,
        "geometry_reference_hash": semantic_geometry_reference,
        "basis_evidence_ids": _ordered_unique_ids(data["basis_evidence_ids"], "basis_evidence_ids"),
    }
    if origin != SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION.value:
        output["conversion_provenance"] = _optional_nonblank(
            data["conversion_provenance"], "conversion_provenance"
        )
    return output


def semantic_geometry_derivation_authority_fact_projection(
    fact: GeometryDerivationAuthorityFact | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
    *,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None = None,
) -> dict[str, object]:
    data = _as_mapping(
        fact,
        {
            "authority_role",
            "expected_shape",
            "expected_unit",
            "evidence",
            "accepted_evidence_id",
            "authority_fact_hash",
        },
        "GeometryDerivationAuthorityFact",
    )
    evidence = _sorted_unique(data["evidence"], "evidence_id", "authority fact evidence")
    return {
        "authority_role": _enum_value(data["authority_role"]),
        "expected_shape": _enum_value(data["expected_shape"]),
        "expected_unit": _nonblank(data["expected_unit"], "expected_unit"),
        "evidence": [
            semantic_interface_evidence_projection(
                item,
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=enclosing_geometry_reference_hashes,
            )
            for item in evidence
        ],
        "accepted_evidence_id": _optional_nonblank(
            data["accepted_evidence_id"], "accepted_evidence_id"
        ),
    }


def semantic_geometry_derivation_unit_conversion_projection(
    conversion: GeometryDerivationUnitConversion | Mapping[str, object],
) -> dict[str, object]:
    data = _as_mapping(
        conversion,
        {"source_unit", "derived_unit", "declaration"},
        "GeometryDerivationUnitConversion",
    )
    return {
        "source_unit": _nonblank(data["source_unit"], "source_unit"),
        "derived_unit": _nonblank(data["derived_unit"], "derived_unit"),
        "declaration": _nonblank(data["declaration"], "declaration"),
    }


def semantic_geometry_derivation_transform_projection(
    transform: GeometryDerivationTransform | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> dict[str, object]:
    data = _as_mapping(
        transform,
        {
            "transform_id",
            "source_geometry",
            "derived_geometry",
            "source_geometry_reference_hash",
            "derived_geometry_reference_hash",
            "translation_fact",
            "rotation_fact",
            "uniform_scale_fact",
            "unit_conversion",
            "status",
            "transform_hash",
        },
        "GeometryDerivationTransform",
    )
    return {
        "transform_id": _nonblank(data["transform_id"], "transform_id"),
        "source_geometry": semantic_geometry_artifact_identity_projection(
            data["source_geometry"], verified_semantic_geometry_bindings
        ),
        "derived_geometry": semantic_geometry_artifact_identity_projection(
            data["derived_geometry"], verified_semantic_geometry_bindings
        ),
        "source_geometry_reference_hash": _semantic_reference_for_geometry(
            data["source_geometry_reference_hash"],
            data["source_geometry"],
            verified_semantic_geometry_bindings,
        ),
        "derived_geometry_reference_hash": _semantic_reference_for_geometry(
            data["derived_geometry_reference_hash"],
            data["derived_geometry"],
            verified_semantic_geometry_bindings,
        ),
        "translation_fact": semantic_geometry_derivation_authority_fact_projection(
            data["translation_fact"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(
                data["source_geometry_reference_hash"],
                data["derived_geometry_reference_hash"],
            ),
        ),
        "rotation_fact": semantic_geometry_derivation_authority_fact_projection(
            data["rotation_fact"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(
                data["source_geometry_reference_hash"],
                data["derived_geometry_reference_hash"],
            ),
        ),
        "uniform_scale_fact": semantic_geometry_derivation_authority_fact_projection(
            data["uniform_scale_fact"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(
                data["source_geometry_reference_hash"],
                data["derived_geometry_reference_hash"],
            ),
        ),
        "unit_conversion": semantic_geometry_derivation_unit_conversion_projection(
            data["unit_conversion"]
        ),
        "status": _enum_value(data["status"]),
    }


def semantic_interface_fact_derivation_binding_projection(
    binding: InterfaceFactDerivationBinding | Mapping[str, object],
) -> dict[str, object]:
    data = _as_mapping(
        binding,
        {
            "fact_path",
            "source_fact_id",
            "derived_fact_id",
            "source_evidence_id",
            "source_evidence_hash",
            "transform_role",
        },
        "InterfaceFactDerivationBinding",
    )
    return {
        "fact_path": _nonblank(data["fact_path"], "fact_path"),
        "source_fact_id": _nonblank(data["source_fact_id"], "source_fact_id"),
        "derived_fact_id": _nonblank(data["derived_fact_id"], "derived_fact_id"),
        "source_evidence_id": _nonblank(
            data["source_evidence_id"], "source_evidence_id"
        ),
        "transform_role": _enum_value(data["transform_role"]),
    }


def semantic_interface_derivation_provenance_projection(
    provenance: InterfaceDerivationProvenance | Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> dict[str, object]:
    data = _as_mapping(
        provenance,
        {
            "source_interface_snapshot",
            "source_interface_hash",
            "source_reference_frame_snapshot",
            "source_reference_frame_hash",
            "derived_reference_frame_id",
            "derived_reference_frame_hash",
            "transform_id",
            "transform_hash",
            "source_geometry",
            "derived_geometry",
            "source_geometry_reference_hash",
            "derived_geometry_reference_hash",
            "fact_derivation_bindings",
            "materialization_algorithm",
            "provenance_hash",
        },
        "InterfaceDerivationProvenance",
    )
    bindings = _sorted_unique(
        data["fact_derivation_bindings"], "fact_path", "fact derivation bindings"
    )
    return {
        "source_interface_snapshot": semantic_interface_definition_projection(
            data["source_interface_snapshot"],
            verified_semantic_geometry_bindings,
            enclosing_geometry_reference_hashes=(
                data["source_geometry_reference_hash"],
            ),
        ),
        "source_reference_frame_snapshot": (
            None
            if data["source_reference_frame_snapshot"] is None
            else semantic_reference_frame_projection(
                data["source_reference_frame_snapshot"],
                verified_semantic_geometry_bindings,
                enclosing_geometry_reference_hashes=(
                    data["source_geometry_reference_hash"],
                ),
            )
        ),
        "derived_reference_frame_id": _optional_nonblank(
            data["derived_reference_frame_id"], "derived_reference_frame_id"
        ),
        "transform_id": _nonblank(data["transform_id"], "transform_id"),
        "source_geometry": semantic_geometry_artifact_identity_projection(
            data["source_geometry"], verified_semantic_geometry_bindings
        ),
        "derived_geometry": semantic_geometry_artifact_identity_projection(
            data["derived_geometry"], verified_semantic_geometry_bindings
        ),
        "source_geometry_reference_hash": _semantic_reference_for_geometry(
            data["source_geometry_reference_hash"],
            data["source_geometry"],
            verified_semantic_geometry_bindings,
        ),
        "derived_geometry_reference_hash": _semantic_reference_for_geometry(
            data["derived_geometry_reference_hash"],
            data["derived_geometry"],
            verified_semantic_geometry_bindings,
        ),
        "fact_derivation_bindings": [
            semantic_interface_fact_derivation_binding_projection(item)
            for item in bindings
        ],
        "materialization_algorithm": _require_literal(
            data["materialization_algorithm"],
            _MATERIALIZATION_ALGORITHM,
            "materialization_algorithm",
        ),
    }


def _semantic_geometry_data(
    data: Mapping[str, object],
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> dict[str, object]:
    artifact_id = _nonblank(data["artifact_id"], "artifact_id")
    artifact_hash = _sha256(data["artifact_hash"], "artifact_hash")
    source_identity = _nonblank(data["source_identity"], "source_identity")
    if data["format"] != "step":
        raise ValueError("unsupported geometry format")
    coordinate_system_id = _optional_nonblank(
        data["coordinate_system_id"], "coordinate_system_id"
    )
    key: RawGeometryBindingKey = (
        artifact_id,
        artifact_hash,
        source_identity,
        "step",
        coordinate_system_id,
    )
    if key not in verified_semantic_geometry_bindings:
        raise ValueError("verified semantic geometry binding is missing or mismatched")
    content_identity, algorithm = _semantic_identity(
        verified_semantic_geometry_bindings[key]
    )
    result = {
        "source_identity": source_identity,
        "format": "step",
        "content_identity": content_identity,
        "content_identity_algorithm": algorithm,
    }
    if coordinate_system_id is not None:
        result["coordinate_system_id"] = coordinate_system_id
    return result


def _semantic_evidence_source_identity(
    source_identity: object,
    source_document_identity: object,
    raw_geometry_reference_hash: object,
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> str:
    source = _nonblank(source_identity, "source_identity")
    if not source.startswith("artifact:"):
        if source.startswith("transform:") and not source.removeprefix("transform:").strip():
            raise ValueError("transform source identity must name a transform")
        return source
    artifact_hash = _sha256(source.removeprefix("artifact:"), "artifact source identity")
    artifact_id = _nonblank(source_document_identity, "source_document_identity")
    matches = [
        key
        for key in verified_semantic_geometry_bindings
        if isinstance(key, tuple)
        and len(key) == 5
        and key[0] == artifact_id
        and key[1] == artifact_hash
        and (
            raw_geometry_reference_hash is None
            or geometry_reference_hash(
                GeometryArtifactIdentity.from_fields(*key)
            ) == raw_geometry_reference_hash
        )
    ]
    if len(matches) != 1:
        raise ValueError("artifact evidence source has no unique verified geometry binding")
    return _semantic_identity(verified_semantic_geometry_bindings[matches[0]])[0]


def _semantic_reference_for_hash(
    raw_reference_hash: object,
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> dict[str, object]:
    raw_hash = _sha256(raw_reference_hash, "geometry reference hash")
    matches: list[dict[str, object]] = []
    for key in verified_semantic_geometry_bindings:
        if not isinstance(key, tuple) or len(key) != 5:
            raise TypeError("verified semantic geometry binding keys must be raw geometry tuples")
        artifact_id, artifact_hash, source_identity, geometry_format, coordinate_system_id = key
        identity = GeometryArtifactIdentity.from_fields(
            artifact_id,
            artifact_hash,
            source_identity,
            geometry_format,
            coordinate_system_id,
        )
        if geometry_reference_hash(identity) == raw_hash:
            matches.append(
                _semantic_geometry_data(
                    {
                        "artifact_id": artifact_id,
                        "artifact_hash": artifact_hash,
                        "source_identity": source_identity,
                        "format": geometry_format,
                        "coordinate_system_id": coordinate_system_id,
                        "geometry_identity_hash": identity.geometry_identity_hash,
                    },
                    verified_semantic_geometry_bindings,
                )
            )
    if len(matches) != 1:
        raise ValueError("geometry reference does not resolve to one verified geometry binding")
    semantic_reference = matches[0]
    if semantic_reference.get("coordinate_system_id") is None:
        semantic_reference = dict(semantic_reference)
        semantic_reference.pop("coordinate_system_id", None)
    return semantic_reference


def _semantic_reference_for_geometry(
    raw_reference_hash: object,
    geometry: object,
    verified_semantic_geometry_bindings: VerifiedSemanticGeometryBindings,
) -> dict[str, object]:
    geometry_data = _as_mapping(
        geometry,
        {
            "artifact_id",
            "artifact_hash",
            "source_identity",
            "format",
            "coordinate_system_id",
            "geometry_identity_hash",
        },
        "GeometryArtifactIdentity",
    )
    raw_geometry = GeometryArtifactIdentity.from_fields(
        geometry_data["artifact_id"],
        geometry_data["artifact_hash"],
        geometry_data["source_identity"],
        geometry_data["format"],
        geometry_data["coordinate_system_id"],
    )
    if geometry_reference_hash(raw_geometry) != _sha256(
        raw_reference_hash, "geometry reference hash"
    ):
        raise ValueError("geometry reference does not match enclosing geometry")
    expected = semantic_geometry_artifact_identity_projection(
        geometry, verified_semantic_geometry_bindings
    )
    actual = _semantic_reference_for_hash(
        raw_reference_hash, verified_semantic_geometry_bindings
    )
    if actual != expected:
        raise ValueError("geometry reference does not match enclosing geometry")
    return actual


def _require_geometry_reference_in_scope(
    raw_reference_hash: object,
    enclosing_geometry_reference_hashes: tuple[object, ...] | None,
) -> None:
    if raw_reference_hash is None or enclosing_geometry_reference_hashes is None:
        return
    raw_hash = _sha256(raw_reference_hash, "geometry reference hash")
    allowed = {
        _sha256(value, "enclosing geometry reference hash")
        for value in enclosing_geometry_reference_hashes
    }
    if raw_hash not in allowed:
        raise ValueError("nested geometry reference does not match its enclosing geometry")


def _semantic_identity(value: object) -> tuple[str, str]:
    if isinstance(value, Mapping):
        data = dict(value)
    elif isinstance(getattr(type(value), "model_fields", None), dict):
        fields = set(type(value).model_fields)
        data = {field: getattr(value, field) for field in fields}
    else:
        raise TypeError("semantic geometry identity must be a typed mapping or model")
    if set(data) != {"algorithm", "content_hash"}:
        raise ValueError("semantic geometry identity has unknown or missing fields")
    algorithm = data["algorithm"]
    content_identity = data["content_hash"]
    if algorithm != _STEP_CONTENT_IDENTITY:
        raise ValueError("unsupported semantic geometry identity algorithm")
    return _sha256(content_identity, "semantic geometry content identity"), algorithm


def _as_mapping(
    value: object,
    expected_fields: set[str],
    type_name: str,
) -> dict[str, object]:
    model_type = _MODEL_TYPES.get(type_name)
    if isinstance(value, Mapping):
        data = dict(value)
        if set(data) != expected_fields:
            raise ValueError(f"{type_name} has unknown or missing fields")
        if model_type is None:
            raise TypeError(f"{type_name} has no production model validator")
        validated = model_type.model_validate(data)
        data = validated.model_dump(mode="python")
    elif isinstance(getattr(type(value), "model_fields", None), dict):
        if model_type is not None and not isinstance(value, model_type):
            raise TypeError(f"{type_name} must be a production model or mapping")
        if set(type(value).model_fields) != expected_fields:
            raise ValueError(f"{type_name} has unknown or missing fields")
        if model_type is None:
            data = {
                field: getattr(value, field)
                for field in expected_fields
                if hasattr(value, field)
            }
        else:
            data = {
                field: getattr(value, field)
                for field in expected_fields
                if hasattr(value, field)
            }
            if set(data) != expected_fields:
                raise ValueError(f"{type_name} has unknown or missing fields")
            validated = model_type.model_validate(data)
            data = validated.model_dump(mode="python")
    else:
        raise TypeError(f"{type_name} must be a production model or mapping")
    if set(data) != expected_fields:
        raise ValueError(f"{type_name} has unknown or missing fields")
    return data


def _sorted_unique(
    values: object,
    key: str,
    label: str,
) -> tuple[object, ...]:
    items = _sequence(values, label)
    keyed: list[tuple[str, object]] = []
    seen: set[str] = set()
    for item in items:
        data = item if isinstance(item, Mapping) else _as_mapping(item, {key} | _model_field_names(item), label)
        item_key = _nonblank(data.get(key), key)
        if item_key in seen:
            raise ValueError(f"{label} contain duplicate {key}")
        seen.add(item_key)
        keyed.append((item_key, item))
    return tuple(item for _, item in sorted(keyed, key=lambda pair: pair[0]))


def _model_field_names(value: object) -> set[str]:
    fields = getattr(type(value), "model_fields", None)
    if isinstance(fields, dict):
        return set(fields)
    raise TypeError("collection item must be a production model or mapping")


def _ordered_unique_ids(values: object, label: str) -> list[str]:
    items = _sequence(values, label)
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        item = _nonblank(item, label)
        if item in seen:
            raise ValueError(f"{label} contain duplicate IDs")
        seen.add(item)
        output.append(item)
    return output


def _sequence(value: object, label: str) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(value)
    raise TypeError(f"{label} must be a sequence")


def _enum_value(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def _json_value(value: object) -> object:
    value = _enum_value(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported semantic value type: {type(value).__name__}")


def _json_engineering_value(value: object) -> object:
    if isinstance(value, Mapping):
        raise ValueError("evidence value must not contain nested mappings")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_engineering_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported engineering evidence value type: {type(value).__name__}")


def _nonblank(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must not be empty or whitespace")
    return value


def _optional_nonblank(value: object, field: str) -> str | None:
    return None if value is None else _nonblank(value, field)


def _sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(_SHA256_PREFIX)
        or len(value) != len(_SHA256_PREFIX) + 64
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{field} must be a sha256 hash")
    return value


def _require_literal(value: object, expected: str, field: str) -> str:
    if value != expected:
        raise ValueError(f"{field} must equal {expected}")
    return expected


__all__ = [
    "RawGeometryBindingKey",
    "VerifiedSemanticGeometryBindings",
    "semantic_geometry_artifact_identity_projection",
    "semantic_reference_frame_projection",
    "semantic_rotational_shaft_interface_projection",
    "semantic_mounting_face_interface_projection",
    "semantic_interface_definition_projection",
    "semantic_supplied_reference_frames_projection",
    "semantic_supplied_interface_definitions_projection",
    "semantic_geometry_derivation_transforms_projection",
    "semantic_m13_collections_projection",
    "semantic_shaft_d_flat_profile_projection",
    "semantic_mounting_hole_projection",
    "semantic_pilot_boss_projection",
    "semantic_interface_fact_projection",
    "semantic_interface_evidence_projection",
    "semantic_geometry_derivation_authority_fact_projection",
    "semantic_geometry_derivation_unit_conversion_projection",
    "semantic_geometry_derivation_transform_projection",
    "semantic_interface_fact_derivation_binding_projection",
    "semantic_interface_derivation_provenance_projection",
]
