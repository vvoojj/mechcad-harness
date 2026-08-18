from mechcad_harness.backends.gearworks_tools import calc_spur_gear_geometry_gearworks, calc_spur_gear_pair_gearworks, gearworks_provenance
from mechcad_harness.gear import SpurGearGeometryInput, SpurGearGeometryResult, SpurGearPairInput, SpurGearPairResult

from .models import ToolRegistration
from mechcad_harness.backends.gearworks_cad import build_spur_gear_cad, build_spur_gear_pair_cad
from mechcad_harness.cad import SpurGearCadInput, SpurGearCadResult, SpurGearPairCadInput, SpurGearPairCadResult


class GearworksTools:
    @staticmethod
    def registrations() -> list[ToolRegistration]:
        return [
            ToolRegistration(name="mechcad-calc-spur-gear-geometry-gearworks", version="1.0", input_model=SpurGearGeometryInput, output_model=SpurGearGeometryResult, handler=calc_spur_gear_geometry_gearworks, provenance_handler=gearworks_provenance, evidence_nodes=("analysis.transmission",)),
            ToolRegistration(name="mechcad-calc-spur-gear-pair-gearworks", version="1.0", input_model=SpurGearPairInput, output_model=SpurGearPairResult, handler=calc_spur_gear_pair_gearworks, provenance_handler=gearworks_provenance, evidence_nodes=("analysis.transmission",)),
            ToolRegistration(name="mechcad-build-spur-gear-cad", version="1.0", input_model=SpurGearCadInput, output_model=SpurGearCadResult, handler=build_spur_gear_cad, provenance_handler=gearworks_provenance, evidence_nodes=("artifact.gear",)),
            ToolRegistration(name="mechcad-build-spur-gear-pair-cad", version="1.0", input_model=SpurGearPairCadInput, output_model=SpurGearPairCadResult, handler=build_spur_gear_pair_cad, provenance_handler=gearworks_provenance, evidence_nodes=("artifact.gear",)),
        ]
