import pytest
from pydantic import ValidationError

from mechcad_harness.candidates.models import (
    ComponentSpecificationSnapshot,
    GeometrySourceReference,
    MechanicalConnection,
    MechanicalConnectionKind,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
)
from mechcad_harness.models.component_property import ComponentPropertyAvailability, ComponentPropertyAuthority
from mechcad_harness.models import (
    CanonicalComponentSpecification,
    CanonicalGeometrySourceReference,
    CanonicalMechanicalConnection,
    CanonicalMechanicalConnectionKind,
    CanonicalPhysicalComponent,
    CanonicalPhysicalComponentRole,
)
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.quaternion import normalize_direction
from mechcad_harness.models.supplied_component_interface import (
    MountingFaceInterface,
    MountingHole,
    RotationalShaftInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedPilotBossReference,
    SuppliedShaftDFlatProfile,
    SuppliedInterfaceEvidence,
    SuppliedInterfaceEvidenceOrigin,
    SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceFact,
    SuppliedInterfaceTransformRole,
    SuppliedComponentReferenceFrame,
    GeometryDerivationTransform,
    materialize_interface,
    require_authoritative_fact,
    require_authoritatively_consumable_interface,
)
from test_m13_geometry_materialization import _materialization_transform


def _evidence(**overrides):
    base = dict(
        evidence_id="E1", shape=SuppliedInterfaceEvidenceShape.SCALAR, value=8.0,
        canonical_unit="mm", availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity="datasheet:5840", evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    )
    return SuppliedInterfaceEvidence.model_validate(base | overrides)


def test_scalar_evidence_hash_deterministic_and_changes_with_authority():
    first = _evidence()
    again = SuppliedInterfaceEvidence.model_validate(first.model_dump(mode="json"))
    assert first.evidence_hash == again.evidence_hash
    changed = SuppliedInterfaceEvidence.model_validate(
        first.model_dump(mode="json")
        | {"authority": ComponentPropertyAuthority.MEASURED_LOCAL, "evidence_hash": "pending"}
    )
    assert changed.evidence_hash != first.evidence_hash


def test_numeric_missing_retains_unit_and_none_value():
    ev = _evidence(value=None, availability=ComponentPropertyAvailability.MISSING)
    assert ev.value is None and ev.canonical_unit == "mm"


@pytest.mark.parametrize(
    ("shape", "available_value"),
    [
        (SuppliedInterfaceEvidenceShape.SCALAR, 8.0),
        (SuppliedInterfaceEvidenceShape.VECTOR3, (1.0, 2.0, 3.0)),
        (SuppliedInterfaceEvidenceShape.QUATERNION, (1.0, 0.0, 0.0, 0.0)),
    ],
)
@pytest.mark.parametrize("availability", list(ComponentPropertyAvailability))
def test_numeric_evidence_requires_a_unit_even_when_unavailable(
    shape, available_value, availability
):
    value = available_value if availability is ComponentPropertyAvailability.AVAILABLE else None
    with pytest.raises(ValidationError, match="unit"):
        _evidence(
            shape=shape,
            value=value,
            canonical_unit=None,
            availability=availability,
        )


def test_text_requires_unit_none_and_rejects_blank():
    text = _evidence(shape=SuppliedInterfaceEvidenceShape.TEXT, value="M4", canonical_unit=None)
    assert text.canonical_unit is None
    with pytest.raises(ValidationError):
        _evidence(shape=SuppliedInterfaceEvidenceShape.TEXT, value="M4", canonical_unit="mm")
    with pytest.raises(ValidationError):
        _evidence(shape=SuppliedInterfaceEvidenceShape.TEXT, value="   ", canonical_unit=None)


def test_unavailable_evidence_rejects_sentinel_values():
    with pytest.raises(ValidationError):
        _evidence(value=0.0, availability=ComponentPropertyAvailability.MISSING)
    with pytest.raises(ValidationError):
        _evidence(value=(0.0, 0.0, 0.0),
                  shape=SuppliedInterfaceEvidenceShape.VECTOR3,
                  availability=ComponentPropertyAvailability.NOT_APPLICABLE)


def test_fact_orders_evidence_and_rejects_duplicate_ids():
    a = _evidence(evidence_id="E2", value=8.01,
                  authority=ComponentPropertyAuthority.MEASURED_LOCAL,
                  evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
                  geometry_reference_hash="sha256:" + "a" * 64)
    b = _evidence(evidence_id="E1")
    fact = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(a, b), accepted_evidence_id="E1",
    )
    assert tuple(e.evidence_id for e in fact.evidence) == ("E1", "E2")
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR, expected_unit="mm",
            transform_role=SuppliedInterfaceTransformRole.LENGTH_MM, evidence=(a, a),
        )


def test_inferred_evidence_cannot_be_accepted():
    inferred = _evidence(value=8.01, authority=ComponentPropertyAuthority.MEASURED_LOCAL,
                         evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
                         geometry_reference_hash="sha256:" + "a" * 64)
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR, expected_unit="mm",
            transform_role=SuppliedInterfaceTransformRole.LENGTH_MM, evidence=(inferred,),
            accepted_evidence_id=inferred.evidence_id,
        )


def test_inferred_only_fact_is_a_valid_unresolved_snapshot():
    inferred = _evidence(
        value=8.01, authority=ComponentPropertyAuthority.MEASURED_LOCAL,
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        geometry_reference_hash="sha256:" + "a" * 64,
    )
    fact = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(inferred,),
    )
    assert fact.accepted_evidence_id is None


def test_normal_confirmation_basis_is_fact_local_and_derived_basis_is_deferred():
    base = _evidence(evidence_id="E1")
    confirmation = _evidence(
        evidence_id="E2", value=8.0,
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        basis_evidence_ids=("E1",),
    )
    fact = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(base, confirmation), accepted_evidence_id="E2",
    )
    assert fact.evidence[1].basis_evidence_ids == ("E1",)
    derived = _evidence(
        evidence_id="D1", value=10.0,
        evidence_origin=SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION,
        basis_evidence_ids=("SOURCE-EVIDENCE",),
    )
    derived_fact = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(derived,), accepted_evidence_id="D1",
    )
    assert derived_fact.accepted_evidence_id == "D1"


def test_human_confirmation_requires_explicit_basis_evidence():
    with pytest.raises(ValidationError, match="basis"):
        _evidence(
            evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        )


def test_human_confirmation_preserves_geometry_inferred_basis_binding():
    geometry_hash = "sha256:" + "a" * 64
    inferred = _evidence(
        evidence_id="E-inferred",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        geometry_reference_hash=geometry_hash,
    )
    confirmation = _evidence(
        evidence_id="E-confirmed",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        basis_evidence_ids=(inferred.evidence_id,),
        geometry_reference_hash=geometry_hash,
    )

    fact = SuppliedInterfaceFact(
        fact_id="F1",
        expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(inferred, confirmation),
        accepted_evidence_id=confirmation.evidence_id,
    )

    assert fact.accepted_evidence_id == confirmation.evidence_id


def test_multi_hop_human_confirmation_preserves_inferred_geometry_binding():
    geometry_hash = "sha256:" + "a" * 64
    inferred = _evidence(
        evidence_id="E-inferred",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        geometry_reference_hash=geometry_hash,
    )
    first_confirmation = _evidence(
        evidence_id="E-confirmed-1",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        basis_evidence_ids=(inferred.evidence_id,),
        geometry_reference_hash=geometry_hash,
    )
    second_confirmation = _evidence(
        evidence_id="E-confirmed-2",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        basis_evidence_ids=(first_confirmation.evidence_id,),
        geometry_reference_hash=geometry_hash,
    )

    fact = SuppliedInterfaceFact(
        fact_id="F1",
        expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(inferred, second_confirmation, first_confirmation),
        accepted_evidence_id=second_confirmation.evidence_id,
    )

    assert fact.accepted_evidence_id == second_confirmation.evidence_id


@pytest.mark.parametrize("confirmation_geometry_hash", [None, "sha256:" + "b" * 64])
def test_human_confirmation_rejects_missing_or_mismatched_geometry_basis_binding(
    confirmation_geometry_hash,
):
    inferred = _evidence(
        evidence_id="E-inferred",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        geometry_reference_hash="sha256:" + "a" * 64,
    )
    confirmation = _evidence(
        evidence_id="E-confirmed",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        basis_evidence_ids=(inferred.evidence_id,),
        geometry_reference_hash=confirmation_geometry_hash,
    )

    with pytest.raises(ValidationError, match="geometry reference"):
        SuppliedInterfaceFact(
            fact_id="F1",
            expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
            expected_unit="mm",
            transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
            evidence=(inferred, confirmation),
            accepted_evidence_id=confirmation.evidence_id,
        )


@pytest.mark.parametrize("confirmation_geometry_hash", [None, "sha256:" + "b" * 64])
def test_nested_human_confirmation_rejects_missing_or_mismatched_geometry_basis_binding(
    confirmation_geometry_hash,
):
    geometry_hash = "sha256:" + "a" * 64
    inferred = _evidence(
        evidence_id="E-inferred",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        geometry_reference_hash=geometry_hash,
    )
    first_confirmation = _evidence(
        evidence_id="E-confirmed-1",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        basis_evidence_ids=(inferred.evidence_id,),
        geometry_reference_hash=geometry_hash,
    )
    nested_confirmation = _evidence(
        evidence_id="E-confirmed-2",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        basis_evidence_ids=(first_confirmation.evidence_id,),
        geometry_reference_hash=confirmation_geometry_hash,
    )

    with pytest.raises(ValidationError, match="geometry reference"):
        SuppliedInterfaceFact(
            fact_id="F1",
            expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
            expected_unit="mm",
            transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
            evidence=(inferred, first_confirmation, nested_confirmation),
            accepted_evidence_id=nested_confirmation.evidence_id,
        )


def test_geometry_inferred_evidence_requires_an_exact_geometry_reference_hash():
    with pytest.raises(ValidationError, match="geometry reference"):
        _evidence(
            evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
            geometry_reference_hash=None,
        )


def test_wrong_artifact_inference_cannot_be_used_as_a_human_confirmation_basis():
    wrong_hash = "sha256:" + "9" * 64
    inferred = _evidence(
        evidence_id="E-inferred-wrong",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        geometry_reference_hash=wrong_hash,
    )
    confirmation = _evidence(
        evidence_id="E-confirmed",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        geometry_reference_hash=wrong_hash,
        basis_evidence_ids=(inferred.evidence_id,),
    )
    fact = SuppliedInterfaceFact(
        fact_id="shaft-diameter",
        expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(inferred, confirmation),
        accepted_evidence_id=confirmation.evidence_id,
    )
    with pytest.raises(ValidationError, match="geometry reference"):
        _shaft(nominal_shaft_diameter=fact)


def test_interface_and_frame_inferred_facts_bind_to_their_enclosing_geometry():
    wrong_hash = "sha256:" + "9" * 64
    inferred = _evidence(
        evidence_id="E-inferred-wrong",
        shape=SuppliedInterfaceEvidenceShape.VECTOR3,
        value=(1.0, 2.0, 3.0),
        canonical_unit="mm",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        geometry_reference_hash=wrong_hash,
    )
    point = SuppliedInterfaceFact(
        fact_id="point",
        expected_shape=SuppliedInterfaceEvidenceShape.VECTOR3,
        expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.POINT_MM,
        evidence=(inferred,),
    )
    shaft_payload = _shaft().model_dump(mode="json")
    shaft_payload["axis_point"] = point.model_dump(mode="json")
    shaft_payload["interface_hash"] = "pending"
    with pytest.raises(ValidationError, match="geometry reference"):
        RotationalShaftInterface.model_validate(shaft_payload)

    with pytest.raises(ValidationError, match="geometry reference"):
        SuppliedComponentReferenceFrame(
            frame_id="frame",
            geometry_reference_hash=_reference_hash(INTERFACE_GEOMETRY),
            origin=point,
            orientation=_spec_frame(
                GeometrySourceReference(
                    artifact_id="ART-INTERFACE",
                    artifact_hash=INTERFACE_GEOMETRY.artifact_hash,
                    source_identity=INTERFACE_GEOMETRY.source_identity,
                    coordinate_system_id="step-model-coordinates@1",
                )
            ).orientation,
        )


def test_dangling_normal_confirmation_basis_fails():
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
            expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
            evidence=(
                _evidence(
                    evidence_id="E2", basis_evidence_ids=("MISSING",),
                    evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
                ),
            ),
        )


def test_frame_normalizes_quaternion_sign_variants():
    origin_fact = SuppliedInterfaceFact(
        fact_id="FO", expected_shape=SuppliedInterfaceEvidenceShape.VECTOR3, expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.POINT_MM,
            evidence=(SuppliedInterfaceEvidence.model_validate(dict(
                evidence_id="EO", shape=SuppliedInterfaceEvidenceShape.VECTOR3, value=(0.1, -5.1, 30.0),
                canonical_unit="mm", availability=ComponentPropertyAvailability.AVAILABLE,
                 authority=ComponentPropertyAuthority.USER_DECLARED, source_identity="handoff",
                 evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT)),),
    )
    def _orientation(value):
        return SuppliedInterfaceFact(
            fact_id="FQ", expected_shape=SuppliedInterfaceEvidenceShape.QUATERNION, expected_unit="1",
            transform_role=SuppliedInterfaceTransformRole.ORIENTATION,
            evidence=(SuppliedInterfaceEvidence.model_validate(dict(
                evidence_id="EQ", shape=SuppliedInterfaceEvidenceShape.QUATERNION, value=value,
                canonical_unit="1", availability=ComponentPropertyAvailability.AVAILABLE,
                 authority=ComponentPropertyAuthority.USER_DECLARED, source_identity="handoff",
                 evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT)),),)

    positive = SuppliedComponentReferenceFrame(
        frame_id="output-frame", geometry_reference_hash="sha256:" + "b" * 64,
        origin=origin_fact, orientation=_orientation((0.5, 0.5, 0.5, 0.5)))
    negative = SuppliedComponentReferenceFrame(
        frame_id="output-frame", geometry_reference_hash="sha256:" + "b" * 64,
        origin=origin_fact, orientation=_orientation((-0.5, -0.5, -0.5, -0.5)))
    assert positive.frame_hash == negative.frame_hash


def test_numeric_fact_requires_exact_transform_role_shape_and_unit():
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
            expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.POINT_MM,
            evidence=(_evidence(),),
        )
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.VECTOR3,
            expected_unit="1", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
            evidence=(_evidence(shape=SuppliedInterfaceEvidenceShape.VECTOR3,
                                value=(1.0, 2.0, 3.0), canonical_unit="1"),),
        )


def test_unavailable_numeric_evidence_still_requires_fact_unit():
    unavailable = _evidence(value=None, availability=ComponentPropertyAvailability.MISSING)
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
            expected_unit="1", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
            evidence=(unavailable,),
        )


def test_available_numeric_values_are_finite_and_not_boolean():
    with pytest.raises(ValidationError):
        _evidence(value=True)
    with pytest.raises(ValidationError):
        _evidence(value=float("inf"))
    with pytest.raises(ValidationError):
        _evidence(shape=SuppliedInterfaceEvidenceShape.QUATERNION,
                  value=(0.0, 0.0, 0.0, 0.0), canonical_unit="1")


def test_confirmation_basis_graph_rejects_cycles():
    first = _evidence(evidence_id="E1", basis_evidence_ids=("E2",))
    second = _evidence(
        evidence_id="E2",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        basis_evidence_ids=("E1",),
    )
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
            expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
            evidence=(first, second),
        )


def test_authoritative_fact_requires_explicit_selection_and_never_allows_derived_flag():
    inferred = _evidence(
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        geometry_reference_hash="sha256:" + "a" * 64,
    )
    unresolved = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(inferred,),
    )
    with pytest.raises(ValueError):
        require_authoritative_fact(unresolved, fact_name="shaft diameter")

    derived = _evidence(
        evidence_origin=SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION,
        basis_evidence_ids=("external-source-evidence",),
    )
    fact = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(derived,), accepted_evidence_id="E1",
    )
    with pytest.raises(ValueError):
        require_authoritative_fact(fact, fact_name="shaft diameter")
    with pytest.raises(TypeError):
        require_authoritative_fact(
            fact, fact_name="shaft diameter", allow_derived_materialization=True
        )


def test_frame_rejects_non_frame_facts_and_tampered_hash():
    scalar = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(_evidence(),),
    )
    with pytest.raises(ValidationError):
        SuppliedComponentReferenceFrame(
            frame_id="frame", geometry_reference_hash="sha256:" + "b" * 64,
            origin=scalar, orientation=scalar,
        )

    origin = SuppliedInterfaceFact(
        fact_id="FO", expected_shape=SuppliedInterfaceEvidenceShape.VECTOR3,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.POINT_MM,
        evidence=(_evidence(shape=SuppliedInterfaceEvidenceShape.VECTOR3,
                             value=(0.0, 0.0, 0.0)),),
    )
    orientation = SuppliedInterfaceFact(
        fact_id="FQ", expected_shape=SuppliedInterfaceEvidenceShape.QUATERNION,
        expected_unit="1", transform_role=SuppliedInterfaceTransformRole.ORIENTATION,
        evidence=(_evidence(shape=SuppliedInterfaceEvidenceShape.QUATERNION,
                             value=(1.0, 0.0, 0.0, 0.0), canonical_unit="1"),),
    )
    frame = SuppliedComponentReferenceFrame(
        frame_id="frame", geometry_reference_hash="sha256:" + "b" * 64,
        origin=origin, orientation=orientation,
    )
    with pytest.raises(ValidationError):
        SuppliedComponentReferenceFrame.model_validate(
            frame.model_dump(mode="json")
            | {"frame_hash": "sha256:" + "0" * 64}
        )


INTERFACE_GEOMETRY = GeometryArtifactIdentity(
    artifact_id="ART-INTERFACE",
    artifact_hash="sha256:" + "c" * 64,
    source_identity="vendor:interface",
)


def _reference_hash(geometry):
    return GeometrySourceReference(
        artifact_id=geometry.artifact_id,
        artifact_hash=geometry.artifact_hash,
        source_identity=geometry.source_identity,
        coordinate_system_id=geometry.coordinate_system_id,
    ).reference_hash


def _interface_fact(
    fact_id, role, value, *, evidence_id=None, origin=None, accepted=True,
    availability=ComponentPropertyAvailability.AVAILABLE,
):
    shape_and_unit = {
        SuppliedInterfaceTransformRole.POINT_MM: (
            SuppliedInterfaceEvidenceShape.VECTOR3, "mm"
        ),
        SuppliedInterfaceTransformRole.LENGTH_MM: (
            SuppliedInterfaceEvidenceShape.SCALAR, "mm"
        ),
        SuppliedInterfaceTransformRole.DIRECTION_UNIT: (
            SuppliedInterfaceEvidenceShape.VECTOR3, "1"
        ),
        SuppliedInterfaceTransformRole.TEXT: (
            SuppliedInterfaceEvidenceShape.TEXT, None
        ),
    }[role]
    record = SuppliedInterfaceEvidence(
        evidence_id=evidence_id or f"E-{fact_id}",
        shape=shape_and_unit[0], value=value,
        canonical_unit=shape_and_unit[1], availability=availability,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity="datasheet:interface",
        evidence_origin=origin or SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
        geometry_reference_hash=(
            _reference_hash(INTERFACE_GEOMETRY)
            if origin is SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED
            else None
        ),
    )
    return SuppliedInterfaceFact(
        fact_id=fact_id, expected_shape=shape_and_unit[0],
        expected_unit=shape_and_unit[1], transform_role=role,
        evidence=(record,),
        accepted_evidence_id=record.evidence_id if accepted else None,
    )


def _shaft(*, direction=(0.0, 0.0, 1.0), profile=None, d_flat=None, **overrides):
    return RotationalShaftInterface(
        interface_id="output-shaft", geometry_reference_hash=_reference_hash(INTERFACE_GEOMETRY),
        geometry=INTERFACE_GEOMETRY,
        axis_point=_interface_fact("axis-point", SuppliedInterfaceTransformRole.POINT_MM, (1.0, 2.0, 3.0)),
        axis_direction=_interface_fact("axis-direction", SuppliedInterfaceTransformRole.DIRECTION_UNIT, direction),
        nominal_shaft_diameter=overrides.get(
            "nominal_shaft_diameter",
            _interface_fact("shaft-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 8.0),
        ),
        usable_axial_engagement_length=overrides.get(
            "usable_axial_engagement_length",
            _interface_fact("engagement", SuppliedInterfaceTransformRole.LENGTH_MM, 20.0),
        ),
        shaft_profile=profile,
        d_flat_profile=d_flat,
    )


def _direct_definition(shaft=None, mounting_face=None, **overrides):
    return SuppliedComponentInterfaceDefinition(
        interface_id=overrides.get("interface_id", "output-shaft"),
        geometry_reference_hash=overrides.get(
            "geometry_reference_hash", _reference_hash(INTERFACE_GEOMETRY)
        ),
        geometry=overrides.get("geometry", INTERFACE_GEOMETRY),
        shaft=shaft,
        mounting_face=mounting_face,
    )


def test_valid_round_and_d_flat_shaft_interfaces_are_direct_snapshots():
    d_flat = SuppliedShaftDFlatProfile(
        flat_normal_direction=_interface_fact(
            "flat-normal", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (1.0, 0.0, 0.0)
        ),
        flat_across_dimension=_interface_fact(
            "flat-across", SuppliedInterfaceTransformRole.LENGTH_MM, 7.0
        ),
        start_from_shoulder=_interface_fact(
            "flat-start", SuppliedInterfaceTransformRole.LENGTH_MM, 2.0
        ),
        effective_length=_interface_fact(
            "flat-length", SuppliedInterfaceTransformRole.LENGTH_MM, 15.0
        ),
    )
    round_definition = _direct_definition(_shaft(profile="round"))
    d_flat_definition = _direct_definition(_shaft(profile="d_flat", d_flat=d_flat))

    assert round_definition.kind == "direct"
    assert d_flat_definition.shaft.d_flat_profile == d_flat
    assert d_flat_definition.derivation is None


def test_reversing_axis_direction_changes_shaft_hash_and_direction_is_normalized():
    forward = _shaft(direction=(0.0, 0.0, 2.0))
    reverse = _shaft(direction=(0.0, 0.0, -2.0))

    assert forward.axis_direction.evidence[0].value == normalize_direction((0.0, 0.0, 2.0))
    assert forward.interface_hash != reverse.interface_hash


def test_available_nonpositive_dimensions_are_rejected_even_when_unselected():
    for field_name in ("nominal_shaft_diameter", "usable_axial_engagement_length"):
        bad = _interface_fact(
            field_name, SuppliedInterfaceTransformRole.LENGTH_MM, 0.0,
            accepted=False,
        )
        with pytest.raises(ValidationError):
            _direct_definition(_shaft(**{field_name: bad}))

    with pytest.raises(ValidationError):
        bad_flat = SuppliedShaftDFlatProfile(
            flat_normal_direction=_interface_fact(
                "flat-normal", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (1.0, 0.0, 0.0)
            ),
            flat_across_dimension=_interface_fact(
                "flat-across", SuppliedInterfaceTransformRole.LENGTH_MM, -1.0, accepted=False
            ),
            start_from_shoulder=_interface_fact(
                "flat-start", SuppliedInterfaceTransformRole.LENGTH_MM, 2.0
            ),
            effective_length=_interface_fact(
                "flat-length", SuppliedInterfaceTransformRole.LENGTH_MM, 15.0
            ),
        )
        _direct_definition(_shaft(profile="d_flat", d_flat=bad_flat))


def test_missing_diameter_and_unselected_axis_are_valid_unresolved_snapshots():
    missing_diameter = _interface_fact(
        "shaft-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, None,
        accepted=False, availability=ComponentPropertyAvailability.MISSING,
    )
    unselected_axis = _interface_fact(
        "axis-direction", SuppliedInterfaceTransformRole.DIRECTION_UNIT, None,
        accepted=False, availability=ComponentPropertyAvailability.MISSING,
    )
    shaft = _shaft(nominal_shaft_diameter=missing_diameter)
    shaft = shaft.model_validate(
        shaft.model_dump(mode="json") | {"axis_direction": unselected_axis, "interface_hash": "pending"}
    )
    assert _direct_definition(shaft).interface_hash.startswith("sha256:")


def test_inferred_only_shaft_requires_authority_helper_but_human_confirmation_consumes():
    inferred = _interface_fact(
        "shaft-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 8.01,
        accepted=False, origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
    )
    unresolved = _direct_definition(_shaft(nominal_shaft_diameter=inferred))
    with pytest.raises(ValueError, match="shaft nominal diameter"):
        require_authoritatively_consumable_interface(unresolved)

    source = inferred.evidence[0]
    confirmation = SuppliedInterfaceEvidence(
        evidence_id="E-shaft-diameter-confirmed",
        shape=source.shape, value=8.0, canonical_unit="mm",
        availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.USER_DECLARED,
        source_identity="review:interface",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        geometry_reference_hash=source.geometry_reference_hash,
        basis_evidence_ids=(source.evidence_id,),
    )
    confirmed = SuppliedInterfaceFact(
        fact_id="shaft-diameter", expected_shape=source.shape, expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(source, confirmation), accepted_evidence_id=confirmation.evidence_id,
    )
    assert require_authoritatively_consumable_interface(
        _direct_definition(_shaft(nominal_shaft_diameter=confirmed))
    ).interface_id == "output-shaft"


def test_direct_definition_rejects_selected_derived_materialization_evidence():
    derived = _interface_fact(
        "shaft-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 8.0,
        origin=SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION,
    )
    with pytest.raises(ValidationError):
        _direct_definition(_shaft(nominal_shaft_diameter=derived))


def _mounting_hole(hole_id, x, y, *, thread=None):
    return MountingHole(
        hole_id=hole_id,
        center=_interface_fact(f"{hole_id}-center", SuppliedInterfaceTransformRole.POINT_MM, (x, y, 0.0)),
        axis=_interface_fact(f"{hole_id}-axis", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0)),
        nominal_diameter=_interface_fact(f"{hole_id}-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 4.0),
        thread_designation=(
            _interface_fact(f"{hole_id}-thread", SuppliedInterfaceTransformRole.TEXT, thread)
            if thread is not None else None
        ),
    )


def _mounting_face(holes):
    return MountingFaceInterface(
        interface_id="mount-face", geometry_reference_hash=_reference_hash(INTERFACE_GEOMETRY),
        geometry=INTERFACE_GEOMETRY, face_reference_id="Face3", reference_frame_id="mount-frame",
        plane_point=_interface_fact("plane-point", SuppliedInterfaceTransformRole.POINT_MM, (0.0, 0.0, 0.0)),
        outward_normal=_interface_fact("plane-normal", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0)),
        holes=tuple(holes),
        pilot_boss=SuppliedPilotBossReference(
            point=_interface_fact("pilot-point", SuppliedInterfaceTransformRole.POINT_MM, (0.0, 0.0, 0.0)),
            axis=_interface_fact("pilot-axis", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0)),
            diameter=_interface_fact("pilot-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 10.0),
        ),
    )


def test_mounting_face_supports_one_or_asymmetric_holes_with_order_independent_hash():
    one = _direct_definition(mounting_face=_mounting_face((_mounting_hole("H1", 3.0, 5.0, thread="M4"),)),
                             interface_id="mount-face")
    holes = tuple(_mounting_hole(f"H{i}", x, y) for i, (x, y) in enumerate(
        ((28.0, 0.0), (0.0, 41.0), (31.0, 7.0), (-3.0, 19.0)), start=1
    ))
    forward = _direct_definition(mounting_face=_mounting_face(holes), interface_id="mount-face")
    reverse = _direct_definition(mounting_face=_mounting_face(tuple(reversed(holes))), interface_id="mount-face")

    assert one.mounting_face.face_reference_id == "Face3"
    assert one.mounting_face.holes[0].thread_designation.expected_shape is SuppliedInterfaceEvidenceShape.TEXT
    assert forward.interface_hash == reverse.interface_hash


def test_duplicate_hole_id_and_blank_face_reference_are_rejected():
    duplicate = _mounting_hole("H1", 0.0, 0.0)
    with pytest.raises(ValidationError):
        _direct_definition(mounting_face=_mounting_face((duplicate, duplicate)), interface_id="mount-face")
    with pytest.raises(ValidationError):
        MountingFaceInterface(
            **_mounting_face((_mounting_hole("H1", 0.0, 0.0),)).model_dump(mode="python")
            | {"face_reference_id": "  "}
        )


def test_distinct_hole_ids_with_identical_complete_semantics_are_rejected():
    first = _mounting_hole("H1", 0.0, 0.0)
    identical = first.model_copy(update={"hole_id": "H2"})

    with pytest.raises(ValidationError, match="identical"):
        _mounting_face((first, identical))


def test_coincident_holes_with_distinct_complete_semantics_are_allowed():
    face = _mounting_face((
        _mounting_hole("H1", 0.0, 0.0),
        _mounting_hole("H2", 0.0, 0.0, thread="M4"),
    ))

    assert tuple(hole.hole_id for hole in face.holes) == ("H1", "H2")


def test_definition_rejects_variant_and_geometry_binding_mismatches():
    with pytest.raises(ValidationError):
        _direct_definition(_shaft(), mounting_face=_mounting_face(()))
    with pytest.raises(ValidationError):
        _direct_definition(_shaft(), geometry_reference_hash="sha256:" + "d" * 64)


def _spec_reference(*, coordinate_system_id="step-model-coordinates@1"):
    return GeometrySourceReference(
        artifact_id="ART-INTERFACE",
        artifact_hash=INTERFACE_GEOMETRY.artifact_hash,
        source_identity=INTERFACE_GEOMETRY.source_identity,
        coordinate_system_id=coordinate_system_id,
    )


def _spec_definition(reference, *, reference_frame_id=None):
    geometry = GeometryArtifactIdentity.from_candidate(reference)
    source = _direct_definition(_shaft())
    payload = source.model_dump(mode="json")
    payload["geometry_reference_hash"] = reference.reference_hash
    payload["geometry"] = geometry.model_dump(mode="json")
    payload["shaft"]["geometry_reference_hash"] = reference.reference_hash
    payload["shaft"]["geometry"] = geometry.model_dump(mode="json")
    payload["shaft"]["reference_frame_id"] = reference_frame_id
    payload["shaft"]["interface_hash"] = "pending"
    payload["interface_hash"] = "pending"
    return SuppliedComponentInterfaceDefinition.model_validate(payload)


def _spec_frame(reference, frame_id="output-frame"):
    geometry_hash = reference.reference_hash
    origin = _interface_fact(
        "frame-origin", SuppliedInterfaceTransformRole.POINT_MM, (0.0, 0.0, 0.0)
    )
    orientation = SuppliedInterfaceFact(
        fact_id="frame-orientation",
        expected_shape=SuppliedInterfaceEvidenceShape.QUATERNION,
        expected_unit="1",
        transform_role=SuppliedInterfaceTransformRole.ORIENTATION,
        evidence=(SuppliedInterfaceEvidence(
            evidence_id="frame-orientation-evidence",
            shape=SuppliedInterfaceEvidenceShape.QUATERNION,
            value=(1.0, 0.0, 0.0, 0.0),
            canonical_unit="1",
            availability=ComponentPropertyAvailability.AVAILABLE,
            authority=ComponentPropertyAuthority.USER_DECLARED,
            source_identity="source:frame",
            evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
        ),),
        accepted_evidence_id="frame-orientation-evidence",
    )
    return SuppliedComponentReferenceFrame(
        frame_id=frame_id,
        geometry_reference_hash=geometry_hash,
        origin=origin,
        orientation=orientation,
    )


def _specification(reference, definition, **overrides):
    values = dict(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="source:motor",
        geometry_source=reference,
        interfaces=(definition.interface_id,),
        supplied_interface_definitions=(definition,),
    )
    values.update(overrides)
    return ComponentSpecificationSnapshot(**values)


def test_specification_canonicalizes_interfaces_and_frames_before_hashing():
    reference = _spec_reference()
    definition = _spec_definition(reference)
    other_payload = definition.model_dump(mode="json")
    other_payload["interface_id"] = "input-shaft"
    other_payload["shaft"]["interface_id"] = "input-shaft"
    other_payload["shaft"]["interface_hash"] = "pending"
    other_payload["interface_hash"] = "pending"
    other = SuppliedComponentInterfaceDefinition.model_validate(other_payload)
    output_frame = _spec_frame(reference, "output-frame")
    input_frame_payload = _spec_frame(reference, "input-frame").model_dump(mode="json")
    input_frame_payload["origin"] = _interface_fact(
        "input-frame-origin", SuppliedInterfaceTransformRole.POINT_MM, (1.0, 0.0, 0.0)
    ).model_dump(mode="json")
    input_frame_payload["frame_hash"] = "pending"
    input_frame = SuppliedComponentReferenceFrame.model_validate(input_frame_payload)
    forward = _specification(
        reference,
        definition,
        interfaces=("input-shaft", "output-shaft"),
        supplied_interface_definitions=(definition, other),
        supplied_reference_frames=(output_frame, input_frame),
    )
    reverse = _specification(
        reference,
        definition,
        interfaces=("input-shaft", "output-shaft"),
        supplied_interface_definitions=(other, definition),
        supplied_reference_frames=(input_frame, output_frame),
    )
    assert tuple(item.interface_id for item in forward.supplied_interface_definitions) == (
        "input-shaft", "output-shaft"
    )
    assert tuple(item.frame_id for item in forward.supplied_reference_frames) == (
        "input-frame", "output-frame"
    )
    assert forward.specification_hash == reverse.specification_hash


def test_specification_rejects_dangling_frames_unlisted_interfaces_and_duplicate_ids():
    reference = _spec_reference()
    definition = _spec_definition(reference, reference_frame_id="missing-frame")
    with pytest.raises(ValidationError, match="frame"):
        _specification(reference, definition)

    definition = _spec_definition(reference)
    with pytest.raises(ValidationError, match="interfaces"):
        _specification(reference, definition, interfaces=())
    with pytest.raises(ValidationError, match="interface IDs"):
        _specification(
            reference,
            definition,
            supplied_interface_definitions=(definition, definition),
        )


def test_specification_rejects_mismatched_geometry_and_missing_at_2_coordinate_system():
    reference = _spec_reference()
    definition = _spec_definition(reference)
    other_reference = GeometrySourceReference(
        artifact_id="ART-OTHER",
        artifact_hash="sha256:" + "d" * 64,
        source_identity="source:other",
        coordinate_system_id="step-model-coordinates@1",
    )
    with pytest.raises(ValidationError, match="geometry"):
        _specification(reference, _spec_definition(other_reference))

    legacy_reference = _spec_reference(coordinate_system_id=None)
    legacy_frame = _spec_frame(legacy_reference)
    with pytest.raises(ValidationError, match="coordinate"):
        ComponentSpecificationSnapshot(
            schema_version="component-specification@2",
            component_type="motor",
            source_identity="source:motor",
            geometry_source=legacy_reference,
            supplied_reference_frames=(legacy_frame,),
        )


def test_specification_rejects_mounting_face_normal_that_disagrees_with_frame_plus_z():
    reference = _spec_reference()
    geometry = GeometryArtifactIdentity.from_candidate(reference)
    face_payload = _mounting_face(()).model_dump(mode="json")
    face_payload["geometry_reference_hash"] = reference.reference_hash
    face_payload["geometry"] = geometry.model_dump(mode="json")
    face_payload["outward_normal"]["evidence"][0]["value"] = (0.0, 0.0, -1.0)
    face_payload["outward_normal"]["evidence"][0]["evidence_hash"] = "pending"
    face_payload["outward_normal"]["fact_hash"] = "pending"
    face_payload["interface_hash"] = "pending"
    face = MountingFaceInterface.model_validate(face_payload)
    definition = SuppliedComponentInterfaceDefinition(
        interface_id=face.interface_id,
        geometry_reference_hash=reference.reference_hash,
        geometry=geometry,
        mounting_face=face,
    )
    with pytest.raises(ValidationError, match="normal"):
        _specification(
            reference,
            definition,
            supplied_reference_frames=(_spec_frame(reference, "mount-frame"),),
        )
    canonical_reference = CanonicalGeometrySourceReference.model_validate(
        reference.model_dump(mode="json")
    )
    with pytest.raises(ValidationError, match="normal"):
        CanonicalComponentSpecification(
            schema_version="canonical-component-specification@2",
            component_type="motor",
            source_identity="source:motor",
            geometry_source=canonical_reference,
            interfaces=(definition.interface_id,),
            supplied_reference_frames=(_spec_frame(reference, "mount-frame"),),
            supplied_interface_definitions=(definition,),
        )


def _materialized_mounting_specification(*, outward_normal=(0.0, 0.0, 1.0)):
    source_reference = GeometrySourceReference(
        artifact_id="ART-SOURCE",
        artifact_hash="sha256:" + "c" * 64,
        source_identity="vendor:interface",
        coordinate_system_id="source-model-coordinates@1",
    )
    source_geometry = GeometryArtifactIdentity.from_candidate(source_reference)
    face_payload = _mounting_face(()).model_dump(mode="json")
    face_payload.update(
        geometry_reference_hash=source_reference.reference_hash,
        geometry=source_geometry.model_dump(mode="json"),
        interface_hash="pending",
    )
    face_payload["outward_normal"]["evidence"][0]["value"] = outward_normal
    face_payload["outward_normal"]["evidence"][0]["evidence_hash"] = "pending"
    face_payload["outward_normal"]["fact_hash"] = "pending"
    source_payload = {
        "kind": "direct",
        "interface_id": "mount-face",
        "geometry_reference_hash": source_reference.reference_hash,
        "geometry": source_geometry.model_dump(mode="json"),
        "shaft": None,
        "mounting_face": face_payload,
        "derivation": None,
        "interface_hash": "pending",
    }
    source = SuppliedComponentInterfaceDefinition.model_validate(source_payload)
    source_frame = _spec_frame(source_reference, "mount-frame")

    transform_payload = _materialization_transform().model_dump(mode="json")
    derived_geometry = GeometryArtifactIdentity(
        artifact_id="ART-DERIVED",
        artifact_hash="sha256:" + "d" * 64,
        source_identity="vendor:interface",
        coordinate_system_id="step-model-coordinates@1",
    )
    derived_reference = GeometrySourceReference(
        artifact_id=derived_geometry.artifact_id,
        artifact_hash=derived_geometry.artifact_hash,
        source_identity=derived_geometry.source_identity,
        coordinate_system_id=derived_geometry.coordinate_system_id,
    )
    transform_payload.update(
        source_geometry=source_geometry.model_dump(mode="json"),
        derived_geometry=derived_geometry.model_dump(mode="json"),
        source_geometry_reference_hash=source_reference.reference_hash,
        derived_geometry_reference_hash=derived_reference.reference_hash,
        transform_hash="pending",
    )
    transform = GeometryDerivationTransform.model_validate(transform_payload)
    result = materialize_interface(source, source_frame, transform)
    return derived_reference, result, transform


def test_materialized_mounting_face_normal_must_match_active_derived_frame_plus_z():
    derived_reference, result, transform = _materialized_mounting_specification(
        outward_normal=(0.0, 0.0, -1.0)
    )
    values = dict(
        schema_version="component-specification@2",
        component_type="mount",
        source_identity="source:mount",
        geometry_source=derived_reference,
        interfaces=(result.interface.interface_id,),
        supplied_reference_frames=(result.reference_frame,),
        supplied_interface_definitions=(result.interface,),
        geometry_derivation_transforms=(transform,),
    )
    with pytest.raises(ValidationError, match="normal"):
        ComponentSpecificationSnapshot(**values)
    canonical_reference = CanonicalGeometrySourceReference.model_validate(
        derived_reference.model_dump(mode="json")
    )
    with pytest.raises(ValidationError, match="normal"):
        CanonicalComponentSpecification(
            schema_version="canonical-component-specification@2",
            component_type="mount",
            source_identity="source:mount",
            geometry_source=canonical_reference,
            interfaces=(result.interface.interface_id,),
            supplied_reference_frames=(result.reference_frame,),
            supplied_interface_definitions=(result.interface,),
            geometry_derivation_transforms=(transform,),
        )


def test_valid_materialized_interface_passes_structural_authority_gate():
    _, result, _ = _materialized_mounting_specification()

    assert require_authoritatively_consumable_interface(
        result.interface, result.reference_frame
    ) is result.interface


def test_materialized_authority_gate_requires_the_exact_active_frame():
    _, result, _ = _materialized_mounting_specification()

    with pytest.raises(ValueError, match="active frame"):
        require_authoritatively_consumable_interface(result.interface)


def test_materialized_authority_gate_rejects_wrong_active_frame_identity():
    _, result, _ = _materialized_mounting_specification()
    assert result.reference_frame is not None
    wrong_frame = SuppliedComponentReferenceFrame.model_validate(
        result.reference_frame.model_dump(mode="json")
        | {"frame_id": "different-frame", "frame_hash": "pending"}
    )

    with pytest.raises(ValueError, match="frame ID"):
        require_authoritatively_consumable_interface(result.interface, wrong_frame)


def test_materialized_authority_gate_rejects_wrong_active_frame_hash():
    _, result, _ = _materialized_mounting_specification()
    assert result.reference_frame is not None
    wrong_hash = result.reference_frame.model_copy(
        update={"frame_hash": "sha256:" + "0" * 64}
    )

    with pytest.raises(ValueError, match="frame"):
        require_authoritatively_consumable_interface(result.interface, wrong_hash)


def test_materialized_authority_gate_rejects_rehashed_forged_active_frame():
    _, result, _ = _materialized_mounting_specification()
    assert result.reference_frame is not None
    frame_payload = result.reference_frame.model_dump(mode="json")
    frame_payload["origin"]["evidence"][0]["value"] = (99.0, 0.0, 0.0)
    frame_payload["origin"]["evidence"][0]["evidence_hash"] = "pending"
    frame_payload["origin"]["fact_hash"] = "pending"
    frame_payload["frame_hash"] = "pending"
    forged_frame = SuppliedComponentReferenceFrame.model_validate(frame_payload)

    with pytest.raises(ValueError, match="frame"):
        require_authoritatively_consumable_interface(result.interface, forged_frame)


def test_materialized_authority_gate_rejects_provenance_snapshot_interface_id_mismatch():
    _, result, _ = _materialized_mounting_specification()
    provenance = result.interface.derivation
    source_payload = provenance.source_interface_snapshot.model_dump(mode="json")
    source_payload["interface_id"] = "different-source-interface"
    source_payload["mounting_face"]["interface_id"] = "different-source-interface"
    source_payload["mounting_face"]["interface_hash"] = "pending"
    source_payload["interface_hash"] = "pending"
    changed_source = SuppliedComponentInterfaceDefinition.model_validate(source_payload)
    changed_provenance = type(provenance).model_validate(
        provenance.model_dump(mode="json")
        | {
            "source_interface_snapshot": changed_source.model_dump(mode="json"),
            "source_interface_hash": changed_source.interface_hash,
            "provenance_hash": "pending",
        }
    )
    malformed = SuppliedComponentInterfaceDefinition.model_validate(
        result.interface.model_dump(mode="json")
        | {
            "derivation": changed_provenance.model_dump(mode="json"),
            "interface_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="interface identity"):
        require_authoritatively_consumable_interface(malformed)


def test_materialized_authority_gate_rejects_forged_derived_evidence_id():
    _, result, _ = _materialized_mounting_specification()
    active_face = result.interface.mounting_face
    assert active_face is not None
    fact = active_face.plane_point
    selected = fact.evidence[0]
    forged_evidence = SuppliedInterfaceEvidence.model_validate(
        selected.model_dump(mode="json")
        | {"evidence_id": "forged-derived-evidence", "evidence_hash": "pending"}
    )
    forged_fact = SuppliedInterfaceFact.model_validate(
        fact.model_dump(mode="json")
        | {
            "evidence": (forged_evidence.model_dump(mode="json"),),
            "accepted_evidence_id": forged_evidence.evidence_id,
            "fact_hash": "pending",
        }
    )
    forged_face = MountingFaceInterface.model_validate(
        active_face.model_dump(mode="json")
        | {"plane_point": forged_fact.model_dump(mode="json"), "interface_hash": "pending"}
    )
    malformed = SuppliedComponentInterfaceDefinition.model_validate(
        result.interface.model_dump(mode="json")
        | {"mounting_face": forged_face.model_dump(mode="json"), "interface_hash": "pending"}
    )

    with pytest.raises(ValueError, match="derived evidence binding"):
        require_authoritatively_consumable_interface(malformed)


def test_materialized_authority_gate_rejects_incomplete_closed_provenance():
    _, result, _ = _materialized_mounting_specification()
    provenance = result.interface.derivation
    incomplete = provenance.model_copy(
        update={
            "fact_derivation_bindings": provenance.fact_derivation_bindings[:-1],
            "provenance_hash": "pending",
        }
    )
    malformed = result.interface.model_copy(update={"derivation": incomplete})

    with pytest.raises(ValueError, match="bindings"):
        require_authoritatively_consumable_interface(malformed)


def test_materialized_authority_gate_rejects_non_derived_active_fact():
    _, result, _ = _materialized_mounting_specification()
    active_face = result.interface.mounting_face
    assert active_face is not None
    direct_fact = _interface_fact(
        "plane-point",
        SuppliedInterfaceTransformRole.POINT_MM,
        (0.0, 0.0, 0.0),
    )
    malformed_face = active_face.model_copy(update={"plane_point": direct_fact})
    malformed = result.interface.model_copy(update={"mounting_face": malformed_face})

    with pytest.raises(ValueError, match="derived"):
        require_authoritatively_consumable_interface(malformed)


def test_materialized_authority_gate_rejects_omitted_source_fact_slot():
    _, result, _ = _materialized_mounting_specification()
    active_face = result.interface.mounting_face
    assert active_face is not None
    face_payload = active_face.model_dump(mode="json")
    face_payload.update(pilot_boss=None, interface_hash="pending")
    malformed_face = MountingFaceInterface.model_validate(face_payload)
    definition_payload = result.interface.model_dump(mode="json")
    definition_payload.update(
        mounting_face=malformed_face.model_dump(mode="json"), interface_hash="pending"
    )
    malformed = SuppliedComponentInterfaceDefinition.model_validate(definition_payload)

    with pytest.raises(ValueError, match="slots"):
        require_authoritatively_consumable_interface(malformed)


def test_materialized_authority_gate_rejects_extra_active_fact_evidence():
    _, result, _ = _materialized_mounting_specification()
    active_face = result.interface.mounting_face
    assert active_face is not None
    selected = active_face.plane_point.evidence[0]
    extra = SuppliedInterfaceEvidence.model_validate(
        selected.model_dump(mode="json")
        | {"evidence_id": "extra-derived-evidence", "evidence_hash": "pending"}
    )
    plane_point_payload = active_face.plane_point.model_dump(mode="json")
    plane_point_payload.update(
        evidence=(selected.model_dump(mode="json"), extra.model_dump(mode="json")),
        fact_hash="pending",
    )
    plane_point = SuppliedInterfaceFact.model_validate(plane_point_payload)
    face_payload = active_face.model_dump(mode="json")
    face_payload.update(plane_point=plane_point.model_dump(mode="json"), interface_hash="pending")
    malformed_face = MountingFaceInterface.model_validate(face_payload)
    definition_payload = result.interface.model_dump(mode="json")
    definition_payload.update(
        mounting_face=malformed_face.model_dump(mode="json"), interface_hash="pending"
    )
    malformed = SuppliedComponentInterfaceDefinition.model_validate(definition_payload)

    with pytest.raises(ValueError, match="one deterministic evidence record"):
        require_authoritatively_consumable_interface(malformed)


def test_unselected_mounting_normal_or_frame_orientation_remains_unresolved():
    reference = _spec_reference()
    geometry = GeometryArtifactIdentity.from_candidate(reference)
    face_payload = _mounting_face(()).model_dump(mode="json")
    face_payload.update(
        geometry_reference_hash=reference.reference_hash,
        geometry=geometry.model_dump(mode="json"),
        interface_hash="pending",
    )
    face_payload["outward_normal"]["accepted_evidence_id"] = None
    face_payload["outward_normal"]["fact_hash"] = "pending"
    face = MountingFaceInterface.model_validate(face_payload)
    definition = SuppliedComponentInterfaceDefinition.model_validate(
        {
            "kind": "direct",
            "interface_id": face.interface_id,
            "geometry_reference_hash": reference.reference_hash,
            "geometry": geometry.model_dump(mode="json"),
            "shaft": None,
            "mounting_face": face.model_dump(mode="json"),
            "derivation": None,
            "interface_hash": "pending",
        }
    )
    specification = _specification(
        reference,
        definition,
        supplied_reference_frames=(_spec_frame(reference, "mount-frame"),),
    )
    assert specification.supplied_interface_definitions[0] == definition
    with pytest.raises(ValueError, match="outward normal"):
        require_authoritatively_consumable_interface(definition)

    frame_payload = _spec_frame(reference, "mount-frame").model_dump(mode="json")
    frame_payload["orientation"]["accepted_evidence_id"] = None
    frame_payload["orientation"]["fact_hash"] = "pending"
    frame_payload["frame_hash"] = "pending"
    unresolved_frame = SuppliedComponentReferenceFrame.model_validate(frame_payload)
    assert _specification(
        reference,
        _spec_definition(reference, reference_frame_id="mount-frame"),
        supplied_reference_frames=(unresolved_frame,),
    ).supplied_reference_frames[0] == unresolved_frame


def test_canonical_specification_uses_the_same_typed_active_interface_registry():
    reference = _spec_reference()
    definition = _spec_definition(reference)
    canonical_reference = CanonicalGeometrySourceReference.model_validate(
        reference.model_dump(mode="json")
    )
    specification = CanonicalComponentSpecification(
        schema_version="canonical-component-specification@2",
        component_type="motor",
        source_identity="source:motor",
        geometry_source=canonical_reference,
        interfaces=(definition.interface_id,),
        supplied_interface_definitions=(definition,),
    )
    assert specification.supplied_interface_definitions[0].interface_id == "output-shaft"


def _historical_snapshot_variants(active):
    historical = active.derivation.source_interface_snapshot
    mutated_payload = historical.model_dump(mode="json")
    mutated_payload["mounting_face"]["face_reference_id"] = "Face9"
    mutated_payload["mounting_face"]["interface_hash"] = "pending"
    mutated_payload["interface_hash"] = "pending"
    mutated = SuppliedComponentInterfaceDefinition.model_validate(mutated_payload)

    replaced_payload = historical.model_dump(mode="json")
    replaced_payload["interface_id"] = "historical-replacement"
    replaced_payload["mounting_face"]["interface_id"] = "historical-replacement"
    replaced_payload["mounting_face"]["interface_hash"] = "pending"
    replaced_payload["interface_hash"] = "pending"
    replaced = SuppliedComponentInterfaceDefinition.model_validate(replaced_payload)
    return ("mutated", mutated), ("removed", None), ("replaced", replaced)


def _materialized_with_historical_snapshot(active, historical):
    provenance = active.derivation.model_copy(
        update={"source_interface_snapshot": historical}
    )
    return active.model_copy(update={"derivation": provenance})


@pytest.mark.parametrize("variant_name", ("mutated", "removed", "replaced"))
def test_candidate_endpoints_resolve_only_from_active_typed_definitions(variant_name):
    derived_reference, result, transform = _materialized_mounting_specification()
    original = ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="mount",
        source_identity="source:mount",
        geometry_source=derived_reference,
        interfaces=(result.interface.interface_id,),
        supplied_reference_frames=(result.reference_frame,),
        supplied_interface_definitions=(result.interface,),
        geometry_derivation_transforms=(transform,),
    )
    variants = dict(_historical_snapshot_variants(result.interface))
    active = _materialized_with_historical_snapshot(
        result.interface, variants[variant_name]
    )
    assert active.derivation.source_interface_snapshot is variants[variant_name]
    specification = original.model_copy(update={
        "supplied_interface_definitions": (active,),
    })
    active_registry = {
        definition.interface_id: definition
        for definition in specification.supplied_interface_definitions
    }
    resolved = active_registry["mount-face"]
    assert resolved is active
    assert resolved.kind == "materialized"
    assert resolved.geometry == GeometryArtifactIdentity.from_candidate(derived_reference)
    assert set(active_registry) == {"mount-face"}
    assert tuple(active_registry) == tuple(
        definition.interface_id
        for definition in specification.supplied_interface_definitions
    )
    PhysicalMechanismRealization(
        components=(
            PhysicalComponentInstance(
                instance_id="left",
                specification_hash=specification.specification_hash,
                role=PhysicalComponentRole.MOUNT_OR_SUPPORT,
                interfaces=tuple(active_registry),
            ),
            PhysicalComponentInstance(
                instance_id="right",
                specification_hash=specification.specification_hash,
                role=PhysicalComponentRole.MOUNT_OR_SUPPORT,
                interfaces=tuple(active_registry),
            ),
        ),
        connections=(
            MechanicalConnection(
                connection_id="attachment",
                kind=MechanicalConnectionKind.FIXED_ATTACHMENT,
                from_instance_id="left",
                from_interface_id="mount-face",
                to_instance_id="right",
                to_interface_id="mount-face",
            ),
        ),
    )


@pytest.mark.parametrize("variant_name", ("mutated", "removed", "replaced"))
def test_canonical_endpoints_resolve_only_from_active_typed_definitions(variant_name):
    derived_reference, result, transform = _materialized_mounting_specification()
    canonical_reference = CanonicalGeometrySourceReference.model_validate(
        derived_reference.model_dump(mode="json")
    )
    original = CanonicalComponentSpecification(
        schema_version="canonical-component-specification@2",
        component_type="mount",
        source_identity="source:mount",
        geometry_source=canonical_reference,
        interfaces=(result.interface.interface_id,),
        supplied_reference_frames=(result.reference_frame,),
        supplied_interface_definitions=(result.interface,),
        geometry_derivation_transforms=(transform,),
    )
    variants = dict(_historical_snapshot_variants(result.interface))
    active = _materialized_with_historical_snapshot(
        result.interface, variants[variant_name]
    )
    assert active.derivation.source_interface_snapshot is variants[variant_name]
    specification = original.model_copy(update={
        "supplied_interface_definitions": (active,),
    })
    active_registry = {
        definition.interface_id: definition
        for definition in specification.supplied_interface_definitions
    }
    resolved = active_registry["mount-face"]
    assert resolved is active
    assert resolved.kind == "materialized"
    assert set(active_registry) == {"mount-face"}
    components = (
        CanonicalPhysicalComponent(
            instance_id="left",
            specification_hash=specification.specification_hash,
            role=CanonicalPhysicalComponentRole.MOUNT_OR_SUPPORT,
            interfaces=tuple(active_registry),
        ),
        CanonicalPhysicalComponent(
            instance_id="right",
            specification_hash=specification.specification_hash,
            role=CanonicalPhysicalComponentRole.MOUNT_OR_SUPPORT,
            interfaces=tuple(active_registry),
        ),
    )
    connection = CanonicalMechanicalConnection(
        connection_id="attachment",
        kind=CanonicalMechanicalConnectionKind.FIXED_ATTACHMENT,
        from_instance_id="left",
        from_interface_id="mount-face",
        to_instance_id="right",
        to_interface_id="mount-face",
    )
    assert connection.from_interface_id in components[0].interfaces
    assert connection.to_interface_id in components[1].interfaces
    assert connection.from_interface_id in active_registry
    assert connection.to_interface_id in active_registry
