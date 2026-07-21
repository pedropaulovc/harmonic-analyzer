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
    "RodProfile": {"RodRootR", "RodTipR", "RodTipY"},
}

DRAWING_NOTES = "\n".join(
    (
        "DATUM A IS FINAL REAMED BORE AXIS; DATUM B IS FLAT END FACE.",
        "TURN HUB AND REAM BORE IN ONE SETUP. CYLINDRICAL HUB LENGTH IS",
        "  THE BORE-DEPTH + END-WALL DIMENSION STACK FROM DATUM B.",
        f"OPPOSITE B: SPHERICAL CROWN SR{CAP_RADIUS:.2f}+/-0.10; 1.50 REF HIGH.",
        "GRIP AXIS BASICALLY INTERSECTS A AT HUB MID-PLANE, 5.00 FROM B;",
        "  POSITION IS CONTROLLED BY THE ATTACHED <MOD-DIAM>0.05 | A | B FRAME.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
