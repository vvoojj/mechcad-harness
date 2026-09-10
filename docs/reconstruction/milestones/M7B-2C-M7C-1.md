# M7B-2C / M7C-1 - Collision Layout And Discrete Kinematics

## Status

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: BUNDLED_IMPLEMENTATION
IMPLEMENTATION_STATUS: PARTIAL_UNRUNNABLE
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
```

## Git Boundary

The bundle is `9ab9e48b8bc54202d5fddd5edc85e7f8c7c3b903`, the direct child of
M7B-2B/R2-R4 `3f7bbc76f6031d1374b0b476a4d58da1dce37dfd` and direct parent of
`8079c5764d377df3b182f8ffc72a306a186b57af`. It changes 14 files with 1,576
insertions.

The source/test naming supports two bundled labels: M7B-2C collision-layout
synthesis and M7C-1 transient FreeCAD measurement/discrete kinematic sweep.

## Historical Role And Result

M7B-2C adds deterministic two-/three-envelope collision layout, overlap and
clearance calculations, lateral adjustment, vertical stagger, hash-bound
authority/carrier/source identity, proposal generation, and explicit non-final
statuses. M7C-1 adds normalized revolute axes, quaternion moving transforms,
ordered pair inventory, transient transformed assemblies, temporary FreeCAD
compilation, exact `common().Volume` / `distToShape()` measurement, deterministic
request/result hashes, and ordered aggregate classification.

M7C-1 is deliberately discrete only: `continuous_sweep_verified=False`.

## Tests And Execution Evidence

M7C-1 tests reproduce `20 passed, 4 skipped`; M7B-2C unit tests reproduce `24
passed, 3 failed`. Combined focused accounting is `44 passed, 3 failed` plus
the four M7C-1 skips. The M7B-2C live test fails during collection because
`collision_resolved_yagi_carrier_assembly` is absent.

The normal full-suite collection fails for the same missing successor symbol,
`collision_resolved_yagi_carrier_assembly`;
ignoring the failing live file produces `510 passed, 37 skipped, 4 failed`.
The four failures include the inherited py_gearworks availability assertion.
FreeCAD was unavailable, so no M7C-1 live measurement ran. No durable sweep
result or M7B-2C/M7C-1-specific generated artifact, completion report, audit, acceptance marker, tag,
or Git note is retained.

## Material Deviations

- `DesignState.yagi_collision_layouts` is absent.
- Ownership for `/yagi_collision_layouts/*` is absent.
- The M7B-2C live test imports the absent
  `collision_resolved_yagi_carrier_assembly`.
- The candidate is therefore not a runnable M7B-2C closure; `8079c57` repairs
  these three gaps.

## Successor Relationship

`8079c57` preserves M7C-1 and adds the missing collision-layout state field,
ownership rule, and collision-resolved assembly builder, alongside broader M7D
and M8B-2 work. Later audit numbers belong to that successor environment and
are not candidate acceptance evidence.

## Reconstruction Conclusion

This is a proven bundled implementation of collision-layout and discrete
kinematic concepts, but M7B-2C is incomplete at its own boundary and M7C-1 has
no live FreeCAD evidence or retained formal acceptance.

See [detailed Git evidence](../evidence/M7B-2C-M7C-1_GIT_RECONSTRUCTION.md).
