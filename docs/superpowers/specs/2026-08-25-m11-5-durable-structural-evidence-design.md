# M11-5 Durable Structural Evidence Design

**Date:** 2026-08-25
**Status:** approved for implementation planning; no commit requested.

## Goal

M11-5 closes the durable trust layer above the accepted M11-4 bounded
single-body linear-static result path. It proves that a later fresh process can
reload one immutable structural evidence record, verify its bytes and all
authoritative dependencies, reconstruct the exact accepted engineering outcome,
and distinguish internal integrity from currentness.

It also introduces bounded, explicitly requested repeatability and
mesh-convergence evidence. It does not redesign M11-2 authority, M11-3
execution, M11-4 interpretation/criteria/analytical validation, physics, or
result representation.

## Scope

The target chain is:

```text
trusted M11-4 execution/result/verification/analytical validation
  -> verify durable manifest and raw ArtifactStore bytes
  -> construct one complete immutable StructuralEvidencePayload
  -> semantic hash
  -> existing EvidenceStore atomic persistence
  -> fresh-store reload and verification
  -> PASS / FAIL / NOT_EVALUABLE recovered unchanged
```

The same evidence architecture supports a bounded explicitly declared
repeatability comparison and a three-or-more-level displacement convergence
study. There is no automatic refinement, generic mesh-isomorphism algorithm,
global stress convergence claim, structural-safety claim, or M11-6 system
acceptance.

## Evidence Model

`Evidence` gains one optional typed `structural_evidence_payload` field. This is
an additive model-only dependency: the generic Evidence model must not import
or depend on structural services, verifier code, runtime discovery, or
`ProductionApplication`. Existing non-structural Evidence records remain
valid without that field.

`StructuralEvidencePayload` is frozen, versioned as `structural-evidence@1`,
and contains the complete machine-verifiable structural conclusion:

- source: project ID, source revision/state hash, definition ID/hash, full
  reconstructed request semantics and request hash;
- geometry: target body, STEP artifact ID/hash, FreeCAD direct-producer
  provenance, region-map hash, resolver identity/version;
- mesh: mesh specification hash, semantic mesh manifest/counts/types,
  MSH artifact ID/hash, Gmsh direct-producer provenance;
- execution: explicit durable execution-manifest artifact ID/hash and complete
  typed manifest; ordered per-load-case case-manifest, deck semantic hash,
  INP/FRD/DAT/LOG IDs/hashes, execution status, and CalculiX direct-producer
  provenance;
- result: complete `StructuralAnalysisResult`, result hash, parser/interpreter
  identity, units, field representation, requested coverage, and physical
  summaries;
- verification: complete `StructuralVerificationResult`, criterion outcomes,
  deterministic reasons, observed/allowable values, units, fields/domains,
  consumed material properties, and material-authority findings;
- optional complete `StructuralAnalyticalValidationResult`, including the full
  immutable analytical policy semantics, policy hash, typed trusted geometry and
  material observations, expected/observed values, errors, tolerances, status,
  and validation hash;
- optional repeatability or convergence payloads; ordinary evidence explicitly
  carries `mesh_convergence_status=NOT_EVALUATED`;
- direct artifact producer provenance plus a distinct aggregate pipeline
  provenance chain.

The payload semantic hash excludes `semantic_hash` itself and all volatile
storage/correlation fields, including EvidenceStore path, timestamp, PID, temp
directory, run directory, JSON whitespace, and `run_id`. It binds the complete
remaining canonical payload, including source/request identities, artifacts,
results, verification, analytical validation, policies, and provenance.
Unsupported structural payload schema versions fail closed. A changed mesh,
criterion, material authority, result, validation policy, or convergence study
creates new immutable evidence; no Evidence record is updated in place.

## Publication

`ProductionApplication.publish_structural_evidence(...)` is the sole trusted
publication operation. It does not make caller-supplied result objects,
statuses, values, hashes, manifests, raw bytes, provider identities, material
snapshots, or analytical observations authoritative.

Publication order is exact:

```text
verify all dependencies
  -> construct complete payload
  -> compute semantic hash
  -> atomically persist one Evidence record
  -> fresh-store reload/self-verify
  -> return success
```

Before persistence it reloads the explicitly bound durable execution-manifest
artifact through `ArtifactStore.read_verified_strict`, verifies its bound
artifact ID/hash/type/scope/metadata/bytes, and parses its typed manifest. It
then independently verifies all source STEP, MSH, INP, FRD, DAT, LOG, and
manifest bytes through ArtifactStore before any result parser consumes them.

The service derives the canonical definition from the bound immutable
`StateManager` revision. It reconstructs the complete typed
`StructuralAnalysisRequest` from the durable evidence semantics, recomputes its
hash, validates it against that canonical definition, and requires exact source
revision/state binding. It reconstructs M11-4 result and criterion verification
from the durable manifest/artifacts/definition without rerunning a solver.

Analytical validation is persisted with sufficient typed policy and observation
data to recompute its deterministic equations/comparisons without re-realizing
the STEP in FreeCAD. Material-authority findings are re-evaluated against the
immutable bound definition during verification. A result-integrity failure,
failed solver, stale source at execution time, untrusted provider, malformed
manifest, or altered artifact prevents accepted evidence publication. Trusted
engineering PASS, FAIL, and NOT_EVALUABLE results are all publishable.

A failed post-publish self-verification is never reported as accepted evidence
and never triggers in-place mutation or repair.

## Verification And Currentness

`StructuralEvidenceVerifier` is a read-only structural service. Given an
evidence ID, it creates no solver/CAD subprocess and does not require FreeCAD,
Gmsh, or CalculiX to be currently installed. It loads Evidence through
EvidenceStore, verifies its structural schema/version/hash, loads the exact
immutable source revision and state hash, reconstructs the request from the
payload, verifies the explicit manifest artifact binding, re-verifies all raw
artifacts, reconstructs typed result/verification/analytical validation, and
checks direct and aggregate provenance.

Integrity, engineering outcome, and currentness are separate:

- internally valid evidence preserves its `PASS`, `FAIL`, or `NOT_EVALUABLE`
  outcome;
- missing/corrupt evidence, historical revision, manifest, artifact,
  provenance, result, verification, or validation is an integrity failure and
  never a criterion NOT_EVALUABLE outcome;
- currentness is `CURRENT`, `STALE_RELATIVE_TO_CURRENT_STATE`, or
  `CURRENTNESS_UNAVAILABLE` when the current pointer cannot be established.

Canonical state advancing never corrupts or invalidates historical evidence.
Any dependency graph addition may affect only selection/cache freshness of
current structural evidence; historical evidence remains verifiable against its
bound revision. Runtime compatibility is a future reproduction/new-execution
concern, not historical integrity verification.

Fresh-process capstones must create fresh `StateManager`, `ArtifactStore`,
`EvidenceStore`, and `StructuralEvidenceVerifier` instances. They reload only
durable IDs and immutable source revisions and may not reuse trusted in-memory
M11-4 records, manifests, or service caches.

## Repeatability

`StructuralRepeatabilityPolicy` is frozen and versioned as
`structural-repeatability@1`. It declares source/definition/request/provider
identity requirements, semantic-result summaries to compare, absolute/relative
tolerances, and explicit treatment of raw-byte and incidental mesh-numbering
differences.

The M11-5 live policy is constructed and hashed before either compared run. It
does not assume node/element identifiers or raw MSH/FRD/DAT bytes are stable and
does not implement generic nodal-field correspondence. It compares declared
semantic summaries only: FE-consistent free-end displacement, maximum
displacement, explicitly represented extrapolated-nodal von-Mises summary,
reaction force/moment, criterion results, and analytical validation results.

`REPEATABLE`, `NOT_REPEATABLE`, and `INTEGRITY_FAILURE` remain distinct. Policy
runtime identities constrain execution of the study; later verification only
checks persisted provenance and requires no installed runtime.

## Mesh Convergence

`StructuralMeshConvergenceStudy` is frozen and versioned as
`structural-mesh-convergence@1`. It binds an ordered unique sequence of at
least three mesh specifications, one load case, a declared displacement metric
and semantic domain, epsilon, threshold, level bound, and required runtime
identities. The initial supported metric is the existing FE-consistent
cantilever free-end transverse-displacement integral.

Each level first produces normal complete structural evidence:

```text
mesh level 1 -> Evidence E1
mesh level 2 -> Evidence E2
mesh level 3 -> Evidence E3
```

The convergence evaluator independently verifies ordered `[E1, E2, E3]`, then
calculates:

```text
relative_change_i = abs(q_i - q_(i-1)) / max(abs(q_i), epsilon)
```

It records each mesh specification/hash/count, response value, optional
analytical reference/error, and previous-level change. A separate immutable
convergence-study Evidence record binds the complete result and ordered level
evidence IDs/hashes.

Outcomes are exactly `CONVERGED`, `NOT_CONVERGED`, `NOT_EVALUABLE`, and
`INTEGRITY_FAILURE`. `NOT_EVALUABLE` means otherwise trusted level evidence
cannot provide the declared metric/domain. Solver failure, corrupted data,
source mismatch, incomplete level, or failed referenced evidence is always
`INTEGRITY_FAILURE`. `CONVERGED` is limited to this exact response metric,
source, load case, mesh sequence, and policy; it is not a global marker or
stress-convergence claim.

## Testing And Documentation

Tests cover payload canonicalization/version handling and old Evidence
compatibility; PASS/FAIL/NOT_EVALUABLE fresh reload; no publication on integrity
failure; payload/artifact tampering; cross-project/revision/case/criterion/
material/policy replay; historical validity/currentness; fake-provider
isolation; runtime-independent historical verification with unavailable or
incompatible current runtime discovery; repeatability status; and convergence
sequence/outcome validation.

Live capstones use FreeCAD 1.1.3, Gmsh 4.15.0, and CalculiX 2.22 for PASS, FAIL,
NOT_EVALUABLE, historical currentness, predeclared two-run repeatability, and a
predeclared three-level displacement convergence study. The completion report
records exact policy identities, scoped metrics, raw artifact/result bindings,
runtime versions, capstone measurements, regression/full-suite commands, and
remaining limitations.

## Boundaries

M11-5 preserves the bounded source-bound single-solid linear-static scope.
Stress remains `calculix_extrapolated_nodal_stress`; no singularity filtering,
global yield/safety conclusion, automatic mesh independence, manufacturing
approval, assembly structural analysis, nonlinear analysis, fatigue, dynamics,
thermal stress, optimization, or automatic refinement is added.

M11-6 remains responsible for final system-wide acceptance. M11-5 may report
only `M11_5_DURABLE_STRUCTURAL_EVIDENCE_VERIFIED` or
`M11_5_NEEDS_FIXES`.
