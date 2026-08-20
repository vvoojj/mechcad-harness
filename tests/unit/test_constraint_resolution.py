from datetime import datetime, timezone

import pytest


def test_neutral_supported_keys_are_exactly_four():
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    assert {key.value for key in SupportedConstraintKey if key.value.startswith("transmission.")} == {
        "transmission.output_angular_speed",
        "transmission.motor_characteristics",
        "transmission.output_interface",
        "transmission.packaging_envelope",
    }


def test_output_speed_source_answer_converts_to_canonical_value():
    from mechcad_harness.agents.constraint_resolution import OutputAngularSpeedAnswer, canonical_value_for_answer
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    answer = OutputAngularSpeedAnswer(value=6, unit="deg/s")
    value = canonical_value_for_answer(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, answer)
    assert value.kind == SupportedConstraintKey.OUTPUT_ANGULAR_SPEED.value
    assert value.value_rad_s == pytest.approx(0.10471975511965977)
    assert "canonical_value" not in value.model_dump()


def test_parameter_identity_is_stable_across_revision_and_resolution():
    from mechcad_harness.agents.constraint_resolution import parameter_id
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    kwargs = dict(project_id="PRJ", scope_id="transmission", anchor_kind="requirement", anchor_id="REQ-TRANSMISSION-OUTPUT-SPEED", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED)
    first = parameter_id(**kwargs)
    assert first == parameter_id(**kwargs)
    assert first == parameter_id(**kwargs)
    assert first != parameter_id(**{**kwargs, "scope_id": "pan-transmission"})
    assert first != parameter_id(**{**kwargs, "anchor_id": "REQ-OTHER"})
    assert first != parameter_id(**{**kwargs, "key": SupportedConstraintKey.MOTOR_CHARACTERISTICS})


def test_authoritative_parameter_rejects_key_value_or_anchor_mismatch():
    from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter, OutputAngularSpeedValue, MotorCharacteristicsValue
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    with pytest.raises(ValueError):
        AuthoritativeParameter(id="PARAM-1", anchor=AuthoritativeAnchor(kind="constraint", id="CON-TRANSMISSION-PACKAGING-ENVELOPE"), scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, value=OutputAngularSpeedValue(value_rad_s=1), source_resolution_id="CRRES-1")
    with pytest.raises(ValueError):
        AuthoritativeParameter(id="PARAM-1", anchor=AuthoritativeAnchor(kind="requirement", id="REQ-TRANSMISSION-OUTPUT-SPEED"), scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, value=MotorCharacteristicsValue(motor_id="M", speed_min_rpm=0, speed_max_rpm=1, continuous_torque_nm=1, peak_torque_nm=1), source_resolution_id="CRRES-1")


def test_authoritative_parameter_accepts_matching_canonical_value():
    from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter, OutputAngularSpeedValue
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    parameter = AuthoritativeParameter(id="PARAM-1", anchor=AuthoritativeAnchor(kind="requirement", id="REQ-TRANSMISSION-OUTPUT-SPEED"), scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, value=OutputAngularSpeedValue(kind=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED.value, value_rad_s=0.104), source_resolution_id="CRRES-1")
    assert parameter.value.value_rad_s == 0.104


def test_legacy_design_state_defaults_authoritative_parameters_empty():
    from mechcad_harness.models import DesignState

    state = DesignState.model_validate({"id": "DES", "revision": 1})
    assert state.authoritative_parameters == []


def test_resolution_batch_is_nonempty_and_rejects_duplicate_requests():
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, OutputAngularSpeedAnswer

    answer = ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s"))
    with pytest.raises(ValueError):
        ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(answer, answer), resolver_type="user", resolver_id="user-1", received_at=datetime.now(timezone.utc))


def test_resolution_command_and_record_ids_are_replay_stable():
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionRecord, OutputAngularSpeedAnswer, command_id, resolution_id

    received_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    answer = ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s"))
    kwargs = dict(project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(answer,), resolver_type="user", resolver_id="user-1", received_at=received_at)
    assert command_id(**kwargs) == command_id(**kwargs)
    assert resolution_id(project_id="PRJ", source_request_id="CRREQ-1", source_revision=1, source_state_hash="sha256:state", answer=answer.answer) == resolution_id(project_id="PRJ", source_request_id="CRREQ-1", source_revision=1, source_state_hash="sha256:state", answer=answer.answer)
    record = ConstraintResolutionRecord(resolution_id="CRRES-1", source_command_id="CMD-1", source_constraint_request_id="CRREQ-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", resolver_type="user", resolver_id="user-1", key="transmission.output_angular_speed", source_answer=answer.answer, canonical_value={"kind": "transmission.output_angular_speed", "value_rad_s": 0.10471975511965977}, status="accepted", validated_at=received_at)
    assert record.status.value == "accepted"


def test_resolution_store_roundtrips_commands_and_resolutions(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionRecord, ConstraintResolutionStore, OutputAngularSpeedAnswer

    store = ConstraintResolutionStore(tmp_path)
    received_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    answer = ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s"))
    command = ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(answer,), resolver_type="user", resolver_id="user-1", received_at=received_at)
    store.write_command("RUN", command)
    assert store.load_command("PRJ", "RUN", command.command_id) == command
    resolution = ConstraintResolutionRecord(resolution_id="CRRES-1", source_command_id="CMD-1", source_constraint_request_id="CRREQ-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", resolver_type="user", resolver_id="user-1", key="transmission.output_angular_speed", source_answer=answer.answer, canonical_value={"kind": "transmission.output_angular_speed", "value_rad_s": 0.10471975511965977}, status="accepted", validated_at=received_at)
    store.write_resolution("RUN", resolution)
    assert store.load_resolution("PRJ", "RUN", resolution.resolution_id) == resolution


def test_resolution_store_rejects_missing_and_malformed_records(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionStore

    store = ConstraintResolutionStore(tmp_path)
    with pytest.raises(Exception):
        store.load_command("PRJ", "RUN", "CMD-MISSING")
    with pytest.raises(Exception):
        store.load_resolution("PRJ", "RUN", "CRRES-MISSING")


def test_resolution_store_rejects_malformed_json(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionStore

    store = ConstraintResolutionStore(tmp_path)
    path = tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "agents" / "constraint_resolution_commands" / "CMD-BAD.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(Exception):
        store.load_command("PRJ", "RUN", "CMD-BAD")


def test_resolution_materializer_validates_request_binding_and_types(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestRecord, ConstraintRequestStore, ConstraintRequestLifecycle
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, OutputAngularSpeedAnswer, MotorCharacteristicsAnswer
    from mechcad_harness.models import ConstraintRequest

    store = ConstraintRequestStore(tmp_path)
    request = ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    store.write(request)
    materializer = ConstraintResolutionMaterializer(store)
    command = ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    records = materializer.materialize(command, run_id="RUN")
    assert records[0].canonical_value.value_rad_s == pytest.approx(0.10471975511965977)
    bad = command.model_copy(update={"answers": (ConstraintResolutionAnswer(request_id="CRREQ-1", answer=MotorCharacteristicsAnswer(motor_id="M", speed_min_rpm=0, speed_max_rpm=1, continuous_torque_nm=1, peak_torque_nm=1)),)})
    with pytest.raises(ValueError):
        materializer.materialize(bad, run_id="RUN")


def test_resolution_materializer_materializes_multiple_answers_in_request_order(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestRecord, ConstraintRequestStore, ConstraintRequestLifecycle
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, OutputAngularSpeedAnswer, OutputInterfaceAnswer
    from mechcad_harness.models import ConstraintRequest

    store = ConstraintRequestStore(tmp_path)
    for request_id, key in (("CRREQ-B", SupportedConstraintKey.OUTPUT_INTERFACE), ("CRREQ-A", SupportedConstraintKey.OUTPUT_ANGULAR_SPEED)):
        store.write(ConstraintRequestRecord(request=ConstraintRequest(id=request_id, description="missing", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=key, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    command = ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(ConstraintResolutionAnswer(request_id="CRREQ-B", answer=OutputInterfaceAnswer(interface_type="keyed", torque_transfer_description="shaft")), ConstraintResolutionAnswer(request_id="CRREQ-A", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s"))), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    records = ConstraintResolutionMaterializer(store).materialize(command, run_id="RUN")
    assert [record.source_constraint_request_id for record in records] == ["CRREQ-A", "CRREQ-B"]


def test_resolution_materializer_reuses_same_resolution_and_rejects_conflict(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, OutputAngularSpeedAnswer, canonical_record_equivalent
    from mechcad_harness.models import ConstraintRequest

    request_store = ConstraintRequestStore(tmp_path)
    request_store.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    materializer = ConstraintResolutionMaterializer(request_store)
    base = dict(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    first = materializer.materialize(ConstraintResolutionBatchCommand(answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), **base), run_id="RUN")
    replay = materializer.materialize(ConstraintResolutionBatchCommand(answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), **base), run_id="RUN")
    assert canonical_record_equivalent(first[0], replay[0])
    with pytest.raises(ValueError):
        materializer.materialize(ConstraintResolutionBatchCommand(answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=7, unit="deg/s")),), **base), run_id="RUN")


def test_public_materialize_batch_persists_command_and_returns_typed_result(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializationResult, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    requests = ConstraintRequestStore(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    command = ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    result = ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path)).materialize_batch(command, run_id="RUN")
    assert isinstance(result, ConstraintResolutionMaterializationResult)
    assert result.command_id == "CMD-1"
    assert result.resolution_ids == (result.resolution_records[0].resolution_id,)
    assert result.resolution_records[0].canonical_value.value_rad_s == pytest.approx(0.10471975511965977)
    assert ConstraintResolutionStore(tmp_path).load_command("PRJ", "RUN", "CMD-1") == command


def test_public_materialize_batch_prevalidates_all_members_before_writes(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer, MotorCharacteristicsAnswer
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    requests = ConstraintRequestStore(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    command = ConstraintResolutionBatchCommand(command_id="CMD-BAD", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")), ConstraintResolutionAnswer(request_id="CRREQ-MISSING", answer=MotorCharacteristicsAnswer(motor_id="M", speed_min_rpm=0, speed_max_rpm=1, continuous_torque_nm=1, peak_torque_nm=1))), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    with pytest.raises(Exception):
        ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path)).materialize_batch(command, run_id="RUN")
    assert not list((tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "agents" / "constraint_resolutions").glob("*.json"))


def test_public_multi_answer_replay_returns_same_records_in_deterministic_order(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer, OutputInterfaceAnswer
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    requests = ConstraintRequestStore(tmp_path)
    for request_id, key in (("CRREQ-B", SupportedConstraintKey.OUTPUT_INTERFACE), ("CRREQ-A", SupportedConstraintKey.OUTPUT_ANGULAR_SPEED)):
        requests.write(ConstraintRequestRecord(request=ConstraintRequest(id=request_id, description="missing", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=key, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    command = ConstraintResolutionBatchCommand(command_id="CMD-MULTI", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(ConstraintResolutionAnswer(request_id="CRREQ-B", answer=OutputInterfaceAnswer(interface_type="keyed", torque_transfer_description="shaft")), ConstraintResolutionAnswer(request_id="CRREQ-A", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s"))), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    materializer = ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path))
    first = materializer.materialize_batch(command, run_id="RUN")
    replay = materializer.materialize_batch(command, run_id="RUN")
    assert first.resolution_ids == replay.resolution_ids
    assert [record.source_constraint_request_id for record in first.resolution_records] == ["CRREQ-A", "CRREQ-B"]
    assert len(list((tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "agents" / "constraint_resolutions").glob("*.json"))) == 2


def test_public_batch_reuses_partial_resolution_persistence(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer, OutputInterfaceAnswer
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    requests = ConstraintRequestStore(tmp_path)
    for request_id, key in (("CRREQ-A", SupportedConstraintKey.OUTPUT_ANGULAR_SPEED), ("CRREQ-B", SupportedConstraintKey.OUTPUT_INTERFACE)):
        requests.write(ConstraintRequestRecord(request=ConstraintRequest(id=request_id, description="missing", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=key, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    command = ConstraintResolutionBatchCommand(command_id="CMD-PARTIAL", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(ConstraintResolutionAnswer(request_id="CRREQ-A", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")), ConstraintResolutionAnswer(request_id="CRREQ-B", answer=OutputInterfaceAnswer(interface_type="keyed", torque_transfer_description="shaft"))), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    store = ConstraintResolutionStore(tmp_path)
    materializer = ConstraintResolutionMaterializer(requests, store)
    first = materializer.materialize_batch(command, run_id="RUN")
    second = materializer.materialize_batch(command, run_id="RUN")
    assert first.resolution_ids == second.resolution_ids
    assert len(list((tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "agents" / "constraint_resolutions").glob("*.json"))) == 2


def test_canonical_record_equivalence_detects_timestamp_change(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, OutputAngularSpeedAnswer, canonical_record_equivalent
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    store = ConstraintRequestStore(tmp_path)
    store.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    command = ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    records = ConstraintResolutionMaterializer(store).materialize(command, run_id="RUN")
    loaded = ConstraintResolutionMaterializer(store).materialize(command, run_id="RUN")[0]
    assert canonical_record_equivalent(records[0], loaded)
    assert not canonical_record_equivalent(records[0], records[0].model_copy(update={"validated_at": datetime(2026, 1, 3, tzinfo=timezone.utc)}))


def test_record_requires_strict_canonical_value_union():
    from pydantic import ValidationError
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionRecord, OutputAngularSpeedAnswer

    with pytest.raises(ValidationError):
        ConstraintResolutionRecord(resolution_id="CRRES-1", source_command_id="CMD-1", source_constraint_request_id="CRREQ-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", resolver_type="user", resolver_id="u", key="transmission.output_angular_speed", source_answer=OutputAngularSpeedAnswer(value=6, unit="deg/s"), canonical_value={"kind": "transmission.motor_characteristics", "motor_id": "M", "speed_min_rpm": 0, "speed_max_rpm": 1, "continuous_torque_nm": 1, "peak_torque_nm": 1}, status="accepted", validated_at=datetime(2026, 1, 2, tzinfo=timezone.utc))


def test_same_id_command_and_resolution_conflicts_are_immutable(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionRecord, ConstraintResolutionStore, OutputAngularSpeedAnswer, canonical_value_for_answer
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    store = ConstraintResolutionStore(tmp_path)
    received = datetime(2026, 1, 2, tzinfo=timezone.utc)
    answer = ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s"))
    command = ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(answer,), resolver_type="user", resolver_id="u", received_at=received)
    store.write_command("RUN", command)
    with pytest.raises(Exception):
        store.write_command("RUN", command.model_copy(update={"resolver_id": "other"}))
    record = ConstraintResolutionRecord(resolution_id="CRRES-1", source_command_id="CMD-1", source_constraint_request_id="CRREQ-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", resolver_type="user", resolver_id="u", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, source_answer=answer.answer, canonical_value=canonical_value_for_answer(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, answer.answer), status="accepted", validated_at=received)
    store.write_resolution("RUN", record)
    with pytest.raises(Exception):
        store.write_resolution("RUN", record.model_copy(update={"resolver_id": "other"}))


def test_materializer_rejects_different_answer_for_same_request(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    requests = ConstraintRequestStore(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    materializer = ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path))
    base = dict(project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    first = materializer.materialize_batch(ConstraintResolutionBatchCommand(command_id="CMD-1", answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), **base), run_id="RUN")
    with pytest.raises(Exception):
        materializer.materialize_batch(ConstraintResolutionBatchCommand(command_id="CMD-2", answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=7, unit="deg/s")),), **base), run_id="RUN")
    assert materializer.resolution_store.load_resolution("PRJ", "RUN", first.resolution_ids[0]).canonical_value.value_rad_s == pytest.approx(0.10471975511965977)


def test_materializer_returns_records_loaded_from_store(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    requests = ConstraintRequestStore(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    store = ConstraintResolutionStore(tmp_path)
    result = ConstraintResolutionMaterializer(requests, store).materialize_batch(ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc)), run_id="RUN")
    loaded = store.load_resolution("PRJ", "RUN", result.resolution_ids[0])
    assert result.resolution_records[0] == loaded
    assert tuple(record.resolution_id for record in result.resolution_records) == result.resolution_ids


def test_multiple_accepted_resolutions_for_source_request_fail_closed(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionRecord, ConstraintResolutionStore, OutputAngularSpeedAnswer, canonical_value_for_answer, resolution_id
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    requests = ConstraintRequestStore(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    store = ConstraintResolutionStore(tmp_path)
    received = datetime(2026, 1, 2, tzinfo=timezone.utc)
    for value in (6, 7):
        answer = OutputAngularSpeedAnswer(value=value, unit="deg/s")
        store.write_resolution("RUN", ConstraintResolutionRecord(resolution_id=resolution_id(project_id="PRJ", source_request_id="CRREQ-1", source_revision=1, source_state_hash="sha256:state", answer=answer), source_command_id=f"CMD-{value}", source_constraint_request_id="CRREQ-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", resolver_type="user", resolver_id="u", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, source_answer=answer, canonical_value=canonical_value_for_answer(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, answer), status="accepted", validated_at=received))
    with pytest.raises(ValueError):
        store.load_accepted_by_source_request("PRJ", "RUN", "CRREQ-1")


def test_public_six_deg_per_second_preserves_source_and_canonical_values_after_reload(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    requests = ConstraintRequestStore(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash="sha256:state"), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    store = ConstraintResolutionStore(tmp_path)
    result = ConstraintResolutionMaterializer(requests, store).materialize_batch(ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash="sha256:state", answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc)), run_id="RUN")
    record = store.load_resolution("PRJ", "RUN", result.resolution_ids[0])
    assert record.source_answer.value == 6
    assert record.source_answer.unit == "deg/s"
    assert record.canonical_value.kind == "transmission.output_angular_speed"
    assert record.canonical_value.value_rad_s == pytest.approx(0.10471975511965977)
