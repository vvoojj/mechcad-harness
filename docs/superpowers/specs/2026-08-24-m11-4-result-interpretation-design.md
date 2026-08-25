# M11-4 CalculiX Result Interpretation Design

**Date:** 2026-08-24
**Status:** approved for implementation; no commit requested.

## Goal

Interpret only successful, source-bound M11-3 CalculiX executions into typed
physical fields and evaluate existing structural criteria as `pass`, `fail`, or
`not_evaluable`. This milestone adds neither accepted structural Evidence nor a
mesh-convergence claim.

## Current CalculiX 2.22 Output Contract

The installed production execution was inspected through the current M11-3
integration fixture. The FRD is fixed-width text and declares:

- `DISP` with `D1`, `D2`, `D3`: node-indexed displacement components in mm.
- `STRESS` with `SXX`, `SYY`, `SZZ`, `SXY`, `SYZ`, `SZX`: node-indexed,
  CalculiX extrapolated nodal stress components in MPa.
- `PSTEP` and `100CL` headers describing the solver step/result block.

The existing DAT output contains `U` only for fixed support nodes. M11-4 will
request `RF` only when reactions are requested, then pin the observed CalculiX
2.22 DAT reaction header, node/DOF, and numeric record contract in parser
fixtures before admitting it.

No stress value is described as integration-point or generic element stress.
`von_mises` is calculated from the parsed extrapolated nodal tensor and retains
that representation. Duplicate samples are preserved only when the actual
format supplies a stable distinguishing identity retained in the typed result
and hash. A duplicate identical sample identity is rejected; samples are never
silently averaged.

## M11-3 Per-Case Compatibility Correction

M11-1 and M11-2 require ordered independent load cases. The current M11-3
service incorrectly combines selected cases into one unnamed solver step. M11-4
will correct this narrowly:

```text
selected_load_case_ids (ordered)
  -> one request-level verified mesh artifact
  -> one deterministic deck per load_case_id using that mesh
  -> one constraint preflight and CalculiX execution per case
  -> one INP/FRD/DAT/LOG artifact partition per case
  -> one per-case execution manifest
  -> one request-level manifest preserving that order
```

The source binding, verified geometry and mesh bytes, rigid-body preflight,
solver discovery/provenance, and M11-3 stage failure behavior remain unchanged.
A per-case manifest references the exact request-level mesh artifact ID/hash.
Artifacts retain direct producer/input/byte bindings; per-case manifests bind
their artifacts; the request-level manifest binds the ordered per-case manifest
identities/hashes. This layering must remain non-circular. A failing selected
case produces a failed request-level manifest with ordered case statuses and
available diagnostics, but no typed analysis result or criterion evaluation.
No envelopes, combinations, or worst-case selection are introduced.

## Result Trust Boundary

`StructuralResultInterpreter` receives a successful request-level execution
manifest and resolves artifacts only through `ArtifactStore`. Before any parser
is called it verifies:

- manifest success, project/source revision/state binding, definition ID/hash,
  request hash, and trusted CalculiX identity/version;
- the per-case load-case ID, mesh artifact/hash, deck artifact/hash, and source
  FRD/DAT references;
- each artifact metadata record, type, bound revision/state, manifest hash, and
  rehashed bytes; and
- mesh nodes and elements against parsed identities.

Manifest mismatch, artifact absence/tampering, an unrequested-but-required
field absence, malformed bytes, an unknown mesh identity, or unsupported FRD or
DAT variant is a result-integrity failure. It produces no typed result and no
criterion status.

## Result Model And Evaluation

Immutable result models bind all local node, element, and result-location IDs
to an exact mesh hash. The request-level result binds request, definition,
source, execution-manifest, parser identities, raw-byte hashes, and per-case
results. Deterministic result hashes exclude run IDs, timestamps, PIDs, and
temporary paths.

Each case records:

- nodal displacement vectors and maximum magnitude with node coordinate;
- extrapolated-nodal stress tensors and tensor-derived von Mises extrema;
- node reactions, total reaction force, total moment about an explicit reference
  point, and applied-versus-reaction equilibrium diagnostics; and
- field representation, units, parser/solver identities, and request coverage.

Existing `MaximumDisplacementCriterion` and `YieldSafetyFactorCriterion` remain
canonical authority. Evaluation reuses `evaluate_material_authority_policy` for
exact consumed properties. A criterion is `not_evaluable` only for a supported
semantic/authority gap, including missing/disallowed material properties,
unrequested fields, or unsupported stress representation/domain. Result
corruption never becomes `not_evaluable`. Aggregate status is `fail` if any
criterion fails, otherwise `not_evaluable` if any criterion is not evaluable,
otherwise `pass`; an empty criterion set is `not_evaluable`.

Stress/yield PASS or FAIL requires requested stress, an explicitly supported
field representation, an unambiguous assessment domain, and eligible material
authority. No singularity filtering, arbitrary peak removal, or averaging is
allowed.

Global extrema are observable summaries only. Every criterion resolves and
evaluates its canonical assessment region/domain against the exact mesh group;
it never substitutes a global result. A missing or ambiguous domain is
`not_evaluable` with a deterministic reason.

## Analytical Validation

One immutable, versioned policy is declared before its live execution. It uses a
source-bound rectangular cantilever with explicit dimensions, material, end
resultant, fixed/free semantic regions, fixed mesh specification, a free-end
area-weighted average transverse displacement metric defined as the
finite-element surface integral `integral_A N_i u_transverse dA / A`, an
explicit fixed-section moment reference point, Euler-Bernoulli reference
equation, and predeclared displacement/reaction tolerances.

The validator reports declared inputs, expected/observed values, absolute and
relative errors, tolerance, and status for geometry, material, load, tip
displacement, reaction force, and reaction moment. It is a physical-pipeline
validation result, separate from the engineering criteria. A deterministic
wrong-result test proves it can fail. Agreement on one fixed mesh does not claim
mesh convergence.

For CPS6 surface integration, the three corner shape functions integrate to zero
and each midside shape function contributes `A/3`; this preserves a constant
displacement exactly. The analytical transverse sign convention is signed
applied-force direction: the declared applied force, expected Euler-Bernoulli
displacement, and observed transverse displacement use the same signed axis.
Geometry and material observations must independently bind to the trusted source
definition and execution geometry artifact; absent observations are
`NOT_EVALUABLE`, never analytical PASS.

## Tests And Live Evidence

Tests cover strict FRD/DAT fixtures, malformed/truncated/nonfinite data,
unknown mesh identities, actual artifact tampering before parser invocation,
manifest/request/mesh/load-case mismatches, von Mises mathematics, material
authority outcomes, criterion PASS/FAIL/NOT_EVALUABLE, and analytical failure.

The live capstone uses the existing `ProductionApplication` path with FreeCAD
1.1.3, Gmsh 4.15.0, and CalculiX 2.22. It demonstrates: analytical cantilever
validation and a displacement PASS; a valid stricter displacement FAIL; and a
valid stress criterion NOT_EVALUABLE due to missing or disallowed yield
authority. At least one real stress field is parsed, but that alone makes no
global safety claim.

## Boundaries

M11-4 remains linear-static, small-deformation, isotropic linear-elastic,
single-homogeneous-solid analysis with modeled rigid supports. It excludes
contact, assemblies/connections, nonlinear material or geometry, buckling,
fatigue, dynamics, thermal stress, manufacturing tolerances, optimization, and
mesh-convergence verification. It records known stress singularity limitations.

No M11-5 `EvidenceStore` structural acceptance, fresh-process durability
closure, repeatability hardening, or mesh-convergence architecture is added.
