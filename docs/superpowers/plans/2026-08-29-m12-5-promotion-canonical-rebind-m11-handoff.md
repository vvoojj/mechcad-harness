# M12-5 Promotion, Canonical Rebind, And M11 Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote one explicitly selected, current feasible M12 candidate through the ordinary change path into canonical physical-mechanism authority, then freshly reconstruct, compile CAD, verify M10, and optionally assess post-promotion M11 eligibility.

**Architecture:** Add a typed `DesignState.physical_mechanisms` collection and compile a complete mechanism into one ownership-checked add operation. After readiness and compilation, create one normal run bound to the pre-promotion source solely for correlation and ArtifactStore scope, then publish and verify the durable decision artifact before applying through `RunController`/`ChangeEngine`; after the new revision, independently rebuild canonical CAD/M10 without candidate authority. M11 remains a post-promotion, optional eligibility assessment only.

**Tech Stack:** Python 3.11+, Pydantic v2, SHA-256 canonical JSON, StateManager/ChangeEngine/RunController, ArtifactStore, FreeCAD M10, existing M11 models.

## Global Constraints

- Preserve Python 3.11+, Pydantic v2, UTC-aware datetime, canonical JSON, and SHA-256 conventions.
- `DesignState` remains the sole canonical authority; only `ChangeEngine` creates revisions.
- Do not create a candidate store, promotion store, second ChangeEngine, second lock, direct state mutation, automatic rebase, rollback, M12-6 capability, or assembly FEA.
- `CandidatePromotionPolicy` defines mapping permissions only; it never contains candidate-specific physical values.
- Candidate CAD/M10/evaluation/comparison remain noncanonical. Canonical reconstruction must not require candidate objects after promotion.
- Preserve component property availability and authority exactly; never convert policy assumptions or derived M12-3 results into source authority.
- M11 is post-promotion only, single-solid only, and optional unless a future canonical requirement makes it mandatory.
- The normal run is correlation and ArtifactStore storage scope only. Its `run_id` is excluded from every promotion semantic identity, including request, projection, compilation, proposal, and canonical-mechanism hashes.
- Do not commit, tag, or push. Preserve unrelated dirty/untracked worktree contents.
- Use test-driven development for every implementation task. Do not rely on timing sleeps for concurrency proofs.

---

## Verified Current Contracts

### DesignState And Paths

- `src/mechcad_harness/models/design.py:71-103` defines `DesignState` as a strict `Model` with list collections; `structural_analysis_definitions` is the nearest typed list precedent.
- `src/mechcad_harness/changes/engine.py:30-105` parses slash paths and resolves list entries by their `id`; `add /collection/<id>` appends a value only when no matching `id` exists.
- `src/mechcad_harness/state/hashing.py:8-19` hashes every `DesignState.model_dump(mode="json")` field. `StateManager._read_snapshot()` at `state/manager.py:190-206` reconstructs `RevisionSnapshot` and recomputes this hash.
- `tests/unit/test_state_foundation.py:176-260` proves a typed list contributes to state hash, survives JSON round trip, rejects duplicate IDs, and supports add/replace/remove through ChangeEngine.

### Ownership, ChangeEngine, And RunController

- `OwnershipPolicy.owner_for/check` in `changes/ownership.py:33-50` supports exact prefix/wildcard rules. `config/ownership.yaml:18-22` demonstrates the narrow `/structural_analysis_definitions/*` pattern.
- `ChangeEngine.prepare_proposal()` at `changes/engine.py:113-140` checks base, ownership, operations, and Pydantic result; `apply_proposal()` at `142-149` currently calls prepare before `StateManager.create_revision()`, leaving a check-then-apply window.
- `StateManager.project_lock()` at `state/manager.py:45-86` uses a per-project re-entrant `threading.RLock` and a process file lock. `create_revision()` at `138-164` reacquires it; the only other callers are `RunController.create_run()` (`runs/controller.py:24-76`), `StateManager.promote_existing_revision()`, and `StructuralAnalysisService.execute()`.
- `RunController.apply_approved_proposal()` at `runs/controller.py:160-184` calls ChangeEngine, advances/saves run state, writes `REVISION_ADVANCED`, builds/persists invalidation, then returns the updated `Run`. On invalidation persistence failure it blocks the run and raises `InvalidRunTransitionError` after the revision exists; `tests/unit/test_runs.py:267-284` verifies this state but no receipt is exposed.

### Proposal, Artifacts, M12, CAD/M10, Dependencies, And M11

- `ChangeProposal.id` and `ChangeSet.id` are only nonempty strings (`models/proposal.py:15-54`); ChangeSet IDs are UUID-generated in `ChangeEngine.prepare_proposal()` (`engine.py:131-139`). M12-5 must compute `promotion_proposal_hash` separately from base binding plus ordered operations.
- `ArtifactStore` stores artifacts under `projects/<project>/runs/<run>/artifacts/<artifact>`; `publish/read_verified_strict/read_verified_in_project` in `artifacts/storage.py:43-137` provides immutable JSON publication, run-scoped resolution, and unique project-wide fresh byte/hash lookup. M12-5 must create its normal pre-promotion run before publishing either promotion manifest, and use that run ID only as ArtifactStore scope/correlation.
- Candidate integrity/currentness is `candidates/services.py:25-76`; evaluation currentness is `candidates/evaluation.py:859-1019`; selection is `candidates/selection.py:40-265`; comparison is `candidates/comparison.py:103-390`.
- M12-4 candidate geometry/placement/fidelity validation is `candidates/cad_realization.py:69-492`; candidate M10 scope/binding/inventory is `candidates/m10_evaluation.py:97-665`. They are candidate-bound and cannot be reused with a synthetic candidate.
- Reusable generic CAD inputs are `CadAssemblyProgram`/`CadRigidTransform` (`cad_assembly.py:16-132`), `compile_mounting_plate()` (`cad_compilation.py:179-225`), and `resolve_imported_component()` (`imported_component.py:71-102`). The imported-component contract deliberately copies the selected artifact's original `bound_revision`/`bound_state_hash`; a canonical N+1 CAD realization therefore records N+1 separately from imported source provenance. `tests/integration/test_transient_imported_multishape_collision.py:168-439` is the imported multi-shape regression.
- The existing M10 entrypoint is `ProductionApplication.prove_continuous_single_axis_clearance()` (`application.py:938-990`); it binds supplied source revision/state hash and emits existing M10 evidence.
- `DependencyGraph.path_matches()` is prefix/wildcard-only (`dependency/graph.py:70-85`), and `EvidenceStore` uses node-level invalidation (`dependency/storage.py:39-107`). It cannot dynamically connect mechanism IDs to separate evidence nodes; M12-5 must document family-level precision when using a wildcard rule.
- M11 requires a complete `StructuralAnalysisDefinition` (`models/structural.py:481-577`), source-bound persistent STEP in `StructuralSourceBinding` (`structural_request.py:18-140`), and one solid (`structural/service.py:125-166`). `tests/integration/test_m11_3_live_structural.py:82-164` is the live construction precedent.

## Planned File Structure

- Create `src/mechcad_harness/models/physical_mechanism.py`: canonical physical mechanism state models and normalized state projection types.
- Modify `src/mechcad_harness/models/design.py`: add `physical_mechanisms` plus uniqueness validation.
- Modify `src/mechcad_harness/models/__init__.py`: lazy exports for canonical mechanism models.
- Modify `src/mechcad_harness/config/ownership.yaml` and `config/dependencies.yaml`: narrow mechanism owner/rules only.
- Modify `src/mechcad_harness/changes/engine.py`: generic locked application path.
- Modify `src/mechcad_harness/runs/errors.py` and `runs/controller.py`: generic post-apply invalidation error that preserves applied receipt.
- Create `src/mechcad_harness/candidates/promotion_models.py`: request, policy, classification, projection, compilation, application, verification, M11 intent/handoff, and manifest-specific durable-input-reference models.
- Create `src/mechcad_harness/candidates/promotion.py`: readiness, mapping, proposal hash, projection, compiler, and run-scoped orchestration.
- Create `src/mechcad_harness/candidates/promotion_artifacts.py`: decision/result manifests and ArtifactStore publisher/resolver.
- Create `src/mechcad_harness/candidates/canonical_mechanism.py`: state-only reconstruction and projection round-trip service.
- Create `src/mechcad_harness/candidates/canonical_cad.py`: canonical-source CAD compiler and canonical physical-to-CAD mapping.
- Create `src/mechcad_harness/candidates/canonical_m10.py`: candidate-independent canonical M10 execution plus initial-only scope-equivalence comparison.
- Create `src/mechcad_harness/candidates/m11_handoff.py`: target-intent resolution and eligibility-only handoff.
- Modify `src/mechcad_harness/candidates/__init__.py` and `src/mechcad_harness/application.py`: exports, composition, and thin production methods.
- Create focused M12-5 unit/integration tests under `tests/unit/` and `tests/integration/`; update reference/audit documentation only after verification.

## Tasks

### Task 1: Canonical Physical-Mechanism Models

**Files:**
- Create: `src/mechcad_harness/models/physical_mechanism.py`
- Modify: `src/mechcad_harness/models/__init__.py`
- Test: `tests/unit/test_m12_canonical_physical_mechanism.py`

**Interfaces:**
- Produces `CanonicalPhysicalMechanism`, `CanonicalPhysicalComponent`, `CanonicalComponentSpecification`, `CanonicalComponentProperty`, `CanonicalAcceptedDesignChoice`, `CanonicalPlacement`, `CanonicalJointPhysicalBinding`, `CanonicalPhysicalPairRequirement`, `CanonicalGeometryFidelity`, and `CanonicalM10VerificationObligation`.
- Every model is frozen, `extra="forbid"`, content-addressed where it has a semantic identity, and contains no candidate CAD/M10 execution ID fields.

- [x] Write failing schema tests for complete JSON round trip, duplicate mechanism/component IDs, missing/not-applicable property preservation, policy-origin design-choice provenance, and rejection of CAD request/result/inventory fields in an M10 obligation. Evidence: `.superpowers/sdd/task-1-report.md` records the red collection run and 14 final focused tests.
- [x] Run `py -3 -m pytest tests/unit/test_m12_canonical_physical_mechanism.py -q`; expect collection/import failure. Evidence: `.superpowers/sdd/task-1-report.md` records the expected missing-export `ImportError`; final focused result was 14 passed.
- [x] Implement the canonical models using explicit fields rather than `dict`, for example: Evidence: `.superpowers/sdd/task-1-report.md` records the ten typed canonical models and 153 focused/relevant model tests.

```python
class CanonicalM10VerificationObligation(Model):
    joint_semantic_key: str
    angle_interval_deg: tuple[float, float]
    required_clearance_mm: float
    physical_pair_requirements: tuple[CanonicalPhysicalPairRequirement, ...]
    fidelity_requirements: tuple[tuple[str, CanonicalGeometryFidelity], ...]
    required_home_check_semantics: tuple[str, ...] = ()
    bounded_limitations: tuple[str, ...] = ()
```

- [x] Keep the joint record a binding snapshot (`joint_id`, expected parent/child instance IDs, axis/frame, semantic hash/version), not an independently editable `RevoluteJointModel`. Evidence: `.superpowers/sdd/task-1-report.md` confirms snapshot-only joint semantics and 14 focused tests.
- [x] Export models lazily from `models/__init__.py` and run the focused test; expect pass. Evidence: `.superpowers/sdd/task-1-report.md`, 14 focused and 153 relevant model tests passed.

### Task 2: DesignState Integration And Canonical Paths

**Files:**
- Modify: `src/mechcad_harness/models/design.py:71-103`
- Test: `tests/unit/test_state_foundation.py`
- Test: `tests/unit/test_m12_canonical_physical_mechanism.py`

**Interfaces:**
- `DesignState.physical_mechanisms: list[CanonicalPhysicalMechanism]` defaults empty and rejects duplicate IDs.

- [x] Add failing tests modeled on `test_structural_definition_is_canonical_state_and_affects_hash` and `test_change_engine_mutates_structural_definition_collection_items`. Evidence: `.superpowers/sdd/task-2-report.md` records 13 expected failures before integration.
- [x] Assert `/physical_mechanisms/PM-1` follows the existing list-item-by-id add/replace/remove behavior and a malformed partial value fails Pydantic validation. Evidence: `.superpowers/sdd/task-2-report.md`, 31 focused and 49 regression tests passed.
- [x] Add the field and uniqueness validator without changing state hashing; `state_hash()` already hashes every field through `canonical_payload()`. Evidence: `.superpowers/sdd/task-2-report.md` confirms unchanged hashing and duplicate-ID validation.
- [x] Run `py -3 -m pytest tests/unit/test_state_foundation.py tests/unit/test_m12_canonical_physical_mechanism.py -q`; expect pass. Evidence: `.superpowers/sdd/task-2-report.md`, 31 passed in 1.97s.

### Task 3: Ownership And Dependency Configuration

**Files:**
- Modify: `config/ownership.yaml`
- Modify: `config/dependencies.yaml`
- Test: `tests/unit/test_changes.py`
- Test: `tests/unit/test_dependency.py`

**Interfaces:**
- Adds only `/physical_mechanisms/* -> mechcad-physical-mechanism`.
- Adds the supported family-level M10 dependency nodes `analysis.continuous_clearance_proof` and `analysis.kinematic_sweep`. Do not add an `analysis.structural` rule until a canonical structural definition explicitly declares consumption of `/physical_mechanisms/<id>`; the current structural schema has no such relation.

- [x] Write failing owner tests proving the new owner can add exactly `/physical_mechanisms/PM-1` but cannot write requirements, components, structural definitions, or a root path; retain existing-owner assertions. Evidence: `.superpowers/sdd/task-3-report.md` records the expected ownership failure and 22 focused tests.
- [x] Write graph tests showing `DependencyGraph.impact(("/physical_mechanisms/PM-1",))` has exactly `analysis.continuous_clearance_proof` and `analysis.kinematic_sweep`, and document that `path_matches()` cannot create dynamic per-mechanism evidence nodes or infer structural consumption. Evidence: `.superpowers/sdd/task-3-report.md`, 53 focused/predecessor tests passed.
- [x] Add the narrow ownership rule and one `/physical_mechanisms/*` dependency rule for those two M10 nodes. Do not add root or broad unrelated ownership, and do not invalidate `analysis.structural` solely because any mechanism changed. Evidence: `.superpowers/sdd/task-3-report.md` confirms exact YAML scope.
- [x] Run `py -3 -m pytest tests/unit/test_changes.py tests/unit/test_dependency.py -q`; expect pass. Evidence: `.superpowers/sdd/task-3-report.md`, 22 focused and 53 predecessor tests passed.

### Task 4: Generic ChangeEngine Atomicity Correction

**Files:**
- Modify: `src/mechcad_harness/changes/engine.py:108-149`
- Test: `tests/unit/test_changes.py`

**Interfaces:**
- `ChangeEngine.apply_proposal(project_id, proposal) -> AppliedChangeResult` revalidates base and builds/applies under one existing `StateManager.project_lock` scope.
- `prepare_proposal()` remains inspection-only; `apply_proposal()` must not trust a prior preparation.

- [x] Use test-only monkeypatching of the private locked preparation helper and `threading.Event` barriers, not a production test-hook API. Cover both valid lock orderings without sleeps: (A) promotion validates N under `project_lock`, commits N+1, then the competing N-bound writer acquires the lock and fails stale-base validation unless it independently builds a proposal against N+1; (B) the competing writer commits N+1 first, then promotion acquires the lock, rereads the pointer, raises `StaleProposalError`, and creates no promotion revision. The proof target is that no payload validated against N can commit after an intervening revision. Evidence: `.superpowers/sdd/task-4-report.md`, 29 focused/predecessor tests passed with Event barriers.
- [x] Add a nested-lock regression that calls `apply_proposal()` while `StateManager.project_lock()` is already held; it must complete without deadlock because the active lock is re-entrant. Evidence: `.superpowers/sdd/task-4-report.md` records the nested-lock regression and 29 passing tests.
- [x] Refactor to a private `_prepare_proposal_locked()` and implement: Evidence: `.superpowers/sdd/task-4-report.md` confirms locked validation and revision creation.

```python
def apply_proposal(self, project_id: str, proposal: ChangeProposal) -> AppliedChangeResult:
    with self.state_manager.project_lock(project_id):
        _, updated, changeset = self._prepare_proposal_locked(project_id, proposal)
        snapshot = self.state_manager.create_revision(project_id, updated)
        changed_paths = tuple(
            dict.fromkeys(operation.path for operation in proposal.operations)
        )
        return AppliedChangeResult(snapshot, changeset.id, changed_paths)
```

- [x] Do not add a promotion lock, retry, or rebase. Run `py -3 -m pytest tests/unit/test_changes.py tests/unit/test_state_foundation.py -q`; expect pass. Evidence: `.superpowers/sdd/task-4-report.md`, 29 passed; no promotion lock/retry/rebase was added.

### Task 5: Generic RunController Post-Apply Failure Receipt

**Files:**
- Modify: `src/mechcad_harness/runs/errors.py`
- Modify: `src/mechcad_harness/runs/controller.py:160-184`
- Test: `tests/unit/test_runs.py`

**Interfaces:**
- Add `PostApplyInvalidationError(InvalidRunTransitionError)` carrying the exact `AppliedChangeResult` and blocked `Run` snapshot so callers can publish truthful post-application status without guessing the revision.
- Keep successful `RunController.apply_approved_proposal()` return type as `Run` for existing callers.

- [x] Extend `test_m3_failure_follows_canonical_revision_and_blocks_without_guessing_impact` to assert the raised error contains `applied.snapshot.revision == 2`, `changeset_id`, and the blocked run; the state revision must exist. Evidence: `.superpowers/sdd/task-5-report.md` records the exact receipt assertions.
- [x] Change only the invalidation-persistence `except` block to raise the new exception after saving `RunStatus.BLOCKED`; do not catch ChangeEngine rejections as post-apply failures. Evidence: `.superpowers/sdd/task-5-report.md` confirms the narrow exception boundary.
- [x] Run `py -3 -m pytest tests/unit/test_runs.py tests/unit/test_tools.py -q`; expect pass. Evidence: `.superpowers/sdd/task-5-report.md`, 42 passed in 3.74s.

### Task 6: Promotion Request, Policy, Classification, And Proposal Identity Models

**Files:**
- Create: `src/mechcad_harness/candidates/promotion_models.py`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/unit/test_m12_promotion_models.py`

**Interfaces:**
- Define `PromotionValueClassification`, `CandidatePromotionPolicy`, `CandidatePromotionRequest`, `PromotionDecisionInputReference`, `PrePromotionM10ScopeProjection`, `PostPromotionM11TargetIntent`, `PromotableMechanismProjection`, `CandidatePromotionCompilation`, `PromotionApplicationStatus`, and `PromotedMechanismVerificationResult`.
- Define `promotion_proposal_hash(base_revision, base_state_hash, operations) -> str` using canonical JSON and ordered operation dumps.

- [x] Write failing tests for strict reconstruction, policy/request separation, no candidate-specific policy values, zero/false policy-origin explicit classification, semantic hash changes when operation/base changes despite a reused `ChangeProposal.id`, and `PromotionDecisionInputReference` rejection of full candidate/evaluation/selection/comparison payload fields. Evidence: `.superpowers/sdd/task-6-report.md` records red collection and fix-wave failures.
- [x] Implement a frozen, strict request that binds exact candidate/request/policy/M12-3/evaluation/selection and optional comparison data. The request carries `PostPromotionM11TargetIntent`, never a `CanonicalM11HandoffRequest`. Evidence: `.superpowers/sdd/task-6-report.md`, 17 focused and 171 model/regression tests passed.
- [x] Implement frozen, strict `PromotionDecisionInputReference` as the manifest-only representation. It contains `promotion_request_hash`, project/base revision/base state hash, candidate/synthesis request/synthesis policy/M12-3/evaluation/selection hashes, comparison flag plus comparison/request hashes when used, promotion policy hash, canonical target mechanism ID, optional M11 target intent, and mapping/classification identities. It contains no `MechanicalDesignCandidate`, evaluation, selection, comparison, CAD, or M10 object payload. Evidence: `.superpowers/sdd/task-6-report.md`, strict durable-reference tests passed.
- [x] Implement frozen, strict `PrePromotionM10ScopeProjection` as the compact normalized pre-mutation requirement projection used only by the initial equivalence proof. It contains joint meaning, interval/path semantics, clearance, physical pair requirements, fidelity, home semantics, and bounded limitations, but no candidate/CAD request IDs, pair inventory, proof budget, runtime path, or execution result. It is not accepted by canonical M10 execution. Evidence: `.superpowers/sdd/task-6-report.md`, 171 model/regression tests passed.
- [x] Implement `promotion_proposal_hash` over this exact payload: Evidence: `.superpowers/sdd/task-6-report.md` confirms ordered canonical JSON hashing.

```python
{"base_revision": base_revision, "base_state_hash": base_state_hash,
 "operations": [operation.model_dump(mode="json") for operation in operations]}
```

- [x] Run `py -3 -m pytest tests/unit/test_m12_promotion_models.py -q`; expect pass. Evidence: `.superpowers/sdd/task-6-report.md`, final focused result 17 passed.

### Task 7: Readiness, Mapping, And Promotion Completeness

**Files:**
- Create: `src/mechcad_harness/candidates/promotion.py`
- Test: `tests/unit/test_m12_promotion_compiler.py`

**Interfaces:**
- `CandidatePromotionCompiler(state_manager, artifact_store_factory, ...)`
- `validate_readiness(request) -> PromotionReadiness`
- `map_instances(request) -> tuple[CandidateCanonicalInstanceMapping, ...]`
- Produces `PromotionReadiness` and `CandidateCanonicalInstanceMapping`; both are frozen strict models declared in `promotion.py` before either compiler method uses them.

- [x] Write failing tests for stale/forged candidate, stale/non-admissible M12-3 result, stale/non-feasible/unresolved evaluation, candidate/evaluation/selection mismatch, comparison flag mismatch, geometry tamper, property/design variable substitution, path collision, delimiter ID rejection, and all pre-apply state equality assertions. Evidence: `.superpowers/sdd/task-7-report.md`, adversarial red runs recorded.
- [x] Reuse `CandidateIntegrityVerifier.verify`, `CandidateCurrentnessService.evaluate`, `CandidateEvaluationCurrentnessService.verify_current`, and current selection/comparison validators rather than copying their formulas. Evidence: `.superpowers/sdd/task-7-report.md` lists each reused validator.
- [x] Require the exact map `PM-1:<candidate-id>` only after lexical validation; persist it as an explicit mapping record and never recover candidate IDs by parsing it later. Evidence: `.superpowers/sdd/task-7-report.md`, 21 focused and 191 candidate/promotion regression tests passed.
- [x] Classify every direct/spur candidate input exactly once. Reject omitted/duplicated classifications, candidate CAD/M10/Evaluation authority promotion, derived M12-3 result promotion, and unclassified `POLICY_ASSUMPTION`, including `0`, `0.0`, and `False`. Evidence: `.superpowers/sdd/task-7-report.md`, classification fix-wave coverage passed.
- [x] Run `py -3 -m pytest tests/unit/test_m12_promotion_compiler.py -q`; expect pass. Evidence: `.superpowers/sdd/task-7-report.md`, 21 passed in 6.16s.

### Task 8: Frozen Promotable Projection And Compiler

**Files:**
- Modify: `src/mechcad_harness/candidates/promotion.py`
- Test: `tests/unit/test_m12_promotion_compiler.py`
- Test: `tests/unit/test_m12_promotion_projection.py`

**Interfaces:**
- `CandidatePromotionCompiler.compile(state, request) -> CandidatePromotionCompilation`
- Compilation carries canonical mechanism, one `ChangeProposal`, `promotion_proposal_hash`, mapping, and `PromotableMechanismProjection`.

- [x] Write projection tests proving identical promoted semantics hash identically and each changed property authority, accepted choice, placement input, connection, geometry source, joint binding, and obligation changes the hash; provenance-only changes do not. Evidence: `.superpowers/sdd/task-8-report.md`, 40 focused projection/compiler tests passed.
- [x] Compile only semantic candidate inputs into canonical models. Candidate CAD mappings may validate placement realization but may not become placement authority; candidate evaluation/CAD/M10/comparison payloads remain out of the canonical mechanism. Evidence: `.superpowers/sdd/task-8-report.md`, 350 related M12 tests passed.
- [x] Create exactly one add operation: Evidence: `.superpowers/sdd/task-8-report.md` confirms one-add proposal shape.

```python
ChangeOperation(
    operation="add",
    path=f"/physical_mechanisms/{mechanism.id}",
    value=mechanism.model_dump(mode="json"),
)
```

- [x] Bind the proposal to the exact current base revision/hash and run `py -3 -m pytest tests/unit/test_m12_promotion_compiler.py tests/unit/test_m12_promotion_projection.py -q`. Evidence: `.superpowers/sdd/task-8-report.md`, final focused result 40 passed.

### Task 9: Decision And Result Manifest Publication

**Files:**
- Create: `src/mechcad_harness/candidates/promotion_artifacts.py`
- Test: `tests/unit/test_m12_promotion_provenance.py`

**Interfaces:**
- `PromotionManifestService.publish_decision(store: ArtifactStore, ...)`, `resolve_decision(store: ArtifactStore, artifact_id)`, `publish_result(store: ArtifactStore, ...)`, and `resolve_result(store: ArtifactStore, artifact_id)`.
- `SelectedCandidateDecisionManifest` is pre-application; `CandidatePromotionResultManifest` is post-application.

- [x] Write failing tests for immutable JSON publication in a pre-created normal run scope, fresh strict resolution, byte tamper, schema extras, forged projection/proposal hash, candidate/evaluation/selection absence during historical verification, missing or byte-tampered selected geometry source, and result manifest mismatch. Evidence: `.superpowers/sdd/task-9-report.md` records red publication tests and source/result fix coverage.
- [x] Decision manifest must contain only `PromotionDecisionInputReference`, `PrePromotionM10ScopeProjection`, promotion policy hash, base binding, compilation/proposal/projection hashes, and mapping. It must not contain an in-memory `CandidatePromotionRequest`, full candidate/evaluation/selection/comparison object, CAD/M10 request/result/inventory payload, applied/resulting revision, or resulting state fields. Evidence: `.superpowers/sdd/task-9-report.md`, compact strict manifest contract verified.
- [x] Result manifest must contain decision artifact identity, semantic proposal hash, operational proposal/ChangeSet identifiers where available, changed paths, mechanism path, and resulting revision/state hash. Evidence: `.superpowers/sdd/task-9-report.md`, result binding tests passed.
- [x] Use the one run-scoped `ArtifactStore` created from the normal pre-promotion run for both manifests. Bind the decision artifact to N/HN and the result artifact to N+1/HN1; exclude `store.run_id` from all manifest semantic hashes. Strict load recomputes self-contained model hashes, fresh-verifies selected geometry references, and never requires transient candidate objects. An explicitly published M12-2 candidate is optional additional provenance only. Evidence: `.superpowers/sdd/task-9-report.md`, 41 focused publication/artifact tests passed.
- [x] Run `py -3 -m pytest tests/unit/test_m12_promotion_provenance.py tests/unit/test_artifacts.py -q`; expect pass. Evidence: `.superpowers/sdd/task-9-report.md`, 41 passed in 3.94s.

### Task 10: Promotion Application Orchestration And Failure States

**Files:**
- Modify: `src/mechcad_harness/candidates/promotion.py`
- Test: `tests/unit/test_m12_promotion_apply.py`

**Interfaces:**
- `PromotionApplicationStatus`: `PRE_APPLY_FAILURE`, `CHANGEENGINE_REJECTED`, `PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED`, `PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED`, `PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED`, `PROMOTION_APPLIED`.
- `promote_selected_candidate(request) -> CandidatePromotionApplicationResult`.
- `CandidatePromotionApplicationResult` is a frozen strict model declared in `promotion_models.py`; it carries only the request/compilation, decision artifact, applied receipt when one exists, result artifact when one exists, and stage status/error.

- [x] Write failing ordered-call tests: readiness -> compilation -> `create_run(expected_source=N/HN)` -> construct `ArtifactStore(workspace, project_id, run_id=run.run_id)` -> decision publish -> decision reload -> `apply_approved_proposal` -> invalidation -> invalidation reload/verification -> result publish -> result reload. Assert run creation is operational only. Include decision-publication failure after run creation: N/HN remain current, no canonical revision exists, and the created run remains at N/HN without a revision-advanced/completed promotion claim. Include a semantic-tamper case where an operational `ChangeProposal.id` is reused with changed operations: recomputed `promotion_proposal_hash` must disagree with the decision manifest and application must not start. Evidence: `.superpowers/sdd/task-10-report.md`, 40 focused/run tests passed.
- [x] Create exactly one normal run with the exact N/HN `SourceBinding` as in `ProductionApplication.create_run()` (`application.py:598-618`) before any manifest publication. The run ID scopes artifacts and correlates the outcome only; it does not enter request, projection, compilation, proposal, or canonical-mechanism identities. Call `RunController.apply_approved_proposal`; do not call `ChangeEngine` directly from promotion orchestration. Evidence: `.superpowers/sdd/task-10-report.md` confirms one run-scoped store and controller-only application.
- [x] Catch decision publication/verification failure as `PRE_APPLY_FAILURE` with no revision change. Catch `StaleProposalError`/ordinary pre-apply failures as no mutation. Catch `PostApplyInvalidationError` as applied revision plus invalidation-persistence failure. After a normal controller return, fresh-load the invalidation record and verify revision, parent revision, changed paths, and ChangeSet ID; a failure is `PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED`, preserves N+1/HN1, publishes no result manifest, and makes no canonical `VERIFIED` claim. Catch result artifact failure only after loading the new revision and report applied provenance failure; never roll back. Evidence: `.superpowers/sdd/task-10-report.md`, 90 promotion/predecessor tests passed.
- [x] Run `py -3 -m pytest tests/unit/test_m12_promotion_apply.py tests/unit/test_runs.py -q`; expect pass. Evidence: `.superpowers/sdd/task-10-report.md`, final focused result 40 passed.

### Task 11: Canonical Reconstruction And Semantic Round Trip

**Files:**
- Create: `src/mechcad_harness/candidates/canonical_mechanism.py`
- Test: `tests/unit/test_m12_canonical_reconstruction.py`

**Interfaces:**
- `CanonicalPhysicalMechanismCompiler(state_manager, artifact_store_factory)`
- `reconstruct(project_id, revision, state_hash, mechanism_id) -> CanonicalMechanismReconstruction`
- `normalized_projection(reconstruction) -> PromotableMechanismProjection`
- `CanonicalMechanismReconstruction` is a frozen strict state-only result declared in `canonical_mechanism.py`; it contains the resolved canonical mechanism, trusted source references, and normalized projection hash.

- [x] Write failing tests that reconstruct from only revision N+1, the canonical mechanism, and trusted artifacts after all transient candidate/evaluation/selection objects are discarded. Evidence: `.superpowers/sdd/task-11-report.md` records the expected missing-module red run.
- [x] Write a tamper test that changes one promoted state fact, then requires projection equivalence against the frozen decision-manifest projection to fail. Evidence: `.superpowers/sdd/task-11-report.md`, tamper and 84 focused/regression tests passed.
- [x] Revalidate typed state, topology, property authority, source choices, placement relations, joint binding snapshot, and obligation. Do not import or call candidate evaluation/CAD/M10 services. Evidence: `.superpowers/sdd/task-11-report.md` confirms state-only reconstruction and source verification.
- [x] Run `py -3 -m pytest tests/unit/test_m12_canonical_reconstruction.py -q`; expect pass. Evidence: `.superpowers/sdd/task-11-report.md`, focused reconstruction tests passed.

### Task 12: Canonical CAD Compiler And Trusted Geometry Rebinding

**Files:**
- Create: `src/mechcad_harness/candidates/canonical_cad.py`
- Test: `tests/unit/test_m12_canonical_cad.py`
- Test: `tests/integration/test_transient_imported_multishape_collision.py`

**Interfaces:**
- `CanonicalPhysicalCadCompiler.realize(reconstruction) -> CanonicalCadRealization`
- `CanonicalCadRealization` binds N+1/HN1 project/revision/state/mechanism, canonical physical-to-CAD mapping, assembly, selected source content identities, their original artifact provenance, and realization hash.
- `CanonicalCadRealization` and its canonical physical-to-CAD mapping model are frozen strict models declared in `canonical_cad.py`.

- [x] Write failing tests proving a canonical N+1 mechanism can consume an explicitly selected trusted STEP artifact originally bound to N/HN; a foreign or non-selected old artifact is rejected; the same artifact ID with changed bytes fails closed; bounded geometry regenerates from canonical design choices; and the canonical realization identity binds N+1/HN1 while the imported source retains N/HN provenance. Evidence: `.superpowers/sdd/task-12-report.md`, 14 focused and 7 live tests passed.
- [x] Call `resolve_imported_component`, `compile_mounting_plate`, and `CadAssemblyProgram` directly from canonical inputs. Do not modify `CandidateCadRealizationService` or extract candidate-service helpers unless a focused test proves a duplicated input-neutral primitive is otherwise unavoidable; it must not synthesize a `MechanicalDesignCandidate`. Evidence: `.superpowers/sdd/task-12-report.md` confirms direct canonical inputs and 59 relevant regressions.
- [x] Resolve every selected source with `ArtifactStore.read_verified_in_project(artifact_id, expected_type=STEP, expected_hash=...)`, require exactly one trusted project artifact, construct a source-run-scoped `ArtifactStore` from the resolved artifact's `run_id`, and call `resolve_imported_component()`. Preserve that returned `ImportedCadComponent.source_revision/source_state_hash` as source provenance; separately bind `CanonicalCadRealization` and its request/hash to N+1/HN1. Do not republish or fabricate source-artifact provenance. Evidence: `.superpowers/sdd/task-12-report.md`, cross-revision source-provenance tests passed.
- [x] Run canonical CAD tests plus `py -3 -m pytest tests/integration/test_transient_imported_multishape_collision.py -q`; expect pass. Evidence: `.superpowers/sdd/task-12-report.md`, 14 focused, 7 live, and 59 relevant tests passed.

### Task 13: Canonical M10 Scope, Inventory, And Fresh Verification

**Files:**
- Create: `src/mechcad_harness/candidates/canonical_m10.py`
- Test: `tests/unit/test_m12_canonical_m10.py`

**Interfaces:**
- `CanonicalM10VerificationService(application).execute(reconstruction, cad) -> CanonicalM10VerificationOutcome`
- `CanonicalM10ScopeEquivalenceService.compare(frozen_pre_promotion_scope_projection: PrePromotionM10ScopeProjection, derived_canonical_scope: DerivedCanonicalM10Scope) -> CanonicalM10ScopeEquivalenceResult`
- Execution derives all interval, clearance, fidelity, home-check, pair-inventory, and request inputs solely from canonical mechanism/obligation/topology/joint binding and fresh canonical CAD mapping; no candidate-bound M10 type or frozen scope is an execution input.
- `CanonicalM10VerificationOutcome`, `DerivedCanonicalM10Scope`, `CanonicalM10ScopeEquivalenceResult`, and all runtime canonical M10 scope/inventory models are frozen strict models declared in `canonical_m10.py` and bind the promoted revision/state hash.

- [x] Write failing tests asserting candidate request hash differs from canonical request hash while initial normalized scope equivalence holds; derive classifications from canonical topology/obligation/CAD mapping rather than copying `CandidateCollisionPairInventory`. Prove changing the frozen comparison projection cannot alter canonical inventory, interval, clearance, fidelity, home checks, or M10 request generation. Evidence: `.superpowers/sdd/task-13-report.md`, review-wave red tests and 22 focused tests.
- [x] Reconstruct the M10 joint from the canonical physical binding snapshot and fail if parent/child/axis semantic hash differs. Derive same-rigid exclusions and directional moving/stationary pairs only after fresh CAD mapping. Evidence: `.superpowers/sdd/task-13-report.md`, topology and binding regressions passed.
- [x] Call `ProductionApplication.prove_continuous_single_axis_clearance()` for each canonical checked pair and `analyze_assembly_kinematics()` for required home checks. Preserve original `VERIFIED_CLEAR`, `COLLISION_WITNESS`, and `NOT_PROVEN` semantics. Evidence: `.superpowers/sdd/task-13-report.md`, 124 relevant canonical/M10 tests passed.
- [x] After initial promotion equivalence succeeds, discard all candidate/pre-promotion objects and re-execute `execute(reconstruction, cad)` from N+1/HN1 only; it must reproduce a valid canonical execution path without invoking the equivalence service. Evidence: `.superpowers/sdd/task-13-report.md`, candidate-free reexecution coverage passed.
- [x] Run `py -3 -m pytest tests/unit/test_m12_canonical_m10.py tests/test_m10_1_continuous_proof.py -q`; expect pass. Evidence: `.superpowers/sdd/task-13-report.md`, final focused/relevant results were 22 and 124 passed respectively.

### Task 14: Promoted Verification Result And Post-Promotion Failure Preservation

**Files:**
- Modify: `src/mechcad_harness/candidates/promotion_models.py`
- Modify: `src/mechcad_harness/candidates/promotion.py`
- Test: `tests/unit/test_m12_promoted_verification.py`

**Interfaces:**
- `verify_promoted_mechanism(application_result) -> PromotedMechanismVerificationResult`.
- Status maps canonical M10 to `VERIFIED`, `ENGINEERING_VIOLATION`, `UNRESOLVED`, `INTEGRITY_FAILURE`, or `OPERATIONAL_FAILURE`.

- [x] Write tests that force collision, not-proven, CAD/backend exception, and canonical source identity corruption after a successful application; assert revision/state hash remain N+1. Evidence: `.superpowers/sdd/task-14-report.md`, 26 focused and 272 relevant tests passed.
- [x] Require decision/result manifests, projection round trip, canonical M10 execution, and the initial pure scope-equivalence comparison before a `VERIFIED` result. Scope mismatch is `UNRESOLVED`; it never changes canonical M10 execution inputs. No automatic rollback or deletion is permitted. Evidence: `.superpowers/sdd/task-14-report.md` confirms stage/status and no-rollback coverage.
- [x] Keep M11 assessment optional/non-gating unless an explicit future canonical requirement says otherwise. Evidence: `.superpowers/sdd/task-14-report.md`, optional M11 boundary tests passed.
- [x] Run `py -3 -m pytest tests/unit/test_m12_promoted_verification.py -q`; expect pass. Evidence: `.superpowers/sdd/task-14-report.md`, final focused result 26 passed.

### Task 15: Post-Promotion M11 Intent, Request, And Eligibility

**Files:**
- Create: `src/mechcad_harness/candidates/m11_handoff.py`
- Test: `tests/unit/test_m12_m11_handoff.py`

**Interfaces:**
- `build_handoff_request(intent, promotion_result, reconstruction) -> CanonicalM11HandoffRequest`
- `CanonicalM11HandoffService.assess(request) -> CanonicalM11Handoff`
- Statuses: `ELIGIBLE`, `NOT_ELIGIBLE`, `UNRESOLVED`, and integrity/operational failures distinct from engineering eligibility.
- `CanonicalM11HandoffRequest` and `CanonicalM11Handoff` are frozen strict models declared in `m11_handoff.py`; neither is admitted into `DesignState` or a pre-application decision manifest.

- [x] Write failing tests for no intent (no assessment), whole-mechanism target (`NOT_ELIGIBLE`), explicitly mapped single-solid target lacking definition/material/load/support/regions (`UNRESOLVED`), and target not promoted/ambiguous/foreign (`INTEGRITY_FAILURE`). Evidence: `.superpowers/sdd/task-15-report.md`, final focused Task 15 suite reached 36 passed.
- [x] Construct the real request only after result-manifest verification and canonical reconstruction; bind N+1/HN1, mechanism identity/hash, resolved target, and eligibility scope/version. Evidence: `.superpowers/sdd/task-15-report.md`, 177 focused/relevant tests passed.
- [x] Inspect canonical `StructuralAnalysisDefinition`/`StructuralSourceBinding` only to determine eligibility. Do not create a definition, STEP artifact, material, region, load, support, structural request, or solver execution in M12-5. Evidence: `.superpowers/sdd/task-15-report.md` confirms no M11 execution.
- [x] Run `py -3 -m pytest tests/unit/test_m12_m11_handoff.py tests/unit/test_structural_models.py -q`; expect pass. Evidence: `.superpowers/sdd/task-15-report.md`, final handoff/regression evidence 177 passed.

### Task 16: ProductionApplication Composition

**Files:**
- Modify: `src/mechcad_harness/application.py:269-476,1630-1902`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/unit/test_production_application.py`
- Test: `tests/integration/test_m12_promotion_production.py`

**Interfaces:**
- Compose read-only services: `candidate_promotion_compiler`, `promotion_manifest_service`, `canonical_mechanism_compiler`, `canonical_cad_compiler`, `canonical_m10_service`, `m11_handoff_service`.
- Add thin methods: `compile_candidate_promotion`, `promote_selected_candidate`, `reconstruct_promoted_mechanism`, and `verify_promoted_mechanism`.

- [x] Write delegation/composition tests parallel to M12-4's `test_default_production_composes_candidate_services_and_attested_freecad` and assert no `apply_change`/direct mutation API is added. Evidence: `.superpowers/sdd/task-16-report.md`, composition tests and 40 final focused tests passed.
- [x] Add dependencies to `_READ_ONLY_DEPENDENCIES` and compose the services in `__init__`; application methods validate project boundary then delegate. Evidence: `.superpowers/sdd/task-16-report.md`, composition wiring review passed.
- [x] Ensure the orchestrator creates one normal source-bound run at N/HN before decision publication, creates the run-scoped ArtifactStore from that run ID, uses `RunController.apply_approved_proposal`, fresh-verifies invalidation before result-manifest publication, and executes CAD/M10/M11 only after application-result provenance completes. Treat the run ID as storage/correlation only. Evidence: `.superpowers/sdd/task-16-report.md`, 182 predecessor promotion tests passed.
- [x] Run `py -3 -m pytest tests/unit/test_production_application.py tests/integration/test_m12_promotion_production.py -q`; expect pass. Evidence: `.superpowers/sdd/task-16-report.md`, final composition result 40 passed.

### Task 17: Direct-Drive Production Capstone

**Files:**
- Create: `tests/integration/test_m12_promotion_production.py`

**Interfaces:**
- Uses existing M12-4 helpers from `tests/integration/test_m12_candidate_cad_m10_production.py:1551-1978` to construct a real ADMISSIBLE/FEASIBLE selected direct-drive candidate with trusted source STEP.

- [x] Write the live test sequence N/HN -> candidate -> M12-4 `VERIFIED_CLEAR` evaluation -> explicit selection -> promotion request -> normal N/HN-bound run -> decision artifact publish/reload in that run scope -> RunController/ChangeEngine -> invalidation reload/verification -> N+1/HN1 -> result artifact publish/reload in the same run scope -> reconstruction/projection equality -> canonical CAD -> real canonical M10 -> initial pure scope equivalence. Evidence: `.superpowers/sdd/task-17-report.md`, real FreeCAD capstone recorded.
- [x] Assert exactly one new revision; the run ID appears only in ArtifactStore/run correlation metadata and not promotion semantic identities; candidate CAD realization identity and candidate M10 request identity differ from canonical identities; semantic projection and scope remain equivalent. Evidence: `.superpowers/sdd/task-17-report.md`, 3 live cases and 252 regression tests passed.
- [x] Add both optional M11 intents: whole mechanism gives `NOT_ELIGIBLE`; mapped mount/support target gives `UNRESOLVED`; assert zero structural execution calls and overall bounded CAD/M10 result remains `VERIFIED`. Evidence: `.superpowers/sdd/task-17-report.md` records both outcomes and zero structural calls.
- [x] Run `py -3 -m pytest tests/integration/test_m12_promotion_production.py -q -s`; expect a real FreeCAD capstone when runtime is available. Evidence: `.superpowers/sdd/task-17-report.md`, final live result 3 passed.

### Task 18: External-Spur, Selection, And Replay Regressions

**Files:**
- Create: `tests/unit/test_m12_promotion_replay.py`
- Modify: `tests/integration/test_m12_promotion_production.py`

**Interfaces:**
- Uses the M12-4 external-spur fixture at `test_m12_candidate_cad_m10_production.py:1716-1830`.

- [x] Write external-spur promotion tests preserving all required physical identities, gear mesh connection, mapping, and joint binding; assert driver remains internal-motion-unmodeled and no gear coupling is created. Evidence: `.superpowers/sdd/task-18-report.md`, external-spur live and 6 focused tests passed.
- [x] Write comparison-used, comparison-not-used, and selected-non-top-ranked feasible promotion tests. Assert promotion never re-ranks. Evidence: `.superpowers/sdd/task-18-report.md`, comparison-path coverage is recorded in the 6 focused tests.
- [x] After a successful N -> N+1 promotion, replay the same request and assert stale/base rejection before a second mechanism path can be added. Evidence: `.superpowers/sdd/task-18-report.md`, replay rejection passed in 128 relevant regressions.
- [x] After initial verification, remove all candidate/pre-promotion scope objects available to the fixture and prove canonical CAD/M10 re-execution remains possible from N+1/HN1 and its selected sources alone. Evidence: `.superpowers/sdd/task-18-report.md`, candidate-cleanup reexecution coverage passed.
- [x] Run `py -3 -m pytest tests/unit/test_m12_promotion_replay.py tests/integration/test_m12_promotion_production.py -q`; expect pass. Evidence: `.superpowers/sdd/task-18-report.md`, final result 6 passed.

### Task 19: Full Trust-Boundary Regression Matrix

**Files:**
- Test: `tests/unit/test_m12_candidate_foundation.py`
- Test: `tests/unit/test_m12_candidate_cad_compiler.py`
- Test: `tests/unit/test_m12_candidate_m10_service.py`
- Test: `tests/unit/test_m12_candidate_evaluation.py`
- Test: `tests/unit/test_m12_candidate_selection.py`
- Test: `tests/unit/test_m12_candidate_comparison.py`
- Test: `tests/unit/test_changes.py`
- Test: `tests/unit/test_runs.py`
- Test: `tests/unit/test_dependency.py`
- Test: `tests/unit/test_artifacts.py`
- Test: `tests/integration/test_transient_imported_multishape_collision.py`

- [x] Run the focused M12-5 suite plus the listed predecessor suites; require zero failures/errors. Evidence: `.superpowers/sdd/task-19-report.md`, final focused matrix `401 passed` and promotion integration `5 passed`; the current full suite below is `1930 passed, 34 skipped`.
- [x] Confirm pre-application negative cases retain identical revision/state hash; confirm post-application failure cases retain the applied revision and are classified by stage. Evidence: `.superpowers/sdd/task-19-report.md`, real-controller regressions and final focused matrix `401 passed`.
- [x] Confirm decision-publication failure after run creation retains N/HN and leaves the run without a promotion-success claim; confirm invalidation persistence and invalidation fresh-verification failures retain N+1/HN1, publish no successful result manifest, and make no canonical `VERIFIED` claim. Evidence: `.superpowers/sdd/task-19-report.md`, stage-specific failure cases passed; final focused matrix `401 passed`.
- [x] Confirm a selected N/HN source artifact is reusable by N+1/HN1 canonical CAD with original artifact provenance intact; foreign/non-selected and byte-tampered sources fail closed; old canonical CAD/M10 results are rejected or invalidated after later mechanism change. Evidence: `.superpowers/sdd/task-19-report.md`, stale-result and source-provenance regressions passed; final focused matrix `401 passed`.

### Task 20: Documentation, Acceptance Evidence, And Final Verification

**Files:**
- Modify: `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md`
- Create: `docs/audit/MECHCAD_M12_5_COMPLETION_REPORT.md`
- Modify: `docs/superpowers/plans/2026-08-29-m12-5-promotion-canonical-rebind-m11-handoff.md`

- [x] Update the plan checkboxes with actual completion evidence; add no M12-6 claim. Evidence: this plan now records Task 1-19 evidence; `docs/audit/MECHCAD_M12_5_COMPLETION_REPORT.md` remains bounded to M12-5.
- [x] Update capability reference only for implemented promotion compiler, canonical physical state, ChangeEngine-only application, durable decision provenance, canonical reconstruction/CAD/M10 rebinding, and eligibility-only M11 handoff. Evidence: `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md` retains the bounded M12-5 section and no M12-6/M11 execution claim.
- [x] Write the required completion report headings and record pre/promotion/post identities, operation/path summary, direct-drive and external-spur capstones, rejected cases, M11 non-gating assessments, exact test commands/counts/timings, compile/diff/untracked scans, limits, files, and worktree status. Evidence: `docs/audit/MECHCAD_M12_5_COMPLETION_REPORT.md` and `.superpowers/sdd/task-20-report.md`.
- [x] Run focused suites, then `py -3 -m pytest tests/` with a 3600-second-or-greater ceiling, `py -3 -m compileall -q src/mechcad_harness tests`, `git diff --check`, and an explicit trailing-whitespace/EOF scan over every new untracked M12-5 source/test/plan/spec/audit file. Evidence: focused matrix `401 passed`; integration `5 passed`; exact full invocation used tool timeout `3700000 ms`, exited `0`, and reported `1930 passed, 34 skipped in 1941.16s`; final gates are recorded in the completion reports.
- [x] Perform the authority, mutation, rebinding, M11, scope, run-storage ordering, durable-manifest, cross-revision source-provenance, race-ordering, and post-apply invalidation-verification self-reviews before reporting final status. Evidence: `docs/audit/MECHCAD_M12_5_COMPLETION_REPORT.md` records the review dispositions; no unresolved scope violation was found.

## Plan Self-Review

Every approved specification element maps to a task: typed state and ownership (1-3), generic lock correctness (4), truthful run failure semantics (5 and 10), request/classification/projection/compiler (6-8), immutable provenance including historical independence (9), canonical reconstruction/CAD/M10/failure semantics (11-14), post-promotion-only M11 (15), production composition/live proof/replay (16-18), and documentation/full verification (19-20).

The plan creates the normal N/HN-bound run before both ArtifactStore publications and uses its ID only for run/artifact correlation, never semantic identity. It persists a compact `PromotionDecisionInputReference`, not full transient exploration objects, and historical verification needs no candidate/evaluation/selection objects. Canonical M10 execution accepts no frozen candidate scope; initial scope equivalence is separate pure provenance comparison. The generic race tests cover both lock orderings. Canonical N+1 CAD consumes only N+1-selected sources while preserving each source artifact's original provenance. Invalidation fresh-verification failure is a post-application status that publishes no successful result manifest. The plan contains no candidate requirement after canonical reconstruction, no candidate hash as canonical design, no direct state mutation, no candidate CAD/M10 replay, no copied M12-4 inventory, no pre-promotion canonical M11 request, no optional-M11 gating, no rollback, no dynamic dependency precision claim unsupported by `DependencyGraph`, and no M12-6 work. `ChangeProposal.id` remains operational; `promotion_proposal_hash` is semantic. No task calls for a commit because the user explicitly forbids it.

## Execution Order

Implement Tasks 1-5 before promotion-domain code. Implement Tasks 6-10 before canonical reconstruction. Implement Tasks 11-15 before application composition. Run Tasks 16-20 only after all focused unit contracts pass.
