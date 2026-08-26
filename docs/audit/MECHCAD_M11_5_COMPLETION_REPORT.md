# MechCAD M11-5 Durable Structural Evidence Completion Report

## Final Disposition

**`M11_5_DURABLE_STRUCTURAL_EVIDENCE_VERIFIED`**

M11-5 is verified for durable structural Evidence over the bounded
source-bound, single-solid, linear-static M11-2/M11-3/M11-4 path. The accepted
scope includes trusted PASS, FAIL, and NOT_EVALUABLE engineering outcomes,
fresh historical reload, repeatability, and explicitly declared bounded
mesh-convergence studies for the supported displacement-magnitude metric.
This report does not expand the structural physics or acceptance scope.

## Accepted Baseline

The accepted predecessor baselines are:

- `M10_FULLY_CLOSED_LIVE_VERIFIED`.
- `M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED`.
- `M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED`.
- `M11_4_REAL_FEA_RESULT_ANALYTICAL_VALIDATION_VERIFIED`.

The final M11-5 marker is justified by the focused, regression, live, compile,
and full-suite results recorded below. No M11-6 acceptance is claimed.

## M11-5 Scope

M11-5 adds a durable trust layer above the accepted M11-4 result path. The
production flow is:

```text
trusted M11-4 execution/result/verification/analytical validation
  -> verified manifest and ArtifactStore bytes
  -> complete immutable structural Evidence payload
  -> semantic hash and EvidenceStore persistence
  -> fresh-store reload and independent verification
```

The same layer supports a predeclared two-run semantic repeatability comparison
and an explicitly bounded ordered mesh-convergence study. It does not rerun a
solver during historical verification.

## Structural Evidence Model

`Evidence` has one optional typed `StructuralEvidencePayload`. Ordinary
records use `EvidenceSubject.STRUCTURAL_ANALYSIS` and
`kind="analysis.structural"`. A convergence-study record uses
`EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY` and
`kind="analysis.structural.convergence"`; it binds verified level Evidence
without masquerading as a physical M11-4 result.

The payload is frozen, extra-field forbidden, versioned as
`structural-evidence@1`, and contains the source-bound request, execution
manifest, result, criterion verification, optional analytical validation,
material and geometry observations, direct and aggregate provenance, and
optional repeatability or convergence data. Ordinary structural Evidence is
explicitly `mesh_convergence_status=NOT_EVALUATED`.

## EvidenceStore Integration

The existing generic `EvidenceStore` remains the sole persistence boundary.
M11-5 adds no structural database and no raw store mutation API. Publication
writes one immutable Evidence record through `EvidenceStore.write_evidence()`;
verification reads it through `EvidenceStore.load_evidence()`. Legacy Evidence
without a structural payload remains valid and retains its prior serialized
shape.

## Evidence Publication Preconditions

`ProductionApplication.publish_structural_evidence()` is the trusted
publication entrypoint. It reconstructs authority from the bound immutable
revision, request, durable execution-manifest artifact, and verified raw
artifacts. The manifest, source STEP, MSH, INP, FRD, DAT, and LOG bytes are
verified through `ArtifactStore` before manifest parsing or result
interpretation. The publisher reconstructs the M11-4 result and verification,
then performs any trusted analytical reconstruction before publication.

Missing, changed, malformed, stale-at-execution, untrusted, or mismatched
dependencies prevent publication. A failed post-write fresh self-verification
is not reported as accepted Evidence and does not trigger mutation or repair.

## Evidence Semantic Hash

`structural_evidence_hash()` hashes the complete canonical structural payload
with its own `semantic_hash` field excluded. The canonicalizer also excludes
volatile storage and correlation values such as paths, timestamps, process IDs, temporary
directories, storage paths, and `run_id` are excluded by the canonical hashing
helper. A changed source binding, result, criterion, material authority,
analytical policy, provenance value, or study creates a new immutable identity.

## Artifact Binding

The explicit durable execution-manifest artifact ID and SHA-256 are bound into
the payload. Every referenced STEP, MSH, INP, FRD, DAT, and LOG artifact is
resolved through its trusted project/run boundary and reverified for identity,
type, size, metadata, producer/input relationships, and byte hash through
`ArtifactStore`. The source STEP may remain in the producing CAD run; analysis
artifacts remain in the structural-analysis run and are still bound to the same
project, revision, and state hash.
No raw artifact path is treated as authority.

## Result Binding

The persisted `StructuralAnalysisResult` is bound to the source project,
revision, state hash, definition identity/hash, request hash, execution
manifest hash, mesh hash, ordered load cases, parser provenance, and result
hash. The verifier reconstructs the result from verified durable artifacts and
compares the reconstruction to the payload instead of trusting caller-supplied
values or hashes.

## Criterion Binding

The complete `StructuralVerificationResult` is bound to the same source,
definition, request, manifest, result, and mesh identities. Criterion IDs,
limits, domains, observed/allowable values, units, reasons, and overall status
are re-evaluated and compared. Trusted engineering `PASS`, `FAIL`, and
`NOT_EVALUABLE` are distinct accepted outcomes.

## Material Authority Binding

Material observations and authority findings remain bound to the immutable
source definition and assignment semantics. M11-5 does not promote typical
reference data into measured or supplier authority. Missing material authority
remains an explicit engineering `NOT_EVALUABLE` outcome where the criterion
requires it; it is not converted into a fabricated PASS or FAIL.

## Analytical Validation Binding

When present, analytical validation persists the complete frozen policy, policy
hash, source request/result/manifest hashes, typed geometry and material
observations, six checks, errors, tolerances, statuses, reasons, and validation
hash. Verification reconstructs the declared analytical equations and checks
from these typed values and trusted MSH bytes without FreeCAD realization.

## Provider / Parser Provenance

Direct geometry, mesh, solver, and parser identities remain separate from the
aggregate structural pipeline provenance. The accepted live runtime is real
FreeCAD 1.1.3, Gmsh 4.15.0, and CalculiX 2.22, with the accepted M11-4 FRD/DAT
parser and interpreter identities. Same-name or same-version foreign/fake
provider provenance does not satisfy the exact trusted identity requirements.

## PASS Evidence

Trusted successful M11-4 execution with all required criteria evaluable and
passing may be published as immutable structural Evidence. Fresh verification
reconstructs and returns the same engineering `PASS` status. The live PASS
capstone passed through publication, durable reload, and independent
verification.

## FAIL Evidence

An otherwise valid solver execution with a predeclared engineering criterion
failure may be published as structural Evidence with `FAIL`. This is an
engineering criterion outcome, not a solver-integrity failure. The live FAIL
capstone preserved the trusted physical execution and recovered the criterion
failure after fresh reload.

## NOT_EVALUABLE Evidence

An otherwise trusted result with insufficient declared engineering authority or
coverage may be published as `NOT_EVALUABLE`. Missing material authority is
not a solver failure and is not replaced with a guessed value. The live
NOT_EVALUABLE capstone was added to the final six-test M11-5 live module and
recovered its typed outcome after fresh reload.

## Result-Integrity Failure Semantics

Corrupt or mismatched Evidence, state, manifest, artifact, result,
verification, analytical validation, parser, provider, material, or source
bindings raise structural integrity failure and do not become
`NOT_EVALUABLE`. Integrity failure is separate from an accepted engineering
criterion outcome. Publication never emits accepted Evidence from a failed
integrity or execution precondition.

## Fresh-Process Reload

The live reload capstones construct fresh `StateManager`, `ArtifactStore`,
`EvidenceStore`, and `StructuralEvidenceVerifier` instances. They reload by
durable Evidence IDs and persisted source/artifact records rather than reusing
in-memory M11-4 result, manifest, or service objects.

## Historical Evidence / Currentness

Verification remains valid against the Evidence record's immutable source
revision after canonical state advances. Currentness is separate and is one of
`CURRENT`, `STALE_RELATIVE_TO_CURRENT_STATE`, or
`CURRENTNESS_UNAVAILABLE`. The live historical capstone verified the old
Evidence as valid and stale after advancing the project revision.

## Tamper Detection

Payload semantic-hash changes and byte changes in the manifest, source,
mesh/deck, FRD, DAT, or LOG artifacts are detected before trusted parsing or
reconstruction. The focused failure suite covers tampering and verifies
fail-closed behavior.

## Replay Protection

Evidence binds exact project, source revision/state hash, structural definition,
request, target body, selected load cases, criterion, material authority,
analytical policy, result, manifest, mesh, artifact, and provenance identities.
Cross-project, cross-revision, cross-case, criterion, material, and analytical
policy replay therefore fails closed.

## Fake Provider Isolation

The production publisher requires the exact trusted provider and runtime
provenance. Fake or foreign same-name/same-version provenance cannot be used to
publish accepted structural Evidence. Fake providers remain test fixtures and
are not accepted as the live M11-5 execution authority.

## Repeatability Policy

`StructuralRepeatabilityPolicy` is frozen and hashed as
`structural-repeatability@1` before either compared run. It declares source,
definition, request, provider, runtime, semantic-summary, and tolerance
requirements. Comparison covers declared engineering summaries including free-
end displacement, maximum displacement, explicitly represented
CalculiX-extrapolated nodal von Mises stress, reactions, criterion results, and
analytical validation.

Raw artifact bytes, run IDs, mesh node IDs, element IDs, and generic mesh
correspondence are not repeatability requirements.

## Live Repeatability Result

The final live M11-5 module passed its predeclared two-run repeatability
capstone. The policy hash was asserted before either run, both Evidence records
were independently verified, and the comparison returned `REPEATABLE` without
requiring raw artifact or incidental mesh-numbering equality:

```text
policy_hash=sha256:916a7d312708b4676dc20f9107d8f49f4b39fdd364bc6ccd829c40660e95517c
first=EVD-STRUCTURAL-ddcd3be6cd51c7a0034bc850
second=EVD-STRUCTURAL-dfcc50937c45102c871daf68
result_hash=sha256:d2129c758860f850311443708536dd19a484287094cdc9f0536c5037666f9b44
status=repeatable
```

## Mesh-Convergence Study Model

`StructuralMeshConvergenceStudy` is frozen and hashed as
`structural-mesh-convergence@1`. It binds an ordered unique sequence of at least
three mesh specifications, one load case, the supported
`FREE_END_TRANSVERSE_DISPLACEMENT` response metric, the `free-end` domain,
nonnegative `magnitude` semantics, a relative-change threshold, epsilon, a
level bound, and required runtime identities.

Each level first becomes ordinary complete structural Evidence. A separate
convergence-study Evidence record then binds the complete ordered level
Evidence IDs and semantic hashes plus the study/result hashes. Level records
are never mutated by study publication.

## Convergence Policy

The evaluator independently verifies every ordered level before extracting the
declared response. For successive response magnitudes it uses:

```text
relative_change_i = abs(q_i - q_(i-1)) / max(abs(q_i), epsilon)
```

The bounded outcomes are `CONVERGED`, `NOT_CONVERGED`, `NOT_EVALUABLE`, and
`INTEGRITY_FAILURE`. Missing metric data in otherwise trusted level Evidence is
`NOT_EVALUABLE`; failed or corrupt level execution, source mismatch, duplicate
level, or failed referenced Evidence is `INTEGRITY_FAILURE`.

## Live Convergence Result

The final live M11-5 module passed the three-level convergence publication and
reload capstone. It verified the declared study hash, ordered mesh-specification
hashes, ordered level Evidence IDs and hashes, complete level result, separate
study publication, fresh reload, and unchanged level snapshots. The observed
convergence result was:

```text
study_hash=sha256:10f8a7d8022de7015bff13dd45e4b2fac098d83b5dd610d0a5dbb855f7070a1c
mesh_sizes=(10.0, 7.5, 5.0)
level_ids=(EVD-STRUCTURAL-df2e03178ca48ab04a4fa2b4,EVD-STRUCTURAL-cdb036bec48ccdaf2ffd3d77,EVD-STRUCTURAL-48b4f2887eb306e6496c394e)
level_hashes=(sha256:89db261076d438de5bbc8b98b89fce8a034f1f03a3473aed20e9c72a570bac9e,sha256:19f5daf0f61523ed15652a5002f5c4f185c2a0017d2078f686bf6e4eaa5d695a,sha256:24e8fad94f36ee12e76c9efdc5b512596d53c610429d20f5a746becbd9ac9d42)
responses=(2.261627083333334,2.2642747222222224,2.267595845655101)
relative_changes=(None,0.0011693099176102004,0.0014646011277725077)
status=converged
study_evidence_id=EVD-STRUCTURAL-3bd6ead32b44547d4df81fe8
```

The result is limited to the declared study and its supported metric; it is not
a global convergence claim.

## Post-Closure Mesh Identity Audit

The original closure run was not sufficient to establish mesh distinctness: its
three MSH artifact IDs were different, but their MSH bytes and counts were the
same because the declared target size was not applied to Gmsh. The execution
path was repaired narrowly by applying the target size to Gmsh, lowering the
CalculiX deck from the same generated MSH rather than remeshing, and normalizing
the admitted C3D10/FRD representations at their parser boundaries. No
repeatability, EvidenceStore, outcome, historical, or convergence-policy
semantics were changed.

The corrected live capstone independently read and SHA-256-verified each MSH,
reparsed its element records, checked the persisted mesh manifest, and checked
the CalculiX result binding. The final per-level observations were:

| target mesh size (mm) | MeshSpecification hash | MSH artifact ID | actual MSH SHA-256 | nodes | C3D10 volume elements | boundary elements | mesh semantic hash / manifest hash | response (mm) |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| 10.0 | `sha256:42cef9a8825970568a399ab0d34ed4e13ce863ece8327bd0b8e61fe6f209ec9d` | `STRUCT-MSH-5115a6288a433481` | `sha256:66730657641fcc561e44627fb294af4cbc60ac75c33d70cb32aa4bd4f773e2ca` | 955 | 430 | 16 | `sha256:477980ee9ba85c9cd3f83560d0a14e38861980fdacd8424a8b0dbc1b59a09a1c` | 2.261627083333334 |
| 7.5 | `sha256:0cf50ed822663b02833b99d29b60807b624129567330d8e7a3406ab6b90ef6ce` | `STRUCT-MSH-ac62085b2951f9dc` | `sha256:e7134952abacc66908a0ccd32c6acd47ddcf0935c01051b9eaab44be807118a9` | 1591 | 706 | 28 | `sha256:8766874dda700a52b6d1f576c6f6d7585fbf73a0aed389d4ed1bce8cd6728ff2` | 2.2642747222222224 |
| 5.0 | `sha256:e20ac87034b4213466fcc40817778c79c4fcdb3574f091f9abaef58b3ccce0f1` | `STRUCT-MSH-b367d3f18e96dde3` | `sha256:efc65cf985838346623c8bc8620a1ce7585cf74e5e42c1b565390b660cdc8594` | 3964 | 2003 | 44 | `sha256:c71de5be81805ecb9eca8591f772c75b27217e82d12b087389045a6446caf838` | 2.267595845655101 |

All three specification hashes, MSH IDs, MSH byte hashes, semantic/manifest
hashes, node counts, C3D10 counts, boundary counts, run IDs, request hashes,
execution-manifest hashes, and complete produced-artifact ID sets were unique.
Each deck artifact was input-bound to its level MSH hash; each FRD and DAT
artifact was input-bound to its level deck hash. The final audit therefore found
no ArtifactStore reuse, request caching, manifest reuse, mesh-artifact reuse, or
solver-result reuse across levels.

## Convergence Limitations

Convergence is explicit and bounded. It does not provide adaptive refinement,
generic mesh correspondence, nodal/element field correspondence, stress
convergence, automatic mesh independence, or a global convergence marker. The
study does not mutate its level Evidence.

## Live Runtime

The live production toolchain was real FreeCAD `1.1.3`, Gmsh `4.15.0`, and
CalculiX `2.22`. No runtime-gated skip occurred for M11-5.

## Live Evidence Capstones

The final M11-5 live module command was:

```text
py -3 -m pytest tests/integration/test_m11_5_live_structural.py -q
```

It completed `6 passed in 574.92s (9:34)` after final fixes. It covers:

- PASS Evidence publication and fresh reload.
- FAIL and NOT_EVALUABLE Evidence publication and fresh reload.
- Predeclared repeatability and its hashed policy.
- Three-level displacement-magnitude convergence publication and fresh reload.
- Historical validity, stale currentness, and runtime-independent verification.

The post-closure three-level mesh identity audit was run as:

```text
py -3 -m pytest tests/integration/test_m11_5_live_structural.py::test_live_three_level_convergence_publication_and_reload -q -s
```

It completed `1 passed in 185.66s (3:05)`, including three independent
CalculiX solves and the per-level identity/reuse assertions above.

The final M11-3/M11-4/M11-5 live subset was `14 passed` in the verified
regression run. The live module uses fresh `StateManager`, `ArtifactStore`,
`EvidenceStore`, and verifier instances for reload and for repeatability and
convergence evaluation; it does not claim a separate operating-system process.

Observed capstone identifiers included:

```text
PASS evidence_id=EVD-STRUCTURAL-e5461b9227b1cbb64500706b
PASS result_hash=sha256:aec29e56a62d0ef7fe92371bbeeaded742fd41cb1b530c7e0b586cca0ad99e3c
PASS maximum_displacement_mm=2.252616918035249
NOT_EVALUABLE convergence_study_evidence_id=EVD-STRUCTURAL-e74d0a235bab2f288525e170
NOT_EVALUABLE level_ids=(EVD-STRUCTURAL-1567f3b211a2b3652edf20ca,EVD-STRUCTURAL-6a9b0f3c0ad25812e73b914a,EVD-STRUCTURAL-7c04300e8db1730ad8f1985d)
NOT_EVALUABLE level_hashes=(sha256:a232c1a0acbbca42126b7a11ed21733221a6b5b9b4cb852b9c580a35d8ed02b5,sha256:8adfee807f32fcf803e325bc4b98426be7bd35ee787c58369c25107b290f3284,sha256:2a5d5dcd1c926c7af3fb97099bdf6563bab5a33a5d9a29d7df2fb1ea2c8ea5fd)
HISTORICAL evidence_id=EVD-STRUCTURAL-601cf9c398e23d097ff31904 current_revision=3 currentness=stale_relative_to_current_state
```

## Focused Failure Tests

The final focused suite covered structural Evidence models and verifier,
artifacts, structural models/request/results/runtime/service/validation, and
the production application:

```text
py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py tests/unit/test_artifacts.py tests/unit/test_structural_models.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_request.py tests/unit/test_structural_results.py tests/unit/test_structural_runtime.py tests/unit/test_structural_service.py tests/unit/test_structural_validation_observations.py tests/unit/test_production_application.py -q
```

```text
520 passed in 59.00s
```

It includes schema/hash and immutability checks, legacy Evidence compatibility,
strict publication and reload bindings, artifact and payload tamper detection,
replay protection, fake-provider isolation, currentness separation,
repeatability outcomes, and convergence sequence/outcome validation.

## M9/M10/M11-3/M11-4 Regression Results

The predecessor/live regression command covering M10-1, the M10 multi-joint
stack, M9 live coverage, M11-3, M11-4, and M11-5 completed with:

```text
py -3 -m pytest tests/test_m10_1_continuous_proof.py tests/unit/test_multi_joint_kinematics.py tests/unit/test_multi_joint_collision_sweep.py tests/unit/test_multi_joint_continuous_clearance.py tests/integration/test_m9_1_freecad_runtime_live.py tests/integration/test_m9_2_real_trusted_imported_artifact.py tests/integration/test_m9_3_live_mixed_assembly_exact_kinematic.py tests/integration/test_m9_4_trusted_analysis_backend_provenance.py tests/integration/test_m11_3_live_structural.py tests/integration/test_m11_4_live_structural.py tests/integration/test_m11_5_live_structural.py -q
```

```text
154 passed, 9 skipped in 316.61s (5:16)
```

The skips are recorded as test-suite skips, not as M11-5 runtime gating. The
final M11-3/M11-4/M11-5 live subset completed with `14 passed`.

## Full Suite Results

The required full command was:

```text
py -3 -m pytest tests/
```

Observed result:

```text
1371 passed, 34 skipped in 1391.53s (23:11)
```

Focused compilation passed:

```text
py -3 -m compileall src/mechcad_harness -q
```

The full compilation also passed:

```text
py -3 -m compileall -q src/mechcad_harness tests
```

## Files Changed

Task 9 changed only these documentation files:

- `README.md`
- `AGENTS.md`
- `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`
- `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`
- `docs/architecture/MECHCAD_ENGINEERING_WORKFLOW.md`
- `docs/architecture/MECHCAD_RUNTIME_FLOW.md`
- `docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md`
- `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`
- `docs/architecture/MECHCAD_DOCUMENTATION_GAPS.md`
- `docs/audit/MECHCAD_M11_5_COMPLETION_REPORT.md`

Pre-existing implementation and test changes, generated project trees,
`err.txt`, and other unrelated worktree artifacts were excluded and left
untouched. No commit, push, reset, stash, clean, checkout, revert, discard,
or deletion was performed.

## Remaining Limitations

- The capability remains source-bound, single-solid, linear-static, and within
  the bounded M11-3/M11-4 execution, interpretation, and analytical policy.
- Stress remains CalculiX extrapolated nodal stress. No global yield or safety
  claim is made.
- Repeatability compares declared semantic summaries, not raw result bytes or
  generic mesh correspondence.
- Mesh convergence is limited to an explicitly declared ordered study of the
  supported free-end displacement-magnitude metric.
- Adaptive refinement, automatic mesh independence, stress convergence,
  assemblies, nonlinear analysis, fatigue, dynamics, thermal stress,
  tolerances, optimization, manufacturing approval, and automatic
  synthesis/selection remain out of scope.

## M11-6 Boundary

M11-5 verifies durable structural Evidence and bounded studies for the stated
scope. It does not provide system-wide acceptance, a global convergence claim,
or broader structural approval. M11-6 remains unperformed and is responsible
for any final system-wide acceptance decision.
