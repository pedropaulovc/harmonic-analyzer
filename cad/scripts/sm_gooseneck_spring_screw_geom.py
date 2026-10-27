"""Pure geometry of the made MHA-SM-04 counter-spring clamp screw.

Native frame: axis Z, under-head face Z=0, head +Z, shank -Z. The
thread is represented by its basic major cylinder, not a die blank with a
made-up general diameter tolerance. The external UNC-2A callout defines it.
No drawing, prose, builder or COM dependencies belong in this module.

Owner ruling 2026-10-26 (#1951, option B): a custom shoulder screw.  Under the
head a plain turned Ø3.50 shoulder is the counter spring's loop seat, at the
height the #6-32 thread crests gave it before; a 45-degree lead steps up to an
#8-32 UNC thread that runs through the MHA-SM-01 plug, retapped #8-32.  The
2026-09-21 rulings stand: the head clamps the loop to the plug face (no torque
value, no threadlocker).  The ruling supersedes the #6-32 the 2026-10-10
option-B note named.  ``sm_gooseneck_spring_screw_spec`` carries the strength
case; ``sm_gooseneck_spring_joint`` the seat, engagement and wall budgets.
"""

from __future__ import annotations

import math

from _printed_tolerance import printed_deviations

MM_PER_IN = 25.4
STOCK_DIA = 0.5 * MM_PER_IN
THREAD_SIZE = "#8-32"
THREAD = f"{THREAD_SIZE} UNC"
THREADS_PER_IN = 32
MAJOR_DIA = 0.164 * MM_PER_IN
PITCH = MM_PER_IN / THREADS_PER_IN
LENGTH = 16.00  # Under-head face to tip, including shoulder, lead and chamfer.
LENGTH_LOWER, LENGTH_UPPER = printed_deviations(LENGTH, 2)
HEAD_DIA = 12.50
HEAD_DIA_LOWER, HEAD_DIA_UPPER = printed_deviations(HEAD_DIA, 2)
HEAD_H = 7.00  # Overall head height, NOT the cylindrical side alone.
HEAD_H_LOWER, HEAD_H_UPPER = printed_deviations(HEAD_H, 2)
CROWN_RISE = 1.00  # Controlling sagitta; the cylindrical side is derived.
CROWN_RISE_LOWER, CROWN_RISE_UPPER = printed_deviations(CROWN_RISE, 2)
HEAD_CYL_H = HEAD_H - CROWN_RISE
CROWN_RADIUS = ((HEAD_DIA / 2.0) ** 2 + CROWN_RISE**2) / (2.0 * CROWN_RISE)
CROWN_CENTER_Z = HEAD_H - CROWN_RADIUS
SLOT_WIDTH = 1.60
SLOT_WIDTH_LOWER, SLOT_WIDTH_UPPER = printed_deviations(SLOT_WIDTH, 2)
SLOT_DEPTH = 3.00  # From the uncut crown apex, not its cylindrical rim.
SLOT_DEPTH_LOWER, SLOT_DEPTH_UPPER = printed_deviations(SLOT_DEPTH, 2)

# #8-32 UNC-2A limits, ASME B1.1 as tabled by Engineers Edge (read 2026-10-26,
# https://www.engineersedge.com/screw_threads_chart.htm): major 0.1631/0.1571
# in, pitch diameter 0.1428/0.1399 in.
THREAD_MAJOR_2A_MIN_IN = 0.1571
THREAD_PD_2A_MIN_IN = 0.1399
THREAD_MAJOR_2A_MIN = THREAD_MAJOR_2A_MIN_IN * MM_PER_IN
# DERIVED ESTIMATE, not a standard minimum minor-diameter limit: the repo's
# deepest die-root construction takes a full basic half-depth (0.649519 P)
# below the minimum 2A pitch diameter (pd_vn_transgear_pivot_screw_spec uses
# the same construction for its #8-32): 3.038.
THREAD_MINOR_2A_MIN_EST = (THREAD_PD_2A_MIN_IN - 0.649519 / THREADS_PER_IN) * MM_PER_IN

# The loop seat: a plain turned shoulder from the under-head face, at the
# owner's Ø3.50 (today's #6-32 crest height, 3.5052, within 0.003 radial), so
# the loop, the spring's line of action and the coil/tube gap stay where the
# native calibration left them.  It prints as the LIMIT band 3.60/3.40: the
# upper limit keeps the seat under the #8-32 2A major minimum, 3.990, so the
# lead always steps UP into the thread blank and the die's run-out stays on
# that blank; the title block's 4.01 would cross it.
SEAT_DIA = 3.50
SEAT_DIA_LOWER, SEAT_DIA_UPPER = -0.10, 0.10
SEAT_DIA_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
SEAT_DIA_MIN = round(SEAT_DIA + SEAT_DIA_LOWER, 6)
SEAT_DIA_MAX = round(SEAT_DIA + SEAT_DIA_UPPER, 6)
# Under-head face to the FOOT of the 45-degree lead (the end of the seat).  It
# prints as the LIMIT band 4.10/3.70: the shortest shoulder still keeps the
# loop's plug-side pass clear of the lead, and the longest still starts full
# thread within the 1.5D engagement budget inside the plug
# (sm_gooseneck_spring_joint owns both checks).  The title block's +/-0.51
# fits neither end.
SHOULDER_LENGTH = 3.90
SHOULDER_LENGTH_LOWER, SHOULDER_LENGTH_UPPER = -0.20, 0.20
SHOULDER_LENGTH_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
SHOULDER_LENGTH_MIN = round(SHOULDER_LENGTH + SHOULDER_LENGTH_LOWER, 6)
SHOULDER_LENGTH_MAX = round(SHOULDER_LENGTH + SHOULDER_LENGTH_UPPER, 6)
# The lead rises at 45 degrees from the seat to the thread major: its legs are
# set by the two diameters, not printed separately (the model holds the 45 by
# equation; the shoulder length's callout names the lead's foot and angle).
STEP_LEAD = (MAJOR_DIA - SEAT_DIA) / 2.0
STEP_LEAD_MAX = (MAJOR_DIA - SEAT_DIA_MIN) / 2.0
# The die runs up to the lead and leaves its chamfered start, 1.5 pitches of
# incomplete thread (drawing-guidelines.md rule 18; the repo's tip allowance,
# sm_gooseneck_spring_joint.SCREW_END_INCOMPLETE_MAX), on the thread blank
# behind the lead.  DIE_RUNOUT is the derivation input only; the sheet prints
# the station it sets.
DIE_RUNOUT = 1.5 * PITCH
FULL_THREAD_STATION = SHOULDER_LENGTH + STEP_LEAD + DIE_RUNOUT
# Printed as the single limit "5.67 MAX" from the under-head face (machinist
# FIX round 1, owner ruling 2026-10-26 (#1951, option B)): the longest
# shoulder, the steepest-legged lead and the die's run-out, floored to the
# print's two places so the printed limit never exceeds the budget
# sm_gooseneck_spring_joint.MATED_ENGAGEMENT_MIN takes.
FULL_THREAD_STATION_MAX = (
    math.floor((SHOULDER_LENGTH_MAX + STEP_LEAD_MAX + DIE_RUNOUT) * 100.0) / 100.0
)
FULL_THREAD_STATION_MAX_TOL_TYPE = 6  # swTolType_e.swTolMAX
# The full thread cannot start before the lead's top on the shortest shoulder
# and largest seat (zero run-out), so the MAX's native band runs from there up
# to the limit: (upper, lower) about the modelled limit.
FULL_THREAD_STATION_MIN = SHOULDER_LENGTH_MIN + (MAJOR_DIA - SEAT_DIA_MAX) / 2.0
FULL_THREAD_STATION_MAX_BAND = (
    0.0,
    -round(FULL_THREAD_STATION_MAX - FULL_THREAD_STATION_MIN, 6),
)
# The longest shoulder must still leave a die one pitch of blank behind the
# lead before the printed limit: anything tighter is not die-cuttable.
FULL_THREAD_DIE_ROOM_MIN = SHOULDER_LENGTH_MAX + STEP_LEAD_MAX + 1.0 * PITCH
# The thread-start chamfer rides the title block's one-place band.
TIP_CHAMFER = 0.30
OVERALL_LENGTH = LENGTH + HEAD_H
SLOT_FLOOR_Z = HEAD_H - SLOT_DEPTH


def require_shoulder_form(
    seat_dia_max: float = SEAT_DIA_MAX,
    seat_dia_min: float = SEAT_DIA_MIN,
    full_thread_station_max: float = FULL_THREAD_STATION_MAX,
) -> None:
    """Refuse a seat that is not a step DOWN from the thread, or a thread too short."""
    if seat_dia_max >= THREAD_MAJOR_2A_MIN:
        raise AssertionError("screw loop seat reaches the #8-32 thread major")
    if seat_dia_min <= 0.0:
        raise AssertionError("screw loop seat has no diameter")
    if full_thread_station_max + TIP_CHAMFER + 1.5 * PITCH >= LENGTH + LENGTH_LOWER:
        raise AssertionError("screw leaves no full thread between the lead and the tip")
    if full_thread_station_max < FULL_THREAD_DIE_ROOM_MIN:
        raise AssertionError(
            "screw full-thread limit leaves a die no room behind the lead"
        )


require_shoulder_form()
