# M12-4 Candidate CAD, M10 Evaluation, Comparison, and Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Realize a current M12 candidate as explicit transient CAD, evaluate its declared one-output-joint collision scope through unchanged M10 proof services, and produce immutable noncanonical evaluation, comparison, and selection records.

**Architecture:** Add a focused `candidates` mapping layer that preserves candidate physical-instance identity through CAD and derives pair-specific M10 proof assemblies without changing M10. CAD and M10 stages are immutable outcomes; evaluation references their identities and existing M12-3/M10 results, while comparison and selection remain separate, transient, noncanonical decisions.

**Tech Stack:** Python 3.11+, Pydantic v2 frozen models, existing canonical JSON/SHA-256 hashing, existing `CadPartProgram`/`CadAssemblyProgram`, `ArtifactStore`, FreeCAD transient measurement, M10 continuous single-axis proof, pytest.

## Existing Contract Verification

### M10 pair-granularity finding

The accepted public path is usable unchanged, with a required bridge adaptation:

- `ProductionApplication.prove_continuous_single_axis_clearance` in
  `src/mechcad_harness/application.py:885-937` builds an unchanged
  `ContinuousSingleAxisProofRequest` and invokes
  `ContinuousSingleAxisClearanceProof.prove`.
- `ContinuousSingleAxisClearanceProof.prove` in
  `src/mechcad_harness/continuous_proof.py:200-226` requires every instance in
  its input assembly to appear exactly once in the moving/stationary partition;
  `CadKinematicSweepService.collision_pairs` in
  `src/mechcad_harness/kinematic_sweep.py:232-234` then derives the cross
  product.
- `CadAssemblyProgram` in `src/mechcad_harness/cad_assembly.py:47-90` permits a
  valid deterministic induced subassembly containing exactly one moving and one
  stationary constituent, preserving their original instance IDs and placements.
  `transformed_assembly_program` in `kinematic_sweep.py:203-213` then rotates
  only that moving constituent.
- The transient request/provider accepts an explicit pair tuple and asserts its
  exact returned order (`transient_assembly_analysis.py:11-39`,
  `transient_freecad_measurement.py:51-70`). The live FreeCAD script measures
  each instance shape independently with `common().Volume` and `distToShape()`
  (`transient_freecad_measurement.py:326-372`).
- Existing tests establish the one-pair contract and exact pair preservation:
  `tests/unit/test_kinematic_sweep.py:137-183`,
  `tests/unit/test_transient_assembly_analysis.py`, and
  `tests/integration/test_transient_imported_multishape_collision.py:168-190`.

Therefore M12-4 must retain the complete candidate assembly as the CAD result,
then derive a deterministic two-constituent `CadAssemblyProgram` for every
`CHECK_CLEARANCE` pair. It must never silently pass all full-assembly instances
to M10 when that cross product would include an excluded pair, and never add
candidate collision arithmetic.

### Exact home-state measurement finding

The smallest existing accepted production path for a required home-only pair is
`ProductionApplication.analyze_assembly_kinematics` in
`src/mechcad_harness/application.py:653-690`, with
`sample_angles_deg=(0.0,)` and the same deterministic two-instance induced
assembly. It constructs the existing `CadKinematicSweepRequest`, delegates to
`CadKinematicSweepService.execute`, calls the transient exact measurement path,
and records normal request/result provenance. The exact one-pair contract is
tested by `tests/unit/test_kinematic_sweep.py:137-183`; the real FreeCAD
constituent-pair path is exercised by
`tests/integration/test_transient_imported_multishape_collision.py:168-190`.

M12-4 must bind the reconstructed exact `CadKinematicSweepRequest` identity and
the returned `CadKinematicSweepResult` identity for each required home check.
An exact non-intended home interference is a hard geometric witness. A clear
home result establishes only the home configuration and cannot satisfy, or be
renamed as, a continuous internal-motion proof.

### Continuous-clearance metric finding

For a successful M10 `VERIFIED_CLEAR` result, the trusted source is
`ContinuousIntervalCertificate.minimum_certified_lower_clearance_mm` in
`src/mechcad_harness/continuous_proof.py:50-57`. The proof calculates it as the
minimum of its exact per-pair `certified_lower_clearance_mm` values in
`continuous_proof.py:337-368`; a `VERIFIED_CLEAR` result contains only certified
leaves (`continuous_proof.py:250-276`). M12-4 derives
`verified_clearance_lower_bound_mm` as the minimum of that existing field across
all certified leaves for each required checked pair, then the minimum across all
required checked pairs. It must not use discrete sweep `minimum_clearance_mm`.
`tests/integration/test_m10_1_live_continuous_proof.py:184-208` validates live
certificate coverage and positive lower bounds.

## Global Constraints

- Keep M12-1, M12-2, M12-3, generic CAD, and M10 semantics unchanged.
- `DesignState` is canonical authority; all M12-4 records are immutable and noncanonical.
- Geometry source artifact IDs within component specifications remain candidate-defining; runtime/publication/derived artifact IDs do not.
- Freshly resolve trusted STEP only through `ArtifactStore` and fail closed on byte/hash mismatch.
- Every candidate CAD instance has explicit fidelity and M10 disposition: `FIXED`, `OUTPUT_RIGID`, or `INTERNAL_MOTION_UNMODELED`.
- A rigid transform group never requires collision-geometry compounding.
- Every eligible constituent geometry pair is classified once; the expected universe and classification inventory are hashed.
- Required output clearance calls existing single-axis continuous M10 per checked pair. Do not call discrete success continuous proof.
- Required home-state checks use the existing exact discrete M10 sweep at angle `0.0` per pair and retain its original request/result identities.
- The only initial comparison metric is `verified_clearance_lower_bound_mm` in `mm` from certified M10 leaves.
- Comparison requires exact same project, `CandidateSourceBinding` hash, and candidate-independent evaluation-scope hash, never a full candidate M10 request hash.
- Requested geometry fidelity never falls back automatically: unavailable trusted/provider geometry is unresolved or an existing typed operational failure; bounded geometry is allowed only when explicitly requested and candidate-bound.
- No candidate CAD store or automatic M12-4 CAD/evaluation/comparison/selection publication; existing M10 request/result provenance Evidence remains its unchanged public-API behavior. No ChangeProposal, ChangeEngine call, canonical mutation, M11, gear coupling/mesh verification, bearing internals, new sizing, optimizer, catalog, or manufacturing/tolerance claim.
- No commits or pushes are performed.

## Planned File Structure

- Create `src/mechcad_harness/candidates/cad_realization.py`: fidelity, source/placement provenance, CAD manifest/request/result/stage models and realization service.
- Create `src/mechcad_harness/candidates/m10_evaluation.py`: M10 body disposition, comparable scope, binding, complete pair inventory, pair induced-assembly derivation, M10 request/stage models, and unchanged-M10 invocation service.
- Create `src/mechcad_harness/candidates/evaluation.py`: required-check policy, evaluation model/currentness, aggregate outcome service, and trusted metric extraction.
- Create `src/mechcad_harness/candidates/comparison.py`: fixed metric vocabulary, policy/request/result models, and lexicographic service.
- Create `src/mechcad_harness/candidates/selection.py`: immutable selection model and precondition service.
- Modify `src/mechcad_harness/candidates/__init__.py` only to expose the new public models/services.
- Modify `src/mechcad_harness/application.py` only for service composition and narrow orchestration methods.
- Create focused unit tests under `tests/unit/` and production/live tests under `tests/integration/` listed in the tasks below.
- Modify `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md` and create `docs/audit/MECHCAD_M12_4_COMPLETION_REPORT.md` only after live acceptance succeeds.

---

### Task 1: Add Candidate CAD Contracts and Strict Identity Tests

**Files:**
- Create: `src/mechcad_harness/candidates/cad_realization.py`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/unit/test_m12_candidate_cad_models.py`

**Interfaces:**
- Produce frozen `CandidateGeometryFidelity`, `CandidatePlacementOrigin`,
  `CandidateCadInstanceMapping`, `CandidateCadRealizationRequest`,
  `CandidateCadRealization`, `CandidateCadStageStatus`, and
  `CandidateCadStageOutcome`.
- `CandidateCadInstanceMapping` binds exactly one candidate physical
  `instance_id`, CAD `instance_id`, fidelity, representation identity, placement
  inputs/provenance, and a validated `CadRigidTransform`; it rejects a direct
  unproven transform.
- All semantic records use canonical JSON SHA-256, reject supplied incorrect
  hashes, and exclude no semantic input other than their own identity field.

- [ ] **Step 1: Write failing model tests**

  Add cases for deterministic hashes; changed candidate/mapping/fidelity/
  placement provenance changes identity; candidate A mapping cannot bind B;
  duplicate physical/CAD IDs reject; source geometry is distinct from bounded
  representation; unresolved CAD has typed reasons and no realization; success
  has exactly one realization; and unknown fields/fake hashes reject.

- [ ] **Step 2: Run model tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_cad_models.py -q`

  Expected: FAIL because the M12-4 CAD models do not exist.

- [ ] **Step 3: Implement immutable schemas**

  Implement a local `_hash`/`_require_hash` using existing `canonical_json`.
  Require one complete mapping for every candidate physical instance and bind
  candidate/source identity, representation-policy version, compiler identity,
  candidate-bound geometry-defining input identities, and placement provenance.
  Make `SUCCESS` carry `realization`; make `UNRESOLVED` and `NOT_REACHED` carry
  nonempty typed reasons and no fabricated realization.

- [ ] **Step 4: Run focused tests**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_cad_models.py -q`

  Expected: PASS.

### Task 2: Implement Fresh Candidate CAD Realization

**Files:**
- Modify: `src/mechcad_harness/candidates/cad_realization.py`
- Test: `tests/unit/test_m12_candidate_cad_compiler.py`
- Test: `tests/unit/test_m12_candidate_cad_replay.py`

**Interfaces:**
- Produce `CandidateCadRealizationService.realize(candidate, synthesis_request,
  synthesis_policy, request) -> CandidateCadStageOutcome`.
- Consume `CandidateIntegrityVerifier`, `CandidateCurrentnessService`, exact
  `ComponentSpecificationSnapshot.geometry_source`, existing
  `resolve_imported_component`, `ArtifactStore.existing_in_project`, and normal
  `CadAssemblyProgram`.

- [ ] **Step 1: Write failing realization tests**

  Cover candidate integrity/currentness gate; fresh trusted STEP resolution;
  source-byte/hash mutation failure; candidate source artifact substitution;
  physical-instance mapping substitution; missing supported geometry returns
  `UNRESOLVED`; generated plate representation uses only candidate-bound
  dimensions; placement changes without changed candidate reject; and imported
  multi-shape components remain represented through `ImportedCadComponent`.

- [ ] **Step 2: Run tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_cad_replay.py -q`

  Expected: FAIL because the realization service is absent.

- [ ] **Step 3: Implement the minimal service**

  Validate candidate integrity/currentness before construction. For trusted
  geometry, perform project-scoped `ArtifactStore.existing_in_project`, verify
  STEP type and SHA-256, then call `resolve_imported_component` through the
  existing trusted path. For supported generated representations, construct only
  normal `CadPartProgram` operations from declared candidate-bound dimensions.
  Use existing plate primitives for the initial generated mount/driven-body
  fixtures; do not add a generic primitive unless a fixture cannot be expressed
  with those accepted operations. Build one full `CadAssemblyProgram` preserving
  every physical and CAD instance ID. Return unresolved rather than a
  placeholder when no representation contract applies.

- [ ] **Step 4: Run focused tests**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_cad_replay.py tests/integration/test_transient_imported_multishape_collision.py -q`

  Expected: PASS; the shared multi-shape imported STEP regression remains green.

### Task 3: Add Candidate-to-M10 Binding and Complete Pair Coverage

**Files:**
- Create: `src/mechcad_harness/candidates/m10_evaluation.py`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/unit/test_m12_candidate_m10_binding.py`

**Interfaces:**
- Produce frozen `CandidateM10BodyDisposition`, `CandidateM10EvaluationScope`,
  `CandidateM10Binding`, `CandidateCollisionPairClassification`,
  `CandidateCollisionPairInventory`, `CandidateM10EvaluationRequest`, and
  `candidate_m10_scope_hash`.
- `CandidateM10Binding` requires exactly one disposition per CAD constituent,
  exact output joint/axis correspondence, and only genuine shared
  `OUTPUT_RIGID` transforms.
- `CandidateM10EvaluationScope` contains only comparable required engineering
  semantics: output-joint semantic key, interval/path, required clearance,
  candidate-independent pair-scope requirement keys/dispositions, fidelity
  requirements, required home-check semantics, proof/service version, and
  explicit policy assumptions. It excludes candidate hash, CAD realization,
  verified geometry bytes, request/result identities, and evaluation hash.
- `CandidateM10EvaluationRequest` binds the exact candidate, CAD realization,
  actual instance inventory/mapping, and `scope_hash`; it validates that the
  candidate-specific inventory realizes the scope requirements. Equivalent
  candidates can share a scope hash while always having different request hashes.
- `CandidateCollisionPairInventory.complete_for(realization, binding, scope)`
  derives the eligible constituent universe and rejects omitted, duplicated, or
  unsupported classifications.

- [ ] **Step 1: Write failing binding/coverage tests**

  Cover fixed/output/unmodeled exhaustive classification; driver gear cannot be
  fixed; shared shaft/hub output transform keeps distinct CAD collision IDs;
  shaft/bearing intended-contact exclusion does not hide hub/mount check;
  removal makes coverage incomplete; reclassification changes scope/request
  hash; candidate A/B can have equal scope but distinct request hashes; changed
  interval, clearance, required pair semantics, or fidelity changes scope hash;
  and an unmodeled home collision remains a valid separately measurable witness.

- [ ] **Step 2: Run tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_m10_binding.py -q`

  Expected: FAIL because the candidate M10 binding and inventory are absent.

- [ ] **Step 3: Implement binding and inventory validation**

  Derive a canonical unordered universe of separate CAD geometry pairs, then
  derive directional moving/stationary checks only from each eligible
  classification. Require one explicit classification and reason when excluded. Accept `CHECK_CLEARANCE`
  only for one output-rigid and one fixed constituent. Mark any required pair
  involving `INTERNAL_MOTION_UNMODELED` unresolved unless explicitly out of
  scope. Add a distinct `requires_home_exact_check` flag to an inventory entry;
  it may accompany `UNMODELED_MOTION_OUT_OF_SCOPE` and requires a non-intended
  exact home check instead of erasing the pair. Preserve exact home geometry
  eligibility separately; never use an unmodeled disposition to discard a
  measurable home interference.

- [ ] **Step 4: Run focused tests**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_m10_binding.py -q`

  Expected: PASS.

### Task 4: Invoke Existing M10 Per Checked Pair and Preserve Stage Outcomes

**Files:**
- Modify: `src/mechcad_harness/candidates/m10_evaluation.py`
- Test: `tests/unit/test_m12_candidate_m10_service.py`
- Test: `tests/unit/test_m12_candidate_m10_replay.py`

**Interfaces:**
- Produce `CandidateM10StageStatus`, `CandidateM10PairProof`,
  `CandidateHomeExactCheck`, `CandidateM10StageOutcome`, and
  `CandidateM10EvaluationService.evaluate(source_revision, source_state_hash,
  realization, binding, request) -> CandidateM10StageOutcome`.
- Accept a callable matching unchanged
  `ProductionApplication.prove_continuous_single_axis_clearance` and a callable
  matching unchanged `ProductionApplication.analyze_assembly_kinematics`.

- [ ] **Step 1: Write failing service tests**

  Assert one pair creates an induced two-instance `CadAssemblyProgram` retaining
  original placements and IDs; multiple output constituents may share a transform
  yet checks execute independently; pair-specific original M10 request/result
  hashes are preserved; path, clearance, pair inventory, CAD realization, and
  binding substitution reject replay; `NOT_PROVEN` is successful M10 execution
  with its exact result retained; and CAD unresolved/not-reached produces no fake
  M10 request/result. Add required unmodeled home-pair cases: an exact home
  collision produces a hard witness with sweep request/result identities; exact
  home clear remains a home-only result and does not satisfy required continuous
  motion; and a required internal continuous path stays unresolved.

- [ ] **Step 2: Run tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_m10_service.py tests/unit/test_m12_candidate_m10_replay.py -q`

  Expected: FAIL because the M10 stage service is absent.

- [ ] **Step 3: Implement the unchanged-M10 bridge**

  For each ordered `CHECK_CLEARANCE` pair, construct a deterministic
  `CadAssemblyProgram` containing only its two already-realized component
  definitions and instances. Call the supplied public M10 method with one moving
  and one stationary ID, exact candidate-bound source revision/hash, declared
  axis, angle interval, clearance, and proof limits. Do not call M10 for an
  excluded pair. For each entry with `requires_home_exact_check`, call the
  supplied unchanged discrete M10 method on the same two-instance assembly with
  `sample_angles_deg=(0.0,)`; reconstruct and bind its exact sweep request hash
  and returned sweep result hash. Bind all continuous and home request/result
  identities into the aggregate stage identity. Return `UNRESOLVED` when policy
  requires unmodeled continuous motion; a clear home result cannot change that.
  Propagate operational and integrity exceptions without translating them to
  engineering status.

- [ ] **Step 4: Run focused tests and predecessor proof tests**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_m10_service.py tests/unit/test_m12_candidate_m10_replay.py tests/test_m10_1_continuous_proof.py tests/integration/test_m10_1_live_continuous_proof.py -q`

  Expected: PASS with the existing M10 API and semantics unchanged.

### Task 5: Add Candidate Evaluation, Currentness, and Trusted Metric Extraction

**Files:**
- Create: `src/mechcad_harness/candidates/evaluation.py`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/unit/test_m12_candidate_evaluation.py`

**Interfaces:**
- Produce `CandidateEvaluationOutcome`, `CandidateEvaluationPolicy`,
  `CandidateMetricKey`, `CandidateMetric`, `CandidateEvaluation`,
  `CandidateEvaluationService.evaluate(...)`, and
  `CandidateEvaluationCurrentnessService.verify_current(...)`.
- Only `CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM` is valid; its unit
  is exactly `mm`.

- [ ] **Step 1: Write failing evaluation tests**

  Cover M12-3 `ADMISSIBLE` plus CAD/M10 clear to feasible; M10 collision witness
  to infeasible; M10 not-proven to unresolved with exact result reference; CAD
  unresolved with no fake identities; M12-3 inadmissible plus M10 not-reached to
  infeasible; required exact home collision to infeasible; home clear without a
  required continuous path to declared home-only satisfaction and never a
  continuous claim; hard-witness precedence over unresolved; forged/foreign M12-3,
  CAD, or M10 identities reject; and stale changed source/geometry/mapping/path/
  clearance/inventory rejects currentness.

- [ ] **Step 2: Run tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_evaluation.py -q`

  Expected: FAIL because candidate evaluation does not exist.

- [ ] **Step 3: Implement aggregate evaluation**

  Validate candidate integrity/currentness and exact M12-3 candidate/source
  binding before aggregation. Map M12-3 `INADMISSIBLE`, an original continuous
  M10 `COLLISION_WITNESS`, and exact-home `CadKinematicSweepResult` interference
  to hard witnesses; map unresolved stages and original M10
  `NOT_PROVEN` to unresolved findings; choose hard-witness precedence. Extract
  the only metric exclusively from a `VERIFIED_CLEAR` result by taking the
  minimum `minimum_certified_lower_clearance_mm` across its certificates and
  required pair proofs. Reject empty/mismatched certificates, metric unit
  substitution, and all non-verified statuses.

- [ ] **Step 4: Run focused tests**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_evaluation.py -q`

  Expected: PASS.

### Task 6: Add Deterministic Comparison

**Files:**
- Create: `src/mechcad_harness/candidates/comparison.py`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/unit/test_m12_candidate_comparison.py`

**Interfaces:**
- Produce frozen `CandidateComparisonDirection`, `CandidateComparisonPolicy`,
  `CandidateComparisonRequest`, `CandidateComparisonResult`, and
  `CandidateComparisonService.compare(request, evaluations)`.
- Policy contains only metric order/direction/unit, required feasible status,
  missing-metric rejection, tie semantics, and comparator version; request
  contains candidate/evaluation pairs and common source/scope hashes.

- [ ] **Step 1: Write failing comparison tests**

  Cover policy hash unchanged for changed candidate set; request hash changes for
  candidate/evaluation substitution; maximum lower-clearance lexicographic order;
  equal metric tie; missing metric rejection; metric source/unit substitution;
  foreign project/source binding rejection; differing M10 path/clearance/pair
  universe/fidelity scope rejection; and no hidden hash ordering preference.

- [ ] **Step 2: Run tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_comparison.py -q`

  Expected: FAIL because comparison contracts are absent.

- [ ] **Step 3: Implement fixed-vocabulary lexicographic comparison**

  Validate every evaluation is current, feasible, and belongs to the exact same
  project, source-binding hash, and candidate-independent evaluation-scope hash,
  never the full candidate M10 request hash. Require the policy to
  request only `verified_clearance_lower_bound_mm` in `mm`. Sort only by the
  declared metric direction; retain equal candidates as a tie instead of using
  a candidate hash as preference. Bind all exact metric values and input hashes.

- [ ] **Step 4: Run focused tests**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_comparison.py -q`

  Expected: PASS.

### Task 7: Add Explicit Noncanonical Selection

**Files:**
- Create: `src/mechcad_harness/candidates/selection.py`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/unit/test_m12_candidate_selection.py`

**Interfaces:**
- Produce frozen `CandidateSelection` and
  `CandidateSelectionService.select(candidate, evaluation, selector_identity,
  rationale, comparison=None)`.

- [ ] **Step 1: Write failing selection tests**

  Cover selection with comparison, selection without comparison with
  `comparison_used=False`, selected candidate/evaluation exact binding,
  non-top-ranked feasible selection with rationale, stale/foreign/forged
  evaluation rejection, infeasible/unresolved rejection, stale/foreign result
  rejection, selected candidate absent from cited comparison rejection, and
  unchanged `DesignState` revision/hash before and after every call.

- [ ] **Step 2: Run tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_selection.py -q`

  Expected: FAIL because selection does not exist.

- [ ] **Step 3: Implement selection-only validation**

  Revalidate candidate integrity/currentness and evaluation currentness. Require
  a feasible evaluation with no unresolved required check. When comparison is
  supplied, verify its request/result identity, currentness, source/scope, and
  membership; otherwise set `comparison_used=False` and reject any comparison
  hash. Return only the immutable selection record. Do not import or invoke
  `ChangeEngine`, `ChangeProposal`, M11, ArtifactStore publication, or CAD/M10.

- [ ] **Step 4: Run focused tests**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_selection.py -q`

  Expected: PASS.

### Task 8: Compose Narrow ProductionApplication Entry Points

**Files:**
- Modify: `src/mechcad_harness/application.py`
- Test: `tests/integration/test_m12_candidate_cad_m10_production.py`

**Interfaces:**
- Add `realize_candidate_cad(...)`, `evaluate_candidate(...)`,
  `compare_candidates(...)`, and `select_candidate(...)` orchestration methods.
- `evaluate_candidate` consumes a verified M12-3 result and M12-4 request/
  policy, performs CAD then M10 staging, and returns an immutable evaluation;
  it never publishes or mutates state.

- [ ] **Step 1: Write failing composition tests**

  Assert default-composed `ProductionApplication` uses its real attested
  `FreeCADTransientAssemblyMeasurementProvider`; a fake provider is rejected by
  the existing continuous path; evaluation does not alter source revision/hash;
  and app methods delegate to focused services rather than duplicate CAD/M10 or
  comparison logic. Add explicit short-circuit tests: M12-3 inadmissible yields
  CAD/M10 `NOT_REACHED` and infeasible; CAD unresolved yields M10 `NOT_REACHED`
  and unresolved; CAD success plus M10 `NOT_PROVEN` yields successful M10 stage
  carrying the exact result and unresolved evaluation.

- [ ] **Step 2: Run tests to confirm failure**

  Run: `py -3 -m pytest tests/integration/test_m12_candidate_cad_m10_production.py -q`

  Expected: FAIL because M12-4 production entry points are absent.

- [ ] **Step 3: Compose services only**

  Instantiate M12-4 services beside the existing candidate and revolute-drive
  services. `evaluate_candidate` first validates candidate/source/currentness
  and exact M12-3 binding. If M12-3 is inadmissible, create CAD and M10
  `NOT_REACHED` outcomes and aggregate immediately. Otherwise run CAD; if CAD is
  unresolved, create M10 `NOT_REACHED` and aggregate immediately. Only after CAD
  success invoke M10/home stages. Pass the existing public
  `prove_continuous_single_axis_clearance` and
  `analyze_assembly_kinematics` methods into the M10 bridge. Keep source
  validation, backend provenance, and trusted import resolution inside existing
  boundaries. Do not expose FreeCAD paths or calls through the new API.

- [ ] **Step 4: Run composition and predecessor tests**

  Run: `py -3 -m pytest tests/integration/test_m12_candidate_cad_m10_production.py tests/integration/test_m12_revolute_drive_production.py tests/integration/test_m10_1_live_continuous_proof.py -q`

  Expected: PASS.

### Task 9: Build Real FreeCAD/M10 M12-4 Capstones

**Files:**
- Modify: `tests/integration/test_m12_candidate_cad_m10_production.py`
- Test: `tests/integration/test_m12_candidate_cad_m10_production.py`

**Interfaces:**
- Reuse M12-3 integration candidate fixtures, current real FreeCAD discovery,
  `ArtifactStore` publication, `ImportedCadComponent`, generated plate programs,
  and application composition.

- [ ] **Step 1: Add direct clear, collision, and not-proven fixtures**

  Build source-bound direct-drive candidates with M12-3 admissible result,
  generated candidate-bound mount/driven-body geometry plus a freshly
  byte-verified trusted imported STEP component. Use explicit interval, required
  clearance, complete pair inventory, and output binding. Assert respectively
  real `VERIFIED_CLEAR -> FEASIBLE`, real `COLLISION_WITNESS -> INFEASIBLE`, and
  budget-constrained real `NOT_PROVEN -> UNRESOLVED`; record actual FreeCAD
  provenance and source non-mutation.

- [ ] **Step 2: Add external-spur limitation capstone**

  Build an external-spur M12-3 candidate preserving motor, driver gear, driven
  gear, shaft, supports, hub, mount, and driven-body mapping identities. Use the
  existing gear provider only when an explicitly requested trusted/provider
  representation is available. If the request requires that representation and
  it is unavailable, assert CAD unresolved or the existing typed provider
  failure, never a fallback. Use a bounded collision representation only in a
  separate fixture whose realization request explicitly selected that fidelity
  and binds every geometry-defining input. Classify driver gear as
  `INTERNAL_MOTION_UNMODELED`, inventory mesh as intended contact/out of scope,
  and assert no driver counter-rotation, mesh, phase, backlash, or internal
  transmission clearance claim is made.

- [ ] **Step 3: Add comparison/selection capstones**

  Evaluate two distinct feasible candidates with identical project,
  source-binding, and scope hashes; compare certified clearance metric values;
  assert deterministic ranking and tie behavior. Create one selection citing the
  comparison, one valid selection without comparison, and one explicit
  non-top-ranked feasible selection. Assert no canonical revision/hash changes.

- [ ] **Step 4: Run live capstones**

  Run: `py -3 -m pytest tests/integration/test_m12_candidate_cad_m10_production.py -q`

  Expected: PASS with actual current FreeCAD, generated plus imported geometry,
  exact transient measurement, and existing continuous single-axis proof.

### Task 10: Document Evidence, Run Regressions, and Complete Verification

**Files:**
- Create: `docs/audit/MECHCAD_M12_4_COMPLETION_REPORT.md`
- Modify: `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md`
- Modify: `docs/superpowers/specs/2026-08-27-m12-4-candidate-cad-m10-evaluation-comparison-selection.md` only if a proven implementation-name correction is needed

- [ ] **Step 1: Run focused M12-4 suite**

  Run: `py -3 -m pytest tests/unit/test_m12_candidate_cad_models.py tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_cad_replay.py tests/unit/test_m12_candidate_m10_binding.py tests/unit/test_m12_candidate_m10_service.py tests/unit/test_m12_candidate_m10_replay.py tests/unit/test_m12_candidate_evaluation.py tests/unit/test_m12_candidate_comparison.py tests/unit/test_m12_candidate_selection.py tests/integration/test_m12_candidate_cad_m10_production.py -q`

  Expected: 0 failed, 0 errors.

- [ ] **Step 2: Run shared-foundation regressions**

  Run: `py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py tests/unit/test_m12_revolute_drive_service.py tests/integration/test_m12_revolute_drive_production.py tests/test_m10_1_continuous_proof.py tests/integration/test_m10_1_live_continuous_proof.py tests/integration/test_transient_imported_multishape_collision.py tests/unit/test_kinematic_sweep.py tests/unit/test_transient_assembly_analysis.py -q`

  Expected: 0 failed, 0 errors.

- [ ] **Step 3: Run full verification**

  Run: `py -3 -m pytest tests/`

  Expected: 0 failed, 0 errors; record collected, passed, skipped, elapsed, and exit code.

  Run: `py -3 -m compileall -q src/mechcad_harness tests`

  Expected: exit code 0.

  Run: `git diff --check`

  Expected: exit code 0. Separately scan all new M12-4 files for trailing whitespace because `git diff --check` excludes untracked files.

- [ ] **Step 4: Write conservative completion documentation**

  Record candidate/CAD/M10/evaluation hashes, actual FreeCAD runtime identity,
  path, checked/excluded pair counts, clearance, original M10 statuses, outcome,
  geometry fidelity, mixed imported/generated path, and source non-mutation.
  State that exactness is with respect to supplied representation and that spur
  internal coupled motion is unverified. List no promotion, M11, optimizer,
  catalog, sizing, gear mesh, or manufacturing capability.

## Plan Self-Review

- **Spec coverage:** Tasks 1-4 cover source-bound CAD, placement, fidelity,
  constituent identity, unmodeled motion, complete pair inventory, and unchanged
  per-pair M10. Task 5 covers staged aggregate semantics and trusted metrics.
  Tasks 6-7 cover policy/request separation and explicit noncanonical selection.
  Tasks 8-10 cover production composition, live evidence, documentation, and
  all mandatory regressions.
- **Pair-contract check:** The plan explicitly derives two-instance induced
  assemblies because the existing M10 input partition must cover every instance;
  it neither modifies M10 nor compounds excluded geometry.
- **Metric check:** The plan names the actual current single-axis certificate
  field and excludes discrete values and unsupported shaft diameter metrics.
- **Placeholder/type check:** All planned public types, methods, paths, and test
  commands are named above. No task requires a commit because the user forbids
  commits and pushes.
- **Home/stage/scope check:** Required unmodeled home checks have an existing
  exact discrete M10 execution path and bind original identities; home clear
  never proves continuous motion. Scope contains no candidate/result identity,
  comparison uses scope rather than request hash, unavailable trusted geometry
  cannot silently downgrade fidelity, and short-circuit outcomes never fabricate
  downstream stages.
