r"""Magnifying-wheel dimensional contract -- the single source of truth shared by
the part build (``build_magnifying_wheel.py``) and its manufacturing drawing
(``draw_magnifying_wheel.py``).

PURE DATA, no SolidWorks/COM imports.  The wheel nominals live in the drawing-
FREE ``magnifying_wheel_geom`` module (the assembly imports the hub + spoke
axial); they are re-exported here for the drawing-side consumers and the offline
lockstep test, which asserts the part marks and the drawing keeps EXACTLY
``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from _fit_limits import REAM_H7
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from magnifying_wheel_geom import (  # noqa: F401 (re-export)
    BORE_DIA,
    HUB_AXIAL,
    HUB_DIA,
    RIM_AXIAL,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
    SPOKE_AXIAL,
    SPOKE_COUNT,
    SPOKE_WIDTH,
)

# The axle bore is the one surface that runs in service: the wheel turns on its
# axle stud (magnifier assembly, "magnifying-wheel pivot").  The hub drum only
# carries the wrapped lever wire, so it stays at the block Ra
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES = (
    SurfaceFinishControl("axle_bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

# The reamed axle bore's band, ON the model dimension (policy rule 2): an H7
# hole over the wheel-axle stud's h band (wheel_axle_spec.STUD_DIA_BAND
# -0.02/-0.05) keeps a 0.02-0.06 running clearance.  (upper, lower).
BORE_DIA_BAND = REAM_H7

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows (all Front-plane circle/spoke dims, so they auto-import to the face
# view).  The rim ID is controlling (the 6 wall is derived); the rim + hub axial
# widths, the spoke thickness and the axial stations are dimensioned on the
# sheet in SECTION A-A. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RimProfile": {"RimOuterDiaDim", "RimInnerDiaDim"},
    "HubProfile": {"HubDiaDim"},
    "SpokeProfile": {"SpokeWidthDim"},
    "BoreProfile": {"BoreDiaDim"},
}

# Notes: the one process fact no view carries -- which faces of the casting are
# machined (policy rule 6).  Every size and station is on a view.
DRAWING_NOTES = "CASTING. MACHINE THE RIM OD, BOTH RIM FACES AND THE HUB DRUM."
# The side elevation is SECTION A-A (its native label); the isometric caption
# carries no scale because it is the sheet scale (title block).
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW"
