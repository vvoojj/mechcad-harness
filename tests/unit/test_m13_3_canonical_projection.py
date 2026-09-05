from __future__ import annotations

import json

import pytest

from mechcad_harness.candidates.models import (
    GeneratedReferenceFrameAxisSource,
    GeneratedRotationalInterfaceAxisSource,
    SuppliedReferenceFrameAxisSource,
    SuppliedRotationalInterfaceAxisSource,
)
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    TrustedSourceArtifact,
    _projection_from_mechanism,
    normalized_projection,
)
from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.models.physical_pair_policy import physical_pair_classification_set_hash

from test_m13_3_promotion import _promotion_chain


def test_multi_joint_canonical_projection_contains_only_rebound_authority(tmp_path):
    candidate, _, _, multi_request, _, request, manager, compiler = _promotion_chain(tmp_path)

    compilation = compiler.compile_multi_joint(
        manager.load_current_state(request.project_id), request
    )
    mechanism = compilation.canonical_mechanism
    mapping = {
        item.candidate_instance_id: item.canonical_instance_id
        for item in compilation.mapping
    }

    candidate_body = candidate.realization.physical_rigid_body_bindings[0]
    canonical_body = next(
        item
        for item in mechanism.physical_rigid_body_bindings
        if item.physical_body_id == candidate_body.physical_body_id
    )
    assert canonical_body.member_physical_instance_ids == tuple(
        sorted(mapping[item] for item in candidate_body.member_physical_instance_ids)
    )
    assert canonical_body.reference_physical_instance_id == mapping[
        candidate_body.reference_physical_instance_id
    ]
    assert canonical_body.binding_hash != candidate_body.binding_hash
    assert tuple(item.physical_body_id for item in mechanism.physical_rigid_body_bindings) == tuple(
        item.physical_body_id
        for item in candidate.realization.physical_rigid_body_bindings
    )
    assert mechanism.kinematic_root_physical_body_id == (
        candidate.realization.kinematic_root_physical_body_id
    )
    assert mechanism.kinematic_root_binding_hash == (
        candidate.realization.kinematic_root_binding_hash
    )

    candidate_joint = candidate.realization.physical_revolute_joint_bindings[0]
    canonical_joint = mechanism.physical_revolute_joint_bindings[0]
    assert canonical_joint.parent_physical_instance_id == mapping[
        candidate_joint.parent_physical_instance_id
    ]
    assert canonical_joint.child_physical_instance_id == mapping[
        candidate_joint.child_physical_instance_id
    ]
    assert canonical_joint.axis_source.source_physical_instance_id == mapping[
        candidate_joint.axis_source.source_physical_instance_id
    ]
    assert canonical_joint.axis_source.source_hash != candidate_joint.axis_source.source_hash
    assert canonical_joint.binding_hash != candidate_joint.binding_hash
    assert tuple(item.physical_joint_id for item in mechanism.physical_revolute_joint_bindings) == tuple(
        item.physical_joint_id
        for item in candidate.realization.physical_revolute_joint_bindings
    )
    assert physical_pair_classification_set_hash(
        mechanism.physical_pair_classification_bindings
    ) != physical_pair_classification_set_hash(
        candidate.realization.physical_pair_classification_bindings
    )
    candidate_pairs = {
        (item.first_physical_instance_id, item.second_physical_instance_id): item
        for item in candidate.realization.physical_pair_classification_bindings
    }
    canonical_pairs = {
        (item.first_physical_instance_id, item.second_physical_instance_id): item
        for item in mechanism.physical_pair_classification_bindings
    }
    for (first, second), pair in candidate_pairs.items():
        projected_pair = canonical_pairs[(mapping[first], mapping[second])]
        assert projected_pair.classification == pair.classification
        assert projected_pair.exclusion_reason == pair.exclusion_reason

    obligation = mechanism.multi_joint_verification_obligations[0]
    assert obligation.configuration_set == multi_request.scope.configuration_set
    assert obligation.volume_tolerance_mm3 == multi_request.scope.volume_tolerance_mm3
    assert obligation.distance_tolerance_mm == multi_request.scope.distance_tolerance_mm
    assert obligation.configuration_set_hash == multi_request.configuration_set_hash

    canonical_payload = json.dumps(mechanism.model_dump(mode="json"), sort_keys=True)
    assert candidate.candidate_hash not in canonical_payload
    assert request.request_hash not in canonical_payload
    assert multi_request.scope.scope_identity not in canonical_payload
    assert multi_request.m10_v2_request_hash not in canonical_payload
    assert candidate_joint.axis_source.source_hash not in canonical_payload
    assert candidate_joint.binding_hash not in canonical_payload

    store = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="canonical-projection-test"
    )
    trusted_sources = tuple(
        TrustedSourceArtifact.from_artifact(
            store.read_verified_in_project(
                specification.geometry_source.artifact_id,
                expected_hash=specification.geometry_source.artifact_hash,
            )[0]
        )
        for specification in mechanism.component_specifications
        if specification.geometry_source is not None
    )
    reconstruction = CanonicalMechanismReconstruction(
        project_id=request.project_id,
        revision=request.source_revision,
        state_hash=request.source_state_hash,
        canonical_mechanism=mechanism,
        trusted_source_references=trusted_sources,
        normalized_projection_hash=_projection_from_mechanism(mechanism).projection_hash,
    )
    projection = normalized_projection(reconstruction)
    assert projection.physical_rigid_body_bindings == mechanism.physical_rigid_body_bindings
    assert projection.physical_revolute_joint_bindings == mechanism.physical_revolute_joint_bindings
    assert projection.physical_pair_classification_bindings == mechanism.physical_pair_classification_bindings
    assert projection.multi_joint_verification_obligations == mechanism.multi_joint_verification_obligations


@pytest.mark.parametrize(
    "source_type",
    [
        SuppliedRotationalInterfaceAxisSource,
        SuppliedReferenceFrameAxisSource,
        GeneratedRotationalInterfaceAxisSource,
        GeneratedReferenceFrameAxisSource,
    ],
)
def test_multi_joint_projection_rebinds_every_axis_source_variant(tmp_path, source_type):
    candidate, _, _, _, _, request, _, compiler = _promotion_chain(tmp_path)
    mapping = {
        component.instance_id: f"PM-M13-3:{component.instance_id}"
        for component in candidate.realization.components
    }
    specifications = {
        specification.specification_hash: compiler._canonical_specification(specification)
        for specification in candidate.component_specifications
    }
    original = candidate.realization.physical_revolute_joint_bindings[0].axis_source
    generated_specification = next(
        specification
        for specification in candidate.component_specifications
        if specification.generated_part is not None
    )
    generated_instance_id = next(
        component.instance_id
        for component in candidate.realization.components
        if component.specification_hash == generated_specification.specification_hash
    )
    generated_interface = generated_specification.generated_part.interfaces[0]
    source_values = {
        "source_physical_instance_id": original.source_physical_instance_id,
        "interface_id": original.interface_id,
        "interface_hash": original.interface_hash,
        "geometry_reference_hash": original.geometry_reference_hash,
        "specification_hash": original.specification_hash,
    }
    if source_type is SuppliedReferenceFrameAxisSource:
        source_values = {
            "source_physical_instance_id": original.source_physical_instance_id,
            "frame_id": "source-frame",
            "frame_hash": original.interface_hash,
            "geometry_reference_hash": original.geometry_reference_hash,
            "specification_hash": original.specification_hash,
        }
    elif source_type is GeneratedRotationalInterfaceAxisSource:
        source_values = {
            "source_physical_instance_id": generated_instance_id,
            "interface_id": generated_interface.interface_id,
            "interface_hash": generated_interface.interface_hash,
            "generated_specification_hash": generated_specification.specification_hash,
        }
    elif source_type is GeneratedReferenceFrameAxisSource:
        source_values = {
            "source_physical_instance_id": generated_instance_id,
            "frame_id": generated_specification.generated_part.reference_frame.frame_id,
            "frame_hash": generated_specification.generated_part.reference_frame.frame_hash,
            "generated_specification_hash": generated_specification.specification_hash,
        }
    source = source_type(**source_values)
    projected = compiler._canonical_axis_source(source, mapping, specifications)

    assert type(projected).__name__.startswith("Canonical")
    assert projected.source_physical_instance_id == mapping[source.source_physical_instance_id]
    assert projected.source_hash != source.source_hash
    assert projected.source_physical_instance_id != source.source_physical_instance_id
