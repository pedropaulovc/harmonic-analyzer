"""Pure geometry of the made MHA-SM-004 counter-spring clamp screw.

Native frame: axis Z, under-head face Z=0, head +Z, shank -Z. The
thread is represented by its basic major cylinder, not a die blank with a
made-up general diameter tolerance. The external UNC-2A callout defines it.
No drawing, prose, builder or COM dependencies belong in this module.
"""

from __future__ import annotations

from _printed_tolerance import printed_deviations

MM_PER_IN = 25.4
STOCK_DIA = 0.5 * MM_PER_IN
THREAD = "#6-32 UNC"
MAJOR_DIA = 0.138 * MM_PER_IN
PITCH = MM_PER_IN / 32.0
LENGTH = 16.00  # Under-head face to tip, including relief and chamfer.
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
RELIEF_DIA = 2.20
RELIEF_DIA_TOL = 0.05
RELIEF_DIA_LOWER, RELIEF_DIA_UPPER = printed_deviations(
    RELIEF_DIA, 2, (-RELIEF_DIA_TOL, RELIEF_DIA_TOL)
)
RELIEF_WIDTH = 2.20  # Under-head face to the full-thread flank.
RELIEF_WIDTH_LOWER, RELIEF_WIDTH_UPPER = printed_deviations(RELIEF_WIDTH, 2)
RELIEF_LEAD = 0.30  # Axial and radial legs of the ordinary 45-degree lead.
RELIEF_LEAD_TOL = 0.10
RELIEF_LEAD_LOWER, RELIEF_LEAD_UPPER = printed_deviations(
    RELIEF_LEAD, 2, (-RELIEF_LEAD_TOL, RELIEF_LEAD_TOL)
)
TIP_CHAMFER = 0.30
TIP_CHAMFER_BAND = (0.05, -0.10)  # (upper, lower), as on MHA-DT-032.
TIP_CHAMFER_LOWER, TIP_CHAMFER_UPPER = printed_deviations(
    TIP_CHAMFER, 2, (TIP_CHAMFER_BAND[1], TIP_CHAMFER_BAND[0])
)

# #6-32 UNC-2A pitch-diameter minimum, ASME B1.1 as tabled by Engineers Edge
# (read 2026-10-10, https://www.engineersedge.com/screw_threads_chart.htm).
THREAD_PD_2A_MIN_IN = 0.1141
# DERIVED ESTIMATE, not a standard minimum minor-diameter limit: the repo's
# deepest die-root construction takes a full basic half-depth (0.649519 P)
# below the minimum 2A pitch diameter. The table publishes a minor MAXIMUM,
# not this minimum. The largest relief must clear the estimated deeper root.
THREAD_MINOR_2A_MIN_EST = (THREAD_PD_2A_MIN_IN - 0.649519 / 32.0) * MM_PER_IN
RELIEF_DIA_MAX = RELIEF_DIA + RELIEF_DIA_UPPER
RELIEF_LEAD_MIN = RELIEF_LEAD + RELIEF_LEAD_LOWER
RELIEF_LEAD_MAX = RELIEF_LEAD + RELIEF_LEAD_UPPER
RELIEF_FLOOR_MIN = RELIEF_WIDTH + RELIEF_WIDTH_LOWER - RELIEF_LEAD_MAX
SEAT_FLAT_INNER_DIA_MAX = RELIEF_DIA_MAX + 2.0 * RELIEF_LEAD_MAX
TIP_CHAMFER_MIN = TIP_CHAMFER + TIP_CHAMFER_LOWER
TIP_CHAMFER_MAX = TIP_CHAMFER + TIP_CHAMFER_UPPER
OVERALL_LENGTH = LENGTH + HEAD_H
SLOT_FLOOR_Z = HEAD_H - SLOT_DEPTH


def require_relief_clearance(
    diameter_max: float = RELIEF_DIA_MAX,
    floor_min: float = RELIEF_FLOOR_MIN,
    lead_outer_dia_max: float = SEAT_FLAT_INNER_DIA_MAX,
) -> None:
    """Refuse a relief that cannot clear the die or leaves no flat head seat."""
    if diameter_max > THREAD_MINOR_2A_MIN_EST:
        raise AssertionError("screw relief stands above the estimated deepest die root")
    if floor_min < 1.5 * PITCH:
        raise AssertionError(
            "screw relief needs at least 1.5 pitches of straight floor"
        )
    if lead_outer_dia_max >= MAJOR_DIA:
        raise AssertionError("screw relief lead consumes the flat under-head seat")


require_relief_clearance()
