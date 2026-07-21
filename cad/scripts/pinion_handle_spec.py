r"""Pure-data dimensional contract shared by the pinion turning handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned tee: a fat grip cylinder with a
domed cap, a cross rod through the grip, and a blind tubular hub that seats over
the pinion arbor stub.  The nominals drive the part's named equation globals AND
the drawing's coordinate math; the marked-dimension map keeps the part marks and
drawing keeps in lockstep (``test_pinion_handle_drawing.py``).
"""

from __future__ import annotations

from pinion_handle_geometry import (
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    GRIP_DIA as GRIP_DIA,
    GRIP_LEN as GRIP_LEN,
    ROD_DIA as ROD_DIA,
    ROD_DOWN as ROD_DOWN,
    ROD_SPAN as ROD_SPAN,
    ROD_UP as ROD_UP,
    TUBE_ID as TUBE_ID,
    TUBE_LEN as TUBE_LEN,
    TUBE_OD as TUBE_OD,
    WALL_T as WALL_T,
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GripProfile": {"GripDia"},
    "Grip": {"GripLen"},
    "TubeProfile": {"TubeOd", "TubeId"},
    "Tube": {"TubeLen"},
    "RodProfile": {"RodDia"},
    "Rod": {"RodSpan"},
}

DRAWING_NOTES = "\n".join(
    (
        "TURN THE GRIP, WALL AND HUB IN ONE SETUP ON THE ARBOR AXIS.",
        "GRIP OD AND HUB OD TIR 0.05 TO THE FINAL REAMED BORE AXIS.",
        f"OPPOSITE GRIP FACE: SPHERICAL CROWN SR{CAP_RADIUS:.2f}+/-0.10;",
        "  2.00+/-0.10 AXIAL HEIGHT FROM THE CROWN ROOT PLANE.",
        "FINAL PART CONSISTS OF THE TURNED BODY AND PRESSED CROSS ROD.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
