from __future__ import annotations

from dataclasses import dataclass

from mechcad_harness.cad_program import (
    AxialBoreOperation,
    BasePlateOperation,
    CadPartProgram,
    CylindricalStockOperation,
    cad_program_hash,
)
from mechcad_harness.models.generated_part import (
    CylindricalHubSpecification,
    GeneratedAuthorityError,
    GeneratedAuthorityView,
    GeneratedPartSpecification,
    RectangularFrameMemberSpecification,
    SolidCircularShaftSpecification,
    derive_frame_interfaces,
    derive_hub_interfaces,
    derive_shaft_interfaces,
    evaluate_generated_field_rule,
    generated_geometry_definition_identities,
    generated_part_hash,
    resolve_generated_inputs,
)


GENERATED_PART_COMPILER_VERSION = "generated-part-compiler@1"


@dataclass(frozen=True)
class GeneratedPartCompilation:
    generated_part: GeneratedPartSpecification
    generated_part_hash: str
    generated_cad_definition_id: str
    program: CadPartProgram
    program_hash: str
    compiler_version: str
    geometry_definition_identities: tuple[str, ...]


def generated_cad_definition_id(generated_part: GeneratedPartSpecification) -> str:
    return "generated-part-" + generated_part_hash(generated_part).removeprefix("sha256:")


def required_field_slots(generated_part: GeneratedPartSpecification) -> tuple[str, ...]:
    if isinstance(generated_part, SolidCircularShaftSpecification):
        return ("shaft.diameter_mm", "shaft.length_mm")
    if isinstance(generated_part, RectangularFrameMemberSpecification):
        return ("frame.length_mm", "frame.width_mm", "frame.height_mm")
    return (
        "hub.outer_diameter_mm",
        "hub.length_mm",
        *(
            f"hub.bore:{bore.bore_id}.{field_name}"
            for bore in generated_part.bores
            for field_name in ("diameter_mm", "start_z_mm", "depth_mm")
        ),
    )


def _revalidated_part(generated_part: GeneratedPartSpecification) -> GeneratedPartSpecification:
    from pydantic import TypeAdapter

    verified = TypeAdapter(GeneratedPartSpecification).validate_python(
        generated_part.model_dump(mode="json")
    )
    if verified != generated_part:
        raise ValueError("generated part self-validation changed the semantic record")
    return verified


def _field_values(generated_part: GeneratedPartSpecification) -> dict[str, float]:
    values: dict[str, float] = {}
    for field_slot in required_field_slots(generated_part):
        prefix, separator, attribute = field_slot.partition(".")
        if field_slot.startswith("hub.bore:"):
            bore_key, separator, attribute = field_slot.removeprefix("hub.").partition(".")
            bore_id = bore_key.removeprefix("bore:")
            bore = next(
                (candidate for candidate in generated_part.bores if candidate.bore_id == bore_id),
                None,
            )
            if bore is None or not separator:
                raise ValueError("generated hub field does not identify a declared bore")
            values[field_slot] = float(getattr(bore, attribute))
        else:
            values[field_slot] = float(getattr(generated_part, attribute))
    return values


def _verify_interfaces(generated_part: GeneratedPartSpecification) -> None:
    if isinstance(generated_part, SolidCircularShaftSpecification):
        expected = derive_shaft_interfaces(generated_part)
    elif isinstance(generated_part, CylindricalHubSpecification):
        expected = derive_hub_interfaces(generated_part)
    else:
        expected = derive_frame_interfaces(generated_part)
    if tuple(generated_part.interfaces) != tuple(expected):
        raise ValueError("generated interfaces do not match pure derivation")


def _verified_field_values(
    generated_part: GeneratedPartSpecification,
    authority_view: GeneratedAuthorityView,
    owning_instance_context: str | None,
) -> dict[str, float]:
    resolved_inputs = resolve_generated_inputs(
        generated_part.inputs,
        authority_view,
        owning_instance_context=owning_instance_context,
    )
    values = _field_values(generated_part)
    bindings = {binding.field_slot: binding for binding in generated_part.field_bindings}
    required = set(required_field_slots(generated_part))
    if set(bindings) != required:
        raise ValueError("every generated geometry field requires exactly one binding")
    for field_slot, binding in bindings.items():
        try:
            field_value = evaluate_generated_field_rule(binding, resolved_inputs)
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, GeneratedAuthorityError):
                raise
            raise GeneratedAuthorityError("generated field binding cannot be replayed") from exc
        if field_value != values[field_slot]:
            raise GeneratedAuthorityError("generated field binding does not match its field value")
    return values


def verify_generated_part(
    generated_part: GeneratedPartSpecification,
    authority_view: GeneratedAuthorityView,
    owning_instance_context: str | None = None,
) -> None:
    verified = _revalidated_part(generated_part)
    _verify_interfaces(verified)
    _verified_field_values(verified, authority_view, owning_instance_context)


def _compile_program(
    generated_part: GeneratedPartSpecification, values: dict[str, float]
) -> CadPartProgram:
    part_id = generated_part.generated_part_id
    if isinstance(generated_part, SolidCircularShaftSpecification):
        operations = (
            CylindricalStockOperation(
                operation_id=f"{part_id}-stock",
                diameter_mm=values["shaft.diameter_mm"],
                length_mm=values["shaft.length_mm"],
            ),
        )
        return CadPartProgram(
            part_id=generated_cad_definition_id(generated_part),
            operations=operations,
            coordinate_system="base-center; +Z cylinder-axis",
        )
    if isinstance(generated_part, CylindricalHubSpecification):
        operations = [
            CylindricalStockOperation(
                operation_id=f"{part_id}-stock",
                diameter_mm=values["hub.outer_diameter_mm"],
                length_mm=values["hub.length_mm"],
            )
        ]
        operations.extend(
            AxialBoreOperation(
                operation_id=f"{part_id}-bore-{bore.bore_id}",
                diameter_mm=values[f"hub.bore:{bore.bore_id}.diameter_mm"],
                start_z_mm=values[f"hub.bore:{bore.bore_id}.start_z_mm"],
                depth_mm=values[f"hub.bore:{bore.bore_id}.depth_mm"],
            )
            for bore in generated_part.bores
        )
        return CadPartProgram(
            part_id=generated_cad_definition_id(generated_part),
            operations=tuple(operations),
            coordinate_system="base-center; +Z cylinder-axis",
        )
    operations = (
        BasePlateOperation(
            operation_id=f"{part_id}-stock",
            length_mm=values["frame.length_mm"],
            width_mm=values["frame.width_mm"],
            thickness_mm=values["frame.height_mm"],
        ),
    )
    return CadPartProgram(
        part_id=generated_cad_definition_id(generated_part),
        operations=operations,
        coordinate_system="lower-left-bottom; +X length, +Y width, +Z thickness",
    )


def compile_generated_part(
    generated_part: GeneratedPartSpecification,
    authority_view: GeneratedAuthorityView,
    owning_instance_context: str | None = None,
) -> GeneratedPartCompilation:
    verified = _revalidated_part(generated_part)
    _verify_interfaces(verified)
    values = _verified_field_values(verified, authority_view, owning_instance_context)
    program = _compile_program(verified, values)
    return GeneratedPartCompilation(
        generated_part=verified,
        generated_part_hash=generated_part_hash(verified),
        generated_cad_definition_id=generated_cad_definition_id(verified),
        program=program,
        program_hash=cad_program_hash(program),
        compiler_version=GENERATED_PART_COMPILER_VERSION,
        geometry_definition_identities=generated_geometry_definition_identities(verified),
    )


__all__ = [
    "GENERATED_PART_COMPILER_VERSION",
    "GeneratedPartCompilation",
    "compile_generated_part",
    "generated_cad_definition_id",
    "required_field_slots",
    "verify_generated_part",
]
