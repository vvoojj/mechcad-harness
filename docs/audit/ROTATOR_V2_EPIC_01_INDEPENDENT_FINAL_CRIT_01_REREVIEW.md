# Rotator V2 Epic 01 Independent FINAL-CRIT-01 Rereview

## Verdict

```text
ROTATOR_V2_EPIC_01_PLAN_INDEPENDENTLY_ACCEPTED
```

`FINAL-CRIT-01` is **CLOSED**. The authorized physical-realizability
revision removes all three previously measured same-body motor collisions using
only frozen generated structure changes. The accepted normalized motor STEP,
the two trusted output-frame transforms, the drive stacks, and platform APIs
remain unchanged. No new CRITICAL or IMPORTANT finding was found.

## Independence And Scope

This is a read-only independent plan acceptance rereview. The accepted
normalized STEP was loaded only for exact FreeCAD/OCCT planning measurements.
No Epic implementation, test, project authority, Spec, Plan, production source,
candidate artifact, M10 execution, commit, tag, or push was modified. The only
repository write is this report.

Reviewed inputs:

- `docs/superpowers/specs/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/superpowers/plans/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/audit/ROTATOR_V2_EPIC_01_INDEPENDENT_PLAN_FINAL_REREVIEW.md`
- `projects/rotator_v2/components/5840-31ZY/5840-31ZY_AUTHORITY.yaml`
- `projects/rotator_v2/components/5840-31ZY/normalized/5840-31ZY_normalized_mm.step`

## Measurement Method

The accepted normalized motor STEP was independently loaded. `motor_AZ` used
the authority `OUTPUT_FRAME` origin `[0.093360, -5.137859, 30.043545]` mapped
with identity orientation to `(66,0,220)`. `motor_EL` used the same source
origin mapped to `(66,135,520)` under the right-handed map `X->X`, `Y->-Z`,
`Z->Y`. The current Spec dimensions were then independently constructed as
planning solids and exact OCCT `common().Volume` booleans were measured.

All values below are mm^3. A displayed zero is the exact returned OCCT volume,
not a rounded positive value.

## Current Geometry Verification

The current frozen AZ carrier contains exactly these retained posts, each
`Z=20..220`:

| Post | X | Y |
| --- | --- | --- |
| 1 | -60..-40 | -60..-40 |
| 2 | -60..-40 | 40..60 |
| 3 | 40..60 | -60..-40 |

There is no current `(+50,+50)` post. Station A is `X/Y=-60..60`,
`Z=50..70`, minus its D50 opening. The only current station-B member is the
left rail `X=-60..-35`, `Y=-60..60`, `Z=170..190`; no full station-B plate is
frozen.

The current EL fork is likewise unambiguous: the -Y arm is
`X=-70..70`, `Y=-110..-90`, `Z=220..520`; the revised +Y arm is
`X=-70..40`, `Y=90..110`, `Z=220..520`. The superseded wider +Y arm is absent.
Support centers remain Y=-100 and Y=+100.

## AZ Exact Recheck

| `motor_AZ` against current same-body solid | Exact common volume |
| --- | ---: |
| base plate | 0.000000000000 |
| retained post 1 | 0.000000000000 |
| retained post 2 | 0.000000000000 |
| retained post 3 | 0.000000000000 |
| station A | 0.000000000000 |
| station-B left rail | 0.000000000000 |
| support A | 0.000000000000 |
| support B | 0.000000000000 |
| generated AZ motor plate | 0.000000000000 |

**AZ motor intersection verdict: PASS.** The prior `3992.706 mm^3` post and
`780.268 mm^3` station-plate collisions cannot enter the current inventory.

### AZ Carrier, Corridor, And Mount

- The fused revised carrier has exactly one OCCT solid.
- Station A overlaps each retained post by `7999.999999999998 mm^3`.
- The station-B rail overlaps each retained -X post by
  `7999.999999999998 mm^3`.
- Station-B rail/support-B common volume is `2616.094617367086 mm^3`, matching
  the frozen declared rigid interface `2616.094617367 mm^3` within kernel
  representation.
- The carrier/D40 corridor common volume is `0.000000000000 mm^3`.
- The station-B rail/D40 and rail/D50 common volumes are both
  `0.000000000000 mm^3`; station A/D50 is also `0.000000000000 mm^3`. The rail
  therefore preserves both the protected D40 corridor and the local D50
  support-opening semantics.
- The AZ plate is frozen at `X=16..116`, `Y=-40..40`,
  `Z=216.995646..219.995646`. Its only structural contact is the retained
  +X/-Y post face at `Y=-40`, `X=40..60` over the specified Z interval. Fusing
  that plate to that post produces one valid OCCT solid with zero separation;
  neither other retained post contacts it. No deleted +X/+Y post is referenced.

**AZ carrier connectivity verdict: PASS.**

**AZ D40 corridor verdict: PASS.**

**AZ station-B/support-B interface verdict: PASS.** It is an explicit,
dimensioned support-housing/carrier rigid interface, not a collision exemption
created after measurement.

**AZ mount attachment verdict: PASS.**

## EL Exact Recheck

| `motor_EL` against current same-body solid | Exact common volume |
| --- | ---: |
| AZ rotating deck | 0.000000000000 |
| -Y fork arm | 0.000000000000 |
| revised +Y fork arm | 0.000000000000 |
| support A | 0.000000000000 |
| support B | 0.000000000000 |
| edge bridge | 0.000000000000 |
| generated EL motor plate | 0.000000000000 |
| AZ shaft | 0.000000000000 |
| AZ hub | 0.000000000000 |
| AZ gear | 0.000000000000 |

**EL motor intersection verdict: PASS.** The former `16542.031 mm^3`
intersection with the superseded +Y arm cannot enter the current inventory.

### EL Support And Bridge

- Revised +Y arm/support-B common volume is `30630.528372500477 mm^3`, matching
  the frozen `30630.528372500 mm^3` declared rigid support interface.
- The -Y arm/support-A overlap is equivalently `30630.528372500477 mm^3`.
- The deck overlaps the -Y and revised +Y arms by `33600.000000000000 mm^3` and
  `26399.999999999996 mm^3`, respectively.
- The deck, both arms, both supports, bridge, and EL plate fuse into one valid
  OCCT solid.
- The unchanged bridge is `X=16..40`, `Y=110..131.995646`, `Z=480..560`. It
  has zero separation and one-solid valid fusion with the revised +Y arm at the
  frozen fork face and with the EL plate at the frozen plate face. Its arm
  attachment spans `Z=480..520`, as specified.

**EL support-B interface verdict: PASS.** The overlap is purposeful support
connectivity and is explicitly frozen before measurement.

**EL bridge verdict: PASS.** The revision does not leave a free bridge or
motor-plate attachment degree of freedom.

## Trusted Transform And Drive Regression

The motor transforms remain exactly the accepted authority:

| Motor | `OUTPUT_FRAME` target | Source-to-candidate orientation |
| --- | --- | --- |
| AZ | `(66,0,220)` | `X->X`, `Y->Y`, `Z->Z` |
| EL | `(66,135,520)` | `X->X`, `Y->-Z`, `Z->Y` |

The physical-realizability result was obtained by deleting/trimming generated
structure, not by moving or rotating either trusted motor.

Both drive stacks remain 30T/36T, module 2.0 mm, PA20, 12 mm face width,
66 mm center distance, and 1.20 ratio. AZ gear faces remain Z=220..232 and EL
gear faces remain Y=135..147. Both retain 12 mm engagement within the accepted
13 mm usable maximum. `PLATE_PINION_EXACT_CAD_STACK` remains valid: each plate
ends 0.004354 mm before its pinion face.

**Motor-transform regression verdict: PASS.**

**Drive-stack regression verdict: PASS.**

## Cross-Body Regression

The frozen carrier/pad topology is unchanged. The relationships affected by the
asymmetric +Y fork were independently rechecked:

| Current relationship | Exact common volume |
| --- | ---: |
| revised +Y fork arm / carrier rail | 0.000000000000 |
| revised +Y fork arm / two-right pad | 0.000000000000 |
| revised +Y fork arm / three-right pad | 0.000000000000 |
| trusted EL motor / two-right pad | 0.000000000000 |
| EL pinion / three-right pad | 0.000000000000 |

The previous 5 mm support-pad, 5 mm rail-fork, at-least-5.877 mm motor-pad, and
5 mm pinion-pad relationships remain frozen and are not altered by the revised
arm extent.

**Cross-body regression verdict: PASS.**

## SAME_BODY_SOLID_INTERFERENCE_CHECK

The revised Spec and Plan make S4's static same-body check acceptance-critical
and independent of M10. For each `base_body`, `az_rotating_body`, and
`el_payload_body`, the required universe is the complete unordered set of
distinct actual physical-solid constituents derived from body membership. It is
not a hand-curated list of known collisions.

The frozen inventory is sufficiently distinguishable for this purpose:

- `base_body` separately exposes the base, three retained posts, station A,
  station-B rail, supports, AZ plate, motor, pinion, and other actual solids.
- `az_rotating_body` separately exposes deck, AZ shaft/hub/gear, both fork
  arms, supports, bridge, EL plate, motor, pinion, and later brackets.
- `el_payload_body` separately exposes the EL shaft/hub/gear, carrier boss, and
  rail-and-pad carrier physical solids. Declared-bounded antenna envelopes and
  the routing keep-out are not manufactured physical-solid constituents.
- Deleted post, full station-B plate, and superseded wider +Y arm have no
  current inventory entry.

**Same-body inventory verdict: PASS.**

**Derived-pair-universe verdict: PASS.**

The S4 oracle must supply a literal, independently maintained
`DECLARED_RIGID_INTERFACE` ID set and verify it is an exact subset of the
derived current inventory. It may not derive exclusions from the construction
helper, a common-volume result, or a historical collision list. Every remaining
pair is `NON_INTERFACE_SAME_BODY_PAIR` and must receive the direct exact OCCT
check `common().Volume == 0`.

Existing M10/CAD analysis uses a `1e-9 mm^3` classification tolerance and a
`1e-7 mm` distance tolerance. Those runtime analysis tolerances do not override
the new S4 plan requirement, which expressly demands a direct zero-volume
static invariant. No unstated tolerance is needed or introduced here.

**Declared-interface oracle verdict: PASS.**

**Non-interface zero rule verdict: PASS.**

Declared interfaces are truthful when frozen before measurement and supported
by the current geometry: station-B rail/support B; revised +Y arm/support B;
support housings/station members; motor mounting face/plate; shaft/hub;
gear/hub; carrier boss/carrier; carrier boss bore/EL shaft; motor shaft/pinion;
and the other explicitly frozen structural attachments. The plan forbids
retrospective reclassification of an observed collision.

**Declared-interface truthfulness verdict: PASS.**

The required trusted-motor sub-gate derives each motor's comparison set from
same-body inventory and excludes only its declared mounting interface. It
explicitly requires the AZ and EL member sets measured above plus later
generated brackets. It would have captured the deleted AZ post, old station-B
plate, and old EL arm without naming them as a special collision list.

**Trusted-motor sub-gate verdict: PASS.**

The S4 topology oracle requires one AZ carrier solid, zero D40 interference,
both AZ supports connected through their station members, AZ plate connection
through the retained +X/-Y post, both EL arms connected to rotating structure,
EL support-B connection to the revised +Y arm, and bridge connection from that
arm to the EL plate. These are explicitly topology-only requirements and make
no M11 or strength claim.

**Topology invariant verdict: PASS.**

## Determinacy, Prior Findings, And Production Gap

The no-free-placement-DOF table continues to require `ALL=YES`. The retained
posts, station-B rail, AZ plate attachment, revised +Y arm, and EL bridge all
have frozen X/Y/Z, parent, orientation, and attachment facts in the current
geometry and placement table.

**No-free-DOF verdict: PASS.**

No regression was found for `IMPORTANT-1`, `IMPORTANT-3`, `IMPORTANT-4`,
`IMPORTANT-5`, `MINOR-1` through `MINOR-4`, `REREVIEW-IMP-01`,
`PLATE_PINION_EXACT_CAD_STACK`, pair-policy semantics, keep-out semantics, the
45 M10 configurations, the six mandatory predecessor gates, or S3/S4
ownership. The only design change is the authorized generated structural
revision.

**Prior-finding regression status: PASS.**

The project-level S4 invariant uses existing frozen candidate-CAD capabilities;
The existing candidate realization, trusted imported-component placement,
exact-generated geometry, declared-bounded fidelity, and generated-placement
contracts remain sufficient.

**Production-gap verdict: `PRODUCTION_GAP = NONE`.**

## New Findings

- CRITICAL: none.
- IMPORTANT: none.
- MINOR: none.
- NOTE: This is a planning acceptance. S1-S5 remain unimplemented and must
  realize and execute the frozen S4/S5 checks as specified.

## Acceptance Decision

All FINAL-CRIT-01 closure conditions pass: independently remeasured required
motor/non-interface volumes are zero; the AZ carrier is one connected solid;
the D40 corridor is clear; both support-B overlaps are truthful declared
interfaces; trusted transforms and drive stacks are unchanged; affected
cross-body geometry did not regress; the same-body inventory/pair universe and
independent interface oracle are complete; all remaining pairs require direct
zero-volume measurement; no prior finding regressed; and no production gap,
CRITICAL finding, or IMPORTANT finding remains.

Implementation may start under the existing S1-S5 then STOP boundary.

```text
ROTATOR_V2_EPIC_01_PLAN_INDEPENDENTLY_ACCEPTED
```
