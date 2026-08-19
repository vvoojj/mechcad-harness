import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from mechcad_harness.models import Model


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def operations_hash(operations) -> str:
    return f"sha256:{hashlib.sha256(_canonical(operations).encode()).hexdigest()}"


def application_id(*, project_id, source_command_id, proposal_id, base_revision, base_state_hash, operations) -> str:
    identity = _canonical({"project_id": project_id, "source_command_id": source_command_id, "proposal_id": proposal_id, "base_revision": base_revision, "base_state_hash": base_state_hash, "operations": operations})
    return f"APP-{uuid5(NAMESPACE_URL, identity)}"


class StateApplicationPreparationRecord(Model):
    application_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_command_id: str = Field(min_length=1)
    source_resolution_ids: tuple[str, ...]
    proposal_id: str = Field(min_length=1)
    changeset_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    base_revision: int = Field(gt=0)
    base_state_hash: str = Field(min_length=1)
    operations: tuple[dict, ...]
    operations_hash: str = Field(min_length=1)
    target_revision: int = Field(gt=0)
    target_state_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_operations(self):
        if operations_hash(self.operations) != self.operations_hash:
            raise ValueError("application operations hash mismatch")
        if self.target_revision != self.base_revision + 1:
            raise ValueError("application target revision mismatch")
        return self


class StateApplicationReceiptRecord(Model):
    application_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_command_id: str = Field(min_length=1)
    source_resolution_ids: tuple[str, ...]
    proposal_id: str = Field(min_length=1)
    changeset_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    base_revision: int = Field(gt=0)
    base_state_hash: str = Field(min_length=1)
    new_revision: int = Field(gt=0)
    new_state_hash: str = Field(min_length=1)
    operations_hash: str = Field(min_length=1)
    outcome: str = Field(min_length=1)


class StateApplicationStore:
    def __init__(self, workspace):
        from mechcad_harness.runs.persistence import RunStore
        self.store = RunStore(workspace)

    def _path(self, project_id, run_id, directory, application_id):
        return self.store.run_dir(project_id, run_id) / "state_application" / directory / f"{application_id}.json"

    def write_preparation(self, run_id, record):
        self.store._write(self._path(record.project_id, run_id, "preparations", record.application_id), record.model_dump(mode="json"), exclusive=True)

    def load_preparation(self, project_id, run_id, application_id):
        return self.store._read(self._path(project_id, run_id, "preparations", application_id), StateApplicationPreparationRecord)

    def write_receipt(self, run_id, record):
        self.store._write(self._path(record.project_id, run_id, "receipts", record.application_id), record.model_dump(mode="json"), exclusive=True)

    def load_receipt(self, project_id, run_id, application_id):
        return self.store._read(self._path(project_id, run_id, "receipts", application_id), StateApplicationReceiptRecord)
