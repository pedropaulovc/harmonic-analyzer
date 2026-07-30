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

SURFACE_FINISHES = (
    SurfaceFinishControl("hub_drum", MACHINED_UM, CylinderFace(HUB_DIA)),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows (all Front-plane circle/spoke dims, so they auto-import to the face
# view).  The three axial widths (rim 8 / hub 10 / spoke 4) are added on the
# sheet across the right-view section; the 6-spoke count is a note. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RimProfile": {"RimOuterDiaDim"},
    "HubProfile": {"HubDiaDim"},
    "SpokeProfile": {"SpokeWidthDim"},
    "BoreProfile": {"BoreDiaDim"},
}

DRAWING_NOTES = "\n".join(
    (
        "6 STRAIGHT SPOKES, EQUALLY SPACED (60 DEG); SPOKE SECTION 5 WIDE x 4 THICK.",
        f"RIM RING Ø{RIM_OUTER_DIA:.0f} OD / Ø{RIM_INNER_DIA:.0f} ID "
        f"({(RIM_OUTER_DIA - RIM_INNER_DIA) / 2:.0f} WALL) x {RIM_AXIAL:.0f} WIDE; "
        f"SPOKE {SPOKE_AXIAL:.0f} THICK CENTRED IN THE RIM.",
        "RIM Ø100 / HUB Ø20 GIVE THE 5X WHEEL RATIO: THE LEVER WIRE WRAPS THE",
        "HUB, THE PEN WIRE LEAVES THE RIM.",
        "Ø5 AXLE BORE THRU, REAMED; RUNNING FIT ON THE AXLE STUD.",
        "THE REFERENCE REQUIRES A GROOVED BRASS HUB DRUM AND AN OUTER WIRE",
        "GROOVE; THE CURRENT ONE-PIECE SOURCE MODEL DEFINES NEITHER. DO NOT",
        "RELEASE UNTIL HUB MATERIAL, GROOVES, AND RETENTION ARE SPECIFIED.",
    )
)
# The right view is a plain side elevation (hidden lines), NOT a cutting-plane
# section -- labelled honestly so the sheet does not promise section geometry it
# does not carry (a true rim/spoke/hub section is a deferred enrichment).
SECTION_VIEW_NOTE = "SIDE VIEW SCALE 1:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
