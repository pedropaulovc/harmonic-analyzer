"""The counter spring's upper-loop retention and envelope gate.

Pure geometry over the pose it is given: it reads no calibration table and
imports no assembly spec, so diagnostics/calibrate_spring_seats.py can gate a
fresh measurement while the counter record it replaces is still stale, and
build_sm_summing_assembly gates the settled placement with the same check.
"""

from __future__ import annotations

import sm_gooseneck_geom
import sm_gooseneck_spring_joint as spring_joint
import sm_gooseneck_spring_screw_geom as spring_screw
import sm_vn_counter_spring_stock_geom as counter_stock
import spring_mount_geom as spring_mounts
from _check import log


def assert_counter_spring_top_hang(
    pose: spring_mounts.SpringPose,
    gooseneck_y: float,
) -> None:
    """Bound retention and envelopes at the fixed measured placement.

    Native body contact is certified separately against actual final component
    instances. The half-turn clocking keeps the raised end on the open side of
    the arm.
    """
    ux, uy = pose.axis_xy
    screw_y = gooseneck_y + sm_gooseneck_geom.ARM_Y
    retention = spring_joint.HEAD_RETENTION
    if spring_joint.HEAD_RETENTION_MIN < 1.0:
        raise RuntimeError(
            f"counter eye worst head retention only "
            f"{spring_joint.HEAD_RETENTION_MIN:.3f} mm radial"
        )
    band = (
        abs(ux) * counter_stock.COIL_MEAN_RADIUS_MM
        + uy * counter_stock.LOOP_HALF_RISE_MM
        + counter_stock.WIRE_RADIUS_MM
    )
    axial_gap = (
        min(
            pose.upper_eye_xy[0] - spring_mounts.GOOSENECK_END_X,
            spring_mounts.GOOSENECK_END_X
            + sm_gooseneck_geom.SPRING_EYE_GAP
            - pose.upper_eye_xy[0],
        )
        - band
    )
    # The supplier band is CLAMPED between the plug face and the under-head
    # plane (user, 2026-09-21), not hung on a free stand-off. Zero nominal
    # side clearance is intentional; only floating-point round-off is tolerated.
    if axial_gap < -1e-9:
        raise RuntimeError(
            f"double-loop band does not fit clamped gap: {axial_gap:.9f} mm"
        )
    # Owner ruling 2026-10-26 (#1951, option B): the loop bears on MHA-SM-04's
    # plain seat. ROT_Y_POS90 sends the shank toward -X, so a station from the
    # under-head face is head_x - x. The band reaches the plug face, past the
    # seat's end at the 45-degree lead's foot (SHOULDER_LENGTH_MIN at the
    # shortest shoulder), so only the loop's two pull-side wire passes may
    # touch the screw: sm_gooseneck_spring_joint fixes them (LOOP_PASS_X) for
    # the plumb loop centred in the gap and bounds their clearance to the lead
    # and to the R0.50 MAX under-head fillet. The band check above already holds
    # the loop plumb; hold it to that centre too, so those budgets are this
    # pose's, and require both passes on the seat.
    head_x = spring_mounts.GOOSENECK_END_X + sm_gooseneck_geom.SPRING_EYE_GAP
    seat_shift = head_x - pose.upper_eye_xy[0] - sm_gooseneck_geom.SPRING_EYE_GAP / 2.0
    passes = tuple(station + seat_shift for station in spring_joint.LOOP_PASS_X)
    seat_overhang = (
        head_x - (pose.upper_eye_xy[0] - band) - spring_screw.SHOULDER_LENGTH_MIN
    )
    lead_clearance = spring_joint.LOOP_LEAD_CLEARANCE_MIN
    corner_clearance = spring_joint.LOOP_CORNER_CLEARANCE_MIN
    if (
        abs(seat_shift) > 1e-9
        or not 0.0 < passes[0] < passes[1] < spring_screw.SHOULDER_LENGTH_MIN
        or min(lead_clearance, corner_clearance) <= 0.0
    ):
        raise RuntimeError(
            "counter upper loop does not bear on the screw's plain seat: loop "
            f"{seat_shift:.9f} off the gap centre, passes at {passes[0]:.4f}/"
            f"{passes[1]:.4f} vs seat end {spring_screw.SHOULDER_LENGTH_MIN:.2f}, "
            f"lead/corner clearance {lead_clearance:.4f}/{corner_clearance:.4f} mm"
        )
    coil_top = (
        pose.centre_xy[1]
        + uy * counter_stock.coil_end_x_mm(pose.length_mm)
        + abs(ux) * counter_stock.COIL_MEAN_RADIUS_MM
        + counter_stock.WIRE_RADIUS_MM
    )
    main_coil_gap = screw_y - sm_gooseneck_geom.TUBE_DIA / 2.0 - coil_top
    tube_gap, head_gap = spring_mounts.counter_half_turn_clearances(pose, screw_y)
    if min(main_coil_gap, tube_gap, head_gap) < spring_mounts.MIN_CLEARANCE_MM:
        raise RuntimeError(
            f"counter coil/support clearance: main {main_coil_gap:.3f}, "
            f"half-turn/tube {tube_gap:.3f}, half-turn/head {head_gap:.3f} mm"
        )
    log(
        f"counter upper support: head retention {retention:.3f}, "
        f"eye clamp side clearance {axial_gap:.9f}, seat passes "
        f"{passes[0]:.4f}/{passes[1]:.4f} before the O{spring_screw.SEAT_DIA:.2f} "
        f"seat's end {spring_screw.SHOULDER_LENGTH_MIN:.2f} (band {seat_overhang:.4f} "
        f"past it to the plug face), lead/corner clearance {lead_clearance:.4f}/"
        f"{corner_clearance:.4f}, main coil {main_coil_gap:.3f}, "
        f"half-turn tube/head {tube_gap:.3f}/{head_gap:.3f} mm"
    )
