# M12-4 Candidate CAD, M10 Evaluation, Comparison, And Selection Completion Report

**Date:** 2026-08-29
**Disposition:** `M12_4_CANDIDATE_CAD_M10_EVALUATION_COMPARISON_SELECTION_VERIFIED`

## Final Disposition

`M12_4_CANDIDATE_CAD_M10_EVALUATION_COMPARISON_SELECTION_VERIFIED`

The bounded M12-4 production path is live verified. An accepted M12-3
candidate is realized as an immutable candidate CAD outcome, its declared
constituent pairs are evaluated through unchanged M10 services, and the
result is aggregated into immutable evaluation, comparison, and explicit
noncanonical selection records. The capstone used real FreeCAD geometry for
generated and trusted imported components and real transient exact measurement.

This report does not promote a candidate, mutate canonical design state, or
extend the accepted capability to M12-5 or to an M11 candidate bridge.

## Required Verification

All commands were run fresh in the current worktree with `py -3`. No pytest-level
test timeout was configured. The execution harness supplied a 3600-second command
ceiling, and the full suite completed normally before that ceiling.

### Focused M12-4 Suite

Command:

```text
py -3 -m pytest tests/unit/test_m12_candidate_cad_models.py tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_cad_replay.py tests/unit/test_m12_candidate_m10_binding.py tests/unit/test_m12_candidate_m10_service.py tests/unit/test_m12_candidate_m10_replay.py tests/unit/test_m12_candidate_evaluation.py tests/unit/test_m12_candidate_comparison.py tests/unit/test_m12_candidate_selection.py tests/integration/test_m12_candidate_cad_m10_production.py -q
```

Result: collected `157`; passed `157`; skipped `0`; failed `0`; errors `0`;
elapsed `247.07s` (`0:04:07`); exit code `0`.

### Live Capstone Evidence Capture

Command:

```text
py -3 -m pytest tests/integration/test_m12_candidate_cad_m10_production.py -q -s
```

Result: collected `15`; passed `15`; skipped `0`; failed `0`; errors `0`;
elapsed `225.16s` (`0:03:45`); exit code `0`. The `-s` run printed the runtime
and identity records transcribed below.

### Shared-Foundation Regressions

Command:

```text
py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py tests/unit/test_m12_revolute_drive_service.py tests/integration/test_m12_revolute_drive_production.py tests/test_m10_1_continuous_proof.py tests/integration/test_m10_1_live_continuous_proof.py tests/integration/test_transient_imported_multishape_collision.py tests/unit/test_kinematic_sweep.py tests/unit/test_transient_assembly_analysis.py -q
```

Result: collected `152`; passed `151`; skipped `1`; failed `0`; errors `0`;
elapsed `58.34s` (`0:00:58`); exit code `0`. The one skip was an existing
runtime-gated predecessor test and was not counted as a pass.

### Full Suite

Command:

```text
py -3 -m pytest tests/
```

Two successful full-suite runs were captured with the same counts:

- Collected: `1741`
- Passed: `1707`
- Skipped: `34`
- Failed: `0`
- Errors: `0`
- Exit code: `0`

- Run 1 elapsed: `1824.44s` (`0:30:24`).
- Run 2 elapsed: `1707.83s` (`0:28:27`).

Both runs used Python `3.14.6` and pytest `8.4.2`, and completed without timeout
or abort.

### Compile

Command:

```text
py -3 -m compileall -q src/mechcad_harness tests
```

Result: no output; exit code `0`; elapsed `0.454s`. No pytest collection or
test-result counts apply.

### Diff Check

Command:

```text
git diff --check
```

Result: no whitespace errors; exit code `0`; elapsed `0.070s`. Git emitted only
existing working copy line-ending normalization notices for unrelated
already-dirty tracked files. The final untracked M12-4 scan covered `18` files
in `0.347s` and found `0` trailing-whitespace issues and `0` malformed
EOF/newline conditions.

### Runtime Identity

Command:

```text
& 'C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe' --version
```

Result: `FreeCAD 1.1.3 Revision: 20260725 (Git shallow)`; exit code `0`;
elapsed `0.234s`.

The live capstone resolved and used the same executable path:
`C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`. Its production runtime
record reported `available: true`, `execution_boundary: bundled FreeCAD
command line`, and `importable: false`; the direct version command provides
the actual `1.1.3` runtime version. The capstone also verified continuous-proof
Evidence with provider `freecad-transient-exact`, execution mode
`freecadcmd-subprocess`, and backend library `FreeCAD`.

## Accepted Baseline

M12-4 consumes the accepted M12-3 source-bound revolute-drive admissibility
result and preserves the accepted generic CAD, trusted imported STEP, and M10
semantics. M12-4 does not reimplement M12-3 formulas or M10 collision/proof
arithmetic.

## M12-4 Scope

The production surface is composed by `ProductionApplication` through:

- `realize_candidate_cad`
- `evaluate_candidate`
- `compare_candidates`
- `select_candidate`

The records are frozen, content-addressed, source-bound, and noncanonical.
Candidate CAD is transient. Existing source artifacts remain under the normal
`ArtifactStore` project/run artifact layout; no candidate CAD store or
automatic candidate publication was introduced.

## Architecture Traceability

```text
M12-3 admissible candidate and source binding
  -> candidate-bound CAD request and physical/CAD mappings
  -> trusted imported STEP resolution and bounded generated plates
  -> complete CadAssemblyProgram
  -> candidate M10 binding and complete pair inventory
  -> induced two-constituent assemblies
  -> unchanged M10 continuous proof or exact home sweep
  -> CandidateEvaluation
  -> deterministic CandidateComparison
  -> explicit noncanonical CandidateSelection
```

The M10 bridge invokes the existing public single-axis proof separately for
each `CHECK_CLEARANCE` pair. It does not pass the full candidate assembly to a
cross-product that would include intentionally excluded pairs.

## Candidate CAD Realization

The focused model/compiler/replay tests verified deterministic SHA-256
identities, complete unique physical-to-CAD mapping, placement provenance,
candidate/source binding, strict extra-field rejection, source-byte tamper
failure, source-artifact substitution failure, and no fabricated realization
for unavailable geometry.

The live direct-drive chain used five trusted INPUT/source STEP artifacts,
created or registered through `ArtifactStore` and freshly byte-verified, plus two explicitly candidate-bound generated
bounded collision representations for `motor-mount` and `payload-body`.
`ImportedCadComponent` remained the imported representation, and the live
assertion confirmed that imported components were present in the realized
assembly.

The live external-spur chain used trusted INPUT/source geometry for the seven
non-gear source components and the two gear source artifacts, plus the same
two explicitly selected bounded representations. The requested bounded
representation was never an automatic downgrade from trusted source geometry.

## Geometry Fidelity

The accepted fidelity vocabulary is explicit:

- `TRUSTED_SOURCE_GEOMETRY`: freshly resolved and SHA-256-verified source
  artifact content.
- `DECLARED_BOUNDED_COLLISION_REPRESENTATION`: deterministic generated plate
  geometry derived from candidate-bound dimensions and retained as bounded
  collision representation only.

The exact FreeCAD measurement claim is therefore exact for the supplied
representation. It is not a claim that bounded geometry is exact manufacturer
geometry or real-world geometry.

## M10 Binding And Pair Coverage

Every realized CAD constituent received exactly one M10 disposition:
`FIXED`, `OUTPUT_RIGID`, or `INTERNAL_MOTION_UNMODELED`. Distinct constituents
may share an output transform without being compounded, so constituent-level
pair identity remains measurable.

The direct-drive fixture has seven CAD constituents, hence a 21-pair complete
unordered inventory. It declares one checked pair, canonical inventory pair
`(cad-motor-mount, cad-output-hub)`, evaluated directionally by M10 as moving
`cad-output-hub` against stationary `cad-motor-mount`; the remaining 20 pairs
are explicit exclusions. The continuous motion interval for the clear and
collision cases was `(-10.0, 10.0)` degrees. The not-proven case deliberately
used `(0.0, 360.0)` degrees with constrained exact-evaluation limits.

The external-spur fixture has 11 CAD constituents, hence a 55-pair complete
unordered inventory. It declares the same one checked hub/mount pair and
explicitly excludes the other 54 pairs. The inventory includes the driver/
driven gear pair as `INTENDED_CONTACT_EXCLUDED` with reason `declared gear
mesh interface is outside M10 scope`.

The unit and live tests reject omitted, duplicated, reclassified, or
unsupported inventory entries and preserve exact candidate, realization,
binding, model, scope, mapping, request, and result identities.

## Continuous M10 Outcomes

The direct-drive live capstone produced all three required semantic outcomes:

| Case | M12-3 | CAD stage | Original M10 status | Candidate evaluation | Evidence |
|---|---|---|---|---|---|
| Clear | `ADMISSIBLE` | `SUCCESS` | `VERIFIED_CLEAR` | `FEASIBLE` | certified lower bound `31.53943423446451 mm` |
| Collision | `ADMISSIBLE` | `SUCCESS` | `COLLISION_WITNESS` | `INFEASIBLE` | positive interference volume witness |
| Budget constrained | `ADMISSIBLE` | `SUCCESS` | `NOT_PROVEN` | `UNRESOLVED` | no fabricated metric or collision witness |

The clear metric is `verified_clearance_lower_bound_mm` in `mm`, derived only
from the minimum trusted `minimum_certified_lower_clearance_mm` value in the
existing M10 certificates. Discrete clearance was not used as a continuous
metric.

The live direct-drive identity record was:

```text
clear_candidate_hash       sha256:d56b82c4f9c49b04799bce2a24d6328c7678eec282043ca6c3a20822a4d9363a
clear_cad_request_hash     sha256:c14629b8024d4df5aaed2fa6f3acc761b60d812e7d04a1c8064bc31a901a740b
clear_cad_realization_hash sha256:59832bff3a0b93e19f6d5a4775c19ff77d35ae69e8c0ee1651589fca35df8d7e
clear_m10_request_hash     sha256:f9a9b67eeaba719c7800ecf6c7c7476c209c272b5891d3f8fc41033c4a45d3b2
clear_m10_result_hash      sha256:26bd3a3497ffb834bfc830680eeff40c7096bbc821da0c156aa99e6cb64d48e2
clear_evaluation_hash      sha256:04c1ad85283748d5377217eb13eb72997e513aa70a437ec38c0003dea432c3f9
collision_candidate_hash   sha256:ba651a64c3f68a5effecbc587db53b57f399f67fa2ba7bf0a4bacdf64dd681aa
collision_cad_realization_hash sha256:bd0791eee336b0b991b1f4d2ece7653e372c631f8b0c77d803a89253dcf0969d
collision_m10_result_hash  sha256:99e47add52f489976e8c8a15b3b1ad77b9da2fb76ae356ea6953ab4a2b5d0585
collision_evaluation_hash  sha256:c6a43dfe0b4e95d32e02f10a70c04f9aa0fd73521992406915a3ce8821e833d6
not_proven_candidate_hash  sha256:d56b82c4f9c49b04799bce2a24d6328c7678eec282043ca6c3a20822a4d9363a
not_proven_cad_realization_hash sha256:59832bff3a0b93e19f6d5a4775c19ff77d35ae69e8c0ee1651589fca35df8d7e
not_proven_m10_result_hash sha256:195d4d81c53e8d3f6c98427857ed6fd75f62260642ec69e4e63bf94878dc4fd2
not_proven_evaluation_hash sha256:06f466e1df8896f9837afeb6d98b3d96d3a7c1d7f45931bb1f1068e6e3cd63f5
```

The not-proven case retained its exact M10 result identity and produced no
continuous-clearance metric. The collision case retained a hard witness and
was not converted into unresolved status.

## Home Exact Checks

The bridge has a separate exact home-state path using the existing discrete
M10 sweep with exactly `sample_angles_deg=(0.0,)`. Home checks preserve the
original sweep request/result identities and do not become continuous proof.
The unit coverage verifies that an exact home collision remains a hard
geometric witness while an unmodeled internal-motion path remains unresolved.

## External Spur Limitation

The live external-spur candidate preserved the identities for motor, driver
gear, driven gear, shaft, bearings, hub, mount, support mounts, and driven
body. The driver gear was explicitly classified as
`INTERNAL_MOTION_UNMODELED`, never `FIXED`. The gear pair was explicitly
classified as `INTENDED_CONTACT_EXCLUDED`.

The live limitation identity record was:

```text
candidate_hash           sha256:a62c26f14523d2ddd7b22c40cab537f327f3a5556f3db83b6b4f27cf8354f968
m12_result_hash          sha256:eee216aa8922db1599ad7248e8624206d2660f5f226a50e2ce9a8c0a59bc0e28
cad_realization_hash     sha256:cd4e46052524a0ee41f6880514662c4e1ddab68aae536b5e833b61805a1c790a
m10_request_hash         sha256:c51f8fc21325cfe01f437b589c3dfc75bf235047a55cee5314fd092e51f562b8
driver_disposition       internal_motion_unmodeled
gear_pair_classification intended_contact_excluded
continuous_proof_pairs   (cad-motor-mount, cad-output-hub)
```

No driver counter-rotation, gear phase, backlash, tooth mesh correctness,
internal transmission clearance, motor-internal, or bearing-internal claim
was made. The live test confirmed that no driver-gear pair entered continuous
or home proof.

The provider-boundary regression
`test_external_spur_trusted_provider_failure_never_downgrades_to_bounded_geometry`
is ToolBroker-only: it verifies that an unavailable py-gearworks provider is
persisted as a failed tool result with `BackendUnavailableError`. It does not
invoke candidate CAD realization. The application-level regression
`test_candidate_realization_rejects_unavailable_trusted_external_spur_artifact_without_downgrade`
does invoke `ProductionApplication.realize_candidate_cad`. It uses
provider-produced external-spur artifacts, removes the explicitly required
trusted driver artifact, marks the provider unavailable, and verifies the
typed `CandidateCadIntegrityError` rather than a bounded realization. Candidate
CAD consumes persisted trusted artifacts and does not silently downgrade or
invoke a bounded compiler when that trusted representation is unavailable.

## Comparison And Selection

Three distinct feasible candidates were evaluated with the same project,
source-binding, and candidate-independent evaluation-scope identities. Their
candidate and evaluation identities were distinct; two candidates shared the
same certified metric and formed a true tie. The sole comparison metric was
the certified clearance lower bound in `mm`.

The live comparison/selection identity record was:

```text
candidate_hashes:
  sha256:877a8f10fd06d1d59ebd637b8ea8dac01dd5af6485faee0d723124c820c844ee
  sha256:85941d13f5d20edb5bfc0f1442f197a672644063b566c150ecc0cc9a5ad7b62b
  sha256:bb6561e96b670d86ab19f670a1202c62e425c0e5babd82ce0bf0140c9c547946
evaluation_hashes:
  sha256:f94a3f05c3b7775098492163ea558931386f1663a5d45cf761e59cebfc50c624
  sha256:373bb3e739bd8e02343df6e418cdb11661562d30bbe39cc61b70721f7b69ced6
  sha256:0cf9b88cfc147cbc8647f93da1a2e0f3ceffd68a8119b75be06427187f62962e
scope_hash                 sha256:ce7228e093d37391a79f02ee0e868015525d24e1a2fcd608b2e98aa9951edab6
ranking_request_hash       sha256:fc4bb29fb908a40bc35067a1b1bca5154da7af86ecd5a5a05d42d2f1981e059c
ranking_result_hash        sha256:19b266dd438cd3786d067eb3c576ef682b80f6ff166f3ac0982f08f937aed033
ranking                    candidate b, candidate a
tie_result_hash            sha256:a422d4d71c8537b2970cf8aa36816316269a7f11a830e07c28a63b06e285ae05
tie_group                  candidate b, candidate c
selection_hashes:
  sha256:9a6154b5e02fe155f54ab357eec97ce277247db307d962c010652b1278b34987
  sha256:7d571efbcdd031fd0846f7463270f0b4c6194ddb73efff3519bc61d58b230fe4
  sha256:f69bd514114ad5f9fee37012c4c3ba27601a90c09272e55a4f60c47a39bcf8fd
```

The first selection cited the comparison and selected the higher-ranked
candidate. The second omitted comparison and recorded `comparison_used=false`.
The third cited the comparison and explicitly selected the non-top-ranked
feasible candidate with rationale. Hash ordering was not used as an
engineering preference.

## Canonical State / Source Nonmutation

Every live direct-drive, external-spur, comparison, and selection capstone
asserted equality of the source revision and source state hash before and
after execution. The direct-drive capstone also read the trusted source
artifact bytes before and after evaluation and asserted byte equality.

Candidate CAD, M10 evaluation, comparison, and selection did not create a
canonical revision, call `ChangeEngine`, publish a candidate record, or alter
the immutable candidate. Existing M10 proof Evidence remained the existing
M10 public-path behavior and was not reclassified as candidate Evidence.

## Trust / Replay / Integrity

The focused tests verified:

- canonical SHA-256 reconstruction for all M12-4 semantic records;
- candidate, source, geometry, placement, mapping, binding, scope, request,
  stage, result, policy, comparison, and selection substitution rejection;
- complete pair inventory and exact constituent granularity;
- exact M10 request/result identity preservation for continuous and home paths;
- `NOT_PROVEN` retention without a fabricated metric;
- hard-witness precedence over unresolved findings;
- exact component-scoped trusted geometry-definition identities, while retaining
  the owning component source artifact identity;
- mandatory CAD replay verification for evaluation currentness, including the
  composed ArtifactStore-backed realization replay;
- stale source/currentness rejection at evaluation, comparison, and selection;
- missing metric and wrong metric source/unit rejection;
- no downstream identity fabrication after CAD unresolved or an earlier stage
  failure.

## Production Composition

`ProductionApplication` composes the focused M12-4 services beside the existing
M12-3, CAD, artifact, and M10 services. Application methods delegate to those
services rather than duplicating their algorithms. Default composition uses the
attested `FreeCADTransientAssemblyMeasurementProvider`; the live capstone
verified its exact `common().Volume` / `distToShape()` measurement boundary
through the existing M10 continuous proof path.

## Engineering Self-Review

No new M10 mathematics, candidate collision arithmetic, placement authority,
candidate store, or automatic fidelity fallback was found in the completed
M12-4 path. The implementation retains separate physical and CAD IDs even
when multiple output-rigid bodies share a transform. It uses the explicit
candidate-bound mapping and complete inventory rather than inferring omitted
interfaces from names.

## Focused Tests

The focused suite covers candidate CAD models/compiler/replay, M10 binding and
replay/service, evaluation, comparison, selection, production short-circuit
behavior, live direct-drive clear/collision/not-proven behavior, external-spur
limitation behavior, the ToolBroker provider-unavailability boundary, the
application-level trusted-artifact-unavailability boundary, exact trusted
component-scoped geometry identities, mandatory currentness CAD replay, and
comparison/selection behavior. It completed with `157 passed`, `0 skipped`,
`0 failed`, and `0 errors`.

## Predecessor Regressions

The shared regression command completed with `151 passed`, `1 skipped`, `0`
failed, and `0` errors. M12-3 production and model/service coverage, M10-1
proof coverage, imported multi-shape collision coverage, kinematic sweep, and
transient assembly analysis remained green.

## Full Suite

Both captured complete-suite runs completed with `1741` collected, `1707` passed,
`34` skipped, `0` failed, and `0` errors; exit code `0`. Run 1 elapsed
`1824.44s` (`0:30:24`), and Run 2 elapsed `1707.83s` (`0:28:27`).

## Compile / Diff

`py -3 -m compileall -q src/mechcad_harness tests` exited `0` with no output.
`git diff --check` exited `0` with no whitespace errors. The separate scan of
the new M12-4 source, test, specification, plan, and audit files found no
trailing whitespace and no malformed EOF/newline condition across `18` scanned
untracked M12-4 files.

## Capability Claim

MechCAD can now, for the bounded supplied-component M12-3 candidate path,
realize candidate-bound mixed CAD with explicit trusted/bounded fidelity,
evaluate declared one-output-joint constituent pairs through unchanged M10
proof and exact home services, aggregate feasible/infeasible/unresolved
outcomes, compare feasible candidates by one trusted clearance metric, and
record an explicit noncanonical selection without mutating `DesignState`.

## Explicit Non-Goals

M12-4 does not implement or claim:

- M12-5 candidate promotion, approval, or post-promotion verification;
- an M11 or candidate-to-M11 structural/FEA bridge;
- canonical `DesignState` mutation or automatic candidate publication;
- general mechanism synthesis, catalog lookup, search, optimization, or
  automatic component selection;
- gear ratio joints, counter-rotation, phase, backlash, tooth mesh correctness,
  internal transmission clearance, motor internals, or bearing internals;
- general trajectories, swept solids, inverse kinematics, dynamics, or
  configuration-space certification;
- manufacturer-exact geometry claims for bounded representations;
- manufacturing, tolerance, cost, mass, safety, strength, life, fatigue,
  thermal, or complete-machine approval claims.

## Remaining Limitations

Continuous proof covers only the explicitly declared one-output-joint interval
for each checked pair. A clear home sample is not continuous proof. Internal
spur motion remains unmodeled and outside the verified continuous scope. The
only comparison metric is the trusted M10 certified clearance lower bound.

## Files Changed

The remaining Important-finding remediation changes are the exact trusted
geometry-definition checks in `src/mechcad_harness/candidates/cad_realization.py`
and `src/mechcad_harness/candidates/evaluation.py`, mandatory CAD replay
verification in `src/mechcad_harness/candidates/evaluation.py`, the focused
unit regressions, this report, and the progress marker. The earlier Task 10
review-fix files remain part of the same uncommitted M12-4 worktree.

The modified
`docs/superpowers/specs/2026-08-27-m12-1-generic-design-candidate-physical-mechanism-realization-architecture.md`
is an accepted narrow M12-1 documentation reconciliation only. It clarifies
candidate identity and comparison-request prose; it is not an M12-4
implementation change.

The M12-4 implementation files present in the worktree are the previously
implemented candidate CAD, M10 bridge, evaluation, comparison, and selection
sources under `src/mechcad_harness/candidates/`, together with their M12-4
specification, plan, and tests. They are distinct from the narrow M12-1
documentation reconciliation above.

## Worktree Status

The worktree remains uncommitted as required. The modified M12-1 reconciliation
file is
`docs/superpowers/specs/2026-08-27-m12-1-generic-design-candidate-physical-mechanism-realization-architecture.md`;
it is documentation-only and separate from the M12-4 implementation files.
Existing M12-4 source, specification, plan, test, and audit files remain in the
worktree alongside the review-fix regression. Existing unrelated dirty and
untracked files, including `.coverage`, `err.txt`, `projects/`, and the
unrelated `src/mechcad-harness/` path, were preserved. No commit, tag, push,
reset, clean, checkout, revert, or destructive operation was performed.
