from __future__ import annotations

import math
from dataclasses import dataclass

from mechcad_harness.structural.tolerances import (
    RIGID_BODY_RANK_POLICY_ID,
    RIGID_BODY_RANK_TOLERANCE,
)

RIGID_BODY_MODES = ("Tx", "Ty", "Tz", "Rx", "Ry", "Rz")


@dataclass
class ConstraintPreflightResult:
    rigid_body_rank: int
    adequate: bool
    constrained_node_count: int
    policy_id: str
    tolerance: float


class ConstraintPreflight:
    policy_id = RIGID_BODY_RANK_POLICY_ID

    def __init__(self, tolerance: float = RIGID_BODY_RANK_TOLERANCE):
        self._tolerance = tolerance

    def evaluate(
        self,
        nodes: dict[int, tuple[float, float, float]],
        fixed_node_sets: dict[str, tuple[int, ...]],
        constrained_dofs: tuple[int, int, int] = (1, 2, 3),
    ) -> ConstraintPreflightResult:
        constrained: list[tuple[float, float, float, int]] = []
        for nset in fixed_node_sets.values():
            for nid in nset:
                coord = nodes.get(nid)
                if coord is None:
                    continue
                for dof in constrained_dofs:
                    constrained.append((coord[0], coord[1], coord[2], dof))
        # 6x6 Gram matrix of the rigid-body mode action on constrained DOFs.
        gram = [[0.0] * 6 for _ in range(6)]
        for (x, y, z, dof) in constrained:
            vals = self._mode_values(x, y, z)
            for i in range(6):
                for j in range(6):
                    gram[i][j] += vals[i][dof - 1] * vals[j][dof - 1]
        rank = self._symmetric_rank(gram, self._tolerance)
        return ConstraintPreflightResult(
            rigid_body_rank=rank,
            adequate=rank == 6,
            constrained_node_count=len({c[3] for c in []}) + len(fixed_node_sets),
            policy_id=self.policy_id,
            tolerance=self._tolerance,
        )

    @staticmethod
    def _mode_values(x: float, y: float, z: float) -> tuple[tuple[float, float, float], ...]:
        # (Tx, Ty, Tz, Rx, Ry, Rz) displacement vectors at node (x,y,z), origin reference.
        return (
            (1.0, 0.0, 0.0),   # Tx
            (0.0, 1.0, 0.0),   # Ty
            (0.0, 0.0, 1.0),   # Tz
            (0.0, -z, y),      # Rx
            (z, 0.0, -x),      # Ry
            (-y, x, 0.0),      # Rz
        )

    @staticmethod
    def _symmetric_rank(matrix: list[list[float]], tol: float) -> int:
        n = len(matrix)
        a = [row[:] for row in matrix]
        rank = 0
        for col in range(n):
            pivot = -1
            for row in range(rank, n):
                if abs(a[row][col]) > tol:
                    pivot = row
                    break
            if pivot == -1:
                continue
            a[rank], a[pivot] = a[pivot], a[rank]
            inv = 1.0 / a[rank][col]
            for j in range(col, n):
                a[rank][j] *= inv
            for row in range(n):
                if row != rank:
                    factor = a[row][col]
                    if factor != 0.0:
                        for j in range(col, n):
                            a[row][j] -= factor * a[rank][j]
            rank += 1
        return rank
