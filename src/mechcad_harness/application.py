import json
from pathlib import Path
from collections.abc import Callable
from typing import Iterable

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.agents import AgentAdapter, AgentIdentity, AgentRegistry, ContextBuilder
from mechcad_harness.agents.gateway import AgentGateway
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.dependency.errors import EvidenceIntegrityError
from mechcad_harness.artifacts.models import ArtifactType
from mechcad_harness.artifacts.storage import ArtifactStore
from mechcad_harness.models import DesignState
from mechcad_harness.runs import Run, RunController, SourceBinding, TaskDefinition
from mechcad_harness.runs.errors import RunIntegrityError
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.state.errors import StateIntegrityError
from mechcad_harness.cad_compilation import CadCompilationResult, CadCompilationService, MountingPlateDesignSpec
from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
from mechcad_harness.assembly_service import CadAssemblyGenerationService, default_assembly_service
from mechcad_harness.backends.freecad import FreeCADBackend
from mechcad_harness.imported_component import ImportedCadComponent, resolve_imported_component
from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistration, ToolRegistry
from mechcad_harness.models.common import Model
from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator, TransmissionToolRoundTripResult
from mechcad_harness.kinematic_sweep import (
    CadKinematicSweepRequest,
    CadKinematicSweepResult,
    CadKinematicSweepService,
    RevoluteAxis,
)
from mechcad_harness.transient_assembly_analysis import (
    TransientAssemblyAnalysisRequest,
    TransientAssemblyAnalysisService,
)
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider
from mechcad_harness.analysis_provenance import (
    AnalysisExecutionProvenance,
    ContinuousProofExecutionProvenance,
    DETERMINISTIC_EXECUTION_MODE,
    DETERMINISTIC_PROVIDER_NAME,
    DETERMINISTIC_PROVIDER_VERSION,
)
from mechcad_harness.models.evidence import Evidence
from mechcad_harness.continuous_proof import (
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisClearanceProof,
)
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicForwardKinematicsResult,
    KinematicModel,
    MultiJointKinematicsService,
    kinematic_model_hash,
    joint_configuration_hash,
)
from mechcad_harness.multi_joint_collision_sweep import (
    MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION,
    MultiJointCollisionSweepRequest,
    MultiJointCollisionSweepResult,
    MultiJointDiscreteCollisionSweepService,
)
from mechcad_harness.multi_joint_continuous_path import (
    MultiJointContinuousPathRequest,
    MultiJointPath,
)
from mechcad_harness.multi_joint_continuous_clearance import (
    MultiJointContinuousClearanceProofResult,
    MultiJointContinuousClearanceProofService,
    continuous_clearance_result_hash,
)
from mechcad_harness.structural.runtime import (
    FREECAD_IDENTITY,
    discover_calculix,
    discover_freecad,
    discover_gmsh,
)
from mechcad_harness.backends.provenance import provenance_from_identity
from mechcad_harness.structural.geometry import (
    StructuralFreeCADGeometryAdapter,
    StructuralRegionResolver,
)
from mechcad_harness.structural.mesh import ParsedMesh, StructuralGmshMeshingProvider
from mechcad_harness.structural.deck import StructuralDeckBuilder
from mechcad_harness.structural.preflight import ConstraintPreflight
from mechcad_harness.structural.solver import StructuralCalculiXSolverProvider
from mechcad_harness.structural.service import StructuralAnalysisService
from mechcad_harness.structural.evidence_service import (
    StructuralEvidencePublisher,
    StructuralRepeatabilityService,
    StructuralMeshConvergenceService,
    StructuralEvidenceVerifier,
)
from mechcad_harness.structural.evidence import (
    StructuralEvidenceCurrentness,
    StructuralEvidenceVerification,
    StructuralMeshConvergenceResult,
    StructuralMeshConvergenceStudy,
    StructuralRepeatabilityPolicy,
    StructuralRepeatabilityResult,
)
from mechcad_harness.structural_request import StructuralAnalysisRequest
from mechcad_harness.structural.results import (
    CalculiXDatResultParser,
    CalculiXFrdResultParser,
    parse_trusted_msh_bytes,
    StructuralAnalysisEvaluation,
    StructuralResultInterpreter,
    StructuralVerificationService,
)
from mechcad_harness.structural.models import (
    REGION_RESOLVER_IDENTITY,
    REGION_RESOLVER_VERSION,
    StructuralExecutionManifest,
    structural_result_hash,
)
from mechcad_harness.structural.validation import (
    CantileverGeometryObservation,
    CantileverMaterialObservation,
    RectangularCantileverValidationPolicy,
    StructuralAnalyticalValidationResult,
    StructuralAnalyticalValidator,
    cantilever_geometry_observation,
    cantilever_material_observation,
)


def _structural_model_snapshot(value):
    if value is None:
        return None
    return json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _structural_discovery_snapshot(discovery):
    return (
        type(discovery),
        discovery.available,
        discovery.executable,
        discovery.version,
        id(discovery.identity),
        _structural_model_snapshot(discovery.identity),
        id(discovery.provenance) if discovery.provenance is not None else None,
        _structural_model_snapshot(discovery.provenance),
    )


def _structural_tolerance_snapshot(tolerances):
    return (
        type(tolerances),
        tolerances.policy_id,
        tolerances.planarity_mm,
        tolerances.area_mm2,
        tolerances.centroid_mm,
        tolerances.normal_abs_dot,
    )


class ProductionStateBinding(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str = Field(min_length=1)
    state: DesignState
    revision: int = Field(gt=0)
    state_hash: str = Field(min_length=1)

    @field_validator("project_id", "state_hash")
    @classmethod
    def validate_strings(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def validate_state_revision(self):
        values = object.__getattribute__(self, "__dict__")
        if values["state"].revision != values["revision"]:
            raise ValueError("state revision does not match binding revision")
        return self

    def __getattribute__(self, name):
        value = super().__getattribute__(name)
        if name == "state" and isinstance(value, Model):
            return value.model_copy(deep=True)
        return value

class ProductionRunBinding(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run: Run
    source: ProductionStateBinding

    @model_validator(mode="after")
    def validate_run_source(self):
        checks = (
            self.run.project_id == self.source.project_id,
            self.run.initial_revision == self.source.revision,
            self.run.initial_state_hash == self.source.state_hash,
            self.run.active_revision == self.source.revision,
            self.run.active_state_hash == self.source.state_hash,
        )
        if not all(checks):
            raise ValueError("run binding does not match production state source")
        return self

    def __getattribute__(self, name):
        value = super().__getattribute__(name)
        if name in {"run", "source"} and isinstance(value, Model):
            return value.model_copy(deep=True)
        return value


class ProductionApplication:
    _READ_ONLY_DEPENDENCIES = frozenset({
        "state_manager",
        "run_controller",
        "agent_registry",
        "agent_gateway",
        "tool_registry",
        "tool_broker",
        "evidence_store",
        "change_engine",
        "context_builder",
        "cad_compiler",
        "structural_service",
        "_structural_frd_parser",
        "_structural_dat_parser",
        "_structural_verification_service",
        "_structural_evidence_publisher",
        "_structural_evidence_verifier",
        "_structural_repeatability_service",
        "_structural_mesh_convergence_service",
        "_composed_structural_geometry_adapter_id",
        "_composed_structural_geometry_discovery_id",
        "_composed_structural_geometry_discovery_snapshot",
        "_composed_structural_region_resolver_id",
        "_composed_structural_region_tolerances_id",
        "_composed_structural_region_tolerances_snapshot",
        "_composed_analytical_validation_factory",
        "standard_tool_permissions",
        "project_id",
        "kinematic_measure",
        "_kinematic_measurement_provider",
        "_kinematic_measurement_provider_attested",
    })
    _IDENTITY = AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )

    def __init__(
        self,
        *,
        project_id: str,
        state_manager: StateManager,
        run_controller: RunController,
        agent_registry: AgentRegistry,
        agent_gateway: AgentGateway,
        tool_registry: ToolRegistry,
        tool_broker: ToolBroker,
        evidence_store: EvidenceStore,
        change_engine: ChangeEngine,
        context_builder: ContextBuilder,
        kinematic_measure: Callable[
            [TransientAssemblyAnalysisRequest, CadAssemblyProgram],
            tuple[tuple[str, str, float, float], ...],
        ]
        | FreeCADTransientAssemblyMeasurementProvider
        | None = None,
    ):
        object.__setattr__(self, "project_id", project_id)
        self.state_manager = state_manager
        self.run_controller = run_controller
        self.agent_registry = agent_registry
        self.agent_gateway = agent_gateway
        self.tool_registry = tool_registry
        self.tool_broker = tool_broker
        self.evidence_store = evidence_store
        self.change_engine = change_engine
        self.context_builder = context_builder
        self.cad_compiler = CadCompilationService(state_manager)
        self.assembly_service = default_assembly_service(state_manager)
        self.standard_tool_permissions = tuple(
            f"{registration.name}@{registration.version}"
            for registration in BuiltinTools.registrations()
        )
        provider_was_created_by_default_composition = kinematic_measure is None
        if kinematic_measure is None or isinstance(kinematic_measure, FreeCADTransientAssemblyMeasurementProvider):
            provider = kinematic_measure or FreeCADTransientAssemblyMeasurementProvider(
                workspace=self.state_manager.workspace,
                project_id=project_id,
            )
            self._kinematic_measurement_provider = provider
            self.kinematic_measure = provider.exact_measure
        else:
            self._kinematic_measurement_provider = None
            self.kinematic_measure = kinematic_measure
        self._kinematic_measurement_provider_attested = (
            provider_was_created_by_default_composition
        )
        structural_geometry_adapter = StructuralFreeCADGeometryAdapter(discover_freecad())
        structural_region_resolver = StructuralRegionResolver()
        self.structural_service = StructuralAnalysisService(
            state_manager=state_manager,
            run_controller=run_controller,
            workspace=state_manager.workspace,
            geometry_adapter=structural_geometry_adapter,
            region_resolver=structural_region_resolver,
            gmsh_provider=StructuralGmshMeshingProvider(discover_gmsh()),
            deck_builder=StructuralDeckBuilder(),
            constraint_preflight=ConstraintPreflight(),
            calculix_provider=StructuralCalculiXSolverProvider(discover_calculix()),
        )
        object.__setattr__(
            self,
            "_composed_structural_geometry_adapter_id",
            id(structural_geometry_adapter),
        )
        object.__setattr__(
            self,
            "_composed_structural_geometry_discovery_id",
            id(structural_geometry_adapter._discovery),
        )
        object.__setattr__(
            self,
            "_composed_structural_geometry_discovery_snapshot",
            _structural_discovery_snapshot(structural_geometry_adapter._discovery),
        )
        object.__setattr__(
            self,
            "_composed_structural_region_resolver_id",
            id(structural_region_resolver),
        )
        object.__setattr__(
            self,
            "_composed_structural_region_tolerances_id",
            id(structural_region_resolver._tolerances),
        )
        object.__setattr__(
            self,
            "_composed_structural_region_tolerances_snapshot",
            _structural_tolerance_snapshot(structural_region_resolver._tolerances),
        )
        self._structural_frd_parser = CalculiXFrdResultParser()
        self._structural_dat_parser = CalculiXDatResultParser()
        self._structural_verification_service = StructuralVerificationService()
        self._structural_requests: dict[str, StructuralAnalysisRequest] = {}
        self._structural_evidence_verifier = StructuralEvidenceVerifier(
            workspace=state_manager.workspace,
            project_id=project_id,
            state_manager=state_manager,
            artifact_store=ArtifactStore(state_manager.workspace, project_id=project_id, run_id="PUBLISH"),
            evidence_store=evidence_store,
        )
        self._structural_repeatability_service = StructuralRepeatabilityService(
            self._structural_evidence_verifier
        )
        self._structural_mesh_convergence_service = StructuralMeshConvergenceService(
            self._structural_evidence_verifier
        )
        analytical_validation_factory = self._publish_structural_analytical_validation
        object.__setattr__(
            self,
            "_composed_analytical_validation_factory",
            analytical_validation_factory,
        )
        self._structural_evidence_publisher = StructuralEvidencePublisher(
            workspace=state_manager.workspace,
            project_id=project_id,
            state_manager=state_manager,
            artifact_store=ArtifactStore(state_manager.workspace, project_id=project_id, run_id="PUBLISH"),
            evidence_store=evidence_store,
            request_resolver=lambda request_hash: self._structural_requests.get(request_hash),
            analytical_validation_factory=analytical_validation_factory,
        )
        object.__setattr__(self, "_dependencies_initialized", True)

    def __setattr__(self, name, value):
        if name in self._READ_ONLY_DEPENDENCIES and getattr(self, "_dependencies_initialized", False):
            raise AttributeError(f"{name} is read-only")
        object.__setattr__(self, name, value)

    def _is_real_freecad_measurement_provider(self, provider) -> bool:
        return (
            self._kinematic_measurement_provider_attested
            and provider is self._kinematic_measurement_provider
            and type(provider) is FreeCADTransientAssemblyMeasurementProvider
            and provider.execute is None
            and provider.execute_in_workspace is None
            and type(provider.backend) is FreeCADBackend
        )

    def _persist_idempotent_evidence(self, evidence: Evidence) -> None:
        evidence_path = (
            self.state_manager.workspace
            / "projects"
            / self.project_id
            / "evidence"
            / f"{evidence.id}.json"
        )
        if not evidence_path.exists():
            self.evidence_store.write_evidence(self.project_id, evidence)
            return

        existing = self.evidence_store.load_evidence(self.project_id, evidence.id)

        def stable_payload(value: Evidence) -> dict:
            payload = value.model_dump(mode="json")
            for provenance_name in (
                "analysis_execution_provenance",
                "continuous_proof_execution_provenance",
            ):
                provenance = payload.get(provenance_name)
                if provenance is not None:
                    provenance.pop("recorded_at", None)
            return payload

        if stable_payload(existing) != stable_payload(evidence):
            raise EvidenceIntegrityError(
                f"existing evidence mismatch: {evidence.id}"
            )

    @classmethod
    def create(
        cls,
        workspace: str | Path,
        project_id: str,
        agent_adapter: AgentAdapter,
        *,
        ownership_path: str | Path,
        dependency_path: str | Path,
        additional_tool_registrations: Iterable[ToolRegistration] = (),
        kinematic_measure: Callable[
            [TransientAssemblyAnalysisRequest, CadAssemblyProgram],
            tuple[tuple[str, str, float, float], ...],
        ]
        | FreeCADTransientAssemblyMeasurementProvider
        | None = None,
    ) -> "ProductionApplication":
        if not project_id.strip():
            raise ValueError("project_id must not be empty")
        if agent_adapter is None:
            raise ValueError("agent_adapter is required")
        if not callable(getattr(agent_adapter, "invoke", None)) or not hasattr(agent_adapter, "identity"):
            raise ValueError("agent_adapter does not satisfy the agent adapter protocol")
        ownership = Path(ownership_path)
        dependencies = Path(dependency_path)
        if not ownership.exists() or not dependencies.exists():
            raise ValueError("ownership and dependency configuration files are required")

        state_manager = StateManager(workspace)
        graph = DependencyGraph.from_yaml(dependencies)
        evidence_store = EvidenceStore(workspace, state_manager, graph)
        ownership_policy = OwnershipPolicy.from_file(ownership)
        change_engine = ChangeEngine(state_manager, ownership_policy)
        controller = RunController(workspace, state_manager, change_engine, evidence_store)

        standard = BuiltinTools.registrations()
        tool_registry = ToolRegistry([*standard, *tuple(additional_tool_registrations)])
        for registration in standard:
            tool_registry.resolve(registration.name, registration.version)
        tool_broker = ToolBroker(controller, tool_registry)

        agent_registry = AgentRegistry()
        agent_registry.register(cls._IDENTITY, agent_adapter)
        context_builder = ContextBuilder(controller)
        gateway = AgentGateway(controller, agent_registry, context_builder, tool_broker=tool_broker)
        return cls(
            project_id=project_id,
            state_manager=state_manager,
            run_controller=controller,
            agent_registry=agent_registry,
            agent_gateway=gateway,
            tool_registry=tool_registry,
            tool_broker=tool_broker,
            evidence_store=evidence_store,
            change_engine=change_engine,
            context_builder=context_builder,
            kinematic_measure=kinematic_measure,
        )

    def load_state(self) -> ProductionStateBinding:
        try:
            state = self.state_manager.load_current_state(self.project_id)
            current = self.state_manager._read_current(self.project_id)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise StateIntegrityError(f"invalid current state binding: {self.project_id}") from exc
        computed_hash = state_hash(state)
        if state.revision != current["revision"] or computed_hash != current["state_hash"]:
            raise StateIntegrityError(f"current state binding mismatch: {self.project_id}")
        return ProductionStateBinding(
            project_id=self.project_id,
            state=state,
            revision=state.revision,
            state_hash=computed_hash,
        )

    def create_run(self, *, max_iterations: int = 3) -> ProductionRunBinding:
        source = self.load_state()
        run = self.run_controller.create_run(
            self.project_id,
            max_iterations=max_iterations,
            expected_source=SourceBinding(
                project_id=source.project_id,
                revision=source.revision,
                state_hash=source.state_hash,
            ),
        )
        persisted = self.run_controller.get_run(run.run_id, self.project_id)
        if (
            persisted.project_id != source.project_id
            or persisted.initial_revision != source.revision
            or persisted.initial_state_hash != source.state_hash
            or persisted.active_revision != source.revision
            or persisted.active_state_hash != source.state_hash
        ):
            raise RunIntegrityError("persisted run binding does not match loaded source")
        return ProductionRunBinding(run=persisted, source=source)

    def run_transmission_round_trip(
        self,
        *,
        selected_requirement_ids: tuple[str, ...] = (),
        max_iterations: int = 3,
    ) -> TransmissionToolRoundTripResult:
        run_binding = self.create_run(max_iterations=max_iterations)
        source = run_binding.source
        run = run_binding.run
        if (
            run.project_id != source.project_id
            or run.active_revision != source.revision
            or run.active_state_hash != source.state_hash
        ):
            raise RunIntegrityError("production run source binding mismatch")

        task = TaskDefinition(
            task_id="TASK-transmission-roundtrip",
            run_id=run.run_id,
            task_type="agent",
            objective="Perform bounded transmission torque round trip.",
            bound_revision=source.revision,
            bound_state_hash=source.state_hash,
            allowed_tools=("mechcad-calc-torque@1.0",),
        )
        self.run_controller.add_task(run.run_id, task)

        coordinator = TransmissionToolRoundTripCoordinator(
            self.run_controller,
            self.agent_gateway,
            self.agent_registry,
        )
        return coordinator.run(
            run.run_id,
            task.task_id,
            self._IDENTITY.agent_name,
            self._IDENTITY.agent_version,
            selected_requirement_ids=tuple(selected_requirement_ids),
        )

    def compile_design_spec(
        self,
        *,
        source_revision: int,
        source_state_hash: str,
        spec: MountingPlateDesignSpec,
    ) -> CadCompilationResult:
        return self.cad_compiler.compile_mounting_plate(
            project_id=self.project_id,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            spec=spec,
        )

    def build_assembly_with_imported_components(
        self,
        *,
        source_revision: int,
        source_state_hash: str,
        assembly_id: str,
        generated_parts: tuple[CadPartProgram, ...] = (),
        imported_components: tuple[ImportedCadComponent, ...] = (),
        instances: tuple[CadComponentInstance, ...] = (),
        run_id: str,
    ):
        binding = self.assembly_service.validate_source(
            self.project_id, source_revision, source_state_hash
        )

        program = CadAssemblyProgram(
            assembly_id=assembly_id,
            parts=generated_parts,
            imported_components=imported_components,
            instances=instances,
        )

        workspace = str(self.state_manager.workspace)
        return self.assembly_service.generate_assembly_with_imported(
            project_id=binding.project_id,
            run_id=run_id,
            revision=binding.revision,
            state_hash=binding.state_hash,
            program=program,
            workspace=workspace,
        )

    def analyze_assembly_kinematics(
        self,
        *,
        source_revision: int,
        source_state_hash: str,
        assembly: CadAssemblyProgram,
        axis: RevoluteAxis,
        moving_instance_ids: tuple[str, ...],
        stationary_instance_ids: tuple[str, ...],
        sample_angles_deg: tuple[float, ...],
    ) -> CadKinematicSweepResult:
        binding = self.assembly_service.validate_source(
            self.project_id, source_revision, source_state_hash
        )

        source_assembly_hash = assembly_hash(assembly)
        request = CadKinematicSweepRequest(
            source_assembly_id=assembly.assembly_id,
            source_assembly_hash=source_assembly_hash,
            axis=axis,
            sample_angles_deg=sample_angles_deg,
            moving_instance_ids=moving_instance_ids,
            stationary_instance_ids=stationary_instance_ids,
        )

        measure = self.kinematic_measure

        transient_service = TransientAssemblyAnalysisService(measure)
        sweep_service = CadKinematicSweepService(transient_analysis_service=transient_service)
        sweep = sweep_service.execute(request, assembly)

        self._record_kinematic_sweep_provenance(
            request=request,
            sweep=sweep,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
        )
        return sweep

    def _record_kinematic_sweep_provenance(self, *, request, sweep, source_revision, source_state_hash) -> None:
        # Trust boundary: provider/backend identity is derived from the composed
        # provider object, never from caller-supplied provenance fields.
        provider = self._kinematic_measurement_provider
        if self._is_real_freecad_measurement_provider(provider):
            provenance = AnalysisExecutionProvenance(
                request_hash=request.request_hash,
                result_hash=sweep.result_hash,
                source_assembly_hash=request.source_assembly_hash,
                sweep_version=request.sweep_version,
                provider_name=provider.provider_name,
                provider_version=provider.provider_version,
                execution_mode=provider.execution_mode,
                backend_provenance=provider.provenance(),
            )
        else:
            provenance = AnalysisExecutionProvenance(
                request_hash=request.request_hash,
                result_hash=sweep.result_hash,
                source_assembly_hash=request.source_assembly_hash,
                sweep_version=request.sweep_version,
                provider_name=DETERMINISTIC_PROVIDER_NAME,
                provider_version=DETERMINISTIC_PROVIDER_VERSION,
                execution_mode=DETERMINISTIC_EXECUTION_MODE,
                backend_provenance=None,
            )

        import hashlib

        evidence_id = f"EVD-KSWEEP-{hashlib.sha256((request.request_hash + sweep.result_hash).encode()).hexdigest()[:24]}"
        evidence = Evidence(
            id=evidence_id,
            kind="analysis.kinematic_sweep",
            summary="Trusted execution provenance for CadKinematicSweepResult",
            revision=source_revision,
            state_hash=source_state_hash,
            producer_type="kinematic_sweep_provider",
            producer_name=provenance.provider_name,
            producer_version=provenance.provider_version,
            producer_result_id=sweep.result_hash,
            input_hash=request.request_hash,
            output_hash=sweep.result_hash,
            backend_provenance=provenance.backend_provenance,
            analysis_execution_provenance=provenance,
        )
        try:
            self.evidence_store.load_evidence(self.project_id, evidence_id)
        except Exception:
            self.evidence_store.write_evidence(self.project_id, evidence)

    def get_kinematic_sweep_evidence(self, result_hash: str):
        evidence_dir = self.state_manager.workspace / "projects" / self.project_id / "evidence"
        if not evidence_dir.is_dir():
            return None
        for path in sorted(evidence_dir.glob("*.json")):
            try:
                evidence = self.evidence_store.load_evidence(self.project_id, path.stem)
            except Exception:
                continue
            if evidence.kind == "analysis.kinematic_sweep" and evidence.producer_result_id == result_hash:
                return evidence
        return None

    def analyze_multi_joint_collision_sweep(
        self,
        *,
        source_revision: int,
        source_state_hash: str,
        assembly: CadAssemblyProgram,
        model: KinematicModel,
        configurations: tuple[JointConfiguration, ...],
        moving_instance_ids: tuple[str, ...],
        stationary_instance_ids: tuple[str, ...],
    ) -> MultiJointCollisionSweepResult:
        self.assembly_service.validate_source(
            self.project_id, source_revision, source_state_hash
        )

        source_assembly_hash = assembly_hash(assembly)
        request = MultiJointCollisionSweepRequest(
            source_assembly_id=assembly.assembly_id,
            source_assembly_hash=source_assembly_hash,
            model=model,
            configurations=configurations,
            moving_instance_ids=moving_instance_ids,
            stationary_instance_ids=stationary_instance_ids,
            evaluator_version=MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION,
        )
        transient_service = TransientAssemblyAnalysisService(self.kinematic_measure)
        sweep_service = MultiJointDiscreteCollisionSweepService(
            transient_analysis_service=transient_service,
        )
        result = sweep_service.execute(request, assembly)

        self._record_multi_joint_collision_sweep_provenance(
            request=request,
            result=result,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
        )
        return result

    def _record_multi_joint_collision_sweep_provenance(
        self,
        *,
        request: MultiJointCollisionSweepRequest,
        result: MultiJointCollisionSweepResult,
        source_revision: int,
        source_state_hash: str,
    ) -> None:
        provider = self._kinematic_measurement_provider
        if self._is_real_freecad_measurement_provider(provider):
            provider_name = provider.provider_name
            provider_version = provider.provider_version
            execution_mode = provider.execution_mode
            backend_provenance = provider.provenance()
        else:
            provider_name = DETERMINISTIC_PROVIDER_NAME
            provider_version = DETERMINISTIC_PROVIDER_VERSION
            execution_mode = DETERMINISTIC_EXECUTION_MODE
            backend_provenance = None

        provenance = AnalysisExecutionProvenance(
            request_hash=request.request_hash,
            result_hash=result.result_hash,
            source_assembly_hash=request.source_assembly_hash,
            model_hash=kinematic_model_hash(request.model),
            sweep_version=result.evaluator_version,
            provider_name=provider_name,
            provider_version=provider_version,
            execution_mode=execution_mode,
            backend_provenance=backend_provenance,
        )

        import hashlib

        evidence_id = (
            "EVD-MJCS-"
            + hashlib.sha256(
                (request.request_hash + result.result_hash).encode("utf-8")
            ).hexdigest()[:24]
        )
        evidence = Evidence(
            id=evidence_id,
            kind="analysis.multi_joint_collision_sweep",
            summary="Trusted execution provenance for multi-joint collision sweep",
            revision=source_revision,
            state_hash=source_state_hash,
            producer_type="multi_joint_collision_sweep_provider",
            producer_name=provenance.provider_name,
            producer_version=provenance.provider_version,
            producer_result_id=result.result_hash,
            input_hash=request.request_hash,
            output_hash=result.result_hash,
            backend_provenance=provenance.backend_provenance,
            analysis_execution_provenance=provenance,
        )
        self._persist_idempotent_evidence(evidence)

    def get_multi_joint_collision_sweep_evidence(self, result_hash: str):
        evidence_dir = self.state_manager.workspace / "projects" / self.project_id / "evidence"
        if not evidence_dir.is_dir():
            return None
        for path in sorted(evidence_dir.glob("*.json")):
            strict_path = path.stem.startswith("EVD-MJCS-")
            try:
                evidence = self.evidence_store.load_evidence(self.project_id, path.stem)
            except Exception as exc:
                strict_kind = False
                if not strict_path:
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, TypeError, ValueError):
                        payload = None
                    strict_kind = (
                        isinstance(payload, dict)
                        and payload.get("kind")
                        == "analysis.multi_joint_collision_sweep"
                    )
                if strict_path or strict_kind:
                    if isinstance(exc, EvidenceIntegrityError):
                        raise
                    raise EvidenceIntegrityError(
                        f"invalid M10-3 evidence record: {path}"
                    ) from exc
                continue
            if (
                evidence.kind == "analysis.multi_joint_collision_sweep"
                and evidence.producer_result_id == result_hash
            ):
                return evidence
        return None

    def prove_continuous_single_axis_clearance(
        self,
        *,
        source_revision: int,
        source_state_hash: str,
        assembly: CadAssemblyProgram,
        axis: RevoluteAxis,
        moving_instance_ids: tuple[str, ...],
        stationary_instance_ids: tuple[str, ...],
        start_angle_deg: float,
        end_angle_deg: float,
        required_clearance_mm: float = 0.0,
        proof_guard_mm: float = 1e-6,
        max_depth: int = 16,
        minimum_interval_deg: float = 1e-6,
        max_exact_evaluations: int = 4096,
    ) -> ContinuousSingleAxisProofResult:
        binding = self.assembly_service.validate_source(
            self.project_id, source_revision, source_state_hash
        )
        source_assembly_hash = assembly_hash(assembly)
        request = ContinuousSingleAxisProofRequest(
            source_assembly_id=assembly.assembly_id,
            source_assembly_hash=source_assembly_hash,
            axis=axis,
            start_angle_deg=start_angle_deg,
            end_angle_deg=end_angle_deg,
            moving_instance_ids=moving_instance_ids,
            stationary_instance_ids=stationary_instance_ids,
            required_clearance_mm=required_clearance_mm,
            proof_guard_mm=proof_guard_mm,
            max_depth=max_depth,
            minimum_interval_deg=minimum_interval_deg,
            max_exact_evaluations=max_exact_evaluations,
        )

        provider = self._kinematic_measurement_provider
        if not self._is_real_freecad_measurement_provider(provider):
            raise ValueError("continuous proof requires the real FreeCAD measurement provider for geometry radial bounds")

        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=self.kinematic_measure,
            radial_bound_provider=provider.geometry_radial_bounds,
        )
        result = proof.prove(request, assembly)

        self._record_continuous_proof_provenance(
            request=request,
            result=result,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
        )
        return result

    def prove_continuous_multi_joint_path_clearance(
        self,
        *,
        source_revision: int,
        source_state_hash: str,
        assembly: CadAssemblyProgram,
        model: KinematicModel,
        path: MultiJointPath,
        moving_instance_ids: tuple[str, ...],
        stationary_instance_ids: tuple[str, ...],
        required_clearance_mm: float = 0.0,
        proof_guard_mm: float = 1e-6,
        max_depth: int = 16,
        minimum_path_interval: float = 1e-6,
        max_exact_evaluations: int = 4096,
    ) -> MultiJointContinuousClearanceProofResult:
        self.assembly_service.validate_source(self.project_id, source_revision, source_state_hash)
        provider = self._kinematic_measurement_provider
        if not self._is_real_freecad_measurement_provider(provider):
            raise ValueError("continuous multi-joint proof requires the real FreeCAD measurement provider")
        request = MultiJointContinuousPathRequest(
            source_assembly_id=assembly.assembly_id,
            source_assembly_hash=assembly_hash(assembly),
            model=model,
            path=path,
            moving_instance_ids=moving_instance_ids,
            stationary_instance_ids=stationary_instance_ids,
            required_clearance_mm=required_clearance_mm,
            proof_guard_mm=proof_guard_mm,
            max_depth=max_depth,
            minimum_path_interval=minimum_path_interval,
            max_exact_evaluations=max_exact_evaluations,
        )
        service = MultiJointContinuousClearanceProofService(
            exact_measure=self.kinematic_measure,
            extent_provider=lambda source, requested_model, instance_ids: provider.trusted_local_geometry_extents(source, instance_ids),
        )
        result = service.execute(request, assembly)
        self._record_multi_joint_continuous_proof_provenance(
            request=request,
            result=result,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
        )
        return result

    def _record_multi_joint_continuous_proof_provenance(self, *, request, result, source_revision, source_state_hash):
        provider = self._kinematic_measurement_provider
        provenance = ContinuousProofExecutionProvenance(
            request_hash=request.request_hash,
            result_hash=result.result_hash,
            source_assembly_hash=request.source_assembly_hash,
            model_hash=request.model_hash,
            path_hash=request.path.path_hash,
            proof_algorithm_version=result.proof_algorithm_version,
            reach_bound_algorithm_version=result.reach_bound_algorithm_version,
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            execution_mode=provider.execution_mode,
            backend_provenance=provider.provenance(),
        )
        import hashlib
        evidence_id = "EVD-MJCP-" + hashlib.sha256((request.request_hash + result.result_hash).encode()).hexdigest()[:24]
        evidence = Evidence(
            id=evidence_id,
            kind="analysis.continuous_multi_joint_clearance_proof",
            summary="Trusted execution provenance for continuous multi-joint path clearance proof",
            revision=source_revision,
            state_hash=source_state_hash,
            producer_type="continuous_multi_joint_clearance_proof",
            producer_name=provenance.provider_name,
            producer_version=provenance.provider_version,
            producer_result_id=result.result_hash,
            input_hash=request.request_hash,
            output_hash=result.result_hash,
            backend_provenance=provenance.backend_provenance,
            continuous_proof_execution_provenance=provenance,
            continuous_multi_joint_clearance_proof_result_payload=result.model_dump(mode="json"),
        )
        self._persist_idempotent_evidence(evidence)

    def get_multi_joint_continuous_proof_evidence(self, result_hash: str):
        evidence_dir = self.state_manager.workspace / "projects" / self.project_id / "evidence"
        if not evidence_dir.is_dir():
            return None
        for path in sorted(evidence_dir.glob("EVD-MJCP-*.json")):
            evidence = self.evidence_store.load_evidence(self.project_id, path.stem)
            if evidence.producer_result_id == result_hash:
                return evidence
        return None

    def get_multi_joint_continuous_proof_result(self, result_hash: str):
        evidence = self.get_multi_joint_continuous_proof_evidence(result_hash)
        if evidence is None:
            return None
        payload = evidence.continuous_multi_joint_clearance_proof_result_payload
        if payload is None:
            raise EvidenceIntegrityError(
                f"M10-4 evidence result payload missing: {result_hash}"
            )
        result = MultiJointContinuousClearanceProofResult.model_validate(payload)
        if result.result_hash != result_hash or result.result_hash != continuous_clearance_result_hash(result):
            raise EvidenceIntegrityError(
                f"M10-4 evidence result payload mismatch: {result_hash}"
            )
        return result

    def _record_continuous_proof_provenance(self, *, request, result, source_revision, source_state_hash) -> None:
        provider = self._kinematic_measurement_provider
        if self._is_real_freecad_measurement_provider(provider):
            provenance = ContinuousProofExecutionProvenance(
                request_hash=request.request_hash,
                result_hash=result.result_hash,
                source_assembly_hash=request.source_assembly_hash,
                proof_algorithm_version=result.proof_algorithm_version,
                provider_name=provider.provider_name,
                provider_version=provider.provider_version,
                execution_mode=provider.execution_mode,
                backend_provenance=provider.provenance(),
            )
        else:
            provenance = ContinuousProofExecutionProvenance(
                request_hash=request.request_hash,
                result_hash=result.result_hash,
                source_assembly_hash=request.source_assembly_hash,
                proof_algorithm_version=result.proof_algorithm_version,
                provider_name=DETERMINISTIC_PROVIDER_NAME,
                provider_version=DETERMINISTIC_PROVIDER_VERSION,
                execution_mode=DETERMINISTIC_EXECUTION_MODE,
                backend_provenance=None,
            )

        import hashlib
        evidence_id = f"EVD-CPROOF-{hashlib.sha256((request.request_hash + result.result_hash).encode()).hexdigest()[:24]}"
        evidence = Evidence(
            id=evidence_id,
            kind="analysis.continuous_clearance_proof",
            summary="Trusted execution provenance for continuous single-axis clearance proof",
            revision=source_revision,
            state_hash=source_state_hash,
            producer_type="continuous_clearance_proof",
            producer_name=provenance.provider_name,
            producer_version=provenance.provider_version,
            producer_result_id=result.result_hash,
            input_hash=request.request_hash,
            output_hash=result.result_hash,
            backend_provenance=provenance.backend_provenance,
            continuous_proof_execution_provenance=provenance,
        )
        try:
            self.evidence_store.load_evidence(self.project_id, evidence_id)
        except Exception:
            self.evidence_store.write_evidence(self.project_id, evidence)

    def get_continuous_proof_evidence(self, result_hash: str):
        evidence_dir = self.state_manager.workspace / "projects" / self.project_id / "evidence"
        if not evidence_dir.is_dir():
            return None
        for path in sorted(evidence_dir.glob("*.json")):
            try:
                evidence = self.evidence_store.load_evidence(self.project_id, path.stem)
            except Exception:
                continue
            if evidence.kind == "analysis.continuous_clearance_proof" and evidence.producer_result_id == result_hash:
                return evidence
        return None

    def execute_structural_analysis(
        self,
        *,
        request: StructuralAnalysisRequest,
    ):
        """Trusted source-bound single-solid linear-static structural preparation
        pipeline (M11-3): geometry admission, semantic region resolution, Gmsh
        C3D10 meshing, deterministic CalculiX deck lowering, rigid-body constraint
        preflight, real CalculiX execution, and durable raw-artifact provenance.

        Produces only the trusted execution manifest.  Result interpretation and
        criterion evaluation are explicit in evaluate_structural_analysis; neither
        path publishes structural Evidence."""
        source_before = self.load_state()
        execution = self.structural_service.execute(request)
        self._assert_structural_source_unchanged(source_before, "structural execution")
        if execution.manifest is not None:
            self._structural_requests[request.request_hash] = request
        return execution

    def publish_structural_evidence(
        self,
        *,
        execution_manifest,
        request: StructuralAnalysisRequest | None = None,
        analytical_policy=None,
        execution_manifest_artifact_id: str | None = None,
        execution_manifest_artifact_hash: str | None = None,
    ) -> Evidence:
        return self._structural_evidence_publisher.publish(
            execution_manifest=execution_manifest,
            request=request,
            analytical_policy=analytical_policy,
            execution_manifest_artifact_id=execution_manifest_artifact_id,
            execution_manifest_artifact_hash=execution_manifest_artifact_hash,
        )

    def verify_structural_evidence(self, evidence_id: str) -> StructuralEvidenceVerification:
        return self._structural_evidence_verifier.verify(evidence_id)

    def check_structural_evidence_currentness(self, evidence_id: str) -> StructuralEvidenceCurrentness:
        return self._structural_evidence_verifier.currentness(evidence_id)

    def compare_structural_repeatability(
        self,
        *,
        policy: StructuralRepeatabilityPolicy,
        first_evidence_id: str,
        second_evidence_id: str,
    ) -> StructuralRepeatabilityResult:
        return self._structural_repeatability_service.compare(
            policy=policy,
            first_evidence_id=first_evidence_id,
            second_evidence_id=second_evidence_id,
        )

    def evaluate_structural_mesh_convergence(
        self,
        *,
        study: StructuralMeshConvergenceStudy,
        level_evidence_ids: tuple[str, ...],
    ) -> StructuralMeshConvergenceResult:
        return self._structural_mesh_convergence_service.evaluate(
            study=study,
            level_evidence_ids=level_evidence_ids,
        )

    def publish_structural_mesh_convergence(
        self,
        *,
        study: StructuralMeshConvergenceStudy,
        level_evidence_ids: tuple[str, ...],
    ) -> Evidence:
        return self._structural_mesh_convergence_service.publish(
            study=study,
            level_evidence_ids=level_evidence_ids,
        )

    def _assert_structural_source_unchanged(self, source_before, operation: str) -> None:
        source_after = self.load_state()
        if (
            source_after.revision != source_before.revision
            or source_after.state_hash != source_before.state_hash
        ):
            raise StateIntegrityError(f"source revision/state changed during {operation}")

    def _publish_structural_analytical_validation(
        self,
        *,
        execution_manifest,
        request,
        definition,
        result,
        verification,
        analytical_policy,
        mesh_artifact_bytes,
    ):
        mesh = parse_trusted_msh_bytes(mesh_artifact_bytes)
        store = ArtifactStore(
            self.state_manager.workspace,
            project_id=self.project_id,
            run_id=execution_manifest.run_id,
        )
        try:
            source_verified = store.read_verified_in_project(
                request.source_binding.geometry_artifact_id,
                expected_type=ArtifactType.STEP,
                expected_hash=request.source_binding.geometry_artifact_hash,
            )
            if source_verified is None:
                raise ValueError("trusted source STEP artifact is unavailable")
            source_artifact, _source_bytes = source_verified
            source_path = store.path_for_in_project(source_artifact)
            if source_path is None:
                raise ValueError("trusted source STEP artifact is unavailable")
            self._assert_composed_structural_dependencies(execution_manifest)
            realization = self.structural_service.geometry_adapter.realize_geometry(source_path)
            region_map = self.structural_service.region_resolver.resolve(
                definition.regions,
                realization,
                source_geometry_hash=request.source_binding.geometry_artifact_hash,
            )
            geometry_observation = cantilever_geometry_observation(
                request, definition, realization, region_map,
            )
            material_observation = cantilever_material_observation(request, definition)
            validation = StructuralAnalyticalValidator().validate(
                result,
                analytical_policy,
                request=request,
                execution_manifest=execution_manifest,
                mesh=mesh,
                mesh_artifact_bytes=mesh_artifact_bytes,
                geometry_observation=geometry_observation,
                material_observation=material_observation,
                definition=definition,
            )
        except Exception as exc:
            raise ValueError("trusted analytical source observations are unavailable") from exc
        return validation, geometry_observation, material_observation

    def _assert_composed_structural_dependencies(self, execution_manifest) -> None:
        if (
            self._structural_evidence_publisher.analytical_validation_factory
            is not self._composed_analytical_validation_factory
        ):
            raise ValueError("composed analytical validation factory is untrusted")
        geometry_adapter = self.structural_service.geometry_adapter
        discovery = getattr(geometry_adapter, "_discovery", None)
        adapter_provenance = getattr(
            discovery, "provenance", None
        )
        if (
            type(geometry_adapter) is not StructuralFreeCADGeometryAdapter
            or id(geometry_adapter) != self._composed_structural_geometry_adapter_id
            or type(discovery) is not self._composed_structural_geometry_discovery_snapshot[0]
            or id(discovery) != self._composed_structural_geometry_discovery_id
            or _structural_discovery_snapshot(discovery)
            != self._composed_structural_geometry_discovery_snapshot
            or adapter_provenance != execution_manifest.geometry_provider_provenance
            or adapter_provenance != provenance_from_identity(FREECAD_IDENTITY)
        ):
            raise ValueError("composed structural geometry adapter provenance is untrusted")
        region_resolver = self.structural_service.region_resolver
        tolerances = getattr(region_resolver, "_tolerances", None)
        if (
            type(region_resolver) is not StructuralRegionResolver
            or id(region_resolver) != self._composed_structural_region_resolver_id
            or id(tolerances) != self._composed_structural_region_tolerances_id
            or _structural_tolerance_snapshot(tolerances)
            != self._composed_structural_region_tolerances_snapshot
            or region_resolver.identity != execution_manifest.resolver_identity
            or region_resolver.resolver_version != execution_manifest.resolver_version
            or region_resolver.identity != REGION_RESOLVER_IDENTITY
            or region_resolver.resolver_version != REGION_RESOLVER_VERSION
        ):
            raise ValueError("composed structural region resolver provenance is untrusted")

    def evaluate_structural_analysis(
        self,
        *,
        execution_manifest,
        request: StructuralAnalysisRequest | None = None,
        definition=None,
    ) -> StructuralAnalysisEvaluation:
        """Interpret one successful execution and evaluate canonical criteria.

        This method deliberately has no EvidenceStore side effects.  The request
        is retained only for the same-process execute-then-evaluate path; callers
        may provide it explicitly when reloading a durable manifest.
        """
        if execution_manifest is None:
            raise ValueError("execution manifest is required")
        request = request or self._structural_requests.get(execution_manifest.request_hash)
        if request is None:
            raise ValueError("the bound structural request is required for interpretation")
        execution_manifest = self._reload_structural_execution_manifest(execution_manifest, request)
        if definition is None:
            state = self.state_manager.load_revision(
                execution_manifest.project_id, execution_manifest.revision,
            )
            definition = next(
                (candidate for candidate in state.structural_analysis_definitions
                 if candidate.id == execution_manifest.definition_id),
                None,
            )
            if definition is None:
                raise ValueError("the bound structural definition is missing")
        source_before = self.load_state()
        result = StructuralResultInterpreter(
            workspace=self.state_manager.workspace,
            project_id=self.project_id,
            request=request,
            definition=definition,
            frd_parser=self._structural_frd_parser,
            dat_parser=self._structural_dat_parser,
        ).interpret(execution_manifest)
        verification = self._structural_verification_service.evaluate(result, definition)
        self._assert_structural_source_unchanged(source_before, "structural evaluation")
        return StructuralAnalysisEvaluation(result=result, verification=verification)

    def _reload_structural_execution_manifest(self, supplied_manifest, request):
        try:
            manifest_artifact_id = "STRUCT-JSON-" + __import__("hashlib").sha256(
                f"{request.request_hash}|json".encode("utf-8")
            ).hexdigest()[:16]
            store = ArtifactStore(
                self.state_manager.workspace,
                project_id=supplied_manifest.project_id,
                run_id=supplied_manifest.run_id,
            )
            verified = store.read_verified(
                manifest_artifact_id,
                expected_type=ArtifactType.JSON,
            )
        except Exception as exc:
            raise ValueError("durable execution manifest is unavailable or untrusted") from exc
        if verified is None:
            raise ValueError("durable execution manifest is unavailable or untrusted")
        artifact, content = verified
        try:
            durable_manifest = StructuralExecutionManifest.model_validate_json(content)
        except Exception as exc:
            raise ValueError("durable execution manifest is malformed") from exc
        binding = request.source_binding
        if (
            artifact.input_hash != request.request_hash
            or artifact.project_id != self.project_id
            or artifact.run_id != durable_manifest.run_id
            or artifact.bound_revision != durable_manifest.revision
            or artifact.bound_state_hash != durable_manifest.state_hash
            or artifact.producer_tool_name != durable_manifest.deck_builder_identity
            or artifact.producer_tool_version != durable_manifest.deck_builder_version
            or durable_manifest.project_id != self.project_id
            or durable_manifest.project_id != binding.project_id
            or durable_manifest.revision != binding.source_revision
            or durable_manifest.state_hash != binding.source_state_hash
            or durable_manifest.definition_id != binding.definition_id
            or durable_manifest.definition_hash != binding.definition_hash
            or durable_manifest.request_hash != request.request_hash
            or durable_manifest.analytical_policy_hash != request.analytical_policy_hash
            or durable_manifest.geometry_artifact_id != binding.geometry_artifact_id
            or durable_manifest.geometry_artifact_hash != binding.geometry_artifact_hash
            or durable_manifest != supplied_manifest
        ):
            raise ValueError("durable execution manifest does not match supplied manifest/request binding")
        return durable_manifest

    def evaluate_structural_analytical_validation(
        self,
        *,
        execution_manifest,
        evaluation: StructuralAnalysisEvaluation,
        policy: RectangularCantileverValidationPolicy,
        mesh: ParsedMesh,
        geometry_observation: CantileverGeometryObservation | None,
        material_observation: CantileverMaterialObservation | None,
        request: StructuralAnalysisRequest | None = None,
        definition=None,
    ) -> StructuralAnalyticalValidationResult:
        """Run analytical validation from authoritative persisted inputs.

        Ordinary structural evaluation never selects analytical assumptions. The
        policy is predeclared, while mesh, geometry, and material observations
        are reloaded or rebuilt inside this application rather than trusted from
        caller-owned snapshots.
        """
        if not isinstance(evaluation, StructuralAnalysisEvaluation):
            raise TypeError("analytical validation requires a typed structural evaluation")
        if not isinstance(policy, RectangularCantileverValidationPolicy):
            raise TypeError("analytical validation requires a predeclared cantilever policy")
        request = request or self._structural_requests.get(execution_manifest.request_hash)
        if request is None:
            raise ValueError("the bound structural request is required for analytical validation")
        execution_manifest = self._reload_structural_execution_manifest(execution_manifest, request)
        if definition is None:
            state = self.state_manager.load_revision(
                execution_manifest.project_id, execution_manifest.revision,
            )
            definition = next(
                (candidate for candidate in state.structural_analysis_definitions
                 if candidate.id == execution_manifest.definition_id),
                None,
            )
            if definition is None:
                raise ValueError("the bound structural definition is missing")
        self._assert_composed_structural_dependencies(execution_manifest)
        source_before = self.load_state()
        interpreter = StructuralResultInterpreter(
            workspace=self.state_manager.workspace,
            project_id=self.project_id,
            request=request,
            definition=definition,
            frd_parser=self._structural_frd_parser,
            dat_parser=self._structural_dat_parser,
        )
        trusted_result = interpreter.interpret(
            execution_manifest, request=request, definition=definition,
        )
        supplied_result_hash = structural_result_hash(evaluation.result)
        if (
            evaluation.result.result_hash != supplied_result_hash
            or supplied_result_hash != trusted_result.result_hash
        ):
            raise ValueError("supplied evaluation result hash does not match fresh trusted result")
        trusted_mesh, mesh_artifact_bytes = interpreter.load_trusted_mesh(
            execution_manifest, request=request, definition=definition,
        )
        source_artifact_match = ArtifactStore(
            self.state_manager.workspace,
            project_id=self.project_id,
            run_id=execution_manifest.run_id,
        ).read_verified_in_project(
            request.source_binding.geometry_artifact_id,
            expected_type=ArtifactType.STEP,
            expected_hash=request.source_binding.geometry_artifact_hash,
        )
        if source_artifact_match is None:
            raise ValueError("trusted source STEP artifact is unavailable")
        source_artifact, _source_bytes = source_artifact_match
        source_refs = tuple(
            ref for ref in execution_manifest.artifacts
            if ref.artifact_id == source_artifact.artifact_id
        )
        if (
            source_artifact.artifact_type is not ArtifactType.STEP
            or source_artifact.sha256 != request.source_binding.geometry_artifact_hash
            or source_artifact.bound_revision != request.source_binding.source_revision
            or source_artifact.bound_state_hash != request.source_binding.source_state_hash
            or source_artifact.project_id != request.source_binding.project_id
            or source_artifact.producer_tool_name != "mechcad-freecad"
            or source_artifact.producer_tool_version
            != execution_manifest.geometry_provider_provenance.backend_adapter_version
            or source_artifact.input_hash != request.source_binding.source_program_hash
            or source_artifact.backend_provenance != execution_manifest.geometry_provider_provenance
            or not StructuralResultInterpreter._is_trusted_freecad_provenance(
                source_artifact.backend_provenance
            )
        ):
            raise ValueError("trusted source STEP artifact input binding/provenance mismatch")
        if len(source_refs) != 1:
            raise ValueError("trusted source STEP artifact manifest reference is missing or ambiguous")
        source_ref = source_refs[0]
        if (
            source_ref.artifact_type != ArtifactType.STEP.value
            or source_ref.artifact_id != source_artifact.artifact_id
            or source_ref.sha256 != source_artifact.sha256
            or source_ref.producer_identity != source_artifact.producer_tool_name
            or source_ref.producer_version != source_artifact.producer_tool_version
        ):
            raise ValueError("trusted source STEP artifact manifest reference mismatch")
        source_path = ArtifactStore(
            self.state_manager.workspace,
            project_id=self.project_id,
            run_id=execution_manifest.run_id,
        ).path_for_in_project(source_artifact)
        if source_path is None:
            raise ValueError("trusted source STEP artifact is unavailable")
        try:
            realization = self.structural_service.geometry_adapter.realize_geometry(source_path)
            region_map = self.structural_service.region_resolver.resolve(
                definition.regions,
                realization,
                source_geometry_hash=request.source_binding.geometry_artifact_hash,
            )
            trusted_geometry_observation = cantilever_geometry_observation(
                request, definition, realization, region_map,
            )
            trusted_material_observation = cantilever_material_observation(request, definition)
        except Exception as exc:
            raise ValueError("trusted analytical source observations are unavailable") from exc
        validation = StructuralAnalyticalValidator().validate(
            trusted_result,
            policy,
            request=request,
            execution_manifest=execution_manifest,
            mesh=trusted_mesh,
            mesh_artifact_bytes=mesh_artifact_bytes,
            geometry_observation=trusted_geometry_observation,
            material_observation=trusted_material_observation,
            definition=definition,
        )
        self._assert_structural_source_unchanged(source_before, "structural analytical validation")
        return validation

    def evaluate_multi_joint_configuration(
        self,
        *,
        source_revision: int,
        source_state_hash: str,
        assembly: CadAssemblyProgram,
        model: KinematicModel,
        configuration: JointConfiguration,
    ) -> KinematicForwardKinematicsResult:
        """Evaluate deterministic forward kinematics for a multi-joint configuration.

        Core forward kinematics is a pure deterministic computation with no
        FreeCAD dependency.  The result contains a transformed CadAssemblyProgram
        that may later be used for exact FreeCAD measurement in M10-3.
        """
        self.assembly_service.validate_source(
            self.project_id, source_revision, source_state_hash
        )

        service = MultiJointKinematicsService()
        result = service.evaluate(assembly, model, configuration)

        self._record_multi_joint_kinematics_provenance(
            model_hash=result.model_hash,
            configuration_hash=result.configuration_hash,
            result=result,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
        )
        return result

    def _record_multi_joint_kinematics_provenance(
        self,
        *,
        model_hash: str,
        configuration_hash: str,
        result: KinematicForwardKinematicsResult,
        source_revision: int,
        source_state_hash: str,
    ) -> None:
        import hashlib as _hashlib
        _hash_input = (
            result.source_assembly_hash
            + result.model_hash
            + result.configuration_hash
        ).encode("utf-8")
        evidence_id = "EVD-MJKIN-" + _hashlib.sha256(_hash_input).hexdigest()[:24]
        evidence = Evidence(
            id=evidence_id,
            kind="analysis.multi_joint_kinematics",
            summary="Deterministic multi-joint forward-kinematics evaluation",
            revision=source_revision,
            state_hash=source_state_hash,
            producer_type="multi_joint_kinematics",
            producer_name="deterministic-forward-kinematics",
            producer_version=result.evaluator_version,
            producer_result_id=result.result_hash,
            input_hash=result.configuration_hash,
            output_hash=result.result_hash,
            backend_provenance=None,
        )
        try:
            self.evidence_store.load_evidence(self.project_id, evidence_id)
        except Exception:
            self.evidence_store.write_evidence(self.project_id, evidence)
