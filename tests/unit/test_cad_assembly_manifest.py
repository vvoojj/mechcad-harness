import pytest

from mechcad_harness.artifacts import ArtifactType
from mechcad_harness.artifacts.models import EngineeringArtifact
from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash, instance_object_name
from mechcad_harness.cad_manifest import build_program_manifest
from mechcad_harness.cad_program import acceptance_program, cad_program_hash
from mechcad_harness.cad_assembly_manifest import build_assembly_manifest
from mechcad_harness.imported_component import ImportedCadComponent


def _imported(component_id="body"):
    return ImportedCadComponent(
        component_id=component_id,
        artifact_id=f"ART-{component_id}",
        artifact_hash="sha256:" + "a" * 64,
        format="step",
        source_revision=1,
        source_state_hash="sha256:" + "b" * 64,
    )


def _artifact(component_id="body"):
    return EngineeringArtifact(
        artifact_id=f"ART-{component_id}",
        project_id="project",
        run_id="run",
        artifact_type=ArtifactType.STEP,
        media_type="model/step",
        relative_path=f"projects/project/runs/run/artifacts/ART-{component_id}/{component_id}.step",
        sha256="sha256:" + "a" * 64,
        size_bytes=1,
        producer_tool_name="fixture",
        producer_tool_version="1.0",
        bound_revision=1,
        bound_state_hash="sha256:" + "b" * 64,
    )


def test_assembly_manifest_semantic_records_are_canonical():
    program = CadAssemblyProgram(assembly_id="asm", parts=(acceptance_program(),), instances=(CadComponentInstance(instance_id="bracket_B", part_id="M7A2ABracket", placement=CadRigidTransform(x_mm=160)), CadComponentInstance(instance_id="bracket_A", part_id="M7A2ABracket")))
    assert assembly_hash(program) == assembly_hash(program.model_copy(update={"instances": tuple(reversed(program.instances))}))
    assert instance_object_name("bracket_A") != instance_object_name("bracket_B")
    assert cad_program_hash(program.parts[0]) == build_program_manifest(program.parts[0]).program_hash


def test_imported_only_assembly_manifest_is_trusted_and_valid():
    imported = _imported()
    program = CadAssemblyProgram(
        assembly_id="imported-only",
        imported_components=(imported,),
        instances=(CadComponentInstance(instance_id="body-instance", part_id="body"),),
    )

    manifest = build_assembly_manifest(program, {"body": _artifact()}, 1, "sha256:" + "b" * 64)

    assert manifest.parts == ()
    assert len(manifest.imported_components) == 1
    record = manifest.imported_components[0]
    assert record.component_id == "body"
    assert record.imported_component_hash.startswith("sha256:")
    assert record.artifact_id == "ART-body"
    assert record.artifact_sha256 == "sha256:" + "a" * 64
    assert record.source_revision == 1
    assert record.source_state_hash == "sha256:" + "b" * 64


def test_assembly_manifest_rejects_no_instances():
    with pytest.raises(ValueError, match="instances"):
        CadAssemblyProgram(
            assembly_id="no-instances",
            imported_components=(_imported(),),
            instances=(),
        )
