from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from mechcad_harness.structural.deck import DeckBuildError, DeckRepresentation, StructuralDeckBuilder
from mechcad_harness.structural.fakes import (
    FakeDiscoveredRuntime,
    FAKE_GMSH_IDENTITY,
    FakeStructuralCalculiXSolverProvider,
    FakeStructuralGmshMeshingProvider,
    FAKE_CALCULIX_IDENTITY,
)
import mechcad_harness.structural.geometry as geometry_module
import mechcad_harness.structural.mesh as mesh_module
from mechcad_harness.structural.geometry import (
    GeometryResolutionError,
    StructuralFreeCADGeometryAdapter,
    _GEO_SCRIPT,
)
from mechcad_harness.structural.mesh import MeshProviderError, ParsedMesh, StructuralGmshMeshingProvider
from mechcad_harness.structural.runtime import DiscoveredRuntime, GMSH_IDENTITY
from mechcad_harness.structural.results import CalculiXDatResultParser, CalculiXFrdResultParser
from mechcad_harness.structural.models import (
    CALCULIX_PROVIDER_IDENTITY,
    ResolvedRegionMap,
    ResolvedStructuralRegion,
    StructuralExecutionStatus,
    StructuralSolverManifest,
    region_map_hash,
    resolved_region_hash,
)
from mechcad_harness.structural.preflight import ConstraintPreflight
from mechcad_harness.structural.service import StructuralAnalysisService
from mechcad_harness.structural.solver import SolverRunResult, StructuralCalculiXSolverProvider
from mechcad_harness.models.structural import (
    StructuralRegionDefinition,
    StructuralResultField,
    StructuralResultantForce,
)
from test_structural_service import _definition


def _c3d10_mesh(*, midpoint_error: bool = False) -> ParsedMesh:
    nodes = {
        1: (0.0, 0.0, 0.0), 2: (10.0, 0.0, 0.0), 3: (0.0, 10.0, 0.0), 4: (0.0, 0.0, 10.0),
        5: (6.0 if midpoint_error else 5.0, 0.0, 0.0), 6: (5.0, 5.0, 0.0), 7: (0.0, 5.0, 0.0),
        8: (0.0, 0.0, 5.0), 9: (5.0, 0.0, 5.0), 10: (0.0, 5.0, 5.0),
    }
    return ParsedMesh(
        nodes=nodes,
        c3d10={1: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)},
        surface_elements={"free": [(1, (1, 2, 4, 5, 9, 8))]},
        volume_elset_name="volume",
        physical_groups=(),
        mesh_bytes=b"mesh",
    )


def _representation(*, volume_element: int = 1) -> DeckRepresentation:
    mesh = _c3d10_mesh()
    return DeckRepresentation(
        heading="test", nodes=mesh.nodes, c3d10=mesh.c3d10, material_name="mat",
        elastic_modulus_mpa=70000.0, poisson_ratio=0.33, density_t_per_mm3=None,
        boundary_node_sets={"fixed": (1, 2, 3)}, surfaces={"free": [(volume_element, "S2")]},
        pressure_loads=[("free", 1.0)], cload={}, grav_loads=[],
    )


def test_geometry_script_aggregates_all_imported_shapes_before_counting_solids():
    assert "Part.makeCompound([o.Shape for o in objs])" in _GEO_SCRIPT


@pytest.mark.parametrize(
    "stdout",
    (
        "M11GEO={not-json}\n",
        'M11GEO={"shape_valid":true,"solid_count":1,"faces":[{}]}\n',
    ),
)
def test_freecad_geometry_adapter_rejects_malformed_structured_output(monkeypatch, stdout):
    discovery = FakeDiscoveredRuntime(True, "freecadcmd", "fake", FAKE_GMSH_IDENTITY, None)
    adapter = StructuralFreeCADGeometryAdapter(discovery)
    monkeypatch.setattr(
        geometry_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=stdout, stderr=""),
    )

    with pytest.raises(GeometryResolutionError, match="structured output"):
        adapter.realize_geometry("fixture.step")


def test_gmsh_provider_maps_unavailable_runtime_to_mesh_provider_error():
    discovery = DiscoveredRuntime(False, None, None, GMSH_IDENTITY, None)
    provider = StructuralGmshMeshingProvider(discovery)

    with pytest.raises(MeshProviderError, match="unavailable"):
        provider._run_gmsh(Path("fixture.geo"), Path("fixture.msh"), out_format="msh2")


def test_gmsh_provider_maps_launch_error_to_mesh_provider_error(monkeypatch):
    discovery = FakeDiscoveredRuntime(True, "gmsh", "fake", FAKE_GMSH_IDENTITY, None)
    provider = StructuralGmshMeshingProvider(discovery)

    def launch_error(*args, **kwargs):
        raise FileNotFoundError("gmsh")

    monkeypatch.setattr(mesh_module.subprocess, "run", launch_error)

    with pytest.raises(MeshProviderError, match="launch"):
        provider._run_gmsh(Path("fixture.geo"), Path("fixture.msh"), out_format="msh2")


def test_validate_mesh_rejects_non_midpoint_c3d10_node():
    provider = StructuralGmshMeshingProvider.__new__(StructuralGmshMeshingProvider)

    with pytest.raises(MeshProviderError, match="not edge midpoint"):
        provider._validate_mesh(_c3d10_mesh(midpoint_error=True))


def test_deck_validation_rejects_unknown_volume_face_reference():
    with pytest.raises(DeckBuildError, match="unknown element"):
        StructuralDeckBuilder().validate(_representation(volume_element=99))


def test_rendered_deck_requests_textual_node_output_for_nonempty_dat_artifact():
    text = StructuralDeckBuilder()._render(_representation())

    assert "*NODE PRINT,NSET=fixed_nodes\nU\n" in text


def test_rendered_reaction_deck_covers_every_support_region():
    representation = _representation()
    representation.boundary_node_sets = {"fixed": (1, 2, 3), "second": (4, 5, 6)}

    text = StructuralDeckBuilder()._render(
        representation, requested_result_fields=(StructuralResultField.REACTIONS,)
    )

    assert "*NODE PRINT,NSET=fixed_nodes\nRF\n" in text
    assert "*NODE PRINT,NSET=second_nodes\nRF\n" in text


def test_deck_requests_only_requested_result_fields():
    builder = StructuralDeckBuilder()
    displacement = builder._render(
        _representation(), requested_result_fields=(StructuralResultField.DISPLACEMENT,)
    )
    reactions = builder._render(
        _representation(), requested_result_fields=(StructuralResultField.REACTIONS,)
    )

    assert "*NODE FILE\nU\n" in displacement
    assert "*EL FILE\nS\n" not in displacement
    assert "*NODE PRINT,NSET=fixed_nodes\nRF\n" in reactions
    assert "*NODE FILE\nU\n" not in reactions
    assert "*NODE PRINT,NSET=fixed_nodes\nU\n" not in reactions


def test_public_build_requests_only_requested_result_fields():
    parsed_mesh, mesh_manifest, _ = FakeStructuralGmshMeshingProvider().mesh(
        None, None, mesh_spec_hash="sha256:" + "m" * 64
    )
    definition = _definition()
    built = StructuralDeckBuilder().build(
        definition=definition,
        selected_cases=(definition.load_cases[0],),
        fixed_supports=(definition.boundary_conditions[0],),
        region_definitions=definition.regions,
        region_map=ResolvedRegionMap(
            source_geometry_hash="geometry",
            resolver_identity="resolver",
            resolver_version="1",
            match_policy_id="test",
            regions=(),
            region_map_hash="sha256:" + "r" * 64,
        ),
        parsed_mesh=parsed_mesh,
        mesh_hash=mesh_manifest.mesh_hash,
        requested_result_fields=(StructuralResultField.REACTIONS,),
    )

    assert "*NODE PRINT,NSET=fixed_nodes\nRF\n" in built.text
    assert "*EL FILE\nS\n" not in built.text
    assert "*NODE FILE\nU\n" not in built.text
    assert "*NODE PRINT,NSET=fixed_nodes\nU\n" not in built.text


def test_preflight_reports_rank_six_for_fixed_planar_face_and_less_for_one_node():
    nodes = _c3d10_mesh().nodes

    adequate = ConstraintPreflight().evaluate(nodes, {"fixed": (1, 2, 3)})
    inadequate = ConstraintPreflight().evaluate(nodes, {"fixed": (1,)})

    assert adequate.rigid_body_rank == 6
    assert adequate.adequate is True
    assert inadequate.rigid_body_rank < 6
    assert inadequate.adequate is False


@pytest.mark.parametrize(
    ("produced_log", "log_text"),
    [(False, "solver log"), (True, "")],
)
def test_solver_success_requires_finished_job_result_files_and_nonempty_log(produced_log, log_text):
    service = StructuralAnalysisService.__new__(StructuralAnalysisService)
    incomplete = SolverRunResult(
        manifest=StructuralSolverManifest(
            calculix_identity="test", calculix_version="1", exit_code=0, job_finished=True,
            produced_frd=True, produced_dat=True, produced_log=produced_log),
        log_text=log_text, frd_bytes=b"FRD", dat_bytes=b"DAT",
    )

    assert service._classify_solver(incomplete) == StructuralExecutionStatus.SOLVER_FAILED


def test_solver_success_still_requires_both_result_files():
    service = StructuralAnalysisService.__new__(StructuralAnalysisService)
    missing_dat = SolverRunResult(
        manifest=StructuralSolverManifest(
            calculix_identity="test", calculix_version="1", exit_code=0, job_finished=True,
            produced_frd=True, produced_dat=False, produced_log=True),
        log_text="solver log", frd_bytes=b"FRD", dat_bytes=None,
    )

    assert service._classify_solver(missing_dat) == StructuralExecutionStatus.SOLVER_FAILED


def test_fake_solver_success_outputs_fixture_compatible_result_bytes():
    mesh = FakeStructuralGmshMeshingProvider().mesh(
        None, None, mesh_spec_hash="sha256:" + "m" * 64
    )[0]
    result = FakeStructuralCalculiXSolverProvider().execute("*HEADING\n")

    parsed_frd = CalculiXFrdResultParser().parse(result.frd_bytes, mesh)
    parsed_dat = CalculiXDatResultParser().parse_reactions(
        result.dat_bytes, mesh, frozenset({1, 2, 3, 5, 6, 7})
    )

    assert parsed_frd.displacements
    assert parsed_frd.stress_samples
    assert parsed_dat


def test_solver_provider_returns_unavailable_for_launch_and_timeout(monkeypatch):
    discovery = FakeDiscoveredRuntime(True, "ccx", "fake", FAKE_CALCULIX_IDENTITY, None)
    provider = StructuralCalculiXSolverProvider(discovery, timeout_seconds=0.01)

    def missing(*args, **kwargs):
        raise FileNotFoundError("ccx")

    monkeypatch.setattr(subprocess, "run", missing)
    assert provider.execute("*HEADING\n").manifest.exit_code is None

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("ccx", 0.01)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert provider.execute("*HEADING\n").manifest.exit_code is None


def test_fake_solver_identity_cannot_match_live_calculix_identity():
    assert FakeStructuralCalculiXSolverProvider.identity != CALCULIX_PROVIDER_IDENTITY


def test_resultant_force_lowering_conserves_force_and_moment_on_c3d10_surface():
    nodes = {
        1: (0.0, 0.0, 0.0), 2: (20.0, 0.0, 0.0), 3: (0.0, 0.0, 20.0), 4: (0.0, 20.0, 0.0),
        5: (10.0, 0.0, 0.0), 6: (10.0, 0.0, 10.0), 7: (0.0, 0.0, 10.0), 8: (0.0, 10.0, 0.0),
        9: (10.0, 10.0, 0.0), 10: (0.0, 10.0, 10.0),
    }
    mesh = ParsedMesh(
        nodes=nodes,
        c3d10={1: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)},
        surface_elements={"free": [(1, (1, 2, 4, 5, 9, 8))]},
        volume_elset_name="volume", physical_groups=(), mesh_bytes=b"mesh",
    )
    source_hash = "sha256:" + "a" * 64
    resolved = ResolvedStructuralRegion(
        region_id="free", source_geometry_hash=source_hash, resolver_identity="test", resolver_version="1",
        geometry_kind="planar_face", exact_brep_area_mm2=200.0,
        exact_brep_centroid_mm=(20.0 / 3.0, 20.0 / 3.0, 0.0), plane_normal=(0.0, 0.0, -1.0),
        bounding_box_mm=(0.0, 0.0, 0.0, 20.0, 20.0, 0.0), expected_cardinality=1,
        actual_cardinality=1, semantic_descriptor="test", region_realization_hash="pending",
    )
    resolved = resolved.model_copy(update={"region_realization_hash": resolved_region_hash(resolved)})
    region_map = ResolvedRegionMap(
        source_geometry_hash=source_hash, resolver_identity="test", resolver_version="1", match_policy_id="test",
        regions=(resolved,), region_map_hash=region_map_hash((resolved,), source_geometry_hash=source_hash, match_policy_id="test"),
    )
    region = StructuralRegionDefinition(
        region_id="free", target_body_id="BODY-1", source_primitive_id="free_face", semantic_role="load",
        geometry_kind="face", selector_kind="planar_face_centroid_axis", selector_parameters={"axis": "x", "side": "max"},
        expected_cardinality=1, resolver_version="1",
    )
    load = StructuralResultantForce(
        load_id="LF-1", target_region_id="free", magnitude_n=300.0, direction_xyz=(0.0, 0.0, -1.0),
        frame="component_local", distribution="uniform_surface_traction_equivalent",
    )
    cload = {}

    lowered = StructuralDeckBuilder()._lower_resultant_force(
        load=load, region=region, region_map=region_map, parsed_mesh=mesh, cload=cload, mesh_hash="sha256:mesh",
        midside_by_boundary_el={1: (5, 9, 8)},
    )

    assert sum(force[2] for force in cload.values()) == pytest.approx(-300.0)
    assert lowered.force_conservation_error_n == pytest.approx(0.0)
    assert lowered.moment_conservation_error_n_mm == pytest.approx(0.0)
