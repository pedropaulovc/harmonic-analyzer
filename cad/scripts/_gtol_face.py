"""Stable, COM-free face geometry and selector protocol.

Concrete selectors stay in separate modules so each spec folds only its own types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

# swSurfaceTypes_e identities read via ISurface.Identity.
SURFACE_PLANE = 4001
SURFACE_CYLINDER = 4002
SURFACE_CONE = 4003
SURFACE_SPHERE = 4004
SURFACE_TORUS = 4005


@dataclass(frozen=True)
class FaceGeometry:
    face: Any
    identity: int
    parameters: tuple[float, ...]
    outward_normal: tuple[float, float, float] | None
    box: tuple[float, ...]


def unit_vector(vector: Sequence[float]) -> tuple[float, float, float]:
    x, y, z = (float(c) for c in vector)
    norm = (x * x + y * y + z * z) ** 0.5
    if norm == 0.0:
        raise ValueError("zero-length direction")
    return (x / norm, y / norm, z / norm)


class FaceSpec(Protocol):
    """A selector owns its identity filter and pure geometry-matching behavior."""

    @property
    def surface_identity(self) -> int: ...

    @property
    def tolerance_mm(self) -> float: ...

    def matches(self, geometry: FaceGeometry) -> bool: ...
