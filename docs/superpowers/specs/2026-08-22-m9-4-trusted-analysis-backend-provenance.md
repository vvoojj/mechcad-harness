# M9-4 — Trusted Analysis / Backend Provenance

Date: 2026-08-22
Status: M9_4_TRUSTED_ANALYSIS_PROVENANCE_VERIFIED (design-complete; live FreeCAD path gated behind `MECHCAD_FREECADCMD` like M9-1/2/3)

## 1. Initial Provenance Gap

Before M9-4, `CadKinematicSweepResult` carried only `request_hash`,
`source_assembly_hash`, `sweep_version`, and `result_hash`. There was **no**
durable identity binding the sweep to the measurement provider or the FreeCAD
backend/runtime that produced it.

- `TransientAssemblyAnalysisResult` carried `source_assembly_hash`,
  `transformed_assembly_hash`, `sweep_request_hash`, `sample_angle_deg`,
  `measurements` — no provider/backend identity.
- `Evidence` already supported `producer_name`, `producer_version`,
  `producer_result_id`, `input_hash`, `output_hash`, `backend_provenance`
  (`BackendProvenance`), but nothing bound those to a kinematic-sweep result.
- `BackendProvenance` (`backend_name`, `backend_adapter_version`,
  `library_name`, `library_version`, `library_source`, `library_revision`)
  already existed and is produced by `FreeCADBackend.provenance()` via the
  established discovery boundary (`discover_freecad()` + `_freecad_version()`).
- Consequently an ordinary reader could **not** distinguish a real FreeCAD
  exact sweep from a deterministic/test execution once the in-memory
  composition was gone. No durable record bound `request_hash` +
  `result_hash` + `source_assembly_hash` to provider/backend identity.

## 2. Selected Provenance Boundary

Provenance lives in the **existing `Evidence` / `EvidenceStore`** trusted-evidence
model (preferred option 1), extended by one new narrow typed record:

- `AnalysisExecutionProvenance` (new, in `analysis_provenance.py`) binds the
  four analysis hashes to the provider/backend execution identity.
- `Evidence.analysis_execution_provenance` carries it, alongside the existing
  `producer_*`, `input_hash` (= `request_hash`), `output_hash` (=
  `result_hash`), and `backend_provenance` fields.

Why this layer:
- It reuses the repo's exclusive atomic-write, trusted `EvidenceStore` (no
  duplicate provenance framework).
- `CadKinematicSweepResult` is kept clean (its `result_hash` is unchanged) —
  provenance is evidence metadata, not canonical engineering authority.
- The provenance is persisted under `projects/<id>/evidence/`, so it does not
  disturb the M9-3 artifact-count assertions.

## 3. Measurement Provider Identity

Stable identity is captured on the composed provider object (never caller input):

- **Live FreeCAD provider** (`FreeCADTransientAssemblyMeasurementProvider`):
  - `provider_name = "freecad-transient-exact"`
  - `provider_version = "mechcad-freecad-transient@1.0"` (new constant
    `TRANSIENT_MEASUREMENT_PROVIDER_VERSION` in `transient_freecad_measurement.py`)
- **Deterministic/test provider** (injected callable at the trusted
  composition boundary):
  - `provider_name = "deterministic-test-provider"`
  - `provider_version = "deterministic-test@1.0"`
  - `backend_provenance = None` (does NOT inherit FreeCAD identity)

The version constants live beside the provider/adapter that owns them; no
FreeCAD runtime version is hardcoded into production code.

## 4. Backend / Runtime Identity

For the live FreeCAD path, `AnalysisExecutionProvenance.backend_provenance` is
produced by `FreeCADTransientAssemblyMeasurementProvider.provenance()` →
`FreeCADBackend.provenance()`, which resolves identity through the M9-1
discovery boundary:

- `backend_name = "freecad"`
- `backend_adapter_version = "mechcad-freecad@2.1"` (`FREECAD_BACKEND_VERSION`)
- `library_name = "FreeCAD"`
- `library_version = <resolved at runtime via `_freecad_version(discovery)>` (e.g. `1.1.3` when present; never hardcoded)
- `library_source = <resolved executable path>` (diagnostic)
- `execution_mode = "freecadcmd-subprocess"` (`TRANSIENT_MEASUREMENT_EXECUTION_MODE`)

## 5. Result Binding

`AnalysisExecutionProvenance` binds:

- `request_hash`   (== `CadKinematicSweepResult.request_hash`)
- `result_hash`    (== `CadKinematicSweepResult.result_hash`)
- `source_assembly_hash` (== `CadKinematicSweepResult.source_assembly_hash`)
- `sweep_version`  (== `CadKinematicSweepResult.sweep_version`)

The `Evidence` record additionally sets `input_hash=request_hash`,
`output_hash=result_hash`, `producer_result_id=result_hash`, and
`producer_name`/`producer_version` = the provider identity. The evidence id is
derived deterministically from `request_hash + result_hash`, so the record is
unambiguously tied to the exact result and cannot be detached/reattached to a
different result.

## 6. Caller Trust Boundary

`ProductionApplication.analyze_assembly_kinematics(...)` accepts **no**
provenance fields (`provider_name`, `provider_version`, `backend_name`,
`runtime_version`, `provenance`, `backend_provenance` are all absent from its
signature — asserted by `test_public_analysis_call_accepts_no_trusted_provenance_override`).

The provider/backend identity is derived **inside** `analyze_assembly_kinematics`
from the composed provider object:

- If `_kinematic_measurement_provider` is a
  `FreeCADTransientAssemblyMeasurementProvider` → FreeCAD identity + real
  `backend.provenance()` (resolved from the local FreeCAD runtime).
- Otherwise (a deterministic callable) → deterministic/test identity with
  `backend_provenance=None`.

Therefore an ordinary caller cannot produce deterministic measurements and then
attach `provider=FreeCAD` / `runtime=1.1.3`. The runtime version comes only
from `discover_freecad()` + `_freecad_version()`, not from any caller string.

## 7. Live Evidence

When run on a host with FreeCAD discoverable (gated by `MECHCAD_FREECADCMD`,
identical to M9-1/2/3), the M9-3 live vertical slice persists an `Evidence`
record of kind `analysis.kinematic_sweep`. The M9-3 test now asserts:

- `evidence.kind == "analysis.kinematic_sweep"`
- `evidence.producer_result_id == sweep.result_hash`
- `prov.provider_name == "freecad-transient-exact"`
- `prov.provider_version == "mechcad-freecad-transient@1.0"`
- `prov.backend_provenance.backend_name == "freecad"`
- `prov.backend_provenance.backend_adapter_version == "mechcad-freecad@2.1"`
- `prov.backend_provenance.library_name == "FreeCAD"`
- `prov.backend_provenance.library_version != "unknown"` (actual runtime version)
- `prov.execution_mode == "freecadcmd-subprocess"`

The recorded `library_version` is whatever the local FreeCAD reports (e.g.
`1.1.3`); it is resolved, never hardcoded.

> Note: In this CI/environment FreeCAD is **not** installed, so the live
> (`@pytest.mark.skipif(not FREECAD_AVAILABLE)`) M9-3 and M9-4 live tests are
> skipped — exactly as M9-1/M9-2/M9-3 live tests are skipped here. The code
> path is gated and the assertions above are verified by the skip-guarded live
> tests, not by a fake smaller test.

## 8. Deterministic Provider Evidence

`TestM9_4TrustedAnalysisBackendProvenance` (deterministic, always runs) proves
the deterministic composition yields distinct provenance:

- `prov.provider_name == "deterministic-test-provider"`
- `prov.provider_version == "deterministic-test@1.0"`
- `prov.execution_mode == "deterministic-injected"`
- `prov.backend_provenance is None` and `evidence.backend_provenance is None`

So deterministic results can never be mistaken for FreeCAD-exact results.

## 9. Result Semantics

- `CadKinematicSweepResult` fields and math are **unchanged**.
- `request_hash` unchanged.
- `result_hash` unchanged (the provenance record is stored separately in
  `EvidenceStore`; re-running yields the identical `result_hash` — asserted by
  `test_result_hash_stable_when_provenance_stored_separately`).
- `continuous_sweep_verified` remains `False`.
- Collision classification, `common().Volume`, `distToShape()` semantics,
  kinematic transforms, angle ordering, moving/stationary partition, and
  continuous-sweep verification are untouched.

## 10. Authority Boundary

Provenance is evidence metadata only. `analyze_assembly_kinematics`:
- does not mutate `DesignState` (asserted by `test_analysis_does_not_mutate_design_state` and the M9-3 no-mutation checks);
- creates no `ChangeProposal` / `ChangeSet`;
- performs no geometry/assembly/selection/engineering decision changes.

## 11. Tests

- Focused: `tests/integration/test_m9_4_trusted_analysis_backend_provenance.py`
  - A default live provider provenance (live, gated)
  - B deterministic provider differentiation
  - C caller cannot spoof
  - D result binding
  - E live runtime identity (live, gated)
  - F stable identity (deterministic + live)
  - G no result-hash corruption
  - H no state mutation
  - I live M9-3 regression (live, gated)
- M9-3 extended with provenance assertions.
- M8C-3 / M9-1 / M9-2 regression suites pass.

## 12. Files Changed

- `src/mechcad_harness/analysis_provenance.py` (new): `AnalysisExecutionProvenance` + provider identity constants.
- `src/mechcad_harness/models/evidence.py`: added `analysis_execution_provenance` field.
- `src/mechcad_harness/transient_freecad_measurement.py`: provider `provider_name`/`provider_version`/`execution_mode` + `provenance()`.
- `src/mechcad_harness/application.py`: `_record_kinematic_sweep_provenance`, `get_kinematic_sweep_evidence`, wiring in `analyze_assembly_kinematics`.
- `tests/integration/test_m9_4_trusted_analysis_backend_provenance.py` (new).
- `tests/integration/test_m9_3_live_mixed_assembly_exact_kinematic.py`: provenance assertions + dependency node.
- `tests/integration/test_m8c3_production_kinematic_vertical_slice.py`: dependency node for `analysis.kinematic_sweep`.

## 13. Remaining Limitations

- This environment has no FreeCAD, so the live M9-3 vertical slice and live
  M9-4 FreeCAD-provenance tests are gated/skipped (same as M9-1/2/3 here). They
  must be executed on a FreeCAD-equipped host for conclusive live evidence.
- No M10 work; out-of-scope items (multi-axis, continuous collision, FEA,
  materials, manufacturing, optimization, component selection, mechanism
  synthesis) are untouched.

## 14. M9-4 Edge Upgraded

`TRUSTED_ANALYSIS_EXECUTION_PROVENANCE_VERIFIED`

## 15. Remaining M9 Work

Only M9 system-level acceptance (run the live gated tests on a FreeCAD host and
record the actual runtime version in the acceptance report).

## 16. Scope Confirmation

No geometry changes, collision changes, kinematic-math changes, multi-axis,
continuous collision, FEA, materials, manufacturing, optimization, or
commit/push/stash/reset/clean.
