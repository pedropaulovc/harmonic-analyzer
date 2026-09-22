"""Offline attachment-axis contracts for the two loaded stock springs.

The channel lever's spring reach (``channel_lever_spec.LEVER_SPRING_X``) keeps
the neutral channel spring plumb over its summing-lever anchor. The counter
spring instead terminates at the centre of MHA-032's released clamped screw
gap. That upper contact is authoritative: reopening the screw must not leak
back into the saved assembly pose, and the rigid spring axis must be recomputed
from the unchanged lower anchor rather than silently retaining the old plumb
orientation.
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


def test_gooseneck_clamp_centres_counter_eye_in_the_released_gap() -> None:
    clamped = (
        spring_mount_geom.GOOSENECK_END_X
        + gooseneck_geom.SPRING_EYE_CENTRE_FROM_ARM_END_MM
    )
    open_position = (
        spring_mount_geom.GOOSENECK_END_X
        + gooseneck_geom.SPRING_SCREW_OPEN_GAP_MM / 2.0
    )

    assert spring_mount_geom.COUNTER_UPPER_EYE_X == pytest.approx(
        clamped, abs=PLUMB_TOL_MM
    )
    assert spring_mount_geom.COUNTER_UPPER_EYE_X != pytest.approx(
        open_position, abs=PLUMB_TOL_MM
    )


def test_reference_counter_spring_recomputes_its_axis_to_the_clamped_eye() -> None:
    pose = spring_mount_geom.COUNTER_REFERENCE_POSE

    assert pose.axis_xy[1] > 0.0
    assert pose.upper_eye_xy[0] == pytest.approx(
        spring_mount_geom.COUNTER_UPPER_EYE_X, abs=PLUMB_TOL_MM
    )
    assert pose.axis_xy[0] < 0.0
    assert pose.upper_eye_xy[0] < pose.lower_eye_xy[0]
