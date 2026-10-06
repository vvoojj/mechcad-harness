# Rotator V2 Epic 01 Independent Plan Review

## Verdict

```text
ROTATOR_V2_EPIC_01_PLAN_REVISE
```

No CRITICAL findings. Five IMPORTANT findings require plan/spec-text revision
before implementation. All five are determinacy or precision gaps fixable by
plan revisions; none requires production change, authority rework, or story
restructuring. The Epic's architecture, boundary, production route, motor
authority, body/joint model, pair policy, claim boundary, and later holds are
correct and grounded in accepted authority.

## Independence

This was a read-only review session. No production source, Epic Spec, execution
plan, project authority, test, golden, CAD, or evidence was modified. The only
repository write is this report. All contract citations below were inspected
directly in `src/mechcad_harness/**` and `projects/rotator_v2/**` during this
session.

## Authority Reviewed

- `docs/superpowers/specs/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/superpowers/plans/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`
- `docs/audit/MECHCAD_M13_4_INDEPENDENT_FINAL_ACCEPTANCE.md` (controlling
  upstream authorization; `M13_4_ACCEPTANCE_STATUS = ACCEPTED`,
  `ROTATOR_V2_MAY_RESUME = YES`, unchanged 120 s non-retrying FreeCADCmd path)
- `projects/rotator_v2/README.md`, `ROTATOR_V2_LAUNCH_PACKAGE.md`,
  `ROTATOR_V2_READINESS_CLOSURE.md`, `CONFIRMATION_CHECKLIST.md`
- `projects/rotator_v2/mechanism/ROTATOR_V2_PHYSICAL_ARCHITECTURE.md`
- `projects/rotator_v2/requirements/MECHANICAL_CONSTRAINTS.md`
- `projects/rotator_v2/components/5840-31ZY/5840-31ZY_AUTHORITY.yaml`,
  `5840-31ZY_CONFIRMATION.md`, `MOTOR_SCALE_CONFIRMATION.md`, normalized README
- Production contracts: `src/mechcad_harness/application.py`,
  `candidates/models.py`, `candidates/cad_realization.py`,
  `candidates/multi_joint_m10_bridge.py`, `candidates/multi_joint_m10_evaluation.py`,
  `models/physical_pair_policy.py`, `models/generated_placement.py`,
  `models/multi_joint_verification.py`

## Epic Boundary

Correct.

- Hierarchy is Project (`projects/rotator_v2/`) → Epic
  (`ROTATOR_V2_EPIC_01_PHYSICAL_MECHANISM_AND_CANDIDATE_EVALUATION`) →
  Stories S1–S5. No competing Project Spec is created.
- M12/M13 are treated as accepted MechCAD capabilities consumed by the project;
  the plan explicitly forbids `m12_1` naming for Rotator paths and forbids
  M12/M13 platform implementation. M12-1/M13 are not restated as new
  Rotator-specific platform milestones.
- The Epic stops after S5 with an explicit STOP IMPLEMENTATION marker
  (Spec, Stories section; Plan, Test Gate 5 and Independent Review Boundary).
  Excluded: candidate selection, promotion, ChangeSet/ChangeEngine advancement,
  canonical mechanism/CAD/M10, final EL usable-range acceptance, M11,
  manufacturing release. No independent-review Story exists inside
  implementation.

## Production Capability Boundary

`src/mechcad_harness/**` is protected in both documents, and the blocked route
is correctly specified as
`ROTATOR_V2_EPIC_01_BLOCKED_BY_PRODUCTION_GAP` with fixture-only workarounds
prohibited (Spec, Protected Surfaces; Plan, Global Constraints and Stop
Conditions).

The existing production contracts genuinely support the planned S1–S5 route.
Verified directly:

- `ProductionApplication.realize_candidate_cad()` — application.py:2128
- `ProductionApplication.evaluate_candidate_multi_joint_m10()` — application.py:2143
- `PhysicalMechanismRealization@2` with rigid-body, revolute-joint, kinematic-root,
  and pair-classification bindings — candidates/models.py:776-976
- `CandidateCadRealizationRequest@2` with generated placement derivations —
  candidates/cad_realization.py:913-1029
- Fidelity classes `TRUSTED_SOURCE_GEOMETRY`,
  `DECLARED_BOUNDED_COLLISION_REPRESENTATION`, `EXACT_GENERATED_GEOMETRY` —
  candidates/cad_realization.py:844-847
- Pair classifications `CHECK_CLEARANCE`, `INTENDED_CONTACT_EXCLUDED`,
  `SAME_RIGID_GROUP_EXCLUDED` with mandatory explicit exclusion reasons —
  models/physical_pair_policy.py:45-97
- Mechanically derived and enforced complete concrete pair inventory
  (`itertools.combinations` completeness check) —
  candidates/multi_joint_m10_bridge.py:1742-1819
- `GeneratedRotationalInterfaceAxisSource` for joint axes owned by generated
  shafts — candidates/models.py:617-647
- `MultiJointVerificationConfigurationSet` / explicit ordered configuration
  validation against the trusted bridge model —
  models/multi_joint_verification.py:30,
  candidates/multi_joint_m10_evaluation.py:111-145
- Two instances of one supplied component with distinct placements and one
  trusted representation identity is the accepted M12/M13 instantiation pattern
  (`SuppliedRotationalInterfaceAxisSource`, per-instance CAD mappings bound to
  one source geometry identity).

No production gap was identified for S1–S5. No production change is implied.

## Motor Authority

Correct.

- Sole active geometry authority is
  `projects/rotator_v2/components/5840-31ZY/normalized/5840-31ZY_normalized_mm.step`
  (present on disk). The raw `motor_az(1).step` is not present in the repo
  (`components/5840-31ZY/source/` contains only a README) and is correctly
  treated as superseded historical provenance, not an Epic input. Legacy
  `legacy_reference/motor_az.step` / `motor_el.step` are not required anywhere
  in the Epic or plan.
- One accepted component definition instantiated as `motor_AZ` and `motor_EL`
  with independent placement and common trusted representation authority
  matches the launch package (§12) and the per-instance trusted-mapping
  production contract.
- Stall torque `39.2266 N*m` remains source fact with design credit prohibited
  (authority YAML `design_credit: PROHIBITED`; Spec preserves this; Task 2
  tests assert it).

## Physical Model

The three-body model is truthful and consistent across the Epic Spec, the
mechanism architecture document (§4, §6, §14), and launch package §16:

- `base_body`: base/frame, AZ motor/mount/pinion, AZ support stations A/B,
  stationary AZ keep-out representation.
- `az_rotating_body`: AZ shaft, AZ driven gear/hub, rotating structure, EL
  fork/frame, EL motor/mount/pinion, EL support stations A/B.
- `el_payload_body`: EL shaft, EL driven gear/hub, antenna carrier, bounded
  antenna envelopes.

`joint_az`: base → az_rotating; axis = common axis of generated AZ shaft and
support stations A/B; continuous; home 0; no hard stop. `joint_el`:
az_rotating → el_payload; axis = common axis of generated EL shaft and supports.
The EL motor belongs to `az_rotating_body`, therefore rotates with AZ and not
with EL. Motor output axes are explicitly parallel, offset by the spur center
distance, and are not joint axes. Production `GeneratedRotationalInterfaceAxisSource`
supports shaft-owned joint axes; `AZ_JOINT.axis == AZ bearing A/B common axis`
binding rules exist in mechanism authority §11. Motor-as-bearing is prohibited
(`MOTOR_IS_STRUCTURAL_SUPPORT = FALSE`, authority YAML
`structural_restriction`).

One wording hazard (MINOR-2 below): the Spec's phrase "`joint_el` … is
non-continuous" must not be mapped to production `BOUNDED` mode with 0/360
angle limits, because production treats those limits as mechanical inclusive
limits and the project forbids inventing a mechanical hard stop before M10.

## Transmission Determinacy

**Verdict: AMBIGUOUS — IMPORTANT-1.** Answer to the review question: the Epic
materially implies (A) — the declared 30T/36T/module-2.0/PA-20°/facewidth-12/
CD-66 seed is the only gearset Epic 01 may instantiate, because the Spec states
"No arbitrary synthesis or optimization is authorized" and no accepted numeric
alternative bounds exist anywhere in project authority (the mechanism document
authorizes changing module/tooth count/face width "as design variables while
preserving ratio approximately 1.20" but defines no numeric search bounds).
However, neither the Spec nor the plan contains a normative sentence stating
that the first candidate instantiates exactly the declared seed values, and the
Spec calls them "bounded design-variable seeds" without stating the bounds. An
implementer could read "bounded" as license to tweak within unstated bounds.
Required revision: one normative sentence in the Epic Spec and in plan Task 3
making the declared seed the explicit first-candidate instantiation while
preserving its `DESIGN_VARIABLE` semantic classification (not `SOURCE_FACT`).

## Generated-Part Determinacy

**Verdict: PLAN_DETERMINACY_GAP — IMPORTANT-2.** Per-family status:

| Family | Status | Evidence |
| --- | --- | --- |
| Gear/hub interface (teeth, module, PA, face width, CD) | Seed fixed, classification DESIGN_VARIABLE | mechanism doc §3; MECHANICAL_CONSTRAINTS "External spur target" |
| Motor offset from axis | Derivation rule: = gear center distance (66 mm seed) | mechanism doc §11 drive-axis relation |
| AZ shaft bore | Bound only: must preserve Ø24 hard / Ø30 preferred keep-out | MECHANICAL_CONSTRAINTS "Rotary-interface keep-out" |
| EL axis height | Bounded range [500,600] mm, initial candidate 520 mm | launch package §9 EL_AXIS_HEIGHT |
| Bearing/support bore | Design candidate only: 6007, bore 35 (not frozen) | launch package §10 BEARING_INITIAL_CANDIDATE |
| Antenna envelopes + positions | Fixed declared values | launch package §8 |
| Envelope bounds | Fixed: base 350×350; body 500×500×650 | MECHANICAL_CONSTRAINTS "Mechanism envelope" |
| Shaft OD / journal diameters / shaft lengths | No value, no range, no rule | readiness closure §10 ("design outputs") |
| Support-station spacing (AZ and EL) | No value, no range, no rule | — |
| Support housing outer dimensions | No value, no range, no rule | — |
| Hub OD / hub length | No value, no range, no rule | — |
| Frame plate dimensions / thickness | No value, no range, no rule | — |
| Fork spacing | No value, no range, no rule (derivable only after EL support spacing is chosen) | — |
| Antenna carrier dimensions | No value, no range, no rule | — |
| Motor mount plate dims | Partially derivable from the confirmed 28×40 M4 motor mount interface | authority YAML `mounting_interface` |

The project authority explicitly authorizes synthesis of the unseeded families
(readiness closure §10: "They are `DESIGN OUTPUTS / DESIGN VARIABLES`… MechCAD
is explicitly authorized to synthesize them"), and the production candidate
contract supports provenanced design selections (`CandidateDesignVariable`;
`GeneratedPlacementDerivation` DESIGN_SELECTION axial-offset inputs,
models/generated_placement.py:176-209). So this is not a
PROJECT_AUTHORITY_GAP, and it is not NOT_BLOCKING as the plan stands: the plan
(Task 3/Task 4) instructs "generated shaft/hub/support/frame geometry" without
fixing or referencing a single initial value for the unseeded families, which
would force the coding agent to invent per-run values that determine the
engineering meaning of the candidate Evidence.

Required revision: freeze an explicit first-candidate design-selection table
(value + authority class + provenance) in the S1 authority manifest or the S2
candidate definition — covering shaft OD/length, journal diameters, support
spacing, support housing dimensions, hub OD/length, frame dimensions, fork
spacing, and carrier dimensions — and mandate those exact values for the Epic 01
candidate, while retaining their `DESIGN_VARIABLE` classification and the global
envelope/keep-out/clearance bounds as admissibility constraints.

## Keep-Out Semantics

**Verdict: REPRESENTABLE BUT UNPINNED — IMPORTANT-3.** The Spec lists
"stationary AZ keep-out geometry" as a required `base_body` member. Under the
accepted candidate contract, every physical instance requires a
`PhysicalComponentRole` and a CAD mapping with exactly one of the three fidelity
classes (cad_realization.py:844-847, 877-910). There is no dedicated
keep-out/envelope record type in the candidate physical mechanism contracts
(the only `keepout` models in production are the unrelated azimuth-mount-plate
subsystem), so a free-floating "constraint/keep-out record" is not an available
production-native representation for this candidate.

The one truthful production-native route is to model the keep-out as a
constituent with fidelity `DECLARED_BOUNDED_COLLISION_REPRESENTATION` — the
same accepted precedent as the antenna envelopes, which are declared
non-manufactured collision representations that are constituents of a body
(launch package §16). This does not falsely claim empty space is a manufactured
solid, because the fidelity class explicitly marks the representation as
declared rather than manufactured/generated. Cross-body pairs (keep-out vs
az_rotating/el_payload members) would be `CHECK_CLEARANCE` at 5 mm, which
conservatively enforces the Ø24 hard / Ø30 preferred / 100 mm axial reservation;
same-body pairs with other base members are `SAME_RIGID_GROUP_EXCLUDED`.
Proving the reservation without any constituent (e.g., purely via generated
bore/opening geometry) would contradict the Spec's own body table.

The hazard: neither the Spec nor the plan states the fidelity class, the role
mapping (`PhysicalComponentRole` has no keep-out role; a declared mapping must
be chosen and justified), or the pair treatment. An implementer could map it as
`EXACT_GENERATED_GEOMETRY`, which would falsely classify reserved empty space
as generated manufactured geometry in durable Evidence. Required revision: pin
the keep-out's fidelity (`DECLARED_BOUNDED_COLLISION_REPRESENTATION`), its
chosen role with rationale, and its pair treatment in the Spec/plan.

## Support Semantics

**Verdict: TRUTHFUL WITH DECLARED INTERFACE AUTHORITY.** Exactly two generated
support stations per axis are mandated by project authority
(`TWO_SUPPORTS_PER_AXIS = REQUIRED`, launch package §10) and matched by the
Epic. The support stations are generated geometry, not catalog-bearing
selections; the Epic and plan both preserve this ("Candidate generated support
geometry is not a commercial-bearing selection").

Shaft/support intended contact is truthful under the accepted model:
MECHANICAL_CONSTRAINTS explicitly excludes "bearing/shaft seating contacts"
from generic clearance requirements, and `MechanicalConnectionKind` provides
`SHAFT_JOURNAL` / `BEARING_SUPPORT` / `STRUCTURAL_SUPPORT_DECLARATION` with
`INTENDED_CONTACT_EXCLUDED` requiring an explicit non-blank reason
(physical_pair_policy.py:81-82). The support station bore is the generated
bearing seat; no commercial bearing is claimed.

One caution (MINOR-3): excluded pairs are not measured by M10, so an exclusion
label can hide geometrically impossible interfaces (e.g., journal OD larger than
support bore). The plan's S4 tests should require interface dimensional
consistency for every intended-contact pair; as written they do not. Also, the
role assignment for generated supports (`BEARING` vs `MOUNT_OR_SUPPORT` in
`PhysicalComponentRole`) should be declared explicitly so Evidence cannot imply
a purchased bearing.

## Pair Policy

**Verdict: CORRECT AND COMPLETE BY CONSTRUCTION.** The Spec requires every
unordered constituent pair to be classified exactly once; the production bridge
independently re-derives the complete concrete pair inventory from the physical
policy and rejects incompleteness against `itertools.combinations` of the
concrete universe (multi_joint_m10_bridge.py:1810-1812), and enforces
same-body ⇒ `SAME_RIGID_GROUP_EXCLUDED` and cross-body ⇒ not same-group
(multi_joint_m10_bridge.py:1732-1737). Scope is therefore mechanically derived
from the member inventory, not a hand-selected list. `INTENDED_CONTACT_EXCLUDED`
requires explicit interface authority (non-blank reason; Spec restricts it to
declared mating interfaces including both gear meshes). The two spur gear meshes
are real mating interfaces with `MechanicalConnectionKind.GEAR_MESH` support.
The three classifications used by the Epic are a subset of the production enum
and are semantically compatible.

## M10 Configuration Determinacy

**Verdict: UNDER-DETERMINED — IMPORTANT-4.** The Spec states AZ ∈
{0, 90, 180, 270, 360} and EL ∈ {0, 45, …, 360} "with named home, endpoint,
cardinal, and combined non-home configurations." This does not define one exact
set: reading (A) — the full Cartesian product 5 × 9 = 45 configurations — is
the most defensible interpretation but is nowhere stated as normative; reading
(B) — some smaller named list — is not enumerated; no deterministic
construction rule is given. The plan defers to a to-be-created
`m10_configurations.json` and a unit test asserting "the named AZ/EL set"
without an external reference, which is circular (the test would validate
whatever the builder chose). Because the configuration set defines the entire
verification scope of the candidate Evidence (each configuration runs the
complete exact pair scope in real FreeCAD), agent discretion here is
material.

The FK periodic-equivalence states (±360, ±720, ±1080 deg) are correctly kept
separate from the physical M10 configuration set in both documents (they are
FK geometric-equivalence checks, not additional M10 collision configurations);
the plan must state explicitly that they do not multiply the M10 scope.

Required revision: define in the plan one exact ordered configuration set —
recommended: the full 5 × 9 Cartesian product in a stated deterministic order —
or one deterministic construction rule, and require the unit test to compare
against that normative enumeration rather than against the builder output.

## CAD / M10 Production Route

**Verdict: CORRECT.** S5 requires exactly the accepted production route:
`ProductionApplication.realize_candidate_cad()` then
`ProductionApplication.evaluate_candidate_multi_joint_m10()` (application.py:2128,
2143), real production FreeCADCmd (MECHCAD_FREECADCMD configured; unchanged
120 s non-retrying subprocess semantics per M13-4 acceptance), trusted imported
normalized motor geometry, generated CAD geometry, complete exact pair scope,
finite exact `common().Volume` / `distToShape()` measurements, and durable
candidate-scoped Evidence. The plan's Test Gate 3 and integration test
explicitly forbid fake providers, MCP substitutes, fixture-only measurement
paths, and skips. No continuous-path, region, M10-4, or global-clearance claim
is permitted anywhere in the Epic; EL 0..360 is an evaluation request only.

## Story Ownership

S1 → S2 → S3 → S4 → S5 is valid. S2 consumes only the S1 manifest and accepted
binding/artifact/state APIs. S3 consumes only S2 inputs and contains no CAD
dependency. S4 consumes the complete S3 physical model and pair policy. S5
consumes verified S4 CAD plus the complete S3 pair policy. No downstream Story
supplies authority missing upstream. The Spec's S3/S4 split is correct
(S3 = physical authority and generated-part *specifications*; S4 = CAD
mappings, representations, placements, realization).

One wording hazard (MINOR-1): plan Task 3 says "Implement the physical
realization with generated shaft/hub/support/frame geometry," which invites CAD
lowering to leak into S3. The production contracts structurally prevent this
(`PhysicalMechanismRealization` contains no CAD; CAD enters only at
`CandidateCadRealizationRequest@2`), but the plan wording should be changed to
"generated-part specifications" in S3 to make the ownership boundary explicit.

## Test Adequacy

The proposed seven-file test set covers authority, physical mechanism, pair
policy, CAD mapping/provenance, configuration determinacy, and a real
production candidate M10 integration test. Adequate in scope. Circular-proof
risks identified:

- Configuration test asserts the agent-chosen set (IMPORTANT-4 above).
- Pair-policy tests derive pairs from the same inventory the policy was built
  from — mitigated by the production bridge's independent combinations-based
  completeness check in the integration path, which is an acceptable
  independent gate.
- CAD mapping/provenance tests should validate against accepted model
  invariants (fidelity rules, placement-origin provenance, one-derivation-per-
  generated-mapping) rather than restating builder outputs; the plan's S4 test
  bullet already points in this direction.

## Regression Gates

**Verdict: UNDER-SPECIFIED — IMPORTANT-5.** The plan says "run relevant
protected M10/M12/M13 regression selectors" without naming them, although the
exact accepted predecessor gates for the contracts exercised by Epic 01 are
known. Required minimum frozen set:

```text
tests/integration/test_m13_4_full_stack_acceptance.py
tests/integration/test_m13_3_candidate_m10_production.py
tests/integration/test_m13_3_generic_multi_joint_acceptance.py
tests/integration/test_m13_2_generated_parts_live.py
tests/integration/test_m12_candidate_cad_m10_production.py
tests/integration/test_m12_6_end_to_end_external_spur.py
```

(`test_m12_6_end_to_end_external_spur.py` is directly relevant because both
Rotator axes use `EXTERNAL_SPUR_REDUCTION`.) Required revision: freeze this
list (or a reviewed superset) in the plan's Test Gates before implementation.

## Later Holds

Correctly left outside first implementation, with contract evidence that none
is required for truthful candidate CAD/M10-3:

- Motor radial/axial/bending qualification, gearbox efficiency, thermal
  duty-cycle, exact motor mass: authority YAML `unresolved_nonblocking`;
  non-blocking because the motor is prohibited from structural support and the
  Epic makes no torque-above-rated or mass claim. Gearbox efficiency affects
  only driven-shaft torque claims, which the Epic does not make.
- Final commercial bearing selection: supports are generated geometry; the Epic
  explicitly does not select bearings.
- Materials / wind loads / M11 / whole-assembly FEA: M11 remains FAIL by
  design; Epic prohibits all M11 artifacts.
- Fastener release, M4 tapped-hole depth (explicitly a manufacturing hold point
  that must not be inferred by M12/M10 — readiness closure §4), manufacturing
  tolerances, weather sealing: none needed for geometric M10-3 evidence.
- Slip-ring selection, RF rotary joint, cable bend radius: the keep-out is
  explicitly `DECLARED_DESIGN_KEEP_OUT`, not a selected product; the Epic
  selects none of these.

## Findings

CRITICAL: none.

IMPORTANT:

1. **IMPORTANT-1 — Transmission first-candidate determinacy (§7 of review
   brief).** The declared 30T/36T/module-2.0/PA-20°/facewidth-12/CD-66 seed is
   the only authorized instantiation, but no normative sentence in the Spec or
   plan states it, and no accepted numeric alternative bounds exist. Plan
   determinacy gap.
2. **IMPORTANT-2 — Generated-part first-candidate determinacy (PLAN_DETERMINACY_GAP).**
   No frozen initial design-selection table exists for shaft OD/length, journal
   diameters, support spacing, support housing dimensions, hub OD/length, frame
   dimensions, fork spacing, or antenna-carrier dimensions; the plan would
   force the coding agent to invent these per run.
3. **IMPORTANT-3 — AZ central keep-out representation unpinned.** The only
   truthful production-native route is a `DECLARED_BOUNDED_COLLISION_REPRESENTATION`
   constituent; the Spec/plan do not pin the fidelity, the role mapping, or the
   pair treatment, risking a false `EXACT_GENERATED_GEOMETRY` manufactured-solid
   claim in durable Evidence.
4. **IMPORTANT-4 — M10 configuration set not exactly defined.** The 5 × 9 value
   grids plus "named home, endpoint, cardinal, and combined non-home
   configurations" do not determine one exact ordered set or construction rule;
   the configuration unit test as planned is circular.
5. **IMPORTANT-5 — Regression gates not frozen.** "Relevant protected
   M10/M12/M13 regression selectors" is left to agent discretion although the
   exact accepted predecessor suites are known.

MINOR:

1. **MINOR-1 — S3 CAD-leakage wording.** Plan Task 3 "generated shaft/hub/
   support/frame geometry" should read "generated-part specifications" to match
   the Spec's S3/S4 ownership boundary.
2. **MINOR-2 — `joint_el` "non-continuous" wording.** Must not be mapped to
   production `BOUNDED` mode with 0/360 limits (which production treats as
   mechanical limits); EL should carry no angle limits in the production model,
   with 0..360 living only in the evaluation request, per the Spec's own
   "no mechanical hard stop or final usable range is invented."
3. **MINOR-3 — Intended-contact exclusions are unmeasured.** S4 tests should
   require dimensional consistency of every excluded interface (journal vs
   bore, gear mesh geometry, hub/shaft fit) so exclusions cannot hide
   geometrically impossible interfaces.
4. **MINOR-4 — Generated support role mapping.** The `PhysicalComponentRole`
   assignment for generated support stations should be declared explicitly so
   Evidence cannot imply a purchased bearing.

NOTE: The launch package still contains stale bounds (380×340 / 400×400×650)
and the superseded EL direct-coaxial initial candidate; these are exactly the
stale text S1 reconciles, and S1's reconciliation preserves them as superseded
history without rewriting engineering semantics. Historical traceability is
preserved.

## Required Revisions

1. Add a normative statement (Spec "Motor And Transmission Authority" + plan
   Task 3) that Epic 01's first candidate instantiates exactly the declared
   30T/36T/module-2.0/PA-20°/facewidth-12/CD-66 seed, classified as
   `DESIGN_VARIABLE`.
2. Add a frozen first-candidate design-selection table (S1 authority manifest or
   S2 candidate definition) fixing initial values with provenance for shaft
   OD/length, journal diameters, support spacing, support housing dimensions,
   hub OD/length, frame dimensions, fork spacing, and carrier dimensions; adopt
   the existing seeds (EL axis height 520 mm within [500,600]; 6007 bearing
   candidate) explicitly if used.
3. Pin the AZ keep-out representation: `DECLARED_BOUNDED_COLLISION_REPRESENTATION`
   fidelity, an explicitly justified role mapping, and CHECK_CLEARANCE pair
   treatment against cross-body members.
4. Define the exact ordered M10-3 configuration set (recommended: full 5 × 9
   Cartesian product in a stated deterministic order) or a deterministic
   construction rule, and make the configuration unit test compare against that
   normative enumeration; explicitly scope the ±360/±720/±1080 FK equivalence
   checks outside the M10 configuration set.
5. Freeze the named regression selector list in the plan's Test Gates.
6. Apply the MINOR wording fixes (S3 "generated-part specifications"; EL joint
   carries no production angle limits; intended-contact dimensional-consistency
   checks in S4 tests; explicit support-station role mapping).

## Acceptance Decision

The Epic's hierarchy, boundary, production route, motor authority, body/joint
model, support semantics, pair policy, claim boundary, later holds, and story
dependencies are correct and grounded in accepted authority. The five IMPORTANT
determinacy/precision findings above must be revised in the Spec/plan before
implementation begins. Upon revision of plan text only (no production change,
no authority rework), the plan is ready for independent re-acceptance.

```text
ROTATOR_V2_EPIC_01_PLAN_REVISE
```
