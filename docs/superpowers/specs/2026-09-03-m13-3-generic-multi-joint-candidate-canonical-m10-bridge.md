# M13-3 Generic Multi-Joint Candidate/Canonical M10 Bridge

## Status

Architecture and specification reconciliation only. This document authorizes no
production or test change, implementation plan, M10 v2 redesign, M11 work,
M13-4 work, Rotator V2 work, commit, tag, push, or release.

**Disposition: `READY_FOR_IMPLEMENTATION_PLANNING`.** The former
`M13_3_BLOCKED_BY_RIGID_BODY_MODEL_GAP` is resolved by accepted
`M13_3P_GENERIC_M10_RIGID_BODY_CONSTITUENT_GROUP_VERIFIED`. M13-3 still needs
additive physical-body and physical-joint authority, but those are bounded
M13-3 work, not a prerequisite or a generic M10 gap.

## Problem

M13-1 and M13-2 establish source-bound interface/frame and placement authority.
M13-3 must lower authoritative candidate physical mechanism semantics into the
existing generic M10 v2 body/joint/pair surface, execute M10-3 v2 and optionally
M10-4 v2, bind selection to that exact bridge, promote physical facts only, and
freshly rebuild the canonical bridge without candidate analysis objects.

```text
candidate physical mechanism + physical body/joint semantics + interface/frame
authority + semantic placements + candidate CAD mapping + complete pair inventory
  -> deterministic physical-to-M10 v2 bridge
  -> existing M10-3 v2 / optional M10-4 v2
  -> selected candidate bridge -> ChangeProposal -> ChangeSet -> ChangeEngine
  -> canonical physical semantics -> fresh canonical CAD -> fresh v2 bridge
  -> fresh canonical M10 verification
```

## Repository Capability Audit

| Contract | Verified current implementation | M13-3 consequence |
| --- | --- | --- |
| M10 v2 bodies | `KinematicRigidBody` and `KinematicRigidBodyMember` carry complete CAD membership, explicit reference member and hash-bound full-precision offsets. | Consume as derived analysis records only. |
| M10 v2 joints | `RevoluteJointModelV2` has body endpoints and parent body-reference-local axis. | Lower physical joints directly into v2 joints. |
| M10 v2 model/FK | `KinematicModelV2` sorts bodies/joints; existing `MultiJointKinematicsService` evaluates body trees and projects all members. | No new FK, grouping, or transform engine. |
| Transform agreement | `rigid_transform_agrees(..., "rigid-transform-agreement@1.0")` is the single policy. | Use only this predicate for bridge pose equivalence. |
| M10-3 v2 | `MultiJointCollisionSweepRequestV2` accepts a `KinematicModelV2` and `ExactConstituentPair` scope; neutral v2 results identify concrete constituents. | Use for candidate/canonical discrete execution. |
| M10-4 v2 | `MultiJointContinuousPathRequestV2` uses the same pair scope and `body-member-reach-bound-plumbing@2.0`; neutral witnesses/results reload. | Optional focused explicit-path regression only. |
| Trusted M10 v2 boundary | `revalidate_v2_kinematic_model` reconstructs body/member/joint records and verifies versions and hashes at FK, requests, providers, parsers, reach, and application APIs. | The bridge must never bypass that boundary. |
| Candidate physical graph | `PhysicalMechanismRealization@1` owns components/connections but no physical body group or complete revolute semantics. | Add M13-3 physical records. |
| Canonical physical graph | `CanonicalPhysicalMechanism@1/@2` owns components, placements, connections, old snapshots, obligations, and M13-2 derivations. | Add projected M13-3 records with an explicit `@3` branch. |
| Candidate/canonical CAD maps | `CandidateCadRealization` and `CanonicalCadRealization` map every physical instance to exactly one concrete CAD instance and bind semantic placements. | They provide all physical-to-CAD correspondence and home placements. |
| M12 M10 adapter | `CandidateM10Binding`, `CandidateM10EvaluationScope`, and `CandidateM10EvaluationRequest` are one-output, v1, directional-partition records. | Preserve unchanged; do not overload. |

Representative production and adversarial M13-3P tests establish the six-member
body hierarchy, articulated/articulated `A2/B1` pairs, v2 evidence/provenance
reload, stale `body_hash` rejection, forged nested schema rejection before
providers/extents, and v1 literal compatibility.

## M13-3P Prerequisite Resolution

The prior spec correctly found that the old instance-endpoint M10 model had one
constituent per topology node. That historical explanation remains useful, but
it is now a **prerequisite gap resolved by M13-3P**, not current behavior.

`KinematicModelV2` requires every source CAD constituent occur exactly once in
one `KinematicRigidBody`; each body has a reference member and explicit member
offsets. `RevoluteJointModelV2` connects bodies. FK computes body poses, then
projects each pose to its concrete CAD members. M10-3/M10-4 v2 accept arbitrary
cross-body concrete pairs through `ExactConstituentPair`. `OUTPUT_RIGID` and
`output_transform_group` remain legacy M12 adapter metadata and are neither
generic M10 grouping nor physical authority.

## Goals

- Add the smallest explicit physical rigid-body and revolute-joint semantics.
- Compile those semantics deterministically to existing M10 v2 records.
- Preserve complete concrete constituent pair classification through candidate,
  selection, promotion, canonical reconstruction, and fresh verification.
- Reuse M13-1/M13-2 authority gates and M13-3P/M10 execution contracts.

## Non-Goals

No new M10 representation, FK, collision, reach-bound, or proof mathematics; no
joint recognition, body discovery, CAD inference, compound geometry, loops, IK,
dynamics, planning, synthesis, FEA, manufacturing approval, M13-4 capstone, or
Rotator-specific name/behavior.

## Existing Physical Mechanism Contracts

`PhysicalMechanismRealization` owns candidate physical components and endpointed
`MechanicalConnection` records. `CanonicalPhysicalMechanism` owns their
canonical projection, accepted placement facts, connections, and M13-2 canonical
placement derivations. Candidate/canonical CAD realization mappings are the sole
physical-instance-to-concrete-CAD correspondence. Existing
`JointPhysicalRealizationBinding` and `CanonicalJointPhysicalBinding` are
legacy realization/lowered snapshots, not owners of complete physical joint
semantics. They remain valid for M12 and are not reused by this bridge.

## Existing M10 V2 Contracts

M13-3 consumes `KinematicRigidBody`, `KinematicRigidBodyMember`,
`KinematicModelV2`, `RevoluteJointModelV2`, `ExactConstituentPair`,
`MultiJointCollisionSweepRequestV2`, `MultiJointContinuousPathRequestV2`,
M10-3 v2 result records, M10-4 v2 result/witness records,
`rigid-transform-agreement@1.0`, and
`body-member-reach-bound-plumbing@2.0`.

M13-3P records are derived M10 analysis structures. They are not physical facts,
must not be promoted, and cannot substitute for M13-3 physical authority.

## Physical Rigid-Body Semantic Owner

**Disposition: `M13_3_ADDITIVE_PHYSICAL_RIGID_BODY_RECORD_REQUIRED`.** No
current physical record truthfully says several physical component instances move
as one rigid body. CAD contact, coincident placement, CAD/STEP hierarchy,
arbitrary connection traversal, `KinematicRigidBody`, and `OUTPUT_RIGID` are not
physical ownership sources.

Add `PhysicalRigidBodyBinding` to `PhysicalMechanismRealization@2` and
`CanonicalPhysicalRigidBodyBinding` to `CanonicalPhysicalMechanism@3`:

- `physical_body_id`: stable nonblank semantic identity, retained unchanged on
  candidate-to-canonical projection.
- `member_physical_instance_ids`: explicit canonicalized nonempty member set.
- `reference_physical_instance_id`: explicit member designated as the semantic
  body reference.
- `binding_hash`: hashes the complete record.

Every physical instance represented by the bridge CAD realization belongs to
exactly one physical rigid body. The record contains no CAD ID, transform,
inferred fixed relation, or M10 object.

`PhysicalMechanismRealization@2` and `CanonicalPhysicalMechanism@3` each carry
`kinematic_root_physical_body_id` and `kinematic_root_binding_hash`. The frozen
pure helper `physical_kinematic_root_hash(kinematic_root_physical_body_id)`
hashes exactly this canonical payload:

```text
{
  "schema_version": "physical-kinematic-root@1",
  "kinematic_root_physical_body_id": <nonblank physical body ID>
}
```

`kinematic_root_binding_hash` must equal that helper result. It is the complete
physical root fact: it contains no CAD mapping, M10 body/model, bridge, pair
inventory, request, result, or execution data. The bridge later references this
physical root hash; it never defines the root. The root fields are physical
mechanism semantics, not bridge-runtime defaults.

## Physical Revolute-Joint Semantic Owner

No existing type owns complete physical revolute semantics. Add
`PhysicalRevoluteJointBinding` to `PhysicalMechanismRealization@2` and
`CanonicalPhysicalRevoluteJointBinding` to `CanonicalPhysicalMechanism@3`:

- stable `physical_joint_id`;
- `parent_physical_body_id`, `child_physical_body_id`, and one `connection_id`;
- exact parent/child endpoint physical-instance/interface identities;
- one discriminated axis source containing source physical instance, source kind,
  interface/frame ID, self-hash, and geometry/specification binding;
- explicit `axis_owner_endpoint` and `axis_sign` (`+1` or `-1`);
- `motion_mode`: `BOUNDED` with both finite limits or `CONTINUOUS` only;
- required `zero_reference_semantics: Literal["accepted-semantic-home@1"]`; and
- a complete binding hash.

These records are physical authority. They do not contain M10 axes, CAD IDs,
rest transforms, output groups, or an M10 model. A binding lowers to exactly one
`RevoluteJointModelV2`; two bindings never collapse to one joint.

## Connection Correspondence

Each physical revolute binding must resolve one existing
`MechanicalConnection`/`CanonicalMechanicalConnection` with kind
`ROTATIONAL_DRIVE` and meaning `KINEMATIC_REALIZATION_INTENT`. Its two stored
endpoint instance/interface pairs must exactly equal the binding’s declared
parent/child endpoints under the binding’s explicit direction; tuple order does
not supply direction. `FIXED_ATTACHMENT`, `MOTOR_MOUNT`, `BEARING_SUPPORT`,
`GEAR_MESH`, `COUPLING`, `STRUCTURAL_SUPPORT_DECLARATION`, and every connection
without that exact intent reject as M13-3 revolute joints. Connections never
become a degree of freedom merely by existing.

## Physical Body Membership

`PhysicalRigidBodyBinding`, not a connection kind, owns membership. Fixed
connections may provide physical context but do not derive membership.

## Physical Pair-Classification Authority

**Disposition: `M13_3_DURABLE_PHYSICAL_PAIR_CLASSIFICATION_AUTHORITY_REQUIRED`.**
`MultiJointCollisionPairInventory@1` is a derived CAD/M10 bridge artifact and
must not be promoted. It cannot be the semantic source for fresh canonical
reconstruction. M13-3 therefore adds `PhysicalPairClassificationBinding` to
`PhysicalMechanismRealization@2` in canonical field
`physical_pair_classification_bindings`, and
`CanonicalPhysicalPairClassificationBinding` to
`CanonicalPhysicalMechanism@3` in its identically named canonical field. Both
versioned mechanism serializers persist the canonically sorted tuple and include
it in their respective mechanism hash payloads. These records are accepted
analysis/policy semantics associated with the physical mechanism. They are not
CAD records, M10 records, collision measurements, or physical geometry facts.

`PhysicalPairClassificationBinding@1` contains exactly:

- `schema_version: Literal["physical-pair-classification-binding@1"]`;
- `first_physical_instance_id` and `second_physical_instance_id`;
- `classification`, using the existing frozen five-value
  `CandidateM10PairClassification` meanings and wire values;
- `exclusion_reason`; and
- `binding_hash`.

`CanonicalPhysicalPairClassificationBinding@1` has schema version
`canonical-physical-pair-classification-binding@1` and the same fields and
reason contract, with projected canonical physical IDs. Its `binding_hash` is
computed independently from its canonical-ID payload.

The implementation may expose a neutral M13 alias for the existing enum where
package import direction requires it, but it must not create new classification
meanings or alter historical enum wire values. Pair identity is unordered: after
validating nonblank, distinct IDs, bindings canonicalize
`first_physical_instance_id < second_physical_instance_id` lexically. The hash
payload contains exactly schema version, the canonical physical pair,
classification, and exclusion reason. It contains no CAD ID/realization hash,
M10 model/request/result, `ExactConstituentPair`, inventory, or bridge hash.

For `CHECK_CLEARANCE`, `exclusion_reason` is absent. For every other
classification it is required and nonblank. A reason change changes the binding
identity. Bindings are canonically sorted by their physical pair, caller tuple
order is non-semantic, and duplicate unordered pairs reject.

The complete physical universe is exactly the M13-3 finalized universe:

```text
P = physical instances in the exact bridge CAD realization mappings
  == physical instances in all explicit PhysicalRigidBodyBinding members
```

`expected_physical_pair_universe` is every lexical unordered pair of distinct
IDs in `P`. The binding set must contain exactly one binding for each pair;
omitted, duplicate, self, unknown, and extra pairs reject. There is no default
classification, including no implicit `CHECK_CLEARANCE` fallback. Define
`physical_pair_classification_set_hash` as the canonical hash over the sorted
semantic binding hashes alone.

Physical body authority constrains but does not replace pair-policy authority.
Every pair whose members share a `PhysicalRigidBodyBinding` must explicitly be
`SAME_RIGID_GROUP_EXCLUDED`; that classification is invalid for every cross-body
pair. The full explicit set remains durable and replayable even where this
consistency rule determines the only valid classification.

## Physical/CAD Universe Contract

M13-3 does not create a subset or projected `CadAssemblyProgram`. The M10 v2
source assembly is exactly the complete `CandidateCadRealization.assembly` or
fresh `CanonicalCadRealization.assembly` consumed by the bridge. Repository
validation already requires each realization’s CAD mappings to cover exactly its
assembly instances one-to-one; M13-3 additionally requires their mapped physical
instance IDs to equal the complete `PhysicalRigidBodyBinding` member universe.

Therefore one finalized physical universe and its one-to-one mapped CAD universe
are used throughout:

```text
P = physical instances in the exact CAD realization mappings
  == physical instances in all explicit physical body members

mapped_cad_ids(P)
  == concrete CAD instances in that realization assembly
  == KinematicModelV2 body-member instances
  == MultiJointCollisionPairInventory@1.complete_concrete_instance_ids
```

Each physical instance maps to exactly one CAD instance and exactly one physical
body; each CAD instance then occurs in exactly one `KinematicRigidBody`. Reject
before `KinematicModelV2` construction a mapped physical instance with no body,
a body member with no mapping, mapping outside the body universe, duplicate
physical membership, duplicate CAD mapping, an extra CAD constituent, or an
omitted CAD constituent. The compiler must not synthesize an implicit fixed,
ungrouped, or singleton fallback body.

## Body Reference Semantics

Reference selection is explicit: `reference_physical_instance_id`. It must be a
member and projects to the candidate/canonical CAD mapping’s corresponding
`reference_member_instance_id`. Caller tuple order, CAD ID sort order, FreeCAD
order, and geometry may not choose it. M10 `body_id` equals `physical_body_id`:
both are stable analysis/physical semantic identifiers, have no CAD namespace
meaning, and remain stable across promotion. Candidate/canonical component and
CAD IDs are projected separately.

## Member Offset Derivation

Offsets are derived bridge data, never physical authority or promoted facts. For
each physical body member, derive full-precision:

```text
reference_to_member_home = inverse(T_world_reference_semantic_home)
                           * T_world_member_semantic_home
```

Candidate poses come from accepted candidate semantic placements, including
M13-2 generated placement replay. Canonical poses come from `CanonicalPlacement`
and `CanonicalGeneratedPlacementDerivation` replay. The compiler emits one
`KinematicRigidBodyMember` per mapped CAD member and literal identity for the
reference member. M10 v2 validates each offset against the source assembly using
`rigid-transform-agreement@1.0`; no CAD geometry measurement is used.

## Axis / Pivot Authority

Only these exact active semantic sources are initially authorized:

- M13-1 `RotationalShaftInterface.axis_point` and `.axis_direction` after
  `require_authoritatively_consumable_interface` and exact active definition,
  geometry, evidence, frame, and source-physical-instance verification.
- M13-1 `SuppliedComponentReferenceFrame.origin` and local +Z derived from its
  accepted orientation under the same authoritative-consumption gate.
- M13-2 `GeneratedRotationalInterface.axis_point` and `.axis_direction`, resolved
  by exact generated interface ID/hash and generated-specification validation.
- M13-2 `GeneratedReferenceFrame.origin` and local +Z derived from its
  hash-verified orientation.

The pivot is the authorized axis point/frame origin. Bbox axes, STEP cylinders,
FreeCAD faces/origins, inferred geometry, proposed/unresolved supplied facts, or
hash-mismatched generated records reject before lowering.

## Coordinate-Space Lowering

`RevoluteJointModelV2.axis_origin` and `.axis_direction` are in the **parent
body reference-member local frame**, not parent instance local, world, or child
local. One shared pure lowerer is used by candidate and canonical adapters:

```text
validated source-local axis point/direction
  -> source physical instance semantic home placement -> world point/direction
  -> inverse(parent reference semantic home placement)
  -> parent body-reference-local point/direction -> RevoluteJointModelV2
```

Use existing `CadRigidTransform`, `transform_apply`, `transform_inverse`,
`transform_compose`, and existing quaternion helpers. A direction is transformed
by transforming its point and point-plus-unit-direction, subtracting, then
normalizing. Apply `axis_sign` only after source resolution. The lowerer adds no
epsilon; all candidate/canonical pose agreement calls cite
`rigid-transform-agreement@1.0` (its frozen 1e-9 mm, 1e-7 rad,
sign-invariant-quaternion semantics).

## Reference / Zero Configuration

The only M13-3 zero-reference semantic is required literal
`accepted-semantic-home@1`. Omission or any other value rejects. It means q=0 is
the accepted candidate semantic placements or their projected canonical semantic
placements, including replayed `CanonicalGeneratedPlacementDerivation`; it is not
a CAD viewer/current pose. The same placements derive body reference poses, member
offsets, and parent/child body home relations. No additional numeric zero offset,
named-home registry, M10 rest transform, or caller-selected zero exists.

For an all-zero keyed `JointConfiguration`, M10 v2 q=0 must agree with those same
semantic CAD home poses under `rigid-transform-agreement@1.0`. Candidate and
canonical q=0 semantics are compared after ID projection with that same predicate.
Alternate homes, calibrated offsets, encoder-zero definitions, and arbitrary named
reference configurations are out of scope; they require a future versioned
physical-joint zero-reference contract.

## Root / Parent / Child Semantics

M10 v2 supports forests, but M13-3 accepts exactly one explicit
`kinematic_root_physical_body_id` physical mechanism fact. A physical revolute
binding direction names parent and child. Every non-root body has exactly one
incoming binding. Reject unknown bodies, root-as-child, self-edge, missing root,
multiple articulated parents, cycles, disconnected required body, and ambiguous
direction. Deterministic joint sorting is by emitted joint ID; any UI/vector
adapter publishes that ordered ID tuple and immediately converts to keyed M10
configurations/paths.

## Topology Validation

Before creating a M10 model, validate unique physical bodies/joints, full body
membership, body/reference validity, connection existence and exact endpoints,
single root/reachability, one parent per non-root, acyclicity, and a one-to-one
physical-joint-to-M10-joint correspondence. M10 v2 then repeats its independent
strict body topology validation. Neither validator replaces the other.

## Limits / Continuous / Multi-Turn Semantics

`BOUNDED` lowers both physical finite limits exactly to `min_angle_deg` and
`max_angle_deg`; `CONTINUOUS` lowers both to `None`. Missing, one-sided,
nonfinite, or unselected limits reject. 0..1080 remains 0..1080; it is not
wrapped to 0..360 or -180..180. `physical_joint_id` is stable authority and emits
the same deterministic v2 `joint_id`; it is never a BFS index, tuple position,
CAD name, or runtime ID. Continuous and raw multi-turn commands remain distinct
keyed configuration/path values.

## Candidate CAD Correspondence

The compiler reconstructs and validates `CandidateCadRealization`, then requires
that its complete mapping/assembly set satisfies the Physical/CAD Universe
Contract and that each mapping placement agrees with the candidate semantic
placement used for lowering. The candidate physical-to-CAD mapping is bridge
input and identity, not physical body identity. Canonical lowering later requires
its own fresh complete canonical map.

## KinematicModelV2 Compilation

Add one pure `PhysicalToM10V2BridgeCompiler` with thin candidate/canonical
adapters. Given validated physical semantics, semantic placements, CAD mappings,
the exact realization assembly, and declared pair classifications, it first
emits/validates:

- `KinematicModelV2` containing `KinematicRigidBody`/member offsets and
  `RevoluteJointModelV2` records;
- immutable body, member, joint, and ordered-joint-ID projections;
- the M10 model, complete inventory, and exact-scope hashes; and
- provenance naming the M13-1/M13-2 source records and placement identities.

It then derives `physical_to_m10_bridge_hash` from those finalized inputs. This
one-way ordering prevents an inventory/bridge hash cycle. It does not run M10,
inspect CAD geometry for authority, choose membership/limits, or invent
connections. At every request/execution boundary it passes the result through
M10’s strict v2 reconstruction/revalidation path.

## Exact Pair Inventory Projection

M13-3 adds `MultiJointCollisionPairInventory@1` and
`MultiJointCollisionPairEntry@1`, rather than reusing M12’s one-output
`CandidateCollisionPairInventory` container. It reuses the existing
`CandidateM10PairClassification` enum without adding meanings. Its exhaustive
initial allowed set is exactly `CHECK_CLEARANCE`, `INTENDED_CONTACT_EXCLUDED`,
`SAME_RIGID_GROUP_EXCLUDED`, `UNMODELED_MOTION_OUT_OF_SCOPE`, and
`OTHER_EXPLICIT_OUT_OF_SCOPE`.

An entry contains a canonical lexical unordered concrete CAD pair
`(first_instance_id, second_instance_id)`, its classification, and
`exclusion_reason`. IDs are nonblank, distinct, and strictly ordered. For
`CHECK_CLEARANCE`, `exclusion_reason` is absent. For every other classification,
it is required and nonblank. M13-3 intentionally omits and forbids the legacy
M12 `requires_home_exact_check`: a multi-joint v2 out-of-scope pair is not a
home-only check and never enters this bridge’s M10 exact scope. The flag remains
unchanged in M12’s legacy inventory only.

The inventory contains `schema_version`, `physical_mechanism_hash`, canonical
physical body binding hashes, `cad_realization_hash`, `m10_model_hash`, canonical
`complete_concrete_instance_ids`, canonical
`expected_pair_universe`, canonical entries, and `inventory_hash`. The concrete
universe is derived only as every lexical unordered pair of distinct IDs in the
exact candidate `CandidateCadRealization` or canonical
`CanonicalCadRealization`. The semantic classification source is never inferred:
for each durable physical pair binding, map both physical members through that
realization's exact physical-to-CAD mapping, canonicalize the resulting concrete
CAD pair, and copy its classification and exclusion reason into the derived
entry. No `OUTPUT_RIGID`, gear, disposition, geometry, or missing-pair heuristic
may classify an M13-3 inventory.
The validator requires `complete_concrete_instance_ids` equal the exact source
assembly constituent IDs used by the `KinematicModelV2` and M10-3 v2 request;
the model’s complete body-member IDs, inventory universe, exact-pair projection,
and source assembly cannot differ.
Entries must contain exactly one entry for every derived pair: omitted, duplicate,
self, unknown, or extra CAD pairs reject. Entries and universe are sorted by
`(first_instance_id, second_instance_id)`; caller entry order is non-semantic.

`inventory_hash` hashes the schema version, physical mechanism/body binding
identities, CAD realization hash, M10 model hash, complete concrete constituent
IDs, complete pair universe, and every canonical entry including classification
and exclusion reason. Thus semantic reason changes change identity. A same-body
pair remains present and must be
`SAME_RIGID_GROUP_EXCLUDED` only when both mapped physical members are in the
same `PhysicalRigidBodyBinding`; it never enters M10 exact scope. Every
cross-body `CHECK_CLEARANCE` entry becomes exactly one canonical
`ExactConstituentPair`; every excluded entry remains in the complete inventory.
The v2 scope independently rejects same-body pairs. This includes required
articulated/articulated pairs such as A2/B1.

## M10-3 V2 Candidate Evaluation

Add `CandidateMultiJointM10EvaluationScope@1`,
`CandidateMultiJointM10EvaluationRequest@1`, and
`CandidateMultiJointM10Evaluation@1`. The request binds candidate and source
currentness, physical mechanism/body/joint hashes, physical pair-classification
set hash, bridge hash, candidate CAD realization/mapping hashes, M10 v2 model
hash, complete derived inventory hash, exact-scope hash, ordered keyed
configuration hashes, its embedded replayable `CandidateMultiJointM10EvaluationScope@1`
including actual ordered `JointConfiguration` values and M10-3 tolerances, and
the exact M10-3 v2 request hash in field
`m10_v2_request_hash`; its own identity is `request_hash`. It does not contain
or bind an M10 result hash, evaluation hash, or selection hash. The evaluator
reconstructs the strict
`MultiJointCollisionSweepRequestV2` from the request inputs, verifies its hash
equals the stored exact M10-3 v2 request hash, then dispatches
`ProductionApplication.analyze_multi_joint_collision_sweep_v2`.

Only after execution, `CandidateMultiJointM10Evaluation@1` binds the candidate
evaluation request hash, `m10_v2_request_hash`, `m10_v2_result_hash`, bridge
hash, M10 model hash, physical pair-classification set hash, inventory hash,
exact-scope hash, configuration-set hash, source/currentness, and its own
`evaluation_hash`. Construction
and replay require the returned result to name `m10_v2_request_hash` and to
recompute to `m10_v2_result_hash`. Thus request A executed with result A cannot
construct/replay an evaluation with result B. M10 collision results remain
engineering outcomes, distinct from authority and integrity failures.

## Multi-Joint Verification Configuration Authority

`JointConfiguration` payloads are replayable semantic M10-3 inputs; their hashes
are not reversible. M13-3 adds `MultiJointVerificationConfigurationSet@1` as a
durable `CANONICAL_REDERIVATION_INPUT`, not a physical geometry fact, M10 model,
M10 request, or M10 result. It contains exactly
`schema_version = "multi-joint-verification-configuration-set@1"`, nonempty
ordered `configurations: tuple[JointConfiguration, ...]`, checked ordered
`configuration_hashes`, and `configuration_set_hash`. Configuration ordering is
semantic because `MultiJointCollisionSweepRequestV2` hashes ordered
configurations; keyed positions inside each configuration retain current
`JointConfiguration` semantics.

`configuration_set_hash` is SHA-256 canonical JSON over exactly:

```text
{
  "schema_version": "multi-joint-verification-configuration-set@1",
  "configurations": <ordered current JointConfiguration wire payloads>
}
```

It is never a hash of hashes only. `configuration_hashes` must equal the ordered
`joint_configuration_hash` values and is redundant checked identity metadata,
not a substitute for actual commands.

`CandidateMultiJointM10EvaluationScope@1` owns the complete embedded
configuration-set record and exactly the discrete M10-3 tolerances
`volume_tolerance_mm3` and `distance_tolerance_mm`, plus `scope_identity` and
`scope_hash`. Its hash payload is schema version, serialized configuration set,
both tolerances, and scope identity. `required_clearance_mm` is absent: M10-3
does not consume it and M13-3 defines no discrete selection rule that uses it.
M10-4 `required_clearance_mm` remains an explicit focused-path-regression input,
not durable M13-3 configuration authority.

The candidate request uses design A: it embeds the immutable scope record, binds
its `configuration_set_hash`, and stores the corresponding ordered configuration
hashes. It therefore contains enough trusted replay input to construct a fresh
M10 request from source assembly identity, derived `KinematicModelV2`, exact pair
scope, actual ordered configurations, and M10-3 tolerances. A caller-provided
prebuilt `MultiJointCollisionSweepRequestV2` is never authority.

At request creation and canonical replay, each configuration must name the fresh
bridge model ID, have exactly the emitted stable physical-joint-ID key set, carry
only finite values, satisfy each bounded inclusive limit, and retain raw
continuous multi-turn values. M13-3 never falls back to q=0, derives samples from
limits, wraps 360 degrees, or invents configurations.

For this purpose the bridge compiler assigns `KinematicModelV2.model_id` from the
versioned semantic payload `{ "schema_version": "physical-to-m10-v2-model-id@1",
"physical_body_ids": <sorted stable physical body IDs>, "physical_joint_ids":
<sorted stable physical joint IDs> }`. The exact model ID is
`physical-to-m10-v2-model@1:` followed by the SHA-256 hex digest of that canonical
payload. It deliberately excludes candidate/canonical physical-instance IDs, CAD
identities, placements, pair policy, model hash, inventory, and bridge hash. Thus
candidate and canonical bridge models use the same model ID for the same stable
physical body/joint topology while their independently derived model/request
hashes may differ. This is a bridge-local identifier derivation, not a new M10
schema or identity rule.

## M10-4 V2 Boundary

M13-3 may add a focused optional explicit-path companion to the multi-joint
request/evaluation records. It binds the same bridge/inventory/scope plus the
`MultiJointPath` and calls
`ProductionApplication.prove_continuous_multi_joint_path_clearance_v2`. It
preserves M10-4’s `VERIFIED_CLEAR`, `COLLISION_WITNESS`, and `NOT_PROVEN`
semantics and `body-member-reach-bound-plumbing@2.0`; it is not configuration
space certification or M13-4 acceptance.

## Bridge Identity / Currentness

`physical_to_m10_bridge_hash` hashes a versioned canonical payload composed of:

- `kinematic_root_binding_hash` and canonical physical body binding hashes;
- canonical physical revolute binding hashes;
- semantic placement/derivation identities used for every member and source;
- candidate/canonical physical-to-CAD mapping hashes;
- `physical_pair_classification_set_hash`;
- derived M10 v2 model hash; and
- complete inventory hash and exact pair-scope hash.

Binding hashes cover physical identity, membership/reference, connection,
interface/frame source hash, axis owner/sign, motion/limits, and
`zero_reference_semantics`. Thus grouping, source authority, limits, placements, mappings, offsets,
pair classifications, or scope substitution changes a bridge or referenced hash.
Do not duplicate payload fields already cryptographically bound by the referenced
canonical hash. Existing candidate/state revision/hash and request identities are
the currentness system; no new currentness service is introduced.

The bridge does not own discrete verification sampling. The separately owned
candidate scope and projected canonical obligation bind configuration-set identity
to the bridge/model/scope at request, evaluation, selection, and canonical replay
boundaries. This prevents a bridge/configuration identity cycle and prevents CAD
or M10 from inventing semantic command configurations.

## Evaluation / Selection Binding

Add `CandidateMultiJointSelection@1`, a selection companion that reuses existing
candidate/currentness/selection validation patterns but binds the selected
`CandidateMultiJointM10Evaluation.evaluation_hash`, its bridge hash, M10 v2
model hash, physical pair-classification set hash, inventory hash, and exact-scope
hash, and configuration-set hash. It also validates the selected evaluation’s
candidate request hash, M10 request hash, M10 result hash, and configuration-set
hash before selection. The M13 promotion route
accepts this record and its exact evaluation chain, not a legacy
`CandidateSelection` standing alone. Evaluation A selected with request/result/
bridge/pair-set/configuration-set B at promotion rejects, even when CAD geometry
or numeric axes
coincide.

Existing `CandidateSelection@1`, `CandidateEvaluation@1`, and their M12
single-output pipeline are unchanged. The new record is additive because the old
candidate-evaluation schema is structurally tied to M12/M10-1 outcomes.

## Promotion Semantics

Promote only physical mechanism authority: physical body/joint records, root,
connection correspondence, axis/interface source identity, sign, limits/motion,
the frozen `accepted-semantic-home@1` zero-reference semantic, and the durable
physical-pair classification bindings. Pair bindings are
`CANONICAL_REDERIVATION_INPUT`, not `ACCEPTED_PHYSICAL_FACT`; they preserve the
analysis/policy semantics needed for canonical re-derivation.
Use `accepted_physical_fact` for each exact source identity:

- `candidate:physical-rigid-body:{physical_body_id}:{binding_hash}`;
- `candidate:physical-revolute-joint:{physical_joint_id}:{binding_hash}`; and
- `candidate:physical-kinematic-root:{kinematic_root_physical_body_id}` with
  `source_value = kinematic_root_binding_hash`.

For every canonicalized candidate physical pair binding, add the additive
promotion classification source identity
`candidate:physical-pair-classification:{first_physical_instance_id}:{second_physical_instance_id}:{binding_hash}`
with classification `CANONICAL_REDERIVATION_INPUT` and
`source_value = binding_hash`. The promotion compiler verifies the complete
physical pair universe, pair-binding and set-hash integrity, exact
candidate-to-canonical physical-ID projection, classification preservation, and
exclusion-reason preservation.

For the selected candidate discrete verification scope, promotion adds exactly
one `PromotionClassification` with source identity
`candidate:multi-joint-verification-obligation:{scope_hash}`, classification
`CANONICAL_REDERIVATION_INPUT`, and `source_value = scope_hash`. Promotion
rebuilds and verifies the actual embedded configuration set, its ordered hashes,
both discrete tolerances, and the selected request/evaluation/selection chain.
It projects only the semantic obligation; it never promotes a candidate scope
object, candidate evaluation request, M10 request/result, bridge, CAD
realization, inventory, exact scope, or M10 model.

The mapped candidate semantic placement derivation identities retain existing
`canonical_rederivation_input` classification where M13-2 defines it. M10 v2
models, joints, bodies, member offsets, pair scopes, requests, results, CAD
artifacts, and bridge compilations are derived and `do_not_promote`.
`MultiJointCollisionPairInventory`, `MultiJointCollisionPairEntry`, and
`ExactConstituentPair` are also derived and `do_not_promote`. No enum is added.

The M13-3 promotion trust boundary carries the complete replayable
`GeneratedPlacementDerivation` set selected and evaluated by the candidate CAD
chain, together with the existing `placement_derivations_hash`. The actual
derivation records and hash are both bound into the M13-3 evaluation and
promotion request identities; a hash without records, records with a
mismatching hash, or a set not bound to the selected candidate CAD realization
is rejected. Promotion projects these records through the existing M13-2
`CanonicalGeneratedPlacementDerivation` machinery. It does not promote
candidate CAD, candidate world placements, or derived member offsets.

## Candidate / Canonical ID Projection

Physical body and joint IDs are stable semantic IDs and remain unchanged.
Candidate physical member IDs project through the accepted candidate-canonical
mapping to canonical physical instance IDs. Candidate CAD IDs never enter
canonical physical records. The candidate bridge uses candidate CAD maps; the
canonical bridge uses fresh `CanonicalPhysicalCadMapping` records and fresh CAD
instance IDs. Connection/interface/frame correspondence projects endpoints while
retaining the authoritative source record/hash meaning.

## Canonical Physical Body / Joint Records

`CanonicalPhysicalMechanism@3` stores projected canonical body member/reference
instance IDs, canonical revolute endpoint IDs, and a complete canonicalized set
of `CanonicalPhysicalPairClassificationBinding` records. The latter contains the
projected canonical physical pair plus the same classification and exclusion
reason semantics, with its own hash over schema version, canonical physical pair,
classification, and exclusion reason. Raw candidate and canonical binding hashes
need not match because physical instance IDs project; semantic equivalence is
checked after explicit ID projection. Candidate CAD IDs never enter canonical
pair authority. The mechanism preserves physical body/joint identity, topology,
connection/interface/frame source correspondence, axis sign, motion mode/limits,
and `zero_reference_semantics`. It does not store candidate CAD mappings,
candidate placements, derived member offsets, M10 transforms/models/results,
candidate inventories, or candidate analysis provenance as authority.

`CanonicalPhysicalMechanism@3` additionally carries
`multi_joint_verification_obligations`, an additive canonical tuple of
`CanonicalMultiJointVerificationObligation@1`. It does not alter legacy
`m10_obligations`, which are historical single-output interval-based
`CanonicalM10VerificationObligation` records and cannot truthfully own a
multi-joint discrete sequence. The new canonical record contains exactly
`schema_version = "canonical-multi-joint-verification-obligation@1"`, an embedded
`MultiJointVerificationConfigurationSet@1`, `volume_tolerance_mm3`,
`distance_tolerance_mm`, checked `configuration_set_hash`, and `obligation_hash`.
Its hash payload is exactly schema version, serialized configuration set, both
tolerances, and configuration-set hash. It contains no candidate CAD, bridge,
model, request, result, or inventory identity.

For initial M13-3 `canonical-physical-mechanism@3`, this tuple has exactly one
member. Promotion emits exactly one selected discrete verification obligation;
canonical reconstruction requires exactly that one obligation and executes it.
Zero obligations, duplicate obligations, or two or more distinct obligations
reject. There is no tuple-order selection, first-item fallback, or all-obligation
iteration semantics in this milestone. The tuple remains only to preserve the
mechanism schema collection style for a future explicitly versioned extension.

Projection preserves configuration order, keyed stable `physical_joint_id`
semantics, and numeric values because physical joint IDs lower directly to M10
v2 joint IDs and stay stable across promotion. Canonical replay rejects a removed
or renamed joint or a command invalid under canonical motion mode/limits.

Candidate-to-canonical projection applies to every physical-instance-bearing
field. It maps the parent endpoint physical instance ID, child endpoint physical
instance ID, and every axis source's `source_physical_instance_id` through the
accepted `CandidateCanonicalInstanceMapping`. Canonical axis-source variants are
distinct canonical records for supplied rotational-interface, supplied
reference-frame, generated rotational-interface, and generated reference-frame
sources. Each retains its source kind and projected semantic interface/frame ID
under M13-1/M13-2 projection rules, retains/rebinds the authoritative source-hash
meaning required by that source model, substitutes the canonical physical
instance ID, and recomputes its canonical `source_hash` from the full canonical
source payload. `CanonicalPhysicalRevoluteJointBinding.binding_hash` is then
recomputed from that canonical source record. Candidate source IDs/hashes and
candidate joint binding hashes are never copied into canonical authority.

## Fresh Canonical CAD Mapping

The canonical CAD compiler must first create and validate a fresh
`CanonicalCadRealization` bound to current `DesignState`, canonical mechanism,
placements/derivations, selected source artifacts, and mappings. Every canonical
physical body member must map to one fresh concrete `CadComponentInstance`, and
every fresh canonical CAD constituent must have that one body owner; none may
silently disappear or be added outside the Physical/CAD Universe Contract.
Candidate CAD maps are forbidden input.

## Fresh Canonical Bridge Reconstruction

A new process reconstructs M13-3 semantics using only `DesignState`,
`CanonicalPhysicalMechanism@3`, canonical placements/M13-2 derivations, trusted
M13-1/M13-2 records, and fresh canonical CAD realization. It calls the same pure
lowering core, maps the complete canonical physical pair-binding set through the
fresh canonical CAD mapping to derive a fresh
`MultiJointCollisionPairInventory@1`, then builds fresh M10 v2 bodies/joints/model
and exact pair scope. It validates the canonical multi-joint verification
obligation against that fresh model, builds a fresh ordered
`MultiJointCollisionSweepRequestV2` from canonical actual configurations and
canonical M10-3 tolerances, then executes M10-3 v2. Candidate and canonical M10
request hashes need not match because fresh CAD, assembly, and model identities
may differ. M10-4 remains a focused regression only and does not consume this
durable discrete configuration authority. The process cannot receive a candidate,
candidate pair inventory/bridge/CAD/model/result, Markdown, or prior process
memory.

## Candidate / Canonical Semantic Equivalence

Compare after explicit candidate-to-canonical physical/member/CAD ID projection:
physical body IDs/member sets/reference member; physical joint IDs/topology;
connection/interface/frame identity and source hash; axis owner/sign; motion,
limits, and `zero_reference_semantics`; lowered parent-reference-local axes;
member offsets; q=0 poses; complete realization/model/inventory universes;
the complete physical-pair binding set including classifications and exclusion
reasons; complete derived pair classifications; and `CHECK_CLEARANCE`
correspondence. It also compares the selected/projected verification obligation:
configuration count, semantic sequence order, keyed physical joint IDs, numeric
commands, configuration-set identity after projection, and both M10-3
tolerances. It does not compare candidate/canonical M10 request hashes.
Separately prove that candidate semantic pair bindings map to
the candidate CAD inventory and canonical semantic pair bindings map to the
fresh canonical CAD inventory with equivalent meaning after candidate/canonical
CAD-ID projection. Raw CAD inventory hashes need not match. Use
`rigid-transform-agreement@1.0` for poses/offsets. Do not require raw candidate
and canonical bridge/model/CAD/hash bytes to match.

## M13-1 Consumption

Resolve supplied definitions and frames through the active component specification
for the named physical instance. Verify exact geometry binding, interface/frame
self-hash, accepted evidence/fact closure, materialization replay where relevant,
and `require_authoritatively_consumable_interface` before extracting axes. Missing,
inferred, proposed, unresolved, unauthorized, or hash-mismatched supplied sources
reject before M10 lowering. M13-3 does not modify M13-1.

## M13-2 Consumption

Resolve each `GeneratedRotationalInterface`/`GeneratedReferenceFrame` from the
active generated specification by exact ID/hash and current registry validation.
Replay `GeneratedPlacementDerivation` candidate-side and
`CanonicalGeneratedPlacementDerivation` canonical-side with their established
placement authority. Never rederive an axis from generated CAD geometry. M13-3
does not modify M13-2.

## M13-3P Consumption

M13-3 consumes all M13-3P types through their public parsers/validators. It must
not make unsafe model copies or trust nested stored `body_hash` values. All M10
v2 requests/execution use strict model reconstruction and exact schema,
evaluator, agreement-policy, and body-hash checks. Forged body/member/joint state
must fail before FK, provider, extent, or proof work.

## Backward Compatibility

M12 one-output candidate/canonical requests, bindings, scopes, inventories,
promotion mappings, JSON, hashes, and execution behavior remain unchanged.
Legacy M10 v1 remains untouched. M13-3 uses explicit schema branches and custom
serializers for extended physical mechanisms; optional fields plus
`exclude_none` are insufficient compatibility strategy.

## Schema Versioning

| Record | Decision |
| --- | --- |
| `PhysicalMechanismRealization` | Add `physical-mechanism-realization@2`, including physical rigid bodies, physical revolute joints, kinematic root, and complete `PhysicalPairClassificationBinding` authority; `@1` literal serializer/hash remains unchanged and forbids new fields. |
| `CanonicalPhysicalMechanism` | Add `canonical-physical-mechanism@3`, projecting the physical bodies/joints/root and complete `CanonicalPhysicalPairClassificationBinding` set; `@1/@2` literal serializers/hashes remain unchanged and forbid new fields. |
| `MechanicalDesignCandidate` | Unchanged `@1`; its existing candidate hash binds the versioned realization. |
| Candidate/canonical CAD realization/mapping | Unchanged current versions; their exact mapping hashes are bridge inputs. |
| Legacy M12 scope/request/binding/inventory | Unchanged `@1`; do not accept M13 multi-joint semantics. |
| `MultiJointCollisionPairEntry` / `MultiJointCollisionPairInventory` | New `@1` records with the frozen five-value reused enum, reason contract, complete-universe validation, canonical ordering, and hash payload defined above. |
| M13 bridge/scope/request/evaluation/selection | New additive `@1` records with explicit serializers/hashes; the evaluation request owns `m10_v2_request_hash`, while only the evaluation owns `m10_v2_result_hash`. |
| `CandidateEvaluation` / `CandidateSelection` | Existing `@1` unchanged; use additive M13 multi-joint evaluation/selection records. |
| Multi-joint discrete verification authority | New `MultiJointVerificationConfigurationSet@1`, embedded in additive `CandidateMultiJointM10EvaluationScope@1` and projected as `CanonicalMultiJointVerificationObligation@1`; current `JointConfiguration` wire semantics and legacy M12/canonical M10 obligations remain unchanged. |
| Promotion classification enum/policy/mapping | Existing enum and current mapping version retained; add M13 projection records/validation without changing old payloads. |
| M10 v2 records | Unchanged; M13-3 performs zero generic M10 representation changes. |

## Failure Semantics

Reuse current `ValueError`/integrity/currentness families with precise errors for
malformed physical body, duplicate/incomplete membership, malformed physical
joint, missing/wrong connection, unauthorized supplied axis, generated hash
mismatch, placement replay failure, unresolved limits, invalid topology, CAD map
mismatch, bridge/evaluation/inventory substitution, stale candidate, canonical
projection mismatch, and fresh reconstruction mismatch. Preserve M10-3 collision
and M10-4 `NOT_PROVEN` as engineering results, never authority failures.

## Dependency Decision

**`USE EXISTING STACK`.** Existing Pydantic v2, transform/quaternion helpers,
M13 authority/placement replay, candidate/canonical mapping, M10 v2, FreeCAD
transient measurement, and provenance services are sufficient. No robotics,
spatial-math, physics, or CAD dependency is required.

## Test Strategy

Future implementation tests must cover:

- direct consumption of M13-3P v2 bodies/joints/pairs and protected empty M10
  implementation diff;
- valid multi-member physical body; duplicate and incomplete membership rejection;
- full Physical/CAD Universe Contract coverage; unmapped body member, mapped CAD
  constituent without a body, duplicate body membership, extra CAD constituent,
  omitted CAD constituent, and model/inventory-universe mismatch rejection;
- identical complete physical/CAD universe under caller reorder produces the same
  canonical mapping/body/inventory identity;
- two-joint chain, cycle, duplicate parent, unknown body, missing/wrong
  `ROTATIONAL_DRIVE` plus `KINEMATIC_REALIZATION_INTENT` connection rejection;
- M13-2 generated and M13-1 accepted supplied axes; inferred/unauthorized axes
  rejection; equal numeric axis with different source hash changing identity;
- explicit body reference, placement-derived offsets, agreement-policy use, and
  no CAD inference;
- required `accepted-semantic-home@1` zero semantics; unsupported or omitted
  zero semantics reject; candidate q=0 derives from candidate placements;
  canonical q=0 derives freshly from canonical placements; projected q=0 poses
  agree under `rigid-transform-agreement@1.0`; and a future versioned zero mode
  changes physical joint binding identity;
- no CAD-viewer or manually supplied rest-transform path can define q=0;
- deterministic v2 body/joint/model lowering with no caller-authored M10 truth;
- complete pair inventory: all cross-body checks reach exact scope, same-body
  pairs stay explicit excluded, and articulated/articulated A2/B1 is executed;
- complete physical pair-binding authority: missing, duplicate, self, unknown,
  or extra physical pair rejects; caller pair ordering canonicalizes; a
  `CHECK_CLEARANCE` reason rejects; an excluded pair without a reason rejects;
  a reason-only change changes binding/set identity; same-body pairs require
  `SAME_RIGID_GROUP_EXCLUDED`; and cross-body use of that classification rejects;
- candidate physical-pair bindings map exactly to candidate CAD inventory entries,
  canonical physical-pair bindings map exactly to fresh canonical CAD inventory
  entries, candidate CAD IDs never enter canonical pair authority, fresh
  canonical reconstruction requires no candidate inventory, and semantic set A /
  inventory A / result A rejects substitution of set B, inventory B, or scope B
  at selection or promotion;
- complete inventory validation: omitted/duplicate/self/unknown/extra pairs
  reject; reclassification and semantic exclusion-reason changes alter inventory
  identity; caller tuple reorder canonicalizes to identical JSON/hash; and the
  M12 `requires_home_exact_check` flag is absent from the new inventory;
- M10-3 v2 candidate result and optional focused M10-4 v2 path;
- replayable configuration authority: actual ordered `JointConfiguration` values
  rather than hashes alone; configuration-set hash/order sensitivity; exact
  model-ID/joint-key/finite-value/limit validation; raw continuous multi-turn
  preservation; and rejection of q=0, limit-derived, or invented fallback;
- reconstruction of M10-3 requests only from embedded trusted scope values,
  source assembly, model, exact scope, and discrete tolerances; caller-authored
  prebuilt request rejection; and exact reconstructed request-hash equality;
- bridge, pair-inventory, grouping, axis-source, and limit substitution rejection;
- request A/result A evaluation rejects substituted result B; selected evaluation
  A rejects request/result/bridge B at promotion;
- configuration set A evaluated then configuration set B supplied at selection
  or promotion rejects, including a changed one-joint command with otherwise
  identical bridge, model, CAD, and pair policy;
- unchanged `kinematic_root_physical_body_id` with changed CAD mapping or pair
  inventory retains its root binding hash; changing it changes both root hash and
  bridge hash;
- bounded 0..360, bounded 0..1080, and continuous identity distinction;
- promotion of physical records only and rejection of M10/CAD promotion;
- promotion projection of complete pair-binding authority with
  `CANONICAL_REDERIVATION_INPUT`, exact ID/classification/reason preservation,
  set-hash integrity, and explicit rejection of inventory promotion;
- promotion of the selected multi-joint verification obligation only as
  `CANONICAL_REDERIVATION_INPUT`, including its exact source identity/value,
  ordered commands/tolerances, and rejection of candidate request/bridge/M10
  request/result promotion or configuration-obligation substitution;
- fresh canonical reconstruction with no candidate/CAD/M10 object; projected
  semantic equivalence using the shared agreement predicate, replayable canonical
  discrete configuration authority, fresh request construction, and no
  candidate/canonical M10 request-hash equality requirement;
- strict v2 forged nested model/body hash/schema tests at bridge and request
  boundaries; and
- M12 v1, M13-1, M13-2, M13-3P, M10 v1/v2 regression suites.

## Representative Two-Joint Example

Use a generic connected tree with multi-member bodies where practical:

```text
physical rigid body R = (R1, R2)
  -> J1 (generated authoritative axis)
physical rigid body A = (A1, A2)
  -> J2 (accepted supplied axis when fixture authority permits; otherwise generated)
physical rigid body B = (B1, B2)
```

The fixture proves semantic q=0, J1 moving A/B members, J2 moving B only,
cross-body root/articulated and A2/B1 exact pairs, selected bridge binding,
promotion, fresh canonical lowering, and canonical discrete verification. It has
no Rotator-specific terminology.

## M13-4 Handoff

M13-3 closes the generic physical-to-M10 bridge with a bounded proof. M13-4
remains the representative full-stack/capstone milestone. It may consume M13-3
but does not move broad integration acceptance, synthesis, or Rotator V2 into
this scope.

## Remaining Boundaries

The resulting capability is limited to deterministic lowering and reconstruction
of explicit rooted multi-revolute physical mechanisms and selected cross-body
collision obligations. It does not claim arbitrary robotics, loops, inverse
kinematics, dynamics, trajectory planning, automatic discovery/recognition,
configuration-space proof, manufacturing approval, or whole-assembly FEA.

## Proposed Implementation Surface

Likely minimal future surface:

- `candidates/models.py`: versioned candidate physical body/joint/root/pair-policy
  records and `PhysicalMechanismRealization@2` serialization/validation.
- `models/physical_mechanism.py`: canonical projected body/joint/root/pair-policy
  records and `CanonicalPhysicalMechanism@3` serialization/validation.
- New `candidates/multi_joint_m10_bridge.py`: shared pure lowerer, candidate and
  canonical adapters, bridge identity, inventory projection, and equivalence.
- New `candidates/multi_joint_m10_evaluation.py`: additive v2 evaluation scope,
  replayable configuration-set ownership, request/result binding, strict
  reconstruction, and production API invocation.
- New `candidates/multi_joint_selection.py`: additive bridge-bound selection.
- `candidates/promotion.py`, `promotion_models.py`, `canonical_mechanism.py`,
  and canonical CAD/reconstruction wiring: physical projection, canonical
  multi-joint verification-obligation projection, and fresh bridge route only.
- `application.py` and package exports: narrow M13 service composition/wiring;
  no generic M10 changes except exports only if genuinely necessary.
- Focused unit/integration/live bridge, promotion, fresh-process, adversarial,
  and regression tests.

## Acceptance Criteria

M13-3 is complete only when authoritative candidate physical body/joint semantics,
M13-1/M13-2 axis authority, semantic placements, candidate CAD mapping, and a
complete durable physical-pair classification set project to a complete derived
pair inventory over the exact complete realization assembly and deterministically
compile to `KinematicModelV2` plus exact scope; every such constituent has one
explicit physical body owner; current M10-3 v2 evaluates it; selection/promotion
preserve physical semantics plus durable pair-policy re-derivation inputs; and a
fresh process creates canonical CAD, a
fresh v2 model, fresh exact scope, and canonical M10-3 v2 verification without
candidate memory, manually authored M10 joints, CAD inference, implicit bodies,
a new M10 solver, candidate inventory, or promoted M10 analysis objects. q=0 is only required
`accepted-semantic-home@1`, derived from the corresponding semantic placements.
The evaluation binds the post-execution exact M10 result, while its request binds
only the pre-execution exact M10 request. A bounded M10-4 v2 regression is
permitted.

The selected discrete configuration sequence and M10-3 tolerances are durable,
replayable candidate scope semantics. They promote only as a canonical
rederivation obligation and are sufficient for fresh canonical M10-3 request
construction without retaining a candidate request, relying on hashes alone,
falling back to q=0, or sampling limits. Candidate and canonical M10 request
hashes need not match.

## Self-Review

This reconciliation removes the stale current blocker while retaining it as
resolved history. It defines additive physical grouping and joint authority;
never treats `KinematicRigidBody`, `OUTPUT_RIGID`, CAD geometry, or member
offsets as physical authority; targets only M10 v2; keeps same-body pairs
explicit; adds complete durable physical-pair policy authority while retaining
the CAD/M10 inventory as derived only; freezes one complete physical/CAD/model/
inventory universe with no
implicit body fallback; binds the only q=0 semantic in physical joint identity;
hash-binds membership/offsets/pairs/authority/selection; prevents
candidate-to-canonical reuse; preserves legacy M12/M10 bytes through explicit
schema branches; requires strict M13-3P reconstruction; and excludes M13-4,
Rotator, M11, and generic M10 scope expansion.

The discrete configuration reconciliation additionally gives actual ordered
`JointConfiguration` values one durable candidate owner, never reconstructs
them from hashes, binds their configuration-set identity through evaluation and
selection, and promotes only their canonical rederivation obligation. Fresh
canonical M10-3 has an explicit obligation source and builds a new request; it
does not retain candidate requests/results, require candidate/canonical request
hash equality, default to q=0, derive samples from limits, or add M10 semantics.
