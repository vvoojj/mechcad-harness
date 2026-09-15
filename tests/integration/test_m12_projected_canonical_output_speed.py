from __future__ import annotations

import json
from datetime import datetime, timezone

from mechcad_harness.agents.constraint_requests import (
    ConstraintRequestLifecycle,
    ConstraintRequestRecord,
    ConstraintRequestStore,
)
from mechcad_harness.agents.constraint_resolution import (
    ConstraintResolutionAnswer,
    ConstraintResolutionBatchCommand,
    ConstraintResolutionMaterializer,
    ConstraintResolutionStore,
    OutputAngularSpeedAnswer,
)
from mechcad_harness.application import ProductionApplication
from mechcad_harness.changes.constraint_resolution_admission import (
    ConstraintResolutionAdmissionPolicy,
    ConstraintResolutionAdmissionRule,
)
from mechcad_harness.candidates import (
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisRequest,
)
from mechcad_harness.engineering import SupportedConstraintKey
from mechcad_harness.engineering.scalar_projection import (
    AuthoritativeParameterLocator,
    CanonicalScalarProjection,
    project_authoritative_scalar,
    projection_hash,
)
from mechcad_harness.models import Constraint, ConstraintRequest, DesignState, Requirement
from mechcad_harness.revolute_drive import (
    DriveAdmissibility,
    DriveArchitecture,
    InputProvenanceKind,
    RevoluteDriveEngineeringRequirements,
    RevoluteDriveTemplateInput,
    SourceBoundScalar,
    StaticOutputShaftDesignLoadCase,
    ShaftSupportGeometry,
)
from mechcad_harness.revolute_drive.lowering import lower_projected_output_speed
from mechcad_harness.runs import TaskDefinition
from mechcad_harness.state import StateManager, state_hash
from tests.integration.test_m12_revolute_drive_production import (
    template,
)


PROJECT_ID = "PRJ-M12-PROJECTED"
TIMESTAMP = datetime(2026, 9, 15, tzinfo=timezone.utc)


class UninvokedAgentAdapter:
    identity = "m12-projected-uninvoked"

    def invoke(self, request):
        raise AssertionError("agent adapter must not be invoked")


def _policy_for_direct_drive():
    from mechcad_harness.candidates import CandidateSynthesisPolicy

    return CandidateSynthesisPolicy(
        entries=(
            ("allow-direct_drive", DriveArchitecture.DIRECT_DRIVE.value, "hard_admissibility"),
            (
                "allow-design-variable:selected-output-shaft-diameter",
                json.dumps({"value": 12.0}, sort_keys=True, separators=(",", ":")),
                "hard_admissibility",
            ),
        )
    )


def _policy_scalar(value: float, unit: str) -> SourceBoundScalar:
    return SourceBoundScalar(
        value=value,
        unit=unit,
        provenance=InputProvenanceKind.POLICY_ASSUMPTION,
    )


def _requirements(projected_speed):
    return RevoluteDriveEngineeringRequirements(
        required_output_speed=projected_speed,
        design_load_case=StaticOutputShaftDesignLoadCase(
            design_torque=_policy_scalar(10.0, "N*m"),
            transverse_force_y=_policy_scalar(0.0, "N"),
            transverse_force_z=_policy_scalar(0.0, "N"),
        ),
        required_voltage=_policy_scalar(24.0, "V"),
        safety_factor=_policy_scalar(2.0, "1"),
        shaft_yield_strength=_policy_scalar(250.0, "MPa"),
        shaft_support_geometry=ShaftSupportGeometry(
            support_a_x=_policy_scalar(0.0, "mm"),
            support_b_x=_policy_scalar(100.0, "mm"),
            load_plane_x=_policy_scalar(50.0, "mm"),
        ),
        trusted_source_scalar_bindings=(),
    )


def _create_application(tmp_path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    ownership.write_text(
        "ownership:\n  - path: /authoritative_parameters/*\n    owner: mechcad-authority-admission\n",
        encoding="utf-8",
    )
    dependencies = tmp_path / "dependencies.yaml"
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    initial_state = DesignState(
        id="DES-M12-PROJECTED",
        revision=1,
        created_at=TIMESTAMP,
        requirements=[
            Requirement(
                id="REQ-TRANSMISSION-OUTPUT-SPEED",
                name="output speed",
                description="canonical output speed",
                created_at=TIMESTAMP,
            ),
            Requirement(
                id="REQ-TRANSMISSION-MOTOR-CHARACTERISTICS",
                name="motor characteristics",
                description="motor authority",
                created_at=TIMESTAMP,
            ),
        ],
        constraints=[
            Constraint(
                id="CON-TRANSMISSION-OUTPUT-INTERFACE",
                name="output interface",
                expression="shaft interface",
                created_at=TIMESTAMP,
            )
        ],
    )
    manager = StateManager(workspace)
    manager.create_project(PROJECT_ID, initial_state)
    admission_policy = ConstraintResolutionAdmissionPolicy(
        project_id=PROJECT_ID,
        rules=(
            ConstraintResolutionAdmissionRule(
                resolver_type="synthetic",
                resolver_id="resolver-1",
                engineering_scope_id="transmission",
                allowed_keys=(SupportedConstraintKey.OUTPUT_ANGULAR_SPEED,),
            ),
        ),
    )
    app = ProductionApplication.create(
        workspace,
        PROJECT_ID,
        UninvokedAgentAdapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
        constraint_resolution_policy=admission_policy,
    )
    return app


def _admit_output_speed(app):
    source = app.state_manager._read_current(PROJECT_ID)
    run = app.create_run().run
    request_store = ConstraintRequestStore(app.state_manager.workspace)
    request_store.write(
        ConstraintRequestRecord(
            request=ConstraintRequest(
                id="CRREQ-SPEED",
                description="output speed",
                revision=1,
                state_hash=source["state_hash"],
            ),
            project_id=PROJECT_ID,
            run_id=run.run_id,
            task_id="TASK-SPEED",
            agent_name="agent",
            agent_version="1.0",
            source_invocation_id="INV-SPEED",
            source_agent_result_id="RES-SPEED",
            engineering_scope_id="transmission",
            key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED,
            rationale="required by the revolute drive",
            lifecycle=ConstraintRequestLifecycle.DISCOVERED,
            created_at=TIMESTAMP,
        )
    )
    app.run_controller.add_task(
        run.run_id,
        TaskDefinition(
            task_id="TASK-SPEED",
            run_id=run.run_id,
            task_type="agent",
            objective="resolve output speed",
            bound_revision=1,
            bound_state_hash=source["state_hash"],
        ),
    )
    command = ConstraintResolutionBatchCommand(
        command_id="CMD-SPEED",
        project_id=PROJECT_ID,
        engineering_scope_id="transmission",
        source_revision=1,
        source_state_hash=source["state_hash"],
        answers=(
            ConstraintResolutionAnswer(
                request_id="CRREQ-SPEED",
                answer=OutputAngularSpeedAnswer(value=120.0, unit="deg/s"),
            ),
        ),
        resolver_type="synthetic",
        resolver_id="resolver-1",
        received_at=TIMESTAMP,
    )
    ConstraintResolutionMaterializer(
        request_store,
        ConstraintResolutionStore(app.state_manager.workspace),
    ).materialize_batch(command, run_id=run.run_id)
    admission = app.admit_constraint_resolution_batch(run.run_id, command.command_id)
    state = app.state_manager.load_current_state(PROJECT_ID)
    parameter = next(
        parameter
        for parameter in state.authoritative_parameters
        if parameter.key is SupportedConstraintKey.OUTPUT_ANGULAR_SPEED
    )
    return admission, state, parameter


def _request(state):
    binding = CandidateSourceBinding(
        project_id=PROJECT_ID,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path="/authoritative_parameters",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_PARAMETER,
            ),
        ),
    ).bound_to(state)
    binding.validate_against(PROJECT_ID, state)
    return CandidateSynthesisRequest(
        source_binding=binding,
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )


def test_canonical_admission_output_speed_projects_lowers_and_evaluates_through_m12_api(tmp_path):
    app = _create_application(tmp_path)
    admission, state, parameter = _admit_output_speed(app)
    locator = AuthoritativeParameterLocator(
        project_id=PROJECT_ID,
        parameter_id=parameter.id,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
    )
    projection = project_authoritative_scalar(PROJECT_ID, state, locator)
    projected_speed = lower_projected_output_speed(projection)
    request = _request(state)
    policy = _policy_for_direct_drive()
    requirements = _requirements(projected_speed)

    outcome = app.realize_and_evaluate_revolute_drive(
        request=request,
        policy=policy,
        template_input=template(DriveArchitecture.DIRECT_DRIVE),
        requirements=requirements,
    )

    assert admission.revision == state.revision
    assert projection.value == parameter.value.value_rad_s
    assert projection.unit == "rad/s"
    assert projected_speed.value == projection.value * 60.0 / (2.0 * 3.141592653589793)
    assert request.source_binding.consumed_authority[0].path == "/authoritative_parameters"
    assert outcome.evaluation is not None
    assert outcome.evaluation.status is DriveAdmissibility.ADMISSIBLE
    assert outcome.evaluation.requirements_hash == requirements.requirements_hash
    assert outcome.evaluation.requirements_hash != "pending"
    speed_check = next(check for check in outcome.evaluation.checks if check.check_id == "motor-speed")
    assert speed_check.status.value == "satisfied"


def test_projected_m12_service_rejects_a_rehashed_caller_claim(tmp_path):
    app = _create_application(tmp_path)
    _, state, parameter = _admit_output_speed(app)
    locator = AuthoritativeParameterLocator(
        project_id=PROJECT_ID,
        parameter_id=parameter.id,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
    )
    original = project_authoritative_scalar(PROJECT_ID, state, locator)
    forged_payload = original.model_dump(mode="json")
    forged_payload["value"] = original.value + 1.0
    forged_payload["projection_hash"] = projection_hash(forged_payload)
    forged = CanonicalScalarProjection.model_validate(forged_payload)
    request = _request(state)

    outcome = app.realize_and_evaluate_revolute_drive(
        request=request,
        policy=_policy_for_direct_drive(),
        template_input=template(DriveArchitecture.DIRECT_DRIVE),
        requirements=_requirements(lower_projected_output_speed(forged)),
    )

    assert outcome.evaluation is not None
    assert outcome.evaluation.status is DriveAdmissibility.UNRESOLVED
    assert "recomputation" in " ".join(
        check.reason or "" for check in outcome.evaluation.checks
    )
