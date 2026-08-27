from __future__ import annotations

import hashlib
import math

from mechcad_harness.candidates.models import (
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    ComponentSpecificationSnapshot,
    ConnectionMeaning,
    JointPhysicalRealizationBinding,
    MechanicalConnection,
    MechanicalConnectionKind,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
    PolicyEntrySemantics,
)
from mechcad_harness.revolute_drive.calculations import (
    _numeric_property,
    calculate_shaft_static_sizing,
    evaluate_motor_checks,
    evaluate_spur_pair,
)
from mechcad_harness.revolute_drive.models import (
    ConsumedPropertyBinding,
    DriveAdmissibility,
    DriveArchitecture,
    EngineeringCheck,
    EngineeringCheckStatus,
    InputProvenanceKind,
    RevoluteDriveAdmissibilityResult,
    RevoluteDriveConstructionOutcome,
    RevoluteDriveEngineeringRequirements,
    RevoluteDriveTemplateInput,
)
from mechcad_harness.state.hashing import canonical_json


GENERATOR_IDENTITY = "revolute-drive-realization-service"
GENERATOR_VERSION = "1"

_MOTOR_INTERFACE_REQUIREMENTS = ("output-shaft", "mount-face")
_SHAFT_INTERFACE_REQUIREMENTS = ("motor-side", "hub-side", "journal-a", "journal-b")
_BEARING_INTERFACE_REQUIREMENTS = ("housing",)
_HUB_INTERFACE_REQUIREMENTS = ("shaft", "body")
_MOUNT_INTERFACE_REQUIREMENTS = ("motor",)
_SUPPORT_MOUNT_INTERFACE_REQUIREMENTS = ("bearing",)
_BODY_INTERFACE_REQUIREMENTS = ("hub",)
_GEAR_INTERFACE_REQUIREMENTS = ("bore", "mesh")


class _Slot:
    __slots__ = ("label", "instance_id", "specification", "required_interfaces", "required_component_types")

    def __init__(
        self,
        label: str,
        instance_id: str | None,
        specification: ComponentSpecificationSnapshot | None,
        required_interfaces: tuple[str, ...],
        required_component_types: tuple[str, ...],
    ) -> None:
        self.label = label
        self.instance_id = instance_id
        self.specification = specification
        self.required_interfaces = required_interfaces
        self.required_component_types = required_component_types


def _slot_problems(slots) -> list[str]:
    problems: list[str] = []
    for slot in slots:
        if slot.instance_id is None and slot.specification is None:
            problems.append(f"{slot.label} instance ID and specification are missing")
        elif slot.instance_id is None:
            problems.append(f"{slot.label} instance ID is missing")
        elif slot.specification is None:
            problems.append(f"{slot.label} specification is missing")
        else:
            if slot.specification.component_type not in slot.required_component_types:
                expected = ", ".join(repr(value) for value in slot.required_component_types)
                problems.append(
                    f"{slot.label} specification has component type {slot.specification.component_type!r}; "
                    f"expected {expected}"
                )
            declared = set(slot.specification.interfaces)
            for interface in slot.required_interfaces:
                if interface not in declared:
                    problems.append(
                        f"{slot.label} specification does not declare the required interface '{interface}'"
                    )
    return problems


def _policy_allows(policy_entries, architecture: DriveArchitecture, design_variables=()) -> bool:
    architecture_allowed = any(
        semantics is PolicyEntrySemantics.HARD_ADMISSIBILITY and value == architecture.value
        for _, value, semantics in policy_entries
    )
    if not architecture_allowed:
        return False
    return all(
        any(
            key == f"allow-design-variable:{variable.name}"
            and value == canonical_json({"value": variable.value}).decode("utf-8")
            and semantics is PolicyEntrySemantics.HARD_ADMISSIBILITY
            for key, value, semantics in policy_entries
        )
        for variable in design_variables
    )


def _resolve_source_path(payload, path: str):
    value = payload
    for segment in path[1:].split("/"):
        if isinstance(value, dict) and segment in value:
            value = value[segment]
        elif isinstance(value, list) and segment.isdecimal() and int(segment) < len(value):
            value = value[int(segment)]
        else:
            raise ValueError(f"canonical source path is missing: {path}")
    return value


def _hash_source_binding(source_binding) -> str:
    payload = source_binding.model_dump(mode="json")
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _revalidate_synthesis_inputs(request, policy):
    return (
        CandidateSynthesisRequest.model_validate(request.model_dump(mode="json")),
        CandidateSynthesisPolicy.model_validate(policy.model_dump(mode="json")),
    )


def _revalidate_requirements(requirements):
    return RevoluteDriveEngineeringRequirements.model_validate(
        requirements.model_dump(mode="json")
    )


def _requirement_scalars(requirements: RevoluteDriveEngineeringRequirements):
    load_case = requirements.design_load_case
    scalars: list[tuple[str, object]] = [
        ("/requirements/required_output_speed", requirements.required_output_speed),
        ("/requirements/design_load_case/design_torque", load_case.design_torque),
    ]
    if load_case.transverse_force_y is not None:
        scalars.append(("/requirements/design_load_case/transverse_force_y", load_case.transverse_force_y))
    if load_case.transverse_force_z is not None:
        scalars.append(("/requirements/design_load_case/transverse_force_z", load_case.transverse_force_z))
    if requirements.required_voltage is not None:
        scalars.append(("/requirements/required_voltage", requirements.required_voltage))
    if requirements.required_peak_torque is not None:
        scalars.append(("/requirements/required_peak_torque", requirements.required_peak_torque))
    if requirements.efficiency is not None:
        scalars.append(("/requirements/efficiency", requirements.efficiency))
    if requirements.safety_factor is not None:
        scalars.append(("/requirements/safety_factor", requirements.safety_factor))
    if requirements.shaft_yield_strength is not None:
        scalars.append(("/requirements/shaft_yield_strength", requirements.shaft_yield_strength))
    geometry = requirements.shaft_support_geometry
    if geometry is not None:
        scalars.extend(
            (
                ("/requirements/shaft_support_geometry/support_a_x", geometry.support_a_x),
                ("/requirements/shaft_support_geometry/support_b_x", geometry.support_b_x),
                ("/requirements/shaft_support_geometry/load_plane_x", geometry.load_plane_x),
            )
        )
    return scalars


def _source_scalar_binding_defects(requirements, request, source_state=None) -> list[str]:
    references = {
        reference.path: reference
        for reference in request.source_binding.consumed_authority
    }
    defects: list[str] = []
    trusted_bindings = {
        binding.source_path: binding
        for binding in requirements.trusted_source_scalar_bindings
    }
    source_payload = None
    if source_state is not None:
        source_payload = (
            source_state.model_dump(mode="json")
            if hasattr(source_state, "model_dump")
            else source_state
        )
    for semantic_path, scalar_value in _requirement_scalars(requirements):
        if scalar_value.provenance is InputProvenanceKind.SOURCE_AUTHORITY:
            declared = scalar_value.source_path
            reference = references.get(declared)
            if reference is None:
                defects.append(
                    f"declared source-authoritative path is not consumed by the request source binding: "
                    f"{declared} ({semantic_path})"
                )
            trusted = trusted_bindings.get(declared)
            if trusted is None:
                defects.append(
                    f"source authority trusted scalar source-binding is missing: {declared} ({semantic_path}); "
                    "the composite canonical source record cannot prove the numeric value"
                )
            else:
                if scalar_value.source_value_hash != "sha256:" + hashlib.sha256(
                    canonical_json({"value": scalar_value.value, "unit": scalar_value.unit})
                ).hexdigest():
                    defects.append(
                        f"source authority scalar self-hash mismatch: {declared} ({semantic_path})"
                    )
                if reference is not None and trusted.source_record_hash != reference.value_hash:
                    defects.append(
                        f"source authority trusted scalar source record mismatch: {declared} ({semantic_path})"
                    )
                if (
                    trusted.value != scalar_value.value
                    or trusted.unit != scalar_value.unit
                    or trusted.source_value_hash != scalar_value.source_value_hash
                ):
                    defects.append(
                        f"source authority trusted scalar value mismatch: {declared} ({semantic_path})"
                    )
                if source_payload is None:
                    defects.append(
                        f"canonical source state is unavailable for source-authoritative path: "
                        f"{declared} ({semantic_path})"
                    )
                else:
                    try:
                        record = _resolve_source_path(source_payload, declared)
                    except ValueError as exc:
                        defects.append(str(exc))
                    else:
                        if (
                            not isinstance(record, dict)
                            or set(record) != {"value", "unit"}
                            or isinstance(record.get("value"), bool)
                            or not isinstance(record.get("value"), (int, float))
                            or not math.isfinite(float(record.get("value")))
                            or not isinstance(record.get("unit"), str)
                        ):
                            defects.append(
                                f"source authority path does not resolve to an explicit scalar record: "
                                f"{declared} ({semantic_path})"
                            )
                        else:
                            actual_record_hash = "sha256:" + hashlib.sha256(
                                canonical_json(record)
                            ).hexdigest()
                            if reference is not None and reference.value_hash != actual_record_hash:
                                defects.append(
                                    f"source authority consumed source record hash mismatch: "
                                    f"{declared} ({semantic_path})"
                                )
                            if trusted.source_record_hash != actual_record_hash:
                                defects.append(
                                    f"source authority trusted scalar source record mismatch: "
                                    f"{declared} ({semantic_path})"
                                )
                            if (
                                record["value"] != scalar_value.value
                                or record["unit"] != scalar_value.unit
                            ):
                                defects.append(
                                    f"source authority canonical scalar value mismatch: "
                                    f"{declared} ({semantic_path})"
                                )
    return defects


class RevoluteDriveRealizationService:
    """Pure deterministic construction and bounded evaluation of the two M12-3
    revolute-drive templates. The service holds no StateManager, artifact or
    evidence stores, CAD runtime, or provider dependencies; candidate integrity
    and currentness remain caller obligations."""

    def construct_candidate(
        self,
        request,
        policy,
        template_input: RevoluteDriveTemplateInput,
    ) -> RevoluteDriveConstructionOutcome:
        request, policy = _revalidate_synthesis_inputs(request, policy)
        problems: list[str] = []
        if len(request.required_joint_ids) != 1:
            problems.append("M12-3 realization requires exactly one required joint")
        elif template_input.joint_id != request.required_joint_ids[0]:
            problems.append(
                f"template joint '{template_input.joint_id}' does not match the required joint "
                f"'{request.required_joint_ids[0]}'"
            )
        if template_input.axis_frame_reference is None:
            problems.append("template requires an explicit nonempty axis/frame reference")
        if not _policy_allows(
            policy.entries,
            template_input.architecture,
            template_input.design_variables,
        ):
            problems.append(
                "synthesis policy does not explicitly admit the requested architecture "
                "and every candidate design variable with exact hard-admissibility values"
            )

        base_slots: list[_Slot] = [
            _Slot("motor", template_input.motor_instance_id, template_input.motor_specification, _MOTOR_INTERFACE_REQUIREMENTS, ("motor",)),
            _Slot("output shaft", template_input.shaft_instance_id, template_input.shaft_specification, _SHAFT_INTERFACE_REQUIREMENTS, ("shaft",)),
            _Slot("bearing A", template_input.bearing_a_instance_id, template_input.bearing_a_specification, _BEARING_INTERFACE_REQUIREMENTS, ("bearing",)),
            _Slot("bearing B", template_input.bearing_b_instance_id, template_input.bearing_b_specification, _BEARING_INTERFACE_REQUIREMENTS, ("bearing",)),
            _Slot("hub", template_input.hub_instance_id, template_input.hub_specification, _HUB_INTERFACE_REQUIREMENTS, ("hub",)),
            _Slot("motor mount", template_input.mount_instance_id, template_input.mount_specification, _MOUNT_INTERFACE_REQUIREMENTS, ("mount", "support", "support-mount")),
            _Slot("driven body", template_input.driven_body_instance_id, template_input.driven_body_specification, _BODY_INTERFACE_REQUIREMENTS, ("driven-body",)),
        ]
        gear_slots: list[_Slot] = []
        support_mount_slots: list[_Slot] = []
        support_mount_ids = template_input.support_mount_instance_ids
        support_mount_specs = template_input.support_mount_specifications
        if template_input.architecture is DriveArchitecture.EXTERNAL_SPUR_REDUCTION:
            gear_slots.extend(
                (
                    _Slot("driver gear", template_input.driver_gear_instance_id, template_input.driver_gear_specification, _GEAR_INTERFACE_REQUIREMENTS, ("gear",)),
                    _Slot("driven gear", template_input.driven_gear_instance_id, template_input.driven_gear_specification, _GEAR_INTERFACE_REQUIREMENTS, ("gear",)),
                )
            )
            if len(support_mount_ids) == 2 and len(support_mount_specs) == 2:
                for index in range(2):
                    support_mount_slots.append(
                        _Slot(
                            f"support mount {chr(ord('a') + index)}",
                            support_mount_ids[index],
                            support_mount_specs[index],
                            _SUPPORT_MOUNT_INTERFACE_REQUIREMENTS,
                            ("mount", "support", "support-mount"),
                        )
                    )
            else:
                problems.append(
                    "external spur reduction requires exactly two shaft-support mounts with matching specifications"
                )

        problems.extend(_slot_problems(base_slots + gear_slots + support_mount_slots))

        if problems:
            return RevoluteDriveConstructionOutcome(status=DriveAdmissibility.UNRESOLVED, reason="; ".join(problems))

        motor_slot, shaft_slot, bearing_a_slot, bearing_b_slot, hub_slot, mount_slot, body_slot = base_slots
        driver_gear_slot = gear_slots[0] if gear_slots else None
        driven_gear_slot = gear_slots[1] if len(gear_slots) > 1 else None

        ordered_specs: list[ComponentSpecificationSnapshot] = []
        registered_hashes: set[str] = set()

        def _register(specification: ComponentSpecificationSnapshot) -> str:
            specification_hash = specification.specification_hash
            if specification_hash not in registered_hashes:
                registered_hashes.add(specification_hash)
                ordered_specs.append(specification)
            return specification_hash

        def _instance(slot: _Slot, role: PhysicalComponentRole) -> PhysicalComponentInstance:
            return PhysicalComponentInstance(
                instance_id=slot.instance_id,
                specification_hash=_register(slot.specification),
                role=role,
                interfaces=slot.specification.interfaces,
            )

        label_roles = {
            motor_slot: PhysicalComponentRole.ACTUATOR,
            shaft_slot: PhysicalComponentRole.SHAFT,
            bearing_a_slot: PhysicalComponentRole.BEARING,
            bearing_b_slot: PhysicalComponentRole.BEARING,
            hub_slot: PhysicalComponentRole.HUB_OR_COUPLING,
            mount_slot: PhysicalComponentRole.MOUNT_OR_SUPPORT,
            body_slot: PhysicalComponentRole.DRIVEN_BODY,
        }

        components: list[PhysicalComponentInstance] = [_instance(slot, label_roles[slot]) for slot in base_slots]
        component_by_slot = dict(zip(base_slots, components))

        connections: list[MechanicalConnection] = []

        def _connection(connection_id, kind, from_instance, from_interface, to_instance, to_interface, meanings):
            connections.append(
                MechanicalConnection(
                    connection_id=connection_id,
                    kind=kind,
                    from_instance_id=from_instance.instance_id,
                    from_interface_id=from_interface,
                    to_instance_id=to_instance.instance_id,
                    to_interface_id=to_interface,
                    meanings=tuple(meanings),
                )
            )

        kinematic_torque = (
            ConnectionMeaning.KINEMATIC_REALIZATION_INTENT,
            ConnectionMeaning.TORQUE_LOAD_PATH_INTENT,
        )
        torque_only = (ConnectionMeaning.TORQUE_LOAD_PATH_INTENT,)
        kinematic_only = (ConnectionMeaning.KINEMATIC_REALIZATION_INTENT,)
        placement = (ConnectionMeaning.CAD_PLACEMENT_MATING_INTENT,)
        structural = (ConnectionMeaning.STRUCTURAL_RELEVANCE,)

        actuator_path: tuple[str, ...]
        transmission_path: tuple[str, ...]
        support_components: list[PhysicalComponentInstance] = []

        if template_input.architecture is DriveArchitecture.DIRECT_DRIVE:
            actuator_path = ("drive",)
            transmission_path = ()
            _connection(
                "drive",
                MechanicalConnectionKind.ROTATIONAL_DRIVE,
                component_by_slot[motor_slot],
                "output-shaft",
                component_by_slot[shaft_slot],
                "motor-side",
                kinematic_torque,
            )
        else:
            driver_gear_instance = _instance(driver_gear_slot, PhysicalComponentRole.TRANSMISSION)
            driven_gear_instance = _instance(driven_gear_slot, PhysicalComponentRole.TRANSMISSION)
            components.extend((driver_gear_instance, driven_gear_instance))
            _connection(
                "gear-drive",
                MechanicalConnectionKind.ROTATIONAL_DRIVE,
                component_by_slot[motor_slot],
                "output-shaft",
                driver_gear_instance,
                "bore",
                kinematic_torque,
            )
            _connection(
                "gear-mesh",
                MechanicalConnectionKind.GEAR_MESH,
                driver_gear_instance,
                "mesh",
                driven_gear_instance,
                "mesh",
                kinematic_only,
            )
            _connection(
                "gear-output",
                MechanicalConnectionKind.ROTATIONAL_DRIVE,
                driven_gear_instance,
                "bore",
                component_by_slot[shaft_slot],
                "motor-side",
                kinematic_torque,
            )
            actuator_path = ("gear-drive",)
            transmission_path = ("gear-mesh", "gear-output")
            for support_slot in support_mount_slots:
                support_instance = _instance(support_slot, PhysicalComponentRole.MOUNT_OR_SUPPORT)
                components.append(support_instance)
                support_components.append(support_instance)

        _connection("support-a", MechanicalConnectionKind.BEARING_SUPPORT, component_by_slot[bearing_a_slot], "housing", component_by_slot[shaft_slot], "journal-a", torque_only)
        _connection("support-b", MechanicalConnectionKind.BEARING_SUPPORT, component_by_slot[bearing_b_slot], "housing", component_by_slot[shaft_slot], "journal-b", torque_only)
        _connection("hub-coupling", MechanicalConnectionKind.COUPLING, component_by_slot[shaft_slot], "hub-side", component_by_slot[hub_slot], "shaft", kinematic_torque)
        _connection("payload-attachment", MechanicalConnectionKind.PAYLOAD_ATTACHMENT, component_by_slot[hub_slot], "body", component_by_slot[body_slot], "hub", kinematic_only)
        _connection("motor-mount", MechanicalConnectionKind.MOTOR_MOUNT, component_by_slot[motor_slot], "mount-face", component_by_slot[mount_slot], "motor", placement)
        if support_components:
            for suffix, bearing_slot, support_instance in (
                ("a", bearing_a_slot, support_components[0]),
                ("b", bearing_b_slot, support_components[1]),
            ):
                _connection(f"support-mount-{suffix}", MechanicalConnectionKind.STRUCTURAL_SUPPORT_DECLARATION, component_by_slot[bearing_slot], "housing", support_instance, "bearing", structural)

        binding = JointPhysicalRealizationBinding(
            joint_id=template_input.joint_id,
            driven_instance_id=component_by_slot[shaft_slot].instance_id,
            realization_component_ids=tuple(component.instance_id for component in components),
            actuator_path_connection_ids=actuator_path,
            transmission_path_connection_ids=transmission_path,
            support_instance_ids=(
                component_by_slot[bearing_a_slot].instance_id,
                component_by_slot[bearing_b_slot].instance_id,
            ),
            hub_or_coupling_instance_id=component_by_slot[hub_slot].instance_id,
            mount_or_support_instance_ids=(
                component_by_slot[mount_slot].instance_id,
                *(component.instance_id for component in support_components),
            ),
            axis_frame_reference=template_input.axis_frame_reference,
            load_path_metadata_available=False,
        )

        candidate = MechanicalDesignCandidate(
            source_binding=request.source_binding,
            synthesis_request_hash=request.request_hash,
            synthesis_policy_hash=policy.policy_hash,
            component_specifications=tuple(ordered_specs),
            realization=PhysicalMechanismRealization(
                components=tuple(components),
                connections=tuple(connections),
                joint_bindings=(binding,),
            ),
            design_variables=template_input.design_variables,
            generator_identity=GENERATOR_IDENTITY,
            generator_version=GENERATOR_VERSION,
        )
        return RevoluteDriveConstructionOutcome(status=DriveAdmissibility.ADMISSIBLE, candidate=candidate)

    def evaluate(
        self,
        candidate: MechanicalDesignCandidate,
        request,
        policy,
        requirements: RevoluteDriveEngineeringRequirements,
        *,
        source_state=None,
    ) -> RevoluteDriveAdmissibilityResult:
        request, policy = _revalidate_synthesis_inputs(request, policy)
        requirements = _revalidate_requirements(requirements)
        if candidate.synthesis_request_hash != request.request_hash:
            raise ValueError("candidate was synthesized from a different synthesis request")
        if candidate.synthesis_policy_hash != policy.policy_hash:
            raise ValueError("candidate was synthesized under a different synthesis policy")
        if candidate.source_binding != request.source_binding:
            raise ValueError("candidate source binding does not match the evaluation request source binding")

        source_path_defects = _source_scalar_binding_defects(
            requirements,
            request,
            source_state,
        )
        if source_path_defects:
            if any("not consumed" in defect or "no scalar value binding" in defect for defect in source_path_defects):
                raise ValueError("; ".join(source_path_defects))
            return RevoluteDriveAdmissibilityResult(
                candidate_hash=candidate.candidate_hash,
                source_binding_hash=_hash_source_binding(candidate.source_binding),
                synthesis_request_hash=request.request_hash,
                synthesis_policy_hash=policy.policy_hash,
                requirements_hash=requirements.requirements_hash,
                design_variables=candidate.design_variables,
                checks=(
                    EngineeringCheck(
                        check_id="source-authority",
                        status=EngineeringCheckStatus.UNRESOLVED,
                        reason="; ".join(source_path_defects),
                    ),
                ),
            )

        scoped_bindings = [
            binding
            for binding in candidate.realization.joint_bindings
            if binding.joint_id in request.required_joint_ids
        ]
        if len(scoped_bindings) != 1:
            raise ValueError(
                "candidate must contain exactly one physical realization binding within the required joint scope"
            )
        binding: JointPhysicalRealizationBinding = scoped_bindings[0]

        instances = {component.instance_id: component for component in candidate.realization.components}
        specifications = {
            specification.specification_hash: specification
            for specification in candidate.component_specifications
        }
        roles_by_id = {component.instance_id: component.role for component in candidate.realization.components}

        def _spec_for(instance_id: str) -> ComponentSpecificationSnapshot:
            instance = instances.get(instance_id)
            if instance is None:
                raise ValueError(f"candidate realization is missing instance '{instance_id}'")
            specification = specifications.get(instance.specification_hash)
            if specification is None:
                raise ValueError(f"candidate lacks the specification snapshot for instance '{instance_id}'")
            return specification

        actuator_ids = [instance_id for instance_id, role in roles_by_id.items() if role is PhysicalComponentRole.ACTUATOR]
        if len(actuator_ids) != 1:
            raise ValueError("candidate must realize exactly one actuator for one revolute joint scope")
        motor_id = actuator_ids[0]
        motor_specification = _spec_for(motor_id)
        shaft_specification = _spec_for(binding.driven_instance_id)

        checks: list[EngineeringCheck] = []

        load_case = requirements.design_load_case
        if (
            load_case.derive_transverse_load_from_spur_mesh
            and load_case.transverse_force_y is None
            and load_case.transverse_force_z is None
        ):
            checks.append(
                EngineeringCheck(
                    check_id="spur-mesh-load-derivation",
                    status=EngineeringCheckStatus.UNRESOLVED,
                    reason=(
                        "driven-side mesh-load derivation requires an explicit transverse-plane "
                        "mapping that this bounded template does not carry; the derived vector "
                        "cannot be established and the affected shaft checks stay unresolved"
                    ),
                )
            )

        is_spur = _realization_is_spur(candidate.realization.connections, binding)
        driver_gear_id = driven_gear_id = None
        if is_spur:
            mesh_connection = next(
                connection
                for connection in candidate.realization.connections
                if connection.kind is MechanicalConnectionKind.GEAR_MESH
            )
            driver_gear_id = mesh_connection.from_instance_id
            driven_gear_id = mesh_connection.to_instance_id

        if requirements.require_nominal_interface_compatibility:
            checks.append(
                _interface_compatibility_check(
                    shaft_specification=shaft_specification,
                    shaft_instance_id=binding.driven_instance_id,
                    bearing_specifications=(
                        _spec_for(binding.support_instance_ids[0]),
                        _spec_for(binding.support_instance_ids[1]),
                    ),
                    bearing_instance_ids=tuple(binding.support_instance_ids[:2]),
                    hub_specification=_spec_for(binding.hub_or_coupling_instance_id),
                    hub_instance_id=binding.hub_or_coupling_instance_id,
                    motor_specification=motor_specification if is_spur else None,
                    motor_instance_id=motor_id if is_spur else None,
                    driver_gear_specification=_spec_for(driver_gear_id) if is_spur else None,
                    driver_gear_instance_id=driver_gear_id,
                    driven_gear_specification=_spec_for(driven_gear_id) if is_spur else None,
                    driven_gear_instance_id=driven_gear_id,
                )
            )

        if is_spur:
            pair = evaluate_spur_pair(
                requirements,
                motor_specification,
                _spec_for(driver_gear_id),
                _spec_for(driven_gear_id),
                motor_instance_id=motor_id,
                driver_gear_instance_id=driver_gear_id,
                driven_gear_instance_id=driven_gear_id,
            )
            checks.extend((pair.compatibility_check, pair.speed_check, pair.torque_check))
            if pair.ratio_magnitude is not None:
                efficiency_value = None if requirements.efficiency is None else requirements.efficiency.value
                checks.extend(
                    evaluate_motor_checks(
                        requirements,
                        motor_specification,
                        motor_instance_id=motor_id,
                        architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
                        ratio_magnitude=pair.ratio_magnitude,
                        efficiency=efficiency_value,
                        include_speed_check=False,
                    )
                )
            else:
                checks.append(
                    EngineeringCheck(
                        check_id="motor-capability",
                        status=EngineeringCheckStatus.UNRESOLVED,
                        reason=(
                            "nominal spur-pair geometry is unavailable; motor-side capability "
                            "requirements cannot be established"
                        ),
                    )
                )
        else:
            checks.extend(
                evaluate_motor_checks(
                    requirements,
                    motor_specification,
                    motor_instance_id=motor_id,
                    architecture=DriveArchitecture.DIRECT_DRIVE,
                )
            )

        selected_diameter = next(
            (
                variable.value
                for variable in candidate.design_variables
                if variable.name == "selected-output-shaft-diameter"
            ),
            None,
        )
        shaft_sizing = calculate_shaft_static_sizing(
            requirements,
            shaft_specification,
            shaft_instance_id=binding.driven_instance_id,
            selected_diameter_mm=selected_diameter,
        )
        checks.extend((shaft_sizing.equilibrium_check, shaft_sizing.stress_check))

        consumed: list[ConsumedPropertyBinding] = []
        seen_keys: set[tuple[str, str]] = set()
        for check in checks:
            for property_binding in check.consumed_property_bindings:
                key = property_binding.model_dump_json()
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                consumed.append(property_binding)

        return RevoluteDriveAdmissibilityResult(
            candidate_hash=candidate.candidate_hash,
            source_binding_hash=_hash_source_binding(candidate.source_binding),
            synthesis_request_hash=request.request_hash,
            synthesis_policy_hash=policy.policy_hash,
            requirements_hash=requirements.requirements_hash,
            design_variables=candidate.design_variables,
            consumed_property_bindings=tuple(consumed),
            checks=tuple(checks),
        )


def _realization_is_spur(connections, binding) -> bool:
    connections_by_id = {connection.connection_id: connection for connection in connections}
    return any(
        connections_by_id[cid].kind is MechanicalConnectionKind.GEAR_MESH
        for cid in binding.transmission_path_connection_ids
        if cid in connections_by_id
    )


def _interface_compatibility_check(
    *,
    shaft_specification: ComponentSpecificationSnapshot,
    shaft_instance_id: str,
    bearing_specifications: tuple[ComponentSpecificationSnapshot, ComponentSpecificationSnapshot],
    bearing_instance_ids: tuple[str, str],
    hub_specification: ComponentSpecificationSnapshot,
    hub_instance_id: str,
    motor_specification: ComponentSpecificationSnapshot | None = None,
    motor_instance_id: str | None = None,
    driver_gear_specification: ComponentSpecificationSnapshot | None = None,
    driver_gear_instance_id: str | None = None,
    driven_gear_specification: ComponentSpecificationSnapshot | None = None,
    driven_gear_instance_id: str | None = None,
) -> EngineeringCheck:
    records: list[tuple[str, object, float | None, str | None]] = [
        ("shaft.diameter_mm",) + _numeric_property(shaft_specification, shaft_instance_id, "shaft.diameter_mm", "mm"),
        ("bearing A bore_diameter_mm",) + _numeric_property(bearing_specifications[0], bearing_instance_ids[0], "bearing.bore_diameter_mm", "mm"),
        ("bearing B bore_diameter_mm",) + _numeric_property(bearing_specifications[1], bearing_instance_ids[1], "bearing.bore_diameter_mm", "mm"),
        ("hub bore_diameter_mm",) + _numeric_property(hub_specification, hub_instance_id, "hub.bore_diameter_mm", "mm"),
    ]

    spur_records: list[tuple[str, object, float | None, str | None]] = []
    if driver_gear_specification is not None:
        spur_records.append(
            ("driver gear bore_diameter_mm",) + _numeric_property(
                driver_gear_specification,
                driver_gear_instance_id,
                "gear.bore_diameter_mm",
                "mm",
            )
        )
    if driven_gear_specification is not None:
        spur_records.append(
            ("driven gear bore_diameter_mm",) + _numeric_property(
                driven_gear_specification,
                driven_gear_instance_id,
                "gear.bore_diameter_mm",
                "mm",
            )
        )
    if motor_specification is not None:
        spur_records.append(
            ("motor output interface diameter",) + _numeric_property(
                motor_specification,
                motor_instance_id,
                "motor.output_shaft_diameter_mm",
                "mm",
            )
        )
    records.extend(spur_records)

    bindings = tuple(record[1] for record in records if record[1] is not None)
    reasons: list[str] = []
    values: list[float] = []
    violated = False
    unresolved = False
    for record in records:
        _, property_binding, value, defect = record
        if property_binding is None:
            unresolved = True
            reasons.append(f"{record[0]} property is missing")
        elif defect is not None:
            unresolved = True
            reasons.append(defect)
        elif value <= 0:
            violated = True
            reasons.append(f"{record[0]} must be strictly positive")
        else:
            values.append(value)

    base_values = [
        record[2]
        for record in records[:4]
        if record[2] is not None and record[2] > 0
    ]
    if len(base_values) > 1 and any(value != base_values[0] for value in base_values):
        violated = True
        reasons.append(
            f"nominal interface diameters are not equal across shaft, bearings, and hub: {sorted(set(base_values))}"
        )

    by_name = {record[0]: record[2] for record in records}
    if (
        by_name.get("driven gear bore_diameter_mm") is not None
        and by_name.get("shaft.diameter_mm") is not None
        and by_name["driven gear bore_diameter_mm"] != by_name["shaft.diameter_mm"]
    ):
        violated = True
        reasons.append("driven gear bore diameter does not equal shaft diameter")
    if (
        by_name.get("driver gear bore_diameter_mm") is not None
        and by_name.get("motor output interface diameter") is not None
        and by_name["driver gear bore_diameter_mm"] != by_name["motor output interface diameter"]
    ):
        violated = True
        reasons.append("driver gear bore diameter does not equal motor output interface diameter")

    status = (
        EngineeringCheckStatus.VIOLATED
        if violated
        else EngineeringCheckStatus.UNRESOLVED
        if unresolved
        else EngineeringCheckStatus.SATISFIED
    )
    reason = "; ".join(reasons) or None
    return EngineeringCheck(
        check_id="nominal-interface-compatibility",
        status=status,
        reason=None if status is EngineeringCheckStatus.SATISFIED else reason,
        consumed_property_bindings=bindings,
        consumed_requirement_paths=(),
    )


__all__ = ["RevoluteDriveRealizationService"]
