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


def test_the_set_screw_keeps_full_thread_and_meets_the_bit() -> None:
    assert part.SET_SCREW_THREAD == set_screw.THREAD
    assert part.TAP_DRILL_DIA == TAP_DRILL_MM[set_screw.THREAD]
    assert part.TAP_LENGTH >= 1.5 * THREAD_MAJOR_MM[set_screw.THREAD]
    # Its tip reaches the bit's top with its socket face near the end face;
    # at the station's shortest (.XX) it stands proudest yet keeps 1.5D.
    assert part.CROSS_HOLE_STATION_TOL == pytest.approx(0.254)
    assert abs(part.SET_SCREW_PROUD) <= 0.1
    proudest = set_screw.LENGTH - (
        part.CROSS_HOLE_STATION - part.CROSS_HOLE_STATION_TOL - bit.BIT_RADIUS
    )
    assert part.SET_SCREW_ENGAGED_MIN == pytest.approx(set_screw.LENGTH - proudest)
    assert part.SET_SCREW_ENGAGED_MIN >= 1.5 * THREAD_MAJOR_MM[set_screw.THREAD]
    # The tap runs to the hole, so the drill breaks out inside the bit's seat.
    assert part.TAP_DRILL_DIA < part.CROSS_HOLE_DIA


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
    keeps = {**drawing.FRONT_KEEP, **drawing.RIGHT_KEEP}
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
    # The bar's top end stays inside the sheet.
    assert drawing.FRONT_ORIGIN[1] + part.BAR_LENGTH * drawing._S < top


def test_the_tap_callout_rewrite_names_the_cross_hole_and_drops_the_class() -> None:
    native = {
        5: "<MOD-DIAM><hw-tapdrldia> <hw-thru>",
        6: "<hw-tapsize>-<hw-threadclass> <hw-thru>",
        7: "",
        8: "",
    }
    rewritten = drawing.tap_callout_definitions(native)
    joined = "\n".join(rewritten.values())
    assert joined.count(part.SET_SCREW_EXTENT) == 2
    assert "<hw-threadclass>" not in joined and "<hw-thru>" not in joined


def test_the_sheet_is_reviewed_under_enforce() -> None:
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
