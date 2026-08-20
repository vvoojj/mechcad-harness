import math

import pytest
from pydantic import ValidationError

from mechcad_harness.cad_program import (
    BasePlateOperation,
    CadPartProgram,
    ThroughHoleOperation,
    RectangularPocketOperation,
    cad_program_hash,
)
from mechcad_harness.backends.freecad import FreeCADBackend, freecad_program_artifact_id, freecad_object_name


def base():
    return BasePlateOperation(operation_id="base", length_mm=80, width_mm=60, thickness_mm=8)


def test_valid_program_variants_and_coordinate_convention():
    program = CadPartProgram(part_id="bracket", operations=(base(), ThroughHoleOperation(operation_id="h1", x_mm=10, y_mm=10, diameter_mm=6), RectangularPocketOperation(operation_id="p1", x_mm=25, y_mm=20, length_mm=30, width_mm=20, depth_mm=3)))
    assert program.coordinate_system == "lower-left-bottom; +X length, +Y width, +Z thickness"


@pytest.mark.parametrize("operations", [(), (ThroughHoleOperation(operation_id="h", x_mm=1, y_mm=1, diameter_mm=1),), (base(), base()), (ThroughHoleOperation(operation_id="h", x_mm=1, y_mm=1, diameter_mm=1), base())])
def test_program_order_and_base_rules(operations):
    with pytest.raises(ValidationError):
        CadPartProgram(part_id="p", operations=operations)


def test_duplicate_operation_ids_are_rejected():
    with pytest.raises(ValidationError):
        CadPartProgram(part_id="p", operations=(base(), ThroughHoleOperation(operation_id="base", x_mm=10, y_mm=10, diameter_mm=6)))


@pytest.mark.parametrize(
    "operation",
    [
        ThroughHoleOperation(operation_id="h", x_mm=1, y_mm=1, diameter_mm=3),
        ThroughHoleOperation(operation_id="h", x_mm=79, y_mm=30, diameter_mm=6),
        RectangularPocketOperation(operation_id="p", x_mm=60, y_mm=20, length_mm=30, width_mm=20, depth_mm=3),
        RectangularPocketOperation(operation_id="p", x_mm=25, y_mm=20, length_mm=30, width_mm=20, depth_mm=8),
    ],
)
def test_cut_geometry_preconditions_are_rejected(operation):
    with pytest.raises(ValidationError):
        CadPartProgram(part_id="p", operations=(base(), operation))


def test_nonfinite_dimensions_are_rejected():
    with pytest.raises(ValidationError):
        BasePlateOperation(operation_id="base", length_mm=math.inf, width_mm=60, thickness_mm=8)


def test_program_hash_is_canonical_order_sensitive_and_semantic():
    first = CadPartProgram(part_id="p", operations=(base(), ThroughHoleOperation(operation_id="h", x_mm=10, y_mm=10, diameter_mm=6)))
    same = CadPartProgram.model_validate(first.model_dump(mode="json"))
    changed = first.model_copy(update={"operations": (base(), ThroughHoleOperation(operation_id="h", x_mm=10, y_mm=10, diameter_mm=7))})
    reordered = CadPartProgram(part_id="p", operations=(base(), ThroughHoleOperation(operation_id="h2", x_mm=20, y_mm=20, diameter_mm=6), ThroughHoleOperation(operation_id="h1", x_mm=10, y_mm=10, diameter_mm=6)))
    assert cad_program_hash(first) == cad_program_hash(same)
    assert cad_program_hash(first) != cad_program_hash(changed)
    assert cad_program_hash(first) != cad_program_hash(reordered)


def test_identifiers_are_not_freecad_handles_or_script_fragments():
    with pytest.raises(ValidationError):
        BasePlateOperation(operation_id='bad\n";exec("x")', length_mm=80, width_mm=60, thickness_mm=8)


def test_program_artifact_identity_includes_program_hash_and_kind():
    program = CadPartProgram(part_id="p", operations=(base(),))
    assert freecad_program_artifact_id("PRJ", "RUN", 1, "sha256:s", program, "FCStd") != freecad_program_artifact_id("PRJ", "RUN", 1, "sha256:s", program, "STEP")


def test_compiler_uses_explicit_operation_mapping_and_safe_literals():
    program = CadPartProgram(part_id="p", operations=(base(), ThroughHoleOperation(operation_id="h", x_mm=10, y_mm=10, diameter_mm=6), RectangularPocketOperation(operation_id="pocket", x_mm=25, y_mm=20, length_mm=30, width_mm=20, depth_mm=3)))
    script = FreeCADBackend.compile_program(program, "C:/tmp/plate.FCStd", "C:/tmp/plate.step")
    assert "Part.makeBox" in script
    assert "makeCylinder" in script
    assert "makeBox" in script
    assert "eval(" not in script
    assert "exec(" not in script


def test_distinct_operation_ids_have_distinct_freecad_names():
    assert freecad_object_name("hole-1") != freecad_object_name("hole.1")
    assert freecad_object_name("hole_1") != freecad_object_name("hole-1")
