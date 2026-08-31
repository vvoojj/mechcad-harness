# M12-6 Live End-to-End Physical Mechanism Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce durable, real-backend M12-6 acceptance evidence for the bounded
direct-drive and external-spur promotion workflows without adding production
capability.

**Architecture:** Add dedicated integration tests that create only initial
fixture authority and execute all engineering stages through the existing
`ProductionApplication` surface. The direct path uses its public promoted
verification method, while a fresh application process boundary resolves durable
promotion provenance before candidate-independent canonical CAD/M10 reruns.
Existing M12-3/4/5 capstones remain unchanged predecessor regressions.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, FreeCAD 1.1 command-line
runtime, existing ArtifactStore/EvidenceStore/RunController/ChangeEngine services.

## Global Constraints

- This is acceptance-only work. **Expected production files changed: NONE.**
- Do not add a workflow orchestrator, registry, promotion store, acceptance store,
  canonical marker, or state-mutation path.
- Do not edit M12-3, M12-4, or M12-5 capstones to represent M12-6 evidence.
- Use `StateManager.create_project()` only for initial acceptance-fixture bootstrap;
  all later canonical changes use `RunController`/`ChangeEngine` through accepted
  production paths.
- Synthetic values must be labeled **M12-6 ACCEPTANCE FIXTURE SOURCE AUTHORITY**;
  never claim catalog or manufacturer truth.
- Use real composed FreeCAD for positive candidate and canonical M10 paths. Do not
  accept a deterministic/mocked provider as live evidence.
- Keep comparison explicit and optional. Never auto-select or substitute rank 1.
- External-spur `VERIFIED` covers only its declared output-joint obligation. Do
  not claim coupled gear motion, phase, backlash, counter-rotation, or internal
  transmission clearance.
- Promotion must remain `CandidatePromotionApplicationService` ->
  `RunController.apply_approved_proposal()` -> `ChangeEngine`; no direct
  ChangeEngine call from M12-6 orchestration.
- Preserve unrelated dirty/untracked files. Do not commit, tag, push, release
  harden, or start M13.
- If a production change seems required, stop before editing and classify it as
  `INTEGRATION_FIX`, `PREDECESSOR_REGRESSION_FIX`,
  `ACCEPTANCE_EVIDENCE_SUPPORT`, or `NEW_CAPABILITY`. Return for review for the
  first three; return `M12_6_BLOCKED_BY_OUT_OF_SCOPE_CAPABILITY` for the last.

---

## Verified Current Contracts

The plan is based on current code, not remembered APIs:

| Contract | Current implementation |
| --- | --- |
| Production factory | `src/mechcad_harness/application.py:653-709`, `ProductionApplication.create(workspace, project_id, agent_adapter, *, ownership_path, dependency_path, additional_tool_registrations=(), kinematic_measure=None)` |
| M12-3 production entrypoint | `application.py:1759-1795`, `realize_and_evaluate_revolute_drive(request, policy, template_input, requirements)` |
| Candidate CAD/evaluation/comparison/selection | `application.py:1797-1810`, `1951-2035`, `2037-2068` |
| Promotion/reconstruction/public verification | `application.py:1817-1839`, `promote_selected_candidate`, `reconstruct_promoted_mechanism`, `verify_promoted_mechanism` |
| Candidate request/policy | `src/mechcad_harness/candidates/models.py:319-364` |
| Promotion manifests | `src/mechcad_harness/candidates/promotion_artifacts.py:143-178`, `340-375`, `546-568` |
| Run-scoped/project-wide artifact trust | `src/mechcad_harness/artifacts/storage.py:78-137` |
| Canonical reconstruction/CAD/M10/scope comparison | `candidates/canonical_mechanism.py:170-302`, `canonical_cad.py:318-508`, `canonical_m10.py:579-810` |
| M11 handoff | `candidates/m11_handoff.py:62-177`, `649-681` |
| Bootstrap and mutation | `state/manager.py:118-216`, `runs/controller.py:179-223`, `changes/engine.py:108-156` |
| Invalidation/Evidence | `dependency/graph.py:152-168`, `dependency/storage.py:39-130` |

### Fresh-Restart Discovery Finding

No contract blocker exists. Retain only the result artifact ID plus expected
project/revision/hash/mechanism identifiers as durable locators. A fresh app must:

1. call `StateManager.load_revision(project_id, promoted_revision)` and compare
   `state_hash(state)` with the retained expected promoted hash;
2. construct `ArtifactStore(workspace, project_id=project_id, run_id="project-lookup")`;
3. resolve the result metadata with `existing_in_project(result_artifact_id)`.
   This succeeds only for one trusted match across project runs; ambiguity returns
   `None` (`artifacts/storage.py:82-103`);
4. construct `ArtifactStore(workspace, project_id=project_id,
   run_id=result_artifact.run_id)` and call
   `PromotionManifestService.resolve_result(store, result_artifact_id)`;
5. use only `fresh_result.decision_artifact_id` and
   `fresh_result.decision_artifact_hash` to call
   `PromotionManifestService.resolve_decision(store, fresh_result.decision_artifact_id)`;
6. verify the resolved decision artifact metadata hash matches the result
   manifest's declared hash, then use its projection, scope projection, and
   mapping only as audit inputs;
7. call `fresh_app.reconstruct_promoted_mechanism(revision=promoted_revision,
   state_hash=expected_promoted_hash, mechanism_id=canonical_mechanism_id)`,
   followed by composed canonical CAD and M10 services.

`PromotionManifestService.resolve_result` already resolves and validates the
referenced decision manifest (`promotion_artifacts.py:546-568`). No new discovery
store or current-promotion pointer is required.

`ArtifactStore.__init__` (`artifacts/storage.py:29-34`) only validates and stores
the workspace/project/run identifiers. It creates no directory, run metadata, or
artifact state; only `publish()` creates an artifact directory (`:43-76`). The
`project-lookup` sentinel is therefore an acceptable side-effect-free receiver
for `existing_in_project()`. Add a focused assertion that constructing this lookup
store and resolving an artifact does not add a run directory or RunController
record.

### ProductionApplication Restart Finding

`ProductionApplication.create` reconstructs StateManager, DependencyGraph,
EvidenceStore, OwnershipPolicy, ChangeEngine, RunController, ToolRegistry,
ToolBroker, agent services, candidate services, and CAD/M10/M11 composition from
workspace/configuration plus a newly supplied adapter. The restart test retains
only: workspace path, ownership/dependency config paths, project ID, promoted
revision/hash, canonical mechanism ID, result-manifest artifact ID, and scalar
semantic hashes for assertions. It must instantiate a new adapter and call
`ProductionApplication.create(workspace, project_id, adapter,
ownership_path=ownership_path, dependency_path=dependency_path)`; it may not
reuse the prior app, services,
application result, compilation, manifest objects, candidate objects, or
closures that retain them.

## Planned File Structure

| File | Responsibility |
| --- | --- |
| `tests/integration/m12_6_acceptance_fixtures.py` | Initial-state bootstrap, explicit fixture authority/specification inputs, trusted STEP publication, and fresh application construction only. It never executes or returns engineering outcomes. |
| `tests/integration/test_m12_6_end_to_end_direct_drive.py` | Primary direct-drive production flow, public promoted verification, durable manifest chain, restart, round trip, M11 eligibility, identity capture. |
| `tests/integration/test_m12_6_end_to_end_external_spur.py` | Positive spur `VERIFIED`, comparison/no-comparison/non-top selection, tie behavior where practical, and transmission limitations. |
| `tests/integration/test_m12_6_end_to_end_failures.py` | Cross-stage rejection/currentness/tamper/replay/target/joint/obligation/invalidation cases. |
| `docs/audit/MECHCAD_M12_6_SYSTEM_ACCEPTANCE.md` | Created only after all acceptance gates pass; durable audit report, never canonical authority. |

No source file under `src/mechcad_harness/` is planned.

### Task 1: Establish Fixture-Authority Boundaries

**Files:**
- Create: `tests/integration/m12_6_acceptance_fixtures.py`
- Test: `tests/integration/test_m12_6_end_to_end_direct_drive.py`

**Interfaces:**
- Consumes: `StateManager.create_project`, `ProductionApplication.create`,
  `CandidateSynthesisRequest`, `CandidateSynthesisPolicy`, M12-3 input models,
  and `ArtifactStore.publish`.
- Produces: initial N=1 `DesignState`, source-bound request/policy/template/
  requirements inputs, trusted source STEP *inputs*, and fresh production app
  setup. It produces no candidate, M12-3 result, CAD realization, M10 result,
  evaluation, comparison, selection, promotion, or canonical verification.

- [ ] **Step 1: Add fixture-boundary tests before the helper**

  Add assertions in the direct-drive module that the helper's values are source
  input models and source artifacts, then execute M12-3 in the test body:

  ```python
  fixture = bootstrap_direct_drive_fixture(tmp_path)
  assert fixture.source.revision == 1
  assert fixture.source_label == "M12-6 ACCEPTANCE FIXTURE SOURCE AUTHORITY"
  assert fixture.source_artifacts["output-hub"].artifact_type is ArtifactType.STEP

  outcome = fixture.app.realize_and_evaluate_revolute_drive(
      request=fixture.synthesis_request,
      policy=fixture.synthesis_policy,
      template_input=fixture.template_input,
      requirements=fixture.requirements,
  )
  assert outcome.evaluation is not None
  ```

- [ ] **Step 2: Run the boundary test to verify the fixture helper is absent**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_direct_drive.py -q`

  Expected: collection failure for `m12_6_acceptance_fixtures` before helper
  implementation.

- [ ] **Step 3: Implement bootstrap-only fixture helpers**

  Implement helpers with this narrow shape:

  ```python
  def bootstrap_direct_drive_fixture(tmp_path) -> DirectDriveFixture:
      # M12-6 ACCEPTANCE FIXTURE SOURCE AUTHORITY only.
      workspace, ownership_path, dependency_path = write_project_configuration(tmp_path)
      StateManager(workspace).create_project(PROJECT_DIRECT, direct_drive_state())
      app = ProductionApplication.create(
          workspace, PROJECT_DIRECT, UninvokedAcceptanceAdapter(),
          ownership_path=ownership_path, dependency_path=dependency_path,
      )
      source = app.load_state()
      artifacts = publish_source_step_inputs(app, source)
      return DirectDriveFixture(
          app=app, source=source, source_artifacts=artifacts,
          synthesis_request=build_synthesis_request(source),
          synthesis_policy=build_direct_policy(),
          template_input=build_direct_template(artifacts),
          requirements=build_direct_requirements(source),
          ownership_path=ownership_path, dependency_path=dependency_path,
          source_label="M12-6 ACCEPTANCE FIXTURE SOURCE AUTHORITY",
      )
  ```

   `StateManager.create_project` is the only bootstrap mutation. The helper must
   not write revision/current JSON directly or call candidate/evaluation/promotion
   services.

  Define the production-composition adapter as a fail-fast test boundary and
  return the same adapter instance only for post-execution call-count assertions:

  ```python
  class UninvokedAcceptanceAdapter:
      def __init__(self):
          self.call_count = 0

      @property
      def identity(self):
          return "m12-6-acceptance-uninvoked"

      def invoke(self, request):
          self.call_count += 1
          raise AssertionError("M12-6 acceptance must not invoke an agent adapter")
  ```

  After every positive direct/spur production chain, assert
  `fixture.acceptance_adapter.call_count == 0`. The adapter must never return a
  candidate, engineering value, CAD/M10 result, selection, proposal, or
  verification result.

  Publish each trusted source STEP by reusing the accepted M12-4 input-fixture
  pattern from `tests/integration/test_m12_candidate_cad_m10_production.py:944-971`:
  load N/HN, call `application.create_run().run`, generate the bounded source
  `CadPartProgram` with:

  ```python
  generated = FreeCADBackend().generate_program(
      program,
      application.state_manager.workspace,
      project_id=application.project_id,
      run_id=source_run.run_id,
      revision=source.revision,
      state_hash=source.state_hash,
  )
  artifact = generated.step
  verified = ArtifactStore(
      application.state_manager.workspace,
      project_id=application.project_id,
      run_id=source_run.run_id,
  ).read_verified_strict(
      artifact.artifact_id,
      expected_type=ArtifactType.STEP,
      expected_hash=artifact.sha256,
  )
  assert verified is not None
  ```

  Retain `source_artifact_run_id` separately from the later promotion
  run ID and assert both are truthful operational provenance only, not candidate,
  mechanism, or promotion semantic identity.

- [ ] **Step 4: Run the direct module after bootstrap implementation**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_direct_drive.py -q`

  Expected: fixture bootstrap and source STEP publication succeed through a real
  source-bound run; the fail-fast adapter call count remains zero.

### Task 2: Implement the Primary Direct-Drive Live Acceptance

**Files:**
- Modify: `tests/integration/test_m12_6_end_to_end_direct_drive.py`
- Test: `tests/integration/test_m12_6_end_to_end_direct_drive.py::test_live_direct_drive_m12_6_end_to_end`

**Interfaces:**
- Consumes: Task 1 fixture inputs and public application methods from
  `application.py:1759-2068`.
- Produces: a visible candidate/M12-3/CAD/M10/evaluation/selection/promotion/
  public-verification identity record for the audit report.

  Define a test-local `promotion_classifications(candidate) -> tuple[PromotionClassification]`
  beside this test. It must enumerate candidate property, geometry-source,
  design-variable, physical-instance, connection, and joint-binding inputs with
  their required promotion classifications; it is request input construction, not
  an engineering result or a canonical mutation.

- [ ] **Step 1: Write the full primary acceptance test with staged assertions**

  Build candidate CAD and M10 *requests* in the test using candidate-bound input
  semantics, then execute each service visibly:

  ```python
  fixture = bootstrap_direct_drive_fixture(tmp_path)
  app = fixture.app
  request = fixture.synthesis_request
  policy = fixture.synthesis_policy
  outcome = app.realize_and_evaluate_revolute_drive(
      request=request,
      policy=policy,
      template_input=fixture.template_input,
      requirements=fixture.requirements,
  )
  candidate = outcome.construction.candidate
  m12 = outcome.evaluation
  assert candidate is not None
  assert m12.status is DriveAdmissibility.ADMISSIBLE

  cad_stage = app.realize_candidate_cad(candidate, request, policy, cad_request)
  evaluation = app.evaluate_candidate(
      candidate, request, policy, m12, cad_request, m10_request, scope, binding,
      evaluation_policy=CandidateEvaluationPolicy(),
  )
  assert cad_stage.status is CandidateCadStageStatus.SUCCESS
  assert evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
  assert evaluation.m10_stage_outcome.pair_proofs[0].result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR

  selection = app.select_candidate(candidate, evaluation, "m12-6-direct-selector", "explicit direct-drive acceptance selection")
  promotion_request = CandidatePromotionRequest(
      project_id=app.project_id,
      source_revision=fixture.source.revision,
      source_state_hash=fixture.source.state_hash,
      candidate=candidate,
      synthesis_request=request,
      synthesis_policy=policy,
      m12_3_result=m12,
      evaluation=evaluation,
      selection=selection,
      promotion_policy=CandidatePromotionPolicy(),
      canonical_target_mechanism_id="PM-m12-6-direct",
      classifications=promotion_classifications(candidate),
  )
  promotion = app.promote_selected_candidate(promotion_request)
  assert promotion.status is PromotionApplicationStatus.PROMOTION_APPLIED
  verification = app.verify_promoted_mechanism(promotion)
  assert verification.status is PromotedMechanismVerificationStatus.VERIFIED
  assert fixture.acceptance_adapter.call_count == 0
  ```

  Include the accepted clear interval, clearance requirement, pair semantics,
  candidate proof lower bound, exact evaluation count, certificate/leaf count,
  provider name, backend provenance, executable/version discovery, and all
  source/candidate/canonical identity assertions. Do not increase proof budgets
  beyond predecessor fixture values.

- [ ] **Step 2: Run the primary test with live output**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_direct_drive.py::test_live_direct_drive_m12_6_end_to_end -q -s`

  Expected: real FreeCAD is discovered and the test prints a concise identity and
  runtime record. It must fail if FreeCAD is unavailable; a skip is not a positive
  acceptance result.

- [ ] **Step 3: Add promotion-boundary assertions in the same test**

  Assert N/HN -> N+1/HN1, one `add /physical_mechanisms/<id>` operation, one run,
  exact invalidation record, decision-before-result artifact ordering, fresh
  manifest re-resolution, and source revision-byte/hash immutability:

  ```python
  assert promotion.applied_revision == source.revision + 1
  assert promotion.applied_state_hash != source.state_hash
  assert result_manifest.resulting_revision == promotion.applied_revision
  assert decision.base_revision == source.revision
  assert original_revision_path.read_bytes() == original_revision_bytes
  assert state_hash(fresh_manager.load_revision(PROJECT_DIRECT, source.revision)) == source.state_hash
  ```

  Assert candidate CAD realization differs from canonical CAD realization and
  candidate M10 request differs from canonical M10 request. Use the public
  `verify_promoted_mechanism` result as the primary post-promotion path; direct
  canonical services are not a substitute here.

- [ ] **Step 4: Run the direct module and verify complete staged visibility**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_direct_drive.py -q -s`

  Expected: all direct-drive acceptance tests pass on real FreeCAD and emit no
  opaque single-status-only assertion.

### Task 3: Implement Durable Restart, Round Trip, and M11 Tests

**Files:**
- Modify: `tests/integration/test_m12_6_end_to_end_direct_drive.py`
- Test: direct-drive restart and M11 test functions in that module

**Interfaces:**
- Consumes: only scalar durable locators from Task 2, a new
  `ProductionApplication.create`, `ArtifactStore.existing_in_project`,
  `PromotionManifestService.resolve_result/resolve_decision`,
  `reconstruct_promoted_mechanism`, `CanonicalM10ScopeEquivalenceService`, and
  `CanonicalM11HandoffService`.
- Produces: restart proof, field-level semantic round trip, result->decision
  provenance proof, and non-gating M11 assessments.

- [ ] **Step 1: Write the result-to-decision durable provenance test**

  Place the original promotion flow in a local helper scope that returns only
  scalar locators and expected hashes. Outside that scope, construct a new app:

  ```python
  locators = _promote_direct_drive_and_return_locators(tmp_path)
  fresh_app = ProductionApplication.create(
      locators.workspace, locators.project_id, UninvokedAcceptanceAdapter(),
      ownership_path=locators.ownership_path, dependency_path=locators.dependency_path,
  )
  result_meta = ArtifactStore(locators.workspace, project_id=locators.project_id,
                              run_id="project-lookup").existing_in_project(locators.result_artifact_id)
  assert result_meta is not None
  store = ArtifactStore(locators.workspace, project_id=locators.project_id, run_id=result_meta.run_id)
  fresh_result = fresh_app.promotion_manifest_service.resolve_result(store, result_meta.artifact_id)
  fresh_decision = fresh_app.promotion_manifest_service.resolve_decision(store, fresh_result.decision_artifact_id)
  assert result_meta.sha256 == locators.result_artifact_hash
  assert fresh_result.decision_artifact_hash == store.read_verified_strict(
      fresh_result.decision_artifact_id, expected_type=ArtifactType.JSON
  )[0].sha256
  ```

  Do not retain or pass in-memory promotion/manifests/projection/scope/candidate
  objects. `resolve_result` must drive decision discovery.

- [ ] **Step 2: Run the provenance test to verify restart failure before implementation**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_direct_drive.py -k durable_provenance -q`

  Expected: fail until the fresh-scope restart test is implemented; it must not
  pass using the original application graph.

- [ ] **Step 3: Add candidate-independent canonical restart execution**

  Fresh-load N+1 and verify HN1 before execution. Use durable decision content
  only for projection/scope/mapping audit comparisons:

  ```python
  state = fresh_app.state_manager.load_revision(locators.project_id, locators.revision)
  assert state_hash(state) == locators.state_hash
  reconstruction = fresh_app.reconstruct_promoted_mechanism(
      revision=locators.revision, state_hash=locators.state_hash,
      mechanism_id=locators.mechanism_id,
  )
  cad = fresh_app.canonical_cad_compiler.realize(reconstruction)
  m10 = fresh_app.canonical_m10_service.execute(reconstruction, cad)
  equivalence = CanonicalM10ScopeEquivalenceService().compare(
      fresh_decision.pre_promotion_scope_projection, m10.scope,
  )
  assert m10.status is CanonicalM10VerificationStatus.VERIFIED_CLEAR
  assert equivalence.equivalent is True
  ```

  Add a regression that changing/removing the *audit-only* supplied scope object
  changes only scope-comparison behavior and cannot change canonical M10 request,
  inventory, interval, clearance, fidelity, or home checks for unchanged N+1.
  Keep canonical execution calls free of decision projection/scope/mapping inputs.

- [ ] **Step 4: Add field-level round-trip and M11 non-gating assertions**

  Compare decision projection with normalized canonical projection, then assert
  representative exact property value/unit/authority/source/hash/availability,
  accepted-design-choice origin, geometry source, placement relation, topology,
  interface/connection semantics, joint binding, and M10 obligation fields.

  Build post-promotion handoff requests using the accepted `build_handoff_request`
  path and assert:

  ```python
  assert whole_handoff.status is CanonicalM11HandoffStatus.NOT_ELIGIBLE
  assert mount_handoff.status is CanonicalM11HandoffStatus.UNRESOLVED
  assert structural_execution_spy.calls == []
  ```

- [ ] **Step 5: Run the complete direct module**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_direct_drive.py -q -s`

  Expected: direct public verification, durable restart, source provenance,
  candidate-independent canonical M10, round trip, and both M11 assessments pass.

### Task 4: Implement External-Spur Positive and Selection Acceptance

**Files:**
- Modify: `tests/integration/test_m12_6_end_to_end_external_spur.py`
- Test: positive spur, comparison/no-comparison/non-top selection test functions

**Interfaces:**
- Consumes: Task 1-style independent spur fixture authority, optional
  `GearworksTools.registrations()`, public M12 production APIs.
- Produces: an independent external-spur `PromotedMechanismVerificationResult.VERIFIED`
  record, comparison/selection records, and bounded limitation assertions.

- [ ] **Step 1: Write the failing positive external-spur flow**

  Bootstrap `PRJ-M12-6-SPUR-COMPARISON` at N=1, publish/verify source STEP
  inputs, construct explicit M12-3 spur inputs, then visibly run M12-3, candidate
  CAD, candidate M10, evaluation, selection, promotion, public verification, and
  fresh canonical CAD/M10. Use an independent project from direct drive.

  ```python
  assert m12.status is DriveAdmissibility.ADMISSIBLE
  assert evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
  assert promotion.status is PromotionApplicationStatus.PROMOTION_APPLIED
  assert app.verify_promoted_mechanism(promotion).status is PromotedMechanismVerificationStatus.VERIFIED
  ```

- [ ] **Step 2: Run the positive spur test under the actual optional provider gate**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_external_spur.py::test_live_external_spur_positive_promotion_is_verified -q -s`

  Expected: real FreeCAD executes candidate and canonical M10. If py-gearworks/
  build123d is required by the selected fixture, record actual invoked provenance;
  if unavailable, treat the blocked required positive scenario as an acceptance
  failure rather than claiming verification.

- [ ] **Step 3: Add limitation assertions to the same positive test**

  Assert distinct driver/driven physical and CAD instances, physical `GEAR_MESH`
  connection, driver `INTERNAL_MOTION_UNMODELED`, intended-contact gear-pair
  exclusion, and absence of coupled ratio joint, phase, backlash, counter-rotation
  proof, or transmission-internal proof pairs:

  ```python
  assert driver.disposition is CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED
  assert gear_mesh.kind is CanonicalMechanicalConnectionKind.GEAR_MESH
  assert all(driver_cad_id not in proof.pair for proof in canonical_m10.pair_proofs)
  assert not {"ratio", "phase", "backlash", "gear_coupling"} & payload_keys(mechanism.model_dump(mode="json"))
  ```

- [ ] **Step 4: Add independent comparison/no-comparison/non-top scenarios**

  Use clean N=1 projects:

  - `PRJ-M12-6-SPUR-COMPARISON`: compare two feasible evaluations only by
    `verified_clearance_lower_bound_mm`, then explicitly select a candidate.
  - `PRJ-M12-6-SPUR-NO-COMPARISON`: make selection with
    `comparison_used=False`, no comparison request/result, and promote it.
  - `PRJ-M12-6-SPUR-NON-TOP`: rank two feasible candidates, select the lower
    ranked candidate with rationale, then promote and verify it.

  Each project is N=1 -> N=2. Do not reuse candidate/evaluation/selection objects
  after another scenario's source advances.

  ```python
  ranking = app.compare_candidates(request, ((candidate_a, evaluation_a), (candidate_b, evaluation_b)))
  selection = app.select_candidate(candidate_a, evaluation_a, "m12-6-selector", "explicit accepted non-top choice", comparison=ranking, comparison_entries=((candidate_a, evaluation_a), (candidate_b, evaluation_b)))
  assert selection.candidate_hash != ranking.ranked_candidate_hashes[0]
  assert app.verify_promoted_mechanism(app.promote_selected_candidate(request_for(selection))).status is PromotedMechanismVerificationStatus.VERIFIED
  ```

  Include a tie only if the existing M12-4 fixture can reproduce an exact trusted
  lower-bound tie without added geometry tricks. Otherwise cite
  `tests/integration/test_m12_candidate_cad_m10_production.py::test_live_comparison_and_selection_are_deterministic_and_noncanonical`
  as predecessor tie evidence.

- [ ] **Step 5: Run the external-spur module**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_external_spur.py -q -s`

  Expected: at least one independent spur scenario reaches `VERIFIED`; comparison,
  no-comparison, and non-top selection remain explicit and bounded, and every
  positive scenario's fail-fast acceptance adapter has `call_count == 0`.

### Task 5: Implement Cross-Stage Failure and Currentness Coverage

**Files:**
- Modify: `tests/integration/test_m12_6_end_to_end_failures.py`
- Test: named failure cases below

**Interfaces:**
- Consumes: bootstrap-only fixture inputs, public application APIs, ordinary
  `ChangeProposal` where mutation is required, and canonical composed services.
- Produces: representative end-to-end failure classification without creating
  manual result objects or direct canonical mutations.

- [ ] **Step 1: Add M12-3, collision, and NOT_PROVEN cross-stage tests**

  Use real supplied source inputs, execute the production M12-3 path, then retain
  the actual status:

  ```python
  assert insufficient_outcome.evaluation.status is DriveAdmissibility.INADMISSIBLE
  assert collision_evaluation.outcome is CandidateEvaluationOutcome.INFEASIBLE
  assert collision_evaluation.m10_stage_outcome.pair_proofs[0].result.status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS
  assert not_proven_evaluation.outcome is CandidateEvaluationOutcome.UNRESOLVED
  assert not_proven_evaluation.m10_stage_outcome.pair_proofs[0].result.status is ContinuousSingleAxisProofStatus.NOT_PROVEN
  ```

  Assert selection/promotion rejects infeasible or unresolved records. Do not
  fabricate a `CandidateEvaluation` or recast `NOT_PROVEN` as infeasible.

- [ ] **Step 2: Run the three engineering-outcome cases**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_failures.py -k 'm12_3 or collision or not_proven' -q -s`

  Expected: each test executes production classification logic; collision is an
  engineering witness and `NOT_PROVEN` remains unresolved.

- [ ] **Step 3: Add currentness, replay, and target-collision tests**

  Advance a candidate's source with a normal allowed `ChangeProposal` through
  `RunController.apply_approved_proposal`, then assert candidate/selection/
  promotion rejection. After a real successful promotion, replay its exact N-bound
  request and assert pre-apply stale failure, no N+2, and no duplicate mechanism.
  Attempt a separately valid promotion to the existing mechanism ID and assert
  `add` conflict with no revision.

  ```python
  advanced_run = app.run_controller.create_run(
      app.project_id,
      expected_source=SourceBinding(
          project_id=app.project_id,
          revision=source.revision,
          state_hash=source.state_hash,
      ),
  )
  app.run_controller.apply_approved_proposal(advanced_run.run_id, relevant_proposal)
  assert app.promote_selected_candidate(stale_request).status is PromotionApplicationStatus.PRE_APPLY_FAILURE
  assert app.load_state().revision == expected_revision
  ```

- [ ] **Step 4: Add source integrity, joint drift, and obligation-change tests**

  In controlled isolated projects, tamper the selected artifact bytes or present
  valid artifact B while state still selects A; canonical reconstruction/CAD must
  fail closed without candidate/generated fallback. Create a later normal proposal
  that changes canonical joint semantic binding or M10 obligation as permitted by
  `/physical_mechanisms/*` ownership. Assert a changed state hash, old canonical
  request cannot serve the new authority, and fresh canonical M10 derives a new
  request or fails on joint drift.

- [ ] **Step 5: Add later invalidation, historical integrity, and run-ID tests**

  Use a normal later mechanism proposal and assert the configured family-level
  dependency behavior: `/physical_mechanisms/*` invalidates
  `analysis.continuous_clearance_proof` and `analysis.kinematic_sweep` per
  `config/dependencies.yaml:46-49`; do not claim dynamic per-mechanism precision.
  Freshly verify the older decision/result manifests after this advance, while
  confirming replay remains stale. Prove run-ID exclusion in a unit-like pure
  manifest semantic test or isolated project, never by duplicate publication in a
  primary live project.

- [ ] **Step 6: Run the failure module**

  Run: `py -3 -m pytest tests/integration/test_m12_6_end_to_end_failures.py -q -s`

  Expected: every failure retains its correct integrity, operational, engineering,
  currentness, or mutation-rejection category.

### Task 6: Run Focused and Predecessor Regression Matrix

**Files:**
- Test: all M12-6 modules and existing focused suites

**Interfaces:**
- Consumes: completed acceptance modules and unmodified predecessor suites.
- Produces: recorded collected/passed/skipped/failed/errors/elapsed/exit-code
  evidence for the report.

- [ ] **Step 1: Run the dedicated M12-6 focused suite**

  Run:

  ```text
  py -3 -m pytest tests/integration/test_m12_6_end_to_end_direct_drive.py tests/integration/test_m12_6_end_to_end_external_spur.py tests/integration/test_m12_6_end_to_end_failures.py -q -s
  ```

  Expected: exit 0, zero failures/errors; record collected, passed, skipped,
  failed, errors, elapsed, exit code, and real runtime records. Positive direct
  and spur tests must not be skipped.

- [ ] **Step 2: Run the M12/M10/M11 and core regression matrix**

  Run:

  ```text
  py -3 -m pytest tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_revolute_drive_models.py tests/unit/test_m12_revolute_drive_service.py tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_m10_service.py tests/unit/test_m12_candidate_evaluation.py tests/unit/test_m12_candidate_comparison.py tests/unit/test_m12_candidate_selection.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m12_promotion_compiler.py tests/unit/test_m12_promotion_projection.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_replay.py tests/unit/test_m12_promoted_verification.py tests/unit/test_m12_canonical_reconstruction.py tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py tests/unit/test_m12_m11_handoff.py tests/unit/test_changes.py tests/unit/test_runs.py tests/unit/test_dependency.py tests/unit/test_artifacts.py tests/unit/test_production_application.py tests/integration/test_m12_revolute_drive_production.py tests/integration/test_m12_candidate_cad_m10_production.py tests/integration/test_m12_promotion_production.py tests/integration/test_transient_imported_multishape_collision.py tests/integration/test_m10_1_live_continuous_proof.py -q
  ```

  Expected: exit 0, zero failures/errors. This covers M12-2 authority/currentness,
  M12-3, M12-4, M12-5, state/change/run/ownership/dependency/artifact, imported
  multi-shape, M10, and M11-handoff boundaries. Record genuine skips separately.

- [ ] **Step 3: Capture backend environment evidence**

  Before/within the focused live run record Python (`py -3 --version`), pytest
  (`py -3 -m pytest --version`), platform (`py -3 -c "import platform; print(platform.platform())"`), and FreeCAD (`discover_freecad()` plus runtime
  provenance). Report each backend as `INSTALLED`, `PRODUCTION_COMPOSED`, or
  `LIVE_INVOKED`. List py-gearworks/build123d version only from actual spur-path
  invocation provenance, never installation alone.

### Task 7: Complete Final Verification and Audit Evidence

**Files:**
- Create: `docs/audit/MECHCAD_M12_6_SYSTEM_ACCEPTANCE.md`

**Interfaces:**
- Consumes: successful Task 6 outputs, durable artifacts/manifests/Evidence, and
  final test metrics.
- Produces: acceptance report only after all gates pass; no canonical state field.

- [ ] **Step 1: Run the authoritative full suite and collect final evidence**

  Run: `py -3 -m pytest tests/`

  Tool execution ceiling: at least 4000 seconds, recorded separately from pytest
  elapsed time.

  Expected: exit 0, zero failures/errors. Counts may exceed the predecessor
  `1930 passed, 34 skipped`; record exact current counts. Capture the final
  runtime/provider/identity records needed by the report before writing it.

- [ ] **Step 2: Write the complete final audit report after successful live evidence**

  Create `docs/audit/MECHCAD_M12_6_SYSTEM_ACCEPTANCE.md` using the approved
  structure: final disposition, bounded claim, environment, entrypoints, source
  authority, direct/spur flows, sizing/CAD/M10/evaluation/selection/promotion,
  canonical boundary/reconstruction/CAD/M10/restart, identity matrix, failure
  matrix, M11 non-gating handoff, regression/full-suite/verification records,
  authority/mutation/CAD/M10/provenance/M11 reviews, limitations, files, and
  worktree status. Reference durable IDs/hashes rather than copying large payloads.

  Do not yet emit the final milestone disposition outside the report: the report
  itself must pass final file checks first.

- [ ] **Step 3: Run compile, diff, and complete untracked M12-6 scans**

  Run:

  ```text
  py -3 -m compileall -q src/mechcad_harness tests
  git diff --check
  ```

  Scan every new/untracked M12-6 test, fixture, specification, plan, final system
  acceptance report, and any other M12-6-only evidence file for trailing
  whitespace and a final newline. Record scanned file count and each failure count.
  Existing unrelated worktree warnings are not M12-6 findings. If any M12-6 file,
  including the report, changes after this scan, rerun `git diff --check` and the
  affected file scan before final disposition.

- [ ] **Step 4: Perform final acceptance self-review and emit the truthful disposition**

  Recheck authority, mutation, CAD, M10, provenance, M11, external-spur scope,
  backend invocation, and report/file-check evidence. Only now may the report and
  final response emit the verified marker.

  The report can emit
  `M12_6_LIVE_END_TO_END_PHYSICAL_MECHANISM_ACCEPTANCE_VERIFIED` only if the
  direct and required external-spur positive gates both pass. Otherwise emit the
  truthful `M12_6_NEEDS_FIXES` or out-of-scope blocker marker.

## Identity Matrix

The direct test/report must capture these exact values:

| Stage | Required identities |
| --- | --- |
| Source | project, N, HN, original revision byte hash, STEP artifact ID/hash/original provenance |
| M12-3 | synthesis request hash, policy hash, result hash, candidate hash |
| Candidate CAD | request and realization hashes |
| Candidate M10/Evaluation | scope, request, result, evaluation hashes |
| Selection | comparison request/result hashes when used; selection hash |
| Promotion | request/policy/projection/scope-projection/compilation/proposal-semantic hashes; decision/result artifact ID/hash; operational proposal and ChangeSet IDs; run ID only as correlation; N+1/HN1 |
| Canonical | mechanism/reconstruction hashes; CAD request/realization; derived M10 scope/request/result; scope-equivalence; promoted verification; M11 handoff IDs/hashes |

Assert `HN != HN1`, candidate CAD realization differs from canonical realization,
and candidate M10 request differs from canonical M10 request. Assert semantic
projection and obligation/scope equivalences only where the contracts explicitly
provide them. Repeat at least one deterministic computation and compare semantic
hashes without requiring run IDs, ChangeSet UUIDs, timestamps, or temp paths.

## Production Changes Required

**NONE.** If this changes during execution, stop before source edits and follow
the Global Constraints classification gate.

## Plan Self-Review

- Production source changes: none planned.
- Fixture helpers: limited to bootstrap/source authority/input artifacts; all
  engineering outcomes execute visibly in tests.
- Primary product path: uses `ProductionApplication.verify_promoted_mechanism`.
- Restart: requires a new application/service graph and durable result -> decision
  manifest resolution; no old application/manifests/candidates cross the boundary.
- Audit projections: used only for equivalence/provenance, never canonical CAD/M10
  inputs.
- Spur: final positive `VERIFIED` requirement and limitation assertions are
  mandatory.
- Lineages: independent N=1 -> N=2 projects; no stale selection reuse.
- M11: eligibility only, non-gating, no fabricated inputs or solver execution.
- Run IDs: semantic proof isolated from primary project artifact lookup.
- Backend claims: installed/composed/invoked categories remain separate.
- Final report ordering: the report is created before compile/diff/untracked scans;
  its own file checks pass before any verified disposition is emitted.
- Source artifacts: trusted STEP fixtures are published in real N/HN-bound source
  runs and their run provenance is distinct from promotion-run provenance.
- Project-wide lookup: `project-lookup` ArtifactStore construction is side-effect
  free and is covered by a no-storage-mutation assertion.
- Acceptance adapter: fail-fast only; every positive path asserts `call_count == 0`
  and no adapter output can enter engineering execution.
- Release/M13, catalog/search/optimizer, and new stores are out of scope.
