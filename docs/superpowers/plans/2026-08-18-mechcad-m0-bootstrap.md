# MechCAD M0 Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal Python/Pydantic foundation for the MechCAD Harness M0 milestone.

**Architecture:** Use a `src`-layout package with centralized readable IDs, shared Pydantic model primitives, and focused domain model modules. Keep `DesignState` canonical and keep proposals, results, validation, and evidence as separate bindable records. Add only placeholder YAML configuration and tests; no execution integrations.

**Tech Stack:** Python 3.11+, Pydantic 2, pytest, setuptools package metadata, YAML configuration files without a YAML runtime dependency.

## Global Constraints

- Work only inside the current repository.
- Do not implement agents, OpenCode integration, CAD, FreeCAD, FEA, scheduling, dependency execution, or LLM workflows.
- Do not add FreeCAD, MuJoCo, CAD, FEA, MCP, SQL, or external services.
- Use Pydantic v2 and UTC-aware datetimes.
- Keep models minimal, strongly typed, and reject obviously invalid values.
- Do not create a nested `mechcad-harness` directory.
- No Git commit unless explicitly requested.

---

### Task 1: Package Scaffold and IDs

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/mechcad_harness/__init__.py`
- Create: `src/mechcad_harness/ids.py`
- Create: package `__init__.py` files under `src/mechcad_harness/{models,core,state,dependency,agents,tools,validation,storage,adapters}`
- Create: `workspace/.gitkeep`
- Test: `tests/unit/test_ids.py`

**Interfaces:**
- Produce `IdPrefix`, `generate_id(prefix: IdPrefix) -> str`, and `id_prefix(value: str) -> str`.
- `generate_id` returns `<PREFIX>-<uuid4>`, and rejects unknown prefixes.

- [ ] **Step 1: Write the failing ID tests**

```python
from mechcad_harness.ids import IdPrefix, generate_id, id_prefix


def test_ids_have_requested_prefixes_and_unique_values():
    first = generate_id(IdPrefix.PROJECT)
    second = generate_id(IdPrefix.PROJECT)
    assert first.startswith("PRJ-")
    assert id_prefix(first) == "PRJ"
    assert first != second


def test_all_required_prefixes_are_supported():
    assert {generate_id(prefix).split("-", 1)[0] for prefix in IdPrefix} == {
        "PRJ", "REV", "RUN", "TASK", "CP", "CS", "ISSUE", "EVD", "VAL",
        "DEC", "REQ", "PRT", "ASM", "MAT", "JNT", "LC",
    }
```

- [ ] **Step 2: Run `pytest tests/unit/test_ids.py -v` and verify it fails because the package does not exist.**
- [ ] **Step 3: Implement the enum and UUID4 generator in `ids.py`, configure the package in `pyproject.toml`, and create empty namespace package initializers.**
- [ ] **Step 4: Run `pytest tests/unit/test_ids.py -v` and verify both tests pass.**

### Task 2: Shared and Domain Models

**Files:**
- Create: `src/mechcad_harness/models/common.py`
- Create: `src/mechcad_harness/models/design.py`
- Create: `src/mechcad_harness/models/component.py`
- Create: `src/mechcad_harness/models/material.py`
- Create: `src/mechcad_harness/models/requirement.py`
- Create: `src/mechcad_harness/models/constraint.py`
- Create: `src/mechcad_harness/models/task.py`
- Create: `src/mechcad_harness/models/proposal.py`
- Create: `src/mechcad_harness/models/issue.py`
- Create: `src/mechcad_harness/models/validation.py`
- Create: `src/mechcad_harness/models/evidence.py`
- Create: `src/mechcad_harness/models/run.py`
- Modify: `src/mechcad_harness/models/__init__.py`
- Test: `tests/unit/test_models.py`

**Interfaces:**
- Provide the required models: `DesignState`, `Requirement`, `Component`, `Assembly`, `MaterialProfile`, `Interface`, `Constraint`, `LoadCase`, `AgentTask`, `AgentResult`, `ChangeOperation`, `ChangeProposal`, `ChangeSet`, `ConstraintRequest`, `Issue`, `ValidationResult`, `Evidence`, and `RunManifest`.
- Shared `StateBinding` contains `revision: int` and `state_hash: str`.
- Use enums for task, proposal, issue, and validation statuses.

- [ ] **Step 1: Write failing construction, validation, binding, and separation tests.**

```python
import pytest
from pydantic import ValidationError
from mechcad_harness.models import (
    Component, DesignState, Evidence, ChangeProposal, ProposalStatus,
)


def test_basic_models_construct():
    component = Component(id="PRT-part", name="Bracket")
    state = DesignState(id="REV-revision", revision=1, components=[component])
    assert state.components[0].name == "Bracket"


def test_invalid_values_are_rejected():
    with pytest.raises(ValidationError):
        Component(id="PRT-part", name="")
    with pytest.raises(ValidationError):
        DesignState(id="REV-revision", revision=0)


def test_proposal_and_evidence_bind_to_revision_and_hash():
    proposal = ChangeProposal(
        id="CP-proposal", title="Add bracket", status=ProposalStatus.DRAFT,
        revision=3, state_hash="sha256:abc",
    )
    evidence = Evidence(id="EVD-proof", kind="calculation", summary="Checked", revision=3, state_hash="sha256:abc")
    assert proposal.revision == evidence.revision == 3
    assert proposal.state_hash == evidence.state_hash


def test_design_state_does_not_contain_evidence_or_results():
    assert "evidence" not in DesignState.model_fields
    assert "results" not in DesignState.model_fields
```

- [ ] **Step 2: Run `pytest tests/unit/test_models.py -v` and verify failure from missing model modules.**
- [ ] **Step 3: Implement small Pydantic models with positive revisions, non-empty strings, UTC-aware `created_at`, typed lists, and state binding.**
- [ ] **Step 4: Re-export all public models and enums from `models/__init__.py`.**
- [ ] **Step 5: Run `pytest tests/unit/test_models.py -v` and verify all tests pass.**

### Task 3: Configuration and Documentation

**Files:**
- Create: `config/harness.yaml`
- Create: `config/agents.yaml`
- Create: `config/tools.yaml`
- Create: `config/ownership.yaml`
- Create: `config/dependencies.yaml`
- Create: `config/validations.yaml`
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `.opencode/README.md`
- Create: `tests/integration/.gitkeep`

**Interfaces:**
- Each YAML file has `schema: mechcad-harness` and `version: 1` plus safe empty/default collections.
- Documentation explicitly states M0 boundaries and canonical-state/proposal ownership.

- [ ] **Step 1: Add configuration files with only schema/version markers and empty collections.**
- [ ] **Step 2: Add README, AGENTS, and `.opencode/README.md` covering the requested project rules and future adapter boundary.**
- [ ] **Step 3: Inspect documentation for later-milestone functionality accidentally implied by placeholder files.**

### Task 4: Full Verification

**Files:**
- Verify: all created files

- [ ] **Step 1: Run `pytest -q`.**
- [ ] **Step 2: Run `python -m compileall src tests` to catch syntax errors.**
- [ ] **Step 3: Print the final tree with `Get-ChildItem -Recurse -Name` and compare it to the requested structure.**
- [ ] **Step 4: Report exact test results, deliberate deviations, and the marker `MECHCAD_M0_BOOTSTRAP_COMPLETE`.**
