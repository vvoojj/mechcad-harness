import pytest

from mechcad_harness.backends.freecad import freecad_object_name


def test_internal_names_are_injective_for_identifier_variants():
    names = {freecad_object_name(value) for value in ("hole-1", "hole.1", "hole_1", "a", "A")}
    assert len(names) == 5
    assert all(name.startswith("op_") for name in names)


def test_overlength_operation_name_is_rejected():
    with pytest.raises(ValueError):
        freecad_object_name("a" * 241)
