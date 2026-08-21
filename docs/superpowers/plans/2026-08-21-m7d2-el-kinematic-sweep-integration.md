# M7D-2 EL Kinematic Sweep Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate a Yagi-only parametric EL reference with the existing generic discrete kinematic sweep and exact transient FreeCAD measurement path.

**Architecture:** Add a thin `yagi_el_sweep.py` domain adapter that validates layout and EL-reference provenance, retains a caller-supplied fixture-only generic axis, and returns the existing `CadKinematicSweepRequest`. Test it through a synthetic live fixture without changing generic kinematic, transient analysis, or measurement modules.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, FreeCADCmd, existing canonical SHA-256 JSON hashing.

## Global Constraints

- Do not modify `RevoluteAxis`, `CadKinematicSweepRequest`, `CadKinematicSweepService`, `TransientAssemblyAnalysisService`, or `FreeCADTransientAssemblyMeasurementProvider`.
- Do not add EL-specific logic to generic kinematics, AZ/EL transform chains, motors, gears, brackets, risers, bearing, structural, material, load, wind, FEA, or manufacturing scope.
- The EL reference must retain range `(180.0, 300.0)`, selected height `None`, and `EL_AXIS_HEIGHT_PARAMETRIC` status.
- The caller-supplied `RevoluteAxis` is marked `REFERENCE_KINEMATIC_FIXTURE_ONLY`; it is not production geometry or a selected axis location.
- Use discrete samples only; `continuous_sweep_verified` remains `False`.
- Do not create CAD geometry through the adapter, mutate `DesignState`, create `ChangeSet`, create canonical artifacts, or use `ArtifactStore`.
- Do not commit, push, stash, reset, clean, or modify unrelated dirty files.

---

### Task 1: Add the Strict Yagi EL Sweep Adapter

**Files:**
- Create: `tests/unit/test_m7d2_el_sweep_adapter.py`
- Create: `src/mechcad_harness/yagi_el_sweep.py`

**Interfaces:**
- Consumes: `YagiCollisionLayoutSpec`, `YagiELKinematicReference`, `RevoluteAxis`, and `CadKinematicSweepRequest`.
- Produces: `YagiELSweepReference`, `REFERENCE_KINEMATIC_FIXTURE_ONLY`, and `create_yagi_el_sweep_request(layout, el_reference, axis, sample_angles_deg, moving_instance_ids, stationary_instance_ids) -> CadKinematicSweepRequest`.

- [ ] **Step 1: Write the failing adapter tests**

```python
def test_yagi_el_sweep_adapter_preserves_hash_bound_request_order_and_fixture_axis():
    layout = _layout()
    reference = create_yagi_el_reference(layout)
    axis = _axis()

    request = create_yagi_el_sweep_request(
        layout,
        reference,
        axis=axis,
        sample_angles_deg=(-45, 0, 45),
        moving_instance_ids=("ANTENNA_ENVELOPE_0400",),
        stationary_instance_ids=("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )

    assert request.axis == axis
    assert request.sample_angles_deg == (-45.0, 0.0, 45.0)
    assert request.moving_instance_ids == ("ANTENNA_ENVELOPE_0400",)
    assert request.stationary_instance_ids == ("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200")
    assert request.source_assembly_hash == layout.authority_hash


def test_yagi_el_sweep_adapter_rejects_unbound_or_non_parametric_reference():
    with pytest.raises(ValueError, match="layout"):
        create_yagi_el_sweep_request(_layout(), YagiELKinematicReference(source_layout_hash="sha256:other"), ...)
```

- [ ] **Step 2: Run the adapter tests to verify they fail**

Run: `py -m pytest -q tests/unit/test_m7d2_el_sweep_adapter.py`

Expected: FAIL during collection because `mechcad_harness.yagi_el_sweep` does not exist.

- [ ] **Step 3: Implement the minimal adapter**

```python
REFERENCE_KINEMATIC_FIXTURE_ONLY = "REFERENCE_KINEMATIC_FIXTURE_ONLY"


class YagiELSweepReference(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_layout_hash: str = Field(min_length=1)
    el_reference_hash: str = Field(min_length=1)
    axis: RevoluteAxis
    axis_reference_status: Literal["REFERENCE_KINEMATIC_FIXTURE_ONLY"] = REFERENCE_KINEMATIC_FIXTURE_ONLY
    sample_angles_deg: tuple[float, ...] = Field(min_length=1)
    moving_instance_ids: tuple[str, ...] = Field(min_length=1)
    stationary_instance_ids: tuple[str, ...] = Field(min_length=1)
    reference_hash: str = "pending"


def create_yagi_el_sweep_request(layout, el_reference, *, axis, sample_angles_deg, moving_instance_ids, stationary_instance_ids):
    if el_reference.source_layout_hash != layout.authority_hash:
        raise ValueError("EL reference layout hash mismatch")
    if el_reference.selected_axis_height_mm is not None or el_reference.reference_status != EL_AXIS_HEIGHT_PARAMETRIC:
        raise ValueError("EL reference must remain parametric")
    return CadKinematicSweepRequest(
        source_assembly_id=layout.layout_id,
        source_assembly_hash=layout.authority_hash,
        axis=axis,
        sample_angles_deg=sample_angles_deg,
        moving_instance_ids=moving_instance_ids,
        stationary_instance_ids=stationary_instance_ids,
    )
```

Compute `YagiELSweepReference.reference_hash` using the canonical SHA-256 JSON pattern from `YagiELKinematicReference`, and expose an adapter factory if test visibility is required. Do not choose an EL height or axis origin.

- [ ] **Step 4: Run adapter tests to verify they pass**

Run: `py -m pytest -q tests/unit/test_m7d2_el_sweep_adapter.py`

Expected: PASS.

### Task 2: Add the Live EL Sweep Fixture

**Files:**
- Create: `tests/integration/test_m7d2_el_kinematic_sweep_live.py`

**Interfaces:**
- Consumes: the M7D-2 adapter, `CadKinematicSweepService`, `TransientAssemblyAnalysisService`, and `FreeCADTransientAssemblyMeasurementProvider`.
- Produces: a live regression test proving EL adapter flow uses temporary exact measurements only.

- [ ] **Step 1: Write the failing live fixture test**

```python
def test_live_yagi_el_sweep_uses_transient_freecad_measurement_without_canonical_side_effects(monkeypatch):
    monkeypatch.setattr(mechcad_harness.artifacts.storage, "ArtifactStore", _forbidden)
    layout = _layout()
    reference = create_yagi_el_reference(layout)
    request = create_yagi_el_sweep_request(
        layout, reference, axis=_axis(), sample_angles_deg=(0, 90, 180),
        moving_instance_ids=("moving",), stationary_instance_ids=("stationary",),
    )
    assembly = _reference_solids_assembly_matching_request(request)
    result = _service().execute(request, assembly)

    assert [sample.angle_deg for sample in result.samples] == [0, 90, 180]
    assert [sample.classification for sample in result.samples] == [
        CollisionClassification.POSITIVE_CLEARANCE,
        CollisionClassification.TOUCHING,
        CollisionClassification.INTERFERENCE,
    ]
    assert result.aggregate_classification is SweepAggregateClassification.COLLISION_PRESENT
    assert result.continuous_sweep_verified is False
```

- [ ] **Step 2: Run the live fixture to verify it fails**

Run: `$env:MECHCAD_FREECADCMD = 'C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe'; py -m pytest -q tests/integration/test_m7d2_el_kinematic_sweep_live.py`

Expected: FAIL because the adapter does not yet expose the required fixture-facing request identity or fixture setup is incomplete.

- [ ] **Step 3: Complete only fixture wiring needed for the live test**

Choose reference-solid placements around the caller-supplied axis such that the transformed moving 10 mm cube produces a positive exact separation at 0 degrees, face touching at 90 degrees, and positive intersection volume at 180 degrees. Keep all fixture geometry in the test; do not add production geometry code.

- [ ] **Step 4: Verify exact results and provenance**

Assert transformed hashes equal `assembly_hash(transformed_assembly_program(...))`, pairs retain request order, the result hash is deterministic on replay, touching volume/distance are zero within tolerance, interference volume is positive, and the `ArtifactStore` patch remains unused.

- [ ] **Step 5: Run the live fixture to verify it passes**

Run: `$env:MECHCAD_FREECADCMD = 'C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe'; py -m pytest -q tests/integration/test_m7d2_el_kinematic_sweep_live.py`

Expected: PASS.

### Task 3: Verify M7D-2 and Regressions

**Files:**
- Verify only: `src/mechcad_harness/kinematic_sweep.py`
- Verify only: `src/mechcad_harness/transient_assembly_analysis.py`
- Verify only: `src/mechcad_harness/transient_freecad_measurement.py`

**Interfaces:**
- Consumes: completed M7D-2 adapter and fixture tests.
- Produces: verification evidence that generic M7C-1 and M7D-1 layers remain intact.

- [ ] **Step 1: Run M7D-2 unit tests**

Run: `py -m pytest -q tests/unit/test_m7d2*`

Expected: PASS.

- [ ] **Step 2: Run M7D-1, M7C-1, and generic sweep regressions**

Run: `py -m pytest -q tests/unit/test_m7d1* tests/unit/test_m7c1* tests/unit/test_kinematic_sweep.py`

Expected: PASS.

- [ ] **Step 3: Run all tests with FreeCADCmd configured**

Run: `$env:MECHCAD_FREECADCMD = 'C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe'; py -m pytest -q`

Expected: PASS, with only pre-existing environment-dependent skips.

- [ ] **Step 4: Compile source and tests**

Run: `py -m compileall -q src tests`

Expected: exit code 0 with no output.

- [ ] **Step 5: Validate diff whitespace**

Run: `git diff --check`

Expected: no whitespace errors; preserve unrelated pre-existing changes.

- [ ] **Step 6: Report verified completion without repository mutation**

Report all test and validation outputs. Do not commit, push, stash, reset, or clean.
