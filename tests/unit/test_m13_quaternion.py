import math
import sys

import pytest

from mechcad_harness.models.quaternion import (
    normalize_direction,
    normalize_quaternion,
    quaternion_compose,
    quaternion_multiply_raw,
    rotate_vector,
)


IDENTITY = (1.0, 0.0, 0.0, 0.0)
X_180 = (0.0, 1.0, 0.0, 0.0)
Y_180 = (0.0, 0.0, 1.0, 0.0)
Z_180 = (0.0, 0.0, 0.0, 1.0)


def test_q_and_minus_q_hash_identically_after_normalization():
    q = (0.5, 0.5, 0.5, 0.5)
    assert normalize_quaternion(q) == normalize_quaternion(tuple(-c for c in q))


def test_identity_and_180_degree_rotations():
    assert normalize_quaternion(IDENTITY) == IDENTITY
    assert rotate_vector((1.0, 0.0, 0.0), X_180) == pytest.approx((1.0, 0.0, 0.0))
    assert rotate_vector((1.0, 0.0, 0.0), Y_180) == pytest.approx((-1.0, 0.0, 0.0))
    assert rotate_vector((1.0, 0.0, 0.0), Z_180) == pytest.approx((-1.0, 0.0, 0.0))
    assert rotate_vector((0.0, 1.0, 0.0), X_180) == pytest.approx((0.0, -1.0, 0.0))


def test_nearly_zero_components_survive():
    small = normalize_quaternion((1e-13, 1.0, 0.0, 0.0))
    assert small[0] >= 0.0 and abs(math.sqrt(sum(c * c for c in small)) - 1.0) < 1e-12
    tiny_vector = normalize_quaternion((1.0, 1e-13, 0.0, 0.0))
    assert tiny_vector[0] == pytest.approx(1.0)


def test_normalization_handles_finite_extreme_components_without_overflow():
    normalized = normalize_quaternion((sys.float_info.max,) * 4)

    assert all(math.isfinite(component) for component in normalized)
    assert math.sqrt(sum(component * component for component in normalized)) == pytest.approx(1.0)


def test_direction_normalization_handles_finite_extreme_components_without_overflow():
    normalized = normalize_direction((sys.float_info.max,) * 3)

    assert all(math.isfinite(component) for component in normalized)
    assert math.sqrt(sum(component * component for component in normalized)) == pytest.approx(1.0)


def test_invalid_quaternions_rejected():
    with pytest.raises(ValueError):
        normalize_quaternion((0.0, 0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        normalize_quaternion((float("nan"), 0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        normalize_quaternion((1e-13, 1e-13, 1e-13, 1e-13))


def test_raw_hamilton_product_is_not_normalized():
    assert quaternion_multiply_raw((2.0, 0.0, 0.0, 0.0), IDENTITY) == (2.0, 0.0, 0.0, 0.0)


def test_composition_matches_kinematic_sweep_convention():
    q = normalize_quaternion((math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4)))
    composed = quaternion_compose(q, q)
    assert composed == pytest.approx(Z_180)
    assert rotate_vector((1.0, 0.0, 0.0), composed) == pytest.approx((-1.0, 0.0, 0.0))


def test_composition_operand_order_is_non_commutative():
    x_quarter_turn = normalize_quaternion((math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0))
    y_quarter_turn = normalize_quaternion((math.sqrt(0.5), 0.0, math.sqrt(0.5), 0.0))

    x_then_y = quaternion_compose(y_quarter_turn, x_quarter_turn)
    y_then_x = quaternion_compose(x_quarter_turn, y_quarter_turn)

    assert x_then_y != pytest.approx(y_then_x)
    assert rotate_vector((0.0, 0.0, 1.0), x_then_y) == pytest.approx((0.0, -1.0, 0.0))
    assert rotate_vector((0.0, 0.0, 1.0), y_then_x) == pytest.approx((1.0, 0.0, 0.0))


def test_rotation_preserves_raw_vector_magnitude():
    vector = (2.0, 3.0, 4.0)

    rotated = rotate_vector(vector, X_180)

    assert rotated == pytest.approx((2.0, -3.0, -4.0))
