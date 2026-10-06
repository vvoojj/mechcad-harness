# Deterministic STEP Content Identity — R-P5.5/R-P5.6/P6/T-P7.2 Implementation — Independent Acceptance

## Verdict

```text
Target evidence record:
  docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_RP6_RP7_IMPLEMENTATION_EVIDENCE.md
  (SHA-256 fd3f6cbb07e854c39d4318a1d3f424c3dd3c98ac9421693da7549659134c5a9a)

Accepted Plan SHA-256:
  291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679

Accepted Spec SHA-256:
  DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68

Code HEAD:
  05da8edad18488492f02be1dad9d1ec3653ce807

Disposition:
  INDEPENDENTLY_ACCEPTED — IMPLEMENTATION EVIDENCE ONLY

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_RP6_RP7_IMPLEMENTATION_INDEPENDENTLY_ACCEPTED
```

This record accepts **implementation evidence only** for the R-P5.5 candidate-track
rebind, the P6 canonical `@4`/CAD `@2` multi-joint bridge, and the T-P7.2
promotion `@2` / MJ typed-parent provenance regression, at the exact bytes
identified below. It is **not** a commit/release authorization. Historical
equality remains **NOT PROVEN** (see the preserved boundary below). P5.3 positive
resumption, complete P5, P7, default activation, and live verification are not
declared complete by this record.

## Historical Boundary (preserved, not reinterpreted)

- The R-P5.M10 replacement verification was independently accepted in
  `docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_RP5_M10_REPLACEMENT_VERIFICATION_INDEPENDENT_ACCEPTANCE.md`
  (SHA-256 `f02a02697f90d859da69b6dce59508b88743f47a6dc151a7e45f3b1caa86c66d`) with
  historical pre/post-relocation projection-output equality **NOT PROVEN** and the
  original before/after equality clause **NOT EXECUTED**.
- This audit does not reinterpret that boundary. The evidence record's line 21
  states the same NOT PROVEN / NOT EXECUTED status, and it was confirmed against
  the accepted record above.
- No historical run is inferred from committed test code; the fresh runs recorded
  below are evidence only for their exact invocations.

## Exact-Byte Checks (check 1)

Independently recomputed SHA-256 values from the working tree:

| Artifact | Recomputed SHA-256 | Result |
|---|---|---|
| Accepted Plan `docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md` | `291b39b0daf33dd3d55937d8062ecce70f4e2fed511c3c611d56a3e98a5d6679` | MATCH |
| Accepted Spec `docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md` | `de17c360f09a9c9cb9a8a01118789b41ad4f1366a23ad728bfa3a9b19e2b1b68` | MATCH |
| Evidence record | `fd3f6cbb07e854c39d4318a1d3f424c3dd3c98ac9421693da7549659134c5a9a` | MATCH (record self-identifies; recomputed here) |
| `src/mechcad_harness/candidates/multi_joint_m10_bridge.py` | `d943dfd253b4f372d51fe83aa4850ec5faee6d67ef0d430f6a977ee963b112b8` | MATCH |
| `src/mechcad_harness/candidates/canonical_cad.py` | `8802647e4e3d624698e9bb3ee950d1003669968f01ba922048a1e61a6251ecfd` | MATCH |
| `tests/integration/test_m12_promotion_production.py` | `c47376302b940acdb4da6bdcd5ffbe5ba19dbe2b580a4d945d02ffd5a2a63fdb` | MATCH |
| `src/mechcad_harness/semantic_m10_kinematics.py` | `5e75da171c0d4c923761a07cf9b68609b85244d0badf3bc528371a418673d5e7` | MATCH |
| `tests/unit/test_rp5_m10_projection_vectors.py` | `499dd924fc34d0c0d8e017125236777e47b65ed4a80bfd6b42dd109a6deb833a` | MATCH |

The checkout HEAD is `05da8edad18488492f02be1dad9d1ec3653ce807`, matching the
reported code HEAD. The three changed files are modified in the worktree relative
to HEAD (as reported); the R-P5.M10 semantic owner and vector test are unchanged.

## R-P5.5 Candidate-Track Rebind (check 2)

Independently inspected current bytes:

- `_derive_candidate_multi_joint_bridge_v2` (`multi_joint_m10_bridge.py:2214`)
  computes `candidate_mechanism_hash = semantic_candidate_mechanism_hash(realization)`
  (`:2327`) and passes it into `derive_multi_joint_collision_pair_inventory_v2`
  (`:2328-2330`) and `PhysicalToM10V2BridgeV2.physical_mechanism_hash` (`:2347`).
- `_build_request_v2` (`multi_joint_m10_evaluation.py:759`) verifies
  `bridge.physical_mechanism_hash == semantic_candidate_mechanism_hash(candidate.realization)`
  (`:811-814`) and rejects otherwise.
- Both `_validate_chain_v2` @2 branches (`multi_joint_selection.py:408` and
  `:611`) compare `request.physical_mechanism_hash` to
  `semantic_candidate_mechanism_hash(realization)` (`:463` and `:658-661`).
- `semantic_candidate_mechanism_hash` (`candidates/models.py:1702`) is the public
  @2-only wrapper over `semantic_candidate_realization_payload`; raw
  `realization_hash` is excluded.
- Legacy @1 is untouched: `compile_candidate`'s legacy branch still uses
  `realization.realization_hash` (`multi_joint_m10_bridge.py:3639`), and the
  legacy `build_request`/`_validate_chain`/`select` tails are unchanged.
- Canonical `compile_canonical`'s legacy branch still requires mechanism `@3` and
  uses `mechanism.mechanism_hash` (`:3689-3711`); it is untouched.

Fresh test evidence: `tests/unit/test_candidate_multijoint_m10_v2.py::test_candidate_m10_v2_rebinds_semantic_mechanism_and_hashes_project_id`
asserts the rebind, the inequality with raw `realization_hash`, rejection of raw
axis-source hashes (`interface_hash`/`geometry_reference_hash`/`source_hash`),
rejection of a canonical `@4` mechanism hash (cross-track substitution), and
project_id inclusion in the MJ request@2/evaluation@2/selection@2 digests
(`tests/unit/test_candidate_multijoint_m10_v2.py:627-772`). The full file passed
(below).

## P6 Canonical `@4`/CAD `@2` Bridge (check 3)

Independently inspected against Spec §6C/§14/§15 and Plan T-P6:

- `compile_canonical` dispatches `CanonicalCadRealizationV2` to
  `_derive_canonical_multi_joint_bridge_v2` (`multi_joint_m10_bridge.py:3654-3662`).
- `_derive_canonical_multi_joint_bridge_v2` (`:3329`) uses
  `mechanism.mechanism_hash` (mechanism `@4`) and
  `cad_realization.realization_hash` (CAD `@2`) (`:3396-3397`, `:3413`), matching
  §6C/§14 track-consistency.
- `_validate_canonical_cad_realization_v2_for_bridge` (`:2097`) recomputes the
  `canonical-cad-request@2` identity via `semantic_canonical_cad_request_hash`
  (`:2153-2166`) and the `canonical-cad-realization@2` semantic hash via
  `canonical_cad_realization_hash_v2` (`:2167-2169`), rejecting forged/stale
  mappings.
- Mappings/coordinates/assembly are revalidated: `_validate_canonical_physical_cad_universe_v2`
  (`:2173`) binds each canonical component to its CAD `@2` mapping/assembly
  instance and mechanism `@4` component/specification; `rigid_transform_agrees`
  re-checks the resolved placement against the mapping (`:3369-3370`).
- The M10 model/inventory are derived through the shared core
  (`compile_kinematic_model_v2`, `derive_multi_joint_collision_pair_inventory_v2`,
  `exact_scope_from_inventory_v2`; `:3387-3411`).
- Canonical joint/axis identities come from
  `canonical_physical_mechanism_hash_payload_v4(mechanism)["physical_revolute_joint_bindings"]`
  (`:3405-3423`); the payload's axis sub-projection (`models/physical_mechanism.py:1596-1648`)
  excludes raw M13 hashes and legacy binding self-hashes. They do not consume the
  legacy binding/source self-hashes.
- The canonical bridge hash is recomputed: `validate_canonical_physical_to_m10_v2_bridge_v2`
  (`:3436`) re-derives and compares (`:3443-3445`), and `PhysicalToM10V2BridgeV2`
  self-validates `physical_to_m10_bridge_hash` (`:3027-3031`).

`canonical_cad.py` `_compile_generated` was changed from an instance method
(`HEAD:canonical_cad.py:605`) to a `classmethod` (`:1456-1457`). It uses
`cls._GENERATED_COMPONENT_TYPES` and `build_canonical_view`; the existing call
site `self._compile_generated(...)` (`:1152`) binds `cls = type(self)`, so behavior
for `CanonicalPhysicalCadCompiler` and subclasses is identical. The new caller
`CanonicalPhysicalCadCompiler._compile_generated(...)` (`multi_joint_m10_bridge.py:2137`)
uses the same accepted compilation. Legacy `CanonicalPhysicalCadCompiler` behavior
is not altered.

Regression: `tests/integration/test_m12_promotion_production.py::test_canonical_bridge_v2_consumes_promoted_mechanism_at4_and_cad_at2`
(`:2051`) passed, covering mechanism@4/CAD@2 assertions, trusted re-verification,
fresh canonical verification, raw assembly-name rotation invariance, forged
mapping-hash rejection, foreign revision/state rejection, and candidate-vs-canonical
`physical_mechanism_hash` cross-track rejection (`:2074-2137`).

## Record-Shape / Store / Registry / Protected Files (check 4)

- The R-P5.5/P6 session adds **no new record schema or version**. It reuses the
  P4 `canonical-cad-realization@2` / `canonical-physical-cad-mapping@2` records and
  the P5 `physical-to-m10-v2-bridge@2` / `multi-joint-collision-pair-inventory@2`
  records. `CanonicalMultiJointM10Verification` and
  `CanonicalMultiJointM10VerificationService` already existed at HEAD
  (`HEAD:multi_joint_m10_bridge.py:514`). The T-P7.2 `@2` promotion family and
  `candidate-multi-joint-m10-provenance@1` envelope are Spec-mandated (§17/§18B)
  and are preserved/re-verified, not invented by the R-P5.5/P6 edits.
- No new store/service/registry: T-P7.2 reuses the existing `ArtifactStore` and the
  single existing `CandidateProvenanceArtifactService`
  (`provenance_artifacts.py:825`), adding only the MJ methods
  `publish_candidate_multi_joint_m10` / `resolve_candidate_multi_joint_m10` and the
  `CandidateMultiJointM10Provenance` model. No new `*Store`/`*Registry`/`*Service`
  class is introduced by this work.
- Protected byte pins (recomputed):

| Protected file | Required SHA-256 | Recomputed | Result |
|---|---|---|---|
| `src/mechcad_harness/multi_joint_kinematics.py` | `514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f` | same | MATCH |
| `src/mechcad_harness/multi_joint_collision_sweep.py` | `56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f` | same | MATCH |
| `tests/unit/test_m13_3_legacy_goldens.py` | `7dc391f10e545fc3291669a894a3c2a10729672eba9e847c1dca4dd88c8d5ba4` | same | MATCH |
| `src/mechcad_harness/multi_joint_pair_scope.py` | unchanged | `b593e0aa41b50a0dbc84c050f2396e0dba63b621fdd48cf3a7e185120706d344` | MATCH (clean) |
| `src/mechcad_harness/multi_joint_continuous_path.py` | unchanged | `c063ca8269392b68b911492f72071bdd5f7de30acd4461c98cad045a5574fa9b` | MATCH (clean) |
| `src/mechcad_harness/multi_joint_continuous_clearance.py` | unchanged | `66a62f30a7fe96c40f6cb049bf96906a427931b276ce9847dad42e6f95ad2bc5` | MATCH (clean) |

`git status --porcelain` reports the three protected source/golden files and the
three additional protected files (plus `README.md`) as clean/untracked-unchanged
from HEAD.

## Fresh Non-Live Test Subset (check 5)

All commands below used the repository virtual environment
(`.venv\Scripts\python.exe`, Python 3.14.6, pytest 9.1.1). No FreeCAD/Gmsh/
CalculiX or other live/external runtime was invoked.

```text
python -m pytest -q tests/unit/test_semantic_family_closure.py \
  tests/unit/test_candidate_multijoint_m10_v2.py \
  tests/unit/test_canonical_m10_v2.py \
  tests/unit/test_m12_canonical_reconstruction.py \
  tests/unit/test_promotion_v2.py \
  tests/unit/test_candidate_multi_joint_m10_provenance_v1.py
177 passed in 167.08s
```

```text
python -m pytest -q \
  "tests/integration/test_m12_promotion_production.py::test_canonical_bridge_v2_consumes_promoted_mechanism_at4_and_cad_at2"
1 passed, 1 warning in 23.55s
```

```text
python -m pytest -q tests/unit/test_m13_3_legacy_goldens.py
3 passed in 2.65s
```

```text
python -m compileall -q src/mechcad_harness
exit 0; no compile errors

git diff --check -- src/mechcad_harness/candidates/multi_joint_m10_bridge.py \
  src/mechcad_harness/candidates/canonical_cad.py \
  tests/integration/test_m12_promotion_production.py
exit 0; no whitespace diagnostics
```

## Pre-Existing / Unrelated Failures (check 6)

- **Four README-doc failures — established pre-existing and unrelated.**
  `README.md` is unmodified (`git diff HEAD --quiet -- README.md` returns clean;
  not in `git status`). The four named tests
  (`test_agent_docs.py::test_m6a1_boundaries_are_documented`,
  `test_section_docs.py::test_structural_extra_and_axis_contract_are_documented`,
  `test_section_engineering_docs.py::test_c3a_boundaries_are_documented`,
  `test_section_warping_docs.py::test_c2b_policy_and_boundaries_are_documented`)
  fail solely because `README.md` lacks expected phrases (`M6A-1`, `x = horizontal`,
  `M5.5C-3A`, `M5.5C-2B`, ...). Re-run here: **4 failed in 0.41s**. None of the
  three changed files is involved.
- **Two reported live integration failures — not executed by this audit (live
  runtimes out of scope); assessed by code-path inspection as unrelated to the
  three changed files.** The failing tests are in
  `tests/integration/test_m12_candidate_cad_m10_production.py`
  (`test_candidate_realization_rejects_unavailable_trusted_external_spur_artifact_without_downgrade`,
  `test_explicit_bounded_collision_fixture_is_candidate_bound_not_trusted_fallback`),
  both gated on `FREECAD_AVAILABLE`/`GEAR_AVAILABLE`. The reported failure occurs in
  fixture setup at `CandidateSourceBinding.bound_to` resolving
  `/yagi_payload_carrier_requirements/13` against a shorter state. Inspection shows
  `production_state()` provides 13 entries (indices 0–12), while
  `make_request` in `tests/integration/test_m12_revolute_drive_production.py:238-241`
  now adds geometry paths at `_GEOMETRY_INDEX_BASE = 13`, and
  `_build_gear_application`/`_build_live_application`
  (`test_m12_candidate_cad_m10_production.py:1717,1755`) call `production_state()`
  without appending the geometry identities. That mismatch lives entirely in
  broader dirty-worktree test files, none of which is one of the three changed
  files; `test_m12_promotion_production.py` is imported by, not imported into, that
  module and is not on the failure path.
  - Explicit caveat: because this audit did not execute the live tests, it
    establishes only that they are **unrelated to the three changed files**. It does
    **not** establish they were already failing at HEAD (the geometry-path fixture
    requirement is itself part of the broader dirty worktree). The evidence record's
    own attribution to "dirty concurrent-work fixtures" is consistent with this
    finding.

## No Other Accepted Plan Gate Weakened or Skipped (check 7)

- The R-P5.5 edits are confined to the symbol/version/track targets named by the
  accepted Plan (`_derive_candidate_multi_joint_bridge_v2`, `_build_request_v2`,
  `_validate_chain_v2` @2 branches). Legacy @1 sites (`build_request` tail,
  `_validate_chain`/legacy `select`, `compile_candidate` tail / bridge@1,
  `compile_canonical`) remain untouched, matching the Plan's explicit EXCLUSIONS.
- The P6 canonical bridge is mandated by normative Spec §6C/§14 (canonical track
  uses `canonical-physical-mechanism@4.mechanism_hash`; cross-track substitution
  fails) and Spec test 85. Observation: the accepted Plan's T-P6.1/T-P6.2 file
  targets name `candidates/canonical_m10.py`; the canonical multi-joint bridge
  extension lives in `candidates/multi_joint_m10_bridge.py` and is a canonical-track
  extension required by §6C/§14. This is a Plan/file-location observation, not a
  weakened or skipped gate; no legacy or canonical `@1` behavior is changed.
- R-P5.M10 protected files and the legacy golden remain byte-identical to their
  pins; `test_m13_3_legacy_goldens.py` passes.
- The R-P5.M10 historical NOT PROVEN / NOT EXECUTED boundary is preserved and not
  upgraded by this record.

## Gate Status and Scope

- R-P5.5 candidate-track rebind: **VERIFIED** at the pinned bytes.
- R-P5.6 / P5.3 representative non-live regression subset: **GREEN**.
- P6 canonical `@4`/CAD `@2` multi-joint bridge: **VERIFIED**; legacy
  `CanonicalPhysicalCadCompiler` behavior unaltered.
- T-P7.2 promotion `@2` / MJ typed-parent provenance regression: **GREEN**.
- Broad non-live gate: green except the four established pre-existing README-doc
  failures.
- Historical equality: **NOT PROVEN** (preserved).
- This record is implementation evidence acceptance only; it does **not** authorize
  commit, release, P5.3 positive resumption beyond the audited gates, complete P5,
  P7, default activation, or live verification.

Only this audit record was created. Production code, tests, the Plan, the Spec,
reconstruction, and existing audits were inspected read-only. No commit or push
was made.
