r"""Gooseneck geometry nominals; the light assembly import surface.

Part origin is the vertical leg's mid-height. The arm runs toward negative
part X; the summing assembly places it Ry(180), so machine X = COLUMN_X -
part X. Sliding the post sets spring tension, not the part's dimensions.

Owner rulings 2026-10-27 (#1951), rederived from the ch19 reference photos:
the WHOLE gooseneck is 1/2 in tube, 4130-N seamless 1/2 in OD x 0.065 in wall
(OnlineMetals 7322), bent on the stock 1/2 in x 3 in CLR die (R76.2,
Pro-Tools 105).  The arm ends flush, with no step, in a solid Ø12.70 end piece
brazed on a shank into the tube bore and tapped for MHA-SM-04.  The top
frame's Ø17 bore and hub set screw are unchanged: a 5/8 in x 0.058 in 4130-N
sleeve (OnlineMetals 7324), select-fitted from stock and brazed over the leg
from its foot, is the post they take.  The spring eye's centre and the clamp
face stay where they were.

Stock limits: OnlineMetals alloy-steel tolerances (read 2026-10-27,
https://www.onlinemetals.com/en/alloy-steel-tolerances): 4130-N cold drawn
seamless round tube, OD 0.500-1.699 in +0.007/-0.002 in; wall 10-25 % of OD
with ID under 0.500 in +/-10 %, wall under 10 % of OD with ID 0.500 in and
over +/-7.5 %.
"""

from __future__ import annotations

from sm_vn_counter_spring_stock_geom import END_OCCUPIED_WIDTH_MM

MM_PER_IN = 25.4
# The tube, OnlineMetals 7322: 4130-N seamless 1/2 in OD x 0.065 in wall.
TUBE_DIA = 0.500 * MM_PER_IN
WALL_T = 0.065 * MM_PER_IN
TUBE_BORE_DIA = TUBE_DIA - 2.0 * WALL_T
TUBE_DIA_MIN = (0.500 - 0.002) * MM_PER_IN
TUBE_DIA_MAX = (0.500 + 0.007) * MM_PER_IN
WALL_T_MIN = 0.065 * 0.90 * MM_PER_IN
WALL_T_MAX = 0.065 * 1.10 * MM_PER_IN
TUBE_BORE_DIA_MIN = TUBE_DIA_MIN - 2.0 * WALL_T_MAX
ARM_Y = 163.3  # arm/screw axis above the part origin
BEND_R = 3.0 * MM_PER_IN  # 90-degree bend centreline radius: the 1/2 in x 3 in CLR die
SPRING_EYE_X = -105.8
SPRING_EYE_GAP = END_OCCUPIED_WIDTH_MM
# The clamp face: the end piece's outer face.
ARM_END_X = SPRING_EYE_X + SPRING_EYE_GAP / 2.0
# The straight arm, from the bend's exit tangent to the clamp face.
ARM_STRAIGHT = -ARM_END_X - BEND_R
# The end piece: a solid head turned to the tube's Ø, flush with it, from the
# clamp face to the tube end, and a shank turned to the measured tube bore,
# brazed PLUG_SHANK_LENGTH deep.  The head holds the whole tapped hole
# (sm_gooseneck_spring_joint); the shank sits in the straight tube.  The head
# is long enough that the deepest tap drill's point meets the shank at the
# 2.0 wall even at the head's shortest .XX length (codjiflo P1 on #1997); the
# shank gives up what the head gains, so the end piece's length is unchanged.
PLUG_DIA = TUBE_DIA
PLUG_HEAD_LENGTH = 21.50
PLUG_SHANK_LENGTH = 4.50
PLUG_LENGTH = PLUG_HEAD_LENGTH + PLUG_SHANK_LENGTH
TUBE_END_X = ARM_END_X + PLUG_HEAD_LENGTH
# The straight tube from the bend's exit tangent to the tube end.
TUBE_STRAIGHT = -TUBE_END_X - BEND_R
if TUBE_STRAIGHT < PLUG_SHANK_LENGTH + 1.0:
    raise AssertionError("gooseneck end piece's braze shank reaches the bend")
# The leg: from its foot up to the bend's entry tangent.
LEG_BOTTOM = -330.0
LEG_TOP = round(ARM_Y - BEND_R, 3)
# The sleeve, OnlineMetals 7324: 4130-N seamless 5/8 in OD x 0.058 in wall,
# from the leg's foot to SLEEVE_TOP, 40 above the top-frame rail at the
# reference setting (build_sm_summing_assembly checks the hub's cover).
SLEEVE_DIA = 0.625 * MM_PER_IN
SLEEVE_WALL_T = 0.058 * MM_PER_IN
SLEEVE_BORE_DIA = SLEEVE_DIA - 2.0 * SLEEVE_WALL_T
SLEEVE_DIA_MIN = (0.625 - 0.002) * MM_PER_IN
SLEEVE_DIA_MAX = (0.625 + 0.007) * MM_PER_IN
SLEEVE_WALL_T_MIN = 0.058 * 0.925 * MM_PER_IN
SLEEVE_WALL_T_MAX = 0.058 * 1.075 * MM_PER_IN
SLEEVE_BORE_DIA_MIN = SLEEVE_DIA_MIN - 2.0 * SLEEVE_WALL_T_MAX
SLEEVE_BORE_DIA_MAX = SLEEVE_DIA_MAX - 2.0 * SLEEVE_WALL_T_MIN
SLEEVE_TOP = -112.0
SLEEVE_LENGTH = SLEEVE_TOP - LEG_BOTTOM
