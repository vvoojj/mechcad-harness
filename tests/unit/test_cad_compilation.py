import inspect
import math

import pytest
from pydantic import ValidationError

from mechcad_harness.cad_compilation import (
    CadCompilationError,
    CadCompilationResult,
    CadCompilationService,
    COMPILER_VERSION,
    DesignSpecHashMismatchError,
    DesignSpecSourceBindingError,
    DesignSpecStaleSourceError,
    MountingPlateDesignSpec,
    UnresolvedDesignInputError,
    compile_mounting_plate,
    mounting_plate_spec_hash,
)
from mechcad_harness.cad_program import (
    BasePlateOperation,
    CadPartProgram,
    RectangularPocketOperation,
    ThroughHoleOperation,
    ThroughSlotOperation,
    cad_program_hash,
)
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager, state_hash


def valid_spec():
    return MountingPlateDesignSpec(
        part_id="motor_mounting_plate",
        plate_length_mm=120.0,
        plate_width_mm=100.0,
        plate_thickness_mm=10.0,
        mounting_holes=(
            MountingPlateDesignSpec.HoleSpec(hole_id="motor_1", x_mm=30.0, y_mm=25.0, diameter_mm=8.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="motor_2", x_mm=90.0, y_mm=25.0, diameter_mm=8.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="motor_3", x_mm=90.0, y_mm=75.0, diameter_mm=8.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="motor_4", x_mm=30.0, y_mm=75.0, diameter_mm=8.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="central", x_mm=60.0, y_mm=50.0, diameter_mm=30.0),
        ),
        pockets=(
            MountingPlateDesignSpec.PocketSpec(
                pocket_id="cable_clearance", x_mm=45.0, y_mm=35.0,
                length_mm=30.0, width_mm=20.0, depth_mm=3.0,
            ),
        ),
    )


# --- DesignSpec model tests ---

def test_spec_valid_construction():
    spec = valid_spec()
    assert spec.part_id == "motor_mounting_plate"
    assert len(spec.mounting_holes) == 5
    assert len(spec.pockets) == 1
    assert len(spec.slots) == 0


def test_spec_deterministic_hash():
    spec = valid_spec()
    h1 = mounting_plate_spec_hash(spec)
    h2 = mounting_plate_spec_hash(spec)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_spec_hash_changes_with_semantics():
    spec1 = valid_spec()
    spec2 = valid_spec()
    spec2.plate_thickness_mm = 12.0
    assert mounting_plate_spec_hash(spec1) != mounting_plate_spec_hash(spec2)


def test_spec_rejects_empty_part_id():
    with pytest.raises(ValidationError):
        MountingPlateDesignSpec(
            part_id="",
            plate_length_mm=100.0,
            plate_width_mm=80.0,
            plate_thickness_mm=6.0,
        )


def test_spec_rejects_nonpositive_dimensions():
    with pytest.raises(ValidationError):
        MountingPlateDesignSpec(
            part_id="p",
            plate_length_mm=0,
            plate_width_mm=80.0,
            plate_thickness_mm=6.0,
        )


def test_spec_rejects_nan_dimensions():
    with pytest.raises((ValidationError, ValueError)):
        MountingPlateDesignSpec(
            part_id="p",
            plate_length_mm=100.0,
            plate_width_mm=float("nan"),
            plate_thickness_mm=6.0,
        )


def test_spec_rejects_hole_outside_plate():
    with pytest.raises((ValidationError, CadCompilationError)):
        MountingPlateDesignSpec(
            part_id="p",
            plate_length_mm=50.0,
            plate_width_mm=50.0,
            plate_thickness_mm=5.0,
            mounting_holes=(
                MountingPlateDesignSpec.HoleSpec(hole_id="h", x_mm=5.0, y_mm=5.0, diameter_mm=50.0),
            ),
        )


def test_spec_rejects_overlapping_holes():
    with pytest.raises((ValidationError, CadCompilationError)):
        MountingPlateDesignSpec(
            part_id="p",
            plate_length_mm=100.0,
            plate_width_mm=100.0,
            plate_thickness_mm=5.0,
            mounting_holes=(
                MountingPlateDesignSpec.HoleSpec(hole_id="h1", x_mm=30.0, y_mm=50.0, diameter_mm=20.0),
                MountingPlateDesignSpec.HoleSpec(hole_id="h2", x_mm=35.0, y_mm=50.0, diameter_mm=20.0),
            ),
        )


def test_spec_rejects_duplicate_hole_ids():
    with pytest.raises(ValidationError):
        MountingPlateDesignSpec(
            part_id="p",
            plate_length_mm=100.0,
            plate_width_mm=100.0,
            plate_thickness_mm=5.0,
            mounting_holes=(
                MountingPlateDesignSpec.HoleSpec(hole_id="h", x_mm=30.0, y_mm=50.0, diameter_mm=8.0),
                MountingPlateDesignSpec.HoleSpec(hole_id="h", x_mm=70.0, y_mm=50.0, diameter_mm=8.0),
            ),
        )


def test_spec_rejects_pocket_beyond_plate():
    with pytest.raises((ValidationError, CadCompilationError)):
        MountingPlateDesignSpec(
            part_id="p",
            plate_length_mm=50.0,
            plate_width_mm=50.0,
            plate_thickness_mm=5.0,
            pockets=(
                MountingPlateDesignSpec.PocketSpec(
                    pocket_id="p1", x_mm=30.0, y_mm=30.0,
                    length_mm=30.0, width_mm=20.0, depth_mm=2.0,
                ),
            ),
        )


def test_spec_rejects_pocket_depth_exceeds_thickness():
    with pytest.raises((ValidationError, CadCompilationError)):
        MountingPlateDesignSpec(
            part_id="p",
            plate_length_mm=100.0,
            plate_width_mm=100.0,
            plate_thickness_mm=3.0,
            pockets=(
                MountingPlateDesignSpec.PocketSpec(
                    pocket_id="p1", x_mm=10.0, y_mm=10.0,
                    length_mm=20.0, width_mm=20.0, depth_mm=5.0,
                ),
            ),
        )


def test_spec_rejects_slot_length_less_than_width():
    with pytest.raises((ValidationError, CadCompilationError)):
        MountingPlateDesignSpec(
            part_id="p",
            plate_length_mm=100.0,
            plate_width_mm=100.0,
            plate_thickness_mm=5.0,
            slots=(
                MountingPlateDesignSpec.SlotSpec(
                    slot_id="s1", center_x_mm=50.0, center_y_mm=50.0,
                    length_mm=5.0, width_mm=10.0, orientation="x",
                ),
            ),
        )


def test_spec_rejects_slot_beyond_plate():
    with pytest.raises((ValidationError, CadCompilationError)):
        MountingPlateDesignSpec(
            part_id="p",
            plate_length_mm=50.0,
            plate_width_mm=50.0,
            plate_thickness_mm=5.0,
            slots=(
                MountingPlateDesignSpec.SlotSpec(
                    slot_id="s1", center_x_mm=45.0, center_y_mm=25.0,
                    length_mm=20.0, width_mm=5.0, orientation="x",
                ),
            ),
        )


# --- Compiler tests ---

def test_compiler_produces_valid_cad_part_program():
    spec = valid_spec()
    program = compile_mounting_plate(spec)
    assert program.part_id == "motor_mounting_plate"
    assert isinstance(program.operations[0], BasePlateOperation)
    assert program.operations[0].length_mm == 120.0
    assert program.operations[0].width_mm == 100.0
    assert program.operations[0].thickness_mm == 10.0


def test_compiler_deterministic_ordering():
    spec = valid_spec()
    p1 = compile_mounting_plate(spec)
    p2 = compile_mounting_plate(spec)
    assert cad_program_hash(p1) == cad_program_hash(p2)
    assert [op.operation_id for op in p1.operations] == [op.operation_id for op in p2.operations]


def test_compiler_exercises_all_operation_types():
    spec = MountingPlateDesignSpec(
        part_id="full_plate",
        plate_length_mm=100.0,
        plate_width_mm=80.0,
        plate_thickness_mm=6.0,
        mounting_holes=(
            MountingPlateDesignSpec.HoleSpec(hole_id="h1", x_mm=20.0, y_mm=20.0, diameter_mm=6.0),
        ),
        pockets=(
            MountingPlateDesignSpec.PocketSpec(
                pocket_id="p1", x_mm=30.0, y_mm=30.0,
                length_mm=20.0, width_mm=15.0, depth_mm=2.0,
            ),
        ),
        slots=(
            MountingPlateDesignSpec.SlotSpec(
                slot_id="s1", center_x_mm=70.0, center_y_mm=40.0,
                length_mm=20.0, width_mm=5.0, orientation="x",
            ),
        ),
    )
    program = compile_mounting_plate(spec)
    op_types = [op.operation_type for op in program.operations]
    assert "base_plate" in op_types
    assert "through_hole" in op_types
    assert "rectangular_pocket" in op_types
    assert "through_slot" in op_types


def test_compiler_sorted_by_type_then_id():
    spec = MountingPlateDesignSpec(
        part_id="sorted_plate",
        plate_length_mm=100.0,
        plate_width_mm=80.0,
        plate_thickness_mm=6.0,
        mounting_holes=(
            MountingPlateDesignSpec.HoleSpec(hole_id="z_hole", x_mm=50.0, y_mm=40.0, diameter_mm=6.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="a_hole", x_mm=20.0, y_mm=20.0, diameter_mm=6.0),
        ),
    )
    program = compile_mounting_plate(spec)
    ids = [op.operation_id for op in program.operations]
    assert ids[0] == "base"
    holes = [op for op in program.operations if isinstance(op, ThroughHoleOperation)]
    assert [h.operation_id for h in holes] == ["a_hole", "z_hole"]


def test_compiler_output_hash_semantic_sensitivity():
    base = compile_mounting_plate(valid_spec())
    modified = compile_mounting_plate(valid_spec().model_copy(update={"plate_thickness_mm": 12.0}))
    assert cad_program_hash(base) != cad_program_hash(modified)


# --- CadCompilationService tests (source binding) ---

def setup_service(tmp_path):
    state = DesignState(id="DES-m8c1", revision=1)
    sm = StateManager(tmp_path)
    sm.create_project("PRJ-m8c1", state)
    return sm, state_hash(state)


def test_service_validated_binding_produces_result(tmp_path):
    sm, sh = setup_service(tmp_path)
    service = CadCompilationService(sm)
    result = service.compile_mounting_plate(
        project_id="PRJ-m8c1",
        source_revision=1,
        source_state_hash=sh,
        spec=valid_spec(),
    )
    assert isinstance(result, CadCompilationResult)
    assert result.project_id == "PRJ-m8c1"
    assert result.source_revision == 1
    assert result.source_state_hash == sh
    assert result.compiler_version == COMPILER_VERSION
    assert result.spec_hash == mounting_plate_spec_hash(valid_spec())
    assert result.program_hash == cad_program_hash(result.program)


def test_service_stale_revision_fails_closed(tmp_path):
    sm, sh = setup_service(tmp_path)
    service = CadCompilationService(sm)
    with pytest.raises(DesignSpecStaleSourceError):
        service.compile_mounting_plate(
            project_id="PRJ-m8c1",
            source_revision=99,
            source_state_hash=sh,
            spec=valid_spec(),
        )


def test_service_hash_mismatch_fails_closed(tmp_path):
    sm, sh = setup_service(tmp_path)
    service = CadCompilationService(sm)
    with pytest.raises(DesignSpecHashMismatchError):
        service.compile_mounting_plate(
            project_id="PRJ-m8c1",
            source_revision=1,
            source_state_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            spec=valid_spec(),
        )


def test_service_project_mismatch_fails_closed(tmp_path):
    sm, sh = setup_service(tmp_path)
    service = CadCompilationService(sm)
    with pytest.raises(DesignSpecSourceBindingError):
        service.compile_mounting_plate(
            project_id="PRJ-wrong",
            source_revision=1,
            source_state_hash=sh,
            spec=valid_spec(),
        )


# --- DeterMINISM tests ---

def test_determinism_same_input_same_output(tmp_path):
    sm, sh = setup_service(tmp_path)
    service = CadCompilationService(sm)
    r1 = service.compile_mounting_plate(
        project_id="PRJ-m8c1",
        source_revision=1,
        source_state_hash=sh,
        spec=valid_spec(),
    )
    r2 = service.compile_mounting_plate(
        project_id="PRJ-m8c1",
        source_revision=1,
        source_state_hash=sh,
        spec=valid_spec(),
    )
    assert r1.program_hash == r2.program_hash
    assert r1.spec_hash == r2.spec_hash
    assert cad_program_hash(r1.program) == cad_program_hash(r2.program)
    assert [op.operation_id for op in r1.program.operations] == [op.operation_id for op in r2.program.operations]


# --- Generic output tests ---

def test_output_contains_only_generic_operations():
    program = compile_mounting_plate(valid_spec())
    for op in program.operations:
        assert isinstance(op, (BasePlateOperation, ThroughHoleOperation, RectangularPocketOperation, ThroughSlotOperation))


# --- No state mutation tests ---

def test_compilation_creates_no_design_state_revision(tmp_path):
    sm, sh = setup_service(tmp_path)
    service = CadCompilationService(sm)
    service.compile_mounting_plate(
        project_id="PRJ-m8c1",
        source_revision=1,
        source_state_hash=sh,
        spec=valid_spec(),
    )
    current = sm._read_current("PRJ-m8c1")
    assert current["revision"] == 1


def test_compilation_creates_no_change_proposal():
    spec = valid_spec()
    program = compile_mounting_plate(spec)
    from mechcad_harness.models.proposal import ChangeProposal
    assert not any(isinstance(program, ChangeProposal) for _ in [])


# --- Unresolved input tests ---

def test_empty_hole_list_compiles_to_only_base():
    spec = MountingPlateDesignSpec(
        part_id="empty_plate",
        plate_length_mm=100.0,
        plate_width_mm=80.0,
        plate_thickness_mm=6.0,
    )
    program = compile_mounting_plate(spec)
    assert len(program.operations) == 1
    assert isinstance(program.operations[0], BasePlateOperation)


# --- Domain isolation tests ---

def test_no_domain_semantics_in_generic_compiler():
    source = inspect.getsource(compile_mounting_plate)
    for term in ("yagi", "antenna", "azimuth", "elevation", "frequency", "transmission"):
        assert term not in source.lower(), f"generic compiler contains domain term: {term}"


def test_no_domain_semantics_in_spec_model():
    source = inspect.getsource(MountingPlateDesignSpec)
    for term in ("yagi", "antenna", "azimuth", "elevation", "frequency"):
        assert term not in source.lower(), f"generic spec contains domain term: {term}"
