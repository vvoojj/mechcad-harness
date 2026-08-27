# Task 3 Report: Exact Result Requests And DAT RF Discovery

## Status

Implemented Task 3 of M11-4. No commit was created. Existing dirty work was
preserved.

## Scope Completed

### Requested-result-field-controlled deck output

Changed `src/mechcad_harness/structural/deck.py` so `StructuralDeckBuilder`
accepts `requested_result_fields` and emits deterministic output cards only for
the requested result fields:

- `VON_MISES_STRESS`: `*EL FILE` / `S`;
- `DISPLACEMENT`: `*NODE FILE` / `U`, plus the existing textual diagnostic
  `*NODE PRINT,NSET=<support>_nodes` / `U`;
- `REACTIONS`: `*NODE PRINT,NSET=<support>_nodes` / `RF`.

The validator now has an explicit result-card allowance and rejects an
unsupported requested field. Direct builder callers retain the prior M11-3
all-fields default. Production requests are exact because the service passes
`request.requested_result_fields` into every per-case deck build.

Changed `src/mechcad_harness/structural/service.py` only at the per-case deck
invocation boundary. Canonical request fields, criteria, load lowering,
meshing, solver classification, and M11-3 artifact semantics were not
changed.

### Live CalculiX 2.22 RF contract

Added `tests/integration/test_m11_4_live_structural.py`. It runs the real
FreeCAD/Gmsh/CalculiX production path with only `REACTIONS` requested, verifies
the persisted deck has `RF` and no `S` or `U` output cards, then reads the
trusted DAT artifact.

The RF section observed from the real CalculiX 2.22 run is:

```text
 forces (fx,fy,fz) for set FIXED_NODES and time  0.1000000E+01

         1  1.658556E+00  1.538604E+00  1.655428E+00
         2  1.678091E+00  1.543324E+00 -1.657691E+00
         3  1.725380E+00 -1.591698E+00  1.764083E+00
         4  1.710490E+00 -1.585220E+00 -1.766760E+00
         9  1.114289E+01  5.088021E+00  6.349413E-03
```

The short contiguous sample is pinned at
`tests/fixtures/calculix_2_22/reactions.dat`. The live test asserts:

- the exact section header;
- node plus exactly three reaction component tokens per record;
- signed scientific notation for each component;
- no rotational-solid reaction DOF column or `UR` token;
- the captured fixture bytes occur in the trusted DAT artifact.

No reaction parser was added. The fixture is the Task 4 parser input contract.

## TDD Evidence

The focused deck test was written before production changes.

Initial red command:

```text
py -3 -m pytest tests/unit/test_structural_pipeline_contracts.py -q
....F.....                                                               [100%]
1 failed, 9 passed in 0.92s
```

The failure was the expected missing-feature error:

```text
TypeError: StructuralDeckBuilder._render() got an unexpected keyword argument 'requested_result_fields'
```

After the minimal builder change:

```text
py -3 -m pytest tests/unit/test_structural_pipeline_contracts.py -q
..........                                                               [100%]
10 passed in 0.78s
```

## Verification

Focused Task 3 tests after the final validator change:

```text
py -3 -m pytest tests/unit/test_structural_pipeline_contracts.py tests/integration/test_m11_4_live_structural.py -q
...........                                                              [100%]
11 passed in 12.67s
```

Structural unit regression set:

```text
py -3 -m pytest tests/unit/test_structural_models.py tests/unit/test_structural_request.py tests/unit/test_structural_results.py tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py -q
........................................................................ [ 37%]
........................................................................ [ 75%]
................................................                         [100%]
192 passed in 6.36s
```

M11-3 and M11-4 live regression set:

```text
py -3 -m pytest tests/integration/test_m11_3_live_structural.py tests/integration/test_m11_4_live_structural.py -q
..                                                                       [100%]
2 passed in 22.50s
```

Compile check:

```text
py -3 -m compileall -q src tests
```

Passed with no output.

Scoped diff whitespace check:

```text
git diff --check -- src/mechcad_harness/structural/deck.py src/mechcad_harness/structural/service.py
```

Passed with no output. A repository-wide `git diff --check` also reported only
pre-existing EOF blank-line warnings in the already-dirty M11 task brief files;
those files were not changed by this task.

## Concerns And Boundaries

- The live test reuses the existing M11-3 source publication fixture and
  trusted production composition; it does not introduce a second geometry
  setup or fake the solver output.
- The fixture pins a representative contiguous RF section, not the entire
  runtime DAT file. The live test requires that exact sample to occur in the
  trusted artifact.
- DAT/FRD interpretation, malformed-input handling, and structural acceptance
  remain deferred to Task 4 and later M11-4 tasks.
- No unrelated files were reverted or modified, and no commit was created.

## Review Follow-Up

Addressed the Task 3 review concerns without changing production behavior:

- The live RF test now verifies the actual `ProductionApplication`-composed
  CalculiX provider and persisted execution manifest. Its trusted runtime is
  required to identify `CalculiX` version `2.22`, and the manifest identity and
  version must match that provider.
- RF fixture records now require a positive integer node token before checking
  the three scientific-notation reaction components.
- Added `test_public_build_requests_only_requested_result_fields`, which uses
  the existing fake Gmsh parsed-mesh helper and exercises
  `StructuralDeckBuilder.build` directly for RF-only output. The private
  `_render` coverage remains for its lower-level rendering contract.

## Review Follow-Up Verification

Task 3 focused tests:

```text
py -3 -m pytest tests/unit/test_structural_pipeline_contracts.py tests/integration/test_m11_4_live_structural.py -q
............                                                             [100%]
12 passed in 10.82s
```

Structural unit regressions:

```text
py -3 -m pytest tests/unit/test_structural_models.py tests/unit/test_structural_request.py tests/unit/test_structural_results.py tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py -q
........................................................................ [ 37%]
........................................................................ [ 74%]
.................................................                        [100%]
193 passed in 5.13s
```

M11-3 and M11-4 live regressions:

```text
py -3 -m pytest tests/integration/test_m11_3_live_structural.py tests/integration/test_m11_4_live_structural.py -q
..                                                                       [100%]
2 passed in 18.72s
```

`py -3 -m compileall -q src tests` passed with no output. Scoped
`git diff --check` for the two changed test files also passed with no output.

## M11-5 Task 3 Report: Runtime-Independent Structural Evidence Verification

### Status

IMPLEMENTED_WITH_CONCERNS. Task 3 is implemented in the current worktree. No
commit, push, reset, stash, clean, checkout, revert, discard, or other
destructive Git operation was performed.

### Scope

Implemented the read-only structural evidence verifier and the public current
pointer accessor required by `.superpowers/sdd/task-3-brief.md`.

- `StructuralEvidenceVerifier.verify(evidence_id)` accepts only a durable
  Evidence ID and fails closed with `StructuralEvidenceIntegrityError` for
  missing, non-structural, unsupported, tampered, replayed, or internally
  inconsistent evidence.
- The verifier reconstructs the typed request from persisted payload semantics,
  loads the exact immutable StateManager revision, recomputes its state hash,
  locates the bound definition without requiring currentness, and validates
  source/project/revision/definition/body/request bindings.
- The explicitly persisted execution-manifest artifact ID and byte hash are
  resolved through a run-scoped `ArtifactStore.read_verified_strict()` call.
  The manifest is parsed only after byte/type/scope/size/SHA/producer/input
  checks and is compared to the persisted typed manifest.
- STEP, MSH, INP, FRD, DAT, and LOG artifacts are byte-verified through the
  durable ArtifactStore boundary before the accepted M11-4 interpreter/parser
  path is invoked. Direct FreeCAD, Gmsh, CalculiX, solver, and parser
  provenance is checked separately from aggregate pipeline provenance.
- The accepted result interpreter and verification service reconstruct the
  result and criterion findings. Result, verification, material-authority
  outcomes, parser provenance, and hashes are compared to persisted evidence,
  preserving PASS, FAIL, and NOT_EVALUABLE as engineering outcomes.
- `reconstruct_analytical_validation()` reparses trusted MSH bytes and
  recomputes persisted analytical equations/checks from typed observations and
  policy semantics without FreeCAD realization or runtime discovery.
- `currentness(evidence_id)` is separate from verification and calls only the
  new public `StateManager.load_current_pointer()` accessor. Historical
  verification does not consult current state.

### TDD Evidence

The first verifier command was run before the implementation:

```text
py -3 -m pytest tests/unit/test_structural_evidence_verifier.py -q
2 failed
```

The failures were the expected missing `StateManager.load_current_pointer`
accessor and missing `StructuralEvidenceVerifier` module. After the minimal
implementation and persisted fixture coverage:

```text
py -3 -m pytest tests/unit/test_structural_evidence_verifier.py -q
7 passed in 3.18s
```

### Runtime-Independence Evidence

The verifier tests patch `discover_freecad`, `discover_gmsh`, and
`discover_calculix` to fail, patch `subprocess.run` to fail, and verify a fresh
store reload successfully. The analytical reconstruction test applies the
same unavailable-runtime/process guards. Both tests pass, demonstrating that
historical verification does not require current FreeCAD, Gmsh, or CalculiX
discovery and does not launch a subprocess.

### Required Verification

```text
py -3 -m pytest tests/unit/test_structural_evidence_verifier.py -q
7 passed in 3.18s

py -3 -m pytest tests/unit/test_structural_evidence_verifier.py tests/unit/test_structural_results.py tests/unit/test_structural_validation_observations.py tests/unit/test_artifacts.py -q
190 passed in 15.04s

py -3 -m compileall src/mechcad_harness -q
no output; exit code 0
```

The scoped `git diff --check` command for the Task 3 implementation/test files
also passed with no diagnostics. Git emitted only normal LF-to-CRLF working
copy warnings for tracked files.

### Files Changed By Task 3

- `src/mechcad_harness/structural/evidence_service.py`
  - Added durable structural Evidence reload verification, explicit artifact
    bindings, result/verification reconstruction, provenance checks, analytical
    replay, currentness, and the structural integrity error type.
- `src/mechcad_harness/structural/validation.py`
  - Added the pure `reconstruct_analytical_validation()` helper. Existing
    analytical models remain in the accepted data-only evidence model module.
- `src/mechcad_harness/state/manager.py`
  - Added public read-only `load_current_pointer(project_id)`.
- `tests/unit/test_structural_evidence_verifier.py`
  - Added persisted typed fixture coverage for request and immutable revision
    binding, explicit manifest ID/hash, tamper-before-parser rejection,
    runtime independence, analytical replay, and currentness separation.
- `.superpowers/sdd/task-3-report.md`
  - Appended this report while retaining the pre-existing historical report.

### Concerns And Boundaries

- The full repository and live M11-5 capstones were not run; they are outside
  this Task 3 focused command set.
- Production application composition, publication, repeatability, convergence,
  and ToolBroker/API wiring remain later-task scope.
- The verifier composes the accepted M11-4 interpreter after durable
  preverification; that interpreter retains its existing deterministic raw
  artifact identity checks as a secondary accepted integrity check. The
  execution-manifest artifact itself is resolved from the persisted explicit
  ID/hash and is never derived as the authority.
- Existing unrelated dirty and untracked worktree changes were preserved.

### No-Destructive-Operation Confirmation

No commit, push, reset, stash, clean, checkout, revert, discard, or destructive
Git operation was performed.
