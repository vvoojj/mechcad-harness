# Task 1 Report: M11-4 Result Models And Hashing

## Status

DONE_WITH_CONCERNS

## Scope

Implemented only Task 1 from `.superpowers/sdd/task-1-brief.md`: immutable
M11-4 result, case/request manifest, provenance, criterion, unit, and
deterministic hashing models. No parser, service, interpreter, application, or
integration behavior was added.

## Files Changed

- `src/mechcad_harness/structural/models.py`
  - Added fixed parser identity constants and the sole `FEA_EXECUTED` result
    maturity.
  - Added immutable finite scalar result models for displacement, reactions,
    Cauchy stress tensors, stress sample identities, stress samples, explicit
    units, and parser provenance.
  - Added `StructuralCaseExecutionManifest` with paired artifact ID/hash
    validation and deterministic `case_manifest_hash`.
  - Added ordered case manifest validation through
    `StructuralRequestExecutionManifest` and optional ordered case fields on
    the existing `StructuralExecutionManifest`.
  - Added immutable `StructuralLoadCaseResult`, `StructuralAnalysisResult`,
    `StructuralCriterionResult`, and `StructuralVerificationResult` models.
  - Enforced exact case mesh-hash binding on all local result records and
    rejected duplicate stress sample identities.
  - Added `structural_case_manifest_hash`, `structural_result_hash`, and
    `structural_verification_hash`; updated execution manifest hashing to omit
    only volatile `run_id` plus each record's self-derived hash field.
- `tests/unit/test_structural_results.py`
  - Added six focused tests covering TDD identity behavior, raw FRD-byte
    binding, duplicate stress identity rejection, mesh binding, finite values,
    immutable records, ordered case IDs, explicit units, parser identities,
    maturity, and criterion reasons.
- `.superpowers/sdd/task-1-report.md`
  - Replaced the stale report at the required path with this implementation
    report.

## Design Decisions

- All new result-family models use frozen Pydantic configuration with extra
  fields forbidden.
- `StressFieldRepresentation` admits only
  `calculix_extrapolated_nodal_stress`; integration-point and generic stress
  claims are intentionally not represented.
- Every local displacement, reaction, and stress result carries a mesh hash;
  stress identities also carry the mesh hash and must match their sample and
  case hashes.
- Duplicate stress records are rejected using the complete stable identity
  (`mesh_hash`, node, optional element, and optional location). Distinct
  location identities are allowed without averaging.
- Result identity hashes use canonical sorted compact JSON, retain raw artifact
  byte hashes, remove `run_id` recursively, and exclude only the model's own
  computed hash field to avoid self-reference.
- Criterion aggregation is fail-closed: any `FAIL` dominates
  `NOT_EVALUABLE`, and an empty criterion set is `NOT_EVALUABLE`.

## TDD Evidence

1. Wrote `tests/unit/test_structural_results.py` before production model code.
2. Red command:
   `py -3 -m pytest tests/unit/test_structural_results.py -q`
   failed during collection with the expected `ImportError` because
   `FRD_RESULT_PARSER_IDENTITY` and the M11-4 model family did not yet exist.
3. Green focused command:
   `py -3 -m pytest tests/unit/test_structural_results.py -q`
   output: `6 passed in 0.44s`.

## Regression And Static Checks

- Command:
  `py -3 -m pytest tests/unit/test_structural_models.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_service.py -q`
  Output: `124 passed in 2.23s`.
- Command: `py -3 -m compileall src/mechcad_harness/structural -q`
  Output: no output; exit code 0.
- Command:
  `git diff --check -- src/mechcad_harness/structural/models.py tests/unit/test_structural_results.py`
  Output: no output.

## Concerns And Boundaries

- The full repository suite was not run because this task brief requests the
  focused model suite; the existing structural regression slice was run.
- M11-4 parsers, artifact rehashing, result interpretation, criterion
  evaluation, and production wiring remain intentionally unimplemented for
  later tasks.
- Existing unrelated dirty and untracked work was preserved. No commit,
  reset, stash, clean, checkout, revert, or discard operation was performed.

## Task 1 Review Fixes

Status: FIXED_WITH_CONCERNS

Fixed the Important findings from the Task 1 review in:

- `src/mechcad_harness/structural/models.py`
  - Optional artifact hashes now reject empty values.
  - Reaction-bearing results require a nonempty DAT artifact hash.
  - Displacement samples now reject duplicate `(mesh_hash, node_id)` identities.
  - `StructuralVerificationResult` now binds source, request, execution
    manifest, result, mesh, raw artifact hashes, parser provenance, and
    criterion identities into its deterministic hash.
  - Verification criterion IDs must be unique.
  - `StructuralRequestExecutionManifest` now derives and validates an ordered
    case-manifest identity/hash manifest hash.
  - `StructuralExecutionManifest` validates that same ordered request-manifest
    hash when case manifests are present; case hashes remain independent of the
    request manifest, avoiding an artifact-to-manifest cycle.
- `tests/unit/test_structural_results.py`
  - Added focused regressions for all five review findings and provenance hash
    changes.

## Review Fix Verification

Red command before the production fix:

```text
py -3 -m pytest tests/unit/test_structural_results.py -q
```

Output: collection failed with `ImportError` because
`structural_request_manifest_hash` did not yet exist.

Focused green command:

```text
py -3 -m pytest tests/unit/test_structural_results.py -q
```

Output:

```text
11 passed in 0.45s
```

Required structural regression command:

```text
py -3 -m pytest tests/unit/test_structural_results.py tests/unit/test_structural_models.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_service.py -q
```

Output:

```text
135 passed in 2.28s
```

Compile command:

```text
py -3 -m compileall src/mechcad_harness -q
```

Output: no output; exit code 0.

Diff check:

```text
git diff --check
```

Output: Git emitted existing LF-to-CRLF working-copy warnings. It also
reported pre-existing `new blank line at EOF` diagnostics for
`.superpowers/sdd/task-1-brief.md`, `.superpowers/sdd/task-2-brief.md`, and
`.superpowers/sdd/task-3-brief.md`. No fix files were reported.

## Remaining Concerns

- The full repository suite was not run; verification used the exact focused
  command requested for this fix.
- Existing unrelated worktree modifications and the pre-existing diff-check
  diagnostics remain unchanged.
- M11-4 parser, service, interpreter, and production wiring boundaries remain
  as described in the original report.

## Re-review Fixes

Status: FIXED

Fixed the four requested findings:

1. Optional artifact IDs in both `StructuralCaseExecutionManifest` and
   `StructuralExecutionManifest` now use `min_length=1`, rejecting an empty ID
   whenever an optional artifact reference is supplied.
2. `execution_manifest_hash` now retains `request_manifest_hash` in its
   canonical payload. It removes only recursive `run_id` values; no request
   manifest field is treated as a self-hash field.
3. `StructuralAnalysisResult` now carries `source_binding`, `definition_id`,
   and `definition_hash` alongside its existing request and execution binding
   fields. Definition identity consistency is validated, and all fields are
   included in `structural_result_hash` through the canonical model payload.
4. `StructuralExecutionManifest` now rejects any per-case mesh artifact ID or
   hash that differs from the request-level shared mesh artifact reference.

Focused regressions were added to `tests/unit/test_structural_results.py` for
all four findings.

## Re-review Fix Verification

Focused result tests:

```text
py -3 -m pytest tests/unit/test_structural_results.py -q
15 passed in 0.47s
```

Required structural regression command:

```text
py -3 -m pytest tests/unit/test_structural_results.py tests/unit/test_structural_models.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_service.py -q
139 passed in 2.29s
```

Compile command:

```text
py -3 -m compileall src/mechcad_harness -q
```

Output: no output; exit code 0.

Diff check:

```text
git diff --check -- src/mechcad_harness/structural/models.py tests/unit/test_structural_results.py
```

Output: no output; exit code 0.

## Final Task 1 Review Fixes

Status: FIXED

Closed the two remaining review findings:

1. `StructuralLoadCaseResult` now rejects duplicate reaction sample identities
   using the represented stable identity `(mesh_hash, node_id)`. No unrepresented
   DOF or sample identity is inferred.
2. `StructuralExecutionManifest` now validates each optional top-level log, FRD,
   and DAT artifact ID/hash pair and rejects empty supplied IDs or hashes.

Focused regressions were added to `tests/unit/test_structural_results.py` for
duplicate reactions, one-sided optional artifact references, and empty optional
artifact values.

## Final Review Fix Verification

Required structural regression command:

```text
py -3 -m pytest tests/unit/test_structural_results.py tests/unit/test_structural_models.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_service.py -q
152 passed in 2.27s
```

Focused result-model command:

```text
py -3 -m pytest tests/unit/test_structural_results.py -q
28 passed in 0.50s
```

Compile command:

```text
py -3 -m compileall src/mechcad_harness -q
```

Output: no output; exit code 0.

Diff check:

```text
git diff --check
```

Output: only existing LF-to-CRLF working-copy warnings and pre-existing `new
blank line at EOF` diagnostics for the three task brief files; no diagnostics
were reported for the implementation or test changes.

## M11-5 Task 1 Report

### Status

DONE_WITH_CONCERNS. The M11-5 Task 1 frozen structural evidence and study
models are implemented and the required focused regression command is green.

### Scope

Implemented only the M11-5 Task 1 model/hash boundary from
`.superpowers/sdd/task-1-brief.md`. No generic `Evidence` integration,
publication service, verifier, application wiring, runtime execution, or
documentation changes were made.

### Files Changed

- `src/mechcad_harness/structural/evidence.py`
  - Added versioned, frozen, extra-forbidden structural evidence payload and
    aggregate pipeline provenance models.
  - Added typed evidence subject, currentness, repeatability, and convergence
    status models.
  - Added immutable repeatability policy/result and bounded ordered mesh-study
    policy/result models with semantic summary comparison fields.
  - Added self-excluding canonical SHA-256 hashes for evidence, policies,
    studies, and results; volatile run/storage/correlation fields are excluded
    from canonical payloads.
  - Added request, execution-manifest, result, verification, and convergence
    binding validation.
- `tests/unit/test_structural_evidence_models.py`
  - Added focused tests for self-excluding and tamper-sensitive hashes, schema
    rejection, frozen models, finite values, ordinary subject defaults,
    provenance separation, policy hashes, ordered unique mesh sequences,
    bounded levels, and status enums.
- `.superpowers/sdd/task-1-report.md`
  - Appended this M11-5 Task 1 implementation report while retaining the
    pre-existing report content.

### TDD Evidence

1. Added `tests/unit/test_structural_evidence_models.py` before the new
   production module.
2. Red command:

   ```text
   py -3 -m pytest tests/unit/test_structural_evidence_models.py -q
   ```

   Output: collection failed as expected with
   `ModuleNotFoundError: No module named 'mechcad_harness.structural.evidence'`.
3. Required green command:

   ```text
   py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_models.py tests/unit/test_structural_results.py -q
   ```

   Output: `266 passed in 11.40s`.

### Additional Verification

- `py -3 -m compileall src/mechcad_harness -q`: no output; exit code 0.
- `git diff --check -- src/mechcad_harness/structural/evidence.py tests/unit/test_structural_evidence_models.py`: no output.

### Concerns And Boundaries

- The full repository suite was not run; this task brief requires the focused
  model and M11-4 structural regression command only.
- The existing typed M11-4 models are intentionally consumed rather than
  duplicated. Generic `Evidence` persistence and structural evidence services
  remain later-plan work.
- Existing unrelated dirty and untracked worktree changes were preserved.

### No-Commit Confirmation

No commit, push, reset, stash, clean, checkout, revert, discard, or other
destructive operation was performed.

## M11-5 Task 1 Reviewer Fixes

### Status

FIXED_WITH_CONCERNS. All seven requested reviewer findings for the Task 1
structural evidence models are closed.

### Files Changed For This Fix

- `src/mechcad_harness/structural/evidence.py`
  - Made ordinary physical bindings conditional on the typed subject and made
    convergence-study payloads physical-field-free; convergence records now
    require only their convergence result and reject ordinary physical fields.
  - Enforced ordinary `NOT_EVALUATED` status and exact convergence-result status
    consistency.
  - Required convergence level mesh specification hashes to equal the study's
    ordered mesh specification hash sequence.
  - Rejected mesh/node/element correspondence IDs in both policy summaries and
    comparison field IDs, including normalized singular/plural forms.
  - Restricted the convergence response domain to `free-end` for the admitted
    FE-consistent displacement metric and required nonempty runtime identities.
  - Removed the unused `StructuralMeshManifest` import.
- `src/mechcad_harness/backends/models.py`
  - Made shared `BackendProvenance` frozen, preserving its existing fields and
    producer-facing construction while preventing mutation when nested in
    structural evidence.
- `tests/unit/test_structural_evidence_models.py`
  - Added focused regressions for convergence-only subjects, physical-field
    rejection, ordered mesh-hash binding, comparison correspondence IDs, deep
    provenance immutability, supported domain/runtime constraints, and status
    consistency.
- `.superpowers/sdd/task-1-report.md`
  - Appended this reviewer-fix report and verification evidence.

### Red Evidence

Command:

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py -q
```

Before the fixes, the new regressions produced `6 failed, 10 passed`; failures
covered required physical fields on convergence payloads, mesh sequence
binding, mutable provenance, unsupported domains, empty runtime identities, and
status consistency. The comparison-ID test initially exposed a missing test
import and was corrected before implementation; its production behavior then
failed as expected until the validator was added.

### Green Evidence

Required focused command:

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py -q
16 passed in 0.69s
```

Required structural regression command:

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_models.py tests/unit/test_structural_results.py -q
272 passed in 10.99s
```

Required compile command:

```text
py -3 -m compileall src/mechcad_harness -q
```

Output: no output; exit code 0.

Shared-provenance consumer regression command:

```text
py -3 -m pytest tests/unit/test_backends.py tests/unit/test_artifacts.py tests/unit/test_structural_service.py -q
58 passed in 9.29s
```

### Concerns

- The full repository suite was not run; verification used the required Task 1
  commands plus direct shared-provenance consumers.
- The convergence record remains a model-only boundary; publication,
  independent verification, and convergence evaluation services remain later
  plan tasks.
- Existing unrelated worktree changes and untracked files were preserved.

### No-Commit Confirmation

No commit or push was performed. No reset, stash, clean, checkout, revert,
discard, or other destructive git operation was performed.

## M11-5 Task 1 Remaining Review Findings

### Status

FIXED_WITH_CONCERNS. The two remaining Task 1 review findings are closed.

### Fixes

- `src/mechcad_harness/structural/evidence.py`
  - `StructuralMeshConvergenceResult` now explicitly rejects
    `StructuralMeshConvergenceStatus.NOT_EVALUATED` before level validation.
    Ordinary `StructuralEvidencePayload` records retain `NOT_EVALUATED`; study
    results accept only evaluated or integrity outcomes.
  - Replaced `Any` repeatability comparison values with the recursive typed
    `StructuralSummaryValue` representation. Mapping values are canonicalized
    into sorted tuples of string-key/value tuples, and vectors into tuples, so
    scalar, vector, criterion, and analytical summaries are deeply immutable.
    Existing mesh-correspondence field rejection remains unchanged.
- `tests/unit/test_structural_evidence_models.py`
  - Added rejection coverage for `NOT_EVALUATED` convergence results.
  - Added nested summary mutation and repeatability-result-hash stability
    coverage.

### TDD Evidence

The focused regressions were run before the production fix and failed for the
expected reasons: `NOT_EVALUATED` reached the unrelated missing-level check,
and nested summary mutation raised `KeyError` because the value remained a
mutable dict. After the fix, the focused file passed with `18 passed`.

### Verification

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py -q
18 passed in 0.80s

py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_models.py tests/unit/test_structural_results.py -q
274 passed in 12.83s

py -3 -m compileall src/mechcad_harness -q
no output; exit code 0

py -3 -m pytest tests/unit/test_structural_request.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_service.py tests/unit/test_structural_runtime.py tests/unit/test_structural_validation_observations.py -q
72 passed in 8.75s
```

### Concerns

- The full repository suite was not run; the requested evidence/model/result
  suite and relevant structural consumers were run.
- Existing unrelated worktree changes and untracked files were preserved.

### No-Commit Confirmation

No commit or push was performed. No reset, stash, clean, checkout, revert,
discard, or other destructive operation was performed.

## M12-3 Task 1 Report

### Status

DONE. Implemented only Task 1 from the current `.superpowers/sdd/task-1-brief.md`:
the shared nominal spur primitive and BuiltinTools delegation. Existing unrelated
worktree changes were preserved.

### Files Changed

- `src/mechcad_harness/engineering/spur.py`
  - Added `NominalSpurGeometry` with driver/driven pitch diameters, center
    distance, and positive ratio magnitude.
  - Added `calculate_nominal_spur(module_mm, driver_teeth, driven_teeth)`.
  - Added finite-positive module validation and strict positive integer tooth
    validation, rejecting booleans and numeric floats for tooth counts.
- `src/mechcad_harness/engineering/__init__.py`
  - Exported `NominalSpurGeometry` and `calculate_nominal_spur`.
- `src/mechcad_harness/tools/builtins.py`
  - Delegated `calc_spur_gear` to the generic primitive and mapped its result to
    the unchanged `SpurGearOutput` contract.
- `tests/unit/test_spur_engineering.py`
  - Added independent equation checks for the primitive and built-in tool.
  - Added invalid module and invalid/non-exact tooth-count checks.
- `.superpowers/sdd/task-1-report.md`
  - Appended this M12-3 Task 1 report while retaining prior report history.

### TDD Evidence

1. Added `tests/unit/test_spur_engineering.py` before production implementation.
2. Red command:

   ```text
   py -3 -m pytest tests/unit/test_spur_engineering.py -q
   ```

   Output: collection failed with `ImportError` because
   `NominalSpurGeometry` was not exported by `mechcad_harness.engineering`.
3. Green focused command:

   ```text
   py -3 -m pytest tests/unit/test_spur_engineering.py tests/unit/test_tools.py -q
   ```

   Output: `29 passed in 2.64s`.

### Additional Verification

- `py -3 -m compileall src/mechcad_harness/engineering/spur.py src/mechcad_harness/tools/builtins.py -q`
  - Output: no output; exit code 0.
- Searched `src/mechcad_harness/tools/builtins.py` for `revolute_drive`.
  - Output: no matches.

### Concerns And Boundaries

- The full repository suite was not run; the exact requested focused test
  command passed.
- `SpurGearInput` remains the existing public Pydantic input model; the shared
  primitive enforces strict runtime tooth-count types after model validation.
- No commit or push was performed. No reset, stash, clean, checkout, revert,
  discard, or other destructive operation was performed.
