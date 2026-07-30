r"""Pure-data dimensional contract shared by the pinion cam-follower pin and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A short bright-steel stud pressed into the
swing strap's west edge, riding on the eccentric cam collar.  The nominals drive
the part's named equation globals AND the drawing's coordinate math; the
marked-dimension map keeps the part marks and drawing keeps in lockstep
(``test_pinion_cam_pin_drawing.py``).
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import GROUND_UM, SurfaceFinishControl
from pinion_cam_pin_geometry import (
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    PIN_DIA as PIN_DIA,
    PIN_LEN as PIN_LEN,
    SEAT_LEN as SEAT_LEN,
)

# Symmetric final-size band about the PIN_DIA mid nominal (4.020 MAX /
# 4.012 MIN press band); the drawing callout derives its limits from these
# two constants so a retuned press fit can never ship stale limit text.
PIN_DIA_TOL = 0.004
PIN_DIA_BAND = (PIN_DIA_TOL, -PIN_DIA_TOL)
PIN_LENGTH_TOLERANCE_MM = 0.05
CAP_RADIUS_TOLERANCE_MM = 0.05

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia"},
    "Pin": {"Depth"},
    "CapProfile": {"CapR"},
}

SURFACE_FINISHES = (
    SurfaceFinishControl(
        key="finished_shank",
        roughness_um=GROUND_UM,
        face=CylinderFace(diameter_mm=PIN_DIA),
    ),
)

DRAWING_NOTES = "\n".join(
    (
        "SEATED END IS FLAT; OPPOSITE END HAS ONE SPHERICAL CROWN.",
        "CROWN ROOT CIRCLE IS A SHARP PROFILE BREAK, R0.10 MAX; NO CHAMFER;",
        "  EXEMPT FROM TITLE-BLOCK EDGE-BREAK REQUIREMENT.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 8:1"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "cam-pin seated-end flatness": "0.05",
    "pinion cam-pin crown profile": "0.05",
}
