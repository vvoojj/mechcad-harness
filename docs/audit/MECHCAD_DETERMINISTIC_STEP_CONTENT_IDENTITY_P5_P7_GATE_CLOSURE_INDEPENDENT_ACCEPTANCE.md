# Deterministic STEP Content Identity — Complete P5 / Complete P7 Phase-Gate Closure — Independent Predecessor Acceptance

## Verdict

```text
Target evidence record:
  docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_P5_P7_GATE_CLOSURE_EVIDENCE.md
  (SHA-256 a2e8da238acf184a0870c6ab354e2c0f4c7fbefd5d57e5ab4cc61933083dbdb8)

Accepted Plan SHA-256:
  291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679

Accepted Spec SHA-256:
  DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68

Code HEAD:
  05da8edad18488492f02be1dad9d1ec3653ce807

Disposition:
  INDEPENDENTLY_ACCEPTED — PHASE-GATE PREDECESSOR ONLY

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_P5_P7_GATE_CLOSURE_INDEPENDENTLY_ACCEPTED
```

This record independently accepts the **complete-P5 and complete-P7 phase-gate
closure evidence only** for the exact bytes identified below. It is a
**predecessor acceptance**: it does **not** declare default activation, live
verification, release/commit authorization, or acceptance of any later phase.
The historical R-P5.M10 pre/post-relocation projection-output equality remains
**NOT PROVEN**; the original before/after equality clause remains **NOT
EXECUTED**.

## Scope and Authority Boundary

- The accepted Plan is `docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md`
  at SHA-256 `291b39b0daf33dd3d55937d8062ecce70f4e2fed511c3c611d56a3e98a5d6679`.
  Its complete-P5 gate is line 449 and its complete-P7 gate is line 511; the
  P5/P6/P7 phase definitions are lines 416–513.
- The accepted Spec is `docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md`
  at SHA-256 `de17c360f09a9c9cb9a8a01118789b41ad4f1366a23ad728bfa3a9b19e2b1b68`.
- Prior independent acceptances relied upon (implementation/evidence only):
  - R-P5.M10 replacement verification:
    `docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_M10_REPLACEMENT_VERIFICATION_INDEPENDENT_ACCEPTANCE.md`
    (prospective verification only; historical equality NOT PROVEN).
  - R-P5.5 / R-P5.6 representative subset / P6 canonical bridge / T-P7.2:
    `docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_RP6_RP7_IMPLEMENTATION_INDEPENDENT_ACCEPTANCE.md`.
  Neither prior record declares complete P5 or complete P7. This record closes
  the two phase gates at the level of predecessor acceptance only.

## Exact-Byte Checks (check 2)

Independently recomputed SHA-256 values from the working tree:

| Artifact | Recomputed SHA-256 | Result |
|---|---|---|
| Accepted Plan | `291b39b0daf33dd3d55937d8062ecce70f4e2fed511c3c611d56a3e98a5d6679` | MATCH |
| Accepted Spec | `de17c360f09a9c9cb9a8a01118789b41ad4f1366a23ad728bfa3a9b19e2b1b68` | MATCH |
| Target evidence record | `a2e8da238acf184a0870c6ab354e2c0f4c7fbefd5d57e5ab4cc61933083dbdb8` | MATCH (recomputed here) |
| `src/mechcad_harness/candidates/multi_joint_m10_bridge.py` | `d943dfd253b4f372d51fe83aa4850ec5faee6d67ef0d430f6a977ee963b112b8` | MATCH |
| `src/mechcad_harness/candidates/canonical_cad.py` | `8802647e4e3d624698e9bb3ee950d1003669968f01ba922048a1e61a6251ecfd` | MATCH |
| `tests/integration/test_m12_promotion_production.py` | `c47376302b940acdb4da6bdcd5ffbe5ba19dbe2b580a4d945d02ffd5a2a63fdb` | MATCH |
| `src/mechcad_harness/semantic_m10_kinematics.py` | `5e75da171c0d4c923761a07cf9b68609b85244d0badf3bc528371a418673d5e7` | MATCH |
| `tests/unit/test_rp5_m10_projection_vectors.py` | `499dd924fc34d0c0d8e017125236777e47b65ed4a80bfd6b42dd109a6deb833a` | MATCH |

Protected bytes named in the evidence record (all MATCH):

| Protected file | Required SHA-256 | Recomputed | Result |
|---|---|---|---|
| `src/mechcad_harness/multi_joint_kinematics.py` | `514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f` | same | MATCH (clean) |
| `src/mechcad_harness/multi_joint_collision_sweep.py` | `56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f` | same | MATCH (clean) |
| `tests/unit/test_m13_3_legacy_goldens.py` | `7dc391f10e545fc3291669a894a3c2a10729672eba9e847c1dca4dd88c8d5ba4` | same | MATCH (clean) |
| `src/mechcad_harness/multi_joint_pair_scope.py` | `b593e0aa41b50a0dbc84c050f2396e0dba63b621fdd48cf3a7e185120706d344` | same | MATCH (clean) |
| `src/mechcad_harness/multi_joint_continuous_path.py` | `c063ca8269392b68b911492f72071bdd5f7de30acd4461c98cad045a5574fa9b` | same | MATCH (clean) |
| `src/mechcad_harness/multi_joint_continuous_clearance.py` | `66a62f30a7fe96c40f6cb049bf96906a427931b276ce9847dad42e6f95ad2bc5` | same | MATCH (clean) |

`git status --porcelain` reports `multi_joint_m10_bridge.py`,
`canonical_cad.py`, and `test_m12_promotion_production.py` as modified relative
to HEAD (as reported), and `semantic_m10_kinematics.py` /
`test_rp5_m10_projection_vectors.py` as untracked; the six protected files above
are clean/unchanged from HEAD. Checkout HEAD is
`05da8edad18488492f02be1dad9d1ec3653ce807`, matching the reported code HEAD.

## Fresh Verification Subset (check 3)

Ordinary local unit tests only; no FreeCAD/Gmsh/CalculiX/live runtime was
invoked. Environment: `.venv\Scripts\python.exe` (Python 3.14.6, pytest 9.1.1).

```text
python -m pytest -q tests/unit/test_semantic_family_closure.py \
  tests/unit/test_candidate_multijoint_m10_v2.py \
  tests/unit/test_candidate_decision_v2.py \
  tests/unit/test_promotion_v2.py \
  tests/unit/test_m11_handoff_v2.py \
  tests/unit/test_m13_3_legacy_goldens.py
190 passed in 166.66s (0:02:46)
```

Per-file collected counts (collect-only, corroborating the 190):

| File | Tests |
|---|---|
| `test_semantic_family_closure.py` | 132 |
| `test_candidate_multijoint_m10_v2.py` | 8 |
| `test_candidate_decision_v2.py` | 18 |
| `test_promotion_v2.py` | 12 |
| `test_m11_handoff_v2.py` | 17 |
| `test_m13_3_legacy_goldens.py` | 3 |
| **Total** | **190** |

## Corroborated Recorded Counts

Collect-only recounts of the evidence record's named batches (no execution
beyond the fresh subset above):

| Recorded batch | Files named | Recorded | Recomputed | Result |
|---|---|---|---|---|
| P5.2 focused | `test_candidate_m10_v2` + `test_m12_candidate_m10_binding/service/replay` | 65 | 65 | MATCH |
| P5 single-/multi-joint legacy M10 | 10 named `test_m13_3*` files | 220 | 220 | MATCH |
| P7 decision batch (focused + legacy) | `test_candidate_decision_v2` + `test_promotion_v2` + `test_m11_handoff_v2` + `test_m12_candidate_evaluation/comparison/selection/m11_handoff` | 145 | 145 | MATCH |
| P7 legacy promotion | 7 named `test_m12_promotion_*` / `test_m13_4e_legacy_promotion_goldens` files | 85 | 85 | MATCH |
| Canonical / P6 batch | 14 named canonical/P6 files (incl. `test_canonical_m10_scope_v2`, `test_canonical_m10_v2`) | 240 | 240 | MATCH |
| P4 row's named 8 files (see caveat C1) | 8 canonical files | 240 (as recorded) | **152** | DISCREPANCY (labeling; see C1) |

The `443`-test P1–P6 focused + transitive-closure batch is recorded only as an
abbreviated command list (line 35) and cannot be reconstructed byte-exactly; it
is not independently recounted here. The directly named members relevant to
P5.1/P5.3 (`test_m10_semantic_projections`, the protected M10 suites,
`test_candidate_multijoint_m10_v2`, `test_semantic_family_closure`) were
exercised in the fresh subset above and/or the corroborated batches.

## Complete-P5 Gate Element Coverage (Plan line 449)

| Plan element | Evidence in record | Independent finding |
|---|---|---|
| P5-R0 work preserved/reconciled | R-P5.M10 + R-P5.5/R-P5.6 rows; prior acceptances | COVERED (preserved R-P5.1–R-P5.4 accepted; see C2 on §0) |
| `R-P5.M10` GREEN | accepted replacement-verification record | COVERED (prospective acceptance; historical equality NOT PROVEN) |
| R-P5.5 complete | accepted RP5/RP6/RP7 record | COVERED |
| R-P5.6 GREEN | accepted RP5/RP6/RP7 record | COVERED (representative non-live subset) |
| P5.3 positive-path suite | `test_candidate_multijoint_m10_v2` (fresh 8 passed) | COVERED |
| P4 green | 240 canonical batch (includes P4 suites) | COVERED (see C1) |
| P1–P6 + N1/MJ focused | 443 batch | COVERED (abbrev.; not byte-recounted) |
| single-joint + multi-joint legacy M10 | 220 batch (recomputed 220) | COVERED |
| transitive-closure audit | `test_semantic_family_closure` (fresh 132 passed) + `test_m10_semantic_projections` | COVERED |
| dirty-worktree reconciliation (§0) | not separately enumerated | SATISFIED-IN-OUTCOME (see C2) |

## Complete-P7 Gate Element Coverage (Plan line 511)

| Plan element | Evidence in record | Independent finding |
|---|---|---|
| P6 green | accepted RP5/RP6/RP7 record + 240 canonical (recomputed 240) | COVERED |
| decision/promotion/M11 focused | `test_candidate_decision_v2` (18), `test_promotion_v2` (12), `test_candidate_multi_joint_m10_provenance_v1` (7), `test_m11_handoff_v2` (17) | COVERED |
| legacy decision/promotion/handoff | 145 decision batch (recomputed 145) + 85 promotion batch (recomputed 85) | COVERED |
| readiness counts 19/20 asserted | `test_promotion_v2.py:84-97` (`PromotionReadinessV2` 19, `MultiJointPromotionReadinessV2` 20) | COVERED |
| `@3`-admission vs wire-read | `test_canonical_cad_mapping_v2.py` admission/override-fail-closed tests | COVERED |
| dirty-worktree reconciliation (§0) | not separately enumerated | SATISFIED-IN-OUTCOME (see C2) |

## Subphase Status Table (check 4)

`PC` = production-composed (activated in the default production composition).
Default remains LEGACY; activation is T-P8.4a, which has not run, so every
new-family subphase is **not** production-composed.

| Subphase | IMPLEMENTED | TESTED | PRODUCTION_COMPOSED | INDEPENDENTLY_ACCEPTED |
|---|---|---|---|---|
| P5.1 | YES (owner `semantic_m10_kinematics.py`, byte-pinned) | YES (projections/protected suites; 103 prior; part of 443) | NO | YES (R-P5.M10 replacement verification, prospective) |
| P5.2 | YES | YES (`test_candidate_m10_v2` + `m12_candidate_m10_*`; 65) | NO | NO (covered by this closure; not named in a prior acceptance) |
| P5.3 | YES | YES (`test_candidate_multijoint_m10_v2`; fresh 8; legacy 36/220) | NO | YES (R-P5.5 acceptance re-ran the positive path) |
| R-P5.M10 | YES (four functions relocated; protected bytes restored) | YES (135 focused; vector test 4 pins) | NO | YES (historical equality NOT PROVEN) |
| R-P5.5 | YES (candidate-track rebind) | YES (36/44) | NO | YES |
| R-P5.6 | YES | YES (full step table + representative subset) | NO | YES (representative non-live subset) |
| P6 | YES (canonical M10 `@2` N2 family + canonical bridge) | YES (240 canonical; N2 suites included) | NO | YES (canonical bridge accepted; N2 family covered by 240) |
| T-P7.1 | YES | YES (18; fresh) | NO | NO (covered by this closure) |
| T-P7.2 | YES (promotion `@2` + MJ provenance `@1`) | YES (12+7; 85) | NO | YES |
| T-P7.3 | YES | YES (17; fresh) | NO | NO (covered by this closure) |

No subphase has changed bytes relative to its accepted implementation bytes; no
subphase evidence is missing.

## P8-R0V Prerequisites (check 5)

- Complete P5: **accepted** by this record.
- P6: **accepted** (canonical bridge + N2 family via the 240 batch).
- Complete P7: **accepted** by this record.
- `R-P5.M10` relocation: independently accepted (prospective); historical
  pre/post equality remains **NOT PROVEN**.

No accepted Plan gate was found skipped or weakened: legacy `@1` surfaces remain
frozen; protected source/golden bytes are unchanged; the default remains LEGACY;
the R-P5.M10 NOT PROVEN / NOT EXECUTED boundary is preserved and not upgraded.
P8-R0V itself, P8.1, and P8.2 remain **NOT run**.

## Caveats (documentation precision; non-substantive)

- **C1 — P4 row command/result labeling.** The Complete-P5 table's P4 row names
  an 8-file command that collects **152** tests, but reports `240 passed`. The
  `240` value belongs to the 14-file canonical/P6 batch (independently
  recomputed at 240, which includes the P4 canonical suites). The P4 gate is
  therefore evidenced; the row's command column is under-specified. This is a
  labeling inaccuracy, not a false test result.
- **C2 — §0 reconciliation not separately enumerated.** The Plan's
  dirty-worktree reconciliation rule (§0) is a process gate repeated per phase.
  The evidence record does not carry an explicit §0 row. Its outcome is
  independently observable: the named target files match their accepted bytes,
  and the unrelated concurrent dirty worktree remains present (not clobbered).
- **C3 — 443 batch not byte-recounted.** Recorded only as an abbreviated command
  list; not reconstructed exactly here. Its P5-relevant members were exercised
  in the fresh subset and corroborated batches.

## Gate Status

- Complete P5 phase gate: **INDEPENDENTLY ACCEPTED (predecessor only)**.
- Complete P7 phase gate: **INDEPENDENTLY ACCEPTED (predecessor only)**.
- Historical R-P5.M10 equality: **NOT PROVEN**; original clause **NOT EXECUTED**.
- This record does **not** declare default activation, live verification,
  P8-R0V/P8.1/P8.2 completion, release authorization, or commit authorization.
- No production code, test, Plan, Spec, reconstruction, or existing audit was
  modified. Only this acceptance record was created. No commit or push was made.
