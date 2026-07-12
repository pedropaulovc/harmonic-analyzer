from __future__ import annotations

import asyncio

import pytest

from _assembly import (
    circular_component_pattern,
    ensure_global_pattern_axis,
    linear_component_pattern,
)


def test_global_pattern_axis_rejects_unknown_axis_before_com() -> None:
    with pytest.raises(ValueError, match="x, y, or z"):
        ensure_global_pattern_axis(None, "diagonal")


def test_linear_pattern_rejects_single_instance_before_com() -> None:
    with pytest.raises(ValueError, match="at least two"):
        asyncio.run(
            linear_component_pattern(
                None,
                "seed-1",
                axis="x",
                spacing_mm=10.0,
                instances=1,
            )
        )


def test_linear_pattern_rejects_nonpositive_spacing_before_com() -> None:
    with pytest.raises(ValueError, match="positive"):
        asyncio.run(
            linear_component_pattern(
                None,
                "seed-1",
                axis="x",
                spacing_mm=0.0,
                instances=2,
            )
        )


def test_circular_pattern_rejects_single_instance_before_com() -> None:
    with pytest.raises(ValueError, match="at least two"):
        asyncio.run(
            circular_component_pattern(
                None,
                "seed-1",
                axis_name="Axis1",
                instances=1,
            )
        )
