import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import Field

from mechcad_harness.ids import IdPrefix
from mechcad_harness.models import DesignState, Model

from .errors import RevisionConflictError, RevisionNotFoundError, StateIntegrityError
from .hashing import canonical_payload, state_hash


SCHEMA_VERSION = "m1"


class RevisionSnapshot(Model):
    project_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    parent_revision: int | None = Field(default=None, ge=1)
    revision_id: str = Field(min_length=1)
    state_hash: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    state: DesignState


class StateManager:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)

    def _project_dir(self, project_id: str) -> Path:
        return self.workspace / "projects" / project_id

    def _revision_path(self, project_id: str, revision: int) -> Path:
        return self._project_dir(project_id) / "revisions" / f"REV-{revision:06d}.json"

    def _current_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "current.json"

    def _write_atomic(self, path: Path, payload: dict[str, Any], *, exclusive: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if exclusive and path.exists():
            raise RevisionConflictError(f"revision already exists: {path.name}")
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            if exclusive and path.exists():
                raise RevisionConflictError(f"revision already exists: {path.name}")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _write_snapshot(self, snapshot: RevisionSnapshot) -> None:
        self._write_atomic(self._revision_path(snapshot.project_id, snapshot.revision), snapshot.model_dump(mode="json"), exclusive=True)

    def create_project(self, project_id: str, state: DesignState) -> RevisionSnapshot:
        if self._project_dir(project_id).exists():
            raise RevisionConflictError(f"project already exists: {project_id}")
        state = state.model_copy(update={"revision": 1})
        snapshot = RevisionSnapshot(
            project_id=project_id,
            revision=1,
            revision_id=f"{IdPrefix.REVISION.value}-000001",
            state_hash=state_hash(state),
            schema_version=SCHEMA_VERSION,
            state=state,
        )
        self._write_snapshot(snapshot)
        self._write_atomic(self._current_path(project_id), {
            "project_id": project_id,
            "revision": snapshot.revision,
            "state_hash": snapshot.state_hash,
        })
        return snapshot

    def create_revision(self, project_id: str, state: DesignState, revision: int | None = None) -> RevisionSnapshot:
        current = self._read_current(project_id)
        parent_revision = current["revision"]
        current_state = self.load_current_state(project_id)
        if state_hash(current_state) != current["state_hash"] and revision is None:
            raise StateIntegrityError(f"current state changed during revision creation: {project_id}")
        next_revision = parent_revision + 1 if revision is None else revision
        if next_revision <= parent_revision:
            raise RevisionConflictError("new revision must be greater than current revision")
        state = state.model_copy(update={"revision": next_revision})
        snapshot = RevisionSnapshot(
            project_id=project_id,
            revision=next_revision,
            parent_revision=parent_revision,
            revision_id=f"{IdPrefix.REVISION.value}-{next_revision:06d}",
            state_hash=state_hash(state),
            schema_version=SCHEMA_VERSION,
            state=state,
        )
        self._write_snapshot(snapshot)
        self._write_atomic(self._current_path(project_id), {
            "project_id": project_id,
            "revision": snapshot.revision,
            "state_hash": snapshot.state_hash,
        })
        return snapshot

    def _read_current(self, project_id: str) -> dict[str, Any]:
        path = self._current_path(project_id)
        if not path.exists():
            raise RevisionNotFoundError(f"current state not found for project: {project_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _read_snapshot(self, project_id: str, revision: int) -> RevisionSnapshot:
        path = self._revision_path(project_id, revision)
        if not path.exists():
            raise RevisionNotFoundError(f"revision not found: {project_id}:{revision}")
        try:
            snapshot = RevisionSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StateIntegrityError(f"invalid revision snapshot: {path}") from exc
        if state_hash(snapshot.state) != snapshot.state_hash:
            raise StateIntegrityError(f"state hash mismatch: {path}")
        return snapshot

    def load_current_state(self, project_id: str) -> DesignState:
        current = self._read_current(project_id)
        snapshot = self._read_snapshot(project_id, current["revision"])
        if snapshot.state_hash != current["state_hash"]:
            raise StateIntegrityError(f"current pointer hash mismatch: {project_id}")
        return snapshot.state

    def load_revision(self, project_id: str, revision: int) -> DesignState:
        return self._read_snapshot(project_id, revision).state

    def verify_revision(self, project_id: str, revision: int) -> bool:
        self._read_snapshot(project_id, revision)
        return True
