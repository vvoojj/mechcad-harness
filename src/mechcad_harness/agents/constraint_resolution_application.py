import json
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from mechcad_harness.changes import ChangeEngine, ChangeOperation, OperationType
from mechcad_harness.changes.provenance import StateApplicationPreparationRecord, StateApplicationReceiptRecord, StateApplicationStore, application_id, operations_hash
from mechcad_harness.models import ChangeProposal, ProposalStatus, Model
from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter
from mechcad_harness.state import StateManager, state_hash

from .constraint_requests import ConstraintRequestStore, ConstraintRequestLifecycle
from .constraint_resolution import (
    ConstraintResolutionBatchCommand,
    ConstraintResolutionMaterializationResult,
    ConstraintResolutionStore,
    ResolutionStatus,
    parameter_id,
)


class ApplicationOutcome(StrEnum):
    APPLIED = "applied"
    NO_CHANGE = "no_change"


class ConstraintResolutionApplicationResult(Model):
    source_command_id: str = Field(min_length=1)
    resolution_ids: tuple[str, ...]
    proposal_id: str | None = None
    changeset_id: str | None = None
    old_revision: int
    old_state_hash: str
    new_revision: int
    new_state_hash: str
    parameter_ids: tuple[str, ...]
    outcome: ApplicationOutcome
    application_id: str | None = None
    preparation_id: str | None = None
    receipt_id: str | None = None


class ConstraintResolutionApplicationService:
    def __init__(self, state_manager: StateManager, change_engine: ChangeEngine, request_store: ConstraintRequestStore, resolution_store: ConstraintResolutionStore | None = None):
        self.state_manager = state_manager
        self.change_engine = change_engine
        self.request_store = request_store
        self.resolution_store = resolution_store or ConstraintResolutionStore(request_store.store.workspace)
        self.application_store = StateApplicationStore(request_store.store.workspace)

    def apply_batch(self, materialization: ConstraintResolutionMaterializationResult, *, run_id: str) -> ConstraintResolutionApplicationResult:
        if tuple(record.resolution_id for record in materialization.resolution_records) != materialization.resolution_ids:
            raise ValueError("resolution materialization identity mismatch")
        command = self.resolution_store.load_command(self._project_id(materialization), run_id, materialization.command_id)
        current_pointer = self.state_manager._read_current(command.project_id)
        current = self.state_manager.load_current_state(command.project_id)
        replay_records = [self.resolution_store.load_resolution(command.project_id, run_id, resolution_id) for resolution_id in materialization.resolution_ids]
        replay_ids = []
        replay_complete = True
        for record in replay_records:
            anchor_kind, anchor_id = _anchor_for(record.key)
            replay_id = parameter_id(project_id=command.project_id, scope_id=command.engineering_scope_id, anchor_kind=anchor_kind, anchor_id=anchor_id, key=record.key)
            replay_ids.append(replay_id)
            matches = [item for item in current.authoritative_parameters if item.id == replay_id]
            replay_complete = replay_complete and len(matches) == 1 and matches[0].value == record.canonical_value and matches[0].source_resolution_id == record.resolution_id
        if replay_complete and replay_records:
            for path in self.application_store.store.workspace.glob(f"projects/{command.project_id}/runs/{run_id}/state_application/receipts/*.json"):
                receipt = self.application_store.store._read(path, StateApplicationReceiptRecord)
                if receipt.source_command_id == command.command_id and receipt.source_resolution_ids == materialization.resolution_ids:
                    return ConstraintResolutionApplicationResult(source_command_id=command.command_id, resolution_ids=materialization.resolution_ids, old_revision=receipt.base_revision, old_state_hash=receipt.base_state_hash, new_revision=receipt.new_revision, new_state_hash=receipt.new_state_hash, parameter_ids=tuple(sorted(replay_ids)), outcome=ApplicationOutcome.NO_CHANGE, application_id=receipt.application_id, preparation_id=receipt.preparation_id, receipt_id=receipt.application_id)
            return ConstraintResolutionApplicationResult(source_command_id=command.command_id, resolution_ids=materialization.resolution_ids, old_revision=current.revision, old_state_hash=current_pointer["state_hash"], new_revision=current.revision, new_state_hash=current_pointer["state_hash"], parameter_ids=tuple(sorted(replay_ids)), outcome=ApplicationOutcome.NO_CHANGE)
        if current_pointer["revision"] != command.source_revision or current_pointer["state_hash"] != command.source_state_hash:
            raise ValueError("stale resolution application binding")
        records = []
        for resolution_id in materialization.resolution_ids:
            record = self.resolution_store.load_resolution(command.project_id, run_id, resolution_id)
            self._validate_record(command, record, materialization)
            request = self.request_store.load(command.project_id, run_id, record.source_constraint_request_id)
            if request.lifecycle is not ConstraintRequestLifecycle.DISCOVERED or request.request.revision != command.source_revision or request.request.state_hash != command.source_state_hash or request.engineering_scope_id != command.engineering_scope_id:
                raise ValueError("stale or invalid source request binding")
            records.append((record, request))
        operations, parameter_ids = self._plan_operations(command, current, records)
        old_revision = current.revision
        old_hash = current_pointer["state_hash"]
        if not operations:
            return ConstraintResolutionApplicationResult(source_command_id=command.command_id, resolution_ids=materialization.resolution_ids, old_revision=old_revision, old_state_hash=old_hash, new_revision=old_revision, new_state_hash=old_hash, parameter_ids=parameter_ids, outcome=ApplicationOutcome.NO_CHANGE)
        proposal = ChangeProposal(id=self._proposal_id(command, operations), title="Apply accepted constraint resolutions", status=ProposalStatus.ACCEPTED, base_revision=old_revision, base_state_hash=old_hash, actor="mechcad-resolution", operations=operations)
        canonical_operations = tuple(operation.model_dump(mode="json") for operation in operations)
        app_id = application_id(project_id=command.project_id, source_command_id=command.command_id, proposal_id=proposal.id, base_revision=old_revision, base_state_hash=old_hash, operations=canonical_operations)
        _, candidate, changeset = self.change_engine.prepare_proposal(command.project_id, proposal)
        canonical_candidate = candidate.model_copy(update={"revision": old_revision + 1})
        preparation = StateApplicationPreparationRecord(application_id=app_id, project_id=command.project_id, run_id=run_id, source_command_id=command.command_id, source_resolution_ids=materialization.resolution_ids, proposal_id=proposal.id, changeset_id=changeset.id, actor=proposal.actor, base_revision=old_revision, base_state_hash=old_hash, operations=canonical_operations, operations_hash=operations_hash(canonical_operations), target_revision=old_revision + 1, target_state_hash=state_hash(canonical_candidate))
        self.application_store.write_preparation(run_id, preparation)
        if self.state_manager._revision_path(command.project_id, old_revision + 1).exists():
            snapshot = self.state_manager._read_snapshot(command.project_id, old_revision + 1)
        else:
            snapshot = self.state_manager.create_revision(command.project_id, candidate)
        applied = type("Applied", (), {"snapshot": snapshot, "changeset_id": changeset.id})()
        reloaded = self.state_manager.load_revision(command.project_id, applied.snapshot.revision)
        if reloaded.revision != old_revision + 1 or state_hash(reloaded) != applied.snapshot.state_hash:
            raise ValueError("persisted revision verification failed")
        for record, _ in records:
            expected_id = parameter_id(project_id=command.project_id, scope_id=command.engineering_scope_id, anchor_kind=_anchor_for(record.key)[0], anchor_id=_anchor_for(record.key)[1], key=record.key)
            matches = [item for item in reloaded.authoritative_parameters if item.id == expected_id]
            if len(matches) != 1 or matches[0].source_resolution_id != record.resolution_id or matches[0].value != record.canonical_value:
                raise ValueError("persisted authoritative parameter verification failed")
        receipt = StateApplicationReceiptRecord(application_id=app_id, preparation_id=app_id, project_id=command.project_id, run_id=run_id, source_command_id=command.command_id, source_resolution_ids=materialization.resolution_ids, proposal_id=proposal.id, changeset_id=applied.changeset_id, actor=proposal.actor, base_revision=old_revision, base_state_hash=old_hash, new_revision=applied.snapshot.revision, new_state_hash=applied.snapshot.state_hash, operations_hash=operations_hash(canonical_operations), outcome=ApplicationOutcome.APPLIED.value)
        self.application_store.write_receipt(run_id, receipt)
        return ConstraintResolutionApplicationResult(source_command_id=command.command_id, resolution_ids=materialization.resolution_ids, proposal_id=proposal.id, changeset_id=applied.changeset_id, old_revision=old_revision, old_state_hash=old_hash, new_revision=applied.snapshot.revision, new_state_hash=applied.snapshot.state_hash, parameter_ids=parameter_ids, outcome=ApplicationOutcome.APPLIED, application_id=app_id, preparation_id=app_id, receipt_id=app_id)

    def recover_application(self, project_id: str, run_id: str, application_id_value: str):
        preparation = self.application_store.load_preparation(project_id, run_id, application_id_value)
        try:
            receipt = self.application_store.load_receipt(project_id, run_id, application_id_value)
            self._verify_receipt_state(project_id, preparation, receipt)
            return ConstraintResolutionApplicationResult(source_command_id=receipt.source_command_id, resolution_ids=receipt.source_resolution_ids, proposal_id=receipt.proposal_id, changeset_id=receipt.changeset_id, old_revision=receipt.base_revision, old_state_hash=receipt.base_state_hash, new_revision=receipt.new_revision, new_state_hash=receipt.new_state_hash, parameter_ids=(), outcome=ApplicationOutcome.APPLIED, application_id=receipt.application_id, preparation_id=receipt.preparation_id, receipt_id=receipt.application_id)
        except Exception:
            target_path = self.state_manager._revision_path(project_id, preparation.target_revision)
            if not target_path.exists():
                base = self.state_manager._read_current(project_id)
                if base["revision"] != preparation.base_revision or base["state_hash"] != preparation.base_state_hash:
                    raise ValueError("prepared application base conflicts with current state")
                target = self._reconstruct_prepared_revision(project_id, run_id, preparation)
                self._verify_target_state(project_id, preparation)
                receipt = self._receipt_from_preparation(preparation)
                self.application_store.write_receipt(run_id, receipt)
                return self._result_from_receipt(receipt)
            target = self.state_manager._read_snapshot(project_id, preparation.target_revision)
            current_pointer = self.state_manager._read_current(project_id)
            if target.state_hash != preparation.target_state_hash:
                raise ValueError("orphan target revision conflicts with preparation")
            if current_pointer["revision"] == preparation.base_revision:
                self.state_manager.promote_existing_revision(project_id, expected_current_revision=preparation.base_revision, expected_current_hash=preparation.base_state_hash, target_revision=preparation.target_revision, target_hash=preparation.target_state_hash)
            elif current_pointer["revision"] != preparation.target_revision or current_pointer["state_hash"] != preparation.target_state_hash:
                raise ValueError("current pointer conflicts with prepared application")
            self._verify_target_state(project_id, preparation)
            receipt = StateApplicationReceiptRecord(application_id=preparation.application_id, preparation_id=preparation.application_id, project_id=project_id, run_id=run_id, source_command_id=preparation.source_command_id, source_resolution_ids=preparation.source_resolution_ids, proposal_id=preparation.proposal_id, changeset_id=preparation.changeset_id, actor=preparation.actor, base_revision=preparation.base_revision, base_state_hash=preparation.base_state_hash, new_revision=preparation.target_revision, new_state_hash=preparation.target_state_hash, operations_hash=preparation.operations_hash, outcome=ApplicationOutcome.APPLIED.value)
            self.application_store.write_receipt(run_id, receipt)
            return ConstraintResolutionApplicationResult(source_command_id=receipt.source_command_id, resolution_ids=receipt.source_resolution_ids, proposal_id=receipt.proposal_id, changeset_id=receipt.changeset_id, old_revision=receipt.base_revision, old_state_hash=receipt.base_state_hash, new_revision=receipt.new_revision, new_state_hash=receipt.new_state_hash, parameter_ids=(), outcome=ApplicationOutcome.APPLIED, application_id=receipt.application_id, preparation_id=receipt.preparation_id, receipt_id=receipt.application_id)

    def _reconstruct_prepared_revision(self, project_id, run_id, preparation):
        command = self.resolution_store.load_command(project_id, run_id, preparation.source_command_id)
        materialized = ConstraintResolutionMaterializationResult(command_id=command.command_id, resolution_ids=preparation.source_resolution_ids, resolution_records=tuple(self.resolution_store.load_resolution(project_id, run_id, item) for item in preparation.source_resolution_ids))
        current = self.state_manager.load_current_state(project_id)
        records = []
        for record in materialized.resolution_records:
            self._validate_record(command, record, materialized)
            request = self.request_store.load(project_id, run_id, record.source_constraint_request_id)
            records.append((record, request))
        operations, _ = self._plan_operations(command, current, records)
        canonical_operations = tuple(operation.model_dump(mode="json") for operation in operations)
        proposal = ChangeProposal(id=self._proposal_id(command, operations), title="Apply accepted constraint resolutions", status=ProposalStatus.ACCEPTED, base_revision=preparation.base_revision, base_state_hash=preparation.base_state_hash, actor=preparation.actor, operations=operations)
        if proposal.id != preparation.proposal_id or canonical_operations != preparation.operations or operations_hash(canonical_operations) != preparation.operations_hash:
            raise ValueError("APPLICATION_INTEGRITY_FAILURE: prepared proposal mismatch")
        _, candidate, changeset = self.change_engine.prepare_proposal(project_id, proposal, changeset_id=preparation.changeset_id)
        candidate = candidate.model_copy(update={"revision": preparation.target_revision})
        if changeset.id != preparation.changeset_id or state_hash(candidate) != preparation.target_state_hash:
            raise ValueError("APPLICATION_INTEGRITY_FAILURE: prepared candidate mismatch")
        return self.state_manager.create_revision(project_id, candidate, revision=preparation.target_revision)

    def _receipt_from_preparation(self, preparation):
        return StateApplicationReceiptRecord(application_id=preparation.application_id, preparation_id=preparation.application_id, project_id=preparation.project_id, run_id=preparation.run_id, source_command_id=preparation.source_command_id, source_resolution_ids=preparation.source_resolution_ids, proposal_id=preparation.proposal_id, changeset_id=preparation.changeset_id, actor=preparation.actor, base_revision=preparation.base_revision, base_state_hash=preparation.base_state_hash, new_revision=preparation.target_revision, new_state_hash=preparation.target_state_hash, operations_hash=preparation.operations_hash, outcome=ApplicationOutcome.APPLIED.value)

    def _result_from_receipt(self, receipt):
        return ConstraintResolutionApplicationResult(source_command_id=receipt.source_command_id, resolution_ids=receipt.source_resolution_ids, proposal_id=receipt.proposal_id, changeset_id=receipt.changeset_id, old_revision=receipt.base_revision, old_state_hash=receipt.base_state_hash, new_revision=receipt.new_revision, new_state_hash=receipt.new_state_hash, parameter_ids=(), outcome=ApplicationOutcome.APPLIED, application_id=receipt.application_id, preparation_id=receipt.preparation_id, receipt_id=receipt.application_id)

    def _verify_target_state(self, project_id, preparation):
        current = self.state_manager._read_current(project_id)
        if current["revision"] != preparation.target_revision or current["state_hash"] != preparation.target_state_hash:
            raise ValueError("application receipt requires verified target pointer")
        target = self.state_manager._read_snapshot(project_id, preparation.target_revision)
        if target.state_hash != preparation.target_state_hash or target.parent_revision != preparation.base_revision:
            raise ValueError("target revision does not match preparation")

    def _verify_receipt_state(self, project_id, preparation, receipt):
        if receipt.project_id != preparation.project_id or receipt.run_id != preparation.run_id or receipt.application_id != preparation.application_id or receipt.preparation_id != preparation.application_id or receipt.proposal_id != preparation.proposal_id or receipt.changeset_id != preparation.changeset_id or receipt.operations_hash != preparation.operations_hash or receipt.base_revision != preparation.base_revision or receipt.base_state_hash != preparation.base_state_hash or receipt.new_revision != preparation.target_revision or receipt.new_state_hash != preparation.target_state_hash:
            raise ValueError("application receipt conflicts with preparation")
        self._verify_target_state(project_id, preparation)

    def _project_id(self, materialization):
        for path in self.resolution_store.store.workspace.glob(f"projects/*/runs/*/agents/constraint_resolution_commands/{materialization.command_id}.json"):
            return path.parents[4].name
        raise ValueError("resolution command not found")

    def _validate_record(self, command: ConstraintResolutionBatchCommand, record: ConstraintResolutionRecord, materialization):
        if record.status is not ResolutionStatus.ACCEPTED or record.source_command_id != command.command_id or record.project_id != command.project_id or record.engineering_scope_id != command.engineering_scope_id or record.source_revision != command.source_revision or record.source_state_hash != command.source_state_hash or record.resolution_id not in materialization.resolution_ids:
            raise ValueError("resolution record is not bound to accepted command")
        if record.source_answer.kind != record.key.value or record.canonical_value.kind != record.key.value:
            raise ValueError("resolution discriminator mismatch")

    def _plan_operations(self, command, current, records):
        planned = []
        ids = []
        for record, _ in records:
            anchor_kind, anchor_id = _anchor_for(record.key)
            collection = current.requirements if anchor_kind == "requirement" else current.constraints
            if not any(item.id == anchor_id for item in collection):
                raise ValueError("required authoritative anchor is missing")
            ids.append(parameter_id(project_id=command.project_id, scope_id=command.engineering_scope_id, anchor_kind=anchor_kind, anchor_id=anchor_id, key=record.key))
            value = AuthoritativeParameter(id=ids[-1], anchor=AuthoritativeAnchor(kind=anchor_kind, id=anchor_id), scope_id=command.engineering_scope_id, key=record.key, value=record.canonical_value, source_resolution_id=record.resolution_id)
            existing = [item for item in current.authoritative_parameters if item.id == value.id]
            if len(existing) > 1 or any(item.anchor != value.anchor or item.scope_id != value.scope_id or item.key != value.key for item in existing):
                raise ValueError("conflicting authoritative parameter identity")
            if not existing:
                planned.append(ChangeOperation(operation=OperationType.ADD, path=f"/authoritative_parameters/{value.id}", value=value.model_dump(mode="json")))
            elif existing[0] != value:
                planned.append(ChangeOperation(operation=OperationType.REPLACE, path=f"/authoritative_parameters/{value.id}", value=value.model_dump(mode="json"), expected=existing[0].model_dump(mode="json")))
        return tuple(sorted(planned, key=lambda item: item.path)), tuple(sorted(ids))

    def _proposal_id(self, command, operations):
        payload = json.dumps([operation.model_dump(mode="json") for operation in operations], sort_keys=True, separators=(",", ":"))
        return f"CP-{uuid5(NAMESPACE_URL, json.dumps({"project_id": command.project_id, "command_id": command.command_id, "revision": command.source_revision, "state_hash": command.source_state_hash, "operations": payload}, sort_keys=True))}"


def _anchor_for(key):
    return {
        "transmission.output_angular_speed": ("requirement", "REQ-TRANSMISSION-OUTPUT-SPEED"),
        "transmission.motor_characteristics": ("requirement", "REQ-TRANSMISSION-MOTOR-CHARACTERISTICS"),
        "transmission.output_interface": ("constraint", "CON-TRANSMISSION-OUTPUT-INTERFACE"),
        "transmission.packaging_envelope": ("constraint", "CON-TRANSMISSION-PACKAGING-ENVELOPE"),
    }[key.value]
