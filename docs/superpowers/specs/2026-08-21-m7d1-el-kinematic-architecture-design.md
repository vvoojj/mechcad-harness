# M7D-1 EL Kinematic Architecture Foundation

## Scope

M7D-1 adds an elevation-axis reference boundary and a helper for constructing
discrete, generic kinematic sweep requests. It does not select or embody an
elevation mechanism.

## Generic Kinematics

The existing `RevoluteAxis` remains the generic axis contract. Its finite
origin, normalized non-zero direction, and non-empty frame identity satisfy
the elevation-axis configuration requirements without parallel aliases. The
existing quaternion and `CadRigidTransform` behavior remains unchanged.

`CadKinematicSweepService` remains generic and continues to receive a single
`RevoluteAxis`. M7D-1 introduces no AZ and EL transform chain.

## Yagi EL Reference

`yagi_el_reference.py` defines a frozen, strict
`YagiELKinematicReference` with these fields:

- `source_layout_hash`
- `el_axis_height_range_mm`, fixed at `(180.0, 300.0)`
- `selected_axis_height_mm`, always `None`
- `reference_status`, fixed at `EL_AXIS_HEIGHT_PARAMETRIC`
- `adapter_version`
- `reference_hash`

The reference hash is a SHA-256 hash of the canonical JSON representation of
all fields except itself. The model validates a finite, ascending axis-height
range and rejects extra fields. It contains no motor, gearbox, bracket, riser,
bearing, load, wind, material, or manufacturing data.

## EL Sweep Helper

`create_yagi_el_sweep_reference(...)` composes existing Yagi kinematic
reference transforms with the generic EL axis and ordered discrete angles to
produce a `CadKinematicSweepRequest`. It preserves the caller's angle order
and axis identity. The caller supplies explicit moving and stationary instance
identities, avoiding any mechanical assumptions.

The helper is reference-only. It does not choose a final EL-axis height and
does not claim continuous verification; all resulting execution results retain
`continuous_sweep_verified=False` under the existing generic result contract.

## Tests

Tests are added before implementation:

- `test_m7d1_el_reference.py` verifies strict validation, the parametric
  180--300 mm range, absent selected height, deterministic hashes, source hash
  sensitivity, invalid axes, and excluded mechanical fields.
- `test_m7d1_el_sweep_reference.py` verifies the complete layout-to-reference-
  to-request flow, ordered angles, preserved axis identity, and the existing
  discrete-only result guarantee.

Existing kinematic and Yagi reference tests remain regression coverage.

## Non-Goals

M7D-1 does not create final EL structure, rotator architecture, Starlink-like
mechanism, motor sizing or selection, gears, bearings, brackets, materials,
FEA, wind analysis, manufacturing CAD, or canonical design-state changes.
