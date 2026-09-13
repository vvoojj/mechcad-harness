import pytest
from types import MappingProxyType

from mechcad_harness.candidates.dimensions import (
    DimensionConflictError,
    DimensionInput,
    DimensionResolutionError,
    LEGACY_PLATE_DIMENSION_ALIASES,
    resolve_dimensions,
)


def _input(component_id, semantic_name, alias, value, identity, unit="mm"):
    return DimensionInput(
        component_instance_id=component_id,
        semantic_name=semantic_name,
        alias=alias,
        value=value,
        unit=unit,
        identity=identity,
    )


def test_conflicting_aliases_fail_without_alias_precedence():
    with pytest.raises(DimensionConflictError, match="mount.*length_mm"):
        resolve_dimensions(
            (
                _input("mount", "length_mm", "geometry.length_mm", 100.0, "property:geometry"),
                _input("mount", "length_mm", "length_mm", 30.0, "property:bare"),
            ),
            required_dimensions=("length_mm",),
        )


def test_equal_aliases_resolve_one_value_and_all_identities():
    resolved = resolve_dimensions(
        (
            _input("mount", "length_mm", "geometry.length_mm", 100.0, "property:geometry"),
            _input("mount", "length_mm", "length_mm", 100.0, "choice:bare"),
        ),
        required_dimensions=("length_mm",),
    )

    assert resolved[("mount", "length_mm")].value == 100.0
    assert resolved[("mount", "length_mm")].identities == ("choice:bare", "property:geometry")


@pytest.mark.parametrize(
    ("semantic_name", "aliases"),
    (
        ("length_mm", ("geometry.length_mm", "plate_length_mm", "length_mm")),
        ("width_mm", ("geometry.width_mm", "plate_width_mm", "width_mm")),
        ("thickness_mm", ("geometry.thickness_mm", "plate_thickness_mm", "thickness_mm")),
    ),
)
def test_every_legacy_plate_alias_family_requires_agreement(semantic_name, aliases):
    with pytest.raises(DimensionConflictError):
        resolve_dimensions(
            tuple(
                _input("mount", semantic_name, alias, float(index + 1), f"value:{alias}")
                for index, alias in enumerate(aliases)
            ),
            required_dimensions=(semantic_name,),
        )


def test_values_for_different_component_instances_do_not_conflict():
    resolved = resolve_dimensions(
        (
            _input("mount-a", "length_mm", "length_mm", 30.0, "a"),
            _input("mount-b", "length_mm", "length_mm", 100.0, "b"),
        ),
        required_dimensions=("length_mm",),
    )

    assert resolved[("mount-a", "length_mm")].value == 30.0
    assert resolved[("mount-b", "length_mm")].value == 100.0


@pytest.mark.parametrize(
    ("alias", "unit", "value"),
    (
        ("unknown", "mm", 30.0),
        ("length_mm", "in", 30.0),
        ("length_mm", "mm", 0.0),
        ("length_mm", "mm", float("nan")),
        ("length_mm", "mm", True),
    ),
)
def test_invalid_normalized_dimension_inputs_fail(alias, unit, value):
    with pytest.raises(DimensionResolutionError):
        resolve_dimensions(
            (_input("mount", "length_mm", alias, value, "invalid", unit),),
            required_dimensions=("length_mm",),
        )


def test_legacy_dimension_alias_authority_is_immutable():
    assert isinstance(LEGACY_PLATE_DIMENSION_ALIASES, MappingProxyType)
    with pytest.raises(TypeError):
        LEGACY_PLATE_DIMENSION_ALIASES["length_mm"] = frozenset()
