# M10-4 Continuous Multi-Joint Path Clearance Proof

## Status and Scope

This specification defines M10-4, a conservative proof for one explicitly
requested continuous path through the accepted M10-2 revolute joint model. It
does not certify a configuration-space box, arbitrary combinations of joint
values, a swept volume, or an entire N-dimensional region.

The requested path is an ordered sequence of at least two
`JointConfiguration` waypoints:

```text
Q0 -> Q1 -> ... -> Qn
```

Each adjacent pair is a separate segment. The complete proof concerns exactly
the piecewise-linear interpolation of those segments in raw joint command
space. The accepted outcomes are:

- `VERIFIED_CLEAR`: every point on every requested segment is proven to have
  distance strictly greater than the requested clearance;
- `COLLISION_WITNESS`: an exact evaluated waypoint or midpoint configuration
  violates the requested property;
- `NOT_PROVEN`: no exact violation was found, but one or more path intervals
  could not be certified within the configured proof limits.

This milestone proves geometric clearance only for represented rigid CAD
geometry, the represented revolute model, the requested path, exact FreeCAD
measurement semantics, and the conservative bounds defined below. It does not
prove dynamics, tracking, compliance, backlash, bearing play, cables,
temperature, vibration, tolerances, or manufacturing approval.

## Path Semantics

`MultiJointPath` is a typed value containing the model identity and an ordered
tuple of `JointConfiguration` waypoints. It rejects fewer than two waypoints,
model mismatches, missing or extra joint IDs, non-finite values, and values
outside the accepted joint limits. Waypoint order is semantic and is included
in request identity.

For segment `s` with endpoints `Qa` and `Qb`, and normalized parameter
`t in [0,1]`, each joint command is interpolated as:

```text
qj(t) = qj,a + t * (qj,b - qj,a)
```

Angles are raw commanded values. They are not modulo-normalized, shortest-path
wrapped, or otherwise geometrically canonicalized. Thus `350 -> 10` means
`-340` degrees, while `350 -> 370` means `+20` degrees, and `0 -> 720`
represents two commanded revolutions. The configuration hash and path request
hash preserve those distinctions.

Because each scalar interpolation is a convex combination of its two endpoint
values, endpoint validation is sufficient for ordinary closed scalar joint
limits: if both endpoints are in `[min,max]`, every interpolated value is also
in `[min,max]`. No clamping or wrapping is performed.

## Exact Measurement and Witness Semantics

Every requested waypoint is evaluated exactly before recursive certification.
The same exact configuration cache is used by all segment boundaries and
midpoints. Each exact evaluation starts from the unchanged source assembly,
uses M10-2 forward kinematics, creates a transient transformed assembly, and
uses the existing M10-3-compatible transient exact provider. The provider
must execute real `common().Volume` and `distToShape()` in live production
composition.

For every required ordered pair `(A,B)`, the exact provider returns interference
volume and distance. Existing classification semantics are reused:
`INTERFERENCE`, `TOUCHING`, and `POSITIVE_CLEARANCE`.

The requested property is strictly:

```text
exact_distance_mm > required_clearance_mm
```

Therefore an exact evaluated configuration is an immediate
`COLLISION_WITNESS` when any pair is `INTERFERENCE`, `TOUCHING`, or has
`exact_distance_mm <= required_clearance_mm`, even when its existing geometric
classification is `POSITIVE_CLEARANCE`. `proof_guard_mm` is not part of this
exact witness threshold. For example, with required clearance `5.0`, proof
guard `0.1`, and exact distance `5.05`, there is no exact witness; the interval
may simply fail its conservative certificate and require subdivision.

A witness retains segment index, normalized path parameter, interpolated
configuration and hash, transformed assembly hash, pair IDs, interference
volume, exact distance, and classification.

## Exact-Evaluation Budget

`max_exact_evaluations` counts every unique configuration for which the exact
provider is actually invoked. Mandatory waypoint evaluations and recursive
midpoint evaluations both consume one unit. A cache hit consumes no unit.
The cache is local to one proof request and is never persisted globally.

The proof checks the budget before invoking the provider. If a needed unique
configuration cannot be evaluated, the affected interval is recorded as
unresolved and the final result is `NOT_PROVEN`. Resource exhaustion can never
produce `VERIFIED_CLEAR`.

The cache key contains the source assembly hash, model hash, complete
configuration hash, ordered pair partition, and exact measurement tolerances.
The cache is keyed by semantic request context, not by temporary files,
timestamps, process IDs, or runtime paths.

## Conservative Reach Bounds

The proof uses a versioned reach-bound algorithm:

```text
articulated-descendant-reach-bound@1.0
```

For each component part, define a stable component-local reference origin as
the local origin of the source `CadComponentInstance` placement. Load the
exact component geometry in its component-local frame. Compute a conservative
local geometry radius `rho_i` as the maximum Euclidean norm of the eight exact
shape bounding-box corners from that local origin, plus explicit numerical
padding. The bounding box contains every represented shape point, so `rho_i`
is an upper bound on the distance from the component-local origin to every
point of the component geometry. Generated and trusted imported components use
the same exact-shape bounding-box procedure; the local component identity is
bound into the evidence.

For an influencing ancestor joint `j` and descendant instance `i`, follow the
unique M10-2 parent chain from the child of `j` to `i`. Construct a sequence of
fixed reference points consisting of:

1. the origin of joint `j` in its parent-instance-local frame;
2. the child-instance reference origin expressed in the same parent frame;
3. for each subsequent joint on the unique chain, that joint's axis origin in
   the current parent-instance-local frame and the next child-instance
   reference origin in that same frame;
4. the descendant instance-local reference origin.

The implementation sums the Euclidean lengths of each consecutive fixed rigid
link offset along this chain, then adds `rho_i`:

```text
R(i,j) = padding + rho_i + sum_k ||offset_k||
```

The exact implementation records the ordered joint/instance chain and every
numeric offset length. Each offset is expressed between two reference points
attached to the same rigid parent or child link. Joint rotations change the
orientation of that link but preserve the Euclidean length of every offset.
Consequently every offset length is invariant under all articulated rotations.
The chain sum plus the descendant local geometry radius therefore bounds the
Euclidean distance from the current axis origin of `j` to every point of
instance `i` for every configuration allowed by the requested path. Perpendicular
distance to the joint axis is no greater than this Euclidean distance, so
`R(i,j)` is also a conservative axis-radius bound.

An instance not descended from joint `j` has `R(i,j)=0`. A root or otherwise
unarticulated instance has no influencing joints and therefore has total motion
bound zero. No source-world-origin distance is used as a reach proof.

The result contains auditable reach-bound records with instance ID, influencing
joint ID, numeric bound, chain identity, local geometry radius, offset lengths,
source component identity, and algorithm version.

## Hierarchical Motion Proof

Consider a path subinterval `[t0,t1]` of one linear segment, with midpoint
`tc=(t0+t1)/2`. Let `Qc` be the exact midpoint configuration and `Q` any
configuration on the subinterval. For joint `j`:

```text
delta_j = abs(q_j(t1) - q_j(t0)) / 2
         = abs(q_j,b - q_j,a) * (t1-t0) / 2
```

converted to radians before the chord formula. This remains valid for raw
changes greater than 180 degrees and multiple revolutions because the chord
bound caps at `2R`:

```text
C(R, delta) = 2 R sin(min(abs(delta), pi) / 2)
```

To account explicitly for hierarchical axis motion, order the influencing
joints deterministically along the validated ancestor chain and construct
intermediate configurations:

```text
Q^(0) = Qc
Q^(1) = Qc with joint j1 changed to Q's value
Q^(2) = Q^(1) with joint j2 changed to Q's value
...
Q^(m) = Q
```

At step `r`, all other joint commands are held fixed. The M10-2 hierarchy
therefore evaluates the descendant as a rigid body rotated about the current
world placement of joint `jr`'s axis. The configuration-independent reach
bound remains valid at that current placement because it was derived from
invariant rigid-link lengths, not a midpoint pose. Every point displacement in
that step is bounded by:

```text
||x^(r) - x^(r-1)|| <= C(R(i,jr), delta_jr)
```

where the per-step command difference is no larger than the full subinterval
deviation `delta_jr`. Telescoping the same material point through the
intermediate configurations gives:

```text
||x(Q) - x(Qc)||
  <= sum_r ||x^(r) - x^(r-1)||
  <= sum_j C(R(i,j), delta_j)
```

This is the required hierarchical proof: ancestor axes may move with earlier
steps, but each step is bounded about its current axis, and the sum remains
conservative by telescoping plus the triangle inequality. Contributions are
only from the actual ancestor chain; branches do not contribute.

For body `i`, define:

```text
B_i = sum over influencing joints j of C(R(i,j), delta_j)
```

For a required pair `(A,B)`, either side may move. Applying the pointwise
displacement bound to both shapes and the triangle inequality for their
closest-point separation yields:

```text
d(A(Q), B(Q)) >= d(A(Qc), B(Qc)) - B_A - B_B
```

The relative motion bound is therefore required to use:

```text
pair_motion_bound = B_A + B_B
certified_lower_clearance = exact_distance_at_midpoint - pair_motion_bound
```

This remains correct when both pair sides are articulated. A truly fixed body
has `B=0` naturally.

## Adaptive Certification

For every candidate interval, the service evaluates the exact midpoint unless
it is already cached. An exact witness immediately terminates deterministic
lower-first traversal with `COLLISION_WITNESS`. Otherwise, for every required
pair it computes the lower bound above. The interval is a certified leaf only
when every pair satisfies:

```text
certified_lower_clearance > required_clearance_mm + proof_guard_mm
```

If any pair fails, the service subdivides the lower half first, then the upper
half, unless `max_depth`, `minimum_path_interval`, or exact-evaluation budget
prevents further proof. A bound failure is never classified as a collision.
It becomes an unresolved leaf and causes `NOT_PROVEN` if it cannot be resolved.

Each certificate records segment index, interval endpoints, midpoint parameter,
reference configuration/hash, transformed assembly hash, pair IDs, exact
distance, `B_A`, `B_B`, pair bound, lower clearance, and the reach-bound table
identity. Each unresolved leaf records the same reference data, failed pair
bound, reason, and whether a resource limit was reached.

`VERIFIED_CLEAR` requires all segments to have certified leaves whose ordered
intervals begin at `0`, end at `1`, and have no gaps or inconsistent overlaps.
The final result validates this complete coverage explicitly rather than
assuming recursion implies it. A clear segment cannot hide an unresolved
segment.

## Typed Requests, Results, and Identity

`MultiJointContinuousPathRequest` includes source assembly identity, model hash,
ordered waypoint configuration hashes, interpolation algorithm/version,
collision partition, exact tolerances, required clearance, proof guard, reach
bound algorithm/version, and all resource limits affecting semantics. Its
request hash is deterministic and order-sensitive.

`MultiJointContinuousClearanceProofResult` is separate from
`MultiJointCollisionSweepResult`. It includes status, source/model/path
identities, proof and reach-bound versions, ordered segment results, exact
evaluation identities, certified and unresolved leaves, optional exact witness,
minimum certified lower clearance when meaningful, `continuous_path_verified`,
and a deterministic result hash.

The continuous flag is true only for `VERIFIED_CLEAR` with validated complete
coverage. It is false for `COLLISION_WITNESS` and `NOT_PROVEN`. M10-3 remains
unchanged and always has `continuous_path_verified=False`.

Identity excludes timestamps, temporary paths, process IDs, and runtime
incidental data. Reversing waypoints changes the request and result identities.
Repeated semantic execution produces the same traversal, certificate ordering,
and hashes.

## Production Boundary, Provenance, and Atomicity

The production entrypoint is a narrow
`ProductionApplication.prove_continuous_multi_joint_path_clearance(...)` method.
The caller supplies source binding, source assembly, model, typed path,
partition, required clearance, and resource parameters. The caller cannot
supply algorithm versions, provider/backend/runtime identity, result hashes,
reach bounds, or a claimed status.

The service reuses M10-2 FK, the generic transient analysis service, the M10-3
pair inventory/classification logic, and the default
`FreeCADTransientAssemblyMeasurementProvider`. Midpoint geometry is disposable;
there are no per-midpoint public Evidence records, FCStd files, or STEP files.

Only after complete request validation, reach-bound derivation, adaptive
execution, result validation, and result hashing does the application persist
one durable M10-4 proof Evidence record. A provider/runtime failure or Evidence
write failure publishes no accepted partial proof.

Trusted provenance binds source assembly hash, model hash, path/request hash,
proof result hash, proof algorithm, reach-bound algorithm, exact provider and
version, backend identity/version, actual FreeCAD runtime/library version, and
execution mode. Existing M9, M10-1, and M10-3 provenance serialization and
semantic hashes remain compatible.

The proof is analysis-only. It does not mutate `DesignState`, create proposals
or revisions, alter waypoints, select limits or clearance, optimize paths, or
avoid collisions automatically.

## Testing and Live Acceptance

Deterministic tests cover path interpolation and identity, mapping-order
independence, raw 0/360/720 values, limits and invalid values, serial and
branching ancestry, two-joint coupling, zero-motion and unrelated joints,
fixed instances, arbitrary axes, both moving pair sides, large angles, reach
bound conservativeness, immediate and subdivided clear proofs, exact requested
clearance witnesses, waypoint witnesses, unresolved budgets, complete coverage,
deterministic traversal/hashes, exact M10-3 compatibility, and provenance
spoof resistance.

The live fixture reuses the accepted generated base plus trusted imported STEP
component and two-joint serial hierarchy. It must demonstrate:

1. a non-zero path where both dependent joints change and the complete path is
   `VERIFIED_CLEAR` using real `common().Volume` and `distToShape()`;
2. a path containing a real exact interference or requested-clearance witness;
3. a no-witness path forced to `NOT_PROVEN` by an intentionally insufficient
   exact-evaluation budget.

The live `NOT_PROVEN` case must first execute at least one real exact FreeCAD
evaluation, including real `common().Volume` and `distToShape()`, and must find
no exact requested-clearance violation. Its intentionally insufficient budget
must then prevent certification of at least one remaining interval, producing
unresolved-leaf evidence rather than an early pre-provider budget failure.

The live report records waypoints, deltas, exact unique evaluations, cache hits,
reach bounds, subdivision depth, leaf coverage, lower-clearance minimum,
witness measurements, result/provenance identities, and the actual FreeCAD
runtime.

## M10-5 Boundary

M10-4 ends with continuous clearance proof along an explicit piecewise-linear
multi-joint joint-space path. M10-5 system acceptance is a separate milestone
and is not implemented or claimed here. Whole configuration-space certification,
free-form trajectories, dynamics, FEA, manufacturing validation, optimization,
and automatic synthesis remain outside this specification.

## Mathematical Self-Review Gate

1. **Is every `R(i,j)` conservative over the path?** Yes. It is derived from
   exact component-local geometry and invariant fixed-link Euclidean offsets
   along the actual ancestor chain, plus explicit padding, and is not based on
   a midpoint pose.
2. **Is hierarchical composition covered?** Yes. Intermediate configurations
   change one influencing joint at a time; each step is a rigid rotation about
   that joint's current axis, and telescoping bounds the total displacement.
3. **Is summation conservative?** Yes. It is the triangle inequality applied
   to the telescoping sequence for each material point.
4. **When both bodies move, is `B_A+B_B` used?** Yes, explicitly in the pair
   relative-motion inequality.
5. **Are large and multi-turn commands conservative?** Yes. Raw deltas are
   preserved and the chord formula caps each contribution at `2R`.
6. **Does subdivision preserve coverage?** Yes. Every non-certified interval
   splits into adjacent lower and upper halves; final ordered leaf coverage is
   independently validated.
7. **Can resource exhaustion yield `VERIFIED_CLEAR`?** No. A needed uncached
   evaluation that exceeds budget creates an unresolved leaf and forces
   `NOT_PROVEN`.
8. **Can a bound failure be called a witness?** No. Only exact evaluated
   `INTERFERENCE`, `TOUCHING`, or `exact_distance <= required_clearance_mm`
   creates a witness; `proof_guard` is excluded from this exact test.

All eight answers are proven by the defined construction. Implementation must
stop with `M10_4_NEEDS_FIXES` if any invariant cannot be maintained.
