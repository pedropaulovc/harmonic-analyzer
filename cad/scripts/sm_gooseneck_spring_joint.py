"""Full-thread and wall budgets for the gooseneck's clamped spring eye.

The 1-inch stock screw passes through the brazed plug into the open tube.
Its incomplete tip threads therefore lie beyond the receiver, rather than
reducing the plug's usable full-thread length. The upper eye is clamped,
not left free to swivel (user ruling 2026-09-21).
"""

from __future__ import annotations

import _config
import sm_gooseneck_geom as gooseneck
import vn_counter_spring_stock_geom as spring
import vn_gooseneck_spring_screw_spec as screw
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm

TAP_SPEC = HoleSpec("tapped", "5/16-18", end="through_all", thread_class="2B")
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
PLUG_DIA = gooseneck.TUBE_DIA - 2.0 * gooseneck.WALL_T
PLUG_DIAMETER_BAND = printed_band_mm(2)
PLUG_LENGTH_BAND = printed_band_mm(2)
THREAD_AXIS_OFFSET_MAX = 0.15
DRILL_WANDER_MAX = 0.10
EDGE_BREAK = float(_config.title_block("edge_break")["chamfer_max_mm"])

# The through tap exits into air; neither tap lead nor screw tip is counted as
# receiver thread. The title-block edge break can remove thread at both faces.
ENGAGEMENT_NOMINAL = gooseneck.PLUG_LENGTH - 2.0 * EDGE_BREAK
ENGAGEMENT_MIN = ENGAGEMENT_NOMINAL - PLUG_LENGTH_BAND
ENGAGEMENT_MIN_D = 1.5
PLUG_WALL_NOMINAL = (PLUG_DIA - screw.MAJOR_DIA) / 2.0
PLUG_WALL_MIN = (
    (PLUG_DIA - PLUG_DIAMETER_BAND - screw.MAJOR_DIA) / 2.0
    - THREAD_AXIS_OFFSET_MAX
    - DRILL_WANDER_MAX
)
HEAD_RETENTION = (screw.HEAD_DIA - spring.EYE_ID_MM) / 2.0

SCREW_REACH = screw.LENGTH - gooseneck.SPRING_EYE_GAP
SCREW_REACH_MIN = SCREW_REACH - screw.LENGTH_MINUS
SCREW_END_INCOMPLETE_MAX = 1.5 * screw.PITCH
FULL_THREAD_REACH_MIN = SCREW_REACH_MIN - SCREW_END_INCOMPLETE_MAX
PLUG_INNER_X = gooseneck.ARM_END_X + gooseneck.PLUG_LENGTH
SCREW_TIP_X = gooseneck.ARM_END_X + SCREW_REACH
TIP_PROTRUSION = SCREW_REACH - gooseneck.PLUG_LENGTH
TIP_PROTRUSION_MIN = SCREW_REACH_MIN - (
    gooseneck.PLUG_LENGTH + PLUG_LENGTH_BAND
)
# The straight tube's hollow bore continues to the bend exit at part X=-BEND_R.
# Stock length-minus is conservative; the selected stock length is the maximum.
TIP_TO_BEND_MIN = gooseneck.ARM_RUN - SCREW_REACH
TIP_BORE_RADIAL_CLEARANCE_MIN = (
    PLUG_DIA - PLUG_DIAMETER_BAND - screw.MAJOR_DIA
) / 2.0 - THREAD_AXIS_OFFSET_MAX - DRILL_WANDER_MAX

if TAP_SPEC.size != screw.THREAD.split()[0] or TAP_SPEC.thread_class != "2B":
    raise AssertionError("gooseneck spring screw does not match its through tap")
if ENGAGEMENT_MIN < ENGAGEMENT_MIN_D * screw.MAJOR_DIA:
    raise AssertionError("gooseneck spring screw loses 1.5D full engagement")
if FULL_THREAD_REACH_MIN <= gooseneck.PLUG_LENGTH + PLUG_LENGTH_BAND:
    raise AssertionError("gooseneck screw incomplete tip thread reaches the plug")
if min(TIP_PROTRUSION_MIN, TIP_TO_BEND_MIN, TIP_BORE_RADIAL_CLEARANCE_MIN) <= 0.0:
    raise AssertionError("gooseneck screw tip is not clear in the open tube bore")
if PLUG_WALL_NOMINAL < 2.0 or PLUG_WALL_MIN < 1.5:
    raise AssertionError("gooseneck plug loses a rule-12 wall")
if HEAD_RETENTION < 1.0:
    raise AssertionError("gooseneck screw head does not retain the spring eye")
