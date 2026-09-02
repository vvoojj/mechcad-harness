import json

import pytest
from pydantic import ValidationError

from mechcad_harness.candidates.models import ComponentSpecificationSnapshot, GeometrySourceReference
from mechcad_harness.models.component_property import (
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
)
from mechcad_harness.models import CanonicalComponentSpecification, CanonicalGeometrySourceReference
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.supplied_component_interface import (
    RotationalShaftInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedInterfaceEvidence,
    SuppliedInterfaceEvidenceOrigin,
    SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceFact,
    SuppliedInterfaceTransformRole,
)

# Goldens captured from unmodified M12 models on 2026-09-01. They are literal
# compatibility locks, never regenerated after M13 model work begins.
GOLDEN_CANDIDATE_REFERENCE_JSON = (
    '{"artifact_id":"ART-1","artifact_hash":"sha256:' + "1" * 64
    + '","source_identity":"vendor:geometry:1","format":"step"}'
)
GOLDEN_CANDIDATE_SPECIFICATION_JSON = (
    '{"schema_version":"component-specification@1","component_type":"motor",'
    '"manufacturer":"Acme","part_number":"M-1","source_identity":"vendor:acme:M-1",'
    '"properties":[],"geometry_source":' + GOLDEN_CANDIDATE_REFERENCE_JSON
    + ',"interfaces":["output"],"compatibility_declarations":["mount"],'
    '"specification_hash":"sha256:8bf62043ceb309199f6e359cffccc3737a79ee1bd7e065cbd6a186ec7a611e4b"}'
)
GOLDEN_CANONICAL_REFERENCE_JSON = (
    '{"artifact_id":"ART-1","artifact_hash":"sha256:' + "1" * 64
    + '","source_identity":"vendor:geometry:1","format":"step",'
    '"reference_hash":"sha256:a3ec5de09c59fa48a2a331916ab5d060db2d03b4ff5dbe5e3b02185a3bb26f3a"}'
)
GOLDEN_CANONICAL_SPECIFICATION_JSON = (
    '{"schema_version":"canonical-component-specification@1","component_type":"motor",'
    '"manufacturer":"Acme","part_number":"M-1","source_identity":"vendor:acme:M-1",'
    '"properties":[],"geometry_source":' + GOLDEN_CANONICAL_REFERENCE_JSON
    + ',"interfaces":["output"],"compatibility_declarations":["mount"],'
    '"specification_hash":"sha256:10cef1cc30c9f53b92b7908a2b9992edb7ac95a9ac8f24700eb353c31d23f898"}'
)


def test_canonical_reference_legacy_payload_reloads_with_unchanged_hash():
    ref = CanonicalGeometrySourceReference.model_validate_json(GOLDEN_CANONICAL_REFERENCE_JSON)
    assert ref.reference_hash == "sha256:a3ec5de09c59fa48a2a331916ab5d060db2d03b4ff5dbe5e3b02185a3bb26f3a"
    assert ref.coordinate_system_id is None
    assert ref.model_dump(mode="json") == json.loads(GOLDEN_CANONICAL_REFERENCE_JSON)
    assert ref.model_dump_json() == GOLDEN_CANONICAL_REFERENCE_JSON


def test_legacy_candidate_reference_and_complete_specification_round_trip_byte_identically():
    candidate_payload = json.loads(GOLDEN_CANDIDATE_SPECIFICATION_JSON)
    specification = ComponentSpecificationSnapshot.model_validate(candidate_payload)
    assert specification.specification_hash == "sha256:8bf62043ceb309199f6e359cffccc3737a79ee1bd7e065cbd6a186ec7a611e4b"
    assert specification.model_dump(mode="json") == candidate_payload
    assert specification.model_dump_json() == GOLDEN_CANDIDATE_SPECIFICATION_JSON
    assert specification.geometry_source.model_dump(mode="json") == json.loads(GOLDEN_CANDIDATE_REFERENCE_JSON)
    assert specification.geometry_source.model_dump_json() == GOLDEN_CANDIDATE_REFERENCE_JSON


def test_complete_canonical_specification_legacy_hash_is_unchanged():
    canonical = CanonicalComponentSpecification.model_validate_json(GOLDEN_CANONICAL_SPECIFICATION_JSON)
    assert canonical.specification_hash == "sha256:10cef1cc30c9f53b92b7908a2b9992edb7ac95a9ac8f24700eb353c31d23f898"
    assert canonical.model_dump(mode="json") == json.loads(GOLDEN_CANONICAL_SPECIFICATION_JSON)
    assert canonical.model_dump_json() == GOLDEN_CANONICAL_SPECIFICATION_JSON


def test_candidate_reference_additive_fields_parse_old_payload():
    legacy = {
        "artifact_id": "ART-1",
        "artifact_hash": "sha256:" + "1" * 64,
        "source_identity": "src",
        "format": "step",
    }
    ref = GeometrySourceReference.model_validate(legacy)
    assert ref.coordinate_system_id is None
    assert ref.reference_hash.startswith("sha256:")
    assert ref.model_dump(mode="json") == legacy


def test_coordinate_system_id_changes_reference_hash_when_set():
    base = GeometrySourceReference(artifact_id="A", artifact_hash="sha256:" + "2" * 64, source_identity="s")
    stamped = GeometrySourceReference.model_validate(
        base.model_dump(mode="json") | {"coordinate_system_id": "step-model-coordinates@1"}
    )
    assert stamped.reference_hash != base.reference_hash
    assert GeometryArtifactIdentity.from_candidate(stamped).coordinate_system_id == "step-model-coordinates@1"
    canonical = CanonicalGeometrySourceReference(
        artifact_id="A",
        artifact_hash="sha256:" + "2" * 64,
        source_identity="s",
        coordinate_system_id="step-model-coordinates@1",
    )
    assert GeometryArtifactIdentity.from_canonical(canonical).coordinate_system_id == "step-model-coordinates@1"


def test_coordinate_system_id_validation():
    with pytest.raises(ValidationError):
        GeometrySourceReference(artifact_id="A", artifact_hash="sha256:" + "2" * 64,
                                 source_identity="s", coordinate_system_id="  ")


def test_canonical_reference_rejects_literal_legacy_hash_when_coordinate_system_is_present():
    legacy_payload = json.loads(GOLDEN_CANONICAL_REFERENCE_JSON)
    with pytest.raises(ValidationError, match="geometry source reference hash mismatch"):
        CanonicalGeometrySourceReference.model_validate(
            legacy_payload | {"coordinate_system_id": "step-model-coordinates@1"}
        )


def _spec_fact(fact_id, role, value, *, source_identity="source:interface"):
    shape, unit = {
        SuppliedInterfaceTransformRole.POINT_MM: (SuppliedInterfaceEvidenceShape.VECTOR3, "mm"),
        SuppliedInterfaceTransformRole.LENGTH_MM: (SuppliedInterfaceEvidenceShape.SCALAR, "mm"),
        SuppliedInterfaceTransformRole.DIRECTION_UNIT: (SuppliedInterfaceEvidenceShape.VECTOR3, "1"),
    }[role]
    evidence = SuppliedInterfaceEvidence(
        evidence_id=f"evidence:{fact_id}",
        shape=shape,
        value=value,
        canonical_unit=unit,
        availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity=source_identity,
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


def _direct_spec_interface(geometry, *, source_identity="source:interface"):
    geometry_reference_hash = GeometrySourceReference(
        artifact_id=geometry.artifact_id,
        artifact_hash=geometry.artifact_hash,
        source_identity=geometry.source_identity,
        coordinate_system_id=geometry.coordinate_system_id,
    ).reference_hash
    shaft = RotationalShaftInterface(
        interface_id="output-shaft",
        geometry_reference_hash=geometry_reference_hash,
        geometry=geometry,
        axis_point=_spec_fact("axis-point", SuppliedInterfaceTransformRole.POINT_MM, (1.0, 2.0, 3.0), source_identity=source_identity),
        axis_direction=_spec_fact("axis-direction", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0), source_identity=source_identity),
        nominal_shaft_diameter=_spec_fact("shaft-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 8.0, source_identity=source_identity),
        usable_axial_engagement_length=_spec_fact("engagement", SuppliedInterfaceTransformRole.LENGTH_MM, 20.0, source_identity=source_identity),
    )
    return SuppliedComponentInterfaceDefinition(
        interface_id=shaft.interface_id,
        geometry_reference_hash=geometry_reference_hash,
        geometry=geometry,
        shaft=shaft,
    )


def _candidate_interface_spec(*, source_identity="source:interface"):
    reference = GeometrySourceReference(
        artifact_id="ART-SPEC",
        artifact_hash="sha256:" + "3" * 64,
        source_identity="source:geometry",
        coordinate_system_id="step-model-coordinates@1",
    )
    geometry = GeometryArtifactIdentity.from_candidate(reference)
    interface = _direct_spec_interface(geometry, source_identity=source_identity)
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="source:motor",
        geometry_source=reference,
        interfaces=(interface.interface_id,),
        supplied_interface_definitions=(interface,),
    )


def test_component_specification_at_2_serializes_typed_interfaces_and_hashes_nested_changes():
    specification = _candidate_interface_spec()
    payload = specification.model_dump(mode="json")

    assert payload["schema_version"] == "component-specification@2"
    assert payload["supplied_interface_definitions"][0]["interface_id"] == "output-shaft"
    assert specification.model_dump_json() == json.dumps(payload, separators=(",", ":"))

    changed = _candidate_interface_spec(source_identity="source:interface:changed")
    assert changed.specification_hash != specification.specification_hash


def test_canonical_component_specification_at_2_serializes_and_hashes_nested_changes():
    candidate = _candidate_interface_spec()
    canonical = CanonicalComponentSpecification(
        schema_version="canonical-component-specification@2",
        component_type=candidate.component_type,
        source_identity=candidate.source_identity,
        geometry_source=CanonicalGeometrySourceReference.model_validate(
            candidate.geometry_source.model_dump(mode="json")
        ),
        interfaces=candidate.interfaces,
        supplied_interface_definitions=candidate.supplied_interface_definitions,
    )
    payload = canonical.model_dump(mode="json")
    assert payload["schema_version"] == "canonical-component-specification@2"
    assert payload["supplied_interface_definitions"][0]["interface_id"] == "output-shaft"
    assert canonical.model_dump_json() == json.dumps(payload, separators=(",", ":"))

    changed_candidate = _candidate_interface_spec(source_identity="source:interface:changed")
    changed = CanonicalComponentSpecification(
        schema_version="canonical-component-specification@2",
        component_type=changed_candidate.component_type,
        source_identity=changed_candidate.source_identity,
        geometry_source=CanonicalGeometrySourceReference.model_validate(
            changed_candidate.geometry_source.model_dump(mode="json")
        ),
        interfaces=changed_candidate.interfaces,
        supplied_interface_definitions=changed_candidate.supplied_interface_definitions,
    )
    assert changed.specification_hash != canonical.specification_hash


def test_at_1_rejects_m13_records_and_coordinate_system_semantics():
    reference = GeometrySourceReference(
        artifact_id="ART-SPEC",
        artifact_hash="sha256:" + "3" * 64,
        source_identity="source:geometry",
    )
    nonlegacy = _candidate_interface_spec()
    with pytest.raises(ValidationError, match="component-specification@1"):
        ComponentSpecificationSnapshot.model_validate(
            nonlegacy.model_dump(mode="json")
            | {"schema_version": "component-specification@1"}
        )

    coordinate_reference = GeometrySourceReference(
        artifact_id="ART-SPEC",
        artifact_hash="sha256:" + "3" * 64,
        source_identity="source:geometry",
        coordinate_system_id="step-model-coordinates@1",
    )
    with pytest.raises(ValidationError, match="component-specification@1"):
        ComponentSpecificationSnapshot.model_validate(
            {
                "schema_version": "component-specification@1",
                "component_type": "motor",
                "source_identity": "source:motor",
                "geometry_source": coordinate_reference.model_dump(mode="json"),
            }
        )


def test_canonical_at_1_rejects_m13_records():
    candidate = _candidate_interface_spec()
    canonical = CanonicalComponentSpecification(
        schema_version="canonical-component-specification@2",
        component_type=candidate.component_type,
        source_identity=candidate.source_identity,
        geometry_source=CanonicalGeometrySourceReference.model_validate(
            candidate.geometry_source.model_dump(mode="json")
        ),
        interfaces=candidate.interfaces,
        supplied_interface_definitions=candidate.supplied_interface_definitions,
    )

    with pytest.raises(ValidationError, match="canonical-component-specification@1"):
        CanonicalComponentSpecification.model_validate(
            canonical.model_dump(mode="json")
            | {"schema_version": "canonical-component-specification@1"}
        )


def test_canonical_at_1_rejects_non_none_geometry_coordinate_system():
    reference = CanonicalGeometrySourceReference(
        artifact_id="ART-SPEC",
        artifact_hash="sha256:" + "3" * 64,
        source_identity="source:geometry",
        coordinate_system_id="step-model-coordinates@1",
    )

    with pytest.raises(ValidationError, match="canonical-component-specification@1"):
        CanonicalComponentSpecification(
            schema_version="canonical-component-specification@1",
            component_type="motor",
            source_identity="source:motor",
            geometry_source=reference,
        )


def test_canonical_at_2_m13_payload_requires_selected_geometry_coordinate_system():
    reference = CanonicalGeometrySourceReference(
        artifact_id="ART-SPEC",
        artifact_hash="sha256:" + "3" * 64,
        source_identity="source:geometry",
    )
    geometry = GeometryArtifactIdentity.from_canonical(reference)
    interface = _direct_spec_interface(geometry)

    with pytest.raises(ValidationError, match="coordinate"):
        CanonicalComponentSpecification(
            schema_version="canonical-component-specification@2",
            component_type="motor",
            source_identity="source:motor",
            geometry_source=reference,
            interfaces=(interface.interface_id,),
            supplied_interface_definitions=(interface,),
        )
