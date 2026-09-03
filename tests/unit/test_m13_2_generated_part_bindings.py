from __future__ import annotations

import hashlib
import math
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from mechcad_harness.models import (
    GeneratedAuthorityInput,
    GeneratedAuthorityError,
    GeneratedPartFieldBinding,
    GeneratedAuthorityView,
    evaluate_generated_field_rule,
    resolve_generated_inputs,
)
from mechcad_harness.models.component_property import (
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
)
from mechcad_harness.candidates.models import ComponentPropertySnapshot
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity, geometry_reference_hash
from mechcad_harness.state.hashing import canonical_json
from mechcad_harness.models.generated_part import selection_hash, value_hash
from mechcad_harness.models.generated_part import DesignSelectionLocator
from mechcad_harness.models.supplied_component_interface import (
    MountingFaceInterface,
    MountingHole,
    SuppliedComponentInterfaceDefinition,
    SuppliedInterfaceEvidence,
    SuppliedInterfaceEvidenceOrigin,
    SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceFact,
    SuppliedInterfaceTransformRole,
    materialize_interface,
)
from test_m13_geometry_materialization import (
    _accepted_shaft_definition,
    _frame_for_source,
    _materialization_transform,
    _source_shaft_with_frame,
)


def _selection_input(
    input_id: str,
    value: float,
    *,
    name_form: str = "component_scoped",
    selection_key: str | None = None,
) -> GeneratedAuthorityInput:
    key = selection_key or input_id
    return GeneratedAuthorityInput(
        input_id=input_id,
        role="dimension",
        source_kind="design_selection",
        locator={
            "name_form": name_form,
            "selection_key": key,
            "selection_hash": selection_hash(name_form, key, value),
        },
        value=value,
        value_hash=value_hash(value),
    )


def test_design_selection_locator_is_layer_independent_and_resolves_by_scope():
    input_record = _selection_input("diameter", 12.5, selection_key="shaft-diameter")
    assert "candidate:" not in repr(input_record.model_dump(mode="json"))
    assert "instance-id" not in repr(input_record.model_dump(mode="json"))
    values = resolve_generated_inputs(
        (input_record,),
        GeneratedAuthorityView(design_selections={"shaft-diameter": 12.5}),
    )
    assert values == {"diameter": 12.5}


def test_instance_scoped_locator_uses_only_the_supplied_owner_context():
    input_record = _selection_input(
        "diameter", 12.5, name_form="instance_scoped", selection_key="geometry.diameter_mm"
    )
    view = GeneratedAuthorityView(
        design_selections={
            "motor-a.geometry.diameter_mm": 12.5,
            "motor-b.geometry.diameter_mm": 15.0,
        }
    )
    assert resolve_generated_inputs((input_record,), view, owning_instance_context="motor-a") == {
        "diameter": 12.5
    }
    with pytest.raises(Exception):
        resolve_generated_inputs((input_record,), view, owning_instance_context="motor-b")


@pytest.mark.parametrize(
    "selection_key",
    [
        "candidate:other.geometry.diameter_mm",
        "motor-b.geometry.diameter_mm",
        "geometry.motor-b.diameter_mm",
    ],
)
def test_instance_scoped_locator_rejects_identity_and_legacy_geometry_keys(selection_key):
    with pytest.raises(ValidationError):
        _selection_input(
            "diameter", 12.5, name_form="instance_scoped", selection_key=selection_key
        )


@pytest.mark.parametrize("selection_key", ["diameter_mm", "geometry.diameter_mm"])
def test_instance_scoped_locator_preserves_relative_alias_forms(selection_key):
    input_record = _selection_input(
        "diameter", 12.5, name_form="instance_scoped", selection_key=selection_key
    )
    assert resolve_generated_inputs(
        (input_record,),
        GeneratedAuthorityView(
            design_selections={f"motor-a.{selection_key}": 12.5}
        ),
        owning_instance_context="motor-a",
    ) == {"diameter": 12.5}


def test_instance_scoped_locator_preserves_relative_placement_alias():
    input_record = _selection_input(
        "offset", 2.5, name_form="instance_scoped", selection_key="placement.axial_offset_mm"
    )
    assert resolve_generated_inputs(
        (input_record,),
        GeneratedAuthorityView(design_selections={"motor-a.placement.axial_offset_mm": 2.5}),
        owning_instance_context="motor-a",
    ) == {"offset": 2.5}


@pytest.mark.parametrize(
    "selection_key",
    [
        "candidate:other.geometry.diameter_mm",
        "motor-a.geometry.diameter_mm",
        "geometry.motor-a.diameter_mm",
    ],
)
def test_component_scoped_locator_rejects_qualified_and_dotted_keys(selection_key):
    with pytest.raises(ValidationError):
        DesignSelectionLocator(
            name_form="component_scoped",
            selection_key=selection_key,
            selection_hash=selection_hash("component_scoped", selection_key, 12.5),
        )


def test_component_scoped_locator_accepts_raw_semantic_key():
    selection_key = "selected-output-shaft-diameter"
    locator = DesignSelectionLocator(
        name_form="component_scoped",
        selection_key=selection_key,
        selection_hash=selection_hash("component_scoped", selection_key, 12.5),
    )
    assert locator.selection_key == selection_key


@pytest.mark.parametrize("identity_field", ["name", "key", "selection_key"])
def test_design_selection_mapping_record_must_self_identify_as_resolved_key(identity_field):
    input_record = _selection_input("diameter", 12.5, selection_key="shaft-diameter")
    valid_record = {identity_field: "shaft-diameter", "value": 12.5}
    assert resolve_generated_inputs(
        (input_record,),
        GeneratedAuthorityView(design_selections={"shaft-diameter": valid_record}),
    ) == {"diameter": 12.5}

    forged_record = {identity_field: "other-selection", "value": 12.5}
    with pytest.raises(Exception):
        resolve_generated_inputs(
            (input_record,),
            GeneratedAuthorityView(design_selections={"shaft-diameter": forged_record}),
        )


def test_resolve_generated_inputs_rejects_duplicate_input_ids():
    first = _selection_input("diameter", 12.5, selection_key="first")
    second = _selection_input("diameter", 12.5, selection_key="second")
    with pytest.raises(Exception, match="unique"):
        resolve_generated_inputs(
            (first, second),
            GeneratedAuthorityView(design_selections={"first": 12.5, "second": 12.5}),
        )


def _component_property_input(value: float = 12.5, property_key: str = "shaft-diameter"):
    return GeneratedAuthorityInput(
        input_id="diameter",
        role="dimension",
        source_kind="component_property",
        locator={"property_key": property_key},
        value=value,
        value_hash=value_hash(value),
    )


def _available_property(value: float = 12.5, key: str = "shaft-diameter"):
    return ComponentPropertySnapshot(
        key=key,
        availability=ComponentPropertyAvailability.AVAILABLE,
        normalized_value=value,
        canonical_unit="mm",
        source_identity="source:property",
        authority=ComponentPropertyAuthority.MEASURED_LOCAL,
    )


def _self_hashed_property_payload(**updates):
    payload = _available_property().model_dump(mode="json")
    payload.update(updates)
    payload.pop("property_hash", None)
    payload["property_hash"] = "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()
    return payload


def test_component_property_resolution_requires_complete_self_hashed_authority_record():
    input_record = _component_property_input()
    property_record = _available_property()
    assert resolve_generated_inputs(
        (input_record,), GeneratedAuthorityView(component_properties={property_record.key: property_record})
    ) == {"diameter": 12.5}

    incomplete = {"key": property_record.key, "normalized_value": 12.5}
    with pytest.raises(Exception):
        resolve_generated_inputs(
            (input_record,), GeneratedAuthorityView(component_properties={property_record.key: incomplete})
        )

    wrong_key = _available_property(key="other-property")
    with pytest.raises(Exception):
        resolve_generated_inputs(
            (input_record,), GeneratedAuthorityView(component_properties={property_record.key: wrong_key})
        )

    tampered = property_record.model_dump(mode="json")
    tampered["property_hash"] = value_hash(12.5)
    with pytest.raises(Exception):
        resolve_generated_inputs(
            (input_record,), GeneratedAuthorityView(component_properties={property_record.key: tampered})
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"availability": "missing"},
        {"canonical_unit": "cm"},
        {"normalized_value": True},
        {"normalized_value": None, "normalized_range": [12.0, 13.0]},
        {"normalized_value": math.nan},
    ],
)
def test_component_property_resolution_rejects_invalid_available_scalar_metadata(updates):
    input_record = _component_property_input()
    property_record = _self_hashed_property_payload(**updates)
    with pytest.raises(Exception):
        resolve_generated_inputs(
            (input_record,),
            GeneratedAuthorityView(component_properties={property_record["key"]: property_record}),
        )


def test_mapping_interface_resolution_checks_selected_record_identity(monkeypatch):
    from mechcad_harness.models.generated_part import M13_1InterfaceFactLocator
    import mechcad_harness.models.supplied_component_interface as supplied

    fact = SimpleNamespace(fact_id="diameter")
    definition = SimpleNamespace(
        interface_hash="sha256:" + "2" * 64,
        shaft=SimpleNamespace(diameter=fact),
        mounting_face=None,
    )
    evidence = SimpleNamespace(evidence_id="evidence:diameter", value=12.5)
    monkeypatch.setattr(supplied, "require_authoritatively_consumable_interface", lambda value: value)
    monkeypatch.setattr(supplied, "require_authoritative_fact", lambda value, fact_name: evidence)
    locator = M13_1InterfaceFactLocator(
        interface_hash="sha256:" + "1" * 64,
        fact_id="diameter",
        accepted_evidence_id="evidence:diameter",
        value_hash=value_hash(12.5),
    )

    with pytest.raises(Exception):
        resolve_generated_inputs(
            (
                GeneratedAuthorityInput(
                    input_id="diameter",
                    role="dimension",
                    source_kind="m13_1_interface_fact",
                    locator=locator,
                    value=12.5,
                    value_hash=value_hash(12.5),
                ),
            ),
            GeneratedAuthorityView(
                interface_definitions={locator.interface_hash: definition}
            ),
        )


def test_interface_fact_resolution_consumes_materialized_fact_after_provenance_gate():
    materialized = materialize_interface(
        _accepted_shaft_definition(scale_independent_fixtures=True),
        None,
        _materialization_transform(),
    )
    definition = materialized.interface
    evidence_id = "derived:shaft-diameter:T1"
    input_record = GeneratedAuthorityInput(
        input_id="diameter",
        role="supplied_diameter",
        source_kind="m13_1_interface_fact",
        locator={
            "interface_hash": definition.interface_hash,
            "fact_id": evidence_id,
            "accepted_evidence_id": evidence_id,
            "value_hash": value_hash(10.0),
        },
        value=10.0,
        value_hash=value_hash(10.0),
    )

    assert resolve_generated_inputs(
        (input_record,),
        GeneratedAuthorityView(interface_definitions={definition.interface_hash: definition}),
    ) == {"diameter": 10.0}


def test_materialized_interface_fact_resolution_supplies_exact_active_frame_to_authority_gate(
    monkeypatch,
):
    source = _source_shaft_with_frame()
    source_frame = _frame_for_source(source.geometry)
    materialized = materialize_interface(source, source_frame, _materialization_transform())
    definition = materialized.interface
    reference_frame = materialized.reference_frame
    assert reference_frame is not None
    evidence_id = "derived:shaft-diameter:T1"
    input_record = GeneratedAuthorityInput(
        input_id="diameter",
        role="supplied_diameter",
        source_kind="m13_1_interface_fact",
        locator={
            "interface_hash": definition.interface_hash,
            "fact_id": evidence_id,
            "accepted_evidence_id": evidence_id,
            "value_hash": value_hash(10.0),
        },
        value=10.0,
        value_hash=value_hash(10.0),
    )

    import mechcad_harness.models.supplied_component_interface as supplied

    calls = []
    original_gate = supplied.require_authoritatively_consumable_interface

    def recording_gate(candidate, frame=None):
        calls.append((candidate, frame))
        return original_gate(candidate, frame)

    monkeypatch.setattr(supplied, "require_authoritatively_consumable_interface", recording_gate)

    assert resolve_generated_inputs(
        (input_record,),
        GeneratedAuthorityView(
            interface_definitions={definition.interface_hash: definition},
            reference_frames={reference_frame.frame_id: reference_frame},
        ),
    ) == {"diameter": 10.0}
    assert len(calls) == 1
    assert calls[0][0].interface_hash == definition.interface_hash
    assert calls[0][1] == reference_frame


def test_interface_fact_resolution_rejects_forged_outer_record_with_typed_variant():
    definition = _accepted_shaft_definition()
    input_record = GeneratedAuthorityInput(
        input_id="diameter",
        role="supplied_diameter",
        source_kind="m13_1_interface_fact",
        locator={
            "interface_hash": definition.interface_hash,
            "fact_id": "shaft-diameter",
            "accepted_evidence_id": "evidence:shaft-diameter",
            "value_hash": value_hash(8.0),
        },
        value=8.0,
        value_hash=value_hash(8.0),
    )
    forged_outer = SimpleNamespace(
        interface_hash=definition.interface_hash,
        shaft=definition.shaft,
        mounting_face=None,
    )

    with pytest.raises(GeneratedAuthorityError, match="cannot be resolved"):
        resolve_generated_inputs(
            (input_record,),
            GeneratedAuthorityView(interface_definitions={definition.interface_hash: forged_outer}),
        )


def test_interface_fact_resolution_consumes_nested_mounting_hole_fact():
    geometry = GeometryArtifactIdentity(
        artifact_id="ART-MOUNT",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="vendor:mount",
    )
    geometry_hash = geometry_reference_hash(geometry)

    def fact(fact_id, role, value):
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
            source_identity="datasheet:mount",
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

    hole = MountingHole(
        hole_id="H1",
        center=fact("hole-center", SuppliedInterfaceTransformRole.POINT_MM, (3.0, 5.0, 0.0)),
        axis=fact("hole-axis", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0)),
        nominal_diameter=fact("hole-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 4.0),
    )
    face = MountingFaceInterface(
        interface_id="mount-face",
        geometry_reference_hash=geometry_hash,
        geometry=geometry,
        face_reference_id="Face3",
        reference_frame_id="mount-frame",
        plane_point=fact("plane-point", SuppliedInterfaceTransformRole.POINT_MM, (0.0, 0.0, 0.0)),
        outward_normal=fact("plane-normal", SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 1.0)),
        holes=(hole,),
    )
    definition = SuppliedComponentInterfaceDefinition(
        interface_id=face.interface_id,
        geometry_reference_hash=geometry_hash,
        geometry=geometry,
        mounting_face=face,
    )
    input_record = GeneratedAuthorityInput(
        input_id="hole-diameter",
        role="supplied_diameter",
        source_kind="m13_1_interface_fact",
        locator={
            "interface_hash": definition.interface_hash,
            "fact_id": "hole-diameter",
            "accepted_evidence_id": "evidence:hole-diameter",
            "value_hash": value_hash(4.0),
        },
        value=4.0,
        value_hash=value_hash(4.0),
    )

    assert SuppliedComponentInterfaceDefinition.model_validate(
        definition.model_dump(mode="json")
    ).interface_hash == definition.interface_hash
    assert resolve_generated_inputs(
        (input_record,),
        GeneratedAuthorityView(interface_definitions={definition.interface_hash: definition}),
    ) == {"hole-diameter": 4.0}


def test_selection_and_value_hashes_are_recomputed_not_trusted():
    with pytest.raises(ValidationError):
        GeneratedAuthorityInput.model_validate(
            _selection_input("diameter", 12.5).model_dump(mode="json")
            | {"value_hash": value_hash(13.0)}
        )
    with pytest.raises(ValidationError):
        GeneratedAuthorityInput(
            input_id="diameter",
            role="dimension",
            source_kind="design_selection",
            locator={
                "name_form": "component_scoped",
                "selection_key": "diameter",
                "selection_hash": selection_hash("component_scoped", "diameter", 13.0),
            },
            value=12.5,
            value_hash=value_hash(12.5),
        )


def test_direct_binding_requires_matching_input_and_field_value_hash():
    input_record = _selection_input("diameter", 12.5)
    binding = GeneratedPartFieldBinding(
        field_slot="shaft.diameter_mm",
        source={"input_id": "diameter"},
        field_value_hash=value_hash(12.5),
    )
    assert evaluate_generated_field_rule(binding, {"diameter": 12.5}) == 12.5
    with pytest.raises(Exception):
        evaluate_generated_field_rule(binding, {"diameter": 15.0})
    assert input_record.value_hash == value_hash(12.5)


@pytest.mark.parametrize(
    "source",
    [
        {"rule_id": "hub-bore-from-supplied-shaft@1", "input_ids": []},
        {"rule_id": "hub-bore-from-supplied-shaft@1", "input_ids": ["a", "b"]},
        {"rule_id": "hub-bore-from-supplied-shaft-with-clearance@1", "input_ids": ["a"]},
    ],
)
def test_relation_arity_and_roles_are_closed(source):
    with pytest.raises(ValidationError):
        GeneratedPartFieldBinding(
            field_slot="hub.bore:x.diameter_mm",
            source=source,
            field_value_hash=value_hash(12.5),
        )


def test_relation_evaluation_is_pure_and_missing_inputs_fail_closed():
    binding = GeneratedPartFieldBinding(
        field_slot="hub.bore:x.diameter_mm",
        source={"rule_id": "hub-bore-from-supplied-shaft-with-clearance@1", "input_ids": ["shaft", "clearance"]},
        field_value_hash=value_hash(13.0),
    )
    assert evaluate_generated_field_rule(binding, {"shaft": 12.0, "clearance": 1.0}) == 13.0
    with pytest.raises(Exception):
        evaluate_generated_field_rule(binding, {"shaft": 12.0})


def test_relation_input_ids_are_not_field_paths_and_no_cycle_can_be_encoded():
    with pytest.raises(ValidationError):
        GeneratedPartFieldBinding(
            field_slot="hub.bore:x.diameter_mm",
            source={"rule_id": "hub-bore-from-supplied-shaft@1", "input_ids": ["hub.bore:x.diameter_mm"]},
            field_value_hash=value_hash(12.0),
        )
