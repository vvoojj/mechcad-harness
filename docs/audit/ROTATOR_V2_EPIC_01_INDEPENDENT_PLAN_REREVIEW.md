# Rotator V2 Epic 01 Independent Plan Rereview

## Verdict

```text
ROTATOR_V2_EPIC_01_PLAN_REVISE
```

All five original IMPORTANT findings and all four original MINOR findings have
been corrected. However, the revised frozen table still does not determine all
CAD-significant placements and interfaces required to realize Candidate 01. One
new IMPORTANT determinacy finding remains. No CRITICAL finding and no production
gap were identified.

## Independence

This was a read-only plan audit. No production source, project authority, Epic
Spec, execution plan, test, golden, CAD artifact, candidate runtime artifact,
or evidence was modified. The only repository write is this independent
rereview report.

## Documents Reviewed

- `docs/superpowers/specs/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/superpowers/plans/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/audit/ROTATOR_V2_EPIC_01_INDEPENDENT_PLAN_REVIEW.md`
- `docs/audit/MECHCAD_M13_4_INDEPENDENT_FINAL_ACCEPTANCE.md`
- Rotator V2 motor and launch authority, including
  `projects/rotator_v2/components/5840-31ZY/5840-31ZY_AUTHORITY.yaml` and
  `ROTATOR_V2_LAUNCH_PACKAGE.md`
- Current production contracts in `src/mechcad_harness/**`

The revised documents consistently identify
`ROTATOR_V2_EPIC_01_PHYSICAL_MECHANISM_AND_CANDIDATE_EVALUATION`, preserve
`src/mechcad_harness/**` as protected, and consume rather than reimplement
accepted M12/M13 capabilities. The upstream authorization remains
`M13_4_INDEPENDENT_FINAL_ACCEPTED`,
`M13_4_ACCEPTANCE_STATUS = ACCEPTED`, and
`ROTATOR_V2_MAY_RESUME = YES`.

## Original Finding Adjudication

| Previous finding | Status | Independent basis |
| --- | --- | --- |
| IMPORTANT-1, transmission determinacy | CLOSED | Spec lines 47-61 and Plan lines 16, 29 freeze both axes to 30T/36T, m2.0, PA20, 12 mm face width, 66 mm center distance, and 1.20 ratio; they retain `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` status and prohibit alternatives. |
| IMPORTANT-2, generated-part determinacy | REPLACED_BY_NEW_FINDING | The previously missing size/interval values are now frozen, but the new `REREVIEW-IMP-01` placement and attachment determinacy gap remains. |
| IMPORTANT-3, keep-out semantics | CLOSED | Spec lines 134-145 and Plan lines 19, 41, 84 specify reserved empty space, declared-bounded fidelity, `PAYLOAD_OR_FRAME_ATTACHMENT`, D30, Z=30..130, cross-body checking, same-body exclusion, and no keep-out intended contact. |
| IMPORTANT-4, M10 configuration determinacy | CLOSED | Spec lines 197-215 and Plan lines 100-115 define the ordered 45-item AZ-major/EL-minor Cartesian product and require a literal independent test oracle. |
| IMPORTANT-5, regression gates | CLOSED | Plan lines 117-135 freezes exactly the six required protected predecessor suites. |
| MINOR-1, S3/S4 ownership | CLOSED | Spec lines 226-231 and Plan lines 80-93 give S3 generated-part specifications only and assign CAD lowering to S4. |
| MINOR-2, EL angle-limit semantics | CLOSED | Spec lines 151-158 and Plan line 81 require production `CONTINUOUS` with no limits and reject `BOUNDED(0,360)`. |
| MINOR-3, excluded-interface validation | CLOSED | Spec lines 171-181 and Plan line 92 require independent dimensional checks for both cross-body intended contacts and same-body rigid interfaces. |
| MINOR-4, support-station role | CLOSED | Spec lines 130-132 and Plan lines 31, 36 require `MOUNT_OR_SUPPORT` and prohibit `BEARING` for generated stations. |

## Candidate 01 Determinacy

The revised table successfully freezes the requested scalar geometry:

- AZ: shaft OD/bore/length and interval; journals; support bore, housing, and
  centers; support spacing; hub; carrier topology; deck; motor mount; plate
  thickness.
- EL: shaft OD/length and interval; journals; support bore, housing, and
  centers; support spacing; hub; fork; axis height; motor mount; plate
  thickness.
- Payload: carrier envelope, nominal two- and three-antenna positions, and
  fore/aft travel.
- Both drives: the exact frozen spur gearset.

Those values are consistently classified as `DESIGN_VARIABLE /
FIRST_CANDIDATE_SELECTION`, not supplier or source facts. The 6007/35 mm
historical seed is correctly not promoted to a selected bearing.

This is not enough to make the full CAD candidate deterministic. See
`REREVIEW-IMP-01` under New Findings.

## EL Geometry

The requested EL shaft/support/hub arithmetic is internally consistent:

```text
shaft:       Y=-150..+150, length 300
support A:   Y=-110..-90
support B:   Y= +90..+110
hub:         center Y=+135, length 30, extent Y=+120..+150
```

- The entire hub interval lies on the shaft.
- Shaft/hub engagement is exactly 30 mm.
- Support B ends at Y=110, leaving a 10 mm hub gap.
- No support/hub axial overlap exists.

This passes the requested EL shaft/hub consistency check. It does not resolve
the separately missing carrier placement and carrier-to-hub attachment
definition.

## AZ Geometry

The requested AZ shaft/support/hub arithmetic is internally consistent:

```text
shaft:       Z=30..250, length 220
support A:   Z=50..70
support B:   Z=170..190
hub:         center Z=220, length 30, extent Z=205..235
```

- The hub is entirely on the shaft.
- Shaft/hub engagement is exactly 30 mm.
- The support B to hub axial gap is exactly 15 mm.

This passes the requested AZ interval check.

## Transmission Geometry

The frozen transmission is consistent between Spec and Plan:

```text
module = 2 mm
pinion teeth = 30       pitch diameter = 2 * 30 = 60 mm
driven teeth = 36       pitch diameter = 2 * 36 = 72 mm
pinion OD = 2 * (30 + 2) = 64 mm
center distance = (60 + 72) / 2 = 66 mm
ratio = 36 / 30 = 1.20
```

The 70 mm hub blank being smaller than the 76 mm gear OD is internally normal:
the hub fits concentrically inside the driven gear rather than enclosing its
outside diameter.

## Pair Semantics

The revised pair policy matches the actual production contract.

- Same-body pairs must be `SAME_RIGID_GROUP_EXCLUDED` and cross-body pairs
  cannot use that class
  (`candidates/multi_joint_m10_bridge.py:1732-1737`).
- Every concrete pair is mechanically derived from the complete physical/CAD
  universe and checked against the full unordered combination set
  (`multi_joint_m10_bridge.py:1776-1812`).
- Every excluded pair requires a nonblank reason
  (`models/physical_pair_policy.py:78-82`).

The only declared cross-body intended-contact families are exactly the six
allowed by the Spec: AZ shaft/support A, AZ shaft/support B, AZ gear mesh, EL
shaft/support A, EL shaft/support B, and EL gear mesh. Same-body shaft/hub,
motor-shaft/pinion, gear/hub, and motor/mount pairs remain rigid-group
exclusions and have separate dimensional validation. This passes the pair
semantic rereview.

## Keep-Out Semantics

The routing keep-out is correctly represented as empty reserved space:

```text
fidelity: DECLARED_BOUNDED_COLLISION_REPRESENTATION
role:     PhysicalComponentRole.PAYLOAD_OR_FRAME_ATTACHMENT
geometry: D30 mm, Z=30..130 mm
```

It is not trusted source geometry, exact generated geometry, or manufactured
hardware. Cross-body pairs are `CHECK_CLEARANCE`; same-body pairs use the
production-required rigid-group exclusion; `INTENDED_CONTACT_EXCLUDED` is
prohibited for the keep-out. The Spec correctly limits M10's proof to
cross-body relationships and requires separate static actual-geometry
invariants for relevant stationary base-body solids.

The D40 shaft bore and carrier opening preserve the planning arithmetic
`D30 + 2*5 = D40`; the enlarged D50 station-plate openings are compatible. The
documents correctly label this as planning/static-invariant geometry, not an
M10 clearance-acceptance claim.

## Carrier Topology

The AZ stationary support carrier is sufficiently deterministic for generated
CAD realization:

- outer envelope 120 x 120 x 200 mm at Z=20..220;
- four 20 x 20 mm posts at X/Y=(+/-50,+/-50);
- 120 x 120 x 20 mm station plates at Z=50..70 and Z=170..190;
- D40 continuous central opening and D50 station-plate openings;
- support centers Z=60 and Z=180.

It cannot reasonably be interpreted as one solid 120 x 120 x 200 block. No
structural adequacy, material, or M11 claim is made.

## Axis Semantics

Axis direction and offset semantics are unambiguous and consistent:

- AZ joint/output axis: +Z; AZ motor output axis: +Z; motor axis is +66 mm X.
- EL joint/output axis: +Y; EL motor output axis: +Y; motor axis is +66 mm X.

In each case, +X is the positional center offset for a parallel spur pair, not
the EL motor axis direction. The accepted output and mount frames remain
available for the trusted motor mappings.

## M10 Configuration Scope

The scope is exact and non-circular:

```text
AZ = (0,90,180,270,360)
EL = (0,45,90,135,180,225,270,315,360)
sequence = AZ-major Cartesian product with EL minor
count = 45
IDs = cfg_000 through cfg_044
cfg_000 = (0,0)
cfg_044 = (360,360)
```

The specified unit test has its own literal AZ/EL oracle and cannot source
expected values from JSON, candidate construction, or the helper under test.
The -1080, -720, -360, +360, +720, and +1080 AZ values remain FK periodicity
checks only; they add no M10 configurations or pair measurements.

## Regression Gates

The Plan freezes exactly these mandatory protected suites:

```text
tests/integration/test_m13_4_full_stack_acceptance.py
tests/integration/test_m13_3_candidate_m10_production.py
tests/integration/test_m13_3_generic_multi_joint_acceptance.py
tests/integration/test_m13_2_generated_parts_live.py
tests/integration/test_m12_candidate_cad_m10_production.py
tests/integration/test_m12_6_end_to_end_external_spur.py
```

They are mandatory after the Epic-specific gates; they cannot be replaced by an
implementation agent's discretionary "relevant" subset.

## Production Capability

No production gap exists for the stated S1-S5 route. Directly rechecked:

- `ProductionApplication.realize_candidate_cad()` and
  `ProductionApplication.evaluate_candidate_multi_joint_m10()` exist
  (`application.py:2128-2153`).
- `PhysicalMechanismRealization@2` supports components, three rigid bodies,
  two revolute joints, a kinematic root, and the complete physical pair policy
  (`candidates/models.py:776-976`).
- Generated shaft-owned axis sources are supported
  (`GeneratedRotationalInterfaceAxisSource`, `candidates/models.py:617-647`).
- Trusted, declared-bounded, and exact-generated CAD mappings are supported
  (`candidates/cad_realization.py:844-910`).
- Candidate CAD realization requires a complete mapping and, for every exact
  generated mapping, exactly one placement derivation
  (`cad_realization.py:913-1028`).
- Explicit ordered multi-joint configurations, including 45 configurations,
  are supported and hash-bound (`models/multi_joint_verification.py:30-96`,
  `candidates/multi_joint_m10_evaluation.py:111-145`).
- Complete pair policy and real-FreeCAD candidate M10-3 execution/evidence are
  already supported by the accepted candidate M13 route.

The placement-derivation requirement is a production capability, not a
production gap. It instead exposes the missing authority inputs described in
the new finding.

## Epic Boundary

The boundary remains correct:

```text
S1 -> S2 -> S3 -> S4 -> S5 -> STOP
```

Selection, promotion, canonical reconstruction, canonical M10, final EL
usable-range acceptance, M10-4/global-path claims, M11, and manufacturing
release remain excluded. The real production FreeCAD route is mandatory for S5.

## New Findings

CRITICAL: none.

IMPORTANT:

1. **REREVIEW-IMP-01 — Candidate 01 CAD placement and attachment determinacy
   remains incomplete.** The frozen dimension table does not define a complete
   deterministic transform and physical attachment for every CAD-significant
   constituent. In particular:
   - The antenna carrier has dimensions, a Y span, and `Y=-100,+100`
     attachment datums, but no candidate-local X/Z placement, no specified
     carrier-to-EL-shaft/hub interface, and no frozen attachment geometry or
     placement derivation. The carrier is `el_payload_body`; it must be fixed
     to an EL payload member, not to the `az_rotating_body` fork/supports.
   - The pinion/driven-gear axial centers, face overlap, and actual pinion
     engagement are not fixed. `13.0 mm maximum engagement` is an upper bound,
     not a frozen first-candidate selection.
   - A motor-axis point plus an axis direction does not define the roll of a
     trusted imported motor. Its confirmed 28 x 40 mm M4 pattern is not
     rotationally symmetric, and the Plan does not freeze the local-frame roll,
     the generated mount plate transform, or the mount-to-structure attachment
     derivation.

   Two implementation agents can therefore produce materially different CAD
   assemblies while complying with the listed scalar dimensions. The table's
   planning assertion that the carrier/fork/payload positions are consistent
   cannot be independently verified until those transforms and interfaces are
   specified. This is not remedied by M10: same-body pairs are required to be
   excluded, and M10 evaluates a realized assembly rather than selecting its
   missing placement authority.

   Required revision before implementation: freeze a candidate-local datum and
   complete placement/attachment derivation for the carrier, the gear faces and
   pinion engagement, and each motor/mount roll and attachment. Bind those
   derivations into S3 generated-part specifications and S4 placement tests.
   Retain their `DESIGN_VARIABLE / FIRST_CANDIDATE_SELECTION` status.

MINOR: none.

NOTE: This rereview does not infer motor-body or carrier solid intersections
from uncreated CAD. The absence of the frozen transforms and attachment
definitions is itself the determinacy defect; real FreeCAD is deliberately
reserved for the S5 production evaluation rather than used in this plan audit.

## Acceptance Decision

The original nine findings are corrected, the requested shaft/hub intervals,
pair semantics, static keep-out proof, carrier topology, axes, gear arithmetic,
configuration scope, regression gates, production route, and Epic boundary all
pass rereview. `REREVIEW-IMP-01` leaves Candidate 01 materially under-specified
at the CAD realization boundary. Implementation must not begin until that
IMPORTANT finding is corrected and independently rereviewed.

```text
ROTATOR_V2_EPIC_01_PLAN_REVISE
```
