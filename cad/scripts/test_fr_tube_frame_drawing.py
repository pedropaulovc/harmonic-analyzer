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
    # The cut length sits on the .001 in grid. The upper station follows
    # MHA-FR-02's taps (40.07527 installed, off the .001 grid); it is
    # match-drilled with that frame, so the sheet prints no station.
    length = fr_tube_frame_spec.COLUMN_LENGTH
    assert math.isclose(length / 25.4, round(length / 25.4, 3), abs_tol=1e-9)
    upper_in = fr_tube_frame_spec.UPPER_CROSS_HOLE_Y / 25.4
    assert math.isclose(upper_in, 39.07527, abs_tol=1e-5)
    assert math.isclose(fr_tube_frame_spec.LOWER_CROSS_HOLE_Y / 25.4, 0.50, abs_tol=1e-9)
    assert fr_tube_frame_spec.OUTER_DIA < COLUMN_SOCKET_DIAMETER
    assert fr_tube_frame_spec.OUTER_DIA == INNER_DIAMETER
    assert fr_tube_frame_spec.OUTER_DIA < MOUTH_INNER_DIAMETER
    assert fr_tube_frame_spec.TOP_END_CHAMFER > INNER_CORNER_R


def test_length_is_flagged_cut_to_fit_from_a_longer_supply() -> None:
    supply = fr_tube_frame_spec.SUPPLY_LENGTH_MIN
    cut = fr_tube_frame_spec.COLUMN_LENGTH
    assert supply >= cut + fr_tube_frame_spec.SUPPLY_LENGTH_ALLOWANCE
    # The supply is the next .01 in above the cut plus its allowance.
    assert supply - 0.254 < cut + fr_tube_frame_spec.SUPPLY_LENGTH_ALLOWANCE
    assert math.isclose(supply, 40.51 * 25.4, abs_tol=1e-9)
    assert "CUT TO FIT" in fr_tube_frame_spec.LENGTH_FIT_CALLOUT
    for mate in ("MHA-FR-01", "MHA-FR-02", "MHA-FR-VN-54"):
        assert mate in fr_tube_frame_spec.LENGTH_FIT_CALLOUT


def test_cross_hole_callout_names_each_station_mate_on_single_line_lanes() -> None:
    callout = fr_tube_frame_spec.CROSS_HOLE_CALLOUT
    mates = fr_tube_frame_spec.CROSS_HOLE_MATES_SUFFIX
    assert "MATCH-DRILL" in callout
    stations = dict(
        clause.strip().split(" WITH ") for clause in mates.split(",")
    )
    assert stations == {"UPPER": "MHA-FR-02", "LOWER": "MHA-FR-01"}
    assert "\n" not in callout + mates
