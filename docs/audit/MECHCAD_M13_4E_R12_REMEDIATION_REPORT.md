# M13-4E R12 Remediation Report

## Input Audit Verdict

```text
M13_4E_INDEPENDENT_R12_REJECTED
```

This remediation addresses only `CRITICAL R12-01` and `IMPORTANT R12-02`. It
does not perform a new independent acceptance audit.

## Scope

- `src/mechcad_harness/candidates/promotion.py`
- `tests/unit/test_m13_4e_promotion_application.py`
- M13-4E candidate evidence reports

No M13-3, M10, CAD, state-schema, dependency, legacy-promotion, or application
surface changed.

## R12-01 Root Cause

The generic exception branch after `apply_approved_proposal()` could issue a
post-apply receipt solely from a reloaded run's `active_revision` and
`active_state_hash`. It did not reload the claimed revision from `StateManager`.

## R12-01 Implementation

The generic branch now uses the run only to identify a possible applied
revision. It reloads the exact revision from `StateManager`, requires the
loaded state's revision and `state_hash` to equal the run claim, and only then
returns `PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED`. Any load or equality
failure follows the existing `PRE_APPLY_FAILURE` path with no applied identity.

A private typed-run validation immediately after the real controller result
provides a narrow test seam for unexpected post-application exceptions. It does
not change controller application mechanics or fabricate authority.

## Generic Exception Regression Matrix

```text
py -3 -m pytest tests/unit/test_m13_4e_promotion_application.py -k "generic_post_apply" -q
5 passed, 13 deselected in 9.16s
```

The cases use real state/run/change machinery and cover:

- valid persisted N+1, which may be claimed;
- missing N+1 snapshot;
- durable N+1 load failure;
- run state-hash mismatch;
- run revision mismatch.

The injected exception occurs after real controller application. The tests do
not monkeypatch `apply_approved_proposal()` and do not fabricate snapshots or
`AppliedChangeResult` values.

## Post-Apply Branch Audit

| Branch | Can N+1 exist? | Proof before N+1 receipt | Result artifact |
| --- | --- | --- | --- |
| Typed run-transition error | Yes | typed ChangeEngine applied snapshot | Absent |
| Typed invalidation error | Yes | typed ChangeEngine applied snapshot | Absent |
| Generic recovery | Possible | exact `StateManager.load_revision` revision/hash match | Absent |
| Generic recovery cannot prove N+1 | Unknown | no receipt claims N+1 | Absent |
| Invalidation verification failure | Yes | returned N+1 is checked by receipt verifier | Absent |
| Result provenance failure | Yes | returned N+1 is checked by receipt verifier | Absent |
| Complete route | Yes | result/invalidation/state/run full verifier | Trusted ID |

## Identity / Ordering Regression

The remediation does not alter compilation, projection, or mapping code.
Original `compile_multi_joint()` identity, independent projection/mapping order,
and exact typed mapping pairing remain unchanged.

## R6 Regression

```text
py -3 -m pytest tests/unit/test_m13_4e_promotion_evidence.py -k "rehash_substitution or swapped_pairing" -q
12 passed, 32 deselected in 19.88s
```

## R8 / R9 Regression

R8 restart and R9 artifact-local resolver tests are included in the focused
M13-4E suite below. The R12-01 route fix adds no nonlocal dependency to the
artifact-local resolver.

## Focused Gate

```text
py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q
116 passed in 127.28s
```

Required M13-4E skips: `0`.

## Predecessor Gate

```text
py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q
75 passed in 36.64s
```

## Fresh Full Suite

```text
py -3 -m pytest -q -rs
2811 passed, 34 skipped in 3255.73s (0:54:15)
```

The command completed within the 7200-second ceiling. The 34 skips are:
OpenCode live-validation opt-ins, unavailable structural profile, unavailable
materials extra, and unavailable FreeCAD/FreeCADCmd runtime. None is a required
M13-4E skip.

## Skip Audit

```text
REQUIRED_M13_4E_SKIPS = 0
```

The historical FreeCAD timeout remains `UNVERIFIABLE`.

## Static / Protected Surface Audit

`py -3 -m compileall src tests` and `git diff --check` passed. Targeted searches
found no candidate-production `SimpleNamespace` or
`_align_multi_joint_evidence_compilation`. The only generic recovery path that
can claim N+1 now contains the intervening exact durable state reload.

## Remaining Findings

No known R12-01 or R12-02 blocker remains. Independent re-audit is still
required; this report does not assert acceptance.

## Candidate Status

```text
M13_4E_R12_REMEDIATION_READY_FOR_REAUDIT
M13_4E_ACCEPTANCE_STATUS = PENDING_INDEPENDENT_REAUDIT
M13_4P_MAY_RESUME = NO
M13_4_MAY_RESUME = NO
ROTATOR_V2_MAY_RESUME = NO
```
