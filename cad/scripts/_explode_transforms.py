"""Rigid presentation transforms, in SolidWorks' row-vector convention.

Explode steps act in assembly space, after the collapsed component placement.
Units belong to the caller (native readers use metres, sheet plans use mm).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


@dataclass(frozen=True)
class RigidTransform:
    """Nine rotation-row entries followed by three translation entries."""

    values: tuple[float, ...] = (
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    )

    @classmethod
    def from_sw(cls, values: Sequence[float], *, label: str) -> RigidTransform:
        """Refuse malformed, scaled, reflected or non-rigid native step data."""
        data = tuple(float(value) for value in values)
        if len(data) != 16 or not all(math.isfinite(value) for value in data):
            raise RuntimeError(f"{label}: invalid 16-value explode transform {data!r}")
        rows = [data[index : index + 3] for index in (0, 3, 6)]
        determinant = sum(
            rows[0][i]
            * (
                rows[1][(i + 1) % 3] * rows[2][(i + 2) % 3]
                - rows[1][(i + 2) % 3] * rows[2][(i + 1) % 3]
            )
            for i in range(3)
        )
        if (
            abs(data[12] - 1.0) > 1e-9
            or abs(determinant - 1.0) > 1e-9
            or any(
                abs(sum(a * b for a, b in zip(rows[i], rows[j])) - (i == j)) > 1e-9
                for i in range(3)
                for j in range(3)
            )
        ):
            raise RuntimeError(f"{label}: explode transform is not rigid: {data!r}")
        return cls(data[:12])

    @classmethod
    def translation(cls, vector: Sequence[float]) -> RigidTransform:
        return cls((*IDENTITY.values[:9], *vector))

    @classmethod
    def rotation(
        cls, axis: Sequence[float], angle: float, pivot: Sequence[float]
    ) -> RigidTransform:
        """Right-hand rotation by radians about a world-space axis through pivot."""
        if not math.isclose(math.hypot(*axis), 1.0, abs_tol=1e-12):
            raise ValueError(f"rotation axis is not unit: {axis!r}")
        x, y, z = axis
        c, s = math.cos(angle), math.sin(angle)
        t = 1.0 - c
        rows = (
            t * x * x + c,
            t * x * y + s * z,
            t * x * z - s * y,
            t * x * y - s * z,
            t * y * y + c,
            t * y * z + s * x,
            t * x * z + s * y,
            t * y * z - s * x,
            t * z * z + c,
        )
        rotated = cls((*rows, 0.0, 0.0, 0.0)).point(pivot)
        return cls((*rows, *(a - b for a, b in zip(pivot, rotated))))

    def point(self, point: Sequence[float]) -> tuple[float, float, float]:
        x, y, z = point
        v = self.values
        return (
            x * v[0] + y * v[3] + z * v[6] + v[9],
            x * v[1] + y * v[4] + z * v[7] + v[10],
            x * v[2] + y * v[5] + z * v[8] + v[11],
        )

    def then(self, following: RigidTransform) -> RigidTransform:
        """Compose chronologically: this move, THEN following (not commutative)."""
        a, b = self.values, following.values
        rows = tuple(
            sum(a[3 * i + k] * b[3 * k + j] for k in range(3))
            for i in range(3)
            for j in range(3)
        )
        return RigidTransform((*rows, *following.point(a[9:12])))


IDENTITY = RigidTransform()


@dataclass(frozen=True)
class ExplodeTransforms:
    """Ordered native operations, resolved against each drawing instance path.

    Lookup on demand preserves ancestor/child chronology without depending on
    a complete configuration-tree walk. Equal leaf names in different nested
    assemblies remain distinct. A step selecting both ancestor and child
    applies their common operation once.
    """

    steps: tuple[Mapping[str, RigidTransform], ...] = ()

    def for_component(self, path: str) -> RigidTransform:
        path = path.replace("\\", "/").casefold()
        result = IDENTITY
        for step in self.steps:
            matches = [
                transform
                for member, transform in step.items()
                if path == member or path.startswith(member + "/")
            ]
            if matches and any(transform != matches[0] for transform in matches[1:]):
                raise RuntimeError(
                    f"explode step gives {path!r} conflicting ancestor moves"
                )
            if matches:
                result = result.then(matches[0])
        return result
