# M13-4E Corrective Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the unaccepted M13-4E candidate without changing M13-3 identities, legacy promotion contracts, or production composition APIs.

**Architecture:** M13-3 remains the sole owner of compilation and projection identities. M13-4E publishes the original `compile_multi_joint()` compilation unchanged, retains candidate-ID order only for evidence mappings, and verifies the two independently ordered records through exact membership and candidate-to-canonical pairing checks. The private route uses a typed context and real `ChangeEngine` persistence.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest 8, existing `ArtifactStore`, `EvidenceStore`, `StateManager`, `RunController`, and `ChangeEngine`; no new dependencies.

## Global Constraints

- Candidate status is `M13_4E_IMPLEMENTATION_NEEDS_FIXES`; do not claim acceptance during repair.
- Do not modify `src/mechcad_harness/application.py`, M10, CAD, state schemas, M13-3 request/evaluation/selection/promotion schemas or hashes, dependencies, or legacy promotion contracts.
- Do not create `@2` schemas or change the four M13-4E wire schema literals.
- Remove `CandidatePromotionApplicationService._align_multi_joint_evidence_compilation()`; no replacement compilation/projection normalization or rehashing helper is permitted.
- Preserve the exact original `CandidatePromotionCompilation` from `compile_multi_joint()`: decision `compilation_hash`, `projection`, and `projection_hash` equal that object exactly.
- `MultiJointPromotionDecisionInputReference.mapping_identities` remains mapping-hash order by ascending `candidate_instance_id`; classification identities remain lexical ascending. Neither evidence ordering changes projection order.
- No commit, tag, push, M13-4P, M13-4, Rotator V2, FreeCAD acceptance, or production API work is authorized.

## Corrective File Map

- Modify: `src/mechcad_harness/candidates/promotion_models.py` - identity-member SHA validation only.
- Modify: `src/mechcad_harness/candidates/promotion_artifacts.py` - projection/mapping validation, application verification, and `__all__` only.
- Modify: `src/mechcad_harness/candidates/promotion.py` - remove normalization and use the strongly typed private context only.
- Modify: `src/mechcad_harness/candidates/__init__.py` - additive export only if the existing module convention requires it.
- Modify: `tests/unit/test_m13_4e_legacy_promotion_goldens.py` - independently sourced literal baseline values.
- Modify: `tests/unit/test_m13_4e_promotion_evidence.py` - decision/reference, ordering, pairing, and substitution tests.
- Modify: `tests/unit/test_m13_4e_promotion_result.py` - artifact-local resolver tamper tests.
- Modify: `tests/unit/test_m13_4e_promotion_application.py` - real failure matrix and receipt verifier tests.
- Modify: `tests/integration/test_m13_4e_promotion_evidence_acceptance.py` - metadata-rooted restart and adversarial reload tests.
- Modify last, after implementation evidence: `docs/audit/MECHCAD_M13_4E_COMPLETION_REPORT.md`.

---

### R0: Independently Freeze Legacy Goldens

**Files:** `tests/unit/test_m13_4e_legacy_promotion_goldens.py`; read legacy M12 tests and baseline commit `ca294e0` in a temporary detached worktree.

**Symbols:** legacy `CandidatePromotionRequest`, `PromotionReadiness`, `PromotionDecisionInputReference`, `SelectedCandidateDecisionManifest`, `CandidatePromotionResultManifest`, `CandidatePromotionApplicationResult`, and `PromotionApplicationStatus`.

- [ ] Write failing literal assertions for canonical JSON and self-hash of request/readiness; JSON/hash of decision input, selected decision, and result manifests; legacy decision/result IDs; exact canonical artifact bytes and byte hashes; receipt field/schema contract; and all status values. No expected value may call the helper under test.
- [ ] From detached `ca294e0`, run the legacy fixture script/tests, record the observed values as literals, then run `py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py -q` and confirm the candidate fails until literals replace tautologies.
- [ ] Add only literal constants and direct legacy imports; remove `bytes == bytes` and every expectation derived from current M13-4E behavior.
- [ ] Run: `py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py -q`.

**Acceptance criterion:** Every named legacy wire value matches independently recovered baseline literals before and after corrective production edits.

### R1: Preserve Original Compilation Identity

**Files:** `src/mechcad_harness/candidates/promotion.py`; `tests/unit/test_m13_4e_promotion_evidence.py`; `tests/unit/test_m13_4e_promotion_application.py`.

**Symbols:** `_promote_multi_joint_route`, `_align_multi_joint_evidence_compilation`, `CandidatePromotionCompiler.compile_multi_joint`.

- [ ] Write failing tests that retain the original compiler return, publish decision evidence, and assert receipt/manifest `compilation_hash == original.compilation_hash`, `projection_hash == original.projection.projection_hash`, `projection == original.projection`, and `mapping == original.mapping`.
- [ ] Run: `py -3 -m pytest tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_application.py -k "original_compilation or projection_identity" -q`; expected failure demonstrates normalization-derived hashes.
- [ ] Delete `_align_multi_joint_evidence_compilation` and its call. Pass the direct `compile_multi_joint()` result through decision publication, context construction, result publication, and receipts.
- [ ] Re-run the focused command.

**Acceptance criterion:** No M13-4E path constructs another compilation/projection and every evidence identity is the original M13-3 identity.

### R2: Repair Projection/Mapping Semantics and Pairing

**Files:** `src/mechcad_harness/candidates/promotion_artifacts.py`; `tests/unit/test_m13_4e_promotion_evidence.py`.

**Symbols:** `SelectedMultiJointCandidateDecisionManifest.validate_manifest`, `verify_multi_joint_promotion_decision`, `PromotableMechanismProjection`.

- [ ] Write failing tests with a valid M13-3 compilation where projection realization order differs from candidate mapping order; require publication/resolution/full verification to accept it. Assert nonblank/unique canonical IDs, equal cardinality, and equal canonical-ID sets. Assert original projection `mapping_identities` remains unchanged and is not compared to mapping hashes.
- [ ] Write a self-consistent forged mapping test: swap two canonical IDs across candidate IDs, reconstruct mapping records and dependent request/readiness/manifest hashes so all self-hashes, universes, and orders are valid, then require the full verifier to reject it by exact equality with original compilation mapping.
- [ ] Run: `py -3 -m pytest tests/unit/test_m13_4e_promotion_evidence.py -k "projection_mapping or swapped_pairing" -q`; expected failure demonstrates positional coercion or set-only acceptance.
- [ ] Replace positional canonical-ID equality with exact universe checks; retain mapping candidate ordering and reference mapping-hash equality; compare the entire typed manifest mapping to the original typed compilation mapping in the full verifier.
- [ ] Re-run the focused command.

**Acceptance criterion:** Different representation order accepts, but changed universe, duplicate/blank ID, or any changed candidate-to-canonical pair rejects.

### R3: Enforce SHA-256 Identity Members

**Files:** `src/mechcad_harness/candidates/promotion_models.py`; `tests/unit/test_m13_4e_promotion_evidence.py`.

**Symbols:** `MultiJointPromotionDecisionInputReference._validate_identities`, `_require_hash`.

- [ ] Write parameterized failing tests for each `mapping_identities` and `classification_identities` member: `abc`, `sha256:`, wrong digest length, and non-hex reject; a valid `sha256:` digest accepts.
- [ ] Run: `py -3 -m pytest tests/unit/test_m13_4e_promotion_evidence.py -k "identity_member_hash" -q`; expected failure proves nonblank-only validation.
- [ ] Apply the existing `_require_hash` field validator to both tuple member fields without introducing a new hash grammar; retain duplicate and lexical-classification checks.
- [ ] Re-run the focused command.

**Acceptance criterion:** Tuple members obey the repository SHA-256 validator exactly.

### R4: Use the Strongly Typed Private Route Context

**Files:** `src/mechcad_harness/candidates/promotion.py`; `tests/unit/test_m13_4e_promotion_application.py`.

**Symbols:** `_MultiJointPromotionRouteContext`, `_promote_multi_joint_route`.

- [ ] Write failing route tests asserting the context is instantiated after decision publication and before application, has `decision_artifact: EngineeringArtifact`, does not have `proposal`, and rejects request/readiness/compilation/run/store/decision-artifact disagreement.
- [ ] Run: `py -3 -m pytest tests/unit/test_m13_4e_promotion_application.py -k "route_context" -q`; expected failure proves unused weak context or duplicate proposal input.
- [ ] Change the dataclass to exactly `request`, `readiness`, `compilation`, `run`, `store`, and typed `decision_artifact`; validate its relationships and derive the proposal only from `compilation.proposal`. Make the route construct and use it rather than retaining a decorative class.
- [ ] Re-run the focused command.

**Acceptance criterion:** The context is real, strongly typed, route-bound, and cannot be an arbitrary promotion input bypass.

### R5: Verify Partial Post-Apply N+1 State

**Files:** `src/mechcad_harness/candidates/promotion_artifacts.py`; `tests/unit/test_m13_4e_promotion_application.py`.

**Symbols:** `verify_multi_joint_promotion_application_result`.

- [ ] Write one failing test per partial post-apply status for nonexistent revision, different persisted state hash, wrong project, and a revision other than decision base plus one. Do not require a run, invalidation, or result artifact beyond its status guarantee.
- [ ] Run: `py -3 -m pytest tests/unit/test_m13_4e_promotion_application.py -k "partial_post_apply_verifier" -q`; expected failure demonstrates the current early return.
- [ ] After decision verification, require receipt applied revision/hash, call `state_manager.load_revision(decision.project_id, receipt.applied_revision)`, compare its `state_hash`, and require `receipt.applied_revision == decision.base_revision + 1` for all four statuses.
- [ ] Re-run the focused command.

**Acceptance criterion:** Every receipt that claims N+1 proves that exact persisted N+1, while lifecycle claims remain bounded by the failure table.

### R6: Deepen Independent Substitution Proofs

**Files:** `tests/unit/test_m13_4e_promotion_evidence.py`; `tests/unit/test_m13_4e_promotion_application.py`.

**Symbols:** `_build_multi_joint_decision_input_reference`, `verify_multi_joint_promotion_decision`.

- [ ] Write parameterized substitutions for evaluation request, evaluation, selection, configuration set, placement derivations, physical pair policy, M10 request, M10 result, mapping, classification, and readiness. For every nested frozen model, reconstruct and rehash all necessary parents so the test reaches the intended cross-chain comparison.
- [ ] Run: `py -3 -m pytest tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_application.py -k "rehash_substitution" -q`; expected failure must name the intended binding rather than a stale self-hash.
- [ ] Add no production permissiveness; correct only test builders/fixtures necessary to make every substitution independently self-consistent.
- [ ] Re-run the focused command.

**Acceptance criterion:** Each cross-chain binding has a direct adversarial proof, not an earlier stale-hash failure.

### R7: Replace Fake Failure Proofs With Real N+1 Lifecycle Tests

**Files:** `tests/unit/test_m13_4e_promotion_application.py`; minimal exception translation only in `src/mechcad_harness/candidates/promotion.py` if test evidence exposes a defect.

**Symbols:** `_promote_multi_joint_route`, `RunController.apply_approved_proposal`, `ChangeEngine.apply_proposal`, `StateManager.load_revision`.

- [ ] Write failing post-N+1 tests using real stores, `RunController`, and `ChangeEngine`: inject run-transition persistence failure, invalidation persistence failure, invalidation reload/verification failure after write, result publication failure before durable success, and result fresh-resolution failure after bytes write. Do not monkeypatch the whole application method or fabricate `AppliedChangeResult`/snapshots.
- [ ] In every test, assert `load_revision(project_id, receipt.applied_revision)` succeeds, loaded hash equals receipt hash, and revision equals base plus one; inspect run/invalidation only where guaranteed by the failure table.
- [ ] Run: `py -3 -m pytest tests/unit/test_m13_4e_promotion_application.py -k "real_post_apply or failure_matrix" -q`; expected failure demonstrates fake proof or incorrect status data.
- [ ] Inject only at the narrow durable operation after real mutation; use the real applied result throughout route/result publication.
- [ ] Re-run the focused command.

**Acceptance criterion:** Each post-apply receipt is supported by actual persisted N+1 state, not a namespace or fabricated snapshot.

### R8: Repair Fresh Reload Run Recovery

**Files:** `tests/integration/test_m13_4e_promotion_evidence_acceptance.py`; `tests/unit/test_m13_4e_promotion_application.py`; resolver/verifier code only if tests expose a defect.

**Symbols:** `PromotionManifestService.resolve_multi_joint_decision`, `EngineeringArtifact.run_id`, `RunController.get_run`.

- [ ] Write restart tests that discard retained run variables and recover only by strict decision artifact retrieval, then `decision_artifact.run_id`, then `RunController.get_run(decision_artifact.run_id)`. Reject blank/missing artifact run ID, artifact/store mismatch, missing run, wrong run, and a result artifact from another run with matching N/N+1 identities.
- [ ] Run: `py -3 -m pytest tests/integration/test_m13_4e_promotion_evidence_acceptance.py -k "restart or run_recovery" -q`; expected failure demonstrates glob/latest/only-run discovery.
- [ ] Remove test and implementation reliance on run-manifest globs, latest run, N+1 state inference, or pre-restart fixture run ID. Preserve strict scoped artifact metadata checks.
- [ ] Re-run the focused command.

**Acceptance criterion:** Restart recovery is rooted exclusively in the resolved decision artifact metadata.

### R9: Deepen Result Resolver Tests and Export Audit

**Files:** `tests/unit/test_m13_4e_promotion_result.py`; `src/mechcad_harness/candidates/promotion_artifacts.py`; optionally `src/mechcad_harness/candidates/__init__.py`.

**Symbols:** `resolve_multi_joint_result`, `verify_multi_joint_promotion_application_result`, `promotion_artifacts.__all__`.

- [ ] Write direct artifact-local resolver tamper tests for result namespace, artifact byte hash, canonical bytes, result self-hash, decision artifact ID, decision artifact byte hash, decision self-hash, base revision/state, resulting revision/state, target/mechanism path, and run-ID mismatch. Instrument the test so `StateManager`, `EvidenceStore`, and `RunController` would fail if invoked.
- [ ] Run: `py -3 -m pytest tests/unit/test_m13_4e_promotion_result.py -k "resolver_tamper" -q`; expected failure identifies an unvalidated persisted fact.
- [ ] Implement only artifact-local checks in the resolver. Add `verify_multi_joint_promotion_application_result` to `promotion_artifacts.__all__` if the module exports peer public verification wrappers; mirror its accepted export through package init only if needed by current convention.
- [ ] Re-run the focused command.

**Acceptance criterion:** Local resolver rejects every listed persisted tamper without accessing nonlocal services; public-wrapper export convention is consistent.

### R10: Run Focused, Legacy, M13-3, and Full Regression Gates

**Files:** no production edits unless a failing test proves an M13-4E defect; only authorized M13-4E files may then change.

- [ ] Run focused corrective suite: `py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q`.
- [ ] Run predecessor gates: `py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q`.
- [ ] Run `py -3 -m pytest -q` with a timeout of at least 6000 seconds and no skipped required M13-4E tests.
- [ ] Run `py -3 -m compileall -q src tests`, `git diff --check`, trailing-whitespace scan, final-newline check, and `git diff --name-only`; stop rather than altering protected surfaces.

**Acceptance criterion:** Corrective and predecessor suites pass without regenerating a legacy/M13-3 value or modifying a protected surface.

### R11: Rewrite the Completion Report After Evidence

**Files:** `docs/audit/MECHCAD_M13_4E_COMPLETION_REPORT.md`.

- [ ] Write the report only after R0-R10 evidence exists. Replace the unaccepted marker and remove every claim that compilation normalization is acceptable.
- [ ] Record that the original M13-3 compilation/projection identity was preserved exactly, with final fixture hashes where useful; enumerate actual test commands/results and each repaired audit issue.
- [ ] State the earlier FreeCAD timeout claim is `UNVERIFIABLE` because durable timeout/rerun evidence was not retained and FreeCAD-dependent tests were unavailable/skipped. Do not call it environmental transient. State M13-4E has no FreeCAD runtime acceptance requirement and whether any required M13-4E test skipped.
- [ ] Run: `git diff --check`; expected success before audit.

**Acceptance criterion:** The report contains only durable, reproduced evidence and no premature acceptance claim.

### R12: Independent Final Acceptance Audit

**Files:** audit output only; no implementation change is authorized during this task.

- [ ] Supply R0 baseline provenance, original-versus-evidence compilation/projection values, full tests, changed-file audit, and R11 report to an independent reviewer.
- [ ] Require explicit review of ordering semantics, pairing forgery, hash grammar, partial N+1 verification, real failure injection, metadata-rooted restart, resolver isolation, protected surfaces, and completion-report claims.
- [ ] If any issue remains, return to the specific R-task; do not update schemas, accepted baselines, or audit marker to hide it.

**Acceptance criterion:** Only an independent evidence-backed audit may determine whether the candidate can advance from `M13_4E_IMPLEMENTATION_NEEDS_FIXES`.

## Plan Self-Review

- [x] R1 removes normalization and prohibits any rehashed replacement compilation.
- [x] R2 freezes independent ordering, exact universe agreement, and exact pair agreement; projection mapping identities are documented as canonical component IDs, not mapping hashes.
- [x] R3 uses the repository SHA validator for every identity tuple member.
- [x] R4 makes the private context real and strongly typed.
- [x] R5 verifies persisted N+1 for every post-apply failure without overclaiming lifecycle state.
- [x] R0, R6, and R7 require independent literal goldens, rehashed substitutions, and real ChangeEngine persistence.
- [x] R8 and R9 cover metadata-rooted restart and isolated resolver tampering.
- [x] R10-R12 preserve protected surfaces and defer all acceptance/report claims until evidence exists.
\n