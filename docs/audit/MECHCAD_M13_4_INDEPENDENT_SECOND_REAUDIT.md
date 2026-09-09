# M13-4 Independent Second Re-Audit

## Verdict

```text
M13_4_INDEPENDENT_SECOND_REAUDIT_REJECTED
M13_4_ACCEPTANCE_STATUS = REJECTED
ROTATOR_V2_MAY_RESUME = NO
```

The second fixture/test-only remediation closes the prior pair-policy, restart
snapshot, compilation, Evidence, and project-identity findings. It does not
prove the required complete exact-result coverage for all eleven checked pairs
in every configuration. The mandatory M13-4 acceptance requirement therefore
remains unmet.

## Audit Independence

This audit did not implement or remediate M13-4, edit production or test code,
commit, tag, push, or start Rotator V2. This report is the only intentional
repository write. The completion report was treated as a candidate claim, not
as acceptance evidence.

## Scope And Protected Surface

Reviewed second-remediation changes are confined to the M13-4 fixture/test and
documentation. No new M13-4 semantic production change was found under
`src/mechcad_harness/`; the existing dirty M13-4E/M13-4P source surface is not
attributed to this remediation. `git diff --check` exits zero, with only the
pre-existing CRLF normalization warnings.

## Runtime

The audit explicitly configured:

```text
MECHCAD_FREECADCMD=C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe
```

The executable exists and reports FreeCAD 1.1.3 Revision 20260725. The focused
M13-4 route executed through the configured real FreeCAD subprocess boundary.

## Prior Finding Adjudication

```text
M13-4-REAUDIT-CRIT-01 = CLOSED
M13-4-REAUDIT-CRIT-02 = CLOSED
M13-4-REAUDIT-IMP-01  = CLOSED
M13-4-REAUDIT-MINOR-PROJECT-ID = CLOSED
```

### M13-4-REAUDIT-CRIT-01

Closed. `motor-r/shaft-a` is no longer excluded in
`m13_4_acceptance_fixtures.py:683-715`. The fifteen-pair policy now has three
truthful same-rigid-body exclusions, one J2 intended-contact exclusion
(`hub-a/shaft-b`), and eleven `CHECK_CLEARANCE` pairs. The candidate request
includes `motor-r/shaft-a`, and its result contains that pair in all four
configurations (`test_m13_4_full_stack_acceptance.py:562-580`).

### M13-4-REAUDIT-CRIT-02

Closed. Phase A persists primitive JSON snapshot, receipt, and locator files.
Phase B receives only the locator path, composes its fresh application with
`locator["project_id"]`, reconstructs and executes canonical CAD/M10 before
reading the diagnostic snapshot, then compares the complete snapshot
(`test_m13_4_full_stack_acceptance.py:1199-1268, 1271-1414`). The snapshot now
includes body/member offsets, derivations, exact scope, and both tolerances.

### M13-4-REAUDIT-IMP-01

Closed. The observed original compilation is directly compared with
`receipt.compilation`, including compilation/projection/mapping identities. The
fresh root re-verifies the serialized receipt and resolves durable decision and
result artifacts. Canonical M10 Evidence is reloaded and bound to the canonical
revision/state, assembly/model, configurations, exact scope, tolerances,
request/result identities, provider/backend/runtime provenance, and currentness
(`test_m13_4_full_stack_acceptance.py:82-121, 644-688, 1311-1392`).

### M13-4-REAUDIT-MINOR-PROJECT-ID

Closed. The fresh Phase-B root receives `locator["project_id"]` at lines
1284-1289. The fixture constant is retained only for the explicit diagnostic
equality assertion at line 1273.

## New Finding

### CRITICAL: M13-4-SECOND-REAUDIT-CRIT-01

**The capstone does not prove that every exact-scope pair is measured exactly
once in every configuration.**

The controlling execution plan requires that every configuration contain every
checked concrete pair exactly once. The candidate test proves only the result
count is eleven and that `motor-r/shaft-a` occurs in each configuration
(`test_m13_4_full_stack_acceptance.py:562-581`). It never compares each
configuration's pair-ID set to `request.exact_pair_scope`. Canonical execution
proves only the same count through `_assert_m10_result` at lines 63-79 and
1385.

The only apparent uniqueness/identity assertions are unreachable because
`_assert_durable_canonical_m10_evidence()` returns at line 121; the assertions
at lines 122-136 follow that return. They also reference unavailable local
names (`result` and `expected_pair_count`), confirming they cannot provide the
intended coverage proof.

**Impact:** eleven results could include a duplicate pair while omitting another
required pair. The live run establishes execution count and the repaired
`motor-r/shaft-a` case, but it does not establish complete measurement coverage
for the final eleven-pair authority in either candidate or canonical execution.

**Minimal remediation:** test-only. For candidate and fresh canonical results,
derive the expected ordered or normalized concrete pair set from the respective
`exact_pair_scope` and assert exact equality with every configuration's
`pair_results`, including uniqueness and nonempty distinct IDs. Keep the
existing real FreeCAD route and do not alter production semantics.

## Verification Evidence

```text
FreeCAD version check: FreeCAD 1.1.3 Revision 20260725 (Git shallow)
Focused M13-4: 3 passed in 210.67s
M13-4P selector: 18 passed, 239 deselected in 36.15s
M13-4E exact gate: 116 passed in 143.75s
M13-3/predecessor exact gate: 75 passed in 37.20s
M10/M12/CAD/provenance exact group: 757 passed in 384.74s
compileall: passed
```

The full suite was not credited: the first invocation was user-aborted after
approximately 55% with one failure displayed, and the subsequent `-x` attempt
exceeded the 900-second harness timeout after approximately 15%. Repository-wide
`ruff check src tests` also reports pre-existing unrelated lint failures; it is
not an M13-4 acceptance gate and was not used to assess the finding.

## Acceptance Decision

The prior re-audit findings are closed, but the new critical proof gap blocks
acceptance. Passing execution counts cannot substitute for an assertion that
the executor measured every required pair exactly once.

```text
M13_4_INDEPENDENT_SECOND_REAUDIT_REJECTED
M13_4_ACCEPTANCE_STATUS = REJECTED
ROTATOR_V2_MAY_RESUME = NO
```
