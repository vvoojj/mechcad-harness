# M3 Dependency Invalidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic dependency impact, immutable invalidation/evidence persistence, and fail-closed evidence freshness to the M0-M2 harness.

**Architecture:** Keep `DesignState` and `StateManager` canonical. Add a focused `dependency` package that loads static path rules and dependency edges, returns direct/transitive impacts, persists invalidation records and evidence outside snapshots, and evaluates freshness by exact provenance plus complete post-evidence invalidation coverage. Extend the M2 engine only with a small `AppliedChangeResult` return value containing the snapshot, changeset ID, and changed paths.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, filesystem JSON persistence, pytest.

## Global Constraints

- Keep changes inside this repository.
- Preserve Python 3.11+, Pydantic v2, and UTC-aware datetime requirements.
- Keep models minimal and reject empty required strings and non-positive revisions.
- Treat `DesignState` as canonical state; evidence and invalidation records remain separate bindable records.
- Do not add agents, OpenCode integration, CAD, FreeCAD, FEA, scheduling, dependency execution, LLM workflows, databases, or external services.
- Do not commit unless explicitly requested.
- Dependency patterns use exact segments, one-segment `*`, and prefix matching only.
- Freshness checks revisions strictly after the evidence revision and fail closed on missing coverage.

---

### Task 1: Dependency Graph Models and Configuration

**Files:**
- Create: `src/mechcad_harness/dependency/models.py`
- Create: `src/mechcad_harness/dependency/errors.py`
- Modify: `src/mechcad_harness/dependency/__init__.py`
- Modify: `config/dependencies.yaml`
- Test: `tests/unit/test_dependency.py`

**Interfaces:**
- Produce `DependencyRule`, `DependencyEdge`, `DependencyGraph`, and `ChangeImpact` models/classes.
- Produce `DependencyGraph.from_yaml(path)`, `match(pattern, path)`, and `impact(changed_paths)`.
- `impact` returns sorted, deduplicated direct and transitive node tuples.

- [ ] **Step 1: Add failing graph tests**

```python
def test_dependency_pattern_matches_descendant_path(tmp_path):
    graph = DependencyGraph.from_yaml(write_dependencies(tmp_path))
    impact = graph.impact(["/materials/MAT-001/material"])
    assert "analysis.materials" in impact.direct_nodes


def test_dependency_graph_rejects_cycles(tmp_path):
    path = write_dependencies(tmp_path, edges=[("analysis.a", "analysis.b"), ("analysis.b", "analysis.a")])
    with pytest.raises(DependencyCycleError):
        DependencyGraph.from_yaml(path)
```

- [ ] **Step 2: Run the focused tests and verify expected missing-symbol failures**

Run: `py -m pytest tests/unit/test_dependency.py -q`

Expected: collection or assertion failure because the M3 graph API does not yet exist.

- [ ] **Step 3: Implement static YAML parsing and deterministic graph traversal**

Implement literal and `*` segment matching where a rule pattern is allowed to be a prefix of the changed path. Validate patterns, node names, YAML structure, and duplicate/cyclic edges. Use DFS with sorted adjacency and a visiting set; raise `DependencyCycleError` on a back edge.

- [ ] **Step 4: Run focused graph tests**

Run: `py -m pytest tests/unit/test_dependency.py -q`

Expected: all graph matching, deduplication, transitive traversal, config, and cycle tests pass.

### Task 2: M2 Applied Change Boundary

**Files:**
- Modify: `src/mechcad_harness/changes/engine.py`
- Modify: `src/mechcad_harness/changes/__init__.py`
- Test: `tests/unit/test_changes.py`

**Interfaces:**
- Produce `AppliedChangeResult(snapshot: RevisionSnapshot, changeset_id: str, changed_paths: tuple[str, ...])`.
- `ChangeEngine.apply_proposal` returns `AppliedChangeResult` while preserving all existing validation and atomicity behavior.

- [ ] **Step 1: Add a failing return-boundary assertion**

```python
result = engine.apply_proposal("demo", proposal)
assert result.snapshot.revision == 2
assert result.changed_paths == ("/materials/MAT-001/material",)
assert result.changeset_id.startswith("CS-")
```

- [ ] **Step 2: Run the existing change tests and confirm the new assertion fails against the snapshot return value**

Run: `py -m pytest tests/unit/test_changes.py -q`

- [ ] **Step 3: Return the small typed result after canonical revision creation**

Keep all operation application in memory before `create_revision`; derive changed paths from operation order and deduplicate them deterministically without changing M2 path semantics.

- [ ] **Step 4: Run all M2 tests**

Run: `py -m pytest tests/unit/test_changes.py tests/unit/test_state_foundation.py -q`

Expected: all M2 behavior passes with the new return type.

### Task 3: Immutable Invalidation and Evidence Records

**Files:**
- Create: `src/mechcad_harness/dependency/storage.py`
- Modify: `src/mechcad_harness/models/evidence.py`
- Modify: `src/mechcad_harness/models/__init__.py`
- Modify: `src/mechcad_harness/dependency/__init__.py`
- Test: `tests/unit/test_dependency.py`

**Interfaces:**
- Produce `InvalidationRecord`, `EvidenceFreshness`, and `EvidenceStore` models/APIs.
- `DependencyStore.record_invalidation(project_id, result, created_at=None)` writes one exclusive `REV-XXXXXX.json` file.
- `EvidenceStore.write(project_id, evidence)` writes one exclusive `<evidence_id>.json` file.
- Existing files raise `InvalidationError` or `EvidenceConflictError` and are never overwritten.

- [ ] **Step 1: Add failing persistence and immutability tests**

```python
store.record_invalidation("demo", record)
original = invalidation_path.read_bytes()
with pytest.raises(InvalidationError):
    store.record_invalidation("demo", record)
assert invalidation_path.read_bytes() == original

evidence_store.write("demo", evidence)
with pytest.raises(EvidenceConflictError):
    evidence_store.write("demo", evidence)
```

- [ ] **Step 2: Run focused persistence tests and verify they fail before implementation**

Run: `py -m pytest tests/unit/test_dependency.py -q`

- [ ] **Step 3: Implement exclusive atomic JSON persistence**

Use UTC-aware timestamps, sorted JSON, and exclusive destination checks before and after temporary-file creation. Store records outside revisions/current state. Validate evidence node names through the graph before writing.

- [ ] **Step 4: Run persistence and snapshot immutability tests**

Run: `py -m pytest tests/unit/test_dependency.py tests/unit/test_state_foundation.py -q`

Expected: records persist externally, duplicate writes fail, and historical revision bytes remain unchanged.

### Task 4: Fail-Closed Freshness Service

**Files:**
- Create: `src/mechcad_harness/dependency/service.py`
- Modify: `src/mechcad_harness/dependency/errors.py`
- Modify: `src/mechcad_harness/dependency/__init__.py`
- Test: `tests/unit/test_dependency.py`

**Interfaces:**
- Produce `DependencyService.get_change_impact`, `record_invalidation`, `get_invalidated_nodes`, `get_evidence_freshness`, `is_evidence_fresh`, and `fresh_evidence_status`.
- `get_evidence_freshness` returns `CURRENT`, `STALE`, or `UNKNOWN`.

- [ ] **Step 1: Add failing freshness tests**

Cover: unrelated changes remain current; matching later changes become stale; evidence at revision N ignores revision N invalidation; missing intermediate invalidation returns unknown; wrong state hash returns unknown; unknown node returns unknown; stale evidence remains stale; replacement evidence at the new revision is current; unknown is rejected by `is_evidence_fresh`.

- [ ] **Step 2: Run focused tests and verify failures**

Run: `py -m pytest tests/unit/test_dependency.py -q`

- [ ] **Step 3: Implement provenance and coverage checks before node invalidation evaluation**

Load the exact canonical revision through `StateManager`, compare its stored `state_hash` to evidence, and return `UNKNOWN` on missing revision or mismatch. Require one valid invalidation record for every integer revision from `evidence.state_revision + 1` through current revision. Any missing/corrupt record returns `UNKNOWN`; do not infer no impact. Only after those checks, return `STALE` if any record includes the evidence node, otherwise `CURRENT`.

- [ ] **Step 4: Implement fresh-evidence query semantics**

`is_evidence_fresh` returns true only for `CURRENT`. `fresh_evidence_status` distinguishes no evidence, only stale evidence, and fresh evidence without treating `UNKNOWN` as fresh.

- [ ] **Step 5: Run focused freshness tests**

Run: `py -m pytest tests/unit/test_dependency.py -q`

Expected: all current/stale/unknown and fail-closed tests pass.

### Task 5: M2-to-M3 Application Integration

**Files:**
- Modify: `src/mechcad_harness/changes/engine.py`
- Create or modify: `src/mechcad_harness/dependency/service.py`
- Test: `tests/unit/test_dependency.py`

**Interfaces:**
- M3 consumes `AppliedChangeResult`; it does not own revision creation and does not run recalculation.

- [ ] **Step 1: Add the end-to-end failing test**

Exercise revision 1 evidence creation, an unrelated revision 2, a material revision 3, and replacement material evidence at revision 3. Assert current evidence after revision 2, stale material evidence after revision 3, unaffected evidence remains current, and replacement evidence is current.

- [ ] **Step 2: Run the end-to-end test and verify failure**

Run: `py -m pytest tests/unit/test_dependency.py -k end_to_end -q`

- [ ] **Step 3: Wire `AppliedChangeResult` into explicit M3 `record_invalidation` calls**

The service records the impact for each accepted revision. If invalidation persistence fails, the canonical snapshot remains valid but freshness queries fail closed because the required record is absent. Do not add event buses, scheduling, or automatic recalculation.

- [ ] **Step 4: Run the end-to-end and regression tests**

Run: `py -m pytest tests/unit/test_dependency.py tests/unit/test_changes.py tests/unit/test_state_foundation.py -q`

### Task 6: Documentation and Scope Verification

**Files:**
- Modify: `README.md`
- Modify: `config/dependencies.yaml`
- Test: all test files

- [ ] **Step 1: Document the M3 data flow and freshness distinction**

Explain canonical state versus derived evidence, exact provenance versus dependency freshness, complete-history fail-closed behavior, immutable stale evidence, deterministic prefix matching, and the fact that execution/recalculation is later scope.

- [ ] **Step 2: Populate only the initial dependency rules and transitive edges**

Use the four requested path rules and the minimal loads/structural/validation edges needed for tests. Do not add future engineering-domain coverage.

- [ ] **Step 3: Run full verification**

Run:

```text
py -m pytest -q
py -m compileall -q src tests
git diff --check
```

Expected: all tests pass, compile succeeds, and diff check is clean.

- [ ] **Step 4: Inspect scope and report files, rules, examples, and deviations**

Confirm no M4+ execution/orchestration or external persistence was added, canonical revision bytes remain unchanged, stale/unknown evidence is never current, and the working tree remains uncommitted.
