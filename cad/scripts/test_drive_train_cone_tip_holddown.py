"""Import-time contracts for the cone tip block's hold-down stack in the drive train.

The block (MHA-DT-021) stands straight on the swing platform, held by one socket
head cap screw (MHA-VN-030) rising through the plate's counterbored hold-down
hole into a blind tap in its foot (user ruling 2026-09-29).  The drive-train
builder asserts, when it is imported, that the block, the platform, the post
and the shaft agree and that every stack the hold-down fixes still closes at
the printed limits.  These tests read those asserts and the values they
produce, and show each tolerance the stacks rely on is load-bearing.
"""

from __future__ import annotations

import pytest


def test_post_fillisters_engage_the_plate_tap_at_least_090d() -> None:
    """I22: each MHA-VN-031 seats on the post's counterbore floor and runs into
    the MHA-DT-020 tap by its cut length past the post's grip -- never proud of
    the plate underside, and 0.90D of thread after the tap's edge break."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_swing_platform_spec as platform
    import vn_post_mount_screw_spec as screw

    assert bdt.POST_SCREW_SEAT == pytest.approx(screw.GRIP_MM)
    assert bdt.POST_SCREW_INTO_PLATE == pytest.approx(
        screw.CUT_LENGTH_MM - screw.GRIP_MM
    )
    assert bdt.POST_SCREW_INTO_PLATE <= platform.PLATE_THICKNESS
    thread = bdt.POST_SCREW_INTO_PLATE - 2.0 * platform.POST_MOUNT_TAP_EDGE_BREAK
    assert thread >= 0.90 * platform.POST_MOUNT_THREAD_DIA
    assert platform.POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS >= 0.90



def test_tip_block_stands_on_the_plate_at_its_print_worst() -> None:
    """The straight prism's whole foot is its plan section, and each side face
    keeps the containment floor plus the print-worst margin inside its own
    plate edge."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    south, north, half = bdt.PLATFORM_RIDER_SPANS["tip block"]
    assert (south, north) == pytest.approx(
        (
            bdt.TIP_BLOCK_STATION - block.BLOCK_Z / 2.0,
            bdt.TIP_BLOCK_STATION + block.BLOCK_Z / 2.0,
        )
    )
    assert half == pytest.approx(block.BLOCK_X / 2.0)
    floor = bdt.PLATFORM_CONTAINMENT_FLOOR_MM + bdt.TIP_PRINT_WORST_MARGIN_MM
    assert bdt.TIP_PRINT_WORST_CONTAINMENT_MM >= floor


def test_block_plus_x_face_is_held_against_the_plates_west_edge() -> None:
    """Both riders take the plate's frame (ROT_Y_INCLINE), whose local +x is
    machine west, so the block's +X face -- where the width's band lands --
    must be checked against the plate's authored +x (west) edge."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_swing_platform_geometry as geometry

    for station in (
        bdt.TIP_BLOCK_STATION - bdt.TIP_BLOCK_Z / 2.0,
        bdt.TIP_BLOCK_STATION + bdt.TIP_BLOCK_Z / 2.0,
    ):
        z_local = station - bdt.PIVOT_STATION
        assert bdt._plat_side_half_widths(station)["+X"] == pytest.approx(
            geometry._west_edge_x(z_local)
        )


def test_block_width_needs_its_three_place_band_for_containment() -> None:
    """The width prints .XXX: at .XX its band on the +X face leaves less than
    the print-worst margin over the plate's narrow west edge."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert block.BLOCK_WIDTH_PLACES == 3
    widened = dict(bdt.TIP_WORST_HALF_WIDTHS_MM)
    widened["+X"] += block.printed_band_mm(2) - block.printed_band_mm(3)
    with pytest.raises(AssertionError, match="overhang"):
        bdt.tip_block_print_worst_containment_mm(widened)


def test_hold_down_hole_stands_under_the_block_foot_tap() -> None:
    """The plate's hole and the block's tap sit the same offset off the cone
    line and the adjuster axis, so in the machine the screw rises into the
    tap and the block body stands centred on the cone line."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert bdt.PLAT_HOLDDOWN_LOCAL_X == pytest.approx(block.FOOT_TAP_OFFSET_X)
    assert bdt.PLAT_HOLDDOWN_LOCAL_X != 0.0  # a real, dimensionable station
    hole = bdt._plate_local_to_machine(
        bdt.PLAT_HOLDDOWN_LOCAL_X, bdt.PLAT_HOLDDOWN_LOCAL_Z
    )
    origin = bdt.cone_station(bdt.TIP_BLOCK_STATION)
    tap = (
        origin[0] + block.FOOT_TAP_OFFSET_X * bdt.ROT_Y_INCLINE[0][0],
        origin[2] + block.FOOT_TAP_OFFSET_X * bdt.ROT_Y_INCLINE[0][2],
    )
    assert hole == pytest.approx(tap, abs=1e-9)


def test_pinch_screw_head_faces_the_blocks_plus_x_clearance_face() -> None:
    """The fillister is authored head up (+Y); its placement must turn that
    onto the block's +X axis, the face whose near jaw is drilled clear, so
    the shank threads only into the far jaw."""
    import build_dt_drive_train_assembly as bdt

    rows = bdt.ROT_PINCH_WEST
    assert rows[1] == pytest.approx(bdt.ROT_Y_INCLINE[0])
    x, y, z = rows
    cross = (
        x[1] * y[2] - x[2] * y[1],
        x[2] * y[0] - x[0] * y[2],
        x[0] * y[1] - x[1] * y[0],
    )
    assert cross == pytest.approx(tuple(z))


def test_pivot_head_keeps_its_air_to_the_block_north_face() -> None:
    """The pivot-screw head clears the block's north face by PIVOT_HEAD_AIR
    at the printed limits; with HoldDownZ at the .XX band it would not."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert bdt.PIVOT_HEAD_WORST_GAP >= bdt.PIVOT_HEAD_AIR
    band = (
        bdt.TIP_NORTH_FACE_BAND_MM
        - bdt.PLAT_HOLDDOWN_STATION_TOL_MM
        + block.printed_band_mm(2)
    )
    with pytest.raises(AssertionError, match="pivot-screw head"):
        bdt.tip_pivot_head_worst_gap_mm(band)


def test_adjuster_embed_stays_in_its_working_window() -> None:
    """The cup's seat moves with the tip's station and the north face's; both
    extremes, with the set end play, stay in the adjuster's 1.0D window.
    Sec4End at .XX (user ruling 2026-09-29) still closes; at .X it would not."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_gear_shaft_spec as shaft
    import dt_cone_tip_block_spec as block

    assert shaft.DRAWING_PRECISION_BY_NAME["Sec4End"] == 2
    low, high = bdt.TIP_EMBED_WORST_MM
    window = bdt.TIP_ADJ_EMBED_WINDOW
    assert window[0] <= low and high <= window[1]
    band = bdt.TIP_EMBED_BAND_MM - block.printed_band_mm(2) + block.printed_band_mm(1)
    with pytest.raises(AssertionError, match="adjuster embed"):
        bdt.tip_embed_worst_mm(band)


def test_stack_collar_never_touches_the_block() -> None:
    """MHA-VN-016 is locked on the shaft one feeler off T006 and must keep air to
    the block's south face at the printed limits (user ruling 2026-09-29):
    the block's Depth at .XX would let the collar reach it."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert block.DRAWING_PRECISION["BlockProfile"]["Depth"] == 3
    assert bdt.TIP_COLLAR_WORST_AIR >= 0.0
    band = bdt.TIP_COLLAR_AIR_BAND_MM - block.printed_band_mm(3) + block.printed_band_mm(2)
    with pytest.raises(AssertionError, match="collar can reach"):
        bdt.tip_collar_worst_air_mm(band)


def _loosened(tight_mm: float) -> float:
    """How much a band grows when a +/-0.10 or .XXX grade falls back to .XX."""
    import dt_cone_tip_block_spec as block

    return block.printed_band_mm(2) - tight_mm


def test_cone_boss_length_at_one_place_opens_the_embed_band() -> None:
    """ConeBossLen prints .XX (user ruling 2026-09-29): the shaft collar bears
    on the boss's north face, half its band off the post centre, and at .X
    the adjuster's shallow extreme leaves its window."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_pivot_post_spec as post
    import dt_cone_tip_block_spec as block

    assert post.DRAWING_PRECISION["ConeShaftBoss"]["ConeBossLen"] == 2
    grown = (block.printed_band_mm(1) - block.printed_band_mm(2)) / 2.0
    with pytest.raises(AssertionError, match="adjuster embed"):
        bdt.tip_embed_worst_mm(bdt.TIP_EMBED_BAND_MM + grown)


def test_post_mount_stations_need_their_explicit_band() -> None:
    """The platform's post-mount taps (+/-0.10) move the collar face; at .XX
    the adjuster's embed leaves its window."""
    import build_dt_drive_train_assembly as bdt

    assert bdt.PLAT_POST_MOUNT_STATION_TOL_MM == pytest.approx(0.10)
    grown = _loosened(bdt.PLAT_POST_MOUNT_STATION_TOL_MM)
    with pytest.raises(AssertionError, match="adjuster embed"):
        bdt.tip_embed_worst_mm(bdt.TIP_EMBED_BAND_MM + grown)


def test_foot_tap_stations_need_their_explicit_band() -> None:
    """FootTapZ at .XX moves the north face past the pivot head's air;
    FootTapX at .XX moves the adjuster axis past the post's take-up."""
    import build_dt_drive_train_assembly as bdt

    grown = _loosened(bdt.TIP_FOOT_TAP_STATION_TOL_MM)
    with pytest.raises(AssertionError, match="pivot-screw head"):
        bdt.tip_pivot_head_worst_gap_mm(bdt.TIP_NORTH_FACE_BAND_MM + grown)
    with pytest.raises(AssertionError, match="lateral error"):
        bdt.require_tip_lateral_take_up(
            bdt.TIP_LATERAL_ERROR_MM + grown, bdt.TIP_LATERAL_CAPACITY_MM
        )


def test_passage_centre_needs_three_places_for_the_lateral_take_up() -> None:
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert bdt.TIP_PASSAGE_CENTER_PLACES == 3
    grown = block.printed_band_mm(2) - block.printed_band_mm(3)
    with pytest.raises(AssertionError, match="lateral error"):
        bdt.require_tip_lateral_take_up(
            bdt.TIP_LATERAL_ERROR_MM + grown, bdt.TIP_LATERAL_CAPACITY_MM
        )


def test_axis_height_needs_its_explicit_band_for_the_cup() -> None:
    """AxisHeight +/-0.10: at .XX the tip could miss the cup's mouth."""
    import build_dt_drive_train_assembly as bdt

    assert bdt.TIP_AXIS_HEIGHT_TOL_MM == pytest.approx(0.10)
    loose = bdt.TIP_VERTICAL_ERROR_MM + _loosened(bdt.TIP_AXIS_HEIGHT_TOL_MM)
    assert loose > bdt.TIP_CUP_CAPTURE_MM


def test_post_turn_takes_up_the_tip_lateral_error() -> None:
    """Turning the post on its screws covers the adjuster axis's lateral
    error; with HoldDownX at the .XX band it would not."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert bdt.TIP_LATERAL_ERROR_MM <= bdt.TIP_LATERAL_CAPACITY_MM
    error = (
        bdt.TIP_LATERAL_ERROR_MM
        - bdt.PLAT_HOLDDOWN_STATION_TOL_MM
        + block.printed_band_mm(2)
    )
    with pytest.raises(AssertionError, match="lateral error"):
        bdt.require_tip_lateral_take_up(error, bdt.TIP_LATERAL_CAPACITY_MM)


def test_tip_stays_inside_the_adjuster_cup_vertically() -> None:
    """Post journal height and block AxisHeight bands keep the stub inside the
    cup's mouth."""
    import build_dt_drive_train_assembly as bdt

    assert bdt.TIP_VERTICAL_ERROR_MM <= bdt.TIP_CUP_CAPTURE_MM


def test_west_edge_is_proven_over_the_whole_swing() -> None:
    """Main, I31 item 8: the north-west edge keeps the arbor pedestals, the
    base lip and every other base seat clear from engaged to disengaged."""
    import build_dt_drive_train_assembly as bdt

    assert bdt.SWING_ANGLES[0] == 0.0
    assert bdt.SWING_ANGLES[-1] == pytest.approx(bdt.DISENGAGE_DEG)
    sweep = bdt.SWING_SWEEP
    assert sweep["south arbor pedestal"] >= 2.0
    assert sweep["north arbor pedestal"] >= 0.25
    assert min(v for k, v in sweep.items() if k.endswith("inside the lip")) >= 0.0
    assert all(isinstance(value, float) for value in sweep.values())
    gap, occupant = bdt.SWING_NEAREST_OCCUPANT
    assert gap == min(clear for clear, _swing in bdt.SWING_OCCUPANT_CLEARANCE.values())
    assert gap >= bdt.SWING_SEAT_RUNNING_CLEARANCE
    assert bdt.SWING_OCCUPANT_CLEARANCE[occupant][0] == gap
    # The north pedestal gap closes as the plate swings out: the engaged pose
    # alone would not have found its minimum.
    engaged = bdt.west_edge_arbor_gaps(0.0)[1]
    assert sweep["north arbor pedestal"] < engaged


def test_swing_occupants_are_the_parts_standing_on_the_seats() -> None:
    """Main (review of 7240ae0de): the thing the swinging plate can hit is the
    part standing on a base seat -- the rocker-arm support, the pivot blocks,
    the pinion spring, the nameplate -- not the screw holding it, so those are
    checked by plan footprint; only the column tube, round in its socket, keeps
    a radius.  Every occupant clears the plate by SWING_SEAT_RUNNING_CLEARANCE
    over the whole swing, and each footprint covers the seats that hold it."""
    import build_dt_drive_train_assembly as bdt

    assert not hasattr(bdt, "SWING_FEATURE_CLEARANCE")
    assert not hasattr(bdt, "SWING_SEAT_FLOORS")
    assert bdt.SWING_SEAT_RUNNING_CLEARANCE == 2.0
    assert set(bdt.SWING_FOOTPRINTS) == {
        "rocker-arm support",
        "front pivot block",
        "back pivot block",
        "pinion spring",
        "nameplate",
        "serial stamp",
    }
    assert set(bdt.SWING_ROUND_OCCUPANTS) == {f"column socket {i}" for i in range(4)}
    for occupant, seats in bdt.SWING_OCCUPANT_SEATS.items():
        for seat in seats:
            assert bdt._point_in_polygon(seat, bdt.SWING_FOOTPRINTS[occupant]), (
                occupant,
                seat,
            )
    clearances = bdt.SWING_OCCUPANT_CLEARANCE
    assert set(clearances) == set(bdt.SWING_FOOTPRINTS) | set(bdt.SWING_ROUND_OCCUPANTS)
    for occupant, (clear, _swing) in clearances.items():
        assert clear >= bdt.SWING_SEAT_RUNNING_CLEARANCE, occupant


def test_pruned_swing_sweep_finds_the_every_sample_minimum() -> None:
    """The occupant sweep skips samples its motion bound rules out; it must
    report exactly the minimum a sweep of every sample finds."""
    import build_dt_drive_train_assembly as bdt

    for occupant, (clear, swing) in bdt.SWING_OCCUPANT_CLEARANCE.items():
        if occupant in bdt.SWING_FOOTPRINTS:
            gaps = [
                bdt._plan_gap_polygons(
                    bdt.plate_vertices_machine(angle), bdt.SWING_FOOTPRINTS[occupant]
                )
                for angle in bdt.SWING_ANGLES
            ]
        else:
            xz, radius = bdt.SWING_ROUND_OCCUPANTS[occupant]
            gaps = [bdt._plan_gap_to_plate(xz, angle) - radius for angle in bdt.SWING_ANGLES]
        assert clear == min(gaps), occupant
        assert swing == bdt.SWING_ANGLES[gaps.index(min(gaps))], occupant


def test_swing_sweep_catches_a_footprint_the_engaged_pose_misses() -> None:
    """Fail-first control: a synthetic footprint parked where the plate's
    corner arrives only at full disengage passes an engaged-only check and
    fails the swept one."""
    import build_dt_drive_train_assembly as bdt

    engaged = bdt.plate_vertices_machine(0.0)
    swung = bdt.plate_vertices_machine(bdt.DISENGAGE_DEG)
    xs = [x for x, _z in swung]
    zs = [z for _x, z in swung]
    # The spot under the fully swung plate that lies farthest outside the
    # engaged one.
    cx, cz = max(
        (
            (x, z)
            for x in (min(xs) + (max(xs) - min(xs)) * i / 200 for i in range(201))
            for z in (min(zs) + (max(zs) - min(zs)) * j / 200 for j in range(201))
            if bdt._plan_gap_to_plate((x, z), bdt.DISENGAGE_DEG) < -1.0
        ),
        key=lambda xz: bdt._plan_gap_to_plate(xz, 0.0),
    )
    square = ((cx - 0.5, cz - 0.5), (cx + 0.5, cz - 0.5), (cx + 0.5, cz + 0.5), (cx - 0.5, cz + 0.5))
    assert bdt._plan_gap_polygons(engaged, square) > bdt.SWING_SEAT_RUNNING_CLEARANCE
    with pytest.raises(AssertionError, match="synthetic"):
        bdt.require_swing_clearance({"synthetic": square}, {})
    # And a round occupant is held off by its radius plus the clearance.
    with pytest.raises(AssertionError, match="synthetic post"):
        bdt.require_swing_clearance({}, {"synthetic post": ((cx, cz), 0.5)})
