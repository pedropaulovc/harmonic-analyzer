"""Offline contracts for the pen-hanger drawing."""

from __future__ import annotations


import math

import pytest

import build_pen_hanger as part


def test_hanger_screw_moves_without_moving_the_pen_or_bar() -> None:
    import build_magnifier_assembly as magnifier
    import build_pen_assembly as pen
    import build_wheel_bar as bar

    assert (
        magnifier.WHEEL_BAR_X0 - bar.BAR_LENGTH / 2.0,
        magnifier.WHEEL_BAR_X0 + bar.BAR_LENGTH / 2.0,
    ) == pytest.approx((-8.0, 226.0))
    assert pen.HANGER_POS == pytest.approx((3.0, 505.0, -157.0))
    assert pen.PEN_ROD_POS == pytest.approx((3.0, 368.0, -159.5))
    tap_axis = (
        pen.HANGER_POS[0] + part.SCREW_HOLE_XY[0],
        pen.HANGER_POS[1] + part.SCREW_HOLE_XY[1],
    )
    bar_axis = (
        magnifier.WHEEL_BAR_X0 + bar.SCREW_HOLE_X,
        magnifier.WHEEL_BAR_Y,
    )
    assert tap_axis == pytest.approx((-3.0, 575.7))
    assert tap_axis == pytest.approx(bar_axis)
    assert pen.HANGER_SCREW_POS == pytest.approx((*tap_axis, -129.9))

    # Receiver thickness and the rear-entry stock-screw stack are unchanged.
    assert part.STRAP_Z[1] - part.STRAP_Z[0] == pytest.approx(3.0)
    assert pen.HANGER_THREAD_PROTRUSION == pytest.approx(0.7)
    assert pen.HANGER_TIP_TO_RIM == pytest.approx(0.3)


def test_hanger_thread_envelope_fits_all_four_tapered_land_edges() -> None:
    point = part.SCREW_HOLE_XY
    vertices = (
        (part.STRAP_BOT_X[0], part.BLOCK_HALF),
        (part.STRAP_BOT_X[1], part.BLOCK_HALF),
        (part.STRAP_TOP_X[1], part.STRAP_TOP_Y),
        (part.STRAP_TOP_X[0], part.STRAP_TOP_Y),
    )
    # Signed point-to-edge distances in the CCW polygon measure the complete
    # circular thread envelope, including the top edge and inclined sides.
    walls = []
    for start, end in zip(vertices, vertices[1:] + vertices[:1]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        distance = (
            dx * (point[1] - start[1]) - dy * (point[0] - start[0])
        ) / math.hypot(dx, dy)
        walls.append(distance - part.HANGER_SCREW_DIA / 2.0)
    assert min(walls) == pytest.approx(2.9172)
    assert min(walls) == pytest.approx(part.HANGER_THREAD_STRAP_WALL)
