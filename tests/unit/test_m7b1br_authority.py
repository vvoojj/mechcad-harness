from datetime import datetime, timezone

import pytest

from mechcad_harness.azimuth_mount_plate import (
    AzimuthDriveMountInterface,
    AzimuthMotorMountPlateDesignRequirements,
    MountPointSpec,
    PlateThicknessPolicy,
    RequiredMatingHole,
    M7B1B_TEST_FIXTURE_ONLY,
)


def requirements():
    return AzimuthMotorMountPlateDesignRequirements(
        minimum_edge_margin_mm=10,
        minimum_hole_ligament_mm=5,
        plate_thickness_policy=PlateThicknessPolicy(allowed_thicknesses_mm=(6, 8, 10), minimum_thickness_mm=7),
        mounting_hole_radial_clearance_mm=1,
        central_radial_clearance_mm=2,
        provenance=M7B1B_TEST_FIXTURE_ONLY,
    )


def test_grouped_requirements_key_and_anchor_are_exact():
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer

    key = SupportedConstraintKey.AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS
    assert key.value == "azimuth.mount_plate_design_requirements"
    assert ConstraintRequestMaterializer.anchor_for(key) == ("constraint", "CON-AZIMUTH-MOUNT-PLATE-DESIGN-REQUIREMENTS")


def test_requirements_authoritative_value_round_trips_domain_semantics():
    from mechcad_harness.engineering.values import AzimuthMotorMountPlateDesignRequirementsValue

    value = AzimuthMotorMountPlateDesignRequirementsValue.from_domain(requirements())
    assert value.to_domain() == requirements()
    assert value.plate_thickness_policy.allowed_thicknesses_mm == (6, 8, 10)


def test_resolution_answer_materializes_typed_requirements_value():
    from mechcad_harness.agents.constraint_resolution import AzimuthMotorMountPlateDesignRequirementsAnswer, canonical_value_for_answer
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    answer = AzimuthMotorMountPlateDesignRequirementsAnswer(**requirements().model_dump(mode="json"))
    value = canonical_value_for_answer(SupportedConstraintKey.AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS, answer)
    assert value.to_domain() == requirements()


def test_requirements_value_rejects_extra_fields():
    from mechcad_harness.engineering.values import AzimuthMotorMountPlateDesignRequirementsValue

    with pytest.raises(ValueError):
        AzimuthMotorMountPlateDesignRequirementsValue(**requirements().model_dump(mode="json"), plate_length_mm=1)


def test_state_backed_synthesis_service_requires_both_authorities():
    from mechcad_harness.azimuth_mount_plate import AzimuthMountPlateSynthesisService, SynthesisStatus
    from mechcad_harness.models import DesignState

    result = AzimuthMountPlateSynthesisService().synthesize(DesignState(id="D", revision=1), source_revision=1, source_state_hash="sha256:state")
    assert result.status is SynthesisStatus.NOT_READY
    assert result.infeasibility.message == "azimuth.drive_mount_interface"


def test_state_resolved_authorities_produce_the_accepted_synthesis_fixture(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import AzimuthDriveMountInterfaceAnswer, AzimuthMotorMountPlateDesignRequirementsAnswer, ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import Constraint, ConstraintRequest, DesignState
    from mechcad_harness.state import StateManager

    drive = AzimuthDriveMountInterface(component_id="drive-test", frame_reference_id="datum-x", mount_points=(MountPointSpec(hole_id="a", x_mm=-30, y_mm=-25, external_mating_requirement=RequiredMatingHole(diameter_mm=8)), MountPointSpec(hole_id="b", x_mm=30, y_mm=-20, external_mating_requirement=RequiredMatingHole(diameter_mm=8)), MountPointSpec(hole_id="c", x_mm=28, y_mm=25, external_mating_requirement=RequiredMatingHole(diameter_mm=8)), MountPointSpec(hole_id="d", x_mm=-25, y_mm=24, external_mating_requirement=RequiredMatingHole(diameter_mm=8))), central_keepout_diameter_mm=30, central_required_mating_opening_diameter_mm=34)
    manager = StateManager(tmp_path)
    manager.create_project("PRJ", DesignState(id="D", revision=1, constraints=[Constraint(id="CON-AZIMUTH-DRIVE-MOUNT-INTERFACE", name="drive", expression="drive"), Constraint(id="CON-AZIMUTH-MOUNT-PLATE-DESIGN-REQUIREMENTS", name="plate", expression="plate")]))
    current = manager._read_current("PRJ")
    requests = ConstraintRequestStore(tmp_path)
    for request_id, key in (("DRIVE", SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE), ("PLATE", SupportedConstraintKey.AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS)):
        requests.write(ConstraintRequestRecord(request=ConstraintRequest(id=request_id, description="synthetic", revision=1, state_hash=current["state_hash"]), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1", source_invocation_id="I", source_agent_result_id="R", engineering_scope_id="transmission", key=key, rationale="test", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    command = ConstraintResolutionBatchCommand(command_id="CMD", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash=current["state_hash"], answers=(ConstraintResolutionAnswer(request_id="DRIVE", answer=AzimuthDriveMountInterfaceAnswer(**drive.model_dump(mode="json"))), ConstraintResolutionAnswer(request_id="PLATE", answer=AzimuthMotorMountPlateDesignRequirementsAnswer(**requirements().model_dump(mode="json")))), resolver_type="test", resolver_id="fixture", received_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    materialized = ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path)).materialize_batch(command, run_id="RUN")
    application = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    application.apply_batch(materialized, run_id="RUN")
    result = __import__("mechcad_harness.azimuth_mount_plate", fromlist=["AzimuthMountPlateSynthesisService"]).AzimuthMountPlateSynthesisService().synthesize(manager.load_current_state("PRJ"), source_revision=2, source_state_hash=manager._read_current("PRJ")["state_hash"], project_id="PRJ")
    assert result.status.value == "success"
    assert (result.spec.plate_length_mm, result.spec.plate_width_mm, result.spec.motor_center_x_mm, result.spec.motor_center_y_mm, result.spec.plate_thickness_mm) == (88, 78, 44, 39, 8)
    assert result.proposal.base_revision == 2


def test_missing_requirements_authority_is_not_ready(tmp_path):
    from mechcad_harness.azimuth_mount_plate import AzimuthMountPlateSynthesisService, SynthesisStatus
    from mechcad_harness.models import Constraint, DesignState
    from mechcad_harness.state import StateManager
    from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.engineering.values import AzimuthDriveMountInterfaceValue

    interface = AzimuthDriveMountInterface(component_id="drive", frame_reference_id="datum", mount_points=(MountPointSpec(hole_id="a", x_mm=1, y_mm=1, external_mating_requirement=RequiredMatingHole(diameter_mm=8)),), central_required_mating_opening_diameter_mm=34)
    manager = StateManager(tmp_path)
    state = DesignState(id="D", revision=1, constraints=[Constraint(id="CON-AZIMUTH-DRIVE-MOUNT-INTERFACE", name="drive", expression="drive"), Constraint(id="CON-AZIMUTH-MOUNT-PLATE-DESIGN-REQUIREMENTS", name="plate", expression="plate")])
    snapshot = manager.create_project("PRJ", state)
    parameter = AuthoritativeParameter(id="P", anchor=AuthoritativeAnchor(kind="constraint", id="CON-AZIMUTH-DRIVE-MOUNT-INTERFACE"), scope_id="transmission", key=SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE, value=AzimuthDriveMountInterfaceValue(kind=SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE.value, **interface.model_dump(mode="json")), source_resolution_id="R")
    updated = manager.create_revision("PRJ", state.model_copy(update={"authoritative_parameters": [parameter]}))
    result = AzimuthMountPlateSynthesisService().synthesize(updated.state, source_revision=2, source_state_hash=updated.state_hash)
    assert result.status is SynthesisStatus.NOT_READY
    assert result.infeasibility.message == "azimuth.mount_plate_design_requirements"
