r"""Summing-lever dimensional contract -- the single source of truth shared by
the part build (``build_summing_lever.py``) and its manufacturing drawing
(``draw_summing_lever.py``).

PURE DATA, no SolidWorks/COM imports.  A large green-iron casting: a
coefficients plate carrying the 20 channel-spring holes on the +X arm, a solid
pivot cylinder with hex knife-edge trunnions, and a curved summation arm ending
in the counter-spring anchor eye on the -X arm.  Values MUST match
build_summing_lever.py.
"""

from __future__ import annotations

MM_PER_IN = 25.4

# --- Nominal geometry (SummingLever.cs, inches -> mm; DIMENSIONS.md ch. 18). ---
PLATE_W = 1.75 * MM_PER_IN  # 44.45 coefficients-plate width (X)
PLATE_L = 6.0 * MM_PER_IN  # 152.40 plate / pivot length (Z)
PLATE_T = 0.2 * MM_PER_IN  # 5.08 plate thickness
CYL_R = 0.5 * MM_PER_IN  # 12.70 pivot-cylinder radius
SUM_H = 3.0 * MM_PER_IN  # 76.20 summation reach (-X)
ANCHOR_R = 0.375 * MM_PER_IN  # 9.525 summation-anchor outer radius
ANCHOR_BORE_R = 1.5  # 3.0 dia counter-spring hook seat

# hex knife-edge trunnion (vertex-up).
HEX_W = 8.653
HEX_H = 10.268
HEX_DEPTH = 21.717

# 20 channel-spring holes (#47 seed + linear pattern).
HOLE_X = 39.85
HOLE_COUNT = 20
CHANNEL_Z0 = -67.1
CHANNEL_PITCH = 7.0565
HOLE_Z_OFFSET = 0.8

# --- Derived. ---
CYL_DIA = 2.0 * CYL_R  # 25.4
TIP_X = -SUM_H  # -76.20 summation tip / anchor X
HOLE_Z_FIRST = CHANNEL_Z0 + HOLE_Z_OFFSET  # -66.3
HOLE_Z_LAST = CHANNEL_Z0 + CHANNEL_PITCH * (HOLE_COUNT - 1) + HOLE_Z_OFFSET  # 67.77
HOLE_EDGE_OFFSET = PLATE_W - HOLE_X  # 4.60 from the free +X plate edge
HOLE_END_OFFSET_FIRST = HOLE_Z_FIRST + PLATE_L / 2.0  # 9.90 from -Z end
HOLE_END_OFFSET_LAST = PLATE_L / 2.0 - HOLE_Z_LAST  # 8.43 from +Z end


# --- Marked-dimension contract.  build_summing_lever marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateLength"},
    "CylinderProfile": {"CylDia"},
    "SummationAnchorProfile": {"AnchorOuterDia"},
}

DRAWING_NOTES = "\n".join(
    (
        f"1. HEX TRUNNIONS {HEX_W:.2f} W x {HEX_H:.2f} HIGH,",
        f"   {HEX_DEPTH:.2f} LONG EACH END; VERTEX UP IS",
        "   THE KNIFE EDGE.",
        f"2. COEFFICIENT PLATE {PLATE_T:.2f} THICK; {HOLE_COUNT} X",
        f"   #47 HOLES AT {CHANNEL_PITCH:.4f} PITCH.",
        f"3. HOLE ROW {HOLE_EDGE_OFFSET:.2f} FROM FREE PLATE EDGE;",
        f"   END OFFSETS {HOLE_END_OFFSET_FIRST:.2f} AND {HOLE_END_OFFSET_LAST:.2f}.",
        f"4. SUMMATION EYE {2.0 * ANCHOR_R:.2f} THICK,",
        f"   {2.0 * ANCHOR_BORE_R:.1f} BORE, {SUM_H:.2f} FROM PIVOT AXIS.",
        f"5. PIVOT CYLINDER {PLATE_L:.2f} LONG; NO BORE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
