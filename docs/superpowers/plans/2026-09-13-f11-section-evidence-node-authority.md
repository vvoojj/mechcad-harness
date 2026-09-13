# F11 Section Evidence Node Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate M5.5C section-tool Evidence from M11 typed structural-FEA Evidence by publishing the section family at `analysis.section` while preserving every M11 structural identity.

**Architecture:** The generic EvidenceStore remains unchanged and continues to use its configured node string for persistence, freshness, and readiness. Only the M5.5C ToolRegistration authorization changes to `analysis.section`; the dependency configuration recognizes that new node through the existing material rule, without adding structural edges. M11's typed `EvidenceSubject.STRUCTURAL_ANALYSIS`, payload semantic hash, deterministic ID, and `analysis.structural` graph remain unchanged.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, JSON/YAML dependency configuration.

## Global Constraints

- Implement F11 authority separation only; do not alter F3, F8, F21, P3 findings, or general dependency/Evidence architecture.
- Preserve M11 `analysis.structural`, `analysis.structural.convergence`, typed subject discriminator, semantic-hash bytes, and deterministic Evidence IDs exactly.
- Publish new M5.5C tool Evidence only at `analysis.section`; do not remove either producer family.
- Do not migrate, reinterpret, or heuristically classify legacy `analysis.structural` records.
- Do not modify `docs/reconstruction/**` or accepted audit records.
- Preserve F1, F4, F5, F6, and F7 behavior and all unrelated node identities.
- Do not run FreeCAD, Gmsh, or CalculiX validation unless separately authorized.
- Do not commit, amend, push, or modify unrelated dirty work without explicit user authorization.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/mechcad_harness/tools/sections.py` | Authorize the six M5.5C geometry/warping producers for the distinct section node. |
| `src/mechcad_harness/tools/section_engineering.py` | Authorize the M5.5C preliminary engineering producer for the same distinct node. |
| `config/dependencies.yaml` | Make `analysis.section` a known node through the existing material invalidation family, without structural edges. |
| `tests/unit/test_section_tools.py` | Verify a real section ToolBroker materialization writes `analysis.section`. |
| `tests/unit/test_section_warping_tools.py` | Verify a warping ToolBroker materialization writes `analysis.section`. |
| `tests/unit/test_section_engineering_tools.py` | Verify complete preliminary engineering emits `analysis.section`; partial output remains Evidence-free. |
| `tests/unit/test_dependency.py` | Prove node-specific readiness/freshness and structural-definition invalidation isolation. |
| `tests/unit/test_structural_evidence_models.py` | Lock the unchanged M11 typed discriminators and persistence round trip. |
| `tests/unit/test_structural_evidence_verifier.py` | Prove structural verification still rejects a generic section-family record. |
| `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md` | State the explicit M5.5C versus M11 Evidence-node boundary. |
| `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md` | Record the optional section registration node without claiming default production wiring. |

### Task 1: Specify Node Separation With Focused Tests

**Files:**
- Modify: `tests/unit/test_section_tools.py:9-48`
- Modify: `tests/unit/test_section_warping_tools.py:9-45`
- Modify: `tests/unit/test_section_engineering_tools.py:18-112`
- Modify: `tests/unit/test_dependency.py:41-63,175-200`
- Modify: `tests/unit/test_structural_evidence_models.py:682-862`
- Modify: `tests/unit/test_structural_evidence_verifier.py:120-162`

**Interfaces:**
- Consumes: `ToolRegistration.evidence_nodes`, `ToolBroker.execute(..., evidence_node=...)`, `EvidenceStore.fresh_evidence_status(project_id, node)`, and `DependencyGraph.impact(paths)`.
- Produces: Regression tests proving `analysis.section` and `analysis.structural` cannot satisfy one another's kind-based readiness/freshness and have scoped invalidation.

- [ ] **Step 1: Change the section test graph fixtures to recognize only the intended section node**

In each `_controller()` helper for the three section test files, replace the test graph payload with the following node. This makes a stale call using the old node fail at ToolBroker authorization before it can be persisted.

```python
graph_path.write_text(
    json.dumps(
        {
            "rules": [
                {
                    "when": ["/components/*/name"],
                    "invalidates": ["analysis.section"],
                }
            ],
            "edges": [],
        }
    ),
    encoding="utf-8",
)
```

- [ ] **Step 2: Change every section tool invocation to request the new node and assert the persisted kind**

Use the exact intended node for geometry, warping, and preliminary engineering executions. Immediately after each successful Evidence-producing result, load its Evidence and assert its `kind`; do not assert an ID literal because the UUIDv5 intentionally changes with the node.

```python
assert result.evidence_id is not None
evidence = controller.evidence.load_evidence("PRJ-1", result.evidence_id)
assert evidence.kind == "analysis.section"
assert evidence.structural_evidence_payload is None
```

Keep the existing partial preliminary-engineering assertions unchanged except add:

```python
assert partial.evidence_id is None
```

- [ ] **Step 3: Add a wrong-family readiness and freshness regression to `test_dependency.py`**

Add this test after `test_end_to_end_unrelated_then_material_change_and_replacement`. It uses generic Evidence deliberately: `EvidenceStore` chooses only by node, so the test isolates the F11 failure mode without manufacturing a structural payload.

```python
def test_section_and_structural_nodes_have_isolated_readiness_and_invalidation(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", make_state())
    graph = DependencyGraph.from_yaml("config/dependencies.yaml")
    store = EvidenceStore(tmp_path, manager, graph)
    current = manager._read_current("PRJ-1")
    section = make_evidence(
        manager,
        "PRJ-1",
        evidence_id="EVD-SECTION",
        node="analysis.section",
        revision=current["revision"],
        hash_value=current["state_hash"],
    )
    store.write_evidence("PRJ-1", section)

    assert store.fresh_evidence_status("PRJ-1", "analysis.section") == "fresh evidence exists"
    assert store.fresh_evidence_status("PRJ-1", "analysis.structural") == "fresh evidence missing"

    structural = make_evidence(
        manager,
        "PRJ-1",
        evidence_id="EVD-STRUCTURAL",
        node="analysis.structural",
        revision=current["revision"],
        hash_value=current["state_hash"],
    )
    store.write_evidence("PRJ-1", structural)
    assert store.fresh_evidence_status("PRJ-1", "analysis.structural") == "fresh evidence exists"

    manager.create_revision("PRJ-1", make_state())
    record = store.build_invalidation(
        "PRJ-1",
        2,
        1,
        ("/structural_analysis_definitions/DEF-1",),
        "CS-STRUCTURAL",
    )
    store.record_invalidation(record)

    assert store.get_evidence_freshness("PRJ-1", section.id) is EvidenceFreshness.CURRENT
    assert store.get_evidence_freshness("PRJ-1", structural.id) is EvidenceFreshness.STALE
```

- [ ] **Step 4: Add the reciprocal material-family assertion**

In the same test, create a second revision and record a material invalidation. The section record must stale; a new structural record at revision 2 remains fresh, proving that the later material invalidation is evaluated by node rather than a shared label.

```python
    current = manager._read_current("PRJ-1")
    structural_at_revision_2 = make_evidence(
        manager,
        "PRJ-1",
        evidence_id="EVD-STRUCTURAL-2",
        node="analysis.structural",
        revision=current["revision"],
        hash_value=current["state_hash"],
    )
    store.write_evidence("PRJ-1", structural_at_revision_2)
    manager.create_revision("PRJ-1", make_state())
    store.record_invalidation(
        store.build_invalidation(
            "PRJ-1", 3, 2, ("/materials/MAT-1/material",), "CS-MATERIAL"
        )
    )

    assert store.get_evidence_freshness("PRJ-1", section.id) is EvidenceFreshness.STALE
    assert store.get_evidence_freshness("PRJ-1", structural_at_revision_2.id) is EvidenceFreshness.STALE
```

This verifies the intentionally shared material dependency. Do not assert that
material changes leave FEA fresh: M11 FEA consumes material authority.

- [ ] **Step 5: Add structural typed-identity and fail-closed regression tests**

In `test_structural_evidence_models.py`, extend
`test_structural_evidence_discriminators_bind_kind_subject_and_payload` with:

```python
    assert EvidenceSubject.STRUCTURAL_ANALYSIS.value == "analysis.structural"
    assert ordinary.kind == "analysis.structural"
    assert ordinary.structural_evidence_payload.semantic_hash == evidence_payload.semantic_hash
```

In `test_structural_evidence_verifier.py`, add a test that writes a generic
`analysis.section` tool record to a graph that knows both nodes, then calls
`StructuralEvidenceVerifier.verify()` and expects the existing fail-closed
error. Use the existing `_persisted_evidence()` helper to obtain a fully bound
state manager and artifact store; replace only the graph and write the generic
record:

```python
def test_structural_verifier_rejects_section_tool_evidence(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    graph = DependencyGraph(
        [],
        [
            DependencyEdge(source="analysis.section", target="analysis.result"),
            DependencyEdge(source="analysis.structural", target="analysis.result"),
        ],
    )
    store = EvidenceStore(persisted.workspace, persisted.state_manager, graph)
    section = Evidence(
        id="EVD-SECTION-TOOL",
        kind="analysis.section",
        summary="section result",
        revision=1,
        state_hash=persisted.request.source_binding.source_state_hash,
        producer_type="tool",
        producer_name="mechcad-calc-rectangle-section-properties",
        producer_version="1.0",
    )
    store.write_evidence("PRJ-1", section)
    verifier = StructuralEvidenceVerifier(
        workspace=persisted.workspace,
        project_id="PRJ-1",
        state_manager=persisted.state_manager,
        artifact_store=ArtifactStore(persisted.workspace, project_id="PRJ-1", run_id="RUN-1"),
        evidence_store=store,
    )

    with pytest.raises(StructuralEvidenceIntegrityError, match="not a supported structural analysis record"):
        verifier.verify(section.id)
```

- [ ] **Step 6: Run the new/changed tests before implementation**

Run:

```text
python -m pytest tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_dependency.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q
```

Expected: FAIL because the current registrations authorize
`analysis.structural` and the current dependency configuration does not know
`analysis.section`. Existing unrelated skips are acceptable; record their exact
reason.

### Task 2: Implement the Separate Section Node

**Files:**
- Modify: `src/mechcad_harness/tools/sections.py:35-45`
- Modify: `src/mechcad_harness/tools/section_engineering.py:81-84`
- Modify: `config/dependencies.yaml:4-12`

**Interfaces:**
- Consumes: Existing generic `ToolRegistration.evidence_nodes` and `EvidenceStore.write_evidence()` node-membership validation.
- Produces: Section tools authorized for `analysis.section`; a configured section node that is independently fresh/readable by the existing generic store.

- [ ] **Step 1: Change only M5.5C registration node literals**

In `SectionTools.registrations()`, change all six `evidence_nodes` tuples:

```python
evidence_nodes=("analysis.section",)
```

In `SectionEngineeringTools.registrations()`, make the same one-literal change:

```python
evidence_nodes=("analysis.section",)
```

Do not change `_structural_evidence_complete`; its name is existing M5.5C
partial-result logic and changing it is unrelated cleanup.

- [ ] **Step 2: Add the recognized section node without creating structural coupling**

In the existing `/materials/*` rule in `config/dependencies.yaml`, insert the
new node next to the other analysis nodes:

```yaml
    invalidates:
      - analysis.materials
      - analysis.section
      - analysis.structural
```

Leave these entries byte-for-byte unchanged:

```yaml
  - when:
      - /structural_analysis_definitions/*
    invalidates:
      - analysis.structural
edges:
  - from: analysis.loads
    to: analysis.structural
  - from: analysis.structural
    to: validation.structural
  - from: analysis.structural
    to: analysis.structural.convergence
```

Do not add an `analysis.section` edge. This makes material invalidation
conservative for the whole section family, but structural-definition/load/
validation/convergence changes cannot reach it.

- [ ] **Step 3: Run focused authority tests after implementation**

Run:

```text
python -m pytest tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_dependency.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q
```

Expected: PASS, subject only to pre-existing optional-profile skips. Confirm the
test output shows no failure caused by an unknown dependency node, old section
node authorization, or structural verifier acceptance.

### Task 3: Prove Run Readiness Isolation and Preserve M11 Publication

**Files:**
- Modify: `tests/unit/test_runs.py:251-266`
- Modify: `tests/unit/test_structural_evidence_verifier.py:120-162`

**Interfaces:**
- Consumes: `RunController.evaluate_completion()` and existing `_persisted_evidence()` typed structural fixture.
- Produces: A regression that a run's required node cannot be satisfied by Evidence from the other authority, plus an unchanged typed M11 publication/reload check.

- [ ] **Step 1: Add a run-completion wrong-node test**

Add this test near `test_completion_requires_current_evidence_and_old_unrelated_evidence_reuses`:

```python
def test_completion_does_not_accept_section_evidence_for_structural_requirement(tmp_path):
    controller, _ = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-SECTION", produces=("analysis.section",))
    controller.create_plan(run.run_id, required_evidence_nodes=("analysis.structural",))
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor())

    assert controller.evidence.fresh_evidence_status("PRJ-1", "analysis.section") == "fresh evidence exists"
    assert controller.evidence.fresh_evidence_status("PRJ-1", "analysis.structural") == "fresh evidence missing"
    assert controller.evaluate_completion(run.run_id) is False
```

Update `make_controller()`'s test dependency fixture only as needed to include
`analysis.section`; do not alter the existing analysis-materials or structural
test semantics.

- [ ] **Step 2: Add an unchanged typed FEA persistence assertion**

Extend the existing `_persisted_evidence()`-based verification test rather than
creating a new FEA fixture. Assert the reloaded typed Evidence keeps its M11
identity before calling the existing verifier:

```python
store = EvidenceStore(persisted.workspace, persisted.state_manager, persisted.graph)
reloaded = store.load_evidence(persisted.project_id, persisted.evidence_id)
payload = reloaded.structural_evidence_payload
assert reloaded.kind == "analysis.structural"
assert reloaded.subject is EvidenceSubject.STRUCTURAL_ANALYSIS
assert payload is not None
assert payload.semantic_hash == structural_evidence_hash(payload)
assert reloaded.id == structural_evidence_id(payload)
```

- [ ] **Step 3: Run run-control and structural persistence regressions**

Run:

```text
python -m pytest tests/unit/test_runs.py tests/unit/test_structural_evidence_verifier.py -q
```

Expected: PASS. The new run test proves kind-based completion cannot cross the
authority boundary; the structural suite proves M11 typed publication/reload
identity is unchanged.

### Task 4: Document the Current Authority Boundary

**Files:**
- Modify: `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md:186-205`
- Modify: `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md:92,240,266`
- Test: `git diff --check`

**Interfaces:**
- Consumes: The implemented node constants and registration behavior from Tasks 1-3.
- Produces: Current documentation that distinguishes optional M5.5C section ToolBroker Evidence from M11 typed structural Evidence without rewriting historical documents.

- [ ] **Step 1: Amend the normative structural Evidence paragraph**

Immediately before the existing M11-5 paragraph, add this bounded sentence:

```markdown
M5.5C section geometry, warping, and preliminary section-engineering ToolBroker
Evidence uses `analysis.section`. It is generic tool Evidence and is not
structural-FEA authority, structural readiness, or an input accepted by
`StructuralEvidenceVerifier`.
```

Keep the existing sentence that ordinary M11-5 Evidence is
`analysis.structural` unchanged.

- [ ] **Step 2: Add the node to the optional section capability inventory**

Extend the existing `sectionproperties geometry/warping` inventory description
with this exact bounded clause:

```markdown
When materialized, their Evidence node is `analysis.section`, distinct from M11
typed structural-FEA Evidence.
```

Do not change `EXISTS_UNWIRED` or claim that section tools are defaults; the
composition root accepts them only through `additional_tool_registrations`.

- [ ] **Step 3: Verify documentation scope and whitespace**

Run:

```text
git diff --check
git diff -- config/dependencies.yaml src/mechcad_harness/tools/sections.py src/mechcad_harness/tools/section_engineering.py tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_dependency.py tests/unit/test_runs.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py docs/architecture/MECHCAD_SYSTEM_CONTRACT.md docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md
```

Expected: no whitespace errors; the diff contains no `docs/reconstruction/**`,
`docs/audit/**`, M11 subject/hash/ID implementation change, or unrelated node
rename.

### Task 5: Final Focused Verification

**Files:**
- Test: files changed in Tasks 1-4

**Interfaces:**
- Consumes: Completed F11 implementation and focused regressions.
- Produces: Exact local verification evidence for the approval scope.

- [ ] **Step 1: Compile changed production modules**

Run:

```text
python -m compileall -q src/mechcad_harness/tools/sections.py src/mechcad_harness/tools/section_engineering.py
```

Expected: exit code 0.

- [ ] **Step 2: Run the complete focused F11 gate**

Run:

```text
python -m pytest tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_dependency.py tests/unit/test_runs.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q
```

Expected: PASS, allowing only existing explicit optional dependency skips. Record
the exact pass/skip count; do not reuse an older count.

- [ ] **Step 3: Inspect final scope**

Run:

```text
git diff --check
git status --short
```

Expected: no whitespace errors. Confirm only F11 files plus the already-recorded
unrelated user work are present; do not revert or stage unrelated work.

## Plan Self-Review

- Spec coverage: Tasks 1-3 prove distinct producer nodes, wrong-family
  readiness/freshness rejection, fail-closed structural verification, scoped
  invalidation, persistence/reload, and unchanged M11 identity. Task 4 records
  the current authority boundary without touching historical or accepted audit
  records.
- Placeholder scan: no deferred implementation, unspecified tests, heuristic
  migration, or unbounded cleanup is included.
- Type consistency: all tests use existing `Evidence`, `EvidenceStore`,
  `DependencyGraph`, `EvidenceSubject`, `StructuralEvidenceVerifier`, and
  `ToolBroker` interfaces; no new runtime type or API is introduced.
