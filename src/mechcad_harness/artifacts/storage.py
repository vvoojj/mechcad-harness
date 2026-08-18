import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

from .models import ArtifactType, EngineeringArtifact


MEDIA_TYPES = {ArtifactType.STEP: "model/step", ArtifactType.STL: "model/stl"}


class ArtifactStore:
    def __init__(self, workspace, *, project_id, run_id, task_id=None):
        self.workspace = Path(workspace)
        self.project_id = self._safe_scope(project_id, "project_id")
        self.run_id = self._safe_scope(run_id, "run_id")
        self.task_id = task_id

    @staticmethod
    def _safe_scope(value, name):
        path = PurePosixPath(str(value).replace("\\", "/"))
        if not value or path.is_absolute() or len(path.parts) != 1 or path.name in {"", ".", ".."}:
            raise ValueError(f"{name} must be a single safe identifier")
        return path.name

    def publish(self, artifact_id, artifact_type, filename, content, producer_tool_name, producer_tool_version, bound_revision, bound_state_hash, *, backend_provenance=None, input_hash=None):
        relative_filename = PurePosixPath(str(filename).replace("\\", "/"))
        if relative_filename.is_absolute() or len(relative_filename.parts) != 1 or relative_filename.name in {"", ".", ".."}:
            raise ValueError("artifact filename must be a single safe relative name")
        if relative_filename.suffix.lower() != f".{artifact_type.value}":
            raise ValueError("artifact filename extension does not match artifact type")
        artifact_dir = self.workspace / "projects" / self.project_id / "runs" / self.run_id / "artifacts" / self._safe_scope(artifact_id, "artifact_id")
        artifact_path = artifact_dir / relative_filename.name
        metadata_path = artifact_dir / "metadata.json"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if artifact_path.exists() or metadata_path.exists():
            raise FileExistsError(f"artifact already exists: {artifact_id}")
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        artifact = EngineeringArtifact(artifact_id=artifact_id, project_id=self.project_id, run_id=self.run_id, task_id=self.task_id, artifact_type=artifact_type, media_type=MEDIA_TYPES[artifact_type], relative_path=artifact_path.relative_to(self.workspace).as_posix(), sha256=digest, size_bytes=len(content), producer_tool_name=producer_tool_name, producer_tool_version=producer_tool_version, backend_provenance=backend_provenance, bound_revision=bound_revision, bound_state_hash=bound_state_hash, input_hash=input_hash)
        self._atomic_bytes(artifact_path, content)
        self._atomic_text(metadata_path, json.dumps(artifact.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n")
        return artifact

    def _atomic_bytes(self, path, content):
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.{uuid4().hex}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _atomic_text(self, path, content):
        self._atomic_bytes(path, content.encode("utf-8"))
