from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictInt, StrictStr, field_validator, model_validator

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.models import CanonicalPhysicalMechanism
from mechcad_harness.state import StateManager, state_hash as calculate_state_hash

from .promotion_models import (
    PromotableMechanismProjection,
    PromotionModel,
    _nonblank,
    _require_hash,
)


class ProjectArtifactResolver:
    """Project-wide lookup over a store whose run scope is operational only."""

    def __init__(self, store: ArtifactStore) -> None:
        if not isinstance(store, ArtifactStore):
            raise ValueError("project artifact resolver requires an ArtifactStore")
        self._store = store
        self._workspace = store.workspace.resolve()
        self._project_id = store.project_id

    @property
    def workspace(self) -> Path:
        return self._workspace

    @property
    def project_id(self) -> str:
        return self._project_id

    def read_verified_in_project(
        self,
        artifact_id: str,
        *,
        expected_type: ArtifactType | None = None,
        expected_hash: str | None = None,
    ) -> tuple[EngineeringArtifact, bytes] | None:
        if (
            self._store.workspace.resolve() != self._workspace
            or self._store.project_id != self._project_id
        ):
            raise ValueError("project artifact resolver scope changed")
        return self._store.read_verified_in_project(
            artifact_id, expected_type=expected_type, expected_hash=expected_hash
        )


class TrustedSourceArtifact(PromotionModel):
    """Immutable snapshot of a verified selected source artifact."""

    schema_version: Literal["trusted-source-artifact@1"] = "trusted-source-artifact@1"
    artifact_id: StrictStr = Field(min_length=1)
    project_id: StrictStr = Field(min_length=1)
    run_id: StrictStr = Field(min_length=1)
    task_id: StrictStr | None = None
    artifact_type: ArtifactType = ArtifactType.STEP
    media_type: StrictStr = Field(min_length=1)
    relative_path: StrictStr = Field(min_length=1)
    sha256: StrictStr
    size_bytes: StrictInt = Field(gt=0)
    producer_tool_name: StrictStr = Field(min_length=1)
    producer_tool_version: StrictStr = Field(min_length=1)
    backend_provenance: BackendProvenance | None = None
    build123d_provenance: BackendProvenance | None = None
    bound_revision: StrictInt = Field(gt=0)
    bound_state_hash: StrictStr
    input_hash: StrictStr | None = None
    created_at: datetime

    _validate_text = field_validator(
        "artifact_id",
        "project_id",
        "run_id",
        "media_type",
        "relative_path",
        "producer_tool_name",
        "producer_tool_version",
    )(_nonblank)
    _validate_optional_text = field_validator("task_id", "input_hash")(
        lambda value: None if value is None else _nonblank(value)
    )
    _validate_hashes = field_validator("sha256", "bound_state_hash")(_require_hash)

    @field_validator("created_at")
    @classmethod
    def require_utc_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("artifact_type")
    @classmethod
    def require_step(cls, value: ArtifactType) -> ArtifactType:
        if value is not ArtifactType.STEP:
            raise ValueError("trusted source artifact must be a STEP artifact")
        return value

    @classmethod
    def from_artifact(cls, artifact: EngineeringArtifact) -> "TrustedSourceArtifact":
        return cls.model_validate(artifact.model_dump(mode="json"))


class CanonicalMechanismReconstruction(PromotionModel):
    """A verified canonical mechanism reconstructed from one state revision."""

    schema_version: Literal["canonical-mechanism-reconstruction@1"] = (
        "canonical-mechanism-reconstruction@1"
    )
    project_id: StrictStr = Field(min_length=1)
    revision: StrictInt = Field(gt=0)
    state_hash: StrictStr
    canonical_mechanism: CanonicalPhysicalMechanism
    trusted_source_references: tuple[TrustedSourceArtifact, ...] = ()
    normalized_projection_hash: StrictStr

    _validate_text = field_validator("project_id")(_nonblank)
    _validate_hashes = field_validator("state_hash", "normalized_projection_hash")(
        _require_hash
    )

    @model_validator(mode="after")
    def validate_reconstruction(self) -> "CanonicalMechanismReconstruction":
        source_references = {
            specification.geometry_source.artifact_id: specification.geometry_source
            for specification in self.canonical_mechanism.component_specifications
            if specification.geometry_source is not None
        }
        trusted_sources = {
            artifact.artifact_id: artifact
            for artifact in self.trusted_source_references
        }
        if len(trusted_sources) != len(self.trusted_source_references):
            raise ValueError("trusted source references must be unique")
        if set(source_references) != set(trusted_sources):
            raise ValueError("trusted source references do not match canonical geometry sources")
        for artifact_id, source in source_references.items():
            artifact = trusted_sources[artifact_id]
            if (
                artifact.project_id != self.project_id
                or artifact.artifact_id != source.artifact_id
                or artifact.artifact_type is not ArtifactType.STEP
                or artifact.sha256 != source.artifact_hash
            ):
                raise ValueError("trusted source artifact binding mismatch")
        expected_projection_hash = _projection_from_mechanism(
            self.canonical_mechanism
        ).projection_hash
        if self.normalized_projection_hash != expected_projection_hash:
            raise ValueError("canonical reconstruction projection hash mismatch")
        return self

    @property
    def mechanism(self) -> CanonicalPhysicalMechanism:
        return self.canonical_mechanism

    @property
    def trusted_source_artifacts(self) -> tuple[TrustedSourceArtifact, ...]:
        return self.trusted_source_references


class CanonicalPhysicalMechanismCompiler:
    """Reconstruct canonical physical semantics without transient M12 inputs."""

    def __init__(self, state_manager: StateManager, artifact_store_factory) -> None:
        if not callable(artifact_store_factory) and not isinstance(
            artifact_store_factory, (ArtifactStore, ProjectArtifactResolver)
        ):
            raise ValueError(
                "canonical reconstruction requires a project artifact resolver factory"
            )
        self.state_manager = state_manager
        self.artifact_store_factory = artifact_store_factory

    def reconstruct(
        self, project_id: str, revision: int, state_hash: str, mechanism_id: str
    ) -> CanonicalMechanismReconstruction:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project ID must not be empty")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision <= 0:
            raise ValueError("revision must be positive")
        _require_hash(state_hash)
        if not isinstance(mechanism_id, str) or not mechanism_id.strip():
            raise ValueError("mechanism ID must not be empty")

        state = self.state_manager.load_revision(project_id, revision)
        actual_hash = calculate_state_hash(state)
        if state.revision != revision or actual_hash != state_hash:
            raise ValueError("canonical state revision or hash binding mismatch")

        mechanisms = tuple(
            mechanism
            for mechanism in state.physical_mechanisms
            if mechanism.id == mechanism_id
        )
        if len(mechanisms) != 1:
            raise ValueError("canonical mechanism is missing or ambiguous")

        mechanism = self._validate_mechanism(mechanisms[0])
        sources = self._verify_sources(project_id, mechanism)
        projection = _projection_from_mechanism(mechanism)
        return CanonicalMechanismReconstruction(
            project_id=project_id,
            revision=revision,
            state_hash=actual_hash,
            canonical_mechanism=mechanism,
            trusted_source_references=sources,
            normalized_projection_hash=projection.projection_hash,
        )

    @staticmethod
    def _validate_mechanism(mechanism: CanonicalPhysicalMechanism) -> CanonicalPhysicalMechanism:
        try:
            validated = CanonicalPhysicalMechanism.model_validate(
                mechanism.model_dump(mode="json")
            )
        except Exception as exc:
            raise ValueError(f"canonical mechanism integrity failure: {exc}") from exc

        specification_hashes = {
            specification.specification_hash for specification in validated.component_specifications
        }
        component_ids = {component.instance_id for component in validated.components}
        if any(
            len(set(component.interfaces)) != len(component.interfaces)
            for component in validated.components
        ):
            raise ValueError("canonical component interfaces must be unique")
        if len({choice.key for choice in validated.accepted_design_choices}) != len(
            validated.accepted_design_choices
        ):
            raise ValueError("canonical design choice keys must be unique")
        if any(
            source.geometry_source is not None
            and source.geometry_source.format != "step"
            for source in validated.component_specifications
        ):
            raise ValueError("canonical geometry source format is unsupported")
        if any(
            binding.expected_parent_instance_id not in component_ids
            or binding.expected_child_instance_id not in component_ids
            for binding in validated.joint_bindings
        ):
            raise ValueError("canonical joint binding references a missing component")
        if any(
            component.specification_hash not in specification_hashes
            for component in validated.components
        ):
            raise ValueError("canonical component specification binding is invalid")
        return validated

    def _verify_sources(
        self, project_id: str, mechanism: CanonicalPhysicalMechanism
    ) -> tuple[TrustedSourceArtifact, ...]:
        references = {}
        for specification in mechanism.component_specifications:
            source = specification.geometry_source
            if source is None:
                continue
            prior = references.get(source.artifact_id)
            if prior is not None and prior != source:
                raise ValueError("canonical geometry source reference conflict")
            references[source.artifact_id] = source
        if not references:
            return ()

        store = self._artifact_store(project_id)
        artifacts = {}
        for source in references.values():
            try:
                verified = store.read_verified_in_project(
                    source.artifact_id,
                    expected_type=ArtifactType.STEP,
                    expected_hash=source.artifact_hash,
                )
            except Exception as exc:
                raise ValueError(f"canonical geometry source verification failed: {exc}") from exc
            if verified is None:
                raise ValueError("canonical geometry source is missing or tampered")
            artifact, _ = verified
            if (
                artifact.artifact_id != source.artifact_id
                or artifact.project_id != project_id
                or artifact.artifact_type is not ArtifactType.STEP
                or artifact.sha256 != source.artifact_hash
            ):
                raise ValueError("canonical geometry source binding mismatch")
            try:
                artifacts[source.artifact_id] = TrustedSourceArtifact.from_artifact(artifact)
            except Exception as exc:
                raise ValueError(
                    "canonical geometry source provenance is invalid"
                ) from exc
        return tuple(artifacts[artifact_id] for artifact_id in references)

    def _artifact_store(self, project_id: str):
        factory = self.artifact_store_factory
        if isinstance(factory, ArtifactStore):
            resolver = ProjectArtifactResolver(factory)
        elif isinstance(factory, ProjectArtifactResolver):
            resolver = factory
        else:
            try:
                resolver = factory(project_id)
            except TypeError as exc:
                raise ValueError(
                    "canonical artifact resolver factory must accept project_id only"
                ) from exc
        if not isinstance(resolver, ProjectArtifactResolver):
            raise ValueError(
                "canonical artifact resolver must be a ProjectArtifactResolver"
            )
        if resolver.workspace != Path(self.state_manager.workspace).resolve():
            raise ValueError("canonical artifact resolver workspace scope mismatch")
        if resolver.project_id != project_id:
            raise ValueError("canonical artifact resolver project scope mismatch")
        return resolver


def _projection_from_mechanism(
    mechanism: CanonicalPhysicalMechanism,
) -> PromotableMechanismProjection:
    return PromotableMechanismProjection(
        canonical_target_mechanism_id=mechanism.id,
        canonical_instance_ids=tuple(
            component.instance_id for component in mechanism.components
        ),
        component_specifications=mechanism.component_specifications,
        components=mechanism.components,
        accepted_design_choices=mechanism.accepted_design_choices,
        placements=mechanism.placements,
        connections=mechanism.connections,
        joint_bindings=mechanism.joint_bindings,
        m10_obligations=mechanism.m10_obligations,
        mapping_identities=tuple(
            component.instance_id for component in mechanism.components
        ),
    )


def normalized_projection(
    reconstruction: CanonicalMechanismReconstruction,
) -> PromotableMechanismProjection:
    if not isinstance(reconstruction, CanonicalMechanismReconstruction):
        raise TypeError("normalized projection requires a canonical reconstruction")
    validated = CanonicalMechanismReconstruction.model_validate(
        reconstruction.model_dump(mode="json")
    )
    projection = _projection_from_mechanism(validated.canonical_mechanism)
    if projection.projection_hash != validated.normalized_projection_hash:
        raise ValueError("canonical reconstruction projection hash mismatch")
    return projection


__all__ = [
    "CanonicalMechanismReconstruction",
    "CanonicalPhysicalMechanismCompiler",
    "ProjectArtifactResolver",
    "TrustedSourceArtifact",
    "normalized_projection",
]
