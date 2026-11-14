"""Offline contract of the DT6-FORM1 fly-cutter bar (MHA-DT-37-TL-02, #2358)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _buildgraph as bg
import _config
import draw_dt_cone_tip_gear_tl_cutter_bar as drawing
import dt_cone_tip_gear_spec as tip
import dt_cone_tip_gear_tl_cutter_bar_spec as part
import dt_cone_tip_gear_tl_form_cutter_spec as bit
import sh_vn_arbor_set_screw_spec as set_screw
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_deviations import deviations
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _machinist_review_mode import MachinistReviewMode

SHEET_INNER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0, 0.4318, 0.066)


def test_the_bar_is_registered_tooling_of_the_tip_gear() -> None:
    row = _config.parts(part.STEM)
    assert row["number"] == part.NUMBER == f"{tip.PART_NUMBER}-TL-02"
    assert bg.is_shop_fixture(part.STEM.replace("-", "_"))
    spec = DRAWINGS_BY_NAME["dt_cone_tip_gear_tl_cutter_bar"]
    assert spec.script.name == Path(drawing.__file__).name


def test_the_cross_hole_is_a_slip_fit_on_the_bit_as_supplied() -> None:
    hole = tuple(
        sorted(part.CROSS_HOLE_DIA + d for d in deviations(part.CROSS_HOLE_BAND))
    )
    assert hole == pytest.approx(part.CROSS_HOLE_LIMITS)
    least = hole[0] - bit.BIT_DIA_LIMITS[1]
    most = hole[1] - bit.BIT_DIA_LIMITS[0]
    # Never an interference; at worst a few tenths loose, which the set screw
    # takes up.
    assert 0.0 <= least < most <= 0.0762


def test_the_tap_runs_into_the_cross_hole_leaving_no_web() -> None:
    """The set screw clamps the bit in the cross hole, so the tap is a native
    up-to-next hole: drill and thread both end in the hole, no blind depth."""
    spec = part.SET_SCREW_HOLE_SPEC
    assert (spec.kind, spec.size, spec.end) == (
        "tapped",
        set_screw.THREAD,
        "through_next",
    )
    assert not spec.depth_mm and not spec.overrides_mm
    assert part.TAP_DRILL_DIA < part.CROSS_HOLE_DIA
    assert part.TAP_LENGTH < part.CROSS_HOLE_STATION


def test_the_set_screw_keeps_full_thread_and_meets_the_bit() -> None:
    assert part.SET_SCREW_THREAD == set_screw.THREAD
    assert part.TAP_DRILL_DIA == TAP_DRILL_MM[set_screw.THREAD]
    one_and_half_d = 1.5 * THREAD_MAJOR_MM[set_screw.THREAD]
    assert part.TAP_LENGTH >= one_and_half_d
    # Its tip reaches the bit's top with its socket face near the end face;
    # across the station's .XX band it keeps 1.5D of thread below the hole's
    # lowest wall: proudest at the shortest, sunk at the longest.
    assert part.CROSS_HOLE_STATION_TOL == pytest.approx(0.254)
    assert abs(part.SET_SCREW_PROUD) <= 0.1
    tol = part.CROSS_HOLE_STATION_TOL
    for station in (part.CROSS_HOLE_STATION - tol, part.CROSS_HOLE_STATION + tol):
        cup = station - bit.BIT_RADIUS
        socket = cup - set_screw.LENGTH
        thread_end = station - part.CROSS_HOLE_LIMITS[1] / 2.0
        engaged = min(cup, thread_end) - max(socket, 0.0)
        assert part.set_screw_engaged(station) == pytest.approx(engaged)
        assert engaged >= part.SET_SCREW_ENGAGED_MIN - 1e-9
    assert part.SET_SCREW_ENGAGED_MIN >= one_and_half_d


def test_the_tap_drill_volume_oracle_is_bounded_by_its_cylinders() -> None:
    # The hole's wall stands lowest on the axis and highest at the drill's
    # edge (TAP_LENGTH), so the drill's volume lies between those cylinders.
    area = math.pi * (part.TAP_DRILL_DIA / 2.0) ** 2
    low = area * (part.CROSS_HOLE_STATION - part.CROSS_HOLE_DIA / 2.0)
    high = area * part.TAP_LENGTH
    assert low < part.tap_drill_volume_mm3() < high
    assert part.tap_drill_volume_mm3(800) == pytest.approx(
        part.tap_drill_volume_mm3(), rel=1e-4
    )


def test_the_walls_around_the_cross_hole_hold() -> None:
    assert min(part.CROSS_HOLE_SIDE_WALL, part.CROSS_HOLE_END_WALL) >= 2.032


def test_the_sheet_prints_each_marked_dimension_once_inside_the_border() -> None:
    keeps = {**drawing.FRONT_KEEP, **drawing.TOP_KEEP}
    assert set(keeps) == drawing.sheet_dimension_names()
    assert set(part.DRAWING_PRECISION_BY_NAME) == set(keeps)
    left, bottom, right, top = SHEET_INNER
    for name, (x, y) in {
        **keeps,
        "tap callout": drawing.TAP_CALLOUT_XY,
        "iso note": drawing.ISO_NOTE_XY,
    }.items():
        assert left < x < right and bottom < y < top, name
        assert not (TITLE_BLOCK[0] < x and y < TITLE_BLOCK[3]), name
    assert set(part.DIMENSION_CALLOUTS) <= set(keeps)
    # The bar's collet end stays inside the sheet, left of the cutting end.
    assert drawing.FRONT_ORIGIN[0] - part.BAR_LENGTH * drawing._S > left


def test_the_views_read_like_the_lathe_and_project_third_angle() -> None:
    """Rule 11: every orthographic view lays the axis horizontal, the faced,
    tapped end on the right; the top view (from +X) stands above the front
    view, the end view (the cutting end) right of it, each on its axis."""
    turns = drawing.VIEW_TURNS
    assert set(turns) == {"*Front", "*Right", "*Bottom"}
    for name in ("*Front", "*Right"):
        (axis, sheet), _check = turns[name]
        assert axis == (0.0, 1.0, 0.0) and sheet == (-1.0, 0.0), name
    # Third angle: the top view's up is away from the front view's viewer
    # (-Z); the end view's right is too, and its up the front view's up.
    assert turns["*Front"][1] == ((1.0, 0.0, 0.0), (0.0, 1.0))
    assert turns["*Right"][1] == ((0.0, 0.0, -1.0), (0.0, 1.0))
    assert turns["*Bottom"] == (
        ((1.0, 0.0, 0.0), (0.0, 1.0)),
        ((0.0, 0.0, -1.0), (1.0, 0.0)),
    )
    assert drawing.TOP_ORIGIN[0] == drawing.FRONT_ORIGIN[0]
    assert drawing.TOP_ORIGIN[1] > drawing.FRONT_ORIGIN[1]
    assert drawing.END_ORIGIN[1] == drawing.FRONT_ORIGIN[1]
    assert drawing.END_ORIGIN[0] > drawing.FRONT_ORIGIN[0]
    # Views clear each other: front/top rows apart by more than the bar plus
    # the Ø's text; the end view right of the cutting end.
    radius = part.BAR_RADIUS * drawing._S
    assert drawing.TOP_ORIGIN[1] - drawing.FRONT_ORIGIN[1] > 4.0 * radius + 0.020
    assert drawing.END_ORIGIN[0] - radius - drawing.FRONT_ORIGIN[0] > 0.020
    dia_y = drawing.FRONT_KEEP["BarDia"][1]
    assert drawing.FRONT_ORIGIN[1] + radius < dia_y < drawing.TOP_ORIGIN[1] - radius


def test_the_tap_callout_rewrite_is_size_drill_into_the_cross_hole() -> None:
    native = {
        5: "<MOD-DIAM><hw-tapdrldia> <hw-thru>",
        6: "<hw-tapsize>-<hw-threadclass> <hw-thru>",
        7: "",
        8: "",
    }
    rewritten = drawing.tap_callout_definitions(native)
    assert rewritten == {
        5: "<MOD-DIAM><hw-tapdrldia> DRILL INTO CROSS HOLE",
        6: "<hw-tapsize> INTO CROSS HOLE",
        7: "",
        8: "",
    }
    assert drawing.TAP_PRECISION == {"hw-tapdrldia": part.HOLE_CALLOUT_PRECISION}
    for bad in (
        {**native, 6: "<hw-tapsize> <HOLE-DEPTH><hw-threaddepth>"},
        {**native, 7: "DRILL"},
    ):
        with pytest.raises(RuntimeError):
            drawing.tap_callout_definitions(bad)


def test_the_stock_diameter_says_stock_ok() -> None:
    assert part.DIMENSION_CALLOUTS["BarDia"] == "STOCK OK"


def test_the_sheet_is_reviewed_under_enforce() -> None:
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
