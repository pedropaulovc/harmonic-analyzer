"""Offline contracts for the pen carriage layout (pn_pen_carriage_geom)."""

from __future__ import annotations

import itertools
import math

import pytest

import _shop_equipment
import pen_driver
import pn_pen_carriage_geom as g
import pn_pen_frame_spec as frame
import pn_pen_rod_groove_spec as groove
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as vb
import sh_vn_arbor_set_screw_spec as rod_set_screw
import sh_vn_music_wire_pen_geom as wire
from _hole_spec import THREAD_MAJOR_MM
from diagnostics import diag_build_91375A106 as set_screw_recipe
from _mg_wheel_rim_geometry import RIM_WIRE_R
from mg_wheel_bar_geom import WHEEL_BAR_Y, WHEEL_X
from _printed_tolerance import printed_band_mm, printed_deviations
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


def test_rod_line_is_on_the_thou_grid_and_clears_the_paper() -> None:
    # PEN_Z_MID sits on the .001-in grid with the rigid carriage >= 0.02 inside
    # the paper stand-off (the rigid points translate 1:1; the nib is re-solved).
    thou = PEN_Z_MID / 25.4 * 1000.0
    assert round(thou) == pytest.approx(thou, abs=1e-9)
    rigid = {
        k: v for k, v in g.paper_side_points().items() if not k.startswith("marker")
    }
    assert PAPER_LIMIT_Z - max(rigid.values()) >= 0.02


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
    the stirrup's paper-side face (``pivot_x`` the rod axis from it), z from
    the body's front face; ``shift`` moves the window centre off the neck's
    centre toward the paper."""
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
    proud: float = g.STIRRUP_PROUD_MAX,
) -> float:
    """Every band the stirrup's stack reads, each at both printed limits, and
    the stirrup anywhere its window lets it sit across the neck, its face
    ``proud`` of the block's paper end: by default as far as its setting's
    square check lets it (#3467).
    ``ring`` is the (window, side rail, outer width) the frame prints."""
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
                    pivot_x + proud, pivot_z, (front, back), window, left, outer, shift
                ),
            )
    return worst


def test_stirrup_clears_the_paper_at_the_printed_worst_case() -> None:
    # Codjiflo on #2119: the printed limits let the stirrup touch the paper.
    # No fit-up setting moves the block off the paper, and the stirrup's
    # setting (#3467) holds its paper face flush or behind the end, so the
    # bands must hold it: every one at both limits, the stirrup anywhere
    # across the neck: 0.209 to spare.
    worst = _stirrup_worst()
    guard = g.paper_side_points_printed_worst()
    assert g.STIRRUP_PROUD_MAX == 0.0
    assert guard["stirrup paper-side corner"] == pytest.approx(worst, abs=1e-6)
    assert worst < PAPER_FRONT_Z
    assert PAPER_FRONT_Z - worst == pytest.approx(0.2085, abs=1e-4)
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


def _sampled_ride(far_x: float, r: float, leg: float, stop: float) -> float:
    """The corner's ride, sampled over its metal: at each z in from the
    neck's face the metal runs from the top down to the arc, and the cone's
    run-out ``d`` past the stop has removed what lies within
    sqrt(d^2 + z^2) + t <= leg (z + t <= leg on the full break)."""
    d = far_x - stop
    worst = 0.0
    for i in range(2001):
        z = r * i / 2000.0
        t = r - math.sqrt(max(0.0, r * r - (r - z) ** 2))
        reach = math.hypot(d, z) + t if d > 0.0 else z + t
        worst = max(worst, reach - leg)
    return worst


def test_stirrup_setting_keeps_its_window_corners_off_the_break_run_out() -> None:
    # #3467 (Codjiflo P3 on #3445): the neck breaks run full only to their
    # stop; past it the chamfer mill's cone runs out.  With the corners at
    # R.070, the legs at .075 and the stop landing 0.02 short (the PM-30MV's
    # repeatability), the far corners reach the run-out once the stirrup's
    # rear face stands 8.489 (.3342) from the paper end.  The setting's far
    # limit, .325 (the deepest stirrup flush plus .005), leaves 0.234 (.0092).
    shop = _shop_equipment.load()["cnc"]["pm-30mv"]
    assert g.MILL_REPEATABILITY == shop["repeatability_mm"]
    assert g.NECK_BREAK_STOP_MIN == pytest.approx(0.33 * 25.4 - 0.02)
    assert g.STIRRUP_REAR_FACE_LIMITS == pytest.approx((0.310 * 25.4, 0.325 * 25.4))
    assert g.STIRRUP_REAR_FACE_LIMIT == pytest.approx(
        g.NECK_BREAK_STOP_MIN + 0.075 * 25.4 - 0.070 * 25.4
    )
    assert g.STIRRUP_REAR_FACE_LIMIT == pytest.approx(8.489, abs=1e-3)
    margin = g.STIRRUP_REAR_FACE_LIMIT - g.STIRRUP_REAR_FACE_LIMITS[1]
    assert margin == pytest.approx(0.234, abs=1e-3)
    assert g.window_corner_ride_max(g.STIRRUP_REAR_FACE_LIMITS[1]) == 0.0
    assert g.WINDOW_CORNER_RIDE_MAX == 0.0
    # Past the limit the far corners ride the run-out one for one.
    limit = g.STIRRUP_REAR_FACE_LIMIT
    assert g.window_corner_ride_max(limit) == pytest.approx(0.0, abs=1e-9)
    assert g.window_corner_ride_max(limit + 0.1) == pytest.approx(0.1)
    # The closed form is the sampled worst over the corner's metal.
    r, leg = frame.WINDOW_CORNER_R_MAX, vb.NECK_EDGE_BREAK_MIN
    for rear in (7.874, 8.128, 8.255, limit, 8.636, 8.890):
        sampled = _sampled_ride(rear, r, leg, g.NECK_BREAK_STOP_MIN)
        assert g.window_corner_ride_max(rear) == pytest.approx(
            max(0.0, sampled), abs=1e-6
        )


def test_the_setting_guard_refuses_a_stirrup_set_toward_the_step() -> None:
    # The pen assembly's interference gate cannot see the ride: the model
    # carries the nominal R.065 corners, the nominal .080 legs, the stirrup
    # centred on the neck and its rail FRAME_TOP_GAP off the top.  Even with
    # the side wall on the neck and the rail on the top, its corners meet
    # the run-out only once its far face stands leg - R past the stop, the
    # stirrup set 0.889 toward the step (the body's step stops it at 1.016).
    # Its rear face set .340 (0.762 toward the step), past the .3342 limit,
    # still rides nothing in the model.
    bad = 0.340 * 25.4
    nominal = g.window_corner_ride(
        bad, frame.WINDOW_CORNER_R, vb.NECK_EDGE_BREAK, vb.NECK_BREAK_FULL_X
    )
    assert nominal == 0.0
    blind_to = vb.NECK_BREAK_FULL_X + vb.NECK_EDGE_BREAK - frame.WINDOW_CORNER_R
    assert blind_to - frame.FRAME_DEPTH == pytest.approx(0.889, abs=1e-3)
    assert vb.RELIEF_X0 - frame.FRAME_DEPTH == pytest.approx(1.016, abs=1e-3)
    # So the guard reads the setting against the printed worst case, at
    # import, before any SolidWorks leaf: set there the corners ride 0.147.
    assert g.window_corner_ride_max(bad) == pytest.approx(0.147, abs=1e-3)
    with pytest.raises(AssertionError, match="rides the neck breaks' run-out"):
        g.stirrup_setting_ride(bad)
    # Just past the limit it refuses; at the limit and as printed it passes.
    with pytest.raises(AssertionError, match="rides the neck breaks' run-out"):
        g.stirrup_setting_ride(g.STIRRUP_REAR_FACE_LIMIT + 0.001)
    assert g.stirrup_setting_ride(g.STIRRUP_REAR_FACE_LIMIT - 1e-9) == 0.0
    assert g.stirrup_setting_ride(g.STIRRUP_REAR_FACE_LIMITS[1]) == 0.0


def test_the_setting_guard_refuses_a_stirrup_set_proud_of_the_paper_end() -> None:
    # Codjiflo P2 on #3470: calipers over a proud stirrup read only its own
    # depth, so the .310-.325 reading alone let the deepest stirrup (.320)
    # stand .010 proud, 0.029 off the paper at the printed worst case, and
    # .020 proud reach it.  The pen assembly has no paper (MHA-HA-00 does),
    # so its gate is blind to this too; step 5D's square check holds the
    # paper face flush or behind, and the guard refuses a proud placement.
    deepest = frame.FRAME_DEPTH + 0.01 * 25.4
    assert PAPER_FRONT_Z - _stirrup_worst(proud=0.254) == pytest.approx(0.0289, abs=1e-4)
    assert _stirrup_worst(proud=0.508) > PAPER_FRONT_Z
    with pytest.raises(AssertionError, match="proud of the paper end"):
        g.stirrup_placement_check(-0.254, deepest)
    with pytest.raises(AssertionError, match="proud of the paper end"):
        g.stirrup_placement_check(-0.001, frame.FRAME_DEPTH)
    # Flush it passes, and set toward the step it refuses the ride instead.
    assert g.stirrup_placement_check(0.0, deepest) == 0.0
    assert g.stirrup_placement_check(g.FRAME_X0_LOCAL, frame.FRAME_DEPTH) == 0.0
    with pytest.raises(AssertionError, match="rides the neck breaks' run-out"):
        g.stirrup_placement_check(0.762, frame.FRAME_DEPTH)


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
    # Cup on the relief groove's floor (#2439), socket face under the front face.
    cup = g.ROD_SET_SCREW_CUP_LOCAL_Z
    assert cup == pytest.approx(vb.DEPTH_MID_Z - groove.GROOVE_DIA / 2.0)
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


def test_set_screw_point_lands_in_the_relief_groove() -> None:
    # #2439 option B: the groove centres on the screw's .24 printed station
    # (.71 block less .47), .010 under the Ø.126 pivot, and the point's
    # chamfer at the bore wall passes between the walls at every printed limit.
    # Owner ruling 2026-11-24, fit audit question 20: the bore is drilled #30
    # (.1285 +.004/0), the pivot unchanged.
    assert vb.BLOCK_HEIGHT / 25.4 == pytest.approx(0.71, abs=0.005)
    station = (groove.GROOVE_NEAR_STATION + groove.GROOVE_FAR_STATION) / 2.0
    assert station / 25.4 == pytest.approx(0.24)
    assert groove.GROOVE_DEPTH / 25.4 == pytest.approx(0.010)
    shoulder_side, end_side = g.groove_landing_spare()
    assert shoulder_side / 25.4 == pytest.approx(0.0077, abs=1e-4)
    assert end_side / 25.4 == pytest.approx(0.0077, abs=1e-4)
    # Full printed worst case (codjiflo P3 on #3152): the deepest .XXX floor
    # in the largest drilled bore raises the point's crossing of the bore
    # wall to .01575, widening the chamfer there by twice the extra rise.  The
    # point must still pass both walls (0.082 mm spare), and the first full
    # thread (one pitch back from the cup) must stay inside the tap.
    floor_low, _ = printed_deviations(
        groove.GROOVE_DIA, groove.GROOVE_PLACES, unit=rod.UNIT
    )
    rise_max = (
        vb.PIVOT_BORE_DIA + vb.PIVOT_BORE_BAND[0] - (groove.GROOVE_DIA + floor_low)
    ) / 2.0
    assert rise_max / 25.4 == pytest.approx(0.01575, abs=1e-5)
    extra = rise_max - (vb.PIVOT_BORE_DIA - groove.GROOVE_DIA) / 2.0
    for spare in (shoulder_side, end_side):
        assert (spare - extra) / 25.4 == pytest.approx(0.0032, abs=1e-4)
        assert spare - extra > 0.0
    assert rod_set_screw.POINT_LENGTH > rise_max
    # The cup still reaches the groove floor with the pivot pushed off by
    # its whole float in the largest bore (.0200 against the .025 point).
    pin_min = rod.PIVOT_DIA + rod.PIVOT_BAND[1]
    reach = rise_max + (vb.PIVOT_BORE_DIA + vb.PIVOT_BORE_BAND[0] - pin_min) / 2.0
    assert reach / 25.4 == pytest.approx(0.0200, abs=1e-4)
    assert rod_set_screw.POINT_LENGTH > reach
