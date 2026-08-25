# M11-3 Failure-Coverage Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the M11-3 structural mesh/solver foundation's demonstrated failure-coverage gaps and publish an evidence-backed audit disposition.

**Architecture:** Add one fake-backed service test module for source binding, artifact integrity, pipeline stage classification, preflight, solver outcomes, and manifest persistence. Add direct unit tests for mesh/deck validation, force conservation, runtime failure semantics, and fake-provider provenance. Change only stage exception translation and geometry aggregation needed for those tests, then validate with the real FreeCAD/Gmsh/CalculiX vertical slice.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, FreeCAD 1.1.3, Gmsh 4.15.0, CalculiX 2.22.

## Global Constraints

- Preserve M8/M9/M10 behavior and existing public contracts.
- Keep `DesignState` canonical and source/run/artifact binding fail-closed.
- Do not create structural results, acceptance decisions, or Evidence records.
- Keep fake provider identities distinct from trusted live provider identities.
- Do not commit or push.

---

### Task 1: Establish Source and Pipeline Failure Semantics

**Files:**
- Create: `tests/unit/test_structural_service.py`
- Modify: `src/mechcad_harness/structural/service.py`
- Modify: `src/mechcad_harness/structural/geometry.py`

**Interfaces:**
- Consumes: `StructuralAnalysisService.execute(request) -> StructuralExecutionResult`.
- Produces: stage-specific `StructuralExecutionStatus` values without invoking later pipeline providers.

- [ ] **Step 1: Write failing tests**

```python
def test_execute_rejects_tampered_source_artifact_before_geometry(...):
    result = service.execute(request)
    assert result.execution_status == StructuralExecutionStatus.GEOMETRY_REJECTED
    assert geometry.calls == 0

def test_execute_classifies_region_resolution_failure(...):
    result = service.execute(request)
    assert result.execution_status == StructuralExecutionStatus.REGION_RESOLUTION_FAILED
```

- [ ] **Step 2: Run the targeted tests and confirm expected failures**

Run: `py -3 -m pytest tests/unit/test_structural_service.py -q`

- [ ] **Step 3: Implement minimal exception translation and aggregate all imported STEP shapes**

```python
except RegionResolutionError as exc:
    raise StructuralPipelineError("region_resolution", StructuralExecutionStatus.REGION_RESOLUTION_FAILED, str(exc)) from exc
```

- [ ] **Step 4: Run targeted service tests**

Run: `py -3 -m pytest tests/unit/test_structural_service.py -q`

### Task 2: Establish Deck, Mesh, Preflight, Solver, and Fake Contracts

**Files:**
- Create: `tests/unit/test_structural_pipeline_contracts.py`
- Modify: `src/mechcad_harness/structural/deck.py`
- Modify: `src/mechcad_harness/structural/mesh.py`

**Interfaces:**
- Consumes: `StructuralDeckBuilder.validate`, `StructuralGmshMeshingProvider._validate_mesh`, `ConstraintPreflight.evaluate`, and `StructuralCalculiXSolverProvider.execute`.
- Produces: rejection before solver invocation, exact force/moment conservation, strict solver output classification, and fake identity separation.

- [ ] **Step 1: Write failing tests for representative invalid deck and invalid mesh cases**

```python
def test_validate_rejects_surface_reference_to_unknown_volume_element():
    with pytest.raises(DeckBuildError, match="unknown element"):
        StructuralDeckBuilder().validate(representation)

def test_validate_mesh_rejects_non_midpoint_c3d10_node():
    with pytest.raises(MeshProviderError, match="not edge midpoint"):
        provider._validate_mesh(parsed_mesh)
```

- [ ] **Step 2: Write direct tests for rank, solver outcomes, and fake provenance**

```python
def test_preflight_returns_rank_six_for_non_collinear_fixed_nodes():
    assert ConstraintPreflight().evaluate(nodes, {"fixed": (1, 2, 3)}).rigid_body_rank == 6

def test_fake_provider_identity_is_not_live_provider_identity():
    assert FakeStructuralCalculiXSolverProvider.identity != CALCULIX_PROVIDER_IDENTITY
```

- [ ] **Step 3: Run the targeted tests and correct only observed defects**

Run: `py -3 -m pytest tests/unit/test_structural_pipeline_contracts.py -q`

- [ ] **Step 4: Remove temporary debug output and re-run both structural unit modules**

Run: `py -3 -m pytest tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py -q`

### Task 3: Strengthen Live Artifact and Manifest Verification

**Files:**
- Modify: `tests/integration/test_m11_3_live_structural.py`
- Modify: `docs/audit/MECHCAD_M11_3_COMPLETION_REPORT.md`

**Interfaces:**
- Consumes: persisted `ArtifactStore` artifacts and serialized `StructuralExecutionManifest`.
- Produces: byte re-hash and JSON reload evidence for mesh, deck, FRD, DAT, log, and manifest artifacts.

- [ ] **Step 1: Write a failing live-test assertion that reloads the manifest artifact and requires DAT on success**

```python
manifest_artifact = next(a for a in result.produced_artifact_ids if a.endswith("JSON") is False)
assert manifest.dat_artifact_id is not None
assert StructuralExecutionManifest.model_validate_json(manifest_path.read_text()) == manifest
```

- [ ] **Step 2: Run the live test and fix the assertion implementation if needed**

Run: `py -3 -m pytest tests/integration/test_m11_3_live_structural.py -q`

- [ ] **Step 3: Update the completion report only with verified claims and exact command outcomes**

```markdown
## Final Independent Verification

- Core M11-3 unit tests: `<actual pytest count>`
- Live vertical slice: `<actual pytest outcome>`
- Full suite: `<actual pytest outcome>`
```

### Task 4: Final Verification and Disposition

**Files:**
- Modify: `docs/audit/MECHCAD_M11_3_COMPLETION_REPORT.md`

- [ ] **Step 1: Run predecessor regression tests**

Run: `py -3 -m pytest tests/unit/test_state_foundation.py tests/unit/test_changes.py tests/integration/test_imported_assembly_bridge.py -q`

- [ ] **Step 2: Run the full suite**

Run: `py -3 -m pytest tests/ -q`

- [ ] **Step 3: Run static and whitespace checks**

Run: `py -3 -m compileall src/mechcad_harness -q`

Run: `git diff --check`

- [ ] **Step 4: Record the disposition**

```markdown
## Final Disposition

`M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED` only if every command above passes and the report makes no unsupported claim.
```
