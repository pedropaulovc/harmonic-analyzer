"""Seat, full-thread and wall budgets for the gooseneck's clamped spring eye.

The shop-turned screw passes through the brazed plug into the open tube.
Its incomplete tip threads lie beyond the receiver, rather than reducing
the plug's usable full-thread length. The upper eye is clamped,
not left free to swivel (user ruling 2026-09-21).  Owner ruling 2026-10-26
(#1951, option B): the loop sits on the screw's plain Ø3.50 shoulder, and the
#8-32 thread past the shoulder's 45-degree lead runs through the MHA-SM-01
plug, retapped #8-32 UNC-2B THRU.
"""

from __future__ import annotations

import math

import _config
import sm_gooseneck_geom as gooseneck
import sm_vn_counter_spring_stock_geom as spring
import sm_gooseneck_spring_screw_geom as screw
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm

TAP_SPEC = HoleSpec("tapped", screw.THREAD_SIZE, end="through_all", thread_class="2B")
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
PLUG_DIA = gooseneck.TUBE_DIA - 2.0 * gooseneck.WALL_T
PLUG_DIAMETER_BAND = printed_band_mm(2)
PLUG_LENGTH_BAND = printed_band_mm(2)
THREAD_AXIS_OFFSET_MAX = 0.15
DRILL_WANDER_MAX = 0.10
# The plug is turned to the measured tube bore for a silver-braze (BAg-7)
# joint: the diametral faying clearance is the mating requirement. The
# retained Ø band still limits the plug, and the wall budget below uses its
# lower limit.
BRAZE_CLEARANCE_MIN = 0.05
BRAZE_CLEARANCE_MAX = 0.13
EDGE_BREAK = float(_config.title_block("edge_break")["chamfer_max_mm"])

# The through tap exits into air; neither tap lead nor screw tip is counted as
# receiver thread. The title-block edge break can remove thread at both faces.
# This is the RECEIVER's full thread, the figure MHA-SM-01 prints.
ENGAGEMENT_NOMINAL = gooseneck.PLUG_LENGTH - 2.0 * EDGE_BREAK
ENGAGEMENT_MIN = ENGAGEMENT_NOMINAL - PLUG_LENGTH_BAND
ENGAGEMENT_MIN_D = 1.5
# The screw's own full thread starts behind its shoulder lead and the die's
# run-out (sm_gooseneck_spring_screw_geom.FULL_THREAD_STATION, from the head).
# Past the clamp gap that station lies inside the plug, so the MATED full
# thread starts at the later of it and the plug mouth's edge break.
SCREW_RUNOUT_INTRUSION = screw.FULL_THREAD_STATION - gooseneck.SPRING_EYE_GAP
SCREW_RUNOUT_INTRUSION_MAX = screw.FULL_THREAD_STATION_MAX - gooseneck.SPRING_EYE_GAP
MATED_ENGAGEMENT_NOMINAL = (
    gooseneck.PLUG_LENGTH - EDGE_BREAK - max(EDGE_BREAK, SCREW_RUNOUT_INTRUSION)
)
MATED_ENGAGEMENT_MIN = (
    gooseneck.PLUG_LENGTH
    - PLUG_LENGTH_BAND
    - EDGE_BREAK
    - max(EDGE_BREAK, SCREW_RUNOUT_INTRUSION_MAX)
)

# drawing-guidelines.md rule 17 wall between the tap and the plug's turned
# OD, FULL worst case (brief 2026-10-26), every term cited:
#  * the plug OD at its lower printed limit (PLUG_DIAMETER_BAND, title-block
#    .XX: the retained Ø band on MHA-SM-01 note 3);
#  * the tap at its basic major plus 0.025 root oversize (TAP_ROOT_OVERSIZE);
#  * the tap's locating band, thread axis to tube axis (MHA-SM-01 note 4,
#    THREAD_AXIS_OFFSET_MAX), and its printed DRILL WANDER (same note);
#  * 0.3 degrees of drill run-off over the longest plug: the plug OD is turned
#    before brazing and the hole is drilled after, in a DIFFERENT setup
#    located on the tube (note 4), so the run-off term applies;
#  * the title-block 0.25 edge break on the tap mouth and on the plug blank's
#    OD edge at the face (counted although the braze fillet fills the second).
TAP_ROOT_OVERSIZE = 0.025
DRILL_RUNOFF_DEG = 0.3
DRILL_RUNOFF_MAX = (gooseneck.PLUG_LENGTH + PLUG_LENGTH_BAND) * math.tan(
    math.radians(DRILL_RUNOFF_DEG)
)
PLUG_WALL_NOMINAL = (PLUG_DIA - screw.MAJOR_DIA) / 2.0
PLUG_WALL_MIN = (
    (PLUG_DIA - PLUG_DIAMETER_BAND) / 2.0
    - (screw.MAJOR_DIA + TAP_ROOT_OVERSIZE) / 2.0
    - THREAD_AXIS_OFFSET_MAX
    - DRILL_WANDER_MAX
    - DRILL_RUNOFF_MAX
    - 2.0 * EDGE_BREAK
)
PLUG_WALL_TARGET = 2.0
HEAD_RETENTION = (screw.HEAD_DIA - spring.EYE_ID_MM) / 2.0
HEAD_RETENTION_MIN = (screw.HEAD_DIA + screw.HEAD_DIA_LOWER - spring.EYE_ID_MM) / 2.0

# The loop on its seat.  The clamp fixes the loop's two pull-side passes (the
# wire that bears on the screw) at these stations from the head face: the
# half-turn clocking sends loop +Z toward the plug (spring_mount_geom
# counter_pose, build_sm_summing_assembly).  Both passes must bear on the
# plain seat alone, so the wire's section clears every other surface.
LOOP_PASS_X = tuple(
    gooseneck.SPRING_EYE_GAP / 2.0 - spring.LOOP_HALF_RISE_MM + spring.LOOP_RISE_MM * t
    for t in (1.0 / (4.0 * spring.LOOP_TURNS), 5.0 / (4.0 * spring.LOOP_TURNS))
)
WIRE_R = spring.WIRE_RADIUS_MM
# Plug-side pass vs the 45-degree lead at the SHORTEST shoulder.  The wire
# rests on the seat, so the clearance depends on the stations only.
LOOP_LEAD_CLEARANCE_MIN = (
    screw.SHOULDER_LENGTH_MIN - LOOP_PASS_X[1] + WIRE_R
) / math.sqrt(2.0) - WIRE_R
# Head-side pass vs the largest inside corner the title block allows under the
# head ("INSIDE CORNERS R1.0 MAX"): past the fillet's tangent point the wire
# meets the fillet's end, not its arc.
INSIDE_CORNER_R_MAX = float(_config.title_block("inside_corner")["radius_mm"])
LOOP_CORNER_CLEARANCE_MIN = (
    math.hypot(LOOP_PASS_X[0] - INSIDE_CORNER_R_MAX, WIRE_R) - WIRE_R
)

SCREW_REACH = screw.LENGTH - gooseneck.SPRING_EYE_GAP
SCREW_REACH_MIN = SCREW_REACH + screw.LENGTH_LOWER
SCREW_REACH_MAX = SCREW_REACH + screw.LENGTH_UPPER
SCREW_END_INCOMPLETE_MAX = 1.5 * screw.PITCH
FULL_THREAD_REACH_MIN = SCREW_REACH_MIN - SCREW_END_INCOMPLETE_MAX
PLUG_INNER_X = gooseneck.ARM_END_X + gooseneck.PLUG_LENGTH
SCREW_TIP_X = gooseneck.ARM_END_X + SCREW_REACH
TIP_PROTRUSION = SCREW_REACH - gooseneck.PLUG_LENGTH
TIP_PROTRUSION_MIN = SCREW_REACH_MIN - (gooseneck.PLUG_LENGTH + PLUG_LENGTH_BAND)
# The straight tube's hollow bore continues to the bend exit at part X=-BEND_R.
# The longest accepted screw still ends in the open straight bore.
TIP_TO_BEND_MIN = gooseneck.ARM_RUN - SCREW_REACH_MAX
TIP_BORE_RADIAL_CLEARANCE_MIN = (
    (PLUG_DIA - PLUG_DIAMETER_BAND - screw.MAJOR_DIA) / 2.0
    - THREAD_AXIS_OFFSET_MAX
    - DRILL_WANDER_MAX
    - DRILL_RUNOFF_MAX
)

if TAP_SPEC.size != screw.THREAD_SIZE or TAP_SPEC.thread_class != "2B":
    raise AssertionError("gooseneck spring screw does not match its through tap")
if min(ENGAGEMENT_MIN, MATED_ENGAGEMENT_MIN) < ENGAGEMENT_MIN_D * screw.MAJOR_DIA:
    raise AssertionError("gooseneck spring screw loses 1.5D full engagement")
if FULL_THREAD_REACH_MIN <= gooseneck.PLUG_LENGTH + PLUG_LENGTH_BAND:
    raise AssertionError("gooseneck screw incomplete tip thread reaches the plug")
if min(TIP_PROTRUSION_MIN, TIP_TO_BEND_MIN, TIP_BORE_RADIAL_CLEARANCE_MIN) <= 0.0:
    raise AssertionError("gooseneck screw tip is not clear in the open tube bore")
if PLUG_WALL_MIN < PLUG_WALL_TARGET:
    raise AssertionError(
        "gooseneck plug loses a drawing-guidelines.md rule 17 (walls and webs) wall"
    )
if HEAD_RETENTION_MIN < 1.0:
    raise AssertionError("gooseneck screw head does not retain the spring eye")
if min(LOOP_LEAD_CLEARANCE_MIN, LOOP_CORNER_CLEARANCE_MIN) <= 0.0:
    raise AssertionError("gooseneck spring loop bears off the screw's plain seat")
if not LOOP_PASS_X[0] < LOOP_PASS_X[1] < screw.SHOULDER_LENGTH_MIN:
    raise AssertionError("gooseneck spring loop passes do not lie on the seat")
