from __future__ import annotations

from pydantic import Field

from mechcad_harness.cad_program import CadPartProgram
from mechcad_harness.models.common import Model


class CadSourceBindingError(Exception):
    pass


class CadSourceRevisionNotFoundError(CadSourceBindingError):
    pass


class CadSourceHashMismatchError(CadSourceBindingError):
    pass


class ValidatedCadSourceBinding(Model):
    project_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    state_hash: str = Field(min_length=1)


class CadGenerationService:
    def __init__(self, state_manager, backend):
        self.state_manager = state_manager
        self.backend = backend

    def validate_source(self, project_id: str, revision: int, state_hash: str) -> ValidatedCadSourceBinding:
        try:
            state = self.state_manager.load_revision(project_id, revision)
        except Exception as exc:
            raise CadSourceRevisionNotFoundError(f"source revision not found: {project_id}:{revision}") from exc
        from mechcad_harness.state import state_hash as canonical_state_hash
        actual_hash = canonical_state_hash(state)
        if actual_hash != state_hash:
            raise CadSourceHashMismatchError(f"source state hash mismatch: {project_id}:{revision}")
        return ValidatedCadSourceBinding(project_id=project_id, revision=state.revision, state_hash=actual_hash)

    def generate_program(self, project_id: str, run_id: str, revision: int, state_hash: str, program: CadPartProgram, workspace):
        binding = self.validate_source(project_id, revision, state_hash)
        return self.backend.generate_program(program, workspace, project_id=binding.project_id, run_id=run_id, revision=binding.revision, state_hash=binding.state_hash)
