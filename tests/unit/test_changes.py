import json

import pytest

from mechcad_harness.changes import (
    ChangeEngine,
    ChangeOperation,
    InvalidChangePathError,
    OperationType,
    OwnershipPolicy,
    OwnershipViolationError,
    StaleProposalError,
)
from mechcad_harness.models import ChangeProposal, Component, DesignState, ProposalStatus
from mechcad_harness.state import StateManager


def state(name="Bracket"):
    return DesignState(id="REV-state", revision=1, components=[Component(id="PRT-1", name=name)])


def proposal(manager, project_id, operations, actor="mechcad-packaging"):
    current = manager._read_current(project_id)
    return ChangeProposal(
        id="CP-1", title="change", status=ProposalStatus.DRAFT,
        base_revision=current["revision"], base_state_hash=current["state_hash"],
        actor=actor, operations=operations,
    )


def make_engine(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", state())
    policy = OwnershipPolicy([{"path": "/components/*", "owner": "mechcad-packaging"}])
    return manager, ChangeEngine(manager, policy)


def test_replace_add_and_remove_create_revisions(tmp_path):
    manager, engine = make_engine(tmp_path)
    engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")]))
    assert manager.load_current_state("PRJ-1").components[0].name == "Plate"
    engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [ChangeOperation(operation="add", path="/components/PRT-2", value={"id": "PRT-2", "name": "Pin"})]))
    assert len(manager.load_current_state("PRJ-1").components) == 2
    engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [ChangeOperation(operation="remove", path="/components/PRT-2")]))
    assert len(manager.load_current_state("PRJ-1").components) == 1


def test_previous_snapshot_is_unchanged_and_multiple_operations_are_atomic(tmp_path):
    manager, engine = make_engine(tmp_path)
    path = tmp_path / "projects" / "PRJ-1" / "revisions" / "REV-000001.json"
    before = path.read_bytes()
    engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [
        ChangeOperation(operation="replace", path="/components/PRT-1/name", value="A"),
        ChangeOperation(operation="replace", path="/components/PRT-1/description", value="B"),
    ]))
    assert path.read_bytes() == before
    assert manager.load_current_state("PRJ-1").components[0].description == "B"


def test_failed_operation_does_not_create_revision_or_move_pointer(tmp_path):
    manager, engine = make_engine(tmp_path)
    pointer = tmp_path / "projects" / "PRJ-1" / "current.json"
    before_pointer = pointer.read_bytes()
    before_revisions = sorted((pointer.parent / "revisions").iterdir())
    with pytest.raises(InvalidChangePathError):
        engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [
            ChangeOperation(operation="replace", path="/components/PRT-1/name", value="A"),
            ChangeOperation(operation="remove", path="/components/MISSING"),
        ]))
    assert pointer.read_bytes() == before_pointer
    assert sorted((pointer.parent / "revisions").iterdir()) == before_revisions


def test_stale_revision_and_hash_are_rejected(tmp_path):
    manager, engine = make_engine(tmp_path)
    current = manager._read_current("PRJ-1")
    stale = ChangeProposal(id="CP-1", title="stale", status=ProposalStatus.DRAFT, base_revision=2, base_state_hash=current["state_hash"], actor="mechcad-packaging", operations=[])
    with pytest.raises(StaleProposalError):
        engine.apply_proposal("PRJ-1", stale)
    stale = stale.model_copy(update={"base_revision": 1, "base_state_hash": "sha256:wrong"})
    with pytest.raises(StaleProposalError):
        engine.apply_proposal("PRJ-1", stale)


def test_missing_replace_and_remove_paths_fail(tmp_path):
    manager, engine = make_engine(tmp_path)
    for operation in [
        ChangeOperation(operation="replace", path="/components/PRT-1/missing", value="x"),
        ChangeOperation(operation="remove", path="/components/MISSING"),
    ]:
        with pytest.raises(InvalidChangePathError):
            engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [operation]))


def test_unowned_and_wrong_owner_paths_fail(tmp_path):
    manager, engine = make_engine(tmp_path)
    operation = ChangeOperation(operation="replace", path="/components/PRT-1/name", value="x")
    with pytest.raises(OwnershipViolationError):
        engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [operation], actor="other"))
    unowned = ChangeOperation(operation="replace", path="/load_cases", value=[])
    with pytest.raises(OwnershipViolationError):
        engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [unowned]))


def test_structural_owner_can_add_definition_but_other_owner_cannot(tmp_path):
    policy = OwnershipPolicy.from_file("config/ownership.yaml")
    policy.check("/structural_analysis_definitions/DEF-1", "mechcad-structural")
    with pytest.raises(OwnershipViolationError):
        policy.check("/structural_analysis_definitions/DEF-1", "mechcad-materials")


def test_result_is_pydantic_revalidated(tmp_path):
    manager, engine = make_engine(tmp_path)
    invalid = ChangeOperation(operation="replace", path="/components/PRT-1/name", value="")
    with pytest.raises(Exception):
        engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [invalid]))


def test_constraint_request_is_not_an_operation():
    assert not hasattr(ChangeOperation, "description")
