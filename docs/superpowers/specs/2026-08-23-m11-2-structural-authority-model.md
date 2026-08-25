# M11-2 Structural Authority Model

**Date:** 2026-08-23

**Status:** specification and implementation target. M11-2 is the typed
structural authority/request-model milestone. It does not implement M11-3 mesh
generation, FreeCAD region realization, Gmsh execution, CalculiX execution, raw
result parsing, or FEA production orchestration.

## 1. Goal

Add the smallest credible typed structural-analysis authority model while
preserving the accepted M11-1 architecture:

```text
canonical DesignState
  -> StructuralAnalysisDefinition
  -> source-bound StructuralAnalysisRequest
     + MeshSpecification
     + requested outputs
     + execution/resource controls
  -> future M11-3 mesh/solver boundaries
```

The canonical definition describes engineering intent. The request describes one
computational execution of that intent. A convergence study can vary its mesh
specification and execution limits while retaining the same canonical definition
and definition hash.

## 2. Hard Boundaries

- `DesignState` remains the only canonical engineering authority.
- `StructuralAnalysisDefinition` is stored in canonical state under
  `structural_analysis_definitions`.
- Ordinary mesh refinement, requested result fields, and execution/resource
  controls are not fields of `StructuralAnalysisDefinition`.
- `MeshSpecification` participates in request identity, mesh provenance, and
  future result provenance.
- Material authority is property-specific. No assignment-level authority field
  may imply that E, nu, density, and yield strength share one source.
- Every consumed material property stores value, normalized unit, source identity,
  authority, context, and conversion provenance.
- Every acceptance criterion declares the material properties it consumes.
- Material authority policy evaluates the actual consumed property snapshots.
- The initial definition has exactly one material assignment for exactly one body.
- The initial definition supports one solid, linear static, small deformation,
  isotropic, linear elastic assumptions only.
- Loads and supports use semantic region IDs, never durable raw `FaceN` indexes.
- No model in this milestone invokes FreeCAD, Gmsh, CalculiX, subprocesses,
  ArtifactStore, EvidenceStore, or ToolBroker execution.
- No solver result, mesh result, or acceptance result is produced by M11-2.
- Do not update current normative capability documents to claim FEA capability.

## 3. Canonical DesignState Model

Add this field to `DesignState`:

```python
structural_analysis_definitions: list[StructuralAnalysisDefinition] = Field(
    default_factory=list
)
```

Each definition is an immutable semantic record inside a revision snapshot. The
existing ChangeEngine remains the only way to add, replace, or remove a
definition. To preserve the repository's existing collection mutation contract,
the Pydantic field is `id`; its semantic meaning is the structural
`definition_id`. It is the stable collection key and must be unique within one
`DesignState`.

The canonical state path is:

```text
/structural_analysis_definitions/<definition_id>
```

The owner is `mechcad-structural`. A changed definition invalidates
`analysis.structural` and downstream `validation.structural` through the existing
dependency graph. A request or mesh change does not create a canonical revision.

## 4. StructuralAnalysisDefinition

The definition contains only accepted engineering semantics:

```text
StructuralAnalysisDefinition
  - id (semantic definition_id)
  - name
  - analysis_kind = linear_static_solid
  - target_body_id
  - regions
  - material_assignment
  - load_cases
  - boundary_conditions
  - acceptance_criteria
  - material_authority_policy
  - physical_assumptions
```

It does not contain `MeshSpecification`, requested result fields, mesher
settings, solver settings, executable paths, timeouts, artifact retention flags,
provider identity, or result hashes.

The definition validator must enforce:

- nonempty `id` (semantic definition ID), `name`, and `target_body_id`;
- `analysis_kind == "linear_static_solid"`;
- exactly one `StructuralMaterialAssignment` whose target body equals
  `target_body_id`;
- at least one active load case;
- unique load-case IDs, boundary-condition IDs, criterion IDs, and region IDs
  within their respective collections;
- unique load IDs across the definition;
- every referenced load-case, body, and region ID exists where the model
  requires it;
- every boundary condition applies only to defined active load cases;
- every body-acceleration load targets `target_body_id`;
- every criterion references an active defined load case;
- every consumed property has a valid property name and policy entry;
- elastic modulus and Poisson ratio exist for a structurally executable
  definition, and density exists when a body-acceleration load is present;
- a criterion-only property such as yield strength may be absent and makes only
  its dependent criterion not evaluable;
- physical assumptions exactly match the initial M11 scope.

The deterministic `structural_definition_hash(definition)` helper hashes the
canonical JSON payload of the definition with sorted keys and compact separators.
It excludes no engineering fields and includes no timestamps, request fields,
runtime fields, or transient artifact paths.

## 5. Physical Assumptions

Use a typed `StructuralPhysicalAssumptions` model with fixed initial values:

```text
analysis_kind       = linear_static_solid
deformation_model   = small_deformation
material_model      = linear_elastic
material_symmetry   = isotropic
body_scope          = single_solid_body
```

The model is explicit and hashable. M11-2 does not expose booleans that could
silently describe unsupported nonlinear behavior. Future physics require a
separate schema and milestone.

## 6. Property-Specific Material Snapshot

Use a restricted structural property enum:

```text
elastic_modulus
poisson_ratio
density
yield_strength
```

`StructuralMaterialPropertySnapshot` contains exactly one scalar value and:

```text
property_name
value
normalized_unit
source_identity
authority
context
conversion_provenance
```

`authority` reuses the existing `MaterialDataAuthority` values:

```text
typical_reference
supplier_datasheet
measured
user_override
```

`conversion_provenance` is a typed record containing at least source unit,
normalization rule, and conversion version. `context` carries temperature,
grade/condition, test context, or other applicable qualification context as an
explicit string; an absent context is represented as `None`, not guessed.

The snapshot validator must enforce:

- finite scalar values;
- `elastic_modulus` in normalized `MPa`, positive;
- `poisson_ratio` in normalized `ratio`, greater than `-1` and less than `0.5`;
- `density` in normalized `kg/m^3`, positive;
- `yield_strength` in normalized `MPa`, positive;
- nonempty source identity, normalized unit, and conversion provenance;
- no duplicate property names within an assignment;
- no unavailable or range-only value is accepted as an analysis scalar.

`StructuralMaterialAssignment` contains material identity, target body identity,
assignment context, and the immutable tuple of property snapshots. It has no
assignment-level authority field. Mixed authorities remain representable:

```text
elastic_modulus ->  supplier_datasheet
poisson_ratio   ->  typical_reference
yield_strength  ->  measured
```

`bd_materials` may provide a typical candidate property, but it cannot create the
assignment, choose a representative strength, or upgrade its authority.

## 7. Material Authority Policy And Criteria

`AcceptanceMaterialAuthorityPolicy` is property-specific:

```text
allowed_authorities_by_property:
  elastic_modulus -> (supplier_datasheet, measured)
  poisson_ratio   -> (typical_reference, supplier_datasheet, measured)
  yield_strength  -> (measured, supplier_datasheet)
```

The policy stores an ordered tuple of
`StructuralPropertyAuthorityRule(property_name, allowed_authorities)` records.
It must contain one rule for each property consumed by any criterion.

Initial criteria:

```text
MaximumDisplacementCriterion
  - criterion_id
  - load_case_id
  - assessment_region_id
  - sampling = nodal_displacement_magnitude_on_region
  - consumed_material_properties = (elastic_modulus, poisson_ratio)
  - maximum_allowed_displacement_mm

YieldSafetyFactorCriterion
  - criterion_id
  - load_case_id
  - assessment_region_id
  - stress_sampling
  - consumed_material_properties = (elastic_modulus, poisson_ratio, yield_strength)
  - minimum_yield_safety_factor
  - zero_stress_tolerance_mpa
```

The criterion validator rejects an empty consumed-property tuple, duplicate
property names, missing policy entries, and property names outside the initial
enum. The pure evaluator has this interface:

```text
evaluate_material_authority_policy(
    criterion,
    assignment,
    policy,
) -> StructuralMaterialAuthorityDecision
```

`StructuralMaterialAuthorityDecision` contains `status = eligible | not_evaluable`,
the ordered consumed property names, and typed rejection reasons keyed to the
property name. It checks each consumed property's snapshot value, normalized
unit, source identity, authority, context, and conversion provenance against
that property's policy rule. A missing criterion-only property, disallowed
authority, invalid unit, or missing conversion provenance returns
`not_evaluable`. Context is retained and compared only when a future criterion
explicitly requires it; M11-2 does not invent a context requirement. It never
downgrades or upgrades authority. Missing solver-required E, nu, or density is a
model/request validation failure rather than a criterion-only not-evaluable
result.

This milestone defines the policy and validation inputs. It does not calculate
stress, displacement, safety factor, or PASS/FAIL from solver output.

## 8. Semantic Regions

`StructuralRegionDefinition` is the canonical target identity used by loads,
supports, and criteria:

```text
region_id
target_body_id
exactly one of source_feature_id or source_primitive_id
semantic_role
geometry_kind = face | edge | volume
selector_kind
selector_parameters
expected_cardinality
resolver_version
```

M11-2 validates nonempty semantic identities and deterministic selector payloads
and requires one nonempty source identity, but does not resolve regions against
FreeCAD. A raw `FaceN`, mesh node ID, Gmsh
entity ID, or CalculiX set name is rejected as a canonical selector.

M11-3 will implement the trusted resolver and produce the geometry-bound region
map. M11-2 only ensures that future providers receive stable semantic input.

## 9. Loads And Coordinate Frames

`StructuralLoadCase` has a stable ID, name, active flag, ordered load primitives,
and semantic identity. The initial load union is:

```text
StructuralResultantForce
  - load_id
  - target_region_id
  - magnitude_n
  - direction_xyz
  - frame = component_local | assembly_world
  - distribution = uniform_surface_traction_equivalent

StructuralSurfacePressure
  - load_id
  - target_region_id
  - pressure_mpa
  - signed_normal_convention
  - frame

StructuralBodyAcceleration
  - load_id
  - target_body_id
  - acceleration_xyz
  - acceleration_unit = mm/s^2
  - frame
```

M11-2 validates finite vectors, nonzero directions where required, positive
force magnitude, explicit units, valid frame values, nonempty target IDs, and
the fixed resultant-force distribution convention. It does not transform frames
or resolve regions. Moment, torque, bearing, remote, centrifugal, thermal, and
wind loads are not accepted by these models.

## 10. Supports And Boundary Conditions

The initial boundary model is `StructuralFixedSupport`:

```text
support_id
target_region_id
applies_to_load_case_ids
frame = component_local | assembly_world
constrained_dofs = (ux, uy, uz)
```

The load-case tuple is nonempty, duplicate-free, and references defined active
load cases. The initial support must constrain exactly the three translational
solid DOFs. Prescribed displacement and rotational DOFs are not accepted.

M11-2 stores semantics only. It does not turn a support into solver node sets or
assume that FreeCAD face numbering is stable.

## 11. Source-Bound StructuralAnalysisRequest

`StructuralAnalysisRequest` is a derived execution input and contains:

```text
StructuralSourceBinding
  - project_id
  - source_revision
  - source_state_hash
  - definition_id
  - definition_hash
  - target_body_id
  - source_program_hash
  - geometry_identity
  - geometry_artifact_id
  - geometry_artifact_hash

StructuralAnalysisRequest
  - source_binding
  - selected_load_case_ids
  - mesh_specification
  - requested_result_fields
  - execution_settings
  - request_hash
```

The selected load-case tuple is nonempty, ordered, duplicate-free, and must be
validated against the canonical definition through
`request.validate_against(definition)`. Every selected case must exist and be
active. The request does not embed a second mutable copy of the canonical
definition.

`MeshSpecification` contains computational settings only:

```text
element_family = c3d10
global_target_size_mm
local_refinements by semantic region ID
quality_policy_id
mesher_settings_version
```

Local refinements are an ordered tuple for serialization but their order is not
semantic. M11-2 rejects duplicate region IDs and canonicalizes the tuple in
ascending `region_id` order before request hashing. A changed target size or
quality policy changes request identity, not definition identity.

`StructuralExecutionSettings` contains resource controls only:

```text
max_elements
max_runtime_seconds
max_output_bytes
retain_raw_artifacts
```

No request field accepts solver executable paths, provider identity, backend
version, solver text, result hashes, or claimed statuses. Requested result fields
are a typed tuple of `displacement`, `von_mises_stress`, and `reactions`.

`structural_request_hash(request)` includes the complete source binding, selected
load-case order, mesh specification, requested output fields, and execution
settings. It excludes timestamps, temporary paths, runtime-discovered provider
identity, and result values. Two requests with different mesh sizes must have
different request hashes while retaining the same `definition_hash`.

## 12. Validation And Failure Semantics

M11-2 exposes typed validation failures through existing Pydantic validation
boundaries and a small structural validation result where a boolean decision is
needed. It does not introduce solver failure categories prematurely.

Validation must fail closed for:

- duplicate definition, load, support, criterion, region, or property IDs;
- unsupported analysis assumptions or physics values;
- multiple material assignments or multi-material region assignments;
- missing/invalid solver-required property values, units, source identities, or
  conversion provenance;
- missing policy entries or disallowed authority values;
- empty/ambiguous target IDs, raw topology selectors, or invalid frames;
- unsupported load kinds, load distributions, DOFs, or criteria;
- request/definition ID or hash mismatch;
- request selection of inactive or unknown load cases;
- nonpositive, nonfinite, or unbounded resource settings.

No validation result mutates canonical state. A valid model is not evidence that
the geometry is resolved, the mesh is valid, the solver is available, or the
structure passes acceptance.

## 13. Existing Architecture Integration

M11-2 changes only the typed authority/model boundary:

- `DesignState` gains the typed canonical definition collection;
- ownership gains `/structural_analysis_definitions/*` for
  `mechcad-structural`;
- dependency rules invalidate `analysis.structural` when a definition changes;
- existing canonical state hashing automatically includes definitions;
- `models/__init__.py` exports the new canonical models;
- existing `MaterialDataAuthority` is reused, not duplicated;
- no Evidence, ArtifactStore, ProductionApplication, ToolBroker, or backend
  execution path is changed.

Current M9/M10 capabilities and source-binding limitations remain unchanged.
M11-2 does not alter `PREACCEPTED_CALLER_CONTRACT_ONLY`, compilation provenance
transitivity, or `run_id` semantics.

## 14. Test Strategy And Exit Gates

Unit tests must prove:

- canonical definition JSON and hash are stable and order-sensitive where order
  is semantic;
- changing only `MeshSpecification` changes request hash but not definition
  hash;
- changing requested outputs or execution limits changes request hash but not
  definition hash;
- property snapshots preserve mixed authorities and conversion provenance;
- assignment-level authority cannot be supplied or serialized;
- each criterion checks only its declared consumed properties;
- policy accepts and rejects authorities per property independently;
- missing yield strength makes yield verification not evaluable without blocking
  a valid elastic model;
- exactly one material assignment is required;
- semantic regions reject raw topology indexes;
- loads reject ambiguous units, frames, targets, vectors, and distributions;
- supports reject missing or unknown load-case applicability and non-solid DOFs;
- requests reject definition mismatch, inactive cases, duplicates, and bad hashes;
- canonical state reload and state hash include structural definitions;
- ChangeEngine ownership and dependency invalidation cover the new state path;
- no M9/M10 tests regress.

M11-2 is complete when these typed models and boundaries are implemented and
tested. It does not require FreeCAD, Gmsh, CalculiX, a mesh artifact, a solver
result, or live structural acceptance.

## 15. Explicitly Deferred To M11-3 And Later

- FreeCAD semantic-region realization and geometry mapping;
- Gmsh meshing and physical-group creation;
- mesh quality measurements and mesh artifacts;
- CalculiX deck generation or solver execution;
- raw solver result parsing and typed structural fields;
- structural acceptance evaluation against solver results;
- durable structural Evidence and solver provenance;
- analytical cantilever live validation;
- assembly connections, contact, nonlinear physics, dynamics, thermal analysis,
  wind, and domain-specific load derivation.

## 16. Disposition

`M11_2_STRUCTURAL_AUTHORITY_MODEL_SPEC_READY_FOR_IMPLEMENTATION`
