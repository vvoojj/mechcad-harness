from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import Iterable


LEGACY_PLATE_DIMENSION_ALIASES = MappingProxyType(
    {
        "length_mm": frozenset({"geometry.length_mm", "plate_length_mm", "length_mm"}),
        "width_mm": frozenset({"geometry.width_mm", "plate_width_mm", "width_mm"}),
        "thickness_mm": frozenset({"geometry.thickness_mm", "plate_thickness_mm", "thickness_mm"}),
    }
)


@dataclass(frozen=True)
class DimensionInput:
    component_instance_id: str
    semantic_name: str
    alias: str
    value: float
    unit: str
    identity: str


@dataclass(frozen=True)
class ResolvedDimension:
    value: float
    identities: tuple[str, ...]


class DimensionResolutionError(ValueError):
    pass


class DimensionConflictError(DimensionResolutionError):
    pass


def _require_nonblank(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DimensionResolutionError(f"{label} must be nonblank")


def _validate_input(item: DimensionInput) -> None:
    if not isinstance(item, DimensionInput):
        raise DimensionResolutionError("inputs must contain only DimensionInput records")

    _require_nonblank(item.component_instance_id, "component_instance_id")
    _require_nonblank(item.semantic_name, "semantic_name")
    _require_nonblank(item.alias, "alias")
    _require_nonblank(item.identity, "identity")

    aliases = LEGACY_PLATE_DIMENSION_ALIASES.get(item.semantic_name)
    if aliases is None or item.alias not in aliases:
        raise DimensionResolutionError(
            f"alias {item.alias!r} is invalid for semantic dimension {item.semantic_name!r}"
        )
    if item.unit != "mm":
        raise DimensionResolutionError("dimension values must use normalized unit 'mm'")
    if isinstance(item.value, bool) or not isinstance(item.value, Real):
        raise DimensionResolutionError("dimension value must be a finite positive number")

    numeric_value = float(item.value)
    if not math.isfinite(numeric_value) or numeric_value <= 0:
        raise DimensionResolutionError("dimension value must be a finite positive number")


def resolve_dimensions(
    inputs: Iterable[DimensionInput],
    required_dimensions: Iterable[str],
) -> dict[tuple[str, str], ResolvedDimension]:
    try:
        records = tuple(inputs)
        required = tuple(required_dimensions)
    except TypeError as exc:
        raise DimensionResolutionError("inputs and required_dimensions must be iterable") from exc

    for item in records:
        _validate_input(item)

    for semantic_name in required:
        _require_nonblank(semantic_name, "required dimension")
        if semantic_name not in LEGACY_PLATE_DIMENSION_ALIASES:
            raise DimensionResolutionError(f"unknown required semantic dimension {semantic_name!r}")

    groups: dict[tuple[str, str], list[DimensionInput]] = {}
    for item in records:
        key = (item.component_instance_id, item.semantic_name)
        groups.setdefault(key, []).append(item)

    required_names = tuple(sorted(set(required)))
    component_ids = tuple(sorted({component_id for component_id, _ in groups}))
    for component_id in component_ids:
        for semantic_name in required_names:
            if (component_id, semantic_name) not in groups:
                raise DimensionResolutionError(
                    f"dimension {component_id}.{semantic_name} is unavailable"
                )

    resolved: dict[tuple[str, str], ResolvedDimension] = {}
    for key in sorted(groups):
        ordered_records = sorted(groups[key], key=lambda item: (item.identity, item.alias))
        first = ordered_records[0]
        if any(item.value != first.value for item in ordered_records[1:]):
            component_id, semantic_name = key
            raise DimensionConflictError(
                f"conflicting values for {component_id}.{semantic_name}"
            )
        resolved[key] = ResolvedDimension(
            value=first.value,
            identities=tuple(sorted(item.identity for item in ordered_records)),
        )

    return resolved
