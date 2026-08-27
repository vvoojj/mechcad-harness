# M12-3 Bounded Revolute-Drive Realization And Deterministic Engineering Sizing

**Date:** 2026-08-27

## Status

Implementation design approved for M12-3. This design extends the accepted M12-2
candidate authority foundation. It does not alter `DesignState`, candidate
publication/currentness/integrity semantics, M10, M11, CAD, comparison,
selection, or promotion.

## Purpose And Bounded Claim

M12-3 will deterministically construct and evaluate supplied-component physical
realizations for exactly one M10 revolute joint using one of two architecture
templates:

- `DIRECT_DRIVE`: motor -> driven shaft -> two supports -> hub -> driven body,
  with a motor mount;
- `EXTERNAL_SPUR_REDUCTION`: motor -> driver external spur gear -> driven
  external spur gear -> driven shaft -> two supports -> hub -> driven body,
  with motor and shaft-support mounts.

The service consumes explicit source-bound engineering requirements, immutable
M12-2 component specification snapshots, candidate-local variables, and an
explicit synthesis policy. A successful construction returns an ordinary
immutable `MechanicalDesignCandidate` plus separately immutable bounded-drive
engineering results. An incomplete template returns a typed pre-candidate
construction outcome with no candidate; it never manufactures an
integrity-invalid candidate. The service does not select a catalog item, mutate
a candidate, publish artifacts/Evidence, make CAD, run M10/M11, or create
canonical state.

The result proves only each recorded check under the following scope. It does
not prove motor thermal duty, gear tooth strength/contact stress/fatigue/life,
backlash, lubrication, bearing life/capacity, coupling capacity, key strength,
shaft fatigue/keyway concentration/critical speed/buckling, tolerance/fit,
manufacturability, collision clearance, or structural/FEM suitability.

## Architecture And Module Boundary

Add a focused `mechcad_harness.revolute_drive` package:

- `models.py`: frozen strict request, template-input, topology, calculation
  input, consumption, result, provenance, and status models;
- `service.py`: pure `RevoluteDriveRealizationService`, which constructs the
  two bounded templates when supplied template inputs are complete and returns
  deterministic engineering results from already-verified inputs;

Add one lower-level generic pure-engineering module, following the repository's
`engineering/` convention, as `mechcad_harness.engineering.spur`. It owns the
one shared nominal spur primitive used by both `tools.builtins.calc_spur_gear`
and the M12-3 service. The generic BuiltinTools layer must never import the
M12-3 `revolute_drive` package. The existing public built-in
`SpurGearInput`/`SpurGearOutput` and ToolBroker registration remain intact.

The primitive takes positive module `m` in mm and positive integer tooth counts
`z_driver`, `z_driven`, and returns:

```text
d_driver = m * z_driver                 [mm]
d_driven = m * z_driven                 [mm]
a = (d_driver + d_driven) / 2           [mm]
i = z_driven / z_driver                 [-]
```

`i` is the positive reduction-ratio magnitude, defined as input motor speed
magnitude divided by driven-shaft output speed magnitude. External mesh
rotation is opposite in direction, but M12-3 accepts only positive scalar
magnitudes and does not check a direction requirement. The primitive is not a
gear strength, contact, life, backlash, lubrication, or manufacturing model.

The service itself is pure with respect to canonical state and has no
`StateManager` dependency. `ProductionApplication` owns the two-phase sequence:

```text
verify request source binding against the current source state
    -> pure service attempts deterministic template admission/construction
    -> if structurally incomplete: return typed unresolved construction outcome, no candidate
    -> otherwise construct MechanicalDesignCandidate
    -> recompute and verify candidate integrity
    -> verify the resulting candidate is CURRENT
    -> pure service evaluates bounded drive engineering
```

Currentness is therefore never requested before candidate construction. Neither
layer receives CAD, FreeCAD, ArtifactStore, EvidenceStore, catalog, optimizer,
or provider dependencies. The application exposes one bounded
realization/evaluation method. It does not compose Gearworks or a catalog.
Optional py_gearworks remains a separate CAD/geometry provider and is not a
required M12-3 dependency.

## Authority, Inputs, Units, And Property Consumption

`RevoluteDriveEngineeringRequirements` is a frozen request input, not a second
source binding. Every required authoritative numeric field names one exact path
already present in the request's `CandidateSourceBinding`; the pure service
rejects an input whose declared source path is not consumed by that binding. The
production entrypoint first validates that source binding against the current
state, constructs the candidate, validates candidate integrity, then requires
the resulting candidate to be `CandidateCurrentness.CURRENT` before evaluation.
Forged candidates raise the existing candidate integrity error; stale or
unavailable currentness is an operational precondition failure, never an
engineering violation.

Every `SOURCE_AUTHORITY` scalar requires an explicit
`TrustedCanonicalScalarSourceBinding` in the M12-3 requirements input. The
production boundary resolves the scalar's canonical path in the current source
state and accepts it only when the record is exactly a generic `{value, unit}`
mapping with the matching finite numeric value and exact unit. The consumed
`CandidateSourceReference.value_hash` and trusted binding record hash must both
match that complete scalar record. Composite records are rejected; production
does not parse prose, infer a field from a composite record, or treat a
recomputed `SourceBoundScalar.source_value_hash` as canonical authority. A
missing or mismatched record is `UNRESOLVED`. Policy assumptions require no
scalar source binding and never become canonical authority.

M12-3 uses only the following explicit canonical units. Exact unit strings are
part of validation; there is no silent conversion:

| Quantity | Unit | Domain |
| --- | --- | --- |
| torque magnitude | `N*m` | strictly positive when required |
| output speed magnitude | `rpm` | one required non-negative scalar; positive motor maximum |
| voltage | `V` | strictly positive when required |
| length/diameter/axial coordinate | `mm` | positive diameter/module/span; coordinate finite |
| force | `N` | finite signed transverse components |
| stress/yield strength | `MPa` (`N/mm^2`) | strictly positive |
| pressure angle | `deg` | strictly between 0 and 90 |
| efficiency | `1` | strictly greater than 0 and at most 1 |
| safety/design factor | `1` | strictly positive |

M12-3 introduces a small typed vocabulary of snapshot keys only for consumed
properties. Generic M12-2 snapshots remain extensible. Required keys are:

```text
motor.continuous_torque_nm
motor.peak_torque_nm
motor.speed_min_rpm
motor.speed_max_rpm
motor.rated_voltage_v
gear.kind
gear.module_mm
gear.tooth_count
gear.pressure_angle_deg
gear.profile_shift
gear.face_width_mm
gear.bore_diameter_mm
shaft.diameter_mm
shaft.yield_strength_mpa
bearing.bore_diameter_mm
hub.bore_diameter_mm
mount.envelope_axial_length_mm
```

The exact key values and units are checked per calculation. A property is
consumed only when its `ComponentPropertySnapshot.property_hash` is included in
that check's ordered `ConsumedPropertyBinding` record with component instance
ID, specification hash, property key, property hash, source identity, and
authority. A property that does not affect a check is not listed or hashed by
that check. A requirement source path is similarly listed explicitly.

Each value additionally records its provenance classification. A value from a
canonical path is `SOURCE_AUTHORITY`; a value from a hard-admissibility policy
entry is `POLICY_ASSUMPTION`. Both can be explicitly consumed and hashed, but a
policy assumption never becomes engineering authority. This classification is
preserved in every consumed-input binding and result. In particular,
transmission efficiency and safety/design factor may be source-authoritative or
explicit policy assumptions, but never hidden defaults or policy-created facts.

The legacy `MotorCharacteristicsValue` remains a separate legacy authority
model. M12-3 does not accept it as component authority and does not make it
canonical. A future caller may normalize an authoritative legacy value into
five M12-2 property snapshots, preserving the original property-specific source
identity and authority; that compatibility normalization is outside M12-3.

## Template Construction And Completeness

`RevoluteDriveTemplateInput` names supplied specification snapshots and explicit
instance IDs. It may enumerate only a caller-supplied finite ordered set of
template inputs. Policy must explicitly allow the requested architecture and
every template design variable. For an exact value, the required
hard-admissibility entry key is `allow-design-variable:<name>` and its value is
the canonical JSON string `{"value": <variable.value>}`. No implicit variable
bounds or defaults are accepted. The service neither discovers components nor
searches product catalogs.

The direct template requires exactly these distinct roles and connections:

```text
actuator motor --ROTATIONAL_DRIVE--> shaft
bearing A --BEARING_SUPPORT--> shaft
bearing B --BEARING_SUPPORT--> shaft
shaft --COUPLING/COAXIAL_CONNECTION--> hub --PAYLOAD_ATTACHMENT--> driven body
motor --MOTOR_MOUNT--> mount
```

The spur template additionally requires separate driver and driven gear
instances (both role `TRANSMISSION`) and these torque/kinematic path edges:

```text
motor --ROTATIONAL_DRIVE--> driver gear
driver gear --GEAR_MESH--> driven gear
driven gear --ROTATIONAL_DRIVE or COAXIAL_CONNECTION--> shaft
```

Both templates require a `JointPhysicalRealizationBinding` for the one scoped
joint. The binding must identify the driven shaft, each template component,
actuator and transmission path connections, both support instances, hub, mount
instances, and a nonempty axis/frame reference. Missing instances, roles,
interfaces, required connections, or binding membership is represented by an
`UNRESOLVED` pre-candidate construction outcome with `candidate = None`; it is
not silently filled. In particular, the service must not construct an M12-2
`MechanicalDesignCandidate` until the resulting graph is structurally and
integrity-valid. Once that candidate exists, missing engineering authority such
as a motor property, shaft material property, efficiency, safety factor, or
required dimensional property is an engineering-check `UNRESOLVED` result and
does not invalidate the candidate. Structural completeness of the graph does
not invoke M10 or prove kinematic/CAD/structural suitability.

The construction boundary is therefore:

```text
template input / realization request
    -> deterministic template admission/construction
    -> if structurally incomplete: typed unresolved construction outcome, no candidate
    -> otherwise: ordinary integrity-valid MechanicalDesignCandidate
    -> candidate integrity verification
    -> candidate currentness verification
    -> bounded engineering evaluation
```

Basic nominal interfaces are checked when declared properties are required:
shaft diameter equals both bearing bore diameters and hub bore diameter exactly
in mm. This is nominal compatibility only, not a fit, tolerance, preload,
retention, or torque-capacity claim. Required mount existence and optional
explicit scalar axial envelope limits are similarly topology/scalar checks, not
bracket verification or collision proof.

## Result Semantics And Identity

Every individual calculation/check has exactly one status:

- `SATISFIED`: all inputs required by the check are present, valid, explicitly
  provenance-bound, and permitted by the calculation contract, and the bounded
  equation/compatibility condition passes. A permitted input may be classified
  as `SOURCE_AUTHORITY` or `POLICY_ASSUMPTION`; the latter remains visibly an
  assumption and does not become engineering authority;
- `VIOLATED`: all inputs for the supported check are present, valid, explicitly
  provenance-bound, and permitted by the calculation contract, but the physical
  requirement is not met. The inputs need not all be engineering authority;
  `SOURCE_AUTHORITY` and `POLICY_ASSUMPTION` remain distinct in provenance;
- `UNRESOLVED`: required authority/property/topology is missing, unavailable,
  not applicable, or a declared required check is outside M12-3 scope.

Normal unsupported requirements become an explicit `UNRESOLVED` check with an
`unsupported_required_check` reason. Schema/programmer validation, candidate
integrity/currentness, and provider/operational failures remain exceptions or
typed operational failures outside those statuses; they must never be recoded as
`VIOLATED` or admissible/inadmissible.

`RevoluteDriveAdmissibilityResult` aggregates the ordered required checks only:

- `INADMISSIBLE` when any required check is `VIOLATED`, even if another
  independent required check is `UNRESOLVED`;
- `UNRESOLVED` when no required check is violated and at least one required
  check is unresolved;
- `ADMISSIBLE` only when every required check is `SATISFIED`.

This precedence preserves every known valid hard engineering violation witness.
Operational and integrity failures remain outside aggregate engineering status.

Every result binds candidate hash; candidate source-binding hash; synthesis
request and policy hashes; exact design variables; exact requirements request
hash; ordered consumed specification/property bindings; calculation identity
and version; result schema version; and its recomputed canonical SHA-256 result
hash. It excludes run IDs, timestamps, paths, artifacts, and transient values.
Nested caller-supplied hashes are recomputed during validation. Different
candidate, requirements, policy, selected diameter, component/property,
efficiency, support geometry, or service/calculation version produces a distinct
result identity. Derived results do not enter candidate identity.

## Direct-Drive Motor Admissibility

`StaticOutputShaftDesignLoadCase` is the one source-bound static design load
case used for shaft torsion, any nominal gear forces, shaft bending, and minimum
diameter. It contains one positive required output-shaft torque magnitude
`T_design_out` in `N*m`, one explicit shaft load-plane coordinate, and either
an explicitly authoritative transverse load vector or an explicit request to
derive that vector from the external-spur mesh. It is not motor maximum
capability. Motor and transmission capabilities are always separate
admissibility comparisons against this load case.

The initial output-speed contract is exactly one required output-speed magnitude
`n_required_out` in `rpm`; it is not a speed interval. For direct drive, motor
output is the driven-shaft output. The service evaluates each requested
requirement independently:

```text
continuous torque: T_motor_continuous >= T_design_out
peak torque:       T_motor_peak >= T_required_peak, when one is source-bound
speed:             motor_speed_min <= n_required_out <= motor_speed_max
voltage:           V_motor == V_required
```

All torque values are positive `N*m`, speeds are non-negative `rpm`, and
voltage is positive `V`. Each input must come from the named authoritative
requirement/property snapshot. A missing continuous torque is `UNRESOLVED` even
if peak or stall torque exists; peak torque is never substituted. A speed value
outside an authoritative usable range, a smaller authoritative torque, or a
different authoritative voltage is a valid `VIOLATED` result. If duty-dependent
derating is requested, it is `UNRESOLVED` because M12-3 has no thermal/duty
model. Interface compatibility is checked only when a hard nominal interface
property is explicitly required.

## External Spur Compatibility, Kinematics, And Torque

Each spur candidate is accepted by the supported calculation only if both
supplied gear snapshots declare `gear.kind = external_spur`, positive integral
tooth counts, a positive equal `gear.module_mm`, a strictly equal
`gear.pressure_angle_deg`, and a positive face width. Profile shift is outside
the initial compatibility/sizing model: both omitted is acceptable; either
present makes the required profile-shift compatibility check `UNRESOLVED` rather
than assuming a convention. Gear bore/shaft nominal compatibility is required
only when an explicit hard interface requirement asks for it; missing required
bore is unresolved. Driver and driven IDs are explicit in the template and
cannot be inferred from tuple order.

For a valid pair, use the shared primitive to derive pitch diameters, center
distance, and ratio magnitude `i`. Output speed is:

```text
n_output = n_motor / i                 [rpm]
```

The scalar required-output-speed check is satisfied exactly when the required
motor speed `n_required_motor = n_required_out * i` lies within the
authoritative usable range:

```text
motor_speed_min <= n_required_out * i <= motor_speed_max
```

Equivalently, `n_required_out` must be in
`[motor_speed_min / i, motor_speed_max / i]`. The mesh reverses direction,
which is reported as an informational limitation rather than a signed-direction
result.

Output torque suitability is only calculated if a distinct efficiency input is
explicit and classified as either a consumed source-authoritative requirement or
an explicit hard-admissibility `POLICY_ASSUMPTION`. With `0 < eta <= 1`:

```text
T_output_continuous = T_motor_continuous * i * eta   [N*m]
T_output_peak = T_motor_peak * i * eta               [N*m]
```

Those quantities are then compared with `T_design_out` and a separately
source-bound peak requirement when requested. Without efficiency, ratio/speed
results remain available but any real output-torque suitability requirement is
`UNRESOLVED`. Ideal multiplication is never treated as real torque capability.
The optional derived power sanity quantity is `P = T * (2*pi*n/60)` in W and
only cross-checks already authoritative/derived values; it grants no thermal or
electrical approval.

## Spur Transmitted Loads

M12-3 derives nominal mesh loads only when the `StaticOutputShaftDesignLoadCase`
explicitly requests driven-shaft mesh loading and the driven pitch diameter and
pressure angle are valid. The calculation uses the source-bound driven-shaft
design torque `T_design_out`, not motor maximum capability and not a torque
back-calculated through the efficiency assumption. For `T_design_out` in `N*m`,
driven pitch diameter `d_driven` in mm, and pressure angle `phi` in degrees:

```text
T_driven_mm = 1000 * T_design_out             [N*mm]
F_t = 2 * T_driven_mm / d_driven              [N]
F_r = F_t * tan(phi * pi / 180)              [N]
```

Pure `calculate_spur_loads` supports the driven-side nominal loads described by
the equations above. The implemented production template has no explicit plane
mapping, so `derive_transverse_load_from_spur_mesh=True` fails closed as
`UNRESOLVED` until an explicit plane mapping is supplied. The equations follow
the elementary pitch-circle force resolution for a rigid external spur pair
(for example, Budynas and Nisbett, *Shigley's Mechanical Engineering Design*,
spur-gear force analysis): pressure angle is measured from the tangent at the
pitch circle, axial/helical force is zero, and dynamic factors are absent.
Invalid/nonpositive driven pitch diameter or pressure angle or missing
design-load authority produces `UNRESOLVED` or validation failure as
appropriate. Mesh efficiency is deliberately not applied a second time in this
driven-side force calculation. These loads do not prove tooth bending/contact
strength, life, wear, lubrication, or backlash.

## Solid-Shaft Static Model

The shaft model is limited to a homogeneous isotropic solid circular shaft under
static elastic loading. It receives exactly two simple radial supports at
explicit axial coordinates `x_A < x_B` in mm, one explicit load plane `x_L`
with `x_A <= x_L <= x_B`, the source-bound `T_design_out` torque magnitude,
and one explicit transverse load vector `(F_y, F_z)` in N. A request to derive
that vector from spur mesh loads is fail-closed as `UNRESOLVED` because the
implemented template has no explicit plane mapping. Overhung loads,
more/fewer supports, multiple transverse loads, axial force, distributed load,
and support compliance are unsupported required conditions.

For each independent transverse plane `q` in `{y,z}`, let `F_q` be the signed
force at `x_L`, `L = x_B - x_A`, and `a = x_L - x_A`. The reactions and maximum
absolute bending moment are:

```text
R_Aq = -F_q * (L - a) / L                   [N]
R_Bq = -F_q * a / L                         [N]
M_q,max = abs(R_Aq * a)                     [N*mm]
M_max = sqrt(M_y,max^2 + M_z,max^2)         [N*mm]
```

The service records force residual `R_Aq + R_Bq + F_q` and moment residual
`R_Bq * L + F_q * a` for both planes. A calculation-specific absolute tolerance
of `1e-9 N` and `1e-9 N*mm` applies because these are algebraic floating-point
residuals at the scale of their native units. A residual above tolerance is an
operational numerical failure, not a violation.

For candidate shaft diameter `d > 0` in mm and
`T_driven_mm = 1000*T_design_out` in N*mm:

```text
sigma_b = 32 * M_max / (pi * d^3)           [MPa]
tau_t   = 16 * T_driven_mm / (pi * d^3)     [MPa]
sigma_vm = sqrt(sigma_b^2 + 3*tau_t^2)      [MPa]
sigma_allow = S_y / n                       [MPa]
```

These solid-circular-section elastic-stress equations are the elementary beam
and torsion relations combined with distortion-energy (von Mises) stress (for
example, Budynas and Nisbett, *Shigley's Mechanical Engineering Design*). They
apply only to the declared static, homogeneous, isotropic, elastic model.
`S_y` is explicitly consumed shaft yield strength in MPa and `n` is an explicit
positive source-authoritative value or an explicit hard-admissibility
`POLICY_ASSUMPTION`. No factor is hidden and a policy value is not engineering
authority. The selected-diameter check is satisfied when
`sigma_vm <= sigma_allow + stress_tolerance`, where
`stress_tolerance = max(1e-9 MPa, 1e-12 * sigma_allow)`; otherwise it is
violated. The tolerance is an explicitly bounded floating-point comparison
allowance, not a safety factor or an authority value.

Because `sigma_vm = C / d^3`, the theoretical minimum diameter is:

```text
C = sqrt((32*M_max/pi)^2 + 3*(16*T_driven_mm/pi)^2)    [N*mm]
sigma_allow = S_y / n                                  [N/mm^2]
C / sigma_allow                                         [mm^3]
d_min = (C / sigma_allow)^(1/3)                         [mm]
```

This is the unrounded theoretical result. Candidate `shaft.diameter_mm` is a
separate candidate design variable/property. The service never rounds, selects,
or writes a standard size. If the selected diameter changes, the caller must
construct a separate candidate with a different candidate hash and obtain a new
result. Missing yield strength, design factor, torque, force/load geometry, or
diameter makes only the affected shaft result unresolved, not failed.

## Validation Strategy

Tests use independent hand equations, not calls to production calculation
functions as oracles:

- shared nominal spur primitive and BuiltinTools return the same independently
  calculated pitch diameters, center distance, and ratio; no two maintained
  implementations exist;
- direct-drive fixture covers satisfied continuous/peak/speed/voltage, torque
  violation, speed violation, voltage mismatch, missing continuous torque, and
  the no-peak-for-continuous regression;
- spur fixture verifies driver=20/driven=100 yields `i=5`, 100 rpm motor yields
  20 rpm output, and explicit-efficiency torque transfer; incompatible module,
  pressure angle, type, and missing efficiency are separately checked;
- gear-load fixture independently evaluates `F_t` and `F_r`, including invalid
  diameter/angle and missing torque authority;
- shaft fixture independently solves each reaction, equilibrium residual,
  resultant bending moment, bending/torsional/von-Mises stress, and `d_min`;
  it evaluates selected diameters at `0.99*d_min`, `d_min`, and `1.01*d_min`
  under the stated comparison tolerance;
- missing-authority matrix covers requirements, motor values, transmission
  efficiency, shaft yield strength/design factor, support/load geometry, and
  declared interface values, all as `UNRESOLVED`;
- aggregate-status tests prove a valid required `VIOLATED` result yields
  `INADMISSIBLE` even when a separate required check is `UNRESOLVED`, while
  integrity/provider failures remain outside aggregate status;
- construction tests prove missing required topology returns the typed
  unresolved pre-candidate outcome with no candidate, while a structurally
  valid candidate with missing engineering authority survives construction and
  produces an unresolved engineering check;
- provenance tests prove that source-authoritative efficiency/design factor and
  policy-assumption efficiency/design factor remain distinctly classified and
  identically explicit in result identity;
- topology tests reject/invalidate incomplete direct and spur templates without
  reinterpretation; provider/tool failure is tested as operationally distinct;
- result identity tests cover semantic equality, volatile-data exclusion,
  property/specification/design-variable/efficiency/support-geometry/service
  version changes, strict JSON round trips, and forged hashes;
- integration capstones prove direct and spur paths, valid violation,
  unresolved efficiency, candidate currentness/integrity rejection, immutable
  original candidate identity, no canonical revision/ChangeEngine call, and no
  ArtifactStore, EvidenceStore, CAD, M10, or M11 call.

## Production Composition And Non-Goals

`ProductionApplication` will expose only
`realize_and_evaluate_revolute_drive(...)`. It validates the request source
binding, asks the pure bounded service to attempt deterministic template
construction, and returns its typed unresolved construction outcome immediately
when no integrity-valid candidate can be constructed. For a constructed
candidate, it recomputes/verifies candidate integrity, verifies candidate
currentness, then delegates bounded engineering evaluation to that same service.
The method returns in-memory candidate/result records. It performs no automatic
publication and has no catalog provider, Gearworks registration, optimizer,
ranking, selection, CAD, M10, M11, `ChangeProposal`, or canonical mutation path.

M12-3 is therefore a deterministic, source/property-bound engineering layer for
the two stated physical-drive architectures only. It is not general mechanism
synthesis or a complete machine-design approval workflow.
