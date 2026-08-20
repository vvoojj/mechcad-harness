import pytest

from mechcad_harness.cad_program import BasePlateOperation
from mechcad_harness.yagi_carrier import YagiCarrierSynthesisService
from mechcad_harness.yagi_carrier_packaging import (
    CARRIER_PACKAGING_CROSS_SECTION_MM,
    compile_yagi_carrier_packaging_geometry,
    reference_antenna_envelope_programs,
    representative_yagi_carrier_assembly,
)
from mechcad_harness.yagi_sliding_interface import select_yagi_carrier_sliding_interface


def test_packaging_compiler_uses_native_extrusion_decision_without_through_slot():
    from tests.unit.test_m7b2b_yagi_carrier import requirements
    from mechcad_harness.yagi_carrier import synthesize_yagi_carrier_layout

    result = synthesize_yagi_carrier_layout(requirements())
    program = compile_yagi_carrier_packaging_geometry(result.spec, select_yagi_carrier_sliding_interface())
    base = program.operations[0]
    assert isinstance(base, BasePlateOperation)
    assert (base.length_mm, base.width_mm, base.thickness_mm) == (40, 500, 40)
    assert len(program.operations) == 1
    assert CARRIER_PACKAGING_CROSS_SECTION_MM == (40, 40)
    assert result.spec.carrier_length_mm == 500


def test_packaging_geometry_is_not_material_or_structural_model():
    from tests.unit.test_m7b2b_yagi_carrier import requirements
    from mechcad_harness.yagi_carrier import synthesize_yagi_carrier_layout

    program = compile_yagi_carrier_packaging_geometry(synthesize_yagi_carrier_layout(requirements()).spec, select_yagi_carrier_sliding_interface())
    assert program.part_id == "preliminary_yagi_carrier_packaging"
    assert 40 * 500 * 40 == 800000


def test_reference_envelopes_are_boxes_with_collision_only_identity():
    programs = reference_antenna_envelope_programs()
    assert [program.part_id for program in programs] == ["ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"]
    assert [(program.operations[0].length_mm, program.operations[0].width_mm, program.operations[0].thickness_mm) for program in programs] == [(850, 400, 60), (700, 320, 60), (600, 150, 60)]


def test_representative_assembly_preserves_nominal_y_and_reference_fixture_xz():
    from tests.unit.test_m7b2b_yagi_carrier import requirements
    from mechcad_harness.yagi_carrier import synthesize_yagi_carrier_layout

    assembly = representative_yagi_carrier_assembly(synthesize_yagi_carrier_layout(requirements()).spec, select_yagi_carrier_sliding_interface())
    placements = {item.instance_id: item.placement for item in assembly.instances}
    assert [placements[name].y_mm for name in ("antenna_0400", "antenna_0600", "antenna_1200")] == [-350, -160, 75]
    assert [placements[name].x_mm for name in ("antenna_0400", "antenna_0600", "antenna_1200")] == [-425, -350, -300]
    assert [placements[name].z_mm for name in ("antenna_0400", "antenna_0600", "antenna_1200")] == [-30, -30, -30]


def test_reference_fixture_places_envelope_geometric_centers_and_y_intervals_exactly():
    from tests.unit.test_m7b2b_yagi_carrier import requirements
    from mechcad_harness.yagi_carrier import synthesize_yagi_carrier_layout

    assembly = representative_yagi_carrier_assembly(synthesize_yagi_carrier_layout(requirements()).spec, select_yagi_carrier_sliding_interface())
    parts = {part.part_id: part.operations[0] for part in assembly.parts}
    intervals = {}
    for instance in assembly.instances:
        if not instance.instance_id.startswith("antenna_"):
            continue
        part = parts[instance.part_id]
        center = instance.placement.y_mm + part.width_mm / 2
        intervals[instance.instance_id] = (instance.placement.y_mm, instance.placement.y_mm + part.width_mm)
        assert center == {"antenna_0400": -150, "antenna_0600": 0, "antenna_1200": 150}[instance.instance_id]
        assert instance.placement.x_mm + part.length_mm / 2 == 0
        assert instance.placement.z_mm + part.thickness_mm / 2 == 0
    assert intervals == {"antenna_0400": (-350, 50), "antenna_0600": (-160, 160), "antenna_1200": (75, 225)}


def test_native_architecture_is_required_by_packaging_compiler():
    from tests.unit.test_m7b2b_yagi_carrier import requirements
    from mechcad_harness.yagi_carrier import synthesize_yagi_carrier_layout
    from mechcad_harness.yagi_sliding_interface import SlidingArchitecture

    design = select_yagi_carrier_sliding_interface().model_copy(update={"architecture": SlidingArchitecture.CUSTOM_THROUGH_SLOT})
    with pytest.raises(ValueError, match="native_extrusion_t_slot"):
        compile_yagi_carrier_packaging_geometry(synthesize_yagi_carrier_layout(requirements()).spec, design)


def test_strict_sliding_interface_section_converts_r3_selection_and_rejects_extra_fields():
    from pydantic import ValidationError
    from mechcad_harness.yagi_carrier import YagiCarrierSlidingInterfaceSection

    section = YagiCarrierSlidingInterfaceSection.from_selection(select_yagi_carrier_sliding_interface())
    assert section.architecture == "native_extrusion_t_slot"
    assert section.continuous_lateral_travel_required is True
    assert section.selection_hash == select_yagi_carrier_sliding_interface().selection_hash
    with pytest.raises(ValidationError):
        YagiCarrierSlidingInterfaceSection(**(section.model_dump() | {"unexpected": True}))


def test_carrier_proposal_persists_typed_section_through_changeset_and_reload(tmp_path):
    from tests.unit.test_m7b2b_yagi_carrier import state_with_authority
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.yagi_carrier import build_yagi_carrier_proposal

    manager = state_with_authority(tmp_path)
    before = manager._read_current("PRJ-CARRIER")
    state = manager.load_current_state("PRJ-CARRIER")
    result = YagiCarrierSynthesisService().synthesize(state, source_revision=before["revision"], source_state_hash=before["state_hash"], project_id="PRJ-CARRIER")
    proposal = build_yagi_carrier_proposal(result, project_id="PRJ-CARRIER", source_revision=before["revision"], source_state_hash=before["state_hash"], sliding_interface=select_yagi_carrier_sliding_interface())
    engine = ChangeEngine(manager, OwnershipPolicy.from_file("config/ownership.yaml"))
    applied = engine.apply_proposal("PRJ-CARRIER", proposal)
    reloaded = manager.load_revision("PRJ-CARRIER", applied.snapshot.revision)
    assert applied.snapshot.revision == before["revision"] + 1
    assert applied.snapshot.state_hash != before["state_hash"]
    assert applied.changed_paths == ("/yagi_carriers/preliminary_yagi_carrier",)
    persisted = reloaded.yagi_carriers[0]
    assert persisted["sliding_interface"]["architecture"] == "native_extrusion_t_slot"
    assert persisted["sliding_interface"]["selection_hash"] == select_yagi_carrier_sliding_interface().selection_hash
    assert YagiCarrierSynthesisService is not None
