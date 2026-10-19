"""Paper-drive pivot, stud and rack placement without feed-law checks."""

from __future__ import annotations

import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as arm
import pd_transgear_feed_pinion_spec
from pd_latch_hook_geometry import BAR_CENTRE_Y

# Keep the existing pivot/latch/stud pose. Mount the stock rack and backer at
# the shifted feed pitch line; relocate only the reducer's knob bearing.
PLATEN_BOTTOM_Y = 273.234
PIVOT_XY = (bar.PIVOT_TAP_X, BAR_CENTRE_Y + bar.HANGER_TAP_Y)
STUD_XY = (
    arm.STUD_MACHINE_X,
    PIVOT_XY[1] + arm.PIN_STATION * arm.ARM_U[1],
)
KNOB_SHAFT_XY = (
    PIVOT_XY[0]
    + arm.KNOB_BORE_STATION * arm.ARM_U[0]
    + arm.KNOB_BORE_OFFSET * arm.ARM_N[0],
    PIVOT_XY[1]
    + arm.KNOB_BORE_STATION * arm.ARM_U[1]
    + arm.KNOB_BORE_OFFSET * arm.ARM_N[1],
)
RACK_PITCH_Y = STUD_XY[1] + pd_transgear_feed_pinion_spec.RACK_AXIS_DISTANCE
RACK_TIP_Y = RACK_PITCH_Y - pd_transgear_feed_pinion_spec.MODULE_MM
RACK_CREST_DROP = PLATEN_BOTTOM_Y - RACK_TIP_Y
