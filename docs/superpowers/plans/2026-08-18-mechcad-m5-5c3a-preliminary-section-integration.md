# M5.5C-3A Preliminary Section Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure normalized material-times-section calculator and a source-ID-only ToolBroker operation for preliminary mass and stiffness properties.

**Architecture:** `section_engineering.py` owns strict models, source records, unit conversion, and pure arithmetic. `tools/section_engineering.py` owns persisted ToolResult resolution, integrity checks, normalized parsing, and registration. The calculator never accesses persistence or third-party backends; the public handler never accepts inline historical result copies.

**Tech Stack:** Python 3.11+, Pydantic v2, existing MechCAD models, existing ToolBroker/RunStore, pytest. No new dependency.

## Global Constraints

- Do not begin C-3B, stress/strength verification, or load-case analysis.
- Do not commit.
- Do not add dependencies.
- Do not call `bd_materials` or `sectionproperties` from the integration calculator.
- Public ToolBroker input accepts only persisted result IDs.
- All contributing ToolResults must share project ID, run ID, bound revision, and bound state hash.
- Every derived output exists as `DerivedEngineeringValue`, including unavailable values.
- Unsupported units, invalid available values, source hash failures, and binding mismatches fail closed.
- Derived authority inherits material authority and is never upgraded by arithmetic.
- Native integration ToolResult backend provenance is `None`; contributing provenance remains structured in normalized output.
- Do not implement stress, strength, yield, safety-factor, buckling, fatigue, material selection, manufacturing, optimization, OpenCode, agents, MCP, SQL, or C-3B.

---

### Task 1: Add Pure Integration Models and Arithmetic

**Files:**
- Create: `src/mechcad_harness/section_engineering.py`
- Test: `tests/unit/test_section_engineering.py`

**Interfaces:**
- `DerivedPropertyStatus` enum with `AVAILABLE`, `UNAVAILABLE`.
- `DerivedEngineeringValue` with property, unit, status, min/max/representative values, authority, source dependencies, value semantics, and optional reason.
- `IntegrationSourceRecord` with result ID, source task ID, tool identity, project/run identity, revision/hash, output hash, and optional backend provenance.
- `PreliminarySectionEngineeringCalculatorInput` containing normalized material, geometry, optional warping, and source records.
- `PreliminarySectionEngineeringResult` containing section facts, five explicit derived values, assumptions, contributing provenance, persisted source records, and warnings.
- `calculate_preliminary_section_engineering(input) -> PreliminarySectionEngineeringResult`.

- [ ] **Step 1: Write failing model and arithmetic tests**

```python
def test_aluminum_rectangle_preserves_ranges_and_representative_mass():
    result = calculate_preliminary_section_engineering(aluminum_rectangle_input())
    assert result.mass_per_length.status is DerivedPropertyStatus.AVAILABLE
    assert result.mass_per_length.representative_value == pytest.approx(14.05)
    assert result.axial_rigidity_ea.min_value == pytest.approx(340_000_000)
    assert result.axial_rigidity_ea.max_value == pytest.approx(360_000_000)
    assert result.axial_rigidity_ea.representative_value is None


def test_missing_shear_modulus_is_explicitly_unavailable():
    result = calculate_preliminary_section_engineering(aluminum_rectangle_input())
    assert result.torsional_rigidity_gj.status is DerivedPropertyStatus.UNAVAILABLE
    assert result.torsional_rigidity_gj.reason == "SHEAR_MODULUS_UNAVAILABLE"


def test_unsupported_units_fail_closed():
    value = aluminum_rectangle_input()
    value.material.properties["elastic_modulus"].unit = "MPa"
    with pytest.raises(ValueError, match="unsupported unit"):
        calculate_preliminary_section_engineering(value)
```

- [ ] **Step 2: Run focused tests and verify the expected missing-module failure**

Run: `py -m pytest tests/unit/test_section_engineering.py -q`

Expected: FAIL because the integration module does not exist.

- [ ] **Step 3: Implement strict models and unit conversion**

Implement `gpa_to_n_per_mm2(value)` as `value * 1000` and reject all units other than exact `GPa` for E/G, `kg/m^3` for density, and the exact section units used by C-2A/C-2B. Validate finite numbers and reject numeric values on unavailable derived properties.

- [ ] **Step 4: Implement range-preserving arithmetic**

Use finite source min/max endpoints without midpoint fabrication. Produce representative outputs only when all required source properties contain representative values. Produce all five derived fields regardless of availability.

- [ ] **Step 5: Implement partial-result and authority semantics**

Use explicit unavailable reasons:

```text
MATERIAL_DENSITY_UNAVAILABLE
ELASTIC_MODULUS_UNAVAILABLE
SHEAR_MODULUS_UNAVAILABLE
TORSION_CONSTANT_UNAVAILABLE
```

Propagate material authority to each available derived property, add homogeneous/isotropic assumptions, and add typical-reference/manufacturing warnings without adding stress or strength logic.

The integration registration must suppress `analysis.structural` Evidence for
successful partial results unless EA, EIx, and EIy are all `AVAILABLE`. Missing
mass density or explicit G/J does not suppress Evidence when those three
stiffness values are available.

- [ ] **Step 6: Run focused pure-calculator tests and verify pass**

Run: `py -m pytest tests/unit/test_section_engineering.py -q`

Expected: PASS.

### Task 2: Add Immutable Source Resolution and Public Tool Input

**Files:**
- Create: `src/mechcad_harness/tools/section_engineering.py`
- Modify: `src/mechcad_harness/tools/__init__.py`
- Test: `tests/unit/test_section_engineering_tools.py`

**Interfaces:**
- `PreliminarySectionEngineeringToolInput(material_result_id, section_geometry_result_id, section_warping_result_id=None)`.
- `resolve_source_result(controller, project_id, run_id, result_id, expected_tools, revision, state_hash) -> (ToolResult, parsed_model, IntegrationSourceRecord)`.
- `calc_preliminary_section_engineering(value, controller context) -> PreliminarySectionEngineeringResult`.
- `SectionEngineeringTools.registrations()` containing `mechcad-calc-preliminary-section-engineering-properties@1.0`.

- [ ] **Step 1: Write failing source-integrity and public-input tests**

Cover:

- inline normalized material fields are rejected by Pydantic extra-forbid;
- unknown result ID rejected;
- failed source result rejected;
- wrong producer tool rejected;
- output hash mismatch rejected;
- revision mismatch rejected;
- state hash mismatch rejected;
- cross-run contributors rejected;
- persisted output is parsed instead of caller data.

```python
def test_public_tool_input_accepts_ids_not_inline_results():
    with pytest.raises(Exception):
        PreliminarySectionEngineeringToolInput(material={})
```

- [ ] **Step 2: Run the focused tests and verify expected missing-tool failures**

Run: `py -m pytest tests/unit/test_section_engineering_tools.py -q`

Expected: FAIL because the public model, resolver, and registration do not exist.

- [ ] **Step 3: Implement exact persisted ToolResult loading**

Load the immutable result from the existing run-scoped `tool_results/<result_id>.json` path. Recompute the persisted output hash using existing `payload_hash`, require equality with `result.output_hash`, require `SUCCEEDED`, and require expected producer tool/version plus exact project/run/revision/state hash.

- [ ] **Step 4: Parse only verified persisted output**

Parse verified `output` into `TypicalMaterialPropertiesResult`, `SectionGeometryResult`, or `SectionWarpingResult`. Build `IntegrationSourceRecord` from persisted identity and provenance. Never accept caller-supplied result copies.

- [ ] **Step 5: Invoke only the pure calculator**

After all sources pass verification, create `PreliminarySectionEngineeringCalculatorInput` and call `calculate_preliminary_section_engineering`. Do not import any backend adapter or access external objects.

- [ ] **Step 6: Register the focused ToolBroker operation**

Use output model `PreliminarySectionEngineeringResult`, no integration backend provenance handler, and Evidence node `analysis.structural`. Let existing ToolBroker supply task binding, call persistence, output hashing, failure persistence, and Evidence creation.

- [ ] **Step 7: Run focused tool tests and verify pass**

Run: `py -m pytest tests/unit/test_section_engineering_tools.py -q`

Expected: PASS.

### Task 3: Add Golden Cases and Regression Tests

**Files:**
- Modify: `tests/unit/test_section_engineering.py`
- Modify: `tests/unit/test_section_engineering_tools.py`

- [ ] **Step 1: Add independent aluminum oracle**

Use normalized `Alu_G7075_T6` semantics and rectangle `50 x 100 mm`. Assert:

```text
mass_per_length = 14.05 kg/m
EA = 340,000,000..360,000,000 N
EIx = 68,000*4,166,666.666... .. 72,000*4,166,666.666... N*mm^2
EIy = 68,000*1,041,666.666... .. 72,000*1,041,666.666... N*mm^2
```

- [ ] **Step 2: Add independent PLA and Nylon range tests**

Use PLA `10 x 20 mm`, density `1240 kg/m^3`, E `3.0..3.9 GPa`; assert range propagation, representative mass, authority, and assumptions. Use the accepted Nylon fixture for equivalent range/authority behavior without interpreting printed anisotropy.

- [ ] **Step 3: Add explicit GJ tests**

Use a direct normalized fixture with explicit `shear_modulus` in `GPa` to assert `GJ = G*1000*J`. Separately assert unavailable GJ when shear modulus or warping J is absent. Do not derive G from E and Poisson ratio.

- [ ] **Step 4: Add ToolBroker success/failure and Evidence-completeness tests**

Assert permission enforcement, stale rejection, ToolCall-before-calculation, source task IDs preserved in contributing lineage, successful complete Evidence, successful partial ToolResult with no Evidence, successful stiffness-only Evidence despite unavailable mass/GJ, no Evidence on source-integrity failure, and unchanged canonical DesignState.

- [ ] **Step 5: Run all integration tests and verify pass**

Run: `py -m pytest tests/unit/test_section_engineering.py tests/unit/test_section_engineering_tools.py -q`

Expected: PASS.

### Task 4: Document C-3A Boundary

**Files:**
- Modify: `README.md`
- Test: `tests/unit/test_section_engineering_docs.py`

- [ ] **Step 1: Write failing documentation assertions**

Assert README contains C-3A flow, source-ID resolution, immutable output-hash verification, explicit unavailable derived values, exact units, authority propagation, GJ prerequisites, homogeneous/isotropic assumptions, and C-3B exclusion.

- [ ] **Step 2: Run documentation test and verify failure**

Run: `py -m pytest tests/unit/test_section_engineering_docs.py -q`

Expected: FAIL before documentation is added.

- [ ] **Step 3: Document the native integration flow and exclusions**

Explain that C-3A arithmetic is native MechCAD logic with no backend provenance, while source records retain each contributing ToolResult and BackendProvenance. Document no new dependencies and no stress/strength/pass-fail behavior.

- [ ] **Step 4: Run documentation test and verify pass**

Run: `py -m pytest tests/unit/test_section_engineering_docs.py -q`

Expected: PASS.

### Task 5: Final Verification

**Files:**
- All new/modified C-3A files and tests

- [ ] **Step 1: Run full suite**

Run: `py -m pytest -q`

Expected: all existing tests pass.

- [ ] **Step 2: Run focused integration suite**

Run: `py -m pytest tests/unit/test_section_engineering.py tests/unit/test_section_engineering_tools.py tests/unit/test_section_engineering_docs.py -q`

Expected: all focused tests pass.

- [ ] **Step 3: Run compile and diff checks**

Run: `py -m compileall -q src tests`

Run: `git diff --check`

Expected: both pass.

- [ ] **Step 4: Run prohibited-scope scan**

Search new C-3A files for `bd_materials`, `sectionproperties`, `calculate_stress`, `yield`, `safety`, `von Mises`, `buckling`, `fatigue`, material selection, optimization, C-3B, OpenCode, agents, MCP, and SQL. Confirm backend names appear only in expected producer-tool allowlists/provenance types and forbidden calculations are absent.

- [ ] **Step 5: Review status without committing**

Run: `git status --short; git diff --stat`

Confirm no unrelated changes were reverted and no commit was created.
