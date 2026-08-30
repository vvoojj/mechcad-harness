# M12-5 Explicit Candidate Promotion, Canonical Rebinding, And M11 Handoff

## Status

M12-5 implementation specification - approved and ready for implementation
planning. This milestone implements the first bounded transition from a selected
noncanonical M12 candidate to an accepted canonical physical-mechanism revision.
It does not implement M12-6, general mechanism synthesis, automatic selection,
manufacturing approval, assembly FEA, or a new M10/M11 solver capability.

## Purpose And Bounded Claim

M12-5 consumes an explicit current selected `MechanicalDesignCandidate` with a
current `CandidateEvaluation` whose outcome is `FEASIBLE`. It deterministically
compiles the selected physical design facts into an ordinary `ChangeProposal`,
applies that proposal only through the existing `RunController` / `ChangeEngine`
mutation path, reconstructs the promoted mechanism from the resulting canonical
state, performs fresh canonical CAD and M10 evaluation, and exposes a
post-promotion-only M11 eligibility handoff.

The maximum claim is:

```text
current feasible selected candidate
    -> deterministic proposal through ChangeEngine
    -> one new canonical DesignState revision
    -> independent canonical physical reconstruction
    -> fresh canonical CAD and M10 verification
    -> durable selection/promotion provenance
    -> eligible M11 handoff assessment only
```

Promotion is not automatic approval. `PROMOTION_APPLIED` and post-promotion
engineering verification are separate states. A candidate evaluation, candidate
CAD realization, candidate M10 request/result, candidate comparison, or ranking
never becomes canonical proof merely because promotion succeeded.

## Accepted Baseline Reused

M12-5 reuses without replacement:

- `DesignState`, `StateManager`, canonical JSON hashing, immutable revisions,
  `ChangeProposal`, `ChangeSet`, `ChangeEngine`, ownership, and the existing
  `StateManager.project_lock`;
- `RunController.apply_approved_proposal()` for normal state application and
  normal invalidation persistence;
- `ArtifactStore` for immutable selected-decision and promotion-result JSON
  manifests;
- M12-2 candidate integrity/currentness and property snapshot semantics;
- M12-3 bounded direct-drive and external-spur candidate/admissibility results;
- M12-4 candidate evaluation, comparison, selection, source geometry, CAD, and
  M10 scope semantics;
- generic `CadAssemblyProgram`, `ImportedCadComponent`, trusted STEP resolution,
  FreeCAD transient measurement, and M10 single-axis proof;
- the unchanged M11 source-bound single-solid structural path.

No new candidate state, selected state, promotion store, candidate revision
store, mechanism database, second mutation engine, or M12-specific transaction
or lock is introduced.

## Canonical Physical-Mechanism Authority

`DesignState` gains a typed `physical_mechanisms` collection. Each item is a
complete `CanonicalPhysicalMechanism` and is atomic at the DesignState revision
level. The canonical collection contains accepted physical design semantics,
not a serialized candidate or generic dictionary payload.

The initial canonical model contains:

- stable canonical mechanism and physical-instance identities;
- component specification snapshots and property snapshots retaining exact
  availability, normalized value/range, unit, source identity, property
  authority, applicability, conversion provenance, property hash, and
  specification hash/provenance;
- accepted design choices with an explicit origin classification;
- selected trusted `GeometrySourceReference` records;
- accepted placement-defining inputs and deterministic placement relations;
- physical interfaces, components, connections, topology, and the physical
  joint-realization binding;
- a canonical M10 verification obligation over canonical physical identities;
- narrow historical promotion provenance references.

It deliberately excludes:

- `MechanicalDesignCandidate` and any candidate snapshot as canonical authority;
- `CandidateEvaluation`, `FEASIBLE`, M12-3 calculations, or suitability results;
- candidate CAD request/result or transient CAD artifacts;
- candidate M10 request/result, proof budgets, runtime data, pair assemblies, or
  Evidence identifiers;
- comparison rank/result as an engineering fact;
- M11 definitions, material/load/support authority, or structural results unless
  those already independently exist as canonical authority.

### Canonical M10 Binding And Obligation

The M10 mathematical joint remains separate from physical realization. A
canonical mechanism stores a `CanonicalJointPhysicalBinding`, not an
independently editable `RevoluteJointModel`. It contains the scoped joint ID,
expected parent/child semantic identities, axis/frame correspondence, and a
normalized semantic snapshot/hash/version required to detect drift.

When no pre-existing canonical M10 joint object exists in `DesignState`, that
snapshot is a binding snapshot required for reconstruction and compatibility
checking. It is not a second M10 joint authority. The canonical M10 compiler
must construct the actual M10 model according to the unchanged M10 contract and
fail closed if it does not match the canonical physical binding snapshot.

`CanonicalM10VerificationObligation` is the accepted requirement, not an
execution request. It contains only:

- the canonical joint semantic identity;
- required interval or path semantics;
- required clearance;
- required pair semantics expressed using canonical physical component/interface
  identities;
- required representation fidelity; and
- declared home-state semantics where applicable.

It never contains candidate CAD IDs, induced assembly IDs, proof budgets,
temporary paths, backend correlation IDs, or candidate M10 identities. The
obligation also does not independently store derived M12-4 execution
classifications such as `SAME_RIGID_GROUP_EXCLUDED`, directional CAD pair order,
or proof pair request identities. Fresh canonical CAD mapping, physical topology,
and the canonical motion binding derive the complete CAD pair inventory and its
execution classifications. An accepted rigid output relationship may therefore
derive `SAME_RIGID_GROUP_EXCLUDED`; it is not independently canonical authority.
An intended gear mesh is canonical physical/interface semantics, while an
unmodeled driver internal-motion limitation is a declared verification-scope
limitation, not a complete physical-kinematics claim.

## Ownership And Paths

The current ownership system is configuration-defined: `OwnershipPolicy` uses
literal/wildcard paths from `config/ownership.yaml`, and ChangeEngine validates
each operation through that policy. There is no separate owner registry.

M12-5 adds only this narrow rule:

```text
/physical_mechanisms/* -> mechcad-physical-mechanism
```

The promotion compiler emits exactly one canonical mutation:

```text
add /physical_mechanisms/<canonical-mechanism-id>
```

with one complete validated canonical mechanism value. It does not receive root
ownership, an ownership escape, or authority over unrelated component,
requirement, structural, or state paths. Path handling follows the existing
list-item-by-`id` grammar used by `ChangeEngine`.

## Candidate-To-Canonical Mapping And Completeness

`CandidatePromotionPolicy` defines how promotion is permitted: allowed target
family, mapping schema/compiler version, allowed promotion classifications,
required source/property authority checks, and publication behavior. It cannot
contain a candidate hash, selection, component value, or other candidate-specific
physical design value.

`CandidatePromotionRequest` defines which exact decision is promoted. It binds:

- candidate, synthesis request, and synthesis policy;
- exact M12-3 admissibility result;
- exact candidate evaluation and selection;
- optional exact comparison result plus the complete comparison entries/request
  when `comparison_used` is true, and no comparison when it is false;
- exact source revision/state hash;
- canonical target mechanism ID;
- promotion policy and mapping classification;
- optional pre-promotion `PostPromotionM11TargetIntent`.

`PostPromotionM11TargetIntent` is workflow input, not structural authority. It
may state that an eligibility assessment is requested, the candidate physical
instance ID to be mapped or an explicit whole-mechanism target scope, and the
requested supported analysis category. It cannot contain a future revision/state hash, canonical CAD artifact,
`StructuralAnalysisDefinition`, canonical handoff request hash, or M11 result
identity, because none can truthfully exist before promotion.

The compiler produces an explicit, deterministic mapping:

```text
candidate physical instance ID
    -> canonical physical instance ID
    -> canonical mechanism path
```

The initial mapping is `<canonical-mechanism-id>:<candidate-instance-id>`. Both
parts must pass the canonical lexical/path rules. Delimiter-containing or
otherwise invalid candidate IDs are rejected; no lossy sanitation is allowed.
The resulting canonical IDs are opaque after creation. Later traceability uses
the persisted mapping rather than parsing IDs.

Before proposal compilation, the compiler validates:

- canonical mechanism ID syntax and target path absence;
- complete one-to-one instance mapping and canonical namespace uniqueness;
- no duplicate canonical target or incompatible existing mechanism;
- all connections, interfaces, placements, source selections, and joint binding
  references resolve to mapped canonical instances;
- every required component property and every candidate-defining physical value
  has one intentional promotion classification;
- no design variable, geometry source, connection, placement input, topology
  member, or M10 obligation semantic disappears;
- the resulting canonical mechanism independently validates as a complete typed
  object.

An existing target is not overwritten. The normal `add` path conflict is the
only allowed behavior; no force, merge, or promotion-specific idempotency path
is added.

### Promotion Classifications

Every relevant source value is classified as exactly one of:

- `ACCEPTED_PHYSICAL_FACT`;
- `ACCEPTED_DESIGN_CHOICE`;
- `CANONICAL_REDERIVATION_INPUT`;
- `PROVENANCE_ONLY`; or
- `DO_NOT_PROMOTE`.

Component properties preserve their actual M12-2 availability and
`ComponentPropertyAuthority`; selection never upgrades authority. Missing and
not-applicable properties remain so. A derived M12-3 suitability/admissibility
conclusion is never a component property.

Candidate design variables become accepted design choices, with provenance that
distinguishes a candidate-local choice, an explicit policy assumption accepted
as a choice, a source-backed fixed value, and a deterministic relation. Derived
M12-3 values are not promoted merely because they influenced evaluation; their
independent source/design inputs are promoted instead.

Policy provenance is checked by classification, never by Python truthiness. Any
candidate-defining value classified as `POLICY_ASSUMPTION`, including `0`, `0.0`,
or `false`, either has an explicit `ACCEPTED_DESIGN_CHOICE` mapping retaining
`explicit_policy_assumption` provenance or makes the mapping incomplete and
promotion fails. The current M12-3 policy's exact design-variable admission is
recorded as admission provenance; it does not by itself relabel a candidate-local
choice as source authority. M12-4 scope policy assumptions cannot become a
canonical obligation without an explicit supported classification; the initial
implementation rejects otherwise-unrepresentable scope policy assumptions.

### Geometry And Placement

The selected canonical `GeometrySourceReference` is a physical source choice.
Its `artifact_id` and declared content hash identify the source; ArtifactStore
byte verification establishes integrity. Candidate CAD realization artifacts do
not become geometry sources.

Canonical placement semantics originate only from accepted design variables,
accepted interfaces/frame definitions, selected source geometry, deterministic
relations of those inputs, or explicitly promoted policy-origin choices. M12-4
CAD realization validates that these values were consistently realizable, but
its request/result identities and transient placements are not placement
authority. Promotion selectively compiles the underlying canonical placement
facts and relations after validating the candidate mappings.

## Promotion Readiness And Generic Atomicity

Immediately before compilation, readiness validation revalidates:

- candidate integrity and currentness;
- synthesis request/policy binding;
- exact M12-3 result identity and `ADMISSIBLE` status;
- exact evaluation identity/currentness, `FEASIBLE` outcome, and no required
  unresolved finding;
- selection integrity, candidate/evaluation/source binding, and comparison flag;
- comparison integrity/currentness/membership when used, and its absence when
  not used;
- source revision/hash equals the current canonical state;
- every promoted trusted geometry source through ArtifactStore;
- promotion policy, mapping identity, and target collision conditions.

Readiness failures are pre-application failures: they create no proposal
application, revision, or canonical mutation.

The current ChangeEngine separates `prepare_proposal()` from
`StateManager.create_revision()`, so M12-5 requires a generic ChangeEngine
correctness correction. `StateManager.project_lock` is an existing re-entrant
`threading.RLock` plus process file lock. ChangeEngine will acquire that existing
lock, reread the current pointer, validate the proposal's base revision/hash,
validate ownership and resulting state, create the immutable revision/current
pointer, and release the lock as one generic operation. Nested
`StateManager.create_revision()` locking remains re-entrant. There is no
promotion lock, second lock hierarchy, rebase, or retry against a new state.

All existing ChangeEngine callers retain this stronger invariant: no caller can
validate base N and accidentally write a revision from N after another writer
has advanced the project.

## Frozen Promotable Projection

Before mutation, `CandidatePromotionCompiler` creates an immutable
`PromotableMechanismProjection` and deterministic projection hash. It contains
only the exact expected surviving semantics:

- canonical instance IDs and mapping;
- promoted specification/property snapshots and authorities;
- accepted design choices;
- physical components, interfaces, connections, and topology;
- placement-defining canonical inputs;
- geometry-source selections;
- physical-to-joint binding; and
- canonical M10 obligation.

It excludes evaluation, candidate CAD, M10, comparison/ranking, temporary
execution identities, timestamps, run IDs, and runtime paths. The projection is
bound into compilation and selected-decision provenance before ChangeEngine
application.

After promotion, canonical reconstruction produces the same normalized
projection from `DesignState`; the verifier compares it to the pre-application
projection hash. It therefore does not load a `MechanicalDesignCandidate` as
authority after promotion. The candidate may disappear after the decision
manifest is published without preventing canonical reconstruction or round-trip
verification.

## Deterministic Proposal And Provenance

The compiler is pure with respect to state mutation and external execution. For
the same base state, selected records, target ID, policy, and mapping it emits
the same canonical mechanism, projection, proposal operations, and compilation
hash. It computes a deterministic `promotion_proposal_hash` from the exact base
binding and canonical operation semantics. This semantic identity is distinct
from `ChangeProposal.id`, ChangeSet IDs, and run IDs unless a future generic
ChangeProposal contract explicitly guarantees equivalence. Operational IDs remain
correlation records and are excluded from promotion semantic hashing.

The precise ordering is:

```text
revalidate readiness
    -> compile canonical mechanism, projection, and exact proposal
    -> publish SelectedCandidateDecisionManifest
    -> fresh byte-verify decision artifact
    -> RunController.apply_approved_proposal
    -> ChangeEngine atomically applies exact expected base
    -> obtain new revision/hash and invalidation record
    -> publish CandidatePromotionResultManifest
    -> fresh byte-verify result artifact
    -> canonical reconstruction and verification
```

`SelectedCandidateDecisionManifest` is immutable and pre-application. It binds
at least promotion request, candidate, evaluation, selection, comparison flag
and result when used, base revision/hash, promotion policy, compilation hash,
`promotion_proposal_hash`, promotable projection hash, and candidate-to-
canonical mapping. It does not claim an applied promotion or resulting revision.

`CandidatePromotionResultManifest` is a separate immutable post-application
artifact. It binds the decision artifact, exact proposal identity, ChangeSet/
application identity where available, changed paths, resulting revision, and
resulting state hash. The manifests use existing `ArtifactStore` JSON records,
not Evidence and not a new promotion store. Fresh resolution byte-verifies the
artifact, strictly parses its schema, recomputes self-contained identities, and
verifies historical source bindings.

If the decision artifact cannot be published or fresh-verified, ChangeEngine is
not called. If ChangeEngine rejects the proposal, no new revision exists. If
ChangeEngine succeeds but result-manifest publication or verification fails, the
returned outcome is explicitly `PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED`.
The new revision remains durable and truthful, but full M12-5 promotion success
is not claimed and no rollback occurs.

Historical artifact integrity is distinct from currentness. A valid historical
decision/result remains verifiable after state advances; it cannot authorize a
new promotion. Every new promotion repeats currentness and expected-base checks.

### Historical Manifest Verification

Pre-application readiness is the only phase that requires transient candidate,
evaluation, selection, M12-3 result, and optional comparison objects. It
freshly verifies their integrity and currentness before freezing the exact
promotable semantics.

Historical manifest verification does not require those transient objects to
remain available. It freshly verifies decision/result manifest bytes, schema,
base project/revision/state identity, durable promotion request representation,
promotion policy, compilation hash, `promotion_proposal_hash`, promotable
projection, candidate-to-canonical mapping, durably resolvable geometry source
artifacts, referenced decision/result artifacts, and resulting revision/state
binding where applicable. Candidate/evaluation/selection/comparison hashes are
historical provenance references, not prerequisites for fresh readiness
reconstruction. An explicitly published M12-2 candidate may be cross-verified
as optional additional provenance but is not required. No CandidateStore or
automatic exploration-record publication is introduced.

### M11 Target Intent And Post-Promotion Request

The decision manifest binds `PostPromotionM11TargetIntent` when one was
supplied. It never binds a nonexistent future `CanonicalM11HandoffRequest`.
Only after ChangeEngine success, result-manifest publication/verification, and
canonical reconstruction succeeds does the handoff service resolve the intent
through the frozen candidate-to-canonical instance mapping. It then constructs a
new `CanonicalM11HandoffRequest` bound to project, promoted revision/state hash,
canonical target identity, canonical mechanism identity/hash, and requested M11
eligibility scope/version.

If the intended candidate target was not promoted, has no mapping, maps
ambiguously, or maps to a different canonical mechanism, post-promotion handoff
request construction fails closed. The service never infers a target by name,
role, largest body, or CAD instance ID.

## RunController And Dependency Invalidation

Promotion uses the normal `RunController.apply_approved_proposal()` path only
after verifying its existing contract: it calls ChangeEngine, records revision
advance, writes the dependency invalidation record, and blocks the normal run if
invalidation persistence fails. Run lifecycle correlation is operational only;
run IDs are excluded from promotion semantic hashes.

If ChangeEngine created the revision but RunController invalidation persistence
then fails, the promotion result is explicitly post-application operational
failure (`PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED`). The new
revision remains; promotion is not described as pre-application failure, no
rollback occurs, and result-manifest publication/canonical verification do not
proceed as a fully completed promotion. Only successful invalidation persistence
permits result-manifest publication. This is separate from
`PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED`, which occurs after successful
invalidation when result-manifest publication or verification fails.

M12-5 adds dependencies at the most precise path granularity supported by the
existing prefix/wildcard graph. Initial analysis records bind the exact
consumed `/physical_mechanisms/<id>` path and mechanism hash. Dependency rules
use mechanism-specific path prefixes where configuration can name a mechanism;
the generic graph cannot express a dynamic relation from arbitrary mechanism ID
to arbitrary Evidence record. Where a configured wildcard family is necessary,
it is documented as family-level invalidation rather than claimed per-analysis
precision. It invalidates only the existing relevant nodes:

- `analysis.continuous_clearance_proof` for canonical single-axis M10 proof;
- `analysis.kinematic_sweep` for canonical home checks; and
- `analysis.structural` only for a canonical structural target whose declared
  definition consumes the mechanism path.

No opaque dirty flag or M12-specific invalidation system is added.

## Independent Canonical Reconstruction

`CanonicalPhysicalMechanismCompiler` accepts only an exact canonical
`DesignState` revision/hash, canonical mechanism entry, and trusted source
artifacts referenced by that state. It validates the typed mechanism, source
choice bindings, component/property authority, topology, placement relations,
joint binding snapshot, and M10 obligation. It returns an immutable canonical
reconstruction and normalized projection hash.

It must not read a candidate, selection, evaluation, candidate CAD realization,
candidate M10 result, comparison result, or candidate artifact as engineering
authority. Historical references may be checked only as provenance.

## Fresh Canonical CAD And M10

`CanonicalPhysicalCadCompiler` consumes the canonical reconstruction, not a
synthetic candidate. It may reuse lower-level deterministic CAD mapping and
assembly primitives only where authority input is explicit. It creates a new
canonical physical-to-CAD mapping and a new canonical CAD request/realization
identity bound to project, promoted revision/state hash, canonical mechanism
hash, placement semantics, fidelity, compiler version, mapping, and freshly
byte-verified trusted STEP source content.

Source STEP artifacts may be reused only as sources explicitly selected by the
canonical mechanism and freshly verified via ArtifactStore. Candidate CAD
requests/results, candidate temporary geometry, candidate assembly IDs, and
candidate caches are never reused as canonical CAD. Imported STEP continues to
mean the complete artifact; all valid top-level shapes participate.

`CanonicalM10VerificationService` derives a new physical-to-CAD disposition,
pair inventory, and M10 request from the canonical obligation and fresh CAD
mapping. It invokes the unchanged M10 single-axis service with the new revision
and state hash. Candidate and canonical M10 request hashes must differ even when
the physical obligation is equivalent.

The candidate M10 scope is normalized only before promotion to compare the
canonical obligation. Scope equivalence compares joint meaning, interval/path,
clearance, physical pair classifications, required home semantics, and fidelity,
not candidate/CAD request hashes. The pre-mutation normalized scope projection is
durably bound so future canonical re-verification does not need the candidate.

External spur promotion preserves distinct driver/driven identities and the gear
mesh semantic connection. Driver internal motion remains `INTERNAL_MOTION_UNMODELED`;
promotion does not create gear coupling, ratio joints, counter-rotation, phase,
backlash, or a transmission-internal clearance claim.

## Post-Promotion Verification Outcomes

`PromotedMechanismVerificationResult` is immutable derived provenance, not
canonical authority. It binds promotion result, promoted revision/hash,
canonical reconstruction, projection-equivalence result, canonical CAD request/
realization, canonical M10 request/result identities, scope-equivalence result,
optional M11 handoff, status, and deterministic hash.

An M11 handoff assessment is not an automatic M12-5 verification gate. The
initial result is `VERIFIED` when the declared post-promotion CAD/M10 obligation
passes even if an optional M11 assembly handoff is `NOT_ELIGIBLE` or an optional
single-solid handoff is `UNRESOLVED`. Only a future explicit canonical
requirement making structural verification mandatory may cause an M11 handoff
outcome to block that broader required verification claim.

Statuses remain distinct:

- `VERIFIED`: promotion provenance completed, round trip matches, scope is
  equivalent where that claim is made, and fresh canonical M10 is
  `VERIFIED_CLEAR`;
- `ENGINEERING_VIOLATION`: promotion completed and fresh M10 found a
  `COLLISION_WITNESS`;
- `UNRESOLVED`: promotion completed but fresh M10 is `NOT_PROVEN`, required
  scope equivalence fails, or required verification is otherwise unresolved;
- `INTEGRITY_FAILURE`: canonical/reconstruction/source/result identity trust
  checks fail; and
- `OPERATIONAL_FAILURE`: CAD/backend/publication/runtime work fails without an
  engineering witness.

Promotion is never rolled back after ChangeEngine success. A later corrective
proposal may supersede the revision.

## M11 Eligibility-Only Handoff

M11 is strictly post-promotion. If no `PostPromotionM11TargetIntent` was
supplied, no handoff assessment is required. Otherwise the post-promotion
`CanonicalM11HandoffRequest` identifies an explicit mapped canonical target;
no target is inferred by name or part size. The eligibility service binds the
new canonical revision/hash and returns a typed handoff assessment without
fabricating structural inputs.

- `NOT_ELIGIBLE` means the requested target is outside accepted M11 scope even
  if further authority existed, such as a whole mechanism/assembly, multi-body
  target, or unsupported analysis kind.
- `UNRESOLVED` means the explicit target could be a supported single solid but
  lacks canonical material, load, support, region, structural-definition, or
  other required authority.
- `ELIGIBLE` requires one supported canonical solid, trusted persistent geometry,
  complete structural definition, material/property authority, semantic regions,
  loads, supports, and a new request bound to the promoted revision.

The primary direct-drive capstone proves both non-executing cases while retaining
a `VERIFIED` bounded CAD/M10 result: whole mechanism target is `NOT_ELIGIBLE`;
an explicit candidate-independent canonical mount/support single-solid target
without structural authority is `UNRESOLVED`; and neither executes M11. If an
independently complete canonical structural definition exists, any later
execution must compile/export a new persistent canonical STEP artifact, create a
new canonical `StructuralAnalysisDefinition`/request bound to the promoted
revision, and use unchanged M11 semantics. It still proves only that one solid,
not whole-mechanism safety.

## Failure Rules

Before ChangeEngine, stale/forged/mismatched candidate, result, evaluation,
selection, comparison, geometry source, property, design variable, mapping,
target collision, or incomplete projection fails with no revision change.

At ChangeEngine, stale base, ownership, operation, path, or resulting-state
failure creates no new revision. Post-application CAD/M10/M11/provenance failure
preserves the new revision and returns its truthful derived status. Replaying the
same selection after the source advances fails stale/base-state validation and
cannot duplicate the mechanism.

## Test And Live Acceptance Scope

Focused tests must cover canonical schema/ownership, complete mapping, property
authority preservation, policy-origin zero-value classification, collision and
namespace failure, readiness substitution/tamper failures, generic ChangeEngine
stale-base race protection, pre/post manifest ordering, reconstruction without a
candidate, projection round trip, fresh source-byte CAD, fresh M10 identity/scope
semantics, collision/not-proven/operational outcomes, invalidation behavior,
replay, direct-drive and external-spur topology, both M11 handoff outcomes, and
proposal semantic tamper rejection when an operational proposal ID is reused
with changed operations.

The live direct-drive capstone must use an accepted M12-4 feasible selected
candidate and trusted imported STEP source, create exactly one ChangeEngine
revision, fresh-reload both promotion artifacts, prove semantic round trip,
freshly execute canonical FreeCAD/M10, and reject replay. It records pre-,
promotion-, and post-promotion identities without copying candidate proof into
canonical authority. Full-suite, compile, diff, and untracked-file whitespace
checks remain required before any verified milestone claim.

## Non-Goals

M12-5 does not add general mechanism synthesis, automatic selection, candidate
approval, candidate-as-canonical authority, generic catalogs, optimization,
assembly/contact FEA, gear coupling, driver-gear kinematics, bearing life, gear
strength, fatigue, thermal analysis, tolerances/GD&T, manufacturing approval,
configuration-space certification, M11 redesign, fabricated M11 authority, or
M12-6 acceptance work.

## Specification Self-Review

This specification explicitly rejects candidate dependency after promotion,
missing pre-mutation projection, mutable decision artifacts, ambiguous
post-application provenance failure, candidate-specific policy content, direct
state mutation, stale-base rebase, candidate CAD/M10 replay, candidate-dependent
canonical scope, fabricated M11 inputs, pre-promotion canonical M11 requests,
and M12-6 scope creep. The existing
dependency graph cannot dynamically associate arbitrary path IDs with arbitrary
Evidence without configured rules; that known precision limit is documented and
is not hidden by an M12-specific invalidation mechanism.

## Final Design Marker

`M12_5_PROMOTION_CANONICAL_REBIND_M11_HANDOFF_SPEC_READY`
