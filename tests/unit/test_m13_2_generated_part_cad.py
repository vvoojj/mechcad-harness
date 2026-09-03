from __future__ import annotations

import ast
import inspect

import pytest

from mechcad_harness.cad_program import (
    BasePlateOperation,
    CylindricalStockOperation,
    AxialBoreOperation,
    cad_program_hash,
)
from mechcad_harness.models import (
    CylindricalHubSpecification,
    GeneratedAuthorityInput,
    GeneratedAuthorityView,
    GeneratedPartFieldBinding,
    RectangularFrameMemberSpecification,
    SolidCircularShaftSpecification,
    selection_hash,
    value_hash,
)


def _input(input_id: str, value: float, *, role: str = "dimension") -> GeneratedAuthorityInput:
    return GeneratedAuthorityInput(
        input_id=input_id,
        role=role,
        source_kind="design_selection",
        locator={
            "name_form": "component_scoped",
            "selection_key": input_id,
            "selection_hash": selection_hash("component_scoped", input_id, value),
        },
        value=value,
        value_hash=value_hash(value),
    )


def _direct(slot: str, input_id: str, value: float) -> GeneratedPartFieldBinding:
    return GeneratedPartFieldBinding(
        field_slot=slot,
        source={"input_id": input_id},
        field_value_hash=value_hash(value),
    )


def _shaft(diameter: float = 12.5, length: float = 40.0) -> SolidCircularShaftSpecification:
    return SolidCircularShaftSpecification(
        generated_part_id="shaft",
        diameter_mm=diameter,
        length_mm=length,
        inputs=(_input("diameter", diameter), _input("length", length)),
        field_bindings=(
            _direct("shaft.diameter_mm", "diameter", diameter),
            _direct("shaft.length_mm", "length", length),
        ),
    )


def _view(*inputs: GeneratedAuthorityInput) -> GeneratedAuthorityView:
    return GeneratedAuthorityView(
        design_selections={input_record.input_id: input_record.value for input_record in inputs}
    )


def _hub_with_clearance() -> tuple[CylindricalHubSpecification, GeneratedAuthorityView]:
    inputs = (
        _input("outer", 30.0),
        _input("length", 50.0),
        _input("supplied", 10.0, role="supplied_diameter"),
        _input("clearance", 0.5, role="clearance"),
        _input("start", 5.0),
        _input("depth", 20.0),
    )
    hub = CylindricalHubSpecification(
        generated_part_id="hub",
        outer_diameter_mm=30.0,
        length_mm=50.0,
        bores=({"bore_id": "input", "diameter_mm": 10.5, "start_z_mm": 5.0, "depth_mm": 20.0},),
        inputs=inputs,
        field_bindings=(
            _direct("hub.outer_diameter_mm", "outer", 30.0),
            _direct("hub.length_mm", "length", 50.0),
            GeneratedPartFieldBinding(
                field_slot="hub.bore:input.diameter_mm",
                source={
                    "rule_id": "hub-bore-from-supplied-shaft-with-clearance@1",
                    "input_ids": ["supplied", "clearance"],
                },
                field_value_hash=value_hash(10.5),
            ),
            _direct("hub.bore:input.start_z_mm", "start", 5.0),
            _direct("hub.bore:input.depth_mm", "depth", 20.0),
        ),
    )
    return hub, _view(*inputs)


def test_same_spec_compiles_to_identical_program_and_hash():
    from mechcad_harness.generated_part_cad import compile_generated_part

    first = compile_generated_part(_shaft(), _view(*_shaft().inputs))
    second = compile_generated_part(_shaft(), _view(*_shaft().inputs))

    assert first.program == second.program
    assert first.program_hash == second.program_hash == cad_program_hash(first.program)
    assert first.program.part_id == first.generated_cad_definition_id


def test_required_slots_and_cylinder_lowering_have_bound_values_and_stable_ids():
    from mechcad_harness.generated_part_cad import compile_generated_part, required_field_slots

    spec = _shaft()
    result = compile_generated_part(spec, _view(*spec.inputs))

    assert required_field_slots(spec) == ("shaft.diameter_mm", "shaft.length_mm")
    assert isinstance(result.program.operations[0], CylindricalStockOperation)
    assert result.program.operations[0].operation_id == "shaft-stock"
    assert result.program.operations[0].diameter_mm == spec.diameter_mm
    assert result.program.operations[0].length_mm == spec.length_mm
    assert result.program.coordinate_system == "base-center; +Z cylinder-axis"


def test_unbound_slot_is_rejected_even_if_the_spec_dimension_is_present():
    from mechcad_harness.generated_part_cad import verify_generated_part

    spec = _shaft()
    object.__setattr__(spec, "field_bindings", (spec.field_bindings[0],))
    with pytest.raises(ValueError, match="binding|field"):
        verify_generated_part(spec, _view(*spec.inputs))


def test_authority_view_value_mismatch_rejects_admitted_twenty_generated_fifteen():
    from mechcad_harness.generated_part_cad import compile_generated_part

    spec = _shaft(diameter=15.0)
    forged_view = GeneratedAuthorityView(
        design_selections={"diameter": 20.0, "length": spec.length_mm}
    )
    with pytest.raises(ValueError, match="match|bound|resolved"):
        compile_generated_part(spec, forged_view)


def test_hub_relation_replays_clearance_and_changes_bore_and_hash():
    from mechcad_harness.generated_part_cad import compile_generated_part

    hub, view = _hub_with_clearance()
    result = compile_generated_part(hub, view)
    bore = result.program.operations[1]
    assert isinstance(bore, AxialBoreOperation)
    assert bore.operation_id == "hub-bore-input"
    assert bore.diameter_mm == 10.5

    direct_hub = hub.model_copy(deep=True)
    direct_binding = _direct("hub.bore:input.diameter_mm", "supplied", 10.0)
    object.__setattr__(direct_hub, "field_bindings", tuple(
        direct_binding if binding.field_slot == direct_binding.field_slot else binding
        for binding in direct_hub.field_bindings
    ))
    with pytest.raises(ValueError):
        compile_generated_part(direct_hub, view)


def test_missing_relation_input_and_unknown_rule_fail_closed(monkeypatch):
    from mechcad_harness.generated_part_cad import compile_generated_part
    import mechcad_harness.models.generated_part as generated_part

    hub, view = _hub_with_clearance()
    missing = GeneratedAuthorityView(
        design_selections={key: value for key, value in view.design_selections.items() if key != "clearance"}
    )
    with pytest.raises(ValueError, match="missing|resolve|bound"):
        compile_generated_part(hub, missing)

    monkeypatch.delitem(generated_part._RULES, "hub-bore-from-supplied-shaft-with-clearance@1")
    with pytest.raises(ValueError, match="unknown|rule"):
        compile_generated_part(hub, view)


def test_frame_lowering_uses_base_plate_operation_and_plate_coordinates():
    from mechcad_harness.generated_part_cad import compile_generated_part

    inputs = (_input("length", 60.0), _input("width", 20.0), _input("height", 10.0))
    spec = RectangularFrameMemberSpecification(
        generated_part_id="frame",
        length_mm=60.0,
        width_mm=20.0,
        height_mm=10.0,
        inputs=inputs,
        field_bindings=(
            _direct("frame.length_mm", "length", 60.0),
            _direct("frame.width_mm", "width", 20.0),
            _direct("frame.height_mm", "height", 10.0),
        ),
    )
    result = compile_generated_part(spec, _view(*inputs))
    base = result.program.operations[0]
    assert isinstance(base, BasePlateOperation)
    assert base.operation_id == "frame-stock"
    assert (base.length_mm, base.width_mm, base.thickness_mm) == (60.0, 20.0, 10.0)
    assert result.program.coordinate_system == "lower-left-bottom; +X length, +Y width, +Z thickness"


def test_definition_identity_is_full_hash_and_depends_on_complete_spec():
    from mechcad_harness.generated_part_cad import generated_cad_definition_id

    first = _shaft()
    second = _shaft(length=41.0)
    first_id = generated_cad_definition_id(first)
    assert first_id == "generated-part-" + first.generated_part_hash.removeprefix("sha256:")
    assert len(first_id.removeprefix("generated-part-")) == len("0" * 64)
    assert generated_cad_definition_id(first) == generated_cad_definition_id(_shaft())
    assert first_id != generated_cad_definition_id(second)


def test_compiler_module_contains_no_numeric_geometry_defaults():
    import mechcad_harness.generated_part_cad as compiler

    numeric_constants = [
        node
        for node in ast.walk(ast.parse(inspect.getsource(compiler)))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ]
    assert numeric_constants == []
