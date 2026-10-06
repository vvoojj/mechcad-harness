from __future__ import annotations

import binascii
import hashlib
import math
from typing import Literal

from pydantic import Field, field_validator, model_validator

from mechcad_harness.cad_program import CadPartProgram, cad_program_hash
from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.models.common import Model


M10_EXECUTION_SEMANTICS_VERSION = "m10-execution-semantics@1"


def _require_semantic_fields(record, expected_type, expected_fields, label: str) -> None:
    if not isinstance(record, expected_type):
        raise TypeError(f"{label} has an unsupported semantic record type")
    actual = set(type(record).model_fields)
    expected = set(expected_fields)
    if actual != expected:
        raise ValueError(
            f"{label} declared fields are not allowlisted: "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


class CadRigidTransform(Model):
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    rotation_quaternion: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, data):
        data = dict(data)
        quaternion = tuple(float(value) for value in data.get("rotation_quaternion", (1.0, 0.0, 0.0, 0.0)))
        values = (float(data.get("x_mm", 0.0)), float(data.get("y_mm", 0.0)), float(data.get("z_mm", 0.0)), *quaternion)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("rigid transform values must be finite")
        norm = math.sqrt(sum(value * value for value in quaternion))
        if norm <= 1e-12:
            raise ValueError("rotation quaternion must have non-zero norm")
        quaternion = tuple(value / norm for value in quaternion)
        first_nonzero = next((value for value in quaternion if abs(value) > 1e-12), 1.0)
        if first_nonzero < 0:
            quaternion = tuple(-value for value in quaternion)
        data["rotation_quaternion"] = quaternion
        return data


class CadComponentInstance(Model):
    instance_id: str = Field(min_length=1)
    part_id: str = Field(min_length=1)
    placement: CadRigidTransform = Field(default_factory=CadRigidTransform)


class CadAssemblyProgram(Model):
    assembly_id: str = Field(min_length=1)
    parts: tuple[CadPartProgram, ...] = Field(default_factory=tuple)
    imported_components: tuple[ImportedCadComponent, ...] = Field(default_factory=tuple)
    instances: tuple[CadComponentInstance, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_registry(self) -> "CadAssemblyProgram":
        if not self.parts and not self.imported_components:
            raise ValueError("at least one part or imported component is required")

        part_ids = [part.part_id for part in self.parts]
        imported_ids = [comp.component_id for comp in self.imported_components]
        all_component_ids = part_ids + imported_ids

        if len(set(part_ids)) != len(part_ids):
            raise ValueError("part IDs must be unique")
        if len(set(imported_ids)) != len(imported_ids):
            raise ValueError("imported component IDs must be unique")
        if len(set(all_component_ids)) != len(all_component_ids):
            raise ValueError("part and imported component IDs must be unique across each other")

        instance_ids = [instance.instance_id for instance in self.instances]
        if len(set(instance_ids)) != len(instance_ids):
            raise ValueError("instance IDs must be unique")

        registered = set(all_component_ids)
        if any(instance.part_id not in registered for instance in self.instances):
            raise ValueError("instance references an unknown component")
        if set(instance.part_id for instance in self.instances) != registered:
            raise ValueError("unused component definitions are not allowed")
        return self

    @property
    def canonical_parts(self) -> tuple[CadPartProgram, ...]:
        return tuple(sorted(self.parts, key=lambda part: part.part_id))

    @property
    def canonical_imported_components(self) -> tuple[ImportedCadComponent, ...]:
        return tuple(sorted(self.imported_components, key=lambda comp: comp.component_id))

    @property
    def canonical_instances(self) -> tuple[CadComponentInstance, ...]:
        return tuple(sorted(self.instances, key=lambda instance: instance.instance_id))

    @property
    def all_component_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                [part.part_id for part in self.parts] +
                [comp.component_id for comp in self.imported_components]
            )
        )

    @property
    def has_imported_components(self) -> bool:
        return len(self.imported_components) > 0


def instance_object_name(instance_id: str) -> str:
    encoded = binascii.hexlify(instance_id.encode("utf-8")).decode("ascii")
    if len(encoded) > 240:
        raise ValueError("instance_id is too long for deterministic FreeCAD identity")
    return f"inst_{encoded}"


def assembly_hash(program: CadAssemblyProgram) -> str:
    payload = {
        "assembly_id": program.assembly_id,
        "parts": [{"part_id": part.part_id, "program_hash": cad_program_hash(part)} for part in program.canonical_parts],
        "imported_components": [
            {
                "component_id": comp.component_id,
                "artifact_id": comp.artifact_id,
                "artifact_hash": comp.artifact_hash,
                "format": comp.format,
                "source_revision": comp.source_revision,
                "source_state_hash": comp.source_state_hash,
                "component_hash": imported_component_hash(comp),
            }
            for comp in program.canonical_imported_components
        ],
        "instances": [instance.model_dump(mode="json") | {"part_id": instance.part_id} for instance in program.canonical_instances],
    }
    canonical = canonical_json_bytes(payload)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def verified_semantic_assembly_hash(
    program: CadAssemblyProgram,
    mappings,
    replay_source_assembly_hash: str,
) -> str:
    """Bind the §10 identity to the exact legacy assembly used for replay."""
    _require_semantic_fields(
        program,
        CadAssemblyProgram,
        {"assembly_id", "parts", "imported_components", "instances"},
        "CadAssemblyProgram",
    )
    try:
        reconstructed = CadAssemblyProgram.model_validate(
            program.model_dump(mode="json")
        )
    except Exception as exc:
        raise ValueError(f"CAD assembly reconstruction failed: {exc}") from exc
    actual_legacy_hash = assembly_hash(reconstructed)
    if replay_source_assembly_hash != actual_legacy_hash:
        raise ValueError("source assembly hash does not match reconstructed assembly")

    # Import locally: candidate CAD models depend on this module for their
    # legacy serialization boundary, while the projection is a pure reuse of
    # the accepted §10 candidate-CAD semantic assembly payload.
    from mechcad_harness.candidates.cad_realization import (
        CandidateCadInstanceMappingV2,
        SemanticSourceGeometryIdentity,
        semantic_assembly_hash,
    )
    from mechcad_harness.candidates.canonical_cad import (
        CanonicalPhysicalCadMappingV2,
    )

    mappings = tuple(mappings)
    candidate_mapping_fields = {
        "schema_version", "candidate_hash", "physical_instance_id", "cad_instance_id",
        "fidelity", "representation_identity", "source_geometry_identity",
        "geometry_definition_identities", "placement", "placement_origin", "mapping_hash",
    }
    canonical_mapping_fields = {
        "schema_version", "mechanism_hash", "physical_instance_id", "cad_instance_id",
        "component_hash", "specification_hash", "fidelity", "representation_identity",
        "source_geometry_identity", "geometry_definition_identities", "placement",
        "placement_id", "placement_input_identities", "placement_relation", "mapping_hash",
    }
    mapping_layers = set()
    for mapping in mappings:
        if isinstance(mapping, CandidateCadInstanceMappingV2):
            _require_semantic_fields(
                mapping, CandidateCadInstanceMappingV2, candidate_mapping_fields,
                "CandidateCadInstanceMappingV2",
            )
            mapping_layers.add("candidate")
        elif isinstance(mapping, CanonicalPhysicalCadMappingV2):
            _require_semantic_fields(
                mapping, CanonicalPhysicalCadMappingV2, canonical_mapping_fields,
                "CanonicalPhysicalCadMappingV2",
            )
            mapping_layers.add("canonical")
        else:
            raise TypeError("semantic assembly requires a new-family CAD mapping")
    if len(mapping_layers) > 1:
        raise ValueError("semantic assembly CAD mappings must not mix candidate and canonical")
    if len({mapping.cad_instance_id for mapping in mappings}) != len(mappings):
        raise ValueError("semantic assembly CAD mapping IDs must be unique")
    if mappings and {mapping.cad_instance_id for mapping in mappings} != {
        instance.instance_id for instance in reconstructed.instances
    }:
        raise ValueError("semantic assembly mappings do not cover the reconstructed assembly")
    if reconstructed.imported_components and not mappings:
        raise ValueError("trusted imported assembly requires semantic CAD mappings")
    for mapping in mappings:
        source = mapping.source_geometry_identity
        if source is not None:
            _require_semantic_fields(
                source,
                SemanticSourceGeometryIdentity,
                {"content_identity", "content_identity_algorithm"},
                "SemanticSourceGeometryIdentity",
            )
            if (
                source.content_identity is None
                or source.content_identity == "pending"
                or not source.content_identity.startswith("sha256:")
                or len(source.content_identity) != 71
                or source.content_identity_algorithm != "step-content-identity@1"
            ):
                raise ValueError("semantic assembly source identity is not finalized")
    return semantic_assembly_hash(reconstructed, mappings)
