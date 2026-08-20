import math

import pytest
from pydantic import ValidationError

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
    instance_object_name,
)
from mechcad_harness.cad_program import acceptance_program


def assembly(instances):
    return CadAssemblyProgram(assembly_id="asm", parts=(acceptance_program(),), instances=tuple(instances))


def test_identity_and_quaternion_signs_are_canonicalized():
    first = CadRigidTransform(rotation_quaternion=(1, 0, 0, 0))
    negative = CadRigidTransform(rotation_quaternion=(-1, 0, 0, 0))
    assert first == negative
    assert first.rotation_quaternion == (1.0, 0.0, 0.0, 0.0)


def test_acceptance_transforms_and_instance_order_normalization():
    a = CadComponentInstance(instance_id="bracket_A", part_id="M7A2ABracket")
    b = CadComponentInstance(instance_id="bracket_B", part_id="M7A2ABracket", placement=CadRigidTransform(x_mm=160, rotation_quaternion=(math.sqrt(0.5), 0, 0, math.sqrt(0.5))))
    first = assembly((a, b))
    reversed_program = assembly((b, a))
    assert first.canonical_instances[0].instance_id == "bracket_A"
    assert assembly_hash(first) == assembly_hash(reversed_program)
    assert first.instances[0].part_id == first.instances[1].part_id


def test_registry_and_instance_validation():
    with pytest.raises(ValidationError):
        CadAssemblyProgram(assembly_id="asm", parts=(acceptance_program(), acceptance_program()), instances=())
    with pytest.raises(ValidationError):
        CadAssemblyProgram(assembly_id="asm", parts=(acceptance_program(),), instances=(CadComponentInstance(instance_id="x", part_id="missing"),))
    with pytest.raises(ValidationError):
        assembly((CadComponentInstance(instance_id="x", part_id="M7A2ABracket"), CadComponentInstance(instance_id="x", part_id="M7A2ABracket")))


def test_invalid_quaternions_are_rejected():
    with pytest.raises(ValidationError):
        CadRigidTransform(rotation_quaternion=(0, 0, 0, 0))
    with pytest.raises(ValidationError):
        CadRigidTransform(rotation_quaternion=(math.nan, 0, 0, 0))


def test_instance_names_are_injective_and_bounded():
    names = {instance_object_name(value) for value in ("motor-1", "motor.1", "motor_1", "a", "A")}
    assert len(names) == 5
    with pytest.raises(ValueError):
        instance_object_name("a" * 241)


def test_assembly_hash_changes_with_physical_placement():
    identity = assembly((CadComponentInstance(instance_id="a", part_id="M7A2ABracket"),))
    translated = assembly((CadComponentInstance(instance_id="a", part_id="M7A2ABracket", placement=CadRigidTransform(x_mm=1)),))
    assert assembly_hash(identity) != assembly_hash(translated)
