# M4 Run Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic filesystem-backed run control, task scheduling, abstract execution, revision advancement, freshness gating, and convergence checks.

**Architecture:** A focused `mechcad_harness.runs` package composes the M1
`StateManager`, M2 `ChangeEngine`, and M3 `EvidenceStore`. Immutable run/task
provenance and results are stored separately from atomically mutable run/task
state. A controller coordinates a validated single-threaded task DAG and exact
revision/hash checks.

**Tech Stack:** Python 3.11+, Pydantic v2, filesystem JSON persistence, pytest,
UTC-aware datetimes.

## Global Constraints

- Do not add OpenCode integration, real agents, LLMs, CAD, FreeCAD, FEA, MuJoCo, MCP, SQL/database storage, calculators, optimization, parallel execution, distributed workers, or external services.
- Preserve `DesignState` as canonical state and reuse M1-M3 boundaries.
- Task definitions and results are immutable; run/task lifecycle state is mutable and atomically written.
- Never rebind an existing task to another revision or overwrite a result.
- M3 freshness is fail-closed; only `CURRENT` evidence satisfies completion.
- Iteration equals accepted design-changing canonical revision advancements.
- M2 revision creation remains valid if M3 invalidation persistence fails; the run must follow canonical reality and become `BLOCKED`.
- Do not commit unless explicitly requested.

---

### Task 1: Add M4 Models And Errors

**Files:**
- Create: `src/mechcad_harness/runs/models.py`
- Create: `src/mechcad_harness/runs/errors.py`
- Create: `src/mechcad_harness/runs/__init__.py`
- Test: `tests/unit/test_runs.py`

**Interfaces:**
- Consume existing `DesignState`, `Evidence`, `ChangeProposal`, and M3 freshness types.
- Produce enums and Pydantic models for `Run`, `RunPlan`, immutable `TaskDefinition`, mutable `TaskState`, `TaskExecutionResult`, `TaskContext`, and convergence outcomes.

- [ ] **Step 1: Write failing model tests** for valid run/task bindings, lifecycle enums, non-positive revision rejection, and separate definition/state payloads.
- [ ] **Step 2: Run `py -m pytest tests/unit/test_runs.py -q` and verify failures are missing-symbol failures.**
- [ ] **Step 3: Implement minimal typed models with UTC-aware timestamps and non-empty required strings.**
- [ ] **Step 4: Run the focused tests and verify they pass.**

### Task 2: Implement Atomic Run Persistence And Events

**Files:**
- Create: `src/mechcad_harness/runs/persistence.py`
- Modify: `src/mechcad_harness/runs/__init__.py`
- Test: `tests/unit/test_runs.py`

**Interfaces:**
- `RunStore.create_manifest`, `load_manifest`, `write_state`, `load_state`, task definition/state/result methods, and `append_event`.
- Exclusive writes reject existing immutable records; mutable state uses fsync and atomic replacement.

- [ ] **Step 1: Add failing tests** for layout, manifest immutability, atomic mutable state, immutable task definition/result, sequential events, and corrupted-file rejection.
- [ ] **Step 2: Run focused tests and verify expected persistence failures.**
- [ ] **Step 3: Implement `RunStore` using the existing M1/M3 JSON write patterns.**
- [ ] **Step 4: Run focused persistence tests and verify they pass.**

### Task 3: Implement Task DAG Scheduler And Executor Boundary

**Files:**
- Create: `src/mechcad_harness/runs/scheduler.py`
- Create: `src/mechcad_harness/runs/executor.py`
- Modify: `src/mechcad_harness/runs/errors.py`
- Test: `tests/unit/test_runs.py`

**Interfaces:**
- `TaskScheduler.validate`, `ordered`, and `ready_tasks`.
- `TaskExecutor` protocol and result-binding validation helper.

- [ ] **Step 1: Add failing tests** for no-dependency readiness, prerequisite gating, failed-prerequisite blocking, stable ordering, unknown dependencies, cycles, and result binding mismatches.
- [ ] **Step 2: Run focused scheduler tests and verify expected failures.**
- [ ] **Step 3: Implement deterministic Kahn topological ordering and explicit status transitions.**
- [ ] **Step 4: Implement protocol-level result validation and stale-result errors.**
- [ ] **Step 5: Run focused tests and verify they pass.**

### Task 4: Implement Convergence Skeleton

**Files:**
- Create: `src/mechcad_harness/runs/convergence.py`
- Modify: `src/mechcad_harness/runs/models.py`
- Test: `tests/unit/test_runs.py`

**Interfaces:**
- `ConvergenceTracker` with exact active hash history and `record_revision`.

- [ ] **Step 1: Add failing tests** for iteration semantics, no progress, cycles, and max iteration blocking.
- [ ] **Step 2: Run focused convergence tests and verify failures.**
- [ ] **Step 3: Implement ordered checks: no progress, cycle, then iteration limit.**
- [ ] **Step 4: Run focused convergence tests and verify they pass.**

### Task 5: Implement RunController Coordination

**Files:**
- Create: `src/mechcad_harness/runs/controller.py`
- Modify: `src/mechcad_harness/runs/__init__.py`
- Test: `tests/unit/test_runs.py`

**Interfaces:**
- `create_run`, `create_plan`, `add_task`, `execute_ready_tasks`, `apply_approved_proposal`, `evaluate_completion`, `get_run`, and `resume_run`.

- [ ] **Step 1: Add failing controller tests** for exact creation binding, fake execution, completion freshness gate, resume integrity, approved M2-to-M3 advancement, M3 failure blocking, stale pending tasks, unaffected tasks, and historical evidence reuse.
- [ ] **Step 2: Run focused controller tests and verify failures.**
- [ ] **Step 3: Implement creation, persistence, event emission, and resume verification.**
- [ ] **Step 4: Implement task execution and immutable result/evidence persistence.**
- [ ] **Step 5: Implement explicit proposal advancement with canonical-reality handling and convergence.**
- [ ] **Step 6: Implement completion gating and affected-task reporting.**
- [ ] **Step 7: Run focused controller tests and verify they pass.**

### Task 6: Document M4 And Run Full Verification

**Files:**
- Modify: `README.md`
- Test: `tests/unit/test_runs.py`

- [ ] **Step 1: Add the deterministic fake-executor end-to-end scenario.**
- [ ] **Step 2: Update README with the M4 flow, state machines, persistence layout, and explicit scope exclusions.**
- [ ] **Step 3: Run `py -m pytest -q`.**
- [ ] **Step 4: Run `py -m compileall -q src tests`.**
- [ ] **Step 5: Run `git diff --check`.**
- [ ] **Step 6: Search M4 changes for prohibited M5+ integrations and inspect the final diff.**
