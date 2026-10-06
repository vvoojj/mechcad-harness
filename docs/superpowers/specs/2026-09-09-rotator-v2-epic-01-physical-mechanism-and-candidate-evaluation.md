# Rotator V2 Epic 01: Physical Mechanism and Candidate Evaluation

## Status And Authority

Planning only. This Epic consumes accepted MechCAD M12/M13 capabilities and
does not reimplement M12, M13, M10, or any platform capability.

Project authority is the existing `projects/rotator_v2/` package. Controlling
upstream authorization is `M13_4_INDEPENDENT_FINAL_ACCEPTED` with
`ROTATOR_V2_MAY_RESUME = YES`. Current project markers are
`INPUT_READY = PASS`, `CAD_M10_READY = PASS`, and `M11_READY = FAIL`.

The only active motor geometry is
`components/5840-31ZY/normalized/5840-31ZY_normalized_mm.step`.
`motor_az(1).step` is superseded historical provenance only and is not an Epic
input. `TIMING_BELT = NOT_USED`; AZ and EL are `EXTERNAL_SPUR_REDUCTION`; the
historical EL direct coupling is superseded. S1 changes only stale wording and
preserves its historical traceability and all unrelated engineering meanings.

## Boundary

Epic `ROTATOR_V2_EPIC_01_PHYSICAL_MECHANISM_AND_CANDIDATE_EVALUATION` creates
one source-bound candidate, trusted candidate CAD, and candidate M10-3 Evidence.
It stops before selection, promotion, canonical reconstruction, final EL usable
range, M11, and manufacturing release.

`src/mechcad_harness/**`, accepted predecessor tests/goldens, FreeCAD
timeout/retry semantics, and the normalized STEP are protected. If existing
production APIs cannot express a required candidate fact, CAD realization, or
M10-3 evaluation, stop with `ROTATOR_V2_EPIC_01_BLOCKED_BY_PRODUCTION_GAP` and
exact contract evidence. Fixture-only workarounds are prohibited.

## Candidate 01 Frozen Design Selection

Candidate 01 is one frozen engineering seed. Every value in this section is
`DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION`, never `SOURCE_FACT` or
`SUPPLIER_FACT`, unless its provenance column says otherwise. It is not a
globally fixed Rotator V2 requirement or a catalog-bearing selection.

Candidate 01 does not optimize shaft diameters, support spacing, frame/hub/gear
dimensions, fork spacing, or carrier geometry. It implements these exact values
and evaluates them. M10 failure is reported; it must not cause a silent redesign.
Candidate 02 requires separately authorized design revision.

Candidate 01 traceability is: initial frozen design -> `FINAL-CRIT-01` ->
Candidate 01 physical-realizability revision. This authorized revision changes
only generated structural `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` values;
it does not revise trusted motor geometry/transforms, drive authority, or APIs.

### Common Transmission

For Candidate 01, both axes instantiate exactly this frozen gearset:

| Variable | Frozen value | Provenance and rule |
| --- | --- | --- |
| pinion teeth | 30 | existing project seed; `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` |
| driven teeth | 36 | existing project seed; `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` |
| module | 2.0 mm | existing project seed; `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` |
| pressure angle | 20 deg | existing project seed; `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` |
| face width | 12 mm | existing project seed; `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` |
| center distance | 66 mm | existing project seed; motor/output axes are parallel and offset exactly 66 mm |
| external ratio | 36 / 30 = 1.20 | deterministic derivation from frozen tooth counts |
| pinion adapter bore / actual engagement / maximum usable zone | 8.0 mm D-shaft / 12 mm / 13 mm | 13 mm is accepted motor interface authority; 12 mm is `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION`; no thread/key is claimed |
| pinion / driven gear outside diameter | 64 / 76 mm | deterministic standard spur relation `module * (teeth + 2)`; 76 mm driven gear fits the 70 mm hub blank |

Epic 01 must not search, synthesize, or alter alternative gearsets.

### Geometry Table

Coordinates are candidate-local mm. The AZ output shaft/joint axis and AZ motor
output axis both point +Z; the motor axis location is offset +66 mm in X from
the AZ output axis. The EL output shaft/joint axis and EL motor output axis both
point +Y; the motor axis location is offset +66 mm in X from the EL output axis.
Each spur pair therefore has parallel motor and output axes. AZ is vertical +Z
with base origin at the AZ axis/base plane. EL is +Y in the AZ rotating frame at
`Z = 520 mm`. Support locations are support-center coordinates along their
respective shaft axes.

| Family / variable | Frozen value | Basis and adjacent-interface relationship | Required constraint |
| --- | --- | --- | --- |
| AZ shaft main OD / clear bore / length | 60 / 40 / 220 mm | engineering first-candidate selection; 40 mm bore is `30 + 2*5` mm around the preferred keep-out | preserves preferred 30 mm routing diameter and 5 mm radial reservation gap |
| AZ journal OD / journal length | 50 / 20 mm each | engineering first-candidate selection; journals mate concentrically to 50 mm generated support bores | two support stations, not a catalog bearing |
| AZ shaft axial extent | Z=30..250 mm | deterministic from frozen 220 mm length | below body height limit |
| AZ support A / B center | Z=60 / Z=180 mm | engineering first-candidate selection | spacing exactly 120 mm; two stations |
| AZ support bore / housing OD / radial width / axial length | 50 / 80 / 15 / 20 mm | engineering first-candidate selection; housing OD is bore plus twice radial width | generated `MOUNT_OR_SUPPORT`, no purchased bearing claim |
| AZ driven hub OD / axial length / bore | 70 / 30 / 60 mm | engineering first-candidate selection; hub bore mates shaft main OD; 70 mm blank fits inside 76 mm gear OD | hub center Z=220, Z=205..235; clear of support B ending Z=190 |
| AZ pinion / driven gear face placement | both center Z=226; face Z=220..232 mm | source-frame-derived from shoulder Z=220 and 12 mm engagement | 12 mm overlap; fully inside AZ hub; 1 mm remaining accepted coupling-zone margin |
| AZ hub-to-shaft interface | concentric 60 mm nominal bore, 30 mm axial engagement | frozen generated interface selection; no tolerance or commercial coupling claim | explicit intended-contact dimensional test |
| AZ base plate | 350 x 350 x 20 mm | project maximum selected exactly | footprint <=350 x 350 mm |
| AZ stationary support carrier | outer envelope 120 x 120 x 200 mm, Z=20..220; three retained 20 x 20 mm posts: X/Y=-60..-40/-60..-40, -60..-40/40..60, and 40..60/-60..-40, each Z=20..220; station-A plate X/Y=-60..60, Z=50..70, minus D50; station-B left support rail X=-60..-35, Y=-60..60, Z=170..190 | `FINAL-CRIT-01` generated-structure revision; deleted `(50,+50)` post and full station-B plate; the rail deliberately leaves the D50 local support opening and D40 corridor clear; one fused carrier solid | station A overlaps every retained post; station-B rail overlaps both -X posts and support B; rail/support-B rigid overlap=2616.094617 mm^3; no trusted AZ motor intersection with a retained carrier member |
| AZ rotating deck | 220 x 220 x 12 mm, Z=250..262 mm | engineering first-candidate selection; attaches to shaft above hub | supports EL fork root |
| AZ motor-mount plate | 100 x 80 x 3 mm, X=16..116, Y=-40..40, Z=216.995646..219.995646; central D20 through-opening; four D4.5 holes at transformed accepted M4 centers | D20 is `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` derived from accepted approximately D18.8 boss; D4.5 is the same classification; plate attaches only to retained +X/-Y post face Y=-40, X=40..60, Z=216.995646..219.995646 | motor output direction +Z; motor axis location X=66, Y=0, Z=220; no thread, fastener, tolerance, or released-fit claim |
| AZ structural plate thickness | 12 mm | engineering first-candidate selection | no M11/material claim |
| EL shaft OD / length | 50 / 300 mm | engineering first-candidate selection | Y=-150..150 mm; dedicated output shaft |
| EL journal OD / journal length | 50 / 20 mm each | engineering first-candidate selection; journals mate concentrically to 50 mm support bores | two support stations, no catalog bearing |
| EL support A / B center | Y=-100 / Y=100 mm | engineering first-candidate selection | spacing exactly 200 mm; two stations |
| EL support bore / housing OD / radial width / axial length | 50 / 80 / 15 / 20 mm | engineering first-candidate selection | generated `MOUNT_OR_SUPPORT`, no purchased bearing claim |
| EL driven hub OD / axial length / bore | 70 / 30 / 50 mm | engineering first-candidate selection; hub center Y=135, Y=120..150, and bore mates shaft | clear of support B ending Y=110 |
| EL pinion / driven gear face placement | both center Y=141; face Y=135..147 mm | source-frame-derived from shoulder Y=135 and 12 mm engagement | 12 mm overlap; fully inside EL hub; 1 mm remaining accepted coupling-zone margin |
| EL hub-to-shaft interface | concentric 50 mm nominal bore, 30 mm axial engagement | frozen generated interface selection | explicit intended-contact dimensional test |
| EL fork arms | -Y arm X=-70..70, Y=-110..-90, Z=220..520; revised +Y arm X=-70..40, Y=90..110, Z=220..520 | `FINAL-CRIT-01` generated-structure revision; both remain 20 mm thick and align support centers Y=-100/+100 | +Y arm/support-B rigid overlap=30630.528373 mm^3; body <=650 mm |
| EL axis height | 520 mm | existing project initial candidate within accepted [500,600] mm range | frozen Candidate 01 selection |
| EL motor-mount plate | 100 x 80 x 3 mm, X=16..116, Y=131.995646..134.995646, Z=480..560; central D20 through-opening; four D4.5 holes at transformed accepted M4 centers | D20 and D4.5 are `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` as stated for AZ plate; edge bridge attachment is X=16..40 at fork face Y=110, Z=480..520 and plate face Y=131.995646, Z=480..560 | motor output direction +Y; motor axis location is +66 mm in X from EL shaft axis at Y=135, Z=520; no thread, fastener, tolerance, or released-fit claim |
| EL structural plate thickness | 20 mm | engineering first-candidate selection | no M11/material claim |
| antenna carrier rail-and-pad topology | left rail X=-60..-50, Y=-180..180, Z=525..530; pads: (-180..-120, X=-60..60), (-85..-65, X=-60..60), (-30..30, X=-60..60), (65..85, X=-60..40), (120..180, X=-60..29), all with Z=510..530 | generated `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION`; not a solid rectangular plate | rail-and-pad envelope X=-60..60, Y=-180..180, Z=510..530; preserves stated support/fork clearance geometry |
| carrier attachment boss | axis +Y; center X/Y/Z=0/0/520; OD/bore/length=70/50/30 mm; Y=-15..15 | generated `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION`; fused to carrier structure, its D50 bore mates separately declared EL shaft | complete generated carrier assembly envelope X=-60..60, Y=-180..180, Z=485..555; inside Z<=650 body limit |
| carrier payload reference datums | Y=-100,+100 mm | frozen payload/reference datums only | not structural attachments to fork or supports |
| three-antenna nominal positions | (0,-150,0), (0,0,0), (0,150,0) mm | existing project seed in payload frame | declared bounded payload representation |
| two-antenna nominal positions | (0,-75,0), (0,75,0) mm | existing project seed in payload frame | declared bounded payload representation |
| carrier fore/aft adjustment | X=-100..+100 mm per antenna mount | existing project preferred adjustment selected as frozen Candidate 01 travel | no measured CoG claim |

The historical 6007 / 35 mm seed is not selected for Candidate 01 because the
preferred 30 mm routing reservation plus 5 mm radial enforcement requires a
40 mm clear bore. Candidate 01's 50 mm support interface is a generated
first-candidate selection, not a bearing choice.

### Planning Interval And Relationship Check

This deterministic arithmetic check is not an M10 clearance proof and makes no
clearance acceptance claim.

| Check | Frozen intervals / relationship | Result |
| --- | --- | --- |
| AZ shaft, supports, and hub | shaft Z=30..250; supports Z=50..70 and 170..190; hub Z=205..235 | two support stations; support B/hub gap=15 mm; hub/shaft engagement=30 mm |
| EL shaft, supports, and hub | shaft Y=-150..150; supports Y=-110..-90 and 90..110; hub Y=120..150 | two support stations; support B/hub gap=10 mm; hub/shaft engagement=30 mm |
| Gear geometry | pitch diameters 60/72 mm; outside diameters 64/76 mm; center distance=(60+72)/2=66 mm | compatible frozen spur geometry |
| AZ motor stack | shoulder Z=220; usable zone Z=220..233; plate Z=216.995646..219.995646; pinion/driven faces Z=220..232; AZ hub Z=205..235 | 12 mm engagement/overlap; 0.004354 mm exact-CAD plate/pinion separation; no manufacturing claim |
| EL motor stack | shoulder Y=135; usable zone Y=135..148; plate Y=131.995646..134.995646; pinion/driven faces Y=135..147; EL hub Y=120..150 | 12 mm engagement/overlap; 0.004354 mm exact-CAD plate/pinion separation; no manufacturing claim |
| Carrier, fork, and payload | rail-and-pad envelope Z=510..530; complete assembly including boss Z=485..555; fork arms Y centers=-100/+100 and Z=220..520 | pads have 5 mm support/fork axial separation; rail begins 5 mm above fork; complete carrier is within Z<=650 |
| Carrier cross-body clearance geometry | support-pad axial gaps=5 mm; rail-to-support radial clearance=`sqrt(50^2+5^2)-40=10.249` mm; right pad ends X=40 at Y=65..85 and X=29 at Y=120..180 | 5.877 mm clearance to transformed trusted EL motor X minimum at the two-antenna-right pad; 5 mm clearance to 64 mm OD EL pinion at the three-antenna-right pad |
| Routing corridor | keep-out D30, Z=30..130; carrier minimum opening D40, enlarged D50 at support plates; AZ shaft bore D40 | 5 mm radial reservation around D30 is retained where carrier geometry is relevant |
| Envelopes | base=350 x 350 x 20 mm; stated body bound=500 x 500 x 650 mm; EL axis Z=520 mm | frozen values remain within stated bounds |

### FINAL-CRIT-01 Physical-Realizability Closure Record

Exact OCCT planning booleans using the accepted normalized motor STEP and the
unchanged trusted motor transforms found the initial frozen collisions: AZ motor
with deleted `(50,+50)` post `3992.706 mm^3`, AZ motor with full station-B plate
`780.268 mm^3`, and EL motor with the superseded +Y fork arm `16542.031 mm^3`.
The authorized generated-structure revision above eliminates these known
intersections without changing trusted motor geometry, trusted motor transforms,
drive architecture, or production APIs. Independent rereview, not this plan,
formally closes `FINAL-CRIT-01`.

| Motor / revised same-body structure | Exact OCCT common volume mm^3 |
| --- | ---: |
| AZ / base plate, each retained post, station-A plate, station-B left rail, supports A/B, motor plate | 0.000000 each |
| EL / rotating deck, -Y arm, revised +Y arm, supports A/B, edge bridge, motor plate | 0.000000 each |
| revised carrier / protected D40 corridor | 0.000000 |

The revised AZ carrier fuses into exactly one connected generated solid. These
are exact-CAD topology/interference results only, not strength, tolerance,
manufacturing, M11, or Epic-acceptance claims.

## Candidate 01 Frames And Placement Authority

At home, `BASE_FRAME` and `AZ_AXIS_FRAME` have origin `(0,0,0)` mm and
candidate axes `+X,+Y,+Z`; the AZ axis is +Z. `AZ_ROTATING_FRAME` at AZ=0 is
coincident and identically oriented with `BASE_FRAME`. `EL_AXIS_FRAME` has
origin `(0,0,520)` mm in `AZ_ROTATING_FRAME` and axis +Y.
`EL_ROTATING_FRAME` at EL=0 is coincident with that home EL frame.
`PAYLOAD_FRAME` is parented by `EL_ROTATING_FRAME`, has origin `(0,0,0)` at the
EL axis/carrier datum, home world origin `(0,0,520)`, and axes +X boresight, +Y
antenna spacing/EL axis, and +Z upward at home.

The accepted normalized motor `OUTPUT_FRAME`, never a STEP model origin, is the
trusted motor placement datum. The accepted `MOUNT_FRAME` is transformed by the
same rigid transform. It is 3.004354 mm in negative source +Z from the source
`OUTPUT_FRAME`; source +Z is its confirmed outward output direction. The 3 mm
plate occupies the non-motor side of that plane. Its D20 opening clears the
accepted approximately D18.8 boss and shaft; four D4.5 holes use transformed
accepted normalized-STEP M4 centers. These generated selections claim no
fastener, thread depth, tolerance, or released fit.

The accepted gear generator exposes no phase/roll input. Every gear uses its
canonical generator-native orientation with local +X mapped to candidate +X and
no additional axial roll; no Candidate 01 free gear-roll input exists.

### Candidate 01 Placement And Attachment Derivation Table

Every CAD-significant constituent has exactly one frozen transform or one
deterministic derivation. `GPD` means the required one
`GeneratedPlacementDerivation` for an exact-generated mapping.

| Constituent | Parent/body frame | Source/local -> target | Translation / axis / roll | Attachment and derivation | Authority |
| --- | --- | --- | --- | --- | --- |
| `motor_AZ` | `base_body` / `BASE_FRAME` | accepted `OUTPUT_FRAME` -> AZ target | origin (66,0,220); source X/Y/Z -> candidate X/Y/Z | trusted exact frame alignment | accepted motor interface |
| AZ motor plate | `base_body` / AZ `MOUNT_FRAME` | source mount plane -> Z=216.995646 | X/Y/Z -> X/Y/Z; Z=216.995646..219.995646 | retained +X/-Y post contact at Y=-40, X=40..60, Z=216.995646..219.995646; GPD | accepted frame plus revised first selection |
| AZ pinion | `base_body` / motor axis | shoulder -> bore Z=220..232 | axis +Z, center (66,0,226), canonical +X roll | 12 mm D-shaft engagement; GPD | accepted zone plus first selection |
| AZ driven gear | `az_rotating_body` / shaft axis | hub -> face Z=220..232 | axis +Z, center (0,0,226), canonical +X roll | concentric hub interface; GPD | first selection |
| AZ hub / shaft | `az_rotating_body` / `AZ_AXIS_FRAME` | axis -> hub / shaft | hub center (0,0,220); shaft Z=30..250; axis +Z | concentric rigid interface / articulated shaft; GPD | first selection |
| AZ supports A/B | `base_body` / `AZ_AXIS_FRAME` | bore -> shaft axis | centers Z=60/180, axis +Z, canonical roll | station-A plate / station-B left rail; B rigid overlap=2616.094617 mm^3; GPD | revised first selection |
| AZ base plate | `base_body` / `BASE_FRAME` | plate center -> base origin | center (0,0,10), X/Y=-175..175, Z=0..20, axes X/Y/Z | stationary base reference; GPD | first selection |
| AZ carrier / deck | `base_body` / `BASE_FRAME`; `az_rotating_body` / shaft | local datum -> frozen Z interval | three-post carrier Z=20..220 with station-B left rail X=-60..-35; deck Z=250..262; axes X/Y/Z | one fused carrier solid / deck lower face Z=250 contacts AZ shaft upper annular end face; GPD | revised first selection |
| EL fork / supports A/B | `az_rotating_body` / `EL_AXIS_FRAME` | local datum -> EL axis | -Y arm X=-70..70, Y=-110..-90; +Y arm X=-70..40, Y=90..110; both Z=220..520; local X->X, Y->-Z, Z->Y | fork/deck fused intersection Z=250..262 / +Y arm-support-B rigid overlap=30630.528373 mm^3; GPD | revised first selection |
| `motor_EL` | `az_rotating_body` / `EL_AXIS_FRAME` | accepted `OUTPUT_FRAME` -> EL target | origin (66,135,520); source X->X, Y->-Z, Z->Y | trusted exact frame alignment; no free roll | accepted motor interface |
| EL motor plate | `az_rotating_body` / EL `MOUNT_FRAME` | source mount plane -> Y=131.995646 | source X->X, Y->-Z, Z->Y; Y=131.995646..134.995646 | edge-rail plate contact; GPD | accepted frame plus first selection |
| EL edge bridge rail | `az_rotating_body` / `EL_AXIS_FRAME` | revised +Y fork face -> plate plane | X=16..40, Y=110..131.995646, Z=480..560 | revised +Y fork contact Y=110, X=16..40, Z=480..520; plate contact Y=131.995646; GPD | revised first selection |
| EL pinion / driven gear | motor axis / EL shaft axis | shoulder / hub -> faces Y=135..147 | centers (66,141,520)/(0,141,520); axis +Y; source X->X, Y->-Z, Z->Y | 12 mm engagement / concentric hub; GPD | accepted zone plus first selection |
| EL hub / shaft | `el_payload_body` / `EL_AXIS_FRAME` | axis -> hub / shaft | hub center (0,135,520); shaft Y=-150..150; axis +Y; local X->X, Y->-Z, Z->Y | concentric rigid interface / articulated shaft; GPD | first selection |
| carrier boss | `el_payload_body` / `PAYLOAD_FRAME` | boss axis -> payload axis | local center (0,0,0), home world center (0,0,520), axis +Y, local Y=-15..15 | fused to carrier; D50 bore mates separate EL shaft; GPD | first selection |
| antenna carrier | `el_payload_body` / `PAYLOAD_FRAME` | carrier datum -> payload origin | rail-and-pad geometry as frozen; axes X/Y/Z, no roll | fused to carrier boss; GPD | first selection |
| antenna envelopes | `el_payload_body` / `PAYLOAD_FRAME` | centers -> payload datum | three: (0,-150,0)/(0,0,0)/(0,150,0); two: (0,-75,0)/(0,75,0); axes X/Y/Z | declared bounded, nominal X=Z=0; not trusted STEP | project seed plus first selection |
| AZ keep-out | `base_body` / `BASE_FRAME` | cylinder axis -> AZ axis | D30, Z=30..130, axis +Z, canonical roll | declared reserved empty space | declared-bounded authority |

The carrier boss is fused to the carrier structure, not into the separately
declared EL shaft. The old `Y=-100,+100` carrier values are payload/reference
datums only and never carrier-to-fork/support attachments.

### No-Free-Placement-DOF Audit

| Constituents | X/Y/Z fixed | Axis fixed | Roll fixed | Parent fixed | Attachment fixed | Result |
| --- | --- | --- | --- | --- | --- | --- |
| motors and motor plates | YES | YES | YES | YES | YES | ALL=YES |
| AZ/EL shafts, hubs, gears, and supports | YES | YES | YES | YES | YES | ALL=YES |
| revised AZ carrier/deck, revised EL fork, and EL bridge rail | YES | YES | YES | YES | YES | ALL=YES |
| carrier, boss, and antenna envelopes | YES | YES | YES | YES | YES | ALL=YES |
| AZ keep-out | YES | YES | YES | YES | YES | ALL=YES |

## Physical Bodies, Roles, And Joints

`base_body` contains the base, revised three-post AZ carrier with station-A
plate/station-B left rail, AZ motor/mount/pinion, AZ supports A/B, and the AZ
routing keep-out. `az_rotating_body` contains AZ shaft/hub/gear/deck, revised
EL fork, EL motor/mount/pinion, EL edge bridge rail, and EL supports A/B.
`el_payload_body` contains the EL shaft/hub/gear, carrier attachment boss,
rail-and-pad carrier, and two or three antenna envelopes.

For the S4 physical-solid inventory, the revised `base_body` carrier exposes
station-A, station-B left rail, and the three retained posts as distinct solid
constituents; the deleted +X/+Y post has no inventory entry. The revised
`az_rotating_body` fork exposes separate -Y and +Y arm constituents. These
inventory IDs are geometry facts for the same-body invariant, not new physical
bodies or M10 pair-policy categories.

Generated support stations use existing `PhysicalComponentRole.MOUNT_OR_SUPPORT`.
It truthfully identifies generated mounting/support geometry without implying a
selected commercial bearing; `BEARING` is prohibited for these constituents.

The AZ routing keep-out is reserved empty space, not manufactured hardware. It
uses `CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION` and
existing `PhysicalComponentRole.PAYLOAD_OR_FRAME_ATTACHMENT`, the closest
available non-actuator/non-transmission/non-bearing role for a body-attached
declared representation. Fidelity, not this role name, states that it is not a
purchased or manufactured part. Its cylinder is exactly diameter 30 mm and
axial Z=30..130 mm: hard clearance >=24 mm, preferred clearance >=30 mm, and
axial reserve >=100 mm. Same-body keep-out pairs are
`SAME_RIGID_GROUP_EXCLUDED` only as required by same-body semantics; every
keep-out pair with AZ rotating or EL payload constituents is `CHECK_CLEARANCE`.
It has no `INTENDED_CONTACT_EXCLUDED` pairs. M10 against it conservatively
enforces empty routing reservation, not collision with manufactured hardware.

`joint_az` is the generated-shaft axis from `base_body` to `az_rotating_body`,
direction +Z, with production motion mode `CONTINUOUS`, no limits, home 0 deg,
and no hard stop.

`joint_el` is the generated-shaft axis from `az_rotating_body` to
`el_payload_body`, direction +Y. It uses existing production motion mode `CONTINUOUS` with
no production angle limits solely because that is the accepted representation
of a joint with no authoritative mechanical limits. This does not assert that
EL is a project continuous-multi-turn mechanism: project authority remains
`continuous_multi_turn = FALSE`. `0..360 deg` is only the
`REQUESTED_EVALUATION_INTERVAL`; it is not `BOUNDED(0,360)`, a hard stop, or an
accepted usable range.

## Pair Policy And Interface Consistency

Every unordered constituent pair is classified exactly once by rigid-body
semantics. Every same-body pair is `SAME_RIGID_GROUP_EXCLUDED`; unrelated
cross-body pairs are `CHECK_CLEARANCE` at 5 mm. Only these genuine cross-body
physical mating interfaces may be `INTENDED_CONTACT_EXCLUDED`, each with
explicit interface authority and a nonblank reason: AZ shaft journal/AZ support
A, AZ shaft journal/AZ support B, AZ pinion/AZ driven gear mesh, EL shaft
journal/EL support A, EL shaft journal/EL support B, and EL pinion/EL driven
gear mesh.

The same-body rigid interfaces shaft/hub, carrier-boss/shaft, motor
shaft/pinion, driven gear/hub, and motor/motor mount remain
`SAME_RIGID_GROUP_EXCLUDED`; physical mating does not change their pair
classification. Pair classification and dimensional interface compatibility are
separate obligations. S4 independently validates
the exact frozen dimensions for the cross-body shaft/support and gear-mesh
interfaces and the same-body shaft/hub, carrier-boss/shaft, motor
shaft/pinion, driven gear/hub, and motor/mount interfaces. Checks include
journal OD <= support bore, shaft/hub and carrier-boss/shaft nominal bore
equality, 8 mm D-shaft compatibility, selected 12 mm engagement within the
accepted 13 mm maximum, driven gear/hub compatibility, common module and pressure angle, pitch diameters
60/72 mm, 66 mm center distance, and the accepted 28 x 40 mm M4 motor mounting
interface. These are interface checks, not M10 clearance measurements.

The AZ routing keep-out's cross-body pairs with every constituent of
`az_rotating_body` and `el_payload_body` are `CHECK_CLEARANCE` at the accepted
5 mm requirement. Its `base_body` pairs remain `SAME_RIGID_GROUP_EXCLUDED`.
M10 therefore proves the required relationship between the declared keep-out
representation and other rigid bodies only; it cannot prove the stationary
corridor against same-body solids. Separate deterministic static-geometry
invariant tests must use actual frozen candidate geometry and dimensions to
verify that each geometrically relevant manufactured/generated `base_body`
solid stays outside the reserved corridor: base/frame geometry, AZ stationary
support carrier, AZ supports A/B, AZ motor mount, AZ motor, and AZ pinion. No
manufactured-solid claim is made for the keep-out itself.

### SAME_BODY_SOLID_INTERFERENCE_CHECK

S4 must run the normative `SAME_BODY_SOLID_INTERFERENCE_CHECK`, independently
of M10. For each `base_body`, `az_rotating_body`, and `el_payload_body`, it
derives the complete unordered pair universe of distinct physical solid
constituents from actual body membership. Every pair is classified exactly once
as either `DECLARED_RIGID_INTERFACE` or `NON_INTERFACE_SAME_BODY_PAIR`.

`DECLARED_RIGID_INTERFACE` is permitted only when this Spec explicitly defines
the intentional physical mating/overlap and its dimensional compatibility. It
includes shaft/hub, gear/hub, carrier-boss/carrier, carrier-boss-bore/EL-shaft,
support housing/carrier station member, revised +Y fork arm/support B, motor
mounting face/plate, AZ station-B left rail/support B, and other explicitly
frozen rigid assembly interfaces. A nonzero common volume is permitted only for
such a declared geometrically consistent interface; no collision may be
retrospectively relabeled an interface.

Every `NON_INTERFACE_SAME_BODY_PAIR` requires exact OCCT `common().Volume == 0`
under the repository/kernel acceptance rule. The test subtracts only declared
rigid-interface pairs from the derived universe, never a hand-picked collision
list. Consequently every newly added same-body solid enters the check.

As a mandatory derived sub-gate, each trusted motor is measured against every
other physical solid in its own body except its explicitly declared mounting
interface; every non-interface result must have zero common volume before S4 is
complete. This preserves production M10 `SAME_RIGID_GROUP_EXCLUDED` semantics.

For Candidate 01, the derived motor inventory must include at least
`motor_AZ` against the base plate, every retained AZ carrier post, station-A,
station-B left rail, supports A/B, and all motor-mount material outside the
declared mounting interface; and `motor_EL` against both fork arms, supports
A/B, edge bridge, EL motor-mount material outside the declared interface, AZ
deck, AZ shaft/hub/gear, and every later generated az-rotating bracket. These
are required by inventory derivation, not a hand-maintained historical-collision
list.

The test oracle independently supplies the literal declared-rigid-interface ID
set and verifies it is an exact subset of the realized same-body inventory. It
must not reuse the geometry-construction helper or derive exemptions from the
actual common-volume outcomes. All remaining derived pairs are non-interface
pairs and must be measured.

S4 also asserts topology only: the revised AZ carrier is one connected solid;
AZ supports A/B connect through station-A/station-B members; the AZ plate
connects through retained +X/-Y post; both EL arms connect to rotating
structure; support B connects to revised +Y arm; and the edge bridge connects
the revised +Y arm to the EL plate. These assertions make no strength, load,
or M11 claim.

## M10-3 Configuration Obligation

The exact M10-3 set is the full Cartesian product, AZ-major then EL-minor:

```text
AZ = [0, 90, 180, 270, 360]
EL = [0, 45, 90, 135, 180, 225, 270, 315, 360]
configurations = tuple((az, el) for az in AZ for el in EL)
count = 45
```

IDs are `cfg_000` through `cfg_044`: `cfg_000=(0,0)`, `cfg_008=(0,360)`,
`cfg_009=(90,0)`, `cfg_017=(90,360)`, `cfg_018=(180,0)`,
`cfg_026=(180,360)`, `cfg_027=(270,0)`, `cfg_035=(270,360)`,
`cfg_036=(360,0)`, and `cfg_044=(360,360)`. Implementation may generate this
sequence mechanically only if the result equals this rule exactly.

AZ `-1080, -720, -360, +360, +720, +1080 deg` checks are FK/geometric-periodicity
equivalence checks only. They are not M10 configurations, do not increase the
45 count, do not create pair measurements, and make no continuous-path or
configuration-space claim.

Candidate M10-3 uses `ProductionApplication.realize_candidate_cad()` then
`ProductionApplication.evaluate_candidate_multi_joint_m10()` with real
FreeCAD, trusted motor geometry, exact complete pair scope, and durable
candidate-scoped provenance. It remains discrete-only.

## Stories

- S1 Authority Reconciliation: stale-text reconciliation and frozen authority manifest.
- S2 Candidate Source Authority: source-bound state, normalized motor artifact, and two motor instances.
- S3 Physical Mechanism: semantic bodies, joints, members, support semantics,
  interfaces, frozen frame/placement/attachment specifications, and pair policy.
  S3 owns generated-part specifications only and must not invoke CAD lowering.
- S4 Candidate CAD: CAD mappings, representation generation, trusted motor
  transforms, `GeneratedPlacementDerivation` records, dimensional interface and
  placement tests, and candidate CAD realization.
- S5 Candidate M10-3: exact bridge, 45 configurations, real candidate M10-3, and Evidence.

After S5: **STOP IMPLEMENTATION.** Independent Epic acceptance is a separate
session.
