from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Iterable

from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.models.generated_part import GeneratedAuthorityView
from mechcad_harness.models.generated_placement import _rotation_aligning
from mechcad_harness.models.supplied_component_interface import (
    MountingFaceInterface,
    RotationalShaftInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedComponentReferenceFrame,
    SuppliedInterfaceEvidenceOrigin,
)


def _record_bytes(record: Any) -> str:
    return record.model_dump_json()


def _unique_by_identity(records: Iterable[Any], identity: str, label: str) -> tuple[Any, ...]:
    found: dict[str, Any] = {}
    for record in records:
        key = getattr(record, identity)
        if key in found:
            previous = found[key]
            if _record_bytes(previous) != _record_bytes(record):
                raise ValueError(f"candidate {label} identity has non-identical records")
            continue
        found[key] = record
    return tuple(found.values())


def _target_specification(candidate: Any, specification_hash: str) -> Any:
    matches = tuple(
        specification
        for specification in candidate.component_specifications
        if specification.specification_hash == specification_hash
    )
    if len(matches) != 1:
        raise ValueError("candidate target specification cannot be resolved by exact hash")
    return matches[0]


def _candidate_selection_records(candidate: Any) -> tuple[Any, ...]:
    variables = tuple(candidate.design_variables)
    names = tuple(variable.name for variable in variables)
    if len(set(names)) != len(names):
        raise ValueError("candidate design variable names must be unique")
    return variables


def build_candidate_view(candidate: Any, specification_hash: str) -> GeneratedAuthorityView:
    """Build the bounded generated-CAD authority view for one target spec."""

    target = _target_specification(candidate, specification_hash)
    definitions = _unique_by_identity(
        (
            definition
            for specification in candidate.component_specifications
            for definition in specification.supplied_interface_definitions
        ),
        "interface_hash",
        "M13-1 interface hash",
    )
    frames_by_identity: dict[tuple[str, str], Any] = {}
    for specification in candidate.component_specifications:
        for frame in specification.supplied_reference_frames:
            key = (frame.frame_id, frame.frame_hash)
            previous = frames_by_identity.get(key)
            if previous is not None and _record_bytes(previous) != _record_bytes(frame):
                raise ValueError("candidate M13-1 frame identity has non-identical records")
            frames_by_identity[key] = frame
    frames = tuple(frames_by_identity.values())
    generated = target.generated_part
    generated_interfaces = () if generated is None else tuple(generated.interfaces)
    generated_frames = () if generated is None else tuple(generated.reference_frames)
    return GeneratedAuthorityView(
        component_properties=tuple(target.properties),
        design_selections=_candidate_selection_records(candidate),
        interface_definitions=definitions,
        supplied_interfaces=definitions,
        reference_frames=frames + generated_frames,
        generated_interfaces=generated_interfaces,
    )


def build_canonical_view(mechanism: Any, specification_hash: str) -> GeneratedAuthorityView:
    """Build generated-CAD authority exclusively from canonical mechanism records."""

    specifications = tuple(mechanism.component_specifications)
    targets = tuple(
        specification
        for specification in specifications
        if specification.specification_hash == specification_hash
    )
    if len(targets) != 1:
        raise ValueError("canonical target specification cannot be resolved by exact hash")

    definitions = _unique_by_identity(
        (
            definition
            for specification in specifications
            for definition in specification.supplied_interface_definitions
        ),
        "interface_hash",
        "M13-1 interface",
    )
    frames_by_identity: dict[tuple[str, str], Any] = {}
    generated_frames_by_identity: dict[tuple[str, str], Any] = {}
    generated_interfaces = []
    for specification in specifications:
        for frame in specification.supplied_reference_frames:
            key = (frame.frame_id, frame.frame_hash)
            previous = frames_by_identity.get(key)
            if previous is not None and _record_bytes(previous) != _record_bytes(frame):
                raise ValueError("canonical M13-1 frame identity has non-identical records")
            frames_by_identity[key] = frame
        generated = specification.generated_part
        if generated is not None:
            for frame in generated.reference_frames:
                key = (frame.frame_id, frame.frame_hash)
                previous = generated_frames_by_identity.get(key)
                if previous is not None and _record_bytes(previous) != _record_bytes(frame):
                    raise ValueError(
                        "canonical generated frame identity has non-identical records"
                    )
                generated_frames_by_identity[key] = frame
            generated_interfaces.extend(generated.interfaces)

    return GeneratedAuthorityView(
        component_properties=tuple(targets[0].properties),
        design_selections=tuple(mechanism.accepted_design_choices),
        interface_definitions=definitions,
        supplied_interfaces=definitions,
        reference_frames=tuple(frames_by_identity.values())
        + tuple(generated_frames_by_identity.values()),
        generated_interfaces=_unique_by_identity(
            generated_interfaces, "interface_hash", "generated interface"
        ),
    )


def candidate_placement_design_variables(candidate: Any, instance_id: str) -> dict[str, float]:
    """Resolve one instance placement from either legal full-name spelling."""

    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError("placement instance ID must not be empty")
    values: dict[str, float] = {}
    for axis in ("x_mm", "y_mm", "z_mm"):
        names = (
            f"{instance_id}.placement.{axis}",
            f"placement.{instance_id}.{axis}",
        )
        matches = tuple(variable for variable in candidate.design_variables if variable.name in names)
        if len(matches) != 1:
            raise ValueError("candidate placement requires exactly one legal variable per axis")
        value = matches[0].value
        if isinstance(value, bool):
            raise ValueError("candidate placement variable must be numeric")
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate placement variable must be numeric") from exc
        if not math.isfinite(value):
            raise ValueError("candidate placement variable must be finite")
        values[axis] = value
    return values


def _fact_value(fact: Any, fact_name: str) -> Any:
    from mechcad_harness.models import supplied_component_interface as m13

    selected = next(
        (
            evidence
            for evidence in fact.evidence
            if evidence.evidence_id == fact.accepted_evidence_id
        ),
        None,
    )
    if selected is None:
        raise ValueError(f"{fact_name} accepted evidence is missing")
    if selected.evidence_origin is SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION:
        evidence = selected
    else:
        evidence = m13.require_authoritative_fact(fact, fact_name=fact_name)
    if evidence.value is None:
        raise ValueError(f"{fact_name} has no accepted value")
    return evidence.value


def m13_local_pose(
    definition_or_frame: Any,
    active_frame: SuppliedComponentReferenceFrame | None = None,
) -> CadRigidTransform:
    """Extract a local pose only after the existing M13-1 authority gate."""

    from mechcad_harness.models import supplied_component_interface as m13

    if isinstance(definition_or_frame, SuppliedComponentReferenceFrame):
        origin = _fact_value(definition_or_frame.origin, "reference frame origin")
        orientation = _fact_value(definition_or_frame.orientation, "reference frame orientation")
        return CadRigidTransform(
            x_mm=origin[0],
            y_mm=origin[1],
            z_mm=origin[2],
            rotation_quaternion=orientation,
        )

    if not isinstance(definition_or_frame, SuppliedComponentInterfaceDefinition):
        raise TypeError("M13-1 local pose requires an interface definition or reference frame")

    m13.require_authoritatively_consumable_interface(definition_or_frame, active_frame)
    variant = definition_or_frame.shaft
    if isinstance(variant, RotationalShaftInterface):
        point = _fact_value(variant.axis_point, "shaft axis point")
        direction = _fact_value(variant.axis_direction, "shaft axis direction")
    else:
        variant = definition_or_frame.mounting_face
        if not isinstance(variant, MountingFaceInterface):
            raise ValueError("M13-1 interface definition has no supported variant")
        point = _fact_value(variant.plane_point, "mounting plane point")
        direction = _fact_value(variant.outward_normal, "mounting outward normal")
    return CadRigidTransform(
        x_mm=point[0],
        y_mm=point[1],
        z_mm=point[2],
        rotation_quaternion=_rotation_aligning(direction, (0.0, 0.0, 1.0)),
    )


__all__ = [
    "build_canonical_view",
    "build_candidate_view",
    "candidate_placement_design_variables",
    "m13_local_pose",
]
