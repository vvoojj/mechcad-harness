# MechCAD M0->M13 full verification — in-place mode

This runner verifies the existing worktree directly at:

`E:\repo\mechcad-harness`

It does NOT clone the repository and does NOT run checkout/reset/clean.
Existing tracked changes, if any, are verified as part of the current worktree byte state.
The runner records the initial Git status/diff and checks that verification does not mutate tracked bytes.

## Install

Copy only:

`run_full_verification_inplace.ps1`

to:

`E:\repo\mechcad-harness\run_full_verification_inplace.ps1`

## Evidence output

Evidence is written inside the same repository under:

`E:\repo\mechcad-harness\.verification-runs\full-m0-m13-<timestamp>-4675c6cdaaf6\`

This directory contains logs, JUnit XML, initial/final Git evidence, milestone summaries, and SUMMARY.txt.
No repository snapshot is created.

The dedicated post-M13 T-P8.3 test still creates its accepted fresh isolated workspace at:

`E:\repo\mechcad-harness\.tmp-live-m12\tp8_3_mini_replay\`

It does not reuse `projects\mini_rotary_fixture`.

## Run

Open PowerShell:

```powershell
cd E:\repo\mechcad-harness
Set-ExecutionPolicy -Scope Process Bypass

.\run_full_verification_inplace.ps1 `
  -FreeCADCmd "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" `
  -GmshExe "C:\path\to\gmsh.exe" `
  -CalculixExe "C:\path\to\ccx.exe"
```

If Gmsh and ccx are already on PATH, their parameters may be omitted. FreeCAD is also auto-discovered from `MECHCAD_FREECADCMD`, PATH, or the default FreeCAD 1.1 path.

The runner defaults to HEAD `4675c6cdaaf63c817719db356b05f30175071081` and fails closed if a different commit is checked out; pass `-ExpectedHead` explicitly when verifying another current HEAD.

For a focused repair loop, pass `-OnlyStages` with exact stage names (for example `-OnlyStages @("11_m1_state_foundation","12_m2_changes")`). Unselected pytest stages are recorded as `NOT_RUN`; focused runs cannot receive full-verification credit.

## Result

Inspect the newest:

`.verification-runs\full-m0-m13-*\SUMMARY.txt`

Full credit requires:

`all_m0_m13_pass=True`
`post_m13_pass=True`
`full_verification_credit_allowed=True`

M11 requires real FreeCAD + Gmsh + CalculiX. Required live milestone stages do not receive PASS credit when pytest skips them.
