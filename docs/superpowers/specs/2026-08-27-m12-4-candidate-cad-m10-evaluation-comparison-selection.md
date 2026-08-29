# M12-4 Candidate CAD, M10 Evaluation, Comparison, and Selection

## Status and scope

M12-4 implements a bounded, noncanonical bridge from an accepted
`MechanicalDesignCandidate` to explicit candidate CAD, existing M10 output
motion verification, immutable candidate evaluation, deterministic comparison,
and explicit selection. It preserves the accepted M12-1, M12-2, M12-3, CAD,
and M10 semantics.

The capability ends before candidate promotion, canonical `DesignState`
mutation, post-promotion verification, M11, optimization, catalog selection,
manufacturing approval, tolerance verification, or general mechanism
synthesis.

## Authority and identity

`MechanicalDesignCandidate` remains immutable, noncanonical, source-bound, and
content-addressed. M12-3 `RevoluteDrive` results remain independent derived
records and M12-4 consumes their exact typed status and identity without
recomputing any sizing, torque, spur, shaft, stress, or admissibility formula.

Candidate identity excludes runtime, publication, execution, temporary, and
derived-result artifact identities. This is a narrow clarification to M12-1:
an explicitly selected `GeometrySourceReference.artifact_id` contained in a
`ComponentSpecificationSnapshot` is a candidate-defining source choice under
the accepted M12-2 implementation. It therefore participates in the component
snapshot and candidate identities. This exception does not extend to arbitrary
artifacts.

Three identities remain distinct:

1. Candidate geometry-source identity: the selected geometry source in the
   candidate component specification.
2. Verified geometry content identity: bytes freshly resolved through
   `ArtifactStore` and checked against the declared SHA-256.
3. Candidate CAD realization identity: the complete derived realization,
   including mappings, placements, representations, compiled assembly, and
   provider provenance.

A changed selected source artifact identity requires a different candidate even
when the bytes match. Changed bytes behind the same source identity are an
integrity failure. Changing a downstream transient CAD artifact never changes
candidate identity.

## Candidate CAD realization

M12-4 adds immutable request and result records equivalent to
`CandidateCadRealizationRequest` and `CandidateCadRealization` plus a focused
domain service. The request deterministically binds:

- candidate and source binding identities;
- representation-policy and compiler versions;
- a complete physical-instance to CAD-instance manifest;
- the exact generated `CadPartProgram` identities or trusted geometry-source
  identities for every represented component;
- representation fidelity, placement provenance, and derived transforms;
- the candidate-local design-variable and component/interface identities used;
- the deterministic request hash.

The result binds the candidate and request hashes, the complete instance
manifest, per-instance fidelity, all generated/imported representation
identities, resulting `CadAssemblyProgram` identity, rigid-body mapping
manifest, verified source content identities, and compiler/provider provenance.
It has a deterministic realization hash and never becomes candidate authority.

The service uses the existing `CadPartProgram`, `CadAssemblyProgram`, generic
compiler, `ImportedCadComponent`, `ArtifactStore`, and existing FreeCAD
backend. It does not introduce an M12-specific CAD backend, STEP trust path, or
CAD store. Imported geometry is freshly resolved and byte-verified by the
existing artifact contract; all valid top-level STEP shapes remain part of the
imported component representation.

Generated geometry may use existing generic CAD primitives only when every
geometry-defining value is candidate-bound. A missing trusted source and missing
supported candidate-bound generated representation yields
`CAD_REALIZATION_UNRESOLVED`; it never creates a placeholder box, cylinder, or
motor envelope. Provider, artifact-integrity, malformed-input, and backend
failures remain separately typed operational/integrity failures.

### Geometry fidelity

Every CAD instance declares one representation fidelity:

- `TRUSTED_SOURCE_GEOMETRY`: the exact verified bytes of the declared trusted
  component source were used.
- `DECLARED_BOUNDED_COLLISION_REPRESENTATION`: deterministic geometry derived
  from candidate-bound geometry-defining dimensions, used only as the declared
  collision representation. Each dimension retains its actual origin:
  `SOURCE_AUTHORITY`, candidate-local design variable, explicit permitted policy
  assumption, or deterministic derived relation.

Exact M10 measurement is exact for the CAD representation supplied to it. It is
not an assertion that a bounded representation is exact manufacturer or
real-world geometry. The fidelity manifest is retained in CAD, M10, and
evaluation provenance.

### Placement authority

The request may carry transforms for execution convenience, but it must bind
their candidate-derived provenance and the realization service must recompute or
validate them. It may not introduce an independent placement authority.

Every placement-changing physical value, including shaft, bearing, support,
motor-axis, gear-center, hub, and driven-body placement, must originate in a
candidate-local design variable, authoritative component/interface data, or a
deterministic relation of those inputs. `MechanicalConnection` alone is not
placement authority. The same candidate must realize the same placement
semantics; a physically different placement requires a different candidate.

The initial typed frame mapping supports only the needed bounded relations:
coaxial shaft/hub/bearing placement, direct motor/output-axis alignment,
external-spur center-distance placement, fixed support/mount placement,
driven-body attachment, and output-joint-axis correspondence. It is not a
general mating or assembly solver. Axis direction and sign conventions are
versioned and documented in the mapping contract.

## Candidate to M10 binding

M12-4 adds an immutable, versioned mapping equivalent to
`CandidateKinematicCadBinding`. It binds the exact candidate CAD realization,
M10 model identity, output `joint_id`, frame/axis correspondence, and every
physical CAD instance's M10 scope disposition. It preserves constituent
identities even when several components share one M10 rigid representation.

The scope dispositions are conceptually:

- `FIXED`: the component is represented by the static/base M10 body.
- `OUTPUT_RIGID`: the component shares the declared output-joint transform.
- `INTERNAL_MOTION_UNMODELED`: the component has physical motion which the
  existing M10 single-output-joint model does not represent.

Repository-consistent names may vary, but the three semantic categories must
remain distinct. No component in candidate CAD can be implicitly omitted from
this classification.

`OUTPUT_RIGID` grouping is allowed only when all grouped constituents genuinely
share the same output transform under the bounded candidate model. Motor and
support housings cannot be grouped with moving output geometry for convenience.

Sharing an M10 rigid transform does not require compounding collision geometry.
The CAD manifest preserves separate candidate physical/geometry instances when
the pair inventory needs constituent-level measurement. A compound is permitted
only when it does not lose a required constituent-level distinction. If the
existing M10 representation/backend cannot independently measure the declared
pair granularity, the requested M10 verification scope is unresolved rather
than coarsened.

For external-spur reduction, a driver gear is
`INTERNAL_MOTION_UNMODELED`, not falsely fixed. The driven gear, shaft, hub,
and driven body may be `OUTPUT_RIGID`; motor and support housings may be
`FIXED`. A monolithic motor STEP similarly does not establish separate
rotor/shaft M10 bodies. A bearing representation does not imply inner/outer
ring, rolling-element, cage, or bearing-life verification.

M12-4 does not add a ratio joint, gear constraint, gear phase, backlash,
bearing DOF, motor rotor DOF, or coupled motion to M10. Therefore it cannot
verify driver counter-rotation, gear tooth engagement, driver/driven phase,
backlash, internal transmission collision, motor internals, or bearing
internals. Any required condition depending on an
`INTERNAL_MOTION_UNMODELED` instance is unresolved unless the declared scope
explicitly places that condition outside scope with a reason.

Unmodeled continuous motion does not erase an independently measurable exact
home-position collision. When its home placement is known, a non-intended home
interference involving an `INTERNAL_MOTION_UNMODELED` instance remains a valid
geometric witness. Only its unrepresented continuous internal-motion path is
unresolved; M12-4 never claims continuous verification for that component.

## M10 request, pair coverage, and proof

An immutable request equivalent to `CandidateM10EvaluationRequest` binds:

- candidate and CAD realization hashes;
- M10 model and scoped output-joint identities;
- the exact continuous angle interval or path;
- clearance requirement and its engineering provenance;
- binding and representation fidelity identities;
- expected eligible geometry-pair universe and complete pair inventory;
- required checked-pair subset and M10 service/version;
- the deterministic request hash.

The initial candidate motion scope is exactly one existing M10 output revolute
joint. Required continuous clearance calls the existing M10 continuous
single-axis proof; it does not introduce candidate collision mathematics or
relabel discrete samples as continuous proof. To preserve declared
constituent-pair granularity, the bridge invokes that unchanged proof separately
for each `CHECK_CLEARANCE` moving/stationary geometry pair and binds every
underlying M10 request/result identity in the candidate M10 stage outcome. It
does not merge such pairs into one cross-product proof when that would include
an intentionally excluded constituent pair. Home realization/load failure is
operational; a home collision in a required pair remains an M10 result.

### Complete collision-pair inventory

The service derives or validates an expected independently measurable
geometry-pair universe from the CAD manifest, M10 scope dispositions, and
declared evaluation scope. Every eligible pair is classified exactly once at the
geometry granularity accepted by the existing M10 path. Classifications are
conceptually:

- `CHECK_CLEARANCE`;
- `INTENDED_CONTACT_EXCLUDED`;
- `SAME_RIGID_GROUP_EXCLUDED`;
- `UNMODELED_MOTION_OUT_OF_SCOPE`;
- `OTHER_EXPLICIT_OUT_OF_SCOPE` with a required reason.

The expected universe, full classification inventory, checked set, excluded
set, and exclusion reasons are all hashed. A caller cannot silently omit a
pair: the request is rejected as incomplete. Removing or reclassifying a pair
changes scope identity and invalidates previous results. Intended interfaces,
such as gear mesh, shaft/support bore, shaft/hub attachment, fixed mounted
interfaces, and same-rigid-group pairs, require explicit inventory entries. An
intended shaft/support exclusion cannot hide an independently measurable
hub/mount clearance pair merely because their respective constituents share an
output/fixed transform. An intended gear mesh is not an M10 clearance check and
does not establish mesh correctness.

### Motion and clearance provenance

For every required M10 condition, the joint, path/interval, clearance threshold,
pair scope, geometry fidelity, and origin are retained. Inputs must originate
from canonical/source authority or an explicit, hashed evaluation/policy
assumption. M12-4 never silently narrows an interval, decreases clearance, or
reduces a pair universe and calls the result feasible. Candidate evaluation and
comparison bind this exact evaluation-scope identity.

M10 result replay fails closed when candidate, realization, source bytes,
fidelity, binding, model, joint, path, inventory, clearance, or semantically
required service/backend identity differs.

## Staged candidate evaluation

M12-4 represents each required CAD and M10 stage with a typed immutable outcome
rather than fabricating downstream objects. The CAD stage is conceptually:

- `SUCCESS`, binding the exact `CandidateCadRealization` identity;
- `UNRESOLVED`, binding one or more typed engineering/input reasons and no
  realization identity;
- `NOT_REACHED`, binding the exact earlier-stage reason when later CAD work was
  legitimately not performed.

The M10 stage is conceptually:

- `SUCCESS`, binding exact M10 request/result identities, including an original
  M10 `VERIFIED_CLEAR`, `COLLISION_WITNESS`, or `NOT_PROVEN` result;
- `UNRESOLVED`, binding typed scope/geometry/input reasons and no fabricated M10
  request or result;
- `NOT_REACHED`, binding the exact earlier-stage reason.

Operational and integrity failures are outside these engineering stage outcomes.
Every required stage outcome has its own deterministic identity and is bound by
the aggregate evaluation. Thus admissible M12-3 plus CAD unresolved yields an
unresolved evaluation without CAD/M10 identities; a successful M10
`NOT_PROVEN` result is retained exactly and yields unresolved; and M12-3
inadmissibility can yield infeasibility while later CAD/M10 stages are explicitly
`NOT_REACHED`.

## Candidate evaluation

`CandidateEvaluation` is immutable and source-bound. It binds candidate and
source identities; exact M12-3 result; exact CAD and M10 stage-outcome
identities; policy and scope identities; required-check inventory; metrics;
unresolved findings; evaluator provenance; and a deterministic evaluation hash.
Successful stage outcomes retain their exact CAD realization and M10
request/result identities.

It references original M12-3 and M10 result semantics. It does not reproduce
their formulas or statuses. Aggregate outcomes are:

- `FEASIBLE`: all required supported checks have valid satisfying evidence and
  no required authority, geometry, or proof remains unresolved.
- `INFEASIBLE`: at least one valid hard engineering or geometric violation
  witness exists.
- `UNRESOLVED`: no hard witness exists but a required authority, geometry,
  representation, internal-motion check, or proof remains unresolved.

A valid M12-3 inadmissibility or M10 `COLLISION_WITNESS` is a hard witness.
M12-3 unresolved, required CAD unresolved, missing required M10 result, or M10
`NOT_PROVEN` is unresolved. Hard witnesses take precedence over unresolved
findings. Operational and integrity errors never become either engineering
outcome.

Candidate evaluation currentness recomputes and validates all candidate, source,
M12-3, CAD-stage, binding, M10-stage, policy, and scope identities. It validates
the CAD realization and M10 request/result identities only for successful stage
outcomes. It does not trust an old enum.

## Comparison and selection

`CandidateComparisonPolicy` defines only how to compare: ordered trusted metric
keys, minimize/maximize direction, expected units, admissibility requirements,
missing-value behavior, tie semantics, and comparator version. The initial
algorithm is deterministic lexicographic comparison only, with no weights or
optimization. A missing required metric rejects/unresolves comparison rather
than receiving an implicit value.

`CandidateComparisonRequest` defines which records to compare: exact candidate
and evaluation hashes, policy hash, and common source/evaluation-scope binding.
The policy never owns a candidate set. Comparison requires same project,
exact same `CandidateSourceBinding` hash, current valid feasible evaluations,
and exact compatible evaluation-scope hashes. It cannot compare differing source
binding, path, clearance, pair universe, or fidelity scope as equivalent. M12-4
does not implement broader semantic source-binding equivalence.

### Initial comparison metric registry

The initial registry contains exactly one metric:
`verified_clearance_lower_bound_mm`, with unit `mm` and direction determined by
the policy. It is available only for an exact required continuous M10
`VERIFIED_CLEAR` result and is deterministically derived from the minimum of the
existing trusted `minimum_certified_lower_clearance_mm` interval certificates.
No other M10 status produces this metric. M12-3 does not currently expose a
selected-shaft-diameter result field suitable for the registry, so
`selected_shaft_diameter_mm` is not implemented in M12-4. Cost, mass,
manufacturability, quality, efficiency, safety, and generic scores are excluded.
Metric key, source result identity, derivation, and unit are part of the
evaluation and comparison identities; a substituted metric source or unit fails
closed.

`CandidateComparisonResult` is immutable and binds request, policy,
candidate/evaluation identities, ranking, ties, exact metrics, comparator
provenance, and result hash. Hash ordering may present a tie deterministically,
but is never an engineering preference. Ranking has no side effect.

`CandidateSelection` is immutable, noncanonical, and explicit. It binds the
selected candidate, exact feasible/current evaluation, source binding, selector,
rationale, whether comparison was used, optional exact comparison-result hash,
schema version, and selection hash. Comparison is optional. A cited comparison
must be current, valid, scope-compatible, and contain the selected candidate.
Selection can choose a non-top-ranked feasible candidate with rationale.

Selection rejects stale or forged candidates/evaluations/comparisons, foreign
or mismatched source bindings, infeasible or unresolved evaluations, and stale
evaluation inputs. It does not mutate `DesignState`, create a `ChangeProposal`,
call `ChangeEngine`, publish records, approve a design, or promote a candidate.

## Production composition and artifact policy

Focused domain services own realization, M10 preparation/invocation,
evaluation, comparison, and selection. `ProductionApplication` exposes the
smallest coherent orchestration surface and does not contain CAD, M10, or
comparison algorithms. Existing ToolBroker use remains limited to existing
external provider execution.

Candidate CAD is transient by default. Existing trusted input artifacts retain
their existing durable `ArtifactStore` identities. No candidate CAD store or
automatic FCStd/STEP publication is introduced; explicit publication occurs
only if an existing trusted runtime API requires it.

## Verification design

Focused tests cover deterministic hashing, strict reconstruction where needed,
mapping/placement validation, fidelity, complete pair coverage, replay and
substitution failures, M12-3 result binding, outcome precedence, comparator
policy/request separation, ties, selection currentness, and canonical
non-mutation.

Live production capstones use real `ProductionApplication`, current FreeCAD,
real M10 exact measurement and continuous proof, and a mixed assembly with
generated and trusted imported geometry. They include:

- direct-drive `VERIFIED_CLEAR` with M12-3 admissibility and feasible
  evaluation;
- engineering-admissible direct-drive geometry with an M10
  `COLLISION_WITNESS` and infeasible evaluation;
- bounded `NOT_PROVEN` with unresolved evaluation;
- external-spur realization preserving motor, driver gear, driven gear, shaft,
  support, hub, mount, and driven-body identities, while explicitly recording
  unmodeled driver/gear-internal motion;
- two compatible feasible candidates, deterministic comparison and real tie
  behavior, selection with comparison, and selection without comparison.

Focused regressions additionally prove distinct collision geometry can share a
rigid transform; an intended-contact exclusion cannot mask a separate
constituent collision; an unmodeled-motion home collision remains a hard witness
while its continuous path is unresolved; CAD unresolved does not fabricate
CAD/M10 identities; M10 `NOT_PROVEN` remains exactly referenced; an M12-3 hard
violation makes later stages `NOT_REACHED`; policy hash is unchanged while a
candidate/evaluation-set change changes the request hash; incompatible source or
M10 scope is rejected; and metric source/unit substitution fails closed.

All capstones assert source revision/hash before and after unchanged. The report
records actual runtime identity, candidate/CAD/M10/evaluation identities, path,
pair/exclusion counts, clearance, result statuses, fidelity, and spur
limitation. M12-5, M11, promotion, and post-promotion verification remain out
of scope.

## Critical self-review

This specification was reviewed before implementation for the following risks:

- Unmodeled internal motion is explicitly classified for every CAD instance;
  spur driver motion is never represented as fixed or continuously verified;
  independently measurable home collisions remain witnesses.
- Request transforms are derived/validated from candidate-bound placement
  provenance and cannot create a second placement authority.
- The pair inventory covers the derived eligible geometry universe completely,
  preserves required constituent granularity, and rejects absent pairs.
- Required interval, clearance, pair scope, and fidelity have visible
  engineering/policy provenance and are part of the scope hash.
- Bounded collision representations are not described as exact source or
  real-world component geometry.
- M10 gear coupling, mesh engagement, and transmission-internal motion are
  explicitly excluded from the claimed capability.
- Comparator policy defines how, request defines which, and comparison has no
  selection side effect; its sole metric has an exact trusted source and unit.
- Selection remains noncanonical and cannot call promotion or canonical mutation
  paths.

No unresolved ambiguity or contradiction remains within the bounded M12-4
scope.
