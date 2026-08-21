from __future__ import annotations

import pytest

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import (
    BasePlateOperation,
    CadPartProgram,
    ThroughHoleOperation,
)
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash


def _make_part(part_id: str) -> CadPartProgram:
    return CadPartProgram(
        part_id=part_id,
        operations=(
            BasePlateOperation(operation_id="base", length_mm=10, width_mm=10, thickness_mm=5),
        ),
    )


def _make_imported(component_id: str, artifact_hash: str = "a" * 64) -> ImportedCadComponent:
    return ImportedCadComponent(
        component_id=component_id,
        artifact_id=f"ART-{component_id}",
        artifact_hash=f"sha256:{artifact_hash}",
        format="step",
        source_revision=1,
        source_state_hash="sha256:" + "b" * 64,
    )


class TestCadAssemblyProgramMixed:
    def test_parts_only(self):
        part = _make_part("plate")
        program = CadAssemblyProgram(
            assembly_id="test",
            parts=(part,),
            instances=(
                CadComponentInstance(instance_id="inst-1", part_id="plate"),
            ),
        )
        assert len(program.parts) == 1
        assert len(program.imported_components) == 0
        assert not program.has_imported_components

    def test_imported_only(self):
        imported = _make_imported("gear-1")
        program = CadAssemblyProgram(
            assembly_id="test",
            imported_components=(imported,),
            instances=(
                CadComponentInstance(instance_id="inst-1", part_id="gear-1"),
            ),
        )
        assert len(program.parts) == 0
        assert len(program.imported_components) == 1
        assert program.has_imported_components

    def test_mixed_components(self):
        part = _make_part("plate")
        imported = _make_imported("gear-1")
        program = CadAssemblyProgram(
            assembly_id="test",
            parts=(part,),
            imported_components=(imported,),
            instances=(
                CadComponentInstance(instance_id="inst-plate", part_id="plate"),
                CadComponentInstance(instance_id="inst-gear", part_id="gear-1"),
            ),
        )
        assert len(program.parts) == 1
        assert len(program.imported_components) == 1
        assert program.has_imported_components
        assert set(program.all_component_ids) == {"plate", "gear-1"}

    def test_empty_components_fails(self):
        with pytest.raises(ValueError, match="at least one part or imported component"):
            CadAssemblyProgram(
                assembly_id="test",
                parts=(),
                imported_components=(),
                instances=(
                    CadComponentInstance(instance_id="inst-1", part_id="plate"),
                ),
            )

    def test_duplicate_part_ids_fails(self):
        part1 = _make_part("plate")
        part2 = _make_part("plate")
        with pytest.raises(ValueError, match="part IDs must be unique"):
            CadAssemblyProgram(
                assembly_id="test",
                parts=(part1, part2),
                instances=(
                    CadComponentInstance(instance_id="inst-1", part_id="plate"),
                ),
            )

    def test_duplicate_imported_ids_fails(self):
        imported1 = _make_imported("gear-1")
        imported2 = _make_imported("gear-1")
        with pytest.raises(ValueError, match="imported component IDs must be unique"):
            CadAssemblyProgram(
                assembly_id="test",
                imported_components=(imported1, imported2),
                instances=(
                    CadComponentInstance(instance_id="inst-1", part_id="gear-1"),
                ),
            )

    def test_cross_type_duplicate_id_fails(self):
        part = _make_part("component-1")
        imported = _make_imported("component-1")
        with pytest.raises(ValueError, match="part and imported component IDs must be unique"):
            CadAssemblyProgram(
                assembly_id="test",
                parts=(part,),
                imported_components=(imported,),
                instances=(
                    CadComponentInstance(instance_id="inst-1", part_id="component-1"),
                ),
            )

    def test_unknown_component_reference_fails(self):
        part = _make_part("plate")
        with pytest.raises(ValueError, match="instance references an unknown component"):
            CadAssemblyProgram(
                assembly_id="test",
                parts=(part,),
                instances=(
                    CadComponentInstance(instance_id="inst-1", part_id="nonexistent"),
                ),
            )

    def test_unused_component_fails(self):
        part = _make_part("plate")
        imported = _make_imported("gear-1")
        with pytest.raises(ValueError, match="unused component definitions are not allowed"):
            CadAssemblyProgram(
                assembly_id="test",
                parts=(part,),
                imported_components=(imported,),
                instances=(
                    CadComponentInstance(instance_id="inst-1", part_id="plate"),
                ),
            )


class TestAssemblyHashMixed:
    def test_hash_includes_imported_components(self):
        part = _make_part("plate")
        imported = _make_imported("gear-1")
        program = CadAssemblyProgram(
            assembly_id="test",
            parts=(part,),
            imported_components=(imported,),
            instances=(
                CadComponentInstance(instance_id="inst-plate", part_id="plate"),
                CadComponentInstance(instance_id="inst-gear", part_id="gear-1"),
            ),
        )
        
        h = assembly_hash(program)
        assert h.startswith("sha256:")
        assert len(h) == 71

    def test_different_artifact_hash_changes_assembly_hash(self):
        part = _make_part("plate")
        imported1 = _make_imported("gear-1", "a" * 64)
        imported2 = _make_imported("gear-1", "c" * 64)
        
        program1 = CadAssemblyProgram(
            assembly_id="test",
            parts=(part,),
            imported_components=(imported1,),
            instances=(
                CadComponentInstance(instance_id="inst-plate", part_id="plate"),
                CadComponentInstance(instance_id="inst-gear", part_id="gear-1"),
            ),
        )
        
        program2 = CadAssemblyProgram(
            assembly_id="test",
            parts=(part,),
            imported_components=(imported2,),
            instances=(
                CadComponentInstance(instance_id="inst-plate", part_id="plate"),
                CadComponentInstance(instance_id="inst-gear", part_id="gear-1"),
            ),
        )
        
        assert assembly_hash(program1) != assembly_hash(program2)

    def test_canonical_ordering(self):
        part = _make_part("plate")
        imported1 = _make_imported("gear-1")
        imported2 = _make_imported("gear-2")
        
        program1 = CadAssemblyProgram(
            assembly_id="test",
            parts=(part,),
            imported_components=(imported1, imported2),
            instances=(
                CadComponentInstance(instance_id="inst-plate", part_id="plate"),
                CadComponentInstance(instance_id="inst-gear1", part_id="gear-1"),
                CadComponentInstance(instance_id="inst-gear2", part_id="gear-2"),
            ),
        )
        
        program2 = CadAssemblyProgram(
            assembly_id="test",
            parts=(part,),
            imported_components=(imported2, imported1),
            instances=(
                CadComponentInstance(instance_id="inst-plate", part_id="plate"),
                CadComponentInstance(instance_id="inst-gear2", part_id="gear-2"),
                CadComponentInstance(instance_id="inst-gear1", part_id="gear-1"),
            ),
        )
        
        assert assembly_hash(program1) == assembly_hash(program2)
