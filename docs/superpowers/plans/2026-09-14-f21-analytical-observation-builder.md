# F21 Analytical Observation Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate only the duplicated application-level analytical-observation construction by adding one private, pure tuple builder while preserving every caller-owned trust and Evidence behavior.

**Architecture:** The existing `ProductionApplication` remains the narrow boundary for the extraction. The new private method will receive only already-trusted `request`, `definition`, `realization`, and `region_map`; it will call the two existing canonical constructors in their current order and return their immutable observations. Both callers retain all preconditions, exception boundaries, validation, currentness, and publication responsibilities.

**Tech Stack:** Python 3.11+, Pydantic v2 frozen models, pytest, existing structural Evidence/ArtifactStore services.

## Global Constraints

- Design authority: `docs/superpowers/specs/2026-09-14-f21-analytical-observation-builder-design.md`.
- Required starting HEAD: `8e8aa3e9bcacde9cead9fcb53a8027c2df324ceb`.
- Preserve every pre-existing modified or untracked worktree path; do not stage, edit, remove, or revert unrelated work.
- Do not modify `docs/audit/**` or `docs/reconstruction/**`.
- Do not begin F13, F16, or F19 work.
- Do not implement broad `application.py` cleanup, structural-provenance consolidation, artifact-verifier consolidation, M11 handoff consolidation, Evidence redesign, public APIs, persistence, models/schemas, hash algorithms, or F10/F12 changes.
- M11-4/M11-5 external CAD/solver execution is separately authorized and is not automatically run for F21.
- Do not push. Do not commit unless separately authorized.

---

## 1. Baseline and Worktree Safety Gate

Run these commands before reading or changing an implementation file:

```powershell
git rev-parse HEAD
git status --short
```

Expected HEAD:

```text
8e8aa3e9bcacde9cead9fcb53a8027c2df324ceb
```

- [ ] Record the complete `git status --short` output before any F21 edit.
- [ ] If `HEAD` is not the required commit, stop without modifying implementation or tests and report exactly `F21_PLAN_BLOCKED_BY_BASELINE_MISMATCH`.
- [ ] Treat every pre-existing modified/untracked path as protected unrelated work, including all pre-existing audit, plan, spec, project, test, coverage, and `.superpowers` paths.
- [ ] After every F21 step, compare `git status --short` with the recorded status; only the planned F21 files may be additionally changed.

## 2. Required Pre-Change Census and Design-Drift Gate

**Files to read, not modify in this task:**

- `src/mechcad_harness/application.py`
- `src/mechcad_harness/structural/validation.py`
- `src/mechcad_harness/structural/evidence_service.py`
- `src/mechcad_harness/structural/evidence.py`
- `src/mechcad_harness/structural/evidence_models.py`
- `tests/unit/test_production_application.py`
- `tests/unit/test_structural_validation_observations.py`
- `tests/unit/test_structural_evidence_models.py`
- `tests/unit/test_structural_evidence_verifier.py`
- `tests/unit/test_structural_results.py`
- `tests/integration/test_m11_4_live_structural.py` (read-only coverage census; do not run without authorization)

- [ ] Locate `ProductionApplication._publish_structural_analytical_validation` semantically and record its two direct constructor calls, positional arguments, geometry-then-material order, enclosing `try`/`except Exception as exc`, pre-construction mesh/STEP/dependency checks, validator invocation, three-value return, and delegated `StructuralEvidencePublisher` publication ownership.
- [ ] Locate `ProductionApplication.evaluate_structural_analytical_validation` semantically and record its two direct constructor calls, positional arguments, geometry-then-material order, enclosing `try`/`except Exception as exc`, durable-manifest reload/equality, definition reload, dependency/result/mesh/STEP/provenance checks, source-currentness assertion, validation-only return, and disregard for caller-supplied observation snapshots.
- [ ] Read `cantilever_geometry_observation` and `cantilever_material_observation`; record every produced field, constructor default/nullable field behavior, definition-hash validation, geometry-derived dimensions, `free` region lookup, and canonical material snapshot lookup.
- [ ] Read `StructuralEvidencePublisher.publish`, `StructuralEvidencePayload`, and `reconstruct_analytical_validation` / `StructuralEvidenceVerifier._verify_analytical_validation`; record the Path A persistence, semantic-hash, output-hash, and runtime-independent historical reconstruction behavior.
- [ ] Search all test references to both application methods and both constructors. Confirm the listed test modules remain the exact focused coverage set; add an existing module only if the census finds a direct observation-path assertion there.
- [ ] Stop without adapting the change if either path differs from the approved design in observation type, constructor inputs, call order, defaults, error boundary, or caller-specific fields. Report exactly `F21_PLAN_BLOCKED_BY_DESIGN_DRIFT`.

## 3. Characterize Observable Behavior Before Extraction

**Files:**

- Modify: `tests/unit/test_production_application.py`
- Modify only if the current fixtures make the comparisons impossible to express there: `tests/unit/test_structural_validation_observations.py`
- Read: `tests/unit/test_structural_evidence_models.py`
- Read: `tests/unit/test_structural_evidence_verifier.py`
- Read: `tests/unit/test_structural_results.py`

**Consumes:** Current direct constructor sequences in both `ProductionApplication` methods and existing structural application test fixtures.

**Produces:** Tests that freeze current behavior without naming or invoking the future private helper.

- [ ] Add a fixed trusted-input fixture using the existing request, definition, realized geometry, and resolved-region fixtures. Independently construct the expected pair through the current public canonical constructors:

```python
expected_geometry = cantilever_geometry_observation(
    request, definition, realization, region_map,
)
expected_material = cantilever_material_observation(request, definition)
```

- [ ] Add Path A characterization that intercepts the validator input or returned factory tuple and asserts exact equality with `expected_geometry` and `expected_material`. Assert the observations' `model_dump(mode="json")` values, including `material_assignment_id`, `elastic_modulus_source_identity`, and `poisson_ratio_source_identity`, not only selected numeric fields.
- [ ] Add Path B characterization that intercepts the validator input and asserts exact equality with the independently constructed pair. Pass forged caller-supplied geometry/material observations and assert they do not become validator inputs or change the validation result.
- [ ] Add order characterization by monkeypatching the existing two constructor symbols with recorders that append `"geometry"` then `"material"` and return typed valid observations. Assert the recorded sequence is exactly:

```python
["geometry", "material"]
```

Run this characterization independently for both Path A and Path B. Do not assert on a private helper name.

- [ ] Add construction-failure characterization for both paths by making the geometry constructor raise a sentinel exception. Assert each caller raises exactly:

```python
ValueError("trusted analytical source observations are unavailable")
```

and assert `raised.value.__cause__ is sentinel`. Keep pre-boundary and post-boundary failure checks unchanged.

- [ ] Add a Path A fixed-fixture compatibility assertion that obtains the published `StructuralEvidencePayload` and compares its serialized observations, `semantic_hash`, and enclosing Evidence `output_hash` against values built from independently constructed canonical observations. The expected hash must be recorded from the pre-extraction fixture, not regenerated solely from the code under test.
- [ ] Add a Path B non-publication assertion using the existing EvidenceStore/application fixture: direct analytical evaluation returns validation and does not add an Evidence record.
- [ ] Run the new focused test nodes before production extraction. They should pass against the direct duplicated implementation, demonstrating they characterize existing behavior rather than an anticipated helper.

```powershell
pytest -q tests/unit/test_production_application.py tests/unit/test_structural_validation_observations.py
```

Expected: all collected tests pass; record collected, passed, skipped, failed, and any exact node IDs.

## 4. Extract the Single Private Construction Helper

**Files:**

- Modify: `src/mechcad_harness/application.py`
- Test: `tests/unit/test_production_application.py`

**Consumes:** The pre-extraction characterization tests and unchanged canonical constructor functions.

**Produces:** One private `ProductionApplication` method with this exact shape and return order:

```python
def _build_cantilever_analytical_observations(
    self,
    *,
    request: StructuralAnalysisRequest,
    definition,
    realization,
    region_map,
) -> tuple[CantileverGeometryObservation, CantileverMaterialObservation]:
    geometry_observation = cantilever_geometry_observation(
        request, definition, realization, region_map,
    )
    material_observation = cantilever_material_observation(request, definition)
    return geometry_observation, material_observation
```

- [ ] Add only the method above near the two current structural analytical-validation methods. Preserve the existing constructor imports and types; do not add a service, model, schema, public wrapper, persistence object, generic observation framework, or hash helper.
- [ ] Verify by inspection that the method has no file/artifact reads, state loads/reloads, definition lookup, geometry realization, region resolution, `free`-region selection, dimension calculation, material snapshot read, hash derivation/comparison, provenance verification, currentness decision, Evidence publication, `try`/`except`, or persistence side effect.
- [ ] Do not add error handling. Exceptions from either existing constructor must propagate to the caller's already-existing boundary unchanged.

## 5. Replace Only the Two Approved Call Sites

**Files:**

- Modify: `src/mechcad_harness/application.py`
- Test: `tests/unit/test_production_application.py`

**Consumes:** `_build_cantilever_analytical_observations` from Task 4.

**Produces:** The same observations at each approved caller with all caller-owned behavior retained.

- [ ] In `_publish_structural_analytical_validation`, replace only the adjacent direct geometry/material constructor sequence with:

```python
geometry_observation, material_observation = (
    self._build_cantilever_analytical_observations(
        request=request,
        definition=definition,
        realization=realization,
        region_map=region_map,
    )
)
```

Keep the helper invocation inside the exact existing `try` block. Retain mesh parsing, project-scoped STEP read/type/hash verification, composed dependency checks, realization, region resolution, exception translation, analytical validation, three-value return, and `StructuralEvidencePublisher` ownership of publication.

- [ ] In `evaluate_structural_analytical_validation`, replace only the adjacent direct trusted geometry/material constructor sequence with:

```python
trusted_geometry_observation, trusted_material_observation = (
    self._build_cantilever_analytical_observations(
        request=request,
        definition=definition,
        realization=realization,
        region_map=region_map,
    )
)
```

Keep the helper invocation inside the exact existing `try` block. Retain input/type checks, durable-manifest reload/equality, definition reload, dependency validation, result reconstruction/hash verification, trusted mesh load, STEP binding/reference/provenance checks, realization, region resolution, exception translation, analytical validation, source-currentness assertion, validation-only return, and the rejection/ignoring of caller-supplied observation authority.

- [ ] Verify there are exactly two calls to `_build_cantilever_analytical_observations` and no remaining duplicate application-level pair of direct observation constructor calls.

```powershell
rg -n "_build_cantilever_analytical_observations|cantilever_geometry_observation\(|cantilever_material_observation\(" src/mechcad_harness/application.py
```

Expected: one helper definition, exactly two helper call sites, and the two low-level constructor calls only inside that helper.

## 6. Hash, Serialization, and Error-Semantics Gates

**Files:**

- Modify: `tests/unit/test_production_application.py`
- Read: `tests/unit/test_structural_evidence_models.py`
- Read: `tests/unit/test_structural_evidence_verifier.py`
- Read: `tests/unit/test_structural_results.py`

- [ ] Re-run the fixed-fixture comparisons from Task 3 after extraction. Require exact equality for geometry observation serialized content, material observation serialized content, nullable field population, `StructuralEvidencePayload.semantic_hash`, enclosing Evidence `output_hash`, and `StructuralAnalyticalValidationResult.validation_hash`.
- [ ] Assert no change in the fixture's request hash, definition hash, geometry artifact hash, mesh hash, or centralized mesh-input hash behavior. Do not rewrite a golden/hash expectation to accept a different output.
- [ ] If any protected serialized content or hash differs, stop and report exactly `F21_PLAN_BLOCKED_BY_HASH_COMPATIBILITY_REGRESSION`.
- [ ] Re-run the two construction-failure tests. For each caller, require the outer `ValueError("trusted analytical source observations are unavailable")` and original sentinel exception as `__cause__`.
- [ ] Confirm errors before or after the original construction `try` boundaries remain tested by the existing source/dependency/provenance rejection tests; do not move these checks or introduce helper exception translation.

## 7. Focused Regression Gates

Run the current exact focused modules identified by the pre-change census:

```powershell
pytest -q tests/unit/test_production_application.py tests/unit/test_structural_validation_observations.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py tests/unit/test_structural_results.py
```

- [ ] Record collected, passed, skipped, failed, and all exact failing node IDs.
- [ ] Investigate only failures caused by the construction-only F21 extraction. Do not widen scope to resolve unrelated baseline failures.
- [ ] Do not run `tests/integration/test_m11_4_live_structural.py`, `tests/integration/test_m11_5_live_structural.py`, FreeCAD, Gmsh, or CalculiX unless separate explicit authorization is received.

## 8. Complete Unit, Static, and Diff Gates

- [ ] Run the complete unit suite after focused regressions:

```powershell
pytest -q tests/unit
```

Record collected, passed, skipped, failed, exact failing node IDs, and import/collection status. Compare to the accepted integrated baseline. Known unrelated baseline failures may remain only when the record shows:

```text
NEW_F21_FAILURES: NONE
IMPORT_COLLECTION_REGRESSIONS: NONE
```

- [ ] Run static compilation:

```powershell
python -m compileall -q src tests
```

- [ ] Run a scoped whitespace check for the F21 files:

```powershell
git diff --check -- src/mechcad_harness/application.py tests/unit/test_production_application.py tests/unit/test_structural_validation_observations.py
```

- [ ] Inspect the complete F21 diff with:

```powershell
git diff -- src/mechcad_harness/application.py tests/unit/test_production_application.py tests/unit/test_structural_validation_observations.py
```

Expected production scope: only the one private helper and replacement of the two approved direct constructor sequences in `application.py`. Any additional production file requires explicit scope-conflict review before editing.

## 9. Final Independent Skeptical Review

- [ ] Confirm only one private construction helper was introduced.
- [ ] Confirm the helper contains no I/O, state reload, Evidence publication, provenance verification, currentness decision, hash derivation, exception translation, or persistence.
- [ ] Confirm constructor order and inputs are unchanged.
- [ ] Confirm both callers retain independent trust boundaries.
- [ ] Confirm Path A publication semantics, Evidence ownership, three-value return, payload serialization, semantic hash, and Evidence output hash are unchanged.
- [ ] Confirm Path B direct-evaluation semantics, validation-only return, currentness assertion, and rejection/ignoring of caller-supplied observation authority are unchanged.
- [ ] Confirm structural provenance verification and artifact verification remain separate.
- [ ] Confirm M11 handoff revalidation, centralized mesh-input hashing, F10 retirement, and F12 canonical replay are unchanged.
- [ ] Confirm F13, F16, and F19 were not started.
- [ ] Confirm `docs/reconstruction/**` and `docs/audit/**` were not modified.
- [ ] Compare final `git status --short` with the baseline worktree record and confirm unrelated work was preserved.

## Plan Self-Review Record

- [x] Compared line-by-line with the approved F21 design: scope remains a construction-only tuple extraction.
- [x] Every required stop condition is executable: baseline mismatch, design drift, and hash compatibility regression each have an exact report marker.
- [x] Characterization precedes extraction and does not depend on the helper name.
- [x] The private API owns exactly two existing constructor calls and their tuple return.
- [x] Caller boundaries, Evidence/currentness behavior, error chaining, serialization/hash invariants, and protected non-goals are explicitly retained.
- [x] No implementation has been performed by creating this plan.
