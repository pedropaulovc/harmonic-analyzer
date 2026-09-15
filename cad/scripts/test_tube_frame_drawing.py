"""Offline contracts for the tube-frame manufacturing drawing."""

from __future__ import annotations

import math

import tube_frame_spec
from frame_attachment_spec import (
    BASE_SCREW_Y,
    COLUMN_BOTTOM_Y,
    COLUMN_SOCKET_DIAMETER,
    TOP_SCREW_Y,
    TUBE_CUT_LENGTH,
    TUBE_TOP_Y,
)
from tube_frame_cap_spec import INNER_CORNER_R, INNER_DIAMETER, MOUTH_INNER_DIAMETER


def test_open_tube_and_cross_holes_share_the_installed_frame_stations() -> None:
    assert tube_frame_spec.OUTER_DIA == 25.4
    assert math.isclose(tube_frame_spec.INNER_DIA, 19.304, abs_tol=1e-9)
    assert tube_frame_spec.COLUMN_LENGTH == TUBE_CUT_LENGTH
    assert math.isclose(
        COLUMN_BOTTOM_Y + tube_frame_spec.COLUMN_LENGTH,
        TUBE_TOP_Y,
        abs_tol=1e-9,
    )
    assert math.isclose(
        COLUMN_BOTTOM_Y + tube_frame_spec.LOWER_CROSS_HOLE_Y,
        BASE_SCREW_Y,
        abs_tol=1e-9,
    )
    assert math.isclose(
        COLUMN_BOTTOM_Y + tube_frame_spec.UPPER_CROSS_HOLE_Y,
        TOP_SCREW_Y,
        abs_tol=1e-9,
    )
    assert tube_frame_spec.CROSS_HOLE_DIAMETER > 4.826
    assert tube_frame_spec.OUTER_DIA < COLUMN_SOCKET_DIAMETER
    assert tube_frame_spec.OUTER_DIA == INNER_DIAMETER
    assert tube_frame_spec.OUTER_DIA < MOUTH_INNER_DIAMETER
    assert tube_frame_spec.TOP_END_CHAMFER > INNER_CORNER_R
