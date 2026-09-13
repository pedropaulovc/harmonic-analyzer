"""Regressions for native Hole Wizard placement-face selection."""

from __future__ import annotations

from dataclasses import dataclass

import _holes


@dataclass
class _Face:
    name: str
    plane_z_mm: float
    area_m2: float
    x_bounds_mm: tuple[float, float] = (190.0, 204.0)
    y_bounds_mm: tuple[float, float] = (0.0, 50.0)

    @property
    def Normal(self) -> tuple[float, float, float]:
        return (0.0, 0.0, -1.0)

    def GetBox(self) -> tuple[float, float, float, float, float, float]:
        return (
            self.x_bounds_mm[0] / 1000.0,
            self.y_bounds_mm[0] / 1000.0,
            self.plane_z_mm / 1000.0,
            self.x_bounds_mm[1] / 1000.0,
            self.y_bounds_mm[1] / 1000.0,
            self.plane_z_mm / 1000.0,
        )

    def GetArea(self) -> float:
        return self.area_m2


class _Body:
    def __init__(self, faces: list[_Face]) -> None:
        self._faces = faces

    def GetFaces(self) -> list[_Face]:
        return self._faces


class _Part:
    def __init__(self, faces: list[_Face]) -> None:
        self._body = _Body(faces)

    def GetBodies2(self, _kind: int, _visible_only: bool) -> list[_Body]:
        return [self._body]


def test_exact_spotface_floor_outranks_larger_offset_face(monkeypatch) -> None:
    monkeypatch.setattr(_holes, "_early_bound", lambda value, _interface: value)
    outer = _Face("outer", plane_z_mm=-133.35, area_m2=1.0)
    floor = _Face("spotface floor", plane_z_mm=-133.0, area_m2=0.00006)

    selected = _holes.find_planar_face(
        _Part([outer, floor]),
        (0.0, 0.0, -1.0),
        [[197.0, 38.1, -133.0]],
    )

    assert selected is floor


def test_equal_plane_ambiguity_prefers_largest_spanning_face(monkeypatch) -> None:
    monkeypatch.setattr(_holes, "_early_bound", lambda value, _interface: value)
    small = _Face("small", plane_z_mm=-133.0, area_m2=0.00006)
    large = _Face("large", plane_z_mm=-133.0, area_m2=1.0)

    selected = _holes.find_planar_face(
        _Part([small, large]),
        (0.0, 0.0, -1.0),
        [[197.0, 38.1, -133.0]],
    )

    assert selected is large


def test_disjoint_exact_floors_outrank_one_offset_face_spanning_both(
    monkeypatch,
) -> None:
    monkeypatch.setattr(_holes, "_early_bound", lambda value, _interface: value)
    outer = _Face(
        "outer spanning both",
        plane_z_mm=-133.35,
        area_m2=1.0,
        x_bounds_mm=(-220.0, 220.0),
    )
    left_floor = _Face(
        "left spotface floor",
        plane_z_mm=-133.0,
        area_m2=0.00006,
        x_bounds_mm=(-202.0, -192.0),
    )
    right_floor = _Face(
        "right spotface floor",
        plane_z_mm=-133.0,
        area_m2=0.00006,
        x_bounds_mm=(192.0, 202.0),
    )

    selected = _holes.find_planar_face(
        _Part([outer, left_floor, right_floor]),
        (0.0, 0.0, -1.0),
        [[-197.0, 38.1, -133.0], [197.0, 38.1, -133.0]],
    )

    assert selected is left_floor
