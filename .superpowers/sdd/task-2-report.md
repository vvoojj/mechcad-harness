# Task 2 Report: Ordered Structural Case Partitions

## Status

Implemented Task 2 of M11-4. No commit or destructive Git operation was made.

## Files Changed

- `src/mechcad_harness/structural/models.py`
  - Added case-level `failure_stage`, `error_detail`, and solver manifest diagnostics.
  - Added optional shared mesh identity to the request-manifest API and bound it to every ordered case manifest.
  - Made legacy request-level deck fields optional so a failed first case can still produce a valid request manifest.
  - Kept case and request hashes non-circular: case hashes bind direct artifact references; request hashes bind ordered case hashes and the shared mesh.
- `src/mechcad_harness/structural/service.py`
  - Publishes exactly one byte-verified mesh artifact per request.
  - Builds, preflights, and solves one selected case at a time in request order.
  - Uses case-scoped deck, FRD, DAT, and log artifact identities.
  - Persists partial ordered case manifests and a FAILED request manifest when a case fails, including solver/deck/preflight diagnostics.
  - Chains direct artifact inputs as mesh artifact -> case deck -> solver/log artifacts; the request manifest artifact uses the request hash, never a manifest hash.
  - Preserves source binding, geometry byte rehash, constraint preflight, and existing solver classification/provider identities.
- `src/mechcad_harness/structural/fakes.py`
  - Added deterministic `calls` counting and `fail_on_call` support.
  - Retained fake provider identities and used nonempty minimal FRD/DAT bytes.
- `tests/unit/test_structural_service.py`
  - Added two-load-case ordered partition coverage, one-mesh/two-solve assertions, artifact input-chain assertions, and second-case failure manifest persistence/diagnostic coverage.
  - Expanded the fixture definition with a second independent load case while retaining the existing single-case tests.

## TDD Evidence

Red command, before the service implementation:

```text
py -3 -m pytest tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py -q
2 failed, 17 passed in 4.18s
```

The two new tests failed because the service returned no case manifests and merged the selected cases into one execution.

Focused green command after implementation:

```text
py -3 -m pytest tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py -q
19 passed in 3.43s
```

## Required Verification

Command:

```text
py -3 -m pytest tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py tests/integration/test_m11_3_live_structural.py -q
```

Output:

```text
....................                                                     [100%]
20 passed in 12.91s
```

Command:

```text
py -3 -m compileall src/mechcad_harness -q
```

Output: no output; exit code 0.

Command:

```text
git diff --check
```

Output: Git emitted existing LF-to-CRLF working-copy warnings and the existing `new blank line at EOF` diagnostics for `.superpowers/sdd/task-1-brief.md`, `.superpowers/sdd/task-2-brief.md`, and `.superpowers/sdd/task-3-brief.md`. No implementation or focused-test whitespace diagnostics were reported.

Additional structural regression command:

```text
py -3 -m pytest tests/unit/test_structural_results.py tests/unit/test_structural_models.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_service.py -q
154 passed in 4.14s
```

## Concerns

- The existing `StructuralExecutionManifest` remains the durable request-level manifest container for compatibility with the current M11-3 API. Its legacy first-case direct artifact accessors are retained; ordered case manifests are authoritative for multi-case execution.
- A failure before mesh publication (source, geometry, region, or mesh stage) retains the existing no-manifest behavior. Case-partition request manifests begin once the shared mesh has been successfully published.
- No result parsing, result interpretation, acceptance evaluation, or FEA result model execution was added; those are outside Task 2.
- Existing unrelated dirty and untracked worktree changes were preserved.

## Review Fixes

- `StructuralRequestExecutionManifest` now requires one shared mesh ID/hash pair,
  enforces exact case mesh identity equality, and accepts only an ordered selected-case
  prefix for non-successful manifests. Successful manifests must contain every selected
  case and every case must succeed.
- Durable request manifests apply the same prefix/completeness rules and pass the
  request execution status through the standalone manifest model.
- Multi-case durable manifests now leave legacy top-level deck, solver, log, FRD, and
  DAT fields unavailable instead of exposing first/last case values. Single-case
  compatibility remains unchanged.
- First-case and intermediate-case solver failures now persist the failed request
  manifest with the ordered partial case prefix rather than falling through the outer
  unexpected-error handler.
- Added regression coverage for first/intermediate failure persistence, multi-case
  legacy-field suppression, and standalone request-level mesh ID/hash equality.

## Review-Fix Verification

```text
py -3 -m pytest tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py tests/integration/test_m11_3_live_structural.py tests/unit/test_structural_results.py tests/unit/test_structural_models.py -q
159 passed in 12.83s

py -3 -m compileall src/mechcad_harness -q
no output; exit code 0

git diff --check -- src/mechcad_harness/structural/models.py src/mechcad_harness/structural/service.py tests/unit/test_structural_service.py tests/unit/test_structural_results.py
no output; exit code 0
```

## Task 2 Important Finding Closure

- Added shared fail-closed request/case-history validation in
  `src/mechcad_harness/structural/models.py`.
- Successful request manifests now require the complete selected-case order and
  every recorded case to be successful.
- Failed request manifests now require a nonempty selected-order prefix whose
  preceding cases all succeeded and whose final recorded case failed.
- Failed status with all-successful cases, success after a failure, and repeated
  failures are rejected for both standalone and durable request manifests.
- Added last-case success/failure acceptance tests and impossible-history
  regression tests in `tests/unit/test_structural_results.py`.

## Important Finding Verification

```text
py -3 -m pytest tests/unit/test_structural_results.py -q
37 passed in 0.69s

py -3 -m pytest tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py tests/integration/test_m11_3_live_structural.py tests/unit/test_structural_results.py tests/unit/test_structural_models.py -q
166 passed in 13.40s

py -3 -m compileall src/mechcad_harness -q
no output; exit code 0

git diff --check -- src/mechcad_harness/structural/models.py tests/unit/test_structural_results.py
no output; exit code 0
```

## M11-5 Task 2 Report: Generic Structural Evidence Payload

### Status

DONE_WITH_CONCERNS. M11-5 Task 2 is implemented in the current worktree. The
generic `Evidence` model now accepts an optional typed structural payload and
typed structural subject discriminator while preserving legacy evidence. No
commit, push, or destructive operation was performed.

### Files

- `src/mechcad_harness/models/evidence.py`
  - Added `subject: EvidenceSubject | None = None` for legacy-compatible
    structural discrimination.
  - Added optional typed `structural_evidence_payload:
    StructuralEvidencePayload | None` with absent/None serialization behavior.
  - Added local validation binding payload subject, Evidence subject, and
    `kind` without importing structural services, runtime discovery, artifact
    storage, or the production application.
- `tests/unit/test_structural_evidence_models.py`
  - Added legacy round-trip, ordinary/convergence discriminator, unsupported
    schema, generic dependency-boundary, and `EvidenceStore` round-trip tests.
- `.superpowers/sdd/task-2-report.md`
  - Appended this M11-5 Task 2 report; existing historical content was retained.
- `src/mechcad_harness/structural/__init__.py`
  - Not changed; no export was needed for the typed model import.
- `src/mechcad_harness/dependency/storage.py`
  - Not changed; `EvidenceStore` remains generic.

### TDD Red

The required first failing test was run before the production change:

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py::test_legacy_evidence_round_trip_has_no_structural_payload -q
```

Result: `1 failed`. The expected failure was `AttributeError` because
`Evidence` had no `subject` field.

### TDD Green

Focused command:

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py -q
```

Result: `23 passed in 0.82s`.

Required regression command:

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_state_foundation.py tests/unit/test_production_application.py -q
```

Result: `59 passed in 3.16s`.

Required compile command:

```text
py -3 -m compileall src/mechcad_harness -q
```

Result: no output; exit code 0.

Additional focused diff check:

```text
git diff --check -- src/mechcad_harness/models/evidence.py tests/unit/test_structural_evidence_models.py
```

Result: no whitespace errors. Git emitted only the existing LF-to-CRLF
working-copy warning for `src/mechcad_harness/models/evidence.py`.

### Dependency-Boundary Review

- `models/evidence.py` imports only the typed `EvidenceSubject` and
  `StructuralEvidencePayload` models from `structural.evidence`.
- It does not import `StructuralEvidenceVerifier`, structural execution or
  publication services, `ArtifactStore`, `EvidenceStore`, runtime discovery,
  or `ProductionApplication`.
- The validator performs only typed discriminator consistency checks.
- `dependency/storage.py` has no structural imports, checks, raw-path reads,
  runtime use, or second persistence subsystem.
- Legacy Evidence construction remains valid with `subject=None` and no
  structural payload; the optional payload is omitted when absent.

### Concerns

- The full repository suite was not requested or run; verification used the
  exact Task 2 commands from the brief.
- The test module also contains the pre-existing Task 1 structural model tests;
  no unrelated test content was removed or rewritten.
- The worktree contains unrelated dirty and untracked files, including prior
  M11-5 artifacts and generated paths. They were preserved unchanged.

### No-Destructive-Operation Confirmation

No commit, push, reset, stash, clean, checkout, revert, discard, or other
destructive operation was performed.

## Task 2 Import-Boundary Fix

### Status

FIXED. The generic `Evidence` import no longer transitively loads structural
runtime, geometry, mesh, or validation modules. Existing unrelated worktree
changes were preserved; no commit, push, or destructive Git operation was
performed.

### Files Changed

- `src/mechcad_harness/structural/evidence_models.py`
  - Added the single authoritative runtime-independent analytical policy,
    geometry/material observation, analytical check, and validation result
    models with their validation and hash helpers.
- `src/mechcad_harness/structural/evidence.py`
  - Replaced its `structural.validation` import with the data-only
    `structural.evidence_models` import.
- `src/mechcad_harness/structural/validation.py`
  - Re-exports and uses the moved analytical models and helpers while retaining
    the existing geometry/mesh-dependent validator and public import names.
- `tests/unit/test_structural_evidence_models.py`
  - Added a clean subprocess import-boundary regression test.
  - Changed the legacy round-trip fixture kind to `analysis.legacy`; ordinary,
    convergence, and unsupported-schema discriminator coverage remains.
- `.superpowers/sdd/task-2-report.md`
  - Appended this fix report.

### TDD Evidence

The new import-boundary test was run before the refactor and failed as expected:
the subprocess reported all four forbidden modules loaded:
`structural.geometry`, `structural.mesh`, `structural.runtime`, and
`structural.validation`.

After the refactor, the clean subprocess assertion passed with:

```text
[]
```

### Verification

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py -q
24 passed in 2.06s

py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_state_foundation.py tests/unit/test_production_application.py -q
60 passed in 5.77s

py -3 -m pytest tests/unit/test_structural_validation_observations.py tests/unit/test_structural_results.py tests/unit/test_structural_service.py -q
169 passed in 19.56s

py -3 -m compileall src/mechcad_harness -q
no output; exit code 0
```

### Concerns

- The full repository suite was not run; the requested focused suites and
  compile check passed.
- `EvidenceStore` was not changed and remains generic.

## Task 2 Code-Quality Follow-up

The direct clean subprocess import finding was fixed in the current worktree.
`structural/evidence_models.py` no longer imports `mechcad_harness.models.common`
and therefore no longer executes the eager `mechcad_harness.models` package
initializer. Its four analytical data-model families now share the local
`_StructuralEvidenceModel` base, which preserves the frozen and
`extra="forbid"` contract without duplicating policy, observation, check, or
result definitions. `structural.validation` continues to import and re-export
the identical classes.

The new direct subprocess regression test was first run against the unfixed
worktree and failed with the expected circular-import `ImportError`. It passed
after the minimal base-class change. The existing generic Evidence import
boundary test also remains passing.

### Follow-up Verification

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py -q
25 passed in 2.13s

py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_state_foundation.py tests/unit/test_production_application.py -q
61 passed in 4.81s

py -3 -m pytest tests/unit/test_structural_validation_observations.py tests/unit/test_structural_results.py tests/unit/test_structural_service.py -q
169 passed in 15.17s

py -3 -m compileall src/mechcad_harness -q
no output; exit code 0
```

An additional subprocess identity/configuration check passed for the
`structural.validation` re-exports and the frozen/extra-forbid model contract.

## Final Task 2 Review Fixes

### Status

FIXED. The final Task 2 review findings are closed without commit, push, or
destructive Git operation.

### Changes

- `src/mechcad_harness/models/evidence.py`
  - Added `exclude_if=lambda value: value is None` to the generic `subject`
    field, preserving the legacy serialized Evidence shape and persisted hash/id.
- `src/mechcad_harness/models/__init__.py`
  - Made `Evidence` a lazy package export through `__getattr__`, preserving
    `from mechcad_harness.models import Evidence` while removing the eager
    import cycle.
- `tests/unit/test_structural_evidence_models.py`
  - Added explicit legacy omission coverage for `subject`.
  - Added a clean direct `structural.evidence` subprocess forbidden-module probe.
- `tests/integration/test_m10_3_provenance.py`
  - Strengthened the existing legacy persisted shape/hash/id regression with an
    explicit assertion that `subject` is absent.
- `.superpowers/sdd/task-2-report.md`
  - Appended this review-fix record.

### TDD Evidence

Before the production fix:

```text
test_legacy_evidence_round_trip_has_no_structural_payload: failed because subject was serialized
test_structural_evidence_import_does_not_load_structural_runtime_modules: failed with circular-import ImportError
test_evidence_store_preserves_legacy_persisted_shape_hash_and_id: failed with a changed persisted hash
```

After the production fix, all three regressions passed.

### Required Verification

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py -q
26 passed in 3.97s

py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_state_foundation.py tests/unit/test_production_application.py -q
62 passed in 6.77s

py -3 -m pytest tests/unit/test_structural_validation_observations.py tests/unit/test_structural_results.py tests/unit/test_structural_service.py tests/unit/test_artifacts.py -q
202 passed in 19.42s

py -3 -m pytest tests/unit/test_models.py tests/unit/test_tools.py -q
19 passed in 2.07s

py -3 -m compileall src/mechcad_harness -q
no output; exit code 0
```

Both clean subprocess probes returned `[]` for the forbidden structural
runtime, geometry, mesh, and validation modules. `from mechcad_harness.models
import Evidence` also passed. The full repository suite was not run.

## M12-3 Task 2: Frozen Revolute-Drive Models

### Status

DONE. Task 2 model schemas and focused tests were implemented without commit,
push, or destructive Git operations. Existing worktree changes and the Task 1
shared spur work were preserved.

### Files Changed

- `src/mechcad_harness/revolute_drive/models.py`
  - Added the four requested enums and frozen, `extra="forbid"` Pydantic models.
  - Added finite/exact-unit/domain validation for scalar, load-case, efficiency,
    safety-factor, yield-strength, and support-geometry inputs.
  - Preserved source-authority versus policy-assumption provenance explicitly.
  - Added deterministic canonical JSON SHA-256 requirements/result hashes,
    excluding each model's own hash field.
- `src/mechcad_harness/revolute_drive/__init__.py`
  - Exported the Task 2 model API.
- `tests/unit/test_m12_revolute_drive_models.py`
  - Added focused frozen/strict, provenance, scalar/domain, load-case,
    support-ordering, template, unresolved-construction, and hash tests.
- `.superpowers/sdd/task-2-report.md`
  - Appended this M12-3 Task 2 report; existing historical scratch content was
    retained.

### TDD Evidence

Red command before the package existed:

```text
py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py -q
1 error during collection: ModuleNotFoundError: No module named 'mechcad_harness.revolute_drive'
```

Focused green command:

```text
py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py -q
........................                                                 [100%]
24 passed in 0.66s
```

Additional verification:

```text
py -3 -m compileall src/mechcad_harness/revolute_drive -q
no output; exit code 0

git diff --check -- src/mechcad_harness/revolute_drive tests/unit/test_m12_revolute_drive_models.py
no output; exit code 0
```

### Concerns

- The complete repository suite was not run; verification was limited to the
  requested focused model suite, package compilation, and scoped whitespace
  validation.
- Task 2 does not add calculations, construction service behavior, production
  composition, or documentation beyond this required scratch report.

## M12-3 Task 2 Review Fixes

### Status

FIXED. All six requested model/test review findings are closed. No commit,
push, or destructive Git operation was performed. Unrelated worktree changes
and Task 1 were preserved.

### Changes

- `RevoluteDriveConstructionOutcome` now rejects both candidate-free resolved
  outcomes and candidate-backed unresolved outcomes.
- `ShaftSupportGeometry` now owns the single load-plane coordinate and binds
  support A, support B, and the load plane through `SourceBoundScalar` with
  exact `mm` units and explicit provenance.
- `StaticOutputShaftDesignLoadCase` no longer contains a duplicate load-plane
  coordinate.
- All supplied template IDs and axis-frame references reject empty or any
  whitespace-containing values, including support mounts and gears.
- Source-authority scalar paths and consumed requirement paths now use the exact
  M12-2 literal canonical path rule, rejecting root, `//`, and `~` paths.
- Added focused regressions for each finding, provenance, strict/frozen models,
  and requirements-hash self-exclusion/determinism.

### Verification

```text
py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py -q
........................................                                 [100%]
40 passed in 0.84s

py -3 -m compileall src/mechcad_harness -q
no output; exit code 0

git diff --check -- src/mechcad_harness/revolute_drive/models.py tests/unit/test_m12_revolute_drive_models.py
no output; exit code 0
```

### Concerns

- The complete repository test suite was not run.
- Calculations, service, application, and unrelated documentation were not
  modified.
