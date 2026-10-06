from __future__ import annotations

import hashlib
import gc
import importlib.util
import json
import os
from types import SimpleNamespace
from pathlib import Path

import pytest

from mechcad_harness.application import ProductionApplication
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateIntegrityError,
    CandidateCadIntegrityError,
    CandidateCadRealization,
    CandidateCadRealizationRequest,
    CandidateCadRealizationService,
    CandidateCadStageReason,
    CandidateCadStageStatus,
    CandidateCadStageOutcomeV2,
    CandidateEvaluationOutcome,
    CandidateEvaluation,
    CandidateEvaluationPolicy,
    CandidateSynthesisPolicy,
    CandidateM10EvaluationService,
    CandidateCollisionPairClassification,
    CandidateM10Binding,
    CandidateM10BodyDisposition,
    CandidateM10ConstituentDisposition,
    CandidateM10EvaluationRequest,
    CandidateM10EvaluationScope,
    CandidateM10PairClassification,
    CandidateM10PairScopeRequirement,
    CandidateM10StageReason,
    CandidateM10StageStatus,
    CandidateComparisonRequest,
    CandidatePlacementOrigin,
    CandidateGeometryFidelity,
    CandidateDesignVariable,
    CandidateComparisonService,
    CandidateComparisonResult,
    CandidateSelectionService,
    CandidateSelection,
    CandidateProvenanceArtifactService,
)
from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.candidates.m10_evaluation import (
    CandidateM10StageOutcome,
    CandidateM10StageOutcomeV2,
)
from mechcad_harness.candidates.cad_realization import CandidateCadStageOutcome
from mechcad_harness.candidates.m10_evaluation import CandidateCollisionPairInventory
from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.cad_compilation import MountingPlateDesignSpec, compile_mounting_plate
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.backends.adapters.py_gearworks import PyGearworksAdapter
from mechcad_harness.backends.errors import BackendUnavailableError
from mechcad_harness.backends.models import BackendHealth, BackendHealthStatus
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.runs import TaskDefinition
from mechcad_harness.tools import GearworksTools
from mechcad_harness.continuous_proof import (
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
    ContinuousSingleAxisProofStatus,
)
from mechcad_harness.continuous_proof import (
    ContinuousIntervalCertificate,
    ContinuousPairCertificate,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
)
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.multi_joint_kinematics import KinematicModel, RevoluteJointModel
from mechcad_harness.revolute_drive import (
    DriveArchitecture,
    EngineeringCheckStatus,
    RevoluteDriveAdmissibilityResult,
)
from mechcad_harness.tools.errors import ToolExecutionError
from mechcad_harness.tools.models import ToolResultStatus
from mechcad_harness.models.evidence import Evidence

from test_m12_revolute_drive_production import (
    build_application,
    production_state,
    UninvokedAgentAdapter,
    make_request,
    motor_specification,
    shaft_specification,
    bearing_specification,
    hub_specification,
    mount_specification,
    body_specification,
    gear_specification,
    support_mount_specification,
    policy_for,
    requirements,
    spur_requirements,
    template,
    workspace_snapshot,
    _geometry_identities,
    _publish_source_artifacts,
)


PROJECT_ID = "PRJ-M12"


FREECAD_CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
GEAR_AVAILABLE = (
    importlib.util.find_spec("py_gearworks") is not None
    and importlib.util.find_spec("build123d") is not None
)


def _freecad_available_for_capstone() -> bool:
    try:
        discovery = discover_freecad()
    except Exception:
        return False
    return discovery.available or os.path.isfile(FREECAD_CANDIDATE)


FREECAD_AVAILABLE = _freecad_available_for_capstone()
def _candidate_and_result(application):
    synthesis_request = make_request(application)
    from mechcad_harness.candidates.services import bind_candidate_synthesis_request_semantic_identity

    synthesis_request = bind_candidate_synthesis_request_semantic_identity(
        synthesis_request,
        state_manager=application.state_manager,
        store=application.candidate_publication_service.store,
        project_id=application.project_id,
    )
    synthesis_policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    outcome = application.realize_and_evaluate_revolute_drive(
        request=synthesis_request,
        policy=synthesis_policy,
        template_input=template(DriveArchitecture.DIRECT_DRIVE),
        requirements=requirements(require_nominal_interface_compatibility=True),
    )
    assert outcome.construction.candidate is not None
    assert outcome.evaluation is not None
    return (
        outcome.construction.candidate,
        synthesis_request,
        synthesis_policy,
        outcome.evaluation,
    )


def _evaluation_fixture(application):
    candidate, synthesis_request, synthesis_policy, m12_result = _candidate_and_result(application)
    cad, m10, scope, binding, m10_request, cad_request = _cad_m10_inputs(candidate)
    return (
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad,
        m10,
        scope,
        binding,
        m10_request,
        cad_request,
    )


def _publish_scalar_restart_evaluation(application):
    """Create the persisted evaluation through production boundaries only."""
    (
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        scope,
        binding,
        m10_request,
        cad_request,
    ) = _evaluation_fixture(application)
    provenance = application.candidate_provenance_artifact_service
    provenance.cad_replay_verifier = lambda *args: None
    application.candidate_evaluation_service.cad_replay_verifier = lambda *args: None
    evaluation = application.candidate_evaluation_service.evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    evidence_dir = application.state_manager.workspace / "projects" / candidate.source_binding.project_id / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for kind, prefix, records in (
        (
            "analysis.continuous_clearance_proof",
            "EVD-CPROOF-",
            m10_stage.pair_proofs,
        ),
        ("analysis.kinematic_sweep", "EVD-KSWEEP-", m10_stage.home_exact_checks),
    ):
        for record in records:
            evidence_id = prefix + hashlib.sha256(
                (record.request_hash + record.result_hash).encode()
            ).hexdigest()[:24]
            (evidence_dir / f"{evidence_id}.json").write_text(
                Evidence(
                    id=evidence_id,
                    kind=kind,
                    summary="deterministic production integration fixture",
                    revision=candidate.source_binding.source_revision,
                    state_hash=candidate.source_binding.source_state_hash,
                    producer_result_id=record.result_hash,
                    input_hash=record.request_hash,
                    output_hash=record.result_hash,
                ).model_dump_json(),
                encoding="utf-8",
            )
    candidate_cad = provenance.publish_candidate_cad(
        candidate,
        synthesis_request,
        synthesis_policy,
        cad_request,
        cad_stage.realization,
        source_step_artifacts=None,
    )
    return provenance.publish_candidate_evaluation(candidate_cad.artifact, evaluation)


def _cad_m10_inputs(
    candidate,
    *,
    application=None,
    synthesis_request=None,
    synthesis_policy=None,
    scope_pair=None,
):
    if candidate.schema_version == "mechanical-design-candidate@2":
        return _cad_m10_inputs_v2(
            candidate,
            application=application,
            synthesis_request=synthesis_request,
            synthesis_policy=synthesis_policy,
            scope_pair=scope_pair,
        )

    physical_ids = tuple(component.instance_id for component in candidate.realization.components)
    output_id = "output-shaft"
    hub_id = "output-hub"
    mount_id = "motor-mount"
    body_id = "payload-body"
    mappings = []
    parts = []
    instances = []
    for index, physical_id in enumerate(physical_ids):
        transform = CadRigidTransform(x_mm=float(index * 20))
        cad_id = f"cad-{physical_id}"
        mapping = CandidateCadInstanceMapping(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id=physical_id,
            cad_instance_id=cad_id,
            fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
            representation_identity=cad_program_hash(
                CadPartProgram(
                    part_id=f"part-{physical_id}",
                    operations=(
                        BasePlateOperation(
                            operation_id=f"base-{physical_id}",
                            length_mm=10,
                            width_mm=10,
                            thickness_mm=2,
                        ),
                    ),
                )
            ),
            geometry_definition_identities=(f"candidate:geometry:{physical_id}",),
            placement=transform,
            placement_origin=CandidatePlacementOrigin(
                authority="deterministic_derived_relation",
                input_identities=(f"candidate:placement:{physical_id}",),
                derivation="fixture-placement@1",
                transform=transform,
            ),
        )
        mappings.append(mapping)
        part = CadPartProgram(
            part_id=f"part-{physical_id}",
            operations=(
                BasePlateOperation(
                    operation_id=f"base-{physical_id}",
                    length_mm=10,
                    width_mm=10,
                    thickness_mm=2,
                ),
            ),
        )
        parts.append(part)
        instances.append(CadComponentInstance(instance_id=cad_id, part_id=part.part_id, placement=transform))

    mappings = tuple(mappings)
    assembly = CadAssemblyProgram(
        assembly_id="candidate-production-fixture",
        parts=tuple(parts),
        instances=tuple(instances),
    )
    cad_request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-evaluation-fixture@1",
        compiler_identity="fixture",
        compiler_version="1",
        candidate_instance_ids=physical_ids,
        mappings=mappings,
    )
    cad_realization = CandidateCadRealization(
        candidate_hash=candidate.candidate_hash,
        request_hash=cad_request.request_hash,
        mappings=mappings,
        assembly=assembly,
        assembly_hash=assembly_hash(assembly),
        compiler_identity="fixture",
        compiler_version="1",
        provider_identity="fixture",
    )
    cad = CandidateCadStageOutcome(status=CandidateCadStageStatus.SUCCESS, realization=cad_realization)
    binding = CandidateM10Binding(
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=cad_realization.realization_hash,
        model=KinematicModel(
            model_id="candidate-production-fixture-model",
            joints=(
                RevoluteJointModel(
                    joint_id="output-joint",
                    parent_instance_id=f"cad-{mount_id}",
                    child_instance_id=f"cad-{output_id}",
                    axis_origin_x_mm=20,
                    axis_direction_z=1,
                ),
            ),
        ),
        output_joint_id="output-joint",
        output_axis=RevoluteAxis(
            origin_x_mm=120,
            origin_y_mm=0,
            origin_z_mm=0,
            direction_x=0,
            direction_y=0,
            direction_z=1,
            frame_id="joint:output-joint",
        ),
        constituent_dispositions=tuple(
            CandidateM10ConstituentDisposition(
                physical_instance_id=physical_id,
                cad_instance_id=f"cad-{physical_id}",
                constituent_key=physical_id,
                disposition=(
                    CandidateM10BodyDisposition.OUTPUT_RIGID
                    if physical_id in {output_id, hub_id, body_id}
                    else CandidateM10BodyDisposition.FIXED
                ),
                output_transform_group="output-joint" if physical_id in {output_id, hub_id, body_id} else None,
            )
            for physical_id in physical_ids
        ),
    )
    scope = CandidateM10EvaluationScope(
        output_joint_semantic_key="primary-output-revolute",
        angle_interval_deg=(-45.0, 45.0),
        required_clearance_mm=1.0,
        pair_scope_requirements=(
            CandidateM10PairScopeRequirement(
                requirement_key="hub-mount-clearance",
                first_constituent_key=hub_id,
                second_constituent_key=mount_id,
                required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
            ),
        ),
        fidelity_requirements=(
            (hub_id, CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION),
            (mount_id, CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION),
        ),
        proof_service_version="m10-single-axis-continuous-proof@1",
    )
    inventory = CandidateCollisionPairInventory.complete_for(cad_realization, binding, scope)
    m10_request = CandidateM10EvaluationRequest(
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=cad_realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding.model_hash,
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in mappings)),
        inventory=inventory,
    )

    def prove(**kwargs):
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
        pair = ContinuousPairCertificate(
            moving_instance_id=kwargs["moving_instance_ids"][0],
            stationary_instance_id=kwargs["stationary_instance_ids"][0],
            exact_distance_mm=10.0,
            radial_bound_mm=1.0,
            angular_motion_bound_mm=0.1,
            certified_lower_clearance_mm=9.9,
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
            status=ContinuousSingleAxisProofStatus.VERIFIED_CLEAR,
            certified_leaf_certificates=(
                ContinuousIntervalCertificate(
                    interval_start_deg=request.start_angle_deg,
                    interval_end_deg=request.end_angle_deg,
                    reference_angle_deg=0.0,
                    pair_certificates=(pair,),
                    minimum_certified_lower_clearance_mm=9.9,
                ),
            ),
            exact_evaluations_count=1,
            maximum_depth_reached=0,
        )
        payload = result.model_dump(mode="json", exclude={"result_hash"})
        return result.model_copy(
            update={
                "result_hash": "sha256:"
                + hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
            }
        )

    m10 = CandidateM10EvaluationService(
        prove,
        lambda **kwargs: pytest.fail("home check not required"),
        scope=scope,
    ).evaluate(
        candidate.source_binding.source_revision,
        candidate.source_binding.source_state_hash,
        cad_realization,
        binding,
        m10_request,
    )
    return cad, m10, scope, binding, m10_request, cad_request


def _cad_m10_inputs_v2(
    candidate,
    *,
    application=None,
    synthesis_request=None,
    synthesis_policy=None,
    publish_cad=True,
    use_production_m10=False,
    not_proven=False,
    external_spur=False,
    request_only=False,
    axis_origin_x_mm=None,
    scope_pair=None,
):
    from test_m12_revolute_drive_production import (
        _GEOMETRY_SLOTS,
        _STEP_ARTIFACT_HASH,
    )
    from mechcad_harness.candidates.cad_realization import (
        CandidateCadInstanceMappingV2,
        CandidateCadRealizationRequestV3,
            CandidateCadRealizationV2,
            CandidateCadStageOutcomeV2,
            SemanticSourceGeometryIdentity,
            SemanticPlacementOrigin,
        bind_semantic_placement_origin,
        trusted_representation_identity,
    )
    import mechcad_harness.candidates.m10_evaluation as candidate_m10_v2
    from mechcad_harness.semantic_m10_kinematics import (
        semantic_single_joint_kinematic_model_hash,
    )

    mappings = []
    instances = []
    imported_components = []
    content_by_artifact = {}
    for index, component in enumerate(candidate.realization.components):
        specification = next(
            item
            for item in candidate.component_specifications
            if item.specification_hash == component.specification_hash
        )
        source = specification.geometry_source
        if source is None:
            raise AssertionError("@2 CAD fixture requires a bound semantic source spec")
        placement_values = {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0}
        placement_variable_identities = []
        if application is not None:
            for axis in placement_values:
                names = (
                    f"{component.instance_id}.placement.{axis}",
                    f"placement.{component.instance_id}.{axis}",
                )
                matches = tuple(
                    variable
                    for variable in candidate.design_variables
                    if variable.name in names
                )
                if len(matches) > 1:
                    raise AssertionError(
                        "candidate placement authority is ambiguous in promotion fixture"
                    )
                if matches:
                    placement_values[axis] = float(matches[0].value)
                    placement_variable_identities.append(
                        f"candidate:design-variable:{matches[0].name}"
                    )
        transform = (
            CadRigidTransform(**placement_values)
            if application is not None
            else CadRigidTransform(x_mm=float(index * 20))
        )
        cad_id = f"cad-{component.instance_id}"
        content_by_artifact[source.artifact_id] = source.content_identity
        content_by_artifact[source.artifact_hash] = source.content_identity
        origin = bind_semantic_placement_origin(
            "source_authority",
            (
                source.artifact_id,
                source.artifact_hash,
                f"candidate:source-authority:{source.source_identity}",
                *placement_variable_identities,
            ),
            "fixture-placement@1",
            transform,
            content_by_artifact=content_by_artifact,
        )
        mappings.append(
            CandidateCadInstanceMappingV2(
                candidate_hash=candidate.candidate_hash,
                physical_instance_id=component.instance_id,
                cad_instance_id=cad_id,
                fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
                representation_identity=trusted_representation_identity(
                    slot=cad_id,
                    content_identity=source.content_identity,
                    content_identity_algorithm=source.content_identity_algorithm,
                ),
                source_geometry_identity=SemanticSourceGeometryIdentity(
                    content_identity=source.content_identity,
                    content_identity_algorithm=source.content_identity_algorithm,
                ),
                geometry_definition_identities=(source.content_identity,),
                placement=transform,
                placement_origin=origin,
            )
        )
        imported_components.append(
            ImportedCadComponent(
                component_id=cad_id,
                artifact_id=source.artifact_id,
                artifact_hash=source.artifact_hash,
                source_revision=candidate.source_binding.source_revision,
                source_state_hash=candidate.source_binding.source_state_hash,
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
    declared_inputs = {
        identity
        for mapping in mappings
        for identity in (
            mapping.geometry_definition_identities
            + mapping.placement_origin.input_identities
        )
    }
    cad_request = CandidateCadRealizationRequestV3(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        semantic_source_binding_hash=candidate.semantic_source_binding_hash,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=tuple(item.physical_instance_id for item in mappings),
        mappings=mappings,
        placement_derivations=(),
        design_variable_identities=tuple(
            sorted(
                identity
                for identity in declared_inputs
                if identity.startswith("candidate:design-variable:")
            )
        ),
        component_interface_identities=tuple(
            sorted(
                identity
                for identity in declared_inputs
                if identity.startswith("candidate:component-interface:")
            )
        ),
    )
    if request_only:
        return cad_request
    if application is not None:
        if synthesis_request is None or synthesis_policy is None:
            raise AssertionError("production CAD fixture requires typed synthesis parents")
        cad_stage = (
            application.realize_candidate_cad(
                candidate, synthesis_request, synthesis_policy, cad_request
            )
            if publish_cad
            else application.candidate_cad_realization_service.realize(
                candidate, synthesis_request, synthesis_policy, cad_request
            )
        )
        if (
            type(cad_stage) is not CandidateCadStageOutcomeV2
            or cad_stage.status is not CandidateCadStageStatus.SUCCESS
            or cad_stage.realization is None
        ):
            raise AssertionError(f"production CAD@2 realization failed: {cad_stage}")
        cad_realization = cad_stage.realization
        required_raw_pairs = (
            application.candidate_provenance_artifact_service
            ._candidate_cad_required_raw_pairs(candidate)
        )
        if sorted(cad_realization.verified_source_artifact_hashes) != sorted(
            required_raw_pairs.values()
        ):
            raise AssertionError(
                "production CAD fixture raw multiset does not match its accepted source set: "
                f"actual={sorted(cad_realization.verified_source_artifact_hashes)!r} "
                f"expected={sorted(required_raw_pairs.values())!r}"
            )
        assembly = cad_realization.assembly
    else:
        assembly = CadAssemblyProgram(
            assembly_id="candidate-production-fixture-v2",
            imported_components=tuple(imported_components),
            instances=tuple(instances),
        )
        cad_realization = CandidateCadRealizationV2(
            candidate_hash=candidate.candidate_hash,
            request_hash=cad_request.request_hash,
            mappings=mappings,
            assembly=assembly,
            assembly_hash=assembly_hash(assembly),
            representation_identities=tuple(item.representation_identity for item in mappings),
            semantic_placement_derivations_hash=cad_request.semantic_placement_derivations_hash,
            verified_source_content_identities=tuple(
                dict.fromkeys(
                    item.source_geometry_identity.content_identity
                    for item in mappings
                    if item.source_geometry_identity is not None
                )
            ),
            verified_source_artifact_hashes=(_STEP_ARTIFACT_HASH,) * len(
                _GEOMETRY_SLOTS
            ),
            compiler_identity="candidate-cad-compiler",
            compiler_version="1",
            provider_identity="candidate-cad-v2-integration-fixture",
        )
        cad_stage = CandidateCadStageOutcomeV2(
            status=CandidateCadStageStatus.SUCCESS,
            realization=cad_realization,
        )

    instance_ids = {item.instance_id for item in candidate.realization.components}
    output_ids = {"output-shaft", "output-hub", "payload-body"}
    dispositions = tuple(
        candidate_m10_v2.CandidateM10ConstituentDispositionV2(
            schema_version="candidate-m10-constituent-disposition@2",
            physical_instance_id=instance_id,
            cad_instance_id=f"cad-{instance_id}",
            constituent_key=instance_id,
            disposition=(
                "internal_motion_unmodeled"
                if external_spur and instance_id == "driver-gear"
                else ("output_rigid" if instance_id in output_ids else "fixed")
            ),
            output_transform_group=(
                "J-1"
                if instance_id in output_ids
                else None
            ),
        )
        for instance_id in sorted(instance_ids)
    )
    motor_mount_placement = next(
        instance.placement
        for instance in assembly.instances
        if instance.instance_id == "cad-motor-mount"
    )
    world_axis_origin_x_mm = 120.0 if axis_origin_x_mm is None else axis_origin_x_mm
    local_axis_origin_x_mm = world_axis_origin_x_mm - motor_mount_placement.x_mm
    model = KinematicModel(
        model_id="candidate-production-fixture-model-v2",
        joints=(
            RevoluteJointModel(
                joint_id="J-1",
                parent_instance_id="cad-motor-mount",
                child_instance_id="cad-output-shaft",
                axis_origin_x_mm=local_axis_origin_x_mm,
                axis_direction_z=1.0,
            ),
        ),
    )
    binding = candidate_m10_v2.CandidateM10BindingV2(
        schema_version="candidate-m10-binding@2",
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=cad_realization.realization_hash,
        model=model,
        semantic_single_joint_kinematic_model_hash=(
            semantic_single_joint_kinematic_model_hash(model)
        ),
        output_joint_id="J-1",
        driver_gear_constituent_key="driver-gear" if external_spur else None,
        output_axis=RevoluteAxis(
            origin_x_mm=world_axis_origin_x_mm,
            origin_y_mm=0.0,
            origin_z_mm=0.0,
            direction_x=0.0,
            direction_y=0.0,
            direction_z=1.0,
            frame_id="joint:J-1",
        ),
        constituent_dispositions=dispositions,
    )
    pair = scope_pair or (
        "hub-mount-clearance",
        "output-hub",
        "motor-mount",
    )
    scope = CandidateM10EvaluationScope(
        output_joint_semantic_key="primary-output-revolute",
        angle_interval_deg=(-45.0, 45.0),
        required_clearance_mm=1.0,
        pair_scope_requirements=(
            CandidateM10PairScopeRequirement(
                requirement_key=pair[0],
                first_constituent_key=pair[1],
                second_constituent_key=pair[2],
                required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
            ),
        ),
        fidelity_requirements=(
            (
                pair[1],
                CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
            ),
            (
                pair[2],
                CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
            ),
        ),
        proof_service_version="m10-single-axis-continuous-proof@1",
    )
    classifications = ()
    if external_spur:
        baseline_inventory = candidate_m10_v2.CandidateCollisionPairInventoryV2.complete_for(
            cad_realization, binding, scope
        )
        classifications = tuple(
            item.model_copy(
                update={
                    "classification": candidate_m10_v2.CandidateM10PairClassification.INTENDED_CONTACT_EXCLUDED,
                    "reason": "declared gear mesh interface is outside M10 scope",
                    "classification_hash": "pending",
                }
            )
            if set(item.pair) == {"cad-driver-gear", "cad-driven-gear"}
            else item
            for item in baseline_inventory.classifications
        )
    inventory = candidate_m10_v2.CandidateCollisionPairInventoryV2.complete_for(
        cad_realization, binding, scope, classifications
    )
    m10_request = candidate_m10_v2.CandidateM10EvaluationRequestV2(
        schema_version="candidate-m10-evaluation-request@2",
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=cad_realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        semantic_single_joint_kinematic_model_hash=(
            binding.semantic_single_joint_kinematic_model_hash
        ),
        mapping_hashes=tuple(sorted(item.mapping_hash for item in mappings)),
        inventory=inventory,
    )

    def prove(**kwargs):
        from hashlib import sha256

        proof_request = ContinuousSingleAxisProofRequest(
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
        pair = ContinuousPairCertificate(
            moving_instance_id=kwargs["moving_instance_ids"][0],
            stationary_instance_id=kwargs["stationary_instance_ids"][0],
            exact_distance_mm=10.0,
            radial_bound_mm=1.0,
            angular_motion_bound_mm=0.1,
            certified_lower_clearance_mm=9.9,
        )
        proof_result = ContinuousSingleAxisProofResult(
            request_hash=proof_request.request_hash,
            source_assembly_hash=proof_request.source_assembly_hash,
            proof_algorithm_version=CONTINUOUS_PROOF_ALGORITHM_VERSION,
            axis=proof_request.axis,
            start_angle_deg=proof_request.start_angle_deg,
            end_angle_deg=proof_request.end_angle_deg,
            moving_instance_ids=proof_request.moving_instance_ids,
            stationary_instance_ids=proof_request.stationary_instance_ids,
            required_clearance_mm=proof_request.required_clearance_mm,
            proof_guard_mm=proof_request.proof_guard_mm,
            status=ContinuousSingleAxisProofStatus.VERIFIED_CLEAR,
            certified_leaf_certificates=(
                ContinuousIntervalCertificate(
                    interval_start_deg=proof_request.start_angle_deg,
                    interval_end_deg=proof_request.end_angle_deg,
                    reference_angle_deg=0.0,
                    pair_certificates=(pair,),
                    minimum_certified_lower_clearance_mm=9.9,
                ),
            ),
            exact_evaluations_count=1,
            maximum_depth_reached=0,
        )
        payload = proof_result.model_dump(mode="json", exclude={"result_hash"})
        return proof_result.model_copy(
            update={
                "result_hash": "sha256:"
                + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            }
        )

    if application is not None and use_production_m10:
        if not_proven:
            application.candidate_m10_evaluation_service.max_exact_evaluations = 2
            application.candidate_m10_evaluation_service.max_depth = 1
        m10_stage = application.candidate_m10_evaluation_service.evaluate(
            candidate.source_binding.source_revision,
            candidate.source_binding.source_state_hash,
            cad_stage,
            binding,
            m10_request,
            scope=scope,
            physical_realization=candidate.realization,
        )
    else:
        m10_stage = candidate_m10_v2.CandidateM10EvaluationService(
            prove,
            lambda **kwargs: pytest.fail("home check not required by fixture scope"),
            scope=scope,
        ).evaluate(
            candidate.source_binding.source_revision,
            candidate.source_binding.source_state_hash,
            cad_realization,
            binding,
            m10_request,
            physical_realization=candidate.realization,
        )
    return cad_stage, m10_stage, scope, binding, m10_request, cad_request


def test_candidate_cad_realization_at2_raw_multiset_covers_full_source_binding(
    tmp_path,
):
    application = build_application(tmp_path)
    candidate, synthesis_request, synthesis_policy, _ = _candidate_and_result(
        application
    )
    cad_stage, _, _, _, _, _ = _cad_m10_inputs_v2(
        candidate,
        application=application,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        publish_cad=False,
    )
    assert cad_stage.realization is not None
    required_raw_pairs = (
        application.candidate_provenance_artifact_service
        ._candidate_cad_required_raw_pairs(candidate)
    )

    assert sorted(cad_stage.realization.verified_source_artifact_hashes) == sorted(
        required_raw_pairs.values()
    )


def _violated_m12_result(result):
    checks = result.checks
    replacement = checks[-1].model_copy(
        update={"status": EngineeringCheckStatus.VIOLATED, "reason": "fixture violation"}
    )
    return RevoluteDriveAdmissibilityResult.model_validate(
        result.model_dump(mode="json")
        | {"checks": (*checks[:-1], replacement), "status": None, "result_hash": "pending"}
    )


def _not_proven_m10_stage(m10):
    proof = m10.pair_proofs[0]
    result = proof.result.model_copy(
        update={
            "status": ContinuousSingleAxisProofStatus.NOT_PROVEN,
            "certified_leaf_certificates": (),
            "unresolved_intervals": ((proof.result.start_angle_deg, proof.result.end_angle_deg),),
            "result_hash": "pending",
        }
    )
    payload = result.model_dump(mode="json", exclude={"result_hash"})
    result = result.model_copy(
        update={
            "result_hash": "sha256:"
            + hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        }
    )
    return type(m10).model_validate(
        m10.model_dump(mode="json")
        | {
            "pair_proofs": (
                proof.model_copy(
                    update={
                        "result": result,
                        "result_hash": result.result_hash,
                        "proof_hash": "pending",
                    }
                ),
            ),
            "outcome_hash": "pending",
        }
    )
def test_default_production_composes_candidate_services_and_attested_freecad(tmp_path):
    application = build_application(tmp_path)

    assert isinstance(application.candidate_cad_realization_service, CandidateCadRealizationService)
    assert isinstance(application.candidate_m10_evaluation_service, CandidateM10EvaluationService)
    assert isinstance(application.candidate_comparison_service, CandidateComparisonService)
    assert isinstance(application.candidate_selection_service, CandidateSelectionService)
    assert isinstance(
        application.candidate_provenance_artifact_service,
        CandidateProvenanceArtifactService,
    )
    with pytest.raises(AttributeError, match="read-only"):
        application.candidate_provenance_artifact_service = object()
    assert application._is_real_freecad_measurement_provider(
        application._kinematic_measurement_provider
    )


def test_candidate_evaluation_restarts_from_scalar_artifact_locator(tmp_path):
    application = build_application(tmp_path)
    publication = _publish_scalar_restart_evaluation(application)
    service = application.candidate_provenance_artifact_service

    project_id = publication.artifact.project_id
    workspace = application.state_manager.workspace
    artifact_id = publication.artifact.artifact_id
    artifact_hash = publication.artifact.sha256
    del service, application, publication
    gc.collect()

    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
    )
    from mechcad_harness.state import StateManager

    restarted = CandidateProvenanceArtifactService(
        workspace,
        # Retain only the declared workspace locator, not the original service.
        project_id,
        StateManager(workspace),
        cad_replay_verifier=lambda *args: None,
    )
    resolved = restarted.resolve_candidate_evaluation(artifact_id)

    assert resolved.artifact.artifact_id == artifact_id
    assert resolved.artifact.sha256 == artifact_hash


def test_candidate_entrypoints_publish_after_typed_result_exists(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    (
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        scope,
        binding,
        m10_request,
        cad_request,
    ) = _evaluation_fixture(application)
    calls = []

    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_cad",
        lambda *args, **kwargs: calls.append("cad"),
    )
    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_evaluation",
        lambda *args, **kwargs: calls.append("evaluation"),
    )
    monkeypatch.setattr(
        application.candidate_cad_realization_service,
        "realize",
        lambda *args, **kwargs: cad_stage,
    )
    monkeypatch.setattr(
        application.candidate_m10_evaluation_service,
        "evaluate",
        lambda *args, **kwargs: m10_stage,
    )
    monkeypatch.setattr(
        application.candidate_evaluation_service,
        "cad_replay_verifier",
        lambda *args, **kwargs: None,
    )

    evaluation = application.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_request,
        m10_request,
        scope,
        binding,
        evaluation_policy=CandidateEvaluationPolicy(),
    )

    from mechcad_harness.candidates.evaluation import CandidateEvaluationV2

    assert isinstance(evaluation, CandidateEvaluationV2)
    assert calls == ["cad", "evaluation"]


def test_failed_cad_does_not_publish_or_promote_and_uncalled_comparison_stays_unpublished(
    tmp_path, monkeypatch
):
    application = build_application(tmp_path)
    (
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        scope,
        binding,
        m10_request,
        cad_request,
    ) = _evaluation_fixture(application)
    unresolved = CandidateCadStageOutcomeV2(
        status=CandidateCadStageStatus.UNRESOLVED,
        reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
    )
    calls = []
    original_evaluate = application.candidate_evaluation_service.evaluate
    comparison_publication_calls = []

    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_cad",
        lambda *args, **kwargs: calls.append("cad"),
    )
    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_evaluation",
        lambda *args, **kwargs: calls.append("evaluation"),
    )
    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_comparison",
        lambda *args, **kwargs: comparison_publication_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        application.candidate_cad_realization_service,
        "realize",
        lambda *args, **kwargs: unresolved,
    )
    monkeypatch.setattr(
        application.candidate_m10_evaluation_service,
        "evaluate",
        lambda *args, **kwargs: pytest.fail("M10 must not run after unresolved CAD"),
    )
    monkeypatch.setattr(
        application.candidate_evaluation_service,
        "evaluate",
        lambda *args, **kwargs: SimpleNamespace(
            outcome=CandidateEvaluationOutcome.UNRESOLVED,
            cad_stage_outcome=args[4],
            m10_stage_outcome=args[5],
        ),
    )

    result = application.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_request,
        m10_request,
        scope,
        binding,
        evaluation_policy=CandidateEvaluationPolicy(),
    )

    assert result.outcome is CandidateEvaluationOutcome.UNRESOLVED
    assert calls == []
    monkeypatch.setattr(
        application.candidate_evaluation_service,
        "cad_replay_verifier",
        lambda *args, **kwargs: None,
    )
    valid_evaluation = original_evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    from mechcad_harness.candidates import CandidateSelectionV2

    selection = CandidateSelectionV2(
        candidate_hash=candidate.candidate_hash,
        evaluation_hash=valid_evaluation.evaluation_hash,
        source_binding_hash=valid_evaluation.source_binding_hash,
        evaluation_scope_hash=valid_evaluation.evaluation_scope_hash,
        selector_identity="manual",
        rationale="bounded fixture selection",
    )
    monkeypatch.setattr(
        application.candidate_selection_service,
        "select",
        lambda *args, **kwargs: selection,
    )
    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_selection",
        lambda *args, **kwargs: calls.append("selection"),
    )
    monkeypatch.setattr(
        application,
        "promote_selected_candidate",
        lambda *args, **kwargs: pytest.fail("candidate selection must not promote"),
    )
    assert (
        application.select_candidate(
            candidate,
            valid_evaluation,
            "manual",
            "bounded fixture selection",
            synthesis_request=synthesis_request,
        )
        == selection
    )
    assert calls == ["selection"]
    assert comparison_publication_calls == []


def test_selection_with_unpublished_supplied_comparison_fails_closed(
    tmp_path, monkeypatch
):
    from mechcad_harness.candidates import CandidateProvenanceIntegrityError
    from mechcad_harness.candidates.comparison import (
        CandidateComparisonRequestV2,
        CandidateComparisonResultV2,
    )
    from mechcad_harness.candidates import CandidateSelectionV2

    application = build_application(tmp_path)
    (
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        scope,
        binding,
        m10_request,
        cad_request,
    ) = _evaluation_fixture(application)
    monkeypatch.setattr(
        application.candidate_evaluation_service,
        "cad_replay_verifier",
        lambda *args, **kwargs: None,
    )
    evaluation = application.candidate_evaluation_service.evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    comparison_request = CandidateComparisonRequestV2(
        project_id=application.project_id,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        policy_hash=application.candidate_comparison_service.policy.policy_hash,
        candidate_evaluation_pairs=((candidate.candidate_hash, evaluation.evaluation_hash),),
    )
    comparison = CandidateComparisonResultV2(
        project_id=application.project_id,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        policy=application.candidate_comparison_service.policy,
        policy_hash=application.candidate_comparison_service.policy.policy_hash,
        request_hash=comparison_request.request_hash,
        candidate_evaluation_pairs=((candidate.candidate_hash, evaluation.evaluation_hash),),
        ranked_candidate_hashes=(candidate.candidate_hash,),
        ranked_evaluation_hashes=(evaluation.evaluation_hash,),
        metric_values=((candidate.candidate_hash, evaluation.metrics[0].value),),
        comparator_version=application.candidate_comparison_service.policy.comparator_version,
    )
    selection = CandidateSelectionV2(
        candidate_hash=candidate.candidate_hash,
        evaluation_hash=evaluation.evaluation_hash,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        selector_identity="manual",
        rationale="selection without a published comparison",
        comparison_used=True,
        comparison_result_hash=comparison.result_hash,
    )
    monkeypatch.setattr(
        application.candidate_selection_service,
        "select",
        lambda *args, **kwargs: selection,
    )
    selection_publication_calls = []
    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_selection",
        lambda *args, **kwargs: selection_publication_calls.append((args, kwargs)),
    )

    with pytest.raises(CandidateProvenanceIntegrityError, match="comparison artifact"):
        application.select_candidate(
            candidate,
            evaluation,
            "manual",
            "selection without a published comparison",
            comparison=comparison,
            comparison_entries=((candidate, evaluation),),
            synthesis_request=synthesis_request,
        )

    assert selection_publication_calls == []


def test_candidate_entrypoints_delegate_to_composed_services(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    calls = []

    def realize(*args, **kwargs):
        calls.append(("cad", args, kwargs))
        return "cad-result"

    def evaluate(*args, **kwargs):
        calls.append(("evaluation", args, kwargs))
        return "evaluation-result"

    def compare(*args, **kwargs):
        calls.append(("comparison", args, kwargs))
        return "comparison-result"

    def select(*args, **kwargs):
        calls.append(("selection", args, kwargs))
        return "selection-result"

    monkeypatch.setattr(application.candidate_cad_realization_service, "realize", realize)
    monkeypatch.setattr(application.candidate_evaluation_service, "evaluate", evaluate)
    monkeypatch.setattr(application.candidate_comparison_service, "compare", compare)
    monkeypatch.setattr(application.candidate_selection_service, "select", select)

    bound = SimpleNamespace(source_binding=SimpleNamespace(project_id=application.project_id))
    comparison_request = SimpleNamespace(project_id=application.project_id)
    assert application.realize_candidate_cad(bound, bound, "policy", "cad-request") == "cad-result"
    assert application.compare_candidates(comparison_request, "evaluations") == "comparison-result"
    assert application.select_candidate(bound, "evaluation", "selector", "rationale") == "selection-result"
    assert [name for name, _, _ in calls] == ["cad", "comparison", "selection"]


def test_inadmissible_m12_result_short_circuits_cad_and_m10(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    candidate, synthesis_request, synthesis_policy, admissible = _candidate_and_result(application)
    _cad, _m10, m10_scope, m10_binding, m10_request, cad_request = _cad_m10_inputs(candidate)
    source_before = application.load_state()
    violated = RevoluteDriveAdmissibilityResult.model_validate(
        admissible.model_dump(mode="json")
        | {
            "checks": tuple(
                admissible.checks[:1]
            )
            if admissible.checks[0].status is EngineeringCheckStatus.VIOLATED
            else tuple(
                admissible.checks[:-1]
                + (admissible.checks[-1].model_copy(
                    update={"status": EngineeringCheckStatus.VIOLATED, "reason": "fixture violation"}
                ),)
            ),
            "status": None,
            "result_hash": "pending",
        }
    )
    cad_calls = []
    m10_calls = []
    evaluation_calls = []

    monkeypatch.setattr(
        application.candidate_cad_realization_service,
        "realize",
        lambda *args, **kwargs: cad_calls.append((args, kwargs)) or pytest.fail("CAD must not run"),
    )
    monkeypatch.setattr(
        application.candidate_m10_evaluation_service,
        "evaluate",
        lambda *args, **kwargs: m10_calls.append((args, kwargs)) or pytest.fail("M10 must not run"),
    )
    def aggregate(*args, **kwargs):
        evaluation_calls.append((args, kwargs))
        return SimpleNamespace(
            outcome=CandidateEvaluationOutcome.INFEASIBLE,
            cad_stage_outcome=args[4],
            m10_stage_outcome=args[5],
        )
    monkeypatch.setattr(application.candidate_evaluation_service, "evaluate", aggregate)

    result = application.evaluate_candidate(
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_3_result=violated,
         cad_request=cad_request,
         m10_request=m10_request,
         m10_scope=m10_scope,
         m10_binding=m10_binding,
        policy=CandidateEvaluationPolicy(),
    )

    assert result.outcome is CandidateEvaluationOutcome.INFEASIBLE
    assert result.cad_stage_outcome.status is CandidateCadStageStatus.NOT_REACHED
    assert result.m10_stage_outcome.status is CandidateM10StageStatus.NOT_REACHED
    assert cad_calls == []
    assert m10_calls == []
    assert evaluation_calls[0][0][4].status is CandidateCadStageStatus.NOT_REACHED
    source_after = application.load_state()
    assert (source_after.revision, source_after.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )


def test_foreign_project_inadmissible_candidate_is_rejected_before_m12_short_circuit(
    tmp_path, monkeypatch
):
    application = build_application(tmp_path)
    foreign_binding = SimpleNamespace(project_id="PRJ-FOREIGN")
    candidate = SimpleNamespace(source_binding=foreign_binding)
    synthesis_request = SimpleNamespace(source_binding=foreign_binding)
    synthesis_policy = object()
    violated = object()

    monkeypatch.setattr(
        application,
        "_validate_candidate_m12_3_result",
        lambda *args, **kwargs: pytest.fail("M12-3 validation must not run for a foreign project"),
    )

    with pytest.raises(CandidateIntegrityError, match="project"):
        application.evaluate_candidate(
            candidate,
            synthesis_request,
            synthesis_policy,
            violated,
            None,
            None,
            None,
            None,
        )


def test_application_selection_rejects_a_foreign_project_before_selection_service(
    tmp_path, monkeypatch
):
    application = build_application(tmp_path)
    candidate = SimpleNamespace(
        source_binding=SimpleNamespace(project_id="PRJ-FOREIGN")
    )
    monkeypatch.setattr(
        application.candidate_selection_service,
        "select",
        lambda *args, **kwargs: pytest.fail("selection service must not run for a foreign project"),
    )

    with pytest.raises(CandidateIntegrityError, match="project"):
        application.select_candidate(candidate, object(), "manual", "Foreign candidate.")


def test_cad_unresolved_short_circuits_m10_and_is_unresolved(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    candidate, synthesis_request, synthesis_policy, admissible = _candidate_and_result(application)
    _cad, _m10, m10_scope, m10_binding, m10_request, cad_request = _cad_m10_inputs(candidate)
    cad_stage = CandidateCadStageOutcomeV2(
        status=CandidateCadStageStatus.UNRESOLVED,
        reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
    )
    monkeypatch.setattr(
        application.candidate_cad_realization_service,
        "realize",
        lambda *args, **kwargs: cad_stage,
    )
    monkeypatch.setattr(
        application.candidate_m10_evaluation_service,
        "evaluate",
        lambda *args, **kwargs: pytest.fail("M10 must not run after unresolved CAD"),
    )
    def aggregate(*args, **kwargs):
        return SimpleNamespace(
            outcome=CandidateEvaluationOutcome.UNRESOLVED,
            cad_stage_outcome=args[4],
            m10_stage_outcome=args[5],
        )
    monkeypatch.setattr(application.candidate_evaluation_service, "evaluate", aggregate)

    result = application.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        admissible,
         cad_request,
         m10_request,
         m10_scope,
         m10_binding,
        CandidateEvaluationPolicy(),
    )

    assert result.outcome is CandidateEvaluationOutcome.UNRESOLVED
    assert result.cad_stage_outcome == cad_stage
    assert result.m10_stage_outcome.status is CandidateM10StageStatus.NOT_REACHED


def test_inadmissible_m12_uses_real_evaluator_with_typed_not_reached_stages(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    (
        candidate,
        synthesis_request,
        synthesis_policy,
        admissible,
        _cad,
        _m10,
        _scope,
        _binding,
        m10_request,
        cad_request,
    ) = _evaluation_fixture(application)
    violated = _violated_m12_result(admissible)
    before = workspace_snapshot(application.state_manager.workspace)
    calls = []
    original_evaluate = application.candidate_evaluation_service.evaluate

    monkeypatch.setattr(
        application.candidate_cad_realization_service,
        "realize",
        lambda *args, **kwargs: pytest.fail("CAD must not run"),
    )
    monkeypatch.setattr(
        application.candidate_m10_evaluation_service,
        "evaluate",
        lambda *args, **kwargs: pytest.fail("M10 must not run"),
    )

    def evaluate(*args, **kwargs):
        calls.append((args, kwargs))
        return original_evaluate(*args, **kwargs)

    monkeypatch.setattr(application.candidate_evaluation_service, "evaluate", evaluate)
    result = application.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        violated,
        cad_request,
        m10_request,
        _scope,
        _binding,
        evaluation_policy=CandidateEvaluationPolicy(),
    )

    assert result.outcome is CandidateEvaluationOutcome.INFEASIBLE
    assert result.cad_stage_outcome.status is CandidateCadStageStatus.NOT_REACHED
    assert result.cad_stage_outcome.schema_version == "candidate-cad-stage-outcome@2"
    assert result.cad_stage_outcome.reasons == (CandidateCadStageReason.PRIOR_STAGE_FAILED,)
    assert result.m10_stage_outcome.status is CandidateM10StageStatus.NOT_REACHED
    assert result.m10_stage_outcome.schema_version == "candidate-m10-stage-outcome@2"
    assert result.m10_stage_outcome.reasons == (CandidateM10StageReason.PRIOR_STAGE_FAILED,)
    assert result.m10_stage_outcome.binding_hash is None
    assert result.m10_stage_outcome.scope_hash is None
    assert result.m10_stage_outcome.evaluation_request_hash is None
    assert result.cad_realization_hash is None
    assert result.m10_request_hashes == ()
    assert result.m10_result_hashes == ()
    assert calls == [
        (
            (
                candidate,
                synthesis_request,
                synthesis_policy,
                violated,
                result.cad_stage_outcome,
                result.m10_stage_outcome,
                CandidateEvaluationPolicy(),
            ),
            {
                "cad_request": None,
                "m10_request": None,
                "m10_scope": None,
                "m10_binding": None,
            },
        )
    ]
    assert workspace_snapshot(application.state_manager.workspace) == before


def test_unresolved_cad_uses_real_evaluator_without_downstream_identities(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    (
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        _cad,
        _m10,
        scope,
        binding,
        m10_request,
        cad_request,
    ) = _evaluation_fixture(application)
    cad_stage = CandidateCadStageOutcomeV2(
        status=CandidateCadStageStatus.UNRESOLVED,
        reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
    )
    before = workspace_snapshot(application.state_manager.workspace)
    calls = []
    original_evaluate = application.candidate_evaluation_service.evaluate

    monkeypatch.setattr(
        application.candidate_cad_realization_service,
        "realize",
        lambda *args, **kwargs: cad_stage,
    )
    monkeypatch.setattr(
        application.candidate_m10_evaluation_service,
        "evaluate",
        lambda *args, **kwargs: pytest.fail("M10 must not run after unresolved CAD"),
    )

    def evaluate(*args, **kwargs):
        calls.append((args, kwargs))
        return original_evaluate(*args, **kwargs)

    monkeypatch.setattr(application.candidate_evaluation_service, "evaluate", evaluate)
    result = application.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_request,
        m10_request,
        scope,
        binding,
        evaluation_policy=CandidateEvaluationPolicy(),
    )

    assert result.outcome is CandidateEvaluationOutcome.UNRESOLVED
    assert result.cad_stage_outcome == cad_stage
    assert result.m10_stage_outcome.status is CandidateM10StageStatus.NOT_REACHED
    assert result.m10_stage_outcome.reasons == (CandidateM10StageReason.PRIOR_STAGE_FAILED,)
    assert result.m10_stage_outcome.binding_hash is None
    assert result.m10_stage_outcome.scope_hash is None
    assert result.m10_stage_outcome.evaluation_request_hash is None
    assert result.cad_realization_hash is None
    assert result.m10_request_hashes == ()
    assert result.m10_result_hashes == ()
    assert calls == [
        (
            (
                candidate,
                synthesis_request,
                synthesis_policy,
                m12_result,
                cad_stage,
                result.m10_stage_outcome,
                CandidateEvaluationPolicy(),
            ),
            {
                "cad_request": None,
                "m10_request": None,
                "m10_scope": None,
                "m10_binding": None,
            },
        )
    ]
    assert workspace_snapshot(application.state_manager.workspace) == before


def test_successful_cad_and_not_proven_m10_retains_exact_result_references(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    (
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        scope,
        binding,
        m10_request,
        cad_request,
    ) = _evaluation_fixture(application)
    not_proven = _not_proven_m10_stage(m10_stage)
    calls = {"cad": [], "m10": [], "evaluation": []}
    original_evaluate = application.candidate_evaluation_service.evaluate

    def realize(*args, **kwargs):
        calls["cad"].append((args, kwargs))
        return cad_stage

    def evaluate_m10(*args, **kwargs):
        calls["m10"].append((args, kwargs))
        return not_proven

    def evaluate(*args, **kwargs):
        calls["evaluation"].append((args, kwargs))
        return original_evaluate(*args, **kwargs)

    monkeypatch.setattr(application.candidate_cad_realization_service, "realize", realize)
    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_cad",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_evaluation",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(application.candidate_evaluation_service, "cad_replay_verifier", lambda *args: None)
    monkeypatch.setattr(application.candidate_m10_evaluation_service, "evaluate", evaluate_m10)
    monkeypatch.setattr(application.candidate_evaluation_service, "evaluate", evaluate)

    result = application.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_request,
        m10_request,
        scope,
        binding,
        evaluation_policy=CandidateEvaluationPolicy(),
    )

    assert result.outcome is CandidateEvaluationOutcome.UNRESOLVED
    assert result.cad_stage_outcome == cad_stage
    assert result.m10_stage_outcome == not_proven
    assert result.cad_realization_hash == cad_stage.realization_hash
    assert result.m10_stage_outcome_hash == not_proven.outcome_hash
    assert result.m10_stage_outcome.pair_proofs[0].result_hash == (
        not_proven.pair_proofs[0].result.result_hash
    )
    assert calls["cad"] == [
        ((candidate, synthesis_request, synthesis_policy, cad_request), {})
    ]
    assert calls["m10"] == [
        (
            (
                candidate.source_binding.source_revision,
                candidate.source_binding.source_state_hash,
                cad_stage,
                binding,
                m10_request,
            ),
            {"scope": scope, "physical_realization": candidate.realization},
        )
    ]
    assert calls["evaluation"] == [
        (
            (
                candidate,
                synthesis_request,
                synthesis_policy,
                m12_result,
                cad_stage,
                not_proven,
                CandidateEvaluationPolicy(),
            ),
            {
                "cad_request": cad_request,
                "m10_request": m10_request,
                "m10_scope": scope,
                "m10_binding": binding,
            },
        )
    ]


def _build_gear_application(tmp_path: Path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /requirements/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/requirements/*"],
                        "invalidates": [
                            "analysis.continuous_clearance_proof",
                            "analysis.kinematic_sweep",
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    from mechcad_harness.state import StateManager

    state = production_state()
    state = state.model_copy(
        update={
            "yagi_payload_carrier_requirements": list(state.yagi_payload_carrier_requirements)
            + _geometry_identities(state)
        }
    )
    StateManager(workspace).create_project(PROJECT_ID, state)
    application = ProductionApplication.create(
        workspace,
        PROJECT_ID,
        UninvokedAgentAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
        additional_tool_registrations=GearworksTools.registrations(),
    )
    _publish_source_artifacts(application, state)
    return application


def _build_live_application(tmp_path: Path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /requirements/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/requirements/*"],
                        "invalidates": [
                            "analysis.continuous_clearance_proof",
                            "analysis.kinematic_sweep",
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    from mechcad_harness.state import StateManager

    state = production_state()
    state = state.model_copy(
        update={
            "yagi_payload_carrier_requirements": list(state.yagi_payload_carrier_requirements)
            + _geometry_identities(state)
        }
    )
    StateManager(workspace).create_project(PROJECT_ID, state)
    application = ProductionApplication.create(
        workspace,
        PROJECT_ID,
        UninvokedAgentAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )
    _publish_source_artifacts(application, state)
    return application


def _publish_source_step(application, *, part_id="candidate-trusted-source", size=(20.0, 20.0, 5.0)):
    source = application.load_state()
    run = application.create_run().run
    program = CadPartProgram(
        part_id=part_id,
        operations=(
            BasePlateOperation(
                operation_id="source-base",
                length_mm=size[0],
                width_mm=size[1],
                thickness_mm=size[2],
            ),
        ),
    )
    generated = FreeCADBackend().generate_program(
        program,
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id=run.run_id,
        revision=source.revision,
        state_hash=source.state_hash,
    )
    artifact = generated.step
    artifact_path = application.state_manager.workspace / artifact.relative_path
    assert artifact.artifact_type is ArtifactType.STEP
    assert artifact_path.read_bytes()
    assert artifact.sha256 == "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    return artifact


def publish_source_step(application, *, part_id="candidate-trusted-source", size=(20.0, 20.0, 5.0)):
    """Public deterministic fixture builder for composed integration tests."""
    return _publish_source_step(application, part_id=part_id, size=size)


def _publish_gear_step(application, *, teeth=20):
    source = application.load_state()
    run = application.create_run().run
    task = TaskDefinition(
        task_id="TASK-candidate-gear",
        run_id=run.run_id,
        task_type="tool",
        objective="cad",
        bound_revision=source.revision,
        bound_state_hash=source.state_hash,
        allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
    )
    application.run_controller.add_task(run.run_id, task)
    result = application.tool_broker.execute(
        run.run_id,
        task.task_id,
        "mechcad-build-spur-gear-cad",
        "1.0",
        {
            "module_mm": 2.0,
            "teeth": teeth,
            "face_width_mm": 5.0,
            "pressure_angle_deg": 20.0,
            "requested_formats": ["step"],
        },
    )
    assert result.status.value == "succeeded"
    reference = result.output["artifact_references"][0]
    store = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id=run.run_id,
        task_id=task.task_id,
    )
    artifact = store.existing(reference["artifact_id"])
    assert artifact is not None and artifact.artifact_type is ArtifactType.STEP
    artifact_path = application.state_manager.workspace / artifact.relative_path
    assert reference["sha256"] == "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    return artifact


def publish_gear_step(application, *, teeth=20):
    """Public deterministic gear fixture builder for composed integration tests."""
    return _publish_gear_step(application, teeth=teeth)


def _source_spec(specification, artifact):
    reference = GeometrySourceReference(
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_identity=f"fixture:trusted-step:{artifact.artifact_id}",
    )
    return type(specification).model_validate(
        specification.model_dump(mode="json")
        | {"geometry_source": reference.model_dump(mode="json"), "specification_hash": "pending"}
    )


def _candidate_template(
    architecture,
    source_artifact,
    positions,
    *,
    gear_artifact=None,
    extra_design_variables=(),
):
    candidate_template = template(architecture)
    source_fields = (
        "motor_specification",
        "shaft_specification",
        "bearing_a_specification",
        "bearing_b_specification",
        "hub_specification",
    )
    def source_for(instance_id):
        return source_artifact[instance_id] if isinstance(source_artifact, dict) else source_artifact

    updates = {
        field: _source_spec(
            getattr(candidate_template, field),
            source_for({
                "motor_specification": "drive-motor",
                "shaft_specification": "output-shaft",
                "bearing_a_specification": "bearing-a",
                "bearing_b_specification": "bearing-b",
                "hub_specification": "output-hub",
            }[field]),
        )
        for field in source_fields
    }
    if isinstance(source_artifact, dict):
        for field, instance_id in (
            ("mount_specification", "motor-mount"),
            ("driven_body_specification", "payload-body"),
        ):
            if instance_id in source_artifact:
                updates[field] = _source_spec(
                    getattr(candidate_template, field), source_artifact[instance_id]
                )
    if architecture is DriveArchitecture.EXTERNAL_SPUR_REDUCTION:
        assert gear_artifact is not None
        updates.update(
            driver_gear_specification=_source_spec(
                candidate_template.driver_gear_specification,
                gear_artifact["driver-gear"] if isinstance(gear_artifact, dict) else gear_artifact,
            ),
            driven_gear_specification=_source_spec(
                candidate_template.driven_gear_specification,
                gear_artifact["driven-gear"] if isinstance(gear_artifact, dict) else gear_artifact,
            ),
            support_mount_specifications=tuple(
                _source_spec(specification, source_for(instance_id))
                for specification, instance_id in zip(
                    candidate_template.support_mount_specifications,
                    ("support-mount-a", "support-mount-b"),
                    strict=True,
                )
            ),
        )

    design_variables = [CandidateDesignVariable(name="selected-output-shaft-diameter", value=12.0)]
    for instance_id, (x_mm, y_mm, z_mm) in positions.items():
        for axis, value in (("x_mm", x_mm), ("y_mm", y_mm), ("z_mm", z_mm)):
            design_variables.append(
                CandidateDesignVariable(name=f"{instance_id}.placement.{axis}", value=value)
            )
    for instance_id, dimensions in {
        "motor-mount": (30.0, 30.0, 5.0),
        "payload-body": (20.0, 20.0, 5.0),
    }.items():
        for axis, value in zip(("length_mm", "width_mm", "thickness_mm"), dimensions, strict=True):
            design_variables.append(CandidateDesignVariable(name=f"{instance_id}.{axis}", value=value))
    design_variables.extend(extra_design_variables)
    return candidate_template.model_copy(update=updates | {"design_variables": tuple(design_variables)})


def _bind_candidate_template_specs(application, candidate_template):
    from mechcad_harness.artifacts import ArtifactType
    from mechcad_harness.models.semantic_component import bind_component_specification_semantic_identity
    from mechcad_harness.step_content_identity import step_content_identity_v1

    store = application.candidate_publication_service.store
    specification_fields = (
        "motor_specification",
        "shaft_specification",
        "bearing_a_specification",
        "bearing_b_specification",
        "hub_specification",
        "mount_specification",
        "driven_body_specification",
        "driver_gear_specification",
        "driven_gear_specification",
    )
    pending = [
        (field, getattr(candidate_template, field))
        for field in specification_fields
        if getattr(candidate_template, field, None) is not None
        and getattr(candidate_template, field).specification_hash == "pending"
    ]
    support_specs = candidate_template.support_mount_specifications
    pending.extend(
        (f"support_mount_specifications[{index}]", spec)
        for index, spec in enumerate(support_specs)
        if spec.specification_hash == "pending"
    )
    context = {}
    for _, spec in pending:
        reference = spec.geometry_source
        if reference is None:
            continue
        verified = store.read_verified_in_project(
            reference.artifact_id,
            expected_type=ArtifactType.STEP,
            expected_hash=reference.artifact_hash,
        )
        if verified is None:
            raise CandidateIntegrityError(
                f"candidate template source artifact is missing: {reference.artifact_id}"
            )
        _, content = verified
        content_identity = step_content_identity_v1(content)
        context[
            (
                reference.artifact_id,
                reference.artifact_hash,
                reference.source_identity,
                reference.format,
                reference.coordinate_system_id,
            )
        ] = content_identity.model_dump(mode="json")
    updates = {
        field: bind_component_specification_semantic_identity(spec, context)
        for field, spec in pending
        if not field.startswith("support_mount_specifications")
    }
    if any(field.startswith("support_mount_specifications") for field, _ in pending):
        updates["support_mount_specifications"] = tuple(
            bind_component_specification_semantic_identity(spec, context)
            if spec.specification_hash == "pending"
            else spec
            for spec in support_specs
        )
    return candidate_template.model_copy(update=updates)


def _bounded_legacy_candidate(
    application,
    source_artifact,
    positions,
    *,
    architecture=DriveArchitecture.DIRECT_DRIVE,
    gear_artifact=None,
    extra_design_variables=(),
):
    """Build an explicit legacy candidate for M12-5 replay fixtures.

    Mount/body use the existing component definitions and candidate-bound geometry
    variables, with no geometry source. Other supplied components retain their exact
    published STEP sources. External-spur gears and support mounts retain their
    supplied sources as well. This fixture is deliberately @1: the M12-5 promotion
    integration path is a legacy replay path and must not mix it with candidate@2.
    """

    from mechcad_harness.candidates import (
        CandidateSynthesisPolicy,
        CandidateSynthesisRequest,
    )
    from mechcad_harness.revolute_drive.models import RevoluteDriveTemplateInput

    pending_request = make_request(application, architecture)
    request_payload = pending_request.model_dump(mode="json")
    request_payload["schema_version"] = "candidate-synthesis-request@1"
    request_payload.pop("semantic_source_binding_hash", None)
    request_payload["request_hash"] = "pending"
    synthesis_request = CandidateSynthesisRequest.model_validate(request_payload)

    candidate_template = _candidate_template(
        architecture,
        source_artifact,
        positions,
        gear_artifact=gear_artifact,
        extra_design_variables=extra_design_variables,
    )
    source_for = (
        lambda instance_id: source_artifact[instance_id]
        if isinstance(source_artifact, dict)
        else source_artifact
    )
    updates = {
            "motor_specification": _source_spec(
                motor_specification(), source_for("drive-motor")
            ),
            "shaft_specification": _source_spec(
                shaft_specification(), source_for("output-shaft")
            ),
            "bearing_a_specification": _source_spec(
                bearing_specification(), source_for("bearing-a")
            ),
            "bearing_b_specification": _source_spec(
                bearing_specification(), source_for("bearing-b")
            ),
            "hub_specification": _source_spec(
                hub_specification(), source_for("output-hub")
            ),
            "mount_specification": mount_specification(),
            "driven_body_specification": body_specification(),
        }
    if architecture is DriveArchitecture.EXTERNAL_SPUR_REDUCTION:
        if gear_artifact is None:
            raise AssertionError("external-spur legacy fixture requires gear STEP artifacts")
        gear_for = (
            lambda instance_id: gear_artifact[instance_id]
            if isinstance(gear_artifact, dict)
            else gear_artifact
        )
        updates.update(
            {
                "driver_gear_specification": _source_spec(
                    gear_specification(20), gear_for("driver-gear")
                ),
                "driven_gear_specification": _source_spec(
                    gear_specification(100), gear_for("driven-gear")
                ),
                "support_mount_specifications": tuple(
                    _source_spec(support_mount_specification(), source_for(instance_id))
                    for instance_id in ("support-mount-a", "support-mount-b")
                ),
            }
        )
    candidate_template = candidate_template.model_copy(update=updates)
    candidate_template = RevoluteDriveTemplateInput.model_validate(
        candidate_template.model_dump(mode="json")
    )

    base_policy = policy_for(architecture)
    entries = list(base_policy.entries)
    declared = {entry[0] for entry in entries}
    for variable in candidate_template.design_variables:
        key = f"allow-design-variable:{variable.name}"
        if key not in declared:
            entries.append(
                (
                    key,
                    json.dumps(
                        {"value": variable.value},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "hard_admissibility",
                )
            )
    synthesis_policy = CandidateSynthesisPolicy(entries=tuple(entries))
    construction = application.revolute_drive_service.construct_candidate(
        synthesis_request, synthesis_policy, candidate_template
    )
    if construction.candidate is None:
        raise AssertionError(
            f"bounded legacy candidate construction failed: {construction.reason}"
        )
    source_state = application.state_manager.load_current_state(application.project_id)
    engineering_requirements = (
        requirements(require_nominal_interface_compatibility=True)
        if architecture is DriveArchitecture.DIRECT_DRIVE
        else spur_requirements(require_nominal_interface_compatibility=True)
    )
    m12_result = application.revolute_drive_service.evaluate(
        construction.candidate,
        synthesis_request,
        synthesis_policy,
        engineering_requirements,
        source_state=source_state,
    )
    return construction.candidate, synthesis_request, synthesis_policy, m12_result


def _real_candidate(application, source_artifact, positions, *, architecture=DriveArchitecture.DIRECT_DRIVE, gear_artifact=None, extra_design_variables=()):
    from mechcad_harness.candidates.services import bind_candidate_synthesis_request_semantic_identity

    synthesis_request = bind_candidate_synthesis_request_semantic_identity(
        make_request(application, architecture),
        state_manager=application.state_manager,
        store=application.candidate_publication_service.store,
        project_id=application.project_id,
    )
    synthesis_policy = policy_for(architecture)
    candidate_template = _candidate_template(
        architecture,
        source_artifact,
        positions,
        gear_artifact=gear_artifact,
        extra_design_variables=extra_design_variables,
    )
    candidate_template = _bind_candidate_template_specs(application, candidate_template)
    policy_entries = list(synthesis_policy.entries)
    declared_policy_keys = {entry[0] for entry in policy_entries}
    for variable in candidate_template.design_variables:
        key = f"allow-design-variable:{variable.name}"
        if key not in declared_policy_keys:
            policy_entries.append(
                (
                    key,
                    json.dumps({"value": variable.value}, sort_keys=True, separators=(",", ":")),
                    "hard_admissibility",
                )
            )
    synthesis_policy = CandidateSynthesisPolicy(entries=tuple(policy_entries))
    engineering_requirements = (
        requirements(require_nominal_interface_compatibility=True)
        if architecture is DriveArchitecture.DIRECT_DRIVE
        else spur_requirements(require_nominal_interface_compatibility=True)
    )
    outcome = application.realize_and_evaluate_revolute_drive(
        request=synthesis_request,
        policy=synthesis_policy,
        template_input=candidate_template,
        requirements=engineering_requirements,
    )
    assert outcome.construction.status.value == "admissible" and outcome.evaluation is not None
    assert outcome.construction.candidate is not None
    assert outcome.evaluation.status.value == "admissible"
    return outcome.construction.candidate, synthesis_request, synthesis_policy, outcome.evaluation


def real_candidate(application, source_artifact, positions, *, architecture=DriveArchitecture.DIRECT_DRIVE, gear_artifact=None, extra_design_variables=()):
    """Public deterministic candidate builder for composed integration tests."""
    return _real_candidate(
        application,
        source_artifact,
        positions,
        architecture=architecture,
        gear_artifact=gear_artifact,
        extra_design_variables=extra_design_variables,
    )


def _cad_request(candidate, *, bounded_instance_ids=()):
    if candidate.schema_version == "mechanical-design-candidate@2":
        if bounded_instance_ids:
            raise ValueError(
                "candidate@2 source-backed specs cannot use bounded CAD mappings"
            )
        return _cad_m10_inputs_v2(
            candidate, request_only=True
        )
    bounded_instance_ids = set(bounded_instance_ids)
    specifications = {
        specification.specification_hash: specification
        for specification in candidate.component_specifications
    }
    component_by_id = {component.instance_id: component for component in candidate.realization.components}
    variables = {variable.name: variable.value for variable in candidate.design_variables}
    mappings = []
    design_variable_identities = set()
    for component in candidate.realization.components:
        instance_id = component.instance_id
        specification = specifications[component.specification_hash]
        cad_id = f"cad-{instance_id}"
        placement_values = tuple(
            variables[f"{instance_id}.placement.{axis}"] for axis in ("x_mm", "y_mm", "z_mm")
        )
        placement = CadRigidTransform(
            x_mm=placement_values[0], y_mm=placement_values[1], z_mm=placement_values[2]
        )
        placement_inputs = tuple(
            f"candidate:design-variable:{instance_id}.placement.{axis}"
            for axis in ("x_mm", "y_mm", "z_mm")
        )
        design_variable_identities.update(placement_inputs)
        origin = CandidatePlacementOrigin(
            authority="candidate_design_variable",
            input_identities=placement_inputs,
            derivation="candidate-placement-fixture@1",
            transform=placement,
        )
        if specification.geometry_source is not None and instance_id not in bounded_instance_ids:
            imported = ImportedCadComponent(
                component_id=cad_id,
                artifact_id=specification.geometry_source.artifact_id,
                artifact_hash=specification.geometry_source.artifact_hash,
                source_revision=candidate.source_binding.source_revision,
                source_state_hash=candidate.source_binding.source_state_hash,
            )
            mapping = CandidateCadInstanceMapping(
                candidate_hash=candidate.candidate_hash,
                physical_instance_id=instance_id,
                cad_instance_id=cad_id,
                fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
                representation_identity=imported_component_hash(imported),
                source_geometry_identity=specification.geometry_source.artifact_hash,
                geometry_definition_identities=(specification.geometry_source.artifact_id,),
                placement=placement,
                placement_origin=origin,
            )
        else:
            dimensions = tuple(
                variables[f"{instance_id}.{axis}"]
                for axis in ("length_mm", "width_mm", "thickness_mm")
            )
            geometry_inputs = tuple(
                f"candidate:design-variable:{instance_id}.{axis}"
                for axis in ("length_mm", "width_mm", "thickness_mm")
            )
            design_variable_identities.update(geometry_inputs)
            program = compile_mounting_plate(
                MountingPlateDesignSpec(
                    part_id=cad_id,
                    plate_length_mm=dimensions[0],
                    plate_width_mm=dimensions[1],
                    plate_thickness_mm=dimensions[2],
                )
            )
            mapping = CandidateCadInstanceMapping(
                candidate_hash=candidate.candidate_hash,
                physical_instance_id=instance_id,
                cad_instance_id=cad_id,
                fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
                representation_identity=cad_program_hash(program),
                geometry_definition_identities=geometry_inputs,
                placement=placement,
                placement_origin=origin,
            )
        mappings.append(mapping)
    return CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-live-capstone@1",
        compiler_identity="generic-mounting-plate-compiler",
        compiler_version="1.0",
        candidate_instance_ids=tuple(component_by_id),
        mappings=tuple(mappings),
        design_variable_identities=tuple(sorted(design_variable_identities)),
    )


def _explicit_bounded_cad_request(candidate):
    return _cad_request(candidate, bounded_instance_ids=("motor-mount", "payload-body"))


def test_candidate_cad_fixture_dispatch_keeps_bounded_legacy_and_trusted_v3_families(tmp_path):
    application = build_application(tmp_path)
    source_store = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id="SOURCE",
    )
    source_artifacts = {}
    for instance_id, slot in (
        ("drive-motor", "motor"),
        ("output-shaft", "shaft"),
        ("bearing-a", "bearing"),
        ("bearing-b", "bearing"),
        ("output-hub", "hub"),
    ):
        source_artifacts[instance_id] = source_store.read_verified_strict(
            f"ART-{slot}", expected_type=ArtifactType.STEP
        )[0]
    positions = {
        "drive-motor": (100.0, 100.0, 0.0),
        "output-shaft": (80.0, 0.0, 0.0),
        "bearing-a": (90.0, 30.0, 0.0),
        "bearing-b": (90.0, -30.0, 0.0),
        "output-hub": (80.0, 0.0, 0.0),
        "motor-mount": (0.0, 0.0, 0.0),
        "payload-body": (80.0, 0.0, 0.0),
    }
    bounded_candidate, bounded_request, _, _ = _bounded_legacy_candidate(
        application, source_artifacts, positions
    )
    bounded_cad_request = _explicit_bounded_cad_request(bounded_candidate)
    bounded_specs = {
        component.instance_id: next(
            specification
            for specification in bounded_candidate.component_specifications
            if specification.specification_hash == component.specification_hash
        )
        for component in bounded_candidate.realization.components
    }

    assert bounded_candidate.schema_version == "mechanical-design-candidate@1"
    assert bounded_request.schema_version == "candidate-synthesis-request@1"
    assert bounded_cad_request.schema_version == "candidate-cad-realization-request@1"
    for instance_id in ("motor-mount", "payload-body"):
        assert bounded_specs[instance_id].schema_version == "component-specification@1"
        assert bounded_specs[instance_id].geometry_source is None
    bounded = {
        mapping.physical_instance_id: mapping
        for mapping in bounded_cad_request.mappings
        if mapping.fidelity is CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION
    }
    assert set(bounded) == {"motor-mount", "payload-body"}
    assert all(mapping.source_geometry_identity is None for mapping in bounded.values())
    assert tuple(mapping.mapping_hash for mapping in bounded_cad_request.mappings) == tuple(
        mapping.mapping_hash
        for mapping in _explicit_bounded_cad_request(bounded_candidate).mappings
    )

    source_candidate, *_ = _candidate_and_result(application)
    v3_request = _cad_request(source_candidate)
    assert source_candidate.schema_version == "mechanical-design-candidate@2"
    assert v3_request.schema_version == "candidate-cad-realization-request@3"
    assert all(
        mapping.schema_version == "candidate-cad-instance-mapping@2"
        and mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
        and mapping.source_geometry_identity is not None
        for mapping in v3_request.mappings
    )


def test_external_spur_trusted_provider_failure_never_downgrades_to_bounded_geometry(tmp_path, monkeypatch):
    application = _build_gear_application(tmp_path)
    source_before = application.load_state()
    monkeypatch.setattr(
        PyGearworksAdapter,
        "healthcheck",
        lambda self: BackendHealth(
            backend_name="py-gearworks",
            status=BackendHealthStatus.UNAVAILABLE,
            message="optional external-spur dependencies are unavailable",
        ),
    )
    run = application.create_run().run
    task = TaskDefinition(
        task_id="TASK-candidate-gear-unavailable",
        run_id=run.run_id,
        task_type="tool",
        objective="trusted external-spur CAD source",
        bound_revision=source_before.revision,
        bound_state_hash=source_before.state_hash,
        allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
    )
    application.run_controller.add_task(run.run_id, task)

    with pytest.raises(ToolExecutionError) as failure:
        application.tool_broker.execute(
            run.run_id,
            task.task_id,
            "mechcad-build-spur-gear-cad",
            "1.0",
            {
                "module_mm": 2.0,
                "teeth": 20,
                "face_width_mm": 5.0,
                "pressure_angle_deg": 20.0,
                "requested_formats": ["step"],
            },
        )

    assert isinstance(failure.value.__cause__, BackendUnavailableError)
    result_paths = tuple(
        (
            application.state_manager.workspace
            / "projects"
            / PROJECT_ID
            / "runs"
            / run.run_id
            / "tool_results"
        ).glob("*.json")
    )
    assert len(result_paths) == 1
    failed_result = application.tool_broker.store.load_result(PROJECT_ID, run.run_id, result_paths[0].stem)
    assert failed_result.status is ToolResultStatus.FAILED
    assert failed_result.error is not None
    assert failed_result.error.error_type == "BackendUnavailableError"
    assert failed_result.output is None
    assert not tuple((application.state_manager.workspace / "artifacts").glob("**/*"))
    source_after = application.load_state()
    assert (source_after.revision, source_after.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available through deterministic discovery")
@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras are not installed")
def test_candidate_realization_rejects_unavailable_trusted_external_spur_artifact_without_downgrade(
    tmp_path, monkeypatch
):
    discovery = discover_freecad()
    monkeypatch.setenv(
        "MECHCAD_FREECADCMD",
        discovery.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE,
    )
    application = _build_gear_application(tmp_path)
    source_before = application.load_state()
    source_artifacts = {
        instance_id: _publish_source_step(
            application,
            part_id=f"candidate-provider-boundary-{instance_id}",
            size=(20.0 + index, 20.0, 5.0),
        )
        for index, instance_id in enumerate(
            (
                "drive-motor",
                "output-shaft",
                "bearing-a",
                "bearing-b",
                "output-hub",
                "support-mount-a",
                "support-mount-b",
            )
        )
    }
    source_artifacts["motor-mount"] = _publish_source_step(
        application,
        part_id="candidate-provider-boundary-motor-mount",
        size=(30.0, 30.0, 5.0),
    )
    source_artifacts["payload-body"] = _publish_source_step(
        application,
        part_id="candidate-provider-boundary-payload-body",
        size=(20.0, 20.0, 5.0),
    )
    gear_artifact = {
        "driver-gear": _publish_gear_step(application, teeth=20),
        "driven-gear": _publish_gear_step(application, teeth=100),
    }
    positions = {
        "drive-motor": (150.0, 150.0, 0.0),
        "driver-gear": (40.0, 0.0, 0.0),
        "driven-gear": (80.0, 0.0, 0.0),
        "output-shaft": (80.0, 0.0, 0.0),
        "bearing-a": (100.0, 30.0, 0.0),
        "bearing-b": (100.0, -30.0, 0.0),
        "output-hub": (80.0, 0.0, 0.0),
        "motor-mount": (0.0, 0.0, 0.0),
        "support-mount-a": (120.0, 30.0, 0.0),
        "support-mount-b": (120.0, -30.0, 0.0),
        "payload-body": (80.0, 0.0, 0.0),
    }
    candidate, synthesis_request, synthesis_policy, _ = _real_candidate(
        application,
        source_artifacts,
        positions,
        architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
        gear_artifact=gear_artifact,
    )
    request = _cad_request(candidate)
    trusted = {
        mapping.physical_instance_id: mapping
        for mapping in request.mappings
        if mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
    }
    assert {instance_id for instance_id in trusted} >= {"driver-gear", "driven-gear"}
    assert all(
        mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
        for mapping in request.mappings
    )

    driver_artifact_path = application.state_manager.workspace / gear_artifact["driver-gear"].relative_path
    driver_artifact_path.unlink()
    monkeypatch.setattr(
        PyGearworksAdapter,
        "healthcheck",
        lambda self: BackendHealth(
            backend_name="py-gearworks",
            status=BackendHealthStatus.UNAVAILABLE,
            message="optional external-spur dependencies are unavailable",
        ),
    )

    with pytest.raises(
        CandidateCadIntegrityError,
        match="candidate required geometry artifact is missing or ambiguous|trusted source artifact is missing",
    ):
        application.realize_candidate_cad(
            candidate,
            synthesis_request,
            synthesis_policy,
            request,
        )

    assert trusted["driver-gear"].fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
    source_after = application.load_state()
    assert (source_after.revision, source_after.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available through deterministic discovery")
def test_explicit_bounded_collision_fixture_is_candidate_bound_not_trusted_fallback(tmp_path, monkeypatch):
    discovery = discover_freecad()
    monkeypatch.setenv(
        "MECHCAD_FREECADCMD",
        discovery.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE,
    )
    application = _build_live_application(tmp_path)
    source_artifacts = {
        instance_id: _publish_source_step(
            application,
            part_id=f"candidate-bounded-{instance_id}",
            size=(20.0 + index, 20.0, 5.0),
        )
        for index, instance_id in enumerate(
            ("drive-motor", "output-shaft", "bearing-a", "bearing-b", "output-hub")
        )
    }
    positions = {
        "drive-motor": (100.0, 100.0, 0.0),
        "output-shaft": (80.0, 0.0, 0.0),
        "bearing-a": (90.0, 30.0, 0.0),
        "bearing-b": (90.0, -30.0, 0.0),
        "output-hub": (80.0, 0.0, 0.0),
        "motor-mount": (0.0, 0.0, 0.0),
        "payload-body": (80.0, 0.0, 0.0),
    }
    candidate, synthesis_request, synthesis_policy, _ = _bounded_legacy_candidate(
        application, source_artifacts, positions
    )
    request = _explicit_bounded_cad_request(candidate)
    bounded = tuple(
        mapping
        for mapping in request.mappings
        if mapping.fidelity is CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION
    )
    assert {mapping.physical_instance_id for mapping in bounded} == {"motor-mount", "payload-body"}
    assert all(mapping.source_geometry_identity is None for mapping in bounded)
    assert all(
        all(identity.startswith("candidate:design-variable:") for identity in mapping.geometry_definition_identities)
        for mapping in bounded
    )
    assert set(request.design_variable_identities) >= {
        identity
        for mapping in bounded
        for identity in mapping.geometry_definition_identities + mapping.placement_origin.input_identities
        if identity.startswith("candidate:design-variable:")
    }

    stage = application.realize_candidate_cad(
        candidate, synthesis_request, synthesis_policy, request
    )
    assert stage.status is CandidateCadStageStatus.SUCCESS
    assert stage.realization is not None
    assert all(
        mapping.fidelity is CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION
        or mapping.source_geometry_identity is not None
        for mapping in stage.realization.mappings
    )
    assert stage.realization.verified_source_content_identities == tuple(
        source_artifacts[component.instance_id].sha256
        for component in candidate.realization.components
        if component.instance_id in source_artifacts
    )



def _m10_inputs(candidate, cad_stage, *, external_spur=False, home=False):
    assert cad_stage.realization is not None
    realization = cad_stage.realization
    dispositions = []
    for component in candidate.realization.components:
        disposition = CandidateM10BodyDisposition.FIXED
        group = None
        if component.instance_id in {"output-shaft", "output-hub", "payload-body"}:
            disposition = CandidateM10BodyDisposition.OUTPUT_RIGID
            group = "output-joint"
        if external_spur and component.instance_id == "driver-gear":
            disposition = CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED
            group = None
        dispositions.append(
            CandidateM10ConstituentDisposition(
                physical_instance_id=component.instance_id,
                cad_instance_id=f"cad-{component.instance_id}",
                constituent_key=component.instance_id,
                disposition=disposition,
                output_transform_group=group,
            )
        )
    binding = CandidateM10Binding(
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        model=KinematicModel(
            model_id="candidate-live-capstone-model",
            joints=(
                RevoluteJointModel(
                    joint_id="output-joint",
                    parent_instance_id="cad-motor-mount",
                    child_instance_id="cad-output-shaft",
                    axis_origin_x_mm=0.0,
                    axis_direction_z=1.0,
                ),
            ),
        ),
        output_joint_id="output-joint",
        output_axis=RevoluteAxis(
            origin_x_mm=0.0,
            origin_y_mm=0.0,
            origin_z_mm=0.0,
            direction_x=0.0,
            direction_y=0.0,
            direction_z=1.0,
            frame_id="joint:output-joint",
        ),
        driver_gear_constituent_key="driver-gear" if external_spur else None,
        constituent_dispositions=tuple(dispositions),
    )
    scope = CandidateM10EvaluationScope(
        output_joint_semantic_key="primary-output-revolute",
        angle_interval_deg=(0.0, 360.0) if home else (-10.0, 10.0),
        required_clearance_mm=1.0,
        pair_scope_requirements=(
            CandidateM10PairScopeRequirement(
                requirement_key="hub-mount-clearance",
                first_constituent_key="output-hub",
                second_constituent_key="motor-mount",
                required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
            ),
        ),
        fidelity_requirements=(
            ("output-hub", CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY),
            ("motor-mount", CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION),
        ),
        proof_service_version="m10-single-axis-continuous-proof@1",
    )
    classifications = None
    if external_spur:
        base = CandidateCollisionPairInventory.complete_for(realization, binding, scope)
        classifications = tuple(
                item.model_copy(
                update={"classification": CandidateM10PairClassification.INTENDED_CONTACT_EXCLUDED, "reason": "declared gear mesh interface is outside M10 scope", "classification_hash": "pending"}
            )
            if set(item.pair) == {"cad-driver-gear", "cad-driven-gear"}
            else item
            for item in base.classifications
        )
    inventory = CandidateCollisionPairInventory.complete_for(
        realization, binding, scope, classifications or ()
    )
    request = CandidateM10EvaluationRequest(
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding.model_hash,
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in realization.mappings)),
        inventory=inventory,
    )
    return scope, binding, request


def m10_inputs(candidate, cad_stage, *, external_spur=False, home=False):
    """Public M10 fixture boundary used by promotion integration tests."""
    return _m10_inputs(candidate, cad_stage, external_spur=external_spur, home=home)


def _evaluate_real_candidate(application, candidate, synthesis_request, synthesis_policy, m12_result, *, external_spur=False, not_proven=False, scope_pair=None):
    if candidate.schema_version == "mechanical-design-candidate@2":
        _cad_stage, _m10_stage, scope, binding, m10_request, cad_request = (
            _cad_m10_inputs_v2(
                candidate,
                application=application,
                synthesis_request=synthesis_request,
                synthesis_policy=synthesis_policy,
                publish_cad=False,
                not_proven=not_proven,
                external_spur=external_spur,
                axis_origin_x_mm=0.0,
                scope_pair=scope_pair,
            )
        )
        evaluation = application.evaluate_candidate(
            candidate,
            synthesis_request,
            synthesis_policy,
            m12_result,
            cad_request,
            m10_request,
            scope,
            binding,
            evaluation_policy=CandidateEvaluationPolicy(),
        )
        return evaluation, cad_request, scope, binding, m10_request
    cad_request = _cad_request(candidate)
    cad_stage = application.realize_candidate_cad(
        candidate, synthesis_request, synthesis_policy, cad_request
    )
    assert cad_stage.status is CandidateCadStageStatus.SUCCESS
    scope, binding, m10_request = m10_inputs(candidate, cad_stage, external_spur=external_spur, home=not_proven)
    if not_proven:
        application.candidate_m10_evaluation_service.max_exact_evaluations = 2
        application.candidate_m10_evaluation_service.max_depth = 1
    evaluation = application.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_request,
        m10_request,
        scope,
        binding,
        evaluation_policy=CandidateEvaluationPolicy(),
    )
    return evaluation, cad_request, scope, binding, m10_request


def evaluate_real_candidate(application, candidate, synthesis_request, synthesis_policy, m12_result, *, external_spur=False, not_proven=False, scope_pair=None):
    """Public deterministic evaluation builder for composed integration tests."""
    return _evaluate_real_candidate(
        application,
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        external_spur=external_spur,
        not_proven=not_proven,
        scope_pair=scope_pair,
    )


def cad_m10_inputs(
    candidate,
    *,
    application=None,
    synthesis_request=None,
    synthesis_policy=None,
    scope_pair=None,
):
    """Public bounded CAD/M10 fixture builder for composed integration tests."""
    return _cad_m10_inputs(
        candidate,
        application=application,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        scope_pair=scope_pair,
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available through deterministic discovery")
def test_live_direct_drive_clear_collision_and_not_proven_chain(tmp_path, monkeypatch):
    discovery = discover_freecad()
    executable = discovery.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE
    monkeypatch.setenv("MECHCAD_FREECADCMD", executable)
    runtime = discover_freecad().require_available()
    print(
        "M12_4_RUNTIME="
        + json.dumps(
            {
                "available": runtime.available,
                "executable": runtime.executable,
                "version": runtime.version,
                "importable": runtime.importable,
                "execution_boundary": runtime.execution_boundary,
            },
            sort_keys=True,
        )
    )

    application = _build_live_application(tmp_path)
    source_before = application.load_state()
    source_artifacts = {
        instance_id: _publish_source_step(
            application,
            part_id=f"candidate-direct-{instance_id}",
            size=(20.0 + index, 20.0, 5.0),
        )
        for index, instance_id in enumerate(
            ("drive-motor", "output-shaft", "bearing-a", "bearing-b", "output-hub")
        )
    }
    source_artifact_path = application.state_manager.workspace / source_artifacts["output-hub"].relative_path
    source_bytes = source_artifact_path.read_bytes()

    common_positions = {
        "drive-motor": (100.0, 100.0, 0.0),
        "output-shaft": (80.0, 0.0, 0.0),
        "bearing-a": (90.0, 30.0, 0.0),
        "bearing-b": (90.0, -30.0, 0.0),
        "output-hub": (80.0, 0.0, 0.0),
        "motor-mount": (0.0, 0.0, 0.0),
        "payload-body": (80.0, 0.0, 0.0),
    }
    clear_candidate, clear_request, clear_policy, clear_m12 = _bounded_legacy_candidate(
        application, source_artifacts, common_positions
    )
    clear_evaluation, clear_cad_request, clear_scope, clear_binding, clear_m10_request = _evaluate_real_candidate(
        application, clear_candidate, clear_request, clear_policy, clear_m12
    )
    assert clear_m12.status.value == "admissible"
    assert clear_evaluation.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS
    assert clear_evaluation.m10_stage_outcome.status is CandidateM10StageStatus.SUCCESS
    clear_proof = clear_evaluation.m10_stage_outcome.pair_proofs[0].result
    assert clear_proof.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR
    assert clear_evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
    assert clear_evaluation.metrics[0].key.value == "verified_clearance_lower_bound_mm"
    assert clear_evaluation.metrics[0].value > 1.0
    assert clear_evaluation.cad_stage_outcome.realization is not None
    assert clear_evaluation.cad_stage_outcome.realization.verified_source_content_identities == tuple(
        source_artifacts[component.instance_id].sha256
        for component in clear_candidate.realization.components
        if component.instance_id in source_artifacts
    )
    assert clear_evaluation.cad_stage_outcome.realization.assembly.imported_components
    clear_evidence = application.get_continuous_proof_evidence(clear_proof.result_hash)
    assert clear_evidence is not None
    assert clear_evidence.continuous_proof_execution_provenance is not None
    assert clear_evidence.continuous_proof_execution_provenance.provider_name == "freecad-transient-exact"
    assert clear_evidence.continuous_proof_execution_provenance.execution_mode == "freecadcmd-subprocess"
    assert clear_evidence.continuous_proof_execution_provenance.backend_provenance is not None
    assert clear_evidence.continuous_proof_execution_provenance.backend_provenance.library_name == "FreeCAD"

    collision_positions = dict(common_positions)
    collision_positions["output-shaft"] = (0.0, 0.0, 0.0)
    collision_positions["output-hub"] = (0.0, 0.0, 0.0)
    collision_positions["payload-body"] = (0.0, 0.0, 0.0)
    collision_candidate, collision_request, collision_policy, collision_m12 = _bounded_legacy_candidate(
        application, source_artifacts, collision_positions
    )
    collision_evaluation, _, _, _, _ = _evaluate_real_candidate(
        application, collision_candidate, collision_request, collision_policy, collision_m12
    )
    assert collision_m12.status.value == "admissible"
    assert collision_evaluation.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS
    collision_proof = collision_evaluation.m10_stage_outcome.pair_proofs[0].result
    assert collision_proof.status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS
    assert collision_proof.collision_witness is not None
    assert collision_proof.collision_witness.interference_volume_mm3 > 0.0
    assert collision_evaluation.outcome is CandidateEvaluationOutcome.INFEASIBLE
    assert collision_evaluation.hard_witnesses

    not_proven_candidate, not_proven_request, not_proven_policy, not_proven_m12 = _bounded_legacy_candidate(
        application, source_artifacts, common_positions
    )
    not_proven_evaluation, _, not_proven_scope, _, _ = _evaluate_real_candidate(
        application,
        not_proven_candidate,
        not_proven_request,
        not_proven_policy,
        not_proven_m12,
        not_proven=True,
    )
    assert not_proven_scope.angle_interval_deg == (0.0, 360.0)
    not_proven_proof = not_proven_evaluation.m10_stage_outcome.pair_proofs[0].result
    assert not_proven_proof.status is ContinuousSingleAxisProofStatus.NOT_PROVEN
    assert not_proven_proof.collision_witness is None
    assert not_proven_evaluation.outcome is CandidateEvaluationOutcome.UNRESOLVED
    assert not_proven_evaluation.hard_witnesses == ()

    source_after = application.load_state()
    assert (source_after.revision, source_after.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    assert source_artifact_path.read_bytes() == source_bytes
    print(
        "M12_4_DIRECT_RESULTS="
        + json.dumps(
            {
                "clear_candidate_hash": clear_candidate.candidate_hash,
                "clear_cad_request_hash": clear_cad_request.request_hash,
                "clear_cad_realization_hash": clear_evaluation.cad_realization_hash,
                "clear_m10_request_hash": clear_m10_request.request_hash,
                "clear_m10_result_hash": clear_proof.result_hash,
                "clear_evaluation_hash": clear_evaluation.evaluation_hash,
                "clear_metric_mm": clear_evaluation.metrics[0].value,
                "collision_candidate_hash": collision_candidate.candidate_hash,
                "collision_cad_realization_hash": collision_evaluation.cad_realization_hash,
                "collision_evaluation_hash": collision_evaluation.evaluation_hash,
                "collision_m10_result_hash": collision_proof.result_hash,
                "not_proven_candidate_hash": not_proven_candidate.candidate_hash,
                "not_proven_cad_realization_hash": not_proven_evaluation.cad_realization_hash,
                "not_proven_evaluation_hash": not_proven_evaluation.evaluation_hash,
                "not_proven_m10_result_hash": not_proven_proof.result_hash,
            },
            sort_keys=True,
        )
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available through deterministic discovery")
@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras are not installed")
def test_live_external_spur_preserves_unmodeled_internal_motion_boundary(tmp_path, monkeypatch):
    discovery = discover_freecad()
    monkeypatch.setenv(
        "MECHCAD_FREECADCMD",
        discovery.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE,
    )
    application = _build_gear_application(tmp_path)
    source_before = application.load_state()
    source_artifacts = {
        instance_id: _publish_source_step(
            application,
            part_id=f"candidate-spur-{instance_id}",
            size=(20.0 + index, 20.0, 5.0),
        )
        for index, instance_id in enumerate(
            (
                "drive-motor", "output-shaft", "bearing-a", "bearing-b", "output-hub",
                "support-mount-a", "support-mount-b",
            )
        )
    }
    source_artifacts["motor-mount"] = _publish_source_step(
        application,
        part_id="candidate-spur-motor-mount",
        size=(30.0, 30.0, 5.0),
    )
    source_artifacts["payload-body"] = _publish_source_step(
        application,
        part_id="candidate-spur-payload-body",
        size=(20.0, 20.0, 5.0),
    )
    gear_artifact = {
        "driver-gear": _publish_gear_step(application, teeth=20),
        "driven-gear": _publish_gear_step(application, teeth=100),
    }
    positions = {
        "drive-motor": (150.0, 150.0, 0.0),
        "driver-gear": (40.0, 0.0, 0.0),
        "driven-gear": (80.0, 0.0, 0.0),
        "output-shaft": (80.0, 0.0, 0.0),
        "bearing-a": (100.0, 30.0, 0.0),
        "bearing-b": (100.0, -30.0, 0.0),
        "output-hub": (80.0, 0.0, 0.0),
        "motor-mount": (0.0, 0.0, 0.0),
        "support-mount-a": (120.0, 30.0, 0.0),
        "support-mount-b": (120.0, -30.0, 0.0),
        "payload-body": (80.0, 0.0, 0.0),
    }
    candidate, synthesis_request, synthesis_policy, m12_result = _real_candidate(
        application,
        source_artifacts,
        positions,
        architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
        gear_artifact=gear_artifact,
    )
    evaluation, _, _, binding, m10_request = _evaluate_real_candidate(
        application,
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        external_spur=True,
    )
    assert m12_result.status.value == "admissible"
    assert (candidate.source_binding.source_revision, candidate.source_binding.source_state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    assert evaluation.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS
    assert binding.driver_gear_constituent_key == "driver-gear"
    assert {
        entry.physical_instance_id for entry in binding.constituent_dispositions
    } >= {
        "drive-motor", "driver-gear", "driven-gear", "output-shaft", "bearing-a",
        "bearing-b", "output-hub", "motor-mount", "support-mount-a", "support-mount-b",
        "payload-body",
    }
    driver = next(
        disposition
        for disposition in binding.constituent_dispositions
        if disposition.cad_instance_id == "cad-driver-gear"
    )
    assert driver.disposition is CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED
    gear_pair = next(
        item for item in m10_request.inventory.classifications
        if set(item.pair) == {"cad-driver-gear", "cad-driven-gear"}
    )
    assert gear_pair.classification is CandidateM10PairClassification.INTENDED_CONTACT_EXCLUDED
    assert gear_pair.reason == "declared gear mesh interface is outside M10 scope"
    driver_pairs = tuple(
        item for item in m10_request.inventory.classifications if "cad-driver-gear" in item.pair
    )
    assert driver_pairs
    assert all(item.requires_home_exact_check is False for item in driver_pairs)
    assert all("driver-gear" not in proof.pair for proof in evaluation.m10_stage_outcome.pair_proofs)
    assert all("driver-gear" not in check.pair for check in evaluation.m10_stage_outcome.home_exact_checks)
    for check in evaluation.m10_stage_outcome.home_exact_checks:
        assert check.request.sample_angles_deg == (0.0,)
        assert check.request_hash == check.request.request_hash
        assert check.result_hash == check.result.result_hash
        assert check.result.source_assembly_hash == check.request.source_assembly_hash
    assert all("gear" not in claim.lower() for claim in evaluation.hard_witnesses + evaluation.unresolved_findings)
    assert evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
    assert (evaluation.m10_stage_outcome.source_revision, evaluation.m10_stage_outcome.source_state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    source_after = application.load_state()
    assert (source_after.revision, source_after.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    print(
        "M12_4_SPUR_LIMITATION="
        + json.dumps(
            {
                "candidate_hash": candidate.candidate_hash,
                "m12_result_hash": m12_result.result_hash,
                "cad_realization_hash": evaluation.cad_realization_hash,
                "m10_request_hash": m10_request.request_hash,
                "driver_disposition": driver.disposition.value,
                "gear_pair_classification": gear_pair.classification.value,
                "continuous_proof_pairs": [proof.pair for proof in evaluation.m10_stage_outcome.pair_proofs],
            },
            sort_keys=True,
        )
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available through deterministic discovery")
def test_live_comparison_and_selection_are_deterministic_and_noncanonical(tmp_path, monkeypatch):
    discovery = discover_freecad()
    monkeypatch.setenv(
        "MECHCAD_FREECADCMD",
        discovery.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE,
    )
    application = _build_live_application(tmp_path)
    source_before = application.load_state()
    source_artifacts = {
        instance_id: _publish_source_step(
            application,
            part_id=f"candidate-comparison-{instance_id}",
            size=(20.0 + index, 20.0, 5.0),
        )
        for index, instance_id in enumerate(
            ("drive-motor", "output-shaft", "bearing-a", "bearing-b", "output-hub")
        )
    }
    source_artifacts["motor-mount"] = _publish_source_step(
        application,
        part_id="candidate-comparison-motor-mount",
        size=(30.0, 30.0, 5.0),
    )
    source_artifacts["payload-body"] = _publish_source_step(
        application,
        part_id="candidate-comparison-payload-body",
        size=(20.0, 20.0, 5.0),
    )
    positions_a = {
        "drive-motor": (100.0, 100.0, 0.0), "output-shaft": (60.0, 0.0, 0.0),
        "bearing-a": (90.0, 30.0, 0.0), "bearing-b": (90.0, -30.0, 0.0),
        "output-hub": (60.0, 0.0, 0.0), "motor-mount": (0.0, 0.0, 0.0),
        "payload-body": (60.0, 0.0, 0.0),
    }
    positions_b = dict(positions_a)
    positions_b["output-shaft"] = (80.0, 0.0, 0.0)
    positions_b["output-hub"] = (80.0, 0.0, 0.0)
    positions_b["payload-body"] = (80.0, 0.0, 0.0)
    candidate_a, request_a, policy_a, m12_a = _real_candidate(application, source_artifacts, positions_a, extra_design_variables=(CandidateDesignVariable(name="comparison-tag", value="a"),))
    evaluation_a, cad_request_a, scope_a, _, m10_request_a = _evaluate_real_candidate(application, candidate_a, request_a, policy_a, m12_a)
    candidate_b, request_b, policy_b, m12_b = _real_candidate(application, source_artifacts, positions_b, extra_design_variables=(CandidateDesignVariable(name="comparison-tag", value="b"),))
    evaluation_b, cad_request_b, scope_b, _, m10_request_b = _evaluate_real_candidate(application, candidate_b, request_b, policy_b, m12_b)
    candidate_c, request_c, policy_c, m12_c = _real_candidate(application, source_artifacts, positions_b, extra_design_variables=(CandidateDesignVariable(name="comparison-tag", value="c"),))
    evaluation_c, cad_request_c, scope_c, _, m10_request_c = _evaluate_real_candidate(application, candidate_c, request_c, policy_c, m12_c)
    assert candidate_a.candidate_hash != candidate_b.candidate_hash != candidate_c.candidate_hash
    assert cad_request_a.request_hash != cad_request_b.request_hash != cad_request_c.request_hash
    assert m10_request_a.request_hash != m10_request_b.request_hash != m10_request_c.request_hash
    assert application._candidate_source_binding_hash(candidate_a) == application._candidate_source_binding_hash(candidate_b) == application._candidate_source_binding_hash(candidate_c)
    assert all(
        (candidate.source_binding.source_revision, candidate.source_binding.source_state_hash)
        == (source_before.revision, source_before.state_hash)
        for candidate in (candidate_a, candidate_b, candidate_c)
    )
    assert evaluation_a.outcome is evaluation_b.outcome is evaluation_c.outcome is CandidateEvaluationOutcome.FEASIBLE
    assert scope_a.scope_hash == scope_b.scope_hash == scope_c.scope_hash
    assert evaluation_b.metrics[0].value > evaluation_a.metrics[0].value
    assert evaluation_b.metrics[0].value == evaluation_c.metrics[0].value
    for evaluation in (evaluation_a, evaluation_b, evaluation_c):
        assert evaluation.metrics[0].unit == "mm"
        if evaluation.schema_version == "candidate-evaluation@2":
            assert evaluation.metrics[0].source_result_hashes == tuple(
                proof.proof_hash
                for proof in evaluation.m10_stage_outcome.pair_proofs
            )
        else:
            assert evaluation.metrics[0].source_result_hashes == evaluation.m10_result_hashes
    comparison_policy = application.candidate_comparison_service.policy
    from mechcad_harness.candidates.comparison import CandidateComparisonRequestV2

    source_binding_hash = candidate_a.semantic_source_binding_hash
    ranking_synthesis_requests = {
        candidate_a.candidate_hash: request_a,
        candidate_b.candidate_hash: request_b,
    }
    tie_synthesis_requests = {
        candidate_b.candidate_hash: request_b,
        candidate_c.candidate_hash: request_c,
    }
    ranking_request = CandidateComparisonRequestV2(
        project_id=application.project_id,
        source_binding_hash=source_binding_hash,
        evaluation_scope_hash=scope_a.scope_hash,
        policy_hash=comparison_policy.policy_hash,
        candidate_evaluation_pairs=(
            (candidate_a.candidate_hash, evaluation_a.evaluation_hash),
            (candidate_b.candidate_hash, evaluation_b.evaluation_hash),
        ),
    )
    ranking = application.compare_candidates(
        ranking_request,
        ((candidate_a, evaluation_a), (candidate_b, evaluation_b)),
        synthesis_requests_by_candidate_hash=ranking_synthesis_requests,
    )
    repeated_ranking = application.compare_candidates(
        ranking_request,
        ((candidate_b, evaluation_b), (candidate_a, evaluation_a)),
        synthesis_requests_by_candidate_hash=ranking_synthesis_requests,
    )
    assert ranking.result_hash == repeated_ranking.result_hash
    assert ranking.ranked_candidate_hashes == (candidate_b.candidate_hash, candidate_a.candidate_hash)
    assert ranking.ties == ()

    tie_request = CandidateComparisonRequestV2(
        project_id=application.project_id,
        source_binding_hash=source_binding_hash,
        evaluation_scope_hash=scope_b.scope_hash,
        policy_hash=comparison_policy.policy_hash,
        candidate_evaluation_pairs=(
            (candidate_b.candidate_hash, evaluation_b.evaluation_hash),
            (candidate_c.candidate_hash, evaluation_c.evaluation_hash),
        ),
    )
    tie = application.compare_candidates(
        tie_request,
        ((candidate_b, evaluation_b), (candidate_c, evaluation_c)),
        synthesis_requests_by_candidate_hash=tie_synthesis_requests,
    )
    assert tie.ranked_candidate_hashes == (candidate_b.candidate_hash, candidate_c.candidate_hash)
    assert tie.ties == ((candidate_b.candidate_hash, candidate_c.candidate_hash),)

    state_before_selections = application.load_state()
    selected_top = application.select_candidate(
        candidate_b,
        evaluation_b,
        "fixture-selector",
        "selected highest certified clearance",
        comparison=ranking,
        comparison_entries=((candidate_a, evaluation_a), (candidate_b, evaluation_b)),
        synthesis_request=request_b,
        synthesis_requests_by_candidate_hash=ranking_synthesis_requests,
    )
    selected_without_comparison = application.select_candidate(
        candidate_a,
        evaluation_a,
        "fixture-selector",
        "selected directly without comparison",
        synthesis_request=request_a,
    )
    selected_non_top = application.select_candidate(
        candidate_a,
        evaluation_a,
        "fixture-selector",
        "explicitly selected non-top-ranked feasible candidate",
        comparison=ranking,
        comparison_entries=((candidate_a, evaluation_a), (candidate_b, evaluation_b)),
        synthesis_request=request_a,
        synthesis_requests_by_candidate_hash=ranking_synthesis_requests,
    )
    state_after_selections = application.load_state()
    assert selected_top.comparison_used is True
    assert selected_top.comparison_result_hash == ranking.result_hash
    assert selected_without_comparison.comparison_used is False
    assert selected_without_comparison.comparison_result_hash is None
    assert selected_non_top.candidate_hash == candidate_a.candidate_hash
    assert selected_non_top.comparison_result_hash == ranking.result_hash
    assert (state_after_selections.revision, state_after_selections.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    source_after = application.load_state()
    assert (source_after.revision, source_after.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    print(
        "M12_4_COMPARISON_SELECTION="
        + json.dumps(
            {
                "candidate_hashes": [candidate_a.candidate_hash, candidate_b.candidate_hash, candidate_c.candidate_hash],
                "evaluation_hashes": [evaluation_a.evaluation_hash, evaluation_b.evaluation_hash, evaluation_c.evaluation_hash],
                "scope_hash": scope_a.scope_hash,
                "ranking_request_hash": ranking_request.request_hash,
                "ranking_result_hash": ranking.result_hash,
                "ranking": list(ranking.ranked_candidate_hashes),
                "tie_result_hash": tie.result_hash,
                "tie_groups": [list(group) for group in tie.ties],
                "selection_hashes": [selected_top.selection_hash, selected_without_comparison.selection_hash, selected_non_top.selection_hash],
            },
            sort_keys=True,
        )
    )
