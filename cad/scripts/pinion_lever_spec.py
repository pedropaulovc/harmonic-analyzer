r"""Pure-data dimensional contract shared by the pinion engage lever and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A hub seated over the lift rod, with a
tapered grip rod rising out of it -- turned steel.  The nominals drive the part's
named equation globals AND the drawing's coordinate math; the marked-dimension
map keeps the part marks and drawing keeps in lockstep
(``test_pinion_lever_drawing.py``).
"""

from __future__ import annotations

from pinion_lever_geometry import (
    BORE as BORE,
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    HUB_LEN as HUB_LEN,
    HUB_OD as HUB_OD,
    ROD_LEN as ROD_LEN,
    ROD_ROOT_DIA as ROD_ROOT_DIA,
    ROD_TIP_DIA as ROD_TIP_DIA,
    ROD_Y0 as ROD_Y0,
    WALL_T as WALL_T,
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarrelProfile": {"HubOd", "HubBore"},
    "Barrel": {"BoreDepth"},
    "Wall": {"EndWall"},
    "RodProfile": {"RodTipY"},
}

DRAWING_NOTES = "\n".join(
    (
        "DATUM A IS FINISHED BORE AXIS; DATUM B IS FLAT END FACE.",
        "BORE AND FINISH TO LIMITS IN THE HUB-TURNING SETUP.",
        "BLIND BORE BOTTOM MAY HAVE R0.15 MAX CORNER RADIUS.",
        f"CROWN PROFILE BREAK AT THE {HUB_LEN:.2f} CYLINDRICAL-HUB PLANE SHALL BE SHARP.",
        f"GRIP AXIS: BASIC {HUB_LEN / 2.0:.2f} FROM B; BASIC 90 DEG TO A; INTERSECTS A.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
