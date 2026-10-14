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


def test_both_slot_walls_keep_the_floor_at_the_printed_worst_case() -> None:
    # drawing-guidelines.md rule 17: printed 12.0 plate, 3.5 near arm and
    # 5.05 +0.05/0 slot, all .X bands from the title block.
    band = printed_band_mm(1)
    assert spec.GUIDE_PLATE_WIDTH == 12.0
    assert round(spec.ARM_WIDTH, 1) == 3.5
    near = 3.5 - band
    far = (12.0 - band) - (3.5 + band) - (spec.SLOT_WIDTH + spec.SLOT_WIDTH_BAND[0])
    assert spec.NEAR_ARM_MIN == pytest.approx(near) == pytest.approx(2.7)
    assert spec.FAR_ARM_MIN == pytest.approx(far) == pytest.approx(1.8)
    assert min(near, far) >= spec.SLOT_WALL_FLOOR == 1.5
    # The slot stays centred on the rod line, the plate flush with both foot
    # corners (note 1).
    assert spec.STRAP_BOT_X == (
        -spec.GUIDE_PLATE_WIDTH / 2.0,
        spec.GUIDE_PLATE_WIDTH / 2.0,
    )


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
    assert draw._fx(draw._X[0]) - draw._fx(draw._X[1]) == pytest.approx(0.022)
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


def test_section_looks_down_onto_the_upper_plate_and_spans_its_silhouette() -> None:
    top = spec.GUIDE_PLATE_YS[1] + spec.GUIDE_PLATE_T
    start, end = draw.SECTION_LINE_MODEL_MM
    assert start[1] == end[1] == draw.SECTION_Y
    # Just above the plate: the 1:1 cutting line clears its top edge, and the
    # strap edge it cuts still reads the plate's overhang to the printed place.
    assert top + 0.5 <= draw.SECTION_Y < top + 1.0
    places = spec.DRAWING_REFERENCE_PRECISION
    assert round(draw._OVERHANG_AT_CUT, places) == 1.5
    assert round(spec.UPPER_PLATE_OVERHANG, places) == 1.5
    source = inspect.getsource(draw._create_section)
    assert "SetDisplayOnlySurfaceCut(False)" in source
    strap = draw._strap_x_at(draw.SECTION_Y)
    assert end[0] < min(strap[0], -spec.GUIDE_PLATE_WIDTH / 2.0)
    assert start[0] > max(strap[1], spec.GUIDE_PLATE_WIDTH / 2.0)
    # Each arrow's letter (5.5 mm wide, 14.6-20.1 mm under the line on the
    # 20261014T002650255Z sheet) clears the slanted strap edges by 1 mm, and on
    # the -x side the StrapTaperDx extension line too.
    half_letter = 0.00275
    letter_ys = (draw.SECTION_Y - 20.1, draw.SECTION_Y - 14.6)
    plus_edge = max(draw._strap_x_at(y)[1] for y in letter_ys)
    minus_edge = min(draw._strap_x_at(y)[0] for y in letter_ys)
    assert draw._fx(start[0]) + half_letter < draw._fx(plus_edge) - 0.001
    assert draw._fx(end[0]) - half_letter > draw._fx(minus_edge) + 0.001
    assert draw._fx(end[0]) + half_letter < draw._fx(spec.STRAP_TOP_X[0]) - 0.001
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


def test_overhang_reference_spans_the_strap_cut_and_the_plate_edge() -> None:
    strap_x = draw._ax(draw._STRAP_CUT_X[1])
    plate_x = draw._ax(draw._HALF_PLATE)
    # Model +x prints left: the plate edge stands left of the strap's cut.
    assert strap_x - plate_x == pytest.approx(draw._OVERHANG_AT_CUT * 0.002)
    # Picks inside the strap's thickness and on the plate's reach, between
    # the plate-back and slot-bottom extension lines.
    assert spec.STRAP_Z[0] < draw.OVERHANG_PICK_Z[0] < spec.STRAP_Z[1]
    assert spec.SLOT_BOTTOM_Z < draw.OVERHANG_PICK_Z[1] < spec.STRAP_Z[0]
    # Its row above the strap back face, its value left of the plate edge,
    # above the slot bottom's value.
    text_x, text_y = draw.OVERHANG_TEXT_XY
    assert text_y > draw._az(spec.STRAP_Z[1]) + 0.006
    assert text_x + 0.0045 < plate_x
    assert draw.SECTION_KEEP["SlotBottom"][1] < draw._az(spec.STRAP_Z[1])
    assert "_add_overhang_reference(adapter, section)" in inspect.getsource(draw.build)
    source = inspect.getsource(draw._add_overhang_reference)
    assert "set_reference_dimension(" in source
    assert 'orientation="horizontal"' in source


def test_upper_plate_location_callout_stays_off_lines() -> None:
    assert not re.search(r"\d", spec.UPPER_PLATE_LOCATION_CALLOUT)
    tip_x, tip_y = draw.UPPER_PLATE_NOTE_TIP
    text_x, text_y = draw.UPPER_PLATE_NOTE_XY
    # The tip on the plate's -x edge, between the slot bottom and plate front.
    assert tip_x == pytest.approx(draw._ax(-draw._HALF_PLATE))
    assert draw._az(spec.PLATE_FRONT_Z) < tip_y < draw._az(spec.SLOT_BOTTOM_Z)
    # The text right of the section's rightmost ink (the strap end), between
    # the corner radius's text above and the slot width's block below (the
    # note's two lines stand about 8.5 mm tall from its top-left).
    assert text_x > draw._ax(draw._SECTION_X[0])
    assert text_y < draw.SECTION_KEEP["SlotCornerR"][1] - 0.006
    assert text_y - 0.0085 > draw.SLOT_WIDTH_TEXT_XY[1] + 0.0075 + 0.005
    assert abs(text_y - tip_y) < text_x - tip_x
    assert "view=section" in inspect.getsource(draw.build)


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
