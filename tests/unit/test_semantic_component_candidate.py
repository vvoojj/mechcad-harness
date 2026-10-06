from __future__ import annotations

import hashlib

import pytest

import mechcad_harness.candidates as candidates_package
import mechcad_harness.candidates.models as candidate_models
from mechcad_harness.candidates.models import (
    CandidateDesignVariable,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    ConnectionMeaning,
    ComponentSpecificationSnapshot,
    GeometrySourceReference,
    JointPhysicalRealizationBinding,
    MechanicalConnection,
    MechanicalConnectionKind,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
    PhysicalRevoluteJointBinding,
    PhysicalRigidBodyBinding,
    PhysicalAxisOwnerEndpoint,
    PhysicalJointMotionMode,
    SuppliedRotationalInterfaceAxisSource,
    UnresolvedCandidateItem,
    UnresolvedCandidateReason,
    candidate_hash,
    candidate_hash_v2,
)
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.physical_mechanism import CanonicalComponentSpecification, CanonicalGeometrySourceReference
from mechcad_harness.models.physical_mechanism import physical_kinematic_root_hash
from mechcad_harness.models.physical_pair_policy import PhysicalPairClassificationBinding
from mechcad_harness.models.semantic_component import (
    bind_component_specification_semantic_identity,
    semantic_component_specification_hash,
    semantic_component_specification_projection,
)
from mechcad_harness.state.hashing import canonical_json


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
CONTENT = "sha256:" + "c" * 64


def _context(artifact_id: str, artifact_hash: str):
    return {
        (artifact_id, artifact_hash, "supplier:component", "step", None): {
            "algorithm": "step-content-identity@1",
            "content_hash": CONTENT,
        }
    }


def _candidate_source(artifact_id: str, artifact_hash: str) -> GeometrySourceReference:
    return GeometrySourceReference(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        source_identity="supplier:component",
        content_identity=CONTENT,
        content_identity_algorithm="step-content-identity@1",
    )


def _canonical_source(artifact_id: str, artifact_hash: str) -> CanonicalGeometrySourceReference:
    return CanonicalGeometrySourceReference(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        source_identity="supplier:component",
        content_identity=CONTENT,
        content_identity_algorithm="step-content-identity@1",
    )


def test_component_specification_at4_uses_context_bound_semantic_geometry():
    first = ComponentSpecificationSnapshot(
        schema_version="component-specification@4",
        component_type="fixture",
        source_identity="supplier:fixture",
        geometry_source=_candidate_source("artifact-a", HASH_A),
    )
    second = ComponentSpecificationSnapshot(
        schema_version="component-specification@4",
        component_type="fixture",
        source_identity="supplier:fixture",
        geometry_source=_candidate_source("artifact-b", HASH_B),
    )
    first_projection = semantic_component_specification_projection(
        first, _context("artifact-a", HASH_A)
    )
    second_projection = semantic_component_specification_projection(
        second, _context("artifact-b", HASH_B)
    )
    assert first_projection == second_projection
    assert semantic_component_specification_hash(first, _context("artifact-a", HASH_A)) == semantic_component_specification_hash(
        second, _context("artifact-b", HASH_B)
    )
    assert "artifact_id" not in str(first_projection)
    assert "artifact_hash" not in str(first_projection)
    wire = first.model_dump(mode="json")
    assert wire["geometry_source"]["content_identity"] == CONTENT
    assert wire["geometry_source"]["content_identity_algorithm"] == "step-content-identity@1"


def test_component_specification_at4_requires_verified_geometry_context():
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@4",
        component_type="fixture",
        source_identity="supplier:fixture",
        geometry_source=_candidate_source("artifact-a", HASH_A),
    )
    with pytest.raises(ValueError, match="verified semantic geometry binding"):
        semantic_component_specification_hash(specification, {})


def test_canonical_component_specification_at4_uses_the_same_projection():
    specification = CanonicalComponentSpecification(
        schema_version="canonical-component-specification@4",
        component_type="fixture",
        source_identity="supplier:fixture",
        geometry_source=_canonical_source("artifact-a", HASH_A),
    )
    projection = semantic_component_specification_projection(
        specification, _context("artifact-a", HASH_A)
    )
    assert projection["schema_version"] == "canonical-component-specification@4"


def test_geometry_identity_context_is_raw_tuple_bound():
    identity = GeometryArtifactIdentity.from_fields(
        "artifact-a", HASH_A, "supplier:component"
    )
    assert identity.coordinate_system_id is None
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@4",
        component_type="fixture",
        source_identity="supplier:fixture",
        geometry_source=_candidate_source("artifact-a", HASH_A),
    )
    with pytest.raises(ValueError):
        semantic_component_specification_hash(
            specification,
            {
                (identity.artifact_id, HASH_B, identity.source_identity, "step", None): {
                    "algorithm": "step-content-identity@1",
                    "content_hash": CONTENT,
                }
            },
        )


def test_pending_component_geometry_is_bound_before_the_semantic_hash_is_published():
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@4",
        component_type="fixture",
        source_identity="supplier:fixture",
        geometry_source=GeometrySourceReference(
            artifact_id="artifact-a",
            artifact_hash=HASH_A,
            source_identity="supplier:component",
            content_identity="pending",
            content_identity_algorithm="step-content-identity@1",
        ),
    )
    bound = bind_component_specification_semantic_identity(
        specification, _context("artifact-a", HASH_A)
    )
    assert bound.specification_hash != "pending"
    assert bound.geometry_source.content_identity == CONTENT
    assert bound.geometry_source.semantic_reference_hash != "pending"


@pytest.mark.parametrize("reference_class", [GeometrySourceReference, CanonicalGeometrySourceReference])
def test_pending_geometry_content_does_not_receive_a_concrete_semantic_reference_hash(reference_class):
    reference = reference_class(
        artifact_id="artifact-a",
        artifact_hash=HASH_A,
        source_identity="supplier:component",
        content_identity="pending",
        content_identity_algorithm="step-content-identity@1",
    )
    assert reference.semantic_reference_hash == "pending"


def _candidate_v2(*, realization=None, design_variables=None, unresolved_items=None):
    specification_a = ComponentSpecificationSnapshot(
        schema_version="component-specification@4",
        component_type="fixture",
        source_identity="supplier:fixture-a",
        geometry_source=_candidate_source("candidate-artifact-a", HASH_A),
        specification_hash=HASH_A,
    )
    specification_b = ComponentSpecificationSnapshot(
        schema_version="component-specification@4",
        component_type="fixture",
        source_identity="supplier:fixture-b",
        geometry_source=_candidate_source("candidate-artifact-b", HASH_B),
        specification_hash=HASH_B,
    )
    if realization is None:
        realization = PhysicalMechanismRealization(
            components=(
                PhysicalComponentInstance(
                    instance_id="z-mount",
                    specification_hash=HASH_B,
                    role=PhysicalComponentRole.MOUNT_OR_SUPPORT,
                    interfaces=("z-port", "a-port"),
                ),
                PhysicalComponentInstance(
                    instance_id="a-motor",
                    specification_hash=HASH_A,
                    role=PhysicalComponentRole.ACTUATOR,
                    interfaces=("motor-shaft",),
                ),
            )
        )
    binding = CandidateSourceBinding(
        project_id="project-a",
        source_revision=1,
        source_state_hash=HASH_A,
        consumed_authority=(
            CandidateSourceReference(
                path="/id",
                value_hash=HASH_B,
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
        ),
    )
    return MechanicalDesignCandidate(
        schema_version="mechanical-design-candidate@2",
        source_binding=binding,
        semantic_source_binding_hash=CONTENT,
        synthesis_request_hash=HASH_A,
        synthesis_policy_hash=HASH_B,
        component_specifications=(specification_b, specification_a),
        realization=realization,
        design_variables=tuple(
            design_variables
            if design_variables is not None
            else (
                CandidateDesignVariable(name="z-variable", value=2.0),
                CandidateDesignVariable(name="a-variable", value=1.0),
            )
        ),
        unresolved_items=tuple(
            unresolved_items
            if unresolved_items is not None
            else (
                UnresolvedCandidateItem(
                    subject_path="/z-subject",
                    required_information="z-info",
                    reason=UnresolvedCandidateReason.REQUIRED_AUTHORITY_MISSING,
                    source_context="z-context",
                ),
                UnresolvedCandidateItem(
                    subject_path="/a-subject",
                    required_information="a-info",
                    reason=UnresolvedCandidateReason.PROPERTY_UNAVAILABLE,
                ),
                UnresolvedCandidateItem(
                    subject_path="/a-subject",
                    required_information="a-info",
                    reason=UnresolvedCandidateReason.PROPERTY_UNAVAILABLE,
                ),
            )
        ),
        generator_identity="candidate-test-generator",
        generator_version="1",
    )


def _unresolved_sort_key(item):
    return (
        item.subject_path,
        item.required_information,
        item.reason.value,
        (0, "") if item.source_context is None else (1, item.source_context),
    )


def _realization_v2():
    components = (
        PhysicalComponentInstance(
            instance_id="a-drive",
            specification_hash=HASH_A,
            role=PhysicalComponentRole.ACTUATOR,
            interfaces=("drive-shaft", "motor-frame"),
        ),
        PhysicalComponentInstance(
            instance_id="b-output",
            specification_hash=HASH_B,
            role=PhysicalComponentRole.SHAFT,
            interfaces=("output-coupling", "output-journal"),
        ),
        PhysicalComponentInstance(
            instance_id="c-support",
            specification_hash=HASH_A,
            role=PhysicalComponentRole.BEARING,
            interfaces=("bearing-bore",),
        ),
    )
    connections = (
        MechanicalConnection(
            connection_id="drive-link",
            kind=MechanicalConnectionKind.ROTATIONAL_DRIVE,
            from_instance_id="a-drive",
            from_interface_id="drive-shaft",
            to_instance_id="b-output",
            to_interface_id="output-coupling",
            meanings=(
                ConnectionMeaning.TORQUE_LOAD_PATH_INTENT,
                ConnectionMeaning.KINEMATIC_REALIZATION_INTENT,
            ),
        ),
        MechanicalConnection(
            connection_id="support-link",
            kind=MechanicalConnectionKind.BEARING_SUPPORT,
            from_instance_id="c-support",
            from_interface_id="bearing-bore",
            to_instance_id="b-output",
            to_interface_id="output-journal",
            meanings=(ConnectionMeaning.STRUCTURAL_RELEVANCE,),
        ),
    )
    joint_bindings = (
        JointPhysicalRealizationBinding(
            joint_id="joint-z",
            driven_instance_id="b-output",
            realization_component_ids=("b-output", "a-drive"),
            actuator_path_connection_ids=("drive-link",),
            transmission_path_connection_ids=("support-link",),
            support_instance_ids=("c-support", "a-drive"),
            hub_or_coupling_instance_id="b-output",
            mount_or_support_instance_ids=("c-support", "a-drive"),
            axis_frame_reference="axis:primary",
            load_path_metadata_available=True,
        ),
        JointPhysicalRealizationBinding(
            joint_id="joint-a",
            driven_instance_id="c-support",
            realization_component_ids=("c-support", "a-drive"),
            actuator_path_connection_ids=("support-link",),
            transmission_path_connection_ids=(),
            support_instance_ids=("a-drive", "c-support"),
            hub_or_coupling_instance_id=None,
            mount_or_support_instance_ids=("a-drive", "c-support"),
            axis_frame_reference="axis:support",
            load_path_metadata_available=False,
        ),
    )
    bodies = (
        PhysicalRigidBodyBinding(
            physical_body_id="body-root",
            member_physical_instance_ids=("c-support", "a-drive"),
            reference_physical_instance_id="a-drive",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="body-output",
            member_physical_instance_ids=("b-output",),
            reference_physical_instance_id="b-output",
        ),
    )
    axis_source = SuppliedRotationalInterfaceAxisSource(
        source_physical_instance_id="a-drive",
        interface_id="drive-shaft",
        interface_hash=HASH_A,
        geometry_reference_hash=HASH_B,
        specification_hash=HASH_A,
    )
    physical_joint = PhysicalRevoluteJointBinding(
        physical_joint_id="physical-joint-1",
        parent_physical_body_id="body-root",
        child_physical_body_id="body-output",
        connection_id="drive-link",
        parent_physical_instance_id="a-drive",
        parent_interface_id="drive-shaft",
        child_physical_instance_id="b-output",
        child_interface_id="output-coupling",
        axis_source=axis_source,
        axis_owner_endpoint=PhysicalAxisOwnerEndpoint.PARENT,
        axis_sign=1,
        motion_mode=PhysicalJointMotionMode.CONTINUOUS,
        min_angle_deg=None,
        max_angle_deg=None,
        zero_reference_semantics="accepted-semantic-home@1",
    )
    return PhysicalMechanismRealization(
        schema_version="physical-mechanism-realization@2",
        components=components,
        connections=connections,
        joint_bindings=joint_bindings,
        physical_rigid_body_bindings=bodies,
        physical_revolute_joint_bindings=(physical_joint,),
        kinematic_root_physical_body_id="body-root",
        kinematic_root_binding_hash=physical_kinematic_root_hash("body-root"),
        physical_pair_classification_bindings=(),
    )


def _rebuild_realization(realization, **updates):
    payload = realization.model_dump(mode="json")
    payload.update(updates)
    payload["realization_hash"] = "pending"
    return PhysicalMechanismRealization.model_validate(payload)


def test_candidate_at2_uses_exact_shared_projection_and_canonical_collection_orders():
    assert hasattr(candidate_models, "semantic_candidate_realization_payload"), (
        "candidate@2 must expose its shared realization projection"
    )
    assert hasattr(candidate_models, "semantic_candidate_design_variable_records"), (
        "candidate@2 must expose its shared design-variable projection"
    )
    realization_projection = candidate_models.semantic_candidate_realization_payload
    design_variable_projection = candidate_models.semantic_candidate_design_variable_records

    candidate = _candidate_v2()
    original_specs = candidate.component_specifications
    original_variables = candidate.design_variables
    original_unresolved = candidate.unresolved_items
    original_components = candidate.realization.components

    assert set(MechanicalDesignCandidate.model_fields) == {
        "schema_version",
        "source_binding",
        "semantic_source_binding_hash",
        "synthesis_request_hash",
        "synthesis_policy_hash",
        "component_specifications",
        "realization",
        "design_variables",
        "unresolved_items",
        "generator_identity",
        "generator_version",
        "parent_candidate_hash",
        "derivation_kind",
        "generation_ordinal",
        "candidate_hash",
    }
    assert realization_projection(candidate.realization) == {
        "schema_version": "physical-mechanism-realization@1",
        "components": [
            {
                "instance_id": "a-motor",
                "specification_hash": HASH_A,
                "role": "actuator",
                "interfaces": ["motor-shaft"],
            },
            {
                "instance_id": "z-mount",
                "specification_hash": HASH_B,
                "role": "mount_or_support",
                "interfaces": ["a-port", "z-port"],
            },
        ],
        "connections": [],
        "joint_bindings": [],
    }
    assert design_variable_projection(candidate.design_variables) == [
        {"name": "a-variable", "value": 1.0, "canonical_path": None},
        {"name": "z-variable", "value": 2.0, "canonical_path": None},
    ]

    unresolved_records = [
        item.model_dump(mode="json")
        for item in sorted(candidate.unresolved_items, key=_unresolved_sort_key)
    ]
    expected_payload = {
        "schema_version": candidate.schema_version,
        "semantic_source_binding_hash": candidate.semantic_source_binding_hash,
        "synthesis_request_hash": candidate.synthesis_request_hash,
        "synthesis_policy_hash": candidate.synthesis_policy_hash,
        "component_specifications": sorted(
            item.specification_hash for item in candidate.component_specifications
        ),
        "realization": realization_projection(candidate.realization),
        "design_variables": design_variable_projection(candidate.design_variables),
        "unresolved_items": unresolved_records,
        "generator_identity": candidate.generator_identity,
        "generator_version": candidate.generator_version,
        "parent_candidate_hash": candidate.parent_candidate_hash,
        "derivation_kind": candidate.derivation_kind,
        "generation_ordinal": candidate.generation_ordinal,
    }
    assert set(expected_payload) == {
        "schema_version",
        "semantic_source_binding_hash",
        "synthesis_request_hash",
        "synthesis_policy_hash",
        "component_specifications",
        "realization",
        "design_variables",
        "unresolved_items",
        "generator_identity",
        "generator_version",
        "parent_candidate_hash",
        "derivation_kind",
        "generation_ordinal",
    }
    expected_hash = "sha256:" + hashlib.sha256(canonical_json(expected_payload)).hexdigest()
    assert candidate_hash_v2(candidate) == expected_hash

    permuted = candidate.model_copy(
        update={
            "component_specifications": tuple(reversed(candidate.component_specifications)),
            "design_variables": tuple(reversed(candidate.design_variables)),
            "unresolved_items": tuple(reversed(candidate.unresolved_items)),
            "candidate_hash": CONTENT,
            "source_binding": candidate.source_binding.model_copy(
                update={"project_id": "different-project", "source_state_hash": CONTENT}
            ),
        }
    )
    assert candidate_hash_v2(permuted) == expected_hash
    assert candidate.component_specifications is original_specs
    assert candidate.design_variables is original_variables
    assert candidate.unresolved_items is original_unresolved
    assert candidate.realization.components is original_components

    without_duplicate = candidate.model_copy(
        update={"unresolved_items": candidate.unresolved_items[:-1]}
    )
    assert candidate_hash_v2(without_duplicate) != expected_hash

    changed_variable = candidate.design_variables[0].model_copy(update={"value": 3.0})
    assert candidate_hash_v2(
        candidate.model_copy(
            update={
                "design_variables": (changed_variable, *candidate.design_variables[1:]),
                "candidate_hash": "pending",
            }
        )
    ) != expected_hash
    changed_specification = candidate.component_specifications[0].model_copy(
        update={"specification_hash": CONTENT}
    )
    assert candidate_hash_v2(
        candidate.model_copy(
            update={
                "component_specifications": (
                    changed_specification,
                    *candidate.component_specifications[1:],
                ),
                "candidate_hash": "pending",
            }
        )
    ) != expected_hash
    changed_unresolved = candidate.unresolved_items[0].model_copy(
        update={"required_information": "different-information"}
    )
    assert candidate_hash_v2(
        candidate.model_copy(
            update={
                "unresolved_items": (changed_unresolved, *candidate.unresolved_items[1:]),
                "candidate_hash": "pending",
            }
        )
    ) != expected_hash


def test_candidate_realization_at2_has_one_shared_ordered_raw_free_mechanism_identity():
    assert hasattr(candidate_models, "semantic_candidate_mechanism_hash"), (
        "the candidate track requires the public semantic mechanism identity"
    )
    mechanism_hash = candidate_models.semantic_candidate_mechanism_hash
    assert candidates_package.semantic_candidate_mechanism_hash is mechanism_hash
    realization_projection = candidate_models.semantic_candidate_realization_payload
    realization = _realization_v2()
    candidate = _candidate_v2(realization=realization)

    component_records = [item.model_dump(mode="json") for item in realization.components]
    for item in component_records:
        item["interfaces"] = list(reversed(item["interfaces"]))
    connection_records = [item.model_dump(mode="json") for item in realization.connections]
    for item in connection_records:
        item["meanings"] = list(reversed(item["meanings"]))
    joint_records = [item.model_dump(mode="json") for item in realization.joint_bindings]
    for item in joint_records:
        for field_name in (
            "realization_component_ids",
            "actuator_path_connection_ids",
            "transmission_path_connection_ids",
            "mount_or_support_instance_ids",
        ):
            item[field_name] = list(reversed(item[field_name]))
    reordered = _rebuild_realization(
        realization,
        components=list(reversed(component_records)),
        connections=list(reversed(connection_records)),
        joint_bindings=list(reversed(joint_records)),
    )
    reordered_candidate = candidate.model_copy(
        update={"realization": reordered, "candidate_hash": "pending"}
    )
    assert realization.realization_hash != reordered.realization_hash
    assert realization_projection(realization) == realization_projection(reordered)
    assert candidate_hash_v2(candidate) == candidate_hash_v2(reordered_candidate)
    assert mechanism_hash(realization) == mechanism_hash(reordered)

    original_axis = realization.physical_revolute_joint_bindings[0].axis_source
    rotated_axis = type(original_axis).model_validate(
        original_axis.model_dump(mode="json")
        | {
            "interface_hash": CONTENT,
            "geometry_reference_hash": CONTENT,
            "source_hash": "pending",
        }
    )
    original_joint = realization.physical_revolute_joint_bindings[0]
    rotated_joint = original_joint.model_copy(
        update={"axis_source": rotated_axis, "binding_hash": "pending"}
    )
    raw_rotated = _rebuild_realization(
        realization, physical_revolute_joint_bindings=(rotated_joint,)
    )
    raw_rotated_candidate = candidate.model_copy(
        update={"realization": raw_rotated, "candidate_hash": "pending"}
    )
    assert raw_rotated.realization_hash != realization.realization_hash
    assert mechanism_hash(raw_rotated) == mechanism_hash(realization)
    assert candidate_hash_v2(raw_rotated_candidate) == candidate_hash_v2(candidate)
    restarted = PhysicalMechanismRealization.model_validate(
        raw_rotated.model_dump(mode="json")
    )
    assert mechanism_hash(restarted) == mechanism_hash(realization)

    support_binding = realization.joint_bindings[0].model_copy(
        update={
            "support_instance_ids": tuple(
                reversed(realization.joint_bindings[0].support_instance_ids)
            )
        }
    )
    support_changed = _rebuild_realization(
        realization,
        joint_bindings=(support_binding, realization.joint_bindings[1]),
    )
    support_changed_candidate = candidate.model_copy(
        update={"realization": support_changed, "candidate_hash": "pending"}
    )
    assert mechanism_hash(support_changed) != mechanism_hash(realization)
    assert candidate_hash_v2(support_changed_candidate) != candidate_hash_v2(candidate)

    directed_connection = realization.connections[0].model_copy(
        update={
            "from_instance_id": "b-output",
            "from_interface_id": "output-coupling",
            "to_instance_id": "a-drive",
            "to_interface_id": "drive-shaft",
        }
    )
    direction_changed = _rebuild_realization(
        realization,
        connections=(directed_connection, realization.connections[1]),
    )
    assert mechanism_hash(direction_changed) != mechanism_hash(realization)

    physical_joint = realization.physical_revolute_joint_bindings[0]
    parent_child_reversed = physical_joint.model_copy(
        update={
            "parent_physical_body_id": "body-output",
            "child_physical_body_id": "body-root",
            "parent_physical_instance_id": "b-output",
            "parent_interface_id": "output-coupling",
            "child_physical_instance_id": "a-drive",
            "child_interface_id": "drive-shaft",
            "binding_hash": "pending",
        }
    )
    parent_child_changed = _rebuild_realization(
        realization, physical_revolute_joint_bindings=(parent_child_reversed,)
    )
    assert mechanism_hash(parent_child_changed) != mechanism_hash(realization)

    duplicate = realization.model_copy(
        update={"components": realization.components + (realization.components[0],)}
    )
    with pytest.raises(ValueError, match="component IDs must be unique"):
        realization_projection(duplicate)

    legacy_payload = realization.model_dump(mode="json")
    for field_name in (
        "physical_rigid_body_bindings",
        "physical_revolute_joint_bindings",
        "kinematic_root_physical_body_id",
        "kinematic_root_binding_hash",
        "physical_pair_classification_bindings",
    ):
        legacy_payload.pop(field_name)
    legacy_payload.update(
        {"schema_version": "physical-mechanism-realization@1", "realization_hash": "pending"}
    )
    legacy = PhysicalMechanismRealization.model_validate(legacy_payload)
    legacy_reordered = _rebuild_realization(
        legacy,
        components=tuple(
            component.model_copy(update={"interfaces": tuple(reversed(component.interfaces))})
            for component in reversed(legacy.components)
        ),
        connections=tuple(
            connection.model_copy(update={"meanings": tuple(reversed(connection.meanings))})
            for connection in reversed(legacy.connections)
        ),
        joint_bindings=tuple(
            binding.model_copy(
                update={
                    field_name: tuple(reversed(getattr(binding, field_name)))
                    for field_name in (
                        "realization_component_ids",
                        "actuator_path_connection_ids",
                        "transmission_path_connection_ids",
                        "mount_or_support_instance_ids",
                    )
                }
            )
            for binding in reversed(legacy.joint_bindings)
        ),
    )
    legacy_candidate = candidate.model_copy(
        update={"realization": legacy, "candidate_hash": "pending"}
    )
    legacy_reordered_candidate = candidate.model_copy(
        update={"realization": legacy_reordered, "candidate_hash": "pending"}
    )
    assert set(realization_projection(legacy)) == {
        "schema_version", "components", "connections", "joint_bindings"
    }
    assert legacy.realization_hash != legacy_reordered.realization_hash
    assert realization_projection(legacy) == realization_projection(legacy_reordered)
    assert candidate_hash_v2(legacy_candidate) == candidate_hash_v2(legacy_reordered_candidate)


def test_concrete_semantic_projection_rejects_a_pending_reference_trio():
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@4",
        component_type="fixture",
        source_identity="supplier:fixture",
        geometry_source=_candidate_source("artifact-a", HASH_A),
    )
    forged_source = specification.geometry_source.model_copy(
        update={"semantic_reference_hash": "pending"}
    )
    forged = specification.model_copy(update={"geometry_source": forged_source})
    with pytest.raises(ValueError, match="incomplete"):
        semantic_component_specification_hash(forged, _context("artifact-a", HASH_A))


def test_candidate_at1_keeps_its_legacy_serialization_and_stored_order_hash():
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@1",
        component_type="custom_fixture",
        source_identity="drawing:legacy-fixture@1",
        interfaces=("body",),
    )
    realization = PhysicalMechanismRealization(
        components=(
            PhysicalComponentInstance(
                instance_id="legacy-instance",
                specification_hash=specification.specification_hash,
                role=PhysicalComponentRole.DRIVEN_BODY,
                interfaces=("body",),
            ),
        )
    )
    source_binding = _candidate_v2().source_binding
    variables = (
        CandidateDesignVariable(name="z-legacy", value=2.0),
        CandidateDesignVariable(name="a-legacy", value=1.0),
    )
    base = {
        "schema_version": "mechanical-design-candidate@1",
        "source_binding": source_binding,
        "synthesis_request_hash": HASH_A,
        "synthesis_policy_hash": HASH_B,
        "component_specifications": (specification,),
        "realization": realization,
        "unresolved_items": (),
        "generator_identity": "legacy-generator",
        "generator_version": "1",
    }
    candidate = MechanicalDesignCandidate(**base, design_variables=variables)
    reordered = MechanicalDesignCandidate(
        **base, design_variables=tuple(reversed(variables))
    )
    wire = candidate.model_dump(mode="json")
    assert set(wire) == {
        "schema_version",
        "source_binding",
        "synthesis_request_hash",
        "synthesis_policy_hash",
        "component_specifications",
        "realization",
        "design_variables",
        "unresolved_items",
        "generator_identity",
        "generator_version",
        "parent_candidate_hash",
        "derivation_kind",
        "generation_ordinal",
        "candidate_hash",
    }
    assert "semantic_source_binding_hash" not in wire
    legacy_payload = dict(wire)
    legacy_payload.pop("candidate_hash")
    expected_legacy_hash = "sha256:" + hashlib.sha256(
        canonical_json(legacy_payload)
    ).hexdigest()
    assert candidate_hash(candidate) == expected_legacy_hash
    assert reordered.candidate_hash != candidate.candidate_hash
