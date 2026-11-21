"""``define_centered_rectangle`` fails at the sketch when the native centre
rectangle snaps (issue #1323). SolidWorks-free."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _sketch_rectangle
from _sketch_rectangle import define_centered_rectangle


def _point(x_mm: float, y_mm: float) -> SimpleNamespace:
    return SimpleNamespace(X=x_mm / 1000.0, Y=y_mm / 1000.0)


class _Segment:
    def __init__(self, start, end, *, construction: bool = False) -> None:
        self.ConstructionGeometry = construction
        self._start = _point(*start)
        self._end = _point(*end)

    def GetStartPoint2(self):
        return self._start

    def GetEndPoint2(self):
        return self._end


def _adapter(corners: list[tuple[float, float]]) -> SimpleNamespace:
    """A sketch whose CreateCenterRectangle answers edges through ``corners``
    (bottom-left, bottom-right, top-right, top-left) plus both diagonals."""
    bl, br, tr, tl = corners
    segments = [
        _Segment(bl, br),
        _Segment(br, tr),
        _Segment(tr, tl),
        _Segment(tl, bl),
        _Segment(bl, tr, construction=True),
        _Segment(br, tl, construction=True),
    ]
    registered: list[object] = []

    def register(_kind, segment):
        registered.append(segment)
        return f"Line{len(registered)}"

    return SimpleNamespace(
        currentSketchManager=SimpleNamespace(
            AddToDB=False, CreateCenterRectangle=lambda *_args: segments
        ),
        _register_sketch_entity=register,
        check_sketch_fully_defined=lambda: SimpleNamespace(
            is_success=True, data={"definition_state": "fully_defined"}
        ),
    )


@pytest.fixture
def dimensions(monkeypatch) -> list[tuple]:
    placed: list[tuple] = []
    monkeypatch.setattr(
        _sketch_rectangle,
        "dimension_between",
        lambda _adapter, start, end, kind, value, label: placed.append(
            (kind, value, label)
        ),
    )
    return placed


def test_an_unsnapped_rectangle_is_dimensioned_at_its_requested_size(dimensions):
    adapter = _adapter([(-10.0, -5.0), (10.0, -5.0), (10.0, 5.0), (-10.0, 5.0)])
    define_centered_rectangle(adapter, 10.0, 5.0, "rib")
    assert [(kind, round(value, 9)) for kind, value, _ in dimensions] == [
        ("horizontal_distance", 20.0),
        ("vertical_distance", 10.0),
    ]


def test_a_snapped_corner_fails_at_the_sketch_naming_the_snap(dimensions):
    # #1310: the rib's end snapped 1 mm onto a deck edge; the rectangle came
    # back another size and its dimension turned driven two features later.
    adapter = _adapter([(-10.0, -4.0), (10.0, -4.0), (10.0, 5.0), (-10.0, 5.0)])
    with pytest.raises(
        RuntimeError, match=r"rib: native center rectangle snapped: .*1\.000000 mm"
    ):
        define_centered_rectangle(adapter, 10.0, 5.0, "rib")
    assert dimensions == []


def test_a_rectangle_shifted_off_the_origin_fails(dimensions):
    adapter = _adapter([(-9.0, -5.0), (11.0, -5.0), (11.0, 5.0), (-9.0, 5.0)])
    with pytest.raises(RuntimeError, match="snapped"):
        define_centered_rectangle(adapter, 10.0, 5.0, "rib")
    assert dimensions == []
