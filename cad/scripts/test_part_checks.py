"""``_part_checks.volume_check`` fails closed on a non-finite volume (issue
#2013). SolidWorks-free."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from _part_checks import volume_check


def _adapter(volume: float) -> SimpleNamespace:
    result = SimpleNamespace(
        is_success=True, error=None, data=SimpleNamespace(volume=volume)
    )
    return SimpleNamespace(get_mass_properties=lambda: result)


def test_a_volume_inside_the_band_passes_and_is_returned():
    assert volume_check(_adapter(1000.4), "block", 1000.0, 0.5) == 1000.4


def test_a_volume_outside_the_band_fails():
    with pytest.raises(RuntimeError, match="block: volume 1001.0 mm"):
        volume_check(_adapter(1001.0), "block", 1000.0, 0.5)


@pytest.mark.parametrize("volume", [math.nan, math.inf, -math.inf])
def test_a_non_finite_volume_fails(volume):
    with pytest.raises(RuntimeError, match="block: volume"):
        volume_check(_adapter(volume), "block", 1000.0, 0.5)


@pytest.mark.parametrize("expected", [math.nan, math.inf])
def test_a_non_finite_expectation_fails(expected):
    # A builder chaining a NaN read into its next expectation stops there.
    with pytest.raises(RuntimeError, match="block: volume 1000.0 mm"):
        volume_check(_adapter(1000.0), "block", expected, 0.5)
