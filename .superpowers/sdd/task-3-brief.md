### Task 3: Implement Pure Motor, Spur, Load, And Shaft Calculations

**Files:**
- Create: `src/mechcad_harness/revolute_drive/calculations.py`
- Modify: `src/mechcad_harness/revolute_drive/__init__.py`
- Test: `tests/unit/test_m12_motor_admissibility.py`
- Test: `tests/unit/test_m12_spur_drive_sizing.py`
- Test: `tests/unit/test_m12_shaft_sizing.py`

**Interfaces:**
- Produces pure functions `evaluate_motor_checks(...)`, `evaluate_spur_pair(...)`, `calculate_spur_loads(...)`, and `calculate_shaft_static_sizing(...)`.
- `evaluate_spur_pair` calls `engineering.spur.calculate_nominal_spur`, uses explicit driver/driven snapshots, and returns ratio, pitch geometry, scalar output-speed compatibility, and optional efficiency-bound output torque.
- `calculate_spur_loads` uses `T_design_out` and `d_driven`: `T_driven_mm=1000*T_design_out`, `Ft=2*T_driven_mm/d_driven`, `Fr=Ft*tan(phi*pi/180)`.
- `calculate_shaft_static_sizing` uses two supports and one load plane, `RA=-F*(L-a)/L`, `RB=-F*a/L`, `Mmax=sqrt(My^2+Mz^2)`, circular stress equations, `sigma_allow=Sy/n`, and `d_min=(C/sigma_allow)^(1/3)` with `C` in `N*mm`.

- [ ] **Step 1: Write independent analytical tests**

  Use hand-coded oracle equations in tests, not production functions. Cover direct motor satisfied/torque violation/speed violation/voltage mismatch/missing continuous torque/no peak substitution; spur 20/100 teeth and explicit efficiency; incompatible module/pressure angle/type; driven-side force units and invalid inputs; shaft reactions/equilibrium, maximum bending, bending/torsional/von-Mises stress, `d_min`, and `0.99*d_min`, `d_min`, `1.01*d_min` boundaries.

- [ ] **Step 2: Run focused tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_motor_admissibility.py tests/unit/test_m12_spur_drive_sizing.py tests/unit/test_m12_shaft_sizing.py -q`

  Expected: FAIL because calculation functions are absent.

- [ ] **Step 3: Implement pure calculations**

  Return per-check results with exact consumed requirement/property bindings. Treat missing or unavailable properties as `UNRESOLVED`; treat valid inadequate values as `VIOLATED`; raise only for malformed schemas or operational programming failures. Do not apply efficiency to driven-side design-load gear forces a second time. Use stress comparison `sigma_vm <= sigma_allow + max(1e-9, 1e-12*sigma_allow)`.

- [ ] **Step 4: Run focused tests to confirm pass**

  Run: `py -3 -m pytest tests/unit/test_m12_motor_admissibility.py tests/unit/test_m12_spur_drive_sizing.py tests/unit/test_m12_shaft_sizing.py -q`

  Expected: PASS with independent numerical oracles.

