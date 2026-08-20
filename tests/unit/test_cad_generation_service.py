from pathlib import Path

import pytest

from mechcad_harness.cad_program import acceptance_program
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.backends.freecad import FreeCADBackend
from mechcad_harness.cad_service import CadGenerationService, CadSourceBindingError, CadSourceRevisionNotFoundError, CadSourceHashMismatchError


class SpyBackend(FreeCADBackend):
    def __init__(self):
        self.calls = 0

    def generate_program(self, *args, **kwargs):
        self.calls += 1
        return "generated"


def setup_state(tmp_path):
    state_manager = StateManager(tmp_path)
    snapshot = state_manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1))
    return state_manager, snapshot


def test_validated_binding_reaches_backend_with_authoritative_values(tmp_path):
    state_manager, snapshot = setup_state(tmp_path)
    backend = SpyBackend()
    result = CadGenerationService(state_manager, backend).generate_program("PRJ-1", "RUN-1", snapshot.revision, snapshot.state_hash, acceptance_program(), tmp_path)
    assert result == "generated"
    assert backend.calls == 1


def test_missing_revision_fails_before_runner(tmp_path):
    state_manager, snapshot = setup_state(tmp_path)
    backend = SpyBackend()
    with pytest.raises(CadSourceRevisionNotFoundError):
        CadGenerationService(state_manager, backend).generate_program("PRJ-1", "RUN-1", 2, snapshot.state_hash, acceptance_program(), tmp_path)
    assert backend.calls == 0


def test_wrong_hash_fails_before_runner(tmp_path):
    state_manager, snapshot = setup_state(tmp_path)
    backend = SpyBackend()
    with pytest.raises(CadSourceHashMismatchError):
        CadGenerationService(state_manager, backend).generate_program("PRJ-1", "RUN-1", 1, "sha256:wrong", acceptance_program(), tmp_path)
    assert backend.calls == 0


def test_project_revision_mismatch_fails_before_runner(tmp_path):
    state_manager, snapshot = setup_state(tmp_path)
    backend = SpyBackend()
    with pytest.raises(CadSourceBindingError):
        CadGenerationService(state_manager, backend).generate_program("PRJ-2", "RUN-1", 1, snapshot.state_hash, acceptance_program(), tmp_path)
    assert backend.calls == 0
