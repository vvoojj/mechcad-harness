# M13-1 Supplied Component Numeric Interface Authority

## Status

Architecture and implementation specification only. This document proposes the
small typed authority extension required for supplied/imported component numeric
interfaces. It does not implement production code, tests, Rotator V2 candidates,
CAD, promotion, M13-2, M13-3, M13-4, timing belts, or any M11 work.

This reconciliation revision is ready for later implementation planning only
after the stated consistency checks pass. It is not an implementation or
acceptance claim.

## Problem

M12 can select an exact imported STEP artifact and preserve it through candidate
CAD and promotion. It can also express physical component/interface IDs,
connections, placements, and an M10 joint physical binding. It cannot express
what a supplied component's interface IDs *mean* numerically in the coordinate
system of that exact STEP artifact.

The missing contract is a generic, authority-preserving answer to questions such
as: which point and direction are the output axis, which plane is a mounting
face, what holes belong to that face, and which source established each number.
The contract must never infer those meanings from a STEP shape merely because a
cylinder, plane, or hole exists.

## Evidence From Real Project

`projects/rotator_v2/components/5840-31ZY/interfaces/INTERFACE_HANDOFF.md`
records a real supplied gearmotor example. It has an exact source STEP and a
separate normalized STEP candidate with a declared, but unconfirmed, uniform
scale of `1.25`. The handoff identifies a proposed output axis, D-shaft values,
mounting plane, and four mounting holes in normalized-STEP coordinates.

The same project deliberately keeps distinct observations distinct:

- a drawing states nominal 8 mm shaft diameter and 28 x 40 mm hole pitch;
- the normalized STEP observation reports approximately 8.01 mm and
  27.438871 x 40.384407 mm;
- shaft/mount interpretations and the source-to-normalized scale remain proposed
  pending human/source confirmation.

Those files are useful consumer evidence only. They are neither an M13 runtime
input format nor platform authority. Production code must not parse their
Markdown to establish an interface.

## Current Repository Gap

The following current contracts were inspected: `DesignState`, M12 candidate and
canonical physical-mechanism models, candidate currentness/publication, candidate
CAD realization, canonical CAD/M10 reconstruction, promotion, M12-2 through
M12-6 tests and completion reports, `ArtifactStore`, `ImportedCadComponent`,
`CadRigidTransform`, and the M10 axis contracts.

| Required fact | Current support | Exact limitation |
| --- | --- | --- |
| Exact STEP artifact ID/hash | Yes | `GeometrySourceReference` and `CanonicalGeometrySourceReference` retain `artifact_id`, SHA-256, source identity, and STEP format. `ImportedCadComponent` is byte-verified through `ArtifactStore`. |
| Imported geometry realization | Yes | M12-4 and canonical CAD resolve the complete exact STEP as `ImportedCadComponent`; it has no semantic feature/interface interpretation. |
| Rigid component placement | Yes | `CadRigidTransform` and `CanonicalPlacement` provide normalized quaternion rigid transforms, but are assembly placements, not named local frames attached to an imported source coordinate system. |
| Shaft/mount interface labels | Partial | `ComponentSpecificationSnapshot.interfaces`, `CanonicalComponentSpecification.interfaces`, and component-instance `interfaces` are only nonempty strings. They hold no geometry, frame, numeric, authority, or source binding. |
| Numeric component properties | Partial | `ComponentPropertySnapshot` and `CanonicalComponentProperty` retain scalar/range values, unit, availability, source identity, authority, applicability, conversion provenance, and hash. They cannot model vectors, frames, axes, faces, hole patterns, or a geometry-coordinate binding. |
| Property authority/availability | Yes, for scalar properties | Existing `ComponentPropertyAvailability` and `ComponentPropertyAuthority` are the M12 vocabulary to reuse. They do not identify whether a geometric semantic is an unresolved inference. |
| Geometry source/derived relation | No | A `GeometrySourceReference` selects one artifact only. No current model records raw-to-normalized/repaired/scaled artifact lineage or a scale-bearing coordinate transform. `CadRigidTransform` intentionally excludes scale. |
| Candidate identity/currentness | Yes, for current fields | Component specification hashes flow to `MechanicalDesignCandidate`; explicit consumed canonical paths drive `CandidateCurrentnessService`. There is no numeric interface payload for that mechanism to hash or currentness-check. |
| Promotion/reconstruction | Yes, for current fields | M12-5 copies component specifications, interfaces, selected geometry, placements, topology, and joint/M10 obligation to `CanonicalPhysicalMechanism`, then reconstructs it without candidate state. There is no numeric interface snapshot to project or reconstruct. |

Therefore A through H in the M13 request are not all representable today:

- A is supported.
- B through F are unsupported.
- G is supported only for the existing incomplete string-interface model.
- H preserves the existing incomplete model, not numeric interface semantics.

In particular, `JointPhysicalRealizationBinding.axis_frame_reference` and
`CanonicalJointPhysicalBinding.axis_frame_reference` are opaque strings. They
cannot prove a source-bound component frame or establish that a motor output axis
is the M10 axis.

## Goals

- Add one generic typed supplied-component numeric-interface snapshot family.
- Bind every interface definition to one exact `GeometrySourceReference` and its
  SHA-256 content identity.
- Represent deterministic right-handed local frames, rotational shaft interfaces,
  mounting faces, arbitrary hole patterns, and a bounded optional shaft profile.
- Preserve source facts, geometry observations, and human-confirmed
  interpretations without collapsing conflicting values.
- Reuse M12 component-property availability, authority, artifact, hashing,
  candidate, currentness, promotion, canonical reconstruction, CAD, and M10
  boundaries.
- Make only accepted, source-bound interface facts eligible for later deterministic
  placement or physical connection work.

## Non-Goals

M13-1 does not add timing-belt realization, a transmission topology, generated
shaft/hub/bearing/frame CAD, automatic mating/feature recognition, automatic
motor recognition, catalog search, component selection, bearing life, gear
strength, worm gearbox internals, tolerance/GD&T, manufacturing approval, M11
assembly FEA, a multi-joint candidate-to-M10 bridge, or Rotator V2 execution.

It also does not claim that a STEP artifact provides functional semantics,
automatically reconcile conflicting observations, establish a geometric
compatibility/tolerance result, or turn a supplied motor output into an M10 joint.

## Authority Model

### Placement Of Authority

The new data belongs in the existing component-specification snapshots:

```text
external drawing / measurement / geometry observation
  -> typed interface proposal or controlled ingestion
  -> ComponentSpecificationSnapshot.supplied_reference_frames
  -> ComponentSpecificationSnapshot.supplied_interface_definitions
  -> ComponentSpecificationSnapshot.geometry_derivation_transforms
  -> MechanicalDesignCandidate
  -> explicit M12 selection/promotion
  -> CanonicalComponentSpecification.supplied_reference_frames
  -> CanonicalComponentSpecification.supplied_interface_definitions
  -> CanonicalComponentSpecification.geometry_derivation_transforms
  -> CanonicalPhysicalMechanism in DesignState N+1
```

The candidate-side snapshot remains noncanonical as all M12 candidates do. It is
an immutable, content-addressed supplied-component input. Once promoted, the
same accepted interface semantics are copied into the existing canonical
component specification nested in `CanonicalPhysicalMechanism`; `DesignState`
remains the only canonical design authority. No `ComponentStore`,
`InterfaceStore`, `CatalogStore`, or second canonical state tree is introduced.

An interface is source/component defining, not evaluation defining. Selecting a
geometry source and accepted interface definition changes the component
specification hash and therefore the candidate hash. An interface change also
changes the canonical specification and canonical mechanism hashes after
promotion. CAD and M10 requests/results consume those changed identities but
remain derived records.

### Reused Authority Vocabulary

Every numeric fact reuses the existing M12 values:

- `ComponentPropertyAvailability`: `available`, `missing`, or `not_applicable`.
- `ComponentPropertyAuthority`: `manufacturer_datasheet`,
  `distributor_listing`, `measured_local`, `derived_normalization`, or
  `user_declared`.

No parallel property-authority taxonomy is added. The interface models add an
evidence-origin/status field only because the existing authority enum says who
backs a value, not whether an automatically recognized geometric semantic has
been accepted. This field is not a replacement authority enum.

### Proposed New Contracts

The names below are proposed new frozen, `extra="forbid"` models. They are
shared structural models used by both M12 snapshot forms; only the enclosing
candidate and canonical component specifications remain distinct as they are
today.

| Proposed contract | Purpose | Immediate consumer |
| --- | --- | --- |
| `GeometryArtifactIdentity` | Shared immutable projection of an exact geometry artifact/reference, including coordinate-system ID. It is not a second source of geometry authority. | Candidate/canonical geometry references and M13 shared models. |
| `SuppliedInterfaceEvidence` | One scalar, vector3, quaternion, or bounded text observation/fact with existing availability/authority/source semantics and an origin/status. | M13-1 validation and M13-2 placement compiler. |
| `SuppliedInterfaceFact` | A named engineering value with a transform role, ordered evidence alternatives, and one optional accepted evidence selection. | Frames, shaft/mount fields, M13-2. |
| `SuppliedComponentReferenceFrame` | A named right-handed frame in a specified geometry-source coordinate system. | M13-2 placement/coupling construction. |
| `RotationalShaftInterface` | An accepted/proposed supplied-side external rotational interface. | M13-2 coupling/hub placement and M13-3 correspondence input. |
| `MountingFaceInterface` and `MountingHole` | A mounting plane/frame and arbitrary supplied hole pattern. | M13-2 bracket/mount placement. |
| `GeometryDerivationTransform` | An explicit accepted/proposed source-artifact to derived-artifact coordinate relationship, including scale. | M13-1 rebinding and later M13-2 derived-geometry placement. |
| `InterfaceDerivationProvenance` | Immutable historical source-interface and optional source-frame snapshots plus transform/source-geometry/derived-geometry binding and closed fact derivation slots for a materialized result. It is not an active interface/frame registry. | M13-1 materialization, promotion, reconstruction. |
| `SuppliedComponentInterfaceDefinition` | Tagged union/root record bound to exact selected geometry, either direct or materialized. | Component specification, candidate identity, promotion, reconstruction. |

`FixedAttachmentInterface` is intentionally not introduced. Existing
`MechanicalConnection`/`CanonicalMechanicalConnection` already expresses a
connection once both endpoint interfaces are defined. M13-2 can add a generated
part-side interface only if a real consumer proves the existing connection labels
are insufficient.

### Fact Evidence And Resolution

`SuppliedInterfaceEvidence` contains:

- stable `evidence_id`;
- a typed value shape (`scalar`, `vector3`, `quaternion`, or `text`), transform
  role supplied by its enclosing fact, and value only when available;
- `canonical_unit`: required for `scalar`, `vector3`, and `quaternion`; exactly
  `None` for `text`;
- existing availability, authority, source identity, applicability context, and
  conversion provenance fields;
- `evidence_origin`: `source_document`, `geometry_inferred`, or
  `human_confirmed_interpretation`, or `derived_materialization`;
- source binding: an immutable source-document/content identity when available,
  plus an exact geometry-reference hash when the evidence was derived from or
  confirms geometry;
- optional ordered `basis_evidence_ids` for a confirmation that reconciles or
  confirms earlier evidence; and a deterministic evidence hash.

`SuppliedInterfaceFact` contains its stable `fact_id`, expected shape/unit,
`transform_role`, ordered unique evidence records, optional
`accepted_evidence_id`, and fact hash.
It permits multiple observations with different values. It never averages them,
uses an implicit priority, or chooses the numerically closest value.

For `text` facts, the fact's expected unit and every evidence `canonical_unit`
are `None`. For numeric facts, the expected canonical unit is required and every
evidence record carries that exact unit, including unavailable records. A text
designation such as `M4` or `M8x1.25` is therefore authority-bearing semantic
data, not a dimensionless quantity.

An interface that requires authoritative placement may consume only a fact whose
accepted evidence is `available` and whose origin is `source_document` or
`human_confirmed_interpretation`, or `derived_materialization` backed by complete
accepted materialization provenance. `geometry_inferred` evidence may be retained,
compared, and cited as a basis, but cannot be the accepted evidence for an
authoritative placement, CAD relation, or canonical physical connection.

The controlled confirmation transition is:

```text
geometry recognizer / FreeCAD inspection
  -> typed proposal evidence (geometry_inferred, exact geometry hash)
  -> independent human/source review
  -> new typed human_confirmed_interpretation evidence with explicit basis
  -> explicit accepted_evidence_id through the normal authority/promotion path
```

Changing `accepted_evidence_id` is a semantic change. A human does not edit an
inferred record in place or silently relabel it. If source-document and geometry
evidence conflict, both remain inspectable; a required placement is unresolved
until an accepted evidence selection exists. M13-1 performs no automatic conflict
resolution.

The exact availability/value invariant applies to every evidence shape:

- `available` requires exactly one value of the declared shape. Numeric values
  must be finite and retain their required declared canonical unit; `text` must
  be nonempty after trimming and has `canonical_unit = None`.
- `missing` and `not_applicable` require `value = None` and no fake zero, empty
  vector, empty text, or sentinel value. Numeric evidence retains its required
  declared canonical unit even when unavailable; text evidence retains
  `canonical_unit = None`. Neither is a sentinel value.

Availability, expected shape/unit, source metadata, evidence origin, confirmation
basis, and the explicit absence of a value are part of the evidence hash. Thus two
unavailable records with different authority/source/availability semantics remain
distinct without inventing an unavailable numeric value.

## Geometry Binding

Every `SuppliedComponentInterfaceDefinition` has a required
`geometry_reference_hash`. It is the self-hash of the enclosing selected
`GeometrySourceReference` (candidate) or `CanonicalGeometrySourceReference`
(canonical), never an artifact ID alone. The definition's geometry binding also
carries its `GeometryArtifactIdentity`; validation requires it to equal the
enclosing selected geometry reference's identity and hash exactly.

This deliberate redundant equality check makes source replacement fail closed at
the interface boundary. The reference is not an arbitrary STEP filesystem path.
It must resolve through the existing `ArtifactStore` and therefore use the same
project boundary, artifact type, byte rehash, and `ImportedCadComponent` trust
rules as M8/M12.

An exact interface snapshot is valid for its historical artifact even after a
later revision selects a different artifact. That is historical integrity, not
currentness. A runtime consumer may use it only when its exact geometry binding
matches the selected geometry. A source-to-derived transform can only be used by
the explicit materialization process described below; resolution never dynamically
reinterprets a source-bound interface against another artifact.

## Coordinate-System Semantics

### Geometry Coordinates And Ownership

All numeric geometry facts are expressed in the bound STEP model coordinate
system, in millimetres (`mm`) for points/lengths and unitless (`1`) for direction
vectors/quaternions. M13-1 chooses additive option A: both
`GeometrySourceReference` and `CanonicalGeometrySourceReference` gain
`coordinate_system_id: str | None = None`. The non-`None` M13 value is a stable
identifier for the coordinate system represented by the exact STEP artifact,
initially `step-model-coordinates@1`; it is not a manufacturer drawing frame or
an assembly-world placement.

`None` is the explicit legacy default, not an implied STEP coordinate system. A
legacy reference serializes/hashes exactly as it does today, omitting the new
field from its reference identity. This is necessary because existing canonical
geometry-reference and enclosing specification hashes are persisted and would
otherwise fail self-hash validation merely by loading them. M13 interface-bearing
component specifications use a new `@2` schema branch and require nonempty
`coordinate_system_id` on their selected STEP geometry. They include it in the
candidate geometry-source serialization, canonical geometry-reference self-hash,
component specification hashes, candidate hashes, and canonical mechanism hashes.
Changing a nonlegacy coordinate-system ID changes geometry/interface identity
because it changes coordinate interpretation. Promotion copies it exactly, and
fresh reconstruction verifies it as part of the selected geometry reference.

`GeometryArtifactIdentity` is the shared immutable value shape used by M13
structural models. It has exactly `artifact_id`, `artifact_hash`,
`source_identity`, `format`, `coordinate_system_id`, and `geometry_identity_hash`.
It is a validated projection made from either existing geometry-reference type;
it is not separately selected, stored as authority, or resolved independently.
The candidate and canonical geometry-reference models expose the same projection
and reference hash. This removes a cross-layer type dependency while preserving
one source of geometry authority.

No value can be reused against another artifact solely because part number,
source identity, filename, or nominal dimensions match.

### Frame Representation

`SuppliedComponentReferenceFrame` contains:

- `frame_id` unique within a component specification;
- `geometry_reference_hash` equal to the enclosing selected geometry reference;
- `origin`: a `vector3` `SuppliedInterfaceFact` in `mm`;
- `orientation`: a `quaternion` `SuppliedInterfaceFact` in `1`, ordered
  `(w, x, y, z)`; and
- deterministic frame hash.

Frames are owned by the enclosing component specification, not by individual
interfaces. Both `ComponentSpecificationSnapshot` and
`CanonicalComponentSpecification` gain:

```text
supplied_reference_frames: tuple[SuppliedComponentReferenceFrame, ...] = ()
```

`frame_id` is unique within that specification. Any shaft or mounting
`reference_frame_id` must resolve to exactly one frame in the same specification
and its geometry-reference hash must equal the interface binding. Dangling or
cross-specification references are invalid. Unused frames are intentionally
allowed: an accepted source datum can be retained for audit or a later generated
counterpart without inventing an interface immediately. They remain complete
semantic input and participate in specification/candidate/canonical hashes,
promotion projection, and fresh reconstruction.

### Frame Materialization

Materialization is geometry-bound and therefore cannot retain a source-bound
frame reference on a derived interface. When a direct source interface names a
`reference_frame_id`, the materialization contract includes the resolved source
frame and produces a derived frame with the same `frame_id`, bound to the derived
selected geometry. Its origin is transformed as `POINT_MM` and its orientation as
`ORIENTATION` through the same accepted `GeometryDerivationTransform` core used
for interface facts. The active derived component specification contains that
derived frame in `supplied_reference_frames` and the materialized interface in
`supplied_interface_definitions`; the materialized interface references that
active derived frame ID.

`InterfaceDerivationProvenance` therefore persists, when a source interface
references a frame, the historical `source_reference_frame_snapshot`, matching
`source_reference_frame_hash`, and matching `derived_reference_frame_id` /
`derived_reference_frame_hash`. The source frame snapshot is historical input
only, never an active derived frame or endpoint. A source interface without a
frame has all four frame-provenance fields `None` and produces no derived frame.

The materializer returns one immutable result containing the materialized
interface and optional derived frame. If multiple materialized interfaces in one
derived specification use the same source frame, the specification retains one
active frame when its `frame_id` and derived `frame_hash` agree. Same frame ID
with a different derived hash fails closed. No per-interface duplicate active
frame and no general frame graph is introduced.

The quaternion uses the same normalized, sign-canonical convention already used
by `CadRigidTransform` and `CanonicalPlacement`: it maps frame-local axes into
the bound geometry coordinate system; it is normalized; and its first component
whose absolute value exceeds `1e-12` is nonnegative. Its rotation matrix columns
are the local `+X`, `+Y`, and `+Z` axes in geometry coordinates. This is an
orthonormal, right-handed frame by construction. `+Y = +Z x +X` under that
convention.

Input quaternions with non-finite values or norm `<= 1e-12` are rejected. Input
is normalized/canonicalized before hash calculation, so quaternion sign variants
and positive scalar multiples represent the same orientation and hash equally.
Coordinates are finite JSON numbers. The implementation must reject a supplied
rotation matrix/basis rather than adding a second frame representation in M13-1.
An ingestion adapter may convert a checked right-handed basis into this
quaternion, preserving the source basis in evidence/provenance.

The current `CadRigidTransform` stays an assembly placement. It is reused only
for later composition of a resolved component-local frame with an assembly
placement; it does not become an authority container.

### Numeric Canonicalization

- Length coordinates, diameters, and engagement lengths use exact unit `mm`.
- Directions are finite nonzero `vector3` facts with unit `1`, normalized using
  the existing axis tolerance `1e-12` before hashing.
- Direction sign is meaningful and is never flipped for hash convenience; an
  outward shaft direction and its opposite are distinct semantics.
- Quaternions use the normalization/sign rule above.
- The implementation uses current canonical JSON serialization and SHA-256.
  It must not round or stringify numbers for identity. A future source-ingestion
  layer may apply a declared quantization policy, but M13-1 adds none.

## Geometry Normalization / Derived Geometry

The repository has no existing artifact-level source-to-derived geometry relation
that can represent a scale. `CadRigidTransform` is deliberately rigid and cannot
honestly encode the Rotator V2 source-to-normalized `1.25` scale. M13-1 therefore
requires `GeometryDerivationTransform` rather than hiding a normalization in an
importer, filename, or numeric interface.

The record contains:

- `source_geometry` and `derived_geometry` as `GeometryArtifactIdentity` values;
- their geometry-reference hashes and exact artifact IDs/SHA-256 values;
- three source/authority/evidence-bound similarity components using the existing
  fact/evidence vocabulary: `translation_fact` (`vector3`, `mm`,
  `DISPLACEMENT_MM`), `rotation_fact` (`quaternion`, `1`, `ORIENTATION`), and
  `uniform_scale_fact` (`scalar`, `1`, transform-authority role
  `UNIFORM_SCALE`);
- an explicit `GeometryDerivationUnitConversion` declaration;
- status `proposed` or `accepted`; and deterministic transform hash.

`UNIFORM_SCALE` is a small role in the transform-authority contract, not an
interface materialization role and not `LENGTH_MM`. The authority facts reuse
the existing availability, authority, source identity, evidence-origin,
source-document binding, confirmation-basis, selection, and hashing semantics.
The effective translation, rotation, and scale are obtained only from their
selected facts; there are no independent default/cached transform numbers. Thus
zero translation and identity rotation require explicit selected evidence just as
any nonidentity value does.

A transform may be structurally persisted as `proposed` or with inferred/
unselected component evidence. `require_authoritative_transform` permits
materialization only when status is `accepted`, all three component facts have
available selected `source_document` or `human_confirmed_interpretation`
evidence, and the unit-conversion declaration is present. Scale evidence alone
never authorizes translation or rotation. A human-confirmed component may cite
fact-local inferred evidence through the normal confirmation basis; no parallel
authority taxonomy is introduced.

The mapping is unambiguous. `SuppliedInterfaceFact.transform_role` is mandatory
for any fact that can appear in a materialized interface; its role, not merely its
shape or unit, selects this transform rule:

```text
POINT_MM:        p' = scale * R * p + translation_mm
LENGTH_MM:       L' = scale * L
DISPLACEMENT_MM: v' = scale * R * v
DIRECTION_UNIT:  d' = normalize(R * d)
ORIENTATION:     q' = q_R compose q
TEXT:            unchanged
```

Initial field roles are structural, not inferred from a generic scalar/vector
shape: frame origins, shaft axis points, shoulder locations, mounting-plane
points, and hole centers are `POINT_MM`; shaft diameter, usable engagement,
flat-across, D-flat start/effective length, hole diameter, pilot/boss diameter,
and axial shoulder offsets are `LENGTH_MM`; declared offset vectors are
`DISPLACEMENT_MM`; shaft/flat/hole/plane normals are `DIRECTION_UNIT`; frame
orientations are `ORIENTATION`; and thread designations/semantic labels are
`TEXT`. The initial interfaces do not require a displacement field, but the role
is defined now so a future typed offset cannot accidentally receive point
translation semantics.

Only uniform positive scale is supported initially. Nonuniform scale, shear, and
unexplained repair/deformation are rejected as unsupported, not approximated.
An apparent unit conversion must be represented explicitly by the scale and its
provenance. A repair, vendor revision, or user-derived STEP that is not proven by
an accepted `GeometryDerivationTransform` is a distinct geometry source; its
interface data is stale/unresolved for use with that geometry.

M13-1 chooses materialization, not a runtime derived-view. An accepted transform
may materialize a distinct derived `SuppliedComponentInterfaceDefinition` only
from a source interface whose needed facts already have accepted evidence. The
materialized definition binds exactly to the selected derived geometry and carries
`InterfaceDerivationProvenance` containing a durable direct
`source_interface_snapshot`, matching `source_interface_hash`, `transform_id` and
matching `transform_hash`, source/derived `GeometryArtifactIdentity` values and
their geometry-reference hashes, plus
`materialization_algorithm = supplied-interface-materialization@1`, plus the
optional source/derived frame provenance defined above. Its derived interface and
derived frame facts contain only deterministic transformed selected evidence and
cite the source evidence/hash through closed derivation slots with origin
`derived_materialization`; source observations remain inspectable through the
embedded historical source snapshots, not silently copied into a different
coordinate system.

The embedded source snapshot is **historical derivation input only**. It must be a
direct source-bound interface, validate independently, and match the provenance's
source geometry/hash. It is not appended to
`supplied_interface_definitions`, is not an active interface endpoint, cannot
be resolved by `PhysicalComponentInstance.interfaces`/`MechanicalConnection`,
M13-2, or M13-3. Endpoint strings resolve exclusively through the enclosing
specification's active `supplied_interface_definitions`; if the historical and
materialized snapshots share an `interface_id`, that string still resolves only
to the active materialized definition. The active interface registry is
exclusively the enclosing specification's `supplied_interface_definitions`, all
of which bind to that specification's selected geometry.

The materialized definition has its own interface/specification/candidate/canonical
hashes and is what CAD/M13-2 resolves. It does not mutate, replace, or make the
source artifact/interface identical to the derived artifact/interface. A proposed
transform, including the current Rotator V2 scale candidate, cannot materialize
an authoritative interface or satisfy a placement request.

Canonical reconstruction must byte-verify the selected geometry source for every
canonical component specification, every exact source/derived artifact named by
an accepted `GeometryDerivationTransform`, and every geometry identity referenced
by a materialized-interface provenance record. It must verify that all of these
identities agree with their enclosing definitions. This extends the existing
reconstruction check, which currently verifies only each
`CanonicalComponentSpecification.geometry_source`.

Fresh materialization verification is a deterministic integrity replay, not a CAD
operation. A shared `MaterializedInterfaceVerifier` must validate the embedded
source snapshot/hash, byte-verify source and derived geometry, resolve the exact
accepted transform by provenance ID/hash, verify all source/derived geometry
bindings, apply the role-aware transformation rules to the source interface and
optional source frame accepted facts, and construct the expected derived result.
The enclosing specification resolves the exact active derived frame by ID and
passes it to the pure verifier; the verifier performs no arbitrary registry
lookup. It compares the complete typed interface/frame semantics and self-hashes
with persisted active records. Its pure semantic replay runs during M13 model integrity
validation; its artifact-aware replay runs when a persisted candidate is freshly
resolved, during promotion readiness, and during canonical reconstruction. A
changed source snapshot/value, transform, geometry binding, derived fact, or
derived interface hash is `INTEGRITY_FAILURE`, never unresolved authority or an
engineering evaluation result. No CAD/M13-2/M13-3 runtime consumer performs this
replay.

## Initial Interface Types

`SuppliedComponentInterfaceDefinition` is a tagged union with exactly two M13-1
variants. Its `interface_id` is unique within the component specification and
must be listed in the existing `interfaces` string tuple for compatibility with
`PhysicalComponentInstance`, `MechanicalConnection`, and their canonical forms.
The string remains the graph endpoint identifier; the new typed definition gives
that identifier meaning.

Each direct interface must bind exactly to the enclosing selected geometry
reference. Each materialized interface must bind exactly to the enclosing selected
derived geometry reference and include matching `InterfaceDerivationProvenance`.
An interface cannot be both direct and materialized, and a materialized interface
cannot omit its source/derived linkage.

### Rotational Shaft Interface

`RotationalShaftInterface` contains:

- `interface_id` and exact geometry binding;
- optional `reference_frame_id` referring to the owned same-specification frame;
- `axis_point` (`vector3`, `mm`) and `axis_direction` (`vector3`, `1`);
- `nominal_shaft_diameter` (`scalar`, `mm`);
- `usable_axial_engagement_length` (`scalar`, `mm`);
- optional `shoulder_reference_plane` represented by point/normal facts; and
- optional bounded `shaft_profile`.

The initial profile values are `round`, `d_flat`, `keyway`, `spline`, `thread`,
and `other`. Only `d_flat` receives a small typed optional detail record:
flat-normal direction, flat-across dimension, start from shoulder, and effective
length. A thread may carry only an opaque nonempty designation and optional
engagement-length fact. Keyway/spline are labels with optional source-backed
detail facts; M13-1 defines no manufacturing dimensions, tolerances, torque
capacity, or fit calculation.

### Mounting Face Interface

`MountingFaceInterface` contains:

- `interface_id` and exact geometry binding;
- `face_reference_id`, a stable semantic reference selected by authority, not a
  FreeCAD face index or inferred topology token;
- required same-specification `reference_frame_id` whose `+Z` is the declared
  outward normal;
- `plane_point` and `outward_normal` facts consistent with that frame; and
- zero or more ordered `MountingHole` records plus an optional pilot/boss
  reference.

`MountingHole` contains `hole_id`, center point, axis direction, nominal diameter,
and optional thread designation. All are facts in the mounting interface's bound
geometry coordinate system. The model supports one hole, N holes, asymmetric
patterns, and arbitrary coordinates; there is no four-hole pattern type.

Hole thread designation is semantic text with explicit evidence; a measured
diameter near 4 mm does not establish M4. Missing thread depth/engagement stays
`missing` or absent and cannot be filled from STEP topology.

The optional pilot/boss reference is a point/axis/diameter fact group. It is a
reference geometry declaration only, not a fit or concentricity claim.

## Numeric Validation

The implementation must reject, before identity calculation or persistence:

- empty/whitespace IDs, duplicate interface/frame/hole/evidence/fact IDs, and
  dangling frame/evidence references;
- non-finite point, dimension, direction, quaternion, scale, or translation
  values;
- zero direction vectors, nonpositive shaft/hole/pilot diameter, nonpositive
  usable engagement length, or nonpositive transform scale;
- wrong shapes, wrong explicit units, or unavailable values selected as accepted;
- invalid quaternion norm, noncanonical frame quaternion after normalization, or
  a plane normal inconsistent with the mounting frame `+Z` within `1e-9` angular
  residual;
- an unaccepted/inferred evidence record used as required placement authority;
- a direct interface missing a selected-geometry binding, a materialized interface
  missing complete materialization provenance, or source/derived provenance that
  does not match its actual interface/geometry references;
- a shaft/mount/frame geometry reference that does not exactly match its
  enclosing selected geometry reference;
- duplicate hole centers/axes only when their complete semantic hole records are
  identical; duplicate IDs are always invalid. Coincident holes with distinct
  authoritative roles are accepted only if explicitly distinct IDs and evidence
  make that intention clear;
- malformed or cyclic confirmation basis references; and
- a geometry derivation that names equal source/derived references, mismatches
  artifact/hash fields, has nonuniform/unsupported parameters, or omits its
  authority/status.

Facts and interface definitions use deterministic ordering by their explicit IDs
for semantic serialization. Callers may provide a different order, but model
construction must canonicalize the ordered collections before hashing and reject
ties/duplicates. The current canonical JSON SHA-256 hashing contract is used for
all self-hashes; run IDs, timestamps, temporary paths, CAD handles, topology face
indices, provider runtime information, and artifact storage locations are not
semantic inputs.

## Source / Inference / Confirmation Semantics

Source-document facts and geometry observations are separate evidence records,
even if their normalized numeric values coincide. For example, an 8 mm drawing
shaft-diameter fact and an 8.01 mm STEP measurement carry different evidence
IDs, source identities, authority classes, and provenance. The same applies to a
drawing 28 x 40 mm pitch and an observed normalized-STEP pitch.

An ingestion boundary produces typed `SuppliedInterfaceEvidence` or a typed
proposal containing it. Valid inputs are an identified drawing/document,
controlled human measurement, or a bounded inspection output carrying exact
artifact binding. The ingestion service validates units, source identity, and
geometry binding; an agent may assist with extraction but may not author an
accepted interface snapshot directly. Arbitrary Markdown is not parsed by a
production resolver.

An inferred axis/plane/hole is valid only as `geometry_inferred` proposal
material. Human confirmation must create new confirmation evidence, record the
source/reviewer/confirmation identity through normal provenance, cite the inferred
basis, and be accepted through the normal authority/promotion flow. It cannot
silently alter the old observation or merely change its enum. The precise owner
of the acceptance transition is the existing domain owner/change workflow, not
FreeCAD, an agent, `ArtifactStore`, or a CAD compiler.

## Candidate Identity

`ComponentSpecificationSnapshot` gains an additive optional tuple:

```text
supplied_reference_frames: tuple[SuppliedComponentReferenceFrame, ...] = ()
supplied_interface_definitions: tuple[SuppliedComponentInterfaceDefinition, ...] = ()
geometry_derivation_transforms: tuple[GeometryDerivationTransform, ...] = ()
```

`CanonicalComponentSpecification` gains the equivalent three additive tuple
fields. Candidate and canonical validators require unique frame/interface/
transform IDs, same-specification frame resolution, and complete materialization
provenance. Their specification hashes include all three fields. A candidate
containing an interface
therefore changes identity when any accepted/proposed fact, evidence, accepted
selection, frame, geometry binding, transform, or interface semantics changes.
Changing an evidence source annotation, availability, authority class,
applicability, conversion provenance, or confirmation basis also changes the
interface/specification/candidate hash because it changes the engineering claim.
Changing only an external artifact storage path or run ID does not.

For materialized interfaces, the derived active frame and its frame provenance
are part of the same `@2` component-specification semantic payload. Changing any
translation/rotation/scale fact, accepted selection, authority, origin, source,
confirmation basis, unit-conversion declaration, source frame snapshot, derived
frame fact, or derived frame hash changes the transform/provenance/interface or
frame hash and therefore the specification, candidate, and canonical identity.

This deliberately retains unselected/proposed evidence in candidate identity.
Current M12 doctrine makes the complete immutable component-property snapshot,
including authority, availability, source identity, and conversion provenance,
candidate-defining; it has no separate audit-evidence set for a snapshot. An
unselected observation can expose a source conflict, alter confirmation basis, or
change the reviewable authority record. Excluding it would allow a candidate to
retain its identity while its auditable supplied-component claim changed. M13-1
therefore follows the existing snapshot doctrine rather than adding a second
evidence persistence/identity layer.

The candidate source binding must explicitly consume the canonical source path
for any interface definition that is read from `DesignState`. This reuses
`CandidateSourceReference` and its exact value hash; no interface-specific
currentness engine is introduced. If the component snapshot is an external
supplied input under the existing M12 model, its immutable interface/specification
hash and source/geometry evidence bindings provide its candidate identity, just as
current M12 external component-property snapshots do.

Candidate currentness is unchanged in category:

- integrity revalidates all nested hashes and exact artifact bindings;
- `CURRENT` requires unchanged consumed canonical interface paths, where such
  paths were consumed;
- `STALE_RELATIVE_TO_CURRENT_STATE` results when a consumed canonical interface
  path changed;
- `CURRENTNESS_UNAVAILABLE` remains operational;
- changed/missing/tampered STEP bytes are integrity failures, not a currentness
  state or engineering infeasibility.

## Currentness And Integrity

The following states remain distinct:

- **Integrity:** the stored snapshot, self-hashes, selected evidence, reference
  equality, and ArtifactStore bytes verify.
- **Semantic identity:** hashes identify the frozen interface/specification,
  candidate, canonical mechanism, requests, or result at their own layer.
- **Currentness:** an otherwise valid historical candidate or canonical derived
  result may be stale relative to the current revision because a consumed source
  path or promoted mechanism changed.
- **Evaluation status:** later compatibility, CAD, and M10 results have their own
  outcomes; an interface snapshot is not a pass/fail evaluation.

Replacing a source geometry artifact with a different SHA-256 requires a new
`GeometrySourceReference`, interface definition, component specification, and
candidate. Existing interface data remains historically verifiable against the
old artifact. Reuse against the new artifact fails closed unless an accepted
`GeometryDerivationTransform` materializes a new derived interface snapshot
bound to the new artifact. A same-ID artifact whose bytes no longer match is an
ArtifactStore integrity failure, not an implicit revision.

## Physical Mechanism Integration

The existing graph models remain the physical relationship layer:

```text
supplied ComponentSpecificationSnapshot
  + accepted RotationalShaftInterface / MountingFaceInterface
  -> PhysicalComponentInstance.interfaces (existing endpoint ID)
  -> MechanicalConnection
  -> candidate placement relation
  -> later CAD realization
```

`MechanicalConnection`, `CanonicalMechanicalConnection`, their connection kinds,
and their meaning flags remain unchanged in M13-1. A connection referencing
`output-shaft` or `mount-face` must resolve that string to exactly one accepted
numeric interface only when a downstream service needs numeric placement. A
connection alone remains non-geometric and does not assert coaxiality, mating,
thread engagement, or a physical fit.

M13-2 will consume the resolved supplied-side shaft/mount interface to derive
candidate-local/generated counterpart placement inputs. It must explicitly state
which facts it consumes and bind their hashes. It must not regenerate the supplied
component or convert it to a `CadPartProgram`.

## CAD Integration Boundary

`ImportedCadComponent` remains the representation of the exact supplied STEP
artifact. `CadPartProgram` remains generated geometry; `CadAssemblyProgram`
remains the derived rigid assembly. Numeric interface authority is separate typed
engineering state/snapshot data.

The minimum future consumption surface is a focused resolver, only if M13-2
needs it:

```text
resolve_supplied_component_interface(specification, interface_id, geometry_reference)
    -> validated accepted source-bound interface view
```

The resolver verifies the specification hash, interface ID, accepted required
facts, exact geometry reference, and ArtifactStore content identity supplied by
its caller. It rejects a source/derived geometry mismatch even when an accepted
transform exists; callers must first provide the separately materialized derived
interface snapshot. It does not inspect STEP topology to find a replacement
feature, parse Markdown, resolve conflicts, or solve an assembly mate.

Direct typed-model access is sufficient for pure graph validation. The resolver
is justified only as the common M13-2 CAD placement trust boundary, not as an API
for aesthetics.

## Kinematic Integration Boundary

M13-1 changes neither `RevoluteAxis`, `KinematicModel`, `RevoluteJointModel`,
M10 forward kinematics, nor `JointPhysicalRealizationBinding`. The new shaft
interface supplies a source-bound axis that a later service may explicitly relate
to a generated coupling, supported shaft, and then an M10 joint.

The M13-3 service must bind the resolved supplied shaft-interface fact hashes,
connection path, and installed placement relation to a particular
`JointPhysicalRealizationBinding`/M10 axis. It must prove the declared relation
(such as coaxiality) under its own bounded contract. A motor output shaft never
becomes the final supported rotator joint merely because both axes have matching
numbers. No M13-1 interface automatically creates or modifies an M10 joint.

## Promotion And Canonical Round Trip

`CanonicalComponentSpecification` gains the same additive tuple fields as the
candidate snapshot. `CandidatePromotionCompiler._canonical_specification` copies
only the complete typed interface definitions and derivation transforms, preserving
all evidence, accepted selections, geometry bindings, and hashes. The compiler
rejects a promotion if a required candidate interface definition lacks an
intentional promotion classification or if a promoted accepted definition cannot
be represented canonically.

The existing `PromotionClassification` is sufficient without a new enum because
its `source_value` accepts a SHA-256 string. It classifies each complete new
immutable record by its self-hash rather than attempting to force vectors,
quaternions, or nested evidence through its scalar/range union. The exact expected
identities and classifications are:

| Candidate record | Promotion classification | `source_value` |
| --- | --- | --- |
| `supplied_reference_frames/<frame_id>` | `ACCEPTED_PHYSICAL_FACT` | exact `frame_hash` |
| `supplied_interface_definitions/<interface_id>` (direct or materialized) | `ACCEPTED_PHYSICAL_FACT` | exact `interface_hash` |
| evidence records and accepted evidence selection | no independent classification; they are complete required fields inside the classified interface hash | n/a |
| `geometry_derivation_transforms/<transform_id>` | `CANONICAL_REDERIVATION_INPUT` | exact `transform_hash` |

`_expected_classifications` must add one identity per frame, interface, and
transform, scoped by the candidate component specification identity plus the
record ID. The existing geometry-source classification remains required for the
selected geometry reference. The compiler validates each nested hash, projects
the entire record byte-for-byte through typed models, and rejects missing,
unknown, substituted, or partial classifications/projections. `PROVENANCE_ONLY`
and `DO_NOT_PROMOTE` are invalid for these records because canonical interface
reconstruction requires their complete semantic content.

No new promotion category is required for frame derivation. The active derived
frame is classified as `ACCEPTED_PHYSICAL_FACT` by its exact `frame_hash`; its
source-frame snapshot and binding fields are nested in the classified materialized
interface/provenance hash. The complete transform, including translation,
rotation, scale, selections, evidence, and unit-conversion declaration, remains
one `CANONICAL_REDERIVATION_INPUT` classified by exact `transform_hash`.

`PromotableMechanismProjection`, `CanonicalPhysicalMechanism`, and normalized
canonical reconstruction include the extended component specifications through
their existing fields and hashes. No candidate object, candidate CAD realization,
agent output, Markdown document, or old parser state is needed after promotion.
The M12-5 reconstruction path additionally validates all accepted interface
bindings and required derivation artifacts through `ProjectArtifactResolver`.

Fresh reconstruction expectations are:

```text
fresh ProductionApplication
  -> DesignState N+1
  -> CanonicalPhysicalMechanism
  -> canonical ComponentSpecification with interface definitions
  -> byte-verified selected/derived STEP source(s)
  -> same interface/specification/mechanism semantics and hashes
```

Candidate evaluation, selection rationale, M13 proposal records, CAD/M10 requests,
execution provenance, run IDs, and temporary geometry remain historical or
derived records, never canonical interface authority.

## Persistence And ArtifactStore

Small semantic interfaces, frames, evidence, selected facts, and transforms are
serialized in existing typed component specifications. Exact STEP, drawing, or
other large source bytes remain in `ArtifactStore` where the current contract
requires stored bytes. The semantic records retain compact IDs/hashes and source
identities; they do not embed STEP bytes or create another persistence store.

The embedded `source_interface_snapshot` and optional
`source_reference_frame_snapshot` are persisted only inside
`InterfaceDerivationProvenance` on its materialized active interface. They are not
duplicated into a component-level collection, `DesignState` path, or a new store.
The active derived frame remains the one record in the component specification's
`supplied_reference_frames`; the embedded source frame is historical derivation
input only. This gives fresh reconstruction a durable, independently recomputable
derivation input without creating a second canonical interface authority tree.

When a drawing/source document is not an ArtifactStore artifact, its
`source_identity` and optional content hash remain explicit in evidence. A future
controlled document-ingestion workflow may publish it through `ArtifactStore`,
but M13-1 does not invent a document/catalog repository or require historical
external sources to be re-imported. A geometry-derived evidence record always
names the exact geometry reference hash.

## Backward Compatibility

The new component-specification fields are optional empty tuples. Existing M12-2
candidates, M12-3 realization templates, M12-4 candidate CAD/M10 evaluations,
M12-5 promotion/reconstruction, and M12-6 fixtures remain valid when no
numeric interface is required. Existing string interface IDs and imported-component
handling retain their semantics.

Only an M13-2/M13-3 operation that explicitly requires a resolved numeric
interface must reject a component lacking an accepted matching definition. It
must return the appropriate unresolved/authority failure rather than fabricate a
frame from a string name or geometry feature. It resolves only a definition bound
to its exact selected artifact; it never applies a transform at runtime.

Current serialization is Pydantic JSON with self-hashes and immutable state
snapshots. M13-1 needs a narrow compatibility branch because hash-bearing M12
models are persisted. `component-specification@1` and
`canonical-component-specification@1` parse/hash with the historical field set:
no M13 tuple fields and legacy `coordinate_system_id = None`. New
`component-specification@2` and `canonical-component-specification@2` carry the
three tuple fields and require explicit coordinate-system IDs wherever M13 uses
geometry. The validators calculate each version's declared payload shape; they do
not silently rewrite old hashes. The new interface-family models have their own
`@1` schema literals. This is the smallest required migration/serialization
behavior and adds no database migration or external store.

## Failure Semantics

- Missing accepted shaft/mount facts needed by a requested consumer are
  unresolved authority, not a zero/default geometry value.
- Inferred-only semantics are unresolved for authoritative placement.
- Source/derived geometry mismatch, stale binding, artifact substitution, malformed
  transform, or hash mismatch is integrity failure and fails closed.
- Conflicting observations without selected accepted evidence are unresolved; they
  are not averaged or silently selected.
- An unsupported transform (nonuniform scale, repair without accepted map) is
  unsupported/unresolved for use, not a rigid transform approximation.
- M13-1 itself produces no engineering feasibility, CAD, collision, M10, M11, or
  manufacturing result.

## Test Strategy

Future implementation tests, not included in this M13-1 task, must cover:

### Pure Model Validation

- valid frame, shaft, mounting face, one-hole, asymmetric N-hole, and D-flat
  examples;
- zero axis direction, nonfinite data, invalid quaternion, wrong units,
  nonpositive dimensions, duplicate IDs, and invalid thread/pilot records;
- dangling/cross-specification frame reference, unused accepted frame, frame/normal
  mismatch, geometry-reference mismatch, invalid scale, and confirmation-basis
  cycle rejection;
- available scalar/vector/quaternion/text values validate, while missing and
  not-applicable evidence rejects every value/sentinel form;
- text evidence requires `canonical_unit = None`, while scalar/vector/quaternion
  evidence requires its declared canonical unit even when unavailable.
- materialized mounting and optional shaft frames derive origin/orientation,
  bind derived geometry, and are active in the derived specification; source
  frame tamper, derived frame tamper, missing derived frame, and same-ID/different-
  hash shared-frame conflicts fail closed.

### Semantic Hashing

- deterministic ID ordering for frames/evidence/interfaces/holes;
- equivalent normalized direction and quaternion-sign inputs hash identically
  where specified;
- reversed axis direction, changed accepted evidence, geometry hash, source,
  availability, authority, value, hole, transform, or interface semantic changes
  the appropriate identity;
- run IDs, timestamps, runtime paths, and artifact locations are excluded.

### Geometry Binding And Authority

- a same-shaped/wrong-artifact interface cannot resolve;
- byte substitution fails integrity;
- raw-to-derived use requires an explicit accepted transform;
- legacy `@1` geometry/specification hash reload remains exact, while M13 `@2`
  rejects an absent coordinate-system ID;
- source document, geometry observation, and human-confirmed evidence remain
  separate; inferred-only evidence cannot satisfy an authoritative resolver;
- source-vs-observed conflicts remain explicit and fail closed until selection.

### Candidate, Promotion, And Reconstruction

- component interface data propagates into specification and candidate hashes;
- a consumed canonical interface-path change makes the candidate stale while an
  unrelated state revision remains current under existing M12 rules;
- candidate-to-canonical projection preserves every interface fact/evidence/frame/
  transform field and rejects partial projection;
- fresh canonical reconstruction works without candidate objects and verifies all
  named geometry artifacts; changed source geometry invalidates/rejects use.
- materialization creates a new derived-bound interface with source interface,
  transform, and source/derived geometry hashes; runtime resolution rejects a
  source-bound interface against that derived artifact.
- materialized provenance persists a direct source-interface snapshot that is not
  active/resolvable, and fresh reconstruction recomputes it before accepting the
  active interface;
- changed source-interface value, transform, derived interface value/hash, or
  source/derived geometry binding each fails materialization integrity.
- promotion and fresh reconstruction preserve/replay source-frame provenance and
  one deduplicated active derived frame for shared source-frame use.

### Derivation Transform

- independent role-aware checks prove the stated point, length, displacement,
  direction, orientation, and text formulas, including shaft/mount/hole/pilot and
  D-flat fields under a non-unit uniform scale;
- a scale transform cannot silently omit a length-bearing field or apply point
  translation to a displacement.
- accepted scale cannot authorize altered/unselected translation or rotation;
  translation/rotation evidence changes alter transform identity; explicit
  accepted identity translation/rotation is valid, while inferred-only
  translation/rotation is unresolved and cannot materialize.

### CAD And Consumer Boundaries

- imported multi-shape STEP remains a complete `ImportedCadComponent` while
  interface semantics remain separate;
- M13-2-facing resolution requires an accepted source-bound definition and never
  calls geometry recognition;
- a representative supplied gearmotor fixture contains source STEP, output shaft,
  and mount interface without any Rotator-specific production type.

## Rotator V2 Validation Example

The generic model can represent the 5840-31ZY example without placing its name or
axis names in production types:

```text
ComponentSpecificationSnapshot
  geometry_source = exact normalized STEP reference
  geometry_derivation_transforms = source STEP -> normalized STEP, scale 1.25,
      status proposed until confirmed
  supplied_interface_definitions =
    Reference frame "output-frame" in normalized STEP coordinates
    Rotational shaft "output-shaft"
      axis point/direction, nominal 8 mm source-document evidence,
      8.01 mm geometry observation, D-flat details, and accepted selection only
      after confirmation
    Mounting face "mount-face"
      declared outward frame/normal and four arbitrary MountingHole records,
      retaining source drawing and geometry observation evidence separately
```

The raw and normalized artifacts do not silently share the interface. The
normalized interface can be used only after it binds the normalized artifact
directly or after an accepted source-to-normalized `GeometryDerivationTransform`
materializes a distinct normalized-bound definition. The motor shaft is
an explicit supplied interface; later architecture must still establish any
coupling, supported-shaft, and final M10-axis relation.

## Remaining Capability Boundaries

After M13-1, MechCAD can represent authoritative supplied-side numeric interfaces
and resolve them against exact geometry. It still cannot generate a bracket/hub,
solve a mate, prove a coupling fit, select a component, recognize a feature,
model a belt, derive a physical joint from a motor shaft, bridge a multi-joint
candidate to M10, or approve manufacturing/structural behavior.

## Implementation Scope For M13-1

The implementation must remain limited to typed authority, validation, hashes,
currentness/integrity extension, candidate/canonical projection, and fresh
reconstruction. It must not compile CAD or create Rotator V2 candidates.

Likely new files:

- `src/mechcad_harness/models/geometry_identity.py` for the shared immutable
  `GeometryArtifactIdentity` projection and geometry-reference hash helpers;
- `src/mechcad_harness/models/supplied_component_interface.py` for the shared
  strict evidence/fact/transform-role, frame, interface, materialization, and
  derivation-transform models, plus the pure `MaterializedInterfaceVerifier`;
- focused unit tests, likely
  `tests/unit/test_m13_supplied_component_interfaces.py`,
  `tests/unit/test_m13_geometry_materialization.py`, and
  `tests/unit/test_m13_interface_promotion_roundtrip.py`.

Likely modified files:

- `src/mechcad_harness/candidates/models.py` to add
  `GeometrySourceReference.coordinate_system_id` and `reference_hash`, plus
  optional `supplied_reference_frames`, `supplied_interface_definitions`, and
  `geometry_derivation_transforms` to `ComponentSpecificationSnapshot`, with
  explicit `component-specification@1` legacy and `@2` M13 hash branches;
- `src/mechcad_harness/models/physical_mechanism.py` to add
  `CanonicalGeometrySourceReference.coordinate_system_id` and the equivalent
  three optional fields to `CanonicalComponentSpecification`, with equivalent
  `canonical-component-specification@1` legacy and `@2` M13 hash branches;
- `src/mechcad_harness/candidates/promotion.py` and
  `src/mechcad_harness/candidates/promotion_models.py` for complete projection,
  exact nested-hash classification, source/derived artifact verification, and a
  `candidate-canonical-mapping@2` mapping-schema version. Existing interface-free
  M12 requests retain `candidate-canonical-mapping@1`; M13 interface-bearing
  requests require `@2`, so the policy verifier accepts each version only for
  its truthful payload shape;
- `src/mechcad_harness/candidates/canonical_mechanism.py` to byte-verify every
  selected/interface/materialization/accepted-transform geometry artifact during
  fresh reconstruction and invoke materialization integrity replay;
- `src/mechcad_harness/candidates/services.py` only for
  `CandidatePublicationService.resolve` to invoke the artifact-aware replay on a
  freshly persisted candidate; `CandidateCurrentnessService` remains unchanged;
- `src/mechcad_harness/models/__init__.py` and
  `src/mechcad_harness/candidates/__init__.py` only for needed public exports.

Existing contracts reused without replacement:

- `GeometrySourceReference`, `CanonicalGeometrySourceReference`,
  `ImportedCadComponent`, `ArtifactStore`, and `ProjectArtifactResolver`;
- `ComponentPropertyAvailability`, `ComponentPropertyAuthority`, and their
  canonical counterparts;
- canonical JSON hashing, candidate currentness/integrity, M12 promotion,
  canonical reconstruction, `CadRigidTransform`, physical connection models, and
  `JointPhysicalRealizationBinding`.

`CadRigidTransform`, candidate CAD realization, canonical CAD realization, M10,
ownership configuration, dependency configuration, and `DesignState` require no
M13-1 behavior change. Candidate/currentness services consume the expanded
specification hashes through their existing validation; only a caller that binds
a top-level canonical interface path needs the existing explicit
`CandidateSourceReference` mechanism.

No ownership/dependency configuration change is required for the first additive
model work because promoted interfaces remain within the existing
`/physical_mechanisms/*` ownership and invalidation family. A later top-level
canonical supplied-component authority path, if independently justified, would
need its own focused architecture decision rather than being introduced here.

## Acceptance Criteria

M13-1 implementation is complete only when typed production data can prove:

```text
exact supplied STEP artifact H
  + explicit source-bound local frame F
  + accepted output shaft interface S
  + accepted mounting interface M
  -> deterministic validated interface snapshot
```

and when a fresh application reconstructs the exact same canonical interface
semantics from persisted `DesignState` and byte-verified artifacts without
Markdown parsing, geometry guessing, candidate memory, or hidden defaults.

It must also prove that a changed bound artifact fails closed or invalidates the
interface for current use unless an explicit accepted compatible derivation
transform materializes a new derived interface snapshot bound to the selected
derived artifact. The implementation must preserve existing M12
candidates with no numeric interface definitions and must not alter M10 or add
M13-2/M13-3 behavior.

## Specification Self-Review

This specification was reviewed for Rotator/5840 leakage, a parallel authority
or persistence system, STEP-as-semantic-authority, silent inference promotion,
hidden scale correction, run-ID identity leakage, candidate authority after
promotion, M13-2/M13-3/CAD/timing-belt/M11 scope creep, and unnecessary
migration machinery.

The selected model uses only generic shaft and mounting concepts, reuses the
existing M12 property authority vocabulary and stores evidence-origin status
separately, keeps all geometry semantics explicitly source-bound, uses
`ArtifactStore`, preserves candidate-to-canonical reconstruction, and confines
new execution behavior to future consumers.

This reconciliation additionally rejects dangling or cross-specification frame
references, a coordinate-system field without a geometry-reference owner,
candidate/canonical geometry-reference type coupling, dynamic source-to-derived
runtime reinterpretation, unavailable sentinel values, untyped thread text,
shape-based scale inference, partial promotion classification, and partial
candidate-to-canonical projection.

The final materialization review also rejects a hash-only/unpersisted source
interface, unresolvable derivation ancestry, an embedded historical snapshot
acting as an active interface registry, trust in a materialized payload without
fresh role-aware recomputation, and a text unit treated as dimensionless numeric
data.
