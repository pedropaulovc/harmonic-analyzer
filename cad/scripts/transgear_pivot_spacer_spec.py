r"""Transgear pivot spacer (MHA-167) dimensional contract.

PURE DATA, no SolidWorks/COM imports.  A turned brass ring on the MHA-168
shoulder screw between the MHA-074 support bar's back face and the MHA-164
arm's front face (contract §3.4).  Its length sets the pivot head play with
the arm's spot-face floor and the screw's shoulder, so it prints ±0.05; it
is fitted as made, never faced (R9-6).

Local frame: lathe axis +Z, origin on the axis at the face that bears on the
bar (the FRONT face, machine z -129.9); the rear face (on the arm) at
z = LENGTH.  Front Plane (z = 0) and the RearFace plane (z = LENGTH) are the
mating planes, Axis1 the bore axis.
"""

from __future__ import annotations

import math

from _gtol_spec import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

OD = 8.6
OD_BAND = 0.13  # ±0.13: 0.07 worst to the lock stations
BORE_DIA = 4.9  # .XXX, runs on the Ø4.7625 shoulder
BORE_DIA_BAND = 0.13
# The bore runs on the MHA-168 shoulder, as the arm's does: a fit bore, so it
# is reamed (policy rule 7: the callout states the process).  A standard hole,
# it is fully defined by its callout on the end view, where it is a circle.
BORE_CALLOUT = "REAM THRU"
LENGTH = 5.5
LENGTH_BAND = 0.05  # pivot head play 0.10..0.35 with the floor and shoulder

WALL_NOMINAL = (OD - BORE_DIA) / 2.0
WALL_WORST = (OD - OD_BAND - BORE_DIA - BORE_DIA_BAND) / 2.0
# A MIN never rounds up: floored to two places.
WALL_WORST_PRINTED = math.floor(WALL_WORST * 100.0 + 1e-9) / 100.0
if not 1.5 <= WALL_WORST_PRINTED < 2.0:
    raise AssertionError(
        f"MHA-167 wall {WALL_WORST:.3f} left the approved 1.5..2.0 shortfall"
    )

# Sheet text (policy rule 6).
# Named exception: MHA-167 wall (drawing-simplicity-policy.md, "Named exceptions").
WALL_NOTE = f"WALL {WALL_WORST_PRINTED:.2f} MIN."

# The sheet's general notes: the worst-case wall, a fact the views cannot
# carry.  The length band is not here: it rides the length dimension as a
# model tolerance (policy rule 2).
DRAWING_NOTES = WALL_NOTE

# Marked model dimensions and the places the part authors on them (policy
# rule 2): every size prints at .XXX.  The title block's .XXX row governs the
# O.D. and the bore (OD_BAND and BORE_DIA_BAND restate it for the wall above
# only); the length carries LENGTH_BAND on the model dimension.
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
    raise AssertionError("every marked MHA-167 dimension needs authored places")

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
