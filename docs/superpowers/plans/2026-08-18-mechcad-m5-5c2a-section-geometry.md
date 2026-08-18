# M5.5C-2A Section Geometry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lazy, trusted `sectionproperties` adapter and focused ToolBroker tools for deterministic geometric properties of rectangles, solid circles, and hollow circles.

**Architecture:** MechCAD-owned Pydantic input/result models validate explicit millimetre dimensions and meshing parameters. `SectionPropertiesAdapter` performs lazy health validation, constructs transient upstream geometry, creates a transient mesh, runs only geometric analysis, and normalizes scalar getters plus reproducibility metadata. Tool registrations expose one focused operation per supported shape; existing broker persistence, binding, permissions, provenance, and evidence rules remain authoritative.

**Tech Stack:** Python 3.11+, Pydantic v2, `sectionproperties==3.10.2`, NumPy `>=2,<2.4` in the optional structural profile, SciPy, Shapely, cytriangle, pytest.

## Global Constraints

- Keep the project runtime requirement at Python `>=3.11`.
- Use the validated legacy-host profile: Python 3.12.10, NumPy 2.3.5, SciPy 1.18.0, matplotlib 3.11.1, Shapely 2.1.2, cytriangle 3.0.2, more-itertools 11.1.0, rich 15.0.0.
- Keep `sectionproperties` out of core dependencies; add only a dedicated optional structural group.
- Do not alter the existing `gear` or `materials` optional dependency semantics.
- Use only geometric analysis; do not add warping, torsion, stress, plastic, composite, material, FEA, optimization, OpenCode, agent, MCP, SQL, or mass behavior.
- External Geometry, Section, Shapely, mesh, FEM, and Material objects must remain transient.
- MechCAD section dimensions are explicit millimetres; no DesignState lookup or implicit material is allowed.
- `mesh_size_mm2` is the FEM triangulation parameter; `discretization_points` is the circular boundary approximation parameter.
- Preserve existing ToolBroker permission, stale binding, call-before-execution, immutable result, failed-result, evidence, and canonical-state behavior.
- Do not commit unless explicitly requested.

---

### Task 1: Add Normalized Section Models

**Files:**
- Create: `src/mechcad_harness/sections.py`
- Test: `tests/unit/test_sections.py`

**Interfaces:**
- Produces `RectangleSectionInput(width_mm, height_mm, mesh_size_mm2)`.
- Produces `CircleSectionInput(diameter_mm, discretization_points, mesh_size_mm2)`.
- Produces `HollowCircleSectionInput(outer_diameter_mm, wall_thickness_mm, discretization_points, mesh_size_mm2)`.
- Produces `SectionGeometryResult(section_type, area_mm2, centroid_x_mm, centroid_y_mm, ixx_centroid_mm4, iyy_centroid_mm4, ixy_centroid_mm4, perimeter_mm, radius_of_gyration_x_mm, radius_of_gyration_y_mm, mesh_metadata, backend_provenance)`.

- [ ] **Step 1: Write failing validation tests**

```python
def test_section_inputs_reject_nonpositive_or_nonfinite_values():
    with pytest.raises(Exception):
        RectangleSectionInput(width_mm=0, height_mm=10, mesh_size_mm2=5)
    with pytest.raises(Exception):
        CircleSectionInput(diameter_mm=float("nan"), discretization_points=32, mesh_size_mm2=5)
    with pytest.raises(Exception):
        CircleSectionInput(diameter_mm=10, discretization_points=3, mesh_size_mm2=5)
    with pytest.raises(Exception):
        HollowCircleSectionInput(outer_diameter_mm=10, wall_thickness_mm=5, discretization_points=32, mesh_size_mm2=5)
```

- [ ] **Step 2: Run the focused test and verify the expected missing-model failure**

Run: `pytest tests/unit/test_sections.py::test_section_inputs_reject_nonpositive_or_nonfinite_values -q`

Expected: FAIL because `mechcad_harness.sections` does not yet exist.

- [ ] **Step 3: Implement strict models**

Use finite validators and explicit bounds. Set `section_type` as a string in the result and keep metadata as JSON-safe scalar/dict data. Do not include external object-typed fields.

- [ ] **Step 4: Add result serialization tests**

```python
def test_section_result_is_json_safe_and_has_no_external_object_fields():
    result = SectionGeometryResult(
        section_type="rectangle",
        area_mm2=5000,
        centroid_x_mm=25,
        centroid_y_mm=50,
        ixx_centroid_mm4=4166666.666666667,
        iyy_centroid_mm4=1041666.666666667,
        ixy_centroid_mm4=0,
        perimeter_mm=300,
        radius_of_gyration_x_mm=28.8675,
        radius_of_gyration_y_mm=14.4338,
        mesh_metadata={"mesh_size_mm2": 5.0},
        backend_provenance=None,
    )
    assert "mesh_metadata" in result.model_dump(mode="json")
```

- [ ] **Step 5: Run the focused tests and verify they pass**

Run: `pytest tests/unit/test_sections.py -q`

Expected: PASS.

### Task 2: Implement the SectionProperties Adapter

**Files:**
- Create: `src/mechcad_harness/backends/section_properties.py`
- Modify: `src/mechcad_harness/backends/__init__.py`
- Test: `tests/unit/test_section_backend.py`

**Interfaces:**
- `SectionPropertiesAdapter.identity` is `BackendIdentity(name="section-properties", adapter_version="0.1.0", library_name="sectionproperties", library_version="3.10.2", library_source="pypi", capabilities=("structural.cross_section.geometry",))`.
- `healthcheck() -> BackendHealth` reports missing distributions as `UNAVAILABLE`, approved-version or numerical-profile mismatches as `INCOMPATIBLE`, and the validated dependency set as `AVAILABLE`.
- `rectangle(value: RectangleSectionInput) -> SectionGeometryResult`.
- `circle(value: CircleSectionInput) -> SectionGeometryResult`.
- `hollow_circle(value: HollowCircleSectionInput) -> SectionGeometryResult`.

- [ ] **Step 1: Write failing identity, health, and golden-case tests**

```python
def test_section_backend_identity_is_geometry_only():
    identity = SectionPropertiesAdapter.identity
    assert identity.name == "section-properties"
    assert identity.library_version == "3.10.2"
    assert identity.capabilities == ("structural.cross_section.geometry",)


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_rectangle_golden_case_matches_independent_oracle():
    result = SectionPropertiesAdapter().rectangle(
        RectangleSectionInput(width_mm=50, height_mm=100, mesh_size_mm2=5)
    )
    assert result.area_mm2 == pytest.approx(5000, rel=1e-8)
    assert result.ixx_centroid_mm4 == pytest.approx(50 * 100**3 / 12, rel=1e-8)
    assert result.iyy_centroid_mm4 == pytest.approx(100 * 50**3 / 12, rel=1e-8)
    assert result.ixy_centroid_mm4 == pytest.approx(0, abs=1e-8)
    assert result.centroid_x_mm == pytest.approx(25, abs=1e-8)
    assert result.centroid_y_mm == pytest.approx(50, abs=1e-8)
```

- [ ] **Step 2: Run the focused tests and verify they fail for the missing adapter**

Run: `pytest tests/unit/test_section_backend.py -q`

Expected: FAIL because the adapter and result methods do not exist.

- [ ] **Step 3: Implement lazy health and provenance**

Check metadata for `sectionproperties==3.10.2`, `numpy` in `[2, 2.4)`, and the required distributions `scipy`, `matplotlib`, `shapely`, `cytriangle`, `more-itertools`, and `rich`. Do not import external libraries in `healthcheck()`. `provenance()` must return only `BackendProvenance` scalars.

- [ ] **Step 4: Implement transient geometry execution**

Import only inside execution methods. Use exactly:

```python
geometry = rectangular_section(d=value.height_mm, b=value.width_mm)
geometry.create_mesh(mesh_sizes=value.mesh_size_mm2)
section = Section(geometry)
section.calculate_geometric_properties()
area = section.get_area()
ixx, iyy, ixy = section.get_ic()
perimeter = section.get_perimeter()
rc_x, rc_y = section.get_rc()
```

Use `circular_section(d=..., n=...)` and `circular_hollow_section(d=..., t=..., n=...)` for the circular operations. Retrieve every production geometric quantity from the validated upstream getters:

```python
section.calculate_geometric_properties()
area = section.get_area()
cx, cy = section.get_c()
ixx, iyy, ixy = section.get_ic()
perimeter = section.get_perimeter()
rc_x, rc_y = section.get_rc()
```

Normalize `centroid_x_mm = float(cx)` and `centroid_y_mm = float(cy)`; never derive production centroids from analytic formulas. Convert all returned values to finite Python floats. Record mesh size, discretization points where applicable, and scalar node/element counts only if available through the validated public mesh data; never store the mesh itself.

- [ ] **Step 5: Add hollow-circle analytic and transient-object boundary tests**

```python
def test_hollow_circle_matches_independent_oracle():
    result = SectionPropertiesAdapter().hollow_circle(
        HollowCircleSectionInput(outer_diameter_mm=50, wall_thickness_mm=5, discretization_points=128, mesh_size_mm2=2)
    )
    di = 40
    assert result.area_mm2 == pytest.approx(math.pi * (50**2 - di**2) / 4, rel=2e-3)
    assert result.ixx_centroid_mm4 == pytest.approx(math.pi * (50**4 - di**4) / 64, rel=2e-3)
    assert result.iyy_centroid_mm4 == pytest.approx(result.ixx_centroid_mm4, rel=1e-8)
    assert result.ixy_centroid_mm4 == pytest.approx(0, abs=1e-8)


def test_normalized_result_contains_no_external_geometry_or_mesh_objects():
    result = SectionPropertiesAdapter().rectangle(
        RectangleSectionInput(width_mm=50, height_mm=100, mesh_size_mm2=5)
    )
    dumped = result.model_dump(mode="python")
    assert all(type(value).__module__.split(".")[0] != "sectionproperties" for value in dumped.values())
    assert all("shapely" not in type(value).__module__ for value in dumped.values())
```

- [ ] **Step 6: Add coarse/fine mesh comparison and unavailable/incompatible health tests**

Use rectangle mesh sizes `20` and `2`, compare area and moments to relative tolerance `1e-8` for the rectangle, and describe this as a mesh-independence check rather than a future-style FEM convergence proof. Add centroid assertions for rectangle `(25, 50)` and symmetry-centroid assertions for circle/hollow-circle at the upstream origin. Add coarse/fine `discretization_points` checks showing circle/hollow-circle agreement with independent analytic formulas improves or is preserved as `n` increases; attribute residual error to boundary discretization, not FEM mesh convergence. Monkeypatch metadata lookups to assert missing package is `UNAVAILABLE` and NumPy `2.4.0` is `INCOMPATIBLE`.

- [ ] **Step 7: Run the focused adapter tests and verify they pass**

Run: `C:\Users\vvooj\AppData\Local\Temp\opencode\mechcad-section-validation312\Scripts\python.exe -m pytest tests/unit/test_section_backend.py -q`

Expected: PASS in the validated Python 3.12.10 environment.

### Task 3: Register Focused ToolBroker Operations

**Files:**
- Create: `src/mechcad_harness/tools/sections.py`
- Modify: `src/mechcad_harness/tools/__init__.py`
- Test: `tests/unit/test_section_tools.py`

**Interfaces:**
- `SectionTools.registrations()` returns registrations for:
  - `mechcad-calc-rectangle-section-properties@1.0`
  - `mechcad-calc-circle-section-properties@1.0`
  - `mechcad-calc-hollow-circle-section-properties@1.0`
- Each registration uses the corresponding strict input model and `SectionGeometryResult`, the adapter provenance handler, and evidence node `analysis.structural`.

- [ ] **Step 1: Write failing broker tests**

Cover explicit permission rejection, stale-task rejection, call persistence before handler execution, backend exception producing a failed persisted result, no evidence on failure, successful provenance, and unchanged canonical state bytes. Keep test setup consistent with `test_materials.py` and use a temporary workspace.

- [ ] **Step 2: Run the focused broker tests and verify expected failures**

Run: `pytest tests/unit/test_section_tools.py -q`

Expected: FAIL because `SectionTools` and registrations do not exist.

- [ ] **Step 3: Implement focused handlers and registrations**

Handlers instantiate `SectionPropertiesAdapter` and call exactly one shape method. Do not add a generic execute tool, pass DesignState, or consume `bd_materials`.

- [ ] **Step 4: Export the section models and tools without eager external imports**

Follow the existing materials export pattern, but keep `sectionproperties` imports lazy so `import mechcad_harness` and model-only imports work without the structural extra.

- [ ] **Step 5: Run focused broker tests and verify pass**

Run: `C:\Users\vvooj\AppData\Local\Temp\opencode\mechcad-section-validation312\Scripts\python.exe -m pytest tests/unit/test_section_tools.py -q`

Expected: PASS; failed calculations produce no Evidence and successful results carry exact `section-properties` provenance.

### Task 4: Add Optional Dependency and Documentation

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Test: `tests/unit/test_section_docs.py`

- [ ] **Step 1: Write failing dependency/documentation assertions**

```python
def test_structural_extra_and_axis_contract_are_documented():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "structural = [" in text
    assert '"sectionproperties==3.10.2"' in text
    assert '"numpy>=2,<2.4"' in text
    assert "x = horizontal" in readme
    assert "C-2A" in readme
    assert "warping" in readme
```

- [ ] **Step 2: Run the documentation test and verify it fails**

Run: `pytest tests/unit/test_section_docs.py -q`

Expected: FAIL because the structural extra and C-2A documentation are absent.

- [ ] **Step 3: Add the dedicated optional group**

Add the validated direct runtime set:

```toml
structural = [
    "numpy>=2,<2.4",
    "scipy==1.18.0",
    "matplotlib==3.11.1",
    "shapely==2.1.2",
    "cytriangle==3.0.2",
    "more-itertools==11.1.0",
    "rich[jupyter]==15.0.0",
    "sectionproperties==3.10.2",
]
```

This keeps the accepted legacy NumPy ceiling and makes the validated profile
reproducible; it does not add these packages to core dependencies.

Do not alter `gear` or `materials`.

- [ ] **Step 4: Document the data flow and boundary**

Document the validated runtime profile, axis convention, independent rectangle/circle/hollow-circle formulas, explicit mesh metadata, the distinction between `mesh_size_mm2` FEM triangulation and `discretization_points` circular boundary approximation, transient external objects, backend health statuses, geometric-only scope, and deliberate absence of material integration, warping, torsion, stress, and plastic analysis. State that rectangle coarse/fine results are a mesh-independence check, not a FEM convergence proof, and that circle residuals are boundary-discretization error.

- [ ] **Step 5: Run documentation tests and verify pass**

Run: `pytest tests/unit/test_section_docs.py -q`

Expected: PASS.

### Task 5: Full Verification and Scope Review

**Files:**
- Test: all existing and new tests

- [ ] **Step 1: Run the full suite in the repository environment**

Run: `py -m pytest -q`

Expected: all existing tests pass; structural-extra tests skip if the repository interpreter lacks the optional dependency.

- [ ] **Step 2: Run focused structural tests in the validated Python 3.12.10 environment**

Run: `C:\Users\vvooj\AppData\Local\Temp\opencode\mechcad-section-validation312\Scripts\python.exe -m pytest tests/unit/test_sections.py tests/unit/test_section_backend.py tests/unit/test_section_tools.py tests/unit/test_section_docs.py -q`

Expected: all focused tests pass.

- [ ] **Step 3: Run compile and whitespace verification**

Run: `py -m compileall -q src tests`

Run: `git diff --check`

Expected: both commands pass.

- [ ] **Step 4: Run prohibited-scope scan**

Search the diff and new source for `calculate_warping_properties`, `calculate_stress`, `plastic`, `torsion`, `shear centre`, `Material`, `bd_materials`, `EA`, `EI`, `mass`, `OpenCode`, `MCP`, `SQL`, and generic arbitrary-section execution. Confirm matches are documentation exclusions or pre-existing unrelated code only.

- [ ] **Step 5: Inspect final diff and status without committing**

Run: `git diff --stat; git diff -- pyproject.toml README.md src tests; git status --short`

Confirm only C-2A files and the pre-existing uncommitted M5.5C-1 files are present; do not revert or commit unrelated changes.
