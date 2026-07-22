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
        "DATUM A IS FINISHED BORE AXIS;",
        "  DATUM B IS FLAT END FACE.",
        "BORE AND FINISH TO LIMITS IN THE",
        "  HUB-TURNING SETUP. BLIND BORE BOTTOM",
        "  MAY HAVE R0.15 MAX CORNER RADIUS.",
        f"CROWN BREAK AT THE CROWN ROOT PLANE ({HUB_LEN:.2f} REF)",
        "  SHALL BE R0.10 MAX AND IS EXEMPT FROM THE",
        "  TITLE-BLOCK EDGE-BREAK REQUIREMENT.",
        f"GRIP AXIS: {HUB_LEN / 2.0:.2f}+/-0.10 FROM B, MEASURED AT THE",
        "  POINT OF THE GRIP AXIS NEAREST A; 90+/-0.5 DEG TO A.",
        "SHORTEST DISTANCE BETWEEN GRIP AXIS AND A:",
        "  0.00 TO 0.10. GRIP-TO-HUB JUNCTION R0.25 MAX.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
