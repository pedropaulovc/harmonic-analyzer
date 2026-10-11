r"""Transgear pivot spacer (MHA-PD-020) dimensional contract.

PURE DATA, no SolidWorks/COM imports.  A turned brass ring on the MHA-VN-041
shoulder screw between the MHA-PD-007 support bar's back face and the MHA-PD-018
arm's front face (contract §3.4).  Its length sets the MHA-VN-049 spring's
room with the arm's spot-face floor and the screw's shoulder, so it prints
±0.05; it is fitted as made, never faced (R9-6).  It is a light press on
the shoulder, pressed flush with the shoulder's end, so screw and spacer
seat on the bar as one body and the ring cannot index its wedge; the
screw's one MHA-VN-049 curved disc spring preloads the arm onto the rear
face.  The hanger's out-of-plane tilt is then both faces' perpendicularity
to the bore (datum A) over the face the arm seats on: the sheet carries
those two frames.

Local frame: lathe axis +Z, origin on the axis at the face that bears on the
bar (the FRONT face, machine z -129.9); the rear face (on the arm) at
z = LENGTH.  Front Plane (z = 0) and the RearFace plane (z = LENGTH) are the
mating planes, Axis1 the bore axis.
"""

from __future__ import annotations

import math

import vn_transgear_pivot_screw_spec as SCREW
from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

OD = 8.6
OD_BAND = 0.13  # ±0.13: 0.142 worst to the lock stations, floating (R9-61)
# The bore is a light press on the Ø4.7625 -0.0254/0 shoulder, so it is a
# reamed fit bore (policy rule 7: the callout states the process) under an
# explicit band on the model dimension.  A standard hole, it is fully
# defined by its callout on the end view, where it is a circle.
BORE_DIA = 4.727
BORE_DIA_BAND = (0.008, 0.0)  # (upper, lower) deviations, reamed
BORE_DIA_MAX = round(BORE_DIA + BORE_DIA_BAND[0], 6)
BORE_DIA_MIN = round(BORE_DIA + BORE_DIA_BAND[1], 6)
BORE_CALLOUT = "REAM THRU"
LENGTH = 5.5
LENGTH_BAND = 0.05  # spring room 0.70..0.95 with the floor and shoulder
# (loosest, tightest): the smallest shoulder in the largest ream, and the
# reverse.
_SHOULDER_DIA_MIN = SCREW.SHOULDER_DIA + SCREW.SHOULDER_DIA_LIMITS[0]
_SHOULDER_DIA_MAX = SCREW.SHOULDER_DIA + SCREW.SHOULDER_DIA_LIMITS[1]
PRESS_INTERFERENCE = (
    round(_SHOULDER_DIA_MIN - BORE_DIA_MAX, 6),
    round(_SHOULDER_DIA_MAX - BORE_DIA_MIN, 6),
)  # 0.0021, 0.0355
if not 0.0 < PRESS_INTERFERENCE[0] <= PRESS_INTERFERENCE[1]:
    raise AssertionError(
        f"MHA-PD-020 bore leaves the shoulder press: {PRESS_INTERFERENCE}"
    )

WALL_NOMINAL = (OD - BORE_DIA) / 2.0
WALL_WORST = (OD - OD_BAND - BORE_DIA_MAX) / 2.0
# A MIN never rounds up: floored to two places.
WALL_WORST_PRINTED = math.floor(WALL_WORST * 100.0 + 1e-9) / 100.0
if not 1.5 <= WALL_WORST_PRINTED < 2.0:
    raise AssertionError(
        f"MHA-PD-020 wall {WALL_WORST:.3f} left the approved 1.5..2.0 shortfall"
    )

# --- geometric control --------------------------------------------------------
# Pressed on the shoulder, the ring's bore is the screw's axis (datum A).  The
# front face seats on the bar and the arm seats on the rear face, so the arm
# tilts off the axis by the sum of both faces' perpendicularity to A over the
# smallest face the arm seats on (the O.D. at its lower limit); the
# assembly's hanger-tilt stack reads all three.
BORE_DATUM = "A"
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "rear face perpendicularity to bore": "0.01",
    "front face perpendicularity to bore": "0.01",
}
REAR_FACE_PERPENDICULARITY = float(
    GEOMETRIC_TOLERANCES_MM["rear face perpendicularity to bore"]
)
FRONT_FACE_PERPENDICULARITY = float(
    GEOMETRIC_TOLERANCES_MM["front face perpendicularity to bore"]
)
FACE_PERPENDICULARITY_ZONE_DIA = OD - OD_BAND

# Sheet text (policy rule 6).
# Named exception: MHA-PD-020 wall (drawing-simplicity-policy.md, "Named exceptions").
WALL_NOTE = f"WALL {WALL_WORST_PRINTED:.2f} MIN."

# The sheet's general notes: the worst-case wall, a fact the views cannot
# carry.  The length and bore bands are not here: they ride their dimensions
# as model tolerances (policy rule 2).
DRAWING_NOTES = WALL_NOTE

# Marked model dimensions and the places the part authors on them (policy
# rule 2): every size prints at .XXX.  The title block's .XXX row governs the
# O.D. (OD_BAND restates it for the wall above only); the length carries
# LENGTH_BAND and the bore BORE_DIA_BAND on their model dimensions.
_XXX = 3
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"RingOd", "BoreDia"},
    "Ring": {"RingLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"RingOd": _XXX, "BoreDia": _XXX},
    "Ring": {"RingLength": _XXX},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-PD-020 dimension needs authored places")

ISOMETRIC_VIEW_SCALE = (4, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)

# Both end faces are MACHINED (policy rule 5): the arm runs on the rear face
# and the front face bears on the bar.  Resolved on the exact native faces by
# outward normal and offset in the part frame.  The bore carries no symbol.
SURFACE_FINISHES = (
    SurfaceFinishControl("front_face", MACHINED_UM, PlanarFace((0.0, 0.0, -1.0), 0.0)),
    SurfaceFinishControl("rear_face", MACHINED_UM, PlanarFace((0.0, 0.0, 1.0), LENGTH)),
)
