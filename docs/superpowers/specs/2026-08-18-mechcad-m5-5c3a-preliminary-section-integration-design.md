# M5.5C-3A Preliminary Section Integration Design

## Goal

Combine already-normalized material, section geometry, and optional section
warping results into deterministic preliminary mass-per-length and stiffness
envelopes, without backend calls, material lookup, or stress/strength analysis.

## Architecture

The public ToolBroker operation accepts only immutable persisted ToolResult IDs.
Its handler resolves and verifies those records, parses their persisted
normalized outputs, and constructs a pure calculator input. The pure native
calculator consumes only `TypicalMaterialPropertiesResult`,
`SectionGeometryResult`, and optional `SectionWarpingResult`; it has no access to
ToolBroker, RunStore, filesystem, `bd_materials`, `sectionproperties`, or
external objects.

```text
public source IDs
  -> immutable ToolResult resolution/integrity verification
  -> normalized MechCAD models
  -> pure native calculator
  -> PreliminarySectionEngineeringResult
  -> ToolResult / optional Evidence
```

## Inputs

Pure calculator input:

- `PreliminarySectionEngineeringCalculatorInput.material`
- `section_geometry`
- optional `section_warping`

Public ToolBroker input:

- `material_result_id`
- `section_geometry_result_id`
- optional `section_warping_result_id`

The handler resolves actual persisted ToolResults and requires each source to be
present, succeeded, immutable, hash-valid, and bound to the same project, run,
revision, and state hash. Expected producer tool names and versions are fixed:

- material: `mechcad-material-typical-properties@1.0`
- geometry: one of the accepted C-2A section geometry tools at `1.0`
- warping: one of the accepted C-2B warping tools at `1.0`

The source record retains result ID, source task ID, tool identity, project/run identity,
revision/hash, output hash, and backend provenance. These records are included
in the normalized C-3A result so they survive ToolResult/Evidence boundaries.
No caller-supplied inline
normalized result is accepted.

## Derived Values

Every output exists as a `DerivedEngineeringValue`, including unavailable
values:

- `mass_per_length`
- `axial_rigidity_ea`
- `bending_rigidity_eix`
- `bending_rigidity_eiy`
- `torsional_rigidity_gj`

Statuses are `AVAILABLE` and `UNAVAILABLE`. Unavailable values contain no
numeric values and carry an explicit reason. Available values contain finite
min/max values when the source is a range, and a representative value only when
every required source has a legitimate representative value. No midpoint is
fabricated.

Unit contract:

- density: exactly `kg/m^3`;
- elastic modulus: exactly `GPa`;
- explicit shear modulus: exactly `GPa`;
- area: `mm^2`;
- second moments: `mm^4`;
- torsion constant: `mm^4`;
- mass per length: `kg/m`;
- EA: `N`;
- EI and GJ: `N*mm^2`.

Unsupported units fail the calculation. A single native conversion helper
converts GPa to N/mm^2 using `* 1000`; no magnitude guessing is allowed.

Calculations:

```text
mass_per_length = area_mm2 * 1e-6 * density_kg_m3
EA = E_GPa * 1000 * area_mm2
EI_x = E_GPa * 1000 * ixx_mm4
EI_y = E_GPa * 1000 * iyy_mm4
GJ = G_GPa * 1000 * J_mm4
```

GJ is available only when both an explicit normalized shear modulus and a
valid supplied warping result exist. No E/Poisson-derived shear modulus is
allowed.

## Partial Results and Authority

Valid density with missing E yields available mass and unavailable EA/EI.
Valid E with missing density yields available EA/EI and unavailable mass.
Missing explicit G yields unavailable GJ with `SHEAR_MODULUS_UNAVAILABLE`.
Missing J/warping input yields unavailable GJ with
`TORSION_CONSTANT_UNAVAILABLE`.

Malformed or non-finite available values, unsupported units, source integrity
failures, and revision/run/hash mismatches fail the entire operation.

Derived values inherit the material property's authority. Current
`bd_materials` values therefore produce `TYPICAL_REFERENCE` derived values;
arithmetic never upgrades authority. Assumptions always include:

- `HOMOGENEOUS_SECTION`
- `ISOTROPIC_LINEAR_ELASTIC_PRELIMINARY`

Warnings state that catalog PLA, nylon, CFRP, or other typical data does not
represent printed-part direction, layers, infill, moisture, calibration, or
manufacturing compensation.

## Provenance

The native integration does not fabricate a `BackendProvenance`. ToolResult
backend provenance remains `None` for the integration operation. The normalized
output instead retains structured contributing source records for material,
geometry, optional warping, and the integration tool identity/version.

## Scope Exclusions

This design does not implement stress, strength, yield, safety factors,
allowables, load cases, fatigue, buckling, material selection, optimization,
manufacturing profiles, C-3B, or any external dependency.
The C-3A ToolBroker registration may execute successfully with partial derived
values, but it creates `analysis.structural` Evidence only when axial rigidity
and both bending rigidities are `AVAILABLE`. Missing mass density or explicit
shear modulus/J does not block Evidence when EA/EIx/EIy are available.
