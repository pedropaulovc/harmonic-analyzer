r"""Pure-data dimensional contract shared by the pinion cam-follower pin and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A short bright-steel stud pressed into the
swing strap's west edge, riding on the eccentric cam collar.  The nominals drive
the part's named equation globals AND the drawing's coordinate math; the
marked-dimension map keeps the part marks and drawing keeps in lockstep
(``test_pinion_cam_pin_drawing.py``).
"""

from __future__ import annotations

from pinion_cam_pin_geometry import (
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    PIN_DIA as PIN_DIA,
    PIN_LEN as PIN_LEN,
    SEAT_LEN as SEAT_LEN,
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia"},
    "Pin": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "SEATED END IS FLAT; OPPOSITE END HAS ONE SPHERICAL CROWN.",
        "CROWN ROOT CIRCLE IS A SHARP PROFILE BREAK, R0.10 MAX; NO CHAMFER;",
        "  EXEMPT FROM TITLE-BLOCK EDGE-BREAK REQUIREMENT.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 8:1"
