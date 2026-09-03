r"""Pure-data geometry contract for the crankshaft-end cap hardware.

The photographed crank end has two distinct coaxial pieces: a broad brass
annular cap over the crank-arm boss and a small slotted screw at its centre.
Both parts are authored along local +Z from their shared under-head / outer-cap
seat so the drive-train assembly can place them without orientation transforms.
"""

from __future__ import annotations

from crank_pin_spec import BIG_END_DIA, PIN_LENGTH, SMALL_END_DIA
from _holes import DRILL_POINT_H, TAP_DRILL_MM


# Brass cap: the OD matches the crank-arm boss envelope (ARM_WIDTH = 16 mm),
# while the centre hole clears the #0 retaining screw major diameter.
WASHER_OD = 16.0
WASHER_ID = 1.8
WASHER_THICK = 1.0

# The stock #4-40 fillister screw is 4 mm under-head and would enter the
# transverse taper-pin envelope after passing through the cap.  Even #2-56
# needs too much drill-point reach for useful engagement ahead of the finished
# 1:48 taper, so the dedicated screw uses the smallest common Unified size.
SCREW_THREAD = "#0-80"
SCREW_SHANK_DIA = 1.10
SCREW_SHANK_LEN = 1.55
SCREW_HEAD_DIA = 4.0
SCREW_HEAD_H = 1.6
SCREW_SLOT_W = 0.6
SCREW_SLOT_D = 0.45

# Bottoming shaft-end tap.  A 3/64-in tap drill (the standard #0-80 drill)
# leaves a conservative web before the FINISHED taper-pin bore, not merely its
# smaller #9 pilot.  Thread engagement is nearly two complete 80-TPI turns.
SHAFT_TAP_DRILL_DIA = TAP_DRILL_MM[SCREW_THREAD]
SHAFT_TAP_DRILL_DEPTH = 0.58
SHAFT_THREAD_DEPTH = 0.55
THREAD_PITCH = 25.4 / 80.0

# Finished 1:48 pin envelope at the crankshaft axis. The pin's Ø5.9375 big
# end starts 3.85 mm proud of the Ø16 arm boss: its Ø1.2 keeper wire is
# centred 3 mm from the big end with 0.25 mm air to the boss. This puts the
# shaft axis 11.85 mm from that end; its local axial centre remains 4 mm from
# the crank end.
FINISHED_TAPER_BIG_END_DIA = BIG_END_DIA
FINISHED_TAPER_BIG_END_TO_SHAFT_AXIS = 11.85
FINISHED_TAPER_AXIS_STATION = 4.0
FINISHED_TAPER_DIA_AT_SHAFT_AXIS = (
    FINISHED_TAPER_BIG_END_DIA
    - FINISHED_TAPER_BIG_END_TO_SHAFT_AXIS * (BIG_END_DIA - SMALL_END_DIA) / PIN_LENGTH
)
FINISHED_TAPER_NEAR_END = (
    FINISHED_TAPER_AXIS_STATION - FINISHED_TAPER_DIA_AT_SHAFT_AXIS / 2.0
)

SCREW_ENGAGEMENT = SCREW_SHANK_LEN - WASHER_THICK
SCREW_ENGAGED_TURNS = SCREW_ENGAGEMENT / THREAD_PITCH
SHAFT_TAP_POINT_END = SHAFT_TAP_DRILL_DEPTH + SHAFT_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
SHAFT_TAP_TO_FINISHED_TAPER_WEB = FINISHED_TAPER_NEAR_END - SHAFT_TAP_POINT_END
MIN_TAP_TO_TAPER_WEB = 0.20
SCREW_TO_FINISHED_TAPER_CLEARANCE = FINISHED_TAPER_NEAR_END - SCREW_ENGAGEMENT
MIN_SCREW_TO_TAPER_CLEARANCE = 0.25
MIN_ENGAGED_TURNS = 1.5
if SHAFT_TAP_TO_FINISHED_TAPER_WEB < MIN_TAP_TO_TAPER_WEB:
    raise AssertionError("shaft-end tap leaves too little web before finished taper")
if SCREW_ENGAGED_TURNS < MIN_ENGAGED_TURNS:
    raise AssertionError("crank retaining screw has insufficient thread engagement")
if SCREW_TO_FINISHED_TAPER_CLEARANCE < MIN_SCREW_TO_TAPER_CLEARANCE:
    raise AssertionError("retaining screw reaches the finished taper envelope")
