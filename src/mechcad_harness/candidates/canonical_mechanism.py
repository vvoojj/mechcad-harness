from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictInt, StrictStr, field_validator, model_validator

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.generated_part_cad import verify_generated_part
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models import CanonicalPhysicalMechanism, CanonicalPlacementOrigin
from mechcad_harness.models.generated_placement import (
    _resolve_rotation_input,
    compose_poses,
    place_generated_target,
    pose_from_interface,
    resolve_placement_inputs,
)
from mechcad_harness.models.supplied_component_interface import (
    GeometryDerivationStatus,
    MaterializedInterfaceVerifier,
)
from mechcad_harness.models import supplied_component_interface as m13
from mechcad_harness.state import StateManager, state_hash as calculate_state_hash

from .promotion_models import (
    PromotableMechanismProjection,
    PromotionModel,
    _nonblank,
    _require_hash,
)
from .generated_authority import build_canonical_view, m13_local_pose


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

        sources = self._verify_sources(project_id, mechanisms[0])
        mechanism = self._validate_mechanism(mechanisms[0])
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
        components_by_specification = {
            specification_hash: tuple(
                component
                for component in validated.components
                if component.specification_hash == specification_hash
            )
            for specification_hash in specification_hashes
        }
        for specification in validated.component_specifications:
            if specification.generated_part is None:
                continue
            contexts = components_by_specification[specification.specification_hash]
            for component in contexts or (None,):
                try:
                    verify_generated_part(
                        specification.generated_part,
                        build_canonical_view(validated, specification.specification_hash),
                        owning_instance_context=(
                            None if component is None else component.instance_id
                        ),
                    )
                except Exception as exc:
                    raise ValueError(
                        "canonical generated specification authority integrity failure"
                    ) from exc
        CanonicalPhysicalMechanismCompiler._validate_generated_placements(validated)
        return validated

    @staticmethod
    def _validate_generated_placements(mechanism: CanonicalPhysicalMechanism) -> None:
        derivations = mechanism.generated_placement_derivations
        specifications = {
            specification.specification_hash: specification
            for specification in mechanism.component_specifications
        }
        if not derivations:
            generated_instance_ids = {
                component.instance_id
                for component in mechanism.components
                if specifications[component.specification_hash].generated_part is not None
            }
            if any(
                placement.instance_id in generated_instance_ids
                for placement in mechanism.placements
            ):
                raise ValueError(
                    "canonical generated placement derivation set is missing"
                )
            return
        target_instance_ids = tuple(
            derivation.target_canonical_instance_id for derivation in derivations
        )
        if len(set(target_instance_ids)) != len(target_instance_ids):
            raise ValueError(
                "canonical generated placement target instance IDs must be unique"
            )
        components = {
            component.instance_id: component for component in mechanism.components
        }
        placements = {placement.instance_id: placement for placement in mechanism.placements}
        generated_instance_ids = {
            component.instance_id
            for component in mechanism.components
            if specifications[component.specification_hash].generated_part is not None
        }
        generated_placement_instance_ids = {
            placement.instance_id
            for placement in mechanism.placements
            if placement.instance_id in generated_instance_ids
        }
        generated_placements = tuple(
            placement
            for placement in mechanism.placements
            if placement.instance_id in generated_instance_ids
        )
        if len(generated_placement_instance_ids) != len(generated_placements):
            raise ValueError(
                "canonical generated placements must have one record per target instance"
            )
        if generated_placement_instance_ids != set(target_instance_ids):
            raise ValueError(
                "canonical generated placements must correspond exactly to derivation targets"
            )
        derivations_by_id = {derivation.derivation_id: derivation for derivation in derivations}
        view_by_specification = {
            specification.specification_hash: build_canonical_view(
                mechanism, specification.specification_hash
            )
            for specification in mechanism.component_specifications
        }
        resolving: set[str] = set()
        resolved: dict[str, CadRigidTransform] = {}

        def generated_interface(component, specification, interface_id, interface_hash):
            generated = specification.generated_part
            if generated is None:
                raise ValueError("canonical generated placement requires a generated target")
            if interface_id not in component.interfaces:
                raise ValueError(
                    "canonical generated placement interface is not declared by its component"
                )
            matches = tuple(
                interface
                for interface in generated.interfaces
                if interface.interface_id == interface_id
                and interface.interface_hash == interface_hash
            )
            if len(matches) != 1:
                raise ValueError("canonical generated interface reference does not resolve")
            return matches[0]

        def generated_frame(specification, frame_id, frame_hash):
            generated = specification.generated_part
            if generated is None:
                return None
            matches = tuple(
                frame
                for frame in generated.reference_frames
                if frame.frame_id == frame_id and frame.frame_hash == frame_hash
            )
            if len(matches) != 1:
                return None
            return matches[0]

        def supplied_interface(component, specification, interface_id, interface_hash):
            if interface_id not in component.interfaces:
                raise ValueError(
                    "canonical source interface is not declared by its component"
                )
            matches = tuple(
                definition
                for definition in specification.supplied_interface_definitions
                if definition.interface_id == interface_id
                and definition.interface_hash == interface_hash
            )
            if len(matches) != 1:
                raise ValueError("canonical supplied interface reference does not resolve")
            definition = matches[0]
            variant = definition.shaft or definition.mounting_face
            active_frame = None
            frame_id = getattr(variant, "reference_frame_id", None)
            if frame_id is not None:
                active_frame = next(
                    (frame for frame in specification.supplied_reference_frames if frame.frame_id == frame_id),
                    None,
                )
                if active_frame is None:
                    raise ValueError("canonical supplied interface frame does not resolve")
            return definition, definition.shaft or definition.mounting_face, active_frame

        def source_local_pose(derivation):
            source_component = components.get(derivation.source_canonical_instance_id)
            if source_component is None:
                raise ValueError("canonical placement source instance does not resolve")
            specification = specifications[source_component.specification_hash]
            generated = specification.generated_part
            if generated is not None:
                generated_interface(
                    source_component,
                    specification,
                    derivation.source_interface_id,
                    derivation.source_interface_hash,
                )
            else:
                definition, variant, active_frame = supplied_interface(
                    source_component,
                    specification,
                    derivation.source_interface_id,
                    derivation.source_interface_hash,
                )
            if derivation.rule_id == "frame-generated-placement@1":
                if derivation.source_frame_id is None or derivation.source_frame_hash is None:
                    raise ValueError("canonical source frame is missing")
                frame = generated_frame(
                    specification, derivation.source_frame_id, derivation.source_frame_hash
                )
                if frame is not None:
                    return pose_from_interface(frame)
                frame_matches = tuple(
                    candidate
                    for candidate in specification.supplied_reference_frames
                    if candidate.frame_id == derivation.source_frame_id
                    and candidate.frame_hash == derivation.source_frame_hash
                )
                if len(frame_matches) != 1:
                    raise ValueError("canonical source frame reference does not resolve")
                if (
                    variant.reference_frame_id != frame_matches[0].frame_id
                    or active_frame is None
                    or active_frame.frame_id != frame_matches[0].frame_id
                    or active_frame.frame_hash != frame_matches[0].frame_hash
                ):
                    raise ValueError(
                        "canonical source frame is not the exact frame declared by the source interface"
                    )
                m13.require_authoritatively_consumable_interface(
                    definition, frame_matches[0]
                )
                return m13_local_pose(frame_matches[0])
            if generated is not None:
                return pose_from_interface(
                    generated_interface(
                        source_component,
                        specification,
                        derivation.source_interface_id,
                        derivation.source_interface_hash,
                    )
                )
            definition, _, active_frame = supplied_interface(
                source_component,
                specification,
                derivation.source_interface_id,
                derivation.source_interface_hash,
            )
            return m13_local_pose(definition, active_frame)

        def source_placement(instance_id, reference):
            if reference.kind == "design_variable_placement":
                placement = placements.get(instance_id)
                if placement is None:
                    raise ValueError(
                        "canonical source placement record is missing"
                    )
                if (
                    placement.origin is not CanonicalPlacementOrigin.ACCEPTED_DESIGN_CHOICE
                    or placement.relation != "accepted-design-variable-placement@1"
                    or placement.rotation_quaternion != (1.0, 0.0, 0.0, 0.0)
                ):
                    raise ValueError("canonical source placement authority is invalid")
                choices = tuple(
                    next(
                        (
                            choice
                            for choice in mechanism.accepted_design_choices
                            if choice.key == f"{instance_id}.placement.{axis}"
                        ),
                        None,
                    )
                    for axis in ("x_mm", "y_mm", "z_mm")
                )
                if any(choice is None for choice in choices):
                    raise ValueError(
                        "canonical source placement design choices are missing"
                    )
                if any(
                    isinstance(choice.value, bool)
                    or not isinstance(choice.value, (int, float))
                    for choice in choices
                ):
                    raise ValueError(
                        "canonical source placement design choices are not numeric"
                    )
                expected_inputs = tuple(
                    identity
                    for choice in choices
                    for identity in choice.source_identities
                )
                if placement.input_identities != expected_inputs:
                    raise ValueError(
                        "canonical source placement design choice identities mismatch"
                    )
                expected_coordinates = tuple(float(choice.value) for choice in choices)
                if (
                    placement.x_mm,
                    placement.y_mm,
                    placement.z_mm,
                ) != expected_coordinates:
                    raise ValueError(
                        "canonical source placement design choice values mismatch"
                    )
                return CadRigidTransform(
                    x_mm=placement.x_mm,
                    y_mm=placement.y_mm,
                    z_mm=placement.z_mm,
                    rotation_quaternion=placement.rotation_quaternion,
                )
            dependency = derivations_by_id.get(reference.derivation_id)
            if dependency is None or dependency.target_canonical_instance_id != instance_id:
                raise ValueError("canonical source placement reference does not resolve")
            return derive(dependency)

        def target_local_pose(derivation):
            target_component = components.get(derivation.target_canonical_instance_id)
            if target_component is None:
                raise ValueError("canonical placement target instance does not resolve")
            specification = specifications[target_component.specification_hash]
            if derivation.rule_id == "coaxial-generated-placement@1":
                interface_id = derivation.target_generated_interface_id
                interface_hash = derivation.target_generated_interface_hash
                if interface_id is None or interface_hash is None:
                    raise ValueError("canonical target interface is missing")
                return pose_from_interface(
                    generated_interface(
                        target_component, specification, interface_id, interface_hash
                    )
                )
            frame_id = derivation.target_generated_frame_id
            frame_hash = derivation.target_generated_frame_hash
            if frame_id is None or frame_hash is None:
                raise ValueError("canonical target frame is missing")
            frame = generated_frame(specification, frame_id, frame_hash)
            if frame is None:
                raise ValueError("canonical target frame does not resolve")
            return pose_from_interface(frame)

        def derive(derivation):
            if derivation.derivation_id in resolving:
                raise ValueError("canonical placement derivation set must be acyclic")
            if derivation.derivation_id in resolved:
                return resolved[derivation.derivation_id]
            resolving.add(derivation.derivation_id)
            source_component = components.get(derivation.source_canonical_instance_id)
            if source_component is None:
                raise ValueError("canonical placement source instance does not resolve")
            source_pose = compose_poses(
                source_placement(
                    derivation.source_canonical_instance_id,
                    derivation.source_placement_ref,
                ),
                source_local_pose(derivation),
            )
            target_component = components.get(derivation.target_canonical_instance_id)
            if target_component is None:
                raise ValueError("canonical placement target instance does not resolve")
            target_view = view_by_specification[target_component.specification_hash]
            inputs = resolve_placement_inputs(derivation, target_view)
            if len(inputs) > 1:
                raise ValueError("canonical generated placement has more than one axial offset")
            rotation = (
                _resolve_rotation_input(derivation, target_view)
                if derivation.rotation is not None
                else None
            )
            result = place_generated_target(
                derivation.rule_id,
                source_pose,
                target_local_pose(derivation),
                next(iter(inputs.values()), None),
                rotation,
            )
            resolving.remove(derivation.derivation_id)
            resolved[derivation.derivation_id] = result
            return result

        for derivation in derivations:
            target = derivation.target_canonical_instance_id
            target_component = components.get(target)
            if target_component is None:
                raise ValueError("canonical placement derivation target is unknown")
            target_specification = specifications[target_component.specification_hash]
            if target_specification.generated_part is None:
                raise ValueError("canonical placement derivation target is not generated")
            expected = derive(derivation)
            placement = placements.get(target)
            if placement is None:
                raise ValueError("canonical generated placement record is missing")
            target_hash = (
                derivation.target_generated_interface_hash
                if derivation.target_generated_interface_hash is not None
                else derivation.target_generated_frame_hash
            )
            if target_hash is None:
                raise ValueError("canonical generated placement target identity is missing")
            expected_inputs = (
                derivation.source_interface_hash,
                target_hash,
                *sorted(item.input_hash for item in derivation.inputs),
                *(
                    ()
                    if derivation.rotation is None
                    else (derivation.rotation.input_hash,)
                ),
            )
            actual = CadRigidTransform(
                x_mm=placement.x_mm,
                y_mm=placement.y_mm,
                z_mm=placement.z_mm,
                rotation_quaternion=placement.rotation_quaternion,
            )
            if (
                actual != expected
                or placement.origin.value != "deterministic_relation"
                or placement.relation != derivation.rule_id
                or placement.input_identities != expected_inputs
            ):
                raise ValueError("canonical placement does not match its generated derivation")

    def _verify_sources(
        self, project_id: str, mechanism: CanonicalPhysicalMechanism
    ) -> tuple[TrustedSourceArtifact, ...]:
        references = {}
        identities = {}

        def register_identity(identity: GeometryArtifactIdentity) -> None:
            prior = identities.get(identity.artifact_id)
            if prior is not None and prior != identity:
                raise ValueError("canonical geometry artifact identity conflict")
            identities[identity.artifact_id] = identity

        for specification in mechanism.component_specifications:
            source = specification.geometry_source
            if source is not None:
                prior = references.get(source.artifact_id)
                if prior is not None and prior != source:
                    raise ValueError("canonical geometry source reference conflict")
                references[source.artifact_id] = source
                register_identity(GeometryArtifactIdentity.from_canonical(source))

            transforms = {
                transform.transform_id: transform
                for transform in specification.geometry_derivation_transforms
            }
            for transform in specification.geometry_derivation_transforms:
                if transform.status is GeometryDerivationStatus.ACCEPTED:
                    register_identity(transform.source_geometry)
                    register_identity(transform.derived_geometry)

            for active_interface in specification.supplied_interface_definitions:
                if active_interface.kind != "materialized":
                    continue
                provenance = active_interface.derivation
                assert provenance is not None
                register_identity(provenance.source_geometry)
                register_identity(provenance.derived_geometry)
                transform = transforms.get(provenance.transform_id)
                if transform is None or transform.transform_hash != provenance.transform_hash:
                    raise ValueError(
                        "canonical materialized interface transform does not resolve"
                    )
                if transform.status is not GeometryDerivationStatus.ACCEPTED:
                    raise ValueError(
                        "canonical materialized interface transform is not accepted"
                    )
        if not identities:
            return ()

        store = self._artifact_store(project_id)
        artifacts = {}
        for identity in identities.values():
            try:
                verified = store.read_verified_in_project(
                    identity.artifact_id,
                    expected_type=ArtifactType.STEP,
                    expected_hash=identity.artifact_hash,
                )
            except Exception as exc:
                raise ValueError(
                    f"canonical geometry artifact verification failed: {exc}"
                ) from exc
            if verified is None:
                raise ValueError("canonical geometry source is missing or tampered")
            artifact, _ = verified
            if (
                artifact.artifact_id != identity.artifact_id
                or artifact.project_id != project_id
                or artifact.artifact_type is not ArtifactType.STEP
                or artifact.sha256 != identity.artifact_hash
            ):
                raise ValueError("canonical geometry artifact binding mismatch")
            if identity.artifact_id in references:
                source = references[identity.artifact_id]
                try:
                    artifacts[source.artifact_id] = TrustedSourceArtifact.from_artifact(
                        artifact
                    )
                except Exception as exc:
                    raise ValueError(
                        "canonical geometry source provenance is invalid"
                    ) from exc

        for specification in mechanism.component_specifications:
            transforms = {
                transform.transform_id: transform
                for transform in specification.geometry_derivation_transforms
            }
            for active_interface in specification.supplied_interface_definitions:
                if active_interface.kind != "materialized":
                    continue
                provenance = active_interface.derivation
                assert provenance is not None
                transform = transforms.get(provenance.transform_id)
                assert transform is not None
                active_frame = None
                if provenance.derived_reference_frame_id is not None:
                    active_frame = next(
                        (
                            frame
                            for frame in specification.supplied_reference_frames
                            if frame.frame_id == provenance.derived_reference_frame_id
                            and frame.frame_hash == provenance.derived_reference_frame_hash
                        ),
                        None,
                    )
                    if active_frame is None:
                        raise ValueError(
                            "canonical materialized interface frame does not resolve"
                        )
                try:
                    MaterializedInterfaceVerifier.verify(
                        provenance, transform, active_interface, active_frame
                    )
                except Exception as exc:
                    raise ValueError(
                        f"canonical materialized interface integrity failure: {exc}"
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


def validate_canonical_mechanism(
    mechanism: CanonicalPhysicalMechanism,
) -> CanonicalPhysicalMechanism:
    """Re-run canonical semantic integrity checks at every trusted boundary."""

    return CanonicalPhysicalMechanismCompiler._validate_mechanism(mechanism)


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
        generated_placement_derivations=mechanism.generated_placement_derivations,
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
    "validate_canonical_mechanism",
    "normalized_projection",
]
