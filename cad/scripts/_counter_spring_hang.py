"""The counter spring's upper-loop retention and envelope gate.

Pure geometry over the pose it is given: it reads no calibration table and
imports no assembly spec, so diagnostics/calibrate_spring_seats.py can gate a
fresh measurement while the counter record it replaces is still stale, and
build_sm_summing_assembly gates the settled placement with the same check.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4, superseding #1951's clamped
eye: the upper eye rides free on MHA-SM-VN-56's shoulder, seated on the end
face, retained by the screw's head on the LOADED basis (owner ruling
2026-11-08 (Pedro), #2144 item 11.4: bare slotted McMaster 91829A566, washer
dropped).  Owner rulings 2026-11-08 (Pedro), #2315: that end face is the
MHA-SM-05 end plug's, bonded flush into MHA-SM-01's arm end, so the arm stays
one Ø TUBE_DIA cylinder up to it.
"""

from __future__ import annotations

import sm_gooseneck_geom
import sm_gooseneck_spring_joint as spring_joint
import sm_vn_counter_spring_stock_geom as counter_stock
import spring_mount_geom as spring_mounts
from _check import log

# Eye shifts along the shoulder the half-turn clearance sweep evaluates, from
# the end face (0) out to the joint's largest axial play, both ends included.
EYE_SHIFT_SAMPLES = 9


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
    # Retention is on the LOADED basis (sm_gooseneck_spring_joint): the pull
    # is plumb, so the eye's inner top bears on the shoulder's top and the
    # head laps its pull-side wire.  A tilted pull voids that basis.
    if abs(ux) > 1e-9:
        raise RuntimeError(
            f"counter pull is not plumb (axis x {ux:.3e}): the loaded-basis "
            "retention of the free eye under the bare head does not hold"
        )
    retention = spring_joint.LOADED_RETENTION_MIN
    if retention < spring_joint.RETENTION_TARGET:
        raise RuntimeError(
            f"counter eye worst loaded head retention only {retention:.3f} mm radial"
        )
    band = (
        abs(ux) * counter_stock.COIL_MEAN_RADIUS_MM
        + uy * counter_stock.LOOP_HALF_RISE_MM
        + counter_stock.WIRE_RADIUS_MM
    )
    # The loop rests on the end face, plumb, inside the joint's envelope
    # (LOOP_ENVELOPE), so the joint's axial play and the shift sweep below are
    # this pose's: its end-face-side wire on the face, its centre half the
    # envelope out.
    seat_shift = (
        pose.upper_eye_xy[0]
        - spring_mounts.GOOSENECK_END_X
        - spring_joint.LOOP_ENVELOPE / 2.0
    )
    face_gap = pose.upper_eye_xy[0] - band - spring_mounts.GOOSENECK_END_X
    if abs(seat_shift) > 1e-9 or face_gap < -1e-9 or 2.0 * band > (
        spring_joint.LOOP_ENVELOPE + 1e-9
    ):
        raise RuntimeError(
            "counter upper loop does not rest on the end face inside its "
            f"envelope: centre {seat_shift:.9f} off, face gap {face_gap:.9f}, "
            f"band {2.0 * band:.4f} vs {spring_joint.LOOP_ENVELOPE:.4f} mm"
        )
    coil_top = (
        pose.centre_xy[1]
        + uy * counter_stock.coil_end_x_mm(pose.length_mm)
        + abs(ux) * counter_stock.COIL_MEAN_RADIUS_MM
        + counter_stock.WIRE_RADIUS_MM
    )
    main_coil_gap = screw_y - sm_gooseneck_geom.TUBE_DIA / 2.0 - coil_top
    # The native seat certificate is taken with the loop on the end face, but
    # the free eye slides out along the shoulder up to EYE_AXIAL_PLAY_MAX
    # (sm_gooseneck_spring_joint). The independent bound of that envelope: the
    # half-turn against the arm and the head at EYE_SHIFT_SAMPLES evenly
    # spaced shifts, both ends included, each the rigid shift
    # counter_half_turn_clearances bounds.
    steps = EYE_SHIFT_SAMPLES - 1
    shifts = tuple(
        spring_joint.EYE_AXIAL_PLAY_MAX * index / steps for index in range(steps + 1)
    )
    sweep = [
        (
            *spring_mounts.counter_half_turn_clearances(
                pose, screw_y, eye_shift=shift
            ),
            shift,
        )
        for shift in shifts
    ]
    tube_gap, tube_at, _ = min((tube, shift, head) for tube, head, shift in sweep)
    head_gap, head_at, _ = min((head, shift, tube) for tube, head, shift in sweep)
    if min(main_coil_gap, tube_gap, head_gap) < spring_mounts.MIN_CLEARANCE_MM:
        raise RuntimeError(
            f"counter coil/support clearance: main {main_coil_gap:.3f}, "
            f"half-turn/tube {tube_gap:.3f} at eye shift {tube_at:.4f}, "
            f"half-turn/head {head_gap:.3f} at eye shift {head_at:.4f} mm "
            f"(shift 0..{spring_joint.EYE_AXIAL_PLAY_MAX:.4f})"
        )
    log(
        f"counter upper support: loaded head retention {retention:.3f}, loop face gap "
        f"{face_gap:.9f}, axial play {spring_joint.EYE_AXIAL_PLAY_MIN:.4f}.."
        f"{spring_joint.EYE_AXIAL_PLAY_MAX:.4f}, main coil {main_coil_gap:.3f}, "
        f"least half-turn tube/head {tube_gap:.3f}/{head_gap:.3f} mm at "
        f"eye shifts {tube_at:.4f}/{head_at:.4f}"
    )
