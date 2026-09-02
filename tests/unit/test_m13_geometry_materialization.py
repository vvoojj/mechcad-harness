import math

import pytest
from pydantic import ValidationError

from mechcad_harness.models.component_property import (
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
)
from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.supplied_component_interface import (
    InterfaceFactDerivationBinding,
    MaterializationIntegrityError,
    MaterializedInterfaceVerifier,
    MountingHole,
    MountingFaceInterface,
    RotationalShaftInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedComponentReferenceFrame,
    GeometryDerivationAuthorityFact,
    GeometryDerivationAuthorityRole,
    GeometryDerivationStatus,
    GeometryDerivationTransform,
    GeometryDerivationUnitConversion,
    SuppliedInterfaceEvidence,
    SuppliedInterfaceEvidenceOrigin,
    SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceFact,
    SuppliedInterfaceTransformRole,
    apply_transform_role,
    build_derivation_provenance,
    construct_materialized_result,
    derive_interface_semantics,
    derive_reference_frame_semantics,
    materialize_interface,
    require_authoritative_transform,
    transform_fact,
)


SCALE_125 = 1.25
HASH_1 = "sha256:" + "1" * 64
HASH_2 = "sha256:" + "2" * 64
HASH_3 = "sha256:" + "3" * 64


def _reference_hash(geometry):
    return GeometrySourceReference(
        artifact_id=geometry.artifact_id,
        artifact_hash=geometry.artifact_hash,
        source_identity=geometry.source_identity,
        coordinate_system_id=geometry.coordinate_system_id,
    ).reference_hash


def _authority_fact(
    role,
    shape,
    unit,
    value,
    evidence_id,
    *,
    origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    accepted=True,
    availability=ComponentPropertyAvailability.AVAILABLE,
):
    records = [SuppliedInterfaceEvidence(
        evidence_id=evidence_id,
        shape=shape,
        value=value,
        canonical_unit=unit,
        availability=availability,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity="vendor:normalization:1",
        evidence_origin=origin,
    )]
    if origin is SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION:
        basis_id = f"basis:{evidence_id}"
        records = [
            SuppliedInterfaceEvidence(
                evidence_id=basis_id,
                shape=shape,
                value=value,
                canonical_unit=unit,
                availability=availability,
                authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
                source_identity="vendor:normalization:source",
                evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
            ),
            SuppliedInterfaceEvidence(
                evidence_id=evidence_id,
                shape=shape,
                value=value,
                canonical_unit=unit,
                availability=availability,
                authority=ComponentPropertyAuthority.USER_DECLARED,
                source_identity="review:normalization",
                evidence_origin=origin,
                basis_evidence_ids=(basis_id,),
            ),
        ]
    return GeometryDerivationAuthorityFact(
        authority_role=role,
        expected_shape=shape,
        expected_unit=unit,
        evidence=tuple(records),
        accepted_evidence_id=evidence_id if accepted else None,
    )


def _transform(
    *,
    scale=SCALE_125,
    rotation=(1.0, 0.0, 0.0, 0.0),
    status=GeometryDerivationStatus.ACCEPTED,
    translation_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    rotation_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    scale_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    translation_accepted=True,
    rotation_accepted=True,
    scale_accepted=True,
):
    def identity(artifact_id, artifact_hash):
        return GeometryArtifactIdentity(
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            source_identity="s",
        )

    source_geometry = identity("ART-SRC", HASH_1)
    derived_geometry = identity("ART-NRM", HASH_2)

    return GeometryDerivationTransform(
        transform_id="T1",
        source_geometry=source_geometry,
        derived_geometry=derived_geometry,
        source_geometry_reference_hash=_reference_hash(source_geometry),
        derived_geometry_reference_hash=_reference_hash(derived_geometry),
        translation_fact=_authority_fact(
            GeometryDerivationAuthorityRole.TRANSLATION_MM,
            SuppliedInterfaceEvidenceShape.VECTOR3,
            "mm",
            (0.0, 0.0, 0.0),
            "translation-source",
            origin=translation_origin,
            accepted=translation_accepted,
        ),
        rotation_fact=_authority_fact(
            GeometryDerivationAuthorityRole.ROTATION,
            SuppliedInterfaceEvidenceShape.QUATERNION,
            "1",
            rotation,
            "rotation-source",
            origin=rotation_origin,
            accepted=rotation_accepted,
        ),
        uniform_scale_fact=_authority_fact(
            GeometryDerivationAuthorityRole.UNIFORM_SCALE,
            SuppliedInterfaceEvidenceShape.SCALAR,
            "1",
            scale,
            "scale-source",
            origin=scale_origin,
            accepted=scale_accepted,
        ),
        unit_conversion=GeometryDerivationUnitConversion(
            source_unit="source-model-unit",
            derived_unit="derived-model-unit",
            declaration="explicit-model-unit-normalization@1",
        ),
        status=status,
    )


def _inferred_transform():
    transform = _transform(
        status=GeometryDerivationStatus.PROPOSED,
        scale_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        scale_accepted=False,
    )
    payload = transform.model_dump(mode="json")
    payload["uniform_scale_fact"]["evidence"][0]["geometry_reference_hash"] = _reference_hash(
        transform.derived_geometry
    )
    payload["uniform_scale_fact"]["evidence"][0]["evidence_hash"] = "pending"
    payload["uniform_scale_fact"]["authority_fact_hash"] = "pending"
    payload["transform_hash"] = "pending"
    return GeometryDerivationTransform.model_validate(payload)


def test_point_and_length_roles_scale_and_translate_only_points():
    transform = _transform()

    assert apply_transform_role(
        SuppliedInterfaceTransformRole.POINT_MM,
        (8.0, 0.0, 24.0),
        transform,
    ) == pytest.approx((10.0, 0.0, 30.0))
    assert apply_transform_role(
        SuppliedInterfaceTransformRole.LENGTH_MM, 8.0, transform
    ) == pytest.approx(10.0)


def test_point_length_and_displacement_apply_rotation_before_scale():
    transform = _transform(rotation=(math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)))

    assert apply_transform_role(
        SuppliedInterfaceTransformRole.POINT_MM,
        (8.0, 0.0, 24.0),
        transform,
    ) == pytest.approx((0.0, 10.0, 30.0))
    assert apply_transform_role(
        SuppliedInterfaceTransformRole.DISPLACEMENT_MM,
        (1.0, 0.0, 0.0),
        transform,
    ) == pytest.approx((0.0, 1.25, 0.0))


def test_displacement_rotation_and_scale_have_no_translation():
    transform = _transform()
    payload = transform.model_dump(mode="json")
    payload["translation_fact"]["evidence"][0]["value"] = (1.0, 2.0, 3.0)
    payload["translation_fact"]["evidence"][0]["evidence_hash"] = "pending"
    payload["translation_fact"]["authority_fact_hash"] = "pending"
    payload["transform_hash"] = "pending"
    translated = GeometryDerivationTransform.model_validate(payload)

    assert apply_transform_role(
        SuppliedInterfaceTransformRole.DISPLACEMENT_MM,
        (1.0, 0.0, 0.0),
        translated,
    ) == pytest.approx((1.25, 0.0, 0.0))
    assert apply_transform_role(
        SuppliedInterfaceTransformRole.POINT_MM,
        (1.0, 0.0, 0.0),
        translated,
    ) == pytest.approx((2.25, 2.0, 3.0))


def test_direction_normalizes_rotated_vector_and_text_is_unchanged():
    transform = _transform(rotation=(math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)))

    assert apply_transform_role(
        SuppliedInterfaceTransformRole.DIRECTION_UNIT,
        (2.0, 0.0, 0.0),
        transform,
    ) == pytest.approx((0.0, 1.0, 0.0))
    assert apply_transform_role(
        SuppliedInterfaceTransformRole.TEXT, "M4", transform
    ) == "M4"


def test_orientation_composes_and_normalizes_rotation_quaternion():
    transform = _transform(
        scale=1.0,
        rotation=(math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)),
    )
    assert apply_transform_role(
        SuppliedInterfaceTransformRole.ORIENTATION,
        (math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0),
        transform,
    ) == pytest.approx((0.5, 0.5, 0.5, 0.5))


def test_explicit_unit_declaration_is_required_and_identity_binds_hash():
    transform = _transform()
    changed = GeometryDerivationTransform.model_validate(
        transform.model_dump(mode="json") | {
            "unit_conversion": {
                "source_unit": "source-model-unit",
                "derived_unit": "derived-model-unit",
                "declaration": "explicit-model-unit-normalization@2",
            },
            "transform_hash": "pending",
        }
    )
    assert changed.transform_hash != transform.transform_hash

    with pytest.raises(ValidationError):
        GeometryDerivationUnitConversion(
            source_unit=" ",
            derived_unit="derived-model-unit",
            declaration="explicit",
        )


def test_transform_rejects_non_distinct_geometry_and_invalid_scale():
    with pytest.raises(ValidationError):
        _transform(scale=0.0)
    with pytest.raises(ValidationError):
        _transform(scale=float("nan"))

    payload = _transform().model_dump(mode="json")
    payload["derived_geometry"] = payload["source_geometry"]
    payload["transform_hash"] = "pending"
    with pytest.raises(ValidationError):
        GeometryDerivationTransform.model_validate(payload)


@pytest.mark.parametrize("field", [
    "source_geometry_reference_hash",
    "derived_geometry_reference_hash",
])
def test_transform_reference_hash_must_be_exact_projection_including_legacy_none_coordinate_system(field):
    transform = _transform()
    payload = transform.model_dump(mode="json")
    geometry = transform.source_geometry if field.startswith("source") else transform.derived_geometry
    payload[field] = geometry.geometry_identity_hash
    payload["transform_hash"] = "pending"

    with pytest.raises(ValidationError, match="geometry reference hash"):
        GeometryDerivationTransform.model_validate(payload)


def test_transform_inferred_evidence_must_bind_to_source_or_derived_geometry():
    transform = _transform()
    payload = transform.model_dump(mode="json")
    inferred = payload["uniform_scale_fact"]["evidence"][0]
    inferred["evidence_origin"] = SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED
    inferred["geometry_reference_hash"] = HASH_3
    inferred["evidence_hash"] = "pending"
    payload["uniform_scale_fact"]["accepted_evidence_id"] = None
    payload["uniform_scale_fact"]["authority_fact_hash"] = "pending"
    payload["transform_hash"] = "pending"
    with pytest.raises(ValidationError, match="geometry reference"):
        GeometryDerivationTransform.model_validate(payload)


@pytest.mark.parametrize("fact_field, evidence_field, value", [
    ("translation_fact", "source_identity", "vendor:translation:2"),
    (
        "rotation_fact",
        "evidence_origin",
        SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
    ),
    ("uniform_scale_fact", "authority", ComponentPropertyAuthority.MEASURED_LOCAL),
])
def test_all_transform_component_evidence_changes_identity(
    fact_field, evidence_field, value
):
    transform = _transform()
    payload = transform.model_dump(mode="json")
    payload[fact_field]["evidence"][0][evidence_field] = value
    payload[fact_field]["evidence"][0]["evidence_hash"] = "pending"
    if (
        evidence_field == "evidence_origin"
        and value is SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION
    ):
        basis = dict(payload[fact_field]["evidence"][0])
        basis.update(
            evidence_id="basis:rotation-source",
            evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
            basis_evidence_ids=(),
            evidence_hash="pending",
        )
        payload[fact_field]["evidence"][0]["basis_evidence_ids"] = (
            "basis:rotation-source",
        )
        payload[fact_field]["evidence"].append(basis)
    payload[fact_field]["authority_fact_hash"] = "pending"
    payload["transform_hash"] = "pending"

    changed = GeometryDerivationTransform.model_validate(payload)
    assert changed.transform_hash != transform.transform_hash


@pytest.mark.parametrize("component", ["translation_fact", "rotation_fact", "uniform_scale_fact"])
def test_accepted_but_unselected_or_inferred_component_is_not_authoritative(component):
    kwargs = {"translation_accepted": True, "rotation_accepted": True, "scale_accepted": True}
    kwargs[{
        "translation_fact": "translation_accepted",
        "rotation_fact": "rotation_accepted",
        "uniform_scale_fact": "scale_accepted",
    }[component]] = False
    transform = _transform(**kwargs)
    with pytest.raises(ValueError):
        require_authoritative_transform(transform)

    inferred_kwargs = {"translation_origin": SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
                       "rotation_origin": SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
                       "scale_origin": SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT}
    inferred_kwargs[{
        "translation_fact": "translation_origin",
        "rotation_fact": "rotation_origin",
        "uniform_scale_fact": "scale_origin",
    }[component]] = SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED
    with pytest.raises(ValueError):
        require_authoritative_transform(_transform(**inferred_kwargs))


def test_proposed_transform_is_structural_but_not_authoritative():
    transform = _transform(status=GeometryDerivationStatus.PROPOSED)
    with pytest.raises(ValueError):
        require_authoritative_transform(transform)


def test_identity_translation_and_rotation_still_require_selected_evidence():
    transform = _transform(translation_accepted=False, rotation_accepted=False)
    with pytest.raises(ValueError):
        require_authoritative_transform(transform)


@pytest.mark.parametrize("role, shape, unit, value", [
    (
        GeometryDerivationAuthorityRole.TRANSLATION_MM,
        SuppliedInterfaceEvidenceShape.SCALAR,
        "mm",
        0.0,
    ),
    (
        GeometryDerivationAuthorityRole.ROTATION,
        SuppliedInterfaceEvidenceShape.VECTOR3,
        "1",
        (0.0, 0.0, 1.0),
    ),
    (
        GeometryDerivationAuthorityRole.UNIFORM_SCALE,
        SuppliedInterfaceEvidenceShape.SCALAR,
        "mm",
        1.25,
    ),
])
def test_transform_authority_facts_require_exact_role_matrix(role, shape, unit, value):
    with pytest.raises(ValidationError):
        _authority_fact(role, shape, unit, value, "bad")


@pytest.mark.parametrize("role, value", [
    (SuppliedInterfaceTransformRole.POINT_MM, 1.0),
    (SuppliedInterfaceTransformRole.LENGTH_MM, (1.0, 2.0, 3.0)),
    (SuppliedInterfaceTransformRole.DISPLACEMENT_MM, 1.0),
    (SuppliedInterfaceTransformRole.DIRECTION_UNIT, (1.0, 2.0)),
    (SuppliedInterfaceTransformRole.ORIENTATION, (1.0, 0.0, 0.0)),
])
def test_runtime_value_shape_must_match_transform_role(role, value):
    with pytest.raises(ValueError):
        apply_transform_role(role, value, _transform())


def test_transform_fact_requires_role_matrix_and_binds_source_evidence():
    transform = _transform()
    source = SuppliedInterfaceFact(
        fact_id="point-fact",
        expected_shape=SuppliedInterfaceEvidenceShape.VECTOR3,
        expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.POINT_MM,
        evidence=(SuppliedInterfaceEvidence(
            evidence_id="point-source",
            shape=SuppliedInterfaceEvidenceShape.VECTOR3,
            value=(1.0, 2.0, 3.0),
            canonical_unit="mm",
            availability=ComponentPropertyAvailability.AVAILABLE,
            authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
            source_identity="vendor:interface:1",
            evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
        ),),
        accepted_evidence_id="point-source",
    )
    derived = transform_fact(source, transform)

    assert derived.evidence_origin is SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION
    assert derived.basis_evidence_ids == ("point-source",)
    assert derived.shape is SuppliedInterfaceEvidenceShape.VECTOR3
    assert derived.canonical_unit == "mm"
    assert derived.value == pytest.approx((1.25, 2.5, 3.75))

    with pytest.raises(TypeError):
        transform_fact(transform.translation_fact, transform)


def test_transform_fact_rejects_proposed_transform_before_materialization():
    source = SuppliedInterfaceFact(
        fact_id="point-fact",
        expected_shape=SuppliedInterfaceEvidenceShape.VECTOR3,
        expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.POINT_MM,
        evidence=(SuppliedInterfaceEvidence(
            evidence_id="point-source",
            shape=SuppliedInterfaceEvidenceShape.VECTOR3,
            value=(1.0, 2.0, 3.0),
            canonical_unit="mm",
            availability=ComponentPropertyAvailability.AVAILABLE,
            authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
            source_identity="vendor:interface:1",
            evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
        ),),
        accepted_evidence_id="point-source",
    )

    with pytest.raises(ValueError, match="not accepted"):
        transform_fact(source, _transform(status=GeometryDerivationStatus.PROPOSED))


def test_transform_fact_does_not_accept_unresolved_source_fact():
    transform = _transform()
    unresolved = SuppliedInterfaceFact(
        fact_id="point-fact",
        expected_shape=SuppliedInterfaceEvidenceShape.VECTOR3,
        expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.POINT_MM,
        evidence=(SuppliedInterfaceEvidence(
            evidence_id="point-source",
            shape=SuppliedInterfaceEvidenceShape.VECTOR3,
            value=None,
            canonical_unit="mm",
            availability=ComponentPropertyAvailability.MISSING,
            authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
            source_identity="vendor:interface:1",
            evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
        ),),
    )
    with pytest.raises(ValueError):
        transform_fact(unresolved, transform)


def test_effective_values_have_no_independent_cached_authority_fields():
    transform = _transform()
    assert transform.translation_mm == (0.0, 0.0, 0.0)
    assert transform.rotation_quaternion == (1.0, 0.0, 0.0, 0.0)
    assert math.isclose(transform.scale, SCALE_125)


def _interface_fact(fact_id, role, value, *, evidence_id=None, accepted=True,
                    origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
                    availability=ComponentPropertyAvailability.AVAILABLE):
    shape, unit = {
        SuppliedInterfaceTransformRole.POINT_MM: (SuppliedInterfaceEvidenceShape.VECTOR3, "mm"),
        SuppliedInterfaceTransformRole.LENGTH_MM: (SuppliedInterfaceEvidenceShape.SCALAR, "mm"),
        SuppliedInterfaceTransformRole.DIRECTION_UNIT: (SuppliedInterfaceEvidenceShape.VECTOR3, "1"),
        SuppliedInterfaceTransformRole.ORIENTATION: (SuppliedInterfaceEvidenceShape.QUATERNION, "1"),
        SuppliedInterfaceTransformRole.TEXT: (SuppliedInterfaceEvidenceShape.TEXT, None),
    }[role]
    evidence = SuppliedInterfaceEvidence(
        evidence_id=evidence_id or f"evidence:{fact_id}",
        shape=shape,
        value=value,
        canonical_unit=unit,
        availability=availability,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity="source:interface",
        evidence_origin=origin,
    )
    return SuppliedInterfaceFact(
        fact_id=fact_id,
        expected_shape=shape,
        expected_unit=unit,
        transform_role=role,
        evidence=(evidence,),
        accepted_evidence_id=evidence.evidence_id if accepted else None,
    )


def _materialization_transform():
    transform = _transform()
    payload = transform.model_dump(mode="json")
    payload["source_geometry_reference_hash"] = _reference_hash(transform.source_geometry)
    payload["derived_geometry_reference_hash"] = _reference_hash(transform.derived_geometry)
    payload["transform_hash"] = "pending"
    return GeometryDerivationTransform.model_validate(payload)


def _accepted_shaft_definition(*, scale_independent_fixtures=False):
    del scale_independent_fixtures
    geometry = GeometryArtifactIdentity(
        artifact_id="ART-SRC", artifact_hash=HASH_1, source_identity="s"
    )
    shaft = RotationalShaftInterface(
        interface_id="output-shaft",
        geometry_reference_hash=_reference_hash(geometry),
        geometry=geometry,
        axis_point=_interface_fact(
            "axis-point", SuppliedInterfaceTransformRole.POINT_MM, (1.0, 2.0, 3.0)
        ),
        axis_direction=_interface_fact(
            "axis-direction", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0)
        ),
        nominal_shaft_diameter=_interface_fact(
            "shaft-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 8.0
        ),
        usable_axial_engagement_length=_interface_fact(
            "engagement", SuppliedInterfaceTransformRole.LENGTH_MM, 20.0
        ),
    )
    return SuppliedComponentInterfaceDefinition(
        interface_id=shaft.interface_id,
        geometry_reference_hash=_reference_hash(geometry),
        geometry=geometry,
        shaft=shaft,
    )


def _inferred_only_shaft_definition():
    source = _accepted_shaft_definition()
    payload = source.model_dump(mode="json")
    diameter = payload["shaft"]["nominal_shaft_diameter"]
    evidence = diameter["evidence"][0]
    evidence["evidence_origin"] = SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED
    evidence["geometry_reference_hash"] = source.geometry_reference_hash
    evidence["evidence_hash"] = "pending"
    diameter["accepted_evidence_id"] = None
    diameter["fact_hash"] = "pending"
    payload["shaft"]["nominal_shaft_diameter"] = diameter
    payload["shaft"]["interface_hash"] = "pending"
    payload["interface_hash"] = "pending"
    return SuppliedComponentInterfaceDefinition.model_validate(payload)


def _revalidated_provenance(provenance, **updates):
    return provenance.model_copy(update=updates)


def test_materialization_replay_recomputes_derived_interface():
    source = _accepted_shaft_definition(scale_independent_fixtures=True)
    transform = _materialization_transform()
    semantics = derive_interface_semantics(source, transform)
    provenance = build_derivation_provenance(source, None, transform)
    materialized = construct_materialized_result(semantics, None, provenance)
    expected = MaterializedInterfaceVerifier.replay(provenance, transform)
    assert expected == materialized
    MaterializedInterfaceVerifier.verify(provenance, transform, materialized.interface)


def test_construct_rejects_provenance_source_snapshot_identity_mismatch():
    source = _accepted_shaft_definition(scale_independent_fixtures=True)
    transform = _materialization_transform()
    semantics = derive_interface_semantics(source, transform)
    provenance = build_derivation_provenance(source, None, transform)

    snapshot_payload = source.model_dump(mode="json")
    snapshot_payload["interface_id"] = "different-source-interface"
    snapshot_payload["shaft"]["interface_id"] = "different-source-interface"
    snapshot_payload["shaft"]["interface_hash"] = "pending"
    snapshot_payload["interface_hash"] = "pending"
    mismatched_snapshot = SuppliedComponentInterfaceDefinition.model_validate(snapshot_payload)
    mismatched_provenance = type(provenance).model_validate(
        provenance.model_dump(mode="json")
        | {
            "source_interface_snapshot": mismatched_snapshot.model_dump(mode="json"),
            "source_interface_hash": mismatched_snapshot.interface_hash,
            "provenance_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="interface identity"):
        construct_materialized_result(semantics, None, mismatched_provenance)


def test_construct_rejects_provenance_source_geometry_binding_mismatches():
    source = _accepted_shaft_definition(scale_independent_fixtures=True)
    transform = _materialization_transform()
    semantics = derive_interface_semantics(source, transform)
    provenance = build_derivation_provenance(source, None, transform)
    alternate_geometry = GeometryArtifactIdentity(
        artifact_id="ART-OTHER", artifact_hash=HASH_3, source_identity="other"
    )

    with pytest.raises(ValueError, match="source geometry"):
        construct_materialized_result(
            semantics,
            None,
            provenance.model_copy(update={
                "source_geometry": alternate_geometry,
                "source_geometry_reference_hash": _reference_hash(alternate_geometry),
            }),
        )


@pytest.mark.parametrize("mutate", [
    lambda p: _revalidated_provenance(p, source_interface_hash="sha256:" + "9" * 64),
    lambda p: _revalidated_provenance(p, transform_hash="sha256:" + "9" * 64),
    lambda p: _revalidated_provenance(p, materialization_algorithm="supplied-interface-materialization@2"),
])
def test_tampered_provenance_fails_integrity(mutate):
    materialized = materialize_interface(
        _accepted_shaft_definition(scale_independent_fixtures=True),
        None,
        _materialization_transform(),
    )
    with pytest.raises(MaterializationIntegrityError):
        MaterializedInterfaceVerifier.verify(
            mutate(materialized.interface.derivation),
            _materialization_transform(),
            materialized.interface,
        )


def test_changed_source_value_breaks_replay():
    materialized = materialize_interface(
        _accepted_shaft_definition(scale_independent_fixtures=True),
        None,
        _materialization_transform(),
    )
    payload = materialized.interface.model_dump(mode="json")
    evidence = payload["shaft"]["nominal_shaft_diameter"]["evidence"][0]
    evidence["value"] = 9.0
    evidence["evidence_hash"] = "pending"
    payload["shaft"]["nominal_shaft_diameter"]["fact_hash"] = "pending"
    payload["shaft"]["interface_hash"] = "pending"
    payload["interface_hash"] = "pending"
    forged = SuppliedComponentInterfaceDefinition.model_validate(payload)
    with pytest.raises(MaterializationIntegrityError):
        MaterializedInterfaceVerifier.verify(
            materialized.interface.derivation,
            _materialization_transform(),
            forged,
        )


def test_materialization_rejects_structurally_valid_unresolved_source_interface():
    with pytest.raises(ValueError, match="unresolved authority"):
        materialize_interface(_inferred_only_shaft_definition(), None, _materialization_transform())


def test_materialization_rejects_proposed_or_inferred_only_transform():
    source = _accepted_shaft_definition(scale_independent_fixtures=True)
    proposed = _materialization_transform().model_validate(
        _materialization_transform().model_dump(mode="json")
        | {"status": GeometryDerivationStatus.PROPOSED, "transform_hash": "pending"}
    )
    with pytest.raises(ValueError, match="unresolved authority"):
        materialize_interface(source, None, proposed)


def test_materialized_external_basis_is_bound_to_source_fact_and_hash():
    materialized = materialize_interface(
        _accepted_shaft_definition(scale_independent_fixtures=True), None, _materialization_transform()
    )
    provenance = materialized.interface.derivation
    assert provenance.fact_derivation_bindings
    assert all(binding.source_evidence_hash.startswith("sha256:") for binding in provenance.fact_derivation_bindings)

    binding = provenance.fact_derivation_bindings[0]
    changed_binding = InterfaceFactDerivationBinding.model_validate(
        binding.model_dump(mode="json") | {"source_evidence_hash": "sha256:" + "8" * 64}
    )
    tampered = _revalidated_provenance(
        provenance,
        fact_derivation_bindings=(
            changed_binding,
            *provenance.fact_derivation_bindings[1:],
        ),
    )
    with pytest.raises(MaterializationIntegrityError):
        MaterializedInterfaceVerifier.verify(tampered, _materialization_transform(), materialized.interface)


def test_direct_interface_cannot_use_external_derivation_basis():
    source = _accepted_shaft_definition()
    payload = source.model_dump(mode="json")
    evidence = payload["shaft"]["nominal_shaft_diameter"]["evidence"][0]
    evidence["evidence_origin"] = SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION
    evidence["basis_evidence_ids"] = ["external-source-evidence"]
    evidence["evidence_hash"] = "pending"
    payload["shaft"]["nominal_shaft_diameter"]["fact_hash"] = "pending"
    payload["shaft"]["interface_hash"] = "pending"
    payload["interface_hash"] = "pending"
    with pytest.raises(ValueError, match="derived_materialization"):
        SuppliedComponentInterfaceDefinition.model_validate(payload)


def _frame_for_source(geometry):
    return SuppliedComponentReferenceFrame(
        frame_id="output-frame",
        geometry_reference_hash=_reference_hash(geometry),
        origin=_interface_fact(
            "frame-origin", SuppliedInterfaceTransformRole.POINT_MM, (2.0, 3.0, 4.0)
        ),
        orientation=_interface_fact(
            "frame-orientation", SuppliedInterfaceTransformRole.ORIENTATION,
            (1.0, 0.0, 0.0, 0.0),
        ),
    )


def _source_shaft_with_frame():
    source = _accepted_shaft_definition()
    payload = source.model_dump(mode="json")
    shaft = RotationalShaftInterface.model_validate(
        payload["shaft"] | {"reference_frame_id": "output-frame", "interface_hash": "pending"}
    )
    payload["shaft"] = shaft.model_dump(mode="json")
    payload["interface_hash"] = "pending"
    return SuppliedComponentInterfaceDefinition.model_validate(payload)


def test_frame_materialization_returns_active_derived_frame_and_requires_it_on_verify():
    source = _source_shaft_with_frame()
    frame = _frame_for_source(source.geometry)
    transform = _materialization_transform()
    result = materialize_interface(source, frame, transform)

    assert result.reference_frame is not None
    assert result.reference_frame.frame_id == "output-frame"
    assert result.reference_frame.geometry_reference_hash == transform.derived_geometry_reference_hash
    assert result.reference_frame.origin.evidence[0].value == pytest.approx((2.5, 3.75, 5.0))
    assert result.interface.shaft.reference_frame_id == "output-frame"
    MaterializedInterfaceVerifier.verify(
        result.interface.derivation, transform, result.interface, result.reference_frame
    )
    with pytest.raises(MaterializationIntegrityError):
        MaterializedInterfaceVerifier.verify(
            result.interface.derivation, transform, result.interface
        )


def test_construct_rejects_active_frame_geometry_binding_mismatch():
    source = _source_shaft_with_frame()
    frame = _frame_for_source(source.geometry)
    transform = _materialization_transform()
    semantics = derive_interface_semantics(source, transform)
    provenance = build_derivation_provenance(source, frame, transform)
    derived_frame = derive_reference_frame_semantics(frame, transform)
    with pytest.raises(ValidationError, match="geometry reference"):
        type(derived_frame).model_validate(
            derived_frame.model_dump(mode="json")
            | {
                "geometry_reference_hash": transform.source_geometry_reference_hash,
                "frame_hash": "pending",
            }
        )


def test_construct_materialized_result_rejects_derived_interface_frame_id_mismatch():
    source = _source_shaft_with_frame()
    frame = _frame_for_source(source.geometry)
    transform = _materialization_transform()
    semantics = derive_interface_semantics(source, transform)
    wrong_shaft = RotationalShaftInterface.model_validate(
        semantics.shaft.model_dump(mode="json")
        | {"reference_frame_id": "different-frame", "interface_hash": "pending"}
    )
    wrong_semantics = semantics.model_validate(
        semantics.model_dump(mode="json")
        | {"shaft": wrong_shaft.model_dump(mode="json")}
    )
    provenance = build_derivation_provenance(source, frame, transform)
    derived_frame = derive_reference_frame_semantics(frame, transform)

    with pytest.raises(ValueError, match="frame ID"):
        construct_materialized_result(wrong_semantics, derived_frame, provenance)


def test_construct_materialized_result_rejects_derived_interface_frame_without_active_frame():
    source = _accepted_shaft_definition()
    transform = _materialization_transform()
    semantics = derive_interface_semantics(source, transform)
    wrong_shaft = RotationalShaftInterface.model_validate(
        semantics.shaft.model_dump(mode="json")
        | {"reference_frame_id": "unexpected-frame", "interface_hash": "pending"}
    )
    wrong_semantics = semantics.model_validate(
        semantics.model_dump(mode="json")
        | {"shaft": wrong_shaft.model_dump(mode="json")}
    )
    provenance = build_derivation_provenance(source, None, transform)

    with pytest.raises(ValueError, match="frame"):
        construct_materialized_result(wrong_semantics, None, provenance)


def test_materialization_accepts_punctuation_in_mounting_hole_id_and_preserves_path():
    geometry = GeometryArtifactIdentity(
        artifact_id="ART-SRC", artifact_hash=HASH_1, source_identity="s"
    )
    mounting_face = MountingFaceInterface(
        interface_id="mount-face",
        geometry_reference_hash=_reference_hash(geometry),
        geometry=geometry,
        face_reference_id="Face3",
        reference_frame_id="output-frame",
        plane_point=_interface_fact(
            "plane-point", SuppliedInterfaceTransformRole.POINT_MM, (0.0, 0.0, 0.0)
        ),
        outward_normal=_interface_fact(
            "plane-normal", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0)
        ),
        holes=(MountingHole(
            hole_id="H.1",
            center=_interface_fact(
                "hole-center", SuppliedInterfaceTransformRole.POINT_MM, (3.0, 5.0, 0.0)
            ),
            axis=_interface_fact(
                "hole-axis", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0)
            ),
            nominal_diameter=_interface_fact(
                "hole-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 4.0
            ),
        ),),
    )
    source = SuppliedComponentInterfaceDefinition(
        interface_id=mounting_face.interface_id,
        geometry_reference_hash=_reference_hash(geometry),
        geometry=geometry,
        mounting_face=mounting_face,
    )
    transform = _materialization_transform()
    frame = _frame_for_source(geometry)
    result = materialize_interface(source, frame, transform)

    paths = {binding.fact_path for binding in result.interface.derivation.fact_derivation_bindings}
    assert "mounting_face.holes[H.1].center" in paths
    assert "mounting_face.holes[H.1].axis" in paths
    assert "mounting_face.holes[H.1].nominal_diameter" in paths
