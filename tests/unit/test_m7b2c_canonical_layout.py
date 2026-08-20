from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.yagi_collision_layout import (
    YagiCollisionLayoutSynthesisService,
    build_yagi_collision_layout_proposal,
)


def _canonical_carrier(manager):
    from mechcad_harness.yagi_carrier import YagiCarrierSynthesisService, build_yagi_carrier_proposal
    from mechcad_harness.yagi_sliding_interface import select_yagi_carrier_sliding_interface

    before = manager._read_current("PRJ-CARRIER")
    carrier_result = YagiCarrierSynthesisService().synthesize(manager.load_current_state("PRJ-CARRIER"), source_revision=before["revision"], source_state_hash=before["state_hash"], project_id="PRJ-CARRIER")
    proposal = build_yagi_carrier_proposal(carrier_result, project_id="PRJ-CARRIER", source_revision=before["revision"], source_state_hash=before["state_hash"], sliding_interface=select_yagi_carrier_sliding_interface())
    ChangeEngine(manager, OwnershipPolicy.from_file("config/ownership.yaml")).apply_proposal("PRJ-CARRIER", proposal)


def test_state_backed_layout_synthesis_proposes_typed_canonical_layout_without_direct_mutation(tmp_path):
    from tests.unit.test_m7b2b_yagi_carrier import state_with_authority

    manager = state_with_authority(tmp_path)
    _canonical_carrier(manager)
    before = manager._read_current("PRJ-CARRIER")
    state = manager.load_current_state("PRJ-CARRIER")

    result = YagiCollisionLayoutSynthesisService().synthesize(
        state,
        source_revision=before["revision"],
        source_state_hash=before["state_hash"],
        project_id="PRJ-CARRIER",
        selected_envelope_ids=("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )

    assert result.status.value == "success"
    assert result.proposal.actor == "mechcad-yagi-carrier"
    assert [operation.path for operation in result.proposal.operations] == ["/yagi_collision_layouts/preliminary_yagi_collision_layout"]
    assert state.yagi_collision_layouts == []
    assert result.spec.synthesis_hash == result.synthesis_hash
    assert result.spec.carrier_design_hash == result.carrier_design_hash


def test_layout_changeset_persists_immutable_post_application_typed_spec(tmp_path):
    from tests.unit.test_m7b2b_yagi_carrier import state_with_authority
    from mechcad_harness.yagi_collision_layout import YagiCollisionLayoutSpec

    manager = state_with_authority(tmp_path)
    _canonical_carrier(manager)
    before = manager._read_current("PRJ-CARRIER")
    result = YagiCollisionLayoutSynthesisService().synthesize(
        manager.load_current_state("PRJ-CARRIER"),
        source_revision=before["revision"],
        source_state_hash=before["state_hash"],
        project_id="PRJ-CARRIER",
        selected_envelope_ids=("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )
    applied = ChangeEngine(manager, OwnershipPolicy.from_file("config/ownership.yaml")).apply_proposal("PRJ-CARRIER", result.proposal)
    reloaded = manager.load_revision("PRJ-CARRIER", applied.snapshot.revision)
    persisted = YagiCollisionLayoutSpec.model_validate(reloaded.yagi_collision_layouts[0])

    assert applied.snapshot.revision == before["revision"] + 1
    assert applied.snapshot.state_hash != before["state_hash"]
    assert applied.changed_paths == ("/yagi_collision_layouts/preliminary_yagi_collision_layout",)
    assert persisted.synthesis_version == "yagi-collision-layout-synthesis@1.0"
    assert persisted.synthesis_hash == result.synthesis_hash
    assert [(placement.envelope_id, placement.center_y_mm, placement.relative_z_offset_mm) for placement in persisted.placements] == [
        ("ANTENNA_ENVELOPE_0400", -150.0, 0.0),
        ("ANTENNA_ENVELOPE_0600", 0.0, 60.0),
        ("ANTENNA_ENVELOPE_1200", 150.0, 0.0),
    ]


def test_layout_path_is_owned_by_yagi_carrier():
    policy = OwnershipPolicy.from_file("config/ownership.yaml")

    assert policy.owner_for("/yagi_collision_layouts/preliminary_yagi_collision_layout") == "mechcad-yagi-carrier"
