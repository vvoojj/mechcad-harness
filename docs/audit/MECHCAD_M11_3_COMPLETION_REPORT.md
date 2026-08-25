# MechCAD M11-3 Structural Mesh/Solver Foundation - Completion Report

**Date:** 2026-08-24
**Disposition:** `M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED`

## Objective

M11-3 establishes a narrow, source-bound production execution foundation for
one valid single-solid linear-static structural definition. It proves trusted
geometry admission, semantic region resolution, C3D10 meshing, deterministic
deck construction, rigid-body preflight, CalculiX execution, and durable raw
execution artifacts. It does not interpret solver fields or decide engineering
acceptance.

## Scope And Non-Goals

In scope:

- one valid source-bound STEP artifact and one valid solid;
- semantic planar face regions, fixed translational support, surface pressure,
  resultant force, and body acceleration deck lowering;
- second-order tetrahedral C3D10 volume mesh with semantic surface groups;
- raw mesh, deck, solver output, log, and execution-manifest persistence.

Out of scope:

- `StructuralAnalysisResult`, stress/displacement interpretation, or safety
  factor calculation;
- acceptance-criterion PASS/FAIL and structural Evidence creation;
- mesh convergence, contact, assemblies, nonlinear material behavior, and
  multi-body analysis;
- M11-4 engineering acceptance evaluation.

## Runtime And Provenance Model

`ProductionApplication.create(...)` composes only trusted live providers:

- FreeCAD 1.1.3 geometry realization;
- Gmsh 4.15.0 meshing;
- CalculiX 2.22 solving.

Runtime discovery owns provider identity and version. The execution manifest
and each artifact record the identity/version of the provider actually used.
The service no longer stamps injected fake providers with live identities;
fake identities (`fake-structural-region-resolver@0`, `fake-gmsh@0`,
`fake-deck-builder@0`, and `fake-calculix@0`) remain explicit in fake-backed
execution manifests.

## Production Path Ownership And Binding

`StructuralAnalysisService.execute()` validates the request's project,
revision, state hash, structural definition identity/hash, target body, and
selected load cases before processing geometry. A stale request is rejected
without a run. A definition missing from the frozen source snapshot, or a
definition-hash mismatch, returns a `geometry_rejected` result at the
`definition` stage.

The STEP artifact is resolved through `ArtifactStore.existing_in_project()`.
Its type, revision/state binding, stored SHA-256, request SHA-256, on-disk
size, and bytes must all agree. Artifact tampering is rejected before geometry
realization.

## Semantic Region Resolution

The FreeCAD adapter aggregates every imported STEP shape before applying the
one-solid admission rule, preventing a multi-object import from silently
dropping bodies. It rejects invalid, zero-solid, and multi-solid geometry.

`StructuralRegionResolver` resolves only canonical semantic planar-face
predicates. The M11-3 implementation uses
`planar_face_centroid_axis(axis, side)` with explicit planarity, area,
centroid, and normal tolerances. Canonical structural definitions reject raw
`FaceN`, mesh, Gmsh, and CalculiX identifiers; runtime Gmsh entity IDs are
derived from the resolved BREP geometry and are audit data only.

## Mesh And Deck Requirements

Gmsh creates semantic physical surfaces and one physical volume. The provider
validates nonempty nodes, C3D10 volumes, second-order midside ordering, and
nonempty six-node semantic boundary elements. The persisted `MSH` artifact is
actual MSH2 bytes; the separately persisted `INP` artifact is the deterministic
CalculiX deck. The deck input mesh hash remains the Gmsh INP mesh hash.

The deck accepts only finite values and valid C3D10 references. It emits:

- elastic modulus in MPa and Poisson ratio as a dimensionless ratio;
- density only for body acceleration, converted from `kg/m^3` to `t/mm^3` by
  `1e-12`;
- fixed support node sets with translational DOFs 1 through 3;
- element-face `*SURFACE` / `*DLOAD` pressure;
- consistent C3D10 surface nodal `*CLOAD` resultant-force lowering;
- `*NODE FILE U` and `*NODE PRINT,NSET=<fixed_support>_nodes` so successful
  runs produce both binary FRD and nonempty textual DAT output.

Resultant-force lowering records source force, normalized traction,
resolved-face area, mesh identity, and force/moment conservation errors. The
direct C3D10 test verifies zero force and moment residual within the configured
tolerance.

## Constraint Preflight

Before CalculiX invocation, `ConstraintPreflight` constructs a 6 by 6 Gram
matrix for translations Tx/Ty/Tz and rotations Rx/Ry/Rz acting on constrained
node DOFs. Rank 6 is required. Lower rank returns
`solver_underconstrained` at `constraint_preflight`; the solver is not called.
This is a global rigid-body-mode check only and does not prove absence of local
mechanisms.

## Failure Semantics

The service returns typed fail-closed `StructuralExecutionResult` diagnostics
and never emits a success manifest after a failed stage:

| Condition | Status | Failure stage |
|---|---|---|
| stale source, missing/changed definition, bad STEP binding or bytes | `geometry_rejected` | `source_binding`, `definition`, or `geometry` |
| geometry realization or solid admission failure | `geometry_rejected` | `geometry` |
| semantic region failure | `region_resolution_failed` | `region_resolution` |
| Gmsh failure or malformed mesh | `mesh_failed` | `mesh` |
| invalid deck, region-to-face mapping, or lowering failure | `deck_invalid` | `deck` |
| rigid-body rank below six | `solver_underconstrained` | `constraint_preflight` |
| unavailable CalculiX runtime | `solver_unavailable` | `solver` |
| nonzero/fatal/incomplete solver output | `solver_failed` | `solver` |

Successful classification requires exit code zero, `Job finished`, FRD and DAT
present and nonempty, `produced_log=True`, and a valid nonempty captured LOG.
Failure results carry status and diagnostic text but do not currently persist
separate failure artifacts; they also do not publish a success execution
manifest.

## Test Evidence

| Command | Result |
|---|---|
| `py -3 -m pytest tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_models.py tests/unit/test_structural_request.py tests/integration/test_m11_3_live_structural.py -q` | `151 passed in 14.70s` |
| `py -3 -m pytest tests/unit/test_state_foundation.py tests/unit/test_changes.py tests/integration/test_imported_assembly_bridge.py -q` | `24 passed, 2 skipped in 1.42s` |
| selected M9/M10 live/provenance/acceptance regression suite | `101 passed, 10 skipped in 194.32s` |
| `py -3 -m pytest tests/ -q` | `1021 passed, 34 skipped in 588.00s` |
| `py -3 -m compileall src/mechcad_harness -q` | passed |

Focused tests cover stale/missing/changed source definitions, artifact-byte
tampering, multi-solid admission, region and mesh rejection, malformed C3D10
ordering, invalid deck references, force/moment conservation, preflight rank,
solver unavailable/timeout/incomplete-output semantics, no-solver
underconstraint behavior, fake identity isolation, actual MSH2 bytes, artifact
rehash, and manifest JSON reload.

## Execution And Artifact Evidence

The real vertical slice ran through `ProductionApplication` with FreeCAD 1.1.3,
Gmsh 4.15.0, and CalculiX 2.22 against a source-bound box-cantilever STEP.
It used a `ResultantForce`, resolved fixed/free semantic regions, generated a
C3D10 mesh, achieved rigid-body rank six, and completed CalculiX successfully.

The test reopens every produced artifact through `ArtifactStore`, recomputes
each SHA-256 from the stored bytes, verifies all six artifact types, and reloads
the JSON manifest as `StructuralExecutionManifest`. Successful output contains
exactly one each of `MSH`, `INP`, `FRD`, `DAT`, `LOG`, and `JSON` execution
manifest artifacts. The manifest binds source revision/state, definition and
request hashes, geometry artifact, region-map hash, mesh/deck hashes and
artifacts, solver manifest, raw artifact hashes, and lowered-load provenance.

## M11-4 Boundary

M11-3 establishes trusted execution and raw provenance only. M11-4 may parse
or otherwise interpret successful solver output, evaluate typed structural
criteria, calculate stress/displacement outcomes, and create acceptance
records. None of those actions are implemented or implied by this report.

## Final Disposition

`M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED`

The marker is justified by the final full-suite result, the live production
vertical slice with six durable byte-verified artifacts and manifest reload,
focused failure-contract tests, and M9/M10 predecessor regressions. It does
not change the M8/M9/M10 acceptance baseline and does not assert M11-4
structural acceptance capability.

## Final Review Closure

The remaining M11-3 trust-boundary findings were closed on 2026-08-25:

- Solver success now requires `produced_log is True` and a strict nonempty
  captured LOG string, in addition to exit code zero, `Job finished`, and
  nonempty FRD/DAT bytes. Missing or empty LOG remains `solver_failed` rather
  than becoming a success.
- Result interpretation rejects any lowered-load deck `*SURFACE` reference
  whose C3D10 element/face pair is not exactly the canonical semantic-region
  face multiset reconstructed from the trusted MSH boundary elements.

Adversarial regressions cover the LOG flag/content gate and wrong C3D10 face
references. Focused structural units pass with `312 passed`; the live M11-3
and M11-4 structural regressions pass with `6 passed`. The final full suite
passes with `1189 passed, 34 skipped` in `597.47s`; `py -3 -m compileall src
tests -q` passes. Scoped and touched-untracked diff checks are recorded in the
task report for this review wave.
