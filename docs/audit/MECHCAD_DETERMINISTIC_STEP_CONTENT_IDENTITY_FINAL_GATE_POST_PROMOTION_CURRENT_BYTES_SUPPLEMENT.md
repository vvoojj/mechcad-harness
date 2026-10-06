# Deterministic STEP Content Identity — Post-Promotion Current-Bytes Gate Supplement

## Authority and scope

- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Controlling Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- Observed HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807` (worktree changes uncommitted).
- This is additive evidence for the later current-byte state. It does not rewrite earlier test, audit, or historical records.
- No commit, push, tag, release, or history rewrite was performed.

The existing `MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_EPIC_INDEPENDENT_ACCEPTANCE.md`
is scoped to a different Plan SHA (`E449C60B…`). Its verdict is preserved as historical
evidence and is not reused as acceptance for the current controlling Plan bytes.

## Exact current file hashes

```text
docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md
  DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68
docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md
  291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679
src/mechcad_harness/candidates/services.py
  6D33640FCFFED213FB1F71C1A7B30091AB79AEB76B3D3037C2DA5F8D8C8D02B3
src/mechcad_harness/backends/gearworks_cad.py
  F67ECB7787D9C421A68F0F6465CB88606BFBDC3A75D5F2640434314AE2C75321
src/mechcad_harness/candidates/provenance_artifacts.py
  F3E8C8379F21C57692101D6F1079C78CDFD8885BB266121EC6B4DD7434144D42
tests/integration/test_m12_candidate_cad_m10_production.py
  4A3C2D7F9DB10602AE1EE3722BFD4F08C6B7DAF2208178A7F6B48EEE117D3F7B
tests/integration/test_m12_promotion_production.py
  5D51401075EAC542F6E35FB7760178E3D10AF6D43A7036F6E376FDD09C8BBB02
tests/unit/test_candidate_provenance_artifacts.py
  379A3DA84BD3878B5B26D208FE9DB2183E3834EA5DF79BB32B4268E81A2A7116
```

All six protected implementation/test pins were previously verified against their
accepted values; none of those files was edited in this continuation.

## Promotion-family remediation

The accepted Plan identifies `test_m12_promotion_production.py` as legacy production
path coverage that must remain unchanged in family semantics. The previous exploratory
fixtures paired candidate/evaluation/selection@2 with M12-5 promotion@1; moving the
promotion request to @2 instead failed at the explicit `realization@2 M13 authority`
requirement. The current M12-5 integration fixtures now construct explicit
candidate-synthesis-request@1 / candidate@1 / promotion@1 chains through the existing
legacy replay service. Source-backed motor, shaft, bearing, hub, support-mount, and gear
components retain their published STEP geometry. Mount/body retain the existing
source-free bounded specifications. No geometry or M13 authority was fabricated.

The promotion runs also exposed a typed-wrapper round-trip defect: canonical CAD and
canonical M10 provenance publication validators accepted typed payload models but not
their serialized dictionary representation, although production promotion verification
reparses those wrappers. Both validators now dispatch on the nested `schema_version`
whether the payload is a model or dictionary. Two focused tests require canonical CAD
and canonical M10 publication wrappers to survive this typed reparse.

## Verification on these bytes

```text
py -3 -m pytest tests/integration/test_m12_promotion_production.py -q
25 passed, 23 warnings in 1222.71s

py -3 -m pytest tests/integration/test_m12_candidate_cad_m10_production.py -q
21 passed, 21 warnings in 457.98s

py -3 -m pytest tests/unit/test_candidate_provenance_artifacts.py tests/unit/test_m12_promoted_verification.py tests/unit/test_promotion_v2.py -q --tb=short -p no:randomly
186 passed in 362.42s

py -3 -m pytest tests/unit/test_candidate_trusted_semantic_verification.py tests/unit/test_candidate_production_admission_matrix.py tests/unit/test_candidate_cad_request_v3.py tests/unit/test_candidate_comparison_selection_provenance_v2.py tests/unit/test_candidate_decision_v2.py tests/unit/test_currentness_exact_source_supplementation.py -q --tb=short -p no:randomly
71 passed in 172.35s
```

Five authorized candidate-CAD live targets, using FreeCAD 1.1.3 through its bundled
command-line subprocess, were rerun together:

```text
$env:MECHCAD_FREECADCMD = "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"
py -3 -m pytest \
  tests/integration/test_m12_candidate_cad_m10_production.py::test_explicit_bounded_collision_fixture_is_candidate_bound_not_trusted_fallback \
  tests/integration/test_m12_candidate_cad_m10_production.py::test_live_direct_drive_clear_collision_and_not_proven_chain \
  tests/integration/test_m12_candidate_cad_m10_production.py::test_live_comparison_and_selection_are_deterministic_and_noncanonical \
  tests/integration/test_m12_candidate_cad_m10_production.py::test_candidate_realization_rejects_unavailable_trusted_external_spur_artifact_without_downgrade \
  tests/integration/test_m12_candidate_cad_m10_production.py::test_live_external_spur_preserves_unmodeled_internal_motion_boundary \
  -v --tb=short -p no:randomly
5 passed, 5 warnings in 442.59s
```

T-P8.3 was rerun after the final production edits:

```text
$env:MECHCAD_FREECADCMD = "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"
py -3 -m pytest tests/integration/test_step_content_identity_live.py -v --tb=short -p no:randomly
6 passed in 42.12s
```

Focused M12-5 promotion live cases were also exercised within the full 25-test promotion
integration invocation. The direct-drive cases and external-spur cases passed on the
legacy family. No Gmsh, CalculiX, mesh/solver, or structural analysis was run.

Static checks on changed paths:

```text
py -3 -m compileall -q src/mechcad_harness tests/integration/test_m12_candidate_cad_m10_production.py tests/integration/test_m12_promotion_production.py tests/unit/test_candidate_provenance_artifacts.py
passed
git diff --check -- src/mechcad_harness/candidates/provenance_artifacts.py tests/integration/test_m12_candidate_cad_m10_production.py tests/integration/test_m12_promotion_production.py tests/unit/test_candidate_provenance_artifacts.py
passed
```

## Verification attempts that timed out

The following invocations are retained as failed/aborted evidence even though a later
full invocation completed:

- `py -3 -m pytest tests/integration/test_m12_promotion_production.py -q` — harness
  timeout at 1200 seconds; 21 progress dots, no final summary.
- `py -3 -m pytest tests/integration/test_m12_promotion_production.py -q -k "not live_"`
  — harness timeout at 600 seconds; 15 progress dots, no final summary.
- `py -3 -m pytest tests/integration/test_m12_promotion_production.py -vv -k "not live_"`
  — harness timeout at 600 seconds after 17 selected cases passed, while
  `test_promotion_v2_typed_restart_rejects_missing_comparison_parent` was in progress.
- The isolated case then passed (**1 passed in 139.97s**), and the subsequent full
  promotion invocation passed all 25 cases (**1222.71s**).

The Pydantic serializer warnings in the integration outputs report
`GeometrySourceReference` model instances in the fixture's `yagi_payload_carrier_requirements`
dict list. They were not suppressed or claimed clean. A repository-global `git diff
--check` also reported trailing whitespace in unrelated modified
`.superpowers/sdd/progress.md` lines 60–61 and 87–92; the changed-path scoped check above
was clean and that file was not edited here.

## Remaining evidence boundaries

- The prior broad P8.2 invocation recorded its two exact excluded test failures in its
  own evidence; this supplement does not relabel those results.
- R-P5.M10 pre/post equality remains **NOT PROVEN** and the original equality clause
  remains **NOT EXECUTED**.
- This supplement claims no independent acceptance. A fresh independent remediation
  audit and a separate final Epic audit of the exact hashes above remain required.
