r"""Pure-data dimensional contract shared by the pinion strap torque shaft and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A plain Ø6.35 turned steel shaft with a
shallow spherical crown at each end -- the pivot the two swing straps rock on.
The nominals drive the part's named equation globals AND the drawing's
coordinate math; the marked-dimension map keeps the part marks and the drawing
keeps in lockstep (``test_pinion_pivot_shaft_drawing.py``).
"""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

SHAFT_DIA = 6.35  # 1/4 in: rides both pivot blocks' east bores and the straps
SHAFT_LEN = 192.0  # ends flush with the pivot blocks' outer faces
CAP_SAG = 1.2  # shallow spherical crown height at each end
CAP_RADIUS = ((SHAFT_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
OVERALL_LEN = SHAFT_LEN + 2.0 * CAP_SAG  # 194.4 crown apex to crown apex
SHAFT_DIA_BAND = SHAFT_H
SHAFT_LENGTH_TOLERANCE_MM = 0.25

SURFACE_FINISHES = (
    SurfaceFinishControl("bearing", MACHINED_UM, CylinderFace(SHAFT_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

# The crowns, as the leadered note on one crown spells them (their sketch
# dims live on the Top plane, outside every placed view, so the crown is
# conveyed by a note ATTACHED to a crowned end rather than buried in the
# block -- machinist review 2026-09-02). The height is a REF (the 192.00
# between root circles plus two crowns is the overall); the root circle stays
# sharp so the crown seats flush in the strap bore.
CROWN_NOTE = "\n".join(
    (
        f"2X SPHERICAL CROWN SR{CAP_RADIUS:.2f}",
        f"({CAP_SAG:.2f}) HIGH; ROOT CIRCLE SHARP, NO CHAMFER",
    )
)

# Notes: process facts only, never a tolerance
# (drawing-simplicity-policy.md rule 6).  The body diameter's band rides the
# model dimension; the crowns are called out from the view.
DRAWING_NOTES = "GROUND 1/4 IN SHAFTING OK AS RECEIVED."
END_VIEW_NOTE = "END VIEW SCALE 4:1"
# The isometric renders at ISO_SCALE (1, 2) while the sheet/title block reads
# 1:1, so without this the pictorial is silently half scale.  Mirrors
# fulcrum-shaft / cylinder-gear-shaft, whose identical 1:2 iso carry the note.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
