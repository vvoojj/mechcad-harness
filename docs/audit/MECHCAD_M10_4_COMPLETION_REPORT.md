# M10-4 Completion Report - Continuous Multi-Joint Path Clearance Proof

## Final Disposition

**`M10_4_CONTINUOUS_MULTI_JOINT_PATH_CLEARANCE_PROOF_VERIFIED`**

M10-4 proves conservative geometric clearance along one explicit requested
piecewise-linear path in raw multi-joint command space. It does not certify an
entire configuration-space region.

## Baseline and Scope

The accepted predecessor baselines remain intact:

- `M9_FULLY_CLOSED_LIVE_VERIFIED`
- `M10_1_CONTINUOUS_SINGLE_AXIS_CLEARANCE_PROOF_VERIFIED`
- `M10_2_GENERIC_MULTI_JOINT_KINEMATICS_VERIFIED`
- `M10_3_MULTI_JOINT_EXACT_DISCRETE_COLLISION_VERIFIED`

M10-3 remains discrete-only with `continuous_path_verified=False`.

`MultiJointPath` uses ordered raw piecewise-linear joint-command interpolation.
The live clear path was:

```text
Q0 = (joint-1=0 deg,  joint-2=0 deg)
Q1 = (joint-1=20 deg, joint-2=20 deg)
```

Both dependent serial joints changed simultaneously. `path_hash` and
`request_hash` are distinct identities; waypoint order is semantic.

## Mathematical Proof

The trusted geometry extent boundary returns a component-local bounding-box
corner radius `rho_i` plus numerical padding. Pure topology derives:

```text
R(i,j) = rho_i + padding + sum_k ||offset_k||
```

For a candidate interval midpoint:

```text
delta_j = abs(q_j,b - q_j,a) * (t1 - t0) / 2
C(R, delta) = 2 R sin(min(abs(delta), pi) / 2)
B_i = sum_j C(R(i,j), delta_j)
```

The hierarchical bound is justified by changing one influencing joint at a
time from the midpoint configuration to an arbitrary target configuration.
Each step is a rigid descendant rotation about that joint's current axis, and
the telescoping triangle inequality gives the summed body displacement bound.
For every pair:

```text
pair_motion_bound = B_A + B_B
certified_lower_clearance = exact_distance_at_reference - pair_motion_bound
```

Certification requires `lower > required_clearance_mm + proof_guard_mm` for
every pair. An exact witness is `INTERFERENCE`, `TOUCHING`, or
`exact_distance_mm <= required_clearance_mm`; `proof_guard_mm` is not part of
that exact witness threshold.

## Typed and Durable Architecture

- `MultiJointPath` and `MultiJointContinuousPathRequest` define typed path and
  request identity.
- `TrustedLocalGeometryExtent` is owned by production geometry composition;
  pure topology code does not open STEP/FCStd files or call FreeCAD.
- `derive_reach_bounds` produces auditable topology chain records.
- `MultiJointContinuousClearanceProofService` records every unique exact
  provider invocation in `exact_evaluations`, including waypoints and
  non-leaf subdivision midpoints. Cache hits do not create records.
- `MultiJointContinuousClearanceProofResult` contains exact evaluations,
  certificates, unresolved leaves, reach bounds, and witness payload.
- The final typed result is serialized inside the one M10-4 Evidence record as
  `continuous_multi_joint_clearance_proof_result_payload`.
- `ProductionApplication` persists the complete result payload and provenance
  together through the existing atomic `EvidenceStore` boundary.

## Live Fixture and Provenance

The accepted generated mounting plate plus trusted imported STEP fixture was
used with:

```text
base -> joint-1 -> link-1 -> joint-2 -> link-2
```

Required pairs were `link-1/base` and `link-2/base`. Live measurement used real
FreeCAD `common().Volume` and `distToShape()`.

All three persisted M10-4 Evidence records reported:

```text
proof algorithm: conservative-multi-joint-path-clearance-proof@1.0
reach-bound algorithm: articulated-descendant-reach-bound@1.0
provider: freecad-transient-exact / mechcad-freecad-transient@1.0
backend: freecad / mechcad-freecad@2.1
library: FreeCAD 1.1.3
execution mode: freecadcmd-subprocess
```

The persisted identity bindings were:

| Outcome | Evidence ID | Source assembly hash | Model hash | Path hash | Request hash | Result hash |
|---|---|---|---|---|---|---|
| `VERIFIED_CLEAR` | `EVD-MJCP-cbf77d93b4b9bfd522a1a80e` | `sha256:73c89f2616211322fb363a389e129664671be146bc5c5f39e98e56c39bb08d37` | `sha256:94af0ddc4892fea06e4dc2c890f3e93adb967a24118714029592b44411cab995` | `sha256:8e053f6ba0154752af144f67c8e08c1f71812957412fe38f309cff1af55497db` | `sha256:91ced503c453c4e9b73484eaae8eddcfc5b673f1ae7f573480dcc53ae8351156` | `sha256:dfe86a4d4a71fccdcf9c21c7b50ce4c0a8ceceea122fbaaa92459d5746f5147e` |
| `COLLISION_WITNESS` | `EVD-MJCP-7332e265ce3b23a2e7d79ce5` | `sha256:73c89f2616211322fb363a389e129664671be146bc5c5f39e98e56c39bb08d37` | `sha256:94af0ddc4892fea06e4dc2c890f3e93adb967a24118714029592b44411cab995` | `sha256:0dbed20e0e989047942457eb6ff335eb7f9b6f51c714185bb2bc148e0ca96b8c` | `sha256:7a1770844837800d0fafd1ccb583bb9b6819d0d832faba31f7c0069325004151` | `sha256:bebfac2bde0235cf51b429731ec0ccf1d7d40e8a4d4a9801f13eb16ff257f39e` |
| `NOT_PROVEN` | `EVD-MJCP-3428e656f3bb7ba3a2c63c2c` | `sha256:73c89f2616211322fb363a389e129664671be146bc5c5f39e98e56c39bb08d37` | `sha256:94af0ddc4892fea06e4dc2c890f3e93adb967a24118714029592b44411cab995` | `sha256:8e053f6ba0154752af144f67c8e08c1f71812957412fe38f309cff1af55497db` | `sha256:dbedb6f4cb2e637c50c681cf77b017fcb76bbb563b7e4686543c060c5de889be` | `sha256:ad847b2a012dee2b6c1d9cd7b14430d55ace828929616352e65fbbe926c7b634` |

After reload, each persisted result's `result_hash` matched both its
provenance `result_hash` and the canonical hash recomputed from the complete
typed result payload.

## Live VERIFIED_CLEAR Exact Trace

The persisted clear result contains 5 unique exact evaluations in actual
provider-call order. Each row includes both ordered required pairs.

| Eval | Location | `t` | joint-1 | joint-2 | Configuration hash | Transformed assembly hash | Pair | Volume mm3 | Distance mm | Classification | Witness? |
|---:|---|---:|---:|---:|---|---|---|---:|---:|---|---|
| 0 | waypoint 0 | 0.0 | 0.0 | 0.0 | `sha256:ae4c3e0a881090a071a7e09a6af323bb37f0fbe6b3380bd813fe04442b52ad67` | `sha256:73c89f2616211322fb363a389e129664671be146bc5c5f39e98e56c39bb08d37` | `link-1/base` | 0.0 | 10.0 | `POSITIVE_CLEARANCE` | no |
| 0 | waypoint 0 | 0.0 | 0.0 | 0.0 | same | same | `link-2/base` | 0.0 | 18.86796226410613 | `POSITIVE_CLEARANCE` | no |
| 1 | waypoint 1 | 1.0 | 20.0 | 20.0 | `sha256:cdb090a889f07fd1b1ce2aa67029a661d6baa9cb73ad74105a03cacc50f11efa` | `sha256:e89a9f4b8a67274774aa341576b57b8ef0c6e535b68320babe626005934ec9e5` | `link-1/base` | 0.0 | 10.0 | `POSITIVE_CLEARANCE` | no |
| 1 | waypoint 1 | 1.0 | 20.0 | 20.0 | same | same | `link-2/base` | 0.0 | 13.380741443442904 | `POSITIVE_CLEARANCE` | no |
| 2 | segment 0 interior | 0.5 | 10.0 | 10.0 | `sha256:0c1ff8fdfd5a0618bf63526cf286c2dbe893954747cb027bbf79d83f2351a7f3` | `sha256:c2f389bc7a04a9ff2af2c6b973cba6bd222fb390c455693e950827556d0c4b59` | `link-1/base` | 0.0 | 10.0 | `POSITIVE_CLEARANCE` | no |
| 2 | segment 0 interior | 0.5 | 10.0 | 10.0 | same | same | `link-2/base` | 0.0 | 15.704026771071437 | `POSITIVE_CLEARANCE` | no |
| 3 | segment 0 interior | 0.25 | 5.0 | 5.0 | `sha256:f38f7238790894b5122f49009c1d28b1247c018861d3cc5f0456c3437a608853` | `sha256:9d90e935285f3f8c81b63794dabe73e1a04cb67b23b4edf9aed11a4c3587eb23` | `link-1/base` | 0.0 | 10.0 | `POSITIVE_CLEARANCE` | no |
| 3 | segment 0 interior | 0.25 | 5.0 | 5.0 | same | same | `link-2/base` | 0.0 | 17.293447164568615 | `POSITIVE_CLEARANCE` | no |
| 4 | segment 0 interior | 0.75 | 15.0 | 15.0 | `sha256:4189600917e410b4ec311ba79c5115094021063f880c0a5d1e43f841fd0391a7` | `sha256:86bb248b745b4e812a5860718bfa30b2e7e0abe7a52e94fa94191bc002614256` | `link-1/base` | 0.0 | 9.999999999999996 | `POSITIVE_CLEARANCE` | no |
| 4 | segment 0 interior | 0.75 | 15.0 | 15.0 | same | same | `link-2/base` | 0.0 | 14.187109940198939 | `POSITIVE_CLEARANCE` | no |

The persisted certified leaves were:

| Leaf | `t_start` | `t_end` | Reference `t` | Pair | `B_A` mm | `B_B` mm | Pair bound mm | Certified lower mm |
|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 0 | 0.0 | 0.5 | 0.25 | `link-1/base` | 7.470361952582291 | 0.0 | 7.470361952582291 | 2.529638047417709 |
| 0 | 0.0 | 0.5 | 0.25 | `link-2/base` | 10.950207641097284 | 0.0 | 10.950207641097284 | 6.343239523471331 |
| 1 | 0.5 | 1.0 | 0.75 | `link-1/base` | 7.470361952582291 | 0.0 | 7.470361952582291 | 2.5296380474177056 |
| 1 | 0.5 | 1.0 | 0.75 | `link-2/base` | 10.950207641097284 | 0.0 | 10.950207641097284 | 3.2369022991016543 |

The minimum certified lower clearance is `2.5296380474177056 mm`, from leaf 1,
reference `t=0.75`, pair `link-1/base`.

## Reach-Bound Evidence

The persisted result contains these non-zero records:

| Instance | Joint | Ancestor chain | `rho` mm | Ordered invariant offsets mm | Padding mm | Final R mm | Component identity |
|---|---|---|---:|---|---:|---:|---|
| link-1 | joint-1 | `base -> link-1` | 50.990195136927845 | `[34.64101615137755]` | 0.000000001 | 85.6312112893054 | `m10-4-live-chain:generated_link_plate` |
| link-2 | joint-1 | `base -> link-1 -> link-2` | 20.43947263660829 | `[34.64101615137755, 50.0, 0.0]` | 0.000000001 | 105.08048878898585 | `m10-4-live-chain:link-2-gear` |
| link-2 | joint-2 | `link-1 -> link-2` | 20.43947263660829 | `[0.0]` | 0.000000001 | 20.43947263760829 | `m10-4-live-chain:link-2-gear` |

Persisted arithmetic:

```text
R(link-1,joint-1) = 50.990195136927845 + 34.64101615137755 + 0.000000001
                  = 85.6312112893054 mm

R(link-2,joint-1) = 20.43947263660829 + 34.64101615137755 + 50.0 + 0.0
                   + 0.000000001
                  = 105.08048878898585 mm

R(link-2,joint-2) = 20.43947263660829 + 0.0 + 0.000000001
                  = 20.43947263760829 mm
```

## Live COLLISION_WITNESS

The persisted witness used required clearance `1000 mm` and was:

```text
location: waypoint_index=0
configuration: joint-1=0.0 deg, joint-2=0.0 deg
configuration_hash: sha256:ae4c3e0a881090a071a7e09a6af323bb37f0fbe6b3380bd813fe04442b52ad67
transformed_assembly_hash: sha256:73c89f2616211322fb363a389e129664671be146bc5c5f39e98e56c39bb08d37
pair: link-1/base
interference_volume_mm3: 0.0
distance_mm: 10.0
classification: POSITIVE_CLEARANCE
required_clearance_mm: 1000.0
```

This was not physical `INTERFERENCE` or `TOUCHING`. It was
`POSITIVE_CLEARANCE` that exactly violated the requested `1000 mm` clearance.

## Live NOT_PROVEN

The persisted `NOT_PROVEN` result used `max_exact_evaluations=3`. It retained
these three exact evaluations in order:

| Eval | Location | Configuration | Configuration hash | Transformed assembly hash | Pair | Volume mm3 | Distance mm | Classification | Witness? |
|---:|---|---|---|---|---|---:|---:|---|---|
| 0 | waypoint 0 | `(0.0, 0.0)` | `sha256:ae4c3e0a881090a071a7e09a6af323bb37f0fbe6b3380bd813fe04442b52ad67` | `sha256:73c89f2616211322fb363a389e129664671be146bc5c5f39e98e56c39bb08d37` | `link-1/base` | 0.0 | 10.0 | `POSITIVE_CLEARANCE` | no |
| 0 | waypoint 0 | same | same | same | `link-2/base` | 0.0 | 18.86796226410613 | `POSITIVE_CLEARANCE` | no |
| 1 | waypoint 1 | `(20.0, 20.0)` | `sha256:cdb090a889f07fd1b1ce2aa67029a661d6baa9cb73ad74105a03cacc50f11efa` | `sha256:e89a9f4b8a67274774aa341576b57b8ef0c6e535b68320babe626005934ec9e5` | `link-1/base` | 0.0 | 10.0 | `POSITIVE_CLEARANCE` | no |
| 1 | waypoint 1 | same | same | same | `link-2/base` | 0.0 | 13.380741443442904 | `POSITIVE_CLEARANCE` | no |
| 2 | segment 0, `t=0.5` | `(10.0, 10.0)` | `sha256:0c1ff8fdfd5a0618bf63526cf286c2dbe893954747cb027bbf79d83f2351a7f3` | `sha256:c2f389bc7a04a9ff2af2c6b973cba6bd222fb390c455693e950827556d0c4b59` | `link-1/base` | 0.0 | 10.0 | `POSITIVE_CLEARANCE` | no |
| 2 | segment 0, `t=0.5` | same | same | same | `link-2/base` | 0.0 | 15.704026771071437 | `POSITIVE_CLEARANCE` | no |

The unresolved leaves were `[0.0, 0.5]` and `[0.5, 1.0]`, both with reason
`exact evaluation budget exhausted`. At least one real exact FreeCAD evaluation
occurred, no exact requested-clearance violation was observed before
exhaustion, and `continuous_path_verified=False`.

## Atomicity and Compatibility

The complete typed result payload and trusted provenance are persisted in one
immutable Evidence JSON record after proof completion. Failed FK/provider/proof
execution does not publish M10-4 Evidence. Cache hits do not create duplicate
exact-evaluation records. M9/M10-1/M10-2/M10-3 result semantics and hashes are
unchanged.

## Verification

| Verification | Passed | Failed | Skipped | Errors |
|---|---:|---:|---:|---:|
| M10-4 persistence/provenance focused tests | 17 | 0 | 0 | 0 |
| M10-4 live all-outcome acceptance | 1 | 0 | 0 | 0 |
| M10-3/M10-2/M10-1 deterministic regressions | 117 | 0 | 0 | 0 |
| M9/transient regressions | 63 | 0 | 3 | 0 |
| Full `tests/` suite | 844 | 0 | 51 | 0 |

`py -3 -m compileall src/mechcad_harness -q` and the required post-closure
verification commands passed. No M10-5 work is included.

## Remaining Limitations

M10-4 verifies one explicit path only, with piecewise-linear raw joint-space
interpolation and the current revolute-only model. It does not prove a whole
configuration-space region, dynamics, compliance, backlash, servo tracking,
thermal effects, vibration, or manufacturing tolerances. Current system
limitations also include `PREACCEPTED_CALLER_CONTRACT_ONLY`,
`COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED`, and run-ID
correlation/storage scope only.

M10-5 system acceptance is not implemented.
