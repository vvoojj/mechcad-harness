from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.models import (
    CanonicalGeneratedPlacementDerivation,
    GeneratedAuthorityInput,
    GeneratedFrameRef,
    GeneratedAuthorityView,
    GeneratedInterfaceRef,
    GeneratedPlacementDerivation,
    GeneratedPlacementRotationInput,
    GeneratedReferenceFrame,
    GeneratedRotationalInterface,
    compose_poses,
    invert_pose,
    place_generated_target,
    placement_derivations_hash,
    pose_from_interface,
    resolve_placement_inputs,
)
from mechcad_harness.models.generated_part import selection_hash, value_hash
from mechcad_harness.models.generated_part import GeneratedInterfaceDerivation
from mechcad_harness.models.generated_placement import (
    _resolve_rotation_input,
    _rotation_aligning,
)
from mechcad_harness.models.quaternion import normalize_quaternion
from test_m13_geometry_materialization import _accepted_shaft_definition, _frame_for_source


HASH = "sha256:" + "a" * 64


def _interface(interface_id: str = "shaft") -> GeneratedInterfaceRef:
    return GeneratedInterfaceRef(interface_id=interface_id, interface_hash=HASH)


def _frame(frame_id: str = "frame") -> GeneratedFrameRef:
    return GeneratedFrameRef(frame_id=frame_id, frame_hash=HASH)


def _generated_rotational_interface(
    interface_id: str = "shaft:shaft",
) -> GeneratedRotationalInterface:
    return GeneratedRotationalInterface(
        interface_id=interface_id,
        axis_point=(0.0, 0.0, 0.0),
        axis_direction=(0.0, 0.0, 1.0),
        nominal_diameter_mm=10.0,
        usable_engagement_length_mm=40.0,
        derivation=GeneratedInterfaceDerivation(
            rule="generated-shaft-interface@1",
            source_slots=("shaft.diameter_mm", "shaft.length_mm"),
        ),
    )


def _rotation(
    angle: float = 90.0,
    *,
    name_form: str = "component_scoped",
    selection_key: str = "clocking",
) -> GeneratedPlacementRotationInput:
    return GeneratedPlacementRotationInput(
        rotation_id="clocking",
        axis_ref={"frame_role": "target", "axis": "+z"},
        angle_degrees=angle,
        provenance={
            "name_form": name_form,
            "selection_key": selection_key,
            "selection_hash": selection_hash(name_form, selection_key, angle),
        },
        value_hash=value_hash(angle),
    )


def _coaxial(**overrides) -> GeneratedPlacementDerivation:
    values = {
        "derivation_id": "place-shaft",
        "rule_id": "coaxial-generated-placement@1",
        "source_physical_instance_id": "motor-a",
        "source_interface_ref": _interface("motor-output"),
        "source_placement_ref": {"kind": "design_variable_placement"},
        "target_physical_instance_id": "shaft-a",
        "target_generated_interface_ref": _interface("shaft:shaft"),
    }
    values.update(overrides)
    return GeneratedPlacementDerivation(**values)


def _frame_derivation(**overrides) -> GeneratedPlacementDerivation:
    values = {
        "derivation_id": "place-frame",
        "rule_id": "frame-generated-placement@1",
        "source_physical_instance_id": "motor-a",
        "source_interface_ref": _interface("motor-face"),
        "source_frame_ref": _frame("motor-frame"),
        "source_placement_ref": {"kind": "design_variable_placement"},
        "target_physical_instance_id": "frame-a",
        "target_generated_frame_ref": _frame("frame-a:frame"),
        "rotation": _rotation(),
    }
    values.update(overrides)
    return GeneratedPlacementDerivation(**values)


def test_rotation_is_scalar_angle_only_and_reconstructs_canonical_quaternion():
    rotation = _rotation()
    assert rotation.input_hash.startswith("sha256:")
    assert normalize_quaternion((math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4))) == normalize_quaternion(
        (math.cos(math.radians(90) / 2), 0.0, 0.0, math.sin(math.radians(90) / 2))
    )
    with pytest.raises(ValidationError):
        GeneratedPlacementRotationInput(
            rotation_id="free",
            axis_ref={"frame_role": "target", "axis": "+z"},
            angle_degrees=(90.0, 0.0),
            provenance={
                "name_form": "component_scoped",
                "selection_key": "clocking",
                "selection_hash": selection_hash("component_scoped", "clocking", 90.0),
            },
            value_hash=value_hash(90.0),
        )


def test_derivation_rules_require_their_exact_rotation_and_frame_inputs():
    with pytest.raises(ValidationError):
        _coaxial(rotation=_rotation())

    with pytest.raises(ValidationError):
        _frame_derivation(rotation=None)


def test_rotation_resolves_exact_scalar_selection_in_target_owned_context():
    frame = GeneratedReferenceFrame(
        frame_id="frame-a:frame",
        origin=(0.0, 0.0, 0.0),
        orientation=(1.0, 0.0, 0.0, 0.0),
        derivation={
            "rule": "generated-shaft-interface@1",
            "source_slots": ("shaft.diameter_mm", "shaft.length_mm"),
        },
    )
    derivation = _frame_derivation(
        rotation=_rotation(
            15.0,
            name_form="instance_scoped",
            selection_key="placement.axial_offset_mm",
        ),
        target_generated_frame_ref=GeneratedFrameRef(
            frame_id=frame.frame_id, frame_hash=frame.frame_hash
        ),
    )
    view = GeneratedAuthorityView(
        design_selections={
            "frame-a.placement.axial_offset_mm": 15.0,
            "frame-b.placement.axial_offset_mm": 80.0,
        },
        reference_frames={"frame-a:frame": frame},
    )
    assert _resolve_rotation_input(derivation, view) == pytest.approx(
        _reconstructed_z_rotation(15.0)
    )
    with pytest.raises(ValueError):
        _resolve_rotation_input(
            derivation,
            GeneratedAuthorityView(design_selections={"clocking": 15.0}),
        )
    with pytest.raises(ValueError):
        _resolve_rotation_input(
            derivation.model_copy(update={"target_physical_instance_id": "frame-b"}),
            view,
        )


def test_canonical_optional_reference_pairs_round_trip_as_null_or_complete_pairs():
    derivation = CanonicalGeneratedPlacementDerivation(
        derivation_id="place-shaft",
        rule_id="coaxial-generated-placement@1",
        source_canonical_instance_id="motor-a",
        source_interface_id="motor:shaft",
        source_interface_hash=HASH,
        source_placement_ref={"kind": "design_variable_placement"},
        target_canonical_instance_id="shaft-a",
        target_generated_interface_id="shaft:shaft",
        target_generated_interface_hash=HASH,
        inputs=(),
    )
    assert CanonicalGeneratedPlacementDerivation.model_validate(
        derivation.model_dump(mode="json")
    ) == derivation
    assert derivation.source_frame_id is None
    assert derivation.source_frame_hash is None
    assert derivation.target_generated_frame_id is None
    assert derivation.target_generated_frame_hash is None


@pytest.mark.parametrize(
    "changes",
    [
        {"target_generated_interface_hash": None},
        {"source_frame_id": "motor:frame"},
        {"target_generated_frame_hash": HASH},
    ],
)
def test_canonical_optional_reference_ids_and_hashes_must_be_jointly_present(changes):
    values = {
        "derivation_id": "place-shaft",
        "rule_id": "coaxial-generated-placement@1",
        "source_canonical_instance_id": "motor-a",
        "source_interface_id": "motor:shaft",
        "source_interface_hash": HASH,
        "source_placement_ref": {"kind": "design_variable_placement"},
        "target_canonical_instance_id": "shaft-a",
        "target_generated_interface_id": "shaft:shaft",
        "target_generated_interface_hash": HASH,
        "inputs": (),
    }
    values.update(changes)
    with pytest.raises(ValidationError):
        CanonicalGeneratedPlacementDerivation(**values)


def test_rotation_requires_exact_generated_frame_id_and_hash_authority():
    frame = GeneratedReferenceFrame(
        frame_id="target:frame",
        origin=(0.0, 0.0, 0.0),
        orientation=(1.0, 0.0, 0.0, 0.0),
        derivation={
            "rule": "generated-shaft-interface@1",
            "source_slots": ("shaft.diameter_mm", "shaft.length_mm"),
        },
    )
    derivation = _frame_derivation(
        target_generated_frame_ref=GeneratedFrameRef(
            frame_id=frame.frame_id, frame_hash=frame.frame_hash
        ),
        rotation=_rotation(15.0),
    )
    view = GeneratedAuthorityView(
        design_selections={"clocking": 15.0},
        reference_frames={frame.frame_id: frame},
    )
    assert _resolve_rotation_input(derivation, view) == pytest.approx(
        _reconstructed_z_rotation(15.0)
    )
    with pytest.raises(ValueError):
        _resolve_rotation_input(
            derivation.model_copy(
                update={
                    "target_generated_frame_ref": GeneratedFrameRef(
                        frame_id=frame.frame_id, frame_hash="sha256:" + "b" * 64
                    )
                }
            ),
            view,
        )


def test_canonical_rotation_uses_canonical_frame_refs_and_target_context():
    source_frame = GeneratedReferenceFrame(
        frame_id="motor:frame",
        origin=(0.0, 0.0, 0.0),
        orientation=(1.0, 0.0, 0.0, 0.0),
        derivation={
            "rule": "generated-shaft-interface@1",
            "source_slots": ("shaft.diameter_mm", "shaft.length_mm"),
        },
    )
    target_frame = GeneratedReferenceFrame(
        frame_id="shaft:frame",
        origin=(0.0, 0.0, 0.0),
        orientation=(1.0, 0.0, 0.0, 0.0),
        derivation={
            "rule": "generated-shaft-interface@1",
            "source_slots": ("shaft.diameter_mm", "shaft.length_mm"),
        },
    )
    rotation = _rotation(
        15.0,
        name_form="instance_scoped",
        selection_key="clocking",
    )
    derivation = CanonicalGeneratedPlacementDerivation(
        derivation_id="place-frame",
        rule_id="frame-generated-placement@1",
        source_canonical_instance_id="motor-canonical",
        source_interface_id="motor:face",
        source_interface_hash=HASH,
        source_frame_id=source_frame.frame_id,
        source_frame_hash=source_frame.frame_hash,
        source_placement_ref={"kind": "design_variable_placement"},
        target_canonical_instance_id="shaft-canonical",
        target_generated_frame_id=target_frame.frame_id,
        target_generated_frame_hash=target_frame.frame_hash,
        inputs=(),
        rotation=rotation,
    )
    view = GeneratedAuthorityView(
        design_selections={"shaft-canonical.clocking": 15.0},
        reference_frames={
            source_frame.frame_id: source_frame,
            target_frame.frame_id: target_frame,
        },
    )

    assert _resolve_rotation_input(derivation, view) == pytest.approx(
        _reconstructed_z_rotation(15.0)
    )
    with pytest.raises(ValueError):
        _resolve_rotation_input(
            derivation.model_copy(update={"target_generated_frame_hash": "sha256:" + "b" * 64}),
            view,
        )


@pytest.mark.parametrize("canonical", [False, True])
def test_coaxial_resolution_requires_an_exact_typed_generated_rotational_interface(canonical):
    interface = _generated_rotational_interface()
    if canonical:
        derivation = CanonicalGeneratedPlacementDerivation(
            derivation_id="place-shaft",
            rule_id="coaxial-generated-placement@1",
            source_canonical_instance_id="motor-canonical",
            source_interface_id="motor:shaft",
            source_interface_hash=HASH,
            source_placement_ref={"kind": "design_variable_placement"},
            target_canonical_instance_id="shaft-canonical",
            target_generated_interface_id=interface.interface_id,
            target_generated_interface_hash=interface.interface_hash,
            inputs=(),
        )
    else:
        derivation = _coaxial(
            target_generated_interface_ref=GeneratedInterfaceRef(
                interface_id=interface.interface_id,
                interface_hash=interface.interface_hash,
            )
        )
    view = GeneratedAuthorityView(
        generated_interfaces={interface.interface_id: interface},
    )
    assert resolve_placement_inputs(derivation, view) == {}

    forged_view = GeneratedAuthorityView(
        generated_interfaces={interface.interface_id: _generated_rotational_interface("other:shaft")}
    )
    with pytest.raises(ValueError):
        resolve_placement_inputs(derivation, forged_view)


def test_placement_derivation_chains_require_instance_continuity():
    first = _coaxial(target_physical_instance_id="shaft-a")
    mismatched = _coaxial(
        derivation_id="place-hub",
        source_physical_instance_id="other-source",
        target_physical_instance_id="hub-a",
        source_placement_ref={"kind": "derivation", "derivation_id": "place-shaft"},
    )
    with pytest.raises(ValueError, match="continuity"):
        placement_derivations_hash((first, mismatched))

    canonical_first = CanonicalGeneratedPlacementDerivation(
        derivation_id="place-shaft",
        rule_id="coaxial-generated-placement@1",
        source_canonical_instance_id="motor-canonical",
        source_interface_id="motor:shaft",
        source_interface_hash=HASH,
        source_placement_ref={"kind": "design_variable_placement"},
        target_canonical_instance_id="shaft-canonical",
        target_generated_interface_id="shaft:shaft",
        target_generated_interface_hash=HASH,
        inputs=(),
    )
    canonical_values = canonical_first.model_dump(mode="json")
    canonical_values.update(
        {
            "derivation_id": "place-hub",
            "source_canonical_instance_id": "other-source",
            "target_canonical_instance_id": "hub-canonical",
            "source_placement_ref": {
                "kind": "derivation",
                "derivation_id": "place-shaft",
            },
            "derivation_hash": "pending",
        }
    )
    canonical_mismatched = CanonicalGeneratedPlacementDerivation(**canonical_values)
    with pytest.raises(ValueError, match="continuity"):
        placement_derivations_hash((canonical_first, canonical_mismatched))


def test_rotation_resolves_typed_supplied_frame_records_without_candidate_imports():
    supplied_frame = _frame_for_source(_accepted_shaft_definition().geometry)
    derivation = _frame_derivation(
        target_generated_frame_ref=GeneratedFrameRef(
            frame_id=supplied_frame.frame_id,
            frame_hash=supplied_frame.frame_hash,
        ),
        rotation=_rotation(15.0),
    )
    assert _resolve_rotation_input(
        derivation,
        GeneratedAuthorityView(
            design_selections={"clocking": 15.0},
            reference_frames={supplied_frame.frame_id: supplied_frame},
        ),
    ) == pytest.approx(_reconstructed_z_rotation(15.0))


def test_coaxial_applicability_accepts_only_generated_shaft_or_hub_bore_interfaces():
    assert _coaxial(
        target_generated_interface_ref=_interface("hub:bore:input:near")
    ).target_generated_interface_ref is not None
    with pytest.raises(ValidationError):
        _coaxial(target_generated_interface_ref=_interface("frame:face:+x"))
    with pytest.raises(ValidationError):
        _coaxial(target_generated_interface_ref=_interface("arbitrary-interface"))


def test_placement_numeric_inputs_are_design_selection_only_and_target_owned():
    input_record = GeneratedAuthorityInput(
        input_id="offset",
        role="axial_offset",
        source_kind="design_selection",
        locator={
            "name_form": "instance_scoped",
            "selection_key": "placement.axial_offset_mm",
            "selection_hash": selection_hash(
                "instance_scoped", "placement.axial_offset_mm", 2.5
            ),
        },
        value=2.5,
        value_hash=value_hash(2.5),
    )
    derivation = _coaxial(
        inputs=(input_record,),
        target_generated_interface_ref=GeneratedInterfaceRef(
            interface_id="shaft:shaft",
            interface_hash=_generated_rotational_interface("shaft:shaft").interface_hash,
        ),
    )
    assert resolve_placement_inputs(
        derivation,
        GeneratedAuthorityView(
            design_selections={"shaft-a.placement.axial_offset_mm": 2.5},
            generated_interfaces={
                "shaft:shaft": _generated_rotational_interface("shaft:shaft")
            },
        ),
    ) == {"offset": 2.5}

    with pytest.raises(ValidationError):
        _coaxial(
            inputs=(
                GeneratedAuthorityInput(
                    input_id="offset",
                    role="axial_offset",
                    source_kind="component_property",
                    locator={"property_key": "placement.offset_mm"},
                    value=2.5,
                    value_hash=value_hash(2.5),
                ),
            )
        )
    with pytest.raises(ValueError):
        _resolve_rotation_input(
            derivation,
            GeneratedAuthorityView(
                design_selections={"frame-a.placement.axial_offset_mm": 16.0}
            ),
        )


def _reconstructed_z_rotation(angle: float):
    half_angle = math.radians(angle) / 2.0
    return normalize_quaternion((math.cos(half_angle), 0.0, 0.0, math.sin(half_angle)))


def test_composition_and_inverse_match_rigid_pose_oracle():
    outer = CadRigidTransform(
        x_mm=10.0,
        y_mm=20.0,
        rotation_quaternion=(math.sqrt(0.5), 0, 0, math.sqrt(0.5)),
    )
    inner = CadRigidTransform(x_mm=3.0, y_mm=4.0)
    composed = compose_poses(outer, inner)
    assert composed.x_mm == pytest.approx(6.0)
    assert composed.y_mm == pytest.approx(23.0)
    identity = compose_poses(composed, invert_pose(composed))
    assert identity.x_mm == pytest.approx(0.0)
    assert identity.y_mm == pytest.approx(0.0)
    assert identity.z_mm == pytest.approx(0.0)
    assert identity.rotation_quaternion == pytest.approx(CadRigidTransform().rotation_quaternion)


def test_shortest_arc_alignment_maps_rotational_axis_to_local_positive_z():
    assert _rotation_aligning((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)) == pytest.approx(
        normalize_quaternion((math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0))
    )
    frame = GeneratedReferenceFrame(
        frame_id="motor:frame",
        origin=(0.0, 0.0, 0.0),
        orientation=(1.0, 0.0, 0.0, 0.0),
        derivation={
            "rule": "generated-shaft-interface@1",
            "source_slots": ("shaft.diameter_mm", "shaft.length_mm"),
        },
    )
    assert pose_from_interface(frame) == CadRigidTransform()


def test_placement_set_hash_is_order_independent_and_chaining_is_acyclic():
    first = _coaxial()
    second = _coaxial(
        derivation_id="place-hub",
        source_physical_instance_id="shaft-a",
        target_physical_instance_id="hub-a",
        source_placement_ref={"kind": "derivation", "derivation_id": "place-shaft"},
    )
    assert placement_derivations_hash((first, second)) == placement_derivations_hash((second, first))
    cycle = _coaxial(
        derivation_id="place-hub",
        source_physical_instance_id="shaft-a",
        target_physical_instance_id="hub-a",
        source_placement_ref={"kind": "derivation", "derivation_id": "place-shaft"},
    )
    first_cycle = _coaxial(
        source_physical_instance_id="hub-a",
        source_placement_ref={"kind": "derivation", "derivation_id": "place-hub"},
    )
    with pytest.raises(ValueError, match="acyclic"):
        placement_derivations_hash((first_cycle, cycle))


def test_axisymmetric_placement_does_not_accept_rotation():
    with pytest.raises(ValidationError):
        _coaxial(rotation=_rotation())


def test_place_generated_target_applies_offset_and_explicit_rotation():
    result = place_generated_target(
        "frame-generated-placement@1",
        CadRigidTransform(x_mm=10.0),
        CadRigidTransform(),
        2.0,
        normalize_quaternion(
            (math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4))
        ),
    )
    assert result.x_mm == pytest.approx(10.0)
    assert result.z_mm == pytest.approx(2.0)
    assert result.rotation_quaternion == pytest.approx(
        normalize_quaternion((math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4)))
    )
