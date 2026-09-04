# MechCAD M13-3P Completion Report

## Final Marker

`M13_3P_GENERIC_M10_RIGID_BODY_CONSTITUENT_GROUP_VERIFIED`

## Scope

M13-3P adds generic M10 v2 rigid-body constituent groups while preserving the
literal M10 v1 wire formats, hashes, forward-kinematics path, exact collision
classification, and continuous-clearance mathematics. It does not add M13
physical authority, candidate/canonical semantics, M11, Rotator behavior, or
automatic group discovery.

## Verification Environment

- Platform: win32
- Python: 3.14.6
- Pytest: 8.4.2
- FreeCAD backend/library: 1.1.3
- FreeCAD executable: `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`
- Live execution boundary: `freecadcmd-subprocess`
- Full-suite ceiling: 5,000 seconds, above the required 4,500 seconds

## Task 0 V1 Evidence

The immutable `tests/unit/test_m13_3p_legacy_goldens.py` suite passed 10/10
after every stage. It locks v1 joint/model JSON, model hashes, one- and
two-joint FK results, M10-3 request/result payloads and hashes, M10-4
request/result payloads and hashes/digests, and all five v1 identity literals.
No v1 JSON, hash, result, request, directional pair label, or proof identity
drifted. The temporary capture helper is absent.

## Transform Agreement

The one frozen policy is `rigid-transform-agreement@1.0`:

- Translation: componentwise maximum absolute error in mm, inclusive `<= 1e-9`.
- Orientation: sign-invariant normalized-quaternion angle in radians, inclusive `<= 1e-7`.
- Inputs must be finite; the shared `normalize_quaternion` helper is used.
- The metric is `2 * acos(clamp(abs(dot(q1, q2)), 0, 1))`.
- q and -q are equivalent; no rounding, hash comparison, geometry query, or caller epsilon is used.

Identity, arbitrary quaternion round trip, floating reconstruction, threshold
boundary, non-finite, sign-equivalence, and materially wrong placement tests
all passed.

## V2 Body Model

`KinematicRigidBodyMember` carries an explicit full-precision member offset.
`KinematicRigidBody` carries body ID, reference member, complete member set,
canonical ordering, and a semantic body hash. Membership is unique and covers
the source assembly exactly once. Reference offsets require literal identity;
other offsets are checked against source placements under the frozen policy.

V2 joints use body endpoints only. Body and joint records are canonicalized by
stable IDs and semantic model identity binds body hashes, offsets, endpoints,
axes, limits, evaluator version, and transform-agreement version.

## FK And Q0

The existing `MultiJointKinematicsService` remains the sole FK engine. V2
topology is a deterministic rooted forest over bodies, with sorted roots and
breadth-first joint traversal. One body-world transform is projected to every
concrete `CadComponentInstance` in source order. No compound or implicit fixed
joint is introduced.

The six-member live hierarchy is `R=(R1,R2) -> J1 -> A=(A1,A2) -> J2 ->
B=(B1,B2)`. Tests prove J1 moves A/B, J2 moves B only, roots remain fixed, and
relative member poses remain invariant under the policy. q=0 policy agreement
passes for all six members. The transformed assembly retains its truthful
derived hash and is not replaced with the source assembly.

## Exact Pair And M10-3

`ExactConstituentPair` is a neutral canonical concrete pair primitive. V2 scope
rejects empty, blank, self, duplicate-unordered, unknown, and same-body pairs.
Cross-body scope accepts root/articulated, articulated/articulated, sibling,
ancestor/descendant, and separate-branch pairs.

V2 M10-3 sends canonical concrete pairs to the existing transient service and
existing FreeCAD exact measurement. `common().Volume`, `distToShape()`, and
`CollisionClassification.from_measurement` remain the exact measurement and
classification path. V2 result records use `first_instance_id` and
`second_instance_id`; no false stationary label exists.

The live test measured both the root/articulated pair and articulated pair
`A2/B1`. Captured live result hash:
`sha256:534a0efbcd14f32168b640ef30021b74a7e6d150cccd23cc64e0ad1272a96417`.

## Continuous M10-4 And Reach

V2 M10-4 preserves
`conservative-multi-joint-path-clearance-proof@1.0`, piecewise-linear path
interpolation, subdivision order, exact sampling, and resource semantics.
V2 records are neutral concrete pair records, including the articulated/
articulated `A2/B1` witness.

Reach input plumbing is explicitly
`body-member-reach-bound-plumbing@2.0`. Both endpoint bounds are independently
derived and the existing pair equation remains `B_A + B_B`; lower clearance
remains `distance - relative`. Clear and required-clearance witness paths both
passed. Captured live hashes:

- Clear result: `sha256:f42fd5a8f4932781fe418bc73b55c828affcb78d5dff916e715f869cd433a405`
- Witness result: `sha256:5dbf3fc95f11b635b13ed484b23066d79d6021f077e18fe47470b66c20d2059e`
- Witness pair: `A2`, `B1`

## Production API And Provenance

Explicit typed v2 APIs were verified for M10-3 and M10-4. V1 and v2 model
versions are rejected by the opposite API, and callers cannot override
provider, backend, evaluator, or trust identity. Configuration evaluation uses
the existing FK service for both versions.

Live provenance bound source/model/request/result identities to provider
`freecad-transient-exact`, version `mechcad-freecad-transient@1.0`, execution
`freecadcmd-subprocess`, and FreeCAD 1.1.3. V2 continuous evidence reloads
through explicit schema dispatch and verifies the v2 outer result hash.
The live discovery record's `runtime.version` was `null`; the trusted backend
provenance's exact `library_version` was `1.1.3`.

## Regression Results

- Stage A grouped-body module: 110 passed.
- Stage B grouped membership/topology/FK/q=0: 17 passed.
- Stage C pair scope/M10-3 v2: 19 passed.
- Stage D M10-4 v2/reach: 19 passed.
- Historical M10/M12/transient groups: 84 + 11 + 18 + 21 + 60 + 7 passed.
- Live grouped-body FreeCAD acceptance: 1 passed, 0 skipped.
- Full suite: 2,524 collected, 2,490 passed, 34 unrelated runtime-gated skips, 0 failed, 0 errors, 3,268.01 seconds.

The required M13-3P positive path was not skipped.

## Static And Dependency Gates

- `py -3 -m compileall -q src/mechcad_harness tests`: passed.
- `git diff --check`: passed.
- Relevant changed-path whitespace scan: 0 trailing-whitespace findings.
- Relevant changed-text EOF scan: 0 failures.
- Dependency manifests changed: 0.
- Forbidden generic-module imports: 0.
- Protected AST definitions `axis_rotation_transform`,
  `_build_kinematic_topology`, `collision_pairs`, and `MultiJointPath.interpolate`
  are equivalent to HEAD.
- The single `distance - relative` formula remains present and unchanged.
- No alternate FK/collision/proof engine, compound body, fake joint, M13
  physical authority, M11/Rotator implementation, or new dependency was added.

## Relevant Files

Production files:

- `src/mechcad_harness/analysis_provenance.py`
- `src/mechcad_harness/application.py`
- `src/mechcad_harness/multi_joint_collision_sweep.py`
- `src/mechcad_harness/multi_joint_continuous_clearance.py`
- `src/mechcad_harness/multi_joint_continuous_path.py`
- `src/mechcad_harness/multi_joint_kinematics.py`
- `src/mechcad_harness/multi_joint_pair_scope.py`
- `src/mechcad_harness/transient_assembly_analysis.py`
- `src/mechcad_harness/transient_freecad_measurement.py`

Test files:

- `tests/unit/test_m13_3p_legacy_goldens.py`
- `tests/unit/test_m13_3p_rigid_body_groups.py`
- `tests/integration/test_m13_3p_live_grouped_body_freecad.py`
- `tests/integration/test_m10_3_provenance.py`
- `tests/integration/test_m10_4_provenance.py`
- `tests/unit/test_transient_freecad_measurement.py`

## Remaining Boundaries And M13-3 Handoff

M10-3 remains discrete and M10-4 proves only the explicitly requested path.
This prerequisite does not infer physical fixed membership, physical joint
authority, candidate/canonical projection, tolerance approval, FEA, materials,
manufacturing approval, optimization, or all-configuration-space clearance.

M13-3 can now lower explicit stable body IDs, complete CAD member sets,
full-precision reference offsets, body-level revolute endpoints, and every
caller-selected cross-body `CHECK_CLEARANCE` pair into the generic v2 M10
surface without another generic M10 body-model change.

## Worktree Note

The task-relevant change set passed the required static gates. The pre-existing
dirty worktree also contains unrelated generated/Rotator artifacts under
`projects/`; a separate broad scan found 19 trailing-whitespace and 10
final-newline findings there. Those files were not modified because the task
explicitly prohibits destructive cleanup operations.

## Conclusion

All M13-3P functional, live, compatibility, provenance, static, dependency,
and protected-region gates passed for the relevant change set. The marker above
is authorized.

## Final-Review Important Finding Repair

Date: 2026-09-04

The final-review trust-boundary finding is closed. Every v2 execution/request
boundary now reconstructs `KinematicModelV2` from serialized semantic fields,
thereby revalidating nested body/member/joint records. Exact schema, evaluator,
and transform-agreement versions are enforced. Body identity is recomputed from
canonical semantic fields and compared with the supplied finalized `body_hash`;
`kinematic_model_hash()` no longer silently trusts stale stored body hashes.
V2 FK, M10-3 request/provider dispatch, M10-4 request/extent/proof dispatch,
parsers, wire identity, reach-bound setup, and production API gates all consume
the strict model boundary. Forged copies and stale hashes fail before FK,
extent, proof, or exact-provider work.

New adversarial tests cover `model_copy` and `object.__setattr__` alteration,
stale body hashes, invalid schema/evaluator/agreement versions, nonzero FK
rejection, and nonzero M10-3/M10-4 rejection before provider callbacks. V1
serializers, hashes, wire bytes, protected M10 math, provenance paths, and live
FreeCAD behavior remain unchanged.

Repair verification: focused M13-3P/M10 suites 224 passed; immutable v1
goldens independently 10 passed; M10-3/M10-4 provenance 59 passed; live
grouped-body FreeCAD acceptance 1 passed with no skip; and compileall passed.

The post-remediation fresh full-suite command passed 2,490/2,524 tests with
34 unrelated skips, 0 failures, and 0 errors in 3,268.01 seconds.
