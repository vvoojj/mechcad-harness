# F7 Shared CAD Dimension Resolution

## Status and scope

This design remediates F7 only: candidate and canonical legacy mounting-plate
CAD must resolve equivalent semantic dimensions through one shared contract.
It does not merge the candidate and canonical CAD stages, change M10
validation, alter defaults or units, add generated-part behavior, or remediate
F1, F3, F4, F5, F6, F8, or F11.

## Current defect

The candidate and canonical legacy mounting-plate paths both resolve three
semantic dimensions, but use copied alias maps with different ordering and
source precedence. The affected dimensions are `length_mm`, `width_mm`, and
`thickness_mm`. Each has these aliases:

- `geometry.<dimension>`
- `plate_<dimension>`
- `<dimension>`

Candidate CAD reads properties before scoped design variables. Canonical CAD
reads accepted design choices before properties. Prior copies also ordered
aliases differently. Consequently, an otherwise accepted component carrying
`geometry.length_mm = 100.0` and `length_mm = 30.0` can realize different
candidate and canonical plates.

M13-2 generated parts do not participate in these alias maps. Their dimensions
remain authority-bound typed semantic fields and are out of scope.

## Shared semantic contract

Add a small candidate-neutral module at
`src/mechcad_harness/candidates/dimensions.py`. It must not depend on
application composition, promotion, CAD backends, runtime services, or state
management.

The module owns one canonical alias *set* for the three legacy plate semantic
dimensions. The contract accepts normalized input records containing only the
semantic dimension name, alias, normalized millimeter value, and provenance
identity. Candidate and canonical adapters collect those records from their
own representations; the shared contract never receives a complete candidate
or `DesignState` object.

The resolver must:

- validate that each supplied alias belongs to the semantic dimension;
- require finite, positive, already-normalized `mm` values;
- accept one supplied alias;
- accept multiple aliases only when their values are exactly equal;
- reject differing values regardless of alias ordering or source;
- return the resolved value and deterministic consumed provenance identities.

The alias set has no semantic precedence. Its stable lexical ordering may be
used only to make diagnostic messages deterministic. Exact equality applies
only to direct stored normalized millimeter values. This remediation introduces
no conversion or tolerance behavior; a future non-normalized input contract
must use an existing MechCAD numerical-equality convention before it can use
this resolver.

## Validation and stage integration

`MechanicalDesignCandidate` gains an early validation gate. For every legacy
plate-capable physical component, it collects specification properties and the
component-scoped candidate design-variable spellings currently supported by
candidate CAD. It invokes the shared resolver once per component instance and
semantic dimension. Ambiguous alias or property-versus-design-variable values
therefore fail at candidate construction, before CAD realization.

Candidate CAD continues to be a distinct stage. Its generated bounded-plate
adapter collects candidate properties and design variables, invokes the shared
resolver, then compiles the existing mounting-plate program unchanged.

Canonical CAD continues to be a distinct stage and never consumes candidate CAD
artifacts. Its adapter collects canonical accepted design choices and canonical
properties, invokes the same resolver, then compiles the existing mounting-plate
program unchanged. Resolver-level conflict checks remain mandatory here so a
directly constructed canonical record cannot bypass the candidate-model gate.

Promotion remains representation-preserving. It neither silently chooses nor
overwrites aliases. Existing property copying and choice remapping remain in
place; any promotable candidate has already passed alias agreement, and the
canonical resolver independently enforces it after reconstruction. No
candidate/canonical hashes or wire schemas change for unambiguous inputs.

## Verification

Focused tests will cover all three semantic dimensions with parameterization:

- the known `geometry.length_mm=100.0` plus `length_mm=30.0` conflict rejects
  before accepted candidate CAD;
- equal aliases are accepted and resolve identically in both stages;
- each candidate-only and canonical-only supported spelling preserves existing
  plate parameters;
- conflicting properties versus candidate design variables and canonical
  accepted choices are rejected rather than source-prioritized;
- an unambiguous promoted candidate gives equal candidate and canonical resolved
  dimensions;
- M13-2 generated-part realization remains covered and unchanged.

Tests compare normalized resolved semantic dimensions or plate-program
parameters, not candidate and canonical artifact identities. The stages retain
their intentionally separate request, mapping, and realization identities.

## Compatibility

The only intentional behavior change is that ambiguous legacy plate aliases,
including persisted records reconstructed directly into canonical state, fail
closed. Existing accepted fixtures must be searched before implementation. If
an accepted ambiguous fixture exists, it must be identified and handled by an
explicit compatibility policy rather than silently reinterpreted. No such
fixture has been identified by the initial F7 audit evidence.

## Acceptance criteria

- Exactly one semantic alias contract is used by both legacy plate realization
  paths.
- Alias order and source order cannot select between conflicting values.
- Agreement is checked per component instance and semantic dimension.
- Candidate-model validation fails ambiguity before CAD realization.
- Canonical realization retains resolver-level defense in depth.
- Candidate and canonical CAD stages remain independent.
- Existing unambiguous legacy plate and generated-part behavior is unchanged.
- The F7 audit record is appended with actual remediation evidence; historical
  finding text and `docs/reconstruction/**` remain unchanged.
