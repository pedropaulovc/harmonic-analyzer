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
    # MHA-FR-02's taps (40.075 installed, on the .001 grid with the snapped
    # top-frame plane); it is match-drilled with that frame, so the sheet
    # prints no station.
    length = fr_tube_frame_spec.COLUMN_LENGTH
    assert math.isclose(length / 25.4, round(length / 25.4, 3), abs_tol=1e-9)
    upper_in = fr_tube_frame_spec.UPPER_CROSS_HOLE_Y / 25.4
    assert math.isclose(upper_in, 39.075, abs_tol=1e-9)
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


def test_callouts_link_numbered_notes_and_view_a_has_room() -> None:
    import draw_fr_tube_frame as drawing

    assert drawing.BELOW_CALLOUTS["Length"] == f"SEE NOTE {drawing.LENGTH_FIT_NOTE_NUMBER}"
    assert drawing.OD_REFERENCE_SUFFIX.endswith(f"SEE NOTE {drawing.OD_FIT_NOTE_NUMBER}")
    for number in (drawing.OD_FIT_NOTE_NUMBER, drawing.LENGTH_FIT_NOTE_NUMBER):
        assert f"\n{number}. " in f"\n{drawing.NOTES}"
    assert "\n" not in drawing.CROSS_HOLE_SUFFIX + drawing.CROSS_HOLE_MATES
    # The arrow's letter stands under VIEW A's caption and over the tube top.
    text_xy, tip_xy = drawing.VIEW_A_ARROW
    caption_bottom = drawing.VIEW_A_CAPTION_XY[1] - 2 * 0.0045
    assert tip_xy[1] < text_xy[1] - drawing.VIEW_LETTER_HEIGHT
    assert text_xy[1] < caption_bottom or text_xy[0] > drawing.VIEW_A_CAPTION_XY[0] + 0.035
    end_view_right = drawing.END_CENTER[0] + drawing._END_VIEW_RADIUS + 0.005
    assert text_xy[0] > end_view_right
