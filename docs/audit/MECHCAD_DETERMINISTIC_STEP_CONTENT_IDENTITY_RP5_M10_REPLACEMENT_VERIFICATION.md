# R-P5.M10 Prospective Replacement Verification

## Status

```text
R-P5.M10 replacement evidence: EXECUTED / GREEN
Separate independent evidence audit: PENDING
R-P5.5: BLOCKED pending that evidence audit
```

This is a prospective execution-evidence record under the independently accepted Plan revision. It is not itself independent audit acceptance.

## Authority and Historical Boundary

- Controlling accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Independently accepted Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- Plan acceptance record: `docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_IMPLEMENTATION_PLAN_RP5_M10_VERIFICATION_REVISION_INDEPENDENT_ACCEPTANCE.md`, marker `MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_PLAN_RP5_M10_VERIFICATION_REVISION_INDEPENDENTLY_ACCEPTED_291B39B0`.

**NOT PROVEN:** historical pre-relocation vs post-relocation output equality. The pre-relocation function bodies/output snapshots were not durably retained and cannot now be recovered. The original equality requirement was not executed. No statement or result in this record upgrades that historical fact.

**PROVEN INSTEAD:** the current relocated projections conform to the accepted semantic contracts under the prospective A–H verification matrix below, while the protected low-level implementation and legacy golden remain byte-identical. This claim is prospective current-state verification only and remains subject to the separate independent evidence audit.

## Worktree and Target Inventory

- Git HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807`.
- The semantic owner existed as an untracked worktree file before this verification; it was not edited here. Its final SHA-256 is `5e75da171c0d4c923761a07cf9b68609b85244d0badf3bc528371a418673d5e7`.
- `tests/unit/test_m10_semantic_projections.py` is an existing untracked worktree test file; SHA-256 `0965bb4f87897339772f1403a0a6953461bd5620e5d8aa43b58294b2044e33b4`.
- Added verification-only test file `tests/unit/test_rp5_m10_projection_vectors.py`; SHA-256 `499dd924fc34d0c0d8e017125236777e47b65ed4a80bfd6b42dd109a6deb833a`.
- No production source, accepted Spec, existing test, legacy golden, prior audit, or reconstruction file was changed by this verification.
- The revised Plan, its new independent Plan acceptance record, and this new verification record are untracked in the current checkout. Other pre-existing dirty worktree contents were preserved.

## A — Owner and Shape

`tests/unit/test_rp5_m10_projection_vectors.py::test_production_owner_definitions_imports_and_dependency_direction` parses production modules and verified:

- Exactly these four top-level projection definitions occur, all in `semantic_m10_kinematics.py`: `semantic_kinematic_model_hash`, `semantic_single_joint_kinematic_model_hash`, `semantic_m10_v2_request_hash`, and `semantic_m10_v2_result_hash`.
- Production references to those functions import them from the semantic owner; all four have production consumers.
- No `__all__` re-export or wildcard import re-exports them; protected low-level modules do not import the owner.
- The semantic owner has no direct candidate/project semantic import. A static module-initialization dependency traversal from its input dependencies is acyclic and does not reach one of its production callers.

Separate runtime import smoke passed for 14 modules: `semantic_m10_kinematics`, `cad_assembly`, `multi_joint_kinematics`, `multi_joint_collision_sweep`, `multi_joint_pair_scope`, `multi_joint_continuous_path`, `multi_joint_continuous_clearance`, candidate `multi_joint_m10_bridge`, `multi_joint_m10_evaluation`, `multi_joint_selection`, `canonical_m10`, `cad_realization`, `provenance_artifacts`, and `application`.

Exact smoke command:

```text
python -c "import importlib; modules=['mechcad_harness.semantic_m10_kinematics','mechcad_harness.cad_assembly','mechcad_harness.multi_joint_kinematics','mechcad_harness.multi_joint_collision_sweep','mechcad_harness.multi_joint_pair_scope','mechcad_harness.multi_joint_continuous_path','mechcad_harness.multi_joint_continuous_clearance','mechcad_harness.candidates.multi_joint_m10_bridge','mechcad_harness.candidates.multi_joint_m10_evaluation','mechcad_harness.candidates.multi_joint_selection','mechcad_harness.candidates.canonical_m10','mechcad_harness.candidates.cad_realization','mechcad_harness.candidates.provenance_artifacts','mechcad_harness.application']; [importlib.import_module(m) for m in modules]; print('related production imports passed:',len(modules))"
related production imports passed: 14
```

## B — Accepted-Contract Field Matrix

Expected classifications below are from accepted Spec `DE17C360...`, not from the current owner implementation. Full declared field sets are asserted in the new test file.

### F1 — `semantic_kinematic_model_hash` (§12A/F1)

| Declared field | Classification / treatment |
|---|---|
| `KinematicModelV2.schema_version` | INCLUDED; exact `kinematic-model@2` contract |
| `model_id` | INCLUDED |
| `bodies` | TRANSFORMED to body-sorted F1-B projections |
| `joints` | TRANSFORMED to joint-sorted F1-J projections |
| `evaluator_version` | EXCLUDED execution provenance; pinned/evaluated separately |
| `transform_agreement_version` | INCLUDED; exact `rigid-transform-agreement@1.0` pin |
| Body `schema_version`, `body_id`, `reference_member_instance_id` | INCLUDED |
| Body `members` | TRANSFORMED to member-sorted member projections |
| Body `body_hash` | EXCLUDED opaque derived/self identity; body integrity is revalidated, and its payload is not consumed |
| Member `member_instance_id` | INCLUDED |
| Member `reference_to_member_home` | TRANSFORMED to transform values |
| Transform `x_mm`, `y_mm`, `z_mm`, `rotation_quaternion` | INCLUDED |
| All 13 `RevoluteJointModelV2` fields: schema, ID, kind, endpoints, six axis values, two limits | INCLUDED |

Payload pins: `semantic_projection_version = m10-execution-semantics@1`, `model_contract = kinematic-model@2`, transform-agreement version; bodies, members, and joints use the accepted sorted order. Unknown fields and duplicate body/member/joint identities reject.

### F3 — `semantic_single_joint_kinematic_model_hash` (§12A/F3)

| Declared field | Classification / treatment |
|---|---|
| `KinematicModel.schema_version` | INCLUDED; exact `kinematic-model@1` contract |
| `model_id` | INCLUDED |
| `joints` | TRANSFORMED to joint-ID-sorted subprojections |
| `evaluator_version` | EXCLUDED execution provenance; pinned/evaluated separately |
| All 13 `RevoluteJointModel` fields: schema, ID, kind, instance endpoints, six axis values, two limits | INCLUDED |

Payload pins: `semantic_projection_version = m10-execution-semantics@1`, `model_contract = kinematic-model@1`. Duplicate joint IDs and mixed V1/V2 model types reject.

### P5 — `semantic_m10_v2_request_hash` (§12B/P5)

| Declared field | Classification / treatment |
|---|---|
| `schema_version` | INCLUDED; exact request `@2` contract |
| `source_assembly_id` | EXCLUDED operational name; equality-checked against the supplied assembly |
| `source_assembly_hash` | EXCLUDED legacy raw identity; replay-validated against the same supplied assembly |
| `model` | TRANSFORMED to F1 `semantic_kinematic_model_hash`; no full model or legacy model hash |
| `configurations` | INCLUDED engineering input; transformed to an ORDERED tuple of configuration hashes |
| `exact_pair_scope` | INCLUDED engineering input; canonicalized as a semantic set, with derived scope hash and pinned scope version |
| `volume_tolerance_mm3`, `distance_tolerance_mm` | INCLUDED |
| `evaluator_version` | EXCLUDED execution provenance; trusted pin validated separately |
| `model_hash` | EXCLUDED legacy evaluator-tainted replay identity |
| `request_hash` | EXCLUDED legacy raw-bound/self identity |

Exact payload fields: `semantic_projection_version`, `request_contract`, F1 identity, ordered configuration hashes, exact-pair scope hash/version, both tolerances, and `semantic_assembly_hash`. No raw assembly hash/name, full model, evaluator, or legacy identity enters the payload.

### P6 — `semantic_m10_v2_result_hash` (§12B/P6)

| Declared field | Classification / treatment |
|---|---|
| `schema_version` | INCLUDED; exact result `@2` contract |
| `evaluator_version` | EXCLUDED execution provenance |
| `source_assembly_hash` | EXCLUDED raw identity; replay-validated against the supplied assembly/request |
| `model_hash` | EXCLUDED legacy identity; result/request replay equality validated |
| `request_hash` | EXCLUDED legacy raw-bound identity; result/request replay equality validated and replaced by P5 |
| `configuration_results` | TRANSFORMED to an index-ordered semantic result tuple |
| `any_interference`, `any_touching`, `all_positive_clearance` | INCLUDED aggregate semantics |
| `collision_configuration_indices` | INCLUDED |
| `minimum_exact_distance_mm`, `minimum_distance_configuration_index` | INCLUDED |
| `continuous_path_verified` | INCLUDED; must be literal `False` |
| `result_hash` | EXCLUDED legacy self-hash |
| Nested configuration `schema_version`, index, configuration hash, joint states, instance transforms, pair results, classification, aggregate booleans, minimum distance | INCLUDED in their declared order; `transformed_assembly_hash` is EXCLUDED |
| Nested joint-state fields (`joint_id`, position, limits flag) | INCLUDED |
| Nested world-transform fields (instance ID, articulated flag, transform) and four transform values | INCLUDED |
| All six exact pair-result fields (schema, instance IDs, interference volume, distance, classification) | INCLUDED |

Payload pins: `semantic_projection_version = m10-execution-semantics@1`, result contract `multi-joint-collision-sweep-result@2`, P5 identity, F1 identity, ordered configuration semantics, aggregate/minimum fields, literal discrete-path `False`, and `semantic_assembly_hash`. Cardinality, configuration index/hash order, replay links, and unknown fields fail closed.

## C — Independent Expected Vectors

The accepted Spec contains normative payload rules but no direct literal digests for these four outputs. The pre-existing `test_m10_semantic_projections.py` covers field counts and invariance/sensitivity but does not pin their direct output digests. The downstream fixed digest pins already in `test_candidate_multijoint_m10_v2.py` and `test_semantic_family_closure.py` were retained and run as downstream regressions; they were not mislabeled as direct projection vectors.

Direct vectors are fixed as literal typed inputs, expected payload dictionaries, derived subidentities, and digest constants in `tests/unit/test_rp5_m10_projection_vectors.py` (SHA-256 above). The module’s `_independent_digest` uses only Python `hashlib`/`json` with UTF-8, sorted keys, compact separators; the expected constants were independently hand-expanded from the accepted Spec before invoking the four current projection functions. It does not import or call those functions to derive an expected value. The vector payloads are ASCII, so the canonical JSON bytes are identical under the accepted `ensure_ascii` default. P5/P6’s §10 assembly identity is independently expanded from its part-program payload, sorted parts/instances, and empty trusted-source list.

| Vector | Typed input | Expected payload constant | Independently derived digest |
|---|---|---|---|
| F1 | V2 model `model-v2`; base/moving bodies, identity member-home transforms, one +Z revolute joint | `_F1_PAYLOAD` | `sha256:05e4fe064b4458ee096fa0758fdd4d2b45b75b609525955aacdb559fb1b41a78` |
| F3 | V1 model `single`; one base→moving +Z revolute joint | `_F3_PAYLOAD` | `sha256:0db39969b526ec6cac7531f328bc1c5b6782a901689ea2df878efb00b335bd76` |
| §10 assembly subvector | Part `link` with a 10×10×2 base plate; `base` identity instance and `moving` at x=20 mm | `_PART_PROGRAM_PAYLOAD`, `_SEMANTIC_ASSEMBLY_PAYLOAD` | Part `sha256:ad0945dd5893d884a8a91426484de65b8d3ff6fa392489f5e588895099759f8a`; assembly `sha256:1a0e2d6ab4dc49597b46b23bffdc269426e43eac12b4f8c2f627ea722314c8d5` |
| P5 | Same assembly/model; ordered configurations `joint=0°`, `joint=45°`; exact pair `{base,moving}`; tolerances `1e-9 mm³`, `1e-7 mm` | `_P5_PAYLOAD`; nested configuration and pair-scope payloads `_CONFIGURATION_PAYLOADS`, `_PAIR_SCOPE_PAYLOAD` | `sha256:2eefb88398c7a3e5e0b4f841a3df8e68e332b71ac04982c438cd8067af6c40fb` |
| P6 | Same typed request; two ordered results (indexes 0/1, typed fixture joint positions 0°/1°), moving transform x=20 mm, base/moving positive clearance 3 mm, discrete path | `_P6_PAYLOAD` | `sha256:47ef3529ace390837138a5f6573a0250cef8775fdac5fa35cc61f6c41472a78b` |

The derived subvector pins used by P5/P6 are `joint_configuration_hash(0°) = sha256:90033cfd665cb11cb21ae79f18147c0c124dba7a4fcb638350fc260d85d88901`, `joint_configuration_hash(45°) = sha256:f56ca341850ee5fbd596b21b2fd4c824c83318911b9ea52537a33571118ffd80`, and exact-pair-scope digest `sha256:213a2984bc3ca06c9e6c707938a774b18f6b4ba604847c3b092c0398b5558007`. Each payload’s digest is self-checked by the test-local canonical digest primitive before the current projection output is compared to the pinned value.

## D — Sensitivity / Invariance / Rejection Matrix

Evidence is in the named tests in `tests/unit/test_rp5_m10_projection_vectors.py` plus the accepted existing suites in F/H:

| Contract case | Test evidence |
|---|---|
| Semantic F1 axis change changes output; evaluator-only change is invariant | `test_f1_f3_exclude_evaluator_and_preserve_semantic_order_rules` |
| F1 body, member, and joint set ordering is canonical; duplicate bodies reject | same test; `test_declared_field_sets_match_the_accepted_projection_tables` |
| F3 evaluator-only change and joint tuple reorder are invariant; axis change and duplicate joint IDs are sensitive/rejected | `test_f1_f3_exclude_evaluator_and_preserve_semantic_order_rules` |
| P5 operational assembly-name rotation is invariant; request self-hash and legacy model hash are excluded; configuration reorder and tolerance change alter output | `test_p5_is_semantic_but_keeps_configuration_order_and_replay_binding` |
| P5 exact-pair-scope tuple reorder canonicalizes to the same set; duplicate scope pair rejects | same test |
| P5 source assembly ID/hash mismatch fails replay binding | same test |
| P6 transient transformed-assembly hash, evaluator, result self-hash, and validly paired legacy model/request hashes are excluded; assembly-name rotation is invariant | `test_p6_excludes_transient_identity_and_binds_ordered_measurements` |
| P6 configuration reorder and measurement change alter identity; continuous-path claim, cardinality mismatch, and raw source hash mismatch reject | same test |
| Wrong V1/V2 record families and unknown fields reject | `test_wrong_semantic_families_and_unknown_declared_fields_fail_closed` |
| Full declared-field tables, including nested F1/P5/P6 records, equal the accepted Spec lists | `test_declared_field_sets_match_the_accepted_projection_tables` |

The matrix distinguishes exclusions from required replay validation: e.g. changing only a raw source assembly hash rejects; changing the operational assembly name while rebuilding matching replay records leaves the semantic output invariant. `body_hash` is omitted from F1 payload but remains integrity-revalidated per Spec; it is not treated as a freely mutable invariant.

## E — Protected Byte Pins

Recomputed after the final test run; all match the accepted Plan pins/current protected baselines:

| Protected file | Expected SHA-256 | Observed SHA-256 | Result |
|---|---|---|---|
| `src/mechcad_harness/multi_joint_kinematics.py` | `514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f` | same | MATCH |
| `src/mechcad_harness/multi_joint_collision_sweep.py` | `56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f` | same | MATCH |
| `tests/unit/test_m13_3_legacy_goldens.py` | `7dc391f10e545fc3291669a894a3c2a10729672eba9e847c1dca4dd88c8d5ba4` | same | MATCH |
| `src/mechcad_harness/multi_joint_pair_scope.py` | byte-identical to HEAD | `b593e0aa41b50a0dbc84c050f2396e0dba63b621fdd48cf3a7e185120706d344` | MATCH |
| `src/mechcad_harness/multi_joint_continuous_path.py` | byte-identical to HEAD | `c063ca8269392b68b911492f72071bdd5f7de30acd4461c98cad045a5574fa9b` | MATCH |
| `src/mechcad_harness/multi_joint_continuous_clearance.py` | byte-identical to HEAD | `66a62f30a7fe96c40f6cb049bf96906a427931b276ce9847dad42e6f95ad2bc5` | MATCH |

The three additional protected M10 source files and all three exact-hash targets were clean in the worktree. No source/golden mutation occurred.

## F — Fresh Focused Regression and Static Checks

Final fresh R-P5.M10 focused invocation:

```text
python -m pytest tests/unit/test_m10_semantic_projections.py tests/unit/test_multi_joint_kinematics.py tests/unit/test_multi_joint_collision_sweep.py tests/unit/test_multi_joint_continuous_path.py tests/unit/test_multi_joint_continuous_clearance.py tests/unit/test_m13_3p_legacy_goldens.py tests/unit/test_m13_3_legacy_goldens.py tests/unit/test_kinematic_sweep.py tests/unit/test_rp5_m10_projection_vectors.py -v
135 passed in 7.43s
```

The final verification-only vector suite also ran independently:

```text
python -m pytest tests/unit/test_rp5_m10_projection_vectors.py -v
8 passed in 6.00s
```

Two earlier draft invocations of that new test file had one test-only failure each; they remain disclosed:

1. Initial draft: 7 passed, 1 failed because the expected-error regex said `replay identities` while the contract correctly rejected earlier with `source assembly hash does not match reconstructed assembly`. The assertion was corrected to the observed contract error.
2. Next draft: 7 passed, 1 failed because the AST reference checker treated a Pydantic field annotation (AST `Store`) as a function use. The checker was corrected to inspect loaded names only.

No production source was changed to address either draft failure. The final vector suite and full focused gate above passed on the final test bytes.

Static/build checks:

```text
python -m compileall src/mechcad_harness
exit 0; no compile errors

git diff --no-index --check -- /dev/null tests/unit/test_rp5_m10_projection_vectors.py
no whitespace diagnostics

git diff --check -- src/mechcad_harness/multi_joint_kinematics.py src/mechcad_harness/multi_joint_collision_sweep.py src/mechcad_harness/multi_joint_pair_scope.py src/mechcad_harness/multi_joint_continuous_path.py src/mechcad_harness/multi_joint_continuous_clearance.py tests/unit/test_m13_3_legacy_goldens.py tests/unit/test_m10_semantic_projections.py
no whitespace diagnostics
```

## G — Import and Ownership

The static AST owner/import/field test passed in the 135-test focused gate. A separate production import smoke after the final verification-test edits passed:

```text
14 production modules imported successfully
```

The import list and static checks are recorded in A and the test source. This is a current import/graph result, not historical equality evidence.

## H — Downstream P5/P6 Consistency

```text
python -m pytest tests/unit/test_candidate_m10_v2.py tests/unit/test_candidate_multijoint_m10_v2.py tests/unit/test_canonical_m10_scope_v2.py tests/unit/test_canonical_m10_v2.py -v
38 passed in 23.44s

python -m pytest tests/unit/test_semantic_family_closure.py -k "m10_semantic_projections_raw_rotation_invariance or evaluator_version_exclusion or transformed_assembly_hash_exclusion" -v
3 passed, 129 deselected in 3.78s
```

These tests verify current downstream consistency and retain the pre-existing expected hash pins in their source. They do not establish historical output equality and do not mark P5.3 or P6 complete.

## Final Evidence Labels and Gate

- **NOT PROVEN:** historical pre-relocation vs post-relocation output equality. It cannot now be reproduced because the pre-relocation bodies/output snapshots were not durably preserved; the original R-P5.M10 clause was not executed.
- **PROVEN INSTEAD:** current relocated projections match the independently derived accepted-Spec vectors and pass the accepted contract/sensitivity matrix; protected M10 sources and legacy golden remain byte-identical.
- Fresh focused and downstream test gates, compilation, import smoke, static ownership/cycle check, diff checks, and protected hashes are green for the exact invocations above.
- Independent read-only audit of this evidence record: **PENDING**. Do not start R-P5.5 until it accepts this record.
