# Rotator V2 Epic 01: Physical Mechanism and Candidate Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implement and evaluate exactly one frozen source-bound Rotator V2 candidate through candidate M10-3.

**Architecture:** M12/M13 are accepted MechCAD capabilities consumed by this project; no platform implementation is authorized. S1 freezes reconciled project-local authority, S2/S3 construct typed candidate semantics, S4 realizes the candidate through existing CAD APIs, and S5 performs the exact candidate M10-3 scope. Stop after S5.

**Tech Stack:** Python 3.11+, Pydantic v2, existing MechCAD candidate/M13 models, ArtifactStore, ProductionApplication, FreeCAD 1.1.3, pytest.

## Global Constraints

- Project authority is `projects/rotator_v2/`; Epic namespace is `ROTATOR_V2_EPIC_01_PHYSICAL_MECHANISM_AND_CANDIDATE_EVALUATION`.
- `src/mechcad_harness/**` is protected. Do not create M12/M13 platform changes or fixture-only workarounds.
- Active motor geometry is only `components/5840-31ZY/normalized/5840-31ZY_normalized_mm.step`; `motor_az(1).step` is superseded history only.
- Candidate 01 uses exactly the Common Transmission and Geometry Table in the Epic Spec section `Candidate 01 Frozen Design Selection`. Those values are `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION`, not source or supplier facts.
- AZ output shaft/joint and motor output directions are +Z; EL output shaft/joint and motor output directions are +Y. In both spur pairs, the motor axis location is +66 mm in X from its output axis and the axes are parallel.
- Candidate 01 performs no optimization or alternative gearset/design search. Report M10 failure; do not silently redesign.
- Keep-out fidelity/role/pairs, support role, EL no-limit semantics, and the 45 configuration rule are exactly those in the Epic Spec.
- M11, selection, promotion, canonical work, manufacturing release, commits, tags, and pushes are prohibited.
- If existing production contracts are insufficient, stop with `ROTATOR_V2_EPIC_01_BLOCKED_BY_PRODUCTION_GAP` and contract evidence.

## Frozen Candidate 01 Table

This table is the normative execution summary. The Spec's `Candidate 01
Placement And Attachment Derivation Table` is the complete normative selection
and placement authority.

| Item | Frozen value | Classification / basis |
| --- | --- | --- |
| both gearsets | 30T/36T, module 2.0 mm, PA 20 deg, face 12 mm, CD 66 mm, ratio 1.20; actual pinion engagement 12 mm; accepted usable maximum 13 mm | 13 mm is accepted motor authority; 12 mm is `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` |
| AZ shaft | OD 60 mm, clear bore 40 mm, length 220 mm, Z=30..250 | first selection; bore is 30 + 2*5 mm |
| AZ journals and supports | journal 50 x20 mm; centers Z=60,180; spacing120; support bore/OD/radial-width/axial=50/80/15/20 mm | first selection; `MOUNT_OR_SUPPORT`, no catalog bearing |
| AZ hub, gear, and motor plate | hub OD/length/bore=70/30/60, Z=205..235; pinion/driven faces Z=220..232, centers Z=226; plate=100x80x3, X=16..116,Y=-40..40,Z=216.995646..219.995646, D20 opening, four D4.5 M4 holes | 12 mm engagement/overlap; exact-CAD plate/pinion separation 0.004354 mm, not manufacturing claim |
| AZ structure | base=350x350x20; carrier outer=120x120x200 at Z=20..220; retained 20x20 posts X/Y=-60..-40/-60..-40, -60..-40/40..60, 40..60/-60..-40; station-A X/Y=-60..60,Z=50..70 minus D50; station-B left rail X=-60..-35,Y=-60..60,Z=170..190, deliberately outside D50; continuous D40 corridor; deck=220x220x12 at Z=250..262 | `FINAL-CRIT-01` first-candidate structure revision; one carrier solid; rail/support-B rigid overlap 2616.094617 mm3 |
| AZ motor mount | motor output direction +Z; motor axis location X=66,Y=0,Z=220; retained +X/-Y post contact Y=-40, X=40..60, Z=216.995646..219.995646 | exact source-frame transform and direct generated attachment |
| EL shaft | OD 50 mm, length300 mm, Y=-150..150 | first selection |
| EL journals and supports | journal50x20; centers Y=-100,100; spacing200; support bore/OD/radial-width/axial=50/80/15/20 mm | first selection; `MOUNT_OR_SUPPORT`, no catalog bearing |
| EL hub, gear, and motor plate | hub OD/length/bore=70/30/50, Y=120..150; pinion/driven faces Y=135..147, centers Y=141; plate=100x80x3, X=16..116,Y=131.995646..134.995646,Z=480..560, D20 opening, four D4.5 M4 holes | 12 mm engagement/overlap; exact-CAD plate/pinion separation 0.004354 mm, not manufacturing claim |
| EL fork and axis | -Y arm X=-70..70,Y=-110..-90,Z=220..520; revised +Y arm X=-70..40,Y=90..110,Z=220..520; axis Z=520 | `FINAL-CRIT-01` first-candidate structure revision; +Y arm/support-B rigid overlap 30630.528373 mm3 |
| EL motor mount | output direction +Y; motor axis location +X66 from EL shaft at Y=135,Z=520; edge bridge X=16..40,Y=110..131.995646,Z=480..560, contacting revised +Y arm at Y=110 | exact source-frame transform and generated bridge selection |
| carrier/payload | rail X=-60..-50,Y=-180..180,Z=525..530; frozen pads and motor/pinion-side notches per Spec; boss center=(0,0,520), axis+Y, OD/bore/length=70/50/30; 3-pos=(0,-150,0),(0,0,0),(0,150,0); 2-pos=(0,-75,0),(0,75,0) | rail/pad envelope Z=510..530; complete boss-inclusive assembly Z=485..555; Y=-100,+100 are reference datums only |
| AZ keep-out | declared cylinder D30 mm, Z=30..130; hard>=24, preferred>=30, reserve>=100 | `DECLARED_BOUNDED_COLLISION_REPRESENTATION`; `PAYLOAD_OR_FRAME_ATTACHMENT`; reserved empty space |

The 6007/35 mm historical bearing seed is not selected. It cannot preserve the
frozen preferred 30 mm keep-out with 5 mm radial enforcement. No bearing catalog
selection is made.

Candidate 01 traceability is initial frozen design -> `FINAL-CRIT-01` ->
physical-realizability revision. Only generated structural first-candidate
selections change; trusted motor geometry/transforms and drive authority remain
unchanged.

## File Structure

| File | Responsibility |
| --- | --- |
| `projects/rotator_v2/epic_01/authority_manifest.json` | reconciled authority and frozen Candidate 01 selections |
| `projects/rotator_v2/epic_01/candidate_definition.py` | source binding, components, bodies, joints, and generated-part specifications |
| `projects/rotator_v2/epic_01/pair_policy.json` | complete pair classifications and explicit mating reasons |
| `projects/rotator_v2/epic_01/candidate_cad.py` | CAD mappings, representations, placements, and derivations |
| `projects/rotator_v2/epic_01/m10_configurations.json` | generated serialization of the normative 45-item configuration sequence |
| `tests/integration/rotator_v2_epic_01_fixtures.py` | production-composed fixture only |
| `tests/unit/test_rotator_v2_epic_01_*.py` | authority, mechanism, pairs, CAD, and configuration tests |
| `tests/integration/test_rotator_v2_epic_01_candidate_m10_production.py` | real FreeCAD candidate CAD/M10-3 test |

### Task 1: S1 Authority Reconciliation

**Files:** project stale authority documents; `projects/rotator_v2/epic_01/authority_manifest.json`; `tests/unit/test_rotator_v2_epic_01_authority.py`.

- [ ] Write a failing authority test for PASS/PASS/FAIL readiness, normalized STEP only, no-belt/external-spur markers, superseded raw STEP/direct EL coupling, retained holds, and exact frozen table values.
- [ ] Reconcile only stale project text and record Candidate 01 selections as design selections, never source facts.
- [ ] Run the focused authority test and confirm pass.

### Task 2: S2 Candidate Source Authority

**Files:** `projects/rotator_v2/epic_01/candidate_definition.py`; `tests/integration/rotator_v2_epic_01_fixtures.py`; `tests/unit/test_rotator_v2_epic_01_physical_mechanism.py`.

- [ ] Write failing tests for exactly `motor_AZ`/`motor_EL`, one trusted normalized representation, independent placements, 24 V/1000:1/rated torque authority, and prohibited stall credit.
- [ ] Build source binding and two instances using existing ArtifactStore/candidate APIs only.
- [ ] Run the focused mechanism test and confirm pass.

### Task 3: S3 Physical Mechanism

**Files:** `candidate_definition.py`; `pair_policy.json`; physical-mechanism and pair-policy unit tests.

- [ ] Write failing tests for three body memberships, two dedicated shafts, exactly two `MOUNT_OR_SUPPORT` stations per axis, frozen dimensions, gear paths, and motor torque-only roles.
- [ ] Write failing tests requiring `joint_az=CONTINUOUS` with no limits and `joint_el=CONTINUOUS` with no limits plus distinct requested evaluation interval metadata; reject `BOUNDED(0,360)`.
- [ ] Define physical semantic model, interfaces, generated-part specifications, frozen selections, and pair policy. Do not invoke CAD lowering in S3.
- [ ] Require the `FINAL-CRIT-01` AZ carrier topology: retained posts X/Y=-60..-40/-60..-40, -60..-40/40..60, 40..60/-60..-40, all Z=20..220; station-A X/Y=-60..60,Z=50..70 minus D50; station-B left rail X=-60..-35,Y=-60..60,Z=170..190 outside the D50 opening; D40 corridor; one connected carrier solid; and AZ support centers Z=60/180.
- [ ] Require keep-out fidelity `DECLARED_BOUNDED_COLLISION_REPRESENTATION`, role `PAYLOAD_OR_FRAME_ATTACHMENT`, same-body `SAME_RIGID_GROUP_EXCLUDED`, and `CHECK_CLEARANCE` at 5 mm against every constituent in the other two bodies. Require separate actual-geometry static invariants proving base/frame, carrier, supports A/B, motor mount, motor, and pinion preserve the stationary corridor where relevant.
- [ ] Freeze the full Candidate 01 placement/attachment derivation table: candidate frame hierarchy, exact motor target frames and transformed mount frames, canonical gear roll, carrier/boss/antenna transforms, plate/structure contacts, and every generated `GPD`. Require the Spec no-free-DOF audit to be `ALL=YES`.
- [ ] Freeze revised body membership and rigid interfaces: no `(50,+50)` AZ post, station-B rail/support-B overlap=2616.094617 mm3, revised +Y EL arm X=-70..40 with arm/support-B overlap=30630.528373 mm3, AZ plate contact only through retained +X/-Y post, and unchanged EL bridge contacts.
- [ ] Run focused S3 tests and confirm pass.

### Task 4: S4 Candidate CAD

**Files:** `candidate_cad.py`; CAD unit test.

- [ ] Write failing mapping tests: motors trusted; generated parts exact-generated; antennas and keep-out declared-bounded; one placement derivation per generated mapping.
- [ ] Write failing exact dimensional-interface tests independently of pair exclusion: cross-body `INTENDED_CONTACT_EXCLUDED` shaft/support and gear-mesh interfaces; same-body `SAME_RIGID_GROUP_EXCLUDED` shaft/hub, carrier-boss/shaft, motor D-shaft/pinion adapter, driven gear/hub, and motor/mount interfaces.
- [ ] Write independent literal-oracle placement tests: AZ/EL `OUTPUT_FRAME` target transforms and roll; transformed `MOUNT_FRAME`; D20/D4.5 plate topology and selected non-motor plate side; exact plate-to-carrier and bridge-to-fork/plate contacts; gear faces, overlap, 12 mm engagement, 13 mm authority maximum, and hub containment; carrier/PAYLOAD_FRAME and antenna transforms; boss-to-carrier attachment; rail/pad support/fork and motor/pinion-side clearance geometry. Do not derive expected transforms from the helper under test.
- [ ] Write a literal-oracle `SAME_BODY_SOLID_INTERFERENCE_CHECK`: derive all unordered distinct physical-solid pairs from actual body membership; compare that inventory to a literal, independently maintained Spec-declared rigid-interface ID set; require exact OCCT common volume zero for every remaining pair. Include a derived trusted-motor sub-gate covering motor_AZ against base, three retained posts, station-A, station-B left rail, supports A/B, and non-interface mount material; and motor_EL against both arms, supports A/B, bridge, non-interface mount material, AZ deck/shaft/hub/gear, and every new bracket. Do not hand-list only historical collisions or derive exemptions from the construction helper/outcomes.
- [ ] Require topology oracles: revised AZ carrier has one solid and D40 corridor common volume zero; station-B rail/support-B and revised +Y arm/support-B have their declared rigid overlap volumes; supports, retained AZ mount post, EL arms, and edge bridge have their frozen connections.
- [ ] Generate representations, CAD mappings, placements, and derivations from frozen specifications; invoke `ProductionApplication.realize_candidate_cad()` only here.
- [ ] Run S4 focused tests and confirm pass.

### Task 5: S5 Candidate M10-3

**Files:** `m10_configurations.json`; configuration unit test; production M10 integration test.

- [ ] Write the configuration test with its own literal oracle: `AZ_EXPECTED=(0,90,180,270,360)`, `EL_EXPECTED=(0,45,90,135,180,225,270,315,360)`, and `expected=tuple((az,el) for az in AZ_EXPECTED for el in EL_EXPECTED)`.
- [ ] Require the implementation sequence to have 45 unique IDs, ordered pairs exactly equal to that oracle, `cfg_000=(0,0)`, and `cfg_044=(360,360)`; do not read expected values from JSON, builder output, or its helper.
- [ ] Keep FK periodic checks at -1080,-720,-360,+360,+720,+1080 separate from M10: no extra configurations, pair measurements, or continuous claims.
- [ ] Execute `ProductionApplication.evaluate_candidate_multi_joint_m10()` after candidate CAD realization; require real FreeCAD, complete exact pair scope, finite exact measures, durable candidate Evidence, and zero skips.

After S5: **STOP IMPLEMENTATION.** Independent acceptance is a separate session.

## Normative M10-3 Sequence

The M10-3 configuration sequence is exactly the AZ-major, EL-minor Cartesian
product of `AZ=(0,90,180,270,360)` and
`EL=(0,45,90,135,180,225,270,315,360)`: 45 configurations, `cfg_000=(0,0)`
through `cfg_044=(360,360)`. Serialization may be generated from those two
arrays only when its ordered result is identical. The accumulated AZ values
`-1080,-720,-360,+360,+720,+1080` are FK periodicity checks only and never
enter this M10 sequence or its pair-measurement scope.

## Mandatory Regression Gates

After all Epic 01 focused tests pass and the Epic 01 production M10 test passes
with zero skips, run these protected suites without changing their sources,
goldens, skips, or expectations:

```text
tests/integration/test_m13_4_full_stack_acceptance.py
tests/integration/test_m13_3_candidate_m10_production.py
tests/integration/test_m13_3_generic_multi_joint_acceptance.py
tests/integration/test_m13_2_generated_parts_live.py
tests/integration/test_m12_candidate_cad_m10_production.py
tests/integration/test_m12_6_end_to_end_external_spur.py
```

All six must pass under their existing accepted skip policy. Then run
`python -m compileall -q src tests` and `git diff --check`. A fresh broader/full
suite is required if the normal repository acceptance policy requires it for
project integration; it is not discretionary and must follow that policy.

## Stop Conditions

Stop with `ROTATOR_V2_EPIC_01_BLOCKED_BY_PRODUCTION_GAP` if current APIs cannot
bind both motors, represent the frozen candidate, lower its CAD, bridge its
three-body/two-joint exact pair scope, or run real-FreeCAD M10-3. Do not change
`src/mechcad_harness/**` or weaken coverage to bypass a gap.
