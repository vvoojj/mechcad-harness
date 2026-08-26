# MechCAD M11 Final System Acceptance

**Date:** 2026-08-26
**Disposition:** `M11_FULLY_CLOSED_LIVE_VERIFIED`

## Final Disposition

`M11_FULLY_CLOSED_LIVE_VERIFIED`

The complete M11 structural architecture (M11-1 through M11-6) is live-verified
as one coherent production system, from canonical engineering authority through
real structural execution, interpretation, engineering evaluation, analytical
validation, durable Evidence, fresh verification, repeatability, and bounded
mesh convergence. No new physics, solver capability, evidence architecture, or
analysis semantics were introduced in M11-6. The distinct-mesh anti-regression
is closed: declared mesh levels produce genuinely distinct realized meshes.

## Accepted Predecessor Milestones

- `M10_FULLY_CLOSED_LIVE_VERIFIED`
- `M11_1_STRUCTURAL_FEA_ARCHITECTURE_READY`
- `M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED`
- `M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED`
- `M11_4_REAL_FEA_RESULT_ANALYTICAL_VALIDATION_VERIFIED`
- `M11_5_DURABLE_STRUCTURAL_EVIDENCE_VERIFIED`

## M11 System Scope

M11 delivers source-bound single-solid linear-static structural analysis through
trusted semantic geometry regions, real C3D10 meshing, deterministic load
lowering, rigid-body constraint preflight, real CalculiX execution, trusted
displacement/stress/reaction interpretation, engineering PASS/FAIL/NOT_EVALUABLE
evaluation, analytical validation, durable structural Evidence, fresh historical
verification, semantic repeatability comparison, and explicitly bounded
displacement mesh-convergence studies.

## Architecture Traceability

The accepted M11 production chain:

```
canonical DesignState
    ->
StructuralAnalysisDefinition
    ->
source-bound StructuralAnalysisRequest
    ->
immutable source revision/state hash
    ->
trusted source STEP / realized solid
    ->
semantic BREP regions
    ->
real Gmsh C3D10 mesh
    ->
deterministic CalculiX deck
    ->
rigid-body constraint preflight
    ->
real CalculiX 2.22 execution
    ->
byte-verified MSH / INP / FRD / DAT / LOG
    ->
strict FRD / DAT interpretation
    ->
typed displacement / extrapolated-nodal stress / reactions
    ->
tensor-derived von Mises
    ->
engineering PASS / FAIL / NOT_EVALUABLE
    ->
analytical cantilever validation
    ->
immutable StructuralEvidencePayload
    ->
EvidenceStore persistence
    ->
fresh-store verification
    ->
repeatability / bounded convergence where explicitly requested
```

Every arrow has an accepted implementation boundary and test/evidence reference.

## Canonical Authority

- `DesignState` is the only canonical engineering source of truth.
- Agents do not mutate structural authority directly.
- FreeCAD/Gmsh/CalculiX are computational/derived.
- `StructuralAnalysisRequest` is source-bound execution semantics, not hidden
  canonical authority.
- Material properties retain property-specific authority.
- No solver output is promoted into canonical state automatically.
- No Evidence record mutates `DesignState`.

## Source And Material Binding

End-to-end binding verified for:
- `project_id`
- `source_revision`
- `source_state_hash`
- `structural definition ID/hash`
- `request hash`
- `geometry artifact ID/hash`
- `target body`
- `selected ordered load cases`

A stale or foreign source fails closed before trusted execution/evidence
acceptance. Historical Evidence remains valid for its bound old revision and is
not corrupted merely because current state advances.

Elastic properties consumed by execution are source-bound. Criterion-specific
material properties are independently evaluated. Missing/disallowed yield
authority produces NOT_EVALUABLE where appropriate. Material authority
participates in verification/evidence identity. No material fallback exists.

## Semantic Region Boundary

Structural regions remain semantic geometry regions resolved from accepted
source-program features and controlled geometric predicates, not raw unstable
topology IDs. Raw `FaceN`-style authority is rejected by the M11-2 contract and
remains unused in production. Trusted BREP/Gmsh bridging is bound to exact source
geometry.

## Mesh And Deck Pipeline

`MeshSpecification.global_target_size_mm` affects the actual Gmsh mesh. The
authoritative flow is:

```
one generated MSH
    ->
parse that exact MSH
    ->
lower CalculiX INP from that exact mesh
```

No independent remesh for the deck occurs. MSH Evidence and solver mesh are the
same realized mesh.

## Solver Trust Boundary

The exact accepted runtime contract is verified:
- FreeCAD 1.1.3
- Gmsh 4.15.0
- CalculiX 2.22

Fake or foreign same-name/version providers are rejected as live production
authority. Runtime discovery owns provider identity and version.

## Result Interpretation

Strict parsing distinguishes:
- DISPLACEMENT: node-indexed displacement components
- STRESS: CalculiX extrapolated nodal stress (`calculix_extrapolated_nodal_stress`)
- REACTIONS: trusted parsed translational support reactions

Stress is explicitly represented as `calculix_extrapolated_nodal_stress`. It is
not relabeled as integration-point stress, generic physical maximum stress, or
globally converged stress.

Von Mises is recomputed from the parsed stress tensor using the accepted tensor
equation. The scalar result inherits the same extrapolated-nodal representation.

## Engineering Verification Semantics

The accepted distinction:
- PASS: valid result + evaluable criterion + requirement satisfied
- FAIL: valid result + evaluable criterion + requirement violated
- NOT_EVALUABLE: valid trusted physical result, but insufficient accepted
  semantic or authority basis to decide the criterion

Integrity or solver failures never become NOT_EVALUABLE.

## Analytical Validation

The rectangular cantilever analytical validation is re-run through the
production path. Observed values:
- Expected tip displacement: `-2.2857142857142856 mm`
- Observed FE-consistent free-end integral: `-2.250974166666667 mm`
- Relative error: `1.52%` (within declared 20% tolerance)
- Reaction force equilibrium residual: below declared absolute ceiling
- Reaction moment equilibrium residual: below declared absolute ceiling

Geometry observations, material inputs, resultant load, FE-consistent free-end
displacement metric, expected Euler-Bernoulli displacement, reaction force,
reaction moment, predeclared tolerances, and validation hash are all verified.

## Durable Structural Evidence

M11-5 uses the existing `EvidenceStore` only. No parallel `StructuralEvidenceStore`,
FEA database, or hidden result cache exists. Structural Evidence is one immutable
versioned typed payload with raw solver/mesh bytes remaining in `ArtifactStore`.

## Fresh Historical Verification

A fresh verifier can recover trusted historical Evidence with fresh
`StateManager`, `ArtifactStore`, `EvidenceStore`, and `StructuralEvidenceVerifier`
using only durable identities/storage. Ordinary historical verification does not
launch FreeCAD/Gmsh/CalculiX.

All three currentness semantics are verified:
- CURRENT
- STALE_RELATIVE_TO_CURRENT_STATE
- CURRENTNESS_UNAVAILABLE

Currentness is independent from Evidence integrity.

## Tamper And Replay Protection

Adversarial coverage is green for:
- Evidence payload tamper
- Execution manifest tamper
- MSH tamper
- INP tamper
- FRD tamper
- DAT tamper
- LOG tamper
- STEP tamper

Replay/substitution across project, revision/state, load case, criterion,
material authority, analytical policy, and provider/parser identity fails
closed. No self-healing/re-hashing behavior exists.

## Repeatability

The predeclared real repeatability case is re-run. Policy exists and is hashed
before either compared live execution. Comparison remains over declared semantic
summaries rather than raw MSH equality, raw FRD equality, node ID equality, or
element ID equality. Expected valid outcomes: REPEATABLE, NOT_REPEATABLE,
INTEGRITY_FAILURE.

## Mesh Convergence

The real bounded three-level convergence study is re-run. The accepted predeclared
ordered mesh sequence and displacement response metric are used. Preserved:
- distinct realized meshes
- independently published normal Evidence per level
- independently verified level Evidence
- ordered level identities/hashes
- response values
- relative changes
- convergence policy hash
- separate convergence-study Evidence
- unchanged level Evidence after study publication

Allowed study outcomes: CONVERGED, NOT_CONVERGED, NOT_EVALUABLE, INTEGRITY_FAILURE.

## Distinct-Mesh Regression Closure

The previous M11-5 closure exposed a real defect where 10.0 mm, 7.5 mm, and 5.0 mm
all produced the same MSH bytes. The correction is retained and verified in M11-6.

Live capstone per-level observations:

| target mesh size (mm) | MeshSpecification hash | MSH artifact ID | actual MSH SHA-256 | nodes | C3D10 volume elements | boundary elements | response (mm) |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| 10.0 | `sha256:42cef9a8...` | `STRUCT-MSH-28f6697d...` | `sha256:66730657...` | 955 | 430 | 16 | -2.261627083333334 |
| 7.5 | `sha256:0cf50ed8...` | `STRUCT-MSH-3b7927bf...` | `sha256:e7134952...` | 1591 | 706 | 28 | -2.2642747222222224 |
| 5.0 | `sha256:e20ac870...` | `STRUCT-MSH-8380e662...` | `sha256:efc65cf9...` | 3964 | 2003 | 44 | -2.267595845655101 |

All three specification hashes, MSH IDs, MSH byte hashes, semantic/manifest
hashes, node counts, C3D10 counts, boundary counts, run IDs, request hashes,
execution-manifest hashes, and complete produced-artifact ID sets are unique.
Each deck artifact is input-bound to its level MSH hash; each FRD and DAT
artifact is input-bound to its level deck hash. No ArtifactStore reuse, request
caching, manifest reuse, mesh-artifact reuse, or solver-result reuse exists
across levels.

## Final Live System Capstone

One coherent final production capstone demonstrates:
- immutable source revision
- canonical StructuralAnalysisDefinition
- trusted StructuralAnalysisRequest
- real source geometry
- real Gmsh C3D10
- real CalculiX
- trusted parsed fields
- engineering verification
- analytical validation where applicable
- durable Evidence publication
- fresh-store verification

The live M11-5 convergence capstone (which exercises the full chain) completed
with `1 passed in 193.25s`. The complete M11-3/M11-4/M11-5 live subset
completed with `14 passed in 716.26s`.

## Source Immutability

Source revision/state hash remains unchanged before execution, after execution,
after interpretation, after Evidence publication, and after Evidence
verification. Structural computation/evidence does not mutate canonical design
state.

## Runtime Provenance

The live production toolchain is real FreeCAD `1.1.3`, Gmsh `4.15.0`, and
CalculiX `2.22`. No runtime-gated skip occurred for any M11-6 live test.

## Regression Results

| Test suite | Result |
|---|---|
| Focused structural unit suite (520 tests) | `520 passed in 44.97s` |
| Live M11-3/M11-4/M11-5 (14 tests) | `14 passed in 716.26s` |
| M9/M10 predecessor regressions (149 tests) | `140 passed, 9 skipped in 30.19s` |

The focused structural suite covers: structural authority/models, request/source
binding, runtime discovery, semantic regions/mesh, deck/load lowering, structural
execution, result parsing, analytical validation, ArtifactStore, structural
Evidence models/verifier, repeatability, convergence, and ProductionApplication.

The M9/M10 predecessor regressions cover: M10-1 continuous proof, multi-joint
kinematics, multi-joint collision sweep, multi-joint continuous clearance, M9
live FreeCAD, trusted imported artifact, live mixed assembly, and trusted
analysis provenance.

## Full Suite Results

```text
py -3 -m pytest tests/ -q
1371 passed, 34 skipped in 1405.17s (0:23:25)
```

- Passed: 1371
- Skipped: 34
- Failed: 0
- Errors: 0

```text
py -3 -m compileall -q src/mechcad_harness tests
```

Exit code: 0 (passed).

```text
git diff --check
```

No actual diff diagnostics (trailing whitespace, conflict markers). Only
pre-existing CRLF normalization warnings in `.superpowers/sdd/` files, unrelated
to M11-6.

## Accepted Capability Claim

MechCAD can perform source-bound single-solid linear-static structural analysis
through trusted semantic geometry regions, real C3D10 meshing, deterministic
load lowering, rigid-body constraint preflight, real CalculiX execution, trusted
displacement/stress/reaction interpretation, engineering PASS/FAIL/NOT_EVALUABLE
evaluation, analytical validation, durable structural Evidence, fresh historical
verification, semantic repeatability comparison, and explicitly bounded
displacement mesh-convergence studies.

## Remaining Limitations

- source-bound single homogeneous solid
- linear static
- small deformation
- isotropic linear elastic
- fixed supports
- currently supported load semantics only
- C3D10 current meshing path
- stress = CalculiX extrapolated nodal stress
- stress singularity limitations
- no contact
- no structural assembly connections
- no nonlinear analysis
- no buckling
- no fatigue
- no dynamics
- no thermal stress
- no tolerances
- no automatic optimization
- no automatic synthesis
- bounded explicit mesh-convergence metric only
- `PREACCEPTED_CALLER_CONTRACT_ONLY`
- `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED`
- `run_id` is correlation/storage scope only, not trusted engineering identity
- ordinary M10-3 discrete sweeps retain `continuous_path_verified = False`
- M10-4 proves only the explicitly requested path, not an entire
  configuration-space region

## Final M11 Closure

`M11_FULLY_CLOSED_LIVE_VERIFIED`

The complete M11 structural architecture is live-verified as one coherent
production system. No unresolved Important/Critical acceptance finding remains.
No new M11 semantics were introduced. No M9/M10 predecessor behavior was broken.
The full repository test suite has 0 failures/errors. Compile verification
passes. The distinct-mesh anti-regression is closed.

## Worktree Preservation

The M11-6 scoped diff is clean and contains only the expected documentation
changes. Pre-existing unrelated/untracked worktree artifacts remain untouched.

Modified files (all documentation):
- `AGENTS.md`
- `README.md`
- `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`
- `docs/architecture/MECHCAD_DOCUMENTATION_GAPS.md`
- `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`
- `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`

New file:
- `docs/audit/MECHCAD_M11_SYSTEM_ACCEPTANCE.md`

No unexpected M11-6 worktree changes were found. No commit, push, reset, stash,
clean, checkout, revert, discard, or deletion was performed.
