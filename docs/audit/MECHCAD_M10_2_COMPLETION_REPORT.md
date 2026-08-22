# M10-2 Completion Report — Generic Multi-Joint Kinematic Model

## Scope

M10-2 introduces the generic multi-joint deterministic forward-kinematics
foundation required for later M10 work (M10-3 multi-joint exact discrete
collision sweep). It implements at least two dependent revolute joints in series
in a rooted acyclic tree (forest) and evaluates an explicit configuration into
instance world transforms and a transformed `CadAssemblyProgram`, with separate
deterministic identities.

## Design Decisions

| Decision | Selection | Rationale |
|---|---|---|
| Topology | Rooted acyclic tree (forest) | Branching allowed; closed loops / constraint solving out of scope |
| Joint type | Revolute only (`KinematicJointKind.REVOLUTE`) | Extensible model; only revolute in M10-2 |
| Axis frame | Parent instance local frame | Joint axis moves naturally with parent |
| Composition | LEFT-TO-RIGHT `compose(A, B) = A ∘ B` | `rotation: A.q * B.q`; `translation: A.t + rot(A.q, B.t)` |
| FK equation | `T_world_child(q) = T_world_parent(q) ∘ T_joint(q) ∘ T_parent_child_home` | `T_joint(q) = Translate(p) ∘ Rotate(u,q) ∘ Translate(-p)` |
| Home config | Derived from source placements | At q=0 reproduces source placement |
| Quaternion helpers | Reused from `kinematic_sweep.py` | No second implementation of `_quaternion_multiply` / `_rotation_quaternion` / `_rotate_vector` |
| Identity separation | `model_hash` / `configuration_hash` / `transformed_assembly_hash` / `result_hash` | Raw commanded angles preserved in `configuration_hash`; geometric normalization via `_rotation_quaternion(angle % 360)` |

## Implementation

| File | Change |
|---|---|
| `src/mechcad_harness/multi_joint_kinematics.py` | New — transform helpers, models (`RevoluteJointModel`, `KinematicModel`, `JointConfiguration`, `KinematicForwardKinematicsResult`), topology validation, `MultiJointKinematicsService.evaluate()` |
| `src/mechcad_harness/application.py` | Modified — added `evaluate_multi_joint_configuration()` + deterministic provenance evidence helper |
| `tests/unit/test_multi_joint_kinematics.py` | New — 53 unit tests |
| `docs/superpowers/specs/2026-08-22-m10-2-generic-multi-joint-kinematic-model.md` | New — design spec (+ Final Disposition) |
| `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md` | Modified — M10-2 row + multi-axis chain row + traceability |
| `docs/architecture/MECHCAD_RUNTIME_FLOW.md` | Modified — M3 multi-joint FK flow section |
| `docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md` | Modified — GenericMultiJointKinematics contract row |
| `AGENTS.md` | Modified — baseline M8+M9+M10-1+M10-2, acceptance marker, limitation update |
| `docs/audit/MECHCAD_M10_2_COMPLETION_REPORT.md` | New — this report |

## Identity Verification

| Identity | Covers | Confirmed |
|---|---|---|
| `model_hash` | model_id, evaluator_version, per-joint (id, kind, parent/child, axis origin/direction, limits) | Deterministic; sorted by joint_id |
| `configuration_hash` | model_id + sorted (joint_id, raw angle) | 0°/360°/720° differ; order-independent |
| `transformed_assembly_hash` | Reuses `assembly_hash()` over transformed `CadAssemblyProgram` | Distinct from source/model/config hashes |
| `result_hash` | version + source + model + config + transformed assembly + joint states + transforms | Stable across runs |

## Topology Validation (Fail Closed)

All enforced and unit-tested:

- Unique joint IDs (raised both at model construction and topology build)
- Parent / child instance IDs exist in assembly
- Parent != child
- Child has at most one articulated parent
- No cycles (deterministic BFS revisit detection; runs before reachability)
- All articulated nodes reachable from deterministic roots
- Deterministic root identification (instances not a child of any joint)
- Deterministic BFS traversal (sorted instance IDs, sorted joint IDs)

## Known Analytic Pose (Determinism Cross-Check)

For the three-body chain `base@(0,0,0)`, `link-1@(30,0,0)`, `link-2@(80,0,0)`
with both joints revolute about Z:

| Config | link-1 | link-2 |
|---|---|---|
| q1=0, q2=0 | (30, 0, 0) | (80, 0, 0) (== source) |
| q1=90, q2=0 | (0, 30, 0) | (0, 80, 0) |
| q1=0, q2=90 | (30, 0, 0) | (60, 20, 0) |
| q1=90, q2=90 | (0, 30, 0) | (-20, 60, 0) |

The q2 rotation is about the joint axis origin `(30,0,0)` expressed in the
parent (link-1) local frame; when the parent rotates, the axis origin moves with
it. The numeric results follow directly from the FK equation and were asserted
to `abs=1e-9`.

## Production Entrypoint

`ProductionApplication.evaluate_multi_joint_configuration()`:

- Validates the source `DesignState` binding (revision / state-hash) fails closed
- Constructs `MultiJointKinematicsService` and evaluates
- Records deterministic provenance `Evidence` (`kind=
  analysis.multi_joint_kinematics`, id `EVD-MJKIN-<sha256[:24]>`)

## M9 / M10-1 Compatibility

- M10-1 continuous proof unchanged; `continuous_sweep_verified` remains `False`
  on ordinary discrete sweeps.
- M9 live exact path, provenance, FreeCAD measurement remain green.
- `continuous_proof.py` and `kinematic_sweep.py` are untouched except for reuse
  (no modification to their behavior).

## Tests

| Suite | Count | Status |
|---|---|---|
| M10-2 unit tests (`test_multi_joint_kinematics.py`) | 53 | **53 passed** |
| M10-1 regression (`test_m10_1_continuous_proof.py`) | 32 | **32 passed** |
| kinematic_sweep regression (`test_kinematic_sweep.py`) | 11 | **11 passed** |
| Full regression (`tests/`) | 750 passed, 51 skipped | **0 failed** |

All M10-2 tests are pure-Python deterministic computations; none require FreeCAD.

## Remaining Limitations

- M10-2 is **discrete forward kinematics only** for one explicit configuration.
  It performs **no** collision, clearance, or continuous verification.
- Multi-axis *continuous* clearance proof remains future (post-M10-2).
- FEA, materials selection, manufacturing approval, tolerance verification,
  optimization, and automatic synthesis/selection remain future.
- M10-3 is the intended consumer of the transformed `CadAssemblyProgram` for
  real FreeCAD exact measurement.

---

**Final disposition: `M10_2_GENERIC_MULTI_JOINT_KINEMATICS_VERIFIED`**
