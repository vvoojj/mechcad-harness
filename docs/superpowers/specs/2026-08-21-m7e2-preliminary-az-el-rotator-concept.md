# M7E-2 Preliminary AZ/EL Rotator FreeCAD Concept Model

## Scope

Create a deterministic FreeCAD packaging and kinematic concept assembly for a
two-axis antenna rotator. The model is preliminary concept geometry only and
is not a manufacturing or structural design.

## Assembly Structure

The document contains a root `Assembly` group with these deterministic child
groups:

- `Base`
- `AZ_Rotator`
- `EL_Frame`
- `Yagi_Carrier`
- `Motor_Placeholders`

The groups contain named Part primitives for the ground base, circular AZ
platform, axis cylinders, support plates, EL supports, carrier envelope,
T-slot concept, adjustable mounting concept, and AZ/EL motor envelope boxes.

## Kinematic Concept

The AZ axis is vertical and represented by a revolute-axis cylinder. Concept
placements are checked at 0 and 360 degrees. The EL axis is horizontal and
represented by a cylinder between side supports. Concept placements are
checked at -90, 0, and +90 degrees. These are discrete packaging checks only.

No final axis height, motor, gearbox, bearing, bracket, riser, load path,
structural approval, wind calculation, FEA result, manufacturing dimension,
or final clamp is asserted.

## Metadata

The root and concept objects expose these properties:

- `DesignStatus = PRELIMINARY_CONCEPT_ONLY`
- `StructuralStatus = NOT_VERIFIED`
- `ManufacturingStatus = NOT_READY`

## Deliverables and Checks

- Save an FCStd assembly in the repository workspace.
- Export a STEP assembly when supported by the installed FreeCAD environment.
- Reload the FCStd file and verify the deterministic assembly tree.
- Verify conceptual AZ and EL placements and check for obvious self-collision.
