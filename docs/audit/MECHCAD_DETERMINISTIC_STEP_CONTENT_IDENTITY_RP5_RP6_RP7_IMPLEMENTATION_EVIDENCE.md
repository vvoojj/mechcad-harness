# Deterministic STEP Content Identity — R-P5.5/R-P5.6/P6/T-P7.2 Implementation Evidence

## Status

```text
R-P5.5 candidate-track rebind: VERIFIED
R-P5.6 predecessor gates: GREEN
P5.3 positive path + complete P5 gate: GREEN
P6 canonical @4/CAD@2 multi-joint bridge: IMPLEMENTED / GREEN
T-P7.2 promotion@2 family: IMPLEMENTED (preserved dirty worktree) / GREEN
Broad non-live gate: GREEN except pre-existing README-doc failures
Independent implementation audit: PENDING
```

This record is implementation/execution evidence under the accepted Plan revision; it is not independent acceptance.

## Authority and Historical Boundary

- Accepted Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- R-P5.M10 replacement verification: independently accepted (`docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_M10_REPLACEMENT_VERIFICATION_INDEPENDENT_ACCEPTANCE.md`), historical equality **NOT PROVEN** / original clause **NOT EXECUTED**.
- Code HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807`.

## Changed Files (this session)

| File | SHA-256 | Role |
|---|---|---|
| `src/mechcad_harness/candidates/multi_joint_m10_bridge.py` | `d943dfd253b4f372d51fe83aa4850ec5faee6d67ef0d430f6a977ee963b112b8` | canonical mechanism@4/CAD@2 bridge@2 lowering + verification |
| `src/mechcad_harness/candidates/canonical_cad.py` | `8802647e4e3d624698e9bb3ee950d1003669968f01ba922048a1e61a6251ecfd` | `_compile_generated` reused as classmethod for canonical verification |
| `tests/integration/test_m12_promotion_production.py` | `c47376302b940acdb4da6bdcd5ffbe5ba19dbe2b580a4d945d02ffd5a2a63fdb` | canonical bridge@2 + verification regression |

`src/mechcad_harness/semantic_m10_kinematics.py` (`5e75da171c0d4c923761a07cf9b68609b85244d0badf3bc528371a418673d5e7`) and the R-P5.M10 vector test (`499dd924fc34d0c0d8e017125236777e47b65ed4a80bfd6b42dd109a6deb833a`) are unchanged.

## R-P5.5 — Candidate-Track Rebind (current bytes)

- `_derive_candidate_multi_joint_bridge_v2` sets `physical_mechanism_hash = semantic_candidate_mechanism_hash(realization)` and passes it into inventory@2 + bridge@2.
- `_build_request_v2` verifies `bridge.physical_mechanism_hash == semantic_candidate_mechanism_hash(candidate.realization)`.
- `_validate_chain_v2` @2 branches compare `request.physical_mechanism_hash` to `semantic_candidate_mechanism_hash(realization)`.
- Raw `realization_hash` and M13 axis/reference raw hashes do not verify on the candidate@2 track; canonical `compile_canonical` keeps the canonical mechanism identity.
- `project_id` is INCLUDED in the MJ request@2/evaluation@2/selection@2 digests (no `@3`).

Fresh results: `tests/unit/test_candidate_multijoint_m10_v2.py` 8 passed; `tests/unit/test_m13_3_candidate_request.py`, `test_m13_3_candidate_evaluation.py`, `test_m13_3_multi_joint_selection.py`, `test_m13_3_pair_inventory.py` 36 passed.

## R-P5.6 — Ordered Predecessor Gates (fresh)

| Step | Command (abbrev.) | Result |
|---|---|---|
| candidate-owner | `test_semantic_component_candidate.py` | 11 passed |
| trusted binding | `test_candidate_trusted_semantic_verification.py` | 19 passed |
| candidate CAD | `test_candidate_cad_mapping_v2/request_v3/realization_v2` | 32 passed |
| T-P3.4 per-slot | `test_candidate_cad_provenance_per_slot_v2.py` | 13 passed |
| CAD legacy | `test_m12_candidate_cad_models/_replay`, `test_m13_2_generated_part_bindings`, `test_m13_2_placement_derivations` | 74 passed |
| P4 | canonical mechanism/CAD + `test_m12_canonical_reconstruction` | 152 passed |
| P5.1 | `test_m10_semantic_projections`, `test_multi_joint_kinematics/collision_sweep`, `test_kinematic_sweep` | 103 passed |
| P5.2 | `test_candidate_m10_v2` + `test_m12_candidate_m10_binding/service/replay` | 65 passed |
| P5.3 + legacy | `test_candidate_multijoint_m10_v2` + `test_m13_3_*` | 44 passed |
| static | `python -m compileall src/mechcad_harness`; scoped `git diff --check` | clean |

## P6 — Canonical mechanism@4 / CAD realization@2 multi-joint bridge

Implemented on the canonical track only, leaving the candidate and legacy tracks unchanged:

- `PhysicalToM10V2BridgeCompiler.compile_canonical` dispatches a `CanonicalCadRealizationV2` input to `_derive_canonical_multi_joint_bridge_v2`, returning a `PhysicalToM10V2BridgeV2`.
- `_derive_canonical_multi_joint_bridge_v2` reuses the existing M10 model/inventory machinery (`compile_kinematic_model_v2`, `derive_multi_joint_collision_pair_inventory_v2`, `exact_scope_from_inventory_v2`) with `physical_mechanism_hash = canonical-physical-mechanism@4.mechanism_hash` and `cad_realization_hash = canonical-cad-realization@2.realization_hash`.
- `_validate_canonical_cad_realization_v2_for_bridge` recomputes the `canonical-cad-request@2` identity and `canonical-cad-realization@2` semantic hash (rejecting forged/stale mappings and coordinates).
- `_validate_canonical_physical_cad_universe_v2` binds each canonical component to its CAD@2 mapping/assembly instance and mechanism@4 component/specification.
- Canonical joint/axis identities are derived from the accepted `canonical_physical_mechanism_hash_payload_v4` projection (not legacy binding/source self-hashes).
- `validate_canonical_physical_to_m10_v2_bridge_v2` recomputes and compares the trusted canonical bridge.
- `CanonicalMultiJointM10VerificationService.execute` accepts `CanonicalCadRealizationV2` and executes the existing fresh M10 sweep path.

`canonical_cad.py` `_compile_generated` was made a `classmethod` so the bridge can reuse the accepted canonical generated-CAD compilation without a second projection; legacy `CanonicalPhysicalCadCompiler` callers are unaffected.

Regression: `tests/integration/test_m12_promotion_production.py::test_canonical_bridge_v2_consumes_promoted_mechanism_at4_and_cad_at2` passes, including: mechanism@4/CAD@2 assertions, trusted re-verification, fresh canonical verification, raw assembly-name rotation invariance, forged mapping/coordinate rejection, and candidate-vs-canonical `physical_mechanism_hash` cross-track rejection.

Canonical/P6 regression: `test_canonical_mechanism_v4`, `test_canonical_cad_mapping_v2`, `test_canonical_cad_realization_v2`, `test_canonical_m10_scope_v2`, `test_canonical_m10_v2`, `test_m12_canonical_reconstruction`, `test_m12_canonical_physical_mechanism`, `test_m13_3_canonical_mechanism_v3`, `test_m13_3_fresh_canonical_bridge`, `test_m13_3_fresh_canonical_m10`, `test_m13_3_bridge_compiler`, `test_m12_canonical_cad`, `test_m12_canonical_m10`, `test_m13_2_promotion_canonical_roundtrip` → **240 passed**.

## T-P7.2 — Promotion@2 / MJ typed-parent provenance

Preserved dirty-worktree implementation; fresh regression: `test_promotion_v2.py`, `test_candidate_multi_joint_m10_provenance_v1.py`, `test_m12_promotion_models/compiler/apply/replay`, `test_m13_4e_legacy_promotion_goldens` → **85 passed**.

## Broad Non-Live Gate

| Command (abbrev.) | Result |
|---|---|
| semantic/promotion/candidate focused batch | 281 passed |
| candidate foundation + M12 candidate batch | 312 passed |
| `tests/unit -k "m12 or m13 or multi_joint or structural"` | 1718 passed, 1 README-doc failure |
| `tests/unit -k "structural"` | 499 passed, 1 README-doc failure |
| candidate decision batch | 80 passed |
| step/semantic identity batch | 80 passed |
| `test_m12_promotion_production.py -k "not test_live"` | 21 passed |
| `test_m12_candidate_cad_m10_production.py -k "not live"` | 15 passed, 2 live failures |

Protected bytes unchanged: `multi_joint_kinematics.py` `514340c2…440c4f`; `multi_joint_collision_sweep.py` `56e55b66…9706f`; `test_m13_3_legacy_goldens.py` `7dc391f1…8d5ba4`; `multi_joint_pair_scope.py` `b593e0aa…d344`; `multi_joint_continuous_path.py` `c063ca82…fa9b`; `multi_joint_continuous_clearance.py` `66a62f30…bc5`.

`python -m compileall src/mechcad_harness` clean; scoped `git diff --check` clean.

### Pre-existing failures (not caused by this change)

1. Four README-doc content tests fail because `README.md` (unmodified; clean in git) does not contain the expected phrases: `test_agent_docs.py::test_m6a1_boundaries_are_documented`, `test_section_docs.py::test_structural_extra_and_axis_contract_are_documented`, `test_section_engineering_docs.py::test_c3a_boundaries_are_documented`, `test_section_warping_docs.py::test_c2b_policy_and_boundaries_are_documented`.
2. Two FreeCAD/gear-backed live integration tests fail in dirty concurrent-work fixtures whose `CandidateSourceBinding.bound_to` resolves `/yagi_payload_carrier_requirements/13` against a state with fewer entries: `test_m12_candidate_cad_m10_production.py::test_candidate_realization_rejects_unavailable_trusted_external_spur_artifact_without_downgrade`, `test_m12_candidate_cad_m10_production.py::test_explicit_bounded_collision_fixture_is_candidate_bound_not_trusted_fallback`. The traceback lies entirely outside the files changed in this session; these are live tests and are out of scope for the non-live gate.

## Gate

- R-P5.5/R-P5.6/P5.3/P5 complete; P6 canonical bridge green; T-P7.2 promotion green; broad non-live gate green apart from the pre-existing failures above.
- Independent implementation audit: **PENDING**.
