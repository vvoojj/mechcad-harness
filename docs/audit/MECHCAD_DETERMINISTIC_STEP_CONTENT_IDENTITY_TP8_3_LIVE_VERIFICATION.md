# Deterministic STEP Content Identity - T-P8.3 Live Verification Record

## Verdict

```text
Epic:
Deterministic STEP Content Identity

Gate:
T-P8.3 live verification through the FINAL default production path

Human authorization:
H4 granted for live FreeCAD execution within the bounded T-P8.3 scope

Controlling Spec:
DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68

Controlling Plan:
291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679
(accepted revision; supersedes E449C60B641DBB5A4A630CC61553F5E586127443DC92B24BD5D983E3A15BB70E)

Observed HEAD:
05da8edad18488492f02be1dad9d1ec3653ce807

Disposition:
LIVE_VERIFIED (bounded scenario)
```

## Runtime Boundary (real executable, not a mock)

```text
Executable:     C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe
Version:        FreeCAD 1.1.3 (Revision 20260725)
Library name:   FreeCAD
Execution mode: freecadcmd-subprocess
Provider:       freecad-transient-exact
Importable:     False (the FreeCAD Python module is NOT importable in the
                test process; the backend uses a real freecadcmd subprocess)
Env:            MECHCAD_FREECADCMD set to the executable above
```

A dedicated test asserts this real subprocess boundary; mocks/importability are
not credited as live proof.

## New Test File

```text
tests/integration/test_step_content_identity_live.py

test_live_runtime_is_real_freecad_subprocess_boundary
test_live_repeated_exports_raw_differs_content_identity_equal
test_live_downstream_semantic_identities_equal_under_timestamp_rotation
test_live_mini_rev3_replay_through_final_default_emits_at2_family
test_live_fresh_process_restart_recomputes_live_step_identities
test_live_real_engineering_change_changes_semantic_identity
```

## Exact Command and Result

```text
$env:MECHCAD_FREECADCMD = "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"
python -m pytest tests/integration/test_step_content_identity_live.py -v

6 passed, 0 failed, 0 skipped, 0 timeout in 31.30s
```

Counts are evidence only for the exact invocation that produced them.

## (a) Raw-Different / Content-Same Under Timestamp-Only Variation

Two real `FreeCADBackend.generate_program` exports of the same 30x30x5 plate,
`FILE_NAME` timestamps `2026-10-01T07:44:29` (A) and `2026-10-01T07:44:35` (B).

| Identity | A | B | Relation |
|---|---|---|---|
| raw SHA-256 of stored bytes | `sha256:6652ef57…6aefec` | `sha256:3aa0b927…91e08b` | **DIFFERS** |
| `step-content-identity@1` | `sha256:450e4471…32b44d` | same | **EQUAL** |
| `semantic_reference_hash` | `sha256:940b263d…3291a9` | same | **EQUAL** |
| `candidate-synthesis-request@2.request_hash` | `sha256:330d71e1…c8ae76f` | same | **EQUAL** |
| `semantic_source_binding_hash` | `sha256:7e698f18…cabd6a7` | same | **EQUAL** |
| `component-specification@4` hashes (6) | sorted set | same | **EQUAL** |
| `mechanical-design-candidate@2.candidate_hash` | `sha256:de91aefd…b421c92` | same | **EQUAL** |
| `revolute-drive-admissibility@2.result_hash` | `sha256:7c0fe546…3164ad8` | same | **EQUAL** |
| raw provenance (artifact id / run id / raw hash) | `ART-LIVE-A-*` / `LIVE-A` / `sha256:282a6563…` | `ART-LIVE-B-*` / `LIVE-B` / `sha256:a0b55418…` | **DIFFERS** |

The reachable path is the FINAL default
`ProductionApplication.realize_and_evaluate_revolute_drive` (single-joint,
`candidate-synthesis-request@2`). The `@2` CAD realization/mapping identities
are not reachable on this activated default because `realize_candidate_cad` /
`evaluate_candidate` remain reject-only for the `@2` family (staged owner
phases); this boundary is documented in the test module rather than bypassed.

## (b) Fresh MINI Rev3 Replay Through the FINAL Default

Isolated workspace: `.tmp-live-m12/tp8_3_mini_replay/` (outside `projects/`).
Built from accepted M12 direct-drive engineering authority plus a real FreeCAD
STEP artifact. Emitted `candidate-synthesis-request@2` →
`mechanical-design-candidate@2` → `revolute-drive-admissibility@2`
(`status=admissible`). Historical `projects/mini_rotary_fixture/**` and all
accepted audit/reconstruction records were not read or mutated (not present in
`git status`).

## (c) Fresh-Process Restart on Live Artifacts

A real separate Python interpreter (`subprocess` + `sys.executable`) loaded the
live artifacts from `ArtifactStore`, rehashed raw bytes, recomputed
`step-content-identity@1`, recomputed the semantic source binding, and
re-verified the persisted candidate@2. Child pid `6400` != parent pid `4388`,
rc=0. All recomputed values matched the persisted ones (raw SHA, content
identity, `semantic_source_binding_hash`, `request_hash`, `candidate_hash`, the
six component-specification@4 hashes, and the semantic reference hashes).

## (d) Real Engineering Change DIFFERS

- Different real geometry (40x25x6 vs 30x30x5): content identity
  `sha256:236f8cda…` != A; candidate `sha256:7f1fbcf2…` != A; result
  `sha256:7565d6bf…` != A.
- Changed real supplied shaft specification (diameter 14.0 vs 12.0, same
  geometry): content identity **unchanged**, request hash unchanged, but the
  specification hashes, candidate `sha256:260fe97c…`, and result
  `sha256:47042ea5…` all differ.

## Boundaries and Protected Surfaces

- No Gmsh, no CalculiX, no solver/mesh execution, no M11 structural analysis.
- `src/mechcad_harness/multi_joint_kinematics.py` = `514340c2…` (pinned, match).
- `src/mechcad_harness/multi_joint_collision_sweep.py` = `56e55b66…` (pinned, match).
- `tests/unit/test_m13_3_legacy_goldens.py` and `projects/mini_rotary_fixture/**`
  unmodified; no accepted audit/reconstruction record modified.
- No production code, Spec, or Plan modified by T-P8.3; no commit/push/release.

## Boundary

This record claims `LIVE_VERIFIED` for the bounded T-P8.3 scenario only. It does
not claim whole-configuration-space certification, manufacturing truth, M11
structural execution, or final implementation acceptance.

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_3_LIVE_VERIFIED

## Fresh run under accepted Plan 291B39B0 (2026-10-03)

Re-executed live under the accepted revised Plan after the live-stage fixture
remediation of `tests/integration/test_m12_candidate_cad_m10_production.py`
(`_build_gear_application` / `_build_live_application` now append the eight
accepted geometry identities and publish the `ART-{slot}` source artifacts, mirroring
`build_application`).

```text
$env:MECHCAD_FREECADCMD = "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"
python -m pytest tests/integration/test_step_content_identity_live.py -v --tb=short -p no:randomly

platform win32 -- Python 3.14.6, pytest-8.4.2
6 passed in 28.68s
```

FreeCAD 1.1.3 (Revision 20260725) confirmed via `FreeCADCmd.exe --version`.
No Gmsh, no CalculiX, no solver/mesh, no M11 structural analysis.
Isolated workspace `.tmp-live-m12/tp8_3_mini_replay/` (outside `projects/`).
No production code, Spec, or Plan modified by the live run; no commit/push/release.
