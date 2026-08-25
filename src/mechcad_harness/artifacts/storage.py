import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

from .models import ArtifactType, EngineeringArtifact


MEDIA_TYPES = {
    ArtifactType.FCSTD: "application/x-freecad",
    ArtifactType.STEP: "model/step",
    ArtifactType.STL: "model/stl",
    ArtifactType.JSON: "application/json",
    ArtifactType.MSH: "application/x-gmsh",
    ArtifactType.INP: "model/calcix-inp",
    ArtifactType.FRD: "application/x-calculix-frd",
    ArtifactType.DAT: "text/plain",
    ArtifactType.LOG: "text/plain",
}
_REPARSE_POINT_ATTRIBUTE = 0x0400


class ArtifactVerificationError(ValueError):
    pass


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

    def publish(self, artifact_id, artifact_type, filename, content, producer_tool_name, producer_tool_version, bound_revision, bound_state_hash, *, backend_provenance=None, build123d_provenance=None, input_hash=None):
        relative_filename = PurePosixPath(str(filename).replace("\\", "/"))
        if relative_filename.is_absolute() or len(relative_filename.parts) != 1 or relative_filename.name in {"", ".", ".."}:
            raise ValueError("artifact filename must be a single safe relative name")
        if relative_filename.suffix.lower() != f".{artifact_type.value}":
            raise ValueError("artifact filename extension does not match artifact type")
        if relative_filename.name.casefold() == "metadata.json":
            raise ValueError("artifact filename conflicts with metadata path")
        artifact_dir = self.workspace / "projects" / self.project_id / "runs" / self.run_id / "artifacts" / self._safe_scope(artifact_id, "artifact_id")
        artifact_path = artifact_dir / relative_filename.name
        metadata_path = artifact_dir / "metadata.json"
        self._validate_publish_paths(artifact_dir, artifact_path, metadata_path)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        self._validate_publish_paths(artifact_dir, artifact_path, metadata_path)
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        artifact = EngineeringArtifact(artifact_id=artifact_id, project_id=self.project_id, run_id=self.run_id, task_id=self.task_id, artifact_type=artifact_type, media_type=MEDIA_TYPES[artifact_type], relative_path=artifact_path.relative_to(self.workspace).as_posix(), sha256=digest, size_bytes=len(content), producer_tool_name=producer_tool_name, producer_tool_version=producer_tool_version, backend_provenance=backend_provenance, build123d_provenance=build123d_provenance, bound_revision=bound_revision, bound_state_hash=bound_state_hash, input_hash=input_hash)
        if os.path.lexists(artifact_path) or os.path.lexists(metadata_path):
            if artifact_path.is_file() and metadata_path.is_file():
                try:
                    existing = EngineeringArtifact.model_validate_json(metadata_path.read_text(encoding="utf-8"))
                    if (
                        existing.model_dump(mode="json", exclude={"created_at"})
                        == artifact.model_dump(mode="json", exclude={"created_at"})
                        and artifact_path.read_bytes() == content
                    ):
                        return existing
                except Exception:
                    pass
            raise FileExistsError(f"artifact conflict: {artifact_id}")
        self._validate_publish_paths(artifact_dir, artifact_path, metadata_path)
        self._atomic_bytes(artifact_path, content)
        self._validate_publish_paths(artifact_dir, artifact_path, metadata_path)
        self._atomic_text(metadata_path, json.dumps(artifact.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n")
        return artifact

    def existing(self, artifact_id):
        verified = self._verified(artifact_id)
        return verified[0] if verified is not None else None

    def existing_in_project(self, artifact_id: str) -> "EngineeringArtifact | None":
        # Project-scoped trusted lookup that reuses the run-scoped `existing`
        # boundary (type, byte SHA-256, size, relative-path, existence checks)
        # instead of duplicating filesystem-layout knowledge. Succeeds only
        # when exactly one matching artifact resolves across the project's runs.
        root = self.workspace / "projects" / self.project_id / "runs"
        if not root.is_dir():
            return None
        matches = []
        for run_dir in sorted(root.glob("*")):
            if not run_dir.is_dir():
                continue
            try:
                sub_store = ArtifactStore(self.workspace, project_id=self.project_id, run_id=run_dir.name)
            except ValueError:
                continue
            artifact = sub_store.existing(artifact_id)
            if artifact is not None:
                matches.append(artifact)
        if len(matches) != 1:
            return None
        return matches[0]

    def read_verified(self, artifact_id: str, *, expected_type=None, expected_hash=None):
        """Return a run-scoped artifact and bytes after strict identity checks."""
        return self._verified(artifact_id, expected_type=expected_type, expected_hash=expected_hash)

    def read_verified_strict(self, artifact_id: str, *, expected_type=None, expected_hash=None):
        return self._verified(
            artifact_id,
            expected_type=expected_type,
            expected_hash=expected_hash,
            raise_on_failure=True,
        )

    def read_verified_in_project(self, artifact_id: str, *, expected_type=None, expected_hash=None):
        """Resolve exactly one trusted artifact across all project runs."""
        root = self.workspace / "projects" / self.project_id / "runs"
        if not root.is_dir():
            return None
        matches = []
        for run_dir in sorted(root.glob("*")):
            if not run_dir.is_dir():
                continue
            try:
                sub_store = ArtifactStore(self.workspace, project_id=self.project_id, run_id=run_dir.name)
            except ValueError:
                continue
            verified = sub_store.read_verified(
                artifact_id, expected_type=expected_type, expected_hash=expected_hash
            )
            if verified is not None:
                matches.append(verified)
        if len(matches) != 1:
            return None
        return matches[0]

    def path_for(self, artifact: EngineeringArtifact):
        """Return a path only when the artifact still passes this store's checks."""
        verified = self._verified(artifact.artifact_id)
        if verified is None or verified[0] != artifact:
            return None
        return self._artifact_path(artifact.artifact_id, artifact.relative_path)

    def path_for_in_project(self, artifact: EngineeringArtifact):
        if artifact.project_id != self.project_id:
            return None
        try:
            store = ArtifactStore(self.workspace, project_id=self.project_id, run_id=artifact.run_id)
        except ValueError:
            return None
        return store.path_for(artifact)

    def _verified(self, artifact_id: str, *, expected_type=None, expected_hash=None, raise_on_failure=False):
        def fail(message):
            if raise_on_failure:
                raise ArtifactVerificationError(message)
            return None

        try:
            safe_artifact_id = self._safe_scope(artifact_id, "artifact_id")
        except (TypeError, ValueError):
            return fail("artifact identity is invalid")
        artifact_dir = self.workspace / "projects" / self.project_id / "runs" / self.run_id / "artifacts" / safe_artifact_id
        metadata_path = artifact_dir / "metadata.json"
        if not metadata_path.is_file():
            return fail("artifact is missing")
        try:
            artifact = EngineeringArtifact.model_validate_json(metadata_path.read_text(encoding="utf-8"))
            if artifact.artifact_id != safe_artifact_id or artifact.project_id != self.project_id or artifact.run_id != self.run_id:
                return fail("artifact identity mismatch")
            if expected_type is not None and artifact.artifact_type is not expected_type:
                return fail("artifact type mismatch")
            if expected_hash is not None and artifact.sha256 != expected_hash:
                return fail("artifact byte/hash mismatch")
            if artifact.media_type != MEDIA_TYPES[artifact.artifact_type]:
                return fail("artifact type metadata mismatch")
            path = self._artifact_path(safe_artifact_id, artifact.relative_path)
            if path.parent != artifact_dir.resolve() or path.suffix.lower() != f".{artifact.artifact_type.value}":
                return fail("artifact path is unsafe")
            if not path.is_file():
                return fail("artifact is missing")
            content = path.read_bytes()
            if not content and artifact.artifact_type is ArtifactType.LOG:
                return fail("artifact is empty")
            if len(content) != artifact.size_bytes:
                return fail("artifact byte/hash mismatch")
            if f"sha256:{hashlib.sha256(content).hexdigest()}" != artifact.sha256:
                return fail("artifact byte/hash mismatch")
            return artifact, content
        except ArtifactVerificationError:
            raise
        except Exception:
            return fail("artifact metadata or bytes are unreadable")

    def _artifact_path(self, artifact_id: str, relative_path: str) -> Path:
        relative = PurePosixPath(str(relative_path).replace("\\", "/"))
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} or ":" in part for part in relative.parts)
        ):
            raise ValueError("artifact relative path is unsafe")
        path = (self.workspace / Path(*relative.parts)).resolve()
        workspace = self.workspace.resolve()
        if path == workspace or workspace not in path.parents:
            raise ValueError("artifact relative path escapes workspace")
        return path

    @staticmethod
    def _is_reparse_point(path: Path) -> bool:
        if path.is_symlink():
            return True
        try:
            attributes = getattr(os.lstat(path), "st_file_attributes", 0)
        except OSError:
            return False
        return bool(attributes & _REPARSE_POINT_ATTRIBUTE)

    def _validate_publish_path(self, path: Path, label: str) -> Path:
        workspace = self.workspace.resolve(strict=False)
        try:
            resolved = path.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"{label} cannot be resolved safely") from exc
        if resolved == workspace or workspace not in resolved.parents:
            raise ValueError(f"{label} escapes workspace")

        lexical_workspace = Path(os.path.abspath(self.workspace))
        lexical_path = Path(os.path.abspath(path))
        try:
            relative = lexical_path.relative_to(lexical_workspace)
        except ValueError as exc:
            raise ValueError(f"{label} is outside workspace") from exc
        current = lexical_workspace
        for part in relative.parts:
            current /= part
            if self._is_reparse_point(current):
                raise ValueError(f"{label} contains a symlink or reparse point")
        return resolved

    def _validate_publish_paths(self, artifact_dir: Path, artifact_path: Path, metadata_path: Path) -> None:
        resolved_dir = self._validate_publish_path(artifact_dir, "artifact directory")
        for path, label in ((artifact_path, "artifact path"), (metadata_path, "metadata path")):
            resolved = self._validate_publish_path(path, label)
            if resolved.parent != resolved_dir:
                raise ValueError(f"{label} resolves outside artifact directory")
        if artifact_path.resolve(strict=False) == metadata_path.resolve(strict=False):
            raise ValueError("artifact path conflicts with metadata path")

    def _atomic_bytes(self, path, content):
        self._validate_publish_path(path, "publication path")
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
