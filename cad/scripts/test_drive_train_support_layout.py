"""Offline invariants for the recentered alignment-pinion support closure."""

from __future__ import annotations

import math

import pytest

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


def test_mha135_is_shown_trimmed_flush_in_its_installed_configuration() -> None:
    # Codex #858 P2: the assembly shows MHA-135 as assembly leaves it, trimmed
    # and peened flush with the hub, not the 16.0 overlength cut the part's
    # drawing prints.  The part carries both as configurations with one BOM
    # identity, and BDT places the installed one.
    import ast
    import inspect

    import build_pinion_lever_pin as pin_build
    import pinion_lever_pin_geometry as pin
    from pinion_lever_geometry import HUB_OD

    assert pin.INSTALLED_LEN == HUB_OD < pin.PIN_LEN
    calls = [
        node
        for node in ast.walk(ast.parse(inspect.getsource(drive)))
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "place_component"
        and any(
            isinstance(arg, ast.Constant) and arg.value == "pinion-lever-pin"
            for arg in node.args
        )
    ]
    assert len(calls) == 1
    keywords = {kw.arg: kw.value for kw in calls[0].keywords}
    configuration = keywords["configuration"]
    assert isinstance(configuration, ast.Name)
    assert configuration.id == "LEVER_PIN_INSTALLED_CONFIG"
    assert drive.LEVER_PIN_INSTALLED_CONFIG == pin.INSTALLED_CONFIG
    source = inspect.getsource(pin_build)
    assert "(INSTALLED_CONFIG, INSTALLED_LEN)" in source
    assert "(default_config, PIN_LEN)" in source
    assert "apply_grouped_bom_properties(" in source


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


# Ruling (c) worst-case stack (user, 2026-09-24), under option E-a (Main,
# restricted review of #858).  Both straps are pinned to the torque shaft, so
# the strap / shaft / strap group slides between the blocks as one: its end
# play is the front-block feeler setting, P = 0.25 +/- 0.10, split between the
# front block gap g_f and the back block gap g_b (g_f + g_b = P).  The two
# drum-end gaps are frozen at the shim the shaft was drilled on, not a free
# share of P: the drum turns in DRUM_END_SHIM +/- DRUM_END_SHIM_SET_ERROR of
# air, split between its ends.  The saved pose is the drilling set-up, g_b = 0
# and the drum hard on the back strap.  Every quantity below is linear in the
# gaps, so the extremes sit at the vertices swept here.
#
# The lift rod floats axially.  Southward, the front cam collar stops on the
# front block's inner face; it is set there with the same 0.25 feeler, so up
# to 0.35 of play.  Northward, the lever hub does NOT bear on the front block
# (its bore takes 8 of the rod's LEVER_SEAT_PROUD, leaving it at least the back
# collar's largest gap plus 0.25 off the block face at the worst stack, Codex
# #837), so the rod runs north until the back cam collar lands on the back
# block -- at most its leaf F plus the set error (user ruling P1-1) -- and the
# hub never stops it.  Main 2026-09-24: keep that
# float, since every follower gate below holds at its true extremes.  The rod
# is set back-flush, so its travel is measured from there against the front
# block (pinion_rig_layout: the pose is the fit-up stack, Codex #854).
_P_MAX = FITUP.FRONT_BLOCK_FEELER + FITUP.FRONT_BLOCK_FEELER_BAND
_P_MIN = FITUP.FRONT_BLOCK_FEELER - FITUP.FRONT_BLOCK_FEELER_BAND
_AIR_MAX = RIG.DRUM_END_SHIM + RIG.DRUM_END_SHIM_SET_ERROR  # the drum's end play
_FEELER_BAND = (  # front collar set gap to the block
    FITUP.FRONT_BLOCK_FEELER - FITUP.FRONT_BLOCK_FEELER_BAND,
    FITUP.FRONT_BLOCK_FEELER + FITUP.FRONT_BLOCK_FEELER_BAND,
)
_LEAF_ERR = RIG.FEELER_SET_ERROR  # every gage leaf sets to the feeler's band


def _hub_gap() -> float:
    """Lever hub to the front block, with the rod set back-flush."""
    import pinion_rig_layout as rig

    hub_north = drive.LEVER_Z + drive.LEVER_HUB_LEN / 2.0
    hub_gap = rig.FRONT_BLOCK_Z0 - hub_north
    assert hub_gap >= 0.25, hub_gap
    return hub_gap


def _back_collar_gap(e: float) -> float:
    """Back collar to back block as set: its back face on leaf F, to +/- e
    (user ruling P1-1).  No strap, collar-length or by-eye term reaches it."""
    return RIG.BACK_COLLAR_LEAF_F + e


def _strap_t_band() -> tuple[float, float]:
    from _printed_tolerance import printed_deviations
    from pinion_bracket_geometry import THICKNESS_PLACES

    lower, upper = printed_deviations(drive.STRAP_T, THICKNESS_PLACES)
    return (drive.STRAP_T + lower, drive.STRAP_T + upper)


def test_j19_keeps_its_full_face_at_the_worst_stack() -> None:
    # User ruling P1-2: with the cluster hard back and the drum hard on the
    # back strap, the drum's back end is set RIG_SET_LEAF_D off g19's back
    # face.  From there it can only advance: the leaf sets to its band, the
    # pinned cluster runs forward to the front block (g_b = P) and the drum
    # forward in its shimmed end play.  The strap is set past, never measured
    # through, so its thickness sweeps without effect.  j = 19 keeps its FULL
    # 3.0 face there, the old floor of 2.0 a fortiori.
    g19_front = drive.Z_DRUM0 + 19 * drive.Z_PITCH - drive.DRUM_FACE / 2.0
    g19_back = g19_front + drive.DRUM_FACE
    backs = [
        g19_back + RIG.RIG_SET_LEAF_D + d - g_b - a
        for _t in _strap_t_band()
        for d in (-_LEAF_ERR, _LEAF_ERR)
        for g_b in (0.0, _P_MAX)
        for a in (0.0, _AIR_MAX)
    ]
    worst = min(min(back, g19_back) - g19_front for back in backs)
    assert worst >= 2.0, worst
    assert math.isclose(worst, drive.DRUM_FACE, abs_tol=1e-9)
    # The layout's named-term advance is this sweep, term for term, and the
    # assembly asserts it at import.
    assert math.isclose(
        min(backs),
        drive.APINION_Z_BACK - sum(RIG.DRUM_BACK_ADVANCE_STACK.values()),
        abs_tol=1e-9,
    )
    assert math.isclose(min(backs) - g19_back, drive.J19_FULL_FACE_MARGIN, abs_tol=1e-9)
    # D is the thinnest gage setting that leaves RIG_MARGIN_SPARE: one leaf
    # step thinner leaves j = 19 short of it.
    assert math.isclose(drive.J19_FULL_FACE_MARGIN, RIG.RIG_MARGIN_SPARE, abs_tol=1e-9)
    assert drive.J19_FULL_FACE_MARGIN - RIG.FEELER_LEAF_STEP < RIG.RIG_MARGIN_SPARE
    assert (RIG.RIG_SET_LEAF_D, RIG.RIG_SET_LEAVES) == (1.25, (1.00, 0.25))
    # j = 0 at the front: the drum's front end never uncovers gear 0, even
    # with the thickest leaf D and the shortest drum (the drum hard aft, the
    # pose).
    g0_front = drive.Z_DRUM0 - drive.DRUM_FACE / 2.0
    face_min = drive.APINION_DRUM_LEN - RIG.DRUM_LEN_BAND
    slack = min(
        (g0_front - 1.0) - (g19_back + RIG.RIG_SET_LEAF_D + d - face_min)
        for d in (-_LEAF_ERR, _LEAF_ERR)
    )
    assert slack >= 0.0, slack
    assert math.isclose(slack, drive.J0_SLACK_WORST, abs_tol=1e-9)
    assert math.isclose(slack, 2.976, abs_tol=5e-4)


def test_rig_set_leaf_d_derives_the_shift_and_leaves_743_open() -> None:
    # User ruling P1-2 (D primary, s derived): the drum's back end is set off
    # g19 directly, so neither the strap thickness nor g19's own station is a
    # term of either stack, and RIG_AFT_SHIFT is what the set-up leaves.
    for stack in (RIG.DRUM_BACK_ADVANCE_STACK, RIG.DRUM_FRONT_RETREAT_STACK):
        for name in stack:
            assert "MHA-056" not in name and "strap" not in name.lower(), name
            assert "MHA-027" not in name and "g19" not in name, name
    assert math.isclose(
        sum(RIG.DRUM_BACK_ADVANCE_STACK.values()) + RIG.RIG_MARGIN_SPARE,
        RIG.RIG_SET_LEAF_D,
        abs_tol=1e-9,
    )
    assert RIG.RIG_SET_LEAF_D == RIG.smallest_leaf_setting(
        sum(RIG.DRUM_BACK_ADVANCE_STACK.values()) + RIG.RIG_MARGIN_SPARE
    )
    assert math.isclose(
        RIG.BACK_STOP_Z,
        RIG.G19_BACK_FACE_Z + RIG.RIG_SET_LEAF_D + drive.STRAP_T,
        abs_tol=1e-12,
    )
    assert math.isclose(
        RIG.RIG_AFT_SHIFT,
        RIG.BACK_STOP_Z - RIG.U28_BACK_STOP_Z - drive.MECHANISM_Z_SHIFT,
        abs_tol=1e-12,
    )
    assert not hasattr(RIG, "RIG_AFT_SHIFT_STEP")
    # The layout's g19 literal is the gear grid's.
    g19_back = drive.Z_DRUM0 + 19 * drive.Z_PITCH + drive.DRUM_FACE / 2.0
    assert math.isclose(RIG.G19_BACK_FACE_Z, g19_back, abs_tol=1e-9)
    # User ruling (E_b): the bank's own terms come from the #743 retention
    # design.  Until then they are named, open, and never valued.
    # D is set with the bank pushed north (#743 rider): g19 then never sits
    # north of the datum, so the bank adds nothing to the advance -- and the
    # print must say so, or the stack would have to carry E_b max.
    assert RIG.DRUM_BACK_ADVANCE_OPEN_TERMS == ()
    assert FITUP.RIG_SET_BANK_PRECONDITION == "BANK PUSHED NORTH"
    assert FITUP.RIG_SET_STEP.endswith(",\nBANK PUSHED NORTH;")
    assert RIG.DRUM_FRONT_RETREAT_OPEN_TERMS == (
        "MHA-027 bank end play E_b (#743)",
        "MHA-027 g0 -> g19 pitch stack (#743)",
    )
    for stack in (RIG.DRUM_BACK_ADVANCE_STACK, RIG.DRUM_FRONT_RETREAT_STACK):
        assert not any("E_b" in name or "#743" in name for name in stack)
    rows = [name for name in drive.RIG_MARGINS if name.startswith(("j = 19", "j = 0"))]
    assert rows == [
        "j = 19 past its full face (bank pushed north)",
        "j = 0 drum overhang slack (rig terms; #743 open)",
    ]


def test_rig_aft_shift_is_the_one_rig_to_frame_move() -> None:
    # RIG_AFT_SHIFT (derived from leaf D, user ruling P1-2) moves every rig
    # station together, so the rig-internal margins cannot move; the
    # rig-to-frame ones it touches keep their floors.
    import arbor_pedestal_spec as ped
    import harmonic_base_spec as base
    from build_cylinder_end_disc import DISC_DIA
    from connecting_rod_spec import RING_OUTER_RADIUS
    from cylinder_gear_spec import ECCENTRICITY

    assert math.isclose(
        RIG.BACK_STOP_Z,
        77.75 + RIG.RIG_AFT_SHIFT + drive.MECHANISM_Z_SHIFT,
        abs_tol=1e-12,
    )
    # Past g19 the drum runs into the north end disc's z band; engaged, its
    # tips stand clear of the disc rim, as they already stand clear of g0's
    # cam and connecting-rod ring at the other end.
    assert drive.ENGAGED_C2C - drive.TIP_APINION - DISC_DIA / 2.0 >= 2.5
    assert (
        drive.ENGAGED_C2C - drive.TIP_APINION - (RING_OUTER_RADIUS + ECCENTRICITY)
        >= 1.0
    )
    # The back block now shares the north pedestal foot's z band; they stand
    # apart in x.
    block_east = drive.BLOCK_X - BLOCK_EAST
    assert block_east - (drive.X_DRUM + ped.FOOT_WIDTH / 2.0) >= 19.0
    # The grip keeps opening from the crank cluster.  Nominal floor re-pinned
    # for the P1-2 rig shift (12.5 -> 12.0: the rig sits 0.776 further south);
    # the worst case gates it (RIG_MARGINS' grip crossrod row, 9.312 vs 0.25).
    assert drive._GRIP_ROD_Z[0] - (drive.REMOVABLE_Z0 + 5.0) >= 12.0
    assert (
        drive.RIG_MARGINS["grip crossrod to the T12 chain wheel"][0]
        >= 0.25 + RIG.RIG_MARGIN_SPARE
    )
    assert drive._GRIP_HEAD_Z[0] - (drive.CRANK_ARM_Z0 + drive.ARM_THICKNESS) >= 21.5
    # The base rim still stands far past the rod's reach and every seat.
    assert base.TOP_WIDTH / 2.0 - base.LIP_W - RIG.BACK_BLOCK_OUTER_Z >= 25.0


def _follower_stations() -> tuple[list[float], list[float]]:
    """Follower-pin stations from each collar's front face, at every vertex."""
    import itertools

    # c is the front collar's gap to the front block's inner face: 0 with the
    # rod hard south, up to the first north stop (back collar on the back
    # block, else the hub on the front block).  The back collar is set on its
    # leaf at c_set with the cluster hard back, its back face F + e off the
    # block and the pin on the strap's mid-plane t/2 inside it; the strap then
    # moves forward by g_b and the rod north by c - c_set.
    # The pinned cluster splits its end play P between the block gaps, so the
    # extremes are all of it at one block or the other (option E-a).
    front, back = [], []
    splits = [(p, 0.0) for p in (_P_MIN, _P_MAX)] + [(0.0, p) for p in (_P_MIN, _P_MAX)]
    for (g_f, g_b), t, c_set, e in itertools.product(
        splits,
        _strap_t_band(),
        _FEELER_BAND,
        (-_LEAF_ERR, _LEAF_ERR),
    ):
        gap = _back_collar_gap(e)
        assert gap >= RIG.BACK_COLLAR_MIN_GAP + RIG.RIG_MARGIN_SPARE - 1e-9, e
        c_max = c_set + min(_hub_gap(), gap)
        set_station = drive.CAM_LEN + gap - t / 2.0
        for c in (0.0, c_max):
            front.append(g_f + t / 2.0 - c)
            back.append(set_station - g_b - (c - c_set))
    return front, back


def test_follower_pins_stay_on_their_collars_at_the_worst_stack() -> None:
    front, back = _follower_stations()
    assert math.isclose(drive.CAM_PIN_STATION[0], drive.STRAP_T / 2.0)
    for stations in (front, back):
        assert min(stations) >= 1.0, stations
        assert max(stations) <= drive.CAM_LEN - 1.0, stations
    # User ruling P1-1: on its leaf the back collar's gap -- the rod's north
    # float -- is F + e at most 1.00, so both pins keep >= 2.75 of collar on
    # either side (the by-eye set it replaced left 1.90 and 2.75).
    assert math.isclose(min(front), 2.75, abs_tol=5e-3)
    assert math.isclose(min(back), 3.75, abs_tol=5e-3)
    assert math.isclose(max(back), drive.CAM_LEN - 2.75, abs_tol=5e-3)
    # North float at the widest setting: the back collar lands first.
    assert _back_collar_gap(_LEAF_ERR) < _hub_gap() - RIG.HUB_STOP_MARGIN
    # The model's back collar sits on its leaf, its pin BACK_CAM_PIN_STATION
    # into it at the nominal strap, and the collar lands on the block only as
    # the rod's north stop.
    assert math.isclose(
        drive.BLOCK_BACK_Z0 - (drive.CAM_Z0[1] + drive.CAM_LEN),
        RIG.BACK_COLLAR_LEAF_F,
        abs_tol=1e-9,
    )
    assert drive.CAM_PIN_STATION[1] == RIG.BACK_CAM_PIN_STATION
    assert math.isclose(RIG.BACK_CAM_PIN_STATION, 5.40, abs_tol=1e-9)
    assert (RIG.BACK_COLLAR_GAP_MIN, RIG.BACK_COLLAR_GAP_MAX) == pytest.approx(
        (0.80, 1.00), abs=1e-9
    )
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
    and the drum in their .X bands, and the drum shim and the feeler in their
    ruled band (Codex #837 P1) move the front block's inner face; its own .XX
    depth moves its outer face.  The back strap's own thickness also sets the back collar's gap, so
    it is carried separately.
    """
    import itertools

    t_lo, t_hi = _strap_t_band()
    d_block = (-RIG.BLOCK_DEPTH_BAND, RIG.BLOCK_DEPTH_BAND)
    inner_nominal = RIG.FRONT_BLOCK_Z0 + RIG.BLOCK_DEPTH
    d_shim = (-RIG.DRUM_END_SHIM_SET_ERROR, RIG.DRUM_END_SHIM_SET_ERROR)
    for t_f, t_b, d_drum, d_air, d_feel, d_back, d_front in itertools.product(
        (t_lo, t_hi),
        (t_lo, t_hi),
        (-RIG.DRUM_LEN_BAND, RIG.DRUM_LEN_BAND),
        d_shim,
        (-RIG.FRONT_BLOCK_FEELER_BAND, RIG.FRONT_BLOCK_FEELER_BAND),
        d_block,
        d_block,
    ):
        growth = (t_f - drive.STRAP_T) + (t_b - drive.STRAP_T) + d_drum + d_air + d_feel
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
    assert (RIG.TORQUE_SHAFT_LEN, RIG.LIFT_ROD_LEN) == (187.0, 198.3)
    assert math.isclose(RIG.BACK_COLLAR_GAP_MAX, 1.00, abs_tol=1e-9)
    bearing_min = math.inf
    hub_margin_min = math.inf
    nominal_inner = RIG.FRONT_BLOCK_Z0 + RIG.BLOCK_DEPTH
    # The sweep's longest stack is the named-term budget's growth, term for
    # term: everything in it but the nominal and the shaft's own length and
    # flush setting.
    shaft_own = ("nominal", "MHA-062 shaft length", "MHA-062 rear end flush")
    growth = -sum(
        value
        for name, value in RIG.TORQUE_SHAFT_BEARING_STACK.items()
        if not name.startswith(shaft_own)
    )
    assert math.isclose(
        max(nominal_inner - inner for inner, _o, _t in _stack_vertices()),
        growth,
        abs_tol=1e-9,
    )
    flush = (-RIG.FLUSH_SET_ERROR, RIG.FLUSH_SET_ERROR)  # rear end past the face
    for inner, outer, t_b in _stack_vertices():
        for dl in (-_ROD_LEN_BAND, _ROD_LEN_BAND):
            for f in flush:
                shaft_front = RIG.BACK_BLOCK_OUTER_Z + f - (RIG.TORQUE_SHAFT_LEN + dl)
                bearing = inner - max(shaft_front, outer)
                bearing_min = min(bearing_min, bearing)
            rod_front = RIG.BACK_BLOCK_OUTER_Z - (RIG.LIFT_ROD_LEN + dl)
            hub_gap = outer - (rod_front + BORE_DEPTH)
            for e in (-_LEAF_ERR, _LEAF_ERR):
                margin = hub_gap - _back_collar_gap(e)
                hub_margin_min = min(hub_margin_min, margin)
    assert bearing_min >= RIG.FRONT_BLOCK_MIN_BEARING + RIG.BLOCK_BEARING_MARGIN - 1e-9
    # The sweep's minimum is the layout's named-term budget, term for term.
    assert math.isclose(
        bearing_min, sum(RIG.TORQUE_SHAFT_BEARING_STACK.values()), abs_tol=1e-9
    )
    assert math.isclose(bearing_min, 10.09, abs_tol=5e-3)
    assert hub_margin_min >= RIG.HUB_STOP_MARGIN - 1e-9
    assert math.isclose(
        hub_margin_min,
        sum(RIG.LIFT_ROD_SEAT_STACK.values())
        - RIG.LEVER_SEAT_MIN
        + RIG.HUB_STOP_MARGIN,
        abs_tol=1e-9,
    )
    # The rod is sized by the lever's air to the shaft (below), which leaves
    # the seat more than it needs.
    assert math.isclose(hub_margin_min, 0.98, abs_tol=5e-3)


def test_lever_station_clears_at_both_rod_extremes() -> None:
    # The lever rides the rod's front end, so its throw plane moves with the
    # rod's length band and float (north to the back collar's largest gap,
    # south to the front collar's widest feeler) and its own printed bands.
    # The torque shaft's front end moves south with its own band, the pinned
    # cluster's end play and its flush set (P2-3).  The rig sizes MHA-060 so
    # the plane clears that front end, and the assembly logs the same row.
    north = RIG.LEVER_NORTH_TRAVEL_STACK
    assert north["MHA-060 floated north to the back collar"] == RIG.BACK_COLLAR_GAP_MAX
    shaft = RIG.SHAFT_FRONT_SOUTH_TRAVEL_STACK
    assert math.isclose(
        sum(shaft.values()), _ROD_LEN_BAND + _P_MAX + RIG.FLUSH_SET_ERROR
    )
    air = (drive.PIVOT_SHAFT_Z0 - sum(shaft.values())) - (
        drive._LEV_Z[1] + sum(north.values())
    )
    assert math.isclose(air, RIG.LEVER_TO_SHAFT_FRONT_WORST, abs_tol=1e-9)
    row = drive.RIG_MARGINS["lever throw plane to the torque shaft's front end"]
    assert math.isclose(row[0], air, abs_tol=1e-9)
    assert air >= RIG.LEVER_THROW_MIN_AIR + RIG.RIG_MARGIN_SPARE - 1e-9
    assert math.isclose(air, 0.54, abs_tol=5e-3)
    # One .X step shorter and the plane crowds the shaft.
    assert RIG.lever_to_shaft_front_worst(RIG.LIFT_ROD_LEN - 0.1) < (
        RIG.LEVER_THROW_MIN_AIR + RIG.RIG_MARGIN_SPARE
    )
    south = sum(RIG.LEVER_SOUTH_TRAVEL_STACK.values())
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
    assert math.isclose(body_end - rig.BACK_BLOCK_OUTER_Z, 1.80, abs_tol=5e-3)
    reach = body_end + CAP_SAG
    assert math.isclose(reach - rig.BACK_BLOCK_OUTER_Z, 3.00, abs_tol=5e-3)
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


def test_pinned_torque_shaft_bears_the_back_block_at_the_worst_stack() -> None:
    # Option E-a (Main, Codex #858): pinned to the straps, the shaft rides the
    # cluster's end play.  Drilled flush with the back block's outer face with
    # the cluster at the back stop, it retreats up to P_MAX into that block
    # when the cluster runs forward to the front block -- and the shallowest
    # accepted block is its printed depth less the .XX row.  It must still bear
    # the 1.5 D floor the front block keeps (rule 12).  The retired check read
    # the nominal depth only (10.25 - 0.35 = 9.90); at the printed worst case
    # the U28 block bore 9.39.  Main (#858, ruling 2): the flush setting it is
    # drilled at carries its own error, printed on MHA-062's drilling note.
    from _printed_tolerance import printed_band_mm
    from pinion_pivot_block_geometry import BLOCK_DEPTH_PLACES

    shallowest = drive.BLOCK_DEPTH - printed_band_mm(BLOCK_DEPTH_PLACES)
    bearing = shallowest - _P_MAX - RIG.FLUSH_SET_ERROR
    # Main (#858): a real margin, >= 0.5 over the floor, from geometry (the
    # 11.0 block), with every band kept; the 10.5 block left 0.04.
    assert bearing >= 9.5 + 0.5 - 1e-9, bearing
    assert RIG.BLOCK_BEARING_MARGIN == 0.5
    assert RIG.BACK_BLOCK_MIN_BEARING == RIG.FRONT_BLOCK_MIN_BEARING == 9.5
    # The layout's named-term stack is this sweep, term for term.
    assert math.isclose(
        sum(RIG.TORQUE_SHAFT_BACK_BEARING_STACK.values()), bearing, abs_tol=1e-9
    )
    assert math.isclose(bearing, 10.04, abs_tol=5e-3)
    # The drilling station: the shaft's back end flush with that outer face.
    assert math.isclose(
        drive.PIVOT_SHAFT_Z0 + RIG.TORQUE_SHAFT_LEN,
        RIG.BACK_BLOCK_OUTER_Z,
        abs_tol=1e-9,
    )


def test_torque_shaft_length_band_clears_both_ends() -> None:
    # MHA-062 at the title-block .X band (U27), set back-flush: at the
    # shortest stack (both blocks thin, Codex #854 P1) the longest shaft's
    # body end stands 7.52 proud of the front block, and its SR crown 1.2
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
    assert math.isclose(proud, 7.52, abs_tol=5e-3)
    assert math.isclose(proud + CAP_SAG, 8.72, abs_tol=5e-3)
    assert math.isclose(
        max(outer for _i, outer, _t in _stack_vertices()), shortest_outer, abs_tol=1e-9
    )
    # Option E-a: pinned to the straps, the shaft rides the cluster's end play
    # from its back-flush drilling station to the front stop.
    assert math.isclose(proud + _P_MAX, 7.87, abs_tol=5e-3)
    assert math.isclose(proud + _P_MAX + CAP_SAG, 9.07, abs_tol=5e-3)
    # Its back end then sits P_MAX inside the back block, bearing
    # test_pinned_torque_shaft_bears_the_back_block_at_the_worst_stack.
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


def test_set_pin_holes_sit_at_the_physical_back_stop_straps() -> None:
    # Option E-a: MHA-062's holes are match-drilled through the MHA-056 cross
    # holes with the shaft back-flush and the cluster at the back stop.  Codex
    # #858 P1: the released part is the manufactured shaft, so its holes sit
    # under the HARDWARE strap mid-planes (back strap hard on the back block,
    # drum and front strap closed up behind it).  Codex #854/#858 P1 (Main):
    # that fit-up stack is also the saved pose, so both strap cross holes
    # share an axis with the shaft's holes in the assembly.
    import pinion_rig_layout as rig
    from pinion_pivot_shaft_spec import (
        PIN_HOLE_BAND,
        PIN_HOLE_DIA,
        PIN_HOLE_Z,
        SHAFT_LEN,
    )

    t = drive.STRAP_T
    from_back = [SHAFT_LEN - z for z in PIN_HOLE_Z]  # (front, back)
    physical_back = drive.BLOCK_DEPTH + t / 2.0
    # Main (#858, ruling 3): drilled with the feeler as a shim at the drum's
    # front end, so the front strap stands the shim off the drum.
    physical_front = physical_back + t + rig.DRUM_LEN + rig.DRUM_END_SHIM
    assert math.isclose(from_back[1], physical_back, abs_tol=1e-9)
    assert math.isclose(from_back[1], 15.5, abs_tol=1e-9)
    assert math.isclose(from_back[0], physical_front, abs_tol=1e-9)
    # Against the pose: both strap mid-planes are the holes' stations.
    model_mid = [(o + i) / 2.0 for o, i in zip(rig.STRAP_Z_OUTER, rig.STRAP_Z_INNER)]
    world = [rig.TORQUE_SHAFT_Z0 + z for z in PIN_HOLE_Z]
    for hole, mid in zip(world, model_mid, strict=True):
        assert math.isclose(hole, mid, abs_tol=1e-9)
    # Each hole stays inside its strap's thickness at its band's maximum.
    hole_max = PIN_HOLE_DIA + PIN_HOLE_BAND[0]
    assert hole_max / 2.0 < t / 2.0
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
    assert math.isclose(pin.SHAFT_LIGAMENT_WORST, 1.826, abs_tol=5e-4)
    assert pin.SHAFT_LIGAMENT_WORST >= 1.5
    assert math.isclose(pin.SHAFT_LIGAMENT_QUARTER, 2.091, abs_tol=5e-4)


def test_mha145_strap_pins_sit_in_both_strap_cross_holes() -> None:
    # Codex #858 P2: the two E-a set pins are components, not only a mated
    # tie.  BDT inserts MHA-145 once per strap (front first), each centred in
    # its strap's cross hole -- the strap's local X line at CrossHoleCz =
    # StrapThickness / 2 through the pivot-bore axis -- with the strap's rows,
    # and locks it to that strap, so it joins the freed pinion swing family.
    # Codex #858 P1: each pin is also coaxial with its MHA-062 hole, because
    # the saved pose is the fit-up stack the holes are match-drilled in.
    import inspect

    from _assembly import allowed_free_stems
    from pinion_bracket_geometry import THICKNESS
    from pinion_pivot_shaft_spec import PIN_HOLE_Z

    source = inspect.getsource(drive)
    assert source.count('"pinion-strap-pin"') == 1
    assert 'zip(("front", "back"), STRAP_PIN_Z, strict=True)' in source
    assert 'named_ref(f"Front Plane@{strap_pins[tag]}", "PLANE")' in source
    assert 'label=f"strap pin {tag} locked to its strap"' in source
    assert len(drive.STRAP_PIN_Z) == 2
    strap_rows = drive.compose_rows(
        drive.ROT_Y_180, drive.rot_z_rows(drive.STRAP_LEAN_DEG)
    )
    strap_origin_z = (drive.RIG.STRAP_Z_INNER[0], drive.RIG.STRAP_Z_OUTER[1])
    for z0, z_pin in zip(strap_origin_z, drive.STRAP_PIN_Z, strict=True):
        hole = _world(
            [drive.PIVOT_X, drive.PIVOT_Y, z0], strap_rows, [0.0, 0.0, THICKNESS / 2.0]
        )
        pin_point = [drive.PIVOT_X, drive.PIVOT_Y, z_pin]
        assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(hole, pin_point))
    shaft_holes = [
        _world(
            [drive.PIVOT_X, drive.PIVOT_Y, drive.PIVOT_SHAFT_Z0],
            drive.TORQUE_SHAFT_ROWS,
            [0.0, 0.0, z],
        )[2]
        for z in PIN_HOLE_Z
    ]
    for z_hole, z_pin in zip(shaft_holes, drive.STRAP_PIN_Z, strict=True):
        assert math.isclose(z_hole, z_pin, abs_tol=1e-9)
    assert "pinion-strap-pin" in allowed_free_stems("drive-train")


def test_mha145_is_mcmaster_98296a027_and_a_purchased_bom_line() -> None:
    # Main: MHA-145 carries a real SKU like its purchased siblings.  The part
    # is the stock 98296A027 recipe (1/16 x 1/2, 0.012 in wall, as installed)
    # at the nominal length; the spec proves the longest pin the band allows
    # is still buried (PIN_BURIED_MARGIN).  The registry row is the
    # drive-train BOM line, qty 2.
    import inspect

    import _config
    import build_pinion_strap_pin as part
    import pinion_strap_pin_spec as pin
    from _buildgraph import part_stems, references_of
    from _drawing_registry import DRAWINGS_BY_NAME
    from _fastener_catalog import FASTENERS
    from _stock_fastener import STOCK_RECIPES
    from diagnostics import diag_build_98296A027 as recipe

    assert part.SPEC is FASTENERS["pinion-strap-pin"]
    assert part.SPEC.skus == ("98296A027",)
    source = inspect.getsource(part)
    assert 'sku="98296A027"' in source and "author=build_98296A027" in source
    assert STOCK_RECIPES["98296A027"].module == "diagnostics.diag_build_98296A027"
    assert (recipe.PIN_OD, recipe.PIN_LEN) == (pin.PIN_DIA, pin.PIN_LEN)
    assert math.isclose(pin.WALL_T, 0.012 * 25.4)
    assert math.isclose(recipe.PIN_ID, pin.PIN_DIA - 2.0 * pin.WALL_T)
    assert pin.PIN_LEN + pin.PIN_LEN_BAND <= pin.STRAP_FOOT_MIN_WIDTH
    row = _config.parts("pinion-strap-pin")
    assert row["number"] == "MHA-145"
    # Two E-a strap pins plus the R1a arbor-collar pin (#860, Main).
    assert int(row["quantity"]) == 3
    assert row["process"] == "purchased"
    assert tuple(row["supplier_skus"]) == ("98296A027",)
    assert row["stock_name"] == part.SPEC.stock_name
    assert DRAWINGS_BY_NAME["pinion_strap_pin"].script_name == (
        "draw_pinion_strap_pin.py"
    )
    assert "pinion_strap_pin" in part_stems()
    assert "pinion_strap_pin" in references_of("drive_train")


def test_drive_train_reads_no_shaft_or_pin_drawing_contract() -> None:
    # Restricted review (Main): BDT imported pinion_pivot_shaft_spec for the
    # pin-hole stations, and through it pinion_strap_pin_spec, so rewording a
    # note on MHA-062 re-keyed and fully rebuilt the drive train.  The stations
    # live in pinion_rig_layout; the specs re-export them.
    from pathlib import Path

    from _buildgraph import module_deps_of
    from pinion_pivot_shaft_spec import PIN_HOLE_Z

    deps = {Path(p).stem for p in module_deps_of(Path(drive.__file__))}
    assert not deps & {"pinion_pivot_shaft_spec", "pinion_strap_pin_spec"}, deps
    assert PIN_HOLE_Z is RIG.TORQUE_SHAFT_PIN_HOLE_Z


def test_mha145_pins_carry_no_interference_exemption() -> None:
    # Codex #858 P1: a straight pin cannot pass offset holes, so the gate must
    # never whitelist pin material inside the shaft.  Pin, strap hole and
    # shaft hole are the one 1/16 drill on one axis: line-to-line contact,
    # which the gate does not count.  The contracts therefore carry no strap
    # pin row and read neither the rig layout nor the pin spec.
    import inspect

    import _interference_contracts as ic

    pairs = ic.allowed_interference_pairs("drive-train")
    assert not [p for p in pairs if any(n.startswith("pinion-strap-pin") for n in p)]
    assert not [p for p in pairs if any(n.startswith("pinion-bracket") for n in p)]
    source = inspect.getsource(ic)
    for module in ("pinion_rig_layout", "pinion_strap_pin_spec"):
        assert module not in source, module


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


def test_drive_train_reads_no_arbor_drawing_contract() -> None:
    # Main (restricted review of #858): the drive train sizes the drum air and
    # the land margins from MHA-102, so it must read the arbor GEOMETRY module,
    # never pinion_arbor_spec -- a print-wording or precision edit there would
    # otherwise re-key the whole drive train.
    from pathlib import Path

    from _buildgraph import module_deps_of

    deps = {Path(dep).stem for dep in module_deps_of(Path(drive.__file__))}
    assert "pinion_arbor_geometry" in deps
    assert "pinion_arbor_spec" not in deps


def test_rig_anchors_are_named_not_literal() -> None:
    # Main (restricted review of #858): the back stop and the drum bond station
    # carry their derivations, not bare literals.
    import pinion_arbor_geometry as arbor

    assert math.isclose(RIG.U28_BACK_STOP_Z, 88.0 - 10.25, abs_tol=1e-12)
    assert math.isclose(
        RIG.BACK_STOP_Z,
        RIG.U28_BACK_STOP_Z + RIG.RIG_AFT_SHIFT + drive.MECHANISM_Z_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(
        arbor.DRUM_STATION_AS_BUILT,
        arbor.RELEASED_DRUM_FRONT_Z - arbor.RELEASED_ARBOR_ROOT_Z - arbor.HEAD_REAR_Z,
        abs_tol=1e-12,
    )
    assert math.isclose(arbor.DRUM_STATION_AS_BUILT, 61.25, abs_tol=1e-12)


def test_spring_pad_books_its_printed_width_band() -> None:
    # Main (restricted review of #858, P2-4): the pad width reads the band its
    # sheet prints, not a 0.51 literal.
    import inspect
    import re

    from _printed_tolerance import printed_deviations
    from pinion_spring_geometry import PAD_WIDTH, PAD_WIDTH_PLACES

    assert not re.search(r"\b0\.51\b", inspect.getsource(drive))
    upper = printed_deviations(PAD_WIDTH, PAD_WIDTH_PLACES)[1]
    assert math.isclose(drive.SPRING_PAD_WIDTH_WORST, PAD_WIDTH + upper, abs_tol=1e-12)


def test_spring_is_stationed_from_the_block_on_its_pad_leaf() -> None:
    # Main (restricted review of #858): MHA-114's pad is set SPRING_PAD_LEAF
    # off the back block's inner face before its seat is transferred.  The
    # blade then stands on the back strap's flank at exactly its floor plus
    # RIG_MARGIN_SPARE at the thinnest strap and the leaf's set error: that
    # row has no spare past the rule, so it is pinned exactly.
    from _printed_tolerance import printed_deviations
    from pinion_bracket_geometry import THICKNESS_PLACES
    from pinion_spring_geometry import PAD_WIDTH, PAD_WIDTH_PLACES, WIDTH

    assert RIG.SPRING_PAD_LEAF == 1.00
    assert math.isclose(
        RIG.SPRING_Z,
        RIG.BACK_BLOCK_Z0 - RIG.SPRING_PAD_LEAF - PAD_WIDTH / 2.0,
        abs_tol=1e-12,
    )
    assert math.isclose(drive.SPRING_Z, RIG.SPRING_Z, abs_tol=1e-12)
    inset = RIG.SPRING_Z - WIDTH / 2.0 - RIG.STRAP_Z_INNER[1]
    assert math.isclose(inset, RIG.SPRING_BLADE_INSET, abs_tol=1e-12)
    assert math.isclose(inset, 1.25, abs_tol=1e-9)
    thin = printed_deviations(drive.STRAP_T, THICKNESS_PLACES)[0]
    flank = inset + thin - RIG.FEELER_SET_ERROR
    assert flank == pytest.approx(RIG.SPRING_BLADE_ON_FLANK_WORST, abs=1e-12)
    assert flank == pytest.approx(
        RIG.SPRING_BLADE_MIN_ON_FLANK + RIG.RIG_MARGIN_SPARE, abs=1e-9
    )
    pad = (
        RIG.SPRING_PAD_LEAF
        - RIG.FEELER_SET_ERROR
        - printed_deviations(PAD_WIDTH, PAD_WIDTH_PLACES)[1] / 2.0
    )
    assert pad == pytest.approx(RIG.SPRING_PAD_TO_BLOCK_WORST, abs=1e-12)
    assert pad == pytest.approx(0.645, abs=1e-9)
    rows = drive.RIG_MARGINS
    assert rows["spring blade on the back strap flank"] == (
        RIG.SPRING_BLADE_ON_FLANK_WORST,
        RIG.SPRING_BLADE_MIN_ON_FLANK,
    )
    assert rows["spring foot pad to the back block"] == (
        RIG.SPRING_PAD_TO_BLOCK_WORST,
        RIG.SPRING_PAD_MIN_AIR,
    )


def test_every_fit_up_setting_is_a_gage_leaf_and_the_prints_name_it() -> None:
    # User rulings P1-1 / P1-2 and the spring pad: every setting is one leaf,
    # or D's pair, of the one purchased gage, and each print states its step.
    import draw_harmonic_base as base_sheet
    import pinion_cam_spec

    for name, leaf in FITUP.SINGLE_LEAF_SETTINGS.items():
        assert round(leaf, 2) in FITUP.FEELER_GAGE_LEAVES_MM, name
    assert FITUP.RIG_SET_LEAVES == (1.00, 0.25)
    assert FITUP.BACK_COLLAR_LEAF_F == 0.90
    assert FITUP.FRONT_COLLAR_LEAF == FITUP.FRONT_BLOCK_FEELER
    assert FITUP.RIG_SET_STEP == (
        "RIG SET: MHA-002 BACK END\n1.00 + 0.25 LEAVES OFF\n"
        "NORTH MHA-027 BACK FACE,\nBANK PUSHED NORTH;"
    )
    assert base_sheet.TRANSFER_BLOCK_CALLOUT.startswith(FITUP.RIG_SET_STEP)
    assert base_sheet.TRANSFER_SPRING_NOTE.startswith(FITUP.SPRING_SET_STEP)
    assert FITUP.SPRING_SET_STEP == "PAD 1.00 LEAF OFF MHA-061;"
    # The collars' set is an assembly step: nothing is cut, so MHA-104's own
    # print stays free of it (policy rule 6, as MHA-061 keeps its feeler).
    assert "LEAF" not in pinion_cam_spec.DRAWING_NOTES
    assert FITUP.COLLAR_SET_STEP.startswith("SET MHA-104 COLLARS ON STARRETT 66MA")
    assert "0.90 OFF BACK MHA-061" in FITUP.COLLAR_SET_STEP
    assert "0.25 OFF FRONT MHA-061" in FITUP.COLLAR_SET_STEP
    # The fit-up module no longer claims MHA-A03 prints the feeler band.
    assert "MHA-A03 prints" not in (FITUP.__doc__ or "")


def test_rig_margin_table_is_logged_at_build() -> None:
    # Main (restricted review of #858): the margin table is visible in the
    # task log, one line per row, not only asserted at import.
    import inspect

    lines = drive.rig_margin_lines()
    assert len(lines) == len(drive.RIG_MARGINS)
    for name, line in zip(drive.RIG_MARGINS, lines, strict=True):
        assert line.startswith(name), line
    source = inspect.getsource(drive.build)
    assert "rig_margin_lines()" in source
    # At info, so the farm leaf log (run at info) carries it.
    assert '_telemetry.info(f"rig margin {line}")' in source


def test_strap_pin_guard_reads_the_strap_parts_cross_holes() -> None:
    # Main (restricted review of #858): the lockstep guard compared two values
    # derived from the same rig stations, so it could never fire.  It now
    # takes each cross hole from the strap part (its placement and CROSS_HOLE_CZ)
    # and each shaft hole from the shaft part's own stations.
    from pinion_bracket_geometry import CROSS_HOLE_CZ, THICKNESS

    assert math.isclose(CROSS_HOLE_CZ, THICKNESS / 2.0, abs_tol=1e-12)
    strap_rows = drive.compose_rows(
        drive.ROT_Y_180, drive.rot_z_rows(drive.STRAP_LEAN_DEG)
    )
    for z0, z_hole in zip(drive.STRAP_ORIGIN_Z, drive.STRAP_CROSS_HOLE_Z, strict=True):
        world = _world(
            [drive.PIVOT_X, drive.PIVOT_Y, z0], strap_rows, [0.0, 0.0, CROSS_HOLE_CZ]
        )
        assert math.isclose(world[2], z_hole, abs_tol=1e-9)
    assert drive.STRAP_PIN_Z == drive.STRAP_CROSS_HOLE_Z
