import importlib.util
import math

import pytest

from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad, freecad_object_name
from mechcad_harness.cad_manifest import build_program_manifest
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram, ThroughSlotOperation, cad_program_hash
from mechcad_harness.cad_service import CadGenerationService
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager


FREECAD_AVAILABLE = discover_freecad().available and importlib.util.find_spec("mechcad_harness") is not None


def slot_fixture_program():
    return CadPartProgram(
        part_id="M7A2AS1ThroughSlotFixture",
        operations=(
            BasePlateOperation(operation_id="base", length_mm=100, width_mm=60, thickness_mm=8),
            ThroughSlotOperation(operation_id="slot1", center_x_mm=50, center_y_mm=30, length_mm=40, width_mm=10, orientation="y"),
        ),
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_through_slot_persists_and_reloads_through_production_cad_path(tmp_path):
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M7A2AS1-TEST", DesignState(id="DES-M7A2AS1-TEST", revision=1))
    program = slot_fixture_program()
    service = CadGenerationService(manager, FreeCADBackend())
    first = service.generate_program("PRJ-M7A2AS1-TEST", "RUN-M7A2AS1-TEST", snapshot.revision, snapshot.state_hash, program, tmp_path)
    second = service.generate_program("PRJ-M7A2AS1-TEST", "RUN-M7A2AS1-TEST", snapshot.revision, snapshot.state_hash, program, tmp_path)
    expected_volume = 100 * 60 * 8 - ((40 - 10) * 10 + math.pi * (10 / 2) ** 2) * 8
    assert first.fcstd == second.fcstd
    assert first.step == second.step
    assert first.fcstd.input_hash == cad_program_hash(program)
    assert first.fcstd_verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
    assert first.step_verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
    assert (first.fcstd_verification.x_length_mm, first.fcstd_verification.y_length_mm, first.fcstd_verification.z_length_mm) == pytest.approx((100, 60, 8), abs=1e-6)
    assert (first.step_verification.x_length_mm, first.step_verification.y_length_mm, first.step_verification.z_length_mm) == pytest.approx((100, 60, 8), abs=1e-6)
    assert first.fcstd_verification.object_name == freecad_object_name("slot1")
    assert first.fcstd_verification.feature_probes == {"slot_slot1_1": True, "slot_slot1_2": True, "slot_slot1_3": True}
    assert first.step_verification.feature_probes == {"slot_slot1_1": True, "slot_slot1_2": True, "slot_slot1_3": True}
    manifest = build_program_manifest(program)
    assert manifest.operations[-1].model_dump() == {"operation_id": "slot1", "operation_kind": "through_slot", "internal_name": freecad_object_name("slot1")}
