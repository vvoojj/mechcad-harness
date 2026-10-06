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

## M12-5 Task 3 Report: Ownership And Dependency Configuration

### Status

Implemented only M12-5 Task 3 ownership and dependency configuration with
focused tests. No commit, tag, or push was created. Existing unrelated dirty
and untracked worktree contents were preserved.

### Scope

Changed only the requested repository configuration and focused test files:

- `config/ownership.yaml`
  - Added exactly `/physical_mechanisms/*` owned by
    `mechcad-physical-mechanism`.
  - No root or broad ownership rule was added.
- `config/dependencies.yaml`
  - Added exactly one `/physical_mechanisms/*` rule.
  - It invalidates only `analysis.continuous_clearance_proof` and
    `analysis.kinematic_sweep`.
  - No `analysis.structural` rule was added because the current structural
    schema has no explicit mechanism-consumption relation.
- `tests/unit/test_changes.py`
  - Added coverage that the physical-mechanism owner may check
    `/physical_mechanisms/PM-1` and is rejected for requirements, components,
    structural definitions, and the root path.
  - Retained the existing structural-owner assertions.
- `tests/unit/test_dependency.py`
  - Added coverage that a PM-1 change has exactly the two supported M10 impact
    nodes and no transitive expansion.
  - The test documents the static matcher boundary: `path_matches()` cannot
    synthesize dynamic per-mechanism evidence nodes or infer structural
    consumption.

Before editing, the actual implementations were inspected. `OwnershipPolicy`
loads the configured ownership list and applies its existing longest matching
path behavior. `DependencyGraph.from_yaml()` uses the existing small YAML
parser, while `impact()` applies static `path_matches()` rules and declared
graph edges. No production parser, graph, ChangeEngine, or promotion code was
changed.

### TDD Evidence

The new tests were written before the YAML changes.

Initial red command:

```text
py -3 -m pytest tests/unit/test_changes.py tests/unit/test_dependency.py -q
.........F...F........                                                   [100%]
2 failed, 20 passed in 1.58s
```

The failures were the expected missing-configuration failures:

- the PM-1 ownership check raised `OwnershipViolationError` because no owner
  governed the path;
- the dependency impact was empty instead of containing the two M10 nodes.

After the minimal YAML changes:

```text
py -3 -m pytest tests/unit/test_changes.py tests/unit/test_dependency.py -q
......................                                                   [100%]
22 passed in 1.29s
```

### Verification

Focused Task 3 tests passed:

```text
py -3 -m pytest tests/unit/test_changes.py tests/unit/test_dependency.py -q
22 passed in 1.29s
```

Focused tests plus the relevant Task 2 predecessor coverage passed:

```text
py -3 -m pytest tests/unit/test_changes.py tests/unit/test_dependency.py tests/unit/test_state_foundation.py tests/unit/test_m12_canonical_physical_mechanism.py -q
53 passed in 1.90s
```

Scoped whitespace verification passed:

```text
git diff --check -- config/ownership.yaml config/dependencies.yaml tests/unit/test_changes.py tests/unit/test_dependency.py
```

Git emitted only normal LF-to-CRLF working-copy warnings for tracked files.

### Self-Review And Concerns

- The ownership rule follows the repository's existing collection-item wildcard
  convention and does not broaden ownership of requirements, components,
  structural definitions, or the root.
- The dependency rule is family-level and static by design. It does not create
  per-mechanism evidence nodes, and structural invalidation is intentionally
  absent until an explicit schema relation exists.
- Existing ownership and dependency parser behavior was left unchanged.
- Full repository execution was not run; the requested focused and predecessor
  suites completed successfully.
- No ChangeEngine, promotion, candidate-store, rebase, rollback, M12-6, or
  assembly FEA work was added.
- No commit, tag, push, reset, stash, clean, checkout, revert, discard, or
  other destructive Git operation was performed.

---

# M13-1 Task 3 Report: Geometry Reference @1 Compatibility

## Status

Implemented M13-1 Task 3 in the current worktree. No commit, tag, push, reset,
stash, clean, checkout, revert, discard, or other destructive Git operation was
performed. Existing unrelated worktree changes were preserved.

## Scope

Added `coordinate_system_id` and `reference_hash` to the candidate
`GeometrySourceReference`, and `coordinate_system_id` to the canonical
`CanonicalGeometrySourceReference`.

- Candidate and canonical reference hashes use `reference_hash_payload(...)`.
- `reference_hash` is excluded from its own hash input.
- A `None` coordinate system is excluded from the hash input.
- Candidate `@1` serialization remains exactly the historical four-field
  reference shape.
- Canonical `@1` serialization remains exactly the historical five-field
  reference shape, including its existing `reference_hash`.
- M13 coordinate-bearing serialization emits the coordinate system and the
  self-hash.
- Explicit candidate and canonical projection helpers remain the serializer
  boundary, rather than relying on Pydantic's treatment of `None`.
- Canonical references accept a valid legacy self-hash when a coordinate system
  is added to an old in-memory payload, then recompute the coordinate-aware
  self-hash; arbitrary mismatches remain rejected.

No M10/M11 behavior or `projects/rotator_v2` files were changed.

## TDD Evidence

The literal golden tests from
`.superpowers/sdd/task-3-brief.md` were added before the production model
changes.

Initial red command:

```text
py -3 -m pytest tests/unit/test_m13_legacy_hash_compatibility.py -q
```

Initial result:

```text
3 failed, 3 passed
```

The expected failures were the absent `coordinate_system_id` attributes and
the forbidden coordinate-system input on `GeometrySourceReference`.

The first implementation attempt also exposed an import cycle caused by
eagerly importing the identity helpers while `state.hashing` lazily imports
canonical models. The helpers were moved to the model methods' runtime import
boundary; no identity semantics changed.

## Verification

Focused M13 goldens, identity tests, and the listed M12 regressions:

```text
py -3 -m pytest tests/unit/test_m13_legacy_hash_compatibility.py tests/unit/test_m13_geometry_identity.py tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_canonical_reconstruction.py tests/unit/test_m12_candidate_cad_models.py -q
................................................                         [100%]
48 passed in 3.24s
```

Compile check:

```text
py -3 -m compileall -q src tests
```

Passed with no output.

Scoped whitespace check:

```text
git diff --check -- src/mechcad_harness/candidates/models.py src/mechcad_harness/models/physical_mechanism.py tests/unit/test_m13_legacy_hash_compatibility.py
```

Passed with no whitespace errors. Git emitted only normal LF-to-CRLF working
copy warnings for the tracked Python files.

## Changed Files

- `src/mechcad_harness/candidates/models.py`
- `src/mechcad_harness/models/physical_mechanism.py`
- `tests/unit/test_m13_legacy_hash_compatibility.py`
- `.superpowers/sdd/task-3-report.md`

## Self-Review And Concerns

- The supplied canonical coordinate-extension test retains the old canonical
  self-hash while adding the coordinate field; the implementation accepts only
  that hash if it exactly matches the legacy projection, and immediately
  replaces it with the coordinate-aware hash.
- The repository was not run as a full test suite; the brief-requested focused
  tests and compile check passed.
- Existing unrelated modifications, including the prior contents of this
  report, remain in place.

---

# M13-3P Task 3 Report: Versioned Kinematic Schema And Hash Contracts

## Status

Implemented Task 3 of M13-3P in the current worktree. No commit, tag, push,
release, reset, stash, clean, checkout, revert, discard, or other destructive
Git operation was performed. Existing unrelated dirty and untracked worktree
contents were preserved.

## Scope Completed

Changed only the requested kinematics module and focused tests:

- `src/mechcad_harness/multi_joint_kinematics.py`
  - Added explicit v1 schema discriminators to `RevoluteJointModel` and
    `KinematicModel` while retaining their public names and construction path.
  - Added wrap serializers that remove only the in-memory v1 discriminator;
    nested v1 joint serialization therefore remains historical and does not use
    `exclude_none`.
  - Added `RevoluteJointModelV2` with body endpoints and
    `KinematicModelV2` with rigid bodies, explicit v2 evaluator/agreement
    versions, and no mixed endpoint constructor.
  - Added explicit `parse_revolute_joint_model` and `parse_kinematic_model`
    discriminator selection. Absent discriminators select v1; only the exact
    v2 discriminator selects v2; unknown values fail closed.
  - Added `kinematic_model_wire_payload` and the exact ordered
    `v2_revolute_joint_wire_payload` semantic mapping.
  - Canonicalized v2 bodies and joints after validation, with duplicate IDs
    rejected before sorting. Existing Task 2 member canonicalization remains
    intact.
  - Preserved the v1 hash payload branch without a v1 discriminator. The v2
    branch hashes schema/version fields, persisted canonical body hashes, and
    persisted joint-ID-ordered v2 wire payloads using the existing canonical
    JSON/SHA-256 convention.
  - Did not change the v1 FK/topology execution path. V2 schema/serialization/
    parser/hash contracts are separate from later execution changes.
- `tests/unit/test_m13_3p_legacy_goldens.py`
  - Added discriminator selection, endpoint mismatch, v2 wire-field, and
    explicit v2 requirement coverage.
- `tests/unit/test_m13_3p_rigid_body_groups.py`
  - Added v2 body/member/joint tuple canonicalization and semantic hash
    sensitivity coverage, including agreement version and joint ID.

The immutable Task 0 literals were not edited.

## TDD Evidence

The new contract tests were added before the production implementation.

Initial red command:

```text
py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py tests/unit/test_m13_3p_rigid_body_groups.py -k "discriminator or v2 or semantic_change or joint_id or agreement_version" -v
```

Initial result was the expected missing-feature collection failure:

```text
collected 0 items / 2 errors
ImportError: cannot import name 'KinematicModelV2'
```

After the minimal implementation:

```text
15 passed, 33 deselected in 0.82s
```

## Verification

Required immutable golden suite:

```text
py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -v
10 passed in 0.74s
```

Required v1 M10 kinematics suite:

```text
py -3 -m pytest tests/unit/test_multi_joint_kinematics.py -v
53 passed in 0.89s
```

Focused schema/hash and rigid-body suite:

```text
py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -v
38 passed in 0.82s

py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py tests/unit/test_m13_3p_rigid_body_groups.py -q
48 passed in 0.89s
```

Adjacent M10 serialization regressions:

```text
py -3 -m pytest tests/unit/test_multi_joint_collision_sweep.py tests/unit/test_multi_joint_continuous_path.py -q
35 passed in 0.90s
```

Additional checks passed:

```text
py -3 -m compileall -q src/mechcad_harness tests/unit/test_m13_3p_legacy_goldens.py tests/unit/test_m13_3p_rigid_body_groups.py
git diff --check -- src/mechcad_harness/multi_joint_kinematics.py tests/unit/test_m13_3p_legacy_goldens.py tests/unit/test_m13_3p_rigid_body_groups.py
```

## Concerns And Boundaries

- Existing FK, topology, collision, and continuous-path services remain typed
  against the v1 `KinematicModel`; v2 execution/projection is intentionally
  deferred to the subsequent task boundary.
- The agreement-version sensitivity test uses Pydantic's unvalidated
  `model_copy(update=...)` to exercise identity sensitivity to a changed
  version, while normal v2 construction still requires the literal trusted
  agreement version.
- The complete repository suite was not run; the required focused suites and
  adjacent M10 regressions passed.
- No captured Task 0 golden literal was modified.

## No-Commit Confirmation

No commit, tag, push, release, reset, stash, clean, checkout, revert, discard,
or other destructive Git operation was performed.

---

## Review Fix Evidence: Unknown Schema Discriminators

Addressed the Task 3 review finding by adding focused regression coverage in
`tests/unit/test_m13_3p_rigid_body_groups.py`:

- `parse_revolute_joint_model` rejects an otherwise-valid payload with the
  unknown `revolute-joint-model@999` discriminator.
- `parse_kinematic_model` rejects an otherwise-valid payload with the unknown
  `kinematic-model@999` discriminator.

No production behavior was changed and no v1 golden literal was modified. The
explicit parser implementation already raised `ValueError` for these unknown
values, so this was a regression-only coverage addition; a production RED/GREEN
cycle was not applicable.

Verification:

```text
py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -q
40 passed in 0.71s

py -3 -m pytest tests/unit/test_multi_joint_kinematics.py -q
53 passed in 0.76s

py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -q
10 passed in 0.68s
```

`git diff --check -- tests/unit/test_m13_3p_rigid_body_groups.py` passed with no
diagnostics. No commit, tag, push, release, reset, stash, clean, checkout,
revert, discard, or other destructive Git operation was performed.
