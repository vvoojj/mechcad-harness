# Deterministic STEP Content Identity — Complete P5 / Complete P7 Phase-Gate Closure Evidence

## Status

```text
Complete P5 phase gate: GREEN (fresh evidence)
Complete P7 phase gate: GREEN (fresh evidence)
P8-R0V / P8.1 / P8.2: NOT yet run
Independent predecessor audit: PENDING
```

This is fresh execution evidence for the Plan's complete-P5 and complete-P7 phase gates. It does not by itself declare milestone acceptance.

## Authority

- Accepted Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Code HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807`.
- RP5/RP6/RP7 implementation-evidence acceptance: `docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_RP6_RP7_IMPLEMENTATION_INDEPENDENT_ACCEPTANCE.md`.
- Historical R-P5.M10 equality remains **NOT PROVEN**; original clause **NOT EXECUTED**.

## Complete P5 Gate (Plan line 449)

Required elements and fresh evidence:

| Element | Command (abbrev.) | Result |
|---|---|---|
| R-P5.M10 GREEN | accepted replacement-verification record | accepted |
| R-P5.5 complete | accepted RP5/RP6/RP7 record | accepted |
| R-P5.6 GREEN | accepted RP5/RP6/RP7 record | accepted |
| P5.1 focused | `test_m10_semantic_projections`, `test_multi_joint_kinematics`, `test_multi_joint_collision_sweep`, `test_kinematic_sweep` | part of 443 passed |
| P5.2 focused | `test_candidate_m10_v2`, `test_m12_candidate_m10_binding/service/replay` | 65 passed (prior fresh) |
| P5.3 positive path | `test_candidate_multijoint_m10_v2` | part of 443 passed |
| P4 canonical | `test_canonical_mechanism_v4`, `test_canonical_cad_mapping_v2`, `test_canonical_cad_realization_v2`, `test_m12_canonical_reconstruction`, `test_m12_canonical_physical_mechanism`, `test_m13_3_canonical_mechanism_v3`, `test_m12_canonical_cad`, `test_m13_2_promotion_canonical_roundtrip` | 240 passed (prior fresh) |
| P1–P6 focused + transitive-closure audit | `test_step_content_identity*`, `test_semantic_geometry_reference`, `test_semantic_source_binding`, `test_semantic_m13_projections`, `test_semantic_component_candidate`, `test_candidate_trusted_semantic_verification`, `test_candidate_synthesis_request_v2`, `test_candidate_cad_mapping_v2`, `test_candidate_cad_request_v3`, `test_candidate_cad_realization_v2`, `test_candidate_cad_provenance_per_slot_v2`, `test_canonical_*`, P5 focused, `test_semantic_family_closure` | **443 passed** |
| single-joint + multi-joint legacy M10 suites | `test_m13_3_candidate_request`, `test_m13_3_candidate_evaluation`, `test_m13_3_multi_joint_selection`, `test_m13_3_pair_inventory`, `test_m13_3_fresh_canonical_m10`, `test_m13_3_fresh_canonical_bridge`, `test_m13_3_bridge_compiler`, `test_m13_3p_legacy_goldens`, `test_m13_3_legacy_goldens`, `test_m13_3p_rigid_body_groups` | **220 passed** |

Transitive-closure audit (no terminal raw/evaluator/legacy hash) is covered by `test_semantic_family_closure.py` (within the 443) plus `test_m10_semantic_projections.py`.

## Complete P7 Gate (Plan line 511)

| Element | Command (abbrev.) | Result |
|---|---|---|
| P6 green | accepted RP5/RP6/RP7 record + 240 canonical | green |
| T-P7.1 decision focused | `test_candidate_decision_v2` | part of 145 passed |
| T-P7.2 promotion focused | `test_promotion_v2`, `test_candidate_multi_joint_m10_provenance_v1` | part of 145 passed |
| T-P7.3 M11 focused | `test_m11_handoff_v2` | part of 145 passed |
| legacy decision suites | `test_m12_candidate_evaluation`, `test_m12_candidate_comparison`, `test_m12_candidate_selection`, `test_m12_m11_handoff` | **145 passed total** |
| legacy promotion suites | `test_m12_promotion_models`, `test_m12_promotion_compiler`, `test_m12_promotion_apply`, `test_m12_promotion_replay`, `test_m13_4e_legacy_promotion_goldens`, `test_m12_promotion_projection`, `test_m12_promotion_provenance` | **85 passed** |
| readiness counts 19/20 | asserted in `test_promotion_v2.py` | pass |
| `@3`-admission vs wire-read | asserted in `test_canonical_cad_mapping_v2.py` | pass |

## Protected Bytes

| File | SHA-256 | Result |
|---|---|---|
| `multi_joint_kinematics.py` | `514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f` | MATCH |
| `multi_joint_collision_sweep.py` | `56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f` | MATCH |
| `test_m13_3_legacy_goldens.py` | `7dc391f10e545fc3291669a894a3c2a10729672eba9e847c1dca4dd88c8d5ba4` | MATCH |
| `multi_joint_pair_scope.py` | `b593e0aa41b50a0dbc84c050f2396e0dba63b621fdd48cf3a7e185120706d344` | MATCH |
| `multi_joint_continuous_path.py` | `c063ca8269392b68b911492f72071bdd5f7de30acd4461c98cad045a5574fa9b` | MATCH |
| `multi_joint_continuous_clearance.py` | `66a62f30a7fe96c40f6cb049bf96906a427931b276ce9847dad42e6f95ad2bc5` | MATCH |

## Notes

- Fresh commands executed after the RP5/RP6/RP7 acceptance: 145 + 85 + 220 + 443 = 893 tests passed.
- These are fresh invocations, not carried-forward counts.
- The four README-doc failures and the two live FreeCAD/gear integration failures are outside this phase-gate scope and are recorded in the RP5/RP6/RP7 evidence record; the live failures are NOT proven pre-existing at HEAD.
