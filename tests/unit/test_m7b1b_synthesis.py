import pytest

from mechcad_harness.azimuth_mount_plate import (
    M7B1B_TEST_FIXTURE_ONLY,
    AzimuthDriveMountInterface,
    AzimuthMotorMountPlateDesignRequirements,
    MountPointSpec,
    RequiredMatingHole,
    PlateThicknessPolicy,
    synthesize_azimuth_motor_mount_plate,
    build_azimuth_mount_plate_proposal,
    SynthesisStatus,
)


def interface():
    return AzimuthDriveMountInterface(
        component_id="drive-test",
        frame_reference_id="datum-x",
        mount_points=(
            MountPointSpec(hole_id="a", x_mm=-30, y_mm=-25, external_mating_requirement=RequiredMatingHole(diameter_mm=8)),
            MountPointSpec(hole_id="b", x_mm=30, y_mm=-20, external_mating_requirement=RequiredMatingHole(diameter_mm=8)),
            MountPointSpec(hole_id="c", x_mm=28, y_mm=25, external_mating_requirement=RequiredMatingHole(diameter_mm=8)),
            MountPointSpec(hole_id="d", x_mm=-25, y_mm=24, external_mating_requirement=RequiredMatingHole(diameter_mm=8)),
        ),
        central_keepout_diameter_mm=30,
        central_required_mating_opening_diameter_mm=34,
    )


def requirements():
    return AzimuthMotorMountPlateDesignRequirements(
        minimum_edge_margin_mm=10,
        minimum_hole_ligament_mm=5,
        plate_thickness_policy=PlateThicknessPolicy(allowed_thicknesses_mm=(6, 8, 10), minimum_thickness_mm=7),
        central_radial_clearance_mm=2,
        mounting_hole_radial_clearance_mm=1,
        provenance=M7B1B_TEST_FIXTURE_ONLY,
    )


def test_minimum_envelope_and_stock_thickness_are_deterministic():
    result = synthesize_azimuth_motor_mount_plate(interface(), requirements())
    assert result.status is SynthesisStatus.SUCCESS
    assert result.spec.plate_length_mm == pytest.approx(88)
    assert result.spec.plate_width_mm == pytest.approx(78)
    assert (result.spec.motor_center_x_mm, result.spec.motor_center_y_mm) == pytest.approx((44, 39))
    assert result.spec.plate_thickness_mm == 8
    assert min(result.edge_margins_mm.values()) == pytest.approx(10)
    assert result.minimum_ligament_mm >= 5


def test_missing_design_clearance_is_not_ready_without_numeric_design():
    incomplete = requirements().model_copy(update={"central_radial_clearance_mm": None})
    no_external = interface().model_copy(update={"central_required_mating_opening_diameter_mm": None, "manufacturer_required_central_radial_clearance_mm": None})
    result = synthesize_azimuth_motor_mount_plate(no_external, incomplete)
    assert result.status is SynthesisStatus.NOT_READY
    assert result.spec is None
    assert result.design_variables == {}
    assert result.infeasibility.code == "missing_requirement"


def test_ligament_conflict_is_infeasible_without_moving_hardware():
    bad = interface().model_copy(update={"mount_points": (MountPointSpec(hole_id="a", x_mm=-4, y_mm=0, external_mating_requirement=RequiredMatingHole(diameter_mm=10)), MountPointSpec(hole_id="b", x_mm=4, y_mm=0, external_mating_requirement=RequiredMatingHole(diameter_mm=10)))})
    result = synthesize_azimuth_motor_mount_plate(bad, requirements())
    assert result.status is SynthesisStatus.INFEASIBLE
    assert result.spec is None
    assert result.infeasibility.feature_pair == ("a", "b")


def test_synthesis_is_replayable_and_order_normalized():
    first = synthesize_azimuth_motor_mount_plate(interface(), requirements())
    reordered = interface().model_copy(update={"mount_points": tuple(reversed(interface().mount_points))})
    second = synthesize_azimuth_motor_mount_plate(reordered, requirements())
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_success_produces_proposal_without_mutating_state():
    result = synthesize_azimuth_motor_mount_plate(interface(), requirements())
    proposal = build_azimuth_mount_plate_proposal(result, project_id="PRJ", source_revision=1, source_state_hash="sha256:state")
    assert proposal.base_revision == 1
    assert proposal.base_state_hash == "sha256:state"
    assert proposal.actor == "mechcad-azimuth-synthesis"
    assert proposal.operations
    assert all("azimuth_mount_plates" in operation.path for operation in proposal.operations)


def test_manufacturer_opening_remains_minimum_when_design_clearance_is_smaller():
    result = synthesize_azimuth_motor_mount_plate(interface(), requirements().model_copy(update={"central_radial_clearance_mm": 0}))
    assert result.status is SynthesisStatus.SUCCESS
    assert result.derived_features["central_opening_diameter_mm"] == 34


def test_thickness_policy_rejects_unsatisfiable_stock():
    with pytest.raises(ValueError, match="satisfying"):
        PlateThicknessPolicy(allowed_thicknesses_mm=(6,), minimum_thickness_mm=7)


def test_active_edge_margin_proves_minimum_envelope():
    result = synthesize_azimuth_motor_mount_plate(interface(), requirements())
    assert min(result.edge_margins_mm.values()) == pytest.approx(requirements().minimum_edge_margin_mm)
    assert result.proposal is None
