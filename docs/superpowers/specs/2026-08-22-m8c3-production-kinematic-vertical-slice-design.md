# M8C-3 Design: Production Assembly → Exact Analysis → Generic Kinematic Vertical Slice

**Date:** 2026-08-22
**Status:** DESIGN
**Depends on:** M8C-1 (DesignSpec → CadPartProgram), M8C-2 (ImportedCadComponent → CadAssemblyProgram)

## 1. Initial Connectivity Gap

The analysis foundation already exists and self-composes correctly:

- `CadKinematicSweepService.execute(request, assembly)` internally calls
  `TransientAssemblyAnalysisService.analyze(transient_request, transformed)`,
  which in turn calls an injected `exact_measure(request, transformed_assembly)`
  callback (the exact geometry boundary: `common().Volume` / `distToShape()`).
- `CadAssemblyProgram` already supports generated parts **and** imported
  components, and `assembly_hash` includes both component identities and instance
  transforms.

The missing edge is **ProductionApplication → kinematic analysis**. There is no
production entry point that takes a trusted assembly + bounded kinematic
semantics and delegates to the existing `CadKinematicSweepService`. The sweep
service and transient provider have only test callers today.

**Gap:** `ProductionApplication.analyze_assembly_kinematics(...)` does not exist.

## 2. Selected Generic Fixture

A generic mechanical fixture, no Yagi/AZ/EL semantics:

- One **generated mounting plate** (`MountingPlateDesignSpec` compiled by
  `CadCompilationService` → `CadPartProgram`, M8C-1 path), and
- One **imported generic component** (`ImportedCadComponent`, M8C-2 path; generic
  body, the analysis code does not know it is any specific part).

The imported component geometry, placements, moving/stationary IDs, axis, and
ordered angles are **accepted inputs** for M8C-3 (verification connectivity, not
mechanism synthesis). M8C-3 does NOT select motor, gear ratio, axis height,
shaft size, bearing, material, structural dimensions, or collision-clear design.

## 3. Exact Source Binding

The production entry point validates the trusted source binding via
`CadAssemblyGenerationService.validate_source(project_id, source_revision,
source_state_hash)` (inherited from `CadGenerationService`), which fails closed
on missing revision or state-hash mismatch against the authoritative
`StateManager`.

Assembly identity is preserved through `assembly_hash(assembly)`:
- `assembly_id`
- per generated part: `part_id`, `program_hash`
- per imported component: `component_id`, `artifact_id`, `artifact_hash`,
  `format`, `source_revision`, `source_state_hash`, `component_hash`
- per instance: `instance_id`, `part_id`, placement

The `CadKinematicSweepRequest` is built with `source_assembly_id =
assembly.assembly_id` and `source_assembly_hash = assembly_hash(assembly)`.

`run_id` is **not** part of the kinematic semantic identity. If the assembly is
persisted, `run_id` remains correlation/storage scope only (M8C-2 semantics).

## 4. Exact Production Application API

```python
# src/mechcad_harness/application.py

class ProductionApplication:
    # Provider composed at the trusted composition boundary (ProductionApplication.create)
    def __init__(self, *, ..., kinematic_measure=None): ...
    def analyze_assembly_kinematics(
        self,
        *,
        source_revision: int,
        source_state_hash: str,
        assembly: CadAssemblyProgram,
        axis: RevoluteAxis,
        moving_instance_ids: tuple[str, ...],
        stationary_instance_ids: tuple[str, ...],
        sample_angles_deg: tuple[float, ...],
    ) -> CadKinematicSweepResult: ...
```

The measurement provider is **composed, not caller-supplied**. An ordinary
workflow caller of `analyze_assembly_kinematics` cannot pass an `exact_measure`
callback; the public method signature exposes no such argument. The provider is
selected once at `ProductionApplication.create(...)` (or `__init__`):

- Default (production): `FreeCADTransientAssemblyMeasurementProvider().exact_measure`
  — the trusted runtime-execution boundary.
- Tests inject a deterministic provider **only at this composition boundary**.

The application:
1. Validates the trusted source binding (`assembly_service.validate_source`).
2. Computes `assembly_hash(assembly)` and builds a `CadKinematicSweepRequest`.
3. Constructs `TransientAssemblyAnalysisService(self.kinematic_measure)`.
4. Constructs `CadKinematicSweepService(transient_analysis_service=...)`.
5. Delegates `service.execute(request, assembly)` and returns the
   `CadKinematicSweepResult`.

It does NOT: transform instances, calculate collision, import STEP, construct
FreeCAD geometry, duplicate `CadKinematicSweepService` logic, or accept a
caller-controlled measurement callback. It is orchestration only.

### Result Trust

Because the provider is owned by the trusted composition, an ordinary
`analyze_assembly_kinematics(...)` call cannot author geometry measurements.
Only the composer of the `ProductionApplication` (trusted runtime/external
boundary) determines the measurement source.

### Reporting Distinction

- **Deterministic connectivity proof** (injected provider): proves the internal
  production graph (request build, sweep service, transient service, partition
  and hash validation, classification) end-to-end. It does **not** prove a
  temporary FreeCAD workspace; no public per-sample `ArtifactStore` artifacts
  are produced.
- **Live FreeCAD provider contract** (trusted default): temporary workspace,
  exact `common().Volume` / `distToShape()`, runtime-gated.

The synthetic `ImportedCadComponent` fixture exercises the assembly/kinematic
boundary (generated plate + imported component identity in `assembly_hash`).
M8C-2 separately owns `ArtifactStore` byte-integrity and resolution proof for
the imported STEP artifact.

## 5. Which Existing Analysis Services Are Reused

- `CadKinematicSweepService` (generic discrete sweep) — unchanged.
- `TransientAssemblyAnalysisService` — unchanged (orchestrates measurement,
  validates pair inventory and transformed hash).
- The exact geometry boundary is the injected `exact_measure` callback
  (`FreeCADTransientAssemblyMeasurementProvider.exact_measure` in production),
  which executes `common().Volume` / `distToShape()` in a temporary workspace.

Exact collision classification (interference / touching / clearance) remains in
`CadKinematicSweepService.CollisionClassification.from_measurement` and is
reused, not re-implemented.

## 6. Moving / Stationary Partition

Explicit instance IDs supplied by the caller. The `CadKinematicSweepRequest`
model validator already fails closed when:
- moving/stationary overlap,
- duplicate IDs,
- empty IDs,
- the union of moving+stationary does not equal the assembly's instance set
  (verified again by `CadKinematicSweepService.validate_source`).

No naming-based inference.

## 7. Axis Definition

`RevoluteAxis` (existing generic model). Direction is normalized and must be
non-zero; frame_id is a free string binding. No AZ/EL/Yagi semantics.

## 8. Angle Sequence

`tuple[float, ...]` of ordered sample angles, supplied by the caller and
preserved in request order. `CadKinematicSweepResult.from_samples` asserts the
returned sample angles equal `request.sample_angles_deg`; no sorting.

## 9. Deterministic Result Identity

- `request_hash` — canonical SHA-256 of the request (axis, partition, angles,
  source hash, tolerances, sweep version).
- `source_assembly_hash` — `assembly_hash(assembly)`.
- `transformed_assembly_hash` per sample — `assembly_hash(transformed)` after
  deterministic axis-angle transform.
- `result_hash` — canonical SHA-256 of the result payload.

## 10. Runtime-Gated Behavior

FreeCAD is unavailable in the M8C-3 verification environment. Production wiring
is fully implemented; the only runtime-dependent boundary is the geometry
execution inside `exact_measure`. Deterministic connectivity tests inject a
deterministic `exact_measure` provider. Disposition: `M8C_3_COMPLETE_RUNTIME_GATED`.

## 11. Why No New Kinematic Semantics Are Introduced

`CadKinematicSweepService`, `RevoluteAxis`, `CadRigidTransform`,
`CadKinematicSweepRequest`, and the exact measurement boundary are all reused
verbatim. `ProductionApplication` only wires them. No AZ/EL/Yagi/pan/tilt is
added to the generic service.

## 12. M8C-4 / Later Exclusions

Not implemented in M8C-3:
- Material selection, transmission synthesis, multi-axis serial chains
- Continuous collision verification
- FEA, structural / tolerance / manufacturing approval, optimization
- Automatic collision avoidance / mechanism redesign
- Yagi-specific kinematic core behavior
- Persisted public CAD artifact per sweep angle (transient samples stay temporary)
- M9 work

## 13. Audit Answers (A–H)

A. The exact geometry boundary `exact_measure(request, program)` accepts
   `(TransientAssemblyAnalysisRequest, CadAssemblyProgram)` and returns
   `tuple[tuple[str, str, float, float], ...]` (moving, stationary,
   interference_volume_mm3, distance_mm). Separately, the persisted-analysis
   `CadAssemblyAnalysisService.analyze(project_id, run_id, revision, state_hash,
   program, plan, workspace)` is NOT in the M8C-3 sweep path.
B. The transient boundary accepts `CadAssemblyProgram` (the transformed
   assembly descriptor).
C. `TransientAssemblyAnalysisService.analyze(request, transformed_assembly)`
   accepts `(TransientAssemblyAnalysisRequest, CadAssemblyProgram)`.
D. `CadKinematicSweepService.execute(request, assembly)` accepts
   `(CadKinematicSweepRequest, CadAssemblyProgram)`.
E. Yes — `CadKinematicSweepService.execute` already calls
   `self.transient_analysis_service.analyze(...)`.
F. The sweep requires: `source_assembly_id`, `source_assembly_hash`,
   `axis: RevoluteAxis`, `sample_angles_deg` (ordered), `moving_instance_ids`,
   `stationary_instance_ids`. The measurement provider is injected into the
   transient analysis service.
G. `ProductionApplication` has real (production) callers for compilation,
   assembly generation, and transmission round-trip. `CadKinematicSweepService`
   and `TransientAssemblyAnalysisService` currently have only test callers —
   the missing production caller is `ProductionApplication`.
H. The missing edge is **application → analysis**: `ProductionApplication` has no
   entry point into the existing generic kinematic sweep.
