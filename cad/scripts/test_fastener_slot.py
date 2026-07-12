from __future__ import annotations

import math

import pytest

from _fastener_slot import slot_strip_area


def test_slot_strip_area_matches_semicircle_limit() -> None:
    radius = 4.0
    assert slot_strip_area(radius, 2.0 * radius * (1.0 - 1e-9)) == pytest.approx(
        math.pi * radius**2,
        rel=1e-8,
    )


@pytest.mark.parametrize("width", [0.0, -1.0, 8.0, 9.0])
def test_slot_strip_area_rejects_invalid_width(width: float) -> None:
    with pytest.raises(ValueError):
        slot_strip_area(4.0, width)
