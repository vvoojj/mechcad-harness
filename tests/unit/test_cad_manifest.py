import pytest
from pydantic import ValidationError

from mechcad_harness.cad_manifest import CadOperationManifest, CadOperationManifestEntry, CadProgramManifest, build_program_manifest
from mechcad_harness.cad_program import AxialBoreOperation, CadPartProgram, CylindricalStockOperation, acceptance_program
from mechcad_harness.backends.freecad import freecad_object_name


def test_manifest_contains_all_operations_in_program_order():
    program = acceptance_program()
    manifest = build_program_manifest(program)
    assert manifest.part_id == program.part_id
    assert manifest.program_hash
    assert [entry.operation_id for entry in manifest.operations] == ["base", "hole1", "hole2", "pocket"]
    assert [entry.operation_kind for entry in manifest.operations] == ["base_plate", "through_hole", "through_hole", "rectangular_pocket"]
    assert [entry.internal_name for entry in manifest.operations] == [freecad_object_name(item.operation_id) for item in program.operations]


def test_manifest_rejects_duplicate_or_wrong_identity():
    program = acceptance_program()
    manifest = build_program_manifest(program)
    with pytest.raises(ValidationError):
        CadProgramManifest.model_validate(manifest.model_dump(mode="json") | {"operations": [manifest.operations[0].model_dump(mode="json")] * 4})
    with pytest.raises(ValidationError):
        CadOperationManifestEntry(operation_id="base", operation_kind="wrong", internal_name="op_62")


def test_m13_2_manifest_contains_cylindrical_operation_kinds_in_order():
    program = CadPartProgram(
        part_id="hub",
        operations=(
            CylindricalStockOperation(operation_id="stock", diameter_mm=40, length_mm=30),
            AxialBoreOperation(operation_id="bore", diameter_mm=20, start_z_mm=0, depth_mm=30),
        ),
        coordinate_system="base-center; +Z cylinder-axis",
    )

    manifest = build_program_manifest(program)

    assert [entry.operation_kind for entry in manifest.operations] == ["cylindrical_stock", "axial_bore"]
