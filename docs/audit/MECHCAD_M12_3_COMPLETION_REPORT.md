# M12-3 Bounded Revolute-Drive Realization And Engineering Sizing Completion Report

## Final Disposition

`M12_3_BOUNDED_PHYSICAL_REVOLUTE_DRIVE_REALIZATION_SIZING_VERIFIED`

The cumulative final review found no Important/Critical issues. The bounded
claim remains: deterministic construction and evaluation of supplied-component
direct-drive and external-spur realizations for one scoped revolute joint. This
is not a claim of general mechanism synthesis, CAD, M10/M11 execution,
manufacturing approval, gear strength/life, bearing life, fatigue, thermal duty,
or complete-machine safety.

## Required Verification

All commands below were run fresh in the current worktree with `py -3`.

### Focused Predecessor Regressions

Command:

```text
py -3 -m pytest tests/unit/test_m12_candidate_foundation.py tests/unit/test_tools.py tests/unit/test_state_foundation.py -q
```

Result: `36 passed in 2.48s`; exit code `0`; no skips, failures, or errors.

### Production / Provider Regression

Command:

```text
py -3 -m pytest tests/unit/test_production_application.py tests/unit/test_tools.py tests/unit/test_gear_backend.py tests/unit/test_gear_cad.py -q
```

Result: `66 passed in 33.63s`; exit code `0`; no skips, failures, or errors.
Existing optional Gearworks guards did not skip a test in this invocation.

### Final-Fix M12-2 / Production / BuiltinTools Regression

The later final-fix wave ran this separate, overlapping regression command:

```text
py -3 -m pytest tests/unit/test_m12_candidate_foundation.py tests/unit/test_production_application.py tests/unit/test_tools.py -q
```

Result: `61 passed in 6.47s`; exit code `0`; no skips, failures, or errors.

### Full Suite

Command:

```text
py -3 -m pytest tests/
```

The command was allowed a 3600-second timeout and completed normally.

Result:

- Collected: `1584`
- Passed: `1550`
- Skipped: `34`
- Failed: `0`
- Errors: `0`
- Elapsed: `1394.30s` (`0:23:14`)
- Exit code: `0`

The full suite includes the M12-3 production integration tests and all existing
M10/M11 regression coverage. Accepted skips were not converted into pass claims.

### Compile

Command:

```text
py -3 -m compileall -q src/mechcad_harness tests
```

Result: exit code `0`, no output.

### Diff Check

Command:

```text
git diff --check
```

Result: no M12-3 whitespace error. Git emitted existing working-copy line-ending
normalization notices (`LF will be replaced by CRLF`) for already-dirty tracked
files. It also reported `new blank line at EOF` only for the unrelated
`.superpowers/sdd/task-1-brief.md`, `task-2-brief.md`, and `task-3-brief.md`.
The M12-3 files are untracked in this worktree, so ordinary `git diff --check`
does not inspect them; a direct scan of the complete untracked M12-3 set
(report/spec/plan, candidate/revolute-drive/engineering sources, and related
unit/integration tests) found no trailing-whitespace or blank-line-at-EOF
findings.

## Focused M12-3 Verification

Command:

```text
py -3 -m pytest tests/unit/test_spur_engineering.py tests/unit/test_m12_revolute_drive_models.py tests/unit/test_m12_motor_admissibility.py tests/unit/test_m12_spur_drive_sizing.py tests/unit/test_m12_shaft_sizing.py tests/unit/test_m12_revolute_drive_service.py tests/unit/test_m12_revolute_drive_provenance.py tests/integration/test_m12_revolute_drive_production.py -q
```

Result after final review fixes and added regressions: `158 passed in 4.55s`;
exit code `0`.

The added red-to-green regressions cover consumed bindings for incomplete and
invalid declared properties, unsupported declared profile shift, one-joint
construction scope, explicit axis/frame references, nonnegative speed
magnitudes, exact canonical scalar-record matching, composite-source rejection,
and exact candidate design-variable policy admission.

## Engineering Self-Review

The following checks were performed against all M12-3 source, test, approved
specification, plan, completion report, and relevant M12-2 candidate files.

### Findings Fixed

1. Direct and spur speed checks previously omitted an available speed-bound
   property binding when the other bound was missing. Both checks now retain
   every declared binding used by the unresolved check.
2. Spur torque transfer previously omitted continuous or peak motor bindings
   when a declared value was nonpositive and produced a violation. Those
   bindings are now retained.
3. Shaft stress sizing previously omitted the declared shaft-diameter binding
   when a nonpositive value produced a violation. The binding is now retained.
4. A declared `gear.profile_shift` property, including an unavailable property,
   is now explicitly unresolved rather than silently treated as omitted. Its
   property binding is retained.
5. Construction now returns a no-candidate unresolved outcome unless the
   request has exactly one required joint matching the template joint.
6. Construction now returns a no-candidate unresolved outcome when the required
   axis/frame reference is absent; it no longer fabricates `joint:<id>`.
7. Direct and spur speed evaluation now rejects negative speed magnitudes,
   including negative usable bounds and negative optional motor speed input.

### Trust And Scope Checks

- No hidden torque, speed, efficiency, safety factor, material, or load default
  was found. Numeric physical assumptions are explicit inputs or bounded
  comparison tolerances.
- Continuous motor torque is read from `motor.continuous_torque_nm`; peak torque
  is checked separately and never substitutes for continuous torque. No stall
  torque substitution exists.
- Pure `calculate_spur_loads` uses the source-bound output-shaft design torque,
  not driver-side motor maximum capability and not an efficiency-adjusted value.
  Production M12-3 currently does not map nominal `Ft`/`Fr` into shaft planes
  because the template input has no explicit plane mapping; mesh-derived shaft
  loading therefore remains `UNRESOLVED`. Explicit transverse load vectors are
  the production-supported shaft path.
- Source-authoritative scalars and policy assumptions remain distinct through
  `InputProvenanceKind`; policy values are not flattened into canonical source
  authority. A source scalar is accepted only after its path resolves to an
  exact `{value, unit}` record and both the consumed source-reference hash and
  trusted scalar-record hash are revalidated; a scalar self-hash alone is not
  canonical authority.
- Consumed property bindings retain instance ID, specification hash, property
  key/hash, source identity, and authority. Result and nested hashes are
  revalidated before use.
- Candidate construction and evaluation do not mutate canonical state or the
  immutable candidate. Candidate lineage does not inherit evaluation results.
- Stale request, policy, requirement, candidate, and source-binding identities
  fail closed through revalidation and currentness/integrity gates.
- No M12-3 path calls CAD, FreeCAD, M10, M11, `ArtifactStore`, or
  `EvidenceStore`, and no artifact/evidence spam path exists.
- No comparison, ranking, selection, promotion, catalog search, optimizer, or
  automatic component selection was found.
- The implementation and report make no unsupported strength, life, fatigue,
  thermal, manufacturing, tolerance, bearing-capacity, or complete-machine
  safety claim.
- Missing structural topology remains a typed unresolved construction outcome
  with `candidate = None`; valid candidates with missing engineering authority
  remain candidates and produce unresolved engineering checks.

### Architecture Checks

- Exactly one M12-3 nominal spur arithmetic implementation exists at
  `mechcad_harness.engineering.spur.calculate_nominal_spur`; BuiltinTools maps
  that result and the revolute-drive calculations call the same primitive.
- M12-2 candidate models, candidate publication/currentness/integrity services,
  and `DesignState` semantics were not replaced or weakened.
- `RevoluteDriveRealizationService` remains stateless and has no state, CAD,
  provider, artifact, evidence, catalog, or optimizer dependency.
- The production entrypoint keeps the required order: source validation,
  bounded construction, immediate no-candidate return for incomplete topology,
  candidate integrity, candidate currentness, then pure engineering evaluation.
- The generic BuiltinTools layer does not import `revolute_drive`.

The generic M12-2 policy model can represent broader variable-bound policy
concepts, but the approved M12-3 surface uses only exact candidate-local value
admission: `allow-design-variable:<name>` with canonical JSON
`{"value": <variable.value>}` under `HARD_ADMISSIBILITY`. Missing or mismatched
admission returns an unresolved no-candidate construction outcome. M12-3 accepts
only explicit caller-supplied template inputs; no search or hidden
policy-derived physical value is introduced.

## Prior Task 8 Changed Files

The prior Task 8 wave changed only the following M12-3 files, in addition to
rewriting this report. All other dirty and untracked worktree changes were
preserved.

- `src/mechcad_harness/revolute_drive/calculations.py`
- `src/mechcad_harness/revolute_drive/service.py`
- `tests/unit/test_m12_motor_admissibility.py`
- `tests/unit/test_m12_spur_drive_sizing.py`
- `tests/unit/test_m12_shaft_sizing.py`
- `tests/unit/test_m12_revolute_drive_service.py`
- `docs/audit/MECHCAD_M12_3_COMPLETION_REPORT.md`

No commit, push, reset, clean, checkout, revert, or destructive operation was
performed.

## Final Fix Wave

The final fix wave changed the revolute-drive service/application trust boundary,
M12-3 fixtures and regressions, and this report/specification. It did not change
M12-2 candidate models or any CAD, M10, M11, catalog, selection, or promotion
code. Source-authoritative scalars now require exact canonical `{value, unit}`
records; candidate-local variables now require exact hard-admissibility policy
entries.

## Concerns And Recommendation

The worktree remains broadly dirty from prior M10/M11/M12 tasks and contains
generated project artifacts. Those changes were not inspected as Task 8 edits
and were not reverted. The normal `git diff --check` limitation for untracked
M12-3 files is documented above and was covered by direct scanning.

Recommendation: accept the bounded M12-3 claim. Do not extend it to production
mesh-derived shaft loading without explicit plane mapping, general mechanism
synthesis, automatic selection, variable-bound optimization, CAD realization,
M10/M11 execution, or unsupported physical strength/life/safety claims.

## Design / Engineering Scope

One revolute joint; direct drive and external spur reduction; explicit supplied
component snapshots; motor checks; nominal spur geometry/loads; and the bounded
two-support static solid-shaft model.

## Existing Capabilities Reused

M12-2 candidate authority, source binding, snapshots, topology, integrity,
currentness, canonical JSON hashing, BuiltinTools, and StateManager read APIs.

## New Production Services

`RevoluteDriveRealizationService` is pure. `ProductionApplication` exposes
`realize_and_evaluate_revolute_drive` with the source, construction, integrity,
currentness, and evaluation sequence.

## Direct-Drive Template

Motor, shaft, two bearings, hub, motor mount, driven body, required connections,
and one joint realization binding are constructed deterministically.

## External-Spur Template

The direct topology is extended with distinct driver/driven external spur gears,
gear mesh, gear output path, and explicit support mounts.

## Motor Admissibility

Continuous torque, separately declared peak torque, scalar speed, and optional
voltage checks are deterministic. Missing properties are unresolved and peak
torque never substitutes for continuous torque.

## Spur Geometry / Ratio

One shared `engineering.spur` primitive provides pitch diameters, center distance,
and `driven_teeth / driver_teeth` reduction magnitude.

## Transmission Torque / Efficiency

Real output torque is evaluated only with explicit efficiency. Missing efficiency
leaves torque transfer unresolved while ratio and speed remain independently
available; no hidden ideal-efficiency claim is made.

## Gear Loads

Pure nominal loads use `T_design_out` and driven pitch diameter. Production mesh
plane mapping remains unresolved without an explicit plane mapping.

## Shaft Model

Exactly two explicit simple radial supports and one load plane are supported for
static homogeneous solid circular-shaft loading.

## Shaft Sizing

Reactions, bending, torsion, von Mises stress, explicit yield/design factor, and
unrounded theoretical minimum diameter are independently tested. Selected shaft
diameter is a separate candidate-local value.

## Bearing / Support Scope

Support count/topology, nominal bore compatibility, and reactions are checked.
Bearing life, rating, compliance, preload, and retention are not claimed.

## Hub / Coupling / Mount Scope

Required identities, interfaces, attachment path, and nominal dimensions are
checked. Coupling capacity, key/spline strength, and fit/tolerance are not
claimed.

## Candidate Generation Boundary

Only explicit finite template inputs and exact hard-policy design-variable
admissions are accepted. No catalog, search, optimizer, ranking, or selection
exists.

## Engineering Outcome Semantics

Checks are `SATISFIED`, `VIOLATED`, or `UNRESOLVED`; aggregate precedence is
`VIOLATED` -> `INADMISSIBLE`, then `UNRESOLVED`, then `ADMISSIBLE`.

## Property Authority / Provenance

Consumed component properties retain instance/specification/property hashes and
authority. Source scalars require exact canonical `{value, unit}` records;
policy assumptions remain visibly distinct.

## Candidate Integrity / Currentness

M12-2 integrity and currentness gates reject forged/stale inputs. Construction
returns no candidate for incomplete topology; engineering gaps remain on valid
candidates as unresolved checks.

## Production Composition

The production entry point is read-only with respect to canonical state and does
not publish artifacts or Evidence.

## Direct-Drive Capstone

The explicit 24 V direct-drive fixture passes through production with deterministic
hashes and no canonical revision.

## Spur-Drive Capstone

The explicit external-spur fixture verifies compatibility, ratio 5, output speed,
efficiency-bound torque, interfaces, and shaft checks using explicit source-bound
transverse load vectors. It does not claim production mesh-plane mapping for
nominal `Ft`/`Fr` loads.

## Violation / Unresolved Cases

Insufficient authoritative capability produces `VIOLATED` and `INADMISSIBLE`;
missing efficiency, material, topology, or source proof remains distinct
`UNRESOLVED` behavior.

## Focused Tests

The final focused M12-3 command completed with `158 passed in 4.55s`.

## Predecessor Regressions

The Task 8 candidate-foundation/tools/state regression command had `36 passed`,
the Task 8 production/provider regression command had `66 passed`, and the
later final-fix candidate-foundation/production/BuiltinTools command had
`61 passed`. These commands use different overlapping test sets.

## Full Suite

`py -3 -m pytest tests/` completed with 1584 collected, 1550 passed, 34 skipped,
0 failed, and 0 errors in 1394.30 seconds.

## Compile / Diff

`compileall` passed. `git diff --check` reported only unrelated pre-existing
CRLF/EOF warnings; direct review found no M12-3 whitespace errors.

## Capability Claim

MechCAD can deterministically construct and evaluate bounded supplied-component
direct-drive and external-spur revolute-drive candidates with explicit motor,
spur, support, and static shaft checks, without canonical mutation.

## Remaining Limitations

No general synthesis, catalog, automatic selection, gear strength, bearing life,
fatigue, thermal duty, manufacturability, CAD, M10, M11, comparison, promotion,
or production spur mesh-plane load mapping.

## Files Changed

M12-3 source, tests, shared spur integration, application composition, approved
specification, capability reference, completion report, and verification records.

## Worktree Status

Changes remain uncommitted as required. Pre-existing unrelated dirty and
untracked files were preserved. No commit or push was performed.
