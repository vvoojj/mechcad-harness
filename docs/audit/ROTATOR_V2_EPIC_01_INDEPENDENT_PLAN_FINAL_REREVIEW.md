# Rotator V2 Epic 01 Independent Plan Final Rereview

## Verdict

```text
ROTATOR_V2_EPIC_01_PLAN_REVISE
```

`REREVIEW-IMP-01` is CLOSED. The revised Spec and Plan now freeze a complete,
unambiguous frame hierarchy, deterministic motor transforms, deterministic gear
stacks, deterministic carrier/boss/antenna placement, a complete
placement-derivation table, and a passing no-free-DOF audit. Every numeric
clearance relationship claimed by the documents was independently reverified and
holds. However, exact boolean evaluation of the accepted normalized motor STEP
under the frozen placement transforms exposes one new CRITICAL physical
realizability defect (`FINAL-CRIT-01`) that no declared Epic check can detect.

## Independence

This was a read-only plan audit. No production source, project authority, Spec,
Plan, test, golden, CAD artifact, candidate runtime artifact, or evidence was
modified. The only repository write is this report. FreeCAD was used solely to
load the accepted normalized STEP and measure exact boolean relationships of the
frozen geometry; no CAD was generated as implementation and no Epic M10 was
executed.

## Documents And Authorities Reviewed

- `docs/superpowers/specs/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/superpowers/plans/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/audit/ROTATOR_V2_EPIC_01_INDEPENDENT_PLAN_REVIEW.md` (unchanged, not overwritten)
- `docs/audit/ROTATOR_V2_EPIC_01_INDEPENDENT_PLAN_REREVIEW.md` (unchanged, not overwritten)
- `docs/audit/MECHCAD_M13_4_INDEPENDENT_FINAL_ACCEPTANCE.md`
- `projects/rotator_v2/components/5840-31ZY/5840-31ZY_AUTHORITY.yaml`
- `projects/rotator_v2/components/5840-31ZY/MOTOR_SCALE_CONFIRMATION.md`
- `projects/rotator_v2/components/5840-31ZY/normalized/5840-31ZY_normalized_mm.step` (measurement only)
- Production contracts: `candidates/cad_realization.py`,
  `models/generated_placement.py`, `cad.py`,
  `backends/adapters/py_gearworks.py`, `candidates/models.py`,
  `models/multi_joint_verification.py`

Upstream authorization remains `M13_4_INDEPENDENT_FINAL_ACCEPTED` with
`ROTATOR_V2_MAY_RESUME = YES`. The protected `src/mechcad_harness/**` boundary,
the consume-not-reimplement posture, and the S1..S5 then STOP boundary are
preserved in the revised documents.

## Measurement Method

The accepted normalized STEP was transformed exactly as the Spec's placement
table freezes it:

- AZ: identity rotation, `OUTPUT_FRAME` origin to `(66, 0, 220)`.
- EL: source `X->X`, `Y->-Z`, `Z->Y`, `OUTPUT_FRAME` origin to `(66, 135, 520)`.

Exact OCCT `common()` booleans were then computed between the transformed
trusted motor solid and each frozen generated structural solid, and between the
frozen EL pinion cylinder (tip radius 32 mm) and the carrier pads. All volumes
quoted below are exact boolean result volumes.

## Frame Hierarchy

Verified against Spec lines 131-138: `BASE_FRAME` origin `(0,0,0)`;
`AZ_AXIS_FRAME` origin `(0,0,0)` axis `+Z`; `AZ_ROTATING_FRAME` at AZ=0
coincident; `EL_AXIS_FRAME` origin `(0,0,520)` axis `+Y` in `AZ_ROTATING_FRAME`;
`EL_ROTATING_FRAME` at EL=0 coincident; `PAYLOAD_FRAME` origin `(0,0,0)` in
`EL_ROTATING_FRAME`, home world origin `(0,0,520)`, axes `+X` boresight, `+Y`
antenna spacing, `+Z` upward. Every origin, axis, handedness, and roll is
frozen. The EL local map `X->X, Y->-Z, Z->Y` is right-handed
(`X x (-Z) = Y`). PASS.

## motor_AZ Trusted Placement

- Target `OUTPUT_FRAME` origin `(66,0,220)`, source `X/Y/Z -> candidate X/Y/Z`
  (Spec line 161). No free roll. PASS.
- The accepted authority, not the STEP model origin, is the datum
  (Spec lines 140-143). PASS.
- Authority `output_frame.origin_mm[2] = 30.043545` and
  `mount_frame.origin_mm[2] = 27.039191` give exactly
  `3.004354 mm` negative source `+Z` offset. The same rigid transform carries
  `MOUNT_FRAME`. PASS.
- Transformed AZ mount plane `Z = 220 - 3.004354 = 216.995646`; plate
  `100 x 80 x 3` at `Z = 216.995646 .. 219.995646` on the non-motor side, D20
  opening, four D4.5 holes at the transformed accepted M4 STEP centers
  (authority `mounting_interface.step_hole_centers_mm`). PASS.
- Plate extent is uniquely determined by the frozen contacts: `Y = -40..+40`
  (post contact faces) and `X = 16..116` (100 mm about the motor axis at
  `X=66`), consistent with the EL bridge contact `X = 16..40` that pins the
  same 100 mm X extent. No residual placement freedom. PASS.

## motor_EL Trusted Placement

- Target `OUTPUT_FRAME` origin `(66,135,520)`; `source X->X, Y->-Z, Z->Y`
  (Spec line 170). Right-handed; all free roll removed. PASS.
- `MOUNT_FRAME` receives the same rigid transform; mount plane
  `Y = 135 - 3.004354 = 131.995646`; plate `100 x 80 x 3` at
  `Y = 131.995646 .. 134.995646`, D20 opening, four D4.5 transformed M4
  holes; plate extent `X = 16..116`, `Z = 480..560` is pinned by the frozen
  edge-bridge contact. PASS.

## Gear Stacks

AZ: shoulder `Z=220`; usable zone `Z=220..233` (accepted 13 mm); pinion and
driven faces `Z=220..232`; face center `Z=226`; engagement `12 mm`; margin
`1 mm`; hub `Z=205..235` fully contains the driven faces. PASS.

EL: shoulder `Y=135`; usable zone `Y=135..148`; pinion and driven faces
`Y=135..147`; face center `Y=141`; engagement `12 mm`; margin `1 mm`; hub
`Y=120..150` fully contains the driven faces. PASS.

## Plate / Pinion Exact-CAD Separation

AZ plate ends `Z=219.995646`, pinion begins `Z=220`; EL plate ends
`Y=134.995646`, pinion begins `Y=135`; separation is exactly `0.004354 mm` in
both stacks, derived exactly from `30.043545 - 27.039191 = 3.004354`. This is
about 4.4e3 times the OCCT kernel confusion tolerance (1e-7 mm), both
constituents are same-body (never measured by M10), and no production contract
or kernel-tolerance evidence indicates the spacing cannot be represented
reliably. The documents correctly disclaim manufacturing-tolerance and
clearance-claim semantics.

`PLATE_PINION_EXACT_CAD_STACK = PASS`

## Mount Attachments

AZ plate: contacts the +X carrier posts at `Y=-40/+40`, `X=40..60`,
`Z=216.995646..219.995646`; transform and `base_body` ownership are
deterministic; the plate is not floating. Determinism PASS. Physical validity of
the mounted motor fails - see `FINAL-CRIT-01`.

EL edge bridge: `X=16..40, Y=110..131.995646, Z=480..560` in
`az_rotating_body`; fork contact `Y=110, X=16..40, Z=480..520` (the +Y fork
arm's +Y face), plate contact `Y=131.995646` over the full bridge height;
truthfully connects the fork to the plate; no placement DOF remains.
Determinism PASS. Physical validity of the mounted motor fails - see
`FINAL-CRIT-01`.

## Carrier Attachment And Topology

- Boss: center `(0,0,520)` home world, axis `+Y`, `OD/bore/length = 70/50/30`,
  `Y=-15..15`; fused to the carrier in `el_payload_body`; not fused into the
  separately declared EL shaft constituent; D50 bore mates EL shaft OD50; no
  fork/support attachment; `Y=-100/+100` remain reference datums only. PASS.
- Topology: left rail `X=-60..-50, Y=-180..180, Z=525..530`; five pads exactly
  as frozen (`X` limits `-60..60`, `-60..60`, `-60..60`, `-60..40`, `-60..29`;
  `Z=510..530`); boss-inclusive envelope `X=-60..60, Y=-180..180, Z=485..555`.
  Fully deterministic; not a solid plate. PASS.

## Carrier Cross-Body Geometry

Independently rechecked and confirmed by exact boolean measurement:

- support A `Y=-110..-90`, support B `Y=90..110`; adjacent pad gaps exactly
  `5 mm` (two-left pad `-85..-65`, two-right pad `65..85`).
- rail/support radial clearance `sqrt(50^2 + 5^2) - 40 = 10.2494 mm` (rail
  corner `X=-50, Z=525` against the 80 mm support housing).
- rail begins `Z=525`, fork ends `Z=520`: exactly `5 mm` vertical separation.
- two-right pad motor-side X limit `40`: the transformed trusted motor's
  minimum-X extent is `66 - 20.122390 = 45.877610` (measured from the accepted
  STEP bounding geometry relative to the output axis), giving `5.877610 mm`
  clearance; the plan's "at least 5.877 mm" claim holds. Exact boolean common
  volume with the pad: `0.000000 mm^3`.
- three-right pad pinion-side X limit `29`: EL pinion tip radius 32 about
  `X=66` gives minimum X `34`, exactly `5 mm` clearance. Exact boolean common
  volume with the pad: `0.000000 mm^3`.
- EL motor vs bridge, EL supports A/B housings, carrier pads, EL boss, EL
  shaft, EL hub, and EL driven gear: all exact common volumes `0.000000 mm^3`.

PASS.

## Antenna Transforms

Three-antenna nominal `(0,-150,0), (0,0,0), (0,150,0)` and two-antenna nominal
`(0,-75,0), (0,75,0)` in `PAYLOAD_FRAME`; nominal `X=0` and `Z=0` frozen
(Spec lines 103-104, 177). The `X=-100..+100` fore/aft range remains adjustment
authority only and Candidate 01 M10 uses the frozen nominal positions; no
trusted antenna STEP claim is introduced. PASS.

## Gear Phase / Roll

`SpurGearCadInput` (`cad.py`) exposes only module, teeth, face width, pressure
angle, profile shift, and bore - no phase or roll input. The py_gearworks
adapter constructs `SpurGear(...)` with no rotation argument and meshes via a
deterministic `mesh_to` call. The Spec's claim (lines 149-151) is true:
canonical generator orientation plus local `+X` mapping removes all Candidate 01
gear-roll freedom. PASS.

## Placement Derivation Table

Audited against `CandidateCadRealizationRequest@2`
(`candidates/cad_realization.py:913-1029`): every `EXACT_GENERATED_GEOMETRY`
mapping requires exactly one placement derivation targeting it; derivation
sources/targets must be candidate instances; targets must be unique; chains
must be acyclic. `coaxial-generated-placement@1` requires an axisymmetric
target interface (`*:shaft` / `*:bore:*:near|far`) and DESIGN_SELECTION
axial-offset inputs; `frame-generated-placement@1` requires source and target
frames plus exactly one rotation input.

Every row of the Spec's placement table maps onto a satisfiable form:

- trusted motors (`motor_AZ`, `motor_EL`): imported-component placement, no GPD
  required - correctly none specified.
- declared-bounded constituents (antenna envelopes, AZ keep-out): no GPD
  required - correctly none specified.
- exact-generated constituents (plates, pinions, driven gears, hubs, shafts,
  supports, base, carrier, deck, fork, edge bridge, boss, carrier): each row
  supplies parent/body frame, source-to-target transform, axis, roll, and
  attachment; each is expressible as one coaxial or frame GPD with frozen
  DESIGN_SELECTION inputs (for example pinions coaxial on the motor D-shaft
  interface, gears/hubs coaxial on `*:shaft`, supports on generated bores,
  plates and bridge and carrier via frame rules with frozen frames).

The Plan requires one derivation per generated mapping (Task 4). The table is
complete; no exact-generated constituent lacks a frozen derivation, and no
constituent has two. PASS.

## No-Free-Placement-DOF Audit

Independently checked per constituent: X, Y, Z, axis, roll, parent, and
attachment/interface are frozen for motors and motor plates (including
MOUNT_FRAME roll and plate side), shafts, hubs, gears, supports, base, carrier,
deck, fork, bridge rail, boss, antenna envelopes, and keep-out. Gear roll is
structurally absent from the generator. The Spec's `ALL=YES` claim is
independently confirmed at the determinacy level. PASS.

## S3 / S4 Ownership

S3 freezes semantic frames, exact placements, attachments, interfaces,
derivation inputs, and body ownership, and must not invoke CAD lowering
(Spec lines 300-302; Plan Task 3). S4 performs the trusted motor transforms,
CAD mappings, generated geometry, GPD records, independent transform/interface
tests, and candidate CAD realization, and is the only caller of
`ProductionApplication.realize_candidate_cad()` (Plan Task 4). No ownership
regression. PASS.

## Test Oracle Adequacy

Plan Task 4 requires independent literal-oracle tests for motor OUTPUT_FRAME
transforms and roll, transformed MOUNT_FRAME, plate side/orientation, D20/D4.5
plate topology, plate-to-carrier and bridge-to-fork/plate contacts, gear faces,
overlap, 12 mm engagement, 13 mm authority maximum, hub containment,
carrier/PAYLOAD_FRAME and antenna transforms, boss-to-carrier attachment,
rail/pad support/fork clearance, and motor-side/pinion-side notch clearance,
and explicitly forbids deriving expected values from the helper under test. PASS.

## Previous Findings

- IMPORTANT-1 (transmission determinacy): CLOSED, unchanged.
- IMPORTANT-3 (keep-out semantics): CLOSED, unchanged.
- IMPORTANT-4 (M10 configuration determinacy): CLOSED, unchanged.
- IMPORTANT-5 (regression gates): CLOSED, unchanged (same six protected suites).
- MINOR-1 (S3/S4 ownership): CLOSED.
- MINOR-2 (EL angle-limit semantics): CLOSED.
- MINOR-3 (excluded-interface validation): CLOSED.
- MINOR-4 (support-station role): CLOSED.
- REREVIEW-IMP-01 (placement/attachment determinacy): **CLOSED.** All listed
  gaps - carrier placement and attachment, antenna envelope transforms, gear
  face positions, pinion engagement, motor roll, transformed MOUNT_FRAME, plate
  placement, plate-to-structure attachment, and GPD inputs - are now frozen and
  independently verified above.

No regression of any previous finding.

## Production Gap

None. Every frozen mapping is representable by existing production contracts
(`realize_candidate_cad`, `candidate-cad-realization-request@2`, both GPD
rules, trusted imported-component placement, exact-generated and
declared-bounded fidelities). The defect below is a frozen-design defect, not a
production gap.

## New Findings

### FINAL-CRIT-01 - Frozen Candidate 01 embeds each trusted motor inside its own mounting structure

CRITICAL. Measured, not speculative: the accepted normalized motor STEP
(`5840-31ZY_normalized_mm.step`) was transformed exactly as frozen and
intersected with the frozen generated structure. Three same-body solid
intersections exist:

```text
AZ motor body vs +Y AZ carrier corner post (base_body):
    common volume = 3992.706 mm^3
AZ motor body vs AZ carrier station plate 2, Z=170..190 (base_body):
    common volume = 780.268 mm^3
EL motor body vs +Y EL fork arm, Y=90..110 (az_rotating_body):
    common volume = 16542.031 mm^3
```

Cause: the frozen AZ roll (`source X/Y/Z -> candidate X/Y/Z`) points the
motor can along candidate `+Y` (measured STEP extent reaches
`Y = +97.87` relative to the output axis) from the mount plane at
`Z = 216.995646` down to `Z = 162.398`, so the can sweeps through the
`Y=40..60` post that the AZ mount plate bolts to and through the `Z=170..190`
station plate. The frozen EL roll (`source Y->-Z`) points the can downward from
the mount plane at `Y = 131.995646` to `Y = 77.398` with its cross-section
centered near `Y ~ 97`, straight through the `Y=90..110` fork arm below the
edge bridge. No roll choice within the frozen axis offsets avoids both; the
frozen design itself is contradictory.

Why this blocks acceptance:

1. Candidate 01 is physically unrealizable as specified: a motor cannot be
   bolted to a plate that is carried by posts the motor body passes through,
   and cannot be bridged off a fork arm it is embedded `~25 mm` deep into.
2. The Epic's declared checks structurally cannot detect any of the three:
   all three pairs are same-body, therefore `SAME_RIGID_GROUP_EXCLUDED` in M10
   and never measured; the declared S4 checks cover only interface dimensions
   (shaft/hub, carrier-boss/shaft, motor D-shaft/pinion, driven gear/hub,
   motor/mount pattern); the declared static invariants cover only the keep-out
   corridor.
3. Consequently S4 realization (which fuses same-body constituents into valid
   solids) and S5 M10-3 could succeed and publish trusted candidate Evidence
   for an impossible mechanism - the exact silent failure the Spec prohibits
   ("M10 failure is reported; it must not cause a silent redesign").

Required revision before implementation: as a separately authorized Candidate 01
design revision, freeze a motor can orientation/mount geometry and/or carrier
post, station-plate, and fork-arm geometry that removes all three same-body
intersections, and add declared S4 static same-body interference invariants for
each motor against its own body's structural constituents. All values remain
`DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION`.

MINOR: none.

NOTE: The measured motor minimum-X clearance is `5.877610 mm`; the plan's
"at least 5.877 mm" phrasing remains a true lower bound.

## Acceptance Decision

`REREVIEW-IMP-01` is closed and every determinacy, frame, stack, attachment,
topology, clearance, configuration, ownership, and oracle requirement passes
independent verification. `FINAL-CRIT-01` alone prevents acceptance: the frozen
candidate embeds each motor in its own mounting structure, and the Epic's
declared evaluation cannot see it. Implementation must not begin until that
CRITICAL finding is corrected by an authorized design revision and independently
rereviewed.

```text
ROTATOR_V2_EPIC_01_PLAN_REVISE
```
