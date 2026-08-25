from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
os.environ.setdefault("MECHCAD_FREECAD_BIN_DIR", r"C:\Program Files\FreeCAD 1.1\bin")
os.environ.setdefault("MECHCAD_GMSH", r"C:\Program Files\FreeCAD 1.1\bin\gmsh.exe")

from mechcad_harness.agents.fake import FakeAgentAdapter
from mechcad_harness.agents import AgentIdentity
from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts.storage import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackend
from mechcad_harness.cad_program import CadPartProgram, BasePlateOperation
from mechcad_harness.models import DesignState
from mechcad_harness.materials import MaterialDataAuthority
from mechcad_harness.models.structural import (
    StructuralAnalysisDefinition,
    StructuralRegionDefinition,
    StructuralResultantForce,
    StructuralFixedSupport,
    StructuralLoadCase,
    StructuralMaterialAssignment,
    StructuralMaterialPropertySnapshot,
    StructuralMaterialPropertyName,
    StructuralMaterialConversionProvenance,
    StructuralPhysicalAssumptions,
    StructuralCoordinateFrame,
    AcceptanceMaterialAuthorityPolicy,
    StructuralPropertyAuthorityRule,
)
from mechcad_harness.state.manager import StateManager
from mechcad_harness.state.hashing import state_hash as hash_state
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.models.structural import structural_definition_hash
from mechcad_harness.structural_request import (
    MeshSpecification,
    StructuralAnalysisRequest,
    StructuralExecutionSettings,
    StructuralSourceBinding,
    StructuralResultField,
)
from mechcad_harness.structural.models import StructuralExecutionManifest, StructuralExecutionStatus


@pytest.fixture
def live_app(tmp_path: Path):
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n"
        "  - path: /structural_analysis_definitions/*\n"
        "    owner: mechcad-structural\n"
        "  - path: /components/*\n"
        "    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps({
            "rules": [{
                "when": ["/structural_analysis_definitions/*"],
                "invalidates": ["analysis.structural", "validation.structural"],
            }],
            "edges": [{"from": "analysis.structural", "to": "validation.structural"}],
        }),
        encoding="utf-8",
    )
    state = DesignState(id="DES-M11-3-live", revision=1)
    StateManager(tmp_path).create_project("PRJ-M11-3-live", state)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0",
                              role="transmission_engineer", protocol_version="1.0")
    return ProductionApplication.create(
        tmp_path, "PRJ-M11-3-live", FakeAgentAdapter(identity, scripted_responses=()),
        ownership_path=ownership, dependency_path=dependencies)


def _make_definition():
    e = StructuralMaterialPropertySnapshot(
        property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS, value=70000.0, normalized_unit="MPa",
        source_identity="test", authority=MaterialDataAuthority.TYPICAL_REFERENCE,
        conversion_provenance=StructuralMaterialConversionProvenance(
            source_unit="MPa", normalization_rule="as_is", conversion_version="1"))
    nu = StructuralMaterialPropertySnapshot(
        property_name=StructuralMaterialPropertyName.POISSON_RATIO, value=0.33, normalized_unit="ratio",
        source_identity="test", authority=MaterialDataAuthority.TYPICAL_REFERENCE,
        conversion_provenance=StructuralMaterialConversionProvenance(
            source_unit="ratio", normalization_rule="as_is", conversion_version="1"))
    region_fixed = StructuralRegionDefinition(
        region_id="fixed", target_body_id="BODY-1", source_primitive_id="fixed_face",
        semantic_role="fixed_support", geometry_kind="face", selector_kind="planar_face_centroid_axis",
        selector_parameters={"axis": "x", "side": "min"}, expected_cardinality=1, resolver_version="1")
    region_free = StructuralRegionDefinition(
        region_id="free", target_body_id="BODY-1", source_primitive_id="free_face",
        semantic_role="load", geometry_kind="face", selector_kind="planar_face_centroid_axis",
        selector_parameters={"axis": "x", "side": "max"}, expected_cardinality=1, resolver_version="1")
    load = StructuralResultantForce(
        load_id="LF-1", target_region_id="free", magnitude_n=200.0, direction_xyz=(-1.0, 0.0, 0.0),
        frame=StructuralCoordinateFrame.COMPONENT_LOCAL, distribution="uniform_surface_traction_equivalent")
    case = StructuralLoadCase(id="LC-1", name="load case 1", loads=(load,))
    support = StructuralFixedSupport(
        support_id="SUP-1", target_region_id="fixed", applies_to_load_case_ids=("LC-1",),
        frame=StructuralCoordinateFrame.COMPONENT_LOCAL,
        constrained_dofs=("ux", "uy", "uz"))
    return StructuralAnalysisDefinition(
        id="DEF-1", name="box cantilever", target_body_id="BODY-1",
        regions=(region_fixed, region_free),
        material_assignment=StructuralMaterialAssignment(
            assignment_id="MAT-1", target_body_id="BODY-1", material_identity="Alu7075",
            assignment_context="test", property_snapshot=(e, nu)),
        load_cases=(case,), boundary_conditions=(support,),
        acceptance_criteria=(),
        material_authority_policy=AcceptanceMaterialAuthorityPolicy(
            allowed_authorities_by_property=(
                StructuralPropertyAuthorityRule(property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS,
                                                 allowed_authorities=(MaterialDataAuthority.TYPICAL_REFERENCE,)),
                StructuralPropertyAuthorityRule(property_name=StructuralMaterialPropertyName.POISSON_RATIO,
                                                 allowed_authorities=(MaterialDataAuthority.TYPICAL_REFERENCE,)),
            )),
        physical_assumptions=StructuralPhysicalAssumptions())


def _publish_step(live_app, definition, tmp_path: Path, *, length_mm=100.0):
    sm = StateManager(tmp_path)
    current = sm._read_current("PRJ-M11-3-live")
    state = sm.load_revision("PRJ-M11-3-live", current["revision"])
    new_state = state.model_copy(update={"structural_analysis_definitions": [definition]})
    rev = sm.create_revision("PRJ-M11-3-live", new_state)
    hashed = hash_state(rev.state)
    run = live_app.run_controller.create_run(
        "PRJ-M11-3-live",
        expected_source=__import__("mechcad_harness.runs.models", fromlist=["SourceBinding"]).SourceBinding(
            project_id="PRJ-M11-3-live", revision=rev.revision, state_hash=hashed))
    freecad = FreeCADBackend()
    program = CadPartProgram(part_id="BOX", operations=(
        BasePlateOperation(operation_id="box", length_mm=length_mm, width_mm=20.0, thickness_mm=10.0),))
    result = freecad.generate_program(program, str(tmp_path), project_id="PRJ-M11-3-live",
                                       run_id=run.run_id, revision=rev.revision, state_hash=hashed)
    return rev.revision, hashed, result.step, program


def test_m11_3_live_vertical_slice(live_app, tmp_path: Path):
    definition = _make_definition()
    revision, state_hash, step_artifact, program = _publish_step(live_app, definition, tmp_path)
    binding = StructuralSourceBinding(
        project_id="PRJ-M11-3-live", source_revision=revision, source_state_hash=state_hash,
        definition_id=definition.id, definition_hash=structural_definition_hash(definition),
        target_body_id=definition.target_body_id, source_program_hash=cad_program_hash(program),
        geometry_identity=program.part_id, geometry_artifact_id=step_artifact.artifact_id,
        geometry_artifact_hash=step_artifact.sha256)
    request = StructuralAnalysisRequest(
        source_binding=binding, selected_load_case_ids=("LC-1",),
        mesh_specification=MeshSpecification(
            global_target_size_mm=5.0, quality_policy_id="q1", mesher_settings_version="1"),
        requested_result_fields=(StructuralResultField.DISPLACEMENT, StructuralResultField.VON_MISES_STRESS,
                                 StructuralResultField.REACTIONS),
        execution_settings=StructuralExecutionSettings(
            max_elements=1_000_000, max_runtime_seconds=300, max_output_bytes=50_000_000,
            retain_raw_artifacts=True))
    result = live_app.execute_structural_analysis(request=request)
    assert result.execution_status == StructuralExecutionStatus.SUCCEEDED, result.error_detail
    assert result.manifest is not None
    manifest = result.manifest
    store = ArtifactStore(tmp_path, project_id="PRJ-M11-3-live", run_id=result.run_id)
    produced = [store.existing(artifact_id) for artifact_id in result.produced_artifact_ids]
    assert all(produced), "a reported artifact could not be reloaded and byte-verified"
    assert len(produced) == 6
    assert {artifact.artifact_type for artifact in produced if artifact is not None} == {
        ArtifactType.MSH, ArtifactType.INP, ArtifactType.FRD, ArtifactType.DAT, ArtifactType.LOG, ArtifactType.JSON,
    }
    mesh_artifact = next(artifact for artifact in produced if artifact is not None and artifact.artifact_type == ArtifactType.MSH)
    assert (tmp_path / mesh_artifact.relative_path).read_bytes().startswith(b"$MeshFormat")
    for art in manifest.artifacts:
        a = store.existing(art.artifact_id)
        assert a is not None, f"missing artifact {art.artifact_id}"
        assert a.sha256 == art.sha256
        path = tmp_path / a.relative_path
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == a.sha256
    assert manifest.frd_artifact_id is not None, "FRD artifact not produced"
    assert manifest.dat_artifact_id is not None, "DAT artifact not produced"
    manifest_artifact = next(artifact for artifact in produced if artifact is not None and artifact.artifact_type == ArtifactType.JSON)
    reloaded_manifest = StructuralExecutionManifest.model_validate_json(
        (tmp_path / manifest_artifact.relative_path).read_text(encoding="utf-8"))
    assert reloaded_manifest == manifest
    assert manifest.execution_status == StructuralExecutionStatus.SUCCEEDED
    assert len(manifest.artifacts) >= 3, f"expected at least 3 artifacts, got {len(manifest.artifacts)}"
