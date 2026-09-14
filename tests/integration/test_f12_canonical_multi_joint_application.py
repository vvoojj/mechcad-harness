from __future__ import annotations

import inspect

import pytest

from mechcad_harness.application import ProductionApplication
from mechcad_harness.candidates import CandidateIntegrityError

from test_m13_4p_production_composition import _completed_receipt


def test_public_entrypoint_replays_one_captured_canonical_snapshot(tmp_path, monkeypatch):
    application, receipt = _completed_receipt(tmp_path)
    mechanism_id = receipt.compilation.projection.canonical_target_mechanism_id
    expected = application.load_state()
    load_calls = []
    reconstruction_calls = []
    cad_calls = []
    service_calls = []

    original_load_state = application.load_state
    original_reconstruct = application.reconstruct_promoted_mechanism
    original_realize = application.canonical_cad_compiler.realize
    original_execute = application.canonical_multi_joint_m10_verification_service.execute

    def observe_load_state():
        load_calls.append(True)
        return original_load_state()

    def observe_reconstruct(**kwargs):
        reconstruction_calls.append(kwargs)
        return original_reconstruct(**kwargs)

    def observe_realize(reconstruction):
        cad = original_realize(reconstruction)
        cad_calls.append((reconstruction, cad))
        return cad

    def observe_execute(reconstruction, cad):
        service_calls.append((reconstruction, cad))
        return original_execute(reconstruction, cad)

    monkeypatch.setattr(application, "load_state", observe_load_state)
    monkeypatch.setattr(application, "reconstruct_promoted_mechanism", observe_reconstruct)
    monkeypatch.setattr(application.canonical_cad_compiler, "realize", observe_realize)
    monkeypatch.setattr(
        application.canonical_multi_joint_m10_verification_service,
        "execute",
        observe_execute,
    )

    verification = application.verify_current_canonical_multi_joint_m10(
        mechanism_id=mechanism_id,
    )

    assert len(load_calls) == 1
    assert reconstruction_calls == [
        {
            "revision": expected.revision,
            "state_hash": expected.state_hash,
            "mechanism_id": mechanism_id,
        }
    ]
    reconstruction = service_calls[0][0]
    assert cad_calls == [(reconstruction, service_calls[0][1])]
    assert verification.project_id == expected.project_id
    assert verification.revision == expected.revision
    assert verification.state_hash == expected.state_hash
    assert verification.mechanism_id == mechanism_id
    assert verification.result.request_hash == verification.request.request_hash
    assert application.get_multi_joint_collision_sweep_evidence(
        verification.result.result_hash
    ) is not None


@pytest.mark.parametrize("mechanism_id", ["", "missing-mechanism"])
def test_public_entrypoint_rejects_invalid_selector_before_m10(tmp_path, mechanism_id, monkeypatch):
    application, _ = _completed_receipt(tmp_path)
    execute_calls = []
    monkeypatch.setattr(
        application.canonical_multi_joint_m10_verification_service,
        "execute",
        lambda *args: execute_calls.append(args),
    )

    with pytest.raises((CandidateIntegrityError, ValueError)):
        application.verify_current_canonical_multi_joint_m10(mechanism_id=mechanism_id)

    assert execute_calls == []


def test_public_entrypoint_rejects_ambiguous_selector_before_m10(tmp_path, monkeypatch):
    application, _ = _completed_receipt(tmp_path)
    execute_calls = []

    def ambiguous_reconstruction(**kwargs):
        raise ValueError("canonical mechanism is missing or ambiguous")

    monkeypatch.setattr(
        application,
        "reconstruct_promoted_mechanism",
        ambiguous_reconstruction,
    )
    monkeypatch.setattr(
        application.canonical_multi_joint_m10_verification_service,
        "execute",
        lambda *args: execute_calls.append(args),
    )

    with pytest.raises(ValueError, match="ambiguous"):
        application.verify_current_canonical_multi_joint_m10(
            mechanism_id="ambiguous-mechanism",
        )

    assert execute_calls == []


def test_public_entrypoint_is_current_only_and_candidate_free():
    parameters = inspect.signature(
        ProductionApplication.verify_current_canonical_multi_joint_m10
    ).parameters

    assert tuple(parameters) == ("self", "mechanism_id")
    assert parameters["mechanism_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert not any("candidate" in name for name in parameters)
    assert not any(name in parameters for name in ("revision", "state_hash"))


def test_public_entrypoint_does_not_reload_or_retry_when_current_pointer_advances(
    tmp_path, monkeypatch
):
    application, receipt = _completed_receipt(tmp_path)
    mechanism_id = receipt.compilation.projection.canonical_target_mechanism_id
    expected = application.load_state()
    load_calls = []
    reconstruct_calls = []
    execute_calls = []
    original_load_state = application.load_state
    original_reconstruct = application.reconstruct_promoted_mechanism
    original_execute = application.canonical_multi_joint_m10_verification_service.execute

    def observe_load_state():
        load_calls.append(True)
        return original_load_state()

    def advance_then_reconstruct(**kwargs):
        reconstruct_calls.append(kwargs)
        application.state_manager.create_revision(
            application.project_id,
            application.state_manager.load_current_state(application.project_id),
        )
        return original_reconstruct(**kwargs)

    def observe_execute(reconstruction, cad):
        execute_calls.append((reconstruction, cad))
        return original_execute(reconstruction, cad)

    monkeypatch.setattr(application, "load_state", observe_load_state)
    monkeypatch.setattr(
        application,
        "reconstruct_promoted_mechanism",
        advance_then_reconstruct,
    )
    monkeypatch.setattr(
        application.canonical_multi_joint_m10_verification_service,
        "execute",
        observe_execute,
    )

    verification = application.verify_current_canonical_multi_joint_m10(
        mechanism_id=mechanism_id,
    )

    assert len(load_calls) == 1
    assert len(reconstruct_calls) == 1
    assert len(execute_calls) == 1
    assert reconstruct_calls[0]["revision"] == expected.revision
    assert reconstruct_calls[0]["state_hash"] == expected.state_hash
    assert verification.revision == expected.revision
    assert verification.state_hash == expected.state_hash


def test_promotion_does_not_auto_invoke_public_canonical_replay(tmp_path, monkeypatch):
    calls = []
    original = ProductionApplication.verify_current_canonical_multi_joint_m10

    def observe(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        ProductionApplication,
        "verify_current_canonical_multi_joint_m10",
        observe,
    )

    _completed_receipt(tmp_path)

    assert calls == []


def test_public_entrypoint_preserves_m10_v2_and_evidence_identity(tmp_path):
    application, receipt = _completed_receipt(tmp_path)
    mechanism_id = receipt.compilation.projection.canonical_target_mechanism_id
    snapshot = application.load_state()
    direct_reconstruction = application.reconstruct_promoted_mechanism(
        revision=snapshot.revision,
        state_hash=snapshot.state_hash,
        mechanism_id=mechanism_id,
    )
    direct_cad = application.canonical_cad_compiler.realize(direct_reconstruction)
    direct = application.canonical_multi_joint_m10_verification_service.execute(
        direct_reconstruction,
        direct_cad,
    )
    direct_evidence = application.get_multi_joint_collision_sweep_evidence(
        direct.result.result_hash
    )

    public = application.verify_current_canonical_multi_joint_m10(
        mechanism_id=mechanism_id,
    )
    public_evidence = application.get_multi_joint_collision_sweep_evidence(
        public.result.result_hash
    )

    assert public.request.request_hash == direct.request.request_hash
    assert public.result.result_hash == direct.result.result_hash
    assert public.request.source_assembly_hash == direct.request.source_assembly_hash
    assert public.request.model_hash == direct.request.model_hash
    assert public.request.evaluator_version == direct.request.evaluator_version
    assert public.result.source_assembly_hash == direct.result.source_assembly_hash
    assert public.result.model_hash == direct.result.model_hash
    assert public.result.evaluator_version == direct.result.evaluator_version
    assert direct_evidence is not None
    assert public_evidence is not None
    assert public_evidence.input_hash == direct_evidence.input_hash
    assert public_evidence.output_hash == direct_evidence.output_hash
    assert public_evidence.analysis_execution_provenance == (
        direct_evidence.analysis_execution_provenance
    )
    assert public.request.request_hash != receipt.request.multi_joint_request.m10_v2_request_hash
