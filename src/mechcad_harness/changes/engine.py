import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from mechcad_harness.models import ChangeProposal, ChangeSet, DesignState, ProposalStatus
from mechcad_harness.state import RevisionSnapshot, StateManager, state_hash

from .errors import (
    ChangeConflictError,
    ChangeSetValidationError,
    InvalidChangePathError,
    StaleProposalError,
)
from .operations import ChangeOperation, OperationType
from .ownership import OwnershipPolicy


class AppliedChangeResult:
    def __init__(self, snapshot: RevisionSnapshot, changeset_id: str, changed_paths: tuple[str, ...]):
        self.snapshot = snapshot
        self.changeset_id = changeset_id
        self.changed_paths = changed_paths


def _segments(path: str) -> list[str]:
    if not path.startswith("/") or path == "/" or "~" in path:
        raise InvalidChangePathError(f"malformed change path: {path!r}")
    segments = path[1:].split("/")
    if any(not segment for segment in segments):
        raise InvalidChangePathError(f"malformed change path: {path!r}")
    return segments


def _find_item(container: list[Any], identifier: str) -> tuple[list[Any], int]:
    for index, item in enumerate(container):
        if isinstance(item, dict) and item.get("id") == identifier:
            return container, index
    raise InvalidChangePathError(f"collection item not found: {identifier}")


def _resolve_parent(payload: dict[str, Any], segments: list[str]) -> tuple[Any, str]:
    current: Any = payload
    for segment in segments[:-1]:
        if isinstance(current, dict):
            if segment not in current:
                raise InvalidChangePathError(f"path segment not found: {segment}")
            current = current[segment]
        elif isinstance(current, list):
            current, index = _find_item(current, segment)
            current = current[index]
        else:
            raise InvalidChangePathError(f"cannot traverse path segment: {segment}")
    return current, segments[-1]


def _get_value(payload: dict[str, Any], segments: list[str]) -> Any:
    parent, leaf = _resolve_parent(payload, segments)
    if isinstance(parent, dict):
        if leaf not in parent:
            raise InvalidChangePathError(f"path not found: /{'/'.join(segments)}")
        return parent[leaf]
    if isinstance(parent, list):
        _, index = _find_item(parent, leaf)
        return parent[index]
    raise InvalidChangePathError(f"cannot resolve path: /{'/'.join(segments)}")


def apply_operation(payload: dict[str, Any], operation: ChangeOperation) -> None:
    segments = _segments(operation.path)
    parent, leaf = _resolve_parent(payload, segments)
    if operation.expected is not None:
        if _get_value(payload, segments) != operation.expected:
            raise ChangeConflictError(f"expected value mismatch at {operation.path}")
    if isinstance(parent, dict):
        exists = leaf in parent
        if operation.operation is OperationType.ADD:
            if exists:
                raise ChangeConflictError(f"path already exists: {operation.path}")
            parent[leaf] = copy.deepcopy(operation.value)
        elif operation.operation is OperationType.REPLACE:
            if not exists:
                raise InvalidChangePathError(f"path not found: {operation.path}")
            parent[leaf] = copy.deepcopy(operation.value)
        else:
            if not exists:
                raise InvalidChangePathError(f"path not found: {operation.path}")
            del parent[leaf]
    elif isinstance(parent, list):
        if operation.operation is OperationType.ADD:
            if any(isinstance(item, dict) and item.get("id") == leaf for item in parent):
                raise ChangeConflictError(f"collection item already exists: {operation.path}")
            parent.append(copy.deepcopy(operation.value))
        else:
            _, index = _find_item(parent, leaf)
            if operation.operation is OperationType.REPLACE:
                parent[index] = copy.deepcopy(operation.value)
            else:
                del parent[index]
    else:
        raise InvalidChangePathError(f"cannot modify path: {operation.path}")


class ChangeEngine:
    def __init__(self, state_manager: StateManager, ownership_policy: OwnershipPolicy):
        self.state_manager = state_manager
        self.ownership_policy = ownership_policy

    def apply_proposal(self, project_id: str, proposal: ChangeProposal) -> AppliedChangeResult:
        current = self.state_manager._read_current(project_id)
        if proposal.base_revision != current["revision"] or proposal.base_state_hash != current["state_hash"]:
            raise StaleProposalError("proposal does not match current revision and state hash")
        state = self.state_manager.load_current_state(project_id)
        payload = json.loads(json.dumps(state.model_dump(mode="json")))
        for operation in proposal.operations:
            self.ownership_policy.check(operation.path, proposal.actor)
            try:
                apply_operation(payload, operation)
            except (ChangeConflictError, InvalidChangePathError):
                raise
            except Exception as exc:
                raise ChangeSetValidationError(f"invalid operation at {operation.path}") from exc
        try:
            updated = DesignState.model_validate(payload)
        except ValidationError as exc:
            raise ChangeSetValidationError("resulting DesignState is invalid") from exc
        changeset = ChangeSet(
            id=f"CS-{uuid4()}",
            proposal_id=proposal.id,
            base_revision=proposal.base_revision,
            base_state_hash=proposal.base_state_hash,
            actor=proposal.actor,
            status=ProposalStatus.ACCEPTED,
            operations=proposal.operations,
        )
        snapshot = self.state_manager.create_revision(project_id, updated)
        return AppliedChangeResult(
            snapshot=snapshot,
            changeset_id=changeset.id,
            changed_paths=tuple(dict.fromkeys(operation.path for operation in proposal.operations)),
        )
