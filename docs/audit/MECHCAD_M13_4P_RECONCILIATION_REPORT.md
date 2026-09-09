# M13-4P Production Composition Reconciliation

## Input Authority

The current M13-4E R8 authority, the M13-4E production implementation and
tests, the M12-6 exact-artifact locator precedent, and the current production
composition root were treated as authoritative. The accepted locator contract
is `ArtifactStore.read_verified_in_project(exact_artifact_id)` followed by a
fresh run-scoped store and the unchanged M13-4E verifier.

## Historical Architecture Gap

M13-4E multi-joint selection, compilation, manifest, application, and
verification services existed below the production root, but the root exposed
only the legacy single-joint candidate-selection and promotion route. The
missing capability was production composition, not a missing M13-4E semantic
or persistence primitive.

## Current Production Route Before Reconciliation

Before this reconciliation, callers could use the M13-3/M13-4E lower-layer
services directly or use the legacy `ProductionApplication` promotion route.
There was no root method that owned the complete multi-joint replay, typed
selection, typed promotion, and durable receipt verification path.

## Gap Classification

The gap is classified as `M13_4P_NARROW_COMPOSITION_WIRING_REQUIRED`.

`M13_4_MAY_RESUME = NO` and `ROTATOR_V2_MAY_RESUME = NO` remain unchanged.

## Implementation Scope

The implementation adds only the required production composition methods and a
focused integration proof. It does not add a generic M10 result store, alter
M13-4E schemas or verifier semantics, broaden the legacy promotion API, or
start M13-4 acceptance work.

## Production Composition Changes

`ProductionApplication` now exposes:

- `select_candidate_multi_joint(...)`
- `promote_selected_multi_joint_candidate(...)`
- `verify_multi_joint_promotion_application(...)`

Selection verifies the candidate project binding, reconstructs the M10 v2
request from the supplied candidate/CAD/bridge inputs, executes the existing
exact sweep path, and rejects request or result identity drift before delegating
to `CandidateMultiJointSelectionService`.

Promotion is a typed request-only delegation to the new service method. The
service creates the normal run, publishes and resolves the decision manifest,
applies the approved proposal through `RunController`, verifies invalidation,
publishes and resolves the result manifest, and returns the typed application
receipt.

Verification locates the decision artifact by its exact persisted artifact ID
through `read_verified_in_project()`, obtains the persisted run ID from the
verified artifact metadata, creates a fresh scoped `ArtifactStore`, and
delegates to `verify_multi_joint_promotion_application_result()`.

## Final Production Route

The accepted route is:

1. Load canonical source state through `ProductionApplication`.
2. Evaluate the supplied multi-joint request through the root M10 v2 path.
3. Replay and select through `select_candidate_multi_joint(...)`.
4. Build a typed `CandidateMultiJointPromotionRequest`.
5. Promote through `promote_selected_multi_joint_candidate(...)`.
6. Verify the durable receipt through `verify_multi_joint_promotion_application(...)`.

The focused route uses `ProductionApplication.create()` and real persistence
services. It does not retain a pre-promotion run object or use a test-only
orchestrator.

## M13-4E Contract Preservation

The legacy `promote_selected_candidate(...)` entry point remains unchanged and
continues to reject a multi-joint request at the legacy schema boundary. No
union dispatch, generic proposal-application method, M13-4E identity
normalization, or accepted M13-4E verifier modification was introduced by the
M13-4P composition additions.

## Run / Artifact / State Authority

The decision artifact and result artifact are published in the normal run
scope. The receipt binds the request, readiness, compilation, decision ID,
result ID, applied revision, and applied state hash. The focused route verifies
that the applied revision is source revision plus one and that the persisted
state hash equals the receipt hash.

Receipt verification uses no latest-run selection, directory globbing, or
ambient cache. Exact artifact ID lookup must resolve uniquely; a strict-valid
duplicate in another run is rejected as ambiguous. Forged run metadata is also
rejected.

## M10 v2 Boundary

M10 v2 remains the existing discrete multi-joint evaluation boundary. The root
composition reuses its request reconstruction and exact sweep execution, checks
the resulting request and result identities, and passes the typed replay result
to the existing selection service. No continuous proof or configuration-space
claim is added.

## Representative Integration Proof

`tests/integration/test_m13_4p_production_composition.py` proves the complete
root route and observes:

- project-bound candidate selection;
- source revision and source state hash binding;
- request, evaluation, selection, and compilation identities;
- identity equality between the compiler's original return and the receipt;
- decision and result artifact IDs;
- applied revision and applied state hash;
- final `PROMOTION_APPLIED` status;
- a second fresh exact-ID receipt verification;
- no retained per-candidate replay inputs or ambient root state.

The test also confirms the original root evaluation occurs before selection and
that selection performs its own replay rather than consuming ambient state.

## Negative Composition Tests

The focused suite covers:

- foreign candidate rejection before replay;
- unchanged measurement-call count on the rejected foreign-candidate path;
- valid replay-result identity mismatch rejection;
- legacy entry-point rejection of a multi-joint request;
- ambiguous exact decision-artifact ID rejection;
- forged decision-artifact run metadata rejection;
- receipt verification through the exact persisted decision artifact ID.

## Focused M13-4P Gate

Command:

```text
py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -q
```

Result: `8 passed in 12.73s`, zero skips.

## M13-4E Regression

Command:

```text
py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q
```

Result: `116 passed in 125.51s`, zero skips.

## M13-3 / Predecessor Regression

Command:

```text
py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q
```

Result: `75 passed in 35.13s`, zero skips.

## Full Suite

Command:

```text
py -3 -m pytest -q -rs
```

Result: `2819 passed, 34 skipped in 3452.67s (0:57:32)` with exit code 0.

## Skip Audit

The 34 skips are environment or opt-in gates only:

- 14 structural-profile skips because the optional structural profile extra is not installed;
- 9 FreeCAD availability skips;
- 6 OpenCode live-validation opt-in skips;
- 5 materials-extra skips because the optional materials extra is not installed.

There are no M13-4P skips.

## Static Audit

The following commands passed:

```text
py -3 -m compileall src tests
git diff --check
```

Targeted searches confirmed the new root verifier uses exact
`read_verified_in_project()` lookup and does not use `latest_run`, `glob`,
`existing_in_project`, or ambient candidate caches. The existing unrelated
`ProductionApplication` evidence-discovery code still contains its historical
glob use; it is outside the new M13-4P route and was not changed.

## Protected Surface Audit

M13-4P production changes are limited to the additive root methods in
`src/mechcad_harness/application.py` and the typed promotion delegation and
run lifecycle in `src/mechcad_harness/candidates/promotion.py`.

M13-4P test changes are limited to
`tests/integration/test_m13_4p_production_composition.py`.

M13-4P documentation changes are the reconciliation specification, execution
plan, and this report. Existing M13-4E source, tests, reports, plans, generated
coverage, project fixtures, and `.superpowers/sdd` changes in the dirty
worktree were classified as pre-existing unrelated worktree noise and were not
reverted or modified for this reconciliation.

## Remaining Findings

No M13-4P composition findings remain. Full M13-4 acceptance, Rotator V2, and
all broader capabilities listed as out of scope remain prohibited and are not
claimed here.

## Candidate Status

`M13_4P_RECONCILIATION_READY_FOR_INDEPENDENT_AUDIT`
