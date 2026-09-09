# M13-4 Independent Acceptance Audit

## Verdict

```text
M13_4_INDEPENDENT_REJECTED
M13_4_ACCEPTANCE_STATUS = REJECTED
ROTATOR_V2_MAY_RESUME = NO
```

The received focused live gates and all requested regression gates pass, but two
CRITICAL acceptance failures remain: the fixture invents and misrepresents both
the supplied interface semantics and generated geometry authority, and the
canonical phase is not separated from candidate runtime by the required
durable-scalar restart boundary.

## Audit Independence

This audit did not implement M13-4, edit production code, edit tests, remediate
findings, commit, tag, push, or start Rotator V2. The only intentional repository
write is this report. The completion report was treated as a claim and was not
accepted as evidence.

## Input Authority

Read and applied:

- `docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md`
- `docs/superpowers/specs/2026-09-06-m13-4-representative-live-full-stack-capstone.md`
- `docs/superpowers/plans/2026-09-07-m13-4-representative-live-full-stack-capstone-execution.md`
- `docs/audit/MECHCAD_M13_4P_INDEPENDENT_ACCEPTANCE.md`
- `docs/audit/MECHCAD_M13_4E_R12_INDEPENDENT_REAUDIT.md`
- The M13-1/M13-2 fixture-consumption tests, M13-4P production composition,
  canonical CAD, ArtifactStore, EvidenceStore, StateManager, ChangeEngine, and
  M10 v2 routes used by the fixture.

Upstream authority remains `M13_4E_INDEPENDENT_R12_ACCEPTED` and
`M13_4P_INDEPENDENT_ACCEPTED`; it authorizes this audit, not Rotator V2.

## Repository / Worktree State

Before this report was created, `git status --short`, `git diff --stat`,
`git diff`, and `git diff --check` were run. `git diff --check` exited zero;
only existing CRLF normalization warnings were emitted.

Received change classification:

- Accepted pre-existing M13-4E/M13-4P production: `src/mechcad_harness/application.py`, `src/mechcad_harness/candidates/__init__.py`, `promotion.py`, `promotion_artifacts.py`, and `promotion_models.py`.
- M13-4 acceptance support/test: `tests/integration/m13_4_acceptance_fixtures.py` and `tests/integration/test_m13_4_full_stack_acceptance.py`.
- M13-4 report/documentation: the completion report, plan, specification addendum, and this audit report.
- Unrelated pre-existing noise: `.coverage`, `.superpowers/sdd/*`, `err.txt`, `projects/`, and `src/mechcad-harness/`.

No M13-4-specific production semantic change was found under
`src/mechcad_harness/`. The accepted pre-existing M13-4E/M13-4P dirty production
surface is not attributed to M13-4 execution.

## FreeCAD Runtime

The inherited shell had no `MECHCAD_FREECADCMD`; the required path was explicitly
set for every live gate:

```text
C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe
Test-Path: True
freecadcmd --version: FreeCAD 1.1.3 Revision: 20260725 (Git shallow)
```

Repository discovery returned `available=True`, that executable,
`importable=False`, and execution boundary `bundled FreeCAD command line`.
`FreeCADBackend.provenance()` returned `mechcad-freecad@2.1`, library `FreeCAD`
version `1.1.3`, source `bundled`, revision `freecad-1.1.3-bundled`. System Python
not importing FreeCAD is not a failure because the accepted subprocess boundary
executed live.

## Representative Fixture

The fixture is generic in naming and does not consume Rotator V2, antenna/Yagi,
or AZ/EL project authority. It declares exactly six members and three bodies:

```text
R = motor-r, frame-r
A = shaft-a, hub-a
B = shaft-b, hub-b
J1: R -> A
J2: A -> B
```

The topology and explicit configuration records are structurally valid. This
does not cure the authority failures below.

## Supplied M13-1 Authority

The supplied artifact is generated live and byte-verified as
`FC-m13-2-supplied-motor-e83a0a00f3ff61ac` with the reported SHA-256. The actual
shape is a `30 x 30 x 5 mm` base plate.

J1 gets its axis from `SuppliedRotationalInterfaceAxisSource` at
`m13_4_acceptance_fixtures.py:391-404`, which binds to the interface hash and
geometry reference hash. However, that interface originates in
`test_m13_2_acceptance_live.py:151-202`: test literals labelled `vendor:motor`
and `MANUFACTURER_DATASHEET` provide a shaft axis, diameter, and frame that the
base-plate STEP does not contain. This is fabricated test authority represented
as supplier/manufacturer authority, contrary to the M13-4 fixture-authority
constraint. STEP geometry itself is not used to infer the axis, but the supposed
semantic source is not acceptable M13-1 authority.

## Generated M13-2 Authority

The fixture deterministically regenerates a shaft (`12.5 x 40 mm`), hub (`30 mm`
OD, `50 mm` length; 10.5/12.5 mm bores and 20/30 mm depths), and frame
(`60 x 20 x 10 mm`). It also replays non-identity placement derivations: 5 mm
frame offset, 15 degree clocking, and two 2 mm hub offsets.

These values are fixture literals in
`m13_4_acceptance_fixtures.py:231-298`, `539-559`, and `591-618`. The source
`DesignState` at lines 109-117 has no requirements, constraints, interfaces, or
authoritative parameters. Replaying literals from candidate design variables is
deterministic, but is not source-bound accepted authority and does not cure the
prohibited fixture-local magic dimensions.

## Physical Body / Joint Semantics

The typed records specify explicit body membership, reference members, root `R`,
bounded `[-90, 90]` degree J1/J2 limits, parent-owned positive axes, and
`accepted-semantic-home@1` zero semantics. No implicit body or DOF inference was
found. J1 authority is nevertheless invalid for the reason above.

## Configuration Set

The persisted candidate configuration set is explicit and within limits:

```text
cfg0 J1=0, J2=0
cfg1 J1=15, J2=0
cfg2 J1=0, J2=15
cfg3 J1=15, J2=45
```

The live result checks that J1 moves A/B, J2 changes B, and cfg3 is distinct.
They are explicit obligations, not limit sampling.

## Complete Pair Universe

The fixture constructs 15 unordered pairs exactly once. Its asserted policy is:

| Pair | Body relation | Classification | Reason | Scope |
| --- | --- | --- | --- | --- |
| frame-r/motor-r | R/R | SAME_RIGID_GROUP_EXCLUDED | same explicit rigid body | excluded |
| frame-r/shaft-a | R/A | CHECK_CLEARANCE | none | all 4 configs |
| frame-r/hub-a | R/A | CHECK_CLEARANCE | none | all 4 configs |
| frame-r/shaft-b | R/B | CHECK_CLEARANCE | none | all 4 configs |
| frame-r/hub-b | R/B | CHECK_CLEARANCE | none | all 4 configs |
| motor-r/shaft-a | R/A | INTENDED_CONTACT_EXCLUDED | explicit J1 connection | excluded |
| motor-r/hub-a | R/A | CHECK_CLEARANCE | none | all 4 configs |
| motor-r/shaft-b | R/B | CHECK_CLEARANCE | none | all 4 configs |
| motor-r/hub-b | R/B | CHECK_CLEARANCE | none | all 4 configs |
| shaft-a/hub-a | A/A | SAME_RIGID_GROUP_EXCLUDED | same explicit rigid body | excluded |
| shaft-a/shaft-b | A/B | CHECK_CLEARANCE | none | all 4 configs |
| shaft-a/hub-b | A/B | CHECK_CLEARANCE | none | all 4 configs |
| hub-a/shaft-b | A/B | INTENDED_CONTACT_EXCLUDED | explicit J2 connection | excluded |
| hub-a/hub-b | A/B | CHECK_CLEARANCE | none | all 4 configs |
| shaft-b/hub-b | B/B | SAME_RIGID_GROUP_EXCLUDED | same explicit rigid body | excluded |

This is structurally complete, has ten checked pairs, and includes root/articulated
and articulated/articulated checks. Its physical truthfulness is not established:
`frame-r` is placed from a fabricated frame around `(100,100,3)` while `motor-r`
is at origin, despite their claimed rigid grouping; the base plate has no actual
J1 shaft contact. Therefore the complete pair policy cannot be accepted as a
truthful physical policy.

## Candidate CAD

The passing live route enters `ProductionApplication.create()` and
`realize_candidate_cad()`. It creates one trusted imported mapping and five exact

## Candidate M10-3

The live candidate evaluation uses
`ProductionApplication.evaluate_candidate_multi_joint_m10()`. The focused gate

The reported 0.0 mm minimum exact distance is a touching result, not automatically

## Selection

Selection calls `ProductionApplication.select_candidate_multi_joint()`, whose

## Promotion / Original Compilation

Promotion calls `ProductionApplication.promote_selected_multi_joint_candidate()`.

The M13-4 test does not itself assert full equality

## Revision Timeline

| Revision | State and transition | Audit adjudication |
| --- | --- | --- |
| 1 | Empty fixture `DesignState` source, hash `sha256:9bdb...c963` | Candidate source; contains no generated geometry authority. |
| 2 | Promotion via the production root. Decision/result artifact route produces ChangeSet `CS-3bdbcd15-d14b-4215-a14a-50c029df4298`, physical mechanism `PM-M13-4-T16`, and reported hash `sha256:55d6...3235a`. | This is the actual M13-4 promoted N+1 state. |
| 3 | `_apply_n_plus_one_name_change()` creates a new run and replaces only `/physical_mechanisms/PM-M13-4-T16` with a renamed copy, producing reported hash `sha256:2a6d...d7f`. | Deliberate later stale/currentness mutation, not promotion. It occurs after canonical execution. |

Answers to the critical revision questions:

- A. Revision 2 is the promoted M13-4 N+1 DesignState.
- B. The fresh canonical reconstruction is explicitly loaded from revision 2.
- C. Revision 3 preserves the physical mechanism except its name, but is not used
  as canonical reconstruction authority.
- D. The plan requires a stale negative but does not authorize treating revision 3
  as the promoted canonical source. The actual ordering preserves the revision-2
  promotion-to-reconstruction chain.
- E. The extra transition does not itself break the promotion chain because it is
  performed only after fresh revision-2 canonical CAD/M10. It does not repair the
  independent restart-boundary failure.

## ChangeEngine / Durable State

For revision 2, the accepted route is request -> readiness -> original

Revision 3 is a separate ChangeProposal `CP-M13-4-T16-NPLUS1`, created directly

## Receipt Verification

The root verifier is invoked with a serialized/rehydrated receipt and resolves

## Hard Restart Audit

The test does construct a fresh `ProductionApplication`, StateManager,

## Canonical Source Revision

Canonical reconstruction loads revision 2 with the promoted revision-2 state

## Fresh Canonical Reconstruction

The fresh root reconstructs persisted revision 2, reloads trusted source bytes,

## Candidate / Canonical Semantic Equivalence

The fixture invokes the accepted

## Canonical M10-3

The canonical M10-3 route runs live with fresh CAD/bridge and creates canonical

## Focused M10-4

The fixture selects exactly two truthful `CHECK_CLEARANCE` scope pairs, one

## M11 Decision

`M11_STATUS=UNRESOLVED` and `M11_ELIGIBLE=False` are explicitly asserted. The

## Candidate Stale Rejection

Candidate CAD and selection are valid before revision 3. The real later

## Canonical Stale / Substitution Rejection

The test copies the persisted workspace, appends bytes to the actual trusted

## Provenance / Evidence

Live candidate CAD, candidate M10-3, promotion decision/result artifacts,

## Test Quality

M13-4 uses narrow observation wrappers for candidate M10 and original compilation

## Focused Gate

```text
MECHCAD_FREECADCMD=C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -rs
2 passed in 152.20s
exit status: 0
M13_4_REQUIRED_SKIPS = 0
```

## Canonical-Focused Gate

```text
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k canonical_m10
1 passed, 1 deselected in 151.77s
exit status: 0
```

## M13-4P Regression

```text
py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -q
8 passed in 18.10s
exit status: 0
```

## M13-4E Regression

```text
116 passed in 145.04s
exit status: 0
```

## M13-3 Regression

```text
75 passed in 45.09s
exit status: 0
```

## Required M10/M12/CAD Regression

The exact regression group in the M13-4 execution plan was run with FreeCAD

```text
757 passed in 379.27s
exit status: 0
```

## Full Suite

```text
MECHCAD_FREECADCMD=C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe
py -3 -m pytest -q -rs
2830 passed, 25 skipped in 3645.73s (1:00:45)
exit status: 0
```

## Skip Audit

All 25 full-suite skips are optional environment/opt-in categories:

- 6 OpenCode live-validation opt-ins.
- 5 unavailable materials extra.
- 14 unavailable structural profile tests.

No M13-4 acceptance test skipped. `M13_4_REQUIRED_SKIPS = 0`.

## Static / Protected Surface

```text
py -3 -m compileall -q src tests: exit status 0
```

The M13-4 fixture/test contain no Rotator, antenna, Yagi, azimuth, elevation,

## Findings

### CRITICAL

- **M13-4-CRIT-01: supplied and generated authority is fabricated rather than source-bound.**
  - Requirement: M13-4 must consume accepted M13-1 semantic authority without representing fixture facts as supplier facts, and every geometry-driving value must have declared accepted authority rather than fixture-local magic dimensions.
  - Evidence: `m13_4_acceptance_fixtures.py:977-1017` creates a 30 x 30 x 5 base plate; `test_m13_2_acceptance_live.py:151-202` supplies unrelated `vendor:motor` / `MANUFACTURER_DATASHEET` shaft axis/frame facts; J1 consumes those facts at fixture lines 391-404. The source state is empty at lines 109-117 while generated dimensions/offsets/clocking are literals at lines 231-298, 539-559, and 591-618.
  - Affected files/symbols: `_state`, `_generated_specifications`, `_candidate`, `_placement_derivations`, `_physical_realization`, `_supplied_motor_spec`.
  - Acceptance impact: the authoritative source chain asserted by the capstone does not exist. Live FreeCAD only proves the fabricated fixture geometry executes.
  - Minimal remediation boundary: acceptance fixture/support and its source-authority construction only. Use truthfully labelled accepted fixture authority tied to the artifact, or an actual accepted M13-1 artifact/interface; bind all generated values to real declared source/candidate authority without modifying production contracts.

- **M13-4-CRIT-02: no hard scalar-only restart boundary and incomplete semantic equivalence evidence.**
  - Requirement: candidate/runtime objects must be disposed before canonical construction; only serialized durable scalar locators and a persisted primitive semantic diagnostic snapshot may cross; equivalence must cover the stated full semantic set.
  - Evidence: `test_m13_4_full_stack_acceptance.py:475-556` creates `fresh_application` while retaining and using receipt, candidate CAD realization, bridge, request, evaluation, and in-memory candidate snapshot. No locator JSON exists. `_semantic_snapshot` at lines 92-171 omits required limits, zero semantics, reasons, tolerances, exact scope, offsets, and derivation semantics.
  - Affected files/symbols: `_semantic_snapshot`, `test_m13_4_representative_canonical_m10_full_stack_capstone`.
  - Acceptance impact: the test cannot prove that canonical authority is reconstructed after the mandated candidate-runtime disposal boundary.
  - Minimal remediation boundary: M13-4 acceptance test/support only. Persist/reload scalar locators and a primitive semantic snapshot, shadow all candidate runtime references before fresh root construction, and compare the complete permitted semantic fields only as diagnostics.

### IMPORTANT

- **M13-4-IMP-01: capstone-specific promotion and canonical-Evidence checks are incomplete.**
  - Requirement: prove receipt equals the original full compilation, durable ChangeSet/run/invalidation lifecycle, repeatable receipt verification, and full canonical Evidence binding.
  - Evidence: test lines 416-474 observe one compile but never assert full `receipt.compilation == compilation`, projection/mapping equality, `REVISION_ADVANCED`, or full invalidation linkage; verifier runs once. Lines 500-510 only assert canonical Evidence/provider presence and execution mode.
  - Acceptance impact: these omissions prevent the test from independently proving several required M13-4 facts, although accepted M13-4E/M13-4P predecessor tests cover the generic contract.
  - Minimal remediation boundary: M13-4 acceptance test only; add independent assertions/reloads without changing production.

### MINOR

None.

### NOTES

- The revision-3 stale mutation occurs after fresh canonical revision-2 execution. It does not replace or corrupt the actual promoted revision-2 chain.
- Passing tests are evidence of executable behavior, not evidence that fabricated authority is permissible.

## Acceptance Decision

The historical M13-4P composition blocker remains resolved and FreeCAD live

```text
M13_4_INDEPENDENT_REJECTED
M13_4_ACCEPTANCE_STATUS = REJECTED
```

## Downstream Authorization

```text
ROTATOR_V2_MAY_RESUME = NO
```
