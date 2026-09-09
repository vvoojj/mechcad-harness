# M13-4 Independent Third Re-Audit

## Verdict

```text
M13_4_INDEPENDENT_THIRD_REAUDIT_REJECTED
M13_4_ACCEPTANCE_STATUS = REJECTED
ROTATOR_V2_MAY_RESUME = NO
```

The third test-only remediation closes `M13-4-SECOND-REAUDIT-CRIT-01`: it now
proves concrete exact-pair coverage for every candidate and canonical
configuration. Acceptance is nevertheless rejected because the independently
fresh full suite completed with one failure in the M13-4 capstone. A real
FreeCAD subprocess timed out during selection replay.

## Independence

This audit did not modify production code, tests, acceptance criteria, prior
reports, goldens, or hashes; commit, tag, push, and Rotator V2 actions were not
performed. This report is the only intentional repository write. The completion
report was treated as a candidate claim, not acceptance evidence.

## Historical Findings

The controlling second independent re-audit rejected only
`M13-4-SECOND-REAUDIT-CRIT-01`, after closing:

- `M13-4-REAUDIT-CRIT-01`
- `M13-4-REAUDIT-CRIT-02`
- `M13-4-REAUDIT-IMP-01`
- `M13-4-REAUDIT-MINOR-PROJECT-ID`

## Third Remediation Scope

The candidate report claims semantic changes only in
`tests/integration/test_m13_4_full_stack_acceptance.py` and
`docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md`. The observed tracked
`src/mechcad_harness/` diff is the documented pre-existing M13-4E/M13-4P dirty
surface; no third-remediation production semantic change was identified. No
predecessor golden/hash update is present.

## Worktree / Protected Surface

`git status --short`, `git diff --stat`, `git diff`, and `git diff --check`
were run. The tracked diff remains limited to `.coverage`, `.superpowers/sdd`,
and the accepted pre-existing M13-4E/M13-4P `src/mechcad_harness/` changes.
M13-4 materials are untracked in this worktree. `git diff --check` passes with
only pre-existing CRLF normalization warnings. `py -3 -m compileall -q src tests`
passes.

## SECOND-REAUDIT-CRIT-01

### Dead-Code Root Cause

The former unreachable assertions after the unconditional return in
`_assert_durable_canonical_m10_evidence()` are absent. That function now ends
at its valid `return reloaded` on test line 181. No acceptance assertion follows
that return and no remaining assertion there references unavailable `result` or
`expected_pair_count` locals.

### Pair Identity Contract

`_normalized_pair_identity()` reads `first_instance_id` and
`second_instance_id`, rejects blank strings and self-pairs, and normalizes the
unordered concrete pair as `tuple(sorted((first, second)))`. These are the
accepted production M10 v2 fields: `ExactConstituentPair` uses them for request
scope and `ExactConstituentPairResultV2` uses them for measurements. Production
scope semantics are unordered and canonicalized lexically by
`multi_joint_pair_scope.py`; scope ordering is not an additional acceptance
requirement.

### Expected Scope Source

`_assert_exact_pair_coverage(exact_pair_scope, configuration_results)` derives
the expected set only from its supplied `exact_pair_scope`. Candidate calls pass
`request.exact_pair_scope` at test line 626. Canonical calls pass
`canonical_m10.request.exact_pair_scope` at lines 820 and 1432. Neither uses a
hard-coded eleven-pair list, a hash, an opposite-phase scope, or a count as
authority.

### Candidate Coverage

Candidate M10 has actual scope length 11. For all four configuration results,
the helper obtains actual identities only from `configuration.pair_results`,
requires actual count equal to scope count, uniqueness, and exact set equality.
This proves no duplicate, missing, or unexpected concrete pair can pass.

### Canonical Coverage

Fresh canonical M10 separately invokes the identical coverage proof with its
own canonical request scope in both the capstone and scalar-restart path. It
therefore does not reuse the candidate scope as canonical truth.

### Uniqueness

The expected scope must itself be unique. Each configuration's actual identity
tuple must have the expected count and `len(set(actual_pairs))` equal to that
count before its identity set is compared. Blank IDs and self-pairs fail during
normalization, and valid unordered pairs cannot collapse except when they are
the same concrete pair, which is correctly rejected as a duplicate.

### Missing / Unexpected Pair Detection

Set equality compares independently-derived expected scope identities with
actual result identities. It rejects both an omitted expected pair and an
unexpected measured pair. This is non-circular: expected data comes from the
request, actual data comes from the result.

### Negative Same-Count Test

`test_m13_4_exact_pair_coverage_rejects_duplicate_for_omitted_pair` creates
two expected pairs, then creates results containing the first pair twice and
omitting the second, preserving total count two. It passed independently:

```text
1 passed, 3 deselected in 2.33s
```

The helper rejects at its uniqueness assertion with `AssertionError` matching
`duplicate` (`measured pair results contain a duplicate identity`).

### motor-r / shaft-a

The fixture's 15-pair policy remains three `SAME_RIGID_GROUP_EXCLUDED`, one
truthful J2 `INTENDED_CONTACT_EXCLUDED`, and eleven `CHECK_CLEARANCE` pairs.
`motor-r/shaft-a` is `CHECK_CLEARANCE`, occurs in candidate exact scope, and is
explicitly asserted present in every candidate configuration. The full exact
coverage invariant also proves it occurs exactly once per configuration.

## Closed-Finding Regression

### Pair Policy

No regression found. The current fixture excludes only the three same-rigid-body
pairs and `hub-a/shaft-b` for the declared J2 contact.

### Restart

No regression found in the changed test surface: Phase B uses
`locator["project_id"]`, receives scalar locator data, reconstructs canonical
authority before reading the diagnostic snapshot, and binds revision 2.

### Semantic Snapshot

No regression found. The persisted primitive snapshot still includes exact
scope, tolerances, placement derivations, and member/body offsets.

### Compilation

No regression found. The capstone retains the one-call observation and full
receipt compilation/projection/mapping equality checks.

### Canonical Evidence

No regression found. The durable canonical M10 Evidence helper retains full
request/result, assembly/model, scope/tolerance, provenance, and currentness
checks.

## FreeCAD Runtime

Configured executable:

```text
C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe
Test-Path: True
FreeCAD 1.1.3 Revision: 20260725 (Git shallow)
```

Focused routes used the real configured FreeCAD subprocess path. No fake
provider or MCP substitute was credited.

## Focused Tests

```text
Negative coverage selector: 1 passed, 3 deselected in 2.33s
Exact capstone selector: 1 passed, 3 deselected in 114.38s
Full M13-4: 4 passed in 214.38s
Post-full-suite capstone selector: 1 passed, 3 deselected in 88.79s
```

All focused M13-4 runs had zero skips.

## M13-4P

```text
8 passed in 17.35s
```

## M13-4E

```text
116 passed in 142.55s
```

## Predecessor

```text
75 passed in 42.65s
```

## Required Regression

The exact required M10/M12/CAD/provenance group passed:

```text
757 passed in 368.69s
```

## Full Suite

The first independent invocation used a 7000-second timeout and was terminated
by the harness at approximately 85% without a summary. The retry used a
12000-second timeout and completed, but failed:

```text
1 failed, 2831 passed, 25 skipped in 4270.96s
```

The failure was
`test_m13_4_representative_canonical_m10_full_stack_capstone`. During
`ProductionApplication.select_candidate_multi_joint()`, the trusted candidate
M10 replay reached the real FreeCAD transient measurement subprocess. Its
production `FreeCADBackend._run(..., timeout_seconds=120.0)` raised
`FreeCADExecutionError: FreeCADCmd timed out`, surfaced as
`ValueError: candidate multi-joint selection trusted M10 replay failed`.

The later standalone capstone selector passing confirms the failure is
full-suite-sensitive runtime timeout behavior. It does not change the failed
fresh full-suite result and cannot be accepted as a passing full suite.

## Skip Audit

The full-suite `-rs` output reported exactly 25 skips:

- 6 OpenCode live-validation opt-ins.
- 5 unavailable materials-extra tests.
- 14 unavailable structural-profile tests.

No M13-4 test was skipped; the required capstone failed instead.

## Static Audit

`py -3 -m compileall -q src tests` and `git diff --check` pass. No
third-remediation production semantic or predecessor golden/hash change was
identified.

## New Findings

### CRITICAL

- **M13-4-THIRD-REAUDIT-CRIT-01: fresh full suite does not reliably complete the required live M13-4 capstone.**
  - Requirement: the fresh full suite must finish with zero failures and errors.
  - Evidence: the 12000-second independently-run suite completed with one failure, `2831 passed, 25 skipped in 4270.96s`; selection replay's real FreeCAD command exceeded its 120-second production timeout.
  - File/symbol: `src/mechcad_harness/backends/freecad.py:FreeCADBackend._run`, reached from `CandidateMultiJointSelectionService.select` during `test_m13_4_representative_canonical_m10_full_stack_capstone`.
  - Acceptance impact: the required fresh full-suite gate fails. Focused success does not replace full-suite success.
  - Minimal remediation boundary: investigate the live FreeCAD timeout/replay performance and establish a passing fresh full suite; do not alter M13-4 acceptance criteria or weaken timeout/error semantics without separate authority.

### IMPORTANT

None.

### MINOR

None.

### NOTES

- The standalone capstone passes before and after the failing full-suite run, so
  the exact-pair coverage repair itself is live-executable.
- This audit does not diagnose a production fix; the observed full-suite failure
  is sufficient to block acceptance.

## Prior Finding Adjudication

```text
M13-4-SECOND-REAUDIT-CRIT-01 = CLOSED
M13-4-REAUDIT-CRIT-01 = CLOSED
M13-4-REAUDIT-CRIT-02 = CLOSED
M13-4-REAUDIT-IMP-01 = CLOSED
M13-4-REAUDIT-MINOR-PROJECT-ID = CLOSED
```

The second re-audit finding is closed, not replaced: the independent scope/result
identity proof and pure same-count negative directly close its stated defect.
The new full-suite failure is a separate blocking finding.

## Acceptance Decision

Exact pair coverage, scope authority, candidate/canonical independence,
motor-r/shaft-a coverage, all four configurations, closed-finding spot checks,
FreeCAD runtime, focused tests, predecessor gates, required regression, and
static checks pass. The mandatory fresh full suite fails, so the acceptance
standard is not met.

```text
M13_4_INDEPENDENT_THIRD_REAUDIT_REJECTED
M13_4_ACCEPTANCE_STATUS = REJECTED
```

## Downstream Authorization

```text
ROTATOR_V2_MAY_RESUME = NO
```
