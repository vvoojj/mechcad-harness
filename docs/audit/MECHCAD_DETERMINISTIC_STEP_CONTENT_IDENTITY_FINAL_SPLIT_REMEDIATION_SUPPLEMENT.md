# Deterministic STEP Content Identity — Split Remediation / Current-Bytes Evidence

## Authority and scope

- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Accepted revised Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- Code HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807` (worktree edits uncommitted).
- No commit, push, tag, release, or history rewrite.

This is a new supplemental record for the current bytes. It does not replace the
historical T-P8.3 evidence record.

## Changed-byte hashes

```text
6d33640fcffed213fb1f71c1a7b30091ab79aeb76b3d3037c2da5f8d8c8d02b3  src/mechcad_harness/candidates/services.py
f67ecb7787d9c421a68f0f6465cb88606bfbdc3a75d5f2640434314ae2c75321  src/mechcad_harness/backends/gearworks_cad.py
8e4f09da9bda0d0405ede98f0c8a77c0977b4d0f480f7491d6e1a6b3c98a7aca  tests/integration/test_m12_candidate_cad_m10_production.py
772112daa552343a1eb173d1e5aeb6117be3b72a49e84217533f7fdd17e84436  tests/integration/test_m12_promotion_production.py
014aaacf04693c73a802265a57264ddae6d33913639e9bd9b481576705b6a938  tests/unit/test_currentness_exact_source_supplementation.py
45a262c797f0dcce69285d61e31750f5bd5216bc53828fa8e0f5dee4ce5e772a  tests/unit/test_gear_cad.py
```

`test_m12_promotion_production.py` is among prior accepted implementation-evidence
bytes; its new hash is distinct from prior `c4737630…`. Prior acceptance does not
transfer to the changed fixture/test bytes; this new audit scope includes them.

## CASE C currentness supplementation

Classification before: `PARTIAL` — existing semantic binding substituted exact source
artifacts for consumed-authority identities but did not supplement the verifier context
with candidate-required source identities.

Production change is limited to the existing semantic-binding owner in
`candidates/services.py`: `_compute_semantic_binding` preserves the state/consumed-
authority pass, then adds only identities from the existing
`candidate_cad_required_raw_source_identities(candidate)` allowlist, verified from
`ArtifactStore` bytes and bound to project/revision/state. Arbitrary exact artifacts do
not become context entries. Currentness accepts/forwards the optional exact-artifact
input; legacy/state-only paths default unchanged.

Fresh verification:

```text
tests/unit/test_currentness_exact_source_supplementation.py
  11 passed (included in the focused 62-pass batch below)
focused supplementation / trusted semantic / synthesis / request / mapping:
  62 passed in 16.14s
currentness + semantic-family + admission + comparison/selection/provenance batches:
  30 passed in 10.65s
  189 passed in 179.40s
```

## CASE G2 provider correction

Classification before: `PARTIAL` — `gearworks_cad.py` explicitly instructed
build123d/Open CASCADE to emit the provider extension `2000-01-01T00:00:00Z`.
Accepted Spec §21 permits exactly `YYYY-MM-DDTHH:MM:SS`; timezone/provider suffixes
must fail closed. The production adapter now requests `2000-01-01T00:00:00` directly
from `export_step`, then publishes those returned bytes. No parser rule or test-only
rewriting was introduced.

Generated stored artifact evidence:

```text
FILE_NAME('Open CASCADE Shape Model','2000-01-01T00:00:00',('Author'), ...)
```

The GearWorks provider test reads the stored STEP artifact, requires the exact accepted
timestamp, computes `step_content_identity@1` from those same bytes, checks repeated
same-input identity equality and a teeth-change identity difference. Existing strict
parser tests retain rejection of external `...Z` and malformed timestamp inputs.

```text
python -m pytest tests/unit/test_gear_cad.py tests/unit/test_step_content_identity.py -q --tb=short -p no:randomly
26 passed in 46.23s
```

## Bounded-vs-source-backed fixture family split

Accepted Spec §8 distinguishes TRUSTED_SOURCE_GEOMETRY from bounded fidelity; bounded
mapping has null `source_geometry_identity`. The current @3 input validator additionally
requires every component specification carrying a non-null `geometry_source` to map as
TRUSTED_SOURCE_GEOMETRY (`evaluation.py:_validate_cad_inputs_v2`). Candidate@2 component
specifications must be `component-specification@4`, and the accepted semantic projection
requires a geometry source for a supplied spec; generated-part specs instead require
EXACT_GENERATED_GEOMETRY. Therefore the legacy capstone test’s combined source-backed
mount/body specs + bounded mappings was not representable by the accepted @3 contract.

The fixture now separates the responsibilities without deleting source authority from
an existing candidate:

- bounded collision tests use a separately constructed legacy candidate@1 whose
  motor-mount and payload-body use the existing base `mount_specification()` and
  `body_specification()` (component-specification@1, geometry_source=None) plus the
  already-declared candidate geometry design variables. Other supplied components keep
  their verified source artifacts and trusted mappings. The request remains @1 for this
  actual legacy candidate family.
- source-backed candidate@2 path dispatches through the existing `_cad_m10_inputs_v2`
  request@3/mapping@2 builder, with source-backed mappings remaining trusted. The
  comparison/selection test uses this @2 path; the M10 world-axis fixture value is
  pinned to the original capstone axis origin (`0 mm`).

Focused family test:

```text
python -m pytest tests/integration/test_m12_candidate_cad_m10_production.py::test_candidate_cad_fixture_dispatch_keeps_bounded_legacy_and_trusted_v3_families -q --tb=short -p no:randomly
1 passed
```

This test verifies bounded legacy specs have no geometry source and bounded mappings
remain bounded, while source-backed candidate@2 generates request@3/mapping@2 trusted
identities. No production CAD validator was changed.

## Five affected live tests

Runtime: `C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe`, FreeCAD 1.1.3 Revision
20260725; Python 3.14.6 at
`C:\Users\vvooj\AppData\Local\Python\pythoncore-3.14-64\python.exe`; real bundled
FreeCAD command-line subprocess. No Gmsh, no CalculiX, no solver/mesh, no M11 structural.

Exact selected node IDs:

```text
tests/integration/test_m12_candidate_cad_m10_production.py::test_explicit_bounded_collision_fixture_is_candidate_bound_not_trusted_fallback
tests/integration/test_m12_candidate_cad_m10_production.py::test_live_direct_drive_clear_collision_and_not_proven_chain
tests/integration/test_m12_candidate_cad_m10_production.py::test_live_comparison_and_selection_are_deterministic_and_noncanonical
tests/integration/test_m12_candidate_cad_m10_production.py::test_candidate_realization_rejects_unavailable_trusted_external_spur_artifact_without_downgrade
tests/integration/test_m12_candidate_cad_m10_production.py::test_live_external_spur_preserves_unmodeled_internal_motion_boundary
```

Command:

```text
$env:MECHCAD_FREECADCMD = "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"
python -m pytest <five node IDs above> -v --tb=short -p no:randomly
5 passed in 404.72s
```

## T-P8.3 on current production bytes

```text
$env:MECHCAD_FREECADCMD = "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"
python -m pytest tests/integration/test_step_content_identity_live.py -v --tb=short -p no:randomly
6 passed in 37.71s
```

FreeCAD only; no Gmsh/CalculiX. This is fresh T-P8.3 evidence for the current
`services.py` and `gearworks_cad.py` bytes. The old record remains a historical record
for its own prior invocation/bytes.

## Required regression summary

- T-P8.1 focused P1→P7 + closure/restart + currentness supplementation: **427 passed
  in 170.96s**.
- T-P8.2 broad `tests/unit` keyword group: initial invocation reported 2 failures,
  1 skip, 2439 passed (Rotator V2 inventory fixture mismatch and README documentation
  expectation); rerun excluding those two exact unrelated node IDs: **2439 passed,
  1 skipped, 866 deselected in 529.53s**. Both excluded findings remain reported, not
  silently waived or claimed pre-existing.
- M12/M13 unit batch: **87 passed**; M13-2 candidate CAD integration: **30 passed**.
- `tests/integration/test_m12_candidate_cad_m10_production.py` excluding its five live
  nodes: **16 passed**.
- `tests/integration/test_m12_promotion_production.py` excluding four M12-5 promotion
  live nodes: **21 passed**.
- The four additional M12-5 live promotion cases were run and failed: two direct-drive
  cases and one no-comparison spur case use legacy `CandidatePromotionRequest@1` with
  candidate/evaluation/selection@2; the comparison-bearing spur case additionally has
  an expected ranking relation opposite to the observed current geometry result. These
  are outside the five authorized live nodes and are retained as separate findings.
- `python -m compileall -q src/mechcad_harness`: passed.
- Scoped `git diff --check`: clean.
- All six protected SHA pins and all five accepted implementation pins still match.

## Acceptance boundary

The previous independently accepted T-P8.3 evidence remains valid only for its own
historical invocation. This supplement establishes bounded T-P8.3 runtime evidence on
the changed currentness/provider bytes. The independent current-bytes audit is pending;
no final Epic acceptance/release claim is made here.

R-P5.M10 historical pre/post equality remains **NOT PROVEN**; original equality clause
remains **NOT EXECUTED**.
