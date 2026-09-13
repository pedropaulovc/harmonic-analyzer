"""Physical mounting regressions for the purchased springs."""

import gooseneck_geom
import spring_mount_geom


def test_counter_leading_half_turn_clears_tube_and_head() -> None:
    """The extra half-turn must face the open side, not penetrate the tube."""
    pose = spring_mount_geom.COUNTER_REFERENCE_POSE
    screw_y = spring_mount_geom.GOOSENECK_ORIGIN_Y + gooseneck_geom.ARM_Y
    tube_gap, head_gap = spring_mount_geom.counter_half_turn_clearances(pose, screw_y)
    assert tube_gap >= spring_mount_geom.MIN_CLEARANCE_MM
    assert head_gap >= spring_mount_geom.MIN_CLEARANCE_MM
