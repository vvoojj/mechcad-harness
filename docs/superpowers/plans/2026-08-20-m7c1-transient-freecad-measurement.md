# M7C-1 Transient FreeCAD Measurement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an exact, transient FreeCAD measurement boundary for deterministic rigid-body collision sweeps without mutating canonical design state or publishing per-angle artifacts.

**Architecture:** A provider receives a hash-bound transient request and transformed `CadAssemblyProgram`, compiles the program into a temporary FreeCAD document, and runs the established M7A-2C exact measurement operations. `TransientAssemblyAnalysisService` owns identity and ordered-pair validation; `CadKinematicSweepService` creates one transient request per requested angle and delegates through that service.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, FreeCADCmd, existing FreeCAD assembly backend.

## Global Constraints

- Do not mutate `DesignState`, create `ChangeSet`s, create canonical artifacts, create public artifact records, or create per-angle persisted evidence.
- Temporary FCStd/STEP files are execution intermediates only and must remain within temporary execution workspace.
- Preserve exact M7A-2C semantics: `shape_a.common(shape_b).Volume` and `shape_a.distToShape(shape_b)[0]`.
- Do not move geometry logic into `kinematic_sweep.py` or duplicate collision algorithms.
- Preserve request pair order, sample-angle order, and fail closed for hash, identity, and pair-response mismatches.
- Use `MECHCAD_FREECADCMD` / the existing FreeCAD discovery mechanism for live tests; the live test must pass when FreeCAD is available.
- Do not commit, push, stash, reset, clean, or modify unrelated dirty worktree changes.

---

### Task 1: Transient Provider and Service Protocol

**Files:**
- Create: `src/mechcad_harness/transient_freecad_measurement.py`
- Modify: `src/mechcad_harness/transient_assembly_analysis.py`
- Modify: `tests/unit/test_transient_assembly_analysis.py`
- Create: `tests/unit/test_transient_freecad_measurement.py`

**Interfaces:**
- Consumes: `TransientAssemblyAnalysisRequest`, `CadAssemblyProgram`, `FreeCADAssemblyBackend`, and existing M7A-2C `CadAssemblyAnalysisService._analysis_script` semantics.
- Produces: `FreeCADTransientAssemblyMeasurementProvider.exact_measure(request, program) -> tuple[tuple[str, str, float, float], ...]`.

- [ ] **Step 1: Write failing unit tests**

Cover provider request/program hash validation, passing the exact transformed program and ordered pairs to its execution seam, raw exact-value propagation, rejection of wrong pair order, and no mutation of a supplied `DesignState` snapshot.

- [ ] **Step 2: Run provider tests to verify the red state**

Run: `py -m pytest -q tests/unit/test_transient_freecad_measurement.py tests/unit/test_transient_assembly_analysis.py`

Expected: collection/import failure until the provider and updated protocol exist.

- [ ] **Step 3: Implement the minimal transient provider and protocol update**

Create `FreeCADTransientAssemblyMeasurementProvider` with an injected execution seam for unit tests. The production path must construct a temporary workspace, compile the transient program using `FreeCADAssemblyBackend` assembly generation capabilities without `ArtifactStore`, run the established M7A-2C measurement script, parse structured ordered results, and return only `(moving_id, stationary_id, common_volume_mm3, distance_mm)` records. Update `TransientAssemblyAnalysisService` so `exact_measure` receives `(request, program)` and remains responsible for pair-order validation and typed result construction.

- [ ] **Step 4: Run focused unit tests**

Run: `py -m pytest -q tests/unit/test_transient_freecad_measurement.py tests/unit/test_transient_assembly_analysis.py`

Expected: all tests pass.

### Task 2: Sweep-Service Integration

**Files:**
- Modify: `src/mechcad_harness/kinematic_sweep.py`
- Modify: `tests/unit/test_kinematic_sweep.py`

**Interfaces:**
- Consumes: `TransientAssemblyAnalysisService.analyze(request, transformed_assembly)` and `TransientAssemblyAnalysisRequest`.
- Produces: `CadKinematicSweepService` delegation chain: sweep service -> transient analysis service -> provider.

- [ ] **Step 1: Write failing wiring test**

Use a recording transient analysis service/provider seam to assert one request per sample angle, the source/transformed/request hash values, exact pair inventory, transformed program, and requested sample ordering.

- [ ] **Step 2: Run the wiring test to verify the red state**

Run: `py -m pytest -q tests/unit/test_kinematic_sweep.py`

Expected: failure because the sweep service still calls its legacy `(program, pairs)` measurement seam.

- [ ] **Step 3: Implement narrow delegation**

Let `CadKinematicSweepService` accept a transient analysis service or compatible injected seam. For each requested angle, build `TransientAssemblyAnalysisRequest` from the original source hash, transformed assembly hash, request hash, angle, and existing ordered moving-by-stationary pair inventory. Delegate measurement through transient analysis and convert only its validated raw results into existing sweep pair results.

- [ ] **Step 4: Run sweep-focused unit tests**

Run: `py -m pytest -q tests/unit/test_kinematic_sweep.py tests/unit/test_transient_assembly_analysis.py tests/unit/test_transient_freecad_measurement.py`

Expected: all tests pass.

### Task 3: Exact FreeCAD Live Fixture

**Files:**
- Create: `tests/integration/test_m7c1_transient_freecad_measurement_live.py`

**Interfaces:**
- Consumes: `FreeCADTransientAssemblyMeasurementProvider` and transient analysis request/service.
- Produces: live evidence that the transient provider applies the established exact common-volume and distance measurements.

- [ ] **Step 1: Write the failing live fixture**

Create two simple box-program instances and run one pair through the provider for three placements: positive separation, face touching, and overlap. Assert ordered raw measurements: positive distance and zero common volume; zero distance and zero common volume; zero distance and positive common volume. Skip only when existing FreeCAD discovery reports unavailable; with `MECHCAD_FREECADCMD` available it must run.

- [ ] **Step 2: Run the live test**

Run: `py -m pytest -q tests/integration/test_m7c1_transient_freecad_measurement_live.py`

Expected: passes against configured FreeCADCmd, or skips only if unavailable.

### Task 4: Regression Verification

**Files:**
- Modify only files needed to correct regressions discovered by the specified commands.

**Interfaces:**
- Consumes: completed provider, transient service, sweep integration, and existing M7A-2C/M7B suites.
- Produces: verification evidence with no canonical-state or artifact side effects.

- [ ] **Step 1: Run M7C-1 focused tests**

Run: `py -m pytest -q tests/unit/test_kinematic_sweep.py tests/unit/test_transient_assembly_analysis.py tests/unit/test_transient_freecad_measurement.py tests/integration/test_m7c1_transient_freecad_measurement_live.py`

- [ ] **Step 2: Run M7A-2C regression**

Run: `py -m pytest -q tests/unit -k "m7a2c or assembly_analysis"`

- [ ] **Step 3: Run M7B regression**

Run: `py -m pytest -q tests/unit/test_m7b2c_collision_layout.py tests/unit/test_m7b2c_canonical_layout.py tests/integration/test_m7b2c_collision_layout_live.py`

- [ ] **Step 4: Run full suite**

Run: `py -m pytest -q`

- [ ] **Step 5: Inspect final working tree without altering it**

Run: `git status --short`
