"""Offline contracts for the knife-mount drawing."""

from __future__ import annotations

import build_knife_mount as part
import knife_mount_spec


def test_conventional_blind_tap_closes_the_adverse_crown_stack() -> None:
    import math

    pitch_mm = 25.4 / 13.0
    runout_at_limits = (
        knife_mount_spec.STUD_TAP_DRILL_DEPTH_MM
        + knife_mount_spec.STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM[0]
        - knife_mount_spec.STUD_TAP_THREAD_DEPTH_MM
        - knife_mount_spec.STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM[1]
    )
    crown_web_at_limits = (
        knife_mount_spec.BORE_FROM_TOP
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
    assert runout_at_limits >= 2.0 * pitch_mm
    assert (
        abs(
            crown_web_at_limits
            - knife_mount_spec.STUD_TAP_WORST_CASE_CROWN_WEB_MM
        )
        < 1e-9
    )
    assert crown_web_at_limits >= 0.5


def test_end_located_hanger_tap_retains_axial_wall_at_limits() -> None:
    """The tap is located 8.00 from ONE end face, so both walls stack.

    Near wall: the location's own band. Far wall: the thickness band plus the
    location band. Each band is the title-block tolerance of the precision the
    sheet actually prints for that dimension.
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
    location_band = band_mm[precision["TapFromEnd"]]
    location = knife_mount_spec.DRAWING_NOMINALS_MM["TapFromEnd"]
    basic_major_radius = 12.7 / 2.0

    near_wall = location - location_band - basic_major_radius
    far_wall = (
        knife_mount_spec.SUPPORT_Z_THICK
        - depth_band
        - (location + location_band)
        - basic_major_radius
    )

    assert near_wall > 0.0
    assert far_wall > 0.0


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
