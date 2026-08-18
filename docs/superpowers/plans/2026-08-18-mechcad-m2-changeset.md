# MechCAD M2 ChangeSet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic proposal validation, ownership enforcement, and atomic ChangeSet application on top of M1 revisions.

**Architecture:** Extend the existing proposal records with explicit base binding and JSON-Pointer-like operations. Implement a small `changes` package that validates and applies operations to a serialized in-memory state, then delegates the only persistence action to `StateManager.create_revision`.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, standard-library JSON/YAML-compatible configuration parsing only.

## Global Constraints

- Existing revision snapshots remain immutable.
- All state changes are explicit `ChangeOperation` records.
- Stale proposals fail closed; no automatic rebase.
- Complete ChangeSets are validated before revision creation.
- Ownership defaults to fail closed for ungoverned paths.
- No agents, OpenCode, dependency execution, scheduling, CAD, FEA, SQL/database storage, EvidenceStore, or later milestones.
- Do not commit unless explicitly requested.

---

### Task 1: Models, operation representation, and errors

**Files:**
- Modify: `src/mechcad_harness/models/proposal.py`
- Modify: `src/mechcad_harness/models/__init__.py`
- Create: `src/mechcad_harness/changes/errors.py`
- Create: `src/mechcad_harness/changes/operations.py`
- Create: `src/mechcad_harness/changes/__init__.py`
- Test: `tests/unit/test_changes.py`

**Interfaces:**
- `OperationType`: `ADD`, `REPLACE`, `REMOVE`.
- `ChangeOperation`: `operation`, `path`, `value`, `expected`.
- `ChangeProposal`: `base_revision`, `base_state_hash`, `actor`, `operations`.
- `ChangeSet`: `changeset_id`, `proposal_id`, `base_revision`, `base_state_hash`, `actor`, `operations`, `status`, `created_at`.
- Errors: `ChangeError`, `InvalidChangePathError`, `ChangeConflictError`, `StaleProposalError`, `OwnershipViolationError`, `ChangeSetValidationError`.

- [ ] Write tests for model construction and required proposal binding.
- [ ] Run `py -m pytest tests/unit/test_changes.py -q` and observe the expected import/model failures.
- [ ] Implement minimal typed models and errors.
- [ ] Run the focused tests and verify they pass.

### Task 2: Path operations and ownership

**Files:**
- Create: `src/mechcad_harness/changes/engine.py`
- Create: `src/mechcad_harness/changes/ownership.py`
- Modify: `config/ownership.yaml`
- Extend: `tests/unit/test_changes.py`

**Interfaces:**
- `apply_operation(payload: dict, operation: ChangeOperation) -> None` mutates only an in-memory payload.
- `OwnershipPolicy.from_file(path)`, `owner_for(path)`, and `check(path, actor)`.
- Paths reject empty segments, `~` escaping, unsupported array traversal, and malformed roots.

- [ ] Add failing tests for add/replace/remove, invalid/missing paths, wildcard ownership, and fail-closed unowned paths.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement explicit path traversal with no `eval`, `exec`, or dynamic reflection.
- [ ] Add minimal ownership rules for requirements, materials, component transmission, and placement.
- [ ] Run focused tests and verify they pass.

### Task 3: Atomic ChangeSet engine

**Files:**
- Modify: `src/mechcad_harness/changes/engine.py`
- Modify: `src/mechcad_harness/changes/__init__.py`
- Extend: `tests/unit/test_changes.py`
- Modify: `README.md`

**Interfaces:**
- `ChangeEngine(state_manager, ownership_policy).apply_proposal(project_id, proposal) -> RevisionSnapshot`.
- Processing loads current state, verifies base revision/hash, validates all operations and ownership, applies to a copy, validates `DesignState`, then calls `StateManager.create_revision` once.

- [ ] Add failing tests for successful revisions, stale proposals, multi-operation atomicity, Pydantic revalidation, and pointer/revision-directory preservation on failure.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement preflight and atomic application.
- [ ] Document M2 flow and exclusions.
- [ ] Run all tests and verify they pass.

### Task 4: Final verification

**Files:**
- Verify all changed files.

- [ ] Run `py -m pytest -q`.
- [ ] Run `py -m compileall -q src tests`.
- [ ] Run `git diff --check`.
- [ ] Inspect the diff and tree for accidental M3+ functionality.
- [ ] Report files, exact test results, ownership rules, immutability, and pointer guarantees.
