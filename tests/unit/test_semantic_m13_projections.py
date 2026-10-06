from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ConfigDict

from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.models.component_property import (
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
)
from mechcad_harness.models.geometry_identity import (
    GeometryArtifactIdentity,
    geometry_reference_hash,
)
from mechcad_harness.models.supplied_component_interface import (
    GeometryDerivationAuthorityFact,
    GeometryDerivationAuthorityRole,
    GeometryDerivationStatus,
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
    SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceFact,
    SuppliedInterfaceTransformRole,
    SuppliedPilotBossReference,
    SuppliedShaftDFlatProfile,
    SuppliedShaftProfileKind,
)
from mechcad_harness.models.semantic_m13 import (
    semantic_geometry_artifact_identity_projection,
    semantic_geometry_derivation_authority_fact_projection,
    semantic_geometry_derivation_transform_projection,
    semantic_geometry_derivation_unit_conversion_projection,
    semantic_m13_collections_projection,
    semantic_interface_definition_projection,
    semantic_interface_derivation_provenance_projection,
    semantic_interface_evidence_projection,
    semantic_interface_fact_derivation_binding_projection,
    semantic_interface_fact_projection,
    semantic_mounting_face_interface_projection,
    semantic_mounting_hole_projection,
    semantic_pilot_boss_projection,
    semantic_reference_frame_projection,
    semantic_rotational_shaft_interface_projection,
    semantic_shaft_d_flat_profile_projection,
)


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64
CONTENT = "sha256:" + "d" * 64


def _geometry(artifact_id: str = "artifact-a", artifact_hash: str = HASH_A):
    return GeometryArtifactIdentity(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        source_identity="supplier:component",
        coordinate_system_id="component-local-mm",
    )


def _bindings(*geometries):
    return {
        (
            geometry.artifact_id,
            geometry.artifact_hash,
            geometry.source_identity,
            geometry.format,
            geometry.coordinate_system_id,
        ): {"algorithm": "step-content-identity@1", "content_hash": CONTENT}
        for geometry in geometries
    }


def _evidence(
    evidence_id: str,
    value=8.0,
    *,
    origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    source_identity="datasheet:component",
    source_document_identity="document-1",
    geometry_hash=None,
    conversion_provenance=None,
    basis_evidence_ids=(),
):
    shape = (
        SuppliedInterfaceEvidenceShape.TEXT
        if isinstance(value, str)
        else (
            SuppliedInterfaceEvidenceShape.SCALAR
            if isinstance(value, float)
            else SuppliedInterfaceEvidenceShape.VECTOR3
        )
    )
    return SuppliedInterfaceEvidence(
        evidence_id=evidence_id,
        shape=shape,
        value=value,
        canonical_unit=None if shape is SuppliedInterfaceEvidenceShape.TEXT else "mm",
        availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity=source_identity,
        applicability_context="component-context",
        conversion_provenance=conversion_provenance,
        evidence_origin=origin,
        source_document_identity=source_document_identity,
        geometry_reference_hash=geometry_hash,
        basis_evidence_ids=basis_evidence_ids,
    )


def _fact(fact_id: str, value=8.0, *, evidence=None, role=SuppliedInterfaceTransformRole.LENGTH_MM):
    shape, unit = {
        SuppliedInterfaceTransformRole.POINT_MM: (
            SuppliedInterfaceEvidenceShape.VECTOR3,
            "mm",
        ),
        SuppliedInterfaceTransformRole.LENGTH_MM: (
            SuppliedInterfaceEvidenceShape.SCALAR,
            "mm",
        ),
        SuppliedInterfaceTransformRole.DIRECTION_UNIT: (
            SuppliedInterfaceEvidenceShape.VECTOR3,
            "1",
        ),
        SuppliedInterfaceTransformRole.ORIENTATION: (
            SuppliedInterfaceEvidenceShape.QUATERNION,
            "1",
        ),
        SuppliedInterfaceTransformRole.TEXT: (
            SuppliedInterfaceEvidenceShape.TEXT,
            None,
        ),
    }[role]
    if evidence is None:
        evidence = SuppliedInterfaceEvidence(
            evidence_id=f"evidence:{fact_id}",
            shape=shape,
            value=value,
            canonical_unit=unit,
            availability=ComponentPropertyAvailability.AVAILABLE,
            authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
            source_identity="datasheet:component",
            evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
        )
    return SuppliedInterfaceFact(
        fact_id=fact_id,
        expected_shape=shape,
        expected_unit=unit,
        transform_role=role,
        evidence=(evidence,),
        accepted_evidence_id=evidence.evidence_id,
    )


def _shaft(geometry):
    ref = geometry_reference_hash(geometry)
    return RotationalShaftInterface(
        interface_id="shaft-interface",
        geometry_reference_hash=ref,
        geometry=geometry,
        reference_frame_id="frame-1",
        axis_point=_fact("axis-point", (1.0, 2.0, 3.0), role=SuppliedInterfaceTransformRole.POINT_MM),
        axis_direction=_fact("axis-direction", (0.0, 0.0, 1.0), role=SuppliedInterfaceTransformRole.DIRECTION_UNIT),
        nominal_shaft_diameter=_fact("shaft-diameter"),
        usable_axial_engagement_length=_fact("shaft-length", 20.0),
        shoulder_reference_plane=(
            _fact("shoulder-point", (0.0, 0.0, 0.0), role=SuppliedInterfaceTransformRole.POINT_MM),
            _fact("shoulder-normal", (0.0, 0.0, 1.0), role=SuppliedInterfaceTransformRole.DIRECTION_UNIT),
        ),
        shaft_profile=SuppliedShaftProfileKind.D_FLAT,
        d_flat_profile=SuppliedShaftDFlatProfile(
            flat_normal_direction=_fact(
                "flat-normal", (1.0, 0.0, 0.0), role=SuppliedInterfaceTransformRole.DIRECTION_UNIT
            ),
            flat_across_dimension=_fact("flat-across", 4.0),
            start_from_shoulder=_fact("flat-start", 2.0),
            effective_length=_fact("flat-length", 10.0),
        ),
        thread_designation=_fact(
            "shaft-thread", "M8", role=SuppliedInterfaceTransformRole.TEXT
        ),
    )


def _face(geometry):
    ref = geometry_reference_hash(geometry)
    hole = MountingHole(
        hole_id="hole-1",
        center=_fact("hole-center", (0.0, 1.0, 0.0), role=SuppliedInterfaceTransformRole.POINT_MM),
        axis=_fact("hole-axis", (0.0, 0.0, 1.0), role=SuppliedInterfaceTransformRole.DIRECTION_UNIT),
        nominal_diameter=_fact("hole-diameter", 5.0),
        thread_designation=_fact(
            "hole-thread", "M5", role=SuppliedInterfaceTransformRole.TEXT
        ),
    )
    return MountingFaceInterface(
        interface_id="face-interface",
        geometry_reference_hash=ref,
        geometry=geometry,
        face_reference_id="face-1",
        reference_frame_id="frame-1",
        plane_point=_fact("plane-point", (0.0, 0.0, 0.0), role=SuppliedInterfaceTransformRole.POINT_MM),
        outward_normal=_fact("face-normal", (0.0, 0.0, 1.0), role=SuppliedInterfaceTransformRole.DIRECTION_UNIT),
        holes=(hole,),
        pilot_boss=SuppliedPilotBossReference(
            point=_fact("pilot-point", (0.0, 0.0, 0.0), role=SuppliedInterfaceTransformRole.POINT_MM),
            axis=_fact("pilot-axis", (0.0, 0.0, 1.0), role=SuppliedInterfaceTransformRole.DIRECTION_UNIT),
            diameter=_fact("pilot-diameter", 12.0),
        ),
    )


def _frame(geometry):
    ref = geometry_reference_hash(geometry)
    return SuppliedComponentReferenceFrame(
        frame_id="frame-1",
        geometry_reference_hash=ref,
        origin=_fact("frame-origin", (0.0, 0.0, 0.0), role=SuppliedInterfaceTransformRole.POINT_MM),
        orientation=_fact(
            "frame-orientation", (1.0, 0.0, 0.0, 0.0), role=SuppliedInterfaceTransformRole.ORIENTATION
        ),
    )


def _authority_fact(fact_id: str, role, value):
    shape, unit = {
        GeometryDerivationAuthorityRole.TRANSLATION_MM: (
            SuppliedInterfaceEvidenceShape.VECTOR3,
            "mm",
        ),
        GeometryDerivationAuthorityRole.ROTATION: (
            SuppliedInterfaceEvidenceShape.QUATERNION,
            "1",
        ),
        GeometryDerivationAuthorityRole.UNIFORM_SCALE: (
            SuppliedInterfaceEvidenceShape.SCALAR,
            "1",
        ),
    }[role]
    evidence = SuppliedInterfaceEvidence(
        evidence_id=f"evidence:{fact_id}",
        shape=shape,
        value=value,
        canonical_unit=unit,
        availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity="datasheet:component",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    )
    return GeometryDerivationAuthorityFact(
        authority_role=role,
        expected_shape=shape,
        expected_unit=unit,
        evidence=(evidence,),
        accepted_evidence_id=evidence.evidence_id,
    )


def _transform(source_geometry, derived_geometry):
    return GeometryDerivationTransform(
        transform_id="transform-1",
        source_geometry=source_geometry,
        derived_geometry=derived_geometry,
        source_geometry_reference_hash=geometry_reference_hash(source_geometry),
        derived_geometry_reference_hash=geometry_reference_hash(derived_geometry),
        translation_fact=_authority_fact(
            "translation", GeometryDerivationAuthorityRole.TRANSLATION_MM, (0.0, 0.0, 0.0)
        ),
        rotation_fact=_authority_fact(
            "rotation", GeometryDerivationAuthorityRole.ROTATION, (1.0, 0.0, 0.0, 0.0)
        ),
        uniform_scale_fact=_authority_fact(
            "scale", GeometryDerivationAuthorityRole.UNIFORM_SCALE, 1.25
        ),
        unit_conversion=GeometryDerivationUnitConversion(
            source_unit="source-unit",
            derived_unit="mm",
            declaration="unit-conversion@1",
        ),
        status=GeometryDerivationStatus.ACCEPTED,
    )


def _context(*geometries):
    return _bindings(*geometries)


def test_all_reachable_m13_projections_have_exact_semantic_field_closure():
    source = _geometry()
    derived = _geometry("artifact-b", HASH_B)
    frame = _frame(source)
    shaft = _shaft(source)
    face = _face(source)
    provenance_shaft = RotationalShaftInterface.model_validate(
        shaft.model_dump(mode="json")
        | {"reference_frame_id": None, "interface_hash": "pending"}
    )
    direct = SuppliedComponentInterfaceDefinition(
        interface_id=provenance_shaft.interface_id,
        geometry_reference_hash=provenance_shaft.geometry_reference_hash,
        geometry=source,
        shaft=provenance_shaft,
    )
    transform = _transform(source, derived)
    binding = InterfaceFactDerivationBinding(
        fact_path="shaft.axis_point",
        source_fact_id=shaft.axis_point.fact_id,
        derived_fact_id="derived:axis-point:transform-1",
        source_evidence_id=shaft.axis_point.accepted_evidence_id,
        source_evidence_hash=shaft.axis_point.evidence[0].evidence_hash,
        transform_role=shaft.axis_point.transform_role,
    )
    provenance = InterfaceDerivationProvenance(
        source_interface_snapshot=direct,
        source_interface_hash=direct.interface_hash,
        transform_id=transform.transform_id,
        transform_hash=transform.transform_hash,
        source_geometry=source,
        derived_geometry=derived,
        source_geometry_reference_hash=transform.source_geometry_reference_hash,
        derived_geometry_reference_hash=transform.derived_geometry_reference_hash,
        fact_derivation_bindings=(binding,),
    )
    context = _context(source, derived)
    cases = (
        (semantic_geometry_artifact_identity_projection(source, context), {"source_identity", "format", "coordinate_system_id", "content_identity", "content_identity_algorithm"}),
        (semantic_reference_frame_projection(frame, context), {"frame_id", "geometry_reference_hash", "origin", "orientation"}),
        (semantic_rotational_shaft_interface_projection(shaft, context), {"interface_id", "geometry_reference_hash", "geometry", "reference_frame_id", "axis_point", "axis_direction", "nominal_shaft_diameter", "usable_axial_engagement_length", "shoulder_reference_plane", "shaft_profile", "d_flat_profile", "thread_designation"}),
        (semantic_mounting_face_interface_projection(face, context), {"interface_id", "geometry_reference_hash", "geometry", "face_reference_id", "reference_frame_id", "plane_point", "outward_normal", "holes", "pilot_boss"}),
        (semantic_interface_definition_projection(direct, context), {"kind", "interface_id", "geometry_reference_hash", "geometry", "shaft", "mounting_face", "derivation"}),
        (semantic_shaft_d_flat_profile_projection(shaft.d_flat_profile, context), {"flat_normal_direction", "flat_across_dimension", "start_from_shoulder", "effective_length"}),
        (semantic_mounting_hole_projection(face.holes[0], context), {"hole_id", "center", "axis", "nominal_diameter", "thread_designation"}),
        (semantic_pilot_boss_projection(face.pilot_boss, context), {"point", "axis", "diameter"}),
        (semantic_interface_fact_projection(shaft.axis_point, context), {"fact_id", "expected_shape", "expected_unit", "transform_role", "evidence", "accepted_evidence_id"}),
        (semantic_interface_evidence_projection(shaft.axis_point.evidence[0], context), {"evidence_id", "shape", "value", "canonical_unit", "availability", "authority", "source_identity", "applicability_context", "conversion_provenance", "evidence_origin", "geometry_reference_hash", "basis_evidence_ids"}),
        (semantic_geometry_derivation_authority_fact_projection(transform.translation_fact, context), {"authority_role", "expected_shape", "expected_unit", "evidence", "accepted_evidence_id"}),
        (semantic_geometry_derivation_unit_conversion_projection(transform.unit_conversion), {"source_unit", "derived_unit", "declaration"}),
        (semantic_geometry_derivation_transform_projection(transform, context), {"transform_id", "source_geometry", "derived_geometry", "source_geometry_reference_hash", "derived_geometry_reference_hash", "translation_fact", "rotation_fact", "uniform_scale_fact", "unit_conversion", "status"}),
        (semantic_interface_fact_derivation_binding_projection(binding), {"fact_path", "source_fact_id", "derived_fact_id", "source_evidence_id", "transform_role"}),
        (semantic_interface_derivation_provenance_projection(provenance, context), {"source_interface_snapshot", "source_reference_frame_snapshot", "derived_reference_frame_id", "transform_id", "source_geometry", "derived_geometry", "source_geometry_reference_hash", "derived_geometry_reference_hash", "fact_derivation_bindings", "materialization_algorithm"}),
    )
    for projection, expected_fields in cases:
        assert set(projection) == expected_fields
        encoded = str(projection)
        assert "artifact_id" not in encoded
        assert "artifact_hash" not in encoded
        assert "geometry_identity_hash" not in encoded
        assert "interface_hash" not in encoded
        assert "frame_hash" not in encoded
        assert "transform_hash" not in encoded
        assert "evidence_hash" not in encoded
        assert "provenance_hash" not in encoded


def test_raw_ids_and_legacy_hashes_do_not_change_semantic_m13_projection():
    first = _geometry("artifact-a", HASH_A)
    second = _geometry("artifact-c", HASH_C)
    context = _context(first, second)
    first_projection = semantic_geometry_artifact_identity_projection(first, context)
    second_projection = semantic_geometry_artifact_identity_projection(second, context)
    assert first_projection == second_projection

    first_frame = _frame(first)
    second_frame = SuppliedComponentReferenceFrame.model_validate(
        first_frame.model_dump(mode="json")
        | {
            "geometry_reference_hash": geometry_reference_hash(second),
            "frame_hash": "pending",
        }
    )
    assert semantic_reference_frame_projection(first_frame, context) == semantic_reference_frame_projection(second_frame, context)


def test_transformed_coordinate_free_references_follow_the_section_three_shape():
    geometry = GeometryArtifactIdentity(
        artifact_id="artifact-coordinate-free",
        artifact_hash=HASH_A,
        source_identity="supplier:component",
    )
    projection = semantic_reference_frame_projection(
        _frame(geometry), _context(geometry)
    )
    assert "coordinate_system_id" not in projection["geometry_reference_hash"]


def test_real_semantic_geometry_and_evidence_changes_are_sensitive():
    geometry = _geometry()
    changed_geometry = GeometryArtifactIdentity.model_validate(
        geometry.model_dump(mode="json")
        | {"source_identity": "supplier:changed", "geometry_identity_hash": "pending"}
    )
    context = _context(geometry, changed_geometry)
    assert semantic_geometry_artifact_identity_projection(geometry, context) != semantic_geometry_artifact_identity_projection(changed_geometry, context)

    first = _evidence("evidence-1", 8.0)
    changed = _evidence("evidence-1", 9.0)
    assert semantic_interface_evidence_projection(first, context) != semantic_interface_evidence_projection(changed, context)


def test_collection_order_is_canonical_and_duplicate_keys_fail_closed():
    geometry = _geometry()
    context = _context(geometry)
    low = _fact("a", 1.0)
    high = _fact("b", 2.0)
    fact_a = SuppliedInterfaceFact(
        fact_id="fact",
        expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(high.evidence[0], low.evidence[0]),
        accepted_evidence_id=low.evidence[0].evidence_id,
    )
    fact_b = fact_a.model_copy(update={"evidence": tuple(reversed(fact_a.evidence))})
    assert semantic_interface_fact_projection(fact_a, context) == semantic_interface_fact_projection(fact_b, context)

    duplicate = deepcopy(fact_a.model_dump(mode="json"))
    duplicate["evidence"] = [duplicate["evidence"][0], duplicate["evidence"][0]]
    with pytest.raises(ValueError, match="unique|duplicate"):
        semantic_interface_fact_projection(duplicate, context)


def test_outer_m13_collections_are_sorted_by_the_pinned_keys_and_reject_duplicates():
    geometry = _geometry()
    context = _context(geometry)
    frame_one = _frame(geometry)
    frame_zero = SuppliedComponentReferenceFrame.model_validate(
        frame_one.model_dump(mode="json")
        | {"frame_id": "frame-0", "frame_hash": "pending"}
    )
    shaft = _shaft(geometry)
    face = _face(geometry)
    shaft_definition = SuppliedComponentInterfaceDefinition(
        interface_id=shaft.interface_id,
        geometry_reference_hash=shaft.geometry_reference_hash,
        geometry=geometry,
        shaft=shaft,
    )
    face_definition = SuppliedComponentInterfaceDefinition(
        interface_id=face.interface_id,
        geometry_reference_hash=face.geometry_reference_hash,
        geometry=geometry,
        mounting_face=face,
    )
    collections = semantic_m13_collections_projection(
        (frame_one, frame_zero),
        (shaft_definition, face_definition),
        (),
        context,
    )
    assert [item["frame_id"] for item in collections["supplied_reference_frames"]] == [
        "frame-0",
        "frame-1",
    ]
    assert [item["interface_id"] for item in collections["supplied_interface_definitions"]] == [
        "face-interface",
        "shaft-interface",
    ]
    with pytest.raises(ValueError, match="duplicate"):
        semantic_m13_collections_projection(
            (frame_one, frame_one), (), (), context
        )


def test_evidence_origin_rules_transform_raw_sources_and_exclude_provenance_pointers():
    geometry = _geometry()
    geometry_hash = geometry_reference_hash(geometry)
    context = _context(geometry)
    inferred = _evidence(
        "inferred",
        (1.0, 0.0, 0.0),
        origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        source_identity=f"artifact:{HASH_A}",
        source_document_identity=geometry.artifact_id,
        geometry_hash=geometry_hash,
    )
    confirmed = _evidence(
        "confirmed",
        (1.0, 0.0, 0.0),
        origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        source_identity=f"artifact:{HASH_A}",
        source_document_identity=geometry.artifact_id,
        geometry_hash=geometry_hash,
        basis_evidence_ids=("inferred",),
    )
    derived = _evidence(
        "derived",
        10.0,
        origin=SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION,
        source_identity="transform:transform-1",
        source_document_identity="raw-document-must-not-enter",
        geometry_hash=geometry_hash,
        conversion_provenance=HASH_B,
        basis_evidence_ids=("source",),
    )
    source = _evidence("source", 8.0)

    inferred_projection = semantic_interface_evidence_projection(inferred, context)
    confirmed_projection = semantic_interface_evidence_projection(confirmed, context)
    derived_projection = semantic_interface_evidence_projection(derived, context)
    source_projection = semantic_interface_evidence_projection(source, context)
    assert inferred_projection["source_identity"] == CONTENT
    assert confirmed_projection["source_identity"] == CONTENT
    assert derived_projection["source_identity"] == "transform:transform-1"
    assert "conversion_provenance" not in derived_projection
    assert source_projection["source_identity"] == "datasheet:component"
    for projection in (inferred_projection, confirmed_projection, derived_projection, source_projection):
        assert "source_document_identity" not in projection
        if projection["geometry_reference_hash"] is not None:
            assert projection["geometry_reference_hash"]["content_identity"] == CONTENT


@pytest.mark.parametrize("extra_field", ["unknown", "artifact_id", "artifact_hash"])
def test_unknown_fields_fail_closed_even_when_the_extra_field_looks_raw_or_harmless(extra_field):
    geometry = _geometry()
    payload = geometry.model_dump(mode="json")
    payload[extra_field] = "unexpected"
    with pytest.raises((TypeError, ValueError)):
        semantic_geometry_artifact_identity_projection(payload, _context(geometry))


def test_kind_is_only_a_direct_materialized_discriminator_and_variant_is_independent():
    geometry = _geometry()
    shaft = _shaft(geometry)
    definition = SuppliedComponentInterfaceDefinition(
        interface_id=shaft.interface_id,
        geometry_reference_hash=shaft.geometry_reference_hash,
        geometry=geometry,
        shaft=shaft,
    )
    direct_payload = definition.model_dump(mode="json")
    materialized_payload = deepcopy(direct_payload)
    materialized_payload["kind"] = "materialized"
    materialized_payload["derivation"] = None
    with pytest.raises(ValueError, match="derivation"):
        semantic_interface_definition_projection(materialized_payload, _context(geometry))

    direct = semantic_interface_definition_projection(direct_payload, _context(geometry))
    assert direct["kind"] == "direct"
    assert direct["shaft"] is not None
    assert direct["mounting_face"] is None


def test_provenance_projection_closes_snapshots_and_replay_hashes():
    source = _geometry()
    derived = _geometry("artifact-b", HASH_B)
    shaft = _shaft(source)
    provenance_shaft = RotationalShaftInterface.model_validate(
        shaft.model_dump(mode="json")
        | {"reference_frame_id": None, "interface_hash": "pending"}
    )
    source_definition = SuppliedComponentInterfaceDefinition(
        interface_id=provenance_shaft.interface_id,
        geometry_reference_hash=provenance_shaft.geometry_reference_hash,
        geometry=source,
        shaft=provenance_shaft,
    )
    transform = _transform(source, derived)
    binding = InterfaceFactDerivationBinding(
        fact_path="shaft.axis_point",
        source_fact_id=shaft.axis_point.fact_id,
        derived_fact_id="derived:axis-point:transform-1",
        source_evidence_id=shaft.axis_point.accepted_evidence_id,
        source_evidence_hash=shaft.axis_point.evidence[0].evidence_hash,
        transform_role=shaft.axis_point.transform_role,
    )
    provenance = InterfaceDerivationProvenance(
        source_interface_snapshot=source_definition,
        source_interface_hash=source_definition.interface_hash,
        transform_id=transform.transform_id,
        transform_hash=transform.transform_hash,
        source_geometry=source,
        derived_geometry=derived,
        source_geometry_reference_hash=transform.source_geometry_reference_hash,
        derived_geometry_reference_hash=transform.derived_geometry_reference_hash,
        fact_derivation_bindings=(binding,),
    )
    projection = semantic_interface_derivation_provenance_projection(
        provenance, _context(source, derived)
    )
    assert projection["source_interface_snapshot"]["interface_id"] == source_definition.interface_id
    assert projection["transform_id"] == "transform-1"
    assert projection["materialization_algorithm"] == "supplied-interface-materialization@1"
    assert "source_interface_hash" not in projection
    assert "source_reference_frame_hash" not in projection
    assert "derived_reference_frame_hash" not in projection
    assert "transform_hash" not in projection
    assert "provenance_hash" not in projection


def test_mapping_evidence_cannot_bypass_origin_or_raw_value_invariants():
    geometry = _geometry()
    context = _context(geometry)
    human = _evidence("human").model_dump(mode="json")
    human["evidence_origin"] = SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION.value
    human["basis_evidence_ids"] = []
    with pytest.raises(ValueError, match="basis evidence"):
        semantic_interface_evidence_projection(human, context)

    raw_value = _evidence("raw-value").model_dump(mode="json")
    raw_value["value"] = {"nested": {"artifact_id": "raw-artifact"}}
    with pytest.raises(ValueError, match="raw"):
        semantic_interface_evidence_projection(raw_value, context)


def test_typed_models_with_declared_extra_fields_fail_closed():
    class ExtendedGeometry(GeometryArtifactIdentity):
        model_config = ConfigDict(frozen=True, extra="forbid")
        extra_semantic_field: str = "unexpected"

    geometry = ExtendedGeometry.model_validate(_geometry().model_dump(mode="json"))
    with pytest.raises(ValueError, match="unknown or missing fields"):
        semantic_geometry_artifact_identity_projection(geometry, _context(geometry))


def test_materialization_algorithm_is_pinned():
    source = _geometry()
    derived = _geometry("artifact-b", HASH_B)
    shaft = _shaft(source)
    provenance_shaft = RotationalShaftInterface.model_validate(
        shaft.model_dump(mode="json")
        | {"reference_frame_id": None, "interface_hash": "pending"}
    )
    source_definition = SuppliedComponentInterfaceDefinition(
        interface_id=provenance_shaft.interface_id,
        geometry_reference_hash=provenance_shaft.geometry_reference_hash,
        geometry=source,
        shaft=provenance_shaft,
    )
    transform = _transform(source, derived)
    binding = InterfaceFactDerivationBinding(
        fact_path="shaft.axis_point",
        source_fact_id=shaft.axis_point.fact_id,
        derived_fact_id="derived:axis-point:transform-1",
        source_evidence_id=shaft.axis_point.accepted_evidence_id,
        source_evidence_hash=shaft.axis_point.evidence[0].evidence_hash,
        transform_role=shaft.axis_point.transform_role,
    )
    provenance = InterfaceDerivationProvenance(
        source_interface_snapshot=source_definition,
        source_interface_hash=source_definition.interface_hash,
        transform_id=transform.transform_id,
        transform_hash=transform.transform_hash,
        source_geometry=source,
        derived_geometry=derived,
        source_geometry_reference_hash=transform.source_geometry_reference_hash,
        derived_geometry_reference_hash=transform.derived_geometry_reference_hash,
        fact_derivation_bindings=(binding,),
    ).model_dump(mode="json")
    provenance["materialization_algorithm"] = "other-algorithm@1"
    with pytest.raises(ValueError, match="materialization_algorithm"):
        semantic_interface_derivation_provenance_projection(
            provenance, _context(source, derived)
        )


def test_geometry_reference_must_match_the_enclosing_geometry():
    source = _geometry()
    other = _geometry("artifact-b", HASH_B)
    payload = _shaft(source).model_dump(mode="json")
    payload["geometry_reference_hash"] = geometry_reference_hash(other)
    with pytest.raises(ValueError, match="geometry reference"):
        semantic_rotational_shaft_interface_projection(
            payload, _context(source, other)
        )


def test_mapping_inputs_reuse_production_type_and_literal_validation():
    geometry = _geometry()
    payload = _fact("invalid").model_dump(mode="json")
    payload["expected_shape"] = "not-a-production-shape"
    with pytest.raises(ValueError, match="expected_shape"):
        semantic_interface_fact_projection(payload, _context(geometry))


def test_nested_evidence_geometry_references_stay_within_the_interface_geometry():
    source = _geometry()
    other = _geometry("artifact-b", HASH_B)
    payload = _shaft(source).model_dump(mode="json")
    evidence = payload["axis_point"]["evidence"][0]
    evidence["geometry_reference_hash"] = geometry_reference_hash(other)
    evidence["evidence_hash"] = "pending"
    payload["axis_point"]["fact_hash"] = "pending"
    payload["interface_hash"] = "pending"
    with pytest.raises(ValueError, match="geometry reference.*enclosing geometry"):
        semantic_rotational_shaft_interface_projection(
            payload, _context(source, other)
        )


def test_mapping_and_model_inputs_use_the_same_normalized_semantic_values():
    geometry = _geometry()
    model = _evidence("normalized", 8.0)
    mapping = model.model_dump(mode="json")
    mapping["value"] = 8
    assert canonical_json_bytes(
        semantic_interface_evidence_projection(model, _context(geometry))
    ) == canonical_json_bytes(
        semantic_interface_evidence_projection(mapping, _context(geometry))
    )


def test_forged_typed_inputs_cannot_bypass_validation_or_raw_value_closure():
    geometry = _geometry()
    forged_shape = _evidence("forged-shape").model_dump(mode="python")
    forged_shape["shape"] = "not-a-production-shape"
    with pytest.raises(ValueError, match="shape"):
        semantic_interface_evidence_projection(
            SuppliedInterfaceEvidence.model_construct(**forged_shape),
            _context(geometry),
        )

    forged_value = _evidence("forged-value").model_dump(mode="python")
    forged_value["value"] = {"evidence_hash": HASH_A}
    with pytest.raises(ValueError, match="evidence value|valid number"):
        semantic_interface_evidence_projection(
            SuppliedInterfaceEvidence.model_construct(**forged_value),
            _context(geometry),
        )
