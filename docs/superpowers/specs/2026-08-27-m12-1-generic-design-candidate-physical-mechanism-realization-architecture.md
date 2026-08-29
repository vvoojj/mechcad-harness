# M12-1 Generic Design Candidate & Physical Mechanism Realization Architecture

**Date:** 2026-08-27

## Status

Architecture/design only. This document does not implement candidate generation,
component selection, physical-joint sizing, CAD, M10/M11 integration, or a new
production entrypoint. It does not change the accepted M10 or M11 contracts.

## Purpose

M12 defines the future architecture for moving from accepted engineering
requirements to one or more physical mechanical alternatives, evaluating those
alternatives deterministically, selecting one explicitly, and promoting only the
selected accepted facts through the existing `ChangeProposal -> ChangeSet ->
ChangeEngine -> DesignState` path.

The initial target is a physically embodied revolute drive, not generic machine
design: motor, bounded transmission, driven member, support bearings, hub or
coupling, mounts, and a rigid driven body.

## Accepted Baseline

M12 reuses, without replacement:

- `DesignState`, immutable revisions/state hashes, authoritative parameters,
  ownership, `ChangeProposal`, `ChangeSet`, `ChangeEngine`, dependency
  invalidation, `RunController`, `ToolBroker`, and agent boundaries;
- `ArtifactStore`, `EvidenceStore`, `ProductionApplication`, generic CAD
  programs/assemblies, trusted `ImportedCadComponent`, and FreeCAD backends;
- M10's `KinematicModel`, `RevoluteJointModel`, FK, exact discrete collision,
  and explicit-path clearance proof;
- M11's source-bound single-solid linear-static analysis and structural Evidence;
- narrow M7 synthesis services as reference patterns only.

The accepted predecessor markers are `M10_FULLY_CLOSED_LIVE_VERIFIED`,
`M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CONSISTENCY_VERIFIED`, and
`M11_FULLY_CLOSED_LIVE_VERIFIED`.

## Existing Capability Reuse

`CadAssemblyProgram` already preserves ordered component-instance identity and
rigid placement. M12 compiles to it rather than introducing a mechanism CAD
backend. `ImportedCadComponent` remains the trusted representation of an entire
byte-verified STEP artifact, including all its top-level shapes.

M10 remains the only kinematic/collision/clearance authority. It receives a
candidate-derived assembly, an unchanged generic kinematic model, explicit
configurations or path, and an explicit collision-pair inventory. M12 does not
restate collision classes, continuous-proof statuses, or geometric measurements.

M11 remains a canonical, source-bound, one-homogeneous-solid structural path.
M12 does not turn a candidate or a rigid assembly into a structural connection
model.

## Problem Statement

An M10 revolute joint defines parent/child instances, axis, origin, and optional
limits. It does not mean motor, bearing, shaft, mount, load path, gear mesh, or
structural connection. Existing component metadata and motor characteristics are
partial authority inputs, not a physical-component catalog or sizing system.

M12 therefore adds a separate noncanonical physical-realization layer. It binds
one abstract joint to one possible physical embodiment while permitting several
different embodiments of the same M10 joint.

## Architecture Principles

- `DesignState` remains the sole canonical engineering authority.
- A candidate is an alternative derived from authority, never a shadow revision.
- Candidate generation never fills an unresolved fact with a guessed value.
- Property authority is per consumed component property, not per catalog or part.
- CAD, providers, agents, analyses, artifacts, Evidence, ranking, and selection
  are distinct from canonical approval.
- A physical interface, kinematic relation, CAD placement relation, and
  structural connection are different declarations. No one implies another.
- Semantic identities use canonical JSON and SHA-256; `run_id` is storage and
  correlation scope only.
- Integrity failures and tool/provider failures are not engineering infeasibility.

## Architecture Options Considered

| Option | Assessment | Decision |
| --- | --- | --- |
| A. Candidate-centric | An immutable candidate owns one topology/realization and binds evaluation, CAD, and promotion inputs through stable hashes. It supports sibling alternatives and lineage without granting authority. | Selected. |
| B. Proposal-centric | Treating `ChangeProposal` as the alternative makes unaccepted alternatives look like canonical patch sets, cannot naturally retain unresolved inputs, and couples exploration to mutable state paths too early. | Rejected. A proposal is the promotion output, not the candidate. |
| C. Graph-centric wrapper | Making the graph the primary public identity undervalues source binding, design variables, component snapshots, feasibility, and promotion provenance. A graph alone is insufficient for comparison and audit. | Rejected as primary model. The graph is the candidate's physical realization. |

## Selected Architecture

```text
canonical DesignState
    -> source-bound CandidateSynthesisRequest + CandidateSynthesisPolicy
    -> immutable noncanonical MechanicalDesignCandidate
         -> PhysicalMechanismRealization
         -> deterministic candidate evaluation
         -> optional transient CAD and M10 references
    -> optional published candidate record
    -> CandidateComparison / explicit CandidateSelection
    -> ChangeProposal -> ChangeSet -> ChangeEngine
    -> new canonical DesignState revision
    -> recompile/rebind CAD, M10, and eligible M11 verification
```

`MechanicalDesignCandidate` is the selected name. It is specific enough to
avoid collision with arbitrary configuration candidates while remaining generic
across rotary mechanisms, stages, mounts, gearboxes, and future domains.

## Candidate Authority Model

A candidate is immutable after construction and content-addressed by
`candidate_hash`. It binds:

- `CandidateSourceBinding`: `project_id`, source revision, source state hash,
  and ordered identities/hashes of consumed authoritative requirements,
  constraints, interfaces, parameters, and selected canonical component/material
  facts;
- `synthesis_request_hash` and `synthesis_policy_hash`;
- one `PhysicalMechanismRealization` hash;
- candidate-local design-variable values and their declared roles;
- normalized component-specification snapshot hashes;
- explicit unresolved items and optional parent-candidate derivation;
- generator identity/version and deterministic candidate schema version.

Candidate-local values may vary only where the synthesis request/policy declares
them as design variables or alternatives. They may not override source-bound
requirements, constraints, interface facts, or canonical component/material
authority. A conflict is invalid candidate construction, not a candidate choice.

Several siblings may bind the same source. They remain separately identifiable
because topology, component snapshots, permitted variables, policy, or generator
inputs differ. A candidate may be historically internally valid after the
canonical state advances; it is then stale, not corrupted.

## Candidate Identity And Source Binding

Candidate identity excludes timestamps, run IDs, temporary paths, evaluation
results, and runtime, publication, or derived-result artifact IDs. An explicitly
selected `GeometrySourceReference.artifact_id` contained in a component
specification is a candidate-defining geometry-source identity under accepted
M12-2 semantics; this narrow exception does not extend to arbitrary artifact
IDs. Candidate identity includes all semantically candidate-defining inputs.
Evaluation, CAD realization, comparison, selection, and proposal each have their
own deterministic hash and explicitly name the candidate hash they consume.

`CandidateCurrentness` is evaluated separately from integrity and engineering
outcome:

- `CURRENT`: the exact bound revision/state hash is still current and all
  declared dependency bindings remain valid;
- `STALE_RELATIVE_TO_CURRENT_STATE`: a newer canonical revision changes an
  input/dependency relevant to the candidate;
- `CURRENTNESS_UNAVAILABLE`: current state or invalidation history cannot be
  verified;
- integrity failure is a separate failure, never a currentness value.

The initial implementation should use explicit consumed canonical paths plus the
existing dependency graph, rather than infer relevance from arbitrary prose.

## Candidate Lifecycle

1. A caller creates a source-bound request and policy from canonical authority.
2. A deterministic enumerator or validated agent proposal creates candidate
   definitions. Missing authority produces unresolved items/constraint requests.
3. Deterministic services validate, size only supported elements, evaluate, and
   optionally realize CAD/M10 analysis.
4. Exploratory candidates remain transient by default.
5. A user/service may explicitly publish an immutable candidate definition and
   evaluation manifest for audit or comparison.
6. If comparison is requested, a comparison request binds the ordered candidate
   and evaluation set to the comparison policy; comparison produces an immutable
   result.
7. An explicit selection, optionally informed by that comparison, produces a
   non-authoritative selection record. Selection may also be made without any
   comparison result.
8. A proposal compiler translates the selected, fully promotion-ready candidate
   into a normal `ChangeProposal`.
9. `ChangeEngine` alone decides whether a new canonical revision is created.
10. The accepted revision is recompiled and reverified under canonical bindings.

Refinement is candidate iteration, not `RunController` canonical iteration. A
derived candidate may record `parent_candidate_hash`, a nonempty derivation kind,
and an optional deterministic generation ordinal. Parent linkage is provenance,
not inheritance of results; C2 must have its own candidate/evaluation hashes.

## Candidate Persistence Decision

The decision is hybrid: candidate definitions and evaluations are transient by
default and become durable only through explicit publication. This avoids
hundreds of exploration records while allowing an audited comparison or selected
decision to be reproduced.

Published candidate definition and evaluation manifests are immutable JSON
artifacts in the existing `ArtifactStore`, with the candidate hash as semantic
input binding and normal project/revision/backend provenance. A future thin
`PublishedCandidateResolver` may validate and load those artifacts, but it is not
a second canonical-state database or a new store. It must use `ArtifactStore`
byte verification and reject ambiguity exactly as other trusted artifacts do.

Candidate publication is not Evidence by itself. An explicitly published
selection decision or final post-promotion verification may use existing generic
`EvidenceStore` semantics only when a declared dependency node and a computation
fact warrant it. Exploratory candidates must not create one artifact/Evidence
record per CAD sample, M10 configuration, or generator attempt.

## Synthesis Request And Policy

`CandidateSynthesisRequest` is a source-bound derived execution request, not
canonical authority. It declares the source binding, authoritative input
identities, requested mechanism scope, required realization targets, and
requested evaluation categories.

`CandidateSynthesisPolicy` is a separately hashed policy/configuration. It may
contain allowed architecture templates, allowed component families, preferred
manufacturers, allowed transmission kinds, explicit variable bounds, candidate
count, search/resource budget, and comparison-policy identity. It must label
each field as either hard admissibility policy, preference, or execution limit.

Requirements and constraints belong in canonical authority. Policy is a user or
workflow preference/execution input unless an explicit future proposal promotes a
policy fact into canonical state. Different policies may produce different
candidates from the same source without changing the source state.

## Physical Component Authority

M12 should add component authority as an immutable snapshot boundary, not a live
catalog object. The minimum future contracts are:

- `ComponentSpecificationSnapshot`: component identity/type, manufacturer and
  part number when known, source identity, normalized property snapshots,
  geometry-source references, compatibility/interface declarations, and snapshot
  hash;
- `ComponentPropertySnapshot`: property name, status, normalized value or range,
  unit, source identity, property-specific authority, applicability/context, and
  conversion provenance;
- `PhysicalComponentInstance`: candidate-local instance ID, specification
  snapshot hash, role, and placement/interface references.

Property availability must distinguish `AVAILABLE`, `MISSING`, and
`NOT_APPLICABLE`; no missing numeric value becomes zero, midpoint, default, or
an engineering conclusion. A property snapshot describes source data and
authority only. Component suitability belongs to a declared deterministic
compatibility, sizing, or admissibility result, which may conclude suitable,
unsuitable, or unresolved for the specific candidate and check.

For example, an `AVAILABLE` bearing dynamic-load rating does not establish that
the bearing is suitable. Missing property data remains unresolved, and a tool,
integrity, or authority failure is not converted into an unsuitable component or
an engineering violation.

The implementation should reuse M11's property-specific authority approach and
existing `MaterialDataAuthority` values where their meanings apply, while adding
a component-property authority enum only if material-specific names are not
sufficient. One part number cannot elevate all its properties to equal authority.

## Component Catalog Boundary

Catalog search, normalized specification, accepted authority, and candidate
selection are four separate stages:

```text
datasheet / local verified entry / provider response
    -> normalized ComponentSpecificationSnapshot
    -> candidate instance reference
    -> explicit canonical promotion if selected
```

An external catalog adapter is a derived provider behind the existing provider
and ToolBroker/production-service boundaries as appropriate. It can return
search results or suggested normalized snapshots, never canonical selection or
unverified values. A local manually entered verified snapshot and a manufacturer
datasheet are equally representable, provided every consumed property states its
source and authority. Imported STEP is geometry evidence and may accompany a
specification; it does not establish torque, rating, mass, material, or interface
facts not declared by property snapshots.

## Physical Mechanism Topology

`PhysicalMechanismRealization` is a typed, ordered graph of component instances
and `MechanicalConnection` records. Its semantic graph is separate from a CAD
assembly graph and from the M10 kinematic tree.

Initial component roles are actuator, transmission, rotating member/shaft,
bearing, hub/coupling, mount/housing/support, driven rigid body, and payload or
frame attachment. A node may be purchased, generated, or imported; each records
its source/specification identity without making that source authoritative.

The graph permits motor-to-transmission drive, transmission-to-shaft drive,
shaft-to-hub connection, bearing support of a shaft, gearbox mounting to frame,
and payload attachment to a driven body. It must validate unique IDs, endpoint
existence, compatible declared interface roles, and topology constraints specific
to each connection kind. It must not infer bearing count, load sharing, gear
ratio, or structural support from a graph edge.

## Mechanical Interface Model

`MechanicalConnection` has a stable ID, kind, endpoint instance/interface IDs,
directionality where meaningful, declared frame/placement reference where
needed, and connection-specific semantic fields. Initial kinds are:

- fixed attachment;
- rotational drive;
- coaxial connection;
- shaft journal;
- bearing support;
- gear mesh;
- coupling;
- motor mount;
- payload attachment;
- structural support declaration.

Each connection declares which of these meanings it has: kinematic realization,
torque/load-path intent, CAD placement/mating intent, and structural relevance.
The structural-relevance flag is descriptive only in M12; it neither creates an
M11 connection nor admits assembly FEA. A gear mesh may define a ratio design
intent and a CAD placement relation but does not imply tooth-contact analysis,
backlash, efficiency, strength, or structural contact.

## M10 Joint Physical Realization Binding

`JointPhysicalRealizationBinding` maps exactly one existing M10 `joint_id` to a
candidate-local realization subgraph and declares the driven member, reference
axis/frame correspondence, actuator/transmission path, support/bearing members,
output hub/coupling, mounts, and explicit load-path metadata availability.

It validates that the referenced M10 joint and candidate components exist and
that axis/frame correspondence is explicit. It does not mutate or extend
`RevoluteJointModel`. A candidate can omit a binding for a joint outside its
scope only when the synthesis request marks that joint out of scope; a required
joint without a binding is unresolved/incomplete, not silently direct drive.

Different candidates may bind the same joint to direct drive, motor plus
reducer, or a motor plus external spur pair. All retain the same abstract M10
joint where their output axis/range semantics match. M10 validates motion;
physical-realization validation separately validates only supported embodiment
claims.

## Physical Engineering Requirement Boundary

Authoritative inputs include stated output speed/range, required continuous or
peak torque, duty, payload, acceleration assumptions, radial/axial loads,
voltage, envelope, mass limit, interfaces, and preferences only when provided.
Candidate design variables include a supported ratio, tooth counts, shaft
diameter, bearing selection, mount dimensions, and component alternatives.

Derived requirements may be calculated only by a declared deterministic service
from explicit authoritative inputs. Missing torque, duty, acceleration, wind,
loading, voltage, material, or component property remains an unresolved item or
a `ConstraintRequest`. A policy preference is neither a hard requirement nor a
design variable until explicitly classified.

## Deterministic Service Responsibilities

Trusted deterministic services own normalization, hashes, topology validation,
supported numerical sizing, compatibility checks, candidate CAD compilation,
M10 invocation, result-reference validation, comparison, proposal compilation,
and persistence validation. Services use existing `ToolBroker`, providers, and
`ProductionApplication` composition where their caller contract requires it;
they do not introduce a parallel provider registry.

`BuiltinTools` may support explicit torque, spur geometry, and envelope checks.
`GearworksTools` and py_gearworks/build123d may support bounded external spur
geometry/CAD. `MaterialTools`, `SectionTools`, and `SectionEngineeringTools` may
provide authority-preserving material/section inputs to future supported checks.
Their current optional/unwired status and narrow semantics remain honest: none
provides motor, bearing, shaft, gearbox, fatigue, efficiency, or optimization
authority by implication.

## Agent Responsibilities

Agents may propose a structured topology using known component families, flag
unresolved inputs, request an allowed deterministic calculation, explain
tradeoffs, and propose a selection. They may not fabricate properties, perform
hidden sizing, choose missing requirements, upgrade feasibility, assert M10/M11
verification, write candidate hashes/provenance identities, mutate state, or
call providers outside authorized mediation. An agent-proposed topology is
validated as untrusted candidate input before it can be evaluated.

## Candidate Generation

The first implementation direction is hybrid and deliberately not optimization:

1. deterministic, bounded realization templates enumerate supported topologies;
2. an agent may choose among declared templates or submit a structured topology;
3. deterministic admission and engineering evaluation accept, reject, or mark it
   unresolved.

The initial templates are direct drive and an external spur-gear reduction. No
generic optimizer, unrestricted topology search, SciPy dependency, or LLM search
loop is required. Future optimization is a separate layer that consumes this
candidate/evaluation contract and always emits ordinary noncanonical candidates.

## Candidate Evaluation

`CandidateEvaluation` is an immutable derived record bound to candidate hash,
evaluation-policy hash, exact input snapshot hashes, evaluator versions, and
result references. It aggregates only references or normalized summaries from
supported checks: authority completeness, topology/component compatibility,
supported sizing, packaging/mass, CAD realization, M10 results, and explicitly
declared unresolved items.

Compatibility, sizing, and admissibility results own component suitability for
their declared candidate, requirements, inputs, and evaluator version. Property
availability alone cannot make a component pass or fail such a result.

M10 result semantics are never copied into aggregate enums. The evaluation
stores M10 result/Evidence identities and a relevance summary such as
`M10_REFERENCE_MISSING` or `M10_RESULT_PRESENT`, leaving interpretation to the
original result type. M11 has no candidate-bound result reference before
promotion. Candidate CAD/evaluation identity includes the candidate hash and
compiler/evaluator inputs so CAD from candidate A cannot be attached to candidate
B.

## Feasibility Semantics

Candidate feasibility is an aggregate decision with three engineering states:

- `FEASIBLE`: every required supported check has a valid passing/satisfying
  result and no required authority is unresolved;
- `INFEASIBLE`: valid supported engineering evaluation establishes a hard
  requirement or admissibility violation;
- `UNRESOLVED`: required authority, unsupported required check, or a required
  result is unavailable without a valid violation witness.

`EVALUATION_FAILED` and `INTEGRITY_FAILURE` are separate operational/integrity
outcomes and cannot be recast as `INFEASIBLE` or `UNRESOLVED`. A candidate can be
feasible only for its declared evaluation scope; it is never a general approval.
Missing property data is an unresolved authority/input, not an unsuitable
component or infeasibility witness.

## Candidate Comparison And Ranking

`CandidateComparisonPolicy` is an optional hashed, noncanonical policy input that
defines comparator semantics only: metric definitions and order,
`MINIMIZE`/`MAXIMIZE` directions, expected units, admissibility requirements,
missing-value behavior, tie semantics, and comparator implementation/version. It
does not own the concrete candidates or evaluations being compared.

`CandidateComparisonRequest` is the separate execution/input binding. It
contains source binding where required, ordered candidate hashes paired with
their exact evaluation hashes, the `candidate_comparison_policy_hash`, and a
deterministic request hash. The candidate/evaluation set belongs only to this
request. The same policy with different candidates therefore has the same policy
hash but a different request/result identity; changing the policy or any
evaluation changes the request/result identity.

Initial comparison is deterministic lexicographic ordering over explicitly
available metrics after excluding `INFEASIBLE` candidates; it must not invent
weights.

`CandidateComparisonResult`, when used, binds its exact comparison request/hash
and therefore transitively binds the candidate set, evaluation set, and policy;
it records the resulting order and ties. A comparison result is never fabricated
merely to enable selection.
`CandidateSelection` always names the selected candidate, required evaluation,
source binding, selector identity, and rationale. When comparison was used, it
references the exact `CandidateComparisonResult` identity rather than
reconstructing comparison inputs. When no comparison was used, it explicitly
records that comparison was not used and carries no manufactured comparison
result.

Evaluation is distinct from comparison; comparison is distinct from selection;
selection is distinct from approval. Selection without comparison still requires
candidate integrity/currentness, promotion-required evaluation, no unresolved
required authority, and satisfaction of hard engineering constraints. Canonical
approval occurs only through `ChangeEngine`.

Weighted objectives and Pareto presentation are future policy implementations.
They may not hide subjective weights in canonical state or turn a top-ranked
candidate into an automatic proposal/application.

## Candidate CAD Realization And Artifact Policy

A deterministic candidate CAD compiler maps candidate components and connections
to existing source-bound `DesignSpec` compilers, `CadPartProgram`, trusted
`ImportedCadComponent`, and `CadAssemblyProgram`. It preserves candidate
component-instance IDs and records mapping manifests, rather than collapsing the
mechanism into anonymous compounds. New CAD primitives are justified separately;
M12 does not create `MechanismCadBackend`.

Exploratory CAD is transient where M10 only needs temporary geometry. Explicitly
published candidates may publish byte-verified FCStd/STEP and JSON manifests to
`ArtifactStore`. A selected/promoted design uses ordinary canonical-source-bound
durable artifacts after recompilation. No per-candidate-config or per-midpoint
artifacts are published during M10 analysis.

## M10 Integration

A candidate M10 evaluation supplies the candidate CAD assembly hash, existing
`KinematicModel`, explicit joint configurations/path, and collision pair
inventory. The physical realization compiler must show the binding between M10
instances and candidate physical instances, but M10's inputs/results remain
unchanged. Physical realization can be incomplete while the mathematical
kinematics is valid, and valid M10 clearance does not prove actuator sizing,
bearing life, load path, backlash, or manufacturability.

## M11 Integration Decision

Decision: option A, no pre-acceptance M11 analysis. M11 requires canonical
`StructuralAnalysisDefinition`, exact immutable source revision/state binding,
trusted persistent STEP artifact, and one homogeneous solid. A candidate lacks
that canonical authority, and a rigid candidate assembly lacks structural
connection semantics.

Candidate evaluation may report M11 eligibility as unresolved/not applicable,
but may not submit an M11 request, label a structural preview as M11, or reuse
M11 Evidence. After promotion, a separately accepted canonical structural
definition/request may run the unchanged M11 path for an eligible single solid.
Candidate-bound structural preview and an intermediate authority tier are
rejected: both would duplicate/weaken M11 source binding and add an unnecessary
second approval boundary.

## Promotion Boundary And Post-Promotion Reverification

The proposal compiler accepts only an explicitly selected candidate whose source
binding exactly matches the requested base state, whose required promotion inputs
are non-unresolved, whose required evaluation is valid, and whose
published/loaded manifest passes integrity checks when durable references are
used. A comparison is not required; if a selection cites one, its exact
`CandidateComparisonResult` binding must validate, including the transitive
request, policy, candidate-set, and evaluation-set bindings. If no comparison was
used, the selection must explicitly represent that fact. It creates ordinary
`ChangeProposal`
operations for the selected architecture, component specification snapshots,
accepted design variables, interfaces, and provenance references on new typed
canonical paths introduced by later implementation milestones.

There is no `Candidate.apply()`, `Candidate.accept()`, direct state replacement,
or candidate-origin mutation API. ChangeEngine stale/ownership/resulting-state
validation remains authoritative.

Promotion always triggers rebind/recompile/reverification. Candidate-local CAD,
M10 results, and especially M11 results are not canonical verification merely
because values look equivalent. A post-promotion compiler must produce
canonical-source-bound programs/artifacts; M10 must execute against that source
assembly/model request; M11, if eligible, must use a new canonical definition,
request, and artifact binding. Candidate artifacts may be retained as provenance
but cannot satisfy canonical accepted verification by replay.

## Dependency / Invalidation

The candidate, evaluation, CAD manifest, M10 request/result reference, comparison
request/result, and selection each record exact consumed hashes. A changed
canonical input, selected component snapshot/property, geometry artifact, design
variable, compiler, provider, M10 model/config/path, evaluation, comparison
request input, or comparison policy invalidates the dependent derived record by
hash mismatch and/or existing dependency-graph impact. No opaque dirty flag is
allowed.

Source changes make the candidate stale. Candidate-definition changes make its
evaluation and all CAD/M10 references stale. CAD mapping or assembly changes make
M10 stale. A component property change invalidates every sizing/compatibility
check that declares it consumed. A candidate/evaluation-set change invalidates
the comparison request/result; a policy change changes the policy/request/result
identities. A changed evaluation changes the comparison request/result identities.
A changed comparison result makes any citing selection stale. Post-promotion
canonical changes follow existing dependency invalidation and make canonical
CAD/M10/M11 Evidence stale according to their existing contracts.

## Provenance And Trust / Replay Protection

Candidate generator/agent identity, deterministic service and provider identity,
catalog source identity, snapshot hashes, CAD compiler version, artifact hashes,
M10 request/result/Evidence identity, comparison policy identity, comparison
request/result identity, and selection identity are all explicit provenance.
`run_id` is excluded from semantic identities.

The implementation must fail closed on:

- a forged candidate hash or source binding;
- stale candidate used for selection/proposal;
- substituted component-property or geometry snapshot;
- artifact bytes/hash or candidate-manifest mismatch;
- candidate A CAD or M10 result attached to candidate B;
- M10 result replay across model/configuration/path/pair inventory changes;
- any M11 result replay, which is prohibited before promotion and must bind the
  post-promotion canonical state afterward;
- a cited comparison using a stale/foreign evaluation, mismatched policy, or
  mismatched comparison request, candidate set, or evaluation set;
- a selection that omits the required evaluation/source binding or misrepresents
  whether a comparison was used;
- candidate mutation after selection but before proposal generation;
- catalog/provider identity mismatch or unavailable provider.

Integrity errors remain integrity errors. The system does not rehash, repair, or
silently substitute records to recover eligibility.

## Evidence Policy

No new EvidenceStore exists. Ordinary exploration persists no Evidence. An
explicitly published candidate evaluation may publish generic Evidence only for a
declared, complete, deterministic computation fact with candidate/evaluation/
source bindings. A selected candidate decision may be durably recorded as a
published JSON artifact and, where a dependency node is defined, as selection
Evidence. Final engineering verification is the existing post-promotion M10/M11
Evidence, not candidate Evidence relabeled as canonical proof.

## Existing M7 Synthesis Reuse

`AzimuthMountPlateSynthesisService`, `YagiCarrierSynthesisService`, and
`YagiCollisionLayoutSynthesisService` demonstrate useful implementation
patterns: exact source binding, deterministic result hashes, explicit
`NOT_READY`/infeasible states, constrained design variables, and
result-to-`ChangeProposal` translation. The sliding-interface selector
demonstrates explicit alternatives and unresolved inputs.

They remain narrow domain services and future domain adapters/reference-only.
They are not migrated into or superseded by M12 merely to force a universal
abstraction. M12 may reuse their proven proposal and unresolved-input discipline,
not their Yagi/AZ schemas or their direct result shapes.

## Initial Physical Mechanism Scope

The first executable scope is one revolute-drive realization with motor, direct
drive or external spur-pair reduction, a shaft/driven member, bearing support,
hub/coupling, motor/support mount, and rigid driven member. It may consume
existing external spur geometry/CAD only within its accepted narrow limits.

Planetary, worm, bevel, belt, chain, harmonic, cycloidal, and arbitrary
transmissions are extension points, not initial types. Motor, shaft, bearing,
and mount sizing must each obtain their own typed deterministic scope and proof;
listing a component in topology does not claim it is sized or selected.

## Domain Extension Boundary And Antenna Rotator Reference Check

The generic layer contains no AZ, EL, antenna, Yagi, boom, or RF names. A future
`antenna_rotator_v2` adapter can define its payload/load authority and bind AZ/EL
M10 joints to candidate drive realizations containing motors, reductions, shafts,
bearings, hubs, mounts, and frame interfaces. It validates that the model can
represent the reference case without defining the generic schema around it.

Payload wind, acceleration, duty, cable routing, exact product data, structural
connections, and final manufacturing dimensions remain explicit domain inputs or
unresolved items. They cannot be inferred from the existing antenna project.

## Non-Goals

M12-1 and the initial M12 direction exclude assembly/contact FEA, nonlinear or
large-deformation FEA, fatigue, motor thermal simulation, bearing contact/life
simulation, detailed gear contact, lubrication, backlash, flexible-body dynamics,
arbitrary trajectories, configuration-space proof, tolerances/GD&T, topology or
unrestricted global optimization, procurement/order workflows, automatic
canonical approval, and arbitrary mechanism classes.

It also does not implement generic candidate generation, motor/bearing/shaft
sizing, physical joint realization, catalog integration, or candidate ranking.

## Follow-On M12 Milestones

| Milestone | New capability | Existing capability reused | Proof required | Explicit non-goals |
| --- | --- | --- | --- | --- |
| M12-2 | Typed noncanonical candidate, source binding, component/property snapshots, publication manifests, and currentness/integrity checks | hashing, ArtifactStore, ChangeProposal, dependency foundations | deterministic IDs, stale/tamper/substitution tests; no canonical mutation | generation, sizing, CAD/M10/M11 execution |
| M12-3 | Bounded physical revolute realization templates and deterministic admissibility/sizing for direct drive and external spur reduction | Builtin/Gearworks tools, provider boundaries, agent mediation | explicit missing-input, feasible/infeasible, property-authority, and provenance proofs | bearing life, broad transmissions, optimization |
| M12-4 | Candidate CAD compiler and candidate-to-M10 evaluation/comparison/selection path | CadPartProgram, CadAssemblyProgram, FreeCAD, M10, ArtifactStore | live generated/imported physical assembly and exact M10 identity/replay checks | new kinematics engine, M11 preview, automatic approval |
| M12-5 | Promotion compiler, post-promotion canonical CAD/M10 rebinding, selected-decision publication, and eligible M11 handoff contract | ChangeEngine, invalidation, EvidenceStore, M11 unchanged | stale-selection rejection; new revision; canonical re-verification; M11 source-binding preservation | assembly FEA, direct candidate M11 |
| M12-6 | One live end-to-end bounded physical mechanism acceptance | all M12 and accepted M9-M11 paths | real provider/CAD/M10/post-promotion provenance and regression suite | general mechanism synthesis/optimization/manufacturing approval |

## Acceptance Criteria

M12-1 is ready only when later implementation follows these decisions:

- candidates are immutable, noncanonical, content-addressed, source-bound, and
  separately current from internally valid;
- persistence is explicit publication through existing ArtifactStore/EvidenceStore,
  never a second canonical database;
- component property authority and catalog/provider boundaries are per-property
  and fail closed;
- physical realization/topology/interfaces are distinct from M10 kinematics and
  M11 structural connections;
- synthesis policy is separate from canonical requirements and agent output;
- deterministic services own math, validation, identity, provider invocation,
  CAD, and result binding;
- feasibility, operational failure, integrity failure, comparison, selection, and
  canonical approval remain distinct;
- comparison is optional; selection always binds required evaluation and source
  state, and binds the exact comparison result only when comparison was used;
- comparison policy defines comparator semantics only; a separate comparison
  request binds the ordered candidate/evaluation set and policy hash, and the
  comparison result binds that exact request/hash;
- CAD/M10 are reused unchanged; M11 is post-promotion only;
- promotion uses only ChangeProposal/ChangeSet/ChangeEngine and requires
  canonical rebinding/reverification;
- evidence/artifact publication is selective and replay protections are complete;
- the initial scope and non-goals remain bounded.

## Open Questions

These are implementation sequencing questions, not unresolved architecture
decisions:

- Which canonical paths and ownership identities should M12-5 introduce for an
  accepted physical realization, after a focused state-schema/ownership design?
- Which component-property authorities need a generic enum beyond existing
  material authority values, and what source-retention policy is sufficient for
  manufacturer datasheets?
- Which first motor and shaft calculations have independently validated equations,
  input authority, and result semantics suitable for M12-3?
- Which published-candidate JSON manifest granularity best supports comparison
  without duplicating large M10/M11 payloads?

## Final Disposition

`M12_1_GENERIC_DESIGN_CANDIDATE_PHYSICAL_MECHANISM_ARCHITECTURE_READY`
