"""Offline contracts for the tube-frame manufacturing drawing."""

from __future__ import annotations

import math

import fr_tube_frame_spec
from fr_frame_attachment_spec import (
    BASE_SCREW_Y,
    COLUMN_BOTTOM_Y,
    COLUMN_SOCKET_DIAMETER,
    TOP_SCREW_Y,
    TUBE_CUT_LENGTH,
    TUBE_TOP_Y,
)
from fr_vn_tube_frame_cap_spec import INNER_CORNER_R, INNER_DIAMETER, MOUTH_INNER_DIAMETER


def test_open_tube_and_cross_holes_share_the_installed_frame_stations() -> None:
    assert fr_tube_frame_spec.OUTER_DIA == 25.4
    assert math.isclose(fr_tube_frame_spec.INNER_DIA, 19.304, abs_tol=1e-9)
    assert fr_tube_frame_spec.COLUMN_LENGTH == TUBE_CUT_LENGTH
    assert math.isclose(
        COLUMN_BOTTOM_Y + fr_tube_frame_spec.COLUMN_LENGTH,
        TUBE_TOP_Y,
        abs_tol=1e-9,
    )
    assert math.isclose(
        COLUMN_BOTTOM_Y + fr_tube_frame_spec.LOWER_CROSS_HOLE_Y,
        BASE_SCREW_Y,
        abs_tol=1e-9,
    )
    assert math.isclose(
        COLUMN_BOTTOM_Y + fr_tube_frame_spec.UPPER_CROSS_HOLE_Y,
        TOP_SCREW_Y,
        abs_tol=1e-9,
    )
    assert fr_tube_frame_spec.CROSS_HOLE_DIAMETER > 4.826
    assert fr_tube_frame_spec.OUTER_DIA < COLUMN_SOCKET_DIAMETER
    assert fr_tube_frame_spec.OUTER_DIA == INNER_DIAMETER
    assert fr_tube_frame_spec.OUTER_DIA < MOUTH_INNER_DIAMETER
    assert fr_tube_frame_spec.TOP_END_CHAMFER > INNER_CORNER_R


def test_length_is_flagged_cut_to_fit_from_a_longer_supply() -> None:
    assert fr_tube_frame_spec.SUPPLY_LENGTH_MIN == 1030.0
    assert fr_tube_frame_spec.SUPPLY_LENGTH_MIN > fr_tube_frame_spec.COLUMN_LENGTH
    assert fr_tube_frame_spec.LENGTH_SUPPLY_CALLOUT == "SUPPLY 1030 MIN"
    assert "CUT TO FIT AT ASSEMBLY" in fr_tube_frame_spec.LENGTH_FIT_CALLOUT


def test_cross_hole_callout_names_each_station_mate_on_single_line_lanes() -> None:
    callout = fr_tube_frame_spec.CROSS_HOLE_CALLOUT
    mates = fr_tube_frame_spec.CROSS_HOLE_MATES_SUFFIX
    assert "MATCH-DRILL" in callout
    assert "UPPER WITH MHA-FR-02" in mates
    assert "LOWER WITH MHA-FR-01" in mates
    assert "\n" not in callout + mates
