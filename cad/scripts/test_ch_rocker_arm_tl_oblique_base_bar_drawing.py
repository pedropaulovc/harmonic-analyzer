"""Offline contracts for the oblique trammel's base bar (MHA-CH-006-TL-20)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _config
import _drawing_contract
import ch_rocker_arm_tl_oblique_base_bar_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_base_bar as drawing
from _hole_spec import THREAD_MAJOR_MM

BUILD = Path(drawing.__file__).with_name("build_ch_rocker_arm_tl_oblique_base_bar.py")


def test_stock_is_the_calculators_flat_bar() -> None:
    assert (spec.BAR_THICK, spec.BAR_WIDTH, spec.BAR_LENGTH) == (
        trammel.BASE_BAR_THICK,
        trammel.BASE_BAR_WIDTH,
        trammel.BASE_BAR_LENGTH,
    )
    assert spec.BAR_THICK == pytest.approx(12.7)
    assert spec.BAR_WIDTH == pytest.approx(101.6)
    assert spec.BAR_LENGTH == 440.0


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
    assert spec.NEAR_SLOT_RISE == pytest.approx(10.3)
    assert spec.FAR_SLOT_DROP == pytest.approx(10.3)
    assert spec.NEAR_SLOT_RISE + spec.SLOT_RUN / 2.0 - spec.HALF_WIDTH == pytest.approx(
        spec.NEAR_SLOT_Y
    )
    assert spec.HALF_WIDTH - spec.FAR_SLOT_DROP - spec.SLOT_RUN / 2.0 == pytest.approx(
        spec.FAR_SLOT_Y
    )


def test_one_part_two_off_the_second_turned_over() -> None:
    """Main's ruling: one configuration, QTY 2. Turned over (180° about X) the
    bar's near slot lands at +37.5, located from its own side as the other
    slot is, so the two bars need no second hand."""
    assert spec.QUANTITY == 2
    row = _config.parts("ch-rocker-arm-tl-oblique-base-bar")
    assert row["quantity"] == spec.QUANTITY
    assert row["description"] == "BASE BAR"
    assert spec.FAR_SLOT_Y == -spec.NEAR_SLOT_Y
    assert spec.NEAR_SLOT_RISE == pytest.approx(spec.FAR_SLOT_DROP)
    assert not hasattr(spec, "FAR_SLOT_RISE")
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
    assert spec.SIDE_WALL == pytest.approx(3.55)
    assert spec.NEAR_END_WALL_WORST >= 1.5
    # c4-r2 blocker: located from the -Y side, the far slot's wall to the +Y
    # side was 1.985 at the nominal stock width and 1.185 at its .X low limit.
    # Each slot from its own side: 10.3 - 0.8 - 7.005, whatever the width.
    assert spec.SIDE_WALL_WORST == pytest.approx(2.495)
    build = BUILD.read_text(encoding="utf-8")
    assert 'high_corner = f"{lines[2]}.end"' in build
    assert "FAR_SLOT_DROP" in build


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
    assert spec.DRAWING_PRECISION_BY_NAME["BarWidth"] == 1  # 101.6 STOCK
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
    # Nothing crosses lane 0 between the near slot and the far slot's station.
    width_text_right = (
        drawing.FRONT_KEEP["SlotWidth"][0] + drawing._SLOT_WIDTH_TEXT_HALF
    )
    assert width_text_right <= drawing._sheet_x(drawing.FRONT_CENTER, spec.FAR_SLOT_X)
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
    assert spec.TOLERANCES == {
        **{("RailHoles", name): 0.08 for name in stations},
        ("RailRowReference", "RailRowY"): 0.08,
    }
    assert not stations & spec.STOCK_DIMENSIONS
    assert all(spec.DRAWING_PRECISION_BY_NAME[name] == 2 for name in stations)
    # Station and row bands do not stack: each hole sits in a 0.08 half-side
    # square, inside the screw's 0.167 a side in the rail's Ø4.5 hole.
    assert spec.RAIL_SCREW_CLEARANCE == pytest.approx(0.167, abs=0.001)
    assert spec.RAIL_HOLE_POSITION_RADIUS == pytest.approx(0.1131, abs=1e-4)
    assert spec.RAIL_PATTERN_ALLOWANCE > 0.05
    # The mate rides the outermost station, the one lane no extension line
    # crosses; no other station carries a callout.
    assert drawing.CALLOUTS_BELOW["RailHole7X"] == "MATCHES HGR15R RAIL HOLES"
    assert not (stations - {"RailHole7X"}) & set(drawing.CALLOUTS_BELOW)


def test_rail_row_is_located_from_the_faced_low_side() -> None:
    """r2 blocker: the row had no lateral location. It prints 50.80 ±0.08
    from the -Y edge, a model dimension on a hidden reference sketch."""
    assert spec.RAIL_ROW_Y == pytest.approx(50.8)
    assert spec.DRAWING_DIMENSIONS["RailRowReference"] == {"RailRowY"}
    assert spec.TOLERANCES[("RailRowReference", "RailRowY")] == spec.RAIL_HOLE_BAND
    assert spec.DRAWING_PRECISION_BY_NAME["RailRowY"] == 2
    build = BUILD.read_text(encoding="utf-8")
    assert 'row_station.record("RailRowY", \'"BarWidth" / 2\')' in build
    assert build.index('blank_sketch(adapter, "RailRowReference")') < build.index(
        "save_part_and_images(adapter, PART_NAME)"
    )
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in sheet
    # Every hole's requirement carries the row band from the low side.
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
    # The row's three-line block sits inside its span (bottom edge to
    # centreline), above the near rise's "10.3" and extension line; the stock
    # width's text rides above the row's upper extension line.
    block_low = row_y - drawing._RAIL_ROW_TEXT_HALF_HIGH
    block_high = row_y + drawing._RAIL_ROW_TEXT_HALF_HIGH
    assert block_low >= drawing._BOTTOM + 0.0055
    assert block_high <= drawing.FRONT_CENTER[1] - 0.0015
    assert width_y - 0.0045 > drawing.FRONT_CENTER[1]
    assert width_x - drawing._BAR_WIDTH_TEXT_HALF >= 0.0124 + 0.002


def test_rail_row_band_names_what_it_buys() -> None:
    """r3 blocker: the 50.80 ±0.08 named no mate. Its callout says the band
    keeps the holes in line with the rail's row, in the station stack's words."""
    assert drawing.CALLOUTS_BELOW["RailRowY"] == spec.RAIL_ROW_CALLOUT
    lines = spec.RAIL_ROW_CALLOUT.split("\n")
    assert lines == ["HOLES IN LINE", "FOR HGR15R RAIL"]
    assert "HGR15R" in spec.RAIL_MATE_CALLOUT
    widest = max(len(line) for line in lines)
    # The lane is sized for the widest line as measured on the r4 sheet,
    # about 2.6 mm a glyph (r1-r3 assumed 2.2 and the block overran).
    assert 2 * drawing._RAIL_ROW_TEXT_HALF >= widest * 0.0026
    # Loosening to the title block's ±0.51 would exceed the screw clearance.
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
    near_x = sx(centre, spec.NEAR_SLOT_X)
    assert keep["NearSlotX"][0] - drawing._NEAR_SLOT_X_TEXT_HALF >= near_x + 0.002
    # The run's text sits under its lower line: the drop's upper extension
    # line runs along the bar's top edge, where the text sat above.
    run_low = drawing._sheet_y(centre, spec.FAR_SLOT_Y - spec.SLOT_RUN / 2.0)
    assert keep["SlotRun"][1] + 0.00175 <= run_low - 0.002
    assert keep["SlotRun"][0] - drawing._SLOT_RUN_TEXT_HALF >= drawing._RIGHT + 0.002
    # Nearest first below the plan: the width's extension lines cross no
    # other dimension line.
    lanes = [
        keep[name][1] - drawing.TEXT_DROP
        for name in ("SlotWidth", "NearSlotX", "FarSlotX", "BarLength")
    ]
    assert lanes == pytest.approx([drawing._below_line(k) for k in range(4)])
    # The far drop's text clears the projected end view; its lower outside
    # arrow (about 3.5 long) stays above the run's text, which SolidWorks
    # sets right of the run's line on a shoulder, under the drop's lane.
    drop_x, drop_y = keep["FarSlotDrop"]
    assert drop_x + 0.0045 + 0.005 <= drawing.END_CENTER[0] - spec.BAR_THICK / 4000
    drop_low = drawing._sheet_y(centre, spec.HALF_WIDTH - spec.FAR_SLOT_DROP)
    assert drop_low - 0.0035 >= keep["SlotRun"][1] + 0.00175 + 0.002
    assert drawing._TOP > drop_y > drop_low


def test_rail_hole_stack_has_clear_lanes_inside_the_sheet() -> None:
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


def test_isometric_and_its_note_clear_the_end_view_and_title_block() -> None:
    iso_x, iso_y = drawing.ISO_CENTER
    # The 1:5 iso spans about 65 x 54 mm.
    assert iso_y + 0.027 <= drawing.END_CENTER[1] - drawing._HALF_W_SHEET - 0.010
    assert iso_x - 0.033 >= drawing._RIGHT + drawing._FAR_DROP_LANE + 0.010
    assert iso_x + 0.033 <= 0.4194 - 0.005
    note_x, note_y = drawing.ISO_NOTE_XY
    assert note_y <= iso_y - 0.027 - 0.003
    assert note_y - 0.0042 >= 0.0652 + 0.002
    assert iso_x - 0.033 <= note_x <= iso_x


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-base-bar")["number"]
    assert number == "MHA-CH-006-TL-20"
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
