from __future__ import annotations

import pytest
from pydantic import ValidationError

from mechcad_harness.models import (
    CanonicalAcceptedDesignChoice,
    CanonicalComponentProperty,
    CanonicalComponentPropertyAvailability,
    CanonicalComponentPropertyAuthority,
    CanonicalComponentSpecification,
    CanonicalConnectionMeaning,
    CanonicalGeometryFidelity,
    CanonicalGeometrySourceReference,
    CanonicalJointPhysicalBinding,
    CanonicalM10VerificationObligation,
    CanonicalPhysicalComponent,
    CanonicalPhysicalMechanism,
    CanonicalPhysicalPairRequirement,
    CanonicalPlacement,
    CanonicalPlacementOrigin,
    CanonicalDesignChoiceOrigin,
    CanonicalMechanicalConnection,
    CanonicalMechanicalConnectionKind,
)


def _mechanism() -> CanonicalPhysicalMechanism:
    specification = CanonicalComponentSpecification(
        component_type="shaft",
        source_identity="drawing:shaft@1",
        properties=(
            CanonicalComponentProperty(
                key="diameter",
                availability=CanonicalComponentPropertyAvailability.AVAILABLE,
                normalized_value=12.0,
                canonical_unit="mm",
                source_identity="drawing:shaft@1",
                authority=CanonicalComponentPropertyAuthority.USER_DECLARED,
            ),
            CanonicalComponentProperty(
                key="material",
                availability=CanonicalComponentPropertyAvailability.MISSING,
                source_identity="drawing:shaft@1",
                authority=CanonicalComponentPropertyAuthority.USER_DECLARED,
            ),
            CanonicalComponentProperty(
                key="dynamic_load_rating",
                availability=CanonicalComponentPropertyAvailability.NOT_APPLICABLE,
                source_identity="drawing:shaft@1",
                authority=CanonicalComponentPropertyAuthority.USER_DECLARED,
                applicability_context="shaft is not a bearing",
            ),
        ),
        interfaces=("input", "output"),
        geometry_source=CanonicalGeometrySourceReference(
            artifact_id="ART-shaft",
            artifact_hash="sha256:" + "4" * 64,
            source_identity="step:shaft@1",
        ),
    )
    mount_specification = CanonicalComponentSpecification(
        component_type="mount",
        source_identity="drawing:mount@1",
        interfaces=("output-frame",),
    )
    return CanonicalPhysicalMechanism(
        id="PM-1",
        name="rotary output",
        component_specifications=(specification, mount_specification),
        components=(
            CanonicalPhysicalComponent(
                instance_id="shaft-1",
                specification_hash=specification.specification_hash,
                role="shaft",
                interfaces=("input", "output"),
                placement_id="placement-shaft-1",
            ),
            CanonicalPhysicalComponent(
                instance_id="mount-1",
                specification_hash=mount_specification.specification_hash,
                role="mount_or_support",
                interfaces=("output-frame",),
            ),
        ),
        accepted_design_choices=(
            CanonicalAcceptedDesignChoice(
                key="use_policy_default",
                value=False,
                origin=CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION,
                provenance="policy:mounting@1",
            ),
        ),
        placements=(
            CanonicalPlacement(
                placement_id="placement-shaft-1",
                instance_id="shaft-1",
                origin=CanonicalPlacementOrigin.ACCEPTED_INTERFACE,
                input_identities=("interface:output@1",),
                relation="coaxial-output-axis@1",
            ),
        ),
        connections=(
            CanonicalMechanicalConnection(
                connection_id="shaft-to-mount",
                kind=CanonicalMechanicalConnectionKind.FIXED_ATTACHMENT,
                from_instance_id="shaft-1",
                from_interface_id="output",
                to_instance_id="mount-1",
                to_interface_id="output-frame",
                meanings=(CanonicalConnectionMeaning.CAD_PLACEMENT_MATING_INTENT,),
            ),
        ),
        joint_bindings=(
            CanonicalJointPhysicalBinding(
                joint_id="joint-output",
                expected_parent_instance_id="mount-1",
                expected_child_instance_id="shaft-1",
                axis_origin_x_mm=0.0,
                axis_origin_y_mm=0.0,
                axis_origin_z_mm=0.0,
                axis_direction_x=0.0,
                axis_direction_y=0.0,
                axis_direction_z=1.0,
                axis_frame_reference="mount-1:output-frame",
                semantic_hash="sha256:" + "1" * 64,
                semantic_version="m10-joint-semantics@1",
            ),
        ),
        m10_obligations=(
            CanonicalM10VerificationObligation(
                joint_semantic_key="joint-output",
                angle_interval_deg=(0.0, 360.0),
                required_clearance_mm=1.0,
                physical_pair_requirements=(
                    CanonicalPhysicalPairRequirement(
                        requirement_key="shaft-to-mount",
                        first_instance_id="shaft-1",
                        first_interface_id="output",
                        second_instance_id="mount-1",
                        second_interface_id="output-frame",
                    ),
                ),
                fidelity_requirements=(("shaft-1", CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY),),
                required_home_check_semantics=("check-home-clearance",),
                bounded_limitations=("internal bearing motion is outside scope",),
            ),
        ),
        promotion_provenance=("promotion-input:selection@1",),
    )


def test_complete_canonical_mechanism_round_trips_json_and_hashes_semantics():
    mechanism = _mechanism()

    assert mechanism.mechanism_hash.startswith("sha256:")
    assert mechanism.components[0].component_hash.startswith("sha256:")
    assert mechanism.m10_obligations[0].obligation_hash.startswith("sha256:")
    assert CanonicalPhysicalMechanism.model_validate(mechanism.model_dump(mode="json")) == mechanism


def test_canonical_mechanism_rejects_duplicate_component_ids():
    mechanism = _mechanism()
    with pytest.raises(ValueError, match="component IDs must be unique"):
        CanonicalPhysicalMechanism(
            **mechanism.model_dump(mode="python")
            | {
                "components": (mechanism.components[0], mechanism.components[0]),
                "mechanism_hash": "pending",
            }
        )


def test_canonical_mechanism_requires_complete_nested_values():
    with pytest.raises(ValidationError):
        CanonicalPhysicalMechanism(
            id="PM-1",
            name="rotary output",
            component_specifications=(),
            components=(),
        )


def test_missing_and_not_applicable_properties_remain_distinct_and_value_free():
    properties = _mechanism().component_specifications[0].properties
    assert properties[1].availability is CanonicalComponentPropertyAvailability.MISSING
    assert properties[1].normalized_value is None
    assert properties[2].availability is CanonicalComponentPropertyAvailability.NOT_APPLICABLE
    assert properties[2].normalized_value is None
    assert properties[2].applicability_context == "shaft is not a bearing"


def test_policy_origin_choice_preserves_false_value_and_explicit_provenance():
    choice = _mechanism().accepted_design_choices[0]
    assert choice.value is False
    assert choice.origin is CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION
    assert choice.provenance == "policy:mounting@1"


def test_m10_obligation_rejects_candidate_cad_result_and_inventory_fields():
    obligation = _mechanism().m10_obligations[0]
    payload = obligation.model_dump(mode="python") | {
        "cad_request_hash": "sha256:" + "2" * 64,
        "m10_result_hash": "sha256:" + "3" * 64,
        "pair_inventory": (),
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CanonicalM10VerificationObligation(**payload)


def test_canonical_models_are_frozen_and_strict():
    mechanism = _mechanism()
    with pytest.raises(ValidationError):
        CanonicalPhysicalMechanism(
            **mechanism.model_dump(mode="python") | {"unexpected": "value"}
        )
    with pytest.raises((TypeError, ValidationError)):
        mechanism.name = "changed"


def _rebuild(mechanism: CanonicalPhysicalMechanism, **updates) -> CanonicalPhysicalMechanism:
    return CanonicalPhysicalMechanism(
        **mechanism.model_dump(mode="python") | updates | {"mechanism_hash": "pending"}
    )


def test_mechanism_rejects_dangling_placement_and_connection_interface_references():
    mechanism = _mechanism()
    dangling_component = mechanism.components[0].model_copy(
        update={"placement_id": "missing-placement", "component_hash": "pending"}
    )
    with pytest.raises(ValueError, match="placement reference"):
        _rebuild(mechanism, components=(dangling_component, *mechanism.components[1:]))

    dangling_connection = mechanism.connections[0].model_copy(
        update={"from_interface_id": "missing-interface", "connection_hash": "pending"}
    )
    with pytest.raises(ValueError, match="interface"):
        _rebuild(mechanism, connections=(dangling_connection,))


def test_mechanism_rejects_dangling_pair_and_fidelity_references():
    mechanism = _mechanism()
    obligation = mechanism.m10_obligations[0]
    dangling_pair = obligation.physical_pair_requirements[0].model_copy(
        update={"second_interface_id": "missing-interface", "requirement_hash": "pending"}
    )
    dangling_pair_obligation = obligation.model_copy(
        update={
            "physical_pair_requirements": (dangling_pair,),
            "obligation_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="pair requirement"):
        _rebuild(mechanism, m10_obligations=(dangling_pair_obligation,))

    dangling_fidelity_obligation = obligation.model_copy(
        update={
            "fidelity_requirements": (("missing-component", CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY),),
            "obligation_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="fidelity"):
        _rebuild(mechanism, m10_obligations=(dangling_fidelity_obligation,))


def test_mechanism_rejects_obligation_for_unknown_joint_binding():
    mechanism = _mechanism()
    obligation = mechanism.m10_obligations[0].model_copy(
        update={"joint_semantic_key": "missing-joint", "obligation_hash": "pending"}
    )
    with pytest.raises(ValueError, match="joint semantic key"):
        _rebuild(mechanism, m10_obligations=(obligation,))


def test_reference_hashes_must_be_bound_sha256_identities():
    mechanism = _mechanism()
    component_values = mechanism.components[0].model_dump(mode="python")
    component_values.update(specification_hash="pending", component_hash="pending")
    with pytest.raises(ValidationError, match="sha256"):
        CanonicalPhysicalComponent(**component_values)

    binding_values = mechanism.joint_bindings[0].model_dump(mode="python")
    binding_values.update(semantic_hash="pending", binding_hash="pending")
    with pytest.raises(ValidationError, match="sha256"):
        CanonicalJointPhysicalBinding(**binding_values)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("canonical_unit", " "),
        ("applicability_context", " "),
        ("conversion_provenance", " "),
    ),
)
def test_component_property_rejects_blank_supplied_semantic_strings(field, value):
    property_values = _mechanism().component_specifications[0].properties[0].model_dump(
        mode="python"
    )
    property_values.update({field: value, "property_hash": "pending"})
    with pytest.raises(ValidationError):
        CanonicalComponentProperty(**property_values)


def test_mechanism_rejects_blank_promotion_provenance_entry():
    with pytest.raises(ValidationError, match="provenance"):
        _rebuild(_mechanism(), promotion_provenance=(" ",))
