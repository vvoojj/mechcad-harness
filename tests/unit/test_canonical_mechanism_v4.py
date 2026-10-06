from __future__ import annotations

from hashlib import sha256

import pytest

from mechcad_harness.models import (
    CanonicalPlacement,
    CanonicalPlacementOrigin,
    CanonicalComponentSpecification,
    CanonicalAcceptedDesignChoice,
    CanonicalGeometrySourceReference,
    CanonicalPhysicalComponent,
    CanonicalPhysicalMechanism,
    CanonicalPhysicalRevoluteJointBinding,
    physical_kinematic_root_hash,
)
from mechcad_harness.models.semantic_component import (
    bind_component_specification_semantic_identity,
)
from mechcad_harness.models.physical_mechanism import (
    canonical_physical_mechanism_hash_payload_v4,
)
from mechcad_harness.step_content_identity import step_content_identity_v1

from test_m13_3_canonical_mechanism_v3 import _mechanism_v3


_STEP_TEMPLATE = (
    "ISO-10303-21;\nHEADER;\n"
    "FILE_NAME('canonical.step','{timestamp}',('author'),('org'),('pre'),('sys'),'');\n"
    "FILE_SCHEMA(('AUTOMOTIVE_DESIGN_CC2'));\nENDSEC;\nDATA;\n"
    "#1=PRODUCT('canonical');\nENDSEC;\nEND-ISO-10303-21;\n"
)


def _mechanism_at4(*, variant: str = "A", promotion_provenance=None):
    base = _mechanism_v3()
    step = _STEP_TEMPLATE.format(
        timestamp=(
            "2026-09-22T12:34:56"
            if variant == "A"
            else "2027-01-02T03:04:05"
        )
    ).encode()
    raw_hash = "sha256:" + sha256(step).hexdigest()
    content_hash = step_content_identity_v1(step).content_hash
    identities = {
        "source:mount@1": (f"ART-MOUNT-{variant}", "source:mount@1"),
        "source:shaft@1": (f"ART-SHAFT-{variant}", "source:shaft@1"),
    }
    context = {
        (
            artifact_id,
            raw_hash,
            source_identity,
            "step",
            None,
        ): {"algorithm": "step-content-identity@1", "content_hash": content_hash}
        for artifact_id, source_identity in identities.values()
    }

    bound_specs = []
    old_spec_hash_to_new = {}
    semantic_ref_hash_by_source = {}
    for spec in base.component_specifications:
        artifact_id, source_identity = identities[spec.source_identity]
        payload = spec.model_dump(mode="python") | {
            "schema_version": "canonical-component-specification@4",
            "geometry_source": CanonicalGeometrySourceReference(
                artifact_id=artifact_id,
                artifact_hash=raw_hash,
                source_identity=source_identity,
                content_identity=content_hash,
                content_identity_algorithm="step-content-identity@1",
            ),
            "specification_hash": "pending",
        }
        at4 = CanonicalComponentSpecification.model_validate(payload)
        bound = bind_component_specification_semantic_identity(at4, context)
        bound_specs.append(bound)
        old_spec_hash_to_new[spec.specification_hash] = bound.specification_hash
        semantic_ref_hash_by_source[source_identity] = bound.geometry_source.semantic_reference_hash

    components = tuple(
        CanonicalPhysicalComponent.model_validate(
            component.model_dump(mode="python")
            | {
                "specification_hash": old_spec_hash_to_new[component.specification_hash],
                "placement_id": (
                    "placement-instance-child"
                    if component.instance_id == "instance-child"
                    else None
                ),
                "component_hash": "pending",
            }
        )
        for component in base.components
    )
    joints = []
    for joint in base.physical_revolute_joint_bindings:
        axis = joint.axis_source
        specification = next(
            spec
            for spec in bound_specs
            if spec.source_identity == "source:mount@1"
        )
        semantic_axis = type(axis).model_validate(
            axis.model_dump(mode="python")
            | {
                "specification_hash": specification.specification_hash,
                "geometry_reference_hash": specification.geometry_source.semantic_reference_hash,
                "source_hash": "pending",
            }
        )
        joints.append(
            CanonicalPhysicalRevoluteJointBinding.model_validate(
                joint.model_dump(mode="python")
                | {"axis_source": semantic_axis, "binding_hash": "pending"}
            )
        )

    return CanonicalPhysicalMechanism.model_validate(
        base.model_dump(mode="python")
        | {
            "schema_version": "canonical-physical-mechanism@4",
            "component_specifications": tuple(bound_specs),
            "components": components,
            "accepted_design_choices": (
                CanonicalAcceptedDesignChoice(
                    key="drive-choice",
                    value="direct",
                    origin="explicit_policy_assumption",
                    provenance="policy:drive@1",
                    source_identities=("candidate:design-variable:drive-choice",),
                ),
            ),
            "placements": (
                CanonicalPlacement(
                    placement_id="placement-instance-child",
                    instance_id="instance-child",
                    origin=CanonicalPlacementOrigin.ACCEPTED_INTERFACE,
                    input_identities=(f"ART-SHAFT-{variant}",),
                    relation="coaxial-output-axis@1",
                    x_mm=20.0,
                    placement_hash="pending",
                ),
            ),
            "physical_revolute_joint_bindings": tuple(joints),
            "promotion_provenance": tuple(
                promotion_provenance
                if promotion_provenance is not None
                else base.promotion_provenance
            ),
            "mechanism_hash": "pending",
        }
    )


def test_mechanism_at4_has_exact_versioned_wire_shape_and_hash():
    mechanism = _mechanism_at4()
    wire = mechanism.model_dump(mode="json")

    assert mechanism.schema_version == "canonical-physical-mechanism@4"
    assert all(
        spec.schema_version == "canonical-component-specification@4"
        for spec in mechanism.component_specifications
    )
    assert mechanism.kinematic_root_binding_hash == physical_kinematic_root_hash(
        mechanism.kinematic_root_physical_body_id
    )
    payload = canonical_physical_mechanism_hash_payload_v4(mechanism)
    assert "promotion_provenance" not in payload
    assert "ART-SHAFT-A" not in repr(payload)
    assert "artifact_hash" not in repr(payload)
    assert payload["kinematic_root_binding_hash"] == physical_kinematic_root_hash(
        mechanism.kinematic_root_physical_body_id
    )
    assert mechanism.mechanism_hash == (
        "sha256:c961184b10c3ca5975c8348654778cc3a13bdbc2359a818a8c4662331f0a2843"
    )
    assert mechanism.mechanism_hash.startswith("sha256:")
    assert "ART-MOUNT-A" not in repr(payload)
    assert "artifact_hash" not in repr(payload)
    assert CanonicalPhysicalMechanism.model_validate(wire) == mechanism


def test_mechanism_at4_is_invariant_to_raw_step_timestamp_and_artifact_id():
    first = _mechanism_at4(variant="A")
    second = _mechanism_at4(variant="B")

    assert first.component_specifications[0].geometry_source.artifact_id != (
        second.component_specifications[0].geometry_source.artifact_id
    )
    assert first.component_specifications[0].geometry_source.artifact_hash != (
        second.component_specifications[0].geometry_source.artifact_hash
    )
    assert first.component_specifications[0].specification_hash == (
        second.component_specifications[0].specification_hash
    )
    assert first.mechanism_hash == second.mechanism_hash


def test_mechanism_at4_excludes_promotion_provenance_but_tracks_engineering_changes():
    baseline = _mechanism_at4(promotion_provenance=("run:a", "task:x"))
    provenance_changed = _mechanism_at4(
        promotion_provenance=("run:b", "task:y", "path:/audit")
    )
    assert baseline.mechanism_hash == provenance_changed.mechanism_hash

    choice = baseline.accepted_design_choices[0]
    changed_choice = type(choice).model_validate(
        choice.model_dump(mode="python")
        | {"provenance": "run:other/task:other/path:/tmp/other", "choice_hash": "pending"}
    )
    provenance_only = CanonicalPhysicalMechanism.model_validate(
        baseline.model_dump(mode="python")
        | {
            "accepted_design_choices": (changed_choice,),
            "mechanism_hash": "pending",
        }
    )
    assert baseline.mechanism_hash == provenance_only.mechanism_hash

    changed = CanonicalPhysicalMechanism.model_validate(
        baseline.model_dump(mode="python")
        | {
            "name": "changed engineering mechanism",
            "mechanism_hash": "pending",
        }
    )
    assert changed.mechanism_hash != baseline.mechanism_hash


def test_mechanism_at4_rejects_non_at4_specification_and_forged_root_hash():
    mechanism = _mechanism_at4()
    legacy_spec = _mechanism_v3().component_specifications[0]
    with pytest.raises(ValueError, match="@4|specification"):
        CanonicalPhysicalMechanism.model_validate(
            mechanism.model_dump(mode="python")
            | {
                "component_specifications": (legacy_spec, *mechanism.component_specifications[1:]),
                "mechanism_hash": "pending",
            }
        )
    with pytest.raises(ValueError, match="root.*hash|root binding"):
        CanonicalPhysicalMechanism.model_validate(
            mechanism.model_dump(mode="python")
            | {
                "kinematic_root_binding_hash": "sha256:" + "f" * 64,
                "mechanism_hash": "pending",
            }
        )


def test_mechanism_at4_allows_empty_multi_joint_obligation_without_relaxing_v3():
    mechanism = _mechanism_at4()
    single_joint = CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="json")
        | {
            "multi_joint_verification_obligations": (),
            "mechanism_hash": "pending",
        }
    )
    assert single_joint.multi_joint_verification_obligations == ()
    assert single_joint.schema_version == "canonical-physical-mechanism@4"

    legacy = _mechanism_v3()
    with pytest.raises(ValueError, match="exactly one obligation"):
        CanonicalPhysicalMechanism.model_validate(
            legacy.model_dump(mode="python")
            | {
                "multi_joint_verification_obligations": (),
                "mechanism_hash": "pending",
            }
        )


def test_mechanism_at4_allows_no_multi_joint_obligation_and_v3_still_requires_one():
    mechanism = _mechanism_at4()
    single_joint = CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="json")
        | {
            "multi_joint_verification_obligations": (),
            "mechanism_hash": "pending",
        }
    )
    assert single_joint.multi_joint_verification_obligations == ()
    assert single_joint.mechanism_hash != mechanism.mechanism_hash

    legacy = _mechanism_v3()
    with pytest.raises(ValueError, match="exactly one obligation"):
        CanonicalPhysicalMechanism.model_validate(
            legacy.model_dump(mode="python")
            | {
                "multi_joint_verification_obligations": (),
                "mechanism_hash": "pending",
            }
        )


def test_legacy_mechanism_v3_hash_and_payload_remain_unchanged():
    mechanism = _mechanism_v3()
    wire = mechanism.model_dump(mode="json")

    assert mechanism.schema_version == "canonical-physical-mechanism@3"
    assert mechanism.mechanism_hash == _mechanism_v3().mechanism_hash
    assert wire["schema_version"] == "canonical-physical-mechanism@3"
    assert "promotion_provenance" in wire
