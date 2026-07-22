"""Offline contracts for shared gear feature construction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from _gear import pattern_about_z


class _Result:
    def __init__(self, data: object) -> None:
        self.is_success = True
        self.data = data
        self.error = None


class _Adapter:
    def __init__(self) -> None:
        self.pattern_params = None

    async def create_axis(self, _params: object) -> _Result:
        return _Result(SimpleNamespace(name="Axis17"))

    async def circular_pattern_feature(self, params: object) -> _Result:
        self.pattern_params = params
        return _Result(SimpleNamespace(name="CirPattern1"))


@pytest.mark.asyncio
async def test_pattern_selects_created_reference_axis_by_name() -> None:
    adapter = _Adapter()

    pattern = await pattern_about_z(adapter, "Cut-Extrude1", 120, 31.1, 1.5)

    assert pattern.name == "CirPattern1"
    assert adapter.pattern_params.axis_name == "Axis17"
    assert adapter.pattern_params.axis_point == []
    assert adapter.pattern_params.features == ["Cut-Extrude1"]
    assert adapter.pattern_params.count == 120
    assert adapter.pattern_params.geometry_pattern is True
