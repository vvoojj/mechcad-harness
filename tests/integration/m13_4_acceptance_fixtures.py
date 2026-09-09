from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication, ProductionStateBinding
from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.backends.freecad import FreeCADBackend
from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateCadRealizationRequest,
    CandidateGeometryFidelity,
    CandidateMultiJointPromotionRequest,
    CandidatePromotionCompiler,
    CandidatePromotionPolicy,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    MechanicalDesignCandidate,
    PhysicalAxisOwnerEndpoint,
    PhysicalJointMotionMode,
    PhysicalMechanismRealization,
    PhysicalRevoluteJointBinding,
    PhysicalRigidBodyBinding,
    JointPhysicalRealizationBinding,
    SuppliedRotationalInterfaceAxisSource,
    GeneratedRotationalInterfaceAxisSource,
    CandidateDesignVariable,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    ComponentSpecificationSnapshot,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    MechanicalConnection,
    MechanicalConnectionKind,
    ConnectionMeaning,
    PromotionClassification,
    PromotionValueClassification,
    physical_kinematic_root_hash,
)
from mechcad_harness.candidates.cad_realization import CandidateCadRealization, CandidatePlacementOrigin
from mechcad_harness.candidates.multi_joint_m10_evaluation import (
    CandidateMultiJointM10EvaluationRequest,
    CandidateMultiJointM10EvaluationScope,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.generated_part_cad import compile_generated_part
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.models import (
    Constraint,
    CylindricalHubSpecification,
    DesignState,
    GeneratedAuthorityInput,
    GeneratedAuthorityView,
    GeneratedPartFieldBinding,
    GeneratedPlacementDerivation,
    GeneratedPlacementRotationInput,
    GeneratedFrameRef,
    GeneratedInterfaceRef,
    RectangularFrameMemberSpecification,
    SolidCircularShaftSpecification,
    PhysicalPairClassification,
    PhysicalPairClassificationBinding,
    MultiJointVerificationConfigurationSet,
    Requirement,
    compose_poses,
    generated_geometry_definition_identities,
    placement_derivations_hash,
    place_generated_target,
    pose_from_interface,
    selection_hash,
    value_hash,
)
from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter
from mechcad_harness.engineering.keys import SupportedConstraintKey
from mechcad_harness.engineering.values import OutputInterfaceValue, PackagingEnvelopeValue
from mechcad_harness.models.component_property import (
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
)
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.supplied_component_interface import (
    MountingFaceInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedComponentReferenceFrame,
    SuppliedInterfaceEvidence,
    SuppliedInterfaceEvidenceOrigin,
    SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceFact,
    SuppliedInterfaceTransformRole,
    require_authoritatively_consumable_interface,
)
from mechcad_harness.multi_joint_kinematics import JointConfiguration
from mechcad_harness.revolute_drive import (
    DriveAdmissibility,
    EngineeringCheck,
    EngineeringCheckStatus,
    RevoluteDriveAdmissibilityResult,
)
from mechcad_harness.state import StateManager
from mechcad_harness.state.hashing import canonical_json

from mechcad_harness.candidates.models import GeometrySourceReference


PROJECT_ID = "PRJ-M13-4-T16"
SOURCE_RUN_ID = "INPUT"


@dataclass(frozen=True)
class M134Fixture:
    application: ProductionApplication
    source: ProductionStateBinding
    supplied_artifact: EngineeringArtifact
    specifications: tuple[ComponentSpecificationSnapshot, ...]
    candidate: MechanicalDesignCandidate
    synthesis_request: CandidateSynthesisRequest
    synthesis_policy: CandidateSynthesisPolicy
    cad_request: CandidateCadRealizationRequest
    m12_result: RevoluteDriveAdmissibilityResult


def _state() -> DesignState:
    return DesignState(
        id="DES-M13-4-T16",
        revision=1,
        requirements=[
            Requirement(
                id="REQ-M13-4-GENERATED-GEOMETRY",
                name="Representative generated geometry",
                description="The representative candidate is generated from persisted transmission authority.",
            ),
        ],
        constraints=[
            Constraint(
                id="CON-TRANSMISSION-OUTPUT-INTERFACE",
                name="Output interface",
                expression="The persisted output interface defines the shaft diameter used by generated parts.",
            ),
            Constraint(
                id="CON-TRANSMISSION-PACKAGING-ENVELOPE",
                name="Packaging envelope",
                expression="The persisted packaging envelope supplies generated length and diameter dimensions.",
            ),
        ],
        interfaces=[],
        authoritative_parameters=[
            AuthoritativeParameter(
                id="PARAM-M13-4-OUTPUT-INTERFACE",
                anchor=AuthoritativeAnchor(
                    kind="constraint", id="CON-TRANSMISSION-OUTPUT-INTERFACE"
                ),
                scope_id="transmission",
                key=SupportedConstraintKey.OUTPUT_INTERFACE,
                value=OutputInterfaceValue(
                    kind=SupportedConstraintKey.OUTPUT_INTERFACE.value,
                    interface_type="round-shaft",
                    shaft_diameter_mm=10.0,
                    torque_transfer_description="Representative generated shaft interface.",
                ),
                source_resolution_id="M13-4-SOURCE-RESOLUTION",
            ),
            AuthoritativeParameter(
                id="PARAM-M13-4-PACKAGING",
                anchor=AuthoritativeAnchor(
                    kind="constraint", id="CON-TRANSMISSION-PACKAGING-ENVELOPE"
                ),
                scope_id="transmission",
                key=SupportedConstraintKey.PACKAGING_ENVELOPE,
                value=PackagingEnvelopeValue(
                    kind=SupportedConstraintKey.PACKAGING_ENVELOPE.value,
                    max_length_mm=60.0,
                    max_width_mm=30.0,
                    max_height_mm=50.0,
                    mounting_description="Representative support plate and coaxial generated members.",
                ),
                source_resolution_id="M13-4-SOURCE-RESOLUTION",
            ),
        ],
    )


def _application_paths(config_root: Path) -> tuple[Path, Path]:
    config_root.mkdir(parents=True, exist_ok=True)
    ownership = config_root / "m134-ownership.yaml"
    dependencies = config_root / "m134-dependencies.json"
    ownership.write_text(
        "ownership:\n"
        "  - path: /physical_mechanisms/*\n"
        "    owner: mechcad-physical-mechanism\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        '{"rules":[{"when":["/physical_mechanisms/*"],'
        '"invalidates":["analysis.multi_joint_collision_sweep",'
        '"analysis.continuous_multi_joint_clearance_proof"]}],"edges":[]}\n',
        encoding="utf-8",
    )
    return ownership, dependencies


def _agent() -> FakeAgentAdapter:
    return FakeAgentAdapter(
        AgentIdentity(
            agent_name="m13-4-generic-fixture-agent",
            agent_version="1.0",
            role="m13-4-fixture",
            protocol_version="1.0",
        ),
        scripted_responses=(),
    )


def _source_geometry_values(state: DesignState) -> dict[str, float]:
    parameters = {parameter.key: parameter.value for parameter in state.authoritative_parameters}
    output_interface = parameters[SupportedConstraintKey.OUTPUT_INTERFACE]
    packaging = parameters[SupportedConstraintKey.PACKAGING_ENVELOPE]
    assert isinstance(output_interface, OutputInterfaceValue)
    assert isinstance(packaging, PackagingEnvelopeValue)
    assert output_interface.shaft_diameter_mm is not None
    return {
        "shaft_diameter": output_interface.shaft_diameter_mm,
        "shaft_length": packaging.max_height_mm,
        "hub_outer_diameter": packaging.max_width_mm,
        "hub_length": packaging.max_height_mm,
        "frame_length": packaging.max_length_mm,
        "frame_width": packaging.max_width_mm,
        "frame_height": output_interface.shaft_diameter_mm,
        "hub_input_start": 0.0,
        "hub_input_depth": packaging.max_height_mm / 2.0,
        "hub_output_start": packaging.max_height_mm / 2.0,
        "hub_output_depth": packaging.max_height_mm / 2.0,
    }


def _artifact_fact(
    artifact,
    geometry_reference_hash: str,
    fact_id: str,
    role: SuppliedInterfaceTransformRole,
    value,
) -> SuppliedInterfaceFact:
    shape, unit = {
        SuppliedInterfaceTransformRole.POINT_MM: (
            SuppliedInterfaceEvidenceShape.VECTOR3,
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
    normalized_value = tuple(float(item) for item in value)
    inferred = SuppliedInterfaceEvidence(
        evidence_id=f"geometry:{fact_id}",
        shape=shape,
        value=normalized_value,
        canonical_unit=unit,
        availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.MEASURED_LOCAL,
        source_identity=f"artifact:{artifact.sha256}",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        source_document_identity=artifact.artifact_id,
        geometry_reference_hash=geometry_reference_hash,
    )
    accepted = SuppliedInterfaceEvidence(
        evidence_id=f"accepted:{fact_id}",
        shape=shape,
        value=normalized_value,
        canonical_unit=unit,
        availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.USER_DECLARED,
        source_identity=f"artifact:{artifact.sha256}",
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        source_document_identity=artifact.artifact_id,
        geometry_reference_hash=geometry_reference_hash,
        basis_evidence_ids=(inferred.evidence_id,),
    )
    return SuppliedInterfaceFact(
        fact_id=fact_id,
        expected_shape=shape,
        expected_unit=unit,
        transform_role=role,
        evidence=(inferred, accepted),
        accepted_evidence_id=accepted.evidence_id,
    )


def _supplied_support_spec(artifact):
    geometry = GeometryArtifactIdentity(
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_identity="trusted:supplied-support-plate",
        coordinate_system_id="plate-local-mm",
    )
    reference = GeometrySourceReference(
        artifact_id=geometry.artifact_id,
        artifact_hash=geometry.artifact_hash,
        source_identity=geometry.source_identity,
        coordinate_system_id=geometry.coordinate_system_id,
    )
    geometry_hash = reference.reference_hash
    face = MountingFaceInterface(
        interface_id="mount-face",
        geometry_reference_hash=geometry_hash,
        geometry=geometry,
        face_reference_id="Face6",
        reference_frame_id="support-mount-frame",
        plane_point=_artifact_fact(
            artifact,
            geometry_hash,
            "support-mount-plane-point",
            SuppliedInterfaceTransformRole.POINT_MM,
            (0.0, 0.0, 5.0),
        ),
        outward_normal=_artifact_fact(
            artifact,
            geometry_hash,
            "support-mount-normal",
            SuppliedInterfaceTransformRole.DIRECTION_UNIT,
            (0.0, 0.0, 1.0),
        ),
    )
    frame = SuppliedComponentReferenceFrame(
        frame_id="support-mount-frame",
        geometry_reference_hash=geometry_hash,
        origin=_artifact_fact(
            artifact,
            geometry_hash,
            "support-frame-origin",
            SuppliedInterfaceTransformRole.POINT_MM,
            (0.0, 0.0, 5.0),
        ),
        orientation=_artifact_fact(
            artifact,
            geometry_hash,
            "support-frame-orientation",
            SuppliedInterfaceTransformRole.ORIENTATION,
            (1.0, 0.0, 0.0, 0.0),
        ),
    )
    definition = SuppliedComponentInterfaceDefinition(
        interface_id=face.interface_id,
        geometry_reference_hash=geometry_hash,
        geometry=geometry,
        mounting_face=face,
    )
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="support-plate",
        source_identity="trusted:supplied-support-plate",
        geometry_source=reference,
        interfaces=(face.interface_id,),
        supplied_reference_frames=(frame,),
        supplied_interface_definitions=(definition,),
    )


def build_m134_application(tmp_path: Path) -> ProductionApplication:
    """Return a production-composed application for the generic fixture project."""
    workspace = tmp_path / "workspace"
    ownership, dependencies = _application_paths(tmp_path)
    current = workspace / "projects" / PROJECT_ID / "current.json"
    if not current.exists():
        StateManager(workspace).create_project(PROJECT_ID, _state())
    return ProductionApplication.create(
        workspace,
        PROJECT_ID,
        _agent(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def build_m134_application_at(
    workspace: Path, config_root: Path, project_id: str, *, agent=None
) -> ProductionApplication:
    """Compose a fresh root over an existing persisted workspace."""
    ownership, dependencies = _application_paths(config_root)
    return ProductionApplication.create(
        workspace,
        project_id,
        _agent() if agent is None else agent,
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def _selection(
    input_id: str,
    value: float,
    *,
    role: str = "dimension",
    name_form: str = "component_scoped",
    selection_key: str | None = None,
) -> GeneratedAuthorityInput:
    key = selection_key or input_id
    if name_form == "instance_scoped":
        key = selection_key or "placement.axial_offset_mm"
    return GeneratedAuthorityInput(
        input_id=input_id,
        role=role,
        source_kind="design_selection",
        locator={
            "name_form": name_form,
            "selection_key": key,
            "selection_hash": selection_hash(name_form, key, value),
        },
        value=float(value),
        value_hash=value_hash(float(value)),
    )


def _direct(slot: str, input_id: str, value: float) -> GeneratedPartFieldBinding:
    return GeneratedPartFieldBinding(
        field_slot=slot,
        source={"input_id": input_id},
        field_value_hash=value_hash(float(value)),
    )


def _generated_specifications(state: DesignState, support):
    values = _source_geometry_values(state)
    shaft = SolidCircularShaftSpecification(
        generated_part_id="shaftdefinition",
        diameter_mm=values["shaft_diameter"],
        length_mm=values["shaft_length"],
        inputs=(
            _selection(
                "selected-output-shaft-diameter",
                values["shaft_diameter"],
                role="supplied_diameter",
            ),
            _selection("shaft-length", values["shaft_length"]),
        ),
        field_bindings=(
            _direct("shaft.diameter_mm", "selected-output-shaft-diameter", values["shaft_diameter"]),
            _direct("shaft.length_mm", "shaft-length", values["shaft_length"]),
        ),
    )
    hub_inputs = (
        _selection("hub-outer-diameter", values["hub_outer_diameter"]),
        _selection("hub-length", values["hub_length"]),
        _selection(
            "supplied-shaft-diameter",
            values["shaft_diameter"],
            role="supplied_diameter",
        ),
        _selection("input-start", values["hub_input_start"]),
        _selection("input-depth", values["hub_input_depth"]),
        _selection("output-start", values["hub_output_start"]),
        _selection("output-depth", values["hub_output_depth"]),
        _selection(
            "selected-output-shaft-diameter",
            values["shaft_diameter"],
            role="supplied_diameter",
        ),
    )
    hub = CylindricalHubSpecification(
        generated_part_id="hubdefinition",
        outer_diameter_mm=values["hub_outer_diameter"],
        length_mm=values["hub_length"],
        bores=(
            {
                "bore_id": "input",
                "diameter_mm": values["shaft_diameter"],
                "start_z_mm": values["hub_input_start"],
                "depth_mm": values["hub_input_depth"],
            },
            {
                "bore_id": "output",
                "diameter_mm": values["shaft_diameter"],
                "start_z_mm": values["hub_output_start"],
                "depth_mm": values["hub_output_depth"],
            },
        ),
        inputs=hub_inputs,
        field_bindings=(
            _direct("hub.outer_diameter_mm", "hub-outer-diameter", values["hub_outer_diameter"]),
            _direct("hub.length_mm", "hub-length", values["hub_length"]),
            GeneratedPartFieldBinding(
                field_slot="hub.bore:input.diameter_mm",
                source={
                    "rule_id": "hub-bore-from-supplied-shaft@1",
                    "input_ids": ("supplied-shaft-diameter",),
                },
                field_value_hash=value_hash(values["shaft_diameter"]),
            ),
            _direct("hub.bore:input.start_z_mm", "input-start", values["hub_input_start"]),
            _direct("hub.bore:input.depth_mm", "input-depth", values["hub_input_depth"]),
            _direct("hub.bore:output.diameter_mm", "selected-output-shaft-diameter", values["shaft_diameter"]),
            _direct("hub.bore:output.start_z_mm", "output-start", values["hub_output_start"]),
            _direct("hub.bore:output.depth_mm", "output-depth", values["hub_output_depth"]),
        ),
    )
    frame = RectangularFrameMemberSpecification(
        generated_part_id="framedefinition",
        length_mm=values["frame_length"],
        width_mm=values["frame_width"],
        height_mm=values["frame_height"],
        inputs=(
            _selection("frame-length", values["frame_length"]),
            _selection("frame-width", values["frame_width"]),
            _selection("frame-height", values["frame_height"]),
        ),
        field_bindings=(
            _direct("frame.length_mm", "frame-length", values["frame_length"]),
            _direct("frame.width_mm", "frame-width", values["frame_width"]),
            _direct("frame.height_mm", "frame-height", values["frame_height"]),
        ),
    )
    return (
        support,
        ComponentSpecificationSnapshot(
            schema_version="component-specification@3",
            component_type="generated-frame",
            source_identity="generated:frame-definition",
            generated_part=frame,
            interfaces=frame.active_interface_ids,
        ),
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


def _component(specification, instance_id: str, role: PhysicalComponentRole):
    return PhysicalComponentInstance(
        instance_id=instance_id,
        specification_hash=specification.specification_hash,
        role=role,
        interfaces=specification.interfaces,
    )


def _physical_realization(specifications) -> PhysicalMechanismRealization:
    support, frame, shaft, hub = specifications
    components = (
        _component(support, "motor-r", PhysicalComponentRole.MOUNT_OR_SUPPORT),
        _component(frame, "frame-r", PhysicalComponentRole.MOUNT_OR_SUPPORT),
        _component(shaft, "shaft-a", PhysicalComponentRole.SHAFT),
        _component(hub, "hub-a", PhysicalComponentRole.HUB_OR_COUPLING),
        _component(shaft, "shaft-b", PhysicalComponentRole.SHAFT),
        _component(hub, "hub-b", PhysicalComponentRole.HUB_OR_COUPLING),
    )
    shaft_interface = shaft.generated_part.interfaces[0].interface_id
    support_interface = support.supplied_interface_definitions[0].interface_id
    hub_output = next(
        item.interface_id
        for item in hub.generated_part.interfaces
        if item.interface_id == "hubdefinition:bore:output:far"
    )
    connections = (
        MechanicalConnection(
            connection_id="connection-j1",
            kind=MechanicalConnectionKind.ROTATIONAL_DRIVE,
            from_instance_id="motor-r",
            from_interface_id=support_interface,
            to_instance_id="shaft-a",
            to_interface_id=shaft_interface,
            meanings=(
                ConnectionMeaning.KINEMATIC_REALIZATION_INTENT,
                ConnectionMeaning.CAD_PLACEMENT_MATING_INTENT,
            ),
        ),
        MechanicalConnection(
            connection_id="connection-j2",
            kind=MechanicalConnectionKind.ROTATIONAL_DRIVE,
            from_instance_id="hub-a",
            from_interface_id=hub_output,
            to_instance_id="shaft-b",
            to_interface_id=shaft_interface,
            meanings=(
                ConnectionMeaning.KINEMATIC_REALIZATION_INTENT,
                ConnectionMeaning.CAD_PLACEMENT_MATING_INTENT,
            ),
        ),
    )
    hub_output_record = next(
        item for item in hub.generated_part.interfaces if item.interface_id == hub_output
    )
    joints = (
            PhysicalRevoluteJointBinding(
            physical_joint_id="J1",
            parent_physical_body_id="R",
            child_physical_body_id="A",
                connection_id="connection-j1",
                parent_physical_instance_id="motor-r",
                parent_interface_id=support_interface,
                child_physical_instance_id="shaft-a",
                child_interface_id=shaft_interface,
                axis_source=GeneratedRotationalInterfaceAxisSource(
                    source_physical_instance_id="shaft-a",
                    interface_id=shaft_interface,
                    interface_hash=shaft.generated_part.interfaces[0].interface_hash,
                    generated_specification_hash=shaft.specification_hash,
                ),
                axis_owner_endpoint=PhysicalAxisOwnerEndpoint.CHILD,
            axis_sign=1,
            motion_mode=PhysicalJointMotionMode.BOUNDED,
            min_angle_deg=-90.0,
            max_angle_deg=90.0,
            zero_reference_semantics="accepted-semantic-home@1",
        ),
        PhysicalRevoluteJointBinding(
            physical_joint_id="J2",
            parent_physical_body_id="A",
            child_physical_body_id="B",
            connection_id="connection-j2",
            parent_physical_instance_id="hub-a",
            parent_interface_id=hub_output,
            child_physical_instance_id="shaft-b",
            child_interface_id=shaft_interface,
            axis_source=GeneratedRotationalInterfaceAxisSource(
                source_physical_instance_id="hub-a",
                interface_id=hub_output,
                interface_hash=hub_output_record.interface_hash,
                generated_specification_hash=hub.specification_hash,
            ),
            axis_owner_endpoint=PhysicalAxisOwnerEndpoint.PARENT,
            axis_sign=1,
            motion_mode=PhysicalJointMotionMode.BOUNDED,
            min_angle_deg=-90.0,
            max_angle_deg=90.0,
            zero_reference_semantics="accepted-semantic-home@1",
        ),
    )
    body_bindings = (
        PhysicalRigidBodyBinding(
            physical_body_id="R",
            member_physical_instance_ids=("motor-r", "frame-r"),
            reference_physical_instance_id="motor-r",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="A",
            member_physical_instance_ids=("shaft-a", "hub-a"),
            reference_physical_instance_id="shaft-a",
        ),
        PhysicalRigidBodyBinding(
            physical_body_id="B",
            member_physical_instance_ids=("shaft-b", "hub-b"),
            reference_physical_instance_id="shaft-b",
        ),
    )
    realization_bindings = (
        JointPhysicalRealizationBinding(
            joint_id="J1",
            driven_instance_id="shaft-a",
            realization_component_ids=("motor-r", "shaft-a", "hub-a"),
            actuator_path_connection_ids=("connection-j1",),
            axis_frame_reference="shaft-a/" + shaft_interface,
            load_path_metadata_available=False,
        ),
        JointPhysicalRealizationBinding(
            joint_id="J2",
            driven_instance_id="shaft-b",
            realization_component_ids=("hub-a", "shaft-b", "hub-b"),
            transmission_path_connection_ids=("connection-j2",),
            hub_or_coupling_instance_id="hub-a",
            axis_frame_reference="hub-a/hubdefinition:bore:output:far",
            load_path_metadata_available=False,
        ),
    )
    excluded = {
        ("frame-r", "motor-r"): (
            PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED,
            "same explicit rigid body",
        ),
        ("hub-a", "shaft-a"): (
            PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED,
            "same explicit rigid body",
        ),
        ("hub-b", "shaft-b"): (
            PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED,
            "same explicit rigid body",
        ),
        ("hub-a", "shaft-b"): (
            PhysicalPairClassification.INTENDED_CONTACT_EXCLUDED,
            "explicit J2 connection",
        ),
    }
    ids = tuple(sorted(component.instance_id for component in components))
    pairs = tuple(
        PhysicalPairClassificationBinding(
            first_physical_instance_id=first,
            second_physical_instance_id=second,
            classification=excluded.get(
                (first, second), excluded.get((second, first), (PhysicalPairClassification.CHECK_CLEARANCE, None))
            )[0],
            exclusion_reason=excluded.get(
                (first, second), excluded.get((second, first), (PhysicalPairClassification.CHECK_CLEARANCE, None))
            )[1],
        )
        for index, first in enumerate(ids)
        for second in ids[index + 1 :]
    )
    return PhysicalMechanismRealization(
        schema_version="physical-mechanism-realization@2",
        components=components,
        connections=connections,
        joint_bindings=realization_bindings,
        physical_rigid_body_bindings=body_bindings,
        physical_revolute_joint_bindings=joints,
        kinematic_root_physical_body_id="R",
        kinematic_root_binding_hash=physical_kinematic_root_hash("R"),
        physical_pair_classification_bindings=pairs,
    )


def _candidate(source: ProductionStateBinding, specifications) -> tuple[MechanicalDesignCandidate, CandidateSynthesisRequest, CandidateSynthesisPolicy]:
    binding = CandidateSourceBinding(
        project_id=source.project_id,
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        consumed_authority=(
            CandidateSourceReference(
                path="/id",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
            CandidateSourceReference(
                path="/requirements",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
            CandidateSourceReference(
                path="/constraints",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_CONSTRAINT,
            ),
            CandidateSourceReference(
                path="/authoritative_parameters",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_PARAMETER,
            ),
            CandidateSourceReference(
                path="/physical_mechanisms",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_COMPONENT_FACT,
            ),
        ),
    ).bound_to(source.state)
    synthesis_request = CandidateSynthesisRequest(
        source_binding=binding,
        requested_joint_ids=("J1", "J2"),
        required_joint_ids=("J1", "J2"),
        requested_evaluation_categories=("multi-joint-collision-sweep",),
    )
    synthesis_policy = CandidateSynthesisPolicy()
    values = _source_geometry_values(source.state)
    variables = (
        CandidateDesignVariable(name="motor-r.placement.x_mm", value=0.0),
        CandidateDesignVariable(name="motor-r.placement.y_mm", value=0.0),
        CandidateDesignVariable(name="motor-r.placement.z_mm", value=0.0),
        CandidateDesignVariable(name="selected-output-shaft-diameter", value=values["shaft_diameter"]),
        CandidateDesignVariable(name="shaft-length", value=values["shaft_length"]),
        CandidateDesignVariable(name="hub-outer-diameter", value=values["hub_outer_diameter"]),
        CandidateDesignVariable(name="hub-length", value=values["hub_length"]),
        CandidateDesignVariable(name="supplied-shaft-diameter", value=values["shaft_diameter"]),
        CandidateDesignVariable(name="input-start", value=values["hub_input_start"]),
        CandidateDesignVariable(name="input-depth", value=values["hub_input_depth"]),
        CandidateDesignVariable(name="output-start", value=values["hub_output_start"]),
        CandidateDesignVariable(name="output-depth", value=values["hub_output_depth"]),
        CandidateDesignVariable(name="frame-length", value=values["frame_length"]),
        CandidateDesignVariable(name="frame-width", value=values["frame_width"]),
        CandidateDesignVariable(name="frame-height", value=values["frame_height"]),
        CandidateDesignVariable(name="frame-clock", value=0.0),
        CandidateDesignVariable(
            name="shaft-a.placement.axial_offset_mm",
            value=values["frame_height"],
        ),
    )
    realization = _physical_realization(specifications)
    candidate = MechanicalDesignCandidate(
        source_binding=binding,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        component_specifications=specifications,
        realization=realization,
        design_variables=variables,
        generator_identity="m13-4-generic-six-constituent-fixture",
        generator_version="1",
    )
    return candidate, synthesis_request, synthesis_policy


def _placement_derivations(candidate, specifications):
    support, frame, shaft, hub = specifications
    support_definition = support.supplied_interface_definitions[0]
    support_frame = support.supplied_reference_frames[0]
    shaft_interface = shaft.generated_part.interfaces[0]
    hub_input = next(item for item in hub.generated_part.interfaces if item.interface_id == "hubdefinition:bore:input:near")
    hub_output = next(item for item in hub.generated_part.interfaces if item.interface_id == "hubdefinition:bore:output:far")
    frame_ref = GeneratedFrameRef(
        frame_id=frame.generated_part.reference_frame.frame_id,
        frame_hash=frame.generated_part.reference_frame.frame_hash,
    )
    support_ref = GeneratedInterfaceRef(
        interface_id=support_definition.interface_id,
        interface_hash=support_definition.interface_hash,
    )
    shaft_ref = GeneratedInterfaceRef(interface_id=shaft_interface.interface_id, interface_hash=shaft_interface.interface_hash)
    hub_input_ref = GeneratedInterfaceRef(interface_id=hub_input.interface_id, interface_hash=hub_input.interface_hash)
    hub_output_ref = GeneratedInterfaceRef(interface_id=hub_output.interface_id, interface_hash=hub_output.interface_hash)
    clocking = GeneratedPlacementRotationInput(
        rotation_id="frame-clock",
        axis_ref={"frame_role": "target", "axis": "+z"},
        angle_degrees=0.0,
        provenance={
            "name_form": "component_scoped",
            "selection_key": "frame-clock",
            "selection_hash": selection_hash("component_scoped", "frame-clock", 0.0),
        },
        value_hash=value_hash(0.0),
    )
    shaft_a_offset = _selection(
        "shaft-a.placement.axial_offset_mm",
        frame.generated_part.height_mm,
        role="axial_offset",
        name_form="instance_scoped",
    )
    return (
        GeneratedPlacementDerivation(
            derivation_id="place-frame-r",
            rule_id="frame-generated-placement@1",
            source_physical_instance_id="motor-r",
            source_interface_ref=support_ref,
            source_frame_ref=GeneratedFrameRef(
                frame_id=support_frame.frame_id,
                frame_hash=support_frame.frame_hash,
            ),
            source_placement_ref={"kind": "design_variable_placement"},
            target_physical_instance_id="frame-r",
            target_generated_frame_ref=frame_ref,
            rotation=clocking,
        ),
        GeneratedPlacementDerivation(
            derivation_id="place-shaft-a",
            rule_id="coaxial-generated-placement@1",
            source_physical_instance_id="motor-r",
            source_interface_ref=support_ref,
            source_placement_ref={"kind": "design_variable_placement"},
            target_physical_instance_id="shaft-a",
            target_generated_interface_ref=shaft_ref,
            inputs=(shaft_a_offset,),
        ),
        GeneratedPlacementDerivation(
            derivation_id="place-hub-a",
            rule_id="coaxial-generated-placement@1",
            source_physical_instance_id="shaft-a",
            source_interface_ref=shaft_ref,
            source_placement_ref={"kind": "derivation", "derivation_id": "place-shaft-a"},
            target_physical_instance_id="hub-a",
            target_generated_interface_ref=hub_input_ref,
        ),
        GeneratedPlacementDerivation(
            derivation_id="place-shaft-b",
            rule_id="coaxial-generated-placement@1",
            source_physical_instance_id="hub-a",
            source_interface_ref=hub_output_ref,
            source_placement_ref={"kind": "derivation", "derivation_id": "place-hub-a"},
            target_physical_instance_id="shaft-b",
            target_generated_interface_ref=shaft_ref,
        ),
        GeneratedPlacementDerivation(
            derivation_id="place-hub-b",
            rule_id="coaxial-generated-placement@1",
            source_physical_instance_id="shaft-b",
            source_interface_ref=shaft_ref,
            source_placement_ref={"kind": "derivation", "derivation_id": "place-shaft-b"},
            target_physical_instance_id="hub-b",
            target_generated_interface_ref=hub_input_ref,
        ),
    )


def _placement_identity(derivation: GeneratedPlacementDerivation) -> tuple[str, ...]:
    target = (
        derivation.target_generated_interface_ref.interface_hash
        if derivation.target_generated_interface_ref is not None
        else derivation.target_generated_frame_ref.frame_hash
    )
    return (
        f"candidate:generated-placement:{derivation.derivation_id}",
        derivation.source_interface_ref.interface_hash,
        target,
        *(sorted(item.input_hash for item in derivation.inputs)),
        *((derivation.rotation.input_hash,) if derivation.rotation is not None else ()),
    )


def _derived_placements(specifications, derivations):
    support, frame, shaft, hub = specifications
    support_frame = support.supplied_reference_frames[0]
    shaft_interface = shaft.generated_part.interfaces[0]
    hub_input = next(item for item in hub.generated_part.interfaces if item.interface_id == "hubdefinition:bore:input:near")
    hub_output = next(item for item in hub.generated_part.interfaces if item.interface_id == "hubdefinition:bore:output:far")
    def accepted_value(fact):
        assert fact.accepted_evidence_id is not None
        evidence = next(
            item for item in fact.evidence if item.evidence_id == fact.accepted_evidence_id
        )
        assert evidence.value is not None
        return evidence.value

    source_frame_pose = CadRigidTransform(
        x_mm=accepted_value(support_frame.origin)[0],
        y_mm=accepted_value(support_frame.origin)[1],
        z_mm=accepted_value(support_frame.origin)[2],
        rotation_quaternion=accepted_value(support_frame.orientation),
    )
    frame_pose = place_generated_target(
        "frame-generated-placement@1",
        source_frame_pose,
        pose_from_interface(frame.generated_part.reference_frame),
        None,
        accepted_value(support_frame.orientation),
    )
    shaft_a_pose = place_generated_target(
        "coaxial-generated-placement@1",
        source_frame_pose,
        pose_from_interface(shaft_interface),
        frame.generated_part.height_mm,
        None,
    )
    hub_a_pose = place_generated_target(
        "coaxial-generated-placement@1",
        shaft_a_pose,
        pose_from_interface(hub_input),
        None,
        None,
    )
    shaft_b_pose = place_generated_target(
        "coaxial-generated-placement@1",
        compose_poses(hub_a_pose, pose_from_interface(hub_output)),
        pose_from_interface(shaft_interface),
        None,
        None,
    )
    hub_b_pose = place_generated_target(
        "coaxial-generated-placement@1",
        shaft_b_pose,
        pose_from_interface(hub_input),
        None,
        None,
    )
    return {
        "motor-r": CadRigidTransform(),
        "frame-r": frame_pose,
        "shaft-a": shaft_a_pose,
        "hub-a": hub_a_pose,
        "shaft-b": shaft_b_pose,
        "hub-b": hub_b_pose,
    }


def _cad_request(candidate, specifications, artifact, derivations) -> CandidateCadRealizationRequest:
    support, frame, shaft, hub = specifications
    view_by_hash = {
        specification.specification_hash: GeneratedAuthorityView(
            design_selections=tuple(candidate.design_variables),
            interface_definitions=specification.supplied_interface_definitions,
            supplied_interfaces=specification.supplied_interface_definitions,
            reference_frames=specification.supplied_reference_frames,
        )
        for specification in specifications
        if specification.generated_part is None
    }
    for specification in specifications:
        if specification.generated_part is not None:
            view_by_hash[specification.specification_hash] = GeneratedAuthorityView(
                design_selections=tuple(candidate.design_variables),
                interface_definitions=(),
                supplied_interfaces=(),
                reference_frames=(),
                generated_interfaces=tuple(specification.generated_part.interfaces),
            )
    compiled = {
        specification.specification_hash: compile_generated_part(
            specification.generated_part,
            view_by_hash[specification.specification_hash],
        )
        for specification in specifications
        if specification.generated_part is not None
    }
    placements = _derived_placements(specifications, derivations)
    imported = ImportedCadComponent(
        component_id="cad-motor-r",
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_revision=candidate.source_binding.source_revision,
        source_state_hash=candidate.source_binding.source_state_hash,
    )

    def mapping(instance_id, cad_id, specification, fidelity, identity, definitions, origin, source_identity=None):
        return CandidateCadInstanceMapping(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id=instance_id,
            cad_instance_id=cad_id,
            fidelity=fidelity,
            representation_identity=identity,
            source_geometry_identity=source_identity,
            geometry_definition_identities=definitions,
            placement=placements[instance_id],
            placement_origin=origin,
        )

    direct_origin = CandidatePlacementOrigin(
        authority="source_authority",
        input_identities=(
            artifact.artifact_id,
            artifact.sha256,
            "candidate:source-authority:trusted:supplied-support-plate",
            "candidate:design-variable:motor-r.placement.x_mm",
            "candidate:design-variable:motor-r.placement.y_mm",
            "candidate:design-variable:motor-r.placement.z_mm",
        ),
        derivation="source-coordinate-system-design-placement@1",
        transform=placements["motor-r"],
    )
    derived_origins = {
        item.target_physical_instance_id: CandidatePlacementOrigin(
            authority="deterministic_derived_relation",
            input_identities=_placement_identity(item),
            derivation=item.rule_id,
            transform=placements[item.target_physical_instance_id],
        )
        for item in derivations
    }
    mappings = (
            mapping(
                "motor-r",
                "cad-motor-r",
                support,
            CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
            imported_component_hash(imported),
            (artifact.artifact_id,),
            direct_origin,
            artifact.sha256,
        ),
        *(
            mapping(
                instance_id,
                f"cad-{instance_id}",
                specification,
                CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY,
                compiled[specification.specification_hash].program_hash,
                generated_geometry_definition_identities(specification.generated_part),
                derived_origins[instance_id],
            )
            for instance_id, specification in (
                ("frame-r", frame),
                ("shaft-a", shaft),
                ("hub-a", hub),
                ("shaft-b", shaft),
                ("hub-b", hub),
            )
        ),
    )
    return CandidateCadRealizationRequest(
        schema_version="candidate-cad-realization-request@2",
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-realization-generic@1",
        compiler_identity="m13-4-generic-candidate-cad",
        compiler_version="1",
        candidate_instance_ids=tuple(component.instance_id for component in candidate.realization.components),
        mappings=mappings,
        placement_derivations=derivations,
        placement_derivations_hash=placement_derivations_hash(derivations),
        design_variable_identities=tuple(
            f"candidate:design-variable:motor-r.placement.{axis}"
            for axis in ("x_mm", "y_mm", "z_mm")
        ),
    )


def _m12_result(candidate: MechanicalDesignCandidate) -> RevoluteDriveAdmissibilityResult:
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
                check_id="bounded-generic-drive",
                status=EngineeringCheckStatus.SATISFIED,
                reason="accepted generic fixture predecessor authority",
            ),
        ),
        status=DriveAdmissibility.ADMISSIBLE,
    )


def build_m134_configuration_set(model) -> MultiJointVerificationConfigurationSet:
    """Return the four explicit ordered configurations for the model."""
    return MultiJointVerificationConfigurationSet(
        configurations=(
            JointConfiguration(model_id=model.model_id, positions={"J1": 0.0, "J2": 0.0}),
            JointConfiguration(model_id=model.model_id, positions={"J1": 15.0, "J2": 0.0}),
            JointConfiguration(model_id=model.model_id, positions={"J1": 0.0, "J2": 15.0}),
            JointConfiguration(model_id=model.model_id, positions={"J1": 15.0, "J2": 45.0}),
        )
    )


def build_m134_multi_joint_request(
    fixture: M134Fixture,
    cad_realization: CandidateCadRealization,
    bridge,
) -> CandidateMultiJointM10EvaluationRequest:
    """Build the candidate M10 request only after live candidate CAD exists."""
    configuration_set = build_m134_configuration_set(bridge.model)
    scope = CandidateMultiJointM10EvaluationScope(
        configuration_set=configuration_set,
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
        scope_identity="candidate-scope:m13-4-representative",
    )
    return fixture.application.candidate_multi_joint_m10_evaluation_service.build_request(
        fixture.candidate,
        cad_realization,
        bridge,
        scope,
        cad_request=fixture.cad_request,
    )


def build_m134_pair_bindings(candidate: MechanicalDesignCandidate) -> tuple[PhysicalPairClassificationBinding, ...]:
    """Return the canonical complete fifteen-pair physical policy."""
    return candidate.realization.physical_pair_classification_bindings


def build_m134_promotion_request(
    fixture: M134Fixture,
    multi_joint_request: CandidateMultiJointM10EvaluationRequest,
    evaluation,
    selection,
) -> CandidateMultiJointPromotionRequest:
    request = CandidateMultiJointPromotionRequest(
        project_id=fixture.candidate.source_binding.project_id,
        source_revision=fixture.candidate.source_binding.source_revision,
        source_state_hash=fixture.candidate.source_binding.source_state_hash,
        candidate=fixture.candidate,
        synthesis_request=fixture.synthesis_request,
        synthesis_policy=fixture.synthesis_policy,
        m12_3_result=fixture.m12_result,
        multi_joint_request=multi_joint_request,
        multi_joint_evaluation=evaluation,
        multi_joint_selection=selection,
        generated_placement_derivations=fixture.cad_request.placement_derivations,
        placement_derivations_hash=fixture.cad_request.placement_derivations_hash,
        promotion_policy=CandidatePromotionPolicy(
            mapping_schema_version="candidate-canonical-mapping@2"
        ),
        canonical_target_mechanism_id="PM-M13-4-T16",
        classifications=(),
    )
    expected = CandidatePromotionCompiler._expected_multi_joint_classifications(request)
    classifications = tuple(
        sorted(
            (
                PromotionClassification(
                    source_identity=identity,
                    classification=(
                        item.required_classification
                        or (
                            PromotionValueClassification.ACCEPTED_DESIGN_CHOICE
                            if identity.startswith("candidate:design-variable:")
                            else PromotionValueClassification.ACCEPTED_PHYSICAL_FACT
                        )
                    ),
                    source_value=item.source_value if item.has_source_value else None,
                )
                for identity, item in expected.items()
            ),
            key=lambda item: item.source_identity,
        )
    )
    return CandidateMultiJointPromotionRequest.model_validate(
        request.model_copy(
            update={"classifications": classifications, "request_hash": "pending"}
        ).model_dump(mode="json")
    )


def build_m134_fixture(tmp_path: Path) -> M134Fixture:
    """Return the fully validated source-bound candidate fixture."""
    application = build_m134_application(tmp_path)
    source = application.load_state()
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
    generated = FreeCADBackend().generate_program(
        program,
        application.state_manager.workspace,
        project_id=source.project_id,
        run_id=SOURCE_RUN_ID,
        revision=source.revision,
        state_hash=source.state_hash,
    )
    artifact = generated.step
    store = ArtifactStore(
        application.state_manager.workspace,
        project_id=source.project_id,
        run_id=SOURCE_RUN_ID,
    )
    verified, content = store.read_verified_strict(
        artifact.artifact_id,
        expected_type=ArtifactType.STEP,
        expected_hash=artifact.sha256,
    )
    assert verified == artifact
    assert "sha256:" + hashlib.sha256(content).hexdigest() == artifact.sha256
    assert generated.step_verification.shape_valid is True
    assert generated.step_verification.solid_count == 1
    assert generated.step_verification.x_length_mm == 30.0
    assert generated.step_verification.y_length_mm == 30.0
    assert generated.step_verification.z_length_mm == 5.0
    support = _supplied_support_spec(artifact)
    definition = support.supplied_interface_definitions[0]
    frame = support.supplied_reference_frames[0]
    require_authoritatively_consumable_interface(definition, frame)
    specifications = _generated_specifications(source.state, support)
    candidate, synthesis_request, synthesis_policy = _candidate(source, specifications)
    derivations = _placement_derivations(candidate, specifications)
    cad_request = _cad_request(candidate, specifications, artifact, derivations)
    return M134Fixture(
        application=application,
        source=source,
        supplied_artifact=artifact,
        specifications=specifications,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        cad_request=cad_request,
        m12_result=_m12_result(candidate),
    )


__all__ = [
    "M134Fixture",
    "PROJECT_ID",
    "SOURCE_RUN_ID",
    "build_m134_application",
    "build_m134_application_at",
    "build_m134_configuration_set",
    "build_m134_fixture",
    "build_m134_multi_joint_request",
    "build_m134_pair_bindings",
    "build_m134_promotion_request",
]
