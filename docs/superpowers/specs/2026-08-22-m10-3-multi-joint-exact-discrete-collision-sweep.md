# M10-3 - Multi-Joint Exact Discrete Collision Sweep

## Objective

M10-3 connects the accepted M10-2 generic multi-joint forward-kinematics
model to the accepted M9 exact transient FreeCAD measurement path.

For one source `CadAssemblyProgram`, one `KinematicModel`, and an ordered
non-empty sequence of `JointConfiguration` values, production execution will:

```text
JointConfiguration
    -> MultiJointKinematicsService
    -> transformed CadAssemblyProgram
    -> TransientAssemblyAnalysisService
    -> exact measurement provider
    -> common().Volume / distToShape()
    -> exact per-pair classification
    -> ordered M10-3 sweep result
```

The result is discrete evidence for the explicitly requested configurations.
It does not make any claim about interpolated motion between configurations.

## Selected Service Boundary

Introduce a dedicated `MultiJointDiscreteCollisionSweepService` in a new
multi-joint collision-sweep module. The service composes, but does not replace
or modify the responsibilities of:

- `MultiJointKinematicsService` for authoritative M10-2 forward kinematics;
- `TransientAssemblyAnalysisService` for generic transformed-assembly exact
  measurement orchestration;
- `FreeCADTransientAssemblyMeasurementProvider` for live FreeCAD geometry;
- `CollisionClassification` for interference, touching, and positive-clearance
  semantics;
- `AnalysisExecutionProvenance` and `Evidence` for trusted execution records.

The existing `CadKinematicSweepService` remains single-axis and unchanged. No
collision logic is added to `multi_joint_kinematics.py`.

The new service first validates and evaluates every requested configuration
through the existing M10-2 FK service, starting from the same source assembly
each time. Only after all FK evaluations succeed does it invoke exact
measurement. This gives whole-request fail-closed validation for model,
configuration, topology, and joint-limit errors without publishing a partial
sweep result.

## Typed Request Model

Add `MultiJointCollisionSweepRequest` with these semantic fields:

- `source_assembly_id`;
- `source_assembly_hash`;
- `model: KinematicModel`;
- `configurations: tuple[JointConfiguration, ...]`;
- `moving_instance_ids`;
- `stationary_instance_ids`;
- collision volume and distance tolerances;
- explicit evaluator version;
- deterministic `request_hash`.

The configuration collection is a tuple and its order is semantic. The request
rejects zero configurations, duplicate or overlapping partition IDs, invalid
tolerances, non-identity source hashes, mismatched evaluator versions, and
configuration model IDs that do not match the request model. Existence and
partition completeness against the actual source assembly are validated by the
service before measurement.

`evaluator_version` is service-owned. The public production entrypoint does not
accept it. The production request factory stamps
`MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION`; the low-level request validator
also rejects any other value. `source_assembly_hash` is computed by the
production entrypoint and by the service's source-validation path from the
actual `CadAssemblyProgram`. A caller-supplied request hash or source hash is
never accepted without recomputation and equality verification.

The request hash covers the source assembly identity, M10-2 model hash, the
ordered configuration hashes, the ordered collision partition, tolerances, and
the stable evaluator version. It does not sort configurations or include
runtime/provider data.

## Forward-Kinematics Integration

For every configuration, the service calls the existing
`MultiJointKinematicsService.evaluate(source, model, configuration)`.

M10-3 does not reimplement topology traversal, parent-child propagation,
axis handling, limits, or configuration canonicalization. It retains each
M10-2 result's:

- `model_hash`;
- `configuration_hash`;
- `transformed_assembly_hash`;
- evaluated joint states;
- instance world transforms;
- transformed `CadAssemblyProgram`.

The service may accept an FK service dependency at its composition boundary for
deterministic tests and call tracing, but production uses the normal
`MultiJointKinematicsService` implementation. The source assembly is never
replaced by a previous transformed result, preventing cumulative transform
drift.

## Generic Transient Boundary

`TransientAssemblyAnalysisService` remains kinematics-agnostic. It will not
gain model-specific or joint-specific fields.

The current transient request technically requires `sample_angle_deg`, even
though the exact provider uses only the transformed assembly and pair
inventory. M10-3 will make the narrow backward-compatible change of changing
`sample_angle_deg` to `float | None = None` and adding generic
`sample_id: str | None = None` to both `TransientAssemblyAnalysisRequest` and
`TransientAssemblyAnalysisResult`. Existing single-axis callers continue to
provide and receive `sample_angle_deg` exactly as before. M10-3 supplies
`sample_angle_deg=None` and uses `sample_id` to carry its already-derived
configuration identity. The transient layer treats `sample_id` as an opaque
sample identity; it does not parse it or learn about joints, models, or
kinematic semantics.

The M10-3 layer binds the semantic chain independently:

```text
model_hash + configuration_hash
    -> M10-2 transformed_assembly_hash
    -> transient exact result
```

The transient service continues to validate the transformed assembly hash and
ordered pair inventory, and it remains responsible only for temporary exact
geometry measurement.

## Exact Pair Semantics

The required inventory is exactly the deterministic Cartesian product:

```text
moving_instance_ids x stationary_instance_ids
```

Moving-moving and stationary-stationary pairs are not added. IDs must exist in
the source assembly, be unique within each partition, and not overlap. Pair
results preserve moving-ID outer order and stationary-ID inner order.

Each pair result reuses the existing exact fields and classification:

- moving instance ID;
- stationary instance ID;
- `interference_volume_mm3`;
- exact distance in millimetres;
- `CollisionClassification`.

Measurements must be finite and non-negative. Provider failures, malformed
measurements, missing pairs, extra pairs, or reordered pairs fail closed.
Classification remains:

- common volume greater than the volume tolerance: `INTERFERENCE`;
- otherwise distance within tolerance: `TOUCHING`;
- otherwise: `POSITIVE_CLEARANCE`.

## Typed Result Model

Add a per-configuration result, conceptually
`MultiJointCollisionConfigurationResult`, containing:

- configuration index;
- configuration hash;
- transformed assembly hash;
- ordered evaluated joint values/states;
- ordered exact pair results;
- per-configuration classification summary;
- collision/touching summary fields derived from pair results.

Add `MultiJointCollisionSweepResult` containing:

- evaluator version;
- source assembly hash;
- model hash;
- request hash;
- ordered per-configuration results;
- `any_interference`;
- `any_touching`;
- `all_positive_clearance`;
- ordered collision configuration indices;
- deterministic minimum exact discrete distance summary;
- `continuous_path_verified = False`;
- deterministic `result_hash`.

The result hash covers the request identity, evaluator version, model/source
identities, ordered configuration identities, transformed assembly identities,
joint values, pair measurements, and classifications. It excludes timestamps,
process IDs, temporary directories, and provider runtime details.

The result never collapses the evidence to one ambiguous collision boolean.
`any_interference` is true if any required pair in any configuration
has `INTERFERENCE`; `any_touching` is true if any required pair has `TOUCHING`;
`all_positive_clearance` is true only if every required pair in every requested
configuration has `POSITIVE_CLEARANCE`. Thus a result containing touching is
not represented as globally collision-free merely because it has no
interference. Pair evidence for every requested configuration remains
inspectable.

## Production Composition and Provenance

Add `ProductionApplication.analyze_multi_joint_collision_sweep(...)`. An
ordinary caller supplies only the source binding, source assembly, model,
ordered configurations, and moving/stationary IDs. The public entrypoint does
not expose provider callbacks, backend provenance, runtime identity, result
hashes, or collision results.

`ProductionApplication` reuses its existing composed measurement provider. The
default provider remains `FreeCADTransientAssemblyMeasurementProvider`; a
deterministic provider remains available only through the existing composition
boundary for tests.

Extend `AnalysisExecutionProvenance` narrowly with
`model_hash: str | None = None`. Existing M9 and M10-1 records remain valid
because the field is optional, legacy serialized records that omit it continue
to validate, and their result/request hash contracts are not changed. M10-3
provenance derives the model hash from `kinematic_model_hash(model)` and binds:

- source assembly hash;
- model hash;
- request hash;
- result hash;
- M10-3 evaluator version;
- provider name/version;
- backend identity/version and FreeCAD library version when live;
- execution mode.

M10-3 Evidence uses a distinct analysis kind and deterministic ID derived from
the request and result identities. The durable result hash remains independent
of volatile provenance timestamps.

Compatibility tests must load representative legacy M9 and M10-1 provenance
and Evidence payloads without `model_hash`, verify they still deserialize and
compare semantically as before, and verify that adding the default `None` field
does not change any legacy request hash, result hash, Evidence ID, or persisted
semantic payload when serialized with the existing non-null-field convention.

## Failure and Authority Rules

The service fails closed for:

- an empty configuration sequence;
- source assembly ID or hash mismatch;
- model/configuration mismatch;
- invalid configuration IDs, non-finite values, or joint-limit violations;
- invalid model topology;
- missing, duplicate, or overlapping partition IDs;
- incomplete exact pair results;
- malformed numeric measurements;
- provider or transient realization failure.

It does not skip invalid configurations, clamp angles, continue after a
measurement failure, mutate the source assembly, create a canonical revision,
create a `ChangeProposal` or `ChangeSet`, publish per-configuration CAD
artifacts, or choose safer configurations.

Execution and persistence are atomic at the sweep level:

```text
pre-FK all configurations
    -> exact-measure all configurations
    -> construct and validate complete result
    -> persist one Evidence/provenance record
    -> return result
```

No per-configuration result or Evidence is persisted. If FK or exact
measurement fails at any configuration, the operation raises and no accepted
M10-3 result or M10-3 Evidence is published. If final result validation or the
single Evidence write fails, the operation also fails rather than returning a
partial or unproven durable result.

## Transient Discipline

Each transformed assembly is a normal in-memory `CadAssemblyProgram` produced
from the unchanged source assembly and one explicit configuration. The real
provider may realize it in a disposable temporary workspace. No public FCStd,
STEP, or STL artifact is created for an individual configuration, and no
`DesignState` revision or run-control mutation is created by the sweep.

## Live Acceptance Fixture

The focused live test will use the accepted production paths to construct a
generic mixed assembly containing:

- a source-bound generated base/plate;
- a generated or imported first link as appropriate;
- a real trusted imported STEP component for the second link;
- a two-joint serial topology `base -> joint-1 -> link-1 -> joint-2 -> link-2`.

The imported artifact will be produced through the real
`ToolBroker -> mechcad-build-spur-gear-cad@1.0 -> ArtifactStore ->
ImportedCadComponent` path when the accepted fixture uses the gear solid. The
algorithm remains gear-neutral.

At least four ordered configurations will cover home, parent-only, child-only,
and combined motion. The live test will assert that link-1 changes under
parent-only motion, link-2 changes under parent-only and child-only motion, and
link-1 remains unchanged under child-only motion.

Every configuration will execute real FreeCAD `common().Volume` and
`distToShape()` through the default provider. The test will report every exact
pair measurement and classification, the M10-2 hashes/transforms, provider and
backend provenance, source immutability, no cumulative drift, and no public
per-configuration artifact leakage.

If the required FreeCAD runtime or real artifact producer is unavailable, the
live acceptance remains explicitly runtime-gated and does not substitute a
deterministic provider for live evidence.

## Test Strategy

Focused unit and composition tests will cover:

- stable request/result identity;
- order-sensitive configuration hashing;
- angle and model/topology identity changes;
- insertion-order-independent joint mappings;
- direct equality with M10-2 FK transformed assemblies;
- all configurations and all moving-by-stationary pairs evaluated;
- classification and summary correctness;
- empty, malformed, mismatched, partition, provider, and measurement failures;
- source immutability and no cumulative transform drift;
- deterministic versus FreeCAD provenance;
- public trust-boundary signature restrictions.

Existing M10-2, M10-1, M9-4, M9-3, M8C-3, transient-analysis,
assembly, artifact, and evidence tests remain regression gates. No M10-1
continuous proof status or M10-2 FK semantics are changed.

## M10-4 Boundary

M10-3 does not implement interpolation, trajectory safety, swept-volume safety,
configuration-space coverage, time-of-impact, multidimensional bounds, or any
continuous multi-joint proof. Those are reserved for M10-4.

The explicit semantic limitation is:

```text
continuous_path_verified = False
```

## Implementation Disposition

This document records the approved design. The completion report and normative
architecture updates will be written only after implementation and live/full
verification succeed.
