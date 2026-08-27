### Task 2: Add Frozen M12-3 Models And Provenance Bindings

**Files:**
- Create: `src/mechcad_harness/revolute_drive/models.py`
- Create: `src/mechcad_harness/revolute_drive/__init__.py`
- Test: `tests/unit/test_m12_revolute_drive_models.py`

**Interfaces:**
- Produces enums `DriveArchitecture`, `EngineeringCheckStatus`, `DriveAdmissibility`, `InputProvenanceKind`.
- Produces frozen models `SourceBoundScalar`, `ConsumedPropertyBinding`, `StaticOutputShaftDesignLoadCase`, `RevoluteDriveEngineeringRequirements`, `RevoluteDriveTemplateInput`, `ShaftSupportGeometry`, `RevoluteDriveConstructionOutcome`, `EngineeringCheck`, and `RevoluteDriveAdmissibilityResult`.
- Every dimensional model validates exact units, finite values, positive domains, and rejects NaN/Inf. Every durable result uses canonical JSON hashing and excludes its own `result_hash` from the hash payload.

- [ ] **Step 1: Write failing model tests**

  Cover frozen/extra-forbid behavior, scalar speed contract, source versus policy provenance, valid/invalid efficiency, safety factor, load case, support ordering, and hash determinism. Assert `RevoluteDriveConstructionOutcome(candidate=None, status=UNRESOLVED)` is valid for incomplete construction.

- [ ] **Step 2: Run model tests to confirm failure**

  Run: `py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py -q`

  Expected: FAIL because the package/models are absent.

- [ ] **Step 3: Implement minimal immutable schemas**

  Reuse `mechcad_harness.models.common.Model` and `state.hashing.canonical_json`. Represent requirements as explicit source-bound fields and policy assumptions as explicit `SourceBoundScalar` values with `InputProvenanceKind.POLICY_ASSUMPTION`; never coerce missing values to zero. Keep derived values, checks, and unresolved reasons separate.

- [ ] **Step 4: Run model tests to confirm pass**

  Run: `py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py -q`

  Expected: PASS.

