# M10-1: Continuous Single-Axis Collision / Clearance Proof

**Date:** 2026-08-22
**Status:** design record (before implementation)

## 1. Problem Definition

M9 established discrete exact kinematic sweep (continuous_sweep_verified = False).
Dense sampling cannot certify continuous clearance between samples.
M10-1 addresses this for ONE generic revolute axis using a mathematically
conservative continuous clearance proof.

## 2. Rejected Approaches

- Dense fixed-angle sampling: No inter-sample guarantee; not a continuous proof.
- Adaptive sampling without conservative geometric bound: Refinement alone still
  does not prove what occurs between samples.
- Swept-volume / true continuous CCD: Overkill for the current single-axis rigid
  model; architecture overhead not justified.

## 3. Selected Proof Strategy

Conservative interval certification using exact clearance at a reference point
plus an upper bound on rigid-body displacement (chord bound). Adaptive
subdivision refines intervals that cannot be certified.

## 4. Mathematical Proof Obligation

For one moving rigid component rotating about a fixed revolute axis:

- M(theta) = moving geometry at angle theta; S = stationary geometry
- Reference angle c: d_c = exact min distance(M(c), S)
- R = conservative max distance(point, revolute_axis) for every point of M
- motion_bound(R, delta_theta) = 2R sin(min(|delta_theta|, pi) / 2)
- For interval [a,b] with midpoint c and half_span h = |b-a|/2:
  B = motion_bound(R, radians(h))
  For all theta in [a,b]: d(theta) >= d(c) - B
  If d(c) - B > required_clearance + proof_guard for every pair: interval certified

The pi cap in motion_bound correctly limits the maximum chord displacement to
2R for any angular excursion including multi-turn intervals.

## 5. Conservative Geometry Radius Bound

R is derived from the exact transformed shape's bounding box in FreeCAD:
Shape -> BoundBox -> 8 corners -> point-to-axis distance -> max.
Since the shape is contained in its bounding box and distance-to-line is
convex, the max is attained at a corner.
Small numerical padding (1e-9 mm) is applied for floating-point safety.

## 6. Outcome Classes

- VERIFIED_CLEAR: entire requested interval conservatively proven to maintain
  required positive clearance.
- COLLISION_WITNESS: at least one exact evaluated configuration contains
  touching or interference.
- NOT_PROVEN: no collision witness found, but conservative proof could not
  certify the entire interval within configured resource limits.

## 7. Tolerance / Guard Semantics

- required_clearance_mm: caller-supplied engineering input (default 0 for
  strictly positive clearance)
- proof_guard_mm: safety margin absorbing floating-point rounding (default 1e-6)
- Motion bound numerical pad: 1e-9 * (1 + R) mm
- Radial bound numerical pad: 1e-9 mm
- Classification tolerances: volume_tolerance_mm3=1e-9, distance_tolerance_mm=1e-7
- Touching is NOT positive clearance; touching triggers COLLISION_WITNESS

## 8. Typed API Design

- ContinuousSingleAxisProofRequest: source, axis, interval, partition, resources
- ContinuousSingleAxisProofResult: status, certificates, witness, provenance
- ContinuousIntervalCertificate: per-leaf interval data
- ContinuousPairCertificate: per-pair lower bound proof
- ContinuousCollisionWitness: exact witness data

## 9. Provenance Strategy

Companion ContinuousProofExecutionProvenance with proof_algorithm_version.
Durable Evidence (kind analysis.continuous_clearance_proof) binds
proof_request_hash, proof_result_hash, source_assembly_hash, provider,
backend, and runtime identity. Does not break M9-4 compatibility.

## 10. Out of Scope

Single axis only. No multi-axis, FEA, materials, manufacturing, tolerance,
dynamics, optimization, collision avoidance, or mechanism synthesis.
