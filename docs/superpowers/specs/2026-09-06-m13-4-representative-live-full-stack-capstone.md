# M13-4 Representative Live Full-Stack Capstone Acceptance

## Status

**Disposition: `M13_4_BLOCKED_BY_ARCHITECTURE_GAP`.**

This is an acceptance-only specification. It authorizes no production change,
test change, implementation plan, M10/M11/M12/M13 predecessor contract change,
automatic synthesis, Rotator V2 work, commit, tag, push, or release.

The intended M13-4 capstone is fully specified below. It cannot be implemented
as an acceptance-only milestone because the accepted M13-3 multi-joint selection
and promotion chain is not exposed through the real `ProductionApplication`
composition root. Resolving that gap requires a separately reviewed production
composition/dispatch contract; an integration test must not construct internal
services or add a fixture-only route to bypass it.

The proposed success marker, only after the blocker is resolved and every gate
below passes, is:

```text
M13_4_REPRESENTATIVE_LIVE_FULL_STACK_CAPSTONE_VERIFIED
```

## Purpose

M13-4 is not a new mechanics capability. It is the representative live
full-stack acceptance before Rotator V2. It must prove that a physically
meaningful, source-bound, generic multi-joint mechanism follows the accepted
authority chain without candidate-runtime reuse:

```text
source/canonical requirements and selections
  -> supplied M13-1 authority + generated M13-2 authority
  -> MechanicalDesignCandidate
  -> PhysicalMechanismRealization@2 and semantic placements
  -> CandidateCadRealization
  -> PhysicalToM10V2Bridge, complete inventory, exact scope
  -> candidate M10-3 evaluation -> selection -> promotion readiness
  -> ChangeProposal -> ChangeSet -> ChangeEngine -> DesignState N+1
  -> CanonicalPhysicalMechanism@3
  -> fresh canonical CAD -> fresh bridge/inventory/scope/configurations
  -> new canonical M10-3 request and live execution -> durable evidence
```

This proves composition of accepted authority, CAD, M10, promotion, canonical
reconstruction, provenance, currentness, and durable records. It does not add
physical authority, a candidate schema, a canonical schema, an M10 algorithm or
representation, a CAD representation, transform semantics, a provider,
synthesis, selection policy, or a new evidence store.

## Repository And Architecture Audit

Normative architecture identifies `DesignState` as canonical; the only
canonical mutation route is `ChangeProposal -> ChangeSet -> ChangeEngine ->
immutable DesignState revision`. CAD, FreeCAD, M10 results, artifacts, and
Evidence are derived and cannot bypass that route. `ProductionApplication.create`
is the production composition root and owns provider composition.

Existing accepted production surfaces are sufficient for most of the capstone:

- Candidate CAD: `ProductionApplication.realize_candidate_cad()`
  (`src/mechcad_harness/application.py:2117`).
- Candidate M13 bridge evaluation: `evaluate_candidate_multi_joint_m10()`
  (`application.py:2132`), which reaches the strict M10 v2 request boundary and
  `analyze_multi_joint_collision_sweep_v2()`.
- Canonical reconstruction: `reconstruct_promoted_mechanism()`
  (`application.py:2153`), followed by existing canonical CAD and canonical
  multi-joint M10 verification services.
- M10-4 v2: `prove_continuous_multi_joint_path_clearance_v2()`.
- Source/currentness, ArtifactStore byte verification, state reload, M10
  Evidence/provenance, M13-1 interface replay, M13-2 generated-part/placement
  replay, M13-3 bridge/inventory/semantic-equivalence checks, and M13-3P strict
  M10 v2 revalidation.

Existing reusable fixture evidence is intentionally generic: the M13-2 mixed
fixture supplies an imported component plus generated shaft/hub and placement
derivations; M13-3 provides a multi-body bridge, promotion request chain, fresh
canonical reconstruction, candidate production M10-3, and focused M10-4 tests.
M13-4 must build one bounded live fixture from these accepted patterns rather
than rename an M13-3 test.

### Blocking Composition Gap

`CandidateMultiJointSelectionService.select()` exists, but is not composed into
`ProductionApplication`; its current tests construct it directly with a custom
trusted result replayer (`tests/unit/test_m13_3_multi_joint_selection.py:60-78`).
There is no public application selection method for M13 multi-joint evaluation.

The public `ProductionApplication.promote_selected_candidate()` delegates only
to `CandidatePromotionApplicationService.promote_selected_candidate()`, which
accepts `CandidatePromotionRequest` and unconditionally calls generic
`validate_readiness()` and `compile()` (`application.py:2149-2151`,
`candidates/promotion.py:2367-2377`). M13-3 instead requires the distinct
`CandidateMultiJointPromotionRequest`, `validate_multi_joint_readiness()`, and
`compile_multi_joint()` (`candidates/promotion.py:413-499`). No composed public
route applies that request through the normal run/manifest/ChangeEngine flow.

Therefore M13-4 cannot truthfully prove its required production selection,
promotion, `ChangeProposal`, `ChangeSet`, `ChangeEngine`, and N+1 transition.
Adding the dispatch to M13-4 would be a new production semantic contract, not
acceptance orchestration. The required disposition is
`M13_4_BLOCKED_BY_ARCHITECTURE_GAP` until a separate architecture/specification
decision defines and accepts that route.

## Representative Mechanism

Once unblocked, use exactly one bounded generic fixture, approximately five to
eight concrete constituents, with three explicit physical rigid bodies:

```text
R: fixed support/frame members
  -> J1
A: intermediate articulated shaft/hub members
  -> J2
B: terminal articulated member(s)
```

Use multiple concrete constituents in at least two bodies where practical. The
fixture is domain-neutral: it must not use Rotator, antenna, Yagi, pan-tilt, or
azimuth/elevation terminology, requirements, packages, or project files.
`projects/rotator_v2`, the `5840-31ZY` package, and AZ/EL authority are forbidden
inputs.

The fixture must have nonzero semantic placements and be materially
geometry-dependent for at least one cross-body measurement. It must remain small
enough for diagnosable real-FreeCAD execution; it must not add components merely
to create apparent realism.

## Supplied Authority Coverage

Use at least one real supplied M13-1 component from a trusted bound STEP
artifact. Its mechanism use must prove all of the following:

- exact artifact ID, SHA-256, source/reference frame, currentness, and artifact
  byte verification;
- at least one exact authoritative M13-1 interface or frame used by the physical
  mechanism;
- required numeric/interface authority is consumed through the M13-1 gate;
- stale or substituted source identity rejects before lowering or promotion.

STEP shape alone cannot authorize torque, axis, mounting, material, duty, or
interface semantics. The acceptance may use an existing generic motor-like
fixture artifact but must not represent test data as supplier fact. A supplied
axis is preferred only when its existing fixture authority truthfully supports
it; otherwise both live axes may be generated and the supplied-axis path remains
a focused predecessor integration regression rather than fabricated capstone
authority.

## Generated Authority Coverage

Use at least two existing M13-2 generated part kinds, including a generated
shaft (or supported equivalent) and hub/sleeve coupling (or supported
equivalent). Include a frame member where the existing generated part types and
fixture authority permit it.

Every geometry-driving dimension must bind to declared authority. The capstone
must prove generated interfaces, deterministic candidate compilation, at least
one non-identity `GeneratedPlacementDerivation`, and fresh canonical generated
regeneration. Fixture-local magic dimensions with no authority are forbidden.

## Physical Body, Joint, Configuration, And Pair Coverage

Use the accepted M13-3 records exactly:

- explicit `PhysicalRigidBodyBinding` records with complete member coverage,
  explicit reference member, and one connected rooted tree;
- two `PhysicalRevoluteJointBinding` records with authoritative axes, correct
  parent/child bodies, exact connection correspondence, explicit limits, and
  required `accepted-semantic-home@1` zero semantics;
- no implicit body membership, fixed relation, joint, axis, or DOF inference.

Use an explicit replayable `MultiJointVerificationConfigurationSet@1` with at
least three ordered configurations: `cfg0` semantic home; `cfg1` with nonzero J1
so A and B move; and `cfg2` with a different valid descendant B pose caused by
J2. Commands are explicit obligations, never generated from limits.

The complete physical unordered-pair universe must be represented exactly once.
It must contain same-body `SAME_RIGID_GROUP_EXCLUDED` pairs, multiple cross-body
`CHECK_CLEARANCE` pairs including one articulated/articulated and one
root/articulated or ancestor/descendant pair, and at least one other truthful
explicit excluded classification with a nonblank reason. No exclusion is
fabricated solely to exercise an enum; if the proposed fixture has no truthful
excluded pair, it is not an acceptable M13-4 fixture.

## Candidate Production Flow

The live candidate phase must use `ProductionApplication.create`, not an
internally constructed service graph, fake provider, stub geometry, mocked exact
provider, or MCP replacement. It must execute real FreeCAD exact M10-3 through
the configured `MECHCAD_FREECADCMD` boundary and prove:

- strict `KinematicModelV2` revalidation;
- exact source assembly, configuration sequence, complete inventory, and exact
  pair scope binding;
- concrete constituent identities in measurements and any witness;
- candidate request/result identity and currentness binding;
- one durable M10 candidate Evidence/provenance record.

The result may be verified positive clearance; it need not intentionally
collide. Ordinary M10-3 remains discrete-only with
`continuous_path_verified = False`.

## Promotion And ChangeEngine Flow

When the blocker is separately resolved, the capstone must use the real
selection and promotion trust boundary. It must bind candidate currentness,
evaluation, selector/rationale, configuration set, pair policy, placement
derivation set, promotion policy, and derived mapping in readiness.

It must then visibly produce `ChangeProposal`, `ChangeSet`, and a successful
`ChangeEngine` application creating immutable `DesignState` revision N+1. A
compiler merely producing a canonical mechanism is insufficient. Direct state
mutation, a test-only promotion path, an internal-service call that bypasses
application composition, or candidate runtime truth promoted as authority is
forbidden.

## Fresh Canonical Restart

After state application, dispose of and do not supply all candidate/runtime
analysis objects: candidate, candidate CAD request/realization/derivations,
bridge, M10 model/inventory/scope/request/result, evaluation, selection,
promotion request/readiness, and candidate M10 result.

The canonical phase must cross a true serialization boundary. Prefer a newly
constructed `ProductionApplication`, `StateManager`, `ArtifactStore`, and
`EvidenceStore`, with only scalar durable locators crossing the boundary. At
minimum it must serialize canonical state/artifact references using
`model_dump(mode="json")`, reload persisted bytes, use `model_validate`, and run
fresh production analysis. Assigning candidate variables to `None` alone is not
sufficient.

## Canonical CAD And M10 Verification

Fresh canonical reconstruction must use only DesignState N+1, persisted
`CanonicalPhysicalMechanism@3`, trusted artifacts, canonical placement and
derivation records, and composed production services. It must:

- reverify supplied geometry;
- regenerate generated parts;
- replay `CanonicalGeneratedPlacementDerivation`;
- produce a fresh canonical assembly and physical-to-CAD mappings;
- prove semantic equivalence of at least one nonzero generated placement;
- construct a fresh bridge, inventory, exact scope, configuration obligation,
  and new M10-3 request;
- execute real production M10-3 and persist/reload canonical provenance/Evidence.

Candidate and canonical request hashes may differ. The required equivalence is
semantic: bodies, members/reference members, joints/axes/limits/zero semantics,
placements/member offsets, pair classifications and reasons, ordered commands,
tolerances, inventory meaning, and exact scope. Use existing
`rigid-transform-agreement@1.0` only for transform agreement; do not demand raw
CAD, bridge, inventory, model, or request hash equality.

## M10-4 Coverage

Run one focused existing M10-4 v2 explicit-path proof on the accepted canonical
mechanism, using real FreeCAD/provider composition and truthful cross-body scope.
It must remain independent of selection/promotion authority and must be labeled
only as proof of the requested typed piecewise-linear path. It is not a
configuration-space or arbitrary-motion safety certificate.

## M11 Scope Decision

**Decision: B.** M11 remains independently accepted and is outside this
multi-joint mechanism capstone. M11-6 already proves the bounded source-bound
single-solid FreeCAD -> Gmsh -> CalculiX chain. M12-5/M12-6 establish
post-promotion M11 as a non-gating eligibility handoff, and M13-3 explicitly
excluded M11 execution.

The representative generic M13 fixture has no canonical structural definition,
material authority, semantic regions, support/load authority, or structural
request. Its truthful M11 handoff status is therefore `UNRESOLVED`, not eligible.
Adding those inputs merely to repeat M11 would be a new authority scope and is
forbidden. M13-4 may record the non-gating boundary or omit M11 runtime work; it
must not execute whole-mechanism FEA, contact/joint/bearing/bolt analysis,
nonlinear analysis, or fabricate M11 eligibility.

## Artifact, Provenance, And Currentness Evidence

Use the existing `ArtifactStore` and `EvidenceStore` only. The completed future
capstone must durably verify at least:

- supplied source artifact identity and bytes;
- generated part CAD artifacts and candidate CAD provenance;
- candidate M10-3 result Evidence/provenance;
- promotion decision and result artifacts, readiness/mapping bindings, and
  ChangeProposal/ChangeSet/ChangeEngine receipt;
- canonical CAD artifacts/provenance;
- canonical M10-3 Evidence/provenance;
- focused M10-4 Evidence/provenance.

The acceptance must include one stale candidate-side rejection and one stale
canonical/replay rejection, without regenerating goldens. Suitable examples are
changed source authority after candidate creation, substituted placement
derivation, selected candidate reused against a new revision, or substituted
canonical artifact binding. Each must fail closed before an invalid accepted
result or revision is published.

## Runtime Requirements

Required live runtime is the real FreeCAD command-line stack through
`MECHCAD_FREECADCMD` and `FreeCADCmd`; fake providers and optional-CI skips are
not positive acceptance. The report must record the actual executable, FreeCAD
version, backend/provider versions, and execution mode rather than assume 1.1.3.

At this specification audit, `discover_freecad()` returned:

```text
available=False, executable=None, version=None, importable=False
```

This is an environmental observation, not the architecture blocker. A future
live M13-4 acceptance with the required composition route but without an
available configured command is `ENVIRONMENT_BLOCKED`, never PASS. Gmsh and
CalculiX are not M13-4 runtime prerequisites because M11 is excluded.

## Expected Implementation Surface

After separate resolution of the composition gap, the preferred M13-4 surface
is acceptance-only:

- `tests/integration/test_m13_4_full_stack_acceptance.py`;
- small generic fixture/support modules under `tests/` only when necessary;
- `docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md`.

Production changes are **not authorized by this specification**. A separately
approved architecture change would need to expose the existing M13 multi-joint
selection and multi-joint promotion application route through trusted production
composition, preserve predecessor schemas/hashes, use the existing ChangeEngine
and manifest/evidence machinery, and receive its own tests and acceptance before
M13-4 planning resumes.

## Regression Strategy

Future execution is staged: fixture/setup validation; live candidate flow;
selection/promotion/state application; fresh serialized restart; canonical CAD;
canonical M10-3; focused M10-4; predecessor regression groups; then full suite.
The full-suite timeout must be at least 6000 seconds.

Required final regressions cover M10-2/3/4/5, M12 promotion/canonical flows,
M13-1, M13-2, M13-3P, M13-3, transient FreeCAD, canonical CAD,
provenance/currentness, and state/ChangeEngine integration. M11 regressions are
required only if future work changes M11 composition, which this capstone must
not do. No predecessor expected JSON/hash may be updated.

## Completion Report Contract

If unblocked and accepted, `docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md` must
record the final marker; generic mechanism and non-Rotator boundary; supplied and
generated authority; semantic placements; physical body/joint and complete pair
policy; ordered configurations; real candidate CAD/M10-3; selection, readiness,
ChangeProposal/ChangeSet/ChangeEngine, N -> N+1 transition; candidate disposal;
serialized canonical reload; fresh canonical CAD/bridge/M10-3; semantic
equivalence; focused M10-4; M11 decision; artifacts/provenance; stale rejection;
runtime versions; predecessor regressions; full suite; static checks;
dependency/scope audit; and the remaining Rotator V2 boundary.

## Remaining Boundaries

M13-4 must not implement Rotator V2, automatic topology/mechanism synthesis,
optimization, catalog/motor/bearing/material selection, arbitrary trajectory or
configuration-space proof, general FEA, whole-assembly FEA, manufacturing,
tolerance, or release work. It preserves all accepted M10, M11, M12, M13-1,
M13-2, M13-3P, and M13-3 contracts.

## Self-Review

The intended fixture is not an M13-3 test renamed: it requires real-FreeCAD
composition, a materially meaningful supplied-plus-generated mechanism, complete
pair policy, explicit nonzero configurations, real state mutation, durable
artifacts/Evidence, stale rejection, and a true serialized fresh canonical
boundary. It is not Rotator V2 and does not invent supplier facts, infer
interfaces from CAD, manually author M10 truth, reuse candidate CAD canonically,
mislabel M10-4, add M11 assembly scope, or add synthesis.

The Critical issue is unresolved: the existing public production composition
cannot select and promote the M13 multi-joint evaluation through the real
ChangeEngine path. This specification intentionally does not prescribe or
implement the missing production dispatch. No implementation worker may decide
that architecture within M13-4.

## Historical Unblock Addendum (2026-09-07)

The former production-composition gap described above was independently closed by
the accepted M13-4P reconciliation. `M13_4P_INDEPENDENT_ACCEPTED` verifies that
`ProductionApplication` now exposes the typed multi-joint selection, promotion,
and durable receipt-verification delegations while preserving the accepted
M13-4E lifecycle and legacy promotion route.

This addendum does not rewrite the historical disposition, authorize Rotator V2,
or claim M13-4 acceptance. The remaining M13-4 execution gate is the required
real FreeCAD runtime and all acceptance obligations in the execution plan. Until
those obligations pass, `M13_4_MAY_RESUME = NO` and no success marker is valid.
