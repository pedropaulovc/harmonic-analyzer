"""Offline invariants for the recentered alignment-pinion support closure."""

from __future__ import annotations

import math

import build_drive_train_assembly as drive
import pinion_rig_fitup as FITUP
import pinion_rig_layout as RIG
from pinion_pivot_block_geometry import BLOCK_EAST
from rocker_arm_support_spec import SUPPORT_WORLD_X


def test_alignment_pinion_mesh_gap_stays_at_the_proven_axis() -> None:
    assert drive.APINION_Y == drive.Y_DRIVE
    assert math.isclose(
        drive.APINION_X - drive.X_DRUM,
        drive.TIP_DRUM120 + drive.TIP_APINION + drive.APINION_GAP,
        abs_tol=1e-9,
    )
    # U28 (user, 2026-09-23; 997f3534): the drum parks 2.0 outside the tip
    # circles PLUS the base-chord seat offset, so the engage swing ends where
    # the 120T tips seat on the gap floor (engaged C2C), not at the pitch sum.
    pitch_sum = (120 + drive.APINION_TEETH) / drive.DP_TRAIN * 25.4 / 2.0
    assert math.isclose(
        drive.APINION_GAP, 2.0 + (drive.ENGAGED_C2C - pitch_sum), abs_tol=1e-4
    )


def test_support_rig_keeps_its_proven_outboard_topology() -> None:
    assert drive.X_DRUM < drive.APINION_X < drive.PIVOT_X < drive.LIFT_X
    assert drive.BLOCK_X > drive.APINION_X
    assert drive.LEVER_TILT_DEG == 10.0
    assert drive.HANDLE_TILT_DEG > 0.0

    # U28 datum B: the block origin is its pivot bore and the block is
    # asymmetric (BLOCK_EAST 14 toward the drum, BLOCK_WEST 26), so the near
    # edge is the east end, not BLOCK_X - BLOCK_WIDTH / 2.
    block_near_edge = drive.BLOCK_X - BLOCK_EAST
    cylinder_outboard_tip = drive.X_DRUM + drive.TIP_DRUM120
    assert block_near_edge - cylinder_outboard_tip >= 0.25


def test_lever_sweeps_from_photographed_park_to_cam_solved_engagement() -> None:
    assert -85.0 < drive.CAM_ENGAGE_ROTATION_DEG < -75.0
    assert -80.0 < drive.LEVER_ENGAGED_TILT_DEG < -65.0
    assert math.isclose(
        drive._engaged_cam_gap(drive.CAM_ENGAGE_ROTATION_DEG),
        0.0,
        abs_tol=1e-12,
    )
    assert drive.LEVER_ENGAGED_TILT_DEG < 0.0 < drive.LEVER_TILT_DEG


def test_rederived_cam_and_return_leaf_clearances_are_positive() -> None:
    # The design band the assembly itself asserts (0.10..0.25 of air).  The
    # derived value moved 0.150 -> 0.153 with the U28 re-lay (997f3534) and
    # -> 0.161 with U27's line-to-line follower pin, 4.016 -> 4.000 (c9685fa0).
    assert 0.10 <= drive._PARK_GAP <= 0.25
    assert math.isclose(drive._PARK_GAP, 0.1606, abs_tol=5e-4)
    cam_authority = (drive.FPIN_DIA + drive.CAM_OD) / 2.0 - drive._D_ENG
    assert cam_authority >= 0.25
    assert drive.LIFT_Y - drive._CAM_SWEEP_R - drive.Y_BASE_TOP >= 0.25
    assert (
        math.hypot(
            drive.X_DRUM - drive.SPRING_CREST[0],
            drive.Y_DRIVE - drive.SPRING_CREST[1],
        )
        - drive.SPRING_T
        >= drive.TIP_DRUM120 + 0.25
    )
    assert drive._FPIN_TIP_S - drive._S_CAM >= 2.0


def test_return_spring_foot_clears_the_fixed_rocker_support() -> None:
    rocker_near_face = SUPPORT_WORLD_X - 31.75
    spring_foot_end = drive.SPRING_X - drive.SPR_FOOT_END_L[0]
    assert rocker_near_face - spring_foot_end >= 0.25
    assert (
        rocker_near_face - (drive.SPRING_HOLE_X + drive.FSCREW_HEAD_DIA / 2.0) >= 0.25
    )


def test_base_holes_follow_the_rederived_support() -> None:
    for derived, base in zip(drive._BLOCK_SCREW_XZ, drive.BASE_BLOCK_XZ, strict=True):
        assert math.dist(derived, base) < 1e-9
    for derived, base in zip(drive._FOOT_SCREW_XZ, drive.BASE_FOOT_XZ, strict=True):
        assert math.dist(derived, base) < 1e-9


def _world(origin, rows, local):
    return [origin[k] + sum(local[i] * rows[i][k] for i in range(3)) for k in range(3)]


def test_mha135_pin_holes_share_one_axis_at_the_drive_train_pose() -> None:
    # MHA-135 is match-drilled through the lever hub and the lift rod at
    # assembly, so the model's two holes must be one line.  Each part cuts its
    # hole along its own local X (build_pinion_lift_rod / build_pinion_lever
    # "lever pin" axes); the rod is phased to the lever to make them coincide.
    from pinion_lever_geometry import PIN_HOLE_Z, ROD_PIN_HOLE_FROM_END

    rod_origin = [drive.LIFT_X, drive.LIFT_Y, drive.LIFT_ROD_Z0]
    lever_origin = [drive.LIFT_X, drive.LIFT_Y, drive.LEVER_Z]
    rod_point = _world(
        rod_origin, drive.LIFT_ROD_ROWS, [0.0, 0.0, ROD_PIN_HOLE_FROM_END]
    )
    lever_point = _world(lever_origin, drive.LEVER_ROWS, [0.0, 0.0, PIN_HOLE_Z])
    rod_dir = drive.LIFT_ROD_ROWS[0]
    lever_dir = drive.LEVER_ROWS[0]

    cross = [
        rod_dir[1] * lever_dir[2] - rod_dir[2] * lever_dir[1],
        rod_dir[2] * lever_dir[0] - rod_dir[0] * lever_dir[2],
        rod_dir[0] * lever_dir[1] - rod_dir[1] * lever_dir[0],
    ]
    assert math.hypot(*cross) < 1e-9
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(rod_point, lever_point))


def test_mha135_is_placed_on_the_shared_pin_axis_and_rides_the_rod() -> None:
    # MHA-135 is a component, not only a mated joint: BDT inserts it with
    # the rod's phase at the rod's pin station (both holes' common point),
    # and locks it to the rod, so it joins the freed lift-rod spin family.
    import inspect

    from _assembly import allowed_free_stems
    from pinion_lever_geometry import ROD_PIN_HOLE_FROM_END

    source = inspect.getsource(drive)
    assert source.count('"pinion-lever-pin"') == 1
    assert 'f"Axis2@{lift_rod}"' in source
    pin_point = [drive.LIFT_X, drive.LIFT_Y, drive.LIFT_ROD_Z0 + ROD_PIN_HOLE_FROM_END]
    rod_point = _world(
        [drive.LIFT_X, drive.LIFT_Y, drive.LIFT_ROD_Z0],
        drive.LIFT_ROD_ROWS,
        [0.0, 0.0, ROD_PIN_HOLE_FROM_END],
    )
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(pin_point, rod_point))
    free = allowed_free_stems("drive-train")
    assert "pinion-lever-pin" in free and "pinion-lift-rod" in free


def test_rod_phase_leaves_the_cams_parked_ecc_down() -> None:
    # The rod carries LEVER_TILT_DEG of phase; the cams must not: their world
    # rows stay the identity the park-gap and engage solves assume, tied back
    # to the rod by the same angle, and the freed spin's rest dihedral moves
    # by exactly that phase.
    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert drive.PINION_CAM_ROWS == identity
    assert math.isclose(drive.CAM_ROD_PHASE_DEG, drive.LEVER_TILT_DEG, abs_tol=1e-9)
    assert math.isclose(
        drive.LIFT_ROD_PARK_DEG, 90.0 + drive.LEVER_TILT_DEG, abs_tol=1e-9
    )
    assert math.isclose(drive._PARK_GAP, 0.1606, abs_tol=5e-4)


# Ruling (c) worst-case stack (user, 2026-09-24).  Physical end play is ONE
# feeler setting, P = 0.25 +/- 0.10, shared by the four axial gaps (front
# block/strap g_f, strap/drum g_df, drum/strap g_db, strap/back block g_b), each
# >= 0; the saved pose is the fit-up vertex, all of P at the front block.
# Every quantity below is linear in the gaps, so the extremes sit at the
# vertices swept here.
#
# The lift rod floats axially.  Southward, the front cam collar stops on the
# front block's inner face; it is set there with the same 0.25 feeler, so up
# to 0.35 of play.  Northward, the lever hub does NOT bear on the front block
# (its bore takes 8 of the rod's LEVER_SEAT_PROUD, leaving it at least the back
# collar's largest gap plus 0.25 off the block face at the worst stack, Codex
# #837), so the rod runs about 1.5 north, until the back cam collar lands on
# the back block, and the hub never stops it.  Main 2026-09-24: keep that
# float, since every follower gate below holds at its true extremes.  The rod
# is set back-flush, so its travel is measured from there against the front
# block (pinion_rig_layout: the pose is the fit-up stack, Codex #854).
_P_MAX = FITUP.FRONT_BLOCK_FEELER + FITUP.FRONT_BLOCK_FEELER_BAND
_FEELER_BAND = (  # front collar set gap to the block
    FITUP.FRONT_BLOCK_FEELER - FITUP.FRONT_BLOCK_FEELER_BAND,
    FITUP.FRONT_BLOCK_FEELER + FITUP.FRONT_BLOCK_FEELER_BAND,
)
_BACK_CAM_SET_ERR = RIG.BACK_CAM_SET_ERR  # the back collar is set to its pin by eye


def _hub_gap() -> float:
    """Lever hub to the front block, with the rod set back-flush."""
    import pinion_rig_layout as rig

    hub_north = drive.LEVER_Z + drive.LEVER_HUB_LEN / 2.0
    hub_gap = rig.FRONT_BLOCK_Z0 - hub_north
    assert hub_gap >= 0.25, hub_gap
    return hub_gap


def _back_collar_gap(t: float, e: float) -> float:
    """Back collar to back block, set to its pin (+e) with the cluster hard back."""
    return t / 2.0 - (drive.CAM_LEN - drive.CAM_PIN_STATION[1]) - e


def _strap_t_band() -> tuple[float, float]:
    return (drive.STRAP_T - RIG.STRAP_T_BAND, drive.STRAP_T + RIG.STRAP_T_BAND)


def test_j19_keeps_two_thirds_face_at_the_worst_stack() -> None:
    # The drum's back end is located from the back block through the back
    # strap: worst when the strap is thickest and all the play sits behind the
    # drum.  Floor 2.0 of the 3.0 face (Main, 2026-09-24: lightly loaded train).
    g19_front = drive.Z_DRUM0 + 19 * drive.Z_PITCH - drive.DRUM_FACE / 2.0
    g19_back = g19_front + drive.DRUM_FACE
    worst = min(
        min(drive.BLOCK_BACK_Z0 - t - g, g19_back) - g19_front
        for t in _strap_t_band()
        for g in (0.0, _P_MAX)
    )
    assert worst >= 2.0, worst
    assert math.isclose(worst, 2.126, abs_tol=5e-3)
    # j = 0 at the front: the drum's front end never uncovers gear 0.
    g0_front = drive.Z_DRUM0 - drive.DRUM_FACE / 2.0
    face_min = drive.APINION_DRUM_LEN - RIG.DRUM_LEN_BAND
    for t in _strap_t_band():
        assert drive.BLOCK_BACK_Z0 - t - face_min <= g0_front - 1.0


def _follower_stations() -> tuple[list[float], list[float]]:
    """Follower-pin stations from each collar's front face, at every vertex."""
    import itertools

    # c is the front collar's gap to the front block's inner face: 0 with the
    # rod hard south, up to the first north stop (back collar on the back
    # block, else the hub on the front block).  The back collar is set to its
    # pin at c_set with the cluster hard back; the strap then moves forward by
    # g_b and the rod north by c - c_set.  Pins ride their strap mid-planes.
    front, back = [], []
    for g_f, g_b, t, c_set, e in itertools.product(
        (0.0, _P_MAX),
        (0.0, _P_MAX),
        _strap_t_band(),
        _FEELER_BAND,
        (-_BACK_CAM_SET_ERR, _BACK_CAM_SET_ERR),
    ):
        assert _back_collar_gap(t, e) >= 0.5, (t, e)
        c_max = c_set + min(_hub_gap(), _back_collar_gap(t, e))
        for c in (0.0, c_max):
            front.append(g_f + t / 2.0 - c)
            back.append(drive.CAM_PIN_STATION[1] + e - g_b - (c - c_set))
    return front, back


def test_follower_pins_stay_on_their_collars_at_the_worst_stack() -> None:
    front, back = _follower_stations()
    assert math.isclose(drive.CAM_PIN_STATION[0], drive.STRAP_T / 2.0)
    for stations in (front, back):
        assert min(stations) >= 1.0, stations
        assert max(stations) <= drive.CAM_LEN - 1.0, stations
    assert math.isclose(min(front), 2.15, abs_tol=5e-3)
    # 2.75, not the old 3.10: at the thickest back strap and the late set,
    # the 2.05 hub gap used to stop the rod before the 2.4 back collar did
    # (Codex #837).  The hub now never is the stop, so the collar's whole gap
    # applies.
    assert math.isclose(min(back), 2.75, abs_tol=5e-3)
    # North float at the nominal set: the back collar lands first.
    assert math.isclose(_back_collar_gap(drive.STRAP_T, 0.0), 1.5, abs_tol=5e-3)
    assert _back_collar_gap(drive.STRAP_T, 0.0) < _hub_gap() - 0.25
    # A perfectly set back collar sits >= 1.0 off the back block; it lands
    # there only as the rod's north stop.
    for t in _strap_t_band():
        collar_back = (
            drive.BLOCK_BACK_Z0 - t / 2.0 + (drive.CAM_LEN - drive.CAM_PIN_STATION[1])
        )
        assert drive.BLOCK_BACK_Z0 - collar_back >= 1.0
    # The model front collar is flush with the strap's outer face, one feeler
    # off the block.
    assert math.isclose(
        drive.CAM_Z0[0] - (drive.BLOCK_FRONT_Z0 + drive.BLOCK_DEPTH), 0.25, abs_tol=1e-9
    )


# MHA-060's and MHA-062's body lengths carry the title-block .X band (Main
# 2026-09-24: keep it loose).  Both are set back-flush at fit-up, so the band
# lands at their front ends; the back-end envelope below still takes the whole
# band at the back as well, so either reference is covered.
_ROD_LEN_BAND = RIG.LENGTH_BAND


def _stack_vertices():
    """Every vertex of the fitted stack: (front block inner and outer faces,
    back strap thickness).

    Measured from the back block's outer face, where the shaft and rod are set
    flush: the back block's depth in its .XX band (Codex #854 P1), both straps
    and the drum in their .X bands and the feeler in its ruled band (Codex #837
    P1) move the front block's inner face; its own .XX depth moves its outer
    face.  The back strap's own thickness also sets the back collar's gap, so
    it is carried separately.
    """
    import itertools

    t_lo, t_hi = _strap_t_band()
    d_block = (-RIG.BLOCK_DEPTH_BAND, RIG.BLOCK_DEPTH_BAND)
    inner_nominal = RIG.FRONT_BLOCK_Z0 + RIG.BLOCK_DEPTH
    for t_f, t_b, d_drum, d_feel, d_back, d_front in itertools.product(
        (t_lo, t_hi),
        (t_lo, t_hi),
        (-RIG.DRUM_LEN_BAND, RIG.DRUM_LEN_BAND),
        (-RIG.FRONT_BLOCK_FEELER_BAND, RIG.FRONT_BLOCK_FEELER_BAND),
        d_block,
        d_block,
    ):
        growth = (t_f - drive.STRAP_T) + (t_b - drive.STRAP_T) + d_drum + d_feel
        inner = inner_nominal - growth - d_back
        yield inner, inner - (RIG.BLOCK_DEPTH + d_front), t_b


def test_worst_stack_sizes_the_torque_shaft_and_the_lift_rod() -> None:
    # Codex #837 P1: the back-flush shaft and rod are fixed .X lengths, while
    # the front block swings with both straps, the drum and the feeler -- and,
    # Codex #854 P1, each block's .XX depth band on top.  At the longest stack the
    # shortest shaft must still bear 9.5 of the block, and the shortest rod
    # must stand the lever hub's bore plus the back collar's largest gap (and a
    # margin) proud, so the hub never becomes the rod's north stop.  Before
    # this, the 182.0 shaft bore 7.0 and the 192.0 rod stood 6.75 proud --
    # 1.25 short of even bottoming in the 8-deep bore; the 184.5 / 195.9 that
    # followed left out the blocks' own depth band (8.99 of bearing).
    from pinion_lever_geometry import BORE_DEPTH

    assert not hasattr(RIG, "STACK_BAND")  # the stacks name every term
    assert (RIG.TORQUE_SHAFT_LEN, RIG.LIFT_ROD_LEN) == (185.1, 197.0)
    assert math.isclose(RIG.BACK_COLLAR_GAP_MAX, 2.4, abs_tol=1e-9)
    bearing_min = math.inf
    hub_margin_min = math.inf
    nominal_inner = RIG.FRONT_BLOCK_Z0 + RIG.BLOCK_DEPTH
    # The sweep's longest stack is the named-term budget's growth, term for
    # term: everything in it but the nominal and the shaft's own band.
    growth = -sum(
        value
        for name, value in RIG.TORQUE_SHAFT_BEARING_STACK.items()
        if not name.startswith(("nominal", "MHA-062"))
    )
    assert math.isclose(
        max(nominal_inner - inner for inner, _o, _t in _stack_vertices()),
        growth,
        abs_tol=1e-9,
    )
    for inner, outer, t_b in _stack_vertices():
        for dl in (-_ROD_LEN_BAND, _ROD_LEN_BAND):
            shaft_front = RIG.BACK_BLOCK_OUTER_Z - (RIG.TORQUE_SHAFT_LEN + dl)
            bearing = inner - max(shaft_front, outer)
            bearing_min = min(bearing_min, bearing)
            rod_front = RIG.BACK_BLOCK_OUTER_Z - (RIG.LIFT_ROD_LEN + dl)
            hub_gap = outer - (rod_front + BORE_DEPTH)
            for e in (-_BACK_CAM_SET_ERR, _BACK_CAM_SET_ERR):
                margin = hub_gap - _back_collar_gap(t_b, e)
                hub_margin_min = min(hub_margin_min, margin)
    assert bearing_min >= RIG.FRONT_BLOCK_MIN_BEARING - 1e-9
    # The sweep's minimum is the layout's named-term budget, term for term.
    assert math.isclose(
        bearing_min, sum(RIG.TORQUE_SHAFT_BEARING_STACK.values()), abs_tol=1e-9
    )
    assert math.isclose(bearing_min, 9.59, abs_tol=5e-3)
    assert hub_margin_min >= RIG.HUB_STOP_MARGIN - 1e-9
    assert math.isclose(
        hub_margin_min,
        sum(RIG.LIFT_ROD_SEAT_STACK.values())
        - RIG.LEVER_SEAT_MIN
        + RIG.HUB_STOP_MARGIN,
        abs_tol=1e-9,
    )
    assert math.isclose(hub_margin_min, 0.33, abs_tol=5e-3)


def test_lever_station_clears_at_both_rod_extremes() -> None:
    # The lever rides the rod's front end, so its station moves with the rod's
    # length band and its float (north to the back collar's largest gap, south
    # to the front collar's widest feeler), never with the stack.  BDT's
    # z-proxy gates hold at every extreme, not only at the model pose.
    north = _ROD_LEN_BAND + RIG.BACK_COLLAR_GAP_MAX  # short rod, floated north
    south = _ROD_LEN_BAND + _P_MAX  # long rod, floated south
    shaft_front_south = drive.PIVOT_SHAFT_Z0 - _ROD_LEN_BAND  # longest shaft
    assert drive._LEV_Z[1] + north <= shaft_front_south - 0.25
    assert drive._LEV_Z[0] - south >= drive._GRIP_HEAD_Z[1] + 0.25
    hub_lo = drive.LEVER_Z - drive.LEVER_HUB_LEN / 2.0 - drive.LEVER_CAP_SAG
    assert hub_lo - south >= drive._GRIP_ROD_Z[1] + 0.25


def test_lift_rod_length_band_clears_past_the_back_block() -> None:
    import arbor_pedestal_spec as ped
    import harmonic_base_spec as base
    import pinion_rig_layout as rig
    from pinion_lift_rod_spec import CAP_SAG, ROD_DIA
    from rocker_arm_support_spec import SUPPORT_HALF_MACHINE_Z, SUPPORT_WORLD_Z

    rod_r = ROD_DIA / 2.0
    # Longest rod, floated hard north: the back collar is its north stop,
    # never the hub (test_worst_stack_sizes_the_torque_shaft_and_the_lift_rod),
    # so the body ends the band plus the collar's largest gap past the block.
    # The SR crown stands CAP_SAG beyond that (Codex #855 P2), and the envelope
    # runs to the crown's apex.
    body_end = rig.BACK_BLOCK_OUTER_Z + _ROD_LEN_BAND + rig.BACK_COLLAR_GAP_MAX
    assert math.isclose(body_end - rig.BACK_BLOCK_OUTER_Z, 3.2, abs_tol=5e-3)
    reach = body_end + CAP_SAG
    assert math.isclose(reach - rig.BACK_BLOCK_OUTER_Z, 4.4, abs_tol=5e-3)
    band = (rig.BACK_BLOCK_OUTER_Z, reach + 0.25)
    # Occupants of that z band near the rod axis (drive_train + frame):
    # the north arbor pedestal stands on the drum axis, well west of the rod.
    ped_z = (
        drive.ARBOR_PEDESTAL_NORTH_Z - ped.FOOT_DEPTH / 2.0,
        drive.ARBOR_PEDESTAL_NORTH_Z + ped.FOOT_DEPTH / 2.0,
    )
    assert ped_z[0] < band[1] and ped_z[1] > band[0]  # it IS in the band
    assert (drive.LIFT_X - rod_r) - (drive.X_DRUM + ped.FOOT_WIDTH / 2.0) >= 25.0
    # The rocker-arm support ends short of the back block's outer face.
    assert SUPPORT_WORLD_Z + SUPPORT_HALF_MACHINE_Z < band[0]
    # The base deck lies under the rod; its north rim is far past the reach.
    assert drive.LIFT_Y - rod_r - drive.Y_BASE_TOP >= 5.0
    assert base.TOP_WIDTH / 2.0 - base.LIP_W - band[1] >= 25.0
    # Nothing else in the pinion rig runs past the back block's outer face.
    assert math.isclose(
        drive.PIVOT_SHAFT_Z0 + rig.TORQUE_SHAFT_LEN,
        rig.BACK_BLOCK_OUTER_Z,
        abs_tol=1e-9,
    )


def test_torque_shaft_length_band_clears_both_ends() -> None:
    # MHA-062 at the title-block .X band (U27), set back-flush: at the
    # shortest stack (both blocks thin, Codex #854 P1) the longest shaft's
    # body end stands 7.47 proud of the front block, and its SR crown 1.2
    # beyond that (Codex #837 P1).
    import arbor_pedestal_spec as ped
    import pinion_lever_geometry as lever
    import pinion_rig_layout as rig
    from pinion_pivot_shaft_spec import CAP_SAG, SHAFT_DIA
    from rocker_arm_support_spec import SUPPORT_HALF_MACHINE_Z, SUPPORT_WORLD_Z

    front_end = rig.BACK_BLOCK_OUTER_Z - rig.TORQUE_SHAFT_LEN - _ROD_LEN_BAND
    # The shortest stack mirrors the named-term long stack of the front
    # block's OUTER face (both blocks' depths, both straps, the drum and the
    # feeler: the lift rod's budget less its nominal and the rod's own band),
    # since every nominal in it prints exactly.
    shrink = -sum(
        value
        for name, value in rig.LIFT_ROD_SEAT_STACK.items()
        if not name.startswith(("nominal", "MHA-060"))
    )
    shortest_outer = rig.FRONT_BLOCK_Z0 + shrink
    proud = shortest_outer - front_end
    assert math.isclose(proud, 7.47, abs_tol=5e-3)
    assert math.isclose(proud + CAP_SAG, 8.67, abs_tol=5e-3)
    assert math.isclose(
        max(outer for _i, outer, _t in _stack_vertices()), shortest_outer, abs_tol=1e-9
    )
    # Option E-a: pinned to the straps, the shaft rides the cluster's end play
    # from its back-flush drilling station to the front stop.
    assert math.isclose(proud + _P_MAX, 7.82, abs_tol=5e-3)
    assert math.isclose(proud + _P_MAX + CAP_SAG, 9.02, abs_tol=5e-3)
    # South of the front block nothing stands on the shaft's axis at any z.
    # The nearest body is the MHA-059 lever on the lift rod: its hub keeps
    # 8.95 radial clearance, and its arm points away from the shaft over the
    # whole throw.  (BDT's lever-plane gate compares z only, as a proxy.)
    shaft_r = SHAFT_DIA / 2.0
    rel = (drive.PIVOT_X - drive.LIFT_X, drive.PIVOT_Y - drive.LIFT_Y)
    hub_clear = math.hypot(*rel) - lever.HUB_OD / 2.0 - shaft_r
    assert math.isclose(hub_clear, 8.95, abs_tol=5e-3)
    arm_r = drive.LEVER_ROD_DIA / 2.0
    steps = 200
    for k in range(steps + 1):
        t = math.radians(
            drive.LEVER_TILT_DEG + drive.CAM_ENGAGE_ROTATION_DEG * k / steps
        )
        u = (-math.sin(t), math.cos(t))
        foot = min(max(rel[0] * u[0] + rel[1] * u[1], 0.0), drive.LEVER_LEN)
        gap = math.hypot(rel[0] - foot * u[0], rel[1] - foot * u[1])
        assert gap - arm_r - shaft_r >= 5.0, (k, gap)
    # The shortest shaft's bearing in the longest stack is swept in
    # test_worst_stack_sizes_the_torque_shaft_and_the_lift_rod.
    # Past the back block (the same band pushed north) nothing stands on the
    # shaft's axis: the north pedestal is well west, the rocker support ends
    # short of the block face, and the base deck lies under the shaft.
    assert (drive.PIVOT_X - shaft_r) - (drive.X_DRUM + ped.FOOT_WIDTH / 2.0) >= 25.0
    assert SUPPORT_WORLD_Z + SUPPORT_HALF_MACHINE_Z < rig.BACK_BLOCK_OUTER_Z
    assert drive.PIVOT_Y - shaft_r - drive.Y_BASE_TOP >= 5.0


def test_short_lift_rod_keeps_its_back_collar_and_bearing() -> None:
    import pinion_rig_layout as rig

    # Shortest rod, hard south (front collar on the front block, set at the
    # widest feeler): the back end's retreat from the back block's outer face.
    rod_end = rig.BACK_BLOCK_OUTER_Z - _ROD_LEN_BAND - (rig.FRONT_BLOCK_FEELER + 0.10)
    collar_back = drive.CAM_Z0[1] + drive.CAM_LEN - (rig.FRONT_BLOCK_FEELER + 0.10)
    assert rod_end - collar_back >= 1.0
    # The rod still bears across most of the back block's bore.
    assert rod_end - drive.BLOCK_BACK_Z0 >= 2.0 / 3.0 * drive.BLOCK_DEPTH


# The cam's M2.5 set screw is tapped radially on its heavy side, at the
# collar's mid-length, and the follower pins sweep over that station
# (front T/2 = 4.5).  The hole stays clear of the follower because it sits
# round the far side of the cam, not because of the axial offset.  Sweep the
# whole engage throw with the strap swing, plus over-travel.
_CAM_OVERTRAVEL_DEG = 10.0
_HOLE_CONTACT_MARGIN_DEG = 45.0


def _hole_to_contact_deg(rotation_deg: float, swing: float) -> float:
    """Angle at the cam centre between the tapped hole and the follower contact."""
    import pinion_cam_geometry as cam

    a = math.radians(rotation_deg)
    hole = (math.sin(a), -math.cos(a))  # heavy side: along the eccentricity
    centre = (drive.LIFT_X + cam.ECC * hole[0], drive.LIFT_Y + cam.ECC * hole[1])
    cs, sn = math.cos(swing), math.sin(swing)
    px, py = drive._FPIN_C[0] - drive.PIVOT_X, drive._FPIN_C[1] - drive.PIVOT_Y
    pin = (drive.PIVOT_X + px * cs - py * sn, drive.PIVOT_Y + px * sn + py * cs)
    nx, ny = drive._SPR_N
    n = (nx * cs - ny * sn, nx * sn + ny * cs)
    n_len = math.hypot(*n)
    n = (n[0] / n_len, n[1] / n_len)
    r = (pin[0] - centre[0], pin[1] - centre[1])
    t = r[0] * n[0] + r[1] * n[1]
    foot = (r[0] - t * n[0], r[1] - t * n[1])  # centre -> nearest pin-axis point
    foot_len = math.hypot(*foot)
    cos_gap = (hole[0] * foot[0] + hole[1] * foot[1]) / foot_len
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_gap))))


def test_cam_set_screw_hole_stays_clear_of_the_follower() -> None:
    import pinion_cam_geometry as cam

    # The axial bands DO overlap, so the angular gap is what keeps them apart.
    hole_band = (
        cam.SET_SCREW_Z - cam.TAP_DRILL_DIA / 2.0,
        cam.SET_SCREW_Z + cam.TAP_DRILL_DIA / 2.0,
    )
    for stations in _follower_stations():
        pin_band = (
            min(stations) - drive.FPIN_DIA / 2.0,
            max(stations) + drive.FPIN_DIA / 2.0,
        )
        assert pin_band[0] < hole_band[1] and pin_band[1] > hole_band[0]
    # Tap-drill half-angle seen from the cam centre at the OD.
    half = math.degrees(math.asin(cam.TAP_DRILL_DIA / cam.CAM_OD))
    assert math.isclose(half, 8.07, abs_tol=0.01)
    end = drive.CAM_ENGAGE_ROTATION_DEG - _CAM_OVERTRAVEL_DEG
    gaps = [
        _hole_to_contact_deg(end * i / 120, drive._PHI_ENG * j / 20)
        for i in range(121)
        for j in range(21)
    ]
    assert min(gaps) - half >= _HOLE_CONTACT_MARGIN_DEG, min(gaps)
    # At the photographed engage, with the strap fully swung: 83.5 deg.
    engaged = _hole_to_contact_deg(drive.CAM_ENGAGE_ROTATION_DEG, drive._PHI_ENG)
    assert math.isclose(engaged, 83.52, abs_tol=0.05)
    assert math.isclose(engaged - half, 75.45, abs_tol=0.05)


def test_set_pin_holes_sit_under_the_pose_straps_and_the_hardware_straps() -> None:
    # Option E-a: MHA-062's holes are match-drilled through the MHA-056 cross
    # holes with the shaft back-flush and the cluster at the back stop.  The
    # model holds them under the POSE's strap mid-planes, so the saved model
    # shows the pin axes through both parts; the hardware's strap stations
    # carry 2 x STRAP_AIR less between them (the M2 pose-air rule).
    import pinion_rig_layout as rig
    from pinion_pivot_shaft_spec import PIN_HOLE_Z, SHAFT_LEN

    t = drive.STRAP_T
    model_mid = [(o + i) / 2.0 for o, i in zip(rig.STRAP_Z_OUTER, rig.STRAP_Z_INNER)]
    for z_hole, mid in zip(PIN_HOLE_Z, model_mid):
        assert math.isclose(rig.TORQUE_SHAFT_Z0 + z_hole, mid, abs_tol=1e-9)
    from_back = [SHAFT_LEN - z for z in PIN_HOLE_Z]  # (front, back)
    physical_back = drive.BLOCK_DEPTH + t / 2.0
    physical_front = physical_back + t + rig.DRUM_LEN
    assert math.isclose(from_back[1], physical_back, abs_tol=1e-9)
    assert math.isclose(from_back[1], 14.75, abs_tol=1e-9)
    assert math.isclose(from_back[0] - physical_front, 2.0 * rig.STRAP_AIR)
    # Both holes stay well inside the body, clear of the crown roots.
    assert min(PIN_HOLE_Z) >= 10.0
    assert max(PIN_HOLE_Z) <= SHAFT_LEN - 10.0


def test_set_pin_never_stands_proud_and_keeps_its_webs() -> None:
    # Option E-a: the pin's west end faces the MHA-104 cam collar, whose air
    # to the strap foot is 0.38 at the printed worst case.  The longest pin
    # (B18.8.2 length +/-0.010 in) fits inside the narrowest strap foot (the
    # .X end-cap radius at its minimum), so driven flush-or-below on the west
    # edge it is buried on the east edge too: it can never eat that air.
    import pinion_strap_pin_spec as pin

    assert pin.PIN_STANDARD == "ASME B18.8.2"
    assert (pin.PIN_DIA, pin.PIN_LEN) == (25.4 / 16.0, 25.4 / 2.0)
    # B18.8.2's recommended 1/16 hole is 0.062-0.065 in.
    assert 0.062 * 25.4 <= pin.HOLE_DIA
    assert pin.HOLE_MAX <= 0.065 * 25.4
    assert math.isclose(pin.PIN_CENTRED_SUB_FLUSH, 0.35, abs_tol=1e-9)
    assert math.isclose(pin.STRAP_FOOT_MIN_WIDTH, 2.0 * (drive.STRAP_R_END - 0.8))
    assert pin.PIN_LEN + pin.PIN_LEN_BAND <= pin.STRAP_FOOT_MIN_WIDTH
    assert pin.PIN_BURIED_MARGIN >= 0.4
    # Engagement in each strap wall past the pivot bore.
    assert pin.PIN_LEN / 2.0 - drive.STRAP_PIVOT_BORE / 2.0 >= 3.0
    # U27 webs: strap faces and follower seat at the 2.0 target (the far
    # strap face against the .XX-printed station, Codex #858 P2); the shaft
    # ligament at the FULL general .XX offset meets the 1.5 floor, and a
    # 0.25 V-block set-up clears the 2.0 target.
    assert math.isclose(pin.STRAP_FACE_WEB_WORST, 2.316, abs_tol=5e-4)
    assert pin.STRAP_FACE_WEB_WORST >= 2.0
    assert pin.FOLLOWER_SEAT_LIGAMENT >= 2.0
    assert math.isclose(pin.SHAFT_LIGAMENT_WORST, 1.831, abs_tol=5e-4)
    assert pin.SHAFT_LIGAMENT_WORST >= 1.5
    assert math.isclose(pin.SHAFT_LIGAMENT_QUARTER, 2.091, abs_tol=5e-4)


def test_torque_shaft_is_phased_to_the_straps_and_swings_with_them() -> None:
    # Option E-a: the shaft's pin-hole axis (local X) lies along the straps'
    # cross holes at the park lean, and verify:soundness admits the shaft into
    # the drive train's free swing family.
    from _assembly import allowed_free_stems
    from pinion_pivot_shaft_spec import SHAFT_DIA

    strap_rows = drive.compose_rows(
        drive.ROT_Y_180, drive.rot_z_rows(drive.STRAP_LEAN_DEG)
    )
    dot = sum(a * b for a, b in zip(drive.TORQUE_SHAFT_ROWS[0], strap_rows[0]))
    assert math.isclose(abs(dot), 1.0, abs_tol=1e-12)
    assert drive.TORQUE_SHAFT_ROWS[2] == [0.0, 0.0, 1.0]
    assert "pinion-pivot-shaft" in allowed_free_stems("drive-train")
    assert SHAFT_DIA == drive.STRAP_PIVOT_BORE
