from __future__ import annotations

import math

import pytest

from mechcad_harness.candidates.models import ComponentSpecificationSnapshot
from mechcad_harness.models import (
    CylindricalHubSpecification,
    GeneratedAuthorityInput,
    M13_1InterfaceFactLocator,
    GeneratedPartFieldBinding,
    GeneratedAuthorityView,
    SolidCircularShaftSpecification,
    selection_hash,
    value_hash,
)
from mechcad_harness.models.supplied_component_interface import (
    RotationalShaftInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedInterfaceTransformRole,
)

from test_m13_2_candidate_cad_integration import (
    _candidate,
    _hub_spec,
    _mixed_fixture,
    _selection_input,
    _state,
    _shaft_spec,
)
from test_m13_geometry_materialization import (
    _frame_for_source,
    _transform,
    _source_shaft_with_frame,
    materialize_interface,
)


def _adapter():
    try:
        from mechcad_harness.candidates.generated_authority import (
            build_candidate_view,
            candidate_placement_design_variables,
            m13_local_pose,
        )
    except ModuleNotFoundError:
        pytest.fail("candidate generated authority adapter is missing")
    return build_candidate_view, candidate_placement_design_variables, m13_local_pose


def _m13_input(interface: SuppliedComponentInterfaceDefinition, value: float = 10.0):
    fact = interface.shaft.nominal_shaft_diameter
    evidence_id = fact.accepted_evidence_id
    assert evidence_id is not None
    return GeneratedAuthorityInput(
        input_id="supplied",
        role="supplied_diameter",
        source_kind="m13_1_interface_fact",
        locator={
            "interface_hash": interface.interface_hash,
            "fact_id": fact.fact_id,
            "accepted_evidence_id": evidence_id,
            "value_hash": value_hash(value),
        },
        value=value,
        value_hash=value_hash(value),
    )


def _hub_from_m13(interface: SuppliedComponentInterfaceDefinition, *, clearance=None):
    baseline = _hub_spec().generated_part
    assert isinstance(baseline, CylindricalHubSpecification)
    supplied = _m13_input(interface)
    inputs = tuple(input_record for input_record in baseline.inputs if input_record.input_id != "hub_bore_diameter")
    inputs += (supplied,)
    if clearance is not None:
        clearance_input = GeneratedAuthorityInput(
            input_id="clearance",
            role="clearance",
            source_kind="design_selection",
            locator={
                "name_form": "component_scoped",
                "selection_key": "clearance",
                "selection_hash": selection_hash("component_scoped", "clearance", clearance),
            },
            value=clearance,
            value_hash=value_hash(clearance),
        )
        inputs += (clearance_input,)
    rule_id = (
        "hub-bore-from-supplied-shaft-with-clearance@1"
        if clearance is not None
        else "hub-bore-from-supplied-shaft@1"
    )
    source_ids = ("supplied", "clearance") if clearance is not None else ("supplied",)
    bore_value = 10.0 if clearance is None else 10.0 + clearance
    bindings = tuple(
        GeneratedPartFieldBinding(
            field_slot=binding.field_slot,
            source={"rule_id": rule_id, "input_ids": source_ids},
            field_value_hash=value_hash(bore_value),
        )
        if binding.field_slot == "hub.bore:input.diameter_mm"
        else binding
        for binding in baseline.field_bindings
    )
    payload = baseline.model_dump(mode="json")
    payload.update(
        inputs=inputs,
        field_bindings=bindings,
        bores=tuple(
            {
                **bore,
                "diameter_mm": bore_value,
            }
            if bore["bore_id"] == "input"
            else bore
            for bore in payload["bores"]
        ),
        interfaces=(),
        reference_frames=(),
        generated_part_hash="pending",
    )
    generated = CylindricalHubSpecification.model_validate(payload)
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@3",
        component_type="hub",
        source_identity="generated:hub-definition",
        generated_part=generated,
        interfaces=generated.active_interface_ids,
    )


def _candidate_with_target_spec(candidate, target: ComponentSpecificationSnapshot):
    specs = tuple(
        target if specification.component_type == "hub" else specification
        for specification in candidate.component_specifications
    )
    components = tuple(
        component.model_copy(
            update={"specification_hash": target.specification_hash}
        )
        if component.role.value == "hub_or_coupling"
        else component
        for component in candidate.realization.components
    )
    return candidate.model_validate(
        candidate.model_dump(mode="python")
        | {
            "component_specifications": specs,
            "realization": {
                **candidate.realization.model_dump(mode="python"),
                "components": components,
                "realization_hash": "pending",
            },
            "candidate_hash": "pending",
        }
    )


def test_authorized_m13_shaft_diameter_replays_direct_and_clearance_hub_rules(tmp_path):
    build_candidate_view, _, m13_local_pose = _adapter()
    _, candidate, _, _, specifications, _ = _mixed_fixture(tmp_path)
    motor = specifications[0]
    pose = m13_local_pose(motor.supplied_interface_definitions[0])
    assert (pose.x_mm, pose.y_mm, pose.z_mm) == (1.0, 2.0, 3.0)
    assert pose.rotation_quaternion == (1.0, 0.0, 0.0, 0.0)
    target = _hub_from_m13(motor.supplied_interface_definitions[0])
    candidate = _candidate_with_target_spec(candidate, target)
    view = build_candidate_view(candidate, target.specification_hash)

    direct = target.generated_part
    assert direct is not None
    assert direct.bores[0].diameter_mm == 10.0
    from mechcad_harness.generated_part_cad import compile_generated_part

    assert compile_generated_part(direct, view).program.operations[1].diameter_mm == 10.0

    clearance_target = _hub_from_m13(motor.supplied_interface_definitions[0], clearance=0.5)
    clearance_candidate = _candidate_with_target_spec(
        candidate.model_copy(
            update={
                "design_variables": tuple(candidate.design_variables)
                + (type(candidate.design_variables[0])(name="clearance", value=0.5),)
            }
        ),
        clearance_target,
    )
    clearance_view = build_candidate_view(clearance_candidate, clearance_target.specification_hash)
    assert compile_generated_part(
        clearance_target.generated_part, clearance_view
    ).program.operations[1].diameter_mm == 10.5


def test_missing_or_unauthorized_m13_interface_fails_closed(tmp_path):
    build_candidate_view, _, _ = _adapter()
    _, candidate, _, _, specifications, _ = _mixed_fixture(tmp_path)
    target = _hub_from_m13(specifications[0].supplied_interface_definitions[0])
    candidate = _candidate_with_target_spec(candidate, target)
    original_input = target.generated_part.inputs[-1]
    forged = GeneratedAuthorityInput(
        input_id=original_input.input_id,
        role=original_input.role,
        source_kind=original_input.source_kind,
        locator=M13_1InterfaceFactLocator(
            interface_hash="sha256:" + "f" * 64,
            fact_id=original_input.locator.fact_id,
            accepted_evidence_id=original_input.locator.accepted_evidence_id,
            value_hash=value_hash(10.0),
        ),
        value=10.0,
        value_hash=value_hash(10.0),
    )
    generated_payload = target.generated_part.model_dump(mode="json")
    generated_payload["inputs"][-1] = forged.model_dump(mode="json")
    generated_payload["generated_part_hash"] = "pending"
    forged_target = ComponentSpecificationSnapshot.model_validate(
        target.model_dump(mode="python")
        | {
            "generated_part": type(target.generated_part).model_validate(generated_payload),
            "specification_hash": "pending",
        }
    )
    forged_candidate = _candidate_with_target_spec(candidate, forged_target)
    from mechcad_harness.generated_part_cad import compile_generated_part

    with pytest.raises(ValueError):
        compile_generated_part(
            forged_target.generated_part,
            build_candidate_view(forged_candidate, forged_target.specification_hash),
        )


def test_changed_m13_evidence_does_not_replay_the_bound_value(tmp_path):
    build_candidate_view, _, _ = _adapter()
    _, candidate, _, _, specifications, _ = _mixed_fixture(tmp_path)
    motor = specifications[0]
    original = motor.supplied_interface_definitions[0]
    payload = original.model_dump(mode="json")
    evidence = payload["shaft"]["nominal_shaft_diameter"]["evidence"][0]
    evidence["value"] = 11.0
    evidence["evidence_hash"] = "pending"
    payload["shaft"]["nominal_shaft_diameter"]["fact_hash"] = "pending"
    payload["shaft"]["interface_hash"] = "pending"
    payload["interface_hash"] = "pending"
    changed = SuppliedComponentInterfaceDefinition.model_validate(payload)
    changed_motor = ComponentSpecificationSnapshot.model_validate(
        motor.model_dump(mode="python")
        | {
            "supplied_interface_definitions": (changed,),
            "interfaces": (changed.interface_id,),
            "specification_hash": "pending",
        }
    )
    changed_target = _hub_from_m13(changed)
    changed_candidate = _candidate_with_target_spec(
        candidate.model_validate(
            candidate.model_dump(mode="python")
            | {
                "component_specifications": (
                    changed_motor,
                    *candidate.component_specifications[1:],
                ),
                "realization": {
                    **candidate.realization.model_dump(mode="python"),
                    "components": tuple(
                        component.model_copy(
                            update={"specification_hash": changed_motor.specification_hash}
                        )
                        if component.instance_id == "motor-a"
                        else component
                        for component in candidate.realization.components
                    ),
                    "realization_hash": "pending",
                },
                "candidate_hash": "pending",
            }
        ),
        changed_target,
    )
    from mechcad_harness.generated_part_cad import compile_generated_part

    with pytest.raises(ValueError):
        compile_generated_part(
            changed_target.generated_part,
            build_candidate_view(changed_candidate, changed_target.specification_hash),
        )


def test_interface_locator_does_not_depend_on_outer_specification_hash(tmp_path):
    build_candidate_view, _, _ = _adapter()
    _, candidate, _, _, specifications, _ = _mixed_fixture(tmp_path)
    motor = specifications[0]
    target = _hub_from_m13(motor.supplied_interface_definitions[0])
    candidate = _candidate_with_target_spec(candidate, target)
    altered_payload = target.model_dump(mode="json")
    altered_payload["source_identity"] = "generated:hub-other-container"
    altered_payload["specification_hash"] = "pending"
    altered = ComponentSpecificationSnapshot.model_validate(altered_payload)
    altered_candidate = _candidate_with_target_spec(candidate, altered)
    view = build_candidate_view(altered_candidate, altered.specification_hash)
    assert view.interface_definitions
    assert view.interface_definitions[0].interface_hash == motor.supplied_interface_definitions[0].interface_hash


def test_generated_binding_bytes_are_stable_when_instance_ids_change(tmp_path):
    build_candidate_view, _, _ = _adapter()
    _, first, _, _, specifications, _ = _mixed_fixture(tmp_path)
    target = _hub_from_m13(specifications[0].supplied_interface_definitions[0])
    first = _candidate_with_target_spec(first, target)
    second = first.model_copy(deep=True)
    components = tuple(
        component.model_copy(update={"instance_id": component.instance_id + "-other"})
        for component in second.realization.components
    )
    second = second.model_validate(
        second.model_dump(mode="python")
        | {
            "realization": {
                **second.realization.model_dump(mode="python"),
                "components": components,
                "realization_hash": "pending",
            },
            "candidate_hash": "pending",
        }
    )
    first_spec = next(
        specification
        for specification in first.component_specifications
        if specification.component_type == "hub"
    )
    second_spec = next(
        specification
        for specification in second.component_specifications
        if specification.component_type == "hub"
    )
    assert first_spec.generated_part is not None
    assert second_spec.generated_part is not None
    assert first_spec.generated_part.model_dump_json() == second_spec.generated_part.model_dump_json()
    assert "candidate:" not in first_spec.generated_part.model_dump_json()
    assert "shaft-a" not in first_spec.generated_part.model_dump_json()
    assert build_candidate_view(first, target.specification_hash).design_selections
    assert build_candidate_view(second, target.specification_hash).design_selections


def test_unequal_instance_scoped_selection_fails_for_the_other_instance():
    build_candidate_view, _, _ = _adapter()
    first = GeneratedAuthorityInput(
        input_id="diameter",
        role="dimension",
        source_kind="design_selection",
        locator={
            "name_form": "instance_scoped",
            "selection_key": "diameter_mm",
            "selection_hash": selection_hash("instance_scoped", "diameter_mm", 12.5),
        },
        value=12.5,
        value_hash=value_hash(12.5),
    )
    shaft = SolidCircularShaftSpecification(
        generated_part_id="shaft",
        diameter_mm=12.5,
        length_mm=40.0,
        inputs=(first, _selection_input("length", 40.0)),
        field_bindings=(
            GeneratedPartFieldBinding(
                field_slot="shaft.diameter_mm",
                source={"input_id": "diameter"},
                field_value_hash=value_hash(12.5),
            ),
            GeneratedPartFieldBinding(
                field_slot="shaft.length_mm",
                source={"input_id": "length"},
                field_value_hash=value_hash(40.0),
            ),
        ),
    )
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@3",
        component_type="shaft",
        source_identity="generated:shaft",
        generated_part=shaft,
        interfaces=shaft.active_interface_ids,
    )
    candidate, _, _ = _candidate(_state(), specification, ("shaft-a", "shaft-b"))
    variables = tuple(candidate.design_variables) + (
        type(candidate.design_variables[0])(name="shaft-a.diameter_mm", value=12.5),
        type(candidate.design_variables[0])(name="shaft-b.diameter_mm", value=15.0),
    )
    candidate = candidate.model_copy(update={"design_variables": variables})
    from mechcad_harness.generated_part_cad import compile_generated_part

    view = build_candidate_view(candidate, specification.specification_hash)
    assert compile_generated_part(shaft, view, owning_instance_context="shaft-a")
    with pytest.raises(ValueError):
        compile_generated_part(shaft, view, owning_instance_context="shaft-b")


def test_placement_helper_accepts_only_the_two_nonlegacy_full_name_aliases(tmp_path):
    _, candidate, _, _, _, _ = _mixed_fixture(tmp_path)
    _, placement_variables, _ = _adapter()
    values = placement_variables(candidate, "motor-a")
    assert values == {"x_mm": 10.0, "y_mm": 20.0, "z_mm": 30.0}

    alias_candidate = candidate.model_copy(
        update={
            "design_variables": tuple(
                type(variable)(
                    name=variable.name.replace(
                        "motor-a.placement.", "placement.motor-a."
                    ),
                    value=variable.value,
                )
                if variable.name.startswith("motor-a.placement.")
                else variable
                for variable in candidate.design_variables
            )
        }
    )
    assert placement_variables(alias_candidate, "motor-a") == values

    legacy = candidate.model_copy(
        update={
            "design_variables": tuple(
                variable
                for variable in candidate.design_variables
                if not variable.name.startswith("motor-a.placement.")
            )
            + tuple(
                type(candidate.design_variables[0])(
                    name=f"geometry.motor-a.{axis}", value=value
                )
                for axis, value in (("x_mm", 10.0), ("y_mm", 20.0), ("z_mm", 30.0))
            ),
        }
    )
    with pytest.raises(ValueError):
        placement_variables(legacy, "motor-a")


def test_materialized_m13_local_pose_uses_gate_and_accepted_derived_values(monkeypatch):
    _, _, m13_local_pose = _adapter()
    import mechcad_harness.models.supplied_component_interface as m13

    source = _source_shaft_with_frame()
    active_source_frame = _frame_for_source(source.geometry)
    transform = _transform(
        rotation=(math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5))
    )
    materialized = materialize_interface(source, active_source_frame, transform)
    active_frame = materialized.reference_frame
    assert active_frame is not None

    gate_calls = []
    fact_calls = []
    original_gate = m13.require_authoritatively_consumable_interface
    original_fact = m13.require_authoritative_fact

    def record_gate(definition, reference_frame=None):
        gate_calls.append((definition, reference_frame))
        return original_gate(definition, reference_frame)

    def reject_derived_fact(fact, *, fact_name):
        fact_calls.append(fact)
        selected = next(
            evidence
            for evidence in fact.evidence
            if evidence.evidence_id == fact.accepted_evidence_id
        )
        if selected.evidence_origin.value == "derived_materialization":
            pytest.fail("m13_local_pose sent a derived fact to require_authoritative_fact")
        return original_fact(fact, fact_name=fact_name)

    monkeypatch.setattr(m13, "require_authoritatively_consumable_interface", record_gate)
    monkeypatch.setattr(m13, "require_authoritative_fact", reject_derived_fact)

    pose = m13_local_pose(materialized.interface, active_frame)

    assert gate_calls == [(materialized.interface, active_frame)]
    assert pose.x_mm == pytest.approx(-2.5)
    assert pose.y_mm == pytest.approx(1.25)
    assert pose.z_mm == pytest.approx(3.75)
    assert pose.rotation_quaternion == pytest.approx((1.0, 0.0, 0.0, 0.0))
    assert fact_calls


def test_materialized_m13_frame_pose_uses_the_exact_active_frame_after_gate(monkeypatch):
    _, _, m13_local_pose = _adapter()
    import mechcad_harness.models.supplied_component_interface as m13

    source = _source_shaft_with_frame()
    source_frame = _frame_for_source(source.geometry)
    materialized = materialize_interface(source, source_frame, _transform())
    active_frame = materialized.reference_frame
    assert active_frame is not None

    original_gate = m13.require_authoritatively_consumable_interface
    original_fact = m13.require_authoritative_fact
    gate_calls = []

    def record_gate(definition, reference_frame=None):
        gate_calls.append((definition.interface_hash, reference_frame.frame_hash))
        return original_gate(definition, reference_frame)

    def reject_derived_fact(fact, *, fact_name):
        selected = next(
            evidence
            for evidence in fact.evidence
            if evidence.evidence_id == fact.accepted_evidence_id
        )
        if selected.evidence_origin.value == "derived_materialization":
            pytest.fail("m13_local_pose sent a derived frame fact to require_authoritative_fact")
        return original_fact(fact, fact_name=fact_name)

    monkeypatch.setattr(m13, "require_authoritatively_consumable_interface", record_gate)
    monkeypatch.setattr(m13, "require_authoritative_fact", reject_derived_fact)

    pose = m13_local_pose(materialized.interface, active_frame)
    frame_pose = m13_local_pose(active_frame)

    assert gate_calls == [(materialized.interface.interface_hash, active_frame.frame_hash)]
    assert pose.x_mm == pytest.approx(1.25)
    assert frame_pose.x_mm == pytest.approx(2.5)
    assert frame_pose.y_mm == pytest.approx(3.75)
    assert frame_pose.z_mm == pytest.approx(5.0)
    assert frame_pose.rotation_quaternion == pytest.approx(
        (1.0, 0.0, 0.0, 0.0)
    )

    wrong_frame = active_frame.model_copy(update={"frame_hash": "sha256:" + "f" * 64})
    with pytest.raises(ValueError, match="frame"):
        m13_local_pose(materialized.interface, wrong_frame)


def test_direct_m13_local_pose_keeps_the_direct_authority_gate(monkeypatch):
    _, _, m13_local_pose = _adapter()
    import mechcad_harness.models.supplied_component_interface as m13

    definition = _source_shaft_with_frame().model_copy(
        update={"kind": "direct"}
    )
    gate_calls = []
    original_gate = m13.require_authoritatively_consumable_interface

    def record_gate(interface, reference_frame=None):
        gate_calls.append((interface, reference_frame))
        return original_gate(interface, reference_frame)

    monkeypatch.setattr(m13, "require_authoritatively_consumable_interface", record_gate)

    pose = m13_local_pose(definition)

    assert gate_calls == [(definition, None)]
    assert (pose.x_mm, pose.y_mm, pose.z_mm) == (1.0, 2.0, 3.0)
