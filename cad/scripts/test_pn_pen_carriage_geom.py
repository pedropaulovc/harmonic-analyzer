"""Offline contracts for the pen carriage layout (pn_pen_carriage_geom)."""

from __future__ import annotations

import itertools
import math

import pytest

import pen_driver
import pn_pen_carriage_geom as g
import pn_pen_frame_spec as frame
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as vb
import sh_vn_arbor_set_screw_spec as rod_set_screw
import sh_vn_music_wire_pen_geom as wire
from _hole_spec import THREAD_MAJOR_MM
from diagnostics import diag_build_91375A106 as set_screw_recipe
from _mg_wheel_rim_geometry import RIM_WIRE_R
from mg_wheel_bar_geom import WHEEL_BAR_Y, WHEEL_X
from _printed_tolerance import printed_band_mm
from _recording_geometry import PAPER_FRONT_Z, PEN_ROD_X, PEN_Z_MID

PAPER_LIMIT_Z = PAPER_FRONT_Z - 2.0 * g.CLEARANCE


def test_carriage_cg_hangs_on_the_rod_axis() -> None:
    # The pen hangs level only if the off-axis carriage balances about the
    # rod: with the lightening bore gone, the block's length is the knob.
    assert vb.BLOCK_LENGTH == 26.162  # 1.03
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


def test_rod_line_is_the_paper_most_thou_that_clears_the_paper() -> None:
    # PEN_Z_MID sits on the .001-in grid with the rigid carriage >= 0.02 inside
    # the paper stand-off, and the next .001 line toward the paper would leave
    # under 0.02 (the rigid points translate 1:1; the nib is re-solved).
    thou = PEN_Z_MID / 25.4 * 1000.0
    assert round(thou) == pytest.approx(thou, abs=1e-9)
    rigid = {
        k: v for k, v in g.paper_side_points().items() if not k.startswith("marker")
    }
    margin = PAPER_LIMIT_Z - max(rigid.values())
    assert margin >= 0.02
    assert margin - 0.0254 < 0.02


def _stirrup_paper_most(
    pivot_x: float,
    pivot_z: float,
    neck: tuple[float, float],
    window: float,
    left_wall: float,
    outer: float,
    shift: float,
) -> float:
    """Machine z of the stirrup's paper-side corner.  Block stations: x from
    the paper end (the stirrup flush on it), z from the body's front face;
    ``shift`` moves the window centre off the neck's centre toward the
    paper."""
    yaw = math.radians(g.PEN_BLOCK_YAW_DEG)
    front_wall = (neck[0] + neck[1]) / 2.0 + shift - window / 2.0
    paper_face = front_wall - left_wall + outer
    return PEN_Z_MID + pivot_x * math.cos(yaw) + (paper_face - pivot_z) * math.sin(yaw)


def _stirrup_worst(
    ring: tuple[float, float, float] = (
        frame.WINDOW_WIDTH,
        frame.RAIL_SIDE,
        frame.OUTER_WIDTH,
    ),
    *,
    centred: bool = False,
) -> float:
    """Every band the stirrup's stack reads, each at both printed limits, and
    the stirrup anywhere its window lets it sit across the neck.  ``ring`` is
    the (window, side rail, outer width) the frame prints."""
    band = printed_band_mm(2, unit=vb.UNIT)
    assert band == printed_band_mm(2, unit=frame.UNIT)
    neck_front, neck_back = vb.depth_station(0.0), vb.depth_station(vb.NECK_DEPTH)
    worst = -math.inf
    for signs in itertools.product((-1.0, 1.0), repeat=7):
        pivot_x, pivot_z, front, back, window, left, outer = (
            nominal + sign * band
            for nominal, sign in zip(
                (
                    vb.PIVOT_BORE_X,
                    vb.depth_station(vb.DEPTH_MID_Z),
                    neck_front,
                    neck_back,
                    *ring,
                ),
                signs,
            )
        )
        gap = (window - (back - front)) / 2.0
        for shift in (0.0,) if centred else (-gap, 0.0, gap):
            worst = max(
                worst,
                _stirrup_paper_most(
                    pivot_x, pivot_z, (front, back), window, left, outer, shift
                ),
            )
    return worst


def test_stirrup_clears_the_paper_at_the_printed_worst_case() -> None:
    # Codjiflo on #2119: the printed limits let the stirrup touch the paper.
    # No fit-up setting moves the stirrup or the block off the paper, so the
    # bands must hold it: every one at both limits and the stirrup anywhere
    # across the neck.
    worst = _stirrup_worst()
    guard = g.paper_side_points_printed_worst()
    assert guard["stirrup paper-side corner"] == pytest.approx(worst, abs=1e-6)
    assert worst < PAPER_FRONT_Z
    # The guard reads every rigid point the model checks, each no nearer the
    # paper than its modelled place.
    rigid = {
        k: v for k, v in g.paper_side_points().items() if not k.startswith("marker")
    }
    assert guard.keys() == rigid.keys()
    assert all(guard[k] >= rigid[k] for k in rigid)
    assert max(guard.values()) < PAPER_FRONT_Z


def test_the_wider_ring_reached_the_paper() -> None:
    # The 1.10 ring with .16 rails and a .78 window reached the paper at the
    # printed worst case even centred on the neck (the review's stack), and
    # further hard over: the narrow window and thin rails are what clear it.
    wide = (0.78 * 25.4, 0.16 * 25.4, 1.10 * 25.4)
    centred = _stirrup_worst(wide, centred=True)
    assert PAPER_FRONT_Z < centred < _stirrup_worst(wide)
    # The narrow window cannot shrink further: at .73 its printed minimum
    # would meet the neck's printed maximum.
    band = printed_band_mm(2, unit=frame.UNIT)
    assert frame.WINDOW_WIDTH - band > vb.NECK_DEPTH + 2.0 * band
    narrower = frame.WINDOW_WIDTH - 25.4 / 100.0
    assert narrower - band <= vb.NECK_DEPTH + 2.0 * band + 1e-9


def test_rod_set_screw_engages_its_full_thread_wholly_in_the_tap() -> None:
    # Codjiflo on #2119: rule 18 counts the installed screw's full-form
    # thread, not the tap's length.  The 3/16 91375A105 left 1.28 D; the
    # shared 1/4 91375A106 leaves over 1.5 D, all of it in the tap.
    recipe = set_screw_recipe
    assert rod_set_screw.LENGTH == pytest.approx(recipe.LENGTH)
    chamfers = recipe.POINT_CHAMFER + recipe.SOCKET_CHAMFER
    need = 1.5 * THREAD_MAJOR_MM[rod_set_screw.THREAD]
    assert vb.ROD_SET_SCREW_FULL_THREAD == pytest.approx(recipe.LENGTH - chamfers)
    assert vb.ROD_SET_SCREW_FULL_THREAD >= need
    assert 3.0 / 16.0 * 25.4 - chamfers < need
    # Cup on the pivot-bore wall, socket face under the front face.
    cup = g.ROD_SET_SCREW_CUP_LOCAL_Z
    assert cup == pytest.approx(vb.DEPTH_MID_Z - vb.PIVOT_BORE_DIA / 2.0)
    assert cup - rod_set_screw.LENGTH > vb.BODY_Z0
    assert g.ROD_SET_SCREW_MASS_G == pytest.approx(
        recipe.VENDOR_VOLUME_MM3 * g.ALLOY_STEEL_G_PER_MM3
    )


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
