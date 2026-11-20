"""Offline contracts for the round arbor's backing collar (MHA-DT-03-TL-08)."""

from __future__ import annotations

import math
import sys

import pytest

import _buildgraph as bg
import _config
import build_dt_cone_gear_tl_round_arbor_collar as part
import draw_dt_cone_gear_tl_round_arbor_collar as drawing
import dt_cone_gear_tl_round_arbor_collar_spec as spec
import dt_cone_gear_tl_round_arbor_spec as arbor
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

INCH = 25.4
XX = printed_band_mm(2, unit="in")
XXX = printed_band_mm(3, unit="in")
STEM = "dt_cone_gear_tl_round_arbor_collar"
TITLE_TOP = 0.066  # the title block's top, sheet metres


def test_registry_row_is_one_standalone_tooling_part_in_inch() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-03-TL-08"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    assert "configuration_quantities" not in row
    entry = DRAWINGS_BY_NAME[STEM]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert bg.is_shop_fixture(STEM)
    assert STEM in bg.part_stems()
    for assembly in bg.ASSEMBLY_ORDER:
        assert STEM not in bg.references_of(assembly), assembly


def test_the_collar_is_the_arbors_and_3_8_stock_passes() -> None:
    assert spec.OUTER_DIA == arbor.COLLAR_DIA == pytest.approx(0.38 * INCH)
    assert spec.LENGTH == arbor.COLLAR_LENGTH == pytest.approx(0.30 * INCH)
    assert spec.BORE == arbor.COLLAR_BORE == pytest.approx(0.250 * INCH)
    stock = 0.375 * INCH
    assert spec.OUTER_DIA - XX <= stock - 0.002 * INCH
    assert stock <= spec.OUTER_DIA + XX
    assert spec.CALLOUTS_BELOW == {"OuterDia": "STOCK OK", "BoreDia": "DRILL THRU"}
    assert "3/8" in _config.parts(spec.PART_NAME)["material_specification"]


def test_the_collar_slides_over_the_pilot_and_the_thread() -> None:
    assert spec.BORE - (arbor.PILOT_DIA + XXX) > 0.0
    assert spec.BORE > arbor.THREAD_MAJOR
    # The nut's flats cover the bore's widest drilled limit.
    assert arbor.NUT_ACROSS_FLATS > spec.BORE + drilled_oversize_mm(unit="in")


def test_the_collar_stands_under_t024s_root_and_backs_over_half_of_it() -> None:
    root = arbor.BLANK.root_min_dia
    floating = (
        spec.BORE + drilled_oversize_mm(unit="in") - (arbor.PILOT_DIA - XXX)
    ) / 2.0
    reach = spec.OUTER_DIA / 2.0 + XX + floating
    assert reach + arbor.AIR_MIN <= root / 2.0
    assert reach == pytest.approx(arbor.COLLAR_REACH)
    assert spec.OUTER_DIA / root >= arbor.BACKING_SHARE_MIN


def test_volume_and_marked_dimensions_are_the_disc_and_bore() -> None:
    expected = math.pi / 4.0 * (spec.OUTER_DIA**2 - spec.BORE**2) * spec.LENGTH
    assert spec.V_COLLAR == pytest.approx(expected)
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked == {"OuterDia", "BoreDia", "Length"}
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "OuterDia": 2,
        "BoreDia": 3,
        "Length": 2,
    }
    assert set(spec.CALLOUTS_BELOW) <= marked
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked


def test_the_bore_callout_names_its_process() -> None:
    """Rule 12: a plain drilled size under DRILLED HOLES says DRILL."""
    assert spec.BORE_CALLOUT == "DRILL THRU"


def test_the_views_and_labels_stand_clear_of_each_other_and_the_title_block() -> None:
    """At 4:1 the end view, the side view with the OD right of it, and the
    2:1 isometric stand in a row above the title block."""
    half_od = drawing.HALF_OD
    side_right = drawing.SIDE_CENTER[0] + drawing.HALF_LENGTH
    iso_half = spec.OUTER_DIA / 2000.0 * spec.ISOMETRIC_VIEW_SCALE[0] * 1.25
    text_half = 0.010
    assert drawing.END_CENTER[0] + half_od + 0.030 < drawing.SIDE_CENTER[0] - half_od
    assert side_right < drawing.OD_ON_SIDE[0] - text_half
    assert drawing.OD_ON_SIDE[0] + text_half < drawing.ISO_CENTER[0] - iso_half
    assert drawing.SIDE_KEEP["Length"][1] - 0.005 > TITLE_TOP
    assert drawing.END_KEEP["OuterDia"][1] - 0.005 > TITLE_TOP
    assert drawing.ISO_NOTE_XY[1] - 0.005 > TITLE_TOP
    assert drawing.ISO_CENTER[1] - iso_half > drawing.ISO_NOTE_XY[1]


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
    monkeypatch.setattr(sys, "argv", ["draw", "dt-cone-gear-tl-arbor-collar"])
    with pytest.raises(SystemExit):
        drawing._parse_args()
