# M13-4P Independent Acceptance Audit

## Verdict

```text
M13_4P_INDEPENDENT_ACCEPTED
```

No CRITICAL or IMPORTANT findings were identified. The received candidate composes
the accepted M13-3 selection/replay and M13-4E promotion/verification workflows
through the real production root without a parallel authority path.

## Audit Independence

This audit did not implement M13-4P, alter production code, alter tests,
remediate findings, commit, tag, push, start M13-4, or start Rotator V2. The only
intentional repository write is this independent audit report. Candidate reports
were used for navigation only. All code-path conclusions and all listed gates
were independently inspected or rerun in this session.

## Input Authority

Read and applied:

- `docs/superpowers/specs/2026-09-07-m13-4p-production-composition-reconciliation.md`
- `docs/superpowers/plans/2026-09-07-m13-4p-production-composition-reconciliation.md`
- `docs/audit/MECHCAD_M13_4P_RECONCILIATION_REPORT.md`
- `docs/audit/MECHCAD_M13_4E_R12_INDEPENDENT_REAUDIT.md`
- `docs/superpowers/specs/2026-09-06-m13-4e-multi-joint-promotion-evidence-contract.md`
- `docs/superpowers/specs/2026-09-06-m13-4-representative-live-full-stack-capstone.md`
- `docs/superpowers/specs/2026-09-06-m13-4p-multi-joint-production-composition.md`

The accepted M13-4E R12 re-audit is upstream authority. Its durable-state
protection and original-compilation identity requirements remain intact.

## Repository / Worktree State

Before this report was written, `git status --short`, `git diff --stat`,
`git diff`, and `git diff --check` were run. `git diff --check` exited 0; its
only output was non-failing CRLF normalization warnings.

Classification of received changes:

- M13-4P production: `src/mechcad_harness/application.py`.
- Mixed pre-existing M13-4E plus M13-4P production: `src/mechcad_harness/candidates/promotion.py`. The accepted M13-4E route/lifecycle is pre-existing; the M13-4P delta is the narrow typed public delegation at `CandidatePromotionApplicationService.promote_selected_multi_joint_candidate`.
- M13-4P test: `tests/integration/test_m13_4p_production_composition.py`.
- M13-4P documentation: the M13-4P specification, plan, reconciliation report, and this report.
- Pre-existing M13-4E work: `src/mechcad_harness/candidates/__init__.py`, `promotion_artifacts.py`, `promotion_models.py`, the five M13-4E test files, and the M13-4E reports/plans/specification.
- Pre-existing unrelated noise: `.coverage`, `.superpowers/sdd/*`, historical M13-1/M13-4 documents, `err.txt`, `projects/`, and `src/mechcad-harness/`.

No unauthorized M13-4P semantic production change was found outside the two
authorized production files. No M10, CAD, state schema, M13-3 contract, legacy
promotion contract, or dependency file changed for M13-4P.

## Protected Surface Audit

The `application.py` diff contains imports and exactly three additive root
methods. The `promotion.py` M13-4P addition is the request-only public service
delegation; its established private M13-4E lifecycle is not duplicated by the
root. `promotion.py` has no M13-4P projection normalization, compilation
replacement, mapping-driven reordering, or generic proposal entrypoint.

## Public Production Surface

`ProductionApplication` exposes exactly these M13-4P public capabilities:

- `select_candidate_multi_joint(...)`
- `promote_selected_multi_joint_candidate(...)`
- `verify_multi_joint_promotion_application(...)`

The legacy `promote_selected_candidate(...)` remains a separate legacy method,
delegating only to the legacy service entry. It accepts no union and contains no
multi-joint dispatch. No `apply_multi_joint_proposal`, `run_candidate_pipeline`,
`promote_any_candidate`, or `verify_artifact_with_run` API exists.

## Selection Composition Audit

`ProductionApplication.select_candidate_multi_joint` first performs candidate
project binding. It then creates a local `result_replayer` closure and a local
`CandidateMultiJointSelectionService` using the existing
`candidate_currentness_service`; it does not retain either object. The root
constructor has no M13-4P candidate/CAD/bridge/result cache or retained replay
authority.

The focused route asserts that the root object's complete `__dict__` is
unchanged over selection and explicitly confirms the absence of `latest_run`,
`last_candidate`, `candidate_result_store`, `cad_realization`, and `bridge`.

## Trusted M10 Replay Audit

The local replayer in `application.py:2167-2187` performs the required path:

```text
candidate + supplied CAD realization + bridge + stored evaluation request
  -> reconstruct_m10_request()
  -> reconstructed request hash == stored M10 request hash
  -> _execute_candidate_v2_sweep()
  -> analyze_multi_joint_collision_sweep_v2()
  -> replay result hash == evaluation expected M10 result hash
  -> CandidateMultiJointM10Replay
  -> unchanged CandidateMultiJointSelectionService.select()
```

The re-execution passes the reconstructed model, ordered configurations, exact
pair scope, and both reconstructed tolerances. It does not reuse the in-memory
M10 result and introduces no M10 result database or ambient candidate geometry.
The foreign-candidate negative records the number of measurement executions
before the selection attempt and proves it is unchanged after the intended
candidate-project rejection. The valid-but-different replay-result negative
reaches the root's exact result-identity check.

## Promotion Composition Audit

`ProductionApplication.promote_selected_multi_joint_candidate` accepts only an
exact `CandidateMultiJointPromotionRequest`, checks project binding, and delegates
to `CandidatePromotionApplicationService.promote_selected_multi_joint_candidate`.
The service method accepts only that request type and immediately delegates to
`_promote_multi_joint_route`. Neither public method accepts readiness,
compilation, projection, mapping, proposal, canonical mechanism, run ID,
ArtifactStore, or manifest.

## M13-4E Preservation Audit

The accepted route remains authoritative:

```text
CandidateMultiJointPromotionRequest
  -> validate_multi_joint_readiness()
  -> original compile_multi_joint()
  -> typed decision artifact
  -> RunController / ChangeProposal / ChangeSet / ChangeEngine
  -> durable DesignState N+1
  -> typed result artifact and receipt
```

The root neither compiles nor applies a proposal itself. It does not introduce a
second lifecycle. The accepted M13-4E generic post-apply durable state reload
still loads the persisted revision and compares its canonical state hash before
issuing an N+1 partial receipt.

## Compilation Identity Audit

The representative test wraps the original `compile_multi_joint` return and
proves full typed equality with `receipt.compilation`, including exact
compilation hash, full projection equality and projection hash, and full mapping
equality. The compiler keeps projection order from the M13-3 realization/
projection and constructs mapping in ascending `candidate_instance_id` order.

Search and source inspection found no `_align_multi_joint_evidence_compilation`,
replacement compilation, projection normalization, or mapping-driven projection
reorder. The M13-4E full verifier still compares the exact mapping record to the
original compilation mapping, not only hashes or sets.

## Receipt Verifier Composition Audit

`ProductionApplication.verify_multi_joint_promotion_application` is read-only.
It accepts only the exact typed receipt, requires its decision artifact ID, and
uses no caller-selected run or ArtifactStore. It delegates the full decision,
result, state, invalidation, and run verification to the unchanged
`verify_multi_joint_promotion_application_result`.

## Exact-ID Locator Audit

The root creates `ArtifactStore(workspace, project_id=self.project_id,
run_id="m13-4p-decision-lookup")` and calls only
`read_verified_in_project(receipt.decision_artifact_id, expected_type=JSON)`.
That accepted locator enumerates run scopes internally, strict-verifies each
candidate artifact, and returns only one match. The root then requires the
located artifact to be in the root project, have a nonblank persisted `run_id`,
and use the `MULTI-JOINT-PROMOTION-DECISION-` namespace before creating a fresh
scoped ArtifactStore from that persisted run ID.

There is no root `glob`, `existing_in_project`, latest/first/only-run choice,
active-revision inference, direct run-directory lookup, or caller-selected scope.
The locator rejects missing, ambiguous, wrong JSON type/media metadata, wrong
project, blank run ID, and non-decision namespace before scoped verification
where the locator binding is available. Full M13-4E verification remains the
authority for the receipt/request and durable-chain bindings.

The ambiguous-ID test republishes the exact strict-valid decision bytes and
metadata into another valid run, producing two strict-valid matches. The locator
returns no unique match and the root rejects. The forged run-metadata test
modifies only stored metadata after a valid receipt; strict ArtifactStore
metadata/path/hash verification rejects the artifact, rather than an unrelated
fixture error.

## Durable State / Run Authority

The representative production route proves:

```text
receipt.applied_revision == source.revision + 1
receipt.applied_state_hash == state_hash(StateManager.load_revision(project_id, receipt.applied_revision))
```

The accepted full verifier additionally reloads the exact N+1 state, invalidation
record, and run selected from persisted decision-artifact metadata. It does not
trust `Run.active_revision` or `Run.active_state_hash` as durable state proof.

## Representative Production Route

`tests/integration/test_m13_4p_production_composition.py` uses
`ProductionApplication.create()` with real production persistence composition and
root APIs. It evaluates through production M10 v2, selects with independent
replay, constructs only the typed promotion input fixture, promotes through the
root, and verifies through the root.

The route observes project binding, source revision/state hash, evaluation and
selection identity, original compilation identity, decision/result artifact IDs,
applied revision/state hash, and final `PROMOTION_APPLIED`. The test does not
manually construct a selection service, orchestrate the compiler/ChangeEngine,
publish results, or sequence the full verifier outside the root.

## Negative Composition Tests

Focused negatives cover foreign candidate rejection before replay, a valid replay
result with a mismatching identity, legacy schema rejection of a multi-joint
request, exact-ID ambiguity using a strict-valid duplicate, and forged decision
metadata run ID. The legacy negative expects the intended
`CandidatePromotionRequest` Pydantic validation error, not an incidental error.

## Test Quality Audit

The complete route uses a small deterministic kinematic measure injected through
`ProductionApplication.create()` for hermetic integration coverage. It still
executes the production M10 v2 request construction and sweep path twice, as
asserted by configuration-counted measurement calls. Test monkeypatches only
observe the accepted private route/compiler return or inject a self-valid
different replay result; they do not replace selection, promotion, ChangeEngine,
artifact publication, state persistence, or full verification.

## Focused M13-4P Gate

```text
py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -q
8 passed in 15.50s
exit status: 0
passes: 8; failures: 0; errors: 0; skips: 0
M13_4P_REQUIRED_SKIPS = 0
```

## M13-4E Regression

```text
py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q
116 passed in 138.09s
exit status: 0
passes: 116; failures: 0; errors: 0; skips: 0
```

## M13-3 / Predecessor Regression

```text
py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q
75 passed in 40.03s
exit status: 0
passes: 75; failures: 0; errors: 0; skips: 0
```

## Full-Suite Evidence

The candidate's reported full-suite result was not credited as durable evidence.
An initial independent invocation was externally aborted before completion and
was discarded. A fresh rerun on the received M13-4P tree completed:

```text
py -3 -m pytest -q -rs
2819 passed, 34 skipped in 3361.92s (0:56:01)
exit status: 0
failures: 0; errors: 0
```

## Skip Audit

The full-suite 34 skips are all optional-environment categories:

- 14 structural profile unavailable.
- 9 FreeCAD or FreeCADCmd unavailable.
- 6 OpenCode live validation opt-in.
- 5 materials extra unavailable.

No M13-4P test skipped.

## Static Audit

```text
py -3 -m compileall src tests
exit status: 0

git diff --check
exit status: 0
```

The targeted static searches covered the root methods, selection service,
request reconstruction, M10 v2 callback, compiler, exact-ID locator,
`ArtifactStore`, `RunController`, `StateManager`, `latest_run`, `glob`,
`SimpleNamespace`, `Any`, and `dict`. Relevant `glob` and generic-container
occurrences are pre-existing unrelated production functionality or accepted
ArtifactStore internal locator behavior, not the M13-4P root route.

## Findings

### CRITICAL

None.

### IMPORTANT

None.

### MINOR

None.

### NOTES

- The candidate report's full-suite result was not relied upon. This audit's fresh rerun is the acceptance evidence.
- The initial independent full-suite invocation was externally aborted and is not credited.
- Test execution updates the pre-existing `.coverage` worktree noise; it is not an M13-4P semantic change.

## Acceptance Decision

All M13-4P acceptance requirements are satisfied. The production root composes
the accepted selection replay, M13-4E typed promotion lifecycle, and exact-ID
receipt verifier without a generic bypass, parallel authority, result store, or
heuristic run discovery.

```text
M13_4P_INDEPENDENT_ACCEPTED
M13_4P_ACCEPTANCE_STATUS = ACCEPTED
```

## Downstream Authorization

```text
M13_4_MAY_RESUME = YES
ROTATOR_V2_MAY_RESUME = NO
```
