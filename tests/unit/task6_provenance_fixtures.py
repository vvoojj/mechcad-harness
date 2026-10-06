from __future__ import annotations

import hashlib
import json

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_compilation import MountingPlateDesignSpec, compile_mounting_plate
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram, cad_program_hash
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateCadRealization,
    CandidateCadRealizationRequest,
    CandidateCadStageOutcome,
    CandidateCadStageStatus,
    CandidateComparisonDirection,
    CandidateComparisonPolicy,
    CandidateComparisonRequest,
    CandidateCurrentness,
    CandidateEvaluationCurrentnessService,
    CandidateEvaluationPolicy,
    CandidateGeometryFidelity,
    CandidateM10Binding,
    CandidateM10BodyDisposition,
    CandidateM10ConstituentDisposition,
    CandidateM10EvaluationRequest,
    CandidateM10EvaluationScope,
    CandidateM10PairClassification,
    CandidateM10PairScopeRequirement,
    CandidateMetricKey,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
    ComponentPropertySnapshot,
    ComponentSpecificationSnapshot,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
)
from mechcad_harness.candidates.cad_realization import CandidateCadRealizationService
from mechcad_harness.continuous_proof import (
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
    ContinuousIntervalCertificate,
    ContinuousPairCertificate,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisProofStatus,
)
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.kinematic_sweep import (
    CadKinematicCollisionPairResult,
    CadKinematicSweepRequest,
    CadKinematicSweepResult,
    CadKinematicSweepSample,
    CollisionClassification,
    transformed_assembly_program,
)
from mechcad_harness.models import DesignState
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
from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    CanonicalPhysicalMechanismCompiler,
    ProjectArtifactResolver,
)
from mechcad_harness.candidates import PromotableMechanismProjection, PrePromotionM10ScopeProjection
from mechcad_harness.models.evidence import Evidence
from mechcad_harness.multi_joint_kinematics import KinematicModel, RevoluteJointModel
from mechcad_harness.revolute_drive import (
    EngineeringCheck,
    EngineeringCheckStatus,
    RevoluteDriveAdmissibilityResult,
)
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.state.hashing import canonical_json


def make_state() -> DesignState:
    return DesignState(
        id="DES-M12-4",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )


def make_candidate_for_specification(
    state: DesignState,
    *,
    specification: ComponentSpecificationSnapshot,
    instance_id: str = "mount",
    role: PhysicalComponentRole = PhysicalComponentRole.MOUNT_OR_SUPPORT,
):
    source = CandidateSourceBinding(
        project_id="PRJ-M12-4",
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path="/id",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
        ),
    ).bound_to(state)
    request = CandidateSynthesisRequest(source_binding=source)
    policy = CandidateSynthesisPolicy()
    candidate = MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=request.request_hash,
        synthesis_policy_hash=policy.policy_hash,
        component_specifications=(specification,),
        realization=PhysicalMechanismRealization(
            components=(
                PhysicalComponentInstance(
                    instance_id=instance_id,
                    specification_hash=specification.specification_hash,
                    role=role,
                    interfaces=specification.interfaces,
                ),
            )
        ),
        generator_identity="m12-4-test-generator",
        generator_version="1",
    )
    return candidate, request, policy


def make_cad_service(tmp_path, manager):
    return CandidateCadRealizationService(
        workspace=tmp_path,
        project_id="PRJ-M12-4",
        state_manager=manager,
    )


def make_candidate_cad_fixture(tmp_path):
    state = make_state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    source = CandidateSourceBinding(
        project_id="PRJ-M12-4",
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path="/id",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
        ),
    ).bound_to(state)
    properties = tuple(
        ComponentPropertySnapshot(
            key=key,
            availability=ComponentPropertyAvailability.AVAILABLE,
            normalized_value=value,
            canonical_unit="mm",
            source_identity="candidate:plate-dimensions@1",
            authority=ComponentPropertyAuthority.USER_DECLARED,
        )
        for key, value in (
            ("geometry.length_mm", 40.0),
            ("geometry.width_mm", 30.0),
            ("geometry.thickness_mm", 5.0),
        )
    )
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
        properties=properties,
    )
    synthesis_request = CandidateSynthesisRequest(source_binding=source)
    policy = CandidateSynthesisPolicy()
    candidate = MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=policy.policy_hash,
        component_specifications=(specification,),
        realization=PhysicalMechanismRealization(
            components=(
                PhysicalComponentInstance(
                    instance_id="mount",
                    specification_hash=specification.specification_hash,
                    role=PhysicalComponentRole.MOUNT_OR_SUPPORT,
                ),
            )
        ),
        generator_identity="m12-4-test-generator",
        generator_version="1",
    )
    plate = MountingPlateDesignSpec(
        part_id="cad_mount",
        plate_length_mm=40.0,
        plate_width_mm=30.0,
        plate_thickness_mm=5.0,
    )
    transform = CadRigidTransform()
    origin = {
        "authority": "deterministic_derived_relation",
        "input_identities": ("candidate:/realization/components/mount",),
        "derivation": "fixed-home-placement@1",
        "transform": transform,
    }
    mapping = CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id="mount",
        cad_instance_id="cad_mount",
        fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
        representation_identity=cad_program_hash(compile_mounting_plate(plate)),
        geometry_definition_identities=tuple(item.property_hash for item in properties),
        placement=transform,
        placement_origin=origin,
    )
    cad_request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=source,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("mount",),
        mappings=(mapping,),
    )
    return make_cad_service(tmp_path, manager), candidate, synthesis_request, policy, cad_request


def _foundation_candidate(state: DesignState):
    source = CandidateSourceBinding(
        project_id="PRJ-M12",
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path="/id",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
        ),
    ).bound_to(state)
    motor = ComponentSpecificationSnapshot(
        component_type="motor",
        manufacturer="Example Motion",
        part_number="MTR-24-100",
        source_identity="datasheet:example:MTR-24-100@1",
        properties=(
            ComponentPropertySnapshot(
                key="rated_voltage",
                availability=ComponentPropertyAvailability.AVAILABLE,
                normalized_value=24.0,
                canonical_unit="V",
                source_identity="datasheet:example:MTR-24-100@1",
                authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
            ),
            ComponentPropertySnapshot(
                key="continuous_torque",
                availability=ComponentPropertyAvailability.MISSING,
                source_identity="datasheet:example:MTR-24-100@1",
                authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
            ),
        ),
        interfaces=("output-shaft", "mount-face"),
    )
    shaft = ComponentSpecificationSnapshot(
        component_type="shaft",
        source_identity="custom:shaft@1",
        properties=(
            ComponentPropertySnapshot(
                key="diameter",
                availability=ComponentPropertyAvailability.AVAILABLE,
                normalized_value=12.0,
                canonical_unit="mm",
                source_identity="drawing:shaft@1",
                authority=ComponentPropertyAuthority.USER_DECLARED,
            ),
        ),
        interfaces=("motor-side", "hub-side", "journal-a", "journal-b"),
    )
    bearing = ComponentSpecificationSnapshot(
        component_type="bearing",
        source_identity="catalog:bearing@1",
        properties=(
            ComponentPropertySnapshot(
                key="dynamic_load_rating",
                availability=ComponentPropertyAvailability.NOT_APPLICABLE,
                source_identity="catalog:bearing@1",
                authority=ComponentPropertyAuthority.DISTRIBUTOR_LISTING,
            ),
        ),
        interfaces=("bore", "housing"),
    )
    hub = ComponentSpecificationSnapshot(
        component_type="hub", source_identity="custom:hub@1", interfaces=("shaft", "body")
    )
    mount = ComponentSpecificationSnapshot(
        component_type="mount", source_identity="custom:mount@1", interfaces=("motor", "frame")
    )
    body = ComponentSpecificationSnapshot(
        component_type="driven-body", source_identity="custom:body@1", interfaces=("hub", "payload")
    )
    specifications = (motor, shaft, bearing, hub, mount, body)
    components = (
        PhysicalComponentInstance(
            instance_id="motor", specification_hash=motor.specification_hash,
            role=PhysicalComponentRole.ACTUATOR, interfaces=motor.interfaces,
        ),
        PhysicalComponentInstance(
            instance_id="driver", specification_hash=motor.specification_hash,
            role=PhysicalComponentRole.TRANSMISSION, interfaces=motor.interfaces,
        ),
        PhysicalComponentInstance(
            instance_id="shaft", specification_hash=shaft.specification_hash,
            role=PhysicalComponentRole.SHAFT, interfaces=shaft.interfaces,
        ),
        PhysicalComponentInstance(
            instance_id="bearing", specification_hash=bearing.specification_hash,
            role=PhysicalComponentRole.BEARING, interfaces=bearing.interfaces,
        ),
        PhysicalComponentInstance(
            instance_id="hub", specification_hash=hub.specification_hash,
            role=PhysicalComponentRole.HUB_OR_COUPLING, interfaces=hub.interfaces,
        ),
        PhysicalComponentInstance(
            instance_id="mount", specification_hash=mount.specification_hash,
            role=PhysicalComponentRole.MOUNT_OR_SUPPORT, interfaces=mount.interfaces,
        ),
        PhysicalComponentInstance(
            instance_id="body", specification_hash=body.specification_hash,
            role=PhysicalComponentRole.DRIVEN_BODY, interfaces=body.interfaces,
        ),
    )
    realization = PhysicalMechanismRealization(components=components)
    request = CandidateSynthesisRequest(source_binding=source)
    policy = CandidateSynthesisPolicy(
        entries=(
            ("allow-direct-drive", "direct_drive", "hard_admissibility"),
            ("preferred-voltage", "24 V", "preference"),
        )
    )
    candidate = MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=request.request_hash,
        synthesis_policy_hash=policy.policy_hash,
        component_specifications=specifications,
        realization=realization,
        generator_identity="fixture-generator",
        generator_version="1",
    )
    return candidate, request, policy


def make_evaluation_candidate(state: DesignState):
    base, _, policy = _foundation_candidate(state)
    specifications = {item.source_identity: item for item in base.component_specifications}
    motor = specifications["datasheet:example:MTR-24-100@1"]
    bearing = specifications["catalog:bearing@1"]
    components = (
        PhysicalComponentInstance(instance_id="motor", specification_hash=motor.specification_hash, role=PhysicalComponentRole.ACTUATOR, interfaces=motor.interfaces),
        PhysicalComponentInstance(instance_id="driver", specification_hash=motor.specification_hash, role=PhysicalComponentRole.TRANSMISSION, interfaces=motor.interfaces),
        PhysicalComponentInstance(instance_id="shaft", specification_hash=specifications["custom:shaft@1"].specification_hash, role=PhysicalComponentRole.SHAFT, interfaces=specifications["custom:shaft@1"].interfaces),
        PhysicalComponentInstance(instance_id="bearing", specification_hash=bearing.specification_hash, role=PhysicalComponentRole.BEARING, interfaces=bearing.interfaces),
        PhysicalComponentInstance(instance_id="hub", specification_hash=specifications["custom:hub@1"].specification_hash, role=PhysicalComponentRole.HUB_OR_COUPLING, interfaces=specifications["custom:hub@1"].interfaces),
        PhysicalComponentInstance(instance_id="mount", specification_hash=specifications["custom:mount@1"].specification_hash, role=PhysicalComponentRole.MOUNT_OR_SUPPORT, interfaces=specifications["custom:mount@1"].interfaces),
        PhysicalComponentInstance(instance_id="body", specification_hash=specifications["custom:body@1"].specification_hash, role=PhysicalComponentRole.DRIVEN_BODY, interfaces=specifications["custom:body@1"].interfaces),
    )
    request = CandidateSynthesisRequest(source_binding=base.source_binding)
    return (
        MechanicalDesignCandidate(
            source_binding=base.source_binding,
            synthesis_request_hash=request.request_hash,
            synthesis_policy_hash=policy.policy_hash,
            component_specifications=base.component_specifications,
            realization=PhysicalMechanismRealization(components=components),
            generator_identity=base.generator_identity,
            generator_version=base.generator_version,
        ),
        request,
        policy,
    )


def make_realization() -> CandidateCadRealization:
    names = ("motor", "driver", "shaft", "bearing", "hub", "mount", "body")
    parts = tuple(
        CadPartProgram(
            part_id=f"part-{name}",
            operations=(BasePlateOperation(operation_id=f"base-{name}", length_mm=10, width_mm=10, thickness_mm=2),),
        )
        for name in names
    )
    mappings = tuple(
        CandidateCadInstanceMapping(
            candidate_hash="sha256:" + "a" * 64,
            physical_instance_id=name,
            cad_instance_id=f"cad-{name}",
            fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
            representation_identity=cad_program_hash(parts[index]),
            geometry_definition_identities=(f"candidate:geometry:{name}",),
            placement=CadRigidTransform(x_mm=float(index * 20)),
            placement_origin={
                "authority": "deterministic_derived_relation",
                "input_identities": (f"candidate:placement:{name}",),
                "derivation": "fixture-placement@1",
                "transform": CadRigidTransform(x_mm=float(index * 20)),
            },
        )
        for index, name in enumerate(names)
    )
    assembly = CadAssemblyProgram(
        assembly_id="candidate-assembly",
        parts=parts,
        instances=tuple(
            CadComponentInstance(
                instance_id=f"cad-{name}", part_id=f"part-{name}", placement=mapping.placement
            )
            for name, mapping in zip(names, mappings, strict=True)
        ),
    )
    return CandidateCadRealization(
        candidate_hash="sha256:" + "a" * 64,
        request_hash="sha256:" + "b" * 64,
        mappings=mappings,
        assembly=assembly,
        assembly_hash=assembly_hash(assembly),
        compiler_identity="test-compiler",
        compiler_version="1",
        provider_identity="test-provider",
    )


def make_binding(realization: CandidateCadRealization, *, driver_gear_constituent_key=None):
    dispositions = {
        "motor": CandidateM10BodyDisposition.FIXED,
        "driver": CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED,
        "shaft": CandidateM10BodyDisposition.OUTPUT_RIGID,
        "bearing": CandidateM10BodyDisposition.FIXED,
        "hub": CandidateM10BodyDisposition.OUTPUT_RIGID,
        "mount": CandidateM10BodyDisposition.FIXED,
        "body": CandidateM10BodyDisposition.OUTPUT_RIGID,
    }
    groups = {"shaft": "output-joint", "hub": "output-joint", "body": "output-joint"}
    return CandidateM10Binding(
        candidate_hash=realization.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        model=KinematicModel(
            model_id="m12-output-model",
            joints=(
                RevoluteJointModel(
                    joint_id="output-joint",
                    parent_instance_id="cad-mount",
                    child_instance_id="cad-shaft",
                    axis_origin_x_mm=20,
                    axis_direction_z=1,
                ),
            ),
        ),
        output_joint_id="output-joint",
        driver_gear_constituent_key=driver_gear_constituent_key,
        output_axis={
            "origin_x_mm": 120,
            "origin_y_mm": 0,
            "origin_z_mm": 0,
            "direction_x": 0,
            "direction_y": 0,
            "direction_z": 1,
            "frame_id": "joint:output-joint",
        },
        constituent_dispositions=tuple(
            CandidateM10ConstituentDisposition(
                physical_instance_id=name,
                cad_instance_id=f"cad-{name}",
                constituent_key=name,
                disposition=dispositions[name],
                output_transform_group=groups.get(name),
            )
            for name in dispositions
        ),
    )


def make_scope() -> CandidateM10EvaluationScope:
    return CandidateM10EvaluationScope(
        output_joint_semantic_key="primary-output-revolute",
        angle_interval_deg=(-45.0, 45.0),
        required_clearance_mm=1.0,
        pair_scope_requirements=(
            CandidateM10PairScopeRequirement(
                requirement_key="hub-mount-clearance",
                first_constituent_key="hub",
                second_constituent_key="mount",
                required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
            ),
            CandidateM10PairScopeRequirement(
                requirement_key="shaft-bearing-contact",
                first_constituent_key="shaft",
                second_constituent_key="bearing",
                required_classification=CandidateM10PairClassification.INTENDED_CONTACT_EXCLUDED,
            ),
            CandidateM10PairScopeRequirement(
                requirement_key="driver-internal-motion",
                first_constituent_key="driver",
                second_constituent_key="mount",
                required_classification=CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE,
                requires_home_exact_check=True,
            ),
        ),
        fidelity_requirements=(
            ("hub", CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION),
            ("mount", CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION),
        ),
        required_home_check_semantics=("exact-home-nonintended-interference@1",),
        proof_service_version="m10-single-axis-continuous-proof@1",
        policy_assumptions=("unmodeled-internal-motion-is-not-continuously-certified",),
    )


def make_inventory(realization, binding, scope):
    from mechcad_harness.candidates import CandidateCollisionPairClassification, CandidateCollisionPairInventory

    ids = tuple(sorted(instance.instance_id for instance in realization.assembly.instances))
    required = {
        tuple(sorted((f"cad-{item.first_constituent_key}", f"cad-{item.second_constituent_key}"))): item
        for item in scope.pair_scope_requirements
    }
    classifications = []
    for index, first in enumerate(ids):
        for second in ids[index + 1 :]:
            pair = (first, second)
            requirement = required.get(pair)
            kind = requirement.required_classification if requirement else CandidateM10PairClassification.OTHER_EXPLICIT_OUT_OF_SCOPE
            classifications.append(
                CandidateCollisionPairClassification(
                    pair=pair,
                    classification=kind,
                    reason=None if kind is CandidateM10PairClassification.CHECK_CLEARANCE else "not required by the declared M10 engineering scope",
                    requires_home_exact_check=bool(requirement and requirement.requires_home_exact_check),
                )
            )
    return CandidateCollisionPairInventory.complete_for(realization, binding, scope, tuple(classifications))


def make_proof_result(kwargs, status=ContinuousSingleAxisProofStatus.VERIFIED_CLEAR):
    request = ContinuousSingleAxisProofRequest(
        source_assembly_id=kwargs["assembly"].assembly_id,
        source_assembly_hash=assembly_hash(kwargs["assembly"]),
        axis=kwargs["axis"],
        start_angle_deg=kwargs["start_angle_deg"],
        end_angle_deg=kwargs["end_angle_deg"],
        moving_instance_ids=kwargs["moving_instance_ids"],
        stationary_instance_ids=kwargs["stationary_instance_ids"],
        required_clearance_mm=kwargs["required_clearance_mm"],
        proof_guard_mm=kwargs["proof_guard_mm"],
        max_depth=kwargs["max_depth"],
        minimum_interval_deg=kwargs["minimum_interval_deg"],
        max_exact_evaluations=kwargs["max_exact_evaluations"],
    )
    certificate = ContinuousIntervalCertificate(
        interval_start_deg=request.start_angle_deg,
        interval_end_deg=request.end_angle_deg,
        reference_angle_deg=request.start_angle_deg,
        pair_certificates=(
            ContinuousPairCertificate(
                moving_instance_id=request.moving_instance_ids[0],
                stationary_instance_id=request.stationary_instance_ids[0],
                exact_distance_mm=10.0,
                radial_bound_mm=1.0,
                angular_motion_bound_mm=0.1,
                certified_lower_clearance_mm=9.9,
            ),
        ),
        minimum_certified_lower_clearance_mm=9.9,
    )
    result = ContinuousSingleAxisProofResult(
        request_hash=request.request_hash,
        source_assembly_hash=request.source_assembly_hash,
        proof_algorithm_version=CONTINUOUS_PROOF_ALGORITHM_VERSION,
        axis=request.axis,
        start_angle_deg=request.start_angle_deg,
        end_angle_deg=request.end_angle_deg,
        moving_instance_ids=request.moving_instance_ids,
        stationary_instance_ids=request.stationary_instance_ids,
        required_clearance_mm=request.required_clearance_mm,
        proof_guard_mm=request.proof_guard_mm,
        status=status,
        certified_leaf_certificates=(certificate,) if status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR else (),
        unresolved_intervals=() if status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR else ((request.start_angle_deg, request.end_angle_deg),),
        exact_evaluations_count=1,
        maximum_depth_reached=0,
    )
    if status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS:
        from mechcad_harness.continuous_proof import ContinuousCollisionWitness

        result = result.model_copy(update={
            "collision_witness": ContinuousCollisionWitness(
                witness_angle_deg=request.start_angle_deg,
                moving_instance_id=request.moving_instance_ids[0],
                stationary_instance_id=request.stationary_instance_ids[0],
                interference_volume_mm3=1.0,
                exact_distance_mm=0.0,
                classification="interference",
            )
        })
    payload = result.model_dump(mode="json", exclude={"result_hash"})
    return result.model_copy(update={"result_hash": "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()})


def make_home_result(kwargs, *, collision=False):
    request = CadKinematicSweepRequest(
        source_assembly_id=kwargs["assembly"].assembly_id,
        source_assembly_hash=assembly_hash(kwargs["assembly"]),
        axis=kwargs["axis"],
        sample_angles_deg=(0.0,),
        moving_instance_ids=kwargs["moving_instance_ids"],
        stationary_instance_ids=kwargs["stationary_instance_ids"],
    )
    classification = CollisionClassification.INTERFERENCE if collision else CollisionClassification.POSITIVE_CLEARANCE
    pair = CadKinematicCollisionPairResult(
        moving_instance_id=request.moving_instance_ids[0],
        stationary_instance_id=request.stationary_instance_ids[0],
        interference_volume_mm3=1.0 if collision else 0.0,
        exact_distance_mm=0.0 if collision else 5.0,
        classification=classification,
    )
    sample = CadKinematicSweepSample(
        angle_deg=0.0,
        transformed_assembly_hash=assembly_hash(
            transformed_assembly_program(
                kwargs["assembly"], kwargs["axis"], 0.0,
                kwargs["moving_instance_ids"], kwargs["stationary_instance_ids"],
            )
        ),
        pair_results=(pair,),
        maximum_interference_volume_mm3=pair.interference_volume_mm3,
        minimum_exact_distance_mm=pair.exact_distance_mm,
        classification=classification,
    )
    return CadKinematicSweepResult.from_samples(request, (sample,))


def make_m10_request(realization, binding, scope):
    return CandidateM10EvaluationRequest(
        candidate_hash=realization.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding.model_hash,
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in realization.mappings)),
        inventory=make_inventory(realization, binding, scope),
    )


def make_bound_m10_inputs(candidate):
    base_realization = make_realization()
    realization = CandidateCadRealization.model_validate(
        base_realization.model_dump(mode="json")
        | {
            "candidate_hash": candidate.candidate_hash,
            "mappings": [
                mapping.model_dump(mode="json")
                | {"candidate_hash": candidate.candidate_hash, "mapping_hash": "pending"}
                for mapping in base_realization.mappings
            ],
            "realization_hash": "pending",
        }
    )
    cad_request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-evaluation-fixture@1",
        compiler_identity="fixture",
        compiler_version="1",
        candidate_instance_ids=tuple(mapping.physical_instance_id for mapping in realization.mappings),
        mappings=realization.mappings,
    )
    realization = CandidateCadRealization.model_validate(
        realization.model_dump(mode="json")
        | {"request_hash": cad_request.request_hash, "realization_hash": "pending"}
    )
    binding = make_binding(realization)
    base_scope = make_scope()
    scope = type(base_scope).model_validate(
        base_scope.model_dump(mode="python")
        | {"pair_scope_requirements": (base_scope.pair_scope_requirements[0],), "scope_hash": "pending"}
    )
    request = make_m10_request(realization, binding, scope)
    from mechcad_harness.candidates import CandidateM10EvaluationService

    m10 = CandidateM10EvaluationService(
        lambda **kwargs: make_proof_result(kwargs),
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("home check not required")),
        scope=scope,
    ).evaluate(1, candidate.source_binding.source_state_hash, realization, binding, request)
    cad = CandidateCadStageOutcome(status=CandidateCadStageStatus.SUCCESS, realization=realization)
    return cad, m10, scope, binding, request, cad_request


def make_m12_result(candidate):
    payload = candidate.source_binding.model_dump(mode="json")
    source_binding_hash = "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()
    result = RevoluteDriveAdmissibilityResult(
        candidate_hash=candidate.candidate_hash,
        source_binding_hash=source_binding_hash,
        synthesis_request_hash=candidate.synthesis_request_hash,
        synthesis_policy_hash=candidate.synthesis_policy_hash,
        requirements_hash="sha256:" + "a" * 64,
        checks=(EngineeringCheck(check_id="required-drive", status=EngineeringCheckStatus.SATISFIED),),
    )
    return RevoluteDriveAdmissibilityResult.model_validate(result.model_dump(mode="json"))


class StateBackedCurrentnessVerifier:
    def __init__(self, manager):
        self._service = CandidateEvaluationCurrentnessService(
            manager, cad_replay_verifier=lambda *args: None
        )

    def verify_current(self, evaluation, candidate):
        return self._service.verify_current(
            evaluation,
            candidate,
            CandidateSynthesisRequest(source_binding=candidate.source_binding),
            CandidateSynthesisPolicy(
                entries=(
                    ("allow-direct-drive", "direct_drive", "hard_admissibility"),
                    ("preferred-voltage", "24 V", "preference"),
                )
            ),
        )


class SelectionCurrentnessVerifier(StateBackedCurrentnessVerifier):
    pass


def comparison_policy() -> CandidateComparisonPolicy:
    return CandidateComparisonPolicy(
        metric_keys=(CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM,),
        directions=(CandidateComparisonDirection.MAXIMIZE,),
        expected_units=("mm",),
    )


def comparison_request(policy, entries):
    evaluation = entries[0][1]
    return CandidateComparisonRequest(
        project_id="PRJ-M12",
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        policy_hash=policy.policy_hash,
        candidate_evaluation_pairs=tuple(
            (candidate.candidate_hash, item.evaluation_hash) for candidate, item in entries
        ),
    )


def _canonical_mechanism() -> CanonicalPhysicalMechanism:
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
        component_type="mount", source_identity="drawing:mount@1", interfaces=("output-frame",)
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
            CanonicalAcceptedDesignChoice(
                key="mount-1.geometry.length_mm",
                value=40.0,
                origin=CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION,
                provenance="test:canonical-cad",
            ),
            CanonicalAcceptedDesignChoice(
                key="mount-1.geometry.width_mm",
                value=30.0,
                origin=CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION,
                provenance="test:canonical-cad",
            ),
            CanonicalAcceptedDesignChoice(
                key="mount-1.geometry.thickness_mm",
                value=5.0,
                origin=CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION,
                provenance="test:canonical-cad",
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


def _canonical_joint_hash(binding) -> str:
    payload = {
        "joint_id": binding.joint_id,
        "joint_kind": "revolute",
        "parent_instance_id": binding.expected_parent_instance_id,
        "child_instance_id": binding.expected_child_instance_id,
        "axis_origin": [binding.axis_origin_x_mm, binding.axis_origin_y_mm, binding.axis_origin_z_mm],
        "axis_direction": [binding.axis_direction_x, binding.axis_direction_y, binding.axis_direction_z],
        "semantic_version": binding.semantic_version,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def canonical_inputs(tmp_path, *, requires_home=False):
    manager = StateManager(tmp_path)
    base = DesignState(id="PRJ-CAD", revision=1)
    snapshot = manager.create_project("PRJ-CAD", base)
    source = ArtifactStore(tmp_path, project_id="PRJ-CAD", run_id="SOURCE").publish(
        "ART-shaft", ArtifactType.STEP, "shaft.step", b"trusted-source-N", "freecad", "1.1.3",
        snapshot.revision, snapshot.state_hash,
    )
    original = _canonical_mechanism()
    source_spec = type(original.component_specifications[0]).model_validate(
        original.component_specifications[0].model_dump(mode="python")
        | {
            "geometry_source": original.component_specifications[0].geometry_source.model_copy(
                update={"artifact_hash": source.sha256, "reference_hash": "pending"}
            ),
            "specification_hash": "pending",
        }
    )
    source_component = original.components[0].model_copy(
        update={"specification_hash": source_spec.specification_hash, "component_hash": "pending"}
    )
    mechanism = CanonicalPhysicalMechanism.model_validate(
        original.model_dump(mode="python")
        | {"component_specifications": (source_spec, original.component_specifications[1]),
           "components": (source_component, original.components[1]), "mechanism_hash": "pending"}
    )
    snapshot = manager.create_revision("PRJ-CAD", base.model_copy(update={"physical_mechanisms": [mechanism]}))
    reconstruction = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: ProjectArtifactResolver(
            ArtifactStore(tmp_path, project_id=project_id, run_id="lookup")
        ),
    ).reconstruct("PRJ-CAD", snapshot.revision, snapshot.state_hash, mechanism.id)
    binding = reconstruction.mechanism.joint_bindings[0].model_copy(
        update={"semantic_hash": _canonical_joint_hash(reconstruction.mechanism.joint_bindings[0]), "binding_hash": "pending"}
    )
    base_obligation = reconstruction.mechanism.m10_obligations[0]
    obligation = type(base_obligation).model_validate(
        base_obligation.model_dump(mode="python")
        | {
            "physical_pair_requirements": tuple(
                type(item).model_validate(
                    item.model_dump(mode="python")
                    | {"requires_home_exact_check": requires_home, "requirement_hash": "pending"}
                )
                for item in base_obligation.physical_pair_requirements
            ),
            "obligation_hash": "pending",
        }
    )
    mechanism = CanonicalPhysicalMechanism.model_validate(
        reconstruction.mechanism.model_dump(mode="python")
        | {"joint_bindings": (binding,), "m10_obligations": (obligation,), "mechanism_hash": "pending"}
    )
    projection = PromotableMechanismProjection(
        canonical_target_mechanism_id=mechanism.id,
        canonical_instance_ids=tuple(item.instance_id for item in mechanism.components),
        component_specifications=mechanism.component_specifications,
        components=mechanism.components,
        accepted_design_choices=mechanism.accepted_design_choices,
        placements=mechanism.placements,
        connections=mechanism.connections,
        joint_bindings=mechanism.joint_bindings,
        m10_obligations=mechanism.m10_obligations,
        mapping_identities=tuple(item.instance_id for item in mechanism.components),
    )
    snapshot = manager.create_revision(
        "PRJ-CAD",
        base.model_copy(update={"physical_mechanisms": [mechanism]}),
    )
    reconstruction = CanonicalMechanismReconstruction.model_validate(
        reconstruction.model_dump(mode="python")
        | {
            "revision": snapshot.revision,
            "state_hash": snapshot.state_hash,
            "canonical_mechanism": mechanism,
            "normalized_projection_hash": projection.projection_hash,
        }
    )
    return reconstruction, CanonicalPhysicalCadCompiler(
        ProjectArtifactResolver(ArtifactStore(tmp_path, project_id="PRJ-CAD", run_id="lookup"))
    ).realize(reconstruction)
