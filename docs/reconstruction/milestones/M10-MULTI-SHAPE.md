# M10 Multi-Shape Transient Geometry Closure

## Status

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: TRUST_BOUNDARY_CORRECTION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: VERIFIED
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CONSISTENCY_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
```

## Git Boundary

This narrow closure is part of `28ac193c21b8046973c7e53c304541eed88801aa`,
after M11-6 documentation reference `52e60e9`. It changes transient imported
measurement to aggregate all top-level STEP shapes and adds targeted tests.
It is not a new candidate, synthesis, M12, or general kinematic milestone.

## Historical Result

Imported STEP transient measurement, radial bounds, and local extents now use a
`Part.makeCompound(...)` of all top-level shapes; generated single-object parts
retain first-object behavior. A two-solid trusted fixture demonstrates that an
obstacle intersecting only the second solid is detected, with persisted and
transient realizations agreeing within `1e-6` relative tolerance.

The accepted closure is narrow latent-input consistency. It does not alter the
`ImportedCadComponent` schema or add new motion semantics.

## Evidence

The retained closure report records 3 static unit tests, 7 live integration
tests, and a full `1,390 passed, 25 skipped, 0 failed, 0 errors` result. The
workspace artifacts are temporary; no new durable M10 artifact is committed.

## Reconstruction Conclusion

This is a verified narrow correction to M10 imported multishape measurement,
not a new candidate or general kinematics capability.

See [detailed Git evidence](../evidence/M10-MULTI-SHAPE_GIT_RECONSTRUCTION.md).
