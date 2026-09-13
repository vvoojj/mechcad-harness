# F3 Evidence Currentness Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the duplicate structural/candidate currentness enum classes by re-exporting one neutral leaf enum while preserving M3, structural, and candidate evaluation semantics exactly.

**Architecture:** Add `core/currentness.py` beside the accepted F2 neutral core as the dependency-leaf owner of the three shared currentness strings. `StructuralEvidenceCurrentness` and `CandidateCurrentness` become direct aliases of `Currentness`; their evaluators are not refactored. M3 `EvidenceFreshness` remains independent, and tests explicitly preserve the graph-freshness versus strict-pointer versus candidate-source-relevance boundary.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, standard-library `enum`, `ast`, and `importlib`.

## Global Constraints

- Work only on F3; do not begin F8, F21, P3 findings, general cleanup, or unrelated refactoring.
- Preserve `current`, `stale_relative_to_current_state`, and `currentness_unavailable` exactly for structural/candidate currentness.
- Preserve public imports `mechcad_harness.structural.evidence.StructuralEvidenceCurrentness` and `mechcad_harness.candidates.services.CandidateCurrentness` as true aliases of one enum object.
- Keep `EvidenceFreshness` and M3 `DependencyGraph` / `EvidenceStore` semantics unchanged.
- Keep `StructuralEvidenceVerifier.currentness` strict-pointer-only and `CandidateCurrentnessService` relevance-sensitive-only.
- Do not add implicit graph-freshness composition to structural or candidate consumers.
- Preserve F11's `analysis.section` and `analysis.structural` namespace separation.
- Do not change F1 M10 trust stages, F4 mesh hashes, F5 provenance identity, F6 physical-root hashes, F7 CAD dimensions, or `docs/reconstruction/**`.
- Do not run FreeCAD, Gmsh, or CalculiX; all required verification is local unit/static verification.
- Do not commit, push, amend, tag, or alter unrelated dirty/untracked work without separate user authorization.
- Do not record test results in the accepted audit until the exact listed command has completed; retain failures/timeouts truthfully.

## File Structure

| File | Responsibility |
| --- | --- |
| `src/mechcad_harness/core/currentness.py` | Neutral, standard-library-only owner of the shared structural/candidate `Currentness` enum. |
| `src/mechcad_harness/structural/evidence.py` | Re-export `StructuralEvidenceCurrentness` as a direct alias of the neutral enum; retain all structural models and logic. |
| `src/mechcad_harness/candidates/services.py` | Re-export `CandidateCurrentness` as a direct alias of the neutral enum; retain all candidate integrity/currentness logic. |
| `tests/unit/test_core_currentness.py` | Assert one enum identity, exact status strings, leaf-import policy, and package importability. |
| `tests/unit/test_structural_evidence_models.py` | Preserve structural public-name/status behavior. |
| `tests/unit/test_m12_candidate_foundation.py` | Preserve candidate relevance-sensitive behavior across unrelated and relevant state changes. |
| `tests/unit/test_dependency.py` | Preserve M3 graph freshness and add the graph-current/strict-pointer-stale distinction regression. |
| `docs/audit/MECHCAD_LOGIC_DUPLICATION_AUDIT.md` | Append an F3 post-acceptance record that corrects current-tree semantics without editing the historical finding. |
| `docs/audit/MECHCAD_CAPABILITY_OWNERSHIP_MAP.md` | Update current authority rows and summary counts to reflect resolved enum duplication and preserved distinct evaluators. |

---

### Task 1: Establish the Neutral Status Authority

**Files:**
- Create: `src/mechcad_harness/core/currentness.py`
- Create: `tests/unit/test_core_currentness.py`

**Interfaces:**
- Produces: `Currentness(StrEnum)` with `CURRENT`, `STALE_RELATIVE_TO_CURRENT_STATE`, and `CURRENTNESS_UNAVAILABLE`.
- Produces: standard-library-only import boundary for the new core module.
- Consumes later: structural and candidate modules import this type without importing each other, `dependency`, `state`, or `application`.

- [ ] **Step 1: Write the failing alias and leaf-boundary tests**

```python
# tests/unit/test_core_currentness.py
from __future__ import annotations

import ast
import importlib
from pathlib import Path


def test_currentness_is_one_neutral_enum_with_unchanged_wire_values():
    from mechcad_harness.candidates.services import CandidateCurrentness
    from mechcad_harness.core.currentness import Currentness
    from mechcad_harness.structural.evidence import StructuralEvidenceCurrentness

    assert StructuralEvidenceCurrentness is Currentness
    assert CandidateCurrentness is Currentness
    assert tuple(Currentness) == (
        Currentness.CURRENT,
        Currentness.STALE_RELATIVE_TO_CURRENT_STATE,
        Currentness.CURRENTNESS_UNAVAILABLE,
    )
    assert [member.value for member in Currentness] == [
        "current",
        "stale_relative_to_current_state",
        "currentness_unavailable",
    ]


def test_currentness_core_is_a_dependency_leaf_and_public_modules_import():
    source_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "mechcad_harness"
        / "core"
        / "currentness.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = [
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    ]
    imports.extend(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert not any(name == "mechcad_harness" or name.startswith("mechcad_harness.") for name in imports)
    importlib.import_module("mechcad_harness.core.currentness")
    importlib.import_module("mechcad_harness.structural.evidence")
    importlib.import_module("mechcad_harness.candidates.services")
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `python -m pytest tests/unit/test_core_currentness.py -q`

Expected: FAIL because `mechcad_harness.core.currentness` does not exist.

- [ ] **Step 3: Add the exact neutral leaf module**

```python
# src/mechcad_harness/core/currentness.py
"""Neutral structural/candidate currentness status vocabulary (F3)."""

from enum import StrEnum


class Currentness(StrEnum):
    CURRENT = "current"
    STALE_RELATIVE_TO_CURRENT_STATE = "stale_relative_to_current_state"
    CURRENTNESS_UNAVAILABLE = "currentness_unavailable"


__all__ = ["Currentness"]
```

Keep this module standard-library-only. `core/canonical.py` already establishes
the package's accepted dependency-leaf convention; `core/currentness.py` is the
correct exact location because both structural and candidate packages already
depend inward on `core`, while `dependency` would incorrectly imply M3 graph
semantics and either domain package would invert the other package's ownership.

- [ ] **Step 4: Run the core test to verify the leaf module passes its own policy**

Run: `python -m pytest tests/unit/test_core_currentness.py -q`

Expected: the leaf-policy assertion passes; the alias assertion still fails until Task 2.

### Task 2: Re-export the Neutral Enum Without Changing Evaluators

**Files:**
- Modify: `src/mechcad_harness/structural/evidence.py:5,59-62`
- Modify: `src/mechcad_harness/candidates/services.py:4,20-23`
- Modify: `tests/unit/test_structural_evidence_models.py:417-421`
- Modify: `tests/unit/test_m12_candidate_foundation.py:190-202,311-314`
- Test: `tests/unit/test_core_currentness.py`

**Interfaces:**
- Consumes: `Currentness` from `mechcad_harness.core.currentness`.
- Produces: `StructuralEvidenceCurrentness is Currentness` and `CandidateCurrentness is Currentness`.
- Preserves: `StructuralEvidenceVerifier.currentness(evidence_id)` return values and `CandidateCurrentnessService.evaluate_source_binding(candidate)` branch behavior.

- [ ] **Step 1: Add focused failing public-alias and semantic-regression assertions**

```python
# Add to tests/unit/test_structural_evidence_models.py
from mechcad_harness.core.currentness import Currentness


def test_structural_currentness_name_is_the_neutral_status_authority():
    assert StructuralEvidenceCurrentness is Currentness
    assert StructuralEvidenceCurrentness.CURRENT.value == "current"
    assert (
        StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE.value
        == "stale_relative_to_current_state"
    )
    assert (
        StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE.value
        == "currentness_unavailable"
    )
```

```python
# Add to tests/unit/test_m12_candidate_foundation.py
from mechcad_harness.core.currentness import Currentness


def test_candidate_currentness_name_is_the_neutral_status_authority():
    assert CandidateCurrentness is Currentness
    assert CandidateCurrentness.CURRENT.value == "current"
    assert (
        CandidateCurrentness.STALE_RELATIVE_TO_CURRENT_STATE.value
        == "stale_relative_to_current_state"
    )
    assert (
        CandidateCurrentness.CURRENTNESS_UNAVAILABLE.value
        == "currentness_unavailable"
    )
```

Do not replace the existing candidate test that proves an unrelated revision is
`CURRENT` and a consumed-path change is `STALE_RELATIVE_TO_CURRENT_STATE`; it is
the behavioral guard against accidentally turning candidate currentness into a
strict-pointer evaluator.

- [ ] **Step 2: Run the focused assertions to verify they fail as aliases**

Run: `python -m pytest tests/unit/test_core_currentness.py tests/unit/test_structural_evidence_models.py tests/unit/test_m12_candidate_foundation.py -q`

Expected: FAIL at `is Currentness` while the two package-local enum classes still exist.

- [ ] **Step 3: Replace only the duplicate declarations with aliases**

```python
# src/mechcad_harness/structural/evidence.py
from mechcad_harness.core.currentness import Currentness

# Preserve this public import path as an exact alias, not a subclass or wrapper.
StructuralEvidenceCurrentness = Currentness
```

Delete only the former three-member `StructuralEvidenceCurrentness(StrEnum)`
class body. Retain the existing `StrEnum` import because `EvidenceSubject`,
`StructuralRepeatabilityStatus`, and `StructuralMeshConvergenceStatus` still
use it.

```python
# src/mechcad_harness/candidates/services.py
from mechcad_harness.core.currentness import Currentness

# Preserve this public import path as an exact alias, not a subclass or wrapper.
CandidateCurrentness = Currentness
```

Delete the `StrEnum` import from `candidates/services.py` only after confirming
it has no remaining use. Do not modify `CandidateCurrentnessService`, including
its exact-source-revision validation and later consumed-authority hash loop. Do
not modify `StructuralEvidenceVerifier.currentness` or `EvidenceFreshness`.

- [ ] **Step 4: Run the alias and semantic-preservation tests**

Run: `python -m pytest tests/unit/test_core_currentness.py tests/unit/test_structural_evidence_models.py tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_revolute_drive_service.py -q`

Expected: PASS. In particular, the candidate foundation test must still prove
that an unrelated newer revision is current and a consumed-authority change is
stale.

### Task 3: Guard the Three Distinct Currentness/Freshness Semantics

**Files:**
- Modify: `tests/unit/test_dependency.py:175-200`
- Modify: `tests/unit/test_structural_evidence_verifier.py:1364-1377`
- Test: `tests/unit/test_runs.py`
- Test: `tests/unit/test_agent_authoritative_context.py`

**Interfaces:**
- Consumes: unchanged `EvidenceStore.get_evidence_freshness`, `StructuralEvidenceVerifier.currentness`, and `CandidateCurrentnessService`.
- Produces: regressions proving M3 graph freshness is not replaced by strict pointer currentness, and F11 node separation remains visible to readiness/freshness.

- [ ] **Step 1: Add the graph-current versus strict-pointer-stale regression**

Add this test beside `test_end_to_end_unrelated_then_material_change_and_replacement` in `tests/unit/test_dependency.py`:

```python
def test_graph_freshness_can_remain_current_after_unrelated_revision(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", make_state())
    graph = DependencyGraph.from_yaml(
        dependency_file(
            tmp_path,
            rules=[
                {"when": ["/materials/*"], "invalidates": ["analysis.materials"]},
                {"when": ["/components/*/description"], "invalidates": ["analysis.packaging"]},
            ],
        )
    )
    store = EvidenceStore(tmp_path, manager, graph)
    evidence = make_evidence(manager, "PRJ-1", node="analysis.materials")
    store.write_evidence("PRJ-1", evidence)

    manager.create_revision("PRJ-1", make_state())
    store.record_invalidation(
        store.build_invalidation("PRJ-1", 2, 1, ("/components/C-1/description",), "CS-2")
    )

    assert store.get_evidence_freshness("PRJ-1", evidence.id) is EvidenceFreshness.CURRENT
    assert manager.load_current_pointer("PRJ-1")["revision"] != evidence.revision
```

The test intentionally proves M3's node-aware condition only. It must not
assert a structural status for this generic Evidence record.

- [ ] **Step 2: Add the structural strict-pointer preservation test**

Add a self-contained test near the existing currentness tests in
`tests/unit/test_structural_evidence_verifier.py`. Reuse `_persisted_evidence()`
for a real typed Evidence record, but provide a small pointer-only state-manager
stub so the test controls only the current-pointer boundary and does not alter
the durable fixture's historical source setup.

```python
def test_structural_currentness_is_strict_current_pointer_equality(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    evidence_store = EvidenceStore(persisted.workspace, persisted.state_manager, persisted.graph)
    binding = persisted.request.source_binding

    class PointerStateManager:
        pointer = {
            "project_id": persisted.project_id,
            "revision": binding.source_revision,
            "state_hash": binding.source_state_hash,
        }

        def load_current_pointer(self, project_id):
            assert project_id == persisted.project_id
            return dict(self.pointer)

    pointer_manager = PointerStateManager()
    verifier = StructuralEvidenceVerifier(
        workspace=persisted.workspace,
        project_id=persisted.project_id,
        state_manager=pointer_manager,
        artifact_store=ArtifactStore(persisted.workspace, project_id=persisted.project_id, run_id="RUN-1"),
        evidence_store=evidence_store,
    )

    assert verifier.currentness(persisted.evidence_id) is StructuralEvidenceCurrentness.CURRENT
    pointer_manager.pointer = {
        "project_id": persisted.project_id,
        "revision": binding.source_revision + 1,
        "state_hash": "sha256:" + "f" * 64,
    }
    assert verifier.currentness(persisted.evidence_id) is (
        StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE
    )
```

Retain the existing malformed/missing durable-pointer assertions for
`CURRENTNESS_UNAVAILABLE`. This new test must not add a graph lookup to the
structural verifier.

- [ ] **Step 3: Run the new semantic-boundary regressions**

Run: `python -m pytest tests/unit/test_dependency.py::test_graph_freshness_can_remain_current_after_unrelated_revision tests/unit/test_structural_evidence_verifier.py::test_structural_currentness_is_strict_current_pointer_equality -q`

Expected: the M3 test already passes against unchanged production code; the new
strict-pointer test passes after Task 2 supplies the shared enum alias. This
confirms M3 needs no semantic modification and the test is a regression guard,
not a production-behavior change.

- [ ] **Step 4: Make test-fixture-only corrections and preserve all production evaluators**

Do not change production source in this task. Keep only the new test fixture and
assertions. Confirm:

```python
# These bodies remain behaviorally unchanged.
EvidenceStore.get_evidence_freshness
StructuralEvidenceVerifier.currentness
CandidateCurrentnessService.evaluate_source_binding
```

Add no graph lookup to structural verifier and no dependency-store lookup to
candidate services.

- [ ] **Step 5: Run the semantic-boundary regression set**

Run: `python -m pytest tests/unit/test_dependency.py tests/unit/test_runs.py tests/unit/test_agent_authoritative_context.py tests/unit/test_structural_evidence_verifier.py tests/unit/test_m12_candidate_foundation.py -q`

Expected: PASS. The result proves M3 context/readiness still uses
`EvidenceFreshness`, structural currentness remains strict-pointer, candidate
currentness remains source-relevance-sensitive, and F11's section/structural
node isolation remains intact.

### Task 4: Verify Protected Compatibility and Import Boundaries

**Files:**
- Modify only if Task 1-3 test failures prove an omission: `tests/unit/test_core_currentness.py`
- Test: `tests/unit/test_section_tools.py`
- Test: `tests/unit/test_section_warping_tools.py`
- Test: `tests/unit/test_section_engineering_tools.py`

**Interfaces:**
- Consumes: final alias/re-export implementation and unchanged public API paths.
- Produces: evidence that no import cycle, F11 namespace regression, M3 vocabulary change, or protected semantic change was introduced.

- [ ] **Step 1: Add no production behavior; expand the core test only if needed for a discovered import edge**

If a cycle is exposed only through a package-level import, add that exact public
import to `test_currentness_core_is_a_dependency_leaf_and_public_modules_import`:

```python
importlib.import_module("mechcad_harness.candidates")
```

Do not add a broad import sweep. The required proof is that the newly shared
leaf and the two documented public import paths load together without a cycle.

- [ ] **Step 2: Run focused protected-surface gates**

Run: `python -m pytest tests/unit/test_core_currentness.py tests/unit/test_dependency.py tests/unit/test_runs.py tests/unit/test_agent_authoritative_context.py tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_revolute_drive_service.py -q`

Expected: PASS with any existing optional dependency skips reported separately.

- [ ] **Step 3: Run static and scope checks**

Run: `python -m compileall -q src/mechcad_harness tests`

Expected: exit `0`.

Run: `git diff --check`

Expected: no new whitespace errors in F3-touched files. If unrelated existing
worktree errors are reported, record their paths separately and do not alter
them.

Run: `git status --short`

Expected: the F3 file set is limited to the neutral enum, direct aliases,
focused regressions, and authorized audit/map updates; preserve all pre-existing
unrelated worktree paths.

### Task 5: Record the Accepted Current-Tree Result

**Files:**
- Modify: `docs/audit/MECHCAD_LOGIC_DUPLICATION_AUDIT.md` (append only)
- Modify: `docs/audit/MECHCAD_CAPABILITY_OWNERSHIP_MAP.md:35-39,95-99,124-135`

**Interfaces:**
- Consumes: exact verification output from Task 4 and the approved F3 design.
- Produces: an append-only F3 remediation record plus an ownership map that distinguishes M3 graph freshness, structural strict pointer currentness, and candidate source-relevance currentness.

- [ ] **Step 1: Append, do not rewrite, the F3 remediation record**

Append `## 23. F3 Remediation Record (post-acceptance)` to
`MECHCAD_LOGIC_DUPLICATION_AUDIT.md`. Include these exact semantic statements:

```markdown
The historical F3 finding above remains unchanged as the pre-remediation audit
record. The current-tree correction is that the duplicated implementation was
the three-value structural/candidate status vocabulary, not an equivalent
pointer evaluator: structural currentness requires exact current-pointer tuple
equality, while candidate currentness may remain current across a newer revision
when every explicit consumed-authority path remains equal.

`core/currentness.py::Currentness` is the standard-library-only neutral status
authority. `StructuralEvidenceCurrentness` and `CandidateCurrentness` are direct
re-export aliases of that one enum. `EvidenceFreshness` remains the independent
M3 graph/history vocabulary and no evaluator's semantics changed.
```

Also record F11's retained `analysis.section` / `analysis.structural` separation,
the exact Task 4 command/result, `compileall` result, `git diff --check` result
including unrelated pre-existing errors if present, and the implementation
commit only if one is separately authorized and actually created. Do not state a
passing result before it exists.

- [ ] **Step 2: Update the ownership map to describe current authorities**

Update row 7 to say M3 freshness is a single graph/history authority and list
structural pointer currentness and candidate source-relevance currentness as
separate layered concepts, not alternate M3 implementations. Update row 45 to
state that structural currentness is a single evaluator using the shared
`core/currentness.py::Currentness` vocabulary; mention candidate currentness as
a distinct source-relevance evaluator, not duplicate logic.

Use statuses that reflect the accepted result:

```markdown
| 7 | Evidence freshness | ... | `dependency/graph.py:impact`, `dependency/storage.py:get_evidence_freshness` (WIRED) | structural strict-pointer currentness and candidate source-relevance currentness are distinct layered contracts | F3 | LEGITIMATE_LAYERING |
| 45 | Structural Evidence currentness | ... | `structural/evidence_service.py:currentness` plus `core/currentness.py:Currentness` (WIRED) | candidate source-relevance evaluator shares status vocabulary only | F3 | SINGLE_AUTHORITY |
```

Recalculate the table counts from all 60 rows after changing those two primary
statuses. With no concurrent map changes, the expected transition is
`SINGLE_AUTHORITY 28 -> 29`, `LEGITIMATE_LAYERING 6 -> 7`,
`SEMANTIC_DUPLICATION 4 -> 3`, and `POSSIBLE_DUPLICATION 7 -> 6`; verify actual
rows instead of copying these values blindly.

- [ ] **Step 3: Validate documentation truthfulness and scope**

Run: `git diff --check -- docs/audit/MECHCAD_LOGIC_DUPLICATION_AUDIT.md docs/audit/MECHCAD_CAPABILITY_OWNERSHIP_MAP.md`

Expected: no whitespace errors.

Run: `git diff -- docs/audit/MECHCAD_LOGIC_DUPLICATION_AUDIT.md docs/audit/MECHCAD_CAPABILITY_OWNERSHIP_MAP.md`

Expected: one appended F3 current-tree remediation record and only the two F3
ownership rows plus their recalculated summary counts; no historical F3 finding
or reconstruction content is edited.

- [ ] **Step 4: Final verification record**

Run: `python -m pytest tests/unit/test_core_currentness.py tests/unit/test_dependency.py tests/unit/test_runs.py tests/unit/test_agent_authoritative_context.py tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_revolute_drive_service.py -q`

Expected: PASS. Record the exact command and observed result in the appended F3
remediation record. If it fails, stop before declaring F3 accepted and record
the failure truthfully; do not broaden scope to repair unrelated findings.

## Final Acceptance Checklist

- [ ] Exactly one `Currentness` enum class exists in `src/mechcad_harness/**`.
- [ ] `StructuralEvidenceCurrentness is Currentness` and `CandidateCurrentness is Currentness`.
- [ ] All three structural/candidate serialized strings are byte-for-byte unchanged.
- [ ] `EvidenceFreshness` remains a separate M3 enum and all three evaluator bodies retain their existing semantics.
- [ ] M3 graph freshness remains required for run completion and agent context.
- [ ] Candidate currentness still accepts unrelated newer revisions and rejects changed consumed authority.
- [ ] Structural currentness remains stale after any durable current-pointer tuple change.
- [ ] F11 section and structural node identities remain independent.
- [ ] No import cycle is introduced; `core/currentness.py` has no `mechcad_harness` imports.
- [ ] The audit append and ownership map describe current code truth without rewriting historical F3 evidence.
