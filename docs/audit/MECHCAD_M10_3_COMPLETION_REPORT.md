# M10-3 Completion Report - Multi-Joint Exact Discrete Collision Sweep

## Final Disposition

**`M10_3_MULTI_JOINT_EXACT_DISCRETE_COLLISION_VERIFIED`**

The required live FreeCAD acceptance executed with the repository-supported
`MECHCAD_FREECADCMD` configuration. The unchanged live test completed all four
ordered configurations through real FreeCAD exact measurement and persisted
trusted M10-3 provenance. The complete test suite also finished green.

## Architecture

The production path is:

```text
JointConfiguration
  -> MultiJointKinematicsService
  -> transformed CadAssemblyProgram
  -> TransientAssemblyAnalysisService
  -> FreeCADTransientAssemblyMeasurementProvider
  -> common().Volume / distToShape()
  -> CollisionClassification
  -> ordered MultiJointCollisionSweepResult
  -> one trusted Evidence/provenance record
```

`MultiJointDiscreteCollisionSweepService` composes the existing M10-2 forward
kinematics service and generic transient exact-analysis service. It evaluates
all configurations from the unchanged source assembly before exact
measurement, preserves configuration order, and fails closed on validation,
provider, or measurement failure. M10-2 owns topology and FK semantics;
`TransientAssemblyAnalysisService` remains kinematics-agnostic; the exact
provider owns FreeCAD geometry; and the application owns trusted composition,
source binding, and durable provenance.

## Typed Request And Result

`MultiJointCollisionSweepRequest` contains:

- `source_assembly_id` and recomputed `source_assembly_hash`;
- `model: KinematicModel` and derived `model_hash`;
- ordered non-empty `configurations: tuple[JointConfiguration, ...]`;
- ordered `moving_instance_ids` and `stationary_instance_ids`;
- non-negative volume and distance tolerances;
- service-owned `evaluator_version`;
- derived `request_hash`.

The trusted evaluator version is
`multi-joint-exact-collision-sweep@1.0`.

`MultiJointCollisionConfigurationResult` retains the configuration index and
hash, transformed assembly hash, evaluated joint states, instance world
transforms, ordered pair results, classification summary, and exact-distance
summary. `MultiJointCollisionSweepResult` retains the evaluator, source, model,
and request identities; ordered configuration results; interference, touching,
and positive-clearance summaries; collision configuration indices; minimum
discrete exact distance; `continuous_path_verified=False`; and a deterministic
`result_hash`.

The exact pair inventory is only the deterministic Cartesian product of moving
IDs by stationary IDs. No moving-moving or stationary-stationary pairs are
added.

## Production Entry Point

`ProductionApplication.analyze_multi_joint_collision_sweep(...)` accepts only
the source revision/state hash, source assembly, model, ordered configurations,
and moving/stationary partitions. It does not expose evaluator version,
provider callbacks, backend provenance, runtime identity, result hashes, or
collision results as caller-authored inputs.

The entry point validates the source state binding, computes the source
assembly hash from the actual assembly, stamps the trusted evaluator version,
executes the dedicated service with the composed measurement provider, and
records one M10-3 Evidence record only after a complete result exists. The
Evidence kind is `analysis.multi_joint_collision_sweep`; its ID is derived from
the request and result hashes.

## Live Fixture And Configurations

The runtime-gated acceptance test defines the required production fixture:

- a source-bound generated mounting plate from `compile_design_spec`;
- a trusted imported STEP component produced through
  `ToolBroker -> mechcad-build-spur-gear-cad@1.0 -> ArtifactStore ->
  resolve_imported_component`;
- mixed assembly instances `base`, `link-1`, and `link-2`;
- serial topology `base --joint-1--> link-1 --joint-2--> link-2`;
- base at `(0, 0, 0)`, link-1 at `(20, 20, 20)`, and link-2 at
  `(70, 20, 20)` in the source assembly;
- both revolute axes along world Z, with joint limits from -45 to 45 degrees.

The required ordered configurations are:

| Index | joint-1 | joint-2 | Meaning |
|---:|---:|---:|---|
| 0 | 0 | 0 | home |
| 1 | 30 | 0 | parent-only |
| 2 | 0 | 30 | child-only |
| 3 | 30 | 30 | combined |

`link-1` and `link-2` are moving; `base` is stationary. The required pair
order for every configuration is:

1. `link-1` versus `base`
2. `link-2` versus `base`

## Hierarchy Evidence

The live test confirmed the base remained at the home transform, link-1 changed
under parent-only motion and remained unchanged under child-only motion, and
link-2 changed under both parent-only and child-only motion. Relevant live
transforms were:

| Config | link-1 world position | link-2 world position | link-1 quaternion | link-2 quaternion |
|---|---|---|---|---|
| 0 `(0,0)` | `(20,20,20)` | `(70,20,20)` | `(1,0,0,0)` | `(1,0,0,0)` |
| 1 `(30,0)` | `(7.320508,27.320508,20)` | `(50.621778,52.320508,20)` | `(0.965926,0,0,0.258819)` | `(0.965926,0,0,0.258819)` |
| 2 `(0,30)` | `(20,20,20)` | `(70,20,20)` | `(1,0,0,0)` | `(0.965926,0,0,0.258819)` |
| 3 `(30,30)` | `(7.320508,27.320508,20)` | `(50.621778,52.320508,20)` | `(0.965926,0,0,0.258819)` | `(0.866025,0,0,0.5)` |

The child-only configuration was independently evaluated from the source with
M10-2 and matched the sweep transformed-assembly hash, proving no cumulative
transform drift.

## Exact Measurement Table

The default `FreeCADTransientAssemblyMeasurementProvider` executed real
`common().Volume` and `distToShape()` for both moving-by-stationary pairs in
each configuration. All measurements were positive-clearance cases:

| Configuration | Pair 1 | Pair 2 | Live status |
|---|---|---|---|
| 0: `(0, 0)` | `0.0 mm3`, `10.0 mm`, `positive_clearance` | `0.0 mm3`, `18.867962 mm`, `positive_clearance` | measured |
| 1: `(30, 0)` | `0.0 mm3`, `10.0 mm`, `positive_clearance` | `0.0 mm3`, `14.673861 mm`, `positive_clearance` | measured |
| 2: `(0, 30)` | `0.0 mm3`, `10.0 mm`, `positive_clearance` | `0.0 mm3`, `18.867962 mm`, `positive_clearance` | measured |
| 3: `(30, 30)` | `0.0 mm3`, `10.0 mm`, `positive_clearance` | `0.0 mm3`, `14.673861 mm`, `positive_clearance` | measured |

Deterministic tests separately cover the unchanged interference, touching, and
positive-clearance classification semantics.

## Sweep Identity And Provenance

The deterministic tests verify that:

- request identity is stable for the same ordered input;
- configuration order changes the request identity;
- angle and model-axis changes alter the relevant identities;
- joint mapping insertion order does not alter semantic identity;
- result identity includes ordered configuration identities, transformed
  assembly identities, joint values, pair measurements, and classifications;
- volatile timestamps, process IDs, temporary paths, and provider runtime data
  are excluded.

The implementation separates `model_hash`, `configuration_hash`,
`transformed_assembly_hash`, `request_hash`, and `result_hash`. The live sweep
identities were:

| Identity | Value |
|---|---|
| source_assembly_hash | `sha256:50f3043819f935e46345eb51fb5002b2614a9747dfb3728eb62437a8f791f235` |
| model_hash | `sha256:982a876298621b7ba21e25739ca852dc55af6824c216acb5eaf1e86600d42b2e` |
| request_hash | `sha256:1fa361e05d5373760a2fdaf5689f0df0220fd73b955c1cc55b7241aa742a2f0c` |
| result_hash | `sha256:0f0c5ee0c15730ff44edc95b402c3ec1bf496c0e9fcda156c56e393e0674fa4a` |
| evaluator_version | `multi-joint-exact-collision-sweep@1.0` |

Ordered configuration identities and transformed assembly identities were:

| Index | configuration_hash | transformed_assembly_hash |
|---:|---|---|
| 0 | `sha256:a2c41ca928bd53b1201744fdda1aa83ca532d9f9da6a2a452b0a5f90eb27a239` | `sha256:50f3043819f935e46345eb51fb5002b2614a9747dfb3728eb62437a8f791f235` |
| 1 | `sha256:523c2c0ea066f51c7050c18b16371e271c24e3d510500ea167d9bacf5b2c8365` | `sha256:b0b38965211a496d2ac4c8d8f496b52a914493fff75d18d236ac3a87c0c9a7a3` |
| 2 | `sha256:7db8f88cb6729779cdef963f671ef866f153792b2f8289227ae2616041f05e8a` | `sha256:ebfe6429dfb90a87febfbc983c04431f74fabc7f76744e90ec7187b81dac2388` |
| 3 | `sha256:239abb6d2bb32fea116c6f95298763b6876590a8fdf766fc9de42d653fdc0ec3` | `sha256:7fff09249a5270e7a756632e4b97d7b3f3e75268dc2d6f578b9901e06a274e92` |

The durable Evidence provenance reported provider
`freecad-transient-exact` version `mechcad-freecad-transient@1.0`, backend
`freecad` / `mechcad-freecad@2.1`, FreeCAD `1.1.3`, source executable
`C:\\Program Files\\FreeCAD 1.1\\bin\\freecadcmd.exe`, and execution mode
`freecadcmd-subprocess`. Its source, model, request, result, and evaluator
identities matched the live result above.

## Boundary And Authority Rules

- The application is authoritative for source revision/state binding, source
  assembly hashing, provider composition, and Evidence persistence.
- The M10-3 service is authoritative for request validation, ordered
  configuration execution, exact pair inventory, result aggregation, and
  deterministic result identity.
- M10-2 remains authoritative for model validation, topology, joint limits,
  configuration identity, and forward kinematics.
- The transient layer carries only opaque sample identity and transformed
  assembly/pair data; it does not parse joint or model semantics.
- Each transformed assembly is transient in memory and may use a disposable
  provider workspace. The sweep does not mutate the source assembly or
  `DesignState`, create revisions/proposals/change sets, or publish
  per-configuration CAD artifacts.
- Persistence is atomic at sweep level. No accepted partial result or M10-3
  Evidence is published after a failed FK, measurement, validation, result
  construction, or Evidence write.

## Verification Counts

| Verification | Passed | Failed | Skipped | Errors | Status |
|---|---:|---:|---:|---:|---|
| M10-3 live acceptance | 2 | 0 | 0 | 0 | pass |
| Focused post-hardening M10-3/provenance/live/continuous command | 108 | 0 | 0 | 0 | pass |
| Required M10-2/M10-1/M9-4/M9-3/M8C-3/transient/assembly/artifact regression | 157 | 0 | 0 | 0 | pass |
| Full `tests/` suite | 852 | 0 | 25 | 0 | pass |

`py -3 -m compileall src/mechcad_harness -q` passed with exit code 0. The
 post-hardening focused command returned `108 passed`; the plan-required
regression returned `157 passed`. The complete verbose suite returned `852
passed, 25 skipped` in `10:34.62`. The previously reported stall was a timeout
ceiling during the expanded real-FreeCAD sequence, not a producer hang or
regression: isolated M9-2 passed all 7 tests in 23.13 seconds, and the complete
suite passed with the runtime configured before collection. The final-review
provenance and result-claim gaps were hardened and verified; no remaining
production bug was identified.

## Files Changed For M10-3

- `src/mechcad_harness/multi_joint_collision_sweep.py` - request/result models
  and dedicated service.
- `src/mechcad_harness/multi_joint_kinematics.py` - shared canonical FK result
  identity helper used by M10-3 validation.
- `src/mechcad_harness/transient_assembly_analysis.py` - generic optional sample
  marker support.
- `src/mechcad_harness/analysis_provenance.py` - optional M10-3 model hash.
- `src/mechcad_harness/dependency/storage.py` - legacy optional provenance
  serialization compatibility.
- `src/mechcad_harness/application.py` - production entrypoint and Evidence
  provenance lookup.
- `tests/unit/test_multi_joint_collision_sweep.py` - deterministic service and
  identity coverage.
- `tests/unit/test_transient_assembly_analysis.py` - opaque sample compatibility.
- `tests/integration/test_m10_3_provenance.py` - production and legacy
  provenance coverage.
- `tests/integration/test_m10_3_live_multi_joint_collision.py` - runtime-gated
  real FreeCAD acceptance fixture.

The normative architecture documents and `AGENTS.md` were updated after live
and full-suite closure. Existing unrelated worktree changes are not attributed
to this Task 7 report.

## Limitations And Next Boundary

M10-3 verifies only the explicitly requested discrete configurations. It does
not verify interpolated motion, trajectory safety, swept-volume safety,
configuration-space coverage, time of impact, multidimensional bounds, or any
continuous multi-joint path. The result field remains
`continuous_path_verified=False`.

FEA, materials selection, manufacturing approval, tolerance verification,
optimization, and automatic synthesis/selection also remain outside this
milestone. M10-4 is the next boundary for continuous multi-joint reasoning.

## Acceptance Checklist

| Acceptance item | Status | Evidence |
|---|---|---|
| Typed M10-3 request/result and trusted evaluator version | PASS | Deterministic unit tests and implementation review |
| Ordered FK-to-transient production path | PASS | Focused deterministic composition tests |
| Trusted generated/imported mixed live fixture | PASS | Live FreeCAD acceptance fixture executed |
| Four configurations executed in real FreeCAD | PASS | Four ordered configurations completed |
| Live hierarchy transforms and no cumulative drift | PASS | Live assertions and independent M10-2 comparison |
| Live `common().Volume` and `distToShape()` measurements | PASS | Eight exact pair measurements |
| Live pair classifications and exact distance summaries | PASS | All pairs classified as positive clearance |
| Live FreeCAD provider/backend/version provenance | PASS | Durable Evidence provenance matched the result |
| Source/transient/artifact discipline | PASS | Live fixture and deterministic checks passed |
| Focused, regression, and compile verification | PASS | Counts recorded above |
| Full-suite verification | PASS | `852 passed, 25 skipped` |
| Normative documentation update | PASS | Current docs updated after runtime closure |
| Continuous path safety claim | NOT CLAIMED | `continuous_path_verified=False` |

The required final disposition is therefore
**`M10_3_MULTI_JOINT_EXACT_DISCRETE_COLLISION_VERIFIED`**.
