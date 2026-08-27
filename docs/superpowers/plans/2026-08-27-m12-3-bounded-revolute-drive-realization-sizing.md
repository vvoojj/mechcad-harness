# M12-3 Bounded Revolute-Drive Realization And Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement deterministic direct-drive and external-spur revolute-drive realization, motor admissibility, nominal gear loads, and bounded solid-shaft static sizing on top of the accepted M12-2 candidate authority.

**Architecture:** Keep M12-2 models and services unchanged. Add a lower-level pure `engineering.spur` primitive shared by BuiltinTools and the new pure `revolute_drive` service. Let `ProductionApplication` validate the source, attempt construction, verify the resulting candidate's integrity/currentness, and then invoke pure engineering evaluation.

**Tech Stack:** Python 3.11+, Pydantic v2 frozen models, existing canonical JSON/SHA-256 helpers, pytest, no new runtime dependency, no CAD/FreeCAD/M10/M11/provider execution.

## Global Constraints

- `DesignState` remains the sole canonical engineering authority.
- M12-2 candidate models, candidate hashes, integrity verification, currentness, and publication remain unchanged.
- Construction returns no candidate when required topology cannot form an integrity-valid M12-2 graph.
- Missing engineering authority on an integrity-valid candidate produces `UNRESOLVED`, not a fabricated value or candidate failure.
- Aggregate precedence is `VIOLATED` -> `INADMISSIBLE`, then `UNRESOLVED`, then `ADMISSIBLE`.
- Use one scalar required output-speed magnitude in `rpm`.
- Use source-bound output-shaft static design torque for shaft torsion, driven-side spur forces, bending, and minimum diameter.
- Source authority and policy assumptions are both explicit, hashed, and provenance-classified; policy never creates engineering authority.
- The shared nominal spur arithmetic lives below `revolute_drive`, and BuiltinTools must not import the M12-3 package.
- No hidden efficiency, safety factor, component selection, catalog/search, optimization, ranking, promotion, ArtifactStore/EvidenceStore publication, CAD, M10, or M11.
- No commits or pushes are performed.

---

### Task 1: Extract Shared Nominal Spur Primitive

**Files:**
- Create: `src/mechcad_harness/engineering/spur.py`
- Modify: `src/mechcad_harness/tools/builtins.py:22-43`
- Modify: `src/mechcad_harness/engineering/__init__.py`
- Test: `tests/unit/test_spur_engineering.py`

**Interfaces:**
- Consumes existing `SpurGearInput` values: `module_mm`, `teeth_pinion`, `teeth_gear`.
- Produces `NominalSpurGeometry` with `pitch_diameter_driver_mm`, `pitch_diameter_driven_mm`, `center_distance_mm`, and `ratio_magnitude` plus `calculate_nominal_spur(module_mm, driver_teeth, driven_teeth)`.
- BuiltinTools maps the shared primitive output to its existing `SpurGearOutput` fields without changing the public ToolBroker contract.

- [ ] **Step 1: Write independent failing tests**

  Add tests that independently calculate `m*z_driver`, `m*z_driven`, `(d_driver+d_driven)/2`, and `z_driven/z_driver`; assert the shared primitive and `calc_spur_gear` expose those values. Add invalid module and tooth-count tests.

- [ ] **Step 2: Run focused tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_spur_engineering.py -q`

  Expected: FAIL because `engineering.spur` and the shared primitive do not exist.

- [ ] **Step 3: Implement the lower generic primitive**

  Use strict finite-positive validation and exact integer tooth-count validation. Keep the implementation free of `revolute_drive` imports. Update `calc_spur_gear` to call the primitive and map fields only.

- [ ] **Step 4: Run focused tests to confirm pass**

  Run: `py -3 -m pytest tests/unit/test_spur_engineering.py tests/unit/test_tools.py -q`

  Expected: PASS with existing BuiltinTools behavior unchanged.

### Task 2: Add Frozen M12-3 Models And Provenance Bindings

**Files:**
- Create: `src/mechcad_harness/revolute_drive/models.py`
- Create: `src/mechcad_harness/revolute_drive/__init__.py`
- Test: `tests/unit/test_m12_revolute_drive_models.py`

**Interfaces:**
- Produces enums `DriveArchitecture`, `EngineeringCheckStatus`, `DriveAdmissibility`, `InputProvenanceKind`.
- Produces frozen models `SourceBoundScalar`, `ConsumedPropertyBinding`, `StaticOutputShaftDesignLoadCase`, `RevoluteDriveEngineeringRequirements`, `RevoluteDriveTemplateInput`, `ShaftSupportGeometry`, `RevoluteDriveConstructionOutcome`, `EngineeringCheck`, and `RevoluteDriveAdmissibilityResult`.
- Every dimensional model validates exact units, finite values, positive domains, and rejects NaN/Inf. Every durable result uses canonical JSON hashing and excludes its own `result_hash` from the hash payload.

- [ ] **Step 1: Write failing model tests**

  Cover frozen/extra-forbid behavior, scalar speed contract, source versus policy provenance, valid/invalid efficiency, safety factor, load case, support ordering, and hash determinism. Assert `RevoluteDriveConstructionOutcome(candidate=None, status=UNRESOLVED)` is valid for incomplete construction.

- [ ] **Step 2: Run model tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py -q`

  Expected: FAIL because the package/models are absent.

- [ ] **Step 3: Implement minimal immutable schemas**

  Reuse `mechcad_harness.models.common.Model` and `state.hashing.canonical_json`. Represent requirements as explicit source-bound fields and policy assumptions as explicit `SourceBoundScalar` values with `InputProvenanceKind.POLICY_ASSUMPTION`; never coerce missing values to zero. Keep derived values, checks, and unresolved reasons separate.

- [ ] **Step 4: Run model tests to confirm pass**

  Run: `py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py -q`

  Expected: PASS.

### Task 3: Implement Pure Motor, Spur, Load, And Shaft Calculations

**Files:**
- Create: `src/mechcad_harness/revolute_drive/calculations.py`
- Modify: `src/mechcad_harness/revolute_drive/__init__.py`
- Test: `tests/unit/test_m12_motor_admissibility.py`
- Test: `tests/unit/test_m12_spur_drive_sizing.py`
- Test: `tests/unit/test_m12_shaft_sizing.py`

**Interfaces:**
- Produces pure functions `evaluate_motor_checks(...)`, `evaluate_spur_pair(...)`, `calculate_spur_loads(...)`, and `calculate_shaft_static_sizing(...)`.
- `evaluate_spur_pair` calls `engineering.spur.calculate_nominal_spur`, uses explicit driver/driven snapshots, and returns ratio, pitch geometry, scalar output-speed compatibility, and optional efficiency-bound output torque.
- `calculate_spur_loads` uses `T_design_out` and `d_driven`: `T_driven_mm=1000*T_design_out`, `Ft=2*T_driven_mm/d_driven`, `Fr=Ft*tan(phi*pi/180)`.
- `calculate_shaft_static_sizing` uses two supports and one load plane, `RA=-F*(L-a)/L`, `RB=-F*a/L`, `Mmax=sqrt(My^2+Mz^2)`, circular stress equations, `sigma_allow=Sy/n`, and `d_min=(C/sigma_allow)^(1/3)` with `C` in `N*mm`.

- [ ] **Step 1: Write independent analytical tests**

  Use hand-coded oracle equations in tests, not production functions. Cover direct motor satisfied/torque violation/speed violation/voltage mismatch/missing continuous torque/no peak substitution; spur 20/100 teeth and explicit efficiency; incompatible module/pressure angle/type; driven-side force units and invalid inputs; shaft reactions/equilibrium, maximum bending, bending/torsional/von-Mises stress, `d_min`, and `0.99*d_min`, `d_min`, `1.01*d_min` boundaries.

- [ ] **Step 2: Run focused tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_motor_admissibility.py tests/unit/test_m12_spur_drive_sizing.py tests/unit/test_m12_shaft_sizing.py -q`

  Expected: FAIL because calculation functions are absent.

- [ ] **Step 3: Implement pure calculations**

  Return per-check results with exact consumed requirement/property bindings. Treat missing or unavailable properties as `UNRESOLVED`; treat valid inadequate values as `VIOLATED`; raise only for malformed schemas or operational programming failures. Do not apply efficiency to driven-side design-load gear forces a second time. Use stress comparison `sigma_vm <= sigma_allow + max(1e-9, 1e-12*sigma_allow)`.

- [ ] **Step 4: Run focused tests to confirm pass**

  Run: `py -3 -m pytest tests/unit/test_m12_motor_admissibility.py tests/unit/test_m12_spur_drive_sizing.py tests/unit/test_m12_shaft_sizing.py -q`

  Expected: PASS with independent numerical oracles.

### Task 4: Implement Deterministic Template Construction And Candidate Creation

**Files:**
- Create: `src/mechcad_harness/revolute_drive/service.py`
- Modify: `src/mechcad_harness/revolute_drive/__init__.py`
- Test: `tests/unit/test_m12_revolute_drive_service.py`

**Interfaces:**
- Produces pure `RevoluteDriveRealizationService.construct_candidate(request, policy, template_input) -> RevoluteDriveConstructionOutcome`.
- Produces pure `RevoluteDriveRealizationService.evaluate(candidate, request, policy, requirements) -> RevoluteDriveAdmissibilityResult`.
- Construction creates ordinary M12-2 `MechanicalDesignCandidate`, `PhysicalMechanismRealization`, `MechanicalConnection`, and `JointPhysicalRealizationBinding` objects only after required topology, role, endpoint, and binding membership checks pass.
- Construction returns typed unresolved outcome with `candidate=None` for missing shaft, supports, mounts, gears, connections, interfaces, or joint binding membership.
- Evaluation assumes candidate integrity/currentness were verified by the caller, validates source-path declarations against the existing source binding, and aggregates statuses with violation precedence.

- [ ] **Step 1: Write failing construction/evaluation tests**

  Build explicit direct and spur snapshots, source binding, request, policy, and design variables. Test deterministic candidate hash equality, incomplete topology with no candidate, valid candidate with missing engineering property, direct and spur evaluation, violation plus unresolved precedence, and candidate immutability.

- [ ] **Step 2: Run service tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_revolute_drive_service.py -q`

  Expected: FAIL because the service is absent.

- [ ] **Step 3: Implement construction and orchestration**

  Build component/specification tuples in explicit semantic order. Generate only the requested architecture and explicit supplied alternatives. Bind all consumed property hashes and source paths. Keep engineering unresolved items on a valid candidate; keep topology construction failures before candidate creation. Compute result hashes from semantic fields only.

- [ ] **Step 4: Run service tests to confirm pass**

  Run: `py -3 -m pytest tests/unit/test_m12_revolute_drive_service.py -q`

  Expected: PASS.

### Task 5: Compose ProductionApplication Two-Phase Entry Point

**Files:**
- Modify: `src/mechcad_harness/application.py:221-399,442-515`
- Test: `tests/integration/test_m12_revolute_drive_production.py`

**Interfaces:**
- Adds read-only `revolute_drive_service` composition.
- Adds `ProductionApplication.realize_and_evaluate_revolute_drive(...)` returning a typed construction outcome plus optional admissibility result.
- The entry point validates `CandidateSourceBinding` against the current state before construction, calls pure construction, returns no-candidate unresolved outcome immediately on structural incompleteness, runs `CandidateIntegrityVerifier`, requires `CandidateCurrentness.CURRENT`, then runs pure evaluation.

- [ ] **Step 1: Write failing production integration tests**

  Use a real `StateManager` project with immutable revision, explicit direct and spur snapshots, and a spy/fake `ChangeEngine` assertion. Prove no revision changes, no ChangeEngine call, no artifact/evidence/CAD/M10/M11 call, currentness/integrity rejection, and deterministic results across repeated calls.

- [ ] **Step 2: Run integration tests to confirm failure**

  Run: `py -3 -m pytest tests/integration/test_m12_revolute_drive_production.py -q`

  Expected: FAIL because the application entry point/composition is absent.

- [ ] **Step 3: Add composition and two-phase orchestration**

  Add the service to `_READ_ONLY_DEPENDENCIES`, initialize it without state mutation or provider dependencies, and implement the exact sequence from the approved spec. Do not add ToolBroker registrations or optional Gearworks composition.

- [ ] **Step 4: Run integration tests to confirm pass**

  Run: `py -3 -m pytest tests/integration/test_m12_revolute_drive_production.py -q`

  Expected: PASS.

### Task 6: Add Provenance, Replay, Boundary, And Capstone Coverage

**Files:**
- Modify: `tests/unit/test_m12_revolute_drive_service.py`
- Modify: `tests/integration/test_m12_revolute_drive_production.py`
- Test: `tests/unit/test_m12_revolute_drive_provenance.py`

**Interfaces:**
- Verifies semantic result identity binds candidate/source/request/policy/design variables/consumed specification and property hashes/calculation version.
- Verifies changed motor property, gear spec/tooth count, efficiency assumption, shaft material, shaft diameter, support geometry, or calculation version changes the result hash.
- Verifies run ID/timestamp-like volatile inputs do not affect identity and forged nested/result hashes fail closed.

- [ ] **Step 1: Write failing replay and capstone tests**

  Add direct satisfied, spur satisfied, valid engineering violation, unresolved efficiency, missing authority matrix, source stale/forged candidates, C1/C2 candidate hash distinction, source-versus-policy provenance, and result serialization round-trip cases.

- [ ] **Step 2: Run tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_revolute_drive_provenance.py tests/unit/test_m12_revolute_drive_service.py tests/integration/test_m12_revolute_drive_production.py -q`

  Expected: FAIL for any missing binding or replay invariant.

- [ ] **Step 3: Close only identified provenance gaps**

  Adjust models/service binding lists and validators, never by weakening M12-2 integrity or adding defaults. Keep result status separate from construction, integrity, currentness, and operational failures.

- [ ] **Step 4: Run the complete M12-3 focused set**

  Run: `py -3 -m pytest tests/unit/test_spur_engineering.py tests/unit/test_m12_revolute_drive_models.py tests/unit/test_m12_motor_admissibility.py tests/unit/test_m12_spur_drive_sizing.py tests/unit/test_m12_shaft_sizing.py tests/unit/test_m12_revolute_drive_service.py tests/unit/test_m12_revolute_drive_provenance.py tests/integration/test_m12_revolute_drive_production.py -q`

  Expected: PASS with zero failures/errors.

### Task 7: Update Capability Reference And Completion Report

**Files:**
- Create: `docs/audit/MECHCAD_M12_3_COMPLETION_REPORT.md`
- Modify: `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md:164-195,218-230`

**Interfaces:**
- Documents only production-composed and tested M12-3 capabilities, exact bounded claim, result semantics, provenance, and limitations.
- Keeps generic mechanism synthesis, catalog, bearing life, gear strength, CAD, M10, M11, comparison, selection, promotion, and optimization explicitly absent.

- [ ] **Step 1: Write documentation assertions/checklist**

  Review the report outline against every acceptance gate and list focused commands/results to be recorded.

- [ ] **Step 2: Update capability reference conservatively**

  Change only M12 physical-component/candidate-generation rows supported by tests and production composition. Do not rewrite architecture docs or M12-2 report.

- [ ] **Step 3: Write completion report**

  Record direct/spur templates, calculation equations and authority, independent analytical tests, production entry point, capstones, limitations, and no canonical mutation.

### Task 8: Run Required Verification And Self-Review

**Files:**
- Inspect all M12-3 changed files and current worktree status.

**Interfaces:**
- Verification commands must produce complete, not partial, evidence before any final acceptance marker.

- [ ] **Step 1: Run focused predecessor regressions**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_foundation.py tests/unit/test_tools.py tests/unit/test_state_foundation.py -q`

- [ ] **Step 2: Run production composition and relevant provider tests**

  Run: `py -3 -m pytest tests/unit/test_production_application.py tests/unit/test_tools.py tests/unit/test_gear_backend.py tests/unit/test_gear_cad.py -q`

  Expected: all applicable tests pass; optional Gearworks tests may be skipped by their existing dependency guards. Record exact counts and any skips.

- [ ] **Step 3: Run the full suite with the required timeout**

  Run: `py -3 -m pytest tests/` with at least a 3600-second timeout. Record collected, passed, skipped, failed, errors, and elapsed time. Require zero failures/errors.

- [ ] **Step 4: Run compile and diff checks**

  Run: `py -3 -m compileall -q src/mechcad_harness tests` and `git diff --check`. Treat only existing unrelated CRLF warnings as warnings.

- [ ] **Step 5: Perform final engineering self-review**

  Search changed code for hidden torque/speed/efficiency/safety defaults, source/policy flattening, peak-for-continuous substitution, driver-side force misuse, unsupported strength/life claims, inferred support geometry, candidate mutation, result replay gaps, CAD/M10/M11 calls, and artifact/evidence spam. Resolve every Important/Critical issue.

- [ ] **Step 6: Perform final architecture self-review**

  Confirm exactly one shared spur arithmetic implementation, no M12-2 authority replacement, no canonical mutation, no comparison/selection/promotion, no catalog/optimizer, no optional provider dependency in M12-3, and complete no-candidate construction semantics.

- [ ] **Step 7: Report final disposition**

  Return `M12_3_BOUNDED_PHYSICAL_REVOLUTE_DRIVE_REALIZATION_SIZING_VERIFIED` only if all applicable gates and the full suite pass. Otherwise return `M12_3_NEEDS_FIXES` and list the blocking evidence.
