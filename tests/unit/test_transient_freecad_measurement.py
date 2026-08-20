import pytest

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, assembly_hash
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider


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
