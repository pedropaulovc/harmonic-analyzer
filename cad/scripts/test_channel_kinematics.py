"""Offline regression contracts for the channel rocker/bar linkage."""

from __future__ import annotations

import math

import build_channel_assembly as channel


def test_rocker_motion_carries_an_amplitude_bar_contact() -> None:
    """The J5 contact must transmit rocker motion without killing the slide DOF.

    This is the user-visible sequence in numbers: choose a bar station near the
    rocker end, then lower the rocker.  The contact point must move with the
    rocker about its pivot, while its pivot radius stays unchanged.  A single
    foot-to-arc-centre distance does not encode that motion; it leaves the bar
    free to choose another point/orientation on the same circle.
    """
    station_mm = 80.0
    rest = channel.rocker_contact_world(station_mm, rocker_angle_deg=0.0)
    lowered = channel.rocker_contact_world(station_mm, rocker_angle_deg=-10.0)

    assert lowered[1] < rest[1] - 1.0
    rest_radius = math.hypot(rest[0] - channel.PIVOT[0], rest[1] - channel.PIVOT[1])
    lowered_radius = math.hypot(
        lowered[0] - channel.PIVOT[0], lowered[1] - channel.PIVOT[1]
    )
    assert math.isclose(lowered_radius, rest_radius, abs_tol=1e-9)


def test_j5_is_a_sliding_tangent_contact() -> None:
    """J5 must constrain contact normal, while leaving amplitude station free."""
    assert channel.J5_MATE_KIND == "tangent"
    assert channel.J5_CONTACT_DOF == "rocker_coupled_with_amplitude_slide"
