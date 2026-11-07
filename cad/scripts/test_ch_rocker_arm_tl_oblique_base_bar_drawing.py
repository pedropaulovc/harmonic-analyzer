"""Offline contracts for the oblique trammel's base bar (MHA-CH-06-TL-20)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _config
import _drawing_contract
import ch_rocker_arm_tl_oblique_base_bar_spec as spec
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_base_bar as drawing
import export_features
from _gtol_planar import PlanarFace
from _hole_spec import CLEARANCE_MM, NUMBER_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from _surface_finish import SEAT_UM

BUILD = Path(drawing.__file__).with_name("build_ch_rocker_arm_tl_oblique_base_bar.py")
STEM = "ch_rocker_arm_tl_oblique_base_bar"


def test_bar_is_milled_from_the_owned_bar_and_faced_to_thickness() -> None:
    assert (spec.BAR_THICK, spec.BAR_WIDTH, spec.BAR_LENGTH) == (
        trammel.BASE_BAR_THICK,
        trammel.BASE_BAR_WIDTH,
        trammel.BASE_BAR_LENGTH,
    )
    # Owner ruling 2026-10-30 (option A): both large faces faced from the
    # 1/2 in bar; owner ruling #2083: the width milled from the owned 1/2 x 6
    # bar. #290: the faced thickness, the milled width and the length print
    # on the .XX grid, at the inch title block's band.
    assert trammel.BASE_BAR_STOCK_THICK == pytest.approx(12.7)
    assert spec.BAR_THICK < trammel.BASE_BAR_STOCK_THICK
    assert spec.UNIT == "in"
    assert spec.THICK_PLACES == trammel.BASE_BAR_THICK_PLACES == 2
    assert spec.WIDTH_PLACES == spec.DRAWING_PRECISION_BY_NAME["BarWidth"] == 2
    assert trammel.BASE_BAR_THICK_BAND == printed_band_mm(2, unit="in")
    assert spec.BAR_WIDTH_BAND == printed_band_mm(spec.WIDTH_PLACES, unit="in")
    for value in (spec.BAR_THICK, spec.BAR_WIDTH, spec.BAR_LENGTH):
        assert value / 25.4 == pytest.approx(round(value / 25.4, 2), abs=1e-9)
    # Milled from 6 in, the widest part still fits the vise's stock jaws.
    assert spec.BAR_WIDTH + spec.BAR_WIDTH_BAND < 6.0 * 25.4
    # Purchased 450 rails are datum-trimmed to the actual existing bars.
    assert spec.BAR_LENGTH == trammel.BASE_BAR_LENGTH == trammel.RAIL_LENGTH
    assert round(spec.BAR_LENGTH / 25.4, 2) == 17.32
    assert trammel.RAIL_OVERHANG == pytest.approx(0.0, abs=1e-9)
    assert trammel.RAIL_TRIM_PER_END == pytest.approx(5.036)
    assert spec.RAIL_HOLE_X[-1] < spec.BAR_LENGTH
    # The 2026-10-30 ruling: 5.50 wide (vise fit) with the column-side edge
    # still 3.5 in off the rail, so the rail sits off the centreline. Rail 1's
    # part frame has y = -lateral, so the column side is the faced -Y side.
    assert (spec.LOW_SIDE_Y, spec.HIGH_SIDE_Y) == pytest.approx((-88.9, 50.8))
    assert spec.LOW_SIDE_Y == -trammel.BASE_BAR_COLUMN_EDGE
    assert spec.HIGH_SIDE_Y == -trammel.BASE_BAR_OPERATOR_EDGE
    assert not hasattr(spec, "HALF_WIDTH")


def test_rail_holes_are_eight_on_the_rail_pitch() -> None:
    assert spec.RAIL_HOLE_X == pytest.approx(tuple(9.964 + 60.0 * k for k in range(8)))
    assert spec.TAP_SPEC.kind == "tapped" and spec.TAP_SPEC.size == trammel.RAIL_SCREW
    assert spec.TAP_SPEC.end == "through_all"


def test_rail_screw_engagement_meets_rule_18() -> None:
    assert spec.RAIL_SCREW_ENGAGEMENT == pytest.approx(9.35)
    assert spec.RAIL_SCREW_ENGAGEMENT >= 1.5 * THREAD_MAJOR_MM[spec.RAIL_SCREW]
    assert spec.RAIL_SCREW_ENGAGEMENT < spec.BAR_THICK


def test_slots_follow_the_brief() -> None:
    assert spec.SLOT_LENGTH == pytest.approx(spec.SLOT_RUN + spec.SLOT_WIDTH)
    # The 1/2 stud passes the narrowest printed slot.
    assert spec.SLOT_WIDTH - printed_band_mm(2, unit="in") > spec.HOLD_DOWN_STUD_DIA
    assert (spec.NEAR_SLOT_Y, spec.FAR_SLOT_Y) == (
        -trammel.HOLD_DOWN_LATERAL,
        trammel.HOLD_DOWN_LATERAL,
    )
    # Every slot size, rise and the far station on the .XX grid; the near
    # station closes the T-slot pitch and prints rounded.
    for value in (
        spec.SLOT_WIDTH,
        spec.SLOT_RUN,
        spec.FAR_SLOT_X,
        spec.NEAR_SLOT_RISE,
        spec.FAR_SLOT_RISE,
    ):
        assert value / 25.4 == pytest.approx(round(value / 25.4, 2), abs=1e-9)
    assert spec.LOW_SIDE_Y + spec.NEAR_SLOT_RISE + spec.SLOT_RUN / 2.0 == pytest.approx(
        spec.NEAR_SLOT_Y
    )
    assert spec.LOW_SIDE_Y + spec.FAR_SLOT_RISE + spec.SLOT_RUN / 2.0 == pytest.approx(
        spec.FAR_SLOT_Y
    )


def test_one_number_two_members_the_second_plain_and_turned_over() -> None:
    """Oblique simplification PR2: one native model, one Number, two named
    members. Bar1 (rail 1) carries the TL-28 bracket holes; Bar2 (rail 2) is
    the same bar without them, turned over (180° about X): it keeps lateral,
    so its column-side edge, near slot and rail row land where Bar1's do on
    its own rail, and the two bars need no second hand."""
    assert spec.QUANTITY == 2
    row = _config.parts("ch-rocker-arm-tl-oblique-base-bar")
    assert row["quantity"] == spec.QUANTITY
    assert row["number"] == "MHA-CH-06-TL-20"
    assert row["description"] == "BASE BAR"
    assert spec.CONFIGURATIONS == (spec.BAR1, spec.BAR2) == ("Bar1", "Bar2")
    assert row["default_configuration"] == spec.BAR1
    assert row["configuration_quantities"] == {"Bar1": 1, "Bar2": 1}
    assert spec.CONFIGURATION_QUANTITIES == {"Bar1": 1, "Bar2": 1}
    assert sum(spec.CONFIGURATION_QUANTITIES.values()) == spec.QUANTITY
    assert spec.CONFIGURATION_DESCRIPTIONS == {
        "Bar1": "BASE BAR 1, END BRACKET HOLES",
        "Bar2": "BASE BAR 2, NO BRACKET HOLES",
    }
    # Bar1 alone owns the bracket holes and their row reference.
    assert spec.BRACKET_FEATURES == ("BracketHoles", "BracketRowReference")
    assert spec.CONFIGURATION_FEATURES == {"Bar1": spec.BRACKET_FEATURES, "Bar2": ()}
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
        "SLOT_Y",
        "RISES",
        "CONFIGURATION_DIMENSIONS",
        "FEATURE_STEP_CONFIGURATIONS",
        "configuration_number",
    ):
        assert not hasattr(spec, gone), gone
    # The shared member helpers (_purchased_part_variants) author, select,
    # read back and export each member; no hand-rolled configuration code.
    build = BUILD.read_text(encoding="utf-8")
    assert "create_member_configurations(adapter, PART_NAME, CONFIGURATIONS)" in build
    assert "require_member_configurations(PART_NAME, CONFIGURATIONS)" in build
    assert "select_member_features(adapter, configuration, CONFIGURATION_FEATURES)" in build
    assert "assert_member_suppression(adapter, configuration, CONFIGURATION_FEATURES)" in build
    assert "save_member_part(" in build and "readback=_readback" in build
    assert "save_part_and_images" not in build
    assert "create_configuration(" not in build
    # Members are authored before the first feature, so every feature exists
    # in both; selection then suppresses Bar1's bracket features in Bar2.
    assert build.index("create_member_configurations(") < build.index('("BarLength", BAR_LENGTH)')
    assert build.index("blank_sketch(adapter, \"BracketRowReference\")") < build.index(
        "select_member_features("
    )
    # Each member has its own sheet (drawing-guidelines rule 7: a member is
    # drawn in its own right, never left to a note on another's sheet), every
    # view on it referencing that member; no hand-opposite shorthand.
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert drawing.SHEET_NAMES == ("BAR 1", "BAR 2")
    assert drawing.MEMBER_SHEETS == {"BAR 1": spec.BAR1, "BAR 2": spec.BAR2}
    assert "configure_reference_views(adapter, configuration, [front, end, iso])" in sheet
    assert "configure_reference_views(adapter, part_spec.BAR1" not in sheet
    assert "create_blank_drawing_sheets(adapter, SHEET_NAMES" in sheet
    assert "expected_sheet_names=SHEET_NAMES" in sheet
    assert "expected_redundant_notes=len(SHEET_NAMES)" in sheet
    assert spec.BRACKET_CALLOUT_PROCESS.startswith("BAR 1 ONLY; NONE ON BAR 2\n")
    for token in ('"LH"', '"RH"', "OPPOSITE HAND"):
        assert token not in sheet, token


def test_bar_2_sheet_dimensions_every_feature_it_keeps() -> None:
    """Bar2's sheet marks every dimension but the bracket features' own, each
    where bar 1's sheet puts it; only bar 1's carries the bracket callout."""
    bracket = set().union(*(spec.DRAWING_DIMENSIONS[f] for f in spec.BRACKET_FEATURES))
    assert bracket == {"BracketHole1X", "BracketHole3X", "BracketRow1Y", "BracketRow2Y"}
    assert spec.MEMBER_DRAWING_DIMENSIONS[spec.BAR1] == set(spec.DRAWING_PRECISION_BY_NAME)
    assert spec.MEMBER_DRAWING_DIMENSIONS[spec.BAR2] == (
        set(spec.DRAWING_PRECISION_BY_NAME) - bracket
    )
    assert drawing.member_front_keep(spec.BAR1) == drawing.FRONT_KEEP
    two = drawing.member_front_keep(spec.BAR2)
    assert set(two) == set(drawing.FRONT_KEEP) - bracket
    assert all(two[name] == drawing.FRONT_KEEP[name] for name in two)
    assert set(drawing.END_KEEP) <= spec.MEMBER_DRAWING_DIMENSIONS[spec.BAR2]
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    member = sheet[sheet.index("def _draw_member_sheet") : sheet.index("async def build")]
    assert member.index("if configuration == part_spec.BAR1:") < member.index(
        "label=\"end bracket holes\""
    )
    assert member.count("add_native_hole_callout(") == 2
    assert "if name in names" in member


def test_each_member_exports_its_own_step_and_png() -> None:
    from _part_configuration_exports import configuration_producer_paths, member_configurations

    assert member_configurations(spec.PART_NAME) == spec.CONFIGURATIONS
    paths = configuration_producer_paths(spec.PART_NAME)
    assert tuple(paths) == spec.CONFIGURATIONS
    for configuration, members in paths.items():
        assert set(members) == {"step", "png"}, configuration
        assert members["png"].suffix == ".png", configuration
    # Bar1 is the bare output; Bar2's STEP and PNG are its own.
    assert paths["Bar1"]["png"] != paths["Bar2"]["png"]
    assert paths["Bar1"]["step"] != paths["Bar2"]["step"]


def test_walls_meet_rule_17() -> None:
    # The far slot's wall to the +Y side is the thinner of the two side walls
    # (the rail sits nearer that side).
    assert spec.SIDE_WALL == spec.FAR_SIDE_WALL < spec.NEAR_SIDE_WALL
    # c3-r6, rule 10: both slots from the -Y side, so the far slot's wall to
    # the +Y side carries the milled width's .XX and its rise's and run's;
    # the near end wall the near station's rounding as well.
    xx = printed_band_mm(2, unit="in")
    assert spec.FAR_SIDE_WALL_WORST == pytest.approx(
        spec.BAR_WIDTH
        - xx
        - (spec.FAR_SLOT_RISE + spec.SLOT_RUN + 2 * xx)
        - (spec.SLOT_WIDTH + xx) / 2
    )
    assert spec.SIDE_WALL_WORST == spec.FAR_SIDE_WALL_WORST
    assert min(spec.SIDE_WALL_WORST, spec.NEAR_END_WALL_WORST) >= WALL_TARGET_MM
    # Nominal-model envelope only; actual transferred holes are inspected.
    xx_station = printed_band_mm(2, unit="in")
    tap_r = THREAD_MAJOR_MM[spec.RAIL_SCREW] / 2.0
    far_nominal = spec.BAR_LENGTH - spec.RAIL_HOLE_X[-1] - tap_r
    assert far_nominal / 25.4 == pytest.approx(0.310, abs=5e-4)
    assert spec.RAIL_TAP_END_WALL_WORST == pytest.approx(
        far_nominal - xx_station
    )
    assert spec.RAIL_TAP_END_WALL_WORST < spec.RAIL_HOLE_X[0] - tap_r
    assert spec.RAIL_TAP_END_WALL_WORST >= WALL_TARGET_MM
    assert spec.RAIL_TAP_SLOT_WALL_WORST >= WALL_TARGET_MM
    build = BUILD.read_text(encoding="utf-8")
    assert "high_corner" not in build
    assert "adapter, low_corner, FAR_SLOT_X, FAR_SLOT_Y, FAR_SLOT_RISE" in build


@pytest.mark.parametrize("wall_name", (
    "counterbore_end_wall", "tap_end_wall", "tap_slot_wall", "tap_bracket_wall",
))
@pytest.mark.parametrize("bad_wall", (1.5, float("nan"), float("inf")))
def test_matched_rail_rejects_insufficient_actual_walls(wall_name, bad_wall) -> None:
    walls = dict.fromkeys(
        ("counterbore_end_wall", "tap_end_wall", "tap_slot_wall", "tap_bracket_wall"), 3.0
    )
    spec.require_matched_rail_walls(**walls)
    walls[wall_name] = bad_wall
    with pytest.raises(ValueError, match="matched rail wall"):
        spec.require_matched_rail_walls(**walls)


def test_plan_uses_actual_rail_as_template_not_nominal_stations() -> None:
    plan = (
        Path(__file__).resolve().parents[1] / "process"
        / "ch_rocker_arm_tl_oblique_base_bar" / "plan.toml"
    ).read_text(encoding="utf-8")
    assert "transfer" in plan.lower()
    assert "NOT DRO targets" in plan
    assert "all eight screws enter freely by hand" in plan
    assert "0.080 in" in plan
    assert "+/-0.08" not in plan


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.END_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.END_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert not hasattr(spec, "STOCK_DIMENSIONS")
    assert set(drawing.CALLOUTS_BELOW) <= marked


def test_milled_width_is_accepted_within_the_xx_band() -> None:
    # Owner ruling #2083: the width is milled, so it carries the title
    # block's .XX band like every machined size.
    side = export_features.requirement_manifest(STEM)["features"]["bar_high_side"]
    low, high = side["width"]
    assert (low, high) == pytest.approx(
        (spec.BAR_WIDTH - spec.BAR_WIDTH_BAND, spec.BAR_WIDTH + spec.BAR_WIDTH_BAND)
    )


def test_slot_run_is_centre_to_centre_with_centre_marks() -> None:
    # Rule 12: slots are dimensioned to their radius centres; the marks make
    # the 2X .16 read as centre-to-centre: twice the stud's travel.
    assert spec.SLOT_RUN == pytest.approx(2.0 * trammel.HOLD_DOWN_ADJUST)
    assert drawing.DIMENSION_TEXT["SlotRun"] == ("2X ", "")
    # r5: the slots never said THRU; the width's text says it for both.
    assert drawing.DIMENSION_TEXT["SlotWidth"] == ("2X ", " THRU")
    glyphs = len("".join(drawing.DIMENSION_TEXT["SlotWidth"])) + len(".53")
    assert 2 * drawing._SLOT_WIDTH_TEXT_HALF >= glyphs * 0.0026
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks(adapter, front, holes=False, slots=True" in source
    # The printed run is the far slot's: its dimension lands right of the
    # bar, off the part (rule 14).
    build = BUILD.read_text(encoding="utf-8")
    assert 'dims.record("SlotRun", \'"SlotRun"\')' in build.split("else:")[-1]
    assert drawing.FRONT_KEEP["SlotRun"][0] > drawing._RIGHT


def test_rail_hole_stations_are_matched_references_that_name_the_mate() -> None:
    stations = {f"RailHole{k}X" for k in range(1, 9)}
    assert spec.DRAWING_DIMENSIONS["RailHoles"] == stations
    assert spec.RAIL_REFERENCE_DIMENSIONS == {
        ("RailHoles", name): 3 for name in stations
    }
    assert not any(feature == "RailHoles" for feature, _ in spec.METRIC_DIMENSIONS)
    assert all(spec.DRAWING_PRECISION_BY_NAME[name] == 3 for name in stations)
    assert all(x == round(x, 3) for x in spec.RAIL_HOLE_X)
    rail_number = _config.parts("ch-rocker-arm-tl-vn-oblique-rail-kit")["number"]
    assert drawing.CALLOUTS_BELOW["RailHole8X"] == spec.RAIL_MATE_CALLOUT
    assert spec.RAIL_MATE_CALLOUT == (
        f"MATCHES HGR15 RAIL {rail_number}; ALL 8 SCREWS START BY HAND"
    )
    assert "RECEIVED" not in spec.RAIL_MATE_CALLOUT
    assert "\n" not in spec.RAIL_MATE_CALLOUT
    assert not (stations - {"RailHole8X"}) & set(drawing.CALLOUTS_BELOW)
    # One line at about 2.6 mm a glyph, centred under the 435.00's text, stays
    # between the end face's and hole 8's extension lines, the only lines in
    # that gap.
    half = len(spec.RAIL_MATE_CALLOUT) * 0.0026 / 2.0
    centre = drawing.FRONT_KEEP["RailHole8X"][0]
    assert centre - half >= drawing._LEFT + 0.002
    assert centre + half <= drawing._sheet_x(drawing.FRONT_CENTER, spec.RAIL_HOLE_X[-1]) - 0.002


def test_rail_row_is_located_from_the_faced_low_side() -> None:
    """r2 blocker: the row had no lateral location. It prints 88.90 from the
    -Y edge, a model dimension on a hidden reference sketch, at the title
    block's .XX band (c3-r7, rule 4: nothing mates with the row's height)."""
    assert spec.RAIL_ROW_Y == pytest.approx(88.9)
    assert spec.DRAWING_DIMENSIONS["RailRowReference"] == {"RailRowY"}
    assert ("RailRowReference", "RailRowY") not in spec.METRIC_DIMENSIONS
    assert spec.DRAWING_PRECISION_BY_NAME["RailRowY"] == spec.RAIL_ROW_PLACES == 2
    build = BUILD.read_text(encoding="utf-8")
    # Since the 2026-10-17 widening the row is off the centreline: the row
    # and the profile's origin anchor both read the -Y side's own station.
    assert 'row_station.record("RailRowY", \'"RailRowY"\')' in build
    assert 'names=["BarLength", "BarWidth", "BarLowSide"]' in build
    assert "drives=['\"BarLength\"', '\"BarWidth\"', '\"RailRowY\"']" in build
    assert build.index('blank_sketch(adapter, "RailRowReference")') < build.index(
        "save_member_part("
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
    # arrow's tail (r4: they struck the block's last "L"), and the width's
    # line.
    assert row_x + drawing._RAIL_ROW_TEXT_HALF <= rise_x - 0.0025 + 1e-12
    assert row_x - drawing._RAIL_ROW_TEXT_HALF >= width_x + 0.002
    # The row's three-line block sits inside its span, above the near rise's
    # upper extension line (the 49.4's text rides inside its own span) and
    # clear of the row's upper arrowhead (2026-10-30 machinist review: the
    # arrowhead struck "88.90"); the width's text rides above the row's
    # upper extension line.
    row_line = drawing._sheet_y(drawing.FRONT_CENTER, 0.0)
    rise_top = drawing._sheet_y(
        drawing.FRONT_CENTER, spec.LOW_SIDE_Y + spec.NEAR_SLOT_RISE
    )
    block_low = row_y - drawing._RAIL_ROW_TEXT_HALF_HIGH
    block_high = row_y + drawing._RAIL_ROW_TEXT_HALF_HIGH
    assert block_low >= rise_top + 0.0005
    assert block_high <= row_line - drawing._ROW_ARROW_LENGTH - 0.0005
    assert width_y - 0.0045 > row_line
    assert width_x - drawing._BAR_WIDTH_TEXT_HALF >= 0.0124 + 0.002


def test_rail_row_names_what_it_buys() -> None:
    """r3 blocker: the row's ±0.08 named no mate; c3-r7 dropped the band (the
    slots set the bar's place, one DRO setting lines the holes up). The
    callout keeps the reason, in the station stack's words."""
    assert drawing.CALLOUTS_BELOW["RailRowY"] == spec.RAIL_ROW_CALLOUT
    lines = spec.RAIL_ROW_CALLOUT.split("\n")
    assert lines == ["HOLES IN LINE", "FOR HGR15 RAIL"]
    assert "HGR15" in spec.RAIL_MATE_CALLOUT and "HGR15R" not in spec.RAIL_MATE_CALLOUT
    widest = max(len(line) for line in lines)
    # The lane is sized for the widest line as measured on the r4 sheet,
    # about 2.6 mm a glyph (r1-r3 assumed 2.2 and the block overran).
    assert 2 * drawing._RAIL_ROW_TEXT_HALF >= widest * 0.0026
    # The screw's nominal radial float is not a transfer-tool accuracy claim.
    assert spec.RAIL_SCREW_CLEARANCE > 0.0


def test_tap_callout_has_clear_air_under_the_border() -> None:
    """r3: the callout's first line touched the 267 mm border. Its two lines
    span about 4.8 above and below the keep point."""
    x, y = drawing.TAP_CALLOUT_XY
    assert y + 0.0048 <= 0.267 - 0.004
    # Clear of the station stack's outermost extension line (hole 8).
    hole_8 = drawing._sheet_x(drawing.FRONT_CENTER, spec.RAIL_HOLE_X[-1])
    assert x - 0.022 >= hole_8 + 0.010


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
    # The near slot's station prints left of the end face's extension line:
    # right of the slot's centre line it stood 1.2 short of the near bracket
    # row's extension line, which runs down through its lane once the
    # centred feed block brought that row to 47.484.
    assert keep["NearSlotX"][0] + drawing._NEAR_SLOT_X_TEXT_HALF <= drawing._LEFT - 0.002
    assert keep["NearSlotX"][0] - drawing._NEAR_SLOT_X_TEXT_HALF >= 0.0127 + 0.005
    # Every measured-width text below the plan clears, by 2 or more, every
    # extension line that runs down through or to its lane, wherever the
    # leadscrew layout puts the bracket stations (model x, deepest lane).
    extension_lines = [
        (spec.NEAR_SLOT_X - spec.SLOT_WIDTH / 2.0, 0),
        (spec.NEAR_SLOT_X + spec.SLOT_WIDTH / 2.0, 0),
        (0.0, 5),
        (spec.NEAR_SLOT_X, 1),
        (drawing.BRACKET_NEAR_X, 2),
        (spec.FAR_SLOT_X, 3),
        (drawing.BRACKET_FAR_X, 4),
        (spec.BAR_LENGTH, 5),
    ]
    for lane, (name, half) in enumerate(
        (
            ("SlotWidth", drawing._SLOT_WIDTH_TEXT_HALF),
            ("NearSlotX", drawing._NEAR_SLOT_X_TEXT_HALF),
            ("BracketHole1X", drawing._BRACKET_NEAR_X_TEXT_HALF),
        )
    ):
        left, right = keep[name][0] - half, keep[name][0] + half
        for x, deepest in extension_lines:
            if deepest >= lane:
                line = sx(centre, x)
                assert line <= left - 0.002 or line >= right + 0.002, (name, x)
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
        "BracketHole3X",
        "BarLength",
    )
    lanes = [keep[name][1] - drawing.TEXT_DROP for name in below]
    assert lanes == pytest.approx([drawing._below_line(k) for k in range(6)])
    # c3-r6: the far rise, from the -Y edge, is the tallest right-side
    # dimension, so it takes the outermost lane, past the outermost bracket
    # row's (PR2: the inner row, 54.909), its text above that row's upper
    # extension line (and its overshoot), below the run's text and clear of
    # the end view. c4-r9: its line one stack lane out struck the row text's
    # last "0"; it now clears that text by 1.5.
    rise_x, rise_y = keep["FarSlotRise"]
    outer_row = drawing._BRACKET_ROW_LANES[0]
    assert drawing._BRACKET_ROW_TEXT_HALF >= 0.0139 / 2
    # The 1.5 clearance holds by construction (_FAR_RISE_LANE); compare it
    # as a clearance so float rounding of the sum cannot fail it.
    clearance = rise_x - (drawing._RIGHT + outer_row + drawing._BRACKET_ROW_TEXT_HALF)
    assert clearance >= 0.0015 - 1e-12
    assert rise_x - drawing._RIGHT - outer_row >= drawing.STACK_LANE
    assert all(rise_x > drawing._RIGHT + lane for lane in drawing._BRACKET_ROW_LANES)
    run_text_right = (
        drawing._RIGHT + drawing._SLOT_RUN_LANE + drawing._SLOT_RUN_TEXT_HALF
    )
    assert rise_x > run_text_right
    # 3 of air to the end view: moving the view right instead would push the
    # thickness text, 2.6 inside the right border on the r9 sheet, over it.
    assert (
        rise_x + drawing._FAR_RISE_TEXT_HALF + 0.003
        <= drawing.END_CENTER[0] - spec.BAR_THICK / 4000
    )
    row_top = drawing._sheet_y(centre, drawing.BRACKET_ROW_Y[0])
    assert rise_y - 0.00175 >= row_top + 0.005
    assert rise_y + 0.00175 + 0.005 <= keep["SlotRun"][1] - 0.00175
    assert rise_y < run_low


def test_rail_hole_stack_has_clear_lanes_inside_the_sheet() -> None:
    # c4-r8: with the plan centred at y 0.1725 the seven-lane stack's top
    # block (400.00) printed about 0.4 under the 267 border; the kit rail's
    # eighth lane (#2177) stands one stack lane higher, and the drop keeps 3
    # or more.
    r8_air, r8_centre_y = 0.0004, 0.1725
    extra_lanes = len(spec.RAIL_HOLE_X) - 7
    assert extra_lanes == 1
    assert (
        r8_air
        + (r8_centre_y - drawing.FRONT_CENTER[1])
        - extra_lanes * drawing.STACK_LANE
        >= 0.003
    )
    count = len(spec.RAIL_HOLE_X)
    lines = [drawing._above_line(k) for k in range(count)]
    assert lines[0] - drawing._TOP >= 0.008
    assert all(b - a >= 0.006 - 1e-12 for a, b in zip(lines, lines[1:]))
    keeps = [drawing.FRONT_KEEP[f"RailHole{k}X"] for k in range(1, count + 1)]
    assert [y for _x, y in keeps] == sorted(y for _x, y in keeps)
    # The two-line top block (value + mate) stays under the 267 mm border.
    assert keeps[-1][1] + 0.0046 <= 0.265
    # A station text (15.00 ±0.08 mm, owner ruling 4's mm label) wider than
    # its span with a gap each side stands left of the end face's extension
    # line, above the width's upper extension line along the top edge and
    # inside the left border: the 15 and the 75 (37.5 on the sheet). Every
    # other one stands mid-span, clear of both its extension lines.
    half = drawing._RAIL_HOLE_TEXT_HALF
    left = [
        name
        for name, (x, _y) in zip(range(1, count + 1), keeps, strict=True)
        if x < drawing._LEFT
    ]
    assert left == [1, 2]
    for k, ((x, y), station) in enumerate(zip(keeps, spec.RAIL_HOLE_X), start=1):
        if k in left:
            assert x + half <= drawing._LEFT - 0.002
            assert x - half >= 0.010 + 0.005
            assert y - 0.00175 >= drawing._TOP + 0.002
        else:
            hole = drawing._sheet_x(drawing.FRONT_CENTER, station)
            assert x - half >= drawing._LEFT + 0.002
            assert x + half <= hole - 0.002


def test_end_view_projects_on_the_plans_centreline() -> None:
    """r2: the edge view hung about 45 mm below the plan."""
    assert drawing.END_CENTER[1] == drawing.FRONT_CENTER[1]
    assert drawing.END_CENTER[0] > drawing._RIGHT
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'place_view(adapter, str(SOURCE), "*Right", *END_CENTER' in source


def test_isometric_and_its_note_take_the_free_bottom_left_corner() -> None:
    """C4: the bracket callout takes the bottom right; the 1:5 iso (about
    66 x 62 mm since the 2026-10-17 widening) moves under the plan's stack,
    left of the title block, its note beside it along its foot (the kit
    rail's eighth station lane dropped the plan, #2177)."""
    iso_x, iso_y = drawing.ISO_CENTER
    half_x, half_y = drawing.ISO_HALF
    lowest_text = drawing._below_line(5) + drawing.TEXT_DROP - 0.00175
    # c4-r8: the iso keeps 7 under the length's text.
    assert iso_y + half_y <= lowest_text - 0.007
    assert iso_x - half_x >= 0.0127 + 0.010
    assert iso_y - half_y >= 0.0127 + 0.005
    note_x, note_y = drawing.ISO_NOTE_XY
    note_width = len(spec.ISOMETRIC_VIEW_NOTE) * 0.0026
    assert note_x >= iso_x + half_x + 0.003
    assert note_x + note_width <= 0.216 - 0.010  # the title block's left edge
    # Its foot level with the iso's, under the length's text.
    assert note_y - drawing.ISO_NOTE_HEIGHT == pytest.approx(iso_y - half_y)
    assert note_y <= lowest_text - 0.007


def test_bracket_holes_are_the_leadscrew_layouts() -> None:
    """PR2: four #8 clearance holes (Bar1 only) at the leadscrew spec's
    positions, from its own tuple; counterbored from the underside."""
    # A pair at each KP08 station (derived by the leadscrew layout), on TL-28's
    # two holes at the KP08's 42 mm pitch; the near station moves with the
    # nut, so it is not pinned.
    near_x = leadscrew.BASE_BAR_HOLES[0][0]
    far_x = leadscrew.BASE_BAR_HOLES[-1][0]
    rows = drawing.BRACKET_ROW_Y
    assert len(leadscrew.BASE_BAR_HOLES) == 4 and len(rows) == 2
    assert leadscrew.BASE_BAR_HOLES == tuple(
        (x, y) for x in (near_x, far_x) for y in rows
    )
    assert rows == tuple(-lateral for lateral in leadscrew.BAR_SCREW_LATERALS)
    assert rows[0] - rows[1] == pytest.approx(leadscrew.KP08_BOLT_SPACING)
    # The rows derive from the KP08's metric span: exact millimetres at three
    # places from the -Y edge (54.909, 12.909) with the stations' band; the
    # two stations print exact millimetres with their own band (owner ruling 4).
    assert [y - spec.LOW_SIDE_Y for y in rows] == pytest.approx([54.909, 12.909])
    for y in rows:
        edge = y - spec.LOW_SIDE_Y
        assert edge == pytest.approx(round(edge, spec.BRACKET_ROW_PLACES), abs=1e-9)
    # Each station prints at its places from the unrounded model centre; the
    # printed limits charge the rounding on top of the band (the near
    # station, 47.484 since the centred feed block, prints 47.48).
    places = spec.BRACKET_STATION_PLACES
    band = spec.BRACKET_STATION_BAND
    for x in (near_x, far_x):
        rounding = abs(x - round(x, places))
        assert rounding <= 0.5 * 10.0**-places + 1e-12
        low, high = printed_deviations(x, places, (-band, band), unit="mm")
        assert max(-low, high) == pytest.approx(band + rounding, abs=1e-12)
    assert spec.METRIC_DIMENSIONS[("BracketHoles", "BracketHole1X")] == (
        2,
        spec.BRACKET_STATION_BAND,
    )
    for row in (1, 2):
        assert spec.METRIC_DIMENSIONS[("BracketRowReference", f"BracketRow{row}Y")] == (
            3,
            spec.BRACKET_ROW_BAND,
        )
    assert spec.BRACKET_STATION_BAND == spec.BRACKET_ROW_BAND
    assert spec.BRACKET_STATION_BAND == printed_band_mm(3, unit="mm") == 0.13
    assert drawing.BRACKET_HOLES is leadscrew.BASE_BAR_HOLES
    hole = spec.BRACKET_HOLE_SPEC
    wanted = leadscrew.BASE_BAR_HOLE_SPEC
    assert (hole.kind, hole.size, hole.end, hole.fit) == (
        wanted.kind,
        wanted.size,
        wanted.end,
        wanted.fit,
    )
    # A #12 drill (.189): its worst-case float holds TL-28's reversal lost
    # motion under the owner's ~.9 mm (leadscrew LOAD_CASES).
    assert spec.BRACKET_HOLE_DRILL == "#12"
    assert spec.BRACKET_HOLE_DIA == NUMBER_DRILL_MM["#12"] == pytest.approx(0.189 * 25.4, abs=1e-3)
    assert CLEARANCE_MM[("#8", "close")] < spec.BRACKET_HOLE_DIA < CLEARANCE_MM[("#8", "normal")]
    assert hole.overrides_mm["HoleDiameter"] == spec.BRACKET_HOLE_DIA
    source = BUILD.read_text(encoding="utf-8")
    assert "leadscrew.BASE_BAR_HOLES" in source
    assert "[[x, y, 0.0] for x, y in BRACKET_HOLES]" in source
    assert "(0.0, 0.0, -1.0)" in source
    assert 'blank_sketch(adapter, "BracketRowReference")' in source


def test_bracket_counterbores_sink_and_seat_the_heads() -> None:
    assert spec.BRACKET_SCREW_HEAD_DIA == pytest.approx(6.858)
    assert spec.BRACKET_SCREW_HEAD_HEIGHT == pytest.approx(leadscrew.SHCS_8_HEAD)
    # The head sinks, clears the counterbore and bears on its floor at the
    # printed bands; the floor keeps rule 17's target.
    assert spec.BRACKET_HEAD_RECESS_MIN >= 0.1
    assert spec.BRACKET_HEAD_CLEARANCE_MIN >= 0.25
    assert spec.BRACKET_HEAD_BEARING_MIN >= 0.5
    assert spec.BRACKET_CBORE_FLOOR_MIN >= WALL_TARGET_MM
    # Rule 18: the common #8-32 x 3/4 reaches 1.5 D into TL-28 at the printed
    # worst (the faced .47 bar at its .XX band), and never through the 1 in
    # bracket; its deepest reach is TL-28's bar-thread window floor.
    assert leadscrew.BAR_SCREW_LENGTH_MM == pytest.approx(0.75 * 25.4)
    low, high = spec.bracket_screw_under_head(leadscrew.BAR_SCREW_LENGTH_MM)
    assert low >= 1.5 * THREAD_MAJOR_MM[leadscrew.BAR_SCREW]
    assert high < leadscrew.BRACKET_THICK
    assert (low, high) == pytest.approx(leadscrew.BAR_SCREW_ENGAGEMENT_RANGE)


def test_bracket_hole_float_bounds_the_lost_motion_on_reversal() -> None:
    """Owner ruling Main 2026-11-06 (option B): TL-28 may slip onto its bar
    screws' positive stop above ~1344 N; up to ~.9 mm reversal lost motion.
    The worst case is the largest drilled hole over the #8 UNC-3A minimum
    major; the basic-major figure is disclosed beside it."""
    hole_max = spec.BRACKET_HOLE_DIA + drilled_oversize_mm(unit=spec.UNIT)
    assert spec.BRACKET_SCREW_FLOAT_MAX == pytest.approx(
        (hole_max - THREAD_MAJOR_MM[leadscrew.BAR_SCREW]) / 2.0
    )
    # ASME B1.1 class 3A #8-32 minimum major.
    assert leadscrew.SHCS_8_MAJOR_MIN == pytest.approx(0.1585 * 25.4)
    assert leadscrew.BRACKET_STOP_FLOAT_MAX == pytest.approx(
        (hole_max - leadscrew.SHCS_8_MAJOR_MIN) / 2.0
    )
    assert leadscrew.BRACKET_REVERSAL_LOST_MOTION_BASIC == pytest.approx(
        2.0 * spec.BRACKET_SCREW_FLOAT_MAX
    )
    assert leadscrew.BRACKET_REVERSAL_LOST_MOTION == pytest.approx(
        2.0 * leadscrew.BRACKET_STOP_FLOAT_MAX
    )
    assert leadscrew.BRACKET_REVERSAL_LOST_MOTION_ACCEPTED == 0.9
    assert (
        leadscrew.BRACKET_REVERSAL_LOST_MOTION
        <= leadscrew.BRACKET_REVERSAL_LOST_MOTION_ACCEPTED
    )
    # One source: the base bar owns the screw's least major and its travel.
    assert leadscrew.SHCS_8_MAJOR_MIN == spec.BRACKET_SCREW_MAJOR_MIN
    assert leadscrew.BRACKET_STOP_FLOAT_MAX == spec.BRACKET_SCREW_FLOAT_WORST


def test_counterbore_three_places_hold_the_head_float_and_the_screw_reach() -> None:
    """Machinist review 84d5991d45: ⌴ Ø.313 ↧ .189 at .XXX with no stated
    function. Both sizes hold a load-path control, so they keep ±.005 and
    the callout names each; the review's .31/.19 at ±.01 breaks both."""
    head = spec.BRACKET_SCREW_HEAD_DIA  # .270, ASME B18.3 max
    hole_max = spec.BRACKET_HOLE_DIA + drilled_oversize_mm(unit=spec.UNIT)
    travel = (hole_max - 0.1585 * 25.4) / 2.0  # the 3A screw's whole float
    assert spec.BRACKET_SCREW_FLOAT_WORST == pytest.approx(travel)
    assert travel == pytest.approx(0.438, abs=1e-3)
    three = printed_band_mm(3, unit=spec.UNIT)  # .005
    two = printed_band_mm(2, unit=spec.UNIT)  # .01
    # Diameter: at .313 ±.005 the head keeps 0.483 a side to the wall, more
    # than the screw's travel, so the thread is TL-28's stop. At .31 ±.01 the
    # .300 bore leaves 0.381: the head bears first.
    clearance = (spec.BRACKET_CBORE_DIA - three - head) / 2.0
    assert spec.BRACKET_HEAD_FLOAT_CLEARANCE_MIN == pytest.approx(clearance)
    assert clearance >= travel
    assert (0.31 * 25.4 - two - head) / 2.0 < travel
    # Depth: .189 ±.005 lets the 3/4 screw reach at most 12.294 past the
    # bar's top, inside TL-28's bottom thread and short of the top thread's
    # tap lead; .19 ±.01 lets it reach 12.446, past both.
    screw = leadscrew.BAR_SCREW_LENGTH_MM
    reach_max = spec.bracket_screw_under_head(screw)[1]
    assert reach_max == pytest.approx(end_bracket.BAR_REACH_MAX)
    two_place = screw - (
        spec.BAR_THICK - printed_band_mm(spec.THICK_PLACES, unit=spec.UNIT)
        - (0.19 * 25.4 + two)
    )
    assert two_place == pytest.approx(12.446, abs=1e-3)
    assert reach_max <= end_bracket.BAR_THREAD_LIMITS[0]
    assert two_place > end_bracket.BAR_THREAD_LIMITS[0]
    assert (
        end_bracket.THICK_MIN - two_place - end_bracket.TAP_LEAD
        < end_bracket.KP08_THREAD_LIMITS[1]
    )
    # The callout names both functions, right above the counterbore's row.
    lines = spec.BRACKET_CALLOUT_PROCESS.split("\n")
    assert lines[-3:] == ["HEAD CLEAR AT FULL FLOAT", "DEPTH SETS SCREW REACH", ""]
    assert set(spec.BRACKET_CALLOUT_PRECISION.values()) == {3}


def test_bracket_hole_walls_meet_rule_17() -> None:
    holes = leadscrew.BASE_BAR_HOLES
    walls = spec.bracket_hole_walls(holes)
    # Each counterbore at its printed largest.
    radius = spec.BRACKET_CBORE_RADIUS_MAX
    assert radius == pytest.approx(
        (
            spec.BRACKET_CBORE_DIA
            + printed_band_mm(spec.BRACKET_CBORE_PLACES, unit=spec.UNIT)
        )
        / 2.0
    )

    def off(value: float, places: int, band: float) -> float:
        """The farthest a centre may sit from its unrounded model value: the
        band about the printed (rounded) value, plus the rounding."""
        return band + abs(value - round(value, places))

    station_places, station_band = spec.BRACKET_STATION_PLACES, spec.BRACKET_STATION_BAND
    row_places, row_band = spec.BRACKET_ROW_PLACES, spec.BRACKET_ROW_BAND
    # The end and edge walls from the unrounded model centres at their
    # printed limits, the rounding charged.
    assert walls["spindle end"] == pytest.approx(
        min(x - off(x, station_places, station_band) for x, _ in holes) - radius
    )
    assert walls["-Y edge"] == pytest.approx(
        min(
            (y - spec.LOW_SIDE_Y) - off(y - spec.LOW_SIDE_Y, row_places, row_band)
            for _, y in holes
        )
        - radius
    )
    # Rule 17: every wall clears the .080 target at its printed worst.
    assert set(walls) == {
        "-Y edge",
        "+Y edge",
        "spindle end",
        "far end",
        "neighbour counterbore",
        "rail tap",
        "hold-down slot",
    }
    for name, wall in walls.items():
        assert wall >= WALL_TARGET_MM, name
    assert spec.BRACKET_WALL_MIN == WALL_FLOOR_MM


def test_bracket_pattern_holds_the_tl28_float_and_names_it() -> None:
    """Rows and stations at exact millimetres with ±0.13 mm: the pair's
    spacing change at the printed limits stays inside the screw float the
    TL-28 pair leaves; the tight band names its mate, and the plan, looking
    at the top, says the counterbores are on the far side and bar 2 has none."""
    assert spec.bracket_pair_spacing_error(leadscrew.BASE_BAR_HOLES) == pytest.approx(
        0.261, abs=1e-3
    )
    # The whole-millimetre KP08 stations print two places under their
    # explicit ±0.13 mm band; the rows three.
    for name in ("BracketHole1X", "BracketHole3X"):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 2
    for name in ("BracketRow1Y", "BracketRow2Y"):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == spec.BRACKET_ROW_PLACES == 3
    lines = spec.BRACKET_CALLOUT_PROCESS.split("\n")
    assert lines == [
        "BAR 1 ONLY; NONE ON BAR 2",
        "MATCHES MHA-CH-06-TL-28",
        "DRILL, C'BORE FAR SIDE",
        "HEAD CLEAR AT FULL FLOAT",
        "DEPTH SETS SCREW REACH",
        "",
    ]
    assert "MHA-CH-06-TL-28" == spec.BRACKET_MATE
    # Every Hole Wizard length prints .XXX (#290).
    assert set(spec.BRACKET_CALLOUT_PRECISION.values()) == {3}
    # Rule 12: the size and a process word, no screw in the place of a size;
    # plain physical facts, no rule or ruling words.
    assert "SHCS" not in spec.BRACKET_CALLOUT_PROCESS
    assert "RULING" not in spec.BRACKET_CALLOUT_PROCESS


def test_bracket_dimensions_and_callout_lay_out_clear() -> None:
    keep = drawing.FRONT_KEEP
    sx = drawing._sheet_x
    centre = drawing.FRONT_CENTER
    # The near station's text (its metric station and band) is wider than its span, so it
    # sits right of its own extension line, short of the far slot's.
    near_text = keep["BracketHole1X"][0]
    near_station = sx(centre, drawing.BRACKET_NEAR_X)
    assert near_text - drawing._BRACKET_NEAR_X_TEXT_HALF >= near_station + 0.002
    assert (
        near_text + drawing._BRACKET_NEAR_X_TEXT_HALF
        <= sx(centre, spec.FAR_SLOT_X) - 0.002
    )
    # Right lanes: the outer row (12.909) nearest, its keep on its own line
    # (SolidWorks shoulders the text right of the line under the bar's edge);
    # the inner row (54.909) a text gap and a half-text further out,
    # mid-span; the far rise outside it.
    inner_x, inner_y = keep["BracketRow1Y"]
    outer_x, outer_y = keep["BracketRow2Y"]
    half = drawing._BRACKET_ROW_TEXT_HALF
    outer_line = drawing._RIGHT + drawing._BRACKET_OUTER_LANE
    inner_line = drawing._RIGHT + drawing._BRACKET_INNER_LANE
    assert drawing._RIGHT < outer_line < inner_line < keep["FarSlotRise"][0]
    assert inner_x == pytest.approx(inner_line)
    assert outer_x == pytest.approx(outer_line)
    assert outer_y + 0.00175 <= drawing._BOTTOM - 0.002  # under the bar's edge
    # Machinist review 0c3ed35988: a keep a half-text right of the lane put
    # the outer line on the inner row's x, its arrowhead in the 54.909's "±".
    # The outer line and its arrowheads stay a text gap left of that text.
    assert inner_x - half >= outer_x + drawing._TEXT_GAP - 1e-9
    assert keep["FarSlotRise"][0] - inner_x >= half + 0.0015 - 1e-9
    # The shouldered outer text ends short of the end view.
    end_left = drawing.END_CENTER[0] - spec.BAR_THICK / 4000
    assert outer_x + drawing._TEXT_GAP + 2 * half <= end_left - 0.005
    # The inner row's text stands above the outer row's extension line.
    outer_top = drawing._sheet_y(centre, drawing.BRACKET_ROW_Y[1])
    assert inner_y - 0.00175 >= outer_top + 0.002
    assert inner_x + half <= drawing.END_CENTER[0] - spec.BAR_THICK / 4000 - 0.005
    # The leader leaves the far outer hole down and right; at the length's
    # extension line (x _RIGHT) it is under the bar, and it passes under the
    # outer row's text.
    hole = (
        sx(centre, drawing.BRACKET_FAR_X),
        drawing._sheet_y(centre, drawing.BRACKET_OUTER_Y),
    )
    cx, cy = drawing.BRACKET_CALLOUT_XY
    # Five rows measured 0.025 tall under the 23-glyph "MATCHES
    # MHA-CH-06-TL-28"; the counterbore's two function rows make seven, the
    # widest "HEAD CLEAR AT FULL FLOAT" (24 glyphs).
    rows = 2 + len(spec.BRACKET_CALLOUT_PROCESS.rstrip("\n").split("\n"))
    assert rows == 7
    widest = max(len(line) for line in spec.BRACKET_CALLOUT_PROCESS.split("\n"))
    half_w, half_h = 0.027 * max(widest, 23) / 23, 0.0125 * rows / 5
    land = (cx - half_w, cy)
    slope = (land[1] - hole[1]) / (land[0] - hole[0])
    at_right = hole[1] + slope * (drawing._RIGHT - hole[0])
    assert at_right < drawing._BOTTOM - 0.002
    # Through the outer text's height the leader runs 5 left of the outer
    # line, so left of the text shouldered right of it.
    for y in (outer_y + 0.00175, outer_y - 0.00175):
        assert hole[0] + (y - hole[1]) / slope <= outer_x - 0.005
    # The block: under the end view, above the title block, inside the border.
    assert cy + half_h <= drawing.END_CENTER[1] - drawing._HALF_W_SHEET - 0.010
    assert cy - half_h >= 0.0657 + 0.010
    assert land[0] >= drawing._RIGHT + 0.005
    assert cx + half_w <= 0.4194 - 0.005


def test_each_sheet_names_its_member_and_quantity() -> None:
    """Machinist review 0c3ed35988: both sheets printed the one Number and no
    member. One part number with named configurations stays (coordinator
    ruling, not the review's separate numbers): each sheet's note prints its
    member's Description and quantity, plain physical words."""
    assert drawing.member_note(spec.BAR1) == "BASE BAR 1, END BRACKET HOLES\nQTY 1"
    assert drawing.member_note(spec.BAR2) == "BASE BAR 2, NO BRACKET HOLES\nQTY 1"
    assert sum(spec.CONFIGURATION_QUANTITIES.values()) == spec.QUANTITY
    notes = [drawing.member_note(name) for name in spec.CONFIGURATIONS]
    assert all("RUL" not in note and "REVIEW" not in note for note in notes)
    lines = [line for note in notes for line in note.split("\n")]
    assert all(len(note.split("\n")) == drawing.MEMBER_NOTE_LINES for note in notes)
    # Right of the iso, 3 above its note, 10 left of the title block (x 216)
    # at 2.6 a glyph, and under the plan's lowest stack line.
    x, top = drawing.MEMBER_NOTE_XY
    foot = top - drawing.MEMBER_NOTE_LINES * drawing.ISO_NOTE_HEIGHT - 0.0015
    assert foot >= drawing.ISO_NOTE_XY[1] + 0.003 - 1e-12
    assert x >= drawing.ISO_CENTER[0] + drawing.ISO_HALF[0] + 0.005 - 1e-12
    assert x + 0.0026 * max(map(len, lines)) <= 0.216 - 0.010
    assert top <= drawing._below_line(5) - 0.010
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "member_note(configuration), MEMBER_NOTE_XY" in sheet


class _CentreMark:
    def __init__(self, dangling: bool) -> None:
        self.dangling = dangling
        self.selected: tuple[bool, int] | None = None

    def IsDangling(self) -> bool:
        return self.dangling

    def Select2(self, append: bool, mark: int) -> bool:
        self.selected = (append, mark)
        return True


class _MarkedView:
    def __init__(self, marks: list[_CentreMark]) -> None:
        self.marks = marks

    def GetAnnotationsByType(self, kind: int) -> tuple[_CentreMark, ...]:
        assert kind == 13  # swCenterMarkSym
        return tuple(self.marks)


class _MarkDrawing:
    def __init__(self, view: _MarkedView, *, deletes: bool = True) -> None:
        self.view = view
        self.deletes = deletes

    def ClearSelection2(self, _all: bool) -> None:
        pass

    def EditDelete(self) -> None:
        if self.deletes:
            self.view.marks = [m for m in self.view.marks if m.selected is None]


def test_plan_deletes_only_its_dangling_centre_marks(monkeypatch) -> None:
    """Machinist review 0c3ed35988: the Bar2 plan printed four orphan centre
    marks at Bar1's bracket holes (dangling: Bar2 suppresses those holes).
    The plan deletes exactly its dangling marks after inserting its own, and
    a mark that survives the delete fails the sheet."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    rebuilt: list[str] = []
    monkeypatch.setattr(
        drawing, "rebuild_drawing", lambda _adapter, *, label: rebuilt.append(label)
    )
    kept = [_CentreMark(False), _CentreMark(False)]
    orphans = [_CentreMark(True) for _ in range(4)]
    view = _MarkedView([kept[0], *orphans, kept[1]])
    adapter = type("Adapter", (), {"currentModel": _MarkDrawing(view)})()
    drawing._delete_dangling_center_marks(adapter, view, label="plan")
    assert view.marks == kept
    assert [m.selected for m in orphans] == [(False, 0)] + [(True, 0)] * 3
    assert all(m.selected is None for m in kept)
    assert rebuilt == ["delete dangling plan centre marks"]
    # Bar 1's plan: nothing dangles, nothing is deleted or rebuilt.
    drawing._delete_dangling_center_marks(adapter, view, label="plan")
    assert view.marks == kept and len(rebuilt) == 1
    # A dangling mark the delete leaves behind raises.
    stuck = _MarkedView([_CentreMark(True)])
    adapter = type("Adapter", (), {"currentModel": _MarkDrawing(stuck, deletes=False)})()
    with pytest.raises(RuntimeError, match="keeps a dangling centre mark"):
        drawing._delete_dangling_center_marks(adapter, stuck, label="plan")
    # The plan runs it after both of its own centre-mark insertions.
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    body = sheet[sheet.index("def _draw_member_sheet") :]
    assert body.index("slots=True") < body.index(
        '_delete_dangling_center_marks(adapter, front, label="plan")'
    )


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-base-bar")["number"]
    assert number == "MHA-CH-06-TL-20"
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_material_names_the_aluminium_flat_bar_family() -> None:
    # Machinist review ENFORCE (rule 2): only the holes and slots need the
    # metal, so the title block names the family; the spec row keeps the owned
    # 6061-T6511 bar as the example source.
    row = _config.parts("ch-rocker-arm-tl-oblique-base-bar")
    assert row["material"].startswith("ALUMINUM FLAT BAR")
    assert "6061" not in row["material"]
    assert "6061-T6511" in row["material_specification"]


def test_places_are_model_authored_and_the_sheet_is_pure() -> None:
    script = Path(drawing.__file__)
    assert script.name in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    assert not _drawing_contract.drawing_specification_violations(
        script.read_text(encoding="utf-8"), filename=script.name
    )


def test_metric_vendor_stations_are_model_authored_in_mm() -> None:
    """Owner ruling 4 (2026-11-01, option B): the HGR15 rail's and KP08's
    stations print exact millimetres, labelled mm: the part authors them, the
    sheet proves they survived the import."""
    assert set(spec.METRIC_DIMENSIONS) == {
        ("BracketHoles", "BracketHole1X"),
        ("BracketHoles", "BracketHole3X"),
        ("BracketRowReference", "BracketRow1Y"),
        ("BracketRowReference", "BracketRow2Y"),
    }
    for (_feature, name), (places, _band) in spec.METRIC_DIMENSIONS.items():
        assert spec.DRAWING_PRECISION_BY_NAME[name] == places
    build = BUILD.read_text(encoding="utf-8")
    assert "set_metric_vendor_units(" in build
    assert "METRIC_DIMENSIONS.items()" in build
    assert "TOLERANCES" not in build
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "print_imported_metric_dimensions(" in sheet


class _Display:
    def __init__(self, places: int) -> None:
        self.doc_units, self.places, self.calls = True, places, []
        self.texts = {1: "", 2: " mm"}

    def GetUseDocUnits(self):
        return self.doc_units

    def GetUnits(self):
        return -1 if self.doc_units else 0

    def GetPrimaryPrecision2(self):
        return self.places

    def GetText(self, part):
        return self.texts.get(part, "")

    def SetText(self, part, text):
        self.calls.append(f"SetText{part}")
        self.texts[part] = text  # Native setter replaces this entire text part.

    def SetUnits2(self, use_doc, *_args):
        self.calls.append("SetUnits2")
        self.doc_units = use_doc
        return 0

    def SetPrecision3(self, places, *_args):
        self.calls.append("SetPrecision3")
        self.places = places
        return 0


class _Annotation:
    def __init__(self, name: str, display: _Display) -> None:
        self.name, self.display = name, display

    def GetSpecificAnnotation(self):
        return self.display


def test_metric_sheet_sets_units_but_never_rewrites_model_precision(
    monkeypatch,
) -> None:
    import _drawing_metric_vendor as metric

    monkeypatch.setattr(metric, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(metric, "_annotation_name", lambda _adapter, ann: ann.name)
    good = _Display(2)
    metric.print_imported_metric_dimensions(
        None, [_Annotation("RailHole1X", good)], {"RailHole1X": 2}
    )
    assert good.calls == ["SetUnits2"]
    # A wrong imported precision is detected, not repaired.
    bad = _Display(3)
    with pytest.raises(RuntimeError, match="arrived at 3 places"):
        metric.print_imported_metric_dimensions(
            None, [_Annotation("RailHole1X", bad)], {"RailHole1X": 2}
        )
    assert bad.calls == []


def test_metric_reference_is_authored_with_units_inside_parentheses(monkeypatch) -> None:
    import _drawing_metric_vendor as metric
    import _metric_vendor_dimension as model

    native_dimension = object()
    display = _Display(3)
    monkeypatch.setattr(model, "_named_dimension", lambda *_args: (display, native_dimension))
    monkeypatch.setattr(model, "_early_bound", lambda obj, _iface: obj)
    model.set_metric_vendor_units(
        None, "RailHoles", "RailHole1X", places=3, presentation="reference"
    )
    assert display.texts == {1: "(", 2: " mm)"}
    assert display.places == 3
    model_text = dict(display.texts)
    display.calls.clear()
    display.doc_units = True  # The inch drawing import adopts document units.
    monkeypatch.setattr(metric, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(metric, "_annotation_name", lambda _adapter, ann: ann.name)
    metric.print_imported_metric_dimensions(
        None, [_Annotation("RailHole1X", display)], {"RailHole1X": 3},
        references={"RailHole1X"},
    )
    assert display.calls == ["SetUnits2"]  # No drawing-side text or precision repair.
    assert display.texts == model_text
    # The old generic REF formatter replaced the same native suffix with ")".
    display.SetText(2, ")")
    with pytest.raises(RuntimeError, match="does not print millimetres"):
        metric.print_imported_metric_dimensions(
            None, [_Annotation("RailHole1X", display)], {"RailHole1X": 3},
            references={"RailHole1X"},
        )


@pytest.mark.parametrize("prefix,suffix", (("", " mm)"), ("(", " mm"), ("(", ")")))
def test_metric_reference_requires_both_parentheses_and_unit(monkeypatch, prefix, suffix) -> None:
    import _drawing_metric_vendor as metric

    display = _Display(3)
    display.texts = {1: prefix, 2: suffix}
    monkeypatch.setattr(metric, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(metric, "_annotation_name", lambda _adapter, ann: ann.name)
    with pytest.raises(RuntimeError, match="does not print millimetres"):
        metric.print_imported_metric_dimensions(
            None, [_Annotation("RailHole1X", display)], {"RailHole1X": 3},
            references={"RailHole1X"},
        )


def test_base_bar_reference_text_is_owned_by_the_model() -> None:
    build = BUILD.read_text(encoding="utf-8")
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'presentation="reference"' in build
    assert 'references=DRAWING_DIMENSIONS["RailHoles"]' in sheet
    assert "set_reference_dimensions(" not in sheet


def test_notes_follow_the_simplicity_policy() -> None:
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert "REFERENCE" not in spec.DRAWING_NOTES
    assert not re.search(r"\d", spec.SEAT_FINISH_REASON)


def test_both_faced_seats_carry_the_part_owned_seat_finish() -> None:
    """Owner ruling 2026-10-30: both large faces are static locating seats
    (rule 6, Ra 3.2), the table under one bar and the rail on the other, so
    the part owns both controls, authors them on the model and the sheet
    places each from its control, under the one reason."""
    by_key = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(by_key) == {"top_seat", "underside_seat"}
    assert all(control.roughness_um == SEAT_UM for control in by_key.values())
    assert by_key["top_seat"].face == PlanarFace((0.0, 0.0, 1.0), spec.BAR_THICK)
    assert by_key["underside_seat"].face == PlanarFace((0.0, 0.0, -1.0), 0.0)
    build = "".join(BUILD.read_text(encoding="utf-8").split())
    assert "author_part_pmi(adapter,surface_finishes=SURFACE_FINISHES)" in build
    assert build.index("author_part_pmi(") < build.index("save_member_part(")
    # The member PNGs hide the PMI (it floated past the image border); the
    # saved part keeps it for the drawing.
    assert "hide_model_annotations=True" in build
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert sheet.count("add_surface_finish(") == 1  # one loop over both seats
    assert "surface_finish_by_key(SURFACE_FINISHES, key)" in sheet
    assert "roughness_ra=" not in sheet
    assert spec.SEAT_FINISH_REASON == "TABLE AND RAIL SEATS"


def test_seat_symbols_stand_above_the_end_view_outboard_of_their_edges() -> None:
    top_x, top_y = drawing.TOP_SEAT_FINISH_XY
    under_x, under_y = drawing.UNDERSIDE_SEAT_FINISH_XY
    half_thick = spec.BAR_THICK * drawing._S / 2000.0
    # The *Right view puts model +Z (the top) at the sheet's left.
    assert top_x < drawing.END_CENTER[0] - half_thick
    assert under_x > drawing.END_CENTER[0] + half_thick
    end_top = drawing.END_CENTER[1] + drawing._HALF_W_SHEET
    assert min(top_y, under_y) > end_top
    # Clear of the far rise's dimension line and under the reason, which
    # stays under the tap callout's block and inside the right border.
    assert top_x > drawing._RIGHT + drawing._FAR_RISE_LANE
    reason_x, reason_y = drawing.SEAT_REASON_XY
    assert reason_y - 0.0035 > max(top_y, under_y)
    assert reason_y + 0.002 <= drawing.TAP_CALLOUT_XY[1] - 0.0048
    assert reason_x + 2 * drawing._SEAT_REASON_HALF <= 0.4191 - 0.005


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
