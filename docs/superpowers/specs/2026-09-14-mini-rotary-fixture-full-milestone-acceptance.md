# MINI_ROTARY_FIXTURE Full Milestone Acceptance

## Purpose

`MINI_ROTARY_FIXTURE` is a project-local, bounded single-axis mechanical
acceptance fixture. Its purpose is to exercise the maximum truthful subset of
the current M0 through M13 capability chain. It is not a mechanism-design,
component-selection, manufacturing, or safety project, and it does not accept
itself independently.

## Authority And Protected Surfaces

- The canonical authority is `DesignState`; all canonical mutation uses the
  current trusted `ChangeProposal` / `ChangeSet` / `ChangeEngine` machinery
  under ownership policy and project lock, via `RunController` where the current
  API requires it.
- New files are limited to `projects/mini_rotary_fixture/`, the named new
  project Spec/Plan, and the new completion claim.
- Existing `src/mechcad_harness/**`, accepted audits, accepted Specs/Plans,
  normative architecture, reconstruction history, and existing tests/goldens
  are protected and must not be modified for this fixture.
- No commit, push, tag, release, package installation, or history rewrite is
  permitted.
- FreeCAD, OpenCode, Gmsh, and CalculiX may be invoked only when their already
  configured production runtime is available. Their actual invocation, not
  availability or importability, is required for a live claim.

## Fixture Authority

The world origin is the rotary axis center at the actuator mounting plane and
the base lower reference plane. `Z=0` is that lower mounting/reference plane;
`+Z` is upward along the rotary axis. The frame is right-handed.

The final requirements are a 6.0 N load, 0.025 m lever arm, torque safety
factor 2.0, 5.0 RPM output speed, 24 V, 5.0 mm minimum clearance, and one
continuous +Z revolute joint evaluated from 0 through 360 degrees.

The base is `120 x 120 x 10 mm`, spanning X/Y `-60..60` and Z `0..10`. The
fixed clearance wall spans X `50..60`, Y `-60..60`, and Z `45..95`. The
rotating plate has bottom Z `55` and thickness `8 mm`.

Two explicit noncanonical candidates share all authority, topology, actuator,
shaft, supports, hub, mount, wall, axis, and load conditions. They differ only
in `top_plate_side_mm`:

| Candidate | Plate side |
| --- | ---: |
| A | 60.0 mm |
| B | 50.0 mm |

The anticipated clearance ordering is non-authoritative. FreeCAD/M10 results
are the sole clearance evidence.

The synthetic supplied actuator is user-authoritative fixture input, not
manufacturer or supplier evidence: `fixture_actuator_01`, 24 V, 0..6 RPM usable
speed, 1.0 N*m continuous torque, +Z 8 mm output shaft, and four 3.2 mm mount
holes at `(+/-10, +/-10)`. Its synthetic envelope is `30 x 30 x 20 mm`.
Numeric shaft and mount interface facts must use the current supplied-component
interface model and remain distinct from STEP geometry.

The direct-drive shaft authority is 8 mm diameter, 120 MPa synthetic yield
strength, factor 2.0, transverse load `(Y=6.0 N, Z=0.0 N)`, support coordinates
0 and 20 mm, and load plane 10 mm. The fixture uses exactly two synthetic radial
supports when required by the current direct-drive template.

For a standalone M11 probe only, the top plate's fixture material is
`fixture_linear_elastic_aluminum`, E=69 GPa, Poisson ratio=0.33, density=2700
kg/m3, with a 6 N structural load. This is neither material selection nor a
safety, yield, fatigue, convergence, or manufacturing claim.

## Staged Authority Protocol

Revision 1 contains the 4.0 N force, 0.025 m lever arm, factor 2.0, 24 V,
5.0 mm clearance, and actuator/interface authority. It deliberately omits target
output speed.

The project owner releases 5.0 RPM only in response to a supported output-speed
`ConstraintRequest`. The project acceptance record preserves the
user-authoritative source value exactly as `5.0 RPM`; the harness resolution
record uses the deterministically normalized `0.5235987755982988 rad/s` required
by the current contract. This does not create a dependency from speed to torque.

The resolution must be applied through the existing project-local
`ProductionApplication.create(..., ownership_path=..., dependency_path=...)`
composition points. Before writing a local ownership rule, the fixture checks
whether the current worktree already owns `/authoritative_parameters` through
`mechcad-resolution`; if so, it reuses that owner. The project-local dependency
configuration preserves the existing dependency rules; this fixture exercises
the force Requirement as the staged torque-invalidation trigger and adds no
output-speed-to-torque dependency.

After valid N1 torque Evidence exists, force changes from 4.0 to 6.0 N only by
replacing the existing torque Requirement description through trusted change
machinery. The prior torque Evidence is checked for actual M3 freshness, then
the trusted deterministic torque tool recomputes and persists fresh Evidence.
Expected arithmetic is not manually entered as Evidence: N1 design torque is
0.20 N*m and the final design torque is 0.30 N*m.

## Dual Truthful Paths

The core path uses the existing bounded M12 direct-drive route: source binding,
component property snapshots, direct-drive realization, motor checks, shaft
equilibrium/admissibility, physical topology and joint binding, candidate CAD,
complete M10 pair inventory, evaluation, comparison, explicit selection,
promotion, and fresh canonical reconstruction/CAD/M10 verification.

Square top plates remain on the existing M12 candidate CAD path. They are not
an M13-2 claim.

M13 is an independent, complementary probe path. M13-1 exercises numeric
supplied shaft/mount interface authority. M13-2 exercises only naturally
representable cylindrical generated parts such as shaft or hub. M13-3P/M13-3
and M13-4 are attempted only where the current one-joint physical topology is
accepted. The fixture must not add an M12-to-M13 bridge. Any absent cross-path
mapping is reported as `EXISTING_CAPABILITY_NOT_WIRED_TO_THIS_PATH`.

M10-2 through M10-4 are attempted with the one-joint topology only where their
models explicitly permit it. No dummy joint is created. M7B, M7D, and M7E are
not applicable domain/historical reference paths and must not import Yagi
semantics or adapters.

## Runtime, Evidence, And Documentation

The fixture must create `README.md`, `EXECUTION_LOG.md`, and
`MILESTONE_COVERAGE.md` under `projects/mini_rotary_fixture/`. The coverage
matrix records M0 through M13 requested rows with the permitted capability
statuses, applicability, production composition, live-execution status, exact
evidence, and blocker reason.

The execution log is append-only for significant stages and includes timestamp,
milestone/substep, source revision/hash, run ID, API/path, command, provider
identity, changed files, artifact/Evidence IDs, outcome, and any failure,
classification, remediation, and rerun result.

The project attempts isolated noncanonical M5.5 gear, material, and section
provider probes only through already installed and supported APIs. It records
whether each is default, optional, unwired, unavailable, or failed. It never
uses their output as final fixture authority.

The fixture attempts the real OpenCode transport without crediting a fake agent.
It separately records the M11 post-promotion eligibility handoff. If ineligible
or unresolved, it may attempt an ordinary source-bound M11 analysis on the same
authoritative plate as `M11_STANDALONE_SUBSYSTEM_PROBE`; this must never be
reported as candidate-to-M11 integration.

The completion claim at
`docs/audit/MECHCAD_MINI_ROTARY_FIXTURE_COMPLETION_REPORT.md` is a claim only,
not independent acceptance. It reports core verdict, complete coverage matrix,
state/evidence/provenance chains, runtime commands/results, artifacts,
remediations, worktree state, protected-surface checks, and unresolved gaps.

## Success Criteria

Core success requires the connected authority -> trusted revisions -> torque
tool/Evidence -> agent where available -> final state -> direct-drive candidates
-> real FreeCAD CAD -> M10 candidate evaluation -> comparison -> explicit
selection -> promotion -> fresh canonical CAD/M10 path. Its only valid verdicts
are `MINI_ROTARY_FIXTURE_CORE_PASSED` and
`MINI_ROTARY_FIXTURE_CORE_REJECTED`.

Maximum coverage additionally includes persistence/recovery, M5.5, M10 v2,
M11, and M13 probes. It is reported as `MILESTONE_COVERAGE_COMPLETE` or
`MILESTONE_COVERAGE_PARTIAL` with exact blockers. A supplemental failure does
not erase an independent core success.
