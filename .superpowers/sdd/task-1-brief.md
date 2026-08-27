### Task 1: Extract Shared Nominal Spur Primitive

**Files:**
- Create: `src/mechcad_harness/engineering/spur.py`
- Modify: `src/mechcad_harness/tools/builtins.py:22-43`
- Modify: `src/mechcad_harness/engineering/__init__.py`
- Test: `tests/unit/test_spur_engineering.py`

**Interfaces:**
- Consumes existing `SpurGearInput` values: `module_mm`, `teeth_pinion`, `teeth_gear`.
- Produces `NominalSpurGeometry` with `pitch_diameter_driver_mm`, `pitch_diameter_driven_mm`, `center_distance_mm`, and `ratio_magnitude` plus `calculate_nominal_spur(module_mm, driver_teeth, driven_teeth)`.
- BuiltinTools maps the shared primitive output to its existing `SpurGearOutput` fields without changing the public ToolBroker contract.

- [ ] **Step 1: Write independent failing tests**

  Add tests that independently calculate `m*z_driver`, `m*z_driven`, `(d_driver+d_driven)/2`, and `z_driven/z_driver`; assert the shared primitive and `calc_spur_gear` expose those values. Add invalid module and tooth-count tests.

- [ ] **Step 2: Run focused tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_spur_engineering.py -q`

  Expected: FAIL because `engineering.spur` and the shared primitive do not exist.

- [ ] **Step 3: Implement the lower generic primitive**

  Use strict finite-positive validation and exact integer tooth-count validation. Keep the implementation free of `revolute_drive` imports. Update `calc_spur_gear` to call the primitive and map fields only.

- [ ] **Step 4: Run focused tests to confirm pass**

  Run: `py -3 -m pytest tests/unit/test_spur_engineering.py tests/unit/test_tools.py -q`

  Expected: PASS with existing BuiltinTools behavior unchanged.

