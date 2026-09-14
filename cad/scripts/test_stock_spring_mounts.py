"""Physical mounting regressions for the purchased springs."""

from dataclasses import replace

import pytest

import build_channel_assembly as channel
import channel_spring_stock_geom as channel_stock
import gooseneck_geom
import spring_mount_geom


def test_counter_leading_half_turn_clears_tube_and_head() -> None:
    """The extra half-turn must face the open side, not penetrate the tube."""
    pose = spring_mount_geom.COUNTER_REFERENCE_POSE
    screw_y = spring_mount_geom.GOOSENECK_ORIGIN_Y + gooseneck_geom.ARM_Y
    tube_gap, head_gap = spring_mount_geom.counter_half_turn_clearances(pose, screw_y)
    assert tube_gap >= spring_mount_geom.MIN_CLEARANCE_MM
    assert head_gap >= spring_mount_geom.MIN_CLEARANCE_MM


def test_native_mount_keeps_clearance_gates_without_requiring_analytic_tangency() -> None:
    seed = spring_mount_geom.channel_pose(0.0)
    # Move only the upper seat down its pull axis, consistently shortening the
    # spring to represent a non-analytic installed pose.
    correction_mm = 0.01
    upper = tuple(
        seed.upper_eye_xy[k] - correction_mm * seed.axis_xy[k] for k in range(2)
    )
    corrected = replace(
        seed,
        length_mm=seed.length_mm - correction_mm,
        upper_eye_xy=upper,
        centre_xy=tuple((seed.lower_eye_xy[k] + upper[k]) / 2 for k in range(2)),
    )
    channel._assert_spring_mount(corrected, 0.0, state="native_seated")
    with pytest.raises(RuntimeError, match="loaded bore margin"):
        channel._assert_spring_mount(corrected, 0.0, state="catalog_seed")

    # Translate the same consistent pose until its lower hook has only 0.2 mm
    # plate clearance. Native seating must not bypass the real 0.3 mm minimum.
    bottom = (
        corrected.lower_eye_xy[1]
        - corrected.axis_xy[1] * channel_stock.COIL_MEAN_RADIUS_MM
        - channel_stock.WIRE_DIA_MM / 2
    )
    drop = bottom - (spring_mount_geom.PLATE_TOP_Y + 0.2)
    below_plate_clearance = replace(
        corrected,
        lower_eye_xy=(corrected.lower_eye_xy[0], corrected.lower_eye_xy[1] - drop),
        upper_eye_xy=(corrected.upper_eye_xy[0], corrected.upper_eye_xy[1] - drop),
        centre_xy=(corrected.centre_xy[0], corrected.centre_xy[1] - drop),
    )
    with pytest.raises(RuntimeError, match="lower hook enters the summing plate"):
        channel._assert_spring_mount(below_plate_clearance, 0.0, state="native_seated")
