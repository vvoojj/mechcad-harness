# Deterministic STEP Content Identity — P8 Non-Live Gate Evidence (P8-R0V / P8.1 / P8.2 / T-P8.4a non-live)

## Status

```text
P8-R0V (relocation persistence): GREEN
T-P8.1 (focused P1->P7 + closure/restart): GREEN
T-P8.2 (broad non-live): GREEN except out-of-scope live tests and README-doc tests
T-P8.4a coded final activation: PRESENT in worktree; non-live post-activation tests GREEN
T-P8.3 LIVE verification: NOT RUN (human gate)
```

## Authority

- Accepted Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Code HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807`.
- Complete P5/P7 predecessor closure independently accepted: `docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_P5_P7_GATE_CLOSURE_INDEPENDENT_ACCEPTANCE.md`.
- Historical R-P5.M10 equality remains **NOT PROVEN**.

## P8-R0V (Plan lines 517-520)

- `semantic_m10_kinematics.py` owns exactly the four projections; protected modules define no duplicates (AST check).
- Protected pins exact: `multi_joint_kinematics.py` `514340c2…440c4f`; `multi_joint_collision_sweep.py` `56e55b66…9706f`; `test_m13_3_legacy_goldens.py` `7dc391f1…8d5ba4`; `multi_joint_pair_scope.py` `b593e0aa…d344`; `multi_joint_continuous_path.py` `c063ca82…fa9b`; `multi_joint_continuous_clearance.py` `66a62f30…bc5`.
- Direct import/identity check: `test_rp5_m10_projection_vectors.py` + `test_m10_semantic_projections.py` + legacy goldens → **30 passed**.

## T-P8.1 (Plan lines 522-529)

Fresh focused P1→P7 set + closure + restart:

```text
pytest test_step_content_identity.py test_step_content_identity_restart_fresh_process.py \
  test_semantic_geometry_reference.py test_semantic_source_binding.py \
  test_candidate_trusted_semantic_verification.py test_semantic_m13_projections.py \
  test_semantic_component_candidate.py test_candidate_synthesis_request_v2.py \
  test_candidate_cad_mapping_v2.py test_candidate_cad_request_v3.py \
  test_candidate_cad_realization_v2.py test_candidate_cad_provenance_per_slot_v2.py \
  test_canonical_mechanism_v4.py test_canonical_cad_mapping_v2.py \
  test_canonical_cad_realization_v2.py test_m10_semantic_projections.py \
  test_candidate_m10_v2.py test_candidate_multijoint_m10_v2.py \
  test_canonical_m10_scope_v2.py test_canonical_m10_v2.py test_candidate_decision_v2.py \
  test_promotion_v2.py test_candidate_multi_joint_m10_provenance_v1.py \
  test_m11_handoff_v2.py test_semantic_family_closure.py -q -p no:randomly
416 passed in 234.85s
```

Legacy regression files (fresh): single/multi-joint legacy M10 + canonical **220 passed**; decision legacy **145 passed**; promotion legacy **85 passed**; canonical/P6 **240 passed**.

## T-P8.2 (Plan lines 531-535)

- `tests/unit -k "structural"` (excluding README-doc files): **499 passed**.
- `tests/unit -k "m12 or m13 or multi_joint or structural"`: 1718 passed (1 README-doc failure in an out-of-category file).
- Candidate/canonical/m12 candidate batches: 281 + 312 + 240 + 145 + 85 passed.
- `tests/integration/test_m12_promotion_production.py -k "not test_live"`: **21 passed**.
- `tests/integration/test_m12_candidate_cad_m10_production.py -k "not live"`: **15 passed**, 2 failures in FreeCAD/gear-backed live tests (see below).

### Out-of-scope failures

- Four README-doc content tests fail because unmodified `README.md` lacks the expected phrases (`test_agent_docs.py`, `test_section_docs.py`, `test_section_engineering_docs.py`, `test_section_warping_docs.py`). These files are outside T-P8.2's required `test_m12_*/test_m13_*/test_candidate_*/test_canonical_*/test_multi_joint_*/test_structural_*` categories.
- Two FreeCAD/gear-backed tests in `test_m12_candidate_cad_m10_production.py` fail with `consumed authority path is missing: /yagi_payload_carrier_requirements/13`. Root cause is a concurrent-work fixture gap: `_build_gear_application` and `_build_live_application` create the project from `production_state()` without appending the 8 geometry identities that `make_request` (`test_m12_revolute_drive_production.py`) now requires (`_GEOMETRY_INDEX_BASE = 13`, 8 slots → indices 13–20); `build_application` in the same module does append them. These are live tests and are NOT proven pre-existing at HEAD; they are recorded, not waived.

## T-P8.4a (Plan lines 542-548) — coded activation present

- `ProductionApplication.realize_and_evaluate_revolute_drive` requires `candidate-synthesis-request@2` (rejects `@1`), trusted-binds it, then constructs.
- `RevoluteDriveRealizationService.construct_candidate` emits `mechanical-design-candidate@2` for `request@2`.
- Non-live post-activation tests green: `test_candidate_trusted_semantic_verification.py` (19), `test_candidate_multijoint_m10_v2.py`, `test_candidate_decision_v2.py`, `test_promotion_v2.py`, `test_semantic_family_closure.py` mixed-version matrices, and the non-live production-composition integration paths.
- The two live tests above are part of this file's post-activation regression and remain unresolved pending live authorization/repair.

## Next Gate

T-P8.3 LIVE verification through the FINAL default path — explicit Plan human/live gate. Not executed.
