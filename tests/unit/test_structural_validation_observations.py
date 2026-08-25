from __future__ import annotations

from mechcad_harness.models.structural import structural_definition_hash
from mechcad_harness.structural.geometry import GeometryRealization
from mechcad_harness.structural.models import (
    ResolvedRegionMap,
    ResolvedStructuralRegion,
    resolved_region_hash,
    region_map_hash,
)
from mechcad_harness.structural.validation import (
    cantilever_geometry_observation,
    cantilever_material_observation,
)
from mechcad_harness.structural_request import (
    MeshSpecification,
    StructuralAnalysisRequest,
    StructuralExecutionSettings,
    StructuralResultField,
    StructuralSourceBinding,
)

from test_structural_service import _definition


def _request(definition):
    binding = StructuralSourceBinding(
        project_id="PRJ-OBS",
        source_revision=1,
        source_state_hash="sha256:" + "s" * 64,
        definition_id=definition.id,
        definition_hash=structural_definition_hash(definition),
        target_body_id=definition.target_body_id,
        source_program_hash="sha256:" + "p" * 64,
        geometry_identity="BOX",
        geometry_artifact_id="STEP-1",
        geometry_artifact_hash="sha256:" + "g" * 64,
    )
    return StructuralAnalysisRequest(
        source_binding=binding,
        selected_load_case_ids=("LC-1",),
        mesh_specification=MeshSpecification(
            global_target_size_mm=5.0,
            quality_policy_id="q1",
            mesher_settings_version="m1",
        ),
        requested_result_fields=(StructuralResultField.DISPLACEMENT,),
        execution_settings=StructuralExecutionSettings(
            max_elements=1000,
            max_runtime_seconds=30,
            max_output_bytes=100000,
            retain_raw_artifacts=True,
        ),
    )


def test_analytical_observations_use_realized_geometry_and_definition_snapshots():
    definition = _definition()
    request = _request(definition)
    region = ResolvedStructuralRegion(
        region_id="free",
        source_geometry_hash=request.source_binding.geometry_artifact_hash,
        resolver_identity="resolver",
        resolver_version="1",
        geometry_kind="planar_face",
        exact_brep_area_mm2=200.0,
        exact_brep_centroid_mm=(100.0, 10.0, 5.0),
        plane_normal=(1.0, 0.0, 0.0),
        bounding_box_mm=(100.0, 0.0, 0.0, 100.0, 20.0, 10.0),
        expected_cardinality=1,
        actual_cardinality=1,
        semantic_descriptor="free",
        region_realization_hash="pending",
    )
    region = region.model_copy(update={"region_realization_hash": resolved_region_hash(region)})
    region_map = ResolvedRegionMap(
        source_geometry_hash=request.source_binding.geometry_artifact_hash,
        resolver_identity="resolver",
        resolver_version="1",
        match_policy_id="policy",
        regions=(region,),
        region_map_hash=region_map_hash(
            (region,),
            source_geometry_hash=request.source_binding.geometry_artifact_hash,
            match_policy_id="policy",
        ),
    )

    geometry = cantilever_geometry_observation(
        request,
        definition,
        GeometryRealization(
            shape_valid=True,
            solid_count=1,
            faces=[],
            bounding_box=(0.0, 0.0, 0.0, 100.0, 20.0, 10.0),
        ),
        region_map,
    )
    material = cantilever_material_observation(request, definition)

    assert (geometry.length_mm, geometry.width_mm, geometry.height_mm) == (100.0, 20.0, 10.0)
    assert geometry.free_end_area_mm2 == 200.0
    assert material.material_identity == "test-material"
    assert material.elastic_modulus_mpa == 70000.0
    assert material.material_assignment_id == "MAT-1"
    assert material.elastic_modulus_source_identity == "test"
