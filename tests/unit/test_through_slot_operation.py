import math

import pytest
from pydantic import ValidationError

from mechcad_harness.backends.freecad import FreeCADBackend, freecad_object_name
from mechcad_harness.cad_manifest import build_program_manifest
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram, ThroughSlotOperation, cad_program_hash


def base():
    return BasePlateOperation(operation_id="base", length_mm=100, width_mm=60, thickness_mm=8)


def slot(**overrides):
    payload = {"operation_id": "slot1", "center_x_mm": 50, "center_y_mm": 30, "length_mm": 40, "width_mm": 10, "orientation": "y"}
    payload.update(overrides)
    return ThroughSlotOperation(**payload)


def test_centered_x_and_y_slots_are_valid_and_preserve_total_length_semantics():
    y_slot = slot()
    x_slot = slot(orientation="x")
    assert y_slot.length_mm == 40
    assert y_slot.width_mm == 10
    assert x_slot.orientation == "x"
    assert y_slot.length_mm >= y_slot.width_mm


@pytest.mark.parametrize(
    "kwargs",
    (
        {"length_mm": 0},
        {"width_mm": 0},
        {"length_mm": 9, "width_mm": 10},
        {"center_x_mm": math.nan},
        {"center_y_mm": math.inf},
        {"orientation": "diagonal"},
    ),
)
def test_slot_schema_rejects_invalid_geometry(kwargs):
    with pytest.raises(ValidationError):
        slot(**kwargs)


@pytest.mark.parametrize(
    "operation",
    (
        slot(orientation="x", center_x_mm=19),
        slot(orientation="x", center_y_mm=4),
        slot(orientation="y", center_x_mm=4),
        slot(orientation="y", center_y_mm=19),
    ),
)
def test_program_rejects_orientation_aware_boundary_crossing(operation):
    with pytest.raises(ValidationError):
        CadPartProgram(part_id="slot_fixture", operations=(base(), operation))


def test_exact_boundary_contact_matches_through_hole_containment_policy():
    program = CadPartProgram(part_id="slot_fixture", operations=(base(), slot(center_x_mm=5, length_mm=10, width_mm=10, orientation="x")))
    assert program.operations[-1].operation_id == "slot1"


def test_program_hash_includes_every_slot_semantic_field():
    first = CadPartProgram(part_id="slot_fixture", operations=(base(), slot()))
    changes = (
        slot(center_x_mm=51),
        slot(center_y_mm=31),
        slot(length_mm=41),
        slot(width_mm=11),
        slot(orientation="x"),
        slot(operation_id="slot2"),
    )
    assert cad_program_hash(first) == cad_program_hash(CadPartProgram.model_validate(first.model_dump(mode="json")))
    assert all(cad_program_hash(first) != cad_program_hash(CadPartProgram(part_id="slot_fixture", operations=(base(), changed))) for changed in changes)


def test_manifest_and_compiler_keep_slot_operation_identity():
    program = CadPartProgram(part_id="slot_fixture", operations=(base(), slot()))
    manifest = build_program_manifest(program)
    entry = manifest.operations[-1]
    assert entry.operation_id == "slot1"
    assert entry.operation_kind == "through_slot"
    assert entry.internal_name == freecad_object_name("slot1")
    script = FreeCADBackend.compile_program(program, "C:/tmp/slot.FCStd", "C:/tmp/slot.step")
    assert "Part.makeBox" in script
    assert script.count("Part.makeCylinder") >= 2
    assert "eval(" not in script
    assert "exec(" not in script


def test_slot_area_and_volume_are_independent_of_freecad():
    operation = slot()
    expected_area = (operation.length_mm - operation.width_mm) * operation.width_mm + math.pi * (operation.width_mm / 2) ** 2
    assert expected_area == pytest.approx(300 + 25 * math.pi)
    assert expected_area * base().thickness_mm == pytest.approx((300 + 25 * math.pi) * 8)
