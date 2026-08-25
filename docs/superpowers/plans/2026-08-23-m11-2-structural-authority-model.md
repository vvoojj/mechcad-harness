# M11-2 Structural Authority Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add typed canonical structural engineering definitions and source-bound computational requests with property-specific material authority, without implementing mesh generation, solver execution, or M11-3.

**Architecture:** Store only engineering semantics in `DesignState.structural_analysis_definitions`. Keep `MeshSpecification`, requested outputs, and resource controls in `StructuralAnalysisRequest`, whose deterministic identity includes those computational inputs and the canonical definition hash. Keep material authority on immutable per-property snapshots and evaluate policy against each criterion's consumed properties.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing `DesignState`, `StateManager`, `ChangeEngine`, `OwnershipPolicy`, dependency graph, `MaterialDataAuthority`, and canonical JSON/SHA-256 hashing.

## Global Constraints

- Preserve `M10_FULLY_CLOSED_LIVE_VERIFIED` and all M9/M10 behavior.
- Keep `DesignState` as the only canonical engineering authority.
- Use the existing `id` collection-key convention for canonical structural definitions; the semantic meaning is `definition_id`.
- Do not place `MeshSpecification`, requested result fields, or execution/resource controls in `StructuralAnalysisDefinition`.
- Make mesh specification part of `StructuralAnalysisRequest` identity and future mesh/result provenance.
- Store material value, normalized unit, source identity, authority, context, and conversion provenance for every consumed property.
- Do not add assignment-level material authority.
- Evaluate `AcceptanceMaterialAuthorityPolicy` per consumed material property.
- Enforce one material assignment for one target body and the fixed initial linear-static assumptions.
- Do not add FreeCAD, Gmsh, CalculiX, solver parsing, mesh generation, ArtifactStore execution, EvidenceStore execution, or ProductionApplication structural orchestration.
- Do not update current normative capability documents to claim FEA capability.
- Preserve Python 3.11+, Pydantic v2, and UTC-aware datetime requirements.
- Do not commit, push, reset, stash, clean, or revert workspace changes.

---

## File Map

- Create: `src/mechcad_harness/models/structural.py` - canonical structural enums, property snapshots, regions, loads, supports, criteria, assumptions, and `StructuralAnalysisDefinition`.
- Create: `src/mechcad_harness/structural_request.py` - source binding, `MeshSpecification`, requested outputs, execution settings, request validation, and request hash.
- Modify: `src/mechcad_harness/models/design.py` - add typed `structural_analysis_definitions` collection and duplicate-ID validation.
- Modify: `src/mechcad_harness/models/__init__.py` - export canonical structural models.
- Modify: `config/ownership.yaml` - add structural definition ownership.
- Modify: `config/dependencies.yaml` - invalidate structural analysis when a canonical definition changes.
- Create: `tests/unit/test_structural_models.py` - pure model, authority, cross-reference, and failure tests.
- Create: `tests/unit/test_structural_request.py` - request identity, mesh variation, source binding, and validation tests.
- Modify: `tests/unit/test_state_foundation.py` - state hash/reload coverage for structural definitions.
- Modify: `tests/unit/test_changes.py` - structural owner and ChangeEngine collection-path coverage.

No M11-3 source files, backend files, live tests, artifact code, solver code, or capability documents are changed.

## Task 1: Add Property-Specific Material And Shared Structural Types

**Files:**
- Create: `src/mechcad_harness/models/structural.py`
- Create: `tests/unit/test_structural_models.py`

**Interfaces:**
- Reuse: `Model` from `models.common` and `MaterialDataAuthority` from `materials`.
- Produce: `StructuralMaterialPropertyName`, `StructuralMaterialPropertySnapshot`, `StructuralMaterialConversionProvenance`, `StructuralMaterialAssignment`, `StructuralPhysicalAssumptions`, `StructuralAnalysisKind`, `StructuralCoordinateFrame`, `StructuralDof`, and `StructuralResultField`.

- [ ] **Step 1: Write failing property-snapshot tests.**

Add tests with exact cases:

```python
def test_property_snapshot_preserves_mixed_authority_and_provenance():
    snapshot = StructuralMaterialPropertySnapshot(
        property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS,
        value=69000.0,
        normalized_unit="MPa",
        source_identity="supplier:datasheet:6061-t6",
        authority=MaterialDataAuthority.SUPPLIER_DATASHEET,
        context="room-temperature T6",
        conversion_provenance=StructuralMaterialConversionProvenance(
            source_unit="GPa",
            normalization_rule="gpa_to_mpa_x1000",
            conversion_version="units@1.0",
        ),
    )
    assert snapshot.authority is MaterialDataAuthority.SUPPLIER_DATASHEET
    assert snapshot.normalized_unit == "MPa"

def test_assignment_does_not_have_assignment_level_authority():
    assignment = make_structural_assignment_with(
        elastic_modulus_authority=MaterialDataAuthority.SUPPLIER_DATASHEET,
        poisson_ratio_authority=MaterialDataAuthority.TYPICAL_REFERENCE,
        yield_strength_authority=MaterialDataAuthority.MEASURED,
    )
    assert assignment.property_snapshot[0].authority is not None
    assert "authority" not in assignment.model_fields

def test_invalid_structural_property_units_and_values_fail_closed():
    with pytest.raises(ValidationError):
        make_snapshot(
            StructuralMaterialPropertyName.POISSON_RATIO,
            value=0.3,
            normalized_unit="MPa",
        )
    with pytest.raises(ValidationError):
        make_snapshot(
            StructuralMaterialPropertyName.ELASTIC_MODULUS,
            value=0.0,
            normalized_unit="MPa",
        )
```

Add equivalent tests for positive density/yield strength, `-1 < nu < 0.5`, finite values, nonempty source/conversion fields, duplicate property names, and missing scalar values. Use `ValidationError` rather than broad `Exception`.

- [ ] **Step 2: Run the new tests and verify the expected import failure.**

Run:

```text
py -3 -m pytest tests/unit/test_structural_models.py -q
```

Expected: collection fails because `mechcad_harness.models.structural` does not exist.

- [ ] **Step 3: Implement the shared enums and typed property snapshot.**

Implement the exact normalized property contract:

```python
class StructuralMaterialPropertyName(StrEnum):
    ELASTIC_MODULUS = "elastic_modulus"
    POISSON_RATIO = "poisson_ratio"
    DENSITY = "density"
    YIELD_STRENGTH = "yield_strength"

class StructuralMaterialConversionProvenance(Model):
    source_unit: str = Field(min_length=1)
    normalization_rule: str = Field(min_length=1)
    conversion_version: str = Field(min_length=1)

class StructuralMaterialPropertySnapshot(Model):
    property_name: StructuralMaterialPropertyName
    value: float
    normalized_unit: str = Field(min_length=1)
    source_identity: str = Field(min_length=1)
    authority: MaterialDataAuthority
    context: str | None = None
    conversion_provenance: StructuralMaterialConversionProvenance
```

Validate the property-specific normalized units and finite/physical ranges in one `model_validator(mode="after")`. Do not add a generic unit engine or infer conversion provenance.

- [ ] **Step 4: Implement the one-body assignment and fixed assumptions.**

Implement `StructuralMaterialAssignment` with `assignment_id`, `target_body_id`, `material_identity`, `assignment_context`, and a nonempty tuple of unique `property_snapshot` records. Do not add `authority`, E, nu, density, or yield fields directly to the assignment.

Implement fixed `StructuralPhysicalAssumptions` values so callers cannot claim unsupported physics:

```python
analysis_kind: Literal["linear_static_solid"] = "linear_static_solid"
deformation_model: Literal["small_deformation"] = "small_deformation"
material_model: Literal["linear_elastic"] = "linear_elastic"
material_symmetry: Literal["isotropic"] = "isotropic"
body_scope: Literal["single_solid_body"] = "single_solid_body"
```

- [ ] **Step 5: Run the focused model tests.**

Run:

```text
py -3 -m pytest tests/unit/test_structural_models.py -q
```

Expected: all property, assignment, enum, and assumptions tests pass.

## Task 2: Add Regions, Loads, Supports, Criteria, And Definition Validation

**Files:**
- Modify: `src/mechcad_harness/models/structural.py`
- Modify: `tests/unit/test_structural_models.py`

**Interfaces:**
- Consume: Task 1 enums, `StructuralMaterialAssignment`, and `StructuralPhysicalAssumptions`.
- Produce: `StructuralRegionDefinition`, `StructuralLoadCase`, `StructuralResultantForce`, `StructuralSurfacePressure`, `StructuralBodyAcceleration`, `StructuralFixedSupport`, `StructuralPropertyAuthorityRule`, `AcceptanceMaterialAuthorityPolicy`, `MaximumDisplacementCriterion`, `YieldSafetyFactorCriterion`, `StructuralAnalysisDefinition`, `StructuralMaterialAuthorityDecision`, `evaluate_material_authority_policy`, and `structural_definition_hash`.

- [ ] **Step 1: Write failing region/load/support tests.**

Cover these exact invalid cases before implementation:

```python
def test_raw_face_selector_is_not_a_canonical_region():
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(
            region_id="fixed-end",
            target_body_id="body-1",
            semantic_role="base_end",
            geometry_kind="face",
            selector_kind="raw_topology_index",
            selector_parameters={"face": "Face7"},
            expected_cardinality=1,
            resolver_version="region-resolver@1.0",
        )

def test_resultant_force_requires_explicit_distribution_and_frame():
    with pytest.raises(ValidationError):
        StructuralResultantForce(
            load_id="force-1",
            target_region_id="free-end",
            magnitude_n=100.0,
            direction_xyz=(1.0, 0.0, 0.0),
            frame="component_local",
            distribution="point_force",
        )

def test_fixed_support_requires_all_solid_translation_dofs_and_case_ids():
    with pytest.raises(ValidationError):
        StructuralFixedSupport(
            support_id="support-1",
            target_region_id="fixed-end",
            applies_to_load_case_ids=(),
            frame="component_local",
            constrained_dofs=("ux", "uy"),
        )
```

Add positive tests for component-local/world frames, uniform surface traction equivalent, pressure with explicit `signed_normal_convention`, body acceleration with explicit `acceleration_unit="mm/s^2"`, and load-case ordering. Add a test that `StructuralResultField` accepts only `displacement`, `von_mises_stress`, or `reactions`.

- [ ] **Step 2: Run the tests to verify they fail.**

Run:

```text
py -3 -m pytest tests/unit/test_structural_models.py -q
```

Expected: import or attribute failures for the new structural semantic types.

- [ ] **Step 3: Implement semantic regions and initial load union.**

Use `selector_kind` validation that rejects `raw_topology_index`, `face_index`, mesh-node, Gmsh-entity, and CalculiX-set selectors. Keep selector parameters JSON-compatible and deterministic; do not resolve them against CAD.

Implement `StructuralRegionDefinition` with exact fields `region_id`,
`target_body_id`, exactly one of `source_feature_id: str | None` and
`source_primitive_id: str | None`, `semantic_role`,
`geometry_kind: Literal["face", "edge", "volume"]`, `selector_kind`,
`selector_parameters: dict[str, str | int | float | bool]`,
`expected_cardinality: int`, and `resolver_version`. Reject nonpositive
cardinality, empty selector/role/version fields, and a missing or ambiguous
source identity.

Implement these exact semantic fields:

```python
class StructuralSurfacePressure(Model):
    kind: Literal["surface_pressure"] = "surface_pressure"
    load_id: str = Field(min_length=1)
    target_region_id: str = Field(min_length=1)
    pressure_mpa: float
    signed_normal_convention: Literal["outward_positive", "inward_positive"]
    frame: StructuralCoordinateFrame

class StructuralBodyAcceleration(Model):
    kind: Literal["body_acceleration"] = "body_acceleration"
    load_id: str = Field(min_length=1)
    target_body_id: str = Field(min_length=1)
    acceleration_xyz: tuple[float, float, float]
    acceleration_unit: Literal["mm/s^2"] = "mm/s^2"
    frame: StructuralCoordinateFrame

class StructuralLoadCase(Model):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    active: bool = True
    loads: tuple[StructuralLoad, ...] = Field(min_length=1)
```

Use a discriminated union with `kind` values `resultant_force`, `surface_pressure`, and `body_acceleration`. Require:

```python
distribution = "uniform_surface_traction_equivalent"
frame in {"component_local", "assembly_world"}
```

Validate finite nonzero direction vectors, positive force magnitude, finite pressure, finite acceleration, nonempty targets, and explicit units represented by the typed field names/enum values.

`StructuralLoadCase.loads` is a nonempty tuple, and `load_id` values are unique
across the definition. Every support's `applies_to_load_case_ids` must
reference defined active cases. Every `StructuralBodyAcceleration.target_body_id`
must equal the definition's `target_body_id`.

Define `StructuralResultField` as the exact string enum
`displacement`, `von_mises_stress`, `reactions`; do not accept arbitrary result
names in M11-2.

- [ ] **Step 4: Implement fixed supports and property authority policy.**

Require `StructuralFixedSupport.applies_to_load_case_ids` to be nonempty and duplicate-free, and `constrained_dofs == ("ux", "uy", "uz")` in canonical order. Reject prescribed displacement, rotational DOFs, and empty frames in M11-2.

Implement:

```python
class StructuralPropertyAuthorityRule(Model):
    property_name: StructuralMaterialPropertyName
    allowed_authorities: tuple[MaterialDataAuthority, ...]

class AcceptanceMaterialAuthorityPolicy(Model):
    allowed_authorities_by_property: tuple[StructuralPropertyAuthorityRule, ...]
```

Validate unique policy property names and nonempty allowed-authority tuples.

Implement the pure authority result and evaluator:

```python
class StructuralMaterialAuthorityDecision(Model):
    status: Literal["eligible", "not_evaluable"]
    consumed_property_names: tuple[StructuralMaterialPropertyName, ...]
    rejection_reasons: tuple[StructuralMaterialAuthorityRejection, ...] = ()

class StructuralMaterialAuthorityRejection(Model):
    property_name: StructuralMaterialPropertyName
    reason: Literal[
        "missing_snapshot",
        "disallowed_authority",
        "invalid_unit",
        "missing_conversion_provenance",
    ]

def evaluate_material_authority_policy(
    criterion: StructuralCriterion,
    assignment: StructuralMaterialAssignment,
    policy: AcceptanceMaterialAuthorityPolicy,
) -> StructuralMaterialAuthorityDecision:
    ...
```

Return one typed rejection record per missing or disallowed consumed property, preserve criterion property order, and do not fail a displacement criterion because optional yield strength is absent.

Define `StructuralCriterion` as the discriminated union of
`MaximumDisplacementCriterion` and `YieldSafetyFactorCriterion`. Add tests for
eligible mixed authorities, missing yield producing `not_evaluable` only for the
yield criterion, disallowed yield authority, and missing conversion provenance.

The missing-yield test must assert both outcomes:

```python
assignment = make_structural_assignment_without(StructuralMaterialPropertyName.YIELD_STRENGTH)
displacement = evaluate_material_authority_policy(
    make_displacement_criterion(), assignment, make_policy()
)
yield_check = evaluate_material_authority_policy(
    make_yield_criterion(), assignment, make_policy()
)
assert displacement.status == "eligible"
assert yield_check.status == "not_evaluable"
assert yield_check.rejection_reasons[0].property_name is StructuralMaterialPropertyName.YIELD_STRENGTH
```

- [ ] **Step 5: Implement criteria with consumed-property declarations.**

Implement the exact initial defaults:

```python
MaximumDisplacementCriterion.consumed_material_properties == (
    StructuralMaterialPropertyName.ELASTIC_MODULUS,
    StructuralMaterialPropertyName.POISSON_RATIO,
)

YieldSafetyFactorCriterion.consumed_material_properties == (
    StructuralMaterialPropertyName.ELASTIC_MODULUS,
    StructuralMaterialPropertyName.POISSON_RATIO,
    StructuralMaterialPropertyName.YIELD_STRENGTH,
)
```

Reject duplicate/empty property tuples, nonpositive displacement allowables, nonpositive required safety factors, and nonpositive zero-stress tolerances. Use `stress_sampling="element_integration_point" | "element_nodal_extrapolated" | "node_averaged"`.

- [ ] **Step 6: Implement `StructuralAnalysisDefinition` cross-validation.**

Use `id` as the Pydantic field so existing ChangeEngine collection paths work. Add a `model_validator(mode="after")` that enforces:

The definition fields are exactly `id`, `name`, `analysis_kind`, `target_body_id`,
`regions: tuple[StructuralRegionDefinition, ...]`,
`material_assignment: StructuralMaterialAssignment`,
`load_cases: tuple[StructuralLoadCase, ...]`,
`boundary_conditions: tuple[StructuralFixedSupport, ...]`,
`acceptance_criteria: tuple[StructuralCriterion, ...]`,
`material_authority_policy`, and `physical_assumptions`.

```python
definition.material_assignment is not None
definition.material_assignment.target_body_id == definition.target_body_id
any(case.active for case in definition.load_cases)
len({case.id for case in definition.load_cases}) == len(definition.load_cases)
len({load.load_id for case in definition.load_cases for load in case.loads}) == len(
    [load.load_id for case in definition.load_cases for load in case.loads]
)
len({support.support_id for support in definition.boundary_conditions}) == len(
    definition.boundary_conditions
)
len({criterion.criterion_id for criterion in definition.acceptance_criteria}) == len(
    definition.acceptance_criteria
)
len({region.region_id for region in definition.regions}) == len(definition.regions)
all(
    criterion.load_case_id in load_case_ids
    and load_cases_by_id[criterion.load_case_id].active
    for criterion in definition.acceptance_criteria
)
all(property_name in policy_names for criterion in criteria for property_name in criterion.consumed_material_properties)
all(region.target_body_id == definition.target_body_id for region in definition.regions)
all(load.target_region_id in region_ids for load in region_targeting_loads)
all(support.target_region_id in region_ids for support in definition.boundary_conditions)
all(criterion.assessment_region_id in region_ids for criterion in definition.acceptance_criteria)
all(
    case_id in load_case_ids and load_cases_by_id[case_id].active
    for support in definition.boundary_conditions
    for case_id in support.applies_to_load_case_ids
)
all(load.target_body_id == definition.target_body_id for load in body_acceleration_loads)
```

The definition must contain at least one active load case, and each criterion must reference an active case. Require elastic modulus and Poisson ratio snapshots for an executable elastic definition and density when a body-acceleration load is present. Permit missing yield strength; the authority evaluator returns `not_evaluable` only for criteria that consume it. Validate all region references used by loads, supports, and criteria. Do not require every defined region to be used.

- [ ] **Step 7: Run the model suite.**

Run:

```text
py -3 -m pytest tests/unit/test_structural_models.py -q
```

Expected: all region, load, support, policy, criteria, cross-reference, and failure tests pass.

## Task 3: Integrate Canonical Definitions Into DesignState

**Files:**
- Modify: `src/mechcad_harness/models/design.py`
- Modify: `src/mechcad_harness/models/__init__.py`
- Modify: `tests/unit/test_structural_models.py`
- Modify: `tests/unit/test_state_foundation.py`

**Interfaces:**
- Consume: `StructuralAnalysisDefinition` from `models.structural`.
- Produce: `DesignState.structural_analysis_definitions: list[StructuralAnalysisDefinition]` and public model exports.

- [ ] **Step 1: Add failing DesignState integration tests.**

Add tests that construct a valid state with one definition, assert the field is present, reject duplicate definition IDs, and prove the structural definition changes the canonical state hash:

```python
def test_structural_definition_is_canonical_state_and_affects_hash():
    first = make_state(structural_analysis_definitions=[])
    second = make_state(structural_analysis_definitions=[make_definition()])
    assert "structural_analysis_definitions" in DesignState.model_fields
    assert state_hash(first) != state_hash(second)

def test_duplicate_structural_definition_ids_fail_closed():
    with pytest.raises(ValidationError):
        make_state(structural_analysis_definitions=[make_definition("DEF-1"), make_definition("DEF-1")])
```

- [ ] **Step 2: Run the red integration tests.**

Run:

```text
py -3 -m pytest tests/unit/test_structural_models.py tests/unit/test_state_foundation.py -q
```

Expected: the new state field is absent and duplicate-ID validation is not yet implemented.

- [ ] **Step 3: Add the typed field and duplicate-ID validator.**

Import `StructuralAnalysisDefinition` into `models/design.py`, add the default-empty list field, and add one `DesignState` after-validator that rejects duplicate structural definition IDs. Preserve all existing fields and the UTC validator.

Export `StructuralAnalysisDefinition` and the public structural semantic models through `models/__init__.py` without changing package-level authority behavior.

- [ ] **Step 4: Verify state serialization and reload.**

Run:

```text
py -3 -m pytest tests/unit/test_structural_models.py tests/unit/test_state_foundation.py -q
```

Expected: the structural definition survives JSON round-trip, contributes to `state_hash`, and existing state tests remain green.

## Task 4: Add Source-Bound Request And Computational Identity

**Files:**
- Create: `src/mechcad_harness/structural_request.py`
- Create: `tests/unit/test_structural_request.py`

**Interfaces:**
- Consume: `StructuralAnalysisDefinition`, `structural_definition_hash`, and shared semantic enums from `models.structural`.
- Produce: `StructuralSourceBinding`, `MeshRefinement`, `MeshSpecification`, `StructuralExecutionSettings`, `StructuralAnalysisRequest`, `structural_request_hash`, and `StructuralAnalysisRequest.validate_against(definition)`.

- [ ] **Step 1: Write failing request identity tests.**

Cover these exact invariants:

```python
base = make_request(definition, global_target_size_mm=5.0)
refined = make_request(definition, global_target_size_mm=2.5)
changed_outputs = make_request(definition, requested_result_fields=("displacement",))
changed_limits = make_request(definition, max_runtime_seconds=90.0)

assert base.source_binding.definition_hash == structural_definition_hash(definition)
assert base.request_hash != refined.request_hash
assert base.request_hash != changed_outputs.request_hash
assert base.request_hash != changed_limits.request_hash
assert base.source_binding.definition_hash == refined.source_binding.definition_hash
```

Also cover definition ID/hash mismatch, source revision/hash validation, empty or duplicate selected cases, inactive cases, unsupported result fields, invalid mesh sizes, invalid refinement regions, nonpositive resource limits, and equivalent refinement tuples producing the same request hash after canonical region-ID ordering.

- [ ] **Step 2: Run the request tests to verify they fail.**

Run:

```text
py -3 -m pytest tests/unit/test_structural_request.py -q
```

Expected: collection fails because `structural_request.py` does not exist.

- [ ] **Step 3: Implement source binding and computational request models.**

Implement:

```python
class StructuralSourceBinding(Model):
    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    definition_id: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    target_body_id: str = Field(min_length=1)
    source_program_hash: str = Field(min_length=1)
    geometry_identity: str = Field(min_length=1)
    geometry_artifact_id: str = Field(min_length=1)
    geometry_artifact_hash: str = Field(min_length=1)
```

Implement `MeshSpecification` with `element_family="c3d10"`, positive global size, a tuple of semantic-region refinements, nonempty quality-policy ID, and nonempty mesher-settings version. Each refinement has `region_id` and positive `target_size_mm`; duplicate region IDs are rejected and the tuple is canonicalized in ascending `region_id` order because refinement order is not semantic. Implement `StructuralExecutionSettings` with positive `max_elements`, positive finite `max_runtime_seconds`, positive `max_output_bytes`, and `retain_raw_artifacts`.

Implement `StructuralAnalysisRequest` with a `request_hash="pending"` default and an after-validator patterned after existing M10 request models. Hash the exact payload below, excluding only `request_hash`:

```python
payload = {
    "source_binding": request.source_binding.model_dump(mode="json"),
    "selected_load_case_ids": list(request.selected_load_case_ids),
    "mesh_specification": request.mesh_specification.model_dump(mode="json"),
    "requested_result_fields": list(request.requested_result_fields),
    "execution_settings": request.execution_settings.model_dump(mode="json"),
}
```

Use sorted keys and compact separators, prefix with `sha256:`, and reject a caller-supplied nonmatching hash. Do not include provider/runtime identity, timestamps, temporary paths, or solver result values.

- [ ] **Step 4: Implement definition validation at the request boundary.**

Implement:

```python
def validate_against(self, definition: StructuralAnalysisDefinition) -> None:
    if definition.id != self.source_binding.definition_id:
        raise ValueError("request definition ID does not match canonical definition")
    if structural_definition_hash(definition) != self.source_binding.definition_hash:
        raise ValueError("request definition hash does not match canonical definition")
    if definition.target_body_id != self.source_binding.target_body_id:
        raise ValueError("request target body does not match canonical definition")
    defined_cases = {case.id: case for case in definition.load_cases}
    if any(case_id not in defined_cases or not defined_cases[case_id].active for case_id in self.selected_load_case_ids):
        raise ValueError("request selects an unknown or inactive load case")
```

The request validator itself rejects empty/duplicate selected IDs; `validate_against` performs canonical definition cross-checks. It does not resolve CAD, mesh, or providers.

- [ ] **Step 5: Run request and model regressions.**

Run:

```text
py -3 -m pytest tests/unit/test_structural_request.py tests/unit/test_structural_models.py tests/unit/test_state_foundation.py -q
```

Expected: all request identity, definition-preserving mesh variation, source binding, and existing state tests pass.

## Task 5: Connect Ownership, Dependency Invalidation, And Final Regression Coverage

**Files:**
- Modify: `config/ownership.yaml`
- Modify: `config/dependencies.yaml`
- Modify: `tests/unit/test_changes.py`
- Modify: `tests/unit/test_structural_models.py`
- Modify: `tests/unit/test_state_foundation.py`

**Interfaces:**
- Consume: canonical `/structural_analysis_definitions/<id>` path and existing `OwnershipPolicy`, `ChangeEngine`, `DependencyGraph`, and `EvidenceStore` behavior.
- Produce: governed structural definition mutation and invalidation semantics; no structural execution service.

- [ ] **Step 1: Write failing ownership and dependency tests.**

Add tests that:

```python
def test_structural_owner_can_add_definition_but_other_owner_cannot(tmp_path):
    policy = OwnershipPolicy.from_file("config/ownership.yaml")
    policy.check("/structural_analysis_definitions/DEF-1", "mechcad-structural")
    with pytest.raises(OwnershipViolationError):
        policy.check("/structural_analysis_definitions/DEF-1", "mechcad-materials")

def test_structural_definition_change_invalidates_structural_analysis(tmp_path):
    graph = DependencyGraph.from_yaml("config/dependencies.yaml")
    impact = graph.impact(("/structural_analysis_definitions/DEF-1",))
    assert "analysis.structural" in impact.direct_nodes
    assert "validation.structural" not in impact.direct_nodes
    assert "validation.structural" in impact.all_nodes
```

Use the repository's actual `DependencyGraph` API in the test fixture; the assertion must verify the configured invalidation node rather than merely reading YAML text.

- [ ] **Step 2: Run the focused tests to verify they fail.**

Run:

```text
py -3 -m pytest tests/unit/test_changes.py tests/unit/test_structural_models.py -q
```

Expected: structural ownership is absent and the dependency rule does not yet invalidate `analysis.structural`.

- [ ] **Step 3: Add the structural owner and dependency rule.**

Add to `config/ownership.yaml`:

```yaml
- path: /structural_analysis_definitions/*
  owner: mechcad-structural
```

Add to `config/dependencies.yaml`:

```yaml
- when:
    - /structural_analysis_definitions/*
  invalidates:
    - analysis.structural
```

The existing `analysis.structural -> validation.structural` edge supplies the transitive validation impact. Do not add request, mesh, solver, or artifact paths to canonical ownership or invalidation configuration in M11-2.

- [ ] **Step 4: Verify ChangeEngine collection mutation and full unit regressions.**

Use a real `ChangeProposal` with path `/structural_analysis_definitions/DEF-1` and actor `mechcad-structural` to prove the existing list-item `id` resolver can add/replace/remove a definition. Do not modify `ChangeEngine` unless this exact existing collection convention fails; if it fails, stop and report the concrete incompatibility rather than introducing a second path grammar.

Run:

```text
py -3 -m pytest tests/unit/test_changes.py tests/unit/test_structural_models.py tests/unit/test_structural_request.py tests/unit/test_state_foundation.py -q
py -3 -m compileall src/mechcad_harness -q
git diff --check -- src/mechcad_harness/models/structural.py src/mechcad_harness/structural_request.py src/mechcad_harness/models/design.py src/mechcad_harness/models/__init__.py tests/unit/test_structural_models.py tests/unit/test_structural_request.py
```

Expected: all focused tests pass, compileall exits successfully, and no new whitespace diagnostics appear.

## M11-2 Exit Criteria

- Canonical definitions contain engineering semantics only.
- Requests contain mesh/output/execution settings and hash them deterministically.
- Mesh variation preserves definition hash and changes request hash.
- Material properties retain independent authority/source/context/conversion provenance.
- Authority policy evaluates each criterion's consumed properties.
- One-body/one-assignment and initial physics invariants fail closed.
- Loads, supports, criteria, and semantic regions are typed and cross-validated.
- DesignState, ChangeEngine ownership, dependency invalidation, serialization, and hash behavior are covered.
- No M11-3 provider, solver, mesher, artifact, or production orchestration code exists.
- M9/M10 regressions remain green.

No commit is part of this workspace execution plan; the repository instruction is to preserve the existing worktree and avoid commits unless explicitly requested.
