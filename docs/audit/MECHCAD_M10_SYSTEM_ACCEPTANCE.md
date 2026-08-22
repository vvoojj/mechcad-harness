# MechCAD M10 System Acceptance

**Date:** 2026-08-23
**Disposition:** `M10_FULLY_CLOSED_LIVE_VERIFIED`
**Scope:** final system-level acceptance of the M10-1 through M10-4 motion,
kinematics, exact collision, continuous proof, evidence, and provenance stack.

This is an integration acceptance record. It does not add motion semantics and
does not claim that the broader MechCAD roadmap is complete.

## 1. Final Disposition

`M10_FULLY_CLOSED_LIVE_VERIFIED`

The complete M10 chain was executed on one fresh real-FreeCAD capstone fixture.
M10-2, M10-3, and M10-4 produced equal identities and exact pair measurements
for shared configurations. The M10-4 typed result was reloaded from durable
Evidence and re-hashed successfully. M9 foundation regressions and the full
test suite were green.

## 2. Accepted Baseline

The accepted predecessor markers are:

- `M9_FULLY_CLOSED_LIVE_VERIFIED`
- `M10_1_CONTINUOUS_SINGLE_AXIS_CLEARANCE_PROOF_VERIFIED`
- `M10_2_GENERIC_MULTI_JOINT_KINEMATICS_VERIFIED`
- `M10_3_MULTI_JOINT_EXACT_DISCRETE_COLLISION_VERIFIED`
- `M10_4_CONTINUOUS_MULTI_JOINT_PATH_CLEARANCE_PROOF_VERIFIED`

The current uncommitted M10-1 through M10-4 bytes were treated as the accepted
baseline. No reset, revert, stash, clean, commit, or push was performed.

## 3. M10 Scope

M10 closes generic rigid-body verification for the current revolute-joint model:

```text
source-bound assembly
  -> generic multi-joint model
  -> deterministic forward kinematics
  -> exact discrete FreeCAD collision / clearance
  -> one explicit piecewise-linear raw joint-space path
  -> conservative continuous clearance proof
  -> typed durable Evidence and trusted provenance
```

M10 does not add inverse kinematics, trajectory planning, collision avoidance,
swept solids, configuration-space search, dynamics, FEA, manufacturing, or
optimization.

## 4. Production Architecture

The live capstone used the production composition root and the following path:

```text
DesignState revision 1 / source state hash
  -> source-bound MountingPlateDesignSpec
  -> CadCompilationService
  -> generated CadPartProgram
  -> ToolBroker: mechcad-build-spur-gear-cad@1.0
  -> ArtifactStore byte-verified STEP
  -> ImportedCadComponent
  -> mixed CadAssemblyProgram
  -> KinematicModel + JointConfiguration / MultiJointPath
  -> ProductionApplication.evaluate_multi_joint_configuration
  -> ProductionApplication.analyze_multi_joint_collision_sweep
  -> ProductionApplication.prove_continuous_multi_joint_path_clearance
  -> FreeCADTransientAssemblyMeasurementProvider
  -> common().Volume / distToShape()
  -> typed result + trusted Evidence / provenance
```

The public production methods do not accept provider identity, backend identity,
runtime version, result hashes, proof status, reach bounds, or algorithm
versions. Those values are derived by trusted composition and result services.

## 5. Authority / Trust Boundaries

The authority chain remains:

```text
DesignState / accepted source binding
  -> source CadAssemblyProgram
  -> KinematicModel + JointConfiguration / MultiJointPath
  -> M10-2 FK
  -> transformed CadAssemblyProgram
  -> transient exact measurement
  -> M10-3 or M10-4 typed result
  -> trusted Evidence + provider/backend/runtime provenance
```

Confirmed boundaries:

- `DesignState` remains canonical and unchanged by analysis.
- Agents and analysis do not create revisions, `ChangeProposal`, or `ChangeSet` records.
- FreeCAD is a derived computational and measurement authority, not a canonical state owner.
- Generated CAD is compiled from a source-bound design specification.
- Imported CAD is accepted only after real producer output, `ArtifactStore` persistence, actual-byte hash verification, and trusted resolution.
- Temporary transformed CAD is disposable; no public per-configuration or per-midpoint CAD artifacts are published.
- Ordinary callers cannot attest an injected callback or custom backend as real FreeCAD; provider attestation is composition-owned.
- M10-4 extents are obtained by the trusted FreeCAD provider; topology reach-bound derivation is FreeCAD-independent.

## 6. Acceptance Audit Matrix

| Capability | Production entrypoint | Authoritative implementation | Provider / backend | Result type | Durable evidence | Live verification | Limitation |
|---|---|---|---|---|---|---|---|
| M10-1 single-axis proof | `prove_continuous_single_axis_clearance` | `continuous_proof.py` | FreeCAD transient provider | `ContinuousSingleAxisProofResult` | continuous proof provenance | focused live suite | single axis only |
| M10-2 multi-joint FK | `evaluate_multi_joint_configuration` | `multi_joint_kinematics.py` | deterministic core, no FreeCAD | `KinematicForwardKinematicsResult` | kinematics Evidence | focused unit and capstone FK comparison | one discrete configuration |
| M10-3 exact discrete sweep | `analyze_multi_joint_collision_sweep` | `multi_joint_collision_sweep.py` | `FreeCADTransientAssemblyMeasurementProvider` | `MultiJointCollisionSweepResult` | one provenance Evidence | fresh live capstone and M9 runtime | discrete configurations only |
| M10-4 continuous path proof | `prove_continuous_multi_joint_path_clearance` | `multi_joint_continuous_clearance.py` and `multi_joint_continuous_path.py` | same FreeCAD transient provider plus trusted extent boundary | `MultiJointContinuousClearanceProofResult` | one complete typed-result Evidence | fresh live capstone and durable reload | one explicit path only |
| Generated CAD | `compile_design_spec` | `cad_compilation.py` | FreeCAD realization | `CadPartProgram` / compilation result | ArtifactStore where realized | capstone generated plate | preaccepted caller contract |
| Trusted imported STEP | ToolBroker producer -> `resolve_imported_component` | ArtifactStore/import resolver | py_gearworks/build123d producer, FreeCAD consumer | `ImportedCadComponent` | artifact metadata and bytes | capstone real STEP | specialized producer provenance remains separate |
| Mixed assembly and exact measurement | `build_assembly_with_imported_components` and transient service | assembly and FreeCAD backend modules | FreeCAD 1.1.3 | assembly / pair measurements | assembly and analysis Evidence | capstone and M9 regressions | transient geometry is not canonical state |

## 7. M10-1 Acceptance

The focused M10-1 suite passed `34` tests, including its live real-FreeCAD
coverage. The accepted semantics remain unchanged:

- strict continuous single-axis proof;
- conservative chord-displacement bound;
- adaptive subdivision and exact measurement;
- `VERIFIED_CLEAR`, `COLLISION_WITNESS`, and `NOT_PROVEN`;
- touching is not positive clearance;
- computation budgets are ceilings, not correctness shortcuts;
- continuous verification is published only after complete interval coverage.

The ordinary discrete single-axis result continues to report
`continuous_sweep_verified = False`. Injected providers cannot run the
production continuous proof entrypoint.

## 8. M10-2 Acceptance

The M10-2 unit suite passed `53` tests. The accepted model and transform law
remain:

```text
T_world_child(q)
  = T_world_parent(q) . T_joint(q) . T_parent_child_home
```

The live capstone used two dependent revolute joints in series:

```text
base -> joint-1 -> link-1 -> joint-2 -> link-2
```

The audit confirmed rooted acyclic topology, deterministic traversal, one
articulated parent per child, parent-local axes and translated origins, raw
command identity preservation, source-placement home transforms, fail-closed
limits, fixed-instance preservation, no modulo normalization of command
identity, and fresh evaluation from the unchanged source assembly. M10-2
performed no collision or clearance logic.

## 9. M10-3 Acceptance

The focused M10-3 suite passed `75` tests, including live real-FreeCAD
execution. The exact pair inventory was:

```text
moving_instance_ids x stationary_instance_ids
= (link-1, link-2) x (base)
= (link-1, base), (link-2, base)
```

All requested configurations were validated before measurement. Each
configuration started from the source assembly, passed through M10-2 FK, and
was measured by real `common().Volume` and `distToShape()`. Classification
semantics and order were unchanged. The result retained
`continuous_path_verified = False`.

M10-3 persisted one final accepted Evidence record after the complete result.
Provider, measurement, validation, and Evidence failures publish no accepted
partial sweep.

## 10. M10-4 Acceptance

The focused M10-4 suite passed `18` tests, including live all-outcome execution.
The accepted proof scope is one explicit ordered piecewise-linear path in raw
joint space, not a configuration-space region.

The proof used trusted local geometry radii plus invariant ancestor-chain
offsets to derive `R(instance, joint)`, then hierarchical telescoping chord
bounds and exact pair-relative `B_A + B_B` bounds. The exact requested-clearance
witness threshold remained separate from `proof_guard`.

Only `VERIFIED_CLEAR` set `continuous_path_verified = True`. Collision witnesses
and budget or bound failures remained fail-closed `NOT_PROVEN` or
`COLLISION_WITNESS` according to the accepted semantics.

## 11. Capstone Live Fixture

The fresh capstone used:

- generated mounting plate: `generated_link_plate`;
- generated compiler: `generic-mounting-plate-compiler@1.0`;
- generated spec hash: `sha256:c67240f4e39f58464a7c51b88ea74c9b1c8c957d93a36f48b1c86962feaee645`;
- generated program hash: `sha256:f0e9c17c9f6ff66f65b8c066871f212e9aafe9b6544b83dbb4bc25ee0413b6c2`;
- trusted imported component: `link-2-gear`;
- real artifact id: `ART-80a15d7a-2fad-4f94-8fef-077c35bcdfbc`;
- actual-byte artifact hash: `sha256:ee7dc56408763b727e592ce466fab8a42bbaa50a74045d1fb35c9c940b41d555`;
- imported producer: `py-gearworks@0.1.0`, `py_gearworks 0.0.18`, Git revision `2fc2a13d82a9997a65f30c870498f0bb3be62318`;
- source revision: `1`;
- source state hash: `sha256:a1a29f72b1c195232af89c89664aea1f433bedcddcb64044bfae794fa0c26134`;
- topology: `base -> joint-1 -> link-1 -> joint-2 -> link-2`;
- moving side: `link-1`, `link-2`;
- stationary side: `base`.

The actual runtime was discovered through `MECHCAD_FREECADCMD`:

| Runtime item | Actual value |
|---|---|
| executable | `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe` |
| FreeCAD version | `1.1.3` |
| backend | `freecad`, `mechcad-freecad@2.1` |
| provider | `freecad-transient-exact`, `mechcad-freecad-transient@1.0` |
| execution mode | `freecadcmd-subprocess` |

## 12. Shared-Configuration Cross-Layer Equality

The same source assembly, model, pair partition, tolerances, and configurations
were submitted to M10-3 and M10-4. Both path waypoints were also explicit M10-3
configurations, and the second waypoint was independently evaluated through the
public M10-2 FK entrypoint.

| Waypoint | Joint-1 | Joint-2 | Configuration hash | M10-2 transformed hash | M10-3 transformed hash | M10-4 exact transformed hash |
|---|---:|---:|---|---|---|---|
| Q0 | 0.0 | 0.0 | `sha256:038da7c1fdb8655c588058a2183a79f94be2c7f70919718a620d7a35bd45ac64` | `sha256:349ed549c3e0a0edb2d9362e5090498dca372a0633adfc95f10b881bb761b8e2` | `sha256:349ed549c3e0a0edb2d9362e5090498dca372a0633adfc95f10b881bb761b8e2` | `sha256:349ed549c3e0a0edb2d9362e5090498dca372a0633adfc95f10b881bb761b8e2` |
| Q1 | 20.0 | 20.0 | `sha256:ea76bc97c8afc3d1839699d1edc6f66a32081b024abbbdf7fdf414c5a08cce7d` | `sha256:5cfcfee70f60755d0668f676f2fa72c672c51549e34b73a3f09ec92d87a02178` | `sha256:5cfcfee70f60755d0668f676f2fa72c672c51549e34b73a3f09ec92d87a02178` | `sha256:5cfcfee70f60755d0668f676f2fa72c672c51549e34b73a3f09ec92d87a02178` |

Every identity in the three transformed-hash columns is equal for the same
configuration. This is an observed cross-layer equality, not an inference from
service reuse.

## 13. Exact Geometry Evidence

All values below came from real FreeCAD `common().Volume()` and
`distToShape()` calls. The M10-3 and M10-4 values are equal within the exact
serialized values; the live comparisons used `pytest.approx` for floating-point
measurement equality.

| Configuration | Pair | M10-3 volume mm3 | M10-4 volume mm3 | M10-3 distance mm | M10-4 distance mm | M10-3 classification | M10-4 classification |
|---|---|---:|---:|---:|---:|---|---|
| Q0 `(0, 0)` | `link-1/base` | 0.0 | 0.0 | 10.0 | 10.0 | `positive_clearance` | `positive_clearance` |
| Q0 `(0, 0)` | `link-2/base` | 0.0 | 0.0 | 18.86796226410613 | 18.86796226410613 | `positive_clearance` | `positive_clearance` |
| Q1 `(20, 20)` | `link-1/base` | 0.0 | 0.0 | 10.0 | 10.0 | `positive_clearance` | `positive_clearance` |
| Q1 `(20, 20)` | `link-2/base` | 0.0 | 0.0 | 13.380741443442904 | 13.380741443442904 | `positive_clearance` | `positive_clearance` |

The pair order was exactly `link-1/base`, then `link-2/base` in both results.

## 14. Continuous Proof Evidence

The accepted path was:

```text
Q0 = (joint-1=0.0 deg,  joint-2=0.0 deg)
Q1 = (joint-1=20.0 deg, joint-2=20.0 deg)
```

Both dependent joints changed. Fresh live proof values were:

| Metric | Value |
|---|---:|
| path hash | `sha256:fb809a5e6751ae4e08a6bf717b85e3efabfdb112602ef6e98e6d7454bfdfc882` |
| exact unique evaluations | 5 |
| certified leaves | 2 |
| unresolved intervals | 0 |
| observed maximum subdivision depth | 1 |
| cache hits | 0 |
| coverage | complete: `[0.0, 0.5]` and `[0.5, 1.0]` |
| minimum certified lower clearance | `2.5296380474177056 mm` |
| continuous path verified | `True` |
| proof algorithm | `conservative-multi-joint-path-clearance-proof@1.0` |
| reach-bound algorithm | `articulated-descendant-reach-bound@1.0` |

The fresh result contained these reach-bound records:

| Instance | Joint | Local radius mm | Offset lengths mm | Reach bound mm |
|---|---|---:|---|---:|
| `link-1` | `joint-1` | 50.990195136927845 | `[34.64101615137755]` | 85.6312112893054 |
| `link-2` | `joint-1` | 20.43947263660829 | `[34.64101615137755, 50.0, 0.0]` | 105.08048878898585 |
| `link-2` | `joint-2` | 20.43947263660829 | `[0.0]` | 20.43947263760829 |

The certified leaves used midpoint references at `t=0.25` and `t=0.75`.
Their minimum lower clearance was `2.5296380474177056 mm` for `link-1/base`.
No unresolved leaf or requested-clearance witness remained.

## 15. Durable Evidence Reload

The capstone reloaded Evidence through a newly constructed `EvidenceStore` and
`StateManager` boundary after the original result objects had been produced.

M10-3 reload recovered:

- Evidence id `EVD-MJCS-b5cf5caacddfbeece11ce609`;
- kind `analysis.multi_joint_collision_sweep`;
- request hash, result hash, source assembly hash, model hash, provider identity, backend identity, and runtime identity;
- `producer_result_id == output_hash == sha256:daa5461371d18076295f405a3685f1e58bfb1c0ab7ee70cf97c01e61b4d21405`.

The accepted M10-3 persistence shape stores the final typed sweep result in the
analysis call result and stores one durable Evidence record containing its
trusted binding and provenance. It does not embed a second full M10-3 result
payload in Evidence. This is intentionally distinct from M10-4 and is not
redesigned for symmetry; M10-3 Evidence remains sufficient for its accepted
provenance contract.

M10-4 reload recovered:

- Evidence id `EVD-MJCP-cad34c77de737e6cf5f80fca`;
- the complete typed `MultiJointContinuousClearanceProofResult` payload;
- all 5 unique exact evaluations;
- both mandatory waypoints and all 3 non-leaf midpoint evaluations;
- both certified leaves;
- zero unresolved leaves;
- all reach-bound records;
- witness field state and proof status;
- `result_hash == sha256:ef1f76b947a0a315219348cf37422bf5b3ac4a8ada23ad46e8219bf058ffe48b`;
- canonical `continuous_clearance_result_hash(reloaded_result)` equal to that result hash;
- provenance `result_hash` equal to that result hash.

Repeated identical calls reused the same semantic request/result identities and
the idempotent Evidence records. No per-midpoint Evidence records were created.

## 16. Provenance / Runtime Identity

| Identity | M10-3 | M10-4 |
|---|---|---|
| source assembly hash | `sha256:349ed549c3e0a0edb2d9362e5090498dca372a0633adfc95f10b881bb761b8e2` | same |
| model hash | `sha256:38c894687e5b4043e5aab99a37d3fcdb99100ffa75e5a5ce7e77a27d787b6da5` | same |
| configuration / path hash | Q0/Q1 hashes above | `sha256:fb809a5e6751ae4e08a6bf717b85e3efabfdb112602ef6e98e6d7454bfdfc882` |
| request hash | `sha256:1131775c81e14d5113f9217fbb54ea1ef02702977a2b66d788aa219865f27722` | `sha256:94790017fa3b20bcb59de7357f1f8d4574944f34afc302aba9dc0d57225fe98a` |
| result hash | `sha256:daa5461371d18076295f405a3685f1e58bfb1c0ab7ee70cf97c01e61b4d21405` | `sha256:ef1f76b947a0a315219348cf37422bf5b3ac4a8ada23ad46e8219bf058ffe48b` |
| Evidence id | `EVD-MJCS-b5cf5caacddfbeece11ce609` | `EVD-MJCP-cad34c77de737e6cf5f80fca` |
| algorithm | `multi-joint-exact-collision-sweep@1.0` | `conservative-multi-joint-path-clearance-proof@1.0` |
| reach-bound algorithm | not applicable | `articulated-descendant-reach-bound@1.0` |
| provider | `freecad-transient-exact / mechcad-freecad-transient@1.0` | same |
| backend | `freecad / mechcad-freecad@2.1` | same |
| FreeCAD runtime | `1.1.3` | `1.1.3` |
| execution mode | `freecadcmd-subprocess` | `freecadcmd-subprocess` |

The capstone source state hash was
`sha256:a1a29f72b1c195232af89c89664aea1f433bedcddcb64044bfae794fa0c26134`.
The imported artifact carried the same source revision and state hash. Provider,
backend, runtime, request, result, and algorithm bindings were cross-checked
after reload.

## 17. Source Immutability

Before and after the complete capstone:

- source assembly hash remained `sha256:349ed549c3e0a0edb2d9362e5090498dca372a0633adfc95f10b881bb761b8e2`;
- all source instance placements remained unchanged;
- repeated evaluations did not accumulate transforms;
- source revision remained `1`;
- source state hash remained `sha256:a1a29f72b1c195232af89c89664aea1f433bedcddcb64044bfae794fa0c26134`;
- public artifact inventory remained unchanged after the imported artifact was produced;
- no per-configuration or midpoint CAD artifacts were published;
- no canonical mutation API was invoked by analysis.

## 18. Failure Semantics

Existing M10 regression tests and the focused acceptance audit cover:

- invalid topology, duplicate or missing joint relationships, cycles, and unreachable articulated nodes;
- invalid joint limits and malformed configuration schemas;
- malformed or overlapping pair partitions;
- provider failure and malformed exact measurement output;
- proof budget exhaustion and incomplete coverage;
- Evidence persistence failure and conflicting or corrupt persisted Evidence;
- caller-supplied provider/backend spoofing attempts.

These cases fail closed: no false `VERIFIED_CLEAR`, no accepted partial sweep or
proof Evidence, no silent clamp or wrap, and no skipped invalid configuration.

## 19. Determinism

The acceptance verified semantic determinism for identical inputs:

- model hash, path hash, configuration hashes, and pair ordering are stable;
- M10-3 repeated calls produced the same request and result hashes;
- M10-4 repeated calls produced the same request and result hashes;
- FK, M10-3, and M10-4 transformed assembly identities matched for shared configurations;
- exact evaluation traversal was ordered by waypoints, then adaptive subdivision;
- Evidence ids are derived from semantic request/result hashes.

Runtime-specific artifact ids and temporary paths are incidental identities. The
real producer may allocate a different artifact id in a separate run while the
actual artifact bytes and downstream semantic identities remain bound through
the accepted artifact hash and source assembly.

## 20. Regression Results

| Verification | Passed | Failed | Skipped | Errors | Result |
|---|---:|---:|---:|---:|---|
| M10-1 focused, including live | 34 | 0 | 0 | 0 | pass |
| M10-2 focused | 53 | 0 | 0 | 0 | pass |
| M10-3 focused, including live | 75 | 0 | 0 | 0 | pass |
| M10-4 focused, including live | 18 | 0 | 0 | 0 | pass |
| M10-5 capstone | 1 | 0 | 0 | 0 | pass |
| Combined M10 focused command | 180 | 0 | 1 | 0 | pass |
| M9 foundation regressions, runtime configured | 65 | 0 | 0 | 0 | pass |
| Full `tests/` with runtime configured | 871 | 0 | 25 | 0 | pass |
| `py -3 -m compileall src/mechcad_harness -q` | exit 0 | - | - | - | pass |

The unscoped `git diff --check` reported existing blank-line findings in
`.superpowers/sdd/task-*.md` and line-ending warnings for pre-existing dirty
files. `git diff --check -- tests/integration/test_m10_5_system_acceptance.py`
was clean. No new diff-check finding was introduced by the M10-5 acceptance
test or this document.

## 21. Production Bugs Found

`NONE`

The only correction during acceptance was a test assertion typo in the new
M10-5 acceptance fixture. No production defect or accepted M10 semantic change
was required.

## 22. Files Changed

M10-5 changes made in this acceptance:

- `tests/integration/test_m10_5_system_acceptance.py` - fresh live capstone, shared-configuration equality, durable reload, source immutability, and semantic replay checks.
- `docs/audit/MECHCAD_M10_SYSTEM_ACCEPTANCE.md` - this authoritative system closure record.
- `AGENTS.md` - current acceptance marker updated to M10 closure.
- `README.md` - current M10-5 status and bounded capability wording.
- `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md` - M10-4 current contract and M10 closure boundary.
- `docs/architecture/MECHCAD_ENGINEERING_WORKFLOW.md` - current M10 production entrypoints and future boundary.
- `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md` - current M10-5 baseline and bounded capability summary.
- `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md` - M10-5 traceability row and live-verified treatment.

All other dirty files shown by `git status --short` predated this acceptance
work and were left unchanged.

## 23. Normative Docs Updated

Updated minimally after live acceptance:

- `AGENTS.md`;
- `README.md`;
- `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`;
- `docs/architecture/MECHCAD_ENGINEERING_WORKFLOW.md`;
- `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`;
- `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`;
- added `docs/audit/MECHCAD_M10_SYSTEM_ACCEPTANCE.md`.

Historical M9 and individual M10 completion records were not rewritten.

## 24. Capability Claim

MechCAD can evaluate generic revolute multi-joint assemblies through
deterministic forward kinematics, exact discrete FreeCAD collision / clearance
measurement, and conservative continuous clearance proof along an explicit
piecewise-linear multi-joint joint-space path.

This claim does not mean arbitrary trajectory safety, all possible joint
combinations are safe, general continuous collision detection, configuration-
space proof, mechanism dynamics, physical real-world safety, manufacturing
approval, or complete MechCAD roadmap closure.

## 25. Remaining Limitations

The accepted limitations remain:

- `PREACCEPTED_CALLER_CONTRACT_ONLY`;
- `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED`;
- `run_id` is correlation/storage scope only, not trusted engineering identity;
- current multi-joint model is revolute-only;
- paths are explicitly supplied piecewise-linear raw joint-space paths;
- no whole configuration-space proof;
- rigid geometry assumption;
- no dynamics;
- no compliance, backlash, bearing-play, or actuator tracking-error proof;
- no cable motion unless modeled;
- no thermal or vibration proof;
- no manufacturing tolerance proof;
- no FEA, materials selection, optimization, or automatic synthesis/selection.

M10-3 remains discrete-only and keeps `continuous_path_verified = False`.
M10-4 proves only the explicitly requested path.

## 26. Next Milestone Boundary

M10 is closed. The next domain, if selected, requires a separate architecture
design and specification cycle. Structural/load/FEA verification is a likely
future direction, but this document does not assign or implement an M11 scope.

## 27. Closure Decision

All M10-5 gates were met:

- M10-1 through M10-4 remained regression-green;
- M10-3 and M10-4 executed real exact FreeCAD geometry;
- the capstone used real generated CAD and a trusted imported STEP artifact;
- M10-2, M10-3, and M10-4 agreed on shared live configurations and pair measurements;
- source assembly and canonical state remained immutable;
- the complete M10-4 payload was durably reloadable and re-hashed;
- trusted provenance matched persisted result identities;
- caller-spoofable trusted runtime identity was not introduced;
- no false continuous or configuration-space claim was added;
- M9 foundation regressions and the full suite passed;
- compileall passed;
- normative documentation now describes the accepted M10 scope and limits.

Therefore:

`M10_FULLY_CLOSED_LIVE_VERIFIED`
