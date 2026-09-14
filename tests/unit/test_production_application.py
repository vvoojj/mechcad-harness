from pathlib import Path
import inspect
from types import SimpleNamespace

import pytest

from mechcad_harness.agents.models import (
    AgentAdapterExecutionOutcome,
    AgentAdapterIdentity,
    AgentAdapterProvenance,
    AgentAuthoredResponsePayload,
)
from mechcad_harness.agents import AgentIdentity
from mechcad_harness.models import Component, DesignState
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.state.errors import RevisionNotFoundError, StateIntegrityError
from mechcad_harness.runs import RunController
from mechcad_harness.runs.models import SourceBinding, TaskDefinition
from mechcad_harness.tools import BuiltinTools, ToolVersionError
from mechcad_harness.tools.errors import ToolPermissionError


class CountingAdapter:
    def __init__(self, identity=None):
        self.identity = identity or AgentAdapterIdentity(adapter_name="forged-provider", adapter_version="9.9")
        self.invocation_count = 0
        self.requests = []

    def invoke(self, request):
        self.invocation_count += 1
        self.requests.append(request)
        return AgentAdapterExecutionOutcome(
            authored_response=AgentAuthoredResponsePayload(
                status="succeeded",
                summary="unused",
                findings=(),
                issues=(),
                constraint_requests=(),
                change_proposals=(),
            ),
            provenance=AgentAdapterProvenance(
                adapter_name="forged-provider",
                adapter_version="9.9",
                provider="test",
                transport="test",
            ),
        )


def make_state() -> DesignState:
    return DesignState(
        id="DES-production",
        revision=1,
        components=[Component(id="PRT-bracket", name="Bracket")],
    )


def build_application(tmp_path: Path, adapter: CountingAdapter):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    StateManager(workspace).create_project("PRJ-production", make_state())

    from mechcad_harness.application import ProductionApplication

    return ProductionApplication.create(
        workspace,
        "PRJ-production",
        adapter,
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def _analytical_observation_inputs(tmp_path: Path):
    from test_structural_service import _definition

    from mechcad_harness.artifacts.models import ArtifactType
    from mechcad_harness.artifacts.storage import ArtifactStore
    from mechcad_harness.backends.provenance import provenance_from_identity
    from mechcad_harness.models.structural import (
        StructuralResultField,
        structural_definition_hash,
    )
    from mechcad_harness.structural.geometry import GeometryRealization
    from mechcad_harness.structural.models import (
        REGION_RESOLVER_IDENTITY,
        ResolvedRegionMap,
        ResolvedStructuralRegion,
        resolved_region_hash,
        region_map_hash,
        StructuralArtifactRef,
    )
    from mechcad_harness.structural.runtime import FREECAD_IDENTITY
    from mechcad_harness.structural_request import (
        MeshSpecification,
        StructuralAnalysisRequest,
        StructuralExecutionSettings,
        StructuralSourceBinding,
    )

    application = build_application(tmp_path, CountingAdapter())
    definition = _definition()
    source = application.load_state()
    source_program_hash = "sha256:" + "p" * 64
    store = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id="RUN-F21-OBS",
    )
    artifact = store.publish(
        "STEP-F21-OBS",
        ArtifactType.STEP,
        "source.step",
        b"ISO-10303-21;\nEND-ISO-10303-21;\n",
        "mechcad-freecad",
        FREECAD_IDENTITY.adapter_version,
        source.revision,
        source.state_hash,
        backend_provenance=provenance_from_identity(FREECAD_IDENTITY),
        input_hash=source_program_hash,
    )
    request = StructuralAnalysisRequest(
        source_binding=StructuralSourceBinding(
            project_id=application.project_id,
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            definition_id=definition.id,
            definition_hash=structural_definition_hash(definition),
            target_body_id=definition.target_body_id,
            source_program_hash=source_program_hash,
            geometry_identity="fixture",
            geometry_artifact_id=artifact.artifact_id,
            geometry_artifact_hash=artifact.sha256,
        ),
        selected_load_case_ids=("LC-1",),
        mesh_specification=MeshSpecification(
            global_target_size_mm=5.0,
            quality_policy_id="f21-quality",
            mesher_settings_version="f21-mesher",
        ),
        requested_result_fields=(StructuralResultField.DISPLACEMENT,),
        execution_settings=StructuralExecutionSettings(
            max_elements=1000,
            max_runtime_seconds=30,
            max_output_bytes=100000,
            retain_raw_artifacts=True,
        ),
    )
    region = ResolvedStructuralRegion(
        region_id="free",
        source_geometry_hash=request.source_binding.geometry_artifact_hash,
        resolver_identity="f21-resolver",
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
        resolver_identity="f21-resolver",
        resolver_version="1",
        match_policy_id="f21-policy",
        regions=(region,),
        region_map_hash=region_map_hash(
            (region,),
            source_geometry_hash=request.source_binding.geometry_artifact_hash,
            match_policy_id="f21-policy",
        ),
    )
    realization = GeometryRealization(
        shape_valid=True,
        solid_count=1,
        faces=[],
        bounding_box=(0.0, 0.0, 0.0, 100.0, 20.0, 10.0),
    )
    manifest = SimpleNamespace(
        run_id="RUN-F21-OBS",
        project_id=application.project_id,
        revision=source.revision,
        state_hash=source.state_hash,
        definition_id=definition.id,
        definition_hash=request.source_binding.definition_hash,
        request_hash=request.request_hash,
        geometry_artifact_id=artifact.artifact_id,
        geometry_artifact_hash=artifact.sha256,
        geometry_provider_provenance=provenance_from_identity(FREECAD_IDENTITY),
        resolver_identity=REGION_RESOLVER_IDENTITY,
        resolver_version="1",
        artifacts=(
            StructuralArtifactRef(
                artifact_type=ArtifactType.STEP.value,
                artifact_id=artifact.artifact_id,
                sha256=artifact.sha256,
                producer_identity=artifact.producer_tool_name,
                producer_version=artifact.producer_tool_version,
            ),
        ),
    )
    return SimpleNamespace(
        application=application,
        artifact=artifact,
        definition=definition,
        manifest=manifest,
        realization=realization,
        region_map=region_map,
        request=request,
    )


def _record_observation_construction(monkeypatch, application_module):
    calls = []
    original_geometry = application_module.cantilever_geometry_observation
    original_material = application_module.cantilever_material_observation

    def geometry(*args):
        calls.append(("geometry", args))
        return original_geometry(*args)

    def material(*args):
        calls.append(("material", args))
        return original_material(*args)

    monkeypatch.setattr(application_module, "cantilever_geometry_observation", geometry)
    monkeypatch.setattr(application_module, "cantilever_material_observation", material)
    return calls


def _assert_observation_pair(actual_geometry, actual_material, expected_geometry, expected_material):
    assert actual_geometry == expected_geometry
    assert actual_material == expected_material
    assert actual_geometry.model_dump(mode="json") == expected_geometry.model_dump(mode="json")
    assert actual_material.model_dump(mode="json") == expected_material.model_dump(mode="json")
    assert actual_material.material_assignment_id == expected_material.material_assignment_id
    assert (
        actual_material.elastic_modulus_source_identity
        == expected_material.elastic_modulus_source_identity
    )
    assert (
        actual_material.poisson_ratio_source_identity
        == expected_material.poisson_ratio_source_identity
    )


def _configure_path_a_characterization(application, application_module, inputs, monkeypatch):
    captured = {}

    class RecordingValidator:
        def validate(self, *args, **kwargs):
            captured.update(kwargs)
            return "validation"

    monkeypatch.setattr(application_module, "parse_trusted_msh_bytes", lambda _bytes: object())
    monkeypatch.setattr(application, "_assert_composed_structural_dependencies", lambda *_args: None)
    monkeypatch.setattr(
        application.structural_service.geometry_adapter,
        "realize_geometry",
        lambda _path: inputs.realization,
    )
    monkeypatch.setattr(
        application.structural_service.region_resolver,
        "resolve",
        lambda *_args, **_kwargs: inputs.region_map,
    )
    monkeypatch.setattr(application_module, "StructuralAnalyticalValidator", RecordingValidator)
    return captured


def _configure_path_b_characterization(application, application_module, inputs, monkeypatch):
    from mechcad_harness.structural.evidence_models import RectangularCantileverValidationPolicy
    from mechcad_harness.structural.results import StructuralAnalysisEvaluation
    from mechcad_harness.structural.models import mesh_specification_hash

    captured = {}
    result = SimpleNamespace(result_hash="f21-result-hash")
    evaluation = StructuralAnalysisEvaluation(result=result, verification=object())
    policy = RectangularCantileverValidationPolicy(
        material_identity=inputs.definition.material_assignment.material_identity,
        length_mm=100.0,
        width_mm=20.0,
        height_mm=10.0,
        elastic_modulus_mpa=70000.0,
        poisson_ratio=0.33,
        resultant_force_n=(0.0, -1.0, 0.0),
        mesh_specification_hash=mesh_specification_hash(inputs.request.mesh_specification),
        free_end_region_id="free",
        fixed_end_region_id="fixed",
        free_end_area_mm2=200.0,
        displacement_relative_tolerance=0.1,
        reaction_relative_tolerance=0.1,
    )

    class FakeInterpreter:
        _is_trusted_freecad_provenance = staticmethod(lambda _provenance: True)

        def __init__(self, **_kwargs):
            pass

        def interpret(self, *_args, **_kwargs):
            return result

        def load_trusted_mesh(self, *_args, **_kwargs):
            return object(), b"mesh"

    class RecordingValidator:
        def validate(self, *args, **kwargs):
            captured.update(kwargs)
            return "validation"

    monkeypatch.setattr(application, "_reload_structural_execution_manifest", lambda *_args: inputs.manifest)
    monkeypatch.setattr(application, "_assert_composed_structural_dependencies", lambda *_args: None)
    monkeypatch.setattr(application_module, "StructuralResultInterpreter", FakeInterpreter)
    monkeypatch.setattr(application_module, "structural_result_hash", lambda _result: "f21-result-hash")
    monkeypatch.setattr(application_module, "StructuralAnalyticalValidator", RecordingValidator)
    monkeypatch.setattr(
        application.structural_service.geometry_adapter,
        "realize_geometry",
        lambda _path: inputs.realization,
    )
    monkeypatch.setattr(
        application.structural_service.region_resolver,
        "resolve",
        lambda *_args, **_kwargs: inputs.region_map,
    )
    return captured, result, evaluation, policy


def _fixed_f21_analytical_payload():
    from test_structural_evidence_models import _payload

    from mechcad_harness.backends.provenance import provenance_from_identity
    from mechcad_harness.structural.evidence import (
        StructuralEvidencePayload,
        StructuralPipelineProvenance,
    )
    from mechcad_harness.structural.evidence_models import (
        AnalyticalValidationCheck,
        CantileverGeometryObservation,
        CantileverMaterialObservation,
        RectangularCantileverValidationPolicy,
        StructuralAnalyticalValidationResult,
        cantilever_validation_policy_hash,
    )
    from mechcad_harness.structural.models import execution_manifest_hash
    from mechcad_harness.structural.runtime import CALCULIX_IDENTITY, GMSH_IDENTITY

    base = _payload()
    policy = RectangularCantileverValidationPolicy(
        request_hash=base.request.request_hash,
        geometry_artifact_hash=base.request.source_binding.geometry_artifact_hash,
        material_identity="test-material",
        length_mm=100.0,
        width_mm=20.0,
        height_mm=10.0,
        elastic_modulus_mpa=70000.0,
        poisson_ratio=0.33,
        resultant_force_n=(0.0, -1.0, 0.0),
        mesh_specification_hash=base.execution_manifest.mesh_specification_hash,
        mesh_hash=base.execution_manifest.mesh_artifact_hash,
        region_map_hash=base.execution_manifest.region_map_hash,
        free_end_region_id="free",
        fixed_end_region_id="fixed",
        free_end_area_mm2=200.0,
        displacement_relative_tolerance=0.1,
        reaction_relative_tolerance=0.1,
    )
    checks = tuple(
        AnalyticalValidationCheck(
            check_id=check_id,
            expected_value=0.0,
            observed_value=0.0,
            absolute_error=0.0,
            relative_error=0.0,
            tolerance=1.0,
            status="pass",
        )
        for check_id in (
            "geometry",
            "material",
            "load",
            "tip_displacement",
            "reaction_force",
            "reaction_moment",
        )
    )
    analytical = StructuralAnalyticalValidationResult(
        policy=policy,
        policy_hash=cantilever_validation_policy_hash(policy),
        source_result_hash=base.result.result_hash,
        source_request_hash=base.request.request_hash,
        source_execution_manifest_hash=execution_manifest_hash(base.execution_manifest),
        status="pass",
        checks=checks,
    )
    binding = base.request.source_binding
    geometry = CantileverGeometryObservation(
        project_id=binding.project_id,
        source_revision=binding.source_revision,
        source_state_hash=binding.source_state_hash,
        definition_id=binding.definition_id,
        definition_hash=binding.definition_hash,
        geometry_artifact_id=binding.geometry_artifact_id,
        geometry_artifact_hash=binding.geometry_artifact_hash,
        length_mm=100.0,
        width_mm=20.0,
        height_mm=10.0,
        free_end_area_mm2=200.0,
    )
    material = CantileverMaterialObservation(
        project_id=binding.project_id,
        source_revision=binding.source_revision,
        source_state_hash=binding.source_state_hash,
        definition_id=binding.definition_id,
        definition_hash=binding.definition_hash,
        geometry_artifact_id=binding.geometry_artifact_id,
        geometry_artifact_hash=binding.geometry_artifact_hash,
        material_identity="test-material",
        elastic_modulus_mpa=70000.0,
        poisson_ratio=0.33,
        material_assignment_id="MAT-1",
        elastic_modulus_source_identity="test",
        poisson_ratio_source_identity="test",
    )
    values = base.model_dump(mode="json")
    values.update(
        analytical_validation=analytical.model_dump(mode="json"),
        analytical_geometry_observation=geometry.model_dump(mode="json"),
        analytical_material_observation=material.model_dump(mode="json"),
        aggregate_provenance=StructuralPipelineProvenance(
            pipeline_identity="mechcad-structural-pipeline@1",
            geometry_provenance=base.execution_manifest.geometry_provider_provenance,
            mesh_provenance=provenance_from_identity(GMSH_IDENTITY),
            solver_provenance=provenance_from_identity(CALCULIX_IDENTITY),
            parser_provenance=base.result.parser_provenance,
        ).model_dump(mode="json"),
        semantic_hash="pending",
    )
    expected_payload = StructuralEvidencePayload.model_validate(values)
    return base, expected_payload, analytical, geometry, material


def test_f21_preextraction_path_a_observations_and_order(tmp_path, monkeypatch):
    import mechcad_harness.application as application_module
    from mechcad_harness.structural.validation import (
        cantilever_geometry_observation,
        cantilever_material_observation,
    )

    inputs = _analytical_observation_inputs(tmp_path)
    expected_geometry = cantilever_geometry_observation(
        inputs.request, inputs.definition, inputs.realization, inputs.region_map,
    )
    expected_material = cantilever_material_observation(inputs.request, inputs.definition)
    calls = _record_observation_construction(monkeypatch, application_module)
    captured = _configure_path_a_characterization(inputs.application, application_module, inputs, monkeypatch)

    validation, geometry, material = inputs.application._publish_structural_analytical_validation(
        execution_manifest=inputs.manifest,
        request=inputs.request,
        definition=inputs.definition,
        result=object(),
        verification=object(),
        analytical_policy=object(),
        mesh_artifact_bytes=b"mesh",
    )

    assert validation == "validation"
    _assert_observation_pair(geometry, material, expected_geometry, expected_material)
    _assert_observation_pair(
        captured["geometry_observation"],
        captured["material_observation"],
        expected_geometry,
        expected_material,
    )
    assert [call[0] for call in calls] == ["geometry", "material"]
    assert calls[0][1] == (
        inputs.request,
        inputs.definition,
        inputs.realization,
        inputs.region_map,
    )
    assert calls[1][1] == (inputs.request, inputs.definition)


def test_f21_preextraction_path_b_rebuilds_observations_and_ignores_forged_inputs(
    tmp_path, monkeypatch
):
    import mechcad_harness.application as application_module
    from mechcad_harness.structural.validation import (
        cantilever_geometry_observation,
        cantilever_material_observation,
    )

    inputs = _analytical_observation_inputs(tmp_path)
    expected_geometry = cantilever_geometry_observation(
        inputs.request, inputs.definition, inputs.realization, inputs.region_map,
    )
    expected_material = cantilever_material_observation(inputs.request, inputs.definition)
    calls = _record_observation_construction(monkeypatch, application_module)
    captured, result, evaluation, policy = _configure_path_b_characterization(
        inputs.application, application_module, inputs, monkeypatch,
    )
    evidence_dir = (
        inputs.application.state_manager.workspace
        / "projects"
        / inputs.application.project_id
        / "evidence"
    )
    evidence_before = tuple(sorted(path.name for path in evidence_dir.glob("*.json")))
    publication_calls = []
    monkeypatch.setattr(
        inputs.application._structural_evidence_publisher,
        "publish",
        lambda **kwargs: publication_calls.append(kwargs),
    )
    forged_geometry = expected_geometry.model_copy(update={"length_mm": 999.0})
    forged_material = expected_material.model_copy(update={"elastic_modulus_mpa": 999.0})

    validation = inputs.application.evaluate_structural_analytical_validation(
        execution_manifest=inputs.manifest,
        evaluation=evaluation,
        policy=policy,
        mesh=object(),
        geometry_observation=forged_geometry,
        material_observation=forged_material,
        request=inputs.request,
        definition=inputs.definition,
    )

    assert validation == "validation"
    _assert_observation_pair(
        captured["geometry_observation"],
        captured["material_observation"],
        expected_geometry,
        expected_material,
    )
    assert captured["geometry_observation"] != forged_geometry
    assert captured["material_observation"] != forged_material
    assert publication_calls == []
    assert tuple(sorted(path.name for path in evidence_dir.glob("*.json"))) == evidence_before
    assert [call[0] for call in calls] == ["geometry", "material"]
    assert calls[0][1] == (
        inputs.request,
        inputs.definition,
        inputs.realization,
        inputs.region_map,
    )
    assert calls[1][1] == (inputs.request, inputs.definition)


def test_f21_preextraction_path_a_translates_constructor_failure(tmp_path, monkeypatch):
    import mechcad_harness.application as application_module

    inputs = _analytical_observation_inputs(tmp_path)
    captured = _configure_path_a_characterization(
        inputs.application, application_module, inputs, monkeypatch,
    )
    sentinel = RuntimeError("geometry constructor sentinel")
    monkeypatch.setattr(
        application_module,
        "cantilever_geometry_observation",
        lambda *_args: (_ for _ in ()).throw(sentinel),
    )

    with pytest.raises(ValueError, match="trusted analytical source observations are unavailable") as raised:
        inputs.application._publish_structural_analytical_validation(
            execution_manifest=inputs.manifest,
            request=inputs.request,
            definition=inputs.definition,
            result=object(),
            verification=object(),
            analytical_policy=object(),
            mesh_artifact_bytes=b"mesh",
        )

    assert raised.value.__cause__ is sentinel
    assert captured == {}


def test_f21_preextraction_path_a_publisher_preserves_fixed_payload_hashes(
    tmp_path, monkeypatch
):
    from mechcad_harness.artifacts.storage import ArtifactStore
    from mechcad_harness.structural.evidence_service import StructuralEvidencePublisher
    from mechcad_harness.structural_request import StructuralAnalysisRequest
    import mechcad_harness.structural.evidence_service as evidence_service_module

    base, expected_payload, analytical, geometry, material = _fixed_f21_analytical_payload()
    written = []

    class RecordingEvidenceStore:
        def write_evidence(self, project_id, evidence):
            written.append((project_id, evidence))

    class FakeVerifier:
        def _load_bound_definition(self, request):
            return object()

        def _load_durable_manifest_for_publication(self, *args):
            return (
                base.execution_manifest,
                object(),
                b"manifest",
                SimpleNamespace(artifact_id="MANIFEST-1", sha256="sha256:" + "n" * 64),
            )

        def _verify_direct_manifest_provenance(self, manifest):
            return None

        def _verify_all_artifacts(self, store, request, definition, manifest):
            return {"msh": b"mesh"}

        def _reconstruct_result(self, request, definition, manifest):
            return base.result

        def _verify_result_and_criteria(self, *args):
            return None

        def _verify_analytical_validation(self, *args):
            return None

        def _verify_pipeline_provenance(self, *args):
            return None

    publisher = StructuralEvidencePublisher(
        workspace=tmp_path,
        project_id=base.request.source_binding.project_id,
        state_manager=object(),
        artifact_store=ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1"),
        evidence_store=RecordingEvidenceStore(),
        analytical_validation_factory=lambda **kwargs: (analytical, geometry, material),
    )
    monkeypatch.setattr(publisher, "_verifier", lambda: FakeVerifier())
    monkeypatch.setattr(
        publisher,
        "_fresh_verifier",
        lambda _run_id: SimpleNamespace(verify=lambda _evidence_id: None),
    )
    monkeypatch.setattr(
        evidence_service_module,
        "StructuralVerificationService",
        lambda: SimpleNamespace(evaluate=lambda _result, _definition: base.verification),
    )
    monkeypatch.setattr(StructuralAnalysisRequest, "validate_against", lambda self, definition: None)

    evidence = publisher.publish(
        execution_manifest=base.execution_manifest,
        request=base.request,
        analytical_policy=analytical.policy,
    )

    assert len(written) == 1
    assert written[0][0] == base.request.source_binding.project_id
    assert evidence.structural_evidence_payload.analytical_geometry_observation == (
        expected_payload.analytical_geometry_observation
    )
    assert evidence.structural_evidence_payload.analytical_material_observation == (
        expected_payload.analytical_material_observation
    )
    assert evidence.structural_evidence_payload.semantic_hash == (
        "sha256:d0f148f232ea27b0a7f2754921cbf7d2ad68cd6653c2a734c44f12e172e5a947"
    )
    assert evidence.output_hash == evidence.structural_evidence_payload.semantic_hash
    assert evidence.structural_evidence_payload.analytical_validation.validation_hash == (
        "sha256:437cbf1dc8bd630a26f10ab1def0135682bbd05bdd9bfdb6c51273ba87a1495f"
    )


def test_f21_preextraction_path_b_translates_constructor_failure(tmp_path, monkeypatch):
    import mechcad_harness.application as application_module

    inputs = _analytical_observation_inputs(tmp_path)
    captured, _result, evaluation, policy = _configure_path_b_characterization(
        inputs.application, application_module, inputs, monkeypatch,
    )
    sentinel = RuntimeError("geometry constructor sentinel")
    monkeypatch.setattr(
        application_module,
        "cantilever_geometry_observation",
        lambda *_args: (_ for _ in ()).throw(sentinel),
    )

    with pytest.raises(ValueError, match="trusted analytical source observations are unavailable") as raised:
        inputs.application.evaluate_structural_analytical_validation(
            execution_manifest=inputs.manifest,
            evaluation=evaluation,
            policy=policy,
            mesh=object(),
            geometry_observation=None,
            material_observation=None,
            request=inputs.request,
            definition=inputs.definition,
        )

    assert raised.value.__cause__ is sentinel
    assert captured == {}


def test_production_application_constructs_real_graph_without_invoking_adapter(tmp_path):
    from mechcad_harness.agents import AgentRegistry
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.runs import RunController
    from mechcad_harness.tools import ToolBroker

    adapter = CountingAdapter()
    application = build_application(tmp_path, adapter)

    assert isinstance(application.state_manager, StateManager)
    assert isinstance(application.run_controller, RunController)
    assert isinstance(application.agent_registry, AgentRegistry)
    assert isinstance(application.agent_gateway, AgentGateway)
    assert isinstance(application.tool_broker, ToolBroker)
    assert adapter.invocation_count == 0


def test_load_state_returns_exact_fresh_binding(tmp_path):
    application = build_application(tmp_path, CountingAdapter())

    first = application.load_state()
    second = application.load_state()

    assert first is not second
    assert (first.revision, first.state_hash) == (1, state_hash(first.state))
    assert second == first


def test_create_run_binds_authoritative_loaded_snapshot(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    source = application.load_state()

    binding = application.create_run()

    assert binding.source == source
    assert binding.run.initial_revision == source.revision
    assert binding.run.initial_state_hash == source.state_hash
    assert binding.run.active_revision == source.revision
    assert binding.run.active_state_hash == source.state_hash


def test_create_and_create_run_never_execute_adapter(tmp_path):
    adapter = CountingAdapter()
    application = build_application(tmp_path, adapter)

    application.create_run()

    assert adapter.invocation_count == 0


def test_production_bindings_are_immutable_and_validate_source(tmp_path):
    from mechcad_harness.application import ProductionRunBinding, ProductionStateBinding

    application = build_application(tmp_path, CountingAdapter())
    source = application.load_state()

    with pytest.raises((TypeError, ValueError)):
        source.revision = 2

    with pytest.raises(ValueError):
        ProductionStateBinding(
            project_id=source.project_id,
            state=source.state,
            revision=2,
            state_hash=source.state_hash,
        )

    run = application.run_controller.create_run(source.project_id)
    with pytest.raises(ValueError):
        ProductionRunBinding(run=run, source=source.model_copy(update={"revision": 2}))


def test_production_run_binding_returns_a_safe_nested_run_snapshot(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    binding = application.create_run()
    binding.run.active_revision = 2

    assert binding.run.active_revision == 1
    assert application.run_controller.get_run(binding.run.run_id, binding.run.project_id).active_revision == 1


def test_application_composed_dependencies_cannot_be_reassigned(tmp_path):
    application = build_application(tmp_path, CountingAdapter())

    for name in (
        "state_manager",
        "run_controller",
        "agent_registry",
        "agent_gateway",
        "tool_registry",
        "tool_broker",
        "evidence_store",
        "change_engine",
        "context_builder",
        "standard_tool_permissions",
    ):
        with pytest.raises(AttributeError):
            setattr(application, name, getattr(application, name))

    with pytest.raises(AttributeError):
        application.project_id = "PRJ-other"


def test_production_application_rejects_invalid_adapter_at_composition(tmp_path):
    from mechcad_harness.application import ProductionApplication

    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")

    with pytest.raises(ValueError):
        ProductionApplication.create(
            tmp_path / "workspace",
            "PRJ-production",
            object(),
            ownership_path=ownership,
            dependency_path=dependencies,
        )


def test_structural_analytical_attestation_rejects_replaced_nested_discovery(tmp_path, monkeypatch):
    from mechcad_harness.backends.provenance import provenance_from_identity
    from mechcad_harness.structural.models import (
        REGION_RESOLVER_IDENTITY,
        REGION_RESOLVER_VERSION,
    )
    from mechcad_harness.structural.runtime import DiscoveredRuntime, FREECAD_IDENTITY

    trusted_discovery = DiscoveredRuntime(
        available=True,
        executable="trusted-freecadcmd",
        version=FREECAD_IDENTITY.library_version,
        identity=FREECAD_IDENTITY,
        provenance=provenance_from_identity(FREECAD_IDENTITY),
    )
    monkeypatch.setattr("mechcad_harness.application.discover_freecad", lambda: trusted_discovery)

    application = build_application(tmp_path, CountingAdapter())
    adapter = application.structural_service.geometry_adapter
    original = adapter._discovery
    adapter._discovery = DiscoveredRuntime(
        available=original.available,
        executable=original.executable,
        version=original.version,
        identity=original.identity,
        provenance=original.provenance,
    )
    manifest = SimpleNamespace(
        geometry_provider_provenance=provenance_from_identity(FREECAD_IDENTITY),
        resolver_identity=REGION_RESOLVER_IDENTITY,
        resolver_version=REGION_RESOLVER_VERSION,
    )

    with pytest.raises(ValueError, match="composed structural geometry adapter"):
        application._assert_composed_structural_dependencies(manifest)


def test_structural_analytical_attestation_rejects_replaced_resolver_tolerances(tmp_path, monkeypatch):
    from dataclasses import replace
    from mechcad_harness.backends.provenance import provenance_from_identity
    from mechcad_harness.structural.models import (
        REGION_RESOLVER_IDENTITY,
        REGION_RESOLVER_VERSION,
    )
    from mechcad_harness.structural.runtime import DiscoveredRuntime, FREECAD_IDENTITY

    trusted_discovery = DiscoveredRuntime(
        available=True,
        executable="trusted-freecadcmd",
        version=FREECAD_IDENTITY.library_version,
        identity=FREECAD_IDENTITY,
        provenance=provenance_from_identity(FREECAD_IDENTITY),
    )
    monkeypatch.setattr("mechcad_harness.application.discover_freecad", lambda: trusted_discovery)

    application = build_application(tmp_path, CountingAdapter())
    resolver = application.structural_service.region_resolver
    resolver._tolerances = replace(resolver._tolerances)
    manifest = SimpleNamespace(
        geometry_provider_provenance=provenance_from_identity(FREECAD_IDENTITY),
        resolver_identity=REGION_RESOLVER_IDENTITY,
        resolver_version=REGION_RESOLVER_VERSION,
    )

    with pytest.raises(ValueError, match="composed structural region resolver"):
        application._assert_composed_structural_dependencies(manifest)


def test_structural_analytical_evaluation_rejects_unbound_source_step_metadata(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import mechcad_harness.application as application_module
    from mechcad_harness.artifacts.models import ArtifactType
    from mechcad_harness.artifacts.storage import ArtifactStore
    from mechcad_harness.backends.provenance import provenance_from_identity
    from mechcad_harness.structural.models import StructuralArtifactRef
    from mechcad_harness.structural.evidence_models import RectangularCantileverValidationPolicy
    from mechcad_harness.structural.results import StructuralAnalysisEvaluation
    from mechcad_harness.structural.runtime import FREECAD_IDENTITY

    application = build_application(tmp_path, CountingAdapter())
    source_binding_values = {
        "project_id": application.project_id,
        "source_revision": 1,
        "source_state_hash": application.load_state().state_hash,
        "definition_id": "DEF-1",
        "definition_hash": "sha256:" + "d" * 64,
        "target_body_id": "BODY-1",
        "source_program_hash": "sha256:" + "p" * 64,
        "geometry_identity": "freecad:body-1",
        "geometry_artifact_id": "STEP-1",
        "geometry_artifact_hash": "pending",
    }
    store = ArtifactStore(application.state_manager.workspace, project_id=application.project_id, run_id="RUN-1")
    source = store.publish(
        "STEP-1",
        ArtifactType.STEP,
        "source.step",
        b"ISO-10303-21;\nEND-ISO-10303-21;\n",
        "mechcad-freecad",
        FREECAD_IDENTITY.adapter_version,
        1,
        source_binding_values["source_state_hash"],
        backend_provenance=provenance_from_identity(FREECAD_IDENTITY),
    )
    source_binding_values["geometry_artifact_hash"] = source.sha256
    binding = SimpleNamespace(**source_binding_values)
    manifest = SimpleNamespace(
        run_id="RUN-1",
        project_id=application.project_id,
        revision=1,
        state_hash=source_binding_values["source_state_hash"],
        definition_id="DEF-1",
        definition_hash="sha256:" + "d" * 64,
        request_hash="request-hash",
        geometry_artifact_id=source.artifact_id,
        geometry_artifact_hash=source.sha256,
        geometry_provider_provenance=provenance_from_identity(FREECAD_IDENTITY),
        artifacts=(StructuralArtifactRef(
            artifact_type=ArtifactType.STEP.value,
            artifact_id=source.artifact_id,
            sha256=source.sha256,
            producer_identity=source.producer_tool_name,
            producer_version=source.producer_tool_version,
        ),),
    )
    request = SimpleNamespace(source_binding=binding, request_hash="request-hash")
    result = SimpleNamespace(result_hash="result-hash")
    monkeypatch.setattr(application, "_reload_structural_execution_manifest", lambda *_args: manifest)
    monkeypatch.setattr(application, "_assert_composed_structural_dependencies", lambda *_args: None)
    monkeypatch.setattr(application_module, "structural_result_hash", lambda _result: "result-hash")
    class FakeInterpreter:
        _is_trusted_freecad_provenance = staticmethod(lambda _provenance: True)

        def __init__(self, **_kwargs):
            pass

        def interpret(self, *_args, **_kwargs):
            return result

        def load_trusted_mesh(self, *_args, **_kwargs):
            return object(), b"mesh"

    monkeypatch.setattr(application_module, "StructuralResultInterpreter", FakeInterpreter)
    monkeypatch.setattr(application.structural_service.geometry_adapter, "realize_geometry", lambda _path: object())
    monkeypatch.setattr(application.structural_service.region_resolver, "resolve", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(application_module, "cantilever_geometry_observation", lambda *_args: object())
    monkeypatch.setattr(application_module, "cantilever_material_observation", lambda *_args: object())
    monkeypatch.setattr(
        application_module,
        "StructuralAnalyticalValidator",
        lambda: SimpleNamespace(validate=lambda *_args, **_kwargs: "validation"),
    )

    with pytest.raises(ValueError, match="source STEP artifact input binding"):
        application.evaluate_structural_analytical_validation(
            execution_manifest=manifest,
            evaluation=StructuralAnalysisEvaluation(result=result, verification=object()),
            policy=RectangularCantileverValidationPolicy(
                material_identity="MAT-1",
                length_mm=10.0,
                width_mm=2.0,
                height_mm=2.0,
                elastic_modulus_mpa=1000.0,
                poisson_ratio=0.3,
                resultant_force_n=(0.0, -1.0, 0.0),
                mesh_specification_hash="sha256:" + "m" * 64,
                free_end_region_id="free",
                fixed_end_region_id="fixed",
                free_end_area_mm2=4.0,
                displacement_relative_tolerance=0.1,
                reaction_relative_tolerance=0.1,
            ),
            mesh=object(),
            geometry_observation=None,
            material_observation=None,
            request=request,
            definition=SimpleNamespace(regions=()),
        )


def test_structural_evidence_publisher_rejects_replaced_analytical_factory(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import mechcad_harness.application as application_module
    from mechcad_harness.backends.provenance import provenance_from_identity
    from mechcad_harness.structural.models import REGION_RESOLVER_IDENTITY, REGION_RESOLVER_VERSION
    from mechcad_harness.structural.runtime import DiscoveredRuntime, FREECAD_IDENTITY

    trusted_discovery = DiscoveredRuntime(
        available=True,
        executable="trusted-freecadcmd",
        version=FREECAD_IDENTITY.library_version,
        identity=FREECAD_IDENTITY,
        provenance=provenance_from_identity(FREECAD_IDENTITY),
    )
    monkeypatch.setattr(application_module, "discover_freecad", lambda: trusted_discovery)

    application = build_application(tmp_path, CountingAdapter())
    application._structural_evidence_publisher.analytical_validation_factory = lambda **_kwargs: None
    manifest = SimpleNamespace(
        geometry_provider_provenance=provenance_from_identity(FREECAD_IDENTITY),
        resolver_identity=REGION_RESOLVER_IDENTITY,
        resolver_version=REGION_RESOLVER_VERSION,
    )

    with pytest.raises(ValueError, match="composed analytical validation factory"):
        application._assert_composed_structural_dependencies(manifest)


def test_production_run_binding_keeps_source_and_run_snapshot_after_state_advances(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    binding = application.create_run()
    original_source = binding.source
    original_run = binding.run

    application.state_manager.create_revision(
        "PRJ-production", make_state().model_copy(update={"revision": 2})
    )

    assert binding.source == original_source
    assert binding.run == original_run
    assert binding.source.revision == 1
    assert binding.run.active_revision == 1


def test_production_state_binding_rejects_blank_project_and_hash(tmp_path):
    from mechcad_harness.application import ProductionStateBinding

    source = build_application(tmp_path, CountingAdapter()).load_state()
    for field, value in (("project_id", " "), ("state_hash", "\t")):
        values = {
            "project_id": source.project_id,
            "state": source.state,
            "revision": source.revision,
            "state_hash": source.state_hash,
        }
        values[field] = value
        with pytest.raises(ValueError):
            ProductionStateBinding(**values)


def test_production_state_binding_returns_a_safe_nested_state_snapshot(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    source = application.load_state()
    source.state.components[0].name = "mutated"

    later = application.load_state()

    assert later.state.components[0].name == "Bracket"
    assert later.state_hash == state_hash(later.state)


def test_production_state_binding_accessor_returns_deep_copy_for_nested_state(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    binding = application.load_state()

    binding.state.components[0].name = "mutated"

    assert binding.state.components[0].name == "Bracket"


def test_application_exposes_composed_services_without_execution_api(tmp_path):
    from mechcad_harness.agents import ContextBuilder
    from mechcad_harness.changes import ChangeEngine
    from mechcad_harness.dependency import EvidenceStore

    application = build_application(tmp_path, CountingAdapter())

    assert isinstance(application.evidence_store, EvidenceStore)
    assert isinstance(application.change_engine, ChangeEngine)
    assert isinstance(application.context_builder, ContextBuilder)
    assert not set(dir(type(application))).intersection({
        "execute_task", "run_workflow", "invoke_agent", "start_run", "apply_change", "mutate_state",
    })


def test_application_exposes_structural_evidence_high_level_apis_without_tool_registration(tmp_path):
    application = build_application(tmp_path, CountingAdapter())

    assert callable(application.publish_structural_evidence)
    assert callable(application.verify_structural_evidence)
    assert callable(application.check_structural_evidence_currentness)
    assert not any("structural_evidence" in permission for permission in application.standard_tool_permissions)
    assert not any("structural_evidence" in registration.name for registration in BuiltinTools.registrations())


def test_application_composes_m12_5_promotion_services_as_read_only_dependencies(tmp_path):
    from mechcad_harness.candidates import (
        CandidatePromotionCompiler,
        CanonicalM10VerificationService,
        CanonicalPhysicalCadCompiler,
        CanonicalPhysicalMechanismCompiler,
        CanonicalM11HandoffService,
        PromotionManifestService,
    )

    application = build_application(tmp_path, CountingAdapter())

    assert isinstance(application.candidate_promotion_compiler, CandidatePromotionCompiler)
    assert isinstance(application.promotion_manifest_service, PromotionManifestService)
    assert isinstance(application.canonical_mechanism_compiler, CanonicalPhysicalMechanismCompiler)
    assert isinstance(application.canonical_cad_compiler, CanonicalPhysicalCadCompiler)
    assert isinstance(application.canonical_m10_service, CanonicalM10VerificationService)
    assert isinstance(application.m11_handoff_service, CanonicalM11HandoffService)
    assert callable(application.promoted_mechanism_verifier)

    for name in (
        "candidate_promotion_compiler",
        "promotion_manifest_service",
        "canonical_mechanism_compiler",
        "canonical_cad_compiler",
        "canonical_m10_service",
        "m11_handoff_service",
        "promoted_mechanism_verifier",
    ):
        with pytest.raises(AttributeError):
            setattr(application, name, getattr(application, name))


def test_application_passes_only_currentness_service_to_promotion_compiler(tmp_path, monkeypatch):
    import mechcad_harness.application as application_module

    real_compiler = application_module.CandidatePromotionCompiler
    received = {}

    def capture_compiler(*args, **kwargs):
        received.update(kwargs)
        return real_compiler(*args, **kwargs)

    monkeypatch.setattr(application_module, "CandidatePromotionCompiler", capture_compiler)
    application = build_application(tmp_path, CountingAdapter())

    assert received["evaluation_currentness_service"] is application.candidate_evaluation_currentness_service
    assert "cad_replay_verifier" not in received


def test_m12_5_application_methods_delegate_without_exposing_mutation_api(tmp_path, monkeypatch):
    from mechcad_harness.candidates import CandidateIntegrityError

    application = build_application(tmp_path, CountingAdapter())
    request = SimpleNamespace(project_id=application.project_id)
    state = object()
    compilation = object()
    reconstruction = object()
    verification = object()
    calls = []

    monkeypatch.setattr(application, "load_state", lambda: SimpleNamespace(state=state))
    monkeypatch.setattr(
        application.candidate_promotion_compiler,
        "compile",
        lambda supplied_state, supplied_request: calls.append(
            ("compile", supplied_state, supplied_request)
        )
        or compilation,
    )
    monkeypatch.setattr(
        application.promotion_application_service,
        "promote_selected_candidate",
        lambda supplied_request: calls.append(("promote", supplied_request)) or compilation,
    )
    monkeypatch.setattr(
        application.canonical_mechanism_compiler,
        "reconstruct",
        lambda project_id, revision, state_hash, mechanism_id: calls.append(
            ("reconstruct", project_id, revision, state_hash, mechanism_id)
        )
        or reconstruction,
    )
    monkeypatch.setattr(
        application.promoted_mechanism_verifier,
        "verify",
        lambda supplied_result: calls.append(("verify", supplied_result)) or verification,
    )

    assert application.compile_candidate_promotion(request) is compilation
    assert application.promote_selected_candidate(request) is compilation
    assert application.reconstruct_promoted_mechanism(
        revision=2,
        state_hash="sha256:" + "a" * 64,
        mechanism_id="PM-1",
    ) is reconstruction
    assert application.verify_promoted_mechanism(compilation) is verification
    assert [call[0] for call in calls] == ["compile", "promote", "reconstruct", "verify"]
    assert not set(dir(type(application))).intersection({"apply_change", "mutate_state"})

    foreign = SimpleNamespace(project_id="PRJ-foreign")
    for method, args in (
        (application.compile_candidate_promotion, (foreign,)),
        (application.promote_selected_candidate, (foreign,)),
    ):
        with pytest.raises(CandidateIntegrityError, match="project"):
            method(*args)
    with pytest.raises(CandidateIntegrityError, match="project"):
        application.reconstruct_promoted_mechanism(
            project_id="PRJ-foreign",
            revision=2,
            state_hash="sha256:" + "a" * 64,
            mechanism_id="PM-1",
        )


def test_promoted_verifier_context_binds_optional_m11_handoff_to_manifest_services(
    tmp_path, monkeypatch
):
    import mechcad_harness.application as application_module
    from mechcad_harness.application import _PromotionVerificationContext

    application = build_application(tmp_path, CountingAdapter())
    intent = SimpleNamespace(assessment_requested=True)
    reconstruction = object()
    handoff_request = object()
    assessment = object()
    application_result = SimpleNamespace(
        request=SimpleNamespace(
            project_id=application.project_id,
            m11_target_intent=intent,
        ),
        applied_revision=2,
        applied_state_hash="sha256:" + "a" * 64,
        compilation=SimpleNamespace(
            projection=SimpleNamespace(canonical_target_mechanism_id="PM-1")
        ),
    )
    calls = []
    context = _PromotionVerificationContext(application, application_result, object())

    monkeypatch.setattr(
        application.canonical_mechanism_compiler,
        "reconstruct",
        lambda *args: reconstruction,
    )
    monkeypatch.setattr(
        application_module,
        "build_handoff_request",
        lambda supplied_intent, supplied_context, supplied_reconstruction: calls.append(
            (supplied_intent, supplied_context, supplied_reconstruction)
        )
        or handoff_request,
    )
    monkeypatch.setattr(
        application.m11_handoff_service,
        "assess",
        lambda supplied_request: assessment,
    )

    assert context.m11_handoff is assessment
    assert calls == [(intent, context, reconstruction)]


def test_application_structural_evidence_apis_delegate_to_composed_services(tmp_path, monkeypatch):
    application = build_application(tmp_path, CountingAdapter())
    evidence = object()
    verification = object()
    currentness = object()
    repeatability = object()
    monkeypatch.setattr(application._structural_evidence_publisher, "publish", lambda **kwargs: evidence)
    monkeypatch.setattr(application._structural_evidence_verifier, "verify", lambda evidence_id: verification)
    monkeypatch.setattr(application._structural_evidence_verifier, "currentness", lambda evidence_id: currentness)
    monkeypatch.setattr(application._structural_repeatability_service, "compare", lambda **kwargs: repeatability)

    assert application.publish_structural_evidence(execution_manifest=object()) is evidence
    assert application.verify_structural_evidence("EVD-1") is verification
    assert application.check_structural_evidence_currentness("EVD-1") is currentness
    assert application.compare_structural_repeatability(
        policy=object(), first_evidence_id="EVD-1", second_evidence_id="EVD-2"
    ) is repeatability


def test_application_fails_closed_if_state_advances_after_load(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    original_load = application.load_state

    def load_then_advance():
        source = original_load()
        application.state_manager.create_revision("PRJ-production", make_state().model_copy(update={"revision": 2}))
        return source

    application.load_state = load_then_advance

    from mechcad_harness.runs.errors import RunIntegrityError
    with pytest.raises(RunIntegrityError):
        application.create_run()


def test_application_passes_typed_expected_source_to_controller(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    source = application.load_state()
    calls = []
    original = application.run_controller.create_run

    def create_run(project_id, *, max_iterations=3, expected_source=None):
        calls.append(expected_source)
        return original(project_id, max_iterations=max_iterations, expected_source=expected_source)

    application.run_controller.create_run = create_run
    application.create_run()

    assert isinstance(calls[0], SourceBinding)
    assert calls[0] == SourceBinding(project_id=source.project_id, revision=source.revision, state_hash=source.state_hash)


def test_injected_adapter_cannot_override_production_identity_or_role(tmp_path):
    adapter = CountingAdapter(AgentAdapterIdentity(adapter_name="forged", adapter_version="9.9"))
    application = build_application(tmp_path, adapter)

    assert application.agent_registry.get_identity("mechcad-transmission", "1.0") == AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )


def test_gateway_uses_registered_transmission_role_not_test_role(tmp_path):
    adapter = CountingAdapter()
    application = build_application(tmp_path, adapter)
    binding = application.create_run()
    task = TaskDefinition(
        task_id="TASK-role",
        run_id=binding.run.run_id,
        task_type="agent",
        objective="inspect",
        bound_revision=binding.run.active_revision,
        bound_state_hash=binding.run.active_state_hash,
    )
    application.run_controller.add_task(binding.run.run_id, task)

    result = application.agent_gateway.invoke(
        binding.run.run_id,
        task.task_id,
        "mechcad-transmission",
        "1.0",
    )
    identity = application.agent_registry.get_identity("mechcad-transmission", "1.0")

    assert identity.role == "transmission_engineer"
    assert identity.role != "test"
    assert adapter.requests[0].agent == identity
    assert (result.agent_name, result.agent_version) == (identity.agent_name, identity.agent_version)


def test_standard_tools_resolve_exact_versions_and_permissions_are_exact(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    registrations = BuiltinTools.registrations()

    assert application.standard_tool_permissions == tuple(
        f"{registration.name}@{registration.version}" for registration in registrations
    )
    for registration in registrations:
        resolved = application.tool_registry.resolve(registration.name, registration.version)
        assert (resolved.name, resolved.version) == (registration.name, registration.version)
        assert f"{registration.name}@{registration.version}" in application.standard_tool_permissions
        assert registration.name not in application.standard_tool_permissions


def test_real_tool_broker_rejects_bare_name_permission(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    run = application.run_controller.create_run(application.project_id)
    task = TaskDefinition(
        task_id="TASK-bare-permission",
        run_id=run.run_id,
        task_type="tool",
        objective="calculate",
        bound_revision=run.active_revision,
        bound_state_hash=run.active_state_hash,
        allowed_tools=("mechcad-calc-torque",),
    )
    application.run_controller.add_task(run.run_id, task)

    with pytest.raises(ToolPermissionError):
        application.tool_broker.execute(
            run.run_id,
            task.task_id,
            "mechcad-calc-torque",
            "1.0",
            {"force_n": 1, "lever_arm_m": 1, "safety_factor": 1},
        )


@pytest.mark.parametrize("bad_setup", ["missing_project", "missing_ownership", "missing_dependencies", "corrupt_current"])
def test_invalid_or_missing_state_and_configuration_fail_closed(tmp_path, bad_setup):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text("ownership:\n  - path: /components/*\n    owner: transmission_engineer\n", encoding="utf-8")
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")

    if bad_setup == "missing_ownership":
        ownership.unlink()
    elif bad_setup == "missing_dependencies":
        dependencies.unlink()
    elif bad_setup != "missing_project":
        StateManager(workspace).create_project("PRJ-production", make_state())
        if bad_setup == "corrupt_current":
            (workspace / "projects" / "PRJ-production" / "current.json").write_text("not-json\n", encoding="utf-8")

    from mechcad_harness.application import ProductionApplication

    if bad_setup in {"missing_ownership", "missing_dependencies"}:
        with pytest.raises(ValueError):
            ProductionApplication.create(workspace, "PRJ-production", CountingAdapter(), ownership_path=ownership, dependency_path=dependencies)
    else:
        application = ProductionApplication.create(workspace, "PRJ-production", CountingAdapter(), ownership_path=ownership, dependency_path=dependencies)
        with pytest.raises(RevisionNotFoundError if bad_setup == "missing_project" else StateIntegrityError):
            application.load_state()


def test_conflicting_standard_registration_fails_closed(tmp_path):
    from mechcad_harness.application import ProductionApplication

    (tmp_path / "ownership.yaml").write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    (tmp_path / "dependencies.yaml").write_text("rules: []\nedges: []\n", encoding="utf-8")
    standard = BuiltinTools.registrations()[0]
    with pytest.raises(ToolVersionError):
        ProductionApplication.create(
            tmp_path / "workspace",
            "PRJ-production",
            CountingAdapter(),
            ownership_path=tmp_path / "ownership.yaml",
            dependency_path=tmp_path / "dependencies.yaml",
            additional_tool_registrations=(standard,),
        )


def test_production_module_does_not_import_test_helpers():
    import mechcad_harness.application

    source = inspect.getsource(mechcad_harness.application)
    assert "tests." not in source
    assert "conftest" not in source


def test_application_delegates_structural_mesh_convergence(tmp_path, monkeypatch):
    from mechcad_harness.structural.evidence import StructuralMeshConvergenceStudy
    from mechcad_harness.structural_request import MeshSpecification

    application = build_application(tmp_path, CountingAdapter())
    study = StructuralMeshConvergenceStudy(
        policy_id="study@1",
        mesh_specifications=tuple(
            MeshSpecification(
                global_target_size_mm=size,
                quality_policy_id="quality@1",
                mesher_settings_version="gmsh-settings@1",
            )
            for size in (10.0, 7.5, 5.0)
        ),
        load_case_id="LC-1",
        relative_change_threshold=0.02,
        epsilon=1e-12,
        max_levels=3,
        required_runtime_identities=("freecad@1",),
    )
    expected = object()

    class RecordingService:
        def evaluate(self, **kwargs):
            self.kwargs = kwargs
            return expected

    service = RecordingService()
    monkeypatch.setattr(application._structural_mesh_convergence_service, "evaluate", service.evaluate)

    result = application.evaluate_structural_mesh_convergence(
        study=study,
        level_evidence_ids=("EVD-1", "EVD-2", "EVD-3"),
    )

    assert result is expected
    assert service.kwargs == {
        "study": study,
        "level_evidence_ids": ("EVD-1", "EVD-2", "EVD-3"),
    }


def test_application_delegates_structural_mesh_convergence_publication(tmp_path, monkeypatch):
    application = build_application(tmp_path, CountingAdapter())
    expected = object()
    calls = []

    def publish(**kwargs):
        calls.append(kwargs)
        return expected

    monkeypatch.setattr(application._structural_mesh_convergence_service, "publish", publish)

    study = object()
    result = application.publish_structural_mesh_convergence(
        study=study,
        level_evidence_ids=("EVD-1", "EVD-2", "EVD-3"),
    )

    assert result is expected
    assert calls == [{
        "study": study,
        "level_evidence_ids": ("EVD-1", "EVD-2", "EVD-3"),
    }]


def test_analytical_publication_rejects_replaced_structural_dependencies(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import mechcad_harness.application as application_module
    from mechcad_harness.artifacts.models import ArtifactType
    from mechcad_harness.artifacts.storage import ArtifactStore
    from mechcad_harness.backends.provenance import provenance_from_identity
    from mechcad_harness.structural.models import REGION_RESOLVER_IDENTITY
    from mechcad_harness.structural.runtime import FREECAD_IDENTITY

    application = build_application(tmp_path, CountingAdapter())
    trusted_provenance = provenance_from_identity(FREECAD_IDENTITY)
    source = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id="RUN-1",
    ).publish(
        "STEP-ANALYTICAL-TEST",
        ArtifactType.STEP,
        "source.step",
        b"ISO-10303-21;\nEND-ISO-10303-21;\n",
        "mechcad-freecad",
        FREECAD_IDENTITY.adapter_version,
        1,
        application.load_state().state_hash,
        backend_provenance=trusted_provenance,
    )
    request = SimpleNamespace(
        source_binding=SimpleNamespace(
            geometry_artifact_id=source.artifact_id,
            geometry_artifact_hash=source.sha256,
        )
    )
    manifest = SimpleNamespace(
        run_id="RUN-1",
        geometry_provider_provenance=trusted_provenance,
        resolver_identity=REGION_RESOLVER_IDENTITY,
        resolver_version="1",
    )

    class ReplacedGeometryAdapter:
        _discovery = SimpleNamespace(provenance=trusted_provenance)

        def realize_geometry(self, _source_path):
            return object()

    class ReplacedRegionResolver:
        identity = REGION_RESOLVER_IDENTITY
        resolver_version = "1"

        def resolve(self, *_args, **_kwargs):
            return object()

    application.structural_service.geometry_adapter = ReplacedGeometryAdapter()
    application.structural_service.region_resolver = ReplacedRegionResolver()
    monkeypatch.setattr(application_module, "parse_trusted_msh_bytes", lambda _bytes: object())
    monkeypatch.setattr(application_module, "cantilever_geometry_observation", lambda *_args: object())
    monkeypatch.setattr(application_module, "cantilever_material_observation", lambda *_args: object())
    monkeypatch.setattr(
        application_module,
        "StructuralAnalyticalValidator",
        lambda: SimpleNamespace(validate=lambda *_args, **_kwargs: "validation"),
    )

    with pytest.raises(ValueError, match="trusted analytical source observations are unavailable"):
        application._publish_structural_analytical_validation(
            execution_manifest=manifest,
            request=request,
            definition=SimpleNamespace(regions=()),
            result=object(),
            verification=object(),
            analytical_policy=object(),
            mesh_artifact_bytes=b"mesh",
        )


def test_analytical_evaluation_rejects_replaced_nested_structural_dependencies(
    tmp_path, monkeypatch
):
    import mechcad_harness.application as application_module
    from mechcad_harness.backends.provenance import provenance_from_identity
    from mechcad_harness.structural.evidence_models import RectangularCantileverValidationPolicy
    from mechcad_harness.structural.models import REGION_RESOLVER_IDENTITY, REGION_RESOLVER_VERSION
    from mechcad_harness.structural.results import StructuralAnalysisEvaluation
    from mechcad_harness.structural.runtime import FREECAD_IDENTITY

    application = build_application(tmp_path, CountingAdapter())
    trusted_provenance = provenance_from_identity(FREECAD_IDENTITY)
    manifest = SimpleNamespace(
        geometry_provider_provenance=trusted_provenance,
        resolver_identity=REGION_RESOLVER_IDENTITY,
        resolver_version=REGION_RESOLVER_VERSION,
    )
    request = SimpleNamespace(request_hash="request-hash")
    policy = RectangularCantileverValidationPolicy(
        material_identity="MAT-1",
        length_mm=10.0,
        width_mm=2.0,
        height_mm=2.0,
        elastic_modulus_mpa=1000.0,
        poisson_ratio=0.3,
        resultant_force_n=(0.0, -1.0, 0.0),
        mesh_specification_hash="mesh-spec",
        free_end_region_id="free",
        fixed_end_region_id="fixed",
        free_end_area_mm2=4.0,
        displacement_relative_tolerance=0.1,
        reaction_relative_tolerance=0.1,
    )
    evaluation = StructuralAnalysisEvaluation(result=object(), verification=object())

    class ReplacedGeometryAdapter:
        _discovery = SimpleNamespace(provenance=trusted_provenance)

        def realize_geometry(self, _source_path):
            raise AssertionError("replaced geometry adapter was invoked")

    class ReplacedRegionResolver:
        identity = REGION_RESOLVER_IDENTITY
        resolver_version = REGION_RESOLVER_VERSION

        def resolve(self, *_args, **_kwargs):
            raise AssertionError("replaced region resolver was invoked")

    application.structural_service.geometry_adapter = ReplacedGeometryAdapter()
    application.structural_service.region_resolver = ReplacedRegionResolver()
    monkeypatch.setattr(application, "_reload_structural_execution_manifest", lambda *_args: manifest)
    monkeypatch.setattr(application_module, "StructuralResultInterpreter", lambda **_kwargs: pytest.fail("interpreter invoked"))

    with pytest.raises(ValueError, match="composed structural"):
        application.evaluate_structural_analytical_validation(
            execution_manifest=manifest,
            evaluation=evaluation,
            policy=policy,
            mesh=object(),
            geometry_observation=None,
            material_observation=None,
            request=request,
            definition=SimpleNamespace(regions=()),
        )
