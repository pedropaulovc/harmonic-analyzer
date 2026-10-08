"""Pure machine-space hanger datums shared by the arm, plate and chain.

The rack mounting height absorbs feed tooth-system changes. The stud, pivot,
arm outline and latch keep their existing machine pose; only the disc mesh's
knob axis and its plate mounting taps follow the reducer centre distance.
No assembly, builder, knob-shaft or arm imports belong here.
"""

from __future__ import annotations

import math

import pd_rack_pinion_spec as DISC
import pd_support_bar_spec as BAR

GUIDE_Y = (283.734, 317.734)
BAR_CY = GUIDE_Y[1] - BAR.BAR_HEIGHT / 2.0
PIVOT_XY = (BAR.PIVOT_TAP_X, BAR_CY + BAR.HANGER_TAP_Y)
# Preserve the original DP30 rack pose's exact stud datum, not its rounded
# drawing coordinate. The replacement rack is positioned relative to this.
STUD_XY = (0.0, 266.2006666666667)
MESH_ANGLE_DEG = -168.0
KNOB_SHAFT_XY = (
    STUD_XY[0] + DISC.CENTRE_DISTANCE * math.cos(math.radians(MESH_ANGLE_DEG)),
    STUD_XY[1] + DISC.CENTRE_DISTANCE * math.sin(math.radians(MESH_ANGLE_DEG)),
)

ARM_REACH = math.dist(PIVOT_XY, STUD_XY)
ARM_U = (
    (STUD_XY[0] - PIVOT_XY[0]) / ARM_REACH,
    (STUD_XY[1] - PIVOT_XY[1]) / ARM_REACH,
)
ARM_N = (-ARM_U[1], ARM_U[0])
ARM_ANGLE_DEG = math.degrees(math.atan2(ARM_U[1], ARM_U[0]))
_K_FROM_P = (
    KNOB_SHAFT_XY[0] - PIVOT_XY[0],
    KNOB_SHAFT_XY[1] - PIVOT_XY[1],
)
BORE_STATION = _K_FROM_P[0] * ARM_U[0] + _K_FROM_P[1] * ARM_U[1]
BORE_OFFSET = _K_FROM_P[0] * ARM_N[0] + _K_FROM_P[1] * ARM_N[1]

# Plate centreline relative to its bore: the two taps must move with it.
PLATE_WIDTH = 31.75
PLATE_END_R = 12.5
PLATE_SCREW_MID_STATION = BORE_STATION + PLATE_END_R - PLATE_WIDTH / 2.0
