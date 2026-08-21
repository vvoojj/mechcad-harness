# M7D-1 EL Kinematic Architecture Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a strict, parametric Yagi elevation-axis reference boundary and convert existing Yagi reference transforms into a generic discrete kinematic sweep request.

**Architecture:** Preserve `RevoluteAxis`, `CadRigidTransform`, quaternion rotation, and `CadKinematicSweepService` unchanged. Add `yagi_el_reference.py` as a strict Yagi-only adapter that creates a parametric EL reference and an explicit generic `CadKinematicSweepRequest`; it does not create geometry or mechanical embodiment.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing MechCAD canonical SHA-256 JSON hashing.

## Global Constraints

- Preserve Python 3.11+, Pydantic v2, and UTC-aware datetime requirements.
- Do not modify the `RevoluteAxis` API, quaternion handling, `CadRigidTransform`, or generic `CadKinematicSweepService`.
- Do not add AZ/EL chains, mechanical geometry, rotator selection, motors, gears, bearings, brackets, risers, materials, loads, wind, FEA, manufacturing, `DesignState` mutation, or `ChangeSet` creation.
- `YagiELKinematicReference.el_axis_height_range_mm` is exactly `(180.0, 300.0)`.
- `YagiELKinematicReference.selected_axis_height_mm` is always `None`.
- `continuous_sweep_verified` remains `False` because only discrete samples are supported.
- Do not commit, push, stash, reset, clean, or modify unrelated dirty files.

---

### Task 1: Define the Strict EL Reference Contract

**Files:**
- Create: `tests/unit/test_m7d1_el_reference.py`
- Create: `src/mechcad_harness/yagi_el_reference.py`

**Interfaces:**
- Consumes: `YagiCollisionLayoutSpec` from `mechcad_harness.yagi_collision_layout` and `RevoluteAxis` from `mechcad_harness.kinematic_sweep`.
- Produces: `YagiELKinematicReference`, `EL_AXIS_HEIGHT_PARAMETRIC`, `YAGI_EL_REFERENCE_ADAPTER_VERSION`, and `create_yagi_el_reference(layout: YagiCollisionLayoutSpec) -> YagiELKinematicReference`.

- [ ] **Step 1: Write the failing model tests**

```python
import pytest
from pydantic import ValidationError

from mechcad_harness.yagi_el_reference import (
    EL_AXIS_HEIGHT_PARAMETRIC,
    YagiELKinematicReference,
    create_yagi_el_reference,
)


def test_yagi_el_reference_is_strict_parametric_and_hashes_deterministically():
    reference = create_yagi_el_reference(_layout())

    assert reference.el_axis_height_range_mm == (180.0, 300.0)
    assert reference.selected_axis_height_mm is None
    assert reference.reference_status == EL_AXIS_HEIGHT_PARAMETRIC
    assert reference.reference_hash == create_yagi_el_reference(_layout()).reference_hash
    assert create_yagi_el_reference(_layout().model_copy(update={"authority_hash": "sha256:changed"})).reference_hash != reference.reference_hash


def test_yagi_el_reference_rejects_extras_and_selected_height():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        YagiELKinematicReference(source_layout_hash="sha256:layout", motor_position_mm=1)
    with pytest.raises(ValueError, match="selected"):
        YagiELKinematicReference(source_layout_hash="sha256:layout", selected_axis_height_mm=180)
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -m pytest -q tests/unit/test_m7d1_el_reference.py`

Expected: FAIL during collection because `mechcad_harness.yagi_el_reference` does not exist.

- [ ] **Step 3: Write the minimal strict model and factory**

```python
EL_AXIS_HEIGHT_PARAMETRIC = "EL_AXIS_HEIGHT_PARAMETRIC"
YAGI_EL_REFERENCE_ADAPTER_VERSION = "yagi-el-reference-adapter@1.0"


class YagiELKinematicReference(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_layout_hash: str = Field(min_length=1)
    el_axis_height_range_mm: Literal[(180.0, 300.0)] = (180.0, 300.0)
    selected_axis_height_mm: None = None
    reference_status: Literal["EL_AXIS_HEIGHT_PARAMETRIC"] = EL_AXIS_HEIGHT_PARAMETRIC
    adapter_version: Literal["yagi-el-reference-adapter@1.0"] = YAGI_EL_REFERENCE_ADAPTER_VERSION
    reference_hash: str = "pending"

    @model_validator(mode="after")
    def validate_reference_hash(self):
        payload = self.model_dump(mode="json", exclude={"reference_hash"})
        expected = f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()}"
        if self.reference_hash == "pending":
            object.__setattr__(self, "reference_hash", expected)
        elif self.reference_hash != expected:
            raise ValueError("reference hash does not match canonical reference")
        return self


def create_yagi_el_reference(layout: YagiCollisionLayoutSpec) -> YagiELKinematicReference:
    return YagiELKinematicReference(source_layout_hash=layout.authority_hash)
```

- [ ] **Step 4: Complete required validation coverage**

Add assertions that the model has no motor, gearbox, bearing, bracket, riser, load, wind, material, manufacturing, or structural fields. In the same test module, instantiate an invalid generic `RevoluteAxis` with zero direction and assert its existing non-zero validation error; this confirms the helper will not weaken generic axis validation.

- [ ] **Step 5: Run the model tests to verify they pass**

Run: `py -m pytest -q tests/unit/test_m7d1_el_reference.py`

Expected: PASS.

### Task 2: Create the Reference-to-Generic Sweep Request Helper

**Files:**
- Create: `tests/unit/test_m7d1_el_sweep_reference.py`
- Modify: `src/mechcad_harness/yagi_el_reference.py`

**Interfaces:**
- Consumes: `create_yagi_kinematic_reference(layout) -> YagiKinematicReferenceModel`, `create_yagi_el_reference(layout) -> YagiELKinematicReference`, `RevoluteAxis`, and `CadKinematicSweepRequest`.
- Produces: `create_yagi_el_sweep_reference(layout: YagiCollisionLayoutSpec, axis: RevoluteAxis, sample_angles_deg: tuple[float, ...], moving_instance_ids: tuple[str, ...], stationary_instance_ids: tuple[str, ...]) -> CadKinematicSweepRequest`.

- [ ] **Step 1: Write the failing end-to-end helper test**

```python
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.yagi_el_reference import create_yagi_el_sweep_reference


def test_yagi_el_sweep_reference_preserves_layout_identity_axis_angles_and_instance_roles():
    layout = _layout()
    axis = RevoluteAxis(
        origin_x_mm=0,
        origin_y_mm=0,
        origin_z_mm=0,
        direction_x=0,
        direction_y=1,
        direction_z=0,
        frame_id="yagi_el_reference",
    )

    request = create_yagi_el_sweep_reference(
        layout,
        axis=axis,
        sample_angles_deg=(-45, 0, 45, 90, 180, 360),
        moving_instance_ids=("ANTENNA_ENVELOPE_0400",),
        stationary_instance_ids=("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )

    assert request.source_assembly_hash == layout.authority_hash
    assert request.axis == axis
    assert request.sample_angles_deg == (-45.0, 0.0, 45.0, 90.0, 180.0, 360.0)
    assert request.moving_instance_ids == ("ANTENNA_ENVELOPE_0400",)
    assert request.stationary_instance_ids == ("ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200")
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -m pytest -q tests/unit/test_m7d1_el_sweep_reference.py`

Expected: FAIL during collection because `create_yagi_el_sweep_reference` is not defined.

- [ ] **Step 3: Implement the smallest helper that preserves generic boundaries**

```python
def create_yagi_el_sweep_reference(
    layout: YagiCollisionLayoutSpec,
    *,
    axis: RevoluteAxis,
    sample_angles_deg: tuple[float, ...],
    moving_instance_ids: tuple[str, ...],
    stationary_instance_ids: tuple[str, ...],
) -> CadKinematicSweepRequest:
    create_yagi_kinematic_reference(layout)
    create_yagi_el_reference(layout)
    return CadKinematicSweepRequest(
        source_assembly_id=layout.layout_id,
        source_assembly_hash=layout.authority_hash,
        axis=axis,
        sample_angles_deg=sample_angles_deg,
        moving_instance_ids=moving_instance_ids,
        stationary_instance_ids=stationary_instance_ids,
    )
```

The helper must accept an axis rather than derive a final axis height; constructing the generic axis is the caller's explicit reference decision. Do not modify generic sweep code.

- [ ] **Step 4: Add discrete-only result coverage**

Use `CadKinematicSweepResult.from_samples` with the request and existing test sample construction to assert `continuous_sweep_verified is False`. This proves the helper does not alter the generic discrete-only result guarantee.

- [ ] **Step 5: Run both M7D-1 test modules**

Run: `py -m pytest -q tests/unit/test_m7d1_el_reference.py tests/unit/test_m7d1_el_sweep_reference.py`

Expected: PASS.

### Task 3: Regression and Completion Verification

**Files:**
- Verify only: `src/mechcad_harness/kinematic_sweep.py`
- Verify only: `src/mechcad_harness/yagi_kinematic_reference.py`
- Verify only: `tests/unit/test_kinematic_sweep.py`
- Verify only: `tests/unit/test_yagi_kinematic_reference.py`

**Interfaces:**
- Consumes: completed M7D-1 adapter and helper.
- Produces: verified M7D-1 implementation without generic kinematic regressions.

- [ ] **Step 1: Run focused M7D-1 and M7C-1/Yagi regression tests**

Run: `py -m pytest -q tests/unit/test_m7d1_el_reference.py tests/unit/test_m7d1_el_sweep_reference.py tests/unit/test_kinematic_sweep.py tests/unit/test_yagi_kinematic_reference.py`

Expected: PASS.

- [ ] **Step 2: Run the full test suite**

Run: `py -m pytest -q`

Expected: PASS, with existing environment-dependent skips permitted.

- [ ] **Step 3: Compile source and tests**

Run: `py -m compileall -q src tests`

Expected: exit code 0 with no output.

- [ ] **Step 4: Validate whitespace and inspect scope**

Run: `git diff --check`

Expected: no whitespace errors. Preserve all pre-existing unrelated worktree changes.

- [ ] **Step 5: Report verified completion without committing**

Report the focused/full test result, compile result, and diff-check result. Do not commit, push, stash, reset, or clean.
