import itertools

import pytest

from mechcad_harness.yagi_collision_layout import (
    CollisionLayoutClassification,
    YagiCollisionLayoutStatus,
    synthesize_yagi_collision_layout,
)


def _requirements():
    from tests.unit.test_m7b2b_yagi_carrier import requirements

    return requirements()


def _carrier():
    from mechcad_harness.yagi_carrier import synthesize_yagi_carrier_layout

    return synthesize_yagi_carrier_layout(_requirements()).spec


def test_rejects_unknown_duplicate_and_invalid_selected_envelope_counts():
    with pytest.raises(ValueError, match="unknown"):
        synthesize_yagi_collision_layout(_requirements(), _carrier(), ("ANTENNA_ENVELOPE_0400", "UNKNOWN"))
    with pytest.raises(ValueError, match="duplicate"):
        synthesize_yagi_collision_layout(_requirements(), _carrier(), ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0400"))
    with pytest.raises(ValueError, match="2 or 3"):
        synthesize_yagi_collision_layout(_requirements(), _carrier(), ("ANTENNA_ENVELOPE_0400",))
    with pytest.raises(ValueError, match="2 or 3"):
        synthesize_yagi_collision_layout(
            _requirements(),
            _carrier(),
            ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200", "ANTENNA_ENVELOPE_3300"),
        )


def test_two_antenna_layout_is_symmetric_lateral_only_and_has_no_x_position():
    result = synthesize_yagi_collision_layout(_requirements(), _carrier(), ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600"))

    assert result.status is YagiCollisionLayoutStatus.SUCCESS
    assert result.spec.classification is CollisionLayoutClassification.NO_INTERFERENCE_TOUCHING
    assert [placement.center_y_mm for placement in result.spec.placements] == [-180.0, 180.0]
    assert [placement.relative_z_offset_mm for placement in result.spec.placements] == [0.0, 0.0]
    assert result.spec.strategies == ("lateral_adjustment",)
    assert result.spec.final_antenna_x_positions_selected is False
    assert all(placement.reference_fixture_x_center_mm is None for placement in result.spec.placements)
    assert result.spec.touching_pairs == (("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600"),)


def test_representative_three_antenna_layout_derives_center_vertical_stagger():
    result = synthesize_yagi_collision_layout(
        _requirements(),
        _carrier(),
        ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )

    assert result.status is YagiCollisionLayoutStatus.SUCCESS
    assert result.spec.classification is CollisionLayoutClassification.NO_INTERFERENCE_TOUCHING
    placements = {placement.envelope_id: placement for placement in result.spec.placements}
    assert (placements["ANTENNA_ENVELOPE_0400"].lane, placements["ANTENNA_ENVELOPE_0400"].center_y_mm, placements["ANTENNA_ENVELOPE_0400"].relative_z_offset_mm) == ("left", -150.0, 0.0)
    assert (placements["ANTENNA_ENVELOPE_0600"].lane, placements["ANTENNA_ENVELOPE_0600"].center_y_mm, placements["ANTENNA_ENVELOPE_0600"].relative_z_offset_mm) == ("center", 0.0, 60.0)
    assert (placements["ANTENNA_ENVELOPE_1200"].lane, placements["ANTENNA_ENVELOPE_1200"].center_y_mm, placements["ANTENNA_ENVELOPE_1200"].relative_z_offset_mm) == ("right", 150.0, 0.0)
    assert result.spec.strategies == ("nominal", "vertical_stagger")
    assert result.spec.touching_pairs == (("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600"), ("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"))
    assert result.spec.minimum_pair_clearance_mm == 0.0
    assert result.spec.vertical_stagger_mechanical_embodiment == "not_designed"


def test_width_sort_uses_canonical_id_tie_break_and_hash_is_deterministic_and_source_bound():
    first = synthesize_yagi_collision_layout(_requirements(), _carrier(), ("ANTENNA_ENVELOPE_5800", "ANTENNA_ENVELOPE_1200", "ANTENNA_ENVELOPE_3300"), source_revision=2, source_state_hash="sha256:one")
    replay = synthesize_yagi_collision_layout(_requirements(), _carrier(), ("ANTENNA_ENVELOPE_5800", "ANTENNA_ENVELOPE_1200", "ANTENNA_ENVELOPE_3300"), source_revision=2, source_state_hash="sha256:one")
    changed = synthesize_yagi_collision_layout(_requirements(), _carrier(), ("ANTENNA_ENVELOPE_5800", "ANTENNA_ENVELOPE_1200", "ANTENNA_ENVELOPE_3300"), source_revision=3, source_state_hash="sha256:two")

    assert [placement.envelope_id for placement in first.spec.placements] == ["ANTENNA_ENVELOPE_1200", "ANTENNA_ENVELOPE_5800", "ANTENNA_ENVELOPE_3300"]
    assert first.synthesis_hash == replay.synthesis_hash
    assert first.synthesis_hash != changed.synthesis_hash


@pytest.mark.parametrize("selected", tuple(itertools.combinations(("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200", "ANTENNA_ENVELOPE_3300", "ANTENNA_ENVELOPE_5800"), 2)) + tuple(itertools.combinations(("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200", "ANTENNA_ENVELOPE_3300", "ANTENNA_ENVELOPE_5800"), 3)))
def test_every_current_two_or_three_envelope_combination_is_deterministic_and_non_interfering(selected):
    result = synthesize_yagi_collision_layout(_requirements(), _carrier(), selected)

    assert result.status is YagiCollisionLayoutStatus.SUCCESS
    assert all(-220 <= placement.center_y_mm <= 220 for placement in result.spec.placements)
    assert all(placement.reference_fixture_x_center_mm is None for placement in result.spec.placements)
    assert "longitudinal_stagger" not in result.spec.strategies
    assert "polarization_rotation" not in result.spec.strategies
    assert all(pair.common_volume_mm3 == 0 for pair in result.spec.pair_results)
