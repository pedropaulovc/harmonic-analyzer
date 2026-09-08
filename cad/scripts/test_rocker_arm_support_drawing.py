"""Offline contracts for the rocker-arm-support drawing."""

from __future__ import annotations

import math

import pytest

import draw_rocker_arm_support as drawing
import build_rocker_arm_support as support
import build_frame_assembly as frame
import build_lag_screw as screw
import rocker_arm_support_spec as placement


def test_drawing_keeps_exactly_the_marked_dimension_set() -> None:
    marked = set().union(*support.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_stock_hold_down_matches_receiver_and_engages_only_foot_material() -> None:
    assert screw.SPEC.skus == ("91783A722",)
    assert support.HOLE_SSIZE == screw.THREAD_SIZE == "1/2-13"
    assert (screw.THREAD_CLASS, support.HOLE_THREAD_CLASS) == ("2A", "2B")
    assert support.HOLE_TAP_DRILL_DIA < screw.SHANK_DIA < frame.LAG_CLEARANCE_DIA
    assert screw.HEAD_DIA < frame.LAG_COUNTERBORE_DIA
    assert frame.LAG_HEAD_RECESS == pytest.approx(0.5)
    assert frame.LAG_SUPPORT_ENGAGEMENT == pytest.approx(6.35)
    assert frame.LAG_SCREW_TIP_Y - screw.THREAD_LEN < frame.BASE_TOP_Y
    assert frame.LAG_TIP_REACH_ABOVE_BASE > frame.LAG_SUPPORT_ENGAGEMENT


def test_bottom_view_picks_actual_tap_drill_rim_at_each_station() -> None:
    for x_mm, z_mm in support.HOLES:
        sheet_x, sheet_y = drawing._bottom_sheet_xy((x_mm, z_mm))
        picked_x = (sheet_x - drawing.BOTTOM_CENTER[0]) * 1000 / drawing.VIEW_SCALE
        picked_z = (sheet_y - drawing.BOTTOM_CENTER[1]) * 1000 / drawing.VIEW_SCALE
        assert math.hypot(picked_x - x_mm, picked_z - z_mm) == pytest.approx(
            support.HOLE_TAP_DRILL_DIA / 2.0
        )


def test_hole_table_covers_every_foot_hole() -> None:
    assert len(support.HOLES) == 4
    points = {drawing._bottom_sheet_xy(hole) for hole in support.HOLES}
    assert len(points) == 4
    half_w = support.BOSS_DEPTH / 2.0 * drawing.VIEW_SCALE / 1000.0
    half_h = support.WIDE * drawing.VIEW_SCALE / 1000.0
    for x, y in points:
        assert abs(x - drawing.BOTTOM_CENTER[0]) <= half_w
        assert abs(y - drawing.BOTTOM_CENTER[1]) <= half_h


def test_support_keeps_original_world_placement_and_hold_down_pattern() -> None:
    assert placement.SUPPORT_WORLD_Z == 0.0
    assert {z for _, z in placement.SUPPORT_HOLD_DOWN_XZ} == {
        -60.32,
        60.32,
    }
