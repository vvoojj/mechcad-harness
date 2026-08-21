# M8C-3 Plan: Production Assembly → Exact Analysis → Generic Kinematic Vertical Slice

**Date:** 2026-08-22
**Status:** PLAN → EXECUTED
**Disposition:** M8C_3_COMPLETE_RUNTIME_GATED

## Objective

Close the production connectivity path:

```
ProductionApplication
  -> assembly-bound analysis request
  -> CadKinematicSweepService
  -> TransientAssemblyAnalysisService
  -> measurement provider (exact geometry boundary)
  -> deterministic discrete sweep result
```

## Audit Conclusion (pre-implementation)

The existing analysis foundation already composes correctly:
- `CadKinematicSweepService.execute` calls `TransientAssemblyAnalysisService.analyze`,
  which calls an injected `exact_measure(request, transformed_assembly)` callback.
- `CadAssemblyProgram` already carries generated + imported component identity.

Missing edge: **`ProductionApplication` had no entry point into the kinematic sweep.**
No new CAD primitives, collision math, or kinematic math were needed.

## Tasks

### Task 1 — Assembly → analysis input bridge (normalize)

- `analyze_assembly_kinematics` accepts a `CadAssemblyProgram` (built through the
  real M8C-1 compile + M8C-2 imported-component path) and bounded kinematic
  semantics (axis, moving/stationary IDs, ordered angles).
- Source binding validated via `CadAssemblyGenerationService.validate_source`
  (fail-closed on stale revision / hash mismatch).
- `CadKinematicSweepRequest` built from `assembly_hash(assembly)`,
  `source_assembly_id=assembly.assembly_id`, and caller-supplied partition/angles.

### Task 2 — Production application/service wiring

- Added `ProductionApplication.analyze_assembly_kinematics(...)` in
  `src/mechcad_harness/application.py`.
- Orchestration only: constructs `TransientAssemblyAnalysisService(self.kinematic_measure)`
  and `CadKinematicSweepService(transient_analysis_service=...)`, delegates
  `execute`, returns `CadKinematicSweepResult`.
- The measurement provider is composed at the trusted boundary
  (`ProductionApplication.create(...)` / `__init__`, `kinematic_measure`):
  - Default (production): `FreeCADTransientAssemblyMeasurementProvider().exact_measure`.
  - Tests inject a deterministic provider only at this composition boundary.
- An ordinary `analyze_assembly_kinematics(...)` caller cannot supply an
  `exact_measure` callback; the public method signature exposes no such argument.
  Result trust is owned by the composition.

### Task 3 — Deterministic injected-provider integration tests

- `tests/integration/test_m8c3_production_kinematic_vertical_slice.py`
  - Real `ProductionApplication` entry.
  - Real `CadKinematicSweepService` + real `TransientAssemblyAnalysisService`.
  - Deterministic `exact_measure` substitute at the geometry boundary only.
  - Generic fixture: compiled mounting plate (M8C-1) + synthetic `ImportedCadComponent` (M8C-2).
  - Proves: source identity preservation, partition fail-closed (overlap / unknown /
    invalid axis), angle order preservation, determinism, no state mutation,
    `continuous_sweep_verified is False`.

### Task 4 — Live FreeCAD runtime integration (if available)

- Live test skeleton included; skipped because FreeCAD is unavailable in the
  verification environment. Disposition: runtime-gated.

### Task 5 — Regression verification

- `python -m compileall src/mechcad_harness -q` → exit 0.
- `git diff --check` → exit 0.
- Full suite: 629 passed, 51 skipped. No regressions vs M8C-1/M8C-2/M8B/M7C
  kinematic, transient analysis, exact collision/clearance, and production app tests.

## Files Changed

- `src/mechcad_harness/application.py` — added `analyze_assembly_kinematics` + imports.
- `tests/integration/test_m8c3_production_kinematic_vertical_slice.py` — NEW.
- `docs/superpowers/specs/2026-08-22-m8c3-production-kinematic-vertical-slice-design.md` — NEW.
- `docs/superpowers/plans/2026-08-22-m8c3-production-kinematic-vertical-slice.md` — NEW.

## Out of Scope (preserved)

No DesignSpec acceptance subsystem, material selection, transmission synthesis,
multi-axis kinematics, continuous collision approval, FEA, direct DesignState
mutation, MCP bypass, commit/push/stash/reset/clean.
