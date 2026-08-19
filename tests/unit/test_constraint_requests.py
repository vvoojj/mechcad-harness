import json

import pytest


def _state(requirement_ids=(), constraint_ids=()):
    from mechcad_harness.models import Constraint, DesignState, Requirement

    return DesignState(
        id="DES-1",
        revision=3,
        requirements=[Requirement(id=item, name=item, description=item) for item in requirement_ids],
        constraints=[Constraint(id=item, name=item, expression=item) for item in constraint_ids],
    )


def _draft(key, description="missing", rationale="needed"):
    from mechcad_harness.agents.constraint_requests import AgentConstraintRequestDraft

    return AgentConstraintRequestDraft(key=key, description=description, rationale=rationale)


def test_supported_constraint_key_registry_is_exactly_four_values():
    from mechcad_harness.agents.constraint_requests import SupportedConstraintKey

    assert {item.value for item in SupportedConstraintKey} == {
        "transmission.output_angular_speed",
        "transmission.motor_characteristics",
        "transmission.output_interface",
        "transmission.packaging_envelope",
    }
    assert len(SupportedConstraintKey) == 4


def test_semantic_identity_contains_key_and_excludes_wording_and_provenance():
    from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer, SupportedConstraintKey

    materializer = ConstraintRequestMaterializer()
    common = dict(project_id="PRJ", engineering_scope_id="transmission", bound_revision=3, bound_state_hash="sha256:state")
    ids = [materializer.request_id(**common, draft=_draft(key)) for key in SupportedConstraintKey]
    assert len(set(ids)) == 4
    key = SupportedConstraintKey.OUTPUT_INTERFACE
    assert materializer.request_id(**common, draft=_draft(key, "one", "why")) == materializer.request_id(**common, draft=_draft(key, "two", "other"))
    assert materializer.request_id(**common, draft=_draft(key)) != materializer.request_id(**{**common, "engineering_scope_id": "pan-transmission"}, draft=_draft(key))
    assert materializer.request_id(**common, draft=_draft(key)) != materializer.request_id(**{**common, "bound_revision": 4}, draft=_draft(key))
    assert materializer.request_id(**common, draft=_draft(key)) != materializer.request_id(**{**common, "bound_state_hash": "sha256:other"}, draft=_draft(key))


def test_satisfaction_uses_exact_trusted_anchors_only():
    from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer, SupportedConstraintKey

    materializer = ConstraintRequestMaterializer()
    state = _state(requirement_ids=("REQ-TRANSMISSION-OUTPUT-SPEED",), constraint_ids=("CON-TRANSMISSION-OUTPUT-INTERFACE",))
    assert not materializer.is_satisfied(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, state)
    assert not materializer.is_satisfied(SupportedConstraintKey.MOTOR_CHARACTERISTICS, state)
    assert not materializer.is_satisfied(SupportedConstraintKey.OUTPUT_INTERFACE, state)
    assert not materializer.is_satisfied(SupportedConstraintKey.PACKAGING_ENVELOPE, state)
    text_only = _state(requirement_ids=("REQ-OTHER",))
    assert not materializer.is_satisfied(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, text_only)


def test_satisfaction_requires_exact_authoritative_parameter_and_fails_closed_on_corruption():
    from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer, SupportedConstraintKey
    from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter, OutputAngularSpeedValue
    from mechcad_harness.models import DesignState

    materializer = ConstraintRequestMaterializer()
    anchor = _state(requirement_ids=("REQ-TRANSMISSION-OUTPUT-SPEED",))
    parameter = AuthoritativeParameter(id="PARAM-1", anchor=AuthoritativeAnchor(kind="requirement", id="REQ-TRANSMISSION-OUTPUT-SPEED"), scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, value=OutputAngularSpeedValue(kind=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED.value, value_rad_s=1), source_resolution_id="CRRES-1")
    assert not materializer.is_satisfied(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, anchor)
    assert materializer.is_satisfied(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, anchor.model_copy(update={"authoritative_parameters": [parameter]}))
    assert not materializer.is_satisfied(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, anchor.model_copy(update={"authoritative_parameters": [parameter.model_copy(update={"scope_id": "other"})]}))
    with pytest.raises(ValueError):
        materializer.is_satisfied(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, _state().model_copy(update={"authoritative_parameters": [parameter]}))
    assert not materializer.is_satisfied(SupportedConstraintKey.MOTOR_CHARACTERISTICS, anchor.model_copy(update={"authoritative_parameters": [parameter]}))
    duplicate = parameter.model_copy(update={"id": "PARAM-2"})
    with pytest.raises(ValueError):
        materializer.is_satisfied(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, anchor.model_copy(update={"authoritative_parameters": [parameter, duplicate]}))


def test_materializer_persists_and_reuses_semantic_request(tmp_path):
    from datetime import datetime, timezone
    from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer, ConstraintRequestStore, SupportedConstraintKey

    store = ConstraintRequestStore(tmp_path)
    materializer = ConstraintRequestMaterializer(store)
    source_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    kwargs = dict(project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", bound_revision=3, bound_state_hash="sha256:state", source_created_at=source_time)
    first = materializer.materialize(state=_state(), drafts=(_draft(SupportedConstraintKey.OUTPUT_INTERFACE),), **kwargs)
    second = materializer.materialize(state=_state(), drafts=(_draft(SupportedConstraintKey.OUTPUT_INTERFACE, "different", "different"),), **kwargs)
    assert first[0].request.id == second[0].request.id
    assert len(list((tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "agents" / "constraint_requests").glob("*.json"))) == 1
    assert first[0].created_at == source_time


def test_materializer_suppresses_satisfied_and_rejects_unknown_keys(tmp_path):
    from pydantic import ValidationError
    from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer, ConstraintRequestStore, SupportedConstraintKey

    materializer = ConstraintRequestMaterializer(ConstraintRequestStore(tmp_path))
    state = _state(requirement_ids=("REQ-TRANSMISSION-OUTPUT-SPEED",))
    result = materializer.materialize(project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", bound_revision=3, bound_state_hash="sha256:state", source_created_at=None, state=state, drafts=(_draft(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED),))
    assert len(result) == 1
    with pytest.raises(ValidationError):
        _draft("transmission.unknown")
