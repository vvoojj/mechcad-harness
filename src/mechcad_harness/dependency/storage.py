import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .errors import EvidenceConflictError, EvidenceIntegrityError, InvalidationError
from .graph import DependencyGraph
from .models import ChangeImpact, EvidenceFreshness, InvalidationRecord


class EvidenceStore:
    def __init__(self, workspace: str | Path, state_manager, graph: DependencyGraph):
        self.workspace = Path(workspace)
        self.state_manager = state_manager
        self.graph = graph

    def _project_dir(self, project_id: str) -> Path:
        return self.workspace / "projects" / project_id

    def _write_exclusive(self, path: Path, payload: dict, error_type: type[Exception]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise error_type(f"record already exists: {path}")
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            if path.exists():
                raise error_type(f"record already exists: {path}")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def build_invalidation(self, project_id: str, revision: int, parent_revision: int | None, changed_paths: tuple[str, ...], changeset_id: str | None) -> InvalidationRecord:
        impact = self.graph.impact(list(changed_paths))
        return InvalidationRecord(
            project_id=project_id,
            revision=revision,
            parent_revision=parent_revision,
            changeset_id=changeset_id,
            changed_paths=impact.changed_paths,
            directly_invalidated_nodes=impact.direct_nodes,
            transitively_invalidated_nodes=impact.all_nodes,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def record_invalidation(self, record: InvalidationRecord) -> None:
        path = self._project_dir(record.project_id) / "invalidations" / f"REV-{record.revision:06d}.json"
        self._write_exclusive(path, record.model_dump(mode="json"), InvalidationError)

    def _invalidation_path(self, project_id: str, revision: int) -> Path:
        return self._project_dir(project_id) / "invalidations" / f"REV-{revision:06d}.json"

    def load_invalidation(self, project_id: str, revision: int) -> InvalidationRecord:
        path = self._invalidation_path(project_id, revision)
        if not path.exists():
            raise InvalidationError(f"invalidation record missing: {path}")
        try:
            return InvalidationRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise InvalidationError(f"invalid invalidation record: {path}") from exc

    def write_evidence(self, project_id: str, evidence) -> None:
        if not self.graph.knows(evidence.kind):
            raise EvidenceIntegrityError(f"unknown dependency node: {evidence.kind}")
        path = self._project_dir(project_id) / "evidence" / f"{evidence.id}.json"
        payload = evidence.model_dump(mode="json")
        provenance = payload.get("analysis_execution_provenance")
        if provenance is not None and provenance.get("model_hash") is None:
            del provenance["model_hash"]
        self._write_exclusive(path, payload, EvidenceConflictError)

    def load_evidence(self, project_id: str, evidence_id: str):
        path = self._project_dir(project_id) / "evidence" / f"{evidence_id}.json"
        if not path.exists():
            raise EvidenceIntegrityError(f"evidence not found: {path}")
        try:
            from mechcad_harness.models.evidence import Evidence
            return Evidence.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise EvidenceIntegrityError(f"invalid evidence record: {path}") from exc

    def get_evidence_freshness(self, project_id: str, evidence_id: str) -> EvidenceFreshness:
        evidence = self.load_evidence(project_id, evidence_id)
        if not self.graph.knows(evidence.kind):
            return EvidenceFreshness.UNKNOWN
        try:
            snapshot = self.state_manager._read_snapshot(project_id, evidence.revision)
            current = self.state_manager._read_current(project_id)
        except Exception:
            return EvidenceFreshness.UNKNOWN
        if snapshot.state_hash != evidence.state_hash:
            return EvidenceFreshness.UNKNOWN
        stale = False
        for revision in range(evidence.revision + 1, current["revision"] + 1):
            try:
                record = self.load_invalidation(project_id, revision)
            except InvalidationError:
                return EvidenceFreshness.UNKNOWN
            if evidence.kind in record.transitively_invalidated_nodes:
                stale = True
        return EvidenceFreshness.STALE if stale else EvidenceFreshness.CURRENT

    def is_evidence_fresh(self, project_id: str, evidence_id: str) -> bool:
        return self.get_evidence_freshness(project_id, evidence_id) is EvidenceFreshness.CURRENT

    def get_change_impact(self, changed_paths: tuple[str, ...] | list[str]) -> ChangeImpact:
        return self.graph.impact(list(changed_paths))

    def get_invalidated_nodes(self, project_id: str, revision: int) -> tuple[str, ...]:
        return self.load_invalidation(project_id, revision).transitively_invalidated_nodes

    def fresh_evidence_status(self, project_id: str, node: str) -> str:
        evidence_dir = self._project_dir(project_id) / "evidence"
        statuses = []
        if evidence_dir.exists():
            for path in sorted(evidence_dir.glob("*.json")):
                evidence = self.load_evidence(project_id, path.stem)
                if evidence.kind == node:
                    statuses.append(self.get_evidence_freshness(project_id, evidence.id))
        if EvidenceFreshness.CURRENT in statuses:
            return "fresh evidence exists"
        if EvidenceFreshness.STALE in statuses:
            return "only stale evidence exists"
        return "fresh evidence missing"
