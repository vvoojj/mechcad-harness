# M10-3 Multi-Joint Exact Discrete Collision Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-owned, exact discrete collision sweep over ordered multi-joint configurations without changing M10-2 FK, single-axis sweep, or generic transient-analysis semantics.

**Architecture:** Create `MultiJointDiscreteCollisionSweepService` as the composition boundary. It pre-evaluates every configuration through the existing `MultiJointKinematicsService`, measures each resulting `CadAssemblyProgram` through the existing `TransientAssemblyAnalysisService`, and aggregates existing `CollisionClassification` pair results. `ProductionApplication` stamps trusted identities, owns provider composition, and persists one complete M10-3 Evidence record only after the sweep succeeds.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing `CadAssemblyProgram`, `MultiJointKinematicsService`, `TransientAssemblyAnalysisService`, `FreeCADTransientAssemblyMeasurementProvider`, `EvidenceStore`, and real FreeCAD 1.1.x when configured.

## Global Constraints

- Preserve `M9_FULLY_CLOSED_LIVE_VERIFIED`, `M10_1_CONTINUOUS_SINGLE_AXIS_CLEARANCE_PROOF_VERIFIED`, and `M10_2_GENERIC_MULTI_JOINT_KINEMATICS_VERIFIED` semantics.
- Use exactly one M10-3 status field: `continuous_path_verified = False`.
- Keep `CadKinematicSweepService` single-axis; do not add collision logic to `multi_joint_kinematics.py`.
- The ordered configuration sequence is semantic and must not be sorted.
- The exact pair inventory is only `moving_instance_ids x stationary_instance_ids` in deterministic outer/inner order.
- `evaluator_version` is stamped by the service/application and rejected when mismatched; ordinary callers cannot author it.
- `source_assembly_hash` is recomputed from the actual source assembly and equality-checked before execution.
- `TransientAssemblyAnalysisService` remains kinematics-agnostic; its only compatibility change is the generic optional sample marker described in Task 1.
- `AnalysisExecutionProvenance.model_hash` is optional and legacy-compatible; M10-3 derives it from `kinematic_model_hash(model)`.
- Exact measurement and Evidence persistence are atomic at sweep level: no accepted partial result or Evidence is published after any failure.
- Do not mutate `DesignState`, create revisions, create proposals/change sets, or publish per-configuration CAD artifacts.
- Do not commit changes in this workspace; preserve pre-existing dirty M10-1/M10-2 changes.

---

## File Map

- Create: `src/mechcad_harness/multi_joint_collision_sweep.py` - M10-3 evaluator constant, request, per-configuration result, sweep result, and dedicated service.
- Modify: `src/mechcad_harness/transient_assembly_analysis.py` - generic optional sample identity and optional angle marker.
- Modify: `src/mechcad_harness/analysis_provenance.py` - optional `model_hash` on the existing provenance type.
- Modify: `src/mechcad_harness/application.py` - production M10-3 entrypoint, trusted provenance recording, and evidence lookup.
- Create: `tests/unit/test_multi_joint_collision_sweep.py` - pure service, identity, validation, exact-pair, and no-drift tests.
- Create: `tests/integration/test_m10_3_provenance.py` - deterministic composition and legacy provenance compatibility tests.
- Create: `tests/integration/test_m10_3_live_multi_joint_collision.py` - runtime-gated real FreeCAD mixed-assembly acceptance.
- Modify: `tests/unit/test_transient_assembly_analysis.py` - generic optional sample compatibility coverage.
- Create after acceptance: `docs/audit/MECHCAD_M10_3_COMPLETION_REPORT.md` - live evidence and acceptance audit.
- Modify after acceptance: `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`, `docs/architecture/MECHCAD_RUNTIME_FLOW.md`, `docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md`, `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`, and `AGENTS.md`.

## Identity and Interfaces

Use these exact public concepts:

```text
MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION = "multi-joint-exact-collision-sweep@1.0"

MultiJointDiscreteCollisionSweepService.__init__(
    transient_analysis_service: TransientAssemblyAnalysisService,
    kinematics_service: MultiJointKinematicsService | None = None,
) -> None

MultiJointDiscreteCollisionSweepService.execute(
    request: MultiJointCollisionSweepRequest,
    assembly: CadAssemblyProgram,
) -> MultiJointCollisionSweepResult
```

`MultiJointCollisionSweepRequest` contains the source assembly identity,
nested `KinematicModel`, ordered tuple of `JointConfiguration`, moving and
stationary IDs, tolerances, trusted evaluator version, derived model hash, and
derived request hash. Its validator rejects empty configurations, duplicate or
overlapping partition IDs, model-ID mismatches, invalid numeric values, and any
evaluator version other than the constant.

`MultiJointCollisionConfigurationResult` contains configuration index/hash,
transformed assembly hash, evaluated joint states, instance world transforms,
ordered existing `CadKinematicCollisionPairResult` values, a deterministic
classification summary, per-configuration interference/touching/positive
clearance flags, and minimum exact distance.

`MultiJointCollisionSweepResult` contains evaluator/source/model/request hashes,
ordered configuration results, `any_interference`, `any_touching`,
`all_positive_clearance`, interference configuration indices, minimum exact
distance/index, `continuous_path_verified=False`, and result hash.

## Task 1: Generalize the Transient Request Marker

**Files:**
- Modify: `src/mechcad_harness/transient_assembly_analysis.py:11-24`
- Modify: `tests/unit/test_transient_assembly_analysis.py`

**Interfaces:**
- Existing single-axis callers continue passing `sample_angle_deg: float`.
- New callers may pass `sample_angle_deg=None` and opaque `sample_id: str | None`.
- No field may mention joints, models, or kinematic semantics.

- [ ] **Step 1: Add a failing compatibility test.**

Add a test that constructs `TransientAssemblyAnalysisRequest` with
`sample_angle_deg=None`, `sample_id="opaque-sample"`, runs the existing
`TransientAssemblyAnalysisService`, and asserts the result preserves both
values. Keep the existing test that passes a real angle unchanged.

- [ ] **Step 2: Run the focused test to verify it fails.**

Run: `python -m pytest tests/unit/test_transient_assembly_analysis.py -q`

Expected: the new construction fails because `sample_angle_deg` is currently
required and `sample_id` is forbidden by the base model.

- [ ] **Step 3: Make the narrow generic change.**

Change both transient request/result models as follows:

```python
sample_angle_deg: float | None = None
sample_id: str | None = None
```

Do not add validators or behavior involving M10-3 types. Keep transformed hash
and pair-inventory validation unchanged. Existing angle-based callers remain
valid.

- [ ] **Step 4: Run the focused and transient regression tests.**

Run: `python -m pytest tests/unit/test_transient_assembly_analysis.py tests/unit/test_transient_freecad_measurement.py -q`

Expected: all focused transient tests pass.

## Task 2: Build the Pure M10-3 Request, Result, and Service

**Files:**
- Create: `src/mechcad_harness/multi_joint_collision_sweep.py`
- Create: `tests/unit/test_multi_joint_collision_sweep.py`

**Interfaces:**
- Consume `CadAssemblyProgram`, `assembly_hash`, existing collision models from `kinematic_sweep.py`, M10-2 `KinematicModel`, `JointConfiguration`, `MultiJointKinematicsService`, and `TransientAssemblyAnalysisService`.
- Produce the three M10-3 Pydantic models and `MultiJointDiscreteCollisionSweepService.execute()` defined above.

- [ ] **Step 1: Write failing identity and validation tests.**

Cover these exact cases before implementation: same ordered request has stable
hash; configuration order changes request hash; one angle changes the relevant
configuration and request hashes; mapping insertion order does not change
semantic identity; model axis changes model/request identity; empty
configurations fail; mismatched evaluator version fails; source hash is
rechecked against the assembly; and the partition requires all existing
instances without duplicates or overlap.

Use the existing M10-2 three-body fixture shape: `base`, `link-1`, and
`link-2`, with `joint-1` parented from `base` and `joint-2` parented from
`link-1`. Use at least one translated or non-world axis in a deterministic
test.

- [ ] **Step 2: Run the new tests to verify they fail.**

Run: `python -m pytest tests/unit/test_multi_joint_collision_sweep.py -q`

Expected: import or model failures because the M10-3 module does not exist.

- [ ] **Step 3: Implement canonical request identity.**

Use `kinematic_model_hash(model)` and `joint_configuration_hash(configuration)`
from M10-2. Build request hash from an explicit ordered payload rather than a
set or unordered model dump:

```python
payload = {
    "source_assembly_id": request.source_assembly_id,
    "source_assembly_hash": request.source_assembly_hash,
    "model_hash": kinematic_model_hash(request.model),
    "configuration_hashes": [
        joint_configuration_hash(configuration)
        for configuration in request.configurations
    ],
    "moving_instance_ids": list(request.moving_instance_ids),
    "stationary_instance_ids": list(request.stationary_instance_ids),
    "volume_tolerance_mm3": request.volume_tolerance_mm3,
    "distance_tolerance_mm": request.distance_tolerance_mm,
    "evaluator_version": MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION,
}
```

Reject any non-constant evaluator version. Stamp the model hash and request
hash when pending; if a caller supplies either value, recompute and reject a
mismatch.

- [ ] **Step 4: Implement fail-closed source and partition validation.**

In `execute()`, recompute `actual_source_hash = assembly_hash(assembly)` and
require both request assembly ID and hash to match. Require
`kinematic_model_hash(request.model)` to equal the request model hash. Require
the union of moving and stationary IDs to equal the actual assembly instance
IDs, with no duplicates or overlap. Generate pairs exactly as:

```python
pairs = tuple(
    (moving, stationary)
    for moving in request.moving_instance_ids
    for stationary in request.stationary_instance_ids
)
```

- [ ] **Step 5: Implement pre-FK execution from the unchanged source.**

Evaluate all configurations before invoking the transient service:

```python
fk_results = tuple(
    self.kinematics_service.evaluate(
        assembly, request.model, configuration
    )
    for configuration in request.configurations
)
```

Do not pass a prior transformed assembly into the next call. This delegates all
model-ID, joint-ID, finite-number, limit, topology, and transform semantics to
M10-2.

- [ ] **Step 6: Implement exact measurement and per-configuration results.**

For each `(index, configuration, fk_result)` in request order, create a generic
transient request with `sample_angle_deg=None`, `sample_id=configuration_hash`,
the source/transformed/request hashes, and the deterministic pair tuple. Call
`self.transient_analysis_service.analyze()`.

Validate every returned scalar with `math.isfinite()` and `>= 0`, verify the
pair tuple exactly matches `pairs`, then construct the existing
`CadKinematicCollisionPairResult` type and classify with:

```python
CollisionClassification.from_measurement(
    volume,
    distance,
    volume_tolerance_mm3=request.volume_tolerance_mm3,
    distance_tolerance_mm=request.distance_tolerance_mm,
)
```

Use precedence `INTERFERENCE`, then `TOUCHING`, then
`POSITIVE_CLEARANCE` for a per-configuration summary. Preserve FK joint
states and all instance world transforms in the configuration result.

- [ ] **Step 7: Implement explicit sweep summaries and deterministic result hash.**

Compute:

```python
any_interference = any(item.any_interference for item in configuration_results)
any_touching = any(item.any_touching for item in configuration_results)
all_positive_clearance = all(
    item.all_positive_clearance for item in configuration_results
)
collision_configuration_indices = tuple(
    item.configuration_index
    for item in configuration_results
    if item.any_interference
)
```

Select minimum exact distance using the first occurrence on ties, retaining its
configuration index. Set `continuous_path_verified=False` unconditionally.
Hash the complete result payload excluding only `result_hash`; include ordered
per-configuration data and evaluator/request identity, and exclude runtime
paths/timestamps.

- [ ] **Step 8: Add service execution and no-drift tests.**

Use a recording deterministic measurement callback to assert:

- all configurations are measured in order;
- every moving-by-stationary pair is measured in order;
- FK is called once per configuration with the original source object;
- Q2 after Q1 has the same FK/transformed hash and measurement as Q2 alone;
- source assembly hash and placements are unchanged;
- interference, touching, and positive-clearance summaries are distinct;
- a malformed value, missing pair, provider exception, or later measurement failure raises and returns no result.

- [ ] **Step 9: Run the pure M10-3 test suite.**

Run: `python -m pytest tests/unit/test_multi_joint_collision_sweep.py -q`

Expected: all new pure-Python M10-3 tests pass.

## Task 3: Add Trusted Production Composition and Provenance

**Files:**
- Modify: `src/mechcad_harness/analysis_provenance.py:23-39`
- Modify: `src/mechcad_harness/application.py` near the existing kinematic methods
- Create: `tests/integration/test_m10_3_provenance.py`

**Interfaces:**
- Add `ProductionApplication.analyze_multi_joint_collision_sweep(...)` with source revision/hash, assembly, model, ordered configurations, and partition arguments only.
- Add `get_multi_joint_collision_sweep_evidence(result_hash)`.
- Add optional `model_hash: str | None = None` to `AnalysisExecutionProvenance`.

- [ ] **Step 1: Write failing trust-boundary and provenance tests.**

Assert the public signature contains none of `evaluator_version`,
`provider_name`, `provider_version`, `backend_provenance`, `measurement_provider`,
or `exact_measure`. For deterministic composition, assert Evidence contains:

```python
provenance.provider_name == "deterministic-test-provider"
provenance.backend_provenance is None
provenance.model_hash == result.model_hash
provenance.request_hash == result.request_hash
provenance.result_hash == result.result_hash
provenance.sweep_version == result.evaluator_version
```

Assert the default application composes a `FreeCADTransientAssemblyMeasurementProvider`.

- [ ] **Step 2: Add optional provenance field without changing legacy contracts.**

Add exactly:

```python
model_hash: str | None = None
```

Do not change existing M9/M10-1 fields or hash computation. Load legacy
provenance/Evidence JSON payloads that omit the field and assert they validate.
Use `exclude_none=True` for compatibility serialization checks so adding the
default field does not alter the legacy semantic payload. Assert existing M9
request/result hashes and Evidence IDs remain identical.

- [ ] **Step 3: Implement the production entrypoint.**

Validate the state source with the existing `assembly_service.validate_source()`.
Compute `source_hash = assembly_hash(assembly)` in the application, construct
the request with the fixed evaluator constant, execute the dedicated service
using `self.kinematic_measure`, and call the provenance recorder only after a
complete result exists.

The recorder must derive provider identity from the composed provider exactly as
the existing M9 recorder does:

```python
if isinstance(provider, FreeCADTransientAssemblyMeasurementProvider):
    provider_name = provider.provider_name
    provider_version = provider.provider_version
    execution_mode = provider.execution_mode
    backend_provenance = provider.provenance()
else:
    provider_name = DETERMINISTIC_PROVIDER_NAME
    provider_version = DETERMINISTIC_PROVIDER_VERSION
    execution_mode = DETERMINISTIC_EXECUTION_MODE
    backend_provenance = None
```

Create one `Evidence` with kind `analysis.multi_joint_collision_sweep`, input
hash=request hash, output hash=result hash, model hash in the nested
provenance, and deterministic ID from request/result hashes. Write no Evidence
before this point. If the write raises, propagate the failure and do not return
the result.

- [ ] **Step 4: Run deterministic provenance tests and legacy regressions.**

Run: `python -m pytest tests/integration/test_m10_3_provenance.py tests/integration/test_m9_4_trusted_analysis_backend_provenance.py tests/unit/test_multi_joint_kinematics.py -q`

Expected: new M10-3 provenance tests and legacy M9/M10-2 tests pass.

## Task 4: Add Focused Regression Coverage

**Files:**
- Modify: `tests/integration/test_m10_3_provenance.py`

- [ ] **Step 1: Add whole-request fail-closed tests.**

Exercise empty configurations, invalid joint ID, limit violation, wrong model
ID, wrong source assembly, unknown/duplicate/overlapping partition IDs,
non-finite provider measurement, provider exception, and incomplete pair
inventory. Assert no M10-3 Evidence exists after every failure.

- [ ] **Step 2: Add identity and ordering tests through `ProductionApplication`.**

Run the same application request twice and assert identical request/result
hashes. Reverse configurations and assert both hashes change. Change one angle
and assert the relevant configuration and result identities change. Change an
axis/topology model and assert model/request/result identities change. Compare
two mappings with different insertion order and assert identical semantic
identity.

- [ ] **Step 3: Add multi-pair and summary tests.**

Use two moving descendants and two stationary instances with a deterministic
provider. Assert four pair results per configuration in moving-outer,
stationary-inner order. Assert touching sets `any_touching=True` and
`all_positive_clearance=False` even when `any_interference=False`.

- [ ] **Step 4: Run focused M10-3 tests.**

Run: `python -m pytest tests/unit/test_multi_joint_collision_sweep.py tests/integration/test_m10_3_provenance.py -q`

Expected: all focused M10-3 tests pass with no partial Evidence on failures.

## Task 5: Add Real FreeCAD M10-3 Acceptance

**Files:**
- Create: `tests/integration/test_m10_3_live_multi_joint_collision.py`

**Fixture construction:** follow the existing M9 production fixture helpers,
not handwritten fake imported components. Create a source-bound generated plate
through `compile_design_spec`. Produce a real STEP imported component through
the accepted `ToolBroker -> mechcad-build-spur-gear-cad@1.0 -> ArtifactStore ->
resolve_imported_component` path. Build a mixed `CadAssemblyProgram` with
`base`, `link-1`, and `link-2` instances. Use `base` as stationary and both
descendants as moving so the generic multiple-moving partition is exercised.

Use the serial topology:

```text
base --joint-1--> link-1 --joint-2--> link-2
```

Use these four ordered configurations:

```python
(
    JointConfiguration(model_id=model.model_id, positions={"joint-1": 0.0, "joint-2": 0.0}),
    JointConfiguration(model_id=model.model_id, positions={"joint-1": 30.0, "joint-2": 0.0}),
    JointConfiguration(model_id=model.model_id, positions={"joint-1": 0.0, "joint-2": 30.0}),
    JointConfiguration(model_id=model.model_id, positions={"joint-1": 30.0, "joint-2": 30.0}),
)
```

Use the generated link instances at z=20 mm and the stationary base at z=0 mm,
with joint limits of -45 to 45 degrees and the four exact configurations shown
above. The fixture is chosen to exercise real positive-clearance measurements
without changing the generic algorithm to force a classification.

- [ ] **Step 1: Add runtime-gated live test.**

Skip only when `discover_freecad().available` or required gear/build123d
dependencies are unavailable. Set `MECHCAD_FREECADCMD` using existing discovery
semantics, never hardcode it in production code.

- [ ] **Step 2: Assert real M10-2 hierarchy preservation.**

For each returned configuration result, assert link-1 changes under q1-only,
link-2 changes under q1-only and q2-only, and link-1 is unchanged under q2-only.
Compare Q2 evaluated after Q1 with an independent Q2 call from the source
assembly to prove no cumulative drift.

- [ ] **Step 3: Assert real exact evidence and provenance.**

For every configuration and every required pair, assert finite nonnegative
interference volume and distance, exact classification, configuration hash, and
transformed assembly hash. The default provider must report
`freecad-transient-exact`, non-null backend provenance, FreeCAD library version,
and `freecadcmd-subprocess`. This test must execute real
`common().Volume` and `distToShape()`; no deterministic callback is permitted.

- [ ] **Step 4: Assert source/transient discipline.**

Compare source assembly hash before and after. Confirm state revision/hash are
unchanged. Snapshot public artifact metadata before the sweep and assert the
sweep adds no per-configuration CAD artifacts; only the intentionally produced
trusted imported artifact may exist.

- [ ] **Step 5: Run the live test.**

Run: `python -m pytest tests/integration/test_m10_3_live_multi_joint_collision.py -q -s`

Expected when runtime is available: PASS with printed configuration,
transform, exact pair, identity, and provenance evidence. Expected when runtime
is unavailable: explicit skip, reported as runtime-gated rather than replaced
by fake live evidence.

## Task 6: Run Regression and Acceptance Verification

**Files:**
- No source changes unless verification identifies a narrow defect with a regression test.

- [ ] **Step 1: Run focused M10-3 and provenance suites.**

Run: `python -m pytest tests/unit/test_multi_joint_collision_sweep.py tests/integration/test_m10_3_provenance.py tests/integration/test_m10_3_live_multi_joint_collision.py -q -s`

- [ ] **Step 2: Run required regressions.**

Run:

```text
python -m pytest tests/unit/test_multi_joint_kinematics.py tests/test_m10_1_continuous_proof.py tests/integration/test_m10_1_live_continuous_proof.py tests/integration/test_m9_4_trusted_analysis_backend_provenance.py tests/integration/test_m9_3_live_mixed_assembly_exact_kinematic.py tests/integration/test_m8c3_production_kinematic_vertical_slice.py tests/unit/test_transient_assembly_analysis.py tests/unit/test_transient_freecad_measurement.py tests/integration/test_m7c1_transient_freecad_measurement_live.py tests/unit/test_cad_assembly.py tests/unit/test_cad_assembly_mixed.py tests/unit/test_assembly_integrity.py tests/unit/test_artifacts.py -q
```

Expected: all selected M9/M10 regression tests pass, with runtime-gated live
tests reported as skips only when their existing runtime conditions are absent.

- [ ] **Step 3: Run compile and full-suite checks.**

Run:

```text
python -m compileall src/mechcad_harness -q
python -m pytest tests/
git diff --check
```

Record exact passed, failed, skipped, and error counts. Do not claim live
acceptance if the real runtime test is skipped.

## Task 7: Write Acceptance Audit and Normative Documentation

**Files:**
- Create: `docs/audit/MECHCAD_M10_3_COMPLETION_REPORT.md`
- Modify: `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`
- Modify: `docs/architecture/MECHCAD_RUNTIME_FLOW.md`
- Modify: `docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md`
- Modify: `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write the completion report from actual output.**

Include the exact architecture path, request/result types, evaluator version,
fixture provenance, four configurations in order, hierarchy transforms,
per-pair `common().Volume`/`distToShape()` measurements and classifications,
source/transient discipline, identity hashes, provider/backend/FreeCAD
provenance, test counts, limitations, and final disposition.

- [ ] **Step 2: Update normative docs only after live/full acceptance.**

Describe the new capability only as exact discrete multi-joint
collision/clearance evaluation. Use `continuous_path_verified=False` and do
not claim trajectory safety, swept-volume safety, or continuous multi-axis
verification. Preserve the current system limitations and add M10-4 as the
next boundary.

- [ ] **Step 3: Verify documentation consistency.**

Run: `git diff --check`

Search all changed normative docs for both `continuous_path_verified` and any
stale M10-3 status spelling. Confirm the completion report's disposition is one
of the required values and matches actual runtime/test evidence.
