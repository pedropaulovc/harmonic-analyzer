"""Physical contracts for the shop-made TL-27 Tr8x2 feed nut (owner ruling
2026-11-01, item 4)."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_oblique_feed_nut_spec as spec
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as nut_screw
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import CLEARANCE_MM
from _inch_wall_limits import WALL_TARGET_MM

INCH = 25.4


def test_identity_and_stock():
    metadata = _config.parts(spec.PART_NAME)
    assert metadata["number"] == spec.NUMBER == "MHA-CH-06-TL-27"
    assert metadata["quantity"] == spec.QUANTITY == 1
    assert spec.UNIT == "in"
    assert "BRASS 360-H02" in metadata["material"]
    assert spec.PART_NAME.replace("-", "_") in DRAWINGS_BY_NAME
    # The bar as bought: 3/4 x 1-1/4 at the supplier's bands, faced to .40.
    assert (spec.WIDTH, spec.HEIGHT) == pytest.approx((1.25 * INCH, 0.75 * INCH))
    assert (spec.WIDTH_STOCK_BAND, spec.HEIGHT_STOCK_BAND) == pytest.approx((0.005 * INCH, 0.0045 * INCH))
    assert spec.STOCK_CALLOUTS == {"NutWidth": "STOCK\n±.005", "NutHeight": "STOCK\n±.0045"}
    assert spec.LENGTH == pytest.approx(0.40 * INCH)
    assert spec.DRAWING_PRECISION_BY_NAME["NutLength"] == 2


def test_tr8_bore_is_letter_c_tapped_through_at_five_turns():
    assert spec.BORE_DRILL == pytest.approx(0.242 * INCH)
    assert spec.TR8_D1 < spec.BORE_DRILL < lead.SCREW_MAJOR_DIA - lead.SCREW_LEAD / 2
    assert spec.LENGTH >= 5 * lead.SCREW_LEAD
    # Under rule 18's 1.5D, accepted by the owner (2026-11-01) as RV-01.
    engagement_d = spec.LENGTH_MIN / lead.SCREW_MAJOR_DIA
    assert engagement_d < 1.5
    (exception,) = _config.parts(spec.PART_NAME)["machinist_exceptions"]
    assert exception["id"] == "RV-01"
    assert f"({engagement_d:.2f}D)" in exception["finding"]
    assert exception["reason"].startswith("Owner ruling 2026-11-01: thread engagement below 1.5D")
    assert (spec.BORE_X, spec.BORE_Y) == pytest.approx((0.63 * INCH, 0.38 * INCH))
    # Rule 20: the callout states the shortfall as a plain fact, RV-01's.
    assert spec.TR8_ENGAGEMENT_D == pytest.approx(engagement_d)
    assert spec.CALLOUTS_BELOW["BoreDia"] == "Tr8x2-7H RH THRU\nENGAGES .39 MIN (1.24D)"
    assert ".39 min (1.24D)" in exception["finding"]


def test_loose_holes_stand_2x_340_from_the_bore_and_name_their_mate():
    assert spec.HOLE_DIA == CLEARANCE_MM[("#4", "loose")]
    assert round(spec.HOLE_DIA / INCH, 3) == 0.144
    # Each hole from the bore axis, one each side, never from the other hole
    # (run 20261101T220223216Z: the chained .63 / .34 / .680 stacked three
    # bands on the far hole).
    assert spec.HOLE_OFFSET == pytest.approx(0.340 * INCH)
    assert spec.HOLE_X == pytest.approx((spec.BORE_X - 0.340 * INCH, spec.BORE_X + 0.340 * INCH))
    assert spec.HOLE_Y == spec.BORE_Y
    assert spec.DRAWING_DIMENSIONS["HolePatternReference"] == {"Hole1Offset", "Hole2Offset"}
    assert spec.DRAWING_PRECISION_BY_NAME["Hole1Offset"] == spec.DRAWING_PRECISION_BY_NAME["Hole2Offset"] == 3
    assert spec.CALLOUTS_BELOW["Hole1Offset"] == spec.CALLOUTS_BELOW["Hole2Offset"] == spec.MATE_CALLOUT
    assert spec.MATE_CALLOUT == "MATCHES TL-32 LUG TAPS"
    assert round(spec.HOLE_OFFSET_BAND / INCH, 4) == 0.0050
    # The loose fit floats a #4 by .016, past the .014 stack of both parts'
    # printed stations; the normal Ø.129's .008 would not.
    assert round(spec.HOLE_FLOAT / INCH, 4) == 0.0160
    assert spec.NORMAL_HOLE_FLOAT < feed_block.FIT_UP_RESIDUAL <= spec.HOLE_FLOAT


def test_walls_meet_the_target_at_the_printed_worst_case():
    assert min(spec.WALLS_MM.values()) >= WALL_TARGET_MM
    assert round(min(spec.WALLS_MM.values()) / INCH, 4) == 0.0937


def test_screws_engage_the_lug_two_diameters_and_stop_inside_it():
    assert spec.SCREW_COUNT == nut_screw.QUANTITY == 2
    assert nut_screw.SKU == "91251A113"
    assert spec.SCREW_ENGAGEMENT == pytest.approx(0.35 * INCH)
    assert spec.SCREW_FULL_THREAD_MIN >= 2.0 * spec.SCREW_MAJOR
    assert spec.SCREW_TIP_REACH_MAX < feed_block.LUG_WIDTH
    assert spec.HEAD_BEARING_LAND_MIN > 0.0


def test_reach_sets_the_near_kp08_gap():
    assert spec.REACH == pytest.approx(spec.LENGTH_MAX + nut_screw.DIMS.head_h)
    gaps = [gap for (name, _station), gap in feed_block.FEED_GAPS.items() if name == "KP08 near"]
    assert round(min(gaps) / INCH, 3) == pytest.approx(3.32 / INCH, abs=1e-3)
    assert min(gaps) >= lead.FEED_GAP


def test_drawing_is_inch_and_enforced():
    source = (Path(__file__).parent / "draw_ch_rocker_arm_tl_oblique_feed_nut.py").read_text(encoding="utf-8")
    assert "MACHINIST_REVIEW = MachinistReviewMode.ENFORCE" in source
    assert math.isclose(spec.LENGTH_BAND, 0.01 * INCH)


def test_hole_callouts_name_the_drill_and_centre_marks_print_once():
    # r1 review: a callout without DRILL leaves the band unnamed; r1 layout
    # audit: the template's marks plus AutoInsertCenterMarks2 printed twice.
    assert spec.CALLOUTS_SUFFIX == {"BoreDia": " DRILL THRU", "HoleDia": " DRILL THRU"}
    source = (Path(__file__).parent / "draw_ch_rocker_arm_tl_oblique_feed_nut.py").read_text(encoding="utf-8")
    assert "if _center_mark_count(face) == 0 and not auto_center_marks(" in source
    assert "FACE_CENTER_MARKS = 3" in source
