from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from mechcad_harness.application import ProductionApplication, ProductionStateBinding
from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.backends.freecad import FreeCADBackend
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.candidates import (
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
)
from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.revolute_drive import (
    DriveArchitecture,
    RevoluteDriveEngineeringRequirements,
    RevoluteDriveTemplateInput,
)
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.state import state_hash

from test_m12_revolute_drive_production import (
    _ALL_CONSUMED_PATHS,
    PROJECT_ID,
    policy_for,
    production_state,
    requirements,
    template,
)


SOURCE_LABEL = "M12-6 ACCEPTANCE FIXTURE SOURCE AUTHORITY"


class UninvokedAcceptanceAdapter:
    """Fail-fast boundary proving acceptance setup does not use an agent."""

    def __init__(self) -> None:
        self.call_count = 0

    @property
    def identity(self) -> str:
        return "m12-6-acceptance-uninvoked"

    def invoke(self, _request):
        self.call_count += 1
        raise AssertionError("M12-6 acceptance must not invoke an agent adapter")


@dataclass(frozen=True)
class DirectDriveFixture:
    app: ProductionApplication
    source: ProductionStateBinding
    source_artifacts: dict[str, EngineeringArtifact]
    source_artifact_run_id: str
    synthesis_request: CandidateSynthesisRequest
    synthesis_policy: CandidateSynthesisPolicy
    template_input: RevoluteDriveTemplateInput
    requirements: RevoluteDriveEngineeringRequirements
    ownership_path: Path
    dependency_path: Path
    acceptance_adapter: UninvokedAcceptanceAdapter
    source_label: str = SOURCE_LABEL


def write_project_configuration(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    ownership_path = tmp_path / "ownership.yaml"
    dependency_path = tmp_path / "dependencies.yaml"
    ownership_path.write_text(
        "ownership:\n"
        "  - path: /requirements/*\n"
        "    owner: transmission_engineer\n"
        "  - path: /physical_mechanisms/*\n"
        "    owner: mechcad-physical-mechanism\n",
        encoding="utf-8",
    )
    dependency_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/physical_mechanisms/*"],
                        "invalidates": [
                            "analysis.continuous_clearance_proof",
                            "analysis.kinematic_sweep",
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    return workspace, ownership_path, dependency_path


def direct_drive_state():
    """Return the real N=1 DesignState used as fixture source authority."""
    return production_state()


def _source_specification(specification, artifact):
    reference = GeometrySourceReference(
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_identity=f"{SOURCE_LABEL}:STEP:{artifact.artifact_id}",
    )
    return type(specification).model_validate(
        specification.model_dump(mode="json")
        | {
            "geometry_source": reference.model_dump(mode="json"),
            "specification_hash": "pending",
        }
    )


def publish_source_step_inputs(
    application: ProductionApplication,
    source: ProductionStateBinding,
) -> dict[str, EngineeringArtifact]:
    source_run = application.create_run().run
    dimensions = {
        "drive-motor": (30.0, 30.0, 5.0),
        "output-shaft": (20.0, 20.0, 5.0),
        "bearing-a": (20.0, 20.0, 5.0),
        "bearing-b": (20.0, 20.0, 5.0),
        "output-hub": (20.0, 20.0, 5.0),
    }
    artifacts = {}
    store = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id=source_run.run_id,
    )
    for instance_id, (length_mm, width_mm, thickness_mm) in dimensions.items():
        program = CadPartProgram(
            part_id=f"source-{instance_id}",
            operations=(
                BasePlateOperation(
                    operation_id=f"source-base-{instance_id}",
                    length_mm=length_mm,
                    width_mm=width_mm,
                    thickness_mm=thickness_mm,
                ),
            ),
        )
        generated = FreeCADBackend().generate_program(
            program,
            application.state_manager.workspace,
            project_id=application.project_id,
            run_id=source_run.run_id,
            revision=source.revision,
            state_hash=source.state_hash,
        )
        artifact = generated.step
        assert artifact.artifact_type is ArtifactType.STEP
        verified = store.read_verified_strict(
            artifact.artifact_id,
            expected_type=ArtifactType.STEP,
            expected_hash=artifact.sha256,
        )
        assert verified is not None
        artifacts[instance_id] = verified[0]
    return artifacts


def _validate_source(source: ProductionStateBinding) -> None:
    if source.state.revision != source.revision or state_hash(source.state) != source.state_hash:
        raise ValueError("captured source binding does not match its state snapshot")


def build_synthesis_request(
    application: ProductionApplication,
    source: ProductionStateBinding,
) -> CandidateSynthesisRequest:
    _validate_source(source)
    if application.project_id != source.project_id:
        raise ValueError("captured source belongs to a different project")
    request = CandidateSynthesisRequest(
        source_binding=CandidateSourceBinding(
            project_id=source.project_id,
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            consumed_authority=tuple(
                CandidateSourceReference(
                    path=path,
                    value_hash="pending",
                    authority=authority,
                )
                for path, authority in _ALL_CONSUMED_PATHS
            ),
        ).bound_to(source.state),
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )
    request.source_binding.validate_against(source.project_id, source.state)
    return request


def build_direct_policy() -> CandidateSynthesisPolicy:
    return policy_for(DriveArchitecture.DIRECT_DRIVE)


def build_direct_template(
    source_artifacts: dict[str, EngineeringArtifact],
) -> RevoluteDriveTemplateInput:
    source_template = template(DriveArchitecture.DIRECT_DRIVE)
    artifact_by_field = {
        "motor_specification": "drive-motor",
        "shaft_specification": "output-shaft",
        "bearing_a_specification": "bearing-a",
        "bearing_b_specification": "bearing-b",
        "hub_specification": "output-hub",
    }
    return source_template.model_copy(
        update={
            field: _source_specification(
                getattr(source_template, field), source_artifacts[instance_id]
            )
            for field, instance_id in artifact_by_field.items()
        }
    )


def build_direct_requirements(
    source: ProductionStateBinding,
    source_binding: CandidateSourceBinding,
) -> RevoluteDriveEngineeringRequirements:
    _validate_source(source)
    source_binding.validate_against(source.project_id, source.state)
    engineering = requirements(require_nominal_interface_compatibility=True)
    source_state_hash = state_hash(source.state)
    if source_state_hash != source.state_hash:
        raise ValueError("captured source state hash changed")
    expected_record_hashes = {
        reference.path: reference.value_hash
        for reference in source_binding.consumed_authority
    }
    if any(
        binding.source_record_hash != expected_record_hashes[binding.source_path]
        for binding in engineering.trusted_source_scalar_bindings
    ):
        raise ValueError("trusted requirement source binding does not match source snapshot")
    return engineering


def bootstrap_direct_drive_fixture(tmp_path: Path) -> DirectDriveFixture:
    # M12-6 ACCEPTANCE FIXTURE SOURCE AUTHORITY only.
    workspace, ownership_path, dependency_path = write_project_configuration(tmp_path)
    StateManager(workspace).create_project(PROJECT_ID, direct_drive_state())
    acceptance_adapter = UninvokedAcceptanceAdapter()
    app = ProductionApplication.create(
        workspace,
        PROJECT_ID,
        acceptance_adapter,
        ownership_path=ownership_path,
        dependency_path=dependency_path,
    )
    source = app.load_state()
    source_artifacts = publish_source_step_inputs(app, source)
    source_run_ids = {artifact.run_id for artifact in source_artifacts.values()}
    assert len(source_run_ids) == 1
    source_artifact_run_id = next(iter(source_run_ids))
    synthesis_request = build_synthesis_request(app, source)
    return DirectDriveFixture(
        app=app,
        source=source,
        source_artifacts=source_artifacts,
        source_artifact_run_id=source_artifact_run_id,
        synthesis_request=synthesis_request,
        synthesis_policy=build_direct_policy(),
        template_input=build_direct_template(source_artifacts),
        requirements=build_direct_requirements(source, synthesis_request.source_binding),
        ownership_path=ownership_path,
        dependency_path=dependency_path,
        acceptance_adapter=acceptance_adapter,
    )
