"""Offline contracts for the pen carriage layout (pn_pen_carriage_geom)."""

from __future__ import annotations

import math

import pytest

import pen_driver
import pn_pen_carriage_geom as g
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as vb
import sh_vn_music_wire_pen_geom as wire
from _mg_wheel_rim_geometry import RIM_WIRE_R
from mg_wheel_bar_geom import WHEEL_BAR_Y, WHEEL_X
from _recording_geometry import PAPER_FRONT_Z, PEN_ROD_X, PEN_Z_MID

PAPER_LIMIT_Z = PAPER_FRONT_Z - 2.0 * g.CLEARANCE


def test_carriage_cg_hangs_on_the_rod_axis() -> None:
    # The pen hangs level only if the off-axis carriage balances about the
    # rod: with the lightening bore gone, the block's length is the knob.
    assert vb.BLOCK_LENGTH == 27.178  # 1.07
    assert g.plan_cg_residual_mm() <= 0.1


def test_every_carriage_point_stands_off_the_paper() -> None:
    points = g.paper_side_points()
    assert max(points.values()) <= PAPER_LIMIT_Z
    # The yawed nib's paper-most point is on its flank, not its axial tip
    # (the top-assembly interference gate caught a 0.03 mm flank overlap).
    sin = math.sin(math.radians(g.PEN_BLOCK_YAW_DEG))
    nib_paper_most = max(
        g.machine_z(g.MARKER_NIB_LOCAL_X + y, vb.DEPTH_MID_Z) + r * sin
        for y, r in g.marker.PROFILE
    )
    assert nib_paper_most == pytest.approx(PAPER_FRONT_Z - g.CLEARANCE)


def test_rod_line_is_the_paper_most_tenth_that_clears_the_paper() -> None:
    # PEN_Z_MID sits on the 0.1 grid, and moving it 0.1 toward the paper
    # would push the binding corner (it translates 1:1; the nib is re-solved)
    # inside the paper stand-off.
    assert round(PEN_Z_MID * 10.0) == pytest.approx(PEN_Z_MID * 10.0, abs=1e-9)
    rigid = {
        k: v for k, v in g.paper_side_points().items() if not k.startswith("marker")
    }
    assert max(rigid.values()) + 0.1 > PAPER_LIMIT_Z


def test_rod_line_sits_on_the_wheel_rim_tangent() -> None:
    assert PEN_ROD_X == pytest.approx(WHEEL_X - RIM_WIRE_R)
    assert g.ROD_POS == (PEN_ROD_X, g.BLOCK_TOP_Y, PEN_Z_MID)


def test_pen_wire_hangs_plumb_onto_the_stud_eye() -> None:
    assert wire.WIRE_X == PEN_ROD_X
    assert wire.WHEEL_MID_Z == PEN_Z_MID
    assert wire.WIRE_BOTTOM == (PEN_ROD_X, g.STUD_HEAD_TOP_REST_Y, PEN_Z_MID)
    assert wire.WIRE_BOTTOM[1] + wire.WIRE_LEN == pytest.approx(WHEEL_BAR_Y)


def test_travel_literal_matches_the_pen_driver_stroke() -> None:
    assert g.PEN_TRAVEL_HALF_MM == pen_driver.stroke_half_mm()
    sweep = [
        pen_driver.expected_tip_disp_mm(2.0 * math.pi * k / 360) for k in range(360)
    ]
    assert max(abs(d) for d in sweep) <= g.PEN_TRAVEL_HALF_MM + 1e-9


def test_rod_seats_on_the_block_and_its_pivot_stops_above_the_relief() -> None:
    assert g.ROD_POS[1] == pytest.approx(g.VBLOCK_POS[1] + vb.BLOCK_HEIGHT)
    pivot_end = vb.BLOCK_HEIGHT - rod.PIVOT_LENGTH
    assert pivot_end == pytest.approx(g.ROD_PIVOT_END_LOCAL_Y)
    assert pivot_end - vb.RELIEF_HEIGHT >= 0.5


def test_stud_and_nut_stack_on_the_rod_top() -> None:
    assert g.STUD_POS[1] == pytest.approx(g.ROD_SQUARE_TOP_REST_Y - rod.STUD_ENGAGEMENT)
    assert g.NUT_POS[1] == pytest.approx(g.ROD_SQUARE_TOP_REST_Y)
    # Rule 18: at least 1.5 D of the #0-80 stud in the rod.
    assert rod.STUD_ENGAGEMENT >= 1.5 * 1.524


def test_rider_rows_are_proper_rotations() -> None:
    for rows in (
        g.BLOCK_ROWS,
        g.MARKER_ROWS,
        g.FRAME_ROWS,
        g.THUMB_SCREW_ROWS,
        g.ROD_SET_SCREW_ROWS,
        g.NUT_ROWS,
    ):
        for i in range(3):
            for j in range(3):
                dot = sum(rows[i][k] * rows[j][k] for k in range(3))
                assert dot == pytest.approx(1.0 if i == j else 0.0, abs=1e-12)
        x, y, z = rows
        cross = (
            x[1] * y[2] - x[2] * y[1],
            x[2] * y[0] - x[0] * y[2],
            x[0] * y[1] - x[1] * y[0],
        )
        assert cross == pytest.approx(tuple(z), abs=1e-12)
