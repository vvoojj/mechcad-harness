# M13-1 Completion Report

## Final Marker

M13_1_SUPPLIED_COMPONENT_NUMERIC_INTERFACE_AUTHORITY_IMPLEMENTED_AND_VERIFIED

## Scope

M13-1 adds generic source-bound numeric shaft and mounting interface authority
for supplied STEP components. It adds typed evidence, facts, local reference
frames, direct shaft and mounting interfaces, explicit source-to-derived
similarity transforms, deterministic materialization, provenance replay,
candidate publication checks, promotion, and fresh canonical reconstruction.

No generated mechanism CAD, mating solver, catalog, recognition, M13-2,
M13-3, M13-4, M10, M11, or Rotator-specific production behavior was added.

## Production Files

Changed production files:

- `src/mechcad_harness/models/component_property.py`
- `src/mechcad_harness/models/geometry_identity.py`
- `src/mechcad_harness/models/quaternion.py`
- `src/mechcad_harness/models/supplied_component_interface.py`
- `src/mechcad_harness/models/physical_mechanism.py`
- `src/mechcad_harness/models/__init__.py`
- `src/mechcad_harness/candidates/models.py`
- `src/mechcad_harness/candidates/services.py`
- `src/mechcad_harness/candidates/promotion_models.py`
- `src/mechcad_harness/candidates/promotion.py`
- `src/mechcad_harness/candidates/canonical_mechanism.py`
- `src/mechcad_harness/candidates/__init__.py`

## Tests

Added M13 tests:

- `tests/unit/test_m13_authority_enum_compatibility.py`
- `tests/unit/test_m13_geometry_identity.py`
- `tests/unit/test_m13_legacy_hash_compatibility.py`
- `tests/unit/test_m13_quaternion.py`
- `tests/unit/test_m13_supplied_component_interfaces.py`
- `tests/unit/test_m13_geometry_materialization.py`
- `tests/unit/test_m13_publication_replay.py`
- `tests/unit/test_m13_interface_promotion_roundtrip.py`

## Geometry Identity

`GeometryArtifactIdentity` is a shared immutable projection containing artifact
ID, artifact SHA-256, source identity, format, coordinate-system ID, and its
own semantic hash. The identity hash excludes only its own hash field and does
not depend on `GeometrySourceReference.reference_hash`. Candidate and canonical
projections are real attribute projections. Legacy reference projections omit a
`None` coordinate-system ID explicitly.

## Authority and Evidence

The existing component-property availability and authority enums now have one
lower-level owner in `models/component_property.py`; candidate and canonical
legacy imports are the same Python enum classes with unchanged serialized
values.

Evidence supports scalar, vector3, quaternion, and text values. Numeric units
are required even for unavailable values; text has no canonical unit.
Unavailable values are represented by `None`, never a sentinel. Evidence
preserves availability, authority, source identity, applicability, conversion
provenance, origin, document identity, geometry binding, confirmation basis,
and self-hash. Facts allow unresolved, inferred-only, missing, and unselected
snapshots. Authoritative consumption is an explicit gate, not a Pydantic
construction side effect.

## Direct Interfaces

Generic `RotationalShaftInterface`, `MountingFaceInterface`, `MountingHole`,
bounded D-flat details, optional pilot/boss and thread details, and the tagged
`SuppliedComponentInterfaceDefinition` are implemented. Interfaces bind to an
exact geometry identity and semantic IDs; no FreeCAD face index or
four-hole-only abstraction is used.

## Full Transform Authority

`GeometryDerivationTransform` has separate evidence-bound translation,
rotation, and uniform-scale authority facts plus an explicit unit-conversion
declaration. Zero translation and identity rotation require selected accepted
evidence. Proposed, inferred, unselected, or derived-only authority cannot
materialize. The single pure role-aware transform core implements point,
length, displacement, direction, orientation, and text rules, including scale
1.25 fixtures using explicit model-unit labels.

## Reference Frames

Frames are owned by component specifications, with same-specification ID
resolution and exact geometry binding. Materialization transforms a source
frame origin and orientation into a new derived-bound frame. The active derived
frame is stored once in the derived specification and is supplied explicitly to
verification. Conflicting same-ID derived frames fail closed.

## Provenance and Replay

Materialized interfaces retain a direct source-interface snapshot and optional
source-frame snapshot as historical derivation inputs, plus source/derived
geometry, transform, frame, and closed fact-derivation bindings. Active
endpoints come only from the enclosing specification collections.

`MaterializedInterfaceVerifier` replays source facts, the accepted transform,
and the exact caller-resolved active frame through the same pure derivation
functions used for creation. It compares complete typed semantics, hashes,
bindings, and provenance and raises integrity failure on mismatch. It performs
no ArtifactStore I/O or arbitrary frame lookup.

## Component Specifications

`component-specification@1` and `canonical-component-specification@1` retain
their historical JSON and SHA-256 identities, with explicit serializers that
omit M13 fields. `@2` carries frames, interface definitions, transforms, and
coordinate-system semantics with complete hashing and validation. Validation
covers IDs, frame resolution, exact geometry bindings, materialized replay,
frame-normal consistency, and active-versus-historical separation.

## Publication Trust Boundary

`CandidatePublicationService.resolve` uses the exact schema-and-payload trigger
for M13 verification. Accepted transforms receive source and derived STEP byte
verification. Materialized interfaces receive exact transform/frame resolution
and replay after artifact verification. Proposed transforms remain typed
proposal data. `CandidateCurrentnessService` was not changed.

## Promotion and Mapping

Promotion classifications are scoped by candidate specification hash. Frames
and complete interfaces are `ACCEPTED_PHYSICAL_FACT` records by exact
self-hash; transforms are `CANONICAL_REDERIVATION_INPUT` records by exact
self-hash. Complete tuples, evidence, selections, geometry identities,
provenance, bindings, and transform authority are copied to canonical models.

Mapping uses `candidate-canonical-mapping@2` whenever any component
specification is `component-specification@2`, including an empty `@2` payload.
All-`@1` candidates retain mapping `@1`; mixed candidates require `@2`.

## Fresh Reconstruction

`CanonicalPhysicalMechanismCompiler` verifies selected, accepted-transform, and
materialized provenance STEP artifacts through `ProjectArtifactResolver` before
its explicit canonical replay. It resolves active derived frames from the same
canonical specification and passes them directly to the verifier. Reconstruction
uses persisted `DesignState`, canonical mechanism data, and project artifacts;
candidate objects, Markdown, parser state, and prior in-memory proposals are
not required.

## Verification Results

Focused M13 tests:

- `180 passed`
- No required M13-1 positive path was skipped.

Required M12 regression matrix:

- `204 passed`

Full suite:

- Command: `py -3 -m pytest tests/`
- Python: `3.14.6`
- pytest: `8.4.2`
- Tests collected: `2164`
- Passed: `2130`
- Skipped: `34`
- Failed: `0`
- Errors: `0`
- Elapsed: `2998.93s` (`0:49:58`)

The full suite included live and optional-backend tests. No required M13-1
positive path was skipped.

Static verification:

- `py -3 -m compileall -q src/mechcad_harness tests`: passed
- `git diff --check`: passed; only existing line-ending normalization warnings
- Explicit trailing-whitespace scans of touched source/test text: zero matches
- Final-newline checks of touched source/test/report text: passed
- Final self-review: no unresolved Critical or Important M13-1 findings

## Legacy Compatibility

Literal candidate geometry reference, canonical geometry reference,
component-specification@1, and canonical-component-specification@1 payload and
hash goldens remain unchanged. Coordinate-system semantics are excluded from
legacy projections only when the value is the explicit legacy `None`; nonlegacy
values participate in the new identity.

## Limitations

M13-1 does not generate shafts, hubs, bearings, brackets, or frames; solve
assembly mates; recognize STEP features; select components; model timing belts;
bridge supplied shafts to M10 joints; implement M13-2/M13-3/M13-4; provide
tolerance/GD&T, manufacturing approval, assembly FEA, or Rotator V2 completion.
The numeric interface is an authority and integrity substrate, not a fit,
clearance, manufacturing, or engineering-feasibility result.

## Worktree and Release Actions

The repository contains pre-existing unrelated dirty and untracked generated
project artifacts and scratch files. They were not reverted or modified.
M13-1 changes remain uncommitted as required.

COMMIT = NO

TAG = NO

PUSH = NO
