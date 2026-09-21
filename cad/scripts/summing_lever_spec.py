r"""Summing-lever dimensional contract -- the single source of truth shared by
the part build (``build_summing_lever.py``) and its manufacturing drawing
(``draw_summing_lever.py``).

PURE DATA, no SolidWorks/COM imports (``stock_anchor_geom`` is pure geometry).
A large green-iron casting: a coefficients plate carrying the 20 channel-spring
anchor taps on the +X arm, a solid pivot cylinder with hex knife-edge
trunnions, and a curved summation arm ending in the tapped counter-spring
anchor boss on the -X arm.  Both anchors are purchased eyebolts that thread
straight into those taps -- the lever IS their nut -- so this module owns the
two thread identities and the boss height, and no plain anchor bore exists.
Values MUST match build_summing_lever.py.
"""

from __future__ import annotations

import math
from _hole_spec import HoleSpec
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1


from _gtol_spec import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

MM_PER_IN = 25.4

# --- Nominal geometry (SummingLever.cs, inches -> mm; DIMENSIONS.md ch. 18). ---
PLATE_W = 1.75 * MM_PER_IN  # 44.45 coefficients-plate width (X)
PLATE_L = 6.0 * MM_PER_IN  # 152.40 plate / pivot length (Z)
PLATE_T = 0.2 * MM_PER_IN  # 5.08 plate thickness
CYL_R = 0.5 * MM_PER_IN  # 12.70 pivot-cylinder radius
SUM_H = 3.0 * MM_PER_IN  # 76.20 summation reach (-X)
ANCHOR_R = 0.375 * MM_PER_IN  # 9.525 summation-anchor outer radius
ANCHOR_H = 0.75 * MM_PER_IN  # 19.05 summation-anchor boss height (Y)

# hex knife-edge trunnion (vertex-up).
HEX_W = 8.653
HEX_H = 10.268
HEX_DEPTH = 21.717

# Outward normal and plane offset of the upper-right sloping face of the
# vertex-up hexagon. Its upper endpoint is the +Y knife-edge ridge.
_KNIFE_FACE_SCALE = math.hypot(HEX_H / 4.0, HEX_W / 2.0)
KNIFE_FACE_NORMAL = (
    (HEX_H / 4.0) / _KNIFE_FACE_SCALE,
    (HEX_W / 2.0) / _KNIFE_FACE_SCALE,
    0.0,
)
KNIFE_FACE_OFFSET = KNIFE_FACE_NORMAL[1] * HEX_H / 2.0

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "knife_edge_ridge",
        MACHINED_UM,
        PlanarFace(
            KNIFE_FACE_NORMAL,
            KNIFE_FACE_OFFSET,
            contains_z_mm=(PLATE_L + HEX_DEPTH) / 2.0,
        ),
    ),
)

# The 20 channel-spring lower anchors (McMaster 9489T111, part ``spring-hook``)
# thread DIRECTLY into the coefficient plate -- the plate is their nut, the
# supplied one is discarded -- so each station is a through tap, not a bore:
# one native seed + a linear pattern. The size is the anchor's own thread, so a
# supplier change can never leave the lever tapped for the wrong screw.
HOLE_SPEC = HoleSpec("tapped", ANCHOR_9489T111.thread_size)
HOLE_X = 39.85
HOLE_COUNT = 20
CHANNEL_Z0 = -67.1
CHANNEL_PITCH = 7.0565
HOLE_Z_OFFSET = 0.8

# The counter-spring lower anchor (McMaster 9490T1, part ``boss-hook``) threads
# DIRECTLY through the summation-anchor boss on the same no-nut rule, authored
# natively AFTER the structural ribs so none of them can refill it.
COUNTER_HOLE_SPEC = HoleSpec("tapped", ANCHOR_9490T1.thread_size)

# --- Derived. ---
CYL_DIA = 2.0 * CYL_R  # 25.4
TIP_X = -SUM_H  # -76.20 summation tip / anchor X
HOLE_Z_FIRST = CHANNEL_Z0 + HOLE_Z_OFFSET  # -66.3
HOLE_Z_LAST = CHANNEL_Z0 + CHANNEL_PITCH * (HOLE_COUNT - 1) + HOLE_Z_OFFSET  # 67.77
HOLE_EDGE_OFFSET = PLATE_W - HOLE_X  # 4.60 from the free +X plate edge
HOLE_END_OFFSET_FIRST = HOLE_Z_FIRST + PLATE_L / 2.0  # 9.90 from -Z end
HOLE_END_OFFSET_LAST = PLATE_L / 2.0 - HOLE_Z_LAST  # 8.43 from +Z end
HEX_Z_INNER = PLATE_L / 2.0  # trunnion inboard face flush with the body end (76.20)
HEX_Z_OUTER = HEX_Z_INNER + HEX_DEPTH  # outboard face overhangs the body (97.92)

# Manufacturing-dimension and precision contracts live with the geometry: the
# part build authors them on the SLDPRT and the drawing only imports and
# verifies them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateLength"},
    "CoefficientsPlate": {"PlateThickness"},
    "CylinderProfile": {"CylDia"},
    "HexKnifeFront": {"HexKnifeFrontDepth"},
    "KnifeEnvelopeReference": {"HexWidth", "HexHeight"},
    "SummationAnchorProfile": {"AnchorOuterX", "AnchorOuterDia"},
    "SummationAnchor": {"AnchorHeight"},
    "SpringHoleSeed": {"HoleSeedX"},
    "SpringHolePattern": {"HolePitch"},
    "PatternReferences": {"HoleStartOffset"},
}

# Decimal places carry the title-block tolerance and therefore live on the
# model.  The spring-pattern coordinates are BASIC on the sheet, but their
# display precision is still authored here rather than rewritten at render
# time.  The knife envelope and first-hole offset are construction-sketch
# dimensions tied to the same globals that drive the solid.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {"PlateWidth": 2, "PlateLength": 1},
    "CoefficientsPlate": {"PlateThickness": 2},
    "CylinderProfile": {"CylDia": 1},
    "HexKnifeFront": {"HexKnifeFrontDepth": 2},
    "KnifeEnvelopeReference": {"HexWidth": 2, "HexHeight": 2},
    "SummationAnchorProfile": {"AnchorOuterX": 1, "AnchorOuterDia": 2},
    "SummationAnchor": {"AnchorHeight": 2},
    "SpringHoleSeed": {"HoleSeedX": 2},
    "SpringHolePattern": {"HolePitch": 2},
    "PatternReferences": {"HoleStartOffset": 2},
}

_PRECISION_NAMES = [
    (feature, name)
    for feature, dimensions in DRAWING_PRECISION.items()
    for name in dimensions
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# The three coordinates that feed the one surviving position frame are BASIC
# on the source model.  The drawing verifies this state; it never changes a
# tolerance after import.
BASIC_DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SpringHoleSeed": {"HoleSeedX"},
    "SpringHolePattern": {"HolePitch"},
    "PatternReferences": {"HoleStartOffset"},
}
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, names in BASIC_DRAWING_DIMENSIONS.items()
    for name in names
):
    raise AssertionError("BASIC_DRAWING_DIMENSIONS names an unmarked dimension")

# Rule 3 permits one position frame for the 20-hole spring pattern.  The knife
# ridge retains its part-owned finish and is datum A for that pattern; the
# counter-spring boss is located by ordinary model dimensions, not another
# frame.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "spring-hole pattern position": "0.30",
}
