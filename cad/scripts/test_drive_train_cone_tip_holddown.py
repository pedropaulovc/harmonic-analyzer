"""Import-time contracts for the cone tip block's hold-down stack in the drive train.

The block (MHA-DT-21) stands straight on the swing platform, held by one socket
head cap screw (MHA-DT-VN-60) rising through the plate's counterbored hold-down
hole into a blind tap in its foot (user ruling 2026-09-29).  The drive-train
builder asserts, when it is imported, that the block, the platform, the post
and the shaft agree and that every stack the hold-down fixes still closes at
the printed limits.  These tests read those asserts and the values they
produce, and show each tolerance the stacks rely on is load-bearing.  The
cone tip's air to G19 (dt_cone_tip_air: the bushing, the end screw and the
block, owner decision C1 keyed 2026-11-09, PR #1992) is proved here too.
"""

from __future__ import annotations

import math

import pytest


def test_post_fillisters_engage_the_plate_tap_at_least_087d() -> None:
    """I22: each MHA-DT-VN-61 seats on the post's counterbore floor and runs into
    the MHA-DT-20 tap by its cut length past the post's grip -- never proud of
    the plate underside, and 0.87D of thread after the tap's edge break."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_swing_platform_spec as platform
    import dt_vn_post_mount_screw_spec as screw

    assert bdt.POST_SCREW_SEAT == pytest.approx(screw.GRIP_MM)
    assert bdt.POST_SCREW_INTO_PLATE == pytest.approx(
        screw.CUT_LENGTH_MM - screw.GRIP_MM
    )
    assert bdt.POST_SCREW_INTO_PLATE <= platform.PLATE_THICKNESS
    thread = bdt.POST_SCREW_INTO_PLATE - 2.0 * platform.POST_MOUNT_TAP_EDGE_BREAK
    assert thread >= 0.87 * platform.POST_MOUNT_THREAD_DIA
    assert platform.POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS >= 0.87



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


def test_plate_edges_come_from_the_platform_outline() -> None:
    """#2611: the assembly reads the plate's edges from PLATE_OUTLINE, so in
    the band the south-east chamfer runs, the east edge is the chamfer line,
    not the straight east taper continued to the south edge."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_swing_platform_geometry as geometry

    south_x, south_z = geometry.SE_CHAMFER_SOUTH_XZ
    east_x, east_z = geometry.SE_CHAMFER_EAST_XZ
    z_local = (south_z + east_z) / 2.0
    station = bdt.PIVOT_STATION + z_local
    chamfer_x = south_x + (east_x - south_x) * (z_local - south_z) / (east_z - south_z)
    taper_east = geometry.HALF_WIDTH_N + (
        geometry.EAST_HALF_S - geometry.HALF_WIDTH_N
    ) * (geometry.NORTH_OVERHANG - z_local) / geometry.PLATE_LEN
    assert bdt._plat_side_half_widths(station)["-X"] == pytest.approx(-chamfer_x)
    assert -chamfer_x < taper_east - 1.0
    # North of the chamfer the east edge is still the taper.
    north = bdt.PIVOT_STATION + geometry.NORTH_OVERHANG - 1.0
    assert bdt._plat_side_half_widths(north)["-X"] == pytest.approx(
        geometry.HALF_WIDTH_N
        + (geometry.EAST_HALF_S - geometry.HALF_WIDTH_N) / geometry.PLATE_LEN
    )


def test_pivot_post_is_held_on_the_plate_as_a_circle() -> None:
    """#2611: the post's round foot is checked as a circle against every
    outline edge, the chamfer included, and agrees with the platform part's
    own POST_FOOT_CONTAINMENT; a foot one margin wider fails."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_swing_platform_checks as checks

    assert "pivot post" not in bdt.PLATFORM_RIDER_SPANS
    radius = bdt.POST_BLOCK_DIA / 2.0
    assert bdt.POST_PLATFORM_CONTAINMENT_MM == pytest.approx(
        checks.POST_FOOT_CONTAINMENT
    )
    assert bdt.POST_PLATFORM_CONTAINMENT_MM >= bdt.PLATFORM_CONTAINMENT_FLOOR_MM
    grown = radius + bdt.POST_PLATFORM_CONTAINMENT_MM + 0.01
    assert bdt._plat_round_foot_containment_mm(bdt.POST_STATION, grown) < 0.0


def test_block_width_one_sided_band_holds_containment() -> None:
    """The width's band may only bring the +X face in (machinist review of
    83e3370f9, rules 4 and 19): its upper limit, the nominal, keeps the
    print-worst margin over the plate's narrow west edge, and the check
    refuses a face standing past that margin."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert block.BLOCK_WIDTH_BAND == (0.0, -0.508)
    assert block.BLOCK_WIDTH_LIMITS[1] == pytest.approx(block.BLOCK_X)
    margin = bdt.tip_block_print_worst_containment_mm(bdt.TIP_WORST_HALF_WIDTHS_MM)
    floor = bdt.PLATFORM_CONTAINMENT_FLOOR_MM + bdt.TIP_PRINT_WORST_MARGIN_MM
    widened = dict(bdt.TIP_WORST_HALF_WIDTHS_MM)
    widened["+X"] += margin - floor + 0.01
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
    at the printed limits, and the check refuses a face standing further
    north than that air allows."""
    import build_dt_drive_train_assembly as bdt

    assert bdt.PIVOT_HEAD_WORST_GAP >= bdt.PIVOT_HEAD_AIR
    band = (
        bdt.TIP_NORTH_FACE_BAND_MM
        + bdt.PIVOT_HEAD_WORST_GAP
        - bdt.PIVOT_HEAD_AIR
        + 0.01
    )
    with pytest.raises(AssertionError, match="pivot-screw head"):
        bdt.tip_pivot_head_worst_gap_mm(band)


def test_end_screw_reaches_the_bushing_with_its_head_clear() -> None:
    """C1 keyed (owner decision 2026-11-09, PR #1992): the end screw is set
    against the bushing, so its embed follows the tip's axial stack; at both
    extremes, with the set end play, its head stands off MHA-DT-21's north
    face and its full thread keeps the booked floor."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    low, high = bdt.END_SCREW_EMBED_WORST_MM
    assert high <= block.END_SCREW_REACH_MAX_EMBED_MM
    assert bdt.END_SCREW_ENGAGEMENT_WORST_D >= bdt.END_SCREW_ENGAGEMENT_FLOOR_D
    assert low < block.END_SCREW_EMBED < high
    grown = block.END_SCREW_REACH_MAX_EMBED_MM - high + 0.01
    with pytest.raises(AssertionError, match="end screw embed"):
        bdt.end_screw_embed_worst_mm(bdt.END_SCREW_EMBED_BAND_MM + grown)


def _loosened(tight_mm: float) -> float:
    """How much a band grows when an explicit or .XXX grade falls back to the
    inch .X (#290: the inch .XX closes these stacks too)."""
    import dt_cone_tip_block_spec as block

    return block.printed_band_mm(1) - tight_mm


def test_cone_boss_length_at_one_place_opens_the_embed_band() -> None:
    """ConeBossLen prints .XXX, the shared 1.654 (user ruling 2026-09-29 put
    it at .XX): the shaft collar bears on the boss's north face, half its band
    off the post centre, and at .X the end screw's deep extreme bottoms its
    head on the block."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_pivot_post_spec as post
    import dt_cone_tip_block_spec as block

    places = post.DRAWING_PRECISION["ConeShaftBoss"]["ConeBossLen"]
    assert places == 3
    grown = (block.printed_band_mm(1) - block.printed_band_mm(places)) / 2.0
    with pytest.raises(AssertionError, match="end screw embed"):
        bdt.end_screw_embed_worst_mm(bdt.END_SCREW_EMBED_BAND_MM + grown)


def test_post_mount_stations_need_their_explicit_band() -> None:
    """The platform's post-mount taps (the shop's +/-.005 drilled-hole row,
    delegated ruling 2026-11-07) move the shaft's thrust face; at the inch
    .X the end screw's embed leaves its reach."""
    import build_dt_drive_train_assembly as bdt

    assert bdt.PLAT_POST_MOUNT_STATION_TOL_MM == pytest.approx(0.127)
    grown = _loosened(bdt.PLAT_POST_MOUNT_STATION_TOL_MM)
    with pytest.raises(AssertionError, match="end screw embed"):
        bdt.end_screw_embed_worst_mm(bdt.END_SCREW_EMBED_BAND_MM + grown)


def test_pushed_post_only_makes_the_embed_shallower() -> None:
    """#2697: MHA-DT-00 holds MHA-DT-05 pushed toward MHA-DT-21 while it is
    turned and tightened, so its screw clearance moves the shaft north only:
    the shallow extreme carries all of it, the deep one none.  Booked both
    ways, the 19/64 holes' clearance would bottom the screw's head."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    band = bdt.END_SCREW_EMBED_BAND_MM
    push = bdt.END_SCREW_POST_PUSH_MM
    assert push == pytest.approx(bdt.POST_SCREW_FLOAT_MM)
    low, high = bdt.END_SCREW_EMBED_WORST_MM
    assert block.END_SCREW_EMBED - low == pytest.approx(high - block.END_SCREW_EMBED + push)
    assert bdt.end_screw_embed_worst_mm(band, 0.0)[1] == pytest.approx(high)
    with pytest.raises(AssertionError, match="end screw embed"):
        bdt.end_screw_embed_worst_mm(band + push, 0.0)
    # More clearance than the holes have drops the shallow end's thread.
    with pytest.raises(AssertionError, match="end screw full thread"):
        bdt.end_screw_embed_worst_mm(band, push + 0.05)


def test_foot_tap_along_station_needs_three_places() -> None:
    """FootTapZ at .XX drops the 5/8 end screw's shallow engagement under the
    owner's 1.39 D (#2697: a longer screw, not a tighter band, is the room)."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert block.FOOT_TAP_Z_PLACES == 3
    grown = block.printed_band_mm(2) - bdt.TIP_FOOT_TAP_Z_TOL_MM
    with pytest.raises(AssertionError, match="end screw full thread"):
        bdt.end_screw_embed_worst_mm(bdt.END_SCREW_EMBED_BAND_MM + grown)


def test_across_stations_print_two_places_with_room_in_the_post_turn() -> None:
    """#2697: PassageCenter and FootTapX print .XX on the .01 grid, and the
    post's turn on its screws still covers the tip's lateral error with a
    further .XX band on each of them and on the platform's hold-down hole."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert (bdt.TIP_PASSAGE_CENTER_PLACES, block.FOOT_TAP_X_PLACES) == (2, 2)
    for station in (block.BLOCK_X / 2.0, block.FOOT_TAP_X):
        assert station / 0.254 == pytest.approx(round(station / 0.254))
    error = bdt.TIP_LATERAL_ERROR_MM + 3.0 * block.printed_band_mm(2)
    bdt.require_tip_lateral_take_up(error, bdt.TIP_LATERAL_CAPACITY_MM)


def test_post_turn_takes_up_the_tip_lateral_error() -> None:
    """Turning the post on its screws covers the adjuster axis's lateral
    error; in the 9/32 holes it replaced (#2697) the same turn would not."""
    import build_dt_drive_train_assembly as bdt

    assert bdt.TIP_LATERAL_ERROR_MM <= bdt.TIP_LATERAL_CAPACITY_MM
    old_float = bdt.POST_SCREW_FLOAT_MM - (bdt.POST_ATTACHMENT_THRU_DIA - 9 / 32 * 25.4) / 2.0
    old_capacity = bdt.TIP_LATERAL_CAPACITY_MM * old_float / bdt.POST_SCREW_FLOAT_MM
    with pytest.raises(AssertionError, match="lateral error"):
        bdt.require_tip_lateral_take_up(bdt.TIP_LATERAL_ERROR_MM, old_capacity)


def test_matched_axis_height_lets_the_pivot_run_free_in_the_end_screw() -> None:
    """MHA-DT-21's AxisHeight is made to the measured MHA-DT-05 journal axis
    (a matched pair): the shaft's tilt, the screw's thread float and the
    pivot's running clearance take up that residual; the .XX general band
    in its place would not close."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_tip_block_spec as block

    assert bdt.TIP_VERTICAL_ERROR_MM <= bdt.TIP_VERTICAL_CAPACITY_MM
    unmatched = (
        bdt.TIP_VERTICAL_ERROR_MM
        - block.AXIS_HEIGHT_MATCH_RESIDUAL_MM
        + block.printed_band_mm(block.DRAWING_PRECISION_BY_NAME["AxisHeight"])
    )
    with pytest.raises(AssertionError, match="tip vertical error"):
        bdt.require_tip_vertical_take_up(unmatched, bdt.TIP_VERTICAL_CAPACITY_MM)


def test_west_edge_is_proven_over_the_whole_swing() -> None:
    """Main, I31 item 8: the north-west edge keeps the arbor pedestals, the
    base pad edge and every other base seat clear from engaged to disengaged."""
    import build_dt_drive_train_assembly as bdt

    assert bdt.SWING_ANGLES[0] == 0.0
    assert bdt.SWING_ANGLES[-1] == pytest.approx(bdt.P1_SWEEP_DEG[1])
    assert bdt.P1_SWEEP_DEG[1] > bdt.DISENGAGE_DEG
    assert min(bdt.P1_STOP_ENCLOSURE["unbroken_fence_margins_mm"].values()) > 0.0
    sweep = bdt.SWING_SWEEP
    assert sweep["south arbor pedestal"] >= 2.0
    assert sweep["north arbor pedestal"] >= 0.25
    assert min(v for k, v in sweep.items() if k.endswith("over the base")) >= 0.0
    assert all(isinstance(value, float) for value in sweep.values())
    gap, occupant = bdt.SWING_NEAREST_OCCUPANT
    assert gap == min(clear for clear, _swing in bdt.SWING_OCCUPANT_CLEARANCE.values())
    assert gap >= bdt.SWING_SEAT_RUNNING_CLEARANCE
    assert bdt.SWING_OCCUPANT_CLEARANCE[occupant][0] == gap
    # The north pedestal gap is checked over the whole swing, not only at the
    # engaged pose; the sweep's minimum is never above the engaged gap.
    engaged = bdt.west_edge_arbor_gaps(0.0)[1]
    assert sweep["north arbor pedestal"] <= engaged


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


def test_south_east_chamfer_is_what_clears_column_socket_0(monkeypatch) -> None:
    """#1038 conflict 4: with the bank centred the swung plate's south end
    passes the front column.  The swept outline is the plate's own
    (south-east corner chamfered); the sharp corner it replaces is the
    fail-first control and fires the same import-time assertion."""
    import build_dt_drive_train_assembly as bdt
    import dt_cone_swing_platform_geometry as geometry

    assert bdt._PLATFORM_VERTICES == tuple((x, z) for _label, x, z in geometry.PLATE_OUTLINE)
    gap, swing = bdt.SWING_OCCUPANT_CLEARANCE["column socket 0"]
    assert gap >= bdt.SWING_SEAT_RUNNING_CLEARANCE
    # The nearest pass is at the end of the certified swing, where the column
    # stands almost on the plate's axis: the south edge passes it, not only
    # the corner.
    assert swing == pytest.approx(bdt.P1_SWEEP_DEG[1])
    pivot = (bdt._PPIVOT[0], bdt._PPIVOT[2])
    socket, radius = bdt.SWING_ROUND_OCCUPANTS["column socket 0"]
    keep_out = math.dist(pivot, socket) - radius - bdt.SWING_SEAT_RUNNING_CLEARANCE
    post_foot_rim = -geometry.POST_LOCAL_Z + geometry.POST_MAIN_DIA / 2.0
    assert 0.0 < keep_out - post_foot_rim < 1.0
    assert -geometry.PLATE_SOUTH_Z > keep_out

    sharp = tuple((x, z) for _label, x, z, _radius in geometry.PLATE_CORNERS)
    monkeypatch.setattr(bdt, "_PLATFORM_VERTICES", sharp)
    with pytest.raises(AssertionError, match="column socket 0"):
        bdt.require_swing_clearance({}, bdt.SWING_ROUND_OCCUPANTS)


def test_what_the_plate_carries_clears_the_frame_columns_over_the_swing() -> None:
    """#2616: the crank column and the cone-shaft gears overhang the plate's
    plan outline and swing with it; each keeps SWING_SEAT_RUNNING_CLEARANCE
    off every base occupant, the frame column tubes included, over the
    stop's certified swing.  The pruned sweep reports the every-sample
    minimum."""
    import build_dt_drive_train_assembly as bdt

    occupants = set(bdt.SWING_FOOTPRINTS) | set(bdt.SWING_ROUND_OCCUPANTS)
    assert {"post crank boss", "crank chain wheel", "64T gear", "cone gear 0"} <= set(
        bdt.SWING_RIDERS
    )
    clearances = bdt.SWING_RIDER_CLEARANCE
    assert set(clearances) == {(r, o) for r in bdt.SWING_RIDERS for o in occupants}
    for pair, (clear, _swing) in clearances.items():
        assert clear >= bdt.SWING_SEAT_RUNNING_CLEARANCE, pair
    rider, occupant = min(clearances, key=lambda pair: clearances[pair][0])
    assert (rider, occupant) == ("post crank boss", "column socket 0")
    xz, radius = bdt.SWING_ROUND_OCCUPANTS[occupant]
    section = bdt.SWING_RIDERS[rider]
    gaps = []
    for angle in bdt.SWING_ANGLES:
        poly = tuple(bdt._swung(point, angle) for point in section)
        nearest = min(bdt._point_segment_gap(xz, a, b) for a, b in bdt._edges(poly))
        gaps.append((-nearest if bdt._point_in_polygon(xz, poly) else nearest) - radius)
    assert clearances[(rider, occupant)] == (
        min(gaps),
        bdt.SWING_ANGLES[gaps.index(min(gaps))],
    )


def test_the_certified_swing_ends_before_the_crank_boss_meets_column_0() -> None:
    """#2616 fail-first control: carried to the 12.38 deg the stop fence
    certified before (no head/thread or shoulder/thread coaxiality at all),
    the post crank boss overlaps frame column 0; the stop's certified swing
    now ends where it still keeps the running clearance, above the nominal
    disengage."""
    import build_dt_drive_train_assembly as bdt

    xz, radius = bdt.SWING_ROUND_OCCUPANTS["column socket 0"]

    def boss_gap(angle: float) -> float:
        poly = tuple(
            bdt._swung(point, angle) for point in bdt.SWING_RIDERS["post crank boss"]
        )
        nearest = min(bdt._point_segment_gap(xz, a, b) for a, b in bdt._edges(poly))
        return (-nearest if bdt._point_in_polygon(xz, poly) else nearest) - radius

    assert boss_gap(12.38) < 0.0
    assert bdt.DISENGAGE_DEG < bdt.P1_SWEEP_DEG[1] < 12.38
    assert boss_gap(bdt.P1_SWEEP_DEG[1]) >= bdt.SWING_SEAT_RUNNING_CLEARANCE


def test_cone_tip_keeps_air_to_g19_over_the_whole_swing() -> None:
    """C1 keyed (owner decision 2026-11-09, PR #1992): the bushing, the end
    screw's proud end and MHA-DT-21's south face (where it stands over G19)
    each keep positive air to G19's tooth and cam tiers over the P1 sweep at
    the printed limits, worst-case arithmetic over every source."""
    import dt_cone_tip_air as air

    rows = air.full_sweep_proof(intervals=100)
    assert {row["method"] for row in rows} == {"arithmetic"}
    assert {row["tier"] for row in rows} == set(air.TIER_NAMES)
    least = air.require_air()
    assert set(least) == set(air.TIER_NAMES)
    assert min(least.values()) > 0.0
    for row in rows:
        assert row["closure_mm"].keys() - {"continuous p1 interval arc"} <= (
            air.IN_SERVICE_CLEARANCES | air.INDEPENDENT_TOLERANCES
        )


def test_tip_air_refuses_an_unclassified_source() -> None:
    import dt_cone_tip_air as air

    with pytest.raises(ValueError, match="unclassified"):
        air.AirStack("bushing", "tooth_face", 0.0, 1.0, {"a stray source": 0.1}, 0.0)


def test_shaft_thrust_collar_width_needs_its_band_for_the_bushing_air(monkeypatch) -> None:
    """CollarWidth's printed band sets where the shaft, and so the bushing on
    T006's pivot, stands along the cone axis; at the inch .X the bushing can
    reach G19."""
    import dt_cone_tip_air as air
    import dt_cone_tip_block_spec as block

    terms = dict(air.AXIAL_TERMS_MM)
    terms["shaft thrust collar width"] = block.printed_band_mm(1)
    monkeypatch.setattr(air, "AXIAL_TERMS_MM", terms)
    with pytest.raises(ValueError, match="cone tip bushing can reach G19"):
        air.full_sweep_proof(intervals=40)


def test_block_shadow_is_the_exact_least_z_over_the_drum() -> None:
    """The block tier's linear program finds the least Z of the block body
    over a drum circle: no sampled point of the body over the circle lies
    lower, and the vertex it returns is on the body over the circle."""
    import math

    import cone_line
    import dt_cone_tip_air as air
    import dt_cone_tip_block_spec as block

    fixed = air.DRUM_TIERS[0]
    for angle in (air.P1_SWEEP_DEG[1] * f for f in (0.6, 0.8, 1.0)):
        low = air.block_shadow_low_z(angle, fixed.radius_mm)
        if not math.isfinite(low):
            continue
        origin, axis = air.tip_pose_frame(angle)
        face = [origin[k] + block.TIP_BLOCK_SOUTH_FACE * axis[k] for k in range(3)]
        sampled = math.inf
        steps = 60
        for i in range(steps + 1):
            u = -block.BLOCK_X / 2.0 + block.BLOCK_X * i / steps
            for j in range(steps + 1):
                t = block.BLOCK_Z * j / steps
                x = face[0] + u * axis[2] + t * axis[0]
                if abs(x - cone_line.X_DRUM) <= fixed.radius_mm:
                    sampled = min(sampled, face[2] - u * axis[0] + t * axis[2])
        assert low <= sampled + 1e-9
        assert sampled - low < 0.05
