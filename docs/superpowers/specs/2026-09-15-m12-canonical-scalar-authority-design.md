# M12 Canonical Scalar Authority Accepted-Design Candidate

**Status:** accepted-design candidate for implementation planning. This is not
normative architecture, acceptance evidence, or an implementation claim.

## Problem

`DesignState.authoritative_parameters` is canonical typed engineering authority.
Constraint-resolution admission persists output speed as:

```json
{"kind":"transmission.output_angular_speed","value_rad_s":<finite-number>}
```

The accepted M12 raw source-authority path instead requires a literal canonical
record exactly equal to `{"value": <number>, "unit": <string>}` and M12 motor
checks consume rpm. No current production route can truthfully turn the typed
canonical output-speed parameter into an M12 trusted scalar. This is a
`PLATFORM_CAPABILITY_GAP`, separate from the independently accepted
constraint-resolution canonical application capability.

## Goal

Add the smallest additive, read-only path:

```text
typed canonical AuthoritativeParameter
-> verified noncanonical canonical-unit scalar projection
-> explicit M12-local rad/s-to-rpm lowering
-> ProjectedSourceBoundScalar
-> existing RevoluteDriveEngineeringRequirements
-> unchanged rpm-based calculations
```

## Scope

- Project only `OutputAngularSpeedValue.value_rad_s` as canonical `rad/s`.
- Verify projection provenance against an already supplied canonical source
  state.
- Add a projection-backed output-speed scalar variant for M12.
- Preserve the raw M12 scalar route and existing M12-6 serialized records.
- Exercise the new route through
  `ProductionApplication.realize_and_evaluate_revolute_drive`.

## Non-Goals

- No canonical state/model/hash/serialization changes.
- No scalar companion collection or persisted projection store.
- No generic unit conversion framework or projection registry.
- No conversion inside the generic projector.
- No automatic construction of all M12 requirements.
- No candidate generation, promotion, M13 change, CAD/M10 redesign, or
  constraint-resolution redesign.
- No claim that M12-6 already proves the new typed-authority route.
- `tests/integration/test_constraint_resolution_canonical_admission.py` is an
  accepted regression surface and is not modified by this work.

## Protected Boundaries

The implementation must not change `DesignState`, `AuthoritativeParameter`,
existing `AuthoritativeValue` fields, `state.hashing.canonical_json`, canonical
state hashing, constraint-resolution admission, raw `CandidateSourceBinding`,
raw `CandidateSourceReference`, raw `SourceBoundScalar`, raw
`TrustedCanonicalScalarSourceBinding`, or M12 calculation implementation.

`DesignState` remains the only canonical engineering authority. The projection,
lowered scalar, candidate, result, artifact, and Evidence are noncanonical.

## Canonical Locator

```text
AuthoritativeParameterLocator
  project_id: str
  parameter_id: str
  source_revision: int
  source_state_hash: sha256
```

The parameter ID, not an `authoritative_parameters` array position, is the
engineering identity. The pure projector must require that the supplied project
matches the locator, supplied state revision matches, and recomputed state hash
matches. It finds exactly one parameter by ID; zero or multiple matches fail
closed. The parameter's model validation must succeed before projection.

## Projection Contract

```text
CanonicalScalarProjection
  source: AuthoritativeParameterLocator
  authoritative_key: SupportedConstraintKey
  authoritative_parameter_hash: sha256
  value: float
  unit: str
  projection_rule_id: str
  projection_hash: sha256
```

`authoritative_parameter_hash` is the SHA-256 of
`state.hashing.canonical_json(parameter.model_dump(mode="json"))`. It covers
parameter ID, anchor, scope, key, typed value, and `source_resolution_id`.

The only initial semantic rule is owned by the engineering-value layer:

```text
OutputAngularSpeedValue.value_rad_s
-> value=<value_rad_s>, unit="rad/s"
-> authoritative-output-angular-speed-rad-s@1
```

All other typed authority values fail closed. `projection_hash` hashes every
projection field except itself using the existing canonical JSON contract. It is
a derived tamper-evident identity, never authority and never independently
persisted.

The generic projector is pure and read-only over `(project_id, source_state,
locator)`. It owns no `StateManager`, does not load revisions, mutate state,
persist data, read candidates, know M12, or convert units.

## M12 Projected Scalar Contract

```text
ProjectedSourceBoundScalar
  value: float
  unit: Literal["rpm"]
  canonical_projection: CanonicalScalarProjection
  normalization_rule_id: Literal["m12-output-angular-speed-rad-s-to-rpm@1"]
  normalized_value_hash: sha256
  binding_hash: sha256
```

This is one S1 record; there is no second projected-binding collection. `value`
is the sole M12-normalized value. `normalized_value_hash` hashes only
`{"value": value, "unit": unit}`. `binding_hash` hashes the full record except
itself. The record has no `source_path` or raw-source `provenance`: its type and
embedded canonical projection claim establish its noncanonical provenance. The
field is intentionally named `canonical_projection`:
a deserialized caller-supplied record is untrusted until production-side
recomputation succeeds.

Extend only:

```text
RevoluteDriveEngineeringRequirements.required_output_speed:
  SourceBoundScalar | ProjectedSourceBoundScalar
```

The existing raw type is first. The union is structural, not discriminated:
the projected type requires `canonical_projection`, while raw models forbid
extras. Existing raw objects therefore dump exactly as before.

## M12 Lowering

The M12-local lowering accepts a `CanonicalScalarProjection` claim with key
`transmission.output_angular_speed` and unit `rad/s` and calculates:

```text
rpm = rad_per_second * 60.0 / (2.0 * pi)
```

Use the same Python binary64 expression in construction and verification. No
rounding, tolerance, or caller-selected unit is permitted; exact equality is
required. Calculations continue to consume `.value` and `.unit == "rpm"` and
must not learn about rad/s, locators, projections, or rules.

## Verification Paths

Raw `SourceBoundScalar` with `SOURCE_AUTHORITY` retains the current path:
literal canonical path, matching `CandidateSourceBinding` reference, matching
`TrustedCanonicalScalarSourceBinding`, exact raw `{"value","unit"}` record,
and exact hashes. Typed/composite raw records remain rejected.

`ProjectedSourceBoundScalar` uses a separate branch. Its embedded
`canonical_projection` is a claim, not pre-existing trust. The branch verifies
finite rpm, normalized hash, matching request/source identity, the locator
against the already loaded source state, exactly one parameter ID, full
parameter hash, typed projection key/value/unit/rule/hash, canonical
output-speed key and `rad/s` unit, exact normalization, and binding hash. It
does not use a raw path or legacy raw-binding dictionary.

The production verifier performs these checks in order: request/source
identity; source-state hash; exact parameter ID; full parameter hash; fresh pure
typed projection; equality of the embedded `canonical_projection` claim with
that recomputed projection; exact `rad/s` to rpm lowering; normalized hash and
binding hash. Only successful completion makes the projected scalar acceptable
as M12 source-authoritative input. The pure projector creates the expected
projection over trusted supplied state; lowering is deterministic construction,
not an authority grant.

For the new path, request `CandidateSourceBinding.consumed_authority` must
contain the accepted coarse aggregate reference:

```text
path=/authoritative_parameters
authority=CANONICAL_PARAMETER
```

Its hash binds the whole collection and intentionally makes any collection
change stale. The locator/projection binds the exact parameter member. The
projected verifier also requires:

```text
locator.project_id
== request.source_binding.project_id
== trusted production project context
```

The locator's project field therefore does not self-authenticate project
identity; the surrounding trusted M12 request/application context supplies the
expected identity.

## Compatibility

Before model changes, capture a static valid raw
`RevoluteDriveEngineeringRequirements` JSON payload and its static
`requirements_hash`. New code must parse it, dump exactly the same JSON-mode
payload, retain exactly the same requirements hash, and preserve raw trusted
binding hashes. The compatibility test must not generate the fixture/hash with
new code.

New projected records serialize only under `required_output_speed`; the existing
requirements hash naturally binds their full projection and normalization chain.
No parallel requirements hash is permitted.

## Production Composition

No public generic `ProductionApplication` projector API is added. No artificial
projector dependency injection is added to `ProductionApplication`: the
existing `realize_and_evaluate_revolute_drive` path already loads the exact
current source state and passes it as `source_state` to the pure
`RevoluteDriveRealizationService`. The M12 service calls the pure projector
using the request/source-binding project identity, that supplied state, and the
locator embedded in the projected scalar. No `StateManager` is injected into
the revolute service. Caller-provided projected records remain claims until
that service-side verifier recomputes their provenance.

Only output speed becomes canonically available. Torque, forces, voltage, peak
torque, efficiency, safety factor, shaft strength/support geometry, interface
policy, supplied component properties, templates, and design variables retain
their existing explicit caller, policy, or candidate authority sources.

## Acceptance Criteria

- A production-admitted output-speed authoritative parameter projects to exact
  `rad/s` with locator, full-record, and projection hashes verified.
- M12 lowering produces exact rpm `ProjectedSourceBoundScalar` provenance.
- Existing production M12 evaluation consumes the projected output speed while
  rpm calculations execute unchanged.
- Missing/wrong project, revision, state hash, ID, key, typed value, collection
  reference, hashes, rule IDs, units, or values fail closed.
- Raw composite records remain rejected by the unchanged raw path.
- Static legacy raw requirements and binding golden values remain exact.
- The new projected route receives fresh focused and production-composed proof;
  M12-6 live re-acceptance is a later explicitly authorized decision.
- The accepted constraint-resolution admission test module remains unchanged
  and is run only as a regression gate.
