# Deterministic STEP Content Identity - T-P8.2 Broad Regression Record

## Verdict

```text
Epic:
Deterministic STEP Content Identity

Gate:
T-P8.2 broad non-live risk-gated regression

Prerequisite:
T-P8.1 coverage closure independently accepted
(MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_1_COVERAGE_CLOSED_GREEN)

Controlling Spec:
DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68

Controlling Plan:
E449C60B641DBB5A4A630CC61553F5E586127443DC92B24BD5D983E3A15BB70E

Observed HEAD:
05da8edad18488492f02be1dad9d1ec3653ce807

Disposition:
PASS (broad non-live gate)
```

This record covers the exact invocations below on the exact byte state above.
A passing count is evidence only for the invocation that produced it. No live
(`*_live.py` or FreeCAD-invoking) test is credited here.

## Gate Definition (from accepted Plan T-P8.2)

```text
at minimum all:
  tests/unit/test_m12_*
  tests/unit/test_m13_*
  tests/unit/test_candidate_*
  tests/unit/test_canonical_*
  tests/unit/test_multi_joint_*
  tests/unit/test_structural_*
plus:
  tests/integration/test_m12_candidate_cad_m10_production.py
  tests/integration/test_m12_promotion_production.py
NO live (*_live.py) tests.
```

## Fresh Invocation Results

### Unit suite (100 files)

```text
command:
  python -m pytest <tests/unit/test_m12_*.py, test_m13_*.py, test_candidate_*.py,
    test_canonical_*.py, test_multi_joint_*.py, test_structural_*.py> -q

result:
  2253 passed
  0 failed
  0 errors
  0 skipped
  0 deselected
  no timeouts
  no aborts
  no environment events
```

### Required integration production paths (non-live)

```text
command:
  python -m pytest tests/integration/test_m12_candidate_cad_m10_production.py \
    tests/integration/test_m12_promotion_production.py -q -k "not live"

result:
  31 passed
  7 deselected (live-named tests, deliberately excluded)
  0 failed
```

## Non-Gate Observation (recorded, not credited)

While probing the broader integration tree, `tests/integration/test_m12_6_end_to_end_direct_drive.py`
was also run. That module invokes real FreeCAD (`discover_freecad().require_available()`,
`C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe`) and is therefore a LIVE-invoking
integration test, outside the accepted T-P8.2 non-live gate. It reported:

```text
4 failed, 19 passed, 1 skipped, 4 deselected
```

The four failures assert an exact promotion run-directory set:

```text
tests/integration/test_m12_6_end_to_end_direct_drive.py
  test_direct_drive_canonical_restart_round_trip_and_scope_isolation
  test_direct_drive_m11_handoff_is_non_gating[m11_intent1-unresolved]
  test_direct_drive_m11_handoff_is_non_gating[m11_intent0-not_eligible]
  test_direct_drive_durable_provenance_survives_restart
```

Observed cause: an extra `PUBLISH` run directory. `CandidatePublicationService._RUN_ID = "PUBLISH"`
exists in HEAD; the pre-existing (uncommitted) worktree provenance-publication additions
in `candidates/services.py` / `application.py` create that run directory. This is a
pre-existing worktree condition on the legacy production path, NOT caused by the
B1-B8 remediation (which touched only `CandidatePromotionCompilerV2.validate_readiness_v2` /
`validate_multi_joint_readiness_v2` and test files, none of which are on this legacy
path). It is recorded here as an environment/finding note and is outside the accepted
T-P8.2 gate. It is not credited as a pass and not used to claim P8.2 green.

## Boundary

This record does NOT claim:

```text
T-P8.4a activation
T-P8.3 live verification
final implementation acceptance
commit / release / deployment
```

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_2_BROAD_REGRESSION_PASS
