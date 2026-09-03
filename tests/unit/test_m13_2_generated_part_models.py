from __future__ import annotations

import math

import pytest
from pydantic import TypeAdapter, ValidationError

from mechcad_harness.models import (
    CylindricalHubSpecification,
    GeneratedPartSpecification,
    GeneratedAuthorityInput,
    GeneratedPartFieldBinding,
    GeneratedAttachmentFaceInterface,
    GeneratedInterfaceDerivation,
    GeneratedReferenceFrame,
    GeneratedRotationalInterface,
    RectangularFrameMemberSpecification,
    SolidCircularShaftSpecification,
    derive_frame_interfaces,
    derive_hub_interfaces,
    derive_shaft_interfaces,
    generated_geometry_definition_identities,
)


def _value_hash(value: float) -> str:
    from mechcad_harness.models.generated_part import value_hash

    return value_hash(value)


def test_generated_part_public_exports_include_locator_and_hash():
    from mechcad_harness.models import M13_1InterfaceFactLocator, generated_part_hash
    from mechcad_harness.models.generated_part import (
        M13_1InterfaceFactLocator as generated_part_locator,
        generated_part_hash as generated_part_hash_function,
    )

    assert M13_1InterfaceFactLocator is generated_part_locator
    assert generated_part_hash is generated_part_hash_function


def _selection_locator(key: str, value: float, *, name_form: str = "component_scoped"):
    from mechcad_harness.models.generated_part import selection_hash

    return {
        "name_form": name_form,
        "selection_key": key,
        "selection_hash": selection_hash(name_form, key, value),
    }


def _input(input_id: str, value: float, *, role: str = "dimension") -> GeneratedAuthorityInput:
    return GeneratedAuthorityInput(
        input_id=input_id,
        role=role,
        source_kind="design_selection",
        locator=_selection_locator(input_id, value),
        value=value,
        value_hash=_value_hash(value),
    )


def _direct(slot: str, input_id: str, value: float) -> GeneratedPartFieldBinding:
    return GeneratedPartFieldBinding(
        field_slot=slot,
        source={"input_id": input_id},
        field_value_hash=_value_hash(value),
    )


def _shaft(*, diameter: float = 10.0, length: float = 40.0, diameter_mm=None, length_mm=None, bindings=None):
    if diameter_mm is not None:
        diameter = diameter_mm
    if length_mm is not None:
        length = length_mm
    inputs = (_input("diameter", diameter), _input("length", length))
    return SolidCircularShaftSpecification(
        generated_part_id="shaft",
        diameter_mm=diameter,
        length_mm=length,
        inputs=inputs,
        field_bindings=bindings
        or (
            _direct("shaft.diameter_mm", "diameter", diameter),
            _direct("shaft.length_mm", "length", length),
        ),
    )


def test_each_generated_part_kind_round_trips_through_tagged_union():
    shaft = _shaft()
    hub = CylindricalHubSpecification(
        generated_part_id="hub",
        outer_diameter_mm=30.0,
        length_mm=50.0,
        bores=(
            {"bore_id": "output", "diameter_mm": 8.0, "start_z_mm": 25.0, "depth_mm": 25.0},
            {"bore_id": "input", "diameter_mm": 10.0, "start_z_mm": 0.0, "depth_mm": 25.0},
        ),
        inputs=(
            _input("outer", 30.0),
            _input("length", 50.0),
            _input("input-diameter", 10.0),
            _input("input-start", 0.0),
            _input("input-depth", 25.0),
            _input("output-diameter", 8.0),
            _input("output-start", 25.0),
            _input("output-depth", 25.0),
        ),
        field_bindings=(
            _direct("hub.outer_diameter_mm", "outer", 30.0),
            _direct("hub.length_mm", "length", 50.0),
            _direct("hub.bore:input.diameter_mm", "input-diameter", 10.0),
            _direct("hub.bore:input.start_z_mm", "input-start", 0.0),
            _direct("hub.bore:input.depth_mm", "input-depth", 25.0),
            _direct("hub.bore:output.diameter_mm", "output-diameter", 8.0),
            _direct("hub.bore:output.start_z_mm", "output-start", 25.0),
            _direct("hub.bore:output.depth_mm", "output-depth", 25.0),
        ),
    )
    frame_inputs = (_input("length", 60.0), _input("width", 20.0), _input("height", 10.0))
    frame = RectangularFrameMemberSpecification(
        generated_part_id="frame",
        length_mm=60.0,
        width_mm=20.0,
        height_mm=10.0,
        inputs=frame_inputs,
        field_bindings=(
            _direct("frame.length_mm", "length", 60.0),
            _direct("frame.width_mm", "width", 20.0),
            _direct("frame.height_mm", "height", 10.0),
        ),
    )

    adapter = TypeAdapter(GeneratedPartSpecification)
    for part in (shaft, hub, frame):
        assert adapter.validate_python(part.model_dump(mode="json")) == part


def test_hashes_are_deterministic_and_input_binding_order_is_canonicalized():
    first = _shaft()
    second = SolidCircularShaftSpecification(
        generated_part_id="shaft",
        diameter_mm=10.0,
        length_mm=40.0,
        inputs=tuple(reversed(first.inputs)),
        field_bindings=tuple(reversed(first.field_bindings)),
    )
    assert first.generated_part_hash == second.generated_part_hash
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


@pytest.mark.parametrize("field,value", [("diameter_mm", 0.0), ("length_mm", -1.0), ("diameter_mm", math.inf)])
def test_non_positive_or_non_finite_dimensions_are_rejected(field, value):
    values = {"diameter_mm": 10.0, "length_mm": 40.0}
    values[field] = value
    with pytest.raises(ValidationError):
        _shaft(**values)


def test_every_required_field_has_exactly_one_binding():
    with pytest.raises(ValidationError, match="binding"):
        _shaft(bindings=(_direct("shaft.diameter_mm", "diameter", 10.0),))

    with pytest.raises(ValidationError, match="binding"):
        _shaft(
            bindings=(
                _direct("shaft.diameter_mm", "diameter", 10.0),
                _direct("shaft.length_mm", "length", 40.0),
                _direct("shaft.length_mm", "length", 40.0),
            )
        )


def test_hub_bores_are_sorted_by_id_and_external_mouths_have_exact_directions():
    segment_a = {"bore_id": "a", "diameter_mm": 8.0, "start_z_mm": 0.0, "depth_mm": 10.0}
    segment_b = {"bore_id": "b", "diameter_mm": 6.0, "start_z_mm": 20.0, "depth_mm": 10.0}
    inputs = (
        _input("outer", 30.0),
        _input("length", 50.0),
        _input("a-diameter", 8.0),
        _input("a-start", 0.0),
        _input("a-depth", 10.0),
        _input("b-diameter", 6.0),
        _input("b-start", 20.0),
        _input("b-depth", 10.0),
    )
    bindings = (
        _direct("hub.outer_diameter_mm", "outer", 30.0),
        _direct("hub.length_mm", "length", 50.0),
        _direct("hub.bore:a.diameter_mm", "a-diameter", 8.0),
        _direct("hub.bore:a.start_z_mm", "a-start", 0.0),
        _direct("hub.bore:a.depth_mm", "a-depth", 10.0),
        _direct("hub.bore:b.diameter_mm", "b-diameter", 6.0),
        _direct("hub.bore:b.start_z_mm", "b-start", 20.0),
        _direct("hub.bore:b.depth_mm", "b-depth", 10.0),
    )
    hub = CylindricalHubSpecification(
        generated_part_id="hub",
        outer_diameter_mm=30.0,
        length_mm=50.0,
        bores=(segment_b, segment_a),
        inputs=inputs,
        field_bindings=bindings,
    )
    assert tuple(bore.bore_id for bore in hub.bores) == ("a", "b")
    mouths = {interface.interface_id: interface for interface in hub.interfaces}
    assert mouths["hub:bore:a:near"].axis_direction == (0.0, 0.0, 1.0)
    assert "hub:bore:a:far" not in mouths
    assert mouths["hub:bore:a:near"].axis_point == (0.0, 0.0, 0.0)
    assert not any("bore:b:near" in key or "bore:b:far" in key for key in mouths)


@pytest.mark.parametrize(
    "bores",
    [
        ({"bore_id": "x", "diameter_mm": 31.0, "start_z_mm": 0.0, "depth_mm": 5.0},),
        ({"bore_id": "x", "diameter_mm": 8.0, "start_z_mm": -1.0, "depth_mm": 5.0},),
        (
            {"bore_id": "x", "diameter_mm": 8.0, "start_z_mm": 0.0, "depth_mm": 6.0},
            {"bore_id": "y", "diameter_mm": 8.0, "start_z_mm": 5.0, "depth_mm": 6.0},
        ),
        (
            {"bore_id": "x", "diameter_mm": 8.0, "start_z_mm": 0.0, "depth_mm": 5.0},
            {"bore_id": "x", "diameter_mm": 8.0, "start_z_mm": 10.0, "depth_mm": 5.0},
        ),
    ],
)
def test_bore_containment_overlap_and_identity_are_fail_closed(bores):
    with pytest.raises(ValidationError):
        CylindricalHubSpecification(
            generated_part_id="hub",
            outer_diameter_mm=30.0,
            length_mm=10.0,
            bores=bores,
            inputs=(),
            field_bindings=(),
        )


@pytest.mark.parametrize("value", [True, 1, (1.0, 0.0, 0.0), math.inf, math.nan])
def test_generated_authority_input_accepts_only_finite_float_scalars(value):
    with pytest.raises(ValidationError):
        GeneratedAuthorityInput(
            input_id="bad",
            role="dimension",
            source_kind="design_selection",
            locator=_selection_locator("bad", 1.0),
            value=value,
            value_hash=_value_hash(1.0),
        )


def test_field_slots_are_exported_from_models_package():
    from mechcad_harness.models import FIELD_SLOTS

    assert "shaft.diameter_mm" in FIELD_SLOTS


@pytest.mark.parametrize(
    ("rule", "source_slots"),
    [
        ("generated-shaft-interface@1", ("frame.length_mm", "frame.width_mm")),
        ("generated-hub-interface@1", ("hub.bore:x.diameter_mm", "hub.bore:y.depth_mm")),
        ("generated-frame-faces@1", ("frame.length_mm", "frame.width_mm")),
    ],
)
def test_standalone_interface_derivations_enforce_rule_specific_source_slots(rule, source_slots):
    from mechcad_harness.models import GeneratedInterfaceDerivation

    with pytest.raises(ValidationError):
        GeneratedInterfaceDerivation(rule=rule, source_slots=source_slots)


def test_standalone_rotational_interface_enforces_rule_id_axis_and_mouth_contracts():
    with pytest.raises(ValidationError):
        GeneratedRotationalInterface(
            interface_id="shaft:face:+x",
            axis_point=(0.0, 0.0, 0.0),
            axis_direction=(0.0, 0.0, 1.0),
            nominal_diameter_mm=10.0,
            usable_engagement_length_mm=40.0,
            derivation=GeneratedInterfaceDerivation(
                rule="generated-shaft-interface@1",
                source_slots=("shaft.diameter_mm", "shaft.length_mm"),
            ),
        )

    with pytest.raises(ValidationError):
        GeneratedRotationalInterface(
            interface_id="shaft:shaft",
            axis_point=(1.0, 0.0, 0.0),
            axis_direction=(0.0, 0.0, 1.0),
            nominal_diameter_mm=10.0,
            usable_engagement_length_mm=40.0,
            derivation=GeneratedInterfaceDerivation(
                rule="generated-shaft-interface@1",
                source_slots=("shaft.diameter_mm", "shaft.length_mm"),
            ),
        )

    with pytest.raises(ValidationError):
        GeneratedRotationalInterface(
            interface_id="hub:bore:input:near",
            axis_point=(0.0, 0.0, 0.0),
            axis_direction=(0.0, 0.0, 1.0),
            nominal_diameter_mm=10.0,
            usable_engagement_length_mm=25.0,
            derivation=GeneratedInterfaceDerivation(
                rule="generated-hub-interface@1",
                source_slots=(
                    "hub.bore:other.diameter_mm",
                    "hub.bore:other.depth_mm",
                ),
            ),
        )


def test_standalone_attachment_interface_enforces_face_rule_normal_and_plane():
    with pytest.raises(ValidationError):
        GeneratedAttachmentFaceInterface(
            interface_id="frame:face:+x",
            plane_point=(60.0, 10.0, 5.0),
            outward_normal=(0.0, 1.0, 0.0),
            derivation=GeneratedInterfaceDerivation(
                rule="generated-frame-faces@1",
                source_slots=("frame.length_mm", "frame.width_mm", "frame.height_mm"),
            ),
        )

    with pytest.raises(ValidationError):
        GeneratedAttachmentFaceInterface(
            interface_id="frame:face:-x",
            plane_point=(1.0, 10.0, 5.0),
            outward_normal=(-1.0, 0.0, 0.0),
            derivation=GeneratedInterfaceDerivation(
                rule="generated-frame-faces@1",
                source_slots=("frame.length_mm", "frame.width_mm", "frame.height_mm"),
            ),
        )


def test_standalone_reference_frame_enforces_frame_identity_contract():
    derivation = GeneratedInterfaceDerivation(
        rule="generated-shaft-interface@1",
        source_slots=("shaft.diameter_mm", "shaft.length_mm"),
    )
    with pytest.raises(ValidationError):
        GeneratedReferenceFrame(
            frame_id="shaft:not-frame",
            origin=(0.0, 0.0, 0.0),
            orientation=(1.0, 0.0, 0.0, 0.0),
            derivation=derivation,
        )
    with pytest.raises(ValidationError):
        GeneratedReferenceFrame(
            frame_id="shaft:frame",
            origin=(1.0, 0.0, 0.0),
            orientation=(1.0, 0.0, 0.0, 0.0),
            derivation=derivation,
        )


def test_frame_face_convention_is_exact_and_replayable():
    frame = RectangularFrameMemberSpecification(
        generated_part_id="frame",
        length_mm=60.0,
        width_mm=20.0,
        height_mm=10.0,
        inputs=(_input("l", 60.0), _input("w", 20.0), _input("h", 10.0)),
        field_bindings=(
            _direct("frame.length_mm", "l", 60.0),
            _direct("frame.width_mm", "w", 20.0),
            _direct("frame.height_mm", "h", 10.0),
        ),
    )
    expected = {
        "frame:face:-x": ((0.0, 10.0, 5.0), (-1.0, 0.0, 0.0)),
        "frame:face:+x": ((60.0, 10.0, 5.0), (1.0, 0.0, 0.0)),
        "frame:face:-y": ((30.0, 0.0, 5.0), (0.0, -1.0, 0.0)),
        "frame:face:+y": ((30.0, 20.0, 5.0), (0.0, 1.0, 0.0)),
        "frame:face:-z": ((30.0, 10.0, 0.0), (0.0, 0.0, -1.0)),
        "frame:face:+z": ((30.0, 10.0, 10.0), (0.0, 0.0, 1.0)),
    }
    assert all(isinstance(interface, GeneratedAttachmentFaceInterface) for interface in frame.interfaces)
    assert {
        interface.interface_id: (interface.plane_point, interface.outward_normal)
        for interface in frame.interfaces
    } == expected
    assert tuple(derive_frame_interfaces(frame)) == frame.interfaces


def test_geometry_definition_identities_include_binding_graph_not_only_inputs():
    direct = _shaft()
    relation_binding = GeneratedPartFieldBinding(
        field_slot="hub.bore:x.diameter_mm",
        source={"rule_id": "hub-bore-from-supplied-shaft@1", "input_ids": ["diameter"]},
        field_value_hash=_value_hash(10.0),
    )
    from types import SimpleNamespace

    alternate = SimpleNamespace(inputs=direct.inputs, field_bindings=(relation_binding,))
    assert set(generated_geometry_definition_identities(direct)) != set(
        generated_geometry_definition_identities(alternate)
    )


def _candidate_generated_specification(**overrides):
    values = {
        "schema_version": "component-specification@3",
        "component_type": "shaft",
        "source_identity": "generated:shaft",
        "interfaces": ("shaft:shaft",),
        "generated_part": _shaft(),
    }
    values.update(overrides)
    from mechcad_harness.candidates.models import ComponentSpecificationSnapshot

    return ComponentSpecificationSnapshot(**values)


def _canonical_generated_specification(**overrides):
    values = {
        "schema_version": "canonical-component-specification@3",
        "component_type": "shaft",
        "source_identity": "generated:shaft",
        "interfaces": ("shaft:shaft",),
        "generated_part": _shaft(),
    }
    values.update(overrides)
    from mechcad_harness.models import CanonicalComponentSpecification

    return CanonicalComponentSpecification(**values)


@pytest.mark.parametrize(
    "factory",
    [_candidate_generated_specification, _canonical_generated_specification],
)
def test_component_specification_at_3_requires_a_generated_part(factory):
    with pytest.raises(ValidationError, match="generated_part"):
        factory(generated_part=None)


@pytest.mark.parametrize(
    ("factory", "schema_version"),
    [
        (_candidate_generated_specification, "component-specification@1"),
        (_candidate_generated_specification, "component-specification@2"),
        (_canonical_generated_specification, "canonical-component-specification@1"),
        (_canonical_generated_specification, "canonical-component-specification@2"),
    ],
)
def test_legacy_component_specification_versions_reject_generated_parts(
    factory, schema_version
):
    with pytest.raises(ValidationError, match="generated_part"):
        factory(schema_version=schema_version)


@pytest.mark.parametrize(
    "factory",
    [_candidate_generated_specification, _canonical_generated_specification],
)
def test_component_specification_at_3_rejects_supplied_geometry_and_m13_records(factory):
    with pytest.raises(ValidationError, match="generated"):
        factory(geometry_source={
            "artifact_id": "ART-1",
            "artifact_hash": "sha256:" + "1" * 64,
            "source_identity": "source:geometry",
        })

    with pytest.raises(ValidationError):
        factory(supplied_reference_frames=(object(),))


@pytest.mark.parametrize(
    "factory",
    [_candidate_generated_specification, _canonical_generated_specification],
)
def test_component_specification_at_3_serialization_and_hash_are_deterministic(factory):
    first = factory()
    second = factory(generated_part=_shaft(bindings=tuple(reversed(_shaft().field_bindings))))

    assert first.specification_hash == second.specification_hash
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.model_dump_json() == second.model_dump_json()
    assert first.model_dump(mode="json")["generated_part"]["generated_part_hash"].startswith(
        "sha256:"
    )


@pytest.mark.parametrize(
    "interfaces",
    [(), ("shaft:shaft", "shaft:shaft"), ("shaft:frame",)],
)
@pytest.mark.parametrize(
    "factory",
    [_candidate_generated_specification, _canonical_generated_specification],
)
def test_component_specification_at_3_requires_exactly_the_active_generated_registry(
    factory, interfaces
):
    with pytest.raises(ValidationError, match="generated interface registry|generated interface IDs"):
        factory(interfaces=interfaces)


@pytest.mark.parametrize(
    "factory",
    [_candidate_generated_specification, _canonical_generated_specification],
)
def test_component_specification_at_3_accepts_active_interfaces_but_not_reference_frame_endpoint(
    factory,
):
    specification = factory(interfaces=("shaft:shaft",))
    assert specification.interfaces == ("shaft:shaft",)
    assert specification.generated_part.reference_frame.frame_id == "shaft:frame"
    assert specification.generated_part.reference_frame.frame_id not in specification.interfaces
