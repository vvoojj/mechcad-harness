from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash, instance_object_name
from mechcad_harness.cad_manifest import build_program_manifest
from mechcad_harness.cad_program import acceptance_program, cad_program_hash


def test_assembly_manifest_semantic_records_are_canonical():
    program = CadAssemblyProgram(assembly_id="asm", parts=(acceptance_program(),), instances=(CadComponentInstance(instance_id="bracket_B", part_id="M7A2ABracket", placement=CadRigidTransform(x_mm=160)), CadComponentInstance(instance_id="bracket_A", part_id="M7A2ABracket")))
    assert assembly_hash(program) == assembly_hash(program.model_copy(update={"instances": tuple(reversed(program.instances))}))
    assert instance_object_name("bracket_A") != instance_object_name("bracket_B")
    assert cad_program_hash(program.parts[0]) == build_program_manifest(program.parts[0]).program_hash
