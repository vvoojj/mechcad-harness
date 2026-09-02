from __future__ import annotations

import math
from typing import Sequence


QUATERNION_NORM_TOLERANCE = 1e-12

Quaternion = tuple[float, float, float, float]


def normalize_direction(vector: Sequence[float]) -> tuple[float, float, float]:
    v = tuple(float(value) for value in vector)
    if len(v) != 3 or any(not math.isfinite(value) for value in v):
        raise ValueError("direction components must be finite")
    scale = max(abs(value) for value in v)
    if scale == 0.0:
        raise ValueError("direction must be non-zero")
    scaled = tuple(value / scale for value in v)
    scaled_norm = math.sqrt(sum(value * value for value in scaled))
    if scale <= QUATERNION_NORM_TOLERANCE / scaled_norm:
        raise ValueError("direction must be non-zero")
    return tuple(value / scaled_norm for value in scaled)


def normalize_quaternion(quaternion: Sequence[float]) -> Quaternion:
    q = tuple(float(value) for value in quaternion)
    if len(q) != 4 or any(not math.isfinite(value) for value in q):
        raise ValueError("quaternion components must be finite (w, x, y, z)")
    scale = max(abs(value) for value in q)
    if scale == 0.0:
        raise ValueError("quaternion must have non-zero norm")
    scaled = tuple(value / scale for value in q)
    scaled_norm = math.sqrt(sum(value * value for value in scaled))
    if scale <= QUATERNION_NORM_TOLERANCE / scaled_norm:
        raise ValueError("quaternion must have non-zero norm")
    normalized = tuple(value / scaled_norm for value in scaled)
    first_nonzero = next(
        (value for value in normalized if abs(value) > QUATERNION_NORM_TOLERANCE), 1.0
    )
    return tuple(-value for value in normalized) if first_nonzero < 0 else normalized


def quaternion_multiply_raw(
    first: Sequence[float], second: Sequence[float]
) -> Quaternion:
    aw, ax, ay, az = first
    bw, bx, by, bz = second
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def quaternion_compose(first: Sequence[float], second: Sequence[float]) -> Quaternion:
    return normalize_quaternion(quaternion_multiply_raw(first, second))


def rotate_vector(
    vector: Sequence[float], quaternion: Sequence[float]
) -> tuple[float, float, float]:
    orientation = normalize_quaternion(quaternion)
    pure = (0.0, *vector)
    conjugate = (orientation[0], -orientation[1], -orientation[2], -orientation[3])
    # Pure vectors are not rotations, so both products must remain raw.
    return quaternion_multiply_raw(
        quaternion_multiply_raw(orientation, pure), conjugate
    )[1:]
