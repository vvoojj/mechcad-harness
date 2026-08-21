import pytest

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.kinematic_sweep import CadKinematicSweepService, RevoluteAxis
from mechcad_harness.yagi_el_reference import create_yagi_el_reference
from mechcad_harness.yagi_el_sweep import (
    REFERENCE_KINEMATIC_FIXTURE_ONLY,
    create_yagi_el_sweep_reference,
    create_yagi_el_sweep_request,
)


def _layout():
    from mechcad_harness.yagi_collision_layout import synthesize_yagi_collision_layout
    from tests.unit.test_m7b2c_collision_layout import _carrier, _requirements

    return synthesize_yagi_collision_layout(
        _requirements(),
        _carrier(),
        ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    ).spec


def _axis():
    return RevoluteAxis(
        origin_x_mm=0,
        origin_y_mm=0,
        origin_z_mm=0,
        direction_x=0,
        direction_y=1,
        direction_z=0,
        frame_id="yagi_el_fixture",
    )


def test_yagi_el_sweep_adapter_preserves_hash_bound_request_order_and_fixture_axis():
    layout = _layout()
    el_reference = create_yagi_el_reference(layout)
    axis = _axis()

    adapter_reference = create_yagi_el_sweep_reference(
        layout,
        el_reference,
        source_assembly_id="assembly",
        source_assembly_hash="sha256:assembly",
        axis=axis,
        sample_angles_deg=(-45, 0, 45),
        moving_instance_ids=("ANTENNA_ENVELOPE_0400",),
        stationary_instance_ids=("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )
    request = create_yagi_el_sweep_request(
        layout,
        el_reference,
        source_assembly_id="assembly",
        source_assembly_hash="sha256:assembly",
        axis=axis,
        sample_angles_deg=(-45, 0, 45),
        moving_instance_ids=("ANTENNA_ENVELOPE_0400",),
        stationary_instance_ids=("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )

    assert adapter_reference.source_layout_hash == layout.authority_hash
    assert adapter_reference.el_reference_hash == el_reference.reference_hash
    assert adapter_reference.source_assembly_id == "assembly"
    assert adapter_reference.source_assembly_hash == "sha256:assembly"
    assert adapter_reference.source_layout_hash != adapter_reference.source_assembly_hash
    assert adapter_reference.axis == axis
    assert adapter_reference.axis_reference_status == REFERENCE_KINEMATIC_FIXTURE_ONLY
    assert request.axis == axis
    assert request.source_assembly_id == "assembly"
    assert request.sample_angles_deg == (-45.0, 0.0, 45.0)
    assert request.moving_instance_ids == ("ANTENNA_ENVELOPE_0400",)
    assert request.stationary_instance_ids == ("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200")
    assert request.source_assembly_hash == "sha256:assembly"
    assert create_yagi_el_sweep_reference(
        layout,
        el_reference,
        source_assembly_id="assembly",
        source_assembly_hash="sha256:assembly",
        axis=axis,
        sample_angles_deg=(-45, 0, 45),
        moving_instance_ids=("ANTENNA_ENVELOPE_0400",),
        stationary_instance_ids=("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    ).reference_hash == adapter_reference.reference_hash


def test_yagi_el_sweep_adapter_rejects_an_el_reference_unbound_from_layout():
    with pytest.raises(ValueError, match="layout hash"):
        create_yagi_el_sweep_reference(
            _layout(),
            create_yagi_el_reference(_layout().model_copy(update={"authority_hash": "sha256:other"})),
            source_assembly_id="assembly",
            source_assembly_hash="sha256:assembly",
            axis=_axis(),
            sample_angles_deg=(0,),
            moving_instance_ids=("ANTENNA_ENVELOPE_0400",),
            stationary_instance_ids=("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
        )


def test_yagi_el_sweep_request_preserves_assembly_hash_and_generic_validation_rejects_wrong_hash():
    layout = _layout()
    el_reference = create_yagi_el_reference(layout)
    assembly = CadAssemblyProgram(
        assembly_id="assembly",
        parts=(CadPartProgram(part_id="moving", operations=(BasePlateOperation(operation_id="moving", length_mm=1, width_mm=1, thickness_mm=1),)),),
        instances=(CadComponentInstance(instance_id="moving", part_id="moving", placement=CadRigidTransform()),),
    )
    request = create_yagi_el_sweep_request(
        layout,
        el_reference,
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        axis=_axis(),
        sample_angles_deg=(0,),
        moving_instance_ids=("moving",),
        stationary_instance_ids=("stationary",),
    )
    assert request.source_assembly_hash == assembly_hash(assembly)
    with pytest.raises(ValueError, match="source assembly hash mismatch"):
        CadKinematicSweepService().validate_source(
            request.model_copy(update={"source_assembly_hash": "sha256:wrong", "request_hash": "pending"}),
            assembly,
        )
