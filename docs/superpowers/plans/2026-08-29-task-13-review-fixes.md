# Task 13 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all Task 13 review findings without adding candidate authority, mutation, or M11 behavior.

**Architecture:** Keep `execute(reconstruction, cad)` as the only canonical execution input boundary. Tighten the frozen canonical models, derive selected-joint motion from canonical topology and connection semantics, and prove the boundary with focused tests. Preserve the existing M10 entrypoints and their result status semantics.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, SHA-256 canonical identities, existing M10 CAD/kinematic services.

## Global Constraints

- Do not commit, tag, or push.
- Keep execution independent of candidate M10 objects and `PrePromotionM10ScopeProjection`.
- Keep `DesignState` as the sole canonical authority.
- Do not add M11 imports, execution, stores, locks, revisions, runs, or manifests.
- Revalidate and defensively copy canonical reconstruction and CAD before use.

### Task 1: Typed Identity And Outcome Invariants

**Files:**
- Modify: `src/mechcad_harness/candidates/canonical_m10.py:59-470`
- Test: `tests/unit/test_m12_canonical_m10.py`

**Interfaces:**
- Required source/result identity fields use a validator that rejects `pending`.
- Computed model identity fields retain `pending` only while their validators calculate the digest.
- `CanonicalM10VerificationOutcome` validates complete nested binding and status coverage.

- [x] **Step 1: Add failing tests for pending and forged mapping identities.**
- [x] **Step 2: Add failing tests for mismatched mechanism IDs, incomplete proof/home coverage, and inconsistent aggregate status.**
- [x] **Step 3: Implement separate required/computed hash validators and outcome invariants.**
- [x] **Step 4: Run the focused invariant tests and confirm they pass.**

### Task 2: Selected-Joint Topology And External-Spur Semantics

**Files:**
- Modify: `src/mechcad_harness/candidates/canonical_m10.py:718-952`
- Test: `tests/unit/test_m12_canonical_m10.py`

**Interfaces:**
- Dispositions are derived from the selected binding child and reachable canonical connection semantics.
- Gear-mesh `from_instance_id` transmission drivers are `INTERNAL_MOTION_UNMODELED`.
- Gear identities and the `GEAR_MESH` connection remain distinct; no ratio, coupling, phase, or backlash model is created.

- [x] **Step 1: Add failing direct-topology and external-spur tests, including an unrelated rotating component.**
- [x] **Step 2: Implement the minimal topology traversal and explicit gear-driver classification.**
- [x] **Step 3: Assert exact pair classifications and moving/stationary partitions.**
- [x] **Step 4: Run the focused topology tests and confirm they pass.**

### Task 3: Candidate-Independent Reexecution And Exact M10 Coverage

**Files:**
- Modify: `tests/unit/test_m12_canonical_m10.py`
- Modify: `.superpowers/sdd/task-13-report.md`

**Interfaces:**
- Candidate/canonical request identity testing uses genuinely equal normalized scope semantics.
- Reexecution uses only canonical reconstruction and CAD after candidate/pre-promotion references are discarded.
- The equivalence service is forbidden during reexecution.
- Both continuous proof and home exact-check entrypoints are exercised with exact typed request/result bindings.

- [x] **Step 1: Replace the weak request-hash test with a real equivalent-scope projection comparison.**
- [x] **Step 2: Add home-check fake application coverage for clear and collision outcomes.**
- [x] **Step 3: Add a reexecution test that deletes candidate/pre-promotion references and makes equivalence calls fail.**
- [x] **Step 4: Run focused tests, then the explicitly relevant regression tests.**
- [x] **Step 5: Append exact commands, results, changed files, and remaining concerns to the Task 13 report.**

### Task 4: Final Read-Only Verification

**Files:**
- Inspect: `src/mechcad_harness/candidates/canonical_m10.py`
- Inspect: `tests/unit/test_m12_canonical_m10.py`
- Inspect: `.superpowers/sdd/task-13-report.md`

- [x] **Step 1: Run compile verification.**
- [x] **Step 2: Run focused Task 13 and M10-1 tests.**
- [x] **Step 3: Run relevant unit/regression tests without changing unrelated worktree files.**
- [x] **Step 4: Confirm no commit was created and report the exact worktree status.**
