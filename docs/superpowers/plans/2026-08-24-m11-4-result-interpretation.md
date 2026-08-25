# M11-4 Result Interpretation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Interpret trusted M11-3 CalculiX 2.22 results into typed fields, validate a live cantilever, and evaluate existing structural criteria as PASS, FAIL, or NOT_EVALUABLE.

**Architecture:** Correct M11-3 to preserve each selected load case as an ordered independently solved partition sharing one trusted mesh. A strict FRD/DAT parser layer consumes only rehashed artifacts selected by successful per-case manifests; an interpreter produces immutable mesh-bound physical summaries and a separate evaluator applies canonical criteria and property-specific material authority. A versioned analytical validator uses the same typed result without publishing accepted Evidence.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, FreeCAD 1.1.3, Gmsh 4.15.0, CalculiX 2.22.

## Global Constraints

- Preserve `DesignState` as canonical authority; result interpretation never mutates it.
- Do not commit, push, reset, stash, clean, checkout, revert, or discard existing work.
- Consume only successful trusted M11-3 request/case manifests and `ArtifactStore` artifact bytes rehashed at interpretation time.
- Keep artifact -> case-manifest -> request-manifest provenance non-circular.
- Use one request-level MSH artifact; every case references its exact ID/hash.
- Preserve ordered selected load-case identities; never combine loads, envelope cases, or infer a worst case.
- Parsed stress is `calculix_extrapolated_nodal_stress`, not integration-point or generic element stress.
- Result-integrity failures emit no engineering evaluation; `NOT_EVALUABLE` is only a valid-result authority or semantic outcome.
- Reuse current `evaluate_material_authority_policy`; no material or criterion modification is permitted.
- No structural EvidenceStore publication, no M11-5 durable-evidence work, and no `MESH_CONVERGENCE_VERIFIED` claim.
- Use ASCII in new source and documentation unless existing surrounding content requires otherwise.

---

## File Structure

- Modify `src/mechcad_harness/structural/models.py`: request/case execution manifests, result/criterion/provenance models, deterministic hashes, and result-integrity exception/status types.
- Modify `src/mechcad_harness/structural/deck.py`: one-case deck construction and requested-field-controlled FRD/DAT output cards.
- Modify `src/mechcad_harness/structural/service.py`: one shared mesh plus ordered case execution, artifact publication, failed request manifest, and non-circular manifest bindings.
- Modify `src/mechcad_harness/structural/fakes.py`: deterministic valid case-partition output and parser-specific raw fixtures.
- Create `src/mechcad_harness/structural/results.py`: strict CalculiX 2.22 FRD/DAT parsers, tensor math, trusted artifact resolution, interpreter, and criterion evaluator.
- Create `src/mechcad_harness/structural/validation.py`: frozen rectangular-cantilever analytical validation policy and evaluator.
- Modify `src/mechcad_harness/application.py`: high-level `evaluate_structural_analysis` composition-root capability only.
- Create `tests/unit/test_structural_results.py`: parser, math, binding, criterion, tampering, and analytical-policy coverage.
- Modify `tests/unit/test_structural_service.py` and `tests/unit/test_structural_pipeline_contracts.py`: per-case M11-3 correction and output-card coverage.
- Create `tests/integration/test_m11_4_live_structural.py`: real M11-4 PASS, FAIL, NOT_EVALUABLE, stress parsing, and cantilever validation capstone.
- Create `docs/audit/MECHCAD_M11_4_COMPLETION_REPORT.md`: final live evidence, limits, and exact verification commands/results.

### Task 1: Establish M11-4 Models And Hashing

**Files:**
- Modify: `src/mechcad_harness/structural/models.py`
- Test: `tests/unit/test_structural_results.py`

**Consumes:** Existing `StructuralExecutionManifest`, `StructuralArtifactRef`, `StructuralExecutionStatus`, `StructuralResultField`, and canonical structural criteria.

**Produces:** Immutable request/case execution manifests, typed result fields, criterion statuses/reasons, parser provenance, and hash functions consumed by the service and interpreter.

- [ ] **Step 1: Write failing immutable-model and identity tests**

```python
def test_case_manifest_and_result_hash_exclude_run_id_but_bind_raw_bytes():
    first = _result(run_id="RUN-A", frd_hash="sha256:" + "a" * 64)
    second = _result(run_id="RUN-B", frd_hash="sha256:" + "a" * 64)
    changed = _result(run_id="RUN-B", frd_hash="sha256:" + "b" * 64)
    assert structural_result_hash(first) == structural_result_hash(second)
    assert structural_result_hash(first) != structural_result_hash(changed)

def test_duplicate_result_identity_requires_distinguishing_location_identity():
    with pytest.raises(ValidationError, match="duplicate stress sample identity"):
        StructuralLoadCaseResult.model_validate(_case_result_payload(stress_samples=(sample, sample)))
```

- [ ] **Step 2: Run the focused test to verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_results.py -q`

Expected: FAIL because M11-4 result models and `structural_result_hash` do not exist.

- [ ] **Step 3: Add the minimal result and manifest model family**

```python
class StructuralCriterionStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUABLE = "not_evaluable"

class StressFieldRepresentation(StrEnum):
    CALCULIX_EXTRAPOLATED_NODAL_STRESS = "calculix_extrapolated_nodal_stress"

class StructuralCaseExecutionManifest(Model):
    load_case_id: str = Field(min_length=1)
    mesh_artifact_id: str = Field(min_length=1)
    mesh_artifact_hash: str = Field(min_length=1)
    deck_artifact_id: str | None = None
    deck_artifact_hash: str | None = None
    frd_artifact_id: str | None = None
    frd_artifact_hash: str | None = None
    dat_artifact_id: str | None = None
    dat_artifact_hash: str | None = None
    log_artifact_id: str | None = None
    log_artifact_hash: str | None = None
    execution_status: StructuralExecutionStatus
    case_manifest_hash: str = "pending"

class StructuralVerificationResult(Model):
    overall_status: StructuralCriterionStatus
    criterion_results: tuple[StructuralCriterionResult, ...]
    verification_hash: str = "pending"
```

Include finite scalar validation, exact mesh-hash binding on every local result ID, nonempty ordered case IDs, `FEA_EXECUTED` maturity only, parser identities (`mechcad-calculix-frd-result-parser@1`, `mechcad-calculix-dat-result-parser@1`, `mechcad-structural-result-interpreter@1`), explicit units, and canonical-JSON hash helpers that remove only `run_id` from engineering identity.

- [ ] **Step 4: Run focused models tests**

Run: `py -3 -m pytest tests/unit/test_structural_results.py -q`

Expected: PASS for immutable models, representation, hash, and duplicate identity coverage.

### Task 2: Correct M11-3 To Execute Ordered Case Partitions

**Files:**
- Modify: `src/mechcad_harness/structural/models.py`
- Modify: `src/mechcad_harness/structural/service.py`
- Modify: `src/mechcad_harness/structural/fakes.py`
- Test: `tests/unit/test_structural_service.py`
- Test: `tests/unit/test_structural_pipeline_contracts.py`

**Consumes:** Task 1 case-manifest models, existing one-solid geometry/mesh/deck/solver components.

**Produces:** One shared mesh and one case manifest/artifact partition per selected load case, with a request manifest that has ordered status-bearing partitions even when a case fails.

- [ ] **Step 1: Write failing two-load-case service tests**

```python
def test_execute_creates_ordered_case_partitions_using_one_mesh(prepared_two_case_request):
    result = _service(prepared_two_case_request).execute(prepared_two_case_request.request)
    assert result.execution_status is StructuralExecutionStatus.SUCCEEDED
    assert [case.load_case_id for case in result.manifest.case_manifests] == ["LC-1", "LC-2"]
    assert len({case.mesh_artifact_hash for case in result.manifest.case_manifests}) == 1

def test_second_case_failure_persists_failed_request_manifest_without_result(prepared_two_case_request):
    result = _service(prepared_two_case_request, solver=_fail_on_second_case()).execute(
        prepared_two_case_request.request
    )
    assert result.execution_status is StructuralExecutionStatus.SOLVER_FAILED
    assert result.manifest is not None
    assert [case.execution_status for case in result.manifest.case_manifests] == [
        StructuralExecutionStatus.SUCCEEDED, StructuralExecutionStatus.SOLVER_FAILED
    ]
```

- [ ] **Step 2: Run M11-3 service tests to verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py -q`

Expected: FAIL because the service merges loads and has no case manifests.

- [ ] **Step 3: Refactor `_run_pipeline` around one mesh and ordered cases**

```python
mesh_artifact = self._publish_shared_mesh(request, run, msh_bytes, mesh_manifest)
case_manifests = []
for load_case_id in request.selected_load_case_ids:
    selected_case = case_by_id[load_case_id]
    built = self.deck_builder.build(
        definition=definition, selected_cases=(selected_case,), fixed_supports=fixed_supports,
        region_definitions=definition.regions, region_map=region_map, parsed_mesh=parsed_mesh,
        mesh_hash=mesh_manifest.mesh_hash, requested_result_fields=request.requested_result_fields,
    )
    preflight = self.constraint_preflight.evaluate(
        parsed_mesh.nodes, built.representation.boundary_node_sets
    )
    solver_result = self.calculix_provider.execute(built.text)
    case_manifest = self._publish_case_artifacts_and_manifest(
        request=request, load_case_id=load_case_id, mesh_artifact=mesh_artifact,
        built=built, solver_result=solver_result, revision=revision, state_hash=state_hash,
    )
    case_manifests.append(case_manifest)
    if case_manifest.execution_status is not StructuralExecutionStatus.SUCCEEDED:
        return self._publish_failed_request_manifest(
            request, run, mesh_artifact, tuple(case_manifests)
        )
return self._publish_succeeded_request_manifest(
    request, run, mesh_artifact, tuple(case_manifests)
)
```

Publish direct artifacts before their case manifest. Case manifests store direct artifact references and hashes. The request manifest stores only the ordered case-manifest identity/hash records, plus the shared mesh reference. Do not add a manifest hash to an artifact input hash. Preserve existing source and geometry verification before mesh generation.

- [ ] **Step 4: Update fake providers and assertions**

Make the fake solver return only deliberately valid minimal FRD/DAT bytes for M11-3 execution tests; retain fake provider identity. Add deterministic invocation counting to prove one solve per selected case, and preserve existing single-case assertions through a compatibility accessor only if current tests require it.

- [ ] **Step 5: Run M11-3 regressions**

Run: `py -3 -m pytest tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py tests/integration/test_m11_3_live_structural.py -q`

Expected: PASS, including new shared-mesh/ordered-case/failure-manifest assertions.

### Task 3: Make Deck Result Requests Exact And Discover DAT RF

**Files:**
- Modify: `src/mechcad_harness/structural/deck.py`
- Modify: `src/mechcad_harness/structural/service.py`
- Test: `tests/unit/test_structural_pipeline_contracts.py`
- Test: `tests/integration/test_m11_4_live_structural.py`

**Consumes:** Per-case deck invocation from Task 2 and `requested_result_fields` from `StructuralAnalysisRequest`.

**Produces:** Deterministic requested-only output cards and a live CalculiX 2.22 DAT RF fixture contract.

- [ ] **Step 1: Write failing deck output tests**

```python
def test_deck_requests_only_requested_result_fields():
    displacement = _deck((StructuralResultField.DISPLACEMENT,)).text
    reactions = _deck((StructuralResultField.REACTIONS,)).text
    assert "*NODE FILE\nU\n" in displacement
    assert "*EL FILE\nS\n" not in displacement
    assert "*NODE PRINT,NSET=fixed_nodes\nRF\n" in reactions
    assert "*NODE PRINT,NSET=fixed_nodes\nU\n" not in reactions
```

- [ ] **Step 2: Run deck tests to verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_pipeline_contracts.py -q`

Expected: FAIL because the current builder always emits `S` and `U` and never requests `RF`.

- [ ] **Step 3: Thread `requested_result_fields` into `StructuralDeckBuilder.build`**

```python
if StructuralResultField.VON_MISES_STRESS in requested_result_fields:
    lines.extend(("*EL FILE", "S"))
if StructuralResultField.DISPLACEMENT in requested_result_fields:
    lines.extend(("*NODE FILE", "U"))
if StructuralResultField.REACTIONS in requested_result_fields:
    lines.extend((f"*NODE PRINT,NSET={first_support_region}_nodes", "RF"))
```

Keep only diagnostic output already required by M11-3. Update the deck validator's allowed-card contract. Do not add criteria or change canonical request fields.

- [ ] **Step 4: Capture and pin real RF DAT output before parser implementation**

Add a live discovery/capstone test that requests reactions, reads the trusted DAT bytes, and asserts the exact CalculiX 2.22 section header, node record tokenization, three translational reaction components, scientific notation support, and absence of rotational-solid reaction DOFs. Store a short representative DAT fixture under `tests/fixtures/calculix_2_22/` only after it is captured from this real run.

- [ ] **Step 5: Run deck and live RF discovery tests**

Run: `py -3 -m pytest tests/unit/test_structural_pipeline_contracts.py tests/integration/test_m11_4_live_structural.py -q`

Expected: PASS with a documented tested DAT RF contract.

### Task 4: Implement Strict CalculiX 2.22 FRD And DAT Parsers

**Files:**
- Create: `src/mechcad_harness/structural/results.py`
- Create: `tests/fixtures/calculix_2_22/displacement_stress.frd`
- Create: `tests/fixtures/calculix_2_22/reactions.dat`
- Test: `tests/unit/test_structural_results.py`

**Consumes:** Actual FRD/DAT formats captured in Tasks 1 and 3, and `ParsedMesh` identities.

**Produces:** `CalculiXFrdResultParser` and `CalculiXDatResultParser` that only admit the proven CalculiX 2.22 subset.

- [ ] **Step 1: Add representative byte fixtures and failing strict-parser tests**

```python
def test_frd_parser_reads_current_displacement_and_extrapolated_nodal_stress_contract(mesh):
    parsed = CalculiXFrdResultParser().parse(_fixture_bytes("displacement_stress.frd"), mesh)
    assert parsed.displacements[2].vector_mm == (0.001, -0.002, 0.003)
    assert parsed.stress_samples[0].representation is StressFieldRepresentation.CALCULIX_EXTRAPOLATED_NODAL_STRESS
    assert parsed.stress_samples[0].tensor_mpa.szx == pytest.approx(-6.0)

@pytest.mark.parametrize("payload", [b" -1         2 NaN 0.0 0.0\n", b" -1         2 Inf 0.0 0.0\n", b" -4  DISP        4    1\n"])
def test_frd_parser_rejects_invalid_or_truncated_records(payload, mesh):
    with pytest.raises(StructuralResultIntegrityError):
        CalculiXFrdResultParser().parse(payload, mesh)
```

Add equivalent DAT RF tests for malformed sections, unknown nodes, duplicate ambiguous node reactions, invalid numeric values, and truncation. Include positive/negative/scientific values, multiple nodes, multiple stress sample locations where the concrete format supports stable IDs, and wrong component counts.

- [ ] **Step 2: Run parser tests to verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_results.py -q`

Expected: FAIL because parser types and integrity error do not exist.

- [ ] **Step 3: Implement finite fixed-width parsing without silent recovery**

```python
class CalculiXFrdResultParser:
    identity = "mechcad-calculix-frd-result-parser@1"

    def parse(self, content: bytes, mesh: ParsedMesh) -> ParsedCalculiXFrd:
        text = content.decode("ascii", errors="strict")
        datasets = _parse_frd_datasets(text)
        displacement = _require_exact_dataset(datasets, "DISP", ("D1", "D2", "D3"))
        stress = _require_exact_dataset(datasets, "STRESS", ("SXX", "SYY", "SZZ", "SXY", "SYZ", "SZX"))
        return ParsedCalculiXFrd(
            displacements=_parse_displacements(displacement, mesh),
            stress_samples=_parse_extrapolated_nodal_stress(stress, mesh),
        )
```

Use `math.isfinite` after every parse. Reject unsupported dataset variants and any non-exact required component ordering. Validate every node result against `mesh.nodes`; validate a supplied element/result-location identity against `mesh.c3d10`. Reject duplicate identities unless a proven format location token distinguishes them and it is included in the `StressSampleIdentity` hash. Ignore only explicitly allowlisted unrelated datasets such as `ERROR`.

```python
class CalculiXDatResultParser:
    identity = "mechcad-calculix-dat-result-parser@1"

    def parse_reactions(self, content: bytes, mesh: ParsedMesh, allowed_nodes: frozenset[int]) -> tuple[NodeReaction, ...]:
        # Parse only the captured CalculiX 2.22 "forces (fx,fy,fz)" RF section.
        return _parse_calculix_2_22_reaction_block(content, mesh, allowed_nodes)
```

- [ ] **Step 4: Run parser tests**

Run: `py -3 -m pytest tests/unit/test_structural_results.py -q`

Expected: PASS for all valid fixtures and fail-closed invalid input coverage.

### Task 5: Implement Trusted Interpretation And Criterion Evaluation

**Files:**
- Create: `src/mechcad_harness/structural/results.py`
- Modify: `src/mechcad_harness/application.py`
- Test: `tests/unit/test_structural_results.py`

**Consumes:** Task 1 models, Task 2 request/case manifests, Task 4 parsers, `ArtifactStore`, canonical definition, and existing material authority evaluator.

**Produces:** `StructuralResultInterpreter.interpret`, `StructuralVerificationService.evaluate`, and high-level `ProductionApplication.evaluate_structural_analysis` methods.

- [ ] **Step 1: Write failing trust-boundary and criterion tests**

```python
def test_interpreter_rehashes_frd_and_refuses_tampering_before_parser(monkeypatch, successful_case):
    _tamper(successful_case.frd_path)
    parser = Mock()
    with pytest.raises(StructuralResultIntegrityError, match="FRD artifact byte/hash mismatch"):
        StructuralResultInterpreter(
            workspace=successful_case.workspace, project_id=successful_case.project_id,
            frd_parser=parser, dat_parser=CalculiXDatResultParser(),
        ).interpret(successful_case.request_manifest)
    parser.parse.assert_not_called()

def test_displacement_criterion_uses_only_assessment_region_nodes(result, definition):
    verification = StructuralVerificationService().evaluate(result, definition)
    assert verification.criterion_results[0].status is StructuralCriterionStatus.PASS
    assert verification.criterion_results[0].consumed_result_field == "nodal_displacement_magnitude_on_region"
```

Add tests for failed/missing manifests, failed status, missing FRD/DAT when requested, manifest/request/definition/source/mesh/deck/load-case mismatch, foreign DAT, unknown mesh results, field not requested, criterion PASS/FAIL, missing yield property, disallowed authority, unsupported extrapolated-nodal stress domain, and aggregate order (`FAIL`, then `NOT_EVALUABLE`, then `PASS`).

- [ ] **Step 2: Run tests to verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_results.py -q`

Expected: FAIL because the interpreter and verification service do not exist.

- [ ] **Step 3: Implement trusted artifact resolution and physical summaries**

```python
def interpret(self, request_manifest: StructuralExecutionManifest) -> StructuralAnalysisResult:
    _require_request_success_and_binding(request_manifest, request, definition)
    shared_mesh = self._load_verified_mesh(request_manifest.mesh_artifact_id, request_manifest.mesh_artifact_hash)
    case_results = tuple(
        self._interpret_case(case, shared_mesh, request, definition)
        for case in request_manifest.case_manifests
    )
    return StructuralAnalysisResult(
        source_binding=request.source_binding, definition_id=definition.id,
        definition_hash=request.source_binding.definition_hash, request_hash=request.request_hash,
        execution_manifest_hash=execution_manifest_hash(request_manifest),
        mesh_hash=shared_mesh.hash, load_case_results=case_results, result_hash="pending",
    )
```

Parse mesh coordinates from the trusted MSH/INP source already represented by the shared mesh artifact; never take coordinate values from caller input. Calculate displacement magnitude with `sqrt(ux**2 + uy**2 + uz**2)` without rounding. Calculate total reactions and moment `sum(cross(node_coordinate - reference_point, reaction))` with an explicit support-centroid reference point. Calculate applied vectors/moments from lowered-load provenance and persist force/moment residuals under an explicit `structural-equilibrium@1` policy.

- [ ] **Step 4: Implement tensor-derived von Mises and domain-bound criterion evaluation**

```python
def von_mises_mpa(tensor: CauchyStressTensor) -> float:
    return sqrt(
        0.5 * ((tensor.sxx - tensor.syy) ** 2 + (tensor.syy - tensor.szz) ** 2 + (tensor.szz - tensor.sxx) ** 2)
        + 3.0 * (tensor.sxy ** 2 + tensor.syz ** 2 + tensor.szx ** 2)
    )
```

Resolve each `assessment_region_id` from the trusted mesh physical group. For displacement, inspect only the group's nodes. For yield, require an explicit matching `stress_sampling` and an unambiguous domain. Current extrapolated nodal stress does not satisfy `element_integration_point`; return deterministic `unsupported_result_representation` rather than a numeric decision. Call `evaluate_material_authority_policy` before numeric comparison. Calculate safety factor only after representation/domain/authority admission, preserving `zero_stress_tolerance_mpa` behavior defined by M11-1.

- [ ] **Step 5: Add direct von Mises mathematics tests and run focused suite**

```python
@pytest.mark.parametrize(("tensor", "expected"), [
    (CauchyStressTensor(sxx=12, syy=0, szz=0, sxy=0, syz=0, szx=0), 12),
    (CauchyStressTensor(sxx=7, syy=7, szz=7, sxy=0, syz=0, szx=0), 0),
    (CauchyStressTensor(sxx=0, syy=0, szz=0, sxy=5, syz=0, szx=0), sqrt(3) * 5),
])
def test_von_mises_known_states(tensor, expected):
    assert von_mises_mpa(tensor) == pytest.approx(expected)
```

Run: `py -3 -m pytest tests/unit/test_structural_results.py -q`

Expected: PASS for parser, trust, physics, domain, authority, and status semantics.

### Task 6: Add Frozen Analytical Cantilever Validation

**Files:**
- Create: `src/mechcad_harness/structural/validation.py`
- Test: `tests/unit/test_structural_results.py`

**Consumes:** Task 5 typed results and immutable result hashes.

**Produces:** `RectangularCantileverValidationPolicy` and `StructuralAnalyticalValidator` with deterministic pass/fail result hashes.

- [ ] **Step 1: Write failing policy and failure-detection tests**

```python
def test_policy_hash_changes_when_tolerance_changes():
    assert cantilever_validation_policy_hash(_policy(0.03)) != cantilever_validation_policy_hash(_policy(0.04))

def test_validator_reports_fail_for_wrong_tip_displacement(valid_result, policy):
    wrong = valid_result.model_copy(update={"analytical_tip_displacement_mm": 999.0})
    assert StructuralAnalyticalValidator().validate(wrong, policy).status == "fail"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_results.py -q`

Expected: FAIL because policy and validator do not exist.

- [ ] **Step 3: Implement frozen declared-before-execution policy**

```python
class RectangularCantileverValidationPolicy(Model):
    policy_id: Literal["rectangular-cantilever-linear-static-validation@1"]
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    elastic_modulus_mpa: float = Field(gt=0)
    poisson_ratio: float
    resultant_force_n: tuple[float, float, float]
    mesh_specification_hash: str
    free_end_region_id: str
    fixed_end_region_id: str
    displacement_relative_tolerance: float = Field(gt=0)
    reaction_relative_tolerance: float = Field(gt=0)
```

Use `I = width * height**3 / 12` and predeclare Euler-Bernoulli `F * L**3 / (3 * E * I)`. Implement the tip metric as an FE-consistent integral over free-end CPS6 triangles: triangle area times the quadratic shape-function nodal transverse displacement integral, divided by total semantic area. It must not be a raw node average. Calculate expected fixed force `-F` and expected moment from the declared free-end centroid/reference point cross the force. Persist all inputs, observed/expected values, absolute/relative errors, tolerance, and per-check status.

- [ ] **Step 4: Run analytical tests**

Run: `py -3 -m pytest tests/unit/test_structural_results.py -q`

Expected: PASS for policy immutability/hash and PASS/FAIL validator behavior.

### Task 7: Integrate Production API And Live Capstone

**Files:**
- Modify: `src/mechcad_harness/application.py`
- Create: `tests/integration/test_m11_4_live_structural.py`

**Consumes:** Tasks 2 through 6 and the existing real fixture helper pattern in `test_m11_3_live_structural.py`.

**Produces:** High-level result interpretation/evaluation through `ProductionApplication` and real capstone evidence in tests.

- [ ] **Step 1: Write the failing high-level integration call**

```python
execution = app.execute_structural_analysis(request=request)
evaluated = app.evaluate_structural_analysis(execution_manifest=execution.manifest)
assert evaluated.result.load_case_results[0].maximum_displacement is not None
assert evaluated.verification.overall_status is StructuralCriterionStatus.PASS
```

- [ ] **Step 2: Run integration test to verify failure**

Run: `py -3 -m pytest tests/integration/test_m11_4_live_structural.py -q`

Expected: FAIL because `ProductionApplication.evaluate_structural_analysis` does not exist.

- [ ] **Step 3: Compose the interpreter and validation service without a new root or ToolBroker command**

```python
def evaluate_structural_analysis(self, *, execution_manifest: StructuralExecutionManifest):
    result = self.structural_result_interpreter.interpret(execution_manifest)
    definition = self.structural_service.load_bound_definition(execution_manifest)
    verification = self.structural_verification_service.evaluate(result, definition)
    return StructuralAnalysisEvaluation(result=result, verification=verification)
```

Construct parser identities/providers inside `ProductionApplication`; callers cannot provide parser identity, raw bytes, hashes, or result values. Do not write `Evidence` or call `EvidenceStore`.

- [ ] **Step 4: Declare the live cantilever policy and test cases before execution**

Use a source-bound `200 x 20 x 10 mm` cantilever, a fixed `x=min` face, free `x=max` face, declared elastic material, one transverse end `ResultantForce`, and a fixed mesh size selected before live observation. Define area-integrated free-end transverse displacement, support-centroid reaction moment reference, Euler-Bernoulli equation, and rationale-backed fixed tolerances in module constants before calling the production service.

Add three real cases:

```python
def test_live_cantilever_pass_and_analytical_validation(live_app, tmp_path):
    assert validation.status == "pass"
    assert verification.overall_status is StructuralCriterionStatus.PASS

def test_live_valid_solution_reports_engineering_fail(live_app, tmp_path):
    assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED
    assert verification.criterion_results[0].status is StructuralCriterionStatus.FAIL

def test_live_valid_solution_reports_missing_yield_not_evaluable(live_app, tmp_path):
    assert result.load_case_results[0].stress_samples
    assert verification.criterion_results[0].status is StructuralCriterionStatus.NOT_EVALUABLE
    assert verification.criterion_results[0].reason == "missing_material_property"
```

Request `DISPLACEMENT`, `VON_MISES_STRESS`, and `REACTIONS` for the PASS fixture. Assert exact parser and solver versions, calculated tensor von Mises, mesh-bound stress sample IDs, force/moment agreement, and `mesh_convergence_verified is False` or the equivalent explicit maturity state. The FAIL limit and NOT_EVALUABLE missing-yield setup are module constants declared before their executions.

- [ ] **Step 5: Run live M11-4 and predecessor structural tests**

Run: `py -3 -m pytest tests/integration/test_m11_3_live_structural.py tests/integration/test_m11_4_live_structural.py tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_results.py -q`

Expected: PASS, with real FreeCAD/Gmsh/CalculiX capstone evidence for PASS, FAIL, NOT_EVALUABLE, displacement, stress, and reactions.

### Task 8: Complete Audit Documentation And Final Verification

**Files:**
- Create: `docs/audit/MECHCAD_M11_4_COMPLETION_REPORT.md`
- Modify: `README.md`
- Modify: `AGENTS.md`

**Consumes:** All implemented models, tests, live result values, and final command output.

**Produces:** Accurate M11-4 capability documentation and acceptance report with no unsupported claim.

- [ ] **Step 1: Write the report with every required heading**

Include exactly the requested sections: Final Disposition, Accepted Baseline, M11-4 Production Scope, Result Trust Boundary, FRD Parser, DAT Parser, Load-Case Binding, Typed StructuralAnalysisResult, Displacement Representation, Stress Representation, Von Mises Derivation, Reaction Interpretation, Result Integrity Failure Semantics, Material Authority Evaluation, Criterion PASS Semantics, Criterion FAIL Semantics, Criterion NOT_EVALUABLE Semantics, Overall Verification Semantics, Analytical Cantilever Definition, Analytical Reference Equations, Analytical Validation Policy, Tip Displacement Comparison, Reaction Force Comparison, Reaction Moment Comparison, Live Stress Interpretation, Engineering PASS Case, Engineering FAIL Case, NOT_EVALUABLE Case, Parser Provenance, Result Hashing, Result Artifact Semantics, Live Runtime, Live Capstone Results, Focused Failure Tests, M9/M10/M11-3 Regression Results, Full Suite Results, Files Changed, Remaining Limitations, and M11-5 Boundary.

Record actual observed values, expected values, errors, declared tolerances, exact test counts/duration, and all known limitations. State that stress is extrapolated nodal and yield was not globally certified. Do not call a computational artifact accepted Evidence.

- [ ] **Step 2: Update current-status documents precisely**

Update `README.md` and `AGENTS.md` only after all verification succeeds. Add `M11_4_REAL_FEA_RESULT_ANALYTICAL_VALIDATION_VERIFIED` and the bounded capability claim; retain all M11-5 boundaries and no-convergence limitation.

- [ ] **Step 3: Run targeted and full verification**

Run: `py -3 -m pytest tests/`

Expected: all passed/skipped/failed/error counts and elapsed duration captured verbatim; no timeout is interpreted as success.

Run: `py -3 -m compileall src/mechcad_harness -q`

Expected: exit code 0.

Run: `git diff --check -- src/mechcad_harness/structural src/mechcad_harness/application.py tests/unit/test_structural_results.py tests/integration/test_m11_4_live_structural.py docs/audit/MECHCAD_M11_4_COMPLETION_REPORT.md`

Expected: no output.

Run: `git diff --check`

Expected: report any pre-existing unrelated `.superpowers/sdd/...` diagnostics accurately without modifying them.

- [ ] **Step 4: Verify documentation claims against implementation**

Read the final report, `README.md`, and `AGENTS.md`; confirm they contain neither `MESH_CONVERGENCE_VERIFIED` nor any structural `EvidenceStore` acceptance claim and that the sole final marker is `M11_4_REAL_FEA_RESULT_ANALYTICAL_VALIDATION_VERIFIED`.
