"""Offline contracts for the pen hanger and its drawing."""

from __future__ import annotations

import inspect
import math
import re

import pytest

import draw_pn_pen_hanger as draw
import pn_pen_hanger_spec as spec
from _printed_tolerance import printed_band_mm


def test_hanger_tap_lands_on_the_bar_screw_axis() -> None:
    import build_mg_magnifier_assembly as magnifier
    import build_mg_wheel_bar as bar
    import build_pn_pen_assembly as pen

    assert pen.HANGER_POS == spec.HANGER_POS
    tap_axis = (
        spec.HANGER_POS[0] + spec.SCREW_HOLE_XY[0],
        spec.HANGER_POS[1] + spec.SCREW_HOLE_XY[1],
    )
    bar_axis = (
        magnifier.WHEEL_BAR_X0 + bar.SCREW_HOLE_X,
        magnifier.WHEEL_BAR_Y,
    )
    assert tap_axis == pytest.approx(bar_axis)
    # The strap seats on the bar front face, its top flush with the bar top.
    assert spec.HANGER_POS[2] + spec.STRAP_Z[1] == pytest.approx(magnifier.BAR_FRONT_Z)
    assert spec.HANGER_POS[1] == pytest.approx(
        magnifier.WHEEL_BAR_Y + bar.BAR_SIDE / 2.0
    )
    # Receiver thickness and the rear-entry stock-screw stack are unchanged.
    assert spec.STRAP_Z[1] - spec.STRAP_Z[0] == pytest.approx(3.0)
    assert pen.HANGER_THREAD_PROTRUSION == pytest.approx(0.7)


def test_hanger_thread_envelope_fits_all_four_tapered_strap_edges() -> None:
    point = spec.SCREW_HOLE_XY
    vertices = spec.STRAP_OUTLINE
    # Signed point-to-edge distances in the CCW outline measure the complete
    # circular thread envelope, including the top edge and inclined sides.
    walls = []
    for start, end in zip(vertices, vertices[1:] + vertices[:1]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        distance = (
            dx * (point[1] - start[1]) - dy * (point[0] - start[0])
        ) / math.hypot(dx, dy)
        walls.append(distance - spec.HANGER_SCREW_DIA / 2.0)
    # The top edge governs: 5.0 below it less the #8 major radius.
    assert min(walls) == pytest.approx(5.0 - spec.HANGER_SCREW_DIA / 2.0)
    assert min(walls) == pytest.approx(spec.HANGER_THREAD_STRAP_WALL)


def test_slots_centre_on_the_rod_line_with_a_running_fit() -> None:
    import paper_drive_geom as paper
    import pn_pen_rod_spec as rod

    # Local x 0 is the rod line; local z ROD_AXIS_Z is the rod axis.
    assert spec.HANGER_POS[0] == paper.PEN_ROD_X
    assert spec.HANGER_POS[2] + spec.ROD_AXIS_Z == pytest.approx(paper.PEN_Z_MID)
    rod_max = rod.ROD_SECTION + rod.SECTION_BAND[0]
    rod_min = rod.ROD_SECTION + rod.SECTION_BAND[1]
    narrow = spec.SLOT_WIDTH + spec.SLOT_WIDTH_BAND[1]
    wide = spec.SLOT_WIDTH + spec.SLOT_WIDTH_BAND[0]
    assert narrow - rod_max == pytest.approx(0.05)
    assert wide - rod_min == pytest.approx(0.15)
    # Worst lean between the two slots' outer faces stays under 0.25 deg.
    span = spec.GUIDE_PITCH + spec.GUIDE_PLATE_T
    assert math.degrees(math.atan((wide - rod_min) / span)) < 0.25
    # Slot bottom behind the largest rod's back face at its .X limit, and the
    # corner fillets' wall tangency still behind it with the radius at its .X
    # limit too (drawing-guidelines.md rule 16 corner radius, no tight band).
    back_face = spec.ROD_AXIS_Z + rod_max / 2.0
    slot_bottom_near = spec.SLOT_BOTTOM_Z - printed_band_mm(1)
    assert slot_bottom_near - back_face == pytest.approx(3.2)
    fillet_tangent = slot_bottom_near - (spec.SLOT_CORNER_R + printed_band_mm(1))
    assert fillet_tangent - back_face == pytest.approx(0.4)
    assert ("UpperGuideProfile", "SlotBottom") not in spec.DRAWING_BANDS
    assert spec.DRAWING_PRECISION["UpperGuideProfile"]["SlotBottom"] == 1
    # The arms reach past the rod's front face.
    assert spec.ROD_AXIS_Z - rod_max / 2.0 - spec.PLATE_FRONT_Z == pytest.approx(1.5)


def test_strap_foot_stays_above_the_platen() -> None:
    import paper_drive_geom as paper
    import pd_platen_spec as platen

    platen_top = paper.PLATEN_BOTTOM_Y + platen.PLATE_HEIGHT
    foot = spec.HANGER_POS[1] + spec.STRAP_BOT_Y
    assert foot == pytest.approx(spec.GUIDE_SPAN_Y[0])
    assert foot - platen_top >= 2.0


def test_both_guides_engage_the_rod_square_over_the_full_travel() -> None:
    import pn_pen_carriage_geom as carriage

    lower, upper = spec.GUIDE_SPAN_Y
    margin = spec.GUIDE_ENGAGE_MARGIN
    # At the lowest pen the square's top still clears the upper plate's top.
    assert min(carriage.ROD_SQUARE_TOP_Y) >= upper + margin
    # At the highest pen the square's bottom and every carriage rider stay
    # below the lower plate's bottom.
    assert max(carriage.ROD_SQUARE_BOTTOM_Y) <= lower - margin
    assert max(carriage.CARRIAGE_TOP_Y) <= lower - margin


def test_drawing_keeps_exactly_the_marked_dimensions() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(draw.FRONT_KEEP) | set(draw.SECTION_KEEP)
    assert not set(draw.FRONT_KEEP) & set(draw.SECTION_KEEP)
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    for feature, name in spec.DRAWING_BANDS:
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert name in spec.DIMENSION_CALLOUTS
    # The printed corner radius counts both corners and keeps its own "R".
    assert spec.DIMENSION_PREFIXES == {("UpperSlotCorner", "SlotCornerR"): "2X R"}
    for feature, name in spec.DIMENSION_PREFIXES:
        assert name in spec.DRAWING_DIMENSIONS[feature]


def test_front_view_looks_at_the_plates_and_keeps_the_taper_outside() -> None:
    # *Back: model +x prints left, so the strap's wide (-x) top corner is right.
    assert draw._fx(spec.STRAP_TOP_X[0]) > draw._fx(spec.STRAP_TOP_X[1])
    assert draw._fx(draw._X[0]) - draw._fx(draw._X[1]) == pytest.approx(0.021)
    # The taper's dimension sits under the view, beside the bottom width, so
    # its long extension line drops from the top outer corner outside the
    # strap instead of running down through it.
    bottom = draw._fy(spec.STRAP_BOT_Y)
    taper_x, taper_y = draw.FRONT_KEEP["StrapTaperDx"]
    assert taper_y < draw.FRONT_KEEP["StrapBotWidth"][1] < bottom
    assert draw._fx(spec.STRAP_BOT_X[0]) < taper_x < draw._fx(spec.STRAP_TOP_X[0])
    # The tap callout and its leader stay right of the strap; every dimension
    # stacked beside the strap is on its left.
    right_edge = draw._fx(draw._X[0])
    assert draw.CALLOUT_XY[0] > right_edge
    for name in ("ScrewY", "UpperPlateDrop", "StrapRise", "PlateThick"):
        assert draw.FRONT_KEEP[name][0] < draw._fx(draw._X[1]), name


def test_section_cuts_the_upper_plate_and_spans_its_silhouette() -> None:
    lower, upper = spec.GUIDE_PLATE_YS[1], spec.GUIDE_PLATE_YS[1] + spec.GUIDE_PLATE_T
    start, end = draw.SECTION_LINE_MODEL_MM
    assert start[1] == end[1] == draw.SECTION_Y
    assert lower < draw.SECTION_Y < upper
    strap = draw._strap_x_at(draw.SECTION_Y)
    assert end[0] < min(strap[0], -spec.GUIDE_PLATE_WIDTH / 2.0)
    assert start[0] > max(strap[1], spec.GUIDE_PLATE_WIDTH / 2.0)
    # Looking down: model +x left, the strap back face above the plate front.
    assert draw._ax(1.0) < draw._ax(0.0)
    assert draw._az(spec.STRAP_Z[1]) > draw._az(spec.PLATE_FRONT_Z)
    centre = (draw._ax(draw._SX), draw._az(draw._SZ))
    assert centre == pytest.approx(draw.SECTION_CENTER)
    # The width rows stack under the plate front: slot, arm, plate, each at
    # least 9 mm apart; the caption under the outermost.
    front = draw._az(spec.PLATE_FRONT_Z)
    rows = [
        draw.SECTION_ROW_Y[name] for name in ("SlotWidth", "ArmWidth", "PlateWidth")
    ]
    assert front > rows[0] > rows[1] > rows[2]
    assert min(a - b for a, b in zip(rows, rows[1:])) >= 0.009 - 1e-12
    assert draw.SECTION_CAPTION_XY[1] < rows[2]
    # The plate width's value stands centred between the plate's extension
    # lines; the arm's value outside the U on the left.
    plate_x = sorted((draw._ax(-draw._HALF_PLATE), draw._ax(draw._HALF_PLATE)))
    assert draw.SECTION_KEEP["PlateWidth"][0] == pytest.approx(sum(plate_x) / 2.0)
    assert draw.SECTION_KEEP["ArmWidth"][0] < plate_x[0]


def test_slot_width_text_is_parked_clear_of_every_extension_line() -> None:
    # Every vertical extension line of the width rows lies inside the plate,
    # and the section's rightmost ink is the strap end: the slot width's
    # ~49 mm text block starts right of both.
    rightmost_ink = draw._ax(draw._SECTION_X[0])
    left_end = draw.SLOT_WIDTH_TEXT_XY[0] - draw._SLOT_TEXT_HALF_WIDTH
    assert left_end > rightmost_ink > draw._ax(-draw._HALF_PLATE)
    # ... and ends left of the isometric's silhouette.
    assert draw.SLOT_WIDTH_TEXT_XY[0] + draw._SLOT_TEXT_HALF_WIDTH < 0.355
    source = inspect.getsource(draw.build)
    assert source.index("offset_dimension_text(") < source.index(
        "set_dimension_callouts("
    )


def test_upper_plate_location_callout_stays_off_lines() -> None:
    assert not re.search(r"\d", spec.UPPER_PLATE_LOCATION_CALLOUT)
    text_x, text_y = draw.UPPER_PLATE_NOTE_XY
    tip = (draw._fx(-draw._HALF_PLATE / 2.0), draw._fy(draw._UPPER_TOP_Y))
    taper_extension_x = draw._fx(spec.STRAP_TOP_X[0])
    assert text_x > taper_extension_x
    # The tip is on the plate's top edge inside the strap's silhouette.
    left, right = draw._strap_x_at(draw._UPPER_TOP_Y)
    assert draw._fx(right) < tip[0] < draw._fx(left)
    # The straight leader passes above the cutting line's right end.
    line_y = draw._fy(draw.SECTION_Y)
    line_end_x = draw._fx(draw.SECTION_LINE_MODEL_MM[1][0])
    lowest_start_y = text_y - 0.010  # the bottom of the two-line block
    t = (line_end_x - tip[0]) / (text_x - tip[0])
    assert tip[1] + t * (lowest_start_y - tip[1]) > line_y + 0.002
    # Above the general notes.
    assert lowest_start_y > draw.NOTES_XY[1]


def test_tap_callout_omits_the_title_block_thread_class() -> None:
    source = inspect.getsource(draw)
    assert (
        'omit_title_block_thread_class(tap_callout, label="hanger-screw through tap")'
        in source
    )


def test_notes_carry_no_dimensions() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert len([line for line in lines if not line.startswith(" ")]) <= 4
    for line in lines:
        assert not re.search(r"\d\.\d|\+/-|±", line), line
