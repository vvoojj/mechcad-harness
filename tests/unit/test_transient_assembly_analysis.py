import pytest

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, assembly_hash
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest, TransientAssemblyAnalysisService


def _assembly():
    return CadAssemblyProgram(
        assembly_id="transient",
        parts=(
            CadPartProgram(part_id="moving", operations=(BasePlateOperation(operation_id="moving", length_mm=1, width_mm=1, thickness_mm=1),)),
            CadPartProgram(part_id="stationary", operations=(BasePlateOperation(operation_id="stationary", length_mm=1, width_mm=1, thickness_mm=1),)),
        ),
        instances=(CadComponentInstance(instance_id="moving", part_id="moving"), CadComponentInstance(instance_id="stationary", part_id="stationary")),
    )


def test_transient_analysis_binds_source_and_transformed_hashes_and_preserves_pair_order():
    assembly = _assembly()
    source_hash = assembly_hash(assembly)
    request = TransientAssemblyAnalysisRequest(
        source_assembly_hash=source_hash,
        transformed_assembly_hash=source_hash,
        sweep_request_hash="sha256:request",
        sample_angle_deg=90,
        pairs=(("moving", "stationary"),),
    )
    calls = []

    def exact_measure(received_request, program):
        calls.append((received_request, program))
        return (("moving", "stationary", 3.0, 0.0),)

    result = TransientAssemblyAnalysisService(exact_measure).analyze(request, assembly)
    assert calls == [(request, assembly)]
    assert result.measurements == (("moving", "stationary", 3.0, 0.0),)


def test_transient_analysis_preserves_optional_opaque_sample_marker():
    assembly = _assembly()
    identity = assembly_hash(assembly)
    request = TransientAssemblyAnalysisRequest(
        source_assembly_hash=identity,
        transformed_assembly_hash=identity,
        sweep_request_hash="sha256:request",
        sample_angle_deg=None,
        sample_id="opaque-sample",
        pairs=(("moving", "stationary"),),
    )

    result = TransientAssemblyAnalysisService(
        lambda received_request, program: (("moving", "stationary", 0.0, 1.0),)
    ).analyze(request, assembly)

    assert result.sample_angle_deg is None
    assert result.sample_id == "opaque-sample"


def test_transient_analysis_fails_closed_for_hash_or_pair_mismatch():
    assembly = _assembly()
    source_hash = assembly_hash(assembly)
    base = dict(source_assembly_hash=source_hash, transformed_assembly_hash=source_hash, sweep_request_hash="sha256:request", sample_angle_deg=0, pairs=(("moving", "stationary"),))
    service = TransientAssemblyAnalysisService(lambda request, program: (("moving", "stationary", 0.0, 1.0),))
    with pytest.raises(ValueError, match="transformed assembly hash mismatch"):
        service.analyze(TransientAssemblyAnalysisRequest(**(base | {"transformed_assembly_hash": "sha256:wrong"})), assembly)
    with pytest.raises(ValueError, match="measurement pairs"):
        TransientAssemblyAnalysisService(lambda request, program: (("stationary", "moving", 0.0, 1.0),)).analyze(TransientAssemblyAnalysisRequest(**base), assembly)


def test_transient_analysis_preserves_distinct_source_provenance_for_transformed_program():
    assembly = _assembly().model_copy(update={"assembly_id": "transient_sweep_90"})
    request = TransientAssemblyAnalysisRequest(
        source_assembly_hash="sha256:source",
        transformed_assembly_hash=assembly_hash(assembly),
        sweep_request_hash="sha256:request",
        sample_angle_deg=90,
        pairs=(("moving", "stationary"),),
    )

    result = TransientAssemblyAnalysisService(
        lambda received_request, program: (("moving", "stationary", 0.0, 1.0),)
    ).analyze(request, assembly)

    assert result.source_assembly_hash == "sha256:source"
    assert result.transformed_assembly_hash == assembly_hash(assembly)
