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
    "RodProfile": {"RodRootR", "RodTipR", "RodTipY"},
}

DRAWING_NOTES = "\n".join(
    (
        "TURN THE HUB AND REAM ITS BLIND BORE IN ONE SETUP.",
        "HUB CYLINDRICAL LENGTH 10.00+/-0.10 FROM FLAT FACE TO CROWN ROOT PLANE.",
        f"OPPOSITE FLAT FACE: SPHERICAL CROWN SR{CAP_RADIUS:.2f}+/-0.10;",
        "  1.50+/-0.05 AXIAL HEIGHT FROM THE CROWN ROOT PLANE.",
        "FLAT FACE PERPENDICULAR 0.05 TO FINAL REAMED BORE AXIS.",
        "INTEGRAL GRIP AXIS INTERSECTS BORE AXIS WITHIN 0.05 AND LIES",
        "  WITHIN 0.05 OF THE HUB MID-PLANE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
