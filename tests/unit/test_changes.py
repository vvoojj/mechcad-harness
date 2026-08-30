import json
import threading

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


def test_physical_mechanism_owner_is_limited_to_mechanism_collection_items():
    policy = OwnershipPolicy.from_file("config/ownership.yaml")
    policy.check("/physical_mechanisms/PM-1", "mechcad-physical-mechanism")

    for path in (
        "/requirements/REQ-1",
        "/components/PRT-1/name",
        "/structural_analysis_definitions/DEF-1",
        "/",
    ):
        with pytest.raises(OwnershipViolationError):
            policy.check(path, "mechcad-physical-mechanism")


def test_result_is_pydantic_revalidated(tmp_path):
    manager, engine = make_engine(tmp_path)
    invalid = ChangeOperation(operation="replace", path="/components/PRT-1/name", value="")
    with pytest.raises(Exception):
        engine.apply_proposal("PRJ-1", proposal(manager, "PRJ-1", [invalid]))


def test_constraint_request_is_not_an_operation():
    assert not hasattr(ChangeOperation, "description")


def test_apply_revalidates_after_promotion_before_competing_writer_can_commit(tmp_path, monkeypatch):
    manager, engine = make_engine(tmp_path)
    promotion = proposal(manager, "PRJ-1", [
        ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Promotion"),
    ]).model_copy(update={"id": "PROMOTION"})
    competing = proposal(manager, "PRJ-1", [
        ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Competing"),
    ]).model_copy(update={"id": "COMPETING"})
    promotion_validated = threading.Event()
    release_promotion = threading.Event()
    competing_acquired = threading.Event()
    errors = {}
    original = engine._prepare_proposal_locked

    def prepare_locked(project_id, candidate):
        if candidate.id == "COMPETING":
            competing_acquired.set()
        result = original(project_id, candidate)
        if candidate.id == "PROMOTION":
            promotion_validated.set()
            assert release_promotion.wait(timeout=5)
        return result

    monkeypatch.setattr(engine, "_prepare_proposal_locked", prepare_locked)

    def apply(name, candidate):
        try:
            engine.apply_proposal("PRJ-1", candidate)
        except BaseException as exc:
            errors[name] = exc

    promotion_thread = threading.Thread(target=apply, args=("promotion", promotion))
    competing_thread = threading.Thread(target=apply, args=("competing", competing))
    promotion_thread.start()
    assert promotion_validated.wait(timeout=5)
    competing_thread.start()
    release_promotion.set()
    promotion_thread.join(timeout=5)
    competing_thread.join(timeout=5)

    assert not promotion_thread.is_alive()
    assert not competing_thread.is_alive()
    assert competing_acquired.is_set()
    assert isinstance(errors["competing"], StaleProposalError)
    assert manager._read_current("PRJ-1")["revision"] == 2
    assert manager.load_current_state("PRJ-1").components[0].name == "Promotion"


def test_apply_rejects_promotion_after_competing_writer_commits_without_extra_revision(tmp_path, monkeypatch):
    manager, engine = make_engine(tmp_path)
    competing = proposal(manager, "PRJ-1", [
        ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Competing"),
    ]).model_copy(update={"id": "COMPETING"})
    promotion = proposal(manager, "PRJ-1", [
        ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Promotion"),
    ]).model_copy(update={"id": "PROMOTION"})
    competing_validated = threading.Event()
    release_competing = threading.Event()
    promotion_acquired = threading.Event()
    errors = {}
    original = engine._prepare_proposal_locked

    def prepare_locked(project_id, candidate):
        if candidate.id == "PROMOTION":
            promotion_acquired.set()
        result = original(project_id, candidate)
        if candidate.id == "COMPETING":
            competing_validated.set()
            assert release_competing.wait(timeout=5)
        return result

    monkeypatch.setattr(engine, "_prepare_proposal_locked", prepare_locked)

    def apply(name, candidate):
        try:
            engine.apply_proposal("PRJ-1", candidate)
        except BaseException as exc:
            errors[name] = exc

    competing_thread = threading.Thread(target=apply, args=("competing", competing))
    promotion_thread = threading.Thread(target=apply, args=("promotion", promotion))
    competing_thread.start()
    assert competing_validated.wait(timeout=5)
    promotion_thread.start()
    release_competing.set()
    competing_thread.join(timeout=5)
    promotion_thread.join(timeout=5)

    assert not competing_thread.is_alive()
    assert not promotion_thread.is_alive()
    assert promotion_acquired.is_set()
    assert "competing" not in errors
    assert isinstance(errors["promotion"], StaleProposalError)
    assert manager._read_current("PRJ-1")["revision"] == 2
    assert manager.load_current_state("PRJ-1").components[0].name == "Competing"


def test_apply_proposal_is_safe_under_nested_project_lock(tmp_path):
    manager, engine = make_engine(tmp_path)
    candidate = proposal(manager, "PRJ-1", [
        ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Nested"),
    ])

    with manager.project_lock("PRJ-1"):
        result = engine.apply_proposal("PRJ-1", candidate)

    assert result.snapshot.revision == 2
    assert manager.load_current_state("PRJ-1").components[0].name == "Nested"
