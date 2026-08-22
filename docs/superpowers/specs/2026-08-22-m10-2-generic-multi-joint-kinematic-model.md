# M10-2 — Generic Multi-Joint Kinematic Model

## Problem Definition

M10-1 proved conservative continuous positive-clearance verification for ONE
generic revolute axis. M10-2 introduces the generic multi-joint rigid-body
kinematic model and deterministic forward-kinematics foundation required for
later M10 work (M10-3 multi-joint exact discrete collision sweep).

The implementation must represent at least two dependent revolute joints in
series, deterministically evaluate an explicit multi-joint configuration into
instance world transforms, produce a transformed CadAssemblyProgram, and
determine semantic identity — all without domain-specific semantics.

## Selected Topology: Rooted Acyclic Tree (Forest)

Each non-root instance has exactly one parent joint. Branching is allowed
(one parent, multiple children). Closed loops, constraint solving, and graph
mechanisms are OUT OF SCOPE.

Rooted tree chosen over strict serial chain because branching is only marginally
more complex and avoids immediate redesign when a mechanism contains branches.

## Rejected Alternatives

- A: Hard-coded two-joint model — too domain/scope specific
- D: Arbitrary graph / closed-loop mechanism — out of scope, requires constraint solving

## Joint Model

### RevoluteJointModel

```
joint_id: str                    # unique within model
joint_kind: KinematicJointKind   # REVOLUTE only in M10-2
parent_instance_id: str          # must exist in assembly
child_instance_id: str           # must exist in assembly
axis_origin_x_mm: float          # in PARENT INSTANCE LOCAL FRAME
axis_origin_y_mm: float
axis_origin_z_mm: float
axis_direction_x: float          # normalized, in PARENT INSTANCE LOCAL FRAME
axis_direction_y: float
axis_direction_z: float
min_angle_deg: float | None      # None = unlimited
max_angle_deg: float | None
```

Axis origin and direction are expressed in the **parent instance local frame**.
When the parent moves, the child's joint axis moves with the parent naturally.

### KinematicJointKind

```
REVOLUTE = "revolute"
```

Extensible for future joint types (prismatic, spherical, etc.) but only
REVOLUTE is implemented in M10-2.

## Home Configuration

Source CadAssemblyProgram placements define q=0 (home/reference configuration).

For a joint (parent P, child C):

```
T_parent_child_home = inverse(T_world_parent_home) ∘ T_world_child_home
```

where T_world_*_home = source CadRigidTransform placement.

At q=0, the evaluated configuration reproduces the source/home assembly placement
within numerical tolerance.

## Forward-Kinematics Equation

```
T_world_child(q) = T_world_parent(q) ∘ T_joint(q) ∘ T_parent_child_home
```

Where:

```
T_joint(q) = Translate(p) ∘ Rotate(u, q) ∘ Translate(-p)
```

- p = axis origin in parent-local frame
- u = axis direction in parent-local frame (unit vector)
- q = commanded joint angle in degrees

Translation component of T_joint = p - rot(q, p).

At q=0: T_joint(0) = identity, so T_world_child(0) = T_world_child_home.

### Composition Order Convention

LEFT-TO-RIGHT: `compose(A, B)` means A ∘ B (apply B first, then A).

```
Composed rotation:    A.q * B.q     (quaternion multiply)
Composed translation: A.t + rot(A.q, B.t)
```

### Quaternion/Rigid-Transform Helpers Reused

From `mechcad_harness.kinematic_sweep`:
- `_quaternion_multiply` — quaternion product
- `_rotation_quaternion(axis, angle_deg)` — axis-angle to quaternion (applies mod 360)
- `_rotate_vector(vector, quaternion)` — rotate 3D vector by quaternion

`_rotation_quaternion` applies `angle % 360` for geometric orientation. This is
correct for the geometric transform. Configuration identity is handled separately.

## Configuration Identity vs Geometric Identity

- **Configuration identity**: `configuration_hash` preserves raw commanded angles.
  0°, 360°, 720° are different configurations with different hashes.
- **Geometric transform identity**: `_rotation_quaternion` normalizes angles
  geometrically, so pose(0°) == pose(360°) == pose(720°) produce equivalent
  canonical transforms.
- These are separate concerns. `configuration_hash` ≠ `transformed_assembly_hash`.

## Configuration Model

```
JointConfiguration:
    model_id: str
    positions: dict[str, float]   # joint_id -> angle_deg (commanded, raw)
```

Validation:
- Every joint in the model must have a position entry
- No extra/unexpected joint IDs allowed
- All angle values must be finite
- Values outside declared limits rejected (fail closed, no clamping)

Canonical ordering for hash: sorted by joint_id.

## Model Identity

`model_hash` covers:
- model_id
- evaluator_version
- For each joint (sorted by joint_id): joint_id, joint_kind, parent/child instance IDs, axis origin/direction, limits

Does NOT cover: Python repr, memory addresses.

## Configuration Identity

`configuration_hash` covers:
- model_id
- Sorted (joint_id, angle_deg) pairs

Proves: same semantic config → same hash independent of dict insertion order.
Changing one angle → different hash.

## Transformed Assembly Identity

Reuses existing `assembly_hash()` from `cad_assembly.py`. The transformed
CadAssemblyProgram carries updated instance placements but same assembly_id
and parts. Distinct from:
- source_assembly_hash
- model_hash
- configuration_hash

## Topology Validation (Fail Closed)

Must validate:
- Unique joint_id
- parent_instance_id exists in assembly
- child_instance_id exists in assembly
- parent != child
- Child has at most one articulated parent (one parent joint)
- No cycles (BFS from roots, detect revisited nodes)
- All articulated nodes reachable from valid roots
- Deterministic root identification (instances not a child of any joint)

## Deterministic Traversal

BFS from roots (sorted by instance_id), child joints processed in sorted
joint_id order. Parent world transform computed before child joints use it.

## Joint Limits

- `min_angle_deg` and `max_angle_deg` optional (None = unlimited)
- If both present, min ≤ max validated
- Configuration values outside [min, max] rejected (fail closed, no clamping)
- Unlimited joints accept any finite angle

## Forward-Kinematics Result Type

`KinematicForwardKinematicsResult` — separate from CadKinematicSweepResult
(M10-2 is not a sweep).

Contains:
- evaluator_version
- source_assembly_hash
- model_hash
- configuration_hash
- transformed_assembly_hash
- ordered_joint_states (joint_id, position, within_limits)
- instance_world_transforms
- transformed_assembly (CadAssemblyProgram)
- result_hash

No collision classification, clearance, or continuous verification.

## Production Application Entrypoint

`ProductionApplication.evaluate_multi_joint_configuration()` validates source
binding, constructs the service, evaluates, and records deterministic provenance.

## Authority Boundary

M10-2 is derived deterministic computation. It must NOT:
- Mutate DesignState
- Create canonical revision, ChangeSet, or ChangeProposal
- Automatically choose joint axes, limits, or mechanism parameters

## FreeCAD Relationship

Core forward kinematics does NOT require FreeCAD. The intended architecture:
```
generic deterministic kinematics → transformed CadAssemblyProgram
```
M10-3 will use the transformed assembly for real FreeCAD exact measurement.

## M10-1 Compatibility

Continuous single-axis proof remains unchanged:
- VERIFIED_CLEAR, COLLISION_WITNESS, NOT_PROVEN semantics preserved
- CadKinematicSweepResult.continuous_sweep_verified remains False
- No multi-joint continuous proof claimed

## M9 Compatibility

Live exact path, provenance, and FreeCAD measurement remain green.

## Domain Isolation

Generic production modules contain no AZ/EL/pan/tilt/gear/Yagi semantics.

## Evaluator Version

```
MULTI_JOINT_FORWARD_KINEMATICS_VERSION = "multi-joint-forward-kinematics@1.0"
```

Future changes to transform semantics that could change results require a
version change.

## Final Disposition

**Acceptance marker: `M10_2_GENERIC_MULTI_JOINT_KINEMATICS_VERIFIED`**

M10-2 implements the generic multi-joint deterministic forward-kinematics model
exactly as specified:

- Rooted acyclic tree (forest) topology with at least two dependent revolute
  joints in series.
- Axis origin and direction expressed in the parent instance local frame;
  when the parent moves, the child's joint axis moves with it.
- Home configuration derived from source `CadAssemblyProgram` placements; at
  q=0 the evaluated configuration reproduces the source placement.
- Forward-kinematics equation `T_world_child(q) = T_world_parent(q) ∘
  T_joint(q) ∘ T_parent_child_home` with `T_joint(q) = Translate(p) ∘
  Rotate(u, q) ∘ Translate(-p)` and LEFT-TO-RIGHT compose convention
  (`compose(A, B) = A ∘ B`).
- Quaternion helpers (`_quaternion_multiply`, `_rotation_quaternion`,
  `_rotate_vector`) reused from `kinematic_sweep.py`; no second implementation.
  `_rotation_quaternion` applies `angle % 360` for geometric orientation; raw
  commanded angles (0°/360°/720°) are preserved in `configuration_hash`.
- Separate deterministic identities: `model_hash`, `configuration_hash`,
  `transformed_assembly_hash` (reusing `assembly_hash`), and `result_hash`.
- Fail-closed topology validation: unique joint IDs, parent/child existence,
  parent != child, single articulated parent, no cycles, all articulated nodes
  reachable from deterministic roots, deterministic BFS traversal.
- `KinematicForwardKinematicsResult` separate from `CadKinematicSweepResult`;
  no collision/classification/clearance/continuous claims.
- `ProductionApplication.evaluate_multi_joint_configuration()` validates the
  source binding, evaluates, and records deterministic provenance evidence.
- Core forward kinematics has no FreeCAD dependency; domain isolation preserved
  (no AZ/EL/pan/tilt/antenna semantics).
- M10-1 continuous proof and M9 live exact path remain unchanged and green.

Remaining boundary (explicitly NOT implemented in M10-2): collision,
clearance, and continuous verification of the transformed assembly; multi-axis
*continuous* clearance proof; FEA; materials selection; manufacturing approval;
tolerance verification; optimization; automatic synthesis/selection. M10-3 is
the intended consumer of the transformed `CadAssemblyProgram` for real FreeCAD
exact measurement.
