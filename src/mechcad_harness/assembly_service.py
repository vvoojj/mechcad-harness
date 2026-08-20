from __future__ import annotations

from mechcad_harness.cad_assembly import CadAssemblyProgram
from mechcad_harness.cad_service import CadGenerationService
from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend


class CadAssemblyGenerationService(CadGenerationService):
    def generate_assembly(self, project_id: str, run_id: str, revision: int, state_hash: str, program: CadAssemblyProgram, workspace):
        binding = self.validate_source(project_id, revision, state_hash)
        return self.backend.generate_assembly(program, workspace, project_id=binding.project_id, run_id=run_id, revision=binding.revision, state_hash=binding.state_hash)


def default_assembly_service(state_manager):
    return CadAssemblyGenerationService(state_manager, FreeCADAssemblyBackend())
