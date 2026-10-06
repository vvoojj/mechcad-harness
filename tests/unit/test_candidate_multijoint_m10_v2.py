from __future__ import annotations

import hashlib

import pytest

import mechcad_harness.candidates.multi_joint_m10_bridge as bridge_models
import mechcad_harness.candidates.multi_joint_m10_evaluation as evaluation_models
import mechcad_harness.candidates.multi_joint_selection as selection_models
from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    PhysicalToM10V2BridgeCompiler,
)
from mechcad_harness.candidates.multi_joint_m10_evaluation import (
    CandidateMultiJointM10EvaluationScope,
    CandidateMultiJointM10EvaluationService,
)
from mechcad_harness.candidates.multi_joint_selection import (
    CandidateMultiJointSelectionService,
)
from mechcad_harness.candidates.services import (
    CandidateCurrentness,
    CandidateCurrentnessService,
    CandidateIntegrityError,
    bind_candidate_synthesis_request_semantic_identity,
)
from mechcad_harness.models.multi_joint_verification import (
    MultiJointVerificationConfigurationSet,
)
from mechcad_harness.multi_joint_collision_sweep import (
    ExactConstituentPairResultV2,
    MultiJointCollisionConfigurationResultV2,
    MultiJointCollisionSweepResultV2,
    multi_joint_collision_sweep_result_v2_hash,
)
from mechcad_harness.multi_joint_kinematics import (
    EvaluatedJointState,
    InstanceWorldTransform,
    JointConfiguration,
    MultiJointKinematicsService,
    joint_configuration_hash,
)
from mechcad_harness.semantic_m10_kinematics import semantic_m10_v2_request_hash
from mechcad_harness.models.physical_mechanism import physical_kinematic_root_hash
from mechcad_harness.models.physical_pair_policy import (
    PhysicalPairClassification,
    PhysicalPairClassificationBinding,
)
from mechcad_harness.candidates.models import (
    CandidateDesignVariable,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisRequest,
    GeometrySourceReference,
    PhysicalAxisOwnerEndpoint,
    PhysicalJointMotionMode,
    PhysicalMechanismRealization,
    PhysicalRevoluteJointBinding,
    PhysicalRigidBodyBinding,
    SuppliedRotationalInterfaceAxisSource,
    ConnectionMeaning,
    MechanicalConnectionKind,
    ComponentSpecificationSnapshot,
    semantic_candidate_mechanism_hash,
)
from mechcad_harness.candidates.cad_realization import (
    CandidateGeometryFidelity,
    CandidateCadInstanceMappingV2,
    CandidateCadRealizationV2,
    SemanticPlacementOrigin,
    SemanticSourceGeometryIdentity,
    bind_semantic_placement_origin,
    trusted_representation_identity,
    semantic_placement_derivations_hash,
)
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.semantic_component import bind_component_specification_semantic_identity
from mechcad_harness.models.supplied_component_interface import (
    RotationalShaftInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedInterfaceTransformRole,
)
from mechcad_harness.imported_component import ImportedCadComponent
from mechcad_harness.state import StateManager
from mechcad_harness.state import state_hash
from mechcad_harness.step_content_identity import step_content_identity_v1
from mechcad_harness.step_content_identity import step_content_identity_v1
from test_candidate_cad_realization_v2 import _realization_at2
from test_candidate_cad_request_v3 import _INSTANCE_SLOTS, _request_at3
from test_candidate_m10_v2 import _policy_requirements
from test_candidate_trusted_semantic_verification import (
    _P2_GEOMETRY_SLOTS,
    _P2_STEP_VARIANTS,
    _at2_chain,
    _at2_setup,
)
from test_canonical_mechanism_v4 import _mechanism_at4
from test_m13_2_placement_derivations import _coaxial
from test_m13_geometry_materialization import _interface_fact
from test_m12_revolute_drive_service import (
    DriveArchitecture,
    RevoluteDriveRealizationService,
    policy_for,
    template,
)
from test_candidate_cad_request_v3 import _INSTANCE_SLOTS


def test_multi_joint_candidate_v2_family_records_have_exact_contract_fields():
    expected_fields = {
        "MultiJointCollisionPairInventoryV2": {
            "schema_version", "physical_mechanism_hash",
            "physical_body_binding_hashes", "cad_realization_hash",
            "semantic_kinematic_model_hash", "complete_concrete_instance_ids",
            "expected_pair_universe", "entries", "inventory_hash",
        },
        "PhysicalToM10V2BridgeV2": {
            "schema_version", "physical_mechanism_hash",
            "kinematic_root_binding_hash", "physical_body_binding_hashes",
            "physical_joint_binding_hashes", "semantic_placement_identities",
            "axis_source_identities", "cad_mapping_hashes",
            "physical_pair_classification_set_hash", "model",
            "semantic_kinematic_model_hash", "inventory", "inventory_hash",
            "exact_pair_scope", "exact_pair_scope_hash", "ordered_body_ids",
            "ordered_joint_ids", "physical_to_m10_bridge_hash",
        },
        "CandidateMultiJointM10EvaluationRequestV2": {
            "schema_version", "project_id", "source_revision", "source_state_hash",
            "semantic_source_binding_hash", "candidate_hash", "physical_mechanism_hash",
            "physical_body_binding_hashes", "physical_joint_binding_hashes",
            "kinematic_root_binding_hash", "physical_pair_classification_set_hash",
            "physical_to_m10_bridge_hash", "cad_realization_hash", "cad_mapping_hashes",
            "semantic_kinematic_model_hash", "inventory_hash", "exact_pair_scope_hash",
            "scope", "scope_hash", "configuration_set_hash", "configuration_hashes",
            "semantic_m10_v2_request_hash", "placement_derivations",
            "semantic_placement_derivations_hash", "request_hash",
        },
        "CandidateMultiJointM10EvaluationV2": {
            "schema_version", "project_id", "source_revision", "source_state_hash",
            "semantic_source_binding_hash", "candidate_hash", "candidate_request_hash",
            "semantic_m10_v2_request_hash", "semantic_m10_v2_result_hash",
            "cad_realization_hash", "physical_to_m10_bridge_hash",
            "semantic_kinematic_model_hash", "physical_pair_classification_set_hash",
            "inventory_hash", "exact_pair_scope_hash", "scope_hash",
            "configuration_set_hash", "evaluation_hash",
        },
        "CandidateMultiJointSelectionV2": {
            "schema_version", "project_id", "source_revision", "source_state_hash",
            "semantic_source_binding_hash", "candidate_hash", "evaluation_hash",
            "candidate_request_hash", "semantic_m10_v2_request_hash",
            "semantic_m10_v2_result_hash", "physical_to_m10_bridge_hash",
            "semantic_kinematic_model_hash", "physical_pair_classification_set_hash",
            "inventory_hash", "exact_pair_scope_hash", "scope_hash",
            "configuration_set_hash", "selector_identity", "rationale",
            "selection_hash",
        },
    }
    modules = {
        "MultiJointCollisionPairInventoryV2": bridge_models,
        "PhysicalToM10V2BridgeV2": bridge_models,
        "CandidateMultiJointM10EvaluationRequestV2": evaluation_models,
        "CandidateMultiJointM10EvaluationV2": evaluation_models,
        "CandidateMultiJointSelectionV2": selection_models,
    }
    for name, fields in expected_fields.items():
        record_type = getattr(modules[name], name)
        assert set(record_type.model_fields) == fields
    assert set(bridge_models.MultiJointCollisionPairEntry.model_fields) == {
        "schema_version", "first_instance_id", "second_instance_id",
        "classification", "exclusion_reason",
    }


def _candidate_with_m13_multi_joint_authority(
    tmp_path, *, variant="A", manager=None, store=None
):
    if manager is None or store is None:
        state_v1, manager, store, _, candidate_request_v1, policy, initial_candidate = _at2_setup(
            tmp_path
        )
    else:
        state_v1, _, candidate_request_v1, policy, initial_candidate = _at2_chain(
            tmp_path, manager, store, variant=variant
        )
    step_bytes = _P2_STEP_VARIANTS[variant]
    raw_hash = "sha256:" + hashlib.sha256(step_bytes).hexdigest()
    content_identity = step_content_identity_v1(step_bytes).content_hash
    state_payload = state_v1.model_dump(mode="json")
    identities = [dict(item) for item in state_payload["yagi_payload_carrier_requirements"]]
    identity_by_slot = {}
    for item, slot in zip(identities, _P2_GEOMETRY_SLOTS, strict=True):
        item["artifact_id"] = f"ART-P5-3-{variant}-{slot}"
        item["artifact_hash"] = raw_hash
        if slot == "motor":
            item["coordinate_system_id"] = "motor-local-mm"
        else:
            item.pop("coordinate_system_id", None)
        identity_by_slot[slot] = item
    state_payload["yagi_payload_carrier_requirements"] = identities
    next_snapshot = manager.create_revision(
        "PRJ-M12", type(state_v1).model_validate(state_payload)
    )
    state = next_snapshot.state
    for slot in _P2_GEOMETRY_SLOTS:
        item = identity_by_slot[slot]
        store.publish(
            item["artifact_id"],
            ArtifactType.STEP,
            f"p5-3-{slot}.step",
            step_bytes,
            "candidate-multijoint-m10-v2-test",
            "1",
            state.revision,
            state_hash(state),
        )

    source_binding = CandidateSourceBinding(
        project_id=initial_candidate.source_binding.project_id,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=tuple(
            CandidateSourceReference(
                path=reference.path,
                value_hash="pending",
                authority=reference.authority,
            )
            for reference in initial_candidate.source_binding.consumed_authority
        ),
    ).bound_to(state)
    pending_request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@2",
        source_binding=source_binding,
        semantic_source_binding_hash="pending",
        requested_joint_ids=(initial_candidate.realization.joint_bindings[0].joint_id,),
        required_joint_ids=(initial_candidate.realization.joint_bindings[0].joint_id,),
    )
    synthesis_request = bind_candidate_synthesis_request_semantic_identity(
        pending_request,
        state_manager=manager,
        store=store,
        project_id=source_binding.project_id,
    )

    identity_context = {}
    for slot, item in identity_by_slot.items():
        identity_context[
            (
                item["artifact_id"],
                item["artifact_hash"],
                item["source_identity"],
                item["format"],
                item.get("coordinate_system_id"),
            )
        ] = {
            "algorithm": "step-content-identity@1",
            "content_hash": content_identity,
        }
    specifications_by_slot = {}
    for spec in initial_candidate.component_specifications:
        slot = spec.source_identity.rsplit(":", 1)[-1].split("@", 1)[0]
        identity = identity_by_slot[slot]
        coordinate_system_id = identity.get("coordinate_system_id")
        geometry_source = GeometrySourceReference.model_validate(
            spec.geometry_source.model_dump(mode="python")
            | {
                "artifact_id": identity["artifact_id"],
                "artifact_hash": identity["artifact_hash"],
                "source_identity": identity["source_identity"],
                "coordinate_system_id": coordinate_system_id,
                "reference_hash": "pending",
                "content_identity": "pending",
                "content_identity_algorithm": "step-content-identity@1",
                "semantic_reference_hash": "pending",
            }
        )
        supplied_definitions = ()
        if slot == "motor":
            geometry = GeometryArtifactIdentity(
                artifact_id=identity["artifact_id"],
                artifact_hash=identity["artifact_hash"],
                source_identity=identity["source_identity"],
                format=identity["format"],
                coordinate_system_id=coordinate_system_id,
            )
            interface = RotationalShaftInterface(
                interface_id="output-shaft",
                geometry_reference_hash=geometry_source.reference_hash,
                geometry=geometry,
                axis_point=_interface_fact(
                    "m10-axis-point", SuppliedInterfaceTransformRole.POINT_MM,
                    (0.0, 0.0, 0.0),
                ),
                axis_direction=_interface_fact(
                    "m10-axis-direction", SuppliedInterfaceTransformRole.DIRECTION_UNIT,
                    (0.0, 0.0, 1.0),
                ),
                nominal_shaft_diameter=_interface_fact(
                    "m10-shaft-diameter", SuppliedInterfaceTransformRole.LENGTH_MM, 12.0
                ),
                usable_axial_engagement_length=_interface_fact(
                    "m10-shaft-engagement", SuppliedInterfaceTransformRole.LENGTH_MM, 20.0
                ),
            )
            supplied_definitions = (
                SuppliedComponentInterfaceDefinition(
                    interface_id=interface.interface_id,
                    geometry_reference_hash=geometry_source.reference_hash,
                    geometry=geometry,
                    shaft=interface,
                ),
            )
        pending_spec = type(spec).model_validate(
            spec.model_dump(mode="python")
            | {
                "schema_version": "component-specification@4",
                "geometry_source": geometry_source,
                "supplied_interface_definitions": supplied_definitions,
                "specification_hash": "pending",
            }
        )
        specifications_by_slot[slot] = bind_component_specification_semantic_identity(
            pending_spec, identity_context
        )
    specifications = tuple(specifications_by_slot.values())
    direct_template = template(
        DriveArchitecture.DIRECT_DRIVE,
        motor_specification=specifications_by_slot["motor"],
        shaft_specification=specifications_by_slot["shaft"],
        bearing_a_specification=specifications_by_slot["bearing"],
        bearing_b_specification=specifications_by_slot["bearing"],
        hub_specification=specifications_by_slot["hub"],
        mount_specification=specifications_by_slot["mount"],
        driven_body_specification=specifications_by_slot["body"],
    )
    policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    constructed = RevoluteDriveRealizationService().construct_candidate(
        synthesis_request, policy, direct_template
    )
    if constructed.candidate is None:
        raise AssertionError(f"test candidate construction was unresolved: {constructed.reason}")
    candidate = constructed.candidate
    motor_at4 = specifications_by_slot["motor"]
    components = candidate.realization.components

    bodies = (
        PhysicalRigidBodyBinding(
            physical_body_id="body-root",
            member_physical_instance_ids=("bearing-a", "bearing-b", "drive-motor", "motor-mount"),
            reference_physical_instance_id="drive-motor",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="body-output",
            member_physical_instance_ids=("output-hub", "output-shaft", "payload-body"),
            reference_physical_instance_id="output-shaft",
        ),
    )
    axis_source = SuppliedRotationalInterfaceAxisSource(
        source_physical_instance_id="drive-motor",
        interface_id=motor_at4.supplied_interface_definitions[0].interface_id,
        interface_hash=motor_at4.supplied_interface_definitions[0].interface_hash,
        geometry_reference_hash=motor_at4.geometry_source.reference_hash,
        specification_hash=motor_at4.specification_hash,
    )
    revolute = PhysicalRevoluteJointBinding(
        physical_joint_id="J-1",
        parent_physical_body_id="body-root",
        child_physical_body_id="body-output",
        connection_id="drive",
        parent_physical_instance_id="drive-motor",
        parent_interface_id="output-shaft",
        child_physical_instance_id="output-shaft",
        child_interface_id="motor-side",
        axis_source=axis_source,
        axis_owner_endpoint=PhysicalAxisOwnerEndpoint.PARENT,
        axis_sign=1,
        motion_mode=PhysicalJointMotionMode.CONTINUOUS,
        min_angle_deg=None,
        max_angle_deg=None,
        zero_reference_semantics="accepted-semantic-home@1",
    )
    body_by_member = {
        member: body.physical_body_id
        for body in bodies
        for member in body.member_physical_instance_ids
    }
    physical_ids = tuple(sorted(body_by_member))
    pair_bindings = tuple(
        PhysicalPairClassificationBinding(
            first_physical_instance_id=first,
            second_physical_instance_id=second,
            classification=(
                PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED
                if body_by_member[first] == body_by_member[second]
                else PhysicalPairClassification.CHECK_CLEARANCE
            ),
            exclusion_reason=(
                "same accepted rigid body"
                if body_by_member[first] == body_by_member[second]
                else None
            ),
        )
        for index, first in enumerate(physical_ids)
        for second in physical_ids[index + 1 :]
    )
    physical = PhysicalMechanismRealization.model_validate(
        candidate.realization.model_dump(mode="json")
        | {
            "schema_version": "physical-mechanism-realization@2",
            "components": [item.model_dump(mode="json") for item in components],
            "physical_rigid_body_bindings": [item.model_dump(mode="json") for item in bodies],
            "physical_revolute_joint_bindings": [revolute.model_dump(mode="json")],
            "kinematic_root_physical_body_id": "body-root",
            "kinematic_root_binding_hash": physical_kinematic_root_hash("body-root"),
            "physical_pair_classification_bindings": [
                item.model_dump(mode="json") for item in pair_bindings
            ],
            "realization_hash": "pending",
        }
    )
    candidate_at2 = type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "component_specifications": [item.model_dump(mode="json") for item in specifications],
            "realization": physical.model_dump(mode="json"),
            "candidate_hash": "pending",
        }
    )
    return state, manager, store, synthesis_request, policy, candidate_at2


def _candidate_cad_v2(candidate, synthesis_request, state, *, assembly_id="candidate-assembly-m13-multi-v2"):
    step_bytes = _P2_STEP_VARIANTS["A"]
    raw_hash = "sha256:" + hashlib.sha256(step_bytes).hexdigest()
    content_hash = step_content_identity_v1(step_bytes).content_hash
    identity_by_slot = {
        item["source_identity"].split(":")[-1].split("@", 1)[0]: item
        for item in state.yagi_payload_carrier_requirements
    }
    content_by_artifact = {raw_hash: content_hash}
    for item in identity_by_slot.values():
        content_by_artifact[item["artifact_id"]] = content_hash

    mappings = []
    imported = []
    instances = []
    for index, (physical_id, slot) in enumerate(_INSTANCE_SLOTS):
        identity = identity_by_slot[slot]
        transform = CadRigidTransform(x_mm=float(index * 20))
        cad_id = f"cad-{physical_id}"
        origin = bind_semantic_placement_origin(
            "source_authority",
            (
                identity["artifact_id"],
                raw_hash,
                f"candidate:source-authority:{identity['source_identity']}",
            ),
            "fixture-placement@1",
            transform,
            content_by_artifact=content_by_artifact,
        )
        mappings.append(
            CandidateCadInstanceMappingV2(
                candidate_hash=candidate.candidate_hash,
                physical_instance_id=physical_id,
                cad_instance_id=cad_id,
                fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
                representation_identity=trusted_representation_identity(
                    slot=cad_id, content_identity=content_hash
                ),
                source_geometry_identity=SemanticSourceGeometryIdentity(
                    content_identity=content_hash,
                    content_identity_algorithm="step-content-identity@1",
                ),
                geometry_definition_identities=(content_hash,),
                placement=transform,
                placement_origin=origin,
            )
        )
        imported.append(
            ImportedCadComponent(
                component_id=cad_id,
                artifact_id=identity["artifact_id"],
                artifact_hash=identity["artifact_hash"],
                source_revision=state.revision,
                source_state_hash=state_hash(state),
            )
        )
        instances.append(
            CadComponentInstance(
                instance_id=cad_id,
                part_id=cad_id,
                placement=transform,
            )
        )
    mappings = tuple(sorted(mappings, key=lambda item: item.physical_instance_id))
    cad_request = _request_at3(
        candidate,
        synthesis_request.semantic_source_binding_hash,
        mappings=mappings,
    )
    assembly = CadAssemblyProgram(
        assembly_id=assembly_id,
        imported_components=tuple(sorted(imported, key=lambda item: item.component_id)),
        instances=tuple(sorted(instances, key=lambda item: item.instance_id)),
    )
    cad = CandidateCadRealizationV2(
        candidate_hash=candidate.candidate_hash,
        request_hash=cad_request.request_hash,
        mappings=mappings,
        assembly=assembly,
        assembly_hash=assembly_hash(assembly),
        representation_identities=tuple(item.representation_identity for item in mappings),
        semantic_placement_derivations_hash=cad_request.semantic_placement_derivations_hash,
        verified_source_content_identities=(content_hash,),
        verified_source_artifact_hashes=tuple(
            raw_hash for _ in identity_by_slot
        ),
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        provider_identity="candidate-multijoint-m10-v2-test-provider",
    )
    return cad_request, cad


def _raw_m10_result(**kwargs):
    from mechcad_harness.cad_assembly import assembly_hash
    from mechcad_harness.multi_joint_collision_sweep import (
        CollisionClassification,
        ExactConstituentPairResultV2,
        MultiJointCollisionConfigurationResultV2,
        MultiJointCollisionSweepRequestV2,
        MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
        MultiJointCollisionSweepResultV2,
        multi_joint_collision_sweep_result_v2_hash,
    )

    assembly = kwargs["assembly"]
    model = kwargs["model"]
    configurations = tuple(kwargs["configurations"])
    low_request = MultiJointCollisionSweepRequestV2(
        schema_version="multi-joint-collision-sweep-request@2",
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        configurations=configurations,
        exact_pair_scope=tuple(kwargs["exact_pair_scope"]),
        volume_tolerance_mm3=kwargs["volume_tolerance_mm3"],
        distance_tolerance_mm=kwargs["distance_tolerance_mm"],
        evaluator_version=MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
    )
    kinematics = MultiJointKinematicsService()
    configuration_results = []
    for index, configuration in enumerate(configurations):
        fk = kinematics.evaluate(assembly, model, configuration)
        pair_results = tuple(
            ExactConstituentPairResultV2(
                schema_version="exact-constituent-pair-result@2",
                first_instance_id=pair.first_instance_id,
                second_instance_id=pair.second_instance_id,
                interference_volume_mm3=0.0,
                exact_distance_mm=5.0,
                classification=CollisionClassification.POSITIVE_CLEARANCE,
            )
            for pair in low_request.exact_pair_scope
        )
        configuration_results.append(
            MultiJointCollisionConfigurationResultV2(
                schema_version="multi-joint-collision-configuration-result@2",
                configuration_index=index,
                configuration_hash=joint_configuration_hash(configuration),
                transformed_assembly_hash=fk.transformed_assembly_hash,
                ordered_joint_states=fk.ordered_joint_states,
                instance_world_transforms=fk.instance_world_transforms,
                pair_results=pair_results,
                classification=CollisionClassification.POSITIVE_CLEARANCE,
                any_interference=False,
                any_touching=False,
                all_positive_clearance=True,
                minimum_exact_distance_mm=5.0,
            )
        )
    result = MultiJointCollisionSweepResultV2(
        schema_version="multi-joint-collision-sweep-result@2",
        evaluator_version=MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
        source_assembly_hash=low_request.source_assembly_hash,
        model_hash=low_request.model_hash,
        request_hash=low_request.request_hash,
        configuration_results=tuple(configuration_results),
        any_interference=False,
        any_touching=False,
        all_positive_clearance=True,
        collision_configuration_indices=(),
        minimum_exact_distance_mm=5.0,
        minimum_distance_configuration_index=0,
        continuous_path_verified=False,
    )
    return result.model_copy(
        update={"result_hash": multi_joint_collision_sweep_result_v2_hash(result)}
    )


def test_candidate_m13_topology_compiles_bridge_v2_from_semantic_candidate_cad(tmp_path):
    state, manager, _, synthesis_request, _, candidate = _candidate_with_m13_multi_joint_authority(tmp_path)
    assert CandidateCurrentnessService(manager).evaluate_source_binding(
        candidate, synthesis_request=synthesis_request
    ) is CandidateCurrentness.CURRENT
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    assert bridge.schema_version == "physical-to-m10-v2-bridge@2"
    assert bridge.inventory.schema_version == "multi-joint-collision-pair-inventory@2"
    assert bridge.semantic_kinematic_model_hash.startswith("sha256:")


def test_candidate_m10_v2_rebinds_semantic_mechanism_and_hashes_project_id(tmp_path):
    state, manager, _, synthesis_request, _, candidate = (
        _candidate_with_m13_multi_joint_authority(tmp_path)
    )
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    expected_mechanism_hash = semantic_candidate_mechanism_hash(candidate.realization)
    assert bridge.physical_mechanism_hash == expected_mechanism_hash
    assert bridge.inventory.physical_mechanism_hash == expected_mechanism_hash
    assert bridge.physical_mechanism_hash != candidate.realization.realization_hash
    restored_realization = PhysicalMechanismRealization.model_validate(
        candidate.realization.model_dump(mode="json")
    )
    assert semantic_candidate_mechanism_hash(restored_realization) == expected_mechanism_hash

    def substitute_mechanism_identity(replacement):
        inventory_payload = bridge.inventory.model_dump(mode="json")
        inventory_payload["physical_mechanism_hash"] = replacement
        inventory_payload.pop("inventory_hash")
        inventory = bridge_models.MultiJointCollisionPairInventoryV2.model_validate(
            inventory_payload
        )
        return bridge_models.PhysicalToM10V2BridgeV2.model_validate(
            bridge.model_dump(mode="json")
            | {
                "physical_mechanism_hash": replacement,
                "inventory": inventory.model_dump(mode="json"),
                "inventory_hash": inventory.inventory_hash,
                "physical_to_m10_bridge_hash": "pending",
            }
        )

    raw_axis_source = candidate.realization.physical_revolute_joint_bindings[0].axis_source
    for substituted_identity in (
        candidate.realization.realization_hash,
        raw_axis_source.interface_hash,
        raw_axis_source.geometry_reference_hash,
        raw_axis_source.source_hash,
        _mechanism_at4().mechanism_hash,
    ):
        substituted_bridge = substitute_mechanism_identity(substituted_identity)
        with pytest.raises(ValueError, match="trusted candidate/CAD/M13 inputs"):
            bridge_models.validate_physical_to_m10_v2_bridge_v2(
                substituted_bridge,
                candidate=candidate,
                cad_realization=cad_realization,
                placement_derivations=cad_request.placement_derivations,
            )

    scope = _multi_joint_scope(bridge.model.model_id)
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessSpy(manager),
        analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
    )
    request = service.build_request(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        scope,
        cad_request=cad_request,
    )
    assert request.physical_mechanism_hash == expected_mechanism_hash
    evaluation = service.execute(
        candidate, synthesis_request, cad_realization, bridge, request
    )
    baseline_evaluation_hash = evaluation_models.candidate_multi_joint_m10_evaluation_hash_v2(
        evaluation, request
    )
    assert evaluation.evaluation_hash == baseline_evaluation_hash
    for foreign_mechanism_hash in (
        candidate.realization.realization_hash,
        "sha256:" + "f" * 64,
    ):
        foreign_request = evaluation_models.CandidateMultiJointM10EvaluationRequestV2.model_validate(
            request.model_dump(mode="json")
            | {
                "physical_mechanism_hash": foreign_mechanism_hash,
                "request_hash": "pending",
            }
        )
        with pytest.raises(ValueError, match="physical mechanism binding mismatch"):
            selection_models.CandidateMultiJointSelectionService._validate_chain_v2(
                candidate, synthesis_request, foreign_request, evaluation
            )

    other_project_request = evaluation_models.CandidateMultiJointM10EvaluationRequestV2.model_validate(
        request.model_dump(mode="json")
        | {"project_id": "PRJ-OTHER", "request_hash": "pending"}
    )
    assert other_project_request.request_hash != request.request_hash
    other_project_evaluation = evaluation_models.CandidateMultiJointM10EvaluationV2.model_validate(
        evaluation.model_dump(mode="json")
        | {
            "project_id": "PRJ-OTHER",
            "candidate_request_hash": other_project_request.request_hash,
            "evaluation_hash": "pending",
        }
    )
    other_project_evaluation_hash = (
        evaluation_models.candidate_multi_joint_m10_evaluation_hash_v2(
            other_project_evaluation, other_project_request
        )
    )
    assert other_project_evaluation_hash != baseline_evaluation_hash

    def selection_for(project_request, project_evaluation):
        return selection_models.CandidateMultiJointSelectionV2(
            project_id=project_request.project_id,
            source_revision=project_request.source_revision,
            source_state_hash=project_request.source_state_hash,
            semantic_source_binding_hash=project_request.semantic_source_binding_hash,
            candidate_hash=project_request.candidate_hash,
            evaluation_hash=(
                project_evaluation.evaluation_hash
                if project_evaluation.evaluation_hash != "pending"
                else evaluation_models.candidate_multi_joint_m10_evaluation_hash_v2(
                    project_evaluation, project_request
                )
            ),
            candidate_request_hash=project_request.request_hash,
            semantic_m10_v2_request_hash=project_evaluation.semantic_m10_v2_request_hash,
            semantic_m10_v2_result_hash=project_evaluation.semantic_m10_v2_result_hash,
            physical_to_m10_bridge_hash=project_request.physical_to_m10_bridge_hash,
            semantic_kinematic_model_hash=project_request.semantic_kinematic_model_hash,
            physical_pair_classification_set_hash=(
                project_request.physical_pair_classification_set_hash
            ),
            inventory_hash=project_request.inventory_hash,
            exact_pair_scope_hash=project_request.exact_pair_scope_hash,
            scope_hash=project_request.scope_hash,
            configuration_set_hash=project_request.configuration_set_hash,
            selector_identity="fixture-selector@1",
            rationale="project identity is semantic",
        )

    baseline_selection = selection_for(request, evaluation)
    other_project_selection = selection_models.CandidateMultiJointSelectionV2.model_validate(
        baseline_selection.model_dump(mode="json")
        | {"project_id": "PRJ-OTHER", "selection_hash": "pending"}
    )
    assert baseline_selection.selection_hash != other_project_selection.selection_hash


class _CurrentnessSpy:
    def __init__(self, state_manager):
        self.delegate = CandidateCurrentnessService(state_manager)
        self.requests = []

    def evaluate_source_binding(self, candidate, *, synthesis_request=None):
        self.requests.append(synthesis_request)
        return self.delegate.evaluate_source_binding(
            candidate, synthesis_request=synthesis_request
        )


def _multi_joint_scope(model_id: str, positions=(0.0, 30.0)):
    configurations = tuple(
        JointConfiguration(model_id=model_id, positions={"J-1": angle})
        for angle in positions
    )
    return CandidateMultiJointM10EvaluationScope(
        configuration_set=MultiJointVerificationConfigurationSet(
            configurations=configurations
        ),
        volume_tolerance_mm3=1e-9,
        distance_tolerance_mm=1e-7,
        scope_identity="explicit-candidate-m10-test-scope@1",
    )


def test_typed_request_v2_flows_through_multi_joint_build_reconstruct_execute_application_and_selection(tmp_path):
    state, manager, _, synthesis_request, policy, candidate = (
        _candidate_with_m13_multi_joint_authority(tmp_path)
    )
    m12_result = RevoluteDriveRealizationService().evaluate(
        candidate, synthesis_request, policy, _policy_requirements()
    )
    assert m12_result.schema_version == "revolute-drive-admissibility@2"
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    scope = _multi_joint_scope(bridge.model.model_id)
    currentness = _CurrentnessSpy(manager)
    provider_calls = []

    def provider(**kwargs):
        provider_calls.append(kwargs)
        return _raw_m10_result(**kwargs)

    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=currentness,
        analyze_multi_joint_collision_sweep_v2=provider,
    )
    request = service.build_request(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        scope,
        cad_request=cad_request,
    )
    assert request.schema_version == "candidate-multi-joint-m10-evaluation-request@2"
    assert request.semantic_placement_derivations_hash is None
    assert currentness.requests[-1] is synthesis_request
    with pytest.raises((TypeError, ValueError), match="typed synthesis request@2"):
        service.build_request(
            candidate, cad_realization, bridge, scope, synthesis_request=None
        )
    with pytest.raises((TypeError, ValueError), match="typed synthesis request@2|request@2"):
        service.build_request(
            candidate, synthesis_request.request_hash, cad_realization, bridge, scope
        )
    legacy_request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@1",
        source_binding=synthesis_request.source_binding,
        requested_joint_ids=synthesis_request.requested_joint_ids,
        required_joint_ids=synthesis_request.required_joint_ids,
    )
    with pytest.raises(ValueError, match="typed synthesis request@2"):
        service.build_request(
            candidate, legacy_request, cad_realization, bridge, scope
        )
    with pytest.raises(CandidateIntegrityError, match="request@2"):
        currentness.delegate.evaluate_source_binding(candidate)

    reconstructed = service.reconstruct_m10_request(
        candidate, synthesis_request, cad_realization, bridge, request
    )
    assert semantic_m10_v2_request_hash(
        reconstructed, cad_realization.assembly, cad_realization.mappings
    ) == request.semantic_m10_v2_request_hash
    assert currentness.requests[-1] is synthesis_request
    evaluation = service.execute(
        candidate, synthesis_request, cad_realization, bridge, request
    )
    assert evaluation.schema_version == "candidate-multi-joint-m10-evaluation@2"
    assert currentness.requests[-1] is synthesis_request
    assert len(provider_calls) == 1

    # The application forwards this same typed request object to the service.
    app = ProductionApplication.__new__(ProductionApplication)
    app.project_id = candidate.source_binding.project_id
    app.candidate_multi_joint_m10_evaluation_service = service
    app.candidate_currentness_service = currentness
    app._execute_candidate_v2_sweep = provider
    app_evaluation = app.evaluate_candidate_multi_joint_m10(
        candidate, synthesis_request, cad_realization, bridge, request
    )
    assert app_evaluation == evaluation
    assert currentness.requests[-1] is synthesis_request
    assert len(provider_calls) == 2

    def result_replayer(replay_candidate, replay_synthesis_request, replay_request, replay_evaluation):
        assert replay_synthesis_request is synthesis_request
        low_request = service.reconstruct_m10_request(
            replay_candidate,
            replay_synthesis_request,
            cad_realization,
            bridge,
            replay_request,
        )
        low_result = _raw_m10_result(
            source_revision=replay_request.source_revision,
            source_state_hash=replay_request.source_state_hash,
            assembly=cad_realization.assembly,
            model=low_request.model,
            configurations=low_request.configurations,
            exact_pair_scope=low_request.exact_pair_scope,
            volume_tolerance_mm3=low_request.volume_tolerance_mm3,
            distance_tolerance_mm=low_request.distance_tolerance_mm,
        )
        return evaluation_models.CandidateMultiJointM10ReplayV2(
            low_request, low_result, cad_realization, bridge
        )

    selection = CandidateMultiJointSelectionService(
        project_id=candidate.source_binding.project_id,
        currentness_verifier=currentness,
        result_replayer=result_replayer,
    ).select(
        candidate,
        request,
        evaluation,
        "fixture-selector@1",
        "replay the typed request parent",
        synthesis_request=synthesis_request,
    )
    assert selection.schema_version == "candidate-multi-joint-selection@2"
    assert currentness.requests[-1] is synthesis_request
    assert len(provider_calls) == 2

    app_selection = app.select_candidate_multi_joint(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        request,
        evaluation,
        "fixture-selector@1",
        "replay the typed request parent",
    )
    assert app_selection == selection
    assert currentness.requests[-1] is synthesis_request
    assert len(provider_calls) == 3
    assert {
        "multi-joint-collision-pair-inventory@2": bridge.inventory.inventory_hash,
        "physical-to-m10-v2-bridge@2": bridge.physical_to_m10_bridge_hash,
        "candidate-multi-joint-m10-evaluation-request@2": request.request_hash,
        "candidate-multi-joint-m10-evaluation@2": evaluation.evaluation_hash,
        "candidate-multi-joint-selection@2": selection.selection_hash,
    } == {
        "multi-joint-collision-pair-inventory@2": "sha256:ddd1467b4c6e22d659520e1b81d02eed99aee112719cacfa729fe49dc38fe0dd",
        "physical-to-m10-v2-bridge@2": "sha256:b73b538032ddd536ddfa4df3e8c79af8e5db8bcefcf1a4557690d9b427eaa787",
        "candidate-multi-joint-m10-evaluation-request@2": "sha256:eeee2b0773550092328d52428e24ed669209f091d1608406f3a1acd443112778",
        "candidate-multi-joint-m10-evaluation@2": "sha256:33f10ceda3bd90cdfde6574c50f68909cb2230bc14064ae91415701deff010a4",
        "candidate-multi-joint-selection@2": "sha256:ea84737c6fda2eda634521f28a3065a84e550478fe64596b6591c36009b63739",
    }


def test_multi_joint_candidate_v2_hashes_preserve_scope_order_and_ignore_raw_assembly_names(tmp_path):
    state, manager, _, synthesis_request, _, candidate = (
        _candidate_with_m13_multi_joint_authority(tmp_path)
    )
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    scope = _multi_joint_scope(bridge.model.model_id)
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessSpy(manager),
        analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
    )
    baseline_request = service.build_request(
        candidate, synthesis_request, cad_realization, bridge, scope,
        cad_request=cad_request,
    )
    reordered_scope = _multi_joint_scope(
        bridge.model.model_id, positions=(30.0, 0.0)
    )
    reordered_request = service.build_request(
        candidate, synthesis_request, cad_realization, bridge, reordered_scope,
        cad_request=cad_request,
    )
    assert baseline_request.configuration_hashes != reordered_request.configuration_hashes
    assert baseline_request.request_hash != reordered_request.request_hash
    reordered_evaluation = service.execute(
        candidate, synthesis_request, cad_realization, bridge, reordered_request
    )

    renamed_assembly = cad_realization.assembly.model_copy(
        update={"assembly_id": "candidate-assembly-raw-name-rotation"}
    )
    renamed_cad = CandidateCadRealizationV2.model_validate(
        cad_realization.model_dump(mode="json")
        | {
            "assembly": renamed_assembly.model_dump(mode="json"),
            "assembly_hash": assembly_hash(renamed_assembly),
            "realization_hash": "pending",
        }
    )
    assert renamed_cad.assembly_hash != cad_realization.assembly_hash
    assert renamed_cad.realization_hash == cad_realization.realization_hash
    renamed_bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, renamed_cad, cad_request.placement_derivations
    )
    renamed_request = service.build_request(
        candidate, synthesis_request, renamed_cad, renamed_bridge, scope,
        cad_request=cad_request,
    )
    assert renamed_request.request_hash == baseline_request.request_hash
    baseline_evaluation = service.execute(
        candidate, synthesis_request, cad_realization, bridge, baseline_request
    )
    renamed_evaluation = service.execute(
        candidate, synthesis_request, renamed_cad, renamed_bridge, renamed_request
    )
    assert baseline_evaluation.evaluation_hash == renamed_evaluation.evaluation_hash
    assert reordered_evaluation.evaluation_hash != baseline_evaluation.evaluation_hash

    def select_with_replay(cad, candidate_bridge, mj_request, mj_evaluation):
        low_request = service.reconstruct_m10_request(
            candidate, synthesis_request, cad, candidate_bridge, mj_request
        )
        low_result = _raw_m10_result(
            source_revision=mj_request.source_revision,
            source_state_hash=mj_request.source_state_hash,
            assembly=cad.assembly,
            model=low_request.model,
            configurations=low_request.configurations,
            exact_pair_scope=low_request.exact_pair_scope,
            volume_tolerance_mm3=low_request.volume_tolerance_mm3,
            distance_tolerance_mm=low_request.distance_tolerance_mm,
        )
        return CandidateMultiJointSelectionService(
            project_id=candidate.source_binding.project_id,
            currentness_verifier=CandidateCurrentnessService(manager),
            result_replayer=lambda *_args: evaluation_models.CandidateMultiJointM10ReplayV2(
                low_request, low_result, cad, candidate_bridge
            ),
        ).select(
            candidate,
            mj_request,
            mj_evaluation,
            "stable-selector@1",
            "same semantic multi-joint result",
            synthesis_request=synthesis_request,
        )

    baseline_selection = select_with_replay(
        cad_realization, bridge, baseline_request, baseline_evaluation
    )
    renamed_selection = select_with_replay(
        renamed_cad, renamed_bridge, renamed_request, renamed_evaluation
    )
    assert baseline_selection.selection_hash == renamed_selection.selection_hash


def test_candidate_m10_v2_full_chain_closes_realization_and_candidate_set_ordering(tmp_path):
    state, manager, _, synthesis_request, _, initial_candidate = (
        _candidate_with_m13_multi_joint_authority(tmp_path)
    )
    # Explicit fixture choices exercise case 93's candidate-level set order on
    # an otherwise eligible candidate. The unresolved-item multiset cases are
    # owned by the candidate R-P5.1 regression suite.
    choice_a = CandidateDesignVariable(name="case93-choice-a", value=1.0)
    choice_b = CandidateDesignVariable(name="case93-choice-b", value=2.0)
    candidate = type(initial_candidate).model_validate(
        initial_candidate.model_dump(mode="json")
        | {
            "design_variables": [
                *(item.model_dump(mode="json") for item in initial_candidate.design_variables),
                choice_b.model_dump(mode="json"),
                choice_a.model_dump(mode="json"),
            ],
            "candidate_hash": "pending",
        }
    )
    realization = candidate.realization

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
    reordered_realization = PhysicalMechanismRealization.model_validate(
        realization.model_dump(mode="json")
        | {
            "components": list(reversed(component_records)),
            "connections": list(reversed(connection_records)),
            "joint_bindings": list(reversed(joint_records)),
            "realization_hash": "pending",
        }
    )
    reordered_candidate = type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "component_specifications": list(
                reversed(candidate.component_specifications)
            ),
            "realization": reordered_realization.model_dump(mode="json"),
            "design_variables": list(reversed(candidate.design_variables)),
            "unresolved_items": list(reversed(candidate.unresolved_items)),
            "candidate_hash": "pending",
        }
    )
    assert reordered_candidate.candidate_hash == candidate.candidate_hash
    assert reordered_realization.realization_hash != realization.realization_hash
    assert (
        semantic_candidate_mechanism_hash(reordered_realization)
        == semantic_candidate_mechanism_hash(realization)
    )

    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    reordered_cad_request, reordered_cad = _candidate_cad_v2(
        reordered_candidate, synthesis_request, state
    )
    assert reordered_cad_request.request_hash == cad_request.request_hash
    assert reordered_cad.realization_hash == cad_realization.realization_hash
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    reordered_bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        reordered_candidate,
        reordered_cad,
        reordered_cad_request.placement_derivations,
    )
    assert reordered_bridge.inventory.inventory_hash == bridge.inventory.inventory_hash
    assert reordered_bridge.physical_to_m10_bridge_hash == bridge.physical_to_m10_bridge_hash

    scope = _multi_joint_scope(bridge.model.model_id)
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessSpy(manager),
        analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
    )
    request = service.build_request(
        candidate, synthesis_request, cad_realization, bridge, scope,
        cad_request=cad_request,
    )
    reordered_request = service.build_request(
        reordered_candidate,
        synthesis_request,
        reordered_cad,
        reordered_bridge,
        scope,
        cad_request=reordered_cad_request,
    )
    assert reordered_request.request_hash == request.request_hash
    evaluation = service.execute(
        candidate, synthesis_request, cad_realization, bridge, request
    )
    reordered_evaluation = service.execute(
        reordered_candidate,
        synthesis_request,
        reordered_cad,
        reordered_bridge,
        reordered_request,
    )
    assert reordered_evaluation.evaluation_hash == evaluation.evaluation_hash

    def select_with_replay(candidate_record, cad, candidate_bridge, mj_request, mj_evaluation):
        low_request = service.reconstruct_m10_request(
            candidate_record, synthesis_request, cad, candidate_bridge, mj_request
        )
        low_result = _raw_m10_result(
            source_revision=mj_request.source_revision,
            source_state_hash=mj_request.source_state_hash,
            assembly=cad.assembly,
            model=low_request.model,
            configurations=low_request.configurations,
            exact_pair_scope=low_request.exact_pair_scope,
            volume_tolerance_mm3=low_request.volume_tolerance_mm3,
            distance_tolerance_mm=mj_request.scope.distance_tolerance_mm,
        )
        return CandidateMultiJointSelectionService(
            project_id=candidate_record.source_binding.project_id,
            currentness_verifier=CandidateCurrentnessService(manager),
            result_replayer=lambda *_args: evaluation_models.CandidateMultiJointM10ReplayV2(
                low_request, low_result, cad, candidate_bridge
            ),
        ).select(
            candidate_record,
            mj_request,
            mj_evaluation,
            "case89-selector@1",
            "set-semantic candidate identities are invariant",
            synthesis_request=synthesis_request,
        )

    selection = select_with_replay(
        candidate, cad_realization, bridge, request, evaluation
    )
    reordered_selection = select_with_replay(
        reordered_candidate, reordered_cad, reordered_bridge,
        reordered_request, reordered_evaluation,
    )
    assert reordered_selection.selection_hash == selection.selection_hash

    # Case 90's bearing A/B order is engineering-significant and propagates
    # through the candidate CAD/M10 chain rather than being set-normalized.
    support_realization_payload = candidate.realization.model_dump(mode="json")
    support_binding = support_realization_payload["joint_bindings"][0]
    support_binding["support_instance_ids"] = list(
        reversed(support_binding["support_instance_ids"])
    )
    support_realization = PhysicalMechanismRealization.model_validate(
        support_realization_payload | {"realization_hash": "pending"}
    )
    support_order_candidate = type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "realization": support_realization.model_dump(mode="json"),
            "candidate_hash": "pending",
        }
    )
    assert support_order_candidate.candidate_hash != candidate.candidate_hash
    assert semantic_candidate_mechanism_hash(support_order_candidate.realization) != (
        semantic_candidate_mechanism_hash(candidate.realization)
    )
    support_cad_request, support_cad = _candidate_cad_v2(
        support_order_candidate, synthesis_request, state
    )
    support_bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        support_order_candidate, support_cad, support_cad_request.placement_derivations
    )
    support_request = service.build_request(
        support_order_candidate,
        synthesis_request,
        support_cad,
        support_bridge,
        scope,
        cad_request=support_cad_request,
    )
    support_evaluation = service.execute(
        support_order_candidate,
        synthesis_request,
        support_cad,
        support_bridge,
        support_request,
    )
    support_selection = select_with_replay(
        support_order_candidate,
        support_cad,
        support_bridge,
        support_request,
        support_evaluation,
    )
    assert support_cad_request.request_hash != cad_request.request_hash
    assert tuple(item.mapping_hash for item in support_cad.mappings) != tuple(
        item.mapping_hash for item in cad_realization.mappings
    )
    assert support_cad.realization_hash != cad_realization.realization_hash
    assert support_bridge.physical_to_m10_bridge_hash != (
        bridge.physical_to_m10_bridge_hash
    )
    assert support_bridge.inventory.inventory_hash != bridge.inventory.inventory_hash
    assert support_request.request_hash != request.request_hash
    assert support_evaluation.evaluation_hash != evaluation.evaluation_hash
    assert support_selection.selection_hash != selection.selection_hash

    axis_change_payload = candidate.realization.model_dump(mode="json")
    axis_change_payload["physical_revolute_joint_bindings"][0]["axis_sign"] = -1
    axis_change_payload["physical_revolute_joint_bindings"][0]["binding_hash"] = "pending"
    axis_change_payload["realization_hash"] = "pending"
    axis_changed_realization = PhysicalMechanismRealization.model_validate(
        axis_change_payload
    )
    axis_changed_candidate = type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "realization": axis_changed_realization.model_dump(mode="json"),
            "candidate_hash": "pending",
        }
    )
    assert axis_changed_candidate.candidate_hash != candidate.candidate_hash
    assert semantic_candidate_mechanism_hash(axis_changed_realization) != (
        semantic_candidate_mechanism_hash(candidate.realization)
    )
    axis_cad_request, axis_cad = _candidate_cad_v2(
        axis_changed_candidate, synthesis_request, state
    )
    axis_bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        axis_changed_candidate, axis_cad, axis_cad_request.placement_derivations
    )
    assert axis_bridge.physical_to_m10_bridge_hash != bridge.physical_to_m10_bridge_hash


def test_candidate_semantic_chain_through_multi_joint_selection_ignores_raw_step_rotation(tmp_path):
    state_a, manager, store, synthesis_a, policy_a, candidate_a = (
        _candidate_with_m13_multi_joint_authority(tmp_path, variant="A")
    )
    state_b, _, _, synthesis_b, policy_b, candidate_b = (
        _candidate_with_m13_multi_joint_authority(
            tmp_path, variant="B", manager=manager, store=store
        )
    )
    assert synthesis_a.semantic_source_binding_hash == synthesis_b.semantic_source_binding_hash
    assert synthesis_a.request_hash == synthesis_b.request_hash
    assert candidate_a.candidate_hash == candidate_b.candidate_hash
    assert candidate_a.realization.realization_hash != candidate_b.realization.realization_hash
    assert semantic_candidate_mechanism_hash(candidate_a.realization) == (
        semantic_candidate_mechanism_hash(candidate_b.realization)
    )

    m12_service = RevoluteDriveRealizationService()
    admissibility_a = m12_service.evaluate(
        candidate_a, synthesis_a, policy_a, _policy_requirements(), source_state=state_a
    )
    admissibility_b = m12_service.evaluate(
        candidate_b, synthesis_b, policy_b, _policy_requirements(), source_state=state_b
    )
    assert admissibility_a.result_hash == admissibility_b.result_hash

    cad_request_a, cad_a = _candidate_cad_v2(candidate_a, synthesis_a, state_a)
    cad_request_b, cad_b = _candidate_cad_v2(candidate_b, synthesis_b, state_b)
    assert cad_a.assembly_hash != cad_b.assembly_hash
    assert cad_a.realization_hash == cad_b.realization_hash
    bridge_a = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate_a, cad_a, cad_request_a.placement_derivations
    )
    bridge_b = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate_b, cad_b, cad_request_b.placement_derivations
    )
    for field in bridge_models.PhysicalToM10V2BridgeV2.model_fields:
        if field != "physical_to_m10_bridge_hash":
            assert getattr(bridge_a, field) == getattr(bridge_b, field), field
    assert bridge_a.physical_to_m10_bridge_hash == bridge_b.physical_to_m10_bridge_hash
    scope = _multi_joint_scope(bridge_a.model.model_id)
    provider = _raw_m10_result
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessSpy(manager),
        analyze_multi_joint_collision_sweep_v2=provider,
    )
    request_a = service.build_request(
        candidate_a, synthesis_a, cad_a, bridge_a, scope, cad_request=cad_request_a
    )
    request_b = service.build_request(
        candidate_b, synthesis_b, cad_b, bridge_b, scope, cad_request=cad_request_b
    )
    assert request_a.request_hash == request_b.request_hash
    evaluation_a = service.execute(candidate_a, synthesis_a, cad_a, bridge_a, request_a)
    evaluation_b = service.execute(candidate_b, synthesis_b, cad_b, bridge_b, request_b)
    assert evaluation_a.evaluation_hash == evaluation_b.evaluation_hash

    def select(candidate, synthesis, cad, bridge, request, evaluation):
        low_request = service.reconstruct_m10_request(
            candidate, synthesis, cad, bridge, request
        )
        low_result = _raw_m10_result(
            source_revision=request.source_revision,
            source_state_hash=request.source_state_hash,
            assembly=cad.assembly,
            model=low_request.model,
            configurations=low_request.configurations,
            exact_pair_scope=low_request.exact_pair_scope,
            volume_tolerance_mm3=low_request.volume_tolerance_mm3,
            distance_tolerance_mm=low_request.distance_tolerance_mm,
        )
        return CandidateMultiJointSelectionService(
            project_id=candidate.source_binding.project_id,
            currentness_verifier=CandidateCurrentnessService(manager),
            result_replayer=lambda *_args: evaluation_models.CandidateMultiJointM10ReplayV2(
                low_request, low_result, cad, bridge
            ),
        ).select(
            candidate,
            request,
            evaluation,
            "stable-selector@1",
            "timestamp and artifact-ID invariant selection",
            synthesis_request=synthesis,
        )

    selection_a = select(
        candidate_a, synthesis_a, cad_a, bridge_a, request_a, evaluation_a
    )
    selection_b = select(
        candidate_b, synthesis_b, cad_b, bridge_b, request_b, evaluation_b
    )
    assert selection_a.selection_hash == selection_b.selection_hash


def test_multi_joint_request_v2_derivation_hash_is_none_iff_derivations_are_empty(tmp_path):
    state, manager, _, synthesis_request, _, candidate = (
        _candidate_with_m13_multi_joint_authority(tmp_path)
    )
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    scope = _multi_joint_scope(bridge.model.model_id)
    request = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessSpy(manager),
        analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
    ).build_request(
        candidate, synthesis_request, cad_realization, bridge, scope,
        cad_request=cad_request,
    )
    assert request.placement_derivations == ()
    assert request.semantic_placement_derivations_hash is None
    with pytest.raises(ValueError, match="None|empty|derivation"):
        evaluation_models.CandidateMultiJointM10EvaluationRequestV2.model_validate(
            request.model_dump(mode="json")
            | {
                "semantic_placement_derivations_hash": semantic_placement_derivations_hash(()),
                "request_hash": "pending",
            }
        )
    derivation = _coaxial(
        source_physical_instance_id="drive-motor",
        target_physical_instance_id="output-shaft",
    )
    with_derivation = evaluation_models.CandidateMultiJointM10EvaluationRequestV2.model_validate(
        request.model_dump(mode="json")
        | {
            "placement_derivations": [derivation.model_dump(mode="json")],
            "semantic_placement_derivations_hash": semantic_placement_derivations_hash(
                (derivation,)
            ),
            "request_hash": "pending",
        }
    )
    assert with_derivation.semantic_placement_derivations_hash == (
        semantic_placement_derivations_hash((derivation,))
    )
    assert "semantic_placement_derivations_hash" not in (
        evaluation_models.CandidateMultiJointM10EvaluationV2.model_fields
    )
