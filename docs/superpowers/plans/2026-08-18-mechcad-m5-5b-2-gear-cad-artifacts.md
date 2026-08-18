# M5.5B-2 Gear CAD Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate immutable, hashed STEP/STL artifacts for validated external spur gear inputs through ToolBroker.

**Architecture:** Add MechCAD-owned artifact models/storage, then a focused CAD adapter that consumes py_gearworks geometry and transient build123d parts. Register single-gear and narrow pair tools with normalized JSON outputs and existing ToolBroker binding/provenance.

**Tech Stack:** Python 3.11+, Pydantic v2, py_gearworks 0.0.18 at exact Git SHA, build123d 0.11.1, NumPy >=2,<2.4, SciPy >=1.10.1, pytest.

## Global Constraints

- Keep core MechCAD importable without gear extras.
- Do not serialize py_gearworks, build123d, or OpenCascade objects.
- Store only STEP/STL artifacts in scoped immutable run directories.
- Keep `DesignState` canonical and M4 `state.json` authoritative.
- Do not implement general CAD, assemblies, strength, optimization, or M5.5C/D.

### Task 1: Artifact Models And Storage

**Files:**
- Create: `src/mechcad_harness/artifacts/models.py`
- Create: `src/mechcad_harness/artifacts/storage.py`
- Create: `src/mechcad_harness/artifacts/__init__.py`
- Test: `tests/unit/test_artifacts.py`

- [ ] Define `ArtifactType`, `EngineeringArtifact`, and `ArtifactStore` with safe relative paths, atomic writes, duplicate rejection, hashes, and immutable metadata.
- [ ] Add tests for exact hash, size, path safety, duplicate rejection, and JSON-only metadata.

### Task 2: Single Gear CAD Adapter

**Files:**
- Create: `src/mechcad_harness/backends/gearworks_cad.py`
- Create: `src/mechcad_harness/cad.py`
- Test: `tests/unit/test_gear_cad.py`

- [ ] Define CAD input/result models with explicit requested formats and optional bore.
- [ ] Create a py_gearworks part, apply a build123d cylindrical bore, validate volume/bounds/thickness, export STEP/STL, and return normalized data plus artifact metadata.
- [ ] Add golden case, bore, re-import, and repeated-export tests.

### Task 3: ToolBroker Integration

**Files:**
- Modify: `src/mechcad_harness/tools/gearworks.py`
- Modify: `src/mechcad_harness/tools/__init__.py`
- Test: `tests/unit/test_gear_cad.py`

- [ ] Register `mechcad-build-spur-gear-cad` with exact version and optional Evidence node.
- [ ] Ensure ToolBroker persists ToolCall before handler execution and returns only JSON-safe result/artifact metadata with backend provenance.
- [ ] Test permission, stale binding, failed generation, and unchanged canonical bytes.

### Task 4: Narrow Pair CAD

**Files:**
- Modify: `src/mechcad_harness/backends/gearworks_cad.py`
- Modify: `src/mechcad_harness/tools/gearworks.py`
- Test: `tests/unit/test_gear_cad.py`

- [ ] Add `mechcad-build-spur-gear-pair-cad` using the validated pair placement and two artifact references plus nominal transform data.
- [ ] Test center distance, parallel axes, and no assembly persistence.

### Task 5: Documentation And Verification

**Files:**
- Modify: `README.md`
- Test: existing suites and focused gear environment

- [ ] Document derived artifact boundaries, storage layout, provenance, and determinism findings.
- [ ] Run core pytest, focused gear pytest, compileall, diff check, and prohibited-scope scans.
