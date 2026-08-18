# M5 Tool Broker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact-version deterministic tool dispatch with immutable ToolCall/ToolResult audit records, explicit task permissions, four pure mechanical tools, and explicit M3 evidence production.

**Architecture:** A focused tools package composes M4 `RunStore`/`RunController`
boundaries and M3 `EvidenceStore`. The broker validates task/run/canonical
provenance and permissions before persisting a call and invoking a pure typed
handler. Tool calls/results contain immutable execution provenance only.

**Tech Stack:** Python 3.11+, Pydantic v2, deterministic Python arithmetic,
filesystem JSON persistence, pytest.

## Global Constraints

- `ToolContext` contains only `project_id`, `run_id`, `task_id`, `bound_revision`, and `bound_state_hash`.
- Tools receive explicit typed inputs only and never receive or inspect `DesignState`.
- `ToolCall` is persisted before handler execution; `ToolResult` is separate and immutable.
- Exact tool name and version are mandatory for lookup and provenance.
- Empty or missing `allowed_tools` fails closed.
- M4 `state.json` remains the sole mutable run-state authority; do not modify `RunManifest` authority.
- Evidence is created only on explicit request, only for declared nodes, and only from successful results.
- Do not add OpenCode, agents, LLMs, MCP, CAD, FEA, SQL, dynamic plugins, parallelism, or autonomous tool selection.
- Do not commit unless explicitly requested.

---

### Task 1: Add Tool Models, Errors, And Task Permission Field

**Files:**
- Create: `src/mechcad_harness/tools/models.py`
- Create: `src/mechcad_harness/tools/errors.py`
- Modify: `src/mechcad_harness/runs/models.py`
- Modify: `src/mechcad_harness/runs/controller.py`
- Test: `tests/unit/test_tools.py`

- [ ] **Step 1: Write failing tests** for provenance-only `ToolContext`, exact task permission defaults, separate `ToolCall`/`ToolResult`, statuses, and structured errors.
- [ ] **Step 2: Run `py -m pytest tests/unit/test_tools.py -q` and verify missing-symbol failures.**
- [ ] **Step 3: Add typed models with strict extra-field rejection, immutable binding fields, and `allowed_tools=()`.**
- [ ] **Step 4: Run the focused model tests and verify they pass.**

### Task 2: Implement Exact-Version Registry And Pure Built-In Tools

**Files:**
- Create: `src/mechcad_harness/tools/registry.py`
- Create: `src/mechcad_harness/tools/builtins.py`
- Modify: `src/mechcad_harness/tools/__init__.py`
- Test: `tests/unit/test_tools.py`

- [ ] **Step 1: Add failing tests** for exact lookup, duplicate rejection, unknown tools, all four calculation contracts, explicit validation, and deterministic repeated outputs.
- [ ] **Step 2: Run focused tests and verify expected failures.**
- [ ] **Step 3: Implement immutable registrations with typed input/output models and declared evidence nodes.**
- [ ] **Step 4: Implement torque, spur gear geometry, envelope, and dimension compensation as pure handlers.**
- [ ] **Step 5: Run focused tests and verify they pass.**

### Task 3: Implement Immutable Tool Call/Result Persistence

**Files:**
- Create: `src/mechcad_harness/tools/persistence.py`
- Modify: `src/mechcad_harness/runs/persistence.py`
- Test: `tests/unit/test_tools.py`

- [ ] **Step 1: Add failing tests** for separate directories, call-before-result ordering, immutable duplicate rejection, failed-result persistence, and absence of mutable run fields.
- [ ] **Step 2: Run focused persistence tests and verify failures.**
- [ ] **Step 3: Implement exclusive writes using the existing M4 atomic/exclusive persistence patterns.**
- [ ] **Step 4: Run focused persistence tests and verify they pass.**

### Task 4: Add Backward-Compatible Evidence Provenance

**Files:**
- Modify: `src/mechcad_harness/models/evidence.py`
- Modify: `src/mechcad_harness/dependency/storage.py`
- Test: `tests/unit/test_tools.py`, `tests/unit/test_dependency.py`

- [ ] **Step 1: Add failing tests** for optional producer/input/output provenance and existing evidence fixtures.
- [ ] **Step 2: Run focused evidence tests and verify failures.**
- [ ] **Step 3: Add optional fields and preserve existing M3 serialization/freshness behavior.**
- [ ] **Step 4: Run both evidence test files and verify they pass.**

### Task 5: Implement ToolBroker Validation, Execution, And Evidence

**Files:**
- Create: `src/mechcad_harness/tools/broker.py`
- Modify: `src/mechcad_harness/tools/__init__.py`
- Test: `tests/unit/test_tools.py`

- [ ] **Step 1: Add failing tests** for permissions, exact-version lookup, task/run ownership, canonical binding, stale old tasks, input/output hashes, failed calls, explicit declared evidence, undeclared evidence rejection, and canonical snapshot immutability.
- [ ] **Step 2: Run focused broker tests and verify failures.**
- [ ] **Step 3: Implement preflight validation and persist `ToolCall` before invoking handlers.**
- [ ] **Step 4: Implement successful and failed `ToolResult` persistence with structured errors.**
- [ ] **Step 5: Implement explicit EvidenceStore production using tool declarations and exact provenance.**
- [ ] **Step 6: Run focused broker tests and verify they pass.**

### Task 6: Document And Verify M5

**Files:**
- Modify: `README.md`
- Test: `tests/unit/test_tools.py`

- [ ] **Step 1: Add deterministic end-to-end broker execution through an M4 task binding.**
- [ ] **Step 2: Document ToolContext, ToolCall/ToolResult layout, permissions, pure tools, hashes, and evidence rules.**
- [ ] **Step 3: Run `py -m pytest -q`.**
- [ ] **Step 4: Run `py -m compileall -q src tests`.**
- [ ] **Step 5: Run `git diff --check`.**
- [ ] **Step 6: Search M5 changes for prohibited integrations and inspect the final diff.**
