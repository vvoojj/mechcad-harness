from __future__ import annotations

import json
from pathlib import Path

from mechcad_harness.artifacts.storage import ArtifactStore, ArtifactType
from mechcad_harness.models.structural import StructuralAnalysisDefinition
from mechcad_harness.runs.controller import RunController
from mechcad_harness.runs.models import SourceBinding
from mechcad_harness.state.manager import StateManager
from mechcad_harness.structural.deck import DeckBuildError, StructuralDeckBuilder
from mechcad_harness.structural.geometry import (
    GeometryResolutionError,
    RegionResolutionError,
    StructuralFreeCADGeometryAdapter,
    StructuralRegionResolver,
)
from mechcad_harness.structural.mesh import MeshProviderError, StructuralGmshMeshingProvider
from mechcad_harness.structural.models import (
    StructuralArtifactRef,
    StructuralCaseExecutionManifest,
    StructuralExecutionManifest,
    StructuralExecutionResult,
    StructuralExecutionStatus,
    mesh_input_hash,
    mesh_manifest_hash,
)
from mechcad_harness.structural.preflight import ConstraintPreflight
from mechcad_harness.structural.runtime import DiscoveredRuntime
from mechcad_harness.structural.solver import StructuralCalculiXSolverProvider
from mechcad_harness.structural_request import StructuralAnalysisRequest


class StructuralPipelineError(Exception):
    def __init__(self, stage: str, status: StructuralExecutionStatus, detail: str):
        super().__init__(detail)
        self.stage = stage
        self.status = status
        self.detail = detail


def _mesh_specification_hash(request: StructuralAnalysisRequest) -> str:
    payload = request.mesh_specification.model_dump(mode="json")
    return "sha256:" + __import__("hashlib").sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class StructuralAnalysisService:
    def __init__(
        self,
        *,
        state_manager: StateManager,
        run_controller: RunController,
        workspace: str | Path,
        geometry_adapter: StructuralFreeCADGeometryAdapter,
        region_resolver: StructuralRegionResolver,
        gmsh_provider: StructuralGmshMeshingProvider,
        deck_builder: StructuralDeckBuilder,
        constraint_preflight: ConstraintPreflight,
        calculix_provider: StructuralCalculiXSolverProvider,
    ):
        self.state_manager = state_manager
        self.run_controller = run_controller
        self.workspace = Path(workspace)
        self.geometry_adapter = geometry_adapter
        self.region_resolver = region_resolver
        self.gmsh_provider = gmsh_provider
        self.deck_builder = deck_builder
        self.constraint_preflight = constraint_preflight
        self.calculix_provider = calculix_provider

    def execute(self, request: StructuralAnalysisRequest) -> StructuralExecutionResult:
        binding = request.source_binding
        project_id = binding.project_id
        with self.state_manager.project_lock(project_id):
            current = self._read_current(project_id)
            if (binding.source_revision != current["revision"]
                    or binding.source_state_hash != current["state_hash"]
                    or binding.project_id != project_id):
                return StructuralExecutionResult(
                    run_id=None, execution_status=StructuralExecutionStatus.GEOMETRY_REJECTED,
                    failure_stage="source_binding", error_detail="stale or mismatched source binding")
            run = self.run_controller.create_run(
                project_id, expected_source=SourceBinding(
                    project_id=project_id, revision=current["revision"], state_hash=current["state_hash"]))
        revision = run.active_revision
        state_hash = run.active_state_hash
        state = self.state_manager.load_revision(project_id, revision)
        try:
            definition = self._locate_definition(state, binding)
            request.validate_against(definition)
        except StructuralPipelineError as exc:
            return StructuralExecutionResult(
                run_id=run.run_id, execution_status=exc.status,
                failure_stage=exc.stage, error_detail=exc.detail)
        except ValueError as exc:
            return StructuralExecutionResult(
                run_id=run.run_id, execution_status=StructuralExecutionStatus.GEOMETRY_REJECTED,
                failure_stage="definition", error_detail=str(exc))
        try:
            return self._run_pipeline(request, run, definition, revision, state_hash)
        except StructuralPipelineError as exc:
            return StructuralExecutionResult(
                run_id=run.run_id, execution_status=exc.status, failure_stage=exc.stage, error_detail=exc.detail)
        except Exception as exc:  # pragma: no cover - defensive
            import traceback
            return StructuralExecutionResult(
                run_id=run.run_id, execution_status=StructuralExecutionStatus.MESH_FAILED,
                failure_stage="unexpected", error_detail=str(exc) + "\n" + traceback.format_exc()[-3000:])

    def _read_current(self, project_id: str) -> dict:
        return self.state_manager._read_current(project_id)

    def _locate_definition(self, state, binding) -> StructuralAnalysisDefinition:
        for definition in state.structural_analysis_definitions:
            if definition.id == binding.definition_id:
                if definition_hash_of(definition) != binding.definition_hash:
                    raise StructuralPipelineError(
                        "definition", StructuralExecutionStatus.GEOMETRY_REJECTED,
                        "definition hash mismatch")
                return definition
        raise StructuralPipelineError(
            "definition", StructuralExecutionStatus.GEOMETRY_REJECTED, "definition not found")

    def _run_pipeline(self, request, run, definition, revision, state_hash) -> StructuralExecutionResult:
        project_id = run.project_id
        binding = request.source_binding
        store = ArtifactStore(self.workspace, project_id=project_id, run_id=run.run_id)
        # --- geometry artifact verification (independent byte verification) ---
        verified_source = store.read_verified_in_project(
            binding.geometry_artifact_id,
            expected_type=ArtifactType.STEP,
            expected_hash=binding.geometry_artifact_hash,
        )
        if verified_source is None:
            raise StructuralPipelineError("geometry", StructuralExecutionStatus.GEOMETRY_REJECTED, "geometry artifact not found")
        artifact, _source_bytes = verified_source
        if artifact.bound_revision != revision or artifact.bound_state_hash != state_hash:
            raise StructuralPipelineError("geometry", StructuralExecutionStatus.GEOMETRY_REJECTED, "geometry artifact bound to different revision/state")
        expected_geometry_provenance = getattr(
            getattr(self.geometry_adapter, "_discovery", None), "provenance", None
        )
        if expected_geometry_provenance is None or artifact.backend_provenance != expected_geometry_provenance:
            raise StructuralPipelineError(
                "geometry", StructuralExecutionStatus.GEOMETRY_REJECTED,
                "geometry artifact provenance does not match the composed FreeCAD runtime",
            )
        step_path = store.path_for_in_project(artifact)
        if step_path is None:
            raise StructuralPipelineError("geometry", StructuralExecutionStatus.GEOMETRY_REJECTED, "geometry artifact path is untrusted")
        # --- realize geometry ---
        try:
            realization = self.geometry_adapter.realize_geometry(step_path)
        except GeometryResolutionError as exc:
            raise StructuralPipelineError(
                "geometry", StructuralExecutionStatus.GEOMETRY_REJECTED, str(exc)) from exc
        if realization.solid_count != 1:
            raise StructuralPipelineError("geometry", StructuralExecutionStatus.GEOMETRY_REJECTED,
                                          f"expected exactly one solid, found {realization.solid_count}")
        # --- resolve semantic regions ---
        try:
            region_map = self.region_resolver.resolve(
                definition.regions, realization, source_geometry_hash=binding.geometry_artifact_hash)
        except RegionResolutionError as exc:
            raise StructuralPipelineError(
                "region_resolution", StructuralExecutionStatus.REGION_RESOLUTION_FAILED, str(exc)) from exc
        # --- mesh ---
        mesh_spec_hash = _mesh_specification_hash(request)
        mesh_input_identity = mesh_input_hash(
            source_geometry_hash=binding.geometry_artifact_hash,
            mesh_specification_hash=mesh_spec_hash,
            region_map_hash=region_map.region_map_hash,
            gmsh_identity=self.gmsh_provider.identity,
            gmsh_version=self.gmsh_provider._discovery.version or "unknown",
        )
        try:
            parsed_mesh, mesh_manifest, msh_bytes = self.gmsh_provider.mesh(
                step_path, region_map, mesh_spec_hash=mesh_spec_hash,
                element_family=request.mesh_specification.element_family)
        except MeshProviderError as exc:
            raise StructuralPipelineError(
                "mesh", StructuralExecutionStatus.MESH_FAILED, str(exc)) from exc
        # Publish the shared mesh before any case can fail so every case partition
        # has a durable, byte-verified mesh reference.
        msh_artifact = store.publish(
            self._artifact_id(request, "msh"), ArtifactType.MSH, "mesh.msh", msh_bytes,
            self.gmsh_provider.identity, mesh_manifest.gmsh_version, revision, state_hash,
            backend_provenance=self.gmsh_provider._discovery.provenance, input_hash=mesh_input_identity)
        refs: list[StructuralArtifactRef] = [
            self._ref(msh_artifact, self.gmsh_provider.identity, mesh_manifest.gmsh_version)
        ]
        produced = [msh_artifact]
        case_manifests: list[StructuralCaseExecutionManifest] = []
        lowered_loads = []
        case_by_id = {case.id: case for case in definition.load_cases}

        for load_case_id in request.selected_load_case_ids:
            selected_case = case_by_id[load_case_id]
            built = None
            case_lowered_loads = []
            deck_artifact = None
            frd_artifact = None
            dat_artifact = None
            log_artifact = None
            solver_result = None
            status = StructuralExecutionStatus.SUCCEEDED
            failure_stage = ""
            error_detail = ""

            try:
                fixed_supports = tuple(
                    support for support in definition.boundary_conditions
                    if load_case_id in support.applies_to_load_case_ids)
                built = self.deck_builder.build(
                    definition=definition, selected_cases=(selected_case,), fixed_supports=fixed_supports,
                    region_definitions=definition.regions, region_map=region_map, parsed_mesh=parsed_mesh,
                    mesh_hash=msh_artifact.sha256,
                    requested_result_fields=request.requested_result_fields)
            except DeckBuildError as exc:
                status = StructuralExecutionStatus.DECK_INVALID
                failure_stage = "deck"
                error_detail = str(exc)

            if built is not None:
                deck_artifact = store.publish(
                    self._artifact_id(request, "inp", load_case_id), ArtifactType.INP,
                    f"deck-{len(case_manifests) + 1}.inp", built.text.encode("utf-8"),
                    self.deck_builder.identity, self.deck_builder.builder_version, revision, state_hash,
                    input_hash=msh_artifact.sha256)
                refs.append(self._ref(deck_artifact, self.deck_builder.identity, self.deck_builder.builder_version))
                produced.append(deck_artifact)
                case_lowered_loads.extend(built.lowered_loads)
                lowered_loads.extend(built.lowered_loads)

                preflight = self.constraint_preflight.evaluate(
                    parsed_mesh.nodes, built.representation.boundary_node_sets)
                if not preflight.adequate:
                    status = StructuralExecutionStatus.SOLVER_UNDERCONSTRAINED
                    failure_stage = "constraint_preflight"
                    error_detail = f"rigid-body rank {preflight.rigid_body_rank} < 6"

                if status is StructuralExecutionStatus.SUCCEEDED:
                    try:
                        solver_result = self.calculix_provider.execute(built.text)
                    except RuntimeError as exc:
                        status = StructuralExecutionStatus.SOLVER_UNAVAILABLE
                        failure_stage = "solver"
                        error_detail = str(exc)
                    else:
                        status = self._classify_solver(solver_result)
                        if status is not StructuralExecutionStatus.SUCCEEDED:
                            failure_stage = "solver"
                            error_detail = solver_result.manifest.solver_message or "solver failed"

                if solver_result is not None:
                    solver_identity = solver_result.manifest.calculix_identity
                    solver_version = solver_result.manifest.calculix_version
                    solver_provenance = solver_result.manifest.backend_provenance
                    if solver_result.frd_bytes:
                        frd_artifact = store.publish(
                            self._artifact_id(request, "frd", load_case_id), ArtifactType.FRD,
                            f"result-{len(case_manifests) + 1}.frd", solver_result.frd_bytes,
                            solver_identity, solver_version, revision, state_hash,
                            backend_provenance=solver_provenance, input_hash=deck_artifact.sha256)
                        refs.append(self._ref(frd_artifact, solver_identity, solver_version))
                        produced.append(frd_artifact)
                    if solver_result.dat_bytes:
                        dat_artifact = store.publish(
                            self._artifact_id(request, "dat", load_case_id), ArtifactType.DAT,
                            f"result-{len(case_manifests) + 1}.dat", solver_result.dat_bytes,
                            solver_identity, solver_version, revision, state_hash,
                            backend_provenance=solver_provenance, input_hash=deck_artifact.sha256)
                        refs.append(self._ref(dat_artifact, solver_identity, solver_version))
                        produced.append(dat_artifact)
                    log_artifact = store.publish(
                        self._artifact_id(request, "log", load_case_id), ArtifactType.LOG,
                        f"solver-{len(case_manifests) + 1}.log",
                        (solver_result.log_text or "solver produced no log\n").encode("utf-8"),
                        solver_identity, solver_version, revision, state_hash,
                        backend_provenance=solver_provenance, input_hash=deck_artifact.sha256)
                    refs.append(self._ref(log_artifact, solver_identity, solver_version))
                    produced.append(log_artifact)

            case_manifest = StructuralCaseExecutionManifest(
                load_case_id=load_case_id,
                mesh_artifact_id=msh_artifact.artifact_id,
                mesh_artifact_hash=msh_artifact.sha256,
                deck_artifact_id=deck_artifact.artifact_id if deck_artifact else None,
                deck_artifact_hash=deck_artifact.sha256 if deck_artifact else None,
                frd_artifact_id=frd_artifact.artifact_id if frd_artifact else None,
                frd_artifact_hash=frd_artifact.sha256 if frd_artifact else None,
                dat_artifact_id=dat_artifact.artifact_id if dat_artifact else None,
                dat_artifact_hash=dat_artifact.sha256 if dat_artifact else None,
                log_artifact_id=log_artifact.artifact_id if log_artifact else None,
                log_artifact_hash=log_artifact.sha256 if log_artifact else None,
                deck_semantic_hash=_deck_hash(built.text) if built is not None else None,
                deck_builder_identity=self.deck_builder.identity if deck_artifact else None,
                deck_builder_version=self.deck_builder.builder_version if deck_artifact else None,
                execution_status=status,
                failure_stage=failure_stage,
                error_detail=error_detail,
                solver_manifest=solver_result.manifest if solver_result else None,
                lowered_loads=tuple(case_lowered_loads),
                run_id=run.run_id,
            )
            case_manifests.append(case_manifest)
            if status is not StructuralExecutionStatus.SUCCEEDED:
                return self._publish_request_manifest(
                    request=request, run=run, definition=definition, revision=revision, state_hash=state_hash,
                    binding=binding, artifact=artifact, region_map=region_map, mesh_spec_hash=mesh_spec_hash,
                    mesh_artifact=msh_artifact, mesh_manifest=mesh_manifest, store=store, refs=refs, produced=produced,
                    case_manifests=case_manifests, lowered_loads=lowered_loads,
                    execution_status=status, failure_stage=failure_stage, error_detail=error_detail)

        return self._publish_request_manifest(
            request=request, run=run, definition=definition, revision=revision, state_hash=state_hash,
            binding=binding, artifact=artifact, region_map=region_map, mesh_spec_hash=mesh_spec_hash,
            mesh_artifact=msh_artifact, mesh_manifest=mesh_manifest, store=store, refs=refs, produced=produced,
            case_manifests=case_manifests, lowered_loads=lowered_loads,
            execution_status=StructuralExecutionStatus.SUCCEEDED, failure_stage="", error_detail="")

    def _publish_request_manifest(
        self, *, request, run, definition, revision, state_hash, binding, artifact, region_map,
        mesh_spec_hash, mesh_artifact, store, refs, produced, case_manifests, lowered_loads,
        execution_status, failure_stage, error_detail, mesh_manifest,
    ) -> StructuralExecutionResult:
        first_case = case_manifests[0]
        multiple_cases = len(request.selected_load_case_ids) > 1
        deck_semantic_hash = None
        if not multiple_cases and first_case.deck_artifact_id is not None:
            verified_deck = store.read_verified(
                first_case.deck_artifact_id,
                expected_type=ArtifactType.INP,
                expected_hash=first_case.deck_artifact_hash,
            )
            if verified_deck is not None:
                deck_artifact, deck_bytes = verified_deck
                deck_semantic_hash = first_case.deck_semantic_hash or _deck_hash(
                    deck_bytes.decode("utf-8"))
        manifest = StructuralExecutionManifest(
            project_id=run.project_id, revision=revision, state_hash=state_hash,
            definition_id=definition.id, definition_hash=binding.definition_hash,
             request_hash=request.request_hash, analytical_policy_hash=request.analytical_policy_hash,
             run_id=run.run_id,
            geometry_artifact_id=binding.geometry_artifact_id, geometry_artifact_hash=binding.geometry_artifact_hash,
            geometry_provider_provenance=artifact.backend_provenance,
            region_map_hash=region_map.region_map_hash, resolver_identity=self.region_resolver.identity,
            resolver_version=self.region_resolver.resolver_version,
            gmsh_identity=self.gmsh_provider.identity,
              gmsh_version=self.gmsh_provider._discovery.version or "unknown",
             mesh_specification_hash=mesh_spec_hash, mesh_artifact_id=mesh_artifact.artifact_id,
              mesh_artifact_hash=mesh_artifact.sha256, mesh_manifest=mesh_manifest,
              mesh_manifest_hash=mesh_manifest_hash(mesh_manifest),
             deck_builder_identity=self.deck_builder.identity, deck_builder_version=self.deck_builder.builder_version,
             deck_semantic_hash=deck_semantic_hash if not multiple_cases else None,
             deck_artifact_id=first_case.deck_artifact_id if not multiple_cases else None,
             deck_artifact_hash=first_case.deck_artifact_hash if not multiple_cases else None,
             calculix_identity=self.calculix_provider.identity,
              calculix_version=self.calculix_provider._discovery.version or "unknown",
             execution_status=execution_status,
             solver_manifest=case_manifests[-1].solver_manifest if not multiple_cases else None,
             log_artifact_id=first_case.log_artifact_id if not multiple_cases else None,
             log_artifact_hash=first_case.log_artifact_hash if not multiple_cases else None,
             frd_artifact_id=first_case.frd_artifact_id if not multiple_cases else None,
             frd_artifact_hash=first_case.frd_artifact_hash if not multiple_cases else None,
             dat_artifact_id=first_case.dat_artifact_id if not multiple_cases else None,
             dat_artifact_hash=first_case.dat_artifact_hash if not multiple_cases else None,
             artifacts=tuple(refs), lowered_loads=tuple(lowered_loads),
            selected_load_case_ids=request.selected_load_case_ids,
            case_manifests=tuple(case_manifests),
        )
        manifest_artifact = store.publish(
            self._artifact_id(request, "json"), ArtifactType.JSON, "execution_manifest.json",
            json.dumps(manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8"),
            self.deck_builder.identity, self.deck_builder.builder_version, revision, state_hash,
            input_hash=request.request_hash)
        produced.append(manifest_artifact)
        return StructuralExecutionResult(
            run_id=run.run_id, execution_status=execution_status,
            failure_stage=failure_stage, error_detail=error_detail, manifest=manifest,
            produced_artifact_ids=tuple(a.artifact_id for a in produced))

    def _classify_solver(self, solver_result) -> StructuralExecutionStatus:
        m = solver_result.manifest
        if m.exit_code is None:
            return StructuralExecutionStatus.SOLVER_UNAVAILABLE
        valid_log = (
            m.produced_log is True
            and isinstance(solver_result.log_text, str)
            and bool(solver_result.log_text.strip())
        )
        if (m.exit_code == 0 and m.job_finished and m.produced_frd and m.produced_dat
                and solver_result.frd_bytes and solver_result.dat_bytes and valid_log):
            return StructuralExecutionStatus.SUCCEEDED
        if m.exit_code == 201 or "*ERROR in calinput" in (m.solver_message or ""):
            return StructuralExecutionStatus.SOLVER_FAILED
        return StructuralExecutionStatus.SOLVER_FAILED

    def _artifact_id(self, request: StructuralAnalysisRequest, kind: str, load_case_id: str | None = None) -> str:
        import hashlib
        case_part = "" if load_case_id is None else f"|{load_case_id}"
        payload = f"{request.request_hash}{case_part}|{kind}".encode("utf-8")
        return f"STRUCT-{kind.upper()}-{hashlib.sha256(payload).hexdigest()[:16]}"

    @staticmethod
    def _ref(artifact, producer_identity: str, producer_version: str) -> StructuralArtifactRef:
        return StructuralArtifactRef(
            artifact_type=artifact.artifact_type.value, artifact_id=artifact.artifact_id,
            sha256=artifact.sha256, producer_identity=producer_identity, producer_version=producer_version)


def _deck_hash(text: str) -> str:
    return "sha256:" + __import__("hashlib").sha256(text.encode("utf-8")).hexdigest()


def definition_hash_of(definition: StructuralAnalysisDefinition) -> str:
    from mechcad_harness.models.structural import structural_definition_hash
    return structural_definition_hash(definition)
