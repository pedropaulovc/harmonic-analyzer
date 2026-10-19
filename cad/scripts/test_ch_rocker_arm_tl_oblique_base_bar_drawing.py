"""Offline contracts for the oblique trammel's base bar (MHA-CH-06-TL-20)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _config
import _drawing_contract
import ch_rocker_arm_tl_oblique_base_bar_spec as spec
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_base_bar as drawing
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm

BUILD = Path(drawing.__file__).with_name("build_ch_rocker_arm_tl_oblique_base_bar.py")


def test_stock_is_the_calculators_flat_bar() -> None:
    assert (spec.BAR_THICK, spec.BAR_WIDTH, spec.BAR_LENGTH) == (
        trammel.BASE_BAR_THICK,
        trammel.BASE_BAR_WIDTH,
        trammel.BASE_BAR_LENGTH,
    )
    assert spec.BAR_THICK == pytest.approx(12.7)
    assert spec.BAR_WIDTH == pytest.approx(152.4)
    assert spec.BAR_LENGTH == 440.0
    # The 2026-10-17 ruling (a): 1/2 x 6 with the column-side edge 3.5 in off
    # the rail, so the rail sits off the centreline. Rail 1's part frame has
    # y = -lateral, so the column side is the faced -Y side.
    assert (spec.LOW_SIDE_Y, spec.HIGH_SIDE_Y) == pytest.approx((-88.9, 63.5))
    assert spec.LOW_SIDE_Y == -trammel.BASE_BAR_COLUMN_EDGE
    assert spec.HIGH_SIDE_Y == -trammel.BASE_BAR_OPERATOR_EDGE
    assert not hasattr(spec, "HALF_WIDTH")


def test_rail_holes_are_seven_on_the_rail_pitch() -> None:
    assert spec.RAIL_HOLE_X == (40.0, 100.0, 160.0, 220.0, 280.0, 340.0, 400.0)
    assert spec.TAP_SPEC.kind == "tapped" and spec.TAP_SPEC.size == trammel.RAIL_SCREW
    assert spec.TAP_SPEC.end == "through_all"


def test_rail_screw_engagement_meets_rule_18() -> None:
    assert spec.RAIL_SCREW_ENGAGEMENT == pytest.approx(9.35)
    assert spec.RAIL_SCREW_ENGAGEMENT >= 1.5 * THREAD_MAJOR_MM[spec.RAIL_SCREW]
    assert spec.RAIL_SCREW_ENGAGEMENT < spec.BAR_THICK


def test_slots_follow_the_brief() -> None:
    assert spec.SLOT_LENGTH == pytest.approx(19.5)
    assert spec.NEAR_SLOT_X == pytest.approx(20.92, abs=0.005)
    assert spec.FAR_SLOT_X == pytest.approx(390.0)
    assert (spec.NEAR_SLOT_Y, spec.FAR_SLOT_Y) == (-37.5, 37.5)
    assert spec.NEAR_SLOT_RISE == pytest.approx(48.4)
    assert spec.FAR_SLOT_RISE == pytest.approx(123.4)
    assert spec.LOW_SIDE_Y + spec.NEAR_SLOT_RISE + spec.SLOT_RUN / 2.0 == pytest.approx(
        spec.NEAR_SLOT_Y
    )
    assert spec.LOW_SIDE_Y + spec.FAR_SLOT_RISE + spec.SLOT_RUN / 2.0 == pytest.approx(
        spec.FAR_SLOT_Y
    )


def test_one_part_two_off_the_second_turned_over() -> None:
    """Main's ruling: one configuration, QTY 2. Turned over (180° about X) the
    bar keeps lateral: its column-side edge, near slot and rail row land where
    bar 1's do on its own rail, so the two bars need no second hand."""
    assert spec.QUANTITY == 2
    row = _config.parts("ch-rocker-arm-tl-oblique-base-bar")
    assert row["quantity"] == spec.QUANTITY
    assert row["description"] == "BASE BAR"
    assert spec.FAR_SLOT_Y == -spec.NEAR_SLOT_Y
    # The slots stay symmetric about the rail, both located from the -Y side
    # (c3-r6, rule 10): the rises differ by the slots' spacing.
    assert spec.FAR_SLOT_RISE - spec.NEAR_SLOT_RISE == pytest.approx(
        spec.FAR_SLOT_Y - spec.NEAR_SLOT_Y
    )
    assert not hasattr(spec, "FAR_SLOT_DROP")
    for gone in (
        "CONFIGS",
        "DEFAULT_CONFIG",
        "QUANTITIES",
        "SLOT_Y",
        "RISES",
        "CONFIGURATION_DIMENSIONS",
        "FEATURE_STEP_CONFIGURATIONS",
        "configuration_number",
    ):
        assert not hasattr(spec, gone), gone
    build = BUILD.read_text(encoding="utf-8")
    assert "create_configuration" not in build
    assert "assert_saved_configurations_regenerate" not in build
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    for token in ("ReferencedConfiguration", "QTY", '"LH"', '"RH"', "OPPOSITE HAND"):
        assert token not in sheet, token


def test_walls_meet_rule_17() -> None:
    assert spec.NEAR_END_WALL == pytest.approx(14.17, abs=0.01)
    # The 2026-10-17 widening: the far slot's wall to the +Y side is the
    # thinner of the two (the rail sits nearer that side).
    assert spec.NEAR_SIDE_WALL == pytest.approx(41.65)
    assert spec.FAR_SIDE_WALL == pytest.approx(16.25)
    assert spec.SIDE_WALL == spec.FAR_SIDE_WALL
    assert spec.NEAR_END_WALL_WORST >= 1.5
    # c3-r6, rule 10: both slots from the -Y side, so the far slot's wall to
    # the +Y side carries the stock width's .X band and its rise's and run's
    # .XX (c4-r2 dropped it from the +Y side when that left 1.2 on the 1/2 x 4
    # bar): 152.4 - 0.8 - (123.4 + 0.8 + 6 + 0.51) - 7.005 on the 1/2 x 6.
    assert spec.FAR_SIDE_WALL_WORST == pytest.approx(13.885)
    assert spec.SIDE_WALL_WORST == spec.FAR_SIDE_WALL_WORST
    assert spec.SIDE_WALL_WORST >= 1.5
    build = BUILD.read_text(encoding="utf-8")
    assert "high_corner" not in build
    assert "adapter, low_corner, FAR_SLOT_X, FAR_SLOT_Y, FAR_SLOT_RISE" in build


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.END_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.END_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.STOCK_DIMENSIONS <= marked
    assert set(drawing.CALLOUTS_BELOW) <= marked


def test_stock_sizes_say_stock_and_nothing_prints_as_reference() -> None:
    assert spec.STOCK_DIMENSIONS == {"BarWidth", "BarThick"}
    for name in spec.STOCK_DIMENSIONS:
        assert drawing.CALLOUTS_BELOW[name] == "STOCK"
    assert spec.DRAWING_PRECISION_BY_NAME["BarWidth"] == 1  # 152.4 STOCK
    assert spec.DRAWING_PRECISION_BY_NAME["BarThick"] == 2  # 12.70 STOCK
    assert not hasattr(spec, "REFERENCE_DIMENSIONS")
    assert not any("(" in prefix for prefix, _ in drawing.DIMENSION_TEXT.values())
    assert spec.DRAWING_NOTES == ""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" not in source


def test_slot_run_is_centre_to_centre_with_centre_marks() -> None:
    # Rule 12: slots are dimensioned to their radius centres; the marks make
    # the 2X 6.00 read as centre-to-centre.
    assert spec.SLOT_RUN == pytest.approx(6.0)
    assert drawing.DIMENSION_TEXT["SlotRun"] == ("2X ", "")
    # r5: the slots never said THRU; the width's text says it for both.
    assert drawing.DIMENSION_TEXT["SlotWidth"] == ("2X ", " THRU")
    glyphs = len("".join(drawing.DIMENSION_TEXT["SlotWidth"])) + len("13.50")
    assert 2 * drawing._SLOT_WIDTH_TEXT_HALF >= glyphs * 0.0026
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks(adapter, front, holes=False, slots=True" in source
    # The printed run is the far slot's: its dimension lands right of the
    # bar, off the part (rule 14).
    build = BUILD.read_text(encoding="utf-8")
    assert 'dims.record("SlotRun", \'"SlotRun"\')' in build.split("else:")[-1]
    assert drawing.FRONT_KEEP["SlotRun"][0] > drawing._RIGHT


def test_rail_holes_hold_a_baseline_band_that_names_its_mate() -> None:
    stations = {f"RailHole{k}X" for k in range(1, 8)}
    assert spec.DRAWING_DIMENSIONS["RailHoles"] == stations
    # c3-r7 (rule 4): only the stations, the rail's pitch, carry the band.
    assert spec.TOLERANCES == {("RailHoles", name): 0.08 for name in stations}
    assert not stations & spec.STOCK_DIMENSIONS
    assert all(spec.DRAWING_PRECISION_BY_NAME[name] == 2 for name in stations)
    # One DRO Y setting cuts the row: only the station band scatters one hole
    # off another, 0.08 inside the screw's 0.167 a side in the rail's Ø4.5.
    assert spec.RAIL_SCREW_CLEARANCE == pytest.approx(0.167, abs=0.001)
    assert spec.RAIL_HOLE_POSITION_RADIUS == spec.RAIL_HOLE_BAND
    assert spec.RAIL_PATTERN_ALLOWANCE == pytest.approx(0.087, abs=1e-3)
    # The mate rides the outermost station, the one lane no extension line
    # crosses; no other station carries a callout.
    assert drawing.CALLOUTS_BELOW["RailHole7X"] == "MATCHES HGR15R RAIL HOLES"
    assert not (stations - {"RailHole7X"}) & set(drawing.CALLOUTS_BELOW)


def test_rail_row_is_located_from_the_faced_low_side() -> None:
    """r2 blocker: the row had no lateral location. It prints 88.90 from the
    -Y edge, a model dimension on a hidden reference sketch, at the title
    block's .XX band (c3-r7, rule 4: nothing mates with the row's height)."""
    assert spec.RAIL_ROW_Y == pytest.approx(88.9)
    assert spec.DRAWING_DIMENSIONS["RailRowReference"] == {"RailRowY"}
    assert ("RailRowReference", "RailRowY") not in spec.TOLERANCES
    assert spec.DRAWING_PRECISION_BY_NAME["RailRowY"] == spec.RAIL_ROW_PLACES == 2
    build = BUILD.read_text(encoding="utf-8")
    # Since the 2026-10-17 widening the row is off the centreline: the row
    # and the profile's origin anchor both read the -Y side's own station.
    assert 'row_station.record("RailRowY", \'"RailRowY"\')' in build
    assert 'names=["BarLength", "BarWidth", "BarLowSide"]' in build
    assert "drives=['\"BarLength\"', '\"BarWidth\"', '\"RailRowY\"']" in build
    assert build.index('blank_sketch(adapter, "RailRowReference")') < build.index(
        "save_part_and_images(adapter, PART_NAME)"
    )
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in sheet
    # Every hole's requirement carries the row's height from the low side.
    assert drawing._FROM_LOW_SIDE[0] == "bar_low_side"


def test_side_lanes_clear_each_other_and_the_border() -> None:
    keep = drawing.FRONT_KEEP
    rise_x = keep["NearSlotRise"][0]
    row_x, row_y = keep["RailRowY"]
    width_x, width_y = keep["BarWidth"]
    assert rise_x < drawing._LEFT and row_x < rise_x and width_x < row_x
    # The row's text clears the rise's line, its outside arrow and that
    # arrow's tail (r4: they struck the block's last "L"), and the stock
    # width's line.
    assert row_x + drawing._RAIL_ROW_TEXT_HALF <= rise_x - 0.0025
    assert row_x - drawing._RAIL_ROW_TEXT_HALF >= width_x + 0.002
    # The row's three-line block sits inside its span (bottom edge to the
    # row's line), above the near rise's upper extension line (the 48.4's
    # text rides inside its own span); the stock width's text rides above the
    # row's upper extension line.
    row_line = drawing._sheet_y(drawing.FRONT_CENTER, 0.0)
    rise_top = drawing._sheet_y(
        drawing.FRONT_CENTER, spec.LOW_SIDE_Y + spec.NEAR_SLOT_RISE
    )
    block_low = row_y - drawing._RAIL_ROW_TEXT_HALF_HIGH
    block_high = row_y + drawing._RAIL_ROW_TEXT_HALF_HIGH
    assert block_low >= rise_top + 0.0005
    assert block_high <= row_line - 0.0015
    assert width_y - 0.0045 > row_line
    assert width_x - drawing._BAR_WIDTH_TEXT_HALF >= 0.0124 + 0.002


def test_rail_row_names_what_it_buys() -> None:
    """r3 blocker: the row's ±0.08 named no mate; c3-r7 dropped the band (the
    slots set the bar's place, one DRO setting lines the holes up). The
    callout keeps the reason, in the station stack's words."""
    assert drawing.CALLOUTS_BELOW["RailRowY"] == spec.RAIL_ROW_CALLOUT
    lines = spec.RAIL_ROW_CALLOUT.split("\n")
    assert lines == ["HOLES IN LINE", "FOR HGR15R RAIL"]
    assert "HGR15R" in spec.RAIL_MATE_CALLOUT
    widest = max(len(line) for line in lines)
    # The lane is sized for the widest line as measured on the r4 sheet,
    # about 2.6 mm a glyph (r1-r3 assumed 2.2 and the block overran).
    assert 2 * drawing._RAIL_ROW_TEXT_HALF >= widest * 0.0026
    # The stations' band stays inside the screw clearance; the title block's
    # ±0.51 would not, so only the row (moving all seven together) takes it.
    assert spec.RAIL_HOLE_BAND < spec.RAIL_SCREW_CLEARANCE < 0.51


def test_tap_callout_has_clear_air_under_the_border() -> None:
    """r3: the callout's first line touched the 267 mm border. Its two lines
    span about 4.8 above and below the keep point."""
    x, y = drawing.TAP_CALLOUT_XY
    assert y + 0.0048 <= 0.267 - 0.004
    # Clear of the station stack's outermost extension line (hole 7).
    hole_7 = drawing._sheet_x(drawing.FRONT_CENTER, spec.RAIL_HOLE_X[-1])
    assert x - 0.022 >= hole_7 + 0.010


def test_short_span_texts_print_beside_their_spans() -> None:
    """r2 struck '2X 13.50', '20.9' and '2X 6.00' with their own lines."""
    keep = drawing.FRONT_KEEP
    sx = drawing._sheet_x
    centre = drawing.FRONT_CENTER
    slot_right = sx(centre, spec.NEAR_SLOT_X + spec.SLOT_WIDTH / 2.0)
    assert keep["SlotWidth"][0] - drawing._SLOT_WIDTH_TEXT_HALF >= slot_right + 0.002
    # Its text sits right of the near bracket row's extension line, which
    # runs down through lane 0 (C4 left the 2X 13.50 struck by it).
    near_pair = sx(centre, drawing.BRACKET_NEAR_X)
    assert keep["SlotWidth"][0] - drawing._SLOT_WIDTH_TEXT_HALF >= near_pair + 0.002
    assert keep["SlotWidth"][0] + drawing._SLOT_WIDTH_TEXT_HALF <= sx(
        centre, spec.FAR_SLOT_X
    )
    near_x = sx(centre, spec.NEAR_SLOT_X)
    assert keep["NearSlotX"][0] - drawing._NEAR_SLOT_X_TEXT_HALF >= near_x + 0.002
    # The run's text sits under its lower line, shouldered right of it.
    run_low = drawing._sheet_y(centre, spec.FAR_SLOT_Y - spec.SLOT_RUN / 2.0)
    assert keep["SlotRun"][1] + 0.00175 <= run_low - 0.002
    assert keep["SlotRun"][0] - drawing._SLOT_RUN_TEXT_HALF >= drawing._RIGHT + 0.002
    # Nearest first below the plan: the width's extension lines cross no
    # other dimension line; each station's lane sits below every shorter one.
    below = (
        "SlotWidth",
        "NearSlotX",
        "BracketHole1X",
        "FarSlotX",
        "BracketHole5X",
        "BarLength",
    )
    lanes = [keep[name][1] - drawing.TEXT_DROP for name in below]
    assert lanes == pytest.approx([drawing._below_line(k) for k in range(6)])
    # c3-r6: the far rise, from the -Y edge, is the tallest right-side
    # dimension, so it takes the outermost lane, past the outermost bracket
    # row's, its text above that row's upper extension line (and its
    # overshoot), below the run's text and clear of the end view. c4-r9: its
    # line one stack lane out struck the 61.400's last "0"; it now clears
    # that text (13.9 wide on the r9 sheet) by 1.5.
    rise_x, rise_y = keep["FarSlotRise"]
    outer_row = drawing._BRACKET_ROW_LANES[0]
    assert drawing._BRACKET_ROW_TEXT_HALF >= 0.0139 / 2
    assert (
        rise_x - 0.0015 >= drawing._RIGHT + outer_row + drawing._BRACKET_ROW_TEXT_HALF
    )
    assert rise_x - drawing._RIGHT - outer_row >= drawing.STACK_LANE
    assert all(rise_x > drawing._RIGHT + lane for lane in drawing._BRACKET_ROW_LANES)
    run_text_right = (
        drawing._RIGHT + drawing._SLOT_RUN_LANE + drawing._SLOT_RUN_TEXT_HALF
    )
    assert rise_x > run_text_right
    # 3 of air to the end view: moving the view right instead would push the
    # 12.70 STOCK text, 2.6 inside the right border on the r9 sheet, over it.
    assert (
        rise_x + drawing._FAR_RISE_TEXT_HALF + 0.003
        <= drawing.END_CENTER[0] - spec.BAR_THICK / 4000
    )
    row_top = drawing._sheet_y(centre, drawing.BRACKET_ROW_Y[0])
    assert rise_y - 0.00175 >= row_top + 0.005
    assert rise_y + 0.00175 + 0.005 <= keep["SlotRun"][1] - 0.00175
    assert rise_y < run_low


def test_rail_hole_stack_has_clear_lanes_inside_the_sheet() -> None:
    # c4-r8: with the plan centred at y 0.1725 the 400.00 block's top line
    # printed about 0.4 under the 267 border; the drop keeps 3 or more.
    r8_air, r8_centre_y = 0.0004, 0.1725
    assert r8_air + (r8_centre_y - drawing.FRONT_CENTER[1]) >= 0.003
    lines = [drawing._above_line(k) for k in range(7)]
    assert lines[0] - drawing._TOP >= 0.008
    assert all(b - a >= 0.006 - 1e-12 for a, b in zip(lines, lines[1:]))
    keeps = [drawing.FRONT_KEEP[f"RailHole{k}X"] for k in range(1, 8)]
    assert [y for _x, y in keeps] == sorted(y for _x, y in keeps)
    # The two-line top block (value + mate) stays under the 267 mm border.
    assert keeps[-1][1] + 0.0046 <= 0.265
    # The 40.00 text sits between holes 1 and 2, clear of the end face's
    # extension line and of hole 1's.
    sheet_x = [drawing._sheet_x(drawing.FRONT_CENTER, x) for x in spec.RAIL_HOLE_X]
    assert sheet_x[0] + 0.012 <= keeps[0][0] <= sheet_x[1] - 0.012


def test_end_view_projects_on_the_plans_centreline() -> None:
    """r2: the edge view hung about 45 mm below the plan."""
    assert drawing.END_CENTER[1] == drawing.FRONT_CENTER[1]
    assert drawing.END_CENTER[0] > drawing._RIGHT
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'place_view(adapter, str(SOURCE), "*Right", *END_CENTER' in source


def test_isometric_and_its_note_take_the_free_bottom_left_corner() -> None:
    """C4: the bracket callout takes the bottom right; the 1:5 iso (about
    66 x 62 mm since the 2026-10-17 widening) moves under the plan's stack,
    left of the title block."""
    iso_x, iso_y = drawing.ISO_CENTER
    half_x, half_y = drawing.ISO_HALF
    lowest_text = drawing._below_line(5) + drawing.TEXT_DROP - 0.00175
    # c4-r8 dropped the plan 3 for the border: the iso keeps 7 under the
    # length's text, its note under it.
    assert iso_y + half_y <= lowest_text - 0.007
    assert iso_x - half_x >= 0.0127 + 0.010
    assert iso_x + half_x <= 0.216 - 0.010  # the title block's left edge
    note_x, note_y = drawing.ISO_NOTE_XY
    assert note_y <= iso_y - half_y - 0.003
    assert note_y - 0.0042 >= 0.0127 + 0.005
    assert iso_x - half_x <= note_x <= iso_x


def test_bracket_holes_are_the_leadscrew_layouts() -> None:
    """C4: eight #8 clearance holes at the leadscrew spec's positions, from
    its own tuple; counterbored from the underside, the spec's hole kind."""
    # A row of four (ruling A′) at each KP08 station (derived by the leadscrew
    # layout) on four shared rows; the near station moves with the nut, so it
    # is not pinned.
    near_x = leadscrew.BASE_BAR_HOLES[0][0]
    far_x = leadscrew.BASE_BAR_HOLES[-1][0]
    rows = (-27.5, -44.0, -66.0, -82.5)
    assert leadscrew.BASE_BAR_HOLES == tuple(
        (x, y) for x in (near_x, far_x) for y in rows
    )
    assert drawing.BRACKET_ROW_Y == rows
    assert drawing.BRACKET_HOLES is leadscrew.BASE_BAR_HOLES
    hole = spec.BRACKET_HOLE_SPEC
    wanted = leadscrew.BASE_BAR_HOLE_SPEC
    assert (hole.kind, hole.size, hole.end, hole.fit) == (
        wanted.kind,
        wanted.size,
        wanted.end,
        wanted.fit,
    )
    assert spec.BRACKET_HOLE_DIA == CLEARANCE_MM[("#8", "normal")]
    assert hole.overrides_mm["HoleDiameter"] == spec.BRACKET_HOLE_DIA
    source = BUILD.read_text(encoding="utf-8")
    assert "leadscrew.BASE_BAR_HOLES" in source
    assert "[[x, y, 0.0] for x, y in BRACKET_HOLES]" in source
    assert "(0.0, 0.0, -1.0)" in source
    assert 'blank_sketch(adapter, "BracketRowReference")' in source


def test_bracket_counterbores_sink_and_seat_the_heads() -> None:
    assert spec.BRACKET_SCREW_HEAD_DIA == pytest.approx(6.858)
    assert spec.BRACKET_SCREW_HEAD_HEIGHT == pytest.approx(leadscrew.SHCS_8_HEAD)
    assert spec.BRACKET_HEAD_RECESS_MIN == pytest.approx(0.124, abs=1e-3)
    assert spec.BRACKET_HEAD_CLEARANCE_MIN == pytest.approx(0.572, abs=1e-3)
    assert spec.BRACKET_HEAD_BEARING_MIN == pytest.approx(0.89, abs=1e-3)
    assert spec.BRACKET_CBORE_FLOOR_MIN == pytest.approx(6.88, abs=1e-3)
    # Rule 18: a #8-32 x 5/8 reaches 1.5 D into TL-28 at the printed worst.
    low, high = spec.bracket_screw_under_head(0.625 * 25.4)
    assert (low, high) == pytest.approx((6.955, 8.995), abs=1e-3)
    assert low >= 1.5 * THREAD_MAJOR_MM[leadscrew.BAR_SCREW]


def test_bracket_hole_walls_meet_rule_17() -> None:
    walls = spec.bracket_hole_walls(leadscrew.BASE_BAR_HOLES)
    # The rows and the far station are fixed; the near station follows the
    # leadscrew layout, so its walls are bounded, not pinned. Ruling A′: the
    # -Y edge's 2.045 is the rule-17 target that bounds the outer screws.
    fixed = {"-Y edge", "+Y edge", "far end", "neighbour counterbore"}
    assert {name: walls[name] for name in fixed} == pytest.approx(
        {
            "-Y edge": 2.045,
            "+Y edge": 85.845,
            "far end": 6.845,
            "neighbour counterbore": 7.682,
        },
        abs=1e-3,
    )
    assert walls["-Y edge"] >= 2.0
    assert walls["spindle end"] > 50.0
    assert walls["rail tap"] > 20.0
    assert walls["hold-down slot"] > 20.0
    assert min(walls.values()) >= spec.BRACKET_WALL_MIN


def test_bracket_pattern_holds_the_tl28_float_and_names_it() -> None:
    """Stations and rows at .XXX (±0.13): inside the ±0.15 the TL-28 stack
    leaves; the tight band names its mate, and the plan, looking at the top,
    says the counterbores are on the far side."""
    assert printed_band_mm(spec.BRACKET_HOLE_PLACES) <= 0.15
    for name in (
        "BracketHole1X",
        "BracketHole5X",
        *(f"BracketRow{row}Y" for row in range(1, 5)),
    ):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 3
    lines = spec.BRACKET_CALLOUT_PROCESS.split("\n")
    assert lines == ["MATCHES MHA-CH-06-TL-28", "DRILL, C'BORE FAR SIDE", ""]
    assert "MHA-CH-06-TL-28" == spec.BRACKET_MATE
    assert spec.BRACKET_CALLOUT_PRECISION == {
        "hw-thruholedia": 2,
        "hw-cbdia": 2,
        "hw-cbdepth": 2,
    }
    # Rule 12: the size and a process word, no screw in the place of a size.
    assert "SHCS" not in spec.BRACKET_CALLOUT_PROCESS


def test_bracket_dimensions_and_callout_lay_out_clear() -> None:
    keep = drawing.FRONT_KEEP
    sx = drawing._sheet_x
    centre = drawing.FRONT_CENTER
    # The near row's station text sits inside its span's right end, clear of
    # the near slot's centre line and of its own extension line.
    near_text = keep["BracketHole1X"][0]
    assert (
        near_text - drawing._BRACKET_NEAR_X_TEXT_HALF
        >= sx(centre, spec.NEAR_SLOT_X) + 0.002
    )
    near_station = sx(centre, drawing.BRACKET_NEAR_X)
    assert near_text + drawing._BRACKET_NEAR_X_TEXT_HALF <= near_station - 0.002
    # Right lanes, nearest first: 6.400 (its text right of its line on a
    # shoulder, under the bar), then 22.900, whose outside arrow under the
    # bar's edge clears that text (c4-r2: it struck the "8"), then 44.900 and
    # 61.400 (ruling A′'s four rows), each one lane further out.
    lanes = [keep[f"BracketRow{row}Y"] for row in (4, 3, 2, 1)]
    outer_x, outer_y = lanes[0]
    assert drawing._RIGHT < outer_x < lanes[1][0] < lanes[2][0] < lanes[3][0]
    assert outer_y + 0.00175 <= drawing._BOTTOM - 0.002  # under the bar's edge
    outer_text_right = outer_x + drawing._SHOULDER_TEXT_SPAN[1]
    assert lanes[1][0] >= outer_text_right + 0.003
    # Spread: the first two lines at least 15 apart (c4-r2: 9, bunched).
    assert lanes[1][0] - outer_x >= 0.015
    half = drawing._BRACKET_ROW_TEXT_HALF
    tops = [drawing._sheet_y(centre, y) for y in reversed(drawing.BRACKET_ROW_Y)]
    for (short_x, _), (tall_x, tall_y), short_top in zip(
        lanes[1:], lanes[2:], tops[1:], strict=False
    ):
        # A text sharing heights with the shorter row's line and that row's
        # extension line (overshoot about 2) clears them by 2.5.
        if tall_y - 0.00175 < short_top:
            # (exactly 2.5 at r9's measured 61.400 width; float slack only)
            assert tall_x - half >= short_x + 0.002 + 0.0025 - 1e-9
    # c4-r8: the 44.900 and 61.400 texts, both mid-span, read as one cluster;
    # the 61.400's stands at the top of its span, 8 or more clear of the other.
    (_x2, y2), (_x1, y1) = lanes[2], lanes[3]
    assert y1 - y2 >= 0.0035 + 0.008
    assert y1 + 0.00175 <= tops[3] - 0.0045  # under its upper arrow (about 3.5)
    assert lanes[-1][0] + half <= (
        drawing.END_CENTER[0] - spec.BAR_THICK / 4000 - 0.005
    )
    # The leader leaves the far outer hole down and right; at the length's
    # extension line (x _RIGHT) it is under the bar, and it passes under the
    # 6.400 text.
    hole = (sx(centre, 428.0), drawing._sheet_y(centre, -82.5))
    cx, cy = drawing.BRACKET_CALLOUT_XY
    half_w, half_h = 0.027, 0.010  # "MATCHES MHA-CH-06-TL-28", four rows
    land = (cx - half_w, cy)
    slope = (land[1] - hole[1]) / (land[0] - hole[0])
    at_right = hole[1] + slope * (drawing._RIGHT - hole[0])
    assert at_right < drawing._BOTTOM - 0.002
    text_left = outer_x + drawing._SHOULDER_TEXT_SPAN[0]
    under_text = hole[1] + slope * (text_left - hole[0])
    assert under_text <= outer_y - 0.00175 - 0.002
    # The block: under the end view, above the title block, inside the border.
    assert cy + half_h <= drawing.END_CENTER[1] - drawing._HALF_W_SHEET - 0.010
    assert cy - half_h >= 0.0657 + 0.010
    assert land[0] >= drawing._RIGHT + 0.005
    assert cx + half_w <= 0.4194 - 0.005


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-base-bar")["number"]
    assert number == "MHA-CH-06-TL-20"
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_places_are_model_authored_and_the_sheet_is_pure() -> None:
    script = Path(drawing.__file__)
    assert script.name in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    assert not _drawing_contract.drawing_specification_violations(
        script.read_text(encoding="utf-8"), filename=script.name
    )


def test_notes_follow_the_simplicity_policy() -> None:
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert "REFERENCE" not in spec.DRAWING_NOTES


def test_isometric_is_in_the_hidden_lines_removed_loop() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, end, iso):" in source


_TAP_VARIABLES = {
    "<hw-threaddesc>": "8-32 UNC",
    "<hw-threadclass>": spec.TAP_SPEC.thread_class,
    "<hw-thru>": "THRU ALL",
}


class _TapCallout:
    """A native tap callout: part 5 is the thread row's definition, part 1
    its resolved text; ``SetText(1, ...)`` rewrites the definition."""

    def __init__(
        self, definition: str, *, accepts: bool = True, stuck: str = ""
    ) -> None:
        self.definition = definition
        self.accepts = accepts
        self.stuck = stuck

    def IsHoleCallout(self) -> bool:
        return True

    def SetText(self, part: int, text: str) -> None:
        assert part == 1
        if self.accepts:
            self.definition = text

    def GetText(self, part: int) -> str:
        if part == 5:
            return self.definition
        if part != 1:
            return ""
        if self.stuck:
            return self.stuck
        resolved = self.definition
        for token, value in _TAP_VARIABLES.items():
            resolved = resolved.replace(token, value)
        return resolved


def test_tap_callout_drops_the_title_block_thread_class() -> None:
    callout = _TapCallout("<hw-threaddesc> - <hw-threadclass> <hw-thru>")
    drawing._omit_tap_thread_class(callout)
    assert callout.definition == "<hw-threaddesc> <hw-thru>"
    assert callout.GetText(1) == "8-32 UNC THRU ALL"
    for refused in (
        _TapCallout("<hw-threaddesc> - <hw-threadclass> <hw-thru>", accepts=False),
        _TapCallout("<hw-threaddesc> <hw-thru>"),
        _TapCallout(
            "<hw-threaddesc> - <hw-threadclass> <hw-thru>",
            stuck="8-32 UNC - 2B THRU ALL",
        ),
    ):
        with pytest.raises(RuntimeError):
            drawing._omit_tap_thread_class(refused)
