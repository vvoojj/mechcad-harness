from datetime import datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from mechcad_harness.models.proposal import ConstraintRequest
from mechcad_harness.engineering.keys import SupportedConstraintKey
from mechcad_harness.models.common import Model


class AgentConstraintRequestDraft(Model):
    key: SupportedConstraintKey
    description: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ConstraintRequestLifecycle(StrEnum):
    DISCOVERED = "discovered"


class ConstraintRequestRecord(Model):
    request: ConstraintRequest
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    source_invocation_id: str = Field(min_length=1)
    source_agent_result_id: str = Field(min_length=1)
    engineering_scope_id: str = Field(min_length=1)
    key: SupportedConstraintKey
    rationale: str = Field(min_length=1)
    lifecycle: ConstraintRequestLifecycle = ConstraintRequestLifecycle.DISCOVERED
    created_at: datetime | None = None


class ConstraintRequestStore:
    def __init__(self, workspace):
        from mechcad_harness.runs.persistence import RunStore
        self.store = RunStore(workspace)

    def _path(self, project_id, run_id, request_id):
        return self.store.run_dir(project_id, run_id) / "agents" / "constraint_requests" / f"{request_id}.json"

    def write(self, record: ConstraintRequestRecord) -> None:
        self.store._write(self._path(record.project_id, record.run_id, record.request.id), record.model_dump(mode="json"), exclusive=True)

    def load(self, project_id, run_id, request_id) -> ConstraintRequestRecord:
        return self.store._read(self._path(project_id, run_id, request_id), ConstraintRequestRecord)


class ConstraintRequestMaterializer:
    _anchors = {
        SupportedConstraintKey.OUTPUT_ANGULAR_SPEED: ("requirements", "REQ-TRANSMISSION-OUTPUT-SPEED"),
        SupportedConstraintKey.MOTOR_CHARACTERISTICS: ("requirements", "REQ-TRANSMISSION-MOTOR-CHARACTERISTICS"),
        SupportedConstraintKey.OUTPUT_INTERFACE: ("constraints", "CON-TRANSMISSION-OUTPUT-INTERFACE"),
        SupportedConstraintKey.PACKAGING_ENVELOPE: ("constraints", "CON-TRANSMISSION-PACKAGING-ENVELOPE"),
        SupportedConstraintKey.AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS: ("constraints", "CON-AZIMUTH-MOUNT-PLATE-DESIGN-REQUIREMENTS"),
    }

    def __init__(self, store: ConstraintRequestStore | None = None):
        self.store = store

    def request_id(self, *, project_id, engineering_scope_id, bound_revision, bound_state_hash, draft: AgentConstraintRequestDraft) -> str:
        identity = "\n".join((project_id, engineering_scope_id, str(bound_revision), bound_state_hash, draft.key.value))
        return f"CRREQ-{uuid5(NAMESPACE_URL, identity)}"

    def is_satisfied(self, key: SupportedConstraintKey, state, engineering_scope_id: str = "transmission") -> bool:
        collection, record_id = self._anchors.get(key, ("constraints", "CON-AZIMUTH-DRIVE-MOUNT-INTERFACE") if key is SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE else self._anchors[key])
        anchors = [item for item in getattr(state, collection) if item.id == record_id]
        parameters = [item for item in state.authoritative_parameters if item.anchor.kind == ("requirement" if collection == "requirements" else "constraint") and item.anchor.id == record_id]
        if len(parameters) > 1:
            raise ValueError("multiple authoritative parameters for anchor")
        if not anchors:
            if parameters:
                raise ValueError("authoritative parameter anchor is missing")
            return False
        if not parameters:
            return False
        parameter = parameters[0]
        if parameter.scope_id != engineering_scope_id:
            return False
        if parameter.key is not key or getattr(parameter.value, "kind", None) != key.value:
            raise ValueError("authoritative parameter key/value mismatch")
        return True

    @classmethod
    def anchor_for(cls, key: SupportedConstraintKey):
        if key is SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE:
            return ("constraint", "CON-AZIMUTH-DRIVE-MOUNT-INTERFACE")
        collection, record_id = cls._anchors[key]
        return ("requirement" if collection == "requirements" else "constraint", record_id)

    def materialize(self, *, project_id, run_id, task_id, agent_name, agent_version, source_invocation_id, source_agent_result_id, engineering_scope_id, bound_revision, bound_state_hash, source_created_at, state, drafts):
        if self.store is None:
            raise ValueError("constraint request store is required")
        records = []
        for draft in drafts:
            if self.is_satisfied(draft.key, state):
                continue
            request_id = self.request_id(project_id=project_id, engineering_scope_id=engineering_scope_id, bound_revision=bound_revision, bound_state_hash=bound_state_hash, draft=draft)
            try:
                existing = self.store.load(project_id, run_id, request_id)
            except Exception:
                existing = None
            if existing is not None:
                records.append(existing)
                continue
            record = ConstraintRequestRecord(
                request=ConstraintRequest(id=request_id, description=draft.description, revision=bound_revision, state_hash=bound_state_hash),
                project_id=project_id,
                run_id=run_id,
                task_id=task_id,
                agent_name=agent_name,
                agent_version=agent_version,
                source_invocation_id=source_invocation_id,
                source_agent_result_id=source_agent_result_id,
                engineering_scope_id=engineering_scope_id,
                key=draft.key,
                rationale=draft.rationale,
                created_at=source_created_at,
            )
            self.store.write(record)
            records.append(record)
        return tuple(records)
