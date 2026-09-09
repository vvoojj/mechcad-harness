# M13-4 Independent Final Acceptance

## Verdict

```text
M13_4_INDEPENDENT_FINAL_ACCEPTED
M13_4_ACCEPTANCE_STATUS = ACCEPTED
ROTATOR_V2_MAY_RESUME = YES
```

## Independence

This was an audit-only runtime-recovery review. No production code, test,
timeout, retry, execution semantic, fixture, golden, or hash was changed.
No commit, tag, push, or Rotator V2 action was performed. This report is the
only intentional repository write. The completion report's recovery section was
treated as a claim and was independently checked against runtime records and the
durable full-suite output.

## Historical Runtime Failure

The third re-audit correctly recorded one failed fresh suite:

```text
2831 passed, 25 skipped, 1 failed in 4270.96s
```

The failed test was the M13-4 capstone. Candidate-selection trusted M10 replay
reached `FreeCADBackend._run()` and a real FreeCADCmd subprocess exceeded the
production 120-second timeout. That result was blocking at the time and is not
rewritten as a passing run.

## Runtime-Recovery Scope

The sole finding under review was:

```text
M13-4-THIRD-REAUDIT-CRIT-01
```

No previously closed substantive M13-4 finding was reopened without regression
evidence.

## Unchanged-Code Proof

The current worktree's recovery-related surfaces were inspected. There is no
diff for either:

```text
src/mechcad_harness/backends/freecad.py
tests/integration/test_m13_4_full_stack_acceptance.py
```

Current SHA-256 values are:

```text
freecad.py: AB124F06BA04A0D2B162D65AC5E280D5ACDF6C8DCB9FE5CD929F65B4E177E5FC
test_m13_4_full_stack_acceptance.py: 973F0EA4C51FB7BE67B5647BEE6ADE597DA5A9DD8A5970C10AE06EFE4F2E8474
```

The candidate recovery record does not contain independently comparable pre-run
and post-run source hashes. The direct current-code inspection establishes that
the recovery did not introduce a tracked runtime-production diff; its stated
test file remains an untracked accepted M13-4 material in this dirty worktree.

`FreeCADBackend._run()` remains a single `subprocess.run()` call with
`timeout_seconds: float = 120.0`, maps `TimeoutExpired` to
`FreeCADExecutionError`, and has no retry path (`freecad.py:272-280`). No M10
or provider execution semantics were changed.

## FreeCAD Runtime

```text
MECHCAD_FREECADCMD=C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe
Test-Path: True
FreeCAD 1.1.3 Revision: 20260725 (Git shallow)
```

The independent capstone used this configured production FreeCADCmd subprocess
path. No fake provider or MCP substitute was credited.

## Power / Sleep Configuration

Read-only `powercfg` inspection reports active `SCHEME_BALANCED`. Current AC
standby and hibernate timeouts are both `0x00000000` (disabled). No battery was
reported by `Win32_Battery`; this is an AC desktop configuration. This audit did
not change any power setting.

## Historical Sleep Events

The inferred failed-suite interval is 2026-09-09 07:46:44 through 08:57:55
local time. Windows System records contain:

```text
08:29:18  Kernel-Power 187  application API requested suspend
08:29:20  Kernel-Power 42   entering sleep
08:29:21  Kernel-Power 107  resumed after sleep
08:40:02  Power-Troubleshooter 1  wake record
```

```text
HISTORICAL_SLEEP_EVENT = CONFIRMED
HOST_SLEEP_TIMEOUT_CAUSATION = PLAUSIBLE
```

The suspend/wake interval falls inside the prior failed full-suite window and
supports a transient host explanation. It does not prove the sleep event caused
the particular subprocess timeout, because the failed runner did not preserve a
per-subprocess start/end correlation.

## Controlled Run Sleep Audit

The controlled interval in the durable recovery log is:

```text
start: 2026-09-09T09:25:42.4827691+03:00
end:   2026-09-09T10:24:15.9267201+03:00
```

Read-only System-event inspection over that exact interval found zero
Kernel-Power suspend/resume or Power-Troubleshooter wake records.

```text
HOST_SLEEP_DURING_CONTROLLED_RUN = NO
```

`freecadcmd.exe` process counts were zero before the logged run according to the
recovery evidence and zero after this audit's independent capstone. A normal
FreeCAD GUI process was not treated as a failure.

## Baseline Capstone

The candidate controlled baseline record reports one run before its full suite:

```text
test_m13_4_representative_canonical_m10_full_stack_capstone
1 passed, 3 deselected
pytest: 104.08s
wall: 106.57s
exit code: 0
```

## Controlled Full-Suite Log

The durable log exists at:

```text
C:\Users\vvooj\AppData\Local\Temp\opencode\m13-4-runtime-controlled-fullsuite.log
```

It is a UTF-16 capture, 11,566 bytes, last written at the claimed controlled-run
end time. Its SHA-256 is:

```text
624791388E2A83CD74E2B8871E0798003AF3684709A6C44942607C8A837F3597
```

Direct decoding and inspection verifies the command output records:

```text
FULL_SUITE_START=2026-09-09T09:25:42.4827691+03:00
2832 passed, 25 skipped in 3497.88s (0:58:17)
FULL_SUITE_END=2026-09-09T10:24:15.9267201+03:00
FULL_SUITE_ELAPSED_SECONDS=3513.44
FULL_SUITE_EXIT_CODE=0
```

It contains neither a failure/error summary nor a timeout string. This is a
fresh controlled full-suite gate with unchanged production timeout semantics;
it satisfies the accepted plan's zero-failure/zero-error requirement.

## Independent Confirmation

This audit ran the exact capstone selector once, under the current no-sleep
configuration and configured FreeCADCmd:

```text
1 passed, 3 deselected in 107.80s
```

No FreeCAD timeout occurred. No independent second full suite was run: the
durable, complete controlled suite above is the decisive fresh gate, and this
audit adds the required independent focused runtime confirmation rather than
repeating a one-hour suite until a preferred result appears.

## Skip Audit

The durable `-rs` output lists exactly:

```text
OpenCode live-validation opt-in: 6
materials-extra unavailable: 5
structural-profile unavailable: 14
M13-4 skips: 0
total: 25
```

```text
M13_4_REQUIRED_SKIPS = 0
```

## Static / Protected Surface

```text
py -3 -m compileall -q src tests: passed
```

`git diff --check` emitted only existing CRLF normalization warnings. No
runtime-recovery production edit, timeout edit, retry edit, or predecessor
golden/hash update was identified.

## Runtime Classification

```text
FREECAD_TIMEOUT_TRANSIENT_ENVIRONMENT_VARIANCE
```

The historical application-API sleep event occurred within the failed-suite
interval. The unchanged code and unchanged 120-second timeout then completed a
full controlled no-sleep suite with zero failures, zero errors, and no timeout;
the exact controlled interval has no sleep/wake event. The independent capstone
also passed once in the same no-sleep environment. This evidence does not
establish a reproducible MechCAD production runtime defect.

## M13-4-THIRD-REAUDIT-CRIT-01 Adjudication

```text
M13-4-THIRD-REAUDIT-CRIT-01 = CLOSED
```

The prior failure is reasonably classified as sleep-contaminated transient
environmental variance, not a demonstrated production timeout defect. The
controlled full suite is complete, durable, and independently inspected; it
uses the unchanged execution path and timeout, has no M13-4 skip, and passes.

## Prior Closed Findings

No regression was found in the current acceptance surface:

```text
M13-4-SECOND-REAUDIT-CRIT-01 = CLOSED
M13-4-REAUDIT-CRIT-01 = CLOSED
M13-4-REAUDIT-CRIT-02 = CLOSED
M13-4-REAUDIT-IMP-01 = CLOSED
M13-4-REAUDIT-MINOR-PROJECT-ID = CLOSED
```

Current direct inspection confirms exact candidate/canonical pair-coverage
checks, scalar restart construction, original compilation equality, durable
canonical Evidence bindings, and the unchanged 120-second non-retrying
FreeCADCmd path.

## New Findings

No new CRITICAL or acceptance-blocking IMPORTANT finding was identified.

## Acceptance Decision

All substantive prior findings are closed. Real FreeCAD 1.1.3 is verified.
Timeout semantics remain unchanged. The controlled full-suite evidence passes
with zero M13-4 skips, compileall and diff checks pass, and no reproducible
production timeout defect is established.

```text
M13_4_INDEPENDENT_FINAL_ACCEPTED
M13_4_ACCEPTANCE_STATUS = ACCEPTED
ROTATOR_V2_MAY_RESUME = YES
```

## Downstream Authorization

```text
ROTATOR_V2_MAY_RESUME = YES
```
