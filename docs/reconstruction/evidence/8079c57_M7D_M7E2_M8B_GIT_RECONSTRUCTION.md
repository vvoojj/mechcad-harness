# 8079c57 M7D, M7E-2, And M8B Forensic Reconstruction

This document classifies the logical work delivered by commit
`8079c5764d377df3b182f8ffc72a306a186b57af`. It is historical reconstruction,
not a statement of the current production capability baseline.

## Verdict

```text
COMMIT_EXISTENCE: PROVEN
DELIVERABLE_TYPE: BUNDLED_IMPLEMENTATION_AND_ARTIFACTS
IMPLEMENTATION_STATUS: PRESENT_WITH_BOUNDARY_CAVEATS
SPEC_CONFORMANCE_STATUS: PARTIAL_BY_SCOPE
HISTORICAL_EXECUTION_EVIDENCE: PARTIAL
TARGET_WIDE_ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
```

## Boundary And Contents

The target is the direct child of `9ab9e48b8bc54202d5fddd5edc85e7f8c7c3b903`
and has tree `e158c442508122d03761f0dbdf6b1494125b28a0`. Its subject is
`feat: complete M8B-2 production vertical slice`, but the commit changes 187
paths and bundles M7B-2C repair work, M7D-1, M7D-2, M7E-2, M8B-1, M8B-2,
cross-cutting provenance changes, historical documentation, and workspace
artifacts.

The target has no tag, Git note, or single target-wide acceptance report.
Later reports and current-branch behavior are not projected backward as
evidence for this commit.

## Logical Milestones

| Scope | Delivered boundary | Target status | Record decision |
| --- | --- | --- | --- |
| M7B-2C repair | Adds `DesignState.yagi_collision_layouts`, ownership for `/yagi_collision_layouts/*`, and `collision_resolved_yagi_carrier_assembly(...)` | Implementation repair present; rerun evidence not retained | Append to the existing M7B-2C record, not a new milestone |
| M7D-1 | Adds strict parametric EL reference and generic EL sweep-reference construction | Implementation present; no retained execution report | Separate record |
| M7D-2 | Adds Yagi EL adapter over generic revolute-axis, transient-analysis, and FreeCAD measurement services | Implementation present; live test is runtime-gated | Separate record |
| M7E-2 | Adds preliminary AZ/EL FreeCAD concept and three workspace artifacts | Preliminary only; explicitly not verified or ready | Separate documentary record, not acceptance |
| M8B-1 | Adds production composition root, source/run bindings, identity policy, tool policy, and narrow project locking | Focused tests reported passing under Python 3.14; no Python 3.11 evidence | Separate record |
| M8B-2 | Adds the production transmission round-trip entry point over the M8B-1 graph | Focused integration and regressions reported passing under Python 3.14 | Separate record |

M8B-1 and M8B-2 share one commit boundary but remain distinct architectural
milestones, just as earlier shared-boundary milestones do.

## M7B-2C Repair

Direct changes are in:

- `src/mechcad_harness/models/design.py`
- `config/ownership.yaml`
- `src/mechcad_harness/yagi_carrier_packaging.py`

The repair supplies the three missing boundaries identified in the predecessor
record. The builder creates deterministic reference envelope parts and
placements from layout placements. It does not introduce a general collision
solver or a final mechanical carrier.

The repair makes the predecessor's live-test import and its state/ownership
expectations resolvable. No target-era rerun transcript, CI result, or repair
acceptance record is retained. This is a successor repair to the existing
M7B-2C boundary, not a new M7B-2C delivery.

## M7D-1

Implementation and tests:

- `src/mechcad_harness/yagi_el_reference.py`
- `tests/unit/test_m7d1_el_reference.py`
- `tests/unit/test_m7d1_el_sweep_reference.py`
- M7D-1 plan and design specification under `docs/superpowers/`

The implementation provides a strict `YagiELKinematicReference` with a fixed
axis-height range of `(180.0, 300.0)`, no selected axis height, deterministic
identity hashing, and a helper that preserves caller-supplied axis, angle, and
instance ordering when constructing a generic
`CadKinematicSweepRequest`.

The scope excludes motor, gearbox, bearing, bracket, load, wind, material,
manufacturing, structural, and mechanism-embodiment semantics. Unit tests
cover the strict fields, invalid axes, identity behavior, and ordering.

No target-era test output or formal M7D-1 acceptance marker is retained.

## M7D-2

Implementation and tests:

- `src/mechcad_harness/yagi_el_sweep.py`
- `tests/unit/test_m7d2_el_sweep_adapter.py`
- `tests/integration/test_m7d2_el_kinematic_sweep_live.py`
- M7D-2 plan and design specification under `docs/superpowers/`

The adapter validates the EL-reference layout binding, records reference,
layout, assembly, and request identities (the axis is included in the adapter
and request canonical hashes, not persisted as a distinct axis hash), marks the fixture axis as
`REFERENCE_KINEMATIC_FIXTURE_ONLY`, and delegates to generic kinematic and
transient-analysis services. The live test uses exact FreeCAD
`common().Volume` and `distToShape()` classifications when FreeCAD is
available.

The implementation remains discrete only and does not create canonical
artifacts or mutate `DesignState`. The live test is FreeCAD-gated. No retained
target-era live execution output or M7D-2 acceptance record exists.

## M7E-2

Design records:

- `docs/superpowers/plans/2026-08-21-m7e2-preliminary-az-el-rotator-concept.md`
- `docs/superpowers/specs/2026-08-21-m7e2-preliminary-az-el-rotator-concept.md`

Workspace artifacts:

- `workspace/m7e2_preliminary_az_el_rotator/M7E2_Preliminary_AZ_EL_Rotator.FCStd`
- `workspace/m7e2_preliminary_az_el_rotator/M7E2_Preliminary_AZ_EL_Rotator.step`
- `workspace/m7e2_preliminary_az_el_rotator/M7E2_Preliminary_AZ_EL_Rotator.20260821-024957.FCBak`

The concept uses the explicit statuses `PRELIMINARY_CONCEPT_ONLY`,
`NOT_VERIFIED`, and `NOT_READY`. It contains grouped AZ/EL/Yagi placeholder
geometry and does not establish a final mechanism, manufacturing approval,
structural result, or canonical `DesignState` mutation.

The artifacts prove committed presence and contain self-described concept
metadata/checks, including status, export, and discrete-check fields. No
independent test, reload transcript, or acceptance result is retained.

## M8B-1

Primary implementation:

- `src/mechcad_harness/application.py`
- `src/mechcad_harness/runs/models.py`
- `src/mechcad_harness/runs/controller.py`
- `src/mechcad_harness/state/manager.py`
- `src/mechcad_harness/agents/registry.py`
- `src/mechcad_harness/agents/gateway.py`
- `src/mechcad_harness/tools/broker.py`
- `tests/unit/test_production_application.py`
- `tests/unit/test_runs.py`

The composition root owns the service graph and produces immutable
`ProductionStateBinding` and `ProductionRunBinding` values. It fixes the
trusted transmission identity to `mechcad-transmission@1.0`, validates the
expected revision and state hash, enforces exact tool permissions, and closes
the revision/run creation race with a narrow per-project synchronization
guard.

The design does not add a general workflow executor, a second state-mutation
API, or an application-level recovery subsystem. The injected agent adapter is
the external runtime boundary.

Retained SDD reports record a final focused application/run result of 51
passed and state/change regressions of 15 passed. These results were obtained
under Python 3.14. Python 3.11 was unavailable, and no target-era full-suite
result is retained.

## M8B-2

Primary implementation and test:

- `src/mechcad_harness/application.py`
- `tests/integration/test_m8b2_production_vertical_slice.py`
- M8B-2 plan and design specification under `docs/superpowers/`

`ProductionApplication.run_transmission_round_trip(...)` calls `create_run()`
once, creates one fixed task, uses the exact
`mechcad-calc-torque@1.0` permission, and delegates execution to the existing
`TransmissionToolRoundTripCoordinator`.

The path produces the expected tool call/result and Evidence flow, including
Evidence-grounded recovery. It does not fabricate a proposal, revise
canonical state, or introduce a second recovery API.

Retained review evidence reports one focused integration test passed, 24 M8B-1
application tests passed, and 76 affected M6B/run/tool/dependency regressions
passed under Python 3.14.6. This is focused evidence, not a full target-wide
acceptance run.

## Cross-Cutting Changes

The target also changes artifact and backend provenance, including
`build123d_provenance` and optional FreeCAD backend provenance fields. These
changes have no independent milestone plan, specification, or acceptance
record in the target tree.

They should be recorded as cross-cutting provenance hardening attached to this
commit. They must not be relabeled as M9 acceptance. Later M9 acceptance uses
newer production paths and live runtime evidence.

The commit also carries historical M6B/M7C documentation and older workspace
artifacts. Their presence does not create new M6B or M7C delivery boundaries at
this commit.

## Successor Relationship

`6c6f46c` follows with M8C source-bound CAD compilation, trusted imported STEP
components, mixed assemblies, and the production kinematic entry point. It
uses the M8B production composition as a foundation.

`a67cee3` later provides M9 live acceptance using FreeCAD 1.1.3 and real
geometry execution. `89b1d75` later extends that chain into M10 motion-system
acceptance. Those records validate successor environments and are not evidence
that M7D, M7E-2, or the target commit itself passed live acceptance.

## Reconstruction Conclusion

The target contains real implementation for M7D-1, M7D-2, M8B-1, and M8B-2,
plus a preliminary M7E-2 artifact package and a concrete repair to M7B-2C.
M8B has the strongest retained execution evidence. M7D and M7E-2 have no
retained target-era acceptance evidence, and M7E-2 remains explicitly
preliminary.

The correct historical record is a set of separate milestone entries linked
to this shared Git boundary, with M7B-2C documented as a repair rather than
reclassified as a new milestone.
