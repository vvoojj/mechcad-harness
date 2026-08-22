# M10-4 Continuous Multi-Joint Path Clearance Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and live-verify a deterministic conservative continuous clearance proof along an explicit piecewise-linear multi-joint path.

**Architecture:** Add typed path, reach-bound, certificate, witness, request, and result models in a dedicated M10-4 module. A proof service will evaluate M10-2 FK from the unchanged source assembly, reuse M10-3 transient exact measurement/classification semantics, derive topology-aware global reach bounds, and adaptively certify scalar path intervals. `ProductionApplication` will own trusted composition, one final Evidence record, and M10-4 provenance.

**Tech Stack:** Python 3.11+, Pydantic v2, existing `CadAssemblyProgram`, `MultiJointKinematicsService`, `TransientAssemblyAnalysisService`, `FreeCADTransientAssemblyMeasurementProvider`, pytest, real FreeCAD through `MECHCAD_FREECADCMD`.

## Global Constraints

- M10-4 proves one explicit path, not a configuration-space region.
- Preserve raw commanded angles; do not modulo-normalize, shortest-wrap, clamp, or interpolate transforms.
- Exact witness threshold is `INTERFERENCE`, `TOUCHING`, or `exact_distance_mm <= required_clearance_mm`; proof guard applies only to conservative certification.
- Every unique exact-provider invocation consumes one budget unit; cache hits consume none; exhaustion is `NOT_PROVEN`.
- Use the hierarchical telescoping proof and pair-relative `B_A + B_B` bound.
- Reuse M10-3 exact provider, pair ordering, and classification semantics; do not publish midpoint evidence/artifacts.
- Keep M10-3 `continuous_path_verified=False` and preserve M9/M10-1/M10-2/M10-3 hashes and behavior.
- Do not commit, push, reset, stash, clean, or revert existing worktree changes.

---

### Task 1: Add Typed Path and Reach-Bound Models

**Files:**
- Create: `src/mechcad_harness/multi_joint_continuous_path.py`
- Modify: `src/mechcad_harness/multi_joint_kinematics.py` only if a narrowly scoped public ancestry helper is required
- Test: `tests/unit/test_multi_joint_continuous_path.py`

**Interfaces:**
- Consumes `JointConfiguration`, `KinematicModel`, `RevoluteJointModel`, `CadAssemblyProgram`, `assembly_hash`, `kinematic_model_hash`, and a typed trusted local geometry extent record supplied through a service dependency boundary.
- Produces typed `MultiJointPath`, interpolation helpers, `MultiJointContinuousPathRequest`, pure topology reach-bound records/table, stable algorithm constants, and deterministic hashes used by later tasks. It must not open STEP/FCStd files, know ArtifactStore layout, or call FreeCAD.

- [ ] **Step 1: Write failing path validation and interpolation tests.** Cover two-waypoint minimum, model mismatch, schema mismatch, non-finite values, endpoint limits, midpoint interpolation, multiple segments, mapping-order independence, path-order sensitivity, and raw `0`, `360`, and `720` preservation.
- [ ] **Step 2: Run `py -3 -m pytest tests/unit/test_multi_joint_continuous_path.py -q` and confirm the missing typed path/request APIs fail.**
- [ ] **Step 3: Implement immutable typed path/request models.** Validate model IDs and exact joint schemas, expose deterministic `interpolate(segment_index, t)`, retain raw values, and include ordered waypoint hashes plus all proof-affecting parameters in the request hash.
- [ ] **Step 4: Add failing ancestry/reach-bound tests.** Cover serial chains, translated and non-world axes, local geometry radius, branching ancestry, fixed roots, unrelated joints, and conservative numeric bounds against representative known points.
- [ ] **Step 5: Implement topology-derived reach-bound construction.** Accept only trusted typed local extent records from the injected extent boundary, build the actual ancestor chain, record fixed local-frame offset lengths between joint-axis/reference origins, add the supplied conservative local geometry radius, return zero for unrelated joints, and include source component identity and algorithm version in the bound table. Keep all file/FreeCAD concerns outside this module.
- [ ] **Step 6: Run the focused path/reach tests and `py -3 -m compileall src/mechcad_harness -q`.** Expected: all new tests pass and compilation exits successfully.

### Task 2: Implement Exact Cached Adaptive Proof Service

**Files:**
- Create: `src/mechcad_harness/multi_joint_continuous_clearance.py`
- Modify: `src/mechcad_harness/multi_joint_collision_sweep.py` only to expose/reuse pair validation helpers without changing M10-3 semantics
- Test: `tests/unit/test_multi_joint_continuous_clearance.py`

**Interfaces:**
- Consumes typed path/request/reach-bound models, a trusted local geometry extent provider, `MultiJointKinematicsService`, `TransientAssemblyAnalysisService`, and M10-3 `CollisionClassification`.
- Produces `MultiJointContinuousClearanceProofResult`, segment/certificate/unresolved-leaf models, exact witness model, and `MultiJointContinuousClearanceProofService.execute(request, assembly)`.

- [ ] **Step 1: Write failing tests for exact witness semantics and budget accounting.** Assert exact requested-clearance violations witness without proof guard, touching/interference witness, canonical `waypoint_index` ownership for shared interior waypoints, interior `segment_index`/`t` ownership, cache hits do not consume budget, waypoint evaluations consume budget, and exhaustion returns unresolved `NOT_PROVEN`.
- [ ] **Step 2: Run the focused proof tests and confirm the service/result types are absent.**
- [ ] **Step 3: Implement exact evaluation caching.** Key by source/model/configuration/partition/tolerance semantics; invoke M10-2 FK from the unchanged source; call transient exact measurement once per unique configuration; validate pair order and result identity; track exact identities, cache hits, and budget consumption. Evaluate all waypoints first and assign any waypoint witness its canonical waypoint index before segment recursion.
- [ ] **Step 4: Write failing tests for motion bounds.** Cover one and two influencing joints, telescoping contributions from both joints, zero-motion joints, unrelated branches, fixed instances, both moving pair sides, arbitrary axes, and `0 -> 360` / `0 -> 720` commands with each contribution capped at `2R`.
- [ ] **Step 5: Implement the hierarchical chord bound.** For each interval use midpoint deltas in radians, calculate each body’s sum over actual ancestor joints from the trusted extent provider plus pure topology offsets, and use `B_A + B_B` for every required pair. Keep exact witness logic separate from proof-guard certification.
- [ ] **Step 6: Write failing tests for recursion and coverage.** Cover immediate clear leaves, subdivision-required clear paths, lower-first deterministic traversal, one unresolved pair/segment blocking the path, ordered complete coverage, witness at a waypoint, and deterministic request/result hashes.
- [ ] **Step 7: Implement adaptive scalar subdivision.** Validate all waypoints first, recursively evaluate midpoint intervals, certify only when every pair has `lower > required + guard`, record certificates/unresolved leaves, terminate on witness, and validate complete `[0,1]` coverage for every segment before allowing `VERIFIED_CLEAR`.
- [ ] **Step 8: Run `py -3 -m pytest tests/unit/test_multi_joint_continuous_clearance.py tests/unit/test_multi_joint_continuous_path.py -q`.** Expected: all focused deterministic tests pass.

### Task 3: Add Trusted Production Entrypoint and Provenance

**Files:**
- Modify: `src/mechcad_harness/analysis_provenance.py`
- Modify: `src/mechcad_harness/application.py`
- Modify: `src/mechcad_harness/models/evidence.py` or `src/mechcad_harness/dependency/storage.py` only if optional companion provenance is required for legacy compatibility
- Test: `tests/integration/test_m10_4_provenance.py`

**Interfaces:**
- Consumes `MultiJointContinuousPathRequest`, `MultiJointContinuousClearanceProofService`, existing composed provider attestation, and `EvidenceStore`.
- Produces `ProductionApplication.prove_continuous_multi_joint_path_clearance(...)`, one idempotent M10-4 Evidence record, lookup helper, and trusted provenance binding all required identities.

- [ ] **Step 1: Write failing production/provenance tests.** Verify ordinary callers cannot spoof algorithm, reach-bound, provider, backend, runtime, status, or hashes; deterministic composition is distinct from real FreeCAD composition; provenance binds source/model/request/result/proof/bound/provider/backend/runtime; and legacy provenance payloads remain compatible.
- [ ] **Step 2: Run `py -3 -m pytest tests/integration/test_m10_4_provenance.py -q` and confirm the entrypoint/provenance APIs fail.**
- [ ] **Step 3: Implement the narrow application entrypoint.** Validate source binding, construct trusted request/service-owned versions, require the real provider for live geometry reach bounds, execute completely before persistence, and persist exactly one idempotent proof Evidence record only after result validation.
- [ ] **Step 4: Extend provenance through a companion type or optional fields without changing old semantic hashes.** Record reach-bound algorithm identity, model hash, path/request hash, result hash, exact provider/backend/runtime, and execution mode.
- [ ] **Step 5: Add failure-atomicity tests.** Force FK/provider/result/Evidence failures and assert no accepted partial M10-4 Evidence is published; assert no per-midpoint M10-3 Evidence is created.
- [ ] **Step 6: Run focused provenance and existing M10-3 provenance tests.** Expected: new tests pass and legacy provenance tests remain green.

### Task 4: Add Deterministic M10-4 Regression Coverage

**Files:**
- Create/modify: `tests/unit/test_m10_4_regressions.py`
- Modify: `tests/unit/test_multi_joint_kinematics.py` only for a narrowly scoped ancestry regression if Task 1 exposes a bug
- Test existing: `tests/unit/test_multi_joint_collision_sweep.py`, `tests/test_m10_1_continuous_proof.py`

**Interfaces:**
- Consumes the completed typed models, proof service, and application composition.
- Produces explicit regression evidence for M10-2 FK identity/no drift, M10-3 exact semantic compatibility, M10-1 preservation, branch filtering, both-side motion, and deterministic hashes.

- [ ] **Step 1: Add tests comparing an M10-4 exact midpoint with M10-3 exact evaluation for the same source/model/configuration/partition/tolerances.** Compare transformed assembly hash, pair order, volume, distance, and classification without requiring duplicate durable evidence.
- [ ] **Step 2: Add tests that independently evaluate shared waypoints and midpoints from the unchanged source.** Assert no cumulative FK drift and stable result identities across repeated proof executions.
- [ ] **Step 3: Add tests for M10-3 `continuous_path_verified=False` and M10-1 status/math compatibility.** Do not update expected legacy hashes.
- [ ] **Step 4: Run focused M10-4, M10-3, M10-2, and M10-1 deterministic suites.** Record exact passed/failed/skipped/error counts.

### Task 5: Add Runtime-Gated Live Acceptance

**Files:**
- Create: `tests/integration/test_m10_4_live_continuous_multi_joint_path.py`

**Interfaces:**
- Consumes the accepted M10-3 generated/imported fixture helpers and trusted default `ProductionApplication` composition.
- Produces live evidence for `VERIFIED_CLEAR`, `COLLISION_WITNESS`, and `NOT_PROVEN`, including actual FreeCAD provider/backend/runtime and exact measurement details.

- [ ] **Step 1: Build the live fixture by reusing the accepted source-bound generated base, trusted imported STEP, and serial `base -> joint-1 -> link-1 -> joint-2 -> link-2` topology.** Keep production code domain-neutral.
- [ ] **Step 2: Add the non-zero clear path with both dependent joints changing simultaneously.** Assert real FreeCAD execution, real `common().Volume`, real `distToShape()`, complete certificates, full segment coverage, reach-bound records, unique exact-evaluation accounting, and `continuous_path_verified=True` only for `VERIFIED_CLEAR`.
- [ ] **Step 3: Add a path containing a real exact interference or requested-clearance witness.** Assert full witness fields and that it is never reported clear.
- [ ] **Step 4: Add a no-witness path with intentionally insufficient exact-evaluation budget.** Ensure the first waypoint exact provider call executes real `common().Volume` and `distToShape()`, returns no requested-clearance violation, then exhaust the remaining budget during certification. Assert `NOT_PROVEN`, unresolved intervals, false continuous flag, and no optimistic result.
- [ ] **Step 5: Run `py -3 -m pytest tests/integration/test_m10_4_live_continuous_multi_joint_path.py -q` with `MECHCAD_FREECADCMD` configured.** Runtime-gated skips are permitted only when FreeCAD is unavailable; no live acceptance claim may be made from skipped tests.

### Task 6: Write Completion Report and Update Normative Docs After Live Closure

**Files:**
- Create: `docs/audit/MECHCAD_M10_4_COMPLETION_REPORT.md`
- Modify after successful live acceptance: `AGENTS.md`, `README.md` if needed, `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`, `docs/architecture/MECHCAD_RUNTIME_FLOW.md`, `docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md`, `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`

**Interfaces:**
- Consumes exact test counts, live measurements, certificates, witnesses, provenance, hashes, runtime identity, and changed-file list.
- Produces the M10-4 audit record and precise accepted baseline status; does not begin M10-5.

- [ ] **Step 1: Run focused M10-4 path/model/reach/proof/provenance/live tests.** Record passed, failed, skipped, and error counts exactly.
- [ ] **Step 2: Run required regressions for M10-3 exact discrete collision, M10-2 FK, M10-1 continuous single-axis proof, M9 provenance/live exact geometry, transient FreeCAD analysis, ArtifactStore, and EvidenceStore.** Record exact counts.
- [ ] **Step 3: Run `py -3 -m pytest tests/`, `py -3 -m compileall src/mechcad_harness -q`, and `git diff --check`.** Do not claim full acceptance unless all required checks pass and live tests execute.
- [ ] **Step 4: Write the completion report with the exact mathematical proof, live clear/witness/NOT_PROVEN evidence, both-side motion proof, large-angle semantics, M10-3 compatibility, trusted provenance, atomicity, determinism, performance, limitations, and `M10-5` next boundary.**
- [ ] **Step 5: Update normative docs only after successful live closure.** State precisely that the system proves conservative continuous clearance along an explicit piecewise-linear multi-joint joint-space path, not arbitrary configuration-space regions or dynamics.
- [ ] **Step 6: Re-run `git diff --check` and inspect `git status --short` to ensure only intended M10-4 and existing baseline files remain changed.**

## Plan Self-Review

- Scope is one implementation plan because the path model, proof service,
  trusted production boundary, tests, and documentation form one acceptance
  unit; each task has an independently testable deliverable.
- The plan covers the required telescoping proof, invariant chain reach bounds,
  exact requested-clearance witness threshold, unique-provider-call budget,
  ancestry filtering, both moving sides, raw large-angle semantics, coverage,
  determinism, provenance, atomicity, live all-outcome acceptance, and all
  required regressions.
- No placeholder task names, unowned versions, or untyped dictionary path
  interfaces are used.
- Legacy M10-1/M10-2/M10-3 behavior and hashes are explicitly protected.
