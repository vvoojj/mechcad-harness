# M11-1 Structural / Load / FEA Architecture

**Date:** 2026-08-23

**Status:** design only. This document neither implements structural analysis nor
changes the current capability baseline. `M10_FULLY_CLOSED_LIVE_VERIFIED` remains
the accepted production status.

## 1. Purpose And Scope

M11 establishes a generic, provenance-aware structural-analysis architecture.
Its first executable scope will be deliberately narrow:

- linear static analysis of one source-bound, homogeneous 3D solid body;
- small-deformation, isotropic, linear-elastic material behavior;
- one or more explicitly named independent load cases;
- fixed supports, concentrated resultant force on a region, distributed pressure,
  and gravity/body acceleration;
- displacement and von Mises stress extraction, plus reactions only when the
  selected backend reports them with an explicit result convention;
- explicit displacement and yield-safety-factor acceptance criteria.

The scope is not assembly FEA. It does not imply contact, bonded interfaces,
bolts, pins, bearings, springs, joint stiffness, load transfer through M10
joints, or an automatic connection model.

The following are explicitly out of scope for the initial M11 architecture and
must not be represented as supported merely because a future solver can expose
them: plasticity, nonlinear geometry, nonlinear material, fatigue, fracture,
buckling, modal or transient dynamics, thermal stress, contact, preload,
composites, tolerance verification, material selection, optimization, and
automatic synthesis.

## 2. Authority Model

Structural analysis is computational and derived. It cannot create or alter a
`DesignState` revision. The required authority layers are separate records, even
where a later M11 schema makes some of them canonical state paths.

| Layer | Meaning | Authority and mutation rule |
|---|---|---|
| A. Fact / source geometry | Accepted component geometry and the exact compiled/realized solid. | `DesignState` and source-bound CAD are authoritative inputs. No solver mutation. |
| B. Engineering requirements | Allowable displacement, required safety factor, operating context, and any stated material authority threshold. | Explicit accepted requirements; never inferred by a solver or material library. |
| C. Material assignment | The selected material properties assigned to the one structural body. | Explicit accepted assignment, source-bound and auditable. A lookup is only a candidate. |
| D. Load definition | Explicit named load cases and typed load primitives. | Engineering input. Every target, direction, frame, magnitude, and unit is stated. |
| E. Support / boundary condition | Explicit structural constraints over a resolved region. | Engineering input. Solver node sets are derived encodings. |
| F. Derived mesh | Actual elements, nodes, region groups, and quality diagnostics. | Mesher output bound to its exact geometry and request. |
| G. Derived solver model | Solver-independent resolved model and backend deck. | Derived from A through F; hand edits are not canonical state. |
| H. Raw solver output | Deck log, solver database/result files, and process status. | Derived artifact; not an engineering conclusion by itself. |
| I. Typed structural result | Parsed fields, extrema, locations, units, assumptions, and result validity. | Derived engineering result with raw artifact provenance. |
| J. Acceptance / verification | PASS, FAIL, or NOT_EVALUABLE for supplied criteria. | Derived decision against B, C, and I. It can create Evidence, an Issue, or a ChangeProposal recommendation only. |

For example, yield strength is an assigned material property, required safety
factor is a requirement, von Mises stress is a computed field, and actual safety
factor is derived from those inputs. None may be silently supplied by CalculiX,
Gmsh, FreeCAD, or `bd_materials`.

The only canonical mutation path remains:

```text
agent or service recommendation
  -> ChangeProposal -> ChangeSet -> ChangeEngine -> immutable DesignState revision
```

M11-2 will add a typed canonical `structural_analysis_definitions` path to
`DesignState`. Each immutable definition will contain the accepted material
assignment, load cases, boundary conditions, and acceptance criteria for a
source body. An analysis request references its exact definition ID and the
definition's canonical snapshot hash; it does not accept caller-supplied
allowables. This is a new M11-2 schema/governance change, not an M11-1 code
change.

The canonical definition intentionally excludes ordinary computational
discretization and execution tuning. A convergence or sensitivity run may vary
mesh refinement while preserving the same definition identity and engineering
meaning.

## 3. Source Binding And Initial Analysis Unit

The initial analysis unit is one `CadPartProgram` that has been compiled against
an exact `(project_id, revision, state_hash)` and realized as one verified solid.
The structural request must bind all of the following:

- source revision and state hash;
- `CadPartProgram` hash and compiler/version provenance where available;
- verified realized geometry artifact identity and actual byte hash;
- realized solid identity, geometry resolver version, and resolved region map
  hash;
- one target body identity;
- `StructuralAnalysisDefinition` hash.
- `StructuralAnalysisRequest` hash, including `MeshSpecification`, requested
  output fields, and execution/resource controls.

The current CAD program supports a limited plate/hole/pocket/slot IR. M11-1 does
not claim that arbitrary parametric geometry, imported STEP-only geometry, or a
`CadAssemblyProgram` is automatically analyzable. M11-2 must define an explicit
source/realization admission contract. An input without a verified one-solid
mapping fails closed.

`PREACCEPTED_CALLER_CONTRACT_ONLY` and
`COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED` remain current trust
limits. A structural result can bind to the exact supplied source revision,
program hash, realized artifact, mesh, deck, and raw result. It cannot honestly
claim that the caller-supplied DesignSpec itself was durably accepted canonical
intent, nor that existing compilation provenance is transitively folded through
every current assembly identity. `run_id` remains correlation and storage scope,
not structural engineering identity.

## 4. Structural Definition And Intermediate Model

M11-2 should introduce typed, immutable models rather than a universal FEM
language:

```text
StructuralAnalysisDefinition
  - definition_id and canonical definition snapshot hash
  - analysis_kind = LINEAR_STATIC_SOLID
  - target_body
  - one material_assignment for the target body
  - ordered load_cases
  - ordered boundary_conditions
  - acceptance_criteria with canonical requirement bindings
  - physical_analysis_assumptions

StructuralAnalysisRequest
  - source binding + StructuralAnalysisDefinition
  - selected nonempty, duplicate-free ordered active load-case identities
  - MeshSpecification
  - requested result/output fields
  - solver-independent execution limits
  - resource/time limits and execution mode controls

ResolvedStructuralModel
  - exact realized solid / region map
  - resolved single material assignment
  - resolved load and support regions in solver coordinates
  - mesh request and mesh artifact reference
  - solver-independent element groups and result requests
```

`StructuralAnalysisDefinition` carries engineering semantics. The resolved model
is derived and may contain mesh node/element sets. A backend adapter turns that
model into a CalculiX-compatible deck. Arbitrary backend text, executable paths,
custom subroutines, and solver keyword fragments are not canonical request
fields.

`MeshSpecification`, requested output selection, and execution/resource controls
are computational request inputs, not ordinary canonical design mutations. They
participate in request identity, mesh identity, result identity, and provenance.
The request must bind them to the exact definition hash and source binding. A
future field may be promoted into canonical requirements only through an
explicit authority decision and ChangeEngine revision.

One request may contain multiple independent named load cases. The backend must
preserve their order and identity and return one result partition per load case.
M11 does not create load combinations, envelopes, or automatic governing cases.
Every selected identity must exist in the definition and be active; an inactive,
unknown, empty, or duplicate selection is `INVALID_STRUCTURAL_MODEL`.

Request-level execution is atomic across selected active load cases. A complete
analysis result has exactly one successfully solved, parsed, and validated
partition for each selected load-case identity in request order. A missing,
duplicate, invalid, or failed partition prevents publication of any typed
analysis result, verification result, or accepted structural Evidence for that
request. Raw diagnostics may persist only as non-authoritative failure artifacts.

Every boundary condition has a nonempty explicit
`applies_to_load_case_ids` tuple. There is no implicit "all load cases" value:
an author who wants a support to apply to every case lists every case identity.
The resolved model expands this membership into each load-case solver model and
records the applied support IDs in that result partition. A case with no
effective support is not repaired by inference; the solver will report the
resulting instability or underconstraint.

## 5. Material Model And Authority

The M11 material binding is an explicit `StructuralMaterialAssignment` concept:

```text
StructuralMaterialAssignment
  - assignment_id
  - target_body_id
  - material_identity
  - material_source_identity and source/provenance
  - immutable property_snapshot
  - assignment_context
  - property_snapshot_hash
```

`StructuralMaterialPropertySnapshot` is property-specific, not assignment-wide:

```text
StructuralMaterialPropertySnapshot
  - property_name
  - value
  - normalized_unit
  - source_identity
  - authority (typical_reference, supplier_datasheet, measured, user_override)
  - context
  - conversion_provenance
```

The selected model is **trusted immutable material identity plus a normalized
analysis snapshot**. The immutable identity and source record support audit; the
immutable snapshot records each consumed property's value, normalized unit,
source identity, authority, context, and conversion provenance. It prevents a
mutable library catalog from changing a replayed analysis. The snapshot must
represent mixed authority honestly, for example E from `supplier_datasheet`, nu
from `typical_reference`, and yield strength from `measured`.
The initial one-solid scope requires exactly one assignment whose `target_body_id`
equals the definition's target body. Multiple assignments, partial material
regions, and multi-material solids are rejected rather than interpreted.

`BdMaterialsAdapter` remains a candidate-data adapter. It currently returns only
`typical_reference`, preserves ranges and missing values, and has no selection or
approval authority. It may populate a proposed snapshot only after an explicit
assignment selects those identity/value pairs. Alias resolution, catalog presence,
or a representative density must never silently become a canonical material
assignment or property snapshot.

Solver-required and acceptance-required properties are distinct:

| Need | Required properties | Missing-property behavior |
|---|---|---|
| Linear elastic force/pressure solve | finite positive E and valid Poisson ratio | `MATERIAL_INCOMPLETE`; do not mesh/solve. |
| Body acceleration | solver properties plus positive density | `MATERIAL_INCOMPLETE`; do not solve that load case. |
| Displacement criterion | a successful displacement field and explicit allowable | result can be computed without an allowable; criterion is `NOT_EVALUABLE`. |
| Yield safety-factor criterion | successful stress field, explicit yield strength, explicit required factor | analysis may be `FEA_EXECUTED`; criterion is `NOT_EVALUABLE` without yield strength or requirement. |

No default strength, density, safety factor, or temperature adjustment is
permitted.

Each criterion declares its exact `consumed_material_properties`, including
upstream material properties whose derived result it relies on. The mandatory
`AcceptanceMaterialAuthorityPolicy` maps each consumed property name to its
allowed authority values; it does not contain one assignment-level authority.
The canonical values are exactly the existing `MaterialDataAuthority` serialized
values: `typical_reference`, `supplier_datasheet`, `measured`, and
`user_override`. The evaluator checks every consumed property's snapshot value,
unit, source, authority, context, and conversion provenance. Any missing property
or disallowed property authority makes that criterion `NOT_EVALUABLE`, never
PASS. Thus E/nu/yield may legitimately have different authorities without
collapsing them into one material label.

## 6. Loads, Frames, And Units

### Load primitives

The first typed `StructuralLoadCase` has a stable `load_case_id`, nonempty name,
ordered primitives, explicit activation state, and its own semantic hash. Initial
primitives are intentionally limited:

| Primitive | Required semantics | Initial backend encoding |
|---|---|---|
| `ResultantForce` | one connected planar face target, magnitude in N, normalized direction, declared frame, units, and `UNIFORM_SURFACE_TRACTION_EQUIVALENT` distribution | resolve area A and apply the constant vector traction F/A over that exact face; a trusted backend may encode it as the mathematically consistent nodal force vector `f_i = integral_A N_i * t dA`; never an unspecified point node. |
| `SurfacePressure` | target region, pressure in MPa, signed normal direction/application convention, declared frame, and units | surface traction over the resolved region. |
| `BodyAcceleration` | target body, vector magnitude/direction, declared frame, acceleration unit, and density dependency | body/gravity load. |

Moment/torque, bearing, remote, centrifugal, thermal, and other loads remain
future primitives. `force = 100` without target, `N`, direction, and frame is
invalid. The distribution convention and resolved face area are part of the load
case and resolved-model semantic hashes; equal nodal, area-weighted nodal, or
other distributions are not hidden substitutions.

For the accepted initial straight-sided planar C3D10 surface contract, this
consistent finite-element nodal vector is an encoding of the same physical
uniform traction, not a change to the canonical load semantics. The closed-form
rule is zero force at each corner and `A_e / 3 * t` at each midside node for
each boundary triangle. Curved or otherwise unsupported geometric mappings are
not admitted by this clarification and must fail closed until exact surface
integration is separately proven.

### Frame contract

Every vector uses exactly one declared coordinate frame:

- `COMPONENT_LOCAL`: axes of the source target body before solver conversion;
- `ASSEMBLY_WORLD`: axes of the source assembly placement, allowed only when a
  single-body target has a verified placement transform;
- `NAMED_DATUM`: future-only until an accepted deterministic datum mapping
  contract exists.

The structural model builder resolves component-local vectors using the exact
source placement transform. It resolves assembly-world vectors directly. It then
records the normalized solver vector and the source transform hash. A backend is
never allowed to decide that a vector is local or global. Since the first scope
is a single body, both frames can numerically coincide in a simple fixture but
they remain different declared meanings.

### Unit contract

Current CAD and section conventions are millimetre-centric, while current
material data use GPa, MPa, and kg/m3. M11 will normalize the solver-independent
model and CalculiX deck to a consistent `mm`, `N`, `s` system:

- length and displacement: mm;
- force and reactions: N;
- stress, E, pressure, and yield strength: MPa (`N/mm^2`);
- density input: kg/m3, converted to `N*s^2/mm^4` by an explicit recorded
  factor of `1e-12`;
- acceleration input: m/s2 or mm/s2 only, normalized to mm/s2;
- dimensionless Poisson ratio and safety factor.

CalculiX is unit-consistent, not unit-aware. The adapter must reject unsupported
or ambiguous units before deck generation and persist the unit policy/version.
The typed public result reports mm, MPa, and N explicitly. No implied solver
unit system is accepted.

## 7. Geometry Targets And Boundary Conditions

Raw `FreeCAD Face12`, Gmsh entity numbers, mesh node IDs, and CalculiX element
set names are derived implementation details. They are not durable engineering
target identities because CAD regeneration and meshing can renumber topology.

The selected target approach is **stable semantic regions resolved from accepted
source-program features and controlled geometric selectors**:

```text
StructuralRegionDefinition
  - region_id
  - target_body_id
  - source_feature_id or source primitive identity
  - semantic_role (for example: base_end, free_end, cylindrical_hole_wall)
  - deterministic geometric predicate in the declared component frame
  - expected cardinality and geometry kind (face, edge, volume)
  - resolver_version
```

The compiler/FreeCAD realization contract must produce the region map while it
has access to the exact realized solid. The map records transient raw topology
references only as evidence, together with the program/geometry hashes and
resolver version. It maps a semantic `region_id` to the actual BREP entity and
then to mesher physical groups. It is invalid for another geometry hash.

The alternatives were assessed as follows:

| Alternative | Decision | Reason |
|---|---|---|
| Raw CAD topology indexes | Rejected as canonical identity | Face numbering is not a regeneration-stable engineering contract. |
| Named deterministic datums / semantic regions | Selected foundation | Stable, reviewable engineering intent when bound to source feature identity. |
| Pure geometric selectors | Supporting mechanism | Needed for reusable roles, but must specify cardinality/tolerances and fail on ambiguity. |
| Generated structural regions | Derived representation | Useful as mesher physical groups, but cannot replace source semantic authority. |
| Feature identities alone | Insufficient alone | A feature may yield multiple faces; semantic role/predicate is still required. |

M11-2 initially supports only selectors that can be unambiguously resolved for
the admitted source program. Any missing, ambiguous, empty, wrong-kind, or
unexpected-cardinality selector returns `GEOMETRY_MAPPING_FAILED`. It must not
fall back to a raw face index.

Initial boundary-condition primitive: `FixedSupport`. It binds a semantic surface
region, explicit `applies_to_load_case_ids`, declared frame, and all
translational displacement DOFs. A continuum solid has no rotational nodal DOFs;
the backend's node-set encoding is derived.
`PrescribedDisplacement` is deferred until a typed component/displacement frame
and nonzero-value validation contract is justified. A "fixed" support is not
assumed to be a solver keyword outside the adapter.

## 8. Single-Body And Assembly Decision

M11 foundation is **single solid / one component only**. This is a deliberate
staged choice, not a claim that a rigid `CadAssemblyProgram` is structurally
connected.

| Scope option | Decision | Reason |
|---|---|---|
| Single body | Selected initial scope | It makes material regions, load/support targets, mesh, and interpretation tractable and testable. |
| Full assembly immediately | Rejected | It requires unmodeled contact, bonding, friction, bolts, bearings, connector stiffness, and load transfer. |
| Staged single body then explicit structural connections | Selected roadmap | Later M11 work may add assembly only with independently typed connection semantics. |

M10 revolute joints are kinematic transform semantics only. They do not imply
bonded contact, friction, pins, bearings, load paths, stiffness, or structural
supports. M10 may provide a source assembly placement or an explicitly selected
configuration as geometry context in a future request; it supplies neither loads
nor structural connections and does not turn motion clearance into FEA proof.
M11-1 also derives no wind, motor torque, payload, or gravity load from M10
motion. Such loads require separately accepted engineering models.

### SectionProperties Boundary

The existing `SectionPropertiesAdapter` remains an analytical cross-section
provider. Its current rectangle/circle/hollow-circle area, centroid, second
moment, torsion, shear-centre, and warping outputs can support future beam checks
or an independent pre-FEA analytical sanity calculation. They do not create a
3D solid mesh, define a material assignment, map a structural region, solve a
3D field, or establish FEA acceptance. Section-properties convergence metadata
is not 3D FEA mesh-convergence evidence.

## 9. Mesh Boundary, Quality, And Convergence

`MeshSpecification` is a solver-independent typed input with a semantic hash:

```text
MeshSpecification
  - element_family = 3D_SOLID_TETRAHEDRON_QUADRATIC
  - global_target_size_mm
  - optional supported semantic-region refinements
  - expected element order/type mapping
  - element-count resource ceiling
  - supported quality-policy identity
  - mesher algorithm/settings version
```

The initial intended CalculiX element mapping is second-order tetrahedral solid
elements (`C3D10`) produced through an explicitly validated Gmsh conversion.
M11-3 must verify the actual emitted element family and reject a mismatch rather
than silently accepting a linear, surface-only, mixed, or unsupported mesh.

The mesher provider receives the verified realized solid plus resolved semantic
regions. It returns a `StructuralMeshArtifact` containing:

- mesh request hash and exact source geometry/region-map hashes;
- actual mesh artifact byte hash and size;
- node/element counts and declared element types;
- region-to-physical-group mapping;
- quality evidence and mesher identity/version/runtime;
- semantic mesh result hash distinct from mesh bytes.

The mesh cannot be reused if its source geometry hash, region map hash, mesh
request hash, or mesher identity differs. Actual bytes are always retained and
bound because neither mesh numbering nor bytes are assumed deterministic across
mesher releases or platforms.

Minimum initial mesh validity is deliberately limited to evidence the chosen
provider can actually report and recheck: expected 3D element family, nonempty
required region groups, no mesher-reported errors, and no nonpositive/inverted
element volumes as reported or independently validated by the selected pipeline.
If Gmsh quality diagnostics such as aspect ratio or scaled Jacobian are exposed
by the validated provider, their metric definition, observed extrema, threshold,
and version must be stored. M11 must not invent a universal skewness or aspect
ratio threshold. Missing mandatory validity evidence is `MESH_INVALID`.

`FEA_EXECUTED` means only that one validly prepared mesh was solved and parsed.
It does not mean mesh-independent. `MESH_CONVERGENCE_VERIFIED` is a later result
maturity available only for an explicit multi-level study with fixed geometry,
regions, material, load/support semantics, selected response metrics, and stated
tolerances. No arbitrary single mesh may be labeled converged.

## 10. Solver Architecture And Decision Record

The selected production direction is:

```text
source-bound CAD / verified realized solid
  -> semantic region resolver (FreeCAD boundary)
  -> ResolvedStructuralModel
  -> Gmsh structural meshing provider
  -> validated mesh artifact and physical groups
  -> CalculiX structural solver adapter
  -> raw artifacts (.inp, logs, .frd/.dat as consumed)
  -> StructuralResultInterpreter
  -> typed result and verification
  -> ArtifactStore + EvidenceStore
```

FreeCAD remains the current trusted CAD realization and BREP/region-resolution
backend. It is not automatically the structural solver owner. CalculiX is the
numerical linear-static solver. Gmsh is the preferred mesher because it provides
an explicit headless mesh boundary and makes the actual mesh, physical groups,
and deck conversion auditable outside a mutable FreeCAD FEM document.

| Integration option | Assessment | Decision |
|---|---|---|
| FreeCAD FEM plus CalculiX | Locally available and a useful pilot/reference path. It can create FEM objects, invoke Gmsh and CalculiX, and import results headlessly. Its document/preferences/object state add provenance and reproducibility surface. | Not the canonical production boundary; retain for discovery and cross-checks. |
| Direct CalculiX only | Clean solver process boundary and deterministic deck hashing, but it has no mesher or semantic CAD-target mapping. | Required solver sub-boundary, insufficient alone. |
| FreeCAD geometry plus Gmsh plus direct CalculiX | Separates source geometry, mesh, solver deck, raw outputs, and parser identities; supports headless Windows execution and future CI with explicit binaries. | Recommended production stack. |
| Other solver | No local/current evidence justifies another dependency or licensing/API boundary. | Not selected. |

This selection does not assert byte determinism for Gmsh meshes or CalculiX
output. It favors explicit provenance and reproducible re-execution over an
opaque integrated document.

`StructuralMeshingProvider` and `StructuralSolverProvider` are trusted,
composition-owned adapters. They expose typed normalized input/output and are
registered with fixed provider identities. Production callers cannot provide a
solver executable, deck text, provider identity, runtime version, result status,
or parsed result. Test-only composition may inject deterministic providers at an
internal service boundary; such runs must record deterministic-test provenance
and are always provenance-distinct from a live run.

The `ProductionApplication` should compose the structural service in the same
way it composes current live FreeCAD measurement providers. Mesh generation and
solver subprocesses are internal calls below that trusted provider boundary; do
not expose raw Gmsh or `ccx` commands as general `ToolBroker` tools. If an agent
later requests analysis through a run task, one high-level exact semantic tool
may broker the application service. It must not expose internal command,
provider, artifact, or attestation fields.

### Future Structural Agent Role

A future structural agent may propose a material/load/support/criterion change,
request a typed structural computation through an authorized high-level
capability, interpret a completed typed result, raise an `EngineeringIssue`, or
emit a `ChangeProposal` recommendation. It may not silently choose or change a
material, alter a mesh to obtain PASS, suppress a high-stress result, mutate
`DesignState`, generate solver attestations, or claim that a provider execution
is trusted. Provider composition, execution, result validation, and Evidence
materialization remain application-owned trusted computation.

## 11. Solver Status, Raw Results, And Interpretation

The solver provider produces `StructuralSolverExecution` with a typed status,
process diagnostics, raw artifact references, and provider/runtime provenance.
Suggested status categories, aligned to existing fail-closed error style, are:

```text
INVALID_STRUCTURAL_MODEL
MATERIAL_INCOMPLETE
INVALID_LOAD
INVALID_SUPPORT
GEOMETRY_MAPPING_FAILED
MESH_FAILED
MESH_INVALID
SOLVER_UNAVAILABLE
SOLVER_FAILED
SOLVER_NONCONVERGED
SOLVER_UNDERCONSTRAINED
RESULT_PARSE_FAILED
RESULT_INVALID
```

The owning layer is explicit: request/model validation owns invalid material,
load, support, and mapping; the mesher owns mesh failure/invalidity; the solver
owns availability, execution, convergence reports, and the normalized
`SOLVER_UNDERCONSTRAINED` status for singular matrix, rigid-body mode, or
unconstrained-DOF reports; the verification evaluator owns acceptance
evaluability.

Singular matrices, rigid body modes, unconstrained DOFs, timeouts, nonzero solver
failure, and nonconvergence are solver failures. They never yield a typed solved
field or structural PASS/FAIL. A diagnostic failure record may be durable, but
it is not accepted positive structural Evidence.

The authoritative publication sequence is all-or-nothing:

```text
validate definition/request
  -> resolve geometry, material, loads, and supports
  -> mesh
  -> validate mesh
  -> build deck
  -> solve
  -> validate solver completion
  -> parse and validate raw results
  -> construct typed analysis result
  -> apply explicit acceptance criteria
  -> persist trusted Evidence and durable artifacts
```

Failure before construction of a complete typed analysis result produces no
accepted PASS structural Evidence and no partial authoritative result. A solved
result with an unevaluable criterion may persist `NOT_EVALUABLE`, but never a
fabricated PASS or FAIL.

Raw output and engineering interpretation are distinct:

```text
StructuralSolverRawResult
  - raw output artifact hashes and parser input identity
  - solver completion/convergence diagnostics
  - nodal displacement, stress tensor, strain, and reactions when actually present

StructuralAnalysisResult
  - result maturity (FEA_EXECUTED or MESH_CONVERGENCE_VERIFIED)
  - per-load-case extrema and locations
  - maximum displacement magnitude in mm
  - observed von Mises stress in MPa
  - reactions only with an explicit source convention
  - mesh/deck/raw-result identities
  - assumptions and result-field conventions

StructuralVerificationResult
  - criterion-by-criterion PASS, FAIL, or NOT_EVALUABLE
  - computed comparison values and reasons
  - acceptance criteria hash and typed result hash
```

A field extremum records one exact `StressFieldRepresentation`:
`ELEMENT_INTEGRATION_POINT`, `ELEMENT_NODAL_EXTRAPOLATED`, or `NODE_AVERAGED`.
It records the derived mesh entity identifier and, where applicable, integration
point identifier, plus the mesh hash, semantic assessment region, and explicit
component-local location. A separately reported assembly-world location, when
available, must carry its exact source transform hash. The
criterion's `FieldSamplingConvention` must select one of those representations;
the interpreter must not silently average, extrapolate, or substitute between
them. A raw global maximum remains observable, but is not universal structural
truth: point loads, sharp corners, and perfect supports can create stress
singularities. M11 performs no automatic singularity filtering.

Any stress-based criterion must explicitly name its assessment region and field
sampling convention. It may use a semantic interior region or a named section
away from a support/load discontinuity. The initial fixture must report raw
maxima and compare analytical stress only at an explicitly defined nonsingular
assessment location. A solver exit code alone cannot generate PASS.

For actual yield safety factor, the typed result needs a deterministic zero-stress
state. A requested criterion provides an explicit positive
`zero_stress_tolerance_mpa`; `stress <= tolerance` produces
`UNBOUNDED_BY_STRESS`, a finite positive stress produces a finite ratio, and
missing/invalid yield strength produces `NOT_EVALUABLE`. NaN, infinity, and a
hidden default tolerance are forbidden.

The initial result always carries these assumptions:

```text
LINEAR_STATIC
SMALL_DEFORMATION
LINEAR_ELASTIC
ISOTROPIC
SINGLE_SOLID_BODY
```

No displacement-to-size heuristic will claim that geometric nonlinearity is
absent. A large-displacement concern is a stated validity limitation that must
be raised by engineering review or a later nonlinear scope, not silently
certified by an unvalidated threshold.

## 12. Engineering Acceptance

Acceptance is a separate evaluator over a successful typed analysis result and
explicit criteria. Initial criteria are:

```text
MaximumDisplacementCriterion
  - criterion_id
  - load_case_id
  - assessment region
  - sampling = NODAL_DISPLACEMENT_MAGNITUDE_ON_REGION
  - consumed_material_properties = (elastic_modulus, poisson_ratio)
  - maximum_allowed_displacement_mm

YieldSafetyFactorCriterion
  - criterion_id
  - load_case_id
  - assessment region
  - field sampling convention
  - consumed_material_properties = (elastic_modulus, poisson_ratio, yield_strength)
  - minimum_yield_safety_factor
  - zero_stress_tolerance_mpa

AcceptanceMaterialAuthorityPolicy
  - allowed_authorities_by_property
```

The evaluator returns per criterion and aggregate `PASS`, `FAIL`, or
`NOT_EVALUABLE`:

- `PASS`: a valid solved result exists and the supplied criterion is met for its
  stated model/mesh maturity;
- `FAIL`: a valid solved result exists and the supplied criterion is exceeded or
  not met;
- `NOT_EVALUABLE`: the solution may exist, but a required allowable, strength,
  assessment region, or valid result field is absent.

Criterion results are keyed by the ordered pair `(criterion_id, load_case_id)`;
the evaluator cannot select another case or create an unstated envelope. For a
complete analysis, aggregate verification is `FAIL` if any criterion fails,
otherwise `NOT_EVALUABLE` if any criterion is not evaluable, otherwise `PASS`.
An empty criteria set is `NOT_EVALUABLE`, never implicit PASS. The material
authority policy is evaluated for every material-dependent criterion before its
numeric comparison.

The only initial displacement sampling convention is
`NODAL_DISPLACEMENT_MAGNITUDE_ON_REGION`: use every mesh node in the exact
physical group mapped from the semantic assessment region; calculate the
Euclidean magnitude from that node's three validated component-local displacement
components; then select the maximum. The resolved region/group map and mesh hash
are retained with the value. Global extrema, another region, a solver display
default, interpolation, and component-wise maxima are not substitutes. Other
displacement sampling conventions are future work.

`SOLVER_SUCCESS + STRUCTURAL_FAIL` is a valid and important outcome. A solver
failure yields no PASS or FAIL. A PASS at `FEA_EXECUTED` maturity must say that
mesh independence was not established; it must not be presented as a general
mesh-converged certification.

## 13. Persistence, Provenance, And Repeatability

`ArtifactStore` remains the durable home for immutable files. `EvidenceStore`
holds the complete typed semantic result, verification result, source binding,
and trusted execution/provenance bindings. M11 must extend existing Evidence
models rather than create a separate FEA database.

The minimum durable artifact set for a successfully authoritative completed
analysis is:

- source realized-geometry artifact reference and actual byte hash;
- canonical structural analysis manifest containing normalized definition,
  resolved-model hash, unit policy, and command-independent settings;
- actual mesh file and mesh artifact metadata;
- generated solver input deck;
- solver stdout/stderr or equivalent execution log;
- each raw solver result file consumed by the interpreter, normally CalculiX
  `.frd` and/or `.dat` as applicable;
- parser manifest identifying exactly which raw artifacts produced the typed
  result.

Ephemeral scripts, temporary FreeCAD documents, intermediate Gmsh files not
needed to replay/audit, and redundant solver scratch files may remain transient.
They must never be confused with trusted Evidence. If an input deck, mesh, or raw
result is omitted, the remaining retained set must still reproduce the typed
result; otherwise omission is not allowed.

Structural provenance must bind at least:

```text
source revision/state hash and source geometry hash
program/compiler/realization provenance where available
material assignment hash
load-case hash
support hash
analysis definition/request/resolved-model hashes
mesh specification hash, actual mesh hash, mesher identity/version/runtime
solver deck semantic hash and actual deck byte hash
solver identity/version/runtime/execution mode
raw-result artifact hash
interpreter identity/version and typed-result hash
acceptance-criteria hash and verification-result hash
```

Geometry backend, mesher, and solver each have distinct provenance records.
`freecad` is therefore not an adequate one-word structural provenance label.

Semantic request hashes use canonical JSON, fixed ordering, no timestamps, no
temporary paths, and no `run_id`. Mesh/deck/raw artifact hashes are byte hashes.
Real meshing and solver output are not assumed byte-identical across releases or
platforms. The exact produced mesh and raw output are retained and bound to the
result. Repeated live runs are evaluated for numeric repeatability under stated
tolerances and identical recorded runtime, not by a false cross-platform byte
identity promise. Typed result hashes preserve full validated finite scalar
values, not silently rounded display values.

## 14. Test And Live Acceptance Strategy

Future M11 tests must cover:

- property-specific material values, units, source identities, authorities,
  contexts, conversion provenance, and required-property failure;
- load units, vector normalization, and component/world frame transforms;
- support semantics and stable semantic-region resolution;
- raw topology rejection and geometry/mesh source binding;
- deterministic definition/request/model hashes, definition-preserving mesh
  variation, and ordered load cases;
- mesh validity, mesh artifact binding, and mesher provenance;
- deck generation, solver provenance, parser correctness, and invalid raw output;
- singular/underconstrained, mesh-invalid, missing-material, and unavailable
  provider failures;
- acceptance PASS, FAIL, and NOT_EVALUABLE, including zero-stress handling;
- durable result/Evidence reload and artifact hash revalidation;
- M9/M10 regression compatibility and source-state immutability.

The first live fixture is a deterministic rectangular cantilever beam, separate
from the antenna mechanism:

- one isotropic rectangular solid with known E and yield strength;
- one semantic fixed-end face;
- one semantic free-end face;
- an end-face resultant force distributed over that face, or a stated pressure;
- beam-theory displacement and a nonsingular interior stress assessment used as
  independent comparison targets with explicit tolerances.

The eventual live acceptance requires all three real-solver categories:

| Case | Expected disposition | Purpose |
|---|---|---|
| Analytically predictable load | PASS for supplied displacement/stress criteria | Verifies units, load direction, support, material, meshing, parser, and acceptance wiring. |
| Intentionally overloaded load | Solver success plus structural FAIL | Proves computation success is separate from engineering acceptance. |
| Underconstrained fixture | Fail closed with solver instability/singularity status | Proves no partial stress field becomes a PASS or FAIL. |

The analytical comparison is an independent sanity check, not a calibration
target. It cannot be used to alter material, support, mesh, or output until a
desired result is obtained.

## 15. Runtime Discovery And Backend Evidence

M11-1 performed no installation. The actual Windows environment contains:

| Item | Discovery status | Evidence |
|---|---|---|
| FreeCAD command runtime | INSTALLED | `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`, FreeCAD 1.1.3. |
| FreeCAD FEM modules | AVAILABLE THROUGH EXISTING FREECAD | `Fem`, `ObjectsFem`, Gmsh tools, and CalculiX FEM modules import under `freecadcmd`. |
| CalculiX | INSTALLED | Bundled `ccx.exe`, version 2.22. |
| Gmsh | INSTALLED | Bundled `gmsh.exe`, version 4.15.0. |
| Harness FreeCAD discovery | NOT CURRENTLY DISCOVERED BY DEFAULT PROCESS | The current `discover_freecad()` requires `MECHCAD_FREECADCMD`, PATH, or importable module; the environment variable/PATH is not presently configured for the host process. |
| Host Python Gmsh bindings | NOT DISCOVERED | No `gmsh` Python package is installed; the recommended provider may use controlled subprocesses. |
| Current MechCAD FEA provider | NOT IMPLEMENTED | No structural mesh, solver, parser, artifact, or test implementation exists. |

This availability is not live structural acceptance. Existing M9/M10 FreeCAD
evidence verifies CAD and exact geometry measurement, not FEM meshing or solver
results.

Primary research references are the installed FreeCAD FEM modules, the official
[FreeCAD FEM source](https://github.com/FreeCAD/FreeCAD/tree/main/src/Mod/Fem),
[CalculiX documentation](https://www.dhondt.de/), and the
[Gmsh reference manual](https://gmsh.info/doc/texinfo/gmsh.html). FreeCAD is
LGPL-2.1; CalculiX is GPL-2.0; Gmsh is GPL-2.0-or-later with upstream stated
exceptions. Any later binary redistribution requires a licensing review.

## 16. Future M11 Milestones

| Milestone | Scope and exit boundary |
|---|---|
| M11-1 | This architecture and backend discovery only. No production schema or FEA code. |
| M11-2 | Typed structural authority/definition models, material snapshots, loads, fixed supports, criteria, semantic-region contract, request/result identities, and pure validation tests. |
| M11-3 | Trusted source-geometry realization/region resolver, Gmsh mesh provider, mesh artifact/quality contract, direct CalculiX deck/solver provider, and deterministic fake-provider tests. |
| M11-4 | Real single-body linear-static vertical slice, raw-result parser/interpreter, cantilever analytical validation, and real PASS/FAIL/underconstrained outcomes. |
| M11-5 | Durable structural Evidence/Artifact provenance, reload/integrity/repeatability hardening, explicit mesh-convergence-result architecture, and M9/M10 regressions. |
| M11-6 | System-level live acceptance over the three required fixture outcomes on the selected real runtime. |

Assembly structural connections, nonlinear physics, and domain-specific antenna
loads are separate future design cycles after this foundation. M10 kinematics may
later supply explicitly selected geometry placement only; wind, gravity-derived
payloads, motor torque, and antenna drag require their own engineering authority
models and are not inferred by M11-1.

## 17. Self-Review Gate

| Required question | M11-1 answer |
|---|---|
| Can a solver/backend mutate canonical engineering state? | NO. |
| Can a material library silently choose canonical material? | NO. |
| Can raw `FaceN` become long-lived authority without stable mapping? | NO. |
| Can solver exit code alone produce structural PASS? | NO. |
| Can mesh for geometry hash X be reused for geometry hash Y? | NO. |
| Do M10 revolute joints define FEA contact/connection semantics? | NO. |
| Are solver convergence and engineering acceptance separate? | YES. |
| Are strength requirements separate from elastic solver properties? | YES. |
| Is ordinary mesh refinement canonical engineering authority? | NO; it belongs to the source-bound request unless separately accepted as a requirement. |
| Is material authority evaluated per consumed property? | YES; the policy maps each consumed property to allowed authorities. |
| Can the result bind exact geometry, materials, loads, BCs, mesh, solver, and runtime? | YES; the required binding set is specified in section 13. |
| Does initial M11 claim nonlinear/contact/dynamic/tolerance verification? | NO. |

## 18. Open Questions

These are implementation-time decisions, not missing authority or placeholders:

- Which exact Gmsh physical-group and CalculiX element-set export method passes
  an M11-3 controlled discovery test for the installed versions?
- Which quality metric APIs are available and stable enough in that validated
  Gmsh path beyond the mandatory no-inversion checks?
- Should the first production acceptance require supplier-datasheet or measured
  material authority for its yield criterion, or label a typical-reference
  fixture only as an architectural solver validation?
- What retention limit and compression policy preserves the required raw artifact
  set without weakening replay/audit obligations?

## 19. Disposition

`M11_1_STRUCTURAL_FEA_ARCHITECTURE_READY`
