# M13-4 Representative Live Full-Stack Capstone

## Final Status

`M13_4_RUNTIME_FULL_SUITE_RECOVERY_READY_FOR_INDEPENDENT_REAUDIT`

`M13_4_ACCEPTANCE_STATUS = PENDING_INDEPENDENT_REAUDIT`

`ROTATOR_V2_MAY_RESUME = NO`

The prior independent rejection remains controlling. The fixture/test-only
remediation below passed the required focused and regression gates and is ready
for independent re-audit. This report does not claim independent acceptance.

## Runtime Recovery Verification

This controlled no-sleep runtime verification addresses only
`M13-4-THIRD-REAUDIT-CRIT-01`. No code, timeout, test, fixture, contract,
acceptance, golden, or hash changes were made.

### Host And FreeCAD Environment

- Executable: `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`
- `Test-Path`: `True`
- FreeCAD: `1.1.3 Revision: 20260725 (Git shallow)`
- Python: `C:\Users\vvooj\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- Workspace: `E:\repo\mechcad-harness`
- Active power scheme: `SCHEME_BALANCED`
- AC standby timeout: `0x00000000` (disabled)
- AC hibernate timeout: `0x00000000` (disabled)
- Battery: none detected; desktop/AC configuration
- Pre-run resources: `1169 MB` available RAM, `28%` CPU, `28.05 GB` free on C:
- Pre-run processes: `freecadcmd.exe = 0`; normal FreeCAD GUI processes = `1`
- Post-run processes: `freecadcmd.exe = 0`; normal FreeCAD GUI processes = `1`

### Historical Sleep Adjudication

The independent third-audit record was created at approximately
`2026-09-09T08:57:55+03:00`. Using its reported failed-suite duration of
`4270.96s` gives an approximate prior interval of `07:46:44` to `08:57:55`.
Windows System logs show a Kernel-Power sleep at `08:29:18` and a
Power-Troubleshooter wake at `08:40:02` inside that inferred interval.

Historical classification: `SLEEP_EVENT_CONFIRMED`.

The timing makes `HOST_SLEEP_OR_SUSPEND_PLAUSIBLE` the likely environmental
explanation for the prior transient timeout, but does not claim deterministic
causation from incomplete original runner timestamps.

### Controlled No-Sleep Run

The baseline capstone selector passed once before the full suite:

- Node: `test_m13_4_representative_canonical_m10_full_stack_capstone`
- Result: `1 passed, 3 deselected`
- Pytest elapsed: `104.08s`
- Wall elapsed: `106.57s`
- FreeCAD timeout: none
- Exit code: `0`

The single controlled full suite ran in the same explicitly configured
PowerShell after sleep was disabled:

- Start: `2026-09-09T09:25:42.4827691+03:00`
- End: `2026-09-09T10:24:15.9267201+03:00`
- Wall elapsed: `3513.44s`
- Pytest elapsed: `3497.88s`
- Result: `2832 passed, 25 skipped`
- Failures: `0`
- Errors: `0`
- Exit code: `0`
- `HOST_SLEEP_DURING_CONTROLLED_RUN = NO`
- M13-4 skips: `0`

The 25 skips were six opt-in OpenCode live validations, five unavailable
materials-extra tests, and fourteen unavailable structural-profile tests.

Runtime classification: `FREECAD_TIMEOUT_TRANSIENT_ENVIRONMENT_VARIANCE`.
The controlled recovery does not indicate defective production timeout
semantics, and `timeout_seconds=120.0` was not changed.

Post-recovery `compileall` and `git diff --check` passed. Durable stdout/stderr
was captured at
`C:\Users\vvooj\AppData\Local\Temp\opencode\m13-4-runtime-controlled-fullsuite.log`.

## Third Remediation Evidence (Historical)

This third remediation addresses the controlling
`M13-4-SECOND-REAUDIT-CRIT-01` finding only. The prior second-re-audit findings
remain closed. This test-only change does not claim independent acceptance,
alter production semantics, or authorize Rotator V2.

### Exact Coverage Invariant

The acceptance test now uses `_assert_exact_pair_coverage()` for both candidate
and fresh canonical M10 results. For each result configuration it derives
unordered concrete identity tuples from the request's own
`exact_pair_scope` and proves:

- every identity is nonempty and has distinct members;
- measured count equals expected scope count;
- measured identities are unique;
- measured identity set equals the complete expected scope set.

The pure negative test
`test_m13_4_exact_pair_coverage_rejects_duplicate_for_omitted_pair` proves that
one duplicate plus one omitted pair cannot pass with the same total count.

### Candidate And Canonical Proof

Candidate execution derives its expected identities from `request.exact_pair_scope`
and proves all eleven concrete pairs occur exactly once in each of four result
configurations. Canonical execution independently derives its expected
identities from `canonical_m10.request.exact_pair_scope` and applies the same
coverage invariant to its four configurations. The candidate and canonical
scope sets are not reused as construction authority for one another.

The repaired `motor-r/shaft-a` pair remains directly asserted in candidate
scope and is asserted exactly once in every candidate result configuration;
the general eleven-pair proof covers all other pairs as well.

### Third Remediation Verification

- Pure coverage negative: `1 passed, 3 deselected`.
- Full M13-4 focused gate: `4 passed` in `204.06s`; zero skips.
- M13-4P: `8 passed` in `13.65s`.
- M13-4E: `116 passed` in `123.67s`.
- M13-3/predecessor: `75 passed` in `33.64s`.
- Required M10/M12/CAD/provenance group: `757 passed` in `349.74s`.
- Fresh full suite: `2832 passed, 25 skipped` in `3537.71s`.
- `python -m compileall -q src tests`: passed.
- `git diff --check`: passed, with only pre-existing CRLF normalization warnings.

The 25 full-suite skips are unrelated optional OpenCode live validations and
unavailable materials/structural-profile extras. No M13-4 test was skipped.

## Second Remediation Evidence (Historical)

This second fixture/test-only remediation addresses the controlling
`M13_4_INDEPENDENT_REAUDIT_REJECTED` findings. It does not claim independent
acceptance, alter production semantics, or authorize Rotator V2.

### M13-4-REAUDIT-CRIT-01: Truthful Pair Policy

`motor-r/shaft-a` is now `CHECK_CLEARANCE` with no exclusion reason. The
support plate occupies `z=0..5 mm`; `shaft-a` begins at `z=15 mm`; the 10 mm
gap has no declared physical-contact authority. Geometry was not changed and no
replacement exclusion was added.

| Member A | Member B | Body relation | Classification | Reason | Authority basis | Configuration scope |
| --- | --- | --- | --- | --- | --- | --- |
| frame-r | motor-r | R/R | SAME_RIGID_GROUP_EXCLUDED | same explicit rigid body | explicit R membership | excluded |
| frame-r | shaft-a | R/A | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| frame-r | hub-a | R/A | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| frame-r | shaft-b | R/B | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| frame-r | hub-b | R/B | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| motor-r | shaft-a | R/A | CHECK_CLEARANCE | none | 10 mm physical separation; no contact authority | all four |
| motor-r | hub-a | R/A | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| motor-r | shaft-b | R/B | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| motor-r | hub-b | R/B | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| shaft-a | hub-a | A/A | SAME_RIGID_GROUP_EXCLUDED | same explicit rigid body | explicit A membership | excluded |
| shaft-a | shaft-b | A/B | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| shaft-a | hub-b | A/B | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| hub-a | shaft-b | A/B | INTENDED_CONTACT_EXCLUDED | explicit J2 connection | declared J2 interface/connection | excluded |
| hub-a | hub-b | A/B | CHECK_CLEARANCE | none | cross-body non-contact | all four |
| shaft-b | hub-b | B/B | SAME_RIGID_GROUP_EXCLUDED | same explicit rigid body | explicit B membership | excluded |

The derived exact M10 scope now contains eleven physical pairs per
configuration: every table row classified `CHECK_CLEARANCE`. The capstone
asserts that `motor-r/shaft-a` is in the exact M10 scope and has one real exact
measurement result in each of the four configuration results.

### M13-4-REAUDIT-CRIT-02: Complete Diagnostic Restart Snapshot

The scalar locator remains the only Phase-A to Phase-B construction input.
Phase B composes its fresh root from `locator["project_id"]` and treats the
fixture project constant only as a diagnostic equality check. It loads the
exact promoted revision/state hash, reconstructs canonical authority, realizes
canonical CAD, compiles the bridge, constructs and executes canonical M10, and
only then reads the diagnostic JSON.

The primitive JSON snapshot is round-tripped through `json.dumps`/`json.loads`
and directly checked for: physical bodies and root, member ownership/reference
members, joints and home semantics, member placements, member/body offsets,
complete generated-placement derivations, all fifteen policy rows, exact checked
scope, ordered configurations/commands, volume and distance tolerances,
inventory meaning, and representation fidelity. Derivation records preserve
rule/derivation IDs, normalized source/target members, interface/frame IDs and
hashes, placement-reference kind, authoritative inputs, and rotation/clocking
semantics. The canonical diagnostic representation is independently rebuilt
after canonical execution and compared without being used for construction.

### M13-4-REAUDIT-IMP-01: Compilation And Evidence

The capstone observes exactly one production `compile_multi_joint()` call and
asserts full typed equality between that observed compilation and
`receipt.compilation`, including full projection, projection hash, and mapping
equality. It does not run a second compiler call to manufacture expected data.

Canonical M10 Evidence is durably reloaded through `EvidenceStore` and checked
against the fresh canonical execution: project/store binding, promoted revision
and state hash, canonical assembly and KinematicModelV2 identities,
configuration set, inventory identity, exact checked scope, both tolerances,
request/result hashes, provider, backend adapter, FreeCAD `1.1.3`, execution
mode, and `CURRENT` freshness before the deliberate revision-3 stale mutation.

### Current Verification Evidence

- FreeCAD executable verified at `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`; version `1.1.3`.
- Focused M13-4: `3 passed` in `206.79s`; zero skips.
- Serialized restart/snapshot selector: `test_m13_4_serialized_restart_canonical_restart_and_durable_reload`, `1 passed, 2 deselected` in `90.53s`; it proves both the scalar restart boundary and complete persisted diagnostic snapshot in one test, not two independent tests.
- M13-4P: `8 passed` in `13.88s`.
- M13-4E: `116 passed` in `126.36s`.
- M13-3/predecessor: `75 passed` in `35.00s`.
- Required M10/M12/CAD/provenance group: `757 passed` in `372.45s`.
- Full suite: `2831 passed, 25 skipped` in `4020.46s`; M13-4 skips: `0`.

The 25 full-suite skips are six opt-in OpenCode live validations, five
unavailable materials-extra tests, and fourteen unavailable structural-profile
tests. They are unrelated to M13-4.

## First Remediation Evidence

### Truthful Authority

The repaired fixture persists non-empty source authority in `DesignState`:

- Requirement: `REQ-M13-4-GENERATED-GEOMETRY`
- Constraints: `CON-TRANSMISSION-OUTPUT-INTERFACE` and `CON-TRANSMISSION-PACKAGING-ENVELOPE`
- Authoritative parameters: `transmission.output_interface` and `transmission.packaging_envelope`
- Candidate source binding: `/id`, `/requirements`, `/constraints`, `/authoritative_parameters`, and `/physical_mechanisms`

The trusted STEP artifact is used as a support plate only. Its accepted supplied
authority is a geometry-backed, human-confirmed mounting face with a reference
frame. It is not labeled as a motor and supplies no rotational shaft authority.

Generated dimensions are derived from persisted source parameters:

- Shaft: `10.0 mm` diameter, `50.0 mm` length
- Hub: `30.0 mm` outer diameter, `50.0 mm` length
- Hub bores: `10.0 mm` diameter, `0.0/25.0 mm` input start/depth, `25.0/25.0 mm` output start/depth
- Frame: `60.0 x 30.0 x 10.0 mm`
- Placement: accepted support-frame pose, generated frame relation, and source-bound axial offset
- `J1`: generated shaft interface, child-owned axis
- `J2`: generated hub output interface, parent-owned axis

The fifteen physical pair rows are declared exactly once and the live M10 scope
contains ten checked pairs per configuration.

### Restart Boundary

`test_m13_4_serialized_restart_canonical_restart_and_durable_reload` executes
Phase A and Phase B across a scalar JSON locator boundary. Phase B constructs a
fresh production root, reloads persisted state/artifacts, verifies the persisted
typed promotion receipt, and uses an adapter that fails if invoked. No candidate,
CAD realization, bridge, M10 request/result, evaluation, selection, or Evidence
object crosses the boundary.

The persisted primitive semantic snapshot includes body/member/reference facts,
joint endpoints, axis owner/sign, limits, zero semantics, all pair policy rows
and reasons, ordered configurations, placement transforms, CAD inventory, and
representation fidelity. The original observed `compile_multi_joint()` result
is compared with the post-promotion reconstructed canonical mechanism by typed
object and mechanism/projection identity.

### Durable Lifecycle

The remediation asserts persisted `RUN_CREATED` and `REVISION_ADVANCED` events,
run source/active bindings, decision/result artifact hashes, ChangeSet identity,
changed paths, invalidation identity, fresh-root receipt verification, canonical
CAD/M10 Evidence provenance, and source revision byte immutability.

### Verification Gates

- M13-4 acceptance file: `3 passed` in `194.83s`
- M13-4P gate: `8 passed` in `12.75s`
- Exact M13-4E gate: `116 passed` in `125.24s`
- Exact M13-3/predecessor gate: `75 passed` in `32.46s`
- Full suite: `2831 passed, 25 skipped` in `3701.76s`
- Both permitted acceptance files compile successfully

The twenty-five skips are unrelated opt-in OpenCode live checks and unavailable
optional structural/material extras. No M13-4 test was skipped.

## Historical Pre-Remediation Record

The remaining sections preserve the original non-accepted capstone record for
traceability. Their fixture values and final status describe the rejected
pre-remediation run and are not current acceptance claims.

## Runtime

- FreeCAD executable: `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`
- FreeCAD version: `1.1.3`
- FreeCAD backend adapter: `mechcad-freecad@2.1`
- FreeCAD library source: `bundled`
- FreeCAD library revision: `freecad-1.1.3-bundled`
- Runtime discovery: available
- Exact provider: `freecad-transient-exact`
- Exact execution mode: `freecadcmd-subprocess`

## Generic Fixture

The fixture is `PRJ-M13-4-T16`, source revision `1`, with source state hash
`sha256:9bdbf981034773c42ab5b97ccd53d9ec6344d59858cf684c0ae51b0c2bc6c963`.

The supplied trusted STEP artifact is:

- Artifact ID: `FC-m13-2-supplied-motor-e83a0a00f3ff61ac`
- Artifact hash: `sha256:bbfb0642ec58be92272af67d13eb94450586ff2f80aaf513cd5e1af56d88aae2`

The fixture contains six constituents, three explicit rigid bodies, two
dependent revolute joints, and all fifteen unordered physical pairs exactly
once:

- Body `R`: `motor-r`, `frame-r`
- Body `A`: `shaft-a`, `hub-a`
- Body `B`: `shaft-b`, `hub-b`
- `J1`: `R -> A`, supplied rotational interface axis
- `J2`: `A -> B`, generated rotational interface axis

Generated dimensions and authority are source-bound:

- Shaft: diameter `12.5 mm`, length `40.0 mm`
- Hub: outer diameter `30.0 mm`, length `50.0 mm`
- Hub input bore: diameter `10.5 mm`, start `0.0 mm`, depth `20.0 mm`
- Hub output bore: diameter `12.5 mm`, start `20.0 mm`, depth `30.0 mm`
- Frame: length `60.0 mm`, width `20.0 mm`, height `10.0 mm`
- Placement derivations include frame axial offset `5.0 mm`, hub offsets
  `2.0 mm` each, and frame clocking `15.0 deg`

The explicit ordered configurations are:

- `cfg0`: `J1=0.0`, `J2=0.0`
- `cfg1`: `J1=15.0`, `J2=0.0`
- `cfg2`: `J1=0.0`, `J2=15.0`
- `cfg3`: `J1=15.0`, `J2=45.0`

The live result confirmed that the root remains fixed, `A` moves with `J1`,
`B` moves with `J2`, and `cfg3` has a distinct descendant pose.

## Candidate Stage

- Candidate hash: `sha256:711b33cbc5b3a9c3e0b09b29ec3eabad6c8fd0d1207f90390d0ddfbdd34f5dd7`
- Candidate CAD request: `sha256:c2c9fde2f61b4f6251880eb7616ab77f21c29de953a58b82482714044ec584eb`
- Candidate CAD realization: `sha256:10bb46f33e9d6ddcc8a3b00f6da1669f073559c2efeb7a57bf913a3c913e2b82`
- Candidate assembly: `sha256:e673810b6ae6a2af95142c4fa4df830b1862854495b941867ed7d9a60055cd3a`
- Candidate bridge: `sha256:84383c3f588dad0ec452641be5472a92d8969f345953095b92fab4a5672c6f2e`
- Candidate M10 model: `sha256:62dba7977c057f05fb14b079affc48cd0fbf2e03274e30de1a4f08a1de0c8037`
- Candidate inventory: `sha256:c9c294ab9508277d61d2456bf1d999e0a8c5729126ae7f78793420a650febf24`
- Candidate checked pair scope: `sha256:8cab76a783c5199e6d33573699651774870010b6fc7b80ec8884cbba533152c9`

Candidate CAD used one trusted imported representation and five exact generated
representations. The realization and supplied artifact were independently
reloaded from JSON/scalar data and remained hash-consistent.

## Candidate M10-3

Candidate evaluation and selection were routed through:

- `ProductionApplication.evaluate_candidate_multi_joint_m10()`
- `ProductionApplication.select_candidate_multi_joint()`

The candidate M10-3 result was discrete-only:

- Evaluation hash: `sha256:20facd3a29a39308b354ba55923308b34c9ff9966e03b8364b7ee33cdd405354`
- Selection hash: `sha256:eaf32892610cc2036c052d94a1522ec46624e920f08113ec44bfafe6ed3d77ea`
- Request hash: `sha256:16acf0dc7026cfa9b69c6e70f243d37e1daf6e91c8451e5c4f341b5e016c07f9`
- Result hash: `sha256:0fc7b2ca458e33c92a54146af5e9410288ebb229a7ac9431317c455f4a403915`
- Evidence ID: `EVD-MJCS-037ddc0508c218ada2c653c7`
- Configurations: `4`
- Checked pairs per configuration: `10`
- Minimum exact distance: `0.0 mm`
- `continuous_path_verified`: `False`

All measured interference volumes and exact distances were finite. Candidate
Evidence was reloaded and verified against request, result, source assembly,
M10 model, provider, FreeCAD backend, and runtime version.

## Promotion And N+1

Promotion was routed through
`ProductionApplication.promote_selected_multi_joint_candidate()`. The
production compiler was observed exactly once through that route; no
independent test-side compilation was used.

- Decision artifact: `MULTI-JOINT-PROMOTION-DECISION-5e6504bf21e37814c5b11914`
- Result artifact: `MULTI-JOINT-PROMOTION-RESULT-15e7b3620ba9d69d3f2ca508`
- Applied revision: `2`
- Applied state hash: `sha256:55d6b1fa61b6f742b8d985ca188e2c1c282588d979dcf65ca80c17482bb3235a`
- ChangeSet ID: `CS-3bdbcd15-d14b-4215-a14a-50c029df4298`

The receipt was serialized to JSON scalars, rehydrated with its typed nested
records, and verified using the durable artifact locators. The promotion run
and `RUN_CREATED` event were independently reloaded from the persisted run
directory.

The N+1 change was applied through `RunController.apply_approved_proposal()`:

- N+1 revision: `3`
- N+1 state hash: `sha256:2a6def6a6bd4a50578b62a2aa9b9b58226bd85ecb033ff608b097c95a56c4d7f`
- Invalidation changed path: `/physical_mechanisms/PM-M13-4-T16`
- Candidate CAD and candidate selection were rejected as stale afterward
- Candidate M10 Evidence freshness after N+1: `stale`

## Fresh Canonical Reload

A fresh `ProductionApplication` root was created over the persisted workspace.
Canonical reconstruction, CAD realization, bridge compilation, M10-3
execution, and Evidence lookup used only persisted canonical state/artifacts.

- Canonical mechanism: `PM-M13-4-T16`
- Canonical projection: `sha256:1b873edbfc701e5994c8d08e7ad6e8db335adb41c83c4984d28e9864d402e84d`
- Canonical CAD request: `sha256:73ba47d2c59ae746e718eb63ba39a0977898f5d34cc6935bbdd5a93f5be70f51`
- Canonical CAD realization: `sha256:be2863d6a3246f4b6e4c1ccebb204e518330b2aa77d589c64f4033f533050d69`
- Canonical assembly: `sha256:3958f05bae4099b6fb498f3c31a003c95f92c2947476267e0bc80bb4461539c8`
- Canonical bridge: `sha256:b9ee60a3271c85af2324f0b98da1f85d660f93b3b7260466d62c933181960837`
- Canonical M10 request: `sha256:a56a666cab65270a6da669886355441c18cc179b3f2a2708464ece34a7c841e4`
- Canonical M10 result: `sha256:7e2a6121bdec23593eee70b23f6e0d903969d1bc1bb708407680003ffc968d21`
- Canonical M10 Evidence: `EVD-MJCS-fcc3535734f8820204be6d56`

The canonical request/result bound to the fresh canonical assembly, model,
configuration set, exact pair scope, tolerances, and discrete-only evaluator.
Candidate hash and candidate result hash were absent from the canonical
reconstruction serialization.

Typed semantic comparison confirmed equivalent bodies, joints, pair policy,
configuration order, placements, inventory, tolerances, and placement
derivations without requiring raw candidate/canonical hash equality.

## Focused M10-4

The proof used exactly two truthful checked pairs: one root/articulated pair
and one articulated/articulated pair. The path was explicitly constructed from
the selected cfg0 to the endpoint `J1=1.0`, `J2=1.0`; no trajectory or region
was generated.

- Candidate status: `COLLISION_WITNESS`
- Candidate result: `sha256:82275ffe25acbf664ee2258e1b8740491a455e295c5bb0aac648b82a7a8e2dce`
- Candidate Evidence: `EVD-MJCP-974dce523008df548000c52d`
- Canonical status: `COLLISION_WITNESS`
- Canonical result: `sha256:9acc71fe5781272ff50890596681b7151bc750a527ddb1270b0a4ca4b0520216`
- Canonical Evidence: `EVD-MJCP-9fdb79c21d15eec787d662bb`
- Candidate and canonical statuses matched
- The result remained explicitly path-scoped; no global clearance claim was made

## M11 Decision

- `M11_STATUS = UNRESOLVED`
- `M11_ELIGIBLE = False`
- No structural analysis definition was created
- No material, semantic region, load, support, mesh, solver request, or FEA
  result was created
- The source fixture contained no structural definitions, materials, or load cases

## Negative And Scope Checks

- Foreign-project candidate selection was rejected by the project binding gate.
- Legacy single-joint promotion entry rejected the multi-joint request schema.
- Stale candidate CAD and selection were rejected after N+1.
- Actual trusted source STEP bytes were tampered in a copied workspace and
  canonical CAD failed closed before canonical M10/Evidence publication.
- In-memory stale trusted-source hash substitution also failed closed.
- Candidate runtime records did not cross the canonical reconstruction boundary.
- Scoped forbidden-term audit over the two new acceptance files returned no matches.
- Native `rg` was not available on PATH in this shell; the equivalent repository
  Grep audit returned no matches.
- This task made no edits below `src/mechcad_harness/`. Pre-existing dirty
  source files remained untouched.
- No commits, tags, pushes, or predecessor golden/hash updates were made.

## Verification Commands

- Focused acceptance: `2 passed` in `110.19s`, `0 skipped`
- Canonical-focused acceptance: `1 passed, 1 deselected` in `109.62s`
- M13-4P gate: `8 passed` in `13.90s`
- M13-4E gate: `116 passed` in `123.53s`
- M13-3/predecessor gate: `75 passed` in `35.08s`
- Required M10/M12/CAD/provenance regression group: `757 passed` in `362.92s`
- `py -3 -m compileall -q src tests`: passed
- `git diff --check`: passed; Git emitted existing line-ending normalization warnings
- Full suite: `2830 passed, 25 skipped` in `3798.58s`

The full-suite skips were unrelated opt-in OpenCode live checks and unavailable
optional materials/structural profile extras. No M13-4 acceptance test skipped.

## Remaining Boundary

Rotator V2, antenna/Yagi/pan-tilt semantics, automatic synthesis/selection,
whole configuration-space certification, trajectories, structural FEA for this
generic mechanism, tolerances, optimization, manufacturing approval, and
global safety claims remain outside this capstone.
