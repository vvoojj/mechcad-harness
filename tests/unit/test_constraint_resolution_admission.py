import pytest


def _resolution_record(*, project_id="PRJ-1", resolution_id="CRRES-1", source_request_id="CRREQ-1", value=6):
    from datetime import datetime, timezone

    from mechcad_harness.agents.constraint_resolution import (
        ConstraintResolutionRecord,
        OutputAngularSpeedAnswer,
        canonical_value_for_answer,
    )
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    answer = OutputAngularSpeedAnswer(value=value, unit="deg/s")
    return ConstraintResolutionRecord(
        resolution_id=resolution_id,
        source_command_id="CMD-1",
        source_constraint_request_id=source_request_id,
        project_id=project_id,
        engineering_scope_id="transmission",
        source_revision=1,
        source_state_hash="sha256:state",
        resolver_type="synthetic",
        resolver_id="resolver-1",
        key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED,
        source_answer=answer,
        canonical_value=canonical_value_for_answer(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, answer),
        status="accepted",
        validated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_project_wide_resolution_lookup_requires_exactly_one_valid_record(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionStore

    store = ConstraintResolutionStore(tmp_path)
    store.write_resolution("RUN-1", _resolution_record())

    assert store.load_unique_project_resolution("PRJ-1", "CRRES-1").resolution_id == "CRRES-1"
    with pytest.raises(ValueError, match="no project-wide resolution"):
        store.load_unique_project_resolution("PRJ-1", "CRRES-MISSING")


def test_project_wide_resolution_lookup_rejects_ambiguity_malformed_and_foreign_payload(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionStore

    duplicate_store = ConstraintResolutionStore(tmp_path / "duplicate")
    duplicate_store.write_resolution("RUN-1", _resolution_record())
    duplicate_store.write_resolution("RUN-2", _resolution_record())
    with pytest.raises(ValueError, match="ambiguous"):
        duplicate_store.load_unique_project_resolution("PRJ-1", "CRRES-1")

    malformed_store = ConstraintResolutionStore(tmp_path / "malformed")
    malformed_store.write_resolution("RUN-1", _resolution_record())
    malformed_path = (
        tmp_path / "malformed" / "projects" / "PRJ-1" / "runs" / "RUN-2"
        / "agents" / "constraint_resolutions" / "CRRES-1.json"
    )
    malformed_path.parent.mkdir(parents=True)
    malformed_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed"):
        malformed_store.load_unique_project_resolution("PRJ-1", "CRRES-1")

    foreign_store = ConstraintResolutionStore(tmp_path / "foreign")
    foreign_store.write_resolution("RUN-1", _resolution_record())
    foreign_path = (
        tmp_path / "foreign" / "projects" / "PRJ-1" / "runs" / "RUN-1"
        / "agents" / "constraint_resolutions" / "CRRES-1.json"
    )
    foreign_path.write_text(
        foreign_path.read_text(encoding="utf-8").replace('"project_id":"PRJ-1"', '"project_id":"PRJ-2"'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="project"):
        foreign_store.load_unique_project_resolution("PRJ-1", "CRRES-1")


def test_admission_policy_defaults_to_deny_all():
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionPolicy,
    )

    policy = ConstraintResolutionAdmissionPolicy.deny_all("PRJ-1")

    assert not policy.allows(
        resolver_type="synthetic",
        resolver_id="resolver-1",
        engineering_scope_id="transmission",
        keys=("transmission.output_angular_speed",),
    )


def test_admission_policy_matches_exact_identity_scope_and_explicit_keys():
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionPolicy,
        ConstraintResolutionAdmissionRule,
    )

    policy = ConstraintResolutionAdmissionPolicy(
        project_id="PRJ-1",
        rules=(
            ConstraintResolutionAdmissionRule(
                resolver_type="synthetic",
                resolver_id="resolver-1",
                engineering_scope_id="transmission",
                allowed_keys=("transmission.output_angular_speed",),
            ),
        ),
    )

    assert policy.allows(
        resolver_type="synthetic",
        resolver_id="resolver-1",
        engineering_scope_id="transmission",
        keys=("transmission.output_angular_speed",),
    )
    assert not policy.allows(
        resolver_type="synthetic",
        resolver_id="resolver-1",
        engineering_scope_id="transmission",
        keys=("transmission.motor_characteristics",),
    )
    assert not policy.allows(
        resolver_type="synthetic",
        resolver_id="other",
        engineering_scope_id="transmission",
        keys=("transmission.output_angular_speed",),
    )


def test_admission_platform_supports_all_seven_retained_keys():
    from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer
    from mechcad_harness.agents.constraint_resolution import (
        AzimuthDriveMountInterfaceAnswer,
        AzimuthMotorMountPlateDesignRequirementsAnswer,
        MotorCharacteristicsAnswer,
        OutputAngularSpeedAnswer,
        OutputInterfaceAnswer,
        PackagingEnvelopeAnswer,
        YagiPayloadCarrierRequirementsAnswer,
        canonical_value_for_answer,
    )
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionPolicy,
        ConstraintResolutionAdmissionRule,
    )
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.engineering.values import YagiEnvelopeValue

    yagi_envelopes = tuple(
        YagiEnvelopeValue(
            semantic_id=f"ANT-{index}",
            frequency_class="test",
            length_mm=100,
            span_mm=50,
            depth_mm=20,
            placeholder_mass_kg=0.5,
            placeholder_wind_area_m2=0.01,
        )
        for index in range(5)
    )
    yagi = YagiPayloadCarrierRequirementsAnswer(
        kind="yagi.payload_carrier_requirements",
        frequency_families_ghz=(0.4,),
        minimum_antenna_count=2,
        maximum_antenna_count=3,
        maximum_rotating_payload_kg=5,
        envelopes=yagi_envelopes,
        nominal_spacing_mm=150,
        adjustable_spacing_required=True,
        recommended_lateral_adjustment_mm=220,
        preferred_carrier_length_mm=500,
        required_fore_aft_travel_mm=75,
        preferred_fore_aft_travel_mm=100,
        preferred_com_offset_mm=20,
        acceptable_com_offset_mm=30,
        collision_resolution_strategies=("orientation",),
        maximum_collision_envelope_mm=(850, 400, 80),
        representative_payload_mass_kg=2,
        el_collision_sweep_degrees=(0, 90, 180),
        el_axis_height_search_range_mm=(180, 300),
        az_continuous_multiturn=True,
        az_target_revolution_time_s=12,
        interchangeable_adjustable_mounts_required=True,
        boom_compatibility_targets=("test",),
        provenance="test",
    )
    cases = {
        SupportedConstraintKey.OUTPUT_ANGULAR_SPEED: OutputAngularSpeedAnswer(value=6, unit="deg/s"),
        SupportedConstraintKey.MOTOR_CHARACTERISTICS: MotorCharacteristicsAnswer(
            motor_id="M", speed_min_rpm=0, speed_max_rpm=100,
            continuous_torque_nm=2, peak_torque_nm=3,
        ),
        SupportedConstraintKey.OUTPUT_INTERFACE: OutputInterfaceAnswer(
            interface_type="keyed", torque_transfer_description="shaft",
        ),
        SupportedConstraintKey.PACKAGING_ENVELOPE: PackagingEnvelopeAnswer(
            max_length_mm=1, max_width_mm=1, max_height_mm=1, mounting_description="plate",
        ),
        SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE: AzimuthDriveMountInterfaceAnswer(
            component_id="drive", frame_reference_id="frame", mount_points=({"hole_id": "H1"},),
        ),
        SupportedConstraintKey.AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS: AzimuthMotorMountPlateDesignRequirementsAnswer(
            minimum_edge_margin_mm=1, minimum_hole_ligament_mm=1,
            plate_thickness_policy={"allowed_thicknesses_mm": (1,), "minimum_thickness_mm": 1},
        ),
        SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS: yagi,
    }
    policy = ConstraintResolutionAdmissionPolicy(
        project_id="PRJ-1",
        rules=(ConstraintResolutionAdmissionRule(
            resolver_type="synthetic",
            resolver_id="resolver-1",
            engineering_scope_id="scope",
            allowed_keys=tuple(SupportedConstraintKey),
        ),),
    )
    assert policy.allows(
        resolver_type="synthetic", resolver_id="resolver-1",
        engineering_scope_id="scope", keys=tuple(cases),
    )
    for key, answer in cases.items():
        assert answer.kind == key.value
        assert canonical_value_for_answer(key, answer).kind == key.value
        assert ConstraintRequestMaterializer.anchor_for(key)[0] in {"requirement", "constraint"}


def test_admission_policy_rejects_wrong_project_and_malformed_configuration(tmp_path):
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionPolicy,
    )

    with pytest.raises(ValueError, match="project"):
        ConstraintResolutionAdmissionPolicy(
            project_id="PRJ-1",
            rules=(),
        ).for_project("PRJ-2")

    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        "project_id: PRJ-1\n"
        "rules:\n"
        "  - resolver_type: synthetic\n"
        "    resolver_id: resolver-1\n"
        "    engineering_scope_id: transmission\n"
        "    allowed_keys: [not-a-supported-key]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        ConstraintResolutionAdmissionPolicy.from_file(policy_path, project_id="PRJ-1")


class _Adapter:
    identity = object()

    def invoke(self, request):
        raise AssertionError("not called")


def test_production_composition_without_policy_is_deny_all(tmp_path):
    from mechcad_harness.application import ProductionApplication

    ownership = tmp_path / "ownership.yaml"
    ownership.write_text("ownership:\n  - path: /components/*\n    owner: test\n", encoding="utf-8")
    dependencies = tmp_path / "dependencies.yaml"
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")

    application = ProductionApplication.create(
        tmp_path / "workspace",
        "PRJ-1",
        _Adapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )

    assert not application.constraint_resolution_policy.allows(
        resolver_type="synthetic",
        resolver_id="resolver-1",
        engineering_scope_id="transmission",
        keys=("transmission.output_angular_speed",),
    )


def test_production_composition_rejects_wrong_project_policy(tmp_path):
    from mechcad_harness.application import ProductionApplication

    ownership = tmp_path / "ownership.yaml"
    ownership.write_text("ownership:\n  - path: /components/*\n    owner: test\n", encoding="utf-8")
    dependencies = tmp_path / "dependencies.yaml"
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    policy = tmp_path / "policy.yaml"
    policy.write_text("project_id: PRJ-other\nrules: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="project"):
        ProductionApplication.create(
            tmp_path / "workspace",
            "PRJ-1",
            _Adapter(),
            ownership_path=ownership,
            dependency_path=dependencies,
            constraint_resolution_policy_path=policy,
        )


def _batch_fixture(tmp_path, *, occupied=False, missing_motor_anchor=False):
    from datetime import datetime, timezone

    from mechcad_harness.agents.constraint_requests import (
        ConstraintRequestLifecycle,
        ConstraintRequestRecord,
        ConstraintRequestStore,
    )
    from mechcad_harness.agents.constraint_resolution import (
        ConstraintResolutionAnswer,
        ConstraintResolutionMaterializer,
        ConstraintResolutionStore,
        MotorCharacteristicsAnswer,
        OutputAngularSpeedAnswer,
        ConstraintResolutionBatchCommand,
        parameter_id,
    )
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import Constraint, DesignState, Requirement, ConstraintRequest
    from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter
    from mechcad_harness.engineering.values import OutputAngularSpeedValue
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager

    workspace = tmp_path / "workspace"
    project_id = "PRJ-1"
    state_manager = StateManager(workspace)
    initial_parameters = []
    if occupied:
        initial_parameters.append(
            AuthoritativeParameter(
                id=parameter_id(
                    project_id=project_id,
                    scope_id="transmission",
                    anchor_kind="requirement",
                    anchor_id="REQ-TRANSMISSION-OUTPUT-SPEED",
                    key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED,
                ),
                anchor=AuthoritativeAnchor(kind="requirement", id="REQ-TRANSMISSION-OUTPUT-SPEED"),
                scope_id="transmission",
                key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED,
                value=OutputAngularSpeedValue(
                    kind=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED.value,
                    value_rad_s=1,
                ),
                source_resolution_id="CRRES-occupied",
            )
        )
    state_manager.create_project(
        project_id,
        DesignState(
            id="DES-1",
            revision=1,
            requirements=[
                Requirement(id="REQ-TRANSMISSION-OUTPUT-SPEED", name="speed", description="speed"),
                *([] if missing_motor_anchor else [Requirement(
                    id="REQ-TRANSMISSION-MOTOR-CHARACTERISTICS", name="motor", description="motor"
                )]),
            ],
            constraints=[
                Constraint(id="CON-TRANSMISSION-OUTPUT-INTERFACE", name="interface", expression="interface"),
            ],
            authoritative_parameters=initial_parameters,
        ),
    )
    evidence = EvidenceStore(workspace, state_manager, DependencyGraph([], []))
    controller = RunController(
        workspace,
        state_manager,
        ChangeEngine(state_manager, OwnershipPolicy([{"path": "/authoritative_parameters/*", "owner": "mechcad-authority-admission"}])),
        evidence,
    )
    source = state_manager._read_current(project_id)
    run = controller.create_run(project_id)
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    request_store = ConstraintRequestStore(workspace)
    requests = (
        ConstraintRequestRecord(
            request=ConstraintRequest(id="CRREQ-S", description="speed", revision=1, state_hash=source["state_hash"]),
            project_id=project_id,
            run_id=run.run_id,
            task_id="TASK-S",
            agent_name="agent",
            agent_version="1.0",
            source_invocation_id="INV-S",
            source_agent_result_id="RES-S",
            engineering_scope_id="transmission",
            key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED,
            rationale="needed",
            lifecycle=ConstraintRequestLifecycle.DISCOVERED,
            created_at=timestamp,
        ),
        ConstraintRequestRecord(
            request=ConstraintRequest(id="CRREQ-M", description="motor", revision=1, state_hash=source["state_hash"]),
            project_id=project_id,
            run_id=run.run_id,
            task_id="TASK-M",
            agent_name="agent",
            agent_version="1.0",
            source_invocation_id="INV-M",
            source_agent_result_id="RES-M",
            engineering_scope_id="transmission",
            key=SupportedConstraintKey.MOTOR_CHARACTERISTICS,
            rationale="needed",
            lifecycle=ConstraintRequestLifecycle.DISCOVERED,
            created_at=timestamp,
        ),
    )
    for request, task_id in zip(requests, ("TASK-S", "TASK-M")):
        request_store.write(request)
        controller.add_task(
            run.run_id,
            TaskDefinition(
                task_id=task_id,
                run_id=run.run_id,
                task_type="agent",
                objective="resolve",
                bound_revision=1,
                bound_state_hash=source["state_hash"],
            ),
        )
    command = ConstraintResolutionBatchCommand(
        command_id="CMD-BATCH",
        project_id=project_id,
        engineering_scope_id="transmission",
        source_revision=1,
        source_state_hash=source["state_hash"],
        answers=(
            ConstraintResolutionAnswer(
                request_id="CRREQ-S",
                answer=OutputAngularSpeedAnswer(value=6, unit="deg/s"),
            ),
            ConstraintResolutionAnswer(
                request_id="CRREQ-M",
                answer=MotorCharacteristicsAnswer(
                    motor_id="M-1",
                    speed_min_rpm=0,
                    speed_max_rpm=100,
                    continuous_torque_nm=2,
                    peak_torque_nm=3,
                ),
            ),
        ),
        resolver_type="synthetic",
        resolver_id="resolver-1",
        received_at=timestamp,
    )
    ConstraintResolutionMaterializer(
        request_store,
        ConstraintResolutionStore(workspace),
    ).materialize_batch(command, run_id=run.run_id)
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionPolicy,
        ConstraintResolutionAdmissionRule,
    )

    policy = ConstraintResolutionAdmissionPolicy(
        project_id=project_id,
        rules=(
            ConstraintResolutionAdmissionRule(
                resolver_type="synthetic",
                resolver_id="resolver-1",
                engineering_scope_id="transmission",
                allowed_keys=tuple(SupportedConstraintKey),
            ),
        ),
    )
    return project_id, run.run_id, command, state_manager, controller, policy


def test_batch_compiler_is_deterministic_and_orders_one_add_per_parameter(tmp_path):
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionService,
    )

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(tmp_path)
    service = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )

    first = service.compile_batch(run_id, command.command_id)
    second = service.compile_batch(run_id, command.command_id)

    assert first.proposal.id == second.proposal.id
    assert first.changeset_id == second.changeset_id
    assert first.proposal.actor == "mechcad-authority-admission"
    assert [operation.operation.value for operation in first.proposal.operations] == ["add", "add"]
    assert [operation.path for operation in first.proposal.operations] == sorted(
        operation.path for operation in first.proposal.operations
    )
    assert state_manager._read_current(project_id)["revision"] == 1


def test_admission_appends_prepared_then_applies_once_and_replays_read_only(tmp_path):
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionService,
    )

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(tmp_path)
    service = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )

    first = service.admit_batch(run_id, command.command_id)
    controller.change_engine.apply_proposal = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("replay must not call ChangeEngine")
    )
    replay = service.admit_batch(run_id, command.command_id)

    assert first.revision == 2
    assert replay.replayed is True
    assert replay.revision == 2
    assert state_manager._read_current(project_id)["revision"] == 2
    events = list((tmp_path / "workspace" / "projects" / project_id / "runs" / run_id / "events").glob("*.json"))
    prepared = [path for path in events if 'CONSTRAINT_RESOLUTION_BATCH_PREPARED' in path.read_text(encoding="utf-8")]
    assert len(prepared) == 1


def test_batch_compiler_rejects_stale_source_before_prepared_event(tmp_path):
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionService,
    )

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(tmp_path)
    state_manager.create_revision(
        project_id,
        state_manager.load_current_state(project_id).model_copy(update={"id": "DES-advanced"}),
    )
    service = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )

    with pytest.raises(ValueError, match="stale"):
        service.compile_batch(run_id, command.command_id)
    event_dir = tmp_path / "workspace" / "projects" / project_id / "runs" / run_id / "events"
    assert not any(
        "CONSTRAINT_RESOLUTION_BATCH_PREPARED" in path.read_text(encoding="utf-8")
        for path in event_dir.glob("*.json")
    )


def test_batch_compiler_rejects_extra_record_claiming_command_but_allows_other_command(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionStore
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionService,
    )

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(tmp_path)
    resolution_store = ConstraintResolutionStore(tmp_path / "workspace")
    existing = resolution_store.load_command_scoped_resolutions(
        project_id, run_id, command.command_id
    )
    resolution_store.write_resolution(
        run_id,
        existing[0].model_copy(
            update={
                "resolution_id": "CRRES-extra",
                "source_command_id": "CMD-other",
                "source_constraint_request_id": "CRREQ-other",
            }
        ),
    )
    service = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )
    assert len(service.compile_batch(run_id, command.command_id).parameters) == 2

    resolution_store.write_resolution(
        run_id,
        existing[1].model_copy(update={"resolution_id": "CRRES-extra-command"}),
    )
    with pytest.raises(ValueError, match="set"):
        service.compile_batch(run_id, command.command_id)


def test_batch_compiler_rejects_missing_anchor_and_missing_source_run(tmp_path):
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionService,
    )

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(
        tmp_path / "anchor", missing_motor_anchor=True
    )
    service = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )
    with pytest.raises(ValueError, match="anchor"):
        service.compile_batch(run_id, command.command_id)
    with pytest.raises(Exception, match="missing run record"):
        service.compile_batch("RUN-missing", command.command_id)


def test_batch_compiler_rejects_canonical_value_mismatch_and_malformed_source_run(tmp_path):
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionStore
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionService,
    )

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(
        tmp_path / "records"
    )
    store = ConstraintResolutionStore(tmp_path / "records" / "workspace")
    record = next(
        item
        for item in store.load_command_scoped_resolutions(project_id, run_id, command.command_id)
        if item.key.value == "transmission.output_angular_speed"
    )
    store.store._write(
        store._path(project_id, run_id, "constraint_resolutions", record.resolution_id),
        record.model_copy(update={
            "canonical_value": record.canonical_value.model_copy(
                update={"value_rad_s": record.canonical_value.value_rad_s + 1}
            )
        }).model_dump(mode="json"),
        exclusive=False,
    )
    service = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )
    with pytest.raises(ValueError, match="canonical value"):
        service.compile_batch(run_id, command.command_id)

    manifest = state_manager.workspace / "projects" / project_id / "runs" / run_id / "manifest.json"
    manifest.write_text("{not-json", encoding="utf-8")
    with pytest.raises(Exception, match="invalid run record"):
        service.compile_batch(run_id, command.command_id)


def test_batch_compiler_rejects_conflicting_project_wide_source_request_resolution(tmp_path):
    from mechcad_harness.agents.constraint_resolution import (
        ConstraintResolutionStore,
        OutputAngularSpeedAnswer,
        canonical_value_for_answer,
        resolution_id,
    )
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionService,
    )
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(tmp_path)
    store = ConstraintResolutionStore(tmp_path / "workspace")
    record = next(
        item for item in store.load_command_scoped_resolutions(project_id, run_id, command.command_id)
        if item.key is SupportedConstraintKey.OUTPUT_ANGULAR_SPEED
    )
    answer = OutputAngularSpeedAnswer(value=7, unit="deg/s")
    conflict = record.model_copy(update={
        "resolution_id": resolution_id(
            project_id=project_id,
            source_request_id=record.source_constraint_request_id,
            source_revision=record.source_revision,
            source_state_hash=record.source_state_hash,
            answer=answer,
        ),
        "source_command_id": "CMD-other",
        "source_answer": answer,
        "canonical_value": canonical_value_for_answer(record.key, answer),
    })
    store.write_resolution("RUN-other", conflict)
    service = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )
    with pytest.raises(ValueError, match="conflicting project-wide"):
        service.compile_batch(run_id, command.command_id)


def test_admission_rejects_unauthorized_resolver_and_occupied_target(tmp_path):
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionPolicy,
        ConstraintResolutionAdmissionRule,
        ConstraintResolutionAdmissionService,
    )
    from mechcad_harness.engineering.keys import SupportedConstraintKey

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(
        tmp_path / "authorized"
    )
    unauthorized = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=ConstraintResolutionAdmissionPolicy(
            project_id=project_id,
            rules=(ConstraintResolutionAdmissionRule(
                resolver_type="other",
                resolver_id="other",
                engineering_scope_id="transmission",
                allowed_keys=tuple(SupportedConstraintKey),
            ),),
        ),
    )
    with pytest.raises(ValueError, match="authorized"):
        unauthorized.compile_batch(run_id, command.command_id)

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(
        tmp_path / "occupied", occupied=True
    )
    with pytest.raises(ValueError, match="occupied"):
        ConstraintResolutionAdmissionService(
            project_id=project_id,
            state_manager=state_manager,
            run_controller=controller,
            policy=policy,
        ).compile_batch(run_id, command.command_id)


def test_prepared_event_is_reused_exactly_and_conflicts_fail_closed(tmp_path):
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionService,
    )

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(tmp_path)
    service = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )
    compiled = service.compile_batch(run_id, command.command_id)
    payload = service._prepared_payload(run_id, command, compiled)
    first = service._ensure_prepared_event(run_id, command.command_id, payload, append=True)
    second = service._ensure_prepared_event(run_id, command.command_id, payload, append=True)
    assert first.event_id == second.event_id

    conflict = dict(payload)
    conflict["changeset_id"] = "CS-conflict"
    with pytest.raises(ValueError, match="conflicting"):
        service._ensure_prepared_event(run_id, command.command_id, conflict, append=True)

    service.run_store.append_event(
        project_id,
        run_id,
        "CONSTRAINT_RESOLUTION_BATCH_PREPARED",
        payload,
    )
    with pytest.raises(ValueError, match="multiple"):
        service._ensure_prepared_event(run_id, command.command_id, payload, append=True)


def test_post_apply_invalidation_failure_keeps_n_plus_one_and_replay_fails_closed(tmp_path, monkeypatch):
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionService,
    )

    project_id, run_id, command, state_manager, controller, policy = _batch_fixture(tmp_path)
    service = ConstraintResolutionAdmissionService(
        project_id=project_id,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )

    def fail_invalidation(*args, **kwargs):
        raise RuntimeError("invalidation persistence failed")

    monkeypatch.setattr(controller.evidence, "record_invalidation", fail_invalidation)
    with pytest.raises(Exception, match="invalidation persistence failed"):
        service.admit_batch(run_id, command.command_id)
    assert state_manager._read_current(project_id)["revision"] == 2
    assert controller.get_run(run_id).status.value == "blocked"
    with pytest.raises(Exception, match="invalidation record missing"):
        service.admit_batch(run_id, command.command_id)
    assert state_manager._read_current(project_id)["revision"] == 2
