# Structural Authority And Artifact Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make durable M11-4 execution manifests authoritative, require trusted composed-FreeCAD source provenance for successful M11-3 execution, and centralize strict artifact verification.

**Architecture:** `ProductionApplication.evaluate_structural_analysis` will reload the deterministic JSON execution-manifest artifact through `ArtifactStore`, compare the reloaded model to the supplied object and request binding, and pass only the durable model to interpretation. `ArtifactStore` will validate lookup identity, safe contained paths, project/run/type/hash/size, and bytes; source and structural result paths will use that verified API. Structural execution will reject source STEP artifacts whose provenance is absent or differs from the composed geometry runtime before publishing any success manifest.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, FreeCAD/Gmsh/CalculiX runtime gates.

## Global Constraints

- Do not commit or run destructive Git commands.
- Preserve existing source artifact semantics and failed-manifest/no-result behavior.
- Keep source-bound single-body linear-static M11-3/M11-4 scope unchanged.
- Do not edit generated project trees or `err.txt`.

---

### Task 1: Add Failing Authority And Artifact Tests

**Files:**
- Modify: `tests/unit/test_artifacts.py`
- Modify: `tests/unit/test_structural_service.py`
- Modify: `tests/unit/test_production_application.py` or the focused structural result tests where the production fixture belongs

**Interfaces:**
- Exercise `ArtifactStore.existing`, `ArtifactStore.read_verified`, and project-scoped verified lookup.
- Exercise `ProductionApplication.evaluate_structural_analysis` with a forged in-memory manifest.
- Exercise M11-3 execution with missing/foreign source STEP provenance.

- [x] **Step 1: Add artifact identity, traversal, and expected type/hash tests.**
- [x] **Step 2: Add a forged in-memory manifest evaluation test and assert no interpreter result is produced.**
- [x] **Step 3: Add missing/foreign source provenance execution regressions and assert no successful manifest is returned while the source artifact remains unchanged.**
- [x] **Step 4: Run the new tests and confirm they fail for the current implementation.**

### Task 2: Harden ArtifactStore And Structural Consumers

**Files:**
- Modify: `src/mechcad_harness/artifacts/storage.py`
- Modify: `src/mechcad_harness/structural/service.py`
- Modify: `src/mechcad_harness/structural/results.py`
- Modify: `src/mechcad_harness/application.py`

**Interfaces:**
- Add strict optional expectations to `read_verified` and `read_verified_in_project` while preserving existing return types.
- Route structural source, mesh, deck, FRD, DAT, and LOG reads through the verified API.

- [x] **Step 1: Validate metadata artifact ID, safe relative path, workspace containment, type/extension, project/run, size, and byte hash in one store path.**
- [x] **Step 2: Add expected type/hash/project/run checks to verified reads and use them for source and result artifacts.**
- [x] **Step 3: Remove structural result direct metadata/path reads.**
- [x] **Step 4: Verify source STEP provenance equals the composed geometry runtime provenance before structural success.**
- [x] **Step 5: Reload and validate the durable JSON execution manifest in production evaluation, compare it to the supplied manifest/request binding, and pass only the durable model to parsing.**
- [x] **Step 6: Run focused tests and verify failed manifests remain persisted with no interpreted result.**

### Task 3: Reports And Verification

**Files:**
- Modify: `docs/audit/MECHCAD_M11_4_COMPLETION_REPORT.md`
- Modify: `.superpowers/sdd/progress.md` only for the current remediation record

- [x] **Step 1: Record the durable-manifest, source-provenance, and ArtifactStore trust-boundary closure without changing capability claims.**
- [x] **Step 2: Run focused/live structural tests, the full suite, `compileall`, `git diff --check`, and scoped/untracked diff checks.**
- [x] **Step 3: Record actual verification counts and remaining runtime concerns.**
