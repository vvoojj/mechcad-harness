import json
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from mechcad_harness.dependency import EvidenceStore
from mechcad_harness.models import Model
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.changes.provenance import StateApplicationStore

from .constraint_requests import ConstraintRequestMaterializer
from .constraint_resolution import ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer
from .constraint_resolution_application import ApplicationOutcome, ConstraintResolutionApplicationResult, ConstraintResolutionApplicationService


class WorkflowOutcome(StrEnum):
    COMPLETE = "complete"
    FAILED = "failed"


class WorkflowTransition(Model):
    workflow_id: str = Field(min_length=1)
    transition: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    source_command_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)


class ConstraintResolutionWorkflowResult(Model):
    workflow_id: str
    source_command_id: str
    resolution_ids: tuple[str, ...]
    outcome: WorkflowOutcome
    application_outcome: ApplicationOutcome
    old_revision: int
    old_state_hash: str
    new_revision: int
    new_state_hash: str
    proposal_id: str | None = None
    changeset_id: str | None = None
    parameter_ids: tuple[str, ...]
    invalidated_node_ids: tuple[str, ...]
    satisfaction_proof_ids: tuple[str, ...]


def workflow_id(project_id: str, source_command_id: str) -> str:
    return f"RESWF-{uuid5(NAMESPACE_URL, f'{project_id}\n{source_command_id}') }"


class ConstraintResolutionWorkflow:
    _transitions = ("00_started", "10_command_materialized", "20_resolutions_materialized", "30_state_application", "40_state_revision", "50_invalidation", "60_satisfaction", "70_complete")

    def __init__(self, state_manager: StateManager, materializer: ConstraintResolutionMaterializer, application: ConstraintResolutionApplicationService, evidence: EvidenceStore):
        self.state_manager = state_manager
        self.materializer = materializer
        self.application = application
        self.evidence = evidence

    def run(self, command: ConstraintResolutionBatchCommand, *, run_id: str) -> ConstraintResolutionWorkflowResult:
        workflow = workflow_id(command.project_id, command.command_id)
        directory = self.state_manager.workspace / "projects" / command.project_id / "runs" / run_id / "resolution_workflow"
        self._validate_workflow_history(directory, command, workflow)
        terminal = directory / "70_complete.json"
        if terminal.exists():
            self._validate_workflow_history(directory, command, workflow, terminal=True)
            self._validate_terminal_artifacts(directory, command, run_id)
            return self._load_complete(directory, command)
        self._write_transition(directory, WorkflowTransition(workflow_id=workflow, transition="00_started", project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash))
        resolutions_path = directory / "20_resolutions_materialized.json"
        if resolutions_path.exists():
            resolutions_transition = WorkflowTransition.model_validate_json(resolutions_path.read_text(encoding="utf-8"))
            resolution_ids = tuple(resolutions_transition.payload["resolution_ids"])
            materialized = self.materializer.materialize_batch(command, run_id=run_id)
            if materialized.resolution_ids != resolution_ids:
                raise ValueError("conflicting materialization transition")
        else:
            materialized = self.materializer.materialize_batch(command, run_id=run_id)
        self._write_transition(directory, WorkflowTransition(workflow_id=workflow, transition="10_command_materialized", project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, payload={"command_id": command.command_id}))
        self._write_transition(directory, WorkflowTransition(workflow_id=workflow, transition="20_resolutions_materialized", project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, payload={"resolution_ids": list(materialized.resolution_ids)}))
        application_path = directory / "30_state_application.json"
        if application_path.exists():
            applied = ConstraintResolutionApplicationResult.model_validate(WorkflowTransition.model_validate_json(application_path.read_text(encoding="utf-8")).payload)
            self._validate_application_result(command, run_id, applied)
        else:
            applied = self._recover_or_apply(command, materialized, run_id)
            self._write_transition(directory, WorkflowTransition(workflow_id=workflow, transition="30_state_application", project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, payload=applied.model_dump(mode="json")))
        revision_path = directory / "40_state_revision.json"
        if revision_path.exists():
            revision_transition = WorkflowTransition.model_validate_json(revision_path.read_text(encoding="utf-8"))
            if revision_transition.payload.get("new_revision") != applied.new_revision or revision_transition.payload.get("new_state_hash") != applied.new_state_hash or revision_transition.payload.get("application_id") != applied.application_id:
                raise ValueError("WORKFLOW_INTEGRITY_FAILURE: conflicting state revision transition")
        else:
            self._verify_revision(command.project_id, applied)
            self._write_transition(directory, WorkflowTransition(workflow_id=workflow, transition="40_state_revision", project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, payload={"application_id": applied.application_id, "receipt_id": applied.receipt_id, "old_revision": applied.old_revision, "old_state_hash": applied.old_state_hash, "new_revision": applied.new_revision, "new_state_hash": applied.new_state_hash, "parameter_ids": list(applied.parameter_ids), "outcome": applied.outcome.value}))
        invalidation_path = directory / "50_invalidation.json"
        if invalidation_path.exists():
            invalidated = tuple(WorkflowTransition.model_validate_json(invalidation_path.read_text(encoding="utf-8")).payload["invalidated_node_ids"])
        else:
            invalidated = ()
        if applied.outcome is ApplicationOutcome.APPLIED and not invalidation_path.exists():
            try:
                existing = self.evidence.load_invalidation(command.project_id, applied.new_revision)
                if existing.parent_revision != applied.old_revision or existing.revision != applied.new_revision or existing.changed_paths != self._changed_paths(applied.parameter_ids):
                    raise ValueError("conflicting invalidation record")
                record = existing
            except Exception:
                record = self.evidence.build_invalidation(command.project_id, applied.new_revision, applied.old_revision, self._changed_paths(applied.parameter_ids), applied.changeset_id)
                self.evidence.record_invalidation(record)
            invalidated = record.transitively_invalidated_nodes
            self._write_transition(directory, WorkflowTransition(workflow_id=workflow, transition="50_invalidation", project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, payload={"invalidated_node_ids": list(invalidated), "new_revision": applied.new_revision}))
        elif not invalidation_path.exists():
            self._write_transition(directory, WorkflowTransition(workflow_id=workflow, transition="50_invalidation", project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, payload={"invalidated_node_ids": [], "new_revision": applied.new_revision}))
        satisfaction_path = directory / "60_satisfaction.json"
        if satisfaction_path.exists():
            satisfaction = WorkflowTransition.model_validate_json(satisfaction_path.read_text(encoding="utf-8"))
            proof_ids = list(satisfaction.payload["satisfaction_proof_ids"])
            current = self.state_manager.load_current_state(command.project_id)
        else:
            current = self.state_manager.load_current_state(command.project_id)
            proof_ids = []
            request_materializer = ConstraintRequestMaterializer()
            for record in materialized.resolution_records:
                if not request_materializer.is_satisfied(record.key, current, command.engineering_scope_id):
                    raise ValueError("resolution satisfaction proof failed")
                proof_ids.append(record.resolution_id)
            self._write_transition(directory, WorkflowTransition(workflow_id=workflow, transition="60_satisfaction", project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, payload={"satisfaction_proof_ids": proof_ids, "revision": current.revision, "state_hash": state_hash(current)}))
        self._write_transition(directory, WorkflowTransition(workflow_id=workflow, transition="70_complete", project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, payload={"outcome": WorkflowOutcome.COMPLETE.value}))
        return ConstraintResolutionWorkflowResult(workflow_id=workflow, source_command_id=command.command_id, resolution_ids=materialized.resolution_ids, outcome=WorkflowOutcome.COMPLETE, application_outcome=applied.outcome, old_revision=applied.old_revision, old_state_hash=applied.old_state_hash, new_revision=applied.new_revision, new_state_hash=applied.new_state_hash, proposal_id=applied.proposal_id, changeset_id=applied.changeset_id, parameter_ids=applied.parameter_ids, invalidated_node_ids=tuple(invalidated), satisfaction_proof_ids=tuple(proof_ids))

    def _load_complete(self, directory: Path, command: ConstraintResolutionBatchCommand) -> ConstraintResolutionWorkflowResult:
        application = WorkflowTransition.model_validate_json((directory / "30_state_application.json").read_text(encoding="utf-8"))
        revision = WorkflowTransition.model_validate_json((directory / "40_state_revision.json").read_text(encoding="utf-8"))
        invalidation = WorkflowTransition.model_validate_json((directory / "50_invalidation.json").read_text(encoding="utf-8"))
        satisfaction = WorkflowTransition.model_validate_json((directory / "60_satisfaction.json").read_text(encoding="utf-8"))
        resolutions = WorkflowTransition.model_validate_json((directory / "20_resolutions_materialized.json").read_text(encoding="utf-8"))
        payload = application.payload
        return ConstraintResolutionWorkflowResult(workflow_id=application.workflow_id, source_command_id=command.command_id, resolution_ids=tuple(resolutions.payload["resolution_ids"]), outcome=WorkflowOutcome.COMPLETE, application_outcome=ApplicationOutcome.NO_CHANGE, old_revision=revision.payload["old_revision"], old_state_hash=revision.payload["old_state_hash"], new_revision=revision.payload["new_revision"], new_state_hash=revision.payload["new_state_hash"], proposal_id=payload.get("proposal_id"), changeset_id=payload.get("changeset_id"), parameter_ids=tuple(payload["parameter_ids"]), invalidated_node_ids=tuple(invalidation.payload["invalidated_node_ids"]), satisfaction_proof_ids=tuple(satisfaction.payload["satisfaction_proof_ids"]))

    def _recover_or_apply(self, command, materialized, run_id):
        store = StateApplicationStore(self.state_manager.workspace)
        preparation_dir = store.store.run_dir(command.project_id, run_id) / "state_application" / "preparations"
        if preparation_dir.exists():
            preparations = list(preparation_dir.glob("*.json"))
            for path in preparations:
                preparation = store.store._read(path, __import__("mechcad_harness.changes.provenance", fromlist=["StateApplicationPreparationRecord"]).StateApplicationPreparationRecord)
                if preparation.source_command_id == command.command_id and preparation.source_resolution_ids == materialized.resolution_ids:
                    return self.application.recover_application(command.project_id, run_id, preparation.application_id)
        return self.application.apply_batch(materialized, run_id=run_id)

    def _validate_application_result(self, command, run_id, applied):
        if applied.source_command_id != command.command_id:
            raise ValueError("WORKFLOW_INTEGRITY_FAILURE: application command mismatch")
        if applied.application_id:
            store = StateApplicationStore(self.state_manager.workspace)
            preparation = store.load_preparation(command.project_id, run_id, applied.application_id)
            receipt = store.load_receipt(command.project_id, run_id, applied.application_id)
            if preparation.proposal_id != applied.proposal_id or preparation.changeset_id != applied.changeset_id or receipt.proposal_id != applied.proposal_id or receipt.changeset_id != applied.changeset_id or receipt.source_resolution_ids != applied.resolution_ids:
                raise ValueError("WORKFLOW_INTEGRITY_FAILURE: application provenance mismatch")

    def _validate_terminal_artifacts(self, directory, command, run_id):
        application = WorkflowTransition.model_validate_json((directory / "30_state_application.json").read_text(encoding="utf-8"))
        applied = ConstraintResolutionApplicationResult.model_validate(application.payload)
        self._validate_application_result(command, run_id, applied)
        revision = WorkflowTransition.model_validate_json((directory / "40_state_revision.json").read_text(encoding="utf-8"))
        if revision.payload.get("application_id") != applied.application_id or revision.payload.get("new_revision") != applied.new_revision or revision.payload.get("new_state_hash") != applied.new_state_hash:
            raise ValueError("WORKFLOW_INTEGRITY_FAILURE: revision linkage mismatch")
        self._verify_revision(command.project_id, applied)
        invalidation = WorkflowTransition.model_validate_json((directory / "50_invalidation.json").read_text(encoding="utf-8"))
        if invalidation.payload.get("new_revision") != applied.new_revision:
            raise ValueError("WORKFLOW_INTEGRITY_FAILURE: invalidation linkage mismatch")
        satisfaction = WorkflowTransition.model_validate_json((directory / "60_satisfaction.json").read_text(encoding="utf-8"))
        current = self.state_manager.load_current_state(command.project_id)
        if satisfaction.payload.get("revision") != current.revision or satisfaction.payload.get("state_hash") != state_hash(current):
            raise ValueError("WORKFLOW_INTEGRITY_FAILURE: satisfaction linkage mismatch")

    def _verify_revision(self, project_id, applied):
        current = self.state_manager._read_current(project_id)
        if current["revision"] != applied.new_revision or current["state_hash"] != applied.new_state_hash:
            raise ValueError("WORKFLOW_INTEGRITY_FAILURE: revision pointer mismatch")
        state = self.state_manager.load_revision(project_id, applied.new_revision)
        if state_hash(state) != applied.new_state_hash:
            raise ValueError("WORKFLOW_INTEGRITY_FAILURE: revision hash mismatch")

    def _validate_workflow_history(self, directory, command, workflow, *, terminal=False):
        present = [path.exists() for path in (directory / f"{name}.json" for name in self._transitions)]
        if terminal and not all(present):
            raise ValueError("WORKFLOW_INTEGRITY_FAILURE: incomplete terminal history")
        if any(present[index + 1] and not present[index] for index in range(len(present) - 1)):
            raise ValueError("WORKFLOW_INTEGRITY_FAILURE: non-contiguous workflow history")
        for name in self._transitions:
            path = directory / f"{name}.json"
            if not path.exists():
                continue
            transition = WorkflowTransition.model_validate_json(path.read_text(encoding="utf-8"))
            if transition.workflow_id != workflow or transition.project_id != command.project_id or transition.source_command_id != command.command_id or transition.source_revision != command.source_revision or transition.source_state_hash != command.source_state_hash:
                raise ValueError("WORKFLOW_INTEGRITY_FAILURE: workflow lineage mismatch")

    def _recover_terminal_transitions(self, directory: Path, command: ConstraintResolutionBatchCommand, workflow: str) -> None:
        base = dict(workflow_id=workflow, project_id=command.project_id, source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash)
        if not (directory / "10_command_materialized.json").exists():
            self._write_transition(directory, WorkflowTransition(transition="10_command_materialized", payload={"command_id": command.command_id}, **base))
        if not (directory / "20_resolutions_materialized.json").exists():
            application = WorkflowTransition.model_validate_json((directory / "30_state_application.json").read_text(encoding="utf-8"))
            self._write_transition(directory, WorkflowTransition(transition="20_resolutions_materialized", payload={"resolution_ids": list(application.payload["resolution_ids"])}, **base))
        if not (directory / "30_state_application.json").exists() or not (directory / "40_state_revision.json").exists():
            raise ValueError("WORKFLOW_INTEGRITY_FAILURE: terminal workflow missing state application linkage")
        if not (directory / "50_invalidation.json").exists():
            revision = WorkflowTransition.model_validate_json((directory / "40_state_revision.json").read_text(encoding="utf-8"))
            self._write_transition(directory, WorkflowTransition(transition="50_invalidation", payload={"invalidated_node_ids": list(self.evidence.load_invalidation(command.project_id, revision.payload["new_revision"]).transitively_invalidated_nodes), "new_revision": revision.payload["new_revision"]}, **base))
        if not (directory / "60_satisfaction.json").exists():
            current = self.state_manager.load_current_state(command.project_id)
            application = WorkflowTransition.model_validate_json((directory / "30_state_application.json").read_text(encoding="utf-8"))
            self._write_transition(directory, WorkflowTransition(transition="60_satisfaction", payload={"satisfaction_proof_ids": application.payload["resolution_ids"], "revision": current.revision, "state_hash": state_hash(current)}, **base))

    def _write_transition(self, directory: Path, transition: WorkflowTransition) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{transition.transition}.json"
        if path.exists():
            existing = WorkflowTransition.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != transition:
                raise ValueError(f"conflicting workflow transition: {transition.transition}")
            return
        path.write_text(transition.model_dump_json(), encoding="utf-8")

    def _changed_paths(self, parameter_ids):
        return tuple(f"/authoritative_parameters/{parameter_id}" for parameter_id in parameter_ids)
