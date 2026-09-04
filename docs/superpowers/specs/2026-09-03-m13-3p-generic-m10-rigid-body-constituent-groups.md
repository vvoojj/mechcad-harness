# M13-3P Generic M10 Rigid-Body Constituent Group Foundation

## Status

Architecture and specification only. This prerequisite authorizes neither
production implementation nor test changes. It does not resume M13-3, start
M13-4, alter M11 or Rotator V2, create an implementation plan, or change any
physical-mechanism authority.

**Disposition: `CONFIRMED`.** The present generic M10 model cannot represent
one articulated rigid body containing multiple `CadComponentInstance` members.
M13-3 therefore remains blocked until this prerequisite is implemented and
accepted. This document specifies the minimum generic M10/CAD extension that
removes that blocker.

## Problem

M10 presently treats one CAD constituent as one kinematic node. A physical
rigid body such as a shaft fixed to a hub and payload support must instead have
one kinematic pose while retaining every constituent as a separately identified
CAD instance. Making every member a child of the physical revolute joint would
invent extra DOFs. Leaving non-reference members as roots would leave them
static. Replacing them with a compound would discard CAD constituent identity
and pair-level evidence.

The required analysis-only relationship is:

```text
Kinematic rigid body A
  -> reference CAD constituent A1
  -> members A1, A2, A3

one parent-body -> child-body revolute joint
  -> one body-reference pose for A
  -> one projected world pose for each of A1, A2, A3
```

Physical component identity, CAD constituent identity, and kinematic-body
identity remain three distinct namespaces. This model is not physical authority,
does not discover fixed connections, and does not replace `CadAssemblyProgram`
as the geometry representation.

## Repository Capability Audit

| Capability | Current state | Evidence |
| --- | --- | --- |
| CAD constituent | A `CadComponentInstance` has one stable `instance_id`, one part identity, and one home `placement`; assemblies reject duplicate instance IDs. | `cad_assembly.py:41-78` |
| M10 joint endpoint | `RevoluteJointModel` stores `parent_instance_id` and `child_instance_id`, with its axis in the parent **instance** local frame. | `multi_joint_kinematics.py:140-208` |
| M10 topology node | Topology validates each joint endpoint against assembly instance IDs, gives each child instance at most one articulated parent, and derives roots from instances with no incoming joint. | `multi_joint_kinematics.py:401-478` |
| M10 FK output | FK computes `world[child_instance_id]` once per joint and emits one `InstanceWorldTransform` and one transformed assembly placement per concrete instance. | `multi_joint_kinematics.py:559-629` |
| M10 descendant propagation | Existing deterministic BFS evaluates children after their parent; a child instance becomes the parent instance of its descendant joint. | `multi_joint_kinematics.py:451-477,579-596`; `tests/unit/test_multi_joint_kinematics.py:604-637,1008-1042` |
| M10-3 consumer | Every configuration is evaluated through M10 FK, but the current exact pair scope is only `moving_instance_ids x stationary_instance_ids`; two IDs on the moving side are never paired. | `multi_joint_collision_sweep.py:45-119,191-225,301-361`; `tests/unit/test_multi_joint_collision_sweep.py:422-456` |
| M10-4 consumer | FK evaluates every path sample and the proof calculates a bound for each side, but its public request also derives pairs only from `moving_instance_ids x stationary_instance_ids`. | `multi_joint_continuous_path.py:181-250`; `multi_joint_continuous_clearance.py:169-245,282-300`; `tests/unit/test_multi_joint_continuous_clearance.py:183-200` |
| Transient exact boundary | The transient request accepts an ordered opaque tuple of concrete pairs, validates transformed-assembly identity, and requires the provider to echo pairs in order. It does not require one operand to be physically stationary. | `transient_assembly_analysis.py:11-46`; `transient_freecad_measurement.py:51-70,326-375` |
| M12 output grouping | `OUTPUT_RIGID` and `output_transform_group` are candidate/canonical disposition and pair-scope metadata. Their only implementation consumers validate metadata and classify `SAME_RIGID_GROUP_EXCLUDED`; no M10 FK consumer reads them. | `candidates/m10_evaluation.py:97-139,267-283,578-595,903-1002`; `candidates/canonical_m10.py:103-141,895-955,1002-1081` |
| M12 exact motion | A checked M12 pair selects one output-rigid constituent and calls the M10-1 single-axis proof with a one-member moving tuple; it does not call M10-2 FK or project a group pose. | `candidates/m10_evaluation.py:913-965`; `candidates/canonical_m10.py:704-756` |

The current unit fixture deliberately assigns `shaft`, `hub`, and `body` the
same `output_transform_group`, but its assertion verifies only distinct IDs in
metadata. It does not demonstrate a shared M10 FK transform.
`tests/unit/test_m12_candidate_m10_binding.py:119-161,238-252`.

## Gap Disposition

**`CONFIRMED`.** The claim that M10 cannot represent one articulated rigid body
containing multiple CAD constituents is correct.

`child_instance_id` is both the topology node and the only target written by
FK. There is no `KinematicRigidBody`, body-to-member mapping, body transform,
or member expansion. M10-3 and M10-4 receive only the per-instance placements
that this FK emits. A non-child instance is a root and retains its home
placement.

The grouping is not already supplied by CAD assemblies: `CadAssemblyProgram`
preserves parts and individually placed instances; it has no articulation or
fixed-body meaning. It must remain that way.

## Existing M10 Body Semantics

Today, M10's implicit body model is exactly one constituent per topology node:

1. A root is every assembly instance that is not any joint's `child_instance_id`.
2. A moving body is one `child_instance_id` and its accumulated world transform.
3. `parent_instance_id` and `child_instance_id` are CAD instance IDs, not body
   IDs or physical IDs.
4. Home transforms are the `CadComponentInstance.placement` values from the
   source assembly.
5. FK derives `T_parent_child_home = inverse(T_world_parent_home) *
   T_world_child_home` for each joint.
6. `world: dict[str, CadRigidTransform]` is keyed by CAD instance ID. It begins
   with root home placements and receives one entry for every joint child.
7. The FK result is a transform per concrete CAD instance, not a transform per
   logical body. Its transformed assembly is the source assembly with those
   individual placements replaced.

The current equation is:

```text
T_world_child_instance(q)
  = T_world_parent_instance(q)
  * T_joint_parent_local(q)
  * T_parent_instance_child_instance_home
```

This is retained for legacy models exactly.

## OUTPUT_RIGID Audit

**Disposition: `NOT_GENERIC_ENOUGH`.** It must not be reused as the M10 rigid
body model or as a lower-level FK primitive.

`OUTPUT_RIGID` is a M12 candidate/canonical adapter disposition, not a generic
M10 type. It is constrained to one `CandidateM10Binding.output_joint_id` and to
the M10-1 proof version (`candidates/m10_evaluation.py:167-204,211-283`).
`output_transform_group` is optional metadata restricted to that one output
joint; it carries no member reference frame, member offset, body identity, body
topology, or M10-2 FK input. The only generic M10 types imported by that module
are a caller-authored model and transform helpers, not a group interpreter.

For a checked M12 pair, the candidate and canonical services each make a
separate single-axis request for exactly one selected CAD constituent. Therefore
the shared string does not cause multiple constituents to receive one M10 FK
transform. It cannot express a multi-joint child body, a grouped root, a body
with articulated descendants, or durable generic body identity.

The existing candidate/canonical pair classification named
`SAME_RIGID_GROUP_EXCLUDED` remains useful to its bounded adapter, but it is not
an M10 body representation and is not elevated to physical authority.

## Goals

- Add one generic M10 analysis representation for a rigid body containing one
  or more existing CAD instances.
- Apply exactly one existing M10 body pose to every member through fixed,
  explicitly declared home offsets.
- Retain rooted-tree/forest topology, revolute equations, keyed configurations,
  exact discrete collision, and continuous path proof semantics.
- Preserve concrete constituent IDs in transformed assemblies, pair inventories,
  exact results, and witnesses.
- Preserve literal legacy model JSON and hashes through explicit version-aware
  serialization and a legacy hash branch.
- Supply a sufficient generic input contract for the future M13-3
  physical-to-M10 bridge.

## Non-Goals

- No physical-joint authority, M13-1/M13-2 interface consumption, candidate
  promotion, canonical physical projection, or candidate/canonical bridge.
- No M13-3 implementation, M13-4, Rotator V2, M11, new joint type, loop, IK,
  dynamics, constraint solver, automatic group discovery, CAD contact inference,
  STEP recognition, or compound replacement geometry.
- No fake fixed, zero-range, duplicated, or infinitesimal revolute joints.
- No alternate FK solver, collision algorithm, or continuous-clearance
  mathematics.

## Rigid Body Model

The selected extension is a versioned **M10 v2** `KinematicModel` containing
explicit `KinematicRigidBody` records. Each record has:

```text
KinematicRigidBody
  schema_version = "kinematic-rigid-body@1"
  body_id
  reference_member_instance_id
  members: tuple[KinematicRigidBodyMember, ...]
  body_hash

KinematicRigidBodyMember
  member_instance_id
  reference_to_member_home: CadRigidTransform
```

`reference_to_member_home` maps a point in the body reference frame, anchored
to the reference member's home frame, to the member's home frame. The reference
member is included in `members` and its transform is the identity transform.
Members are canonicalized by `member_instance_id`; body records are canonicalized
by `body_id`. The hash covers body ID, reference member, every member ID, and
every fixed reference-to-member transform.

The transform is intentionally explicit rather than inferred from geometry. It
makes the body frame and static member offsets durable analysis inputs, gives
them their required model identity, and permits assembly agreement to be
validated fail-closed.

### Alternatives Considered

1. **Infer all member offsets from the source assembly.** Smaller data shape,
   but an offset change would change only assembly/request identity rather than
   the body-model identity required here. Rejected.
2. **Keep instance endpoints and add a side mapping from reference instance to
   members.** Preserves field names but makes `parent_instance_id` and
   `child_instance_id` ambiguously mean both constituent and logical body.
   Rejected.
3. **Explicit v2 bodies and v2 body-endpoint joints.** Provides unambiguous
   identity, validates static offsets, and keeps all FK math in the existing
   service. Selected.

## Body / Member Identity

`body_id` is a nonblank explicitly declared stable M10 analysis ID. It may not
be a runtime index, BFS order, FreeCAD object name, or artifact path. For v2,
it is included in the body hash and the model hash.

Every `member_instance_id` resolves to exactly one
`CadComponentInstance.instance_id` in the evaluated source assembly. A member
may occur once within a body and in exactly one v2 body across the model. A v2
model must cover every assembly instance exactly once. This selected complete
membership contract is preferable to implicit fixed members because it lets a
multi-member fixed root be represented truthfully and prevents unclassified
geometry from silently becoming an independent root.

For legacy v1 projection only, the body identity is the existing CAD instance
ID and the one member is that same instance. This is truthful because the legacy
contract already identifies both its topology node and sole constituent by that
ID. No persisted legacy record gains a body field.

## Body Reference / Home Transform

For a v2 body `B`, let `r(B)` be its reference member and `m` one of its
members. The source assembly remains the home-placement authority:

```text
T_world_body_home(B) = T_world_home(r(B))
T_body_member_home(B, m) = reference_to_member_home(m)
```

The declared fixed offset is full-precision, persisted, and hash-bound. It is
validated against the authoritative source placement, not fitted, rounded,
aligned by bounding boxes, or obtained from FreeCAD:

```text
rigid_transform_agrees(
    T_world_home(m),
    transform_compose(
        T_world_body_home(B),
        T_body_member_home(B, m),
    ),
    policy="rigid-transform-agreement@1.0",
)
```

This validates that the declared offset is numerically consistent with the
source placement; it does not permit a different offset or a second placement
authority. For a reference member, `T_body_reference_home` is literal identity
`CadRigidTransform()` at model validation time. This field is declared directly,
not calculated through inverse/compose arithmetic, so this invariant remains
literal equality. Non-finite or invalid quaternions remain rejected by the
existing `CadRigidTransform` validator.

## Rigid Transform Agreement Contract

M10 v2 defines one deterministic comparison convention:

```text
RigidTransformAgreementPolicy
  version = "rigid-transform-agreement@1.0"
  translation_metric = "componentwise-max-absolute-mm"
  translation_abs_tol_mm = 1e-9
  orientation_metric = "sign-invariant-unit-quaternion-angle-rad"
  orientation_abs_tol_rad = 1e-7
```

`RigidTransformAgreementPolicy` is an immutable constant-backed semantic
contract, not a new engineering-authority record and not caller-selectable
analysis input. It is used only where M10 v2 must prove that independently
calculated transforms represent the same rigid pose. The implementation exposes
one deterministic pure-Python predicate:

```text
rigid_transform_agrees(first, second,
                       policy="rigid-transform-agreement@1.0") -> bool
```

The policy version must be exact. An unknown version is rejected; an
implementation may not supply an implementation-local epsilon or choose a
comparison rule per worker.

### Comparison Algorithm

For inputs `a` and `b`, the predicate performs these steps in this order:

1. Require every translation and quaternion component of both transforms to be
   finite. A non-finite input returns `False`; model/source validation that uses
   the predicate then fails closed.
2. Normalize `a.rotation_quaternion` and `b.rotation_quaternion` with the
   existing shared `normalize_quaternion` helper. No comparator-local
   normalization, rounding, quantization, Euler conversion, geometry query, or
   FreeCAD comparison is permitted.
3. Compute:

   ```text
   translation_error_mm = max(
       abs(a.x_mm - b.x_mm),
       abs(a.y_mm - b.y_mm),
       abs(a.z_mm - b.z_mm),
   )
   ```

4. Compute the sign-invariant orientation metric:

   ```text
   d = clamp(
       abs(qa.w * qb.w + qa.x * qb.x + qa.y * qb.y + qa.z * qb.z),
       0.0,
       1.0,
   )
   orientation_error_rad = 2.0 * acos(d)
   ```

   `clamp(value, low, high)` means `min(high, max(low, value))`. It handles
   only numerical drift around the unit-quaternion dot-product boundary; it is
   not rounding before comparison.
5. Return `True` exactly when both inclusive bounds hold:

   ```text
   translation_error_mm <= 1e-9
   and orientation_error_rad <= 1e-7
   ```

The predicate is deterministic pure Python over the existing numerical stack.
For identical finite numeric inputs, all candidate, canonical, and M10 callers
must receive the same boolean result.

### Quaternion Sign Semantics

The orientation calculation deliberately uses `abs(dot(qa, qb))`. Therefore
`q` and `-q` represent the same physical orientation even if either input has
not already received the repository's canonical-sign normalization. Direct
quaternion-component equality is not a rigid-pose comparison contract.

### Numerical Characterization and Frozen Thresholds

The following deterministic CPython 3.14.6 characterization used the current
`CadRigidTransform`, `transform_inverse`, `transform_compose`, and quaternion
helpers without modifying repository code or tests:

| Case | Result | Literal equality |
| --- | --- | --- |
| Translation only | source `x_mm = -6.54321987`; reconstructed `x_mm = -6.543219869999998`; max translation residual `1.7763568394002505e-15 mm` | false |
| Arbitrary normalized quaternions | zero translation residual and zero reported angular residual; normalized quaternion components still differed after inverse/compose | false |
| Combined translation and rotation | max translation residual `7.72715225139109e-14 mm`; zero reported angular residual | false |
| Near-180-degree rotation | max translation residual `5.684341886080802e-14 mm`; zero reported angular residual | false |
| Two-joint q=0-style nested reconstruction | max translation residual `6.394884621840902e-14 mm`; quaternion components differed by ordinary floating roundoff | false |
| Deterministic 90-case identity/arbitrary/near-180/near-zero/250/1,000/10,000 mm set | maximum translation residual `7.275957614183426e-12 mm`; maximum reported angular residual `0.0 rad` | mixed, including false |
| Seeded deterministic 1,000-case mechanical-scale stress set | maximum translation residual `1.4551915228366852e-11 mm`; maximum angular residual `2.9802322387695312e-08 rad` | mixed, including false |

The translation threshold is approximately 68 times the largest observed pure
round-trip residual, is aligned with the existing M10 q=0 test scale of
`1e-9 mm`, and is a nanometre-scale placement check rather than a mechanical
placement allowance. The orientation threshold is approximately 3.3 times the
largest observed angular residual. The `acos(dot)` metric itself resolves a
one-ULP unit-dot drift at about `4e-8 rad`, so a materially smaller threshold
would reject equivalent current transforms because of metric arithmetic rather
than pose difference. Both thresholds remain far below meaningful M10 mechanism
placement changes and are independent of all collision and FreeCAD tolerances.

The existing `1e-6` FreeCAD placement comparison and M10 collision thresholds
are separate subsystem contracts and are not reused here. The thresholds above
are compile-time/spec constants; they do not depend on characterization data at
runtime.

### Explicitly Rejected Alternatives

- Literal `CadRigidTransform` equality after inverse/compose arithmetic.
- Rounding or quantizing persisted transforms merely to make equality pass.
- Replacing recomputed q=0 placements with source assembly placements.
- `pytest.approx` as production semantics.
- An implementation-local arbitrary epsilon.
- Geometry, bounding-box, or FreeCAD comparison.
- Serialized transform-hash comparison as geometric equivalence.
- Treating `q` and `-q` as distinct orientations because their components differ.

## Revolute Joint Body Correspondence

`RevoluteJointModel` gains an explicit versioned v2 shape:

```text
RevoluteJointModel @2
  joint_id
  joint_kind = REVOLUTE
  parent_body_id
  child_body_id
  axis_origin_* and axis_direction_* in parent body-reference frame
  optional min_angle_deg / max_angle_deg
```

The existing v1 shape continues to contain exactly `parent_instance_id` and
`child_instance_id`, whose axis remains in the parent instance frame. V2 must
not accept instance endpoint fields; v1 must not accept body endpoint fields.
This removes the ambiguity that a side map would create.

For v2, the home relation used by existing FK composition is:

```text
T_parent_body_child_body_home
  = inverse(T_world_body_home(parent)) * T_world_body_home(child)
```

The revolute equation and composition order are unchanged:

```text
T_world_body(child, q)
  = T_world_body(parent, q)
  * T_joint_parent_body_reference(q)
  * T_parent_body_child_body_home
```

Only endpoint namespace and frame anchoring change for v2. A legacy singleton
projection has each body reference equal to its only instance, so this equation
is exactly the existing v1 equation.

## Root / Hierarchy

V2 topology nodes are bodies. A root is every declared body with no incoming
v2 joint; all of its members remain fixed at their home poses. Therefore a
fixed root may contain a base, bracket, motor housing, and other fixed-together
CAD constituents without presenting them as unrelated roots.

The generic M10 forest remains supported. V2 permits multiple root bodies and
multiple articulated branches. A body may have several child joints. Each
non-root body has one articulated parent at most. M13-3 may impose its later
single physical-root policy at its physical bridge boundary, but this
prerequisite does not narrow generic M10 forest semantics.

There is no separate descendant walk. The existing deterministic topology/BFS
owner is generalized from instance nodes to body nodes. Its traversal ordering
is roots sorted by `body_id`, then child joints sorted by `joint_id`. Projection
to members occurs only after a body pose has been computed.

## FK Expansion

V2 FK must compute one internal `world_body[body_id]` map. It initializes every
root body with its reference member's source home transform, then applies the
existing per-joint equation in the existing `MultiJointKinematicsService`.

One deterministic projection creates the externally visible concrete placement:

```text
T_world_member(q)
  = T_world_body(B, q) * T_body_member_home(B, member)
```

The projection emits the existing `InstanceWorldTransform` records and replaces
the placement of every original `CadComponentInstance` in the existing
`CadAssemblyProgram`. Results continue to expose constituent transforms, not a
compound or body-only geometry. A member is `is_articulated` exactly when its
body has an incoming joint; members of a root body are not articulated.

V1 executes its existing instance topology and transform path without routing
through a serially changed representation. An internal legacy singleton view
may be used only if it produces exactly the legacy JSON, hash, ordering, and
transforms; it is not persisted and it must not affect the v1 code path's
identity calculation.

## q=0 Semantics

For every valid v2 model, the all-zero keyed configuration has this mandatory
invariant:

```text
rigid_transform_agrees(
    FK(q = 0).transformed_assembly.instances[member].placement,
    source_assembly.instances[member].placement,
    policy="rigid-transform-agreement@1.0",
)
```

It follows from identity joint rotations, the declared/validated body home
offsets, and the existing parent-child home composition. It applies to every
member of every root, articulated, and descendant body. The required invariant
is geometric rigid-pose agreement, not literal serialized
`CadRigidTransform` equality after FK arithmetic. The FK result remains the
actual deterministic result of the calculation; it must not be overwritten with
the source placement. Violation is an M10 model/assembly integrity error before
collision or proof execution, not a FreeCAD re-placement operation.

Consequently, a source placement hash `H1` and a mathematically equivalent q=0
recomputed placement hash `H2` may differ. Transform-hash equality is not
rigid-pose agreement.

## Collision Pair Semantics

The current M10-3 partition contract is insufficient for a generic multi-joint
mechanism. For a root `R -> J1 -> A -> J2 -> B`, placing `A` and `B` in the
moving partition and `R` in the stationary partition measures `A-R` and `B-R`,
but omits `A-B`. This is confirmed by `collision_pairs()`, which has no source
of pairs other than the nested moving/stationary product
(`multi_joint_collision_sweep.py:190-198`). A transformed assembly can be
correct while its measured pair scope remains incomplete.

Kinematic articulation and exact-measurement operand position are separate
concepts. The FK-transformed assembly contains every constituent's correct pose,
whether it belongs to a root, ancestor, descendant, or sibling body. A pair
selection request chooses two concrete shapes to measure; it does not declare
that either shape is physically stationary.

Legacy M10-3 v1 retains its existing ordered Cartesian product:

```text
moving_instance_ids x stationary_instance_ids
```

Its historical partitions, result labels, JSON, hashes, and result semantics do
not change. It is not an adequate request form for M10 v2 body-group collision
evaluation and must not be used by a v2 body model.

## V2 Exact Pair Scope

M13-3P adds one shared, generic pair-selection primitive in a small neutral
module, for example `multi_joint_pair_scope.py`:

```text
ExactConstituentPair
  schema_version = "exact-constituent-pair@1"
  first_instance_id
  second_instance_id

exact_pair_scope: tuple[ExactConstituentPair, ...]
exact_pair_scope_version = "exact-constituent-pair-scope@1.0"
```

Each pair is an unordered physical pair represented in canonical lexical order
(`first_instance_id < second_instance_id`). The scope is non-empty and
canonicalized by that pair key, so caller tuple ordering is non-semantic. It
rejects a self-pair, blank ID, duplicate unordered pair, and unknown source
assembly ID. A v2 request additionally resolves body membership and rejects an
exact pair whose two members are in the same rigid body. The caller retains that
same-body pair in its higher-level inventory as a rigid-internal exclusion; it
does not submit it to generic exact measurement as an external collision.

`MultiJointCollisionSweepRequest@2` has schema version
`"multi-joint-collision-sweep-request@2"`, explicit `exact_pair_scope`, no
`moving_instance_ids`, and no `stationary_instance_ids`. Its request hash covers
the canonical exact pair scope in addition to the existing source assembly,
model, ordered configurations, tolerances, and v2 service version
`multi-joint-exact-collision-sweep@2.0` plus
`exact-constituent-pair-scope@1.0`. A v2 pair scope may contain any concrete
constituents from different bodies, including:

- root versus articulated;
- articulated versus articulated;
- siblings;
- ancestor versus descendant; and
- bodies in different trees of the generic M10 forest.

M10-3 v2 executes the existing flow only:

```text
configuration -> existing M10 FK -> full transformed CadAssemblyProgram
  -> TransientAssemblyAnalysisRequest.pairs
  -> existing FreeCAD exact provider -> existing classification thresholds
```

The v2 service supplies each canonical pair to the existing transient `pairs`
tuple as `(first_instance_id, second_instance_id)`. The transient service already
binds source/transformed/request/sample identities and validates exact ordered
pair echoing. FreeCAD already realizes all shapes in the transformed assembly
before indexing both operands (`transient_freecad_measurement.py:333-371`).
`common().Volume`, `distToShape()`, `CollisionClassification`, provider
composition, and durable M10-3 provenance remain the existing implementation.
This is a versioned M10-3 request/result evolution, not a parallel collision
system.

The legacy M10-3 request form accepts only a legacy v1 kinematic model. A v2
body model requires `MultiJointCollisionSweepRequest@2`; this prevents a grouped
body analysis from silently taking the incomplete Cartesian-pair path.

### Same-Body Pairs

Two members of one rigid body have a constant declared relative transform. They
are still members of the complete caller-level constituent inventory; grouping
must never silently delete either constituent or collapse the pair into opaque
geometry. V2 generic exact scope rejects a same-body pair so it cannot be
silently measured or misreported as external collision.

Where a caller owns a complete unordered pair inventory, it must retain each
same-body pair and classify it explicitly as rigid-internal. The current M12
candidate/canonical inventory already has
`SAME_RIGID_GROUP_EXCLUDED`; its existing meaning may be used by that adapter
after it derives the classification from the generic M10 body membership. M13-3
will supply its future bridge request's complete inventory using the same fact.
M13-3P adds no duplicate generic collision-exclusion system and does not modify
M10-3's exact pair algorithm.

### Cross-Body Pairs

Pairs spanning distinct bodies retain ordinary exact M10 semantics: positive
common volume is interference, touching is not positive clearance, and distance
is measured by the unchanged exact provider. The v2 pair scope makes every
required cross-body pair executable; grouping does not suppress or relax a pair
merely because both members have inherited motion.

## Complete Pair Inventory Boundary

Generic M10 execution scope is only the explicit canonical tuple of exact
concrete pairs requested for FK-transformed measurement. It has no
`CHECK_CLEARANCE`, contact, rigid-internal, or physical meaning enum.

The higher-level M12/M13 evaluation inventory remains the authoritative complete
unordered constituent universe and assigns classifications such as
`CHECK_CLEARANCE`, `INTENDED_CONTACT_EXCLUDED`, and
`SAME_RIGID_GROUP_EXCLUDED`. It derives same-body exclusions from generic body
membership and passes every cross-body `CHECK_CLEARANCE` pair to M10 v2 exact
scope. Thus no higher-level caller can truthfully claim a checked pair that
generic M10 cannot execute, and M13-3 does not require a further M10 pair model.

## Witness Identity

V1 discrete/continuous results retain their literal directional
`moving_instance_id` / `stationary_instance_id` JSON and hashes. V2 cannot use
those labels because either operand may have non-empty articulated ancestry.

V2 adds versioned pair result records with neutral concrete identities:

```text
ExactConstituentPairResult@2
  schema_version = "exact-constituent-pair-result@2"
  first_instance_id
  second_instance_id
  interference_volume_mm3
  exact_distance_mm
  classification
```

`MultiJointCollisionConfigurationResult@2` and
`MultiJointCollisionSweepResult@2` use schema versions
`"multi-joint-collision-configuration-result@2"` and
`"multi-joint-collision-sweep-result@2"`. M10-4 v2 exact-evaluation,
certificate, and witness records use `first_instance_id` / `second_instance_id`;
its outer result uses schema version
`"multi-joint-continuous-clearance-proof-result@2"`. Each matches the canonical
requested pair. A body ID may be added only as auxiliary provenance; it must
never replace a constituent ID. Exact collision evidence therefore continues to
identify the actual CAD members that interfered or violated requested clearance.

## M10-4 Pair Audit

The current `MultiJointContinuousPathRequest` has the same public pair-scope
limitation as M10-3: its `pairs` property derives only a moving/stationary
Cartesian product (`multi_joint_continuous_path.py:181-250`). Although its
implementation already calculates a motion bound for both operands, as shown by
the existing test that passes articulated `b` as the nominal stationary operand,
the request/result labels are false for a general two-moving-body pair.

`MultiJointContinuousPathRequest@2` therefore has schema version
`"multi-joint-continuous-path-request@2"`, uses the shared canonical
`exact_pair_scope`, omits both directional partitions, and hash-binds the scope
with the existing source/model/path/tolerances/resource limits and v2 pair-scope
version `exact-constituent-pair-scope@1.0`. Its `pairs` property projects
canonical pairs to the transient request. M10-4 v2 result records use the neutral
pair identifiers defined above. The existing proof algorithm version remains
`conservative-multi-joint-path-clearance-proof@1.0` because its mathematics does
not change. The legacy M10-4 request form accepts only a legacy v1 kinematic
model. V1 request/result JSON and hashes retain their exact current forms.

## Continuous M10 Boundary

M10-4 path interpolation, conservative subdivision, exact measurements, and
the pair-relative `B_A + B_B` proof rule do not change. Every path sample simply
receives the v2 FK-expanded constituent assembly.

`derive_reach_bounds` needs only topology/input expansion. For a v2 member, it
uses the member's body-joint chain and adds the declared fixed distance from the
terminal body reference to that member origin to the existing telescoping
offset list. Its trusted local extent remains keyed by the concrete member ID.
The same existing reach-bound mathematics is then applied. A v2-specific
reach-bound plumbing version is required so v2 result/request identity does not
claim the legacy body-free topology interpretation; v1 retains the existing
version and exact bytes.

No geometry query, bounding-box alignment, alternative motion bound, or second
continuous proof is introduced.

For either endpoint of a v2 pair, v2 body-chain reach expansion derives records
from that constituent's own body/joint ancestry, including its fixed terminal
member offset. The existing proof loops over both operands and sums their
independent bounds. This is conservative for ancestor/descendant pairs with
overlapping ancestry, siblings, and separate articulated branches; overlap may
over-bound motion but cannot understate it. No articulated/root special case is
permitted.

## Hash / Currentness

`KinematicRigidBody.body_hash` covers its schema version, stable body ID,
reference member ID, and canonical member records including each fixed offset.
`kinematic_model_hash` for v2 covers:

- model ID, v2 forward-kinematics evaluator version, and explicit
  `transform_agreement_version = "rigid-transform-agreement@1.0"`;
- canonical body hashes, sorted by `body_id`; and
- canonical v2 joints, sorted by `joint_id`, including parent/child body IDs,
  axis, and limits.

Thus changes to body ID, member set, reference member/frame, member home offset,
or body-level parent/child correspondence change model identity. Input ordering
of bodies and members does not change identity.

V2 M10-3 and M10-4 request hashes bind both `kinematic_model_hash` and the
canonical exact pair scope. A result under pair scope A cannot be reused under
scope B. Source assembly placement changes remain source-assembly identity
changes and are also revalidated against the hash-bound v2 offsets. FK, discrete
results, continuous results, and durable provenance continue to bind their
existing model/request/transformed-assembly identities; v2 provenance binds the
v2 request hash and thereby the exact pair scope. No second currentness
mechanism is created.

The agreement predicate does not change `CadRigidTransform` serialization,
member-offset serialization, source placement serialization, v1 model
serialization, v1 model hashes, or v1 request/result hashes. Full unrounded
transform values remain persisted and hashed. Changing either agreement metric
or either threshold requires a new `rigid-transform-agreement@<version>` value
and a v2 model payload carrying that new value; it cannot silently reinterpret
an existing v2 model hash or its downstream requests/results.

## Transformed Assembly Identity at q=0

The FK-expanded `CadAssemblyProgram` is a separately derived value with its
truthful literal serialized transform hash. M13-3P does not require:

```text
transformed_assembly_hash(q = 0) == source_assembly_hash
```

It instead requires the same constituent definitions, the same concrete
constituent identities, the same applicable explicit pair scope, and
`rigid_transform_agrees(..., policy="rigid-transform-agreement@1.0")` for every
member placement. No hash normalization is added to force source and transformed
assembly hashes equal.

## Collision and Tolerance Boundary

`rigid-transform-agreement@1.0` is used only for v2 model-to-source home
integrity validation, q=0 replay consistency, and explicitly named equivalent
bridge/reference-pose checks. It is not a collision-clearance tolerance, contact
tolerance, manufacturing tolerance, M10-3 interference threshold, M10-4
`proof_guard`, or FreeCAD geometry tolerance. Those existing contracts retain
their independent meanings and values.

## Schema / Backward Compatibility

M10 requires explicit schema-aware evolution because current M10 records have
no schema-version field and their model JSON/hash are accepted historical
values. Optional fields with `exclude_none` are prohibited as a compatibility
strategy.

### Legacy v1

- Absent M10 model/joint discriminator fields parse as v1. Their in-memory
  defaults are `"kinematic-model@1"` and `"revolute-joint-model@1"`, but their
  v1 serializers omit those fields to preserve literal historical JSON.
- Existing serialized `KinematicModel` remains exactly
  `model_id`, `joints`, and `evaluator_version` with current nested v1 joints.
- Existing `RevoluteJointModel` JSON remains exactly its instance endpoints,
  axis values, and limits.
- `kinematic_model_hash` takes the current v1 payload branch byte-for-byte.
- Existing M10-3/M10-4 request, result, Evidence, configuration, and path JSON
  and hashes remain unchanged for their v1 schemas.

### New v2

- `KinematicModel` gains explicit discriminator value
  `"kinematic-model@2"`; its serializer emits that version, its body records,
  and v2 joints only.
- `RevoluteJointModel` gains explicit discriminator value
  `"revolute-joint-model@2"`; it serializes body endpoints only.
- V2 uses the new trusted M10 FK evaluator version
  `multi-joint-forward-kinematics@2.0` and emits explicit
  `transform_agreement_version = "rigid-transform-agreement@1.0"` in the v2
  model/hash payload. M10-3 accepts the explicit trusted v1 and v2 evaluator
  set while retaining its own sweep algorithm/version and v1 request bytes.
  M10-4 likewise selects its reach-bound plumbing version by model version.
- `JointConfiguration` and `MultiJointPath` need no schema change: they remain
  keyed by unchanged stable `joint_id` and bind the model through `model_id` and
  the enclosing request model hash.
- `MultiJointCollisionSweepRequest@2` and
  `MultiJointContinuousPathRequest@2` have explicit `exact_pair_scope` and no
  directional partitions. They use explicit v2 serializers and request hashes;
  they must not silently coerce v1 records to v2.
- V2 discrete/continuous result records have explicit versioned neutral
  first/second constituent pair fields. They retain concrete instance transforms
  and are bound to the versioned model and pair-scope hashes. Their v1 result
  serializers remain unchanged.

The v1/v2 mismatch cases are rejected: a v1 model cannot carry bodies or v2
joints; a v2 model cannot carry v1 joint endpoints; and v2 body endpoint or
membership references cannot resolve against the source assembly.

## Failure Semantics

Reuse existing `ValueError`-style model/topology integrity validation and retain
its specific error families. The v2 implementation must reject before exact
measurement or proof for:

- duplicate or blank body ID, empty body, missing reference member, and reference
  member not included exactly once;
- duplicate member within a body, a member in two bodies, unknown assembly
  member, or incomplete/extra v2 membership coverage;
- invalid/non-finite member offset, non-identity reference-member offset, or
  declared offset that does not agree with the assembly home placement under
  `rigid-transform-agreement@1.0`;
- duplicate joint ID, unknown parent/child body, parent equal to child, duplicate
  articulated parent, body cycle, or unreachable articulated body;
- malformed or mismatched v1/v2 schema/version/endpoints;
- an empty, self, duplicate-unordered, unknown, or same-body v2 exact pair;
- an M10-3/M10-4 v2 pair scope whose canonical form or hash does not match its
  supplied request, source assembly, model, or transformed assembly;
- a full caller-owned pair inventory that omits a same-body pair or classifies
  it as checked motion without an explicit policy contract.

M10-3 provider failures and M10-4 `NOT_PROVEN` remain their existing distinct
execution outcomes. They must not be relabeled as body-model validation errors.

## Dependency Decision

**`USE EXISTING STACK`.** The extension uses `CadRigidTransform`,
`transform_compose`, `transform_inverse`, `transform_apply`, existing quaternion
helpers, existing Pydantic v2 models, and current FreeCAD transient realization.
No robotics, transform, collision, or CAD third-party dependency is needed.

## M13-3 Handoff

After M13-3P, M13-3 receives this complete generic M10 input surface:

```text
KinematicModel @2
  bodies = (
    KinematicRigidBody(
      body_id=<stable bridge body ID>,
      reference_member_instance_id=<CAD instance ID>,
      members=(<CAD ID + explicit reference-to-member home transform>, ...),
    ),
    ...,
  )
  joints = (
    RevoluteJointModel @2(
      joint_id=<stable physical-joint-derived M10 ID>,
      parent_body_id=<bridge parent body ID>,
      child_body_id=<bridge child body ID>,
      axis in parent body-reference frame,
      limits=...,
    ),
    ...,
  )
```

M13-3 supplies these explicit body IDs, CAD membership, static reference offsets,
body-level revolute endpoints, and every cross-body pair selected
`CHECK_CLEARANCE` by its caller-owned complete inventory. It does not modify M10
again, construct compounds, or implement FK. Candidate and canonical adapters
use the same generic v2 M10 core after each resolves its own authority.

M13-3 may later use `rigid-transform-agreement@1.0` to prove that a
candidate-lowered body/reference pose and its canonical-lowered body/reference
pose represent the same physical pose after ID projection and deterministic
transform arithmetic. M13-3P does not define candidate/canonical authority. Any
such use must cite this exact versioned contract and must not invent another
epsilon.

Its generic execution calls are explicit:

```text
MultiJointCollisionSweepRequest@2(
  model=<KinematicModel@2>,
  exact_pair_scope=(ExactConstituentPair(A2, B1), ...),
)

MultiJointContinuousPathRequest@2(
  model=<KinematicModel@2>,
  path=<MultiJointPath>,
  exact_pair_scope=(ExactConstituentPair(A2, B1), ...),
)
```

With this prerequisite accepted, the original M13-3 rigid-body representation
blocker is **RESOLVED**. Remaining M13-3 work is the separately specified
physical authority/lowering/promotion/canonical bridge, not another M10 body
model prerequisite.

## Proposed Implementation Surface

Implementation is intentionally limited to generic M10/CAD plumbing:

- `multi_joint_kinematics.py`: versioned v1/v2 model records and serializers,
  body/member validation and hashes, body topology projection, existing FK body
  pose evaluation, and member placement expansion.
- a small neutral `multi_joint_pair_scope.py`: canonical concrete pair model and
  shared validation; it has no CAD, FreeCAD, candidate, physical, or collision
  classification dependency.
- `multi_joint_collision_sweep.py`: explicit v2 pair-scope request/result
  models, source/body validation, and neutral pair result mapping; retain FK,
  transient service, exact measurement, and classification code.
- `multi_joint_continuous_path.py`: explicit v2 pair-scope request, v2
  body-chain reach inputs, and versioned request plumbing without changing the
  bound equation.
- `multi_joint_continuous_clearance.py`: consume the shared v2 pairs and emit
  neutral v2 pair/witness/certificate records without changing proof logic.
- `transient_assembly_analysis.py` and `transient_freecad_measurement.py`:
  retain their existing opaque ordered pair transport and exact provider; rename
  only implementation-local operand labels from moving/stationary to
  first/second where needed to prevent semantic mislabeling.
- `application.py` and exports: construct/accept explicit typed v1 or v2
  M10-3/M10-4 requests rather than optional mixed fields, preserve v1 public
  request construction, and bind v2 exact-pair scopes into the existing trusted
  provenance/Evidence paths.
- M10 tests and a focused live FreeCAD acceptance fixture.

Do not create `rigid_body_kinematics.py`, a parallel solver, a physical model,
or a new dependency.

## Test Strategy

Future implementation must include, at minimum:

1. Legacy v1 golden JSON and `kinematic_model_hash` equality, unchanged v1 FK
   transforms/results, M10-3 request/results, M10-4 request/results, and the
   existing M10-2/M10-3/M10-4 regression suites.
2. One v2 body with two members: both inherit the same body delta and retain
   their declared relative transform.
3. One v2 body with three members and a grouped fixed root.
4. Transform-agreement tests that invoke the production predicate itself, not a
   broad `pytest.approx`: literal identity for the reference-member offset; an
   arbitrary normalized-quaternion member offset; the observed one-ULP-style
   translation reconstruction; and `q` versus `-q` as the same orientation.
5. Transform-agreement threshold boundaries: translation just inside passes and
   just outside fails; orientation just inside passes and just outside fails;
   non-finite input fails; and a wrong member offset with meaningful displacement
   fails.
6. q=0 rigid-pose agreement for every grouped-FK member, including a case where
   source and transformed assembly hashes differ solely because of floating
   reconstruction; source/transformed hash equality must not be required.
7. A changed transform-agreement version changes the appropriate v2 model
   identity, while all v1 JSON and hashes remain byte-identical.
8. A two-joint hierarchy with multi-member root, A, and B bodies: J1 moves all
   A and B members; J2 moves only B members.
9. A branching body tree with two independent child groups.
10. Every body/member/schema/topology/exact-pair failure listed above.
11. Body/model hashes independent of body/member tuple order but changed by body
   IDs, membership, reference member, static offset, and body endpoints.
12. Concrete transformed assembly and M10-3 v2 coverage for articulated versus
   root, articulated versus articulated, sibling articulated bodies, and an
   ancestor/descendant pair.
13. Explicit same-body pair retention/classification through the existing M12
    inventory semantics; a same-body v2 exact pair is rejected rather than
    silently measured as external collision.
14. V2 pair-scope canonicalization and hash equality under caller pair tuple
    reorder; changed pair inventory changes the request hash; duplicate unordered
    pair and self-pair reject.
15. V2 exact witness/result IDs remain concrete `first_instance_id` and
    `second_instance_id`, including a pair with two articulated endpoints.
16. Exact discrete collision for a grouped moving body and continuous M10-4 path
    proof for a grouped pair whose two endpoints both have articulated ancestry.
17. V1 M10-3/M10-4 golden request/result JSON and hashes remain byte-identical.
18. A higher-level full inventory can route every cross-body `CHECK_CLEARANCE`
    pair to generic v2 execution without another M10 pair-scope change.
19. Regression proving `OUTPUT_RIGID` remains adapter metadata and is not
    silently interpreted as a generic M10 body.

## Live Acceptance Target

Use deterministic simple CAD geometry through the existing real FreeCAD path:

```text
root body R: R1, R2 (fixed)
  -> J1
body A: A1, A2
  -> J2
body B: B1, B2
```

The focused acceptance must prove with live FreeCAD transient measurement that:

- q=0 rigid-transform-agrees with all six source placements under
  `rigid-transform-agreement@1.0`;
- J1 moves all A and B constituents while retaining A1/A2 and B1/B2 relative
  transforms;
- J2 changes B constituents but not A constituents;
- an articulated-root exact pair and the explicit articulated-articulated pair
  `A2 <-> B1` are sent to the exact provider as concrete canonical pairs;
- `A2 <-> B1` has a known exact clearance or interference outcome, both A and B
  poses are from the same FK-transformed assembly, and its v2 result/witness
  retains `A2` and `B1` IDs without a false stationary label; and
- an explicit grouped-child M10-4 v2 pair with articulated ancestry on both
  sides executes through unchanged conservative path semantics.

The fixture has no physical interface, candidate, canonical, promotion, or
M13-3 authority. It is only a generic M10/CAD grouping acceptance.

## Remaining Boundaries

This prerequisite says nothing about whether physical components are truly fixed
together, which body a physical component belongs to, or which interfaces
authorize a joint axis. Those are future M13-3 bridge facts. It also does not
make an all-configuration-space clearance claim: M10-3 remains discrete and
M10-4 proves only its requested explicit path.

## Acceptance Criteria

M13-3P is implementation-ready only if an implementation can demonstrate all
of the following without algorithm replacement:

- v2 has an explicit, hash-bound body/member/reference-offset model;
- legacy v1 JSON/hash/results remain exact;
- v2 joints are unambiguously body-level;
- q=0 geometrically agrees with source placements under the named
  transform-agreement policy;
- existing FK alone computes body hierarchy and projects every constituent;
- generic v2 pair scope executes every required cross-body constituent pair,
  including articulated-articulated, sibling, and ancestor/descendant pairs;
- concrete constituent geometry, pair coverage, and witness identity survive;
- same-body pair disposition is explicit at the existing caller inventory
  boundary rather than silently removed;
- M10-4 v2 scope supports two-moving-side pairs while its proof mathematics
  remains unchanged; and
- M13-3 can lower its declared rigid groups without another generic M10 change.

## Self-Review

- No anonymous compound or pseudo-component replaces a constituent.
- No false or duplicated revolute DOF represents fixed membership.
- A member has exactly one v2 body; all v2 assembly members are covered.
- q=0 is named rigid-transform agreement, not literal floating-value equality
  or a geometry-derived approximation.
- Member offsets are explicit and hash-bound, then validated against assembly
  transforms; they are never inferred from geometry.
- FK traversal remains in `MultiJointKinematicsService`; member projection is
  not a second kinematics engine or descendant traversal.
- Articulated-articulated pairs are not lost because both endpoints move; M10-3
  and M10-4 v2 choose concrete exact pairs independently of articulation.
- V2 results never call a moving second operand stationary; v1 directional
  JSON/hash semantics remain unchanged.
- M10-3 exact classification and M10-4 proof mathematics remain unchanged.
- `OUTPUT_RIGID` is audited as bounded adapter metadata, not assumed generic.
- Legacy hashes are preserved by explicit v1 serializer/hash branches, not
  optional-field omission.
- Group membership contributes to model/request/result currentness through the
  existing hash chain, and v2 pair scope is hash-bound in both analyses.
- No M13 physical authority, candidate/canonical semantics, M11, or
  Rotator-specific behavior leaks into the generic prerequisite.
