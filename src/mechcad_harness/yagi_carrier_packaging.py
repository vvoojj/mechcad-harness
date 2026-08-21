from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.yagi_sliding_interface import SlidingArchitecture


CARRIER_PACKAGING_CROSS_SECTION_MM = (40, 40)


def compile_yagi_carrier_packaging_geometry(spec, sliding_interface) -> CadPartProgram:
    if sliding_interface.architecture is not SlidingArchitecture.NATIVE_EXTRUSION_T_SLOT:
        raise ValueError("preliminary packaging compiler requires native_extrusion_t_slot architecture")
    if not sliding_interface.preliminary_packaging_cad_ready or sliding_interface.final_profile_selected:
        raise ValueError("preliminary packaging geometry policy is unresolved")
    cross_x, cross_z = CARRIER_PACKAGING_CROSS_SECTION_MM
    return CadPartProgram(
        part_id=f"{spec.carrier_id}_packaging",
        operations=(BasePlateOperation(operation_id="carrier_packaging_envelope", length_mm=cross_x, width_mm=spec.carrier_length_mm, thickness_mm=cross_z),),
    )


def reference_antenna_envelope_programs() -> tuple[CadPartProgram, ...]:
    dimensions = (
        ("ANTENNA_ENVELOPE_0400", 850, 400, 60),
        ("ANTENNA_ENVELOPE_0600", 700, 320, 60),
        ("ANTENNA_ENVELOPE_1200", 600, 150, 60),
    )
    return tuple(
        CadPartProgram(part_id=part_id, operations=(BasePlateOperation(operation_id="reference_collision_envelope", length_mm=length, width_mm=width, thickness_mm=depth),))
        for part_id, length, width, depth in dimensions
    )


def representative_yagi_carrier_assembly(spec, sliding_interface) -> CadAssemblyProgram:
    carrier = compile_yagi_carrier_packaging_geometry(spec, sliding_interface)
    envelopes = reference_antenna_envelope_programs()
    return CadAssemblyProgram(
        assembly_id="preliminary_yagi_carrier_nominal_reference_fixture",
        parts=(carrier, *envelopes),
        instances=(
            CadComponentInstance(instance_id="carrier", part_id=carrier.part_id, placement=CadRigidTransform(x_mm=-20, y_mm=-250, z_mm=-40)),
            CadComponentInstance(instance_id="antenna_0400", part_id="ANTENNA_ENVELOPE_0400", placement=CadRigidTransform(x_mm=-425, y_mm=-350, z_mm=-30)),
            CadComponentInstance(instance_id="antenna_0600", part_id="ANTENNA_ENVELOPE_0600", placement=CadRigidTransform(x_mm=-350, y_mm=-160, z_mm=-30)),
            CadComponentInstance(instance_id="antenna_1200", part_id="ANTENNA_ENVELOPE_1200", placement=CadRigidTransform(x_mm=-300, y_mm=75, z_mm=-30)),
        ),
    )


def collision_resolved_yagi_carrier_assembly(spec, sliding_interface, layout) -> CadAssemblyProgram:
    carrier = compile_yagi_carrier_packaging_geometry(spec, sliding_interface)
    dimensions = {
        "ANTENNA_ENVELOPE_0400": (850, 400, 60),
        "ANTENNA_ENVELOPE_0600": (700, 320, 60),
        "ANTENNA_ENVELOPE_1200": (600, 150, 60),
        "ANTENNA_ENVELOPE_3300": (500, 120, 60),
        "ANTENNA_ENVELOPE_5800": (300, 150, 80),
    }
    by_id = {
        part_id: CadPartProgram(part_id=part_id, operations=(BasePlateOperation(operation_id="reference_collision_envelope", length_mm=length, width_mm=width, thickness_mm=depth),))
        for part_id, (length, width, depth) in dimensions.items()
    }
    envelope_parts = tuple(by_id[placement.envelope_id] for placement in layout.placements)
    instances = [CadComponentInstance(instance_id="carrier", part_id=carrier.part_id, placement=CadRigidTransform(x_mm=-20, y_mm=-250, z_mm=-40))]
    for placement in layout.placements:
        part = by_id[placement.envelope_id].operations[0]
        instances.append(
            CadComponentInstance(
                instance_id=f"antenna_{placement.envelope_id.removeprefix('ANTENNA_ENVELOPE_').lower()}",
                part_id=placement.envelope_id,
                placement=CadRigidTransform(
                    x_mm=-part.length_mm / 2,
                    y_mm=placement.center_y_mm - part.width_mm / 2,
                    z_mm=placement.relative_z_offset_mm - part.thickness_mm / 2,
                ),
            )
        )
    return CadAssemblyProgram(
        assembly_id=f"{layout.layout_id}_reference_fixture",
        parts=(carrier, *envelope_parts),
        instances=tuple(instances),
    )
