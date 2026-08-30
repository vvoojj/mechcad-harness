from __future__ import annotations

import pytest

from mechcad_harness.candidates import PromotableMechanismProjection
from mechcad_harness.candidates import CandidatePromotionCompiler
from mechcad_harness.models import (
    CanonicalAcceptedDesignChoice,
    CanonicalComponentProperty,
    CanonicalComponentPropertyAuthority,
    CanonicalComponentSpecification,
    CanonicalGeometrySourceReference,
    CanonicalJointPhysicalBinding,
    CanonicalM10VerificationObligation,
    CanonicalMechanicalConnection,
    CanonicalPhysicalMechanism,
    CanonicalPlacement,
)

from test_m12_canonical_physical_mechanism import _mechanism


def _projection(mechanism: CanonicalPhysicalMechanism) -> PromotableMechanismProjection:
    return PromotableMechanismProjection.model_validate(
        {
            "canonical_target_mechanism_id": mechanism.id,
            "canonical_instance_ids": tuple(component.instance_id for component in mechanism.components),
            "component_specifications": mechanism.component_specifications,
            "components": mechanism.components,
            "accepted_design_choices": mechanism.accepted_design_choices,
            "placements": mechanism.placements,
            "connections": mechanism.connections,
            "joint_bindings": mechanism.joint_bindings,
            "m10_obligations": mechanism.m10_obligations,
            "mapping_identities": ("mapping:shaft-1", "mapping:mount-1"),
            "projection_hash": "pending",
        }
    )


def _changed(model, identity_field: str, **updates):
    return type(model).model_validate(
        model.model_dump(mode="json") | updates | {identity_field: "pending"}
    )


def _changed_projection(projection: PromotableMechanismProjection, field: str, value):
    return PromotableMechanismProjection.model_validate(
        projection.model_dump(mode="json") | {field: value, "projection_hash": "pending"}
    )


def test_identical_promoted_semantics_have_identical_projection_hashes():
    first = _projection(_mechanism())
    second = _projection(
        CanonicalPhysicalMechanism.model_validate(_mechanism().model_dump(mode="json"))
    )

    assert first.projection_hash == second.projection_hash


def test_projection_mapping_identities_are_derivable_from_canonical_state_only():
    mechanism = _mechanism()

    projection = CandidatePromotionCompiler._projection(mechanism)
    reloaded = PromotableMechanismProjection.model_validate(
        projection.model_dump(mode="json")
    )

    assert projection.mapping_identities == tuple(
        component.instance_id for component in mechanism.components
    )
    assert reloaded.projection_hash == projection.projection_hash


@pytest.mark.parametrize("semantic_change", [
    "property_authority",
    "accepted_choice",
    "placement_input",
    "connection",
    "geometry_source",
    "joint_binding",
    "obligation",
])
def test_each_promoted_semantic_change_changes_projection_hash(semantic_change):
    baseline_mechanism = _mechanism()
    baseline = _projection(baseline_mechanism)

    if semantic_change == "property_authority":
        specification = baseline_mechanism.component_specifications[0]
        property_value = _changed(
            specification.properties[0],
            "property_hash",
            authority=CanonicalComponentPropertyAuthority.MEASURED_LOCAL,
        )
        changed_specification = _changed(
            specification,
            "specification_hash",
            properties=(property_value, *specification.properties[1:]),
        )
        changed = _changed_projection(
            baseline,
            "component_specifications",
            (changed_specification, *baseline.component_specifications[1:]),
        )
    elif semantic_change == "accepted_choice":
        choice = _changed(
            baseline.accepted_design_choices[0], "choice_hash", value=True
        )
        changed = _changed_projection(baseline, "accepted_design_choices", (choice,))
    elif semantic_change == "placement_input":
        placement = _changed(
            baseline.placements[0],
            "placement_hash",
            input_identities=("interface:changed-output@1",),
        )
        changed = _changed_projection(baseline, "placements", (placement,))
    elif semantic_change == "connection":
        connection = _changed(
            baseline.connections[0],
            "connection_hash",
            meanings=(),
        )
        changed = _changed_projection(baseline, "connections", (connection,))
    elif semantic_change == "geometry_source":
        specification = baseline_mechanism.component_specifications[0]
        source = _changed(
            specification.geometry_source,
            "reference_hash",
            artifact_hash="sha256:" + "5" * 64,
        )
        changed_specification = _changed(
            specification,
            "specification_hash",
            geometry_source=source,
        )
        changed = _changed_projection(
            baseline,
            "component_specifications",
            (changed_specification, *baseline.component_specifications[1:]),
        )
    elif semantic_change == "joint_binding":
        binding = _changed(
            baseline.joint_bindings[0],
            "binding_hash",
            semantic_version="m10-joint-semantics@2",
        )
        changed = _changed_projection(baseline, "joint_bindings", (binding,))
    else:
        obligation = _changed(
            baseline.m10_obligations[0], "obligation_hash", required_clearance_mm=2.0
        )
        changed = _changed_projection(baseline, "m10_obligations", (obligation,))

    assert changed.projection_hash != baseline.projection_hash


def test_projection_excludes_provenance_and_execution_payloads():
    projection = _projection(_mechanism())
    payload = projection.model_dump(mode="json")

    for excluded in (
        "candidate_hash",
        "evaluation_hash",
        "cad_request_hash",
        "m10_request_hash",
        "comparison_result_hash",
        "ranking",
        "run_id",
        "timestamp",
        "path",
    ):
        assert excluded not in payload

    with pytest.raises(ValueError, match="extra"):
        PromotableMechanismProjection.model_validate(payload | {"evaluation_hash": "x"})


def test_provenance_only_mechanism_changes_do_not_change_projection_hash():
    mechanism = _mechanism()
    baseline = _projection(mechanism)
    changed_provenance = CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="json")
        | {
            "promotion_provenance": ("historical:other-candidate",),
            "mechanism_hash": "pending",
        }
    )

    assert _projection(changed_provenance).projection_hash == baseline.projection_hash
