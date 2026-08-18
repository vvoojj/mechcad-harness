# M5.5A Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the trusted external-backend foundation without adding any engineering library dependency or production backend adapter.

**Architecture:** A focused `backends` package owns typed backend identity,
structured provenance, health, deterministic registry, and safe package metadata
inspection. It composes with existing M5 persistence models only through optional
scalar Pydantic provenance.

**Tech Stack:** Python 3.11+, Pydantic v2, `importlib.metadata`, pytest.

## Global Constraints

- Do not add py_gearworks, build123d, bd_materials, sectionproperties, NumPy, or SciPy dependencies.
- Do not add production adapters or generic backend execution.
- `BackendIdentity` is declared registration metadata; `BackendHealth` is detected runtime state and never mutates identity.
- Package inspection must use a trusted explicit distribution mapping and must not import target packages.
- Backend-specific objects must not cross ToolResult, Evidence, Run, or DesignState persistence boundaries.
- Preserve M0-M5 behavior and optional backward compatibility.
- Do not commit unless explicitly requested.

---

### Task 1: Add Backend Models And Errors

**Files:**
- Create: `src/mechcad_harness/backends/models.py`
- Create: `src/mechcad_harness/backends/errors.py`
- Create: `src/mechcad_harness/backends/__init__.py`
- Test: `tests/unit/test_backends.py`

- [ ] **Step 1: Write failing tests** for identity validation, structured provenance, health statuses, optional fields, and rejection of non-scalar backend objects.
- [ ] **Step 2: Run `py -m pytest tests/unit/test_backends.py -q` and verify missing-symbol failures.**
- [ ] **Step 3: Implement strict Pydantic models with non-empty names, versions, and capabilities.**
- [ ] **Step 4: Run focused model tests and verify they pass.**

### Task 2: Implement Explicit Deterministic Backend Registry

**Files:**
- Create: `src/mechcad_harness/backends/registry.py`
- Create: `src/mechcad_harness/backends/adapters/__init__.py`
- Modify: `src/mechcad_harness/backends/__init__.py`
- Test: `tests/unit/test_backends.py`

- [ ] **Step 1: Add failing tests** for deterministic ordering, duplicate registration, unknown lookup, capability lookup, and explicit health adapter behavior.
- [ ] **Step 2: Run focused registry tests and verify failures.**
- [ ] **Step 3: Implement a trusted in-process registry with no dynamic import or generic execute method.**
- [ ] **Step 4: Run focused registry tests and verify they pass.**

### Task 3: Implement Trusted Compatibility Inspection

**Files:**
- Create: `src/mechcad_harness/backends/compatibility.py`
- Create: `src/mechcad_harness/backends/provenance.py`
- Modify: `src/mechcad_harness/backends/__init__.py`
- Test: `tests/unit/test_backends.py`

- [ ] **Step 1: Add failing tests** for installed/missing distributions, unknown logical names, non-importing inspection, and identity/health separation.
- [ ] **Step 2: Run focused compatibility tests and verify failures.**
- [ ] **Step 3: Implement fixed logical-name to distribution-name mapping using `importlib.metadata.version`.**
- [ ] **Step 4: Run focused compatibility tests and verify they pass.**

### Task 4: Integrate Optional Structured Provenance

**Files:**
- Modify: `src/mechcad_harness/tools/models.py`
- Modify: `src/mechcad_harness/models/evidence.py`
- Test: `tests/unit/test_backends.py`, `tests/unit/test_tools.py`, `tests/unit/test_dependency.py`

- [ ] **Step 1: Add failing tests** proving M0-M5 records without provenance remain valid and structured provenance serializes without third-party objects.
- [ ] **Step 2: Run focused compatibility tests and verify failures.**
- [ ] **Step 3: Add only optional `backend_provenance` fields to ToolResult and Evidence.**
- [ ] **Step 4: Run all focused tests and verify they pass.**

### Task 5: Document And Verify M5.5A

**Files:**
- Modify: `README.md`
- Test: `tests/unit/test_backends.py`

- [ ] **Step 1: Add tests** proving registry/health operations do not change canonical revision bytes.
- [ ] **Step 2: Document the M5.5A boundary, planned M5.5B-D phases, dependency policy, and external-object persistence rule.**
- [ ] **Step 3: Run `py -m pytest -q`.**
- [ ] **Step 4: Run `py -m compileall -q src tests`.**
- [ ] **Step 5: Run `git diff --check`.**
- [ ] **Step 6: Search for accidental M5.5B-D functionality and inspect the final diff.**
