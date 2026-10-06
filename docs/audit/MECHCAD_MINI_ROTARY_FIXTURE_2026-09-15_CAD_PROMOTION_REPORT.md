# MINI_ROTARY_FIXTURE 2026-09-15 CAD/Promotion Report

## Claim Status

```text
PROJECT CONTINUATION CLAIM — NOT INDEPENDENT ACCEPTANCE
MINI_CORE_CAD_PROMOTION_REMEDIATION_REJECTED_BY_FULL_RANGE_CLEARANCE
```

This is a current continuation record. It does not modify or supersede the
historical completion report and does not create a new milestone acceptance
marker.

## Baseline And Accepted Inputs

- HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807`.
- Accepted current markers: `MINI_N2_N3_INDEPENDENTLY_ACCEPTED` and
  `MINI_CANDIDATE_AB_INDEPENDENTLY_ACCEPTED`.
- Candidate source Revision 3 hash:
  `sha256:d48680ac9bafde5f7328ea57ad66ef80ff0388cfbfec9ec553fbeb5ee8322270`.
- Candidate A: `top_plate_side_mm=60.0`.
- Candidate B: `top_plate_side_mm=50.0`.
- The geometry-bearing path preserves the two old geometry-less candidate
  records as historical inputs and creates exactly two new candidate identities;
  the older N2 candidate and a third candidate are not used.
- Shared accepted authority: force `6.0 N`, lever arm `0.025 m`, safety factor
  `2.0`, trusted design torque `0.30000000000000004 N*m`, canonical output speed
  `0.5235987755982988 rad/s`, lowered speed `4.999999999999999 rpm`, voltage
  `24 V`, shaft `8.0 mm`, transverse load Y `6.0 N`, Z `0.0 N`.

## Process-Local Runtime Configuration

The following variables were set only in the PowerShell process running the
verification and production API attempts:

```text
MECHCAD_FREECADCMD=C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe
MECHCAD_GMSH=C:\Program Files\FreeCAD 1.1\bin\gmsh.exe
MECHCAD_CCX=C:\Program Files\FreeCAD 1.1\bin\ccx.exe
```

No persistent environment, registry, PATH, profile, or repository
configuration was changed.

## Runtime Discovery

- FreeCAD discovery: available executable
  `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`, execution boundary
  `bundled FreeCAD command line`. The current `discover_freecad()` object
  leaves `version=None` for configured command-line discovery; the production
  `FreeCADBackend.provenance()` probe observed FreeCAD `1.1.3` and matching
  bundled identity `freecad-1.1.3-bundled`.
- Gmsh discovery: available at
  `C:\Program Files\FreeCAD 1.1\bin\gmsh.exe`, version `4.15.0`, matching
  identity `gmsh-4.15.0-bundled`.
- CalculiX discovery: available at
  `C:\Program Files\FreeCAD 1.1\bin\ccx.exe`, version `2.22`, matching
  identity `calculix-2.22-bundled`.

The runtime/provider readiness gate passed. No platform discovery gap was
found, and no platform source was patched.

## Geometry-Bearing Candidate CAD

Project-local composition now publishes deterministic synthetic STEP authority
through the existing FreeCAD backend for the motor envelope, output shaft,
bearing, hub, and stationary mount scene. The stationary scene contains the
`120 x 120 x 10 mm` base, wall `X=50..60`, `Y=-60..60`, `Z=45..95`, and motor
shelf. Candidate A and B use bounded generated top plates `60 x 60 x 8 mm` and
`50 x 50 x 8 mm` respectively.

The new candidates bind all seven constituents to geometry authority: six
trusted source STEP specifications and one bounded generated plate
specification. Their candidate hashes differ from the historical geometry-less
Candidate A/B hashes, while Revision 3 and the engineering authority remain
unchanged.

`ProductionApplication.realize_candidate_cad(...)` returned successful
realizations for both candidates. The generated mappings cover all seven
physical instances and the production CAD replay verifier accepts them.

## Pair Inventory And M10

The remediation declares all 21 pairs in a project-local authority table. It
uses the full seven-constituent pair universe, classifying fixed-fixed,
connected, and shared output-rigid pairs explicitly out of scope, while
declaring every remaining fixed/output pair for clearance evaluation. The
required interval is `(0.0, 360.0)` degrees with required clearance `5.0 mm`.

The retained production transient provider now emits `M7C1_JSON` after the
workspace path is canonicalized. Candidate A's first four checked pairs
returned `verified_clear` over the full interval, but the fifth checked pair,
`cad-fixture-bearing-b` / `cad-fixture-output-hub`, returned a `TOUCHING`
witness at `180.0` degrees with `0.0 mm` exact distance and `0.0 mm^3`
interference volume. This violates the frozen `5.0 mm` requirement. No
CandidateEvaluation, comparison, selection, promotion, canonical result, or
M11 handoff is claimed from this rejected run.

## Comparison, Selection, And Promotion

- Not executed after the full-range remediation failed. No candidate was
  silently selected or promoted.

## Canonical Reconstruction And M11

- Not executed after the full-range remediation failed. The earlier bounded
  temporary run remains historical bounded evidence only.
- M11 eligibility/handoff: not part of this implementation run. No structural
  solve was run.

## M6A And Optional Providers

- M6A current classification: `PROJECT_LOCAL_MISSING`; the MINI still injects
  `_NoAgentAdapter`. No M6A changes or live agent invocation were made.
- M5.5 materials and section providers were not executed and were not installed.
- `py_gearworks` and `build123d` were not used by this core task.

## Verification

Runtime/API verification:

```text
FreeCADBackend.provenance(): FreeCAD 1.1.3
discover_gmsh(): available, 4.15.0
discover_calculix(): available, 2.22
run_final_candidate_continuation(): Revision 3, exactly two candidates
realize_candidate_cad(): geometry-bearing candidate CAD reached the real
provider boundary
diagnose_retained_m7c1(): PRODUCTION_TRANSIENT_SUCCESS; FreeCAD 1.1.3 emitted
M7C1_JSON with 20.0 mm exact distance and 0.0 mm^3 interference
Candidate A full-range M10: first four checked pairs verified; fifth pair
returned TOUCHING at 180.0 degrees and 0.0 mm exact distance
```

Focused verification after the production boundary attempt:

```text
python -m pytest projects/mini_rotary_fixture/test_acceptance.py -q
14 passed in 247.93s

python -m compileall -q projects/mini_rotary_fixture
exit 0

py -3 -m pytest tests/unit/test_freecad_backend.py tests/unit/test_freecad_identity.py tests/unit/test_m12_candidate_cad_models.py tests/unit/test_m12_candidate_cad_replay.py tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_m10_binding.py tests/unit/test_m12_candidate_m10_service.py tests/test_m10_1_continuous_proof.py tests/integration/test_m12_candidate_cad_m10_production.py tests/integration/test_freecad_backend_live.py -q
147 passed in 248.85s
```

The prior bounded suite includes isolated production CAD, `0..10` degree M10,
comparison, selection, promotion, reconstruction, and fresh canonical M10
execution. The latest full-range run is rejected by the touching witness above;
the result is not independent milestone acceptance.

## Genuine Blocker And Next Boundary

The retained workspace path/protocol blocker is resolved by canonicalizing the
project workspace before invoking the real FreeCAD transient provider. The
full-range geometry blocker was resolved by the later explicit MINI test
authority and source-traceable lowering: bearing B and output hub now have a
verified `5.305869220520782 mm` lower bound. The later motor-side `mount-face`
and hub-side `body` authorities resolved the motor and hub promotion
ambiguities, but promotion then stopped with `canonical M10 pair interface is
ambiguous for shaft`. The shaft's `motor-side`, `hub-side`, `journal-a`, and
`journal-b` interfaces are not narrowed by the supplied authority for the
nonconnected motor-mount/shaft clearance obligation. No interface may be
guessed, so no canonical mutation, canonical CAD/M10, or M11 execution is
claimed.

## Protected Surfaces

- Historical completion report: unchanged.
- `src/mechcad_harness/**`: unchanged.
- Tests: project-local acceptance tests now include geometry-bearing and
  full-chain coverage.
- Accepted Specs/Plans and normative architecture: unchanged.
- No package installation, permanent environment change, commit, push, reset,
  clean, or stash was performed.
