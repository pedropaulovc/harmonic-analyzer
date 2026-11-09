r"""Gooseneck geometry nominals; the light assembly import surface.

Part origin is the vertical leg's mid-height. The arm runs toward negative
part X; the summing assembly places it Ry(180), so machine X = COLUMN_X -
part X. Sliding the post sets spring tension, not the part's dimensions.

Owner rulings 2026-10-27 (#1951), rederived from the ch19 reference photos:
the WHOLE gooseneck is 1/2 in tube, 4130-N seamless 1/2 in OD x 0.065 in wall
(OnlineMetals 7322), bent on the stock 1/2 in x 3 in CLR die (R3.0,
Pro-Tools 105).

Owner rulings 2026-11-08 (Pedro), #2315: the gooseneck is two independent
parts, each with its own drawing and MHA-SM-00 BOM row, joined at MHA-SM-00
with LOCTITE 638 (no torch, no plating):

* MHA-SM-01 ``sm-gooseneck``: the bent tube alone.  It is bent with a tail
  and its arm end is then sawn and faced to TUBE_END_X.  Its bare leg is the
  post: the reference machine has no sleeve (the #1951 5/8 in sleeve was an
  adapter for the old Ø.670 hub bore), so MHA-FR-02's hub is bored to slide
  on the tube itself (fr_top_frame_spec.GOOSENECK_BORE_DIA).
* MHA-SM-05 ``sm-gooseneck-end-plug``: a solid Ø.500 head flush with the tube,
  PLUG_HEAD_LENGTH from the end face ARM_END_X to the tube end, then a spigot
  PLUG_SHANK_LENGTH into the tube bore, turned to the measured bore at the
  joint's clearance (sm_gooseneck_spring_joint) and tapped #10-24 for the
  MHA-SM-VN-56 shoulder screw before bonding.

The spring eye's centre and the end face it rests on are unchanged.

Stock limits: OnlineMetals alloy-steel tolerances (read 2026-10-27,
https://www.onlinemetals.com/en/alloy-steel-tolerances): 4130-N cold drawn
seamless round tube, OD 0.500-1.699 in +0.007/-0.002 in; wall 10-25 % of OD
with ID under 0.500 in +/-10 %, wall under 10 % of OD with ID 0.500 in and
over +/-7.5 %.

#290: the sheets print decimal inch.  The spring eye's station (ARM_END_X) is
calibrated spring-support geometry (the native counter-seat certificate,
settled_spring_seats, records it), so it keeps its millimetre value; the
plug's head and spigot are .XX inch lengths, and the leg is cut to its
printed .X length.
"""

from __future__ import annotations

from sm_vn_counter_spring_stock_geom import END_OCCUPIED_WIDTH_MM

MM_PER_IN = 25.4
# The gooseneck parts' sheet unit, their registry rows' drawing_unit (each
# part spec checks its row agrees): a literal here because
# sm_gooseneck_spring_joint, which charges the plug sheet's printed bands,
# reads no registry row (codjiflo P3 on #1997).
SHEET_UNIT = "in"
# The tube, OnlineMetals 7322: 4130-N seamless 1/2 in OD x 0.065 in wall.
TUBE_DIA = 0.500 * MM_PER_IN
WALL_T = 0.065 * MM_PER_IN
TUBE_BORE_DIA = TUBE_DIA - 2.0 * WALL_T
TUBE_DIA_MIN = (0.500 - 0.002) * MM_PER_IN
TUBE_DIA_MAX = (0.500 + 0.007) * MM_PER_IN
WALL_T_MIN = 0.065 * 0.90 * MM_PER_IN
WALL_T_MAX = 0.065 * 1.10 * MM_PER_IN
TUBE_BORE_DIA_MIN = TUBE_DIA_MIN - 2.0 * WALL_T_MAX
TUBE_BORE_DIA_MAX = TUBE_DIA_MAX - 2.0 * WALL_T_MIN
ARM_Y = 163.3  # arm/screw axis above the part origin
BEND_R = 3.0 * MM_PER_IN  # 90-degree bend centreline radius: the 1/2 in x 3 in CLR die
SPRING_EYE_X = -105.8
SPRING_EYE_GAP = END_OCCUPIED_WIDTH_MM
# The end face: MHA-SM-05's outer face, where the shoulder screw seats.
ARM_END_X = SPRING_EYE_X + SPRING_EYE_GAP / 2.0
# The bend's exit tangent to the end face.
ARM_STRAIGHT = -ARM_END_X - BEND_R
# MHA-SM-05: a solid head turned to the tube's Ø, flush with it, from the end
# face to the tube end, and a spigot turned to the measured tube bore, bonded
# PLUG_SHANK_LENGTH deep (owner pick 2026-11-08 (Pedro), #2315 option 2: head
# .60, spigot .42).  The head holds the whole tapped hole
# (sm_gooseneck_spring_joint); the spigot sits in the straight tube.
PLUG_DIA = TUBE_DIA
PLUG_HEAD_LENGTH = 0.60 * MM_PER_IN
PLUG_SHANK_LENGTH = 0.42 * MM_PER_IN
PLUG_LENGTH = PLUG_HEAD_LENGTH + PLUG_SHANK_LENGTH
# MHA-SM-01's arm end, sawn and faced after the bend.
TUBE_END_X = ARM_END_X + PLUG_HEAD_LENGTH
# MHA-SM-01's straight arm from the bend's exit tangent to its faced end.
TUBE_STRAIGHT = -TUBE_END_X - BEND_R
if TUBE_STRAIGHT < PLUG_SHANK_LENGTH + 1.0:
    raise AssertionError("gooseneck end plug's spigot reaches the bend")
# The leg: from its foot up to the bend's entry tangent, 16.4 in long (the
# sheet's .X leg length).
LEG_TOP = round(ARM_Y - BEND_R, 3)
LEG_LENGTH = 16.4 * MM_PER_IN
LEG_BOTTOM = round(LEG_TOP - LEG_LENGTH, 3)
