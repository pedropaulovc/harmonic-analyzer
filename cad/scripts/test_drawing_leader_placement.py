"""SolidWorks-free contract for annotation leader placement geometry.

``IAnnotation::SetPosition2`` places a datum tag's symbol, but ``GetPosition``
reports a shouldered tag's leader knee, so a persisted move reads back short
*along* the leader. Measured on ``drawing:pinion_cam`` datum D (2026-09-16,
byte-identical on two workers): the reported point keeps the requested bearing
about the boss axis to six decimals and sits 4.795 mm nearer it. The live
builds exercise the COM path; these cases pin the decomposition that tells a
shoulder apart from a placement that actually failed.
"""

from __future__ import annotations

import math

import _drawing_common as drawing_common

ANCHOR = (0.26680000000000004, 0.1894)
REQUESTED = (0.192, 0.170)
# Reported by SolidWorks for pinion_cam datum D, twice, on two workers.
MEASURED = (0.1966536526575493, 0.17115744694100282)


def test_measured_shoulder_reads_as_on_aim_and_pulled_in():
    """The one case that motivated this: on the leader, short along it."""
    placement = drawing_common.leader_placement(MEASURED, REQUESTED, ANCHOR)
    assert placement.lateral < 1e-4
    assert 0.004 < placement.pull_in < 0.005


def test_exact_placement_is_neither_lateral_nor_pulled_in():
    placement = drawing_common.leader_placement(REQUESTED, REQUESTED, ANCHOR)
    assert placement.lateral < 1e-12
    assert abs(placement.pull_in) < 1e-12


def test_an_ignored_move_leaves_the_tag_at_its_attachment():
    """A tag SolidWorks never moved sits on the leader but nowhere near the
    requested point, so only the pull-in bound rejects it."""
    placement = drawing_common.leader_placement(ANCHOR, REQUESTED, ANCHOR)
    assert placement.lateral < 1e-12
    assert placement.pull_in == math.hypot(
        REQUESTED[0] - ANCHOR[0], REQUESTED[1] - ANCHOR[1]
    )


def test_off_aim_placement_is_reported_as_lateral():
    """Perpendicular displacement is what says the leader no longer points
    where it was aimed; a 1 mm sideways offset reads as exactly 1 mm."""
    span_x, span_y = REQUESTED[0] - ANCHOR[0], REQUESTED[1] - ANCHOR[1]
    span = math.hypot(span_x, span_y)
    sideways = (-span_y / span * 0.001, span_x / span * 0.001)
    actual = (REQUESTED[0] + sideways[0], REQUESTED[1] + sideways[1])
    placement = drawing_common.leader_placement(actual, REQUESTED, ANCHOR)
    assert math.isclose(placement.lateral, 0.001, rel_tol=1e-9)
    assert abs(placement.pull_in) < 1e-12


def test_overshoot_past_the_requested_point_is_negative_pull_in():
    """Past the requested point the sign flips, so the guard's lower bound
    catches a tag thrown beyond its aim instead of silently accepting it."""
    span_x, span_y = REQUESTED[0] - ANCHOR[0], REQUESTED[1] - ANCHOR[1]
    span = math.hypot(span_x, span_y)
    actual = (
        REQUESTED[0] + span_x / span * 0.002,
        REQUESTED[1] + span_y / span * 0.002,
    )
    placement = drawing_common.leader_placement(actual, REQUESTED, ANCHOR)
    assert placement.lateral < 1e-12
    assert math.isclose(placement.pull_in, -0.002, rel_tol=1e-9)


def test_degenerate_anchor_falls_back_to_straight_distance():
    """With the attachment on the requested point there is no ray to decompose
    about, so the raw distance is all that can be asserted."""
    placement = drawing_common.leader_placement((0.1, 0.104), (0.1, 0.1), (0.1, 0.1))
    assert math.isclose(placement.lateral, 0.004, rel_tol=1e-9)
    assert placement.pull_in == 0.0
