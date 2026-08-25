# MechCAD M11-2 Structural Authority Model — Completion / Audit Report

**Date:** 2026-08-23
**Author:** independent audit closure of the uncommitted M11-2 implementation candidate
**Baseline accepted before this task:** `M10_FULLY_CLOSED_LIVE_VERIFIED`, `M11_1_STRUCTURAL_FEA_ARCHITECTURE_READY`

## Final Disposition

`M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED`

The uncommitted M11-2 bytes implement exactly the typed structural authority/request model specified in `docs/superpowers/specs/2026-08-23-m11-2-structural-authority-model.md`, and satisfy the M11-1 architecture constraints in `docs/superpowers/specs/2026-08-23-m11-1-structural-fea-architecture.md`. No M11-3 runtime capability (Gmsh meshing, CalculiX execution, FreeCAD FEM, raw-result parsing, FEA production orchestration) was introduced.

## Accepted Baseline

- `M10_FULLY_CLOSED_LIVE_VERIFIED` — preserved; no M9/M10 behavior changed.
- `M11_1_STRUCTURAL_FEA_ARCHITECTURE_READY` — preserved; M11-1 remains design-only.
- Newly recorded: `M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED`.
- The M11-2 spec disposition `M11_2_STRUCTURAL_AUTHORITY_MODEL_SPEC_READY_FOR_IMPLEMENTATION` is now superseded by the implementation-verified marker above. The two are distinct: the spec marker denotes a design ready for implementation; this report records that the implemented bytes were independently audited and closed.

## M11-2 Scope

Add the smallest credible typed structural-analysis authority model:

- canonical `DesignState.structural_analysis_definitions`;
- `StructuralAnalysisDefinition` = accepted engineering semantics only;
- `StructuralAnalysisRequest` = source-bound execution input carrying `MeshSpecification`, requested result fields, and execution/resource controls;
- property-specific material authority, semantic regions, typed loads/supports/criteria, deterministic definition/request identities;
- pure validation and identity tests only.

Out of scope (deferred to M11-3+): FreeCAD region realization, Gmsh meshing, mesh artifacts, CalculiX deck/solver execution, raw-result parsing, typed structural fields, acceptance evaluation against solver results, durable structural Evidence, analytical cantilever validation, assembly connections, nonlinear physics, dynamics, thermal, wind, and domain-specific load derivation.

## Canonical DesignState Path

`DesignState.structural_analysis_definitions: list[StructuralAnalysisDefinition]` (`src/mechcad_harness/models/design.py:82`). It is the canonical engineering-authority path. A `DesignState`-level after-validator rejects duplicate definition IDs (`design.py:98-102`); the state hash automatically includes definitions because it serializes the full state.

The definition model (`models/structural.py`) deliberately excludes computational discretization and execution tuning. Confirmed by test `test_definition_cross_validation_requires_active_cases_and_references` asserting `"mesh_specification" not in StructuralAnalysisDefinition.model_fields`. `MeshSpecification`, requested result fields, and `StructuralExecutionSettings` live only on `StructuralAnalysisRequest`, not in canonical state. Ordinary mesh refinement therefore does not require or create a `DesignState` mutation. Result: M11_2 marker is satisfied; no `M11_2_NEEDS_FIXES` for canonical/noncanonical split.

## Mutation Authority

- All canonical structural models use `model_config = ConfigDict(frozen=True, extra="forbid")` (`models/structural.py`), so instances cannot be mutated after construction. Request models are also `frozen=True` (`structural_request.py`).
- The only accepted canonical mutation path is `ChangeProposal -> ChangeSet -> ChangeEngine -> immutable DesignState revision`, proven by `tests/unit/test_state_foundation.py:205` `test_change_engine_mutates_structural_definition_collection_items`, which uses real `ChangeOperation` add/replace/remove over `/structural_analysis_definitions/DEF-1` with actor `mechcad-structural` and a `StateManager`/`ChangeEngine` boundary.
- No analysis service, agent, solver, or mesher layer exists in M11-2 that could mutate definitions. Fail-closed behavior against unauthorized mutation is covered by the ownership test below and by the frozen models raising `ValidationError` on attribute assignment (`test_structural_property_snapshot_is_immutable`, `test_assignment_and_nested_structural_records_are_immutable`, `test_structural_request_records_are_immutable_and_hash_stays_bound`).

## Material Snapshot / Property Authority

`StructuralMaterialPropertySnapshot` (`models/structural.py:158`) is property-specific: every consumed property stores `property_name`, `value`, `normalized_unit`, `source_identity`, `authority` (`MaterialDataAuthority`), `context` (explicit `None` allowed, never guessed), and `conversion_provenance`. Normalized units are enforced per property (E/yield in `MPa`, nu in `ratio`, density in `kg/m^3`) with finite/physical range checks (`-1 < nu < 0.5`, positive E/density/yield).

`StructuralMaterialAssignment` has **no** assignment-level authority field — proven by `test_assignment_does_not_have_assignment_level_authority` which asserts `"authority" not in StructuralMaterialAssignment.model_fields` and that injecting one raises `ValidationError`. Mixed authorities remain representable, e.g. E `supplier_datasheet`, nu `typical_reference`, yield `measured` (`test_authority_evaluator_accepts_mixed_allowed_authorities`).

`bd_materials` remains candidate/reference-only: it is never imported or referenced in the M11-2 structural models; the only material source in code is `MaterialDataAuthority` enum reuse. No material-library candidate silently becomes accepted canonical material.

## Loads

`StructuralLoadCase` carries stable `id`, `name`, `active` flag, and a discriminated union of typed primitives: `StructuralResultantForce`, `StructuralSurfacePressure`, `StructuralBodyAcceleration` (`models/structural.py:333`). Each primitive requires explicit semantics:

- `ResultantForce`: `magnitude_n` finite positive, `direction_xyz` finite nonzero, explicit `frame` (`component_local`/`assembly_world`), and fixed distribution `uniform_surface_traction_equivalent` (any other distribution such as `point_force` is rejected — `test_resultant_force_requires_explicit_distribution_and_frame`).
- `SurfacePressure`: `pressure_mpa` finite, explicit `signed_normal_convention`, explicit frame.
- `BodyAcceleration`: targets `target_body_id`, explicit `acceleration_unit="mm/s^2"`, finite acceleration vector.

Ambiguous magnitude-only definitions are impossible: `force = 100` without target/units/direction/frame cannot be constructed. Load IDs are unique across the definition; body-acceleration loads must target the definition's `target_body_id`.

## Boundary Conditions

`StructuralFixedSupport` (`models/structural.py:348`) binds a semantic `target_region_id`, a nonempty duplicate-free `applies_to_load_case_ids` tuple, an explicit `frame`, and exactly the three translational solid DOFs `("ux","uy","uz")` in canonical order. Prescribed displacement and rotational DOFs are not accepted (`test_fixed_support_requires_all_solid_translation_dofs_and_case_ids`). It stores semantics only; it does not emit solver node sets and never treats a raw `FaceN` as stable.

## Semantic Regions

`StructuralRegionDefinition` (`models/structural.py:240`) is the canonical target identity used by loads, supports, and criteria. It requires exactly one nonempty source identity (`source_feature_id` XOR `source_primitive_id`), a `semantic_role`, `geometry_kind`, a `selector_kind`, deterministic immutable `selector_parameters`, `expected_cardinality > 0`, and `resolver_version`.

Raw backend topology identifiers are rejected. `_RAW_IDENTITY_PREFIXES = ("face","edge","vertex","topology","raw_topology","mesh","gmsh","calculix")` plus value patterns (`FaceN`, `EdgeN`, `VertexN`, `MeshNodeN`, `GmshEntityN`, `CalculiXSetN`) cause rejection of either the `selector_kind`, a raw key, or a raw value (`test_raw_face_selector_is_not_a_canonical_region`, `test_semantic_region_rejects_raw_topology_identity_parameters`, `test_raw_topology_and_solver_identity_is_rejected_for_all_selector_kinds`, `test_exact_raw_identity_values_are_rejected_for_every_selector_kind`).

Selector parameters are genuinely immutable and not a `dict`: `selector_parameters` is `_ImmutableSelectorParameters(Mapping)` with all mutators (`__setitem__`, `update`, `clear`, `pop`, etc.) raising `TypeError`, and base-`dict` mutation (`dict.__setitem__`, `dict.clear`) also blocked (`test_selector_parameters_are_immutable_and_hash_stable`, `test_selector_parameters_reject_base_dict_mutation_and_preserve_hash`). Missing/ambiguous/wrong-cardinality resolution fails closed at the M11-3 resolver stage; M11-2 rejects empty source identity and nonpositive cardinality (`test_region_requires_exactly_one_source_identity_and_positive_cardinality`). No fallback to raw `FaceN`.

## StructuralAnalysisDefinition

`StructuralAnalysisDefinition` (`models/structural.py:481`) contains only accepted engineering semantics: `id`, `name`, `analysis_kind`, `target_body_id`, `regions`, `material_assignment`, `load_cases`, `boundary_conditions`, `acceptance_criteria`, `material_authority_policy`, `physical_assumptions`. A single after-validator enforces: exactly one material assignment whose target body equals the definition target; at least one active load case; unique load-case/load/support/criterion/region IDs; every load/support/criterion region reference exists; supports reference defined active cases; criteria reference active cases and declared policy properties; required E/nu (and density when a body-acceleration load is present) are present; yield strength may be absent and only makes its dependent criterion not evaluable.

`structural_definition_hash` (`models/structural.py:650`) hashes the canonical JSON payload with sorted keys and compact separators, includes all engineering fields, and excludes timestamps, request fields, runtime fields, and transient paths.

## StructuralAnalysisRequest

`StructuralAnalysisRequest` (`structural_request.py:85`) is the derived execution input. `StructuralSourceBinding` binds `project_id`, `source_revision`, `source_state_hash`, `definition_id`, `definition_hash`, `target_body_id`, `source_program_hash`, `geometry_identity`, `geometry_artifact_id`, `geometry_artifact_hash` — all source-identity fields, including the canonical definition hash. The request also binds `selected_load_case_ids`, `mesh_specification`, `requested_result_fields`, `execution_settings`.

`MeshSpecification` holds computational settings only (`element_family="c3d10"`, positive `global_target_size_mm`, duplicate-free region refinements canonicalized in ascending `region_id` order, `quality_policy_id`, `mesher_settings_version`). `StructuralExecutionSettings` holds resource controls only (`max_elements`, `max_runtime_seconds`, `max_output_bytes`, `retain_raw_artifacts`); no solver executable, provider identity, backend version, solver text, or result hash field exists.

`structural_request_hash` (`structural_request.py:129`) hashes source binding, selected load-case order, mesh specification, requested output fields, and execution settings, excluding timestamps, temp paths, runtime-discovered provider identity, and result values. Two requests differing only in mesh size or outputs produce different request hashes while retaining the same `definition_hash` (`test_request_binds_definition_and_hashes_computational_inputs`, `test_refinement_order_is_canonical_and_hash_is_order_insensitive`).

## Deterministic Identity

- Definition identity is invariant to mesh/request fields and includes all canonical engineering fields; changing only `MeshSpecification` changes request hash but not definition hash (verified in request tests).
- Request identity binds exact source binding, ordered selected load cases, mesh spec, requested result fields, and execution settings.
- Hashes exclude volatile data: no timestamp, PID, temp path, or incidental run directory name is included (payloads are pure canonical JSON of model fields; `run_id` is never a structural identity field).
- Repeat construction yields identical hashes (`test_structural_request_records_are_immutable_and_hash_stays_bound`, `test_selector_parameters_reject_base_dict_mutation_and_preserve_hash`).

## Ownership Integration

`config/ownership.yaml` adds `/structural_analysis_definitions/*` owned by `mechcad-structural`. `test_structural_owner_can_add_definition_but_other_owner_cannot` (`tests/unit/test_changes.py:105`) proves `mechcad-structural` is allowed and `mechcad-materials` is rejected with `OwnershipViolationError`. No generic/unknown owner can bypass the structural mutation boundary because the path is explicitly governed and all other owners fail closed.

## Dependency Invalidation

`config/dependencies.yaml` adds:

```yaml
- when:
    - /structural_analysis_definitions/*
  invalidates:
    - analysis.structural
```

The existing edge `analysis.structural -> validation.structural` supplies the transitive `validation.structural` impact. `test_structural_definition_change_invalidates_structural_analysis` (`tests/unit/test_structural_models.py:1050`, also `test_structural_definition_survives_state_json_round_trip` via `test_state_foundation.py`) uses the real `DependencyGraph.from_yaml` and asserts `analysis.structural` is a direct invalidated node and `validation.structural` is transitively included while not a direct node.

A changed structural definition therefore stales `analysis.structural` and `validation.structural`; the request/mesh are noncanonical and do not create a canonical revision, so they cannot falsely keep a definition valid.

Mechanism A (canonical dependency invalidation) covers only changes to the `StructuralAnalysisDefinition` content itself. Material assignment, loads, supports, criteria, regions, and target-body *identity* are all fields of the definition, so altering any of them produces a new definition revision and fires the rule. The **source geometry hash, source state hash, and source revision are NOT fields of the definition** — they are carried only in `StructuralSourceBinding`. Therefore, when the source geometry changes but the definition remains semantically unchanged (same `target_body_id`, same regions/loads/supports/criteria), mechanism A does **not** fire.

Mechanism B (`StructuralSourceBinding` revision/state/hash validation) is **not implemented in M11-2**: `StructuralAnalysisRequest.validate_against(definition)` (`structural_request.py:108`) checks the definition `id`/`definition_hash`/`target_body_id` and load-case/refinement references, but it does **not** compare `source_revision`, `source_state_hash`, `geometry_artifact_hash`, or `source_program_hash` against the live `DesignState`. Mechanism C (`ProductionApplication` current-state binding) and mechanism D (future M11-3 geometry realization binding) are explicitly out of M11-2 scope.

Consequently, M11-2 does **not** fail closed against a changed source state when the definition is semantically unchanged. This is an explicitly accepted limitation, not an implementation defect: M11-1 §3 records `PREACCEPTED_CALLER_CONTRACT_ONLY` and `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED` as current trust limits, and the M11-2 spec §13 states it does not alter them. The source-binding fields are carried so that a future M11-3 service (mechanism D) can validate them against realized geometry and current state before executing or persisting any request/result. M11-2 itself produces no structural request/result artifacts and has no replay service, so the stale-binding scenario cannot arise within M11-2; the gap must be closed before M11-3 executes or persists any request.

## Source Binding

`StructuralAnalysisRequest` is source-bound (`structural_request.py:18`). `validate_against(definition)` (`structural_request.py:108`) rejects:
- definition ID mismatch (`request definition ID does not match canonical definition`);
- definition hash mismatch (`request definition hash does not match canonical definition`);
- target body mismatch;
- selection of unknown or inactive load cases;
- mesh refinement referencing an unknown definition region.

The binding includes `project_id`, `source_revision`, `source_state_hash`, `definition_id`, `definition_hash`, `target_body_id`, `source_program_hash`, `geometry_identity`, `geometry_artifact_id`, `geometry_artifact_hash`. `validate_against` does **not** compare the binding's `source_revision`, `source_state_hash`, `geometry_artifact_hash`, or `source_program_hash` against the live `DesignState`; those are a preaccepted caller contract (see Dependency Invalidation). The current documented limitations `PREACCEPTED_CALLER_CONTRACT_ONLY` and `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED` remain unchanged and are not claimed solved. `run_id` is not a structural engineering identity.

## Fail-Closed Validation

Covered by focused tests (all pass):

- empty/duplicate structural definition: `test_duplicate_structural_definition_ids_fail_closed`.
- invalid/duplicate load-case identities: `test_definition_cross_validation_requires_active_cases_and_references`, request tests for empty/duplicate/unknown/inactive selections.
- unknown selected load case: `test_validate_against_rejects_inactive_or_unknown_cases`.
- malformed material property: `test_invalid_structural_property_units_and_values_fail_closed`, `test_structural_property_snapshot_requires_nonempty_provenance_fields`, `test_structural_property_snapshot_requires_value`.
- missing required elastic property: `test_definition_cross_validation_requires_active_cases_and_references` (removing E fails).
- invalid Poisson ratio: parametrized invalid nu values (`-1.0`, `0.5`) rejected.
- invalid/nonfinite magnitudes: force/pressure/acceleration/refinement/execution tests.
- unsupported/ambiguous units: normalized-unit enforcement per property.
- invalid/raw topology region identity: the four raw-identity test groups.
- mutable/noncanonical selector payload: `test_selector_parameters_reject_base_dict_mutation_and_preserve_hash`.
- invalid support/load target: region-reference and DOF checks; `test_resultant_force_requires_explicit_distribution_and_frame`.
- invalid acceptance criterion: `test_criteria_declare_ordered_consumed_properties_and_reject_invalid_values`.
- source/definition binding mismatch: `test_validate_against_rejects_definition_binding_mismatches`, `test_request_rejects_unsupported_result_fields_and_nonmatching_hash`.

## Explicitly Not Implemented

M11-2 contains no production:
- Gmsh execution / mesh artifact generation;
- CalculiX deck generation / `ccx` execution;
- FEA result parsing / interpreter;
- solver PASS/FAIL evaluation against solver output;
- FreeCAD FEM orchestration or region realization.

The grep of `models/structural.py` and `structural_request.py` for `gmsh|calculix|ccx|mesh|FEM|fem|solve|deck|FEA|artifact` returns only (a) the raw-identity rejection prefix list and error strings, (b) typed `MeshSpecification`/`MeshRefinement`/`mesher_settings_version`/`quality_policy_id`/`retain_raw_artifacts` request metadata fields, and (c) `geometry_artifact_*` source-binding identity strings. No subprocess, import of a mesher/solver, or execution path exists. Interface/type preparation is limited to the accepted M11-2 typed authority model only.

## Regression Results

- Focused M11-2 suite: `153 passed` (`tests/unit/test_structural_models.py`, `tests/unit/test_structural_request.py`, `tests/unit/test_state_foundation.py`, `tests/unit/test_changes.py`).
- Required predecessor regressions (M9/M10/StateManager/ChangeEngine/OwnershipPolicy/dependency invalidation): included in the full run below; `tests/unit/test_state_foundation.py` and `tests/unit/test_changes.py` exercise `StateManager`, `ChangeEngine`, `OwnershipPolicy`, and `DependencyGraph`, and all pass.
- Full suite: `985 passed, 52 skipped` over `py -3 -m pytest tests/` (no timeouts; integration and unit combined).
- `py -3 -m compileall src/mechcad_harness -q`: passed (exit 0).
- `git diff --check` (modified files and new files via `git diff --no-index --check`): clean (only CRLF normalization warnings from pre-existing line-ending state; no trailing-whitespace or other diagnostics).

## Files Changed

New:
- `src/mechcad_harness/models/structural.py`
- `src/mechcad_harness/structural_request.py`
- `tests/unit/test_structural_models.py`
- `tests/unit/test_structural_request.py`

Modified:
- `src/mechcad_harness/models/design.py` — `structural_analysis_definitions` field + duplicate-ID validator.
- `src/mechcad_harness/models/__init__.py` — lazy exports of structural models (no import-cycle, no authority change).
- `config/ownership.yaml` — `/structural_analysis_definitions/*` owner `mechcad-structural`.
- `config/dependencies.yaml` — structural definition invalidates `analysis.structural`.
- `src/mechcad_harness/dependency/graph.py` — minimal YAML parser blank-list-field fix.
- `tests/unit/test_state_foundation.py`, `tests/unit/test_changes.py` — M11-2 coverage.

Unrelated pre-existing worktree modifications (preserved, not part of M11-2): see `git status` (`backends/freecad_assembly.py`, `cad_assembly_manifest.py`, `analysis_provenance.py`, integration/unit tests, `projects/`, `err.txt`, `.superpowers/sdd/*`). These were not introduced by M11-2 and were left untouched.

## Remaining Limitations

- M11-2 is a typed authority/request model only; it performs no FEA, meshing, solving, or acceptance evaluation against solver output.
- Semantic-region resolution against FreeCAD, Gmsh meshing, CalculiX execution, raw-result parsing, and durable structural Evidence are M11-3+ scope and not present.
- `PREACCEPTED_CALLER_CONTRACT_ONLY` and `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED` remain current trust limits.
- `bd_materials` remains candidate/reference-only (`TYPICAL_REFERENCE`); no selection or override authority was added.
- Single solid body / one material assignment / initial linear-static assumptions only.

## Next Milestone Boundary

Do not start M11-3 in this task. The next milestone, M11-3, is scoped (per M11-1 §16) to the trusted source-geometry realization/region resolver, Gmsh mesh provider, mesh artifact/quality contract, direct CalculiX deck/solver provider, and deterministic fake-provider tests — none of which exist in the audited M11-2 bytes.

## Disposition

`M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED`
