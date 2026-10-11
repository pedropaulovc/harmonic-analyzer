"""define_circle's size dimension: a diameter by default, a radius on request.

v37 arbor-pedestal: the crown's DIAMETER dimension, driven by
``"TopRadius" * 2``, was flipped radial on the sheet and the drawing's rebuild
drove a radius of 22 -- an R22 crown on an R11 part. A circle that prints as a
radius is dimensioned as one in the part, and its drive then means a radius.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _sketch
import _sketch_chains
import _sketch_circle


class _Adapter:
    def __init__(self) -> None:
        self.currentSketchManager = SimpleNamespace(AddToDB=False)
        self.dimensions: list[tuple[str, float]] = []

    async def add_circle(self, _x: float, _y: float, _radius: float):
        return SimpleNamespace(is_success=True, data="Circle1", error=None)

    async def add_sketch_dimension(self, entity, other, kind, value):
        assert (entity, other) == ("Circle1", None)
        self.dimensions.append((kind, value))
        return SimpleNamespace(is_success=True, data=None, error=None)


@pytest.fixture
def adapter(monkeypatch) -> _Adapter:
    async def anchored(*_args) -> None:
        return None

    monkeypatch.setattr(_sketch, "anchor_point_to_origin", anchored)
    monkeypatch.setattr(_sketch_chains, "anchor_point_to_origin", anchored)
    monkeypatch.setattr(_sketch_circle, "anchor_point_to_origin", anchored)
    return _Adapter()


def _define(adapter: _Adapter, **kwargs) -> _sketch.SketchDims:
    dims = _sketch.SketchDims()
    asyncio.run(
        _sketch_circle.define_circle(
            adapter,
            0.0,
            39.718,
            11.0,
            "crown",
            dims=dims,
            names=("CrownX", "CrownCy", "CrownSize"),
            drives=(None, '"BoreHeight"', '"CrownSize"'),
            **kwargs,
        )
    )
    return dims


def test_a_circle_is_dimensioned_by_its_diameter_by_default(adapter) -> None:
    dims = _define(adapter)
    assert adapter.dimensions == [("diameter", 22.0)]
    assert dims._rows == [("CrownCy", '"BoreHeight"'), ("CrownSize", '"CrownSize"')]


def test_a_radius_circle_carries_a_driving_radius(adapter) -> None:
    dims = _define(adapter, size_dimension="radius")
    assert adapter.dimensions == [("radial", 11.0)]
    # The size slot's name and drive now belong to the radius.
    assert dims._rows[-1] == ("CrownSize", '"CrownSize"')
