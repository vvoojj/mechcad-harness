from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import pytest

from mechcad_harness.agents import AgentIdentity
from mechcad_harness.agents.fake import FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
import mechcad_harness.application as application_module
from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.artifacts.storage import ArtifactStore, ArtifactType
from mechcad_harness.models import DesignState
from mechcad_harness.models.structural import StructuralAnalysisDefinition, StructuralResultField, structural_definition_hash
from mechcad_harness.state import StateManager
from mechcad_harness.state.errors import StateIntegrityError
from mechcad_harness.structural.deck import DeckBuildError, StructuralDeckBuilder
from mechcad_harness.structural.fakes import (
    FAKE_FREECAD_IDENTITY,
    FakeStructuralCalculiXSolverProvider,
    FakeStructuralDeckBuilder,
    FakeStructuralFreeCADGeometryAdapter,
    FakeStructuralGmshMeshingProvider,
    FakeStructuralRegionResolver,
)
from mechcad_harness.structural.geometry import (
    GeometryResolutionError,
    RegionResolutionError,
    StructuralFreeCADGeometryAdapter,
)
import mechcad_harness.structural.geometry as geometry_module
from mechcad_harness.structural.models import StructuralExecutionStatus
from mechcad_harness.structural.models import StructuralExecutionResult, mesh_input_hash
from mechcad_harness.structural.preflight import ConstraintPreflightResult
from mechcad_harness.structural.runtime import DiscoveredRuntime, GMSH_IDENTITY
from types import SimpleNamespace
from mechcad_harness.structural.service import StructuralAnalysisService
from mechcad_harness.structural_request import (
    MeshSpecification,
    StructuralAnalysisRequest,
    StructuralExecutionSettings,
    StructuralSourceBinding,
)


PROJECT_ID = "PRJ-M11-3-unit"


def _definition() -> StructuralAnalysisDefinition:
    return StructuralAnalysisDefinition.model_validate({
        "id": "DEF-1",
        "name": "Structural fixture",
        "target_body_id": "BODY-1",
        "regions": [
            {
                "region_id": "fixed", "target_body_id": "BODY-1", "source_primitive_id": "fixed_face",
                "semantic_role": "fixed_support", "geometry_kind": "face",
                "selector_kind": "planar_face_centroid_axis", "selector_parameters": {"axis": "x", "side": "min"},
                "expected_cardinality": 1, "resolver_version": "1",
            },
            {
                "region_id": "free", "target_body_id": "BODY-1", "source_primitive_id": "free_face",
                "semantic_role": "load", "geometry_kind": "face",
                "selector_kind": "planar_face_centroid_axis", "selector_parameters": {"axis": "x", "side": "max"},
                "expected_cardinality": 1, "resolver_version": "1",
            },
        ],
        "material_assignment": {
            "assignment_id": "MAT-1", "target_body_id": "BODY-1", "material_identity": "test-material",
            "assignment_context": "test", "property_snapshot": [
                {"property_name": "elastic_modulus", "value": 70000.0, "normalized_unit": "MPa",
                 "source_identity": "test", "authority": "typical_reference",
                 "conversion_provenance": {"source_unit": "MPa", "normalization_rule": "as_is", "conversion_version": "1"}},
                {"property_name": "poisson_ratio", "value": 0.33, "normalized_unit": "ratio",
                 "source_identity": "test", "authority": "typical_reference",
                 "conversion_provenance": {"source_unit": "ratio", "normalization_rule": "as_is", "conversion_version": "1"}},
            ],
        },
        "load_cases": [{
            "id": "LC-1", "name": "load", "loads": [{
                "kind": "surface_pressure", "load_id": "LP-1", "target_region_id": "free", "pressure_mpa": 1.0,
                "signed_normal_convention": "outward_positive", "frame": "component_local",
            }],
        }, {
            "id": "LC-2", "name": "load 2", "loads": [{
                "kind": "surface_pressure", "load_id": "LP-2", "target_region_id": "free", "pressure_mpa": 2.0,
                "signed_normal_convention": "outward_positive", "frame": "component_local",
            }],
        }, {
            "id": "LC-3", "name": "load 3", "loads": [{
                "kind": "surface_pressure", "load_id": "LP-3", "target_region_id": "free", "pressure_mpa": 3.0,
                "signed_normal_convention": "outward_positive", "frame": "component_local",
            }],
        }],
        "boundary_conditions": [{
            "support_id": "SUP-1", "target_region_id": "fixed", "applies_to_load_case_ids": ["LC-1", "LC-2", "LC-3"],
            "frame": "component_local", "constrained_dofs": ["ux", "uy", "uz"],
        }],
        "acceptance_criteria": [],
        "material_authority_policy": {"allowed_authorities_by_property": [
            {"property_name": "elastic_modulus", "allowed_authorities": ["typical_reference"]},
            {"property_name": "poisson_ratio", "allowed_authorities": ["typical_reference"]},
        ]},
        "physical_assumptions": {},
    })


@dataclass
class PreparedStructuralRequest:
    app: ProductionApplication
    workspace: Path
    request: StructuralAnalysisRequest
    step_path: Path


@pytest.fixture
def prepared_structural_request(tmp_path: Path) -> PreparedStructuralRequest:
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text("ownership: []\n", encoding="utf-8")
    dependencies.write_text('{"rules": [], "edges": []}\n', encoding="utf-8")
    definition = _definition()
    state = DesignState(id="DES-M11-3-unit", revision=1, structural_analysis_definitions=[definition])
    StateManager(tmp_path).create_project(PROJECT_ID, state)
    app = ProductionApplication.create(
        tmp_path,
        PROJECT_ID,
        FakeAgentAdapter(AgentIdentity(
            agent_name="test", agent_version="1", role="test", protocol_version="1"), scripted_responses=()),
        ownership_path=ownership,
        dependency_path=dependencies,
    )
    current = app.state_manager._read_current(PROJECT_ID)
    artifact_run = app.run_controller.create_run(
        PROJECT_ID,
        expected_source=__import__("mechcad_harness.runs.models", fromlist=["SourceBinding"]).SourceBinding(
            project_id=PROJECT_ID, revision=current["revision"], state_hash=current["state_hash"]),
    )
    artifact = ArtifactStore(tmp_path, project_id=PROJECT_ID, run_id=artifact_run.run_id).publish(
        "STEP-UNIT", ArtifactType.STEP, "fixture.step", b"ISO-10303-21;\nEND-ISO-10303-21;\n",
        "test-step", "1", current["revision"], current["state_hash"],
        backend_provenance=FakeStructuralFreeCADGeometryAdapter()._discovery.provenance,
    )
    request = StructuralAnalysisRequest(
        source_binding=StructuralSourceBinding(
            project_id=PROJECT_ID, source_revision=current["revision"], source_state_hash=current["state_hash"],
            definition_id=definition.id, definition_hash=structural_definition_hash(definition),
            target_body_id=definition.target_body_id, source_program_hash="sha256:" + "1" * 64,
            geometry_identity="fixture", geometry_artifact_id=artifact.artifact_id, geometry_artifact_hash=artifact.sha256,
        ),
        selected_load_case_ids=("LC-1",),
        mesh_specification=MeshSpecification(global_target_size_mm=5.0, quality_policy_id="test", mesher_settings_version="1"),
        requested_result_fields=(StructuralResultField.DISPLACEMENT,),
        execution_settings=StructuralExecutionSettings(
            max_elements=1000, max_runtime_seconds=30, max_output_bytes=100000, retain_raw_artifacts=True),
    )
    return PreparedStructuralRequest(app, tmp_path, request, tmp_path / artifact.relative_path)


def _service(prepared: PreparedStructuralRequest, **overrides) -> StructuralAnalysisService:
    return StructuralAnalysisService(
        state_manager=prepared.app.state_manager,
        run_controller=prepared.app.run_controller,
        workspace=prepared.workspace,
        geometry_adapter=overrides.get("geometry", FakeStructuralFreeCADGeometryAdapter()),
        region_resolver=overrides.get("regions", FakeStructuralRegionResolver()),
        gmsh_provider=overrides.get("mesh", FakeStructuralGmshMeshingProvider()),
        deck_builder=overrides.get("deck", FakeStructuralDeckBuilder()),
        constraint_preflight=overrides.get("preflight", __import__("mechcad_harness.structural.preflight", fromlist=["ConstraintPreflight"]).ConstraintPreflight()),
        calculix_provider=overrides.get("solver", FakeStructuralCalculiXSolverProvider()),
    )


@pytest.fixture
def prepared_two_case_request(prepared_structural_request) -> PreparedStructuralRequest:
    request_values = prepared_structural_request.request.model_dump(mode="json")
    request_values.update({"selected_load_case_ids": ["LC-1", "LC-2"], "request_hash": "pending"})
    request = StructuralAnalysisRequest.model_validate(request_values)
    return PreparedStructuralRequest(
        prepared_structural_request.app,
        prepared_structural_request.workspace,
        request,
        prepared_structural_request.step_path,
    )


@pytest.fixture
def prepared_three_case_request(prepared_structural_request) -> PreparedStructuralRequest:
    request_values = prepared_structural_request.request.model_dump(mode="json")
    request_values.update({"selected_load_case_ids": ["LC-1", "LC-2", "LC-3"], "request_hash": "pending"})
    request = StructuralAnalysisRequest.model_validate(request_values)
    return PreparedStructuralRequest(
        prepared_structural_request.app,
        prepared_structural_request.workspace,
        request,
        prepared_structural_request.step_path,
    )


def _fail_on_second_case():
    return FakeStructuralCalculiXSolverProvider(fail_on_call=2)


def test_execute_creates_ordered_case_partitions_using_one_mesh(prepared_two_case_request):
    solver = FakeStructuralCalculiXSolverProvider()
    result = _service(prepared_two_case_request, solver=solver).execute(prepared_two_case_request.request)

    assert result.execution_status is StructuralExecutionStatus.SUCCEEDED
    assert result.manifest is not None
    assert [case.load_case_id for case in result.manifest.case_manifests] == ["LC-1", "LC-2"]
    assert len({case.mesh_artifact_hash for case in result.manifest.case_manifests}) == 1
    assert solver.calls == 2
    assert result.manifest.case_manifests[0].deck_artifact_id != result.manifest.case_manifests[1].deck_artifact_id
    assert result.manifest.deck_artifact_id is None
    assert result.manifest.deck_artifact_hash is None
    assert result.manifest.deck_semantic_hash is None
    assert result.manifest.solver_manifest is None
    assert result.manifest.log_artifact_id is None
    assert result.manifest.log_artifact_hash is None
    assert result.manifest.frd_artifact_id is None
    assert result.manifest.frd_artifact_hash is None
    assert result.manifest.dat_artifact_id is None
    assert result.manifest.dat_artifact_hash is None
    store = ArtifactStore(
        prepared_two_case_request.workspace,
        project_id=PROJECT_ID,
        run_id=result.run_id,
    )
    mesh = store.existing(result.manifest.mesh_artifact_id)
    assert mesh is not None
    expected_mesh_input = mesh_input_hash(
        source_geometry_hash=prepared_two_case_request.request.source_binding.geometry_artifact_hash,
        mesh_specification_hash=result.manifest.mesh_specification_hash,
        region_map_hash=result.manifest.region_map_hash,
        gmsh_identity=result.manifest.gmsh_identity,
        gmsh_version=result.manifest.gmsh_version,
    )
    assert mesh.input_hash == expected_mesh_input
    assert mesh.input_hash != mesh.sha256
    for case in result.manifest.case_manifests:
        deck = store.existing(case.deck_artifact_id)
        log = store.existing(case.log_artifact_id)
        assert deck is not None and deck.input_hash == mesh.sha256
        assert log is not None and log.input_hash == deck.sha256
    request_manifest = store.existing(result.produced_artifact_ids[-1])
    assert request_manifest is not None
    assert request_manifest.input_hash == prepared_two_case_request.request.request_hash
    assert request_manifest.sha256 not in {artifact.input_hash for artifact in (mesh,)}


def test_production_structural_execution_rejects_source_change_after_execute(
    prepared_structural_request, monkeypatch
):
    app = prepared_structural_request.app

    def mutate_source(_request):
        state = app.state_manager.load_current_state(PROJECT_ID)
        app.state_manager.create_revision(PROJECT_ID, state)
        return StructuralExecutionResult(execution_status=StructuralExecutionStatus.SOLVER_FAILED)

    monkeypatch.setattr(app.structural_service, "execute", mutate_source)

    with pytest.raises(StateIntegrityError, match="changed during structural execution"):
        app.execute_structural_analysis(request=prepared_structural_request.request)


@pytest.mark.parametrize(
    "provenance",
    [
        None,
        BackendProvenance(
            backend_name="freecad",
            backend_adapter_version="foreign-adapter@1",
            library_name="FreeCAD",
            library_version="1.1.3",
            library_source="bundled",
            library_revision="foreign-revision",
        ),
    ],
)
def test_structural_execution_rejects_source_without_composed_freecad_provenance(
    prepared_structural_request, provenance
):
    metadata_path = prepared_structural_request.step_path.parent / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    original = metadata.copy()
    metadata["backend_provenance"] = provenance.model_dump(mode="json") if provenance else None
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = _service(prepared_structural_request).execute(prepared_structural_request.request)

    assert result.execution_status is StructuralExecutionStatus.GEOMETRY_REJECTED
    assert result.manifest is None
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["backend_provenance"] == metadata["backend_provenance"]
    assert original["sha256"] == metadata["sha256"]


def test_production_evaluation_rejects_forged_in_memory_manifest(
    prepared_structural_request, monkeypatch
):
    execution = _service(prepared_structural_request).execute(prepared_structural_request.request)
    assert execution.manifest is not None
    app = prepared_structural_request.app
    app._structural_requests[prepared_structural_request.request.request_hash] = prepared_structural_request.request
    forged = execution.manifest.model_copy(update={"geometry_artifact_hash": "sha256:" + "f" * 64})
    interpreted = []

    class ForgivingInterpreter:
        def __init__(self, **_kwargs):
            pass

        def interpret(self, manifest, **_kwargs):
            interpreted.append(manifest)
            return object()

    monkeypatch.setattr(application_module, "StructuralResultInterpreter", ForgivingInterpreter)
    monkeypatch.setattr(app._structural_verification_service, "evaluate", lambda *_args: object())

    with pytest.raises(ValueError, match="durable execution manifest"):
        app.evaluate_structural_analysis(execution_manifest=forged)

    assert interpreted == []


def test_second_case_failure_persists_failed_request_manifest_without_result(prepared_two_case_request):
    solver = _fail_on_second_case()

    result = _service(prepared_two_case_request, solver=solver).execute(
        prepared_two_case_request.request
    )

    assert result.execution_status is StructuralExecutionStatus.SOLVER_FAILED
    assert result.manifest is not None
    assert [case.execution_status for case in result.manifest.case_manifests] == [
        StructuralExecutionStatus.SUCCEEDED,
        StructuralExecutionStatus.SOLVER_FAILED,
    ]
    assert solver.calls == 2
    assert result.manifest.case_manifests[1].failure_stage == "solver"
    assert result.manifest.case_manifests[1].error_detail
    manifest_artifact = ArtifactStore(
        prepared_two_case_request.workspace,
        project_id=PROJECT_ID,
        run_id=result.run_id,
    ).existing(result.produced_artifact_ids[-1])
    assert manifest_artifact is not None
    assert manifest_artifact.artifact_type is ArtifactType.JSON


@pytest.mark.parametrize(
    ("fail_on_call", "expected_case_ids"),
    [
        (1, ("LC-1",)),
        (2, ("LC-1", "LC-2")),
    ],
)
def test_first_and_intermediate_case_failures_persist_ordered_failed_manifest(
    prepared_three_case_request, fail_on_call, expected_case_ids
):
    result = _service(
        prepared_three_case_request,
        solver=FakeStructuralCalculiXSolverProvider(fail_on_call=fail_on_call),
    ).execute(prepared_three_case_request.request)

    assert result.execution_status is StructuralExecutionStatus.SOLVER_FAILED
    assert result.manifest is not None
    assert result.manifest.execution_status is StructuralExecutionStatus.SOLVER_FAILED
    assert tuple(case.load_case_id for case in result.manifest.case_manifests) == expected_case_ids
    assert result.manifest.case_manifests[-1].execution_status is StructuralExecutionStatus.SOLVER_FAILED
    assert result.produced_artifact_ids[-1].startswith("STRUCT-JSON-")


def test_execute_rejects_stale_source_binding_without_creating_run(prepared_structural_request):
    request = prepared_structural_request.request.model_copy(update={
        "source_binding": prepared_structural_request.request.source_binding.model_copy(update={"source_revision": 2}),
    })

    result = _service(prepared_structural_request).execute(request)

    assert result.execution_status == StructuralExecutionStatus.GEOMETRY_REJECTED
    assert result.run_id is None
    assert result.failure_stage == "source_binding"


@pytest.mark.parametrize("binding_update", (
    {"definition_id": "MISSING"},
    {"definition_hash": "sha256:" + "f" * 64},
))
def test_execute_rejects_missing_or_changed_definition(prepared_structural_request, binding_update):
    request = prepared_structural_request.request.model_copy(update={
        "source_binding": prepared_structural_request.request.source_binding.model_copy(update=binding_update),
    })

    result = _service(prepared_structural_request).execute(request)

    assert result.execution_status == StructuralExecutionStatus.GEOMETRY_REJECTED
    assert result.failure_stage == "definition"
    assert result.manifest is None
    assert result.error_detail


def test_execute_rejects_tampered_artifact_before_geometry(prepared_structural_request):
    prepared_structural_request.step_path.write_bytes(b"tampered STEP")

    result = _service(prepared_structural_request).execute(prepared_structural_request.request)

    assert result.execution_status == StructuralExecutionStatus.GEOMETRY_REJECTED
    assert result.failure_stage == "geometry"


class _FailingGeometry(FakeStructuralFreeCADGeometryAdapter):
    def realize_geometry(self, step_path):
        raise GeometryResolutionError("bad geometry")


class _FailingRegions(FakeStructuralRegionResolver):
    def resolve(self, regions, realization, *, source_geometry_hash):
        raise RegionResolutionError("bad region")


class _FailingDeck(StructuralDeckBuilder):
    def build(self, **kwargs):
        raise DeckBuildError("bad deck")


def test_execute_classifies_geometry_region_and_deck_failures(prepared_structural_request):
    cases = (
        (_service(prepared_structural_request, geometry=_FailingGeometry()), StructuralExecutionStatus.GEOMETRY_REJECTED, "geometry"),
        (_service(prepared_structural_request, regions=_FailingRegions()), StructuralExecutionStatus.REGION_RESOLUTION_FAILED, "region_resolution"),
        (_service(prepared_structural_request, deck=_FailingDeck()), StructuralExecutionStatus.DECK_INVALID, "deck"),
    )

    for service, expected_status, expected_stage in cases:
        result = service.execute(prepared_structural_request.request)
        assert result.execution_status == expected_status, result.error_detail
        assert result.failure_stage == expected_stage


def test_execute_classifies_unavailable_freecad_geometry_runtime(prepared_structural_request):
    source_provenance = FakeStructuralFreeCADGeometryAdapter()._discovery.provenance
    unavailable = DiscoveredRuntime(
        available=False,
        executable=None,
        version=None,
        identity=FAKE_FREECAD_IDENTITY,
        provenance=source_provenance,
    )

    result = _service(
        prepared_structural_request,
        geometry=StructuralFreeCADGeometryAdapter(unavailable),
    ).execute(prepared_structural_request.request)

    assert result.execution_status is StructuralExecutionStatus.GEOMETRY_REJECTED
    assert result.failure_stage == "geometry"
    assert "FreeCAD" in result.error_detail


def test_execute_classifies_malformed_freecad_structured_output(prepared_structural_request, monkeypatch):
    source_provenance = FakeStructuralFreeCADGeometryAdapter()._discovery.provenance
    geometry = StructuralFreeCADGeometryAdapter(
        DiscoveredRuntime(True, "freecadcmd", "fake", FAKE_FREECAD_IDENTITY, source_provenance)
    )
    monkeypatch.setattr(
        geometry_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="M11GEO={not-json}\n", stderr=""
        ),
    )

    result = _service(prepared_structural_request, geometry=geometry).execute(
        prepared_structural_request.request
    )

    assert result.execution_status is StructuralExecutionStatus.GEOMETRY_REJECTED
    assert result.failure_stage == "geometry"


def test_execute_classifies_unavailable_gmsh_runtime(prepared_structural_request):
    unavailable = DiscoveredRuntime(False, None, None, GMSH_IDENTITY, None)
    mesh = __import__(
        "mechcad_harness.structural.mesh", fromlist=["StructuralGmshMeshingProvider"]
    ).StructuralGmshMeshingProvider(unavailable)

    result = _service(prepared_structural_request, mesh=mesh).execute(
        prepared_structural_request.request
    )

    assert result.execution_status is StructuralExecutionStatus.MESH_FAILED
    assert result.failure_stage == "mesh"


class _Underconstrained:
    def evaluate(self, nodes, fixed_node_sets):
        return ConstraintPreflightResult(5, False, 3, "test", 1e-9)


class _CountingSolver(FakeStructuralCalculiXSolverProvider):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def execute(self, deck_text):
        self.calls += 1
        return super().execute(deck_text)


class _UnavailableSolver(FakeStructuralCalculiXSolverProvider):
    def execute(self, deck_text):
        raise RuntimeError("calculix runtime is unavailable")


def test_execute_stops_before_solver_when_preflight_is_underconstrained(prepared_structural_request):
    solver = _CountingSolver()

    result = _service(prepared_structural_request, preflight=_Underconstrained(), solver=solver).execute(prepared_structural_request.request)

    assert result.execution_status == StructuralExecutionStatus.SOLVER_UNDERCONSTRAINED, result.error_detail
    assert result.failure_stage == "constraint_preflight"
    assert solver.calls == 0


def test_execute_classifies_unavailable_solver_runtime(prepared_structural_request):
    result = _service(prepared_structural_request, solver=_UnavailableSolver()).execute(prepared_structural_request.request)

    assert result.execution_status == StructuralExecutionStatus.SOLVER_UNAVAILABLE
    assert result.failure_stage == "solver"


def test_fake_provider_execution_manifest_preserves_fake_provider_identities(prepared_structural_request):
    result = _service(prepared_structural_request).execute(prepared_structural_request.request)

    assert result.execution_status == StructuralExecutionStatus.SUCCEEDED, result.error_detail
    assert result.manifest is not None
    assert result.manifest.resolver_identity == "fake-structural-region-resolver@0"
    assert result.manifest.gmsh_identity == "fake-gmsh@0"
    assert result.manifest.deck_builder_identity == "fake-deck-builder@0"
    assert result.manifest.calculix_identity == "fake-calculix@0"
