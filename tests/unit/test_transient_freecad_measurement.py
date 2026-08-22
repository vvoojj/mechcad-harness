import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, assembly_hash
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.imported_component import ImportedCadComponent
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider


def _publish_step(workspace, project_id, run_id, artifact_id, content=b"STEP-BYTES", artifact_type=ArtifactType.STEP):
    store = ArtifactStore(workspace, project_id=project_id, run_id=run_id)
    return store.publish(
        artifact_id,
        artifact_type,
        f"{artifact_id}.{artifact_type.value}",
        content,
        "producer",
        "1.0",
        1,
        "sha256:" + "a" * 64,
    )


def _imported(artifact_id, artifact_hash):
    return ImportedCadComponent(
        component_id="c1",
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        format="step",
        source_revision=1,
        source_state_hash="sha256:" + "b" * 64,
    )


def _assembly():
    return CadAssemblyProgram(
        assembly_id="transient-provider",
        parts=(
            CadPartProgram(part_id="moving", operations=(BasePlateOperation(operation_id="moving", length_mm=1, width_mm=1, thickness_mm=1),)),
            CadPartProgram(part_id="stationary", operations=(BasePlateOperation(operation_id="stationary", length_mm=1, width_mm=1, thickness_mm=1),)),
        ),
        instances=(CadComponentInstance(instance_id="moving", part_id="moving"), CadComponentInstance(instance_id="stationary", part_id="stationary")),
    )


def _request(program):
    identity = assembly_hash(program)
    return TransientAssemblyAnalysisRequest(
        source_assembly_hash=identity,
        transformed_assembly_hash=identity,
        sweep_request_hash="sha256:request",
        sample_angle_deg=90,
        pairs=(("moving", "stationary"),),
    )


def test_provider_validates_transformed_program_identity_before_execution():
    program = _assembly()
    called = False

    def execute(request, transformed):
        nonlocal called
        called = True
        return (("moving", "stationary", 0.0, 1.0),)

    provider = FreeCADTransientAssemblyMeasurementProvider(execute=execute)
    request = _request(program).model_copy(update={"transformed_assembly_hash": "sha256:wrong"})
    with pytest.raises(ValueError, match="transformed assembly hash mismatch"):
        provider.exact_measure(request, program)
    assert not called


def test_provider_preserves_order_and_propagates_exact_measurements():
    program = _assembly()
    request = _request(program)
    calls = []

    def execute(received_request, transformed):
        calls.append((received_request, transformed))
        return (("moving", "stationary", 2.5, 0.25),)

    result = FreeCADTransientAssemblyMeasurementProvider(execute=execute).exact_measure(request, program)
    assert calls == [(request, program)]
    assert result == (("moving", "stationary", 2.5, 0.25),)


def test_provider_rejects_wrong_measurement_pair_order():
    program = _assembly()
    request = _request(program)
    provider = FreeCADTransientAssemblyMeasurementProvider(execute=lambda request, transformed: (("stationary", "moving", 0.0, 1.0),))
    with pytest.raises(ValueError, match="measurement pairs"):
        provider.exact_measure(request, program)


def test_provider_uses_temporary_workspace_without_artifact_store(monkeypatch):
    program = _assembly()
    request = _request(program)
    workspaces = []

    def execute_in_workspace(received_request, transformed, workspace):
        workspaces.append((received_request, transformed, workspace))
        assert workspace.name.startswith("mechcad-transient-measure-")
        return (("moving", "stationary", 0.0, 1.0),)

    provider = FreeCADTransientAssemblyMeasurementProvider(execute_in_workspace=execute_in_workspace)
    assert provider.exact_measure(request, program) == (("moving", "stationary", 0.0, 1.0),)
    assert [(received_request, transformed) for received_request, transformed, _ in workspaces] == [(request, program)]
    assert not hasattr(provider, "artifact_store")


def test_artifact_store_existing_in_project_resolves_single_and_fails_closed(tmp_path):
    from mechcad_harness.artifacts.storage import ArtifactStore as _Store

    artifact = _publish_step(tmp_path, "PRJ-X", "RUN-1", "ART-single")
    store = _Store(tmp_path, project_id="PRJ-X", run_id="RUN-1")
    resolved = store.existing_in_project("ART-single")
    assert resolved is not None
    assert resolved.artifact_id == "ART-single"
    assert store.existing_in_project("ART-missing") is None

    # Ambiguous: same artifact_id published under two runs -> fails closed.
    _publish_step(tmp_path, "PRJ-X", "RUN-2", "ART-single")
    assert store.existing_in_project("ART-single") is None


def test_provider_resolves_imported_artifact_through_trusted_store(tmp_path):
    artifact = _publish_step(tmp_path, "PRJ-X", "RUN-1", "ART-resolve")
    provider = FreeCADTransientAssemblyMeasurementProvider(workspace=tmp_path, project_id="PRJ-X")
    path = provider._resolve_imported_artifact_path(_imported(artifact.artifact_id, artifact.sha256))
    assert path.is_file()
    assert path.read_bytes() == b"STEP-BYTES"


def test_provider_rejects_imported_artifact_when_store_missing(tmp_path):
    provider = FreeCADTransientAssemblyMeasurementProvider(workspace=tmp_path, project_id="PRJ-X")
    with pytest.raises(Exception, match="imported artifact not found"):
        provider._resolve_imported_artifact_path(_imported("ART-absent", "sha256:" + "0" * 64))


def test_provider_rejects_imported_artifact_hash_mismatch(tmp_path):
    artifact = _publish_step(tmp_path, "PRJ-X", "RUN-1", "ART-hash")
    provider = FreeCADTransientAssemblyMeasurementProvider(workspace=tmp_path, project_id="PRJ-X")
    with pytest.raises(Exception, match="hash mismatch"):
        provider._resolve_imported_artifact_path(_imported(artifact.artifact_id, "sha256:" + "f" * 64))


def test_provider_rejects_non_step_imported_artifact(tmp_path):
    artifact = _publish_step(tmp_path, "PRJ-X", "RUN-1", "ART-json", content=b"{}", artifact_type=ArtifactType.JSON)
    provider = FreeCADTransientAssemblyMeasurementProvider(workspace=tmp_path, project_id="PRJ-X")
    with pytest.raises(Exception, match="not a STEP"):
        provider._resolve_imported_artifact_path(_imported(artifact.artifact_id, artifact.sha256))


def test_provider_requires_workspace_scope_for_imported_resolution():
    provider = FreeCADTransientAssemblyMeasurementProvider()
    with pytest.raises(Exception, match="requires workspace and project_id"):
        provider._resolve_imported_artifact_path(_imported("ART-scope", "sha256:" + "0" * 64))
