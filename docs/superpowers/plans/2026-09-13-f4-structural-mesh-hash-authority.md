# F4 Structural Mesh Hash Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one authoritative mesh-specification hash projection and one authoritative mesh-input hash projection while preserving all existing digest bytes and independent verification.

**Architecture:** `mechcad_harness.structural.models` owns both semantic projections. Producers and verifiers independently invoke those helpers before comparing persisted values; no local hashing wrapper or generic volatile-key filtering remains in the mesh identity path. The closed `MeshSpecification` schema makes all declared fields identity-bearing.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, SHA-256, existing `canonical_json_bytes` serialization primitive.

## Global Constraints

- Remediate F4 only; do not remediate F3/F5/F6/F11/F21 except strictly necessary support.
- Preserve existing mesh-specification and mesh-input digest bytes for the current schema.
- `MeshSpecification` remains `extra="forbid"` and every declared field participates in identity regardless of its name.
- A future non-identity mesh field requires an explicit versioned identity-contract change; no generic volatile-key stripping is permitted.
- Preserve independent producer/verifier recomputation; share the semantic projection, not a persisted hash value.
- Use one local F4 commit and do not push.

---

## File Structure

- Modify: `src/mechcad_harness/structural/models.py` — own `mesh_specification_hash` and retain the canonical `mesh_input_hash` projection.
- Modify: `src/mechcad_harness/structural/service.py` — produce mesh identities through model-owned helpers.
- Modify: `src/mechcad_harness/structural/validation.py` — independently recompute mesh-spec identity through the model-owned helper.
- Modify: `src/mechcad_harness/structural/results.py` — independently recompute mesh-spec and mesh-input identities through model-owned helpers.
- Modify: `src/mechcad_harness/structural/evidence.py` — use the model-owned mesh-spec identity contract without the Evidence volatile-key filter.
- Modify: `src/mechcad_harness/structural/evidence_service.py` — independently recompute mesh-input identity through the model-owned helper.
- Modify: `tests/unit/test_structural_models.py` — characterize exact pre-change digest bytes and the closed-schema/full-field identity policy.
- Modify: `tests/unit/test_structural_service.py` — preserve producer mesh-input metadata verification.
- Modify: `tests/unit/test_structural_results.py` — preserve result-verifier recomputation and reject mismatches.
- Modify: `tests/unit/test_structural_evidence_verifier.py` — preserve Evidence convergence and artifact verifier cross-comparisons.
- Create: `docs/superpowers/specs/2026-09-13-f4-structural-mesh-hash-authority-design.md` — approved F4 design contract.
- Create: `docs/superpowers/plans/2026-09-13-f4-structural-mesh-hash-authority.md` — this implementation plan.

### Task 1: Characterize Existing Identity Bytes and Policy

**Files:**
- Modify: `tests/unit/test_structural_models.py`

**Interfaces:**
- Consumes: `MeshSpecification`, `MeshRefinement`, and existing `mesh_input_hash`.
- Produces: failing expectations for `mesh_specification_hash(specification) -> str` and frozen reference digests that later tasks must preserve.

- [ ] **Step 1: Record the pre-change reference values in an isolated Python invocation**

Run:

```powershell
python -c "from mechcad_harness.structural_request import MeshSpecification, MeshRefinement; from mechcad_harness.structural.service import _mesh_specification_hash; from mechcad_harness.structural.models import mesh_input_hash; spec=MeshSpecification(global_target_size_mm=5.0, refinements=(MeshRefinement(region_id='free', target_size_mm=2.5),), quality_policy_id='quality@1', mesher_settings_version='gmsh-settings@1'); print(_mesh_specification_hash(type('Request', (), {'mesh_specification': spec})())); print(mesh_input_hash(source_geometry_hash='sha256:'+'1'*64, mesh_specification_hash=_mesh_specification_hash(type('Request', (), {'mesh_specification': spec})()), region_map_hash='sha256:'+'2'*64, gmsh_identity='mechcad-structural-gmsh@1', gmsh_version='4.13.1'))"
```

Expected: two `sha256:` digests. Copy both exact values into the tests below; they are the pre-change checkpoint.

Recorded pre-change checkpoint:

```text
mesh_specification_hash = sha256:174fe65bf908f1eb7498e1f375f4dd9f09bca7ec9f5786da2652455d40a3d7cd
mesh_input_hash         = sha256:4919280e8151fad564c3fccb5fff8208b914aa486117c6e5efb5670facfd2000
```

- [ ] **Step 2: Write failing characterization tests**

```python
from pydantic import ValidationError

from mechcad_harness.structural.models import mesh_input_hash, mesh_specification_hash
from mechcad_harness.structural_request import MeshRefinement, MeshSpecification


def _identity_specification(**updates) -> MeshSpecification:
    values = {
        "element_family": "c3d10",
        "global_target_size_mm": 5.0,
        "refinements": (MeshRefinement(region_id="free", target_size_mm=2.5),),
        "quality_policy_id": "quality@1",
        "mesher_settings_version": "gmsh-settings@1",
    }
    values.update(updates)
    return MeshSpecification(**values)


def test_mesh_identity_reference_digests_preserve_pre_change_bytes():
    specification = _identity_specification()
    assert mesh_specification_hash(specification) == "sha256:174fe65bf908f1eb7498e1f375f4dd9f09bca7ec9f5786da2652455d40a3d7cd"
    assert mesh_input_hash(
        source_geometry_hash="sha256:" + "1" * 64,
        mesh_specification_hash=mesh_specification_hash(specification),
        region_map_hash="sha256:" + "2" * 64,
        gmsh_identity="mechcad-structural-gmsh@1",
        gmsh_version="4.13.1",
    ) == "sha256:4919280e8151fad564c3fccb5fff8208b914aa486117c6e5efb5670facfd2000"


def test_every_declared_mesh_specification_field_participates_in_identity():
    baseline = _identity_specification()
    changes = {
        "element_family": "future-family",
        "global_target_size_mm": 4.0,
        "refinements": (),
        "quality_policy_id": "quality@2",
        "mesher_settings_version": "gmsh-settings@2",
    }
    assert set(changes) == set(MeshSpecification.model_fields)
    for field_name, value in changes.items():
        altered = baseline.model_copy(update={field_name: value})
        assert mesh_specification_hash(altered) != mesh_specification_hash(baseline)


def test_mesh_specification_rejects_unknown_volatile_named_fields():
    with pytest.raises(ValidationError):
        _identity_specification(timestamp="2026-09-13T00:00:00Z")
```

`model_copy(update=...)` deliberately supplies a distinct serialized value for
the currently single-valued `element_family` field without asserting that value
is a valid request. The test proves the hashing projection includes every
declared field; normal construction still enforces the `c3d10` literal.

- [ ] **Step 3: Run the new tests to verify the missing mesh-spec helper fails**

Run: `pytest tests/unit/test_structural_models.py -k "mesh_identity_reference or every_declared_mesh or unknown_volatile" -v`

Expected: collection failure because `mesh_specification_hash` is not importable.

### Task 2: Establish the Model-Owned Projections

**Files:**
- Modify: `src/mechcad_harness/structural/models.py:10-14,698-706`
- Test: `tests/unit/test_structural_models.py`

**Interfaces:**
- Consumes: `MeshSpecification` and `canonical_json_text` through existing `_hash_payload`.
- Produces: `mesh_specification_hash(specification: MeshSpecification) -> str`; preserves `mesh_input_hash(*, source_geometry_hash: str, mesh_specification_hash: str, region_map_hash: str, gmsh_identity: str, gmsh_version: str) -> str`.

- [ ] **Step 1: Add the missing import and canonical helper**

```python
from mechcad_harness.structural_request import MeshSpecification


def mesh_specification_hash(specification: MeshSpecification) -> str:
    """Return the identity of every declared field in a closed mesh specification."""
    return _hash_payload(specification.model_dump(mode="json"))
```

Place the helper immediately before `mesh_input_hash`. Do not call Evidence `_hash`, `_canonical`, or a volatile-key filter.

- [ ] **Step 2: Run the characterization tests**

Run: `pytest tests/unit/test_structural_models.py -k "mesh_identity_reference or every_declared_mesh or unknown_volatile" -v`

Expected: PASS. The exact reference digests must equal the recorded pre-change values.

### Task 3: Replace Local Mesh-Spec and Mesh-Input Authorities

**Files:**
- Modify: `src/mechcad_harness/structural/service.py:3,7,20-28,43-46,169-176`
- Modify: `src/mechcad_harness/structural/validation.py:215,664-666`
- Modify: `src/mechcad_harness/structural/results.py:1016,1106-1111,1203`
- Modify: `src/mechcad_harness/structural/evidence.py:462-463`
- Modify: `src/mechcad_harness/structural/evidence_service.py:35,347,1286,1514-1525`
- Test: `tests/unit/test_structural_service.py`
- Test: `tests/unit/test_structural_results.py`
- Test: `tests/unit/test_structural_evidence_verifier.py`

**Interfaces:**
- Consumes: `mesh_specification_hash` and `mesh_input_hash` from `structural.models`.
- Produces: production and verification paths that independently call the same semantic projection.

- [ ] **Step 1: Change each caller to import and invoke the model helpers**

```python
from mechcad_harness.structural.models import mesh_input_hash, mesh_specification_hash

# Producer and verifier each recompute the projection before their existing comparison.
mesh_spec_hash = mesh_specification_hash(request.mesh_specification)
mesh_input_identity = mesh_input_hash(
    source_geometry_hash=request.source_binding.geometry_artifact_hash,
    mesh_specification_hash=mesh_spec_hash,
    region_map_hash=manifest.region_map_hash,
    gmsh_identity=manifest.gmsh_identity,
    gmsh_version=manifest.gmsh_version,
)
```

Delete `service._mesh_specification_hash`, `validation._mesh_specification_hash`, `StructuralResultInterpreter._mesh_specification_hash`, `structural_mesh_specification_hash`, and `StructuralEvidenceVerifier._mesh_input_hash`. Remove now-unused `hashlib`, `json`, and `canonical_json_bytes` imports only when no remaining code uses them.

- [ ] **Step 2: Update direct test references to the public model helpers**

```python
from mechcad_harness.structural.models import mesh_input_hash, mesh_specification_hash

mesh_spec_hash = mesh_specification_hash(request.mesh_specification)
assert mesh_specification_hash(request.mesh_specification) == expected_mesh_hash
```

Replace all references to removed local helpers. Retain existing artifact metadata tampering tests so they continue to prove verifier recomputation rejects mismatched persisted identities.

- [ ] **Step 3: Run focused producer/verifier regression tests**

Run: `pytest tests/unit/test_structural_models.py tests/unit/test_structural_service.py tests/unit/test_structural_results.py tests/unit/test_structural_evidence_verifier.py -q`

Expected: PASS. This is the producer/verifier cross-comparison gate.

### Task 4: Confirm Single Authority and Deliver F4 Evidence

**Files:**
- Modify: the files from Tasks 1-3 only, plus the approved design and plan documents.

**Interfaces:**
- Consumes: completed focused tests and the exact pre-change digest constants.
- Produces: one reviewable F4 commit with no push.

- [ ] **Step 1: Confirm no local duplicate hash projections remain**

Run:

```powershell
rg -n "def (_mesh_specification_hash|structural_mesh_specification_hash|_mesh_input_hash)|def mesh_(specification|input)_hash" src/mechcad_harness/structural
```

Expected: exactly two definitions, both in `src/mechcad_harness/structural/models.py`.

- [ ] **Step 2: Run focused tests and full unit suite**

Run: `pytest tests/unit/test_structural_models.py tests/unit/test_structural_service.py tests/unit/test_structural_results.py tests/unit/test_structural_evidence_verifier.py -q`

Expected: PASS.

Run: `pytest tests/unit -q`

Expected: PASS. If environment or time prevents completion, retain the exact failure/timeout result and report it without claiming full-suite success.

- [ ] **Step 3: Run static validation and review the exact F4 diff**

Run: `git diff --check`

Expected: no output and exit code 0.

Run: `git diff -- src/mechcad_harness/structural/models.py src/mechcad_harness/structural/service.py src/mechcad_harness/structural/validation.py src/mechcad_harness/structural/results.py src/mechcad_harness/structural/evidence.py src/mechcad_harness/structural/evidence_service.py tests/unit/test_structural_models.py tests/unit/test_structural_service.py tests/unit/test_structural_results.py tests/unit/test_structural_evidence_verifier.py docs/superpowers/specs/2026-09-13-f4-structural-mesh-hash-authority-design.md docs/superpowers/plans/2026-09-13-f4-structural-mesh-hash-authority.md`

Expected: only F4 ownership consolidation, characterization tests, and requested documentation.

- [ ] **Step 4: Request a fresh skeptical review**

Ask the reviewer to attempt to disprove these claims: exactly one mesh-specification authority; exactly one mesh-input authority; current digest bytes unchanged; all declared mesh fields participate; unknown volatile-named fields fail closed; producer and verifier independently recompute; no F3/F5/F6/F11/F21 remediation is included.

- [ ] **Step 5: Create the single authorized local commit after review passes**

```powershell
git add docs/superpowers/specs/2026-09-13-f4-structural-mesh-hash-authority-design.md docs/superpowers/plans/2026-09-13-f4-structural-mesh-hash-authority.md src/mechcad_harness/structural/models.py src/mechcad_harness/structural/service.py src/mechcad_harness/structural/validation.py src/mechcad_harness/structural/results.py src/mechcad_harness/structural/evidence.py src/mechcad_harness/structural/evidence_service.py tests/unit/test_structural_models.py tests/unit/test_structural_service.py tests/unit/test_structural_results.py tests/unit/test_structural_evidence_verifier.py
git commit -m "refactor(structural): centralize mesh identity hashing"
```

Expected: one new local commit. Do not push.

## Self-Review

- Spec coverage: Tasks 1-2 establish the two contract owners and exact-byte characterization. Task 3 removes all six local semantic authorities while retaining independent recomputation. Task 4 verifies duplicate removal, focused and full unit tests, static diff cleanliness, skeptical review, and one no-push commit.
- Placeholder scan: the exact pre-change checkpoint is recorded in Task 1 and all implementation/test snippets are concrete.
- Type consistency: every consuming module imports `mesh_specification_hash` and `mesh_input_hash` from `structural.models`; both helper signatures match the current model and artifact metadata call sites.
