# M7D-2 EL Kinematic Sweep Integration

## Scope

M7D-2 adds a thin Yagi domain adapter over the existing M7C-1 generic
kinematic sweep and validates it with a transient, exact FreeCAD fixture. It
does not select or embody an elevation mechanism.

## Adapter Boundary

`yagi_el_sweep.py` accepts a `YagiCollisionLayoutSpec`, its bound
`YagiELKinematicReference`, a caller-supplied generic `RevoluteAxis`, ordered
moving and stationary envelope identities, and ordered discrete angles.

It validates that the EL reference is bound to the layout authority hash,
retains the fixed parametric EL height range of 180.0--300.0 mm, requires no
selected height, and returns a normal `CadKinematicSweepRequest`.

The caller-supplied axis is represented only as
`REFERENCE_KINEMATIC_FIXTURE_ONLY`. It is not a selected production axis and
does not establish any mechanical axis location.

The adapter records deterministic canonical hash-bound input data but does not
modify `RevoluteAxis`, `CadKinematicSweepRequest`, `CadKinematicSweepService`,
the transient analysis service, or the FreeCAD provider.

## Live Fixture

A single live test creates simple transient 10 mm reference solids and sends
the request through:

```text
Yagi layout -> EL reference -> EL sweep adapter -> generic sweep service
-> transient analysis service -> FreeCAD transient measurement provider
```

The fixture uses one moving group and one stationary group, with discrete
angles producing positive clearance, touching, and interference. It verifies
ordered samples and pairs, transformed assembly identities, deterministic
result hashing, exact FreeCAD measurements, collision aggregation, and the
existing `continuous_sweep_verified=False` behavior.

Temporary execution is verified by forbidding `ArtifactStore`; the test does
not instantiate or mutate `DesignState`, `ChangeSet`, or canonical artifacts.

## Non-Goals

M7D-2 does not add EL-specific generic kinematics, an AZ/EL chain, a final EL
axis, height selection, rotator architecture, motors, gears, bearings,
brackets, risers, materials, structural values, loads, wind analysis, FEA,
manufacturing CAD, `DesignState` mutation, or `ChangeSet` creation.
