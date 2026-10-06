# Deterministic STEP Content Identity Epic - Final Independent Acceptance

## Verdict

```text
Epic:
Deterministic STEP Content Identity

Controlling Spec:
docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md
SHA-256: DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68
(UNCHANGED through the entire Epic)

Controlling Plan:
docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md
SHA-256: E449C60B641DBB5A4A630CC61553F5E586127443DC92B24BD5D983E3A15BB70E
(UNCHANGED through the entire Epic)

Observed HEAD:
05da8edad18488492f02be1dad9d1ec3653ce807

Disposition:
EPIC IMPLEMENTATION INDEPENDENTLY ACCEPTED

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_EPIC_INDEPENDENTLY_ACCEPTED
```

This is an implementation-verification acceptance for the exact byte state
above. It is not a commit, release, deployment, or production-release approval.

## Gate Chain (each independently verified)

```text
T-P8.1  coverage closure          MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_1_COVERAGE_CLOSED_GREEN
T-P8.2  broad non-live regression PASS
T-P8.4a coded final activation    MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_4A_ACTIVATION_INDEPENDENTLY_VERIFIED
T-P8.3  live verification         MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_3_LIVE_VERIFIED
Final   implementation audit      MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_EPIC_INDEPENDENTLY_ACCEPTED
```

Records:

```text
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_1_COVERAGE_CLOSED_GREEN.md
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_2_BROAD_REGRESSION.md
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_4A_ACTIVATION_INDEPENDENT_VERIFICATION.md
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_3_LIVE_VERIFICATION.md
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_EPIC_INDEPENDENT_ACCEPTANCE.md
```

## What Was Resolved

- **B1 SPEC_AMBIGUITY**: Case 92's "promotion@2 semantic hashes" resolved as the
  full applicable promotion@2 family by contextual reading of §17, §21, and
  Cases 89/93. No Spec revision was required; the Spec SHA is unchanged.
- **B2-B8 TEST_COVERAGE_GAPs**: closed with new/strengthened tests (genuine
  fresh-process restart; literal 9-row T-P2.6 route matrix; Case 93
  unresolved-items multiset + V2 gate; genuine mechanical closure for cases
  40/43/46/67; Case 90 connection/joint reversal propagation; Case 26 N1/N2
  self-hash exclusion; Case 89/92 applicable promotion@2 family).
- **Two minimal Spec-required production corrections**:
  `CandidatePromotionCompilerV2.validate_readiness_v2` /
  `validate_multi_joint_readiness_v2` now reject non-empty `unresolved_items`
  (Spec §6C / Case 93); and `application.py:_validate_candidate_m12_3_result`
  schema-dispatches the M12-3 source-binding comparison.
- **T-P8.4a activation**: `ProductionApplication.realize_and_evaluate_revolute_drive`
  now emits the new homogeneous family for `candidate-synthesis-request@2`
  (trusted bind → candidate@2 → integrity → contextual currentness →
  `revolute-drive-admissibility@2`), while the `@1` legacy replay dispatch is
  preserved per Spec §20.
- **T-P8.3 live verification**: real FreeCAD 1.1.3 subprocess boundary; raw
  SHA differs / `step-content-identity@1` and downstream semantic identities
  equal under timestamp-only rotation; fresh-process restart; real engineering
  change differs.

## Evidence Levels

```text
DESIGNED               Spec DE17C360 normative contract
IMPLEMENTED            production code in src/mechcad_harness
TESTED                 unit + integration suites (fresh invocations recorded per gate)
PRODUCTION_COMPOSED    realize_and_evaluate_revolute_drive @2 default
RUNTIME_VERIFIED       post-activation composition + mixed-version + restart gates
LIVE_VERIFIED          real FreeCAD 1.1.3 subprocess (T-P8.3)
INDEPENDENTLY_ACCEPTED T-P8.1 / T-P8.4a / T-P8.3 / final implementation audit
```

## Capability Boundaries (not overstated)

- Promotion@2 is NOT activated (T-P7.2 unactivated). The activated default is
  bounded to `realize_and_evaluate_revolute_drive` (request@2 → candidate@2 →
  `revolute-drive-admissibility@2`). `realize_candidate_cad`, `evaluate_candidate`,
  and the promotion entrypoints remain reject-only for the `@2` family.
- No Gmsh/CalculiX solver execution, no M11 structural analysis, no assembly FEA,
  no whole-configuration-space certification, no manufacturing/safety approval.
- The `@1` path is historical replay/compatibility dispatch, not new-family
  production.
- This acceptance is bounded to the exact byte state above and to the bounded
  live scenario recorded in the T-P8.3 record.

## Protected Surfaces

```text
src/mechcad_harness/multi_joint_kinematics.py
  514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f  (UNCHANGED)
src/mechcad_harness/multi_joint_collision_sweep.py
  56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f  (UNCHANGED)
tests/unit/test_m13_3_legacy_goldens.py  (UNCHANGED from HEAD)
projects/mini_rotary_fixture/**          (UNTOUCHED)
accepted audits / reconstruction records (UNTOUCHED)
```

## Recorded Non-Blocking Limitations

1. Promotion@2 owner records (compilation/projection/manifests/verification) are
   not causally constructible; promotion@2 remains reject-only under T-P7.2.
2. The Plan's "reject `@1`" wording is a documentation/implementation gap; the
   implementation follows Spec §20 schema-version dispatch. No Spec or Plan bytes
   were changed.
3. A pre-existing, non-gate condition: 4 failures in the live-invoking
   `tests/integration/test_m12_6_end_to_end_direct_drive.py` from an extra
   `PUBLISH` run directory (legacy path, unrelated to this Epic's remediation).

## Not Claimed

```text
commit / push / tag / release / deploy (require separate H5 authorization)
production release / deployment
whole-configuration-space certification
```

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_EPIC_INDEPENDENTLY_ACCEPTED
