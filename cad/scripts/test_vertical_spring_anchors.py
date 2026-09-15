"""Offline contract: both stock springs hang PLUMB in the neutral pose.

The channel lever's spring reach (``channel_lever_spec.LEVER_SPRING_X``) and the
gooseneck's arm end (``gooseneck_geom.ARM_END_X``) are not free styling numbers:
each is dimensioned so its spring's upper attachment lands on the machine X of
the summing-lever anchor underneath it. A lean feeds a horizontal component into
the knife load that no tension setting removes, so a reach/arm-end edit (or a
summing-lever hole move) that drifts off plumb must fail here rather than in a
native interference run.
"""

from __future__ import annotations

import math

import pytest

import channel_frame_geom
import channel_kinematics
import channel_lever_spec
import gooseneck_geom
import spring_mount_geom

# The prints carry these stations to two decimals, so plumb is held to half of
# that quantum; the neutral-tilt projection residual is ~1e-7 mm.
PLUMB_TOL_MM = 0.005


def test_lever_reach_puts_the_neutral_spring_hole_over_the_channel_anchor() -> None:
    hole_x, _hole_y = channel_kinematics.spring_hole_xy(0.0)
    anchor_x, _anchor_y = spring_mount_geom.CHANNEL_ANCHOR_XY

    assert hole_x == pytest.approx(anchor_x, abs=PLUMB_TOL_MM)
    # The reach is the fulcrum-to-anchor span, corrected for the neutral tilt.
    phi = math.radians(channel_kinematics.solve_state(0.0)["lever_tilt"])
    fulcrum_x = channel_frame_geom.LEVER_FULCRUM_XY[0]
    assert channel_lever_spec.LEVER_SPRING_X == pytest.approx(
        (fulcrum_x - anchor_x) / math.cos(phi), abs=PLUMB_TOL_MM
    )


def test_neutral_channel_spring_axis_is_vertical() -> None:
    pose = spring_mount_geom.channel_pose(0.0)

    assert pose.axis_xy[1] > 0.0
    assert pose.lower_eye_xy[0] == pytest.approx(
        pose.upper_eye_xy[0], abs=PLUMB_TOL_MM
    )
    assert abs(pose.axis_xy[0]) <= PLUMB_TOL_MM / pose.length_mm


def test_gooseneck_arm_end_hangs_the_counter_eye_over_its_anchor() -> None:
    anchor_x, _anchor_y = spring_mount_geom.COUNTER_ANCHOR_XY

    assert spring_mount_geom.COUNTER_UPPER_EYE_X == pytest.approx(
        anchor_x, abs=PLUMB_TOL_MM
    )
    # Stated the other way: the arm end face is the only free term, so it is the
    # thing a future edit must keep, not the eye position it produces.
    assert gooseneck_geom.ARM_END_X == pytest.approx(
        spring_mount_geom.COLUMN_X - anchor_x + gooseneck_geom.SCREW_SHANK_LEN / 2.0,
        abs=PLUMB_TOL_MM,
    )


def test_reference_counter_spring_axis_is_vertical() -> None:
    pose = spring_mount_geom.COUNTER_REFERENCE_POSE

    assert pose.axis_xy[1] > 0.0
    assert pose.lower_eye_xy[0] == pytest.approx(
        pose.upper_eye_xy[0], abs=PLUMB_TOL_MM
    )
    assert abs(pose.axis_xy[0]) <= PLUMB_TOL_MM / pose.length_mm
