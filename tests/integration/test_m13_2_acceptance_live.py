from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import pytest

from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.cad_program import AxialBoreOperation, BasePlateOperation, CylindricalStockOperation
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateCadRealizationRequest,
    CandidateCadStageStatus,
    CandidateDesignVariable,
    CandidateEvaluationOutcome,
    CandidateGeometryFidelity,
    CandidateM10Binding,
    CandidateM10BodyDisposition,
    CandidateM10ConstituentDisposition,
    CandidateM10EvaluationRequest,
    CandidateM10EvaluationScope,
    CandidateM10PairClassification,
    CandidateM10PairScopeRequirement,
    CandidatePromotionRequest,
    CandidateSelection,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    PromotionApplicationStatus,
    PromotionValueClassification,
)
from mechcad_harness.candidates.models import (
    ComponentSpecificationSnapshot,
    GeometrySourceReference,
    JointPhysicalRealizationBinding,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
)
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.candidates.cad_realization import CandidatePlacementOrigin
from mechcad_harness.candidates.m10_evaluation import CandidateCollisionPairInventory
from mechcad_harness.candidates.promotion_models import CandidatePromotionPolicy, PromotionClassification
from mechcad_harness.generated_part_cad import compile_generated_part
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.models import (
    CylindricalHubSpecification,
    DesignState,
    GeneratedAuthorityInput,
    GeneratedAuthorityView,
    GeneratedPartFieldBinding,
    GeneratedPlacementDerivation,
    GeneratedPlacementRotationInput,
    SolidCircularShaftSpecification,
    compose_poses,
    generated_geometry_definition_identities,
    place_generated_target,
    pose_from_interface,
    placement_derivations_hash,
    selection_hash,
    value_hash,
)
from mechcad_harness.models.component_property import (
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
)
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.supplied_component_interface import (
    RotationalShaftInterface,
    SuppliedComponentReferenceFrame,
    SuppliedComponentInterfaceDefinition,
    SuppliedInterfaceEvidence,
    SuppliedInterfaceEvidenceOrigin,
    SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceTransformRole,
)
from mechcad_harness.multi_joint_kinematics import KinematicModel, RevoluteJointModel
from mechcad_harness.revolute_drive import (
    DriveAdmissibility,
    EngineeringCheck,
    EngineeringCheckStatus,
    RevoluteDriveAdmissibilityResult,
)
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.state.hashing import canonical_json



def _state() -> DesignState:
    return DesignState(
        id="DES-M13-2-T15",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )


def _interface_fact(fact_id, role, value):
    shape, unit = {
        SuppliedInterfaceTransformRole.POINT_MM: (
            SuppliedInterfaceEvidenceShape.VECTOR3,
            "mm",
        ),
        SuppliedInterfaceTransformRole.LENGTH_MM: (
            SuppliedInterfaceEvidenceShape.SCALAR,
            "mm",
        ),
        SuppliedInterfaceTransformRole.DIRECTION_UNIT: (
            SuppliedInterfaceEvidenceShape.VECTOR3,
            "1",
        ),
        SuppliedInterfaceTransformRole.ORIENTATION: (
            SuppliedInterfaceEvidenceShape.QUATERNION,
            "1",
        ),
    }[role]
    evidence = SuppliedInterfaceEvidence(
        evidence_id=f"evidence:{fact_id}",
        shape=shape,
        value=value,
        canonical_unit=unit,
        availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity="task-15:source-document",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    )
    from mechcad_harness.models.supplied_component_interface import SuppliedInterfaceFact

    return SuppliedInterfaceFact(
        fact_id=fact_id,
        expected_shape=shape,
        expected_unit=unit,
        transform_role=role,
        evidence=(evidence,),
        accepted_evidence_id=evidence.evidence_id,
    )


def _supplied_motor_spec(artifact):
    geometry = GeometryArtifactIdentity(
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_identity="vendor:motor",
        coordinate_system_id="motor-local-mm",
    )
    geometry_reference = GeometrySourceReference(
        artifact_id=geometry.artifact_id,
        artifact_hash=geometry.artifact_hash,
        source_identity=geometry.source_identity,
        coordinate_system_id="motor-local-mm",
    )
    interface = RotationalShaftInterface(
        interface_id="output-shaft",
        geometry_reference_hash=geometry_reference.reference_hash,
        geometry=geometry,
        axis_point=_interface_fact(
            "motor-axis-point",
            SuppliedInterfaceTransformRole.POINT_MM,
            (1.0, 2.0, 3.0),
        ),
        axis_direction=_interface_fact(
            "motor-axis-direction",
            SuppliedInterfaceTransformRole.DIRECTION_UNIT,
            (0.0, 0.0, 1.0),
        ),
        nominal_shaft_diameter=_interface_fact(
            "motor-shaft-diameter",
            SuppliedInterfaceTransformRole.LENGTH_MM,
            10.0,
        ),
        usable_axial_engagement_length=_interface_fact(
            "motor-engagement",
            SuppliedInterfaceTransformRole.LENGTH_MM,
            20.0,
        ),
    )
    definition = SuppliedComponentInterfaceDefinition(
        interface_id=interface.interface_id,
        geometry_reference_hash=geometry_reference.reference_hash,
        geometry=geometry,
        shaft=interface,
    )
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="vendor:motor",
        geometry_source=geometry_reference,
        interfaces=(interface.interface_id,),
        supplied_interface_definitions=(definition,),
    )


def _m12_result(candidate):
    source_binding_hash = "sha256:" + hashlib.sha256(
        canonical_json(candidate.source_binding.model_dump(mode="json"))
    ).hexdigest()
    return RevoluteDriveAdmissibilityResult(
        candidate_hash=candidate.candidate_hash,
        source_binding_hash=source_binding_hash,
        synthesis_request_hash=candidate.synthesis_request_hash,
        synthesis_policy_hash=candidate.synthesis_policy_hash,
        requirements_hash="sha256:" + "a" * 64,
        design_variables=candidate.design_variables,
        checks=(
            EngineeringCheck(
                check_id="required-drive",
                status=EngineeringCheckStatus.SATISFIED,
                reason="task 15 bounded fixture",
            ),
        ),
    )


PROJECT_ID = "P"
FREECAD_CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
FREECAD_AVAILABLE = bool(discover_freecad().available or os.path.isfile(FREECAD_CANDIDATE))


class _UninvokedAgent:
    identity = "m13-2-acceptance-uninvoked"

    def invoke(self, _request):
        raise AssertionError("M13-2 acceptance must not invoke an agent adapter")


def _application(tmp_path: Path) -> ProductionApplication:
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n"
        "  - path: /physical_mechanisms/*\n"
        "    owner: mechcad-physical-mechanism\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/physical_mechanisms/*"],
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
    StateManager(workspace).create_project(PROJECT_ID, _state())
    return ProductionApplication.create(
        workspace,
        PROJECT_ID,
        _UninvokedAgent(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def _publish_motor(application: ProductionApplication):
    source = application.load_state()
    from mechcad_harness.cad_program import CadPartProgram

    source_run_id = "R"

    program = CadPartProgram(
        part_id="m13-2-supplied-motor",
        operations=(
            BasePlateOperation(
                operation_id="motor-plate",
                length_mm=30.0,
                width_mm=30.0,
                thickness_mm=5.0,
            ),
        ),
    )
    result = FreeCADBackend().generate_program(
        program,
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id=source_run_id,
        revision=source.revision,
        state_hash=source.state_hash,
    )
    assert result.step.artifact_type is ArtifactType.STEP
    assert result.fcstd_verification.shape_valid is True
    assert result.step_verification.volume_mm3 == pytest.approx(4500.0, rel=1e-6)
    return result.step, source_run_id


def _assert_freecad_program(result, program, *, revision, state_hash):
    base = program.operations[0]
    assert isinstance(base, CylindricalStockOperation)
    expected_volume = math.pi * (base.diameter_mm / 2) ** 2 * base.length_mm
    expected_probes = {}
    for operation in program.operations[1:]:
        if isinstance(operation, AxialBoreOperation):
            expected_volume -= math.pi * (operation.diameter_mm / 2) ** 2 * operation.depth_mm
            expected_probes[f"bore_{operation.operation_id}"] = True
    for verification in (result.fcstd_verification, result.step_verification):
        assert verification.shape_valid is True
        assert verification.solid_count == 1
        assert verification.x_length_mm == pytest.approx(base.diameter_mm, abs=1e-6)
        assert verification.y_length_mm == pytest.approx(base.diameter_mm, abs=1e-6)
        assert verification.z_length_mm == pytest.approx(base.length_mm, abs=1e-6)
        assert verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6, abs=1e-6)
        assert verification.feature_probes == expected_probes
    backend = FreeCADBackend()
    for artifact in (result.fcstd, result.step):
        assert artifact.bound_revision == revision
        assert artifact.bound_state_hash == state_hash
        assert artifact.backend_provenance == backend.provenance()


def _motor_with_reference_frame(artifact):
    motor = _supplied_motor_spec(artifact)
    geometry = motor.geometry_source
    assert geometry is not None
    frame = SuppliedComponentReferenceFrame(
        frame_id="motor-output-frame",
        geometry_reference_hash=geometry.reference_hash,
        origin=_interface_fact(
            "motor-frame-origin",
            SuppliedInterfaceTransformRole.POINT_MM,
            (100.0, 100.0, 3.0),
        ),
        orientation=_interface_fact(
            "motor-frame-orientation",
            SuppliedInterfaceTransformRole.ORIENTATION,
            (1.0, 0.0, 0.0, 0.0),
        ),
    )
    definition = motor.supplied_interface_definitions[0]
    assert definition.shaft is not None
    shaft_payload = definition.shaft.model_dump(mode="python")
    shaft_payload.update(reference_frame_id=frame.frame_id, interface_hash="pending")
    shaft = type(definition.shaft).model_validate(shaft_payload)
    definition_payload = definition.model_dump(mode="python")
    definition_payload.update(shaft=shaft.model_dump(mode="python"), interface_hash="pending")
    definition = type(definition).model_validate(definition_payload)
    return ComponentSpecificationSnapshot.model_validate(
        motor.model_dump(mode="python")
        | {
            "supplied_reference_frames": (frame,),
            "supplied_interface_definitions": (definition,),
            "specification_hash": "pending",
        }
    )


def _selection(input_id: str, value: float, *, role: str = "dimension", name_form: str = "component_scoped"):
    return GeneratedAuthorityInput(
        input_id=input_id,
        role=role,
        source_kind="design_selection",
        locator={
            "name_form": name_form,
            "selection_key": input_id if name_form == "component_scoped" else "placement.axial_offset_mm",
            "selection_hash": selection_hash(
                name_form,
                input_id if name_form == "component_scoped" else "placement.axial_offset_mm",
                value,
            ),
        },
        value=value,
        value_hash=value_hash(value),
    )


def _direct(slot: str, input_id: str, value: float):
    return GeneratedPartFieldBinding(
        field_slot=slot,
        source={"input_id": input_id},
        field_value_hash=value_hash(value),
    )


def _m13_input(motor: ComponentSpecificationSnapshot):
    interface = motor.supplied_interface_definitions[0]
    fact = interface.shaft.nominal_shaft_diameter
    assert fact.accepted_evidence_id is not None
    return GeneratedAuthorityInput(
        input_id="supplied-shaft-diameter",
        role="supplied_diameter",
        source_kind="m13_1_interface_fact",
        locator={
            "interface_hash": interface.interface_hash,
            "fact_id": fact.fact_id,
            "accepted_evidence_id": fact.accepted_evidence_id,
            "value_hash": value_hash(10.0),
        },
        value=10.0,
        value_hash=value_hash(10.0),
    )


def _generated_specs(motor):
    shaft = SolidCircularShaftSpecification(
        generated_part_id="shaftdefinition",
        diameter_mm=12.5,
        length_mm=40.0,
        inputs=(_selection("selected-output-shaft-diameter", 12.5), _selection("shaft-length", 40.0)),
        field_bindings=(
            _direct("shaft.diameter_mm", "selected-output-shaft-diameter", 12.5),
            _direct("shaft.length_mm", "shaft-length", 40.0),
        ),
    )
    hub_inputs = (
        _selection("hub-outer-diameter", 30.0),
        _selection("hub-length", 50.0),
        _m13_input(motor),
        _selection("clearance", 0.5, role="clearance"),
        _selection("input-start", 0.0),
        _selection("input-depth", 20.0),
        _selection("output-start", 20.0),
        _selection("output-depth", 30.0),
        _selection("selected-output-shaft-diameter", 12.5),
    )
    hub = CylindricalHubSpecification(
        generated_part_id="hubdefinition",
        outer_diameter_mm=30.0,
        length_mm=50.0,
        bores=(
            {"bore_id": "input", "diameter_mm": 10.5, "start_z_mm": 0.0, "depth_mm": 20.0},
            {"bore_id": "output", "diameter_mm": 12.5, "start_z_mm": 20.0, "depth_mm": 30.0},
        ),
        inputs=hub_inputs,
        field_bindings=(
            _direct("hub.outer_diameter_mm", "hub-outer-diameter", 30.0),
            _direct("hub.length_mm", "hub-length", 50.0),
            GeneratedPartFieldBinding(
                field_slot="hub.bore:input.diameter_mm",
                source={
                    "rule_id": "hub-bore-from-supplied-shaft-with-clearance@1",
                    "input_ids": ("supplied-shaft-diameter", "clearance"),
                },
                field_value_hash=value_hash(10.5),
            ),
            _direct("hub.bore:input.start_z_mm", "input-start", 0.0),
            _direct("hub.bore:input.depth_mm", "input-depth", 20.0),
            _direct("hub.bore:output.diameter_mm", "selected-output-shaft-diameter", 12.5),
            _direct("hub.bore:output.start_z_mm", "output-start", 20.0),
            _direct("hub.bore:output.depth_mm", "output-depth", 30.0),
        ),
    )
    return (
        motor,
        ComponentSpecificationSnapshot(
            schema_version="component-specification@3",
            component_type="shaft",
            source_identity="generated:shaft-definition",
            generated_part=shaft,
            interfaces=shaft.active_interface_ids,
        ),
        ComponentSpecificationSnapshot(
            schema_version="component-specification@3",
            component_type="hub",
            source_identity="generated:hub-definition",
            generated_part=hub,
            interfaces=hub.active_interface_ids,
        ),
    )


def _candidate(state, specifications):
    motor, shaft, hub = specifications
    source = CandidateSourceBinding(
        project_id=PROJECT_ID,
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
    synthesis_request = CandidateSynthesisRequest(source_binding=source)
    synthesis_policy = CandidateSynthesisPolicy()
    components = (
        PhysicalComponentInstance(
            instance_id="motor-a",
            specification_hash=motor.specification_hash,
            role=PhysicalComponentRole.ACTUATOR,
            interfaces=motor.interfaces,
        ),
        PhysicalComponentInstance(
            instance_id="shaft-a",
            specification_hash=shaft.specification_hash,
            role=PhysicalComponentRole.SHAFT,
            interfaces=shaft.interfaces,
        ),
        PhysicalComponentInstance(
            instance_id="hub-a",
            specification_hash=hub.specification_hash,
            role=PhysicalComponentRole.HUB_OR_COUPLING,
            interfaces=hub.interfaces,
        ),
    )
    variables = (
        CandidateDesignVariable(name="motor-a.placement.x_mm", value=0.0),
        CandidateDesignVariable(name="motor-a.placement.y_mm", value=0.0),
        CandidateDesignVariable(name="motor-a.placement.z_mm", value=0.0),
        CandidateDesignVariable(name="selected-output-shaft-diameter", value=12.5),
        CandidateDesignVariable(name="shaft-length", value=40.0),
        CandidateDesignVariable(name="hub-outer-diameter", value=30.0),
        CandidateDesignVariable(name="hub-length", value=50.0),
        CandidateDesignVariable(name="clearance", value=0.5),
        CandidateDesignVariable(name="input-start", value=0.0),
        CandidateDesignVariable(name="input-depth", value=20.0),
        CandidateDesignVariable(name="output-start", value=20.0),
        CandidateDesignVariable(name="output-depth", value=30.0),
        CandidateDesignVariable(name="clocking", value=0.0),
        CandidateDesignVariable(name="hub-a.placement.axial_offset_mm", value=2.0),
    )
    realization = PhysicalMechanismRealization(
        components=components,
        joint_bindings=(
            JointPhysicalRealizationBinding(
                joint_id="output-joint",
                driven_instance_id="shaft-a",
                realization_component_ids=("motor-a", "shaft-a", "hub-a"),
                axis_frame_reference="joint:output-joint",
                load_path_metadata_available=False,
            ),
        ),
    )
    return (
        MechanicalDesignCandidate(
            source_binding=source,
            synthesis_request_hash=synthesis_request.request_hash,
            synthesis_policy_hash=synthesis_policy.policy_hash,
            component_specifications=specifications,
            realization=realization,
            design_variables=variables,
            generator_identity="m13-2-task-15-acceptance",
            generator_version="1",
        ),
        synthesis_request,
        synthesis_policy,
    )


def _placement_inputs(derivation):
    target_hash = (
        derivation.target_generated_interface_ref.interface_hash
        if derivation.target_generated_interface_ref is not None
        else derivation.target_generated_frame_ref.frame_hash
    )
    return (
        f"candidate:generated-placement:{derivation.derivation_id}",
        derivation.source_interface_ref.interface_hash,
        target_hash,
        *sorted(item.input_hash for item in derivation.inputs),
        *(() if derivation.rotation is None else (derivation.rotation.input_hash,)),
    )


def _cad_request(candidate, specifications, artifact):
    motor, shaft, hub = specifications
    shaft_part = compile_generated_part(
        shaft.generated_part,
        GeneratedAuthorityView(design_selections=tuple(candidate.design_variables)),
    )
    hub_part = compile_generated_part(
        hub.generated_part,
        GeneratedAuthorityView(
            design_selections=tuple(candidate.design_variables),
            interface_definitions=(motor.supplied_interface_definitions[0],),
            supplied_interfaces=(motor.supplied_interface_definitions[0],),
            reference_frames=motor.supplied_reference_frames,
        ),
    )
    assert shaft_part.program.part_id != hub_part.program.part_id
    assert shaft_part.program_hash != hub_part.program_hash
    source_placement = CadRigidTransform()
    frame = motor.supplied_reference_frames[0]
    shaft_frame = shaft.generated_part.reference_frame
    hub_interface = next(
        interface
        for interface in hub.generated_part.interfaces
        if interface.interface_id == "hubdefinition:bore:input:near"
    )
    rotation = GeneratedPlacementRotationInput(
        rotation_id="clocking",
        axis_ref={"frame_role": "target", "axis": "+z"},
        angle_degrees=0.0,
        provenance={
            "name_form": "component_scoped",
            "selection_key": "clocking",
            "selection_hash": selection_hash("component_scoped", "clocking", 0.0),
        },
        value_hash=value_hash(0.0),
    )
    first = GeneratedPlacementDerivation(
        derivation_id="place-shaft",
        rule_id="frame-generated-placement@1",
        source_physical_instance_id="motor-a",
        source_interface_ref={
            "interface_id": motor.supplied_interface_definitions[0].interface_id,
            "interface_hash": motor.supplied_interface_definitions[0].interface_hash,
        },
        source_frame_ref={"frame_id": frame.frame_id, "frame_hash": frame.frame_hash},
        source_placement_ref={"kind": "design_variable_placement"},
        target_physical_instance_id="shaft-a",
        target_generated_frame_ref={
            "frame_id": shaft_frame.frame_id,
            "frame_hash": shaft_frame.frame_hash,
        },
        rotation=rotation,
    )
    offset = _selection(
        "hub-a.placement.axial_offset_mm",
        2.0,
        role="axial_offset",
        name_form="instance_scoped",
    )
    second = GeneratedPlacementDerivation(
        derivation_id="place-hub",
        rule_id="coaxial-generated-placement@1",
        source_physical_instance_id="shaft-a",
        source_interface_ref={
            "interface_id": shaft.generated_part.interfaces[0].interface_id,
            "interface_hash": shaft.generated_part.interfaces[0].interface_hash,
        },
        source_placement_ref={"kind": "derivation", "derivation_id": "place-shaft"},
        target_physical_instance_id="hub-a",
        target_generated_interface_ref={
            "interface_id": hub_interface.interface_id,
            "interface_hash": hub_interface.interface_hash,
        },
        inputs=(offset,),
    )
    derivations = (first, second)
    shaft_transform = place_generated_target(
        "frame-generated-placement@1",
        compose_poses(source_placement, CadRigidTransform(x_mm=100.0, y_mm=100.0, z_mm=3.0)),
        pose_from_interface(shaft_frame),
        None,
        (1.0, 0.0, 0.0, 0.0),
    )
    hub_transform = place_generated_target(
        "coaxial-generated-placement@1",
        shaft_transform,
        pose_from_interface(hub_interface),
        2.0,
        None,
    )
    def mapping(instance_id, cad_id, fidelity, identity, definitions, placement, origin, source_geometry=None):
        return CandidateCadInstanceMapping(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id=instance_id,
            cad_instance_id=cad_id,
            fidelity=fidelity,
            representation_identity=identity,
            source_geometry_identity=source_geometry,
            geometry_definition_identities=definitions,
            placement=placement,
            placement_origin=origin,
        )

    motor_origin = CandidatePlacementOrigin(
        authority="candidate_design_variable",
        input_identities=tuple(
            f"candidate:design-variable:motor-a.placement.{axis}"
            for axis in ("x_mm", "y_mm", "z_mm")
        ),
        derivation="accepted-design-variable-placement@1",
        transform=source_placement,
    )
    imported = ImportedCadComponent(
        component_id="cad-motor-a",
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_revision=candidate.source_binding.source_revision,
        source_state_hash=candidate.source_binding.source_state_hash,
    )
    shaft_origin = CandidatePlacementOrigin(
        authority="deterministic_derived_relation",
        input_identities=_placement_inputs(first),
        derivation=first.rule_id,
        transform=shaft_transform,
    )
    hub_origin = CandidatePlacementOrigin(
        authority="deterministic_derived_relation",
        input_identities=_placement_inputs(second),
        derivation=second.rule_id,
        transform=hub_transform,
    )
    mappings = (
        mapping(
            "motor-a",
            "cad-motor-a",
            CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
            imported_component_hash(imported),
            (artifact.artifact_id,),
            source_placement,
            motor_origin,
            artifact.sha256,
        ),
        mapping(
            "shaft-a",
            "cad-shaft-a",
            CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY,
            shaft_part.program_hash,
            generated_geometry_definition_identities(shaft.generated_part),
            shaft_transform,
            shaft_origin,
        ),
        mapping(
            "hub-a",
            "cad-hub-a",
            CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY,
            hub_part.program_hash,
            generated_geometry_definition_identities(hub.generated_part),
            hub_transform,
            hub_origin,
        ),
    )
    return CandidateCadRealizationRequest(
        schema_version="candidate-cad-realization-request@2",
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="m13-2-task-15-candidate@1",
        compiler_identity="m13-2-task-15-candidate-compiler",
        compiler_version="1",
        candidate_instance_ids=("motor-a", "shaft-a", "hub-a"),
        mappings=mappings,
        placement_derivations=derivations,
        placement_derivations_hash=placement_derivations_hash(derivations),
        design_variable_identities=tuple(
            f"candidate:design-variable:motor-a.placement.{axis}"
            for axis in ("x_mm", "y_mm", "z_mm")
        ),
    )


def _m10_inputs(candidate, realization):
    dispositions = (
        CandidateM10ConstituentDisposition(
            physical_instance_id="motor-a",
            cad_instance_id="cad-motor-a",
            constituent_key="motor",
            disposition=CandidateM10BodyDisposition.FIXED,
        ),
        CandidateM10ConstituentDisposition(
            physical_instance_id="shaft-a",
            cad_instance_id="cad-shaft-a",
            constituent_key="shaft",
            disposition=CandidateM10BodyDisposition.OUTPUT_RIGID,
            output_transform_group="output-joint",
        ),
        CandidateM10ConstituentDisposition(
            physical_instance_id="hub-a",
            cad_instance_id="cad-hub-a",
            constituent_key="hub",
            disposition=CandidateM10BodyDisposition.OUTPUT_RIGID,
            output_transform_group="output-joint",
        ),
    )
    binding = CandidateM10Binding(
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        model=KinematicModel(
            model_id="m13-2-task-15-model",
            joints=(
                RevoluteJointModel(
                    joint_id="output-joint",
                    parent_instance_id="cad-motor-a",
                    child_instance_id="cad-shaft-a",
                    axis_origin_x_mm=100.0,
                    axis_origin_y_mm=100.0,
                    axis_origin_z_mm=3.0,
                    axis_direction_z=1.0,
                ),
            ),
        ),
        output_joint_id="output-joint",
        output_axis=RevoluteAxis(
            origin_x_mm=100.0,
            origin_y_mm=100.0,
            origin_z_mm=3.0,
            direction_x=0.0,
            direction_y=0.0,
            direction_z=1.0,
            frame_id="joint:output-joint",
        ),
        constituent_dispositions=dispositions,
    )
    scope = CandidateM10EvaluationScope(
        output_joint_semantic_key="primary-output-revolute",
        angle_interval_deg=(-10.0, 10.0),
        required_clearance_mm=1.0,
        pair_scope_requirements=(
            CandidateM10PairScopeRequirement(
                requirement_key="motor-shaft-clearance",
                first_constituent_key="motor",
                second_constituent_key="shaft",
                required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
            ),
        ),
        fidelity_requirements=(
            ("motor", CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY),
            ("shaft", CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY),
        ),
        proof_service_version="m10-single-axis-continuous-proof@1",
    )
    inventory = CandidateCollisionPairInventory.complete_for(realization, binding, scope)
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


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD is not available through deterministic discovery")
def test_live_m13_2_generic_generated_part_acceptance(tmp_path, monkeypatch):
    discovery = discover_freecad()
    monkeypatch.setenv(
        "MECHCAD_FREECADCMD",
        discovery.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE,
    )
    runtime = discover_freecad().require_available()
    application = _application(tmp_path)
    source = application.load_state()
    motor_artifact, source_run_id = _publish_motor(application)
    specifications = _generated_specs(_motor_with_reference_frame(motor_artifact))
    candidate, synthesis_request, synthesis_policy = _candidate(source.state, specifications)
    cad_request = _cad_request(candidate, specifications, motor_artifact)
    cad_stage = application.realize_candidate_cad(
        candidate, synthesis_request, synthesis_policy, cad_request
    )
    assert cad_stage.status is CandidateCadStageStatus.SUCCESS
    assert cad_stage.realization is not None
    candidate_assembly = cad_stage.realization.assembly
    assert tuple(item.derivation_id for item in cad_request.placement_derivations) == (
        "place-shaft",
        "place-hub",
    )
    assert candidate_assembly.instances[1].placement.x_mm == pytest.approx(100.0, abs=1e-6)
    assert candidate_assembly.instances[1].placement.z_mm == pytest.approx(3.0, abs=1e-6)
    assert candidate_assembly.instances[2].placement.z_mm == pytest.approx(5.0, abs=1e-6)

    backend = FreeCADBackend()
    for part in candidate_assembly.parts:
        first = backend.generate_program(
            part,
            application.state_manager.workspace,
            project_id=PROJECT_ID,
            run_id=source_run_id,
            revision=source.revision,
            state_hash=source.state_hash,
        )
        second = backend.generate_program(
            part,
            application.state_manager.workspace,
            project_id=PROJECT_ID,
            run_id=source_run_id,
            revision=source.revision,
            state_hash=source.state_hash,
        )
        assert first.fcstd.artifact_id == second.fcstd.artifact_id
        assert first.step.artifact_id == second.step.artifact_id
        assert first.fcstd_verification.shape_valid is True
        assert first.step_verification.shape_valid is True
        assert first.fcstd_verification.volume_mm3 == pytest.approx(
            first.step_verification.volume_mm3, rel=1e-6
        )
        if part.part_id.startswith("generated-part-"):
            _assert_freecad_program(
                first,
                part,
                revision=source.revision,
                state_hash=source.state_hash,
            )

    scope, binding, m10_request = _m10_inputs(candidate, cad_stage.realization)
    evaluation = application.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad_request,
        m10_request,
        scope,
        binding,
        evaluation_policy=None,
    )
    assert evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
    assert evaluation.m10_stage_outcome.status.value == "success"
    assert evaluation.m10_stage_outcome.pair_proofs[0].result.status.value == "verified_clear"
    assert evaluation.m10_stage_outcome.pair_proofs[0].result.exact_evaluations_count >= 1
    assert application.get_continuous_proof_evidence(
        evaluation.m10_stage_outcome.pair_proofs[0].result.result_hash
    ) is not None

    selection = application.select_candidate(
        candidate,
        evaluation,
        "m13-2-task-15-selector",
        "bounded generic generated-part acceptance selection",
    )
    promotion_request = CandidatePromotionRequest(
        project_id=PROJECT_ID,
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_3_result=_m12_result(candidate),
        evaluation=evaluation,
        selection=selection,
        promotion_policy=CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
        canonical_target_mechanism_id="PM-m13-2-task-15",
        classifications=(),
    )
    expected = application.candidate_promotion_compiler._expected_classifications(promotion_request)
    classifications = tuple(
        PromotionClassification(
            source_identity=identity,
            classification=(
                expected_value.required_classification
                or (
                    PromotionValueClassification.ACCEPTED_DESIGN_CHOICE
                    if identity.startswith("candidate:design-variable:")
                    else PromotionValueClassification.ACCEPTED_PHYSICAL_FACT
                )
            ),
            source_value=expected_value.source_value if expected_value.has_source_value else None,
        )
        for identity, expected_value in expected.items()
    )
    promotion_request = CandidatePromotionRequest.model_validate(
        promotion_request.model_dump(mode="python")
        | {"classifications": classifications, "request_hash": "pending"}
    )
    promotion = application.promote_selected_candidate(promotion_request)
    assert promotion.status is PromotionApplicationStatus.PROMOTION_APPLIED, promotion.error
    assert promotion.compilation is not None
    canonical = promotion.compilation.canonical_mechanism
    assert canonical.schema_version == "canonical-physical-mechanism@2"
    assert len(canonical.generated_placement_derivations) == 2
    assert {item.classification.value for item in promotion_request.classifications} >= {
        "accepted_physical_fact",
        "accepted_design_choice",
        "canonical_rederivation_input",
    }

    fresh = ProductionApplication.create(
        application.state_manager.workspace,
        PROJECT_ID,
        _UninvokedAgent(),
        ownership_path=tmp_path / "ownership.yaml",
        dependency_path=tmp_path / "dependencies.yaml",
    )
    promoted = fresh.load_state()
    reconstruction = fresh.reconstruct_promoted_mechanism(
        revision=promoted.revision,
        state_hash=promoted.state_hash,
        mechanism_id=canonical.id,
    )
    assert reconstruction.mechanism.mechanism_hash == canonical.mechanism_hash
    assert len(reconstruction.mechanism.generated_placement_derivations) == 2
    canonical_cad = fresh.canonical_cad_compiler.realize(reconstruction)
    for part in canonical_cad.assembly.parts:
        first = FreeCADBackend().generate_program(
            part,
            fresh.state_manager.workspace,
            project_id=PROJECT_ID,
            run_id=source_run_id,
            revision=reconstruction.revision,
            state_hash=reconstruction.state_hash,
        )
        second = FreeCADBackend().generate_program(
            part,
            fresh.state_manager.workspace,
            project_id=PROJECT_ID,
            run_id=source_run_id,
            revision=reconstruction.revision,
            state_hash=reconstruction.state_hash,
        )
        assert first.fcstd.artifact_id == second.fcstd.artifact_id
        assert first.step.artifact_id == second.step.artifact_id
        assert first.fcstd_verification.shape_valid is True
        assert first.step_verification.shape_valid is True
        if part.part_id.startswith("generated-part-"):
            _assert_freecad_program(
                first,
                part,
                revision=reconstruction.revision,
                state_hash=reconstruction.state_hash,
            )
    canonical_m10 = fresh.canonical_m10_service.execute(reconstruction, canonical_cad)
    assert canonical_m10.status.value == "verified_clear"
    verification = fresh.verify_promoted_mechanism(promotion)
    assert verification.status.value == "verified"
    assert verification.canonical_mechanism_hash == canonical.mechanism_hash
    assert fresh.load_state().revision == source.revision + 1
    assert fresh.state_manager.load_revision(PROJECT_ID, source.revision) == source.state
    assert motor_artifact.backend_provenance == FreeCADBackend().provenance()
    assert motor_artifact.sha256 == "sha256:" + hashlib.sha256(
        (application.state_manager.workspace / motor_artifact.relative_path).read_bytes()
    ).hexdigest()
    assert FreeCADBackend().provenance().library_version == "1.1.3"
