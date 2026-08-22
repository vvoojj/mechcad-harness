# M10-1 Completion Report — Continuous Single-Axis Clearance Proof

## Live Runtime

- **FreeCAD**: 1.1.3 (`C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`)
- **py_gearworks**: 0.0.18
- **build123d**: 0.11.1
- **numpy**: 2.3.5 / **scipy**: 1.18.0
- **Python**: 3.14.6
- **Execution mode**: freecadcmd-subprocess

## Real Fixture

- **Generated part**: `plate` — `MountingPlateDesignSpec` (40×40×10 mm, 1× M6 hole)
  → `CadPartProgram` via `CadCompilationService.compile_mounting_plate`
- **Trusted imported STEP**: `gear-1` — real `mechcad-build-spur-gear-cad@1.0`
  (12 teeth, module 2, face width 5 mm, 20° pressure angle)
  → `ArtifactStore` → `ImportedCadComponent` (SHA-256 verified)
- **Assembly**: `m10-1-fixture` — mixed `CadAssemblyProgram`
  (plate at (0, −60, 0), gear at (20, 0, 5))
- **FreeCAD realization**: live `CadAssemblyGenerationService` → FCStd verified `shape_valid=True`
- **Axis**: world-Z through origin, frame `fixture_frame`

## VERIFIED_CLEAR Evidence

| Field | Value |
|-------|-------|
| interval | 85.000000 .. 95.000000 deg |
| required_clearance_mm | 0.0 |
| proof_guard_mm | 1e-06 |
| status | `verified_clear` |
| exact_evaluations_count | 1 |
| maximum_depth_reached | 0 |
| certified_leaf_count | 1 |
| unresolved_intervals | () |
| minimum_certified_lower_clearance_mm | **22.7907** |
| radial_bound_mm | 36.7875 |
| angular_motion_bound_mm | 3.2093 |
| exact_distance_mm (at 90°) | 26.0000 |
| request_hash | `sha256:7ac5379c8a490203c23297bf64e3052e3c963e7fb509e30262767c15aae034bc` |
| result_hash | `sha256:ede31c2d70b65c69eb3827b1bdcabc85eac8db73e0ef24f7518ae74969ac7022` |

**Coverage**: COMPLETE — single leaf interval [85.0, 95.0] covers the full
requested interval with no gaps. `22.7907 > 0` confirms positive certified
clearance. Real FreeCAD `common().Volume` / `distToShape()` evaluation at 90°
produced exact distance 26.0 mm; radial bound 36.79 mm derived from real
bounding box corners of the gear STEP geometry.

## COLLISION_WITNESS Evidence

| Field | Value |
|-------|-------|
| interval | 260.000000 .. 280.000000 deg |
| witness_angle_deg | 270.000000 |
| moving_instance_id | `gear-inst` |
| stationary_instance_id | `plate-inst` |
| interference_volume_mm3 | **545.4343** |
| exact_distance_mm | 0.0000 |
| classification | `interference` |
| result_hash | `sha256:a7416354ade7cb20ad08d4a3968f413c8720c14d5b32da0ace287e940afc0721` |

Confirmed: real FreeCAD geometry evidence. The gear overlaps the plate at 270°
with 545.43 mm³ interference volume. The interval was **not** certified
VERIFIED_CLEAR.

## NOT_PROVEN Evidence

| Field | Value |
|-------|-------|
| interval | 0.000000 .. 360.000000 deg |
| max_exact_evaluations | 2 |
| max_depth | 1 |
| status | `not_proven` |
| exact_evaluations_count | 2 |
| maximum_depth_reached | 1 |
| certified_leaf_count | 0 |
| unresolved_intervals | [0..180, 180..360] (2 intervals, each 180° wide) |
| collision_witness | None |
| result_hash | `sha256:f2563146092d8a8b23ce8df48d9e426fbfe77b5d6a7188d01a5075841a54a5e4` |

Confirmed: resource limits exhausted without claiming clearance or witness.
Two unresolved intervals remain. Fail-closed NOT_PROVEN semantics verified.

## Conservative Bound Evidence

- **motion_bound formula**: `2R·sin(min(|Δθ|, π)/2) + ε(1+R)` with
  `ε = 1e-9`
- **Radial bound (R)**: 36.7875 mm — derived from real FreeCAD bounding box
  corners of gear STEP, projected to world-Z axis via `point_to_line_distance`
- **Half-span at 90°** (interval width 10°): 5° = 0.0873 rad
- **Angular motion bound**: `2 × 36.7875 × sin(2.5°) = 3.2093 mm`
- **Certified lower clearance**: `26.0000 − 3.2093 − 0.0 = 22.7907 mm > 0`

## Provenance Binding

| Field | Value |
|-------|-------|
| proof_algorithm_version | `conservative-single-axis-clearance-proof@1.0` |
| provider_name | `freecad-transient-exact` |
| provider_version | `mechcad-freecad-transient@1.0` |
| backend_name | `freecad` |
| backend_adapter_version | `mechcad-freecad@2.1` |
| library_name | `FreeCAD` |
| library_version | `1.1.3` |
| library_source | `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe` |
| execution_mode | `freecadcmd-subprocess` |
| evidence.id | `EVD-CPROOF-2e45d2cede471d2ac9e4cf69` |
| evidence.kind | `analysis.continuous_clearance_proof` |

**Hash bindings** (all verified True):
- `result.request_hash == evidence.input_hash`
- `result.result_hash == evidence.output_hash`
- `prov.request_hash == result.request_hash`
- `prov.result_hash == result.result_hash`
- `prov.source_assembly_hash == result.source_assembly_hash`

## Discrete Sweep Regression

| Field | Value |
|-------|-------|
| continuous_sweep_verified | **False** |
| sweep_version | `rigid-body-collision-sweep@1.0` |
| aggregate_classification | `collision_present` |
| samples | 4 (0°, 90°, 180°, 270°) |
| 0° | positive_clearance, 6.0 mm |
| 90° | positive_clearance, 26.0 mm |
| 180° | positive_clearance, 14.9 mm |
| 270° | interference, 545.4 mm³ |

Confirmed: ordinary `CadKinematicSweepResult.continuous_sweep_verified` remains
`False`. M10-1 does not globally change discrete sweep semantics.

## Tests

| Suite | Count | Status |
|-------|-------|--------|
| M10-1 unit tests | 33 | **33 passed** |
| Full regression | 723 passed, 25 skipped | **0 failed** |
| Live integration | 1 | **1 passed** (58.81s) |
| Compile check | — | **clean** |
| git diff --check | — | **CRLF warnings only** (no errors) |

## Files Changed

| File | Change |
|------|--------|
| `src/mechcad_harness/continuous_proof.py` | New — core proof algorithm |
| `src/mechcad_harness/analysis_provenance.py` | Modified — added ContinuousProofExecutionProvenance |
| `src/mechcad_harness/models/evidence.py` | Modified — added continuous_proof_execution_provenance field |
| `src/mechcad_harness/transient_freecad_measurement.py` | Modified — added geometry_radial_bounds + _radial_script; **fixed** instance→component ID mapping bug |
| `src/mechcad_harness/application.py` | Modified — added prove_continuous_single_axis_clearance + helpers |
| `tests/test_m10_1_continuous_proof.py` | New — 33 unit tests |
| `tests/integration/test_m10_1_live_continuous_proof.py` | New — live integration test |
| `scripts/m10_1_evidence_capture.py` | New — evidence capture script |
| `docs/superpowers/specs/2026-08-22-m10-1-continuous-single-axis-collision-proof.md` | New — design spec |
| `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md` | Modified — M10-1 row |
| `docs/architecture/MECHCAD_RUNTIME_FLOW.md` | Modified — M10-1 flow section |
| `docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md` | Modified — continuous proof contract row |
| `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md` | Modified — acceptance, limitations, next boundary |
| `AGENTS.md` | Modified — acceptance line + hard limitation |
| `docs/audit/MECHCAD_M10_1_COMPLETION_REPORT.md` | Updated — actual live evidence |

## Remaining Limitations

- M10-1 is **single-axis only**; multi-axis kinematic chains remain future
- `continuous_sweep_verified = False` on ordinary discrete sweeps (by design)
- FEA, materials selection, manufacturing output, tolerance verification,
  optimization, and automatic synthesis/selection remain future
- Radial bound is conservative (bounding box corners); tighter bounds possible
  but not required for correctness

---

**Final disposition: `M10_1_CONTINUOUS_SINGLE_AXIS_CLEARANCE_PROOF_VERIFIED`**
