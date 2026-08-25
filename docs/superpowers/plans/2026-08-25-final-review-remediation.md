# M11 Final Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the final M11 review findings without weakening the structural result trust boundary or overstating the bounded capability.

**Architecture:** Keep multi-case execution authoritative in ordered case manifests, with the optional legacy top-level fields used only as a single-case mirror. Pin interpretation to the composed FreeCAD/Gmsh/CalculiX identities and verify source artifact provenance before parsing. Keep analytical validation as an explicit separate `ProductionApplication.evaluate_structural_analytical_validation` service API, with predeclared policy input and tests documenting that boundary.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, FreeCAD 1.1.3, Gmsh 4.15.0, CalculiX 2.22, Markdown.

## Global Constraints

- Do not commit or run destructive Git commands.
- Preserve source-bound single-body linear-static scope and all M11-5 limitations.
- Reject empty required strings, non-positive revisions, forged artifact metadata, and foreign runtime provenance.
- Keep `DesignState` canonical and analytical policies predeclared before execution.

---

### Task 1: Add Failing Trust-Boundary And Multi-Case Tests

**Files:**
- Modify: `tests/unit/test_structural_results.py`
- Modify: `tests/integration/test_m11_4_live_structural.py`
- Modify: `tests/unit/test_production_application.py`

**Interfaces:**
- The tests will exercise `StructuralResultInterpreter.interpret`, the production structural execute/evaluate path, and the explicit analytical-validation service API.

- [x] **Step 1: Add a two-case production interpretation test** with one shared mesh and ordered `LC-1`, `LC-2` result assertions.
- [x] **Step 2: Add an adversarial empty-LOG test** that rewrites the LOG bytes and matching metadata/manifest hashes while leaving forged success flags true; assert interpretation rejects before parsers run.
- [x] **Step 3: Add a foreign self-consistent Gmsh provenance test** and a source geometry provenance mismatch test.
- [x] **Step 4: Add a production API test** showing analytical validation requires an explicit predeclared policy and remains separate from ordinary structural evaluation.
- [x] **Step 5: Run each new test and confirm the expected pre-fix failures.**

### Task 2: Fix Interpretation Provenance And Case Binding

**Files:**
- Modify: `src/mechcad_harness/structural/results.py`
- Modify: `src/mechcad_harness/structural/models.py` only if a small validation correction is required.
- Modify: `tests/unit/test_structural_results.py` fixtures to use admitted runtime provenance.

**Interfaces:**
- `StructuralResultInterpreter._verify_manifest_binding` validates ordered per-case solver manifests and only validates top-level solver fields as a single-case mirror.
- `_read_artifact` rejects zero-byte LOG artifacts after byte verification.
- Interpretation admits only `GMSH_PROVIDER_IDENTITY` / Gmsh `4.15.0`, trusted FreeCAD source geometry provenance, and matching manifest/artifact provenance.

- [x] **Step 1: Remove the unconditional top-level solver-manifest requirement for multi-case manifests.**
- [x] **Step 2: Keep single-case top-level mirror validation and validate every case solver manifest independently.**
- [x] **Step 3: Reject empty LOG bytes at the artifact trust boundary.**
- [x] **Step 4: Pin Gmsh identity/version and verify source geometry backend provenance.**
- [x] **Step 5: Run focused unit tests and confirm green.**

### Task 3: Document The Analytical Validation Boundary

**Files:**
- Modify: `src/mechcad_harness/application.py`
- Modify: `tests/unit/test_production_application.py`
- Modify: `docs/audit/MECHCAD_M11_4_COMPLETION_REPORT.md`

**Interfaces:**
- Add `ProductionApplication.evaluate_structural_analytical_validation(...)` as the explicit trusted service API for a predeclared policy and trusted observations, without implicitly composing policy selection into ordinary result evaluation.

- [x] **Step 1: Add the explicit API contract test.**
- [x] **Step 2: Compose the API with `StructuralAnalyticalValidator` and trusted manifest/mesh loading inputs.**
- [x] **Step 3: Update the capstone wording to name the actual production path and preserve the separate-policy limitation.**

### Task 4: Reconcile Normative Architecture And Acceptance Counts

**Files:**
- Modify: `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`
- Modify: `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`
- Modify: `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`
- Modify: `README.md` only where its current structural status is stale.
- Modify: `AGENTS.md` only where current accepted baseline wording is stale.
- Modify: `docs/audit/MECHCAD_M11_4_COMPLETION_REPORT.md`

**Interfaces:**
- Current architecture will identify bounded M11-3/M11-4 structural/FEA capability as current, while explicitly excluding broad structural approval, mesh convergence, assemblies, nonlinear/fatigue/dynamics/thermal/tolerance/optimization/manufacturing claims.
- The M11-4 report will use the final actual count `1189 passed, 34 skipped, 0 failed, 0 errors` consistently; historical M11-3 counts remain unchanged unless required for current-status cross-reference.

- [x] **Step 1: Update the capability matrix rows and add M11 traceability.**
- [x] **Step 2: Reconcile overview/system-contract future-boundary language.**
- [x] **Step 3: Correct all stale internal M11-4 counts without editing unrelated historical M11-3 evidence.**

### Task 5: Full Verification And Diff Audit

**Files:**
- No new source files.

- [x] **Step 1: Run focused structural and production tests.**
- [x] **Step 2: Run live M11-3/M11-4 tests when runtimes are available.**
- [x] **Step 3: Run `py -3 -m pytest tests/`.**
- [x] **Step 4: Run `py -3 -m compileall src tests -q`.**
- [x] **Step 5: Run `git diff --check` on changed files and inspect status/diff for unrelated edits.**
