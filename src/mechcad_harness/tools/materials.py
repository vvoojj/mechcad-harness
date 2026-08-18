from mechcad_harness.backends.bd_materials import BdMaterialsAdapter
from mechcad_harness.materials import MaterialMassInput, MaterialMassResult, TypicalMaterialPropertiesInput, TypicalMaterialPropertiesResult

from .models import ToolRegistration


def material_provenance():
    return BdMaterialsAdapter().provenance()


def get_typical_material_properties(value: TypicalMaterialPropertiesInput):
    return BdMaterialsAdapter().typical_properties(value)


def calc_mass_from_typical_material(value: MaterialMassInput):
    return BdMaterialsAdapter().mass(value)


class MaterialTools:
    @staticmethod
    def registrations():
        return [
            ToolRegistration(name="mechcad-material-typical-properties", version="1.0", input_model=TypicalMaterialPropertiesInput, output_model=TypicalMaterialPropertiesResult, handler=get_typical_material_properties, provenance_handler=material_provenance, evidence_nodes=("material.typical",)),
            ToolRegistration(name="mechcad-calc-mass-from-typical-material", version="1.0", input_model=MaterialMassInput, output_model=MaterialMassResult, handler=calc_mass_from_typical_material, provenance_handler=material_provenance, evidence_nodes=("material.typical",)),
        ]
