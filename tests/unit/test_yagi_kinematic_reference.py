import pytest
from pydantic import ValidationError

from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.yagi_kinematic_reference import (
    REFERENCE_KINEMATIC_FIXTURE_ONLY,
    YagiKinematicReferenceModel,
    YagiKinematicReferencePlacement,
    create_yagi_kinematic_reference,
)


def _layout():
    from tests.unit.test_m7b2c_collision_layout import _carrier, _requirements
    from mechcad_harness.yagi_collision_layout import synthesize_yagi_collision_layout

    return synthesize_yagi_collision_layout(
        _requirements(),
        _carrier(),
        ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    ).spec


def test_create_yagi_kinematic_reference_preserves_placement_order_as_fixture_only_transforms():
    layout = _layout()

    reference = create_yagi_kinematic_reference(layout)

    assert isinstance(reference, YagiKinematicReferenceModel)
    assert [placement.envelope_id for placement in reference.placements] == list(layout.selected_envelope_ids)
    assert [(placement.transform.x_mm, placement.transform.y_mm, placement.transform.z_mm) for placement in reference.placements] == [
        (0.0, layout_placement.center_y_mm, layout_placement.relative_z_offset_mm)
        for layout_placement in layout.placements
    ]
    assert all(placement.x_reference_status == REFERENCE_KINEMATIC_FIXTURE_ONLY for placement in reference.placements)


def test_yagi_kinematic_reference_hash_replays_and_changes_with_ordered_placement_data():
    layout = _layout()
    first = create_yagi_kinematic_reference(layout)
    replay = create_yagi_kinematic_reference(layout)
    changed = YagiKinematicReferenceModel(
        source_layout_hash=first.source_layout_hash,
        synthesis_hash=first.synthesis_hash,
        placements=(
            YagiKinematicReferencePlacement(
                envelope_id=first.placements[0].envelope_id,
                transform=CadRigidTransform(x_mm=0, y_mm=first.placements[0].transform.y_mm + 1, z_mm=first.placements[0].transform.z_mm),
            ),
            *first.placements[1:],
        ),
    )

    assert first.reference_hash == replay.reference_hash
    assert changed.reference_hash != first.reference_hash
    assert create_yagi_kinematic_reference(layout.model_copy(update={"synthesis_hash": "sha256:changed"})).reference_hash != first.reference_hash


def test_yagi_kinematic_reference_models_reject_extras_and_exclude_final_mechanism_fields():
    placement = {
        "envelope_id": "ANTENNA_ENVELOPE_0400",
        "transform": CadRigidTransform(),
        "x_reference_status": REFERENCE_KINEMATIC_FIXTURE_ONLY,
    }
    with pytest.raises(ValidationError, match="extra_forbidden"):
        YagiKinematicReferencePlacement(**(placement | {"final_x_mm": 12}))
    with pytest.raises(ValidationError, match="extra_forbidden"):
        YagiKinematicReferenceModel(
            source_layout_hash="sha256:layout",
            synthesis_hash="sha256:synthesis",
            placements=(YagiKinematicReferencePlacement(**placement),),
            reference_hash="sha256:reference",
            el_axis_height=200,
        )
    reference = create_yagi_kinematic_reference(_layout())
    for name in ("final_x_mm", "el_axis_height", "riser_height", "clamp_dimensions", "structural_load", "wind_data"):
        assert not hasattr(reference, name)
