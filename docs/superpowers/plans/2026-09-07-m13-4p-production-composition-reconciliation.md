# M13-4P Production Composition Reconciliation Implementation Plan

> **Execution status:** Complete. The red-state instructions below describe the
> intended TDD sequence; they were not rerun by removing the already-present
> implementation. Focused tests and all required regression/static gates were
> run against the final working tree.

**Goal:** Expose accepted M13-3 multi-joint selection and accepted M13-4E promotion/result verification through the real `ProductionApplication` without changing their contracts or creating a parallel lifecycle.

**Architecture:** Add a call-scoped trusted M10 replay closure behind a typed selection method and a typed delegation to the accepted M13-4E route. The receipt-only root verifier first uses the existing trusted exact-ID project artifact locator, then scopes a fresh `ArtifactStore` from persisted decision-artifact metadata and delegates to the accepted M13-4E full verifier.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing `StateManager`, `RunController`, `ChangeEngine`, `ArtifactStore`, `EvidenceStore`, M13-3 selection/M10 types, and M13-4E promotion services.

## Global Constraints

- Preserve the accepted M13-4E compilation, projection, mapping, artifact, lifecycle, and durable post-apply semantics exactly.
- `CandidateMultiJointSelectionService.select()` keeps its accepted signature and remains unchanged.
- The legacy `ProductionApplication.promote_selected_candidate()` and all legacy schemas/hashes remain behavior-compatible; no union dispatch is permitted.
- Do not retain candidate CAD realization, bridge, reconstructed requests, or results on `ProductionApplication` or in a new store.
- Do not add an M10 result store, latest-run lookup, run globbing, ambient candidate state, a generic promotion helper, or a second application lifecycle.
- Production entrypoints are typed and accept only the frozen input types in the reconciliation specification.
- Authorized production files are `src/mechcad_harness/application.py` and `src/mechcad_harness/candidates/promotion.py` only.
- Do not modify M13-3 contracts, M13-4E models/artifacts/route semantics, M10, CAD, state schemas, legacy promotion contracts, Rotator V2, or dependencies.
- No commit, tag, push, M13-4 acceptance, or Rotator V2 work is authorized.
- The root may use `ArtifactStore.read_verified_in_project()` only as an exact-ID locator for the receipt decision artifact; it must reject missing or ambiguous matches and must not choose a run.
- The locator result's persisted nonblank `EngineeringArtifact.run_id` is the sole root-level source for the fresh scoped `ArtifactStore` supplied to the accepted M13-4E verifier.

---

## File Map

- Modify `src/mechcad_harness/application.py`: import accepted multi-joint types, compose the call-scoped selection boundary, and expose typed root delegations.
- Modify `src/mechcad_harness/candidates/promotion.py`: add an additive typed service entry that delegates only to `_promote_multi_joint_route()`.
- Create `tests/integration/test_m13_4p_production_composition.py`: real-production-root positive and narrow composition-negative tests.
- Create `docs/audit/MECHCAD_M13_4P_RECONCILIATION_REPORT.md`: final evidence only after all implementation and regression gates pass.

### Task 1: Freeze The Public Root Selection Boundary

**Files:**
- Modify: `src/mechcad_harness/application.py`
- Test: `tests/integration/test_m13_4p_production_composition.py`

**Consumes:** Existing `CandidateCadRealization`, `PhysicalToM10V2Bridge`, `MechanicalDesignCandidate`, `CandidateMultiJointM10EvaluationRequest`, `CandidateMultiJointM10Evaluation`, `CandidateMultiJointM10Replay`, and `CandidateMultiJointSelectionService`.

**Produces:**

```python
ProductionApplication.select_candidate_multi_joint(
    candidate: MechanicalDesignCandidate,
    cad_realization: CandidateCadRealization,
    bridge: PhysicalToM10V2Bridge,
    request: CandidateMultiJointM10EvaluationRequest,
    evaluation: CandidateMultiJointM10Evaluation,
    selector_identity: str,
    rationale: str,
) -> CandidateMultiJointSelection
```

- [x] **Step 1: Add the production-root integration tests.**

```python
def test_root_selection_replays_typed_request_through_production_m10(tmp_path):
    app, candidate, cad_realization, bridge, request, evaluation, calls = _route_inputs(tmp_path)

    selection = app.select_candidate_multi_joint(
        candidate,
        cad_realization,
        bridge,
        request,
        evaluation,
        selector_identity="m13-4p-selector",
        rationale="independent production replay",
    )

    assert selection.evaluation_hash == evaluation.evaluation_hash
    assert selection.m10_v2_result_hash == evaluation.m10_v2_result_hash
    assert len(calls) == 2  # evaluation plus independent selection replay


def test_root_selection_does_not_retain_per_candidate_replay_inputs(tmp_path):
    app, candidate, cad_realization, bridge, request, evaluation, _ = _route_inputs(tmp_path)

    app.select_candidate_multi_joint(
        candidate, cad_realization, bridge, request, evaluation, "selector", "replay"
    )

    assert "cad_realization" not in vars(app)
    assert "bridge" not in vars(app)
    assert "replayed_request" not in vars(app)
    assert "replay_result" not in vars(app)
```

- [x] **Step 2: Run the focused selection tests against the implemented API.**

Run: `py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -k "root_selection" -q`

Expected: failure because `ProductionApplication.select_candidate_multi_joint` does not exist.

- [x] **Step 3: Add only the required imports and typed root method.**

Import the exact public models from their existing modules/package exports. The
method must project-check `candidate` through `_require_candidate_project()`,
then create a local closure and a local `CandidateMultiJointSelectionService`:

```python
def result_replayer(
    replay_candidate: MechanicalDesignCandidate,
    replay_request: CandidateMultiJointM10EvaluationRequest,
    replay_evaluation: CandidateMultiJointM10Evaluation,
) -> CandidateMultiJointM10Replay:
    reconstructed = self.candidate_multi_joint_m10_evaluation_service.reconstruct_m10_request(
        replay_candidate, cad_realization, bridge, replay_request
    )
    if reconstructed.request_hash != replay_request.m10_v2_request_hash:
        raise ValueError("candidate multi-joint selection replay request identity mismatch")
    result = self._execute_candidate_v2_sweep(
        source_revision=replay_request.source_revision,
        source_state_hash=replay_request.source_state_hash,
        assembly=cad_realization.assembly,
        model=reconstructed.model,
        configurations=reconstructed.configurations,
        exact_pair_scope=reconstructed.exact_pair_scope,
        volume_tolerance_mm3=reconstructed.volume_tolerance_mm3,
        distance_tolerance_mm=reconstructed.distance_tolerance_mm,
    )
    if result.result_hash != replay_evaluation.m10_v2_result_hash:
        raise ValueError("candidate multi-joint selection replay result identity mismatch")
    return CandidateMultiJointM10Replay(reconstructed, result)

return CandidateMultiJointSelectionService(
    project_id=self.project_id,
    currentness_verifier=self.candidate_currentness_service,
    result_replayer=result_replayer,
).select(candidate, request, evaluation, selector_identity, rationale)
```

Do not add a `ProductionApplication` attribute for the service or closure. Do
not call `execute()` because selection must return the reconstructed M10 request
and independently replayed result to its accepted service contract.

- [x] **Step 4: Add narrow selection-boundary negatives.**

```python
def test_root_selection_rejects_foreign_candidate_before_replay(tmp_path):
    app, candidate, cad_realization, bridge, request, evaluation, calls = _route_inputs(tmp_path)
    foreign = _candidate_for_project(candidate, "PRJ-foreign")
    before = len(calls)

    with pytest.raises(CandidateIntegrityError, match="project"):
        app.select_candidate_multi_joint(
            foreign, cad_realization, bridge, request, evaluation, "selector", "replay"
        )

    assert len(calls) == before


def test_root_selection_rejects_replay_result_not_bound_to_evaluation(tmp_path, monkeypatch):
    app, candidate, cad_realization, bridge, request, evaluation, _ = _route_inputs(tmp_path)
    monkeypatch.setattr(app, "_execute_candidate_v2_sweep", _different_valid_v2_result)

    with pytest.raises(ValueError, match="replay result identity"):
        app.select_candidate_multi_joint(
            candidate, cad_realization, bridge, request, evaluation, "selector", "replay"
        )
```

The result mismatch fixture must be a valid v2 result for the reconstructed
request but have a different result hash, so the assertion reaches the root
composition binding rather than a malformed-result failure.

- [x] **Step 5: Run the selection tests to verify they pass.**

Run: `py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -k "root_selection" -q`

Expected: all selected tests pass with zero skips.

### Task 2: Expose The Typed M13-4E Promotion Delegation

**Files:**
- Modify: `src/mechcad_harness/candidates/promotion.py`
- Modify: `src/mechcad_harness/application.py`
- Test: `tests/integration/test_m13_4p_production_composition.py`

**Consumes:** Accepted `CandidateMultiJointPromotionRequest`,
`CandidateMultiJointPromotionApplicationResult`, and private accepted
`CandidatePromotionApplicationService._promote_multi_joint_route()`.

**Produces:**

```python
CandidatePromotionApplicationService.promote_selected_multi_joint_candidate(
    request: CandidateMultiJointPromotionRequest,
) -> CandidateMultiJointPromotionApplicationResult

ProductionApplication.promote_selected_multi_joint_candidate(
    request: CandidateMultiJointPromotionRequest,
) -> CandidateMultiJointPromotionApplicationResult
```

- [x] **Step 1: Add the root-promotion delegation tests.**

```python
def test_root_multi_joint_promotion_uses_accepted_typed_route(tmp_path, monkeypatch):
    app, promotion_request = _selected_multi_joint_promotion_request(tmp_path)
    calls = []
    original = app.promotion_application_service._promote_multi_joint_route

    def observe(request):
        calls.append(request)
        return original(request)

    monkeypatch.setattr(app.promotion_application_service, "_promote_multi_joint_route", observe)
    receipt = app.promote_selected_multi_joint_candidate(promotion_request)

    assert calls == [promotion_request]
    assert receipt.request == promotion_request
    assert receipt.compilation is not None
    assert receipt.status.value == "promotion_applied"


def test_legacy_promotion_entry_does_not_dispatch_multi_joint_request(tmp_path):
    app, promotion_request = _selected_multi_joint_promotion_request(tmp_path)

    with pytest.raises(ValidationError, match="CandidatePromotionRequest"):
        app.promote_selected_candidate(promotion_request)
```

The legacy root's existing project check accepts the same project ID, then its
unchanged legacy route rejects the typed multi-joint value while constructing its
`CandidatePromotionApplicationResult.request: CandidatePromotionRequest | None`.
The exact `CandidatePromotionRequest` validation error, rather than a broad
incidental exception, proves there is no multi-joint dispatch.

- [x] **Step 2: Run the promotion tests against the implemented typed APIs.**

Run: `py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -k "root_multi_joint_promotion or legacy_promotion_entry" -q`

Expected: failure because the new typed service/root entrypoints do not exist.

- [x] **Step 3: Add the minimal typed service delegation.**

Add the public service method without changing `_promote_multi_joint_route()`:

```python
def promote_selected_multi_joint_candidate(
    self, request: CandidateMultiJointPromotionRequest
) -> CandidateMultiJointPromotionApplicationResult:
    if type(request) is not CandidateMultiJointPromotionRequest:
        raise ValueError("multi-joint promotion request must be a typed request")
    return self._promote_multi_joint_route(request)
```

No parameter for readiness, compilation, proposal, mapping, projection, run,
artifact, or canonical mechanism is permitted.

- [x] **Step 4: Add the minimal typed root delegation.**

```python
def promote_selected_multi_joint_candidate(
    self, request: CandidateMultiJointPromotionRequest
) -> CandidateMultiJointPromotionApplicationResult:
    if type(request) is not CandidateMultiJointPromotionRequest:
        raise CandidateIntegrityError("multi-joint promotion request must be typed")
    self._require_promotion_project(request)
    return self.promotion_application_service.promote_selected_multi_joint_candidate(request)
```

Keep `promote_selected_candidate()` byte-for-byte behaviorally unchanged. Do
not call `compile_multi_joint()` from the root.

- [x] **Step 5: Extend the positive assertion to preserve original compilation identity.**

Capture the compiler return by narrowly observing
`candidate_promotion_compiler.compile_multi_joint`, then assert:

```python
assert receipt.compilation == compiled[0]
assert receipt.compilation.compilation_hash == compiled[0].compilation_hash
assert receipt.compilation.projection == compiled[0].projection
assert receipt.compilation.projection.projection_hash == compiled[0].projection.projection_hash
assert receipt.compilation.mapping == compiled[0].mapping
```

- [x] **Step 6: Run the promotion tests to verify they pass.**

Run: `py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -k "root_multi_joint_promotion or legacy_promotion_entry" -q`

Expected: all selected tests pass with zero skips.

### Task 3: Expose Thin Durable Receipt Verification

**Files:**
- Modify: `src/mechcad_harness/application.py`
- Test: `tests/integration/test_m13_4p_production_composition.py`

**Consumes:** Accepted
`verify_multi_joint_promotion_application_result()`,
`CandidateMultiJointPromotionApplicationResult`, `PromotionManifestService`,
`ArtifactStore`, `StateManager`, `EvidenceStore`, and `RunController`.

**Produces:**

```python
ProductionApplication.verify_multi_joint_promotion_application(
    receipt: CandidateMultiJointPromotionApplicationResult,
) -> None
```

- [x] **Step 1: Add the receipt-only root-verifier tests.**

```python
def test_root_verifier_locates_decision_scope_from_exact_artifact_id(tmp_path):
    app, receipt = _completed_multi_joint_receipt(tmp_path)

    app.verify_multi_joint_promotion_application(receipt)


def test_root_verifier_rejects_ambiguous_decision_artifact_id(tmp_path):
    app, receipt = _completed_multi_joint_receipt(tmp_path)
    _copy_strict_valid_decision_artifact_to_another_run(tmp_path, receipt)

    with pytest.raises(ValueError, match="decision artifact.*missing|ambiguous"):
        app.verify_multi_joint_promotion_application(receipt)
```

The duplicate must be strict-valid in both runs so
`read_verified_in_project()` returns no locator result due to ambiguity.

- [x] **Step 2: Run the root-verifier tests against the implemented API.**

Run: `py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -k "root_verifier" -q`

Expected: failure because `ProductionApplication.verify_multi_joint_promotion_application` does not exist.

- [x] **Step 3: Implement the accepted exact-ID locator and verifier delegation.**

```python
def verify_multi_joint_promotion_application(
    self, receipt: CandidateMultiJointPromotionApplicationResult
) -> None:
    if type(receipt) is not CandidateMultiJointPromotionApplicationResult:
        raise CandidateIntegrityError("multi-joint promotion receipt must be typed")
    if receipt.decision_artifact_id is None:
        raise CandidateIntegrityError("multi-joint promotion receipt has no decision artifact")
    locator = ArtifactStore(
        self.state_manager.workspace,
        project_id=self.project_id,
        run_id="m13-4p-decision-lookup",
    )
    resolved = locator.read_verified_in_project(
        receipt.decision_artifact_id, expected_type=ArtifactType.JSON
    )
    if resolved is None:
        raise CandidateIntegrityError("multi-joint decision artifact is missing or ambiguous")
    decision_artifact, _ = resolved
    if (
        decision_artifact.project_id != self.project_id
        or not decision_artifact.run_id.strip()
        or not decision_artifact.artifact_id.startswith("MULTI-JOINT-PROMOTION-DECISION-")
    ):
        raise CandidateIntegrityError("multi-joint decision artifact locator binding mismatch")
    manifest_store = ArtifactStore(
        self.state_manager.workspace,
        project_id=self.project_id,
        run_id=decision_artifact.run_id,
    )
    verify_multi_joint_promotion_application_result(
        receipt,
        manifest_service=self.promotion_manifest_service,
        manifest_store=manifest_store,
        state_manager=self.state_manager,
        evidence_store=self.evidence_store,
        run_controller=self.run_controller,
    )
```

The locator supplies only persisted decision metadata. The accepted full verifier
must still resolve the decision/result and validate run, state, and invalidation
bindings. Do not call `existing_in_project`, access run directories directly, or
choose a run.

- [x] **Step 4: Add a forged-metadata/run-scope negative.**

```python
def test_root_verifier_rejects_forged_decision_metadata_run_id(tmp_path):
    app, receipt = _completed_multi_joint_receipt(tmp_path)
    _rewrite_decision_artifact_run_id(tmp_path, receipt, "RUN-forged")

    with pytest.raises(ValueError, match="artifact|run|binding"):
        app.verify_multi_joint_promotion_application(receipt)
```

The locator's strict byte/path/metadata checks reject an inconsistent artifact;
the accepted M13-4E full verifier rejects any surviving scoped run mismatch.

- [x] **Step 5: Run the verifier tests to verify they pass.**

Run: `py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -k "root_verifier" -q`

Expected: all selected tests pass with zero skips. Do not modify
`promotion_artifacts.py`, receipt schemas, artifact storage, or accepted M13-4E
verifier behavior.

### Task 4: Prove The Complete Production Composition Route

**Files:**
- Modify: `tests/integration/test_m13_4p_production_composition.py`

**Consumes:** The three root APIs from Tasks 1-3 and an existing generic M13-3
candidate/CAD/bridge fixture adapted to use `ProductionApplication.create()`.

**Produces:** A focused positive route that records all required production
identities without using a test-only orchestrator.

- [x] **Step 1: Add the complete route test through `ProductionApplication.create()`.**

```python
def test_production_root_composes_multi_joint_selection_promotion_and_verification(tmp_path):
    app, candidate, cad_realization, bridge, request, evaluation = _evaluated_route_inputs(tmp_path)
    source = app.load_state()

    selection = app.select_candidate_multi_joint(
        candidate, cad_realization, bridge, request, evaluation, "m13-4p-selector", "production replay"
    )
    promotion_request = _promotion_request(candidate, request, evaluation, selection, source)
    receipt = app.promote_selected_multi_joint_candidate(promotion_request)
    app.verify_multi_joint_promotion_application(receipt)

    assert receipt.status.value == "promotion_applied"
    assert receipt.request.request_hash == promotion_request.request_hash
    assert receipt.readiness.source_revision == source.revision
    assert receipt.compilation.proposal.base_revision == source.revision
    assert receipt.decision_artifact_id is not None
    assert receipt.result_artifact_id is not None
    assert receipt.applied_revision == source.revision + 1
    persisted = app.state_manager.load_revision(app.project_id, receipt.applied_revision)
    assert receipt.applied_state_hash == state_hash(persisted)
```

Resolve the decision artifact through the same project locator in the test only
to record its metadata run ID; do not retain a pre-promotion run object.

- [x] **Step 2: Run the complete route test.**

Run: `py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -k "production_root_composes" -q`

Expected: pass with zero skips, recording project ID, decision-metadata run ID,
base revision/hash, request/selection/compilation identities, decision/result
artifact IDs, applied revision/hash, and final status.

- [x] **Step 3: Add static architecture assertions.**

Assert the implementation has exactly the three new public root names and that
`ProductionApplication` has no attributes named `latest_run`, `last_candidate`,
`candidate_result_store`, `cad_realization`, or `bridge`. Test only public
behavior and direct object attributes; do not inspect private source text as a
substitute for functional tests.

- [x] **Step 4: Run the complete focused M13-4P suite.**

Run: `py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -q`

Expected: all M13-4P tests pass with zero skips. Record pass count, skip count,
and elapsed time for the report.

### Task 5: Regression, Static Audit, And Reconciliation Report

**Files:**
- Create: `docs/audit/MECHCAD_M13_4P_RECONCILIATION_REPORT.md`

- [x] **Step 1: Run the exact M13-4E regression gate.**

Run: `py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q`

Expected: `116 passed`, zero skips.

- [x] **Step 2: Run the exact M13-3/predecessor regression gate.**

Run: `py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q`

Expected: `75 passed`, zero skips.

- [x] **Step 3: Run the full regression with durable captured output.**

Run: `py -3 -m pytest -q -rs`

Timeout: at least 6000 seconds.

Expected: zero failures and errors; record exact pass/skip counts, elapsed time,
and every skip category. Required M13-4P skips are zero.

- [x] **Step 4: Run static and architecture gates.**

Run: `py -3 -m compileall src tests`

Expected: exit 0.

Run: `git diff --check`

Expected: exit 0; non-failing CRLF warnings may be recorded separately.

Run targeted `rg` searches for `ProductionApplication`,
`promote_multi_joint`, `compile_multi_joint`,
`verify_multi_joint_promotion`, `resolve_multi_joint_result`,
`apply_approved_proposal`, `StateManager`, `RunController`, `ArtifactStore`,
`EvidenceStore`, `latest_run`, `glob`, `SimpleNamespace`, `Any`, and `dict`.

Inspect acceptance-relevant occurrences to prove one root route, no generic
promotion bypass, no latest/glob discovery, no ambient candidate cache, and no
M13-4E identity normalization.

- [x] **Step 5: Audit the protected worktree surface.**

Run: `git status --short`

Run: `git diff --stat`

Run: `git diff`

Classify each changed file as M13-4P production, M13-4P test,
documentation/report, pre-existing unrelated noise, or unexpected change. Do
not revert pre-existing changes. Stop for investigation if an unexpected
production change affects the route.

- [x] **Step 6: Write the reconciliation report after all gates pass.**

Create `docs/audit/MECHCAD_M13_4P_RECONCILIATION_REPORT.md` with exactly these
sections:

```text
# M13-4P Production Composition Reconciliation

## Input Authority
## Historical Architecture Gap
## Current Production Route Before Reconciliation
## Gap Classification
## Implementation Scope
## Production Composition Changes
## Final Production Route
## M13-4E Contract Preservation
## Run / Artifact / State Authority
## M10 v2 Boundary
## Representative Integration Proof
## Negative Composition Tests
## Focused M13-4P Gate
## M13-4E Regression
## M13-3 / Predecessor Regression
## Full Suite
## Skip Audit
## Static Audit
## Protected Surface Audit
## Remaining Findings
## Candidate Status
```

The report must list the exact commands, outputs, elapsed times, file changes,
and required identity observations. It must retain `M13_4_MAY_RESUME = NO` and
`ROTATOR_V2_MAY_RESUME = NO` and may state only
`M13_4P_RECONCILIATION_READY_FOR_INDEPENDENT_AUDIT`.

## Plan Self-Review

- The selection task keeps the M13-3 selection-service signature unchanged and
  limits CAD/bridge lifetime to one root-method call.
- The promotion task adds a typed request-only route without legacy union
  dispatch or a generic proposal application API.
- The verifier task uses the accepted exact-ID project locator only to obtain
  persisted decision metadata, then delegates unchanged to M13-4E verification.
- The integration test requires `ProductionApplication.create()` and real
  persistence services rather than a deep-service test fixture.
- Regression/static/report tasks preserve M13-4E and M13-3 gates and prohibit
  an M13-4 acceptance claim.
- No commit step appears because this milestone forbids commits.
