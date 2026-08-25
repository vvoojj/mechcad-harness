# MechCAD M11-4 Result Interpretation And Analytical Validation Completion Report

## Final Disposition

**`M11_4_REAL_FEA_RESULT_ANALYTICAL_VALIDATION_VERIFIED`**

M11-4 is verified for the bounded source-bound, single-body, linear-static
structural result interpretation and fixed cantilever analytical validation
scope described below. This report records observed implementation and test
evidence only. It does not expand the structural capability beyond that scope.

## Accepted Baseline

The accepted predecessor baselines are:

- `M10_FULLY_CLOSED_LIVE_VERIFIED`.
- `M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED`.
- `M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED`.

The fresh repository-wide verification for this final review completed with
`1231 passed, 34 skipped, 0 failed, 0 errors` in `712.25s` (`0:11:52`).

## M11-4 Production Scope

`ProductionApplication.execute_structural_analysis()` executes the existing
source-bound structural pipeline and returns a `StructuralExecutionResult`.
For a successful execution, its `.manifest` is passed to
`ProductionApplication.evaluate_structural_analysis()` as the execution
manifest. Evaluation then uses internally constructed FRD and DAT parsers,
`StructuralResultInterpreter`, and `StructuralVerificationService` to produce a
typed result and criterion verification. Callers do not supply parser
identities, raw result bytes, result hashes, or result values.

Analytical validation is intentionally a separate production service API. The
application reloads the authoritative MSH artifact through the trusted parser,
re-realizes the source STEP through the composed FreeCAD geometry adapter, and
rebuilds material observations from canonical definition snapshots. Caller-
supplied mesh, geometry, and material objects are not analytical authority.
Ordinary structural evaluation does not select or infer an analytical policy.

The live capstone covers one `200 x 20 x 10 mm` single-solid cantilever, a
semantic fixed support at `x=min`, a semantic free load region at `x=max`, one
`100 N` negative-Z resultant force, and an isotropic linear-elastic material.

## Result Trust Boundary

The interpreter reads only artifact references in a successful,
source-bound execution manifest. It rehashes artifact bytes and verifies
artifact identity, type, size, producer identity/version, input hashes, source
STEP bytes, trusted FreeCAD source-geometry provenance, source revision/state
hash, pinned Gmsh identity/version `mechcad-structural-gmsh@1` / `4.15.0`, exact
Gmsh artifact backend provenance and direct producer identity, mesh provenance,
canonical load semantics, deterministic deck/CLOAD lowering, per-case
load-case/solver provenance, and solver completion semantics before parsing.
Trusted FreeCAD provenance requires source `bundled` and revision
`freecad-1.1.3-bundled`, in addition to the exact name, adapter, library, and
version. Empty LOG bytes are rejected even if success flags and forged metadata
claim otherwise. The interpreter requires the exact trusted CalculiX runtime
identity version `2.22`; a manifest version is not accepted merely because it
is nonempty or non-`unknown`. The FRD declared version must match that same
trusted version.

Structural evaluation has no `EvidenceStore` publication side effect. The
computational result and analytical validation remain result records, not
accepted structural Evidence.

## Lowered-Load Provenance

For each canonical resultant force, interpretation reconstructs the verified
deck's semantic `*SURFACE` C3D10 face references, requires the exact canonical
element/face set from the trusted MSH semantic boundary region, checks
referenced node coordinates, and independently derives face area, area-weighted
application point, traction, force/moment conservation errors, and the
consistent nodal CLOAD vector. Missing, wrong-face, or non-reconstructible deck
geometry is rejected rather than accepted from self-reported provenance.

## FRD Parser

The FRD parser identity observed in the live result is
`mechcad-calculix-frd-result-parser@1`. It admits only the whitelisted minimal
fixture envelope or the exact captured CalculiX 2.22 header/program/version
envelope, including the permitted runtime header record forms. Arbitrary,
duplicate, reordered, or unrecognized `1U` records are rejected. It parses the
requested displacement and stress fields from byte-verified output, and
validates any admitted element-envelope connectivity against the trusted C3D10
mesh before binding samples to mesh hashes and node identities.

## DAT Parser

The DAT parser identity observed in the live result is
`mechcad-calculix-dat-result-parser@1`. The live reaction test observed the
CalculiX 2.22 `forces (fx,fy,fz)` section for `FIXED_NODES`, with node IDs and
three translational reaction components in scientific notation. Rotational
reaction DOFs were not accepted by the tested parser contract.

## Load-Case Binding

The live PASS request selected `LC-1`. A live two-case request also selected
`LC-1`, `LC-2` in order and interpreted both case manifests through one shared
mesh artifact. Each execution manifest, ordered case manifest, deck, FRD, DAT,
LOG, result, and verification binds to its load case and to the exact source
project, revision, state hash, definition hash, geometry artifact hash, request
hash, and mesh specification hash.

## Typed StructuralAnalysisResult

The interpreter returns a typed `StructuralAnalysisResult` containing the
source binding, definition identity/hash, request hash, execution-manifest
hash, mesh hash, ordered load-case results, parser provenance, and result
maturity. The live PASS result maturity was `FEA_EXECUTED`.

## Displacement Representation

The live PASS result contained `448` displacement samples. The maximum nodal
displacement magnitude was `2.252616918035249 mm` at node `14`. The analytical
tip comparison used the FE-consistent CPS6 quadratic surface integral over the
semantic free-end region, not a raw node average.

## Stress Representation

The live PASS result contained `448` stress samples. Stress is explicitly
represented as `calculix_extrapolated_nodal_stress`; it is not an integration-
point stress result and does not establish a global yield or safety claim.

## Von Mises Derivation

The maximum von Mises stress observed was `58.08477941035892 MPa`. The test
recomputed the maximum by applying the canonical tensor von Mises equation to
the parsed stress tensor and confirmed that the selected maximum sample's
mesh hash matched the result mesh hash.

## Reaction Interpretation

The live PASS result contained `13` reaction samples bound to the fixed
support node set. The total reaction force was
`(3.662000005988375e-05, 2.0019999972475944e-05, 100.00015999999971) N`.
The total reaction moment about the declared support-centroid reference was
`(-7.124999979168933e-05, -19999.99975, -0.0009540000010019867) N*mm`.

## Result Integrity Failure Semantics

Missing, changed, malformed, mismatched, or untrusted result artifacts are
rejected before result interpretation. Successful interpretation requires a
successful execution manifest, successful ordered load cases, exit code zero,
finished solver status, FRD/DAT/LOG output, valid mesh provenance, and exact
artifact bindings. Failed execution does not become a typed successful result.

## Material Authority Evaluation

The live canonical material snapshot was `Alu7075`, with `E=70000.0 MPa` and
`nu=0.33`. The material assignment was `MAT-1`; both elastic-modulus and
Poisson-ratio source identities were `test`. Material observations were built
from canonical definition snapshots and independently bound to the source
geometry/request identity rather than copied from the analytical policy.

## Criterion PASS Semantics

The live PASS case used a maximum displacement limit of `5.0 mm`. Its observed
maximum displacement was `2.252616918035249 mm`, and all six analytical checks
passed. The production verification status was `PASS`, and the analytical
validation status was `pass`.

## Criterion FAIL Semantics

The live engineering-fail case used the same valid physical execution with a
predeclared maximum displacement limit of `1.0 mm`. Solver execution was
`SUCCEEDED`; criterion evaluation was `FAIL` with reason
`maximum_displacement_exceeded`. The observed value was
`2.252616918035249 mm`.

## Criterion NOT_EVALUABLE Semantics

The live missing-yield case completed with solver execution status
`SUCCEEDED` and retained `448` real stress samples. The declared yield-safety
factor criterion was `NOT_EVALUABLE` with reason
`missing_material_property`. Missing material authority did not become a
fabricated PASS or FAIL.

## Overall Verification Semantics

Overall verification is `FAIL` if any criterion is `FAIL`, `NOT_EVALUABLE` if
there are no criteria or any criterion is `NOT_EVALUABLE` and none is `FAIL`,
and `PASS` only when all criteria are evaluable and pass. The live empty-
criteria interpretation test observed `NOT_EVALUABLE`.

## Analytical Cantilever Definition

The declared live cantilever is a source-bound `200 x 20 x 10 mm` rectangular
single solid. The fixed semantic region is the planar `x=min` face. The free
semantic region is the planar `x=max` face. The load is one uniform-surface-
traction-equivalent `100 N` resultant directed along negative Z. The material
uses `E=70000 MPa` and `nu=0.33`.

## Analytical Reference Equations

The declared second moment was:

```text
I = width * height^3 / 12
```

The declared signed Euler-Bernoulli tip displacement was:

```text
delta = F * L^3 / (3 * E * I)
```

The expected signed tip displacement was `-2.2857142857142856 mm`.
Expected reaction force was `(-0.0, -0.0, 100.0) N`. Expected reaction
moment was `(0.0, -20000.0, -0.0) N*mm` about the declared support-centroid
reference point.

## Analytical Validation Policy

The fixed mesh specification used target size `5.0 mm`, quality policy
`m11-4-fixed-cantilever-quality@1`, and mesher settings
`m11-4-fixed-cantilever-mesher@1`. The declared displacement relative
tolerance was `20%`; the declared reaction relative tolerance was `5%`.
The absolute residual ceilings used by the live test were `0.001 N` for force
and `0.1 N*mm` for moment. The policy was constructed before live FreeCAD,
Gmsh, or CalculiX observation.

## Tip Displacement Comparison

Expected: `-2.2857142857142856 mm`.

Observed FE-consistent free-end integral: `-2.250974166666667 mm`.

Relative error: `0.015198802083333157`, or `1.5198802083333157%`, against the
declared `20%` tolerance. The check passed.

## Reaction Force Comparison

Expected: `(-0.0, -0.0, 100.0) N`.

Observed: `(3.662000005988375e-05, 2.0019999972475944e-05,
100.00015999999971) N`.

Force equilibrium residual: `0.00016535363531049456 N`, below the declared
`0.001 N` absolute ceiling. Relative analytical error was
`1.6535363531049457e-06`. The check passed.

## Reaction Moment Comparison

Expected: `(0.0, -20000.0, -0.0) N*mm`.

Observed: `(-7.124999979168933e-05, -19999.99975,
-0.0009540000010019867) N*mm`.

Moment equilibrium residual: `0.0009887833761053628 N*mm`, below the declared
`0.1 N*mm` absolute ceiling. Relative analytical error was
`4.943916880526814e-08`. The check passed.

## Live Stress Interpretation

The live PASS request asked for `DISPLACEMENT`, `VON_MISES_STRESS`, and
`REACTIONS`. The observed maximum von Mises value was
`58.08477941035892 MPa` over `448` extrapolated nodal stress samples. No
global yield or safety conclusion was made.

## Engineering PASS Case

The real CalculiX execution succeeded, the typed result was interpreted, the
criterion verification was `PASS`, and the analytical validation was `pass`.
The execution produced six artifacts: MSH, INP, FRD, DAT, LOG, and JSON.

## Engineering FAIL Case

The real solver execution succeeded with the same source-bound physical setup,
but the predeclared `1.0 mm` maximum displacement criterion evaluated to
`FAIL` with reason `maximum_displacement_exceeded`. This is an engineering
criterion result, not a solver failure.

## NOT_EVALUABLE Case

The real solver execution succeeded and produced the stress field, but the
yield-strength snapshot was intentionally absent. The yield-safety-factor
criterion evaluated to `NOT_EVALUABLE` with reason
`missing_material_property`.

## Parser Provenance

The live result recorded:

- FRD parser: `mechcad-calculix-frd-result-parser@1`.
- DAT parser: `mechcad-calculix-dat-result-parser@1`.
- Interpreter: `mechcad-structural-result-interpreter@1`.
- CalculiX direct producer: `mechcad-structural-calculix@1`.
- CalculiX backend provenance: `calculix` / `mechcad-structural-calculix@1` /
  `CalculiX` / `2.22` / `bundled` / `calculix-2.22-bundled`.
- Gmsh: `4.15.0`.
- FreeCAD: `1.1.3`.

## Result Hashing

The recorded live PASS identities were:

- Policy hash: `sha256:8cf61be14b45b671260dd359d29a0501338eb313f107619725d3bbde54492a76`.
- Request hash: `sha256:6400824d289ffe3f49ec4647ba49cee554439f8324f29cb57c1fc06682e8980f`.
- Result hash: `sha256:114498050da7907a1403584d64b24f5f9e682709832e859e81db33f0f8d64812`.
- Verification hash: `sha256:1e6e7d87d64044d60c1d266c0111e909b3333c89d6ce2f7eef89f0dc5ad22f07`.
- Analytical validation hash: `sha256:477f538bc1cec86600f7ac779d89a50970634099f4df0d0fb37882515be1e258`.
- Mesh hash: `sha256:e83e278ce20630f331fae9a68c3fb0adc196659f1948c7f0092f646e84dc4698`.

## Result Artifact Semantics

The six live PASS artifacts were byte-verified through `ArtifactStore`. The
MSH artifact contained the actual mesh bytes; its input hash was the
deterministic pre-mesh identity over source geometry, mesh specification,
region map, and Gmsh identity/version rather than the MSH output hash. The INP
artifact was the deterministic CalculiX deck; FRD, DAT, and LOG were solver
outputs; and JSON was the execution manifest. The manifest and artifact records
retained source binding, producer identity/version, SHA-256, and input-hash
relationships. The solver manifest and each FRD, DAT, and LOG artifact also
retain the exact CalculiX backend provenance, including source and revision;
interpretation rejects foreign provenance even when direct producer name and
version are unchanged.

## Live Runtime

The observed production runtime was FreeCAD `1.1.3`, Gmsh `4.15.0`, and
CalculiX `2.22`. The live helper configured `MECHCAD_FREECADCMD`,
`MECHCAD_FREECAD_BIN_DIR`, and `MECHCAD_GMSH`; CalculiX was discovered from
the configured FreeCAD bin directory in the live environment. Runtime
discovery rejected observed FreeCAD `0.21.2` and CalculiX `9.99` in unit
coverage with unavailable status and no trusted provenance. Gmsh discovery
accepted only the observed configured `4.15.0` and rejected probe failure,
unparseable output, and version mismatch.

## Live Capstone Results

The PASS live capstone observed `448` mesh nodes, `191` C3D10 volume elements,
`8` CPS6 boundary elements, `448` displacement samples, `448` stress samples,
and `13` reaction samples. The source snapshot remained revision `2` with
state hash
`sha256:362145e3d009ea94b8c1a3e565ee405ea3c2ebff38d263cc19a44fe24b620fb8`
before and after both execution and evaluation.

## Focused Failure Tests

The fresh focused command was:

```text
py -3 -m pytest tests/unit/test_artifacts.py tests/unit/test_structural_models.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_request.py tests/unit/test_structural_results.py tests/unit/test_structural_runtime.py tests/unit/test_structural_service.py tests/unit/test_structural_validation_observations.py tests/unit/test_production_application.py -q
```

Observed result: `386 passed in 20.57s`.

This command covered runtime mismatch rejection, exact CalculiX 2.22 manifest
and FRD binding, strict `1U` envelope rejection, independently reconstructed
lowered-load application point/area/force/moment/CLOAD semantics, structural
execution and result integrity, production composition, trusted observations,
source mutation protection, solver-provenance persistence, and
forged-evaluation-result rejection cases.

The separate live command was:

```text
py -3 -m pytest tests/integration/test_m11_3_live_structural.py tests/integration/test_m11_4_live_structural.py -q
8 passed in 86.54s (0:01:26)
```

## M9/M10/M11-3 Regression Results

The repository-wide command collected and passed the M9 and M10 integration
regressions, including M9-3, M10-5 system acceptance, and the M11-3 live
structural vertical slice. Runtime-gated tests remained explicitly skipped
where their runtime prerequisites were unavailable. No failure or error was
observed in these regression modules.

## Full Suite Results

The required command was:

```text
py -3 -m pytest tests/
```

Observed output: `1231 passed, 34 skipped, 0 failed, 0 errors` in `712.25s
(0:11:52)`.

Failed tests: `0`.

Errors: `0`.

The command exited successfully. No intermittent test failure occurred in this
fresh full-suite run.

## Files Changed

The final M11-4 review remediation changed these implementation, test, and
documentation files in addition to the preserved earlier worktree changes:

- `src/mechcad_harness/artifacts/storage.py`.
- `src/mechcad_harness/application.py`.
- `src/mechcad_harness/structural/deck.py`.
- `src/mechcad_harness/structural/fakes.py`.
- `src/mechcad_harness/structural/mesh.py`.
- `src/mechcad_harness/structural/models.py`.
- `src/mechcad_harness/structural/results.py`.
- `src/mechcad_harness/structural/runtime.py`.
- `src/mechcad_harness/structural/service.py`.
- `src/mechcad_harness/structural/validation.py`.
- `src/mechcad_harness/backends/freecad.py`.
- `tests/unit/test_production_application.py`.
- `tests/unit/test_structural_pipeline_contracts.py`.
- `tests/unit/test_structural_results.py`.
- `tests/unit/test_structural_runtime.py`.
- `tests/unit/test_structural_service.py`.
- `tests/integration/test_m11_4_live_structural.py`.
- `README.md`.
- `AGENTS.md`.
- `docs/audit/MECHCAD_M11_4_COMPLETION_REPORT.md`.
- `.superpowers/sdd/task-8-report.md`.
- `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`.
- `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`.
- `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`.
- `docs/architecture/MECHCAD_ENGINEERING_WORKFLOW.md`.
- `docs/architecture/MECHCAD_DOCUMENTATION_GAPS.md`.
- `docs/superpowers/plans/2026-08-25-final-review-remediation.md`.

All pre-existing dirty and untracked files were preserved. No commit or
destructive Git operation was performed.

## Remaining Limitations

- The capability is source-bound, single-body, linear-static, small-deformation, and isotropic linear-elastic.
- The analytical validator is the fixed rectangular cantilever policy, not a general structural validation framework.
- Stress is CalculiX extrapolated nodal stress, not integration-point stress.
- The live yield case is `NOT_EVALUABLE`; no global yield or safety claim is made.
- One fixed mesh was used. Mesh convergence was not evaluated or claimed.
- Contact, nonlinear material or geometry, assemblies, fatigue, dynamics, thermal stress, tolerances, optimization, manufacturing approval, and automatic synthesis/selection remain out of scope.

## M11-5 Boundary

M11-4 does not publish accepted structural `Evidence` through `EvidenceStore`.
It does not create a structural acceptance Evidence record, durable accepted
result Evidence, or a mesh-convergence claim. M11-5 remains the boundary for
any future structural Evidence, convergence, repeatability, or broader
acceptance architecture.

## Final Review Closure

The remaining analytical and lowering trust-boundary findings were closed on
2026-08-25:

- Lowered-load reconstruction now requires the deck's C3D10 surface references
  to match exactly the canonical semantic-region face multiset from the
  trusted MSH, so a geometrically plausible but semantically wrong face is
  rejected.
- Analytical reaction force and moment checks recompute totals from trusted
  reaction samples and exact trusted mesh coordinates relative to the declared
  policy reference point. Persisted aggregate summaries are not used as the
  observed values; zero or mismatched samples fail closed.
- Tip displacement integration requires an independently observed semantic
  free-end area. Neither the validator nor its integration helper falls back
  to the policy area.
- M11-3 solver success now requires the produced-log flag and nonempty LOG
  content, preserving `solver_failed` semantics for incomplete output.
- Multi-case interpretation now treats ordered per-case solver manifests as
  authoritative and does not require omitted legacy top-level solver fields.
- Result interpretation pins Gmsh to the trusted identity/version and verifies
  exact source geometry provenance plus MSH backend/direct-producer provenance
  before parsing. Trusted FreeCAD provenance includes source and revision.
- Solver manifests and FRD/DAT/LOG artifact records now carry the exact
  CalculiX backend provenance, and interpretation verifies that provenance plus
  the direct solver producer identity and version.
- The analytical capstone now runs through the explicit production analytical
  validation API with a predeclared policy; the API reparses authoritative MSH
  bytes, freshly interprets the execution manifest, verifies the supplied
  evaluation result hash, and rebuilds FreeCAD/material observations instead of
  trusting caller snapshots.
- Missing analytical displacement, reaction, or related result fields produce
  deterministic `NOT_EVALUABLE`; present wrong values remain `FAIL`.
- The accepted full-suite pass is recorded above; M9-3 executed successfully in
  the current runtime.

Adversarial regressions cover wrong semantic faces, forged/zero reaction
samples and summaries, missing observed free-end area, incomplete LOG output,
foreign same-name/version Gmsh and FreeCAD provenance, forged analytical inputs,
foreign same-name/version CalculiX provenance and forged analytical result
hashes, omitted analytical result fields, and ordered multi-case
interpretation. Focused structural units, live M11-3/M11-4 tests, full-suite
result, and a clean `compileall -q` run are recorded from the final review
verification. The final full suite is `1231 passed, 34 skipped, 0 failed, 0
errors`. Scoped and touched-untracked diff checks are recorded in the
accompanying task report.

## Post-Closure Authority Hardening

The subsequent Important-finding remediation closed three trust-boundary gaps
without changing the bounded capability claim:

- `evaluate_structural_analysis()` derives the deterministic JSON execution
  manifest artifact ID, reloads its persisted bytes through `ArtifactStore`,
  rehashes and validates the artifact metadata, parses the durable manifest,
  and compares it to both the supplied manifest and request binding before
  invoking result interpretation. Forged in-memory manifests are rejected.
- M11-3 now requires the source STEP artifact's `BackendProvenance` to be
  present and exactly equal to the composed FreeCAD geometry runtime
  provenance before execution can publish a successful manifest. Missing or
  foreign provenance leaves the source artifact unchanged and produces no
  success manifest.
- `ArtifactStore` now rejects lookup-ID mismatches, unsafe or escaping relative
  paths, wrong project/run/type metadata, producer media mismatches, and any
  size or SHA-256 byte mismatch. Source, mesh, deck, FRD, DAT, LOG, and
  durable manifest reads use this verified boundary.

The remediation red-to-green adversarial tests cover forged manifests, source
provenance absence/foreign identity, metadata lookup identity, relative-path
traversal, and expected type/hash mismatches. Live M11-3/M11-4 verification
passed `8 tests`; the full suite passed `1231 tests` with `34` runtime-gated
skips. No commit or destructive Git operation was performed.

## Post-Closure Artifact Publish-Path Hardening

The remaining Important finding in the ArtifactStore publication boundary is
closed without changing M11-4 durability scope or the bounded structural
capability claim.

- `ArtifactStore.publish()` now validates the artifact directory and both
  resolved publication paths before directory creation, after directory
  creation, and immediately before each atomic write.
- Validation requires resolved paths to remain strictly contained by the
  workspace and rejects existing symlink, junction, or Windows reparse-point
  components, including dangling or in-workspace symlink targets. Existing
  path checks use `lexists()` so dangling links cannot be mistaken for absent
  files.
- Publication remains the existing `mkstemp` in the artifact directory,
  flushed and `fsync()`ed, followed by `os.replace()` flow. No fresh-process
  directory durability or recovery protocol was added.
- Portable adversarial tests cover symlinked artifact directories, existing
  artifact and metadata symlink targets, and dangling artifact symlinks; tests
  skip only when the runtime cannot create symlinks.

Verification for this remediation:

- `tests/unit/test_artifacts.py`: `33 passed`.
- Structural and production focused unit set, including ArtifactStore:
  `386 passed`.
- Live M11-3/M11-4 coverage: `8 passed`.
- Full repository suite: `1231 passed, 34 skipped`.
- `py -3 -m compileall -q src/mechcad_harness tests`: passed.
- Scoped `git diff --check`: passed.

The full `py -3 -m pytest tests/` run completed successfully in `712.25s`.
Generated project trees and `err.txt` were not edited, and no commit or
destructive Git operation was performed.
