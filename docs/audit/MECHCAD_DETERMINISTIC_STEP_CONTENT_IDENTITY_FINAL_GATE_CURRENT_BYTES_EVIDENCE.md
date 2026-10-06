# Deterministic STEP Content Identity — Final-Gate Current-Bytes Evidence

## Authority and disposition

- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Accepted revised Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- Code HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807` (worktree changes uncommitted).
- This supplements, and does not rewrite, the historical T-P8.3 run record.
- No commit, push, tag, release, or history rewrite.

## Changed bytes

```text
6d33640fcffed213fb1f71c1a7b30091ab79aeb76b3d3037c2da5f8d8c8d02b3  src/mechcad_harness/candidates/services.py
f67ecb7787d9c421a68f0f6465cb88606bfbdc3a75d5f2640434314ae2c75321  src/mechcad_harness/backends/gearworks_cad.py
8e4f09da9bda0d0405ede98f0c8a77c0977b4d0f480f7491d6e1a6b3c98a7aca  tests/integration/test_m12_candidate_cad_m10_production.py
772112daa552343a1eb173d1e5aeb6117be3b72a49e84217533f7fdd17e84436  tests/integration/test_m12_promotion_production.py
014aaacf04693c73a802265a57264ddae6d33913639e9bd9b481576705b6a938  tests/unit/test_currentness_exact_source_supplementation.py
45a262c797f0dcce69285d61e31750f5bd5216bc53828fa8e0f5dee4ce5e772a  tests/unit/test_gear_cad.py
```

`tests/integration/test_m12_promotion_production.py` was previously pinned at
`c4737630…`; its current hash differs. The prior acceptance is limited to the old test
bytes. The current fixture-byte change is included in the new independent audit scope.

## Currentness supplementation

Classification: **BEFORE = PARTIAL** (substitution only); the existing semantic-binding
owner now supplements its consumed-authority context only with identities in the
existing `candidate_cad_required_raw_source_identities(candidate)` allowlist. State
authority is processed first and cannot be overridden; raw bytes are read and verified
through the existing ArtifactStore path, with project/revision/state binding enforced.
No arbitrary exact artifact becomes a semantic binding.

Fresh focused/owner/regression counts:

```text
@3 request/mapping owner + fixture family test: 21 passed in 8.73s
currentness/trusted/synthesis/semantic family/admission/comparison/selection/provenance: 62 passed in 16.14s; 189 passed in 179.40s
candidate CAD request/mapping/realization/provenance/M10: 57 passed in 13.58s
currentness + trusted semantic + family + decision + comparison/provenance final subset: 34 passed in 54.27s
GearWorks provider + strict STEP timestamp profile: 26 passed in 46.23s
P8.1 focused P1→P7 closure/restart + currentness supplement: 427 passed in 170.96s
P8 relocation/import + protected legacy tests: 20 passed in 16.35s
```

## GearWorks provider G2 correction

`src/mechcad_harness/backends/gearworks_cad.py` now passes
`timestamp="2000-01-01T00:00:00"` directly to `build123d.export_step`. The actual
published bytes contain the accepted timestamp; no post-publication rewrite occurs.
The provider test recomputes content identity from those stored bytes, checks repeat
identity equality for identical inputs, and checks a teeth change differs. Existing
STEP tests continue to reject external `...Z` and malformed timestamps.

## Bounded/source-backed fixture split

The explicit bounded direct-drive fixture is now a separate candidate@1/request@1 built
from the existing `mount_specification()` and `body_specification()` (`component-specification@1`,
`geometry_source=None`) and their existing candidate-bound length/width/thickness design
variables. Other supplied components retain verified STEP sources and trusted mappings.
The source-backed candidate@2 family dispatches to the existing `_cad_m10_inputs_v2`
request@3/mapping@2 path, with trusted semantic identities. No production CAD validator
was changed and no existing source-backed candidate had its geometry source removed.

## Five affected live tests

Runtime: `C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe`, FreeCAD 1.1.3 Revision
20260725, real bundled command-line subprocess. Python 3.14.6 from
`C:\Users\vvooj\AppData\Local\Python\pythoncore-3.14-64\python.exe`. No Gmsh,
CalculiX, solver/mesh, or M11 structural execution.

```text
python -m pytest <the five exact test_candidate_cad_m10_production.py node IDs> -v --tb=short -p no:randomly
5 passed in 404.72s
```

The five node IDs and command were executed together on these current fixture bytes; the
full paths are recorded in the command session and supplemental live log.

## T-P8.3 on current production bytes

```text
$env:MECHCAD_FREECADCMD = "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"
python -m pytest tests/integration/test_step_content_identity_live.py -v --tb=short -p no:randomly
6 passed in 37.71s
```

The six tests prove the bounded final-default runtime boundary, raw-different/content-same
timestamp variation, downstream semantic equality, isolated Rev3 replay through the
FINAL default, fresh-process recomputation, and engineering-change identity difference.

## P8 broad regression and explicit findings

Fresh broad unit keyword command, excluding exactly two unrelated node IDs after
recording their initial failure:

```text
python -m pytest tests/unit -k "(m12 or m13 or candidate or canonical or multi_joint or structural) and not test_s4_candidate_inventory_equals_frozen_s3_physical_inventory and not test_structural_extra_and_axis_contract_are_documented" -q --tb=short -p no:randomly
2439 passed, 1 skipped, 866 deselected in 529.53s
```

The first unfiltered invocation reported 2439 passed, 1 skipped, and two failures:

- `test_rotator_v2_epic_01_candidate_cad.py::test_s4_candidate_inventory_equals_frozen_s3_physical_inventory` (fixture inventory mismatch).
- `test_section_docs.py::test_structural_extra_and_axis_contract_are_documented` (README phrase expectation).

They remain visible and are not claimed pre-existing. The explicit non-live integration
subsets passed: candidate CAD/M10 **16 passed**; promotion **21 passed**. A broader
exploratory run of `test_m12_promotion_production.py` also found four additional live
promotion failures outside the five authorized live nodes: legacy `CandidatePromotionRequest@1`
is supplied with candidate/evaluation/selection@2 in three cases, and the comparison
case’s expected candidate-B metric ordering opposes the observed current result. These
are recorded separately and not claimed as the five-test acceptance result.

`python -m compileall -q src/mechcad_harness`: passed. Scoped `git diff --check`: clean.
All six protected SHA pins match. Accepted M10/semantic implementation pins remain
unchanged; `test_m12_promotion_production.py` is the changed fixture/test byte noted above.

## Acceptance boundary

No independent current-bytes audit or final Epic acceptance is claimed in this record.
The independent remediation audit and separate final Epic audit are pending.

Historical R-P5.M10 pre/post equality remains **NOT PROVEN**; the original equality
clause remains **NOT EXECUTED**.
