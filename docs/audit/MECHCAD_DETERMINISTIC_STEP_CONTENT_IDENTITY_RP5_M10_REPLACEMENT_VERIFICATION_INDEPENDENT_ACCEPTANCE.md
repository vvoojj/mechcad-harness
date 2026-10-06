# R-P5.M10 Replacement Verification — Independent Evidence Acceptance

## Verdict

```text
Target evidence bundle:
  docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_M10_REPLACEMENT_VERIFICATION.md
  docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_M10_REPLACEMENT_VERIFICATION_SUPPLEMENT_01.md
  docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_M10_REPLACEMENT_VERIFICATION_SUPPLEMENT_02.md

Accepted Plan SHA-256:
  291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679

Controlling accepted Spec SHA-256:
  DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68

Disposition:
  INDEPENDENTLY_ACCEPTED — PROSPECTIVE VERIFICATION EVIDENCE ONLY

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_M10_REPLACEMENT_VERIFICATION_INDEPENDENTLY_ACCEPTED
```

The Plan acceptance is planning authority only. This record accepts
**planning-accepted prospective verification evidence only** for the exact Plan,
Spec, execution report, supplements, vector test, semantic owner, and protected
bytes identified below. It accepts the complete prospective R-P5.M10
replacement-evidence bundle. It is not implementation acceptance, completion
of P5.3/P6, or live-runtime acceptance.

## Historical Boundary

- **Historical pre-relocation versus post-relocation projection-output equality:
  NOT PROVEN.** The pre-relocation function bodies/output snapshots were not
  durably preserved and cannot now be recovered.
- **Original before/after equality clause: NOT EXECUTED.** No test, source hash,
  current vector, prospective conformance result, or `PROVEN INSTEAD` statement
  is interpreted as historical equality.
- The accepted claim is prospective: the current relocated projections match
  the independently derived accepted-Spec contracts and the applicable
  sensitivity, invariance, rejection, ownership, and regression checks.

## Exact-Byte and Authority Checks

Independently recomputed SHA-256 values:

| Artifact | Recomputed SHA-256 | Result |
|---|---|---|
| Accepted Plan `docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md` | `291b39b0daf33dd3d55937d8062ecce70f4e2fed511c3c611d56a3e98a5d6679` | MATCH |
| Accepted Spec `docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md` | `de17c360f09a9c9cb9a8a01118789b41ad4f1366a23ad728bfa3a9b19e2b1b68` | MATCH |
| Plan acceptance record `docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_IMPLEMENTATION_PLAN_RP5_M10_VERIFICATION_REVISION_INDEPENDENT_ACCEPTANCE.md` | `f93616a1a94d5331301ae742bbf4b662c3407a64c97bdf8c248f23acea0d169f` | MATCH; binds Plan and controlling Spec above |
| Primary execution report | `2935d8ff95bf4e9effbece09c4dd076ab37e30a18f0778e07c5f77f3ace95a58` | MATCH |
| Supplement 01 | `0b1056ac7f014de83574e34ca7c14496b6b883bdc01ae40fc2eae433d694b63c` | MATCH |
| Supplement 02 | `2af1c230b6a5a4c6c57e1e2b9d454543a7b8a40e38b0664f41af9c6807b7d020` | MATCH |
| Vector/matrix test `tests/unit/test_rp5_m10_projection_vectors.py` | `499dd924fc34d0c0d8e017125236777e47b65ed4a80bfd6b42dd109a6deb833a` | MATCH |
| Semantic owner `src/mechcad_harness/semantic_m10_kinematics.py` | `5e75da171c0d4c923761a07cf9b68609b85244d0badf3bc528371a418673d5e7` | MATCH |

The Spec revision acceptance record was read and binds the same exact Spec SHA
to `MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_INDEPENDENTLY_ACCEPTED`.
The Plan acceptance record binds the same Plan and Spec hashes and explicitly
preserves the historical NOT PROVEN / NOT EXECUTED boundary.

The checkout HEAD was `05da8edad18488492f02be1dad9d1ec3653ce807`, matching the
reported code HEAD. The Plan, Spec, evidence reports, vector test, and semantic
owner are untracked worktree artifacts at that HEAD; their exact worktree bytes
were independently hashed above. The worktree had extensive unrelated dirty
and untracked content. It was preserved.

## Independent Literal-Payload Digest Recalculation

The four direct expected digests were recomputed in a standalone Python script
using only `hashlib` and `json` from the standard library. The script manually
constructed the normative payloads and did not import or call any current
projection function, semantic hash helper, or test module. Serialization was
UTF-8 JSON with sorted object keys and compact separators; the payload literals
are ASCII. All direct and derived pins matched:

| Independently constructed payload | Recomputed digest |
|---|---|
| F1 `semantic_kinematic_model_hash` | `sha256:05e4fe064b4458ee096fa0758fdd4d2b45b75b609525955aacdb559fb1b41a78` |
| F3 `semantic_single_joint_kinematic_model_hash` | `sha256:0db39969b526ec6cac7531f328bc1c5b6782a901689ea2df878efb00b335bd76` |
| P5 `semantic_m10_v2_request_hash` | `sha256:2eefb88398c7a3e5e0b4f841a3df8e68e332b71ac04982c438cd8067af6c40fb` |
| P6 `semantic_m10_v2_result_hash` | `sha256:47ef3529ace390837138a5f6573a0250cef8775fdac5fa35cc61f6c41472a78b` |
| §10 base-plate part-program payload | `sha256:ad0945dd5893d884a8a91426484de65b8d3ff6fa392489f5e588895099759f8a` |
| §10 semantic assembly payload | `sha256:1a0e2d6ab4dc49597b46b23bffdc269426e43eac12b4f8c2f627ea722314c8d5` |
| Configuration `joint=0°` | `sha256:90033cfd665cb11cb21ae79f18147c0c124dba7a4fcb638350fc260d85d88901` |
| Configuration `joint=45°` | `sha256:f56ca341850ee5fbd596b21b2fd4c824c83318911b9ea52537a33571118ffd80` |
| Exact-pair scope | `sha256:213a2984bc3ca06c9e6c707938a774b18f6b4ba604847c3b092c0398b5558007` |

The §10 input was independently expanded as the sorted `link` part with its
base-plate program hash, an empty trusted-source list, and sorted `base` and
`moving` instances with their declared placements. That same semantic assembly
digest appears in the independently constructed P5 and P6 payloads. The
existing downstream pins remain downstream regression pins; they are not
represented as direct projection digests.

## Accepted-Spec Contract Review

The accepted Spec §§10, 12A/F1/F3, 12B/P5/P6, and 23 were compared field by
field with the primary report, test payloads, semantic owner, and supplements.
Declared source fields are distinct from derived values as required by §12B.

### F1 — `semantic_kinematic_model_hash`

| Declared input | Classification and payload treatment |
|---|---|
| Model `schema_version` | INCLUDED by exact `model_contract: kinematic-model@2` pin |
| `model_id` | INCLUDED |
| `bodies` | TRANSFORMED to body-ID-sorted F1 body projections |
| `joints` | TRANSFORMED to joint-ID-sorted F1 joint projections |
| `evaluator_version` | EXCLUDED execution provenance; execution trust pin is validated separately |
| `transform_agreement_version` | INCLUDED; exact `rigid-transform-agreement@1.0` pin |
| Body `schema_version`, `body_id`, `reference_member_instance_id` | INCLUDED |
| Body `members` | TRANSFORMED to member-ID-sorted projections |
| Body `body_hash` | EXCLUDED derived/self identity; body model validation re-derives/checks it |
| Member `member_instance_id` | INCLUDED |
| Member `reference_to_member_home` | TRANSFORMED to its four declared transform values |
| Transform `x_mm`, `y_mm`, `z_mm`, `rotation_quaternion` | INCLUDED |
| All 13 `RevoluteJointModelV2` fields | INCLUDED: schema, ID, kind, both body endpoints, six axis coordinates/directions, and two nullable limits |

Exact F1 payload keys are `semantic_projection_version`, `model_contract`,
`model_id`, `bodies`, `joints`, and `transform_agreement_version`.
`semantic_projection_version` is pinned to `m10-execution-semantics@1`.
Unknown declared fields and duplicate body/member/joint identities fail
closed. The vector includes complete body/member/joint/transform records.

### F3 — `semantic_single_joint_kinematic_model_hash`

| Declared input | Classification and payload treatment |
|---|---|
| Model `schema_version` | INCLUDED by exact `model_contract: kinematic-model@1` pin |
| `model_id` | INCLUDED |
| `joints` | TRANSFORMED to joint-ID-sorted projections |
| `evaluator_version` | EXCLUDED execution provenance; execution trust pin is validated separately |
| All 13 `RevoluteJointModel` fields | INCLUDED: schema, ID, kind, both instance endpoints, six axis coordinates/directions, and two nullable limits |

Exact F3 payload keys are `semantic_projection_version`, `model_contract`,
`model_id`, and `joints`; the projection version is
`m10-execution-semantics@1`. Duplicate joint IDs, unknown fields, and mixed
V1/V2 model types fail closed.

### P5 — `semantic_m10_v2_request_hash`

| One of 11 declared request fields | Classification and behavior |
|---|---|
| `schema_version` | INCLUDED through exact `request_contract: multi-joint-collision-sweep-request@2`; other versions reject |
| `source_assembly_id` | EXCLUDED operational name; must equal the supplied assembly ID |
| `source_assembly_hash` | EXCLUDED raw identity; independently recomputed against the same reconstructed assembly and must match |
| `model` | TRANSFORMED to F1 semantic identity; full/legacy model hash is not payload input |
| `configurations` | INCLUDED as ordered configuration hashes; value and tuple order changes alter P5 |
| `exact_pair_scope` | INCLUDED as canonical set semantics, exact-pair scope hash, and pinned scope version |
| `volume_tolerance_mm3` | INCLUDED |
| `distance_tolerance_mm` | INCLUDED |
| `evaluator_version` | EXCLUDED execution provenance; trusted evaluator validation remains separate |
| `model_hash` | EXCLUDED legacy evaluator-tainted replay identity |
| `request_hash` | EXCLUDED legacy raw-bound/self identity |

Exact P5 payload keys are `semantic_projection_version`, `request_contract`,
`semantic_kinematic_model_hash`, ordered `configuration_hashes`,
`exact_pair_scope_hash`, `exact_pair_scope_version`, `volume_tolerance_mm3`,
`distance_tolerance_mm`, and `semantic_assembly_hash`. Derived configuration,
scope, and assembly identities are not counted as declared request fields.

The supplements and fresh direct probes cover every declared field: unsupported
schema rejection; invalid assembly ID/hash replay rejection and valid assembly
rename/raw-identity rotation invariance; model-axis sensitivity; configuration
value and order sensitivity; scope membership sensitivity, tuple-order
invariance, and duplicate rejection; both tolerance fields; evaluator
exclusion; and legacy model/request identity exclusion.

Supplement 02 verifies the scope membership case against one typed assembly
containing all three declared instances `base`, `moving`, and `other`. It adds
`(base, other)` to `(base, moving)` and verifies that membership changes P5,
while reversing the same two-pair tuple leaves P5 unchanged. The assembly is
reconstructed and its matching raw assembly hash is replay-verified by the P5
path.

### P6 — `semantic_m10_v2_result_hash`

| Declared input | Classification and payload treatment |
|---|---|
| Result `schema_version` | INCLUDED through exact `result_contract: multi-joint-collision-sweep-result@2` |
| `evaluator_version` | EXCLUDED execution provenance |
| `source_assembly_hash` | EXCLUDED raw identity; replay-validated against request and supplied assembly |
| `model_hash` | EXCLUDED legacy identity; result/request replay equality is checked |
| `request_hash` | EXCLUDED legacy raw-bound identity; result/request replay equality is checked and P5 replaces it semantically |
| `configuration_results` | TRANSFORMED to index-ordered semantic configuration projections |
| `any_interference`, `any_touching`, `all_positive_clearance` | INCLUDED aggregate semantics |
| `collision_configuration_indices` | INCLUDED |
| `minimum_exact_distance_mm`, `minimum_distance_configuration_index` | INCLUDED |
| `continuous_path_verified` | INCLUDED with discrete-path value pinned to literal `False`; true rejects |
| `result_hash` | EXCLUDED legacy self-hash |
| Nested configuration's 12 fields | Schema, index, configuration hash, ordered joint states, ordered world transforms, ordered pair results, classification, three aggregate booleans, and minimum distance are included/transformed; `transformed_assembly_hash` is excluded |
| Nested `EvaluatedJointState` (3 fields) | `joint_id`, `joint_position_deg`, `within_limits` included |
| Nested world transform (3 fields) | `instance_id`, `is_articulated` included; nested transform transformed to all four included transform values |
| Nested exact pair result (6 fields) | Schema, both IDs, interference volume, exact distance, and classification included |

Exact P6 payload keys are `semantic_projection_version`, `result_contract`,
`semantic_m10_v2_request_hash`, `semantic_kinematic_model_hash`,
`configuration_semantic_results`, `any_interference`, `any_touching`,
`all_positive_clearance`, `collision_configuration_indices`,
`minimum_exact_distance_mm`, `minimum_distance_configuration_index`,
`continuous_path_verified`, and `semantic_assembly_hash`. Configuration index
and order, joint-state order, world-transform order, and pair-result order are
preserved. The projection version is pinned to `m10-execution-semantics@1`.

The complete typed F1/F3/P5/P6 expected payloads and declared-field sets are
present in the hashed vector test. Unknown fields, wrong semantic record
families, invalid source replay bindings, result/request replay-link mismatch,
configuration cardinality/order/hash mismatch, and a continuous-path claim
fail closed. P6 tests additionally cover excluded transformed-assembly hashes,
execution identity, and self-hash; semantic measurement and ordering changes
alter the identity.

## Closure of the Prior Rejection Findings

The field-probe coverage previously rejected is closed:

1. **F1 body/member/joint/transform:** Supplement 01 records changed body ID
   with a matching joint endpoint, added member identity, changed member home
   transform, changed joint limit, body/member/joint order invariance, duplicate
   body/member/joint rejection, and an unknown nested body-field rejection.
   Fresh direct behavioral probes reproduced these outcomes.
2. **F3 unknown fields:** Supplement 01 records the single-joint unknown-field
   rejection. The F3 field-set/type matrix and duplicate/type/order probes are
   also in the vector test; fresh direct probes reproduced the unknown-field
   rejection.
3. **P5 all 11 fields:** The classifications and probe outcomes above account
   for every declared request field, including both tolerance fields, ordered
   configuration values, scope membership/order/duplicate behavior, version,
   source ID/hash binding and replay, model transformation, evaluator exclusion,
   legacy model hash, and request self-hash. Supplement 02 resolves the prior
   invalid-pair-set-coverage concern with three IDs declared in the same
   assembly.

The supplements report 35 supplemental assertions and the valid three-instance
probe. An additional auditor-run direct behavior pass completed 36 assertions.
No current projection was used to derive the expected literal digests.

## A–H Replacement Contract and Other Plan Requirements

| Plan gate | Independent finding |
|---|---|
| A — owner and shape | The passing AST test confirms exactly four definitions in `semantic_m10_kinematics.py`, direct production imports, no compatibility re-export/wildcard export, no protected-file import of the owner, no candidate/project semantic dependency, and acyclic static module-initialization dependencies. |
| B — accepted-contract matrix | The F1/F3/P5/P6 classifications and exact payload keys above agree with the accepted Spec. All declared input/nested fields, order rules, version pins, replay bindings, and fail-closed behavior were checked. |
| C — independent vectors | Four complete fixed typed vectors are present; all four digests and §10/P5/P6 input digests were independently recomputed without projection imports/calls. Existing downstream pins are kept distinct from direct projection pins. |
| D — sensitivity/invariance/rejection | Primary tests, Supplement 01, Supplement 02, and the fresh direct probes cover applicable semantic changes, set/order semantics, raw/replay binding, execution/self-hash exclusions, duplicate/unknown/mixed-family rejection, and valid pair-set membership. No additional invariance is inferred. |
| E — protected bytes | All six specified M10 files match their required hashes or HEAD bytes, as tabulated below. |
| F — focused verification | The exact focused gate, predecessor gate, direct vectors, compilation, and whitespace checks were freshly run; commands/results are recorded below. |
| G — import/ownership | The AST ownership/dependency check passed; the separate 14-module production import smoke passed after final test edits. |
| H — downstream consistency | The accepted P5/P6 focused consumer command and semantic-family closure command passed with the recorded counts below. They do not establish historical equality or mark P5.3/P6 complete. |

The accepted Plan's only R-P5.M10 requirement replacement is its expressly
accepted narrow substitution of prospective Spec-conformance proof for the
unrecoverable before/after comparison. All other substantive relocation
requirements remain binding: exactly four functions and one owner; unchanged
payloads, allowlists, canonicalization, and projection version; protected files
and golden unchanged; direct owner imports; no duplicate/re-export; and acyclic
dependencies. R-P5.5, R-P5.6, complete P5, P6, P7, and later gates are not
collapsed, waived, or declared complete here.

## Protected Byte Checks

Hashes were recomputed after the fresh test runs:

| Protected file | Required SHA-256 | Recomputed SHA-256 | Result |
|---|---|---|---|
| `src/mechcad_harness/multi_joint_kinematics.py` | `514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f` | same | MATCH; byte-identical to HEAD |
| `src/mechcad_harness/multi_joint_collision_sweep.py` | `56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f` | same | MATCH; byte-identical to HEAD |
| `tests/unit/test_m13_3_legacy_goldens.py` | `7dc391f10e545fc3291669a894a3c2a10729672eba9e847c1dca4dd88c8d5ba4` | same | MATCH; byte-identical to HEAD |
| `src/mechcad_harness/multi_joint_pair_scope.py` | Byte-identical to HEAD | `b593e0aa41b50a0dbc84c050f2396e0dba63b621fdd48cf3a7e185120706d344` | MATCH |
| `src/mechcad_harness/multi_joint_continuous_path.py` | Byte-identical to HEAD | `c063ca8269392b68b911492f72071bdd5f7de30acd4461c98cad045a5574fa9b` | MATCH |
| `src/mechcad_harness/multi_joint_continuous_clearance.py` | Byte-identical to HEAD | `66a62f30a7fe96c40f6cb049bf96906a427931b276ce9847dad42e6f95ad2bc5` | MATCH |

All three additional protected files were clean in the worktree and byte-equal
to HEAD. The three pinned source/golden files also match HEAD exactly.

## Fresh Verification Results

The following ordinary unit-test commands were rerun by this audit. No
FreeCAD/Gmsh/CalculiX or other live/external runtime was invoked.

```text
python -m pytest tests/unit/test_m10_semantic_projections.py tests/unit/test_multi_joint_kinematics.py tests/unit/test_multi_joint_collision_sweep.py tests/unit/test_multi_joint_continuous_path.py tests/unit/test_multi_joint_continuous_clearance.py tests/unit/test_m13_3p_legacy_goldens.py tests/unit/test_m13_3_legacy_goldens.py tests/unit/test_kinematic_sweep.py tests/unit/test_rp5_m10_projection_vectors.py -v
135 passed in 7.91s
```

```text
python -m pytest tests/unit/test_candidate_m10_v2.py tests/unit/test_candidate_multijoint_m10_v2.py tests/unit/test_canonical_m10_scope_v2.py tests/unit/test_canonical_m10_v2.py -v
38 passed in 23.91s
```

```text
python -m pytest tests/unit/test_semantic_family_closure.py -k "m10_semantic_projections_raw_rotation_invariance or evaluator_version_exclusion or transformed_assembly_hash_exclusion" -v
3 passed, 129 deselected in 4.02s
```

Additional fresh checks:

```text
python -m compileall src/mechcad_harness
exit 0; no compile errors

14-module production import smoke (the exact command is recorded in the primary report)
related production imports passed: 14

git diff --check -- <the six protected M10/golden files and existing semantic test>
no whitespace diagnostics

git diff --no-index --check -- /dev/null tests/unit/test_rp5_m10_projection_vectors.py
no whitespace diagnostics

git diff --no-index --check -- /dev/null src/mechcad_harness/semantic_m10_kinematics.py
no whitespace diagnostics
```

The primary report and Supplement 01 continue to disclose the two earlier
test-only draft failures: the first was an error-message regex mismatch; the
second was an AST checker counting an annotation `Store` as a use. Neither was
resolved by changing production code. Both are retained as failed earlier
invocations, and the final test bytes passed the fresh 135-test focused gate.

## Gate Status and Scope

- R-P5.M10 prospective replacement-verification evidence: **ACCEPTED** by this
  independent audit.
- Historical equality: **NOT PROVEN**; original clause: **NOT EXECUTED**.
- `R-P5.5` may proceed only after this evidence acceptance, and subject to the
  accepted Plan's remaining current-byte/worktree reconciliation and phase
  prerequisites. This record does not execute R-P5.5 or authorize edits outside
  the user's stated scope.
- P5.3, R-P5.6, complete P5, P6, P7, default activation, and live verification
  are not accepted or marked complete by this record.

The Plan, Spec, source, existing tests, primary report, both supplements, prior
acceptance records, and reconstruction were inspected read-only. This new audit
record is the only file created. No commit or push was made.
