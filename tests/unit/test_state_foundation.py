import json

import pytest

from mechcad_harness.models import Component, DesignState, Evidence
from mechcad_harness.state import (
    StateIntegrityError,
    StateManager,
    canonical_json,
    state_hash,
)


def make_state(name: str = "Bracket") -> DesignState:
    return DesignState(
        id="REV-state",
        revision=1,
        components=[Component(id="PRT-bracket", name=name)],
    )


def test_equivalent_states_have_same_canonical_hash():
    first = make_state()
    second = DesignState.model_validate(json.loads(first.model_dump_json()))
    assert canonical_json(first) == canonical_json(second)
    assert state_hash(first) == state_hash(second)


def test_hash_ignores_mapping_order_but_changes_with_state():
    first = make_state()
    reordered = DesignState.model_validate(
        {
            "load_cases": [],
            "constraints": [],
            "interfaces": [],
            "materials": [],
            "assemblies": [],
            "components": [{"created_at": first.components[0].created_at, "name": "Bracket", "id": "PRT-bracket"}],
            "requirements": [],
            "created_at": first.created_at,
            "revision": 1,
            "id": "REV-state",
        }
    )
    assert state_hash(first) == state_hash(reordered)
    assert state_hash(first) != state_hash(make_state("Changed"))


def test_project_revisions_are_immutable_and_current_points_to_latest(tmp_path):
    manager = StateManager(tmp_path)
    project_id = "PRJ-test"
    first = manager.create_project(project_id, make_state())
    first_path = tmp_path / "projects" / project_id / "revisions" / "REV-000001.json"
    first_bytes = first_path.read_bytes()

    second = manager.create_revision(project_id, make_state("Updated"))

    assert first.revision == 1
    assert second.revision == 2
    assert first_path.read_bytes() == first_bytes
    assert manager.load_current_state(project_id).components[0].name == "Updated"
    assert manager.load_revision(project_id, 1).components[0].name == "Bracket"


def test_existing_revision_cannot_be_overwritten(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-test", make_state())
    with pytest.raises(Exception):
        manager.create_revision("PRJ-test", make_state(), revision=1)


def test_tampered_snapshot_is_detected(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-test", make_state())
    path = tmp_path / "projects" / "PRJ-test" / "revisions" / "REV-000001.json"
    payload = json.loads(path.read_text())
    payload["state"]["components"][0]["name"] = "Tampered"
    path.write_text(json.dumps(payload))
    with pytest.raises(StateIntegrityError):
        manager.verify_revision("PRJ-test", 1)


def test_current_pointer_is_unchanged_when_snapshot_persistence_fails(tmp_path, monkeypatch):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-test", make_state())
    current_path = tmp_path / "projects" / "PRJ-test" / "current.json"
    current_bytes = current_path.read_bytes()

    def fail_write(*args, **kwargs):
        raise OSError("persistence failed")

    monkeypatch.setattr(manager, "_write_snapshot", fail_write)
    with pytest.raises(OSError):
        manager.create_revision("PRJ-test", make_state("Updated"))
    assert current_path.read_bytes() == current_bytes


def test_evidence_is_not_part_of_design_state():
    state = make_state()
    Evidence(id="EVD-test", kind="note", summary="separate", revision=1, state_hash="sha256:test")
    assert "evidence" not in DesignState.model_fields
