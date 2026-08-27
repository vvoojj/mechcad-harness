from __future__ import annotations

from copy import deepcopy
import json

import pytest

from mechcad_harness.candidates import (
    CandidateCurrentness,
    CandidateCurrentnessService,
    CandidateIntegrityError,
    CandidateIntegrityVerifier,
    CandidatePublicationService,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    CandidateDesignVariable,
    ComponentPropertyAvailability,
    ComponentPropertySnapshot,
    ComponentPropertyAuthority,
    ComponentSpecificationSnapshot,
    ConnectionMeaning,
    MechanicalConnection,
    MechanicalConnectionKind,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
    JointPhysicalRealizationBinding,
    UnresolvedCandidateItem,
    UnresolvedCandidateReason,
    candidate_hash,
)
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager, state_hash


def _state() -> DesignState:
    return DesignState(
        id="DES-M12",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )


def _source(state: DesignState) -> CandidateSourceBinding:
    return CandidateSourceBinding(
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


def _candidate(state: DesignState | None = None) -> tuple[MechanicalDesignCandidate, CandidateSynthesisRequest, CandidateSynthesisPolicy]:
    state = state or _state()
    source = _source(state)
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
    hub = ComponentSpecificationSnapshot(component_type="hub", source_identity="custom:hub@1", interfaces=("shaft", "body"))
    mount = ComponentSpecificationSnapshot(component_type="mount", source_identity="custom:mount@1", interfaces=("motor", "frame"))
    body = ComponentSpecificationSnapshot(component_type="driven-body", source_identity="custom:body@1", interfaces=("hub", "payload"))
    specs = (motor, shaft, bearing, hub, mount, body)
    instances = (
        PhysicalComponentInstance(instance_id="motor", specification_hash=motor.specification_hash, role=PhysicalComponentRole.ACTUATOR, interfaces=("output-shaft", "mount-face")),
        PhysicalComponentInstance(instance_id="shaft", specification_hash=shaft.specification_hash, role=PhysicalComponentRole.SHAFT, interfaces=("motor-side", "hub-side", "journal-a", "journal-b")),
        PhysicalComponentInstance(instance_id="bearing-a", specification_hash=bearing.specification_hash, role=PhysicalComponentRole.BEARING, interfaces=("bore", "housing")),
        PhysicalComponentInstance(instance_id="bearing-b", specification_hash=bearing.specification_hash, role=PhysicalComponentRole.BEARING, interfaces=("bore", "housing")),
        PhysicalComponentInstance(instance_id="hub", specification_hash=hub.specification_hash, role=PhysicalComponentRole.HUB_OR_COUPLING, interfaces=("shaft", "body")),
        PhysicalComponentInstance(instance_id="mount", specification_hash=mount.specification_hash, role=PhysicalComponentRole.MOUNT_OR_SUPPORT, interfaces=("motor", "frame")),
        PhysicalComponentInstance(instance_id="body", specification_hash=body.specification_hash, role=PhysicalComponentRole.DRIVEN_BODY, interfaces=("hub", "payload")),
    )
    realization = PhysicalMechanismRealization(
        components=instances,
        connections=(
            MechanicalConnection(connection_id="drive", kind=MechanicalConnectionKind.ROTATIONAL_DRIVE, from_instance_id="motor", from_interface_id="output-shaft", to_instance_id="shaft", to_interface_id="motor-side", meanings=(ConnectionMeaning.KINEMATIC_REALIZATION_INTENT, ConnectionMeaning.TORQUE_LOAD_PATH_INTENT)),
            MechanicalConnection(connection_id="support-a", kind=MechanicalConnectionKind.BEARING_SUPPORT, from_instance_id="bearing-a", from_interface_id="bore", to_instance_id="shaft", to_interface_id="journal-a", meanings=(ConnectionMeaning.TORQUE_LOAD_PATH_INTENT,)),
            MechanicalConnection(connection_id="support-b", kind=MechanicalConnectionKind.BEARING_SUPPORT, from_instance_id="bearing-b", from_interface_id="bore", to_instance_id="shaft", to_interface_id="journal-b", meanings=(ConnectionMeaning.TORQUE_LOAD_PATH_INTENT,)),
            MechanicalConnection(connection_id="hub", kind=MechanicalConnectionKind.COUPLING, from_instance_id="shaft", from_interface_id="hub-side", to_instance_id="hub", to_interface_id="shaft", meanings=(ConnectionMeaning.KINEMATIC_REALIZATION_INTENT, ConnectionMeaning.TORQUE_LOAD_PATH_INTENT)),
            MechanicalConnection(connection_id="payload", kind=MechanicalConnectionKind.PAYLOAD_ATTACHMENT, from_instance_id="hub", from_interface_id="body", to_instance_id="body", to_interface_id="hub", meanings=(ConnectionMeaning.KINEMATIC_REALIZATION_INTENT,)),
            MechanicalConnection(connection_id="mount", kind=MechanicalConnectionKind.MOTOR_MOUNT, from_instance_id="motor", from_interface_id="mount-face", to_instance_id="mount", to_interface_id="motor", meanings=(ConnectionMeaning.CAD_PLACEMENT_MATING_INTENT,)),
        ),
        joint_bindings=(
            {"joint_id": "J-1", "driven_instance_id": "shaft", "realization_component_ids": ("motor", "shaft", "bearing-a", "bearing-b", "hub", "mount"), "actuator_path_connection_ids": ("drive",), "support_instance_ids": ("bearing-a", "bearing-b"), "hub_or_coupling_instance_id": "hub", "mount_or_support_instance_ids": ("mount",), "axis_frame_reference": "joint:J-1=shaft-axis", "load_path_metadata_available": False},
        ),
    )
    request = CandidateSynthesisRequest(source_binding=source, required_joint_ids=("J-1",), requested_joint_ids=("J-1",))
    policy = CandidateSynthesisPolicy(entries=(("allow-direct-drive", "direct_drive", "hard_admissibility"), ("preferred-voltage", "24 V", "preference")))
    candidate = MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=request.request_hash,
        synthesis_policy_hash=policy.policy_hash,
        component_specifications=specs,
        realization=realization,
        unresolved_items=(UnresolvedCandidateItem(subject_path="/components/motor/properties/continuous_torque", required_information="continuous torque", reason=UnresolvedCandidateReason.PROPERTY_UNAVAILABLE),),
        generator_identity="fixture-generator",
        generator_version="1",
    )
    return candidate, request, policy


def test_candidate_is_immutable_and_hashes_a_realistic_direct_drive_fixture():
    candidate, request, policy = _candidate()
    assert candidate.candidate_hash == candidate_hash(candidate)
    assert CandidateIntegrityVerifier().verify(candidate, request, policy).candidate_hash == candidate.candidate_hash
    with pytest.raises(Exception):
        candidate.generator_identity = "forged"


def test_property_availability_preserves_missing_and_per_property_authority():
    candidate, *_ = _candidate()
    properties = candidate.component_specifications[0].properties
    assert [property.availability for property in properties] == [ComponentPropertyAvailability.AVAILABLE, ComponentPropertyAvailability.MISSING]
    assert properties[1].normalized_value is None
    assert ComponentPropertyAvailability.NOT_APPLICABLE != ComponentPropertyAvailability.MISSING
    assert "NOT_SUITABLE" not in ComponentPropertyAvailability.__members__


def test_integrity_rejects_forged_candidate_and_nested_hashes():
    candidate, request, policy = _candidate()
    forged = candidate.model_copy(update={"candidate_hash": "sha256:" + "0" * 64})
    with pytest.raises(CandidateIntegrityError):
        CandidateIntegrityVerifier().verify(forged, request, policy)
    forged_spec = candidate.component_specifications[0].model_copy(update={"specification_hash": "sha256:" + "0" * 64})
    forged_candidate = candidate.model_copy(update={"component_specifications": (forged_spec, *candidate.component_specifications[1:])})
    with pytest.raises(CandidateIntegrityError):
        CandidateIntegrityVerifier().verify(forged_candidate, request, policy)


def test_source_validation_and_relevance_sensitive_currentness(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, request, policy = _candidate(state)
    service = CandidateCurrentnessService(manager)
    assert service.evaluate(candidate, request, policy) is CandidateCurrentness.CURRENT
    unrelated = state.model_copy(update={"components": []})
    manager.create_revision("PRJ-M12", unrelated)
    assert service.evaluate(candidate, request, policy) is CandidateCurrentness.CURRENT
    changed = unrelated.model_copy(update={"id": "DES-CHANGED"})
    manager.create_revision("PRJ-M12", changed)
    assert service.evaluate(candidate, request, policy) is CandidateCurrentness.STALE_RELATIVE_TO_CURRENT_STATE


def test_explicit_publication_fresh_reloads_and_rejects_tamper(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, request, policy = _candidate(state)
    publication = CandidatePublicationService(tmp_path, "PRJ-M12", manager).publish(candidate, request, policy)
    assert publication.candidate.candidate_hash == candidate.candidate_hash
    payload_path = tmp_path / publication.artifact.relative_path
    payload_path.write_bytes(b"{}")
    with pytest.raises(CandidateIntegrityError):
        CandidatePublicationService(tmp_path, "PRJ-M12", manager).resolve(publication.artifact.artifact_id)


def test_m12_2_candidate_request_publication_round_trip_has_no_m12_3_scalar_extension(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, request, policy = _candidate(state)

    assert "source_value_hash" not in candidate.source_binding.consumed_authority[0].model_dump(mode="json")
    candidate_round_trip = MechanicalDesignCandidate.model_validate(
        candidate.model_dump(mode="json")
    )
    request_round_trip = CandidateSynthesisRequest.model_validate(
        request.model_dump(mode="json")
    )
    assert candidate_round_trip == candidate
    assert request_round_trip == request

    publication = CandidatePublicationService(tmp_path, "PRJ-M12", manager).publish(
        candidate, request, policy
    )
    resolved = CandidatePublicationService(tmp_path, "PRJ-M12", manager).resolve(
        publication.artifact.artifact_id
    )
    assert resolved.candidate == candidate


def test_required_joint_omission_and_policy_override_are_rejected():
    candidate, request, policy = _candidate()
    missing_values = candidate.model_dump(mode="json")
    missing_values["realization"]["joint_bindings"] = []
    missing_values["realization"]["realization_hash"] = "pending"
    missing_values["candidate_hash"] = "pending"
    missing_joint = MechanicalDesignCandidate.model_validate(missing_values)
    with pytest.raises(CandidateIntegrityError, match="required joint"):
        CandidateIntegrityVerifier().verify(missing_joint, request, policy)
    override_values = candidate.model_dump(mode="json")
    override_values["design_variables"] = [{"name": "preferred-voltage", "value": "12 V", "canonical_path": "/id"}]
    override_values["candidate_hash"] = "pending"
    with pytest.raises(ValueError, match="cannot override"):
        MechanicalDesignCandidate.model_validate(override_values)


def test_topology_and_property_contracts_fail_closed():
    candidate, *_ = _candidate()
    duplicate = candidate.realization.components[0]
    with pytest.raises(ValueError, match="unique"):
        PhysicalMechanismRealization(components=(duplicate, duplicate))
    with pytest.raises(ValueError, match="endpoint"):
        PhysicalMechanismRealization(
            components=candidate.realization.components,
            connections=(MechanicalConnection(connection_id="bad", kind=MechanicalConnectionKind.COUPLING, from_instance_id="missing", from_interface_id="x", to_instance_id="shaft", to_interface_id="motor-side"),),
        )
    with pytest.raises(ValueError, match="available component property"):
        ComponentPropertySnapshot(key="mass", availability=ComponentPropertyAvailability.AVAILABLE, source_identity="x", authority=ComponentPropertyAuthority.MEASURED_LOCAL)


def test_component_property_hash_change_cascades_to_candidate_identity():
    candidate, request, policy = _candidate()
    original = candidate.candidate_hash
    motor = candidate.component_specifications[0]
    voltage_values = motor.properties[0].model_dump(mode="json")
    voltage_values.update(normalized_value=48.0, property_hash="pending")
    voltage = ComponentPropertySnapshot.model_validate(voltage_values)
    motor_values = motor.model_dump(mode="json")
    motor_values.update(properties=[voltage.model_dump(mode="json"), *[property.model_dump(mode="json") for property in motor.properties[1:]]], specification_hash="pending")
    changed_motor = ComponentSpecificationSnapshot.model_validate(motor_values)
    changed_values = candidate.model_dump(mode="json")
    changed_values["component_specifications"] = [changed_motor.model_dump(mode="json"), *[spec.model_dump(mode="json") for spec in candidate.component_specifications[1:]]]
    changed_values["realization"]["components"][0]["specification_hash"] = changed_motor.specification_hash
    changed_values["realization"]["realization_hash"] = "pending"
    changed_values["candidate_hash"] = "pending"
    changed = MechanicalDesignCandidate.model_validate(changed_values)
    assert changed.candidate_hash != original


def test_publication_rejects_cross_project_and_semantic_manifest_substitution(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, request, policy = _candidate(state)
    publisher = CandidatePublicationService(tmp_path, "PRJ-M12", manager)
    publication = publisher.publish(candidate, request, policy)
    other_manager = StateManager(tmp_path)
    other_manager.create_project("PRJ-OTHER", state)
    with pytest.raises(CandidateIntegrityError):
        CandidatePublicationService(tmp_path, "PRJ-OTHER", other_manager).resolve(publication.artifact.artifact_id)
    payload_path = tmp_path / publication.artifact.relative_path
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["candidate"]["source_binding"]["source_revision"] = 2
    payload_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(CandidateIntegrityError):
        publisher.resolve(publication.artifact.artifact_id)


def test_currentness_unavailable_is_not_an_integrity_failure(tmp_path):
    candidate, request, policy = _candidate()
    assert CandidateIntegrityVerifier().verify(candidate, request, policy) == candidate
    assert CandidateCurrentnessService(StateManager(tmp_path)).evaluate(candidate, request, policy) is CandidateCurrentness.CURRENTNESS_UNAVAILABLE
