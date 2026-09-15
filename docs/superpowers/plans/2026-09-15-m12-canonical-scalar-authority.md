# M12 Canonical Scalar Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a verified typed-canonical output-speed projection and M12-local rpm lowering without changing canonical or accepted raw M12 wire semantics.

**Architecture:** A pure engineering projector validates an ID-addressed authoritative parameter against the source state and emits canonical `rad/s` projection facts. An additive M12 projected scalar embeds those facts and the explicit rpm normalization, while the existing raw source path and rpm calculations remain intact.

**Tech Stack:** Python 3.11+, Pydantic v2, existing canonical JSON SHA-256, pytest.

## Global Constraints

- Do not modify canonical state models, state hashing, canonical JSON, constraint-resolution admission, candidate-source wire models, raw M12 scalar/binding wire models, or M12 calculations.
- `DesignState` is canonical; projections and lowered scalars are noncanonical and are never independently persisted.
- The projector is pure over supplied state and has no `StateManager` dependency.
- Initial semantic support is only output angular speed in canonical `rad/s`.
- Do not add a generic unit framework, projection registry, public application projector API, parallel requirements hash, or second projected-binding collection.
- Do not commit, push, update the capability inventory, or run live FreeCAD acceptance without separate authorization.

---

## File Map

- Create `src/mechcad_harness/engineering/scalar_projection.py`: immutable locator/projection models, complete-record hash, pure typed projection and verification.
- Create `src/mechcad_harness/revolute_drive/lowering.py`: exact output-speed rad/s-to-rpm lowering and projected binding construction.
- Modify `src/mechcad_harness/engineering/__init__.py`: export new engineering projection contracts only.
- Modify `src/mechcad_harness/revolute_drive/models.py`: additive projected scalar and output-speed structural union only.
- Modify `src/mechcad_harness/revolute_drive/service.py`: separate projected verifier branch while retaining raw logic.
- Do not modify `src/mechcad_harness/application.py`: its existing M12 entrypoint already loads and passes the exact source state; the M12 service calls the pure projector directly.
- Add focused tests under `tests/unit/` and `tests/integration/`; add a static legacy raw JSON fixture under `tests/fixtures/`.
- Protected expected-no-change integration surface: `tests/integration/test_constraint_resolution_canonical_admission.py`; run it as a regression gate only.

### Task 1: Characterize the Raw Baseline

**Files:** Test: `tests/unit/test_m12_revolute_drive_models.py`, `tests/integration/test_m12_revolute_drive_production.py`

- [ ] Write assertions that the current representative raw requirements dump has only raw output-speed fields and that the current raw production test still rejects a composite source record.
- [ ] Run the focused selectors before implementation; record only the command and result in the implementation evidence, not in this plan.
- [ ] Stop if raw output-speed serialization or composite rejection differs from this specification.

### Task 2: Freeze a Static Legacy Golden

**Files:** Create `tests/fixtures/m12_raw_requirements_legacy.json`; Test: `tests/unit/test_m12_revolute_drive_models.py`

- [ ] Before changing M12 models, serialize one valid representative raw requirements object with its already-computed `requirements_hash` and raw trusted-binding hashes into the fixture as literal JSON.
- [ ] Write a failing regression that validates the literal fixture and asserts exact JSON-mode dump and exact stored hash equality:

```python
payload = json.loads(LEGACY_FIXTURE.read_text(encoding="utf-8"))
parsed = RevoluteDriveEngineeringRequirements.model_validate(payload)
assert parsed.model_dump(mode="json") == payload
assert parsed.requirements_hash == payload["requirements_hash"]
```

- [ ] Verify the test passes before model extension; stop if the fixture is generated during the test.

### Task 3: Add Pure Locator and Projection Models

**Files:** Create `src/mechcad_harness/engineering/scalar_projection.py`; Test: `tests/unit/test_canonical_scalar_projection.py`

**Produces:** `AuthoritativeParameterLocator`, `CanonicalScalarProjection`, complete-parameter hash helper.

- [ ] Write failing tests for valid exact-state/ID resolution, missing ID, duplicate IDs, wrong project, wrong revision, wrong state hash, and changed full parameter payload.
- [ ] Implement frozen, extra-forbidden models and a pure function equivalent to:

```python
def project_authoritative_scalar(project_id, source_state, locator):
    # verify project/revision/state hash; find one ID; hash full parameter;
    # delegate typed semantic projection; return a validated projection
```

- [ ] Hash `parameter.model_dump(mode="json")` with `state.hashing.canonical_json`; do not introduce a serializer or state-store dependency.
- [ ] Run the projection unit module. Stop if any canonical model needs a new serialized field.

### Task 4: Add the Single Typed Semantic Rule

**Files:** Modify `src/mechcad_harness/engineering/scalar_projection.py`; Test: `tests/unit/test_canonical_scalar_projection.py`

- [ ] Write failing tests that `OutputAngularSpeedValue(value_rad_s=x)` projects to `x`, `rad/s`, and `authoritative-output-angular-speed-rad-s@1`.
- [ ] Write failing tests that motor, interface, packaging, azimuth, and Yagi typed values fail closed.
- [ ] Implement a pure engineering-value-layer `isinstance(OutputAngularSpeedValue)` rule. Do not create a registry or add a method to serialized canonical value models.
- [ ] Run the focused module. Stop if the generic resolver needs to infer a scalar from a composite value.

### Task 5: Projection Tamper Coverage

**Files:** Test: `tests/unit/test_canonical_scalar_projection.py`

- [ ] Add failing cases for wrong key, scalar value, unit, rule ID, projection hash, and full parameter hash.
- [ ] Implement deterministic projection-hash validation over all projection fields except `projection_hash`.
- [ ] Run the unit module. Stop if a tampered projection can validate without recomputation against supplied state.

### Task 6: Add the Additive M12 Projected Scalar

**Files:** Modify `src/mechcad_harness/revolute_drive/models.py`; Test: `tests/unit/test_m12_revolute_drive_models.py`

**Produces:** `ProjectedSourceBoundScalar` and `SourceBoundScalar | ProjectedSourceBoundScalar` for `required_output_speed`.

- [ ] Write failing tests that the projected type exposes `.value` and `.unit == "rpm"`, has no `source_path`, carries `canonical_projection` without implying trust, and rejects nonfinite values, wrong units, bad normalized hashes, and bad binding hashes.
- [ ] Implement the frozen projected type with `value`, `unit`, `canonical_projection`, normalization rule ID, normalized value hash, and binding hash only. A deserialized embedded projection remains a claim until the production verifier recomputes and compares it.
- [ ] Extend only `required_output_speed` with the structural union; leave raw field/default/schema output untouched.
- [ ] Re-run the static legacy golden and raw model tests. Stop if any raw dump or raw requirements hash changes.

### Task 7: Implement M12-Local Lowering

**Files:** Create `src/mechcad_harness/revolute_drive/lowering.py`; Test: `tests/unit/test_m12_projected_output_speed.py`

- [ ] Write failing tests for a valid output-speed projection, wrong key/unit/rule, and exact conversion.
- [ ] Implement a pure lowering function equivalent to:

```python
def lower_projected_output_speed(projection):
    rpm = projection.value * 60.0 / (2.0 * math.pi)
    return ProjectedSourceBoundScalar(
        value=rpm,
        unit="rpm",
        canonical_projection=projection,
        normalization_rule_id="m12-output-angular-speed-rad-s-to-rpm@1",
    )
```

- [ ] Treat lowering as deterministic construction only; it grants no trust to caller-supplied projections. Require exact binary64 equality during projected binding validation; add no rounding or tolerance.
- [ ] Run the lowering module. Stop if calculation code must accept rad/s.

### Task 8: Lock the Raw Verifier

**Files:** Modify `src/mechcad_harness/revolute_drive/service.py`; Test: existing raw M12 service/production tests

- [ ] Add raw-path regression selectors before editing the verifier.
- [ ] Refactor only enough to dispatch on scalar type; preserve the raw `SourceBoundScalar` branch's path, reference, raw trusted binding, exact-record, and hash checks.
- [ ] Verify the existing composite-record rejection remains `UNRESOLVED` through the production entrypoint.
- [ ] Stop if raw verification consults projected fields or raw accepted errors/serialization change.

### Task 9: Add the Projected Verifier Branch

**Files:** Modify `src/mechcad_harness/revolute_drive/service.py`; Test: `tests/unit/test_m12_projected_output_speed.py`

- [ ] Write failing projected cases for every locator, parameter, projection, normalization, and binding tamper listed in the spec.
- [ ] Implement a separate branch that validates collection reference, `locator.project_id == request.source_binding.project_id == trusted production project context`, locator/state identity, exactly one parameter, full hash, recomputed projection, equality with embedded `canonical_projection`, exact rpm normalization, normalized hash, and binding hash.
- [ ] Do not resolve a raw scalar path or consult `trusted_source_scalar_bindings` in this branch. The embedded projection is a claim until all recomputation checks succeed.
- [ ] Run projected and raw verifier tests. Stop if a caller-provided projected value is accepted without recomputation.

### Task 10: Validate C1 Candidate Source Binding

**Files:** Test: `tests/unit/test_m12_projected_output_speed.py`

- [ ] Write failing cases for missing `/authoritative_parameters`, wrong authority enum, and stale collection hash.
- [ ] Require the existing `CANONICAL_PARAMETER` aggregate reference and validate it against the same supplied source state.
- [ ] Do not modify `CandidateSourceBinding` or use numeric parameter indexes.
- [ ] Run focused currentness/source-binding tests. Stop if exact-member consumption cannot remain separately bound by locator/full hash.

### Task 11: Verify Through the Existing Production API

**Files:** No production application change; Modify: `src/mechcad_harness/revolute_drive/service.py`; Test: `tests/integration/test_m12_projected_canonical_output_speed.py`

- [ ] Write a failing production-composed test using `realize_and_evaluate_revolute_drive` with a projected output-speed claim and valid explicitly supplied remaining M12 inputs.
- [ ] Verify that the existing application entrypoint already loads `current_state` and passes it as `source_state`; call the pure projector directly from the M12 service using the request/source-binding project identity and embedded locator. Do not add a public application projector method, artificial application dependency injection, or `StateManager` dependency.
- [ ] Assert existing rpm motor checks execute and the candidate/evaluation outcome is admissible only after projected provenance verifies.
- [ ] Run the new integration test. Stop if the path fabricates any non-speed M12 requirement.

### Task 12: Exercise Real Canonical Admission Output

**Files:** Test: `tests/integration/test_m12_projected_canonical_output_speed.py` only. Regression gate, do not modify: `tests/integration/test_constraint_resolution_canonical_admission.py`

- [ ] Write a failing integration scenario that materializes and admits output-speed resolution through `ProductionApplication.admit_constraint_resolution_batch`, then uses its actual parameter ID in the projection locator.
- [ ] Reuse the accepted admission path without editing it; bind `/authoritative_parameters` as `CANONICAL_PARAMETER` and feed the projected output speed into the existing M12 entrypoint.
- [ ] Assert rad/s projection, rpm lowering, requirements hash inclusion, unchanged rpm calculation consumption, and service-side recomputation rather than caller-claim trust.
- [ ] Run the new M12 integration scenario and separately run `tests/integration/test_constraint_resolution_canonical_admission.py` unchanged as a regression gate. Stop if admission requires an M12-specific field or API change.

### Task 13: Run Predecessor and Static Gates

**Files:** No production changes; Test: existing M12/candidate suites

- [ ] Run existing revolute model, provenance, service, raw production, candidate integrity/currentness, affected candidate CAD/M10 predecessor tests, and unchanged `tests/integration/test_constraint_resolution_canonical_admission.py`.
- [ ] Run `python -m compileall -q src` and `git diff --check`.
- [ ] Do not run M12-6 live FreeCAD acceptance without explicit authorization. Record exact commands/results only in later implementation evidence.

### Task 14: Independent Acceptance Handoff

**Files:** Later authorized audit/evidence artifacts only; no capability-inventory update in implementation before acceptance.

- [ ] Prepare an audit handoff identifying the new projected path, static raw compatibility golden, production-composed positive scenario, negative matrix, and predecessor gate results.
- [ ] Require independent review to distinguish new unit/integration proof from M12-6's existing raw fixture proof.
- [ ] Update `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md` only after implementation, production wiring, fresh verification, and appropriate acceptance evidence are complete.
- [ ] Stop if acceptance would require rewriting M12-6 historical evidence or changing protected canonical/raw wire semantics.

## Plan Self-Review

- Canonical state and admission are expected-no-change surfaces in every task.
- Raw scalar, trusted binding, and candidate source-reference serialization are protected by a static golden and predecessor tests.
- The only unit conversion is M12-local lowering; calculations remain rpm-only.
- The new projector receives supplied state and no state repository dependency.
- The plan creates no second projected binding collection, public generic projector API, registry, unit framework, or automatic full-requirements builder.
- `canonical_projection` is a caller claim until service-side recomputation; lowering alone grants no trust.
- `application.py` and `tests/integration/test_constraint_resolution_canonical_admission.py` are expected-no-change/protected surfaces.
