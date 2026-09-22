"""Offline contracts for the knife-mount drawing."""

from __future__ import annotations

import build_knife_mount as part
import knife_mount_spec


def test_conventional_blind_tap_closes_the_adverse_crown_stack() -> None:
    """User ruling 2026-09-22: >= 2 mm of crown web at the deepest drill limit.

    Measured from the seat plane (the boss top): the boss may finish short,
    the bore location and diameter at their adverse limits, the drill at its
    deepest title-block limit with an oversize, 1-degree-blunter point.
    """
    import math

    import knife_hanger_interface as hanger

    pitch_mm = knife_mount_spec.STUD_TAP_PITCH_MM
    runout_at_limits = (
        knife_mount_spec.STUD_TAP_DRILL_DEPTH_MM
        + knife_mount_spec.STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM[0]
        - knife_mount_spec.STUD_TAP_THREAD_DEPTH_MM
    )
    crown_web_at_limits = (
        knife_mount_spec.BOSS_HEIGHT
        + hanger.BOSS_HEIGHT_DEVIATIONS_MM[0]
        + knife_mount_spec.BORE_FROM_TOP
        - knife_mount_spec.BORE_FROM_TOP_TOLERANCE_MM
        - (
            2.0 * knife_mount_spec.R_BORE
            + knife_mount_spec.BORE_DIAMETER_TOLERANCE_MM
        )
        / 2.0
        - (
            knife_mount_spec.STUD_TAP_DRILL_DEPTH_MM
            + knife_mount_spec.STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM[1]
        )
        - 0.5
        * (
            knife_mount_spec.STUD_TAP_DIA
            + knife_mount_spec.DRILLED_HOLE_DIAMETER_PLUS_MM
        )
        / math.tan(
            math.radians(
                knife_mount_spec.DRILL_POINT_MIN_INCLUDED_ANGLE_DEG / 2.0
            )
        )
    )

    assert (
        abs(runout_at_limits - knife_mount_spec.STUD_TAP_WORST_CASE_RUNOUT_MM)
        < 1e-9
    )
    # The tap never has to reach the bottom: a pitch beyond a bottoming tap's
    # two-pitch lead stays below the usable-thread minimum.
    assert runout_at_limits >= 3.0 * pitch_mm - 1e-9
    assert (
        abs(
            crown_web_at_limits
            - knife_mount_spec.STUD_TAP_WORST_CASE_CROWN_WEB_MM
        )
        < 1e-9
    )
    assert crown_web_at_limits >= 2.0


def test_end_located_hanger_tap_retains_axial_wall_at_limits() -> None:
    """The boss (and its concentric tap) is located Depth/2 from ONE end face.

    Near wall: the location's own band. Far wall: the thickness band plus the
    location band. Each band is the title-block tolerance of the precision the
    sheet actually prints for that dimension. 1.2 mm is the user's floor
    (2026-09-22) for a quench-hardened wall beside a thread root; it is why
    the block is 18 deep. It was set against the old 1/2-13 thread: the #10-24
    tap clears it by ~4 mm even at the .X location band, and would at Depth 16.
    """
    import _config

    band_mm = {
        places: round(
            float(_config.title_block(f"linear_{places}pl")["value_in"]) * 25.4, 2
        )
        for places in (1, 2)
    }
    precision = knife_mount_spec.DRAWING_PRECISION_BY_NAME
    depth_band = band_mm[precision["Depth"]]
    location_band = band_mm[precision["BossFromEnd"]]
    location = knife_mount_spec.DRAWING_NOMINALS_MM["BossFromEnd"]
    basic_major_radius = knife_mount_spec.STUD_TAP_MAJOR_DIA_MM / 2.0

    near_wall = location - location_band - basic_major_radius
    far_wall = (
        knife_mount_spec.SUPPORT_Z_THICK
        - depth_band
        - (location + location_band)
        - basic_major_radius
    )

    assert near_wall >= 1.2
    assert far_wall >= 1.2


def test_bore_crown_contacts_ridge_and_clears_required_rock_sweep_at_limits() -> None:
    import math

    from summing_lever_spec import HEX_H, HEX_W

    # The lever is hung from its top ridge, so that vertex remains tangent to
    # the bore crown while the hex rotates about it.
    assert abs(part.BORE_CY + part.R_BORE) < 1e-9

    bore_radius_min = (
        part.R_BORE - knife_mount_spec.BORE_DIAMETER_TOLERANCE_MM / 2.0
    )
    # Use the lever print's actual adverse material limits, not nominal geometry.
    hex_width_max = HEX_W + knife_mount_spec.MATING_HEX_SIZE_PLUS_MM
    hex_height_max = HEX_H + knife_mount_spec.MATING_HEX_SIZE_PLUS_MM
    vertices_from_ridge = (
        (-hex_width_max / 2.0, -hex_height_max / 4.0),
        (-hex_width_max / 2.0, -3.0 * hex_height_max / 4.0),
        (0.0, -hex_height_max),
        (hex_width_max / 2.0, -3.0 * hex_height_max / 4.0),
        (hex_width_max / 2.0, -hex_height_max / 4.0),
    )
    # dimensions.yaml:1333 derives the required summing-bar knife rock from the
    # observed 6-mm tip arc.
    sweep = math.radians(knife_mount_spec.REQUIRED_ROCK_SWEEP_DEG)
    minimum_clearance = math.inf
    for x, y in vertices_from_ridge:
        # Distance squared to a bore centre at (0, -R) is
        # |p|² + R² + 2R(x sin(theta) + y cos(theta)). Include every stationary
        # point inside the sweep, not only sampled/end poses.
        candidates = [-sweep, sweep]
        stationary = math.atan2(x, y)
        for half_turn in range(-2, 3):
            angle = stationary + half_turn * math.pi
            if -sweep <= angle <= sweep:
                candidates.append(angle)
        maximum_radius = max(
            math.sqrt(
                x * x
                + y * y
                + bore_radius_min * bore_radius_min
                + 2.0
                * bore_radius_min
                * (x * math.sin(angle) + y * math.cos(angle))
            )
            for angle in candidates
        )
        minimum_clearance = min(
            minimum_clearance, bore_radius_min - maximum_radius
        )

    assert minimum_clearance > 0.0


def test_summing_assembly_imports_the_knife_mount_tap_contract() -> None:
    """The assembly consumes the tap contract by name; a rename must fail here.

    5849f9d5 dropped STUD_TAP_DEPTH while build_summing_assembly still
    imported it, and only check:math's spring gate noticed.
    """
    import build_summing_assembly

    assert (
        build_summing_assembly.STUD_TAP_THREAD_DEPTH_MM
        == knife_mount_spec.STUD_TAP_THREAD_DEPTH_MM
    )


def test_hanger_joint_meets_one_and_a_half_diameters_of_engagement() -> None:
    """User ruling 2026-09-22 (machining-dfm.md:73): E >= 1.5D of the engaging thread.

    Engagement at limits is the overlap of the stud's full thread (from its
    die runout to its tip less the chamfer) with the tap's full thread (from
    the mouth allowance to the usable minimum), both measured from the seat.
    At its longest the tip must stay inside the usable thread so the shoulder
    seats, and the mount's tap is exactly the interface's.
    """
    import knife_hanger_interface as hanger

    assert knife_mount_spec.STUD_TAP_SPEC.size == hanger.THREAD
    tip_min = hanger.STUD_TIP_LENGTH_MM + hanger.STUD_TIP_LENGTH_DEVIATIONS_MM[0]
    tip_max = hanger.STUD_TIP_LENGTH_MM + hanger.STUD_TIP_LENGTH_DEVIATIONS_MM[1]
    stud_full = (
        hanger.STUD_THREAD_RELIEF_MAX_MM,
        tip_min - hanger.STUD_TIP_CHAMFER_MAX_MM,
    )
    tap_full = (
        max(hanger.TAP_MOUTH_COUNTERSINK_DEPTH_MM, hanger.TAP_MOUTH_EDGE_BREAK_MM),
        knife_mount_spec.STUD_TAP_THREAD_DEPTH_MM,
    )
    overlap = min(stud_full[1], tap_full[1]) - max(stud_full[0], tap_full[0])

    assert abs(overlap - hanger.MIN_ENGAGEMENT_MM) < 1e-9
    assert overlap >= 1.5 * hanger.THREAD_MAJOR_DIA_MM
    assert tip_max <= knife_mount_spec.STUD_TAP_THREAD_DEPTH_MM
    assert abs(hanger.SHOULDER_SEAT_Y - (part.CONTACT_Y + part.SEAT_TOP)) < 1e-9


def test_hanger_interface_matches_its_model_sources() -> None:
    """The interface's copied geometry is pinned to the models that own it.

    Imported here only: the interface stays pure data with no build imports.
    """
    import build_frame_assembly
    import build_top_frame
    import knife_hanger_interface as hanger
    import top_frame_spec

    casting_mid_y = build_frame_assembly.TOP_FRAME_MID_Y
    assert (
        abs(hanger.CASTING_UNDERSIDE_Y - (casting_mid_y - top_frame_spec.HALF_H))
        < 1e-9
    )
    assert abs(hanger.CASTING_TOP_Y - (casting_mid_y + top_frame_spec.HALF_H)) < 1e-9
    # A plain drilled clearance hole through the whole crossbar: no counterbore
    # or chamfer where the boss enters from the underside.
    assert build_top_frame.STUD_HOLE_SPEC.kind == "clearance"
    assert build_top_frame.STUD_HOLE_SPEC.end == "through_all"
    assert abs(hanger.CASTING_STUD_HOLE_DIA_MM - build_top_frame.STUD_HOLE_DIA) < 1e-9
    # The knife-bore crown is the part origin (the knife contact line), so its
    # depth below the seat is the mount model's local seat height.
    assert abs(part.BORE_CY + part.R_BORE) < 1e-9
    assert abs(hanger.KNIFE_BORE_CROWN_DEPTH_MM - part.SEAT_TOP) < 1e-9
    assert abs(hanger.MOUNT_GAP - part.MOUNT_GAP) < 1e-9
    assert abs(knife_mount_spec.BLK_TOP - part.BLK_TOP) < 1e-9


def test_seat_boss_clears_the_casting_hole_and_holds_its_thread_wall() -> None:
    """Novice margins (user 2026-09-22).

    At least 1.5 mm radial clearance to the Ø13.49 casting hole at the boss's
    largest size, at least 1.5 mm of boss wall outside the thread major at its
    smallest, a block top that never lands on the casting, and a boss top
    below the casting's top face.
    """
    import knife_hanger_interface as hanger

    boss_max = hanger.BOSS_DIA_MM + hanger.BOSS_DIA_DEVIATIONS_MM[1]
    boss_min = hanger.BOSS_DIA_MM + hanger.BOSS_DIA_DEVIATIONS_MM[0]
    assert hanger.CASTING_STUD_HOLE_DIA_MM / 2.0 - boss_max / 2.0 >= 1.5
    assert (boss_min - hanger.THREAD_MAJOR_DIA_MM) / 2.0 >= 1.5
    assert hanger.MOUNT_GAP + hanger.BOSS_HEIGHT_DEVIATIONS_MM[0] > 0.0
    assert (
        hanger.SHOULDER_SEAT_Y + hanger.BOSS_HEIGHT_DEVIATIONS_MM[1]
        < hanger.CASTING_TOP_Y
    )
